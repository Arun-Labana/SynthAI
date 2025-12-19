"""Database models."""
from sqlalchemy import Column, String, Integer, Boolean, Text, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database.connection import Base


class Task(Base):
    """Task model."""
    __tablename__ = "tasks"
    
    task_id = Column(String(50), primary_key=True, index=True)
    task_description = Column(Text, nullable=False)
    status = Column(String(50), nullable=False, default="pending")
    
    # Workflow state
    iteration_count = Column(Integer, default=0)
    is_tests_passing = Column(Boolean, default=False)
    is_approved = Column(Boolean, default=False)
    
    # Results
    specification = Column(Text, nullable=True)
    pr_url = Column(String(500), nullable=True)
    error_message = Column(Text, nullable=True)
    
    # Code files (stored as JSON)
    code_files = Column(JSON, nullable=True)
    test_files = Column(JSON, nullable=True)
    
    # Task configuration
    target_repo_path = Column(String(500), nullable=True)
    github_repo_url = Column(String(500), nullable=True)
    
    # Metadata
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    messages = relationship("TaskMessage", back_populates="task", cascade="all, delete-orphan")


class TaskMessage(Base):
    """Task message/log model."""
    __tablename__ = "task_messages"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(50), ForeignKey("tasks.task_id", ondelete="CASCADE"), nullable=False)
    
    agent = Column(String(100), nullable=False)
    content = Column(Text, nullable=False)
    timestamp = Column(String(50), nullable=False)
    
    # Relationship
    task = relationship("Task", back_populates="messages")

