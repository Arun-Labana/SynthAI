"""
Unit tests for the FastAPI endpoints.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """Create test client."""
    with patch('backend.api.main.get_settings') as mock_settings:
        mock_settings.return_value = Mock(
            api_host="0.0.0.0",
            api_port=8000,
            anthropic_api_key="test-key",
            openai_api_key="test-key"
        )
        
        from backend.api.main import app
        yield TestClient(app)


class TestHealthEndpoint:
    """Tests for the health check endpoint."""
    
    @patch('backend.api.routes.DockerSandbox')
    def test_health_check(self, mock_sandbox, client):
        """Test health check returns status."""
        mock_sandbox.return_value.health_check.return_value = {
            "docker_available": True,
            "docker_version": "24.0.0"
        }
        
        response = client.get("/api/v1/health")
        
        assert response.status_code == 200
        data = response.json()
        assert "api" in data
        assert data["api"] == "healthy"


class TestTaskEndpoints:
    """Tests for task management endpoints."""
    
    def test_list_tasks_empty(self, client):
        """Test listing tasks when none exist."""
        # Clear task state
        from backend.api.routes import _task_states
        _task_states.clear()
        
        response = client.get("/api/v1/tasks")
        
        assert response.status_code == 200
        data = response.json()
        assert data["tasks"] == []
        assert data["total"] == 0
    
    def test_get_task_not_found(self, client):
        """Test getting a non-existent task."""
        response = client.get("/api/v1/tasks/nonexistent-id")
        
        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()
    
    @patch('backend.api.routes._run_workflow')
    def test_create_task(self, mock_workflow, client):
        """Test creating a new task."""
        # Clear task state
        from backend.api.routes import _task_states
        _task_states.clear()
        
        response = client.post(
            "/api/v1/tasks",
            json={
                "task_description": "Build a test feature",
                "task_id": "test-task-001"
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["task_id"] == "test-task-001"
        assert data["status"] == "started"
    
    def test_create_task_duplicate_id(self, client):
        """Test creating task with duplicate ID."""
        # Setup existing task
        from backend.api.routes import _task_states
        _task_states["existing-task"] = {"task_id": "existing-task", "status": "pending"}
        
        response = client.post(
            "/api/v1/tasks",
            json={
                "task_description": "Another feature",
                "task_id": "existing-task"
            }
        )
        
        assert response.status_code == 400
        assert "already exists" in response.json()["detail"].lower()
    
    def test_approve_task_not_awaiting(self, client):
        """Test approving a task that isn't awaiting approval."""
        from backend.api.routes import _task_states
        _task_states["running-task"] = {
            "task_id": "running-task",
            "status": "dev_processing"
        }
        
        response = client.post("/api/v1/tasks/running-task/approve")
        
        assert response.status_code == 400
        assert "not awaiting approval" in response.json()["detail"].lower()
    
    def test_reject_task(self, client):
        """Test rejecting a task."""
        from backend.api.routes import _task_states
        from backend.graph.state import WorkflowStatus
        
        _task_states["approve-test"] = {
            "task_id": "approve-test",
            "status": WorkflowStatus.AWAITING_APPROVAL.value
        }
        
        response = client.post(
            "/api/v1/tasks/approve-test/reject",
            json={"reason": "Not ready yet"}
        )
        
        assert response.status_code == 200
        assert _task_states["approve-test"]["status"] == WorkflowStatus.REJECTED.value


class TestRAGEndpoints:
    """Tests for RAG management endpoints."""
    
    @patch('backend.api.routes.CodeRetriever')
    def test_get_rag_stats(self, mock_retriever, client):
        """Test getting RAG statistics."""
        mock_retriever.return_value.get_collection_stats.return_value = {
            "total_chunks": 100,
            "collection_name": "codebase",
            "persist_directory": "./chroma_db"
        }
        
        response = client.get("/api/v1/rag/stats")
        
        assert response.status_code == 200
        data = response.json()
        assert data["total_chunks"] == 100


class TestRootEndpoint:
    """Tests for the root endpoint."""
    
    def test_root_returns_info(self, client):
        """Test root endpoint returns API info."""
        response = client.get("/")
        
        assert response.status_code == 200
        data = response.json()
        assert "name" in data
        assert "version" in data
        assert "docs" in data

