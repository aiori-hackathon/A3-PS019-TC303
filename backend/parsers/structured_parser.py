"""
backend/parsers/structured_parser.py
====================================
Parser for structured data formats: JSON, JSONL, XML.
Flattens nested keys and XML elements into dot-notated field paths.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional

from backend.parsers.base import BaseParser, CorruptedFileError, ParsedDocument, ParsedField


class StructuredParser(BaseParser):
    """Parses JSON, JSONL, and XML hierarchical data structures."""

    SUPPORTED_EXTENSIONS = {".json", ".jsonl", ".xml"}

    def __init__(self, max_records: int = 1000) -> None:
        self.max_records = max_records

    def can_parse(self, ext: str, mime: Optional[str] = None, header_bytes: Optional[bytes] = None) -> bool:
        return ext.lower() in self.SUPPORTED_EXTENSIONS

    def parse(self, path: Path) -> ParsedDocument:
        path = Path(path)
        file_name = path.name
        ext = path.suffix.lower()

        if ext == ".json":
            return self._parse_json(path, file_name)
        elif ext == ".jsonl":
            return self._parse_jsonl(path, file_name)
        elif ext == ".xml":
            return self._parse_xml(path, file_name)
        else:
            raise CorruptedFileError(f"Unsupported structured format '{ext}'", file_name)

    # ------------------------------------------------------------------
    # JSON Parser
    # ------------------------------------------------------------------
    def _parse_json(self, path: Path, file_name: str) -> ParsedDocument:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = json.load(f)
        except Exception as e:
            raise CorruptedFileError(f"Invalid or corrupted JSON in '{file_name}': {str(e)}", file_name)

        path_values: dict[str, list[str]] = {}
        total_records = 0

        if isinstance(data, list):
            total_records = len(data)
            for item in data[: self.max_records]:
                self._flatten_object(item, "", path_values)
        elif isinstance(data, dict):
            # Check if root has a list of items (e.g. {"users": [...]})
            total_records = 1
            self._flatten_object(data, "", path_values)
        else:
            path_values["value"] = [str(data)]

        fields = self._build_fields_from_dict(path_values)
        return ParsedDocument(
            file_name=file_name,
            file_type="json",
            fields=fields,
            total_records=total_records,
            metadata={"fields_count": len(fields)},
        )

    # ------------------------------------------------------------------
    # JSONL Parser
    # ------------------------------------------------------------------
    def _parse_jsonl(self, path: Path, file_name: str) -> ParsedDocument:
        path_values: dict[str, list[str]] = {}
        count = 0
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                for line in f:
                    line_s = line.strip()
                    if not line_s:
                        continue
                    count += 1
                    try:
                        record = json.loads(line_s)
                        if isinstance(record, dict):
                            self._flatten_object(record, "", path_values)
                    except Exception:
                        continue
                    if count >= self.max_records:
                        break
        except Exception as e:
            raise CorruptedFileError(f"Failed to read JSONL file '{file_name}': {str(e)}", file_name)

        fields = self._build_fields_from_dict(path_values)
        return ParsedDocument(
            file_name=file_name,
            file_type="jsonl",
            fields=fields,
            total_records=count,
            metadata={"lines_processed": count},
        )

    # ------------------------------------------------------------------
    # XML Parser (defusedxml)
    # ------------------------------------------------------------------
    def _parse_xml(self, path: Path, file_name: str) -> ParsedDocument:
        try:
            import defusedxml.ElementTree as ET
        except ImportError:
            import xml.etree.ElementTree as ET

        try:
            tree = ET.parse(str(path))
            root = tree.getroot()
        except Exception as e:
            raise CorruptedFileError(f"Corrupted or invalid XML document in '{file_name}': {str(e)}", file_name)

        path_values: dict[str, list[str]] = {}
        self._traverse_xml(root, root.tag, path_values)

        fields = self._build_fields_from_dict(path_values)
        return ParsedDocument(
            file_name=file_name,
            file_type="xml",
            fields=fields,
            total_records=len(root),
            metadata={"root_tag": root.tag, "total_fields": len(fields)},
        )

    def _traverse_xml(self, elem: Any, current_path: str, path_values: dict[str, list[str]]) -> None:
        # Strip XML namespaces from tag
        tag = re.sub(r"\{.*?\}", "", elem.tag)
        path = f"{current_path}/{tag}" if current_path != tag else tag

        if elem.text and elem.text.strip():
            text_val = elem.text.strip()
            # Leaf node with text
            clean_field = path.split("/")[-1]
            path_values.setdefault(clean_field, []).append(text_val)

        # Inspect attributes
        for attr, attr_val in elem.attrib.items():
            if attr_val and attr_val.strip():
                clean_attr = f"{tag}_{attr}"
                path_values.setdefault(clean_attr, []).append(attr_val.strip())

        for child in elem:
            self._traverse_xml(child, path, path_values)

    # ------------------------------------------------------------------
    # Helpers for recursive object flattening
    # ------------------------------------------------------------------
    def _flatten_object(self, obj: Any, prefix: str, out: dict[str, list[str]]) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                clean_k = re.sub(r"\s+", "_", str(k).strip())
                new_key = f"{prefix}.{clean_k}" if prefix else clean_k
                self._flatten_object(v, new_key, out)
        elif isinstance(obj, list):
            for item in obj[:50]:
                self._flatten_object(item, f"{prefix}[]", out)
        elif obj is not None:
            s_val = str(obj).strip()
            if s_val:
                # Use simplified leaf name for scanner rules while saving full path
                leaf_name = prefix.split(".")[-1].replace("[]", "")
                field_key = leaf_name or prefix
                out.setdefault(field_key, []).append(s_val)

    @staticmethod
    def _build_fields_from_dict(path_values: dict[str, list[str]]) -> list[ParsedField]:
        fields: list[ParsedField] = []
        for k, vals in path_values.items():
            clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", k).strip("_") or "field"
            fields.append(
                ParsedField(
                    field_name=clean_name,
                    values=vals,
                    field_path=k,
                )
            )
        return fields
