"""
Mock Trial Case Sources

This module provides metadata for publicly available mock trial cases.
Actual case content must be downloaded by users from the source websites
and uploaded to the system, as case materials are copyrighted.

Primary Source: MYLaw (Maryland Youth & the Law)
https://www.mylaw.org/mock-trial-cases-and-resources

All case materials are copyrighted by their respective owners.
Express permission is required for re-print/distribution/use.
Appropriate credit must be extended to case authors.

Data persistence:
- Favorites, recent cases, and uploaded cases are persisted to Supabase
- Falls back to in-memory storage if Supabase is not configured
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


# =============================================================================
# CASE SOURCES - Metadata Only (No Copyrighted Content)
# =============================================================================

# AMTA cases (American Mock Trial Association)
AMTA_CASE_SOURCES: List[Dict[str, Any]] = [
    {
        "id": "amta_2026_state_v_martin",
        "title": "State of Midlands v. Charlie Martin",
        "source": "AMTA (American Mock Trial Association)",
        "source_url": "https://www.collegemocktrial.org",
        "year": 2026,
        "case_type": "criminal",
        "difficulty": "advanced",
        "description": "2025-26 AMTA Criminal Case. Charlie Martin is indicted for murder after "
                       "the death of fellow reality TV contestant Rob Armstrong during filming of "
                       "The Saboteurs. Features 11 witnesses, 32 exhibits, and complex forensic evidence.",
        "requires_upload": True,
        "pdf_urls": [],
        "password_protected": True,
        "charge": "Murder (First Degree Felony)",
        "jurisdiction": "Midlands",
        "witness_count": 11,
        "exhibit_count": 32,
    },
]

# MYLaw cases with direct PDF URLs where available
# Note: Current year cases are password-protected; archived cases may be public
MYLAW_CASE_SOURCES: List[Dict[str, Any]] = [
    {
        "id": "mylaw_2025_ballan_v_chesapeake",
        "title": "Micah Ballan v. Chesapeake Corrections Inc. and Dylan Oberfeld",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2025,
        "case_type": "civil",
        "difficulty": "intermediate",
        "description": "2025-26 MYLaw Mock Trial Competition case (current year - password protected).",
        "requires_upload": True,
        "pdf_urls": [],  # Password protected
        "password_protected": True,
    },
    {
        "id": "mylaw_2024_state_v_luna",
        "title": "State of Maryland v. Dana Luna",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2024,
        "case_type": "criminal",
        "difficulty": "intermediate",
        "description": "2024-25 MYLaw Mock Trial Competition case.",
        "requires_upload": True,
        "pdf_urls": [],  # May still be protected
        "password_protected": True,
    },
    {
        "id": "mylaw_2023_harper_v_reese",
        "title": "Parker Harper v. Dakota Reese",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2023,
        "case_type": "civil",
        "difficulty": "intermediate",
        "description": "2023-24 MYLaw Mock Trial Competition case. Civil case with exhibit 18 video content.",
        "requires_upload": True,
        "pdf_urls": [],  # Links available on page
        "password_protected": False,
    },
    {
        "id": "mylaw_2022_state_v_grimes",
        "title": "State of Maryland v. Ryan Grimes",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2022,
        "case_type": "criminal",
        "difficulty": "intermediate",
        "description": "2022-23 MYLaw Mock Trial Competition case. Criminal case with rules, procedures, and exhibits.",
        "requires_upload": True,
        "pdf_urls": [],
        "password_protected": False,
    },
    {
        "id": "mylaw_2021_griggs_v_donahue",
        "title": "Estate of Aaron Griggs v. Jodie Donahue",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2021,
        "case_type": "civil",
        "difficulty": "intermediate",
        "description": "2021-22 MYLaw Mock Trial Competition case. Civil wrongful death case.",
        "requires_upload": True,
        "pdf_urls": [],
        "password_protected": False,
    },
    {
        "id": "mylaw_2020_state_v_gardner",
        "title": "State v. Gardner",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2020,
        "case_type": "criminal",
        "difficulty": "intermediate",
        "description": "2020-21 MYLaw Mock Trial Competition case. Criminal case.",
        "requires_upload": True,
        "pdf_urls": [],
        "password_protected": False,
    },
    {
        "id": "mylaw_2019_wolfe_v_shepherd",
        "title": "Wolfe v. Shepherd",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2019,
        "case_type": "civil",
        "difficulty": "intermediate",
        "description": "2019-20 MYLaw Mock Trial Competition case. Civil case.",
        "requires_upload": True,
        "pdf_urls": [],
        "password_protected": False,
    },
    {
        "id": "mylaw_2018_state_v_tannen",
        "title": "Maryland v. Tannen",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2018,
        "case_type": "criminal",
        "difficulty": "intermediate",
        "description": "2018-19 MYLaw Mock Trial Competition case. Criminal case.",
        "requires_upload": True,
        "pdf_urls": [],
        "password_protected": False,
    },
    {
        "id": "mylaw_2017_slater_v_kapowski",
        "title": "Slater v. Kapowski",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2017,
        "case_type": "civil",
        "difficulty": "intermediate",
        "description": "2017-18 MYLaw Mock Trial Competition case. Civil case.",
        "requires_upload": True,
        "pdf_urls": [],
        "password_protected": False,
    },
    {
        "id": "mylaw_2016_perez_v_dempsey",
        "title": "Perez v. Dempsey et al",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2016,
        "case_type": "civil",
        "difficulty": "intermediate",
        "description": "2016-17 MYLaw Mock Trial Competition case. Civil case.",
        "requires_upload": True,
        "pdf_urls": [],
        "password_protected": False,
    },
    {
        "id": "mylaw_2015_state_v_gray",
        "title": "State of Maryland v. Darren Gray",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2015,
        "case_type": "criminal",
        "difficulty": "intermediate",
        "description": "2015-16 MYLaw Mock Trial Competition case. Criminal case.",
        "requires_upload": True,
        "pdf_urls": [],
        "password_protected": False,
    },
    {
        "id": "mylaw_2014_williams_v_swathmore",
        "title": "Chris Williams v. Swathmore Pavilion",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2014,
        "case_type": "civil",
        "difficulty": "intermediate",
        "description": "2014-15 MYLaw Mock Trial Competition case. Civil case.",
        "requires_upload": True,
        "pdf_urls": [],
        "password_protected": False,
    },
    {
        "id": "mylaw_2013_state_v_harding",
        "title": "State of Maryland v. Danny Harding",
        "source": "MYLaw (Maryland Youth & the Law)",
        "source_url": "https://www.mylaw.org/mock-trial-cases-and-resources",
        "year": 2013,
        "case_type": "criminal",
        "difficulty": "intermediate",
        "description": "2013-14 MYLaw Mock Trial Competition case. Criminal case.",
        "requires_upload": True,
        "pdf_urls": [],
        "password_protected": False,
    },
]


def get_case_source_by_id(case_id: str) -> Optional[Dict[str, Any]]:
    """Get a case source entry by ID (searches AMTA and MYLaw sources)."""
    for case in AMTA_CASE_SOURCES:
        if case["id"] == case_id:
            return case
    for case in MYLAW_CASE_SOURCES:
        if case["id"] == case_id:
            return case
    return None


# =============================================================================
# CASE SECTIONS - For organizing uploaded content
# =============================================================================

CASE_SECTIONS = [
    {
        "id": "summary",
        "name": "Case Summary",
        "description": "Overview of the case, parties, and key issues",
        "required": True,
        "order": 1,
    },
    {
        "id": "special_instructions",
        "name": "Special Instructions",
        "description": "AMTA participant rules, witness selection restrictions, and competition guidelines",
        "required": False,
        "order": 2,
    },
    {
        "id": "indictment",
        "name": "Indictment / Complaint",
        "description": "Formal charge(s) or complaint filed against the defendant",
        "required": False,
        "order": 3,
    },
    {
        "id": "witnesses_plaintiff",
        "name": "Plaintiff/Prosecution Witnesses",
        "description": "Witness affidavits for the plaintiff or prosecution side",
        "required": True,
        "order": 4,
    },
    {
        "id": "witnesses_defense",
        "name": "Defense Witnesses",
        "description": "Witness affidavits for the defense side",
        "required": True,
        "order": 5,
    },
    {
        "id": "witnesses_either",
        "name": "Either-Side Witnesses",
        "description": "Witness affidavits for witnesses that may be called by either side",
        "required": False,
        "order": 6,
    },
    {
        "id": "exhibits",
        "name": "Exhibits",
        "description": "Documents, photos, reports, and other evidence",
        "required": True,
        "order": 7,
    },
    {
        "id": "stipulations",
        "name": "Stipulations",
        "description": "Agreed-upon facts that do not require proof",
        "required": False,
        "order": 8,
    },
    {
        "id": "jury_instructions",
        "name": "Jury Instructions / Legal Standards",
        "description": "Applicable laws and jury instructions",
        "required": True,
        "order": 9,
    },
    {
        "id": "relevant_law",
        "name": "Relevant Law",
        "description": "Applicable statutes and case law citations",
        "required": False,
        "order": 10,
    },
    {
        "id": "motions_in_limine",
        "name": "Motions in Limine",
        "description": "Pre-trial rulings on evidentiary issues",
        "required": False,
        "order": 11,
    },
    {
        "id": "rules",
        "name": "Rules & Procedures",
        "description": "Competition rules and procedural guidelines (MRE, AMTA rules)",
        "required": False,
        "order": 12,
    },
]


# =============================================================================
# DATABASE-BACKED STORAGE WITH IN-MEMORY FALLBACK
# =============================================================================

# In-memory fallback storage (used when Supabase is not configured)
_uploaded_cases: Dict[str, Dict[str, Any]] = {}
_favorite_cases: set = set()
_recently_accessed: List[Dict[str, Any]] = []
MAX_RECENT_CASES = 10

# Database repositories (initialized lazily)
_prefs_repo = None
_cases_repo = None
_db_available = None


def _get_repos():
    """
    Get database repositories, initializing and verifying on first call.
    Returns (prefs_repo, cases_repo, db_available).
    """
    global _prefs_repo, _cases_repo, _db_available
    
    if _db_available is not None:
        return _prefs_repo, _cases_repo, _db_available
    
    try:
        from ..db import UserPreferencesRepository, UploadedCasesRepository
        _prefs_repo = UserPreferencesRepository()
        _cases_repo = UploadedCasesRepository()
        
        # Verify tables exist by doing a quick read
        _prefs_repo.get_favorites()
        _cases_repo.get_all()
        
        _db_available = True
        logger.info("Database persistence active - favorites, uploads, and recents will survive restarts")
    except Exception as e:
        err_str = str(e)
        if "Could not find the table" in err_str or "PGRST205" in err_str:
            logger.warning("Database tables not found. Using in-memory storage. "
                           "Run the SQL schema in Supabase to enable persistence.")
        else:
            logger.warning(f"Database not available, using in-memory storage: {e}")
        _db_available = False
    
    return _prefs_repo, _cases_repo, _db_available


def get_uploaded_case(case_id: str) -> Optional[Dict[str, Any]]:
    """Get an uploaded case by ID (database-backed)."""
    prefs_repo, cases_repo, db_available = _get_repos()
    
    if db_available and cases_repo:
        db_case = cases_repo.get(case_id)
        if db_case:
            # Sync to in-memory cache
            _uploaded_cases[case_id] = db_case
            return db_case
    
    return _uploaded_cases.get(case_id)


def save_uploaded_case(case_id: str, case_data: Dict[str, Any]) -> None:
    """Save or update an uploaded case (database-backed)."""
    prefs_repo, cases_repo, db_available = _get_repos()
    
    # Always update in-memory cache
    _uploaded_cases[case_id] = case_data
    
    # Persist to database
    if db_available and cases_repo:
        try:
            cases_repo.save(case_id, case_data)
            logger.debug(f"Saved case {case_id} to database")
        except Exception as e:
            logger.warning(f"Failed to persist case {case_id} to database: {e}")


def delete_uploaded_case(case_id: str) -> bool:
    """Delete an uploaded case (database-backed)."""
    prefs_repo, cases_repo, db_available = _get_repos()
    
    deleted = False
    
    # Remove from in-memory
    if case_id in _uploaded_cases:
        del _uploaded_cases[case_id]
        deleted = True
    
    # Remove from favorites (in-memory)
    _favorite_cases.discard(case_id)
    
    # Remove from database
    if db_available:
        if cases_repo:
            try:
                cases_repo.delete(case_id)
                deleted = True
            except Exception as e:
                logger.warning(f"Failed to delete case {case_id} from database: {e}")
        
        if prefs_repo:
            try:
                prefs_repo.remove_favorite(case_id)
            except Exception:
                pass
    
    return deleted


def get_all_uploaded_cases() -> List[Dict[str, Any]]:
    """Get metadata for all uploaded cases (database-backed)."""
    prefs_repo, cases_repo, db_available = _get_repos()
    
    # Get from database if available
    if db_available and cases_repo:
        try:
            db_cases = cases_repo.get_all()
            # Sync to in-memory cache
            for case in db_cases:
                _uploaded_cases[case["id"]] = case
        except Exception as e:
            logger.warning(f"Failed to fetch uploaded cases from database: {e}")
    
    favorites = set(get_favorite_cases())
    
    return [
        {
            "id": case_id,
            "title": data.get("title", "Untitled Case"),
            "case_type": data.get("case_type", "unknown"),
            "uploaded": True,
            "sections_complete": len(data.get("sections", {})),
            "total_sections": len(CASE_SECTIONS),
            "is_favorite": case_id in favorites,
        }
        for case_id, data in _uploaded_cases.items()
    ]


# =============================================================================
# FAVORITES AND RECENT ACCESS (DATABASE-BACKED)
# =============================================================================

def toggle_favorite(case_id: str) -> bool:
    """Toggle favorite status. Persists to database when available."""
    prefs_repo, _, db_available = _get_repos()
    
    # Always update in-memory
    if case_id in _favorite_cases:
        _favorite_cases.discard(case_id)
        new_status = False
    else:
        _favorite_cases.add(case_id)
        new_status = True
    
    # Persist to database
    if db_available and prefs_repo:
        try:
            if new_status:
                prefs_repo.add_favorite(case_id)
            else:
                prefs_repo.remove_favorite(case_id)
        except Exception as e:
            logger.warning(f"Failed to toggle favorite in database: {e}")
    
    return new_status


def set_favorite(case_id: str, favorite: bool) -> None:
    """Set favorite status. Persists to database when available."""
    prefs_repo, _, db_available = _get_repos()
    
    # Always update in-memory
    if favorite:
        _favorite_cases.add(case_id)
    else:
        _favorite_cases.discard(case_id)
    
    # Persist to database
    if db_available and prefs_repo:
        try:
            if favorite:
                prefs_repo.add_favorite(case_id)
            else:
                prefs_repo.remove_favorite(case_id)
        except Exception as e:
            logger.warning(f"Failed to set favorite in database: {e}")


def is_favorite(case_id: str) -> bool:
    """Check if a case is favorited. Uses database when available."""
    prefs_repo, _, db_available = _get_repos()
    
    if db_available and prefs_repo:
        try:
            result = prefs_repo.is_favorite(case_id)
            if result:
                _favorite_cases.add(case_id)
            else:
                _favorite_cases.discard(case_id)
            return result
        except Exception as e:
            logger.warning(f"Failed to check favorite in database: {e}")
    
    return case_id in _favorite_cases


def get_favorite_cases() -> List[str]:
    """Get list of favorited case IDs. Uses database when available."""
    prefs_repo, _, db_available = _get_repos()
    
    if db_available and prefs_repo:
        try:
            db_favorites = prefs_repo.get_favorites()
            _favorite_cases.clear()
            _favorite_cases.update(db_favorites)
            return db_favorites
        except Exception as e:
            logger.warning(f"Failed to get favorites from database: {e}")
    
    return list(_favorite_cases)


def record_case_access(case_id: str) -> None:
    """Record that a case was accessed. Persists to database when available."""
    global _recently_accessed
    prefs_repo, _, db_available = _get_repos()
    
    # Always update in-memory
    _recently_accessed = [r for r in _recently_accessed if r["case_id"] != case_id]
    _recently_accessed.insert(0, {
        "case_id": case_id,
        "accessed_at": datetime.utcnow().isoformat(),
    })
    _recently_accessed = _recently_accessed[:MAX_RECENT_CASES]
    
    # Persist to database
    if db_available and prefs_repo:
        try:
            prefs_repo.record_access(case_id)
        except Exception as e:
            logger.warning(f"Failed to record access in database: {e}")


def get_recently_accessed(limit: int = 5) -> List[Dict[str, Any]]:
    """Get recently accessed cases. Uses database when available."""
    prefs_repo, _, db_available = _get_repos()
    
    if db_available and prefs_repo:
        try:
            return prefs_repo.get_recent(limit)
        except Exception as e:
            logger.warning(f"Failed to get recent cases from database: {e}")
    
    return _recently_accessed[:limit]


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_all_demo_cases() -> List[Dict[str, Any]]:
    """
    Return all available case sources for listing.
    Merges MYLaw source metadata with uploaded case data.
    """
    # First, load uploaded cases from database into memory
    _, cases_repo, db_available = _get_repos()
    if db_available and cases_repo:
        try:
            db_cases = cases_repo.get_all()
            for case in db_cases:
                _uploaded_cases[case["id"]] = case
        except Exception as e:
            logger.warning(f"Failed to load uploaded cases from database: {e}")
    
    cases = []
    uploaded_ids = set(_uploaded_cases.keys())
    
    # Add all case sources, merging with uploaded data if available
    all_sources = AMTA_CASE_SOURCES + MYLAW_CASE_SOURCES
    for case in all_sources:
        case_id = case["id"]
        uploaded_data = _uploaded_cases.get(case_id)
        has_uploads = uploaded_data is not None and len(uploaded_data.get("sections", {})) > 0
        sections_count = len(uploaded_data.get("sections", {})) if uploaded_data else 0
        
        cases.append({
            "id": case_id,
            "title": case["title"],
            "description": case["description"],
            "year": case["year"],
            "difficulty": case.get("difficulty", "intermediate"),
            "case_type": case["case_type"],
            "source": case["source"],
            "source_url": case["source_url"],
            "requires_upload": not has_uploads,
            "has_uploads": has_uploads,
            "sections_uploaded": sections_count,
            "witness_count": len(uploaded_data.get("witnesses", [])) if uploaded_data else 0,
            "exhibit_count": len(uploaded_data.get("exhibits", [])) if uploaded_data else 0,
            "featured": case["year"] >= 2023,
            "popularity": max(50, 100 - (2025 - case["year"]) * 5),
            "is_favorite": is_favorite(case_id),
            "is_uploaded": has_uploads,
        })
    
    # Add user-uploaded cases that are NOT known sources
    mylaw_ids = {c["id"] for c in MYLAW_CASE_SOURCES}
    amta_ids = {c["id"] for c in AMTA_CASE_SOURCES}
    mylaw_ids.update(amta_ids)
    for case_id, data in _uploaded_cases.items():
        if case_id not in mylaw_ids:
            cases.append({
                "id": case_id,
                "title": data.get("title", "Uploaded Case"),
                "description": data.get("description", "User-uploaded case materials"),
                "year": data.get("year", 2024),
                "difficulty": data.get("difficulty", "intermediate"),
                "case_type": data.get("case_type", "civil"),
                "source": data.get("source", "User Upload"),
                "source_url": None,
                "requires_upload": False,
                "has_uploads": True,
                "sections_uploaded": len(data.get("sections", {})),
                "witness_count": len(data.get("witnesses", [])),
                "exhibit_count": len(data.get("exhibits", [])),
                "featured": is_favorite(case_id),
                "popularity": 80 if is_favorite(case_id) else 60,
                "is_favorite": is_favorite(case_id),
                "is_uploaded": True,
            })
    
    return cases


def get_demo_case_by_id(case_id: str) -> Optional[Dict[str, Any]]:
    """
    Get a specific case by ID.
    Returns case metadata for source cases, or full content for uploaded cases.
    """
    # Check uploaded cases first
    if case_id in _uploaded_cases:
        return _uploaded_cases[case_id]
    
    # Check all sources (AMTA + MYLaw)
    for case in AMTA_CASE_SOURCES + MYLAW_CASE_SOURCES:
        if case["id"] == case_id:
            return {
                **case,
                "witnesses": [],
                "exhibits": [],
                "facts": [],
                "stipulations": [],
                "legal_standards": [],
                "message": "This case requires upload. Download from the source URL and upload the case materials.",
            }
    
    return None


def get_demo_case_ids() -> List[str]:
    """Get list of all case IDs."""
    ids = [case["id"] for case in AMTA_CASE_SOURCES]
    ids.extend(case["id"] for case in MYLAW_CASE_SOURCES)
    ids.extend(_uploaded_cases.keys())
    return ids


def get_featured_demo_cases(limit: int = 3) -> List[Dict[str, Any]]:
    """Get top featured cases for homepage display."""
    all_cases = get_all_demo_cases()
    featured = [c for c in all_cases if c.get("featured", False)]
    sorted_cases = sorted(featured, key=lambda x: x.get("year", 0), reverse=True)
    return sorted_cases[:limit]


def get_case_sections() -> List[Dict[str, Any]]:
    """Get the list of case sections for upload organization."""
    return CASE_SECTIONS
