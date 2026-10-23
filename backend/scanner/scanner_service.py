"""
backend/scanner/scanner_service.py
====================================
Orchestration layer for PS-019 TC-303.

Provides a single, easy-to-use ScannerService that wires together:
  - PersonalDataDetector  (rules loaded from backend/config/rules.json)
  - CSVScanner            (CSV file scanning)
  - SQLScanner            (SQLite database scanning)

This is the class that will later be connected to FastAPI endpoints.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import pandas as pd

from backend.parsers.registry import get_parser_registry
from backend.scanner.csv_scanner import CSVScanner
from backend.scanner.detector import FieldDetectionResult, PersonalDataDetector
from backend.scanner.sql_scanner import SQLScanner

logger = logging.getLogger("privsight.scanner")

# ---------------------------------------------------------------------------
# Default paths (resolved relative to this file's location in the project)
# ---------------------------------------------------------------------------
_PROJECT_ROOT    = Path(__file__).parent.parent.parent
_DEFAULT_CSV_DIR = _PROJECT_ROOT / "data" / "csv"
_DEFAULT_UPLOADS = _PROJECT_ROOT / "data" / "uploads"
_DEFAULT_DB_PATH = _PROJECT_ROOT / "data" / "sql" / "privacy_demo.db"
_DEFAULT_RULES   = _PROJECT_ROOT / "backend" / "config" / "rules.json"


# ===========================================================================
# Scan result containers
# ===========================================================================

@dataclass
class CSVScanResult:
    """Detection results for a single CSV file."""
    source_path: str
    source_name: str
    field_results: list[FieldDetectionResult] = field(default_factory=list)

    @property
    def detected_fields(self) -> list[FieldDetectionResult]:
        """Fields with a non-None detected_class."""
        return [r for r in self.field_results if r.detected_class is not None]

    @property
    def review_required_fields(self) -> list[FieldDetectionResult]:
        return [r for r in self.field_results if r.review_required]


@dataclass
class FileScanResult:
    """Detection results for any multi-format document (PDF, DOCX, XLSX, JSON, XML, etc.)."""
    source_path: str
    source_name: str
    file_type: str
    field_results: list[FieldDetectionResult] = field(default_factory=list)
    total_records: int = 0
    warnings: list[str] = field(default_factory=list)

    @property
    def detected_fields(self) -> list[FieldDetectionResult]:
        return [r for r in self.field_results if r.detected_class is not None]

    @property
    def review_required_fields(self) -> list[FieldDetectionResult]:
        return [r for r in self.field_results if r.review_required]


@dataclass
class SQLScanResult:
    """Detection results for a single SQLite database (all tables)."""
    source_path: str
    db_name: str
    tables: dict[str, list[FieldDetectionResult]] = field(default_factory=dict)

    @property
    def all_results(self) -> list[FieldDetectionResult]:
        return [r for table_results in self.tables.values() for r in table_results]

    @property
    def detected_fields(self) -> list[FieldDetectionResult]:
        return [r for r in self.all_results if r.detected_class is not None]

    @property
    def review_required_fields(self) -> list[FieldDetectionResult]:
        return [r for r in self.all_results if r.review_required]


@dataclass
class FullScanReport:
    """Aggregated results from one complete scan run across all data formats."""
    csv_results: list[CSVScanResult] = field(default_factory=list)
    sql_results: list[SQLScanResult] = field(default_factory=list)
    file_results: list[FileScanResult] = field(default_factory=list)

    @property
    def all_field_results(self) -> list[FieldDetectionResult]:
        csv_all = [r for cr in self.csv_results for r in cr.field_results]
        sql_all = [r for sr in self.sql_results for r in sr.all_results]
        file_all = [r for fr in self.file_results for r in fr.field_results]
        return csv_all + sql_all + file_all

    @property
    def all_detected(self) -> list[FieldDetectionResult]:
        return [r for r in self.all_field_results if r.detected_class is not None]

    @property
    def all_review_required(self) -> list[FieldDetectionResult]:
        return [r for r in self.all_field_results if r.review_required]

    def detected_by_class(self) -> dict[str, list[FieldDetectionResult]]:
        """Group all detected fields by their data class."""
        grouped: dict[str, list[FieldDetectionResult]] = {}
        for r in self.all_detected:
            grouped.setdefault(r.detected_class, []).append(r)  # type: ignore[arg-type]
        return grouped


# ===========================================================================
# ScannerService
# ===========================================================================

class ScannerService:
    """
    High-level orchestrator that exposes unified scan methods across all formats.

    Internally it instantiates the detector and scanner wrappers,
    delegating document and structured parsing to the ParserRegistry.
    """

    def __init__(
        self,
        rules_path:  Optional[str | Path] = None,
        csv_dir:     Optional[str | Path] = None,
        db_path:     Optional[str | Path] = None,
        uploads_dir: Optional[str | Path] = None,
    ) -> None:
        self._rules_path  = Path(rules_path)  if rules_path  else _DEFAULT_RULES
        self._csv_dir     = Path(csv_dir)     if csv_dir     else _DEFAULT_CSV_DIR
        self._db_path     = Path(db_path)     if db_path     else _DEFAULT_DB_PATH
        self._uploads_dir = Path(uploads_dir) if uploads_dir else _DEFAULT_UPLOADS

        self._uploads_dir.mkdir(parents=True, exist_ok=True)

        # Single shared detector instance
        self._detector = PersonalDataDetector(self._rules_path)

        # Scanner wrappers
        self._csv_scanner = CSVScanner(self._detector)
        self._sql_scanner = SQLScanner(self._detector)

    # ------------------------------------------------------------------

    def scan_csv(self, path: str | Path) -> CSVScanResult:
        """Scan a single CSV file."""
        path = Path(path)
        logger.info("[SCAN ENGINE] Processing CSV source: %s", path.name)
        results = self._csv_scanner.scan(path)
        detected_count = sum(1 for r in results if r.detected_class is not None)
        logger.info(
            "[SCAN ENGINE] Completed CSV source %s: %d fields analyzed, %d PII candidates detected",
            path.name,
            len(results),
            detected_count,
        )
        return CSVScanResult(
            source_path  = str(path),
            source_name  = path.name,
            field_results= results,
        )

    def scan_file(self, path: str | Path) -> FileScanResult:
        """Scan any supported document or structured file format."""
        path = Path(path)
        logger.info("[SCAN ENGINE] Processing multi-format file: %s", path.name)
        registry = get_parser_registry()

        try:
            parsed_doc = registry.parse_file(path)
        except Exception as e:
            logger.warning("[SCAN ENGINE] Failed to parse document %s: %s", path.name, e)
            return FileScanResult(
                source_path=str(path),
                source_name=path.name,
                file_type=registry.get_file_type(path.name),
                field_results=[],
                total_records=0,
                warnings=[f"Parse error: {str(e)}"],
            )

        results: list[FieldDetectionResult] = []
        source_type_label = parsed_doc.file_type.upper()

        for p_field in parsed_doc.fields:
            clean_vals = [str(v) for v in p_field.values if v is not None and str(v).strip() != ""]
            series = pd.Series(clean_vals, dtype=object)

            res = self._detector.detect(
                field_name=p_field.field_name,
                series=series,
                source_type=source_type_label,
                source_name=path.name,
            )
            results.append(res)

        detected_count = sum(1 for r in results if r.detected_class is not None)
        logger.info(
            "[SCAN ENGINE] Completed %s (%s): %d fields analyzed, %d PII candidates detected",
            path.name,
            parsed_doc.file_type,
            len(results),
            detected_count,
        )
        return FileScanResult(
            source_path=str(path),
            source_name=path.name,
            file_type=parsed_doc.file_type,
            field_results=results,
            total_records=parsed_doc.total_records,
            warnings=parsed_doc.warnings,
        )

    def scan_sqlite(self, db_path: Optional[str | Path] = None) -> SQLScanResult:
        """Scan the SQLite database (defaults to data/sql/privacy_demo.db)."""
        db_path = Path(db_path) if db_path else self._db_path
        logger.info("[SCAN ENGINE] Processing SQLite database: %s", db_path.name)
        tables  = self._sql_scanner.scan(db_path)
        for tbl, t_results in tables.items():
            t_detected = sum(1 for r in t_results if r.detected_class is not None)
            logger.info(
                "[SCAN ENGINE] Completed SQL table %s in %s: %d columns analyzed, %d PII candidates detected",
                tbl,
                db_path.name,
                len(t_results),
                t_detected,
            )
        return SQLScanResult(
            source_path = str(db_path),
            db_name     = db_path.name,
            tables      = tables,
        )

    def scan_all_csv(self) -> list[CSVScanResult]:
        """Scan every *.csv file found in the configured csv_dir."""
        csv_files = sorted(self._csv_dir.glob("*.csv"))
        logger.info(
            "[SCAN ENGINE] Discovered %d CSV files to scan: %s",
            len(csv_files),
            [f.name for f in csv_files],
        )
        return [self.scan_csv(f) for f in csv_files]

    def scan_all_files(self) -> list[FileScanResult]:
        """Scan all uploaded multi-format files in data/uploads/ and non-CSVs in data/csv/."""
        registry = get_parser_registry()
        supported_exts = registry.get_supported_extensions() - {".db", ".sqlite", ".sqlite3", ".csv"}

        files_to_scan: list[Path] = []
        if self._uploads_dir.exists():
            for p in sorted(self._uploads_dir.iterdir()):
                if p.is_file() and p.suffix.lower() in supported_exts:
                    files_to_scan.append(p)

        if self._csv_dir.exists():
            for p in sorted(self._csv_dir.iterdir()):
                if p.is_file() and p.suffix.lower() in supported_exts:
                    if p not in files_to_scan:
                        files_to_scan.append(p)

        logger.info(
            "[SCAN ENGINE] Discovered %d multi-format files to scan: %s",
            len(files_to_scan),
            [f.name for f in files_to_scan],
        )
        return [self.scan_file(f) for f in files_to_scan]

    def scan_all_sql(self) -> list[SQLScanResult]:
        """Scan every *.db, *.sqlite, *.sqlite3 file found in data/sql/."""
        sql_dir = self._db_path.parent
        db_files = sorted(set(list(sql_dir.glob("*.db")) + list(sql_dir.glob("*.sqlite")) + list(sql_dir.glob("*.sqlite3"))))
        if not db_files and self._db_path.exists():
            db_files = [self._db_path]
        scan_dbs = [f for f in db_files if f.name != "users.db"]
        logger.info(
            "[SCAN ENGINE] Discovered %d SQLite databases to scan: %s",
            len(scan_dbs),
            [f.name for f in scan_dbs],
        )
        return [self.scan_sqlite(f) for f in scan_dbs]

    def run_full_scan(self) -> FullScanReport:
        """
        Run a complete scan across all supported sources:
        CSVs + SQLite databases + Multi-format files (PDF, DOCX, XLSX, JSON, XML, Logs, etc.).

        Returns a FullScanReport that aggregates every result.
        """
        logger.info("[SCAN ENGINE] >>> Starting full personal-data scan across stored sources")
        report = FullScanReport()
        report.csv_results = self.scan_all_csv()
        report.sql_results = self.scan_all_sql()
        report.file_results = self.scan_all_files()
        logger.info(
            "[SCAN ENGINE] <<< Full scan completed: %d total fields analyzed across %d CSVs, %d SQL databases, and %d document/data files (%d detected candidates, %d review required)",
            len(report.all_field_results),
            len(report.csv_results),
            len(report.sql_results),
            len(report.file_results),
            len(report.all_detected),
            len(report.all_review_required),
        )
        return report

