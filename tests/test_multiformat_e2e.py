"""
tests/test_multiformat_e2e.py
=============================
End-to-End API verification of multi-format data ingestion, scanning,
error handling, and inventory synchronization across all supported formats.
"""

from pathlib import Path
import pytest
from starlette.testclient import TestClient

from backend.api.main import app

QA_DIR = Path(__file__).parent.parent / "PrivSight_QA_MultiFormat_Data"


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_e2e_json_upload_and_scan(client: TestClient):
    file_path = QA_DIR / "qa_customers.json"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": (file_path.name, f, "application/json")},
            data={"auto_scan": "true"},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["filename"] == "qa_customers.json"
    assert data["file_type"] == "json"
    assert data["scanned_fields_count"] > 0
    # Field names should include personal data candidates
    detected = [f["field_name"] for f in data["detected_fields"]]
    assert any("email" in f or "phone" in f for f in detected)


def test_e2e_xlsx_upload_and_scan(client: TestClient):
    file_path = QA_DIR / "qa_executive_payroll.xlsx"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
            data={"auto_scan": "true"},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["filename"] == "qa_executive_payroll.xlsx"
    assert data["file_type"] == "xlsx"
    assert data["scanned_fields_count"] >= 5
    detected_classes = [f["detected_class"] for f in data["detected_fields"]]
    assert any(c in ("Financial", "Contact", "Identity") for c in detected_classes)


def test_e2e_docx_upload_and_scan(client: TestClient):
    file_path = QA_DIR / "qa_contractor_profile.docx"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"auto_scan": "true"},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["filename"] == "qa_contractor_profile.docx"
    assert data["file_type"] == "docx"
    assert data["scanned_fields_count"] > 0


def test_e2e_pdf_upload_and_scan(client: TestClient):
    file_path = QA_DIR / "qa_security_brief.pdf"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": (file_path.name, f, "application/pdf")},
            data={"auto_scan": "true"},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["filename"] == "qa_security_brief.pdf"
    assert data["file_type"] == "pdf"


def test_e2e_xml_upload_and_scan(client: TestClient):
    file_path = QA_DIR / "qa_suppliers.xml"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": (file_path.name, f, "application/xml")},
            data={"auto_scan": "true"},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["filename"] == "qa_suppliers.xml"
    assert data["file_type"] == "xml"


def test_e2e_log_upload_and_scan(client: TestClient):
    file_path = QA_DIR / "qa_access_audit.log"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": (file_path.name, f, "text/plain")},
            data={"auto_scan": "true"},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["filename"] == "qa_access_audit.log"
    assert data["file_type"] == "log"


def test_e2e_txt_upload_and_scan(client: TestClient):
    file_path = QA_DIR / "qa_patient_notes.txt"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": (file_path.name, f, "text/plain")},
            data={"auto_scan": "true"},
        )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["filename"] == "qa_patient_notes.txt"
    assert data["file_type"] == "txt"


def test_e2e_corrupted_file_rejection(client: TestClient):
    file_path = QA_DIR / "qa_corrupted_document.docx"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": (file_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
            data={"auto_scan": "true"},
        )
    assert res.status_code == 400
    detail = res.json()["detail"].lower()
    assert "signature" in detail or "corrupt" in detail or "invalid" in detail


def test_e2e_encrypted_file_rejection(client: TestClient):
    file_path = QA_DIR / "qa_encrypted_report.pdf"
    assert file_path.exists()

    with open(file_path, "rb") as f:
        res = client.post(
            "/api/upload",
            files={"file": (file_path.name, f, "application/pdf")},
            data={"auto_scan": "true"},
        )
    assert res.status_code == 400
    detail = res.json()["detail"].lower()
    assert "encrypted" in detail or "password" in detail


def test_e2e_data_sources_listing(client: TestClient):
    res = client.get("/api/data-sources")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert len(data["csv_files"]) > 0
    # Check that format badges are present
    badges = [f.get("badge_label") for f in data["csv_files"]]
    assert any(b in ("JSON", "XLSX", "DOCX", "PDF", "XML", "LOG", "TXT", "CSV") for b in badges)


def test_e2e_trigger_full_scan(client: TestClient):
    res = client.post("/api/scan")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert data["scanned_fields_count"] > 0
    assert len(data["file_sources_scanned"]) > 0


def test_e2e_delete_uploaded_file(client: TestClient):
    # Delete one of the uploaded test files
    res = client.delete("/api/uploads/qa_customers.json")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert "removed" in data["message"]
