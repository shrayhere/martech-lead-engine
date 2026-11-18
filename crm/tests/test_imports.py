import pytest

from app.extensions import db
from app.models import Company, Contact, DuplicateRecord, ImportJob, LeadActivity, SyncLog
from tests.conftest import register, run_import, upload


def contact_by_email(email):
    return Contact.query.filter_by(email=email).one()


def test_first_import_cleans_and_reports(auth):
    resp, up = run_import(auth, "01_first_import.csv", "upsert")
    assert resp.status_code == 201, resp.get_json()
    s = resp.get_json()["summary"]
    assert up["job"]["total_rows"] == 19  # blank line skipped
    assert s["total_processed"] == 19
    assert s["invalid"] == 3  # bad email, missing identifiers, bad activity date
    assert s["duplicates"] == 1  # Ritika repeated in the file
    assert s["inserted"] == 15
    # cleaning
    ritika = contact_by_email("ritika.malhotra@technova.io")
    assert ritika.first_name == "Ritika" and ritika.phone == "+14155550101"
    assert ritika.company.company_name == "TechNova Inc." and ritika.company.country == "United States"
    assert ritika.activities.count() == 2  # in-file repeat folded its activity in
    assert ritika.lead_score == 55 and ritika.lead_category == "warm"
    # one company per normalised name -> relational association, no repeated company text
    assert Company.query.filter_by(name_key="technova").count() == 1
    assert contact_by_email("arnav.kapoor@technova.io").company_id == ritika.company_id
    assert Company.query.filter_by(name_key="finedge").count() == 1
    assert contact_by_email("meghna.iyer@finedge.in").company.city == "Bengaluru"
    # Fatima has no email but a valid phone -> imported and qualifiable
    fatima = Contact.query.filter_by(first_name="Fatima").one()
    assert fatima.phone == "+97145550123" and fatima.lead_category is not None
    # sync log + reports
    job = db.session.get(ImportJob, up["job"]["import_id"])
    assert job.import_status == "completed" and job.failed_rows == 3 and job.inserted_rows == 15
    assert SyncLog.query.filter_by(import_id=job.import_id).one().records_inserted == 15
    errors = auth.get(f"/api/imports/{job.import_id}/errors")
    assert errors.status_code == 200
    text = errors.get_data(as_text=True)
    assert "Invalid email format" in text and "Missing contact identifier" in text
    assert auth.get(f"/api/imports/{job.import_id}/report?download=success").status_code == 200
    assert auth.get(f"/api/imports/{job.import_id}/report?download=duplicates").status_code == 200
    assert auth.get("/api/imports/history").get_json()["total"] == 1
    # cannot execute the same job twice
    again = auth.post("/api/imports/execute", json={"import_id": job.import_id, "mapping": up["suggested_mapping"],
                                                    "mode": "upsert"})
    assert again.status_code == 409


def test_dry_run_changes_nothing(auth):
    resp, up = run_import(auth, "01_first_import.csv", "upsert", dry_run=True)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["dry_run"] and data["summary"]["inserted"] == 15
    assert Contact.query.count() == 0 and Company.query.count() == 0 and LeadActivity.query.count() == 0
    assert data["job"]["import_status"] == "previewed"
    assert any(r["action"] == "failed" for r in data["rows"])


def test_insert_only_skips_existing(auth):
    run_import(auth, "01_first_import.csv", "upsert")
    before = contact_by_email("grace.lee@medicore.com").job_title
    resp, _ = run_import(auth, "02_second_import_updates.csv", "insert_only")
    s = resp.get_json()["summary"]
    assert s["updated"] == 0
    assert s["inserted"] == 3  # Priyanka, Marco, Ethan
    assert contact_by_email("grace.lee@medicore.com").job_title == before


def test_update_existing_preserves_blank_fields(auth):
    run_import(auth, "01_first_import.csv", "upsert")
    phone_before = contact_by_email("ritika.malhotra@technova.io").phone
    count_before = Contact.query.count()
    resp, _ = run_import(auth, "02_second_import_updates.csv", "update_existing")
    s = resp.get_json()["summary"]
    assert s["inserted"] == 0 and Contact.query.count() == count_before
    assert s["updated"] == 3  # Ritika, Grace, Tom
    ritika = contact_by_email("ritika.malhotra@technova.io")
    assert ritika.job_title == "Chief Marketing Officer"
    assert ritika.phone == phone_before  # blank incoming phone kept existing value
    assert ritika.lead_category == "hot"  # pricing inquiry recalculated the score
    tom = contact_by_email("tom.becker@alpinelogix.de")
    assert tom.company.company_name == "Alpine Logix GmbH"  # blank company did not unlink


def test_upsert_and_duplicate_review(auth):
    run_import(auth, "01_first_import.csv", "upsert")
    resp, up = run_import(auth, "02_second_import_updates.csv", "upsert")
    s = resp.get_json()["summary"]
    assert s["inserted"] == 3 and s["updated"] == 3 and s["invalid"] == 1
    assert s["needs_review"] == 3  # Kabir (name+company), Gracie (phone), Daniel (name+company)
    pending = auth.get("/api/duplicates").get_json()
    assert pending["total"] == 3
    items = {i["incoming"]["email"]: i for i in pending["items"]}
    gracie = items["gracie.lee@gmail.com"]
    assert gracie["matching_reason"].startswith("Same phone") and gracie["differences"]
    assert gracie["recommended_action"] in ("merge", "update_existing", "keep_existing")

    # Keep existing: nothing changes
    r = auth.post(f"/api/duplicates/{gracie['duplicate_id']}/resolve", json={"action": "keep_existing"})
    assert r.status_code == 200
    assert Contact.query.filter_by(email="gracie.lee@gmail.com").count() == 0
    # Merge: fills blanks only
    kabir = items["kabir.s@cloudnine.ai"]
    r = auth.post(f"/api/duplicates/{kabir['duplicate_id']}/resolve", json={"action": "merge"})
    k = contact_by_email("kabir.shah@cloudnine.ai")
    assert k.job_title == "Data Scientist"  # existing value kept
    # Update existing: overwrites with incoming values
    daniel = items["d.owusu@medicore-health.com"]
    auth.post(f"/api/duplicates/{daniel['duplicate_id']}/resolve", json={"action": "update_existing"})
    assert Contact.query.filter_by(email="d.owusu@medicore-health.com").count() == 1
    # already resolved
    again = auth.post(f"/api/duplicates/{daniel['duplicate_id']}/resolve", json={"action": "merge"})
    assert again.status_code == 409
    assert auth.get("/api/duplicates").get_json()["total"] == 0


def test_not_duplicate_creates_contact(auth):
    run_import(auth, "01_first_import.csv", "upsert")
    run_import(auth, "02_second_import_updates.csv", "upsert")
    dup = DuplicateRecord.query.filter(DuplicateRecord.incoming_data.like("%gracie.lee%")).one()
    r = auth.post(f"/api/duplicates/{dup.duplicate_id}/resolve", json={"action": "not_duplicate"})
    assert r.status_code == 200 and r.get_json()["result"]["created_contact_id"]
    assert contact_by_email("gracie.lee@gmail.com")


def test_scan_existing_duplicates_and_merge_contacts(auth):
    a = auth.post("/api/contacts", json={"first_name": "Jon", "last_name": "Smith", "email": "jon@a.com",
                                         "phone": "415-555-0199", "job_title": "CEO"}).get_json()["contact"]
    b = auth.post("/api/contacts", json={"first_name": "Jon", "last_name": "Smith", "email": "jsmith@b.com",
                                         "phone": "+1 415 555 0199"}).get_json()["contact"]
    auth.post(f"/api/contacts/{b['contact_id']}/activities", json={"activity_type": "demo_requested"})
    r = auth.post("/api/duplicates/scan")
    assert r.get_json()["created"] == 1
    assert auth.post("/api/duplicates/scan").get_json()["created"] == 0  # not re-flagged
    dup = auth.get("/api/duplicates").get_json()["items"][0]
    assert dup["confidence_score"] == 0.95
    auth.post(f"/api/duplicates/{dup['duplicate_id']}/resolve", json={"action": "merge"})
    assert Contact.query.count() == 1
    merged = db.session.get(Contact, a["contact_id"])
    assert merged.activities.count() == 1 and merged.lead_score == 40  # history moved, score recalculated


def test_semicolon_latin1_different_columns(auth):
    resp, up = run_import(auth, "03_different_columns_semicolon_latin1.csv", "upsert")
    assert up["job"]["encoding"] == "cp1252" and up["delimiter_label"] == "semicolon"
    assert up["suggested_mapping"]["Organization"] == "company_name"
    assert up["suggested_mapping"]["Designation"] == "job_title"
    assert resp.get_json()["summary"]["inserted"] == 5
    jose = contact_by_email("jose.alvarez@iberiasoft.es")
    assert jose.first_name == "José" and jose.last_name == "Álvarez"
    assert contact_by_email("rahul.sharma@google.com").first_name == "Rahul"


def test_activity_import_recalculates_scores(auth):
    run_import(auth, "01_first_import.csv", "upsert")
    assert contact_by_email("grace.lee@medicore.com").lead_category == "cold"
    resp, _ = run_import(auth, "04_activity_updates.csv", "update_existing")
    s = resp.get_json()["summary"]
    # Grace appears twice: the second row is folded into the first as an in-file duplicate.
    assert s["updated"] == 3 and s["duplicates"] == 1 and s["skipped"] == 1 and s["activities_added"] == 4
    grace = contact_by_email("grace.lee@medicore.com")
    assert grace.lead_score == 75 and grace.lead_category == "hot"


def test_import_rollback_on_failure(auth, monkeypatch):
    from app.services import sync_engine
    original = sync_engine._Run.insert
    calls = {"n": 0}

    def boom(self, *args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 5:
            raise RuntimeError("simulated crash mid-import")
        return original(self, *args, **kwargs)

    monkeypatch.setattr(sync_engine._Run, "insert", boom)
    resp, up = run_import(auth, "01_first_import.csv", "upsert")
    assert resp.status_code == 500 and "rolled back" in resp.get_json()["error"]
    assert Contact.query.count() == 0 and Company.query.count() == 0  # nothing partially written
    job = db.session.get(ImportJob, up["job"]["import_id"])
    assert job.import_status == "rolled_back"
    assert SyncLog.query.filter_by(import_id=job.import_id).one().sync_status == "rolled_back"


def test_concurrent_import_rejected(auth):
    first = upload(auth, "01_first_import.csv").get_json()
    job = db.session.get(ImportJob, first["job"]["import_id"])
    from app.models.base import utcnow
    job.import_status, job.started_at = "processing", utcnow()
    db.session.commit()
    resp, _ = run_import(auth, "02_second_import_updates.csv", "upsert")
    assert resp.status_code == 409 and "still running" in resp.get_json()["error"]


def test_bad_mapping_rejected(auth):
    up = upload(auth, "01_first_import.csv").get_json()
    r = auth.post("/api/imports/preview", json={"import_id": up["job"]["import_id"],
                                               "mapping": {"company": "company_name"}, "mode": "upsert"})
    assert r.status_code == 422 and "identifier" in r.get_json()["details"]
    r = auth.post("/api/imports/preview", json={"import_id": up["job"]["import_id"],
                                               "mapping": up["suggested_mapping"], "mode": "replace_all"})
    assert r.status_code == 400


def test_data_isolation_between_users(client):
    register(client, "owner@example.com")
    resp, up = run_import(client, "01_first_import.csv", "upsert")
    cid = Contact.query.first().contact_id
    company_id = Company.query.first().company_id
    client.post("/api/auth/logout")
    register(client, "intruder@example.com")
    assert client.get("/api/contacts").get_json()["total"] == 0
    assert client.get("/api/companies").get_json()["total"] == 0
    assert client.get(f"/api/contacts/{cid}").status_code == 404
    assert client.put(f"/api/contacts/{cid}", json={"first_name": "Hacked"}).status_code == 404
    assert client.delete(f"/api/companies/{company_id}").status_code == 404
    assert client.get(f"/api/imports/{up['job']['import_id']}/report").status_code == 404
    assert client.get("/api/imports/history").get_json()["total"] == 0
    assert client.get("/api/dashboard/stats").get_json()["stats"]["total_contacts"] == 0
    assert client.get("/api/search?q=ritika").get_json()["contacts"] == []
    # the intruder can create the same email in their own workspace
    assert client.post("/api/contacts", json={"first_name": "R", "email": "ritika.malhotra@technova.io"}).status_code == 201
