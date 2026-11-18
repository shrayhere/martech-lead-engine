"""Title seniority tiers used by lead scoring (whole-word keyword matching)."""
import os
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.scoring_service import classify_seniority  # noqa: E402


@pytest.mark.parametrize("title,tier", [
    ("Director of IT", 80),             # "dire-cto-r" used to match the CTO keyword
    ("Director of Marketing", 80),
    ("Vice President of Sales", 80),    # "president" alone is C-level, "vice president" is not
    ("VP, Sales", 80),
    ("Head of Growth", 80),
    ("CTO", 100),
    ("Chief Executive Officer", 100),
    ("CEO & Co-Founder", 100),
    ("President", 100),
    ("SVP Marketing", 100),
    ("Senior Demand Generation Manager", 50),
    ("Sr. Software Engineer", 50),
    ("Account Executive", 25),
    ("Microsoft Specialist", 25),       # "micro" contains "cro"
    ("", 25),
])
def test_seniority_tiers(title, tier):
    assert classify_seniority(title)[0] == tier
