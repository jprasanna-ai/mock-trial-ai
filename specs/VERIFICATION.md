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
