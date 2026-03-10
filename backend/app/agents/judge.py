"""
Judge Agent

Per AGENTS.md Section 4:
- Responsibilities: Enforce rules, Rule on objections, Interrupt improper conduct, Score performance
- Behavior: Persona-driven authority, Minimal verbosity during trial, Detailed justification post-trial

Per SCORING.md:
- Exactly 3 JudgeAgents per panel
- Independent scoring, no shared memory
- Each category scored 1-10
- Must provide numeric scores + written justification
- Anti-Hallucination Rule: Only score what occurred in transcript + audio timeline

Per ARCHITECTURE.md - LLM Access:
- Agents never hold API keys or call OpenAI directly
- Agents communicate with LLM via backend service (call_llm)

Per AGENTS.md - Agent → LLM Communication:
- All agent calls to GPT-4.1 go through backend service
- Agents are unaware of API keys

Per AUDIO.md:
- Judge voice ALWAYS has priority
- Judges may interrupt any speaker
"""

from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field
from enum import Enum

from ..services.llm_service import call_llm, PersonaContext
from ..config import MODEL_MID, MODEL_NANO

from ..graph.trial_graph import (
    TrialState,
    TrialPhase,
    Role,
    TESTIMONY_STATES,
    VALID_OBJECTION_TYPES,
    validate_speaker,
    judge_interrupt,
    judge_yield,
)


# =============================================================================
# SCORING CATEGORIES (per SCORING.md Section 2)
# =============================================================================

class ScoringCategory(str, Enum):
    """Scoring categories. Original 7 from SCORING.md plus role-specific ones."""
    OPENING_CLARITY = "opening_clarity"
    DIRECT_EXAMINATION_EFFECTIVENESS = "direct_examination_effectiveness"
    CROSS_EXAMINATION_CONTROL = "cross_examination_control"
    OBJECTION_ACCURACY = "objection_accuracy"
    RESPONSIVENESS = "responsiveness"
    COURTROOM_PRESENCE = "courtroom_presence"
    CASE_THEORY_CONSISTENCY = "case_theory_consistency"
    # Opening-specific
    PERSUASIVENESS = "persuasiveness"
    FACTUAL_FOUNDATION = "factual_foundation"
    # Closing-specific
    CLOSING_PERSUASIVENESS = "closing_persuasiveness"
    EVIDENCE_INTEGRATION = "evidence_integration"
    REBUTTAL_EFFECTIVENESS = "rebuttal_effectiveness"
    # Witness-specific
    TESTIMONY_CONSISTENCY = "testimony_consistency"
    CREDIBILITY = "credibility"
    COMPOSURE_UNDER_PRESSURE = "composure_under_pressure"


ALL_SCORING_CATEGORIES = list(ScoringCategory)

# Role-specific category sets
OPENING_ATTORNEY_CATEGORIES = [
    ScoringCategory.OPENING_CLARITY,
    ScoringCategory.CASE_THEORY_CONSISTENCY,
    ScoringCategory.COURTROOM_PRESENCE,
    ScoringCategory.PERSUASIVENESS,
    ScoringCategory.FACTUAL_FOUNDATION,
]

DIRECT_CROSS_ATTORNEY_CATEGORIES = [
    ScoringCategory.DIRECT_EXAMINATION_EFFECTIVENESS,
    ScoringCategory.CROSS_EXAMINATION_CONTROL,
    ScoringCategory.OBJECTION_ACCURACY,
    ScoringCategory.RESPONSIVENESS,
    ScoringCategory.COURTROOM_PRESENCE,
]

CLOSING_ATTORNEY_CATEGORIES = [
    ScoringCategory.CLOSING_PERSUASIVENESS,
    ScoringCategory.EVIDENCE_INTEGRATION,
    ScoringCategory.REBUTTAL_EFFECTIVENESS,
    ScoringCategory.CASE_THEORY_CONSISTENCY,
    ScoringCategory.COURTROOM_PRESENCE,
]

WITNESS_CATEGORIES = [
    ScoringCategory.RESPONSIVENESS,
    ScoringCategory.COURTROOM_PRESENCE,
    ScoringCategory.TESTIMONY_CONSISTENCY,
    ScoringCategory.CREDIBILITY,
    ScoringCategory.COMPOSURE_UNDER_PRESSURE,
]


def get_categories_for_subrole(subrole: str) -> list:
    """Return the appropriate category list for an attorney sub-role or witness."""
    mapping = {
        "opening": OPENING_ATTORNEY_CATEGORIES,
        "direct_cross": DIRECT_CROSS_ATTORNEY_CATEGORIES,
        "closing": CLOSING_ATTORNEY_CATEGORIES,
        "witness": WITNESS_CATEGORIES,
    }
    return mapping.get(subrole, ALL_SCORING_CATEGORIES)


# =============================================================================
# SCORING DATA STRUCTURES
# =============================================================================

@dataclass
class CategoryScore:
    """Score for a single category."""
    category: ScoringCategory
    score: int  # 1-10 per SCORING.md
    justification: str  # Written justification per SCORING.md Section 4
    
    def __post_init__(self):
        if not 1 <= self.score <= 10:
            raise ValueError(f"Score must be 1-10, got {self.score}")


@dataclass
class Ballot:
    """
    Complete ballot from one judge.
    
    Per SCORING.md Section 4:
    - Numeric scores
    - Written justification per category
    """
    judge_id: str
    judge_name: str
    participant_role: Role
    participant_id: str  # Session participant identifier
    scores: Dict[ScoringCategory, CategoryScore] = field(default_factory=dict)
    overall_comments: str = ""
    
    def total_score(self) -> int:
        """Sum of all category scores."""
        return sum(cs.score for cs in self.scores.values())
    
    def average_score(self) -> float:
        """Average across categories."""
        if not self.scores:
            return 0.0
        return self.total_score() / len(self.scores)
    
    def is_complete(self) -> bool:
        """Check if all categories are scored."""
        return len(self.scores) == len(ALL_SCORING_CATEGORIES)


@dataclass
class ObjectionRuling:
    """Record of an objection ruling."""
    objection_type: str
    objecting_party: Role
    sustained: bool
    explanation: str
    timestamp: float = 0.0


# =============================================================================
# PERSONA PARAMETERS
# =============================================================================

class JudicialTemperament(str, Enum):
    """Judge temperament affecting courtroom demeanor."""
    STERN = "stern"          # Strict, low tolerance for errors
    PATIENT = "patient"      # Allows some leeway, educational
    FORMAL = "formal"        # By-the-book, procedural
    PRAGMATIC = "pragmatic"  # Focuses on substance over form


class ScoringStyle(str, Enum):
    """How the judge approaches scoring."""
    STRICT = "strict"        # High standards, scores trend lower
    BALANCED = "balanced"    # Fair middle-ground scoring
    GENEROUS = "generous"    # Focuses on positives, scores trend higher


@dataclass
class JudgePersona:
    """
    Persona parameters that shape judge behavior.
    
    Per SPEC.md Section 2: Persona parameters shape reasoning, speech style,
    voice output, and scoring bias.
    """
    name: str
    judge_id: str  # Unique identifier for the judge
    
    # Judicial characteristics
    temperament: JudicialTemperament = JudicialTemperament.FORMAL
    scoring_style: ScoringStyle = ScoringStyle.BALANCED
    
    # Authority level affects interruption frequency
    authority_level: float = 0.7  # 0.0 = permissive, 1.0 = very strict
    
    # Speech characteristics (for TTS persona conditioning)
    speaking_pace: float = 0.9  # Judges typically speak deliberately
    formality: float = 0.9      # High formality
    
    # Verbosity during trial (per AGENTS.md: minimal during trial)
    trial_verbosity: float = 0.3  # Low during trial
    
    # Verbosity for scoring feedback (per AGENTS.md: detailed post-trial)
    scoring_verbosity: float = 0.8  # Detailed for feedback
    
    # Background for consistent persona
    years_on_bench: int = 10
    judicial_philosophy: str = ""

    # Per-agent prep materials (loaded from DB)
    prep_materials: Dict[str, Any] = field(default_factory=dict)

    # Per-agent LLM overrides
    llm_model: Optional[str] = None
    llm_temperature: Optional[float] = None
    llm_max_tokens: Optional[int] = None
    custom_system_prompt: Optional[str] = None


# =============================================================================
# JUDGE AGENT
# =============================================================================

class JudgeAgent:
    """
    AI Judge Agent using GPT-4.1.
    
    Per AGENTS.md Section 4:
    - Enforce rules
    - Rule on objections
    - Interrupt improper conduct
    - Score performance
    - Minimal verbosity during trial
    - Detailed justification post-trial
    
    Per AUDIO.md:
    - Judge voice ALWAYS has priority
    - May interrupt any speaker
    
    Per SCORING.md:
    - Independent scoring (no shared memory with other judges)
    - Only score what occurred in transcript + audio timeline
    """
    
    MODEL = "gpt-4.1"  # Per README.md: OpenAI GPT-4.1 for all agents
    
    def __init__(
        self,
        persona: JudgePersona,
    ):
        """
        Initialize judge agent with persona.
        
        Per ARCHITECTURE.md - LLM Access:
        - Agents never hold API keys or call OpenAI directly
        - Agents communicate with LLM via backend service (call_llm)
        
        Args:
            persona: JudgePersona defining behavior parameters
        """
        self.persona = persona
        self.role = Role.JUDGE
        
        # Persona context for LLM service calls
        self._persona_context = PersonaContext(
            role="judge",
            name=persona.name,
            style=persona.temperament.value,
            authority=persona.authority_level,
            nervousness=0.0,
            formality=persona.formality,
            additional_traits={
                "strictness": persona.authority_level,  # Use authority_level as strictness
                "verbosity": persona.trial_verbosity,
            }
        )
        
        # Track rulings for consistency
        self._objection_rulings: List[ObjectionRuling] = []
        
        # Track interruptions issued
        self._interruptions_issued: int = 0
        
        # Ballots produced (one per participant scored)
        self._ballots: Dict[str, Ballot] = {}
    
    # =========================================================================
    # CORE GENERATION METHOD
    # =========================================================================
    
    def _generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.5,
        max_tokens: int = 300,
        model: str = None
    ) -> str:
        """Generate text response via backend LLM service with per-agent overrides."""
        resolved_model = self.persona.llm_model or model or self.MODEL
        if resolved_model != MODEL_NANO and self.persona.custom_system_prompt:
            system_prompt = self.persona.custom_system_prompt + "\n\n" + system_prompt
        return call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            persona=self._persona_context if resolved_model != MODEL_NANO else None,
            temperature=self.persona.llm_temperature if self.persona.llm_temperature is not None else temperature,
            max_tokens=self.persona.llm_max_tokens if self.persona.llm_max_tokens is not None else max_tokens,
            model=resolved_model,
        )
    
    def _build_system_prompt(self, context: str, is_scoring: bool = False) -> str:
        """
        Build system prompt incorporating persona parameters.
        
        Args:
            context: Situation-specific context
            is_scoring: Whether this is for scoring (affects verbosity)
        """
        temperament_instructions = {
            JudicialTemperament.STERN: (
                "You are stern and have low tolerance for errors. "
                "You expect proper procedure at all times. "
                "You do not suffer fools gladly."
            ),
            JudicialTemperament.PATIENT: (
                "You are patient and allow some leeway for learning. "
                "You may offer brief guidance when appropriate. "
                "You remain calm even when frustrated."
            ),
            JudicialTemperament.FORMAL: (
                "You are formal and procedural. "
                "You follow the rules exactly. "
                "You maintain judicial decorum at all times."
            ),
            JudicialTemperament.PRAGMATIC: (
                "You focus on substance over form. "
                "You care more about justice than procedure. "
                "You may overlook minor technical violations."
            ),
        }
        
        scoring_instructions = {
            ScoringStyle.STRICT: (
                "You have high standards. A score of 7 represents good work. "
                "Scores of 9-10 are reserved for exceptional performance. "
                "You do not give points for merely adequate work."
            ),
            ScoringStyle.BALANCED: (
                "You score fairly in the middle range. "
                "5 is average, 7 is good, 9-10 is exceptional. "
                "You weigh positives and negatives equally."
            ),
            ScoringStyle.GENEROUS: (
                "You focus on what participants did well. "
                "You give credit for effort and improvement. "
                "You score on the higher end when in doubt."
            ),
        }
        
        verbosity = self.persona.scoring_verbosity if is_scoring else self.persona.trial_verbosity
        verbosity_instruction = (
            "Be detailed and thorough in your explanations." if verbosity > 0.6
            else "Be concise but complete." if verbosity > 0.3
            else "Be brief and to the point. Use minimal words."
        )
        
        return f"""You are Judge {self.persona.name}, presiding over this mock trial.

ROLE AND AUTHORITY:
- You are the judicial authority in this courtroom
- Your rulings are final
- You may interrupt any speaker at any time
- All participants must obey your instructions immediately

JUDICIAL TEMPERAMENT:
{temperament_instructions[self.persona.temperament]}

{"SCORING APPROACH:" if is_scoring else ""}
{scoring_instructions[self.persona.scoring_style] if is_scoring else ""}

SPEECH STYLE:
- {verbosity_instruction}
- Maintain judicial formality
- Do not explain your reasoning during trial unless ruling on an objection
- Text will be converted to speech via TTS

CONSTRAINTS:
- You CANNOT advocate for either side
- You CANNOT suggest questions or strategy
- You MUST rule consistently on similar objections
- During trial: minimal verbosity
- Post-trial scoring: detailed justification required

BACKGROUND:
- Years on the bench: {self.persona.years_on_bench}
{self.persona.judicial_philosophy}

{self._format_prep_for_prompt()}

{context}
"""
    
    # =========================================================================
    # TRIAL STATE VALIDATION
    # =========================================================================
    
    def can_act(self, state: TrialState) -> tuple[bool, Optional[str]]:
        """
        Check if judge can act. Judge can always act.
        
        Per AUDIO.md: Judge voice ALWAYS has priority.
        """
        return True, None  # Judge can always act
    
    def _format_prep_for_prompt(self) -> str:
        """Format judge's prep materials into a prompt section."""
        prep = self.persona.prep_materials
        if not prep:
            return ""
        parts = ["\n=== CASE-SPECIFIC JUDICIAL NOTES ==="]
        for key, value in prep.items():
            if isinstance(value, list):
                items = "\n".join(f"  - {v}" for v in value[:8])
                parts.append(f"{key.replace('_', ' ').title()}:\n{items}")
            elif isinstance(value, str) and value:
                parts.append(f"{key.replace('_', ' ').title()}: {value}")
        parts.append("=== END JUDICIAL NOTES ===\n")
        return "\n".join(parts)

    # =========================================================================
    # OBJECTION RULINGS
    # =========================================================================
    
    def rule_on_objection(
        self,
        state: TrialState,
        objection_type: str,
        objecting_party: Role,
        question_or_testimony: str,
        context: Dict[str, Any],
        trial_memory=None,
    ) -> tuple[bool, str]:
        """
        Rule on an objection.
        
        Per AGENTS.md: Rule on objections.
        
        Args:
            state: Current trial state
            objection_type: Type of objection raised
            objecting_party: Who raised the objection
            question_or_testimony: The objected-to content
            context: Additional context (examination type, witness, etc.)
            trial_memory: Optional TrialMemory for recording ruling
            
        Returns:
            (sustained: bool, ruling_text: str for TTS)
        """
        if objection_type not in VALID_OBJECTION_TYPES:
            # Invalid objection type
            return False, "Overruled. That is not a recognized objection."
        
        # Check for consistency with prior rulings on same type
        similar_rulings = [
            r for r in self._objection_rulings 
            if r.objection_type == objection_type
        ]
        
        exam_type = context.get("examination_type", "unknown")
        is_cross = "cross" in exam_type.lower()
        
        ruling_context = f"""
OBJECTION RAISED:
- Type: {objection_type}
- By: {objecting_party.value}
- Phase: {state.phase.value}
- Examination type: {exam_type}

OBJECTED-TO CONTENT:
"{question_or_testimony}"

ADDITIONAL CONTEXT:
- Witness: {context.get('witness_name', 'Unknown')}
- This is {"cross-examination (leading questions ARE allowed)" if is_cross else "direct examination (leading questions are NOT allowed)"}

PRIOR RULINGS ON {objection_type.upper()} (for consistency):
{self._format_prior_rulings(similar_rulings) if similar_rulings else "No prior rulings on this objection type."}

OBJECTION RULES:
- hearsay: Out-of-court statements offered for truth
- leading: Questions suggesting the answer (allowed on cross, not on direct)
- relevance: Evidence must relate to facts at issue
- speculation: Witness cannot guess or speculate
- asked_and_answered: Question already answered
- compound: Multiple questions in one
- argumentative: Attorney arguing rather than questioning
- assumes_facts: Question assumes unproven facts
- beyond_scope: Cross limited to direct scope; redirect limited to cross scope
- narrative: Witness giving long uncontrolled answer
- non_responsive: Witness not answering the question asked

Analyze whether the objection is valid and rule accordingly.
"""
        
        system_prompt = self._build_system_prompt(ruling_context, is_scoring=False)
        
        analysis_prompt = f"""Rule on this objection.

First, determine if the objection is valid based on the rules.
Then provide your ruling.

Respond in this EXACT format:
RULING: [SUSTAINED or OVERRULED]
SPOKEN: [What you say aloud - brief, judicial]

Example responses:
RULING: SUSTAINED
SPOKEN: Sustained. Rephrase your question, counsel.

RULING: OVERRULED
SPOKEN: Overruled. The witness may answer.
"""
        
        response = self._generate(
            system_prompt,
            analysis_prompt,
            temperature=0.3,  # Consistent rulings
            max_tokens=150,
            model=MODEL_MID
        )
        
        # Parse response
        sustained = "SUSTAINED" in response.upper().split("RULING:")[1].split("\n")[0] if "RULING:" in response.upper() else False
        
        # Extract spoken portion
        if "SPOKEN:" in response:
            spoken = response.split("SPOKEN:")[1].strip()
        else:
            spoken = "Sustained." if sustained else "Overruled."
        
        # Record ruling for consistency
        self._objection_rulings.append(ObjectionRuling(
            objection_type=objection_type,
            objecting_party=objecting_party,
            sustained=sustained,
            explanation=spoken,
        ))

        # Record to trial memory and update attorney performance
        if trial_memory is not None:
            objecting_side = "plaintiff" if objecting_party in (
                Role.ATTORNEY_PLAINTIFF,
            ) else "defense"
            trial_memory.record_objection(
                objection_type=objection_type,
                by_side=objecting_side,
                sustained=sustained,
                phase=state.phase.value,
                context_text=question_or_testimony[:200],
                judge_explanation=spoken,
                witness_id=getattr(state, "current_witness_id", None),
            )
        
        return sustained, spoken
    
    def _format_prior_rulings(self, rulings: List[ObjectionRuling]) -> str:
        """Format prior rulings for context."""
        if not rulings:
            return "None"
        
        lines = []
        for r in rulings[-5:]:  # Last 5 relevant rulings
            lines.append(f"- {'Sustained' if r.sustained else 'Overruled'}: {r.explanation}")
        return "\n".join(lines)
    
    # =========================================================================
    # INTERRUPTS
    # =========================================================================
    
    def should_interrupt(
        self,
        state: TrialState,
        current_speech: str,
        speaker_role: Role,
        context: Dict[str, Any]
    ) -> Optional[str]:
        """
        Determine if judge should interrupt current speaker.
        
        Per AUDIO.md Section 4: Judges may interrupt any speaker.
        Per AGENTS.md: Interrupt improper conduct.
        
        Args:
            state: Current trial state
            current_speech: What is currently being said
            speaker_role: Who is speaking
            context: Additional context
            
        Returns:
            Interrupt text for TTS if should interrupt, None otherwise
        """
        # Check based on authority level
        # Higher authority = more likely to interrupt
        
        interrupt_context = f"""
CURRENT SITUATION:
- Phase: {state.phase.value}
- Speaker: {speaker_role.value}
- Current speech: "{current_speech}"

REASONS TO INTERRUPT:
- Speaking out of turn
- Improper argument during opening (should be previewing, not arguing)
- Improper examination technique
- Disrespectful behavior
- Non-responsive answer continuing too long
- Witness volunteering information not asked
- Attorney making speaking objections
- Testimony about facts not in evidence

Your authority level: {self.persona.authority_level} (higher = stricter)

Should you interrupt? Only interrupt for clear rule violations.
Respond with:
INTERRUPT: [text to speak]
or
NO INTERRUPT
"""
        
        response = self._generate(
            self._build_system_prompt(interrupt_context),
            "Decide whether to interrupt.",
            temperature=0.4,
            max_tokens=100,
            model=MODEL_NANO
        )
        
        if response.startswith("INTERRUPT:"):
            interrupt_text = response.replace("INTERRUPT:", "").strip()
            self._interruptions_issued += 1
            return interrupt_text
        
        return None
    
    def generate_interrupt(self, reason: str) -> str:
        """
        Generate interrupt statement.
        
        Per AUDIO.md: Interrupted audio must stop immediately.
        
        Args:
            reason: Reason for interrupt
            
        Returns:
            Interrupt text for TTS
        """
        # Brief, authoritative interrupts
        interrupt_templates = {
            "out_of_turn": "Counsel, you are out of turn.",
            "argumentative": "Counsel, save argument for closing.",
            "leading": "That's a leading question on direct, counsel.",
            "non_responsive": "The witness will answer the question that was asked.",
            "narrative": "The witness will confine their answer to the question.",
            "improper_conduct": "Counsel, that is improper.",
            "decorum": "I will have order in my courtroom.",
        }
        
        if reason in interrupt_templates:
            return interrupt_templates[reason]
        
        # Generate custom interrupt
        return self._generate(
            self._build_system_prompt(f"Reason for interrupt: {reason}"),
            "Generate a brief judicial interrupt statement.",
            temperature=0.5,
            max_tokens=50,
            model=MODEL_NANO
        )
    
    # =========================================================================
    # PROCEDURAL STATEMENTS
    # =========================================================================
    
    def call_case(self, case_name: str) -> str:
        """Generate statement to call the case."""
        return f"This court is now in session. The matter before us is {case_name}."
    
    def swear_witness(self, witness_name: str) -> str:
        """Generate oath administration."""
        return (
            f"{witness_name}, please raise your right hand. "
            "Do you swear or affirm that the testimony you are about to give "
            "is the truth, the whole truth, and nothing but the truth?"
        )
    
    def instruct_proceed(self, to_whom: str) -> str:
        """Instruct a party to proceed."""
        return f"{to_whom}, you may proceed."
    
    def announce_recess(self) -> str:
        """Announce recess."""
        return "Court is in recess."
    
    def announce_closing_instructions(self) -> str:
        """Instructions before closing arguments."""
        return "We will now hear closing arguments. Plaintiff, you may proceed."
    
    def thank_jury(self) -> str:
        """Thank jury after trial."""
        return "Thank you, members of the jury. This trial is now concluded."

    def generate_verdict(
        self,
        prosecution_avg: float,
        defense_avg: float,
        prosecution_details: Dict[str, float],
        defense_details: Dict[str, float],
        case_name: str = "",
        transcript_summary: str = "",
    ) -> str:
        """Generate a verdict announcement based on scored performance.

        This is a mock trial performance verdict — not a legal guilty/not-guilty
        finding. The judge announces which team performed better overall and
        highlights the decisive scoring categories.
        """
        winner = "Prosecution" if prosecution_avg > defense_avg else "Defense"
        margin = abs(prosecution_avg - defense_avg)

        top_pros = sorted(prosecution_details.items(), key=lambda x: x[1], reverse=True)[:3]
        top_def = sorted(defense_details.items(), key=lambda x: x[1], reverse=True)[:3]

        prompt = f"""You are Judge {self.persona.name} presiding over a mock trial competition.
The trial is complete and all participants have been scored by the judicial panel.

CASE: {case_name or "Mock Trial Case"}

SCORING RESULTS:
- Prosecution average: {prosecution_avg:.1f}/10
- Defense average: {defense_avg:.1f}/10
- Winning team: {winner} (by {margin:.1f} points)

Prosecution strengths: {', '.join(f'{c.replace("_"," ").title()} ({s:.1f})' for c,s in top_pros)}
Defense strengths: {', '.join(f'{c.replace("_"," ").title()} ({s:.1f})' for c,s in top_def)}

{f"TRIAL HIGHLIGHTS: {transcript_summary}" if transcript_summary else ""}

Deliver a VERDICT ANNOUNCEMENT (150-250 words) that:
1. Addresses the courtroom formally
2. Acknowledges BOTH teams' efforts with specific praise
3. Announces the {winner} as the winner and explains why based on the scores
4. Highlights 2-3 decisive scoring categories that determined the outcome
5. Offers brief constructive feedback for the losing team
6. Concludes with an encouraging remark about the competition

Use the tone of a {self.persona.temperament.value} judge. Speak directly — this goes to TTS."""

        persona_context = PersonaContext(
            role="judge",
            name=self.persona.name,
            style="authoritative",
            authority=self.persona.authority_level,
            formality=0.9,
        )

        try:
            return call_llm(
                system_prompt=f"You are Judge {self.persona.name}, a {self.persona.temperament.value} mock trial judge delivering the final verdict.",
                user_prompt=prompt,
                persona=persona_context,
                max_tokens=400,
                temperature=0.7,
            )
        except Exception as e:
            return (
                f"This court finds that the {winner} has prevailed in this mock trial "
                f"with an average score of {max(prosecution_avg, defense_avg):.1f} to "
                f"{min(prosecution_avg, defense_avg):.1f}. Both teams showed excellent "
                f"preparation and advocacy. This trial is now concluded."
            )
    
    # =========================================================================
    # SCORING (per SCORING.md)
    # =========================================================================
    
    def score_participant(
        self,
        participant_role: Role,
        participant_id: str,
        transcript: List[Dict[str, Any]],
        audio_metrics: Optional[Dict[str, Any]] = None,
        trial_memory=None,
        categories: Optional[List[ScoringCategory]] = None,
    ) -> Ballot:
        """
        Score a participant's performance.
        
        Args:
            participant_role: Role being scored
            participant_id: Identifier for the participant
            transcript: Full trial transcript
            audio_metrics: Optional audio analysis data
            trial_memory: Optional TrialMemory for live performance observations
            categories: Specific categories to score (defaults to ALL if None)
            
        Returns:
            Complete Ballot with all scores and justifications
        """
        ballot = Ballot(
            judge_id=self.persona.judge_id,
            judge_name=self.persona.name,
            participant_role=participant_role,
            participant_id=participant_id,
        )
        
        participant_transcript = self._extract_participant_transcript(
            transcript, participant_role
        )

        memory_context = ""
        if trial_memory is not None:
            memory_context = trial_memory.build_scoring_context()
        
        cats_to_score = categories or ALL_SCORING_CATEGORIES
        batch_results = self._score_all_categories(
            cats_to_score,
            participant_role,
            participant_transcript,
            transcript,
            audio_metrics,
            memory_context=memory_context,
        )
        for category, (score, justification) in batch_results.items():
            ballot.scores[category] = CategoryScore(
                category=category,
                score=score,
                justification=justification,
            )

        ballot.overall_comments = self._generate_overall_comments(
            participant_role,
            ballot.scores,
            participant_transcript
        )
        
        self._ballots[participant_id] = ballot
        
        return ballot
    
    def _extract_participant_transcript(
        self,
        transcript: List[Dict[str, Any]],
        role: Role
    ) -> List[Dict[str, Any]]:
        """Extract transcript entries for a specific participant."""
        return [
            entry for entry in transcript
            if entry.get("role") == role.value
        ]
    
    def _score_all_categories(
        self,
        categories: List[ScoringCategory],
        participant_role: Role,
        participant_transcript: List[Dict[str, Any]],
        full_transcript: List[Dict[str, Any]],
        audio_metrics: Optional[Dict[str, Any]],
        memory_context: str = "",
    ) -> Dict[ScoringCategory, tuple]:
        """Score ALL categories in a single LLM call and return a dict of (score, justification)."""
        import json as _json

        all_transcript = self._format_transcript_for_scoring(participant_transcript)
        if not all_transcript or all_transcript == "No transcript entries.":
            return {c: (5, "No relevant activity observed for this category.") for c in categories}

        cat_defs = "\n".join(
            f"- {c.value}: {self._get_category_definition(c)}" for c in categories
        )

        audio_context = ""
        if audio_metrics:
            audio_context = (
                f"AUDIO: confidence={audio_metrics.get('confidence','N/A')}, "
                f"clarity={audio_metrics.get('clarity','N/A')}"
            )

        memory_section = f"\nLIVE OBSERVATIONS:\n{memory_context}" if memory_context else ""

        scoring_context = f"""SCORING TASK — score the participant on ALL categories at once.
Participant: {participant_role.value}
Scale: 1-10

CATEGORIES TO SCORE:
{cat_defs}

TRANSCRIPT (ONLY evidence you may use):
{all_transcript}
{audio_context}{memory_section}

SCORING STYLE: {self._get_scoring_style_instruction()}

Respond with ONLY a JSON object mapping each category key to {{"score": <1-10>, "justification": "<2-3 sentences>"}}.
Example: {{"opening_clarity": {{"score": 7, "justification": "Clear roadmap..."}}}}
"""
        system_prompt = self._build_system_prompt(scoring_context, is_scoring=True)
        response = self._generate(
            system_prompt,
            "Score all categories now. Return ONLY valid JSON.",
            temperature=0.4,
            max_tokens=200 * len(categories),
            model=MODEL_MID,
        )

        results: Dict[ScoringCategory, tuple] = {}
        try:
            start = response.find("{")
            end = response.rfind("}") + 1
            if start >= 0 and end > start:
                data = _json.loads(response[start:end])
                for cat in categories:
                    entry = data.get(cat.value, {})
                    if isinstance(entry, dict):
                        s = max(1, min(10, int(entry.get("score", 5))))
                        j = str(entry.get("justification", ""))
                        results[cat] = (s, j)
        except Exception:
            pass

        for cat in categories:
            if cat not in results:
                results[cat] = (5, "Scoring unavailable for this category.")
        return results

    def _score_category(
        self,
        category: ScoringCategory,
        participant_role: Role,
        participant_transcript: List[Dict[str, Any]],
        full_transcript: List[Dict[str, Any]],
        audio_metrics: Optional[Dict[str, Any]],
        memory_context: str = "",
    ) -> tuple[int, str]:
        """
        Score a single category.
        
        Per SCORING.md Section 5: Anti-Hallucination Rule
        Only score what occurred in transcript + audio timeline.
        
        Returns:
            (score: 1-10, justification: str)
        """
        # Get relevant transcript portions for this category
        relevant_phases = self._get_relevant_phases_for_category(category)
        relevant_transcript = [
            entry for entry in participant_transcript
            if entry.get("phase") in [p.value for p in relevant_phases]
        ]
        
        if not relevant_transcript:
            return 5, "No relevant activity observed for this category."
        
        # Format transcript for analysis
        transcript_text = self._format_transcript_for_scoring(relevant_transcript)
        
        # Audio metrics context
        audio_context = ""
        if audio_metrics:
            audio_context = f"""
AUDIO ANALYSIS (per SCORING.md Section 3):
- Confidence: {audio_metrics.get('confidence', 'N/A')}
- Clarity: {audio_metrics.get('clarity', 'N/A')}
- Control under interruption: {audio_metrics.get('control', 'N/A')}
- Professional tone: {audio_metrics.get('tone', 'N/A')}
"""

        # Live performance observations from trial memory
        memory_section = ""
        if memory_context:
            memory_section = f"""
LIVE PERFORMANCE OBSERVATIONS:
{memory_context}
"""
        
        scoring_context = f"""
SCORING TASK:
- Category: {category.value.replace('_', ' ').title()}
- Participant: {participant_role.value}
- Scale: 1-10 (per SCORING.md)

CATEGORY DEFINITION:
{self._get_category_definition(category)}

RELEVANT TRANSCRIPT (this is the ONLY evidence you may consider):
{transcript_text}

{audio_context}
{memory_section}
ANTI-HALLUCINATION RULE (SCORING.md Section 5):
You may ONLY score what occurred in the transcript and audio timeline.
Do NOT invent or assume things that did not happen.
If you cannot assess this category from the evidence, score 5 and explain why.

YOUR SCORING STYLE:
{self._get_scoring_style_instruction()}
"""
        
        system_prompt = self._build_system_prompt(scoring_context, is_scoring=True)
        
        scoring_prompt = f"""Score this participant on {category.value.replace('_', ' ')}.

Respond in this EXACT format:
SCORE: [1-10]
JUSTIFICATION: [2-4 sentences explaining the score based ONLY on observed evidence]

Be specific. Reference actual moments from the transcript.
"""
        
        response = self._generate(
            system_prompt,
            scoring_prompt,
            temperature=0.4,  # Consistent scoring
            max_tokens=250,
            model=MODEL_MID
        )
        
        # Parse response
        try:
            score_line = [l for l in response.split("\n") if "SCORE:" in l][0]
            score = int(score_line.split("SCORE:")[1].strip().split()[0])
            score = max(1, min(10, score))  # Clamp to 1-10
        except (IndexError, ValueError):
            score = 5  # Default if parsing fails
        
        try:
            justification = response.split("JUSTIFICATION:")[1].strip()
        except IndexError:
            justification = response
        
        return score, justification
    
    def _get_relevant_phases_for_category(
        self,
        category: ScoringCategory
    ) -> List[TrialPhase]:
        """Map scoring category to relevant trial phases."""
        mapping = {
            ScoringCategory.OPENING_CLARITY: [TrialPhase.OPENING],
            ScoringCategory.DIRECT_EXAMINATION_EFFECTIVENESS: [
                TrialPhase.DIRECT, TrialPhase.REDIRECT
            ],
            ScoringCategory.CROSS_EXAMINATION_CONTROL: [
                TrialPhase.CROSS, TrialPhase.RECROSS
            ],
            ScoringCategory.OBJECTION_ACCURACY: list(TESTIMONY_STATES),
            ScoringCategory.RESPONSIVENESS: list(TESTIMONY_STATES) + [TrialPhase.OPENING, TrialPhase.CLOSING],
            ScoringCategory.COURTROOM_PRESENCE: [
                TrialPhase.OPENING, TrialPhase.DIRECT, TrialPhase.CROSS,
                TrialPhase.REDIRECT, TrialPhase.RECROSS, TrialPhase.CLOSING
            ],
            ScoringCategory.CASE_THEORY_CONSISTENCY: [
                TrialPhase.OPENING, TrialPhase.CLOSING
            ],
            ScoringCategory.PERSUASIVENESS: [TrialPhase.OPENING],
            ScoringCategory.FACTUAL_FOUNDATION: [TrialPhase.OPENING],
            ScoringCategory.CLOSING_PERSUASIVENESS: [TrialPhase.CLOSING],
            ScoringCategory.EVIDENCE_INTEGRATION: [TrialPhase.CLOSING],
            ScoringCategory.REBUTTAL_EFFECTIVENESS: [TrialPhase.CLOSING],
            ScoringCategory.TESTIMONY_CONSISTENCY: list(TESTIMONY_STATES),
            ScoringCategory.CREDIBILITY: list(TESTIMONY_STATES),
            ScoringCategory.COMPOSURE_UNDER_PRESSURE: [
                TrialPhase.CROSS, TrialPhase.RECROSS
            ],
        }
        return mapping.get(category, [])
    
    def _get_category_definition(self, category: ScoringCategory) -> str:
        """Get scoring criteria for a category."""
        definitions = {
            ScoringCategory.OPENING_CLARITY: (
                "How clearly did the advocate preview their case theory? "
                "Was the opening organized, compelling, and appropriate "
                "(previewing, not arguing)?"
            ),
            ScoringCategory.DIRECT_EXAMINATION_EFFECTIVENESS: (
                "How effectively did the advocate elicit testimony on direct? "
                "Were questions open-ended and non-leading? "
                "Did they build the witness's story logically?"
            ),
            ScoringCategory.CROSS_EXAMINATION_CONTROL: (
                "How well did the advocate control the witness on cross? "
                "Were questions leading and pointed? "
                "Did they advance their case theory and undermine the witness?"
            ),
            ScoringCategory.OBJECTION_ACCURACY: (
                "Were objections raised appropriately and on valid grounds? "
                "Were improper questions challenged? "
                "Were frivolous objections avoided?"
            ),
            ScoringCategory.RESPONSIVENESS: (
                "How well did the participant respond to questions, "
                "objections, and court instructions? "
                "Were answers direct and on-point?"
            ),
            ScoringCategory.COURTROOM_PRESENCE: (
                "How professional was the participant's demeanor? "
                "Consider confidence, poise, and appropriate courtroom behavior."
            ),
            ScoringCategory.CASE_THEORY_CONSISTENCY: (
                "Was the case theory clear and consistent throughout? "
                "Did opening and closing arguments align? "
                "Did examination support the stated theory?"
            ),
            ScoringCategory.PERSUASIVENESS: (
                "How persuasive was the opening statement? "
                "Did the advocate capture attention, tell a compelling story, "
                "and make the audience want to hear more?"
            ),
            ScoringCategory.FACTUAL_FOUNDATION: (
                "Did the opening properly preview the facts the advocate intends to prove? "
                "Was the factual roadmap clear, accurate, and well-organized?"
            ),
            ScoringCategory.CLOSING_PERSUASIVENESS: (
                "How persuasive was the closing argument? "
                "Did the advocate effectively summarize the case, appeal to logic and emotion, "
                "and deliver a compelling final message?"
            ),
            ScoringCategory.EVIDENCE_INTEGRATION: (
                "How well did the closing argument weave in evidence and testimony presented at trial? "
                "Were key exhibits and witness statements referenced effectively?"
            ),
            ScoringCategory.REBUTTAL_EFFECTIVENESS: (
                "How effectively did the closing address and rebut the opposing side's arguments? "
                "Were weaknesses in the opponent's case highlighted?"
            ),
            ScoringCategory.TESTIMONY_CONSISTENCY: (
                "Was the witness's testimony internally consistent? "
                "Did answers align with prior statements and established facts? "
                "Were there contradictions?"
            ),
            ScoringCategory.CREDIBILITY: (
                "How believable was the witness? "
                "Did the witness come across as honest, knowledgeable, and trustworthy? "
                "Did demeanor and substance support credibility?"
            ),
            ScoringCategory.COMPOSURE_UNDER_PRESSURE: (
                "How well did the witness handle challenging cross-examination? "
                "Did they maintain composure, avoid getting flustered, "
                "and give measured, appropriate responses?"
            ),
        }
        return definitions.get(category, "")
    
    def _get_scoring_style_instruction(self) -> str:
        """Get scoring style instruction based on persona."""
        instructions = {
            ScoringStyle.STRICT: (
                "You score strictly. 7 is good work. 9-10 is reserved for exceptional performance. "
                "Do not inflate scores."
            ),
            ScoringStyle.BALANCED: (
                "You score fairly. 5 is average, 7 is good, 9-10 is exceptional. "
                "Weight positives and negatives equally."
            ),
            ScoringStyle.GENEROUS: (
                "You focus on strengths. Give credit for effort. "
                "Score on the higher end when performance is adequate."
            ),
        }
        return instructions.get(self.persona.scoring_style, "")
    
    def _format_transcript_for_scoring(
        self,
        transcript: List[Dict[str, Any]]
    ) -> str:
        """Format transcript entries for scoring analysis."""
        if not transcript:
            return "No transcript entries."
        
        lines = []
        for entry in transcript[-30:]:  # Last 30 entries for context
            phase = entry.get("phase", "unknown")
            text = entry.get("text", "")[:500]  # Truncate long entries
            lines.append(f"[{phase}] {text}")
        
        return "\n".join(lines)
    
    def _generate_overall_comments(
        self,
        participant_role: Role,
        scores: Dict[ScoringCategory, CategoryScore],
        participant_transcript: List[Dict[str, Any]]
    ) -> str:
        """
        Generate overall comments for the ballot.
        
        Per AGENTS.md: Detailed justification post-trial.
        """
        # Calculate summary stats
        avg_score = sum(cs.score for cs in scores.values()) / len(scores) if scores else 5.0
        
        # Find strengths and weaknesses
        sorted_scores = sorted(scores.items(), key=lambda x: x[1].score, reverse=True)
        strengths = [s[0].value for s in sorted_scores[:2]]
        weaknesses = [s[0].value for s in sorted_scores[-2:]]
        
        context = f"""
PARTICIPANT: {participant_role.value}
AVERAGE SCORE: {avg_score:.1f}
STRONGEST CATEGORIES: {', '.join(strengths)}
WEAKEST CATEGORIES: {', '.join(weaknesses)}

Generate 2-3 sentences of overall feedback summarizing this participant's performance.
Be constructive and specific.
"""
        
        return self._generate(
            self._build_system_prompt(context, is_scoring=True),
            "Write overall comments for this ballot.",
            temperature=0.6,
            max_tokens=200,
            model=MODEL_MID
        )
    
    # =========================================================================
    # BALLOT RETRIEVAL
    # =========================================================================
    
    def get_ballot(self, participant_id: str) -> Optional[Ballot]:
        """Get ballot for a participant."""
        return self._ballots.get(participant_id)
    
    def get_all_ballots(self) -> Dict[str, Ballot]:
        """Get all ballots produced by this judge."""
        return dict(self._ballots)
    
    # =========================================================================
    # VERBAL FEEDBACK
    # =========================================================================
    
    def generate_verbal_feedback(
        self,
        participant_role: Role,
        ballot: Ballot
    ) -> str:
        """
        Generate spoken feedback for TTS delivery.
        
        Per AGENTS.md: Detailed justification post-trial.
        
        Args:
            participant_role: Role being addressed
            ballot: The completed ballot
            
        Returns:
            Verbal feedback text for TTS
        """
        # Summary of scores
        scores_summary = "\n".join([
            f"- {cat.value.replace('_', ' ').title()}: {cs.score}/10"
            for cat, cs in ballot.scores.items()
        ])
        
        context = f"""
You are delivering verbal feedback to the {participant_role.value}.

SCORES:
{scores_summary}

OVERALL: {ballot.average_score():.1f}/10

Generate spoken feedback that:
1. Acknowledges what they did well
2. Identifies areas for improvement
3. Is constructive and professional
4. Is appropriate for spoken delivery (2-3 paragraphs)
"""
        
        return self._generate(
            self._build_system_prompt(context, is_scoring=True),
            "Deliver your verbal feedback.",
            temperature=0.6,
            max_tokens=400
        )


# =============================================================================
# JUDGE PANEL (per SCORING.md Section 1)
# =============================================================================

class JudgePanel:
    """
    Panel of 3 JudgeAgents for scoring.
    
    Per SCORING.md Section 1:
    - Exactly 3 JudgeAgents
    - Independent scoring
    - No shared memory between judges
    """
    
    def __init__(self, judges: List[JudgeAgent]):
        """
        Initialize judge panel.
        
        Args:
            judges: Exactly 3 JudgeAgents
        """
        if len(judges) != 3:
            raise ValueError(f"Panel must have exactly 3 judges, got {len(judges)}")
        
        self.judges = judges
    
    def score_participant(
        self,
        participant_role: Role,
        participant_id: str,
        transcript: List[Dict[str, Any]],
        audio_metrics: Optional[Dict[str, Any]] = None,
        trial_memory=None,
    ) -> List[Ballot]:
        """
        Score participant with all 3 judges.
        
        Per SCORING.md: Independent scoring, no shared memory.
        
        Returns:
            List of 3 ballots, one from each judge
        """
        ballots = []
        for judge in self.judges:
            ballot = judge.score_participant(
                participant_role,
                participant_id,
                transcript,
                audio_metrics,
                trial_memory=trial_memory,
            )
            ballots.append(ballot)
        return ballots
    
    def calculate_final_scores(
        self,
        ballots: List[Ballot]
    ) -> Dict[ScoringCategory, float]:
        """
        Calculate final scores as average of all judges.
        
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
        
        return final_scores
    
    def get_overall_average(self, ballots: List[Ballot]) -> float:
        """Get overall average across all categories and judges."""
        all_scores = []
        for ballot in ballots:
            for cs in ballot.scores.values():
                all_scores.append(cs.score)
        
        return sum(all_scores) / len(all_scores) if all_scores else 0.0


# =============================================================================
# FACTORY FUNCTIONS
# =============================================================================

def create_judge_agent(
    name: str,
    judge_id: str,
    temperament: JudicialTemperament = JudicialTemperament.FORMAL,
    scoring_style: ScoringStyle = ScoringStyle.BALANCED,
    authority_level: float = 0.7,
    **kwargs
) -> JudgeAgent:
    """
    Factory function to create a JudgeAgent.
    
    Per ARCHITECTURE.md - LLM Access:
    - Agents never hold API keys or call OpenAI directly
    - LLM access is handled internally via call_llm service
    
    Args:
        name: Judge's name
        judge_id: Unique identifier
        temperament: Judicial temperament
        scoring_style: How the judge scores
        authority_level: How strict (0.0-1.0)
        **kwargs: Additional persona parameters
        
    Returns:
        Configured JudgeAgent
    """
    persona = JudgePersona(
        name=name,
        judge_id=judge_id,
        temperament=temperament,
        scoring_style=scoring_style,
        authority_level=authority_level,
        **kwargs
    )
    
    return JudgeAgent(persona)


def create_judge_panel(
    judge_configs: Optional[List[Dict[str, Any]]] = None,
) -> JudgePanel:
    """
    Create a panel of 3 judges.
    
    Per SCORING.md: Exactly 3 JudgeAgents with independent scoring.
    
    Per ARCHITECTURE.md - LLM Access:
    - Agents never hold API keys or call OpenAI directly
    - LLM access is handled internally via call_llm service
    
    Args:
        judge_configs: Optional list of 3 judge configurations.
            If not provided, creates default diverse panel.
            
    Returns:
        JudgePanel with 3 judges
    """
    if judge_configs is None:
        # Create diverse default panel
        judge_configs = [
            {
                "name": "Harrison",
                "judge_id": "judge_1",
                "temperament": JudicialTemperament.FORMAL,
                "scoring_style": ScoringStyle.BALANCED,
            },
            {
                "name": "Chen",
                "judge_id": "judge_2",
                "temperament": JudicialTemperament.STERN,
                "scoring_style": ScoringStyle.STRICT,
            },
            {
                "name": "Williams",
                "judge_id": "judge_3",
                "temperament": JudicialTemperament.PATIENT,
                "scoring_style": ScoringStyle.GENEROUS,
            },
        ]
    
    if len(judge_configs) != 3:
        raise ValueError("Must provide exactly 3 judge configurations")
    
    judges = [create_judge_agent(**config) for config in judge_configs]
    return JudgePanel(judges)
