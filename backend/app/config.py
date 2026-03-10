"""
Backend Configuration

Per ARCHITECTURE.md - LLM Access:
- API keys (OpenAI, Whisper, TTS) are stored ONLY in backend environment variables
- Agents never hold API keys or call OpenAI directly
- Frontend communicates with backend via REST or WebRTC; no keys in frontend

Required Environment Variables:
- OPENAI_API_KEY: OpenAI API key for GPT-4.1, Whisper, and TTS
- PINECONE_API_KEY: Pinecone API key for vector storage
- DATABASE_URL: Supabase PostgreSQL connection string

Optional Environment Variables:
- SUPABASE_URL: Supabase project URL (for Supabase client features)
- SUPABASE_ANON_KEY: Supabase anonymous key (for Supabase client features)
- SUPABASE_SERVICE_ROLE_KEY: Supabase service role key (for admin operations)

Optional Environment Variables:
- PINECONE_INDEX_NAME: Pinecone index name (default: "mock-trial")
- LOG_LEVEL: Logging level (default: "INFO")
- DEBUG: Enable debug mode (default: "false")
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Config:
    """
    Application configuration loaded from environment variables.
    
    Per ARCHITECTURE.md: API keys stored only in backend environment variables.
    """
    
    # OpenAI API (required)
    # Used for: GPT-4.1 (all agents), Whisper (STT), TTS
    openai_api_key: str
    
    # Pinecone (required)
    # Used for: Case facts, witness memory, transcript storage
    pinecone_api_key: str
    pinecone_index_name: str
    
    # Supabase Database (required)
    database_url: str  # Supabase PostgreSQL connection string
    
    # Optional settings
    log_level: str = "INFO"
    debug: bool = False
    
    # Supabase API (optional - only needed for Supabase client features)
    supabase_url: Optional[str] = None
    supabase_anon_key: Optional[str] = None
    supabase_service_role_key: Optional[str] = None
    
    @classmethod
    def from_env(cls) -> "Config":
        """
        Load configuration from environment variables.
        
        Raises:
            ValueError: If required environment variables are missing
        """
        missing = []
        
        openai_api_key = os.environ.get("OPENAI_API_KEY")
        if not openai_api_key:
            missing.append("OPENAI_API_KEY")
        
        pinecone_api_key = os.environ.get("PINECONE_API_KEY")
        if not pinecone_api_key:
            missing.append("PINECONE_API_KEY")
        
        database_url = os.environ.get("DATABASE_URL")
        if not database_url:
            missing.append("DATABASE_URL")
        
        # Supabase API keys are optional (only needed for Supabase client features)
        supabase_url = os.environ.get("SUPABASE_URL")
        supabase_anon_key = os.environ.get("SUPABASE_ANON_KEY")
        supabase_service_role_key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Per ARCHITECTURE.md, API keys must be stored in backend environment variables. "
                "Create a .env file with the required variables."
            )
        
        return cls(
            openai_api_key=openai_api_key,
            pinecone_api_key=pinecone_api_key,
            pinecone_index_name=os.environ.get("PINECONE_INDEX_NAME", "mock-trial"),
            database_url=database_url,
            supabase_url=supabase_url,
            supabase_anon_key=supabase_anon_key,
            supabase_service_role_key=supabase_service_role_key,
            log_level=os.environ.get("LOG_LEVEL", "INFO"),
            debug=os.environ.get("DEBUG", "false").lower() == "true",
        )
    
    def validate(self) -> bool:
        """
        Validate that configuration is complete.
        
        Returns:
            True if valid, raises ValueError otherwise
        """
        if not self.openai_api_key.startswith("sk-"):
            logger.warning("OPENAI_API_KEY does not start with 'sk-', may be invalid")
        
        return True


# Singleton configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """
    Get the application configuration.
    
    Loads from environment variables on first call.
    
    Returns:
        Config instance
        
    Raises:
        ValueError: If required environment variables are missing
    """
    global _config
    if _config is None:
        _config = Config.from_env()
        _config.validate()
        logger.info("Configuration loaded from environment variables")
    return _config


def get_openai_api_key() -> str:
    """
    Get OpenAI API key from configuration.
    
    Per ARCHITECTURE.md: This is the ONLY place API keys should be retrieved.
    Services and utilities should call this function, not read os.environ directly.
    """
    return get_config().openai_api_key


def get_pinecone_api_key() -> str:
    """Get Pinecone API key from configuration."""
    return get_config().pinecone_api_key


def get_supabase_url() -> str:
    """Get Supabase project URL from configuration."""
    return get_config().supabase_url


def get_supabase_anon_key() -> str:
    """Get Supabase anonymous key from configuration."""
    return get_config().supabase_anon_key


def get_supabase_service_role_key() -> str:
    """Get Supabase service role key from configuration."""
    return get_config().supabase_service_role_key


def get_database_url() -> str:
    """Get Supabase PostgreSQL connection URL from configuration."""
    return get_config().database_url


# =============================================================================
# MODEL TIER CONFIGURATION
# =============================================================================

import os as _os

MODEL_FULL = _os.environ.get("LLM_MODEL_FULL", "gpt-4.1")
MODEL_MID = _os.environ.get("LLM_MODEL_MID", "gpt-4.1-mini")
MODEL_NANO = _os.environ.get("LLM_MODEL_NANO", "gpt-4.1-nano")

ENABLE_STRATEGIC_ANALYSIS = (
    _os.environ.get("ENABLE_STRATEGIC_ANALYSIS", "false").lower() == "true"
)
