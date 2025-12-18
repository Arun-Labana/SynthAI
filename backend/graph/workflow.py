"""
LangGraph Workflow Construction.

Builds the stateful graph that orchestrates the multi-agent SDLC workflow.
"""

from typing import Optional, Dict, Any, Callable
from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from backend.graph.state import AgentState, WorkflowStatus, create_initial_state
from backend.graph.nodes import (
    pm_node,
    dev_node,
    qa_node,
    sandbox_node,
    reviewer_node,
    human_approval_node,
    github_pr_node,
    route_after_review,
    route_after_approval,
)
from backend.config import get_settings


def create_workflow(checkpointer: Optional[MemorySaver] = None) -> StateGraph:
    """
    Create the LangGraph workflow for the SDLC orchestration.
    
    The workflow follows this pattern:
    
    PM → Dev → QA → Sandbox → Reviewer
                                  ↓
                        ┌─────────┴─────────┐
                        ↓                   ↓
                    Dev (retry)      Human Approval
                                           ↓
                                    GitHub PR → End
    
    Args:
        checkpointer: Optional memory saver for state persistence
        
    Returns:
        Compiled StateGraph ready for execution
    """
    # Create the graph with our state schema
    workflow = StateGraph(AgentState)
    
    # Add all nodes
    workflow.add_node("pm_node", pm_node)
    workflow.add_node("dev_node", dev_node)
    workflow.add_node("qa_node", qa_node)
    workflow.add_node("sandbox_node", sandbox_node)
    workflow.add_node("reviewer_node", reviewer_node)
    workflow.add_node("human_approval_node", human_approval_node)
    workflow.add_node("github_pr_node", github_pr_node)
    
    # Set the entry point
    workflow.set_entry_point("pm_node")
    
    # Add linear edges (sequential flow)
    workflow.add_edge("pm_node", "dev_node")
    workflow.add_edge("dev_node", "qa_node")
    workflow.add_edge("qa_node", "sandbox_node")
    workflow.add_edge("sandbox_node", "reviewer_node")
    
    # Add conditional edges (branching)
    workflow.add_conditional_edges(
        "reviewer_node",
        route_after_review,
        {
            "dev_node": "dev_node",  # Loop back for revision
            "human_approval_node": "human_approval_node",  # Proceed to approval
            "end": END,  # Failure case
        }
    )
    
    workflow.add_conditional_edges(
        "human_approval_node",
        route_after_approval,
        {
            "github_pr_node": "github_pr_node",  # Create PR
            "end": END,  # Rejected
        }
    )
    
    # GitHub PR leads to end
    workflow.add_edge("github_pr_node", END)
    
    # Compile with checkpointer for persistence
    if checkpointer is None:
        checkpointer = MemorySaver()
    
    # Compile with interrupt points for human-in-the-loop
    compiled = workflow.compile(
        checkpointer=checkpointer,
        interrupt_before=["human_approval_node"],  # Pause for human approval
    )
    
    return compiled


class WorkflowRunner:
    """
    High-level interface for running the SDLC workflow.
    
    Provides convenient methods for:
    - Starting new tasks
    - Resuming paused workflows
    - Approving/rejecting at human checkpoints
    - Getting workflow status
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.checkpointer = MemorySaver()
        self.workflow = create_workflow(self.checkpointer)
    
    def start_task(
        self,
        task_id: str,
        task_description: str,
        target_repo_path: Optional[str] = None,
        github_repo_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Start a new SDLC task.
        
        Args:
            task_id: Unique identifier for this task
            task_description: Natural language description of what to build
            target_repo_path: Optional path to existing repo for RAG context
            github_repo_url: Optional GitHub repo URL for PR creation
            
        Returns:
            Initial state after PM agent processing (paused before human approval)
        """
        # Create initial state
        initial_state = create_initial_state(
            task_id=task_id,
            task_description=task_description,
            target_repo_path=target_repo_path,
            github_repo_url=github_repo_url,
            max_iterations=self.settings.max_iterations,
        )
        
        # Configuration for this run
        config = {"configurable": {"thread_id": task_id}}
        
        # Run until interrupt (human approval point)
        result = None
        for event in self.workflow.stream(initial_state, config):
            result = event
        
        return self._extract_state(result)
    
    def start_task_with_updates(
        self,
        task_id: str,
        task_description: str,
        target_repo_path: Optional[str] = None,
        github_repo_url: Optional[str] = None,
        on_update: Optional[Callable] = None,
    ) -> Dict[str, Any]:
        """Start task with callback for status updates."""
        initial_state = create_initial_state(
            task_id=task_id,
            task_description=task_description,
            target_repo_path=target_repo_path,
            github_repo_url=github_repo_url,
            max_iterations=self.settings.max_iterations,
        )
        
        config = {"configurable": {"thread_id": task_id}}
        
        result = None
        for event in self.workflow.stream(initial_state, config):
            result = event
            # Call update callback with extracted state
            if on_update and result:
                extracted = self._extract_state(result)
                on_update(extracted)
        
        return self._extract_state(result)
    
    def get_status(self, task_id: str) -> Dict[str, Any]:
        """
        Get the current status of a task.
        
        Args:
            task_id: The task identifier
            
        Returns:
            Current state of the task
        """
        config = {"configurable": {"thread_id": task_id}}
        
        try:
            state = self.workflow.get_state(config)
            return self._format_status(state.values)
        except Exception as e:
            return {"error": str(e), "task_id": task_id}
    
    def approve(self, task_id: str) -> Dict[str, Any]:
        """
        Approve a task at the human approval checkpoint.
        
        Args:
            task_id: The task identifier
            
        Returns:
            Final state after PR creation
        """
        config = {"configurable": {"thread_id": task_id}}
        
        # Update state to approved
        self.workflow.update_state(
            config,
            {"is_approved": True},
        )
        
        # Resume workflow
        result = None
        for event in self.workflow.stream(None, config):
            result = event
        
        return self._extract_state(result)
    
    def reject(self, task_id: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """
        Reject a task at the human approval checkpoint.
        
        Args:
            task_id: The task identifier
            reason: Optional rejection reason
            
        Returns:
            Final state
        """
        config = {"configurable": {"thread_id": task_id}}
        
        # Update state to rejected
        updates = {
            "is_approved": False,
            "status": WorkflowStatus.REJECTED,
        }
        if reason:
            updates["error_message"] = f"Rejected: {reason}"
        
        self.workflow.update_state(config, updates)
        
        # Resume to end
        result = None
        for event in self.workflow.stream(None, config):
            result = event
        
        return self._extract_state(result)
    
    def _extract_state(self, event: Dict) -> Dict[str, Any]:
        """Extract state from a workflow event."""
        if not event:
            return {}
        
        # Event is a dict with node names as keys
        # Get the last node's output
        for node_name, state in event.items():
            if isinstance(state, dict):
                return self._format_status(state)
        
        return event
    
    def _format_status(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Format state for API response."""
        return {
            "task_id": state.get("task_id"),
            "status": state.get("status", WorkflowStatus.PENDING).value if hasattr(state.get("status", ""), "value") else str(state.get("status")),
            "iteration_count": state.get("iteration_count", 0),
            "is_tests_passing": state.get("is_tests_passing", False),
            "is_approved": state.get("is_approved", False),
            "pr_url": state.get("pr_url"),
            "error_message": state.get("error_message"),
            "messages": state.get("messages", []),
            "code_files": list(state.get("code_files", {}).keys()),
            "test_files": list(state.get("test_files", {}).keys()),
        }


# Convenience function for quick workflow creation
def run_task(
    task_description: str,
    task_id: Optional[str] = None,
    target_repo_path: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Convenience function to run a task through the workflow.
    
    Args:
        task_description: What to build
        task_id: Optional task ID (auto-generated if not provided)
        target_repo_path: Optional repo path for context
        
    Returns:
        Workflow result
    """
    import uuid
    
    if task_id is None:
        task_id = str(uuid.uuid4())[:8]
    
    runner = WorkflowRunner()
    return runner.start_task(
        task_id=task_id,
        task_description=task_description,
        target_repo_path=target_repo_path,
    )

