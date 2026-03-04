# Audio & Voice Specification

## 1. Audio Is Primary Interface

- All advocacy is spoken
- Text exists only as transcript
- Silence, pauses, interruptions matter

---

## 2. Speech-to-Text (Whisper)

Rules:
- Streaming transcription only
- Verbatim capture
- Preserve filler words and pauses
- No semantic cleanup

---

## 3. Text-to-Speech

Rules:
- One persistent voice per agent per session
- Persona controls:
  - Pace
  - Authority
  - Nervousness
  - Interruptiveness

Judge voice ALWAYS has priority.

---

## 4. Opening Sequence Audio Pipeline

Opening statements use a pre-generation + TTS-only pipeline to minimize courtroom delays:

1. Opening statement **text** is pre-generated during the preparation phase and cached
2. When the trial starts, `runOpeningSequence` fetches the cached text (no LLM call)
3. TTS audio is pre-fetched in parallel with the clerk announcement (~3-5s)
4. The attorney begins speaking within 1-2 seconds of the clerk finishing
5. While the prosecution speaks, the defense TTS audio is pre-fetched in parallel
6. Fallback: if cached text is unavailable, `triggerAITurn` generates text in real-time

---

## 5. Interrupt Handling

- Judges may interrupt any speaker
- Objections may interrupt testimony
- Interrupted audio must stop immediately

---

## 5. Accessibility

- Captions always enabled
- Transcript synced with audio timestamps

## Audio Processing Pipeline

- Whisper (STT) and TTS calls are handled **by backend services**.
- Agents request TTS via backend with persona parameters.
- Frontend streams mic audio → backend → Whisper → text → agent → TTS → audio stream.
- No keys are exposed in frontend or agent code.
