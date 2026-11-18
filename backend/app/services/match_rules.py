"""Shared duplicate-matching rules used by both deduplication paths.

A pair of leads is only treated as the same person when:
  1. the normalised email addresses are identical (exact match), or
  2. the normalised phone numbers are identical (exact match), or
  3. a guarded fuzzy match passes ALL of:
       - identical normalised last name,
       - first names at least FIRST_NAME_MIN_SIMILARITY similar (catches "Jonathan"/"Jonathon"),
       - same company (after removing legal suffixes) or the same non-generic email domain,
       - composite "first last | company | email" token_sort_ratio >= threshold.

The composite score alone is NOT enough: two different people at the same company share most of
that string ("Katherine Thomas | OmniChannel Media" vs "Katherine Wilson | OmniChannel Media" scores ~85),
so the name guards above are required before a fuzzy match can merge records.
"""
import re
from typing import Any, Dict, Optional, Tuple

from rapidfuzz import fuzz

FIRST_NAME_MIN_SIMILARITY = 85.0
REVIEW_BAND = (80.0, 90.0)  # composite scores in this range are reported as borderline

GENERIC_DOMAINS = {
    "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com",
    "aol.com", "proton.me", "protonmail.com", "mail.com", "zoho.com",
}
COMPANY_SUFFIXES = {
    "inc", "incorporated", "corp", "corporation", "llc", "ltd", "limited", "co", "company",
    "plc", "gmbh", "pvt", "private", "group", "holdings",
}


def norm_name(value: Optional[str]) -> str:
    return re.sub(r"[^a-z]", "", (value or "").lower())


def company_key(value: Optional[str]) -> str:
    words = re.sub(r"[^a-z0-9 ]+", " ", (value or "").lower()).split()
    while len(words) > 1 and words[-1] in COMPANY_SUFFIXES:
        words.pop()
    return " ".join(words)


def email_domain(email: Optional[str]) -> str:
    if not email or "@" not in email:
        return ""
    domain = email.rsplit("@", 1)[1].strip().lower()
    return "" if domain in GENERIC_DOMAINS else domain


def composite_string(lead: Dict[str, Any]) -> str:
    return (f"{lead.get('first_name') or ''} {lead.get('last_name') or ''} | "
            f"{lead.get('company') or ''} | {lead.get('email') or ''}").lower()


def fuzzy_match(a: Dict[str, Any], b: Dict[str, Any], threshold: float,
                composite_a: Optional[str] = None, composite_b: Optional[str] = None
                ) -> Tuple[bool, float, str]:
    """Return (is_match, composite_score, reason)."""
    last_a, last_b = norm_name(a.get("last_name")), norm_name(b.get("last_name"))
    if not last_a or not last_b or last_a != last_b:
        return False, 0.0, "Different last names"
    first_a, first_b = norm_name(a.get("first_name")), norm_name(b.get("first_name"))
    if not first_a or not first_b:
        return False, 0.0, "Missing first name"
    first_sim = fuzz.ratio(first_a, first_b)
    if first_sim < FIRST_NAME_MIN_SIMILARITY:
        return False, 0.0, f"First names differ ({first_sim:.0f}%)"
    same_company = bool(company_key(a.get("company"))) and company_key(a.get("company")) == company_key(b.get("company"))
    same_domain = bool(email_domain(a.get("email"))) and email_domain(a.get("email")) == email_domain(b.get("email"))
    if not (same_company or same_domain):
        return False, 0.0, "Different company and email domain"
    score = round(float(fuzz.token_sort_ratio(composite_a or composite_string(a), composite_b or composite_string(b))), 1)
    if score < threshold:
        return False, score, f"Composite similarity {score}% below {threshold}%"
    basis = "same company" if same_company else "same email domain"
    return True, score, (f"Same last name, first name {first_sim:.0f}% similar, {basis}; "
                         f"composite similarity {score}% (threshold {threshold}%)")
