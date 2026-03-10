# System Architecture Specification

## 1. Frontend

- Built in Next.js 14 (TypeScript)
- Responsible only for:
  - Audio capture
  - Audio playback
  - UI rendering
  - WebRTC signaling

Frontend must NEVER:
- Call LLMs directly
- Make scoring decisions
- Control trial logic

---

## 2. Backend

- Python FastAPI
- Stateless request handling
- All trial logic flows through LangGraph

Backend responsibilities:
- Session lifecycle
- Agent orchestration
- Audio routing
- Trial state enforcement
- Scoring persistence

---

## 3. Agent Orchestration

LangGraph is the single source of truth for:
- Trial phase
- Speaker permissions
- Interrupts
- Objections
- Transitions

No agent may bypass the graph.

---

## 4. Audio Pipeline

User:
Mic → WebRTC → Whisper → Text

AI:
Text → GPT-4.1 → Persona Conditioning → TTS → WebRTC → Speaker

All audio must be streamed (no blocking).


## 5. Data Storage

- **Supabase (PostgreSQL)**: Sessions, scoring results, case metadata, participants, prep materials (including pre-generated opening statements), live scores, transcript metadata
- **Supabase Storage**: Case material files (PDFs, exhibits, affidavits), trial transcripts, TTS audio cache
- **Pinecone**: Case facts, witness memory, transcript embeddings

### Preparation Materials Schema

The `prep_materials` table stores AI-generated content per `case_id`:

| Column | Type | Description |
|--------|------|-------------|
| `case_brief` | TEXT | AI-generated case brief |
| `theory_plaintiff` | TEXT | Prosecution theory of the case |
| `theory_defense` | TEXT | Defense theory of the case |
| `opening_plaintiff` | TEXT | Pre-generated prosecution opening statement |
| `opening_defense` | TEXT | Pre-generated defense opening statement |
| `witness_outlines` | JSONB | Structured witness outlines |
| `objection_playbook` | JSONB | Objection strategies |
| `cross_exam_traps` | JSONB | Cross-examination traps |
| `generation_status` | JSONB | Per-section generation status |

### Supabase Storage Structure

Case files are stored in the `case-materials` bucket:

```
cases/{case_id}/
├── summary/              # Case summary/overview documents
├── witnesses_plaintiff/  # Plaintiff/prosecution witness affidavits
├── witnesses_defense/    # Defense witness affidavits
├── exhibits/             # Evidence (documents, images)
├── stipulations/         # Agreed-upon facts
├── jury_instructions/    # Legal standards
└── rules/                # Competition rules
```

TTS audio files are stored in the `tts-audio-cache` bucket:

```
tts-audio-cache/
└── {sha256_hash}.mp3    # Keyed by SHA-256(text + role + speaker)
```

Trial transcripts are stored in the `trial-transcripts` bucket:

```
transcripts/{user_id}/{case_id}/{session_id}.json
```

---

## LLM Access

- API keys (OpenAI, Anthropic, Google, xAI, Whisper, TTS, Supabase, Pinecone) are stored **only in backend environment variables**.
- Agents never hold API keys or call providers directly.
- Agents communicate with the LLM via **local backend functions** (e.g., `call_llm(prompt, persona)`).
- All memory, persona, and prompt assembly is done in backend before calling LLM.
- Frontend communicates with backend via REST or WebRTC for audio streaming; no keys in frontend.

### Multi-Provider Support

The LLM service supports four providers via `backend/app/services/llm_providers.py`:

| Provider | Models | Env Var |
|----------|--------|---------|
| OpenAI | GPT-4.1, GPT-4o, etc. | `OPENAI_API_KEY` |
| Anthropic | Claude Sonnet 4, Claude 3.5 Sonnet/Haiku | `ANTHROPIC_API_KEY` |
| Google | Gemini 2.5 Pro/Flash, Gemini 2.0 Flash | `GOOGLE_API_KEY` |
| xAI | Grok 3, Grok 3 Mini | `XAI_API_KEY` |

Model → provider routing is automatic. Missing API keys cause graceful fallback to OpenAI.

### Per-Agent Configuration

Each agent persona carries optional LLM overrides:
- `llm_model` — override the model for this specific agent
- `llm_temperature` — override temperature
- `llm_max_tokens` — override max tokens
- `custom_system_prompt` — prepended to the agent's built-in system prompt

Resolution order: **per-agent override → global session override → method default**

Changes saved via the persona API are hot-patched to live agents immediately.

---

## Authentication

- **Supabase Auth** for user identity (email + OAuth providers)
- Frontend: `@supabase/ssr` with Next.js middleware for route protection
- Backend: JWT validation via `get_current_user_id()` dependency
- User ID scopes transcript history and storage paths

---

## Transcript Storage

- **Supabase Storage bucket**: `trial-transcripts`
- File path: `transcripts/{user_id}/{case_id}/{session_id}.json`
- **Metadata table**: `trial_transcript_history` (session_id, user_id, case_id, case_name, started_at, entry_count, phases)
- Transcripts saved progressively after openings, each exam, and closings
- Public transcript listing via `GET /api/trial/transcripts/public` (no auth required)
- Individual transcript retrieval includes `audio_keys` map linking entries to cached TTS audio

---

## TTS Audio Cache

- **Supabase Storage bucket**: `tts-audio-cache`
- Files keyed by SHA-256 hash of (text content + role + speaker name)
- Audio generated once during live trial, stored permanently, never regenerated
- Served via `GET /api/public/tts/audio/{cache_key}` (public, no auth)
- Backfill for historical transcripts: `POST /api/admin/backfill-audio` (async via `BackgroundTasks`)

---

## Public Routes

The following frontend routes are accessible without authentication:

| Route | Purpose |
|-------|---------|
| `/` | Homepage |
| `/login` | Login/signup page |
| `/about` | About page |
| `/contact` | Contact page |
| `/trials` | Public recorded trials listing |
| `/trials/{sessionId}` | Unified trial detail (transcript + audio + scores) |
| `/auth/*` | OAuth callback handlers |

---

## Deployment

| Component | Platform | Config |
|-----------|----------|--------|
| Frontend | Vercel | `frontend/next.config.mjs` (standalone output) |
| Backend | Render | `backend/render.yaml` (Python 3.11, uvicorn) |
| Database | Supabase | PostgreSQL + Auth + Storage |

CORS origins are configured via the `CORS_ORIGINS` environment variable (comma-separated).
