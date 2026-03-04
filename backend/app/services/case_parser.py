"""
AMTA Mock Trial Case PDF Parser

Extracts structured case data from AMTA-style mock trial PDF documents.
Uses a two-pass approach:
  1. Extract per-page text from the PDF
  2. Identify section boundaries via header patterns and table-of-contents page
  3. Extract each section's content into a structured format

Supported sections:
  - Case name, court, charge, parties
  - Synopsis / case summary
  - Special instructions (participant rules)
  - Captains' meeting form (witness calling restrictions)
  - Indictment
  - Jury instructions
  - Stipulations
  - Motions in limine rulings
  - Relevant law (statutes + case law)
  - Exhibit list and exhibit content
  - Witness affidavits / reports / interrogations
"""

import io
import re
import logging
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Minimum length for an affidavit header match to be the "main" content
# on a page (vs. a passing reference)
_AFFIDAVIT_HEADER_RE = re.compile(
    r"^(?:\s*Revised\s+\S+\s+)?\s*\d*\s*"
    r"(AFFIDAVIT\s+OF\s+(.+?))\s*\d*\s*$",
    re.MULTILINE | re.IGNORECASE,
)
_REPORT_HEADER_RE = re.compile(
    r"(?:Expert\s+)?Report\s+of\s+(?:Dr\.\s+)?(.+?)(?:,\s*M\.?D\.?)?\s+"
    r"(?:State\s+v\.|Case)",
    re.IGNORECASE,
)
_FORENSIC_EVAL_RE = re.compile(
    r"FORENSIC\s+EVALUATION\s+CENTER",
    re.IGNORECASE,
)
_INTERROGATION_HEADER_RE = re.compile(
    r"^(?:\s*Revised\s+\S+\s+)?\s*\d*\s*"
    r"INTERVIEW\s+WITH\s+(.+?)\s*$",
    re.MULTILINE | re.IGNORECASE,
)


def extract_text_from_pdf_bytes(pdf_bytes: bytes) -> List[Dict[str, Any]]:
    """Extract text from PDF bytes, returning per-page results."""
    try:
        import PyPDF2
        reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        pages = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text() or ""
            pages.append({"page": i + 1, "text": text})
        return pages
    except ImportError:
        raise ImportError("PyPDF2 is required for PDF parsing")


def _get_page_text(pages: List[Dict[str, Any]], page_num: int) -> str:
    """Get text for a 1-indexed page number."""
    for p in pages:
        if p["page"] == page_num:
            return p["text"]
    return ""


def _get_range_text(
    pages: List[Dict[str, Any]], start: int, end: int
) -> str:
    """Concatenate text for pages in [start, end] (1-indexed, inclusive)."""
    parts = []
    for p in pages:
        if start <= p["page"] <= end:
            parts.append(p["text"])
    return "\n\n".join(parts)


# ─────────────────────────────────────────────────────────────────────
# Pass 1: Locate section boundaries
# ─────────────────────────────────────────────────────────────────────

def _detect_sections(pages: List[Dict[str, Any]]) -> Dict[str, Tuple[int, int]]:
    """
    Detect section page ranges.

    Returns dict mapping section_name -> (start_page, end_page) inclusive.
    Uses strict header matching to avoid false positives from references.
    """
    total_pages = len(pages)
    sections: Dict[str, Tuple[int, int]] = {}

    # Track key landmark pages
    synopsis_page = None
    special_instructions_start = None
    toc_page = None  # "AVAILABLE CASE DOCUMENTS" page
    captains_meeting_page = None
    indictment_page = None
    jury_instructions_start = None
    stipulations_start = None
    motions_start = None
    relevant_law_start = None
    exhibits_start = None
    verdict_form_page = None
    first_witness_page = None

    # Pass 1a: Find key landmark pages (synopsis, special instructions, TOC)
    for p in pages:
        pg = p["page"]
        text = p["text"]
        first_300 = re.sub(r"\n", " ", text[:400]).upper()

        if "SYNO" in first_300 and "PSIS" in first_300:
            if synopsis_page is None:
                synopsis_page = pg

        if "SPECIAL INSTRUCTIONS" in first_300:
            if special_instructions_start is None:
                special_instructions_start = pg

        if "AVAILABLE CASE DOCUMENTS" in first_300:
            if toc_page is None:
                toc_page = pg

    # Pass 1b: Find sections that depend on TOC page position
    for p in pages:
        pg = p["page"]
        text = p["text"]
        first_300 = re.sub(r"\n", " ", text[:400]).upper()

        # Captains' meeting form: must be after the TOC page
        if re.search(r"CA\s*PTAINS.*MEETING\s+FORM", first_300):
            if pg > (toc_page or 99) and captains_meeting_page is None:
                captains_meeting_page = pg

        # Indictment: standalone header with court header
        if re.search(r"\bINDICTMENT\b", first_300) and "STATE OF" in text[:500].upper():
            if pg > (toc_page or 0) and indictment_page is None:
                if "JURY INSTRUCTIONS" not in first_300:
                    indictment_page = pg

        if "JURY INSTRUCTIONS" in first_300:
            if pg > (toc_page or 0) and jury_instructions_start is None:
                jury_instructions_start = pg

        if re.search(r"^\s*STIPULATIONS\s*$", text, re.MULTILINE):
            if pg > (toc_page or 0) and stipulations_start is None:
                stipulations_start = pg

        if "MOTIONS IN LIMINE" in first_300 or "ORDER ON MOTIONS IN LIMINE" in first_300:
            if pg > (toc_page or 0) and motions_start is None:
                motions_start = pg

        if re.search(r"RELEVANT\s+(?:MIDLANDS\s+)?LAW", first_300):
            if pg > (toc_page or 0) + 1 and relevant_law_start is None:
                relevant_law_start = pg

        if text.strip().upper().startswith("EXHIBITS"):
            if exhibits_start is None:
                exhibits_start = pg

        if re.search(r"^\s*VERDICT\s+FORM\s*$", text, re.MULTILINE | re.IGNORECASE):
            if pg > (toc_page or 0) and verdict_form_page is None:
                verdict_form_page = pg

        if first_witness_page is None and pg > (exhibits_start or toc_page or 30):
            if _AFFIDAVIT_HEADER_RE.search(text[:300]):
                oath = text[:500]
                if "duly sworn" in oath.lower() or "competent to make" in oath.lower():
                    first_witness_page = pg

    # Build section ranges using landmarks
    if synopsis_page:
        end = (special_instructions_start or toc_page or synopsis_page + 2) - 1
        sections["synopsis"] = (synopsis_page, min(synopsis_page, end))

    if special_instructions_start:
        end = (toc_page or special_instructions_start + 5) - 1
        sections["special_instructions"] = (special_instructions_start, end)

    if toc_page:
        sections["available_documents"] = (toc_page, toc_page)

    if captains_meeting_page:
        # Captains' meeting is typically 1-2 pages (form + gender pronouns)
        end = min(captains_meeting_page + 2, (indictment_page or captains_meeting_page + 2) - 1)
        sections["captains_meeting"] = (captains_meeting_page, end)

    if indictment_page:
        end = (jury_instructions_start or indictment_page + 2) - 1
        sections["indictment"] = (indictment_page, min(indictment_page + 1, end))

    if jury_instructions_start:
        # Jury instructions end before the verdict form
        if verdict_form_page and verdict_form_page > jury_instructions_start:
            end = verdict_form_page - 1
        elif stipulations_start and stipulations_start > jury_instructions_start:
            end = stipulations_start - 1
        else:
            end = jury_instructions_start + 5
        sections["jury_instructions"] = (jury_instructions_start, end)

    if verdict_form_page:
        end = (stipulations_start or verdict_form_page + 1)
        sections["verdict_form"] = (verdict_form_page, verdict_form_page)

    if stipulations_start:
        end = (motions_start or stipulations_start + 3) - 1
        sections["stipulations"] = (stipulations_start, end)

    if motions_start:
        if relevant_law_start and relevant_law_start > motions_start:
            end = relevant_law_start - 1
        else:
            end = motions_start + 8
        sections["motions_in_limine"] = (motions_start, end)

    if relevant_law_start:
        end = (exhibits_start or relevant_law_start + 15) - 1
        sections["relevant_law"] = (relevant_law_start, end)

    if exhibits_start:
        end = (first_witness_page or exhibits_start + 100) - 1
        sections["exhibits"] = (exhibits_start, end)

    if first_witness_page:
        sections["witnesses"] = (first_witness_page, total_pages)

    return sections


# ─────────────────────────────────────────────────────────────────────
# Pass 2: Extract structured content from each section
# ─────────────────────────────────────────────────────────────────────

def _extract_case_header(pages: List[Dict[str, Any]]) -> Dict[str, str]:
    """Extract case name, court, parties from the title page and indictment."""
    header = {
        "case_name": "",
        "court": "",
        "jurisdiction": "Midlands",
        "case_number": "",
        "charge": "",
        "plaintiff": "",
        "defendant": "",
        "revision_date": "",
    }

    for p in pages[:3]:
        text = p["text"]

        rev_date = re.search(r"Revised\s+(\d{2}/\d{2}/\d{2,4})", text)
        if rev_date and not header["revision_date"]:
            header["revision_date"] = rev_date.group(1)

        # Look for "State of X \n v. \n Name" pattern
        v_match = re.search(
            r"(State\s+of\s+\w+)\s*\n\s*v\.\s*\n\s*(.+?)(?:\s*\n|$)",
            text,
            re.IGNORECASE,
        )
        if v_match and not header["case_name"]:
            plaintiff = v_match.group(1).strip()
            defendant = v_match.group(2).strip()
            header["case_name"] = f"{plaintiff} v. {defendant}"
            header["plaintiff"] = plaintiff
            header["defendant"] = defendant

    # Try to get case number from indictment pages
    for p in pages[:20]:
        text = p["text"]
        case_no = re.search(r"CASE\s+NO\.?:?\s*(CR[\d\s\-]+\d)", text, re.IGNORECASE)
        if case_no and not header["case_number"]:
            # Normalize spaces around dashes
            header["case_number"] = re.sub(r"\s*-\s*", "-", case_no.group(1).strip())

    return header


def _extract_synopsis(
    pages: List[Dict[str, Any]], sections: Dict[str, Tuple[int, int]]
) -> str:
    """Extract case synopsis text."""
    if "synopsis" not in sections:
        return ""

    start, end = sections["synopsis"]
    text = _get_range_text(pages, start, end)

    # Strip header and extract until AVAILABLE WITNESSES
    text = re.sub(r"^.*?SYNO\s*PSIS\s*", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.split(r"AVAILABLE\s+WITNESSES", text, flags=re.IGNORECASE)[0]
    return text.strip()


def _extract_available_witnesses(
    pages: List[Dict[str, Any]], sections: Dict[str, Tuple[int, int]]
) -> List[Dict[str, str]]:
    """Extract the available witnesses list from synopsis page."""
    if "synopsis" not in sections:
        return []

    start, _ = sections["synopsis"]
    text = _get_page_text(pages, start)
    witnesses = []

    witness_section = re.search(
        r"AVAILABLE\s+WITNESSES\s*(.*?)(?=SUSPECTED\s+ERRORS|LICENSING|NOTES|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not witness_section:
        return witnesses

    # Split by ● (bullet), handling cases where newlines are missing
    raw = witness_section.group(1).strip()
    items = re.split(r"[●•]", raw)
    for item in items:
        item = item.strip().lstrip("-– \n")
        if item and len(item) > 3:
            name_role = item.split(",", 1)
            name = name_role[0].strip()
            role = name_role[1].strip() if len(name_role) > 1 else ""
            witnesses.append({"name": name, "role": role})

    return witnesses


def _extract_witness_calling_restrictions(
    pages: List[Dict[str, Any]], sections: Dict[str, Tuple[int, int]]
) -> Dict[str, List[str]]:
    """
    Extract witness calling restrictions from the Captains' Meeting form.
    Returns dict with 'prosecution_only', 'defense_only', 'either_side' lists.
    """
    restrictions = {
        "prosecution_only": [],
        "defense_only": [],
        "either_side": [],
    }

    if "captains_meeting" not in sections:
        return restrictions

    start, end = sections["captains_meeting"]
    text = _get_range_text(pages, start, end)

    # Parse "Only the Prosecution may call X, Y, Z. Only the Defense may call A, B, C.
    # Either side may call D, E, F."
    # Use "Only the Defense" as boundary instead of "." to avoid matching "Dr."
    pros_match = re.search(
        r"Only\s+the\s+Prosecution\s+may\s+call\s+(.+?)\.\s*Only\s+the\s+Defense",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if pros_match:
        names = re.split(r",\s*(?:or\s+)?", pros_match.group(1))
        restrictions["prosecution_only"] = [
            " ".join(n.split()) for n in names if n.strip() and len(n.strip()) > 1
        ]

    def_match = re.search(
        r"Only\s+the\s+Defense\s+may\s+call\s+(.+?)\.\s*Either\s+side",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if def_match:
        names = re.split(r",\s*(?:or\s+)?", def_match.group(1))
        restrictions["defense_only"] = [
            " ".join(n.split()) for n in names if n.strip() and len(n.strip()) > 1
        ]

    either_match = re.search(
        r"Either\s+side\s+may\s+call\s+(.+?)\.\s",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if either_match:
        names = re.split(r",\s*(?:or\s+)?", either_match.group(1))
        restrictions["either_side"] = [
            " ".join(n.split()) for n in names if n.strip() and len(n.strip()) > 1
        ]

    return restrictions


def _extract_numbered_items(text: str) -> List[Dict[str, Any]]:
    """
    Extract numbered items from text, filtering out false positives.
    Returns list of dicts with 'number' and 'content' keys.
    Only keeps items whose numbers form a plausible ascending sequence.
    """
    # Match numbered items: allow any word boundary before the number
    # The sequential filter will reject false positives
    matches = list(re.finditer(r"(?:^|\s)(\d+)\.\s+", text))
    if not matches:
        return []

    raw_items = []
    for idx, match in enumerate(matches):
        num = int(match.group(1))
        start_pos = match.end()

        if idx + 1 < len(matches):
            end_pos = matches[idx + 1].start()
        else:
            end_pos = len(text)

        content = text[start_pos:end_pos].strip()
        content = " ".join(content.split())

        if len(content) < 10:
            continue

        raw_items.append({"number": num, "content": content})

    # Filter to plausible sequential items: keep items where number
    # is within reasonable range of previous item (allow small gaps for
    # items on pages with poor PDF extraction)
    filtered = []
    last_num = 0
    for item in raw_items:
        n = item["number"]
        if n > last_num and n <= last_num + 3 and n <= 200:
            filtered.append(item)
            last_num = n
        elif not filtered and n <= 5:
            filtered.append(item)
            last_num = n

    return filtered


def _extract_special_instructions(
    pages: List[Dict[str, Any]], sections: Dict[str, Tuple[int, int]]
) -> List[Dict[str, Any]]:
    """Extract numbered special instructions."""
    if "special_instructions" not in sections:
        return []

    start, end = sections["special_instructions"]
    text = _get_range_text(pages, start, end)

    # Remove header
    text = re.sub(
        r"^.*?SPECIAL\s+INSTRUCTIONS\s*",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    items = _extract_numbered_items(text)
    instructions = []

    for item in items:
        content = item["content"]
        # Try to separate title from body
        title_match = re.match(r"([A-Z][^.]+\.)\s*(.*)", content, re.DOTALL)
        if title_match and len(title_match.group(1)) < 80:
            instructions.append({
                "number": item["number"],
                "title": title_match.group(1).strip(),
                "content": title_match.group(2).strip(),
            })
        else:
            instructions.append({
                "number": item["number"],
                "title": "",
                "content": content,
            })

    return instructions


def _extract_indictment(
    pages: List[Dict[str, Any]], sections: Dict[str, Tuple[int, int]]
) -> Dict[str, str]:
    """Extract indictment details."""
    if "indictment" not in sections:
        return {}

    start, end = sections["indictment"]
    text = _get_range_text(pages, start, end)

    result = {"charge": "", "charge_detail": "", "full_text": ""}

    # Look for COUNT ONE header and charge name
    count_match = re.search(
        r"COUNT\s+ONE\s*\n\s*(\w[\w\s]*?)\s*\n\s*(.*?)(?=COUNT\s+TWO|A\s+TRUE\s+BILL|THE\s+JURORS|$)",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if count_match:
        result["charge"] = count_match.group(1).strip()
        detail = count_match.group(2).strip()
        result["charge_detail"] = " ".join(detail.split())

    result["full_text"] = " ".join(text.split())
    return result


def _extract_jury_instructions(
    pages: List[Dict[str, Any]], sections: Dict[str, Tuple[int, int]]
) -> List[Dict[str, Any]]:
    """Extract numbered jury instructions."""
    if "jury_instructions" not in sections:
        return []

    start, end = sections["jury_instructions"]
    text = _get_range_text(pages, start, end)
    instructions = []

    # Split on INSTRUCTION NO. X pattern
    blocks = re.split(
        r"INSTRUCTION\s+NO\.\s*(\d+):?\s*",
        text,
        flags=re.IGNORECASE,
    )

    if len(blocks) > 1:
        for i in range(1, len(blocks) - 1, 2):
            num = int(blocks[i])
            content = blocks[i + 1].strip()

            # Try to extract a title (all-caps line at the start)
            title_match = re.match(
                r"([A-Z][A-Z\s/&;()]+)\s+(.*)",
                content,
                re.DOTALL,
            )
            if title_match:
                title = title_match.group(1).strip()
                body = title_match.group(2).strip()
            else:
                title = ""
                body = content

            body = " ".join(body.split())
            instructions.append({
                "id": f"instruction_{num}",
                "number": num,
                "title": title,
                "content": body,
            })

    return instructions


def _extract_stipulations(
    pages: List[Dict[str, Any]], sections: Dict[str, Tuple[int, int]]
) -> List[Dict[str, str]]:
    """Extract numbered stipulations."""
    if "stipulations" not in sections:
        return []

    start, end = sections["stipulations"]
    text = _get_range_text(pages, start, end)

    # Remove everything before "STIPULATIONS" header
    text = re.sub(
        r"^.*?STIPULATIONS\s*",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    items = _extract_numbered_items(text)
    return [
        {
            "id": f"stip_{item['number']}",
            "number": item["number"],
            "content": item["content"],
        }
        for item in items
    ]


def _extract_motions_in_limine(
    pages: List[Dict[str, Any]], sections: Dict[str, Tuple[int, int]]
) -> List[Dict[str, Any]]:
    """Extract motions in limine rulings."""
    if "motions_in_limine" not in sections:
        return []

    start, end = sections["motions_in_limine"]
    text = _get_range_text(pages, start, end)

    # Remove header
    text = re.sub(
        r"^.*?ORDER\s+ON\s+MOTIONS?\s+IN\s+LIMINE.*?\n",
        "",
        text,
        flags=re.DOTALL | re.IGNORECASE,
    )

    motions = []
    # Split on lettered sections: A., B., C. etc.
    motion_blocks = re.split(
        r"\n\s*([A-Z])\.\s+Motion\s+to\s+",
        text,
        flags=re.IGNORECASE,
    )

    if len(motion_blocks) > 1:
        for i in range(1, len(motion_blocks) - 1, 2):
            letter = motion_blocks[i]
            content = motion_blocks[i + 1].strip()
            title_end = content.find("\n")
            if title_end > 0:
                title = f"Motion to {content[:title_end].strip()}"
                body = content[title_end:].strip()
            else:
                title = f"Motion to {content[:100]}"
                body = content

            body = " ".join(body.split())
            motions.append({
                "id": f"motion_{letter.lower()}",
                "letter": letter,
                "title": title,
                "ruling": body,
            })

    return motions


def _extract_relevant_law(
    pages: List[Dict[str, Any]], sections: Dict[str, Tuple[int, int]]
) -> Dict[str, Any]:
    """Extract relevant statutes and case law."""
    if "relevant_law" not in sections:
        return {"statutes": [], "cases": []}

    start, end = sections["relevant_law"]
    text = _get_range_text(pages, start, end)

    statutes = []
    cases = []

    # Split into statutes section and cases section
    cases_start = re.search(r"Relevant\s+Cases", text, re.IGNORECASE)

    statute_text = text[:cases_start.start()] if cases_start else text
    case_text = text[cases_start.start():] if cases_start else ""

    # Extract statutes: "Midlands Penal Code §18-XXX Title"
    statute_blocks = re.findall(
        r"(Midlands\s+Penal\s+Code\s+§[\d\-]+\s+.+?)\s*\n(.*?)(?=Midlands\s+Penal\s+Code\s+§|$)",
        statute_text,
        re.DOTALL,
    )
    for title, body in statute_blocks:
        title = title.strip()
        body = " ".join(body.strip().split())
        statute_id = re.sub(r"[^a-z0-9]", "_", title.lower()).strip("_")
        statutes.append({
            "id": f"statute_{statute_id[:50]}",
            "title": title,
            "content": body,
        })

    # Extract case law: "State v. Name (Year)"
    if case_text:
        case_blocks = re.split(
            r"\n\s*((?:State|Estate|[A-Z][a-z]+(?:'s)?)\s+v\.\s+[A-Z][a-zA-Z\s]+?\(\d{4}\))\s*\n",
            case_text,
        )
        if len(case_blocks) > 1:
            for i in range(1, len(case_blocks) - 1, 2):
                citation = case_blocks[i].strip()
                body = case_blocks[i + 1].strip()
                body = " ".join(body.split())
                case_id = re.sub(r"[^a-z0-9]", "_", citation.lower()).strip("_")
                if len(body) > 20:
                    cases.append({
                        "id": f"case_{case_id[:50]}",
                        "citation": citation,
                        "content": body,
                    })

    return {"statutes": statutes, "cases": cases}


def _extract_exhibits_from_toc(
    pages: List[Dict[str, Any]], sections: Dict[str, Tuple[int, int]]
) -> List[Dict[str, Any]]:
    """Extract exhibit list from the available documents/TOC page."""
    if "available_documents" not in sections:
        return []

    start, _ = sections["available_documents"]
    text = _get_page_text(pages, start)

    exhibits = []
    exhibit_section = re.search(
        r"Exhibit\s+List\s*(.*?)$",
        text,
        re.DOTALL | re.IGNORECASE,
    )
    if not exhibit_section:
        return exhibits

    exhibit_text = exhibit_section.group(1)
    lines = exhibit_text.strip().split("\n")

    for line in lines:
        line = line.strip()
        num_match = re.match(r"(\d+)\.\s+(.+)", line)
        if num_match:
            exhibits.append({
                "id": f"exhibit_{num_match.group(1)}",
                "exhibit_number": num_match.group(1),
                "title": num_match.group(2).strip(),
                "content_type": "document",
            })

    return exhibits


def _detect_witness_pages(
    pages: List[Dict[str, Any]], sections: Dict[str, Tuple[int, int]]
) -> List[Dict[str, Any]]:
    """
    Detect individual witness affidavit/report/interrogation boundaries
    within the witnesses section.
    """
    if "witnesses" not in sections:
        return []

    w_start, w_end = sections["witnesses"]
    witnesses = []
    current_witness = None

    for p in pages:
        pg = p["page"]
        if pg < w_start or pg > w_end:
            continue

        text = p["text"]
        first_400 = text[:400]

        # Check for affidavit header with oath
        aff_match = _AFFIDAVIT_HEADER_RE.search(first_400)
        if aff_match and ("duly sworn" in text[:600].lower() or "competent to make" in text[:600].lower()):
            name = aff_match.group(2).strip()
            # Clean up trailing numbers or artifacts
            name = re.sub(r"\s+\d+\s*$", "", name).strip()
            if current_witness:
                current_witness["end_page"] = pg - 1
                witnesses.append(current_witness)
            current_witness = {
                "name": name,
                "document_type": "affidavit",
                "start_page": pg,
                "end_page": w_end,
            }
            continue

        # Check for expert report header
        report_match = _REPORT_HEADER_RE.search(first_400)
        if report_match:
            name = report_match.group(1).strip()
            name = re.sub(r"\s+\d+\s*$", "", name).strip()
            if current_witness:
                current_witness["end_page"] = pg - 1
                witnesses.append(current_witness)
            current_witness = {
                "name": name,
                "document_type": "report",
                "start_page": pg,
                "end_page": w_end,
            }
            continue

        # Check for forensic evaluation
        if _FORENSIC_EVAL_RE.search(first_400):
            # Extract examiner name (handle tabs in PDF text)
            # Match everything after "Examiner:" until a newline or end
            examiner = re.search(r"Examiner:[\s\t]*([^\n]+)", text)
            if examiner:
                name = examiner.group(1).strip()
                # Clean up tabs, trailing numbers/artifacts
                name = re.sub(r"[\t]+", " ", name)
                name = re.sub(r"\s+\d+\s*$", "", name).strip()
                # Remove trailing degree suffixes for consistency
                name = re.sub(r",?\s*Psy\.?D\.?\s*$", "", name, flags=re.IGNORECASE).strip()
            else:
                name = "Unknown"
            if current_witness:
                current_witness["end_page"] = pg - 1
                witnesses.append(current_witness)
            current_witness = {
                "name": name,
                "document_type": "report",
                "start_page": pg,
                "end_page": w_end,
            }
            continue

    # Don't forget the last witness
    if current_witness:
        witnesses.append(current_witness)

    return witnesses


def _classify_witness_side(
    witness_name: str,
    restrictions: Dict[str, List[str]],
) -> str:
    """Determine which side calls a witness based on captains' meeting restrictions."""
    name_lower = witness_name.lower()

    for pros_name in restrictions.get("prosecution_only", []):
        if _names_match(name_lower, pros_name.lower()):
            return "prosecution"

    for def_name in restrictions.get("defense_only", []):
        if _names_match(name_lower, def_name.lower()):
            return "defense"

    for either_name in restrictions.get("either_side", []):
        if _names_match(name_lower, either_name.lower()):
            return "either"

    return "unknown"


def _names_match(name_a: str, name_b: str) -> bool:
    """Fuzzy match two names (handles "Dr. X" vs "X", first/last variations)."""
    a = re.sub(r"(dr\.?\s*|investigator\s*|,?\s*m\.?d\.?|,?\s*psy\.?d\.?)", "", name_a).strip()
    b = re.sub(r"(dr\.?\s*|investigator\s*|,?\s*m\.?d\.?|,?\s*psy\.?d\.?)", "", name_b).strip()

    if a == b:
        return True

    # Check if last names match
    a_parts = a.split()
    b_parts = b.split()
    if a_parts and b_parts and a_parts[-1] == b_parts[-1]:
        return True

    return False


def _extract_witness_affidavits(
    pages: List[Dict[str, Any]],
    sections: Dict[str, Tuple[int, int]],
    witness_pages: List[Dict[str, Any]],
    restrictions: Dict[str, List[str]],
    available_witnesses: List[Dict[str, str]],
) -> List[Dict[str, Any]]:
    """Build full witness records with affidavit text and metadata."""
    witnesses = []

    for wp in witness_pages:
        name = wp["name"]
        start = wp["start_page"]
        end = wp["end_page"]
        doc_type = wp["document_type"]

        affidavit_text = _get_range_text(pages, start, end)

        called_by = _classify_witness_side(name, restrictions)

        # Find role from available witnesses list
        role = ""
        for aw in available_witnesses:
            if _names_match(name.lower(), aw["name"].lower()):
                role = aw.get("role", "")
                break

        witness_id = re.sub(r"[^a-z0-9]", "_", name.lower()).strip("_")

        witnesses.append({
            "id": f"witness_{witness_id}",
            "name": name,
            "document_type": doc_type,
            "called_by": called_by,
            "role_description": role,
            "start_page": start,
            "end_page": end,
            "affidavit": affidavit_text,
            "key_facts": [],
        })

    return witnesses


# ─────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────

def parse_mock_trial_pdf(pdf_bytes: bytes) -> Dict[str, Any]:
    """
    Parse an AMTA-style mock trial PDF into structured case data.

    Returns a comprehensive dict with all extracted sections:
    - name, case_number, plaintiff, defendant, charge
    - synopsis, special_instructions, indictment
    - jury_instructions, stipulations, motions_in_limine
    - relevant_law (statutes + cases)
    - exhibits, witnesses (with full affidavit text)
    - witness_calling_restrictions
    - facts (unified list), legal_standards (unified list)
    """
    logger.info("Starting AMTA mock trial PDF parsing...")
    pages = extract_text_from_pdf_bytes(pdf_bytes)
    logger.info(f"Extracted text from {len(pages)} pages")

    # Pass 1: Detect sections
    sections = _detect_sections(pages)
    logger.info(f"Detected sections: {list(sections.keys())}")
    for name, (s, e) in sections.items():
        logger.info(f"  {name}: pages {s}-{e}")

    # Pass 2: Extract content
    header = _extract_case_header(pages)
    synopsis = _extract_synopsis(pages, sections)
    available_witnesses = _extract_available_witnesses(pages, sections)
    restrictions = _extract_witness_calling_restrictions(pages, sections)
    special_instructions = _extract_special_instructions(pages, sections)
    indictment = _extract_indictment(pages, sections)
    jury_instructions = _extract_jury_instructions(pages, sections)
    stipulations = _extract_stipulations(pages, sections)
    motions = _extract_motions_in_limine(pages, sections)
    law = _extract_relevant_law(pages, sections)
    exhibits = _extract_exhibits_from_toc(pages, sections)

    # Detect and extract witnesses
    witness_pages = _detect_witness_pages(pages, sections)
    witness_affidavits = _extract_witness_affidavits(
        pages, sections, witness_pages, restrictions, available_witnesses
    )

    # Enrich header with indictment info
    if indictment.get("charge") and not header.get("charge"):
        header["charge"] = indictment["charge"]

    # Build unified legal standards list
    legal_standards = []
    for ji in jury_instructions:
        legal_standards.append({
            "id": ji["id"],
            "content": f"{ji.get('title', '')}: {ji['content']}" if ji.get("title") else ji["content"],
            "source": "Jury Instructions",
        })
    for statute in law.get("statutes", []):
        legal_standards.append({
            "id": statute["id"],
            "content": f"{statute['title']}: {statute['content']}",
            "source": "Midlands Penal Code",
        })
    for case in law.get("cases", []):
        legal_standards.append({
            "id": case["id"],
            "content": f"{case['citation']}: {case['content']}",
            "source": "Case Law",
        })

    # Build unified facts list
    facts = _build_facts_list(synopsis, stipulations, indictment)

    case_data = {
        "name": header.get("case_name", "Unknown Case"),
        "case_number": header.get("case_number", ""),
        "court": header.get("court", ""),
        "jurisdiction": header.get("jurisdiction", "Midlands"),
        "revision_date": header.get("revision_date", ""),
        "plaintiff": header.get("plaintiff", ""),
        "defendant": header.get("defendant", ""),
        "charge": header.get("charge", ""),
        "charge_detail": indictment.get("charge_detail", ""),
        "case_type": "criminal" if indictment.get("charge") else "civil",
        "synopsis": synopsis,
        "summary": synopsis,
        "description": synopsis[:500] if synopsis else "",
        "available_witnesses": available_witnesses,
        "witness_calling_restrictions": restrictions,
        "special_instructions": special_instructions,
        "indictment": indictment,
        "stipulations": stipulations,
        "jury_instructions": jury_instructions,
        "motions_in_limine": motions,
        "relevant_law": law,
        "exhibits": exhibits,
        "witnesses": witness_affidavits,
        "legal_standards": legal_standards,
        "facts": facts,
        "section_pages": {k: {"start": v[0], "end": v[1]} for k, v in sections.items()},
        "total_pages": len(pages),
        "witness_count": len(witness_affidavits),
        "exhibit_count": len(exhibits),
    }

    logger.info(
        f"Parsing complete: {case_data['name']} | "
        f"{len(witness_affidavits)} witnesses, {len(exhibits)} exhibits, "
        f"{len(stipulations)} stipulations, {len(jury_instructions)} jury instructions, "
        f"{len(law.get('statutes', []))} statutes, {len(law.get('cases', []))} case law entries"
    )

    return case_data


def _build_facts_list(
    synopsis: str,
    stipulations: List[Dict],
    indictment: Dict,
) -> List[Dict[str, Any]]:
    """Build a unified facts list from various sources."""
    facts = []

    if synopsis:
        facts.append({
            "id": "fact_synopsis",
            "fact_type": "background",
            "content": synopsis,
            "source": "Synopsis",
        })

    if indictment.get("charge_detail"):
        facts.append({
            "id": "fact_indictment",
            "fact_type": "legal_standard",
            "content": f"Charge: {indictment.get('charge', 'Unknown')}. {indictment['charge_detail']}",
            "source": "Indictment",
        })

    for stip in stipulations:
        facts.append({
            "id": stip["id"],
            "fact_type": "stipulation",
            "content": stip["content"],
            "source": "Stipulations",
        })

    return facts
