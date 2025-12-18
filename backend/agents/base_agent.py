"""
Base Agent class that all specialized agents inherit from.
Provides common LLM setup, structured output parsing, and utilities.
"""

from abc import ABC, abstractmethod
from typing import Type, TypeVar, Optional, Any
from datetime import datetime
import json

from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.language_models import BaseChatModel
from pydantic import BaseModel

from backend.config import get_settings
from backend.graph.state import AgentState, AgentMessage

T = TypeVar("T", bound=BaseModel)


def create_llm(settings) -> BaseChatModel:
    """
    Create LLM instance based on configured provider.
    
    Supports:
    - ollama: Free, local models (default)
    - anthropic: Claude (requires API key)
    """
    if settings.llm_provider == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.llm_model,
            base_url=settings.ollama_base_url,
            temperature=0.2,
            timeout=120,  # 2 minute timeout
        )
    elif settings.llm_provider == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=settings.llm_model,
            api_key=settings.anthropic_api_key,
            max_tokens=8192,
            temperature=0.2,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    
    Provides:
    - LLM initialization (Ollama or Anthropic)
    - Structured output parsing
    - Retry logic with exponential backoff
    - Message logging to state
    """
    
    def __init__(self, name: str):
        """
        Initialize the agent with LLM setup.
        
        Args:
            name: Human-readable name for this agent (e.g., "PM Agent")
        """
        self.name = name
        self.settings = get_settings()
        
        # Initialize LLM based on provider
        self.llm = create_llm(self.settings)
    
    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """Return the system prompt for this agent."""
        pass
    
    @abstractmethod
    def run(self, state: AgentState) -> AgentState:
        """
        Execute the agent's task and return updated state.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        pass
    
    def invoke_llm(self, user_prompt: str) -> str:
        """
        Invoke the LLM with system and user prompts.
        """
        print(f"\n[{self.name}] Calling LLM...")
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt),
        ]
        
        response = self.llm.invoke(messages)
        print(f"[{self.name}] ✅ Response received ({len(response.content)} chars)")
        return response.content
    
    def invoke_llm_structured(
        self, 
        user_prompt: str, 
        output_schema: Type[T],
        max_retries: int = 2
    ) -> T:
        """
        Invoke the LLM and parse output into a Pydantic model.
        The user_prompt should already contain the example JSON format.
        """
        print(f"\n[{self.name}] Calling LLM...")
        
        messages = [
            SystemMessage(content=self.system_prompt),
            HumanMessage(content=user_prompt),
        ]
        
        last_error = None
        
        for attempt in range(max_retries + 1):
            try:
                response = self.llm.invoke(messages)
                content = response.content
                
                print(f"[{self.name}] Response: {content[:200]}...")
                
                # Try to extract JSON from the response
                extracted_json = self._extract_and_parse_json(content, output_schema)
                if extracted_json:
                    print(f"[{self.name}] ✅ Parsed successfully")
                    return extracted_json
                
                raise ValueError("Could not parse JSON")
                
            except Exception as e:
                print(f"[{self.name}] Attempt {attempt + 1} failed: {str(e)[:50]}")
                last_error = e
                if attempt < max_retries:
                    messages.append(HumanMessage(content="Return ONLY valid JSON, nothing else."))
                    continue
        
        raise ValueError(f"Failed to get structured output after {max_retries + 1} attempts. Last error: {last_error}")
    
    def _extract_and_parse_json(self, text: str, output_schema: Type[T]) -> Optional[T]:
        """
        Try multiple strategies to extract and parse JSON from LLM response.
        """
        import re
        
        strategies = [
            # Strategy 1: Find JSON in code blocks
            lambda t: re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', t),
            # Strategy 2: Find object starting with {
            lambda t: re.search(r'(\{[\s\S]*\})', t),
        ]
        
        for strategy in strategies:
            match = strategy(text)
            if match:
                try:
                    json_str = match.group(1) if hasattr(match, 'group') else match
                    data = json.loads(json_str)
                    return output_schema.model_validate(data)
                except (json.JSONDecodeError, Exception):
                    continue
        
        return None
    
    def create_message(self, content: str) -> AgentMessage:
        """
        Create a timestamped message from this agent.
        
        Args:
            content: Message content
            
        Returns:
            AgentMessage dict
        """
        return AgentMessage(
            agent=self.name,
            content=content,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_to_state(self, state: AgentState, message: str) -> list:
        """
        Create a message list to append to state.
        
        Args:
            state: Current state (unused but kept for consistency)
            message: Message to log
            
        Returns:
            List containing the new message (for Annotated append)
        """
        return [self.create_message(message)]
    
    def extract_code_blocks(self, text: str) -> dict[str, str]:
        """
        Extract code blocks from LLM response.
        
        Expects format:
        ```filename.py
        code content
        ```
        
        Args:
            text: LLM response containing code blocks
            
        Returns:
            Dict of {filename: code_content}
        """
        import re
        
        code_files = {}
        
        # Pattern to match ```filename.ext\ncode\n```
        pattern = r'```(\S+)\n(.*?)```'
        matches = re.findall(pattern, text, re.DOTALL)
        
        for filename, code in matches:
            # Clean up the filename (remove language hints if present)
            if '.' not in filename:
                # It's probably just a language hint like "python", skip
                continue
            code_files[filename.strip()] = code.strip()
        
        return code_files
    
    def extract_json_from_response(self, text: str) -> Optional[Any]:
        """
        Extract JSON from LLM response, handling markdown code blocks.
        
        Args:
            text: LLM response that may contain JSON
            
        Returns:
            Parsed JSON or None if not found
        """
        import re
        
        # Try to find JSON in code blocks first
        json_pattern = r'```(?:json)?\n(.*?)```'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                return json.loads(match.strip())
            except json.JSONDecodeError:
                continue
        
        # Try parsing the whole text as JSON
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

