"""Best-effort discovery of UiPath resource bindings from project source code."""

from ._apply import (
    InferOutcome,
    infer_bindings,
    infer_bindings_into_file,
    load_bindings,
    report_outcome,
    serialize_bindings,
)
from ._emitter import MergeReport, binding_key, build_binding, merge_bindings
from ._registry import BINDABLE_RESOURCE_TYPES, BindingSpec, build_registry
from ._scanner import (
    ResourceReference,
    ScanResult,
    SkippedReference,
    scan_project,
    scan_source,
)

__all__ = [
    "BINDABLE_RESOURCE_TYPES",
    "InferOutcome",
    "BindingSpec",
    "MergeReport",
    "ResourceReference",
    "ScanResult",
    "SkippedReference",
    "binding_key",
    "build_binding",
    "build_registry",
    "infer_bindings",
    "infer_bindings_into_file",
    "load_bindings",
    "merge_bindings",
    "report_outcome",
    "serialize_bindings",
    "scan_project",
    "scan_source",
]
