"""Unit tests for the guarded duplicate-matching rule and the merge log."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.services.fast_dedup import fast_deduplicate_leads  # noqa: E402
from app.services.match_rules import fuzzy_match  # noqa: E402
from evaluate_dedup import metrics, new_rule_pairs, prepared_leads, true_pairs  # noqa: E402


def lead(first, last, company, email, phone=None, row=2):
    return {"first_name": first, "last_name": last, "company": company, "email": email, "phone": phone,
            "row_index": row, "is_junk": False}


def test_different_people_at_same_company_never_merge():
    a = lead("Katherine", "Thomas", "OmniChannel Media", "katherine.thomas@omnichannelmedia.com")
    b = lead("Katherine", "Wilson", "OmniChannel Media", "katherine.wilson@omnichannelmedia.com")
    assert fuzzy_match(a, b, 75.0)[0] is False
    c = lead("Rowan", "Martin", "DataPulse Systems", "rowan.martin@datapulsesystems.com")
    d = lead("Rowan", "Brown", "DataPulse Systems", "rowan.brown@datapulsesystems.com")
    assert fuzzy_match(c, d, 75.0)[0] is False
    e = lead("Jordan", "Smith", "Acme Corp", "jordan.smith@acmecorp.com")
    f = lead("Morgan", "Smith", "Acme Corp", "morgan.smith@acmecorp.com")
    assert fuzzy_match(e, f, 75.0)[0] is False  # same last name, different first name


def test_fuzzy_path_catches_typos_without_shared_identifiers():
    a = lead("Jonathan", "Smith", "Acme Corp", "jonathan.smith@acmecorp.com", row=2)
    b = lead("Jonathon", "Smith", "Acme Corporation", "jonathon.smith@acmecorp.com", row=3)
    ok, score, reason = fuzzy_match(a, b, 85.0)
    assert ok and score >= 85.0 and "Same last name" in reason
    winners, logs, stats = fast_deduplicate_leads([a, b], "unit", threshold=85.0)
    assert stats["duplicates_merged"] == 1 and len(winners) == 1
    assert logs[0]["merge_reason"].startswith("Fuzzy match") and logs[0]["similarity_score"] == score


def test_merge_log_ids_are_consistent():
    leads = [lead("Ana", "Lopez", "Apex", "ana@apex.com", row=10), lead("Ana", "Lopez", "Apex", "ana@apex.com", row=11),
             lead("Ana", "Lopez", "Apex", "ana@apex.com", row=12)]
    _, logs, _ = fast_deduplicate_leads(leads, "unit", threshold=85.0)
    assert len(logs) == 2
    for m in logs:
        assert m["id_type"] == "csv_row"
        assert m["winner_raw_lead_id"] != m["archived_raw_lead_id"]  # never "merged into itself"
        assert m["similarity_score"] == 100.0 and m["merge_reason"].startswith("Exact match on email")


def test_generator_ground_truth_and_accuracy():
    leads = prepared_leads()
    truth = true_pairs(leads)
    assert len(leads) == 200 and len(truth) == 20
    pred, logs = new_rule_pairs(leads, 85.0)
    tp, fp, fn, precision, recall = metrics(pred, truth)
    assert (tp, fp, fn) == (20, 0, 0)
    assert len(logs) == 20
