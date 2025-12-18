"""
Code Retriever module for RAG-based code context.

Manages ChromaDB storage and retrieval of code embeddings.
"""

import os
from typing import List, Dict, Optional
from dataclasses import asdict

import chromadb
from chromadb.config import Settings as ChromaSettings

from backend.config import get_settings
from backend.rag.embeddings import CodeEmbedder, CodeChunk


class CodeRetriever:
    """
    Manages code embeddings in ChromaDB and provides retrieval functionality.
    
    This class handles:
    - Initializing/connecting to ChromaDB
    - Indexing code repositories
    - Retrieving relevant code context for queries
    """
    
    def __init__(self):
        self.settings = get_settings()
        self.embedder = CodeEmbedder()
        
        # Ensure persist directory exists
        os.makedirs(self.settings.chroma_persist_directory, exist_ok=True)
        
        # Initialize ChromaDB client with persistence
        self.client = chromadb.PersistentClient(
            path=self.settings.chroma_persist_directory,
            settings=ChromaSettings(
                anonymized_telemetry=False,
            ),
        )
        
        # Get or create the collection
        self.collection = self.client.get_or_create_collection(
            name=self.settings.chroma_collection_name,
            metadata={"hnsw:space": "cosine"},  # Use cosine similarity
        )
    
    def index_repository(self, repo_path: str, clear_existing: bool = False) -> int:
        """
        Index a repository's code into ChromaDB.
        
        Args:
            repo_path: Path to the repository to index
            clear_existing: Whether to clear existing embeddings first
            
        Returns:
            Number of chunks indexed
        """
        if clear_existing:
            # Delete all documents in the collection
            self._clear_collection()
        
        # Process repository into chunks
        chunks = self.embedder.process_repository(repo_path)
        
        if not chunks:
            return 0
        
        # Generate embeddings
        chunk_embeddings = self.embedder.generate_embeddings(chunks)
        
        # Prepare data for ChromaDB
        ids = []
        embeddings = []
        documents = []
        metadatas = []
        
        for chunk, embedding in chunk_embeddings:
            # Create unique ID from file path and hash
            chunk_id = f"{chunk.file_path}:{chunk.start_line}:{chunk.hash}"
            
            ids.append(chunk_id)
            embeddings.append(embedding)
            documents.append(chunk.content)
            metadatas.append({
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "chunk_type": chunk.chunk_type,
                "name": chunk.name or "",
                "language": chunk.language,
            })
        
        # Add to ChromaDB in batches
        batch_size = 100
        for i in range(0, len(ids), batch_size):
            end_idx = min(i + batch_size, len(ids))
            self.collection.add(
                ids=ids[i:end_idx],
                embeddings=embeddings[i:end_idx],
                documents=documents[i:end_idx],
                metadatas=metadatas[i:end_idx],
            )
        
        return len(ids)
    
    def retrieve(
        self, 
        query: str, 
        k: Optional[int] = None,
        filter_language: Optional[str] = None,
        filter_type: Optional[str] = None,
    ) -> List[Dict]:
        """
        Retrieve relevant code chunks for a query.
        
        Args:
            query: Natural language query or code snippet
            k: Number of results to return (default from settings)
            filter_language: Optional language filter (e.g., 'python')
            filter_type: Optional chunk type filter (e.g., 'function', 'class')
            
        Returns:
            List of relevant code chunks with metadata
        """
        k = k or self.settings.retrieval_k
        
        # Build where filter if needed
        where_filter = None
        if filter_language or filter_type:
            conditions = []
            if filter_language:
                conditions.append({"language": filter_language})
            if filter_type:
                conditions.append({"chunk_type": filter_type})
            
            if len(conditions) == 1:
                where_filter = conditions[0]
            else:
                where_filter = {"$and": conditions}
        
        # Generate query embedding
        query_embedding = self.embedder.embeddings.embed_query(query)
        
        # Query ChromaDB
        results = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=k,
            where=where_filter,
            include=["documents", "metadatas", "distances"],
        )
        
        # Format results
        formatted_results = []
        if results['ids'] and results['ids'][0]:
            for i, doc_id in enumerate(results['ids'][0]):
                formatted_results.append({
                    "id": doc_id,
                    "content": results['documents'][0][i],
                    "metadata": results['metadatas'][0][i],
                    "similarity": 1 - results['distances'][0][i],  # Convert distance to similarity
                })
        
        return formatted_results
    
    def retrieve_for_task(
        self, 
        task_description: str,
        specification: Optional[str] = None,
        k: Optional[int] = None,
    ) -> str:
        """
        Retrieve and format relevant code context for a development task.
        
        Args:
            task_description: The task to work on
            specification: Optional technical specification for additional context
            k: Number of chunks to retrieve
            
        Returns:
            Formatted string of relevant code context
        """
        # Combine task and spec for richer query
        query = task_description
        if specification:
            query = f"{task_description}\n\nSpecification:\n{specification[:500]}"
        
        results = self.retrieve(query, k=k)
        
        if not results:
            return "No existing code context found."
        
        # Format results for the LLM
        context = "## Relevant Code from Repository\n\n"
        
        for result in results:
            metadata = result['metadata']
            context += f"### {metadata['file_path']}"
            if metadata.get('name'):
                context += f" - {metadata['name']}"
            context += f" ({metadata['chunk_type']})\n"
            context += f"Lines {metadata['start_line']}-{metadata['end_line']}\n"
            context += f"```{metadata['language']}\n{result['content']}\n```\n\n"
        
        return context
    
    def get_collection_stats(self) -> Dict:
        """Get statistics about the indexed collection."""
        count = self.collection.count()
        
        return {
            "total_chunks": count,
            "collection_name": self.settings.chroma_collection_name,
            "persist_directory": self.settings.chroma_persist_directory,
        }
    
    def _clear_collection(self):
        """Clear all documents from the collection."""
        # Get all IDs and delete them
        all_ids = self.collection.get()['ids']
        if all_ids:
            self.collection.delete(ids=all_ids)
    
    def delete_file(self, file_path: str):
        """
        Remove all chunks from a specific file.
        
        Useful for incremental updates when a file changes.
        """
        # Get all chunks from this file
        results = self.collection.get(
            where={"file_path": file_path},
        )
        
        if results['ids']:
            self.collection.delete(ids=results['ids'])
    
    def update_file(self, file_path: str):
        """
        Update embeddings for a single file.
        
        Removes existing chunks and re-indexes the file.
        """
        # Remove old chunks
        self.delete_file(file_path)
        
        # Re-process and index the file
        chunks = self.embedder.process_file(file_path)
        
        if not chunks:
            return 0
        
        # Generate embeddings
        chunk_embeddings = self.embedder.generate_embeddings(chunks)
        
        # Add to ChromaDB
        ids = []
        embeddings = []
        documents = []
        metadatas = []
        
        for chunk, embedding in chunk_embeddings:
            chunk_id = f"{chunk.file_path}:{chunk.start_line}:{chunk.hash}"
            
            ids.append(chunk_id)
            embeddings.append(embedding)
            documents.append(chunk.content)
            metadatas.append({
                "file_path": chunk.file_path,
                "start_line": chunk.start_line,
                "end_line": chunk.end_line,
                "chunk_type": chunk.chunk_type,
                "name": chunk.name or "",
                "language": chunk.language,
            })
        
        self.collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=documents,
            metadatas=metadatas,
        )
        
        return len(ids)

