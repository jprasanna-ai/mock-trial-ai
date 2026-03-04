"""
Mock Trial AI Agents

Per AGENTS.md: All agents must obey trial state, respect persona parameters,
never invent facts, and never break role boundaries.

Per ARCHITECTURE.md - LLM Access:
- Agents never hold API keys or call OpenAI directly
- Agents communicate with LLM via backend service (call_llm)
- All memory, persona, and prompt assembly is done in backend before calling LLM

Per AGENTS.md - Agent → LLM Communication:
- All agent calls to GPT-4.1 go through backend service
- Agents are unaware of API keys and cannot call LLM directly
"""

from .attorney import (
    AttorneyAgent,
    AttorneyPersona,
    AttorneyStyle,
    SkillLevel,
    create_attorney_agent,
)

from .witness import (
    WitnessAgent,
    WitnessPersona,
    WitnessType,
    Demeanor,
    WitnessMemory,
    TestimonyEntry,
    create_witness_agent,
)

from .judge import (
    JudgeAgent,
    JudgePersona,
    JudicialTemperament,
    ScoringStyle,
    ScoringCategory,
    ALL_SCORING_CATEGORIES,
    OPENING_ATTORNEY_CATEGORIES,
    DIRECT_CROSS_ATTORNEY_CATEGORIES,
    CLOSING_ATTORNEY_CATEGORIES,
    WITNESS_CATEGORIES,
    get_categories_for_subrole,
    CategoryScore,
    Ballot,
    ObjectionRuling,
    JudgePanel,
    create_judge_agent,
    create_judge_panel,
)

from .coach import (
    CoachAgent,
    CoachPersona,
    CoachingStyle,
    ExperienceLevel,
    DrillType,
    DrillRecommendation,
    SkillAssessment,
    CoachingSession,
    create_coach_agent,
)

__all__ = [
    # Attorney
    "AttorneyAgent",
    "AttorneyPersona",
    "AttorneyStyle",
    "SkillLevel",
    "create_attorney_agent",
    # Witness
    "WitnessAgent",
    "WitnessPersona",
    "WitnessType",
    "Demeanor",
    "WitnessMemory",
    "TestimonyEntry",
    "create_witness_agent",
    # Judge
    "JudgeAgent",
    "JudgePersona",
    "JudicialTemperament",
    "ScoringStyle",
    "ScoringCategory",
    "ALL_SCORING_CATEGORIES",
    "OPENING_ATTORNEY_CATEGORIES",
    "DIRECT_CROSS_ATTORNEY_CATEGORIES",
    "CLOSING_ATTORNEY_CATEGORIES",
    "WITNESS_CATEGORIES",
    "get_categories_for_subrole",
    "CategoryScore",
    "Ballot",
    "ObjectionRuling",
    "JudgePanel",
    "create_judge_agent",
    "create_judge_panel",
    # Coach
    "CoachAgent",
    "CoachPersona",
    "CoachingStyle",
    "ExperienceLevel",
    "DrillType",
    "DrillRecommendation",
    "SkillAssessment",
    "CoachingSession",
    "create_coach_agent",
]
