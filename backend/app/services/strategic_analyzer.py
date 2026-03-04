"""
Live Strategic Analyzer — LLM-powered real-time prep updates.

After each examination phase completes for a witness, this analyzer reviews
what was said and generates strategic recommendations for EACH team, modeling
how real mock trial teams confer and adjust strategy between witnesses.

Runs asynchronously so it doesn't block the trial flow.
"""

import json
import logging
from typing import Dict, List, Optional

from ..memory.trial_memory import (
    TrialMemory,
    LivePrepUpdate,
)
from .llm_service import call_llm_async, PersonaContext

logger = logging.getLogger(__name__)

_ANALYZER_PERSONA = PersonaContext(
    role="attorney",
    name="Strategic Advisor",
    style="methodical",
    authority=0.9,
    nervousness=0.0,
    formality=0.8,
)


async def analyze_examination_for_teams(
    trial_memory: TrialMemory,
    witness_id: str,
    witness_name: str,
    exam_type: str,
    calling_side: str,
    case_theory_plaintiff: str = "",
    case_theory_defense: str = "",
) -> None:
    """Analyze a completed examination phase and generate live prep updates for both teams.

    Called after direct, cross, redirect, or recross completes for a witness.
    Generates strategic insights for BOTH sides based on what was said.
    """
    testimony = trial_memory.get_testimony_by_type(witness_id, exam_type)
    if not testimony:
        return

    qa_summary = "\n".join(
        f"Q ({e.questioner_side}): {e.question[:150]}\nA: {e.answer[:200]}"
        for e in testimony[-10:]
    )

    opposing_side = "defense" if calling_side == "plaintiff" else "plaintiff"

    for side in ["plaintiff", "defense"]:
        is_friendly = (side == calling_side)
        side_label = "Prosecution" if side == "plaintiff" else "Defense"
        case_theory = case_theory_plaintiff if side == "plaintiff" else case_theory_defense

        role_context = (
            "This was YOUR witness on direct — assess how well your testimony went."
            if is_friendly and exam_type == "direct"
            else "The opposing side just examined YOUR witness — assess the damage and plan your response."
            if not is_friendly and exam_type == "cross"
            else "You just cross-examined the OPPOSING witness — assess what you gained."
            if not is_friendly and exam_type in ("direct",)
            else f"Review this {exam_type} examination testimony."
        )

        prompt = f"""You are the {side_label} team's strategic advisor in a mock trial.

{role_context}

Witness: {witness_name} (called by {"prosecution" if calling_side == "plaintiff" else "defense"})
Examination type: {exam_type}

YOUR CASE THEORY: {case_theory or "Not specified"}

TESTIMONY:
{qa_summary}

Based on this testimony, provide strategic analysis as JSON with these fields:
- "strategy_adjustments": List of 1-3 specific strategy adjustments for your team going forward (or empty list if none needed)
- "weaknesses_discovered": List of 0-2 new weaknesses you noticed in the OPPOSING case (be specific — cite what was said)
- "rebuttal_points": List of 0-2 points from this testimony that your team needs to address or counter
- "upcoming_witness_notes": List of 0-2 specific things to address with future witnesses based on what was just said
- "closing_material": List of 0-2 notable quotes or moments to reference in closing argument

IMPORTANT:
- Be SPECIFIC — reference exact testimony, not generic advice
- Only include items that provide actionable intelligence
- Empty lists are fine if there's nothing notable
- This is a mock trial — focus on what a real team would discuss between witnesses

Return ONLY valid JSON."""

        try:
            result = await call_llm_async(
                system_prompt="You are a mock trial strategic advisor. Analyze testimony and provide actionable intelligence. Return ONLY valid JSON.",
                user_prompt=prompt,
                persona=_ANALYZER_PERSONA,
                max_tokens=800,
                temperature=0.3,
            )

            data = json.loads(result)
            _apply_analysis_to_memory(trial_memory, side, witness_id, witness_name, exam_type, data)

        except json.JSONDecodeError:
            logger.warning(f"Strategic analyzer returned non-JSON for {side}/{exam_type}/{witness_name}")
        except Exception as e:
            logger.warning(f"Strategic analysis failed for {side}: {e}")


def _apply_analysis_to_memory(
    trial_memory: TrialMemory,
    side: str,
    witness_id: str,
    witness_name: str,
    exam_type: str,
    analysis: Dict,
) -> None:
    """Apply parsed strategic analysis to the trial memory."""
    for adj in analysis.get("strategy_adjustments", []):
        if isinstance(adj, str) and adj.strip():
            trial_memory.record_live_prep_update(side, LivePrepUpdate(
                update_type="cross_adjustment",
                side=side,
                witness_id=witness_id,
                witness_name=witness_name,
                insight=adj.strip(),
                priority=2,
                source_phase=exam_type,
            ))

    for weak in analysis.get("weaknesses_discovered", []):
        text = weak if isinstance(weak, str) else weak.get("detail", str(weak))
        if text.strip():
            trial_memory.record_live_prep_update(side, LivePrepUpdate(
                update_type="new_weakness",
                side=side,
                witness_id=witness_id,
                witness_name=witness_name,
                insight=text.strip(),
                priority=1,
                source_phase=exam_type,
            ))

    for reb in analysis.get("rebuttal_points", []):
        text = reb if isinstance(reb, str) else reb.get("detail", str(reb))
        if text.strip():
            trial_memory.record_live_prep_update(side, LivePrepUpdate(
                update_type="rebuttal_needed",
                side=side,
                witness_id=witness_id,
                witness_name=witness_name,
                insight=text.strip(),
                priority=2,
                source_phase=exam_type,
            ))

    for note in analysis.get("upcoming_witness_notes", []):
        text = note if isinstance(note, str) else note.get("detail", str(note))
        if text.strip():
            trial_memory.record_live_prep_update(side, LivePrepUpdate(
                update_type="upcoming_witness_note",
                side=side,
                witness_id=witness_id,
                witness_name=witness_name,
                insight=text.strip(),
                priority=2,
                source_phase=exam_type,
            ))

    for closing in analysis.get("closing_material", []):
        if isinstance(closing, str) and closing.strip():
            trial_memory.record_live_prep_update(side, LivePrepUpdate(
                update_type="closing_note",
                side=side,
                witness_id=witness_id,
                witness_name=witness_name,
                insight=closing.strip(),
                priority=3,
                source_phase=exam_type,
            ))


async def analyze_opening_for_teams(
    trial_memory: TrialMemory,
    side_that_spoke: str,
    opening_text: str,
    case_theory_plaintiff: str = "",
    case_theory_defense: str = "",
) -> None:
    """Analyze an opening statement and generate live prep updates for the opposing team.

    The opposing team listens to the opening and adjusts their strategy.
    """
    opposing = "defense" if side_that_spoke == "plaintiff" else "plaintiff"
    opp_label = "Defense" if opposing == "defense" else "Prosecution"
    spoke_label = "Prosecution" if side_that_spoke == "plaintiff" else "Defense"
    case_theory = case_theory_plaintiff if opposing == "plaintiff" else case_theory_defense

    prompt = f"""You are the {opp_label} team's strategic advisor in a mock trial.
The {spoke_label} just delivered their opening statement. Your team needs to know
what themes they're pushing and how to counter them.

THEIR OPENING STATEMENT:
{opening_text[:2000]}

YOUR CASE THEORY: {case_theory or "Not specified"}

Provide strategic analysis as JSON:
- "strategy_adjustments": List of 1-3 adjustments to your approach based on their opening
- "rebuttal_points": List of 1-3 claims they made that you need to directly counter
- "closing_material": List of 0-2 promises they made that you can hold them to if undelivered

Return ONLY valid JSON."""

    try:
        result = await call_llm_async(
            system_prompt="You are a mock trial strategic advisor analyzing the opposing opening statement. Return ONLY valid JSON.",
            user_prompt=prompt,
            persona=_ANALYZER_PERSONA,
            max_tokens=600,
            temperature=0.3,
        )
        data = json.loads(result)
        _apply_analysis_to_memory(trial_memory, opposing, "", "", "opening", data)
    except Exception as e:
        logger.warning(f"Opening analysis failed for {opposing}: {e}")
