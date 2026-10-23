"""
tests/test_api.py
=================
Integration tests for Phase 6 FastAPI REST API layer & Dashboard endpoints.

Verifies:
  1. GET  /api/health            Health status and disclaimer
  2. GET  /api/summary           Overview summary counts
  3. POST /api/scan              Actual scanner execution across CSV + SQLite
  4. POST /api/analyze           Metadata mapping, gap reporting, and evaluation update
  5. GET  /api/inventory         Personal-data inventory query and filtering
  6. GET  /api/gaps              Evidence gaps endpoint with status filtering
  7. GET  /api/evaluation        Ground-truth metrics, confusion matrix, errors
  8. GET  /api/rules             Configured detection rules (read-only)
  9. GET  /api/reports/{name}    Safe report downloads
 10. Path traversal protection on report downloads
 11. GET  /                      Static frontend dashboard index.html serving
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from backend.api.main import APPROVED_REPORTS, app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def test_api_health(client: TestClient) -> None:
    res = client.get("/api/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "healthy"
    assert "disclaimer" in data
    assert "technical rules" in data["disclaimer"]


def test_api_summary(client: TestClient) -> None:
    res = client.get("/api/summary")
    assert res.status_code == 200
    data = res.json()
    assert "scanned_fields" in data
    assert "candidate_fields" in data
    assert "evidence_gaps" in data
    assert data["scanned_fields"] >= 50
    assert data["candidate_fields"] >= 40


def test_api_scan_trigger(client: TestClient) -> None:
    res = client.post("/api/scan")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert data["scanned_fields_count"] >= 84
    assert data["detected_candidates_count"] >= 50
    assert len(data["csv_sources_scanned"]) >= 3
    assert len(data["sql_sources_scanned"]) >= 3


def test_api_analyze_trigger(client: TestClient) -> None:
    res = client.post("/api/analyze")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "completed"
    assert data["inventory_count"] >= 50
    assert data["complete_count"] >= 15
    assert data["total_gaps_count"] >= 35


def test_api_inventory(client: TestClient) -> None:
    res = client.get("/api/inventory")
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] >= 50
    assert len(data["records"]) == data["total_count"]

    # Test filtering by class
    res_filtered = client.get("/api/inventory?data_class=Contact")
    assert res_filtered.status_code == 200
    f_data = res_filtered.json()
    assert all(r["detected_class"] == "Contact" for r in f_data["records"])

    # Test search query
    res_search = client.get("/api/inventory?search=email")
    assert res_search.status_code == 200
    s_data = res_search.json()
    assert len(s_data["records"]) > 0


def test_api_gaps(client: TestClient) -> None:
    res = client.get("/api/gaps")
    assert res.status_code == 200
    data = res.json()
    assert data["total_gaps"] >= 35
    assert len(data["gaps"]) == data["total_gaps"]
    assert all(g["overall_status"] != "Complete" for g in data["gaps"])

    # Test gap type filter
    res_filtered = client.get("/api/gaps?status_type=Retention+Missing")
    assert res_filtered.status_code == 200
    g_data = res_filtered.json()
    assert all(g["overall_status"] == "Retention Missing" for g in g_data["gaps"])


def test_api_evaluation(client: TestClient) -> None:
    res = client.get("/api/evaluation")
    assert res.status_code == 200
    data = res.json()
    assert "detection_metrics" in data
    assert "per_class_metrics" in data
    assert "confusion_matrix" in data
    assert data["matched_records_count"] == 84
    assert data["detection_metrics"]["precision"] == 0.8
    assert data["detection_metrics"]["recall"] == 1.0


def test_api_rules(client: TestClient) -> None:
    res = client.get("/api/rules")
    assert res.status_code == 200
    data = res.json()
    assert "classes" in data
    assert "Identity" in data["classes"]
    assert "Contact" in data["classes"]
    assert "Location" in data["classes"]
    assert "Financial" in data["classes"]
    assert "Sensitive/Health" in data["classes"]


def test_api_reports_download_approved(client: TestClient) -> None:
    for report_name in APPROVED_REPORTS.keys():
        res = client.get(f"/api/reports/{report_name}")
        assert res.status_code == 200
        assert len(res.content) > 0


def test_api_reports_path_traversal_protection(client: TestClient) -> None:
    # Attempt unauthorized access or path traversal
    res = client.get("/api/reports/../../backend/config/rules.json")
    assert res.status_code in [400, 404]

    res_unapproved = client.get("/api/reports/secret_passwords.txt")
    assert res_unapproved.status_code == 400


def test_api_frontend_serving(client: TestClient) -> None:
    res = client.get("/")
    assert res.status_code == 200
    assert "text/html" in res.headers["content-type"]
    assert "Personal-Data Discovery & Evidence Inventory" in res.text


def test_api_inventory_empty_search(client: TestClient) -> None:
    res = client.get("/api/inventory?search=non_existent_field_xyz_123")
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] == 0
    assert data["records"] == []


def test_api_gaps_empty_filter(client: TestClient) -> None:
    res = client.get("/api/gaps?status_type=NonExistentStatus")
    assert res.status_code == 200
    data = res.json()
    assert data["total_gaps"] == 0
    assert data["gaps"] == []


def test_api_repeated_scan_idempotency(client: TestClient) -> None:
    # Run scan twice
    res1 = client.post("/api/scan")
    res2 = client.post("/api/scan")
    assert res1.status_code == 200
    assert res2.status_code == 200
    data1 = res1.json()
    data2 = res2.json()
    assert data1["scanned_fields_count"] == data2["scanned_fields_count"]
    assert data1["scanned_fields_count"] >= 84
    assert data1["detected_candidates_count"] == data2["detected_candidates_count"]
    assert data1["detected_candidates_count"] >= 50

    # Verify inventory is not duplicated
    inv_res = client.get("/api/inventory")
    assert inv_res.json()["total_count"] == data1["detected_candidates_count"]



def test_api_data_sources_preview(client: TestClient) -> None:
    res = client.get("/api/data-sources")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["total_sources"] >= 6
    assert data["csv_count"] >= 3
    assert data["sql_count"] >= 3

    # Check CSV sources
    csv_names = [c["file_name"] for c in data["csv_files"]]
    assert "customers.csv" in csv_names
    assert "employees.csv" in csv_names
    assert "transactions.csv" in csv_names
    for c in data["csv_files"]:
        assert c["status"] == "Available"
        assert c["row_count"] > 0
        assert c["columns_count"] > 0
        assert len(c["columns"]) > 0

    # Check SQL sources
    sql_tables = [s["table_name"] for s in data["sql_tables"]]
    assert "customers" in sql_tables
    assert "employees" in sql_tables
    assert "transactions" in sql_tables
    for s in data["sql_tables"]:
        assert s["status"] == "Available"
        assert s["row_count"] > 0
        assert s["columns_count"] > 0
        assert len(s["columns"]) > 0


def test_api_scan_status(client: TestClient) -> None:
    res = client.get("/api/scan/status")
    assert res.status_code == 200
    data = res.json()
    assert "status" in data
    assert data["status"] in ("pending", "running", "completed", "failed")


def test_api_scan_prevents_duplicate_concurrent_submissions(client: TestClient) -> None:
    from backend.api.main import _SCAN_LOCK
    _SCAN_LOCK.acquire()
    try:
        res = client.post("/api/scan")
        assert res.status_code == 409
        assert "already in progress" in res.json()["detail"]
    finally:
        _SCAN_LOCK.release()


def test_api_scan_failure_handling(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.scanner.scanner_service import ScannerService

    def mock_run_full_scan(self):
        raise RuntimeError("Simulated scanner disk read failure")

    monkeypatch.setattr(ScannerService, "run_full_scan", mock_run_full_scan)

    res = client.post("/api/scan")
    assert res.status_code == 500
    assert "Simulated scanner disk read failure" in res.json()["detail"]

    # Verify scan status endpoint reflects the actual failure
    status_res = client.get("/api/scan/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "failed"
    assert "Simulated scanner disk read failure" in status_data["error"]


def test_api_analyze_prevents_duplicate_concurrent_submissions(client: TestClient) -> None:
    from backend.api.main import _SCAN_LOCK
    _SCAN_LOCK.acquire()
    try:
        res = client.post("/api/analyze")
        assert res.status_code == 409
        assert "already in progress" in res.json()["detail"]
    finally:
        _SCAN_LOCK.release()


def test_api_analyze_failure_handling(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.scanner.scanner_service import ScannerService

    def mock_run_full_scan(self):
        raise RuntimeError("Simulated pipeline engine failure")

    monkeypatch.setattr(ScannerService, "run_full_scan", mock_run_full_scan)

    res = client.post("/api/analyze")
    assert res.status_code == 500
    assert "Simulated pipeline engine failure" in res.json()["detail"]

    # Verify scan status endpoint reflects the actual failure
    status_res = client.get("/api/scan/status")
    assert status_res.status_code == 200
    status_data = status_res.json()
    assert status_data["status"] == "failed"
    assert "Simulated pipeline engine failure" in status_data["error"]





