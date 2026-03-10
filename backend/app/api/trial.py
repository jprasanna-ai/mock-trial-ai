"""
Trial State Endpoints

Per ARCHITECTURE.md:
- All trial logic flows through LangGraph
- LangGraph is the single source of truth

This router provides endpoints to interact with trial state.
No trial logic is implemented here - uses trial_graph.py for state enforcement.
"""

import asyncio
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from ..graph.trial_graph import (
    TrialState,
    TrialPhase,
    Role,
    validate_transition,
    validate_speaker,
    can_object,
    VALID_OBJECTION_TYPES,
    TESTIMONY_STATES,
)
from .session import get_session, _sessions
from .scoring import _live_scores as _scoring_live_scores, _persist_live_scores
from .auth import get_current_user_id
from ..db.storage import get_transcript_storage

logger = logging.getLogger(__name__)

router = APIRouter()


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class TrialStateResponse(BaseModel):
    """Current trial state."""
    session_id: str
    phase: str
    current_speaker: Optional[str] = None
    human_role: Optional[str] = None
    objection_pending: bool = False
    judge_interrupt_active: bool = False
    can_object: bool = False
    transcript_length: int = 0
    current_witness_id: Optional[str] = None
    current_witness_name: Optional[str] = None
    case_in_chief: str = "prosecution"
    prosecution_rested: bool = False
    defense_rested: bool = False
    witnesses_remaining: int = 0
    direct_complete: bool = False
    cross_complete: bool = False
    redirect_complete: bool = False
    recross_complete: bool = False


class ValidateTransitionRequest(BaseModel):
    """Request to validate a phase transition."""
    target_phase: str


class ValidateTransitionResponse(BaseModel):
    """Response for transition validation."""
    current_phase: str
    target_phase: str
    valid: bool
    reason: Optional[str]


class ValidateSpeakerRequest(BaseModel):
    """Request to validate if a role can speak."""
    role: str


class ValidateSpeakerResponse(BaseModel):
    """Response for speaker validation."""
    role: str
    can_speak: bool
    reason: Optional[str]


class ObjectionCheckRequest(BaseModel):
    """Request to check if objection is valid."""
    objecting_role: str
    objection_type: str


class ObjectionCheckResponse(BaseModel):
    """Response for objection check."""
    can_object: bool
    objection_type_valid: bool
    reason: Optional[str]


class AdvancePhaseRequest(BaseModel):
    """Request to advance to a new phase."""
    target_phase: str


class AdvancePhaseResponse(BaseModel):
    """Response for phase advancement."""
    success: bool
    previous_phase: str
    current_phase: str
    message: str


class RaiseObjectionRequest(BaseModel):
    """Request to raise an objection."""
    objection_type: str
    role: str


class RaiseObjectionResponse(BaseModel):
    """Response for objection ruling."""
    objection_type: str
    sustained: bool
    explanation: str
    ruling_by: str = "Judge"


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/{session_id}/state", response_model=TrialStateResponse)
async def get_trial_state(session_id: str):
    """
    Get current trial state.
    
    Per ARCHITECTURE.md: LangGraph is the single source of truth.
    """
    session = get_session(session_id)
    state = session.trial_state
    
    witness_name = None
    if state.current_witness_id and state.current_witness_id in session.witnesses:
        witness_name = session.witnesses[state.current_witness_id].persona.name

    return TrialStateResponse(
        session_id=session_id,
        phase=state.phase.value,
        current_speaker=state.current_speaker.value if state.current_speaker else None,
        human_role=state.human_role.value if state.human_role else None,
        objection_pending=state.objection_pending,
        judge_interrupt_active=state.judge_interrupt_active,
        can_object=state.phase in TESTIMONY_STATES,
        transcript_length=len(state.transcript),
        current_witness_id=state.current_witness_id,
        current_witness_name=witness_name,
        case_in_chief=state.case_in_chief,
        prosecution_rested=state.prosecution_rested,
        defense_rested=state.defense_rested,
        witnesses_remaining=len(state.witnesses_to_examine),
        direct_complete=state.direct_complete,
        cross_complete=state.cross_complete,
        redirect_complete=state.redirect_complete,
        recross_complete=state.recross_complete,
    )


@router.post("/{session_id}/validate-transition", response_model=ValidateTransitionResponse)
async def validate_phase_transition(session_id: str, request: ValidateTransitionRequest):
    """
    Validate if a phase transition is legal.
    
    Per trial_graph.py: VALID_TRANSITIONS defines legal transitions.
    """
    session = get_session(session_id)
    state = session.trial_state
    
    # Parse target phase
    try:
        target = TrialPhase(request.target_phase.upper())
    except ValueError:
        return ValidateTransitionResponse(
            current_phase=state.phase.value,
            target_phase=request.target_phase,
            valid=False,
            reason=f"Invalid phase: {request.target_phase}"
        )
    
    valid = validate_transition(state.phase, target)
    
    return ValidateTransitionResponse(
        current_phase=state.phase.value,
        target_phase=target.value,
        valid=valid,
        reason=None if valid else f"Cannot transition from {state.phase.value} to {target.value}"
    )


@router.post("/{session_id}/advance-phase", response_model=AdvancePhaseResponse)
async def advance_trial_phase(session_id: str, request: AdvancePhaseRequest):
    """
    Advance the trial to a new phase.
    
    Validates the transition is legal before proceeding.
    """
    session = get_session(session_id)
    state = session.trial_state
    previous_phase = state.phase
    
    # Parse target phase
    try:
        target = TrialPhase(request.target_phase.upper())
    except ValueError:
        return AdvancePhaseResponse(
            success=False,
            previous_phase=previous_phase.value,
            current_phase=previous_phase.value,
            message=f"Invalid phase: {request.target_phase}"
        )
    
    # If already at the target phase, treat as success (idempotent)
    if state.phase == target:
        return AdvancePhaseResponse(
            success=True,
            previous_phase=previous_phase.value,
            current_phase=target.value,
            message=f"Already at phase {target.value}"
        )

    # Validate transition
    if not validate_transition(state.phase, target):
        return AdvancePhaseResponse(
            success=False,
            previous_phase=previous_phase.value,
            current_phase=previous_phase.value,
            message=f"Cannot transition from {state.phase.value} to {target.value}"
        )
    
    # Perform transition
    state.phase = target
    
    # Add transcript entry for phase change
    state.transcript.append({
        "speaker": "SYSTEM",
        "role": "system",
        "text": f"--- {target.value.upper()} PHASE BEGINS ---",
        "phase": target.value,
        "timestamp": None
    })
    
    _save_transcript_snapshot(session_id)

    return AdvancePhaseResponse(
        success=True,
        previous_phase=previous_phase.value,
        current_phase=target.value,
        message=f"Advanced from {previous_phase.value} to {target.value}"
    )


@router.post("/{session_id}/validate-speaker", response_model=ValidateSpeakerResponse)
async def validate_speaker_permission(session_id: str, request: ValidateSpeakerRequest):
    """
    Validate if a role can speak in current state.
    
    Per trial_graph.py: SPEAKER_PERMISSIONS defines who can speak when.
    """
    session = get_session(session_id)
    state = session.trial_state
    
    # Parse role
    try:
        role = Role(request.role)
    except ValueError:
        return ValidateSpeakerResponse(
            role=request.role,
            can_speak=False,
            reason=f"Invalid role: {request.role}"
        )
    
    valid, reason = validate_speaker(state, role)
    
    return ValidateSpeakerResponse(
        role=role.value,
        can_speak=valid,
        reason=reason
    )


@router.post("/{session_id}/check-objection", response_model=ObjectionCheckResponse)
async def check_objection_validity(session_id: str, request: ObjectionCheckRequest):
    """
    Check if an objection would be valid.
    
    Per trial_graph.py: Objections only valid in TESTIMONY_STATES.
    """
    session = get_session(session_id)
    state = session.trial_state
    
    # Parse role
    try:
        role = Role(request.objecting_role)
    except ValueError:
        return ObjectionCheckResponse(
            can_object=False,
            objection_type_valid=False,
            reason=f"Invalid role: {request.objecting_role}"
        )
    
    # Check if objection type is valid
    type_valid = request.objection_type in VALID_OBJECTION_TYPES
    
    # Check if can object
    valid, reason = can_object(state, role)
    
    return ObjectionCheckResponse(
        can_object=valid,
        objection_type_valid=type_valid,
        reason=reason if not valid else (f"Invalid objection type: {request.objection_type}" if not type_valid else None)
    )


@router.get("/{session_id}/valid-objection-types")
async def get_valid_objection_types(session_id: str):
    """Get list of valid objection types."""
    # Verify session exists
    get_session(session_id)
    
    return {
        "objection_types": list(VALID_OBJECTION_TYPES)
    }


@router.post("/{session_id}/objection", response_model=RaiseObjectionResponse)
async def raise_objection(session_id: str, request: RaiseObjectionRequest):
    """
    Raise an objection during testimony.
    
    The judge AI will rule on the objection.
    """
    session = get_session(session_id)
    state = session.trial_state
    
    # Parse role
    try:
        role = Role(request.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")
    
    # Check if objection type is valid
    if request.objection_type not in VALID_OBJECTION_TYPES:
        raise HTTPException(status_code=400, detail=f"Invalid objection type: {request.objection_type}")
    
    # Check if can object
    valid, reason = can_object(state, role)
    if not valid:
        raise HTTPException(status_code=400, detail=reason or "Cannot object in current state")
    
    # Set objection pending
    state.objection_pending = True
    
    # Add objection to transcript
    role_label = "Plaintiff" if "plaintiff" in request.role else "Defense"
    state.transcript.append({
        "speaker": f"{role_label} Attorney",
        "role": request.role,
        "text": f"Objection! {request.objection_type.replace('_', ' ').title()}.",
        "phase": state.phase.value,
        "timestamp": None
    })
    
    # Use judge agent to rule on objection if available
    sustained = False
    explanation = ""
    
    # Get recent transcript for context
    recent_transcript = state.transcript[-5:] if len(state.transcript) > 5 else state.transcript
    recent_text = "\n".join([f"{e.get('speaker', 'Unknown')}: {e.get('text', '')}" for e in recent_transcript[:-1]])  # Exclude the objection itself
    
    if session.judges:
        judge = session.judges[0]
        try:
            sustained, explanation = judge.rule_on_objection(
                state=state,
                objection_type=request.objection_type,
                objecting_party=role,
                question_or_testimony=recent_text or "Recent testimony",
                context={
                    "examination_type": state.phase.value,
                    "witness_name": "the witness"
                },
                trial_memory=session.trial_memory,
            )
        except Exception as e:
            logger.error(f"Judge ruling failed: {e}")
            import random
            sustained = random.choice([True, False])
            explanation = f"The objection is {'well-taken' if sustained else 'not well-founded'}."
    else:
        import random
        sustained = random.choice([True, False])
        explanation = f"The objection is {'well-taken' if sustained else 'not well-founded'}."
    
    # Add ruling to transcript
    state.transcript.append({
        "speaker": "Judge",
        "role": "judge",
        "text": explanation,
        "phase": state.phase.value,
        "timestamp": None
    })
    
    # Clear objection pending
    state.objection_pending = False
    
    return RaiseObjectionResponse(
        objection_type=request.objection_type,
        sustained=sustained,
        explanation=explanation,
        ruling_by="Judge"
    )


@router.get("/{session_id}/phases")
async def get_trial_phases(session_id: str):
    """Get all trial phases and current phase."""
    session = get_session(session_id)
    
    return {
        "current_phase": session.trial_state.phase.value,
        "all_phases": [p.value for p in TrialPhase],
        "testimony_phases": [p.value for p in TESTIMONY_STATES]
    }


@router.get("/{session_id}/transcript")
async def get_transcript(session_id: str, limit: Optional[int] = None):
    """Get trial transcript."""
    session = get_session(session_id)
    
    transcript = session.trial_state.transcript
    
    if limit:
        transcript = transcript[-limit:]
    
    return {
        "session_id": session_id,
        "total_entries": len(session.trial_state.transcript),
        "returned_entries": len(transcript),
        "transcript": transcript
    }


class RecordTranscriptRequest(BaseModel):
    speaker: str = Field(..., max_length=200)
    role: str = Field(..., pattern=r"^(attorney_plaintiff|attorney_defense|attorney|witness|judge|clerk|bailiff|narrator)$")
    text: str = Field(..., max_length=50000)
    phase: str = Field(..., max_length=100)
    event_type: Optional[str] = Field(None, max_length=50)


@router.post("/{session_id}/record-transcript")
async def record_transcript(session_id: str, request: RecordTranscriptRequest):
    """Record a transcript entry from the frontend (e.g. opening statements loaded from prep cache)."""
    session = get_session(session_id)
    session.trial_state.transcript.append({
        "speaker": request.speaker,
        "role": request.role,
        "text": request.text,
        "phase": request.phase,
        "event_type": request.event_type or "speech",
        "timestamp": None,
    })
    return {"success": True}


# =============================================================================
# AI TURN ENDPOINT
# =============================================================================

VALID_AI_ACTIONS = {
    "opening", "closing", "cross_question", "direct_question",
    "witness_answer", "redirect_question", "redirect_answer",
    "recross_question", "recross_answer",
}


class AITurnRequest(BaseModel):
    """Request for AI to take its turn."""
    action: str = Field(..., max_length=50)
    witness_id: Optional[str] = Field(None, max_length=100)
    is_teammate: bool = False
    regenerate: bool = False


class AITurnResponse(BaseModel):
    """Response from AI's turn."""
    success: bool
    speaker: str
    role: str
    text: str
    phase: str
    attorney_name: Optional[str] = None
    attorney_role: Optional[str] = None
    audio_url: Optional[str] = None
    message: str = ""
    cached: bool = False


@router.post("/{session_id}/ai-turn", response_model=AITurnResponse)
async def ai_take_turn(session_id: str, request: AITurnRequest):
    """
    Have the AI take its turn in the trial.
    
    This endpoint triggers the appropriate AI agent to generate content
    based on the current trial phase and requested action:
    - opening: AI opposing opening attorney delivers opening statement
    - closing: AI opposing closing attorney delivers closing argument
    - cross_question: AI opposing direct/cross attorney asks cross-examination question
    - direct_question: AI attorney asks a direct examination question
    - witness_answer: AI witness answers the last question
    """
    session = get_session(session_id)
    state = session.trial_state

    human_side = "plaintiff" if session.human_role == Role.ATTORNEY_PLAINTIFF else "defense"

    if request.is_teammate:
        ai_side = human_side
        ai_role_label = "Prosecution" if human_side == "plaintiff" else "Defense"
    else:
        if session.human_role == Role.ATTORNEY_PLAINTIFF:
            ai_side = "defense"
            ai_role_label = "Defense"
        else:
            ai_side = "plaintiff"
            ai_role_label = "Prosecution"

    action = request.action.lower()
    if action not in VALID_AI_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid action. Must be one of: {', '.join(sorted(VALID_AI_ACTIONS))}"
        )
    teammate_tag = " (Teammate)" if request.is_teammate else ""

    # AI turns bypass the normal speaker validation since they're triggered
    # explicitly by the user. Temporarily override phase if needed.
    saved_phase = state.phase
    PHASE_FOR_ACTION = {
        "opening": TrialPhase.OPENING,
        "closing": TrialPhase.CLOSING,
        "cross_question": TrialPhase.CROSS,
        "direct_question": TrialPhase.DIRECT,
        "witness_answer": TrialPhase.DIRECT,
    }
    if action in PHASE_FOR_ACTION and state.phase != PHASE_FOR_ACTION[action]:
        state.phase = PHASE_FOR_ACTION[action]
        logger.info(f"AI turn: temporarily set phase to {state.phase.value} for action '{action}'")

    try:
        # --- OPENING STATEMENT ---
        if action == "opening":
            team_key = f"{ai_side}_opening"
            agent = session.attorney_team.get(team_key) or session.attorneys.get(ai_side)
            if not agent:
                return AITurnResponse(
                    success=False, speaker="", role="", text="",
                    phase=saved_phase.value, message="No AI opening attorney configured"
                )

            attorney_name = agent.persona.name
            cache_key = f"opening_{ai_side}"
            cached = False

            if not request.regenerate and session.prep_materials.get(cache_key):
                text = session.prep_materials[cache_key]
                cached = True
                logger.info(f"Using cached opening for {ai_side} (session cache)")
            elif not request.regenerate and session.case_id:
                from .preparation import get_cached_materials_from_db
                db_materials = get_cached_materials_from_db(session.case_id)
                if db_materials and db_materials.get(cache_key):
                    text = db_materials[cache_key]
                    session.prep_materials[cache_key] = text
                    cached = True
                    logger.info(f"Using cached opening for {ai_side} (DB cache)")
                else:
                    text = agent.generate_opening(state, case_data=session.case_data)
                    session.prep_materials[cache_key] = text
            else:
                text = agent.generate_opening(state, case_data=session.case_data)
                session.prep_materials[cache_key] = text
            
            state.transcript.append({
                "speaker": f"{ai_role_label} Opening Attorney{teammate_tag} ({attorney_name})",
                "role": f"attorney_{ai_side}",
                "text": text,
                "phase": state.phase.value,
                "event_type": "opening_statement",
                "timestamp": None,
            })

            # Record opening to trial memory and team shared
            session.trial_memory.record_opening(ai_side, text)
            try:
                session.trial_memory.record_team_heard(
                    ai_side,
                    f"{ai_role_label} Opening Attorney{teammate_tag} ({attorney_name})",
                    f"Opening statement delivered: {text[:200]}...",
                )
            except Exception:
                pass

            from ..config import ENABLE_STRATEGIC_ANALYSIS
            if ENABLE_STRATEGIC_ANALYSIS:
                try:
                    from ..services.strategic_analyzer import analyze_opening_for_teams
                    pt = ""
                    dt = ""
                    for sub in ("opening", "direct_cross", "closing"):
                        pa = session.attorney_team.get(f"plaintiff_{sub}")
                        if pa and pa.persona.case_theory:
                            pt = pa.persona.case_theory
                            break
                    for sub in ("opening", "direct_cross", "closing"):
                        da = session.attorney_team.get(f"defense_{sub}")
                        if da and da.persona.case_theory:
                            dt = da.persona.case_theory
                            break
                    asyncio.create_task(analyze_opening_for_teams(
                        trial_memory=session.trial_memory,
                        side_that_spoke=ai_side,
                        opening_text=text,
                        case_theory_plaintiff=pt,
                        case_theory_defense=dt,
                    ))
                except Exception as e:
                    logger.warning(f"Failed to launch opening analysis: {e}")

            return AITurnResponse(
                success=True,
                speaker=f"{ai_role_label} Opening Attorney{teammate_tag}",
                role=f"attorney_{ai_side}",
                text=text,
                phase=state.phase.value,
                attorney_name=attorney_name,
                attorney_role="opening",
                cached=cached,
            )

        # --- CLOSING ARGUMENT ---
        elif action == "closing":
            team_key = f"{ai_side}_closing"
            agent = session.attorney_team.get(team_key) or session.attorneys.get(ai_side)
            if not agent:
                return AITurnResponse(
                    success=False, speaker="", role="", text="",
                    phase=state.phase.value, message="No AI closing attorney configured"
                )

            attorney_name = agent.persona.name
            cache_key = f"closing_{ai_side}"
            cached = False

            if not request.regenerate and cache_key in session.prep_materials:
                text = session.prep_materials[cache_key]
                cached = True
            else:
                text = agent.generate_closing(
                    state, state.transcript, trial_memory=session.trial_memory
                )
                session.prep_materials[cache_key] = text
            
            state.transcript.append({
                "speaker": f"{ai_role_label} Closing Attorney{teammate_tag} ({attorney_name})",
                "role": f"attorney_{ai_side}",
                "text": text,
                "phase": state.phase.value,
                "event_type": "closing_argument",
                "timestamp": None,
            })

            return AITurnResponse(
                success=True,
                speaker=f"{ai_role_label} Closing Attorney{teammate_tag}",
                role=f"attorney_{ai_side}",
                text=text,
                phase=state.phase.value,
                attorney_name=attorney_name,
                attorney_role="closing",
                cached=cached,
            )

        # --- CROSS-EXAMINATION QUESTION ---
        elif action == "cross_question":
            team_key = f"{ai_side}_direct_cross"
            agent = session.attorney_team.get(team_key) or session.attorneys.get(ai_side)
            if not agent:
                return AITurnResponse(
                    success=False, speaker="", role="", text="",
                    phase=state.phase.value, message="No AI cross attorney configured"
                )

            # Get current witness info
            witness_id = request.witness_id or state.current_witness_id
            witness_agent = session.witnesses.get(witness_id) if witness_id else None
            witness_name = witness_agent.persona.name if witness_agent else "the witness"
            witness_affidavit = witness_agent.persona.affidavit if witness_agent else ""

            # Get direct testimony and prior cross from transcript
            direct_testimony = [
                {"question": e.get("text", ""), "answer": ""}
                for e in state.transcript
                if e.get("phase") in ("DIRECT", "REDIRECT") and e.get("role") == "witness"
            ]
            prior_cross = [
                {"question": e.get("text", ""), "answer": ""}
                for e in state.transcript
                if e.get("phase") in ("CROSS", "RECROSS") and e.get("role") == f"attorney_{ai_side}"
            ]

            text = agent.generate_cross_question(
                state, witness_name, witness_affidavit, direct_testimony, prior_cross,
                trial_memory=session.trial_memory,
            )
            attorney_name = agent.persona.name

            state.transcript.append({
                "speaker": f"{ai_role_label} Attorney{teammate_tag} ({attorney_name})",
                "role": f"attorney_{ai_side}",
                "text": text,
                "phase": state.phase.value,
                "event_type": "cross_question",
                "timestamp": None,
            })

            return AITurnResponse(
                success=True,
                speaker=f"{ai_role_label} Attorney{teammate_tag}",
                role=f"attorney_{ai_side}",
                text=text,
                phase=state.phase.value,
                attorney_name=attorney_name,
                attorney_role="direct_cross",
            )

        # --- DIRECT EXAMINATION QUESTION ---
        elif action == "direct_question":
            team_key = f"{ai_side}_direct_cross"
            agent = session.attorney_team.get(team_key) or session.attorneys.get(ai_side)
            if not agent:
                return AITurnResponse(
                    success=False, speaker="", role="", text="",
                    phase=state.phase.value, message="No AI direct attorney configured"
                )

            witness_id = request.witness_id or state.current_witness_id
            witness_agent = session.witnesses.get(witness_id) if witness_id else None
            witness_name = witness_agent.persona.name if witness_agent else "the witness"
            witness_affidavit = witness_agent.persona.affidavit if witness_agent else ""

            prior_testimony = [
                {"question": e.get("text", ""), "answer": ""}
                for e in state.transcript
                if e.get("phase") == "DIRECT" and witness_id and e.get("witness_id") == witness_id
            ]

            text = agent.generate_direct_question(
                state, witness_name, witness_affidavit, prior_testimony,
                trial_memory=session.trial_memory,
            )
            attorney_name = agent.persona.name

            state.transcript.append({
                "speaker": f"{ai_role_label} Attorney{teammate_tag} ({attorney_name})",
                "role": f"attorney_{ai_side}",
                "text": text,
                "phase": state.phase.value,
                "event_type": "direct_question",
                "timestamp": None,
            })

            return AITurnResponse(
                success=True,
                speaker=f"{ai_role_label} Attorney{teammate_tag}",
                role=f"attorney_{ai_side}",
                text=text,
                phase=state.phase.value,
                attorney_name=attorney_name,
                attorney_role="direct_cross",
            )

        # --- WITNESS ANSWER ---
        elif action == "witness_answer":
            witness_id = request.witness_id or state.current_witness_id
            if not witness_id or witness_id not in session.witnesses:
                return AITurnResponse(
                    success=False, speaker="", role="", text="",
                    phase=state.phase.value, message="No witness on the stand"
                )

            witness_agent = session.witnesses[witness_id]

            # Find the last question in transcript
            last_question = ""
            for entry in reversed(state.transcript):
                if entry.get("event_type") in ("cross_question", "direct_question") or (
                    "attorney" in entry.get("role", "") and "?" in entry.get("text", "")
                ):
                    last_question = entry.get("text", "")
                    break

            if not last_question:
                return AITurnResponse(
                    success=False, speaker="", role="", text="",
                    phase=state.phase.value, message="No question to answer"
                )

            # Determine questioner side
            questioner_side = ai_side  # AI asked, so AI side
            if session.human_role == Role.ATTORNEY_PLAINTIFF:
                if state.phase in (TrialPhase.DIRECT, TrialPhase.REDIRECT):
                    questioner_side = "plaintiff"  # Human direct
                else:
                    questioner_side = "defense"  # AI cross
            else:
                if state.phase in (TrialPhase.DIRECT, TrialPhase.REDIRECT):
                    questioner_side = "defense"
                else:
                    questioner_side = "plaintiff"

            text = witness_agent.answer_question(
                state, last_question, questioner_side,
                trial_memory=session.trial_memory,
            )

            state.transcript.append({
                "speaker": witness_agent.persona.name,
                "role": "witness",
                "text": text,
                "phase": state.phase.value,
                "event_type": "witness_answer",
                "witness_id": witness_id,
                "timestamp": None,
            })

            # Update team shared memory and trial memory for this Q&A
            if session.trial_memory:
                calling_side = getattr(witness_agent.persona, "called_by", "plaintiff")
                if calling_side in ("prosecution", "plaintiff"):
                    calling_side = "plaintiff"
                exam_type = state.phase.value.lower() if state.phase else "direct"
                session.trial_memory.record_exam_event(
                    witness_id=witness_id,
                    witness_name=witness_agent.persona.name,
                    exam_type=exam_type,
                    questioner_side=questioner_side,
                    question=last_question,
                    answer=text,
                )
                session.trial_memory.update_team_shared_from_testimony(
                    side=calling_side,
                    witness_name=witness_agent.persona.name,
                    witness_id=witness_id,
                    question=last_question,
                    answer=text,
                    exam_type=exam_type,
                    questioner_side=questioner_side,
                )

            return AITurnResponse(
                success=True,
                speaker=witness_agent.persona.name,
                role="witness",
                text=text,
                phase=state.phase.value,
            )

        else:
            return AITurnResponse(
                success=False, speaker="", role="", text="",
                phase=state.phase.value,
                message=f"Unknown action: {action}. Use: opening, closing, cross_question, direct_question, witness_answer"
            )

    except Exception as e:
        logger.error(f"AI turn failed: {e}", exc_info=True)
        return AITurnResponse(
            success=False, speaker="", role="", text="",
            phase=saved_phase.value, message="AI generation failed"
        )
    finally:
        state.phase = saved_phase


# =============================================================================
# WITNESS & EXAMINATION MANAGEMENT ENDPOINTS
# =============================================================================

class CallWitnessRequest(BaseModel):
    witness_id: str
    calling_side: str  # "plaintiff" or "defense"


class CompleteExamRequest(BaseModel):
    examination_type: str  # "direct", "cross", "redirect", "recross"


class RestCaseRequest(BaseModel):
    side: str  # "prosecution"/"plaintiff" or "defense"


def _resolve_witness_side(session, w) -> str:
    """Determine which side a witness belongs to, respecting restrictions
    and trial-prep assignments. Returns 'plaintiff' or 'defense'."""
    wid = w.get("id", "")
    name = w.get("name", "").lower()
    called_by = w.get("called_by", "").lower()

    # Hard restrictions from case packet override everything
    restrictions = (session.case_data or {}).get("witness_calling_restrictions", {})
    if restrictions:
        for pn in restrictions.get("prosecution_only", []):
            if pn.lower() in name or name in pn.lower():
                return "plaintiff"
        for dn in restrictions.get("defense_only", []):
            if dn.lower() in name or name in dn.lower():
                return "defense"

    # For "either" witnesses, use the session's trial-prep assignment
    if called_by == "either":
        return getattr(session, "witness_assignments", {}).get(wid, "plaintiff")

    if called_by in ("plaintiff", "prosecution"):
        return "plaintiff"
    if called_by == "defense":
        return "defense"
    return "plaintiff"


def _ensure_witness_lists(session, state):
    """Populate prosecution/defense witness lists and witnesses_to_examine.

    Re-checks every time to catch witnesses that were added after initial setup
    (e.g. from section uploads that parsed new witness data).
    Respects calling restrictions and trial-prep witness assignments.
    """
    case_witnesses = session.case_data.get("witnesses", []) if session.case_data else []
    existing_pros = set(state.prosecution_witnesses)
    existing_def = set(state.defense_witnesses)

    for w in case_witnesses:
        wid = w.get("id")
        if not wid or wid not in session.witnesses:
            continue

        side = _resolve_witness_side(session, w)

        if side == "defense":
            if wid not in existing_def:
                state.defense_witnesses.append(wid)
                existing_def.add(wid)
            if wid in existing_pros:
                state.prosecution_witnesses.remove(wid)
                existing_pros.discard(wid)
        else:
            if wid not in existing_pros:
                state.prosecution_witnesses.append(wid)
                existing_pros.add(wid)
            if wid in existing_def:
                state.defense_witnesses.remove(wid)
                existing_def.discard(wid)

        if wid not in state.witnesses_to_examine and wid not in state.witnesses_examined:
            state.witnesses_to_examine.append(wid)

    witness_assignments = getattr(session, "witness_assignments", {})
    logger.info(
        f"Witness lists built: prosecution={state.prosecution_witnesses}, "
        f"defense={state.defense_witnesses}, "
        f"to_examine={state.witnesses_to_examine}, "
        f"examined={state.witnesses_examined}, "
        f"witness_assignments={witness_assignments}"
    )


@router.get("/{session_id}/witnesses")
async def get_witnesses(session_id: str):
    """Get all witnesses with their current status and case-in-chief info."""
    session = get_session(session_id)
    state = session.trial_state
    _ensure_witness_lists(session, state)

    witnesses = []
    case_witnesses = session.case_data.get("witnesses", []) if session.case_data else []
    case_witness_map = {w.get("id"): w for w in case_witnesses}

    witness_assignments = getattr(session, "witness_assignments", {})
    for wid, agent in session.witnesses.items():
        cw = case_witness_map.get(wid, {})
        original_cb = (cw.get("called_by") or "unknown").lower()
        if original_cb == "prosecution":
            original_cb = "plaintiff"
        agent_cb = getattr(agent.persona, "called_by", None)
        if agent_cb:
            norm_cb = agent_cb
        else:
            raw_cb = original_cb
            norm_cb = "plaintiff" if raw_cb in ("plaintiff", "prosecution", "either") else raw_cb
        is_either = original_cb == "either"
        entry = {
            "id": wid,
            "name": agent.persona.name,
            "called_by": norm_cb,
            "is_current": state.current_witness_id == wid,
            "is_examined": wid in state.witnesses_examined,
            "is_pending": wid in state.witnesses_to_examine,
        }
        if is_either:
            entry["original_side"] = "either"
            entry["assigned_side"] = witness_assignments.get(wid, "plaintiff")
            entry["is_reassignable"] = True
        witnesses.append(entry)

    return {
        "session_id": session_id,
        "current_witness_id": state.current_witness_id,
        "current_witness_name": (
            session.witnesses[state.current_witness_id].persona.name
            if state.current_witness_id and state.current_witness_id in session.witnesses
            else None
        ),
        "witnesses_remaining": len(state.witnesses_to_examine),
        "witnesses_examined_count": len(state.witnesses_examined),
        "case_in_chief": state.case_in_chief,
        "prosecution_rested": state.prosecution_rested,
        "defense_rested": state.defense_rested,
        "prosecution_witnesses": state.prosecution_witnesses,
        "defense_witnesses": state.defense_witnesses,
        "witness_calling_restrictions": state.witness_calling_restrictions or {},
        "exam_status": {
            "direct_complete": state.direct_complete,
            "cross_complete": state.cross_complete,
            "redirect_complete": state.redirect_complete,
            "recross_complete": state.recross_complete,
            "redirect_requested": state.redirect_requested,
            "recross_requested": state.recross_requested,
        },
        "witnesses": witnesses,
    }


@router.post("/{session_id}/call-witness")
async def call_witness_to_stand(session_id: str, request: CallWitnessRequest):
    """Call a witness to the stand."""
    from ..graph.trial_graph import call_witness as graph_call_witness, validate_witness_calling
    session = get_session(session_id)
    state = session.trial_state
    _ensure_witness_lists(session, state)

    witness_id = request.witness_id
    if witness_id not in session.witnesses:
        raise HTTPException(status_code=404, detail=f"Witness '{witness_id}' not found")

    agent = session.witnesses[witness_id]
    witness_name = agent.persona.name
    calling_side = request.calling_side or state.case_in_chief

    # Enforce: each side may only call witnesses on their own list
    if calling_side in ("prosecution", "plaintiff"):
        if witness_id not in state.prosecution_witnesses:
            raise HTTPException(
                status_code=400,
                detail=f"{witness_name} is not a prosecution witness and cannot be called by the prosecution."
            )
    elif calling_side == "defense":
        if witness_id not in state.defense_witnesses:
            raise HTTPException(
                status_code=400,
                detail=f"{witness_name} is not a defense witness and cannot be called by the defense."
            )

    # Enforce witness_calling_restrictions from the case packet
    allowed, err_msg = validate_witness_calling(state, witness_name, calling_side)
    if not allowed:
        raise HTTPException(status_code=400, detail=err_msg)

    graph_call_witness(state, witness_id, calling_side)

    if state.last_error:
        err = state.last_error
        state.last_error = None
        raise HTTPException(status_code=400, detail=err)

    # Ensure phase is DIRECT for new witness
    if state.phase not in (TrialPhase.DIRECT, TrialPhase.CROSS, TrialPhase.REDIRECT, TrialPhase.RECROSS):
        state.phase = TrialPhase.DIRECT

    state.transcript.append({
        "speaker": "SYSTEM",
        "role": "system",
        "text": f"The Court calls {witness_name} to the stand.",
        "phase": state.phase.value,
        "event_type": "call_witness",
        "timestamp": None,
    })

    return {
        "success": True,
        "witness_id": witness_id,
        "witness_name": witness_name,
        "calling_side": request.calling_side,
        "message": f"{witness_name} has been called to the stand.",
    }


@router.post("/{session_id}/complete-examination")
async def complete_examination_endpoint(session_id: str, request: CompleteExamRequest):
    """
    Mark the current examination type as complete and determine next step.
    Returns the next action the frontend should take.
    """
    from ..graph.trial_graph import complete_examination, dismiss_witness
    session = get_session(session_id)
    state = session.trial_state

    if not state.current_witness_id:
        raise HTTPException(status_code=400, detail="No witness on the stand")

    exam_type = request.examination_type.lower()
    if exam_type not in ("direct", "cross", "redirect", "recross"):
        raise HTTPException(status_code=400, detail=f"Invalid examination type: {exam_type}")

    witness_name = session.witnesses[state.current_witness_id].persona.name
    complete_examination(state, exam_type)

    # Determine next action
    next_action = None
    next_phase = None

    if exam_type == "direct":
        next_action = "cross"
        next_phase = "CROSS"
        state.phase = TrialPhase.CROSS
        state.transcript.append({
            "speaker": "SYSTEM", "role": "system",
            "text": f"Direct examination of {witness_name} is complete. Cross-examination may begin.",
            "phase": state.phase.value, "event_type": "exam_complete", "timestamp": None,
        })
    elif exam_type == "cross":
        next_action = "offer_redirect"
        next_phase = state.phase.value
        state.transcript.append({
            "speaker": "SYSTEM", "role": "system",
            "text": f"Cross-examination of {witness_name} is complete.",
            "phase": state.phase.value, "event_type": "exam_complete", "timestamp": None,
        })
    elif exam_type == "redirect":
        next_action = "offer_recross"
        next_phase = state.phase.value
        state.transcript.append({
            "speaker": "SYSTEM", "role": "system",
            "text": f"Redirect examination of {witness_name} is complete.",
            "phase": state.phase.value, "event_type": "exam_complete", "timestamp": None,
        })
    elif exam_type == "recross":
        dismiss_witness(state)
        next_action = "witness_done"
        next_phase = "DIRECT"
        state.phase = TrialPhase.DIRECT
        state.transcript.append({
            "speaker": "SYSTEM", "role": "system",
            "text": f"Examination of {witness_name} is complete. The witness is excused.",
            "phase": state.phase.value, "event_type": "witness_excused", "timestamp": None,
        })

    return {
        "success": True,
        "examination_completed": exam_type,
        "witness_name": witness_name,
        "next_action": next_action,
        "next_phase": next_phase,
        "exam_status": {
            "direct_complete": state.direct_complete,
            "cross_complete": state.cross_complete,
            "redirect_complete": state.redirect_complete,
            "recross_complete": state.recross_complete,
        },
    }


@router.post("/{session_id}/request-redirect")
async def request_redirect_endpoint(session_id: str):
    """Request redirect examination after cross."""
    from ..graph.trial_graph import request_redirect
    session = get_session(session_id)
    state = session.trial_state
    request_redirect(state)
    if state.last_error:
        err = state.last_error
        state.last_error = None
        raise HTTPException(status_code=400, detail=err)
    state.phase = TrialPhase.REDIRECT
    return {"success": True, "phase": state.phase.value}


@router.post("/{session_id}/waive-redirect")
async def waive_redirect_endpoint(session_id: str):
    """Waive redirect, excusing the witness."""
    from ..graph.trial_graph import waive_redirect
    session = get_session(session_id)
    state = session.trial_state
    waive_redirect(state)
    witness_name = "the witness"
    state.phase = TrialPhase.DIRECT
    state.transcript.append({
        "speaker": "SYSTEM", "role": "system",
        "text": "Redirect is waived. The witness is excused.",
        "phase": state.phase.value, "event_type": "witness_excused", "timestamp": None,
    })
    return {"success": True, "next_action": "witness_done", "phase": state.phase.value}


@router.post("/{session_id}/request-recross")
async def request_recross_endpoint(session_id: str):
    """Request recross examination after redirect."""
    from ..graph.trial_graph import request_recross
    session = get_session(session_id)
    state = session.trial_state
    request_recross(state)
    if state.last_error:
        err = state.last_error
        state.last_error = None
        raise HTTPException(status_code=400, detail=err)
    state.phase = TrialPhase.RECROSS
    return {"success": True, "phase": state.phase.value}


@router.post("/{session_id}/waive-recross")
async def waive_recross_endpoint(session_id: str):
    """Waive recross, excusing the witness."""
    from ..graph.trial_graph import waive_recross
    session = get_session(session_id)
    state = session.trial_state
    waive_recross(state)
    state.phase = TrialPhase.DIRECT
    state.transcript.append({
        "speaker": "SYSTEM", "role": "system",
        "text": "Recross is waived. The witness is excused.",
        "phase": state.phase.value, "event_type": "witness_excused", "timestamp": None,
    })
    return {"success": True, "next_action": "witness_done", "phase": state.phase.value}


@router.post("/{session_id}/rest-case")
async def rest_case_endpoint(session_id: str, request: RestCaseRequest):
    """Mark a side as resting their case."""
    from ..graph.trial_graph import rest_case
    session = get_session(session_id)
    state = session.trial_state

    side = request.side.lower()
    rest_case(state, side)

    side_label = "Prosecution" if side in ("plaintiff", "prosecution") else "Defense"
    state.transcript.append({
        "speaker": "SYSTEM", "role": "system",
        "text": f"The {side_label} rests.",
        "phase": state.phase.value, "event_type": "rest_case", "timestamp": None,
    })

    if state.prosecution_rested and state.defense_rested:
        next_action = "closing"
    elif state.prosecution_rested and not state.defense_rested:
        next_action = "defense_case"
        state.transcript.append({
            "speaker": "SYSTEM", "role": "system",
            "text": "The Defense may now present its case-in-chief.",
            "phase": state.phase.value, "event_type": "defense_case_begins", "timestamp": None,
        })
    else:
        next_action = "continue"

    return {
        "success": True,
        "side": side_label,
        "next_action": next_action,
        "case_in_chief": state.case_in_chief,
        "prosecution_rested": state.prosecution_rested,
        "defense_rested": state.defense_rested,
    }


_DEFAULT_DIRECT = int(os.environ.get("DEFAULT_DIRECT_QUESTIONS", "3"))
_DEFAULT_CROSS = int(os.environ.get("DEFAULT_CROSS_QUESTIONS", "3"))
_DEFAULT_REDIRECT = int(os.environ.get("DEFAULT_REDIRECT_QUESTIONS", "2"))
_DEFAULT_RECROSS = int(os.environ.get("DEFAULT_RECROSS_QUESTIONS", "1"))


class AutoExamRequest(BaseModel):
    witness_id: str
    calling_side: str  # "plaintiff" or "defense"
    num_direct_questions: int = _DEFAULT_DIRECT
    num_cross_questions: int = _DEFAULT_CROSS
    num_redirect_questions: int = _DEFAULT_REDIRECT
    num_recross_questions: int = _DEFAULT_RECROSS
    skip_redirect: bool = False
    skip_recross: bool = False


@router.post("/{session_id}/auto-examine")
async def auto_examine_witness(session_id: str, request: AutoExamRequest):
    """
    Generate a complete examination sequence for a witness.
    Returns all Q&A pairs for direct, cross, redirect, recross in one batch
    so the frontend can play them sequentially without per-question round trips.
    """
    from ..graph.trial_graph import (
        call_witness as graph_call_witness,
        complete_examination,
        dismiss_witness,
        request_redirect,
        request_recross,
    )
    session = get_session(session_id)
    state = session.trial_state
    _ensure_witness_lists(session, state)

    witness_id = request.witness_id
    logger.info(
        f"Auto-examine requested: witness={witness_id}, calling_side={request.calling_side}, "
        f"phase={state.phase.value}, case_in_chief={state.case_in_chief}, "
        f"prosecution_witnesses={state.prosecution_witnesses}, "
        f"defense_witnesses={state.defense_witnesses}, "
        f"to_examine={state.witnesses_to_examine}, examined={state.witnesses_examined}"
    )

    if witness_id not in session.witnesses:
        raise HTTPException(status_code=404, detail=f"Witness '{witness_id}' not found in session (available: {list(session.witnesses.keys())})")

    witness_agent = session.witnesses[witness_id]
    witness_name = witness_agent.persona.name

    # Normalize calling_side: "prosecution" -> "plaintiff" for internal lookups
    raw_calling = request.calling_side
    calling_side = "plaintiff" if raw_calling in ("plaintiff", "prosecution") else "defense"

    # Enforce: each side may only call witnesses on their own list
    from ..graph.trial_graph import validate_witness_calling
    if calling_side == "plaintiff":
        if witness_id not in state.prosecution_witnesses:
            logger.warning(
                f"BLOCKED: {witness_name} ({witness_id}) is NOT in prosecution_witnesses "
                f"{state.prosecution_witnesses}. Request calling_side={request.calling_side}"
            )
            raise HTTPException(
                status_code=400,
                detail=f"{witness_name} is not a prosecution witness and cannot be called by the prosecution."
            )
    elif calling_side == "defense":
        if witness_id not in state.defense_witnesses:
            logger.warning(
                f"BLOCKED: {witness_name} ({witness_id}) is NOT in defense_witnesses "
                f"{state.defense_witnesses}. Request calling_side={request.calling_side}"
            )
            raise HTTPException(
                status_code=400,
                detail=f"{witness_name} is not a defense witness and cannot be called by the defense."
            )

    logger.info(f"ALLOWED: {calling_side} calling {witness_name} ({witness_id})")

    # Enforce witness_calling_restrictions from case packet
    allowed, err_msg = validate_witness_calling(state, witness_name, calling_side)
    if not allowed:
        raise HTTPException(status_code=400, detail=err_msg)

    # Ensure witness is in the pending list
    if witness_id not in state.witnesses_to_examine and witness_id not in state.witnesses_examined:
        state.witnesses_to_examine.append(witness_id)

    logger.info(f"Examining witness: {witness_name} (id={witness_id}), affidavit length={len(witness_agent.persona.affidavit or '')}")

    human_side = "plaintiff" if session.human_role == Role.ATTORNEY_PLAINTIFF else "defense"
    opposing_side = "defense" if calling_side == "plaintiff" else "plaintiff"

    calling_label = "Prosecution" if calling_side == "plaintiff" else "Defense"
    opposing_label = "Defense" if calling_side == "plaintiff" else "Prosecution"

    direct_team_key = f"{calling_side}_direct_cross"
    direct_agent = session.attorney_team.get(direct_team_key) or session.attorneys.get(calling_side)
    cross_team_key = f"{opposing_side}_direct_cross"
    cross_agent = session.attorney_team.get(cross_team_key) or session.attorneys.get(opposing_side)

    # Fallback: try any attorney on that side from the team
    if not direct_agent:
        for k, v in session.attorney_team.items():
            if k.startswith(calling_side):
                direct_agent = v
                logger.warning(f"direct_agent fallback to {k}")
                break
    if not cross_agent:
        for k, v in session.attorney_team.items():
            if k.startswith(opposing_side):
                cross_agent = v
                logger.warning(f"cross_agent fallback to {k}")
                break

    # Last resort: create a temporary attorney if still missing
    if not direct_agent or not cross_agent:
        from .session import create_attorney_agent
        from ..agents import AttorneyStyle, SkillLevel
        if not direct_agent:
            logger.warning(f"Creating fallback direct attorney for side={calling_side}")
            direct_agent = create_attorney_agent(
                name=f"{calling_label} Counsel",
                side=calling_side,
                style=AttorneyStyle.METHODICAL,
                skill_level=SkillLevel.EXPERT,
                case_theory=f"Represent the {calling_label} effectively.",
            )
            session.attorneys[calling_side] = direct_agent
            session.attorney_team[direct_team_key] = direct_agent
        if not cross_agent:
            logger.warning(f"Creating fallback cross attorney for side={opposing_side}")
            cross_agent = create_attorney_agent(
                name=f"{opposing_label} Counsel",
                side=opposing_side,
                style=AttorneyStyle.METHODICAL,
                skill_level=SkillLevel.EXPERT,
                case_theory=f"Represent the {opposing_label} effectively.",
            )
            session.attorneys[opposing_side] = cross_agent
            session.attorney_team[cross_team_key] = cross_agent

    logger.info(
        f"Agents: direct_agent={'YES' if direct_agent else 'NONE'} ({direct_team_key}), "
        f"cross_agent={'YES' if cross_agent else 'NONE'} ({cross_team_key}), "
        f"attorney_team keys={list(session.attorney_team.keys())}, "
        f"attorneys keys={list(session.attorneys.keys())}"
    )

    graph_call_witness(state, witness_id, calling_side)
    if state.last_error:
        err = state.last_error
        state.last_error = None
        raise HTTPException(status_code=400, detail=err)

    if state.phase not in (TrialPhase.DIRECT, TrialPhase.CROSS, TrialPhase.REDIRECT, TrialPhase.RECROSS):
        state.phase = TrialPhase.DIRECT

    state.transcript.append({
        "speaker": "SYSTEM", "role": "system",
        "text": f"The Court calls {witness_name} to the stand.",
        "phase": state.phase.value, "event_type": "call_witness", "timestamp": None,
    })

    trial_memory = session.trial_memory

    # Ensure attorney performance trackers exist
    trial_memory._ensure_performance(f"{calling_side}_direct_cross", calling_side)
    trial_memory._ensure_performance(f"{opposing_side}_direct_cross", opposing_side)

    # Record the phase event
    trial_memory.record_phase_event(
        "witness_called", f"{witness_name} called by {calling_side}", state.phase.value
    )

    examination = {
        "witness_id": witness_id,
        "witness_name": witness_name,
        "calling_side": calling_side,
        "direct": [],
        "cross": [],
        "redirect": [],
        "recross": [],
        "human_cross": False,
    }

    witness_affidavit = witness_agent.persona.affidavit if witness_agent else ""
    if not witness_affidavit or len(witness_affidavit.strip()) < 50:
        case_witnesses = session.case_data.get("witnesses", []) if session.case_data else []
        for cw in case_witnesses:
            if cw.get("id") == witness_id or cw.get("name") == witness_name:
                witness_affidavit = cw.get("affidavit", "")
                if witness_affidavit:
                    break
        if not witness_affidavit or len(witness_affidavit.strip()) < 50:
            facts = session.case_data.get("facts", []) if session.case_data else []
            fact_lines = []
            for f in facts[:15]:
                fact_lines.append(f.get("content", str(f)) if isinstance(f, dict) else str(f))
            witness_affidavit = (
                f"Witness: {witness_name}\nCalled by: {calling_side}\n\n"
                f"Case facts this witness may know about:\n"
                + "\n".join(f"- {fl}" for fl in fact_lines)
            )
            logger.warning(f"No affidavit for {witness_name}, using case facts fallback")

    direct_testimony_log: list = []

    def _gen_qa(agent, exam_type, num_questions, side_label):
        """Generate Q&A pairs for an examination phase, with live objections."""
        nonlocal direct_testimony_log
        pairs = []
        prior = []
        action_type = "direct_question" if exam_type in ("direct", "redirect") else "cross_question"
        questioner_side = calling_side if exam_type in ("direct", "redirect") else opposing_side

        # Determine opposing attorney for objection checks
        if exam_type in ("direct", "redirect"):
            opposing_agent_for_objection = cross_agent
            objecting_side = opposing_side
        else:
            opposing_agent_for_objection = direct_agent
            objecting_side = calling_side

        for i in range(num_questions):
            try:
                if exam_type in ("direct", "redirect"):
                    question = agent.generate_direct_question(
                        state, witness_name, witness_affidavit, prior,
                        trial_memory=trial_memory,
                    )
                else:
                    question = agent.generate_cross_question(
                        state, witness_name, witness_affidavit,
                        direct_testimony_log, prior,
                        trial_memory=trial_memory,
                    )

                attorney_name = agent.persona.name

                # --- Opposing attorney considers objection ---
                objection_raised = False
                objection_sustained = False
                objection_type = None
                ruling_text = ""

                if opposing_agent_for_objection:
                    objection_type = opposing_agent_for_objection.should_object(
                        state, question, {
                            "recent_questions": [p["question"] for p in prior],
                            "witness_name": witness_name,
                            "examination_type": exam_type,
                        }
                    )
                    logger.info(
                        f"Objection check Q{i+1} ({exam_type}): "
                        f"objection_type={objection_type}, "
                        f"has_judges={bool(session.judges)}, "
                        f"attorney={opposing_agent_for_objection.persona.name}"
                    )
                    if objection_type and session.judges:
                        objection_raised = True
                        judge = session.judges[0]
                        objection_sustained, ruling_text = judge.rule_on_objection(
                            state=state,
                            objection_type=objection_type,
                            objecting_party=(
                                Role.ATTORNEY_PLAINTIFF if objecting_side == "plaintiff"
                                else Role.ATTORNEY_DEFENSE
                            ),
                            question_or_testimony=question,
                            context={
                                "examination_type": exam_type,
                                "witness_name": witness_name,
                            },
                            trial_memory=trial_memory,
                        )

                        # Record objection to transcript
                        objecting_label = "Prosecution" if objecting_side == "plaintiff" else "Defense"
                        state.transcript.append({
                            "speaker": f"{objecting_label} Attorney ({opposing_agent_for_objection.persona.name})",
                            "role": f"attorney_{objecting_side}",
                            "text": opposing_agent_for_objection.generate_objection(objection_type),
                            "phase": state.phase.value,
                            "event_type": "objection",
                            "timestamp": None,
                        })
                        state.transcript.append({
                            "speaker": f"Judge ({session.judges[0].persona.name})",
                            "role": "judge",
                            "text": ruling_text,
                            "phase": state.phase.value,
                            "event_type": "ruling",
                            "timestamp": None,
                        })

                        if objection_sustained:
                            pairs.append({
                                "objection": objection_type,
                                "sustained": True,
                                "ruling": ruling_text,
                                "attorney_name": opposing_agent_for_objection.persona.name,
                                "attorney_role": f"attorney_{objecting_side}",
                            })
                            continue

                # Append question to transcript
                state.transcript.append({
                    "speaker": f"{side_label} Attorney ({attorney_name})",
                    "role": f"attorney_{questioner_side}",
                    "text": question,
                    "phase": state.phase.value,
                    "event_type": action_type,
                    "timestamp": None,
                })

                answer = witness_agent.answer_question(
                    state, question, questioner_side, trial_memory=trial_memory,
                )
                state.transcript.append({
                    "speaker": witness_name,
                    "role": "witness",
                    "text": answer,
                    "phase": state.phase.value,
                    "event_type": "witness_answer",
                    "witness_id": witness_id,
                    "timestamp": None,
                })

                # Record to trial memory
                trial_memory.record_exam_event(
                    witness_id=witness_id,
                    witness_name=witness_name,
                    exam_type=exam_type,
                    questioner_side=questioner_side,
                    question=question,
                    answer=answer,
                    objection_raised=objection_raised,
                    objection_type=objection_type,
                    objection_sustained=objection_sustained,
                )

                # Run strategic analysis
                trial_memory.analyze_answer(
                    question=question,
                    answer=answer,
                    witness_id=witness_id,
                    witness_name=witness_name,
                    exam_type=exam_type,
                    questioner_side=questioner_side,
                )

                # Update team shared memory for both sides
                trial_memory.update_team_shared_from_testimony(
                    side=calling_side,
                    witness_name=witness_name,
                    witness_id=witness_id,
                    question=question,
                    answer=answer,
                    exam_type=exam_type,
                    questioner_side=questioner_side,
                )

                # Index testimony in Pinecone for vector retrieval (closings, cross)
                try:
                    from ..services.vector_retrieval import index_testimony as _index_testimony
                    _index_testimony(
                        witness_id=witness_id,
                        witness_name=witness_name,
                        question=question,
                        answer=answer,
                        phase=state.phase.value,
                        questioner_side=questioner_side,
                        case_id=session.case_id or "",
                    )
                except Exception:
                    pass

                qa_entry: dict = {
                    "question": question,
                    "answer": answer,
                    "attorney_name": attorney_name,
                    "attorney_role": f"attorney_{questioner_side}",
                }
                if objection_raised and not objection_sustained:
                    qa_entry["objection"] = objection_type
                    qa_entry["sustained"] = False
                    qa_entry["ruling"] = ruling_text
                pairs.append(qa_entry)
                prior.append({"question": question, "answer": answer})
                if exam_type in ("direct", "redirect"):
                    direct_testimony_log.append({"question": question, "answer": answer})
            except Exception as e:
                logger.warning(f"Q&A generation failed for {exam_type} Q{i+1}: {e}")
                continue

        return pairs

    # Run all sync LLM / vector-retrieval work in a thread so we don't block
    # the async event loop (which would freeze polling endpoints).
    is_spectator = session.human_role == Role.SPECTATOR
    human_sub_role = session.attorney_sub_role or "direct_cross"
    human_does_exam = human_sub_role == "direct_cross" and not is_spectator
    is_human_direct = (calling_side == human_side) and human_does_exam
    is_human_cross = (opposing_side == human_side) and human_does_exam

    def _run_examination_sync():
        # --- DIRECT EXAMINATION ---
        state.phase = TrialPhase.DIRECT
        if is_human_direct:
            examination["human_direct"] = True
        else:
            if direct_agent:
                examination["direct"] = _gen_qa(
                    direct_agent, "direct", request.num_direct_questions, calling_label
                )

        complete_examination(state, "direct")
        state.transcript.append({
            "speaker": "SYSTEM", "role": "system",
            "text": f"Direct examination of {witness_name} is complete. Cross-examination may begin.",
            "phase": "CROSS", "event_type": "exam_complete", "timestamp": None,
        })

        # --- CROSS EXAMINATION ---
        state.phase = TrialPhase.CROSS
        if is_human_cross:
            examination["human_cross"] = True
        else:
            if cross_agent:
                examination["cross"] = _gen_qa(
                    cross_agent, "cross", request.num_cross_questions, opposing_label
                )

        complete_examination(state, "cross")
        state.transcript.append({
            "speaker": "SYSTEM", "role": "system",
            "text": f"Cross-examination of {witness_name} is complete.",
            "phase": state.phase.value, "event_type": "exam_complete", "timestamp": None,
        })

        # --- REDIRECT (optional) ---
        if not request.skip_redirect and direct_agent:
            request_redirect(state)
            state.phase = TrialPhase.REDIRECT
            examination["redirect"] = _gen_qa(
                direct_agent, "redirect", request.num_redirect_questions, calling_label
            )
            complete_examination(state, "redirect")
            state.transcript.append({
                "speaker": "SYSTEM", "role": "system",
                "text": f"Redirect examination of {witness_name} is complete.",
                "phase": state.phase.value, "event_type": "exam_complete", "timestamp": None,
            })

            # --- RECROSS (optional, only if redirect happened) ---
            if not request.skip_recross and cross_agent:
                request_recross(state)
                state.phase = TrialPhase.RECROSS
                examination["recross"] = _gen_qa(
                    cross_agent, "recross", request.num_recross_questions, opposing_label
                )
                complete_examination(state, "recross")

    await asyncio.to_thread(_run_examination_sync)

    # Dismiss the witness
    dismiss_witness(state)
    state.phase = TrialPhase.DIRECT
    state.transcript.append({
        "speaker": "SYSTEM", "role": "system",
        "text": f"Examination of {witness_name} is complete. The witness is excused.",
        "phase": state.phase.value, "event_type": "witness_excused", "timestamp": None,
    })

    trial_memory.record_phase_event(
        "witness_excused", f"{witness_name} excused", state.phase.value
    )

    from ..config import ENABLE_STRATEGIC_ANALYSIS
    if ENABLE_STRATEGIC_ANALYSIS:
        try:
            from ..services.strategic_analyzer import analyze_examination_for_teams

            pt = ""
            dt = ""
            for sub in ("opening", "direct_cross", "closing"):
                pa = session.attorney_team.get(f"plaintiff_{sub}")
                if pa and pa.persona.case_theory:
                    pt = pa.persona.case_theory
                    break
            for sub in ("opening", "direct_cross", "closing"):
                da = session.attorney_team.get(f"defense_{sub}")
                if da and da.persona.case_theory:
                    dt = da.persona.case_theory
                    break

            asyncio.create_task(analyze_examination_for_teams(
                trial_memory=trial_memory,
                witness_id=witness_id,
                witness_name=witness_name,
                exam_type="full_witness",
                calling_side=calling_side,
                case_theory_plaintiff=pt,
                case_theory_defense=dt,
            ))
        except Exception as e:
            logger.warning(f"Failed to launch strategic analysis: {e}")

    # Count remaining witnesses for the current case-in-chief
    cic_witnesses = state.prosecution_witnesses if state.case_in_chief == "prosecution" else state.defense_witnesses
    remaining = [wid for wid in cic_witnesses if wid in state.witnesses_to_examine]

    # Trigger live scoring after each witness examination
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

    live_scores = None
    if session.judges:
        try:
            judge = session.judges[0]
            scores = {}
            opposing = "defense" if calling_side == "plaintiff" else "plaintiff"
            sides_to_score = [calling_side, opposing]
            for side in sides_to_score:
                role = Role.ATTORNEY_PLAINTIFF if side == "plaintiff" else Role.ATTORNEY_DEFENSE
                exam_entries = [
                    e for e in state.transcript
                    if e.get("role") == f"attorney_{side}"
                    and (e.get("event_type") or "").lower() in _EXAM_EVENTS
                ]
                if not exam_entries:
                    continue
                sr = "direct_cross"
                score_key = f"attorney_{side}_{sr}"
                from ..agents import get_categories_for_subrole
                cats = get_categories_for_subrole(sr)
                ballot = judge.score_participant(
                    participant_role=role,
                    participant_id=score_key,
                    transcript=exam_entries,
                    trial_memory=trial_memory,
                    categories=cats,
                )
                att_name = None
                for e in exam_entries:
                    sp = e.get("speaker", "")
                    if sp:
                        att_name = sp.split("(")[-1].rstrip(")") if "(" in sp and sp.endswith(")") else sp
                        break
                if not att_name:
                    agent = session.attorney_team.get(f"{side}_{sr}") or session.attorneys.get(side)
                    att_name = agent.persona.name if agent else ("Prosecution" if side == "plaintiff" else "Defense")
                cat_scores = {
                    cat.value: {"score": cs.score, "justification": cs.justification}
                    for cat, cs in ballot.scores.items()
                }
                scores[score_key] = {
                    "role": f"attorney_{side}",
                    "name": att_name,
                    "attorney_sub_role": _SUBROLE_LABELS.get(sr, "Attorney"),
                    "side": "Prosecution" if side == "plaintiff" else "Defense",
                    "average": round(ballot.average_score(), 1),
                    "total": ballot.total_score(),
                    "categories": cat_scores,
                    "comments": ballot.overall_comments,
                }

            # Score the witness that was just examined
            witness_entries = [e for e in state.transcript if e.get("witness_id") == witness_id]
            if witness_entries:
                from ..agents import get_categories_for_subrole as get_cats
                w_cats = get_cats("witness")
                ballot = judge.score_participant(
                    participant_role=Role.WITNESS,
                    participant_id=f"witness_{witness_id}",
                    transcript=state.transcript,
                    trial_memory=trial_memory,
                    categories=w_cats,
                )
                w_side = "Prosecution" if calling_side == "plaintiff" else "Defense"
                w_agent = session.witnesses.get(witness_id)
                w_role_label = getattr(w_agent.persona, "role_description", "Witness") if w_agent else "Witness"
                w_cat_scores = {
                    cat.value: {"score": cs.score, "justification": cs.justification}
                    for cat, cs in ballot.scores.items()
                }
                scores[f"witness_{witness_id}"] = {
                    "role": "witness",
                    "name": witness_name,
                    "witness_role": w_role_label,
                    "side": w_side,
                    "average": round(ballot.average_score(), 1),
                    "total": ballot.total_score(),
                    "categories": w_cat_scores,
                    "comments": ballot.overall_comments,
                }
            live_scores = scores
            existing = _scoring_live_scores.get(session_id, {})
            merged_scores = {**existing.get("scores", {}), **scores}
            merged_data = {
                "scores": merged_scores,
                "phase": state.phase.value,
                "transcript_length": len(state.transcript),
            }
            _scoring_live_scores[session_id] = merged_data
            _persist_live_scores(session_id, merged_data)
        except Exception as e:
            logger.warning(f"Live scoring after witness failed: {e}")

    _save_transcript_snapshot(session_id)

    return {
        "success": True,
        "examination": examination,
        "live_scores": live_scores,
        "witnesses_remaining": len(remaining),
        "total_witnesses_for_side": len(cic_witnesses),
        "witnesses_examined": len(state.witnesses_examined),
        "case_in_chief": state.case_in_chief,
    }


@router.get("/{session_id}/ai-team")
async def get_ai_team_info(session_id: str):
    """Get info about the AI team's attorneys for the current session."""
    session = get_session(session_id)
    
    if session.human_role == Role.ATTORNEY_PLAINTIFF:
        ai_side = "defense"
    else:
        ai_side = "plaintiff"
    
    team_info = []
    for key, agent in session.attorney_team.items():
        if key.startswith(ai_side):
            role = key.replace(f"{ai_side}_", "")
            team_info.append({
                "key": key,
                "name": agent.persona.name,
                "side": ai_side,
                "role": role,
                "style": agent.persona.style.value,
                "skill_level": agent.persona.skill_level.value,
            })
    
    return {
        "session_id": session_id,
        "ai_side": ai_side,
        "attorneys": team_info,
        "witness_count": len(session.witnesses),
    }


# =============================================================================
# AI TTS ENDPOINT
# =============================================================================

_ai_audio_cache: dict = {}
_tts_text_cache: dict = {}


class AITTSRequest(BaseModel):
    text: str = Field(..., max_length=10000)
    role: str = Field(..., max_length=50)
    speaker_name: Optional[str] = Field(None, max_length=200)


@router.post("/{session_id}/ai-tts")
async def generate_ai_tts(session_id: str, request: AITTSRequest):
    """Generate TTS audio for AI-generated text. Returns audio bytes directly."""
    from ..services.tts import get_voice_for_speaker, VoicePersona, guess_gender_from_name
    import hashlib

    # Text-based cache: reuse audio for identical text+role+speaker combos
    cache_key = hashlib.md5(
        f"{request.text}|{request.role}|{request.speaker_name or ''}".encode()
    ).hexdigest()
    if cache_key in _tts_text_cache:
        from fastapi.responses import StreamingResponse
        import io
        return StreamingResponse(
            io.BytesIO(_tts_text_cache[cache_key]),
            media_type="audio/mp3",
            headers={"Content-Disposition": 'inline; filename="ai_speech.mp3"'},
        )

    session = get_session(session_id)

    if not session.tts:
        raise HTTPException(status_code=400, detail="TTS service not available")

    try:
        role = Role(request.role)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")

    tts_session = session.tts.get_session(session_id)
    if not tts_session:
        tts_session = session.tts.create_session(session_id)

    voice = get_voice_for_speaker(
        request.speaker_name or "", role
    )
    speaker = request.speaker_name or "the speaker"
    gender = guess_gender_from_name(speaker)
    gender_desc = "young woman" if gender == "female" else "young man" if gender == "male" else "young person"

    if speaker.lower() == "court clerk":
        persona = VoicePersona(
            voice=voice,
            priority=80,
            instructions=(
                "You are a young woman acting as court clerk in a college mock trial. "
                "Speak with a clear, bright, feminine voice. Be formal but warm and youthful."
            ),
        )
    elif role == Role.JUDGE:
        persona = VoicePersona(
            voice=voice,
            priority=100,
            instructions=(
                f"You are a {gender_desc} acting as a judge in a college mock trial. "
                f"Speak with calm authority but sound youthful and approachable. "
                f"Clear and measured, not stiff."
            ),
        )
    elif role in (Role.ATTORNEY_PLAINTIFF, Role.ATTORNEY_DEFENSE):
        side_label = "prosecution" if role == Role.ATTORNEY_PLAINTIFF else "defense"
        persona = VoicePersona(
            voice=voice,
            priority=50,
            instructions=(
                f"You are {speaker}, a {gender_desc} and a passionate college student "
                f"attorney for the {side_label}. "
                f"Speak with a clear {'feminine' if gender == 'female' else 'masculine'} voice. "
                f"Show genuine emotion and conviction — you care about winning. "
                f"Vary your pace: slow down for emphasis, speed up for momentum. "
                f"Use natural pauses. Sound young, energetic, and confident — "
                f"like a brilliant college debater, not a monotone reader. "
                f"Show passion and intensity."
            ),
        )
    elif role == Role.WITNESS:
        persona = VoicePersona(
            voice=voice,
            priority=10,
            instructions=(
                f"You are {speaker}, a {gender_desc} testifying in a college mock trial. "
                f"Speak with a clear {'feminine' if gender == 'female' else 'masculine'} voice. "
                f"Sound natural and conversational, like recalling real events. "
                f"Show emotion — nervousness when pressed, confidence when sure."
            ),
        )
    else:
        persona = VoicePersona(voice=voice)

    tts_session.voice_personas[role] = persona
    logger.info(
        f"TTS REQUEST: speaker='{speaker}' gender={gender} role={role.value} "
        f"voice={voice.value} instructions='{persona.instructions[:60]}...'"
    )

    max_retries = 2
    segment = None
    for attempt in range(max_retries + 1):
        segment = await session.tts.generate_speech(session_id, request.text, role)
        if segment:
            break
        if attempt < max_retries:
            logger.warning(f"TTS attempt {attempt + 1} failed, retrying...")
            await asyncio.sleep(1)

    if not segment:
        raise HTTPException(status_code=500, detail="TTS generation failed after retries")

    _ai_audio_cache[segment.segment_id] = segment.audio_data
    _tts_text_cache[cache_key] = segment.audio_data

    # Persist to Supabase so recorded trials have audio available
    try:
        from ..main import _tts_cache_key, _upload_to_supabase
        supabase_key = _tts_cache_key(request.text, request.role, request.speaker_name or "")
        _upload_to_supabase(supabase_key, segment.audio_data)
    except Exception as e:
        logger.warning(f"Failed to persist TTS to Supabase: {e}")

    from fastapi.responses import StreamingResponse
    import io

    return StreamingResponse(
        io.BytesIO(segment.audio_data),
        media_type="audio/mp3",
        headers={"Content-Disposition": 'inline; filename="ai_speech.mp3"'},
    )


@router.get("/{session_id}/live-prep")
async def get_live_prep(session_id: str):
    """Get the live strategic prep updates for both teams.

    Returns accumulated strategic intelligence generated during the trial
    as each team analyzes opposing testimony in real-time.
    """
    session = get_session(session_id)
    trial_memory = session.trial_memory
    return trial_memory.get_live_prep_snapshot()


@router.get("/{session_id}/team-memory")
async def get_team_memory(session_id: str):
    """Get team shared memory for both sides.

    Returns the accumulated intra-team knowledge for prosecution and defense
    separately. Each side's memory is isolated — prosecution never sees
    defense strategy and vice versa.
    """
    session = get_session(session_id)
    tm = session.trial_memory
    result = {}
    for side_key, label in (("plaintiff", "Prosecution"), ("defense", "Defense")):
        shared = tm.team_shared.get(side_key)
        if not shared:
            result[side_key] = {"label": label, "case_theory": [], "facts": [], "weaknesses": [], "directives": [], "heard": [], "witness_notes": {}}
            continue
        result[side_key] = {
            "label": label,
            "case_theory": shared.case_theory_notes,
            "facts": shared.key_facts_established,
            "weaknesses": shared.opposing_weaknesses,
            "directives": shared.attorney_directives,
            "heard": shared.heard_in_court,
            "witness_notes": shared.witness_prep_notes,
        }
    return result


# =============================================================================
# TRANSCRIPT PERSISTENCE
# =============================================================================

def _save_transcript_snapshot(session_id: str, user_id: str = "default"):
    """Save current transcript to Supabase Storage (fire-and-forget)."""
    try:
        session = get_session(session_id)
        state = session.trial_state
        storage = get_transcript_storage()
        if not storage.is_available:
            return

        case_name = getattr(session, "case_name", None) or session_id
        case_id = getattr(session, "case_id", None) or "unknown"
        human_role = getattr(session, "human_role", None) or "spectator"

        phases = []
        if state.phase:
            phases.append(state.phase.value if hasattr(state.phase, "value") else str(state.phase))

        storage.save_transcript(
            session_id=session_id,
            user_id=user_id,
            case_id=str(case_id),
            case_name=case_name,
            human_role=str(human_role),
            transcript=list(state.transcript),
            phases_completed=phases,
        )
    except Exception as e:
        logger.debug(f"Transcript snapshot failed for {session_id}: {e}")


@router.post("/{session_id}/save-transcript")
async def save_transcript(session_id: str, user_id: str = Depends(get_current_user_id)):
    """Manually trigger transcript save to Supabase Storage."""
    session = get_session(session_id)
    _save_transcript_snapshot(session_id, user_id)
    return {"status": "saved", "entry_count": len(session.trial_state.transcript)}


@router.get("/transcripts/public")
async def list_public_transcripts():
    """List completed trial transcripts that have stored data for public viewing."""
    storage = get_transcript_storage()
    all_transcripts = storage.list_transcripts("default")
    completed = [
        t for t in all_transcripts
        if t.get("storage_path")
        and t.get("phases_completed")
        and t["phases_completed"][-1].lower() in ("scoring", "completed")
    ]
    from ..data import get_demo_case_by_id
    for t in completed:
        if not t.get("case_name") or t["case_name"] == t.get("session_id") or len(t["case_name"]) < 10:
            case_info = get_demo_case_by_id(t.get("case_id", ""))
            t["case_name"] = case_info.get("title", t.get("case_id", "Mock Trial")) if case_info else t.get("case_id", "Mock Trial Session")
        if t.get("human_role", "").startswith("Role."):
            t["human_role"] = t["human_role"].replace("Role.", "").lower()
    completed.sort(key=lambda x: x.get("entry_count", 0), reverse=True)
    return {"transcripts": completed[:1]}


@router.get("/transcripts/history")
async def list_transcript_history(user_id: str = Depends(get_current_user_id)):
    """List all saved trial transcripts for the current user."""
    storage = get_transcript_storage()
    transcripts = storage.list_transcripts(user_id)
    return {"transcripts": transcripts}


@router.get("/transcripts/{session_id}")
async def get_transcript_detail(session_id: str):
    """Get full transcript data from storage, with audio cache keys."""
    storage = get_transcript_storage()
    data = storage.get_transcript(session_id)
    if not data:
        raise HTTPException(status_code=404, detail="Transcript not found")

    # Compute audio cache keys for each transcript entry and check availability
    try:
        from ..main import _tts_cache_key, _list_existing_tts_keys
        existing_keys = _list_existing_tts_keys()
        audio_map = {}
        for i, entry in enumerate(data.get("transcript", [])):
            text = entry.get("text") or entry.get("content") or ""
            role = entry.get("role", "narrator")
            speaker = entry.get("speaker", "")
            if text.strip():
                key = _tts_cache_key(text, role, speaker)
                if key in existing_keys:
                    audio_map[str(i)] = key
        data["audio_keys"] = audio_map
    except Exception as e:
        logger.warning(f"Could not compute audio keys: {e}")
        data["audio_keys"] = {}

    return data


# =============================================================================
# EMAIL TRANSCRIPT & SCORES
# =============================================================================

class EmailReportRequest(BaseModel):
    recipients: List[str]
    include_transcript: bool = True
    include_scores: bool = True
    subject: Optional[str] = None
    sender_name: Optional[str] = None


def _build_transcript_html(session, scores: dict, include_transcript: bool, include_scores: bool) -> str:
    """Build a formatted HTML email body with transcript and scores."""
    case_name = getattr(session, "case_name", None) or "Mock Trial"
    state = session.trial_state

    lines = [
        "<html><body style='font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px; color: #333;'>",
        f"<h1 style='color: #1e293b; border-bottom: 3px solid #3b82f6; padding-bottom: 10px;'>{case_name}</h1>",
        f"<p style='color: #64748b;'>Phase: {state.phase.value} &nbsp;|&nbsp; Session: {getattr(session, 'session_id', 'N/A')}</p>",
    ]

    if include_scores and scores:
        lines.append("<h2 style='color: #1e293b; margin-top: 30px;'>Scores &amp; Performance</h2>")
        lines.append("<table style='width: 100%; border-collapse: collapse; margin-bottom: 20px;'>")
        lines.append(
            "<tr style='background: #1e293b; color: white;'>"
            "<th style='padding: 10px; text-align: left;'>Participant</th>"
            "<th style='padding: 10px; text-align: left;'>Role</th>"
            "<th style='padding: 10px; text-align: left;'>Side</th>"
            "<th style='padding: 10px; text-align: center;'>Score</th>"
            "</tr>"
        )
        for key, s in scores.items():
            bg = "#f8fafc" if "plaintiff" in key else "#fef2f2"
            name = s.get("name", key)
            role = s.get("attorney_sub_role") or s.get("witness_role") or s.get("role", "")
            side = s.get("side", "")
            avg = s.get("average", 0)
            score_color = "#059669" if avg >= 7 else "#d97706" if avg >= 5 else "#dc2626"
            lines.append(
                f"<tr style='background: {bg}; border-bottom: 1px solid #e2e8f0;'>"
                f"<td style='padding: 10px;'><strong>{name}</strong></td>"
                f"<td style='padding: 10px;'>{role}</td>"
                f"<td style='padding: 10px;'>{side}</td>"
                f"<td style='padding: 10px; text-align: center;'>"
                f"<span style='color: {score_color}; font-weight: bold; font-size: 18px;'>{avg}</span>/10</td>"
                f"</tr>"
            )

            cats = s.get("categories", {})
            if cats:
                lines.append(
                    f"<tr style='background: {bg};'><td colspan='4' style='padding: 5px 10px 15px 30px;'>"
                    "<table style='width: 100%; font-size: 13px;'>"
                )
                for cat, detail in cats.items():
                    c_score = detail.get("score", detail) if isinstance(detail, dict) else detail
                    c_just = detail.get("justification", "") if isinstance(detail, dict) else ""
                    cat_label = cat.replace("_", " ").title()
                    lines.append(
                        f"<tr><td style='padding: 3px 0; color: #64748b;'>{cat_label}</td>"
                        f"<td style='padding: 3px 0; width: 50px; text-align: right; font-weight: bold;'>{c_score}/10</td></tr>"
                    )
                    if c_just:
                        lines.append(
                            f"<tr><td colspan='2' style='padding: 0 0 6px 10px; color: #94a3b8; font-style: italic; font-size: 12px;'>{c_just}</td></tr>"
                        )
                lines.append("</table></td></tr>")

            comments = s.get("comments")
            if comments:
                lines.append(
                    f"<tr style='background: {bg};'><td colspan='4' style='padding: 5px 10px 15px 30px; color: #6b7280; font-style: italic; font-size: 13px;'>"
                    f"<strong>Judge:</strong> {comments}</td></tr>"
                )

        lines.append("</table>")

    if include_transcript and state.transcript:
        lines.append("<h2 style='color: #1e293b; margin-top: 30px;'>Trial Transcript</h2>")
        phase_labels = {
            "opening": "Opening Statements",
            "OPENING": "Opening Statements",
            "prosecution_case": "Prosecution Case-in-Chief",
            "defense_case": "Defense Case-in-Chief",
            "closing": "Closing Arguments",
            "CLOSING": "Closing Arguments",
        }
        current_phase = None
        for entry in state.transcript:
            entry_phase = entry.get("phase", "")
            if entry_phase and entry_phase != current_phase:
                current_phase = entry_phase
                label = phase_labels.get(entry_phase, entry_phase.replace("_", " ").title())
                lines.append(
                    f"<div style='margin: 20px 0 10px 0; padding: 8px 15px; background: #f1f5f9; "
                    f"border-left: 4px solid #3b82f6; font-weight: bold; color: #1e293b;'>{label}</div>"
                )

            speaker = entry.get("speaker", entry.get("role", "Unknown"))
            text = entry.get("text", "")
            role = entry.get("role", "")

            if "attorney_plaintiff" in role:
                badge_bg, badge_color = "#dbeafe", "#1d4ed8"
            elif "attorney_defense" in role:
                badge_bg, badge_color = "#fee2e2", "#dc2626"
            elif role == "witness":
                badge_bg, badge_color = "#fef3c7", "#92400e"
            elif role == "judge":
                badge_bg, badge_color = "#e0e7ff", "#4338ca"
            else:
                badge_bg, badge_color = "#f1f5f9", "#475569"

            lines.append(
                f"<div style='margin: 8px 0; padding: 10px 15px; border-radius: 8px; background: #fafafa; border: 1px solid #e2e8f0;'>"
                f"<span style='display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; "
                f"background: {badge_bg}; color: {badge_color}; margin-right: 8px;'>{speaker}</span>"
                f"<span style='color: #334155; line-height: 1.6;'>{text}</span>"
                f"</div>"
            )

    lines.append(
        "<hr style='margin-top: 40px; border: none; border-top: 1px solid #e2e8f0;'/>"
        "<p style='color: #94a3b8; font-size: 12px; text-align: center;'>Generated by Mock Trial AI</p>"
        "</body></html>"
    )
    return "\n".join(lines)


@router.post("/{session_id}/email-report")
async def email_report(session_id: str, request: EmailReportRequest):
    """Send trial transcript and/or scores via email."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_pass:
        raise HTTPException(
            status_code=400,
            detail="Email not configured. Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD in backend .env",
        )

    if not request.recipients:
        raise HTTPException(status_code=400, detail="At least one recipient email is required")

    session = get_session(session_id)

    scores = {}
    if request.include_scores:
        from .scoring import _live_scores, _load_live_scores_from_db
        cached = _live_scores.get(session_id)
        if not cached:
            cached = _load_live_scores_from_db(session_id)
        if cached:
            scores = cached.get("scores", {})

    case_name = getattr(session, "case_name", None) or "Mock Trial"
    subject = request.subject or f"Mock Trial Report: {case_name}"
    sender_name = request.sender_name or "Mock Trial AI"

    html_body = _build_transcript_html(session, scores, request.include_transcript, request.include_scores)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{sender_name} <{smtp_from}>"
    msg["To"] = ", ".join(request.recipients)
    msg.attach(MIMEText(html_body, "html"))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_host, smtp_port)
        else:
            server = smtplib.SMTP(smtp_host, smtp_port)
            server.starttls()
        server.login(smtp_user, smtp_pass)
        server.sendmail(smtp_from, request.recipients, msg.as_string())
        server.quit()
    except smtplib.SMTPAuthenticationError:
        raise HTTPException(status_code=401, detail="SMTP authentication failed. Check SMTP_USER and SMTP_PASSWORD.")
    except Exception as e:
        logger.error(f"Email send failed: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to send email: {str(e)}")

    return {"success": True, "recipients": request.recipients, "message": f"Report sent to {len(request.recipients)} recipient(s)"}
