"""
FastAPI Routes for the Autonomous Tech Lead API.

Provides REST endpoints for:
- Creating and managing tasks
- Checking task status
- Approving/rejecting implementations
- RAG operations
"""

from typing import Optional, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import uuid

from backend.graph.workflow import WorkflowRunner
from backend.graph.state import WorkflowStatus


# API Router
router = APIRouter(prefix="/api/v1", tags=["tasks"])

# Store active workflow runners (in production, use Redis or similar)
_runners: Dict[str, WorkflowRunner] = {}
_task_states: Dict[str, Dict[str, Any]] = {}


# === Request/Response Models ===

class CreateTaskRequest(BaseModel):
    """Request body for creating a new task."""
    task_description: str = Field(..., description="Natural language description of the feature to build")
    target_repo_path: Optional[str] = Field(None, description="Path to existing repository for RAG context")
    github_repo_url: Optional[str] = Field(None, description="GitHub repo URL for PR creation (e.g., https://github.com/owner/repo)")
    task_id: Optional[str] = Field(None, description="Custom task ID (auto-generated if not provided)")


class CreateTaskResponse(BaseModel):
    """Response for task creation."""
    task_id: str
    status: str
    message: str


class TaskStatusResponse(BaseModel):
    """Response for task status."""
    task_id: str
    status: str
    iteration_count: int
    is_tests_passing: bool
    is_approved: bool
    pr_url: Optional[str]
    error_message: Optional[str]
    messages: list
    code_files: list
    test_files: list


class ApproveRejectRequest(BaseModel):
    """Request body for approve/reject."""
    reason: Optional[str] = Field(None, description="Optional reason for rejection")


class IndexRepositoryRequest(BaseModel):
    """Request body for indexing a repository."""
    repo_path: str = Field(..., description="Path to repository to index")
    clear_existing: bool = Field(False, description="Whether to clear existing embeddings")


# === Task Endpoints ===

@router.post("/tasks", response_model=CreateTaskResponse)
async def create_task(
    request: CreateTaskRequest,
) -> CreateTaskResponse:
    """
    Create a new SDLC task and start the workflow.
    
    The workflow will run through PM → Dev → QA → Sandbox → Review stages
    and pause at the human approval checkpoint.
    """
    # Generate task ID if not provided
    task_id = request.task_id or str(uuid.uuid4())[:8]
    
    # Check for duplicate task ID
    if task_id in _task_states:
        raise HTTPException(
            status_code=400,
            detail=f"Task with ID '{task_id}' already exists"
        )
    
    # Initialize task state
    _task_states[task_id] = {
        "task_id": task_id,
        "status": WorkflowStatus.PENDING.value,
        "task_description": request.task_description,
        "target_repo_path": request.target_repo_path,
        "github_repo_url": request.github_repo_url,
    }
    
    # Start workflow in background thread (non-blocking)
    _run_workflow(
        task_id,
        request.task_description,
        request.target_repo_path,
        request.github_repo_url,
    )
    
    return CreateTaskResponse(
        task_id=task_id,
        status="started",
        message="Task created. Workflow starting in background.",
    )


@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str) -> TaskStatusResponse:
    """Get the current status of a task."""
    if task_id not in _task_states:
        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_id}' not found"
        )
    
    state = _task_states[task_id]
    
    return TaskStatusResponse(
        task_id=task_id,
        status=state.get("status", "unknown"),
        iteration_count=state.get("iteration_count", 0),
        is_tests_passing=state.get("is_tests_passing", False),
        is_approved=state.get("is_approved", False),
        pr_url=state.get("pr_url"),
        error_message=state.get("error_message"),
        messages=state.get("messages", []),
        code_files=state.get("code_files", []),
        test_files=state.get("test_files", []),
    )


@router.get("/tasks")
async def list_tasks() -> Dict[str, Any]:
    """List all tasks with their current status."""
    tasks = []
    for task_id, state in _task_states.items():
        tasks.append({
            "task_id": task_id,
            "status": state.get("status", "unknown"),
            "description": state.get("task_description", "")[:100],
        })
    
    return {"tasks": tasks, "total": len(tasks)}


@router.post("/tasks/{task_id}/approve")
async def approve_task(
    task_id: str,
    background_tasks: BackgroundTasks,
) -> Dict[str, str]:
    """
    Approve a task at the human approval checkpoint.
    
    This will resume the workflow and create a GitHub PR.
    """
    if task_id not in _task_states:
        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_id}' not found"
        )
    
    state = _task_states[task_id]
    
    if state.get("status") != WorkflowStatus.AWAITING_APPROVAL.value:
        raise HTTPException(
            status_code=400,
            detail=f"Task is not awaiting approval. Current status: {state.get('status')}"
        )
    
    # Resume workflow in background
    background_tasks.add_task(_approve_task, task_id)
    
    return {"message": "Approval submitted. Creating PR in background."}


@router.post("/tasks/{task_id}/reject")
async def reject_task(
    task_id: str,
    request: ApproveRejectRequest,
) -> Dict[str, str]:
    """
    Reject a task at the human approval checkpoint.
    
    This will end the workflow without creating a PR.
    """
    if task_id not in _task_states:
        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_id}' not found"
        )
    
    state = _task_states[task_id]
    
    if state.get("status") != WorkflowStatus.AWAITING_APPROVAL.value:
        raise HTTPException(
            status_code=400,
            detail=f"Task is not awaiting approval. Current status: {state.get('status')}"
        )
    
    # Update state
    state["status"] = WorkflowStatus.REJECTED.value
    state["is_approved"] = False
    if request.reason:
        state["error_message"] = f"Rejected: {request.reason}"
    
    return {"message": "Task rejected.", "task_id": task_id}


@router.get("/tasks/{task_id}/code")
async def get_task_code(task_id: str) -> Dict[str, Any]:
    """Get the generated code files for a task."""
    if task_id not in _task_states:
        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_id}' not found"
        )
    
    state = _task_states[task_id]
    
    return {
        "task_id": task_id,
        "code_files": state.get("full_code_files", {}),
        "test_files": state.get("full_test_files", {}),
    }


@router.get("/tasks/{task_id}/spec")
async def get_task_specification(task_id: str) -> Dict[str, Any]:
    """Get the technical specification for a task."""
    if task_id not in _task_states:
        raise HTTPException(
            status_code=404,
            detail=f"Task '{task_id}' not found"
        )
    
    state = _task_states[task_id]
    
    return {
        "task_id": task_id,
        "specification": state.get("specification"),
        "task_breakdown": state.get("task_breakdown"),
        "acceptance_criteria": state.get("acceptance_criteria"),
    }


# === RAG Endpoints ===

@router.post("/rag/index")
async def index_repository(request: IndexRepositoryRequest) -> Dict[str, Any]:
    """Index a repository for RAG context."""
    from backend.rag.retriever import CodeRetriever
    
    try:
        retriever = CodeRetriever()
        count = retriever.index_repository(
            request.repo_path,
            clear_existing=request.clear_existing,
        )
        
        return {
            "message": f"Indexed {count} code chunks",
            "repo_path": request.repo_path,
            "chunks_indexed": count,
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to index repository: {str(e)}"
        )


@router.get("/rag/stats")
async def get_rag_stats() -> Dict[str, Any]:
    """Get RAG collection statistics."""
    from backend.rag.retriever import CodeRetriever
    
    try:
        retriever = CodeRetriever()
        return retriever.get_collection_stats()
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get RAG stats: {str(e)}"
        )


# === Health Endpoints ===

@router.get("/health")
async def health_check() -> Dict[str, Any]:
    """Check API health and dependencies (fast, no external calls)."""
    from backend.config import get_settings
    import os
    
    settings = get_settings()
    
    health = {
        "api": "healthy",
        "llm_provider": settings.llm_provider,
        "docker": "unknown",
        "github": "unknown",
    }
    
    # Check Docker socket exists (fast check, no API call)
    docker_sockets = [
        os.path.expanduser("~/.rd/docker.sock"),  # Rancher Desktop
        "/var/run/docker.sock",  # Docker Desktop / Linux
    ]
    for sock in docker_sockets:
        if os.path.exists(sock):
            health["docker"] = "available"
            health["docker_socket"] = sock
            break
    else:
        health["docker"] = "socket not found"
    
    # Check GitHub token is configured (no API call)
    github_token = os.environ.get("GITHUB_TOKEN", "")
    if github_token:
        health["github"] = "token configured"
    else:
        health["github"] = "no token (PR creation disabled)"
    
    return health


@router.get("/health/full")
async def health_check_full() -> Dict[str, Any]:
    """Full health check with external API calls (slower)."""
    from backend.sandbox.docker_runner import DockerSandbox
    
    health = {
        "api": "healthy",
        "docker": "unknown",
        "github": "unknown",
    }
    
    # Check Docker
    try:
        sandbox = DockerSandbox()
        docker_health = sandbox.health_check()
        health["docker"] = "healthy" if docker_health.get("docker_available") else "unavailable"
        health["docker_details"] = docker_health
    except Exception as e:
        health["docker"] = f"error: {str(e)}"
    
    # Check GitHub (only if token exists)
    import os
    if os.environ.get("GITHUB_TOKEN"):
        try:
            from backend.integrations.github_client import GitHubClient
            client = GitHubClient()
            gh_health = client.check_connection()
            health["github"] = "connected" if gh_health.get("connected") else "disconnected"
            health["github_details"] = gh_health
        except Exception as e:
            health["github"] = f"error: {str(e)}"
    else:
        health["github"] = "no token configured"
    
    return health


# === Background Task Functions ===

def _run_workflow_sync(
    task_id: str,
    task_description: str,
    target_repo_path: Optional[str],
    github_repo_url: Optional[str] = None,
):
    """Run the workflow synchronously (called from thread)."""
    import traceback
    
    print(f"[{task_id}] 🚀 Starting workflow...")
    
    try:
        runner = WorkflowRunner()
        _runners[task_id] = runner
        
        _task_states[task_id]["status"] = WorkflowStatus.PM_PROCESSING.value
        
        # Run workflow with status updates after each step
        result = runner.start_task_with_updates(
            task_id=task_id,
            task_description=task_description,
            target_repo_path=target_repo_path,
            github_repo_url=github_repo_url,
            on_update=lambda state: _update_task_state(task_id, state),
        )
        
        final_status = result.get('status', 'unknown')
        print(f"[{task_id}] ✅ Workflow completed: {final_status}")
        
        # Get full state for code/test files
        status = runner.get_status(task_id)
        
        # Update task state with result (has correct final status)
        _task_states[task_id].update(result)
        
        # Add full file contents
        if "code_files" in status:
            _task_states[task_id]["full_code_files"] = status.get("code_files", {})
        if "test_files" in status:
            _task_states[task_id]["full_test_files"] = status.get("test_files", {})
        
        # Ensure status is correct (result has the authoritative status)
        if "status" in result:
            _task_states[task_id]["status"] = result["status"]
        
        print(f"[{task_id}] Final status in _task_states: {_task_states[task_id].get('status')}")
            
    except Exception as e:
        print(f"[{task_id}] ❌ Error: {str(e)}")
        traceback.print_exc()
        _task_states[task_id]["status"] = WorkflowStatus.FAILED.value
        _task_states[task_id]["error_message"] = str(e)


def _update_task_state(task_id: str, state: Dict[str, Any]):
    """Update task state from workflow progress."""
    if task_id in _task_states:
        if "status" in state:
            status = state["status"]
            # Convert WorkflowStatus enum to string if needed
            _task_states[task_id]["status"] = status.value if hasattr(status, 'value') else str(status)
        if "messages" in state:
            _task_states[task_id]["messages"] = state.get("messages", [])
        if "iteration_count" in state:
            _task_states[task_id]["iteration_count"] = state.get("iteration_count", 0)
        if "code_files" in state:
            cf = state.get("code_files", {})
            _task_states[task_id]["code_files"] = list(cf.keys()) if isinstance(cf, dict) else cf
        if "test_files" in state:
            tf = state.get("test_files", {})
            _task_states[task_id]["test_files"] = list(tf.keys()) if isinstance(tf, dict) else tf


def _run_workflow(
    task_id: str,
    task_description: str,
    target_repo_path: Optional[str],
    github_repo_url: Optional[str] = None,
):
    """Start workflow in a background thread (non-blocking)."""
    import threading
    thread = threading.Thread(
        target=_run_workflow_sync,
        args=(task_id, task_description, target_repo_path, github_repo_url),
        daemon=True
    )
    thread.start()


async def _approve_task(task_id: str):
    """Approve task and resume workflow."""
    try:
        if task_id in _runners:
            runner = _runners[task_id]
            result = runner.approve(task_id)
            _task_states[task_id].update(result)
        else:
            # Recreate runner if not in memory
            runner = WorkflowRunner()
            result = runner.approve(task_id)
            _task_states[task_id].update(result)
            
    except Exception as e:
        _task_states[task_id]["status"] = WorkflowStatus.FAILED.value
        _task_states[task_id]["error_message"] = f"Approval failed: {str(e)}"

