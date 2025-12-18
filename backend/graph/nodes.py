"""
Graph Node Functions for LangGraph Workflow.

Each function represents a node in the workflow graph and takes/returns AgentState.
"""

from typing import Literal

from backend.graph.state import AgentState, WorkflowStatus
from backend.agents.pm_agent import PMAgent
from backend.agents.dev_agent import DevAgent
from backend.agents.qa_agent import QAAgent
from backend.agents.reviewer_agent import ReviewerAgent
from backend.sandbox.docker_runner import DockerSandbox, SandboxResult
from backend.rag.retriever import CodeRetriever


# Initialize agents (lazily loaded on first use)
_pm_agent = None
_dev_agent = None
_qa_agent = None
_reviewer_agent = None
_sandbox = None
_retriever = None


def get_pm_agent() -> PMAgent:
    """Get or create PM Agent instance."""
    global _pm_agent
    if _pm_agent is None:
        _pm_agent = PMAgent()
    return _pm_agent


def get_dev_agent() -> DevAgent:
    """Get or create Dev Agent instance."""
    global _dev_agent, _retriever
    if _dev_agent is None:
        try:
            _retriever = CodeRetriever()
        except Exception:
            _retriever = None
        _dev_agent = DevAgent(retriever=_retriever)
    return _dev_agent


def get_qa_agent() -> QAAgent:
    """Get or create QA Agent instance."""
    global _qa_agent
    if _qa_agent is None:
        _qa_agent = QAAgent()
    return _qa_agent


def get_reviewer_agent() -> ReviewerAgent:
    """Get or create Reviewer Agent instance."""
    global _reviewer_agent
    if _reviewer_agent is None:
        _reviewer_agent = ReviewerAgent()
    return _reviewer_agent


def get_sandbox() -> DockerSandbox:
    """Get or create Docker Sandbox instance."""
    global _sandbox
    if _sandbox is None:
        _sandbox = DockerSandbox()
    return _sandbox


# === Node Functions ===

def pm_node(state: AgentState) -> AgentState:
    """PM Agent Node - Generates technical specification."""
    print(f"\n📋 [PM Node] Starting...")
    agent = get_pm_agent()
    result = agent.run(state)
    print(f"📋 [PM Node] Done - Generated spec with {len(result.get('task_breakdown', []))} tasks")
    return {**result, "status": WorkflowStatus.PM_PROCESSING}


def dev_node(state: AgentState) -> AgentState:
    """
    Dev Agent Node - Generates code implementation.
    
    Uses RAG to understand existing codebase and generates code
    that matches the specification.
    """
    print(f"\n💻 [Dev Node] Starting...")
    agent = get_dev_agent()
    result = agent.run(state)
    files = list(result.get('code_files', {}).keys())
    print(f"💻 [Dev Node] Done - Generated {len(files)} files: {files}")
    return {**result, "status": WorkflowStatus.DEV_PROCESSING}


def qa_node(state: AgentState) -> AgentState:
    """QA Agent Node - Generates test suite."""
    print(f"\n🧪 [QA Node] Starting...")
    agent = get_qa_agent()
    result = agent.run(state)
    tests = list(result.get('test_files', {}).keys())
    print(f"🧪 [QA Node] Done - Generated {len(tests)} test files: {tests}")
    return {**result, "status": WorkflowStatus.QA_PROCESSING}


def sandbox_node(state: AgentState) -> AgentState:
    """Sandbox Node - Executes code in Docker."""
    print(f"\n🐳 [Sandbox Node] Starting...")
    sandbox = get_sandbox()
    
    code_files = state.get('code_files', {})
    test_files = state.get('test_files', {})
    
    print(f"🐳 [Sandbox] Code files: {list(code_files.keys())}")
    print(f"🐳 [Sandbox] Test files: {list(test_files.keys())}")
    
    if not code_files:
        print(f"🐳 [Sandbox] ❌ No code files!")
        return {
            "status": WorkflowStatus.FAILED,
            "error_message": "No code files to execute",
            "execution_logs": "Error: No code files were generated.",
            "exit_code": -1,
            "messages": [{
                "agent": "Sandbox",
                "content": "Failed: No code files to execute",
                "timestamp": _get_timestamp(),
            }],
        }
    
    result: SandboxResult = sandbox.run(code_files, test_files)
    
    print(f"🐳 [Sandbox] Exit code: {result.exit_code}")
    print(f"🐳 [Sandbox] Success: {result.success}")
    print(f"🐳 [Sandbox] STDOUT:\n{result.stdout[:500]}...")
    if result.stderr:
        print(f"🐳 [Sandbox] STDERR:\n{result.stderr[:500]}...")
    
    execution_logs = f"=== STDOUT ===\n{result.stdout}\n\n=== STDERR ===\n{result.stderr}"
    
    if result.success:
        test_summary = "All tests passed!"
    else:
        test_summary = f"Tests failed with exit code {result.exit_code}.\n{result.stderr or result.stdout}"
    
    return {
        "status": WorkflowStatus.REVIEW_PROCESSING,
        "execution_logs": execution_logs,
        "test_results": test_summary,
        "exit_code": result.exit_code,
        "messages": [{
            "agent": "Sandbox",
            "content": f"Execution completed in {result.execution_time:.2f}s. Exit code: {result.exit_code}",
            "timestamp": _get_timestamp(),
        }],
    }


def reviewer_node(state: AgentState) -> AgentState:
    """
    Reviewer Agent Node - Reviews execution results and decides next action.
    
    Determines whether to:
    - Approve and send to human review
    - Send back to Dev Agent for fixes
    - Fail the workflow
    """
    print(f"\n🔍 [Reviewer Node] Starting...")
    print(f"🔍 [Reviewer] Exit code from sandbox: {state.get('exit_code')}")
    agent = get_reviewer_agent()
    result = agent.run(state)
    decision = result.get('status', 'unknown')
    print(f"🔍 [Reviewer Node] Done - Decision: {decision}")
    # Don't overwrite the status - agent sets the correct one (awaiting_approval, dev_processing, or failed)
    return result


def human_approval_node(state: AgentState) -> AgentState:
    """
    Human Approval Node - Placeholder for human-in-the-loop.
    
    In the actual workflow, this is an interrupt point where
    the graph pauses for human approval.
    """
    return {
        "status": WorkflowStatus.AWAITING_APPROVAL,
        "messages": [{
            "agent": "System",
            "content": "Awaiting human approval before creating PR.",
            "timestamp": _get_timestamp(),
        }],
    }


def github_pr_node(state: AgentState) -> AgentState:
    """
    GitHub PR Node - Creates pull request with the implementation.
    
    Only called after human approval.
    """
    from backend.integrations.github_client import GitHubClient
    
    # Check if GitHub is configured for this task
    if not state.get('github_owner') or not state.get('github_repo'):
        return {
            "status": WorkflowStatus.COMPLETED,
            "is_approved": True,
            "pr_url": None,
            "messages": [{
                "agent": "GitHub",
                "content": "✅ Task approved! No GitHub repo configured - PR creation skipped.",
                "timestamp": _get_timestamp(),
            }],
        }
    
    try:
        client = GitHubClient(
            owner=state.get('github_owner'),
            repo=state.get('github_repo'),
        )
        
        # Create PR
        pr_result = client.create_pull_request(
            title=f"[AI] {state['task_description'][:50]}",
            body=_build_pr_body(state),
            code_files=state.get('code_files', {}),
            test_files=state.get('test_files', {}),
        )
        
        return {
            "status": WorkflowStatus.COMPLETED,
            "is_approved": True,
            "pr_url": pr_result.get('pr_url'),
            "branch_name": pr_result.get('branch_name'),
            "messages": [{
                "agent": "GitHub",
                "content": f"PR created successfully: {pr_result.get('pr_url')}",
                "timestamp": _get_timestamp(),
            }],
        }
        
    except Exception as e:
        return {
            "status": WorkflowStatus.FAILED,
            "error_message": f"Failed to create PR: {str(e)}",
            "messages": [{
                "agent": "GitHub",
                "content": f"Failed to create PR: {str(e)}",
                "timestamp": _get_timestamp(),
            }],
        }


# === Routing Functions ===

def route_after_review(state: AgentState) -> Literal["dev_node", "human_approval_node", "end"]:
    """
    Route after reviewer decision.
    
    Returns:
        - "dev_node" if revision needed
        - "human_approval_node" if approved or max iterations reached
        - "end" if failed
    """
    status = state.get('status')
    
    if status == WorkflowStatus.DEV_PROCESSING:
        return "dev_node"
    elif status == WorkflowStatus.AWAITING_APPROVAL:
        return "human_approval_node"
    elif status == WorkflowStatus.FAILED:
        return "end"
    else:
        # Default to human approval for safety
        return "human_approval_node"


def route_after_approval(state: AgentState) -> Literal["github_pr_node", "end"]:
    """
    Route after human approval.
    
    Returns:
        - "github_pr_node" if approved
        - "end" if rejected
    """
    if state.get('is_approved'):
        return "github_pr_node"
    else:
        return "end"


# === Helper Functions ===

def _get_timestamp() -> str:
    """Get current UTC timestamp."""
    from datetime import datetime
    return datetime.utcnow().isoformat()


def _build_pr_body(state: AgentState) -> str:
    """Build the PR description body."""
    body = f"""## 🤖 AI-Generated Pull Request

### Task Description
{state['task_description']}

### Technical Specification
{state.get('specification', 'N/A')[:2000]}

### Files Changed
"""
    
    for filename in state.get('code_files', {}).keys():
        body += f"- `{filename}`\n"
    
    body += "\n### Test Files\n"
    for filename in state.get('test_files', {}).keys():
        body += f"- `{filename}`\n"
    
    body += f"""
### Test Results
```
{state.get('test_results', 'N/A')[:1000]}
```

### Review Notes
{state.get('review_feedback', 'Approved by reviewer agent.')[:500]}

---
*This PR was automatically generated by the Autonomous Tech Lead system.*
"""
    
    return body

