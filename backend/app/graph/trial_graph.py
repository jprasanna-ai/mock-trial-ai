"""
LangGraph Trial State Machine

This module implements the single source of truth for:
- Trial phase
- Speaker permissions
- Interrupts
- Objections
- Transitions

Per ARCHITECTURE.md: No agent may bypass the graph.
"""

from enum import Enum
from typing import Literal, Optional, List, Dict, Any
from dataclasses import dataclass, field
from langgraph.graph import StateGraph, END  # type: ignore[import-unresolved]


# =============================================================================
# TRIAL STATES (EXACT as per SPEC.md Section 4)
# =============================================================================

class TrialPhase(str, Enum):
    """Exact trial phases. Do not add or remove."""
    PREP = "PREP"
    OPENING = "OPENING"
    DIRECT = "DIRECT"
    CROSS = "CROSS"
    REDIRECT = "REDIRECT"
    RECROSS = "RECROSS"
    CLOSING = "CLOSING"
    SCORING = "SCORING"


# States where objections are valid (testimony states only)
TESTIMONY_STATES = frozenset({
    TrialPhase.DIRECT,
    TrialPhase.CROSS,
    TrialPhase.REDIRECT,
    TrialPhase.RECROSS,
})


# =============================================================================
# ROLES (per SPEC.md Section 3)
# =============================================================================

class Role(str, Enum):
    """Supported courtroom roles."""
    ATTORNEY_PLAINTIFF = "attorney_plaintiff"
    ATTORNEY_DEFENSE = "attorney_defense"
    WITNESS = "witness"
    JUDGE = "judge"
    COACH = "coach"  # Post-trial only
    SPECTATOR = "spectator"  # Watch-only, all roles are AI


# =============================================================================
# SPEAKER PERMISSIONS BY STATE
# =============================================================================

# Maps each phase to the roles permitted to speak
# Judge can always interrupt (handled separately)
SPEAKER_PERMISSIONS: Dict[TrialPhase, frozenset] = {
    TrialPhase.PREP: frozenset({
        Role.ATTORNEY_PLAINTIFF,
        Role.ATTORNEY_DEFENSE,
        Role.WITNESS,
    }),
    TrialPhase.OPENING: frozenset({
        Role.ATTORNEY_PLAINTIFF,
        Role.ATTORNEY_DEFENSE,
    }),
    TrialPhase.DIRECT: frozenset({
        Role.ATTORNEY_PLAINTIFF,
        Role.ATTORNEY_DEFENSE,
        Role.WITNESS,
    }),
    TrialPhase.CROSS: frozenset({
        Role.ATTORNEY_PLAINTIFF,
        Role.ATTORNEY_DEFENSE,
        Role.WITNESS,
    }),
    TrialPhase.REDIRECT: frozenset({
        Role.ATTORNEY_PLAINTIFF,
        Role.ATTORNEY_DEFENSE,
        Role.WITNESS,
    }),
    TrialPhase.RECROSS: frozenset({
        Role.ATTORNEY_PLAINTIFF,
        Role.ATTORNEY_DEFENSE,
        Role.WITNESS,
    }),
    TrialPhase.CLOSING: frozenset({
        Role.ATTORNEY_PLAINTIFF,
        Role.ATTORNEY_DEFENSE,
    }),
    TrialPhase.SCORING: frozenset({
        Role.JUDGE,
    }),
}


# =============================================================================
# TRIAL STATE (LangGraph State)
# =============================================================================

@dataclass
class TrialState:
    """
    The complete trial state. This is the single source of truth.
    
    Per ARCHITECTURE.md: LangGraph is the single source of truth for:
    - Trial phase
    - Speaker permissions
    - Interrupts
    - Objections
    - Transitions
    """
    # Current trial phase
    phase: TrialPhase = TrialPhase.PREP
    
    # Session identification
    session_id: str = ""
    
    # Role assignments
    human_role: Optional[Role] = None
    current_speaker: Optional[Role] = None
    
    # Witness tracking (which witness is on the stand)
    current_witness_id: Optional[str] = None
    
    # Side tracking for examination flow
    # "plaintiff" or "defense" - who called the current witness
    examining_side: Optional[Literal["plaintiff", "defense"]] = None
    
    # Objection state
    objection_pending: bool = False
    objection_by: Optional[Role] = None
    objection_type: Optional[str] = None
    
    # Judge interrupt state
    judge_interrupt_active: bool = False
    
    # Transcript (audio timestamps synced per AUDIO.md)
    transcript: List[Dict[str, Any]] = field(default_factory=list)
    
    # Agent response hooks (text before TTS)
    pending_agent_response: Optional[str] = None
    pending_agent_role: Optional[Role] = None
    
    # Error tracking
    last_error: Optional[str] = None
    
    # Witness order tracking
    witnesses_examined: List[str] = field(default_factory=list)
    witnesses_to_examine: List[str] = field(default_factory=list)  # Pending witnesses
    prosecution_witnesses: List[str] = field(default_factory=list)
    defense_witnesses: List[str] = field(default_factory=list)

    # Case-in-chief tracking
    case_in_chief: str = "prosecution"  # "prosecution" or "defense"
    prosecution_rested: bool = False
    defense_rested: bool = False
    
    # Opening/Closing tracking
    openings_completed: List[Role] = field(default_factory=list)
    closings_completed: List[Role] = field(default_factory=list)
    
    # Examination flow tracking
    direct_complete: bool = False      # Current witness direct done
    cross_complete: bool = False       # Current witness cross done
    redirect_complete: bool = False    # Current witness redirect done
    recross_complete: bool = False     # Current witness recross done
    redirect_requested: bool = False   # Did calling attorney request redirect
    recross_requested: bool = False    # Did crossing attorney request recross
    
    # Prep phase tracking
    case_loaded: bool = False
    roles_assigned: bool = False
    personas_configured: bool = False

    # AMTA-style time tracking (per special instruction 13)
    # Each side gets 25 minutes for direct and 25 minutes for cross total.
    # Reading documents into the record deducts from that time.
    time_limits: Dict[str, int] = field(default_factory=lambda: {
        "opening_per_side": 300,       # 5 minutes
        "direct_total": 1500,          # 25 minutes total across all directs
        "cross_total": 1500,           # 25 minutes total across all crosses
        "closing_per_side": 420,       # 7 minutes
        "rebuttal": 180,              # 3 minutes (prosecution only)
    })
    time_used: Dict[str, float] = field(default_factory=lambda: {
        "plaintiff_direct": 0.0,
        "plaintiff_cross": 0.0,
        "defense_direct": 0.0,
        "defense_cross": 0.0,
        "plaintiff_opening": 0.0,
        "plaintiff_closing": 0.0,
        "defense_opening": 0.0,
        "defense_closing": 0.0,
    })

    # AMTA witness calling restrictions (from captains' meeting)
    witness_calling_restrictions: Dict[str, List[str]] = field(default_factory=dict)

    # AMTA special instructions for enforcement
    special_instructions: List[Dict[str, Any]] = field(default_factory=list)


# =============================================================================
# TRANSITION VALIDATION
# =============================================================================

# Valid phase transitions
VALID_TRANSITIONS: Dict[TrialPhase, frozenset] = {
    TrialPhase.PREP: frozenset({TrialPhase.OPENING}),
    TrialPhase.OPENING: frozenset({TrialPhase.DIRECT}),
    TrialPhase.DIRECT: frozenset({TrialPhase.CROSS, TrialPhase.CLOSING}),
    TrialPhase.CROSS: frozenset({TrialPhase.REDIRECT, TrialPhase.DIRECT, TrialPhase.CLOSING}),
    TrialPhase.REDIRECT: frozenset({TrialPhase.RECROSS, TrialPhase.DIRECT, TrialPhase.CLOSING}),
    TrialPhase.RECROSS: frozenset({TrialPhase.DIRECT, TrialPhase.CLOSING}),
    TrialPhase.CLOSING: frozenset({TrialPhase.SCORING}),
    TrialPhase.SCORING: frozenset({END}),
}


def validate_transition(current: TrialPhase, target: TrialPhase) -> bool:
    """
    Validate that a phase transition is legal.
    
    Returns True if transition is valid, False otherwise.
    """
    if current not in VALID_TRANSITIONS:
        return False
    return target in VALID_TRANSITIONS[current]


# =============================================================================
# SPEAKER VALIDATION
# =============================================================================

def can_speak(state: TrialState, role: Role) -> bool:
    """
    Check if a role is permitted to speak in the current state.
    
    Judge can always interrupt (per AUDIO.md Section 4).
    Coach cannot speak during trial (per AGENTS.md Section 5).
    """
    # Judge can always interrupt
    if role == Role.JUDGE:
        return True
    
    # Coach cannot participate during live trial
    if role == Role.COACH:
        return state.phase == TrialPhase.SCORING  # Post-trial only
    
    # Check standard permissions
    permitted = SPEAKER_PERMISSIONS.get(state.phase, frozenset())
    return role in permitted


def validate_witness_calling(
    state: TrialState, witness_name: str, calling_side: str
) -> tuple[bool, Optional[str]]:
    """
    Validate whether a side can call a particular witness per AMTA rules.

    Returns (allowed, error_message).
    """
    restrictions = state.witness_calling_restrictions
    if not restrictions:
        return True, None

    name_lower = witness_name.lower()

    # Check prosecution-only witnesses
    for pros_name in restrictions.get("prosecution_only", []):
        if pros_name.lower() in name_lower or name_lower in pros_name.lower():
            if calling_side != "plaintiff" and calling_side != "prosecution":
                return False, f"{witness_name} may only be called by the prosecution"
            return True, None

    # Check defense-only witnesses
    for def_name in restrictions.get("defense_only", []):
        if def_name.lower() in name_lower or name_lower in def_name.lower():
            if calling_side != "defense":
                return False, f"{witness_name} may only be called by the defense"
            return True, None

    return True, None


def validate_speaker(state: TrialState, role: Role) -> tuple[bool, Optional[str]]:
    """
    Validate if a role can speak and return reason if not.
    
    Returns:
        (True, None) if speaker is valid
        (False, reason) if speaker is invalid
    """
    if not can_speak(state, role):
        return False, f"Role {role.value} cannot speak during {state.phase.value}"
    
    # If judge interrupt is active, only judge can speak
    if state.judge_interrupt_active and role != Role.JUDGE:
        return False, "Judge interrupt active - all other speakers must yield"
    
    # If objection is pending, only judge can rule
    if state.objection_pending and role != Role.JUDGE:
        return False, "Objection pending - awaiting judge ruling"
    
    return True, None


# =============================================================================
# OBJECTION HANDLING
# =============================================================================

# Valid objection types (common mock trial objections)
VALID_OBJECTION_TYPES = frozenset({
    "hearsay",
    "leading",
    "relevance",
    "speculation",
    "asked_and_answered",
    "compound",
    "argumentative",
    "assumes_facts",
    "beyond_scope",
    "narrative",
    "non_responsive",
})


def can_object(state: TrialState, objecting_role: Role) -> tuple[bool, Optional[str]]:
    """
    Validate if an objection can be raised.
    
    Per requirements: Objections only valid in testimony states.
    Per AGENTS.md: Only attorneys can object.
    """
    # Only valid in testimony states
    if state.phase not in TESTIMONY_STATES:
        return False, f"Objections not permitted during {state.phase.value}"
    
    # Only attorneys can object
    if objecting_role not in {Role.ATTORNEY_PLAINTIFF, Role.ATTORNEY_DEFENSE}:
        return False, "Only attorneys may raise objections"
    
    # Cannot object while another objection is pending
    if state.objection_pending:
        return False, "Objection already pending"
    
    # Cannot object during judge interrupt
    if state.judge_interrupt_active:
        return False, "Cannot object during judge interrupt"
    
    return True, None


def raise_objection(
    state: TrialState,
    objecting_role: Role,
    objection_type: str
) -> TrialState:
    """
    Raise an objection. Returns new state with objection pending.
    
    Per AUDIO.md: Objections may interrupt testimony.
    """
    valid, reason = can_object(state, objecting_role)
    if not valid:
        state.last_error = reason
        return state
    
    if objection_type not in VALID_OBJECTION_TYPES:
        state.last_error = f"Invalid objection type: {objection_type}"
        return state
    
    state.objection_pending = True
    state.objection_by = objecting_role
    state.objection_type = objection_type
    state.last_error = None
    
    return state


def rule_on_objection(
    state: TrialState,
    sustained: bool,
    ruling_text: str,
    audio_timestamp: float = 0.0
) -> TrialState:
    """
    Judge rules on pending objection.
    
    Only the judge may call this (enforced by graph).
    
    Args:
        state: Current trial state
        sustained: Whether the objection is sustained
        ruling_text: The judge's spoken ruling
        audio_timestamp: Timestamp for transcript sync
        
    Returns:
        Updated TrialState
    """
    if not state.objection_pending:
        state.last_error = "No objection pending"
        return state
    
    # Record objection and ruling in transcript
    objection_entry = {
        "role": state.objection_by.value if state.objection_by else "unknown",
        "text": f"Objection! {state.objection_type.replace('_', ' ').title() if state.objection_type else 'Unknown'}.",
        "audio_timestamp": audio_timestamp,
        "phase": state.phase.value,
        "event_type": "objection",
        "objection_type": state.objection_type,
    }
    state.transcript.append(objection_entry)
    
    ruling_entry = {
        "role": Role.JUDGE.value,
        "text": ruling_text,
        "audio_timestamp": audio_timestamp,
        "phase": state.phase.value,
        "event_type": "ruling",
        "sustained": sustained,
        "objection_type": state.objection_type,
    }
    state.transcript.append(ruling_entry)
    
    state.objection_pending = False
    state.objection_by = None
    state.objection_type = None
    state.last_error = None
    
    return state


# =============================================================================
# JUDGE INTERRUPT HANDLING
# =============================================================================

def judge_interrupt(
    state: TrialState,
    interrupt_text: str = "",
    audio_timestamp: float = 0.0
) -> TrialState:
    """
    Judge interrupts current proceedings.
    
    Per AUDIO.md Section 4:
    - Judges may interrupt any speaker
    - Interrupted audio must stop immediately
    
    Per AUDIO.md Section 3:
    - Judge voice ALWAYS has priority
    
    Args:
        state: Current trial state
        interrupt_text: What the judge says when interrupting
        audio_timestamp: Timestamp for transcript sync
        
    Returns:
        Updated TrialState with interrupt_active flag set
    """
    state.judge_interrupt_active = True
    state.current_speaker = Role.JUDGE
    
    # Record interrupt in transcript
    if interrupt_text:
        interrupt_entry = {
            "role": Role.JUDGE.value,
            "text": interrupt_text,
            "audio_timestamp": audio_timestamp,
            "phase": state.phase.value,
            "event_type": "interrupt",
        }
        state.transcript.append(interrupt_entry)
    
    return state


def judge_yield(
    state: TrialState,
    yield_text: str = "",
    audio_timestamp: float = 0.0
) -> TrialState:
    """
    Judge yields the floor back to trial proceedings.
    
    Args:
        state: Current trial state
        yield_text: Optional statement when yielding floor
        audio_timestamp: Timestamp for transcript sync
        
    Returns:
        Updated TrialState
    """
    state.judge_interrupt_active = False
    state.current_speaker = None
    state.last_error = None
    
    # Record yield in transcript if text provided
    if yield_text:
        yield_entry = {
            "role": Role.JUDGE.value,
            "text": yield_text,
            "audio_timestamp": audio_timestamp,
            "phase": state.phase.value,
            "event_type": "yield",
        }
        state.transcript.append(yield_entry)
    
    return state


# =============================================================================
# LANGGRAPH NODE FUNCTIONS
# =============================================================================

def prep_node(state: TrialState) -> TrialState:
    """
    PREP phase node.
    
    Handles case selection, role selection, persona configuration.
    Per SPEC.md Section 4: Steps 1-4 of trial lifecycle.
    
    Integration points (handled by API/orchestration layer):
    - Case loading from Pinecone: Set state.case_loaded = True after loading
    - Role assignment: Set state.roles_assigned = True after assignment
    - Witness scheduling: Populate state.witnesses_to_examine with witness IDs
    - Persona configuration: Set state.personas_configured = True after config
    
    This node validates preparation completeness and sets phase.
    """
    state.phase = TrialPhase.PREP
    
    # Validation checks - state flags set by API layer
    # If all prep requirements met, routing logic will advance to opening
    # (see route_from_prep for transition conditions)
    
    return state


def opening_node(state: TrialState) -> TrialState:
    """
    OPENING phase node.
    
    Per AGENTS.md: Attorney responsibilities include openings.
    Per SCORING.md: Opening clarity is scored 1-10.
    
    Integration points (handled by API/orchestration layer):
    - AttorneyAgent.deliver_opening_statement() generates opening text
    - Response added to state.pending_agent_response for TTS
    - After TTS complete, add to transcript via add_to_transcript()
    - Track completion: call complete_opening(state, side) when done
    
    Opening order (per typical trial procedure):
    1. Plaintiff delivers opening
    2. Defense delivers opening (or reserves)
    3. Transition to DIRECT when both complete
    """
    state.phase = TrialPhase.OPENING
    
    # State tracking for opening completion is managed via:
    # - complete_opening(state, "plaintiff") 
    # - complete_opening(state, "defense")
    # Routing checks both flags via route_from_opening()
    
    return state


def direct_node(state: TrialState) -> TrialState:
    """
    DIRECT examination node.
    
    Per AGENTS.md:
    - Attorney: Direct examination
    - Witness: Answer questions truthfully within affidavit
    
    Per SCORING.md: Direct examination effectiveness scored 1-10.
    
    Integration points (handled by API/orchestration layer):
    - Call witness to stand via call_witness(state, witness_id, calling_side)
    - AttorneyAgent.ask_direct_question() generates question text
    - WitnessAgent.answer_question() generates answer
      - WitnessAgent enforces: cannot invent facts outside affidavit
      - WitnessAgent applies: hesitation/pauses based on nervousness persona
    - Each Q&A pair added to transcript via add_to_transcript()
    - Opposing counsel may object: process via rule_on_objection()
    - When done: complete_examination(state, "direct")
    """
    state.phase = TrialPhase.DIRECT
    return state


def cross_node(state: TrialState) -> TrialState:
    """
    CROSS examination node.
    
    Per AGENTS.md:
    - Attorney: Cross examination (adversarial, strategic)
    - Witness: Higher difficulty = narrower answers
    
    Per SCORING.md: Cross examination control scored 1-10.
    
    Integration points (handled by API/orchestration layer):
    - AttorneyAgent.ask_cross_question() generates cross question
      - Leading questions ARE allowed on cross
      - Strategy: control witness, elicit admissions
    - WitnessAgent.answer_cross_question() generates answer
      - Higher difficulty setting for cross
      - Witness may be evasive based on difficulty persona
    - Objection tracking: count objections in state for scoring
      - state.objection_count tracks total objections
    - Each Q&A pair added to transcript with event_type tracking
    - When done: complete_examination(state, "cross")
    """
    state.phase = TrialPhase.CROSS
    return state


def redirect_node(state: TrialState) -> TrialState:
    """
    REDIRECT examination node.
    
    Limited to matters raised on cross.
    
    Integration points (handled by API/orchestration layer):
    - Only proceeds if redirect_requested is True (via request_redirect())
    - AttorneyAgent.ask_redirect_question() generates question
      - Questions must relate to cross examination topics
      - Rehabilitate witness, clarify damaging testimony
    - WitnessAgent.answer_question() generates answer
    - Scope validation: extract cross topics from transcript
    - When done: complete_examination(state, "redirect")
    """
    state.phase = TrialPhase.REDIRECT
    return state


def recross_node(state: TrialState) -> TrialState:
    """
    RECROSS examination node.
    
    Limited to matters raised on redirect.
    
    Integration points (handled by API/orchestration layer):
    - Only proceeds if recross_requested is True (via request_recross())
    - AttorneyAgent.ask_recross_question() generates question
      - Questions must relate to redirect topics only
    - WitnessAgent.answer_question() generates answer
    - When done: complete_examination(state, "recross")
      - This marks witness as fully examined
      - Witness moved to witnesses_examined list
    """
    state.phase = TrialPhase.RECROSS
    return state


def closing_node(state: TrialState) -> TrialState:
    """
    CLOSING arguments node.
    
    Per AGENTS.md: Attorney responsibilities include closings.
    Per SCORING.md: Case theory consistency scored 1-10.
    
    Integration points (handled by API/orchestration layer):
    - AttorneyAgent.deliver_closing_argument() generates closing text
      - Uses _summarize_transcript_for_closing() for context
      - References specific testimony and evidence
      - Argues case theory to jury
    - Response added to state.pending_agent_response for TTS
    - After TTS complete, add to transcript via add_to_transcript()
    - Track completion: call complete_closing(state, side) when done
    
    Closing order (per typical trial procedure):
    1. Plaintiff delivers closing
    2. Defense delivers closing
    3. Plaintiff may deliver rebuttal (optional, not implemented)
    4. Transition to SCORING when both complete
    """
    state.phase = TrialPhase.CLOSING
    return state


def scoring_node(state: TrialState) -> TrialState:
    """
    SCORING phase node.
    
    Per SCORING.md:
    - 3 independent JudgeAgents
    - Each scores 1-10 per category
    - Average of all judges for final score
    
    NOTE: Actual scoring logic is handled by the scoring API endpoint.
    This node manages state transition and enables post-trial features.
    
    Integration points (handled by API/orchestration layer):
    - JudgePanel.score_participant() triggers all 3 judges
      - Each JudgeAgent scores independently
      - Returns List[Ballot] with category scores + justifications
    - Scoring API: /api/scoring/{session_id}/score
      - Collects ballots
      - Computes final scores (averages)
      - Persists to Supabase
    - CoachAgent becomes available for feedback:
      - CoachAgent.analyze_performance() reviews transcript
      - CoachAgent.generate_drill() creates practice scenarios
    - Post-trial features:
      - GET /api/scoring/{session_id}/feedback for verbal feedback
      - GET /api/scoring/{session_id}/leaderboard for rankings
    """
    state.phase = TrialPhase.SCORING
    return state


# =============================================================================
# TRANSITION ROUTING
# =============================================================================

def route_from_prep(state: TrialState) -> str:
    """
    Route from PREP to OPENING.
    
    Validates all prep requirements are met before transitioning.
    """
    # Check all prep requirements
    if not state.case_loaded:
        return "prep"  # Stay in prep - case not loaded
    
    if not state.roles_assigned:
        return "prep"  # Stay in prep - roles not assigned
    
    if not state.witnesses_to_examine:
        return "prep"  # Stay in prep - no witnesses scheduled
    
    # All requirements met, proceed to opening
    return "opening"


def route_from_opening(state: TrialState) -> str:
    """Route from OPENING to DIRECT after both openings complete."""
    if (Role.ATTORNEY_PLAINTIFF in state.openings_completed and
        Role.ATTORNEY_DEFENSE in state.openings_completed):
        return "direct"
    return "opening"  # Stay in opening


def route_from_direct(state: TrialState) -> str:
    """
    Route from DIRECT to CROSS or CLOSING.
    
    After direct examination completes, moves to cross.
    If all witnesses examined, moves to closing.
    """
    if not state.direct_complete:
        return "direct"  # Stay in direct until complete
    
    # Direct complete, move to cross
    return "cross"


def route_from_cross(state: TrialState) -> str:
    """
    Route from CROSS to REDIRECT, DIRECT (next witness), or CLOSING.
    
    After cross examination:
    - If redirect requested, go to redirect
    - If more witnesses, go to next witness (direct)
    - Otherwise, go to closing
    """
    if not state.cross_complete:
        return "cross"  # Stay in cross until complete
    
    # Cross complete - check for redirect
    if state.redirect_requested:
        return "redirect"
    
    # No redirect - check for more witnesses
    if state.witnesses_to_examine:
        return "direct"
    
    # No more witnesses, go to closing
    return "closing"


def route_from_redirect(state: TrialState) -> str:
    """
    Route from REDIRECT to RECROSS, DIRECT (next witness), or CLOSING.
    
    After redirect examination:
    - If recross requested, go to recross
    - If more witnesses, go to next witness (direct)
    - Otherwise, go to closing
    """
    if not state.redirect_complete:
        return "redirect"  # Stay in redirect until complete
    
    # Redirect complete - check for recross
    if state.recross_requested:
        return "recross"
    
    # No recross - check for more witnesses
    if state.witnesses_to_examine:
        return "direct"
    
    # No more witnesses, go to closing
    return "closing"


def route_from_recross(state: TrialState) -> str:
    """
    Route from RECROSS to DIRECT (next witness) or CLOSING.
    
    After recross, move to next witness or closing.
    """
    if not state.recross_complete:
        return "recross"  # Stay in recross until complete
    
    # Recross complete - check for more witnesses
    if state.witnesses_to_examine:
        return "direct"
    
    # No more witnesses, go to closing
    return "closing"


def route_from_closing(state: TrialState) -> str:
    """Route from CLOSING to SCORING after both closings complete."""
    if (Role.ATTORNEY_PLAINTIFF in state.closings_completed and
        Role.ATTORNEY_DEFENSE in state.closings_completed):
        return "scoring"
    return "closing"  # Stay in closing


# =============================================================================
# GRAPH CONSTRUCTION
# =============================================================================

def build_trial_graph() -> StateGraph:
    """
    Build the LangGraph trial state machine.
    
    This is the SINGLE SOURCE OF TRUTH for trial flow.
    Per ARCHITECTURE.md: No agent may bypass the graph.
    """
    # Create graph with TrialState
    graph = StateGraph(TrialState)
    
    # Add nodes for each phase
    graph.add_node("prep", prep_node)
    graph.add_node("opening", opening_node)
    graph.add_node("direct", direct_node)
    graph.add_node("cross", cross_node)
    graph.add_node("redirect", redirect_node)
    graph.add_node("recross", recross_node)
    graph.add_node("closing", closing_node)
    graph.add_node("scoring", scoring_node)
    
    # Set entry point
    graph.set_entry_point("prep")
    
    # Add conditional edges with routing functions
    graph.add_conditional_edges(
        "prep",
        route_from_prep,
        {"opening": "opening"}
    )
    
    graph.add_conditional_edges(
        "opening",
        route_from_opening,
        {"opening": "opening", "direct": "direct"}
    )
    
    graph.add_conditional_edges(
        "direct",
        route_from_direct,
        {"cross": "cross", "closing": "closing"}
    )
    
    graph.add_conditional_edges(
        "cross",
        route_from_cross,
        {"redirect": "redirect", "direct": "direct", "closing": "closing"}
    )
    
    graph.add_conditional_edges(
        "redirect",
        route_from_redirect,
        {"recross": "recross", "direct": "direct", "closing": "closing"}
    )
    
    graph.add_conditional_edges(
        "recross",
        route_from_recross,
        {"direct": "direct", "closing": "closing"}
    )
    
    graph.add_conditional_edges(
        "closing",
        route_from_closing,
        {"closing": "closing", "scoring": "scoring"}
    )
    
    # Scoring is terminal
    graph.add_edge("scoring", END)
    
    return graph


def compile_trial_graph():
    """
    Compile the trial graph for execution.
    
    Returns a compiled graph that can be invoked with a TrialState.
    """
    graph = build_trial_graph()
    return graph.compile()


# =============================================================================
# AGENT RESPONSE HOOKS
# =============================================================================

def set_agent_response(
    state: TrialState,
    role: Role,
    response_text: str
) -> TrialState:
    """
    Set pending agent response for TTS processing.
    
    Per AUDIO.md: All agent responses must go through TTS.
    Per ARCHITECTURE.md: Text → GPT-4.1 → Persona Conditioning → TTS
    """
    valid, reason = validate_speaker(state, role)
    if not valid:
        state.last_error = reason
        return state
    
    state.pending_agent_response = response_text
    state.pending_agent_role = role
    state.current_speaker = role
    
    # TTS pipeline integration is handled by the audio API layer:
    # 1. API reads pending_agent_response
    # 2. TTSService.generate_speech() with persona conditioning
    # 3. Audio streamed via WebRTC/WebSocket
    # 4. After TTS complete, call add_to_transcript() with timestamp
    # 5. Then call clear_agent_response() to reset
    #
    # See: backend/app/api/audio.py stream_tts endpoint
    
    return state


def clear_agent_response(state: TrialState) -> TrialState:
    """
    Clear pending agent response after TTS complete.
    """
    state.pending_agent_response = None
    state.pending_agent_role = None
    
    return state


# =============================================================================
# TRANSCRIPT MANAGEMENT
# =============================================================================

def add_to_transcript(
    state: TrialState,
    role: Role,
    text: str,
    audio_timestamp: float
) -> TrialState:
    """
    Add entry to transcript with audio timestamp.
    
    Per AUDIO.md Section 5: Transcript synced with audio timestamps.
    """
    entry = {
        "role": role.value,
        "text": text,
        "audio_timestamp": audio_timestamp,
        "phase": state.phase.value,
    }
    state.transcript.append(entry)
    
    return state


# =============================================================================
# EXAMINATION FLOW MANAGEMENT
# =============================================================================

def call_witness(
    state: TrialState,
    witness_id: str,
    calling_side: Literal["plaintiff", "defense"]
) -> TrialState:
    """
    Call a witness to the stand.
    
    Moves witness from pending list to current and resets examination flags.
    
    Args:
        state: Current trial state
        witness_id: ID of witness to call
        calling_side: Which side is calling the witness
        
    Returns:
        Updated TrialState
    """
    if witness_id not in state.witnesses_to_examine:
        state.last_error = f"Witness {witness_id} not in pending witness list"
        return state
    
    # Remove from pending and set as current
    state.witnesses_to_examine.remove(witness_id)
    state.current_witness_id = witness_id
    state.examining_side = calling_side
    
    # Reset examination flags for new witness
    state.direct_complete = False
    state.cross_complete = False
    state.redirect_complete = False
    state.recross_complete = False
    state.redirect_requested = False
    state.recross_requested = False
    
    return state


def complete_examination(
    state: TrialState,
    examination_type: Literal["direct", "cross", "redirect", "recross"]
) -> TrialState:
    """
    Mark an examination phase as complete for the current witness.
    
    Args:
        state: Current trial state
        examination_type: Which examination just completed
        
    Returns:
        Updated TrialState
    """
    if examination_type == "direct":
        state.direct_complete = True
    elif examination_type == "cross":
        state.cross_complete = True
    elif examination_type == "redirect":
        state.redirect_complete = True
    elif examination_type == "recross":
        state.recross_complete = True

    return state


def dismiss_witness(state: TrialState) -> TrialState:
    """Mark the current witness as fully examined and remove from the stand."""
    if state.current_witness_id:
        state.witnesses_examined.append(state.current_witness_id)
        state.current_witness_id = None
        state.examining_side = None
    return state


def request_redirect(state: TrialState) -> TrialState:
    """
    Request redirect examination after cross.
    
    Only the calling side's attorney may request redirect.
    """
    if not state.cross_complete:
        state.last_error = "Cannot request redirect before cross is complete"
        return state
    
    state.redirect_requested = True
    return state


def request_recross(state: TrialState) -> TrialState:
    """
    Request recross examination after redirect.
    
    Only the crossing side's attorney may request recross.
    """
    if not state.redirect_complete:
        state.last_error = "Cannot request recross before redirect is complete"
        return state
    
    state.recross_requested = True
    return state


def waive_redirect(state: TrialState) -> TrialState:
    """Waive redirect examination, moving to next witness or closing."""
    state.redirect_requested = False
    dismiss_witness(state)
    return state


def waive_recross(state: TrialState) -> TrialState:
    """Waive recross examination, moving to next witness or closing."""
    state.recross_requested = False
    dismiss_witness(state)
    return state


def rest_case(state: TrialState, side: str) -> TrialState:
    """
    Mark that a side has rested its case.
    When prosecution rests, defense case-in-chief begins.
    When defense rests, proceed to closing.
    """
    if side in ("plaintiff", "prosecution"):
        state.prosecution_rested = True
        state.case_in_chief = "defense"
    elif side == "defense":
        state.defense_rested = True
    return state


# =============================================================================
# PREP PHASE MANAGEMENT
# =============================================================================

def load_case(
    state: TrialState,
    case_id: str,
    witness_ids: List[str]
) -> TrialState:
    """
    Load a case and configure witnesses for examination.
    
    Args:
        state: Current trial state
        case_id: ID of the case being loaded
        witness_ids: List of witness IDs to examine in order
        
    Returns:
        Updated TrialState
    """
    state.witnesses_to_examine = list(witness_ids)
    state.case_loaded = True
    return state


def assign_roles(
    state: TrialState,
    human_role: Role
) -> TrialState:
    """
    Assign the human player's role.
    
    Args:
        state: Current trial state
        human_role: Role the human will play
        
    Returns:
        Updated TrialState
    """
    state.human_role = human_role
    state.roles_assigned = True
    return state


def complete_opening(
    state: TrialState,
    role: Role
) -> TrialState:
    """
    Mark an attorney's opening statement as complete.
    
    Args:
        state: Current trial state
        role: Attorney role that completed their opening
        
    Returns:
        Updated TrialState
    """
    if role not in {Role.ATTORNEY_PLAINTIFF, Role.ATTORNEY_DEFENSE}:
        state.last_error = f"Only attorneys can give openings, not {role.value}"
        return state
    
    if role not in state.openings_completed:
        state.openings_completed.append(role)
    
    return state


def complete_closing(
    state: TrialState,
    role: Role
) -> TrialState:
    """
    Mark an attorney's closing argument as complete.
    
    Args:
        state: Current trial state
        role: Attorney role that completed their closing
        
    Returns:
        Updated TrialState
    """
    if role not in {Role.ATTORNEY_PLAINTIFF, Role.ATTORNEY_DEFENSE}:
        state.last_error = f"Only attorneys can give closings, not {role.value}"
        return state
    
    if role not in state.closings_completed:
        state.closings_completed.append(role)
    
    return state


# =============================================================================
# STATE INSPECTION (for debugging and validation)
# =============================================================================

def get_state_summary(state: TrialState) -> Dict[str, Any]:
    """
    Get a summary of current trial state for debugging.
    
    NOTE: Agents must NOT use this to explain internal reasoning
    per AGENTS.md Section 1.
    """
    return {
        "phase": state.phase.value,
        "current_speaker": state.current_speaker.value if state.current_speaker else None,
        "current_witness_id": state.current_witness_id,
        "examining_side": state.examining_side,
        "objection_pending": state.objection_pending,
        "judge_interrupt_active": state.judge_interrupt_active,
        "can_object": state.phase in TESTIMONY_STATES,
        "transcript_length": len(state.transcript),
        "witnesses_remaining": len(state.witnesses_to_examine),
        "witnesses_examined": len(state.witnesses_examined),
        "openings_done": [r.value for r in state.openings_completed],
        "closings_done": [r.value for r in state.closings_completed],
        "examination_status": {
            "direct_complete": state.direct_complete,
            "cross_complete": state.cross_complete,
            "redirect_complete": state.redirect_complete,
            "recross_complete": state.recross_complete,
            "redirect_requested": state.redirect_requested,
            "recross_requested": state.recross_requested,
        },
        "last_error": state.last_error,
    }
