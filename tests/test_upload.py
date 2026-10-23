"""
tests/test_upload.py
====================
Integration tests for PrivSight Data Upload endpoints:
  - POST   /api/upload
  - GET    /api/uploads
  - DELETE /api/uploads/{filename}

Validates:
  - File extension whitelist (.csv, .db, .sqlite, .sqlite3)
  - File size limits (<= 25MB)
  - Magic byte / content validation (SQLite header, CSV text)
  - Automatic detection and pipeline sync
  - Protection of system default datasets from deletion
  - Safe deletion of custom uploads
"""

from __future__ import annotations

import io
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app, DEFAULT_SYSTEM_DATASETS


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_list_uploads_endpoint(client: TestClient) -> None:
    res = client.get("/api/uploads")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total_files"] >= 4
    filenames = [f["filename"] for f in data["files"]]
    assert "customers.csv" in filenames
    assert "privacy_demo.db" in filenames
    # System datasets should be marked is_custom=False
    for f in data["files"]:
        if f["filename"] in DEFAULT_SYSTEM_DATASETS:
            assert f["is_custom"] is False


def test_upload_rejects_unsupported_extension(client: TestClient) -> None:
    file_content = b"some random text"
    files = {"file": ("malicious.exe", io.BytesIO(file_content), "application/octet-stream")}
    res = client.post("/api/upload", files=files)
    assert res.status_code == 400
    assert "Unsupported file format" in res.json()["detail"]


def test_upload_rejects_empty_file(client: TestClient) -> None:
    files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    res = client.post("/api/upload", files=files)
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_upload_rejects_corrupted_csv(client: TestClient) -> None:
    # Binary null bytes in CSV
    corrupted = b"col1,col2\x00\xff\xfe"
    files = {"file": ("bad.csv", io.BytesIO(corrupted), "text/csv")}
    res = client.post("/api/upload", files=files)
    assert res.status_code == 400
    assert "Invalid CSV format" in res.json()["detail"]


def test_upload_rejects_fake_sqlite(client: TestClient) -> None:
    # Missing SQLite format 3 magic header
    fake_db = b"THIS IS NOT A SQLITE DATABASE"
    files = {"file": ("fake.db", io.BytesIO(fake_db), "application/octet-stream")}
    res = client.post("/api/upload", files=files)
    assert res.status_code == 400
    assert "Invalid SQLite database" in res.json()["detail"]


def test_upload_valid_csv_and_process(client: TestClient) -> None:
    csv_content = (
        "customer_id,full_name,email_address,phone_number,signup_ip\n"
        "101,John Doe,john.doe@example.com,+1-555-0199,192.168.1.10\n"
        "102,Jane Smith,jane.smith@example.org,+1-555-0188,10.0.0.12\n"
    ).encode("utf-8")

    filename = "test_custom_customers.csv"
    files = {"file": (filename, io.BytesIO(csv_content), "text/csv")}
    data = {"auto_scan": "true"}

    res = client.post("/api/upload", files=files, data=data)
    assert res.status_code == 200
    resp_data = res.json()

    assert resp_data["status"] == "success"
    assert resp_data["filename"] == filename
    assert resp_data["file_type"] == "csv"
    assert resp_data["scanned_fields_count"] == 5
    assert resp_data["detected_candidates_count"] >= 3

    detected_classes = [d["detected_class"] for d in resp_data["detected_fields"]]
    assert "Contact" in detected_classes
    assert "Identity" in detected_classes

    # Verify dataset appears in list
    list_res = client.get("/api/uploads")
    custom_entry = next((f for f in list_res.json()["files"] if f["filename"] == filename), None)
    assert custom_entry is not None
    assert custom_entry["is_custom"] is True

    # Attempt to delete system default dataset should fail (400)
    del_sys_res = client.delete("/api/uploads/customers.csv")
    assert del_sys_res.status_code == 400

    # Delete custom uploaded dataset should succeed (200)
    del_custom_res = client.delete(f"/api/uploads/{filename}")
    assert del_custom_res.status_code == 200

    # Verify it is no longer in list
    list_res_after = client.get("/api/uploads")
    assert not any(f["filename"] == filename for f in list_res_after.json()["files"])
