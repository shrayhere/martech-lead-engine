from app import create_app
from app.extensions import db
from tests.conftest import register


def test_register_login_logout(client):
    resp = register(client)
    assert resp.status_code == 201
    assert resp.get_json()["user"]["role"] == "admin"  # first user
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 200
    assert client.get("/api/auth/me").status_code == 401
    resp = client.post("/api/auth/login", json={"email": "ALICE@example.com", "password": "Password123"})
    assert resp.status_code == 200
    assert client.get("/api/contacts").status_code == 200


def test_register_validation_and_duplicates(client):
    resp = client.post("/api/auth/register", json={"full_name": "B", "email": "bad", "password": "short"})
    assert resp.status_code == 422
    assert {"full_name", "email", "password"} <= set(resp.get_json()["details"])
    assert register(client).status_code == 201
    client.post("/api/auth/logout")
    assert register(client).status_code == 409
    second = register(client, email="bob@example.com")
    assert second.get_json()["user"]["role"] == "member"


def test_password_is_hashed_and_wrong_password_rejected(client):
    register(client)
    from app.models import User
    user = User.query.filter_by(email="alice@example.com").one()
    assert user.password_hash != "Password123" and user.password_hash.startswith(("scrypt", "pbkdf2"))
    client.post("/api/auth/logout")
    resp = client.post("/api/auth/login", json={"email": "alice@example.com", "password": "Wrong12345"})
    assert resp.status_code == 401


def test_protected_routes(client):
    assert client.get("/api/contacts").status_code == 401
    assert client.get("/api/dashboard/stats").status_code == 401
    page = client.get("/contacts")
    assert page.status_code == 302 and "/login" in page.headers["Location"]


def test_csrf_enforced_when_enabled():
    from config import TestConfig

    class CsrfConfig(TestConfig):
        WTF_CSRF_ENABLED = True

    app = create_app(CsrfConfig)
    with app.app_context():
        db.create_all()
        client = app.test_client()
        body = {"full_name": "Carol", "email": "carol@example.com", "password": "Password123"}
        resp = client.post("/api/auth/register", json=body)
        assert resp.status_code == 400 and "CSRF" in resp.get_json()["error"]
        html = client.get("/login").get_data(as_text=True)
        token = html.split('name="csrf-token" content="')[1].split('"')[0]
        resp = client.post("/api/auth/register", headers={"X-CSRFToken": token}, json=body)
        assert resp.status_code == 201
        db.session.remove()
        db.drop_all()


def test_profile_update(auth):
    resp = auth.put("/api/auth/profile", json={"full_name": "Alice A", "current_password": "nope",
                                               "new_password": "NewPass123"})
    assert resp.status_code == 422
    resp = auth.put("/api/auth/profile", json={"full_name": "Alice A", "current_password": "Password123",
                                               "new_password": "NewPass123"})
    assert resp.status_code == 200
    auth.post("/api/auth/logout")
    assert auth.post("/api/auth/login",
                     json={"email": "alice@example.com", "password": "NewPass123"}).status_code == 200
