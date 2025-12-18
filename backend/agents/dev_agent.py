"""
Dev Agent - Generates code implementations based on specifications.

This agent uses RAG to understand the existing codebase and generates
code that fits with existing patterns and conventions.
"""

from typing import Dict, Optional
from pydantic import BaseModel, Field

from backend.agents.base_agent import BaseAgent
from backend.graph.state import AgentState, WorkflowStatus
from backend.rag.retriever import CodeRetriever


class DevAgentOutput(BaseModel):
    """Structured output from the Dev Agent."""
    implementation_notes: str = Field(
        description="Brief notes about the implementation approach"
    )
    files_created: list[str] = Field(
        description="List of files that were created or modified"
    )


class DevAgent(BaseAgent):
    """
    Developer Agent that generates code implementations.
    
    Input: Technical specification + codebase context from RAG
    Output: Dictionary of {filename: code_content}
    """
    
    def __init__(self, retriever: Optional[CodeRetriever] = None):
        """
        Initialize the Dev Agent.
        
        Args:
            retriever: Optional CodeRetriever for RAG context. If not provided,
                      will be created on first use if a target repo is specified.
        """
        super().__init__(name="Dev Agent")
        self._retriever = retriever
    
    @property
    def retriever(self) -> Optional[CodeRetriever]:
        """Lazy initialization of retriever."""
        if self._retriever is None:
            try:
                self._retriever = CodeRetriever()
            except Exception:
                # RAG is optional - continue without it
                pass
        return self._retriever
    
    @property
    def system_prompt(self) -> str:
        return """You are an expert Senior Software Engineer with extensive experience in multiple programming languages and frameworks.

Your role is to implement features based on technical specifications, writing clean, maintainable, and well-documented code.

Guidelines for code generation:
1. **Follow the specification exactly** - Don't add features that weren't requested
2. **Match existing patterns** - If provided with codebase context, follow the existing code style and conventions
3. **Write complete, runnable code** - No placeholders or TODOs unless absolutely necessary
4. **Include proper error handling** - Handle edge cases and errors gracefully
5. **Add docstrings and comments** - Document your code clearly
6. **Use type hints** - Add type annotations for better code quality
7. **Keep it simple** - Prefer simple, readable solutions over clever ones

Code output format:
- Provide each file in a separate code block
- Use the filename as the code block language identifier
- Example:
```main.py
# code here
```

If you're fixing code based on review feedback:
- Focus on the specific issues mentioned
- Don't refactor unrelated parts
- Explain what you changed and why

Remember: Quality over quantity. Write code you'd be proud to have reviewed."""

    def run(self, state: AgentState) -> AgentState:
        """
        Generate code implementation based on specification.
        
        Args:
            state: Current workflow state with specification
            
        Returns:
            Updated state with code_files
        """
        # Get RAG context if repository is specified
        rag_context = self._get_rag_context(state)
        
        # Build the prompt
        user_prompt = self._build_prompt(state, rag_context)
        
        # Get LLM response
        response = self.invoke_llm(user_prompt)
        
        # Extract code files from response
        code_files = self.extract_code_blocks(response)
        
        # If no code files extracted, try alternative parsing
        if not code_files:
            code_files = self._extract_code_alternative(response)
        
        # Merge with existing code files if this is an iteration
        existing_files = state.get('code_files', {})
        if existing_files and state.get('iteration_count', 0) > 0:
            # Update existing files with new ones
            merged_files = {**existing_files, **code_files}
            code_files = merged_files
        
        # Determine message based on whether this is first attempt or revision
        iteration = state.get('iteration_count', 0)
        if iteration == 0:
            message = f"Generated initial implementation with {len(code_files)} file(s): {', '.join(code_files.keys())}"
        else:
            message = f"Revision #{iteration}: Updated implementation based on review feedback."
        
        return {
            "code_files": code_files,
            "status": WorkflowStatus.QA_PROCESSING,
            "messages": self.log_to_state(state, message),
        }
    
    def _get_rag_context(self, state: AgentState) -> str:
        """Retrieve relevant code context from the repository."""
        if not state.get('target_repo_path'):
            return ""
        
        if not self.retriever:
            return ""
        
        try:
            # Check if repository is indexed
            stats = self.retriever.get_collection_stats()
            if stats['total_chunks'] == 0:
                # Index the repository first
                self.retriever.index_repository(state['target_repo_path'])
            
            # Retrieve relevant context
            return self.retriever.retrieve_for_task(
                task_description=state['task_description'],
                specification=state.get('specification'),
            )
        except Exception as e:
            return f"(RAG context unavailable: {e})"
    
    def _build_prompt(self, state: AgentState, rag_context: str) -> str:
        """Build the prompt for code generation."""
        iteration = state.get('iteration_count', 0)
        
        prompt = f"""Please implement the following feature based on the technical specification.

## Task Description
{state['task_description']}

## Technical Specification
{state.get('specification', 'No specification provided - implement based on task description.')}

"""
        
        # Add acceptance criteria
        criteria = state.get('acceptance_criteria', [])
        if criteria:
            prompt += "## Acceptance Criteria\n"
            for i, criterion in enumerate(criteria, 1):
                prompt += f"{i}. {criterion}\n"
            prompt += "\n"
        
        # Add RAG context if available
        if rag_context and "unavailable" not in rag_context.lower():
            prompt += f"""## Existing Codebase Context
The following code snippets are from the existing codebase. Please follow similar patterns and conventions:

{rag_context}

"""
        
        # If this is a revision, add the feedback
        if iteration > 0:
            prompt += f"""## Revision Required (Iteration #{iteration})

The previous implementation failed testing. Please fix the issues based on the following feedback:

### Review Feedback
{state.get('review_feedback', 'No specific feedback provided.')}

### Test Results
{state.get('test_results', 'No test results available.')}

### Previous Implementation
"""
            existing_files = state.get('code_files', {})
            for filename, content in existing_files.items():
                prompt += f"```{filename}\n{content}\n```\n\n"
            
            prompt += """
Please provide the corrected implementation. Focus on fixing the specific issues mentioned.
"""
        else:
            prompt += """
## Output Requirements
Please provide complete, runnable code files. Format each file as:
```filename.py
# complete code here
```

Make sure to:
1. Include all necessary imports
2. Add proper error handling
3. Include docstrings and type hints
4. Follow PEP 8 style guidelines (for Python)
"""
        
        return prompt
    
    def _extract_code_alternative(self, response: str) -> Dict[str, str]:
        """
        Alternative code extraction for when standard parsing fails.
        
        Handles various LLM response formats.
        """
        import re
        
        files = {}
        
        # Try pattern: ### filename.py followed by code block
        pattern = r'###?\s*`?(\w+\.py)`?\s*\n```(?:python)?\n(.*?)```'
        matches = re.findall(pattern, response, re.DOTALL)
        
        for filename, code in matches:
            files[filename] = code.strip()
        
        # Try pattern: **filename.py** followed by code block
        if not files:
            pattern = r'\*\*(\w+\.py)\*\*\s*\n```(?:python)?\n(.*?)```'
            matches = re.findall(pattern, response, re.DOTALL)
            
            for filename, code in matches:
                files[filename] = code.strip()
        
        # Last resort: any python code block becomes main.py
        if not files:
            pattern = r'```python\n(.*?)```'
            matches = re.findall(pattern, response, re.DOTALL)
            
            if matches:
                # Combine all python blocks
                combined = "\n\n".join(match.strip() for match in matches)
                files["main.py"] = combined
        
        return files

