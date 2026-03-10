"""
FastAPI Application Entry Point

Per ARCHITECTURE.md:
- Python FastAPI
- Stateless request handling
- All trial logic flows through LangGraph

Backend responsibilities:
- Session lifecycle
- Agent orchestration
- Audio routing
- Trial state enforcement
- Scoring persistence
"""

import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from contextlib import asynccontextmanager

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from .api import session, trial, audio, scoring, case, preparation, persona, test_suite
from .config import get_config

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown lifecycle for the app."""
    # --- Startup ---
    # Sync Supabase Storage files with database records
    try:
        from .db.storage import get_storage_service
        from .data.demo_cases import (
            MYLAW_CASE_SOURCES, get_uploaded_case, save_uploaded_case
        )
        
        storage = get_storage_service()
        if storage.is_available:
            synced = 0
            for source_case in MYLAW_CASE_SOURCES:
                cid = source_case["id"]
                try:
                    files = storage.list_files(cid)
                    if not files:
                        continue
                    
                    existing = get_uploaded_case(cid)
                    file_sections = set(f.get("section", "other") for f in files)
                    existing_sections = set(
                        existing.get("sections", {}).keys()
                    ) if existing else set()
                    
                    if existing and file_sections.issubset(existing_sections):
                        continue
                    
                    sections = {}
                    storage_files = []
                    for f in files:
                        sec = f.get("section", "other")
                        if sec not in sections:
                            sections[sec] = {
                                "content": f"[File in storage: {f['name']}]",
                                "filename": f["name"],
                                "uploaded_at": f.get("created_at", ""),
                                "storage_path": f["path"],
                            }
                        storage_files.append({
                            "path": f["path"],
                            "filename": f["name"],
                            "original_filename": f["name"],
                            "section": sec,
                            "size": f.get("size", 0),
                            "uploaded_at": f.get("created_at", ""),
                        })
                    
                    if existing:
                        case_data = existing
                        for sid, sd in sections.items():
                            if sid not in case_data.get("sections", {}):
                                case_data.setdefault("sections", {})[sid] = sd
                        case_data.setdefault("storage_files", []).extend(storage_files)
                    else:
                        case_data = {
                            "id": cid,
                            "title": source_case["title"],
                            "case_type": source_case["case_type"],
                            "source": source_case["source"],
                            "year": source_case["year"],
                            "difficulty": source_case.get("difficulty", "intermediate"),
                            "description": source_case.get("description", ""),
                            "sections": sections,
                            "witnesses": [], "exhibits": [], "facts": [],
                            "stipulations": [], "legal_standards": [],
                            "storage_files": storage_files,
                        }
                    
                    save_uploaded_case(cid, case_data)
                    synced += 1
                except Exception as e:
                    logger.debug(f"Sync skip {cid}: {e}")
            
            if synced:
                logger.info(f"Synced {synced} case(s) from Supabase Storage")
    except Exception as e:
        logger.debug(f"Storage sync skipped: {e}")
    
    # Auto-load example parsed cases from Example/ directory
    _autoload_example_cases()
    
    yield
    # --- Shutdown ---


def _autoload_example_cases():
    """Pre-load any parsed JSON files from the Example/ directory so they
    appear immediately in the case library without requiring manual upload."""
    import json as _json
    from .api.case import _cases, CaseData
    from .data.demo_cases import save_uploaded_case, AMTA_CASE_SOURCES

    example_dir = Path(__file__).parent.parent.parent / "Example"
    if not example_dir.exists():
        return

    loaded = 0
    for json_path in sorted(example_dir.glob("*_parsed.json")):
        try:
            data = _json.loads(json_path.read_text(encoding="utf-8"))
            case_name = data.get("name", json_path.stem)

            # Match to a known AMTA source entry if possible
            amta_id = None
            name_lower = case_name.lower()
            for src in AMTA_CASE_SOURCES:
                if src["title"].lower() in name_lower or name_lower in src["title"].lower():
                    amta_id = src["id"]
                    break

            case_id = amta_id or f"example_{json_path.stem}"

            if case_id in _cases:
                continue

            cd = CaseData(
                case_id=case_id,
                name=case_name,
                source_type="json",
                source_filename=json_path.name,
            )
            cd.synopsis = data.get("synopsis", "")
            cd.case_type = data.get("case_type", "criminal")
            cd.charge = data.get("charge", "")
            cd.plaintiff = data.get("plaintiff", "")
            cd.defendant = data.get("defendant", "")
            cd.facts = data.get("facts", [])
            cd.witnesses = data.get("witnesses", [])
            cd.exhibits = data.get("exhibits", [])
            cd.stipulations = data.get("stipulations", [])
            cd.legal_standards = data.get("legal_standards", [])
            cd.special_instructions = data.get("special_instructions", [])
            cd.jury_instructions = data.get("jury_instructions", [])
            cd.indictment = data.get("indictment", {})
            cd.relevant_law = data.get("relevant_law", {})
            cd.motions_in_limine = data.get("motions_in_limine", [])
            cd.witness_calling_restrictions = data.get("witness_calling_restrictions", {})
            cd.fact_count = len(cd.facts)
            cd.witness_count = len(cd.witnesses)
            cd.exhibit_count = len(cd.exhibits)

            _cases[case_id] = cd

            # Also register in the demo-cases uploaded-case tracker so
            # get_all_demo_cases() marks the AMTA entry as "has_uploads"
            save_uploaded_case(case_id, {
                "id": case_id,
                "title": case_name,
                "case_type": cd.case_type,
                "source": "Example (auto-loaded)",
                "year": 2026,
                "difficulty": "advanced",
                "description": cd.synopsis or f"Auto-loaded from {json_path.name}",
                "sections": {"summary": {"content": cd.synopsis}},
                "witnesses": cd.witnesses,
                "exhibits": cd.exhibits,
                "facts": cd.facts,
                "stipulations": cd.stipulations,
                "legal_standards": cd.legal_standards,
            })

            loaded += 1
            logger.info(f"Auto-loaded example case: {case_name} (id={case_id})")
        except Exception as e:
            logger.warning(f"Failed to auto-load {json_path.name}: {e}")

    if loaded:
        logger.info(f"Auto-loaded {loaded} example case(s) from {example_dir}")


app = FastAPI(
    title="Mock Trial AI",
    description="Audio-first, agent-driven mock trial simulation",
    version="0.1.0",
    lifespan=lifespan,
)

_default_origins = "http://localhost:3000,http://localhost:3001"
_cors_origins = [
    o.strip() for o in os.getenv("CORS_ORIGINS", _default_origins).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(session.router, prefix="/api/session", tags=["session"])
app.include_router(trial.router, prefix="/api/trial", tags=["trial"])
app.include_router(audio.router, prefix="/api/audio", tags=["audio"])
app.include_router(scoring.router, prefix="/api/scoring", tags=["scoring"])
app.include_router(case.router, prefix="/api/case", tags=["case"])
app.include_router(preparation.router, prefix="/api/prep", tags=["preparation"])
app.include_router(persona.router, prefix="/api/persona", tags=["persona"])

if get_config().debug:
    app.include_router(test_suite.router, prefix="/api/tests", tags=["tests"])
    logger.info("Test suite endpoints enabled (DEBUG=true)")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


from pydantic import BaseModel, Field  # noqa: E402
from fastapi.responses import StreamingResponse  # noqa: E402


import hashlib  # noqa: E402
from typing import List, Optional  # noqa: E402
from io import BytesIO  # noqa: E402

TTS_BUCKET = "tts-audio-cache"
_tts_bucket_ready = False


def _ensure_tts_bucket():
    """Create the Supabase Storage bucket for TTS audio if it doesn't exist."""
    global _tts_bucket_ready
    if _tts_bucket_ready:
        return
    try:
        from .db.supabase_client import get_supabase_client
        client = get_supabase_client()
        buckets = client.storage.list_buckets()
        names = [b.name for b in buckets]
        if TTS_BUCKET not in names:
            client.storage.create_bucket(
                TTS_BUCKET,
                options={"public": True, "file_size_limit": 10485760},
            )
            logger.info(f"Created TTS audio bucket: {TTS_BUCKET}")
        _tts_bucket_ready = True
    except Exception as e:
        logger.warning(f"Could not ensure TTS bucket: {e}")


def _tts_cache_key(text: str, role: str, speaker: str) -> str:
    raw = f"{text.strip()[:2000]}|{role.lower()}|{speaker.lower()}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _tts_storage_path(cache_key: str) -> str:
    return f"audio/{cache_key}.mp3"


def _download_from_supabase(cache_key: str) -> bytes | None:
    """Try to download cached audio from Supabase Storage."""
    try:
        from .db.supabase_client import get_supabase_client
        client = get_supabase_client()
        path = _tts_storage_path(cache_key)
        data = client.storage.from_(TTS_BUCKET).download(path)
        if data and len(data) > 0:
            return data
    except Exception:
        pass
    return None


def _upload_to_supabase(cache_key: str, audio_bytes: bytes):
    """Upload audio to Supabase Storage."""
    try:
        from .db.supabase_client import get_supabase_client
        _ensure_tts_bucket()
        client = get_supabase_client()
        path = _tts_storage_path(cache_key)
        client.storage.from_(TTS_BUCKET).upload(
            path, audio_bytes,
            file_options={"content-type": "audio/mpeg", "upsert": "true"},
        )
        logger.info(f"Stored TTS audio in Supabase: {cache_key} ({len(audio_bytes)} bytes)")
    except Exception as e:
        logger.error(f"Failed to store TTS in Supabase: {e}")


def _generate_and_store(text: str, role: str, speaker: str) -> bytes:
    """Generate TTS audio, store in Supabase, return audio bytes."""
    from .services.tts import get_voice_for_speaker
    from .graph.trial_graph import Role

    cache_key = _tts_cache_key(text, role, speaker)

    existing = _download_from_supabase(cache_key)
    if existing:
        return existing

    role_enum_map = {
        "attorney_plaintiff": Role.ATTORNEY_PLAINTIFF,
        "attorney_defense": Role.ATTORNEY_DEFENSE,
        "witness": Role.WITNESS,
        "judge": Role.JUDGE,
    }
    role_map = {
        "attorney_plaintiff": "attorney_plaintiff",
        "attorney_defense": "attorney_defense",
        "witness": "witness",
        "judge": "judge",
        "clerk": "witness",
        "bailiff": "witness",
        "narrator": "judge",
    }
    mapped = role_map.get(role.lower(), "judge")
    trial_role = role_enum_map.get(mapped, Role.JUDGE)
    voice = get_voice_for_speaker(speaker or "", trial_role)

    from openai import OpenAI
    api_key = os.getenv("OPENAI_API_KEY")
    client = OpenAI(api_key=api_key)
    response = client.audio.speech.create(
        model="gpt-4o-mini-tts",
        voice=voice.value,
        input=text.strip()[:2000],
        response_format="mp3",
    )
    audio_bytes = response.content
    _upload_to_supabase(cache_key, audio_bytes)
    return audio_bytes


@app.get("/api/public/tts/audio/{cache_key}")
async def get_cached_tts(cache_key: str):
    """Serve pre-generated TTS audio from Supabase Storage by hash key."""
    data = _download_from_supabase(cache_key)
    if not data:
        raise HTTPException(status_code=404, detail="Audio not found")
    return StreamingResponse(BytesIO(data), media_type="audio/mpeg")


def _list_existing_tts_keys() -> set[str]:
    """List all cache keys that already exist in Supabase TTS bucket."""
    try:
        from .db.supabase_client import get_supabase_client
        _ensure_tts_bucket()
        client = get_supabase_client()
        files = client.storage.from_(TTS_BUCKET).list("audio", {"limit": 10000})
        return {f["name"].replace(".mp3", "") for f in files if f.get("name", "").endswith(".mp3")}
    except Exception as e:
        logger.warning(f"Failed to list TTS cache: {e}")
        return set()


from fastapi import BackgroundTasks  # noqa: E402

_backfill_status: dict = {"running": False, "result": None}


def _run_backfill():
    """Background worker: generate TTS audio for all recorded trials."""
    from .db.storage import get_transcript_storage
    storage = get_transcript_storage()
    all_transcripts = storage.list_transcripts("default")

    existing_keys = _list_existing_tts_keys()
    total_generated = 0
    total_cached = 0
    total_errors = 0
    session_results = []

    for meta in all_transcripts:
        sid = meta.get("session_id")
        if not meta.get("storage_path"):
            continue
        data = storage.get_transcript(sid)
        if not data:
            continue
        entries = data.get("transcript", [])
        gen = 0
        cached = 0
        errors = 0
        for entry in entries:
            text = (entry.get("text") or entry.get("content") or "").strip()
            if not text or len(text) < 3:
                continue
            role = entry.get("role", "narrator")
            speaker = entry.get("speaker", "")
            key = _tts_cache_key(text, role, speaker)
            if key in existing_keys:
                cached += 1
                continue
            try:
                _generate_and_store(text, role, speaker)
                existing_keys.add(key)
                gen += 1
            except Exception as e:
                logger.error(f"Backfill TTS error [{sid}]: {e}")
                errors += 1
        total_generated += gen
        total_cached += cached
        total_errors += errors
        session_results.append({"session_id": sid, "generated": gen, "cached": cached, "errors": errors})
        logger.info(f"Backfill [{sid}]: {gen} generated, {cached} cached, {errors} errors")

    _backfill_status["result"] = {
        "total_generated": total_generated,
        "total_already_cached": total_cached,
        "total_errors": total_errors,
        "sessions": session_results,
    }
    _backfill_status["running"] = False
    logger.info(f"Backfill complete: {total_generated} generated, {total_cached} cached, {total_errors} errors")


@app.post("/api/admin/backfill-audio")
async def backfill_trial_audio(bg: BackgroundTasks):
    """Start background TTS audio generation for all recorded trials. Non-blocking."""
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="TTS not configured")
    if _backfill_status["running"]:
        return {"status": "already_running"}

    _backfill_status["running"] = True
    _backfill_status["result"] = None
    bg.add_task(_run_backfill)
    return {"status": "started", "message": "Backfill running in background. Check /api/admin/backfill-status for progress."}


@app.get("/api/admin/backfill-status")
async def backfill_status():
    """Check status of background audio backfill."""
    return {
        "running": _backfill_status["running"],
        "result": _backfill_status["result"],
    }


class ContactRequest(BaseModel):
    name: str
    email: str = Field(..., pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    subject: str = ""
    message: str


@app.post("/api/contact")
async def contact_form(req: ContactRequest):
    """Send a contact-form email to the site owner via SMTP."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASSWORD")
    smtp_from = os.getenv("SMTP_FROM", smtp_user)

    if not smtp_host or not smtp_user or not smtp_pass:
        raise HTTPException(status_code=500, detail="Email is not configured on the server.")

    subject_line = req.subject.strip() if req.subject.strip() else "New Contact Form Submission"

    html = f"""\
<div style="font-family:sans-serif;max-width:600px;margin:0 auto;padding:20px;">
  <div style="background:#1e293b;border-radius:12px;padding:24px;color:#fff;">
    <h2 style="margin:0 0 4px;">MockPrepAI — Contact Form</h2>
    <p style="color:#94a3b8;margin:0 0 20px;font-size:14px;">New message received</p>
    <table style="width:100%;border-collapse:collapse;font-size:14px;">
      <tr><td style="color:#94a3b8;padding:6px 12px 6px 0;vertical-align:top;white-space:nowrap;">Name</td><td style="color:#fff;padding:6px 0;">{req.name}</td></tr>
      <tr><td style="color:#94a3b8;padding:6px 12px 6px 0;vertical-align:top;white-space:nowrap;">Email</td><td style="color:#fff;padding:6px 0;"><a href="mailto:{req.email}" style="color:#fbbf24;">{req.email}</a></td></tr>
      <tr><td style="color:#94a3b8;padding:6px 12px 6px 0;vertical-align:top;white-space:nowrap;">Subject</td><td style="color:#fff;padding:6px 0;">{subject_line}</td></tr>
    </table>
    <div style="margin-top:16px;padding:16px;background:#0f172a;border-radius:8px;color:#e2e8f0;font-size:14px;line-height:1.6;white-space:pre-wrap;">{req.message}</div>
  </div>
</div>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[MockPrepAI Contact] {subject_line}"
    msg["From"] = smtp_from
    msg["To"] = smtp_user
    msg["Reply-To"] = req.email
    msg.attach(MIMEText(f"From: {req.name} <{req.email}>\nSubject: {subject_line}\n\n{req.message}", "plain"))
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.sendmail(smtp_from, [smtp_user], msg.as_string())
    except Exception as e:
        logger.error(f"Contact email failed: {e}")
        raise HTTPException(status_code=500, detail="Failed to send message. Please try again later.")

    return {"success": True, "message": "Your message has been sent successfully."}


# =============================================================================
# SEED DEMO DATA
# =============================================================================

@app.post("/api/demo/seed")
async def seed_demo_data():
    """Insert demo trial history and scores into Supabase for the test user."""
    from datetime import datetime, timedelta
    from .db.supabase_client import get_supabase_client

    target_email = "prasanna.jagatap@gmail.com"

    client = get_supabase_client()

    # Look up user_id from Supabase auth
    user_id = None
    try:
        resp = client.auth.admin.list_users()
        for u in resp:
            if hasattr(u, "email") and u.email == target_email:
                user_id = u.id
                break
    except Exception:
        pass

    if not user_id:
        # Fallback: check trial_transcript_history for any row with this email-like user_id
        try:
            rows = client.table("trial_transcript_history").select("user_id").limit(1).execute()
            if rows.data:
                user_id = rows.data[0]["user_id"]
        except Exception:
            pass

    if not user_id:
        raise HTTPException(status_code=404, detail=f"Could not find user_id for {target_email}. Make sure the user has signed up.")

    now = datetime.utcnow()
    day = timedelta(days=1)

    sessions = [
        {
            "session_id": "seed-demo-1",
            "user_id": user_id,
            "case_id": "amta_2026_state_v_martin",
            "case_name": "State of Midlands v. Charlie Martin",
            "human_role": "attorney_plaintiff",
            "started_at": (now - 2 * day).isoformat(),
            "updated_at": (now - 2 * day).isoformat(),
            "entry_count": 48,
            "phases_completed": ["opening", "prosecution_case", "defense_case", "closing", "scoring"],
        },
        {
            "session_id": "seed-demo-2",
            "user_id": user_id,
            "case_id": "mylaw_2024_state_v_luna",
            "case_name": "State of Maryland v. Dana Luna",
            "human_role": "attorney_defense",
            "started_at": (now - 5 * day).isoformat(),
            "updated_at": (now - 5 * day).isoformat(),
            "entry_count": 52,
            "phases_completed": ["opening", "prosecution_case", "defense_case", "closing", "scoring"],
        },
        {
            "session_id": "seed-demo-3",
            "user_id": user_id,
            "case_id": "mylaw_2023_harper_v_reese",
            "case_name": "Parker Harper v. Dakota Reese",
            "human_role": "attorney_plaintiff",
            "started_at": (now - 9 * day).isoformat(),
            "updated_at": (now - 9 * day).isoformat(),
            "entry_count": 35,
            "phases_completed": ["opening", "prosecution_case", "defense_case", "closing", "scoring"],
        },
        {
            "session_id": "seed-demo-4",
            "user_id": user_id,
            "case_id": "mylaw_2022_state_v_grimes",
            "case_name": "State of Maryland v. Ryan Grimes",
            "human_role": "attorney_defense",
            "started_at": (now - 14 * day).isoformat(),
            "updated_at": (now - 14 * day).isoformat(),
            "entry_count": 41,
            "phases_completed": ["opening", "prosecution_case", "defense_case", "closing", "scoring"],
        },
        {
            "session_id": "seed-demo-5",
            "user_id": user_id,
            "case_id": "mylaw_2021_griggs_v_donahue",
            "case_name": "Estate of Aaron Griggs v. Jodie Donahue",
            "human_role": "attorney_plaintiff",
            "started_at": (now - 20 * day).isoformat(),
            "updated_at": (now - 20 * day).isoformat(),
            "entry_count": 29,
            "phases_completed": ["opening", "prosecution_case"],
        },
    ]

    scores_data = {
        "seed-demo-1": {
            "attorney_plaintiff_opening": {"side": "Prosecution", "average": 8.2, "name": "Plaintiff Attorney — Opening"},
            "attorney_plaintiff_direct_cross": {"side": "Prosecution", "average": 7.8, "name": "Plaintiff Attorney — Direct/Cross"},
            "attorney_defense_opening": {"side": "Defense", "average": 7.5, "name": "Defense Attorney — Opening"},
            "attorney_defense_direct_cross": {"side": "Defense", "average": 7.1, "name": "Defense Attorney — Direct/Cross"},
            "witness_riley_chen": {"side": "Prosecution", "average": 7.4, "name": "Riley Chen"},
            "witness_sam_lopez": {"side": "Defense", "average": 6.9, "name": "Sam Lopez"},
        },
        "seed-demo-2": {
            "attorney_plaintiff_opening": {"side": "Prosecution", "average": 7.0, "name": "Plaintiff Attorney — Opening"},
            "attorney_plaintiff_direct_cross": {"side": "Prosecution", "average": 7.3, "name": "Plaintiff Attorney — Direct/Cross"},
            "attorney_defense_opening": {"side": "Defense", "average": 8.5, "name": "Defense Attorney — Opening"},
            "attorney_defense_direct_cross": {"side": "Defense", "average": 8.1, "name": "Defense Attorney — Direct/Cross"},
            "attorney_defense_closing": {"side": "Defense", "average": 8.7, "name": "Defense Attorney — Closing"},
            "witness_dana_luna": {"side": "Defense", "average": 7.6, "name": "Dana Luna"},
        },
        "seed-demo-3": {
            "attorney_plaintiff_opening": {"side": "Prosecution", "average": 7.4, "name": "Plaintiff Attorney — Opening"},
            "attorney_plaintiff_direct_cross": {"side": "Prosecution", "average": 6.9, "name": "Plaintiff Attorney — Direct/Cross"},
            "attorney_plaintiff_closing": {"side": "Prosecution", "average": 7.7, "name": "Plaintiff Attorney — Closing"},
            "attorney_defense_opening": {"side": "Defense", "average": 7.2, "name": "Defense Attorney — Opening"},
            "attorney_defense_direct_cross": {"side": "Defense", "average": 6.8, "name": "Defense Attorney — Direct/Cross"},
        },
        "seed-demo-4": {
            "attorney_plaintiff_opening": {"side": "Prosecution", "average": 6.8, "name": "Plaintiff Attorney — Opening"},
            "attorney_defense_opening": {"side": "Defense", "average": 7.9, "name": "Defense Attorney — Opening"},
            "attorney_defense_direct_cross": {"side": "Defense", "average": 7.5, "name": "Defense Attorney — Direct/Cross"},
            "attorney_defense_closing": {"side": "Defense", "average": 8.0, "name": "Defense Attorney — Closing"},
        },
    }

    inserted_history = 0
    inserted_scores = 0

    for s in sessions:
        try:
            client.table("trial_transcript_history").upsert(s, on_conflict="session_id").execute()
            inserted_history += 1
        except Exception as e:
            logger.warning(f"Failed to seed history {s['session_id']}: {e}")

    for sid, scores in scores_data.items():
        try:
            client.table("live_scores").upsert({
                "session_id": sid,
                "scores": scores,
                "phase": "scoring",
                "transcript_length": 0,
            }, on_conflict="session_id").execute()
            inserted_scores += 1
        except Exception as e:
            logger.warning(f"Failed to seed scores {sid}: {e}")

    return {
        "success": True,
        "user_id": user_id,
        "inserted_history": inserted_history,
        "inserted_scores": inserted_scores,
        "message": f"Seeded {inserted_history} sessions and {inserted_scores} score sets for {target_email}",
    }
