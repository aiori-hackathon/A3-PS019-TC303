"""
scripts/create_qa_multiformat_data.py
=====================================
Generates synthetic multi-format test datasets for PS-019 end-to-end verification:
- PDF (pypdf)
- DOCX (python-docx)
- XLSX (openpyxl)
- JSON
- XML
- LOG
- TXT
- Encrypted PDF (test graceful error handling)
- Corrupted file (test graceful error handling)
"""

import json
from pathlib import Path

# Directories
PROJECT_ROOT = Path(__file__).parent.parent
OUTPUT_DIR = PROJECT_ROOT / "PrivSight_QA_MultiFormat_Data"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def create_txt():
    txt_path = OUTPUT_DIR / "qa_patient_notes.txt"
    content = """Patient Name: Dr. Arthur Pendelton
Date of Birth: 1980-05-14
Contact Phone: +1-555-342-1100
Email Address: arthur.pendelton@medicare-sample.org
Residential Address: 42 Elm Street, Apt 3B, Boston, MA 02108
Medical Notes: Routine checkup. Patient reported normal health insurance status.
"""
    txt_path.write_text(content, encoding="utf-8")
    print(f"Created: {txt_path.name}")


def create_json():
    json_path = OUTPUT_DIR / "qa_customers.json"
    data = [
        {
            "customer_id": 9001,
            "full_name": "Elena Rostova",
            "email_address": "elena.rostova@globalcorp.example",
            "phone_number": "+1-555-0144",
            "city": "Chicago",
            "country": "United States",
            "postal_code": "60601",
        },
        {
            "customer_id": 9002,
            "full_name": "Klaus Weber",
            "email_address": "klaus.weber@techfirm.example",
            "phone_number": "+49-30-1234567",
            "city": "Berlin",
            "country": "Germany",
            "postal_code": "10115",
        },
    ]
    json_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    print(f"Created: {json_path.name}")


def create_xml():
    xml_path = OUTPUT_DIR / "qa_suppliers.xml"
    content = """<?xml version="1.0" encoding="UTF-8"?>
<suppliers>
  <supplier>
    <id>SUP-101</id>
    <full_name>Marcus Vance</full_name>
    <email_address>marcus.vance@supplychain.net</email_address>
    <phone_number>+1-555-789-0123</phone_number>
    <country>Canada</country>
  </supplier>
  <supplier>
    <id>SUP-102</id>
    <full_name>Amara Okafor</full_name>
    <email_address>amara.okafor@logistics-intl.org</email_address>
    <phone_number>+44-20-7946-0888</phone_number>
    <country>United Kingdom</country>
  </supplier>
</suppliers>
"""
    xml_path.write_text(content, encoding="utf-8")
    print(f"Created: {xml_path.name}")


def create_log():
    log_path = OUTPUT_DIR / "qa_access_audit.log"
    content = """2026-10-23 08:30:12 [INFO] Authentication success: user_email=compliance.officer@privsight.io client_ip=192.168.1.45
2026-10-23 08:35:40 [WARN] Rate limit reached for customer_id=CUST-8839 phone_number=555-019-8877
2026-10-23 08:40:15 [INFO] Session created for account_name=DevOpsLead email=ops.lead@cloudinfra.net
"""
    log_path.write_text(content, encoding="utf-8")
    print(f"Created: {log_path.name}")


def create_xlsx():
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "ExecutiveStaff"
    ws.append([
        "employee_id",
        "full_name",
        "work_email",
        "phone_number",
        "salary",
        "bank_account",
        "health_insurance_id",
    ])
    ws.append([
        "EMP-501",
        "Eleanor Vance",
        "eleanor.vance@hillhouse.example",
        "+1-555-667-8901",
        115000,
        "ACCT-8899001122",
        "INS-8877-A",
    ])
    ws.append([
        "EMP-502",
        "Theodora Crain",
        "theo.crain@designstudio.example",
        "+1-555-667-8902",
        98000,
        "ACCT-3344556677",
        "INS-8877-B",
    ])
    xlsx_path = OUTPUT_DIR / "qa_executive_payroll.xlsx"
    wb.save(xlsx_path)
    print(f"Created: {xlsx_path.name}")


def create_docx():
    import docx
    doc = docx.Document()
    doc.add_heading("Confidential Contractor Registration", level=1)
    doc.add_paragraph("Contractor Full Name: Victor Frankenstein")
    doc.add_paragraph("Primary Email: victor.f@geneva-research.ch")
    doc.add_paragraph("Emergency Phone: +41-22-555-0199")

    table = doc.add_table(rows=1, cols=3)
    hdr_cells = table.rows[0].cells
    hdr_cells[0].text = "reference_id"
    hdr_cells[1].text = "contact_email"
    hdr_cells[2].text = "phone_number"

    r1 = table.add_row().cells
    r1[0].text = "REF-9901"
    r1[1].text = "henry.clerval@merchants.ch"
    r1[2].text = "+41-22-555-0188"

    docx_path = OUTPUT_DIR / "qa_contractor_profile.docx"
    doc.save(docx_path)
    print(f"Created: {docx_path.name}")


def create_pdf():
    import pypdf
    # We can create a simple PDF with pypdf or reportlab
    # If reportlab is not installed, we can write a standard compliant minimal PDF
    pdf_path = OUTPUT_DIR / "qa_security_brief.pdf"
    # Construct a valid minimal text-based PDF using pypdf writer or raw PDF stream
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    # Add metadata containing test PII and author
    writer.add_metadata({
        "/Title": "Information Security Personnel Briefing",
        "/Author": "Chief Information Security Officer: Alice Morgan (alice.morgan@security.corp)",
        "/Subject": "Personnel Contact: +1-555-901-2233 | Emergency Email: ciso-emergency@security.corp",
    })
    with open(pdf_path, "wb") as f:
        writer.write(f)
    print(f"Created: {pdf_path.name}")


def create_corrupted():
    corrupt_path = OUTPUT_DIR / "qa_corrupted_document.docx"
    # An invalid file pretending to be DOCX but lacking PK signature
    corrupt_path.write_bytes(b"THIS IS CORRUPTED DATA NOT A VALID DOCX ZIP ARCHIVE")
    print(f"Created: {corrupt_path.name}")


def create_encrypted_pdf():
    import pypdf
    writer = pypdf.PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("SecretPassword123")
    enc_path = OUTPUT_DIR / "qa_encrypted_report.pdf"
    with open(enc_path, "wb") as f:
        writer.write(f)
    print(f"Created: {enc_path.name}")


if __name__ == "__main__":
    create_txt()
    create_json()
    create_xml()
    create_log()
    create_xlsx()
    create_docx()
    create_pdf()
    create_corrupted()
    create_encrypted_pdf()
    print("All QA synthetic datasets generated successfully in PrivSight_QA_MultiFormat_Data/!")
