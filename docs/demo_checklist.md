# Hackathon Live Demo Checklist: PS-019

Use this quick-reference step-by-step checklist to ensure a smooth, error-free presentation.

---

## Pre-Demo Checklist (5 Minutes Before Presentation)

- [ ] **Open PowerShell** in the project directory: `c:\Users\honey\OneDrive\Desktop\A3-PS019-TC303`
- [ ] **Run test suite** to ensure clean state:
  ```powershell
  .venv\Scripts\python -m pytest tests/ -q
  ```
  *(Expected: `133 passed, 11 warnings`)*
- [ ] **Start the application**:
  ```powershell
  $env:PYTHONIOENCODING="utf-8"
  .venv\Scripts\python -m uvicorn backend.api.main:app --reload --host 127.0.0.1 --port 8000
  ```
- [ ] **Open browser** at: `http://127.0.0.1:8000` (or `http://127.0.0.1:8000/workspace`)
- [ ] **Check connectivity**: Verify the green dot **API Connected** is visible in top right.

---

## Live Demo Step-by-Step Flow

### Step 1: Overview & Available Data Sources
- [ ] Point out the **Header Title**: *Personal-Data Discovery & Evidence Inventory (PS-019 · TC-303)*.
- [ ] Point out the **Technical Evidence Scope Banner** (No legal compliance decisions).
- [ ] Note key metric cards: **Data Fields Checked**, **Personal Data Found**, **Metadata Completed**, and **Missing Proof**.
- [ ] Review the **Available Data Sources** grid:
  - Default CSV files (`customers.csv`, `employees.csv`, `transactions.csv`) and SQLite tables.
  - Notice status sorting (Available sources appear at top) and format badge pills (`CSV`, `SQLITE`).

### Step 2: Multi-Format Upload & Ingestion (New!)
- [ ] Click **Upload Data File** (or drag & drop files onto the upload zone).
- [ ] Show multi-format support across 26 common file extensions:
  - **Documents:** PDF (`.pdf`), Word (`.docx`), PowerPoint (`.pptx`), Plain text (`.txt`, `.rtf`).
  - **Spreadsheets:** Excel (`.xlsx`, `.xlsm`, `.xls`), OpenDocument (`.ods`).
  - **Delimited & Structured:** CSV, TSV, JSON, JSONL, XML.
  - **Logs & Config:** LOG, YAML, INI/CONF/CFG.
  - **Email:** EML, MBOX.
  - **Databases:** SQLite (`.db`, `.sqlite`, `.sqlite3`).
- [ ] Upload test files (e.g. from `PrivSight_QA_MultiFormat_Data/`):
  - Notice real-time file queue with format badges, file sizes, and parse status.
  - Upload an encrypted or corrupted file to demonstrate graceful rejection and clear error messaging without crashing.

### Step 3: Trigger Live Scan
- [ ] Click **Run Full Scan** button.
- [ ] Observe spinner and toast confirmation with real discovery counts across both default datasets and uploaded files.
- [ ] Demonstrate that the data reloads smoothly without page refreshes.

### Step 4: Personal-Data Inventory Tab
- [ ] Click **Personal-Data Inventory** tab.
- [ ] In the search box, search for extracted PII fields from multi-format files (e.g. `qa_executive_payroll.xlsx`, `qa_customers.json`, `qa_security_brief.pdf`).
- [ ] Demonstrate preserved source filenames and structured field paths (e.g., `Payroll!tax_id`, `audit.details.national_id`).
- [ ] Click the **Details** button on any record to inspect detected class, confidence score, declared purpose, retention period, and governance status.

### Step 5: Missing Proof Tab (Evidence Gaps)
- [ ] Click **Missing Proof** tab.
- [ ] Filter by **Retention Missing** or **Not Mapped** to show technical governance discrepancies requiring human review.
- [ ] Explain that missing proof indicates technical discrepancies for governance auditing, not legal conclusions.

### Step 6: Ground-Truth Evaluation Tab
- [ ] Click **Ground-Truth Evaluation** tab.
- [ ] Highlight Binary Detection Metrics (Precision, Recall, F1-Score).
- [ ] Show per-class metrics and explain sample size transparency (`Limited Sample` indicator).
- [ ] Review Confusion Matrix and Discrepancy Error Records.

### Step 7: Reports & Downloads Tab
- [ ] Click **Reports & Downloads** tab.
- [ ] Click **Download CSV** on *Evidence Inventory (CSV)* or *Evidence Gaps (CSV)*.
- [ ] Confirm file downloads immediately into browser download folder.

---

## Troubleshooting Quick-Fixes

- **Browser can't connect?** Confirm Uvicorn is running on port 8000 and terminal hasn't paused (press `Enter` in PowerShell if selection mode is paused).
- **Reports missing?** Click **Run Pipeline** in the top navigation bar to regenerate all reports immediately.

 