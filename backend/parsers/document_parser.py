"""
backend/parsers/document_parser.py
==================================
Parser for document formats: PDF, DOCX, PPTX, TXT, RTF.
Extracts structured tables, key-value records, form fields, and text entities.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from backend.parsers.base import BaseParser, CorruptedFileError, EncryptedFileError, ParsedDocument, ParsedField


class DocumentParser(BaseParser):
    """Parses PDF, DOCX, PPTX, TXT, and RTF documents."""

    SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".pptx", ".txt", ".rtf"}

    def __init__(self, max_pages_or_slides: int = 100) -> None:
        self.max_pages_or_slides = max_pages_or_slides

    def can_parse(self, ext: str, mime: Optional[str] = None, header_bytes: Optional[bytes] = None) -> bool:
        return ext.lower() in self.SUPPORTED_EXTENSIONS

    def parse(self, path: Path) -> ParsedDocument:
        path = Path(path)
        file_name = path.name
        ext = path.suffix.lower()

        if ext == ".pdf":
            return self._parse_pdf(path, file_name)
        elif ext == ".docx":
            return self._parse_docx(path, file_name)
        elif ext == ".pptx":
            return self._parse_pptx(path, file_name)
        elif ext in {".txt", ".rtf"}:
            return self._parse_text(path, file_name, ext.lstrip("."))
        else:
            raise CorruptedFileError(f"Unsupported document format '{ext}'", file_name)

    # ------------------------------------------------------------------
    # 1. PDF Parser (pypdf)
    # ------------------------------------------------------------------
    def _parse_pdf(self, path: Path, file_name: str) -> ParsedDocument:
        try:
            import pypdf
        except ImportError:
            raise CorruptedFileError("pypdf is required to parse PDF documents.", file_name)

        try:
            reader = pypdf.PdfReader(str(path))
        except Exception as e:
            err = str(e).lower()
            if "encrypted" in err or "password" in err:
                raise EncryptedFileError(f"PDF document '{file_name}' is password-protected or encrypted.", file_name)
            raise CorruptedFileError(f"Damaged or invalid PDF file '{file_name}': {str(e)}", file_name)

        if reader.is_encrypted:
            # Try empty password
            try:
                if not reader.decrypt(""):
                    raise EncryptedFileError(f"PDF document '{file_name}' is encrypted and requires a password.", file_name)
            except Exception:
                raise EncryptedFileError(f"PDF document '{file_name}' is encrypted and requires a password.", file_name)

        total_pages = len(reader.pages)
        pages_to_read = min(total_pages, self.max_pages_or_slides)

        extracted_lines: list[str] = []
        for i in range(pages_to_read):
            try:
                page_text = reader.pages[i].extract_text() or ""
                for line in page_text.splitlines():
                    clean_l = line.strip()
                    if clean_l:
                        extracted_lines.append(clean_l)
            except Exception:
                continue

        warnings = []
        if not extracted_lines and total_pages > 0:
            warnings.append(
                "Document appears to contain scanned images or vector graphics with no embedded text layer (OCR required)."
            )

        # Extract structured key-values and labeled patterns
        fields = self._extract_key_values_from_lines(extracted_lines, source_name=file_name)

        # Also inspect document metadata
        meta_dict = {}
        if reader.metadata:
            for k, v in reader.metadata.items():
                if v and isinstance(v, str):
                    clean_k = k.lstrip("/").lower()
                    meta_dict[clean_k] = v
                    if any(target in clean_k for target in ("author", "creator", "producer", "title", "subject")):
                        fields.append(ParsedField(field_name=f"metadata:{clean_k}", values=[v], field_path=f"metadata/{clean_k}"))

        return ParsedDocument(
            file_name=file_name,
            file_type="pdf",
            fields=fields,
            total_records=total_pages,
            metadata={"pages": total_pages, "extracted_lines": len(extracted_lines), **meta_dict},
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # 2. DOCX Parser (python-docx)
    # ------------------------------------------------------------------
    def _parse_docx(self, path: Path, file_name: str) -> ParsedDocument:
        try:
            import docx
        except ImportError:
            raise CorruptedFileError("python-docx is required to parse DOCX documents.", file_name)

        try:
            doc = docx.Document(str(path))
        except Exception as e:
            err = str(e).lower()
            if "encrypted" in err or "password" in err or "ole" in err:
                raise EncryptedFileError(f"Word document '{file_name}' is password-protected or encrypted.", file_name)
            raise CorruptedFileError(f"Corrupted or invalid Word document '{file_name}': {str(e)}", file_name)

        all_fields: list[ParsedField] = []
        lines: list[str] = []

        # Extract paragraphs
        for p in doc.paragraphs:
            txt = p.text.strip()
            if txt:
                lines.append(txt)

        # Extract structured tables
        for t_idx, table in enumerate(doc.tables):
            if not table.rows:
                continue
            header_row = [cell.text.strip() for cell in table.rows[0].cells]
            clean_headers = [re.sub(r"\s+", "_", h) or f"col_{i+1}" for i, h in enumerate(header_row)]
            table_col_vals: dict[str, list[str]] = {h: [] for h in clean_headers}

            for row in table.rows[1:]:
                row_cells = [cell.text.strip() for cell in row.cells]
                for idx, cell_text in enumerate(row_cells):
                    if idx < len(clean_headers) and cell_text:
                        table_col_vals[clean_headers[idx]].append(cell_text)

            prefix = f"Table{t_idx+1}:" if len(doc.tables) > 1 else ""
            for h in clean_headers:
                vals = table_col_vals[h]
                all_fields.append(
                    ParsedField(
                        field_name=f"{prefix}{h}",
                        values=vals,
                        field_path=f"tables[{t_idx}]/{h}",
                    )
                )

        # Extract key-value pairs from paragraph text
        kv_fields = self._extract_key_values_from_lines(lines, source_name=file_name)
        existing_names = {f.field_name.lower() for f in all_fields}
        for kv in kv_fields:
            if kv.field_name.lower() not in existing_names:
                all_fields.append(kv)

        return ParsedDocument(
            file_name=file_name,
            file_type="docx",
            fields=all_fields,
            total_records=len(doc.paragraphs) + len(doc.tables),
            metadata={"paragraphs_count": len(doc.paragraphs), "tables_count": len(doc.tables)},
        )

    # ------------------------------------------------------------------
    # 3. PPTX Parser (python-pptx)
    # ------------------------------------------------------------------
    def _parse_pptx(self, path: Path, file_name: str) -> ParsedDocument:
        try:
            import pptx
        except ImportError:
            raise CorruptedFileError("python-pptx is required to parse PPTX presentations.", file_name)

        try:
            prs = pptx.Presentation(str(path))
        except Exception as e:
            err = str(e).lower()
            if "encrypted" in err or "password" in err:
                raise EncryptedFileError(f"Presentation '{file_name}' is password-protected.", file_name)
            raise CorruptedFileError(f"Corrupted or invalid PowerPoint presentation '{file_name}': {str(e)}", file_name)

        all_fields: list[ParsedField] = []
        lines: list[str] = []

        total_slides = len(prs.slides)
        slides_to_read = min(total_slides, self.max_pages_or_slides)

        for s_idx in range(slides_to_read):
            slide = prs.slides[s_idx]
            for shape in slide.shapes:
                if shape.has_text_frame:
                    for paragraph in shape.text_frame.paragraphs:
                        txt = paragraph.text.strip()
                        if txt:
                            lines.append(txt)
                elif shape.has_table:
                    table = shape.table
                    if not table.rows:
                        continue
                    header = [cell.text.strip() for cell in table.rows[0].cells]
                    clean_headers = [re.sub(r"\s+", "_", h) or f"col_{i+1}" for i, h in enumerate(header)]
                    t_vals: dict[str, list[str]] = {h: [] for h in clean_headers}
                    for row in table.rows[1:]:
                        for idx, cell in enumerate(row.cells):
                            if idx < len(clean_headers) and cell.text.strip():
                                t_vals[clean_headers[idx]].append(cell.text.strip())
                    for h in clean_headers:
                        all_fields.append(
                            ParsedField(
                                field_name=f"Slide{s_idx+1}_{h}",
                                values=t_vals[h],
                                field_path=f"slides[{s_idx}]/{h}",
                            )
                        )

        kv_fields = self._extract_key_values_from_lines(lines, source_name=file_name)
        existing_names = {f.field_name.lower() for f in all_fields}
        for kv in kv_fields:
            if kv.field_name.lower() not in existing_names:
                all_fields.append(kv)

        return ParsedDocument(
            file_name=file_name,
            file_type="pptx",
            fields=all_fields,
            total_records=total_slides,
            metadata={"slides_count": total_slides},
        )

    # ------------------------------------------------------------------
    # 4. Plain Text & RTF Parser
    # ------------------------------------------------------------------
    def _parse_text(self, path: Path, file_name: str, file_type: str) -> ParsedDocument:
        content = None
        for enc in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
            try:
                with open(path, "r", encoding=enc, errors="replace") as f:
                    content = f.read(512 * 1024)
                break
            except Exception:
                continue

        if content is None:
            raise CorruptedFileError(f"Unable to read text file '{file_name}'.", file_name)

        if file_type == "rtf":
            # Strip simple RTF control codes
            content = re.sub(r"\\[a-zA-Z0-9\-]+ ?", "", content)
            content = re.sub(r"[{}]", "", content)

        lines = [line.strip() for line in content.splitlines() if line.strip()]

        fields = self._extract_key_values_from_lines(lines, source_name=file_name)
        return ParsedDocument(
            file_name=file_name,
            file_type=file_type,
            fields=fields,
            total_records=len(lines),
            metadata={"lines_count": len(lines)},
        )

    # ------------------------------------------------------------------
    # Shared Helper: Extract Key-Value Pairs from Unstructured Lines
    # ------------------------------------------------------------------
    @staticmethod
    def _extract_key_values_from_lines(lines: list[str], source_name: str) -> list[ParsedField]:
        """
        Scans lines for structured key: value or key = value pairs,
        e.g. 'Email: alex@example.com', 'Phone = +1-555-0101', 'Full Name: Jane Doe'.
        Also falls back to structured token detection if no labeled keys are found.
        """
        kv_pattern = re.compile(r"^([A-Za-z0-9_\-\s]{2,40})[:=]\s*(.+)$")
        extracted_kv: dict[str, list[str]] = {}

        for line in lines:
            m = kv_pattern.match(line)
            if m:
                k = re.sub(r"\s+", "_", m.group(1).strip().lower())
                v = m.group(2).strip()
                if k and v and len(k) <= 35:
                    extracted_kv.setdefault(k, []).append(v)

        fields: list[ParsedField] = []
        for k, vals in extracted_kv.items():
            fields.append(
                ParsedField(
                    field_name=k,
                    values=vals,
                    field_path=k,
                )
            )

        # If no key-value pairs were found, create a document body field
        if not fields and lines:
            fields.append(
                ParsedField(
                    field_name="document_text",
                    values=lines[:500],
                    field_path="body",
                )
            )

        return fields
