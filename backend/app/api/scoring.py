"""
Scoring Endpoints

Per SCORING.md:
- Exactly 3 JudgeAgents
- Independent scoring, no shared memory
- Each category scored 1-10
- Written justification per category
- Final score = average of all judges
- Anti-Hallucination Rule: Only score what occurred in transcript

Per ARCHITECTURE.md:
- Scoring persistence in Supabase (PostgreSQL)
"""

import logging
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from datetime import datetime

from ..graph.trial_graph import (
    TrialPhase,
    Role,
)
from ..agents import (
    ScoringCategory,
    ALL_SCORING_CATEGORIES,
    get_categories_for_subrole,
    Ballot,
    JudgePanel,
)
from .session import get_session, _sessions
from ..db import ScoringRepository


router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# IN-MEMORY CACHE
# =============================================================================

# In-memory cache for quick access; Supabase is source of truth
_scoring_results: Dict[str, "ScoringResult"] = {}


class ScoringResult:
    """Stored scoring result."""
    
    def __init__(
        self,
        session_id: str,
        participant_id: str,
        participant_role: str,
        ballots: List[Dict[str, Any]],
        final_scores: Dict[str, float],
        overall_average: float,
        created_at: datetime
    ):
        self.session_id = session_id
        self.participant_id = participant_id
        self.participant_role = participant_role
        self.ballots = ballots
        self.final_scores = final_scores
        self.overall_average = overall_average
        self.created_at = created_at


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class ScoreParticipantRequest(BaseModel):
    """Request to score a participant."""
    participant_id: str
    participant_role: str
    audio_metrics: Optional[Dict[str, Any]] = None


class CategoryScoreResponse(BaseModel):
    """Score for a single category."""
    category: str
    score: int = Field(ge=1, le=10)
    justification: str


class BallotResponse(BaseModel):
    """Complete ballot from one judge."""
    judge_id: str
    judge_name: str
    scores: List[CategoryScoreResponse]
    total_score: int
    average_score: float
    overall_comments: str


class FinalScoresResponse(BaseModel):
    """Final averaged scores across all judges."""
    opening_clarity: float
    direct_examination_effectiveness: float
    cross_examination_control: float
    objection_accuracy: float
    responsiveness: float
    courtroom_presence: float
    case_theory_consistency: float


class ScoreParticipantResponse(BaseModel):
    """Complete scoring response."""
    session_id: str
    participant_id: str
    participant_role: str
    ballots: List[BallotResponse]
    final_scores: FinalScoresResponse
    overall_average: float
    feedback_summary: str


class StoredScoreResponse(BaseModel):
    """Response for stored scoring results."""
    session_id: str
    participant_id: str
    participant_role: str
    final_scores: Dict[str, float]
    overall_average: float
    created_at: str
    judge_count: int


class FeedbackRequest(BaseModel):
    """Request for verbal feedback."""
    participant_id: str
    participant_role: str


class FeedbackResponse(BaseModel):
    """Verbal feedback response."""
    session_id: str
    participant_id: str
    verbal_feedback: str
    key_strengths: List[str]
    areas_for_improvement: List[str]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def ballot_to_response(ballot: Ballot) -> BallotResponse:
    """Convert Ballot to BallotResponse."""
    scores = [
        CategoryScoreResponse(
            category=cat.value,
            score=cs.score,
            justification=cs.justification
        )
        for cat, cs in ballot.scores.items()
    ]
    
    return BallotResponse(
        judge_id=ballot.judge_id,
        judge_name=ballot.judge_name,
        scores=scores,
        total_score=ballot.total_score(),
        average_score=ballot.average_score(),
        overall_comments=ballot.overall_comments
    )


def calculate_final_scores(ballots: List[Ballot]) -> Dict[ScoringCategory, float]:
    """
    Calculate final scores as average across all judges.
    
    Per SCORING.md Section 4: Final score = average of all judges.
    """
    final_scores = {}
    
    for category in ALL_SCORING_CATEGORIES:
        category_scores = [
            b.scores[category].score
            for b in ballots
            if category in b.scores
        ]
        if category_scores:
            final_scores[category] = sum(category_scores) / len(category_scores)
        else:
            final_scores[category] = 0.0
    
    return final_scores


def generate_feedback_summary(
    ballots: List[Ballot],
    final_scores: Dict[ScoringCategory, float]
) -> str:
    """Generate a summary of feedback from all judges."""
    # Find highest and lowest categories
    sorted_scores = sorted(final_scores.items(), key=lambda x: x[1], reverse=True)
    
    strengths = [cat.value.replace("_", " ").title() for cat, _ in sorted_scores[:2]]
    improvements = [cat.value.replace("_", " ").title() for cat, _ in sorted_scores[-2:]]
    
    overall_avg = sum(final_scores.values()) / len(final_scores) if final_scores else 0
    
    return (
        f"Overall performance: {overall_avg:.1f}/10. "
        f"Strengths: {', '.join(strengths)}. "
        f"Areas for improvement: {', '.join(improvements)}."
    )


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/{session_id}/score", response_model=ScoreParticipantResponse)
async def score_participant(
    session_id: str,
    request: ScoreParticipantRequest,
):
    """
    Score a participant using all 3 JudgeAgents.
    
    Per SCORING.md:
    - Exactly 3 JudgeAgents
    - Independent scoring
    - Each category scored 1-10
    - Written justification per category
    """
    session = get_session(session_id)
    scoring_repo = ScoringRepository()
    
    # Validate trial phase
    if session.trial_state.phase != TrialPhase.SCORING:
        raise HTTPException(
            status_code=400,
            detail=f"Scoring only allowed in SCORING phase. Current: {session.trial_state.phase.value}"
        )
    
    # Validate we have judges
    if not session.judges or len(session.judges) != 3:
        raise HTTPException(
            status_code=400,
            detail="Exactly 3 judges required for scoring"
        )
    
    # Parse role
    try:
        role = Role(request.participant_role)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role: {request.participant_role}"
        )
    
    # Get transcript
    transcript = session.trial_state.transcript
    
    if not transcript:
        raise HTTPException(
            status_code=400,
            detail="No transcript available for scoring"
        )
    
    # Create judge panel and score
    panel = JudgePanel(session.judges)
    
    ballots = panel.score_participant(
        participant_role=role,
        participant_id=request.participant_id,
        transcript=transcript,
        audio_metrics=request.audio_metrics,
        trial_memory=session.trial_memory,
    )
    
    # Calculate final scores
    final_scores = calculate_final_scores(ballots)
    overall_average = sum(final_scores.values()) / len(final_scores) if final_scores else 0
    
    # Generate feedback summary
    feedback_summary = generate_feedback_summary(ballots, final_scores)
    
    # Convert to response format
    ballot_responses = [ballot_to_response(b) for b in ballots]
    
    final_scores_response = FinalScoresResponse(
        opening_clarity=final_scores.get(ScoringCategory.OPENING_CLARITY, 0),
        direct_examination_effectiveness=final_scores.get(ScoringCategory.DIRECT_EXAMINATION_EFFECTIVENESS, 0),
        cross_examination_control=final_scores.get(ScoringCategory.CROSS_EXAMINATION_CONTROL, 0),
        objection_accuracy=final_scores.get(ScoringCategory.OBJECTION_ACCURACY, 0),
        responsiveness=final_scores.get(ScoringCategory.RESPONSIVENESS, 0),
        courtroom_presence=final_scores.get(ScoringCategory.COURTROOM_PRESENCE, 0),
        case_theory_consistency=final_scores.get(ScoringCategory.CASE_THEORY_CONSISTENCY, 0),
    )
    
    # Persist results to in-memory cache
    result_id = f"{session_id}_{request.participant_id}"
    _scoring_results[result_id] = ScoringResult(
        session_id=session_id,
        participant_id=request.participant_id,
        participant_role=request.participant_role,
        ballots=[ballot_to_response(b).model_dump() for b in ballots],
        final_scores={k.value: v for k, v in final_scores.items()},
        overall_average=overall_average,
        created_at=datetime.utcnow()
    )
    
    # Persist to Supabase
    try:
        # Create scoring result record
        db_scoring_result = scoring_repo.create_scoring_result(
            session_id=session_id,
            participant_id=request.participant_id,
            participant_role=request.participant_role,
            overall_average=overall_average,
            final_scores={k.value: v for k, v in final_scores.items()},
        )
        
        # Persist each ballot with category scores
        for ballot in ballots:
            db_ballot = scoring_repo.add_ballot(
                scoring_result_id=db_scoring_result.id,
                judge_id=ballot.judge_id,
                judge_name=ballot.judge_name,
                total_score=ballot.total_score(),
                average_score=ballot.average_score(),
                overall_comments=ballot.overall_comments,
            )
            
            # Persist category scores
            for category, cat_score in ballot.scores.items():
                scoring_repo.add_category_score(
                    ballot_id=db_ballot.id,
                    category=category.value,
                    score=cat_score.score,
                    justification=cat_score.justification,
                )
        
        logger.info(f"Scoring results persisted to database for {request.participant_id}")
    except Exception as e:
        logger.warning(f"Failed to persist scoring results to database: {e}")
    
    return ScoreParticipantResponse(
        session_id=session_id,
        participant_id=request.participant_id,
        participant_role=role.value,
        ballots=ballot_responses,
        final_scores=final_scores_response,
        overall_average=overall_average,
        feedback_summary=feedback_summary
    )


@router.get("/{session_id}/scores", response_model=List[StoredScoreResponse])
async def get_session_scores(session_id: str, ):
    """Get all scoring results for a session."""
    # Verify session exists
    get_session(session_id)
    
    # Try Supabase first
    scoring_repo = ScoringRepository()
    try:
        db_results = scoring_repo.get_scoring_results(session_id)
        if db_results:
            return [
                StoredScoreResponse(
                    session_id=r.session_id,
                    participant_id=r.participant_id,
                    participant_role=r.participant_role,
                    final_scores=r.final_scores,
                    overall_average=r.overall_average,
                    created_at=r.created_at.isoformat(),
                    judge_count=len(scoring_repo.get_ballots(r.id))
                )
                for r in db_results
            ]
    except Exception as e:
        logger.warning(f"Failed to query scoring results from database: {e}")
    
    # Fallback to in-memory cache
    results = [
        StoredScoreResponse(
            session_id=r.session_id,
            participant_id=r.participant_id,
            participant_role=r.participant_role,
            final_scores=r.final_scores,
            overall_average=r.overall_average,
            created_at=r.created_at.isoformat(),
            judge_count=len(r.ballots)
        )
        for r in _scoring_results.values()
        if r.session_id == session_id
    ]
    
    return results


@router.get("/{session_id}/scores/{participant_id}")
async def get_participant_score(session_id: str, participant_id: str):
    """Get detailed scoring for a specific participant."""
    result_id = f"{session_id}_{participant_id}"
    
    if result_id not in _scoring_results:
        raise HTTPException(
            status_code=404,
            detail="Scoring result not found"
        )
    
    result = _scoring_results[result_id]
    
    return {
        "session_id": result.session_id,
        "participant_id": result.participant_id,
        "participant_role": result.participant_role,
        "ballots": result.ballots,
        "final_scores": result.final_scores,
        "overall_average": result.overall_average,
        "created_at": result.created_at.isoformat()
    }


@router.post("/{session_id}/feedback", response_model=FeedbackResponse)
async def get_verbal_feedback(session_id: str, request: FeedbackRequest):
    """
    Get verbal feedback from judges for TTS delivery.
    
    Per AGENTS.md: Detailed justification post-trial.
    """
    session = get_session(session_id)
    
    # Get stored scoring result
    result_id = f"{session_id}_{request.participant_id}"
    
    if result_id not in _scoring_results:
        raise HTTPException(
            status_code=404,
            detail="Score participant first before requesting feedback"
        )
    
    result = _scoring_results[result_id]
    
    # Parse role
    try:
        role = Role(request.participant_role)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid role: {request.participant_role}"
        )
    
    # Get first judge's ballot for detailed feedback
    if not session.judges:
        raise HTTPException(
            status_code=400,
            detail="No judges available"
        )
    
    # Get ballot from first judge
    ballot = session.judges[0].get_ballot(request.participant_id)
    
    if not ballot:
        raise HTTPException(
            status_code=404,
            detail="Ballot not found"
        )
    
    # Generate verbal feedback
    verbal_feedback = session.judges[0].generate_verbal_feedback(role, ballot)
    
    # Extract strengths and improvements from final scores
    sorted_scores = sorted(
        result.final_scores.items(),
        key=lambda x: x[1],
        reverse=True
    )
    
    strengths = [
        cat.replace("_", " ").title()
        for cat, _ in sorted_scores[:3]
    ]
    
    improvements = [
        cat.replace("_", " ").title()
        for cat, _ in sorted_scores[-3:]
    ]
    
    return FeedbackResponse(
        session_id=session_id,
        participant_id=request.participant_id,
        verbal_feedback=verbal_feedback,
        key_strengths=strengths,
        areas_for_improvement=improvements
    )


@router.get("/{session_id}/categories")
async def get_scoring_categories(session_id: str):
    """Get list of scoring categories with descriptions."""
    # Verify session exists
    get_session(session_id)
    
    category_descriptions = {
        ScoringCategory.OPENING_CLARITY: "How clearly did the advocate preview their case theory?",
        ScoringCategory.DIRECT_EXAMINATION_EFFECTIVENESS: "How effectively did the advocate elicit testimony on direct?",
        ScoringCategory.CROSS_EXAMINATION_CONTROL: "How well did the advocate control the witness on cross?",
        ScoringCategory.OBJECTION_ACCURACY: "Were objections raised appropriately and on valid grounds?",
        ScoringCategory.RESPONSIVENESS: "How well did the participant respond to questions and instructions?",
        ScoringCategory.COURTROOM_PRESENCE: "How professional was the participant's demeanor?",
        ScoringCategory.CASE_THEORY_CONSISTENCY: "Was the case theory clear and consistent throughout?",
    }
    
    return {
        "categories": [
            {
                "name": cat.value,
                "display_name": cat.value.replace("_", " ").title(),
                "description": category_descriptions.get(cat, ""),
                "min_score": 1,
                "max_score": 10
            }
            for cat in ALL_SCORING_CATEGORIES
        ]
    }


@router.get("/{session_id}/leaderboard")
async def get_leaderboard(session_id: str, ):
    """Get leaderboard of all scored participants in a session."""
    # Verify session exists
    get_session(session_id)
    
    # Try Supabase first (already sorted by score)
    scoring_repo = ScoringRepository()
    try:
        db_results = scoring_repo.get_leaderboard(session_id)
        if db_results:
            leaderboard = [
                {
                    "rank": i + 1,
                    "participant_id": r.participant_id,
                    "participant_role": r.participant_role,
                    "overall_average": round(r.overall_average, 2),
                    "total_score": sum(r.final_scores.values()) if r.final_scores else 0,
                }
                for i, r in enumerate(db_results)
            ]
            
            return {
                "session_id": session_id,
                "participant_count": len(leaderboard),
                "leaderboard": leaderboard
            }
    except Exception as e:
        logger.warning(f"Failed to get leaderboard from database: {e}")
    
    # Fallback to in-memory cache
    session_results = [
        r for r in _scoring_results.values()
        if r.session_id == session_id
    ]
    
    # Sort by overall average
    sorted_results = sorted(
        session_results,
        key=lambda r: r.overall_average,
        reverse=True
    )
    
    leaderboard = [
        {
            "rank": i + 1,
            "participant_id": r.participant_id,
            "participant_role": r.participant_role,
            "overall_average": round(r.overall_average, 2),
            "total_score": sum(r.final_scores.values()),
        }
        for i, r in enumerate(sorted_results)
    ]
    
    return {
        "session_id": session_id,
        "participant_count": len(leaderboard),
        "leaderboard": leaderboard
    }


# =============================================================================
# LIVE SCORING (updates throughout the trial, not just at SCORING phase)
# =============================================================================

_live_scores: Dict[str, Dict[str, Any]] = {}


@router.post("/{session_id}/live-score")
async def live_score_all(session_id: str):
    """
    Score all participants using a single judge based on what has happened so far.

    Unlike the full /score endpoint this works in ANY phase, uses only one judge
    for speed, and stores results in a lightweight in-memory cache that the
    frontend can poll.
    """
    session = get_session(session_id)

    if not session.judges:
        raise HTTPException(status_code=400, detail="No judges available")

    judge = session.judges[0]
    transcript = session.trial_state.transcript
    trial_memory = session.trial_memory

    if not transcript:
        return {"session_id": session_id, "scores": {}, "message": "No transcript yet"}

    results: Dict[str, Any] = {}

    # Map event types to attorney sub-roles
    _EVENT_TO_SUBROLE = {
        "opening_statement": "opening",
        "closing_argument": "closing",
    }
    _EXAM_EVENTS = {
        "direct_question", "cross_question", "redirect_question",
        "recross_question", "objection", "direct_examination",
        "cross_examination", "redirect_examination", "recross_examination",
    }
    _SUBROLE_LABELS = {
        "opening": "Opening Attorney",
        "direct_cross": "Direct/Cross Attorney",
        "closing": "Closing Attorney",
    }

    for side in ["plaintiff", "defense"]:
        role = Role.ATTORNEY_PLAINTIFF if side == "plaintiff" else Role.ATTORNEY_DEFENSE
        all_entries = [e for e in transcript if e.get("role") == f"attorney_{side}"]
        if not all_entries:
            continue

        # Group transcript entries by sub-role
        subrole_entries: Dict[str, list] = {}
        for e in all_entries:
            evt = (e.get("event_type") or "").lower()
            if evt in _EVENT_TO_SUBROLE:
                sr = _EVENT_TO_SUBROLE[evt]
            elif evt in _EXAM_EVENTS:
                sr = "direct_cross"
            else:
                sr = "direct_cross"
            subrole_entries.setdefault(sr, []).append(e)

        for sr, entries in subrole_entries.items():
            score_key = f"attorney_{side}_{sr}"
            cats = get_categories_for_subrole(sr)
            try:
                ballot = judge.score_participant(
                    participant_role=role,
                    participant_id=score_key,
                    transcript=entries,
                    trial_memory=trial_memory,
                    categories=cats,
                )
                cat_scores = {
                    cat.value: {"score": cs.score, "justification": cs.justification}
                    for cat, cs in ballot.scores.items()
                }
                att_name = None
                speakers = set()
                for e in entries:
                    sp = e.get("speaker", "")
                    if sp:
                        speakers.add(sp)
                if speakers:
                    raw = speakers.pop()
                    if "(" in raw and raw.endswith(")"):
                        att_name = raw.split("(")[-1].rstrip(")")
                    else:
                        att_name = raw
                if not att_name:
                    agent = session.attorney_team.get(f"{side}_{sr}")
                    if agent:
                        att_name = agent.persona.name
                if not att_name:
                    agent = session.attorneys.get(side)
                    att_name = agent.persona.name if agent else ("Prosecution" if side == "plaintiff" else "Defense")

                results[score_key] = {
                    "role": f"attorney_{side}",
                    "name": att_name,
                    "attorney_sub_role": _SUBROLE_LABELS.get(sr, "Attorney"),
                    "side": "Prosecution" if side == "plaintiff" else "Defense",
                    "average": round(ballot.average_score(), 1),
                    "total": ballot.total_score(),
                    "categories": cat_scores,
                    "comments": ballot.overall_comments,
                }
            except Exception as e:
                logger.warning(f"Live scoring failed for {score_key}: {e}")

    # Score each witness that has testified
    for wid, agent in session.witnesses.items():
        witness_entries = [
            e for e in transcript
            if e.get("role") == "witness" and e.get("witness_id") == wid
        ]
        if not witness_entries:
            continue
        try:
            cats = get_categories_for_subrole("witness")
            ballot = judge.score_participant(
                participant_role=Role.WITNESS,
                participant_id=f"witness_{wid}",
                transcript=transcript,
                trial_memory=trial_memory,
                categories=cats,
            )
            cat_scores = {
                cat.value: {"score": cs.score, "justification": cs.justification}
                for cat, cs in ballot.scores.items()
            }
            called_by = getattr(agent.persona, "called_by", None) or "unknown"
            w_side = "Prosecution" if called_by in ("plaintiff", "prosecution") else "Defense"
            witness_role_label = getattr(agent.persona, "role_description", None) or "Witness"
            results[f"witness_{wid}"] = {
                "role": "witness",
                "name": agent.persona.name,
                "witness_role": witness_role_label,
                "side": w_side,
                "average": round(ballot.average_score(), 1),
                "total": ballot.total_score(),
                "categories": cat_scores,
                "comments": ballot.overall_comments,
            }
        except Exception as e:
            logger.warning(f"Live scoring failed for witness {wid}: {e}")

    _live_scores[session_id] = {
        "scores": results,
        "phase": session.trial_state.phase.value,
        "transcript_length": len(transcript),
    }

    return {
        "session_id": session_id,
        "phase": session.trial_state.phase.value,
        "scores": results,
    }


@router.get("/{session_id}/live-scores")
async def get_live_scores(session_id: str):
    """Get the most recent live scores for a session."""
    get_session(session_id)
    cached = _live_scores.get(session_id)
    if not cached:
        return {"session_id": session_id, "scores": {}, "message": "No live scores yet"}
    return {"session_id": session_id, **cached}


# =============================================================================
# FULL SCORING REPORT
# =============================================================================

CATEGORY_DESCRIPTIONS = {
    "opening_clarity": "How clear and organized the opening statement was",
    "direct_examination_effectiveness": "Quality of direct examination questions and witness preparation",
    "cross_examination_control": "Control of witness during cross-examination",
    "objection_accuracy": "Accuracy and timeliness of objections",
    "responsiveness": "How well answers addressed the questions asked",
    "courtroom_presence": "Poise, confidence, and professionalism in the courtroom",
    "case_theory_consistency": "Consistency in advancing the case theory throughout trial",
    "persuasiveness": "How compelling and persuasive the opening argument was",
    "factual_foundation": "How well the opening previewed the facts to be proven",
    "closing_persuasiveness": "Strength and persuasiveness of the closing argument",
    "evidence_integration": "How well evidence and testimony were woven into the closing",
    "rebuttal_effectiveness": "How effectively the opposing side's arguments were addressed",
    "testimony_consistency": "Internal consistency of the witness's testimony",
    "credibility": "How believable and trustworthy the witness appeared",
    "composure_under_pressure": "How well the witness handled challenging cross-examination",
}


@router.get("/{session_id}/full-report")
async def get_full_scoring_report(session_id: str):
    """
    Comprehensive scoring report combining live scores, full scoring ballots,
    and category descriptions. Used by the Score Detail page.
    """
    session = get_session(session_id)

    live = _live_scores.get(session_id, {})
    live_scores = live.get("scores", {})

    stored = _scoring_results.get(session_id)
    ballots_data = []
    if stored:
        ballots_data = stored.ballots

    case_name = getattr(session, "case_name", None) or session_id
    case_id = getattr(session, "case_id", None) or "unknown"

    return {
        "session_id": session_id,
        "case_name": case_name,
        "case_id": str(case_id),
        "phase": session.trial_state.phase.value,
        "live_scores": live_scores,
        "stored_ballots": ballots_data,
        "category_descriptions": CATEGORY_DESCRIPTIONS,
    }


# =============================================================================
# DATABASE PERSISTENCE: IMPLEMENTED
# =============================================================================
# Supabase (PostgreSQL) persistence is now integrated via:
# - db/models.py: ScoringResultModel, BallotModel, CategoryScoreModel
# - db/repository.py: ScoringRepository
# - db/session.py: get_db dependency
#
# All scoring operations now persist to Supabase with in-memory cache fallback.
