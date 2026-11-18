import pytest

from app.services import csv_processor as cp
from app.services import data_cleaner as dc
from app.utils.api import ApiError


def test_field_normalisation():
    assert dc.clean_str("  hello   world ") == "hello world"
    assert dc.clean_str(" N/A ") is None
    assert dc.normalize_email("  John.DOE@Example.COM ") == "john.doe@example.com"
    assert dc.is_valid_email("a.b@c.io") and not dc.is_valid_email("a@b") and not dc.is_valid_email("a..b@c.com")
    assert dc.normalize_phone("(415) 555-0101") == ("+14155550101", True)
    assert dc.normalize_phone("+91 98450 11223") == ("+919845011223", True)
    assert dc.normalize_phone("0049 711 555 0199") == ("+497115550199", True)
    assert dc.normalize_phone("9845022334", "+91") == ("+919845022334", True)
    assert dc.normalize_phone("+1 (212) 555-0123 ext 45")[0] == "+12125550123"
    assert dc.normalize_phone("555-0170") == ("555-0170", False)
    assert dc.normalize_phone("") == (None, True)
    assert dc.standardize_company_name("  technova   inc ") == "Technova Inc"
    assert dc.standardize_company_name("IBM") == "IBM" and dc.standardize_company_name("HubSpot") == "HubSpot"
    assert dc.company_key("TechNova Inc.") == dc.company_key("technova") == "technova"
    assert dc.company_key("FinEdge Pvt Ltd") == dc.company_key("FinEdge Private Limited") == "finedge"
    assert dc.normalize_country("usa") == "United States" and dc.normalize_country("UK") == "United Kingdom"
    assert dc.normalize_city("bangalore") == "Bengaluru" and dc.normalize_city("san francisco") == "San Francisco"
    assert dc.normalize_website("WWW.Example.com/") == "https://www.example.com"
    assert dc.split_full_name("Sharma, Rahul") == ("Rahul", "Sharma")
    assert dc.split_full_name("mary ann smith") == ("Mary Ann", "Smith")
    assert dc.parse_int("51-200") == 51 and dc.parse_int("1.5k") == 1500
    assert str(dc.parse_decimal("$2.5M")) == "2500000.00"
    assert dc.normalize_activity_type("Requested demo") == "demo_requested"
    assert dc.normalize_activity_type("email-opened") == "email_opened"


def test_suggest_and_validate_mapping():
    cols = ["name", "email", "phone", "company", "designation", "industry", "website", "lead_source"]
    mapping = cp.suggest_mapping(cols)
    assert mapping == {"name": "full_name", "email": "email", "phone": "phone", "company": "company_name",
                       "designation": "job_title", "industry": "industry", "website": "website",
                       "lead_source": "lead_source"}
    assert cp.validate_mapping(mapping, cols)
    with pytest.raises(ApiError) as e:
        cp.validate_mapping({"name": "full_name", "company": "company_name"}, cols)
    assert "identifier" in e.value.details
    with pytest.raises(ApiError) as e:
        cp.validate_mapping({"email": "email", "phone": "email"}, cols)
    assert "duplicates" in e.value.details
    with pytest.raises(ApiError) as e:
        cp.validate_mapping({"missing_col": "email"}, cols)
    assert "columns" in e.value.details


def test_clean_record_errors_and_warnings():
    mapping = {"n": "full_name", "e": "email", "p": "phone", "c": "company_name", "w": "website", "a": "activity_type",
               "d": "activity_date"}
    ok = cp.clean_record({"n": " jane DOE ", "e": "JANE@X.COM ", "p": "415 555 0101", "c": "acme inc",
                          "w": "acme.com", "a": "demo", "d": "2026-11-01"}, mapping)
    assert not ok["errors"]
    assert ok["contact"]["first_name"] == "Jane" and ok["contact"]["email"] == "jane@x.com"
    assert ok["company"]["company_name"] == "Acme Inc" and ok["activity"]["activity_type"] == "demo_requested"
    bad = cp.clean_record({"n": "Sam", "e": "sam@", "p": "", "c": "", "w": "", "a": "", "d": ""}, mapping)
    assert any("Invalid email" in e for e in bad["errors"])
    missing = cp.clean_record({"n": "", "e": "", "p": "", "c": "", "w": "", "a": "", "d": ""}, mapping)
    assert any("identifier" in e for e in missing["errors"])
    warn = cp.clean_record({"n": "", "e": "kim.lee@x.com", "p": "12", "c": "", "w": "", "a": "telepathy",
                            "d": "bad-date"}, mapping)
    assert warn["contact"]["first_name"] == "Kim"
    assert any("derived" in w for w in warn["warnings"]) and any("Phone" in w for w in warn["warnings"])
    assert any("Invalid activity date" in e for e in warn["errors"])


def test_upload_validation(auth):
    from tests.conftest import upload
    assert upload(auth, None, b"", name="empty.csv").status_code == 400
    assert upload(auth, None, b"first,email\n", name="header_only.csv").status_code == 400
    assert upload(auth, None, b"a,b\n1,2\n", name="data.xlsx").status_code == 415
    assert upload(auth, None, b"PK\x03\x04binary\x00\x00", name="fake.csv").status_code == 415
    ok = upload(auth, None, "email;Name\nx@y.com;X\n", name="semi.csv")
    assert ok.status_code == 201 and ok.get_json()["delimiter_label"] == "semicolon"
    assert auth.post("/api/imports/upload").status_code == 400
