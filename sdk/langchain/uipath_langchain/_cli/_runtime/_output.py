import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from functools import cached_property
from typing import Any, Dict, Optional, Union, cast

from langgraph.types import Interrupt, StateSnapshot
from uipath_sdk._cli._runtime._contracts import (
    UiPathApiTrigger,
    UiPathErrorCategory,
    UiPathResumeTrigger,
    UiPathResumeTriggerType,
    UiPathRuntimeResult,
    UiPathRuntimeStatus,
)
from uipath_sdk._models.actions import Action

from ._context import LangGraphRuntimeContext
from ._escalation import Escalation
from ._exception import LangGraphRuntimeError

logger = logging.getLogger(__name__)


@dataclass
class InterruptInfo:
    """Contains all information about an interrupt."""

    value: Any

    @property
    def type(self) -> Optional[UiPathResumeTriggerType]:
        """Returns the type of the interrupt value."""
        if isinstance(self.value, Action):
            return UiPathResumeTriggerType.ACTION
        return None

    @property
    def identifier(self) -> Optional[str]:
        """Returns the identifier based on the type."""
        if isinstance(self.value, Action):
            return str(self.value.key)
        return None

    def serialize(self) -> str:
        """
        Converts the interrupt value to a JSON string if possible,
        falls back to string representation if not.
        """
        try:
            if hasattr(self.value, "dict"):
                data = self.value.dict()
            elif hasattr(self.value, "to_dict"):
                data = self.value.to_dict()
            elif hasattr(self.value, "__dataclass_fields__"):
                data = asdict(self.value)
            else:
                data = dict(self.value)

            return json.dumps(data, default=str)
        except (TypeError, ValueError, json.JSONDecodeError):
            return str(self.value)

    @cached_property
    def resume_trigger(self) -> UiPathResumeTrigger:
        """Creates the resume trigger based on interrupt type."""
        if self.type is None:
            return UiPathResumeTrigger(
                api_resume=UiPathApiTrigger(
                    inbox_id=str(uuid.uuid4()), request=self.serialize()
                )
            )
        else:
            return UiPathResumeTrigger(itemKey=self.identifier, triggerType=self.type)


@dataclass
class LangGraphOutputProcessor:
    """
    Contains and manages the complete output information from graph execution.
    Handles serialization, interrupt data, and file output.
    """

    context: LangGraphRuntimeContext

    _interrupt_info: Optional[InterruptInfo] = field(
        default=None, init=False, repr=False
    )
    _resume_trigger: Optional[UiPathResumeTrigger] = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self):
        """Process and cache interrupt information after initialization."""
        state = cast(StateSnapshot, self.context.state)
        if not state or not hasattr(state, "next") or not state.next:
            return

        for task in state.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                for interrupt in task.interrupts:
                    if isinstance(interrupt, Interrupt):
                        self._interrupt_info = InterruptInfo(interrupt.value)
                        self._resume_trigger = self._interrupt_info.resume_trigger
                        return

    @property
    def status(self) -> UiPathRuntimeStatus:
        """Determines the execution status based on state."""
        return (
            UiPathRuntimeStatus.SUSPENDED
            if self._interrupt_info
            else UiPathRuntimeStatus.SUCCESSFUL
        )

    @property
    def interrupt_value(self) -> Union[Action, Any]:
        """Returns the actual value of the interrupt, with its specific type."""
        if self.interrupt_info is None:
            return None
        return self.interrupt_info.value

    @property
    def interrupt_info(self) -> Optional[InterruptInfo]:
        """Gets interrupt information if available."""
        return self._interrupt_info

    @property
    def resume_trigger(self) -> Optional[UiPathResumeTrigger]:
        """Gets resume trigger if interrupted."""
        return self._resume_trigger

    @cached_property
    def serialized_output(self) -> Dict[str, Any]:
        """Serializes the graph execution result."""
        try:
            if self.context.output is None:
                return {}
            if hasattr(self.context.output, "dict"):
                return self.context.output.dict()
            elif hasattr(self.context.output, "to_dict"):
                return self.context.output.to_dict()
            return dict(self.context.output)
        except Exception as e:
            raise LangGraphRuntimeError(
                "OUTPUT_SERIALIZATION_FAILED",
                "Failed to serialize graph output",
                f"Error serializing output data: {str(e)}",
                UiPathErrorCategory.SYSTEM,
            ) from e

    async def process(self) -> UiPathRuntimeResult:
        """
        Process the output and prepare the final execution result.

        Returns:
            UiPathRuntimeResult: The processed execution result.

        Raises:
            LangGraphRuntimeError: If processing fails.
        """
        try:
            await self._save_resume_trigger()

            return UiPathRuntimeResult(
                output=self.serialized_output,
                status=self.status,
                resume=self.resume_trigger if self.resume_trigger else None,
            )

        except LangGraphRuntimeError:
            raise
        except Exception as e:
            raise LangGraphRuntimeError(
                "OUTPUT_PROCESSING_FAILED",
                "Failed to process execution output",
                f"Unexpected error during output processing: {str(e)}",
                UiPathErrorCategory.SYSTEM,
            ) from e

    async def _save_resume_trigger(self) -> None:
        """
        Stores the resume trigger in the SQLite database if available.

        Raises:
            LangGraphRuntimeError: If database operations fail.
        """
        if not self.resume_trigger or not self.context.memory:
            return

        try:
            await self.context.memory.setup()
            async with (
                self.context.memory.lock,
                self.context.memory.conn.cursor() as cur,
            ):
                try:
                    await cur.execute(f"""
                        CREATE TABLE IF NOT EXISTS {self.context.resume_triggers_table} (
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            type TEXT NOT NULL,
                            key TEXT,
                            timestamp DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'utc'))
                        )
                    """)
                except Exception as e:
                    raise LangGraphRuntimeError(
                        "DB_TABLE_CREATION_FAILED",
                        "Failed to create resume triggers table",
                        f"Database error while creating table: {str(e)}",
                        UiPathErrorCategory.SYSTEM,
                    ) from e

                try:
                    default_escalation = Escalation()

                    if default_escalation.enabled:
                        action = await default_escalation.create(self.interrupt_value)
                        if action:
                            self._resume_trigger = UiPathResumeTrigger(
                                trigger_type=UiPathResumeTriggerType.ACTION,
                                item_key=action.key,
                            )

                except Exception as e:
                    raise LangGraphRuntimeError(
                        "ESCALATION_CREATION_FAILED",
                        "Failed to create escalation action",
                        f"Error while creating escalation action: {str(e)}",
                        UiPathErrorCategory.SYSTEM,
                    ) from e

                if (
                    self.resume_trigger.trigger_type.value
                    == UiPathResumeTriggerType.API.value
                    and self.resume_trigger.api_resume
                ):
                    trigger_key = self.resume_trigger.api_resume.inbox_id
                    trigger_type = self.resume_trigger.trigger_type.value
                else:
                    trigger_key = self.resume_trigger.item_key
                    trigger_type = self.resume_trigger.trigger_type.value

                try:
                    logger.debug(f"ResumeTrigger: {trigger_type} {trigger_key}")
                    await cur.execute(
                        f"INSERT INTO {self.context.resume_triggers_table} (type, key) VALUES (?, ?)",
                        (trigger_type, trigger_key),
                    )
                    await self.context.memory.conn.commit()
                except Exception as e:
                    raise LangGraphRuntimeError(
                        "DB_INSERT_FAILED",
                        "Failed to save resume trigger",
                        f"Database error while saving resume trigger: {str(e)}",
                        UiPathErrorCategory.SYSTEM,
                    ) from e
        except LangGraphRuntimeError:
            raise
        except Exception as e:
            raise LangGraphRuntimeError(
                "RESUME_TRIGGER_SAVE_FAILED",
                "Failed to save resume trigger",
                f"Unexpected error while saving resume trigger: {str(e)}",
                UiPathErrorCategory.SYSTEM,
            ) from e
