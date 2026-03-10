"""
Data module for AI Mock Trial.

Contains case source metadata for official mock trial cases.
Actual case content must be downloaded by users from source websites.
"""

from .demo_cases import (
    AMTA_CASE_SOURCES,
    MYLAW_CASE_SOURCES,
    CASE_SECTIONS,
    get_all_demo_cases,
    get_demo_case_by_id,
    get_demo_case_ids,
    get_featured_demo_cases,
    get_case_sections,
    get_uploaded_case,
    save_uploaded_case,
    delete_uploaded_case,
    get_all_uploaded_cases,
    get_case_source_by_id,
    hide_case,
    unhide_case,
    is_case_hidden,
    toggle_favorite,
    set_favorite,
    is_favorite,
    get_favorite_cases,
    record_case_access,
    get_recently_accessed,
)

__all__ = [
    "AMTA_CASE_SOURCES",
    "MYLAW_CASE_SOURCES",
    "CASE_SECTIONS",
    "get_all_demo_cases",
    "get_demo_case_by_id",
    "get_demo_case_ids",
    "get_featured_demo_cases",
    "get_case_sections",
    "get_uploaded_case",
    "save_uploaded_case",
    "delete_uploaded_case",
    "get_all_uploaded_cases",
    "get_case_source_by_id",
    "hide_case",
    "unhide_case",
    "is_case_hidden",
    "toggle_favorite",
    "set_favorite",
    "is_favorite",
    "get_favorite_cases",
    "record_case_access",
    "get_recently_accessed",
]
