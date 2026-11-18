import io
import os
import shutil
import sys

import pytest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app import create_app  # noqa: E402
from app.extensions import db  # noqa: E402

SAMPLES = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "samples"))


@pytest.fixture()
def app():
    app = create_app("config.TestConfig")
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()
    shutil.rmtree(app.config["UPLOAD_FOLDER"], ignore_errors=True)


@pytest.fixture()
def client(app):
    return app.test_client()


def register(client, email="alice@example.com", password="Password123", name="Alice Admin"):
    return client.post("/api/auth/register", json={"full_name": name, "email": email, "password": password})


@pytest.fixture()
def auth(client):
    resp = register(client)
    assert resp.status_code == 201, resp.get_json()
    return client


def upload(client, filename, content=None, name=None):
    if content is None:
        with open(os.path.join(SAMPLES, filename), "rb") as fh:
            content = fh.read()
    if isinstance(content, str):
        content = content.encode("utf-8")
    return client.post("/api/imports/upload", data={"file": (io.BytesIO(content), name or filename or "data.csv")},
                       content_type="multipart/form-data")


def run_import(client, filename=None, mode="upsert", content=None, mapping=None, dry_run=False):
    up = upload(client, filename, content)
    assert up.status_code == 201, up.get_json()
    data = up.get_json()
    body = {"import_id": data["job"]["import_id"], "mapping": mapping or data["suggested_mapping"], "mode": mode}
    endpoint = "/api/imports/preview" if dry_run else "/api/imports/execute"
    resp = client.post(endpoint, json=body)
    return resp, data
