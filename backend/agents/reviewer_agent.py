"""
Reviewer Agent - Reviews code execution results and makes pass/fail decisions.

This agent acts as the decision point in the workflow, determining whether
code should be sent for human approval or back to the Dev Agent for fixes.
"""

from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent
from backend.graph.state import AgentState, WorkflowStatus


class ReviewOutput(BaseModel):
    """Structured output from the Reviewer Agent."""
    decision: str = Field(description="approve, revise, or fail")
    summary: str = Field(description="Brief summary")
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


class ReviewerAgent(BaseAgent):
    """
    Reviewer Agent that evaluates code execution results.
    
    Input: Execution logs, test results, and original specification
    Output: Decision (approve/revise/fail) with feedback
    """
    
    def __init__(self):
        super().__init__(name="Reviewer Agent")
    
    @property
    def system_prompt(self) -> str:
        return "You are a code reviewer. You review test results and decide: approve, revise, or fail."

    def run(self, state: AgentState) -> AgentState:
        """Review the execution results and make a decision."""
        user_prompt = self._build_prompt(state)
        review = self.invoke_llm_structured(user_prompt, ReviewOutput)
        
        iteration = state.get('iteration_count', 0)
        max_iterations = state.get('max_iterations', 3)
        
        # Normalize decision
        decision = review.decision.lower().strip()
        
        if decision == "approve":
            new_status = WorkflowStatus.AWAITING_APPROVAL
            is_tests_passing = True
            message = f"✅ Approved: {review.summary}"
        elif decision == "revise":
            if iteration >= max_iterations:
                new_status = WorkflowStatus.AWAITING_APPROVAL
                message = f"⚠️ Max iterations reached: {review.summary}"
            else:
                new_status = WorkflowStatus.DEV_PROCESSING
                message = f"🔄 Revision needed: {review.summary}"
            is_tests_passing = False
        else:
            new_status = WorkflowStatus.FAILED
            is_tests_passing = False
            message = f"❌ Failed: {review.summary}"
        
        feedback = f"Summary: {review.summary}\nIssues: {review.issues}\nSuggestions: {review.suggestions}"
        
        updates = {
            "review_feedback": feedback,
            "is_tests_passing": is_tests_passing,
            "status": new_status,
            "messages": self.log_to_state(state, message),
        }
        
        if new_status == WorkflowStatus.DEV_PROCESSING:
            updates["iteration_count"] = iteration + 1
        
        return updates
    
    def _build_prompt(self, state: AgentState) -> str:
        """Build the review prompt."""
        exit_code = state.get('exit_code', 'N/A')
        logs = state.get('execution_logs', 'No output')[:1000]
        
        return f"""Task: {state['task_description']}
Exit code: {exit_code}
Output: {logs}

Review and return JSON only:
{{"decision": "approve", "summary": "all tests pass", "issues": [], "suggestions": []}}

OR if tests failed:
{{"decision": "revise", "summary": "tests failed", "issues": ["issue 1"], "suggestions": ["fix 1"]}}"""
    

