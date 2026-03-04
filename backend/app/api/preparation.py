"""
Preparation Phase API Endpoints

Provides AI-generated preparation materials for mock trial practice:
- Case brief
- Theory of the case
- Witness outlines
- Objection playbook
- Cross-exam traps
- AMTA rules reminders
- Coach AI chat
- Drilling specific sections

Materials are stored in the database per case_id, so they only need to be
generated once per case. Regeneration is only triggered when explicitly requested.
"""

import logging
import asyncio
import json
import os
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel

from ..services.llm_service import call_llm_async, PersonaContext
from .session import get_session


def _normalize_called_by(raw: str) -> str:
    """Map prosecution/either/plaintiff variants to 'plaintiff' for consistency."""
    val = (raw or "unknown").lower().strip()
    if val in ("plaintiff", "prosecution", "either"):
        return "plaintiff"
    return val

# Try to import Supabase repository, fall back to in-memory if not available
try:
    from ..db.supabase_client import (
        SupabasePrepMaterialsRepository,
        SupabaseAgentPrepRepository,
        get_supabase_client,
    )
    _db_available = True
except Exception as e:
    _db_available = False
    logging.warning(f"Database not available, using in-memory storage: {e}")

router = APIRouter()
logger = logging.getLogger(__name__)


# =============================================================================
# REQUEST/RESPONSE MODELS
# =============================================================================

class WitnessOutline(BaseModel):
    witness_id: str
    witness_name: str
    called_by: str
    direct_exam_outline: List[str]
    cross_exam_outline: List[str]
    key_points: List[str]
    potential_weaknesses: List[str]


class ObjectionPlaybook(BaseModel):
    common_objections: List[Dict[str, str]]
    when_to_object: List[str]
    how_to_respond: List[str]


class CrossExamTrap(BaseModel):
    witness_name: str
    trap_description: str
    how_to_set: str
    expected_response: str
    follow_up: str


class PrepMaterials(BaseModel):
    case_brief: str = ""
    theory_plaintiff: str = ""
    theory_defense: str = ""
    opening_plaintiff: str = ""
    opening_defense: str = ""
    witness_outlines: List[WitnessOutline] = []
    objection_playbook: Optional[ObjectionPlaybook] = None
    cross_exam_traps: List[CrossExamTrap] = []
    amta_rules: List[str] = []
    generation_status: Dict[str, str] = {}


class CoachChatRequest(BaseModel):
    message: str
    context: Optional[str] = None


class CoachChatResponse(BaseModel):
    response: str
    suggestions: List[str] = []


class DrillRequest(BaseModel):
    drill_type: str
    witness_id: Optional[str] = None
    scenario: Optional[str] = None


class DrillResponse(BaseModel):
    scenario: str
    prompts: List[str]
    tips: List[str]
    sample_responses: List[str]


class UserNotesRequest(BaseModel):
    section: str
    content: str


class UpdateMaterialRequest(BaseModel):
    """Request to update a specific preparation material section."""
    section: str  # case_brief, theory_plaintiff, theory_defense, witness_outline, objection_playbook
    content: str  # The updated content (text or JSON string for complex sections)
    witness_id: Optional[str] = None  # Required for witness_outline updates


class UpdateMaterialResponse(BaseModel):
    """Response after updating preparation material."""
    success: bool
    section: str
    message: str
    updated_at: str


class SpeechAnalysisRequest(BaseModel):
    """Request to analyze speech patterns from a transcript."""
    transcript: str
    duration_seconds: float
    context: str = "general"  # opening_statement, cross_examination, direct_examination, objection, coach_question


class FillerWord(BaseModel):
    word: str
    count: int


class PauseAnalysis(BaseModel):
    count: int
    total_seconds: float


class SpeechAnalysisResponse(BaseModel):
    """Response with detailed speech pattern analysis."""
    transcript: str
    duration_seconds: float
    word_count: int
    words_per_minute: int
    filler_words: List[FillerWord]
    filler_word_percentage: float
    average_sentence_length: float
    pauses: PauseAnalysis
    clarity_score: int  # 0-100
    pacing_feedback: str
    delivery_tips: List[str]
    strengths: List[str]
    areas_to_improve: List[str]


# =============================================================================
# LOCAL FILE STORAGE (Works without database)
# =============================================================================

from pathlib import Path

# Directory for storing prep materials locally
PREP_CACHE_DIR = Path(__file__).parent.parent / "data" / "prep_cache"
PREP_CACHE_DIR.mkdir(parents=True, exist_ok=True)

AUDIO_CACHE_DIR = PREP_CACHE_DIR / "audio"
AUDIO_CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _get_cache_file(case_id: str) -> Path:
    """Get the cache file path for a case."""
    safe_case_id = case_id.replace("/", "_").replace("\\", "_")
    return PREP_CACHE_DIR / f"{safe_case_id}.json"


def _get_audio_cache_file(case_id: str, side: str) -> Path:
    """Get the audio cache file path for an opening statement."""
    safe_case_id = case_id.replace("/", "_").replace("\\", "_")
    return AUDIO_CACHE_DIR / f"{safe_case_id}_opening_{side}.mp3"


def has_cached_audio(case_id: str, side: str) -> bool:
    """Check if cached TTS audio exists for an opening statement."""
    return _get_audio_cache_file(case_id, side).exists()


def save_audio_cache(case_id: str, side: str, audio_data: bytes):
    """Save TTS audio data to local file cache."""
    path = _get_audio_cache_file(case_id, side)
    try:
        path.write_bytes(audio_data)
        logger.info(f"Saved opening audio cache: {path} ({len(audio_data)} bytes)")
    except Exception as e:
        logger.error(f"Failed to save audio cache: {e}")


def load_audio_cache(case_id: str, side: str) -> Optional[bytes]:
    """Load cached TTS audio data."""
    path = _get_audio_cache_file(case_id, side)
    if path.exists():
        try:
            return path.read_bytes()
        except Exception as e:
            logger.error(f"Failed to load audio cache: {e}")
    return None


def load_materials_from_file(case_id: str) -> Optional[Dict[str, Any]]:
    """Load materials from local JSON file."""
    cache_file = _get_cache_file(case_id)
    if cache_file.exists():
        try:
            with open(cache_file, "r") as f:
                data = json.load(f)
                return {
                    "case_brief": data.get("case_brief"),
                    "theory_plaintiff": data.get("theory_plaintiff"),
                    "theory_defense": data.get("theory_defense"),
                    "opening_plaintiff": data.get("opening_plaintiff"),
                    "opening_defense": data.get("opening_defense"),
                    "witness_outlines": {
                        w.get("witness_id", str(i)): w 
                        for i, w in enumerate(data.get("witness_outlines") or [])
                    },
                    "objection_playbook": data.get("objection_playbook"),
                    "cross_exam_traps": data.get("cross_exam_traps") or [],
                    "amta_rules": get_amta_rules(),
                    "is_complete": data.get("is_complete", False),
                    "generation_status": data.get("generation_status") or {},
                }
        except Exception as e:
            logger.warning(f"Failed to load prep cache file: {e}")
    return None


def save_materials_to_file(case_id: str, materials: Dict[str, Any], is_complete: bool = False):
    """Save materials to local JSON file."""
    cache_file = _get_cache_file(case_id)
    try:
        # Convert Pydantic models to dicts
        witness_list = []
        for wid, outline in materials.get("witness_outlines", {}).items():
            if outline:
                if hasattr(outline, "dict"):
                    witness_list.append(outline.dict())
                elif isinstance(outline, dict):
                    witness_list.append(outline)
        
        playbook = materials.get("objection_playbook")
        if playbook and hasattr(playbook, "dict"):
            playbook = playbook.dict()
        
        traps = []
        for trap in materials.get("cross_exam_traps", []):
            if hasattr(trap, "dict"):
                traps.append(trap.dict())
            elif isinstance(trap, dict):
                traps.append(trap)
        
        data = {
            "case_id": case_id,
            "case_brief": materials.get("case_brief"),
            "theory_plaintiff": materials.get("theory_plaintiff"),
            "theory_defense": materials.get("theory_defense"),
            "opening_plaintiff": materials.get("opening_plaintiff"),
            "opening_defense": materials.get("opening_defense"),
            "witness_outlines": witness_list,
            "objection_playbook": playbook,
            "cross_exam_traps": traps,
            "is_complete": is_complete,
            "generation_status": materials.get("generation_status", {}),
        }
        
        with open(cache_file, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Saved prep materials to {cache_file}")
    except Exception as e:
        logger.error(f"Failed to save prep cache file: {e}")


# =============================================================================
# DATABASE-BACKED STORAGE (Falls back to file storage if unavailable)
# =============================================================================

def get_prep_repo():
    """Get the prep materials repository."""
    if _db_available:
        try:
            return SupabasePrepMaterialsRepository()
        except Exception as e:
            logger.warning(f"Failed to create Supabase repo: {e}")
    return None


def get_cached_materials_from_db(case_id: str) -> Optional[Dict[str, Any]]:
    """Get cached materials from database, merging with file cache for completeness."""
    db_data = None
    repo = get_prep_repo()
    if repo:
        try:
            raw = repo.get_by_case_id(case_id)
            if raw:
                db_data = {
                    "case_brief": raw.get("case_brief"),
                    "theory_plaintiff": raw.get("theory_plaintiff"),
                    "theory_defense": raw.get("theory_defense"),
                    "opening_plaintiff": raw.get("opening_plaintiff"),
                    "opening_defense": raw.get("opening_defense"),
                    "witness_outlines": {
                        w.get("witness_id", str(i)): w 
                        for i, w in enumerate(raw.get("witness_outlines") or [])
                    },
                    "objection_playbook": raw.get("objection_playbook"),
                    "cross_exam_traps": raw.get("cross_exam_traps") or [],
                    "amta_rules": get_amta_rules(),
                    "is_complete": raw.get("is_complete", False),
                    "generation_status": raw.get("generation_status") or {},
                }
        except Exception as e:
            logger.warning(f"Failed to get materials from DB: {e}")

    file_data = load_materials_from_file(case_id)

    if not db_data and not file_data:
        return None
    if not db_data:
        return file_data
    if not file_data:
        return db_data

    # Merge: for each key, prefer whichever source has actual content
    merged = dict(db_data)
    merge_keys = [
        "case_brief", "theory_plaintiff", "theory_defense",
        "opening_plaintiff", "opening_defense",
        "objection_playbook",
    ]
    needs_db_update = False
    for key in merge_keys:
        if not merged.get(key) and file_data.get(key):
            merged[key] = file_data[key]
            needs_db_update = True
    # Merge list/dict fields if DB version is empty
    if not merged.get("witness_outlines") and file_data.get("witness_outlines"):
        merged["witness_outlines"] = file_data["witness_outlines"]
        needs_db_update = True
    if not merged.get("cross_exam_traps") and file_data.get("cross_exam_traps"):
        merged["cross_exam_traps"] = file_data["cross_exam_traps"]
        needs_db_update = True

    # If file had fields that DB was missing, sync them back to DB
    if needs_db_update and repo:
        try:
            repo.upsert(
                case_id,
                opening_plaintiff=merged.get("opening_plaintiff"),
                opening_defense=merged.get("opening_defense"),
                is_complete=merged.get("is_complete", False),
            )
        except Exception:
            pass

    return merged


def save_materials_to_db(case_id: str, materials: Dict[str, Any], is_complete: bool = False):
    """Save materials to database and local file (for redundancy)."""
    # Always save to file first (as backup)
    save_materials_to_file(case_id, materials, is_complete)
    
    # Try to save to database
    repo = get_prep_repo()
    if repo:
        try:
            # Convert witness_outlines dict to list
            witness_list = []
            for wid, outline in materials.get("witness_outlines", {}).items():
                if outline:
                    if hasattr(outline, "dict"):
                        witness_list.append(outline.dict())
                    elif isinstance(outline, dict):
                        witness_list.append(outline)
            
            # Convert objection_playbook
            playbook = materials.get("objection_playbook")
            if playbook and hasattr(playbook, "dict"):
                playbook = playbook.dict()
            
            # Convert cross_exam_traps
            traps = []
            for trap in materials.get("cross_exam_traps", []):
                if hasattr(trap, "dict"):
                    traps.append(trap.dict())
                elif isinstance(trap, dict):
                    traps.append(trap)
            
            repo.upsert(
                case_id=case_id,
                case_brief=materials.get("case_brief"),
                theory_plaintiff=materials.get("theory_plaintiff"),
                theory_defense=materials.get("theory_defense"),
                opening_plaintiff=materials.get("opening_plaintiff"),
                opening_defense=materials.get("opening_defense"),
                witness_outlines=witness_list,
                objection_playbook=playbook,
                cross_exam_traps=traps,
                is_complete=is_complete,
                generation_status=materials.get("generation_status", {}),
            )
            logger.info(f"Saved prep materials for case {case_id}")
        except Exception as e:
            logger.error(f"Failed to save materials to DB: {e}")


def get_cached_materials(session) -> Dict[str, Any]:
    """Get cached materials from database first, then session fallback."""
    case_id = session.case_id
    
    if case_id:
        db_materials = get_cached_materials_from_db(case_id)
        if db_materials:
            session.prep_materials = db_materials
            session.prep_generation_status = db_materials.get("generation_status", {})
            return db_materials
    
    if not session.prep_materials:
        session.prep_materials = {
            "case_brief": None,
            "theory_plaintiff": None,
            "theory_defense": None,
            "opening_plaintiff": None,
            "opening_defense": None,
            "witness_outlines": {},
            "objection_playbook": None,
            "cross_exam_traps": [],
            "amta_rules": get_amta_rules(),
        }
    return session.prep_materials


# =============================================================================
# LLM GENERATION FUNCTIONS (Thorough, case-specific prompts)
# =============================================================================

async def generate_case_brief(
    case_name: str, 
    case_type: str, 
    description: str, 
    charge: str = "",
    facts: List[Dict] = None,
    summary: str = ""
) -> str:
    """Generate a comprehensive case brief with full case context."""
    
    # Build facts summary
    facts_text = ""
    if facts:
        stipulations = [f["content"] for f in facts if f.get("fact_type") == "stipulation"]
        evidence = [f["content"] for f in facts if f.get("fact_type") == "evidence"]
        legal_standards = [f["content"] for f in facts if f.get("fact_type") == "legal_standard"]
        
        if stipulations:
            facts_text += "\n\nKEY STIPULATIONS:\n" + "\n".join(f"- {s}" for s in stipulations[:6])
        if evidence:
            facts_text += "\n\nKEY EVIDENCE:\n" + "\n".join(f"- {e}" for e in evidence[:4])
        if legal_standards:
            facts_text += "\n\nLEGAL STANDARDS:\n" + "\n".join(f"- {l}" for l in legal_standards[:3])
    
    prompt = f"""You are preparing a comprehensive case brief for a mock trial student. Analyze this case thoroughly.

CASE: {case_name}
TYPE: {case_type.upper()}
{f'CHARGE: {charge}' if charge else ''}

CASE SUMMARY:
{summary or description}
{facts_text}

Create a DETAILED case brief that includes:

1. PROCEDURAL POSTURE
   - What stage is this case at?
   - What must each side prove?

2. PARTIES & ROLES
   - Who is the plaintiff/prosecution?
   - Who is the defendant?
   - What is the relationship between parties?

3. KEY FACTS (Undisputed)
   - List the stipulated facts both sides agree on
   - Note the timeline of events

4. CONTESTED ISSUES
   - What facts are in dispute?
   - What is each side's version of events?

5. LEGAL ELEMENTS
   - What must the prosecution/plaintiff prove?
   - What is the burden of proof?
   - What defenses are available?

6. THEME DEVELOPMENT
   - Suggest a prosecution/plaintiff theme
   - Suggest a defense theme

Write 400-500 words with clear section headers."""

    persona = PersonaContext(
        role="coach",
        name="Legal Coach",
        style="analytical",
        authority=0.9,
        formality=0.8
    )
    
    try:
        result = await asyncio.wait_for(
            call_llm_async(
                system_prompt="You are an experienced mock trial coach with 20 years of AMTA competition experience. Provide thorough, actionable analysis.",
                user_prompt=prompt,
                persona=persona,
                max_tokens=800,
                temperature=0.7
            ),
            timeout=45.0
        )
        return result
    except asyncio.TimeoutError:
        logger.error("Case brief generation timed out")
        raise
    except Exception as e:
        logger.error(f"Case brief generation failed: {e}")
        raise


async def generate_theory(
    case_name: str, 
    side: str, 
    description: str,
    charge: str = "",
    facts: List[Dict] = None,
    witnesses: List[Dict] = None
) -> str:
    """Generate comprehensive theory of the case for one side."""
    
    # Build supporting context
    facts_text = ""
    if facts:
        relevant_facts = [f["content"] for f in facts[:8]]
        facts_text = "\n\nKEY FACTS:\n" + "\n".join(f"- {fact}" for fact in relevant_facts)
    
    witness_text = ""
    if witnesses:
        side_witnesses = [w for w in witnesses if _normalize_called_by(w.get("called_by", "")) == side]
        opposing_witnesses = [w for w in witnesses if _normalize_called_by(w.get("called_by", "")) != side]
        
        witness_text = f"\n\n{side.upper()} WITNESSES:\n"
        for w in side_witnesses[:3]:
            witness_text += f"- {w.get('name')}: {w.get('role_description', '')}\n"
        
        witness_text += f"\nOPPOSING WITNESSES:\n"
        for w in opposing_witnesses[:3]:
            witness_text += f"- {w.get('name')}: {w.get('role_description', '')}\n"
    
    side_label = "PROSECUTION" if side == "plaintiff" else "DEFENSE"
    
    prompt = f"""Develop a comprehensive trial strategy and theory for the {side_label} in this case.

CASE: {case_name}
{f'CHARGE: {charge}' if charge else ''}

CASE OVERVIEW:
{description}
{facts_text}
{witness_text}

Create a DETAILED theory of the case that includes:

1. THEORY STATEMENT (3-4 sentences)
   - What is your narrative of what happened?
   - Why should the jury believe your version?

2. THEME / TAGLINE
   - A memorable phrase that encapsulates your case
   - Something jurors will remember during deliberation

3. KEY ARGUMENTS (5-6 points)
   - Your strongest legal arguments
   - How the evidence supports your theory

4. WITNESS STRATEGY
   - What to establish with each of your witnesses
   - What to challenge in opposing witnesses

5. EVIDENCE TO EMPHASIZE
   - Which exhibits help your case
   - How to use stipulations to your advantage

6. ANTICIPATED CHALLENGES
   - Weaknesses in your case
   - How to address them

Write 350-450 words with clear section headers."""

    persona = PersonaContext(
        role="coach",
        name="Trial Strategist",
        style="persuasive",
        authority=0.9,
        formality=0.7
    )
    
    try:
        result = await asyncio.wait_for(
            call_llm_async(
                system_prompt=f"You are a veteran mock trial coach helping prepare the {side_label}. Be strategic, persuasive, and thorough.",
                user_prompt=prompt,
                persona=persona,
                max_tokens=700,
                temperature=0.7
            ),
            timeout=40.0
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"Theory generation for {side} timed out")
        raise
    except Exception as e:
        logger.error(f"Theory generation failed: {e}")
        raise


async def generate_witness_outline(
    witness_name: str, 
    witness_role: str, 
    called_by: str, 
    is_friendly: bool,
    affidavit_excerpt: str = "",
    case_context: str = ""
) -> Dict:
    """Generate detailed examination outline for one witness."""
    relationship = "YOUR witness (direct examination focus)" if is_friendly else "OPPOSING witness (cross-examination focus)"
    
    prompt = f"""Create detailed examination strategies for {witness_name}.

WITNESS: {witness_name}
ROLE: {witness_role}
CALLED BY: {called_by.upper()}
RELATIONSHIP: {relationship}

{f'CASE CONTEXT: {case_context}' if case_context else ''}

{f'WITNESS BACKGROUND (from affidavit): {affidavit_excerpt[:800]}' if affidavit_excerpt else ''}

Provide a JSON response with DETAILED, SPECIFIC examination questions and strategies:

{{
  "direct_exam_outline": [
    "Establish credentials: Ask about their professional background and experience",
    "Set the scene: Have them describe their involvement in the events",
    "Key testimony point 1: [specific question building your case]",
    "Key testimony point 2: [specific question building your case]",
    "Key testimony point 3: [specific question building your case]",
    "Emphasize: Final question that reinforces your theme",
    "Introduce exhibits: 'I'd like to show you Exhibit X...'"
  ],
  "cross_exam_outline": [
    "Establish limitations: What didn't they see/know?",
    "Prior inconsistency: Compare to earlier statements",
    "Bias/motive: Explore reasons to favor one side",
    "Alternative explanation: Suggest different interpretation",
    "Impeachment: Challenge credibility if applicable",
    "Concessions: Get them to agree with helpful facts",
    "Control questions: Short, leading, one fact at a time"
  ],
  "key_points": [
    "Most important fact this witness establishes",
    "How their testimony supports the theory of the case",
    "Critical quote or admission to elicit",
    "Documentary evidence they can authenticate"
  ],
  "potential_weaknesses": [
    "Credibility issues: [specific concerns]",
    "Gaps in knowledge: What they can't testify to",
    "Contradictions: Possible inconsistencies in their story",
    "Bias factors: Why they might favor one side"
  ]
}}

Respond with valid JSON only. Make questions SPECIFIC to this witness and case."""

    persona = PersonaContext(
        role="coach",
        name="Examination Coach",
        style="practical",
        authority=0.9,
        formality=0.6
    )
    
    try:
        result = await asyncio.wait_for(
            call_llm_async(
                system_prompt="You are an expert mock trial examination coach. Create detailed, case-specific examination strategies. Respond with valid JSON only.",
                user_prompt=prompt,
                persona=persona,
                max_tokens=800,
                temperature=0.7
            ),
            timeout=35.0
        )
        
        # Parse JSON from response
        json_start = result.find('{')
        json_end = result.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(result[json_start:json_end])
        return {}
    except asyncio.TimeoutError:
        logger.error(f"Witness outline for {witness_name} timed out")
        raise
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse witness outline JSON for {witness_name}")
        return {}
    except Exception as e:
        logger.error(f"Witness outline generation failed: {e}")
        raise


async def generate_objection_playbook(
    case_name: str = "",
    case_type: str = "",
    witnesses: List[Dict] = None,
    human_role: str = "attorney_plaintiff"
) -> Dict:
    """Generate comprehensive, case-specific objection playbook."""
    
    # Build witness context for case-specific objections
    witness_context = ""
    if witnesses:
        witness_context = "\n\nWITNESSES IN THIS CASE:\n"
        for w in witnesses[:6]:
            witness_context += f"- {w.get('name')} ({_normalize_called_by(w.get('called_by', ''))}): {w.get('role_description', '')}\n"
    
    is_prosecution = "plaintiff" in human_role
    your_side = "PROSECUTION" if is_prosecution else "DEFENSE"
    opposing_side = "DEFENSE" if is_prosecution else "PROSECUTION"
    
    prompt = f"""Create a comprehensive objection playbook for the {your_side} in this mock trial case.

CASE: {case_name or 'Mock Trial Case'}
TYPE: {case_type.upper() if case_type else 'TRIAL'}
YOUR ROLE: {your_side} ATTORNEY
{witness_context}

Generate a DETAILED objection strategy with specific examples relevant to this case:

{{
  "common_objections": [
    {{
      "type": "Hearsay",
      "rule": "Out-of-court statement offered for truth of matter asserted (FRE 801-802)",
      "when_to_use": "When witness quotes what someone else said to prove that statement is true",
      "example_in_this_case": "[Specific example relevant to this case's witnesses]",
      "magic_words": "Objection, hearsay. The witness is testifying to an out-of-court statement offered for its truth.",
      "response_if_objected": "Your Honor, this statement is not offered for its truth but to show [effect on listener/state of mind/etc.]"
    }},
    {{
      "type": "Leading Question on Direct",
      "rule": "Leading questions not permitted on direct examination (FRE 611)",
      "when_to_use": "When opposing counsel suggests answer in question to their own witness",
      "example_in_this_case": "[Specific example]",
      "magic_words": "Objection, leading. Counsel is testifying for the witness.",
      "response_if_objected": "Your Honor, this is foundational/hostile witness/I'll rephrase."
    }},
    {{
      "type": "Relevance",
      "rule": "Evidence must be relevant to be admissible (FRE 401-402)",
      "when_to_use": "When testimony has no connection to the issues in the case",
      "example_in_this_case": "[Specific example]",
      "magic_words": "Objection, relevance. This testimony has no bearing on the issues before the court.",
      "response_if_objected": "Your Honor, this is relevant because [explain connection to elements]."
    }},
    {{
      "type": "Speculation",
      "rule": "Witness must testify from personal knowledge (FRE 602)",
      "when_to_use": "When witness guesses or assumes rather than stating what they know",
      "example_in_this_case": "[Specific example]",
      "magic_words": "Objection, calls for speculation. The witness has no personal knowledge.",
      "response_if_objected": "Your Honor, the witness is offering a reasonable inference from observed facts."
    }},
    {{
      "type": "Lack of Foundation",
      "rule": "Proper foundation must be laid before admitting evidence",
      "when_to_use": "When counsel tries to admit exhibit or testimony without proper setup",
      "example_in_this_case": "[Specific example]",
      "magic_words": "Objection, lack of foundation. Counsel has not established [authentication/personal knowledge/chain of custody].",
      "response_if_objected": "Your Honor, I'll lay additional foundation. [Ask foundational questions]"
    }},
    {{
      "type": "Beyond the Scope",
      "rule": "Cross-examination limited to scope of direct (FRE 611)",
      "when_to_use": "When cross-examiner asks about topics not covered on direct",
      "example_in_this_case": "[Specific example]",
      "magic_words": "Objection, beyond the scope of direct examination.",
      "response_if_objected": "Your Honor, this goes to credibility/this was opened on direct when witness said [X]."
    }},
    {{
      "type": "Improper Character Evidence",
      "rule": "Character evidence generally inadmissible to prove conduct (FRE 404)",
      "when_to_use": "When counsel asks about defendant's/witness's general character or past acts",
      "example_in_this_case": "[Specific example]",
      "magic_words": "Objection, improper character evidence under Rule 404.",
      "response_if_objected": "Your Honor, this is offered for [motive/intent/identity/plan], not character."
    }},
    {{
      "type": "Asked and Answered",
      "rule": "Repetitive questions waste time and harass witness",
      "when_to_use": "When counsel repeatedly asks the same question already answered",
      "example_in_this_case": "[Specific example]",
      "magic_words": "Objection, asked and answered. The witness has already responded to this question.",
      "response_if_objected": "Your Honor, I'm seeking clarification on [specific point]."
    }}
  ],
  "when_to_object": [
    "Object IMMEDIATELY when you hear the objectionable content - don't wait for the answer",
    "Object when opposing counsel leads their own witness on crucial testimony",
    "Object to hearsay statements that directly support opposing party's key arguments",
    "Object when witness speculates about another person's thoughts or motivations",
    "Object to improper exhibit introduction before it's shown to the jury",
    "Object strategically - too many objections can annoy the judge and jury",
    "Save your strongest objections for the most damaging testimony"
  ],
  "how_to_respond": [
    "Stay calm and professional - arguing helps no one",
    "State your objection clearly: 'Objection, [specific ground]'",
    "Be prepared to briefly explain if judge asks 'On what basis?'",
    "If overruled, accept gracefully and move on - don't argue with the judge",
    "If sustained, consider moving to strike if answer was already given",
    "When YOUR objection is overruled, you may request a continuing objection",
    "If opposing counsel objects to your question, have a response ready",
    "Know when to withdraw and rephrase rather than argue"
  ],
  "strategic_tips": [
    "Keep a checklist of common objections at counsel table",
    "Practice objection timing - hesitation looks weak",
    "Use objections to break opposing counsel's momentum",
    "Some judges prefer 'speaking objections' - know your judge",
    "Standing during objections shows confidence and grabs attention"
  ]
}}

Respond with valid JSON only. Make examples SPECIFIC to this case and its witnesses."""

    persona = PersonaContext(
        role="coach",
        name="Objection Coach",
        style="tactical",
        authority=0.95,
        formality=0.7
    )
    
    try:
        result = await asyncio.wait_for(
            call_llm_async(
                system_prompt="You are an expert mock trial objection coach with extensive AMTA competition experience. Create detailed, practical objection strategies. Respond with valid JSON only.",
                user_prompt=prompt,
                persona=persona,
                max_tokens=2000,
                temperature=0.7
            ),
            timeout=60.0
        )
        
        json_start = result.find('{')
        json_end = result.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(result[json_start:json_end])
        return {}
    except asyncio.TimeoutError:
        logger.error("Objection playbook generation timed out")
        raise
    except json.JSONDecodeError:
        logger.warning("Failed to parse objection playbook JSON")
        return {}
    except Exception as e:
        logger.error(f"Objection playbook generation failed: {e}")
        raise


def _ensure_string(value) -> str:
    """Convert value to string, joining lists if needed."""
    if isinstance(value, list):
        return " ".join(str(v) for v in value)
    return str(value) if value else ""


async def generate_cross_trap(witness_name: str, witness_role: str) -> Dict:
    """Generate one cross-exam trap for a witness."""
    prompt = f"""Create a cross-examination trap for {witness_name} ({witness_role}).

Provide JSON only (all values must be strings, not arrays):
{{
  "trap_description": "what the trap exposes",
  "how_to_set": "setup questions as a single string",
  "expected_response": "what witness will say",
  "follow_up": "how to spring the trap"
}}"""

    persona = PersonaContext(
        role="coach",
        name="Coach",
        style="tactical",
        authority=0.8,
        formality=0.6
    )
    
    try:
        result = await asyncio.wait_for(
            call_llm_async(
                system_prompt="You are a cross-examination coach. Respond with valid JSON only. All values must be strings.",
                user_prompt=prompt,
                persona=persona,
                max_tokens=300,
                temperature=0.7
            ),
            timeout=20.0
        )
        
        json_start = result.find('{')
        json_end = result.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(result[json_start:json_end])
            return {
                "trap_description": _ensure_string(data.get("trap_description", "")),
                "how_to_set": _ensure_string(data.get("how_to_set", "")),
                "expected_response": _ensure_string(data.get("expected_response", "")),
                "follow_up": _ensure_string(data.get("follow_up", "")),
            }
        return {}
    except asyncio.TimeoutError:
        logger.error(f"Cross trap for {witness_name} timed out")
        raise
    except json.JSONDecodeError:
        return {}
    except Exception as e:
        logger.error(f"Cross trap generation failed: {e}")
        raise


def get_amta_rules() -> List[str]:
    """Return AMTA rules (static content)."""
    return [
        "TIME LIMITS: Strict time limits apply to each phase. Opening/Closing statements have set durations.",
        "WITNESS BOUND: Witnesses must testify consistent with their affidavit. Material facts cannot be invented.",
        "OBJECTIONS: Object immediately when you hear objectionable testimony. State the type clearly.",
        "EXHIBITS: All exhibits must be properly introduced through a witness before being admitted.",
        "SCOPE: Cross-examination is limited to the scope of direct examination plus credibility.",
        "LEADING: Leading questions are not allowed on direct but are permitted on cross.",
        "APPROACHING: Always ask 'May I approach the witness?' before handing exhibits.",
        "REFRESH MEMORY: A witness may use their affidavit to refresh memory but must testify from memory.",
        "SIDEBAR: Request a sidebar for legal arguments outside the jury's presence.",
        "PROFESSIONALISM: Maintain courtroom decorum. Address the judge as 'Your Honor.'",
        "SCORING: Judges score on presentation, not who 'wins.' Focus on technique.",
        "BENCH MEMOS: Judges have bench memos. Understand the legal issues they're evaluating.",
    ]


# =============================================================================
# ENDPOINTS
# =============================================================================

@router.get("/{session_id}/materials")
async def get_prep_materials(session_id: str, force_regenerate: bool = False):
    """
    Get preparation materials. Returns cached content and status of generation.
    Materials are fetched from database first, so they persist across sessions.
    """
    session = get_session(session_id)
    
    if not session.case_id or not session.case_data:
        raise HTTPException(status_code=400, detail="No case loaded for this session")
    
    cache = get_cached_materials(session)
    status = cache.get("generation_status", {})
    
    is_complete_from_db = cache.get("is_complete", False)
    
    witness_outlines = []
    for wid, outline in cache.get("witness_outlines", {}).items():
        if outline:
            if hasattr(outline, "called_by"):
                outline.called_by = _normalize_called_by(outline.called_by)
            elif isinstance(outline, dict):
                outline["called_by"] = _normalize_called_by(outline.get("called_by", ""))
            witness_outlines.append(outline)
    
    materials = PrepMaterials(
        case_brief=cache.get("case_brief") or "",
        theory_plaintiff=cache.get("theory_plaintiff") or "",
        theory_defense=cache.get("theory_defense") or "",
        opening_plaintiff=cache.get("opening_plaintiff") or "",
        opening_defense=cache.get("opening_defense") or "",
        witness_outlines=witness_outlines,
        objection_playbook=cache.get("objection_playbook"),
        cross_exam_traps=cache.get("cross_exam_traps") or [],
        amta_rules=cache.get("amta_rules") or get_amta_rules(),
        generation_status=status
    )
    
    has_all_fields = all([
        cache.get("case_brief"),
        cache.get("theory_plaintiff"),
        cache.get("theory_defense"),
        len(cache.get("witness_outlines", {})) > 0,
        cache.get("objection_playbook"),
    ])
    is_complete = is_complete_from_db or has_all_fields

    if is_complete and not is_complete_from_db:
        cache["is_complete"] = True
        save_materials_to_db(session.case_id, cache, True)
        logger.info(f"Updated is_complete=True for case {session.case_id}")

    logger.info(
        f"GET /materials: case={session.case_id} is_complete_from_db={is_complete_from_db} "
        f"has_all_fields={has_all_fields} is_complete={is_complete} "
        f"has_opening_p={bool(cache.get('opening_plaintiff'))} "
        f"has_opening_d={bool(cache.get('opening_defense'))}"
    )
    
    # Include canonical witness and exhibit lists from case data so the
    # frontend can display a consistent list across all views.
    case_witnesses = []
    for w in (session.case_data or {}).get("witnesses", []):
        case_witnesses.append({
            "id": w.get("id"),
            "name": w.get("name"),
            "called_by": _normalize_called_by(w.get("called_by", "")),
            "role_description": w.get("role_description", ""),
        })

    case_exhibits = []
    for e in (session.case_data or {}).get("exhibits", []):
        case_exhibits.append({
            "id": e.get("id"),
            "title": e.get("title"),
            "description": e.get("description", ""),
            "exhibit_type": e.get("exhibit_type", "document"),
        })

    return {
        "session_id": session_id,
        "materials": materials.dict(),
        "is_complete": is_complete,
        "case_witnesses": case_witnesses,
        "case_exhibits": case_exhibits,
    }


@router.post("/{session_id}/generate")
async def generate_prep_materials(
    session_id: str,
    section: Optional[str] = None,
    force: bool = False,
    background_tasks: BackgroundTasks = None
):
    """
    Generate or regenerate preparation materials.
    
    Args:
        section: Specific section to generate (case_brief, theory, witnesses, objections, traps)
                 If None, generates all sections incrementally.
        force: Force regeneration even if cached
    """
    session = get_session(session_id)
    
    if not session.case_id or not session.case_data:
        raise HTTPException(status_code=400, detail="No case loaded for this session")
    
    cache = get_cached_materials(session)
    status = session.prep_generation_status
    
    case_data = session.case_data
    case_name = case_data.get("case_name", "Unknown Case")
    case_type = case_data.get("case_type", "civil")
    description = case_data.get("description", "")
    summary = case_data.get("summary", description)
    charge = case_data.get("charge", "")
    facts = case_data.get("facts", [])
    witnesses = case_data.get("witnesses", [])
    human_role = session.human_role.value if session.human_role else "attorney_plaintiff"
    
    results = {"generated": [], "errors": []}
    
    # Generate case brief with full context
    if section in [None, "case_brief"] and (force or not cache.get("case_brief")):
        status["case_brief"] = "generating"
        try:
            cache["case_brief"] = await generate_case_brief(
                case_name=case_name, 
                case_type=case_type, 
                description=description, 
                charge=charge,
                facts=facts,
                summary=summary
            )
            status["case_brief"] = "complete"
            results["generated"].append("case_brief")
        except Exception as e:
            status["case_brief"] = f"error: {str(e)}"
            results["errors"].append(f"case_brief: {str(e)}")
    
    # Generate theories with full context
    if section in [None, "theory"] and (force or not cache.get("theory_plaintiff")):
        status["theory_plaintiff"] = "generating"
        try:
            cache["theory_plaintiff"] = await generate_theory(
                case_name=case_name, 
                side="plaintiff", 
                description=description,
                charge=charge,
                facts=facts,
                witnesses=witnesses
            )
            status["theory_plaintiff"] = "complete"
            results["generated"].append("theory_plaintiff")
        except Exception as e:
            status["theory_plaintiff"] = f"error: {str(e)}"
            results["errors"].append(f"theory_plaintiff: {str(e)}")
    
    if section in [None, "theory"] and (force or not cache.get("theory_defense")):
        status["theory_defense"] = "generating"
        try:
            cache["theory_defense"] = await generate_theory(
                case_name=case_name, 
                side="defense", 
                description=description,
                charge=charge,
                facts=facts,
                witnesses=witnesses
            )
            status["theory_defense"] = "complete"
            results["generated"].append("theory_defense")
        except Exception as e:
            status["theory_defense"] = f"error: {str(e)}"
            results["errors"].append(f"theory_defense: {str(e)}")
    
    # Generate witness outlines with affidavit context
    if section in [None, "witnesses"]:
        is_plaintiff = "plaintiff" in human_role
        for witness in witnesses:
            wid = witness.get("id", "")
            if force or wid not in cache.get("witness_outlines", {}):
                status[f"witness_{wid}"] = "generating"
                try:
                    norm_cb = _normalize_called_by(witness.get("called_by", ""))
                    is_friendly = (
                        (norm_cb == "plaintiff" and is_plaintiff) or
                        (norm_cb == "defense" and not is_plaintiff)
                    )
                    
                    # Get affidavit excerpt for context
                    affidavit = witness.get("affidavit", "")
                    affidavit_excerpt = affidavit[:1200] if affidavit else ""
                    
                    outline_data = await generate_witness_outline(
                        witness_name=witness.get("name", ""),
                        witness_role=witness.get("role_description", ""),
                        called_by=norm_cb,
                        is_friendly=is_friendly,
                        affidavit_excerpt=affidavit_excerpt,
                        case_context=f"{case_name}: {description[:200]}"
                    )
                    
                    if "witness_outlines" not in cache:
                        cache["witness_outlines"] = {}
                    
                    cache["witness_outlines"][wid] = WitnessOutline(
                        witness_id=wid,
                        witness_name=witness.get("name", ""),
                        called_by=norm_cb,
                        direct_exam_outline=outline_data.get("direct_exam_outline", []),
                        cross_exam_outline=outline_data.get("cross_exam_outline", []),
                        key_points=outline_data.get("key_points", []),
                        potential_weaknesses=outline_data.get("potential_weaknesses", [])
                    )
                    status[f"witness_{wid}"] = "complete"
                    results["generated"].append(f"witness_{wid}")
                except Exception as e:
                    status[f"witness_{wid}"] = f"error: {str(e)}"
                    results["errors"].append(f"witness_{wid}: {str(e)}")
    
    # Generate objection playbook with case-specific context
    if section in [None, "objections"] and (force or not cache.get("objection_playbook")):
        status["objection_playbook"] = "generating"
        try:
            playbook_data = await generate_objection_playbook(
                case_name=case_name,
                case_type=case_type,
                witnesses=witnesses,
                human_role=human_role
            )
            cache["objection_playbook"] = ObjectionPlaybook(
                common_objections=playbook_data.get("common_objections", []),
                when_to_object=playbook_data.get("when_to_object", []),
                how_to_respond=playbook_data.get("how_to_respond", [])
            )
            status["objection_playbook"] = "complete"
            results["generated"].append("objection_playbook")
        except Exception as e:
            status["objection_playbook"] = f"error: {str(e)}"
            results["errors"].append(f"objection_playbook: {str(e)}")
    
    # Generate cross-exam traps
    if section in [None, "traps"] and (force or not cache.get("cross_exam_traps")):
        is_plaintiff = "plaintiff" in human_role
        adverse_witnesses = [w for w in witnesses if _normalize_called_by(w.get("called_by", "")) != ("plaintiff" if is_plaintiff else "defense")]
        traps = []
        
        for witness in adverse_witnesses[:2]:  # Limit to 2 traps
            status[f"trap_{witness.get('id')}"] = "generating"
            try:
                trap_data = await generate_cross_trap(
                    witness.get("name", ""),
                    witness.get("role_description", "")
                )
                if trap_data:
                    traps.append(CrossExamTrap(
                        witness_name=witness.get("name", ""),
                        trap_description=trap_data.get("trap_description", ""),
                        how_to_set=trap_data.get("how_to_set", ""),
                        expected_response=trap_data.get("expected_response", ""),
                        follow_up=trap_data.get("follow_up", "")
                    ))
                status[f"trap_{witness.get('id')}"] = "complete"
                results["generated"].append(f"trap_{witness.get('id')}")
            except Exception as e:
                status[f"trap_{witness.get('id')}"] = f"error: {str(e)}"
                results["errors"].append(f"trap_{witness.get('id')}: {str(e)}")
        
        if traps:
            cache["cross_exam_traps"] = traps
    
    # NOTE: Opening statements are NOT generated here. They are handled
    # exclusively by POST /generate-openings to avoid duplicate generation.
    # The frontend calls ensureOpeningsGenerated() separately.
    
    # Check if generation is complete
    is_complete = all([
        cache.get("case_brief"),
        cache.get("theory_plaintiff"),
        cache.get("theory_defense"),
        len(cache.get("witness_outlines", {})) > 0,
        cache.get("objection_playbook"),
    ])
    
    # Save to database for persistence
    cache["generation_status"] = status
    save_materials_to_db(session.case_id, cache, is_complete)
    
    return {
        "session_id": session_id,
        "results": results,
        "status": status,
        "is_complete": is_complete
    }


@router.get("/{session_id}/opening-statements")
async def get_opening_statements(session_id: str):
    """Return cached opening statement texts and their generation status."""
    session = get_session(session_id)
    if not session.case_id:
        raise HTTPException(status_code=400, detail="No case loaded for this session")
    
    cache = get_cached_materials(session)
    status = session.prep_generation_status
    
    plaintiff_name = None
    defense_name = None
    agent = session.attorney_team.get("plaintiff_opening") or session.attorneys.get("plaintiff")
    if agent:
        plaintiff_name = agent.persona.name
    agent = session.attorney_team.get("defense_opening") or session.attorneys.get("defense")
    if agent:
        defense_name = agent.persona.name
    
    text_ready = bool(cache.get("opening_plaintiff") and cache.get("opening_defense"))
    audio_p = has_cached_audio(session.case_id, "plaintiff")
    audio_d = has_cached_audio(session.case_id, "defense")
    logger.info(
        f"GET /opening-statements: case={session.case_id} text_ready={text_ready} "
        f"audio_p={audio_p} audio_d={audio_d} "
        f"opening_p_len={len(cache.get('opening_plaintiff') or '')} "
        f"opening_d_len={len(cache.get('opening_defense') or '')}"
    )
    return {
        "opening_plaintiff": cache.get("opening_plaintiff") or None,
        "opening_defense": cache.get("opening_defense") or None,
        "plaintiff_attorney_name": plaintiff_name,
        "defense_attorney_name": defense_name,
        "status": {
            "opening_plaintiff": status.get("opening_plaintiff", "pending"),
            "opening_defense": status.get("opening_defense", "pending"),
        },
        "ready": text_ready,
        "audio_plaintiff_ready": audio_p,
        "audio_defense_ready": audio_d,
    }


@router.get("/{session_id}/opening-audio/{side}")
async def get_opening_audio(session_id: str, side: str):
    """Serve cached TTS audio for an opening statement. Returns 404 if not cached."""
    if side not in ("plaintiff", "defense"):
        raise HTTPException(status_code=400, detail="side must be 'plaintiff' or 'defense'")

    session = get_session(session_id)
    if not session.case_id:
        raise HTTPException(status_code=400, detail="No case loaded for this session")

    audio_data = load_audio_cache(session.case_id, side)
    if not audio_data:
        raise HTTPException(status_code=404, detail=f"No cached audio for {side} opening")

    from fastapi.responses import Response
    return Response(
        content=audio_data,
        media_type="audio/mp3",
        headers={"Content-Disposition": f'inline; filename="opening_{side}.mp3"'},
    )


@router.post("/{session_id}/generate-opening-audio")
async def generate_opening_audio_endpoint(session_id: str):
    """Generate TTS audio for already-existing opening statement text. Skips if audio already cached."""
    session = get_session(session_id)
    if not session.case_id or not session.case_data:
        raise HTTPException(status_code=400, detail="No case loaded for this session")

    cache = get_cached_materials(session)
    generated = []

    for side in ["plaintiff", "defense"]:
        cache_key = f"opening_{side}"
        text = cache.get(cache_key)
        if not text:
            continue
        if has_cached_audio(session.case_id, side):
            continue
        team_key = f"{side}_opening"
        agent = session.attorney_team.get(team_key) or session.attorneys.get(side)
        attorney_name = agent.persona.name if agent else f"{side} attorney"
        await _generate_opening_audio(session, side, text, attorney_name)
        generated.append(side)

    return {
        "generated_audio": generated,
        "audio_plaintiff_ready": has_cached_audio(session.case_id, "plaintiff"),
        "audio_defense_ready": has_cached_audio(session.case_id, "defense"),
    }


class GenerateOpeningsRequest(BaseModel):
    side: Optional[str] = None  # "plaintiff", "defense", or None for both
    force: bool = False  # Force regeneration even if text/audio already cached


async def _generate_opening_audio(session, side: str, text: str, attorney_name: str):
    """Generate and cache TTS audio for an opening statement."""
    from ..services.tts import get_voice_for_speaker, VoicePersona, guess_gender_from_name
    from ..graph.trial_graph import Role

    if not session.tts or not text:
        return

    role = Role.ATTORNEY_PLAINTIFF if side == "plaintiff" else Role.ATTORNEY_DEFENSE

    tts_session = session.tts.get_session(session.session_id)
    if not tts_session:
        tts_session = session.tts.create_session(session.session_id)

    voice = get_voice_for_speaker(attorney_name, role)
    gender = guess_gender_from_name(attorney_name)
    gender_desc = "young woman" if gender == "female" else "young man" if gender == "male" else "young person"
    side_label = "prosecution" if side == "plaintiff" else "defense"

    persona = VoicePersona(
        voice=voice,
        priority=50,
        instructions=(
            f"You are {attorney_name}, a {gender_desc} and a passionate college student "
            f"attorney for the {side_label}. "
            f"Speak with a clear {'feminine' if gender == 'female' else 'masculine'} voice. "
            f"Show genuine emotion and conviction — you care about winning. "
            f"Vary your pace: slow down for emphasis, speed up for momentum. "
            f"Use natural pauses. Sound young, energetic, and confident — "
            f"like a brilliant college debater, not a monotone reader."
        ),
    )
    tts_session.voice_personas[role] = persona

    try:
        segment = await session.tts.generate_speech(session.session_id, text, role)
        if segment and segment.audio_data:
            save_audio_cache(session.case_id, side, segment.audio_data)
            logger.info(f"Generated and cached opening audio for {side} ({attorney_name})")
    except Exception as e:
        logger.error(f"Failed to generate opening audio for {side}: {e}")


@router.post("/{session_id}/generate-openings")
async def generate_openings(session_id: str, request: GenerateOpeningsRequest = None):
    """Generate or regenerate opening statements and their TTS audio."""
    from ..graph.trial_graph import TrialState, TrialPhase, Role
    
    session = get_session(session_id)
    if not session.case_id or not session.case_data:
        raise HTTPException(status_code=400, detail="No case loaded for this session")
    
    cache = get_cached_materials(session)
    status = session.prep_generation_status
    
    sides_to_generate = []
    req_side = request.side if request else None
    force = request.force if request else False
    if req_side:
        sides_to_generate = [req_side]
    else:
        sides_to_generate = ["plaintiff", "defense"]

    logger.info(
        f"POST /generate-openings: case={session.case_id} force={force} sides={sides_to_generate} "
        f"has_cached_p={bool(cache.get('opening_plaintiff'))} "
        f"has_cached_d={bool(cache.get('opening_defense'))} "
        f"has_audio_p={has_cached_audio(session.case_id, 'plaintiff')} "
        f"has_audio_d={has_cached_audio(session.case_id, 'defense')}"
    )
    
    temp_state = TrialState(
        session_id=session_id,
        phase=TrialPhase.OPENING,
        human_role=session.human_role,
    )
    
    results = {"generated": [], "errors": [], "cached": []}
    
    for side in sides_to_generate:
        cache_key = f"opening_{side}"
        try:
            team_key = f"{side}_opening"
            agent = session.attorney_team.get(team_key) or session.attorneys.get(side)
            if not agent:
                status[cache_key] = "error: no attorney agent configured"
                results["errors"].append(f"{cache_key}: no attorney agent configured")
                continue

            existing_text = cache.get(cache_key)
            if existing_text and not force:
                text = existing_text
                status[cache_key] = "complete"
                results["cached"].append(cache_key)
                logger.info(f"Using cached opening text for {side} ({agent.persona.name})")
            else:
                status[cache_key] = "generating"
                temp_state.current_speaker = (
                    Role.ATTORNEY_PLAINTIFF if side == "plaintiff" else Role.ATTORNEY_DEFENSE
                )
                text = agent.generate_opening(temp_state, case_data=session.case_data)
                cache[cache_key] = text
                session.prep_materials[cache_key] = text
                status[cache_key] = "complete"
                results["generated"].append(cache_key)
                logger.info(f"Generated opening statement for {side} ({agent.persona.name})")

            if force or not has_cached_audio(session.case_id, side):
                await _generate_opening_audio(session, side, text, agent.persona.name)
        except Exception as e:
            status[cache_key] = f"error: {str(e)}"
            results["errors"].append(f"{cache_key}: {str(e)}")
            logger.error(f"Failed to generate opening for {side}: {e}")
    
    cache["generation_status"] = status
    save_materials_to_db(session.case_id, cache, False)
    
    plaintiff_name = None
    defense_name = None
    agent = session.attorney_team.get("plaintiff_opening") or session.attorneys.get("plaintiff")
    if agent:
        plaintiff_name = agent.persona.name
    agent = session.attorney_team.get("defense_opening") or session.attorneys.get("defense")
    if agent:
        defense_name = agent.persona.name
    
    return {
        "opening_plaintiff": cache.get("opening_plaintiff") or None,
        "opening_defense": cache.get("opening_defense") or None,
        "plaintiff_attorney_name": plaintiff_name,
        "defense_attorney_name": defense_name,
        "status": {
            "opening_plaintiff": status.get("opening_plaintiff", "pending"),
            "opening_defense": status.get("opening_defense", "pending"),
        },
        "ready": bool(cache.get("opening_plaintiff") and cache.get("opening_defense")),
        "audio_plaintiff_ready": has_cached_audio(session.case_id, "plaintiff"),
        "audio_defense_ready": has_cached_audio(session.case_id, "defense"),
        "results": results,
    }


@router.put("/{session_id}/materials")
async def update_prep_material(session_id: str, request: UpdateMaterialRequest):
    """
    Update a specific preparation material section.
    
    Allows users to edit and save their own modifications to AI-generated content.
    Changes are persisted to both local file and database.
    """
    from datetime import datetime
    
    session = get_session(session_id)
    
    if not session.case_id:
        raise HTTPException(status_code=400, detail="No case loaded for this session")
    
    cache = get_cached_materials(session)
    
    valid_sections = [
        "case_brief", "theory_plaintiff", "theory_defense", 
        "witness_outline", "objection_playbook"
    ]
    
    if request.section not in valid_sections:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid section. Must be one of: {', '.join(valid_sections)}"
        )
    
    try:
        # Update the appropriate section
        if request.section == "case_brief":
            cache["case_brief"] = request.content
            
        elif request.section == "theory_plaintiff":
            cache["theory_plaintiff"] = request.content
            
        elif request.section == "theory_defense":
            cache["theory_defense"] = request.content
            
        elif request.section == "witness_outline":
            if not request.witness_id:
                raise HTTPException(
                    status_code=400, 
                    detail="witness_id is required for witness_outline updates"
                )
            
            # Parse the content as JSON for witness outlines
            try:
                outline_data = json.loads(request.content)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="witness_outline content must be valid JSON"
                )
            
            if "witness_outlines" not in cache:
                cache["witness_outlines"] = {}
            
            # Update the specific witness outline
            existing = cache["witness_outlines"].get(request.witness_id, {})
            if isinstance(existing, dict):
                witness_name = existing.get("witness_name", "")
                called_by = existing.get("called_by", "")
            else:
                witness_name = getattr(existing, "witness_name", "")
                called_by = getattr(existing, "called_by", "")
            
            cache["witness_outlines"][request.witness_id] = WitnessOutline(
                witness_id=request.witness_id,
                witness_name=outline_data.get("witness_name", witness_name),
                called_by=outline_data.get("called_by", called_by),
                direct_exam_outline=outline_data.get("direct_exam_outline", []),
                cross_exam_outline=outline_data.get("cross_exam_outline", []),
                key_points=outline_data.get("key_points", []),
                potential_weaknesses=outline_data.get("potential_weaknesses", [])
            )
            
        elif request.section == "objection_playbook":
            # Parse the content as JSON for objection playbook
            try:
                playbook_data = json.loads(request.content)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=400,
                    detail="objection_playbook content must be valid JSON"
                )
            
            cache["objection_playbook"] = ObjectionPlaybook(
                common_objections=playbook_data.get("common_objections", []),
                when_to_object=playbook_data.get("when_to_object", []),
                how_to_respond=playbook_data.get("how_to_respond", [])
            )
        
        # Check completeness
        is_complete = all([
            cache.get("case_brief"),
            cache.get("theory_plaintiff"),
            cache.get("theory_defense"),
            len(cache.get("witness_outlines", {})) > 0,
            cache.get("objection_playbook"),
        ])
        
        # Save to database and file
        save_materials_to_db(session.case_id, cache, is_complete)
        
        return UpdateMaterialResponse(
            success=True,
            section=request.section,
            message=f"Successfully updated {request.section}",
            updated_at=datetime.utcnow().isoformat()
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update material: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update: {str(e)}")


def get_coach_history_repo():
    """Get coach history repository."""
    if _db_available:
        try:
            from ..db.supabase_client import SupabaseCoachHistoryRepository
            return SupabaseCoachHistoryRepository()
        except Exception as e:
            logger.warning(f"Failed to create coach history repo: {e}")
    return None


def load_coach_history(session_id: str, case_id: str = None) -> List[Dict[str, str]]:
    """Load coach history from database, falling back to in-memory."""
    repo = get_coach_history_repo()
    if repo:
        try:
            db_history = repo.get_by_session(session_id, limit=20)
            if db_history:
                return [{"role": m["role"], "content": m["content"]} for m in db_history]
        except Exception as e:
            logger.warning(f"Failed to load coach history from DB: {e}")
    return []


def save_coach_message(session_id: str, role: str, content: str, case_id: str = None, context: str = None):
    """Save a coach message to database."""
    repo = get_coach_history_repo()
    if repo:
        try:
            repo.add_message(session_id, role, content, case_id, context)
        except Exception as e:
            logger.warning(f"Failed to save coach message: {e}")


@router.get("/{session_id}/coach/history")
async def get_coach_history(session_id: str):
    """Get coach chat history for this session."""
    session = get_session(session_id)
    
    # Try to load from database first
    history = load_coach_history(session_id, session.case_id)
    
    # Fall back to in-memory if no DB history
    if not history and session.coach_history:
        history = session.coach_history
    
    return {
        "session_id": session_id,
        "history": history,
        "count": len(history)
    }


@router.post("/{session_id}/coach")
async def coach_chat(session_id: str, request: CoachChatRequest):
    """Chat with the AI coach. History is persisted to database."""
    session = get_session(session_id)
    
    case_data = session.case_data or {}
    human_role = session.human_role.value if session.human_role else "attorney"
    case_id = session.case_id
    
    # Load history from database first, then in-memory fallback
    history = load_coach_history(session_id, case_id)
    if not history and session.coach_history:
        history = session.coach_history.copy()
    
    system_prompt = f"""You are an experienced mock trial coach helping a student.
Case: {case_data.get('case_name', 'Mock Trial')}
Student Role: {human_role}

Be practical, encouraging, and concise. Keep responses under 200 words."""

    persona = PersonaContext(
        role="coach",
        name="Coach",
        style="supportive",
        authority=0.8,
        formality=0.5
    )
    
    # Add user message
    history.append({"role": "user", "content": request.message})
    
    try:
        response = await asyncio.wait_for(
            call_llm_async(
                system_prompt=system_prompt,
                user_prompt=request.message,
                persona=persona,
                conversation_history=history[-6:],
                max_tokens=300,
                temperature=0.8
            ),
            timeout=30.0
        )
        
        # Save both messages to database
        save_coach_message(session_id, "user", request.message, case_id, request.context)
        save_coach_message(session_id, "assistant", response, case_id)
        
        # Also update in-memory for immediate access
        history.append({"role": "assistant", "content": response})
        session.coach_history = history[-20:]
        
        return CoachChatResponse(
            response=response,
            suggestions=[
                "How should I handle objections?",
                "Tips for cross-examination?",
                "Quiz me on the case facts"
            ]
        )
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Coach response timed out")
    except Exception as e:
        logger.error(f"Coach chat failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def get_drill_repo():
    """Get drill repository."""
    if _db_available:
        try:
            from ..db.supabase_client import SupabaseDrillRepository
            return SupabaseDrillRepository()
        except Exception as e:
            logger.warning(f"Failed to create drill repo: {e}")
    return None


def save_drill_session(session_id: str, drill_type: str, data: Dict, case_id: str = None, witness_id: str = None):
    """Save drill session to database."""
    repo = get_drill_repo()
    if repo:
        try:
            repo.create(
                session_id=session_id,
                drill_type=drill_type,
                scenario=data.get("scenario", ""),
                prompts=data.get("prompts", []),
                tips=data.get("tips", []),
                sample_responses=data.get("sample_responses", []),
                case_id=case_id,
                witness_id=witness_id,
            )
        except Exception as e:
            logger.warning(f"Failed to save drill session: {e}")


@router.get("/{session_id}/drill/history")
async def get_drill_history(session_id: str):
    """Get drill session history for this session."""
    session = get_session(session_id)
    
    repo = get_drill_repo()
    history = []
    if repo:
        try:
            history = repo.get_by_session(session_id)
        except Exception as e:
            logger.warning(f"Failed to get drill history: {e}")
    
    return {
        "session_id": session_id,
        "drills": history,
        "count": len(history)
    }


@router.post("/{session_id}/drill")
async def start_drill(session_id: str, request: DrillRequest):
    """Start a practice drill. Drill scenarios are persisted to database."""
    session = get_session(session_id)
    
    case_data = session.case_data or {}
    witnesses = case_data.get("witnesses", [])
    case_id = session.case_id
    
    drill_prompts = {
        "direct": "Create 5 direct examination questions to practice.",
        "cross": "Create 5 cross-examination questions to practice.",
        "opening": "Create an opening statement outline with 4 key points.",
        "closing": "Create a closing argument outline with 4 key points.",
        "objections": "Create 5 objectionable statements for practice recognition."
    }
    
    prompt = drill_prompts.get(request.drill_type, drill_prompts["direct"])
    
    if request.witness_id and request.drill_type in ["direct", "cross"]:
        witness = next((w for w in witnesses if w.get("id") == request.witness_id), None)
        if witness:
            prompt = f"For witness {witness.get('name')} ({witness.get('role_description', '')}): {prompt}"
    
    prompt += """

Provide JSON:
{
  "scenario": "brief description",
  "prompts": ["item1", "item2", "item3", "item4", "item5"],
  "tips": ["tip1", "tip2", "tip3"],
  "sample_responses": ["sample1", "sample2"]
}"""

    persona = PersonaContext(
        role="coach",
        name="Coach",
        style="instructive",
        authority=0.8,
        formality=0.6
    )
    
    try:
        response = await asyncio.wait_for(
            call_llm_async(
                system_prompt="You are a mock trial drill coach. Respond with valid JSON only.",
                user_prompt=prompt,
                persona=persona,
                max_tokens=500,
                temperature=0.7
            ),
            timeout=30.0
        )
        
        json_start = response.find('{')
        json_end = response.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            data = json.loads(response[json_start:json_end])
            
            # Save drill to database
            save_drill_session(
                session_id=session_id,
                drill_type=request.drill_type,
                data=data,
                case_id=case_id,
                witness_id=request.witness_id,
            )
            
            return DrillResponse(
                scenario=data.get("scenario", f"{request.drill_type.title()} Practice"),
                prompts=data.get("prompts", []),
                tips=data.get("tips", []),
                sample_responses=data.get("sample_responses", [])
            )
        
        raise HTTPException(status_code=500, detail="Failed to parse drill response")
        
    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="Drill generation timed out")
    except json.JSONDecodeError:
        raise HTTPException(status_code=500, detail="Failed to parse drill response")
    except Exception as e:
        logger.error(f"Drill generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def load_user_notes_from_db(case_id: str) -> Dict[str, str]:
    """Load user notes from database."""
    if not case_id:
        return {}
    
    db_materials = get_cached_materials_from_db(case_id)
    if db_materials:
        return db_materials.get("user_notes", {}) or {}
    return {}


def save_user_notes_to_db(case_id: str, notes: Dict[str, str]):
    """Save user notes to database alongside prep materials."""
    if not case_id:
        return
    
    repo = get_prep_repo()
    if repo:
        try:
            repo.update(case_id, user_notes=notes)
        except Exception as e:
            logger.warning(f"Failed to save user notes to DB: {e}")


@router.get("/{session_id}/notes")
async def get_user_notes(session_id: str):
    """Get user notes. Notes are loaded from database for persistence."""
    session = get_session(session_id)
    
    # Load from database first
    notes = load_user_notes_from_db(session.case_id)
    
    # Merge with in-memory notes (in-memory takes precedence for current session)
    if session.user_notes:
        notes.update(session.user_notes)
    
    return {"session_id": session_id, "notes": notes}


@router.post("/{session_id}/notes")
async def save_user_notes(session_id: str, request: UserNotesRequest):
    """Save user notes. Notes are persisted to database."""
    session = get_session(session_id)
    
    # Update in-memory first
    session.user_notes[request.section] = request.content
    
    # Load existing notes and merge
    existing_notes = load_user_notes_from_db(session.case_id)
    existing_notes[request.section] = request.content
    
    # Save to database
    save_user_notes_to_db(session.case_id, existing_notes)
    
    return {"session_id": session_id, "section": request.section, "saved": True}


@router.get("/{session_id}/status")
async def get_generation_status(session_id: str):
    """Get the status of material generation."""
    session = get_session(session_id)
    return {
        "session_id": session_id,
        "status": session.prep_generation_status
    }


# =============================================================================
# SPEECH PATTERN ANALYSIS
# =============================================================================

import re

# Common filler words in courtroom speech
FILLER_WORDS = {
    "um", "uh", "like", "you know", "so", "basically", "actually", "literally",
    "right", "okay", "well", "i mean", "kind of", "sort of", "just", "really"
}

def analyze_transcript_basic(transcript: str, duration_seconds: float) -> dict:
    """Perform basic text analysis on the transcript."""
    words = transcript.lower().split()
    word_count = len(words)
    
    # Words per minute
    wpm = int(word_count / max(duration_seconds / 60, 0.1)) if duration_seconds > 0 else 0
    
    # Filler word detection
    filler_counts = {}
    text_lower = transcript.lower()
    for filler in FILLER_WORDS:
        count = len(re.findall(r'\b' + re.escape(filler) + r'\b', text_lower))
        if count > 0:
            filler_counts[filler] = count
    
    total_fillers = sum(filler_counts.values())
    filler_percentage = (total_fillers / max(word_count, 1)) * 100
    
    # Sentence analysis
    sentences = re.split(r'[.!?]+', transcript)
    sentences = [s.strip() for s in sentences if s.strip()]
    avg_sentence_length = word_count / max(len(sentences), 1)
    
    # Rough pause detection (... or long gaps indicated by punctuation)
    pause_indicators = len(re.findall(r'\.{3,}|,\s*,|--', transcript))
    
    return {
        "word_count": word_count,
        "wpm": wpm,
        "filler_counts": filler_counts,
        "filler_percentage": filler_percentage,
        "avg_sentence_length": avg_sentence_length,
        "pause_count": pause_indicators,
        "sentence_count": len(sentences)
    }


async def generate_speech_feedback(
    transcript: str,
    basic_analysis: dict,
    context: str
) -> dict:
    """Use LLM to generate detailed speech feedback."""
    
    context_descriptions = {
        "opening_statement": "an opening statement in a mock trial",
        "closing_argument": "a closing argument in a mock trial",
        "direct_examination": "direct examination questions in a mock trial",
        "cross_examination": "cross examination questions in a mock trial",
        "objection": "making or responding to objections in a mock trial",
        "coach_question": "asking a question to a mock trial coach",
        "witness_interview": "practicing witness testimony",
        "general": "mock trial practice"
    }
    
    context_desc = context_descriptions.get(context, context_descriptions["general"])
    
    prompt = f"""Analyze this speech transcript from {context_desc} and provide detailed feedback.

TRANSCRIPT:
"{transcript}"

METRICS:
- Word count: {basic_analysis['word_count']}
- Words per minute: {basic_analysis['wpm']}
- Filler words detected: {basic_analysis['filler_counts']}
- Average sentence length: {basic_analysis['avg_sentence_length']:.1f} words
- Sentence count: {basic_analysis['sentence_count']}

Provide feedback in this JSON format:
{{
  "clarity_score": <0-100 based on clarity, coherence, and effectiveness>,
  "pacing_feedback": "<2-3 sentence assessment of speaking pace and rhythm>",
  "strengths": [
    "<specific strength observed>",
    "<another strength>"
  ],
  "areas_to_improve": [
    "<specific improvement area>",
    "<another area>"
  ],
  "delivery_tips": [
    "<actionable tip for this context>",
    "<another tip specific to mock trial>"
  ]
}}

Consider:
- For mock trial, ideal WPM is 130-160 (clear and deliberate)
- Filler words should be <3% for polished delivery
- Sentence length should vary for engagement (8-20 words average is good)
- Opening statements should be confident and narrative-driven
- Cross examination should be tight, controlled, leading questions
- Direct examination should be open-ended and witness-focused

Respond with valid JSON only."""

    persona = PersonaContext(
        role="coach",
        name="Speech Coach",
        style="constructive",
        authority=0.85,
        formality=0.7
    )
    
    try:
        result = await asyncio.wait_for(
            call_llm_async(
                system_prompt="You are an expert mock trial speech coach with years of AMTA judging experience. Provide constructive, specific feedback on delivery and communication skills. Respond with valid JSON only.",
                user_prompt=prompt,
                persona=persona,
                max_tokens=600,
                temperature=0.7
            ),
            timeout=30.0
        )
        
        json_start = result.find('{')
        json_end = result.rfind('}') + 1
        if json_start >= 0 and json_end > json_start:
            return json.loads(result[json_start:json_end])
        
        return {
            "clarity_score": 70,
            "pacing_feedback": "Analysis could not be completed. Please try again.",
            "strengths": [],
            "areas_to_improve": [],
            "delivery_tips": []
        }
    except Exception as e:
        logger.error(f"Speech feedback generation failed: {e}")
        return {
            "clarity_score": 70,
            "pacing_feedback": "Analysis could not be completed.",
            "strengths": [],
            "areas_to_improve": [],
            "delivery_tips": []
        }


def get_speech_practice_repo():
    """Get speech practice repository."""
    if _db_available:
        try:
            from ..db.supabase_client import SupabaseSpeechPracticeRepository
            return SupabaseSpeechPracticeRepository()
        except Exception as e:
            logger.warning(f"Failed to create speech practice repo: {e}")
    return None


def save_speech_practice(
    session_id: str,
    practice_type: str,
    transcript: str,
    duration_seconds: float,
    basic: Dict,
    feedback: Dict,
    case_id: str = None,
    witness_id: str = None,
):
    """Save speech practice session to database."""
    repo = get_speech_practice_repo()
    if repo:
        try:
            filler_list = [{"word": w, "count": c} for w, c in basic.get("filler_counts", {}).items()]
            repo.create(
                session_id=session_id,
                practice_type=practice_type,
                transcript=transcript,
                duration_seconds=duration_seconds,
                word_count=basic.get("word_count"),
                words_per_minute=basic.get("wpm"),
                filler_words=filler_list,
                clarity_score=feedback.get("clarity_score"),
                pacing_feedback=feedback.get("pacing_feedback"),
                strengths=feedback.get("strengths", []),
                areas_to_improve=feedback.get("areas_to_improve", []),
                delivery_tips=feedback.get("delivery_tips", []),
                case_id=case_id,
                witness_id=witness_id,
            )
        except Exception as e:
            logger.warning(f"Failed to save speech practice: {e}")


@router.get("/{session_id}/speech-practice/history")
async def get_speech_practice_history(session_id: str):
    """Get speech practice history for this session."""
    session = get_session(session_id)
    
    repo = get_speech_practice_repo()
    history = []
    if repo:
        try:
            history = repo.get_by_session(session_id)
        except Exception as e:
            logger.warning(f"Failed to get speech practice history: {e}")
    
    return {
        "session_id": session_id,
        "practices": history,
        "count": len(history)
    }


@router.post("/{session_id}/analyze-speech", response_model=SpeechAnalysisResponse)
async def analyze_speech(session_id: str, request: SpeechAnalysisRequest):
    """
    Analyze speech patterns from a transcript.
    Speech practice sessions are persisted for progress tracking.
    
    Provides feedback on:
    - Speaking pace (words per minute)
    - Filler word usage
    - Clarity and coherence
    - Context-specific delivery tips
    """
    # Validate session exists
    session = get_session(session_id)
    
    if not request.transcript.strip():
        raise HTTPException(status_code=400, detail="Transcript is empty")
    
    # Basic text analysis
    basic = analyze_transcript_basic(request.transcript, request.duration_seconds)
    
    # LLM-generated feedback
    feedback = await generate_speech_feedback(
        request.transcript,
        basic,
        request.context
    )
    
    # Save to database for progress tracking
    save_speech_practice(
        session_id=session_id,
        practice_type=request.context,
        transcript=request.transcript,
        duration_seconds=request.duration_seconds,
        basic=basic,
        feedback=feedback,
        case_id=session.case_id,
    )
    
    # Build response
    filler_words = [
        FillerWord(word=word, count=count) 
        for word, count in basic["filler_counts"].items()
    ]
    
    return SpeechAnalysisResponse(
        transcript=request.transcript,
        duration_seconds=request.duration_seconds,
        word_count=basic["word_count"],
        words_per_minute=basic["wpm"],
        filler_words=filler_words,
        filler_word_percentage=round(basic["filler_percentage"], 2),
        average_sentence_length=round(basic["avg_sentence_length"], 1),
        pauses=PauseAnalysis(
            count=basic["pause_count"],
            total_seconds=0.0  # Would need audio analysis for actual pause duration
        ),
        clarity_score=feedback.get("clarity_score", 70),
        pacing_feedback=feedback.get("pacing_feedback", ""),
        delivery_tips=feedback.get("delivery_tips", []),
        strengths=feedback.get("strengths", []),
        areas_to_improve=feedback.get("areas_to_improve", [])
    )


# =============================================================================
# PER-AGENT PREPARATION MATERIALS
# =============================================================================

_agent_prep_cache: Dict[str, Dict[str, Any]] = {}
_PREP_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".agent_prep_cache")
_agent_prep_db_ok: Optional[bool] = None  # None = untested, True/False = tested


def _get_agent_prep_repo():
    """Get agent prep repository if the DB table exists.
    
    Tests connectivity once on first call, caches the result, and never
    retries if the table is missing (circuit breaker pattern).
    """
    global _agent_prep_db_ok
    if _agent_prep_db_ok is False or not _db_available:
        return None
    try:
        repo = SupabaseAgentPrepRepository()
        if _agent_prep_db_ok is None:
            # One-time probe: raw select that will raise if the table doesn't exist
            repo.client.table("agent_prep_materials").select("id").limit(1).execute()
            _agent_prep_db_ok = True
            logger.info("agent_prep_materials DB table verified OK")
        return repo
    except Exception:
        _agent_prep_db_ok = False
        logger.warning(
            "agent_prep_materials table not available in DB — using local file cache only. "
            "To enable DB persistence, run the CREATE TABLE statement from SCHEMA_SQL "
            "in the Supabase SQL Editor."
        )
        return None


def _file_cache_path(case_id: str, agent_key: str) -> str:
    """Path for local JSON file fallback: .agent_prep_cache/<case_id>/<agent_key>.json"""
    safe_case = case_id.replace("/", "_").replace("\\", "_")
    safe_key = agent_key.replace("/", "_").replace("\\", "_")
    return os.path.join(_PREP_DIR, safe_case, f"{safe_key}.json")


def _read_file_cache(case_id: str, agent_key: str) -> Optional[Dict[str, Any]]:
    """Read agent prep from local JSON file."""
    path = _file_cache_path(case_id, agent_key)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r") as f:
            return json.load(f)
    except Exception:
        return None


def _write_file_cache(case_id: str, agent_key: str, content: Dict[str, Any]):
    """Write agent prep to local JSON file."""
    path = _file_cache_path(case_id, agent_key)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        with open(path, "w") as f:
            json.dump(content, f)
    except Exception as e:
        logger.warning(f"Failed to write file cache for {agent_key}: {e}")


def _load_all_agent_prep_for_case(case_id: str) -> Dict[str, Dict[str, Any]]:
    """Bulk-load all agent prep for a case.
    
    Tries DB first (single query), then fills gaps from file cache.
    Populates the in-memory cache so subsequent per-key lookups are instant.
    """
    result: Dict[str, Dict[str, Any]] = {}

    # 1. Try DB bulk load (single query instead of N queries)
    repo = _get_agent_prep_repo()
    if repo:
        try:
            rows = repo.get_all_for_case(case_id)
            for row in rows:
                key = row.get("agent_key", "")
                content = row.get("prep_content")
                if key and content and row.get("is_generated"):
                    result[key] = content
                    _agent_prep_cache[f"{case_id}:{key}"] = content
            if result:
                logger.info(f"Loaded {len(result)} agent preps from DB for case {case_id}")
        except Exception as e:
            logger.warning(f"DB bulk load failed for case {case_id}: {e}")

    # 2. Fill gaps from local JSON file cache
    safe_case = case_id.replace("/", "_").replace("\\", "_")
    case_dir = os.path.join(_PREP_DIR, safe_case)
    if os.path.isdir(case_dir):
        for fname in os.listdir(case_dir):
            if not fname.endswith(".json"):
                continue
            key = fname[:-5]  # strip .json
            if key in result:
                continue
            content = _read_file_cache(case_id, key)
            if content:
                result[key] = content
                _agent_prep_cache[f"{case_id}:{key}"] = content
        if result:
            file_only = [k for k in result if f"{case_id}:{k}" not in _agent_prep_cache or k not in [r.get("agent_key") for r in (rows if 'rows' in dir() else [])]]
            if file_only:
                logger.info(f"Loaded {len(file_only)} agent preps from file cache for case {case_id}")

    # 3. Check in-memory cache for anything else
    prefix = f"{case_id}:"
    for ck, cv in _agent_prep_cache.items():
        if ck.startswith(prefix):
            key = ck[len(prefix):]
            if key not in result:
                result[key] = cv

    return result


def _get_cached_agent_prep(case_id: str, agent_key: str) -> Optional[Dict[str, Any]]:
    """Check in-memory cache, then DB, then file cache for existing agent prep."""
    # Fast path: in-memory
    cache_key = f"{case_id}:{agent_key}"
    cached = _agent_prep_cache.get(cache_key)
    if cached:
        return cached

    # DB lookup
    repo = _get_agent_prep_repo()
    if repo:
        try:
            row = repo.get_by_case_and_key(case_id, agent_key)
            if row and row.get("is_generated"):
                content = row.get("prep_content") or {}
                if content:
                    _agent_prep_cache[cache_key] = content
                    logger.debug(f"Loaded agent prep from DB: {agent_key}")
                    return content
        except Exception as e:
            logger.warning(f"DB lookup failed for {agent_key}: {e}")

    # File cache fallback
    content = _read_file_cache(case_id, agent_key)
    if content:
        _agent_prep_cache[cache_key] = content
        logger.info(f"Loaded agent prep from file cache: {agent_key}")
        return content

    return None


def _save_agent_prep(case_id: str, agent_key: str, role_type: str, content: Dict[str, Any]):
    """Persist agent prep to DB, file cache, and in-memory cache."""
    cache_key = f"{case_id}:{agent_key}"
    _agent_prep_cache[cache_key] = content

    # Always write to local file so prep survives DB issues and server restarts
    _write_file_cache(case_id, agent_key, content)

    repo = _get_agent_prep_repo()
    if repo:
        try:
            repo.upsert(case_id, agent_key, role_type, content)
            logger.info(f"Saved agent prep to DB: {agent_key}")
        except Exception as e:
            logger.warning(f"Failed to persist agent prep to DB (saved to file): {e}")


async def _generate_attorney_opening_prep(case_data: Dict, side: str) -> Dict[str, Any]:
    """Generate prep for an opening attorney."""
    case_name = case_data.get("case_name", "")
    charge = case_data.get("charge", "")
    summary = case_data.get("summary", case_data.get("description", ""))
    facts = case_data.get("facts", [])
    witnesses = case_data.get("witnesses", [])
    facts_str = "\n".join(f"- {f}" for f in facts[:15]) if isinstance(facts, list) else str(facts)[:1500]
    witness_names = ", ".join(w.get("name", "") for w in witnesses[:8])
    side_label = "Prosecution" if side == "plaintiff" else "Defense"

    prompt = f"""You are preparing an opening statement strategy for the {side_label} in {case_name}.
Charge: {charge}
Summary: {summary}
Key facts:
{facts_str}
Witnesses available: {witness_names}

Generate a detailed preparation document as JSON with these fields:
- "opening_strategy": A comprehensive strategy for the opening statement (2-3 paragraphs)
- "key_themes": A list of 3-5 key themes to emphasize
- "opening_outline": A list of 5-8 bullet points for the structure of the opening
- "emotional_hooks": A list of 2-3 emotional anchors for the jury/judge
- "evidence_preview": A list of key evidence to preview in the opening

Return ONLY valid JSON."""

    result = await call_llm_async(
        system_prompt=f"You are the {side_label} Opening Attorney preparing for trial. Return ONLY valid JSON.",
        user_prompt=prompt,
        persona=PersonaContext(
            role="attorney", name=f"{side_label} Opening Attorney", style="methodical",
            authority=0.8, nervousness=0.0, formality=0.9,
        ),
        max_tokens=1500,
    )
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"opening_strategy": result, "key_themes": [], "opening_outline": []}


async def _generate_attorney_direct_cross_prep(case_data: Dict, side: str) -> Dict[str, Any]:
    """Generate prep for a direct/cross examination attorney.

    IMPORTANT: In real mock trial tournaments, attorneys do NOT use scripted questions.
    They study the case materials, develop a case theory, identify strategic themes,
    and craft questions dynamically during examination based on witness responses.
    This prep focuses on strategy, themes, and goals — NOT pre-written questions.
    """
    case_name = case_data.get("case_name", "")
    charge = case_data.get("charge", "")
    summary = case_data.get("summary", case_data.get("description", ""))
    witnesses = case_data.get("witnesses", [])
    side_label = "Prosecution" if side == "plaintiff" else "Defense"
    friendly_side = "plaintiff" if side == "plaintiff" else "defense"

    witness_details = []
    for w in witnesses[:8]:
        affidavit_excerpt = (w.get("affidavit", "") or "")[:500]
        witness_details.append(
            f"- {w.get('name', 'Unknown')} (called by {_normalize_called_by(w.get('called_by', ''))}): {affidavit_excerpt}"
        )
    witness_str = "\n".join(witness_details)

    prompt = f"""You are preparing examination strategy for the {side_label} in {case_name}.
Charge: {charge}
Summary: {summary}

Witnesses:
{witness_str}

IMPORTANT: In mock trial, attorneys do NOT use scripted questions. They develop strategic
themes and goals, then craft questions dynamically during examination based on what the
witness actually says. Do NOT include specific pre-written questions.

Generate a strategic preparation document as JSON with:
- "direct_exam_strategy": Overall strategy for examining friendly witnesses — what themes to develop, what story arc to build (2-3 paragraphs)
- "direct_exam_plans": A list of objects, one per friendly witness ({friendly_side} witnesses), each with:
  - "witness_name"
  - "goals": What key facts and themes to establish through this witness (2-3 sentences)
  - "topics_to_cover": List of 4-6 topic areas to explore (NOT specific questions), e.g. "the witness's relationship to the defendant", "timeline of events on the night in question"
  - "key_facts_to_elicit": List of 3-5 specific facts from this witness's affidavit that support the case theory
- "cross_exam_strategy": Overall strategy for cross-examining hostile witnesses — how to undermine credibility and support your theory (2-3 paragraphs)
- "cross_exam_plans": A list of objects, one per opposing witness, each with:
  - "witness_name"
  - "weaknesses_to_probe": List of 3-5 specific weaknesses, gaps, or inconsistencies in this witness's testimony/affidavit
  - "themes_to_challenge": List of 2-3 strategic themes to develop during cross (e.g. "bias toward defendant", "limited vantage point")
- "objection_strategy": When to object based on legal grounds and how to assess whether an objection is warranted (1 paragraph). Focus on recognizing genuine violations (hearsay, leading on direct, speculation) rather than objecting for disruption.

Do NOT include pre-written questions. The attorney must craft questions dynamically.

Return ONLY valid JSON."""

    result = await call_llm_async(
        system_prompt=f"You are a mock trial coach for the {side_label}. Focus on strategy and themes, NOT scripted questions. Return ONLY valid JSON.",
        user_prompt=prompt,
        persona=PersonaContext(
            role="attorney", name=f"{side_label} Exam Attorney", style="aggressive",
            authority=0.8, nervousness=0.0, formality=0.8,
        ),
        max_tokens=2000,
    )
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"direct_exam_strategy": result, "cross_exam_strategy": "", "direct_exam_plans": [], "cross_exam_plans": []}


async def _generate_attorney_closing_prep(case_data: Dict, side: str) -> Dict[str, Any]:
    """Generate prep for a closing attorney."""
    case_name = case_data.get("case_name", "")
    charge = case_data.get("charge", "")
    summary = case_data.get("summary", case_data.get("description", ""))
    facts = case_data.get("facts", [])
    facts_str = "\n".join(f"- {f}" for f in facts[:15]) if isinstance(facts, list) else str(facts)[:1500]
    side_label = "Prosecution" if side == "plaintiff" else "Defense"

    prompt = f"""You are preparing a closing argument strategy for the {side_label} in {case_name}.
Charge: {charge}
Summary: {summary}
Key facts:
{facts_str}

Generate a detailed preparation document as JSON with:
- "closing_strategy": Comprehensive closing argument strategy (2-3 paragraphs)
- "argument_structure": List of 5-7 key argument points in order
- "evidence_to_highlight": List of most compelling evidence to reference
- "rebuttal_points": List of anticipated opposing arguments and how to counter them
- "emotional_appeal": Strategy for final emotional appeal (1 paragraph)

Return ONLY valid JSON."""

    result = await call_llm_async(
        system_prompt=f"You are the {side_label} Closing Attorney preparing for trial. Return ONLY valid JSON.",
        user_prompt=prompt,
        persona=PersonaContext(
            role="attorney", name=f"{side_label} Closing Attorney", style="charismatic",
            authority=0.8, nervousness=0.0, formality=0.8,
        ),
        max_tokens=1500,
    )
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"closing_strategy": result, "argument_structure": [], "evidence_to_highlight": []}


async def _generate_witness_prep(case_data: Dict, witness: Dict) -> Dict[str, Any]:
    """Generate prep for a witness.

    IMPORTANT: In real mock trial tournaments, witnesses do NOT receive scripted
    questions or pre-written answers. They study their affidavit and case materials,
    understand the facts they personally know, and must respond naturally to whatever
    questions are asked — always grounded in their affidavit. This prep mirrors that
    realistic approach: it helps the witness understand their own knowledge, identify
    areas of strength/vulnerability, and prepare their demeanor — NOT rehearse answers.
    """
    case_name = case_data.get("case_name", "")
    witness_name = witness.get("name", "Unknown")
    called_by = _normalize_called_by(witness.get("called_by", ""))
    affidavit = (witness.get("affidavit", "") or "")[:2000]

    prompt = f"""You are coaching witness {witness_name} for a mock trial tournament in {case_name}.
Called by: {called_by}

IMPORTANT: In mock trial, witnesses do NOT receive scripted questions or answers.
They study their affidavit thoroughly and must answer whatever questions attorneys ask,
always grounded in the facts from their affidavit. They never make up information.

Affidavit:
{affidavit}

Generate a witness preparation document as JSON with:
- "case_understanding": A summary of what this witness personally knows and experienced based ONLY on their affidavit (2-3 paragraphs). What events did they witness? What is their connection to the case?
- "key_facts_known": List of 5-8 specific facts this witness can testify about (names, dates, locations, events they personally observed) — pulled directly from the affidavit
- "areas_of_strength": List of 3-5 areas where this witness's testimony is strong, credible, and well-supported by their affidavit
- "areas_of_vulnerability": List of 3-5 areas where the opposing attorney might challenge this witness — gaps in knowledge, potential inconsistencies, things the witness did NOT see or cannot confirm
- "things_witness_does_not_know": List of 3-4 topics that are outside this witness's personal knowledge (based on affidavit limits) — the witness should say "I don't know" if asked about these
- "demeanor_guidance": How this witness should present themselves given their role and personality (1 paragraph)

Do NOT include any scripted questions or pre-written answers. The witness must respond naturally.

Return ONLY valid JSON."""

    result = await call_llm_async(
        system_prompt=f"You are a mock trial coach preparing witness {witness_name}. Focus on case understanding, NOT scripted answers. Return ONLY valid JSON.",
        user_prompt=prompt,
        persona=PersonaContext(
            role="witness", name=witness_name, style="calm",
            authority=0.3, nervousness=0.3, formality=0.6,
        ),
        max_tokens=1500,
    )
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"case_understanding": result, "key_facts_known": [], "areas_of_strength": [], "areas_of_vulnerability": []}


async def _generate_judge_prep(case_data: Dict) -> Dict[str, Any]:
    """Generate prep for the judge."""
    case_name = case_data.get("case_name", "")
    charge = case_data.get("charge", "")
    case_type = case_data.get("case_type", "criminal")
    summary = case_data.get("summary", case_data.get("description", ""))

    prompt = f"""You are preparing judicial guidelines for the presiding judge in {case_name}.
Case type: {case_type}
Charge: {charge}
Summary: {summary}

Generate a detailed preparation document as JSON with:
- "ruling_guidelines": General principles for rulings in this type of case (2 paragraphs)
- "key_legal_issues": List of 3-5 legal issues likely to arise
- "evidentiary_considerations": List of evidentiary issues to watch for
- "scoring_criteria": What to evaluate in attorney and witness performance (list of 4-6 criteria)
- "jury_instructions_notes": Key instructions that apply to this case (1-2 paragraphs)

Return ONLY valid JSON."""

    result = await call_llm_async(
        system_prompt="You are the Presiding Judge preparing judicial guidelines for trial. Return ONLY valid JSON.",
        user_prompt=prompt,
        persona=PersonaContext(
            role="judge", name="Presiding Judge", style="formal",
            authority=1.0, nervousness=0.0, formality=1.0,
        ),
        max_tokens=1500,
    )
    try:
        return json.loads(result)
    except json.JSONDecodeError:
        return {"ruling_guidelines": result, "key_legal_issues": [], "scoring_criteria": []}


@router.post("/{session_id}/generate-agent-prep")
async def generate_all_agent_prep(session_id: str, force: bool = False):
    """Generate prep materials for all agents in the session.

    Args:
        force: If True, regenerate all prep materials even if cached.
               Use this after updating prep format/prompts.
    """
    session = get_session(session_id)
    if not session.case_id or not session.case_data:
        raise HTTPException(status_code=400, detail="No case loaded")

    case_id = session.case_id
    case_data = session.case_data
    witnesses = case_data.get("witnesses", [])

    agents_to_generate = []

    for side in ["plaintiff", "defense"]:
        for sub_role in ["opening", "direct_cross", "closing"]:
            key = f"{side}_{sub_role}"
            agents_to_generate.append((key, "attorney", side, sub_role))

    for w in witnesses[:10]:
        wid = w.get("id", "")
        if wid:
            agents_to_generate.append((f"witness_{wid}", "witness", None, None))

    agents_to_generate.append(("judge", "judge", None, None))

    generated = []
    skipped = []
    errors = []

    for agent_key, role_type, side, sub_role in agents_to_generate:
        if not force:
            existing = _get_cached_agent_prep(case_id, agent_key)
            if existing:
                skipped.append(agent_key)
                continue

        try:
            if role_type == "attorney":
                if sub_role == "opening":
                    content = await _generate_attorney_opening_prep(case_data, side)
                elif sub_role == "direct_cross":
                    content = await _generate_attorney_direct_cross_prep(case_data, side)
                else:
                    content = await _generate_attorney_closing_prep(case_data, side)
            elif role_type == "witness":
                wid = agent_key.replace("witness_", "", 1)
                witness = next((w for w in witnesses if w.get("id") == wid), None)
                if not witness:
                    errors.append(f"{agent_key}: witness not found")
                    continue
                content = await _generate_witness_prep(case_data, witness)
            else:
                content = await _generate_judge_prep(case_data)

            _save_agent_prep(case_id, agent_key, role_type, content)
            generated.append(agent_key)
        except Exception as e:
            logger.error(f"Failed to generate prep for {agent_key}: {e}")
            errors.append(f"{agent_key}: {str(e)}")

    return {
        "success": True,
        "generated": generated,
        "skipped": skipped,
        "errors": errors,
        "total": len(agents_to_generate),
    }


@router.get("/{session_id}/agent-prep")
async def get_all_agent_prep(session_id: str):
    """Get all agent prep materials for this session's case."""
    session = get_session(session_id)
    if not session.case_id:
        raise HTTPException(status_code=400, detail="No case loaded")

    case_id = session.case_id
    result: Dict[str, Any] = {}

    repo = _get_agent_prep_repo()
    if repo:
        try:
            rows = repo.get_all_for_case(case_id)
            for row in rows:
                result[row["agent_key"]] = {
                    "role_type": row.get("role_type"),
                    "prep_content": row.get("prep_content", {}),
                    "is_generated": row.get("is_generated", False),
                }
        except Exception:
            pass

    for cache_key, content in _agent_prep_cache.items():
        if cache_key.startswith(f"{case_id}:"):
            agent_key = cache_key.split(":", 1)[1]
            if agent_key not in result:
                role_type = "attorney"
                if agent_key.startswith("witness_"):
                    role_type = "witness"
                elif agent_key == "judge":
                    role_type = "judge"
                result[agent_key] = {
                    "role_type": role_type,
                    "prep_content": content,
                    "is_generated": True,
                }

    # Enrich with actual names from session agents
    for side in ["plaintiff", "defense"]:
        for sub in ["opening", "direct_cross", "closing"]:
            key = f"{side}_{sub}"
            if key in result:
                att = session.attorney_team.get(key) or session.attorneys.get(side)
                if att:
                    result[key]["agent_name"] = att.persona.name
                    result[key]["side"] = "Prosecution" if side == "plaintiff" else "Defense"
    for wid, w_agent in session.witnesses.items():
        wkey = f"witness_{wid}"
        if wkey in result:
            result[wkey]["agent_name"] = w_agent.persona.name
            cb = _normalize_called_by(getattr(w_agent.persona, "called_by", None) or "")
            result[wkey]["side"] = "Prosecution" if cb == "plaintiff" else "Defense"
    if "judge" in result and session.judges:
        result["judge"]["agent_name"] = session.judges[0].persona.name

    return {"case_id": case_id, "agents": result}


@router.get("/{session_id}/agent-prep/{agent_key}")
async def get_agent_prep(session_id: str, agent_key: str):
    """Get prep materials for a specific agent."""
    session = get_session(session_id)
    if not session.case_id:
        raise HTTPException(status_code=400, detail="No case loaded")

    content = _get_cached_agent_prep(session.case_id, agent_key)
    if not content:
        raise HTTPException(status_code=404, detail=f"No prep found for {agent_key}")

    return {"agent_key": agent_key, "prep_content": content, "is_generated": True}


@router.post("/{session_id}/regenerate-agent-prep/{agent_key}")
async def regenerate_agent_prep(session_id: str, agent_key: str):
    """Force-regenerate prep for a specific agent."""
    session = get_session(session_id)
    if not session.case_id or not session.case_data:
        raise HTTPException(status_code=400, detail="No case loaded")

    case_data = session.case_data
    witnesses = case_data.get("witnesses", [])

    if agent_key.startswith("witness_"):
        wid = agent_key.replace("witness_", "", 1)
        witness = next((w for w in witnesses if w.get("id") == wid), None)
        if not witness:
            raise HTTPException(status_code=404, detail=f"Witness not found: {wid}")
        content = await _generate_witness_prep(case_data, witness)
        role_type = "witness"
    elif agent_key == "judge":
        content = await _generate_judge_prep(case_data)
        role_type = "judge"
    elif "_" in agent_key:
        parts = agent_key.split("_", 1)
        side = parts[0]
        sub_role = parts[1]
        if sub_role == "opening":
            content = await _generate_attorney_opening_prep(case_data, side)
        elif sub_role in ("direct_cross", "direct-cross"):
            content = await _generate_attorney_direct_cross_prep(case_data, side)
        elif sub_role == "closing":
            content = await _generate_attorney_closing_prep(case_data, side)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown agent key: {agent_key}")
        role_type = "attorney"
    else:
        raise HTTPException(status_code=400, detail=f"Unknown agent key: {agent_key}")

    _save_agent_prep(session.case_id, agent_key, role_type, content)
    return {"agent_key": agent_key, "prep_content": content, "is_generated": True}
