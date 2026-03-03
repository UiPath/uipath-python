"""Tests for LLM request throttling functionality."""

import asyncio
from unittest.mock import MagicMock, patch

import pytest

from uipath.platform import UiPathApiConfig, UiPathExecutionContext
from uipath.platform.chat import UiPathLlmChatService, UiPathOpenAIService
from uipath.platform.chat.llm_throttle import (
    DEFAULT_LLM_CONCURRENCY,
    get_llm_semaphore,
    set_llm_concurrency,
)


class TestLLMThrottling:
    """Tests for LLM throttling mechanism."""

    @pytest.fixture(autouse=True)
    def reset_semaphore(self):
        """Reset the global semaphore and limit before each test."""
        import uipath.platform.chat.llm_throttle as module

        module._llm_semaphore = None
        module._llm_semaphore_loop = None
        module._llm_concurrency_limit = module.DEFAULT_LLM_CONCURRENCY
        yield
        module._llm_semaphore = None
        module._llm_semaphore_loop = None
        module._llm_concurrency_limit = module.DEFAULT_LLM_CONCURRENCY

    @pytest.fixture
    def config(self):
        """Create a test config."""
        return UiPathApiConfig(base_url="https://example.com", secret="test_secret")

    @pytest.fixture
    def execution_context(self):
        """Create a test execution context."""
        return UiPathExecutionContext()

    @pytest.fixture
    def openai_service(self, config, execution_context):
        """Create an OpenAI service instance."""
        return UiPathOpenAIService(config=config, execution_context=execution_context)

    @pytest.fixture
    def llm_service(self, config, execution_context):
        """Create an LLM chat service instance."""
        return UiPathLlmChatService(config=config, execution_context=execution_context)

    def test_default_concurrency_constant(self):
        """Test that DEFAULT_LLM_CONCURRENCY is set correctly."""
        assert DEFAULT_LLM_CONCURRENCY == 20

    @pytest.mark.asyncio
    async def testget_llm_semaphore_creates_semaphore(self):
        """Test that get_llm_semaphore creates a semaphore with default limit."""
        semaphore = get_llm_semaphore()
        assert isinstance(semaphore, asyncio.Semaphore)
        # Semaphore should allow DEFAULT_LLM_CONCURRENCY concurrent acquisitions
        assert semaphore._value == DEFAULT_LLM_CONCURRENCY

    @pytest.mark.asyncio
    async def testget_llm_semaphore_returns_same_instance(self):
        """Test that get_llm_semaphore returns the same semaphore instance."""
        semaphore1 = get_llm_semaphore()
        semaphore2 = get_llm_semaphore()
        assert semaphore1 is semaphore2

    @pytest.mark.asyncio
    async def test_set_llm_concurrency_changes_limit(self):
        """Test that set_llm_concurrency sets a custom limit."""
        set_llm_concurrency(5)
        semaphore = get_llm_semaphore()
        assert semaphore._value == 5

    @pytest.mark.asyncio
    async def test_throttle_limits_concurrency(self):
        """Test that throttling actually limits concurrent operations."""
        set_llm_concurrency(2)

        concurrent_count = 0
        max_concurrent = 0

        async def task():
            nonlocal concurrent_count, max_concurrent
            async with get_llm_semaphore():
                concurrent_count += 1
                max_concurrent = max(max_concurrent, concurrent_count)
                await asyncio.sleep(0.05)
                concurrent_count -= 1

        # Run 10 tasks with concurrency limit of 2
        await asyncio.gather(*[task() for _ in range(10)])

        assert max_concurrent == 2

    @patch.object(UiPathOpenAIService, "request_async")
    @pytest.mark.asyncio
    async def test_openai_service_uses_throttle(self, mock_request, openai_service):
        """Test that OpenAI service chat_completions uses throttling."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "test",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_request.return_value = mock_response

        set_llm_concurrency(1)
        semaphore = get_llm_semaphore()

        # Verify semaphore is used during the call
        initial_value = semaphore._value

        await openai_service.chat_completions(
            messages=[{"role": "user", "content": "Hi"}]
        )

        # After the call, semaphore should be back to initial value
        assert semaphore._value == initial_value

    @patch.object(UiPathLlmChatService, "request_async")
    @pytest.mark.asyncio
    async def test_llm_service_uses_throttle(self, mock_request, llm_service):
        """Test that LLM chat service chat_completions uses throttling."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "id": "test",
            "object": "chat.completion",
            "created": 1234567890,
            "model": "gpt-4o-mini",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "Hello"},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
        mock_request.return_value = mock_response

        set_llm_concurrency(1)
        semaphore = get_llm_semaphore()

        initial_value = semaphore._value

        await llm_service.chat_completions(messages=[{"role": "user", "content": "Hi"}])

        assert semaphore._value == initial_value

    @patch.object(UiPathOpenAIService, "request_async")
    @pytest.mark.asyncio
    async def test_embeddings_uses_throttle(self, mock_request, openai_service):
        """Test that embeddings endpoint uses throttling."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "data": [{"embedding": [0.1, 0.2, 0.3], "index": 0, "object": "embedding"}],
            "model": "text-embedding-ada-002",
            "object": "list",
            "usage": {"prompt_tokens": 4, "total_tokens": 4},
        }
        mock_request.return_value = mock_response

        set_llm_concurrency(1)
        semaphore = get_llm_semaphore()

        initial_value = semaphore._value

        await openai_service.embeddings(input="Test input")

        assert semaphore._value == initial_value


class TestEventLoopBug:
    """Tests for the event loop binding bug.

    The bug: If set_llm_concurrency() creates the semaphore before asyncio.run(),
    the semaphore is bound to the wrong event loop and will fail with:
    RuntimeError: Semaphore object is bound to a different event loop

    The fix: set_llm_concurrency() only stores the limit, doesn't create semaphore.
    """

    @pytest.fixture(autouse=True)
    def reset_semaphore(self):
        """Reset the global semaphore and limit before each test."""
        import uipath.platform.chat.llm_throttle as module

        module._llm_semaphore = None
        module._llm_semaphore_loop = None
        module._llm_concurrency_limit = module.DEFAULT_LLM_CONCURRENCY
        yield
        module._llm_semaphore = None
        module._llm_semaphore_loop = None
        module._llm_concurrency_limit = module.DEFAULT_LLM_CONCURRENCY

    def test_set_llm_concurrency_before_asyncio_run(self):
        """Test that set_llm_concurrency called before asyncio.run causes issues.

        This test reproduces the bug where the semaphore is created in one
        event loop context but used in another (created by asyncio.run).
        """
        # This simulates what happens in cli_eval.py:
        # 1. set_llm_concurrency() is called (creates semaphore)
        # 2. asyncio.run() starts a NEW event loop
        # 3. Code tries to use the semaphore in the new loop

        # Step 1: Call set_llm_concurrency outside any event loop
        # (simulating CLI code before asyncio.run)
        set_llm_concurrency(5)

        # Step 2 & 3: Run async code in a new event loop
        async def use_semaphore():
            semaphore = get_llm_semaphore()
            async with semaphore:
                pass

        # This should raise RuntimeError if the bug exists
        # because the semaphore was created in a different loop context
        try:
            asyncio.run(use_semaphore())
            # If we get here, either:
            # a) The bug is fixed (semaphore created lazily in correct loop)
            # b) Python version handles this gracefully
            bug_exists = False
        except RuntimeError as e:
            if "different event loop" in str(
                e
            ) or "attached to a different loop" in str(e):
                bug_exists = True
            else:
                raise

        # This assertion documents expected behavior:
        # - If bug_exists is True, the fix is needed
        # - If bug_exists is False, the fix has been applied or Python handles it
        # Currently we expect the bug to exist (test should fail after fix is applied)
        assert not bug_exists, (
            "Event loop bug detected! The semaphore was created outside the running "
            "event loop. Fix: set_llm_concurrency should only store the limit, not "
            "create the semaphore."
        )

    def test_lazy_semaphore_creation_in_correct_loop(self):
        """Test that semaphore created inside asyncio.run works correctly.

        This is the expected behavior after the fix is applied.
        """
        import uipath.platform.chat.llm_throttle as module

        # Ensure semaphore is None (not pre-created)
        module._llm_semaphore = None

        async def use_semaphore():
            # Semaphore should be created here, inside the running loop
            semaphore = get_llm_semaphore()
            async with semaphore:
                return True

        # This should work because semaphore is created in the correct loop
        result = asyncio.run(use_semaphore())
        assert result is True

    def test_set_llm_concurrency_does_not_create_semaphore(self):
        """Test that set_llm_concurrency only stores limit, doesn't create semaphore.

        This is the key fix - the semaphore should be created lazily inside
        the running event loop, not when set_llm_concurrency is called.
        """
        import uipath.platform.chat.llm_throttle as module

        # Ensure semaphore is None initially
        module._llm_semaphore = None

        # Call set_llm_concurrency
        set_llm_concurrency(5)

        # Verify semaphore is still None (not created yet)
        assert module._llm_semaphore is None

        # Verify limit was stored
        assert module._llm_concurrency_limit == 5

        # Now when we get the semaphore, it should be created with the stored limit
        async def get_sem():
            return get_llm_semaphore()

        semaphore = asyncio.run(get_sem())
        assert semaphore._value == 5


class TestMultipleEventLoops:
    """Tests for semaphore behavior across multiple event loops.

    This tests the scenario where:
    1. First asyncio.run() creates semaphore bound to loop A
    2. Loop A closes
    3. Second asyncio.run() creates loop B
    4. Code tries to use semaphore still bound to dead loop A
    5. Should NOT crash - semaphore should be recreated for loop B
    """

    @pytest.fixture(autouse=True)
    def reset_semaphore(self):
        """Reset the global semaphore before each test."""
        import uipath.platform.chat.llm_throttle as module

        module._llm_semaphore = None
        module._llm_semaphore_loop = None
        module._llm_concurrency_limit = module.DEFAULT_LLM_CONCURRENCY
        yield
        module._llm_semaphore = None
        module._llm_semaphore_loop = None
        module._llm_concurrency_limit = module.DEFAULT_LLM_CONCURRENCY

    def test_semaphore_works_across_multiple_asyncio_runs(self):
        """Test that semaphore works correctly across multiple asyncio.run() calls.

        This is the key test for the event-loop binding bug. Without the fix,
        this test will fail with:
        RuntimeError: Semaphore object is bound to a different event loop

        NOTE: The bug only triggers when there's CONTENTION on the semaphore
        (multiple tasks competing). Without contention, _get_loop() is not
        called and the semaphore doesn't bind to the event loop.
        """
        # Use a limit of 1 to force contention
        set_llm_concurrency(1)

        async def use_semaphore_with_contention():
            """Use the semaphore with contention to trigger loop binding."""
            semaphore = get_llm_semaphore()

            async def contender():
                async with semaphore:
                    await asyncio.sleep(0.001)

            # Hold the semaphore while another task tries to acquire it
            async with semaphore:
                # Create a contending task - this forces _get_loop() to be called
                task = asyncio.create_task(contender())
                await asyncio.sleep(0.001)

            await task
            return True

        # First run - creates semaphore and binds to loop A due to contention
        result1 = asyncio.run(use_semaphore_with_contention())
        assert result1 is True

        # Second run - loop A is closed, loop B is created
        # Without fix: crashes because semaphore is still bound to loop A
        # With fix: should work because semaphore is recreated for loop B
        result2 = asyncio.run(use_semaphore_with_contention())
        assert result2 is True

        # Third run - just to be sure
        result3 = asyncio.run(use_semaphore_with_contention())
        assert result3 is True

    def test_semaphore_limit_preserved_across_loops(self):
        """Test that concurrency limit is preserved when semaphore is recreated."""
        set_llm_concurrency(3)

        async def get_semaphore_value():
            semaphore = get_llm_semaphore()
            return semaphore._value

        # First run
        value1 = asyncio.run(get_semaphore_value())
        assert value1 == 3

        # Second run - should still have limit of 3
        value2 = asyncio.run(get_semaphore_value())
        assert value2 == 3


class TestConcurrencyValidation:
    """Tests for input validation of concurrency settings."""

    @pytest.fixture(autouse=True)
    def reset_semaphore(self):
        """Reset the global semaphore before each test."""
        import uipath.platform.chat.llm_throttle as module

        module._llm_semaphore = None
        module._llm_semaphore_loop = None
        module._llm_concurrency_limit = module.DEFAULT_LLM_CONCURRENCY
        yield
        module._llm_semaphore = None
        module._llm_semaphore_loop = None
        module._llm_concurrency_limit = module.DEFAULT_LLM_CONCURRENCY

    def test_set_llm_concurrency_zero_raises_error(self):
        """Test that setting concurrency to 0 raises ValueError.

        A semaphore with value 0 would deadlock all requests.
        """
        with pytest.raises(ValueError, match="must be at least 1"):
            set_llm_concurrency(0)

    def test_set_llm_concurrency_negative_raises_error(self):
        """Test that setting negative concurrency raises ValueError."""
        with pytest.raises(ValueError, match="must be at least 1"):
            set_llm_concurrency(-1)

    def test_set_llm_concurrency_one_is_valid(self):
        """Test that setting concurrency to 1 (minimum valid) works."""
        set_llm_concurrency(1)

        async def check_semaphore():
            semaphore = get_llm_semaphore()
            return semaphore._value

        value = asyncio.run(check_semaphore())
        assert value == 1
