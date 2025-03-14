from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class Job(Base):
    __tablename__ = "jobs"

    id = Column(String, primary_key=True, index=True)
    agent_job_key = Column(String, index=True, nullable=True)
    agent_job_id = Column(Integer, index=True, nullable=True)
    topic = Column(String, index=True)
    status = Column(String, index=True)  # creating, pending, running, suspended, resumed, faulted, completed
    output = Column(Text)
    error_message = Column(Text, nullable=True)
    human_feedback = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.now)
    completed_at = Column(DateTime, nullable=True)

    messages = relationship("InboxMessage", back_populates="job")

class InboxMessage(Base):
    __tablename__ = "inbox_messages"

    id = Column(String, primary_key=True, index=True)
    job_id = Column(String, ForeignKey("jobs.id"), index=True)
    content = Column(Text)
    status = Column(String, index=True)  # pending, approved, rejected
    human_feedback = Column(Text, nullable=True)
    received_at = Column(DateTime, default=datetime.now)
    approved_at = Column(DateTime, nullable=True)

    job = relationship("Job", back_populates="messages")
