"""Derives the scannable SDK surface from the ``@resource_override`` decorators.

The decorators on the platform services already declare, per method, which
resource type is touched and which parameters carry the resource name and its
folder. Reading them back is what keeps the scanner in step with the SDK: a
hand-maintained list would silently go stale as services grow.
"""

import inspect
import typing
from dataclasses import dataclass
from functools import lru_cache
from typing import Any, Optional

BINDABLE_RESOURCE_TYPES = frozenset(
    {"asset", "process", "bucket", "index", "app", "connection"}
)


@dataclass(frozen=True)
class BindingSpec:
    """One scannable SDK call, e.g. ``sdk.assets.retrieve_async(...)``."""

    service_attr: str
    method: str
    resource_type: str
    name_param: str
    folder_param: Optional[str]
    name_index: Optional[int]
    folder_index: Optional[int]
    activity_name: str


def _binding_metadata(func: Any) -> Optional[dict[str, str]]:
    target = getattr(func, "__func__", func)
    metadata = getattr(target, "__uipath_binding__", None)
    if isinstance(metadata, dict):
        return metadata
    return _metadata_from_closure(target)


def _metadata_from_closure(target: Any) -> Optional[dict[str, str]]:
    """Recover the decorator arguments from an SDK that predates the attribute."""
    closure = getattr(target, "__closure__", None)
    code = getattr(target, "__code__", None)
    if not closure or code is None:
        return None
    cells = dict(zip(code.co_freevars, closure, strict=True))
    process_args = cells.get("process_args")
    if process_args is None:
        return None
    inner = process_args.cell_contents
    inner_closure = getattr(inner, "__closure__", None)
    inner_code = getattr(inner, "__code__", None)
    if not inner_closure or inner_code is None:
        return None
    inner_cells = dict(zip(inner_code.co_freevars, inner_closure, strict=True))
    if not {"resource_type", "resource_identifier", "folder_identifier"} <= set(
        inner_cells
    ):
        return None
    return {
        key: inner_cells[key].cell_contents
        for key in ("resource_type", "resource_identifier", "folder_identifier")
    }


def _iter_service_classes() -> typing.Iterator[tuple[str, type]]:
    from uipath.platform import UiPath

    for attr, descriptor in vars(UiPath).items():
        if attr.startswith("_"):
            continue
        accessor = getattr(descriptor, "fget", None) or getattr(
            descriptor, "func", None
        )
        if accessor is None:
            continue
        try:
            hints = typing.get_type_hints(accessor)
        except Exception:
            continue
        service_cls = hints.get("return")
        if isinstance(service_cls, type):
            yield attr, service_cls


def _positional_index(signature: inspect.Signature, param_name: str) -> Optional[int]:
    index = 0
    for name, parameter in signature.parameters.items():
        if name == "self":
            continue
        if parameter.kind not in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        ):
            return None
        if name == param_name:
            return index
        index += 1
    return None


def _resolve_activity_name(service_cls: type, method: str) -> str:
    if method.endswith("_async"):
        return method
    if hasattr(service_cls, f"{method}_async"):
        return f"{method}_async"
    return method


def _build_spec(
    service_attr: str,
    service_cls: type,
    method: str,
    func: Any,
    metadata: dict[str, str],
) -> Optional[BindingSpec]:
    try:
        signature = inspect.signature(func)
    except (TypeError, ValueError):
        return None

    name_param = metadata["resource_identifier"]
    if name_param not in signature.parameters:
        return None

    folder_param: Optional[str] = metadata["folder_identifier"]
    if folder_param not in signature.parameters:
        folder_param = None

    return BindingSpec(
        service_attr=service_attr,
        method=method,
        resource_type=metadata["resource_type"],
        name_param=name_param,
        folder_param=folder_param,
        name_index=_positional_index(signature, name_param),
        folder_index=(
            _positional_index(signature, folder_param) if folder_param else None
        ),
        activity_name=_resolve_activity_name(service_cls, method),
    )


@lru_cache(maxsize=1)
def build_registry() -> dict[tuple[str, str], BindingSpec]:
    """Map ``(sdk attribute, method name)`` to its binding spec."""
    registry: dict[tuple[str, str], BindingSpec] = {}
    for service_attr, service_cls in _iter_service_classes():
        for method, func in vars(service_cls).items():
            metadata = _binding_metadata(func)
            if metadata is None:
                continue
            if metadata["resource_type"] not in BINDABLE_RESOURCE_TYPES:
                continue
            spec = _build_spec(service_attr, service_cls, method, func, metadata)
            if spec is not None:
                registry[(service_attr, method)] = spec
    return registry


def service_attributes(registry: dict[tuple[str, str], BindingSpec]) -> set[str]:
    """The SDK attribute names worth looking for in project source."""
    return {service_attr for service_attr, _ in registry}
