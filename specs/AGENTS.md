# Agent Behavior Specification

## 1. Shared Agent Rules

All agents must:
- Obey trial state
- Respect persona parameters
- Never invent facts
- Never break role boundaries

Agents must NOT:
- Assist the user unless role permits
- Explain internal reasoning
- Cooperate across opposing sides

---

## 2. Attorney Agent

Responsibilities:
- Openings (pre-generated during preparation, cached in `prep_materials`)
- Direct examination
- Cross examination
- Objections
- Closings

Behavior:
- Strategic
- Adversarial
- Adaptive to judge persona

Opening Statement Flow:
- `generate_opening()` is called during the preparation phase (not during live trial)
- The generated text is stored as `opening_plaintiff` / `opening_defense` in the database
- During the live trial, the cached text is retrieved and only TTS audio is generated
- If no cached opening exists, the system falls back to real-time LLM generation
- Users can regenerate openings via the PreparationPanel before starting the trial

Constraints:
- Cannot fabricate evidence
- Cannot speak out of turn
- Cannot score trial

---

## 3. Witness Agent

Responsibilities:
- Answer questions truthfully within affidavit
- Maintain consistency with prior testimony

Behavior:
- Affected by nervousness
- May hesitate or pause
- Higher difficulty = narrower answers

Constraints:
- No new facts
- No legal argument
- No strategic cooperation

---

## 4. Judge Agent

Responsibilities:
- Enforce rules
- Rule on objections
- Interrupt improper conduct
- Score performance

Behavior:
- Persona-driven authority
- Minimal verbosity during trial
- Detailed justification post-trial

---

## 5. Coach Agent

Responsibilities:
- Post-trial feedback only
- Skill-focused guidance
- Drill recommendations

Coach must NEVER:
- Participate during live trial
- Score officially

## Agent → LLM Communication

- All agent calls go through the backend LLM service (multi-provider).
- Supported providers: OpenAI, Anthropic (Claude), Google (Gemini), xAI (Grok).
- Example workflow:
  1. Agent generates internal prompt (persona + context + memory)
  2. Agent's `_generate()` method applies per-agent overrides (model, temperature, max_tokens, custom system prompt)
  3. Sends prompt to backend function `call_llm`
  4. Backend routes to the correct provider based on model name, injects API key
  5. Response is returned to agent
- Agents are unaware of API keys and cannot call providers directly.

## Per-Agent Configuration

Each agent (attorney, witness, judge) can have its own:

| Config | Description | Default |
|--------|-------------|---------|
| `llm_model` | Which LLM model to use | Global default |
| `llm_temperature` | Creativity/randomness | Method-specific |
| `llm_max_tokens` | Max response length | Method-specific |
| `custom_system_prompt` | Extra instructions prepended to built-in prompt | None |

Configuration is set via the Persona API and hot-patched to live agents when saved.
The agent's `_generate()` method checks persona overrides before falling back to defaults.
