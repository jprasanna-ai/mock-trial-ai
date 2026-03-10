"""
Supabase Client

Provides Supabase client for database operations using the Supabase API
instead of direct PostgreSQL connection.

Per ARCHITECTURE.md:
- Data storage in Supabase (PostgreSQL)
- API keys stored only in backend environment variables
"""

import os
import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from supabase import create_client, Client

logger = logging.getLogger(__name__)


# =============================================================================
# SUPABASE CLIENT SINGLETON
# =============================================================================

_supabase_client: Optional[Client] = None


def get_supabase_client() -> Client:
    """
    Get the Supabase client singleton.
    
    Uses SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY from environment.
    Service role key is used for backend operations (bypasses RLS).
    """
    global _supabase_client
    
    if _supabase_client is None:
        url = os.environ.get("SUPABASE_URL")
        key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        
        if not url or not key:
            raise ValueError(
                "SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY "
                "must be set in environment variables. "
                "Do NOT use SUPABASE_ANON_KEY for backend operations."
            )
        
        _supabase_client = create_client(url, key)
        logger.info("Supabase client initialized")
    
    return _supabase_client


# =============================================================================
# TABLE NAMES
# =============================================================================

class Tables:
    """Database table names."""
    SESSIONS = "sessions"
    PARTICIPANTS = "participants"
    SCORING_RESULTS = "scoring_results"
    BALLOTS = "ballots"
    CATEGORY_SCORES = "category_scores"
    CASES = "cases"
    WITNESSES = "witnesses"
    TRANSCRIPT_ENTRIES = "transcript_entries"
    PREP_MATERIALS = "prep_materials"
    COACH_CHAT_HISTORY = "coach_chat_history"
    DRILL_SESSIONS = "drill_sessions"
    SPEECH_PRACTICE = "speech_practice"
    CASE_FILES = "case_files"
    USER_FAVORITES = "user_favorites"
    RECENT_CASES = "recent_cases"
    UPLOADED_CASES = "uploaded_cases"
    HIDDEN_CASES = "hidden_cases"
    AGENT_PREP = "agent_prep_materials"


# =============================================================================
# SESSION REPOSITORY
# =============================================================================

class SupabaseSessionRepository:
    """Repository for session operations using Supabase client."""
    
    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()
    
    def create_session(
        self,
        session_id: str,
        status: str = "created",
        case_id: Optional[str] = None,
        human_role: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Create a new session."""
        data = {
            "id": session_id,
            "status": status,
            "created_at": datetime.utcnow().isoformat(),
        }
        if case_id:
            data["case_id"] = case_id
        if human_role:
            data["human_role"] = human_role
        result = self.client.table(Tables.SESSIONS).insert(data).execute()
        return result.data[0] if result.data else data
    
    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get session by ID."""
        result = self.client.table(Tables.SESSIONS).select("*").eq("id", session_id).execute()
        return result.data[0] if result.data else None
    
    def update_session(
        self,
        session_id: str,
        **updates
    ) -> Optional[Dict[str, Any]]:
        """Update session fields."""
        updates["updated_at"] = datetime.utcnow().isoformat()
        result = self.client.table(Tables.SESSIONS).update(updates).eq("id", session_id).execute()
        return result.data[0] if result.data else None
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session."""
        self.client.table(Tables.SESSIONS).delete().eq("id", session_id).execute()
        return True
    
    def add_participant(
        self,
        session_id: str,
        role: str,
        name: str,
        is_human: bool = False,
        participant_id: Optional[str] = None,
        **extra
    ) -> Dict[str, Any]:
        """Add a participant to a session. Auto-generates ID if not provided."""
        pid = participant_id or str(uuid.uuid4())
        serialisable_extra = {}
        for k, v in extra.items():
            if isinstance(v, dict) or isinstance(v, list) or isinstance(v, (str, int, float, bool)) or v is None:
                serialisable_extra[k] = v
        data = {
            "id": pid,
            "session_id": session_id,
            "role": role,
            "name": name,
            "is_human": is_human,
            "created_at": datetime.utcnow().isoformat(),
            **serialisable_extra,
        }
        try:
            result = self.client.table(Tables.PARTICIPANTS).upsert(data, on_conflict="id").execute()
        except Exception:
            result = self.client.table(Tables.PARTICIPANTS).insert(data).execute()
        return result.data[0] if result.data else data
    
    def get_participants(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all participants in a session."""
        result = self.client.table(Tables.PARTICIPANTS).select("*").eq("session_id", session_id).execute()
        return result.data or []


# =============================================================================
# SCORING REPOSITORY
# =============================================================================

class SupabaseScoringRepository:
    """Repository for scoring operations using Supabase client."""
    
    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()
    
    def create_scoring_result(
        self,
        session_id: str,
        participant_id: str,
        participant_role: str,
        overall_average: float,
        final_scores: Dict[str, float],
    ) -> Dict[str, Any]:
        """Create a scoring result."""
        data = {
            "session_id": session_id,
            "participant_id": participant_id,
            "participant_role": participant_role,
            "overall_average": overall_average,
            "final_scores": final_scores,
            "created_at": datetime.utcnow().isoformat(),
        }
        result = self.client.table(Tables.SCORING_RESULTS).insert(data).execute()
        return result.data[0] if result.data else data
    
    def add_ballot(
        self,
        scoring_result_id: str,
        judge_id: str,
        judge_name: str,
        total_score: float,
        average_score: float,
        overall_comments: str = "",
    ) -> Dict[str, Any]:
        """Add a ballot to a scoring result."""
        data = {
            "scoring_result_id": scoring_result_id,
            "judge_id": judge_id,
            "judge_name": judge_name,
            "total_score": total_score,
            "average_score": average_score,
            "overall_comments": overall_comments,
            "created_at": datetime.utcnow().isoformat(),
        }
        result = self.client.table(Tables.BALLOTS).insert(data).execute()
        return result.data[0] if result.data else data
    
    def add_category_score(
        self,
        ballot_id: str,
        category: str,
        score: int,
        justification: str,
    ) -> Dict[str, Any]:
        """Add a category score to a ballot."""
        data = {
            "ballot_id": ballot_id,
            "category": category,
            "score": score,
            "justification": justification,
        }
        result = self.client.table(Tables.CATEGORY_SCORES).insert(data).execute()
        return result.data[0] if result.data else data
    
    def get_scoring_results(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all scoring results for a session."""
        result = self.client.table(Tables.SCORING_RESULTS).select("*").eq("session_id", session_id).execute()
        return result.data or []

    def get_ballots(self, scoring_result_id: str) -> List[Dict[str, Any]]:
        """Get all ballots for a scoring result."""
        result = self.client.table(Tables.BALLOTS).select("*").eq("scoring_result_id", scoring_result_id).execute()
        return result.data or []

    def get_leaderboard(self, session_id: Optional[str] = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top scores, optionally filtered by session."""
        query = self.client.table(Tables.SCORING_RESULTS).select("*")
        if session_id:
            query = query.eq("session_id", session_id)
        result = query.order("overall_average", desc=True).limit(limit).execute()
        return result.data or []


# =============================================================================
# CASE REPOSITORY
# =============================================================================

class SupabaseCaseRepository:
    """Repository for case operations using Supabase client."""
    
    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()
    
    def create_case(
        self,
        case_id: str,
        title: str,
        description: str = "",
        case_type: str = "json",
        facts: List[str] = None,
        exhibits: List[str] = None,
    ) -> Dict[str, Any]:
        """Create a new case."""
        data = {
            "id": case_id,
            "title": title,
            "description": description,
            "case_type": case_type,
            "facts": facts or [],
            "exhibits": exhibits or [],
            "embedding_status": "pending",
            "created_at": datetime.utcnow().isoformat(),
        }
        result = self.client.table(Tables.CASES).insert(data).execute()
        return result.data[0] if result.data else data
    
    def get_case(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Get case by ID."""
        result = self.client.table(Tables.CASES).select("*").eq("id", case_id).execute()
        return result.data[0] if result.data else None
    
    def get_all_cases(self) -> List[Dict[str, Any]]:
        """Get all cases."""
        result = self.client.table(Tables.CASES).select("*").execute()
        return result.data or []
    
    def update_case(self, case_id: str, **updates) -> Optional[Dict[str, Any]]:
        """Update case fields."""
        updates["updated_at"] = datetime.utcnow().isoformat()
        result = self.client.table(Tables.CASES).update(updates).eq("id", case_id).execute()
        return result.data[0] if result.data else None
    
    def delete_case(self, case_id: str) -> bool:
        """Delete a case."""
        self.client.table(Tables.CASES).delete().eq("id", case_id).execute()
        return True
    
    def add_witness(
        self,
        case_id: str,
        witness_id: str,
        name: str,
        affidavit: str = "",
        called_by: str = "plaintiff",
        **extra
    ) -> Dict[str, Any]:
        """Add a witness to a case."""
        data = {
            "id": witness_id,
            "case_id": case_id,
            "name": name,
            "affidavit": affidavit,
            "called_by": called_by,
            **extra
        }
        result = self.client.table(Tables.WITNESSES).insert(data).execute()
        return result.data[0] if result.data else data
    
    def get_witnesses(self, case_id: str) -> List[Dict[str, Any]]:
        """Get all witnesses for a case."""
        result = self.client.table(Tables.WITNESSES).select("*").eq("case_id", case_id).execute()
        return result.data or []


# =============================================================================
# PREP MATERIALS REPOSITORY
# =============================================================================

class SupabasePrepMaterialsRepository:
    """Repository for AI-generated preparation materials using Supabase."""
    
    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()
    
    def get_by_case_id(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Get prep materials for a case."""
        try:
            result = self.client.table(Tables.PREP_MATERIALS).select("*").eq("case_id", case_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.warning(f"Failed to get prep materials: {e}")
            return None
    
    def create(
        self,
        case_id: str,
        case_brief: str = None,
        theory_plaintiff: str = None,
        theory_defense: str = None,
        opening_plaintiff: str = None,
        opening_defense: str = None,
        witness_outlines: List[Dict] = None,
        objection_playbook: Dict = None,
        cross_exam_traps: List[Dict] = None,
        is_complete: bool = False,
        generation_status: Dict = None,
    ) -> Dict[str, Any]:
        """Create prep materials for a case."""
        data = {
            "id": str(uuid.uuid4()),
            "case_id": case_id,
            "case_brief": case_brief,
            "theory_plaintiff": theory_plaintiff,
            "theory_defense": theory_defense,
            "opening_plaintiff": opening_plaintiff,
            "opening_defense": opening_defense,
            "witness_outlines": witness_outlines or [],
            "objection_playbook": objection_playbook,
            "cross_exam_traps": cross_exam_traps or [],
            "is_complete": is_complete,
            "generation_status": generation_status or {},
            "created_at": datetime.utcnow().isoformat(),
        }
        try:
            result = self.client.table(Tables.PREP_MATERIALS).insert(data).execute()
            return result.data[0] if result.data else data
        except Exception as e:
            # Retry without columns that may not exist yet
            if "column" in str(e) and "does not exist" in str(e):
                for col in ("opening_plaintiff", "user_notes"):
                    data.pop(col, None)
                try:
                    result = self.client.table(Tables.PREP_MATERIALS).insert(data).execute()
                    return result.data[0] if result.data else data
                except Exception as e2:
                    logger.error(f"Failed to create prep materials (retry): {e2}")
            else:
                logger.error(f"Failed to create prep materials: {e}")
            return data
    
    def update(self, case_id: str, **updates) -> Optional[Dict[str, Any]]:
        """Update prep materials for a case."""
        updates["updated_at"] = datetime.utcnow().isoformat()
        try:
            result = self.client.table(Tables.PREP_MATERIALS).update(updates).eq("case_id", case_id).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"Failed to update prep materials: {e}")
            return None
    
    def upsert(self, case_id: str, **data) -> Dict[str, Any]:
        """Create or update prep materials."""
        existing = self.get_by_case_id(case_id)
        if existing:
            return self.update(case_id, **data) or existing
        else:
            return self.create(case_id=case_id, **data)
    
    def delete(self, case_id: str) -> bool:
        """Delete prep materials for a case."""
        try:
            self.client.table(Tables.PREP_MATERIALS).delete().eq("case_id", case_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete prep materials: {e}")
            return False


# =============================================================================
# AGENT PREP MATERIALS REPOSITORY
# =============================================================================

class SupabaseAgentPrepRepository:
    """Repository for per-agent preparation materials using Supabase."""

    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()

    def get_by_case_and_key(self, case_id: str, agent_key: str) -> Optional[Dict[str, Any]]:
        try:
            result = (
                self.client.table(Tables.AGENT_PREP)
                .select("*")
                .eq("case_id", case_id)
                .eq("agent_key", agent_key)
                .execute()
            )
            return result.data[0] if result.data else None
        except Exception as e:
            logger.warning(f"Failed to get agent prep: {e}")
            return None

    def get_all_for_case(self, case_id: str) -> List[Dict[str, Any]]:
        try:
            result = (
                self.client.table(Tables.AGENT_PREP)
                .select("*")
                .eq("case_id", case_id)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.warning(f"Failed to get agent preps for case: {e}")
            return []

    def upsert(
        self,
        case_id: str,
        agent_key: str,
        role_type: str,
        prep_content: Dict[str, Any],
    ) -> Dict[str, Any]:
        import uuid
        existing = self.get_by_case_and_key(case_id, agent_key)
        data = {
            "case_id": case_id,
            "agent_key": agent_key,
            "role_type": role_type,
            "prep_content": prep_content,
            "is_generated": True,
            "updated_at": datetime.utcnow().isoformat(),
        }
        try:
            if existing:
                result = (
                    self.client.table(Tables.AGENT_PREP)
                    .update(data)
                    .eq("case_id", case_id)
                    .eq("agent_key", agent_key)
                    .execute()
                )
                return result.data[0] if result.data else data
            else:
                data["id"] = str(uuid.uuid4())
                data["created_at"] = datetime.utcnow().isoformat()
                result = self.client.table(Tables.AGENT_PREP).insert(data).execute()
                return result.data[0] if result.data else data
        except Exception as e:
            logger.error(f"Failed to upsert agent prep: {e}")
            return data

    def delete_for_case(self, case_id: str) -> bool:
        try:
            self.client.table(Tables.AGENT_PREP).delete().eq("case_id", case_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete agent preps: {e}")
            return False


# =============================================================================
# COACH CHAT HISTORY REPOSITORY
# =============================================================================

class SupabaseCoachHistoryRepository:
    """Repository for coach chat history using Supabase."""
    
    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()
    
    def get_by_session(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get coach chat history for a session (most recent messages)."""
        try:
            result = (
                self.client.table(Tables.COACH_CHAT_HISTORY)
                .select("*")
                .eq("session_id", session_id)
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.warning(f"Failed to get coach history: {e}")
            return []
    
    def get_by_case(self, case_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get coach chat history for a case (for reuse across sessions)."""
        try:
            result = (
                self.client.table(Tables.COACH_CHAT_HISTORY)
                .select("*")
                .eq("case_id", case_id)
                .order("created_at", desc=False)
                .limit(limit)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.warning(f"Failed to get coach history by case: {e}")
            return []
    
    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        case_id: str = None,
        context: str = None,
    ) -> Dict[str, Any]:
        """Add a message to coach chat history."""
        data = {
            "session_id": session_id,
            "case_id": case_id,
            "role": role,
            "content": content,
            "context": context,
            "created_at": datetime.utcnow().isoformat(),
        }
        try:
            result = self.client.table(Tables.COACH_CHAT_HISTORY).insert(data).execute()
            return result.data[0] if result.data else data
        except Exception as e:
            logger.error(f"Failed to add coach message: {e}")
            return data
    
    def clear_session(self, session_id: str) -> bool:
        """Clear coach history for a session."""
        try:
            self.client.table(Tables.COACH_CHAT_HISTORY).delete().eq("session_id", session_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to clear coach history: {e}")
            return False


# =============================================================================
# DRILL SESSIONS REPOSITORY
# =============================================================================

class SupabaseDrillRepository:
    """Repository for drill practice sessions using Supabase."""
    
    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()
    
    def get_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all drill sessions for a session."""
        try:
            result = (
                self.client.table(Tables.DRILL_SESSIONS)
                .select("*")
                .eq("session_id", session_id)
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.warning(f"Failed to get drill sessions: {e}")
            return []
    
    def get_by_case(self, case_id: str) -> List[Dict[str, Any]]:
        """Get all drill sessions for a case."""
        try:
            result = (
                self.client.table(Tables.DRILL_SESSIONS)
                .select("*")
                .eq("case_id", case_id)
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.warning(f"Failed to get drill sessions by case: {e}")
            return []
    
    def create(
        self,
        session_id: str,
        drill_type: str,
        scenario: str,
        prompts: List[str],
        tips: List[str],
        sample_responses: List[str],
        case_id: str = None,
        witness_id: str = None,
    ) -> Dict[str, Any]:
        """Create a new drill session."""
        data = {
            "session_id": session_id,
            "case_id": case_id,
            "drill_type": drill_type,
            "witness_id": witness_id,
            "scenario": scenario,
            "prompts": prompts,
            "tips": tips,
            "sample_responses": sample_responses,
            "user_responses": [],
            "completed": False,
            "created_at": datetime.utcnow().isoformat(),
        }
        try:
            result = self.client.table(Tables.DRILL_SESSIONS).insert(data).execute()
            return result.data[0] if result.data else data
        except Exception as e:
            logger.error(f"Failed to create drill session: {e}")
            return data
    
    def add_user_response(self, drill_id: int, response: str) -> bool:
        """Add a user response to a drill session."""
        try:
            # Get current responses
            result = self.client.table(Tables.DRILL_SESSIONS).select("user_responses").eq("id", drill_id).execute()
            if result.data:
                current = result.data[0].get("user_responses", [])
                current.append({"response": response, "timestamp": datetime.utcnow().isoformat()})
                self.client.table(Tables.DRILL_SESSIONS).update({"user_responses": current}).eq("id", drill_id).execute()
                return True
        except Exception as e:
            logger.error(f"Failed to add user response: {e}")
        return False
    
    def mark_completed(self, drill_id: int) -> bool:
        """Mark a drill session as completed."""
        try:
            self.client.table(Tables.DRILL_SESSIONS).update({"completed": True}).eq("id", drill_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to mark drill completed: {e}")
            return False


# =============================================================================
# SPEECH PRACTICE REPOSITORY
# =============================================================================

class SupabaseSpeechPracticeRepository:
    """Repository for speech practice sessions using Supabase."""
    
    def __init__(self, client: Optional[Client] = None):
        self.client = client or get_supabase_client()
    
    def get_by_session(self, session_id: str) -> List[Dict[str, Any]]:
        """Get all speech practice sessions for a session."""
        try:
            result = (
                self.client.table(Tables.SPEECH_PRACTICE)
                .select("*")
                .eq("session_id", session_id)
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.warning(f"Failed to get speech practice: {e}")
            return []
    
    def get_by_case(self, case_id: str) -> List[Dict[str, Any]]:
        """Get all speech practice sessions for a case."""
        try:
            result = (
                self.client.table(Tables.SPEECH_PRACTICE)
                .select("*")
                .eq("case_id", case_id)
                .order("created_at", desc=True)
                .execute()
            )
            return result.data or []
        except Exception as e:
            logger.warning(f"Failed to get speech practice by case: {e}")
            return []
    
    def create(
        self,
        session_id: str,
        practice_type: str,
        transcript: str,
        duration_seconds: float,
        word_count: int = None,
        words_per_minute: int = None,
        filler_words: List[Dict] = None,
        clarity_score: int = None,
        pacing_feedback: str = None,
        strengths: List[str] = None,
        areas_to_improve: List[str] = None,
        delivery_tips: List[str] = None,
        case_id: str = None,
        witness_id: str = None,
    ) -> Dict[str, Any]:
        """Create a new speech practice session."""
        data = {
            "session_id": session_id,
            "case_id": case_id,
            "practice_type": practice_type,
            "witness_id": witness_id,
            "transcript": transcript,
            "duration_seconds": duration_seconds,
            "word_count": word_count,
            "words_per_minute": words_per_minute,
            "filler_words": filler_words or [],
            "clarity_score": clarity_score,
            "pacing_feedback": pacing_feedback,
            "strengths": strengths or [],
            "areas_to_improve": areas_to_improve or [],
            "delivery_tips": delivery_tips or [],
            "created_at": datetime.utcnow().isoformat(),
        }
        try:
            result = self.client.table(Tables.SPEECH_PRACTICE).insert(data).execute()
            return result.data[0] if result.data else data
        except Exception as e:
            logger.error(f"Failed to create speech practice: {e}")
            return data


# =============================================================================
# USER PREFERENCES REPOSITORY
# =============================================================================

class SupabaseUserPreferencesRepository:
    """Repository for user preferences (favorites, recent cases) using Supabase."""
    
    def __init__(self, client: Optional[Client] = None, user_id: str = "default"):
        self.client = client or get_supabase_client()
        self.user_id = user_id
    
    # --- Favorites ---
    
    def add_favorite(self, case_id: str) -> bool:
        """Add a case to favorites."""
        try:
            self.client.table(Tables.USER_FAVORITES).upsert({
                "user_id": self.user_id,
                "case_id": case_id,
                "created_at": datetime.utcnow().isoformat(),
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to add favorite: {e}")
            return False
    
    def remove_favorite(self, case_id: str) -> bool:
        """Remove a case from favorites."""
        try:
            self.client.table(Tables.USER_FAVORITES).delete().eq(
                "user_id", self.user_id
            ).eq("case_id", case_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to remove favorite: {e}")
            return False
    
    def toggle_favorite(self, case_id: str) -> bool:
        """Toggle favorite status. Returns new status."""
        if self.is_favorite(case_id):
            self.remove_favorite(case_id)
            return False
        else:
            self.add_favorite(case_id)
            return True
    
    def is_favorite(self, case_id: str) -> bool:
        """Check if a case is favorited."""
        try:
            result = self.client.table(Tables.USER_FAVORITES).select("id").eq(
                "user_id", self.user_id
            ).eq("case_id", case_id).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.warning(f"Failed to check favorite: {e}")
            return False
    
    def get_favorites(self) -> List[str]:
        """Get all favorited case IDs."""
        try:
            result = self.client.table(Tables.USER_FAVORITES).select("case_id").eq(
                "user_id", self.user_id
            ).order("created_at", desc=True).execute()
            return [r["case_id"] for r in result.data] if result.data else []
        except Exception as e:
            logger.warning(f"Failed to get favorites: {e}")
            return []
    
    # --- Recent Cases ---
    
    def record_access(self, case_id: str) -> bool:
        """Record that a case was accessed."""
        try:
            self.client.table(Tables.RECENT_CASES).upsert({
                "user_id": self.user_id,
                "case_id": case_id,
                "accessed_at": datetime.utcnow().isoformat(),
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to record access: {e}")
            return False
    
    def get_recent(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recently accessed cases."""
        try:
            result = self.client.table(Tables.RECENT_CASES).select("case_id, accessed_at").eq(
                "user_id", self.user_id
            ).order("accessed_at", desc=True).limit(limit).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.warning(f"Failed to get recent cases: {e}")
            return []
    
    def clear_recent(self) -> bool:
        """Clear recent case history."""
        try:
            self.client.table(Tables.RECENT_CASES).delete().eq(
                "user_id", self.user_id
            ).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to clear recent: {e}")
            return False
    
    # --- Hidden Cases ---
    
    def add_hidden(self, case_id: str) -> bool:
        """Mark a case as hidden/deleted."""
        try:
            self.client.table(Tables.HIDDEN_CASES).upsert({
                "user_id": self.user_id,
                "case_id": case_id,
                "hidden_at": datetime.utcnow().isoformat(),
            }).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to hide case: {e}")
            return False
    
    def remove_hidden(self, case_id: str) -> bool:
        """Unhide a case."""
        try:
            self.client.table(Tables.HIDDEN_CASES).delete().eq(
                "user_id", self.user_id
            ).eq("case_id", case_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to unhide case: {e}")
            return False
    
    def get_hidden(self) -> List[str]:
        """Get all hidden case IDs."""
        try:
            result = self.client.table(Tables.HIDDEN_CASES).select("case_id").eq(
                "user_id", self.user_id
            ).execute()
            return [r["case_id"] for r in result.data] if result.data else []
        except Exception as e:
            logger.warning(f"Failed to get hidden cases: {e}")
            return []


# =============================================================================
# UPLOADED CASES REPOSITORY
# =============================================================================

class SupabaseUploadedCasesRepository:
    """Repository for uploaded case data using Supabase."""
    
    def __init__(self, client: Optional[Client] = None, user_id: str = "default"):
        self.client = client or get_supabase_client()
        self.user_id = user_id
    
    def save(self, case_id: str, case_data: Dict[str, Any]) -> Dict[str, Any]:
        """Save or update an uploaded case."""
        data = {
            "id": case_id,
            "title": case_data.get("title", "Untitled Case"),
            "description": case_data.get("description", ""),
            "case_type": case_data.get("case_type", "civil"),
            "source": case_data.get("source", "User Upload"),
            "year": case_data.get("year", 2024),
            "difficulty": case_data.get("difficulty", "intermediate"),
            "sections": case_data.get("sections", {}),
            "witnesses": case_data.get("witnesses", []),
            "exhibits": case_data.get("exhibits", []),
            "facts": case_data.get("facts", []),
            "stipulations": case_data.get("stipulations", []),
            "legal_standards": case_data.get("legal_standards", []),
            "storage_files": case_data.get("storage_files", []),
            "user_id": self.user_id,
            "updated_at": datetime.utcnow().isoformat(),
        }
        try:
            result = self.client.table(Tables.UPLOADED_CASES).upsert(data).execute()
            return result.data[0] if result.data else data
        except Exception as e:
            logger.error(f"Failed to save uploaded case: {e}")
            return data
    
    def get(self, case_id: str) -> Optional[Dict[str, Any]]:
        """Get an uploaded case by ID."""
        try:
            result = self.client.table(Tables.UPLOADED_CASES).select("*").eq(
                "id", case_id
            ).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.warning(f"Failed to get uploaded case: {e}")
            return None
    
    def get_all(self, user_id: str = None) -> List[Dict[str, Any]]:
        """Get all uploaded cases for a user."""
        try:
            query = self.client.table(Tables.UPLOADED_CASES).select("*")
            if user_id:
                query = query.eq("user_id", user_id)
            result = query.order("updated_at", desc=True).execute()
            return result.data if result.data else []
        except Exception as e:
            logger.warning(f"Failed to get uploaded cases: {e}")
            return []
    
    def delete(self, case_id: str) -> bool:
        """Delete an uploaded case."""
        try:
            self.client.table(Tables.UPLOADED_CASES).delete().eq("id", case_id).execute()
            return True
        except Exception as e:
            logger.error(f"Failed to delete uploaded case: {e}")
            return False
    
    def exists(self, case_id: str) -> bool:
        """Check if an uploaded case exists."""
        try:
            result = self.client.table(Tables.UPLOADED_CASES).select("id").eq(
                "id", case_id
            ).execute()
            return len(result.data) > 0
        except Exception as e:
            logger.warning(f"Failed to check case existence: {e}")
            return False


# =============================================================================
# DATABASE INITIALIZATION
# =============================================================================

def init_supabase() -> None:
    """
    Initialize Supabase connection.
    
    Call this at application startup to verify connection.
    """
    client = get_supabase_client()
    logger.info("Supabase connection verified")
    print("✓ Supabase connected")


# =============================================================================
# SQL FOR TABLE CREATION (run in Supabase SQL Editor)
# =============================================================================

SCHEMA_SQL = """
-- Run this in Supabase SQL Editor to create tables

-- Sessions table
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    status TEXT DEFAULT 'created',
    human_role TEXT,
    case_id TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Participants table
CREATE TABLE IF NOT EXISTS participants (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    name TEXT NOT NULL,
    is_human BOOLEAN DEFAULT FALSE,
    persona JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Cases table
CREATE TABLE IF NOT EXISTS cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    case_type TEXT DEFAULT 'json',
    facts JSONB DEFAULT '[]',
    exhibits JSONB DEFAULT '[]',
    embedding_status TEXT DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Witnesses table
CREATE TABLE IF NOT EXISTS witnesses (
    id TEXT PRIMARY KEY,
    case_id TEXT REFERENCES cases(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    affidavit TEXT,
    called_by TEXT DEFAULT 'plaintiff',
    witness_type TEXT,
    demeanor TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Scoring results table
CREATE TABLE IF NOT EXISTS scoring_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    participant_id TEXT NOT NULL,
    participant_role TEXT NOT NULL,
    overall_average FLOAT,
    final_scores JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Ballots table
CREATE TABLE IF NOT EXISTS ballots (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    scoring_result_id UUID REFERENCES scoring_results(id) ON DELETE CASCADE,
    judge_id TEXT NOT NULL,
    judge_name TEXT NOT NULL,
    total_score FLOAT,
    average_score FLOAT,
    overall_comments TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Category scores table
CREATE TABLE IF NOT EXISTS category_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ballot_id UUID REFERENCES ballots(id) ON DELETE CASCADE,
    category TEXT NOT NULL,
    score INTEGER NOT NULL,
    justification TEXT
);

-- Transcript entries table
CREATE TABLE IF NOT EXISTS transcript_entries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT REFERENCES sessions(id) ON DELETE CASCADE,
    speaker_role TEXT NOT NULL,
    speaker_name TEXT,
    content TEXT NOT NULL,
    phase TEXT,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    audio_start_ms INTEGER,
    audio_end_ms INTEGER
);

-- Prep materials table (AI-generated study materials, stored per case)
CREATE TABLE IF NOT EXISTS prep_materials (
    id TEXT PRIMARY KEY,
    case_id TEXT UNIQUE NOT NULL,
    case_brief TEXT,
    theory_plaintiff TEXT,
    theory_defense TEXT,
    opening_plaintiff TEXT,
    opening_defense TEXT,
    witness_outlines JSONB DEFAULT '[]',
    objection_playbook JSONB,
    cross_exam_traps JSONB DEFAULT '[]',
    user_notes JSONB DEFAULT '{}',
    is_complete BOOLEAN DEFAULT FALSE,
    generation_status JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

-- Coach chat history table (persisted coaching conversations)
CREATE TABLE IF NOT EXISTS coach_chat_history (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    case_id TEXT,
    role TEXT NOT NULL,
    content TEXT NOT NULL,
    context TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Drill sessions table (practice drill scenarios and responses)
CREATE TABLE IF NOT EXISTS drill_sessions (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    case_id TEXT,
    drill_type TEXT NOT NULL,
    witness_id TEXT,
    scenario TEXT,
    prompts JSONB DEFAULT '[]',
    tips JSONB DEFAULT '[]',
    sample_responses JSONB DEFAULT '[]',
    user_responses JSONB DEFAULT '[]',
    completed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Speech practice table (voice practice sessions with analysis)
CREATE TABLE IF NOT EXISTS speech_practice (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    case_id TEXT,
    practice_type TEXT NOT NULL,
    witness_id TEXT,
    transcript TEXT NOT NULL,
    duration_seconds FLOAT NOT NULL,
    word_count INTEGER,
    words_per_minute INTEGER,
    filler_words JSONB DEFAULT '[]',
    clarity_score INTEGER,
    pacing_feedback TEXT,
    strengths JSONB DEFAULT '[]',
    areas_to_improve JSONB DEFAULT '[]',
    delivery_tips JSONB DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for common queries
CREATE INDEX IF NOT EXISTS idx_participants_session ON participants(session_id);
CREATE INDEX IF NOT EXISTS idx_witnesses_case ON witnesses(case_id);
CREATE INDEX IF NOT EXISTS idx_scoring_results_session ON scoring_results(session_id);
CREATE INDEX IF NOT EXISTS idx_transcript_session ON transcript_entries(session_id);
CREATE INDEX IF NOT EXISTS idx_prep_materials_case ON prep_materials(case_id);
CREATE INDEX IF NOT EXISTS idx_coach_history_session ON coach_chat_history(session_id);
CREATE INDEX IF NOT EXISTS idx_coach_history_case ON coach_chat_history(case_id);
CREATE INDEX IF NOT EXISTS idx_drill_sessions_session ON drill_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_drill_sessions_case ON drill_sessions(case_id);
CREATE INDEX IF NOT EXISTS idx_speech_practice_session ON speech_practice(session_id);
CREATE INDEX IF NOT EXISTS idx_speech_practice_case ON speech_practice(case_id);

-- Case files metadata table (actual files stored in Supabase Storage)
CREATE TABLE IF NOT EXISTS case_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id TEXT NOT NULL,
    section TEXT NOT NULL,
    filename TEXT NOT NULL,
    original_filename TEXT,
    storage_path TEXT NOT NULL,
    content_type TEXT,
    size_bytes BIGINT,
    parsed_content TEXT,
    metadata JSONB DEFAULT '{}',
    uploaded_by TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_case_files_case ON case_files(case_id);
CREATE INDEX IF NOT EXISTS idx_case_files_section ON case_files(case_id, section);
CREATE UNIQUE INDEX IF NOT EXISTS idx_case_files_path ON case_files(storage_path);

-- User favorites table (persists favorite cases across restarts)
CREATE TABLE IF NOT EXISTS user_favorites (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL DEFAULT 'default',  -- For future multi-user support
    case_id TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, case_id)
);

CREATE INDEX IF NOT EXISTS idx_user_favorites_user ON user_favorites(user_id);
CREATE INDEX IF NOT EXISTS idx_user_favorites_case ON user_favorites(case_id);

-- Recently accessed cases (persists across restarts)
CREATE TABLE IF NOT EXISTS recent_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL DEFAULT 'default',
    case_id TEXT NOT NULL,
    accessed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, case_id)
);

CREATE INDEX IF NOT EXISTS idx_recent_cases_user ON recent_cases(user_id);
CREATE INDEX IF NOT EXISTS idx_recent_cases_accessed ON recent_cases(user_id, accessed_at DESC);

-- Uploaded cases metadata (persists case data across restarts)
CREATE TABLE IF NOT EXISTS uploaded_cases (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    case_type TEXT DEFAULT 'civil',
    source TEXT DEFAULT 'User Upload',
    year INTEGER DEFAULT 2024,
    difficulty TEXT DEFAULT 'intermediate',
    sections JSONB DEFAULT '{}',
    witnesses JSONB DEFAULT '[]',
    exhibits JSONB DEFAULT '[]',
    facts JSONB DEFAULT '[]',
    stipulations JSONB DEFAULT '[]',
    legal_standards JSONB DEFAULT '[]',
    storage_files JSONB DEFAULT '[]',
    user_id TEXT DEFAULT 'default',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_uploaded_cases_user ON uploaded_cases(user_id);

-- Hidden/deleted cases (persists across restarts)
CREATE TABLE IF NOT EXISTS hidden_cases (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL DEFAULT 'default',
    case_id TEXT NOT NULL,
    hidden_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(user_id, case_id)
);

CREATE INDEX IF NOT EXISTS idx_hidden_cases_user ON hidden_cases(user_id);
CREATE INDEX IF NOT EXISTS idx_hidden_cases_case ON hidden_cases(case_id);

-- Per-agent prep materials (generated once per case, reused across sessions)
CREATE TABLE IF NOT EXISTS agent_prep_materials (
    id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    agent_key TEXT NOT NULL,
    role_type TEXT NOT NULL,
    prep_content JSONB NOT NULL DEFAULT '{}',
    is_generated BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,
    UNIQUE(case_id, agent_key)
);

CREATE INDEX IF NOT EXISTS idx_agent_prep_case ON agent_prep_materials(case_id);
CREATE INDEX IF NOT EXISTS idx_agent_prep_case_key ON agent_prep_materials(case_id, agent_key);
"""


def get_schema_sql() -> str:
    """Get the SQL to create all tables."""
    return SCHEMA_SQL
