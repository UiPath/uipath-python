from asyncio import Protocol
from typing import Any, Optional

from uipath._cli._evals._models._progress_events import (
    CreateEvalRunEvent,
    CreateEvalSetRunEvent,
    ProgressEvent,
    UpdateEvalRunEvent,
    UpdateEvalSetRunEvent,
)
from uipath._cli._evals._models._sw_reporting import SwProgressItem
from uipath._cli._evals._progress_reporter import StudioWebProgressReporter
from uipath.eval.models import ScoreType


class ProgressHandler(Protocol):
    async def handle_event(self, event: ProgressEvent) -> Optional[Any]: ...


class StudioWebProgressHandler:
    def __init__(self):
        self.reporter = StudioWebProgressReporter()
        self.eval_set_run_id: Optional[str] = None
        self.evaluators: dict[str, Any] = {}
        self.evaluator_scores: dict[str, list[float]] = {}

    async def handle_event(self, event: ProgressEvent) -> Optional[Any]:
        if isinstance(event, CreateEvalSetRunEvent):
            self.evaluators = {eval.id: eval for eval in event.evaluators}
            self.evaluator_scores = {eval.id: [] for eval in event.evaluators}
            self.eval_set_run_id = await self.reporter.create_eval_set_run(
                eval_set_id=event.eval_set_id,
                agent_snapshot=event.agent_snapshot,
                no_of_evals=event.no_of_evals,
                evaluators=event.evaluators,
            )
            return self.eval_set_run_id
        elif isinstance(event, CreateEvalRunEvent):
            if self.eval_set_run_id:
                return await self.reporter.create_eval_run(
                    event.eval_item, self.eval_set_run_id
                )
        elif isinstance(event, UpdateEvalRunEvent):
            for eval_result in event.eval_results:
                match eval_result.result.score_type:
                    case ScoreType.NUMERICAL:
                        self.evaluator_scores[eval_result.evaluator_id].append(
                            eval_result.result.score
                        )
                    case ScoreType.BOOLEAN:
                        self.evaluator_scores[eval_result.evaluator_id].append(
                            100 if eval_result.result.score else 0
                        )
                    case ScoreType.ERROR:
                        self.evaluator_scores[eval_result.evaluator_id].append(0)

            await self.reporter.update_eval_run(
                SwProgressItem(
                    eval_run_id=event.eval_run_id,
                    eval_results=event.eval_results,
                    success=event.success,
                    agent_output=event.agent_output,
                    agent_execution_time=event.agent_execution_time,
                ),
                self.evaluators,
            )
        elif isinstance(event, UpdateEvalSetRunEvent):
            if self.eval_set_run_id:
                await self.reporter.update_eval_set_run(
                    self.eval_set_run_id,
                    self.evaluator_scores,
                    self.evaluators,
                )
        return None
