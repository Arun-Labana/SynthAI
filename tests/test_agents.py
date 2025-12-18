"""
Unit tests for the agent implementations.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock

from backend.graph.state import AgentState, WorkflowStatus, create_initial_state


class TestAgentState:
    """Tests for AgentState creation and manipulation."""
    
    def test_create_initial_state(self):
        """Test creating an initial state."""
        state = create_initial_state(
            task_id="test-123",
            task_description="Build a feature",
            max_iterations=5
        )
        
        assert state["task_id"] == "test-123"
        assert state["task_description"] == "Build a feature"
        assert state["max_iterations"] == 5
        assert state["iteration_count"] == 0
        assert state["status"] == WorkflowStatus.PENDING
        assert state["code_files"] == {}
        assert state["test_files"] == {}
        assert state["messages"] == []
    
    def test_create_initial_state_with_repo_path(self):
        """Test creating state with repository path."""
        state = create_initial_state(
            task_id="test-456",
            task_description="Add authentication",
            target_repo_path="/path/to/repo"
        )
        
        assert state["target_repo_path"] == "/path/to/repo"
    
    def test_workflow_status_values(self):
        """Test all workflow status values exist."""
        expected_statuses = [
            "pending", "pm_processing", "dev_processing", 
            "qa_processing", "sandbox_running", "review_processing",
            "awaiting_approval", "approved", "rejected", "failed", "completed"
        ]
        
        for status in expected_statuses:
            assert hasattr(WorkflowStatus, status.upper())


class TestBaseAgent:
    """Tests for BaseAgent functionality."""
    
    @patch('backend.agents.base_agent.ChatAnthropic')
    @patch('backend.agents.base_agent.get_settings')
    def test_extract_code_blocks(self, mock_settings, mock_llm):
        """Test code block extraction from LLM response."""
        mock_settings.return_value = Mock(
            anthropic_api_key="test-key",
            llm_model="claude-sonnet-4-20250514"
        )
        
        from backend.agents.base_agent import BaseAgent
        
        # Create a concrete implementation for testing
        class TestAgent(BaseAgent):
            @property
            def system_prompt(self):
                return "Test prompt"
            
            def run(self, state):
                return state
        
        agent = TestAgent("Test")
        
        # Test code extraction
        response = '''Here's the code:

```main.py
def hello():
    return "world"
```

And another file:

```utils.py
def helper():
    pass
```
'''
        
        files = agent.extract_code_blocks(response)
        
        assert "main.py" in files
        assert "utils.py" in files
        assert 'def hello():' in files["main.py"]
    
    @patch('backend.agents.base_agent.ChatAnthropic')
    @patch('backend.agents.base_agent.get_settings')
    def test_create_message(self, mock_settings, mock_llm):
        """Test message creation."""
        mock_settings.return_value = Mock(
            anthropic_api_key="test-key",
            llm_model="claude-sonnet-4-20250514"
        )
        
        from backend.agents.base_agent import BaseAgent
        
        class TestAgent(BaseAgent):
            @property
            def system_prompt(self):
                return "Test prompt"
            
            def run(self, state):
                return state
        
        agent = TestAgent("Test Agent")
        message = agent.create_message("Test content")
        
        assert message["agent"] == "Test Agent"
        assert message["content"] == "Test content"
        assert "timestamp" in message


class TestPMAgent:
    """Tests for PM Agent."""
    
    @patch('backend.agents.pm_agent.BaseAgent.__init__')
    def test_build_prompt(self, mock_init):
        """Test prompt building."""
        mock_init.return_value = None
        
        from backend.agents.pm_agent import PMAgent
        
        agent = PMAgent()
        agent.name = "PM Agent"
        agent.settings = Mock()
        
        state = create_initial_state(
            task_id="test",
            task_description="Build user authentication"
        )
        
        prompt = agent._build_prompt(state)
        
        assert "Build user authentication" in prompt
        assert "Feature Request" in prompt


class TestQAAgent:
    """Tests for QA Agent."""
    
    @patch('backend.agents.qa_agent.BaseAgent.__init__')
    def test_create_basic_test_file(self, mock_init):
        """Test basic test file generation."""
        mock_init.return_value = None
        
        from backend.agents.qa_agent import QAAgent
        
        agent = QAAgent()
        agent.name = "QA Agent"
        
        state = create_initial_state(
            task_id="test",
            task_description="Build feature"
        )
        state["code_files"] = {"main.py": "def hello(): pass"}
        state["acceptance_criteria"] = ["Feature works correctly"]
        
        test_files = agent._create_basic_test_file(state)
        
        assert "test_basic.py" in test_files
        assert "pytest" in test_files["test_basic.py"]


class TestReviewerAgent:
    """Tests for Reviewer Agent."""
    
    @patch('backend.agents.reviewer_agent.BaseAgent.__init__')
    def test_build_feedback(self, mock_init):
        """Test feedback building."""
        mock_init.return_value = None
        
        from backend.agents.reviewer_agent import ReviewerAgent, ReviewOutput, ReviewDecision
        
        agent = ReviewerAgent()
        agent.name = "Reviewer Agent"
        
        review = ReviewOutput(
            decision=ReviewDecision.REVISE,
            confidence=0.8,
            summary="Tests are failing",
            issues_found=["Import error in line 5"],
            suggestions=["Fix the import statement"],
            tests_analysis="1 test failed"
        )
        
        feedback = agent._build_feedback(review)
        
        assert "Tests are failing" in feedback
        assert "Import error in line 5" in feedback
        assert "Fix the import statement" in feedback

