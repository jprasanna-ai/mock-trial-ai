# AI Mock Trial Game — Full Product Specification

## 1. Product Purpose

This system simulates a full mock trial experience using autonomous AI agents.
One role is controlled by a human user via microphone.
All other roles are played by AI agents operating under strict courtroom rules.

The system replicates:
- Mock trial preparation
- Live trial advocacy
- Judicial rulings
- AMTA-style scoring
- Post-trial coaching

This is a simulation platform for education and practice.
It does NOT provide legal advice.

---

## 2. Core Principles

- Audio-first interaction
- Deterministic trial flow
- Adversarial agents (not cooperative chatbots)
- Persona-driven behavior
- Rule-enforced courtroom realism
- Replayability and scoring consistency

---

## 3. Supported Roles

- Attorney (Plaintiff / Defense)
- Witness
- Judge
- Coach (post-trial only)

Only ONE role may be human-controlled per session.

---

## 4. Trial Lifecycle

1. Case selection (browse library or upload AMTA/MYLaw PDF)
2. Role selection
3. Persona configuration
4. Preparation phase (case materials loaded, witness restrictions enforced, opening statements pre-generated)
5. Live trial (AMTA time limits and rules enforced)
6. Scoring
7. Coaching feedback
8. Replay & review

### 4.1 Opening Statement Pre-Generation

Opening statements for both prosecution and defense are generated during the **preparation phase**, not during the live trial. This eliminates the 15-25 second delay that would otherwise occur when the trial begins.

- Generated using the `AttorneyAgent.generate_opening()` method with case data context
- Stored in `prep_materials` (both file cache and database)
- Viewable and regenerable in the PreparationPanel "Openings" tab
- The "Begin Trial" button is gated on opening statement readiness
- During the live trial, only TTS audio needs to be fetched (~3-5s), not LLM text generation

---

## 4a. Case Upload & Parsing

### AMTA PDF Parser

When an AMTA-format PDF is uploaded, the system uses a specialized regex-based parser
(`backend/app/services/case_parser.py`) to extract structured content:

- **Synopsis**: Case summary from the first pages
- **Special Instructions**: Numbered competition rules (typically 20-24 instructions)
- **Witness Calling Restrictions**: Parsed from the Captains' Meeting form
- **Indictment/Complaint**: Formal charges and elements
- **Jury Instructions**: Numbered legal instructions
- **Stipulations**: Agreed-upon facts
- **Motions in Limine**: Pre-trial evidentiary rulings
- **Relevant Law**: Statutes (Penal Code sections) and case law (court decisions)
- **Exhibit List**: All exhibits with numbers and titles
- **Witness Affidavits**: Full text of affidavits, reports, and interrogations
  with side-assignment (prosecution, defense, or either)

### Parsing Approach

The parser uses a two-pass approach:
1. **Pass 1**: Detect section boundaries via header patterns and table-of-contents page
2. **Pass 2**: Extract each section's content using section-specific regexes

No LLM API calls are required for AMTA-format PDFs. The parser falls back to GPT-4
for non-AMTA format PDFs.

### Data Flow: Parsed Case → Session → UI

```
PDF Upload → case_parser.py → CaseData (case.py _cases dict / Supabase)
                                       ↓
                              session.py load_case() / initialize_session()
                                       ↓
                              session.case_data (full schema)
                                       ↓
                    ┌──────────────────┼──────────────────┐
                    ↓                  ↓                  ↓
          GET case-materials     Agent prompts     Witness restrictions
          (all fields returned)  (_build_case_context)  (calling validation)
                    ↓
          CaseMaterialsModal (7 tabs)
```

`session.case_data` carries all parsed fields: `synopsis`, `special_instructions`,
`jury_instructions`, `motions_in_limine`, `indictment`, `relevant_law`,
`witness_calling_restrictions`, `stipulations`, `exhibits`, `witnesses`,
`plaintiff`, `defendant`, `charge`, `charge_detail`, `case_type`.

### Case Materials UI (CaseMaterialsModal)

The modal provides seven tabs for reviewing case content during preparation:

| Tab | Contents |
|-----|----------|
| **Overview** | Parties, charge, indictment, synopsis, witness calling restrictions summary, quick stats |
| **Case Files** | Uploaded PDFs, images, and documents organised by section |
| **Witnesses** | Plaintiff, defense, and either-side witness affidavits with expandable details |
| **Exhibits** | Numbered exhibit list with descriptions and content |
| **Facts** | Background facts, evidence, stipulations, legal standards |
| **Rules** | Special Instructions (numbered), witness calling restrictions (by side) |
| **Legal** | Jury instructions, relevant statutes, relevant case law, motions in limine rulings |

### AMTA Trial Rules

The following rules from the Special Instructions are enforced by the trial state machine
and AI agent context:

| Rule | Special Instruction | Enforcement |
|------|---------------------|-------------|
| Witness calling restrictions | Captains' Meeting | `_resolve_called_by()` during agent init assigns witnesses per side |
| Time limits | SI 13 | 25 min direct, 25 min cross per side |
| Charge requirements | SI 10 | Prosecution must pursue specified charge |
| Closed-universe law | SI 7 | Only case law from "Relevant Law" section |
| No guilty portrayals | SI 17 | Witnesses cannot claim to be the perpetrator |
| Defendant materials | SI 5 | Martin only has interrogation, not affidavit |
| Evidence rules | SI 11 | Best Evidence limited to case packet items |
| Motions in limine | Pre-trial rulings | Injected into attorney agent context to prevent excluded evidence arguments |
| Special instructions | Full set | Included in attorney `_build_case_context()` as binding rules |
| Jury instruction elements | Numbered | Fed to attorneys so opening/closing statements address required elements |

---

## 5. Trial Phase Sequence

```
PREP → OPENING → PLAINTIFF_CASE → DEFENSE_CASE → CLOSING → SCORING → COMPLETE
```

Within each case-in-chief (plaintiff/defense):
```
For each witness:
  DIRECT → CROSS → REDIRECT (optional) → RECROSS (optional)
```

---

## 6. Authentication

- Users must log in before accessing the app
- Supported methods: email/password, Google, LinkedIn, Facebook, Discord
- Authentication handled by Supabase Auth
- Next.js middleware redirects unauthenticated users to `/login`

---

## 7. Transcript History

- Transcripts are saved progressively to Supabase Storage during the trial
- Users can review past trial transcripts at `/history`
- Transcripts are grouped by case name and show date, role, and phases completed
