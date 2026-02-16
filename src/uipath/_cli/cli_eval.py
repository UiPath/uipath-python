import ast
import asyncio
import logging
import os
import uuid
from typing import Any

import click
from uipath.core.tracing import UiPathTraceManager
from uipath.runtime import (
    UiPathRuntimeContext,
    UiPathRuntimeFactoryRegistry,
    UiPathRuntimeProtocol,
    UiPathRuntimeSchema,
)

from uipath._cli._evals._console_progress_reporter import ConsoleProgressReporter
from uipath._cli._evals._evaluate import evaluate
from uipath._cli._evals._models._evaluation_set import EvaluationSet
from uipath._cli._evals._progress_reporter import StudioWebProgressReporter
from uipath._cli._evals._runtime import (
    LLMAgentRuntimeProtocol,
    UiPathEvalContext,
)
from uipath._cli._evals._telemetry import EvalTelemetrySubscriber
from uipath._cli._utils._folders import get_personal_workspace_key_async
from uipath._cli._utils._studio_project import StudioClient
from uipath._cli.middlewares import Middlewares
from uipath._events._event_bus import EventBus
from uipath._utils._bindings import ResourceOverwritesContext
from uipath.eval._helpers import auto_discover_entrypoint
from uipath.platform.chat import set_llm_concurrency
from uipath.platform.common import UiPathConfig
from uipath.telemetry._track import flush_events
from uipath.tracing import (
    JsonLinesFileExporter,
    LiveTrackingSpanProcessor,
    LlmOpsHttpExporter,
)

from ._utils._console import ConsoleLogger
from ._utils._eval_set import EvalHelpers

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


def _find_agent_model_in_runtime(runtime: UiPathRuntimeProtocol) -> str | None:
    """Recursively search for get_agent_model in runtime and its delegates.

    Runtimes may be wrapped (e.g., ResumableRuntime wraps TelemetryWrapper
    which wraps the base runtime). This method traverses the wrapper chain
    to find a runtime that implements LLMAgentRuntimeProtocol.

    Args:
        runtime: The runtime to check (may be a wrapper)

    Returns:
        The model name if found, None otherwise.
    """
    # Check if this runtime implements the protocol
    if isinstance(runtime, LLMAgentRuntimeProtocol):
        return runtime.get_agent_model()

    # Check for delegate property (used by UiPathResumableRuntime, TelemetryRuntimeWrapper)
    delegate = getattr(runtime, "delegate", None) or getattr(runtime, "_delegate", None)
    if delegate is not None:
        return _find_agent_model_in_runtime(delegate)

    return None


async def _get_agent_model(
    runtime: UiPathRuntimeProtocol, schema: UiPathRuntimeSchema
) -> str | None:
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

        # Fallback to protocol-based approach for backwards compatibility
        model = _find_agent_model_in_runtime(runtime)
        if model:
            logger.debug(f"Got agent model from runtime protocol: {model}")
        return model
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

        eval_context.entrypoint = entrypoint or auto_discover_entrypoint()
        eval_context.workers = workers
        eval_context.eval_set_run_id = eval_set_run_id
        eval_context.enable_mocker_cache = enable_mocker_cache

        # Load eval set to resolve the path
        eval_set_path = eval_set or EvalHelpers.auto_discover_eval_set()
        _, resolved_eval_set_path = EvalHelpers.load_eval_set(eval_set_path, eval_ids)

        eval_context.report_coverage = report_coverage
        eval_context.input_overrides = input_overrides
        eval_context.resume = resume

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
                    factory_settings = await runtime_factory.get_settings()
                    trace_settings = (
                        factory_settings.trace_settings if factory_settings else None
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
                            JsonLinesFileExporter(trace_file), settings=trace_settings
                        )

                    project_id = UiPathConfig.project_id

                    eval_context.execution_id = (
                        eval_context.job_id
                        or eval_context.eval_set_run_id
                        or str(uuid.uuid4())
                    )

                    # Load eval set (path is already resolved in cli_eval.py)
                    eval_context.evaluation_set, _ = EvalHelpers.load_eval_set(
                        resolved_eval_set_path, eval_ids
                    )

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
                        await _get_agent_model(runtime, eval_context.runtime_schema),
                    )

                    # Runtime is not required anymore.
                    await runtime.dispose()

                    try:
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
                            logger.debug("No UIPATH_PROJECT_ID configured, executing evaluation without resource overwrites")
                            ctx.result = await evaluate(
                                runtime_factory,
                                trace_manager,
                                eval_context,
                                event_bus,
                            )
                    finally:
                        if runtime_factory:
                            await runtime_factory.dispose()

            asyncio.run(execute_eval())

        except Exception as e:
            console.error(
                f"Error occurred: {e or 'Execution failed'}", include_traceback=True
            )
        finally:
            flush_events()


if __name__ == "__main__":
    eval()
