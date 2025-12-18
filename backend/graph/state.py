"""
Agent State Definition for LangGraph workflow.
This is the shared state that all agents read from and write to.
"""

from typing import TypedDict, Dict, List, Optional, Annotated
from enum import Enum
import operator


class WorkflowStatus(str, Enum):
    """Status of the overall workflow."""
    PENDING = "pending"
    PM_PROCESSING = "pm_processing"
    DEV_PROCESSING = "dev_processing"
    QA_PROCESSING = "qa_processing"
    SANDBOX_RUNNING = "sandbox_running"
    REVIEW_PROCESSING = "review_processing"
    AWAITING_APPROVAL = "awaiting_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    FAILED = "failed"
    COMPLETED = "completed"


class AgentMessage(TypedDict):
    """A message from an agent."""
    agent: str
    content: str
    timestamp: str


class AgentState(TypedDict):
    """
    Shared state for the multi-agent workflow.
    
    This state is passed through the LangGraph workflow and modified by each agent.
    Using Annotated with operator.add allows messages to be appended rather than replaced.
    """
    
    # Task Information
    task_id: str
    task_description: str
    target_repo_path: Optional[str]  # Local path for RAG context
    
    # GitHub Repository (for PR creation)
    github_repo_url: Optional[str]  # e.g., "https://github.com/owner/repo"
    github_owner: Optional[str]     # Extracted from URL
    github_repo: Optional[str]      # Extracted from URL
    
    # PM Agent Output
    specification: Optional[str]  # Technical specification markdown
    task_breakdown: Optional[List[Dict[str, str]]]  # List of subtasks
    acceptance_criteria: Optional[List[str]]
    
    # Dev Agent Output
    code_files: Dict[str, str]  # {filename: content}
    
    # QA Agent Output
    test_files: Dict[str, str]  # {test_filename: content}
    
    # Sandbox Execution
    execution_logs: Optional[str]
    test_results: Optional[str]
    exit_code: Optional[int]
    
    # Review & Iteration
    review_feedback: Optional[str]
    is_tests_passing: bool
    is_approved: bool
    iteration_count: int
    max_iterations: int
    
    # Workflow Control
    status: WorkflowStatus
    error_message: Optional[str]
    
    # Message History (appended by each agent)
    messages: Annotated[List[AgentMessage], operator.add]
    
    # GitHub PR (final output)
    pr_url: Optional[str]
    branch_name: Optional[str]


def parse_github_url(url: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    """
    Parse GitHub URL to extract owner and repo.
    
    Supports formats:
    - https://github.com/owner/repo
    - https://github.com/owner/repo.git
    - git@github.com:owner/repo.git
    
    Returns:
        Tuple of (owner, repo) or (None, None) if invalid
    """
    if not url:
        return None, None
    
    import re
    
    # HTTPS format
    https_match = re.match(r'https?://github\.com/([^/]+)/([^/\.]+)', url)
    if https_match:
        return https_match.group(1), https_match.group(2)
    
    # SSH format
    ssh_match = re.match(r'git@github\.com:([^/]+)/([^/\.]+)', url)
    if ssh_match:
        return ssh_match.group(1), ssh_match.group(2)
    
    return None, None


def create_initial_state(
    task_id: str,
    task_description: str,
    target_repo_path: Optional[str] = None,
    github_repo_url: Optional[str] = None,
    max_iterations: int = 3
) -> AgentState:
    """
    Create a fresh initial state for a new task.
    
    Args:
        task_id: Unique identifier for this task
        task_description: Natural language description of what to build
        target_repo_path: Optional path to existing repository for RAG context
        github_repo_url: Optional GitHub repo URL for PR creation
        max_iterations: Maximum dev-review iterations before human intervention
    
    Returns:
        Initial AgentState ready for workflow execution
    """
    # Parse GitHub URL
    github_owner, github_repo = parse_github_url(github_repo_url)
    
    return AgentState(
        # Task Information
        task_id=task_id,
        task_description=task_description,
        target_repo_path=target_repo_path,
        
        # GitHub
        github_repo_url=github_repo_url,
        github_owner=github_owner,
        github_repo=github_repo,
        
        # PM Agent Output (to be filled)
        specification=None,
        task_breakdown=None,
        acceptance_criteria=None,
        
        # Dev Agent Output (to be filled)
        code_files={},
        
        # QA Agent Output (to be filled)
        test_files={},
        
        # Sandbox Execution (to be filled)
        execution_logs=None,
        test_results=None,
        exit_code=None,
        
        # Review & Iteration
        review_feedback=None,
        is_tests_passing=False,
        is_approved=False,
        iteration_count=0,
        max_iterations=max_iterations,
        
        # Workflow Control
        status=WorkflowStatus.PENDING,
        error_message=None,
        
        # Message History
        messages=[],
        
        # GitHub PR
        pr_url=None,
        branch_name=None,
    )

