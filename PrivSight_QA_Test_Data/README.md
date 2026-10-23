# PrivSight QA Live Test Data

This directory contains standalone, synthetic QA test datasets created for end-to-end verification of the PrivSight Personal-Data Discovery & Evidence Inventory Platform (PS-019 / TC-303).

> **Privacy & Ethics Assurance**: All names, email addresses (`@example.com`), phone numbers (`+1-555-XXXX`), and identifiers in these datasets are 100% fictional and synthetic. No real personal data is contained herein.

---

## 1. Datasets Overview

### A. `qa_customers.csv` (12 records, 10 columns)
Simulates an e-commerce customer master registry.
- **Expected Personal-Data (PII) Detections**:
  - `full_name` -> **Identity** (Rule keyword match)
  - `email` -> **Contact** (RFC-5321 pattern & keyword match)
  - `phone` -> **Contact** (E.164 phone pattern & keyword match)
  - `date_of_birth` -> **Identity** (ISO-8601 date pattern & keyword match)
  - `city` -> **Location** (Keyword match)
  - `country` -> **Location** (Keyword match)
- **Expected Non-PII Fields (Filtered / Low Confidence)**:
  - `customer_id`, `account_status`, `signup_timestamp`, `newsletter_subscribed`

### B. `qa_transactions.csv` (12 records, 9 columns)
Simulates an online payment and order processing ledger.
- **Expected Personal-Data (PII) Detections**:
  - `billing_email` -> **Contact** (Email pattern & keyword match)
  - `billing_phone` -> **Contact** (Phone pattern & keyword match)
  - `amount` -> **Financial** (Currency decimal pattern & keyword match)
- **Expected Non-PII Fields (Filtered / Low Confidence)**:
  - `transaction_id`, `customer_id`, `payment_method`, `order_status`, `store_channel`, `item_count`

### C. `qa_employees.csv` (12 records, 9 columns)
Simulates an internal HR staff and payroll directory.
- **Expected Personal-Data (PII) Detections**:
  - `employee_name` -> **Identity** (Keyword match)
  - `work_email` -> **Contact** (Email pattern & token keyword match)
  - `mobile_number` -> **Contact** (Phone pattern & keyword match)
  - `salary` -> **Financial** (Decimal currency pattern & keyword match)
- **Expected Non-PII Fields (Filtered / Low Confidence)**:
  - `employee_id`, `department`, `job_title`, `office_badge_id`, `employment_type`

---

## 2. Evidence Gap Scenarios & Governance Design

When these files are scanned, PrivSight correlates discovered fields against declared governance metadata:

| File | Field | Declared Purpose | Declared Retention | Expected Gap Status |
| :--- | :--- | :--- | :--- | :--- |
| `qa_customers.csv` | `email` | Customer communications | 3 years post-closure | **Complete** |
| `qa_customers.csv` | `phone` | Customer support routing | *None (null)* | **Retention Missing** |
| `qa_customers.csv` | `full_name` | *None (null)* | 5 years | **Purpose Missing** |
| `qa_customers.csv` | `date_of_birth` | *None (null)* | *None (null)* | **Both Missing** |
| `qa_customers.csv` | `city`, `country` | *Not in metadata.json* | *Not in metadata.json* | **Not Mapped** |
| `qa_transactions.csv` | `billing_email` | Receipt delivery | 7 years | **Complete** |
| `qa_transactions.csv` | `amount` | Financial reporting | *None (null)* | **Retention Missing** |
| `qa_transactions.csv` | `billing_phone` | *None (null)* | 3 years | **Purpose Missing** |
| `qa_employees.csv` | `work_email` | IT system access | Employment + 2 years | **Complete** |
| `qa_employees.csv` | `salary` | *None (null)* | 7 years statutory | **Purpose Missing** |
| `qa_employees.csv` | `mobile_number` | Emergency contacts | *None (null)* | **Retention Missing** |
| `qa_employees.csv` | `employee_name` | *Not in metadata.json* | *Not in metadata.json* | **Not Mapped** |

---

## 3. End-to-End Test Plan

1. **Upload Verification**: Upload `qa_customers.csv`, `qa_transactions.csv`, and `qa_employees.csv` via the web UI.
2. **Sources Inspection**: Verify the files appear under "Available Data Sources" with row/column counts and status `Available`.
3. **Execution**: Click "Run Full Scan" and observe loading states and backend logging.
4. **Inventory Audit**: Verify detected PII fields with high confidence scores, correct data classes, and auto-triage statuses.
5. **Evidence Gaps Audit**: Verify categorized gaps, test filter dropdowns, and verify "Reset Filters".
6. **Pipeline Run**: Click "Run Pipeline" to compute end-to-end evaluation metrics.
7. **Report Export**: Download CSV report and inspect generated evidence records.
