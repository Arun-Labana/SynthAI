"""
Configuration management using Pydantic Settings.
Loads from environment variables and .env file.
"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # LLM Provider: "ollama" (free, local) or "anthropic" (paid, cloud)
    llm_provider: str = Field("ollama", description="LLM provider: 'ollama' or 'anthropic'")
    
    # API Keys (only needed if using cloud providers)
    anthropic_api_key: Optional[str] = Field(None, description="Anthropic API key for Claude")
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key for embeddings")
    github_token: Optional[str] = Field(None, description="GitHub personal access token")
    
    # Model Configuration
    llm_model: str = Field("llama3.1", description="Model to use (llama3.1 for Ollama, claude-sonnet-4-20250514 for Anthropic)")
    embedding_model: str = Field("nomic-embed-text", description="Embedding model")
    
    # Ollama Configuration
    ollama_base_url: str = Field("http://localhost:11434", description="Ollama server URL")
    
    # Sandbox Configuration
    sandbox_timeout: int = Field(60, description="Docker container timeout in seconds")
    sandbox_memory_limit: str = Field("512m", description="Docker memory limit")
    sandbox_cpu_limit: float = Field(1.0, description="Docker CPU limit")
    sandbox_network_disabled: bool = Field(True, description="Disable network in sandbox")
    
    # Workflow Configuration
    max_iterations: int = Field(3, description="Max dev-review iterations before human intervention")
    
    # ChromaDB Configuration
    chroma_persist_directory: str = Field("./chroma_db", description="ChromaDB persistence path")
    chroma_collection_name: str = Field("codebase", description="ChromaDB collection name")
    
    # GitHub Configuration
    github_owner: Optional[str] = Field(None, description="GitHub repository owner")
    github_repo: Optional[str] = Field(None, description="GitHub repository name")
    github_base_branch: str = Field("main", description="Base branch for PRs")
    
    # Server Configuration
    api_host: str = Field("0.0.0.0", description="API server host")
    api_port: int = Field(8000, description="API server port")
    
    # RAG Configuration
    chunk_size: int = Field(1000, description="Code chunk size for embedding")
    chunk_overlap: int = Field(200, description="Chunk overlap for embedding")
    retrieval_k: int = Field(5, description="Number of chunks to retrieve")
    
    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

