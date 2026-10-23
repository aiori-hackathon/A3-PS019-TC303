"""
backend/parsers/delimited_parser.py
===================================
Parser for delimited text formats: CSV, TSV, TAB.
"""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Optional

from backend.parsers.base import BaseParser, CorruptedFileError, ParsedDocument, ParsedField


class DelimitedParser(BaseParser):
    """Parses CSV, TSV, and delimited tabular text files."""

    SUPPORTED_EXTENSIONS = {".csv", ".tsv", ".tab"}

    def __init__(self, max_sample_rows: int = 1000) -> None:
        self.max_sample_rows = max_sample_rows

    def can_parse(self, ext: str, mime: Optional[str] = None, header_bytes: Optional[bytes] = None) -> bool:
        return ext.lower() in self.SUPPORTED_EXTENSIONS

    def parse(self, path: Path) -> ParsedDocument:
        path = Path(path)
        file_name = path.name
        ext = path.suffix.lower()
        file_type = "tsv" if ext in {".tsv", ".tab"} else "csv"

        # Read text with fallback encodings
        content = None
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                with open(path, "r", encoding=enc, errors="replace") as f:
                    content = f.read(512 * 1024)  # 512KB sample
                break
            except Exception:
                continue

        if content is None:
            raise CorruptedFileError(f"Unable to decode text in '{file_name}'.", file_name)

        lines = [line.strip() for line in content.splitlines() if line.strip()]
        if not lines:
            return ParsedDocument(
                file_name=file_name,
                file_type=file_type,
                fields=[],
                total_records=0,
                warnings=["File is empty or contains only whitespace."],
            )

        # Detect delimiter
        first_line = lines[0]
        delimiter = "\t" if ext in {".tsv", ".tab"} else ","
        if ext not in {".tsv", ".tab"}:
            if "\t" in first_line and first_line.count("\t") > first_line.count(","):
                delimiter = "\t"
            elif ";" in first_line and first_line.count(";") > first_line.count(","):
                delimiter = ";"
            elif "|" in first_line and first_line.count("|") > first_line.count(","):
                delimiter = "|"

        try:
            reader = csv.reader(lines, delimiter=delimiter)
            header = next(reader, None)
            if not header:
                raise CorruptedFileError("No header row could be parsed.", file_name)

            clean_headers = [re.sub(r"\s+", "_", h.strip()) or f"column_{i+1}" for i, h in enumerate(header)]
            col_values: dict[str, list[str]] = {h: [] for h in clean_headers}

            row_count = 0
            for row in reader:
                if not row or not any(row):
                    continue
                row_count += 1
                for i, val in enumerate(row):
                    if i < len(clean_headers):
                        h = clean_headers[i]
                        s_val = val.strip()
                        if s_val:
                            col_values[h].append(s_val)
                if row_count >= self.max_sample_rows:
                    break

            parsed_fields: list[ParsedField] = []
            for h in clean_headers:
                vals = col_values[h]
                parsed_fields.append(
                    ParsedField(
                        field_name=h,
                        values=vals,
                        field_path=h,
                    )
                )

            return ParsedDocument(
                file_name=file_name,
                file_type=file_type,
                fields=parsed_fields,
                total_records=row_count,
                metadata={"delimiter": delimiter, "total_columns": len(clean_headers)},
            )
        except Exception as e:
            raise CorruptedFileError(f"Failed to parse delimited data in '{file_name}': {str(e)}", file_name)
