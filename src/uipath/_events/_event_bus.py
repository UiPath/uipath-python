"""Event bus implementation for evaluation events."""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class EventBus:
    """Event bus for publishing and subscribing to events."""

    def __init__(self) -> None:
        """Initialize a new EventBus instance."""
        self._subscribers: Dict[str, List[Callable[[Any], Any]]] = {}
        self._running_tasks: Set[asyncio.Task[Any]] = set()

    def subscribe(self, topic: str, handler: Callable[[Any], Any]) -> None:
        """Subscribe a handler method/function to a topic.

        Args:
            topic: The topic name to subscribe to.
            handler: The async handler method/function that will handle events for this topic.
        """
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        self._subscribers[topic].append(handler)
        logger.debug(f"Handler registered for topic: {topic}")

    def unsubscribe(self, topic: str, handler: Callable[[Any], Any]) -> None:
        """Unsubscribe a handler from a topic.

        Args:
            topic: The topic name to unsubscribe from.
            handler: The handler to remove.
        """
        if topic in self._subscribers:
            try:
                self._subscribers[topic].remove(handler)
                if not self._subscribers[topic]:
                    del self._subscribers[topic]
                logger.debug(f"Handler unregistered from topic: {topic}")
            except ValueError:
                logger.warning(f"Handler not found for topic: {topic}")

    def _cleanup_completed_tasks(self) -> None:
        completed_tasks = {task for task in self._running_tasks if task.done()}
        self._running_tasks -= completed_tasks

    async def publish(
        self, topic: str, payload: T, wait_for_completion: bool = True
    ) -> None:
        """Publish an event to all handlers of a topic.

        Args:
            topic: The topic name to publish to.
            payload: The event payload to publish.
            wait_for_completion: Whether to wait for the event to be processed.
        """
        if topic not in self._subscribers:
            logger.debug(f"No handlers for topic: {topic}")
            return

        self._cleanup_completed_tasks()

        tasks = []
        for subscriber in self._subscribers[topic]:
            try:
                task = asyncio.create_task(subscriber(payload))
                tasks.append(task)
                self._running_tasks.add(task)
            except Exception as e:
                logger.error(f"Error creating task for subscriber {subscriber}: {e}")

        if tasks and wait_for_completion:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            except Exception as e:
                logger.error(f"Error during event processing for topic {topic}: {e}")
            finally:
                # Clean up the tasks we just waited for
                for task in tasks:
                    self._running_tasks.discard(task)

    def get_running_tasks_count(self) -> int:
        """Get the number of currently running subscriber tasks.

        Returns:
            Number of running tasks.
        """
        self._cleanup_completed_tasks()
        return len(self._running_tasks)

    async def wait_for_all(self, timeout: Optional[float] = None) -> None:
        """Wait for all currently running subscriber tasks to complete.

        Args:
            timeout: Maximum time to wait in seconds. If None, waits indefinitely.
        """
        self._cleanup_completed_tasks()

        if not self._running_tasks:
            logger.debug("No running tasks to wait for")
            return

        logger.debug(
            f"Waiting for {len(self._running_tasks)} EventBus tasks to complete..."
        )

        try:
            tasks_to_wait = list(self._running_tasks)

            if timeout:
                await asyncio.wait_for(
                    asyncio.gather(*tasks_to_wait, return_exceptions=True),
                    timeout=timeout,
                )
            else:
                await asyncio.gather(*tasks_to_wait, return_exceptions=True)

            logger.debug("All EventBus tasks completed")

        except asyncio.TimeoutError:
            logger.warning(f"Timeout waiting for EventBus tasks after {timeout}s")
            for task in tasks_to_wait:
                if not task.done():
                    task.cancel()
        except Exception as e:
            logger.error(f"Error waiting for EventBus tasks: {e}")
        finally:
            self._cleanup_completed_tasks()

    def get_subscribers_count(self, topic: str) -> int:
        """Get the number of subscribers for a topic.

        Args:
            topic: The topic name.

        Returns:
            Number of handlers for the topic.
        """
        return len(self._subscribers.get(topic, []))

    def clear_subscribers(self, topic: Optional[str] = None) -> None:
        """Clear subscribers for a topic or all topics.

        Args:
            topic: The topic to clear. If None, clears all topics.
        """
        if topic is None:
            self._subscribers.clear()
            logger.debug("All handlers cleared")
        elif topic in self._subscribers:
            del self._subscribers[topic]
            logger.debug(f"Handlers cleared for topic: {topic}")
