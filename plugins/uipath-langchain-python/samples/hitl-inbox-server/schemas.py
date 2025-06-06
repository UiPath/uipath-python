from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class JobRequest(BaseModel):
    topic: str
    callback_url: Optional[str] = None

class JobResponse(BaseModel):
    job_id: str
    status: str
    message: str

class InboxMessageResponse(BaseModel):
    id: str
    job_id: str
    content: str
    status: str
    human_feedback: Optional[str] = None
    received_at: datetime
    approved_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class MessageApprovalRequest(BaseModel):
    human_feedback: str

class MessageApprovalResponse(BaseModel):
    status: str
    message: str

class JobBasicResponse(BaseModel):
    id: str
    topic: str
    status: str
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        orm_mode = True

class JobDetailResponse(BaseModel):
    id: str
    topic: str
    status: str
    output: Optional[str] = None
    agent_job_id: Optional[int] = None
    agent_job_key: Optional[str] = None
    human_feedback: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    messages: List[InboxMessageResponse] = []

    class Config:
        orm_mode = True
