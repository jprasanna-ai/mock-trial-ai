"""
LangGraph Trial State Machine

Per ARCHITECTURE.md:
- LangGraph controls all trial flow
- Single source of truth for speaker permissions, objections, and transitions
"""

from .trial_graph import (
    # Enums
    TrialPhase,
    Role,
    # State
    TrialState,
    # Constants
    TESTIMONY_STATES,
    SPEAKER_PERMISSIONS,
    VALID_TRANSITIONS,
    VALID_OBJECTION_TYPES,
    # Validation functions
    validate_transition,
    can_speak,
    validate_speaker,
    validate_witness_calling,
    can_object,
    # Objection handling
    raise_objection,
    rule_on_objection,
    # Judge actions
    judge_interrupt,
    judge_yield,
    # Agent response hooks
    set_agent_response,
    clear_agent_response,
    add_to_transcript,
    # Examination flow management
    call_witness,
    complete_examination,
    request_redirect,
    request_recross,
    waive_redirect,
    waive_recross,
    # Prep phase management
    load_case,
    assign_roles,
    complete_opening,
    complete_closing,
    # State inspection
    get_state_summary,
    # Graph construction
    build_trial_graph,
    compile_trial_graph,
)

__all__ = [
    # Enums
    "TrialPhase",
    "Role",
    # State
    "TrialState",
    # Constants
    "TESTIMONY_STATES",
    "SPEAKER_PERMISSIONS",
    "VALID_TRANSITIONS",
    "VALID_OBJECTION_TYPES",
    # Validation functions
    "validate_transition",
    "can_speak",
    "validate_speaker",
    "validate_witness_calling",
    "can_object",
    # Objection handling
    "raise_objection",
    "rule_on_objection",
    # Judge actions
    "judge_interrupt",
    "judge_yield",
    # Agent response hooks
    "set_agent_response",
    "clear_agent_response",
    "add_to_transcript",
    # Examination flow management
    "call_witness",
    "complete_examination",
    "request_redirect",
    "request_recross",
    "waive_redirect",
    "waive_recross",
    # Prep phase management
    "load_case",
    "assign_roles",
    "complete_opening",
    "complete_closing",
    # State inspection
    "get_state_summary",
    # Graph construction
    "build_trial_graph",
    "compile_trial_graph",
]
