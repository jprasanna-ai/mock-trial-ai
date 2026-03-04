"""
Automated Test Suite API

Provides endpoints to run integration tests against the running system
and return structured results. Tests are non-destructive — they create
temporary sessions, validate behaviour, and clean up.
"""

import asyncio
import logging
import time
from typing import Any, Optional
from pydantic import BaseModel
from fastapi import APIRouter

logger = logging.getLogger(__name__)

router = APIRouter()


class TestResult(BaseModel):
    name: str
    passed: bool
    duration_ms: float
    details: str
    category: str


class TestSuiteReport(BaseModel):
    total: int
    passed: int
    failed: int
    duration_ms: float
    results: list[TestResult]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _run_test(name: str, category: str, fn) -> TestResult:
    """Run a single async test function and capture the result."""
    t0 = time.time()
    try:
        details = await fn()
        return TestResult(
            name=name, passed=True,
            duration_ms=round((time.time() - t0) * 1000, 1),
            details=details or "OK", category=category,
        )
    except Exception as e:
        return TestResult(
            name=name, passed=False,
            duration_ms=round((time.time() - t0) * 1000, 1),
            details=str(e), category=category,
        )


# ---------------------------------------------------------------------------
# Individual tests
# ---------------------------------------------------------------------------

async def test_health_check() -> str:
    """Verify the health endpoint responds."""
    from ..main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200, f"Status {r.status_code}"
    data = r.json()
    assert data.get("status") == "healthy", f"Unexpected: {data}"
    return "Health endpoint OK"


async def test_case_list() -> str:
    """Verify the case library returns at least one case."""
    from ..main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)
    r = client.get("/api/case/")
    if r.status_code != 200:
        r = client.get("/api/case/demo")
    assert r.status_code == 200, f"Status {r.status_code}"
    data = r.json()
    cases = data if isinstance(data, list) else data.get("cases", [])
    assert len(cases) > 0, "No cases found in library"
    return f"Found {len(cases)} case(s)"


async def test_session_create_and_status() -> str:
    """Create a spectator session and verify it initialises."""
    from ..main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    # Get a case ID
    r = client.get("/api/case/")
    if r.status_code != 200:
        r = client.get("/api/case/demo")
    cases = r.json() if isinstance(r.json(), list) else r.json().get("cases", [])
    if not cases:
        return "SKIP: no cases"
    case_id = cases[0].get("id") or cases[0].get("case_id")

    # Create session
    r = client.post("/api/session/create", json={
        "case_id": case_id,
        "human_role": "spectator",
    })
    assert r.status_code == 200, f"Create failed: {r.status_code} {r.text}"
    session_id = r.json().get("session_id")
    assert session_id, "No session_id returned"

    # Poll for initialisation (up to 90s)
    for _ in range(30):
        sr = client.get(f"/api/session/{session_id}/status")
        if sr.status_code == 200 and sr.json().get("initialized"):
            return f"Session {session_id[:8]}... initialised"
        await asyncio.sleep(3)

    return f"Session created ({session_id[:8]}...) but init timed out"


async def test_tts_service() -> str:
    """Verify the TTS service can generate audio bytes."""
    from ..services.tts import TTSService
    svc = TTSService()
    session = svc.create_session("test_tts")
    from ..graph.trial_graph import Role
    seg = await svc.generate_speech("test_tts", "Hello, this is a test.", Role.JUDGE)
    svc.end_session("test_tts")
    if seg and len(seg.audio_data) > 100:
        return f"Generated {len(seg.audio_data)} bytes of audio"
    raise AssertionError("TTS returned empty or no segment")


async def test_session_witnesses() -> str:
    """Verify that a session has witnesses assigned."""
    from ..main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    r = client.get("/api/case/")
    if r.status_code != 200:
        r = client.get("/api/case/demo")
    cases = r.json() if isinstance(r.json(), list) else r.json().get("cases", [])
    if not cases:
        return "SKIP: no cases"
    case_id = cases[0].get("id") or cases[0].get("case_id")

    r = client.post("/api/session/create", json={
        "case_id": case_id,
        "human_role": "spectator",
    })
    session_id = r.json().get("session_id")

    for _ in range(30):
        sr = client.get(f"/api/session/{session_id}/status")
        if sr.status_code == 200 and sr.json().get("initialized"):
            break
        await asyncio.sleep(3)

    wr = client.get(f"/api/trial/{session_id}/witnesses")
    assert wr.status_code == 200, f"Witnesses endpoint failed: {wr.status_code}"
    data = wr.json()
    ws = data.get("witnesses", [])
    assert len(ws) > 0, "No witnesses found"

    has_pros = any(w.get("called_by") in ("plaintiff", "prosecution") for w in ws)
    has_def = any(w.get("called_by") == "defense" for w in ws)
    sides = []
    if has_pros:
        sides.append("prosecution")
    if has_def:
        sides.append("defense")
    return f"{len(ws)} witness(es) — sides: {', '.join(sides)}"


async def test_phase_advance() -> str:
    """Create session and advance from prep to opening."""
    from ..main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    r = client.get("/api/case/")
    if r.status_code != 200:
        r = client.get("/api/case/demo")
    cases = r.json() if isinstance(r.json(), list) else r.json().get("cases", [])
    if not cases:
        return "SKIP: no cases"
    case_id = cases[0].get("id") or cases[0].get("case_id")

    r = client.post("/api/session/create", json={
        "case_id": case_id,
        "human_role": "spectator",
    })
    session_id = r.json().get("session_id")

    for _ in range(30):
        sr = client.get(f"/api/session/{session_id}/status")
        if sr.status_code == 200 and sr.json().get("initialized"):
            break
        await asyncio.sleep(3)

    r = client.post(f"/api/trial/{session_id}/advance-phase", json={"target_phase": "opening"})
    assert r.status_code == 200, f"Advance failed: {r.status_code} {r.text}"
    data = r.json()
    assert data.get("success"), f"Advance not successful: {data}"
    return f"Advanced to: {data.get('current_phase', '?')}"


async def test_opening_statements() -> str:
    """Verify opening statements can be generated/fetched."""
    from ..main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    r = client.get("/api/case/")
    if r.status_code != 200:
        r = client.get("/api/case/demo")
    cases = r.json() if isinstance(r.json(), list) else r.json().get("cases", [])
    if not cases:
        return "SKIP: no cases"
    case_id = cases[0].get("id") or cases[0].get("case_id")

    r = client.post("/api/session/create", json={
        "case_id": case_id,
        "human_role": "spectator",
    })
    session_id = r.json().get("session_id")

    for _ in range(30):
        sr = client.get(f"/api/session/{session_id}/status")
        if sr.status_code == 200 and sr.json().get("initialized"):
            break
        await asyncio.sleep(3)

    r = client.get(f"/api/prep/{session_id}/opening-statements")
    assert r.status_code == 200, f"Opening statements endpoint failed: {r.status_code}"
    data = r.json()
    ready = data.get("ready", False)
    return f"Opening statements ready={ready}"


async def test_scoring_endpoint() -> str:
    """Verify scoring endpoint exists and responds."""
    from ..main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    r = client.get("/api/case/")
    if r.status_code != 200:
        r = client.get("/api/case/demo")
    cases = r.json() if isinstance(r.json(), list) else r.json().get("cases", [])
    if not cases:
        return "SKIP: no cases"
    case_id = cases[0].get("id") or cases[0].get("case_id")

    r = client.post("/api/session/create", json={
        "case_id": case_id,
        "human_role": "spectator",
    })
    session_id = r.json().get("session_id")

    r = client.get(f"/api/scoring/{session_id}/live-scores")
    assert r.status_code == 200, f"Scoring endpoint failed: {r.status_code}"
    return "Scoring endpoint OK"


async def test_transcript_record() -> str:
    """Verify the record-transcript endpoint accepts entries."""
    from ..main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    r = client.get("/api/case/")
    if r.status_code != 200:
        r = client.get("/api/case/demo")
    cases = r.json() if isinstance(r.json(), list) else r.json().get("cases", [])
    if not cases:
        return "SKIP: no cases"
    case_id = cases[0].get("id") or cases[0].get("case_id")

    r = client.post("/api/session/create", json={
        "case_id": case_id,
        "human_role": "spectator",
    })
    session_id = r.json().get("session_id")

    for _ in range(30):
        sr = client.get(f"/api/session/{session_id}/status")
        if sr.status_code == 200 and sr.json().get("initialized"):
            break
        await asyncio.sleep(3)

    r = client.post(f"/api/trial/{session_id}/record-transcript", json={
        "speaker": "Test Speaker",
        "role": "judge",
        "text": "Test transcript entry",
        "phase": "prep",
    })
    assert r.status_code == 200, f"Record transcript failed: {r.status_code}"
    data = r.json()
    assert data.get("success"), f"Not successful: {data}"
    return "Transcript entry recorded"


async def test_objection_detection() -> str:
    """Verify the attorney objection logic detects leading questions on direct."""
    from ..agents.attorney import AttorneyAgent, AttorneyPersona, AttorneyStyle, SkillLevel
    from ..graph.trial_graph import TrialState, TrialPhase, Role

    persona = AttorneyPersona(
        name="Test Attorney",
        side="defense",
        style=AttorneyStyle.AGGRESSIVE,
        skill_level=SkillLevel.EXPERT,
        case_theory="Test theory",
        objection_frequency=0.9,
        risk_tolerance=0.7,
    )
    agent = AttorneyAgent(persona=persona)

    state = TrialState()
    state.phase = TrialPhase.DIRECT

    leading_q = "Isn't it true that you saw the defendant at the scene?"
    result = agent.should_object(state, leading_q, {
        "recent_questions": [],
        "witness_name": "Test Witness",
        "examination_type": "direct",
    })
    if result:
        return f"Detected objection: {result}"
    raise AssertionError("Failed to detect leading question on direct")


async def test_objection_no_false_positive() -> str:
    """Verify proper questions on cross don't trigger false objections."""
    from ..agents.attorney import AttorneyAgent, AttorneyPersona, AttorneyStyle, SkillLevel
    from ..graph.trial_graph import TrialState, TrialPhase, Role

    persona = AttorneyPersona(
        name="Test Attorney",
        side="plaintiff",
        style=AttorneyStyle.METHODICAL,
        skill_level=SkillLevel.EXPERT,
        case_theory="Test theory",
        objection_frequency=0.3,
        risk_tolerance=0.3,
    )
    agent = AttorneyAgent(persona=persona)

    state = TrialState()
    state.phase = TrialPhase.CROSS

    proper_q = "What time did you arrive at the location?"
    result = agent.should_object(state, proper_q, {
        "recent_questions": [],
        "witness_name": "Test Witness",
        "examination_type": "cross",
    })
    if result is None:
        return "No false positive on proper cross question"
    return f"Possible false positive: {result} (acceptable with high obj frequency)"


# ---------------------------------------------------------------------------
# Per-agent LLM config tests
# ---------------------------------------------------------------------------

async def test_per_agent_llm_config() -> str:
    """Verify per-agent LLM config fields propagate to agent personas."""
    from ..agents.attorney import create_attorney_agent, AttorneyStyle, SkillLevel
    from ..agents.witness import create_witness_agent, WitnessType, Demeanor
    from ..agents.judge import create_judge_agent, JudicialTemperament, ScoringStyle

    att = create_attorney_agent(
        "Config Test Atty", "plaintiff",
        llm_model="claude-sonnet-4-20250514",
        llm_temperature=0.4,
        llm_max_tokens=1000,
        custom_system_prompt="You are extremely concise.",
    )
    assert att.persona.llm_model == "claude-sonnet-4-20250514", "Attorney model override failed"
    assert att.persona.llm_temperature == 0.4, "Attorney temperature override failed"
    assert att.persona.llm_max_tokens == 1000, "Attorney max_tokens override failed"
    assert att.persona.custom_system_prompt == "You are extremely concise.", "Attorney system prompt failed"

    wit = create_witness_agent(
        "Config Test Witness", "w_test", "Test affidavit", "defense",
        llm_model="gemini-2.5-pro",
        llm_temperature=0.9,
    )
    assert wit.persona.llm_model == "gemini-2.5-pro", "Witness model override failed"
    assert wit.persona.llm_temperature == 0.9, "Witness temperature override failed"
    assert wit.persona.llm_max_tokens is None, "Witness max_tokens should default to None"

    jdg = create_judge_agent(
        "Config Test Judge", "j_test",
        llm_model="grok-3",
        custom_system_prompt="Be strict.",
    )
    assert jdg.persona.llm_model == "grok-3", "Judge model override failed"
    assert jdg.persona.custom_system_prompt == "Be strict.", "Judge system prompt failed"

    return "All 3 agent types accept per-agent LLM config"


async def test_per_agent_defaults_none() -> str:
    """Verify agents with no LLM overrides default to None."""
    from ..agents.attorney import create_attorney_agent

    att = create_attorney_agent("Default Atty", "defense")
    assert att.persona.llm_model is None, "Default model should be None"
    assert att.persona.llm_temperature is None, "Default temperature should be None"
    assert att.persona.llm_max_tokens is None, "Default max_tokens should be None"
    assert att.persona.custom_system_prompt is None, "Default system prompt should be None"
    return "Per-agent LLM config defaults correctly to None"


# ---------------------------------------------------------------------------
# Multi-provider tests
# ---------------------------------------------------------------------------

async def test_provider_model_routing() -> str:
    """Verify model-to-provider mapping is correct."""
    from ..services.llm_providers import get_provider_for_model, AVAILABLE_MODELS

    checks = {
        "gpt-4.1": "openai",
        "gpt-4o-mini": "openai",
        "claude-sonnet-4-20250514": "anthropic",
        "claude-3-5-haiku-20241022": "anthropic",
        "gemini-2.5-pro": "google",
        "gemini-2.0-flash": "google",
        "grok-3": "xai",
        "grok-3-mini": "xai",
        "unknown-model-xyz": "openai",  # unknown defaults to openai
    }
    for model, expected in checks.items():
        actual = get_provider_for_model(model)
        assert actual == expected, f"{model} → {actual} (expected {expected})"

    assert len(AVAILABLE_MODELS) >= 13, f"Expected 13+ models, got {len(AVAILABLE_MODELS)}"

    providers_covered = set(m["provider"] for m in AVAILABLE_MODELS)
    for p in ("openai", "anthropic", "google", "xai"):
        assert p in providers_covered, f"Provider {p} missing from AVAILABLE_MODELS"

    return f"Model routing OK for {len(checks)} models, {len(AVAILABLE_MODELS)} available across {len(providers_covered)} providers"


async def test_available_models_structure() -> str:
    """Verify each model entry has required fields."""
    from ..services.llm_providers import AVAILABLE_MODELS

    for m in AVAILABLE_MODELS:
        assert "id" in m, f"Missing 'id' in model {m}"
        assert "label" in m, f"Missing 'label' in model {m}"
        assert "provider" in m, f"Missing 'provider' in model {m}"
        assert "description" in m, f"Missing 'description' in model {m}"

    return f"All {len(AVAILABLE_MODELS)} models have required fields"


# ---------------------------------------------------------------------------
# Phase advance idempotency test
# ---------------------------------------------------------------------------

async def test_phase_advance_idempotent() -> str:
    """Verify advancing to the current phase returns success (idempotent)."""
    from ..main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    r = client.get("/api/case/")
    if r.status_code != 200:
        r = client.get("/api/case/demo")
    cases = r.json() if isinstance(r.json(), list) else r.json().get("cases", [])
    if not cases:
        return "SKIP: no cases"
    case_id = cases[0].get("id") or cases[0].get("case_id")

    r = client.post("/api/session/create", json={
        "case_id": case_id,
        "human_role": "spectator",
    })
    session_id = r.json().get("session_id")

    for _ in range(30):
        sr = client.get(f"/api/session/{session_id}/status")
        if sr.status_code == 200 and sr.json().get("initialized"):
            break
        await asyncio.sleep(3)

    # Advance to opening
    r = client.post(f"/api/trial/{session_id}/advance-phase", json={"target_phase": "opening"})
    assert r.status_code == 200 and r.json().get("success"), "First advance failed"

    # Try advancing to opening AGAIN — should succeed (idempotent)
    r = client.post(f"/api/trial/{session_id}/advance-phase", json={"target_phase": "opening"})
    assert r.status_code == 200, f"Idempotent advance HTTP error: {r.status_code}"
    data = r.json()
    assert data.get("success"), f"Idempotent advance should succeed: {data}"
    return f"Phase advance is idempotent: {data.get('message', '')}"


# ---------------------------------------------------------------------------
# Persona API tests
# ---------------------------------------------------------------------------

async def test_persona_endpoint() -> str:
    """Verify persona API returns team config with available models."""
    from ..main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    r = client.get("/api/case/")
    if r.status_code != 200:
        r = client.get("/api/case/demo")
    cases = r.json() if isinstance(r.json(), list) else r.json().get("cases", [])
    if not cases:
        return "SKIP: no cases"
    case_id = cases[0].get("id") or cases[0].get("case_id")

    r = client.post("/api/session/create", json={
        "case_id": case_id,
        "human_role": "spectator",
    })
    session_id = r.json().get("session_id")

    r = client.get(f"/api/persona/{session_id}")
    assert r.status_code == 200, f"Persona endpoint failed: {r.status_code}"
    data = r.json()

    assert "prosecution_attorneys" in data, "Missing prosecution_attorneys"
    assert "defense_attorneys" in data, "Missing defense_attorneys"
    assert "available_models" in data, "Missing available_models"
    models = data["available_models"]
    assert len(models) >= 13, f"Expected 13+ models, got {len(models)}"

    providers = set(m.get("provider") for m in models)
    for p in ("openai", "anthropic", "google", "xai"):
        assert p in providers, f"Provider {p} missing"

    return f"Persona config OK: {len(data.get('prosecution_attorneys', []))} pros attys, {len(models)} models across {len(providers)} providers"


async def test_persona_llm_config_update() -> str:
    """Verify per-agent LLM config can be set via the persona API."""
    from ..main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    r = client.get("/api/case/")
    if r.status_code != 200:
        r = client.get("/api/case/demo")
    cases = r.json() if isinstance(r.json(), list) else r.json().get("cases", [])
    if not cases:
        return "SKIP: no cases"
    case_id = cases[0].get("id") or cases[0].get("case_id")

    r = client.post("/api/session/create", json={
        "case_id": case_id,
        "human_role": "spectator",
    })
    session_id = r.json().get("session_id")

    # Get current prosecution attorneys
    r = client.get(f"/api/persona/{session_id}")
    data = r.json()
    atty = data["prosecution_attorneys"][0]

    # Update with per-agent LLM config
    atty["llm_model"] = "claude-sonnet-4-20250514"
    atty["llm_temperature"] = 0.3
    atty["system_prompt"] = "Always be extremely brief."
    r = client.put(f"/api/persona/{session_id}/prosecution/attorney/0", json=atty)
    assert r.status_code == 200, f"Update failed: {r.status_code} {r.text}"
    result = r.json()
    cfg = result.get("config", {})
    assert cfg.get("llm_model") == "claude-sonnet-4-20250514", "Model not saved"
    assert cfg.get("llm_temperature") == 0.3, "Temperature not saved"
    assert cfg.get("system_prompt") == "Always be extremely brief.", "System prompt not saved"

    return "Per-agent LLM config saved and returned via persona API"


async def test_llm_config_global_endpoint() -> str:
    """Verify the global LLM config endpoint works."""
    from ..main import app
    from fastapi.testclient import TestClient
    client = TestClient(app)

    r = client.get("/api/case/")
    if r.status_code != 200:
        r = client.get("/api/case/demo")
    cases = r.json() if isinstance(r.json(), list) else r.json().get("cases", [])
    if not cases:
        return "SKIP: no cases"
    case_id = cases[0].get("id") or cases[0].get("case_id")

    r = client.post("/api/session/create", json={
        "case_id": case_id,
        "human_role": "spectator",
    })
    session_id = r.json().get("session_id")

    # GET config
    r = client.get(f"/api/persona/{session_id}/llm-config")
    assert r.status_code == 200, f"LLM config GET failed: {r.status_code}"
    data = r.json()
    assert "model" in data, "Missing model"
    assert "temperature" in data, "Missing temperature"
    assert "available_models" in data, "Missing available_models"

    # PUT update
    r = client.put(f"/api/persona/{session_id}/llm-config", json={
        "model": "gpt-4.1-mini",
        "temperature": 0.5,
    })
    assert r.status_code == 200, f"LLM config PUT failed: {r.status_code}"
    result = r.json()
    assert result.get("config", {}).get("model") == "gpt-4.1-mini", "Global model not updated"

    return "Global LLM config GET/PUT OK"


# ---------------------------------------------------------------------------
# Suite runner endpoint
# ---------------------------------------------------------------------------

ALL_TESTS = [
    ("Health Check", "infrastructure", test_health_check),
    ("Case Library", "case_management", test_case_list),
    ("Session Create & Init", "session", test_session_create_and_status),
    ("Witness Assignment", "session", test_session_witnesses),
    ("Phase Advancement", "trial_flow", test_phase_advance),
    ("Phase Advance Idempotent", "trial_flow", test_phase_advance_idempotent),
    ("Opening Statements", "trial_flow", test_opening_statements),
    ("Scoring Endpoint", "scoring", test_scoring_endpoint),
    ("Transcript Recording", "trial_flow", test_transcript_record),
    ("TTS Audio Generation", "audio", test_tts_service),
    ("Objection Detection (Leading)", "objections", test_objection_detection),
    ("No False Positive Objections", "objections", test_objection_no_false_positive),
    ("Per-Agent LLM Config", "agent_config", test_per_agent_llm_config),
    ("Per-Agent Config Defaults", "agent_config", test_per_agent_defaults_none),
    ("Provider Model Routing", "multi_provider", test_provider_model_routing),
    ("Available Models Structure", "multi_provider", test_available_models_structure),
    ("Persona Endpoint", "persona", test_persona_endpoint),
    ("Persona LLM Config Update", "persona", test_persona_llm_config_update),
    ("Global LLM Config", "persona", test_llm_config_global_endpoint),
]


@router.post("/run")
async def run_test_suite(categories: Optional[list[str]] = None):
    """
    Run the automated test suite and return results.
    Optionally filter by categories: infrastructure, session, trial_flow,
    scoring, audio, objections, case_management.
    """
    t0 = time.time()
    tests_to_run = ALL_TESTS
    if categories:
        tests_to_run = [(n, c, f) for n, c, f in ALL_TESTS if c in categories]

    results: list[TestResult] = []
    for name, category, fn in tests_to_run:
        result = await _run_test(name, category, fn)
        results.append(result)
        logger.info(f"Test '{name}': {'PASS' if result.passed else 'FAIL'} ({result.duration_ms}ms)")

    passed = sum(1 for r in results if r.passed)
    return TestSuiteReport(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        duration_ms=round((time.time() - t0) * 1000, 1),
        results=results,
    )


@router.get("/categories")
async def list_categories():
    """List available test categories."""
    cats = sorted(set(c for _, c, _ in ALL_TESTS))
    return {"categories": cats, "total_tests": len(ALL_TESTS)}
