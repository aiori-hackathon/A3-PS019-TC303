"""
backend/relationships/entity_engine.py
======================================
Entity Identification Engine for PrivSight TRACERA Phase 2.

Identifies entities, tables, columns, and data classes across natural language queries:
- People / Persons
- Customers
- Employees / Staff
- Organizations / Departments
- Financial entities (Orders, Payments, Transactions, Salaries, Cards)
- Contact entities (Email addresses, Phone numbers)
- Location entities (Addresses, Cities, Countries)
- Sensitive / Health entities
- Documents & Files
- Database tables and columns

Compiles comprehensive technical and governance metadata for each identified entity.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from backend.relationships.engine import mask_personal_value
from backend.relationships.privsight_data import PrivSightDataManager, TableInfo, get_privsight_data_manager

logger = logging.getLogger("privsight.relationships.entity")

# Canonical entity definitions
ENTITY_TAXONOMY = {
    "customer": {
        "label": "Customer",
        "category": "Person / Commercial",
        "keywords": ["customer", "customers", "client", "clients", "buyer", "buyers", "consumer", "patron", "subscriber"],
        "tables": ["customers.csv", "qa_customers.csv", "relational_demo.db:customers", "privacy_demo.db:customers"],
        "primary_id": "customer_id",
        "description": "Represents external customer accounts, personal identity attributes, and contact endpoints.",
    },
    "employee": {
        "label": "Employee",
        "category": "Person / Internal Workforce",
        "keywords": ["employee", "employees", "staff", "worker", "workers", "personnel", "contractor", "team member"],
        "tables": ["employees.csv", "qa_employees.csv", "relational_demo.db:employees", "privacy_demo.db:employees", "qa_executive_payroll.xlsx", "qa_contractor_profile.docx"],
        "primary_id": "employee_id",
        "description": "Represents internal workforce members, compensation records, and department assignments.",
    },
    "order": {
        "label": "Order",
        "category": "Transaction / Commercial",
        "keywords": ["order", "orders", "purchase", "purchases", "order item"],
        "tables": ["orders.csv", "relational_demo.db:orders"],
        "primary_id": "order_id",
        "description": "Represents commercial customer purchases, order dates, amounts, and fulfillment statuses.",
    },
    "payment": {
        "label": "Payment",
        "category": "Financial / Settlement",
        "keywords": ["payment", "payments", "settlement", "settlements", "billing", "disbursement", "remittance"],
        "tables": ["payments.csv", "relational_demo.db:payments"],
        "primary_id": "payment_id",
        "description": "Represents financial settlement records, payment methods, transaction amounts, and masked card numbers.",
    },
    "department": {
        "label": "Department",
        "category": "Organization",
        "keywords": ["department", "departments", "dept", "unit", "division", "team"],
        "tables": ["departments.csv", "relational_demo.db:departments"],
        "primary_id": "department_id",
        "description": "Represents organizational business units, location codes, operational budgets, and department heads.",
    },
    "transaction": {
        "label": "Transaction",
        "category": "Financial / Commercial",
        "keywords": ["transaction", "transactions", "txn", "ledger", "checkout"],
        "tables": ["transactions.csv", "qa_transactions.csv", "privacy_demo.db:transactions"],
        "primary_id": "transaction_id",
        "description": "Represents payment transaction ledgers, billing emails, masked payment cards, and merchant categories.",
    },
    "person": {
        "label": "Person",
        "category": "Natural Person (GDPR Subject)",
        "keywords": ["person", "people", "individual", "individuals", "human", "subject", "data subject", "user", "users"],
        "tables": ["customers.csv", "employees.csv", "privacy_demo.db:customers", "privacy_demo.db:employees"],
        "primary_id": "id",
        "description": "General natural person entity encompassing both customer and employee records.",
    },
}

DATA_CLASS_TAXONOMY = {
    "contact": {
        "class_name": "Contact",
        "keywords": ["email", "emails", "e-mail", "phone", "phones", "telephone", "mobile", "contact", "address", "communication"],
        "target_fields": ["email", "phone", "mobile_number", "work_email", "billing_email", "billing_phone", "contact_phone", "contact_email"],
        "description": "Communication endpoints including email addresses, telephone numbers, and mailing addresses.",
    },
    "identity": {
        "class_name": "Identity",
        "keywords": ["name", "names", "full name", "first name", "last name", "dob", "birth", "date of birth", "ssn", "national id", "passport", "identity"],
        "target_fields": ["full_name", "employee_name", "date_of_birth", "patient_name", "contractor_full_name"],
        "description": "Direct personal identifiers including full names, dates of birth, and official credentials.",
    },
    "financial": {
        "class_name": "Financial",
        "keywords": ["salary", "salaries", "compensation", "amount", "card", "credit card", "bank", "bank account", "budget", "financial"],
        "target_fields": ["salary", "amount", "budget", "bank_account", "card_last4", "card_last_four"],
        "description": "Monetary ledgers, employee compensation, bank account references, and masked payment cards.",
    },
    "location": {
        "class_name": "Location",
        "keywords": ["city", "country", "state", "postal", "zip", "location", "address", "geographic"],
        "target_fields": ["city", "country", "state", "postal_code", "billing_city", "billing_country", "residential_address", "location_code"],
        "description": "Geographical attributes including residential city, country, postal code, and billing region.",
    },
    "sensitive": {
        "class_name": "Sensitive/Health",
        "keywords": ["health", "medical", "insurance", "patient", "sensitive", "diagnosis", "benefits"],
        "target_fields": ["health_insurance_id", "medical_notes"],
        "description": "Special category personal data including health insurance IDs and clinical patient notes.",
    },
}

# Identifier pattern for specific record queries: C001, E101, ORD-101, PAY-501, D01, TXN-101
RECORD_ID_REGEX = re.compile(
    r"\b(C\d{3}|CUST-\d+|ORD-\d+|PAY-\d+|E\d{3}|EMP-\d+|D\d{2}|TXN-\d+|DEP-\d+)\b",
    re.IGNORECASE,
)


@dataclass
class IdentifiedEntity:
    """Detailed profile of an entity identified in a user query or data source."""
    entity_key: str
    label: str
    category: str
    description: str
    primary_id: Optional[str]
    matched_tables: List[TableInfo] = field(default_factory=list)
    personal_data_fields: List[Dict[str, Any]] = field(default_factory=list)
    evidence_gaps: List[Dict[str, Any]] = field(default_factory=list)
    declared_purposes: List[str] = field(default_factory=list)
    declared_retentions: List[str] = field(default_factory=list)
    sample_records_count: int = 0
    sample_preview: List[Dict[str, Any]] = field(default_factory=list)


class EntityIdentificationEngine:
    """
    Intelligent entity extraction and profiling engine.
    Grounds natural language entities to real tables, columns, and records in PrivSight.
    """

    def __init__(self, data_manager: Optional[PrivSightDataManager] = None) -> None:
        self.dm = data_manager or get_privsight_data_manager()

    def identify_entities_in_query(
        self,
        query: str,
        context_entities: Optional[List[str]] = None,
    ) -> List[IdentifiedEntity]:
        """
        Analyze a query to identify mentioned entities (e.g. Customer, Employee, Order, Payment).
        Also supports contextual carry-over from prior conversation turns.
        """
        q_lower = query.lower()
        matched_keys: Set[str] = set()

        # 1. Match entity keywords
        for key, spec in ENTITY_TAXONOMY.items():
            for kw in spec["keywords"]:
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, q_lower):
                    matched_keys.add(key)
                    break

        # 2. Check for explicit table or file names in query
        all_tables = self.dm.get_all_tables()
        for t in all_tables:
            tbl_clean = t.key.lower()
            if tbl_clean in q_lower or (t.table_name and t.table_name.lower() in q_lower):
                # Map to canonical entity if possible
                for key, spec in ENTITY_TAXONOMY.items():
                    if any(t.key.lower().startswith(tbl.lower()) or tbl.lower() in t.key.lower() for tbl in spec["tables"]):
                        matched_keys.add(key)
                        break

        # 3. Contextual carryover if pronoun/reference detected and no new entity mentioned
        if not matched_keys and context_entities:
            for ce in context_entities:
                ce_clean = ce.lower().strip()
                for key in ENTITY_TAXONOMY:
                    if key in ce_clean or ce_clean in key:
                        matched_keys.add(key)

        # Build full profile for each matched entity
        profiles: List[IdentifiedEntity] = []
        for key in matched_keys:
            profile = self.build_entity_profile(key)
            if profile:
                profiles.append(profile)

        return profiles

    def identify_data_classes_in_query(self, query: str) -> List[str]:
        """Identify privacy data classes mentioned in query (Contact, Identity, Financial, Location, Sensitive/Health)."""
        q_lower = query.lower()
        matched_classes: List[str] = []

        for key, spec in DATA_CLASS_TAXONOMY.items():
            for kw in spec["keywords"]:
                if re.search(rf"\b{re.escape(kw)}\b", q_lower):
                    matched_classes.append(spec["class_name"])
                    break

        return matched_classes

    def identify_record_id(self, query: str) -> Optional[str]:
        """Extract a specific record identifier like C001, E101, ORD-101."""
        match = RECORD_ID_REGEX.search(query)
        return match.group(0).upper() if match else None

    def identify_tables_in_query(self, query: str) -> List[TableInfo]:
        """Find explicit tables or files mentioned in query."""
        q_lower = query.lower()
        matched_tables: List[TableInfo] = []
        for t in self.dm.get_all_tables():
            key_l = t.key.lower()
            stem_l = t.file_or_db.lower()
            tbl_l = (t.table_name or "").lower()
            if key_l in q_lower or (tbl_l and re.search(rf"\b{re.escape(tbl_l)}\b", q_lower)) or (stem_l in q_lower and "." in stem_l):
                matched_tables.append(t)
        return matched_tables

    def build_entity_profile(self, entity_key: str) -> Optional[IdentifiedEntity]:
        """Assemble full profile for an entity including tables, fields, gaps, and sample rows."""
        spec = ENTITY_TAXONOMY.get(entity_key.lower())
        if not spec:
            return None

        # Find matching tables in DataManager
        matched_tables = self.dm.find_tables_for_entity(entity_key)

        # Collect personal data fields and evidence gaps across these tables
        pd_fields: List[Dict[str, Any]] = []
        gaps: List[Dict[str, Any]] = []
        purposes: Set[str] = set()
        retentions: Set[str] = set()
        sample_rows: List[Dict[str, Any]] = []
        total_rows = 0

        for t in matched_tables:
            total_rows += t.row_count
            table_inv = self.dm.get_inventory_for_table(t.key)
            for r in table_inv:
                pd_fields.append(r)
                if r.get("overall_status") != "Complete":
                    gaps.append(r)
                p = r.get("purpose")
                if p:
                    purposes.add(p)
                ret = r.get("retention_period")
                if ret:
                    retentions.add(ret)

            # Sample row preview (masked)
            if t.data_df is not None and not t.data_df.empty and len(sample_rows) < 2:
                for _, row in t.data_df.head(2).iterrows():
                    masked_row = {
                        k: mask_personal_value(k, str(v))
                        for k, v in row.items()
                        if pd.notna(v) and str(v).strip() != ""
                    }
                    sample_rows.append({"source": t.key, "record": masked_row})

        return IdentifiedEntity(
            entity_key=entity_key,
            label=spec["label"],
            category=spec["category"],
            description=spec["description"],
            primary_id=spec["primary_id"],
            matched_tables=matched_tables,
            personal_data_fields=pd_fields,
            evidence_gaps=gaps,
            declared_purposes=sorted(purposes),
            declared_retentions=sorted(retentions),
            sample_records_count=total_rows,
            sample_preview=sample_rows[:3],
        )

    def explain_entity_location(self, entity_name: str) -> str:
        """
        Produce a comprehensive, evidence-grounded explanation of where an entity's data is stored.
        Follows the requirement: explain the result rather than simply returning a table name!
        """
        profile = self.build_entity_profile(entity_name)
        if not profile or not profile.matched_tables:
            return (
                f"### Entity Search Result: `{entity_name.title()}`\n"
                f"No specific database tables or datasets matching entity `{entity_name}` were found across active sources. "
                f"Available entities include Customers, Employees, Orders, Payments, Departments, and Transactions."
            )

        parts: List[str] = []
        parts.append(f"### Storage & Schema Overview for **{profile.label} Information**\n")
        parts.append(
            f"**{profile.label}** records ({profile.category}) are discovered and stored across **{len(profile.matched_tables)} active data source(s)** "
            f"comprising **{profile.sample_records_count} total records**:\n"
        )

        for i, tbl in enumerate(profile.matched_tables, 1):
            pk_str = f"Primary Key: `{tbl.primary_keys[0]}`" if tbl.primary_keys else "Primary Key: Inferred / None"
            fks_str = ""
            if tbl.foreign_keys:
                fk_items = [f"`{fk['from']}` → `{fk['to_table']}.{fk['to_col']}`" for fk in tbl.foreign_keys]
                fks_str = f" | Foreign Keys: {', '.join(fk_items)}"

            # Get candidate personal data fields in this table
            inv = self.dm.get_inventory_for_table(tbl.key)
            field_summary = []
            for r in inv:
                cls_pill = r.get("detected_class", "PII")
                field_summary.append(f"`{r['field_name']}` ({cls_pill})")

            fields_text = ", ".join(field_summary[:6]) if field_summary else "No detected personal data candidates"
            if len(field_summary) > 6:
                fields_text += f", and {len(field_summary) - 6} more"

            parts.append(f"{i}. **`{tbl.key}`** ({tbl.source_type} · {tbl.row_count} rows)")
            parts.append(f"   - **Identifiers**: {pk_str}{fks_str}")
            parts.append(f"   - **Personal Data Candidates**: {fields_text}")

            # Highlight declared purpose or gaps if any
            complete_in_tbl = sum(1 for r in inv if r.get("overall_status") == "Complete")
            gaps_in_tbl = sum(1 for r in inv if r.get("overall_status") != "Complete")
            parts.append(f"   - **Governance Status**: {complete_in_tbl} Complete Metadata, {gaps_in_tbl} Evidence Gap(s)")

        # Summary of identifiers and governance
        parts.append("\n**Key Entity Attributes & Identifiers:**")
        parts.append(f"- **Primary Identifier**: `{profile.primary_id}` enables entity resolution and referential joins across datasets.")
        if profile.declared_purposes:
            parts.append(f"- **Declared Business Purpose**: {profile.declared_purposes[0]}")
        if profile.declared_retentions:
            parts.append(f"- **Declared Retention Schedule**: {profile.declared_retentions[0]}")
        if profile.evidence_gaps:
            parts.append(f"- **Evidence Gaps / Missing Proofs**: {len(profile.evidence_gaps)} field(s) require governance review.")

        return "\n".join(parts)
