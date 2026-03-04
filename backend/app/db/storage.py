"""
Supabase Storage Service

Handles file storage for case materials using Supabase Storage.

Directory Structure:
    cases/
    └── {case_id}/
        ├── summary/
        │   └── {filename}
        ├── witnesses_plaintiff/
        │   └── {filename}
        ├── witnesses_defense/
        │   └── {filename}
        ├── exhibits/
        │   └── {filename}
        ├── stipulations/
        │   └── {filename}
        ├── jury_instructions/
        │   └── {filename}
        └── rules/
            └── {filename}
"""

import os
import logging
import uuid
from typing import Optional, List, Dict, Any, BinaryIO
from datetime import datetime

from .supabase_client import get_supabase_client

logger = logging.getLogger(__name__)


# =============================================================================
# STORAGE CONFIGURATION
# =============================================================================

BUCKET_NAME = "case-materials"

# Valid section types for case materials
VALID_SECTIONS = [
    "summary",
    "special_instructions",
    "indictment",
    "witnesses_plaintiff",
    "witnesses_defense",
    "witnesses_either",
    "exhibits",
    "stipulations",
    "jury_instructions",
    "relevant_law",
    "motions_in_limine",
    "rules",
]

# Allowed file types
ALLOWED_EXTENSIONS = {
    ".pdf": "application/pdf",
    ".txt": "text/plain",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".json": "application/json",
}


# =============================================================================
# STORAGE SERVICE
# =============================================================================

class SupabaseStorageService:
    """
    Service for managing case file storage in Supabase Storage.
    
    Provides:
    - Upload files to case-specific directories
    - List files for a case or section
    - Download files
    - Delete files
    - Get public/signed URLs
    """
    
    def __init__(self):
        self._initialized = False
        self._client = None
        self.bucket_name = BUCKET_NAME
        self._init_client()
    
    def _init_client(self) -> None:
        """Initialize the Supabase client, handling missing config gracefully."""
        try:
            self._client = get_supabase_client()
            self._ensure_bucket_exists()
            self._initialized = True
        except ValueError as e:
            logger.warning(f"Supabase not configured, storage will be disabled: {e}")
            self._initialized = False
        except Exception as e:
            logger.warning(f"Failed to initialize Supabase storage: {e}")
            self._initialized = False
    
    @property
    def client(self):
        """Get the Supabase client."""
        if not self._initialized or not self._client:
            raise RuntimeError("Supabase Storage not configured. Set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY.")
        return self._client
    
    @property
    def is_available(self) -> bool:
        """Check if storage service is available."""
        return self._initialized and self._client is not None
    
    def _ensure_bucket_exists(self) -> None:
        """Ensure the storage bucket exists."""
        try:
            buckets = self.client.storage.list_buckets()
            bucket_names = [b.name for b in buckets]
            
            if self.bucket_name not in bucket_names:
                self.client.storage.create_bucket(
                    self.bucket_name,
                    options={
                        "public": False,  # Keep files private, use signed URLs
                        "file_size_limit": 52428800,  # 50MB limit
                        "allowed_mime_types": list(ALLOWED_EXTENSIONS.values()),
                    }
                )
                logger.info(f"Created storage bucket: {self.bucket_name}")
            else:
                logger.debug(f"Storage bucket exists: {self.bucket_name}")
        except Exception as e:
            logger.warning(f"Could not verify bucket existence: {e}")
    
    def _get_file_path(self, case_id: str, section: str, filename: str) -> str:
        """
        Generate the storage path for a file.
        
        Format: cases/{case_id}/{section}/{filename}
        """
        # Sanitize inputs
        safe_case_id = case_id.replace("/", "_").replace("\\", "_")
        safe_section = section if section in VALID_SECTIONS else "other"
        safe_filename = filename.replace("/", "_").replace("\\", "_")
        
        return f"cases/{safe_case_id}/{safe_section}/{safe_filename}"
    
    def _get_extension(self, filename: str) -> str:
        """Get the file extension from filename."""
        ext = os.path.splitext(filename)[1].lower()
        return ext if ext else ".bin"
    
    def upload_file(
        self,
        case_id: str,
        section: str,
        filename: str,
        file_content: bytes,
        content_type: str = None,
    ) -> Dict[str, Any]:
        """
        Upload a file to Supabase Storage.
        
        Args:
            case_id: The case identifier
            section: The section type (summary, exhibits, etc.)
            filename: Original filename
            file_content: File content as bytes
            content_type: MIME type (auto-detected if not provided)
        
        Returns:
            Dict with upload result including path and URL
        """
        if section not in VALID_SECTIONS:
            section = "other"
        
        # Generate unique filename to avoid conflicts
        ext = self._get_extension(filename)
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        unique_filename = f"{timestamp}_{uuid.uuid4().hex[:8]}{ext}"
        
        # Store original filename in metadata
        original_name = filename
        
        file_path = self._get_file_path(case_id, section, unique_filename)
        
        # Detect content type
        if not content_type:
            content_type = ALLOWED_EXTENSIONS.get(ext, "application/octet-stream")
        
        try:
            result = self.client.storage.from_(self.bucket_name).upload(
                path=file_path,
                file=file_content,
                file_options={
                    "content-type": content_type,
                    "x-upsert": "true",
                }
            )
            
            logger.info(f"Uploaded file: {file_path}")
            
            return {
                "success": True,
                "path": file_path,
                "filename": unique_filename,
                "original_filename": original_name,
                "case_id": case_id,
                "section": section,
                "content_type": content_type,
                "size": len(file_content),
                "uploaded_at": datetime.utcnow().isoformat(),
            }
        except Exception as e:
            logger.error(f"Failed to upload file: {e}")
            return {
                "success": False,
                "error": str(e),
                "path": file_path,
            }
    
    def download_file(self, case_id: str, section: str, filename: str) -> Optional[bytes]:
        """
        Download a file from Supabase Storage.
        
        Returns the file content as bytes, or None if not found.
        """
        file_path = self._get_file_path(case_id, section, filename)
        
        try:
            result = self.client.storage.from_(self.bucket_name).download(file_path)
            return result
        except Exception as e:
            logger.error(f"Failed to download file {file_path}: {e}")
            return None
    
    def get_signed_url(
        self,
        case_id: str,
        section: str,
        filename: str,
        expires_in: int = 3600,
    ) -> Optional[str]:
        """
        Get a signed URL for a file (valid for expires_in seconds).
        
        This allows temporary access to private files.
        """
        file_path = self._get_file_path(case_id, section, filename)
        
        try:
            result = self.client.storage.from_(self.bucket_name).create_signed_url(
                path=file_path,
                expires_in=expires_in,
            )
            return result.get("signedURL")
        except Exception as e:
            logger.error(f"Failed to get signed URL for {file_path}: {e}")
            return None
    
    def list_files(
        self,
        case_id: str,
        section: str = None,
    ) -> List[Dict[str, Any]]:
        """
        List files for a case, optionally filtered by section.
        
        Returns list of file metadata.
        """
        # Build the path prefix
        safe_case_id = case_id.replace("/", "_").replace("\\", "_")
        
        if section and section in VALID_SECTIONS:
            prefix = f"cases/{safe_case_id}/{section}"
        else:
            prefix = f"cases/{safe_case_id}"
        
        try:
            # List all files under the prefix
            files = []
            
            if section:
                # List files in specific section
                result = self.client.storage.from_(self.bucket_name).list(prefix)
                for item in result:
                    if item.get("name"):
                        files.append({
                            "name": item["name"],
                            "path": f"{prefix}/{item['name']}",
                            "section": section,
                            "case_id": case_id,
                            "size": item.get("metadata", {}).get("size"),
                            "created_at": item.get("created_at"),
                            "updated_at": item.get("updated_at"),
                        })
            else:
                # List all sections
                for sec in VALID_SECTIONS:
                    sec_prefix = f"cases/{safe_case_id}/{sec}"
                    try:
                        result = self.client.storage.from_(self.bucket_name).list(sec_prefix)
                        for item in result:
                            if item.get("name"):
                                files.append({
                                    "name": item["name"],
                                    "path": f"{sec_prefix}/{item['name']}",
                                    "section": sec,
                                    "case_id": case_id,
                                    "size": item.get("metadata", {}).get("size"),
                                    "created_at": item.get("created_at"),
                                    "updated_at": item.get("updated_at"),
                                })
                    except Exception:
                        pass  # Section folder doesn't exist
            
            return files
        except Exception as e:
            logger.error(f"Failed to list files for {case_id}: {e}")
            return []
    
    def delete_file(self, case_id: str, section: str, filename: str) -> bool:
        """
        Delete a specific file.
        
        Returns True if deleted successfully.
        """
        file_path = self._get_file_path(case_id, section, filename)
        
        try:
            self.client.storage.from_(self.bucket_name).remove([file_path])
            logger.info(f"Deleted file: {file_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    def delete_case_files(self, case_id: str, section: str = None) -> Dict[str, Any]:
        """
        Delete all files for a case, or for a specific section.
        
        Returns summary of deleted files.
        """
        files = self.list_files(case_id, section)
        deleted = []
        failed = []
        
        for file_info in files:
            file_path = file_info["path"]
            try:
                self.client.storage.from_(self.bucket_name).remove([file_path])
                deleted.append(file_path)
            except Exception as e:
                logger.error(f"Failed to delete {file_path}: {e}")
                failed.append({"path": file_path, "error": str(e)})
        
        logger.info(f"Deleted {len(deleted)} files for case {case_id}")
        
        return {
            "case_id": case_id,
            "section": section,
            "deleted_count": len(deleted),
            "failed_count": len(failed),
            "deleted": deleted,
            "failed": failed,
        }
    
    def get_case_storage_summary(self, case_id: str) -> Dict[str, Any]:
        """
        Get a summary of all files stored for a case.
        
        Returns counts and sizes by section.
        """
        files = self.list_files(case_id)
        
        summary = {
            "case_id": case_id,
            "total_files": len(files),
            "total_size": 0,
            "sections": {},
        }
        
        for file_info in files:
            section = file_info.get("section", "other")
            size = file_info.get("size", 0) or 0
            
            if section not in summary["sections"]:
                summary["sections"][section] = {
                    "file_count": 0,
                    "total_size": 0,
                    "files": [],
                }
            
            summary["sections"][section]["file_count"] += 1
            summary["sections"][section]["total_size"] += size
            summary["sections"][section]["files"].append(file_info["name"])
            summary["total_size"] += size
        
        return summary


# =============================================================================
# SINGLETON INSTANCE
# =============================================================================

_storage_service: Optional[SupabaseStorageService] = None


def get_storage_service() -> SupabaseStorageService:
    """Get the storage service singleton."""
    global _storage_service
    if _storage_service is None:
        _storage_service = SupabaseStorageService()
    return _storage_service


# =============================================================================
# SQL FOR CASE FILES METADATA TABLE
# =============================================================================

CASE_FILES_SCHEMA_SQL = """
-- Table to store metadata about uploaded case files
-- The actual files are stored in Supabase Storage

CREATE TABLE IF NOT EXISTS case_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id TEXT NOT NULL,
    section TEXT NOT NULL,
    filename TEXT NOT NULL,
    original_filename TEXT,
    storage_path TEXT NOT NULL,
    content_type TEXT,
    size_bytes BIGINT,
    parsed_content TEXT,  -- Extracted text content for search
    metadata JSONB DEFAULT '{}',
    uploaded_by TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_case_files_case ON case_files(case_id);
CREATE INDEX IF NOT EXISTS idx_case_files_section ON case_files(case_id, section);
CREATE UNIQUE INDEX IF NOT EXISTS idx_case_files_path ON case_files(storage_path);

-- Function to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_case_files_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to auto-update timestamp
DROP TRIGGER IF EXISTS case_files_update_timestamp ON case_files;
CREATE TRIGGER case_files_update_timestamp
    BEFORE UPDATE ON case_files
    FOR EACH ROW
    EXECUTE FUNCTION update_case_files_timestamp();
"""


def get_case_files_schema_sql() -> str:
    """Get SQL to create case_files metadata table."""
    return CASE_FILES_SCHEMA_SQL


# =============================================================================
# TRANSCRIPT STORAGE
# =============================================================================

TRANSCRIPT_BUCKET = "trial-transcripts"

TRANSCRIPT_HISTORY_SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS trial_transcript_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL UNIQUE,
    user_id TEXT NOT NULL DEFAULT 'default',
    case_id TEXT,
    case_name TEXT NOT NULL,
    human_role TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    entry_count INTEGER DEFAULT 0,
    phases_completed TEXT[] DEFAULT '{}',
    storage_path TEXT
);

CREATE INDEX IF NOT EXISTS idx_transcript_history_user ON trial_transcript_history(user_id);
CREATE INDEX IF NOT EXISTS idx_transcript_history_case ON trial_transcript_history(case_id);
"""


def get_transcript_history_schema_sql() -> str:
    return TRANSCRIPT_HISTORY_SCHEMA_SQL


class TranscriptStorageService:
    """Saves and retrieves trial transcripts from Supabase Storage."""

    def __init__(self):
        self._client = None
        self._available = False
        try:
            self._client = get_supabase_client()
            self._ensure_bucket()
            self._available = True
        except Exception as e:
            logger.warning(f"Transcript storage not available: {e}")

    @property
    def is_available(self) -> bool:
        return self._available and self._client is not None

    def _ensure_bucket(self):
        buckets = self._client.storage.list_buckets()
        names = [b.name for b in buckets]
        if TRANSCRIPT_BUCKET not in names:
            self._client.storage.create_bucket(
                TRANSCRIPT_BUCKET,
                options={"public": False, "file_size_limit": 10485760},
            )
            logger.info(f"Created transcript bucket: {TRANSCRIPT_BUCKET}")

    def save_transcript(
        self,
        session_id: str,
        user_id: str,
        case_id: str,
        case_name: str,
        human_role: str,
        transcript: list,
        phases_completed: list[str],
    ) -> bool:
        if not self.is_available:
            return False
        try:
            import json as _json

            path = f"transcripts/{user_id}/{case_id}/{session_id}.json"
            content = _json.dumps({
                "session_id": session_id,
                "case_id": case_id,
                "case_name": case_name,
                "human_role": human_role,
                "entry_count": len(transcript),
                "transcript": transcript,
            }, default=str).encode("utf-8")

            self._client.storage.from_(TRANSCRIPT_BUCKET).upload(
                path, content,
                file_options={"content-type": "application/json", "upsert": "true"},
            )

            self._client.table("trial_transcript_history").upsert({
                "session_id": session_id,
                "user_id": user_id,
                "case_id": case_id,
                "case_name": case_name,
                "human_role": human_role,
                "entry_count": len(transcript),
                "phases_completed": phases_completed,
                "storage_path": path,
                "updated_at": datetime.utcnow().isoformat(),
            }, on_conflict="session_id").execute()

            return True
        except Exception as e:
            logger.warning(f"Failed to save transcript for {session_id}: {e}")
            return False

    def get_transcript(self, session_id: str, user_id: str = "default") -> dict | None:
        if not self.is_available:
            return None
        try:
            import json as _json
            row = (
                self._client.table("trial_transcript_history")
                .select("storage_path")
                .eq("session_id", session_id)
                .single()
                .execute()
            )
            if not row.data or not row.data.get("storage_path"):
                return None
            path = row.data["storage_path"]
            data = self._client.storage.from_(TRANSCRIPT_BUCKET).download(path)
            return _json.loads(data)
        except Exception as e:
            logger.warning(f"Failed to get transcript {session_id}: {e}")
            return None

    def list_transcripts(self, user_id: str = "default") -> list[dict]:
        if not self.is_available:
            return []
        try:
            q = self._client.table("trial_transcript_history").select("*").order("started_at", desc=True)
            if user_id != "default":
                q = q.eq("user_id", user_id)
            result = q.execute()
            return result.data or []
        except Exception as e:
            logger.warning(f"Failed to list transcripts: {e}")
            return []


_transcript_storage: TranscriptStorageService | None = None


def get_transcript_storage() -> TranscriptStorageService:
    global _transcript_storage
    if _transcript_storage is None:
        _transcript_storage = TranscriptStorageService()
    return _transcript_storage
