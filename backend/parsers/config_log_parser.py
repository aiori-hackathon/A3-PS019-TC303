"""
backend/parsers/config_log_parser.py
====================================
Parser for configuration files (YAML, INI, CONF) and log files (LOG).
"""

from __future__ import annotations

import configparser
import re
from pathlib import Path
from typing import Any, Optional

from backend.parsers.base import BaseParser, CorruptedFileError, ParsedDocument, ParsedField


class ConfigLogParser(BaseParser):
    """Parses YAML, INI, CONF, CFG, and LOG files."""

    SUPPORTED_EXTENSIONS = {".yaml", ".yml", ".ini", ".conf", ".cfg", ".log"}

    def __init__(self, max_lines: int = 2000) -> None:
        self.max_lines = max_lines

    def can_parse(self, ext: str, mime: Optional[str] = None, header_bytes: Optional[bytes] = None) -> bool:
        return ext.lower() in self.SUPPORTED_EXTENSIONS

    def parse(self, path: Path) -> ParsedDocument:
        path = Path(path)
        file_name = path.name
        ext = path.suffix.lower()

        if ext in {".yaml", ".yml"}:
            return self._parse_yaml(path, file_name)
        elif ext in {".ini", ".conf", ".cfg"}:
            return self._parse_ini(path, file_name, ext.lstrip("."))
        elif ext == ".log":
            return self._parse_log(path, file_name)
        else:
            raise CorruptedFileError(f"Unsupported config/log format '{ext}'", file_name)

    # ------------------------------------------------------------------
    # YAML Parser (ruamel.yaml)
    # ------------------------------------------------------------------
    def _parse_yaml(self, path: Path, file_name: str) -> ParsedDocument:
        try:
            from ruamel.yaml import YAML
            yaml = YAML(typ="safe")
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                data = yaml.load(f)
        except Exception as e:
            raise CorruptedFileError(f"Corrupted or invalid YAML in '{file_name}': {str(e)}", file_name)

        path_values: dict[str, list[str]] = {}
        if isinstance(data, (dict, list)):
            self._flatten_yaml(data, "", path_values)

        fields: list[ParsedField] = []
        for k, vals in path_values.items():
            leaf_name = k.split(".")[-1].replace("[]", "")
            clean_field = re.sub(r"[^a-zA-Z0-9_\-]", "_", leaf_name).strip("_") or k
            fields.append(ParsedField(field_name=clean_field, values=vals, field_path=k))

        return ParsedDocument(
            file_name=file_name,
            file_type="yaml",
            fields=fields,
            total_records=len(fields),
            metadata={"fields_count": len(fields)},
        )

    def _flatten_yaml(self, obj: Any, prefix: str, out: dict[str, list[str]]) -> None:
        if isinstance(obj, dict):
            for k, v in obj.items():
                k_str = str(k).strip()
                new_key = f"{prefix}.{k_str}" if prefix else k_str
                self._flatten_yaml(v, new_key, out)
        elif isinstance(obj, list):
            for item in obj[:50]:
                self._flatten_yaml(item, f"{prefix}[]", out)
        elif obj is not None:
            s_val = str(obj).strip()
            if s_val:
                out.setdefault(prefix, []).append(s_val)

    # ------------------------------------------------------------------
    # INI / CONF Parser
    # ------------------------------------------------------------------
    def _parse_ini(self, path: Path, file_name: str, file_type: str) -> ParsedDocument:
        cp = configparser.ConfigParser()
        fields: list[ParsedField] = []
        total_items = 0

        try:
            cp.read(str(path), encoding="utf-8")
            for section in cp.sections():
                for key, val in cp.items(section):
                    total_items += 1
                    clean_key = re.sub(r"\s+", "_", key.strip())
                    fields.append(
                        ParsedField(
                            field_name=clean_key,
                            values=[val.strip()] if val else [],
                            field_path=f"[{section}].{clean_key}",
                        )
                    )
        except Exception:
            # Fallback to line-by-line key-value parsing if INI header syntax is missing
            try:
                with open(path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                kv_dict: dict[str, list[str]] = {}
                for line in lines[: self.max_lines]:
                    line_s = line.strip()
                    if not line_s or line_s.startswith(("#", ";")):
                        continue
                    if "=" in line_s or ":" in line_s:
                        parts = re.split(r"[:=]", line_s, maxsplit=1)
                        if len(parts) == 2:
                            k = re.sub(r"\s+", "_", parts[0].strip().lower())
                            v = parts[1].strip()
                            if k and v:
                                kv_dict.setdefault(k, []).append(v)
                for k, vals in kv_dict.items():
                    fields.append(ParsedField(field_name=k, values=vals, field_path=k))
                total_items = len(fields)
            except Exception as e:
                raise CorruptedFileError(f"Failed to parse config file '{file_name}': {str(e)}", file_name)

        return ParsedDocument(
            file_name=file_name,
            file_type=file_type,
            fields=fields,
            total_records=total_items,
        )

    # ------------------------------------------------------------------
    # LOG Parser
    # ------------------------------------------------------------------
    def _parse_log(self, path: Path, file_name: str) -> ParsedDocument:
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                lines = [f.readline() for _ in range(self.max_lines)]
        except Exception as e:
            raise CorruptedFileError(f"Failed to read log file '{file_name}': {str(e)}", file_name)

        # Look for key=value or key: value parameters in log lines
        token_pattern = re.compile(r"([A-Za-z0-9_\-]{2,30})[=:]([^\s,;\"]+)")
        kv_data: dict[str, list[str]] = {}
        valid_lines = 0

        for line in lines:
            line_s = line.strip()
            if not line_s:
                continue
            valid_lines += 1
            matches = token_pattern.findall(line_s)
            for k, v in matches:
                clean_k = k.lower().strip()
                clean_v = v.strip().strip("'\"")
                if clean_k and clean_v:
                    kv_data.setdefault(clean_k, []).append(clean_v)

        fields: list[ParsedField] = []
        for k, vals in kv_data.items():
            fields.append(ParsedField(field_name=k, values=vals, field_path=k))

        if not fields and valid_lines > 0:
            fields.append(ParsedField(field_name="log_message", values=[l.strip() for l in lines[:200] if l.strip()], field_path="raw_logs"))

        return ParsedDocument(
            file_name=file_name,
            file_type="log",
            fields=fields,
            total_records=valid_lines,
            metadata={"lines_analyzed": valid_lines},
        )
