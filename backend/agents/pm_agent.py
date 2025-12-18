"""
PM (Product Manager) Agent - Transforms task descriptions into technical specifications.

This agent acts as the first node in the workflow, taking raw user requirements
and producing structured specifications that the Dev Agent can implement.
"""

from typing import List, Dict
from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent
from backend.graph.state import AgentState, WorkflowStatus


class TaskBreakdown(BaseModel):
    """A single task in the breakdown."""
    id: str = Field(description="Task ID")
    title: str = Field(description="Task title")
    description: str = Field(description="What to do")


class PMAgentOutput(BaseModel):
    """Structured output from the PM Agent."""
    technical_specification: str = Field(description="What to build")
    task_breakdown: List[TaskBreakdown] = Field(description="Tasks")
    acceptance_criteria: List[str] = Field(description="Done criteria")
    technical_notes: List[str] = Field(description="Tech notes")


class PMAgent(BaseAgent):
    """
    Product Manager Agent that creates technical specifications from requirements.
    
    Input: Raw task description from user
    Output: Technical specification, task breakdown, and acceptance criteria
    """
    
    def __init__(self):
        super().__init__(name="PM Agent")
    
    @property
    def system_prompt(self) -> str:
        return "You are a technical product manager. You create specs for developers."

    def run(self, state: AgentState) -> AgentState:
        """
        Process the task description and generate technical specification.
        
        Args:
            state: Current workflow state with task_description
            
        Returns:
            Updated state with specification, task_breakdown, and acceptance_criteria
        """
        # Build the user prompt
        user_prompt = self._build_prompt(state)
        
        # Get structured output from LLM
        output = self.invoke_llm_structured(user_prompt, PMAgentOutput)
        
        # Convert task breakdown to list of dicts
        task_breakdown = [
            {
                "id": task.id,
                "title": task.title,
                "description": task.description,
            }
            for task in output.task_breakdown
        ]
        
        # Build the full specification markdown
        specification = output.technical_specification
        
        # Return updated state
        return {
            "specification": specification,
            "task_breakdown": task_breakdown,
            "acceptance_criteria": output.acceptance_criteria,
            "status": WorkflowStatus.DEV_PROCESSING,
            "messages": self.log_to_state(
                state, 
                f"Generated technical specification with {len(task_breakdown)} tasks and {len(output.acceptance_criteria)} acceptance criteria."
            ),
        }
    
    def _build_prompt(self, state: AgentState) -> str:
        """Build the user prompt for the LLM."""
        return f"""Task: {state['task_description']}

Create a spec. Return JSON only:
{{"technical_specification": "description of what to build", "task_breakdown": [{{"id": "task-1", "title": "task name", "description": "what to do"}}], "acceptance_criteria": ["criterion 1"], "technical_notes": ["note 1"]}}"""

