"""
Case Management Endpoints

Per SPEC.md Section 4: Trial lifecycle starts with case selection.

Handles:
- Accept case files (PDF/JSON)
- Parse facts, witnesses, exhibits
- Store embeddings in Pinecone
- Return CaseMetadata
- Serve case material files (PDFs, images, docs)
"""

import os
import io
import json
import uuid
import hashlib
import logging
from pathlib import Path
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from openai import OpenAI

from ..services import (
    PineconeClient,
    Namespace,
    VectorRecord,
    get_witness_namespace,
    create_pinecone_client,
)
from ..db import CaseRepository, get_storage_service, VALID_SECTIONS as STORAGE_SECTIONS
from ..data import get_all_demo_cases, get_demo_case_by_id, get_demo_case_ids
from ..data.demo_cases import (
    get_featured_demo_cases,
    get_case_sections,
    get_uploaded_case,
    save_uploaded_case,
    delete_uploaded_case,
    get_case_source_by_id,
    toggle_favorite,
    is_favorite,
    get_favorite_cases,
    record_case_access,
    get_recently_accessed,
    MYLAW_CASE_SOURCES,
)
import httpx


router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# IN-MEMORY CACHE
# =============================================================================

# In-memory cache for quick access; Supabase is source of truth
_cases: Dict[str, "CaseData"] = {}
_processing_status: Dict[str, "ProcessingStatus"] = {}


class ProcessingStatus:
    """Track case processing status."""
    
    def __init__(self, case_id: str):
        self.case_id = case_id
        self.status: str = "pending"  # pending, processing, completed, failed
        self.progress: float = 0.0
        self.message: str = "Waiting to process"
        self.started_at: Optional[datetime] = None
        self.completed_at: Optional[datetime] = None
        self.error: Optional[str] = None


class CaseData:
    """In-memory case data container."""
    
    def __init__(
        self,
        case_id: str,
        name: str,
        source_type: str,
        source_filename: str
    ):
        self.case_id = case_id
        self.name = name
        self.source_type = source_type
        self.source_filename = source_filename
        self.created_at = datetime.utcnow()
        
        # Parsed content
        self.facts: List[Dict[str, Any]] = []
        self.witnesses: List[Dict[str, Any]] = []
        self.exhibits: List[Dict[str, Any]] = []
        self.stipulations: List[Dict[str, Any]] = []
        self.legal_standards: List[Dict[str, Any]] = []
        self.special_instructions: List[Dict[str, Any]] = []
        self.jury_instructions: List[Dict[str, Any]] = []
        self.indictment: Dict[str, Any] = {}
        self.relevant_law: Dict[str, Any] = {}
        self.motions_in_limine: List[Dict[str, Any]] = []
        self.witness_calling_restrictions: Dict[str, List[str]] = {}
        self.synopsis: str = ""
        
        # Metadata
        self.case_type: str = "unknown"
        self.charge: str = ""
        self.plaintiff: str = ""
        self.defendant: str = ""
        self.fact_count: int = 0
        self.witness_count: int = 0
        self.exhibit_count: int = 0
        self.embedding_count: int = 0
        
        # Processing
        self.processed: bool = False


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class FactItem(BaseModel):
    """A parsed fact from the case."""
    id: str
    fact_type: str  # evidence, stipulation, background, legal_standard
    content: str
    source: str
    page: Optional[int] = None


class WitnessItem(BaseModel):
    """A parsed witness from the case."""
    id: str
    name: str
    called_by: str  # plaintiff, defense
    affidavit: str
    role_description: str
    key_facts: List[str] = []


class ExhibitItem(BaseModel):
    """A parsed exhibit from the case."""
    id: str
    exhibit_number: str
    title: str
    description: str
    content_type: str  # document, photo, diagram, etc.
    pre_admitted: bool = False


class CaseMetadataResponse(BaseModel):
    """Response with case metadata."""
    case_id: str
    name: str
    source_type: str
    source_filename: str
    created_at: str
    processed: bool
    fact_count: int
    witness_count: int
    exhibit_count: int
    embedding_count: int


class CaseDetailResponse(BaseModel):
    """Full case details."""
    case_id: str
    name: str
    source_type: str
    created_at: str
    case_type: str = "unknown"
    charge: str = ""
    plaintiff: str = ""
    defendant: str = ""
    synopsis: str = ""
    facts: List[FactItem]
    witnesses: List[WitnessItem]
    exhibits: List[ExhibitItem]
    stipulations: List[Dict[str, Any]] = []
    jury_instructions: List[Dict[str, Any]] = []
    special_instructions: List[Dict[str, Any]] = []
    indictment: Dict[str, Any] = {}
    relevant_law: Dict[str, Any] = {}
    motions_in_limine: List[Dict[str, Any]] = []
    witness_calling_restrictions: Dict[str, Any] = {}


class ProcessingStatusResponse(BaseModel):
    """Processing status response."""
    case_id: str
    status: str
    progress: float
    message: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error: Optional[str]


class UploadCaseResponse(BaseModel):
    """Response after uploading a case."""
    case_id: str
    name: str
    status: str
    message: str


class ParsedCaseJSON(BaseModel):
    """Schema for JSON case files."""
    name: str
    facts: List[Dict[str, Any]] = []
    witnesses: List[Dict[str, Any]] = []
    exhibits: List[Dict[str, Any]] = []
    stipulations: List[Dict[str, Any]] = []
    legal_standards: List[Dict[str, Any]] = []


# =============================================================================
# EMBEDDING SERVICE
# =============================================================================

class EmbeddingService:
    """Service for generating embeddings using OpenAI.

    Uses text-embedding-3-small with dimensions=512 to match the Pinecone
    index dimension.  The newer model is cheaper, faster, and supports
    the ``dimensions`` parameter for truncated output.
    """

    MODEL = "text-embedding-3-small"
    DIMENSIONS = 512

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client: Optional[OpenAI] = None

    @property
    def client(self) -> OpenAI:
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    def embed_text(self, text: str) -> List[float]:
        """Generate embedding for a single text."""
        response = self.client.embeddings.create(
            model=self.MODEL,
            input=text,
            dimensions=self.DIMENSIONS,
        )
        return response.data[0].embedding

    def embed_batch(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings for multiple texts."""
        if not texts:
            return []

        batch_size = 100
        all_embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            response = self.client.embeddings.create(
                model=self.MODEL,
                input=batch,
                dimensions=self.DIMENSIONS,
            )
            all_embeddings.extend([d.embedding for d in response.data])

        return all_embeddings


# Global services
_embedding_service: Optional[EmbeddingService] = None
_pinecone_client: Optional[PineconeClient] = None


def get_embedding_service() -> EmbeddingService:
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def get_pinecone() -> PineconeClient:
    global _pinecone_client
    if _pinecone_client is None:
        _pinecone_client = create_pinecone_client()
    return _pinecone_client


# =============================================================================
# PDF PARSING
# =============================================================================

def _parse_witness_section(section_text: str, called_by: str) -> List[Dict[str, Any]]:
    """Parse a witness section (affidavit text) into structured witness data.

    Uses a simple heuristic: split on common affidavit markers
    (e.g. "AFFIDAVIT OF", "STATEMENT OF", "WITNESS:", numbered witness headers).
    Each chunk becomes a witness entry with the full affidavit text preserved verbatim.
    Falls back to treating the whole section as a single witness if splitting fails.
    """
    import re

    if not section_text or len(section_text.strip()) < 50:
        return []

    # Common patterns that start a new witness affidavit
    split_pattern = re.compile(
        r'(?=(?:^|\n)(?:'
        r'AFFIDAVIT\s+OF\s+'
        r'|SWORN\s+STATEMENT\s+OF\s+'
        r'|STATEMENT\s+OF\s+'
        r'|WITNESS\s*(?:STATEMENT|AFFIDAVIT)?\s*:\s*'
        r'|(?:(?:PROSECUTION|DEFENSE|PLAINTIFF)\s+)?WITNESS\s+\d+'
        r'|\d+\.\s+AFFIDAVIT'
        r'))',
        re.IGNORECASE | re.MULTILINE,
    )

    chunks = split_pattern.split(section_text)
    chunks = [c.strip() for c in chunks if c.strip() and len(c.strip()) > 50]

    if not chunks:
        chunks = [section_text.strip()]

    witnesses: List[Dict[str, Any]] = []
    for i, chunk in enumerate(chunks):
        # Try to extract name from the first line
        first_line = chunk.split("\n")[0].strip()
        name_match = re.search(
            r'(?:AFFIDAVIT|STATEMENT|WITNESS)\s*(?:OF|:)?\s*(.+)',
            first_line,
            re.IGNORECASE,
        )
        name = name_match.group(1).strip().rstrip(".,:;") if name_match else f"Witness {i + 1}"
        # Clean up name
        name = re.sub(r'\s+', ' ', name)
        if len(name) > 60:
            name = name[:60]

        witness_id = re.sub(r'[^a-z0-9]+', '_', name.lower()).strip('_')
        if not witness_id:
            witness_id = f"witness_{called_by}_{i + 1}"

        witnesses.append({
            "id": witness_id,
            "name": name,
            "called_by": called_by,
            "affidavit": chunk,
            "role_description": "",
            "key_facts": [],
            "document_type": "affidavit",
        })

    return witnesses


def extract_text_from_pdf(pdf_bytes: bytes) -> str:
    """
    Extract text from PDF bytes.
    
    Uses PyPDF2 or pdfplumber if available.
    """
    try:
        # Try PyPDF2 first
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        text_parts = []
        for page in reader.pages:
            text_parts.append(page.extract_text() or "")
        return "\n\n".join(text_parts)
    except ImportError:
        pass
    
    try:
        # Try pdfplumber
        import pdfplumber
        with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
            text_parts = []
            for page in pdf.pages:
                text_parts.append(page.extract_text() or "")
            return "\n\n".join(text_parts)
    except ImportError:
        pass
    
    raise HTTPException(
        status_code=500,
        detail="PDF parsing requires PyPDF2 or pdfplumber. Install with: pip install PyPDF2"
    )


def parse_pdf_to_case(pdf_bytes_or_text, case_name: str) -> Dict[str, Any]:
    """
    Parse a mock trial PDF into structured case data.

    Uses the AMTA section-aware parser first (regex-based, no API calls).
    Falls back to GPT-4 for non-AMTA format PDFs.

    Args:
        pdf_bytes_or_text: Either raw PDF bytes or pre-extracted text string
        case_name: Fallback name for the case
    """
    # If we received raw bytes, try the AMTA parser first
    if isinstance(pdf_bytes_or_text, bytes):
        try:
            from ..services.case_parser import parse_mock_trial_pdf
            result = parse_mock_trial_pdf(pdf_bytes_or_text)
            if result.get("witness_count", 0) > 0 or result.get("exhibit_count", 0) > 0:
                logger.info(
                    f"AMTA parser succeeded: {result.get('name')} "
                    f"({result['witness_count']} witnesses, {result['exhibit_count']} exhibits)"
                )
                return result
            logger.info("AMTA parser returned no witnesses/exhibits, falling back to GPT-4")
        except Exception as e:
            logger.warning(f"AMTA parser failed, falling back to GPT-4: {e}")

    # Extract text if we have bytes
    if isinstance(pdf_bytes_or_text, bytes):
        pdf_text = extract_text_from_pdf(pdf_bytes_or_text)
    else:
        pdf_text = pdf_bytes_or_text

    # Fallback: GPT-4 parsing for non-AMTA format PDFs
    try:
        client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"))

        prompt = f"""Analyze this mock trial case document and extract structured data.

Document text:
{pdf_text[:60000]}

Extract and return a JSON object with:
{{
    "name": "Case name from document",
    "charge": "The criminal charge or civil claim",
    "case_type": "criminal or civil",
    "synopsis": "Brief 2-3 sentence summary of the case",
    "facts": [
        {{"id": "fact_1", "fact_type": "evidence|stipulation|background|legal_standard", "content": "...", "source": "page X"}}
    ],
    "witnesses": [
        {{"id": "witness_1", "name": "...", "called_by": "plaintiff|defense", "affidavit": "FULL AND COMPLETE affidavit text — do NOT summarize, include EVERY paragraph verbatim", "role_description": "...", "key_facts": ["fact1", "fact2"]}}
    ],
    "exhibits": [
        {{"id": "exhibit_1", "exhibit_number": "1", "title": "...", "description": "...", "content_type": "document|photo|diagram", "pre_admitted": false}}
    ],
    "stipulations": [
        {{"id": "stip_1", "content": "..."}}
    ],
    "legal_standards": [
        {{"id": "law_1", "content": "..."}}
    ]
}}

CRITICAL: For each witness, the "affidavit" field MUST contain the COMPLETE, VERBATIM text of their affidavit or sworn statement. Do NOT summarize or truncate. Include every paragraph, every detail, every specific fact.

Return ONLY valid JSON, no explanation."""

        response = client.chat.completions.create(
            model="gpt-4.1",
            messages=[
                {"role": "system", "content": "You are a legal document parser. Extract structured mock trial case data. PRESERVE full witness affidavit text verbatim — do not summarize. Return only valid JSON."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            max_tokens=16000,
        )

        return json.loads(response.choices[0].message.content)
    except Exception:
        return {
            "name": case_name,
            "facts": [{"id": "fact_raw", "fact_type": "background", "content": pdf_text[:5000], "source": "raw_extract"}],
            "witnesses": [],
            "exhibits": [],
            "stipulations": [],
            "legal_standards": []
        }


# =============================================================================
# BACKGROUND PROCESSING
# =============================================================================

async def process_case_embeddings(case_id: str):
    """
    Background task to process case data and store embeddings in Pinecone.
    """
    if case_id not in _cases:
        return
    
    case = _cases[case_id]
    status = _processing_status.get(case_id)
    
    if not status:
        return
    
    status.status = "processing"
    status.started_at = datetime.utcnow()
    status.message = "Generating embeddings..."
    
    try:
        embedding_service = get_embedding_service()
        pinecone = get_pinecone()
        
        total_items = (
            len(case.facts) + 
            len(case.witnesses) + 
            len(case.exhibits) + 
            len(case.stipulations) + 
            len(case.legal_standards)
        )
        processed_items = 0
        
        # Process facts
        status.message = "Processing facts..."
        for fact in case.facts:
            try:
                embedding = embedding_service.embed_text(fact["content"])
                pinecone.upsert_case_fact(
                    id=f"{case_id}_{fact['id']}",
                    vector=embedding,
                    fact_type=fact.get("fact_type", "evidence"),
                    content=fact["content"],
                    source=fact.get("source", "case_file"),
                    case_id=case_id
                )
                case.embedding_count += 1
            except Exception:
                pass  # Continue on individual failures
            
            processed_items += 1
            status.progress = processed_items / total_items if total_items > 0 else 1.0
        
        # Process witnesses (embed affidavits)
        status.message = "Processing witness affidavits..."
        for witness in case.witnesses:
            try:
                witness_id = witness["id"]
                affidavit = witness.get("affidavit", "")
                
                if affidavit:
                    # Split affidavit into chunks
                    chunks = _chunk_text(affidavit, max_chars=1000)
                    
                    for i, chunk in enumerate(chunks):
                        embedding = embedding_service.embed_text(chunk)
                        pinecone.upsert_witness_memory(
                            witness_id=witness_id,
                            memory_id=f"{witness_id}_affidavit_{i}",
                            vector=embedding,
                            memory_type="affidavit",
                            content=chunk,
                            case_id=case_id,
                            witness_name=witness.get("name", ""),
                            called_by=witness.get("called_by", "")
                        )
                        case.embedding_count += 1
            except Exception:
                pass
            
            processed_items += 1
            status.progress = processed_items / total_items if total_items > 0 else 1.0
        
        # Process exhibits
        status.message = "Processing exhibits..."
        for exhibit in case.exhibits:
            try:
                content = f"{exhibit.get('title', '')} - {exhibit.get('description', '')}"
                embedding = embedding_service.embed_text(content)
                pinecone.upsert_case_fact(
                    id=f"{case_id}_exhibit_{exhibit['id']}",
                    vector=embedding,
                    fact_type="exhibit",
                    content=content,
                    source=f"Exhibit {exhibit.get('exhibit_number', '')}",
                    case_id=case_id,
                    exhibit_number=exhibit.get("exhibit_number", ""),
                    pre_admitted=exhibit.get("pre_admitted", False)
                )
                case.embedding_count += 1
            except Exception:
                pass
            
            processed_items += 1
            status.progress = processed_items / total_items if total_items > 0 else 1.0
        
        # Process stipulations
        status.message = "Processing stipulations..."
        for stip in case.stipulations:
            try:
                embedding = embedding_service.embed_text(stip["content"])
                pinecone.upsert_case_fact(
                    id=f"{case_id}_stip_{stip['id']}",
                    vector=embedding,
                    fact_type="stipulation",
                    content=stip["content"],
                    source="stipulations",
                    case_id=case_id
                )
                case.embedding_count += 1
            except Exception:
                pass
            
            processed_items += 1
            status.progress = processed_items / total_items if total_items > 0 else 1.0
        
        # Process legal standards
        status.message = "Processing legal standards..."
        for law in case.legal_standards:
            try:
                embedding = embedding_service.embed_text(law["content"])
                pinecone.upsert_case_fact(
                    id=f"{case_id}_law_{law['id']}",
                    vector=embedding,
                    fact_type="legal_standard",
                    content=law["content"],
                    source="legal_standards",
                    case_id=case_id
                )
                case.embedding_count += 1
            except Exception:
                pass
            
            processed_items += 1
            status.progress = processed_items / total_items if total_items > 0 else 1.0
        
        case.processed = True
        status.status = "completed"
        status.progress = 1.0
        status.message = f"Completed. {case.embedding_count} embeddings stored."
        status.completed_at = datetime.utcnow()
        
    except Exception as e:
        status.status = "failed"
        status.error = str(e)
        status.message = f"Processing failed: {str(e)}"


def _chunk_text(text: str, max_chars: int = 1000) -> List[str]:
    """Split text into chunks for embedding."""
    if len(text) <= max_chars:
        return [text]
    
    chunks = []
    sentences = text.replace("\n", " ").split(". ")
    current_chunk = ""
    
    for sentence in sentences:
        if len(current_chunk) + len(sentence) + 2 <= max_chars:
            current_chunk += sentence + ". "
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = sentence + ". "
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks if chunks else [text[:max_chars]]


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/upload/json", response_model=UploadCaseResponse)
async def upload_case_json(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    process_embeddings: bool = Form(True),
):
    """
    Upload a case from a JSON file.
    
    The JSON should match the ParsedCaseJSON schema.
    """
    if not file.filename.endswith(".json"):
        raise HTTPException(
            status_code=400,
            detail="File must be a JSON file"
        )
    
    try:
        content = await file.read()
        data = json.loads(content.decode("utf-8"))
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {str(e)}"
        )
    
    # Generate case ID
    case_id = hashlib.md5(content).hexdigest()[:12]
    
    # Check if already exists (in-memory cache or database)
    case_repo = CaseRepository()
    db_case = case_repo.get_case(case_id)
    
    if case_id in _cases or db_case:
        existing_name = _cases[case_id].name if case_id in _cases else db_case.title
        return UploadCaseResponse(
            case_id=case_id,
            name=existing_name,
            status="exists",
            message="Case already uploaded"
        )
    
    # Create in-memory case
    case = CaseData(
        case_id=case_id,
        name=data.get("name", file.filename),
        source_type="json",
        source_filename=file.filename
    )
    
    case.facts = data.get("facts", [])
    case.witnesses = data.get("witnesses", [])
    case.exhibits = data.get("exhibits", [])
    case.stipulations = data.get("stipulations", [])
    case.legal_standards = data.get("legal_standards", [])
    case.special_instructions = data.get("special_instructions", [])
    case.jury_instructions = data.get("jury_instructions", [])
    case.indictment = data.get("indictment", {})
    case.relevant_law = data.get("relevant_law", {})
    case.motions_in_limine = data.get("motions_in_limine", [])
    case.witness_calling_restrictions = data.get("witness_calling_restrictions", {})
    case.synopsis = data.get("synopsis", "")
    case.case_type = data.get("case_type", "unknown")
    case.charge = data.get("charge", "")
    case.plaintiff = data.get("plaintiff", "")
    case.defendant = data.get("defendant", "")
    
    case.fact_count = len(case.facts)
    case.witness_count = len(case.witnesses)
    case.exhibit_count = len(case.exhibits)
    
    _cases[case_id] = case
    
    # Persist to Supabase
    try:
        db_case = case_repo.create_case(
            case_id=case_id,
            title=case.name,
            description=f"Uploaded from {file.filename}",
            case_type="json",
            facts=case.facts,
            exhibits=case.exhibits,
        )
        
        # Persist witnesses
        for witness in case.witnesses:
            case_repo.add_witness(
                case_id=case_id,
                witness_id=witness.get("id"),
                name=witness.get("name", "Unknown"),
                called_by=witness.get("called_by", "plaintiff"),
                affidavit=witness.get("affidavit", ""),
                witness_type=witness.get("witness_type", "fact_witness"),
                default_persona={
                    "role_description": witness.get("role_description", ""),
                    "key_facts": witness.get("key_facts", []),
                }
            )
        
        logger.info(f"Case {case_id} persisted to database")
    except Exception as e:
        logger.warning(f"Failed to persist case to database: {e}")
    
    # Initialize processing status
    _processing_status[case_id] = ProcessingStatus(case_id)
    
    if process_embeddings:
        background_tasks.add_task(process_case_embeddings, case_id)
        status_msg = "Processing embeddings in background"
    else:
        _processing_status[case_id].status = "skipped"
        status_msg = "Uploaded without embedding processing"
    
    return UploadCaseResponse(
        case_id=case_id,
        name=case.name,
        status="uploaded",
        message=status_msg
    )


@router.post("/upload/pdf", response_model=UploadCaseResponse)
async def upload_case_pdf(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    case_name: str = Form(None),
    process_embeddings: bool = Form(True),
):
    """
    Upload a case from a PDF file.
    
    The PDF will be parsed using GPT-4 to extract structured case data.
    Files are also stored in Supabase Storage for persistence.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(
            status_code=400,
            detail="File must be a PDF file"
        )
    
    content = await file.read()
    
    # Generate case ID from content hash
    case_id = hashlib.md5(content).hexdigest()[:12]
    
    # Check if already exists (in-memory cache or database)
    case_repo = CaseRepository()
    db_case = case_repo.get_case(case_id)
    
    if case_id in _cases or db_case:
        existing_name = _cases[case_id].name if case_id in _cases else db_case.title
        return UploadCaseResponse(
            case_id=case_id,
            name=existing_name,
            status="exists",
            message="Case already uploaded"
        )
    
    # Store original PDF in Supabase Storage
    storage_path = None
    try:
        storage_service = get_storage_service()
        storage_result = storage_service.upload_file(
            case_id=case_id,
            section="summary",  # Store full PDF in summary section
            filename=file.filename,
            file_content=content,
            content_type="application/pdf",
        )
        if storage_result.get("success"):
            storage_path = storage_result["path"]
            logger.info(f"Stored PDF in Supabase Storage: {storage_path}")
    except Exception as e:
        logger.warning(f"Failed to store PDF in Supabase Storage: {e}")
    
    # Parse PDF content (AMTA parser first, then GPT-4 fallback)
    name = case_name or file.filename.replace(".pdf", "")
    try:
        parsed_data = parse_pdf_to_case(content, name)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse PDF content: {str(e)}"
        )
    
    # Create in-memory case
    case = CaseData(
        case_id=case_id,
        name=parsed_data.get("name", name),
        source_type="pdf",
        source_filename=file.filename
    )
    
    # Store parsed content
    case.facts = parsed_data.get("facts", [])
    case.witnesses = parsed_data.get("witnesses", [])
    case.exhibits = parsed_data.get("exhibits", [])
    case.stipulations = parsed_data.get("stipulations", [])
    case.legal_standards = parsed_data.get("legal_standards", [])
    case.special_instructions = parsed_data.get("special_instructions", [])
    case.jury_instructions = parsed_data.get("jury_instructions", [])
    case.indictment = parsed_data.get("indictment", {})
    case.relevant_law = parsed_data.get("relevant_law", {})
    case.motions_in_limine = parsed_data.get("motions_in_limine", [])
    case.witness_calling_restrictions = parsed_data.get("witness_calling_restrictions", {})
    case.synopsis = parsed_data.get("synopsis", "")
    case.case_type = parsed_data.get("case_type", "unknown")
    case.charge = parsed_data.get("charge", "")
    case.plaintiff = parsed_data.get("plaintiff", "")
    case.defendant = parsed_data.get("defendant", "")
    
    # Update counts
    case.fact_count = len(case.facts)
    case.witness_count = len(case.witnesses)
    case.exhibit_count = len(case.exhibits)
    
    _cases[case_id] = case
    
    # Persist to Supabase
    try:
        db_case = case_repo.create_case(
            case_id=case_id,
            title=case.name,
            description=parsed_data.get("synopsis", f"Parsed from PDF: {file.filename}")[:500],
            case_type=case.case_type,
            facts=case.facts,
            exhibits=case.exhibits,
        )
        
        # Persist witnesses
        for witness in case.witnesses:
            case_repo.add_witness(
                case_id=case_id,
                witness_id=witness.get("id"),
                name=witness.get("name", "Unknown"),
                called_by=witness.get("called_by", "unknown"),
                affidavit=witness.get("affidavit", ""),
                witness_type=witness.get("document_type", "fact_witness"),
                default_persona={
                    "role_description": witness.get("role_description", ""),
                    "key_facts": witness.get("key_facts", []),
                }
            )
        
        logger.info(f"Case {case_id} (PDF) persisted to database")
    except Exception as e:
        logger.warning(f"Failed to persist PDF case to database: {e}")
    
    # Initialize processing status
    _processing_status[case_id] = ProcessingStatus(case_id)
    
    if process_embeddings:
        background_tasks.add_task(process_case_embeddings, case_id)
        status_msg = "PDF parsed. Processing embeddings in background."
    else:
        _processing_status[case_id].status = "skipped"
        status_msg = "PDF parsed. Embeddings not processed."
    
    return UploadCaseResponse(
        case_id=case_id,
        name=case.name,
        status="uploaded",
        message=status_msg
    )


@router.get("/demo", response_model=List[Dict[str, Any]])
async def list_demo_cases():
    """
    List all available demo cases.
    
    These are pre-built AMTA-style cases for practice.
    """
    return get_all_demo_cases()


@router.get("/featured", response_model=List[Dict[str, Any]])
async def list_featured_cases(limit: int = 3):
    """
    Get featured/popular cases for homepage display.
    
    Returns the top N most popular cases marked as featured.
    """
    return get_featured_demo_cases(limit)


@router.get("/demo/{case_id}")
async def get_demo_case(case_id: str):
    """
    Get full details for a specific demo case.
    """
    case = get_demo_case_by_id(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Demo case not found")
    return case


@router.get("/", response_model=List[CaseMetadataResponse])
async def list_cases(include_demo: bool = True):
    """
    List all cases (uploaded + demo cases).
    
    Set include_demo=false to only show uploaded cases.
    """
    results = []
    
    # Add demo cases first if requested
    if include_demo:
        for demo in get_all_demo_cases():
            results.append(
                CaseMetadataResponse(
                    case_id=demo["id"],
                    name=demo["title"],
                    source_type="demo",
                    source_filename="Built-in Demo Case",
                    created_at="2024-01-01T00:00:00",
                    processed=True,  # Demo cases are always ready
                    fact_count=7,  # Approximate
                    witness_count=demo["witness_count"],
                    exhibit_count=demo["exhibit_count"],
                    embedding_count=0
                )
            )
    
    # Try Supabase for uploaded cases
    case_repo = CaseRepository()
    try:
        db_cases = case_repo.get_all_cases()
        if db_cases:
            for c in db_cases:
                witnesses = case_repo.get_witnesses(c.id)
                cache_case = _cases.get(c.id)
                results.append(
                    CaseMetadataResponse(
                        case_id=c.id,
                        name=c.title,
                        source_type=c.case_type or "unknown",
                        source_filename=c.description or "",
                        created_at=c.created_at.isoformat(),
                        processed=c.embedding_status == "completed",
                        fact_count=len(c.facts) if c.facts else 0,
                        witness_count=len(witnesses),
                        exhibit_count=len(c.exhibits) if c.exhibits else 0,
                        embedding_count=cache_case.embedding_count if cache_case else 0
                    )
                )
    except Exception as e:
        logger.warning(f"Failed to query cases from database: {e}")
    
    # Also add in-memory uploaded cases
    for case in _cases.values():
        # Skip if already added from DB
        if any(r.case_id == case.case_id for r in results):
            continue
        results.append(
            CaseMetadataResponse(
                case_id=case.case_id,
                name=case.name,
                source_type=case.source_type,
                source_filename=case.source_filename,
                created_at=case.created_at.isoformat(),
                processed=case.processed,
                fact_count=case.fact_count,
                witness_count=case.witness_count,
                exhibit_count=case.exhibit_count,
                embedding_count=case.embedding_count
            )
        )
    
    return results


@router.get("/{case_id}", response_model=CaseMetadataResponse)
async def get_case_metadata(case_id: str):
    """Get case metadata."""
    if case_id not in _cases:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = _cases[case_id]
    
    return CaseMetadataResponse(
        case_id=case.case_id,
        name=case.name,
        source_type=case.source_type,
        source_filename=case.source_filename,
        created_at=case.created_at.isoformat(),
        processed=case.processed,
        fact_count=case.fact_count,
        witness_count=case.witness_count,
        exhibit_count=case.exhibit_count,
        embedding_count=case.embedding_count
    )


@router.get("/{case_id}/details", response_model=CaseDetailResponse)
async def get_case_details(case_id: str):
    """Get full case details including facts, witnesses, and exhibits."""
    if case_id not in _cases:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = _cases[case_id]
    
    # Convert to response models
    facts = [
        FactItem(
            id=f.get("id", ""),
            fact_type=f.get("fact_type", "evidence"),
            content=f.get("content", ""),
            source=f.get("source", ""),
            page=f.get("page")
        )
        for f in case.facts
    ]
    
    witnesses = [
        WitnessItem(
            id=w.get("id", ""),
            name=w.get("name", ""),
            called_by=w.get("called_by", "plaintiff"),
            affidavit=w.get("affidavit", ""),
            role_description=w.get("role_description", ""),
            key_facts=w.get("key_facts", [])
        )
        for w in case.witnesses
    ]
    
    exhibits = [
        ExhibitItem(
            id=e.get("id", ""),
            exhibit_number=e.get("exhibit_number", ""),
            title=e.get("title", ""),
            description=e.get("description", ""),
            content_type=e.get("content_type", "document"),
            pre_admitted=e.get("pre_admitted", False)
        )
        for e in case.exhibits
    ]
    
    return CaseDetailResponse(
        case_id=case.case_id,
        name=case.name,
        source_type=case.source_type,
        created_at=case.created_at.isoformat(),
        case_type=case.case_type,
        charge=case.charge,
        plaintiff=case.plaintiff,
        defendant=case.defendant,
        synopsis=case.synopsis,
        facts=facts,
        witnesses=witnesses,
        exhibits=exhibits,
        stipulations=case.stipulations,
        jury_instructions=case.jury_instructions,
        special_instructions=case.special_instructions,
        indictment=case.indictment,
        relevant_law=case.relevant_law,
        motions_in_limine=case.motions_in_limine,
        witness_calling_restrictions=case.witness_calling_restrictions,
    )


@router.get("/{case_id}/status", response_model=ProcessingStatusResponse)
async def get_processing_status(case_id: str):
    """Get embedding processing status for a case."""
    if case_id not in _processing_status:
        raise HTTPException(status_code=404, detail="Processing status not found")
    
    status = _processing_status[case_id]
    
    return ProcessingStatusResponse(
        case_id=status.case_id,
        status=status.status,
        progress=status.progress,
        message=status.message,
        started_at=status.started_at.isoformat() if status.started_at else None,
        completed_at=status.completed_at.isoformat() if status.completed_at else None,
        error=status.error
    )


@router.post("/{case_id}/reprocess")
async def reprocess_case(case_id: str, background_tasks: BackgroundTasks):
    """Re-process embeddings for a case."""
    if case_id not in _cases:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = _cases[case_id]
    
    # Reset embedding count
    case.embedding_count = 0
    case.processed = False
    
    # Reset status
    _processing_status[case_id] = ProcessingStatus(case_id)
    
    # Start background processing
    background_tasks.add_task(process_case_embeddings, case_id)
    
    return {
        "case_id": case_id,
        "status": "reprocessing",
        "message": "Embedding processing restarted"
    }


@router.delete("/{case_id}")
async def delete_case(
    case_id: str,
    delete_embeddings: bool = True,
):
    """
    Delete a case and optionally its embeddings.
    """
    # Check both in-memory cache and database
    case_repo = CaseRepository()
    db_case = case_repo.get_case(case_id)
    
    if case_id not in _cases and not db_case:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = _cases.get(case_id)
    witnesses = case.witnesses if case else []
    
    if delete_embeddings:
        try:
            pinecone = get_pinecone()
            
            # Delete case facts
            pinecone.delete(
                namespace=Namespace.CASE_FACTS,
                filter={"case_id": case_id}
            )
            
            # Delete witness memories
            for witness in witnesses:
                witness_namespace = get_witness_namespace(witness.get("id", ""))
                pinecone.delete_namespace(witness_namespace)
                
        except Exception as e:
            logger.warning(f"Failed to delete Pinecone embeddings: {e}")
    
    # Delete from Supabase
    try:
        case_repo.delete_case(case_id)
        logger.info(f"Case {case_id} deleted from database")
    except Exception as e:
        logger.warning(f"Failed to delete case from database: {e}")
    
    # Remove from in-memory storage
    if case_id in _cases:
        del _cases[case_id]
    if case_id in _processing_status:
        del _processing_status[case_id]
    
    return {
        "case_id": case_id,
        "deleted": True,
        "embeddings_deleted": delete_embeddings
    }


@router.get("/{case_id}/witnesses")
async def get_case_witnesses(case_id: str):
    """Get all witnesses for a case."""
    if case_id not in _cases:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = _cases[case_id]
    
    return {
        "case_id": case_id,
        "witness_count": len(case.witnesses),
        "witnesses": [
            {
                "id": w.get("id"),
                "name": w.get("name"),
                "called_by": w.get("called_by"),
                "role_description": w.get("role_description", ""),
                "key_facts_count": len(w.get("key_facts", []))
            }
            for w in case.witnesses
        ]
    }


@router.get("/{case_id}/exhibits")
async def get_case_exhibits(case_id: str):
    """Get all exhibits for a case."""
    if case_id not in _cases:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = _cases[case_id]
    
    return {
        "case_id": case_id,
        "exhibit_count": len(case.exhibits),
        "exhibits": [
            {
                "id": e.get("id"),
                "exhibit_number": e.get("exhibit_number"),
                "title": e.get("title"),
                "content_type": e.get("content_type"),
                "pre_admitted": e.get("pre_admitted", False)
            }
            for e in case.exhibits
        ]
    }


@router.get("/{case_id}/facts")
async def get_case_facts(case_id: str, fact_type: Optional[str] = None):
    """
    Get all facts for a case, optionally filtered by type.
    
    Fact types: evidence, stipulation, background, legal_standard
    """
    if case_id not in _cases:
        raise HTTPException(status_code=404, detail="Case not found")
    
    case = _cases[case_id]
    
    facts = case.facts
    if fact_type:
        facts = [f for f in facts if f.get("fact_type") == fact_type]
    
    return {
        "case_id": case_id,
        "fact_count": len(facts),
        "filter": fact_type,
        "facts": [
            {
                "id": f.get("id"),
                "fact_type": f.get("fact_type"),
                "content": f.get("content"),
                "source": f.get("source")
            }
            for f in facts
        ]
    }


# =============================================================================
# FILE-BASED CASE MATERIALS
# =============================================================================

# Directory where case files are stored
CASE_FILES_DIR = Path(__file__).parent.parent / "data" / "case_files"

# Supported file types and their MIME types
FILE_TYPES = {
    # Documents
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".rtf": "application/rtf",
    # Spreadsheets
    ".xls": "application/vnd.ms-excel",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".csv": "text/csv",
    # Images
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
    ".svg": "image/svg+xml",
    # Other
    ".json": "application/json",
}


@router.get("/{case_id}/files")
async def list_case_files(case_id: str):
    """
    List all available files for a case (PDFs, images, docs).
    
    Files should be placed in: backend/app/data/case_files/{case_folder}/
    """
    # Map case_id to folder name
    case_folder_map = {
        "case_state_v_avery": "state_v_avery",
        "case_harper_v_zenith": "harper_v_zenith",
    }
    
    folder_name = case_folder_map.get(case_id, case_id)
    case_dir = CASE_FILES_DIR / folder_name
    
    if not case_dir.exists():
        return {
            "case_id": case_id,
            "files": [],
            "message": f"No files directory found. Add files to: {case_dir}"
        }
    
    files = []
    for file_path in case_dir.iterdir():
        if file_path.is_file() and file_path.suffix.lower() in FILE_TYPES:
            files.append({
                "filename": file_path.name,
                "type": FILE_TYPES.get(file_path.suffix.lower(), "application/octet-stream"),
                "size": file_path.stat().st_size,
                "url": f"/api/case/{case_id}/files/{file_path.name}"
            })
    
    # Sort by filename
    files.sort(key=lambda x: x["filename"])
    
    return {
        "case_id": case_id,
        "file_count": len(files),
        "files": files
    }


@router.get("/{case_id}/files/{filename}")
async def get_case_file(case_id: str, filename: str):
    """
    Serve a specific case file (PDF, image, doc).
    
    This allows the frontend to open/display case materials directly.
    """
    # Map case_id to folder name
    case_folder_map = {
        "case_state_v_avery": "state_v_avery",
        "case_harper_v_zenith": "harper_v_zenith",
    }
    
    folder_name = case_folder_map.get(case_id, case_id)
    case_dir = CASE_FILES_DIR / folder_name
    file_path = case_dir / filename
    
    # Security: ensure the file is within the case directory
    try:
        file_path = file_path.resolve()
        case_dir_resolved = case_dir.resolve()
        if not str(file_path).startswith(str(case_dir_resolved)):
            raise HTTPException(status_code=403, detail="Access denied")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid file path")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {filename}")
    
    # Get MIME type
    suffix = file_path.suffix.lower()
    media_type = FILE_TYPES.get(suffix, "application/octet-stream")
    
    return FileResponse(
        path=file_path,
        media_type=media_type,
        filename=filename
    )


@router.post("/{case_id}/files/upload")
async def upload_case_file(
    case_id: str,
    file: UploadFile = File(...),
):
    """
    Upload a file to a case's materials folder.
    
    Supports PDFs, images, and documents.
    """
    # Validate file type
    suffix = Path(file.filename).suffix.lower()
    if suffix not in FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {suffix}. Supported: {list(FILE_TYPES.keys())}"
        )
    
    # Map case_id to folder name
    case_folder_map = {
        "case_state_v_avery": "state_v_avery",
        "case_harper_v_zenith": "harper_v_zenith",
    }
    
    folder_name = case_folder_map.get(case_id, case_id)
    case_dir = CASE_FILES_DIR / folder_name
    
    # Create directory if it doesn't exist
    case_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file
    file_path = case_dir / file.filename
    content = await file.read()
    
    with open(file_path, "wb") as f:
        f.write(content)
    
    return {
        "case_id": case_id,
        "filename": file.filename,
        "size": len(content),
        "url": f"/api/case/{case_id}/files/{file.filename}",
        "message": "File uploaded successfully"
    }


# =============================================================================
# SECTION-BASED CASE UPLOAD (for MYLaw and other copyrighted cases)
# =============================================================================

@router.get("/sections")
async def list_case_sections():
    """
    Get the list of case sections for organizing uploads.
    
    Sections include:
    - Case Summary
    - Plaintiff/Prosecution Witnesses
    - Defense Witnesses
    - Exhibits
    - Stipulations
    - Jury Instructions / Legal Standards
    - Rules & Procedures
    """
    return {
        "sections": get_case_sections(),
        "message": "Upload case materials to each section. Materials are copyrighted - download from source and upload here."
    }


@router.get("/sources")
async def list_case_sources():
    """
    Get list of available case sources (MYLaw, etc).
    
    These are metadata entries pointing to external sources.
    Users must download cases from the source website and upload them.
    """
    return {
        "sources": [
            {
                "name": "MYLaw (Maryland Youth & the Law)",
                "url": "https://www.mylaw.org/mock-trial-cases-and-resources",
                "description": "Maryland high school mock trial cases from 2007-present. Includes civil and criminal cases.",
                "copyright_notice": "All case materials are copyrighted. Express permission is required for re-print/distribution/use.",
            }
        ],
        "cases": MYLAW_CASE_SOURCES,
        "instructions": [
            "1. Visit the source website and download the case PDF",
            "2. Select a case from the list or create a new one",
            "3. Upload the PDF to parse it automatically, OR",
            "4. Upload content to individual sections manually"
        ]
    }


@router.post("/{case_id}/sections/{section_id}")
async def upload_section_content(
    case_id: str,
    section_id: str,
    background_tasks: BackgroundTasks,
    file: UploadFile = File(None),
    content: str = Form(None),
    title: str = Form(None),
):
    """
    Upload content to a specific case section.
    
    Files are stored in Supabase Storage with the following structure:
    cases/{case_id}/{section_id}/{filename}
    
    You can upload either:
    - A file (PDF, text, etc.) which will be parsed and stored
    - Raw text content
    
    Section IDs:
    - summary: Case Summary
    - witnesses_plaintiff: Plaintiff/Prosecution Witnesses  
    - witnesses_defense: Defense Witnesses
    - exhibits: Exhibits
    - stipulations: Stipulations
    - jury_instructions: Jury Instructions / Legal Standards
    - rules: Rules & Procedures
    """
    valid_sections = [s["id"] for s in get_case_sections()]
    if section_id not in valid_sections:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid section. Valid sections: {valid_sections}"
        )
    
    if not file and not content:
        raise HTTPException(
            status_code=400,
            detail="Must provide either a file or content"
        )
    
    # Get or create case data
    case_data = get_uploaded_case(case_id)
    if not case_data:
        # Check if it's a known source case
        source_case = None
        for sc in MYLAW_CASE_SOURCES:
            if sc["id"] == case_id:
                source_case = sc
                break
        
        case_data = {
            "id": case_id,
            "title": source_case["title"] if source_case else (title or "Uploaded Case"),
            "case_type": source_case["case_type"] if source_case else "unknown",
            "source": source_case["source"] if source_case else "User Upload",
            "year": source_case["year"] if source_case else 2024,
            "sections": {},
            "witnesses": [],
            "exhibits": [],
            "facts": [],
            "stipulations": [],
            "legal_standards": [],
            "storage_files": [],  # Track files stored in Supabase Storage
        }
    
    # Process uploaded content
    section_content = ""
    storage_result = None
    
    if file:
        file_content = await file.read()
        
        # Store file in Supabase Storage (if available)
        try:
            storage_service = get_storage_service()
            if storage_service.is_available:
                storage_result = storage_service.upload_file(
                    case_id=case_id,
                    section=section_id,
                    filename=file.filename,
                    file_content=file_content,
                    content_type=file.content_type,
                )
                
                if storage_result.get("success"):
                    # Track stored file
                    if "storage_files" not in case_data:
                        case_data["storage_files"] = []
                    case_data["storage_files"].append({
                        "path": storage_result["path"],
                        "filename": storage_result["filename"],
                        "original_filename": storage_result["original_filename"],
                        "section": section_id,
                        "size": storage_result["size"],
                        "uploaded_at": storage_result["uploaded_at"],
                    })
            else:
                logger.info("Supabase Storage not configured, skipping file storage")
        except Exception as e:
            logger.warning(f"Failed to store file in Supabase Storage: {e}")
            # Continue processing even if storage fails
        
        if file.filename.endswith(".pdf"):
            # Parse PDF
            try:
                section_content = extract_text_from_pdf(file_content)
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to parse PDF: {e}")
        else:
            # Assume text file
            try:
                section_content = file_content.decode("utf-8")
            except:
                section_content = file_content.decode("latin-1")
    else:
        section_content = content
    
    # Store section content
    case_data["sections"][section_id] = {
        "content": section_content,
        "filename": file.filename if file else None,
        "uploaded_at": datetime.utcnow().isoformat(),
        "storage_path": storage_result["path"] if storage_result and storage_result.get("success") else None,
    }
    
    # Parse section into structured data based on section type
    if section_id in ("witnesses_plaintiff", "witnesses_defense", "witnesses_either"):
        called_by = {
            "witnesses_plaintiff": "prosecution",
            "witnesses_defense": "defense",
            "witnesses_either": "either",
        }[section_id]
        parsed_witnesses = _parse_witness_section(section_content, called_by)
        if parsed_witnesses:
            existing_ids = {w.get("id") for w in case_data.get("witnesses", [])}
            for pw in parsed_witnesses:
                if pw["id"] not in existing_ids:
                    case_data.setdefault("witnesses", []).append(pw)
            _uploaded_cases[case_id] = case_data
            logger.info(f"Parsed {len(parsed_witnesses)} witnesses from section {section_id}")
    elif section_id == "exhibits":
        pass
    elif section_id == "stipulations":
        # Parse stipulations (often numbered list)
        lines = section_content.strip().split("\n")
        stips = []
        for i, line in enumerate(lines):
            line = line.strip()
            if line and len(line) > 10:
                stips.append({"id": f"stip_{i}", "content": line})
        case_data["stipulations"] = stips
    elif section_id == "jury_instructions":
        lines = section_content.strip().split("\n\n")
        standards = []
        for i, para in enumerate(lines):
            para = para.strip()
            if para and len(para) > 20:
                standards.append({"id": f"law_{i}", "content": para})
        case_data["legal_standards"] = standards
    
    # Save case data
    save_uploaded_case(case_id, case_data)
    
    response = {
        "case_id": case_id,
        "section_id": section_id,
        "content_length": len(section_content),
        "sections_complete": len(case_data["sections"]),
        "message": f"Section '{section_id}' uploaded successfully",
    }
    
    if storage_result and storage_result.get("success"):
        response["storage"] = {
            "path": storage_result["path"],
            "filename": storage_result["filename"],
            "size": storage_result["size"],
        }
    
    return response


@router.get("/{case_id}/sections")
async def get_case_section_status(case_id: str):
    """
    Get upload status for all sections of a case.
    
    Shows which sections have been uploaded and which are missing.
    """
    case_data = get_uploaded_case(case_id)
    
    sections = get_case_sections()
    section_status = []
    
    for section in sections:
        uploaded = case_data and section["id"] in case_data.get("sections", {})
        section_status.append({
            "id": section["id"],
            "name": section["name"],
            "description": section["description"],
            "required": section["required"],
            "uploaded": uploaded,
            "content_length": len(case_data["sections"][section["id"]]["content"]) if uploaded else 0,
        })
    
    return {
        "case_id": case_id,
        "case_title": case_data["title"] if case_data else "Not Started",
        "sections": section_status,
        "complete": all(
            s["uploaded"] for s in section_status if s["required"]
        ) if case_data else False,
    }


@router.delete("/{case_id}/sections/{section_id}")
async def delete_section_content(case_id: str, section_id: str):
    """
    Delete content from a specific case section.
    Also removes files from Supabase Storage.
    """
    case_data = get_uploaded_case(case_id)
    
    if not case_data:
        raise HTTPException(status_code=404, detail="Case not found")
    
    if section_id not in case_data.get("sections", {}):
        raise HTTPException(status_code=404, detail="Section not found")
    
    # Delete files from Supabase Storage for this section
    storage_deleted = []
    try:
        storage_service = get_storage_service()
        delete_result = storage_service.delete_case_files(case_id, section_id)
        storage_deleted = delete_result.get("deleted", [])
    except Exception as e:
        logger.warning(f"Failed to delete storage files: {e}")
    
    # Remove from storage_files tracking
    if "storage_files" in case_data:
        case_data["storage_files"] = [
            f for f in case_data["storage_files"]
            if f.get("section") != section_id
        ]
    
    del case_data["sections"][section_id]
    save_uploaded_case(case_id, case_data)
    
    return {
        "case_id": case_id,
        "section_id": section_id,
        "storage_files_deleted": len(storage_deleted),
        "message": "Section deleted"
    }


# =============================================================================
# STORAGE MANAGEMENT ENDPOINTS
# =============================================================================

@router.get("/{case_id}/storage")
async def get_case_storage_info(case_id: str):
    """
    Get storage information for a case including all uploaded files.
    
    Returns a summary of files stored in Supabase Storage organized by section.
    """
    try:
        storage_service = get_storage_service()
        if not storage_service.is_available:
            return {
                "case_id": case_id,
                "storage_available": False,
                "message": "Supabase Storage not configured",
                "total_files": 0,
                "sections": {},
            }
        summary = storage_service.get_case_storage_summary(case_id)
        summary["storage_available"] = True
        return summary
    except Exception as e:
        logger.error(f"Failed to get storage info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get storage info: {e}")


@router.get("/{case_id}/storage/files")
async def list_case_files(case_id: str, section: str = None):
    """
    List all files stored for a case, optionally filtered by section.
    
    Query params:
    - section: Filter by section (summary, witnesses_plaintiff, etc.)
    """
    try:
        storage_service = get_storage_service()
        if not storage_service.is_available:
            return {
                "case_id": case_id,
                "section": section,
                "files": [],
                "count": 0,
                "storage_available": False,
            }
        files = storage_service.list_files(case_id, section)
        return {
            "case_id": case_id,
            "section": section,
            "files": files,
            "count": len(files),
            "storage_available": True,
        }
    except Exception as e:
        logger.error(f"Failed to list files: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list files: {e}")


@router.get("/{case_id}/storage/files/{section}/{filename}/url")
async def get_file_url(
    case_id: str,
    section: str,
    filename: str,
    expires_in: int = 3600,
):
    """
    Get a signed URL for a file (valid for the specified duration).
    
    Args:
    - expires_in: URL validity in seconds (default 1 hour, max 1 week)
    """
    if section not in STORAGE_SECTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid section: {section}")
    
    # Cap expiration at 1 week
    expires_in = min(expires_in, 604800)
    
    try:
        storage_service = get_storage_service()
        url = storage_service.get_signed_url(case_id, section, filename, expires_in)
        
        if not url:
            raise HTTPException(status_code=404, detail="File not found")
        
        return {
            "case_id": case_id,
            "section": section,
            "filename": filename,
            "url": url,
            "expires_in": expires_in,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file URL: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get file URL: {e}")


@router.delete("/{case_id}/storage/files/{section}/{filename}")
async def delete_storage_file(case_id: str, section: str, filename: str):
    """
    Delete a specific file from storage.
    """
    if section not in STORAGE_SECTIONS:
        raise HTTPException(status_code=400, detail=f"Invalid section: {section}")
    
    try:
        storage_service = get_storage_service()
        success = storage_service.delete_file(case_id, section, filename)
        
        if not success:
            raise HTTPException(status_code=404, detail="File not found or could not be deleted")
        
        # Also update local case data
        case_data = get_uploaded_case(case_id)
        if case_data and "storage_files" in case_data:
            case_data["storage_files"] = [
                f for f in case_data["storage_files"]
                if not (f.get("section") == section and f.get("filename") == filename)
            ]
            save_uploaded_case(case_id, case_data)
        
        return {
            "case_id": case_id,
            "section": section,
            "filename": filename,
            "message": "File deleted successfully",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete file: {e}")


@router.delete("/{case_id}/storage")
async def delete_all_case_storage(case_id: str):
    """
    Delete all files stored for a case.
    
    This removes all files from Supabase Storage for the given case.
    """
    try:
        storage_service = get_storage_service()
        result = storage_service.delete_case_files(case_id)
        
        # Update local case data
        case_data = get_uploaded_case(case_id)
        if case_data:
            case_data["storage_files"] = []
            save_uploaded_case(case_id, case_data)
        
        return {
            "case_id": case_id,
            "deleted_count": result["deleted_count"],
            "failed_count": result["failed_count"],
            "message": f"Deleted {result['deleted_count']} files",
        }
    except Exception as e:
        logger.error(f"Failed to delete case storage: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete case storage: {e}")


# =============================================================================
# FETCH CASE FROM SOURCE (MYLaw, etc.)
# =============================================================================

@router.post("/{case_id}/fetch")
async def fetch_case_from_source(
    case_id: str,
    background_tasks: BackgroundTasks,
    pdf_url: str = Form(None),
):
    """
    Fetch a case PDF from its source URL and import it.
    
    For MYLaw cases, this will:
    1. Download the PDF from the provided URL or known source
    2. Parse it using GPT-4 to extract structured data
    3. Store the case for practice
    
    Note: Some cases are password-protected and cannot be fetched automatically.
    """
    # Check if this is a known case source
    source_case = get_case_source_by_id(case_id)
    
    if source_case and source_case.get("password_protected"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "password_protected",
                "message": f"This case ({source_case['title']}) is password-protected. "
                           f"Please download it manually from {source_case['source_url']} "
                           f"after registering with MYLaw, then upload it here.",
                "source_url": source_case["source_url"],
            }
        )
    
    # Determine PDF URL
    fetch_url = pdf_url
    if not fetch_url and source_case:
        # Check if we have known PDF URLs
        pdf_urls = source_case.get("pdf_urls", [])
        if pdf_urls:
            fetch_url = pdf_urls[0]  # Use first available
    
    if not fetch_url:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "no_url",
                "message": "No PDF URL available. Please provide a direct PDF URL or upload the file manually.",
                "source_url": source_case["source_url"] if source_case else None,
            }
        )
    
    # Fetch the PDF
    try:
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(fetch_url)
            response.raise_for_status()
            pdf_content = response.content
    except httpx.HTTPStatusError as e:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "fetch_failed",
                "message": f"Failed to fetch PDF: HTTP {e.response.status_code}. "
                           f"The file may be password-protected or no longer available.",
                "source_url": source_case["source_url"] if source_case else fetch_url,
            }
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "fetch_error",
                "message": f"Error fetching PDF: {str(e)}",
            }
        )
    
    # Verify it's a PDF
    if not pdf_content.startswith(b"%PDF"):
        raise HTTPException(
            status_code=400,
            detail={
                "error": "not_pdf",
                "message": "The fetched content is not a valid PDF. "
                           "The file may be password-protected or require authentication.",
                "source_url": source_case["source_url"] if source_case else fetch_url,
            }
        )
    
    # Parse PDF content (AMTA parser first, GPT-4 fallback)
    case_name = source_case["title"] if source_case else "Fetched Case"
    try:
        parsed_data = parse_pdf_to_case(pdf_content, case_name)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to parse PDF content: {str(e)}"
        )
    
    # Create case data
    case_data = {
        "id": case_id,
        "title": parsed_data.get("name", case_name),
        "case_type": source_case["case_type"] if source_case else "unknown",
        "source": source_case["source"] if source_case else "Fetched",
        "year": source_case["year"] if source_case else 2024,
        "sections": {
            "summary": {
                "content": pdf_text[:5000],  # First part as summary
                "filename": f"{case_id}.pdf",
                "uploaded_at": datetime.utcnow().isoformat(),
            }
        },
        "witnesses": parsed_data.get("witnesses", []),
        "exhibits": parsed_data.get("exhibits", []),
        "facts": parsed_data.get("facts", []),
        "stipulations": parsed_data.get("stipulations", []),
        "legal_standards": parsed_data.get("legal_standards", []),
        "fetched_from": fetch_url,
        "fetched_at": datetime.utcnow().isoformat(),
    }
    
    # Save case
    save_uploaded_case(case_id, case_data)
    
    # Also create in-memory CaseData for session use
    case = CaseData(
        case_id=case_id,
        name=case_data["title"],
        source_type="fetched",
        source_filename=fetch_url
    )
    case.facts = case_data["facts"]
    case.witnesses = case_data["witnesses"]
    case.exhibits = case_data["exhibits"]
    case.stipulations = case_data["stipulations"]
    case.legal_standards = case_data["legal_standards"]
    case.fact_count = len(case.facts)
    case.witness_count = len(case.witnesses)
    case.exhibit_count = len(case.exhibits)
    
    _cases[case_id] = case
    
    # Initialize processing status
    _processing_status[case_id] = ProcessingStatus(case_id)
    
    # Process embeddings in background
    background_tasks.add_task(process_case_embeddings, case_id)
    
    return {
        "case_id": case_id,
        "title": case_data["title"],
        "status": "imported",
        "message": f"Case fetched and imported successfully. Found {len(case.witnesses)} witnesses, {len(case.exhibits)} exhibits.",
        "witness_count": len(case.witnesses),
        "exhibit_count": len(case.exhibits),
        "fact_count": len(case.facts),
    }


@router.get("/{case_id}/fetch-status")
async def get_fetch_info(case_id: str):
    """
    Get information about fetching a case from its source.
    
    Returns whether the case can be auto-fetched, requires manual download, etc.
    """
    source_case = get_case_source_by_id(case_id)
    
    if not source_case:
        return {
            "case_id": case_id,
            "fetchable": False,
            "message": "Unknown case. Please upload a PDF manually.",
        }
    
    if source_case.get("password_protected"):
        return {
            "case_id": case_id,
            "fetchable": False,
            "password_protected": True,
            "title": source_case["title"],
            "source": source_case["source"],
            "source_url": source_case["source_url"],
            "message": f"This case is password-protected. Download manually from {source_case['source']} and upload here.",
            "instructions": [
                f"1. Visit {source_case['source_url']}",
                f"2. Find '{source_case['title']}' ({source_case['year']})",
                "3. Download the PDF (may require registration/password)",
                "4. Upload the PDF using the upload button",
            ],
        }
    
    pdf_urls = source_case.get("pdf_urls", [])
    
    return {
        "case_id": case_id,
        "fetchable": len(pdf_urls) > 0,
        "password_protected": False,
        "title": source_case["title"],
        "source": source_case["source"],
        "source_url": source_case["source_url"],
        "pdf_urls": pdf_urls,
        "message": "This case may be available for direct fetch. Click 'Fetch & Import' to try." if pdf_urls else "No direct PDF links available. Please download manually and upload.",
    }


# =============================================================================
# FAVORITES AND RECENT CASES
# =============================================================================

@router.post("/{case_id}/favorite")
async def toggle_case_favorite(case_id: str):
    """
    Toggle favorite status for a case.
    
    Returns the new favorite status.
    """
    new_status = toggle_favorite(case_id)
    return {
        "case_id": case_id,
        "is_favorite": new_status,
        "message": "Added to favorites" if new_status else "Removed from favorites",
    }


@router.get("/{case_id}/favorite")
async def get_case_favorite_status(case_id: str):
    """Get favorite status for a case."""
    return {
        "case_id": case_id,
        "is_favorite": is_favorite(case_id),
    }


@router.get("/user/favorites")
async def list_favorite_cases():
    """
    Get all favorited cases.
    
    Returns full case details for each favorited case.
    """
    favorite_ids = get_favorite_cases()
    cases = []
    
    for case_id in favorite_ids:
        case = get_demo_case_by_id(case_id)
        if case:
            cases.append({
                "id": case_id,
                "title": case.get("title", "Unknown"),
                "case_type": case.get("case_type", "unknown"),
                "year": case.get("year", 2024),
                "is_favorite": True,
            })
    
    return {
        "count": len(cases),
        "cases": cases,
    }


@router.post("/{case_id}/access")
async def record_case_accessed(case_id: str):
    """
    Record that a case was accessed (for recently accessed tracking).
    
    Call this when a user opens a case for practice.
    """
    record_case_access(case_id)
    return {
        "case_id": case_id,
        "recorded": True,
    }


@router.get("/user/recent")
async def list_recent_cases(limit: int = 5):
    """
    Get recently accessed cases.
    
    Returns cases in order of most recent access.
    """
    recent = get_recently_accessed(limit)
    cases = []
    
    for entry in recent:
        case_id = entry["case_id"]
        case = get_demo_case_by_id(case_id)
        if case:
            cases.append({
                "id": case_id,
                "title": case.get("title", "Unknown"),
                "case_type": case.get("case_type", "unknown"),
                "year": case.get("year", 2024),
                "accessed_at": entry["accessed_at"],
                "is_favorite": is_favorite(case_id),
            })
    
    return {
        "count": len(cases),
        "cases": cases,
    }


@router.get("/user/homepage")
async def get_homepage_cases():
    """
    Get cases for homepage display.
    
    Priority:
    1. Favorited cases (up to 3)
    2. Recently accessed cases (up to 3)
    3. Featured/popular cases (fill remaining)
    """
    homepage_cases = []
    seen_ids = set()
    
    # Add favorites first
    favorite_ids = get_favorite_cases()
    for case_id in favorite_ids[:3]:
        case = get_demo_case_by_id(case_id)
        if case and case_id not in seen_ids:
            homepage_cases.append({
                "id": case_id,
                "title": case.get("title", "Unknown"),
                "description": case.get("description", ""),
                "case_type": case.get("case_type", "unknown"),
                "year": case.get("year", 2024),
                "difficulty": case.get("difficulty", "intermediate"),
                "is_favorite": True,
                "source": "favorite",
            })
            seen_ids.add(case_id)
    
    # Add recently accessed
    recent = get_recently_accessed(3)
    for entry in recent:
        case_id = entry["case_id"]
        if case_id not in seen_ids:
            case = get_demo_case_by_id(case_id)
            if case:
                homepage_cases.append({
                    "id": case_id,
                    "title": case.get("title", "Unknown"),
                    "description": case.get("description", ""),
                    "case_type": case.get("case_type", "unknown"),
                    "year": case.get("year", 2024),
                    "difficulty": case.get("difficulty", "intermediate"),
                    "is_favorite": is_favorite(case_id),
                    "source": "recent",
                    "accessed_at": entry["accessed_at"],
                })
                seen_ids.add(case_id)
    
    # Fill with featured cases if needed
    if len(homepage_cases) < 3:
        featured = get_featured_demo_cases(limit=3 - len(homepage_cases))
        for case in featured:
            case_id = case["id"]
            if case_id not in seen_ids:
                homepage_cases.append({
                    **case,
                    "is_favorite": is_favorite(case_id),
                    "source": "featured",
                })
                seen_ids.add(case_id)
    
    return {
        "cases": homepage_cases[:6],  # Max 6 on homepage
        "has_favorites": len(favorite_ids) > 0,
        "has_recent": len(recent) > 0,
    }


# =============================================================================
# DELETE CASE
# =============================================================================

@router.delete("/{case_id}/materials")
async def delete_case_materials(case_id: str):
    """
    Delete uploaded case materials.
    
    This removes the case from the uploaded cases list and deletes
    all associated files from Supabase Storage.
    
    Note: MYLaw source cases cannot be deleted, only their uploaded content.
    """
    # Check if it's an uploaded case
    uploaded_case = get_uploaded_case(case_id)
    
    if not uploaded_case:
        # Check if it's a source case (MYLaw)
        source_case = get_case_source_by_id(case_id)
        if source_case:
            return {
                "case_id": case_id,
                "deleted": False,
                "message": "This is a source case template. Upload your own materials to practice.",
            }
        raise HTTPException(status_code=404, detail="Case not found")
    
    # Delete files from Supabase Storage
    storage_deleted = 0
    try:
        storage_service = get_storage_service()
        result = storage_service.delete_case_files(case_id)
        storage_deleted = result.get("deleted_count", 0)
        logger.info(f"Deleted {storage_deleted} files from Supabase Storage for case {case_id}")
    except Exception as e:
        logger.warning(f"Failed to delete storage files for case {case_id}: {e}")
    
    # Delete the uploaded case
    deleted = delete_uploaded_case(case_id)
    
    # Also clean up from in-memory cache
    if case_id in _cases:
        del _cases[case_id]
    if case_id in _processing_status:
        del _processing_status[case_id]
    
    return {
        "case_id": case_id,
        "deleted": deleted,
        "storage_files_deleted": storage_deleted,
        "message": "Case materials deleted successfully" if deleted else "Failed to delete",
    }


# =============================================================================
# STORAGE SYNC - Rebuild case records from Supabase Storage
# =============================================================================

@router.post("/admin/sync-storage")
async def sync_storage_to_database():
    """
    Scan Supabase Storage for existing files and rebuild uploaded_cases
    records in the database for any cases that have files but no record.
    
    This is useful after the database tables are first created, to recover
    case data from files that were already uploaded to storage.
    """
    try:
        storage_service = get_storage_service()
        if not storage_service.is_available:
            return {"synced": 0, "message": "Supabase Storage not available"}
    except Exception:
        return {"synced": 0, "message": "Supabase Storage not available"}
    
    synced = []
    
    from ..data.demo_cases import AMTA_CASE_SOURCES
    # Check all known case sources
    all_sources = AMTA_CASE_SOURCES + MYLAW_CASE_SOURCES
    for source_case in all_sources:
        case_id = source_case["id"]
        
        try:
            files = storage_service.list_files(case_id)
            if not files:
                continue
            
            # Check if we already have a record with all storage sections covered
            existing = get_uploaded_case(case_id)
            file_sections = set(f.get("section", "other") for f in files)
            existing_sections = set(existing.get("sections", {}).keys()) if existing else set()
            if existing and file_sections.issubset(existing_sections):
                continue  # All storage sections already tracked
            
            # Build case data from storage files
            sections = {}
            storage_files = []
            for f in files:
                section = f.get("section", "other")
                if section not in sections:
                    sections[section] = {
                        "content": f"[File in Supabase Storage: {f['name']}]",
                        "filename": f["name"],
                        "uploaded_at": f.get("created_at", ""),
                        "storage_path": f["path"],
                    }
                storage_files.append({
                    "path": f["path"],
                    "filename": f["name"],
                    "original_filename": f["name"],
                    "section": section,
                    "size": f.get("size", 0),
                    "uploaded_at": f.get("created_at", ""),
                })
            
            # Merge with existing data if available
            if existing:
                case_data = existing
                for sec_id, sec_data in sections.items():
                    if sec_id not in case_data.get("sections", {}):
                        case_data.setdefault("sections", {})[sec_id] = sec_data
                case_data.setdefault("storage_files", []).extend(storage_files)
            else:
                case_data = {
                    "id": case_id,
                    "title": source_case["title"],
                    "case_type": source_case["case_type"],
                    "source": source_case["source"],
                    "year": source_case["year"],
                    "difficulty": source_case.get("difficulty", "intermediate"),
                    "description": source_case.get("description", ""),
                    "sections": sections,
                    "witnesses": [],
                    "exhibits": [],
                    "facts": [],
                    "stipulations": [],
                    "legal_standards": [],
                    "storage_files": storage_files,
                }
            
            save_uploaded_case(case_id, case_data)
            synced.append({
                "case_id": case_id,
                "title": source_case["title"],
                "files": len(files),
                "sections": list(sections.keys()),
            })
            
        except Exception as e:
            logger.warning(f"Failed to sync case {case_id}: {e}")
    
    return {
        "synced": len(synced),
        "cases": synced,
        "message": f"Synced {len(synced)} cases from Supabase Storage",
    }
