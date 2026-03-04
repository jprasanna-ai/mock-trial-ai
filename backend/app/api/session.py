"""
Session Management Endpoints

Per ARCHITECTURE.md:
- Backend responsibilities: Session lifecycle
- All trial logic flows through LangGraph

Endpoints:
- Create trial session
- Assign roles
- Load case
- Initialize agents

No trial logic - uses trial_graph.py for state enforcement.
"""

import logging
from typing import Optional, List, Dict, Any, Literal
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
import uuid

from ..graph.trial_graph import (
    TrialState,
    TrialPhase,
    Role,
)
from ..agents import (
    AttorneyAgent,
    AttorneyPersona,
    AttorneyStyle,
    SkillLevel,
    WitnessAgent,
    WitnessPersona,
    WitnessType,
    Demeanor,
    JudgeAgent,
    JudgePersona,
    JudicialTemperament,
    ScoringStyle,
    CoachAgent,
    CoachPersona,
    CoachingStyle,
    ExperienceLevel,
    create_attorney_agent,
    create_witness_agent,
    create_judge_agent,
    create_judge_panel,
    create_coach_agent,
)
from ..services import (
    WhisperService,
    TTSService,
    PineconeClient,
    create_whisper_service,
    create_tts_service,
    create_pinecone_client,
)
from ..db import SessionRepository, CaseRepository, get_supabase_client
from ..memory import TrialMemory


router = APIRouter()
logger = logging.getLogger(__name__)


# Fields that carry the full richness of a parsed case document
_CASE_DATA_FIELDS = [
    "case_id", "case_name", "description", "summary", "synopsis",
    "case_type", "charge", "charge_detail", "plaintiff", "defendant",
    "facts", "exhibits", "stipulations", "legal_standards", "witnesses",
    "special_instructions", "jury_instructions", "motions_in_limine",
    "indictment", "relevant_law", "witness_calling_restrictions",
    "available_witnesses",
]


def _build_full_case_data(source: Dict[str, Any]) -> Dict[str, Any]:
    """Build a complete case_data dict from any source (demo, uploaded, DB).

    Normalises key names so the rest of the codebase can rely on a
    stable schema regardless of where the case came from.
    """
    data: Dict[str, Any] = {}

    # Map source keys that may differ in name
    key_map = {
        "case_id": ["case_id", "id"],
        "case_name": ["case_name", "title", "name"],
    }

    for field in _CASE_DATA_FIELDS:
        candidates = key_map.get(field, [field])
        for key in candidates:
            if key in source and source[key]:
                data[field] = source[key]
                break
        if field not in data:
            if field in (
                "facts", "exhibits", "stipulations", "legal_standards",
                "witnesses", "special_instructions", "jury_instructions",
                "motions_in_limine", "available_witnesses",
            ):
                data[field] = []
            elif field in ("indictment", "relevant_law", "witness_calling_restrictions"):
                data[field] = {}
            else:
                data[field] = ""

    return data


# =============================================================================
# SESSION STORAGE
# =============================================================================

# In-memory cache for active sessions (agents, services are not DB-serializable)
# Supabase stores session metadata; this cache holds live runtime objects
_sessions: Dict[str, "SessionData"] = {}


class SessionData:
    """In-memory session data container."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.trial_state = TrialState(session_id=session_id)
        self.case_id: Optional[str] = None
        self.case_data: Dict[str, Any] = {}
        
        # Agents - keyed by side for primary, or by role key for full team
        self.attorneys: Dict[str, AttorneyAgent] = {}  # "plaintiff"/"defense" for primary
        self.attorney_team: Dict[str, AttorneyAgent] = {}  # "pros_opening", "def_closing", etc.
        self.witnesses: Dict[str, WitnessAgent] = {}
        self.judges: List[JudgeAgent] = []
        self.coach: Optional[CoachAgent] = None
        
        # 6-Layer Trial Memory (shared across all agents)
        self.trial_memory: TrialMemory = TrialMemory()

        # Preparation materials (cached LLM-generated content)
        self.prep_materials: Dict[str, Any] = {}
        self.prep_generation_status: Dict[str, str] = {}
        self.user_notes: Dict[str, str] = {}
        self.coach_history: List[Dict[str, str]] = []
        
        # Services
        self.whisper: Optional[WhisperService] = None
        self.tts: Optional[TTSService] = None
        self.pinecone: Optional[PineconeClient] = None
        
        # Configuration
        self.human_role: Optional[Role] = None
        self.attorney_sub_role: Optional[str] = None  # "opening", "direct_cross", "closing"
        self.initialized: bool = False


def get_session(session_id: str) -> SessionData:
    """Get session or raise 404."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return _sessions[session_id]


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class CreateSessionRequest(BaseModel):
    """Request to create a new session."""
    case_id: Optional[str] = None
    human_role: Optional[str] = None  # Can set role during creation
    attorney_sub_role: Optional[str] = None  # "opening", "direct_cross", or "closing"


class CreateSessionResponse(BaseModel):
    """Response with new session ID."""
    session_id: str
    phase: str
    message: str


class AssignRoleRequest(BaseModel):
    """Request to assign human role."""
    role: Literal[
        "attorney_plaintiff",
        "attorney_defense",
        "witness",
        "judge",
        "spectator"
    ]


class AssignRoleResponse(BaseModel):
    """Response confirming role assignment."""
    session_id: str
    human_role: str
    message: str


class LoadCaseRequest(BaseModel):
    """Request to load a case."""
    case_id: str


class LoadCaseResponse(BaseModel):
    """Response confirming case load."""
    session_id: str
    case_id: str
    case_name: str
    witness_count: int
    message: str


class WitnessConfig(BaseModel):
    """Configuration for a witness."""
    witness_id: str
    name: str
    affidavit: str
    called_by: Literal["plaintiff", "defense"]
    witness_type: str = "fact_witness"
    demeanor: str = "calm"
    nervousness: float = Field(0.3, ge=0.0, le=1.0)
    difficulty: float = Field(0.3, ge=0.0, le=1.0)


class AttorneyConfig(BaseModel):
    """Configuration for an attorney."""
    name: str
    side: Literal["plaintiff", "defense"]
    style: str = "methodical"
    skill_level: str = "expert"
    case_theory: str = ""


class JudgeConfig(BaseModel):
    """Configuration for a judge."""
    name: str
    temperament: str = "formal"
    scoring_style: str = "balanced"
    authority_level: float = Field(0.7, ge=0.0, le=1.0)


class CoachConfig(BaseModel):
    """Configuration for the coach."""
    name: str
    style: str = "direct"
    experience_level: str = "varsity"


class InitializeAgentsRequest(BaseModel):
    """Request to initialize all agents."""
    attorneys: List[AttorneyConfig]
    witnesses: List[WitnessConfig]
    judges: Optional[List[JudgeConfig]] = None  # Defaults to 3-judge panel
    coach: Optional[CoachConfig] = None


class InitializeAgentsResponse(BaseModel):
    """Response confirming agent initialization."""
    session_id: str
    attorneys_created: int
    witnesses_created: int
    judges_created: int
    coach_created: bool
    message: str


class SessionStatusResponse(BaseModel):
    """Current session status."""
    session_id: str
    phase: str
    human_role: Optional[str]
    attorney_sub_role: Optional[str] = None
    case_id: Optional[str]
    case_name: Optional[str] = None
    initialized: bool
    attorney_count: int
    witness_count: int
    judge_count: int


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.post("/create", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
):
    """
    Create a new trial session.
    
    Per SPEC.md Section 4: Trial lifecycle starts with case selection.
    """
    session_id = str(uuid.uuid4())
    
    # Create in-memory session for runtime objects (always works)
    session = SessionData(session_id)
    
    if request.case_id:
        session.case_id = request.case_id
    
    # Try to persist session to Supabase (optional - may not be configured)
    try:
        session_repo = SessionRepository()
        db_session = session_repo.create_session(
            session_id=session_id,
            case_id=request.case_id,
        )
        logger.info(f"Session {session_id} persisted to database")
    except Exception as e:
        logger.warning(f"Database not configured or failed: {e}. Using in-memory only.")
    
    # Initialize services (these are optional and may fail if not configured)
    try:
        session.whisper = create_whisper_service()
    except Exception as e:
        logger.warning(f"Whisper service not available: {e}")
    
    try:
        session.tts = create_tts_service()
    except Exception as e:
        logger.warning(f"TTS service not available: {e}")
    
    try:
        session.pinecone = create_pinecone_client()
    except Exception as e:
        logger.warning(f"Pinecone client not available: {e}")
    
    _sessions[session_id] = session
    
    # If human_role was provided, assign it
    if request.human_role:
        role_map = {
            "attorney_plaintiff": Role.ATTORNEY_PLAINTIFF,
            "attorney_defense": Role.ATTORNEY_DEFENSE,
            "witness": Role.WITNESS,
            "judge": Role.JUDGE,
            "spectator": Role.SPECTATOR,
        }
        role = role_map.get(request.human_role)
        if role:
            session.human_role = role
            session.trial_state.human_role = role
            session.trial_state.roles_assigned = True
            logger.info(f"Human role {request.human_role} assigned during session creation")
    
    # Store attorney sub-role if provided
    if request.attorney_sub_role and request.attorney_sub_role in ("opening", "direct_cross", "closing"):
        session.attorney_sub_role = request.attorney_sub_role
        logger.info(f"Attorney sub-role: {request.attorney_sub_role}")
    
    return CreateSessionResponse(
        session_id=session_id,
        phase=session.trial_state.phase.value,
        message="Session created. Assign roles and load case to continue."
    )


def _ensure_case_embeddings(case_id: str, case_data: dict):
    """Populate the case.py _cases cache and trigger background embedding if needed."""
    import threading
    try:
        from .case import _cases, _processing_status, ProcessingStatus, CaseData, process_case_embeddings

        if case_id in _cases and _cases[case_id].processed:
            logger.info(f"Case {case_id} already has embeddings — skipping")
            return

        if case_id not in _cases:
            case = CaseData(
                case_id=case_id,
                name=case_data.get("case_name", case_id),
                source_type="session",
            )
            case.facts = case_data.get("facts", [])
            case.witnesses = case_data.get("witnesses", [])
            case.exhibits = case_data.get("exhibits", [])
            case.stipulations = case_data.get("stipulations", [])
            case.legal_standards = case_data.get("legal_standards", [])
            case.fact_count = len(case.facts)
            case.witness_count = len(case.witnesses)
            case.exhibit_count = len(case.exhibits)
            _cases[case_id] = case

        if case_id not in _processing_status:
            _processing_status[case_id] = ProcessingStatus(case_id)

        import asyncio

        def _run_embeddings():
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(process_case_embeddings(case_id))
                loop.close()
                logger.info(f"Background embedding completed for case {case_id}")
            except Exception as e:
                logger.warning(f"Background embedding failed for case {case_id}: {e}")

        t = threading.Thread(target=_run_embeddings, daemon=True)
        t.start()
        logger.info(f"Started background embedding for case {case_id}")

    except Exception as e:
        logger.warning(f"Could not trigger embeddings for {case_id}: {e}")


def _load_and_inject_agent_prep(session: SessionData):
    """Bulk-load all agent prep for the case (single DB query + file cache) and inject."""
    if not session.case_id:
        return
    try:
        from .preparation import _load_all_agent_prep_for_case
    except ImportError:
        return

    case_id = session.case_id
    all_prep = _load_all_agent_prep_for_case(case_id)
    if not all_prep:
        logger.info(f"No cached prep found for case {case_id} — will generate")
        return

    injected = []

    for team_key, agent in session.attorney_team.items():
        prep = all_prep.get(team_key)
        if prep:
            agent.persona.prep_materials = prep
            injected.append(team_key)

    for side, agent in session.attorneys.items():
        key = f"{side}_direct_cross"
        prep = all_prep.get(key)
        if prep:
            agent.persona.prep_materials = prep
            if key not in injected:
                injected.append(key)

    for wid, agent in session.witnesses.items():
        prep = all_prep.get(f"witness_{wid}") or all_prep.get(wid)
        if prep:
            agent.persona.prep_materials = prep
            injected.append(f"witness_{wid}")

    judge_prep = all_prep.get("judge")
    if judge_prep:
        for judge in session.judges:
            judge.persona.prep_materials = judge_prep
        injected.append("judge")

    logger.info(f"Injected cached prep into {len(injected)} agents: {injected}")


async def _ensure_agent_prep_generated(session: "SessionData"):
    """Auto-generate agent prep for any agents that don't have prep materials yet.

    Checks DB first; only calls the LLM generators for agents whose prep
    is missing.  All missing preps are generated IN PARALLEL via asyncio.gather
    to avoid sequential waits.  Results are persisted to DB so future sessions
    skip generation entirely.
    """
    import asyncio

    if not session.case_id or not session.case_data:
        return
    try:
        from .preparation import (
            _get_cached_agent_prep,
            _save_agent_prep,
            _generate_attorney_opening_prep,
            _generate_attorney_direct_cross_prep,
            _generate_attorney_closing_prep,
            _generate_witness_prep,
            _generate_judge_prep,
        )
    except ImportError:
        return

    case_id = session.case_id
    case_data = session.case_data
    witnesses = case_data.get("witnesses", [])

    # Collect all prep tasks that need generation (not cached)
    tasks = []  # list of (key, role_type, coroutine)

    for side in ["plaintiff", "defense"]:
        for sub_role, gen_fn in [
            ("opening", _generate_attorney_opening_prep),
            ("direct_cross", _generate_attorney_direct_cross_prep),
            ("closing", _generate_attorney_closing_prep),
        ]:
            key = f"{side}_{sub_role}"
            if _get_cached_agent_prep(case_id, key):
                continue
            tasks.append((key, "attorney", gen_fn(case_data, side)))

    for w in witnesses[:10]:
        wid = w.get("id", "")
        if not wid:
            continue
        key = f"witness_{wid}"
        if _get_cached_agent_prep(case_id, key):
            continue
        tasks.append((key, "witness", _generate_witness_prep(case_data, w)))

    if not _get_cached_agent_prep(case_id, "judge"):
        tasks.append(("judge", "judge", _generate_judge_prep(case_data)))

    if not tasks:
        logger.info(f"All agent prep already cached for case {case_id} — 0 LLM calls needed")
        return

    logger.info(
        f"Generating prep for {len(tasks)} agents in parallel (LLM calls): "
        f"{[t[0] for t in tasks]}"
    )

    # Run ALL LLM calls concurrently
    results = await asyncio.gather(
        *(coro for _, _, coro in tasks),
        return_exceptions=True,
    )

    generated = []
    for (key, role_type, _), result in zip(tasks, results):
        if isinstance(result, Exception):
            logger.warning(f"Auto-prep failed for {key}: {result}")
            continue

        _save_agent_prep(case_id, key, role_type, result)
        generated.append(key)

        # Inject into the live agent
        if role_type == "attorney":
            agent = session.attorney_team.get(key) or session.attorneys.get(key.split("_")[0])
            if agent:
                agent.persona.prep_materials = result
        elif role_type == "witness":
            wid = key.replace("witness_", "", 1)
            agent = session.witnesses.get(wid)
            if agent:
                agent.persona.prep_materials = result
        elif role_type == "judge":
            for judge in session.judges:
                judge.persona.prep_materials = result

    if generated:
        logger.info(f"Auto-generated prep for {len(generated)} agents in parallel: {generated}")


@router.post("/{session_id}/initialize")
async def initialize_session(session_id: str):
    """
    Quick initialization endpoint that sets up default agents for a session.
    
    This is a convenience endpoint that loads the case (if set) and creates
    default AI agents so the session is ready to use immediately.
    """
    from ..data import get_demo_case_by_id
    from .case import _cases as uploaded_cases
    
    session = get_session(session_id)
    
    # Load case if specified (and not already loaded with full data)
    if session.case_id and not session.case_data.get("case_name"):
        case_source = None

        # Try demo cases first
        demo_case = get_demo_case_by_id(session.case_id)
        if demo_case:
            case_source = demo_case
            logger.info(f"Demo case {session.case_id} auto-loaded for session {session_id}")

        # Then try uploaded (in-memory) cases
        if not case_source and session.case_id in uploaded_cases:
            uc = uploaded_cases[session.case_id]
            case_source = {
                "case_id": uc.case_id, "case_name": uc.name,
                "description": getattr(uc, "synopsis", "") or "",
                "summary": getattr(uc, "synopsis", "") or "",
                "synopsis": getattr(uc, "synopsis", "") or "",
                "case_type": getattr(uc, "case_type", "unknown"),
                "charge": getattr(uc, "charge", ""),
                "charge_detail": getattr(uc, "charge", ""),
                "plaintiff": getattr(uc, "plaintiff", ""),
                "defendant": getattr(uc, "defendant", ""),
                "facts": uc.facts, "exhibits": uc.exhibits,
                "stipulations": uc.stipulations,
                "legal_standards": uc.legal_standards,
                "witnesses": uc.witnesses,
                "special_instructions": uc.special_instructions,
                "jury_instructions": uc.jury_instructions,
                "motions_in_limine": uc.motions_in_limine,
                "indictment": uc.indictment,
                "relevant_law": uc.relevant_law,
                "witness_calling_restrictions": uc.witness_calling_restrictions,
            }
            logger.info(f"Uploaded case {session.case_id} auto-loaded for session {session_id}")

        if case_source:
            session.case_data = _build_full_case_data(case_source)
            session.trial_state.case_loaded = True
            session.trial_state.witnesses_to_examine = [
                w["id"] for w in session.case_data.get("witnesses", []) if "id" in w
            ]
    
    # Load team personas (custom or defaults; derives witness list from case data)
    from .persona import get_team_config
    team = get_team_config(session_id, case_data=session.case_data)

    # Build case-specific theories from loaded case data
    def _build_case_theory(side: str) -> str:
        cd = session.case_data
        if not cd or not cd.get("case_name"):
            return "The evidence supports our position."
        
        case_name = cd.get("case_name", "")
        charge = cd.get("charge", "")
        summary = cd.get("summary", cd.get("description", ""))
        
        if side == "plaintiff":
            if charge:
                return (f"In {case_name}, the prosecution will prove beyond reasonable doubt "
                        f"that the defendant committed {charge}. {summary}")
            return (f"In {case_name}, the plaintiff will demonstrate by a preponderance of "
                    f"the evidence that the defendant is liable. {summary}")
        else:
            if charge:
                return (f"In {case_name}, the defense will show that the prosecution has failed "
                        f"to prove {charge} beyond a reasonable doubt. {summary}")
            return (f"In {case_name}, the defense will demonstrate that the plaintiff has not "
                    f"met their burden of proof. {summary}")

    is_spectator = session.human_role == Role.SPECTATOR

    # Determine opposing side based on human role
    if is_spectator:
        opposing_side = "defense"
        opposing_attorneys = team.get("defense_attorneys", [])
    elif session.human_role == Role.ATTORNEY_PLAINTIFF:
        opposing_side = "defense"
        opposing_attorneys = team.get("defense_attorneys", [])
    elif session.human_role == Role.ATTORNEY_DEFENSE:
        opposing_side = "plaintiff"
        opposing_attorneys = team.get("prosecution_attorneys", [])
    else:
        opposing_side = "defense"
        opposing_attorneys = team.get("defense_attorneys", [])

    # Create ALL 3 opposing attorneys (opening, direct/cross, closing)
    for att_config in opposing_attorneys:
        att_role = att_config.get("role", "direct_cross")
        agent = create_attorney_agent(
            name=att_config.get("name", "Opposing Counsel"),
            side=opposing_side,
            style=AttorneyStyle(att_config.get("style", "methodical")),
            skill_level=SkillLevel(att_config.get("skill_level", "expert")),
            case_theory=_build_case_theory(opposing_side),
            objection_frequency=att_config.get("objection_frequency", 0.3),
            risk_tolerance=att_config.get("risk_tolerance", 0.5),
            speaking_pace=att_config.get("speaking_pace", 1.0),
            formality=att_config.get("formality", 0.8),
            llm_model=att_config.get("llm_model"),
            llm_temperature=att_config.get("llm_temperature"),
            llm_max_tokens=att_config.get("llm_max_tokens"),
            custom_system_prompt=att_config.get("system_prompt"),
        )
        team_key = f"{opposing_side}_{att_role}"
        session.attorney_team[team_key] = agent

        if att_role == "direct_cross":
            session.attorneys[opposing_side] = agent

    if opposing_side not in session.attorneys and session.attorney_team:
        first_key = next(iter(session.attorney_team))
        session.attorneys[opposing_side] = session.attorney_team[first_key]

    # For spectator: create ALL prosecution attorneys too (since there's no human)
    # For attorney roles: create teammate attorneys (skipping human's sub-role)
    if is_spectator:
        human_side = "plaintiff"
        human_sub_role = None  # No role to skip
    else:
        human_side = "plaintiff" if session.human_role == Role.ATTORNEY_PLAINTIFF else "defense"
        human_sub_role = session.attorney_sub_role or "direct_cross"

    own_side_attorneys = team.get(
        "prosecution_attorneys" if human_side == "plaintiff" else "defense_attorneys", []
    )
    for att_config in own_side_attorneys:
        att_role = att_config.get("role", "direct_cross")
        if att_role == human_sub_role:
            continue
        agent = create_attorney_agent(
            name=att_config.get("name", "Teammate Counsel"),
            side=human_side,
            style=AttorneyStyle(att_config.get("style", "methodical")),
            skill_level=SkillLevel(att_config.get("skill_level", "expert")),
            case_theory=_build_case_theory(human_side),
            objection_frequency=att_config.get("objection_frequency", 0.3),
            risk_tolerance=att_config.get("risk_tolerance", 0.5),
            speaking_pace=att_config.get("speaking_pace", 1.0),
            formality=att_config.get("formality", 0.8),
            llm_model=att_config.get("llm_model"),
            llm_temperature=att_config.get("llm_temperature"),
            llm_max_tokens=att_config.get("llm_max_tokens"),
            custom_system_prompt=att_config.get("system_prompt"),
        )
        team_key = f"{human_side}_{att_role}"
        session.attorney_team[team_key] = agent
        logger.info(f"Created AI teammate attorney: {team_key} ({att_config.get('name')})")

        if att_role == "direct_cross":
            session.attorneys[human_side] = agent

    if human_side not in session.attorneys and session.attorney_team:
        own_keys = [k for k in session.attorney_team if k.startswith(human_side)]
        if own_keys:
            session.attorneys[human_side] = session.attorney_team[own_keys[0]]

    # Store full team config on session for trial phase transitions
    session.case_data["team_personas"] = team

    # Create witnesses from case data, applying persona configs and calling restrictions
    case_witnesses = session.case_data.get("witnesses", [])
    pros_witness_configs = team.get("prosecution_witnesses", [])
    def_witness_configs = team.get("defense_witnesses", [])
    restrictions = session.case_data.get("witness_calling_restrictions", {})

    def _resolve_called_by(name: str, fallback: str) -> str:
        """Use witness_calling_restrictions to resolve which side calls a witness."""
        if not restrictions:
            return fallback
        name_lower = name.lower()
        for pn in restrictions.get("prosecution_only", []):
            if pn.lower() in name_lower or name_lower in pn.lower():
                return "prosecution"
        for dn in restrictions.get("defense_only", []):
            if dn.lower() in name_lower or name_lower in dn.lower():
                return "defense"
        for en in restrictions.get("either_side", []):
            if en.lower() in name_lower or name_lower in en.lower():
                return "either"
        return fallback

    # Build a lookup of section texts for affidavit fallback
    sections = session.case_data.get("sections", {})
    _section_affidavit_texts = {}
    for sec_key in ("witnesses_plaintiff", "witnesses_defense", "witnesses_either"):
        sec_data = sections.get(sec_key)
        if sec_data:
            content = sec_data.get("content", "") if isinstance(sec_data, dict) else str(sec_data)
            if content:
                _section_affidavit_texts[sec_key] = content

    # Also pull case-level facts/summary for context injection when affidavit is missing
    _case_facts_summary = ""
    facts = session.case_data.get("facts", [])
    if facts:
        fact_lines = []
        for f in facts[:20]:
            if isinstance(f, dict):
                fact_lines.append(f.get("content", str(f)))
            else:
                fact_lines.append(str(f))
        _case_facts_summary = "\n".join(f"- {fl}" for fl in fact_lines)

    for i, witness_data in enumerate(case_witnesses):
        witness_id = witness_data.get("id", str(uuid.uuid4()))
        raw_called_by = witness_data.get("called_by", "unknown")
        called_by = _resolve_called_by(
            witness_data.get("name", ""),
            raw_called_by,
        )
        # Normalise to plaintiff/defense for agent creation.
        # "prosecution", "plaintiff", "either", "unknown" all default to plaintiff
        # to match _resolve_witness_side in persona.py.
        agent_side = "defense" if called_by == "defense" else "plaintiff"

        # Match persona config by index within side
        if agent_side == "plaintiff":
            side_witnesses = [w for w in case_witnesses[:i+1] if w.get("called_by") in ("plaintiff", "prosecution", "either")]
            idx = len(side_witnesses) - 1
            persona_cfg = pros_witness_configs[idx] if idx < len(pros_witness_configs) else {}
        else:
            side_witnesses = [w for w in case_witnesses[:i+1] if w.get("called_by") in ("defense",)]
            idx = len(side_witnesses) - 1
            persona_cfg = def_witness_configs[idx] if idx < len(def_witness_configs) else {}

        demeanor_str = persona_cfg.get("demeanor", "calm")
        demeanor_map = {"calm": Demeanor.CALM, "nervous": Demeanor.NERVOUS, "defensive": Demeanor.DEFENSIVE, "eager": Demeanor.EAGER, "hostile": Demeanor.HOSTILE}
        wtype_str = persona_cfg.get("witness_type", witness_data.get("document_type", "fact_witness"))
        wtype_map = {"fact_witness": WitnessType.FACT_WITNESS, "expert_witness": WitnessType.EXPERT_WITNESS, "character_witness": WitnessType.CHARACTER_WITNESS, "report": WitnessType.EXPERT_WITNESS, "affidavit": WitnessType.FACT_WITNESS}

        # Resolve the affidavit: use direct data first, then fall back to section text
        affidavit = witness_data.get("affidavit", "")
        witness_name = witness_data.get("name", "Unknown Witness")
        if not affidavit or len(affidavit.strip()) < 50:
            # Try to find this witness's affidavit in the uploaded sections
            sec_key_map = {"plaintiff": "witnesses_plaintiff", "prosecution": "witnesses_plaintiff",
                           "defense": "witnesses_defense", "either": "witnesses_either"}
            sec_key = sec_key_map.get(called_by, "witnesses_plaintiff")
            sec_text = _section_affidavit_texts.get(sec_key, "")
            if sec_text and witness_name != "Unknown Witness":
                # Search for this witness's name in the section text and extract their portion
                import re
                name_esc = re.escape(witness_name)
                pattern = re.compile(
                    rf'(?:AFFIDAVIT|STATEMENT|WITNESS).*?{name_esc}.*?\n(.*?)(?=(?:AFFIDAVIT|STATEMENT|WITNESS)\s+(?:OF|:)|\Z)',
                    re.IGNORECASE | re.DOTALL,
                )
                match = pattern.search(sec_text)
                if match:
                    affidavit = match.group(0).strip()
                    logger.info(f"Extracted affidavit for {witness_name} from section ({len(affidavit)} chars)")
            # If still no affidavit, use the full section text as context
            if (not affidavit or len(affidavit.strip()) < 50) and sec_text:
                affidavit = f"[Full witness section for reference]\n{sec_text}"
                logger.info(f"Using full section text as affidavit fallback for {witness_name}")
            # Last resort: inject case facts so witness has SOMETHING case-specific
            if not affidavit or len(affidavit.strip()) < 50:
                role_desc = witness_data.get("role_description", "")
                key_facts = witness_data.get("key_facts", [])
                kf_text = "\n".join(f"- {kf}" for kf in key_facts) if key_facts else ""
                affidavit = (
                    f"Witness: {witness_name}\n"
                    f"Called by: {called_by}\n"
                    f"Role: {role_desc}\n\n"
                    f"Key Facts Known:\n{kf_text}\n\n"
                    f"Case Facts:\n{_case_facts_summary}"
                )
                logger.warning(f"No affidavit for {witness_name}, using case facts as fallback")

        w_role_desc = (
            witness_data.get("role_description", "")
            or persona_cfg.get("role_description", "")
            or witness_data.get("document_type", "").replace("_", " ").title()
            or "Witness"
        )
        agent = create_witness_agent(
            name=witness_name,
            witness_id=witness_id,
            affidavit=affidavit,
            called_by=agent_side,
            witness_type=wtype_map.get(wtype_str, WitnessType.FACT_WITNESS),
            demeanor=demeanor_map.get(demeanor_str, Demeanor.CALM),
            nervousness=persona_cfg.get("nervousness", 0.3),
            difficulty=persona_cfg.get("difficulty", 0.5),
            role_description=w_role_desc,
            llm_model=persona_cfg.get("llm_model"),
            llm_temperature=persona_cfg.get("llm_temperature"),
            llm_max_tokens=persona_cfg.get("llm_max_tokens"),
            custom_system_prompt=persona_cfg.get("system_prompt"),
        )
        session.witnesses[witness_id] = agent

    # Create judges from team personas (2 judges instead of 3-panel)
    if not session.judges:
        judge_configs = team.get("judges", [])
        from ..agents.judge import JudicialTemperament, ScoringStyle, create_judge_agent as _create_judge
        judges = []
        temperament_map = {"stern": JudicialTemperament.STERN, "patient": JudicialTemperament.PATIENT, "formal": JudicialTemperament.FORMAL, "pragmatic": JudicialTemperament.PRAGMATIC}
        scoring_map = {"strict": ScoringStyle.STRICT, "balanced": ScoringStyle.BALANCED, "generous": ScoringStyle.GENEROUS}

        for j_idx, j_cfg in enumerate(judge_configs[:2]):
            judge = _create_judge(
                name=j_cfg.get("name", f"Judge {j_idx + 1}"),
                judge_id=j_cfg.get("id", f"judge_{j_idx + 1}"),
                temperament=temperament_map.get(j_cfg.get("temperament", "formal"), JudicialTemperament.FORMAL),
                scoring_style=scoring_map.get(j_cfg.get("scoring_style", "balanced"), ScoringStyle.BALANCED),
                authority_level=j_cfg.get("authority_level", 0.7),
                llm_model=j_cfg.get("llm_model"),
                llm_temperature=j_cfg.get("llm_temperature"),
                llm_max_tokens=j_cfg.get("llm_max_tokens"),
                custom_system_prompt=j_cfg.get("system_prompt"),
            )
            judges.append(judge)

        # Ensure we have at least 2 judges; pad with a third for the panel requirement
        while len(judges) < 3:
            judges.append(_create_judge(
                name=f"Judge {len(judges) + 1}",
                judge_id=f"judge_{len(judges) + 1}",
            ))
        session.judges = judges
    
    # Create default coach
    if not session.coach:
        session.coach = create_coach_agent(
            name="Coach Williams",
            style=CoachingStyle.DIRECT,
            experience_level=ExperienceLevel.VARSITY
        )
    
    # Load per-agent prep materials from DB and inject into agents.
    # If not yet generated, trigger generation so agents always have prep.
    _load_and_inject_agent_prep(session)
    await _ensure_agent_prep_generated(session)

    # Ensure case data is indexed in Pinecone for vector retrieval.
    # Runs in the background so it doesn't block initialization.
    if session.case_id and session.case_data:
        _ensure_case_embeddings(session.case_id, session.case_data)

    # Seed team shared memory with case theories from both sides
    for side in ("plaintiff", "defense"):
        for sub_role in ("opening", "direct_cross", "closing"):
            agent = session.attorney_team.get(f"{side}_{sub_role}")
            if agent and agent.persona.case_theory:
                session.trial_memory.record_team_directive(
                    side, f"Case theory: {agent.persona.case_theory}"
                )
                break  # One case theory per side is enough

    session.initialized = True
    
    return {
        "session_id": session_id,
        "initialized": True,
        "human_role": session.human_role.value if session.human_role else None,
        "attorney_sub_role": session.attorney_sub_role,
        "case_loaded": session.trial_state.case_loaded,
        "case_name": session.case_data.get("case_name", "None"),
        "attorneys_created": len(session.attorneys),
        "witnesses_created": len(session.witnesses),
        "judges_created": len(session.judges),
        "message": "Session initialized and ready"
    }


@router.post("/{session_id}/assign-role", response_model=AssignRoleResponse)
async def assign_role(
    session_id: str,
    request: AssignRoleRequest,
):
    """
    Assign human role for this session.
    
    Per SPEC.md Section 3: Only ONE role may be human-controlled per session.
    """
    session = get_session(session_id)
    
    # Map string to Role enum
    role_map = {
        "attorney_plaintiff": Role.ATTORNEY_PLAINTIFF,
        "attorney_defense": Role.ATTORNEY_DEFENSE,
        "witness": Role.WITNESS,
        "judge": Role.JUDGE,
        "spectator": Role.SPECTATOR,
    }
    
    role = role_map.get(request.role)
    if not role:
        raise HTTPException(status_code=400, detail=f"Invalid role: {request.role}")
    
    # Per SPEC.md: Only one human role per session
    session.human_role = role
    session.trial_state.human_role = role
    session.trial_state.roles_assigned = True
    
    # Try to persist to Supabase (optional)
    try:
        session_repo = SessionRepository()
        session_repo.update_session(
            session_id,
            human_role=role.value,
            phase=session.trial_state.phase.value,
        )
        # Add participant record for human
        session_repo.add_participant(
            session_id=session_id,
            role=role.value,
            is_human=True,
            name="Human Player",
        )
        logger.info(f"Role {role.value} assigned and persisted for session {session_id}")
    except Exception as e:
        logger.warning(f"Failed to persist role assignment: {e}")
    
    return AssignRoleResponse(
        session_id=session_id,
        human_role=role.value,
        message=f"Human role assigned: {role.value}"
    )


@router.post("/{session_id}/load-case", response_model=LoadCaseResponse)
async def load_case(
    session_id: str,
    request: LoadCaseRequest,
):
    """
    Load case materials for this session.
    
    Per SPEC.md Section 4: Case selection is step 1 of trial lifecycle.
    """
    from ..data import get_demo_case_by_id
    from .case import _cases as uploaded_cases
    
    session = get_session(session_id)
    case_loaded = False
    
    # First, try to load from demo cases
    demo_case = get_demo_case_by_id(request.case_id)
    if demo_case:
        session.case_id = demo_case["id"]
        session.case_data = _build_full_case_data(demo_case)
        session.trial_state.case_loaded = True
        session.trial_state.witnesses_to_examine = [
            w["id"] for w in session.case_data.get("witnesses", []) if "id" in w
        ]
        logger.info(f"Demo case {request.case_id} loaded for session {session_id}")
        case_loaded = True
    
    # Try uploaded (in-memory) cases
    if not case_loaded and request.case_id in uploaded_cases:
        uc = uploaded_cases[request.case_id]
        session.case_id = uc.case_id
        source = {
            "case_id": uc.case_id, "case_name": uc.name,
            "description": getattr(uc, "synopsis", "") or "",
            "summary": getattr(uc, "synopsis", "") or "",
            "synopsis": getattr(uc, "synopsis", "") or "",
            "case_type": getattr(uc, "case_type", "unknown"),
            "charge": getattr(uc, "charge", ""),
            "charge_detail": getattr(uc, "charge", ""),
            "plaintiff": getattr(uc, "plaintiff", ""),
            "defendant": getattr(uc, "defendant", ""),
            "facts": uc.facts, "exhibits": uc.exhibits,
            "stipulations": uc.stipulations,
            "legal_standards": uc.legal_standards,
            "witnesses": uc.witnesses,
            "special_instructions": uc.special_instructions,
            "jury_instructions": uc.jury_instructions,
            "motions_in_limine": uc.motions_in_limine,
            "indictment": uc.indictment,
            "relevant_law": uc.relevant_law,
            "witness_calling_restrictions": uc.witness_calling_restrictions,
        }
        session.case_data = _build_full_case_data(source)
        session.trial_state.case_loaded = True
        session.trial_state.witnesses_to_examine = [
            w["id"] for w in session.case_data.get("witnesses", []) if "id" in w
        ]
        logger.info(f"Uploaded case {request.case_id} loaded for session {session_id}")
        case_loaded = True
    
    # Try to load from database
    if not case_loaded:
        try:
            case_repo = CaseRepository()
            db_case = case_repo.get_case(request.case_id)
            
            if db_case:
                session.case_id = db_case.id
                db_source = {
                    "case_id": db_case.id,
                    "case_name": db_case.title,
                    "description": db_case.description,
                    "facts": db_case.facts or [],
                    "exhibits": db_case.exhibits or [],
                }
                
                witnesses = case_repo.get_witnesses(request.case_id)
                db_source["witnesses"] = [
                    {
                        "id": w.id,
                        "name": w.name,
                        "called_by": w.called_by,
                        "affidavit": w.affidavit,
                        "witness_type": w.witness_type,
                        "default_persona": w.default_persona,
                    }
                    for w in witnesses
                ]
                
                session.case_data = _build_full_case_data(db_source)
                session.trial_state.case_loaded = True
                session.trial_state.witnesses_to_examine = [w.id for w in witnesses]
                
                logger.info(f"Case {request.case_id} loaded from database for session {session_id}")
                case_loaded = True
        except Exception as e:
            logger.warning(f"Database not available: {e}")
    
    # Fallback: create placeholder case data
    if not case_loaded:
        session.case_id = request.case_id
        session.case_data = _build_full_case_data({
            "case_id": request.case_id,
            "case_name": f"Case {request.case_id}",
        })
        session.trial_state.case_loaded = True
        logger.warning(f"Case {request.case_id} not found, using placeholder")
    
    # Update session in Supabase (optional)
    try:
        session_repo = SessionRepository()
        session_repo.update_session(
            session_id,
            case_id=request.case_id,
        )
    except Exception as e:
        logger.warning(f"Failed to update session with case: {e}")
    
    return LoadCaseResponse(
        session_id=session_id,
        case_id=request.case_id,
        case_name=session.case_data.get("case_name", "Unknown"),
        witness_count=len(session.case_data.get("witnesses", [])),
        message="Case loaded. Initialize agents to continue."
    )


@router.post("/{session_id}/initialize-agents", response_model=InitializeAgentsResponse)
async def initialize_agents(
    session_id: str,
    request: InitializeAgentsRequest,
):
    """
    Initialize all AI agents for this session.
    
    Per SPEC.md Section 4: Persona configuration is step 3 of trial lifecycle.
    Per AGENTS.md: All agents must respect persona parameters.
    """
    session = get_session(session_id)
    
    # Validate we have required data
    if not session.case_id:
        raise HTTPException(
            status_code=400,
            detail="Load case before initializing agents"
        )
    
    # Initialize attorneys
    for config in request.attorneys:
        # Skip if this is the human role
        if session.human_role == Role.ATTORNEY_PLAINTIFF and config.side == "plaintiff":
            continue
        if session.human_role == Role.ATTORNEY_DEFENSE and config.side == "defense":
            continue
        
        style = AttorneyStyle(config.style) if config.style in [e.value for e in AttorneyStyle] else AttorneyStyle.METHODICAL
        skill = SkillLevel(config.skill_level) if config.skill_level in [e.value for e in SkillLevel] else SkillLevel.INTERMEDIATE
        
        agent = create_attorney_agent(
            name=config.name,
            side=config.side,
            style=style,
            skill_level=skill,
            case_theory=config.case_theory
        )
        
        session.attorneys[config.side] = agent
    
    # Initialize witnesses
    # Per SPEC.md Section 3: Only ONE role may be human-controlled per session
    # If human is playing a witness, the first witness is human-controlled
    human_witness_id = None
    if session.human_role == Role.WITNESS and request.witnesses:
        # First witness in list is human-controlled
        human_witness_id = request.witnesses[0].witness_id
        logger.info(f"Human controlling witness: {human_witness_id}")
    
    for config in request.witnesses:
        # Skip creating AI agent for human-controlled witness
        if config.witness_id == human_witness_id:
            continue
        
        witness_type = WitnessType(config.witness_type) if config.witness_type in [e.value for e in WitnessType] else WitnessType.FACT_WITNESS
        demeanor = Demeanor(config.demeanor) if config.demeanor in [e.value for e in Demeanor] else Demeanor.CALM
        
        agent = create_witness_agent(
            name=config.name,
            witness_id=config.witness_id,
            affidavit=config.affidavit,
            called_by=config.called_by,
            witness_type=witness_type,
            demeanor=demeanor,
            nervousness=config.nervousness,
            difficulty=config.difficulty
        )
        
        session.witnesses[config.witness_id] = agent
    
    # Initialize judges (panel of 3 per SCORING.md)
    if request.judges and len(request.judges) == 3:
        for i, config in enumerate(request.judges):
            temperament = JudicialTemperament(config.temperament) if config.temperament in [e.value for e in JudicialTemperament] else JudicialTemperament.FORMAL
            scoring_style = ScoringStyle(config.scoring_style) if config.scoring_style in [e.value for e in ScoringStyle] else ScoringStyle.BALANCED
            
            agent = create_judge_agent(
                name=config.name,
                judge_id=f"judge_{i+1}",
                temperament=temperament,
                scoring_style=scoring_style,
                authority_level=config.authority_level
            )
            
            session.judges.append(agent)
    else:
        # Create default 3-judge panel
        panel = create_judge_panel()
        session.judges = panel.judges
    
    # Initialize coach
    if request.coach:
        style = CoachingStyle(request.coach.style) if request.coach.style in [e.value for e in CoachingStyle] else CoachingStyle.DIRECT
        experience = ExperienceLevel(request.coach.experience_level) if request.coach.experience_level in [e.value for e in ExperienceLevel] else ExperienceLevel.VARSITY
        
        session.coach = create_coach_agent(
            name=request.coach.name,
            style=style,
            experience_level=experience
        )
    else:
        # Create default coach
        session.coach = create_coach_agent(name="Coach Morgan")
    
    # Configure TTS voices for agents
    if session.tts:
        tts_session = session.tts.create_session(session_id)
    
    session.initialized = True
    session.trial_state.personas_configured = True
    
    # Persist participants to Supabase
    try:
        # Persist attorneys
        for side, agent in session.attorneys.items():
            role = f"attorney_{side}"
            session_repo.add_participant(
                session_id=session_id,
                role=role,
                is_human=False,
                name=agent.persona.name,
                persona={
                    "style": agent.persona.style.value,
                    "skill_level": agent.persona.skill_level.value,
                    "case_theory": agent.persona.case_theory,
                }
            )
        
        # Persist witnesses
        for witness_id, agent in session.witnesses.items():
            session_repo.add_participant(
                session_id=session_id,
                role=f"witness_{witness_id}",
                is_human=False,
                name=agent.persona.name,
                persona={
                    "witness_type": agent.persona.witness_type.value,
                    "demeanor": agent.persona.demeanor.value,
                    "nervousness": agent.persona.nervousness,
                }
            )
        
        # Persist judges
        for judge in session.judges:
            session_repo.add_participant(
                session_id=session_id,
                role=f"judge_{judge.persona.judge_id}",
                is_human=False,
                name=judge.persona.name,
                persona={
                    "temperament": judge.persona.temperament.value,
                    "scoring_style": judge.persona.scoring_style.value,
                    "authority_level": judge.persona.authority_level,
                }
            )
        
        # Update session status
        session_repo.update_session(
            session_id,
            status="initialized",
            phase=session.trial_state.phase.value,
        )
        
        logger.info(f"All agents persisted for session {session_id}")
    except Exception as e:
        logger.warning(f"Failed to persist agents to database: {e}")
    
    return InitializeAgentsResponse(
        session_id=session_id,
        attorneys_created=len(session.attorneys),
        witnesses_created=len(session.witnesses),
        judges_created=len(session.judges),
        coach_created=session.coach is not None,
        message="Agents initialized. Ready to start trial."
    )


@router.get("/{session_id}/status", response_model=SessionStatusResponse)
async def get_session_status(session_id: str):
    """Get current session status."""
    session = get_session(session_id)
    
    return SessionStatusResponse(
        session_id=session_id,
        phase=session.trial_state.phase.value,
        human_role=session.human_role.value if session.human_role else None,
        attorney_sub_role=session.attorney_sub_role,
        case_id=session.case_id,
        case_name=session.case_data.get("case_name") if session.case_data else None,
        initialized=session.initialized,
        attorney_count=len(session.attorneys),
        witness_count=len(session.witnesses),
        judge_count=len(session.judges)
    )


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    """Delete a session."""
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = _sessions[session_id]
    
    # Cleanup services
    if session.whisper:
        session.whisper.end_session(session_id)
    if session.tts:
        session.tts.end_session(session_id)
    
    # Delete from Supabase (optional)
    try:
        session_repo = SessionRepository()
        session_repo.delete_session(session_id)
        logger.info(f"Session {session_id} deleted from database")
    except Exception as e:
        logger.warning(f"Failed to delete session from database: {e}")
    
    del _sessions[session_id]
    
    return {"message": "Session deleted", "session_id": session_id}


@router.get("/{session_id}/agents")
async def get_agents(session_id: str):
    """Get list of initialized agents."""
    session = get_session(session_id)
    
    return {
        "session_id": session_id,
        "attorneys": [
            {"side": side, "name": agent.persona.name}
            for side, agent in session.attorneys.items()
        ],
        "witnesses": [
            {"witness_id": wid, "name": agent.persona.name}
            for wid, agent in session.witnesses.items()
        ],
        "judges": [
            {"judge_id": agent.persona.judge_id, "name": agent.persona.name}
            for agent in session.judges
        ],
        "coach": {
            "name": session.coach.persona.name
        } if session.coach else None
    }


@router.get("/{session_id}/case-materials")
async def get_case_materials(session_id: str):
    """Get all case materials for preparation - facts, witnesses, exhibits."""
    session = get_session(session_id)
    
    if not session.case_id:
        raise HTTPException(status_code=400, detail="No case loaded for this session")
    
    case_data = session.case_data or {}
    
    # Format witnesses with useful info for display
    # Use the live session agents when available, so the displayed side
    # matches how they were actually assigned during initialization.
    witnesses = []
    for w in case_data.get("witnesses", []):
        wid = w.get("id")
        raw_cb = (w.get("called_by") or "unknown").lower()
        # If there's a live witness agent, use its called_by (already normalized)
        if wid and hasattr(session, "witnesses") and wid in session.witnesses:
            agent_cb = getattr(session.witnesses[wid].persona, "called_by", None)
            normalized_cb = agent_cb if agent_cb else ("plaintiff" if raw_cb in ("plaintiff", "prosecution", "either") else raw_cb)
        else:
            normalized_cb = "plaintiff" if raw_cb in ("plaintiff", "prosecution", "either") else raw_cb
        witnesses.append({
            "id": wid,
            "name": w.get("name"),
            "called_by": normalized_cb,
            "role_description": w.get("role_description", ""),
            "affidavit": w.get("affidavit", ""),
            "key_facts": w.get("key_facts", [])
        })
    
    # Format exhibits
    exhibits = []
    for e in case_data.get("exhibits", []):
        exhibits.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "description": e.get("description", ""),
            "content": e.get("content", ""),
            "exhibit_type": e.get("exhibit_type", "document")
        })
    
    # Format facts by category
    facts_by_type = {
        "background": [],
        "evidence": [],
        "stipulation": [],
        "legal_standard": []
    }
    for f in case_data.get("facts", []):
        fact_type = f.get("fact_type", "background")
        if fact_type in facts_by_type:
            facts_by_type[fact_type].append({
                "id": f.get("id"),
                "content": f.get("content"),
                "source": f.get("source", "")
            })
    
    return {
        "session_id": session_id,
        "case_id": session.case_id,
        "case_name": case_data.get("case_name", "Unknown Case"),
        "case_type": case_data.get("case_type", "civil"),
        "description": case_data.get("description", ""),
        "summary": case_data.get("summary", ""),
        "charge": case_data.get("charge", ""),
        "plaintiff": case_data.get("plaintiff", ""),
        "defendant": case_data.get("defendant", ""),
        "witnesses": witnesses,
        "exhibits": exhibits,
        "facts": facts_by_type,
        "stipulations": case_data.get("stipulations", []),
        "legal_standards": case_data.get("legal_standards", []),
        "special_instructions": case_data.get("special_instructions", []),
        "jury_instructions": case_data.get("jury_instructions", []),
        "motions_in_limine": case_data.get("motions_in_limine", []),
        "indictment": case_data.get("indictment", {}),
        "relevant_law": case_data.get("relevant_law", {}),
        "witness_calling_restrictions": case_data.get("witness_calling_restrictions", {}),
    }
