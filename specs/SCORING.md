# Scoring & Evaluation Specification

## 1. Judge Panels

- Exactly 3 JudgeAgents
- Independent scoring
- No shared memory between judges

---

## 2. Role-Specific Scoring Categories

Each participant is scored only on categories relevant to their role. Each category is scored 1-10.

### Opening Attorney Categories
- **Opening Clarity** — How clearly the advocate previewed their case theory
- **Case Theory Consistency** — Was the case theory well established
- **Courtroom Presence** — Professional demeanor, confidence, poise
- **Persuasiveness** — How compelling and attention-capturing the opening was
- **Factual Foundation** — Did the opening properly preview the facts to be proven

### Direct/Cross Examination Attorney Categories
- **Direct Examination Effectiveness** — Quality of direct questions, non-leading, logical story building
- **Cross-Examination Control** — Control of witness, leading questions, advancing case theory
- **Objection Accuracy** — Appropriate objections on valid grounds, no frivolous objections
- **Responsiveness** — Adapting to testimony, rulings, and court instructions
- **Courtroom Presence** — Professional demeanor, confidence, poise

### Closing Attorney Categories
- **Closing Persuasiveness** — Strength of the closing argument, appeal to logic and emotion
- **Evidence Integration** — How well evidence and testimony were woven into the closing
- **Rebuttal Effectiveness** — How effectively the opponent's arguments were addressed
- **Case Theory Consistency** — Did closing tie back to the opening and examination themes
- **Courtroom Presence** — Professional demeanor, confidence, poise

### Witness Categories
- **Responsiveness** — Answered questions directly and on-point
- **Courtroom Presence** — Professional demeanor, confidence, poise
- **Testimony Consistency** — Internal consistency with prior statements and established facts
- **Credibility** — How believable, honest, and trustworthy the witness appeared
- **Composure Under Pressure** — Handling challenging cross-examination without getting flustered

---

## 3. Audio-Influenced Scoring

Judges must consider:
- Confidence
- Clarity
- Control under interruption
- Professional tone

---

## 4. Ballots

Each judge produces:
- Numeric scores (1-10) per applicable category
- Written justification per category
- Overall comments with strengths and improvement suggestions

Final score per participant:
Average across all scored categories for that role.

---

## 5. Live Scoring

- Live scoring runs after each witness examination and after opening/closing arguments
- Uses a single judge for speed (full 3-judge panel for final scoring)
- Results cached in memory and exposed via `/api/scoring/{session_id}/live-scores`
- Frontend polls for updates and displays in the Scores & Stats panel
- **Score merging**: When witness examination scores are generated, they are merged with existing scores (opening, closing) rather than replacing them, preserving all attorney sub-role scores throughout the trial
- **Transcript sync**: Opening and closing statement transcript entries are awaited before live scoring to prevent race conditions

---

## 6. Score Detail Page

The `/scores/{sessionId}` page provides:
- **Category-by-category breakdown** with every team member's score and justification per category
- **Individual performance cards** per participant with strengths (7+) and improvement areas (<7)
- **Overall judge comments** per participant
- **Email Report** button to send scores and transcript via email
- Full report available via `GET /api/scoring/{session_id}/full-report`

---

## 7. Score Persistence

- In-memory cache for fast live score access
- Supabase (PostgreSQL) for persistent storage via `ScoringRepository`
- Stored data: session ID, participant ID, role, ballots, final scores, overall average

### Historical Score Access

Scoring endpoints work for both active in-memory sessions and historical completed trials:

| Endpoint | Historical Behavior |
|----------|-------------------|
| `GET /api/scoring/{session_id}/live-scores` | Loads from `live_scores` DB table if not in memory |
| `GET /api/scoring/{session_id}/full-report` | Falls back to DB scores + `transcript_storage` for case metadata |
| `GET /api/scoring/{session_id}/verdict` | Computes verdict from DB scores if no live session exists |

If no live session object is available (e.g., after server restart):
- Scores are loaded from the `live_scores` database table
- Case name, case ID, and phase are resolved from `transcript_storage` metadata
- The verdict is computed from stored scores without requiring an active session
- A 404 is only returned if absolutely no scoring data exists for the session

---

## 8. Anti-Hallucination Rule

Judges may only score what occurred in transcript + audio timeline.
Do not invent or assume things that did not happen.
If a category cannot be assessed from evidence, score 5 and explain why.
