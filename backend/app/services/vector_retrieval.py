"""
Vector Retrieval Service

Thin retrieval layer between trial agents and Pinecone.
Agents call these functions to get semantically relevant context
without knowing about Pinecone internals.

All functions degrade gracefully — returning empty results if
Pinecone or the embedding service is unavailable.
"""

import logging
import os
from typing import List, Optional, Dict, Any

logger = logging.getLogger(__name__)

_pinecone_available: Optional[bool] = None
_dimension_error_count: int = 0
_MAX_DIMENSION_ERRORS = 3


def _get_services():
    """Lazy-load embedding + Pinecone services. Returns (embedding_svc, pinecone_client) or (None, None)."""
    global _pinecone_available, _dimension_error_count
    if _pinecone_available is False:
        return None, None
    if _dimension_error_count >= _MAX_DIMENSION_ERRORS:
        if _pinecone_available is not False:
            _pinecone_available = False
            logger.warning(
                "Vector retrieval disabled: Pinecone index dimension mismatch. "
                "The index uses 512 dims but text-embedding-ada-002 produces 1536. "
                "Delete and recreate the Pinecone index with dimension=1536, or "
                "change DEFAULT_DIMENSION in pinecone.py. Agents will use full-text fallback."
            )
        return None, None
    try:
        from ..api.case import get_embedding_service, get_pinecone
        emb = get_embedding_service()
        pc = get_pinecone()
        if _pinecone_available is None:
            pc._get_index()
            _pinecone_available = True
            logger.info("Vector retrieval: Pinecone connection verified")
        return emb, pc
    except Exception as e:
        if _pinecone_available is None:
            _pinecone_available = False
            logger.warning(f"Vector retrieval unavailable — agents will use full-text fallback: {e}")
        return None, None


def _handle_pinecone_error(e: Exception) -> None:
    """Track dimension mismatch errors for circuit breaker."""
    global _dimension_error_count
    err_str = str(e)
    if "dimension" in err_str.lower() and "does not match" in err_str.lower():
        _dimension_error_count += 1


def retrieve_relevant_affidavit(
    witness_id: str,
    query: str,
    top_k: int = 5,
) -> List[str]:
    """Retrieve the most relevant affidavit passages for a witness given a query.

    Queries the witness_memory_<id> namespace in Pinecone.
    Returns a list of text passages ranked by relevance.
    """
    emb, pc = _get_services()
    if not emb or not pc:
        return []
    try:
        vector = emb.embed_text(query)
        from .pinecone import get_witness_namespace
        ns = get_witness_namespace(witness_id)
        results = pc.query(ns, vector, top_k=top_k, include_metadata=True)
        passages = [r.metadata.get("content", "") for r in results if r.metadata.get("content")]
        if passages:
            logger.debug(f"Retrieved {len(passages)} affidavit passages for witness {witness_id}")
        return passages
    except Exception as e:
        _handle_pinecone_error(e)
        logger.warning(f"Affidavit retrieval failed for {witness_id}: {e}")
        return []


def retrieve_relevant_facts(
    query: str,
    top_k: int = 5,
    fact_type: Optional[str] = None,
) -> List[str]:
    """Retrieve the most relevant case facts for a query.

    Queries the case_facts namespace in Pinecone.
    Optional fact_type filter: 'evidence', 'stipulation', 'legal_standard', 'exhibit'.
    """
    emb, pc = _get_services()
    if not emb or not pc:
        return []
    try:
        vector = emb.embed_text(query)
        results = pc.query_case_facts(vector, top_k=top_k, fact_type=fact_type)
        facts = [r.metadata.get("content", "") for r in results if r.metadata.get("content")]
        if facts:
            logger.debug(f"Retrieved {len(facts)} case facts")
        return facts
    except Exception as e:
        _handle_pinecone_error(e)
        logger.warning(f"Case fact retrieval failed: {e}")
        return []


def retrieve_relevant_testimony(
    query: str,
    top_k: int = 10,
    phase: Optional[str] = None,
    role: Optional[str] = None,
) -> List[str]:
    """Retrieve the most relevant prior testimony for a query.

    Queries the transcript namespace in Pinecone.
    Returns formatted Q&A strings.
    """
    emb, pc = _get_services()
    if not emb or not pc:
        return []
    try:
        vector = emb.embed_text(query)
        results = pc.query_transcript(vector, top_k=top_k, phase=phase, role=role)
        entries = [r.metadata.get("content", "") for r in results if r.metadata.get("content")]
        if entries:
            logger.debug(f"Retrieved {len(entries)} testimony entries")
        return entries
    except Exception as e:
        _handle_pinecone_error(e)
        logger.warning(f"Testimony retrieval failed: {e}")
        return []


def index_testimony(
    witness_id: str,
    witness_name: str,
    question: str,
    answer: str,
    phase: str,
    questioner_side: str,
    case_id: str = "",
) -> bool:
    """Embed and store a Q&A exchange in the transcript namespace.

    Called after each question/answer pair during examination.
    Returns True on success, False on failure (non-blocking).
    """
    emb, pc = _get_services()
    if not emb or not pc:
        return False
    try:
        content = f"Q ({questioner_side} attorney): {question}\nA ({witness_name}): {answer}"
        vector = emb.embed_text(content)

        import uuid
        entry_id = f"testimony_{uuid.uuid4().hex[:12]}"

        pc.upsert_transcript_entry(
            id=entry_id,
            vector=vector,
            role=f"witness_{witness_id}",
            phase=phase,
            content=content,
            timestamp=0.0,
            witness_id=witness_id,
            witness_name=witness_name,
            questioner_side=questioner_side,
            case_id=case_id,
        )
        return True
    except Exception as e:
        _handle_pinecone_error(e)
        logger.warning(f"Testimony indexing failed: {e}")
        return False


def build_retrieval_context(
    witness_id: str,
    query: str,
    include_facts: bool = True,
    affidavit_top_k: int = 5,
    facts_top_k: int = 5,
) -> str:
    """Convenience: build a combined retrieval context string for agent prompts.

    Returns empty string if nothing was retrieved (caller should fall back to
    full-text affidavit).
    """
    parts = []

    affidavit_passages = retrieve_relevant_affidavit(witness_id, query, top_k=affidavit_top_k)
    if affidavit_passages:
        numbered = "\n".join(f"{i+1}. {p}" for i, p in enumerate(affidavit_passages))
        parts.append(f"RELEVANT AFFIDAVIT PASSAGES (semantically matched):\n{numbered}")

    if include_facts:
        facts = retrieve_relevant_facts(query, top_k=facts_top_k)
        if facts:
            numbered = "\n".join(f"{i+1}. {f}" for i, f in enumerate(facts))
            parts.append(f"RELEVANT CASE FACTS:\n{numbered}")

    if not parts:
        return ""
    return "\n\n".join(parts)
