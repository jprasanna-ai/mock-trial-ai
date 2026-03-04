"""
Database layer for Mock Trial AI

Provides Supabase client for database operations and file storage.
Per ARCHITECTURE.md: Data storage in Supabase (PostgreSQL)
"""

from .supabase_client import (
    get_supabase_client,
    init_supabase,
    get_schema_sql,
    Tables,
    SupabaseSessionRepository,
    SupabaseScoringRepository,
    SupabaseCaseRepository,
    SupabaseUserPreferencesRepository,
    SupabaseUploadedCasesRepository,
)

from .storage import (
    SupabaseStorageService,
    get_storage_service,
    get_case_files_schema_sql,
    VALID_SECTIONS,
    ALLOWED_EXTENSIONS,
)

# Aliases for compatibility
SessionRepository = SupabaseSessionRepository
ScoringRepository = SupabaseScoringRepository
CaseRepository = SupabaseCaseRepository
StorageService = SupabaseStorageService
UserPreferencesRepository = SupabaseUserPreferencesRepository
UploadedCasesRepository = SupabaseUploadedCasesRepository

__all__ = [
    # Supabase client
    "get_supabase_client",
    "init_supabase",
    "get_schema_sql",
    "Tables",
    # Repositories
    "SessionRepository",
    "ScoringRepository",
    "CaseRepository",
    "SupabaseSessionRepository",
    "SupabaseScoringRepository",
    "SupabaseCaseRepository",
    # User preferences & uploaded cases
    "UserPreferencesRepository",
    "UploadedCasesRepository",
    "SupabaseUserPreferencesRepository",
    "SupabaseUploadedCasesRepository",
    # Storage
    "StorageService",
    "SupabaseStorageService",
    "get_storage_service",
    "get_case_files_schema_sql",
    "VALID_SECTIONS",
    "ALLOWED_EXTENSIONS",
]
