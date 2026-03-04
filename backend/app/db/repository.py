"""
Repository Pattern for Database Operations

Provides clean data access abstraction for:
- Sessions
- Scoring
- Cases
"""

from typing import Optional, List, Dict, Any
from datetime import datetime
import uuid

from sqlalchemy.orm import Session
from sqlalchemy import select, update, delete

from .models import (
    SessionModel,
    ParticipantModel,
    TranscriptEntryModel,
    ScoringResultModel,
    BallotModel,
    CategoryScoreModel,
    CaseModel,
    WitnessModel,
    PrepMaterialsModel,
)


# =============================================================================
# SESSION REPOSITORY
# =============================================================================

class SessionRepository:
    """Repository for trial session operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================================================
    # SESSION CRUD
    # =========================================================================
    
    def create_session(
        self,
        session_id: Optional[str] = None,
        case_id: Optional[str] = None,
        human_role: Optional[str] = None,
    ) -> SessionModel:
        """Create a new trial session."""
        session = SessionModel(
            id=session_id or str(uuid.uuid4()),
            case_id=case_id,
            human_role=human_role,
            status="created",
            phase="PREP",
            trial_state={},
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session
    
    def get_session(self, session_id: str) -> Optional[SessionModel]:
        """Get session by ID."""
        return self.db.query(SessionModel).filter(
            SessionModel.id == session_id
        ).first()
    
    def get_all_sessions(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> List[SessionModel]:
        """Get all sessions, optionally filtered by status."""
        query = self.db.query(SessionModel)
        
        if status:
            query = query.filter(SessionModel.status == status)
        
        return query.order_by(
            SessionModel.created_at.desc()
        ).offset(offset).limit(limit).all()
    
    def update_session(
        self,
        session_id: str,
        **kwargs
    ) -> Optional[SessionModel]:
        """Update session fields."""
        session = self.get_session(session_id)
        if not session:
            return None
        
        for key, value in kwargs.items():
            if hasattr(session, key):
                setattr(session, key, value)
        
        self.db.commit()
        self.db.refresh(session)
        return session
    
    def update_trial_state(
        self,
        session_id: str,
        trial_state: Dict[str, Any],
    ) -> Optional[SessionModel]:
        """Update the trial state JSON."""
        return self.update_session(session_id, trial_state=trial_state)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all related data."""
        session = self.get_session(session_id)
        if not session:
            return False
        
        self.db.delete(session)
        self.db.commit()
        return True
    
    # =========================================================================
    # PARTICIPANT CRUD
    # =========================================================================
    
    def add_participant(
        self,
        session_id: str,
        role: str,
        is_human: bool = False,
        persona: Optional[Dict[str, Any]] = None,
        name: Optional[str] = None,
    ) -> ParticipantModel:
        """Add a participant to a session."""
        participant = ParticipantModel(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            is_human=is_human,
            persona=persona or {},
            name=name,
        )
        self.db.add(participant)
        self.db.commit()
        self.db.refresh(participant)
        return participant
    
    def get_participants(self, session_id: str) -> List[ParticipantModel]:
        """Get all participants for a session."""
        return self.db.query(ParticipantModel).filter(
            ParticipantModel.session_id == session_id
        ).all()
    
    def get_participant_by_role(
        self,
        session_id: str,
        role: str,
    ) -> Optional[ParticipantModel]:
        """Get participant by role."""
        return self.db.query(ParticipantModel).filter(
            ParticipantModel.session_id == session_id,
            ParticipantModel.role == role,
        ).first()
    
    # =========================================================================
    # TRANSCRIPT CRUD
    # =========================================================================
    
    def add_transcript_entry(
        self,
        session_id: str,
        role: str,
        text: str,
        phase: str,
        audio_timestamp: Optional[float] = None,
        event_type: Optional[str] = None,
    ) -> TranscriptEntryModel:
        """Add an entry to the transcript."""
        entry = TranscriptEntryModel(
            session_id=session_id,
            role=role,
            text=text,
            phase=phase,
            audio_timestamp=audio_timestamp,
            event_type=event_type,
        )
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry
    
    def get_transcript(
        self,
        session_id: str,
        phase: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[TranscriptEntryModel]:
        """Get transcript entries for a session."""
        query = self.db.query(TranscriptEntryModel).filter(
            TranscriptEntryModel.session_id == session_id
        )
        
        if phase:
            query = query.filter(TranscriptEntryModel.phase == phase)
        
        query = query.order_by(TranscriptEntryModel.id)
        
        if limit:
            query = query.limit(limit)
        
        return query.all()


# =============================================================================
# SCORING REPOSITORY
# =============================================================================

class ScoringRepository:
    """Repository for scoring operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_scoring_result(
        self,
        session_id: str,
        participant_id: str,
        participant_role: str,
        overall_average: float,
        final_scores: Dict[str, float],
    ) -> ScoringResultModel:
        """Create a scoring result."""
        result = ScoringResultModel(
            session_id=session_id,
            participant_id=participant_id,
            participant_role=participant_role,
            overall_average=overall_average,
            final_scores=final_scores,
        )
        self.db.add(result)
        self.db.commit()
        self.db.refresh(result)
        return result
    
    def add_ballot(
        self,
        scoring_result_id: int,
        judge_id: str,
        judge_name: str,
        total_score: int,
        average_score: float,
        overall_comments: Optional[str] = None,
    ) -> BallotModel:
        """Add a ballot to a scoring result."""
        ballot = BallotModel(
            scoring_result_id=scoring_result_id,
            judge_id=judge_id,
            judge_name=judge_name,
            total_score=total_score,
            average_score=average_score,
            overall_comments=overall_comments,
        )
        self.db.add(ballot)
        self.db.commit()
        self.db.refresh(ballot)
        return ballot
    
    def add_category_score(
        self,
        ballot_id: int,
        category: str,
        score: int,
        justification: Optional[str] = None,
    ) -> CategoryScoreModel:
        """Add a category score to a ballot."""
        cat_score = CategoryScoreModel(
            ballot_id=ballot_id,
            category=category,
            score=score,
            justification=justification,
        )
        self.db.add(cat_score)
        self.db.commit()
        self.db.refresh(cat_score)
        return cat_score
    
    def get_scoring_results(
        self,
        session_id: str,
    ) -> List[ScoringResultModel]:
        """Get all scoring results for a session."""
        return self.db.query(ScoringResultModel).filter(
            ScoringResultModel.session_id == session_id
        ).all()
    
    def get_scoring_result_for_participant(
        self,
        session_id: str,
        participant_id: str,
    ) -> Optional[ScoringResultModel]:
        """Get scoring result for a specific participant."""
        return self.db.query(ScoringResultModel).filter(
            ScoringResultModel.session_id == session_id,
            ScoringResultModel.participant_id == participant_id,
        ).first()
    
    def get_ballots(
        self,
        scoring_result_id: int,
    ) -> List[BallotModel]:
        """Get all ballots for a scoring result."""
        return self.db.query(BallotModel).filter(
            BallotModel.scoring_result_id == scoring_result_id
        ).all()
    
    def get_leaderboard(
        self,
        session_id: str,
    ) -> List[ScoringResultModel]:
        """Get scoring results ordered by score (leaderboard)."""
        return self.db.query(ScoringResultModel).filter(
            ScoringResultModel.session_id == session_id
        ).order_by(
            ScoringResultModel.overall_average.desc()
        ).all()


# =============================================================================
# CASE REPOSITORY
# =============================================================================

class CaseRepository:
    """Repository for case operations."""
    
    def __init__(self, db: Session):
        self.db = db
    
    # =========================================================================
    # CASE CRUD
    # =========================================================================
    
    def create_case(
        self,
        title: str,
        case_id: Optional[str] = None,
        description: Optional[str] = None,
        case_type: Optional[str] = None,
        facts: Optional[List[Dict]] = None,
        exhibits: Optional[List[Dict]] = None,
    ) -> CaseModel:
        """Create a new case."""
        case = CaseModel(
            id=case_id or str(uuid.uuid4()),
            title=title,
            description=description,
            case_type=case_type,
            facts=facts or [],
            exhibits=exhibits or [],
            processing_status="pending",
            embedding_status="pending",
        )
        self.db.add(case)
        self.db.commit()
        self.db.refresh(case)
        return case
    
    def get_case(self, case_id: str) -> Optional[CaseModel]:
        """Get case by ID."""
        return self.db.query(CaseModel).filter(
            CaseModel.id == case_id
        ).first()
    
    def get_all_cases(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> List[CaseModel]:
        """Get all cases."""
        return self.db.query(CaseModel).order_by(
            CaseModel.created_at.desc()
        ).offset(offset).limit(limit).all()
    
    def update_case(
        self,
        case_id: str,
        **kwargs
    ) -> Optional[CaseModel]:
        """Update case fields."""
        case = self.get_case(case_id)
        if not case:
            return None
        
        for key, value in kwargs.items():
            if hasattr(case, key):
                setattr(case, key, value)
        
        self.db.commit()
        self.db.refresh(case)
        return case
    
    def update_processing_status(
        self,
        case_id: str,
        processing_status: Optional[str] = None,
        embedding_status: Optional[str] = None,
    ) -> Optional[CaseModel]:
        """Update case processing status."""
        updates = {}
        if processing_status:
            updates["processing_status"] = processing_status
        if embedding_status:
            updates["embedding_status"] = embedding_status
        
        return self.update_case(case_id, **updates)
    
    def delete_case(self, case_id: str) -> bool:
        """Delete a case and all related data."""
        case = self.get_case(case_id)
        if not case:
            return False
        
        self.db.delete(case)
        self.db.commit()
        return True
    
    # =========================================================================
    # WITNESS CRUD
    # =========================================================================
    
    def add_witness(
        self,
        case_id: str,
        name: str,
        called_by: str,
        affidavit: str,
        witness_id: Optional[str] = None,
        witness_type: str = "fact_witness",
        default_persona: Optional[Dict[str, Any]] = None,
    ) -> WitnessModel:
        """Add a witness to a case."""
        witness = WitnessModel(
            id=witness_id or str(uuid.uuid4()),
            case_id=case_id,
            name=name,
            called_by=called_by,
            affidavit=affidavit,
            witness_type=witness_type,
            default_persona=default_persona or {},
        )
        self.db.add(witness)
        self.db.commit()
        self.db.refresh(witness)
        return witness
    
    def get_witnesses(self, case_id: str) -> List[WitnessModel]:
        """Get all witnesses for a case."""
        return self.db.query(WitnessModel).filter(
            WitnessModel.case_id == case_id
        ).all()
    
    def get_witness(self, witness_id: str) -> Optional[WitnessModel]:
        """Get witness by ID."""
        return self.db.query(WitnessModel).filter(
            WitnessModel.id == witness_id
        ).first()
    
    def delete_witness(self, witness_id: str) -> bool:
        """Delete a witness."""
        witness = self.get_witness(witness_id)
        if not witness:
            return False
        
        self.db.delete(witness)
        self.db.commit()
        return True


# =============================================================================
# PREP MATERIALS REPOSITORY
# =============================================================================

class PrepMaterialsRepository:
    """Repository for AI-generated preparation materials."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_by_case_id(self, case_id: str) -> Optional[PrepMaterialsModel]:
        """Get prep materials for a case."""
        return self.db.query(PrepMaterialsModel).filter(
            PrepMaterialsModel.case_id == case_id
        ).first()
    
    def create(
        self,
        case_id: str,
        case_brief: Optional[str] = None,
        theory_plaintiff: Optional[str] = None,
        theory_defense: Optional[str] = None,
        opening_plaintiff: Optional[str] = None,
        opening_defense: Optional[str] = None,
        witness_outlines: Optional[List[Dict]] = None,
        objection_playbook: Optional[Dict] = None,
        cross_exam_traps: Optional[List[Dict]] = None,
        is_complete: bool = False,
        generation_status: Optional[Dict] = None,
    ) -> PrepMaterialsModel:
        """Create prep materials for a case."""
        materials = PrepMaterialsModel(
            id=str(uuid.uuid4()),
            case_id=case_id,
            case_brief=case_brief,
            theory_plaintiff=theory_plaintiff,
            theory_defense=theory_defense,
            opening_plaintiff=opening_plaintiff,
            opening_defense=opening_defense,
            witness_outlines=witness_outlines or [],
            objection_playbook=objection_playbook,
            cross_exam_traps=cross_exam_traps or [],
            is_complete=is_complete,
            generation_status=generation_status or {},
        )
        self.db.add(materials)
        self.db.commit()
        self.db.refresh(materials)
        return materials
    
    def update(
        self,
        case_id: str,
        **kwargs
    ) -> Optional[PrepMaterialsModel]:
        """Update prep materials."""
        materials = self.get_by_case_id(case_id)
        if not materials:
            return None
        
        for key, value in kwargs.items():
            if hasattr(materials, key):
                setattr(materials, key, value)
        
        self.db.commit()
        self.db.refresh(materials)
        return materials
    
    def upsert(
        self,
        case_id: str,
        **kwargs
    ) -> PrepMaterialsModel:
        """Create or update prep materials."""
        existing = self.get_by_case_id(case_id)
        if existing:
            return self.update(case_id, **kwargs)
        else:
            return self.create(case_id=case_id, **kwargs)
    
    def delete(self, case_id: str) -> bool:
        """Delete prep materials for a case."""
        materials = self.get_by_case_id(case_id)
        if not materials:
            return False
        
        self.db.delete(materials)
        self.db.commit()
        return True
