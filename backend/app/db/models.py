"""
SQLAlchemy Database Models

Defines all database tables for Mock Trial AI persistence.
Per ARCHITECTURE.md: Data storage in Supabase (PostgreSQL)
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
import json

from sqlalchemy import (  # type: ignore[import-unresolved]
    Column,
    Integer,
    String,
    Float,
    Boolean,
    DateTime,
    Text,
    ForeignKey,
    JSON,
    Enum as SQLEnum,
)
from sqlalchemy.orm import declarative_base, relationship  # type: ignore[import-unresolved]

Base = declarative_base()


# =============================================================================
# SESSION MODELS
# =============================================================================

class SessionModel(Base):
    """Trial session persistence."""
    
    __tablename__ = "sessions"
    
    id = Column(String(36), primary_key=True)  # UUID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Session state
    status = Column(String(20), default="created", nullable=False)  # created, active, completed
    phase = Column(String(20), default="PREP", nullable=False)
    
    # Case reference
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=True)
    
    # Human player
    human_role = Column(String(30), nullable=True)
    human_participant_id = Column(String(36), nullable=True)
    
    # Trial state (JSON blob for complex state)
    trial_state = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    participants = relationship("ParticipantModel", back_populates="session")
    transcript_entries = relationship("TranscriptEntryModel", back_populates="session")
    scoring_results = relationship("ScoringResultModel", back_populates="session")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status,
            "phase": self.phase,
            "case_id": self.case_id,
            "human_role": self.human_role,
            "human_participant_id": self.human_participant_id,
            "trial_state": self.trial_state,
        }


class ParticipantModel(Base):
    """Trial participant (human or AI agent)."""
    
    __tablename__ = "participants"
    
    id = Column(String(36), primary_key=True)  # UUID
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    
    # Role and type
    role = Column(String(30), nullable=False)  # attorney_plaintiff, attorney_defense, witness, judge, coach
    is_human = Column(Boolean, default=False, nullable=False)
    
    # Persona configuration (JSON)
    persona = Column(JSON, default=dict, nullable=False)
    
    # Agent-specific data
    name = Column(String(100), nullable=True)
    
    # Relationships
    session = relationship("SessionModel", back_populates="participants")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "is_human": self.is_human,
            "persona": self.persona,
            "name": self.name,
        }


class TranscriptEntryModel(Base):
    """Individual transcript entry."""
    
    __tablename__ = "transcript_entries"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    
    # Entry data
    role = Column(String(30), nullable=False)
    text = Column(Text, nullable=False)
    phase = Column(String(20), nullable=False)
    audio_timestamp = Column(Float, nullable=True)
    
    # Event metadata
    event_type = Column(String(30), nullable=True)  # speech, objection, ruling, interrupt
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    session = relationship("SessionModel", back_populates="transcript_entries")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "text": self.text,
            "phase": self.phase,
            "audio_timestamp": self.audio_timestamp,
            "event_type": self.event_type,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


# =============================================================================
# SCORING MODELS
# =============================================================================

class ScoringResultModel(Base):
    """Aggregated scoring result for a participant."""
    
    __tablename__ = "scoring_results"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.id"), nullable=False)
    participant_id = Column(String(36), nullable=False)
    participant_role = Column(String(30), nullable=False)
    
    # Final scores (averaged across judges)
    overall_average = Column(Float, nullable=False)
    final_scores = Column(JSON, nullable=False)  # Dict[category, score]
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relationships
    session = relationship("SessionModel", back_populates="scoring_results")
    ballots = relationship("BallotModel", back_populates="scoring_result")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "participant_id": self.participant_id,
            "participant_role": self.participant_role,
            "overall_average": self.overall_average,
            "final_scores": self.final_scores,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class BallotModel(Base):
    """Individual judge ballot."""
    
    __tablename__ = "ballots"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    scoring_result_id = Column(Integer, ForeignKey("scoring_results.id"), nullable=False)
    
    # Judge info
    judge_id = Column(String(36), nullable=False)
    judge_name = Column(String(100), nullable=False)
    
    # Scores
    total_score = Column(Integer, nullable=False)
    average_score = Column(Float, nullable=False)
    overall_comments = Column(Text, nullable=True)
    
    # Relationships
    scoring_result = relationship("ScoringResultModel", back_populates="ballots")
    category_scores = relationship("CategoryScoreModel", back_populates="ballot")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "scoring_result_id": self.scoring_result_id,
            "judge_id": self.judge_id,
            "judge_name": self.judge_name,
            "total_score": self.total_score,
            "average_score": self.average_score,
            "overall_comments": self.overall_comments,
            "category_scores": [cs.to_dict() for cs in self.category_scores],
        }


class CategoryScoreModel(Base):
    """Individual category score within a ballot."""
    
    __tablename__ = "category_scores"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    ballot_id = Column(Integer, ForeignKey("ballots.id"), nullable=False)
    
    # Score data
    category = Column(String(50), nullable=False)
    score = Column(Integer, nullable=False)  # 1-10
    justification = Column(Text, nullable=True)
    
    # Relationships
    ballot = relationship("BallotModel", back_populates="category_scores")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "ballot_id": self.ballot_id,
            "category": self.category,
            "score": self.score,
            "justification": self.justification,
        }


# =============================================================================
# CASE MODELS
# =============================================================================

class CaseModel(Base):
    """Case definition and metadata."""
    
    __tablename__ = "cases"
    
    id = Column(String(36), primary_key=True)  # UUID
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Case metadata
    title = Column(String(200), nullable=False)
    description = Column(Text, nullable=True)
    case_type = Column(String(50), nullable=True)  # civil, criminal
    
    # Processing status
    processing_status = Column(String(20), default="pending", nullable=False)
    embedding_status = Column(String(20), default="pending", nullable=False)
    
    # Case content (JSON)
    facts = Column(JSON, default=list, nullable=False)
    exhibits = Column(JSON, default=list, nullable=False)
    
    # Pinecone namespace (if embedded)
    pinecone_namespace = Column(String(100), nullable=True)
    
    # Relationships
    witnesses = relationship("WitnessModel", back_populates="case")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "title": self.title,
            "description": self.description,
            "case_type": self.case_type,
            "processing_status": self.processing_status,
            "embedding_status": self.embedding_status,
            "facts": self.facts,
            "exhibits": self.exhibits,
            "pinecone_namespace": self.pinecone_namespace,
        }


class WitnessModel(Base):
    """Witness definition within a case."""
    
    __tablename__ = "witnesses"
    
    id = Column(String(36), primary_key=True)  # UUID
    case_id = Column(String(36), ForeignKey("cases.id"), nullable=False)
    
    # Witness info
    name = Column(String(100), nullable=False)
    called_by = Column(String(20), nullable=False)  # plaintiff, defense
    witness_type = Column(String(30), default="fact_witness", nullable=False)
    
    # Affidavit (source of truth)
    affidavit = Column(Text, nullable=False)
    
    # Persona defaults (JSON)
    default_persona = Column(JSON, default=dict, nullable=False)
    
    # Relationships
    case = relationship("CaseModel", back_populates="witnesses")
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "name": self.name,
            "called_by": self.called_by,
            "witness_type": self.witness_type,
            "affidavit": self.affidavit,
            "default_persona": self.default_persona,
        }


# =============================================================================
# PREPARATION MATERIALS
# =============================================================================

class PrepMaterialsModel(Base):
    """
    AI-generated preparation materials for a case.
    
    Stored per case_id so materials only need to be generated once per case.
    """
    
    __tablename__ = "prep_materials"
    
    id = Column(String(36), primary_key=True)  # UUID
    case_id = Column(String(100), nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Generated content (stored as JSON)
    case_brief = Column(Text, nullable=True)
    theory_plaintiff = Column(Text, nullable=True)
    theory_defense = Column(Text, nullable=True)
    opening_plaintiff = Column(Text, nullable=True)
    opening_defense = Column(Text, nullable=True)
    witness_outlines = Column(JSON, default=list, nullable=False)  # List of outline objects
    objection_playbook = Column(JSON, nullable=True)  # Playbook object
    cross_exam_traps = Column(JSON, default=list, nullable=False)  # List of trap objects
    
    # User notes (editable by user)
    user_notes = Column(JSON, default=dict, nullable=False)  # Dict[section, note_content]
    
    # Generation status
    is_complete = Column(Boolean, default=False, nullable=False)
    generation_status = Column(JSON, default=dict, nullable=False)  # Per-section status
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "case_brief": self.case_brief,
            "theory_plaintiff": self.theory_plaintiff,
            "theory_defense": self.theory_defense,
            "opening_plaintiff": self.opening_plaintiff,
            "opening_defense": self.opening_defense,
            "witness_outlines": self.witness_outlines or [],
            "objection_playbook": self.objection_playbook,
            "cross_exam_traps": self.cross_exam_traps or [],
            "user_notes": self.user_notes or {},
            "is_complete": self.is_complete,
            "generation_status": self.generation_status or {},
        }


class CoachChatHistoryModel(Base):
    """
    Persisted coach chat conversation history.
    
    Stored per session_id so coaching conversations persist across page reloads.
    """
    
    __tablename__ = "coach_chat_history"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False, index=True)
    case_id = Column(String(100), nullable=True, index=True)  # Also index by case for reuse
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Message data
    role = Column(String(20), nullable=False)  # user or assistant
    content = Column(Text, nullable=False)
    
    # Optional metadata
    context = Column(String(50), nullable=True)  # What the user was asking about
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "case_id": self.case_id,
            "role": self.role,
            "content": self.content,
            "context": self.context,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class DrillSessionModel(Base):
    """
    Persisted drill practice sessions.
    
    Stores the AI-generated drill scenarios and user responses for review.
    """
    
    __tablename__ = "drill_sessions"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False, index=True)
    case_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Drill configuration
    drill_type = Column(String(30), nullable=False)  # direct, cross, opening, closing, objections
    witness_id = Column(String(36), nullable=True)  # If applicable
    
    # AI-generated drill content
    scenario = Column(Text, nullable=True)
    prompts = Column(JSON, default=list, nullable=False)
    tips = Column(JSON, default=list, nullable=False)
    sample_responses = Column(JSON, default=list, nullable=False)
    
    # User practice data (optional, for tracking progress)
    user_responses = Column(JSON, default=list, nullable=False)
    completed = Column(Boolean, default=False, nullable=False)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "case_id": self.case_id,
            "drill_type": self.drill_type,
            "witness_id": self.witness_id,
            "scenario": self.scenario,
            "prompts": self.prompts or [],
            "tips": self.tips or [],
            "sample_responses": self.sample_responses or [],
            "user_responses": self.user_responses or [],
            "completed": self.completed,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class AgentPrepModel(Base):
    """
    Per-agent preparation materials for a case.

    Keyed by (case_id, agent_key) so each agent's prep is generated once per case.
    agent_key examples: plaintiff_opening, defense_direct_cross, witness_indigo_quade, judge
    """

    __tablename__ = "agent_prep_materials"

    id = Column(String(36), primary_key=True)
    case_id = Column(String(100), nullable=False, index=True)
    agent_key = Column(String(120), nullable=False, index=True)
    role_type = Column(String(30), nullable=False)  # attorney, witness, judge
    prep_content = Column(JSON, default=dict, nullable=False)
    is_generated = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "case_id": self.case_id,
            "agent_key": self.agent_key,
            "role_type": self.role_type,
            "prep_content": self.prep_content or {},
            "is_generated": self.is_generated,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class SpeechPracticeModel(Base):
    """
    Persisted speech practice sessions with analysis.
    
    Stores voice practice attempts and AI feedback for progress tracking.
    """
    
    __tablename__ = "speech_practice"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), nullable=False, index=True)
    case_id = Column(String(100), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Practice context
    practice_type = Column(String(50), nullable=False)  # opening_statement, cross_examination, etc.
    witness_id = Column(String(36), nullable=True)
    
    # Speech data
    transcript = Column(Text, nullable=False)
    duration_seconds = Column(Float, nullable=False)
    
    # Analysis results
    word_count = Column(Integer, nullable=True)
    words_per_minute = Column(Integer, nullable=True)
    filler_words = Column(JSON, default=list, nullable=False)
    clarity_score = Column(Integer, nullable=True)
    
    # AI feedback
    pacing_feedback = Column(Text, nullable=True)
    strengths = Column(JSON, default=list, nullable=False)
    areas_to_improve = Column(JSON, default=list, nullable=False)
    delivery_tips = Column(JSON, default=list, nullable=False)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "case_id": self.case_id,
            "practice_type": self.practice_type,
            "witness_id": self.witness_id,
            "transcript": self.transcript,
            "duration_seconds": self.duration_seconds,
            "word_count": self.word_count,
            "words_per_minute": self.words_per_minute,
            "filler_words": self.filler_words or [],
            "clarity_score": self.clarity_score,
            "pacing_feedback": self.pacing_feedback,
            "strengths": self.strengths or [],
            "areas_to_improve": self.areas_to_improve or [],
            "delivery_tips": self.delivery_tips or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
