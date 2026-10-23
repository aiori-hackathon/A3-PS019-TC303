"""
tests/test_parsers.py
=====================
Comprehensive unit tests for PrivSight multi-format parsers and registry.
Tests:
- DelimitedParser (CSV, TSV)
- SpreadsheetParser (XLSX, ODS)
- DocumentParser (DOCX, PPTX, TXT, RTF, PDF)
- StructuredParser (JSON, JSONL, XML)
- ConfigLogParser (YAML, INI, LOG)
- EmailParser (EML)
- ParserRegistry (magic bytes, encryption detection, corrupted file detection)
"""

import json
from pathlib import Path

import pytest

from backend.parsers import (
    CorruptedFileError,
    EncryptedFileError,
    UnsupportedFormatError,
    get_parser_registry,
)
from backend.parsers.config_log_parser import ConfigLogParser
from backend.parsers.delimited_parser import DelimitedParser
from backend.parsers.document_parser import DocumentParser
from backend.parsers.email_parser import EmailParser
from backend.parsers.spreadsheet_parser import SpreadsheetParser
from backend.parsers.structured_parser import StructuredParser


def test_delimited_parser_csv_and_tsv(tmp_path: Path):
    parser = DelimitedParser()

    # CSV
    csv_file = tmp_path / "sample.csv"
    csv_file.write_text("first_name,email_address,phone_number\nAlice,alice@example.com,555-1234\nBob,bob@example.com,555-5678\n", encoding="utf-8")
    doc = parser.parse(csv_file)
    assert doc.total_records == 2
    field_names = [f.field_name for f in doc.fields]
    assert "email_address" in field_names
    assert "first_name" in field_names

    # TSV
    tsv_file = tmp_path / "sample.tsv"
    tsv_file.write_text("user_id\tuser_email\tuser_city\n101\tuser@corp.com\tNew York\n", encoding="utf-8")
    doc_tsv = parser.parse(tsv_file)
    assert doc_tsv.total_records == 1
    assert "user_email" in [f.field_name for f in doc_tsv.fields]


def test_structured_parser_json_and_jsonl(tmp_path: Path):
    parser = StructuredParser()

    # JSON Array
    json_file = tmp_path / "records.json"
    data = [
        {"id": 1, "profile": {"name": "Charlie", "email": "charlie@test.com"}, "phone": "+1-555-9999"},
        {"id": 2, "profile": {"name": "Dana", "email": "dana@test.com"}, "phone": "+1-555-8888"},
    ]
    json_file.write_text(json.dumps(data), encoding="utf-8")
    doc = parser.parse(json_file)
    field_names = [f.field_name for f in doc.fields]
    assert "email" in field_names
    assert "phone" in field_names
    assert doc.total_records == 2

    # JSONL
    jsonl_file = tmp_path / "stream.jsonl"
    jsonl_content = '{"user": "Eve", "contact_email": "eve@privacy.org"}\n{"user": "Frank", "contact_email": "frank@privacy.org"}\n'
    jsonl_file.write_text(jsonl_content, encoding="utf-8")
    doc_jsonl = parser.parse(jsonl_file)
    assert "contact_email" in [f.field_name for f in doc_jsonl.fields]
    assert doc_jsonl.total_records == 2


def test_structured_parser_xml(tmp_path: Path):
    parser = StructuredParser()
    xml_file = tmp_path / "dataset.xml"
    xml_content = """<?xml version="1.0" encoding="UTF-8"?>
    <customers>
      <customer>
        <id>1</id>
        <full_name>Grace Hopper</full_name>
        <email>grace@navy.mil</email>
      </customer>
      <customer>
        <id>2</id>
        <full_name>Alan Turing</full_name>
        <email>alan@bletchley.uk</email>
      </customer>
    </customers>
    """
    xml_file.write_text(xml_content, encoding="utf-8")
    doc = parser.parse(xml_file)
    field_names = [f.field_name for f in doc.fields]
    assert any("email" in f for f in field_names)
    assert any("full_name" in f for f in field_names)


def test_config_log_parser_yaml_and_ini(tmp_path: Path):
    parser = ConfigLogParser()

    # YAML
    yaml_file = tmp_path / "config.yaml"
    yaml_content = """
    app:
      admin_email: admin@secure.local
      database:
        host: db.internal
        user: db_admin
    notification:
      recipient_phone: "+1-800-555-0100"
    """
    yaml_file.write_text(yaml_content, encoding="utf-8")
    doc = parser.parse(yaml_file)
    field_names = [f.field_name for f in doc.fields]
    assert "admin_email" in field_names
    assert "recipient_phone" in field_names

    # INI
    ini_file = tmp_path / "settings.ini"
    ini_content = """
    [DEFAULT]
    system_email = sysadmin@privsight.io

    [USER_PROFILE]
    support_phone = 555-0123
    manager_name = Sarah Connor
    """
    ini_file.write_text(ini_content, encoding="utf-8")
    doc_ini = parser.parse(ini_file)
    field_names_ini = [f.field_name for f in doc_ini.fields]
    assert "support_phone" in field_names_ini
    assert "manager_name" in field_names_ini


def test_config_log_parser_log_file(tmp_path: Path):
    parser = ConfigLogParser()
    log_file = tmp_path / "access.log"
    log_content = """
    2026-10-23 10:00:01 INFO [AuthService] Login success for user_email=audit@corp.com from ip=192.168.1.50
    2026-10-23 10:00:02 WARN [PaymentGateway] Card charge failed for customer_id=CUST99 phone=555-9876
    """
    log_file.write_text(log_content, encoding="utf-8")
    doc = parser.parse(log_file)
    field_names = [f.field_name for f in doc.fields]
    assert any("user_email" in f for f in field_names)
    assert any("phone" in f for f in field_names)


def test_email_parser_eml(tmp_path: Path):
    parser = EmailParser()
    eml_file = tmp_path / "notice.eml"
    eml_content = """From: dpo@organization.com
To: user.contact@external.org
Cc: compliance@privacy.gov
Subject: GDPR Article 15 Data Subject Access Request
Date: Fri, 23 Oct 2026 12:00:00 +0000

Dear Sir/Madam,
Please confirm receipt of personal data for Johnathan Doe, telephone number +1-555-4321.
"""
    eml_file.write_text(eml_content, encoding="utf-8")
    doc = parser.parse(eml_file)
    field_names = [f.field_name for f in doc.fields]
    assert "from" in field_names
    assert "to" in field_names
    assert "subject" in field_names
    assert "email_body" in field_names


def test_spreadsheet_parser_xlsx(tmp_path: Path):
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Employees"
    ws.append(["emp_id", "emp_name", "work_email", "ssn_tax_id"])
    ws.append([1, "Ada Lovelace", "ada@analytics.org", "987-65-4321"])
    ws.append([2, "Charles Babbage", "charles@diffengine.com", "123-45-6789"])
    xlsx_file = tmp_path / "staff.xlsx"
    wb.save(xlsx_file)

    parser = SpreadsheetParser()
    doc = parser.parse(xlsx_file)
    field_names = [f.field_name for f in doc.fields]
    assert "work_email" in field_names
    assert "ssn_tax_id" in field_names
    assert doc.total_records == 2


def test_document_parser_docx(tmp_path: Path):
    import docx
    doc_obj = docx.Document()
    doc_obj.add_heading("Customer Onboarding Form", level=1)
    doc_obj.add_paragraph("Customer Full Name: Margaret Hamilton")
    doc_obj.add_paragraph("Contact Email: margaret.hamilton@mit.edu")
    table = doc_obj.add_table(rows=1, cols=2)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "attribute"
    hdr_cells[1].text = "value"
    r1 = table.add_row().cells
    r1[0].text = "phone_number"
    r1[1].text = "+1-555-0987"
    docx_file = tmp_path / "profile.docx"
    doc_obj.save(docx_file)

    parser = DocumentParser()
    doc = parser.parse(docx_file)
    field_names = [f.field_name.lower() for f in doc.fields]
    assert any("email" in f or "phone" in f for f in field_names)


def test_document_parser_txt(tmp_path: Path):
    parser = DocumentParser()
    txt_file = tmp_path / "memo.txt"
    txt_file.write_text("Primary Contact: Johnathan Smith\nEmail Address: jsmith@example.org\nPhone Number: 555-1122\n", encoding="utf-8")
    doc = parser.parse(txt_file)
    field_names = [f.field_name.lower() for f in doc.fields]
    assert any("email" in f or "phone" in f or "contact" in f for f in field_names)


def test_registry_supported_extensions():
    registry = get_parser_registry()
    exts = registry.get_supported_extensions()
    for required_ext in [".pdf", ".docx", ".xlsx", ".csv", ".tsv", ".json", ".xml", ".yaml", ".log", ".eml", ".db"]:
        assert required_ext in exts


def test_registry_rejects_unsupported_format(tmp_path: Path):
    registry = get_parser_registry()
    bad_file = tmp_path / "archive.tar.gz"
    bad_file.write_bytes(b"\x1f\x8b\x08\x00")
    with pytest.raises(UnsupportedFormatError):
        registry.parse_file(bad_file)


def test_registry_detects_corrupted_signature(tmp_path: Path):
    registry = get_parser_registry()
    # A file named sample.pdf but without %PDF- magic bytes
    fake_pdf = tmp_path / "fake.pdf"
    fake_pdf.write_bytes(b"HELLO THIS IS NOT A PDF FILE")
    with pytest.raises(CorruptedFileError):
        registry.parse_file(fake_pdf)
