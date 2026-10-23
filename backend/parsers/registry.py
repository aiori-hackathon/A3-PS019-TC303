"""
backend/parsers/registry.py
===========================
Central format detection, validation, and parser registry for PrivSight.
Validates file signatures, enforces security controls, and routes files
to the correct specialized format parser.
"""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import Any, Optional

from backend.parsers.base import (
    BaseParser,
    CorruptedFileError,
    ParsedDocument,
    UnsupportedFormatError,
)
from backend.parsers.config_log_parser import ConfigLogParser
from backend.parsers.delimited_parser import DelimitedParser
from backend.parsers.document_parser import DocumentParser
from backend.parsers.email_parser import EmailParser
from backend.parsers.spreadsheet_parser import SpreadsheetParser
from backend.parsers.structured_parser import StructuredParser


class ParserRegistry:
    """Central registry and dispatcher for all file parsers."""

    def __init__(self) -> None:
        self.delimited_parser = DelimitedParser()
        self.spreadsheet_parser = SpreadsheetParser()
        self.document_parser = DocumentParser()
        self.structured_parser = StructuredParser()
        self.config_log_parser = ConfigLogParser()
        self.email_parser = EmailParser()

        self._parsers: list[BaseParser] = [
            self.delimited_parser,
            self.spreadsheet_parser,
            self.document_parser,
            self.structured_parser,
            self.config_log_parser,
            self.email_parser,
        ]

        # Magic byte file signatures for security verification
        self._signatures: dict[str, list[bytes]] = {
            ".pdf": [b"%PDF-"],
            ".docx": [b"PK\x03\x04"],
            ".xlsx": [b"PK\x03\x04"],
            ".xlsm": [b"PK\x03\x04"],
            ".pptx": [b"PK\x03\x04"],
            ".ods": [b"PK\x03\x04"],
            ".db": [b"SQLite format 3\x00"],
            ".sqlite": [b"SQLite format 3\x00"],
            ".sqlite3": [b"SQLite format 3\x00"],
        }

    def get_supported_extensions(self) -> set[str]:
        """Returns all recognized file extensions."""
        exts: set[str] = {".db", ".sqlite", ".sqlite3"}
        for p in self._parsers:
            if hasattr(p, "SUPPORTED_EXTENSIONS"):
                exts.update(getattr(p, "SUPPORTED_EXTENSIONS"))
        return exts

    def is_supported(self, filename: str) -> bool:
        """Checks if the filename has a supported extension."""
        ext = Path(filename).suffix.lower()
        return ext in self.get_supported_extensions()

    def get_file_type(self, filename: str) -> str:
        """Returns a canonical format category label for display."""
        ext = Path(filename).suffix.lower()
        if ext in {".csv", ".tsv", ".tab"}:
            return "CSV / Delimited"
        elif ext in {".xlsx", ".xlsm", ".xls", ".ods"}:
            return "Spreadsheet"
        elif ext == ".pdf":
            return "PDF Document"
        elif ext == ".docx":
            return "Word Document"
        elif ext == ".pptx":
            return "Presentation"
        elif ext in {".json", ".jsonl"}:
            return "JSON"
        elif ext == ".xml":
            return "XML"
        elif ext in {".yaml", ".yml"}:
            return "YAML"
        elif ext in {".ini", ".conf", ".cfg"}:
            return "Configuration"
        elif ext == ".log":
            return "Log File"
        elif ext in {".eml", ".mbox"}:
            return "Email Message"
        elif ext in {".txt", ".rtf"}:
            return "Text Document"
        elif ext in {".db", ".sqlite", ".sqlite3"}:
            return "SQLite Database"
        return "Unknown Document"

    def get_format_badge_info(self, filename: str) -> dict[str, str]:
        """Returns badge text, CSS style, and format group for UI rendering."""
        ext = Path(filename).suffix.lower()
        mapping = {
            ".csv": {"badge": "CSV", "color": "#06B6D4", "group": "Delimited"},
            ".tsv": {"badge": "TSV", "color": "#06B6D4", "group": "Delimited"},
            ".tab": {"badge": "TSV", "color": "#06B6D4", "group": "Delimited"},
            ".xlsx": {"badge": "XLSX", "color": "#10B981", "group": "Spreadsheet"},
            ".xlsm": {"badge": "XLSM", "color": "#10B981", "group": "Spreadsheet"},
            ".xls": {"badge": "XLS", "color": "#10B981", "group": "Spreadsheet"},
            ".ods": {"badge": "ODS", "color": "#10B981", "group": "Spreadsheet"},
            ".pdf": {"badge": "PDF", "color": "#EF4444", "group": "Document"},
            ".docx": {"badge": "DOCX", "color": "#3B82F6", "group": "Document"},
            ".pptx": {"badge": "PPTX", "color": "#F97316", "group": "Presentation"},
            ".json": {"badge": "JSON", "color": "#EAB308", "group": "Structured"},
            ".jsonl": {"badge": "JSONL", "color": "#EAB308", "group": "Structured"},
            ".xml": {"badge": "XML", "color": "#8B5CF6", "group": "Structured"},
            ".yaml": {"badge": "YAML", "color": "#A855F7", "group": "Config"},
            ".yml": {"badge": "YAML", "color": "#A855F7", "group": "Config"},
            ".ini": {"badge": "INI", "color": "#64748B", "group": "Config"},
            ".conf": {"badge": "CONF", "color": "#64748B", "group": "Config"},
            ".cfg": {"badge": "CFG", "color": "#64748B", "group": "Config"},
            ".log": {"badge": "LOG", "color": "#EC4899", "group": "Log"},
            ".eml": {"badge": "EML", "color": "#14B8A6", "group": "Email"},
            ".mbox": {"badge": "MBOX", "color": "#14B8A6", "group": "Email"},
            ".txt": {"badge": "TXT", "color": "#94A3B8", "group": "Text"},
            ".rtf": {"badge": "RTF", "color": "#94A3B8", "group": "Text"},
            ".db": {"badge": "SQLite", "color": "#D4A72C", "group": "Database"},
            ".sqlite": {"badge": "SQLite", "color": "#D4A72C", "group": "Database"},
            ".sqlite3": {"badge": "SQLite", "color": "#D4A72C", "group": "Database"},
        }
        return mapping.get(ext, {"badge": ext.upper().lstrip("."), "color": "#A0AEC0", "group": "Other"})

    def validate_file_content(self, content_sample: bytes, filename: str) -> None:
        """
        Validates magic bytes, checks for null bytes in text formats,
        and ensures container files have valid signatures.
        """
        ext = Path(filename).suffix.lower()

        # 1. Magic bytes validation for binary container formats
        if ext in self._signatures:
            expected_headers = self._signatures[ext]
            if not any(content_sample.startswith(h) for h in expected_headers):
                raise CorruptedFileError(
                    f"File '{filename}' does not have a valid '{ext}' signature header. It may be corrupted or renamed.",
                    filename,
                )

        # 2. Text formats should not contain null bytes
        text_extensions = {".csv", ".tsv", ".json", ".jsonl", ".xml", ".yaml", ".yml", ".ini", ".conf", ".cfg", ".log", ".txt", ".rtf"}
        if ext in text_extensions:
            if b"\x00" in content_sample:
                raise CorruptedFileError(
                    f"Invalid text document: binary/null bytes detected in text file '{filename}'.",
                    filename,
                )

    def parse_file(self, path: Path) -> ParsedDocument:
        """Finds the appropriate parser and parses the target file."""
        path = Path(path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {path}")

        ext = path.suffix.lower()
        if not self.is_supported(path.name):
            raise UnsupportedFormatError(
                f"Unsupported file format '{ext}'. Supported formats: {', '.join(sorted(self.get_supported_extensions()))}",
                path.name,
            )

        # Check file signature
        try:
            with open(path, "rb") as f:
                header = f.read(512)
            self.validate_file_content(header, path.name)
        except Exception as e:
            if isinstance(e, (CorruptedFileError, UnsupportedFormatError)):
                raise
            raise CorruptedFileError(f"Error inspecting file '{path.name}': {str(e)}", path.name)

        # Dispatch to parser
        for parser in self._parsers:
            if parser.can_parse(ext):
                return parser.parse(path)

        raise UnsupportedFormatError(f"No parser available for format '{ext}'", path.name)

    def get_supported_formats_catalog(self) -> list[dict[str, Any]]:
        """Returns structured metadata on all supported formats for the frontend."""
        return [
            {
                "category": "Documents",
                "formats": ["PDF (.pdf)", "Word (.docx)", "PowerPoint (.pptx)", "Text (.txt, .rtf)"],
                "description": "Extracts tables, key-value fields, paragraphs, and document metadata.",
            },
            {
                "category": "Spreadsheets",
                "formats": ["Excel (.xlsx, .xlsm, .xls)", "OpenDocument (.ods)"],
                "description": "Multi-sheet workbook parsing with column header and cell value extraction.",
            },
            {
                "category": "Delimited & Structured",
                "formats": ["CSV (.csv)", "TSV (.tsv, .tab)", "JSON (.json, .jsonl)", "XML (.xml)"],
                "description": "Delimiter detection, hierarchical key flattening, and element traversal.",
            },
            {
                "category": "Logs & Configuration",
                "formats": ["LOG (.log)", "YAML (.yaml, .yml)", "INI (.ini, .conf, .cfg)"],
                "description": "Configuration section mapping and log parameter extraction.",
            },
            {
                "category": "Email",
                "formats": ["EML (.eml)", "MBOX (.mbox)"],
                "description": "Header parsing (From, To, Cc, Subject) and plain text body analysis.",
            },
            {
                "category": "Databases",
                "formats": ["SQLite (.db, .sqlite, .sqlite3)"],
                "description": "Relational schema discovery and table column scanning.",
            },
        ]


_REGISTRY_INSTANCE: Optional[ParserRegistry] = None


def get_parser_registry() -> ParserRegistry:
    """Returns singleton instance of ParserRegistry."""
    global _REGISTRY_INSTANCE
    if _REGISTRY_INSTANCE is None:
        _REGISTRY_INSTANCE = ParserRegistry()
    return _REGISTRY_INSTANCE
