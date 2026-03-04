"""
Mock Trial AI Services

Per ARCHITECTURE.md:
- Backend responsibilities: Session lifecycle, Agent orchestration, 
  Audio routing, Trial state enforcement, Scoring persistence
"""

from .whisper import (
    WhisperService,
    TranscriptionSegment,
    TranscriptionSession,
    TranscriptionStatus,
    SilenceDetector,
    create_whisper_service,
    contains_filler_words,
    contains_pause_markers,
    FILLER_WORDS,
    PAUSE_MARKERS,
)

from .tts import (
    TTSService,
    TTSSegment,
    TTSSession,
    VoicePersona,
    OpenAIVoice,
    create_tts_service,
    create_judge_persona,
    create_attorney_persona,
    create_witness_persona,
    create_coach_persona,
    DEFAULT_VOICE_MAPPING,
)

from .pinecone import (
    PineconeClient,
    VectorRecord,
    Namespace,
    get_witness_namespace,
    create_pinecone_client,
)

from .llm_service import (
    LLMService,
    LLMRequest,
    LLMResponse,
    PersonaContext,
    get_llm_service,
    call_llm,
    call_llm_async,
)

from .case_parser import (
    parse_mock_trial_pdf,
    extract_text_from_pdf_bytes,
)

from .vector_retrieval import (
    retrieve_relevant_affidavit,
    retrieve_relevant_facts,
    retrieve_relevant_testimony,
    index_testimony,
    build_retrieval_context,
)

__all__ = [
    # Whisper Service (STT)
    "WhisperService",
    "TranscriptionSegment",
    "TranscriptionSession",
    "TranscriptionStatus",
    "SilenceDetector",
    "create_whisper_service",
    "contains_filler_words",
    "contains_pause_markers",
    "FILLER_WORDS",
    "PAUSE_MARKERS",
    # TTS Service
    "TTSService",
    "TTSSegment",
    "TTSSession",
    "VoicePersona",
    "OpenAIVoice",
    "create_tts_service",
    "create_judge_persona",
    "create_attorney_persona",
    "create_witness_persona",
    "create_coach_persona",
    "DEFAULT_VOICE_MAPPING",
    # Pinecone
    "PineconeClient",
    "VectorRecord",
    "Namespace",
    "get_witness_namespace",
    "create_pinecone_client",
    # LLM Service (Per ARCHITECTURE.md - agents use this, not OpenAI directly)
    "LLMService",
    "LLMRequest",
    "LLMResponse",
    "PersonaContext",
    "get_llm_service",
    "call_llm",
    "call_llm_async",
    # Case Parser
    "parse_mock_trial_pdf",
    "extract_text_from_pdf_bytes",
    # Vector Retrieval
    "retrieve_relevant_affidavit",
    "retrieve_relevant_facts",
    "retrieve_relevant_testimony",
    "index_testimony",
    "build_retrieval_context",
]
