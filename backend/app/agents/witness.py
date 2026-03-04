"""
Witness Agent

Per AGENTS.md Section 3:
- Responsibilities: Answer questions truthfully within affidavit,
  Maintain consistency with prior testimony
- Behavior: Affected by nervousness, May hesitate or pause,
  Higher difficulty = narrower answers
- Constraints: No new facts, No legal argument, No strategic cooperation

Per ARCHITECTURE.md:
- Uses GPT-4.1 for all reasoning
- Text output only (TTS handled by audio pipeline)
- Must respect trial state from LangGraph
- Agents never hold API keys or call OpenAI directly
- Agents communicate with LLM via backend service (call_llm)

Per AGENTS.md - Agent → LLM Communication:
- All agent calls to GPT-4.1 go through backend service
- Agents are unaware of API keys

Per AUDIO.md:
- Preserve filler words and pauses
- Silence, pauses, interruptions matter
"""

import logging
from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field
from enum import Enum

from ..services.llm_service import call_llm, PersonaContext
from ..services.vector_retrieval import retrieve_relevant_affidavit

_witness_logger = logging.getLogger(__name__)

from ..graph.trial_graph import (
    TrialState,
    TrialPhase,
    Role,
    TESTIMONY_STATES,
    validate_speaker,
)


# =============================================================================
# PERSONA PARAMETERS
# =============================================================================

class WitnessType(str, Enum):
    """Type of witness affecting baseline behavior."""
    FACT_WITNESS = "fact_witness"      # Ordinary person who observed events
    EXPERT_WITNESS = "expert_witness"  # Professional with specialized knowledge
    CHARACTER_WITNESS = "character_witness"  # Testifies about character


class Demeanor(str, Enum):
    """Witness demeanor affecting speech patterns."""
    CALM = "calm"              # Steady, composed
    NERVOUS = "nervous"        # Hesitant, filler words
    DEFENSIVE = "defensive"    # Guarded, short answers
    EAGER = "eager"            # Wants to help, may over-explain
    HOSTILE = "hostile"        # Reluctant, minimal cooperation


@dataclass
class WitnessPersona:
    """
    Persona parameters that shape witness behavior.
    
    Per SPEC.md Section 2: Persona parameters shape reasoning, speech style,
    voice output, and scoring bias.
    
    Per AGENTS.md Section 3: Behavior affected by nervousness.
    """
    name: str
    witness_id: str  # Unique identifier for tracking
    
    # Witness characteristics
    witness_type: WitnessType = WitnessType.FACT_WITNESS
    demeanor: Demeanor = Demeanor.CALM
    
    # Which side called this witness
    called_by: Literal["plaintiff", "defense"] = "plaintiff"
    
    # Nervousness level (0.0 = completely calm, 1.0 = extremely nervous)
    # Per AGENTS.md: Affected by nervousness, may hesitate or pause
    nervousness: float = 0.3
    
    # Difficulty level (0.0 = very cooperative, 1.0 = very difficult)
    # Per AGENTS.md: Higher difficulty = narrower answers
    difficulty: float = 0.3
    
    # Speech characteristics (for TTS persona conditioning)
    speaking_pace: float = 1.0  # Affected by nervousness
    
    # The witness's affidavit (source of truth for all testimony)
    affidavit: str = ""
    
    # Character background (for consistent persona, not for inventing facts)
    background: str = ""
    
    # Age, occupation for context
    age: Optional[int] = None
    occupation: str = ""
    role_description: str = ""  # e.g. "Expert Witness", "Eyewitness"

    # Per-agent prep materials (loaded from DB)
    prep_materials: Dict[str, Any] = field(default_factory=dict)

    # Per-agent LLM overrides
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    custom_system_prompt: Optional[str] = None


# =============================================================================
# TESTIMONY MEMORY
# =============================================================================

@dataclass
class TestimonyEntry:
    """A single Q&A exchange in testimony."""
    question: str
    answer: str
    phase: TrialPhase
    questioner_side: Literal["plaintiff", "defense"]
    timestamp: float = 0.0


@dataclass
class WitnessMemory:
    """
    Tracks everything the witness has said.
    
    Per AGENTS.md: Maintain consistency with prior testimony.
    """
    # All testimony given
    testimony: List[TestimonyEntry] = field(default_factory=list)
    
    # Facts explicitly stated (for consistency checking)
    stated_facts: Dict[str, str] = field(default_factory=dict)
    
    # Topics covered (to detect asked_and_answered)
    topics_covered: List[str] = field(default_factory=list)
    
    def add_testimony(
        self,
        question: str,
        answer: str,
        phase: TrialPhase,
        questioner_side: Literal["plaintiff", "defense"],
        timestamp: float = 0.0
    ) -> None:
        """Record a Q&A exchange."""
        self.testimony.append(TestimonyEntry(
            question=question,
            answer=answer,
            phase=phase,
            questioner_side=questioner_side,
            timestamp=timestamp
        ))
    
    def get_prior_testimony(self, limit: int = 10) -> List[TestimonyEntry]:
        """Get recent prior testimony for context."""
        return self.testimony[-limit:]
    
    def get_testimony_by_phase(self, phase: TrialPhase) -> List[TestimonyEntry]:
        """Get all testimony from a specific phase."""
        return [t for t in self.testimony if t.phase == phase]
    
    def has_stated(self, topic: str) -> bool:
        """Check if witness has already addressed a topic."""
        return topic.lower() in [t.lower() for t in self.topics_covered]
    
    def record_stated_fact(self, fact_key: str, fact_value: str) -> None:
        """Record a specific fact that was stated."""
        self.stated_facts[fact_key] = fact_value
    
    def get_stated_fact(self, fact_key: str) -> Optional[str]:
        """Get a previously stated fact for consistency."""
        return self.stated_facts.get(fact_key)


# =============================================================================
# WITNESS AGENT
# =============================================================================

class WitnessAgent:
    """
    AI Witness Agent using GPT-4.1.
    
    Per AGENTS.md Section 3:
    - Answer questions truthfully within affidavit
    - Maintain consistency with prior testimony
    - Affected by nervousness, may hesitate or pause
    - Higher difficulty = narrower answers
    - No new facts
    - No legal argument
    - No strategic cooperation
    
    Per ARCHITECTURE.md:
    - All output is text for TTS pipeline
    - Must respect trial state from LangGraph
    """
    
    MODEL = "gpt-4.1"  # Per README.md: OpenAI GPT-4.1 for all agents
    
    def __init__(
        self,
        persona: WitnessPersona,
    ):
        """
        Initialize witness agent with persona.
        
        Per ARCHITECTURE.md - LLM Access:
        - Agents never hold API keys or call OpenAI directly
        - Agents communicate with LLM via backend service (call_llm)
        
        Args:
            persona: WitnessPersona defining behavior parameters
        """
        self.persona = persona
        self.role = Role.WITNESS
        self.memory = WitnessMemory()
        
        # Persona context for LLM service calls
        self._persona_context = PersonaContext(
            role="witness",
            name=persona.name,
            style=persona.demeanor.value,
            authority=0.3,  # Witnesses generally don't speak with authority
            nervousness=persona.nervousness,
            formality=0.6,
            additional_traits={
                "witness_type": persona.witness_type.value,
                "called_by": persona.called_by,
                "difficulty": persona.difficulty,
            }
        )
        
        # Track current examination state
        self._current_questioner: Optional[Literal["plaintiff", "defense"]] = None
        self._questions_in_current_exam: int = 0
    
    # =========================================================================
    # CORE GENERATION METHOD
    # =========================================================================
    
    def _generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 300
    ) -> str:
        """Generate text response via backend LLM service with per-agent overrides."""
        if self.persona.custom_system_prompt:
            system_prompt = self.persona.custom_system_prompt + "\n\n" + system_prompt
        return call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            persona=self._persona_context,
            temperature=self.persona.llm_temperature if self.persona.llm_temperature is not None else temperature,
            max_tokens=self.persona.llm_max_tokens if self.persona.llm_max_tokens is not None else max_tokens,
            model=self.persona.llm_model or self.MODEL,
        )
    
    def _build_system_prompt(self, context: str) -> str:
        """
        Build system prompt incorporating persona parameters.
        
        Per AGENTS.md: Behavior is persona-driven.
        """
        demeanor_instructions = {
            Demeanor.CALM: (
                "You are calm and composed. "
                "Answer steadily without rushing. "
                "You are not rattled by difficult questions."
            ),
            Demeanor.NERVOUS: (
                "You are nervous and uncertain. "
                "Use filler words like 'um', 'uh', 'well'. "
                "Sometimes pause mid-sentence with '...' "
                "You may ask for clarification when confused."
            ),
            Demeanor.DEFENSIVE: (
                "You are guarded and defensive. "
                "Give short, minimal answers. "
                "Do not volunteer extra information. "
                "You are wary of tricks."
            ),
            Demeanor.EAGER: (
                "You want to be helpful and thorough. "
                "You may explain more than asked. "
                "Be careful not to go beyond what you actually know."
            ),
            Demeanor.HOSTILE: (
                "You are reluctant and uncooperative. "
                "Answer only exactly what is asked. "
                "You may express frustration briefly. "
                "You do not help the questioner."
            ),
        }
        
        difficulty_instructions = self._get_difficulty_instructions()
        nervousness_instructions = self._get_nervousness_instructions()
        
        # Build prior testimony summary for consistency
        prior_summary = self._summarize_prior_testimony()
        
        return f"""You are {self.persona.name}, a witness in a college mock trial tournament.
You are portrayed by a college student — speak naturally with a youthful, conversational tone.

HOW MOCK TRIAL WITNESSES WORK:
You have studied your affidavit thoroughly. You know the facts from your own experience.
You do NOT have pre-rehearsed answers to specific questions — you respond naturally based
on what you remember from your affidavit. You never make things up. If a question catches
you off guard, you think and answer honestly from what you know.

ABSOLUTE CONSTRAINTS (NEVER VIOLATE):
- You can ONLY testify to facts in your affidavit below — READ IT CAREFULLY
- You CANNOT invent new facts, details, or information not in the affidavit
- You CANNOT make legal arguments
- You CANNOT strategically help either side
- You MUST be consistent with everything you have previously said
- If asked about something NOT in your affidavit, say "I don't know" or "I don't recall"
- CRITICAL: When answering, USE SPECIFIC names, dates, locations, and details from your affidavit. NEVER give vague or generic answers when your affidavit contains specific information.
- You are NOT reading from a script. You are recalling events from your own memory/experience.

YOUR AFFIDAVIT (this is ALL you know — study every detail):
{self.persona.affidavit or "[WARNING: No affidavit loaded — answer every question with: I do not recall the specifics]"}

YOUR BACKGROUND:
- Name: {self.persona.name}
- Age: {self.persona.age or "Not specified"}
- Occupation: {self.persona.occupation or "Not specified"}
- Called by: {self.persona.called_by}
{self.persona.background}

DEMEANOR:
{demeanor_instructions[self.persona.demeanor]}

{nervousness_instructions}

{difficulty_instructions}

PRIOR TESTIMONY (you MUST be consistent with this):
{prior_summary}

SPEECH OUTPUT RULES:
- Generate ONLY spoken words — this goes directly to TTS.
- Speak like a real young person, not a textbook. Use contractions (don't, wasn't, I'd).
- Include natural hesitations ("um", "well", "I mean") and pauses (...) if nervous.
- Show emotion appropriate to what you're describing — concern, frustration, sadness, certainty.
- Do NOT include stage directions, actions, or internal thoughts.
- Sound like you're actually REMEMBERING and TELLING your story, not reading a script.

{context}
"""
    
    def _get_nervousness_instructions(self) -> str:
        """Get instructions based on nervousness level."""
        n = self.persona.nervousness
        
        if n < 0.2:
            return "NERVOUSNESS: Very low. You are confident and clear."
        elif n < 0.4:
            return "NERVOUSNESS: Low. Mostly confident with occasional hesitation."
        elif n < 0.6:
            return (
                "NERVOUSNESS: Moderate. Include occasional 'um' or 'uh'. "
                "Sometimes pause briefly with '...' when thinking."
            )
        elif n < 0.8:
            return (
                "NERVOUSNESS: High. Frequently use filler words. "
                "Pause often with '...' Include phrases like 'I think' or 'I believe'. "
                "May ask to have questions repeated."
            )
        else:
            return (
                "NERVOUSNESS: Very high. Heavy use of fillers: 'um', 'uh', 'well...'. "
                "Long pauses '...' frequently. Voice may waver. "
                "May say 'I'm sorry, could you repeat that?' "
                "Answers may trail off..."
            )
    
    def _get_difficulty_instructions(self) -> str:
        """Get instructions based on difficulty level."""
        d = self.persona.difficulty
        
        if d < 0.2:
            return (
                "ANSWER STYLE: Very cooperative. "
                "Give full, helpful answers within your knowledge. "
                "Volunteer relevant context when appropriate."
            )
        elif d < 0.4:
            return (
                "ANSWER STYLE: Cooperative. "
                "Answer questions directly and completely. "
                "Don't volunteer extra information."
            )
        elif d < 0.6:
            return (
                "ANSWER STYLE: Neutral. "
                "Answer only what is directly asked. "
                "Be precise but not expansive."
            )
        elif d < 0.8:
            return (
                "ANSWER STYLE: Difficult. "
                "Give narrow, literal answers. "
                "If a question is slightly ambiguous, answer the narrowest interpretation. "
                "Do not help clarify poorly-worded questions."
            )
        else:
            return (
                "ANSWER STYLE: Very difficult. "
                "Answer only the absolute minimum required. "
                "Take advantage of any ambiguity in questions. "
                "If you can technically answer 'yes' or 'no' without lying, do so. "
                "Force the attorney to ask precise questions."
            )
    
    def _summarize_prior_testimony(self) -> str:
        """Summarize prior testimony for consistency checking."""
        prior = self.memory.get_prior_testimony(limit=15)
        
        if not prior:
            return "No prior testimony yet."
        
        summary_lines = []
        for entry in prior:
            phase_label = entry.phase.value
            summary_lines.append(
                f"[{phase_label}]\n"
                f"Q: {entry.question}\n"
                f"A: {entry.answer}"
            )
        
        return "\n\n".join(summary_lines)
    
    # =========================================================================
    # TRIAL STATE VALIDATION
    # =========================================================================
    
    def can_act(self, state: TrialState) -> tuple[bool, Optional[str]]:
        """
        Check if witness can testify in current trial state.
        
        Per ARCHITECTURE.md: LangGraph is single source of truth.
        """
        return validate_speaker(state, self.role)
    
    def _validate_state_for_testimony(self, state: TrialState) -> None:
        """
        Validate trial state before answering.
        
        Raises:
            ValueError: If state doesn't permit testimony
        """
        valid, reason = self.can_act(state)
        if not valid:
            raise ValueError(f"Cannot testify: {reason}")
        
        if state.phase not in TESTIMONY_STATES:
            raise ValueError(
                f"Testimony not permitted in {state.phase.value}. "
                f"Testimony phases: {[p.value for p in TESTIMONY_STATES]}"
            )
        
        # Verify this witness is on the stand
        if state.current_witness_id != self.persona.witness_id:
            raise ValueError(
                f"Witness {self.persona.witness_id} is not on the stand. "
                f"Current witness: {state.current_witness_id}"
            )
    
    # =========================================================================
    # ANSWER GENERATION
    # =========================================================================
    
    def answer_question(
        self,
        state: TrialState,
        question: str,
        questioner_side: Literal["plaintiff", "defense"],
        trial_memory=None,
    ) -> str:
        """
        Generate answer to a question.
        
        Per AGENTS.md:
        - Answer questions truthfully within affidavit
        - Maintain consistency with prior testimony
        - Cannot invent facts
        
        Args:
            state: Current trial state
            question: The question being asked
            questioner_side: Which side is asking
            trial_memory: Optional TrialMemory for cross-witness consistency
            
        Returns:
            Answer text for TTS
        """
        self._validate_state_for_testimony(state)
        
        # Update tracking
        self._current_questioner = questioner_side
        self._questions_in_current_exam += 1
        
        # Determine examination type for context
        is_friendly = (questioner_side == self.persona.called_by)
        exam_type = self._get_examination_type(state.phase, is_friendly)
        
        # Adjust difficulty based on examination type
        effective_difficulty = self._get_effective_difficulty(is_friendly)
        
        prep_section = ""
        prep = self.persona.prep_materials
        if prep:
            parts = []
            if prep.get("case_understanding"):
                parts.append(f"YOUR UNDERSTANDING OF THE CASE:\n{prep['case_understanding']}")
            if prep.get("key_facts_known"):
                facts = prep["key_facts_known"]
                parts.append("FACTS YOU PERSONALLY KNOW (from your affidavit):\n" + "\n".join(f"- {f}" for f in facts[:8]))
            if prep.get("areas_of_strength"):
                strengths = prep["areas_of_strength"]
                parts.append("YOUR STRONGEST TESTIMONY AREAS:\n" + "\n".join(f"- {s}" for s in strengths[:5]))
            if not is_friendly and prep.get("areas_of_vulnerability"):
                vulns = prep["areas_of_vulnerability"]
                parts.append("BE CAREFUL WITH THESE AREAS (opposing counsel may challenge):\n" + "\n".join(f"- {v}" for v in vulns[:5]))
            if prep.get("things_witness_does_not_know"):
                unknowns = prep["things_witness_does_not_know"]
                parts.append("OUTSIDE YOUR KNOWLEDGE (say 'I don't know'):\n" + "\n".join(f"- {u}" for u in unknowns[:4]))
            if prep.get("demeanor_guidance"):
                parts.append(f"DEMEANOR: {prep['demeanor_guidance']}")
            # Legacy fallback for old prep format
            if not parts and prep.get("key_points_to_emphasize"):
                points = prep["key_points_to_emphasize"]
                parts.append("KEY POINTS TO REMEMBER:\n" + "\n".join(f"- {p}" for p in points[:6]))
            if parts:
                prep_section = "\n\n=== YOUR PREPARATION NOTES ===\n" + "\n".join(parts) + "\n=== END PREPARATION NOTES ===\n"

        # Cross-exam consistency context from trial memory
        memory_section = ""
        team_section = ""
        if trial_memory:
            prior_context = trial_memory.build_witness_context(self.persona.witness_id)
            if prior_context:
                memory_section = f"\n=== CROSS-EXAM CONSISTENCY (from all prior examinations) ===\n{prior_context}\n=== END ===\n"
            # Team shared intelligence for this witness
            witness_side = getattr(self.persona, "called_by", None) or "plaintiff"
            if witness_side in ("prosecution", "plaintiff"):
                witness_side = "plaintiff"
            team_section = trial_memory.build_team_shared_context_for_witness(witness_side, self.persona.witness_id)

        # Vector retrieval: get the most relevant affidavit passages for this question
        retrieval_section = ""
        retrieved_passages = retrieve_relevant_affidavit(
            self.persona.witness_id, question, top_k=5
        )
        if retrieved_passages:
            _witness_logger.debug(f"Witness {self.persona.name}: retrieved {len(retrieved_passages)} relevant passages for question")
            numbered = "\n".join(f"{i+1}. {p}" for i, p in enumerate(retrieved_passages))
            retrieval_section = f"\n=== MOST RELEVANT PARTS OF YOUR AFFIDAVIT FOR THIS QUESTION ===\n{numbered}\n=== END RELEVANT PASSAGES ===\n"

        context = f"""
CURRENT EXAMINATION:
- Phase: {state.phase.value}
- Questioner: {questioner_side} attorney
- This is: {exam_type}
- Questions so far in this examination: {self._questions_in_current_exam}

THE QUESTION:
"{question}"
{retrieval_section}
{prep_section}
{memory_section}
{team_section}
ANSWERING RULES:
1. Answer ONLY from your affidavit — cite SPECIFIC facts, names, dates, and details
2. If it's not in your affidavit, say "I don't know" or "I don't recall"
3. Stay consistent with all prior testimony
4. {"Be helpful and complete — provide detail from your affidavit." if effective_difficulty < 0.4 else "Be precise and narrow — answer only what is asked." if effective_difficulty > 0.6 else "Answer directly with specifics from your affidavit."}
5. {"This is friendly examination - give full, detailed answers from your affidavit." if is_friendly else "This is adverse examination - be careful and precise, but still answer truthfully with specifics."}
6. NEVER give generic or vague answers. Always reference specific facts you know.
"""
        
        system_prompt = self._build_system_prompt(context)
        user_prompt = f'Answer this question: "{question}"'
        
        # Temperature varies with nervousness (more nervous = slight variance)
        temperature = 0.5 + (self.persona.nervousness * 0.3)
        
        max_tokens = int(600 - (effective_difficulty * 200))
        max_tokens = max(200, max_tokens)
        
        answer = self._generate(
            system_prompt,
            user_prompt,
            temperature=temperature,
            max_tokens=max_tokens
        )
        
        # Record in memory
        self.memory.add_testimony(
            question=question,
            answer=answer,
            phase=state.phase,
            questioner_side=questioner_side
        )
        
        return answer
    
    def _get_examination_type(
        self,
        phase: TrialPhase,
        is_friendly: bool
    ) -> str:
        """Describe the type of examination for context."""
        if phase == TrialPhase.DIRECT:
            return "Direct examination (friendly)" if is_friendly else "Direct examination (unusual - opposing counsel)"
        elif phase == TrialPhase.CROSS:
            return "Cross examination (adverse)" if not is_friendly else "Cross examination (unusual - friendly counsel)"
        elif phase == TrialPhase.REDIRECT:
            return "Redirect examination (friendly)" if is_friendly else "Redirect examination (unusual)"
        elif phase == TrialPhase.RECROSS:
            return "Recross examination (adverse)" if not is_friendly else "Recross examination (unusual)"
        return "Unknown examination"
    
    def _get_effective_difficulty(self, is_friendly: bool) -> float:
        """
        Calculate effective difficulty based on context.
        
        Witnesses are typically more cooperative on direct than cross.
        """
        base = self.persona.difficulty
        
        if is_friendly:
            # More cooperative with friendly counsel
            return max(0.0, base - 0.2)
        else:
            # More difficult with adverse counsel
            return min(1.0, base + 0.2)
    
    # =========================================================================
    # SPECIAL RESPONSES
    # =========================================================================
    
    def generate_oath_response(self) -> str:
        """
        Generate response to oath.
        
        Returns:
            Oath affirmation text for TTS
        """
        if self.persona.nervousness > 0.6:
            return "I... I do."
        elif self.persona.nervousness > 0.3:
            return "I do."
        else:
            return "I do, Your Honor."
    
    def generate_state_name(self) -> str:
        """
        Generate response to "Please state your name for the record."
        
        Returns:
            Name statement text for TTS
        """
        if self.persona.nervousness > 0.7:
            return f"Um... my name is {self.persona.name}."
        elif self.persona.nervousness > 0.4:
            return f"My name is {self.persona.name}."
        else:
            return f"{self.persona.name}."
    
    def generate_clarification_request(self) -> str:
        """
        Generate request for clarification when question is unclear.
        
        Per AGENTS.md: May hesitate or pause.
        
        Returns:
            Clarification request text for TTS
        """
        responses = {
            (0.0, 0.3): "I'm not sure I understand the question. Could you rephrase that?",
            (0.3, 0.6): "I'm sorry... could you repeat that?",
            (0.6, 0.8): "Um... I don't... could you say that again?",
            (0.8, 1.0): "I... I'm sorry, I... what was the question?",
        }
        
        for (low, high), response in responses.items():
            if low <= self.persona.nervousness < high:
                return response
        
        return "Could you repeat the question?"
    
    def generate_dont_know(self) -> str:
        """
        Generate "I don't know" response.
        
        Used when question asks about facts not in affidavit.
        Per AGENTS.md: Cannot invent facts.
        
        Returns:
            "I don't know" variation for TTS
        """
        n = self.persona.nervousness
        d = self.persona.demeanor
        
        if d == Demeanor.DEFENSIVE:
            return "I don't know."
        elif d == Demeanor.HOSTILE:
            return "I wouldn't know."
        elif d == Demeanor.EAGER:
            return "I'm sorry, I don't know the answer to that."
        elif n > 0.6:
            return "I... I don't know."
        elif n > 0.3:
            return "I don't know."
        else:
            return "I don't recall."
    
    def generate_dont_recall(self) -> str:
        """
        Generate "I don't recall" response.
        
        Returns:
            "I don't recall" variation for TTS
        """
        n = self.persona.nervousness
        
        if n > 0.6:
            return "I... I don't... I don't remember."
        elif n > 0.3:
            return "I don't recall."
        else:
            return "I don't recall the specific details."
    
    # =========================================================================
    # CONSISTENCY CHECKING
    # =========================================================================
    
    def check_consistency(
        self,
        proposed_answer: str,
        question: str
    ) -> tuple[bool, Optional[str]]:
        """
        Check if proposed answer is consistent with prior testimony.
        
        Per AGENTS.md: Maintain consistency with prior testimony.
        
        Args:
            proposed_answer: Answer being checked
            question: Question that prompted the answer
            
        Returns:
            (True, None) if consistent
            (False, inconsistency_description) if inconsistent
        """
        if not self.memory.testimony:
            return True, None
        
        # Use LLM to check consistency
        prior_summary = self._summarize_prior_testimony()
        
        check_prompt = f"""Check if this new answer is consistent with prior testimony.

PRIOR TESTIMONY:
{prior_summary}

NEW QUESTION: "{question}"
PROPOSED ANSWER: "{proposed_answer}"

Respond with EXACTLY one of:
- "CONSISTENT" if the answer does not contradict prior testimony
- "INCONSISTENT: [brief description of contradiction]" if it contradicts

Do not explain your reasoning beyond the brief description.
"""
        
        response = self._generate(
            "You are a consistency checking assistant. Respond only as instructed.",
            check_prompt,
            temperature=0.1,  # Very low for consistent analysis
            max_tokens=100
        )
        
        if response.startswith("CONSISTENT"):
            return True, None
        elif response.startswith("INCONSISTENT:"):
            description = response.replace("INCONSISTENT:", "").strip()
            return False, description
        
        # Default to consistent if unclear
        return True, None
    
    def is_in_affidavit(self, fact: str) -> bool:
        """
        Check if a fact is contained in the witness's affidavit.
        
        Per AGENTS.md: Cannot invent facts not in affidavit.
        
        Args:
            fact: The fact to check
            
        Returns:
            True if fact is in affidavit, False otherwise
        """
        # Use LLM for semantic check
        check_prompt = f"""Does the witness's affidavit contain or support this fact?

AFFIDAVIT:
{self.persona.affidavit}

FACT TO CHECK: "{fact}"

Respond with EXACTLY:
- "YES" if the affidavit contains or directly supports this fact
- "NO" if the affidavit does not contain or support this fact

Do not explain.
"""
        
        response = self._generate(
            "You are a fact-checking assistant. Respond only YES or NO.",
            check_prompt,
            temperature=0.1,
            max_tokens=10
        )
        
        return response.strip().upper() == "YES"
    
    # =========================================================================
    # STATE MANAGEMENT
    # =========================================================================
    
    def start_examination(
        self,
        questioner_side: Literal["plaintiff", "defense"]
    ) -> None:
        """
        Mark start of new examination phase.
        
        Args:
            questioner_side: Which side is examining
        """
        self._current_questioner = questioner_side
        self._questions_in_current_exam = 0
    
    def end_examination(self) -> None:
        """Mark end of current examination phase."""
        self._current_questioner = None
        self._questions_in_current_exam = 0
    
    def get_testimony_summary(self) -> Dict[str, Any]:
        """
        Get summary of all testimony given.
        
        Returns:
            Summary dict with testimony statistics
        """
        total = len(self.memory.testimony)
        by_phase = {}
        for phase in TESTIMONY_STATES:
            phase_testimony = self.memory.get_testimony_by_phase(phase)
            by_phase[phase.value] = len(phase_testimony)
        
        return {
            "witness_id": self.persona.witness_id,
            "witness_name": self.persona.name,
            "total_questions_answered": total,
            "questions_by_phase": by_phase,
            "stated_facts": dict(self.memory.stated_facts),
        }
    
    def clear_memory(self) -> None:
        """
        Clear all testimony memory.
        
        WARNING: Should only be used between sessions, not mid-trial.
        """
        self.memory = WitnessMemory()
        self._current_questioner = None
        self._questions_in_current_exam = 0


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_witness_agent(
    name: str,
    witness_id: str,
    affidavit: str,
    called_by: Literal["plaintiff", "defense"],
    witness_type: WitnessType = WitnessType.FACT_WITNESS,
    demeanor: Demeanor = Demeanor.CALM,
    nervousness: float = 0.3,
    difficulty: float = 0.3,
    **kwargs
) -> WitnessAgent:
    """
    Factory function to create a WitnessAgent.
    
    Per ARCHITECTURE.md - LLM Access:
    - Agents never hold API keys or call OpenAI directly
    - LLM access is handled internally via call_llm service
    
    Args:
        name: Witness's name
        witness_id: Unique identifier
        affidavit: The witness's affidavit text (source of truth)
        called_by: Which side called this witness
        witness_type: Type of witness
        demeanor: Witness demeanor
        nervousness: Nervousness level (0.0-1.0)
        difficulty: Difficulty level (0.0-1.0)
        **kwargs: Additional persona parameters
        
    Returns:
        Configured WitnessAgent
    """
    persona = WitnessPersona(
        name=name,
        witness_id=witness_id,
        affidavit=affidavit,
        called_by=called_by,
        witness_type=witness_type,
        demeanor=demeanor,
        nervousness=nervousness,
        difficulty=difficulty,
        **kwargs
    )
    
    return WitnessAgent(persona)
