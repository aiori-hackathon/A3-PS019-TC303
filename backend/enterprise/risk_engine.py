"""
backend/enterprise/risk_engine.py
=================================
Module 5.2: Intelligent Risk Assessment Engine
- Evaluates actual PII classifications, missing evidence, unverified relationships,
  lineage stages, observable egress events, and evidence ledger integrity.
- Computes deterministic, explainable risk scores (0-100) with weighted contributing factors.
- Classifies risk into Critical, High, Medium, Low, or Unknown.
- Maintains snapshot history for historical risk trend tracking.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.auth.db import get_db_connection
from backend.enterprise.database import init_enterprise_tables
from backend.enterprise.models import (
    FieldRiskRecord,
    RiskContributingFactor,
    RiskSeverity,
    RiskSnapshot,
    TableRiskRecord,
)
from backend.lineage.egress import get_egress_tracker
from backend.lineage.engine import get_lineage_engine
from backend.lineage.ledger import get_evidence_ledger

logger = logging.getLogger("privsight.enterprise.risk")

BASE_DIR = Path(__file__).resolve().parent.parent.parent
EVIDENCE_INVENTORY_FILE = BASE_DIR / "reports" / "evidence_inventory.json"
MISSING_PROOFS_FILE = BASE_DIR / "reports" / "missing_proofs.json"


# PII Sensitivity Base Weights (Scale: 0 - 45)
PII_BASE_WEIGHTS: Dict[str, float] = {
    "SSN": 45.0,
    "NATIONAL_ID": 45.0,
    "CREDIT_CARD": 42.0,
    "PASSPORT": 42.0,
    "DRIVER_LICENSE": 38.0,
    "HEALTH_RECORD": 40.0,
    "BIOMETRIC": 40.0,
    "EMAIL": 28.0,
    "PHONE": 26.0,
    "FULL_NAME": 24.0,
    "NAME": 24.0,
    "ADDRESS": 22.0,
    "DATE_OF_BIRTH": 25.0,
    "DOB": 25.0,
    "SALARY": 30.0,
    "BANK_ACCOUNT": 40.0,
    "IP_ADDRESS": 18.0,
    "ZIP_CODE": 15.0,
    "GENDER": 12.0,
    "DEPARTMENT": 10.0,
}

DIRECT_IDENTIFIER_CLASSES = {
    "SSN", "NATIONAL_ID", "CREDIT_CARD", "PASSPORT", "DRIVER_LICENSE",
    "EMAIL", "PHONE", "FULL_NAME", "NAME", "BANK_ACCOUNT", "BIOMETRIC"
}


class IntelligentRiskEngine:
    """Centralized privacy and security risk assessment engine."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        init_enterprise_tables()

    def assess_enterprise_risk(self, force_fresh_snapshot: bool = False) -> RiskSnapshot:
        """
        Executes full deterministic risk evaluation across all scanned data sources.
        Returns a complete RiskSnapshot with table and field breakdowns.
        """
        inventory_data = self._load_evidence_inventory()
        missing_proofs = self._load_missing_proofs()
        egress_tracker = get_egress_tracker()
        egress_events = egress_tracker.get_egress_events(limit=200)
        lineage_engine = get_lineage_engine()
        lineage_dag = lineage_engine.build_directional_dag()
        evidence_ledger = get_evidence_ledger()
        ledger_result = evidence_ledger.verify_ledger_integrity()

        # Map egress exposure by source field
        egress_field_map: Dict[str, List[Any]] = {}
        for ev in egress_events:
            key = f"{ev.source_dataset}:{ev.source_column}".lower()
            egress_field_map.setdefault(key, []).append(ev)

        # Map missing proofs by field
        missing_proof_map: Dict[str, List[Dict[str, Any]]] = {}
        for mp in missing_proofs:
            src = mp.get("source_dataset", "")
            field = mp.get("field_name") or mp.get("column_name", "")
            key = f"{src}:{field}".lower()
            missing_proof_map.setdefault(key, []).append(mp)

        field_risks: List[FieldRiskRecord] = []
        table_grouped: Dict[str, List[FieldRiskRecord]] = {}

        if not inventory_data:
            logger.warning("No evidence inventory items available for risk assessment.")
            return self._create_empty_or_unknown_snapshot()

        for item in inventory_data:
            dataset = item.get("source_dataset") or item.get("dataset") or "unknown_dataset"
            table = item.get("table_name") or item.get("source_table") or dataset
            column = item.get("field_name") or item.get("column_name") or "unknown_column"
            entity = item.get("entity_name") or item.get("entity") or table.title()
            pii_class = (item.get("pii_class") or item.get("classification") or "PERSONAL_DATA").upper()

            field_key = f"{dataset}:{column}"
            field_lookup = field_key.lower()

            # 1. Base Sensitivity Scoring
            is_direct = pii_class in DIRECT_IDENTIFIER_CLASSES or item.get("is_direct_identifier", False)
            base_score = PII_BASE_WEIGHTS.get(pii_class, 20.0)
            factors: List[RiskContributingFactor] = [
                RiskContributingFactor(
                    category="Data Sensitivity",
                    description=f"{pii_class} classified as {'Direct Personal Identifier' if is_direct else 'Quasi-Identifier'}",
                    weight=0.45,
                    score_contribution=base_score,
                )
            ]

            # 2. Evidence Verification & Missing Proofs Factor
            has_missing_proof = field_lookup in missing_proof_map
            verification_status = item.get("verification_status") or ("Missing Proof" if has_missing_proof else "Verified")
            evidence_points = 0.0
            if has_missing_proof:
                evidence_points = 25.0
                factors.append(
                    RiskContributingFactor(
                        category="Evidence Gaps",
                        description=f"Missing proof record: {missing_proof_map[field_lookup][0].get('gap_reason', 'Unverified personal data candidate')}",
                        weight=0.25,
                        score_contribution=evidence_points,
                    )
                )
            elif verification_status != "Verified":
                evidence_points = 15.0
                factors.append(
                    RiskContributingFactor(
                        category="Evidence Gaps",
                        description=f"Relationship verification status is '{verification_status}' without database-enforced foreign key",
                        weight=0.15,
                        score_contribution=evidence_points,
                    )
                )
            else:
                factors.append(
                    RiskContributingFactor(
                        category="Evidence Gaps",
                        description="Backed by verified technical evidence and schema constraints",
                        weight=0.0,
                        score_contribution=0.0,
                    )
                )

            # 3. Lineage & Egress Factor
            has_egress = field_lookup in egress_field_map
            egress_points = 0.0
            if has_egress:
                ev_count = len(egress_field_map[field_lookup])
                op_types = list({e.operation_type for e in egress_field_map[field_lookup]})
                egress_points = 20.0
                factors.append(
                    RiskContributingFactor(
                        category="Egress Surface",
                        description=f"Observable egress detected ({ev_count} event(s): {', '.join(op_types)})",
                        weight=0.20,
                        score_contribution=egress_points,
                    )
                )

            # 4. Storage & Relational Exposure Factor
            storage_points = 0.0
            if dataset.endswith(".csv"):
                storage_points = 10.0
                factors.append(
                    RiskContributingFactor(
                        category="Storage Posture",
                        description="Stored in unencrypted flat-file (CSV) with unrestricted read visibility",
                        weight=0.10,
                        score_contribution=storage_points,
                    )
                )

            # 5. Ledger Integrity Factor
            if not ledger_result.is_valid:
                factors.append(
                    RiskContributingFactor(
                        category="Ledger Integrity",
                        description="Evidence integrity ledger contains unverified or modified blocks",
                        weight=0.10,
                        score_contribution=10.0,
                    )
                )

            # Aggregate total score (clamped to 0 - 100)
            total_raw = sum(f.score_contribution for f in factors)
            final_score = min(100.0, max(0.0, round(total_raw, 1)))

            # Severity Classification
            if final_score >= 80.0:
                severity = RiskSeverity.CRITICAL
            elif final_score >= 60.0:
                severity = RiskSeverity.HIGH
            elif final_score >= 40.0:
                severity = RiskSeverity.MEDIUM
            else:
                severity = RiskSeverity.LOW

            # Synthesize natural language rationale
            reasons = [f.description for f in factors if f.score_contribution > 0]
            rationale = "; ".join(reasons) if reasons else "Standard low-sensitivity personal data attribute."

            rec = FieldRiskRecord(
                field_key=field_key,
                dataset=dataset,
                table_name=table,
                column_name=column,
                entity_name=entity,
                pii_class=pii_class,
                is_direct_identifier=is_direct,
                risk_score=final_score,
                severity=severity,
                contributing_factors=factors,
                rationale=rationale,
                evidence_status=verification_status,
                egress_observed=has_egress,
                hop_distance_from_origin=0,
            )
            field_risks.append(rec)

            tbl_key = f"{dataset}:{table}"
            table_grouped.setdefault(tbl_key, []).append(rec)

        # Aggregate Table-Level Risk Records
        table_risks: List[TableRiskRecord] = []
        for tbl_key, records in table_grouped.items():
            first = records[0]
            max_s = max(r.risk_score for r in records)
            avg_s = round(sum(r.risk_score for r in records) / len(records), 1)
            tbl_sev = (
                RiskSeverity.CRITICAL if max_s >= 80.0 else
                RiskSeverity.HIGH if max_s >= 60.0 else
                RiskSeverity.MEDIUM if max_s >= 40.0 else
                RiskSeverity.LOW
            )
            crit_factors = list({f.description for r in records for f in r.contributing_factors if f.score_contribution >= 20.0})
            unverified_cnt = sum(1 for r in records if r.evidence_status != "Verified")
            missing_cnt = sum(1 for r in records if r.evidence_status == "Missing Proof")

            table_risks.append(
                TableRiskRecord(
                    table_key=tbl_key,
                    dataset=first.dataset,
                    table_name=first.table_name,
                    entity_name=first.entity_name,
                    total_fields=len(records),
                    pii_fields_count=len(records),
                    max_risk_score=max_s,
                    average_risk_score=avg_s,
                    severity=tbl_sev,
                    critical_factors=crit_factors[:4],
                    unverified_relationships_count=unverified_cnt,
                    missing_proofs_count=missing_cnt,
                )
            )

        table_risks.sort(key=lambda t: (t.max_risk_score, t.average_risk_score), reverse=True)
        field_risks.sort(key=lambda f: f.risk_score, reverse=True)

        crit_c = sum(1 for f in field_risks if f.severity == RiskSeverity.CRITICAL)
        high_c = sum(1 for f in field_risks if f.severity == RiskSeverity.HIGH)
        med_c = sum(1 for f in field_risks if f.severity == RiskSeverity.MEDIUM)
        low_c = sum(1 for f in field_risks if f.severity == RiskSeverity.LOW)
        overall_score = round(sum(f.risk_score for f in field_risks) / len(field_risks), 1) if field_risks else 0.0

        overall_sev = (
            RiskSeverity.CRITICAL if overall_score >= 75.0 or crit_c >= 5 else
            RiskSeverity.HIGH if overall_score >= 50.0 or crit_c > 0 or high_c >= 10 else
            RiskSeverity.MEDIUM if overall_score >= 30.0 or med_c > 0 else
            RiskSeverity.LOW
        )

        now_iso = datetime.now(timezone.utc).isoformat()
        snapshot = RiskSnapshot(
            snapshot_id=f"risk_snap_{uuid.uuid4().hex[:12]}",
            timestamp=now_iso,
            overall_risk_score=overall_score,
            severity=overall_sev,
            total_assessed_fields=len(field_risks),
            critical_count=crit_c,
            high_count=high_c,
            medium_count=med_c,
            low_count=low_c,
            unknown_count=0,
            top_risk_tables=table_risks[:10],
            top_risk_fields=field_risks[:15],
            scoring_methodology="PrivSight Deterministic Risk Assessment Methodology v5.2 (Sensitivity 45% + Evidence Gaps 25% + Egress 20% + Storage 10%)",
        )

        # Persist snapshot for historical tracking
        self._persist_snapshot(snapshot)
        return snapshot

    def get_historical_risk_trend(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Returns chronological list of risk snapshots for trend visualization."""
        conn = get_db_connection(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, timestamp, overall_risk_score, severity,
                       critical_count, high_count, medium_count, low_count
                FROM enterprise_risk_snapshots
                ORDER BY timestamp DESC
                LIMIT ?
                """,
                (limit,),
            )
            rows = cursor.fetchall()
            trend = []
            for r in reversed(rows):
                trend.append({
                    "id": r["id"],
                    "timestamp": r["timestamp"],
                    "overall_risk_score": r["overall_risk_score"],
                    "severity": r["severity"],
                    "critical_count": r["critical_count"],
                    "high_count": r["high_count"],
                    "medium_count": r["medium_count"],
                    "low_count": r["low_count"],
                })
            return trend
        finally:
            conn.close()

    def _persist_snapshot(self, snap: RiskSnapshot) -> None:
        """Stores a risk snapshot safely in SQLite."""
        conn = get_db_connection(self.db_path)
        try:
            with conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO enterprise_risk_snapshots
                    (id, timestamp, overall_risk_score, severity, total_assessed_fields,
                     critical_count, high_count, medium_count, low_count, unknown_count,
                     top_risk_tables, top_risk_fields, scoring_methodology)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        snap.snapshot_id,
                        snap.timestamp,
                        snap.overall_risk_score,
                        snap.severity.value,
                        snap.total_assessed_fields,
                        snap.critical_count,
                        snap.high_count,
                        snap.medium_count,
                        snap.low_count,
                        snap.unknown_count,
                        json.dumps([t.model_dump() for t in snap.top_risk_tables]),
                        json.dumps([f.model_dump() for f in snap.top_risk_fields]),
                        snap.scoring_methodology,
                    ),
                )
        except Exception as e:
            logger.error(f"Failed to persist risk snapshot: {e}")
        finally:
            conn.close()

    def _load_evidence_inventory(self) -> List[Dict[str, Any]]:
        """Loads actual personal data findings from reports/evidence_inventory.json."""
        if not EVIDENCE_INVENTORY_FILE.exists():
            return []
        try:
            with open(EVIDENCE_INVENTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else data.get("inventory", [])
        except Exception as e:
            logger.error(f"Error loading evidence inventory: {e}")
            return []

    def _load_missing_proofs(self) -> List[Dict[str, Any]]:
        """Loads actual missing proof records from reports/missing_proofs.json."""
        if not MISSING_PROOFS_FILE.exists():
            return []
        try:
            with open(MISSING_PROOFS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else data.get("missing_proofs", [])
        except Exception as e:
            logger.error(f"Error loading missing proofs: {e}")
            return []

    def _create_empty_or_unknown_snapshot(self) -> RiskSnapshot:
        now_iso = datetime.now(timezone.utc).isoformat()
        return RiskSnapshot(
            snapshot_id=f"risk_snap_unknown_{uuid.uuid4().hex[:8]}",
            timestamp=now_iso,
            overall_risk_score=0.0,
            severity=RiskSeverity.UNKNOWN,
            total_assessed_fields=0,
            critical_count=0,
            high_count=0,
            medium_count=0,
            low_count=0,
            unknown_count=1,
            top_risk_tables=[],
            top_risk_fields=[],
            scoring_methodology="PrivSight Methodology v5.2 - Status: Unknown (No scan findings)",
        )


_risk_engine_instance: Optional[IntelligentRiskEngine] = None


def get_risk_engine() -> IntelligentRiskEngine:
    global _risk_engine_instance
    if _risk_engine_instance is None:
        _risk_engine_instance = IntelligentRiskEngine()
    return _risk_engine_instance
