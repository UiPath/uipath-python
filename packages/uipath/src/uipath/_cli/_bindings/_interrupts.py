"""Resources reached by constructing an interrupt model rather than calling the SDK.

A LangGraph agent rarely calls ``sdk.processes.invoke_async`` directly. It
builds an interrupt model and hands it to ``interrupt(...)``; the resume-trigger
protocol then makes the decorated SDK call on its behalf::

    interrupt(InvokeProcess(name="child", process_folder_path="Shared"))

The call site in user code is a constructor, so the decorator registry cannot
see it. Each spec below mirrors one branch of
``uipath.platform.resume_triggers._protocol``, which is what decides the SDK
method a model routes to and therefore the resource it binds.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class InterruptSpec:
    """How to read a resource out of one interrupt model constructor."""

    model: str
    resource_type: str
    name_field: str
    folder_field: Optional[str]
    activity_name: str


def _spec(
    model: str,
    resource_type: str,
    name_field: str,
    folder_field: str,
    activity_name: str,
) -> tuple[str, InterruptSpec]:
    return model, InterruptSpec(
        model=model,
        resource_type=resource_type,
        name_field=name_field,
        folder_field=folder_field,
        activity_name=activity_name,
    )


INTERRUPT_SPECS: dict[str, InterruptSpec] = dict(
    [
        _spec(
            "InvokeProcess", "process", "name", "process_folder_path", "invoke_async"
        ),
        _spec(
            "InvokeProcessRaw", "process", "name", "process_folder_path", "invoke_async"
        ),
        _spec("CreateTask", "app", "app_name", "app_folder_path", "create_async"),
        _spec("CreateEscalation", "app", "app_name", "app_folder_path", "create_async"),
        # `name` on these two is the task's own name; `index_name` is the resource.
        _spec(
            "CreateDeepRag",
            "index",
            "index_name",
            "index_folder_path",
            "start_deep_rag_async",
        ),
        _spec(
            "CreateDeepRagRaw",
            "index",
            "index_name",
            "index_folder_path",
            "start_deep_rag_async",
        ),
        _spec(
            "CreateBatchTransform",
            "index",
            "index_name",
            "index_folder_path",
            "start_batch_transform_async",
        ),
    ]
)

NON_BINDING_INTERRUPT_MODELS: frozenset[str] = frozenset(
    {
        # Reference a job or action that already exists, by key. The folder on
        # them locates that object; it does not name a new resource.
        "WaitJob",
        "WaitJobRaw",
        "WaitTask",
        "WaitEscalation",
        "WaitDeepRag",
        "WaitDeepRagRaw",
        "WaitBatchTransform",
        "WaitEphemeralIndex",
        "WaitEphemeralIndexRaw",
        "WaitDocumentExtraction",
        "WaitDocumentExtractionValidation",
        "WaitSystemAgent",
        # Ephemeral indexes are created per run and have no name to bind.
        "CreateEphemeralIndex",
        "CreateEphemeralIndexRaw",
        # Routed through agenthub, which carries no @resource_override.
        "InvokeSystemAgent",
        # Document Understanding projects are not one of the bindable types.
        "DocumentExtraction",
        "DocumentExtractionValidation",
        # Names a connection, but connection bindings key on the connection id.
        "WaitIntegrationEvent",
        # Carries no resource at all.
        "WaitUntil",
    }
)
