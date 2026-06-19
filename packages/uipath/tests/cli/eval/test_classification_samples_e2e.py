"""End-to-end tests that run the classification sample projects through evaluate().

These tests double as integration coverage for the binary and multiclass
classification evaluators added in #1397 — they wire each sample's main.py
into a stand-in runtime, run the full eval set, and assert the per-row scores
plus the aggregated metric produced by `reduce_scores`.
"""

import importlib.util
import uuid
from pathlib import Path
from types import ModuleType
from typing import Any, AsyncGenerator

import pytest

from uipath.core.events import EventBus
from uipath.core.tracing import UiPathTraceManager
from uipath.eval.helpers import EvalHelpers
from uipath.eval.runtime import UiPathEvalContext, evaluate
from uipath.eval.runtime._types import UiPathEvalOutput
from uipath.eval.runtime.runtime import compute_evaluator_scores
from uipath.runtime import (
    UiPathExecuteOptions,
    UiPathRuntimeEvent,
    UiPathRuntimeFactorySettings,
    UiPathRuntimeProtocol,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
    UiPathRuntimeStorageProtocol,
    UiPathStreamOptions,
)
from uipath.runtime.schema import UiPathRuntimeSchema

SAMPLES_DIR = Path(__file__).resolve().parents[3] / "samples"


def _load_sample_main(sample_dir: Path) -> ModuleType:
    """Import a sample's main.py as an isolated module."""
    module_name = f"_eval_sample_{sample_dir.name}"
    spec = importlib.util.spec_from_file_location(module_name, sample_dir / "main.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class _SampleRuntime:
    """Runtime that delegates execution to the sample's `main` function."""

    def __init__(self, sample_main: Any) -> None:
        self._sample_main = sample_main

    async def execute(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathExecuteOptions | None = None,
    ) -> UiPathRuntimeResult:
        input_model = self._sample_main.EmailInput(**(input or {}))
        output = await self._sample_main.main(input_model)
        return UiPathRuntimeResult(
            output={"category": output.category},
            status=UiPathRuntimeStatus.SUCCESSFUL,
        )

    async def stream(
        self,
        input: dict[str, Any] | None = None,
        options: UiPathStreamOptions | None = None,
    ) -> AsyncGenerator[UiPathRuntimeEvent, None]:
        yield await self.execute(input, None)

    async def get_schema(self) -> UiPathRuntimeSchema:
        return UiPathRuntimeSchema(
            filePath="main.py",
            uniqueId="main",
            type="agent",
            input={
                "type": "object",
                "properties": {
                    "email_subject": {"type": "string"},
                    "email_body": {"type": "string"},
                },
            },
            output={
                "type": "object",
                "properties": {"category": {"type": "string"}},
            },
        )

    async def dispose(self) -> None:
        pass


class _SampleFactory:
    def __init__(self, sample_main: Any) -> None:
        self._sample_main = sample_main

    def discover_entrypoints(self) -> list[str]:
        return ["main"]

    async def get_storage(self) -> UiPathRuntimeStorageProtocol | None:
        return None

    async def get_settings(self) -> UiPathRuntimeFactorySettings | None:
        return None

    async def new_runtime(
        self, entrypoint: str, runtime_id: str, **kwargs: Any
    ) -> UiPathRuntimeProtocol:
        return _SampleRuntime(self._sample_main)

    async def dispose(self) -> None:
        pass


async def _run_sample(sample_dir: Path) -> tuple[UiPathEvalOutput, dict[str, float]]:
    """Run the sample's eval set and return (per-row output, evaluator_averages)."""
    sample_main = _load_sample_main(sample_dir)
    factory = _SampleFactory(sample_main)

    eval_set_path = str(sample_dir / "evaluations" / "eval-sets" / "default.json")
    evaluation_set, _ = EvalHelpers.load_eval_set(eval_set_path)
    evaluators = await EvalHelpers.load_evaluators(
        eval_set_path, evaluation_set, agent_model=None
    )

    runtime = await factory.new_runtime("main", "test-runtime-id")
    runtime_schema = await runtime.get_schema()

    context = UiPathEvalContext()
    context.execution_id = str(uuid.uuid4())
    context.evaluation_set = evaluation_set
    context.runtime_schema = runtime_schema
    context.evaluators = evaluators

    result = await evaluate(
        factory,
        UiPathTraceManager(),
        context,
        EventBus(),
    )

    eval_output = UiPathEvalOutput.model_validate(result.output)
    _, evaluator_averages = compute_evaluator_scores(
        eval_output.evaluation_set_results, evaluators
    )
    return eval_output, evaluator_averages


def _per_row_scores(output: UiPathEvalOutput) -> dict[str, float]:
    return {
        row.evaluation_name: row.evaluation_run_results[0].result.score
        for row in output.evaluation_set_results
    }


async def test_binary_classification_sample_end_to_end():
    """Binary spam classifier: 4/5 datapoints correct, but precision is 2/3 because of one FP."""
    output, averages = await _run_sample(SAMPLES_DIR / "binary_classification_agent")

    per_row = _per_row_scores(output)
    assert per_row == {
        "Spam: prize giveaway": 1.0,
        "Spam: unsolicited promo": 1.0,
        "Ham: legitimate invoice": 1.0,
        "Ham: meeting request": 1.0,
        "Ham mislabeled as spam (forces a false positive)": 0.0,
    }
    # Precision = TP / (TP + FP) = 2 / (2 + 1) = 0.6666...
    assert averages["BinarySpamPrecision"] == pytest.approx(2 / 3, rel=1e-6)

    # Dataset-level aggregators embedded on the evaluator config also fire.
    # Each result keyed by "{evaluator_name}.{aggregator_type}".
    keys = set(output.dataset_evaluator_results)
    assert keys == {
        "BinarySpamPrecision.precision",
        "BinarySpamPrecision.recall",
        "BinarySpamPrecision.fscore",
    }


async def test_multiclass_classification_sample_end_to_end():
    """Multiclass router: 6/7 correct, macro F1 = (0.8 + 0.8 + 1.0) / 3 = 0.8666..."""
    output, averages = await _run_sample(
        SAMPLES_DIR / "multiclass_classification_simple"
    )

    per_row = _per_row_scores(output)
    assert per_row == {
        "Payments: invoice reminder": 1.0,
        "Payments: refund request": 1.0,
        "Support: feature broken": 1.0,
        "Support: how-to question": 1.0,
        "Spam: prize giveaway": 1.0,
        "Spam: marketing winner": 1.0,
        "Support email accidentally routed to payments "
        "(forces an FP for payments)": 0.0,
    }
    # payments F1=0.8 (P=2/3, R=1), support F1=0.8 (P=1, R=2/3), spam F1=1.0
    # macro = mean = 2.6 / 3
    assert averages["EmailMulticlassFScore"] == pytest.approx(2.6 / 3, rel=1e-6)

    # Three embedded aggregators ran in addition to reduce_scores.
    keys = set(output.dataset_evaluator_results)
    assert keys == {
        "EmailMulticlassFScore.precision",
        "EmailMulticlassFScore.recall",
        "EmailMulticlassFScore.fscore",
    }
    # The macro F1 computed by the embedded fscore aggregator should match
    # reduce_scores' result (both walk the same confusion matrix).
    fscore_result = output.dataset_evaluator_results["EmailMulticlassFScore.fscore"]
    assert fscore_result.score == pytest.approx(2.6 / 3, rel=1e-6)
