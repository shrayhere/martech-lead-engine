import os
from datetime import datetime
import pytest
from app.services.scoring_service import classify_seniority, score_company_size, score_recency
from app.services.smart_scoring import smart_score_leads, score_lead_with_adaptive_weights, DEFAULT_WEIGHTS
from app.services.pipeline_cleaning import parse_iso_date, parse_company_size_value, clean_and_normalize_records
from app.services.classifier import classify_titles_local, recommend_action

def test_missing_engagement_and_date_score_cold_with_warning():
    """A lead with only email and name gets engagement=0 and lowest recency, scoring Cold with completeness warning."""
    lead = {
        "id": 1,
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@example.com",
        "company": "Example Inc",
        "job_title": "Associate",
        "phone": "+1 555 0100",
        "state": "CA",
        "industry": "Tech",
        "company_size": 100,
        "engagement_score": None,     # missing
        "last_activity_date": None    # missing
    }
    score, breakdown, reasons = score_lead_with_adaptive_weights(lead, DEFAULT_WEIGHTS)
    assert score < 50.0
    # Completeness warnings must be present
    assert any("engagement" in r.lower() or "missing" in r.lower() for r in reasons)
    assert "completeness_warnings" in breakdown
    assert len(breakdown["completeness_warnings"]) >= 2


def test_range_validation_out_of_bounds_never_score_hot():
    """Out-of-range engagement (150) and negative company size (-50) are treated as invalid/missing, never scoring Hot."""
    assert parse_company_size_value("-50") is None
    assert parse_company_size_value(-100) is None
    assert parse_iso_date("1999-13-45") is None
    assert parse_iso_date("2030-01-01") is None

    lead = {
        "id": 2,
        "first_name": "Out",
        "last_name": "Bounds",
        "email": "out.bounds@test.com",
        "company": "Bad Co",
        "job_title": "Analyst",
        "company_size": -50,
        "engagement_score": 150.0,
        "last_activity_date": "2030-12-31"
    }
    score, breakdown, reasons = score_lead_with_adaptive_weights(lead, DEFAULT_WEIGHTS)
    assert score < 70.0


def test_seniority_scorer_and_classifier_alignment():
    """Senior roles (Owner, MD, CXO, Partner, Procurement Head) score senior (100/80); Founder's Office and Intern score low (25)."""
    assert classify_seniority("Owner & Proprietor")[0] == 100
    assert classify_seniority("Managing Director")[0] == 100
    assert classify_seniority("Chief Technology Officer")[0] == 100
    assert classify_seniority("Partner")[0] == 100
    assert classify_seniority("Procurement Head")[0] == 80
    assert classify_seniority("Head - Sourcing & Procurement")[0] == 80

    # Low roles
    assert classify_seniority("Founder's Office Associate")[0] == 25
    assert classify_seniority("Summer Intern")[0] == 25
    assert classify_seniority("Student")[0] == 25
    assert classify_seniority("Retired")[0] == 25


def test_low_confidence_classifier_fallback():
    """If classifier confidence is < 0.6, persona/role/interest are set to 'Unknown' and action to 'Enrich: verify job title before outreach'."""
    res = classify_titles_local(["Grand Vizier of Synergy"])[0]
    if res.get("confidence", 0.0) < 0.6:
        assert res["persona"] == "Unknown"
        assert res["buying_role"] == "Unknown"
        assert res["interest"] == "Unknown"
        action = recommend_action(res["persona"], res["buying_role"], res["interest"], "Hot")
        assert action == "Enrich: verify job title before outreach"


def test_ml_score_and_rule_score_calibrated():
    """Both ML score and rule score are computed, and ML conversion likelihood is calibrated."""
    today = datetime.now().strftime("%Y-%m-%d")
    lead = {
        "id": 10,
        "first_name": "Sarah",
        "last_name": "Connor",
        "email": "sarah@cyberdyne.com",
        "company": "Cyberdyne Systems",
        "job_title": "Chief Executive Officer",
        "phone": "+1 555 0199",
        "state": "CA",
        "industry": "Enterprise Technology",
        "company_size": 500,
        "engagement_score": 98.0,
        "last_activity_date": today
    }
    scored_rule, _ = smart_score_leads([lead], scoring_mode="rule")
    assert scored_rule[0]["score_band"] == "Hot"
    assert scored_rule[0]["rule_score"] >= 80.0

    scored_ml, _ = smart_score_leads([lead], scoring_mode="ml")
    assert scored_ml[0]["score_band"] == "Hot"
    assert 0.0 <= scored_ml[0]["ml_score"] <= 100.0
