"""
Code Embedding module for the RAG pipeline.

Handles parsing code files, chunking them intelligently, and generating embeddings
for storage in ChromaDB.
"""

import os
import ast
import hashlib
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.embeddings import Embeddings

from backend.config import get_settings


def create_embeddings(settings) -> Embeddings:
    """
    Create embeddings instance based on configured provider.
    
    Supports:
    - ollama: Free, local embeddings (default)
    - openai: OpenAI embeddings (requires API key)
    """
    if settings.llm_provider == "ollama":
        from langchain_ollama import OllamaEmbeddings
        return OllamaEmbeddings(
            model=settings.embedding_model,
            base_url=settings.ollama_base_url,
        )
    else:
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=settings.embedding_model,
            api_key=settings.openai_api_key,
        )


@dataclass
class CodeChunk:
    """A chunk of code with metadata."""
    content: str
    file_path: str
    start_line: int
    end_line: int
    chunk_type: str  # 'function', 'class', 'module', 'block'
    name: Optional[str]  # Function/class name if applicable
    language: str
    hash: str  # For deduplication


# Supported file extensions and their languages
SUPPORTED_EXTENSIONS = {
    '.py': 'python',
    '.js': 'javascript',
    '.ts': 'typescript',
    '.jsx': 'javascript',
    '.tsx': 'typescript',
    '.java': 'java',
    '.go': 'go',
    '.rs': 'rust',
    '.cpp': 'cpp',
    '.c': 'c',
    '.rb': 'ruby',
    '.php': 'php',
}

# Directories to skip
SKIP_DIRS = {
    'node_modules', '__pycache__', '.git', '.venv', 'venv', 
    'env', '.env', 'dist', 'build', '.idea', '.vscode',
    'target', 'vendor', '.mypy_cache', '.pytest_cache',
}


class CodeEmbedder:
    """
    Handles code parsing, chunking, and embedding generation.
    
    Uses AST-based chunking for Python and falls back to text-based
    chunking for other languages.
    """
    
    def __init__(self):
        self.settings = get_settings()
        
        # Initialize embedding model based on provider
        self.embeddings = create_embeddings(self.settings)
        
        # Text splitter for non-AST chunking
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.settings.chunk_size,
            chunk_overlap=self.settings.chunk_overlap,
            separators=[
                "\nclass ",
                "\ndef ",
                "\n\ndef ",
                "\n\n",
                "\n",
                " ",
                "",
            ],
        )
    
    def process_repository(self, repo_path: str) -> List[CodeChunk]:
        """
        Process an entire repository and return code chunks.
        
        Args:
            repo_path: Path to the repository root
            
        Returns:
            List of CodeChunk objects ready for embedding
        """
        chunks = []
        repo_path = Path(repo_path)
        
        for file_path in self._walk_repository(repo_path):
            try:
                file_chunks = self.process_file(str(file_path))
                chunks.extend(file_chunks)
            except Exception as e:
                print(f"Warning: Failed to process {file_path}: {e}")
                continue
        
        return chunks
    
    def process_file(self, file_path: str) -> List[CodeChunk]:
        """
        Process a single file and return code chunks.
        
        Args:
            file_path: Path to the file
            
        Returns:
            List of CodeChunk objects
        """
        path = Path(file_path)
        extension = path.suffix.lower()
        
        if extension not in SUPPORTED_EXTENSIONS:
            return []
        
        language = SUPPORTED_EXTENSIONS[extension]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        except (UnicodeDecodeError, IOError):
            return []
        
        # Use AST-based chunking for Python
        if language == 'python':
            return self._chunk_python_ast(content, file_path)
        
        # Fall back to text-based chunking for other languages
        return self._chunk_text_based(content, file_path, language)
    
    def _walk_repository(self, repo_path: Path):
        """Walk repository and yield supported files."""
        for root, dirs, files in os.walk(repo_path):
            # Skip unwanted directories
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith('.')]
            
            for file in files:
                file_path = Path(root) / file
                if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                    yield file_path
    
    def _chunk_python_ast(self, content: str, file_path: str) -> List[CodeChunk]:
        """
        Chunk Python code using AST for semantic boundaries.
        
        Extracts functions and classes as individual chunks.
        """
        chunks = []
        lines = content.split('\n')
        
        try:
            tree = ast.parse(content)
        except SyntaxError:
            # Fall back to text-based chunking on syntax error
            return self._chunk_text_based(content, file_path, 'python')
        
        # Extract module-level docstring if present
        if (tree.body and 
            isinstance(tree.body[0], ast.Expr) and 
            isinstance(tree.body[0].value, ast.Constant) and
            isinstance(tree.body[0].value.value, str)):
            docstring = tree.body[0].value.value
            chunks.append(self._create_chunk(
                content=f'"""{docstring}"""',
                file_path=file_path,
                start_line=1,
                end_line=tree.body[0].end_lineno or 1,
                chunk_type='docstring',
                name='module_docstring',
                language='python',
            ))
        
        # Extract functions and classes
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                chunk_content = self._get_node_source(lines, node)
                chunks.append(self._create_chunk(
                    content=chunk_content,
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    chunk_type='function',
                    name=node.name,
                    language='python',
                ))
            
            elif isinstance(node, ast.ClassDef):
                chunk_content = self._get_node_source(lines, node)
                chunks.append(self._create_chunk(
                    content=chunk_content,
                    file_path=file_path,
                    start_line=node.lineno,
                    end_line=node.end_lineno or node.lineno,
                    chunk_type='class',
                    name=node.name,
                    language='python',
                ))
        
        # If no chunks extracted, treat whole file as one chunk
        if not chunks:
            chunks.append(self._create_chunk(
                content=content,
                file_path=file_path,
                start_line=1,
                end_line=len(lines),
                chunk_type='module',
                name=Path(file_path).stem,
                language='python',
            ))
        
        return chunks
    
    def _chunk_text_based(
        self, 
        content: str, 
        file_path: str, 
        language: str
    ) -> List[CodeChunk]:
        """
        Chunk code using text-based splitting.
        
        Used for non-Python languages or as fallback.
        """
        chunks = []
        lines = content.split('\n')
        
        # Use LangChain text splitter
        text_chunks = self.text_splitter.split_text(content)
        
        for i, chunk_content in enumerate(text_chunks):
            # Estimate line numbers (approximate)
            start_idx = content.find(chunk_content[:100])
            start_line = content[:start_idx].count('\n') + 1 if start_idx >= 0 else 1
            end_line = start_line + chunk_content.count('\n')
            
            chunks.append(self._create_chunk(
                content=chunk_content,
                file_path=file_path,
                start_line=start_line,
                end_line=end_line,
                chunk_type='block',
                name=f"chunk_{i}",
                language=language,
            ))
        
        return chunks
    
    def _get_node_source(self, lines: List[str], node: ast.AST) -> str:
        """Extract source code for an AST node."""
        start = node.lineno - 1  # Convert to 0-indexed
        end = node.end_lineno if node.end_lineno else start + 1
        return '\n'.join(lines[start:end])
    
    def _create_chunk(
        self,
        content: str,
        file_path: str,
        start_line: int,
        end_line: int,
        chunk_type: str,
        name: Optional[str],
        language: str,
    ) -> CodeChunk:
        """Create a CodeChunk with computed hash."""
        content_hash = hashlib.md5(content.encode()).hexdigest()[:12]
        
        return CodeChunk(
            content=content,
            file_path=file_path,
            start_line=start_line,
            end_line=end_line,
            chunk_type=chunk_type,
            name=name,
            language=language,
            hash=content_hash,
        )
    
    def generate_embeddings(self, chunks: List[CodeChunk]) -> List[Tuple[CodeChunk, List[float]]]:
        """
        Generate embeddings for a list of code chunks.
        
        Args:
            chunks: List of CodeChunk objects
            
        Returns:
            List of (chunk, embedding) tuples
        """
        if not chunks:
            return []
        
        # Prepare texts for embedding (include metadata context)
        texts = []
        for chunk in chunks:
            # Create a rich text representation for embedding
            context = f"File: {chunk.file_path}\n"
            context += f"Type: {chunk.chunk_type}\n"
            if chunk.name:
                context += f"Name: {chunk.name}\n"
            context += f"Language: {chunk.language}\n"
            context += f"---\n{chunk.content}"
            texts.append(context)
        
        # Generate embeddings in batches
        embeddings = self.embeddings.embed_documents(texts)
        
        return list(zip(chunks, embeddings))

