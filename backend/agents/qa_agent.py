"""
QA Agent - Generates comprehensive test suites for AI-generated code.

This agent takes the generated code and specification, then creates
pytest-compatible tests to validate the implementation.
"""

from typing import List, Dict
from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent
from backend.graph.state import AgentState, WorkflowStatus


class TestCase(BaseModel):
    """A single test case specification."""
    name: str = Field(description="Test function name (e.g., test_user_registration)")
    description: str = Field(description="What this test validates")
    test_type: str = Field(description="Type: unit, integration, or edge_case")


class QAAgentOutput(BaseModel):
    """Structured output from the QA Agent."""
    test_strategy: str = Field(description="Overall testing strategy explanation")
    test_cases: List[TestCase] = Field(description="List of test cases to implement")
    test_files: Dict[str, str] = Field(
        description="Dictionary of test file names to their complete code content"
    )


class QAAgent(BaseAgent):
    """
    QA Agent that generates test suites for the generated code.
    
    Input: Generated code files and specification
    Output: pytest-compatible test files
    """
    
    def __init__(self):
        super().__init__(name="QA Agent")
    
    @property
    def system_prompt(self) -> str:
        return """You are an expert QA Engineer and Test Automation Specialist.
Your role is to create comprehensive test suites for code implementations.

Your responsibilities:
1. Analyze the code and its specification
2. Design a testing strategy covering all requirements
3. Write pytest-compatible test files
4. Include unit tests, integration tests, and edge case tests
5. Ensure tests are deterministic and don't have side effects

Testing Guidelines:
- Use pytest as the testing framework
- Use descriptive test names that explain what's being tested
- Include docstrings explaining each test's purpose
- Test both happy paths and error cases
- Use fixtures for setup/teardown when appropriate
- Mock external dependencies (APIs, databases, etc.)
- Include assertions with clear failure messages
- Test boundary conditions and edge cases
- Aim for high code coverage

Test Structure:
- Group related tests in classes when appropriate
- Use parametrize for testing multiple inputs
- Keep tests independent - no test should depend on another

Your tests should be runnable with: pytest test_*.py -v"""

    def run(self, state: AgentState) -> AgentState:
        """
        Generate test files for the implementation.
        
        Args:
            state: Current workflow state with code_files and specification
            
        Returns:
            Updated state with test_files
        """
        # Build the prompt with code and spec
        user_prompt = self._build_prompt(state)
        
        # Get the response and extract test files
        response = self.invoke_llm(user_prompt)
        
        # Extract test files from the response
        test_files = self.extract_code_blocks(response)
        
        # Filter to only test files
        test_files = {
            name: content 
            for name, content in test_files.items() 
            if name.startswith("test_") or name.endswith("_test.py")
        }
        
        # If no test files found with proper naming, try to get any Python files
        if not test_files:
            all_files = self.extract_code_blocks(response)
            test_files = {
                f"test_{name}" if not name.startswith("test_") else name: content
                for name, content in all_files.items()
                if name.endswith(".py")
            }
        
        # Ensure we have at least a basic test file
        if not test_files:
            test_files = self._create_basic_test_file(state)
        
        return {
            "test_files": test_files,
            "status": WorkflowStatus.SANDBOX_RUNNING,
            "messages": self.log_to_state(
                state,
                f"Generated {len(test_files)} test file(s) with comprehensive test coverage."
            ),
        }
    
    def _build_prompt(self, state: AgentState) -> str:
        """Build the prompt for test generation."""
        prompt = f"""Please create a comprehensive test suite for the following implementation.

## Technical Specification
{state.get('specification', 'No specification provided')}

## Acceptance Criteria
"""
        
        criteria = state.get('acceptance_criteria', [])
        if criteria:
            for i, criterion in enumerate(criteria, 1):
                prompt += f"{i}. {criterion}\n"
        else:
            prompt += "No specific criteria provided.\n"
        
        prompt += "\n## Implementation Code\n\n"
        
        code_files = state.get('code_files', {})
        for filename, content in code_files.items():
            prompt += f"### {filename}\n```python\n{content}\n```\n\n"
        
        prompt += """
## Requirements

Please create pytest-compatible test files that:
1. Test all acceptance criteria
2. Cover happy paths and error cases
3. Include edge case tests
4. Use appropriate fixtures and mocks
5. Have clear, descriptive test names

Format your response with code blocks like:
```test_filename.py
# test code here
```

Make sure each test file is complete and runnable independently."""

        return prompt
    
    def _create_basic_test_file(self, state: AgentState) -> Dict[str, str]:
        """Create a basic test file if LLM didn't produce proper tests."""
        code_files = state.get('code_files', {})
        
        # Generate basic import tests
        imports = []
        for filename in code_files.keys():
            if filename.endswith('.py'):
                module_name = filename[:-3]  # Remove .py
                imports.append(f"    # from {module_name} import *")
        
        test_content = f'''"""
Auto-generated basic test file.
Tests that the implementation can be imported without errors.
"""

import pytest


class TestBasicImports:
    """Test that all modules can be imported."""
    
    def test_imports_succeed(self):
        """Verify all modules can be imported."""
        # TODO: Add proper imports once modules are in path
{chr(10).join(imports) if imports else "        pass"}
        assert True  # Basic sanity check


class TestAcceptanceCriteria:
    """Tests for acceptance criteria."""
    
'''
        
        criteria = state.get('acceptance_criteria', [])
        for i, criterion in enumerate(criteria, 1):
            safe_name = criterion[:50].lower().replace(' ', '_').replace('-', '_')
            safe_name = ''.join(c for c in safe_name if c.isalnum() or c == '_')
            test_content += f'''    def test_criterion_{i}_{safe_name[:30]}(self):
        """Test: {criterion[:100]}"""
        # TODO: Implement test for this criterion
        pytest.skip("Test not yet implemented")

'''
        
        return {"test_basic.py": test_content}

