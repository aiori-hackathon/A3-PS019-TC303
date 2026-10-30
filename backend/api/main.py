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

import csv
import json
import logging
import re
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from backend.auth.models import UserResponse
from backend.auth.routes import SESSION_COOKIE_NAME, _extract_token, auth_router, auth_service
from backend.evaluation.evaluator import DEFAULT_GROUND_TRUTH_PATH, Evaluator
from backend.evaluation.reporting import EvaluationReporter
from backend.metadata.gap_report import GapReportGenerator
from backend.metadata.inventory import EvidenceInventory
from backend.metadata.mapper import MetadataMapper
from backend.parsers import (
    CorruptedFileError,
    EncryptedFileError,
    ParserError,
    UnsupportedFormatError,
    get_parser_registry,
)
from backend.relationships.routes import relationships_router
from backend.scanner.scanner_service import ScannerService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("privsight.api")

# ---------------------------------------------------------------------------
# Project directories & paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).parent.parent.parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
REPORTS_DIR = PROJECT_ROOT / "reports"
RULES_PATH = PROJECT_ROOT / "backend" / "config" / "rules.json"
METADATA_PATH = PROJECT_ROOT / "backend" / "metadata" / "metadata.json"
DATA_UPLOADS_DIR = PROJECT_ROOT / "data" / "uploads"
DATA_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

MAX_UPLOAD_SIZE = 25 * 1024 * 1024  # 25 MB
SUPPORTED_EXTENSIONS = get_parser_registry().get_supported_extensions()
DEFAULT_SYSTEM_DATASETS = {
    "customers.csv",
    "employees.csv",
    "transactions.csv",
    "privacy_demo.db",
}

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
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    """Ensure dynamic API responses are never cached by browsers."""
    response = await call_next(request)
    if request.url.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response


# Authentication router for user registration, sessions, and login
app.include_router(auth_router)

# AI Relationship Intelligence Assistant router
app.include_router(relationships_router)


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
    file_sources_scanned: list[str] = []


class AnalyzeTriggerResponse(BaseModel):
    status: str
    message: str
    inventory_count: int
    complete_count: int
    total_gaps_count: int
    gap_breakdown: dict[str, int]
    reports_updated: list[str]
    scanned_fields_count: int = 84
    detected_candidates_count: int = 50


class UploadedFieldInfo(BaseModel):
    field_name: str
    detected_class: Optional[str] = None
    confidence: float
    confidence_level: str = "Medium"
    review_required: bool
    reason: Optional[str] = None


class FileUploadResponse(BaseModel):
    status: str
    message: str
    filename: str
    file_type: str
    file_size_bytes: int
    scanned_fields_count: int
    detected_candidates_count: int
    detected_fields: list[UploadedFieldInfo]


class UploadedFileInfo(BaseModel):
    filename: str
    file_type: str
    size_bytes: int
    last_modified: str
    is_custom: bool


class UploadsListResponse(BaseModel):
    status: str
    total_files: int
    files: list[UploadedFileInfo]


class DataSourceItem(BaseModel):
    source_name: str
    source_type: str
    file_name: Optional[str] = None
    table_name: Optional[str] = None
    db_file: Optional[str] = None
    file_size_bytes: Optional[int] = None
    row_count: Optional[int] = None
    columns_count: int
    columns: list[str] = []
    schema_preview: Optional[str] = None
    status: str = "Available"
    is_custom: bool = False
    badge_label: Optional[str] = None
    badge_color: Optional[str] = None
    format_group: Optional[str] = None


class DataSourcesResponse(BaseModel):
    status: str
    message: str
    total_sources: int
    csv_count: int
    sql_count: int
    csv_files: list[DataSourceItem]
    sql_tables: list[DataSourceItem]
    scan_status: str
    last_scan_time: Optional[str] = None


class ScanStatusResponse(BaseModel):
    status: str
    message: str
    last_scan_time: Optional[str] = None
    last_scan_duration_ms: Optional[int] = None
    scanned_fields_count: int = 0
    detected_candidates_count: int = 0
    review_required_count: int = 0
    error: Optional[str] = None


# Scan execution lock and state
_SCAN_LOCK = threading.Lock()
_SCAN_STATE: dict[str, Any] = {
    "status": "pending",
    "message": "Review your available data sources, then click Run Full Scan to begin analysis.",
    "last_scan_time": None,
    "last_scan_duration_ms": None,
    "scanned_fields_count": 0,
    "detected_candidates_count": 0,
    "review_required_count": 0,
    "error": None,
}


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

    if _SCAN_STATE.get("scanned_fields_count", 0) > summary_data["scanned_fields"]:
        summary_data["scanned_fields"] = _SCAN_STATE.get("scanned_fields_count", 0)

    return summary_data


def _sync_pipeline_reports(scan_report) -> tuple[Any, Any]:
    """
    Synchronizes evidence inventory, evidence gaps, and evaluation reports after a scan or upload.
    Returns (inventory_records, gap_summary).
    """
    mapper = MetadataMapper(METADATA_PATH)
    inv_builder = EvidenceInventory(mapper)
    inventory_records = inv_builder.build(scan_report.all_field_results)
    gap_reporter = GapReportGenerator(inventory_records)
    summary = gap_reporter.build_summary()
    gap_reporter.export_inventory_csv()
    gap_reporter.export_gaps_csv()
    gap_reporter.export_inventory_json()

    try:
        evaluator = Evaluator()
        gt_records = evaluator.load_ground_truth(DEFAULT_GROUND_TRUTH_PATH)
        eval_summary = evaluator.evaluate(scan_report.all_field_results, gt_records)
        errors = evaluator.extract_error_records(scan_report.all_field_results, gt_records)

        eval_reporter = EvaluationReporter()
        eval_reporter.export_summary_json(eval_summary)
        eval_reporter.export_per_class_csv(eval_summary.per_class_metrics)
        eval_reporter.export_confusion_matrix_csv(eval_summary.confusion_matrix)
        eval_reporter.export_errors_csv(errors)
    except Exception as eval_err:
        logger.warning("Evaluation update skipped or partial: %s", eval_err)

    return inventory_records, summary


# ---------------------------------------------------------------------------
# 3. Available Data Sources Preview (Non-scanning)
# ---------------------------------------------------------------------------
@app.get("/api/data-sources", response_model=DataSourcesResponse)
def get_data_sources() -> DataSourcesResponse:
    """
    Returns available data sources (CSV files and SQL tables) with schema metadata
    WITHOUT executing any discovery scan or pipeline recalculation.
    """
    csv_dir = PROJECT_ROOT / "data" / "csv"
    sql_dir = PROJECT_ROOT / "data" / "sql"

    csv_items: list[DataSourceItem] = []
    sql_items: list[DataSourceItem] = []
    registry = get_parser_registry()

    # 1. Inspect CSV files
    if csv_dir.exists():
        for p in sorted(csv_dir.glob("*.csv")):
            badge_info = registry.get_format_badge_info(p.name)
            try:
                stat = p.stat()
                with open(p, "r", encoding="utf-8", errors="replace") as f:
                    reader = csv.reader(f)
                    header = next(reader, [])
                    rows = sum(1 for _ in reader)
                columns = [c.strip() for c in header if c.strip()]
                csv_items.append(
                    DataSourceItem(
                        source_name=p.name,
                        source_type="CSV File",
                        file_name=p.name,
                        file_size_bytes=stat.st_size,
                        row_count=rows,
                        columns_count=len(columns),
                        columns=columns,
                        schema_preview=", ".join(columns[:6]) + ("..." if len(columns) > 6 else ""),
                        status="Available",
                        is_custom=p.name not in DEFAULT_SYSTEM_DATASETS,
                        badge_label=badge_info["badge"],
                        badge_color=badge_info["color"],
                        format_group=badge_info["group"],
                    )
                )
            except Exception as e:
                logger.warning("Error reading CSV metadata %s: %s", p.name, e)
                csv_items.append(
                    DataSourceItem(
                        source_name=p.name,
                        source_type="CSV File",
                        file_name=p.name,
                        columns_count=0,
                        columns=[],
                        status="Unavailable",
                        is_custom=p.name not in DEFAULT_SYSTEM_DATASETS,
                        badge_label=badge_info["badge"],
                        badge_color=badge_info["color"],
                        format_group=badge_info["group"],
                    )
                )

    # 2. Inspect multi-format uploaded documents, spreadsheets, logs, and structured files
    if DATA_UPLOADS_DIR.exists():
        for p in sorted(DATA_UPLOADS_DIR.iterdir()):
            if not p.is_file():
                continue
            badge_info = registry.get_format_badge_info(p.name)
            file_type_label = registry.get_file_type(p.name)
            stat = p.stat()
            try:
                parsed = registry.parse_file(p)
                cols = [f.field_name for f in parsed.fields]
                row_cnt = parsed.total_records
                schema_str = ", ".join(cols[:5]) + ("..." if len(cols) > 5 else "")
                if parsed.warnings and not schema_str:
                    schema_str = f"Notice: {parsed.warnings[0]}"
                status_str = "Available"
                csv_items.append(
                    DataSourceItem(
                        source_name=p.name,
                        source_type=file_type_label,
                        file_name=p.name,
                        file_size_bytes=stat.st_size,
                        row_count=row_cnt,
                        columns_count=len(cols),
                        columns=cols,
                        schema_preview=schema_str if schema_str else "(Document text/content)",
                        status=status_str,
                        is_custom=True,
                        badge_label=badge_info["badge"],
                        badge_color=badge_info["color"],
                        format_group=badge_info["group"],
                    )
                )
            except Exception as e:
                logger.warning("Error reading multi-format file metadata %s: %s", p.name, e)
                csv_items.append(
                    DataSourceItem(
                        source_name=p.name,
                        source_type=file_type_label,
                        file_name=p.name,
                        file_size_bytes=stat.st_size,
                        columns_count=0,
                        columns=[],
                        schema_preview=f"Error: {type(e).__name__}",
                        status=f"Unavailable: {str(e)[:40]}",
                        is_custom=True,
                        badge_label=badge_info["badge"],
                        badge_color=badge_info["color"],
                        format_group=badge_info["group"],
                    )
                )

    # 3. Inspect SQLite databases and tables
    if sql_dir.exists():
        db_files = sorted(set(list(sql_dir.glob("*.db")) + list(sql_dir.glob("*.sqlite")) + list(sql_dir.glob("*.sqlite3"))))
        for p in db_files:
            if p.name == "users.db":
                continue
            badge_info = registry.get_format_badge_info(p.name)
            try:
                stat = p.stat()
                conn = sqlite3.connect(p)
                cursor = conn.cursor()
                tables = [
                    r[0]
                    for r in cursor.execute(
                        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                    ).fetchall()
                ]
                for t in sorted(tables):
                    count_res = cursor.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()
                    row_cnt = count_res[0] if count_res else 0
                    cols_info = cursor.execute(f'PRAGMA table_info("{t}")').fetchall()
                    col_names = [ci[1] for ci in cols_info]
                    schema_parts = [f"{ci[1]} ({ci[2] or 'TEXT'})" for ci in cols_info]
                    schema_str = ", ".join(schema_parts[:5]) + ("..." if len(schema_parts) > 5 else "")

                    sql_items.append(
                        DataSourceItem(
                            source_name=f"{p.name}:{t}",
                            source_type="SQL Table",
                            table_name=t,
                            db_file=p.name,
                            file_size_bytes=stat.st_size,
                            row_count=row_cnt,
                            columns_count=len(col_names),
                            columns=col_names,
                            schema_preview=schema_str,
                            status="Available",
                            is_custom=p.name not in DEFAULT_SYSTEM_DATASETS,
                            badge_label=badge_info["badge"],
                            badge_color=badge_info["color"],
                            format_group=badge_info["group"],
                        )
                    )
                conn.close()
            except Exception as e:
                logger.warning("Error reading SQL metadata %s: %s", p.name, e)

    return DataSourcesResponse(
        status="success",
        message="Review your available data sources, then click Run Full Scan to begin analysis.",
        total_sources=len(csv_items) + len(sql_items),
        csv_count=len(csv_items),
        sql_count=len(sql_items),
        csv_files=csv_items,
        sql_tables=sql_items,
        scan_status=_SCAN_STATE["status"],
        last_scan_time=_SCAN_STATE.get("last_scan_time"),
    )


@app.get("/api/supported-formats")
def get_supported_formats():
    """Returns the comprehensive catalog of supported file formats and extensions."""
    reg = get_parser_registry()
    return {
        "status": "success",
        "catalog": reg.get_supported_formats_catalog(),
        "extensions": sorted(reg.get_supported_extensions()),
        "count": len(reg.get_supported_extensions()),
    }


@app.get("/api/scan/status", response_model=ScanStatusResponse)
def get_scan_status() -> ScanStatusResponse:
    """Returns current scan execution status (pending, running, completed, failed)."""
    return ScanStatusResponse(
        status=_SCAN_STATE["status"],
        message=_SCAN_STATE["message"],
        last_scan_time=_SCAN_STATE["last_scan_time"],
        last_scan_duration_ms=_SCAN_STATE["last_scan_duration_ms"],
        scanned_fields_count=_SCAN_STATE["scanned_fields_count"],
        detected_candidates_count=_SCAN_STATE["detected_candidates_count"],
        review_required_count=_SCAN_STATE["review_required_count"],
        error=_SCAN_STATE["error"],
    )


# ---------------------------------------------------------------------------
# 4. Trigger Scanner Endpoint
# ---------------------------------------------------------------------------
@app.post("/api/scan", response_model=ScanTriggerResponse)
def trigger_scan() -> ScanTriggerResponse:
    """
    Executes actual personal-data scanner across CSV datasets and SQLite database.
    Does not use mock or hardcoded results.
    Prevents concurrent duplicate scan executions using a thread lock.
    """
    logger.info("[API SCAN] Received POST /api/scan request.")
    acquired = _SCAN_LOCK.acquire(blocking=False)
    if not acquired:
        logger.warning("[API SCAN] Rejected concurrent scan request: scan already in progress.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A scan is already in progress. Please wait for it to complete.",
        )

    start_ts = datetime.now(timezone.utc)
    _SCAN_STATE["status"] = "running"
    _SCAN_STATE["message"] = "Scanning CSV files and SQLite database tables..."
    _SCAN_STATE["error"] = None

    try:
        service = ScannerService()
        report = service.run_full_scan()

        csv_names = [cr.source_name for cr in report.csv_results]
        sql_names = [f"{sr.db_name}:{tbl}" for sr in report.sql_results for tbl in sr.tables.keys()]
        file_names = [fr.source_name for fr in report.file_results]

        logger.info("[API SCAN] Synchronizing evidence inventory and evaluation reports with scan findings...")
        _sync_pipeline_reports(report)
        logger.info("[API SCAN] Reports synchronized successfully.")

        duration_ms = int((datetime.now(timezone.utc) - start_ts).total_seconds() * 1000)
        _SCAN_STATE["status"] = "completed"
        _SCAN_STATE["message"] = f"Scan completed successfully across {len(report.all_field_results)} fields."
        _SCAN_STATE["last_scan_time"] = datetime.now(timezone.utc).isoformat()
        _SCAN_STATE["last_scan_duration_ms"] = duration_ms
        _SCAN_STATE["scanned_fields_count"] = len(report.all_field_results)
        _SCAN_STATE["detected_candidates_count"] = len(report.all_detected)
        _SCAN_STATE["review_required_count"] = len(report.all_review_required)

        logger.info(
            "[API SCAN] Scan completed successfully in %d ms (%d fields, %d candidates).",
            duration_ms,
            len(report.all_field_results),
            len(report.all_detected),
        )

        return ScanTriggerResponse(
            status="completed",
            message="Scanner executed successfully across all data sources.",
            scanned_fields_count=len(report.all_field_results),
            detected_candidates_count=len(report.all_detected),
            review_required_count=len(report.all_review_required),
            csv_sources_scanned=csv_names,
            sql_sources_scanned=sql_names,
            file_sources_scanned=file_names,
        )
    except Exception as e:
        logger.error("[API SCAN] Scan execution failed: %s", e, exc_info=True)
        _SCAN_STATE["status"] = "failed"
        _SCAN_STATE["error"] = str(e)
        _SCAN_STATE["message"] = f"Scan failed: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Scan execution error: {str(e)}",
        )
    finally:
        _SCAN_LOCK.release()


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
    logger.info("[API ANALYZE] Received POST /api/analyze request. Starting pipeline execution.")
    acquired = _SCAN_LOCK.acquire(blocking=False)
    if not acquired:
        logger.warning("[API ANALYZE] Rejected concurrent request: scan or analysis already in progress.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A scan or analysis pipeline is already in progress. Please wait for it to complete.",
        )

    start_ts = datetime.now(timezone.utc)
    _SCAN_STATE["status"] = "running"
    _SCAN_STATE["message"] = "Executing governance mapping, gap analysis, and evaluation pipeline..."
    _SCAN_STATE["error"] = None

    try:
        service = ScannerService()
        scan_report = service.run_full_scan()
        inventory_records, summary = _sync_pipeline_reports(scan_report)

        duration_ms = int((datetime.now(timezone.utc) - start_ts).total_seconds() * 1000)
        _SCAN_STATE["status"] = "completed"
        _SCAN_STATE["message"] = f"Pipeline analysis completed successfully across {len(scan_report.all_field_results)} fields."
        _SCAN_STATE["last_scan_time"] = datetime.now(timezone.utc).isoformat()
        _SCAN_STATE["last_scan_duration_ms"] = duration_ms
        _SCAN_STATE["scanned_fields_count"] = len(scan_report.all_field_results)
        _SCAN_STATE["detected_candidates_count"] = len(scan_report.all_detected)
        _SCAN_STATE["review_required_count"] = len(scan_report.all_review_required)

        logger.info(
            "[API ANALYZE] Pipeline completed in %d ms (%d inventory records, %d evidence gaps).",
            duration_ms,
            len(inventory_records),
            summary.total_gap_count,
        )

        return AnalyzeTriggerResponse(
            status="completed",
            message="Evidence inventory, gap analysis, and evaluation updated successfully.",
            inventory_count=len(inventory_records),
            complete_count=summary.complete_count,
            total_gaps_count=summary.total_gap_count,
            gap_breakdown=summary.gaps_by_status,
            reports_updated=list(APPROVED_REPORTS.keys()),
            scanned_fields_count=len(scan_report.all_field_results),
            detected_candidates_count=len(scan_report.all_detected),
        )
    except Exception as e:
        logger.error("[API ANALYZE] Pipeline execution failed: %s", e, exc_info=True)
        _SCAN_STATE["status"] = "failed"
        _SCAN_STATE["error"] = str(e)
        _SCAN_STATE["message"] = f"Pipeline execution failed: {str(e)}"
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Analysis pipeline error: {str(e)}",
        )
    finally:
        _SCAN_LOCK.release()


# ---------------------------------------------------------------------------
# 5. Data Upload & Custom Dataset Management Endpoints
# ---------------------------------------------------------------------------
@app.post("/api/upload", response_model=FileUploadResponse)
async def upload_data_file(
    request: Request,
    file: UploadFile = File(...),
    auto_scan: bool = Form(True),
) -> FileUploadResponse:
    """
    Accepts, validates, and processes custom data files across 26 common formats:
    PDF, Word (DOCX/DOC), PowerPoint (PPTX), Spreadsheets (XLSX, XLS, ODS),
    Delimited (CSV, TSV), Structured (JSON, JSONL, XML),
    Logs & Config (LOG, YAML, INI, CONF), Email (EML, MBOX), and SQLite databases (.db, .sqlite).

    Applies security controls: 25MB ceiling, signature/magic-bytes verification,
    path traversal sanitization, and macro/executable rejection.
    Optionally executes personal data detection immediately and synchronizes the evidence inventory.
    """
    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No filename provided in upload payload.",
        )

    clean_basename = Path(file.filename).name.strip()
    ext = Path(clean_basename).suffix.lower()
    registry = get_parser_registry()

    if not registry.is_supported(clean_basename):
        supported_list = ", ".join(sorted(registry.get_supported_extensions()))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported file format '{ext}'. PrivSight supports 26 common file formats across "
                f"Documents, Spreadsheets, Structured data, Logs, Configs, Email, and Databases: {supported_list}"
            ),
        )

    # Sanitize filename (alphanumeric, underscores, hyphens, and extension)
    stem = re.sub(r"[^a-zA-Z0-9_\-]", "_", Path(clean_basename).stem)
    if not stem:
        stem = f"uploaded_{uuid.uuid4().hex[:6]}"
    safe_filename = f"{stem}{ext}"

    # Determine storage directory based on format
    if ext == ".csv":
        target_dir = PROJECT_ROOT / "data" / "csv"
        file_type = "csv"
    elif ext in {".db", ".sqlite", ".sqlite3"}:
        target_dir = PROJECT_ROOT / "data" / "sql"
        file_type = "sqlite"
    else:
        target_dir = DATA_UPLOADS_DIR
        file_type = registry.get_format_badge_info(safe_filename)["badge"].lower()

    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / safe_filename

    # Read content chunk-by-chunk with 25MB ceiling
    total_bytes = 0
    chunks = []
    while True:
        chunk = await file.read(64 * 1024)  # 64KB chunks
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > MAX_UPLOAD_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Uploaded file exceeds maximum allowed size limit of {MAX_UPLOAD_SIZE // (1024 * 1024)} MB.",
            )
        chunks.append(chunk)

    if total_bytes == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="The uploaded file is empty (0 bytes).",
        )

    content = b"".join(chunks)

    # File signature and content integrity verification
    try:
        registry.validate_file_content(content[:4096], clean_basename)
    except CorruptedFileError as cfe:
        if ext == ".csv":
            err_msg = f"Invalid CSV format: {str(cfe)}"
        elif ext in {".db", ".sqlite", ".sqlite3"}:
            err_msg = f"Invalid SQLite database: {str(cfe)}"
        else:
            err_msg = f"Corrupted or invalid file signature: {str(cfe)}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as ve:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File validation failed: {str(ve)}",
        )

    # Write securely to target path
    with open(target_path, "wb") as f:
        f.write(content)

    # Parse and scan
    scanned_results = []
    service = ScannerService()
    try:
        if ext == ".csv":
            if auto_scan:
                csv_res = service.scan_csv(target_path)
                scanned_results = csv_res.field_results
        elif ext in {".db", ".sqlite", ".sqlite3"}:
            if auto_scan:
                sql_res = service.scan_sqlite(target_path)
                scanned_results = sql_res.all_results
        else:
            # Structural parsing validation to reject encrypted/corrupted files immediately
            registry.parse_file(target_path)
            if auto_scan:
                file_res = service.scan_file(target_path)
                scanned_results = file_res.field_results

        # Synchronize overall report pipeline
        if auto_scan:
            full_report = service.run_full_scan()
            _sync_pipeline_reports(full_report)
    except EncryptedFileError as efe:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Encrypted or password-protected file detected: {str(efe)}. Decryption is required before scanning.",
        )
    except CorruptedFileError as cfe:
        if target_path.exists():
            target_path.unlink()
        if ext == ".csv":
            err_msg = f"Invalid CSV format: {str(cfe)}"
        elif ext in {".db", ".sqlite", ".sqlite3"}:
            err_msg = f"Invalid SQLite database: {str(cfe)}"
        else:
            err_msg = f"Corrupted or malformed file: {str(cfe)}"
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=err_msg,
        )
    except Exception as e:
        if target_path.exists():
            target_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to extract readable content: {str(e)}",
        )

    detected_items = [
        UploadedFieldInfo(
            field_name=r.field_name,
            detected_class=r.detected_class,
            confidence=round(r.confidence, 3),
            confidence_level=r.confidence_level,
            review_required=r.review_required,
            reason=r.reason,
        )
        for r in scanned_results
        if r.detected_class is not None
    ]

    file_type_resp = "csv" if ext == ".csv" else ("sqlite" if ext in {".db", ".sqlite", ".sqlite3"} else ext.lstrip("."))

    return FileUploadResponse(
        status="success",
        message=f"File '{safe_filename}' uploaded and processed successfully.",
        filename=safe_filename,
        file_type=file_type_resp,
        file_size_bytes=total_bytes,
        scanned_fields_count=len(scanned_results),
        detected_candidates_count=len(detected_items),
        detected_fields=detected_items,
    )


@app.get("/api/uploads", response_model=UploadsListResponse)
def list_uploaded_datasets() -> UploadsListResponse:
    """
    Returns an inventory of all currently available datasets (system datasets and user uploads).
    """
    csv_dir = PROJECT_ROOT / "data" / "csv"
    sql_dir = PROJECT_ROOT / "data" / "sql"
    uploads_dir = DATA_UPLOADS_DIR

    files_list: list[UploadedFileInfo] = []
    registry = get_parser_registry()

    if csv_dir.exists():
        for p in sorted(csv_dir.glob("*.csv")):
            stat = p.stat()
            files_list.append(
                UploadedFileInfo(
                    filename=p.name,
                    file_type="csv",
                    size_bytes=stat.st_size,
                    last_modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    is_custom=p.name not in DEFAULT_SYSTEM_DATASETS,
                )
            )

    if uploads_dir.exists():
        for p in sorted(uploads_dir.iterdir()):
            if not p.is_file():
                continue
            stat = p.stat()
            badge_info = registry.get_format_badge_info(p.name)
            files_list.append(
                UploadedFileInfo(
                    filename=p.name,
                    file_type=badge_info["badge"].lower(),
                    size_bytes=stat.st_size,
                    last_modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    is_custom=True,
                )
            )

    if sql_dir.exists():
        for p in sorted(list(sql_dir.glob("*.db")) + list(sql_dir.glob("*.sqlite")) + list(sql_dir.glob("*.sqlite3"))):
            if p.name == "users.db":
                continue
            stat = p.stat()
            files_list.append(
                UploadedFileInfo(
                    filename=p.name,
                    file_type="sqlite",
                    size_bytes=stat.st_size,
                    last_modified=datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                    is_custom=p.name not in DEFAULT_SYSTEM_DATASETS,
                )
            )

    return UploadsListResponse(
        status="success",
        total_files=len(files_list),
        files=files_list,
    )


@app.delete("/api/uploads/{filename}")
def delete_uploaded_dataset(filename: str):
    """
    Safely deletes a custom uploaded dataset file and refreshes the evidence pipeline.
    System default datasets are protected from deletion.
    """
    clean_name = Path(filename).name
    if clean_name in DEFAULT_SYSTEM_DATASETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot delete system default dataset '{clean_name}'.",
        )

    csv_path = PROJECT_ROOT / "data" / "csv" / clean_name
    upload_path = DATA_UPLOADS_DIR / clean_name
    sql_path = PROJECT_ROOT / "data" / "sql" / clean_name

    deleted = False
    if csv_path.exists():
        csv_path.unlink()
        deleted = True
    elif upload_path.exists():
        upload_path.unlink()
        deleted = True
    elif sql_path.exists():
        sql_path.unlink()
        deleted = True

    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Dataset file '{clean_name}' not found.",
        )

    # Re-sync pipeline after file removal
    service = ScannerService()
    full_report = service.run_full_scan()
    _sync_pipeline_reports(full_report)

    return {
        "status": "success",
        "message": f"Dataset '{clean_name}' removed and evidence inventory updated.",
    }


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

    @app.get("/tracera", include_in_schema=False)
    @app.get("/tracera.html", include_in_schema=False)
    def serve_frontend_tracera(request: Request):
        """Serves the dedicated TRACERA AI Relationship Intelligence Assistant page (protected)."""
        return _require_auth_page(request, "tracera.html")

    @app.get("/relationship-explorer", include_in_schema=False)
    @app.get("/relationship-explorer.html", include_in_schema=False)
    def serve_frontend_relationship_explorer(request: Request):
        """Backwards-compatible route redirecting to TRACERA."""
        return _require_auth_page(request, "tracera.html")

    @app.get("/style.css", include_in_schema=False)
    def serve_direct_style_css():
        """Direct fallback route for style.css to prevent 404s when referenced without /static."""
        return FileResponse(str(FRONTEND_DIR / "style.css"), media_type="text/css")

    @app.get("/vendor/{path:path}", include_in_schema=False)
    def serve_direct_vendor(path: str):
        """Direct fallback route for vendor assets to prevent 404s when referenced without /static."""
        target = FRONTEND_DIR / "vendor" / path
        if target.exists():
            return FileResponse(str(target))
        return JSONResponse(status_code=404, content={"detail": f"Vendor asset '{path}' not found"})

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
