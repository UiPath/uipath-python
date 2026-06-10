import ast
import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Any

import click

from uipath._cli._errors import EntrypointDiscoveryException
from uipath._cli._evals._console_progress_reporter import ConsoleProgressReporter
from uipath._cli._evals._progress_reporter import StudioWebProgressReporter
from uipath._cli._evals._telemetry import EvalTelemetrySubscriber
from uipath._cli._utils._folders import get_personal_workspace_key_async
from uipath._cli._utils._studio_project import StudioClient
from uipath._cli.middlewares import Middlewares
from uipath.core.events import EventBus
from uipath.core.tracing import UiPathTraceManager
from uipath.eval.helpers import EVAL_SETS_DIRECTORY_NAME, EvalHelpers, get_agent_model
from uipath.eval.models.evaluation_set import EvaluationSet
from uipath.eval.runtime import UiPathEvalContext, evaluate
from uipath.platform.chat import set_llm_concurrency
from uipath.platform.common import ResourceOverwritesContext, UiPathConfig
from uipath.runtime import (
    UiPathRuntimeContext,
    UiPathRuntimeFactoryRegistry,
)
from uipath.telemetry._track import flush_events
from uipath.tracing import (
    JsonLinesFileExporter,
    LiveTrackingSpanProcessor,
    LlmOpsHttpExporter,
)

from ._utils._console import ConsoleLogger

logger = logging.getLogger(__name__)
console = ConsoleLogger()


class LiteralOption(click.Option):
    def type_cast_value(self, ctx, value):
        try:
            return ast.literal_eval(value)
        except Exception as e:
            raise click.BadParameter(value) from e


def setup_reporting_prereq(no_report: bool) -> bool:
    if no_report:
        return False

    if not UiPathConfig.is_studio_project:
        console.warning(
            "UIPATH_PROJECT_ID environment variable not set. Results will not be reported to Studio Web."
        )
        return False

    if not UiPathConfig.folder_key:
        folder_key = asyncio.run(get_personal_workspace_key_async())
        if folder_key:
            os.environ["UIPATH_FOLDER_KEY"] = folder_key
    return True


def _detect_agent_type_from_solution() -> tuple[bool, Path, Path]:
    """Read agent.json from CWD to determine whether this is a low-code agent.

    and which eval-sets / evaluators directories to walk.

    The HDENS executor downloads the project tree (including agent.json) into
    the subprocess working directory before invoking us; reading the
    discriminator from disk lets the activity stay agnostic to agent type.

    Returns (is_low_code_agent, eval_sets_dir, evaluators_dir). Falls back to
    coded paths when agent.json is missing or unreadable — matches the
    previous default and keeps standalone-CLI behavior intact.
    """
    import json

    agent_file = Path.cwd() / "agent.json"
    is_low_code = False
    if agent_file.exists():
        try:
            data = json.loads(agent_file.read_text(encoding="utf-8"))
            is_low_code = data.get("type") == "lowCode"
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "aggregate: failed to read agent.json (%s); defaulting to coded.",
                exc,
            )

    if is_low_code:
        return True, Path("evals/eval-sets/"), Path("evals/evaluators/")
    return False, Path("evaluations/eval-sets/"), Path("evaluations/evaluators/")


def _load_aggregators_via_evalsets(
    eval_sets_dir: Path,
    evaluators_dir: Path,
) -> dict[str, list[dict[str, Any]]]:
    """Walk the eval-sets directory to discover which evaluators are in any.

    eval config (eval set), then look up each referenced evaluator's
    aggregator config from the evaluators directory.

    Orphaned evaluator files (not referenced by any eval set) are skipped,
    matching the user's expectation that "what runs in this eval pipeline"
    drives "what gets aggregated."

    Returns {evaluator_id: aggregators[]}. Evaluators without an
    `aggregators` field are simply absent from the map.
    """
    import json

    # First pass: walk eval-sets to collect the union of referenced evaluator
    # ids across every eval config in the solution.
    referenced_ids: set[str] = set()
    if eval_sets_dir.exists() and eval_sets_dir.is_dir():
        for path in eval_sets_dir.glob("*.json"):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("aggregate: failed to read eval set %s: %s", path, exc)
                continue
            refs = data.get("evaluatorRefs") if isinstance(data, dict) else None
            if isinstance(refs, list):
                for ref in refs:
                    if isinstance(ref, str) and ref:
                        referenced_ids.add(ref)
    else:
        logger.warning("aggregate: eval-sets dir '%s' does not exist.", eval_sets_dir)

    if not referenced_ids:
        logger.info("aggregate: no eval set references any evaluator; nothing to do.")
        return {}

    # Second pass: walk evaluator files (file naming isn't deterministic from
    # id), match each by its embedded `id` field, extract aggregators.
    result: dict[str, list[dict[str, Any]]] = {}
    if not evaluators_dir.exists() or not evaluators_dir.is_dir():
        logger.warning("aggregate: evaluators dir '%s' does not exist.", evaluators_dir)
        return result

    for path in evaluators_dir.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("aggregate: failed to read evaluator %s: %s", path, exc)
            continue
        if not isinstance(data, dict):
            continue
        evaluator_id = data.get("id")
        if not isinstance(evaluator_id, str) or evaluator_id not in referenced_ids:
            continue
        # Coded shape (evaluatorConfig.aggregators) first; legacy low-code
        # may store it top-level.
        aggregators = None
        ec = data.get("evaluatorConfig")
        if isinstance(ec, dict) and isinstance(ec.get("aggregators"), list):
            aggregators = ec["aggregators"]
        elif isinstance(data.get("aggregators"), list):
            aggregators = data["aggregators"]
        if aggregators:
            result[evaluator_id] = aggregators

    return result


def _load_aggregators_from_evaluators_dir(
    evaluators_dir: str,
) -> dict[str, list[dict[str, Any]]]:
    """Walk a directory of evaluator JSON files; return a {evaluator_id:.

    aggregators[]} map for any evaluator whose JSON declares an
    `aggregators` field (under `evaluatorConfig` for coded-shape files,
    or top-level for low-code legacy shape — checks both for resilience
    to evaluator JSON variations).

    File-naming is not assumed; the evaluator id is read from each file's
    `id` field. Glob is `*.json`. Files that don't parse, lack an `id`,
    or lack an `aggregators` field are simply skipped.
    """
    import json

    result: dict[str, list[dict[str, Any]]] = {}
    base = Path(evaluators_dir)
    if not base.exists() or not base.is_dir():
        logger.warning(
            "aggregate: evaluators dir '%s' does not exist; skipping.", evaluators_dir
        )
        return result

    for path in base.glob("*.json"):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("aggregate: failed to read %s: %s", path, exc)
            continue
        if not isinstance(data, dict):
            continue
        evaluator_id = data.get("id")
        if not isinstance(evaluator_id, str) or not evaluator_id:
            continue
        # Coded-shape: evaluatorConfig.aggregators. Low-code legacy: top-
        # level aggregators. Check coded first since most evaluator files
        # follow that shape.
        aggregators = None
        ec = data.get("evaluatorConfig")
        if isinstance(ec, dict) and isinstance(ec.get("aggregators"), list):
            aggregators = ec["aggregators"]
        elif isinstance(data.get("aggregators"), list):
            aggregators = data["aggregators"]
        if aggregators:
            result[evaluator_id] = aggregators

    return result


async def _fetch_observations_from_api(
    eval_set_run_id: str,
    is_low_code_agent: bool,
) -> dict:
    """Fetch the per-datapoint observations payload for this eval-set-run.

    from the backend's observations endpoint. Uses the same authenticated
    HTTP client the reporter uses for its UpdateEvalSetRun POST — same
    JWT, same base URL — so no extra auth wiring needed.

    Routing mirrors `StudioWebProgressReporter`: respects
    `UIPATH_EVAL_BACKEND_URL` so local-backend dev (localhost:5001) works
    without hitting alpha, and uses the matching `scoped`/URL-prefix
    combo (`org` + `api/` for localhost, `tenant` + `agentsruntime_/api/`
    for cloud).
    """
    from urllib.parse import urlparse

    from uipath._utils.constants import (
        ENV_EVAL_BACKEND_URL,
        ENV_TENANT_ID,
        HEADER_INTERNAL_TENANT_ID,
    )
    from uipath.platform import UiPath

    eval_backend_url = os.getenv(ENV_EVAL_BACKEND_URL)
    uipath = UiPath(base_url=eval_backend_url) if eval_backend_url else UiPath()
    api_client = uipath.api_client
    project_id = os.getenv("UIPATH_PROJECT_ID") or os.getenv("UIPATH_AGENT_ID")
    if not project_id:
        raise RuntimeError(
            "aggregate-only API fetch requires UIPATH_PROJECT_ID (or "
            "UIPATH_AGENT_ID) to construct the observations URL."
        )

    is_localhost = False
    if eval_backend_url:
        try:
            parsed = urlparse(eval_backend_url)
            hostname = parsed.hostname or parsed.netloc.split(":")[0]
            is_localhost = hostname.lower() in ("localhost", "127.0.0.1")
        except Exception:
            pass

    prefix = "api/" if is_localhost else "agentsruntime_/api/"
    endpoint = f"{prefix}execution/agents/{project_id}/evalSetRuns/{eval_set_run_id}/observations"
    headers: dict[str, str] = {}
    tenant_id = os.getenv(ENV_TENANT_ID)
    if tenant_id:
        headers[HEADER_INTERNAL_TENANT_ID] = tenant_id
    response = await api_client.request_async(
        method="GET",
        url=endpoint,
        params={"isLowCodeAgent": str(is_low_code_agent).lower()},
        headers=headers,
        scoped="org" if is_localhost else "tenant",
    )
    response.raise_for_status()
    import json as _json

    return _json.loads(response.content)


async def _run_aggregate(
    eval_set_run_id: str,
    aggregate_config_json: str | None,
    no_report: bool,
    output_file: str | None,
) -> None:
    """Aggregate post-pass. Self-contained: detects agent type from.

    agent.json in CWD, walks eval-sets to discover which evaluators are in
    eval configs, reads each evaluator JSON's aggregator config, fetches
    per-datapoint observations from the backend via API, computes
    per-evaluator metrics, ships results via the reporter on
    UpdateEvalSetRun.

    Aggregator config comes from each evaluator's JSON `aggregators` field
    (canonical source — what the user authored in the UI).

    Observations come from GET /api/execution/agents/{agentId}/
    evalSetRuns/{evalSetRunId}/observations using the same authenticated
    HTTP client the reporter uses (same JWT, same base URL — no extra
    auth wiring needed).
    """
    import json

    from uipath.eval.aggregators import compute_aggregations

    # Determine agent type + project dirs from the solution itself. The
    # HDENS executor downloads agent.json into CWD before invoking us, so
    # this works without any flag plumbing from the C# activity.
    is_low_code_agent, eval_sets_dir, evaluators_dir = (
        _detect_agent_type_from_solution()
    )
    logger.info(
        "aggregate: detected is_low_code_agent=%s, walking eval sets at %s, evaluators at %s",
        is_low_code_agent,
        eval_sets_dir,
        evaluators_dir,
    )

    # Two-step walk:
    #   1. Walk eval-sets dir; collect the union of evaluatorRefs across
    #      every eval config (eval set file) in the solution.
    #   2. Walk the evaluators dir; for each evaluator whose id is in that
    #      referenced set, pull its `aggregators` config.
    # Orphaned evaluator files (not referenced by any eval set) are skipped.
    per_evaluator_aggregators = _load_aggregators_via_evalsets(
        eval_sets_dir, evaluators_dir
    )
    if not per_evaluator_aggregators:
        logger.info(
            "aggregate: no eval-set-referenced evaluator under '%s' declared an"
            " aggregators field; nothing to do.",
            evaluators_dir,
        )
        return

    payload = await _fetch_observations_from_api(
        eval_set_run_id=eval_set_run_id,
        is_low_code_agent=is_low_code_agent,
    )
    observation_rows = payload.get("observations") or []
    if not observation_rows:
        logger.info("aggregate: no observations returned from API; nothing to do.")
        return

    # Backfill aggregator config onto each observation row so the existing
    # compute_aggregations harvester can pick it up — keeps the math one
    # implementation regardless of where config came from.
    for row in observation_rows:
        ev_id = row.get("evaluatorId")
        if ev_id and ev_id in per_evaluator_aggregators and "aggregators" not in row:
            row["aggregators"] = per_evaluator_aggregators[ev_id]

    # Reshape into the eval-output dict shape that compute_aggregations'
    # harvester already understands. One synthetic eval-set-result row per
    # observation; the harvester only cares about evaluatorName and details.
    eval_output: dict[str, Any] = {
        "evaluationSetResults": [
            {
                "evaluationName": f"obs-{i}",
                "evaluationRunResults": [
                    {
                        "evaluatorName": row.get("evaluatorId")
                        or row.get("evaluatorName"),
                        "result": {
                            "details": {
                                k: v
                                for k, v in row.items()
                                if k not in ("evaluatorId", "evaluatorName")
                            }
                        },
                    }
                ],
            }
            for i, row in enumerate(observation_rows)
        ]
    }

    aggregations = compute_aggregations(aggregate_config_json, eval_output)
    logger.info(
        "aggregate-only: computed metrics for %d evaluator(s) from %d observations.",
        len(aggregations),
        len(observation_rows),
    )

    if output_file:
        # Optional convenience: stash the result locally for inspection.
        Path(output_file).write_text(
            json.dumps({"aggregations": aggregations}, indent=2),
            encoding="utf-8",
        )

    if no_report or not aggregations:
        return

    # Ship the result via the existing reporter on UpdateEvalSetRun.
    # `evaluator_scores={}` because aggregate-only doesn't recompute the
    # per-evaluator averages — the original per-datapoint run already did.
    reporter = StudioWebProgressReporter()
    await reporter.update_eval_set_run(
        eval_set_run_id=eval_set_run_id,
        evaluator_scores={},
        # is_low_code_agent was detected from agent.json above; the reporter
        # needs the inverse — `is_coded` toggles the endpoint suffix
        # (`coded/evalSetRun` vs `evalSetRun`) so the aggregations land in
        # the right table (CodedEvalSetRun vs EvalSetRun).
        is_coded=not is_low_code_agent,
        success=True,
        aggregations=aggregations,
    )


def _resolve_model_settings_override(
    model_settings_id: str, evaluation_set: EvaluationSet
) -> dict[str, Any] | None:
    """Resolve model settings override from evaluation set.

    Returns:
        Model settings dict to use for override, or None if using defaults.
        Settings are passed to factory via settings kwarg.
    """
    # Skip if no model settings ID specified or using default
    if not model_settings_id or model_settings_id == "default":
        return None

    # Load evaluation set to get model settings
    if not evaluation_set.model_settings:
        logger.warning("No model settings available in evaluation set")
        return None

    # Find the specified model settings
    target_model_settings = next(
        (ms for ms in evaluation_set.model_settings if ms.id == model_settings_id),
        None,
    )

    if not target_model_settings:
        logger.warning(
            f"Model settings ID '{model_settings_id}' not found in evaluation set"
        )
        return None

    logger.info(
        f"Applying model settings override: model={target_model_settings.model_name}, temperature={target_model_settings.temperature}"
    )

    # Return settings dict with correct keys for factory
    override: dict[str, str | float] = {}
    if (
        target_model_settings.model_name
        and target_model_settings.model_name != "same-as-agent"
    ):
        override["model"] = target_model_settings.model_name
    if (
        target_model_settings.temperature is not None
        and target_model_settings.temperature != "same-as-agent"
    ):
        override["temperature"] = float(target_model_settings.temperature)

    return override if override else None


class _EvalDiscoveryError(EntrypointDiscoveryException):
    """Raised when auto-discovery of entrypoint or eval set fails."""

    def __init__(self, entrypoints: list[str], eval_sets: list[Path]):
        super().__init__(entrypoints)
        self.eval_sets = eval_sets

    def get_usage_help(self) -> list[str]:
        lines = super().get_usage_help()

        if self.eval_sets:
            lines.append("")
            lines.append("Available eval sets:")
            for f in self.eval_sets:
                lines.append(f"  - {f}")
        else:
            lines.append("")
            lines.append(
                f"No eval sets found in '{EVAL_SETS_DIRECTORY_NAME}/' directory."
            )

        lines.append("")
        lines.append("Usage: uipath eval <entrypoint> <eval_set>")
        if self.entrypoints and self.eval_sets:
            lines.append(
                f"Example: uipath eval {self.entrypoints[0]} {self.eval_sets[0]}"
            )
        return lines


def _discover_eval_sets() -> list[Path]:
    """Discover available eval set files."""
    eval_sets_dir = Path(EVAL_SETS_DIRECTORY_NAME)
    if eval_sets_dir.exists():
        return sorted(eval_sets_dir.glob("*.json"))
    return []


@click.command()
@click.argument("entrypoint", required=False)
@click.argument("eval_set", required=False)
@click.option("--eval-ids", cls=LiteralOption, default="[]")
@click.option(
    "--eval-set-run-id",
    required=False,
    type=str,
    help="Custom evaluation set run ID (if not provided, a UUID will be generated)",
)
@click.option(
    "--no-report",
    is_flag=True,
    help="Do not report the evaluation results",
    default=False,
)
@click.option(
    "--workers",
    type=int,
    default=1,
    help="Number of parallel workers for running evaluations (default: 1)",
)
@click.option(
    "--output-file",
    required=False,
    type=click.Path(exists=False),
    help="File path where the output will be written",
)
@click.option(
    "--enable-mocker-cache",
    is_flag=True,
    default=False,
    help="Enable caching for LLM mocker responses",
)
@click.option(
    "--report-coverage",
    is_flag=True,
    default=False,
    help="Report evaluation coverage",
)
@click.option(
    "--model-settings-id",
    type=str,
    default="default",
    help="Model settings ID from evaluation set to override agent settings (default: 'default')",
)
@click.option(
    "--trace-file",
    required=False,
    type=click.Path(exists=False),
    help="File path where traces will be written in JSONL format",
)
@click.option(
    "--max-llm-concurrency",
    type=int,
    default=20,
    help="Maximum concurrent LLM requests (default: 20)",
)
@click.option(
    "--input-overrides",
    cls=LiteralOption,
    default="{}",
    help='Input field overrides per evaluation ID: \'{"eval-1": {"operator": "*"}, "eval-2": {"a": 100}}\'. Supports deep merge for nested objects.',
)
@click.option(
    "--resume",
    is_flag=True,
    default=False,
    help="Resume execution from a previous suspended state",
)
@click.option(
    "--verbose",
    is_flag=True,
    default=False,
    help="Include agent execution output (trace, result) in the output file",
)
@click.option(
    "--aggregate-only",
    is_flag=True,
    default=False,
    help=(
        "Cloud subprocess mode flag. Skip agent execution and run only the"
        " aggregator post-pass. Reads agent.json from CWD to detect"
        " low-code vs coded, walks eval-sets + evaluators dirs for config,"
        " fetches observations from the backend via API, computes metrics"
        " per evaluator, ships results via the reporter on UpdateEvalSetRun."
        " Used by the orchestrator's final aggregation activity."
    ),
)
@click.option(
    "--aggregator-config-file",
    required=False,
    type=str,
    help=(
        "Local CLI ergonomic. Path to an evaluator JSON file. The"
        " evaluator's `aggregators` field is loaded and used as the"
        " aggregator config for the in-process post-pass that runs at the"
        " end of `uipath eval`. Compose with `--output-file` to merge"
        " aggregations into the persisted blob."
    ),
)
def eval(
    entrypoint: str | None,
    eval_set: str | None,
    eval_ids: list[str],
    eval_set_run_id: str | None,
    no_report: bool,
    workers: int,
    output_file: str | None,
    enable_mocker_cache: bool,
    report_coverage: bool,
    model_settings_id: str,
    trace_file: str | None,
    max_llm_concurrency: int,
    input_overrides: dict[str, Any],
    resume: bool,
    verbose: bool,
    aggregate_only: bool,
    aggregator_config_file: str | None,
) -> None:
    """Run an evaluation set against the agent.

    Args:
        entrypoint: Path to the agent script to evaluate (optional, will auto-discover if not specified)
        eval_set: Path to the evaluation set JSON file (optional, will auto-discover if not specified)
        eval_ids: Optional list of evaluation IDs
        eval_set_run_id: Custom evaluation set run ID (optional, will generate UUID if not specified)
        workers: Number of parallel workers for running evaluations
        no_report: Do not report the evaluation results
        enable_mocker_cache: Enable caching for LLM mocker responses
        report_coverage: Report evaluation coverage
        model_settings_id: Model settings ID to override agent settings
        trace_file: File path where traces will be written in JSONL format
        max_llm_concurrency: Maximum concurrent LLM requests
        input_overrides: Input field overrides mapping (direct field override with deep merge)
        resume: Resume execution from a previous suspended state
    """
    set_llm_concurrency(max_llm_concurrency)

    should_register_progress_reporter = setup_reporting_prereq(no_report)

    # Aggregate-only mode: skip agent execution entirely. The cloud
    # orchestrator's final aggregation activity invokes us this way, passing
    # observations harvested from EvalScore rows. We compute metrics in
    # process and ship them via the existing reporter on UpdateEvalSetRun.
    # Cloud subprocess mode: --aggregate-only triggers the self-contained
    # aggregate flow. No eval execution; observations come from the API.
    if aggregate_only:
        if not eval_set_run_id:
            console.error(
                "--aggregate-only requires --eval-set-run-id so the reporter"
                " can target the right run and the observations endpoint can"
                " be constructed."
            )
            return
        asyncio.run(
            _run_aggregate(
                eval_set_run_id=eval_set_run_id,
                aggregate_config_json=None,
                no_report=no_report,
                output_file=output_file,
            )
        )
        return

    # Local CLI ergonomic: --aggregator-config-file=<file> reads an evaluator
    # JSON and uses its `aggregators` field as the config for the in-process
    # post-pass that runs after the eval. Doesn't change the eval-execution
    # mode. When omitted, per-evaluator aggregators (already embedded in each
    # observation's details by the SDK evaluator class) are used.
    aggregate_config: str | None = None
    if aggregator_config_file:
        import json

        try:
            evaluator_doc = json.loads(
                Path(aggregator_config_file).read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError) as exc:
            console.error(
                f"--aggregator-config-file: failed to read {aggregator_config_file}: {exc}"
            )
            return
        ec = (
            evaluator_doc.get("evaluatorConfig")
            if isinstance(evaluator_doc, dict)
            else None
        )
        specs = None
        if isinstance(ec, dict) and isinstance(ec.get("aggregators"), list):
            specs = ec["aggregators"]
        elif isinstance(evaluator_doc, dict) and isinstance(
            evaluator_doc.get("aggregators"), list
        ):
            specs = evaluator_doc["aggregators"]
        if not specs:
            console.error(
                f"--aggregator-config-file: {aggregator_config_file} has no"
                " `aggregators` array (looked at top-level and under"
                " `evaluatorConfig`)."
            )
            return
        aggregate_config = json.dumps({"aggregators": specs})

    result = Middlewares.next(
        "eval",
        entrypoint,
        eval_set,
        eval_ids,
        eval_set_run_id=eval_set_run_id,
        no_report=no_report,
        workers=workers,
        output_file=output_file,
        register_progress_reporter=should_register_progress_reporter,
    )

    if result.error_message:
        console.error(result.error_message)

    if result.should_continue:
        eval_context = UiPathEvalContext()
        eval_context.workers = workers
        eval_context.eval_set_run_id = eval_set_run_id
        eval_context.enable_mocker_cache = enable_mocker_cache
        eval_context.report_coverage = report_coverage
        eval_context.input_overrides = input_overrides
        eval_context.resume = resume
        eval_context.verbose = verbose
        # Carry the aggregator config (from --aggregator-config-file, if
        # provided) onto the runtime context so the eval runtime can compute
        # aggregations from in-memory results just before publishing the
        # final EvalSetRunUpdatedEvent. The reporter picks up the result
        # and ships it on its existing UpdateEvalSetRun POST.
        eval_context.aggregate_config_json = aggregate_config

        try:

            async def execute_eval():
                event_bus = EventBus()

                # Only create studio web exporter when reporting to Studio Web
                if should_register_progress_reporter:
                    progress_reporter = StudioWebProgressReporter()
                    await progress_reporter.subscribe_to_eval_runtime_events(event_bus)

                console_reporter = ConsoleProgressReporter()
                await console_reporter.subscribe_to_eval_runtime_events(event_bus)

                telemetry_subscriber = EvalTelemetrySubscriber()
                await telemetry_subscriber.subscribe_to_eval_runtime_events(event_bus)

                trace_manager = UiPathTraceManager()

                with UiPathRuntimeContext.with_defaults(
                    output_file=output_file,
                    trace_manager=trace_manager,
                    command="eval",
                    resume=resume,
                ) as ctx:
                    # Set job_id in eval context for single runtime runs
                    eval_context.job_id = ctx.job_id

                    runtime_factory = UiPathRuntimeFactoryRegistry.get(context=ctx)

                    try:
                        # Auto-discover entrypoint and eval set using the runtime factory
                        resolved_entrypoint = entrypoint
                        eval_set_path = eval_set

                        available_entrypoints = runtime_factory.discover_entrypoints()
                        available_eval_sets = _discover_eval_sets()

                        if not resolved_entrypoint:
                            if len(available_entrypoints) == 1:
                                resolved_entrypoint = available_entrypoints[0]
                            else:
                                raise _EvalDiscoveryError(
                                    available_entrypoints, available_eval_sets
                                )

                        if not eval_set_path:
                            if len(available_eval_sets) == 1:
                                eval_set_path = str(available_eval_sets[0])
                            else:
                                raise _EvalDiscoveryError(
                                    available_entrypoints, available_eval_sets
                                )

                        eval_context.entrypoint = resolved_entrypoint

                        # Load eval set and resolve the path
                        loaded_eval_set, resolved_eval_set_path = (
                            EvalHelpers.load_eval_set(
                                eval_set_path, eval_ids, input_overrides=input_overrides
                            )
                        )

                        factory_settings = await runtime_factory.get_settings()
                        trace_settings = (
                            factory_settings.trace_settings
                            if factory_settings
                            else None
                        )

                        if (
                            ctx.job_id or should_register_progress_reporter
                        ) and UiPathConfig.is_tracing_enabled:
                            # Live tracking for Orchestrator or Studio Web
                            # Uses UIPATH_TRACE_ID from environment for trace correlation
                            trace_manager.add_span_processor(
                                LiveTrackingSpanProcessor(
                                    LlmOpsHttpExporter(),
                                    settings=trace_settings,
                                )
                            )

                        if trace_file:
                            trace_settings = (
                                factory_settings.trace_settings
                                if factory_settings
                                else None
                            )
                            trace_manager.add_span_exporter(
                                JsonLinesFileExporter(trace_file),
                                settings=trace_settings,
                            )

                        project_id = UiPathConfig.project_id

                        eval_context.execution_id = (
                            eval_context.job_id
                            or eval_context.eval_set_run_id
                            or str(uuid.uuid4())
                        )

                        eval_context.evaluation_set = loaded_eval_set

                        # Resolve model settings override from eval set
                        settings_override = _resolve_model_settings_override(
                            model_settings_id, eval_context.evaluation_set
                        )

                        runtime = await runtime_factory.new_runtime(
                            entrypoint=eval_context.entrypoint or "",
                            runtime_id=eval_context.execution_id,
                            settings=settings_override,
                        )

                        eval_context.runtime_schema = await runtime.get_schema()

                        eval_context.evaluators = await EvalHelpers.load_evaluators(
                            resolved_eval_set_path,
                            eval_context.evaluation_set,
                            get_agent_model(eval_context.runtime_schema),
                        )

                        # Runtime is not required anymore.
                        await runtime.dispose()

                        if project_id:
                            studio_client = StudioClient(project_id)

                            async with ResourceOverwritesContext(
                                lambda: studio_client.get_resource_overwrites()
                            ):
                                ctx.result = await evaluate(
                                    runtime_factory,
                                    trace_manager,
                                    eval_context,
                                    event_bus,
                                )
                        else:
                            logger.debug(
                                "No UIPATH_PROJECT_ID configured, executing evaluation without resource overwrites"
                            )
                            ctx.result = await evaluate(
                                runtime_factory,
                                trace_manager,
                                eval_context,
                                event_bus,
                            )
                    finally:
                        await runtime_factory.dispose()

            asyncio.run(execute_eval())

            # Aggregator post-pass.
            #
            # Two sources of aggregator config, by precedence:
            #   1. `--aggregator-config-file=<path>` — read an evaluator JSON's
            #      `aggregators` field and use it as a global override.
            #   2. Per-evaluator config — each evaluator class reads its
            #      `aggregators` field from the evaluator JSON and embeds the
            #      list in every result's `details["aggregators"]`. The
            #      harvester in compute_aggregations picks them up without
            #      any flag.
            #
            # We always run the post-pass when --output-file is set; the
            # harvester is a no-op if nothing was emitted. This means
            # `uipath eval main eval-set.json --output-file out.json` picks
            # up whatever each evaluator's JSON config declared, with no
            # extra flag required.
            if output_file:
                from uipath.eval.aggregators import apply_to_output_file

                apply_to_output_file(
                    aggregate_config_json=aggregate_config,
                    eval_output_path=output_file,
                )
            elif aggregate_config:
                console.error(
                    "--aggregator-config-file requires --output-file so the"
                    " results can be merged into the persisted blob."
                )

        except _EvalDiscoveryError as e:
            click.echo("\n".join(e.get_usage_help()))
            if not e.entrypoints:
                click.echo()
                console.link(
                    "uipath.json spec:",
                    "https://github.com/UiPath/uipath-python/blob/main/packages/uipath/specs/uipath.spec.md",
                )
        except ValueError as e:
            console.error(str(e))
        except Exception as e:
            console.error(
                f"Error occurred: {e or 'Execution failed'}", include_traceback=True
            )
        finally:
            flush_events()


if __name__ == "__main__":
    eval()
