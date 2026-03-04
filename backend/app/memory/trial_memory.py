"""
6-Layer Trial Memory Architecture.

Layer 1 (Immutable Case Memory): Handled by persona.case_theory, prep_materials, affidavit -- no changes needed.
Layer 2 (Courtroom Event Memory): ExamEvent, ObjectionEvent, PhaseEvent logs.
Layer 3 (Character Memory): Handled by AttorneyPersona, WitnessPersona, JudgePersona -- no changes needed.
Layer 4 (Short-Term Conversation Memory): Handled per-agent (_conversation_history, WitnessMemory) -- no changes needed.
Layer 5 (Strategic Memory): StrategicNotes per attorney side + LivePrepUpdate (real-time strategic insights).
Layer 6 (Credibility & Scoring Memory): CredibilityTracker per witness, PerformanceTracker per attorney.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

_memory_logger = logging.getLogger(__name__)


# =============================================================================
# LAYER 2: COURTROOM EVENT MEMORY
# =============================================================================

@dataclass
class ExamEvent:
    """A single examination exchange with full metadata."""
    witness_id: str
    witness_name: str
    exam_type: str  # direct, cross, redirect, recross
    questioner_side: str  # plaintiff or defense
    question: str
    answer: str
    objection_raised: bool = False
    objection_type: Optional[str] = None
    objection_sustained: bool = False
    timestamp: float = field(default_factory=time.time)


@dataclass
class ObjectionEvent:
    """An objection raised and its ruling."""
    objection_type: str
    by_side: str
    sustained: bool
    phase: str
    context_text: str  # the question/testimony that triggered it
    judge_explanation: str
    witness_id: Optional[str] = None
    timestamp: float = field(default_factory=time.time)


@dataclass
class PhaseEvent:
    """A trial phase transition or significant announcement."""
    event_type: str  # phase_change, witness_called, witness_excused, case_rested
    description: str
    phase: str
    timestamp: float = field(default_factory=time.time)


# =============================================================================
# LAYER 5: STRATEGIC MEMORY
# =============================================================================

@dataclass
class StrategicNotes:
    """Running strategic insights for one side (plaintiff or defense)."""
    contradictions_found: List[Dict[str, str]] = field(default_factory=list)
    strong_testimony: List[Dict[str, str]] = field(default_factory=list)
    weak_points_exploited: List[Dict[str, str]] = field(default_factory=list)
    closing_argument_notes: List[str] = field(default_factory=list)
    key_admissions: List[Dict[str, str]] = field(default_factory=list)

    def format_for_prompt(self, max_items: int = 8) -> str:
        """Format strategic notes into a prompt-ready section."""
        parts = []
        if self.contradictions_found:
            items = self.contradictions_found[:max_items]
            lines = "\n".join(
                f"  - {c.get('witness', '?')}: {c.get('detail', '')}" for c in items
            )
            parts.append(f"CONTRADICTIONS FOUND:\n{lines}")
        if self.key_admissions:
            items = self.key_admissions[:max_items]
            lines = "\n".join(
                f"  - {a.get('witness', '?')}: {a.get('detail', '')}" for a in items
            )
            parts.append(f"KEY ADMISSIONS:\n{lines}")
        if self.strong_testimony:
            items = self.strong_testimony[:max_items]
            lines = "\n".join(
                f"  - {s.get('witness', '?')}: {s.get('detail', '')}" for s in items
            )
            parts.append(f"STRONG TESTIMONY FOR YOUR CASE:\n{lines}")
        if self.weak_points_exploited:
            items = self.weak_points_exploited[:max_items]
            lines = "\n".join(
                f"  - {w.get('witness', '?')}: {w.get('detail', '')}" for w in items
            )
            parts.append(f"WEAKNESSES EXPLOITED IN OPPOSING CASE:\n{lines}")
        if self.closing_argument_notes:
            items = self.closing_argument_notes[:max_items]
            parts.append("NOTES FOR CLOSING ARGUMENT:\n" + "\n".join(f"  - {n}" for n in items))
        return "\n\n".join(parts)


# =============================================================================
# LAYER 5b: LIVE STRATEGIC PREP (real-time updates during trial)
# =============================================================================

@dataclass
class LivePrepUpdate:
    """A strategic insight generated in real-time as the trial unfolds.

    In real mock trial, each team watches opposing testimony and adjusts their
    strategy between witnesses. This models that — LLM-generated strategic
    recommendations stored per-side and fed to attorneys for future actions.
    """
    update_type: str  # "cross_adjustment", "new_weakness", "rebuttal_needed", "closing_note", "credibility_shift"
    side: str
    witness_id: Optional[str] = None
    witness_name: Optional[str] = None
    insight: str = ""
    priority: int = 2  # 1=critical, 2=important, 3=useful
    source_phase: str = ""
    timestamp: float = field(default_factory=time.time)


@dataclass
class TeamLivePrep:
    """Running live preparation updates for one side (plaintiff or defense).

    Accumulates strategic intelligence throughout the trial, modeling how a
    real mock trial team would confer and adjust strategy between witnesses.
    """
    strategy_adjustments: List[str] = field(default_factory=list)
    weaknesses_discovered: List[Dict[str, str]] = field(default_factory=list)
    rebuttal_points: List[Dict[str, str]] = field(default_factory=list)
    upcoming_witness_notes: List[Dict[str, str]] = field(default_factory=list)
    closing_material: List[str] = field(default_factory=list)
    all_updates: List[LivePrepUpdate] = field(default_factory=list)

    def add_update(self, update: LivePrepUpdate) -> None:
        self.all_updates.append(update)
        if update.update_type == "cross_adjustment":
            self.strategy_adjustments.append(update.insight)
        elif update.update_type == "new_weakness":
            self.weaknesses_discovered.append({
                "witness": update.witness_name or "unknown",
                "detail": update.insight,
            })
        elif update.update_type == "rebuttal_needed":
            self.rebuttal_points.append({
                "witness": update.witness_name or "unknown",
                "detail": update.insight,
            })
        elif update.update_type == "upcoming_witness_note":
            self.upcoming_witness_notes.append({
                "witness": update.witness_name or "unknown",
                "detail": update.insight,
            })
        elif update.update_type == "closing_note":
            self.closing_material.append(update.insight)

    def format_for_prompt(self, max_items: int = 6) -> str:
        """Format live prep updates into a prompt-ready section."""
        parts = []
        if self.strategy_adjustments:
            items = self.strategy_adjustments[-max_items:]
            parts.append("STRATEGY ADJUSTMENTS (based on what you've heard so far):\n" +
                         "\n".join(f"  - {a}" for a in items))
        if self.weaknesses_discovered:
            items = self.weaknesses_discovered[-max_items:]
            parts.append("NEW WEAKNESSES DISCOVERED IN OPPOSING CASE:\n" +
                         "\n".join(f"  - {w['witness']}: {w['detail']}" for w in items))
        if self.rebuttal_points:
            items = self.rebuttal_points[-max_items:]
            parts.append("POINTS TO REBUT:\n" +
                         "\n".join(f"  - {r['witness']}: {r['detail']}" for r in items))
        if self.upcoming_witness_notes:
            items = self.upcoming_witness_notes[-max_items:]
            parts.append("NOTES FOR UPCOMING WITNESSES:\n" +
                         "\n".join(f"  - {n['witness']}: {n['detail']}" for n in items))
        if self.closing_material:
            items = self.closing_material[-max_items:]
            parts.append("MATERIAL FOR CLOSING ARGUMENT:\n" +
                         "\n".join(f"  - {m}" for m in items))
        return "\n\n".join(parts)


# =============================================================================
# LAYER 5c: TEAM SHARED MEMORY (intra-team knowledge sharing)
# =============================================================================

@dataclass
class TeamSharedMemory:
    """Shared knowledge within a prosecution or defense team.

    Models how team members in a real mock trial share information:
    - Attorneys brief witnesses on what to expect
    - Witnesses share key points they want emphasized
    - All members share case theory and important admissions heard in court
    """
    case_theory_notes: List[str] = field(default_factory=list)
    key_facts_established: List[Dict[str, str]] = field(default_factory=list)
    opposing_weaknesses: List[Dict[str, str]] = field(default_factory=list)
    witness_prep_notes: Dict[str, List[str]] = field(default_factory=dict)
    attorney_directives: List[str] = field(default_factory=list)
    heard_in_court: List[Dict[str, str]] = field(default_factory=list)

    def add_fact(self, source: str, fact: str) -> None:
        self.key_facts_established.append({"source": source, "fact": fact})

    def add_weakness(self, source: str, detail: str) -> None:
        self.opposing_weaknesses.append({"source": source, "detail": detail})

    def add_witness_note(self, witness_id: str, note: str) -> None:
        self.witness_prep_notes.setdefault(witness_id, []).append(note)

    def add_directive(self, directive: str) -> None:
        self.attorney_directives.append(directive)

    def add_heard(self, speaker: str, summary: str) -> None:
        self.heard_in_court.append({"speaker": speaker, "summary": summary})

    def format_for_attorney(self, max_items: int = 8) -> str:
        parts = []
        if self.case_theory_notes:
            parts.append("TEAM CASE THEORY:\n" +
                         "\n".join(f"  - {n}" for n in self.case_theory_notes[-max_items:]))
        if self.key_facts_established:
            items = self.key_facts_established[-max_items:]
            parts.append("KEY FACTS ESTABLISHED BY OUR TEAM:\n" +
                         "\n".join(f"  - [{f['source']}] {f['fact']}" for f in items))
        if self.opposing_weaknesses:
            items = self.opposing_weaknesses[-max_items:]
            parts.append("OPPOSING WEAKNESSES IDENTIFIED:\n" +
                         "\n".join(f"  - [{w['source']}] {w['detail']}" for w in items))
        if self.attorney_directives:
            parts.append("TEAM DIRECTIVES:\n" +
                         "\n".join(f"  - {d}" for d in self.attorney_directives[-max_items:]))
        if self.heard_in_court:
            items = self.heard_in_court[-max_items:]
            parts.append("NOTABLE COURTROOM MOMENTS:\n" +
                         "\n".join(f"  - {h['speaker']}: {h['summary']}" for h in items))
        return "\n\n".join(parts)

    def format_for_witness(self, witness_id: str, max_items: int = 6) -> str:
        parts = []
        if self.case_theory_notes:
            parts.append("YOUR TEAM'S CASE THEORY:\n" +
                         "\n".join(f"  - {n}" for n in self.case_theory_notes[-4:]))
        notes = self.witness_prep_notes.get(witness_id, [])
        if notes:
            parts.append("NOTES FROM YOUR ATTORNEY FOR YOUR TESTIMONY:\n" +
                         "\n".join(f"  - {n}" for n in notes[-max_items:]))
        if self.key_facts_established:
            items = self.key_facts_established[-max_items:]
            parts.append("FACTS YOUR TEAM HAS ESTABLISHED SO FAR:\n" +
                         "\n".join(f"  - {f['fact']}" for f in items))
        return "\n\n".join(parts)


# =============================================================================
# LAYER 6: CREDIBILITY & SCORING MEMORY
# =============================================================================

@dataclass
class CredibilityTracker:
    """Tracks a single witness's credibility throughout the trial."""
    witness_id: str
    witness_name: str
    consistency_issues: List[str] = field(default_factory=list)
    key_admissions: List[str] = field(default_factory=list)
    evasive_answers: List[str] = field(default_factory=list)
    confidence_level: float = 0.7  # 0.0=unreliable, 1.0=very credible
    total_questions: int = 0
    helpful_answers: int = 0  # answers that clearly supported calling side

    def format_for_prompt(self) -> str:
        parts = [f"WITNESS CREDIBILITY — {self.witness_name} (confidence: {self.confidence_level:.1f}):"]
        if self.consistency_issues:
            parts.append("  Consistency issues: " + "; ".join(self.consistency_issues[:5]))
        if self.key_admissions:
            parts.append("  Key admissions: " + "; ".join(self.key_admissions[:5]))
        if self.evasive_answers:
            parts.append("  Evasive on: " + "; ".join(self.evasive_answers[:3]))
        return "\n".join(parts)


@dataclass
class PerformanceTracker:
    """Tracks an attorney's live performance metrics."""
    attorney_key: str  # e.g. "plaintiff_direct_cross"
    side: str
    objections_raised: int = 0
    objections_sustained: int = 0
    objections_overruled: int = 0
    questions_asked: int = 0
    quality_notes: List[str] = field(default_factory=list)

    @property
    def objection_success_rate(self) -> float:
        if self.objections_raised == 0:
            return 0.0
        return self.objections_sustained / self.objections_raised

    def format_for_prompt(self) -> str:
        rate = f"{self.objection_success_rate:.0%}" if self.objections_raised else "N/A"
        parts = [
            f"ATTORNEY PERFORMANCE — {self.attorney_key}:",
            f"  Questions asked: {self.questions_asked}",
            f"  Objections: {self.objections_raised} raised, {self.objections_sustained} sustained ({rate})",
        ]
        if self.quality_notes:
            parts.append("  Notes: " + "; ".join(self.quality_notes[:5]))
        return "\n".join(parts)


# =============================================================================
# CENTRAL TRIAL MEMORY
# =============================================================================

@dataclass
class TrialMemory:
    """
    Central memory store shared across all agents in a session.

    Provides structured access to all 6 memory layers:
    - L1 (Immutable Case) and L3 (Character) live on agent personas — not here.
    - L2 (Courtroom Events) — examination_log, objection_log, phase_events
    - L4 (Short-Term) — per-agent, not here (but helpers provided)
    - L5 (Strategic) — strategic_notes per side
    - L6 (Credibility & Scoring) — witness_credibility, attorney_performance
    """

    # Layer 2: Courtroom Event Memory
    opening_statements: Dict[str, str] = field(default_factory=dict)
    examination_log: List[ExamEvent] = field(default_factory=list)
    objection_log: List[ObjectionEvent] = field(default_factory=list)
    phase_events: List[PhaseEvent] = field(default_factory=list)

    # Layer 5: Strategic Memory (per side)
    strategic_notes: Dict[str, StrategicNotes] = field(default_factory=lambda: {
        "plaintiff": StrategicNotes(),
        "defense": StrategicNotes(),
    })

    # Layer 5b: Live Strategic Prep (per side — updated in real-time during trial)
    team_live_prep: Dict[str, TeamLivePrep] = field(default_factory=lambda: {
        "plaintiff": TeamLivePrep(),
        "defense": TeamLivePrep(),
    })

    # Layer 5c: Team Shared Memory (intra-team knowledge sharing)
    team_shared: Dict[str, TeamSharedMemory] = field(default_factory=lambda: {
        "plaintiff": TeamSharedMemory(),
        "defense": TeamSharedMemory(),
    })

    # Layer 6: Credibility & Scoring Memory
    witness_credibility: Dict[str, CredibilityTracker] = field(default_factory=dict)
    attorney_performance: Dict[str, PerformanceTracker] = field(default_factory=dict)

    # -------------------------------------------------------------------------
    # RECORDING METHODS
    # -------------------------------------------------------------------------

    def record_opening(self, side: str, text: str) -> None:
        self.opening_statements[side] = text

    def record_phase_event(self, event_type: str, description: str, phase: str) -> None:
        self.phase_events.append(PhaseEvent(
            event_type=event_type,
            description=description,
            phase=phase,
        ))

    def record_exam_event(
        self,
        witness_id: str,
        witness_name: str,
        exam_type: str,
        questioner_side: str,
        question: str,
        answer: str,
        objection_raised: bool = False,
        objection_type: Optional[str] = None,
        objection_sustained: bool = False,
    ) -> None:
        event = ExamEvent(
            witness_id=witness_id,
            witness_name=witness_name,
            exam_type=exam_type,
            questioner_side=questioner_side,
            question=question,
            answer=answer,
            objection_raised=objection_raised,
            objection_type=objection_type,
            objection_sustained=objection_sustained,
        )
        self.examination_log.append(event)

        # Update attorney performance
        perf_key = f"{questioner_side}_direct_cross"
        perf = self.attorney_performance.get(perf_key)
        if perf:
            perf.questions_asked += 1

        # Update witness credibility tracker
        cred = self._ensure_credibility(witness_id, witness_name)
        cred.total_questions += 1

    def record_objection(
        self,
        objection_type: str,
        by_side: str,
        sustained: bool,
        phase: str,
        context_text: str,
        judge_explanation: str,
        witness_id: Optional[str] = None,
    ) -> None:
        self.objection_log.append(ObjectionEvent(
            objection_type=objection_type,
            by_side=by_side,
            sustained=sustained,
            phase=phase,
            context_text=context_text,
            judge_explanation=judge_explanation,
            witness_id=witness_id,
        ))

        # Update attorney performance for the objecting side
        perf_key = f"{by_side}_direct_cross"
        perf = self._ensure_performance(perf_key, by_side)
        perf.objections_raised += 1
        if sustained:
            perf.objections_sustained += 1
        else:
            perf.objections_overruled += 1

    # -------------------------------------------------------------------------
    # QUERY METHODS
    # -------------------------------------------------------------------------

    def get_witness_testimony(self, witness_id: str) -> List[ExamEvent]:
        return [e for e in self.examination_log if e.witness_id == witness_id]

    def get_testimony_by_type(self, witness_id: str, exam_type: str) -> List[ExamEvent]:
        return [
            e for e in self.examination_log
            if e.witness_id == witness_id and e.exam_type == exam_type
        ]

    def get_all_testimony_for_side(self, side: str) -> List[ExamEvent]:
        """Get all testimony where this side's attorney was questioning."""
        return [e for e in self.examination_log if e.questioner_side == side]

    def get_recent_objections(self, limit: int = 5) -> List[ObjectionEvent]:
        return self.objection_log[-limit:]

    def get_objections_for_witness(self, witness_id: str) -> List[ObjectionEvent]:
        return [o for o in self.objection_log if o.witness_id == witness_id]

    # -------------------------------------------------------------------------
    # STRATEGIC CONTEXT BUILDERS
    # -------------------------------------------------------------------------

    def build_cross_exam_context(self, side: str, witness_id: str) -> str:
        """Build strategic context for cross-examination."""
        parts = []

        # Credibility info for this witness
        cred = self.witness_credibility.get(witness_id)
        if cred and (cred.consistency_issues or cred.key_admissions or cred.evasive_answers):
            parts.append(cred.format_for_prompt())

        # Strategic notes for the examining side
        notes = self.strategic_notes.get(side)
        if notes:
            # Only show contradictions relevant to this witness or cross-witness
            relevant_contradictions = [
                c for c in notes.contradictions_found
                if c.get("witness") == witness_id or c.get("cross_witness")
            ]
            if relevant_contradictions:
                lines = "\n".join(f"  - {c.get('detail', '')}" for c in relevant_contradictions[:5])
                parts.append(f"CONTRADICTIONS TO EXPLOIT:\n{lines}")

        # Recent objection patterns
        recent_obj = self.get_objections_for_witness(witness_id)
        if recent_obj:
            sustained_types = [o.objection_type for o in recent_obj if o.sustained]
            overruled_types = [o.objection_type for o in recent_obj if not o.sustained]
            if sustained_types:
                parts.append(f"OBJECTIONS SUSTAINED (avoid these patterns): {', '.join(sustained_types)}")
            if overruled_types:
                parts.append(f"OBJECTIONS OVERRULED (safe to continue): {', '.join(overruled_types)}")

        return "\n\n".join(parts)

    def build_closing_context(self, side: str) -> str:
        """Build memory-driven context for closing argument."""
        parts = []

        notes = self.strategic_notes.get(side)
        if notes:
            formatted = notes.format_for_prompt(max_items=10)
            if formatted:
                parts.append(f"=== STRATEGIC INSIGHTS FROM TRIAL ===\n{formatted}")

        # Summarize witness credibility
        cred_parts = []
        for wid, cred in self.witness_credibility.items():
            if cred.consistency_issues or cred.key_admissions:
                cred_parts.append(cred.format_for_prompt())
        if cred_parts:
            parts.append("=== WITNESS CREDIBILITY SUMMARY ===\n" + "\n".join(cred_parts))

        # Objection summary
        if self.objection_log:
            by_side = {}
            for obj in self.objection_log:
                by_side.setdefault(obj.by_side, []).append(obj)
            obj_lines = []
            for s, objs in by_side.items():
                sustained = sum(1 for o in objs if o.sustained)
                obj_lines.append(f"  {s}: {len(objs)} objections, {sustained} sustained")
            parts.append("=== OBJECTION SUMMARY ===\n" + "\n".join(obj_lines))

        return "\n\n".join(parts)

    def build_witness_context(self, witness_id: str) -> str:
        """Build context for a witness about their prior testimony across all exams."""
        prior = self.get_witness_testimony(witness_id)
        if not prior:
            return ""
        parts = ["YOUR PRIOR TESTIMONY IN THIS TRIAL:"]
        for e in prior[-10:]:
            parts.append(f"  [{e.exam_type}] Q: {e.question}")
            parts.append(f"           A: {e.answer}")
        return "\n".join(parts)

    def build_scoring_context(self) -> str:
        """Build context for judge scoring from live observations."""
        parts = []
        for key, perf in self.attorney_performance.items():
            parts.append(perf.format_for_prompt())
        for wid, cred in self.witness_credibility.items():
            parts.append(cred.format_for_prompt())
        if self.objection_log:
            parts.append(f"Total objections during trial: {len(self.objection_log)}")
        return "\n\n".join(parts)

    # -------------------------------------------------------------------------
    # LIVE PREP METHODS
    # -------------------------------------------------------------------------

    def record_live_prep_update(self, side: str, update: LivePrepUpdate) -> None:
        """Record a live prep strategic update for a team."""
        prep = self.team_live_prep.get(side)
        if prep is None:
            self.team_live_prep[side] = TeamLivePrep()
            prep = self.team_live_prep[side]
        prep.add_update(update)
        _memory_logger.info(
            f"Live prep update for {side}: [{update.update_type}] {update.insight[:80]}..."
        )

    def build_live_prep_context(self, side: str) -> str:
        """Build live prep context for an attorney's prompt.

        Returns formatted strategic intelligence accumulated during the trial
        from the team's real-time analysis of opposing testimony.
        """
        prep = self.team_live_prep.get(side)
        if not prep or not prep.all_updates:
            return ""
        formatted = prep.format_for_prompt(max_items=8)
        if not formatted:
            return ""
        return (
            "\n=== LIVE STRATEGIC INTELLIGENCE (updated during trial) ===\n"
            f"{formatted}\n"
            "=== END LIVE INTELLIGENCE ===\n"
        )

    def get_recent_testimony_summary(
        self,
        witness_id: str,
        exam_type: Optional[str] = None,
        max_events: int = 15,
    ) -> str:
        """Get a compact summary of recent testimony for a specific witness."""
        events = [
            e for e in self.examination_log
            if e.witness_id == witness_id
            and (exam_type is None or e.exam_type == exam_type)
        ]
        if not events:
            return ""
        recent = events[-max_events:]
        lines = []
        for e in recent:
            lines.append(f"[{e.exam_type}] Q: {e.question[:100]}")
            lines.append(f"         A: {e.answer[:120]}")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # TEAM SHARED MEMORY METHODS
    # -------------------------------------------------------------------------

    def _ensure_team_shared(self, side: str) -> "TeamSharedMemory":
        if side not in self.team_shared:
            self.team_shared[side] = TeamSharedMemory()
        return self.team_shared[side]

    def record_team_fact(self, side: str, source: str, fact: str) -> None:
        self._ensure_team_shared(side).add_fact(source, fact)

    def record_team_weakness(self, side: str, source: str, detail: str) -> None:
        self._ensure_team_shared(side).add_weakness(source, detail)

    def record_team_directive(self, side: str, directive: str) -> None:
        self._ensure_team_shared(side).add_directive(directive)

    def record_team_witness_note(self, side: str, witness_id: str, note: str) -> None:
        self._ensure_team_shared(side).add_witness_note(witness_id, note)

    def record_team_heard(self, side: str, speaker: str, summary: str) -> None:
        self._ensure_team_shared(side).add_heard(speaker, summary)

    def build_team_shared_context_for_attorney(self, side: str) -> str:
        """Build team shared memory context for an attorney's prompt."""
        shared = self.team_shared.get(side)
        if not shared:
            return ""
        formatted = shared.format_for_attorney(max_items=8)
        if not formatted:
            return ""
        return (
            "\n=== TEAM SHARED INTELLIGENCE ===\n"
            f"{formatted}\n"
            "=== END TEAM INTELLIGENCE ===\n"
        )

    def build_team_shared_context_for_witness(self, side: str, witness_id: str) -> str:
        """Build team shared memory context for a witness's prompt."""
        shared = self.team_shared.get(side)
        if not shared:
            return ""
        formatted = shared.format_for_witness(witness_id, max_items=6)
        if not formatted:
            return ""
        return (
            "\n=== TEAM BRIEFING ===\n"
            f"{formatted}\n"
            "=== END TEAM BRIEFING ===\n"
        )

    def update_team_shared_from_testimony(
        self, side: str, witness_name: str, witness_id: str,
        question: str, answer: str, exam_type: str, questioner_side: str
    ) -> None:
        """Auto-populate team shared memory from courtroom events.

        Strict isolation: each side's TeamSharedMemory is only written with
        intelligence relevant to THAT side. Prosecution never sees defense
        strategy and vice versa.

        - Direct/redirect: the CALLING side's team records strong testimony
          from their own witness.
        - Cross/recross: the QUESTIONER's team records admissions and
          weaknesses they extracted. The witness's own team gets nothing
          (they observe the transcript directly, not via shared memory).
        """
        answer_lower = answer.lower()

        # Direct/redirect: calling side questions their own witness
        if exam_type in ("direct", "redirect") and questioner_side == side:
            calling_team = self._ensure_team_shared(side)
            strong_markers = [
                "absolutely", "definitely", "i clearly", "without a doubt",
                "i'm certain", "i know for a fact", "i'm positive",
            ]
            if any(m in answer_lower for m in strong_markers):
                calling_team.add_fact(witness_name, f"{answer[:120]}")
            calling_team.add_heard(witness_name, f"[{exam_type}] {answer[:100]}")

        # Cross/recross: opposing side questions the witness — only the
        # QUESTIONER's team gets the intelligence they discovered.
        if exam_type in ("cross", "recross") and questioner_side != side:
            questioner_team = self._ensure_team_shared(questioner_side)
            admission_markers = ["yes", "correct", "that's correct", "i agree", "i admit"]
            if any(answer_lower.strip().startswith(m) for m in admission_markers):
                questioner_team.add_fact(witness_name, f"Admitted: {answer[:100]}")
            evasive = ["i don't recall", "i don't remember", "i'm not sure", "i don't know"]
            if any(p in answer_lower for p in evasive):
                questioner_team.add_weakness(witness_name, f"Evasive on: {question[:80]}")

    # -------------------------------------------------------------------------
    # STRATEGIC ANALYSIS ENGINE (rule-based, no LLM calls)
    # -------------------------------------------------------------------------

    def analyze_answer(
        self,
        question: str,
        answer: str,
        witness_id: str,
        witness_name: str,
        exam_type: str,
        questioner_side: str,
    ) -> None:
        """
        Post-answer rule-based analysis to update strategic and credibility layers.

        Runs after each Q&A exchange.  Uses keyword/phrase overlap heuristics —
        no LLM call — to keep latency near zero.
        """
        answer_lower = answer.lower()
        question_lower = question.lower()

        cred = self._ensure_credibility(witness_id, witness_name)

        # --- 1. Detect contradictions with prior testimony ---
        prior = [e for e in self.examination_log if e.witness_id == witness_id]
        for prev in prior:
            if self._texts_contradict(prev.answer, answer):
                detail = (
                    f"Previously said '{prev.answer[:80]}…' but now says '{answer[:80]}…'"
                )
                contradiction = {
                    "witness": witness_name,
                    "detail": detail,
                    "cross_witness": False,
                }
                opposing = "defense" if questioner_side == "plaintiff" else "plaintiff"
                self.strategic_notes[opposing].contradictions_found.append(contradiction)
                cred.consistency_issues.append(detail[:120])
                cred.confidence_level = max(0.1, cred.confidence_level - 0.1)

        # --- 2. Detect evasive answers ---
        evasive_phrases = [
            "i don't recall", "i don't remember", "i'm not sure",
            "i can't say", "i wouldn't know", "that's not how i'd put it",
            "i don't know", "i can't recall",
        ]
        if any(p in answer_lower for p in evasive_phrases):
            cred.evasive_answers.append(question[:100])
            cred.confidence_level = max(0.1, cred.confidence_level - 0.05)

        # --- 3. Detect key admissions (cross-exam only) ---
        if exam_type in ("cross", "recross"):
            admission_markers = [
                "yes", "that's correct", "i agree", "correct", "right",
                "i admit", "that's true", "i concede", "fair enough",
            ]
            if any(answer_lower.strip().startswith(m) for m in admission_markers):
                admission = {"witness": witness_name, "detail": f"Admitted: Q: {question[:60]}… A: {answer[:60]}…"}
                self.strategic_notes[questioner_side].key_admissions.append(admission)
                cred.key_admissions.append(f"{question[:60]} → {answer[:60]}")

        # --- 4. Detect strong testimony (direct/redirect for calling side) ---
        if exam_type in ("direct", "redirect"):
            strong_indicators = [
                "absolutely", "i'm certain", "without a doubt", "i clearly saw",
                "definitely", "i'm positive", "i know for a fact",
            ]
            if any(s in answer_lower for s in strong_indicators):
                self.strategic_notes[questioner_side].strong_testimony.append({
                    "witness": witness_name,
                    "detail": f"{question[:60]}… → {answer[:60]}…",
                })
                cred.helpful_answers += 1
                cred.confidence_level = min(1.0, cred.confidence_level + 0.03)

        # --- 5. Accumulate closing argument notes for significant moments ---
        significance_triggers = [
            "never", "always", "impossible", "certain", "guarantee",
            "admit", "concede", "absolutely", "definitely",
        ]
        if any(t in answer_lower for t in significance_triggers):
            note = f"{witness_name} ({exam_type}): \"{answer[:100]}…\" in response to \"{question[:60]}…\""
            self.strategic_notes[questioner_side].closing_argument_notes.append(note)

        # --- 6. Cross-witness contradiction detection ---
        self._check_cross_witness_contradictions(
            answer, witness_id, witness_name, questioner_side
        )

    # -------------------------------------------------------------------------
    # RULE-BASED HEURISTICS
    # -------------------------------------------------------------------------

    @staticmethod
    def _texts_contradict(text_a: str, text_b: str) -> bool:
        """
        Simple heuristic: two answers contradict if one contains a negation
        of a key phrase from the other, or they give opposite yes/no answers
        to semantically overlapping content.
        """
        a = text_a.lower()
        b = text_b.lower()

        negation_pairs = [
            ("yes", "no"), ("did", "didn't"), ("was", "wasn't"),
            ("could", "couldn't"), ("would", "wouldn't"), ("can", "can't"),
            ("is", "isn't"), ("are", "aren't"), ("do", "don't"),
            ("have", "haven't"), ("had", "hadn't"),
            ("were", "weren't"), ("will", "won't"),
        ]
        words_a = set(a.split())
        words_b = set(b.split())
        shared = words_a & words_b
        if len(shared) < 3:
            return False

        for pos, neg in negation_pairs:
            if pos in words_a and neg in words_b:
                return True
            if neg in words_a and pos in words_b:
                return True
        return False

    def _check_cross_witness_contradictions(
        self,
        answer: str,
        witness_id: str,
        witness_name: str,
        questioner_side: str,
    ) -> None:
        """Check if this answer contradicts testimony from other witnesses."""
        other_answers = [
            e for e in self.examination_log
            if e.witness_id != witness_id
        ]
        if not other_answers:
            return

        for prev in other_answers[-20:]:
            if self._texts_contradict(prev.answer, answer):
                detail = (
                    f"{witness_name} said '{answer[:60]}…' but "
                    f"{prev.witness_name} said '{prev.answer[:60]}…'"
                )
                opposing = "defense" if questioner_side == "plaintiff" else "plaintiff"
                self.strategic_notes[opposing].contradictions_found.append({
                    "witness": witness_name,
                    "detail": detail,
                    "cross_witness": True,
                })

    # -------------------------------------------------------------------------
    # SERIALIZATION (for API access and persistence)
    # -------------------------------------------------------------------------

    def get_live_prep_snapshot(self) -> Dict[str, Any]:
        """Return a serializable snapshot of all live prep updates for both sides."""
        snapshot: Dict[str, Any] = {}
        for side in ("plaintiff", "defense"):
            prep = self.team_live_prep.get(side)
            if not prep:
                snapshot[side] = {"updates": [], "summary": ""}
                continue
            snapshot[side] = {
                "total_updates": len(prep.all_updates),
                "strategy_adjustments": prep.strategy_adjustments[-10:],
                "weaknesses_discovered": prep.weaknesses_discovered[-10:],
                "rebuttal_points": prep.rebuttal_points[-10:],
                "upcoming_witness_notes": prep.upcoming_witness_notes[-10:],
                "closing_material": prep.closing_material[-10:],
                "formatted_summary": prep.format_for_prompt(max_items=8),
            }
        return snapshot

    # -------------------------------------------------------------------------
    # INTERNAL HELPERS
    # -------------------------------------------------------------------------

    def _ensure_credibility(self, witness_id: str, witness_name: str) -> CredibilityTracker:
        if witness_id not in self.witness_credibility:
            self.witness_credibility[witness_id] = CredibilityTracker(
                witness_id=witness_id, witness_name=witness_name
            )
        return self.witness_credibility[witness_id]

    def _ensure_performance(self, key: str, side: str) -> PerformanceTracker:
        if key not in self.attorney_performance:
            self.attorney_performance[key] = PerformanceTracker(
                attorney_key=key, side=side
            )
        return self.attorney_performance[key]
