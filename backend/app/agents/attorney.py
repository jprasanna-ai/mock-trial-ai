"""
Attorney Agent

Per AGENTS.md Section 2:
- Responsibilities: Openings, Direct examination, Cross examination, Objections, Closings
- Behavior: Strategic, Adversarial, Adaptive to judge persona
- Constraints: Cannot fabricate evidence, Cannot speak out of turn, Cannot score trial

Per ARCHITECTURE.md:
- Uses GPT-4.1 for all reasoning
- Text output only (TTS handled by audio pipeline)
- Must respect trial state from LangGraph
- Agents never hold API keys or call OpenAI directly
- Agents communicate with LLM via backend service (call_llm)

Per AGENTS.md - Agent → LLM Communication:
- All agent calls to GPT-4.1 go through backend service
- Agents send prompts to call_llm function
- Agents are unaware of API keys

Per SPEC.md Section 2:
- Agents are adversarial (not cooperative chatbots)
- Persona-driven behavior
"""

import json
import logging
import random
import re
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field
from enum import Enum

from ..services.llm_service import call_llm, PersonaContext
from ..services.vector_retrieval import (
    build_retrieval_context,
    retrieve_relevant_testimony,
)

_attorney_logger = logging.getLogger(__name__)

from ..graph.trial_graph import (
    TrialState,
    TrialPhase,
    Role,
    TESTIMONY_STATES,
    VALID_OBJECTION_TYPES,
    can_speak,
    validate_speaker,
    can_object,
)
from ..config import MODEL_FULL, MODEL_MID, MODEL_NANO


# =============================================================================
# PERSONA PARAMETERS
# =============================================================================

class AttorneyStyle(str, Enum):
    """Attorney advocacy styles affecting speech and strategy."""
    AGGRESSIVE = "aggressive"      # Rapid-fire, confrontational
    METHODICAL = "methodical"      # Slow, deliberate, builds case step-by-step
    CHARISMATIC = "charismatic"    # Persuasive, jury-focused
    TECHNICAL = "technical"        # Evidence-focused, precise language


class SkillLevel(str, Enum):
    """Attorney skill level affecting strategy quality."""
    NOVICE = "novice"          # Makes basic mistakes, misses opportunities
    INTERMEDIATE = "intermediate"  # Competent but predictable
    ADVANCED = "advanced"      # Strong strategy, few mistakes
    EXPERT = "expert"          # Exploits every opportunity, adapts quickly


@dataclass
class AttorneyPersona:
    """
    Persona parameters that shape attorney behavior.
    
    Per SPEC.md Section 2: Persona parameters shape reasoning, speech style,
    voice output, and scoring bias.
    """
    name: str
    side: Literal["plaintiff", "defense"]
    style: AttorneyStyle = AttorneyStyle.METHODICAL
    skill_level: SkillLevel = SkillLevel.INTERMEDIATE
    
    # Speech characteristics (for TTS persona conditioning)
    speaking_pace: float = 1.0  # 0.5 = slow, 1.5 = fast
    formality: float = 0.8     # 0.0 = casual, 1.0 = formal
    
    # Strategic tendencies
    objection_frequency: float = 0.5  # 0.0 = never objects, 1.0 = objects often
    risk_tolerance: float = 0.5       # 0.0 = conservative, 1.0 = aggressive risks
    
    # Case theory (loaded from case materials)
    case_theory: str = ""
    key_evidence: List[str] = field(default_factory=list)
    witness_goals: Dict[str, str] = field(default_factory=dict)

    # Per-agent prep materials (loaded from DB)
    prep_materials: Dict[str, Any] = field(default_factory=dict)

    # Per-agent LLM overrides (optional; None = use global config)
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    custom_system_prompt: Optional[str] = None


# =============================================================================
# ATTORNEY AGENT
# =============================================================================

class AttorneyAgent:
    """
    AI Attorney Agent using GPT-4.1.
    
    Per AGENTS.md:
    - Strategic and adversarial
    - Adaptive to judge persona
    - Cannot fabricate evidence
    - Cannot speak out of turn
    - Cannot score trial
    
    Per ARCHITECTURE.md:
    - All output is text for TTS pipeline
    - Must respect trial state from LangGraph
    """
    
    MODEL = "gpt-4.1"  # Per README.md: OpenAI GPT-4.1 for all agents
    
    def __init__(
        self,
        persona: AttorneyPersona,
    ):
        """
        Initialize attorney agent with persona.
        
        Per ARCHITECTURE.md - LLM Access:
        - Agents never hold API keys or call OpenAI directly
        - Agents communicate with LLM via backend service (call_llm)
        
        Args:
            persona: AttorneyPersona defining behavior parameters
        """
        self.persona = persona
        self.role = (
            Role.ATTORNEY_PLAINTIFF 
            if persona.side == "plaintiff" 
            else Role.ATTORNEY_DEFENSE
        )
        
        # Persona context for LLM service calls
        self._persona_context = PersonaContext(
            role="attorney",
            name=persona.name,
            style=persona.style.value,
            authority=0.7 if persona.skill_level in [SkillLevel.ADVANCED, SkillLevel.EXPERT] else 0.5,
            nervousness=0.0,
            formality=persona.formality,
            additional_traits={
                "side": persona.side,
                "skill_level": persona.skill_level.value,
            }
        )
        
        # Conversation history for context
        self._conversation_history: List[Dict[str, str]] = []
        
        # Track objections made (for strategic decisions)
        self._objections_made: int = 0
        self._objections_sustained: int = 0
    
    # =========================================================================
    # CORE GENERATION METHOD
    # =========================================================================
    
    _MAX_HISTORY = 5

    def _generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500,
        model: str = None
    ) -> str:
        """
        Generate text response via backend LLM service.
        
        Uses per-agent model/temperature/max_tokens overrides when set,
        otherwise falls back to the default or global overrides.
        """
        resolved_model = self.persona.llm_model or model or self.MODEL
        if resolved_model != MODEL_NANO and self.persona.custom_system_prompt:
            system_prompt = self.persona.custom_system_prompt + "\n\n" + system_prompt
        history = self._conversation_history[-self._MAX_HISTORY:]
        return call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            persona=self._persona_context if resolved_model != MODEL_NANO else None,
            conversation_history=history,
            temperature=self.persona.llm_temperature if self.persona.llm_temperature is not None else temperature,
            max_tokens=self.persona.llm_max_tokens if self.persona.llm_max_tokens is not None else max_tokens,
            model=resolved_model,
        )
    
    def _build_system_prompt(self, context: str) -> str:
        """
        Build system prompt incorporating persona parameters.
        
        Per AGENTS.md: Behavior is persona-driven.
        """
        style_instructions = {
            AttorneyStyle.AGGRESSIVE: (
                "You are aggressive and confrontational. "
                "Use rapid-fire questions. Challenge witnesses directly. "
                "Maintain pressure throughout."
            ),
            AttorneyStyle.METHODICAL: (
                "You are methodical and deliberate. "
                "Build your case step by step. "
                "Ensure each point is clearly established before moving on."
            ),
            AttorneyStyle.CHARISMATIC: (
                "You are charismatic and persuasive. "
                "Connect with the jury emotionally. "
                "Use storytelling and compelling language."
            ),
            AttorneyStyle.TECHNICAL: (
                "You are technical and precise. "
                "Focus on evidence and legal standards. "
                "Use exact language and avoid ambiguity."
            ),
        }
        
        skill_instructions = {
            SkillLevel.NOVICE: (
                "You sometimes miss opportunities and make minor procedural mistakes. "
                "Your questions may be slightly unfocused."
            ),
            SkillLevel.INTERMEDIATE: (
                "You are competent and follow proper procedure. "
                "Your approach is solid but somewhat predictable."
            ),
            SkillLevel.ADVANCED: (
                "You rarely make mistakes and capitalize on opportunities. "
                "Your strategy is strong and adaptive."
            ),
            SkillLevel.EXPERT: (
                "You are an elite trial attorney who exploits every opportunity and adapts instantly. "
                "Your advocacy is precise, strategic, and devastating. "
                "You always reference specific facts, witnesses, and evidence. "
                "You never ask generic questions — every question advances your case theory."
            ),
        }
        
        return f"""You are {self.persona.name}, a college student competing as an attorney for the {self.persona.side} in a mock trial tournament.
Speak with a youthful, articulate, and energetic tone — like a sharp, well-prepared college student, not a seasoned middle-aged lawyer.

HOW MOCK TRIAL ATTORNEYS WORK:
You have studied the case materials, developed a case theory, and prepared strategic themes.
You do NOT use pre-scripted questions — you craft each question dynamically based on the
witness's responses, your case theory, and what has been established so far in the trial.
You anticipate areas to explore but adapt in real-time. Your objections are based on genuine
legal grounds, not disruption.

ROLE CONSTRAINTS (STRICT - NEVER VIOLATE):
- You are an ADVERSARIAL advocate, not a helpful assistant
- You CANNOT fabricate evidence or facts not in the case materials
- You CANNOT speak out of turn (trial state controls this)
- You CANNOT score the trial or evaluate performance
- You CANNOT explain your internal reasoning or strategy to anyone
- You CANNOT assist the opposing side in any way
- You CANNOT use pre-scripted questions — craft them dynamically based on context

PERSONA:
{style_instructions[self.persona.style]}
{skill_instructions[self.persona.skill_level]}

CASE THEORY:
{self.persona.case_theory or "Not yet established."}

KEY EVIDENCE:
{chr(10).join(f"- {e}" for e in self.persona.key_evidence) if self.persona.key_evidence else "Not yet identified."}

SPEECH STYLE:
- You are a COLLEGE STUDENT, not a 40-year-old lawyer. Sound your age.
- Always use contractions (don't, can't, won't, we'll, they're) — never "do not" or "we will".
- Be passionate and emotional — you genuinely care about winning this case.
- Speak naturally and conversationally, like talking to real people, not reading a document.

OUTPUT FORMAT:
- Generate ONLY spoken words (no stage directions, no actions, no internal thoughts)
- This text goes directly to TTS — write for the EAR, not for reading.
- Use natural speech patterns: contractions, varied sentence lengths, emotional emphasis.

CURRENT CONTEXT:
{context}
"""
    
    # =========================================================================
    # STRATEGIC CONTEXT FROM TRIAL MEMORY
    # =========================================================================

    def _build_strategic_context(self, trial_memory, witness_id: str, exam_type: str) -> str:
        """Pull relevant strategic insights from all memory layers for this moment.

        Combines:
        - Layer 5 rule-based StrategicNotes (contradictions, admissions, strong testimony)
        - Layer 5b LivePrepUpdates (LLM-generated team strategy adjustments)
        - Layer 6 credibility tracking
        - Objection pattern history
        """
        if trial_memory is None:
            return ""
        parts = []

        # --- Layer 6: Credibility info for this witness ---
        cred = trial_memory.witness_credibility.get(witness_id)
        if cred and (cred.consistency_issues or cred.key_admissions or cred.evasive_answers):
            parts.append(cred.format_for_prompt())

        # --- Layer 5: Rule-based strategic notes ---
        notes = trial_memory.strategic_notes.get(self.persona.side)
        if notes:
            relevant_contradictions = [
                c for c in notes.contradictions_found
                if c.get("witness") == witness_id or c.get("cross_witness")
            ]
            if relevant_contradictions:
                lines = "\n".join(
                    f"  - {c.get('detail', '')}" for c in relevant_contradictions[:5]
                )
                parts.append(f"CONTRADICTIONS TO EXPLOIT:\n{lines}")

            if notes.key_admissions:
                lines = "\n".join(
                    f"  - {a.get('witness', '?')}: {a.get('detail', '')}"
                    for a in notes.key_admissions[:5]
                )
                parts.append(f"KEY ADMISSIONS OBTAINED:\n{lines}")

            if notes.strong_testimony:
                lines = "\n".join(
                    f"  - {s.get('witness', '?')}: {s.get('detail', '')}"
                    for s in notes.strong_testimony[:5]
                )
                parts.append(f"STRONG TESTIMONY FOR YOUR CASE:\n{lines}")

        # --- Objection patterns for this witness ---
        witness_objs = trial_memory.get_objections_for_witness(witness_id)
        if witness_objs:
            sustained_types = [o.objection_type for o in witness_objs if o.sustained]
            overruled_types = [o.objection_type for o in witness_objs if not o.sustained]
            if sustained_types:
                parts.append(f"OBJECTIONS SUSTAINED (avoid these patterns): {', '.join(sustained_types)}")
            if overruled_types:
                parts.append(f"OBJECTIONS OVERRULED (safe to continue): {', '.join(overruled_types)}")

        # --- Layer 5b: Live team prep updates (LLM-generated strategic intelligence) ---
        live_prep_context = trial_memory.build_live_prep_context(self.persona.side)
        if live_prep_context:
            parts.append(live_prep_context)

        # --- Layer 5c: Team shared memory (intra-team knowledge) ---
        team_shared_context = trial_memory.build_team_shared_context_for_attorney(self.persona.side)
        if team_shared_context:
            parts.append(team_shared_context)

        if not parts:
            return ""
        return "\n=== STRATEGIC INTELLIGENCE ===\n" + "\n\n".join(parts) + "\n=== END STRATEGIC INTELLIGENCE ===\n"

    # =========================================================================
    # PREP MATERIALS INJECTION
    # =========================================================================

    def _format_prep_for_prompt(self) -> str:
        """Format agent's prep materials into a prompt section.

        Focuses on strategy, themes, and goals — NOT scripted questions.
        In real mock trial, attorneys craft questions dynamically based on
        witness responses and case theory, not from a pre-written script.
        """
        prep = self.persona.prep_materials
        if not prep:
            return ""
        parts = ["\n=== YOUR STRATEGIC PREPARATION ==="]

        # Strategy sections (string paragraphs)
        for strategy_key in [
            "direct_exam_strategy", "cross_exam_strategy",
            "closing_strategy", "objection_strategy",
            "opening_strategy", "opening_framework",
        ]:
            if prep.get(strategy_key) and isinstance(prep[strategy_key], str):
                label = strategy_key.replace("_", " ").title()
                parts.append(f"{label}:\n{prep[strategy_key]}")

        # Examination plans — include goals, themes, and weaknesses but NOT scripted questions
        for plan_key in ["direct_exam_plans", "cross_exam_plans"]:
            plans = prep.get(plan_key, [])
            if not isinstance(plans, list):
                continue
            label = "Direct Exam" if "direct" in plan_key else "Cross Exam"
            for plan in plans[:6]:
                if isinstance(plan, dict):
                    wname = plan.get("witness_name", "Unknown")
                    plan_parts = [f"  {label} — {wname}:"]
                    if plan.get("goals"):
                        plan_parts.append(f"    Goals: {plan['goals']}")
                    if plan.get("topics_to_cover"):
                        topics = plan["topics_to_cover"]
                        plan_parts.append("    Topics: " + ", ".join(topics[:6]) if isinstance(topics, list) else f"    Topics: {topics}")
                    if plan.get("key_facts_to_elicit"):
                        facts = plan["key_facts_to_elicit"]
                        plan_parts.append("    Key facts: " + ", ".join(f for f in facts[:5]) if isinstance(facts, list) else f"    Key facts: {facts}")
                    if plan.get("weaknesses_to_probe"):
                        weaknesses = plan["weaknesses_to_probe"]
                        plan_parts.append("    Weaknesses: " + "; ".join(w for w in weaknesses[:5]) if isinstance(weaknesses, list) else f"    Weaknesses: {weaknesses}")
                    if plan.get("themes_to_challenge"):
                        themes = plan["themes_to_challenge"]
                        plan_parts.append("    Themes: " + "; ".join(t for t in themes[:3]) if isinstance(themes, list) else f"    Themes: {themes}")
                    parts.append("\n".join(plan_parts))

        # Argument structure, evidence, rebuttal points (for closing)
        for list_key in [
            "argument_structure", "evidence_to_highlight",
            "rebuttal_points", "key_themes",
        ]:
            items = prep.get(list_key, [])
            if isinstance(items, list) and items:
                label = list_key.replace("_", " ").title()
                formatted = "\n".join(f"  - {v}" if isinstance(v, str) else f"  - {json.dumps(v)}" for v in items[:8])
                parts.append(f"{label}:\n{formatted}")

        # Emotional appeal (closing)
        if prep.get("emotional_appeal") and isinstance(prep["emotional_appeal"], str):
            parts.append(f"Emotional Appeal Strategy:\n{prep['emotional_appeal']}")

        parts.append("=== END STRATEGIC PREPARATION ===\n")
        return "\n".join(parts)

    # =========================================================================
    # CASE CONTEXT BUILDER
    # =========================================================================
    
    def _build_case_context(self, case_data: dict = None) -> str:
        """Build case-specific context section for prompts from loaded case materials."""
        if not case_data:
            return ""
        
        parts = []
        
        case_name = case_data.get("case_name", "")
        if case_name:
            parts.append(f"CASE: {case_name}")
        
        case_type = case_data.get("case_type", "")
        charge = case_data.get("charge", "")
        if charge:
            parts.append(f"CHARGE/CLAIM: {charge}")
        elif case_type:
            parts.append(f"CASE TYPE: {case_type}")
        
        description = case_data.get("description", "")
        summary = case_data.get("summary", "")
        if summary:
            parts.append(f"CASE SUMMARY:\n{summary}")
        elif description:
            parts.append(f"CASE DESCRIPTION:\n{description}")
        
        facts = case_data.get("facts", [])
        if facts:
            fact_lines = []
            for f in facts[:15]:
                text = (f.get("content") or f.get("text") or str(f)) if isinstance(f, dict) else str(f)
                fact_type = f.get("fact_type", "") if isinstance(f, dict) else ""
                prefix = f"[{fact_type}] " if fact_type else ""
                fact_lines.append(f"  - {prefix}{text}")
            parts.append(f"KEY FACTS:\n" + "\n".join(fact_lines))
        
        witnesses = case_data.get("witnesses", [])
        if witnesses:
            pros_witnesses = []
            def_witnesses = []
            either_witnesses = []
            for w in witnesses:
                name = w.get("name", "Unknown")
                role_desc = w.get("role_description", w.get("role", w.get("description", "")))
                cb = (w.get("called_by") or w.get("side") or "").lower()
                entry = f"  - {name}" + (f": {role_desc}" if role_desc else "")
                if cb in ("prosecution", "plaintiff"):
                    pros_witnesses.append(entry)
                elif cb == "defense":
                    def_witnesses.append(entry)
                else:
                    either_witnesses.append(entry)

            if pros_witnesses:
                parts.append(f"PROSECUTION/PLAINTIFF WITNESSES:\n" + "\n".join(pros_witnesses))
            if def_witnesses:
                parts.append(f"DEFENSE WITNESSES:\n" + "\n".join(def_witnesses))
            if either_witnesses:
                parts.append(f"EITHER-SIDE WITNESSES (callable by both):\n" + "\n".join(either_witnesses))
        
        exhibits = case_data.get("exhibits", [])
        if exhibits:
            exhibit_lines = []
            for e in exhibits[:10]:
                title = e.get("title", e.get("id", "")) if isinstance(e, dict) else str(e)
                desc = e.get("description", "") if isinstance(e, dict) else ""
                exhibit_lines.append(f"  - {title}" + (f": {desc}" if desc else ""))
            parts.append(f"EXHIBITS:\n" + "\n".join(exhibit_lines))
        
        stipulations = case_data.get("stipulations", [])
        if stipulations:
            stip_lines = [f"  - {s}" if isinstance(s, str) else f"  - {s.get('text', s)}" for s in stipulations[:8]]
            parts.append(f"STIPULATIONS:\n" + "\n".join(stip_lines))
        
        legal_standards = case_data.get("legal_standards", [])
        if legal_standards:
            std_lines = [f"  - {s}" if isinstance(s, str) else f"  - {s.get('text', s)}" for s in legal_standards[:5]]
            parts.append(f"APPLICABLE LEGAL STANDARDS:\n" + "\n".join(std_lines))
        
        special_instructions = case_data.get("special_instructions", [])
        if special_instructions:
            si_lines = []
            for si in special_instructions[:10]:
                if isinstance(si, dict):
                    title = si.get("title", "")
                    content = si.get("content", "")
                    si_lines.append(f"  {si.get('number', '-')}. {title}: {content}" if title else f"  {si.get('number', '-')}. {content}")
                else:
                    si_lines.append(f"  - {si}")
            parts.append("SPECIAL INSTRUCTIONS (binding rules):\n" + "\n".join(si_lines))
        
        jury_instructions = case_data.get("jury_instructions", [])
        if jury_instructions:
            ji_lines = []
            for ji in jury_instructions[:10]:
                if isinstance(ji, dict):
                    title = ji.get("title", "")
                    content = ji.get("content", "")
                    ji_lines.append(f"  Instruction {ji.get('number', '-')}: {title} — {content}" if title else f"  Instruction {ji.get('number', '-')}: {content}")
                else:
                    ji_lines.append(f"  - {ji}")
            parts.append("JURY INSTRUCTIONS (elements you must address):\n" + "\n".join(ji_lines))
        
        motions = case_data.get("motions_in_limine", [])
        if motions:
            mot_lines = []
            for m in motions:
                if isinstance(m, dict):
                    title = m.get("title", "")
                    ruling = m.get("ruling", "")
                    mot_lines.append(f"  Motion {m.get('letter', '?')}: {title} — RULING: {ruling}")
                else:
                    mot_lines.append(f"  - {m}")
            parts.append("MOTIONS IN LIMINE (excluded/limited evidence — DO NOT violate):\n" + "\n".join(mot_lines))
        
        relevant_law = case_data.get("relevant_law", {})
        if isinstance(relevant_law, dict):
            statutes = relevant_law.get("statutes", [])
            if statutes:
                stat_lines = []
                for s in statutes[:5]:
                    if isinstance(s, dict):
                        stat_lines.append(f"  - {s.get('title', '')}: {s.get('content', '')[:200]}")
                    else:
                        stat_lines.append(f"  - {s}")
                parts.append("RELEVANT STATUTES:\n" + "\n".join(stat_lines))
            
            cases = relevant_law.get("cases", [])
            if cases:
                case_lines = []
                for c in cases[:5]:
                    if isinstance(c, dict):
                        case_lines.append(f"  - {c.get('citation', '')}: {c.get('content', '')[:200]}")
                    else:
                        case_lines.append(f"  - {c}")
                parts.append("RELEVANT CASE LAW:\n" + "\n".join(case_lines))
        
        restrictions = case_data.get("witness_calling_restrictions", {})
        if isinstance(restrictions, dict) and any(restrictions.values()):
            r_lines = []
            for side_key, label in [("prosecution_only", "Prosecution only"), ("defense_only", "Defense only"), ("either_side", "Either side")]:
                names = restrictions.get(side_key, [])
                if names:
                    r_lines.append(f"  {label}: {', '.join(names)}")
            parts.append("WITNESS CALLING RESTRICTIONS:\n" + "\n".join(r_lines))
        
        return "\n\n".join(parts) if parts else ""
    
    # =========================================================================
    # TRIAL STATE VALIDATION
    # =========================================================================
    
    def can_act(self, state: TrialState) -> tuple[bool, Optional[str]]:
        """
        Check if attorney can act in current trial state.
        
        Per ARCHITECTURE.md: LangGraph is single source of truth.
        Attorney cannot bypass the graph.
        """
        return validate_speaker(state, self.role)
    
    def _validate_state_for_action(
        self,
        state: TrialState,
        required_phases: Optional[set] = None
    ) -> None:
        """
        Validate trial state before taking action.
        
        Raises:
            ValueError: If state doesn't permit action
        """
        valid, reason = self.can_act(state)
        if not valid:
            raise ValueError(f"Cannot act: {reason}")
        
        if required_phases and state.phase not in required_phases:
            raise ValueError(
                f"Action not permitted in {state.phase.value}. "
                f"Required phases: {[p.value for p in required_phases]}"
            )
    
    # =========================================================================
    # OPENING STATEMENT
    # =========================================================================
    
    def generate_opening(self, state: TrialState, case_data: dict = None) -> str:
        """
        Generate opening statement.
        
        Per AGENTS.md: Attorney responsibilities include openings.
        Per SCORING.md: Opening clarity is scored 1-10.
        
        Args:
            state: Current trial state
            case_data: Case materials (facts, witnesses, exhibits, charge, etc.)
            
        Returns:
            Opening statement text for TTS
        """
        self._validate_state_for_action(state, {TrialPhase.OPENING})
        
        case_section = self._build_case_context(case_data)
        prep_section = self._format_prep_for_prompt()

        context = f"""
Phase: Opening Statement
Your role: {self.persona.side.title()} Attorney
Task: Deliver your opening statement to the court.

{case_section}
{prep_section}

Guidelines:
- Reference the SPECIFIC facts, witnesses, and evidence from this case
- Tell the story of THIS case using the actual names, dates, and events
- Preview what your witnesses will testify about BY NAME
- Reference specific exhibits you will introduce
- Do NOT argue - opening is for previewing, not persuading
- Address the judge as "Your Honor" and the jury as "members of the jury"
- Do NOT be generic. Every sentence should relate to this specific case.

CRITICAL — HOW TO WRITE THIS (this text will be spoken aloud via TTS):
- Write EXACTLY how a passionate college student would TALK, not how they'd write an essay.
- Use contractions naturally: "doesn't", "we'll", "they're", "you'll" — nobody says "does not" when speaking.
- NEVER write like a legal brief. No stuffy phrasing like "the evidence will show" repeated five times.
- Use emotional language: "This is heartbreaking." "Think about that for a moment." "That changes everything."
- Vary your energy: start sentences differently, mix short punches with flowing narrative.
- Include natural speech markers: "Look," "Here's the thing," "And that's exactly why..."
- Show you CARE about the case. You're not reading a report — you're fighting for someone.
- Start with a hook that grabs attention. End with a powerful, memorable line.
- Keep it conversational and direct. Imagine you're telling a friend the most important story of your life.
"""
        
        system_prompt = self._build_system_prompt(context)
        user_prompt = (
            "Deliver your opening statement now. Talk like a real passionate college student in a courtroom — "
            "not a textbook. Reference actual witnesses, evidence, and facts from THIS case. "
            "Use contractions, emotional language, and natural speech rhythms. "
            "This is spoken aloud, so write for the ear, not the eye."
        )
        
        return self._generate(
            system_prompt,
            user_prompt,
            temperature=0.7,
            max_tokens=2000
        )
    
    # =========================================================================
    # DIRECT EXAMINATION
    # =========================================================================
    
    def generate_direct_question(
        self,
        state: TrialState,
        witness_name: str,
        witness_affidavit: str,
        prior_testimony: List[Dict[str, str]],
        trial_memory=None,
    ) -> str:
        """
        Generate next question for direct examination.
        
        Per AGENTS.md:
        - Attorney: Direct examination
        - Cannot fabricate evidence
        
        Args:
            state: Current trial state
            witness_name: Name of witness on stand
            witness_affidavit: Witness affidavit content
            prior_testimony: List of prior Q&A in this examination
            trial_memory: Optional TrialMemory for strategic context
            
        Returns:
            Question text for TTS
        """
        self._validate_state_for_action(state, {TrialPhase.DIRECT, TrialPhase.REDIRECT})
        
        # Format prior testimony for context
        prior_qa = "\n".join([
            f"Q: {qa['question']}\nA: {qa['answer']}"
            for qa in prior_testimony[-5:]  # Last 5 Q&A pairs
        ]) if prior_testimony else "No prior questions yet."
        
        witness_goal = self.persona.witness_goals.get(witness_name, "Establish relevant facts.")
        
        prep_section = self._format_prep_for_prompt()

        # Derive witness_id for strategic context
        witness_id = getattr(state, "current_witness_id", None) or ""
        strategic_section = ""
        if trial_memory:
            strategic_section = self._build_strategic_context(trial_memory, witness_id, "direct")

        # Vector retrieval: get targeted affidavit passages instead of full dump
        retrieval_query = f"{witness_goal} {prior_qa[-200:]}" if prior_testimony else witness_goal
        retrieval_section = build_retrieval_context(witness_id, retrieval_query) if witness_id else ""
        if retrieval_section:
            _attorney_logger.debug(f"Direct exam: using vector-retrieved context for {witness_name}")
            affidavit_display = f"{retrieval_section}\n\nFULL AFFIDAVIT REFERENCE:\n{witness_affidavit[:1500]}"
        else:
            affidavit_display = witness_affidavit

        context = f"""
Phase: {"Direct" if state.phase == TrialPhase.DIRECT else "Redirect"} Examination
Witness: {witness_name}
Your goal with this witness: {witness_goal}

WITNESS AFFIDAVIT (what the witness knows):
{affidavit_display}

PRIOR TESTIMONY IN THIS EXAMINATION:
{prior_qa}
{prep_section}
{strategic_section}
RULES FOR DIRECT EXAMINATION:
- Ask OPEN-ENDED questions (who, what, when, where, why, how)
- Do NOT ask leading questions (opposing counsel will object)
- Build testimony step by step, eliciting SPECIFIC facts from the affidavit
- Only elicit facts from the affidavit — but ask about SPECIFIC names, dates, events, locations
- You CANNOT make the witness say things not in their affidavit
- NEVER ask generic questions like "what happened?" — ask targeted questions about specific events in the case
- Each question should advance a strategic point in your case theory
"""
        
        system_prompt = self._build_system_prompt(context)
        
        if state.phase == TrialPhase.REDIRECT:
            user_prompt = (
                "Ask your next redirect question. "
                "You may only address matters raised on cross-examination."
            )
        else:
            user_prompt = "Ask your next direct examination question."
        
        return self._generate(
            system_prompt,
            user_prompt,
            temperature=0.7,
            max_tokens=300,
            model=MODEL_MID
        )
    
    # =========================================================================
    # CROSS EXAMINATION
    # =========================================================================
    
    def generate_cross_question(
        self,
        state: TrialState,
        witness_name: str,
        witness_affidavit: str,
        direct_testimony: List[Dict[str, str]],
        prior_cross: List[Dict[str, str]],
        trial_memory=None,
    ) -> str:
        """
        Generate next question for cross examination.
        
        Per AGENTS.md:
        - Attorney: Cross examination (adversarial, strategic)
        - Cannot fabricate evidence
        
        Args:
            state: Current trial state
            witness_name: Name of witness on stand
            witness_affidavit: Witness affidavit content
            direct_testimony: Testimony from direct examination
            prior_cross: Prior Q&A in this cross examination
            trial_memory: Optional TrialMemory for strategic context
            
        Returns:
            Question text for TTS
        """
        self._validate_state_for_action(state, {TrialPhase.CROSS, TrialPhase.RECROSS})
        
        # Format testimonies
        direct_qa = "\n".join([
            f"Q: {qa['question']}\nA: {qa['answer']}"
            for qa in direct_testimony[-8:]
        ]) if direct_testimony else "No direct testimony available."
        
        prior_qa = "\n".join([
            f"Q: {qa['question']}\nA: {qa['answer']}"
            for qa in prior_cross[-5:]
        ]) if prior_cross else "No prior cross questions yet."
        
        prep_section = self._format_prep_for_prompt()

        witness_id = getattr(state, "current_witness_id", None) or ""
        strategic_section = ""
        if trial_memory:
            strategic_section = self._build_strategic_context(trial_memory, witness_id, "cross")

        # Vector retrieval: find weak points to exploit
        cross_query = f"inconsistencies weaknesses {witness_name} {direct_qa[-300:]}"
        retrieval_section = build_retrieval_context(witness_id, cross_query) if witness_id else ""
        if retrieval_section:
            _attorney_logger.debug(f"Cross exam: using vector-retrieved context for {witness_name}")
            affidavit_display = f"{retrieval_section}\n\nFULL AFFIDAVIT REFERENCE:\n{witness_affidavit[:1500]}"
        else:
            affidavit_display = witness_affidavit

        context = f"""
Phase: {"Cross" if state.phase == TrialPhase.CROSS else "Recross"} Examination
Witness: {witness_name} (opposing witness)
Your goal: Undermine their testimony, expose weaknesses, support YOUR case theory

WITNESS AFFIDAVIT:
{affidavit_display}

DIRECT EXAMINATION TESTIMONY (what they said):
{direct_qa}

YOUR PRIOR CROSS QUESTIONS:
{prior_qa}
{prep_section}
{strategic_section}
RULES FOR CROSS EXAMINATION:
- You SHOULD ask leading questions (statements with "isn't that right?" or "correct?")
- Control the witness — don't let them explain
- Short, pointed questions that reference SPECIFIC facts from the affidavit and testimony
- Attack credibility, perception, memory, bias using SPECIFIC inconsistencies
- Do NOT ask questions you don't know the answer to
- Do NOT let the witness repeat their direct testimony
- Exploit specific gaps between the affidavit and their testimony
- Every question should undermine a specific point or establish a fact for YOUR theory
"""
        
        system_prompt = self._build_system_prompt(context)
        
        if state.phase == TrialPhase.RECROSS:
            user_prompt = (
                "Ask your next recross question. "
                "You may only address matters raised on redirect."
            )
        else:
            user_prompt = "Ask your next cross-examination question."
        
        return self._generate(
            system_prompt,
            user_prompt,
            temperature=0.8,
            max_tokens=250,
            model=MODEL_MID
        )
    
    # =========================================================================
    # CLOSING ARGUMENT
    # =========================================================================
    
    def generate_closing(
        self,
        state: TrialState,
        trial_transcript: List[Dict[str, Any]],
        trial_memory=None,
    ) -> str:
        """
        Generate closing argument.
        
        Per AGENTS.md: Attorney responsibilities include closings.
        Per SCORING.md: Case theory consistency scored 1-10.
        
        Args:
            state: Current trial state
            trial_transcript: Full trial transcript
            trial_memory: Optional TrialMemory for strategic closing context
            
        Returns:
            Closing argument text for TTS
        """
        self._validate_state_for_action(state, {TrialPhase.CLOSING})
        
        # Use trial memory for closing context when available; fall back to transcript summary
        if trial_memory:
            testimony_summary = trial_memory.build_closing_context(self.persona.side)
            if len(testimony_summary) < 200:
                testimony_summary += "\n\n" + self._summarize_transcript_for_closing(trial_transcript)
        else:
            testimony_summary = self._summarize_transcript_for_closing(trial_transcript)

        # Vector retrieval: pull the most relevant testimony quotes for the closing
        case_theory = self.persona.case_theory or ""
        closing_query = f"{case_theory} {self.persona.side} closing argument key evidence"
        retrieved_testimony = retrieve_relevant_testimony(closing_query, top_k=10)
        if retrieved_testimony:
            _attorney_logger.info(f"Closing: retrieved {len(retrieved_testimony)} testimony quotes from Pinecone")
            numbered = "\n".join(f"{i+1}. {t}" for i, t in enumerate(retrieved_testimony))
            testimony_summary += f"\n\nSEMANTICALLY RETRIEVED TESTIMONY QUOTES (most relevant to your theory):\n{numbered}"

        # Live strategic prep accumulated during the entire trial
        live_prep_section = ""
        if trial_memory:
            live_prep_section = trial_memory.build_live_prep_context(self.persona.side)

        prep_section = self._format_prep_for_prompt()

        context = f"""
Phase: Closing Argument
Your role: {self.persona.side.title()} Attorney
Task: Deliver your closing argument to the jury.

KEY TESTIMONY AND EVIDENCE FROM TRIAL:
{testimony_summary}
{prep_section}
{live_prep_section}

YOUR CASE THEORY:
{self.persona.case_theory or "Argue based on the evidence presented."}

RULES FOR CLOSING:
- NOW you may argue and persuade
- You MUST reference specific witness testimony by NAME — quote what they actually said
- Connect specific evidence and exhibits to your theory
- Address weaknesses in your case head-on and explain them away
- Explain why the other side's case fails, referencing their specific witnesses and testimony
- Tell the jury what verdict to return and why, citing the legal standard
- NEVER be generic or vague. Every argument must cite a specific witness, exhibit, or fact from the trial.

CRITICAL — HOW TO WRITE THIS (spoken aloud via TTS):
- Write EXACTLY how a fired-up college student would SPEAK in a closing — not a legal essay.
- Use contractions naturally. Nobody says "did not" in passionate speech — say "didn't".
- Show REAL emotion: frustration, conviction, urgency. "This matters." "You heard it yourself."
- QUOTE WITNESSES: "Remember when [witness name] told you [specific thing]? That's the key."
- Use rhetorical questions: "So what does that tell us?" "How can we ignore that?"
- Vary energy: build to crescendos, then drop to quiet intensity for key moments.
- Include conversational markers: "Look," "Think about this," "And here's what really matters..."
- End with your most powerful, emotional argument. Make the jury feel it, not just understand it.
"""
        
        system_prompt = self._build_system_prompt(context)
        user_prompt = (
            "Deliver your closing argument now. You MUST reference at least 3 specific witnesses by name "
            "and quote or paraphrase their actual testimony. Connect each witness's testimony to your case theory. "
            "Speak like a passionate college student making the most important argument of your life. "
            "This is spoken aloud — write for the ear, not the page."
        )
        
        return self._generate(
            system_prompt,
            user_prompt,
            temperature=0.7,
            max_tokens=2000
        )
    
    def _summarize_transcript_for_closing(
        self,
        transcript: List[Dict[str, Any]],
        max_entries: int = 30
    ) -> str:
        """
        Summarize trial transcript for closing argument context.
        
        Uses a multi-pass approach to extract relevant testimony:
        1. Extract testimony from direct/cross examinations
        2. Prioritize testimony from our own witnesses and cross of opposing witnesses
        3. Include key moments (objections, rulings)
        4. Summarize long entries using LLM if needed
        
        Args:
            transcript: Full trial transcript
            max_entries: Maximum entries to include in summary
            
        Returns:
            Formatted summary of key testimony for closing argument
        """
        if not transcript:
            return "No testimony recorded."
        
        # Categorize transcript entries
        our_direct_testimony = []
        our_cross_testimony = []
        opposing_direct_testimony = []
        opposing_cross_testimony = []
        key_moments = []  # objections, rulings, interruptions
        
        for entry in transcript:
            role = entry.get("role", "unknown")
            text = entry.get("text", "")
            phase = entry.get("phase", "").upper()
            event_type = entry.get("event_type", "")
            
            # Track key moments (objections, rulings)
            if event_type in ["objection", "ruling", "interrupt", "sustain", "overrule"]:
                key_moments.append({
                    "phase": phase,
                    "role": role,
                    "text": text[:300],
                    "event_type": event_type
                })
                continue
            
            # Categorize testimony by phase and side
            if "DIRECT" in phase:
                # On direct, our side's witnesses testify
                is_our_witness = (
                    (self.persona.side == "plaintiff" and "PLAINTIFF" in role.upper()) or
                    (self.persona.side == "defense" and "DEFENSE" in role.upper()) or
                    ("WITNESS" in role.upper())  # Witness testimony
                )
                if is_our_witness or self.persona.side in role.lower():
                    our_direct_testimony.append({
                        "phase": phase, "role": role, "text": text[:400]
                    })
                else:
                    opposing_direct_testimony.append({
                        "phase": phase, "role": role, "text": text[:400]
                    })
            elif "CROSS" in phase:
                # On cross, we examine opposing witnesses
                is_our_questioning = (
                    (self.persona.side == "plaintiff" and "PLAINTIFF" in role.upper()) or
                    (self.persona.side == "defense" and "DEFENSE" in role.upper())
                )
                if is_our_questioning:
                    our_cross_testimony.append({
                        "phase": phase, "role": role, "text": text[:400]
                    })
                else:
                    opposing_cross_testimony.append({
                        "phase": phase, "role": role, "text": text[:400]
                    })
        
        # Build summary prioritizing most relevant testimony
        summary_parts = []
        
        # Our direct testimony (most important for our case theory)
        if our_direct_testimony:
            summary_parts.append("=== KEY TESTIMONY FROM OUR WITNESSES ===")
            for entry in our_direct_testimony[-8:]:  # Last 8 entries
                summary_parts.append(
                    f"[{entry['phase']}] {entry['role']}: {entry['text']}"
                )
        
        # Our cross examination (damaging admissions from opposing witnesses)
        if our_cross_testimony:
            summary_parts.append("\n=== CROSS-EXAMINATION HIGHLIGHTS ===")
            for entry in our_cross_testimony[-6:]:  # Last 6 entries
                summary_parts.append(
                    f"[{entry['phase']}] {entry['role']}: {entry['text']}"
                )
        
        # Opposing testimony to address
        if opposing_direct_testimony:
            summary_parts.append("\n=== OPPOSING TESTIMONY TO ADDRESS ===")
            for entry in opposing_direct_testimony[-6:]:
                summary_parts.append(
                    f"[{entry['phase']}] {entry['role']}: {entry['text']}"
                )
        
        # Key moments (objections, rulings)
        if key_moments:
            summary_parts.append("\n=== KEY RULINGS/MOMENTS ===")
            for moment in key_moments[-5:]:
                summary_parts.append(
                    f"[{moment['event_type'].upper()}] {moment['role']}: {moment['text']}"
                )
        
        # Fallback if categorization yielded nothing
        if not summary_parts:
            recent = transcript[-max_entries:]
            summary_parts = [
                f"[{entry.get('phase', '')}] {entry.get('role', '')}: {entry.get('text', '')[:200]}"
                for entry in recent
            ]
        
        return "\n".join(summary_parts)
    
    # =========================================================================
    # OBJECTION HANDLING
    # =========================================================================
    
    def should_object(
        self,
        state: TrialState,
        opposing_question: str,
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Determine if attorney should object to opposing counsel's question.

        In real mock trial tournaments, attorneys are expected to raise
        well-founded objections whenever the rules of evidence are violated.
        Failing to object is a scoring weakness. This method uses broad
        pattern detection plus LLM analysis on every question to ensure
        objections are raised when warranted.
        """

        valid, reason = can_object(state, self.role)
        if not valid:
            return None

        question_lower = opposing_question.lower().strip()

        is_direct = "direct" in state.phase.value.lower() or "redirect" in state.phase.value.lower()
        is_cross = not is_direct
        recent_questions = context.get("recent_questions", [])

        # ---- Pattern detection for clear-cut violations ----
        # When a pattern match is found, object immediately (high confidence).
        obvious_issues: list[str] = []

        # Leading on direct — broader detection
        leading_indicators = [
            "isn't it true", "wouldn't you agree", "isn't that correct",
            "isn't that right", "wouldn't you say", "don't you think",
            "isn't it fair to say", "you would agree", "it's true that",
            "so you're saying", "you're telling us",
        ]
        # Tag questions: statements ending with ", correct?", ", right?", ", yes?"
        tag_question = bool(re.search(r",\s*(correct|right|yes|no|true)\s*\?", question_lower))
        if is_direct and (any(ind in question_lower for ind in leading_indicators) or tag_question):
            obvious_issues.append("leading")

        # Hearsay — witness asked about what someone else said/told/stated
        hearsay_indicators = [
            "what did .+ tell you", "what did .+ say", "what were you told",
            "according to .+,", "someone told you", "you were informed",
            "did .+ mention", "did .+ tell you", "you heard .+ say",
        ]
        if any(re.search(pat, question_lower) for pat in hearsay_indicators):
            obvious_issues.append("hearsay")

        # Speculation — asking witness to guess, speculate, or opine on others' state of mind
        speculation_indicators = [
            "what do you think", "what do you believe", "how do you think",
            "why do you think", "what was .+ thinking", "what was .+ feeling",
            "what might have", "what could have", "can you speculate",
            "would you guess", "in your opinion", "do you suppose",
        ]
        if any(re.search(pat, question_lower) for pat in speculation_indicators):
            obvious_issues.append("speculation")

        # Asked and answered — semantic similarity (not exact match)
        q_words = set(question_lower.split())
        for prev_q in recent_questions[-5:]:
            prev_words = set(prev_q.lower().split())
            if len(q_words) > 3 and len(prev_words) > 3:
                overlap = len(q_words & prev_words) / max(len(q_words | prev_words), 1)
                if overlap > 0.7:
                    obvious_issues.append("asked_and_answered")
                    break

        # Compound — multiple independent questions
        qmark_count = question_lower.count("?")
        if qmark_count > 1:
            obvious_issues.append("compound")

        # Argumentative — attorney arguing with the witness
        argumentative_indicators = [
            "you expect us to believe", "that's ridiculous",
            "you're lying", "that makes no sense", "come on",
            "don't you think that's suspicious", "isn't it convenient",
            "how convenient", "that's hard to believe", "really?",
        ]
        if any(ind in question_lower for ind in argumentative_indicators):
            obvious_issues.append("argumentative")

        # Assumes facts not in evidence
        assumes_facts_indicators = [
            "after you .+ (which|that) we know", "given that you",
            "since you already", "we all know that",
        ]
        if any(re.search(pat, question_lower) for pat in assumes_facts_indicators):
            obvious_issues.append("assumes_facts")

        # Beyond scope (on cross — question unrelated to direct testimony)
        if is_cross and context.get("direct_topics"):
            pass  # LLM will catch this better

        # Narrative — "tell us everything that happened" style
        narrative_indicators = [
            "tell us everything", "describe everything",
            "walk us through your entire", "tell us the whole story",
            "explain everything",
        ]
        if any(ind in question_lower for ind in narrative_indicators):
            obvious_issues.append("narrative")

        # ---- For pattern-detected issues, object with high probability ----
        if obvious_issues:
            if random.random() < 0.85:
                return obvious_issues[0]
            return None

        # ---- Keyword pre-filter: skip LLM if question looks clean ----
        _OBJECTION_KEYWORDS = {
            "told", "said", "heard", "told you", "informed", "mentioned",
            "think", "believe", "guess", "speculate", "suppose", "opinion",
            "everything", "entire", "whole story",
            "ridiculous", "lying", "convenient", "really",
            "given that", "since you", "we all know",
            "correct", "right", "true", "agree",
        }
        has_keyword = any(kw in question_lower for kw in _OBJECTION_KEYWORDS)
        if not has_keyword and not is_direct:
            return None

        llm_skip_rate = 0.15
        if random.random() < llm_skip_rate:
            return None

        exam_label = "direct examination" if is_direct else "cross-examination"
        recent_qs_text = "\n".join(f"- {q}" for q in recent_questions[-4:]) if recent_questions else "(none)"

        analysis_prompt = f"""You are an experienced mock trial attorney analyzing whether to object to a question.

QUESTION BEING ASKED: "{opposing_question}"
EXAMINATION TYPE: {exam_label}
WITNESS: {context.get('witness_name', 'Unknown')}
RECENT PRIOR QUESTIONS:
{recent_qs_text}

EVIDENCE RULES:
- Leading questions are ALLOWED on cross-examination but PROHIBITED on direct/redirect
- Hearsay: witness asked to repeat what someone ELSE said/told them (out-of-court statements offered for truth)
- Speculation: witness asked to guess or speculate about something they don't have personal knowledge of
- Relevance: question has nothing to do with the issues in the case
- Assumes facts: question assumes something that hasn't been established in evidence
- Beyond scope: on cross, question goes beyond what was covered on direct
- Compound: two or more separate questions combined into one
- Argumentative: attorney is arguing with the witness rather than asking a question
- Narrative: overly broad question inviting a lengthy unstructured answer
- Asked and answered: substantially the same question was already asked and answered
- Non-responsive: (used for witness answers, not questions)

INSTRUCTIONS:
- You MUST object when there is a valid legal basis. Failing to object to an improper question is a scoring weakness in mock trial.
- Object when the question violates the rules of evidence. Be vigilant but not frivolous.
- Proper, well-formed questions should get "NO OBJECTION".
- When in doubt on a borderline question, it is better to object and let the judge rule.

Respond with EXACTLY one line:
- "OBJECT: [type]" if the question violates any rule of evidence
- "NO OBJECTION" if the question is proper

Answer:"""

        try:
            response = self._generate(
                "You are a mock trial evidence rules analyst. Identify violations of the rules of evidence.",
                analysis_prompt,
                temperature=0.3,
                max_tokens=30,
                model=MODEL_NANO
            )
        except Exception as e:
            _attorney_logger.warning(f"Objection analysis LLM call failed: {e}")
            return None

        response = response.strip()
        upper = response.upper()

        if "OBJECT" in upper and "NO OBJECTION" not in upper:
            raw = response.split(":", 1)[-1].strip() if ":" in response else ""
            candidate = raw.strip().strip(".").strip('"').strip("'").lower().replace(" ", "_")
            if candidate in VALID_OBJECTION_TYPES:
                return candidate
            for vt in VALID_OBJECTION_TYPES:
                if vt in candidate or candidate in vt:
                    return vt
            return None

        return None
    
    def generate_objection(self, objection_type: str) -> str:
        """
        Generate the spoken objection.
        
        Per AUDIO.md: Objections may interrupt testimony.
        
        Args:
            objection_type: Type of objection to raise
            
        Returns:
            Objection text for TTS (e.g., "Objection, Your Honor. Leading.")
        """
        # Objections should be brief and formal
        objection_phrases = {
            "hearsay": "Objection, Your Honor. Hearsay.",
            "leading": "Objection. Leading the witness.",
            "relevance": "Objection, Your Honor. Relevance.",
            "speculation": "Objection. Calls for speculation.",
            "asked_and_answered": "Objection. Asked and answered.",
            "compound": "Objection. Compound question.",
            "argumentative": "Objection, Your Honor. Argumentative.",
            "assumes_facts": "Objection. Assumes facts not in evidence.",
            "beyond_scope": "Objection. Beyond the scope.",
            "narrative": "Objection. Narrative.",
            "non_responsive": "Objection, Your Honor. Non-responsive.",
        }
        
        return objection_phrases.get(
            objection_type,
            f"Objection, Your Honor. {objection_type.replace('_', ' ').title()}."
        )
    
    def respond_to_ruling(self, sustained: bool) -> Optional[str]:
        """
        Generate response to judge's ruling on objection.
        
        Args:
            sustained: Whether objection was sustained
            
        Returns:
            Response text for TTS, or None if no response needed
        """
        # Brief acknowledgment only
        if sustained:
            return None  # No need to respond when you win
        
        # When overruled, may briefly acknowledge
        if self.persona.formality > 0.5:
            return None  # Formal attorneys don't respond to overruled
        
        return None  # Generally, don't respond to rulings
    
    # =========================================================================
    # STATE TRACKING (for strategic decisions)
    # =========================================================================
    
    def record_objection_result(self, sustained: bool) -> None:
        """
        Record objection result for strategic tracking.
        
        This affects future objection decisions.
        """
        self._objections_made += 1
        if sustained:
            self._objections_sustained += 1
    
    def get_objection_success_rate(self) -> float:
        """Get current objection success rate."""
        if self._objections_made == 0:
            return 0.5  # Default to neutral
        return self._objections_sustained / self._objections_made
    
    # =========================================================================
    # CONVERSATION HISTORY
    # =========================================================================
    
    def add_to_history(self, role: str, content: str) -> None:
        """
        Add exchange to conversation history for context.
        
        Args:
            role: "user" or "assistant"
            content: Message content
        """
        self._conversation_history.append({
            "role": role,
            "content": content
        })
        
        # Keep history bounded
        if len(self._conversation_history) > 50:
            self._conversation_history = self._conversation_history[-50:]
    
    def clear_history(self) -> None:
        """Clear conversation history (e.g., between witnesses)."""
        self._conversation_history = []
    
    # =========================================================================
    # PROCEDURAL STATEMENTS
    # =========================================================================
    
    def generate_witness_call(self, witness_name: str) -> str:
        """
        Generate statement to call a witness.
        
        Args:
            witness_name: Name of witness to call
            
        Returns:
            Text for TTS
        """
        return f"Your Honor, the {self.persona.side} calls {witness_name} to the stand."
    
    def generate_no_further_questions(self) -> str:
        """Generate statement to end examination."""
        return "No further questions, Your Honor."
    
    def generate_rest_case(self) -> str:
        """Generate statement to rest case."""
        return f"Your Honor, the {self.persona.side} rests."


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_attorney_agent(
    name: str,
    side: Literal["plaintiff", "defense"],
    style: AttorneyStyle = AttorneyStyle.METHODICAL,
    skill_level: SkillLevel = SkillLevel.INTERMEDIATE,
    case_theory: str = "",
    **kwargs
) -> AttorneyAgent:
    """
    Factory function to create an AttorneyAgent.
    
    Per ARCHITECTURE.md - LLM Access:
    - Agents never hold API keys or call OpenAI directly
    - LLM access is handled internally via call_llm service
    
    Args:
        name: Attorney's name
        side: "plaintiff" or "defense"
        style: Advocacy style
        skill_level: Skill level
        case_theory: The attorney's theory of the case
        **kwargs: Additional persona parameters
        
    Returns:
        Configured AttorneyAgent
    """
    persona = AttorneyPersona(
        name=name,
        side=side,
        style=style,
        skill_level=skill_level,
        case_theory=case_theory,
        **kwargs
    )
    
    return AttorneyAgent(persona)
