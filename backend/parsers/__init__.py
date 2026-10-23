"""
backend/parsers/__init__.py
============================
Format-aware data extraction and ingestion engine for PrivSight.
Supports Documents (PDF, DOCX, PPTX, TXT, RTF), Spreadsheets (XLSX, XLS, ODS),
Structured Data (CSV, TSV, JSON, JSONL, XML), Config/Logs (LOG, YAML, INI),
Email (EML, MBOX), and Databases (SQLite).
"""

from backend.parsers.base import (
    ParsedField,
    ParsedDocument,
    ParserError,
    UnsupportedFormatError,
    EncryptedFileError,
    CorruptedFileError,
)
from backend.parsers.registry import ParserRegistry, get_parser_registry

__all__ = [
    "ParsedField",
    "ParsedDocument",
    "ParserError",
    "UnsupportedFormatError",
    "EncryptedFileError",
    "CorruptedFileError",
    "ParserRegistry",
    "get_parser_registry",
]
