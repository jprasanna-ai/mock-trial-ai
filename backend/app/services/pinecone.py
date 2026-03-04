"""
Pinecone Client Wrapper

Per README.md:
- Pinecone for case data, memory

Provides CRUD operations for namespaces:
- case_facts: Case materials, evidence, legal standards
- witness_memory_<id>: Per-witness memory and affidavit data
- transcript: Trial transcript for retrieval
- prep_notes: Preparation notes and strategy

No trial logic - this is a data access layer only.
"""

import os
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
from enum import Enum

from pinecone import Pinecone, ServerlessSpec


# =============================================================================
# NAMESPACE CONFIGURATION
# =============================================================================

class Namespace(str, Enum):
    """Standard namespaces for the mock trial system."""
    CASE_FACTS = "case_facts"
    TRANSCRIPT = "transcript"
    PREP_NOTES = "prep_notes"
    # witness_memory_<id> is dynamic, use get_witness_namespace()


def get_witness_namespace(witness_id: str) -> str:
    """Get namespace for a specific witness's memory."""
    return f"witness_memory_{witness_id}"


# =============================================================================
# VECTOR RECORD
# =============================================================================

@dataclass
class VectorRecord:
    """A record stored in Pinecone."""
    id: str
    values: List[float]
    metadata: Dict[str, Any]
    score: Optional[float] = None  # Populated on query results
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for upsert."""
        return {
            "id": self.id,
            "values": self.values,
            "metadata": self.metadata,
        }
    
    @classmethod
    def from_match(cls, match: Any) -> "VectorRecord":
        """Create from Pinecone query match."""
        return cls(
            id=match.id,
            values=match.values if hasattr(match, 'values') else [],
            metadata=match.metadata if hasattr(match, 'metadata') else {},
            score=match.score if hasattr(match, 'score') else None,
        )


# =============================================================================
# PINECONE CLIENT
# =============================================================================

class PineconeClient:
    """
    Pinecone client wrapper for mock trial data.
    
    Provides CRUD operations for:
    - case_facts
    - witness_memory_<id>
    - transcript
    - prep_notes
    
    No trial logic - data access only.
    """
    
    # Default index configuration
    DEFAULT_DIMENSION = 512  # text-embedding-3-small with dimensions=512
    DEFAULT_METRIC = "cosine"
    DEFAULT_CLOUD = "aws"
    DEFAULT_REGION = "us-east-1"
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        index_name: str = "mock-trial",
        dimension: int = DEFAULT_DIMENSION
    ):
        """
        Initialize Pinecone client.
        
        Args:
            api_key: Pinecone API key (defaults to env var)
            index_name: Name of the Pinecone index
            dimension: Vector dimension (default 1536 for OpenAI embeddings)
        """
        self.api_key = api_key or os.environ.get("PINECONE_API_KEY")
        self.index_name = index_name
        self.dimension = dimension
        
        # Initialize Pinecone
        self._pc = Pinecone(api_key=self.api_key)
        self._index = None
    
    # =========================================================================
    # INDEX MANAGEMENT
    # =========================================================================
    
    def _get_index(self):
        """Get or create the index."""
        if self._index is None:
            # Check if index exists
            existing = self._pc.list_indexes()
            index_names = [idx.name for idx in existing]
            
            if self.index_name not in index_names:
                # Create index
                self._pc.create_index(
                    name=self.index_name,
                    dimension=self.dimension,
                    metric=self.DEFAULT_METRIC,
                    spec=ServerlessSpec(
                        cloud=self.DEFAULT_CLOUD,
                        region=self.DEFAULT_REGION
                    )
                )
            
            self._index = self._pc.Index(self.index_name)
        
        return self._index
    
    def ensure_index(self) -> None:
        """Ensure the index exists."""
        self._get_index()
    
    def delete_index(self) -> None:
        """Delete the index. Use with caution."""
        try:
            self._pc.delete_index(self.index_name)
            self._index = None
        except Exception:
            pass
    
    def get_index_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        index = self._get_index()
        stats = index.describe_index_stats()
        return {
            "dimension": stats.dimension,
            "total_vector_count": stats.total_vector_count,
            "namespaces": dict(stats.namespaces) if stats.namespaces else {},
        }
    
    # =========================================================================
    # CRUD OPERATIONS
    # =========================================================================
    
    def upsert(
        self,
        namespace: str,
        records: List[VectorRecord]
    ) -> int:
        """
        Upsert records to a namespace.
        
        Args:
            namespace: Target namespace
            records: List of VectorRecord to upsert
            
        Returns:
            Number of records upserted
        """
        if not records:
            return 0
        
        index = self._get_index()
        vectors = [r.to_dict() for r in records]
        
        response = index.upsert(
            vectors=vectors,
            namespace=namespace
        )
        
        return response.upserted_count
    
    def upsert_one(
        self,
        namespace: str,
        record: VectorRecord
    ) -> bool:
        """
        Upsert a single record.
        
        Args:
            namespace: Target namespace
            record: VectorRecord to upsert
            
        Returns:
            True if successful
        """
        count = self.upsert(namespace, [record])
        return count > 0
    
    def query(
        self,
        namespace: str,
        vector: List[float],
        top_k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_metadata: bool = True,
        include_values: bool = False
    ) -> List[VectorRecord]:
        """
        Query vectors by similarity.
        
        Args:
            namespace: Namespace to query
            vector: Query vector
            top_k: Number of results
            filter: Optional metadata filter
            include_metadata: Include metadata in results
            include_values: Include vector values in results
            
        Returns:
            List of matching VectorRecord
        """
        index = self._get_index()
        
        response = index.query(
            namespace=namespace,
            vector=vector,
            top_k=top_k,
            filter=filter,
            include_metadata=include_metadata,
            include_values=include_values
        )
        
        return [VectorRecord.from_match(m) for m in response.matches]
    
    def fetch(
        self,
        namespace: str,
        ids: List[str]
    ) -> Dict[str, VectorRecord]:
        """
        Fetch records by ID.
        
        Args:
            namespace: Namespace to fetch from
            ids: List of record IDs
            
        Returns:
            Dict mapping ID to VectorRecord
        """
        if not ids:
            return {}
        
        index = self._get_index()
        response = index.fetch(ids=ids, namespace=namespace)
        
        result = {}
        for id, vec in response.vectors.items():
            result[id] = VectorRecord(
                id=id,
                values=vec.values,
                metadata=vec.metadata if hasattr(vec, 'metadata') else {}
            )
        
        return result
    
    def fetch_one(
        self,
        namespace: str,
        id: str
    ) -> Optional[VectorRecord]:
        """
        Fetch a single record by ID.
        
        Args:
            namespace: Namespace to fetch from
            id: Record ID
            
        Returns:
            VectorRecord or None if not found
        """
        result = self.fetch(namespace, [id])
        return result.get(id)
    
    def delete(
        self,
        namespace: str,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict[str, Any]] = None,
        delete_all: bool = False
    ) -> None:
        """
        Delete records from a namespace.
        
        Args:
            namespace: Namespace to delete from
            ids: Specific IDs to delete
            filter: Metadata filter for deletion
            delete_all: Delete all records in namespace
        """
        index = self._get_index()
        
        if delete_all:
            index.delete(delete_all=True, namespace=namespace)
        elif ids:
            index.delete(ids=ids, namespace=namespace)
        elif filter:
            index.delete(filter=filter, namespace=namespace)
    
    def delete_one(self, namespace: str, id: str) -> None:
        """Delete a single record."""
        self.delete(namespace, ids=[id])
    
    def delete_namespace(self, namespace: str) -> None:
        """Delete all records in a namespace."""
        self.delete(namespace, delete_all=True)
    
    # =========================================================================
    # CASE FACTS OPERATIONS
    # =========================================================================
    
    def upsert_case_fact(
        self,
        id: str,
        vector: List[float],
        fact_type: str,
        content: str,
        source: str,
        **extra_metadata
    ) -> bool:
        """
        Upsert a case fact.
        
        Args:
            id: Unique identifier
            vector: Embedding vector
            fact_type: Type of fact (evidence, stipulation, law, etc.)
            content: The fact content
            source: Source document
            **extra_metadata: Additional metadata
        """
        record = VectorRecord(
            id=id,
            values=vector,
            metadata={
                "fact_type": fact_type,
                "content": content,
                "source": source,
                **extra_metadata
            }
        )
        return self.upsert_one(Namespace.CASE_FACTS, record)
    
    def query_case_facts(
        self,
        vector: List[float],
        top_k: int = 10,
        fact_type: Optional[str] = None
    ) -> List[VectorRecord]:
        """Query case facts by similarity."""
        filter = {"fact_type": fact_type} if fact_type else None
        return self.query(Namespace.CASE_FACTS, vector, top_k, filter)
    
    def get_case_fact(self, id: str) -> Optional[VectorRecord]:
        """Get a specific case fact."""
        return self.fetch_one(Namespace.CASE_FACTS, id)
    
    def delete_case_fact(self, id: str) -> None:
        """Delete a case fact."""
        self.delete_one(Namespace.CASE_FACTS, id)
    
    def clear_case_facts(self) -> None:
        """Clear all case facts."""
        self.delete_namespace(Namespace.CASE_FACTS)
    
    # =========================================================================
    # WITNESS MEMORY OPERATIONS
    # =========================================================================
    
    def upsert_witness_memory(
        self,
        witness_id: str,
        memory_id: str,
        vector: List[float],
        memory_type: str,
        content: str,
        **extra_metadata
    ) -> bool:
        """
        Upsert a witness memory entry.
        
        Args:
            witness_id: Witness identifier
            memory_id: Memory entry ID
            vector: Embedding vector
            memory_type: Type (affidavit, testimony, fact, etc.)
            content: Memory content
            **extra_metadata: Additional metadata
        """
        namespace = get_witness_namespace(witness_id)
        record = VectorRecord(
            id=memory_id,
            values=vector,
            metadata={
                "witness_id": witness_id,
                "memory_type": memory_type,
                "content": content,
                **extra_metadata
            }
        )
        return self.upsert_one(namespace, record)
    
    def query_witness_memory(
        self,
        witness_id: str,
        vector: List[float],
        top_k: int = 10,
        memory_type: Optional[str] = None
    ) -> List[VectorRecord]:
        """Query witness memory by similarity."""
        namespace = get_witness_namespace(witness_id)
        filter = {"memory_type": memory_type} if memory_type else None
        return self.query(namespace, vector, top_k, filter)
    
    def get_witness_memory(
        self,
        witness_id: str,
        memory_id: str
    ) -> Optional[VectorRecord]:
        """Get a specific witness memory entry."""
        namespace = get_witness_namespace(witness_id)
        return self.fetch_one(namespace, memory_id)
    
    def delete_witness_memory(
        self,
        witness_id: str,
        memory_id: str
    ) -> None:
        """Delete a witness memory entry."""
        namespace = get_witness_namespace(witness_id)
        self.delete_one(namespace, memory_id)
    
    def clear_witness_memory(self, witness_id: str) -> None:
        """Clear all memory for a witness."""
        namespace = get_witness_namespace(witness_id)
        self.delete_namespace(namespace)
    
    # =========================================================================
    # TRANSCRIPT OPERATIONS
    # =========================================================================
    
    def upsert_transcript_entry(
        self,
        id: str,
        vector: List[float],
        role: str,
        phase: str,
        content: str,
        timestamp: float,
        **extra_metadata
    ) -> bool:
        """
        Upsert a transcript entry.
        
        Args:
            id: Entry ID
            vector: Embedding vector
            role: Speaker role
            phase: Trial phase
            content: Transcript text
            timestamp: Audio timestamp
            **extra_metadata: Additional metadata
        """
        record = VectorRecord(
            id=id,
            values=vector,
            metadata={
                "role": role,
                "phase": phase,
                "content": content,
                "timestamp": timestamp,
                **extra_metadata
            }
        )
        return self.upsert_one(Namespace.TRANSCRIPT, record)
    
    def query_transcript(
        self,
        vector: List[float],
        top_k: int = 10,
        phase: Optional[str] = None,
        role: Optional[str] = None
    ) -> List[VectorRecord]:
        """Query transcript by similarity."""
        filter = {}
        if phase:
            filter["phase"] = phase
        if role:
            filter["role"] = role
        
        return self.query(
            Namespace.TRANSCRIPT,
            vector,
            top_k,
            filter if filter else None
        )
    
    def get_transcript_entry(self, id: str) -> Optional[VectorRecord]:
        """Get a specific transcript entry."""
        return self.fetch_one(Namespace.TRANSCRIPT, id)
    
    def delete_transcript_entry(self, id: str) -> None:
        """Delete a transcript entry."""
        self.delete_one(Namespace.TRANSCRIPT, id)
    
    def clear_transcript(self) -> None:
        """Clear all transcript entries."""
        self.delete_namespace(Namespace.TRANSCRIPT)
    
    # =========================================================================
    # PREP NOTES OPERATIONS
    # =========================================================================
    
    def upsert_prep_note(
        self,
        id: str,
        vector: List[float],
        note_type: str,
        content: str,
        related_to: Optional[str] = None,
        **extra_metadata
    ) -> bool:
        """
        Upsert a preparation note.
        
        Args:
            id: Note ID
            vector: Embedding vector
            note_type: Type (strategy, question, theme, etc.)
            content: Note content
            related_to: Related entity (witness, exhibit, etc.)
            **extra_metadata: Additional metadata
        """
        metadata = {
            "note_type": note_type,
            "content": content,
            **extra_metadata
        }
        if related_to:
            metadata["related_to"] = related_to
        
        record = VectorRecord(
            id=id,
            values=vector,
            metadata=metadata
        )
        return self.upsert_one(Namespace.PREP_NOTES, record)
    
    def query_prep_notes(
        self,
        vector: List[float],
        top_k: int = 10,
        note_type: Optional[str] = None,
        related_to: Optional[str] = None
    ) -> List[VectorRecord]:
        """Query prep notes by similarity."""
        filter = {}
        if note_type:
            filter["note_type"] = note_type
        if related_to:
            filter["related_to"] = related_to
        
        return self.query(
            Namespace.PREP_NOTES,
            vector,
            top_k,
            filter if filter else None
        )
    
    def get_prep_note(self, id: str) -> Optional[VectorRecord]:
        """Get a specific prep note."""
        return self.fetch_one(Namespace.PREP_NOTES, id)
    
    def delete_prep_note(self, id: str) -> None:
        """Delete a prep note."""
        self.delete_one(Namespace.PREP_NOTES, id)
    
    def clear_prep_notes(self) -> None:
        """Clear all prep notes."""
        self.delete_namespace(Namespace.PREP_NOTES)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_pinecone_client(
    api_key: Optional[str] = None,
    index_name: str = "mock-trial"
) -> PineconeClient:
    """
    Create a new Pinecone client instance.
    
    Args:
        api_key: Optional API key (defaults to env var)
        index_name: Index name
        
    Returns:
        PineconeClient instance
    """
    return PineconeClient(api_key=api_key, index_name=index_name)
