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
from uipath.eval.helpers import EVAL_SETS_DIRECTORY_NAME, EvalHelpers
from uipath.eval.models.evaluation_set import EvaluationSet
from uipath.eval.runtime import UiPathEvalContext, evaluate
from uipath.platform.chat import set_llm_concurrency
from uipath.platform.common import ResourceOverwritesContext, UiPathConfig
from uipath.runtime import (
    UiPathRuntimeContext,
    UiPathRuntimeFactoryRegistry,
    UiPathRuntimeSchema,
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


def _get_agent_model(schema: UiPathRuntimeSchema) -> str | None:
    """Get agent model from the runtime schema metadata.

    The model is read from schema.metadata["settings"]["model"] which is
    populated by the low-code agents runtime from agent.json.

    Returns:
        The model name from agent settings, or None if not found.
    """
    try:
        if schema.metadata and "settings" in schema.metadata:
            settings = schema.metadata["settings"]
            model = settings.get("model")
            if model:
                logger.debug(f"Got agent model from schema.metadata: {model}")
                return model
        return None
    except Exception:
        return None


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
                            ctx.job_id
                            or ctx.log_to_file
                            or should_register_progress_reporter
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
                            _get_agent_model(eval_context.runtime_schema),
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
