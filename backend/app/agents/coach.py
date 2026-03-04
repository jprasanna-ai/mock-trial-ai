"""
Coach Agent

Per AGENTS.md Section 5:
- Responsibilities: Post-trial feedback only, Skill-focused guidance, Drill recommendations
- Coach must NEVER: Participate during live trial, Score officially

Per SPEC.md Section 3:
- Coach is post-trial only

Per ARCHITECTURE.md:
- Uses GPT-4.1 for all reasoning
- Text output only (TTS handled by audio pipeline)
- Agents never hold API keys or call OpenAI directly
- Agents communicate with LLM via backend service (call_llm)

Per AGENTS.md - Agent → LLM Communication:
- All agent calls to GPT-4.1 go through backend service
- Agents are unaware of API keys
"""

from typing import Optional, List, Dict, Any, Literal
from dataclasses import dataclass, field
from enum import Enum

from ..services.llm_service import call_llm, PersonaContext

from ..graph.trial_graph import (
    TrialState,
    TrialPhase,
    Role,
    TESTIMONY_STATES,
)

from .judge import (
    Ballot,
    ScoringCategory,
    ALL_SCORING_CATEGORIES,
)


# =============================================================================
# DRILL TYPES
# =============================================================================

class DrillType(str, Enum):
    """Types of practice drills the coach can recommend."""
    OPENING_STRUCTURE = "opening_structure"
    DIRECT_QUESTIONING = "direct_questioning"
    CROSS_CONTROL = "cross_control"
    OBJECTION_RECOGNITION = "objection_recognition"
    OBJECTION_RESPONSE = "objection_response"
    WITNESS_HANDLING = "witness_handling"
    CLOSING_ARGUMENT = "closing_argument"
    VOICE_PROJECTION = "voice_projection"
    PACING_CONTROL = "pacing_control"
    RECOVERY_TECHNIQUES = "recovery_techniques"
    CASE_THEORY_DEVELOPMENT = "case_theory_development"
    IMPEACHMENT = "impeachment"


@dataclass
class DrillRecommendation:
    """A specific drill recommendation."""
    drill_type: DrillType
    priority: int  # 1 = highest priority
    description: str
    focus_area: str
    estimated_duration_minutes: int
    specific_exercises: List[str]


# =============================================================================
# PERSONA PARAMETERS
# =============================================================================

class CoachingStyle(str, Enum):
    """Coach's approach to feedback."""
    ENCOURAGING = "encouraging"    # Focuses on positives, gentle criticism
    DIRECT = "direct"              # Straightforward, no sugarcoating
    ANALYTICAL = "analytical"      # Data-driven, systematic
    MOTIVATIONAL = "motivational"  # High energy, confidence building


class ExperienceLevel(str, Enum):
    """Coach's experience level affects depth of feedback."""
    ASSISTANT = "assistant"    # Basic feedback, simple drills
    VARSITY = "varsity"        # Solid feedback, standard drills
    COLLEGIATE = "collegiate"  # Advanced feedback, complex drills
    PROFESSIONAL = "professional"  # Expert feedback, elite drills


@dataclass
class CoachPersona:
    """
    Persona parameters that shape coach behavior.
    
    Per SPEC.md Section 2: Persona parameters shape reasoning, speech style,
    voice output.
    """
    name: str
    
    # Coaching characteristics
    style: CoachingStyle = CoachingStyle.DIRECT
    experience_level: ExperienceLevel = ExperienceLevel.VARSITY
    
    # Speech characteristics (for TTS persona conditioning)
    speaking_pace: float = 1.0
    energy_level: float = 0.7  # 0.0 = calm, 1.0 = high energy
    
    # Feedback characteristics
    detail_level: float = 0.7  # 0.0 = brief, 1.0 = exhaustive
    
    # Areas of specialty
    specialties: List[str] = field(default_factory=list)
    
    # Background
    background: str = ""


# =============================================================================
# FEEDBACK STRUCTURES
# =============================================================================

@dataclass
class SkillAssessment:
    """Assessment of a specific skill area."""
    skill_name: str
    current_level: int  # 1-10
    target_level: int   # 1-10
    strengths: List[str]
    areas_for_improvement: List[str]
    specific_feedback: str


@dataclass
class CoachingSession:
    """Complete coaching session output."""
    participant_role: Role
    participant_id: str
    
    # Overall assessment
    overall_assessment: str
    
    # Skill assessments
    skill_assessments: Dict[str, SkillAssessment] = field(default_factory=dict)
    
    # Drill recommendations (ordered by priority)
    drill_recommendations: List[DrillRecommendation] = field(default_factory=list)
    
    # Verbal feedback for TTS
    verbal_feedback: str = ""
    
    # Key takeaways (3-5 points)
    key_takeaways: List[str] = field(default_factory=list)
    
    # Next steps
    next_steps: List[str] = field(default_factory=list)


# =============================================================================
# COACH AGENT
# =============================================================================

class CoachAgent:
    """
    AI Coach Agent using GPT-4.1.
    
    Per AGENTS.md Section 5:
    - Post-trial feedback only
    - Skill-focused guidance
    - Drill recommendations
    - Must NEVER participate during live trial
    - Must NEVER score officially
    
    Per ARCHITECTURE.md:
    - All output is text for TTS pipeline
    """
    
    MODEL = "gpt-4.1"  # Per README.md: OpenAI GPT-4.1 for all agents
    
    def __init__(
        self,
        persona: CoachPersona,
    ):
        """
        Initialize coach agent with persona.
        
        Per ARCHITECTURE.md - LLM Access:
        - Agents never hold API keys or call OpenAI directly
        - Agents communicate with LLM via backend service (call_llm)
        
        Args:
            persona: CoachPersona defining behavior parameters
        """
        self.persona = persona
        self.role = Role.COACH
        
        # Persona context for LLM service calls
        self._persona_context = PersonaContext(
            role="coach",
            name=persona.name,
            style=persona.style.value,
            authority=0.6,
            nervousness=0.0,
            formality=0.5,  # Coaches can be more casual
            additional_traits={
                "experience_level": persona.experience_level.value,
                "speaking_pace": persona.speaking_pace,
            }
        )
        
        # Track coaching sessions
        self._sessions: Dict[str, CoachingSession] = {}
    
    # =========================================================================
    # CORE GENERATION METHOD
    # =========================================================================
    
    def _generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 500
    ) -> str:
        """
        Generate text response using GPT-4.1 via backend LLM service.
        
        Per ARCHITECTURE.md - LLM Access:
        - Agents communicate with LLM via call_llm function
        - Agents are unaware of API keys and cannot call LLM directly
        
        Per AUDIO.md: Output is text only, TTS is handled separately.
        
        Returns:
            Text suitable for TTS output.
        """
        return call_llm(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            persona=self._persona_context,
            temperature=temperature,
            max_tokens=max_tokens,
            model=self.MODEL,
        )
    
    def _build_system_prompt(self, context: str) -> str:
        """
        Build system prompt incorporating persona parameters.
        """
        style_instructions = {
            CoachingStyle.ENCOURAGING: (
                "You are encouraging and supportive. "
                "Lead with positives before addressing areas for improvement. "
                "Use phrases like 'great job on...' and 'one thing to work on...'. "
                "Build confidence while providing constructive feedback."
            ),
            CoachingStyle.DIRECT: (
                "You are direct and straightforward. "
                "Tell it like it is without sugarcoating. "
                "Be respectful but clear about what needs improvement. "
                "Focus on actionable feedback."
            ),
            CoachingStyle.ANALYTICAL: (
                "You are analytical and systematic. "
                "Break down performance into specific components. "
                "Use specific examples from the transcript. "
                "Provide data-driven observations."
            ),
            CoachingStyle.MOTIVATIONAL: (
                "You are high-energy and motivational. "
                "Inspire confidence and drive improvement. "
                "Frame challenges as opportunities. "
                "Use dynamic, engaging language."
            ),
        }
        
        experience_instructions = {
            ExperienceLevel.ASSISTANT: (
                "Provide basic, foundational feedback. "
                "Focus on fundamental skills and simple drills."
            ),
            ExperienceLevel.VARSITY: (
                "Provide solid, practical feedback. "
                "Address both fundamentals and intermediate techniques."
            ),
            ExperienceLevel.COLLEGIATE: (
                "Provide advanced, nuanced feedback. "
                "Address sophisticated techniques and strategy."
            ),
            ExperienceLevel.PROFESSIONAL: (
                "Provide expert-level feedback. "
                "Address elite techniques, psychology, and competitive strategy."
            ),
        }
        
        detail_instruction = (
            "Be thorough and detailed in your feedback." if self.persona.detail_level > 0.7
            else "Provide focused, moderate-length feedback." if self.persona.detail_level > 0.4
            else "Keep feedback concise and focused on key points."
        )
        
        specialties_text = ""
        if self.persona.specialties:
            specialties_text = f"\nYour areas of specialty: {', '.join(self.persona.specialties)}"
        
        return f"""You are Coach {self.persona.name}, a mock trial coach providing post-trial feedback.

ROLE CONSTRAINTS (STRICT - NEVER VIOLATE):
- You provide feedback ONLY after the trial is complete
- You CANNOT participate during live trial
- You CANNOT provide official scores (judges do that)
- You focus on skill development and improvement
- You recommend specific drills and exercises

COACHING STYLE:
{style_instructions[self.persona.style]}

EXPERIENCE LEVEL:
{experience_instructions[self.persona.experience_level]}

FEEDBACK APPROACH:
{detail_instruction}
{specialties_text}

SPEECH OUTPUT:
- Generate spoken feedback suitable for TTS
- {"Use energetic, dynamic language" if self.persona.energy_level > 0.7 else "Use calm, measured language" if self.persona.energy_level < 0.4 else "Use clear, professional language"}
- Be specific - reference actual moments from the trial
- Focus on actionable improvement

{self.persona.background}

{context}
"""
    
    # =========================================================================
    # TRIAL STATE VALIDATION
    # =========================================================================
    
    def can_act(self, state: TrialState) -> tuple[bool, Optional[str]]:
        """
        Check if coach can act.
        
        Per AGENTS.md: Coach cannot participate during live trial.
        """
        if state.phase != TrialPhase.SCORING:
            return False, "Coach can only provide feedback post-trial (SCORING phase)"
        return True, None
    
    def _validate_post_trial(self, state: TrialState) -> None:
        """
        Validate that trial is complete before coaching.
        
        Raises:
            ValueError: If trial is still in progress
        """
        valid, reason = self.can_act(state)
        if not valid:
            raise ValueError(f"Cannot coach: {reason}")
    
    # =========================================================================
    # TRANSCRIPT ANALYSIS
    # =========================================================================
    
    def analyze_transcript(
        self,
        transcript: List[Dict[str, Any]],
        participant_role: Role
    ) -> Dict[str, Any]:
        """
        Analyze transcript for coaching insights.
        
        Args:
            transcript: Full trial transcript
            participant_role: Role to analyze
            
        Returns:
            Analysis dict with strengths, weaknesses, patterns
        """
        # Extract participant's contributions
        participant_entries = [
            entry for entry in transcript
            if entry.get("role") == participant_role.value
        ]
        
        # Group by phase
        by_phase: Dict[str, List[Dict[str, Any]]] = {}
        for entry in participant_entries:
            phase = entry.get("phase", "unknown")
            if phase not in by_phase:
                by_phase[phase] = []
            by_phase[phase].append(entry)
        
        # Format for analysis
        transcript_text = self._format_transcript_for_analysis(participant_entries)
        
        analysis_prompt = f"""Analyze this mock trial performance for coaching feedback.

PARTICIPANT: {participant_role.value}

TRANSCRIPT:
{transcript_text}

Analyze and identify:
1. STRENGTHS: What did they do well? (3-5 specific examples)
2. WEAKNESSES: What needs improvement? (3-5 specific areas)
3. PATTERNS: Any recurring issues or habits?
4. KEY MOMENTS: Critical points that affected the trial
5. SKILL GAPS: Specific skills that need development

Respond in this format:
STRENGTHS:
- [specific strength with example]
...

WEAKNESSES:
- [specific weakness with example]
...

PATTERNS:
- [pattern observed]
...

KEY_MOMENTS:
- [moment and impact]
...

SKILL_GAPS:
- [skill needing development]
...
"""
        
        response = self._generate(
            self._build_system_prompt("Analyzing transcript for coaching feedback."),
            analysis_prompt,
            temperature=0.5,
            max_tokens=800
        )
        
        # Parse response into structured format
        return self._parse_analysis_response(response, by_phase)
    
    def _format_transcript_for_analysis(
        self,
        entries: List[Dict[str, Any]]
    ) -> str:
        """Format transcript entries for analysis."""
        if not entries:
            return "No entries for this participant."
        
        lines = []
        for entry in entries[:50]:  # Limit for context window
            phase = entry.get("phase", "unknown")
            text = entry.get("text", "")[:300]
            lines.append(f"[{phase}] {text}")
        
        return "\n".join(lines)
    
    def _parse_analysis_response(
        self,
        response: str,
        by_phase: Dict[str, List[Dict[str, Any]]]
    ) -> Dict[str, Any]:
        """Parse analysis response into structured format."""
        analysis = {
            "strengths": [],
            "weaknesses": [],
            "patterns": [],
            "key_moments": [],
            "skill_gaps": [],
            "entries_by_phase": {k: len(v) for k, v in by_phase.items()},
        }
        
        current_section = None
        section_map = {
            "STRENGTHS:": "strengths",
            "WEAKNESSES:": "weaknesses",
            "PATTERNS:": "patterns",
            "KEY_MOMENTS:": "key_moments",
            "SKILL_GAPS:": "skill_gaps",
        }
        
        for line in response.split("\n"):
            line = line.strip()
            
            # Check for section headers
            for header, key in section_map.items():
                if line.startswith(header):
                    current_section = key
                    break
            else:
                # Add content to current section
                if current_section and line.startswith("- "):
                    analysis[current_section].append(line[2:])
        
        return analysis
    
    # =========================================================================
    # SKILL ASSESSMENT
    # =========================================================================
    
    def assess_skills(
        self,
        transcript: List[Dict[str, Any]],
        participant_role: Role,
        judge_ballots: Optional[List[Ballot]] = None
    ) -> Dict[str, SkillAssessment]:
        """
        Assess specific skills based on transcript and judge feedback.
        
        Args:
            transcript: Full trial transcript
            participant_role: Role to assess
            judge_ballots: Optional judge ballots for reference
            
        Returns:
            Dict mapping skill names to assessments
        """
        assessments = {}
        
        # Map scoring categories to skill names
        skill_areas = {
            "Opening Statements": ScoringCategory.OPENING_CLARITY,
            "Direct Examination": ScoringCategory.DIRECT_EXAMINATION_EFFECTIVENESS,
            "Cross Examination": ScoringCategory.CROSS_EXAMINATION_CONTROL,
            "Objections": ScoringCategory.OBJECTION_ACCURACY,
            "Responsiveness": ScoringCategory.RESPONSIVENESS,
            "Courtroom Presence": ScoringCategory.COURTROOM_PRESENCE,
            "Case Theory": ScoringCategory.CASE_THEORY_CONSISTENCY,
        }
        
        # Get judge scores if available
        judge_scores = {}
        if judge_ballots:
            for category in ALL_SCORING_CATEGORIES:
                scores = [
                    b.scores[category].score 
                    for b in judge_ballots 
                    if category in b.scores
                ]
                if scores:
                    judge_scores[category] = sum(scores) / len(scores)
        
        for skill_name, category in skill_areas.items():
            assessment = self._assess_single_skill(
                skill_name,
                category,
                transcript,
                participant_role,
                judge_scores.get(category)
            )
            assessments[skill_name] = assessment
        
        return assessments
    
    def _assess_single_skill(
        self,
        skill_name: str,
        category: ScoringCategory,
        transcript: List[Dict[str, Any]],
        participant_role: Role,
        judge_score: Optional[float]
    ) -> SkillAssessment:
        """Assess a single skill area."""
        # Extract relevant transcript
        relevant_phases = self._get_relevant_phases_for_skill(skill_name)
        relevant_entries = [
            entry for entry in transcript
            if entry.get("role") == participant_role.value
            and entry.get("phase") in [p.value for p in relevant_phases]
        ]
        
        transcript_text = self._format_transcript_for_analysis(relevant_entries)
        
        # Use judge score as baseline if available
        current_level = int(judge_score) if judge_score else 5
        
        assessment_prompt = f"""Assess this participant's {skill_name} skill.

TRANSCRIPT (relevant portions):
{transcript_text}

{"JUDGE SCORE: " + str(judge_score) + "/10" if judge_score else "No judge score available."}

Provide assessment in this format:
CURRENT_LEVEL: [1-10]
TARGET_LEVEL: [realistic improvement target]
STRENGTHS:
- [strength 1]
- [strength 2]
AREAS_FOR_IMPROVEMENT:
- [area 1]
- [area 2]
SPECIFIC_FEEDBACK: [2-3 sentences of specific, actionable feedback]
"""
        
        response = self._generate(
            self._build_system_prompt(f"Assessing {skill_name} skill."),
            assessment_prompt,
            temperature=0.5,
            max_tokens=300
        )
        
        # Parse response
        return self._parse_skill_assessment(skill_name, response, current_level)
    
    def _get_relevant_phases_for_skill(self, skill_name: str) -> List[TrialPhase]:
        """Map skill to relevant trial phases."""
        mapping = {
            "Opening Statements": [TrialPhase.OPENING],
            "Direct Examination": [TrialPhase.DIRECT, TrialPhase.REDIRECT],
            "Cross Examination": [TrialPhase.CROSS, TrialPhase.RECROSS],
            "Objections": list(TESTIMONY_STATES),
            "Responsiveness": list(TESTIMONY_STATES),
            "Courtroom Presence": [
                TrialPhase.OPENING, TrialPhase.DIRECT, TrialPhase.CROSS,
                TrialPhase.REDIRECT, TrialPhase.RECROSS, TrialPhase.CLOSING
            ],
            "Case Theory": [TrialPhase.OPENING, TrialPhase.CLOSING],
        }
        return mapping.get(skill_name, [])
    
    def _parse_skill_assessment(
        self,
        skill_name: str,
        response: str,
        default_level: int
    ) -> SkillAssessment:
        """Parse skill assessment from LLM response."""
        # Extract values with defaults
        current_level = default_level
        target_level = min(10, default_level + 2)
        strengths = []
        areas_for_improvement = []
        specific_feedback = ""
        
        lines = response.split("\n")
        current_section = None
        
        for line in lines:
            line = line.strip()
            
            if line.startswith("CURRENT_LEVEL:"):
                try:
                    current_level = int(line.split(":")[1].strip().split()[0])
                    current_level = max(1, min(10, current_level))
                except (ValueError, IndexError):
                    pass
            elif line.startswith("TARGET_LEVEL:"):
                try:
                    target_level = int(line.split(":")[1].strip().split()[0])
                    target_level = max(1, min(10, target_level))
                except (ValueError, IndexError):
                    pass
            elif line.startswith("STRENGTHS:"):
                current_section = "strengths"
            elif line.startswith("AREAS_FOR_IMPROVEMENT:"):
                current_section = "improvement"
            elif line.startswith("SPECIFIC_FEEDBACK:"):
                specific_feedback = line.split(":", 1)[1].strip()
                current_section = "feedback"
            elif line.startswith("- "):
                if current_section == "strengths":
                    strengths.append(line[2:])
                elif current_section == "improvement":
                    areas_for_improvement.append(line[2:])
            elif current_section == "feedback" and line:
                specific_feedback += " " + line
        
        return SkillAssessment(
            skill_name=skill_name,
            current_level=current_level,
            target_level=target_level,
            strengths=strengths or ["No specific strengths identified"],
            areas_for_improvement=areas_for_improvement or ["Continue practicing"],
            specific_feedback=specific_feedback or "Keep working on this skill."
        )
    
    # =========================================================================
    # DRILL RECOMMENDATIONS
    # =========================================================================
    
    def recommend_drills(
        self,
        skill_assessments: Dict[str, SkillAssessment],
        analysis: Dict[str, Any]
    ) -> List[DrillRecommendation]:
        """
        Generate drill recommendations based on assessment.
        
        Per AGENTS.md: Drill recommendations.
        
        Args:
            skill_assessments: Skill assessments from assess_skills()
            analysis: Analysis from analyze_transcript()
            
        Returns:
            Ordered list of drill recommendations
        """
        recommendations = []
        
        # Find skills with largest gaps
        skill_gaps = [
            (name, assess.target_level - assess.current_level, assess)
            for name, assess in skill_assessments.items()
        ]
        skill_gaps.sort(key=lambda x: x[1], reverse=True)
        
        # Generate drills for top priority areas
        priority = 1
        for skill_name, gap, assessment in skill_gaps[:5]:
            if gap > 0:
                drill = self._create_drill_recommendation(
                    skill_name,
                    assessment,
                    analysis,
                    priority
                )
                recommendations.append(drill)
                priority += 1
        
        return recommendations
    
    def _create_drill_recommendation(
        self,
        skill_name: str,
        assessment: SkillAssessment,
        analysis: Dict[str, Any],
        priority: int
    ) -> DrillRecommendation:
        """Create a specific drill recommendation."""
        # Map skills to drill types
        skill_to_drill = {
            "Opening Statements": DrillType.OPENING_STRUCTURE,
            "Direct Examination": DrillType.DIRECT_QUESTIONING,
            "Cross Examination": DrillType.CROSS_CONTROL,
            "Objections": DrillType.OBJECTION_RECOGNITION,
            "Responsiveness": DrillType.RECOVERY_TECHNIQUES,
            "Courtroom Presence": DrillType.VOICE_PROJECTION,
            "Case Theory": DrillType.CASE_THEORY_DEVELOPMENT,
        }
        
        drill_type = skill_to_drill.get(skill_name, DrillType.DIRECT_QUESTIONING)
        
        # Generate specific exercises
        exercises_prompt = f"""Generate 3-4 specific practice exercises for improving {skill_name}.

CURRENT ISSUES:
{chr(10).join('- ' + area for area in assessment.areas_for_improvement)}

SKILL GAPS FROM ANALYSIS:
{chr(10).join('- ' + gap for gap in analysis.get('skill_gaps', [])[:3])}

Generate practical, actionable exercises. Format:
EXERCISES:
- [exercise 1]
- [exercise 2]
- [exercise 3]
"""
        
        response = self._generate(
            self._build_system_prompt("Generating drill exercises."),
            exercises_prompt,
            temperature=0.6,
            max_tokens=200
        )
        
        # Parse exercises
        exercises = []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("- "):
                exercises.append(line[2:])
        
        if not exercises:
            exercises = [
                f"Practice {skill_name.lower()} with sample cases",
                "Record and review your performance",
                "Get feedback from a partner"
            ]
        
        # Estimate duration based on skill level
        duration = 15 + (10 - assessment.current_level) * 5
        
        return DrillRecommendation(
            drill_type=drill_type,
            priority=priority,
            description=f"Focus drill for {skill_name.lower()} improvement",
            focus_area=assessment.areas_for_improvement[0] if assessment.areas_for_improvement else skill_name,
            estimated_duration_minutes=duration,
            specific_exercises=exercises[:4]
        )
    
    # =========================================================================
    # VERBAL FEEDBACK (for TTS)
    # =========================================================================
    
    def generate_verbal_feedback(
        self,
        participant_role: Role,
        skill_assessments: Dict[str, SkillAssessment],
        drill_recommendations: List[DrillRecommendation],
        analysis: Dict[str, Any]
    ) -> str:
        """
        Generate spoken feedback for TTS delivery.
        
        Args:
            participant_role: Role being coached
            skill_assessments: Skill assessments
            drill_recommendations: Drill recommendations
            analysis: Transcript analysis
            
        Returns:
            Verbal feedback text for TTS
        """
        # Build context
        strengths = analysis.get("strengths", [])[:3]
        weaknesses = analysis.get("weaknesses", [])[:3]
        
        # Top skills and areas for improvement
        sorted_skills = sorted(
            skill_assessments.items(),
            key=lambda x: x[1].current_level,
            reverse=True
        )
        top_skills = [s[0] for s in sorted_skills[:2]]
        improve_skills = [s[0] for s in sorted_skills[-2:]]
        
        # Top drills
        top_drills = [d.drill_type.value.replace("_", " ") for d in drill_recommendations[:3]]
        
        feedback_context = f"""
PARTICIPANT: {participant_role.value}

STRENGTHS OBSERVED:
{chr(10).join('- ' + s for s in strengths)}

AREAS FOR IMPROVEMENT:
{chr(10).join('- ' + w for w in weaknesses)}

STRONGEST SKILLS: {', '.join(top_skills)}
SKILLS TO DEVELOP: {', '.join(improve_skills)}

RECOMMENDED DRILLS: {', '.join(top_drills)}

Generate verbal coaching feedback that:
1. Opens with acknowledgment of effort
2. Highlights 2-3 specific strengths with examples
3. Addresses 2-3 areas for improvement constructively
4. Recommends specific practice activities
5. Ends with encouragement

Make it sound natural for spoken delivery (2-3 minutes of speech).
"""
        
        return self._generate(
            self._build_system_prompt(feedback_context),
            "Deliver your verbal coaching feedback.",
            temperature=0.7,
            max_tokens=800
        )
    
    def generate_quick_feedback(
        self,
        strengths: List[str],
        improvements: List[str]
    ) -> str:
        """
        Generate brief verbal feedback.
        
        Args:
            strengths: Key strengths observed
            improvements: Key areas for improvement
            
        Returns:
            Brief feedback text for TTS (30-60 seconds)
        """
        context = f"""
STRENGTHS: {', '.join(strengths[:2])}
IMPROVEMENTS: {', '.join(improvements[:2])}

Generate brief, focused coaching feedback (30-60 seconds of speech).
Be specific and actionable.
"""
        
        return self._generate(
            self._build_system_prompt(context),
            "Give quick coaching feedback.",
            temperature=0.7,
            max_tokens=250
        )
    
    # =========================================================================
    # COMPLETE COACHING SESSION
    # =========================================================================
    
    def conduct_coaching_session(
        self,
        state: TrialState,
        participant_role: Role,
        participant_id: str,
        transcript: List[Dict[str, Any]],
        judge_ballots: Optional[List[Ballot]] = None
    ) -> CoachingSession:
        """
        Conduct a complete coaching session.
        
        Per AGENTS.md: Post-trial feedback only.
        
        Args:
            state: Current trial state (must be SCORING)
            participant_role: Role being coached
            participant_id: Participant identifier
            transcript: Full trial transcript
            judge_ballots: Optional judge ballots for reference
            
        Returns:
            Complete CoachingSession
        """
        # Validate we're post-trial
        self._validate_post_trial(state)
        
        # Analyze transcript
        analysis = self.analyze_transcript(transcript, participant_role)
        
        # Assess skills
        skill_assessments = self.assess_skills(
            transcript, participant_role, judge_ballots
        )
        
        # Generate drill recommendations
        drill_recommendations = self.recommend_drills(skill_assessments, analysis)
        
        # Generate verbal feedback
        verbal_feedback = self.generate_verbal_feedback(
            participant_role,
            skill_assessments,
            drill_recommendations,
            analysis
        )
        
        # Generate key takeaways
        key_takeaways = self._generate_key_takeaways(analysis, skill_assessments)
        
        # Generate next steps
        next_steps = self._generate_next_steps(drill_recommendations)
        
        # Generate overall assessment
        overall_assessment = self._generate_overall_assessment(
            participant_role, analysis, skill_assessments
        )
        
        session = CoachingSession(
            participant_role=participant_role,
            participant_id=participant_id,
            overall_assessment=overall_assessment,
            skill_assessments=skill_assessments,
            drill_recommendations=drill_recommendations,
            verbal_feedback=verbal_feedback,
            key_takeaways=key_takeaways,
            next_steps=next_steps,
        )
        
        # Store session
        self._sessions[participant_id] = session
        
        return session
    
    def _generate_key_takeaways(
        self,
        analysis: Dict[str, Any],
        skill_assessments: Dict[str, SkillAssessment]
    ) -> List[str]:
        """Generate 3-5 key takeaways."""
        takeaways = []
        
        # Add top strength
        if analysis.get("strengths"):
            takeaways.append(f"Strength: {analysis['strengths'][0]}")
        
        # Add critical improvement area
        if analysis.get("weaknesses"):
            takeaways.append(f"Focus area: {analysis['weaknesses'][0]}")
        
        # Add skill-based takeaways
        sorted_skills = sorted(
            skill_assessments.items(),
            key=lambda x: x[1].target_level - x[1].current_level,
            reverse=True
        )
        
        if sorted_skills:
            top_gap = sorted_skills[0]
            takeaways.append(
                f"Priority skill: {top_gap[0]} (current: {top_gap[1].current_level}, target: {top_gap[1].target_level})"
            )
        
        # Add pattern if identified
        if analysis.get("patterns"):
            takeaways.append(f"Pattern to address: {analysis['patterns'][0]}")
        
        return takeaways[:5]
    
    def _generate_next_steps(
        self,
        drill_recommendations: List[DrillRecommendation]
    ) -> List[str]:
        """Generate actionable next steps."""
        steps = []
        
        for i, drill in enumerate(drill_recommendations[:3], 1):
            steps.append(
                f"{i}. Practice {drill.drill_type.value.replace('_', ' ')} "
                f"({drill.estimated_duration_minutes} min)"
            )
        
        steps.append(f"{len(steps) + 1}. Review this feedback and set specific goals")
        steps.append(f"{len(steps) + 1}. Schedule next practice session")
        
        return steps
    
    def _generate_overall_assessment(
        self,
        participant_role: Role,
        analysis: Dict[str, Any],
        skill_assessments: Dict[str, SkillAssessment]
    ) -> str:
        """Generate overall assessment summary."""
        avg_level = sum(
            a.current_level for a in skill_assessments.values()
        ) / len(skill_assessments) if skill_assessments else 5.0
        
        context = f"""
PARTICIPANT: {participant_role.value}
AVERAGE SKILL LEVEL: {avg_level:.1f}/10
STRENGTHS: {len(analysis.get('strengths', []))} identified
AREAS FOR IMPROVEMENT: {len(analysis.get('weaknesses', []))} identified

Write a 2-3 sentence overall assessment of this participant's performance.
Be constructive and specific.
"""
        
        return self._generate(
            self._build_system_prompt(context),
            "Write the overall assessment.",
            temperature=0.6,
            max_tokens=150
        )
    
    # =========================================================================
    # SESSION RETRIEVAL
    # =========================================================================
    
    def get_session(self, participant_id: str) -> Optional[CoachingSession]:
        """Get coaching session for a participant."""
        return self._sessions.get(participant_id)
    
    def get_all_sessions(self) -> Dict[str, CoachingSession]:
        """Get all coaching sessions."""
        return dict(self._sessions)


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_coach_agent(
    name: str,
    style: CoachingStyle = CoachingStyle.DIRECT,
    experience_level: ExperienceLevel = ExperienceLevel.VARSITY,
    specialties: Optional[List[str]] = None,
    **kwargs
) -> CoachAgent:
    """
    Factory function to create a CoachAgent.
    
    Per ARCHITECTURE.md - LLM Access:
    - Agents never hold API keys or call OpenAI directly
    - LLM access is handled internally via call_llm service
    
    Args:
        name: Coach's name
        style: Coaching style
        experience_level: Coach's experience level
        specialties: Areas of specialty
        **kwargs: Additional persona parameters
        
    Returns:
        Configured CoachAgent
    """
    persona = CoachPersona(
        name=name,
        style=style,
        experience_level=experience_level,
        specialties=specialties or [],
        **kwargs
    )
    
    return CoachAgent(persona)
