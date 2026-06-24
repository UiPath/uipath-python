"""Base adapter contracts for framework-specific integrations.

An adapter's job:

1. Detect whether it can handle a given agent object.
2. Attach hooks to that agent (framework-specific).
3. Publish events to a policy evaluator when those hooks fire.

The evaluator subscribes to events and runs policy checks; it never
knows or cares which adapter fired the event.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from uuid import uuid4

from .evaluator import EvaluatorProtocol


class BaseAdapter(ABC):
    """Base class for framework-specific governance adapters."""

    #: Higher value = more specific = inserted earlier in the registry.
    #: Plugin authors should set this above ``0`` on adapters that target
    #: a narrower agent type than another already-registered adapter, so
    #: the specific one wins ``can_handle`` resolution regardless of the
    #: order in which plugins happen to be imported. Among adapters with
    #: the same priority, registration order is preserved (stable).
    priority: int = 0

    #: Set to True on a catch-all adapter that should always sort last in
    #: the registry. The registry uses this flag (not the class name or
    #: :attr:`priority`) to keep the fallback in last position when new
    #: adapters register.
    is_fallback: bool = False

    @property
    def name(self) -> str:
        """Return adapter name for logging."""
        return self.__class__.__name__

    @abstractmethod
    def can_handle(self, agent: Any) -> bool:
        """Return True if this adapter knows how to hook into this agent type."""

    @abstractmethod
    def attach(
        self,
        agent: Any,
        agent_id: str,
        session_id: str,
        evaluator: EvaluatorProtocol,
    ) -> Any:
        """Attach governance hooks to the agent.

        Args:
            agent: The agent to govern.
            agent_id: Unique identifier for the agent.
            session_id: Session identifier for tracing.
            evaluator: Policy evaluator implementing
                :class:`EvaluatorProtocol`.

        Returns:
            A governed proxy (or the original agent with hooks installed).
        """

    def detach(self, governed: Any) -> Any:
        """Detach governance and return the original agent.

        Default implementation uses the public :attr:`GovernedAgentBase.unwrapped`
        contract; non-proxy adapters that return the original agent from
        :meth:`attach` get back ``governed`` unchanged.
        """
        return getattr(governed, "unwrapped", governed)

    def _generate_trace_id(self) -> str:
        """Generate a trace ID for governance events."""
        return str(uuid4())


class GovernedAgentBase:
    """Base class for governed agent proxies.

    Provides common functionality for all governed agents:

    - Stores reference to original agent
    - Forwards unknown attributes to original agent
    - Tracks governance metadata
    """

    def __init__(
        self,
        agent: Any,
        adapter: BaseAdapter,
        agent_id: str,
        session_id: str,
        evaluator: EvaluatorProtocol,
    ) -> None:
        """Initialize with the wrapped agent and governance metadata."""
        self._agent = agent
        self._adapter = adapter
        self._agent_id = agent_id
        self._session_id = session_id
        self._evaluator = evaluator
        self._trace_id = adapter._generate_trace_id()

    @property
    def unwrapped(self) -> Any:
        """Get the original unwrapped agent."""
        return self._agent

    def __getattr__(self, name: str) -> Any:
        """Forward attribute access to the original agent."""
        return getattr(self._agent, name)
