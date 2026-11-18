from datetime import timedelta

from app.cli import seed_user
from app.extensions import db
from app.models import Contact, User
from app.models.base import utcnow
from tests.conftest import run_import


def test_dashboard_stats_match_database(auth):
    user = User.query.one()
    seed_user(user)
    db.session.commit()
    stats = auth.get("/api/dashboard/stats").get_json()["stats"]
    contacts = Contact.query.all()
    assert stats["total_contacts"] == len(contacts) == 36
    assert stats["total_companies"] == 12
    leads = [c for c in contacts if c.is_lead and c.effective_category]
    assert stats["total_leads"] == len(leads)
    for cat in ("hot", "warm", "cold"):
        assert stats[f"{cat}_leads"] == sum(1 for c in leads if c.effective_category == cat)
    assert stats["hot_leads"] > 0 and stats["warm_leads"] > 0 and stats["cold_leads"] > 0
    assert stats["hot_leads"] + stats["warm_leads"] + stats["cold_leads"] == stats["total_leads"]


def test_dashboard_reacts_to_imports_and_ranges(auth):
    before = auth.get("/api/dashboard/stats").get_json()["stats"]
    assert before["total_contacts"] == 0 and before["imports_completed"] == 0
    run_import(auth, "01_first_import.csv", "upsert")
    after = auth.get("/api/dashboard/stats?range=7d").get_json()["stats"]
    assert after["total_contacts"] == 15 and after["imports_completed"] == 1
    # Move one contact far into the past: it leaves the 30-day window but stays in "all"
    c = Contact.query.first()
    c.created_at = utcnow() - timedelta(days=200)
    db.session.commit()
    assert auth.get("/api/dashboard/stats?range=30d").get_json()["stats"]["total_contacts"] == 14
    assert auth.get("/api/dashboard/stats?range=all").get_json()["stats"]["total_contacts"] == 15
    start = (utcnow() - timedelta(days=250)).date().isoformat()
    end = (utcnow() - timedelta(days=150)).date().isoformat()
    custom = auth.get(f"/api/dashboard/stats?range=custom&start={start}&end={end}").get_json()["stats"]
    assert custom["total_contacts"] == 1
    assert auth.get("/api/dashboard/stats?range=custom").status_code == 400


def test_chart_data(auth):
    seed_user(User.query.one())
    db.session.commit()
    charts = auth.get("/api/dashboard/charts?range=90d").get_json()
    dist = charts["lead_distribution"]
    stats = auth.get("/api/dashboard/stats?range=90d").get_json()["stats"]
    assert dist["hot"] == stats["hot_leads"] and dist["cold"] == stats["cold_leads"]
    assert sum(charts["leads_over_time"]["total"]) == stats["total_leads"] + sum(
        1 for c in Contact.query if c.is_lead and c.effective_category is None)
    assert charts["contacts_by_company"]["labels"][0] == "Google"
    assert sum(charts["lead_sources"]["values"]) == 36
    assert [f["stage"] for f in charts["funnel"]][0] == "subscriber"
    assert charts["funnel"][0]["reached"] >= charts["funnel"][-1]["reached"]
    summary = auth.get("/api/reports/summary?range=all").get_json()
    assert summary["activities"] and summary["industries"]
    analytics = auth.get("/api/leads/analytics").get_json()
    assert analytics["total_leads"] > 0
    dq = auth.get("/api/data-quality").get_json()
    assert dq["total_contacts"] == 36 and dq["sources"]
