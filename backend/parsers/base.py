"""
backend/parsers/base.py
=======================
Base data structures and abstract parser interface for PrivSight's
format-aware ingestion pipeline.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional


class ParserError(Exception):
    """Base exception for document parsing failures."""
    def __init__(self, message: str, file_name: Optional[str] = None) -> None:
        super().__init__(message)
        self.message = message
        self.file_name = file_name


class UnsupportedFormatError(ParserError):
    """Raised when an uploaded file format is not supported."""
    pass


class EncryptedFileError(ParserError):
    """Raised when a file is password-protected or encrypted."""
    pass


class CorruptedFileError(ParserError):
    """Raised when a file structure is damaged or truncated."""
    pass


@dataclass
class ParsedField:
    """A structured field or column extracted from a file."""
    field_name: str
    values: list[str] = field(default_factory=list)
    sample_preview: str = ""
    field_path: str = ""

    def __post_init__(self) -> None:
        if not self.sample_preview and self.values:
            preview_items = [str(v).strip() for v in self.values[:3] if str(v).strip()]
            self.sample_preview = ", ".join(preview_items[:3])


@dataclass
class ParsedDocument:
    """The complete result of parsing a document or structured file."""
    file_name: str
    file_type: str                  # e.g., 'pdf', 'docx', 'xlsx', 'json', 'xml', 'csv', 'yaml', etc.
    fields: list[ParsedField] = field(default_factory=list)
    total_records: int = 0          # Number of rows, lines, elements, or pages
    metadata: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    @property
    def field_names(self) -> list[str]:
        return [f.field_name for f in self.fields]

    def get_field(self, name: str) -> Optional[ParsedField]:
        for f in self.fields:
            if f.field_name.lower() == name.lower():
                return f
        return None


class BaseParser(ABC):
    """Abstract base class for all file format parsers."""

    @abstractmethod
    def can_parse(self, ext: str, mime: Optional[str] = None, header_bytes: Optional[bytes] = None) -> bool:
        """Return True if this parser can handle the specified file characteristics."""
        pass

    @abstractmethod
    def parse(self, path: Path) -> ParsedDocument:
        """
        Parse the target file and return a ParsedDocument.
        Must handle errors cleanly, raising EncryptedFileError or CorruptedFileError where appropriate.
        """
        pass
