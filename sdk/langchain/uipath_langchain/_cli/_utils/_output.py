import json
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Optional

from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Interrupt, StateSnapshot
from uipath_sdk._models.actions import Action  # type: ignore

from ._trigger import ResumeTriggerType


@dataclass
class ApiResumeTrigger:
    """API resume trigger request."""

    inboxId: Optional[str] = None
    request: Any = None


@dataclass
class ResumeTrigger:
    """Resume trigger structure"""

    triggerType: str = ResumeTriggerType.API
    itemKey: Optional[str] = None
    apiResume: Optional[ApiResumeTrigger] = None


@dataclass
class InterruptInfo:
    """Contains all information about an interrupt."""

    value: Any
    _inbox_id: str = field(
        default_factory=lambda: str(uuid.uuid4()), init=False, repr=False
    )
    _resume_trigger: Optional[ResumeTrigger] = field(
        default=None, init=False, repr=False
    )

    @property
    def type(self) -> Optional[str]:
        """Returns the type of the interrupt value."""
        if isinstance(self.value, Action):
            return ResumeTriggerType.ACTION
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

    @property
    def resume_trigger(self) -> ResumeTrigger:
        """Creates the resume trigger based on interrupt type."""
        if self._resume_trigger is None:
            if self.type is None:
                self._resume_trigger = ResumeTrigger(
                    apiResume=ApiResumeTrigger(
                        inboxId=self._inbox_id, request=self.serialize()
                    )
                )
            else:
                self._resume_trigger = ResumeTrigger(
                    itemKey=self.identifier, triggerType=self.type
                )
        return self._resume_trigger


@dataclass
class GraphOutput:
    """
    Contains and manages the complete output information from graph execution.
    Handles serialization, interrupt data, and file output.
    """

    result: Any
    state: Optional[StateSnapshot]
    checkpointer: Optional[AsyncSqliteSaver] = None

    @property
    def status(self) -> str:
        """Determines the execution status based on state."""
        return "suspended" if self.interrupt_info else "completed"

    @property
    def interrupt_info(self) -> Optional[InterruptInfo]:
        """Gets interrupt information if available."""
        if not self.state or not hasattr(self.state, "next") or not self.state.next:
            return None

        for task in self.state.tasks:
            if hasattr(task, "interrupts") and task.interrupts:
                for interrupt in task.interrupts:
                    if isinstance(interrupt, Interrupt):
                        return InterruptInfo(interrupt.value)
        return None

    @property
    def resume_trigger(self) -> Optional[ResumeTrigger]:
        """Gets resume trigger if interrupted."""
        if self.interrupt_info:
            return self.interrupt_info.resume_trigger
        return None

    @property
    def serialized_result(self) -> Dict[str, Any]:
        """Serializes the graph execution result."""
        if hasattr(self.result, "dict"):
            return self.result.dict()
        elif hasattr(self.result, "to_dict"):
            return self.result.to_dict()
        return dict(self.result)

    async def store_resume_trigger(self) -> None:
        """Stores the resume trigger in the SQLite database if available."""
        if not self.resume_trigger or not self.checkpointer:
            return

        await self.checkpointer.setup()
        async with self.checkpointer.lock, self.checkpointer.conn.cursor() as cur:
            await cur.execute("""
                CREATE TABLE IF NOT EXISTS __uipath_resume_triggers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    key TEXT,
                    timestamp DATETIME DEFAULT (strftime('%Y-%m-%d %H:%M:%S', 'now', 'utc'))
                )
            """)

            key = None
            if (
                self.resume_trigger.triggerType == ResumeTriggerType.API
                and self.resume_trigger.apiResume
            ):
                key = self.resume_trigger.apiResume.inboxId
            else:
                key = self.resume_trigger.itemKey

            print(f"[ResumeTrigger]: Store DB {self.resume_trigger.triggerType} {key}")
            await cur.execute(
                "INSERT INTO __uipath_resume_triggers (type, key) VALUES (?, ?)",
                (self.resume_trigger.triggerType, key),
            )
            await self.checkpointer.conn.commit()

    def to_dict(self) -> Dict[str, Any]:
        """Converts the complete output to a dictionary."""
        return {
            "output": self.serialized_result,
            "status": self.status,
            "resume": asdict(self.resume_trigger) if self.resume_trigger else None,
        }

    def write_to_file(self, filename: str = "__uipath_output.json") -> None:
        """Writes the complete output to a JSON file."""
        content = self.to_dict()
        print(json.dumps(content))
        with open(filename, "w") as f:
            json.dump(content, f, indent=2, default=str)

    def print_output(self) -> None:
        """Prints the output in the expected format."""
        print(f"[OutputStart]{json.dumps(self.serialized_result)}[OutputEnd]")

        if self.interrupt_info:
            print(f"[SuspendStart]{self.interrupt_info.serialize()}[SuspendEnd]")
