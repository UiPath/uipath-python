from typing import TypedDict


class ContextGroundingMetadata(TypedDict):
    operation_id: str
    strategy: str


class ContextGroundingQueryResponse(TypedDict):
    id: str
    reference: str
    source: str
    page_number: str
    source_document_id: str
    caption: str
    score: float
    content: str
    metadata: ContextGroundingMetadata
