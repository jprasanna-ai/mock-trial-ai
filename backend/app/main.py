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
from pathlib import Path
from contextlib import asynccontextmanager

# Load environment variables from .env file
from dotenv import load_dotenv
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import session, trial, audio, scoring, case, preparation, persona, test_suite

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
app.include_router(test_suite.router, prefix="/api/tests", tags=["tests"])


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}
