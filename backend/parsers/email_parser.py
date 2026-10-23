"""
backend/parsers/email_parser.py
===============================
Parser for email message formats: EML, MBOX.
Extracts message headers (From, To, Cc, Subject, Date) and message body text.
"""

from __future__ import annotations

import email
import mailbox
import re
from pathlib import Path
from typing import Optional

from backend.parsers.base import BaseParser, CorruptedFileError, ParsedDocument, ParsedField


class EmailParser(BaseParser):
    """Parses EML message files and MBOX mailbox archives."""

    SUPPORTED_EXTENSIONS = {".eml", ".mbox"}

    def __init__(self, max_messages: int = 500) -> None:
        self.max_messages = max_messages

    def can_parse(self, ext: str, mime: Optional[str] = None, header_bytes: Optional[bytes] = None) -> bool:
        return ext.lower() in self.SUPPORTED_EXTENSIONS

    def parse(self, path: Path) -> ParsedDocument:
        path = Path(path)
        file_name = path.name
        ext = path.suffix.lower()

        if ext == ".eml":
            return self._parse_eml(path, file_name)
        elif ext == ".mbox":
            return self._parse_mbox(path, file_name)
        else:
            raise CorruptedFileError(f"Unsupported email format '{ext}'", file_name)

    def _parse_eml(self, path: Path, file_name: str) -> ParsedDocument:
        try:
            with open(path, "rb") as f:
                msg = email.message_from_bytes(f.read())
        except Exception as e:
            raise CorruptedFileError(f"Corrupted or invalid EML file '{file_name}': {str(e)}", file_name)

        header_fields = ["from", "to", "cc", "bcc", "reply-to", "subject", "date"]
        fields: list[ParsedField] = []

        for h in header_fields:
            val = msg.get(h)
            if val:
                clean_name = re.sub(r"[^a-zA-Z0-9_\-]", "_", h).lower()
                fields.append(ParsedField(field_name=clean_name, values=[str(val).strip()], field_path=f"header/{h}"))

        # Extract body text
        body_text = self._extract_body(msg)
        if body_text:
            lines = [l.strip() for l in body_text.splitlines() if l.strip()]
            fields.append(ParsedField(field_name="email_body", values=lines[:100], field_path="body"))

        return ParsedDocument(
            file_name=file_name,
            file_type="eml",
            fields=fields,
            total_records=1,
            metadata={"subject": msg.get("subject", "")},
        )

    def _parse_mbox(self, path: Path, file_name: str) -> ParsedDocument:
        try:
            mbox = mailbox.mbox(str(path))
        except Exception as e:
            raise CorruptedFileError(f"Failed to open MBOX archive '{file_name}': {str(e)}", file_name)

        col_data: dict[str, list[str]] = {
            "from": [],
            "to": [],
            "cc": [],
            "subject": [],
            "date": [],
            "email_body": [],
        }

        count = 0
        try:
            for msg in mbox:
                count += 1
                for h in ("from", "to", "cc", "subject", "date"):
                    val = msg.get(h)
                    if val:
                        col_data[h].append(str(val).strip())
                body = self._extract_body(msg)
                if body:
                    clean_b = body.strip().replace("\n", " ")[:300]
                    col_data["email_body"].append(clean_b)
                if count >= self.max_messages:
                    break
        finally:
            mbox.close()

        fields = [
            ParsedField(field_name=h, values=vals, field_path=f"messages[].{h}")
            for h, vals in col_data.items()
            if vals
        ]

        return ParsedDocument(
            file_name=file_name,
            file_type="mbox",
            fields=fields,
            total_records=count,
            metadata={"messages_count": count},
        )

    @staticmethod
    def _extract_body(msg: Any) -> str:
        body = ""
        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                content_disposition = str(part.get("Content-Disposition"))
                if content_type == "text/plain" and "attachment" not in content_disposition:
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            body += payload.decode("utf-8", errors="replace") + "\n"
                    except Exception:
                        continue
        else:
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    body = payload.decode("utf-8", errors="replace")
            except Exception:
                body = str(msg.get_payload())
        return body
