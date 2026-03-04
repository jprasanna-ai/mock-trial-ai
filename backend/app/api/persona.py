"""
Persona Management API

Full mock trial team persona customization:
- Prosecution Team: 3 Attorneys (Opening, Direct/Cross, Closing) + 3 Witnesses
- Defense Team: 3 Attorneys (Opening, Direct/Cross, Closing) + 3 Witnesses
- Judges: 2 (Presiding + Scoring)

Per SPEC.md: Persona parameters shape reasoning, speech style, voice output, and scoring bias.
"""

from typing import List, Dict, Any, Optional, Literal
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

# =============================================================================
# ATTORNEY ROLE ASSIGNMENTS
# =============================================================================

ATTORNEY_ROLES = {
    "opening": {
        "label": "Opening Attorney",
        "description": "Gives the opening statement. Tells the story of the case. Cannot argue - just outlines what evidence will show.",
        "responsibilities": ["opening_statement"],
    },
    "direct_cross": {
        "label": "Direct/Cross Attorney",
        "description": "Conducts direct examinations (own witnesses), cross-examinations (opposing witnesses), makes objections, argues evidentiary disputes.",
        "responsibilities": ["direct_examination", "cross_examination", "objections"],
    },
    "closing": {
        "label": "Closing Attorney",
        "description": "Argues the case. Connects evidence to legal standards. Persuades the judge why their side should win. The most dramatic role.",
        "responsibilities": ["closing_argument"],
    },
}

# =============================================================================
# DEFAULT TEAM PERSONAS
# =============================================================================

DEFAULT_PROSECUTION_ATTORNEYS = [
    {
        "id": "pros_opening",
        "role": "opening",
        "name": "Sarah Mitchell",
        "style": "charismatic",
        "skill_level": "expert",
        "description": "Compelling storyteller who frames the prosecution's narrative clearly and persuasively.",
        "objection_frequency": 0.2,
        "risk_tolerance": 0.4,
        "speaking_pace": 0.9,
        "formality": 0.8,
    },
    {
        "id": "pros_direct_cross",
        "role": "direct_cross",
        "name": "Marcus Webb",
        "style": "methodical",
        "skill_level": "expert",
        "description": "Precise questioner who builds testimony step by step. Strong on direct, relentless on cross.",
        "objection_frequency": 0.35,
        "risk_tolerance": 0.5,
        "speaking_pace": 1.0,
        "formality": 0.8,
    },
    {
        "id": "pros_closing",
        "role": "closing",
        "name": "Victoria Steele",
        "style": "aggressive",
        "skill_level": "expert",
        "description": "Powerful closer who connects every piece of evidence to the legal standard with conviction.",
        "objection_frequency": 0.3,
        "risk_tolerance": 0.7,
        "speaking_pace": 1.1,
        "formality": 0.7,
    },
]

DEFAULT_DEFENSE_ATTORNEYS = [
    {
        "id": "def_opening",
        "role": "opening",
        "name": "James Crawford",
        "style": "charismatic",
        "skill_level": "expert",
        "description": "Thoughtful advocate who humanizes the defendant and plants seeds of reasonable doubt.",
        "objection_frequency": 0.2,
        "risk_tolerance": 0.4,
        "speaking_pace": 0.9,
        "formality": 0.8,
    },
    {
        "id": "def_direct_cross",
        "role": "direct_cross",
        "name": "David Park",
        "style": "technical",
        "skill_level": "expert",
        "description": "Evidence-focused examiner who exploits every inconsistency. Devastating on cross-examination.",
        "objection_frequency": 0.4,
        "risk_tolerance": 0.3,
        "speaking_pace": 1.0,
        "formality": 0.9,
    },
    {
        "id": "def_closing",
        "role": "closing",
        "name": "Sophia Rivera",
        "style": "charismatic",
        "skill_level": "expert",
        "description": "Persuasive closer who weaves a compelling story of reasonable doubt.",
        "objection_frequency": 0.25,
        "risk_tolerance": 0.6,
        "speaking_pace": 1.0,
        "formality": 0.7,
    },
]

DEFAULT_PROSECUTION_WITNESSES = [
    {
        "id": "pros_witness_1",
        "name": "Witness 1 (Prosecution)",
        "witness_type": "fact_witness",
        "demeanor": "calm",
        "nervousness": 0.2,
        "difficulty": 0.3,
        "description": "Composed fact witness. Answers questions directly and clearly.",
    },
    {
        "id": "pros_witness_2",
        "name": "Witness 2 (Prosecution)",
        "witness_type": "expert_witness",
        "demeanor": "calm",
        "nervousness": 0.1,
        "difficulty": 0.4,
        "description": "Confident expert who speaks with authority on specialized topics.",
    },
    {
        "id": "pros_witness_3",
        "name": "Witness 3 (Prosecution)",
        "witness_type": "fact_witness",
        "demeanor": "nervous",
        "nervousness": 0.6,
        "difficulty": 0.2,
        "description": "Somewhat nervous eyewitness. May hesitate but wants to be helpful.",
    },
]

DEFAULT_DEFENSE_WITNESSES = [
    {
        "id": "def_witness_1",
        "name": "Witness 1 (Defense)",
        "witness_type": "fact_witness",
        "demeanor": "defensive",
        "nervousness": 0.4,
        "difficulty": 0.5,
        "description": "Guarded witness who gives careful, measured answers.",
    },
    {
        "id": "def_witness_2",
        "name": "Witness 2 (Defense)",
        "witness_type": "expert_witness",
        "demeanor": "calm",
        "nervousness": 0.1,
        "difficulty": 0.3,
        "description": "Confident expert witness for the defense. Clear and authoritative.",
    },
    {
        "id": "def_witness_3",
        "name": "Witness 3 (Defense)",
        "witness_type": "fact_witness",
        "demeanor": "eager",
        "nervousness": 0.3,
        "difficulty": 0.2,
        "description": "Eager to help. May over-explain but stays within their knowledge.",
    },
]

DEFAULT_JUDGES = [
    {
        "id": "judge_presiding",
        "role": "presiding",
        "name": "Judge Harrison",
        "temperament": "formal",
        "scoring_style": "balanced",
        "authority_level": 0.8,
        "description": "Presiding judge who enforces rules, administers oaths, rules on objections, and manages the courtroom.",
        "years_on_bench": 20,
    },
    {
        "id": "judge_scoring",
        "role": "scoring",
        "name": "Judge Chen",
        "temperament": "patient",
        "scoring_style": "balanced",
        "authority_level": 0.6,
        "description": "Scoring judge who observes the trial and provides detailed performance evaluations.",
        "years_on_bench": 12,
    },
]


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class AttorneyPersonaConfig(BaseModel):
    """Configuration for a single attorney persona."""
    name: str = Field(..., description="Attorney's name")
    role: Literal["opening", "direct_cross", "closing"] = "direct_cross"
    style: Literal["aggressive", "methodical", "charismatic", "technical"] = "methodical"
    skill_level: Literal["novice", "intermediate", "advanced", "expert"] = "expert"
    objection_frequency: float = Field(0.3, ge=0, le=1)
    risk_tolerance: float = Field(0.5, ge=0, le=1)
    speaking_pace: float = Field(1.0, ge=0.5, le=1.5)
    formality: float = Field(0.8, ge=0, le=1)
    description: str = ""
    # Per-agent LLM configuration
    llm_model: Optional[str] = Field(None, description="LLM model override for this agent")
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature override")
    llm_max_tokens: Optional[int] = Field(None, ge=50, le=8000, description="Max tokens override")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt for this agent")


class WitnessPersonaConfig(BaseModel):
    """Configuration for a single witness persona."""
    name: str = Field("", description="Witness name (overridden by case data)")
    witness_type: Literal["fact_witness", "expert_witness", "character_witness"] = "fact_witness"
    demeanor: Literal["calm", "nervous", "defensive", "eager", "hostile"] = "calm"
    nervousness: float = Field(0.3, ge=0, le=1)
    difficulty: float = Field(0.3, ge=0, le=1)
    verbosity: float = Field(0.5, ge=0, le=1)
    evasiveness: float = Field(0.2, ge=0, le=1)
    description: str = ""
    llm_model: Optional[str] = Field(None, description="LLM model override for this agent")
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature override")
    llm_max_tokens: Optional[int] = Field(None, ge=50, le=8000, description="Max tokens override")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt for this agent")


class JudgePersonaConfig(BaseModel):
    """Configuration for a single judge persona."""
    name: str = Field(..., description="Judge's name")
    role: Literal["presiding", "scoring"] = "presiding"
    temperament: Literal["stern", "patient", "formal", "pragmatic"] = "formal"
    scoring_style: Literal["strict", "balanced", "generous"] = "balanced"
    authority_level: float = Field(0.7, ge=0, le=1)
    years_on_bench: int = Field(15, ge=1, le=50)
    description: str = ""
    llm_model: Optional[str] = Field(None, description="LLM model override for this agent")
    llm_temperature: Optional[float] = Field(None, ge=0.0, le=2.0, description="Temperature override")
    llm_max_tokens: Optional[int] = Field(None, ge=50, le=8000, description="Max tokens override")
    system_prompt: Optional[str] = Field(None, description="Custom system prompt for this agent")


class TeamPersonaConfig(BaseModel):
    """Full team persona configuration for a session."""
    prosecution_attorneys: List[AttorneyPersonaConfig] = []
    defense_attorneys: List[AttorneyPersonaConfig] = []
    prosecution_witnesses: List[WitnessPersonaConfig] = []
    defense_witnesses: List[WitnessPersonaConfig] = []
    judges: List[JudgePersonaConfig] = []


# In-memory storage for session personas
_session_personas: Dict[str, TeamPersonaConfig] = {}


# =============================================================================
# HELPER - Get full team config (merged defaults + custom)
# =============================================================================

def _resolve_witness_side(name: str, called_by: str, restrictions: Dict[str, List[str]]) -> str:
    """Classify which side calls a witness.

    Uses the same logic as session.py's ``_resolve_called_by`` + agent_side
    normalisation so that the persona customiser always agrees with the
    case materials and courtroom views.
    """
    name_lower = name.lower()

    # 1. Check restrictions (prosecution_only / defense_only / either_side)
    for pn in restrictions.get("prosecution_only", []):
        if pn.lower() in name_lower or name_lower in pn.lower():
            return "prosecution"
    for dn in restrictions.get("defense_only", []):
        if dn.lower() in name_lower or name_lower in dn.lower():
            return "defense"
    for en in restrictions.get("either_side", []):
        if en.lower() in name_lower or name_lower in en.lower():
            return "prosecution"  # "either" → prosecution, same as session.py

    # 2. Fall back to the called_by field from case data
    cb = (called_by or "unknown").lower()
    if cb in ("plaintiff", "prosecution", "either"):
        return "prosecution"
    if cb == "defense":
        return "defense"

    # 3. Unknown → prosecution (matches session.py's default)
    return "prosecution"


def _build_witness_personas_from_case(case_data: Dict[str, Any]) -> tuple:
    """Build witness persona lists from loaded case data instead of hardcoded defaults.

    Side classification mirrors session.py's agent creation so that
    Case Materials, AI Persona, and the courtroom witness list always agree.
    """
    if not case_data:
        return DEFAULT_PROSECUTION_WITNESSES, DEFAULT_DEFENSE_WITNESSES

    case_witnesses = case_data.get("witnesses", [])
    if not case_witnesses:
        return DEFAULT_PROSECUTION_WITNESSES, DEFAULT_DEFENSE_WITNESSES

    restrictions = case_data.get("witness_calling_restrictions", {})

    pros_witnesses: List[Dict[str, Any]] = []
    def_witnesses: List[Dict[str, Any]] = []
    demeanors = ["calm", "nervous", "defensive", "eager", "calm"]

    for i, w in enumerate(case_witnesses):
        name = w.get("name", f"Witness {i+1}")
        called_by = w.get("called_by", "unknown")
        side = _resolve_witness_side(name, called_by, restrictions)

        doc_type = w.get("document_type", "affidavit")
        wtype = "expert_witness" if doc_type == "report" else "fact_witness"

        persona = {
            "id": w.get("id", f"{'pros' if side == 'prosecution' else 'def'}_witness_{i+1}"),
            "name": name,
            "witness_type": wtype,
            "demeanor": demeanors[i % len(demeanors)],
            "nervousness": round(0.2 + (i % 4) * 0.15, 2),
            "difficulty": round(0.3 + (i % 3) * 0.15, 2),
            "description": w.get("role_description") or w.get("role", ""),
        }

        if side == "prosecution":
            pros_witnesses.append(persona)
        else:
            def_witnesses.append(persona)

    return (
        pros_witnesses if pros_witnesses else DEFAULT_PROSECUTION_WITNESSES,
        def_witnesses if def_witnesses else DEFAULT_DEFENSE_WITNESSES,
    )


def get_team_config(session_id: str, case_data: Dict[str, Any] = None) -> Dict[str, Any]:
    """Get the complete team configuration, merging custom with defaults.

    When case_data is provided, witness defaults are built from actual case
    witnesses instead of generic placeholders.
    """
    custom = _session_personas.get(session_id)

    pros_w_default, def_w_default = _build_witness_personas_from_case(case_data)

    if not custom:
        return {
            "prosecution_attorneys": DEFAULT_PROSECUTION_ATTORNEYS,
            "defense_attorneys": DEFAULT_DEFENSE_ATTORNEYS,
            "prosecution_witnesses": pros_w_default,
            "defense_witnesses": def_w_default,
            "judges": DEFAULT_JUDGES,
            "using_defaults": True,
        }

    return {
        "prosecution_attorneys": (
            [a.model_dump() for a in custom.prosecution_attorneys]
            if custom.prosecution_attorneys else DEFAULT_PROSECUTION_ATTORNEYS
        ),
        "defense_attorneys": (
            [a.model_dump() for a in custom.defense_attorneys]
            if custom.defense_attorneys else DEFAULT_DEFENSE_ATTORNEYS
        ),
        "prosecution_witnesses": (
            [w.model_dump() for w in custom.prosecution_witnesses]
            if custom.prosecution_witnesses else pros_w_default
        ),
        "defense_witnesses": (
            [w.model_dump() for w in custom.defense_witnesses]
            if custom.defense_witnesses else def_w_default
        ),
        "judges": (
            [j.model_dump() for j in custom.judges]
            if custom.judges else DEFAULT_JUDGES
        ),
        "using_defaults": False,
    }


# =============================================================================
# ENDPOINTS
# =============================================================================

# --- Presets (unchanged IDs for backwards compat) ---

@router.get("/presets/judge")
async def get_judge_presets() -> List[Dict[str, Any]]:
    """Get available judge persona presets."""
    return DEFAULT_JUDGES


@router.get("/presets/attorney")
async def get_attorney_presets() -> List[Dict[str, Any]]:
    """Get available attorney persona presets (prosecution defaults)."""
    return DEFAULT_PROSECUTION_ATTORNEYS + DEFAULT_DEFENSE_ATTORNEYS


@router.get("/presets/witness")
async def get_witness_presets() -> List[Dict[str, Any]]:
    """Get available witness persona presets."""
    return DEFAULT_PROSECUTION_WITNESSES + DEFAULT_DEFENSE_WITNESSES


@router.get("/defaults")
async def get_default_team() -> Dict[str, Any]:
    """Get the full default team configuration."""
    return {
        "prosecution_attorneys": DEFAULT_PROSECUTION_ATTORNEYS,
        "defense_attorneys": DEFAULT_DEFENSE_ATTORNEYS,
        "prosecution_witnesses": DEFAULT_PROSECUTION_WITNESSES,
        "defense_witnesses": DEFAULT_DEFENSE_WITNESSES,
        "judges": DEFAULT_JUDGES,
        "attorney_roles": ATTORNEY_ROLES,
    }


# --- Session team config ---

def _session_case_data(session_id: str) -> Optional[Dict[str, Any]]:
    """Safely retrieve case_data from an active session, or None."""
    try:
        from .session import _sessions
        s = _sessions.get(session_id)
        return s.case_data if s else None
    except Exception:
        return None


@router.get("/{session_id}")
async def get_session_personas(session_id: str) -> Dict[str, Any]:
    """Get the full team configuration for a session (custom + defaults)."""
    config = get_team_config(session_id, case_data=_session_case_data(session_id))
    config["session_id"] = session_id
    config["attorney_roles"] = ATTORNEY_ROLES
    from ..services.llm_providers import AVAILABLE_MODELS
    config["available_models"] = AVAILABLE_MODELS
    return config


@router.put("/{session_id}/team")
async def set_team_personas(session_id: str, config: TeamPersonaConfig) -> Dict[str, Any]:
    """Set the entire team persona configuration for a session."""
    _session_personas[session_id] = config
    result = get_team_config(session_id, case_data=_session_case_data(session_id))
    result["session_id"] = session_id
    result["message"] = "Team personas updated"
    return result


# --- Live agent hot-patching ---

def _hot_patch_attorney(session_id: str, side: str, role: str, config: AttorneyPersonaConfig):
    """Apply persona changes to an already-running attorney agent."""
    try:
        from .session import _sessions
        session = _sessions.get(session_id)
        if not session:
            return
        norm_side = "plaintiff" if side == "prosecution" else side
        team_key = f"{norm_side}_{role}"
        agent = session.attorney_team.get(team_key)
        if not agent:
            return
        p = agent.persona
        p.llm_model = config.llm_model
        p.llm_temperature = config.llm_temperature
        p.llm_max_tokens = config.llm_max_tokens
        p.custom_system_prompt = config.system_prompt
        p.objection_frequency = config.objection_frequency
        p.risk_tolerance = config.risk_tolerance
        p.speaking_pace = config.speaking_pace
        p.formality = config.formality
        logger.info(f"Hot-patched attorney {team_key} (model={config.llm_model})")
    except Exception as e:
        logger.warning(f"Could not hot-patch attorney: {e}")


def _hot_patch_witness(session_id: str, name: str, config: WitnessPersonaConfig):
    """Apply persona changes to an already-running witness agent."""
    try:
        from .session import _sessions
        session = _sessions.get(session_id)
        if not session:
            return
        for wid, agent in session.witnesses.items():
            if agent.persona.name.lower() == name.lower():
                p = agent.persona
                p.llm_model = config.llm_model
                p.llm_temperature = config.llm_temperature
                p.llm_max_tokens = config.llm_max_tokens
                p.custom_system_prompt = config.system_prompt
                p.nervousness = config.nervousness
                p.difficulty = config.difficulty
                logger.info(f"Hot-patched witness {wid} (model={config.llm_model})")
                return
    except Exception as e:
        logger.warning(f"Could not hot-patch witness: {e}")


def _hot_patch_judge(session_id: str, index: int, config: JudgePersonaConfig):
    """Apply persona changes to an already-running judge agent."""
    try:
        from .session import _sessions
        session = _sessions.get(session_id)
        if not session or index >= len(session.judges):
            return
        agent = session.judges[index]
        p = agent.persona
        p.llm_model = config.llm_model
        p.llm_temperature = config.llm_temperature
        p.llm_max_tokens = config.llm_max_tokens
        p.custom_system_prompt = config.system_prompt
        p.authority_level = config.authority_level
        logger.info(f"Hot-patched judge {index} (model={config.llm_model})")
    except Exception as e:
        logger.warning(f"Could not hot-patch judge: {e}")


# --- Individual persona updates ---

@router.put("/{session_id}/prosecution/attorney/{index}")
async def set_prosecution_attorney(
    session_id: str, index: int, config: AttorneyPersonaConfig
) -> Dict[str, Any]:
    """Set a specific prosecution attorney persona (index 0-2)."""
    if index < 0 or index > 2:
        raise HTTPException(status_code=400, detail="Attorney index must be 0-2")

    if session_id not in _session_personas:
        _session_personas[session_id] = TeamPersonaConfig()

    team = _session_personas[session_id]
    # Initialize from defaults if empty
    if not team.prosecution_attorneys:
        team.prosecution_attorneys = [
            AttorneyPersonaConfig(**{k: v for k, v in a.items() if k != "id"})
            for a in DEFAULT_PROSECUTION_ATTORNEYS
        ]

    team.prosecution_attorneys[index] = config
    _hot_patch_attorney(session_id, "prosecution", config.role, config)
    return {"session_id": session_id, "side": "prosecution", "index": index, "config": config.model_dump(), "message": "Updated"}


@router.put("/{session_id}/defense/attorney/{index}")
async def set_defense_attorney(
    session_id: str, index: int, config: AttorneyPersonaConfig
) -> Dict[str, Any]:
    """Set a specific defense attorney persona (index 0-2)."""
    if index < 0 or index > 2:
        raise HTTPException(status_code=400, detail="Attorney index must be 0-2")

    if session_id not in _session_personas:
        _session_personas[session_id] = TeamPersonaConfig()

    team = _session_personas[session_id]
    if not team.defense_attorneys:
        team.defense_attorneys = [
            AttorneyPersonaConfig(**{k: v for k, v in a.items() if k != "id"})
            for a in DEFAULT_DEFENSE_ATTORNEYS
        ]

    team.defense_attorneys[index] = config
    _hot_patch_attorney(session_id, "defense", config.role, config)
    return {"session_id": session_id, "side": "defense", "index": index, "config": config.model_dump(), "message": "Updated"}


@router.put("/{session_id}/prosecution/witness/{index}")
async def set_prosecution_witness(
    session_id: str, index: int, config: WitnessPersonaConfig
) -> Dict[str, Any]:
    """Set a specific prosecution witness persona (index 0-2)."""
    if index < 0 or index > 2:
        raise HTTPException(status_code=400, detail="Witness index must be 0-2")

    if session_id not in _session_personas:
        _session_personas[session_id] = TeamPersonaConfig()

    team = _session_personas[session_id]
    if not team.prosecution_witnesses:
        team.prosecution_witnesses = [
            WitnessPersonaConfig(**{k: v for k, v in a.items() if k != "id"})
            for a in DEFAULT_PROSECUTION_WITNESSES
        ]

    team.prosecution_witnesses[index] = config
    _hot_patch_witness(session_id, config.name, config)
    return {"session_id": session_id, "side": "prosecution", "index": index, "config": config.model_dump(), "message": "Updated"}


@router.put("/{session_id}/defense/witness/{index}")
async def set_defense_witness(
    session_id: str, index: int, config: WitnessPersonaConfig
) -> Dict[str, Any]:
    """Set a specific defense witness persona (index 0-2)."""
    if index < 0 or index > 2:
        raise HTTPException(status_code=400, detail="Witness index must be 0-2")

    if session_id not in _session_personas:
        _session_personas[session_id] = TeamPersonaConfig()

    team = _session_personas[session_id]
    if not team.defense_witnesses:
        team.defense_witnesses = [
            WitnessPersonaConfig(**{k: v for k, v in a.items() if k != "id"})
            for a in DEFAULT_DEFENSE_WITNESSES
        ]

    team.defense_witnesses[index] = config
    _hot_patch_witness(session_id, config.name, config)
    return {"session_id": session_id, "side": "defense", "index": index, "config": config.model_dump(), "message": "Updated"}


@router.put("/{session_id}/judge/{index}")
async def set_judge_persona(
    session_id: str, index: int, config: JudgePersonaConfig
) -> Dict[str, Any]:
    """Set a specific judge persona (index 0=presiding, 1=scoring)."""
    if index < 0 or index > 1:
        raise HTTPException(status_code=400, detail="Judge index must be 0-1")

    if session_id not in _session_personas:
        _session_personas[session_id] = TeamPersonaConfig()

    team = _session_personas[session_id]
    if not team.judges:
        team.judges = [
            JudgePersonaConfig(**{k: v for k, v in j.items() if k != "id"})
            for j in DEFAULT_JUDGES
        ]

    team.judges[index] = config
    _hot_patch_judge(session_id, index, config)
    return {"session_id": session_id, "index": index, "config": config.model_dump(), "message": "Updated"}


# --- Backward-compat endpoints ---

@router.put("/{session_id}/judge")
async def set_judge_persona_legacy(session_id: str, config: JudgePersonaConfig) -> Dict[str, Any]:
    """Legacy: set presiding judge persona."""
    return await set_judge_persona(session_id, 0, config)


@router.put("/{session_id}/opposing-attorney")
async def set_attorney_persona_legacy(session_id: str, config: AttorneyPersonaConfig) -> Dict[str, Any]:
    """Legacy: set opposing direct/cross attorney."""
    return await set_defense_attorney(session_id, 1, config)


@router.post("/{session_id}/apply-preset/judge/{preset_id}")
async def apply_judge_preset(session_id: str, preset_id: str) -> Dict[str, Any]:
    """Apply a judge preset to a session."""
    preset = next((p for p in DEFAULT_JUDGES if p["id"] == preset_id), None)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    config = JudgePersonaConfig(
        name=preset["name"],
        role=preset.get("role", "presiding"),
        temperament=preset["temperament"],
        scoring_style=preset["scoring_style"],
        authority_level=preset["authority_level"],
        years_on_bench=preset["years_on_bench"],
        description=preset.get("description", ""),
    )

    idx = 0 if preset.get("role") == "presiding" else 1
    return await set_judge_persona(session_id, idx, config)


@router.post("/{session_id}/apply-preset/attorney/{preset_id}")
async def apply_attorney_preset(session_id: str, preset_id: str) -> Dict[str, Any]:
    """Apply an attorney preset to a session."""
    all_attorneys = DEFAULT_PROSECUTION_ATTORNEYS + DEFAULT_DEFENSE_ATTORNEYS
    preset = next((p for p in all_attorneys if p["id"] == preset_id), None)
    if not preset:
        raise HTTPException(status_code=404, detail="Preset not found")

    config = AttorneyPersonaConfig(
        name=preset["name"],
        role=preset.get("role", "direct_cross"),
        style=preset["style"],
        skill_level=preset["skill_level"],
        objection_frequency=preset.get("objection_frequency", 0.3),
        risk_tolerance=preset.get("risk_tolerance", 0.5),
        description=preset.get("description", ""),
    )

    # Determine side and index
    is_prosecution = preset["id"].startswith("pros_")
    role_to_index = {"opening": 0, "direct_cross": 1, "closing": 2}
    idx = role_to_index.get(preset.get("role", "direct_cross"), 1)

    if is_prosecution:
        return await set_prosecution_attorney(session_id, idx, config)
    else:
        return await set_defense_attorney(session_id, idx, config)


@router.delete("/{session_id}")
async def reset_session_personas(session_id: str) -> Dict[str, str]:
    """Reset all personas for a session to defaults."""
    if session_id in _session_personas:
        del _session_personas[session_id]
    return {"message": "All personas reset to defaults"}


# =============================================================================
# LLM CONFIGURATION
# =============================================================================

_DEFAULT_LLM_CONFIG = {
    "model": "gpt-4.1",
    "temperature": 0.7,
    "max_tokens": 500,
    "tts_model": "tts-1",
    "tts_voice": "alloy",
}

_session_llm_configs: Dict[str, Dict[str, Any]] = {}


class LLMConfigUpdate(BaseModel):
    model: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=50, le=16000)
    tts_model: Optional[str] = None
    tts_voice: Optional[str] = None


@router.get("/{session_id}/llm-config")
async def get_llm_config(session_id: str) -> Dict[str, Any]:
    """Get current LLM configuration for a session."""
    config = _session_llm_configs.get(session_id, {})
    merged = {**_DEFAULT_LLM_CONFIG, **config}
    from ..services.llm_providers import AVAILABLE_MODELS
    merged["available_models"] = AVAILABLE_MODELS
    merged["available_tts_voices"] = [
        {"id": "alloy", "label": "Alloy (Neutral)"},
        {"id": "echo", "label": "Echo (Male)"},
        {"id": "fable", "label": "Fable (Expressive)"},
        {"id": "onyx", "label": "Onyx (Deep Male)"},
        {"id": "nova", "label": "Nova (Female)"},
        {"id": "shimmer", "label": "Shimmer (Warm Female)"},
    ]
    return merged


@router.put("/{session_id}/llm-config")
async def update_llm_config(session_id: str, update: LLMConfigUpdate) -> Dict[str, Any]:
    """Update LLM configuration for a session."""
    current = _session_llm_configs.get(session_id, {})
    for field, value in update.dict(exclude_none=True).items():
        current[field] = value
    _session_llm_configs[session_id] = current
    merged = {**_DEFAULT_LLM_CONFIG, **current}

    from ..services.llm_service import set_llm_overrides
    set_llm_overrides({
        "model": merged.get("model"),
        "temperature": merged.get("temperature"),
        "max_tokens": merged.get("max_tokens"),
    })

    logger.info(f"LLM config updated for session {session_id}: {current}")
    return {"message": "LLM configuration updated", "config": merged}


@router.get("/{session_id}/agent-configs")
async def get_live_agent_configs(session_id: str) -> Dict[str, Any]:
    """Return effective LLM config + default system prompt for every live agent."""
    from .session import _sessions
    session = _sessions.get(session_id)
    if not session:
        return {"agents": []}

    agents = []

    for team_key, agent in session.attorney_team.items():
        p = agent.persona
        default_prompt = agent._build_system_prompt("(context placeholder)")
        agents.append({
            "type": "attorney",
            "key": team_key,
            "name": p.name,
            "side": p.side,
            "llm_model": p.llm_model,
            "llm_temperature": p.llm_temperature,
            "llm_max_tokens": p.llm_max_tokens,
            "custom_system_prompt": p.custom_system_prompt,
            "default_system_prompt": default_prompt,
        })

    for wid, agent in session.witnesses.items():
        p = agent.persona
        default_prompt = agent._build_system_prompt("(context placeholder)")
        agents.append({
            "type": "witness",
            "key": wid,
            "name": p.name,
            "side": p.called_by,
            "llm_model": p.llm_model,
            "llm_temperature": p.llm_temperature,
            "llm_max_tokens": p.llm_max_tokens,
            "custom_system_prompt": p.custom_system_prompt,
            "default_system_prompt": default_prompt,
        })

    for i, agent in enumerate(session.judges):
        p = agent.persona
        default_prompt = agent._build_system_prompt("(context placeholder)")
        agents.append({
            "type": "judge",
            "key": f"judge_{i}",
            "name": p.name,
            "side": "court",
            "llm_model": p.llm_model,
            "llm_temperature": p.llm_temperature,
            "llm_max_tokens": p.llm_max_tokens,
            "custom_system_prompt": p.custom_system_prompt,
            "default_system_prompt": default_prompt,
        })

    return {"agents": agents}
