"""Database service for task operations."""
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from backend.database.models import Task, TaskMessage
from backend.database.connection import SessionLocal


class TaskService:
    """Service for managing tasks in database."""
    
    @staticmethod
    def create_task(
        task_id: str,
        task_description: str,
        target_repo_path: Optional[str] = None,
        github_repo_url: Optional[str] = None,
    ) -> Task:
        """Create a new task."""
        db = SessionLocal()
        try:
            task = Task(
                task_id=task_id,
                task_description=task_description,
                status="pending",
                target_repo_path=target_repo_path,
                github_repo_url=github_repo_url,
            )
            db.add(task)
            db.commit()
            db.refresh(task)
            return task
        finally:
            db.close()
    
    @staticmethod
    def get_task(task_id: str) -> Optional[Task]:
        """Get task by ID."""
        db = SessionLocal()
        try:
            return db.query(Task).filter(Task.task_id == task_id).first()
        finally:
            db.close()
    
    @staticmethod
    def list_tasks(limit: int = 100, offset: int = 0) -> List[Task]:
        """List all tasks."""
        db = SessionLocal()
        try:
            return db.query(Task).order_by(Task.created_at.desc()).limit(limit).offset(offset).all()
        finally:
            db.close()
    
    @staticmethod
    def update_task(task_id: str, updates: Dict[str, Any]) -> Optional[Task]:
        """Update task fields."""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                return None
            
            for key, value in updates.items():
                if hasattr(task, key):
                    setattr(task, key, value)
            
            db.commit()
            db.refresh(task)
            return task
        finally:
            db.close()
    
    @staticmethod
    def add_message(task_id: str, agent: str, content: str, timestamp: str):
        """Add a message to a task."""
        db = SessionLocal()
        try:
            message = TaskMessage(
                task_id=task_id,
                agent=agent,
                content=content,
                timestamp=timestamp,
            )
            db.add(message)
            db.commit()
        finally:
            db.close()
    
    @staticmethod
    def get_messages(task_id: str) -> List[TaskMessage]:
        """Get all messages for a task."""
        db = SessionLocal()
        try:
            return db.query(TaskMessage).filter(TaskMessage.task_id == task_id).all()
        finally:
            db.close()
    
    @staticmethod
    def delete_task(task_id: str) -> bool:
        """Delete a task."""
        db = SessionLocal()
        try:
            task = db.query(Task).filter(Task.task_id == task_id).first()
            if not task:
                return False
            
            db.delete(task)
            db.commit()
            return True
        finally:
            db.close()

