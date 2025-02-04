from pydantic import BaseModel


class ContextGroundingMetadata(BaseModel):
    operation_id: str
    strategy: str


class ContextGroundingQueryResponse(BaseModel):
    id: str
    reference: str
    source: str
    page_number: str
    source_document_id: str
    caption: str
    score: float
    content: str
    metadata: ContextGroundingMetadata
