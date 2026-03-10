# Verification Checklist

## Trial Graph
- [x] All states present (PREP, OPENING, DIRECT, CROSS, REDIRECT, RECROSS, CLOSING, SCORING)
- [x] Single speaker enforcement (validate_speaker function)
- [x] Objections allowed only in testimony (TESTIMONY_STATES check in can_object)
- [x] Judge interrupt hooks (judge_interrupt, release_judge_interrupt functions)
- [x] Hooks for agents (can_speak, validate_speaker, can_object)

## Agents
- [x] Roles obey trial graph (all agents use trial_graph validation)
- [x] Persona parameters used (AttorneyPersona, WitnessPersona, JudgePersona, CoachPersona)
- [x] Witness cannot invent facts (affidavit constraint in WitnessAgent)
- [x] Judge scoring implemented (ScoringCategory enum, score_participant method)
- [x] Coach post-trial only (SCORING phase restriction in coach.py)

## Audio
- [x] Whisper streaming (WhisperService in services/whisper.py)
- [x] TTS persona voices (TTSService in services/tts.py)
- [x] Judge interrupts correctly (judge_interrupt_active state, priority handling)

## Scoring
- [x] Numeric + written feedback (ScoringCategory 1-10 + justification)
- [x] Rubric compliance (7 scoring categories per SCORING.md)
- [x] Judges independent (3-judge panel, separate scoring in JudgePanel)

## Preparation Phase
- [x] Opening statements pre-generated during preparation (AttorneyAgent.generate_opening)
- [x] Opening statements stored in DB (opening_plaintiff, opening_defense in prep_materials)
- [x] Opening statements viewable in PreparationPanel "Openings" tab
- [x] Regenerate buttons for individual or both openings
- [x] "Begin Trial" button gated on opening statement readiness
- [x] Courtroom fetches cached openings (skips LLM, TTS-only ~3-5s)
- [x] Fallback to real-time generation if cache is empty

## Multi-Provider LLM
- [x] Provider abstraction exists (llm_providers.py with chat_completion / chat_completion_async)
- [x] OpenAI routing (GPT-4.1, GPT-4o, etc.)
- [x] Anthropic routing (Claude Sonnet 4, Claude 3.5 Sonnet/Haiku via Messages API)
- [x] Google routing (Gemini 2.5 Pro/Flash via GenAI SDK)
- [x] xAI routing (Grok 3/Mini via OpenAI-compatible API)
- [x] Graceful fallback to OpenAI when provider API key missing
- [x] LLMService routes to providers based on model name
- [x] Available models list includes all 4 providers (13+ models)

## Per-Agent Configuration
- [x] AttorneyPersona has llm_model, llm_temperature, llm_max_tokens, custom_system_prompt
- [x] WitnessPersona has llm_model, llm_temperature, llm_max_tokens, custom_system_prompt
- [x] JudgePersona has llm_model, llm_temperature, llm_max_tokens, custom_system_prompt
- [x] Agent _generate() applies per-agent overrides before defaults
- [x] Custom system prompt prepended to built-in system prompt
- [x] Persona API accepts and returns per-agent LLM config fields
- [x] Hot-patching: saving persona config updates live agent immediately
- [x] Factory functions (create_attorney_agent, etc.) pass LLM config via **kwargs
- [x] Session initialization pipes per-agent config from persona data to agent creation

## Per-Agent Config UI
- [x] AgentLLMConfigSection component in PersonaCustomizer
- [x] Model dropdown grouped by provider (OpenAI, Anthropic, Google, xAI)
- [x] Temperature and max_tokens sliders per agent
- [x] Custom system prompt textarea per agent
- [x] "View Built-in System Prompt" shows agent's default prompt
- [x] "Reset to Defaults" clears all per-agent overrides
- [x] "Custom" badge shown when agent has overrides

## Frontend
- [x] Components exist (MicInput, AudioPlayer, TranscriptPanel, ObjectionPanel, etc.)
- [x] Audio streaming works (WebRTC signaling, Whisper integration)
- [x] UI reflects trial state (phase indicators, speaker permissions, courtroom page)
- [x] Collapsible Scores & Stats panel with side grouping
- [x] Collapsible phase progress bar

---

## Authentication
- [x] Supabase Auth integration (email + OAuth)
- [x] Next.js middleware route protection
- [x] Login page with email and 4 social providers
- [x] OAuth callback handler
- [x] Backend JWT validation
- [x] User ID propagation to storage/transcript APIs

## Transcript History
- [x] Progressive transcript saving to Supabase Storage
- [x] Transcript metadata table
- [x] History page (`/history`) grouped by case name
- [x] Transcript viewer with expandable entries

## Score Detail Page
- [x] Category-by-category breakdown with per-member scores
- [x] Individual performance cards with strengths/improvements
- [x] Judge comments and justifications
- [x] Role-specific scoring categories (5 per role)

## Persistent TTS Audio
- [x] TTS audio stored in Supabase Storage (`tts-audio-cache` bucket)
- [x] SHA-256 hash key (text + role + speaker) for deterministic caching
- [x] Audio generated once during live trial, never regenerated for playback
- [x] Public serving via `GET /api/public/tts/audio/{cache_key}` (no auth)
- [x] Transcript API returns `audio_keys` map linking entries to cached audio
- [x] Backfill endpoint (`POST /api/admin/backfill-audio`) with async `BackgroundTasks`
- [x] Backfill status monitoring via `GET /api/admin/backfill-status`

## Recorded Trials & Public Pages
- [x] `/trials` public listing of completed trials (no auth required)
- [x] `/trials/{sessionId}` unified detail page for both public and dashboard trials
- [x] Middleware allows all `/trials/*` routes without authentication
- [x] Detail page uses plain `fetch` (not `apiFetch`) for public access
- [x] Tabbed UI: Transcript tab with audio playback, Scores tab with detailed breakdown
- [x] Audio controls: Play Full Trial, Pause, Resume, Stop, per-entry play buttons
- [x] Graceful handling: auto-switch to Scores tab when transcript unavailable
- [x] "No data available" fallback when neither transcript nor scores exist
- [x] Dashboard "Recent Trials" and "Your Performance" route to `/trials/{sessionId}`
- [x] ScoresPanel with verdict banner, comparison bar, expandable participant cards
- [x] Per-category scores with visual bars, justifications, and judge comments

## Historical Score Access
- [x] `/api/scoring/{session_id}/full-report` works without live session (DB fallback)
- [x] `/api/scoring/{session_id}/verdict` computes from DB scores if no live session
- [x] Case metadata (name, ID, phase) resolved from `transcript_storage` as fallback
- [x] 404 only returned when absolutely no scoring data exists

## Deployment
- [x] Vercel deployment (frontend, standalone output)
- [x] Render deployment (backend, render.yaml blueprint)
- [x] Dynamic CORS via `CORS_ORIGINS` env var
- [x] GitHub repository at `jprasanna-ai/mock-trial-ai`
- [x] Supabase Auth redirect URLs configured for production
