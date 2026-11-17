from typing import Any, Dict, Tuple

from ._documents_service import _DocumentsServiceBase  # type: ignore[attr-defined]


class DocumentsServiceV2(_DocumentsServiceBase):
    """Service for managing UiPath DocumentUnderstanding Document Operations on DU Framework API v2.

    It has the same methods as `DocumentsService`, which calls API v1.1. API v2 results differ:

    - field IDs are prefixed with their document type and field group, e.g. `Default.Invoice.Total`
    - IXP results group fields in `FieldGroup` fields instead of `Table` fields, and their fields are typed, e.g. `MonetaryQuantity`
    - validation tasks open in the Compact view

    !!! warning "Preview Feature"
        This function is currently experimental.
        Behavior and parameters are subject to change in future versions.
    """

    _api_version = "2.0"

    def _tag_route(self, tag: str) -> Tuple[str, ...]:
        # v2 moved tag-scoped routes under a literal `tags` segment.
        return ("tags", tag)

    def _allow_document_type_change(self) -> Dict[str, Any]:
        # v2 moved this setting into the validation configuration.
        return {"configuration": {"allowChangeOfDocumentType": True}}
