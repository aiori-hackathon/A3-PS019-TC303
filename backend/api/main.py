"""
backend/api/main.py
===================
FastAPI REST API layer for PS-019: Personal-Data Discovery & Privacy Evidence Inventory.

Endpoints:
  - GET  /api/health                Service health status
  - GET  /api/summary               Overview counts (scanned fields, candidates, complete, gaps, evaluation)
  - POST /api/scan                  Run actual CSV and SQLite scanning workflow
  - POST /api/analyze               Run metadata mapping & evidence-gap generation
  - GET  /api/inventory             Retrieve unified personal-data evidence inventory
  - GET  /api/gaps                  Retrieve evidence gap records
  - GET  /api/evaluation            Retrieve ground-truth evaluation metrics, confusion matrix, errors
  - GET  /api/rules                 Return configured detection rules (read-only)
  - GET  /api/reports/{report_name} Safely download approved generated CSV/JSON reports
  - GET  /                          Serves frontend dashboard (index.html)

SCOPE DISCLAIMER:
This prototype identifies candidate personal-data fields using configurable technical rules
and records evidence about declared purpose and retention metadata. Results require human review.
Detection is not a legal determination, does not establish lawful basis, and does not prove
universal data-flow coverage or regulatory compliance.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query, Request, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.auth.routes import SESSION_COOKIE_NAME, auth_router, auth_service
from backend.evaluation.evaluator import DEFAULT_GROUND_TRUTH_PATH, Evaluator
from backend.evaluation.reporting import EvaluationReporter
from backend.metadata.gap_report import GapReportGenerator
from backend.metadata.inventory import EvidenceInventory
from backend.metadata.mapper import MetadataMapper
from backend.scanner.scanner_service import ScannerService

# ---------------------------------------------------------------------------
# Project directories & paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
REPORTS_DIR = PROJECT_ROOT / "reports"
RULES_PATH = PROJECT_ROOT / "backend" / "config" / "rules.json"
METADATA_PATH = PROJECT_ROOT / "backend" / "metadata" / "metadata.json"

# Whitelist of approved report filenames to prevent path traversal attacks
APPROVED_REPORTS: dict[str, str] = {
    "evidence_inventory.csv": "text/csv; charset=utf-8",
    "evidence_inventory.json": "application/json; charset=utf-8",
    "evidence_gaps.csv": "text/csv; charset=utf-8",
    "evaluation_summary.json": "application/json; charset=utf-8",
    "evaluation_per_class.csv": "text/csv; charset=utf-8",
    "evaluation_confusion_matrix.csv": "text/csv; charset=utf-8",
    "evaluation_errors.csv": "text/csv; charset=utf-8",
}

# ---------------------------------------------------------------------------
# FastAPI app creation & middleware
# ---------------------------------------------------------------------------
app = FastAPI(
    title="PS-019 Privacy Evidence Inventory API",
    description="Technical evidence discovery, purpose/retention mapping, and ground-truth evaluation.",
    version="1.0.0",
)

# Narrow, secure CORS configuration (local demo environment)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

# Authentication router for user registration, sessions, and login
app.include_router(auth_router)


# ---------------------------------------------------------------------------
# Response Models
# ---------------------------------------------------------------------------
class HealthResponse(BaseModel):
    status: str
    version: str
    service: str
    disclaimer: str


class ScanTriggerResponse(BaseModel):
    status: str
    message: str
    scanned_fields_count: int
    detected_candidates_count: int
    review_required_count: int
    csv_sources_scanned: list[str]
    sql_sources_scanned: list[str]


class AnalyzeTriggerResponse(BaseModel):
    status: str
    message: str
    inventory_count: int
    complete_count: int
    total_gaps_count: int
    gap_breakdown: dict[str, int]
    reports_updated: list[str]


# ---------------------------------------------------------------------------
# 1. Health Endpoint
# ---------------------------------------------------------------------------
@app.get("/api/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """Service status and technical readiness check."""
    return HealthResponse(
        status="healthy",
        version="1.0.0",
        service="PS-019 Privacy Evidence Inventory API",
        disclaimer=(
            "This prototype identifies candidate personal-data fields using configurable technical rules "
            "and records evidence about declared purpose and retention metadata. Results require human review. "
            "Detection is not a legal determination, does not establish lawful basis, and does not prove "
            "universal data-flow coverage or regulatory compliance."
        ),
    )


# ---------------------------------------------------------------------------
# 2. Summary Overview Endpoint
# ---------------------------------------------------------------------------
@app.get("/api/summary")
def get_summary() -> dict[str, Any]:
    """
    Returns latest overview metrics across inventory and evaluation.
    Gracefully handles states when reports have not yet been generated.
    """
    inventory_json_path = REPORTS_DIR / "evidence_inventory.json"
    evaluation_json_path = REPORTS_DIR / "evaluation_summary.json"

    summary_data: dict[str, Any] = {
        "reports_available": False,
        "scanned_fields": 0,
        "candidate_fields": 0,
        "complete_metadata": 0,
        "evidence_gaps": 0,
        "review_required": 0,
        "gaps_by_status": {},
        "gaps_by_class": {},
        "evaluation": None,
    }

    if inventory_json_path.exists():
        try:
            with open(inventory_json_path, encoding="utf-8") as f:
                inv_data = json.load(f)
            sum_block = inv_data.get("summary", {})
            summary_data["reports_available"] = True
            summary_data["candidate_fields"] = sum_block.get("total_candidates", 0)
            summary_data["complete_metadata"] = sum_block.get("complete_count", 0)
            summary_data["evidence_gaps"] = sum_block.get("total_gap_count", 0)
            summary_data["gaps_by_status"] = sum_block.get("gaps_by_status", {})
            summary_data["gaps_by_class"] = sum_block.get("gaps_by_class", {})

            # Count review required from inventory array
            inventory_list = inv_data.get("inventory", [])
            summary_data["scanned_fields"] = len(inventory_list)  # candidates in inventory
            summary_data["review_required"] = sum(
                1 for item in inventory_list if item.get("review_required") is True
            )
        except Exception as e:
            summary_data["inventory_error"] = str(e)

    if evaluation_json_path.exists():
        try:
            with open(evaluation_json_path, encoding="utf-8") as f:
                eval_data = json.load(f)
            summary_data["evaluation"] = {
                "total_evaluated": eval_data.get("matched_records_count", 0),
                "detection_precision": eval_data.get("detection_metrics", {}).get("precision"),
                "detection_recall": eval_data.get("detection_metrics", {}).get("recall"),
                "detection_f1": eval_data.get("detection_metrics", {}).get("f1"),
                "total_errors": eval_data.get("total_errors", 0),
            }
            if eval_data.get("scanner_predictions_total", 0) > summary_data["scanned_fields"]:
                summary_data["scanned_fields"] = eval_data.get("scanner_predictions_total", 0)
        except Exception as e:
            summary_data["evaluation_error"] = str(e)

    return summary_data


# ---------------------------------------------------------------------------
# 3. Trigger Scanner Endpoint
# ---------------------------------------------------------------------------
@app.post("/api/scan", response_model=ScanTriggerResponse)
def trigger_scan() -> ScanTriggerResponse:
    """
    Executes actual personal-data scanner across CSV datasets and SQLite database.
    Does not use mock or hardcoded results.
    """
    try:
        service = ScannerService()
        report = service.run_full_scan()

        csv_names = [cr.source_name for cr in report.csv_results]
        sql_names = [f"{sr.db_name}:{tbl}" for sr in report.sql_results for tbl in sr.tables.keys()]

        # Automatically synchronize metadata inventory and evaluation reports
        try:
            mapper = MetadataMapper(METADATA_PATH)
            inv_builder = EvidenceInventory(mapper)
            inventory_records = inv_builder.build(report.all_field_results)
            gap_reporter = GapReportGenerator(inventory_records)
            gap_reporter.build_summary()
            gap_reporter.export_inventory_csv()
            gap_reporter.export_gaps_csv()
            gap_reporter.export_inventory_json()

            evaluator = Evaluator()
            gt_records = evaluator.load_ground_truth(DEFAULT_GROUND_TRUTH_PATH)
            eval_summary = evaluator.evaluate(report.all_field_results, gt_records)
            errors = evaluator.extract_error_records(report.all_field_results, gt_records)

            eval_reporter = EvaluationReporter()
            eval_reporter.export_summary_json(eval_summary)
            eval_reporter.export_per_class_csv(eval_summary.per_class_metrics)
            eval_reporter.export_confusion_matrix_csv(eval_summary.confusion_matrix)
            eval_reporter.export_errors_csv(errors)
        except Exception as sync_err:
            # Non-fatal during raw scan if metadata/ground-truth are missing or custom
            pass

        return ScanTriggerResponse(
            status="completed",
            message="Scanner executed successfully across all synthetic data sources.",
            scanned_fields_count=len(report.all_field_results),
            detected_candidates_count=len(report.all_detected),
            review_required_count=len(report.all_review_required),
            csv_sources_scanned=csv_names,
            sql_sources_scanned=sql_names,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan execution error: {str(e)}",
        )


# ---------------------------------------------------------------------------
# 4. Trigger Analysis Endpoint (Metadata Mapping + Gaps + Evaluation)
# ---------------------------------------------------------------------------
@app.post("/api/analyze", response_model=AnalyzeTriggerResponse)
def trigger_analyze() -> AnalyzeTriggerResponse:
    """
    Executes the end-to-end mapping pipeline:
      1. Runs scanner on CSV and SQLite.
      2. Maps candidates to declared purpose & retention metadata.
      3. Generates unified inventory and computes evidence gaps.
      4. Evaluates against ground-truth dataset.
      5. Updates all reports in reports/ directory.
    """
    try:
        # 1. Scan
        service = ScannerService()
        scan_report = service.run_full_scan()

        # 2. Map & Build Inventory
        mapper = MetadataMapper(METADATA_PATH)
        inv_builder = EvidenceInventory(mapper)
        inventory_records = inv_builder.build(scan_report.all_field_results)

        # 3. Gap Report & Export
        gap_reporter = GapReportGenerator(inventory_records)
        summary = gap_reporter.build_summary()
        gap_reporter.export_inventory_csv()
        gap_reporter.export_gaps_csv()
        gap_reporter.export_inventory_json()

        # 4. Evaluation & Export
        evaluator = Evaluator()
        gt_records = evaluator.load_ground_truth(DEFAULT_GROUND_TRUTH_PATH)
        eval_summary = evaluator.evaluate(scan_report.all_field_results, gt_records)
        errors = evaluator.extract_error_records(scan_report.all_field_results, gt_records)

        eval_reporter = EvaluationReporter()
        eval_reporter.export_summary_json(eval_summary)
        eval_reporter.export_per_class_csv(eval_summary.per_class_metrics)
        eval_reporter.export_confusion_matrix_csv(eval_summary.confusion_matrix)
        eval_reporter.export_errors_csv(errors)

        return AnalyzeTriggerResponse(
            status="completed",
            message="Evidence inventory, gap analysis, and evaluation updated successfully.",
            inventory_count=len(inventory_records),
            complete_count=summary.complete_count,
            total_gaps_count=summary.total_gap_count,
            gap_breakdown=summary.gaps_by_status,
            reports_updated=list(APPROVED_REPORTS.keys()),
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis pipeline error: {str(e)}",
        )


# ---------------------------------------------------------------------------
# 5. Inventory Endpoint
# ---------------------------------------------------------------------------
@app.get("/api/inventory")
def get_inventory(
    search: Optional[str] = Query(None, description="Search term across field, source, purpose"),
    data_class: Optional[str] = Query(None, description="Filter by data class"),
    gap_status: Optional[str] = Query(None, description="Filter by overall metadata status"),
    review_required: Optional[bool] = Query(None, description="Filter by review required"),
) -> dict[str, Any]:
    """Returns the unified personal-data evidence inventory with optional query filters."""
    json_path = REPORTS_DIR / "evidence_inventory.json"
    if not json_path.exists():
        # Auto-run analysis if report has not yet been generated
        trigger_analyze()

    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        records: list[dict[str, Any]] = data.get("inventory", [])

        # Apply search filter
        if search:
            q = search.lower().strip()
            records = [
                r for r in records
                if q in r.get("field_name", "").lower()
                or q in r.get("source_name", "").lower()
                or q in r.get("purpose", "").lower()
                or q in r.get("detected_class", "").lower()
            ]

        # Apply data class filter
        if data_class and data_class != "All":
            records = [r for r in records if r.get("detected_class") == data_class]

        # Apply gap status filter
        if gap_status and gap_status != "All":
            records = [r for r in records if r.get("overall_status") == gap_status]

        # Apply review required filter
        if review_required is not None:
            records = [r for r in records if r.get("review_required") is review_required]

        return {
            "total_count": len(records),
            "records": records,
            "disclaimer": data.get("disclaimer"),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load inventory: {str(e)}")


# ---------------------------------------------------------------------------
# 6. Evidence Gaps Endpoint
# ---------------------------------------------------------------------------
@app.get("/api/gaps")
def get_gaps(
    search: Optional[str] = Query(None),
    status_type: Optional[str] = Query(None),
    data_class: Optional[str] = Query(None),
) -> dict[str, Any]:
    """Returns records that have missing or unmapped declared metadata."""
    json_path = REPORTS_DIR / "evidence_inventory.json"
    if not json_path.exists():
        trigger_analyze()

    try:
        with open(json_path, encoding="utf-8") as f:
            data = json.load(f)

        all_records = data.get("inventory", [])
        # Only gap records (overall_status != 'Complete')
        gap_records = [r for r in all_records if r.get("overall_status") != "Complete"]

        if search:
            q = search.lower().strip()
            gap_records = [
                r for r in gap_records
                if q in r.get("field_name", "").lower()
                or q in r.get("source_name", "").lower()
                or q in r.get("evidence_note", "").lower()
            ]

        if status_type and status_type != "All":
            gap_records = [r for r in gap_records if r.get("overall_status") == status_type]

        if data_class and data_class != "All":
            gap_records = [r for r in gap_records if r.get("detected_class") == data_class]

        return {
            "total_gaps": len(gap_records),
            "summary": data.get("summary", {}),
            "gaps": gap_records,
            "scope_note": "Evidence gaps indicate missing declared metadata requiring human review. Not a legal violation.",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load gaps: {str(e)}")


# ---------------------------------------------------------------------------
# 7. Evaluation Metrics Endpoint
# ---------------------------------------------------------------------------
@app.get("/api/evaluation")
def get_evaluation() -> dict[str, Any]:
    """Returns the ground-truth evaluation metrics, confusion matrix, and errors."""
    eval_json_path = REPORTS_DIR / "evaluation_summary.json"
    if not eval_json_path.exists():
        trigger_analyze()

    try:
        with open(eval_json_path, encoding="utf-8") as f:
            eval_data = json.load(f)

        # Also load error records from CSV if available
        errors_path = REPORTS_DIR / "evaluation_errors.csv"
        errors_list: list[dict[str, Any]] = []
        if errors_path.exists():
            import csv
            with open(errors_path, encoding="utf-8") as ef:
                reader = csv.DictReader(ef)
                errors_list = list(reader)

        eval_data["detailed_errors"] = errors_list
        return eval_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load evaluation: {str(e)}")


# ---------------------------------------------------------------------------
# 8. Detection Rules Endpoint (Read-Only)
# ---------------------------------------------------------------------------
@app.get("/api/rules")
def get_rules() -> dict[str, Any]:
    """Returns the currently configured detection rules without exposing internal secrets."""
    if not RULES_PATH.exists():
        raise HTTPException(status_code=404, detail="rules.json configuration not found.")

    try:
        with open(RULES_PATH, encoding="utf-8") as f:
            rules_data = json.load(f)
        return rules_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load rules: {str(e)}")


# ---------------------------------------------------------------------------
# 9. Safe Report Downloads Endpoint
# ---------------------------------------------------------------------------
@app.get("/api/reports/{report_name}")
def download_report(report_name: str):
    """
    Safely serves only approved, generated report files.
    Strictly protects against path traversal attacks.
    """
    # Strict whitelist check
    if report_name not in APPROVED_REPORTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Report '{report_name}' is not an approved downloadable report.",
        )

    file_path = (REPORTS_DIR / report_name).resolve()

    # Ensure path stays within REPORTS_DIR
    try:
        file_path.relative_to(REPORTS_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    if not file_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report file '{report_name}' has not been generated yet. Please run scan/analyze.",
        )

    media_type = APPROVED_REPORTS[report_name]
    return FileResponse(
        path=str(file_path),
        media_type=media_type,
        filename=report_name,
    )


# ---------------------------------------------------------------------------
# 10. Frontend Multi-Page Static & HTML Serving
# ---------------------------------------------------------------------------
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

    def _serve_page(filename: str, no_cache: bool = False):
        filepath = FRONTEND_DIR / filename
        if filepath.exists():
            headers = {"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"} if no_cache else {}
            return FileResponse(str(filepath), headers=headers)
        return JSONResponse(
            status_code=404,
            content={"message": f"Page '{filename}' not found."},
        )

    def _require_auth_page(request: Request, filename: str):
        token = request.cookies.get(SESSION_COOKIE_NAME)
        user = auth_service.get_user_by_session(token) if token else None
        if not user:
            target_path = request.url.path
            return RedirectResponse(
                url=f"/login?redirect={target_path}",
                status_code=303,
                headers={"Cache-Control": "no-store, no-cache, must-revalidate, max-age=0"},
            )
        return _serve_page(filename, no_cache=True)

    @app.get("/", include_in_schema=False)
    @app.get("/index.html", include_in_schema=False)
    def serve_frontend_root(request: Request):
        """Root route: If authenticated, redirects to workspace; if unauthenticated, serves login page."""
        token = request.cookies.get(SESSION_COOKIE_NAME)
        user = auth_service.get_user_by_session(token) if token else None
        if user:
            return RedirectResponse(url="/workspace", status_code=303)
        return _serve_page("login.html")

    @app.get("/login", include_in_schema=False)
    @app.get("/login.html", include_in_schema=False)
    def serve_frontend_login(request: Request):
        """Serves the dedicated login page. If already authenticated, redirects to workspace."""
        token = request.cookies.get(SESSION_COOKIE_NAME)
        user = auth_service.get_user_by_session(token) if token else None
        if user:
            redirect_param = request.query_params.get("redirect", "/workspace")
            if not redirect_param.startswith("/"):
                redirect_param = "/workspace"
            return RedirectResponse(url=redirect_param, status_code=303)
        return _serve_page("login.html")

    @app.get("/register", include_in_schema=False)
    @app.get("/register.html", include_in_schema=False)
    def serve_frontend_register(request: Request):
        """Serves the dedicated registration page. If already authenticated, redirects to workspace."""
        token = request.cookies.get(SESSION_COOKIE_NAME)
        user = auth_service.get_user_by_session(token) if token else None
        if user:
            return RedirectResponse(url="/workspace", status_code=303)
        return _serve_page("register.html")

    @app.get("/workspace", include_in_schema=False)
    @app.get("/workspace.html", include_in_schema=False)
    @app.get("/overview", include_in_schema=False)
    @app.get("/overview.html", include_in_schema=False)
    def serve_frontend_workspace(request: Request):
        """Serves the main workspace overview dashboard (protected)."""
        return _require_auth_page(request, "workspace.html")

    @app.get("/inventory", include_in_schema=False)
    @app.get("/inventory.html", include_in_schema=False)
    def serve_frontend_inventory(request: Request):
        """Serves the personal-data inventory page (protected)."""
        return _require_auth_page(request, "inventory.html")

    @app.get("/evidence-gaps", include_in_schema=False)
    @app.get("/evidence-gaps.html", include_in_schema=False)
    @app.get("/gaps", include_in_schema=False)
    @app.get("/gaps.html", include_in_schema=False)
    def serve_frontend_gaps(request: Request):
        """Serves the evidence gaps page (protected)."""
        return _require_auth_page(request, "gaps.html")

    @app.get("/evaluation", include_in_schema=False)
    @app.get("/evaluation.html", include_in_schema=False)
    def serve_frontend_evaluation(request: Request):
        """Serves the ground-truth evaluation page (protected)."""
        return _require_auth_page(request, "evaluation.html")

    @app.get("/rules", include_in_schema=False)
    @app.get("/rules.html", include_in_schema=False)
    def serve_frontend_rules(request: Request):
        """Serves the detection rules page (protected)."""
        return _require_auth_page(request, "rules.html")

    @app.get("/reports", include_in_schema=False)
    @app.get("/reports.html", include_in_schema=False)
    def serve_frontend_reports(request: Request):
        """Serves the reports & downloads page (protected)."""
        return _require_auth_page(request, "reports.html")

    @app.get("/404", include_in_schema=False)
    @app.get("/404.html", include_in_schema=False)
    def serve_frontend_404():
        """Serves the custom 404 error page."""
        return _serve_page("404.html")

    @app.exception_handler(404)
    async def custom_404_handler(request, exc):
        """Custom 404 handler returning 404.html for browser routes and JSON for API."""
        if request.url.path.startswith("/api/"):
            return JSONResponse(
                status_code=404,
                content={"detail": getattr(exc, "detail", "Not Found")},
            )
        file_404 = FRONTEND_DIR / "404.html"
        if file_404.exists():
            return FileResponse(str(file_404), status_code=404)
        return JSONResponse(status_code=404, content={"detail": "Page not found."})
