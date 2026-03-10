# Mock Trial AI

> An audio-first, agent-driven mock trial simulation platform

---

## 1. What This Project Is

This repository contains an **audio-first, agent-driven mock trial simulation**.

The system simulates:
- A real mock trial courtroom
- Attorneys, witnesses, and judges as autonomous AI agents
- One human user participating via microphone
- Deterministic trial flow enforced by a state machine
- AMTA-style scoring and post-trial coaching

**This is NOT:**
- A chatbot
- A turn-based text game
- A legal advice system
- A multiplayer platform (v1)

---

## 2. Core Design Philosophy

> **Read this first before touching any code.**

| Principle | Description |
|-----------|-------------|
| **Audio is primary** | If a feature bypasses audio, it is wrong |
| **LangGraph controls the courtroom** | No agent may speak, interrupt, or object outside the graph |
| **Agents are adversarial** | They do not help each other or the user unless explicitly allowed |
| **Personas affect everything** | Reasoning, speech style, voice output, scoring bias |
| **Determinism beats cleverness** | Predictable behavior > creative behavior |

---

## 3. Repository Structure

```
mock-trial-ai/
├── frontend/          # Next.js UI, audio capture, playback
├── backend/           # FastAPI, agents, LangGraph orchestration
├── specs/             # Source-of-truth documentation
└── README.md
```

> **Important:** If it's not defined in `/specs`, it does not exist.

---

## 4. Specs Directory (Source of Truth)

All development must conform to these documents:

| File | Purpose |
|------|---------|
| `SPEC.md` | Product definition & trial lifecycle |
| `ARCHITECTURE.md` | System boundaries & responsibilities |
| `AGENTS.md` | Agent behavior contracts |
| `AUDIO.md` | Audio & voice rules |
| `SCORING.md` | Judge scoring rubric |
| `VERIFICATION.md` | Implementation checklist |

> **If code and specs disagree, the specs win.**

---

## 5. System Overview

### High-Level Flow

```
User speaks
 → Whisper (STT)
 → Trial State Validation (LangGraph)
 → Agent Reasoning (GPT-4.1)
 → Persona Conditioning
 → Text-to-Speech
 → Audio streamed back
 → Transcript + scoring recorded
```

### Preparation Phase Pipeline

```
Case loaded → AI generates prep materials in parallel:
  ├── Case Brief
  ├── Theory of the Case (plaintiff & defense)
  ├── Witness Outlines
  ├── Objection Playbook
  ├── Cross-Exam Traps
  └── Opening Statements (plaintiff & defense)  ← Pre-generated!

Opening statements are cached in the database.
"Begin Trial" button is gated until openings are ready.
During the live trial, only TTS audio is fetched (~3-5s vs 15-25s).
```

### Single Source of Truth

The **LangGraph trial state machine** is the authority for:
- Who can speak
- When objections are valid
- When judges can interrupt
- When scoring begins

---

## 6. Technology Stack (Locked)

### Frontend
- Next.js 14
- TypeScript
- WebRTC (audio streaming)

### Backend
- Python
- FastAPI
- LangGraph

### AI (Multi-Provider)
- **OpenAI** — GPT-4.1, GPT-4.1 Mini/Nano, GPT-4o, GPT-4o Mini
- **Anthropic** — Claude Sonnet 4, Claude 3.5 Sonnet, Claude 3.5 Haiku
- **Google** — Gemini 2.5 Pro, Gemini 2.5 Flash, Gemini 2.0 Flash
- **xAI** — Grok 3, Grok 3 Mini
- OpenAI Whisper (speech-to-text)
- OpenAI TTS (persona voices)

Each AI agent can be configured independently with its own model, temperature, and system prompt.

### Data & Auth
- Supabase (PostgreSQL - sessions, scores, transcript history)
- Supabase Auth (email + OAuth: Google, LinkedIn, Facebook, Discord)
- Supabase Storage (case materials, trial transcripts)
- Pinecone (case data, memory)

---

## 7. Local Development Setup

### Prerequisites

- macOS
- Node.js ≥ 18
- Python ≥ 3.10
- Supabase account (provides PostgreSQL)
- Pinecone API key
- OpenAI API key

### 7.1 Environment Variables

Per `ARCHITECTURE.md` - LLM Access:
- API keys are stored **only in backend environment variables**
- Agents never hold API keys or call OpenAI directly
- Frontend never has access to API keys

Create `.env` files in both frontend and backend.

**Backend `.env` (required):**
```bash
OPENAI_API_KEY=sk-your-openai-api-key
PINECONE_API_KEY=your-pinecone-api-key
PINECONE_INDEX_NAME=mock-trial  # optional, defaults to "mock-trial"

# Supabase (https://supabase.com/dashboard)
SUPABASE_URL=https://your-project-ref.supabase.co
SUPABASE_ANON_KEY=your-supabase-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-supabase-service-role-key
DATABASE_URL=postgresql://postgres.your-project-ref:password@aws-0-region.pooler.supabase.com:6543/postgres

# Multi-Provider LLM Keys (optional — agents fall back to OpenAI if unset)
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key      # For Claude models
GOOGLE_API_KEY=your-google-api-key                # For Gemini models (or GEMINI_API_KEY)
XAI_API_KEY=xai-your-xai-key                     # For Grok models

LOG_LEVEL=INFO  # optional, defaults to "INFO"
```

**Frontend `.env.local`:**
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
```

> **Security Notes:**
> - Never commit `.env` files to version control
> - Never expose API keys in frontend code
> - All LLM/TTS/Whisper calls go through backend services

### 7.2 Backend Setup

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs at: **http://localhost:8000**

### 7.3 Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at: **http://localhost:3000**

---

## 8. Development Order

> **Do not skip steps.** Follow this order strictly:

1. LangGraph trial state machine
2. Text-only agent responses
3. Judge scoring logic
4. Whisper STT integration
5. TTS voice output
6. WebRTC audio streaming
7. Persona tuning
8. UI polish

**Skipping ahead causes compounding bugs.**

---

## 9. How to Work With Cursor

### Always Start Prompts With:

> *"Follow SPEC.md, ARCHITECTURE.md, AGENTS.md, AUDIO.md, and SCORING.md strictly."*

### Rules for Cursor-Generated Code

- Generate one file at a time
- No new folders unless specified
- Leave TODOs instead of guessing
- Never refactor unrelated files

**Cursor is an assistant, not an architect.**

---

## 10. Common Pitfalls

### Anti-Patterns

| Don't Do This |
|---------------|
| Letting agents speak freely without graph checks |
| Cleaning up Whisper transcripts |
| Combining judge and coach logic |
| Making witnesses "helpful" |
| Using text input instead of mic |
| Scoring based on intuition instead of rubric |

### Correct Patterns

| Do This Instead |
|-----------------|
| Explicit state validation |
| Verbatim transcripts |
| Persona-controlled voice output |
| Judges interrupting mid-speech |
| Clear separation of roles |

---

## 11. Testing Strategy

### Automated Test Suite

The project includes a built-in automated test suite accessible from the UI.

**How to run:**
1. Navigate to `http://localhost:3000/tests` or click the 🧪 **Tests** button in the header
2. Optionally filter by category (Infrastructure, Session, Trial Flow, etc.)
3. Click **Run All Tests** — results appear with pass/fail status and timing

**What the suite tests:**

| Category | Tests |
|----------|-------|
| **Infrastructure** | Health check endpoint |
| **Case Management** | Case library returns cases |
| **Session** | Session creation and initialisation, witness assignment |
| **Trial Flow** | Phase advancement (prep → opening), idempotent phase advance, opening statement generation, transcript recording |
| **Scoring** | Scoring endpoint responds correctly |
| **Audio** | TTS audio generation produces valid bytes |
| **Objections** | Objection detection for leading questions on direct, no false positives on cross |
| **Agent Config** | Per-agent LLM config propagation (model, temperature, max_tokens, system prompt), default values |
| **Multi-Provider** | Provider-to-model routing for all 4 providers, available models structure validation |
| **Persona** | Persona API returns team config with multi-provider models, per-agent LLM config save/load, global LLM config GET/PUT |

**API endpoints:**
- `POST /api/tests/run` — Run suite, optionally pass `categories` array in body
- `GET /api/tests/categories` — List available test categories

### What NOT to Test
- LLM creativity
- Exact wording of responses

> **We test structure and rules, not prose.**

---

## 12. Case Materials & Sources

### Official Case Sources

This platform uses **real mock trial cases** from official competition sources. We do NOT generate fictional case content.

| Source | URL | Case Types |
|--------|-----|------------|
| **AMTA** (American Mock Trial Association) | [collegemocktrial.org](https://www.collegemocktrial.org) | College-level criminal & civil cases |
| **MYLaw** (Maryland Youth & the Law) | [mylaw.org/mock-trial-cases-and-resources](https://www.mylaw.org/mock-trial-cases-and-resources) | High school civil & criminal (2007-present) |

### Copyright Notice

All case materials are **copyrighted** by their respective organizations:

> "All case materials are the intellectual property of the American Mock Trial Association." — AMTA

> "All case materials are copyrighted. Express permission is required for all re-print/distribution/use." — MYLaw

### How to Use Cases

1. **Browse** the Case Library in the app
2. **Download** the case PDF from the official source website
3. **Upload** the PDF to the platform (it will be parsed automatically)
4. **Practice** with AI-powered opposing counsel, witnesses, and judges

### AMTA Case PDF Parser

The platform includes a specialized parser for AMTA-format mock trial PDFs. When you upload an AMTA case PDF, the system automatically extracts:

| Extracted Section | Description |
|-------------------|-------------|
| Synopsis | Case summary and overview |
| Special Instructions | 24 AMTA competition rules and restrictions |
| Witness Calling Restrictions | Which side may call each witness |
| Indictment / Complaint | Formal charges with elements |
| Jury Instructions | Numbered legal instructions for the jury |
| Stipulations | Agreed-upon facts between parties |
| Motions in Limine | Pre-trial evidentiary rulings |
| Relevant Law | Applicable statutes and case law citations |
| Exhibit List | All exhibits with numbers and titles |
| Witness Affidavits | Full text of all witness statements, reports, and interrogations |

The parser works without any LLM API calls — it uses regex-based section detection and boundary analysis. If the PDF is not in AMTA format, it falls back to GPT-4 parsing.

### Case Materials Viewer

During preparation and trial, the Case Materials modal gives access to all extracted content across seven tabs:

| Tab | Contents |
|-----|----------|
| **Overview** | Parties (Prosecution v. Defendant), charge, indictment detail, case synopsis, witness calling restrictions summary, quick stats |
| **Case Files** | Uploaded PDFs, images, and documents organised by section |
| **Witnesses** | Plaintiff, defense, and either-side witness cards with expandable affidavits |
| **Exhibits** | Numbered exhibit list with descriptions and inline content |
| **Facts** | Background facts, evidence, stipulations grouped by category |
| **Rules** | Special Instructions (numbered, from the case packet), witness calling restrictions (prosecution-only / defense-only / either-side) |
| **Legal** | Jury instructions, relevant statutes, relevant case law citations, motions in limine rulings |

### AMTA Trial Rules Enforced

The trial state machine and AI agents enforce AMTA-specific rules extracted from the case:

| Rule | Implementation |
|------|----------------|
| **Time Limits** | 25 minutes per side for direct, 25 for cross |
| **Witness Restrictions** | Captains' meeting calling restrictions resolved at agent init via `_resolve_called_by()` |
| **Charge Requirements** | Prosecution must pursue specified charge(s) |
| **Evidence Rules** | Midlands Rules of Evidence (closed-universe) |
| **No Guilty Portrayals** | Witnesses cannot portray themselves as the perpetrator |
| **Motions in Limine** | Rulings injected into attorney agent context — excluded evidence cannot be argued |
| **Special Instructions** | Full set included as binding rules in attorney AI prompts |
| **Jury Instruction Elements** | Fed to attorneys so openings/closings address required legal elements |

### Section-Based Upload

Cases are organized into sections for proper parsing:

| Section | Description |
|---------|-------------|
| Case Summary | Overview, parties, key issues |
| Special Instructions | AMTA participant rules and restrictions |
| Indictment / Complaint | Formal charges or complaint |
| Plaintiff/Prosecution Witnesses | Witness affidavits for one side |
| Defense Witnesses | Witness affidavits for the other side |
| Either-Side Witnesses | Witnesses callable by either side |
| Exhibits | Documents, photos, evidence |
| Stipulations | Agreed-upon facts |
| Jury Instructions | Legal standards and laws |
| Relevant Law | Statutes and case law |
| Motions in Limine | Pre-trial rulings |
| Rules & Procedures | Competition rules |

### File Storage (Supabase Storage)

All uploaded case materials are stored in **Supabase Storage** with the following directory structure:

```
case-materials/               # Storage bucket
└── cases/
    └── {case_id}/
        ├── summary/              # Case summary PDFs
        ├── special_instructions/ # AMTA rules
        ├── indictment/           # Formal charges
        ├── witnesses_plaintiff/  # Plaintiff witness affidavits
        ├── witnesses_defense/    # Defense witness affidavits
        ├── witnesses_either/     # Either-side witnesses
        ├── exhibits/             # Evidence documents/images
        ├── stipulations/         # Agreed facts
        ├── jury_instructions/    # Legal standards
        ├── relevant_law/         # Statutes and case law
        ├── motions_in_limine/    # Pre-trial rulings
        └── rules/                # Competition rules
```

**Supported file types:** PDF, TXT, DOC, DOCX, PNG, JPG, GIF, JSON

**Storage API Endpoints:**

| Endpoint | Description |
|----------|-------------|
| `GET /api/case/{id}/storage` | Get storage summary for a case |
| `GET /api/case/{id}/storage/files` | List all files for a case |
| `GET /api/case/{id}/storage/files/{section}/{filename}/url` | Get signed download URL |
| `DELETE /api/case/{id}/storage/files/{section}/{filename}` | Delete specific file |
| `DELETE /api/case/{id}/storage` | Delete all files for a case |

---

## 13. Legal & Ethical Notes

- This is an **educational simulation**
- Not affiliated with AMTA or MYLaw
- No legal advice is provided
- Case content must be downloaded from official sources by users
- Platform does not redistribute copyrighted materials

---

## 14. When You're Unsure

1. Check `/specs`
2. Search `trial_graph.py`
3. Ask before inventing

> **Silence is better than hallucination.**

---

## 15. Final Orientation

If built correctly, this system:

| Effect | Intentional? |
|--------|--------------|
| Feels stressful | Yes |
| Sounds real | Yes |
| Punishes mistakes | Yes |

**That's how mock trial works.**

---

## 16. Agent LLM Communication

Per `ARCHITECTURE.md` and `AGENTS.md`, agents communicate with LLMs through backend services:

1. Agents do **NOT** have API keys
2. Agents call backend service functions for GPT, TTS, and Whisper
3. API keys are injected by backend services, never exposed to agents

### Multi-Provider Architecture

The system supports four LLM providers, routed automatically by model name:

| Provider | Models | API Key Env Var |
|----------|--------|-----------------|
| **OpenAI** | GPT-4.1, GPT-4.1 Mini/Nano, GPT-4o, GPT-4o Mini | `OPENAI_API_KEY` |
| **Anthropic** | Claude Sonnet 4, Claude 3.5 Sonnet/Haiku | `ANTHROPIC_API_KEY` |
| **Google** | Gemini 2.5 Pro/Flash, Gemini 2.0 Flash | `GOOGLE_API_KEY` or `GEMINI_API_KEY` |
| **xAI** | Grok 3, Grok 3 Mini | `XAI_API_KEY` |

If a provider's API key is not set, calls to its models fall back to OpenAI transparently.

The provider router (`backend/app/services/llm_providers.py`) maps each model ID to its provider and handles API format differences (OpenAI chat format, Anthropic Messages API, Google GenAI, xAI OpenAI-compatible).

### Per-Agent LLM Configuration

Every AI agent (attorney, witness, judge) can be individually configured with:

| Field | Description | Default |
|-------|-------------|---------|
| `llm_model` | Model to use for this specific agent | Global default (GPT-4.1) |
| `llm_temperature` | Creativity/randomness for this agent | Varies by method (0.2–0.8) |
| `llm_max_tokens` | Max response length for this agent | Varies by method (100–1200) |
| `custom_system_prompt` | Additional instructions prepended to built-in prompt | None |

**Configuration hierarchy:**
```
Per-agent override → Global session override → Method-specific default
```

**Example:** You can set the prosecution's opening attorney to use Claude Sonnet 4 at temperature 0.9 for creative openings, while the defense cross-examination attorney uses GPT-4.1 at temperature 0.3 for precise questions, and the judge uses Gemini 2.5 Pro.

### UI Configuration

In the **Customize AI Personas** panel, expand any agent card and click **Agent LLM Config** to:
- Select a model from any supported provider (grouped by provider)
- Adjust temperature and max tokens with sliders
- Write a custom system prompt (prepended to the agent's built-in prompt)
- View the agent's full built-in system prompt via "View Built-in System Prompt"
- Reset all overrides back to defaults

Changes are **hot-patched** to live agents immediately — no session restart needed.

### Example Usage

```python
from services.llm_service import call_llm, PersonaContext

persona = PersonaContext(role="attorney", name="Smith", style="aggressive")
response = call_llm(
    system_prompt="You are a prosecutor...",
    user_prompt="Cross-examine this witness about...",
    persona=persona,
    model="claude-sonnet-4-20250514",  # per-agent model override
    temperature=0.4,
)
```

### Backend Service Handles:
- Multi-provider routing based on model name
- API key injection from environment variables
- Persona conditioning of prompts
- Per-agent config override resolution
- Graceful fallback to OpenAI if provider unavailable

---

## 17. 6-Layer Memory Architecture

AI agents use a layered memory system for context-aware responses:

| Layer | Purpose | Persistence |
|-------|---------|-------------|
| **Immutable Case Memory** | Case facts, affidavits, exhibits | Session lifetime |
| **Courtroom Event Memory** | Phase transitions, witness calls, rulings | Session lifetime |
| **Character Memory** | Agent personas, styles, skill levels | Session lifetime |
| **Short-Term Conversation** | Recent Q&A pairs for context | Per-witness |
| **Strategic Memory** | Case theory, examination strategy | Session lifetime |
| **Credibility & Scoring** | Witness credibility, attorney performance | Session lifetime |

**Vector Search (Pinecone):** Case facts, witness affidavits, and live testimony are embedded and indexed. Agents retrieve relevant passages for question generation, cross-examination, and closing arguments.

---

## 18. Objection System

AI attorneys automatically object during examination based on:

1. **Deterministic pattern detection** — Leading questions on direct, compound questions, argumentative tone, asked-and-answered
2. **LLM analysis** — GPT-4.1 evaluates questions for hearsay, speculation, relevance, beyond scope, narrative, and other objection types
3. **Persona-driven gating** — Objection frequency, skill level, and risk tolerance control how often an attorney objects

**Objection flow:**
```
Attorney question → Opposing attorney evaluates → Objection raised (if warranted)
→ Judge rules (sustained/overruled) → Sustained: question struck, next Q
                                    → Overruled: witness answers
```

**UI indicators:**
- Objection counter in the Scores & Stats panel (prosecution/defense/sustained/overruled)
- Objection entries appear inline in the transcript
- Objection panel in the right column during examination phases

---

## 19. Scoring & Live Stats

- **Live scoring** updates after each witness examination and after opening/closing arguments
- Opening attorney scores are preserved across witness examinations (merged, not replaced)
- Scores are displayed in the **Scores & Stats** panel (always visible, top of right column)
- Each score bar clearly labels **PROS** (prosecution) or **DEF** (defense)
- Witness scores show which side called them
- **Role-specific categories**: Opening attorneys, direct/cross attorneys, closing attorneys, and witnesses each have 5 tailored scoring categories (see Section 24)
- Click **View Detailed Scores** to navigate to the full score breakdown page at `/scores/{sessionId}`
- **Email Report**: From the Score Details page, click "Email Report" to send transcript and scores to others via email

---

## 20. TTS Audio Pipeline

### Live Trial Audio

Audio playback during live trials uses a cascading fallback chain for reliability:

```
1. Preloaded blob (prefetched during Q&A generation)
   ↓ if failed
2. Backend TTS fetch (OpenAI TTS with retries + text-based cache)
   ↓ if failed
3. Browser speech synthesis (with Chrome queue-clearing workaround)
   ↓ if failed
4. Reading delay (proportional to text length)
```

**Reliability measures:**
- Backend TTS caches audio by text content hash — identical text never regenerates
- Backend retries TTS generation up to 2 times on failure
- Frontend maintains an `AudioContext` to prevent browser autoplay revocation
- Safety timers resolve playback promises if `onended` events fail to fire
- Chrome `speechSynthesis.cancel()` before each utterance prevents queue hang

### Persistent TTS Audio Storage

All TTS audio generated during live trials is permanently stored in **Supabase Storage** (`tts-audio-cache` bucket):

- Audio files are keyed by a **SHA-256 hash** of (text + role + speaker), ensuring deterministic, unique storage
- Audio is generated **once** during the live trial and never regenerated for playback
- Stored as MP3 files, served via `GET /api/public/tts/audio/{cache_key}` (no auth required)
- The transcript API (`GET /api/trial/transcripts/{session_id}`) returns an `audio_keys` dictionary mapping each transcript entry to its cached audio key
- A backfill endpoint (`POST /api/admin/backfill-audio`) can generate audio for historical transcripts that predate the caching system; runs asynchronously via `BackgroundTasks` to prevent server blocking
- Backfill status can be monitored via `GET /api/admin/backfill-status`

---

## 21. Agent Prep Material Caching

AI-generated preparation materials (case briefs, witness outlines, opening statements, etc.) are cached to avoid redundant LLM calls:

| Storage | Purpose |
|---------|---------|
| **Supabase `agent_prep_materials` table** | Persistent database cache |
| **Local `.agent_prep_cache/` directory** | Fast file-system cache |

On session creation, the system checks both caches before generating new materials. Users can force regeneration if needed.

---

## 22. Authentication

The platform uses **Supabase Auth** for user authentication with the following login methods:

- Email/password (sign up + sign in)
- Google OAuth
- LinkedIn (OpenID Connect)
- Facebook OAuth
- Discord OAuth

### Architecture

- Frontend uses `@supabase/ssr` for Next.js-compatible auth
- Next.js middleware (`middleware.ts`) protects all routes — unauthenticated users are redirected to `/login`
- Backend validates JWT tokens from the `Authorization` header via `get_current_user_id()` dependency
- User ID from JWT is used to scope transcript history and other user-specific data

### Key Files

| File | Purpose |
|------|---------|
| `frontend/app/login/page.tsx` | Login/signup page with email + social buttons |
| `frontend/app/auth/callback/route.ts` | OAuth redirect callback handler |
| `frontend/lib/supabase/client.ts` | Browser-side Supabase client |
| `frontend/lib/supabase/server.ts` | Server-side Supabase client |
| `frontend/lib/supabase/middleware.ts` | Session refresh helper for middleware |
| `frontend/middleware.ts` | Route protection middleware |
| `backend/app/api/auth.py` | Backend JWT validation |

### Frontend Environment Variables

```bash
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your-supabase-anon-key
```

### OAuth Provider Setup

Each OAuth provider must be configured in the **Supabase Dashboard** (Authentication > Providers) with the redirect URI: `https://YOUR_SUPABASE_REF.supabase.co/auth/v1/callback`

| Provider | Developer Console |
|----------|------------------|
| Google | [Google Cloud Console](https://console.cloud.google.com/) > APIs & Services > Credentials |
| LinkedIn | [LinkedIn Developer Portal](https://www.linkedin.com/developers/) |
| Facebook | [Facebook Developers](https://developers.facebook.com/) |
| Discord | [Discord Developer Portal](https://discord.com/developers/applications) |

---

## 23. Transcript History

Trial transcripts are progressively saved to **Supabase Storage** during the trial and can be reviewed later.

### How It Works

- Transcripts are saved automatically after opening statements, each witness examination, and closing arguments
- Stored as JSON files in Supabase Storage: `transcripts/{user_id}/{case_id}/{session_id}.json`
- Metadata (case name, date, session ID, phases completed) is tracked in a `trial_transcript_history` database table

### Viewing History

- Navigate to `/history` from the app header
- Transcripts are grouped by case name
- Each entry shows: date/time, role played, entry count, phases completed
- Click to expand and read the full transcript

### API Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/trial/{session_id}/save-transcript` | Manually save current transcript |
| `GET /api/trial/transcripts/history` | List all transcripts for the current user |
| `GET /api/trial/transcripts/{session_id}` | Get full transcript data (includes `audio_keys` map) |
| `GET /api/trial/transcripts/public` | List all completed trials (public, no auth) |

---

## 24. Score Detail Page

Scoring details are displayed in two locations:

1. **`/scores/{sessionId}`** — Full score breakdown page (accessible during/after live trial)
2. **`/trials/{sessionId}`** (Scores tab) — Unified trial detail page showing scores alongside transcript and audio (used by both Recorded Trials and dashboard Recent Trials)

### What It Shows

1. **Verdict Banner** — Which side won, with average score comparison
2. **Score Comparison Bar** — Visual prosecution vs defense score split
3. **Individual Performance** — Per-participant expandable cards (Prosecution vs Defense) with:
   - Category scores with visual score bars and judge justification
   - Overall judge comments
4. **Scoring Categories Reference** — Descriptions of what each category measures

### Role-Specific Scoring

Each participant is scored only on categories relevant to their role:

| Role | Categories |
|------|-----------|
| **Opening Attorney** | Opening Clarity, Case Theory Consistency, Courtroom Presence, Persuasiveness, Factual Foundation |
| **Direct/Cross Attorney** | Direct Examination, Cross-Examination Control, Objection Accuracy, Responsiveness, Courtroom Presence |
| **Closing Attorney** | Closing Persuasiveness, Evidence Integration, Rebuttal Effectiveness, Case Theory Consistency, Courtroom Presence |
| **Witness** | Responsiveness, Courtroom Presence, Testimony Consistency, Credibility, Composure Under Pressure |

---

## 25. Either-Side Witness Assignment

Witnesses marked as "either" in the case materials can be called by either side. The system handles them as follows:

### Automatic Random Assignment

When a session is initialized, "either" witnesses are randomly divided between prosecution and defense (roughly evenly). This determines:
- Which side calls the witness during the trial
- Whether direct or cross examination is "friendly"
- The strategic context in the witness's prep materials

### Reassignment During Preparation

In the Preparation Panel (both Witnesses and Agent Prep tabs), "either" witnesses display a toggle button allowing reassignment between Prosecution and Defense. Reassignment triggers:
- Agent recreation with the new side context
- Regeneration of witness outlines and prep materials aligned to the new side
- Update of the prosecution/defense witness lists

### Witness Calling Restrictions

Some case materials specify hard restrictions (prosecution-only, defense-only). These are enforced:
- During trial, the backend validates that only the allowed side can call a restricted witness
- Hard restrictions override random assignments for "either" witnesses
- The trial UI only shows callable witnesses for the current case-in-chief

---

## 26. Audio Toggle & Trial Flow Controls

### Audio Toggle

Users can enable or disable TTS audio at any point:
- **Before trial**: A toggle switch appears above the "Begin Trial" button in the prep phase
- **During trial**: A speaker icon button in the courtroom header toggles audio on/off
- When audio is disabled, all TTS generation and playback is skipped — the trial continues on transcript only
- Audio can be re-enabled at any time; subsequent speech will use TTS

### Trial Flow Controls

During an active trial, the courtroom header displays control buttons:

| Control | Behavior |
|---------|----------|
| **Pause** | Suspends trial flow after the current speech/action completes. The trial freezes in place. |
| **Resume** | Continues the trial from where it was paused. |
| **Stop** | Permanently halts the trial. The session transitions to scoring. Cannot be undone. |

These controls use cooperative checking — the trial flow checks for pause/stop between examination phases, witness calls, and Q&A pairs.

---

## 27. Email Trial Reports

The Score Details page (`/scores/{sessionId}`) includes an "Email Report" button that sends a formatted HTML email containing:

- **Scores & Performance**: All participant scores with category breakdowns and judge justifications
- **Trial Transcript**: Full transcript with speaker labels, phase separators, and color-coded roles

### Configuration

Add SMTP settings to `backend/.env`:

```bash
SMTP_HOST=smtp.gmail.com       # SMTP server hostname
SMTP_PORT=587                  # SMTP port (587 for TLS, 465 for SSL)
SMTP_USER=your-email@gmail.com # SMTP login username
SMTP_PASSWORD=your-app-password # SMTP password or app password
SMTP_FROM=your-email@gmail.com # Sender address (defaults to SMTP_USER)
```

For Gmail, use an [App Password](https://myaccount.google.com/apppasswords) instead of your account password.

### API Endpoint

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/trial/{sessionId}/email-report` | POST | Send transcript and/or scores to specified email addresses |

**Request body:**
```json
{
  "recipients": ["user@example.com", "coach@school.edu"],
  "include_transcript": true,
  "include_scores": true,
  "sender_name": "John Doe"
}
```

---

## 28. Recorded Trials & Public Trial Pages

### Public Trial Listing

The `/trials` page is publicly accessible (no login required) and displays all completed trial simulations. Each trial card shows the case name, date, role played, and exchange count.

Clicking any trial navigates to `/trials/{sessionId}` — the **unified trial detail page**.

### Unified Trial Detail Page (`/trials/{sessionId}`)

Both **Recorded Trials** (public, from `/trials`) and **Recent Trials** (authenticated, from the dashboard) use the **same detail page**. The underlying data may differ depending on the trial:

| Data Source | Availability |
|-------------|-------------|
| Transcript | Available for trials with stored transcripts in Supabase Storage |
| Audio playback | Available for trials with pre-generated TTS audio in `tts-audio-cache` |
| Scores | Available for trials with scoring data in `live_scores` DB table |

**Graceful data handling:**
- If a trial has both transcript and scores, both tabs are available
- If a trial has scores but no transcript (e.g., seeded demo data), the page auto-switches to the Scores tab
- If neither is available, a "No data available" message is shown
- Audio playback controls (Play Full Trial, Pause, Resume, Stop) appear only when cached audio exists

**Tabbed UI:**
- **Transcript tab** — Full trial transcript with inline audio play buttons per entry, plus "Play Full Trial" with pause/resume/stop controls
- **Scores tab** — Verdict banner, score comparison bar, expandable participant cards with per-category scores, justifications, and judge comments

### Public Routes

The middleware allows all `/trials/*` routes without authentication. The detail page uses plain `fetch` (not authenticated `apiFetch`) so it works for both logged-in and anonymous visitors.

### Dashboard Integration

From the dashboard, clicking any "Recent Trial" or "Your Performance" entry navigates to `/trials/{sessionId}` — the same page that public recorded trials use.

### Backend Endpoints for Historical Trials

Scoring endpoints (`/api/scoring/{session_id}/full-report`, `/api/scoring/{session_id}/verdict`) work for both active in-memory sessions and historical completed trials:
- If no live session exists (e.g., after server restart), scores are loaded from the `live_scores` database table
- Case metadata (name, ID, phase) falls back to `transcript_storage` if the session object is unavailable
- A 404 is only returned if absolutely no scoring data exists

---

## 29. Deployment

The application is deployed as a split architecture:

| Component | Platform | URL |
|-----------|----------|-----|
| Frontend (Next.js) | Vercel | `https://mock-trial-ai.vercel.app` |
| Backend (FastAPI) | Render | `https://mock-trial-ai.onrender.com` |
| Database & Auth | Supabase | Managed service |

### Backend (Render)

- Runtime: Python 3.11
- Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- CORS origins configured via `CORS_ORIGINS` environment variable
- Blueprint file: `backend/render.yaml`

### Frontend (Vercel)

- Framework: Next.js 14 (auto-detected)
- Root directory: `frontend`
- Output: Standalone (`next.config.mjs`)
- Environment variables: `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`

### Supabase Configuration

For production, update in the Supabase Dashboard:
- **Site URL**: Your Vercel domain
- **Redirect URLs**: `https://your-domain.vercel.app/auth/callback`

### GitHub Repository

Source code: [github.com/jprasanna-ai/mock-trial-ai](https://github.com/jprasanna-ai/mock-trial-ai)
