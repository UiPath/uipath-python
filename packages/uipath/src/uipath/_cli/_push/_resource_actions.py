from dataclasses import dataclass

from .._utils._studio_project import (
    ReferencedResourceRequest,
    VirtualResourceRequest,
)


@dataclass(frozen=True, slots=True)
class CreateReference:
    request: ReferencedResourceRequest
    resource_name: str
    kind: str
    sub_type: str | None


@dataclass(frozen=True, slots=True)
class CreateVirtual:
    request: VirtualResourceRequest


@dataclass(frozen=True, slots=True)
class Skip:
    message: str


ResourceAction = CreateReference | CreateVirtual | Skip
