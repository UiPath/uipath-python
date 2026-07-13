"""Tests replace runtime-governance types via ``monkeypatch.setattr`` on
the bootstrap module's namespace (not via ``sys.modules``) — the
bootstrap imports them at top level.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from uipath._cli._governance_bootstrap import (
    GovernanceBootstrap,
    resolve_governance,
)
from uipath.core.governance import EnforcementMode, PolicyContext
from uipath.runtime.governance.native.models import PolicyIndex
from uipath.runtime.governance.runtime import UiPathGovernedRuntime


@pytest.fixture
def cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Change into an isolated cwd for each test.

    Kept even though ``resolve_governance`` no longer touches project
    files — several tests still want an isolated working directory so
    incidental file access (SDK config discovery, logging) doesn't leak
    across cases.
    """
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _install_fake_runtime_governance(
    monkeypatch: pytest.MonkeyPatch,
    *,
    audit_manager_cls: type,
    metadata_cls: type,
    evaluator_cls: type,
    compensator_cls: type,
) -> None:
    """Replace the runtime-governance names bound in the bootstrap module."""
    monkeypatch.setattr(
        "uipath._cli._governance_bootstrap.AuditManager",
        audit_manager_cls,
    )
    monkeypatch.setattr(
        "uipath._cli._governance_bootstrap.GovernanceRuntimeMetadata",
        metadata_cls,
    )
    monkeypatch.setattr(
        "uipath._cli._governance_bootstrap.GovernanceEvaluator",
        evaluator_cls,
    )
    monkeypatch.setattr(
        "uipath._cli._governance_bootstrap.GuardrailCompensator",
        compensator_cls,
    )


class _FakeAuditManager:
    """Records the constructor kwargs so tests can inspect them."""

    def __init__(self, *, track_event: Any, runtime_metadata: Any) -> None:
        self.track_event = track_event
        self.runtime_metadata = runtime_metadata


class _FakeMetadata:
    def __init__(self, *, agent_type: str | None, agent_framework: str) -> None:
        self.agent_type = agent_type
        self.agent_framework = agent_framework


class _FakeCompensator:
    def __init__(self, provider: Any) -> None:
        self.provider = provider


class _FakeEvaluator:
    def __init__(
        self,
        policy_index: Any,
        *,
        enforcement_mode: Any,
        audit_manager: Any,
        compensator: Any,
    ) -> None:
        self.policy_index = policy_index
        self.enforcement_mode = enforcement_mode
        self.audit_manager = audit_manager
        self.compensator = compensator


def _fake_policy_response(*, mode: EnforcementMode | None, policies: str) -> MagicMock:
    resp = MagicMock()
    resp.mode = mode
    resp.policies = policies
    return resp


def _stub_provider(
    monkeypatch: pytest.MonkeyPatch, *, response_or_exc: Any
) -> MagicMock:
    """Replace the ``UiPath()`` + provider construction with a stub whose
    ``get_policy_async`` returns ``response_or_exc`` (or raises if it's
    an exception instance).
    """
    provider = MagicMock()
    if isinstance(response_or_exc, BaseException):
        provider.get_policy_async = AsyncMock(side_effect=response_or_exc)
    else:
        provider.get_policy_async = AsyncMock(return_value=response_or_exc)
    provider.track_event_async = AsyncMock()

    monkeypatch.setattr(
        "uipath._cli._governance_bootstrap.UiPath",
        lambda: MagicMock(governance=MagicMock()),
    )
    monkeypatch.setattr(
        "uipath._cli._governance_bootstrap.UiPathPlatformGovernanceProvider",
        lambda service: provider,
    )
    return provider


class TestResolveGovernance:
    async def test_returns_none_when_feature_flag_disabled(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: False,
        )
        assert (
            await resolve_governance(
                agent_framework="langgraph",
                agent_type="uipath_coded",
                is_conversational=False,
            )
            is None
        )

    @pytest.mark.parametrize("is_conversational", [True, False])
    async def test_is_conversational_forwarded_verbatim_to_policy_context(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
        is_conversational: bool,
    ) -> None:
        """The caller derives ``is_conversational`` from
        ``bool(ctx.conversation_id)`` and passes it through. The
        bootstrap must forward the exact value to :class:`PolicyContext`
        so the backend can select the conversational or autonomous
        policy view."""
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        provider = _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.ENFORCE, policies="rules: []"
            ),
        )

        result = await resolve_governance(
            agent_framework="langgraph",
            agent_type="uipath_coded",
            is_conversational=is_conversational,
        )
        assert result is not None
        try:
            provider.get_policy_async.assert_awaited_once()
            context_arg = provider.get_policy_async.await_args.args[0]
            assert isinstance(context_arg, PolicyContext)
            assert context_arg.is_conversational is is_conversational
        finally:
            result.dispose()

    async def test_returns_none_when_policy_fetch_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(monkeypatch, response_or_exc=RuntimeError("backend unreachable"))
        assert (
            await resolve_governance(
                agent_framework="langgraph",
                agent_type="uipath_coded",
                is_conversational=False,
            )
            is None
        )

    async def test_returns_none_when_mode_is_disabled(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.DISABLED, policies="rules:"
            ),
        )
        assert (
            await resolve_governance(
                agent_framework="langgraph",
                agent_type="uipath_coded",
                is_conversational=False,
            )
            is None
        )

    async def test_returns_none_when_mode_is_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(mode=None, policies="rules:"),
        )
        assert (
            await resolve_governance(
                agent_framework="langgraph",
                agent_type="uipath_coded",
                is_conversational=False,
            )
            is None
        )

    async def test_returns_none_when_policies_empty(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.ENFORCE, policies=""
            ),
        )
        assert (
            await resolve_governance(
                agent_framework="langgraph",
                agent_type="uipath_coded",
                is_conversational=False,
            )
            is None
        )

    async def test_returns_none_when_policy_compilation_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """Malformed YAML must be caught by the compile-time try/except so
        governance skips cleanly rather than propagating a ``YAMLError``
        out of ``resolve_governance``.
        """
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                # Unclosed flow mapping — ``yaml.safe_load_all`` raises
                # ``ScannerError`` (a subclass of ``YAMLError``), which
                # ``resolve_governance``'s try/except converts to
                # ``None``.
                mode=EnforcementMode.ENFORCE,
                policies="foo: {unclosed",
            ),
        )
        assert (
            await resolve_governance(
                agent_framework="langgraph",
                agent_type="uipath_coded",
                is_conversational=False,
            )
            is None
        )

    async def test_success_returns_bootstrap_with_dispose_contract(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """Happy path -- named fields populated and dispose unregisters
        atexit + shuts the dispatcher down.
        """
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.ENFORCE, policies="rules: [a, b]"
            ),
        )

        # Capture what the code hands to atexit so we can verify
        # register/unregister without relying on atexit internals.
        registered: list[Any] = []

        def _fake_register(func: Any, *_a: Any, **_kw: Any) -> Any:
            registered.append(func)
            return func

        def _fake_unregister(func: Any) -> None:
            if func in registered:
                registered.remove(func)

        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.atexit.register", _fake_register
        )
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.atexit.unregister", _fake_unregister
        )

        result = await resolve_governance(
            agent_framework="langgraph",
            agent_type="uipath_coded",
            is_conversational=False,
        )
        assert result is not None

        assert isinstance(result.evaluator, _FakeEvaluator)
        assert isinstance(result.policy_index, PolicyIndex)
        assert result.policy_index.total_rules == 0
        assert result.enforcement_mode == EnforcementMode.ENFORCE
        assert isinstance(result.evaluator.audit_manager, _FakeAuditManager)
        assert isinstance(result.evaluator.compensator, _FakeCompensator)
        assert callable(result.evaluator.audit_manager.track_event)

        assert (
            result.evaluator.audit_manager.runtime_metadata.agent_type == "uipath_coded"
        )
        assert (
            result.evaluator.audit_manager.runtime_metadata.agent_framework
            == "langgraph"
        )

        assert len(registered) == 1
        result.dispose()
        assert not registered, "atexit hook was not unregistered on dispose"
        result.dispose()  # idempotent

    async def test_agent_type_forwarded_verbatim_to_metadata(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """The ``agent_type`` argument is forwarded verbatim to
        :class:`GovernanceRuntimeMetadata` -- the CLI does not classify
        the project; the factory does via
        :attr:`UiPathRuntimeFactorySettings.agent_type`.
        """
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.ENFORCE, policies="rules: [a, b]"
            ),
        )

        result = await resolve_governance(
            agent_framework="lowcode",
            agent_type="uipath_lowcode",
            is_conversational=False,
        )
        assert result is not None
        try:
            assert isinstance(result.evaluator, _FakeEvaluator)
            assert (
                result.evaluator.audit_manager.runtime_metadata.agent_type
                == "uipath_lowcode"
            )
            assert (
                result.evaluator.audit_manager.runtime_metadata.agent_framework
                == "lowcode"
            )
        finally:
            result.dispose()

    async def test_agent_framework_none_passes_through_as_unknown(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """A factory with no ``agent_framework`` opinion emits
        ``"unknown"`` -- symmetric with the ``agent_type`` fallback."""
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.ENFORCE, policies="rules: []"
            ),
        )

        result = await resolve_governance(
            agent_framework=None,
            agent_type="uipath_coded",
            is_conversational=False,
        )
        assert result is not None
        try:
            assert isinstance(result.evaluator, _FakeEvaluator)
            assert (
                result.evaluator.audit_manager.runtime_metadata.agent_framework
                == "unknown"
            )
        finally:
            result.dispose()

    async def test_agent_type_none_passes_through_to_metadata(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """A factory with no ``agent_type`` opinion yields ``None`` on
        the metadata -- the backend decides how to interpret the gap."""
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.ENFORCE, policies="rules: []"
            ),
        )

        result = await resolve_governance(
            agent_framework="langgraph",
            agent_type=None,
            is_conversational=False,
        )
        assert result is not None
        try:
            assert isinstance(result.evaluator, _FakeEvaluator)
            # Metadata field is strict ``str`` with default ``"unknown"``
            # -- the bootstrap forwards that when the factory has no
            # opinion, so the CLI never has to invent a value.
            assert (
                result.evaluator.audit_manager.runtime_metadata.agent_type == "unknown"
            )
        finally:
            result.dispose()

    async def test_wrap_runtime_produces_governed_runtime_with_bootstrap_fields(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """``GovernanceBootstrap.wrap_runtime`` must construct a
        :class:`UiPathGovernedRuntime` populated from the bootstrap's
        own ``evaluator`` / ``policy_index`` / ``enforcement_mode`` plus
        the caller's ``agent_name`` / ``runtime_id``. This is the code
        path CLI callers replaced their manual construction with.
        """
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.ENFORCE, policies="rules: []"
            ),
        )

        # The installed uipath-runtime may not yet accept rego_evaluator —
        # patch in a forward-compatible subclass so this test isn't gated on
        # the dependency version.
        class _UiPathGovernedRuntimeWithRego(UiPathGovernedRuntime):
            def __init__(self, delegate: Any, *, rego_evaluator: Any = None, **kwargs: Any) -> None:
                super().__init__(delegate, **kwargs)
                self._rego_evaluator = rego_evaluator

        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.UiPathGovernedRuntime",
            _UiPathGovernedRuntimeWithRego,
        )

        result = await resolve_governance(
            agent_framework="langgraph",
            agent_type="uipath_coded",
            is_conversational=False,
        )
        assert isinstance(result, GovernanceBootstrap)
        try:
            delegate = MagicMock()  # stand-in for the real runtime
            wrapped = result.wrap_runtime(
                delegate,
                agent_name="my-agent",
                runtime_id="run-123",
            )
            assert isinstance(wrapped, UiPathGovernedRuntime)
            assert wrapped._delegate is delegate
            assert wrapped._policy_index is result.policy_index
            assert wrapped._enforcement_mode is result.enforcement_mode
            assert wrapped._evaluator is result.evaluator
            assert wrapped._agent_name == "my-agent"
            assert wrapped._runtime_id == "run-123"
        finally:
            result.dispose()

    async def test_returns_none_when_dispatcher_init_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """A dispatcher constructor blow-up must be swallowed — governance
        is optional and a failing bootstrap must not crash the CLI. No
        ``atexit`` hook should leak.
        """
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.ENFORCE, policies="rules: []"
            ),
        )

        def _boom(_provider: Any) -> Any:
            raise RuntimeError("dispatcher init exploded")

        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.LiveTrackEventDispatcher",
            _boom,
        )

        registered: list[Any] = []

        def _fake_register(func: Any, *_a: Any, **_kw: Any) -> Any:
            registered.append(func)
            return func

        def _fake_unregister(func: Any) -> None:
            if func in registered:
                registered.remove(func)

        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.atexit.register", _fake_register
        )
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.atexit.unregister", _fake_unregister
        )

        result = await resolve_governance(
            agent_framework="langgraph",
            agent_type="uipath_coded",
            is_conversational=False,
        )
        assert result is None
        assert not registered, "atexit hook leaked when dispatcher init failed"

    async def test_returns_none_and_cleans_up_when_evaluator_setup_fails(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """If a component built AFTER the dispatcher (e.g., the evaluator)
        raises, ``resolve_governance`` must unregister the ``atexit`` hook
        AND shut the dispatcher down before returning ``None``.
        """
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )

        class _ExplodingEvaluator:
            def __init__(self, *_a: Any, **_kw: Any) -> None:
                raise RuntimeError("evaluator init exploded")

        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_ExplodingEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.ENFORCE, policies="rules: []"
            ),
        )

        shutdown_calls: list[int] = []

        class _FakeDispatcher:
            def __init__(self, _provider: Any) -> None:
                self.dispatch = MagicMock()

            def shutdown(self) -> None:
                shutdown_calls.append(1)

        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.LiveTrackEventDispatcher",
            _FakeDispatcher,
        )

        registered: list[Any] = []

        def _fake_register(func: Any, *_a: Any, **_kw: Any) -> Any:
            registered.append(func)
            return func

        def _fake_unregister(func: Any) -> None:
            if func in registered:
                registered.remove(func)

        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.atexit.register", _fake_register
        )
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.atexit.unregister", _fake_unregister
        )

        result = await resolve_governance(
            agent_framework="langgraph",
            agent_type="uipath_coded",
            is_conversational=False,
        )
        assert result is None
        assert not registered, "atexit hook not unregistered after evaluator failure"
        assert shutdown_calls == [1], "dispatcher not shut down after evaluator failure"

    async def test_dispose_swallows_dispatcher_shutdown_errors(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """``dispose`` runs from CLI ``finally`` blocks — it must never
        raise, or it will mask the primary exception. A shutdown that
        blows up should be logged at debug and swallowed.
        """
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.ENFORCE, policies="rules: []"
            ),
        )

        class _ExplodingDispatcher:
            def __init__(self, _provider: Any) -> None:
                self.dispatch = MagicMock()

            def shutdown(self) -> None:
                raise RuntimeError("shutdown exploded")

        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.LiveTrackEventDispatcher",
            _ExplodingDispatcher,
        )
        # atexit stubs so the exploding shutdown is never left registered
        # against the real atexit — otherwise it would fire at pytest exit.
        registered: list[Any] = []

        def _fake_register(func: Any, *_a: Any, **_kw: Any) -> Any:
            registered.append(func)
            return func

        def _fake_unregister(func: Any) -> None:
            if func in registered:
                registered.remove(func)

        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.atexit.register", _fake_register
        )
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.atexit.unregister", _fake_unregister
        )

        result = await resolve_governance(
            agent_framework="langgraph",
            agent_type="uipath_coded",
            is_conversational=False,
        )
        assert result is not None
        # Must not raise even though the dispatcher's shutdown does.
        result.dispose()
        # And must remain idempotent-safe.
        result.dispose()

    async def test_dispose_atexit_hook_matches_dispatcher_shutdown(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """The atexit hook that ``dispose`` unregisters must be the same
        callable that ``atexit.register`` received — otherwise unregister
        is a silent no-op and the dispatcher lingers.
        """
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.ENFORCE, policies="rules: []"
            ),
        )

        registered_arg: list[Any] = []
        unregistered_arg: list[Any] = []

        def _capture_register(func: Any) -> Any:
            registered_arg.append(func)
            return func

        def _capture_unregister(func: Any) -> None:
            unregistered_arg.append(func)

        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.atexit.register", _capture_register
        )
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.atexit.unregister",
            _capture_unregister,
        )

        result = await resolve_governance(
            agent_framework="langgraph",
            agent_type="uipath_coded",
            is_conversational=False,
        )
        assert result is not None

        result.dispose()

        assert len(registered_arg) == 1
        assert len(unregistered_arg) == 1
        # Same bound method → same underlying dispatcher shutdown.
        assert registered_arg[0] == unregistered_arg[0]

    # ------------------------------------------------------------------
    # Rego evaluator bootstrap path
    # ------------------------------------------------------------------

    def _setup_successful_governance(
        self,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Common setup for a successful governance bootstrap (no Rego)."""
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_governance_enabled",
            lambda: True,
        )
        _install_fake_runtime_governance(
            monkeypatch,
            audit_manager_cls=_FakeAuditManager,
            metadata_cls=_FakeMetadata,
            evaluator_cls=_FakeEvaluator,
            compensator_cls=_FakeCompensator,
        )
        _stub_provider(
            monkeypatch,
            response_or_exc=_fake_policy_response(
                mode=EnforcementMode.ENFORCE, policies="rules: []"
            ),
        )

    def _stub_rego_module(
        self,
        monkeypatch: pytest.MonkeyPatch,
        *,
        return_value: Any = None,
        side_effect: Any = None,
    ) -> None:
        """Inject a fake ``uipath.runtime.governance.rego`` into sys.modules
        so the lazy import inside ``resolve_governance`` succeeds.
        """
        import sys

        fake_rego = MagicMock()
        if side_effect is not None:
            fake_rego.build_rego_evaluator_async = AsyncMock(side_effect=side_effect)
        else:
            fake_rego.build_rego_evaluator_async = AsyncMock(return_value=return_value)
        monkeypatch.setitem(sys.modules, "uipath.runtime.governance.rego", fake_rego)

    async def test_rego_evaluator_populated_when_rego_enabled_and_build_succeeds(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """When ``is_rego_enabled()`` is ``True`` and
        ``build_rego_evaluator_async`` returns a non-None evaluator, the
        bootstrap's ``rego_evaluator`` field must be set to that object.
        """
        self._setup_successful_governance(monkeypatch)
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_rego_enabled",
            lambda: True,
        )
        mock_rego_evaluator = MagicMock()
        mock_rego_evaluator.loaded_hooks = []
        self._stub_rego_module(monkeypatch, return_value=mock_rego_evaluator)

        result = await resolve_governance(
            agent_framework="langgraph",
            agent_type="uipath_coded",
            is_conversational=False,
        )
        assert result is not None
        try:
            assert result.rego_evaluator is mock_rego_evaluator
        finally:
            result.dispose()

    async def test_rego_evaluator_none_when_rego_enabled_but_build_returns_none(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """When ``build_rego_evaluator_async`` returns ``None`` (e.g. no
        bundles available), ``rego_evaluator`` must stay ``None`` and
        governance still succeeds.
        """
        self._setup_successful_governance(monkeypatch)
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_rego_enabled",
            lambda: True,
        )
        self._stub_rego_module(monkeypatch, return_value=None)

        result = await resolve_governance(
            agent_framework="langgraph",
            agent_type="uipath_coded",
            is_conversational=False,
        )
        assert result is not None
        try:
            assert result.rego_evaluator is None
        finally:
            result.dispose()

    async def test_rego_evaluator_none_when_build_raises(
        self,
        monkeypatch: pytest.MonkeyPatch,
        cwd: Path,
    ) -> None:
        """Exceptions in ``build_rego_evaluator_async`` must be swallowed —
        a Rego failure must not crash the bootstrap.  ``rego_evaluator``
        stays ``None`` and governance returns a valid (non-Rego) bootstrap.
        """
        self._setup_successful_governance(monkeypatch)
        monkeypatch.setattr(
            "uipath._cli._governance_bootstrap.is_rego_enabled",
            lambda: True,
        )
        self._stub_rego_module(
            monkeypatch, side_effect=RuntimeError("Rego bundle unavailable")
        )

        result = await resolve_governance(
            agent_framework="langgraph",
            agent_type="uipath_coded",
            is_conversational=False,
        )
        assert result is not None
        try:
            assert result.rego_evaluator is None
        finally:
            result.dispose()
