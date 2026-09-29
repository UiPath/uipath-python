"""Turns discovered resource references into ``bindings.json`` entries.

Merging never rewrites an entry that is already in the file. Existing bindings
carry things a static scan cannot reproduce — expressions, connector metadata,
display names edited by hand — so a known key is left exactly as it is.
"""

from dataclasses import dataclass, field
from typing import Optional

from ..models.runtime_schema import BindingResource, BindingResourceValue, Bindings
from ._scanner import ResourceReference

BINDINGS_VERSION = "2.0"
BINDINGS_METADATA_VERSION = "2.2"

_DISPLAY_NAMES = {
    "app": ("App Name", "App Folder Path"),
}
_DEFAULT_DISPLAY_NAMES = ("Name", "Folder Path")


@dataclass
class MergeReport:
    added: list[str] = field(default_factory=list)
    unchanged: list[str] = field(default_factory=list)
    preserved: list[str] = field(default_factory=list)


def binding_key(reference: ResourceReference) -> str:
    """The ``key`` field, which the platform prefixes with the resource type."""
    if reference.resource_type == "connection" or not reference.folder_path:
        return reference.name
    return f"{reference.name}.{reference.folder_path}"


def _value(default_value: str, display_name: str) -> BindingResourceValue:
    """Generated values are always literal; see _scanner._record."""
    return BindingResourceValue(
        default_value=default_value,
        is_expression=False,
        display_name=display_name,
    )


def _connection_binding(reference: ResourceReference) -> BindingResource:
    return BindingResource(
        resource="connection",
        key=binding_key(reference),
        value={"ConnectionId": _value(reference.name, "Connection")},
        metadata={
            "BindingsVersion": BINDINGS_METADATA_VERSION,
            "Connector": "",
            "UseConnectionService": "True",
        },
    )


def build_binding(reference: ResourceReference) -> BindingResource:
    """Build a single binding entry for a discovered reference."""
    if reference.resource_type == "connection":
        return _connection_binding(reference)

    name_label, folder_label = _DISPLAY_NAMES.get(
        reference.resource_type, _DEFAULT_DISPLAY_NAMES
    )
    display_label = reference.name if reference.resource_type == "app" else "FullName"

    return BindingResource(
        resource=reference.resource_type,
        key=binding_key(reference),
        value={
            "name": _value(reference.name, name_label),
            "folderPath": _value(reference.folder_path or "", folder_label),
        },
        metadata={
            "ActivityName": reference.activity_name,
            "BindingsVersion": BINDINGS_METADATA_VERSION,
            "DisplayLabel": display_label,
        },
    )


def merge_bindings(
    existing: Optional[Bindings], references: list[ResourceReference]
) -> tuple[Bindings, MergeReport]:
    """Add newly discovered bindings without disturbing the ones already there."""
    resources = list(existing.resources) if existing else []
    known = {(entry.resource, entry.key) for entry in resources}
    report = MergeReport()
    discovered: set[tuple[str, str]] = set()

    ordered = sorted(references, key=lambda ref: (ref.resource_type, binding_key(ref)))
    for reference in ordered:
        identity = (reference.resource_type, binding_key(reference))
        if identity in discovered:
            continue
        discovered.add(identity)
        label = f"{identity[0]}:{identity[1]}"
        if identity in known:
            report.unchanged.append(label)
            continue
        resources.append(build_binding(reference))
        known.add(identity)
        report.added.append(label)

    for entry in resources:
        identity = (entry.resource, entry.key)
        if identity not in discovered:
            report.preserved.append(f"{entry.resource}:{entry.key}")

    version = existing.version if existing else BINDINGS_VERSION
    return Bindings(version=version, resources=resources), report
