from app.models import AuditLog, Contact


def make_company(client, name="Google", **extra):
    resp = client.post("/api/companies", json={"company_name": name, **extra})
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["company"]


def make_contact(client, **fields):
    payload = {"first_name": "Test", **fields}
    resp = client.post("/api/contacts", json=payload)
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()["contact"]


def test_company_crud_and_duplicate_names(auth):
    c = make_company(auth, "Acme Corp", industry="saas", website="WWW.Acme.com/", country="usa",
                     employee_count="1,200", annual_revenue="$5M")
    assert c["industry"] == "SaaS" and c["website"] == "https://www.acme.com"
    assert c["country"] == "United States" and c["employee_count"] == 1200 and c["annual_revenue"] == 5_000_000
    assert auth.post("/api/companies", json={"company_name": "ACME Corporation"}).status_code == 409
    resp = auth.put(f"/api/companies/{c['company_id']}", json={"city": "pune", "description": "Updated"})
    assert resp.status_code == 200 and resp.get_json()["company"]["city"] == "Pune"
    assert auth.post("/api/companies", json={"company_name": ""}).status_code == 422
    assert AuditLog.query.filter_by(entity_type="company", operation="update").count() == 1


def test_contact_crud_validation(auth):
    contact = make_contact(auth, first_name="  rahul ", last_name="SHARMA", email="Rahul@Example.COM",
                           phone="(415) 555-0101", job_title="Marketing Manager")
    assert contact["first_name"] == "Rahul" and contact["last_name"] == "Sharma"
    assert contact["email"] == "rahul@example.com" and contact["phone"] == "+14155550101"
    cid = contact["contact_id"]
    assert auth.post("/api/contacts", json={"first_name": "X", "email": "rahul@example.com"}).status_code == 409
    bad = auth.post("/api/contacts", json={"first_name": "", "email": "not-an-email"})
    assert bad.status_code == 422 and {"first_name", "email"} <= set(bad.get_json()["details"])
    resp = auth.put(f"/api/contacts/{cid}", json={"job_title": "VP Marketing", "lifecycle_stage": "mql"})
    assert resp.status_code == 200 and resp.get_json()["contact"]["lifecycle_stage"] == "mql"
    detail = auth.get(f"/api/contacts/{cid}").get_json()
    assert detail["recommended_next_action"] and detail["history"]
    assert auth.delete(f"/api/contacts/{cid}").status_code == 200
    assert auth.get(f"/api/contacts/{cid}").status_code == 404


def test_company_contact_relationships(auth):
    google = make_company(auth, "Google")
    for first, title in (("Rahul", "Marketing Manager"), ("Aman", "Sales Executive"), ("Priya", "HR Manager")):
        make_contact(auth, first_name=first, email=f"{first.lower()}@google.com", job_title=title,
                     company_id=google["company_id"])
    loner = make_contact(auth, first_name="Solo", email="solo@example.com")
    assert loner["company"] is None

    detail = auth.get(f"/api/companies/{google['company_id']}").get_json()
    assert detail["company"]["contact_count"] == 3
    assert {c["company_id"] for c in detail["contacts"]} == {google["company_id"]}
    assert len({c.company_id for c in Contact.query.filter(Contact.company_id.isnot(None))}) == 1

    c = make_contact(auth, first_name="Neha", email="neha@infosys.com", new_company={"company_name": "Infosys"})
    assert c["company"]["company_name"] == "Infosys"
    resp = auth.put(f"/api/contacts/{c['contact_id']}", json={"company_id": google["company_id"]})
    assert resp.get_json()["contact"]["company"]["company_name"] == "Google"
    assert auth.get(f"/api/contacts?company_id={google['company_id']}").get_json()["total"] == 4
    assert auth.get("/api/contacts?no_company=1").get_json()["total"] == 1
    empty = auth.get("/api/companies?has_contacts=0").get_json()
    assert [i["company_name"] for i in empty["items"]] == ["Infosys"]
    resp = auth.delete(f"/api/companies/{google['company_id']}")
    assert resp.get_json()["contacts_unassigned"] == 4
    assert auth.get("/api/contacts?no_company=1").get_json()["total"] == 5
    assert auth.put(f"/api/contacts/{c['contact_id']}", json={"company_id": 9999}).status_code == 404


def test_search_filter_sort_paginate(auth):
    acme = make_company(auth, "Acme Analytics")
    for i in range(30):
        make_contact(auth, first_name=f"Person{i:02d}", last_name="Tester", email=f"p{i}@acme.io",
                     phone=f"+1415555{i:04d}", company_id=acme["company_id"] if i % 2 else None,
                     lead_source="Webinar" if i % 3 == 0 else "Website")
    page1 = auth.get("/api/contacts?per_page=10&page=1&sort=name&order=asc").get_json()
    assert page1["total"] == 30 and page1["pages"] == 3 and len(page1["items"]) == 10
    assert page1["items"][0]["first_name"] == "Person00"
    page3 = auth.get("/api/contacts?per_page=10&page=3&sort=name&order=asc").get_json()
    assert page3["items"][-1]["first_name"] == "Person29"
    assert auth.get("/api/contacts?q=PERSON1").get_json()["total"] == 10  # Person10..Person19
    assert auth.get("/api/contacts?q=p7@acme").get_json()["total"] == 1
    assert auth.get("/api/contacts?q=555-0012").get_json()["total"] == 1
    assert auth.get("/api/contacts?q=acme analytics").get_json()["total"] == 15
    assert auth.get("/api/contacts?lead_source=Webinar").get_json()["total"] == 10
    assert auth.get("/api/contacts?category=cold").get_json()["total"] == 30
    assert auth.get("/api/contacts?score_min=50").get_json()["total"] == 0
    assert auth.get("/api/contacts?sort=bogus").status_code == 400
    search = auth.get("/api/search?q=acme").get_json()
    assert search["companies"][0]["company_name"] == "Acme Analytics" and search["contacts"]
    companies = auth.get("/api/companies?q=analytics").get_json()
    assert companies["items"][0]["contact_count"] == 15


def test_bulk_actions_and_export(auth):
    ids = [make_contact(auth, first_name=f"B{i}", email=f"b{i}@x.com")["contact_id"] for i in range(3)]
    resp = auth.post("/api/contacts/bulk", json={"ids": ids, "action": "set_category", "value": "hot"})
    assert resp.status_code == 200
    assert auth.get("/api/contacts?category=hot").get_json()["total"] == 3
    item = auth.get(f"/api/contacts/{ids[0]}").get_json()["contact"]
    assert item["lead_category_auto"] == "cold" and item["lead_category_override"] == "hot"
    assert AuditLog.query.filter_by(operation="category_override").count() == 3
    auth.post("/api/contacts/bulk", json={"ids": ids, "action": "clear_override"})
    assert auth.get("/api/contacts?category=hot").get_json()["total"] == 0
    export = auth.get("/api/contacts/export")
    assert export.status_code == 200 and export.mimetype == "text/csv"
    lines = export.get_data(as_text=True).splitlines()
    assert lines[0].startswith("contact_id,first_name") and len(lines) == 4
    assert auth.get("/api/companies/export").status_code == 200
    assert auth.post("/api/contacts/bulk", json={"ids": ids, "action": "delete"}).status_code == 200
    assert auth.get("/api/contacts").get_json()["total"] == 0
