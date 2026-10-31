"""
backend/enterprise/recommendations.py
=====================================
Module 5.3: AI Recommendations & Actionable Insights Engine
- Dynamically derives prioritized, evidence-backed corrective actions from actual findings:
  Risk assessment scores, Missing proofs, Observable egress events, and Schema gaps.
- Full lifecycle status management: Pending, Accepted, In Progress, Completed, Dismissed.
- Full audit tracking of user assignments and resolution notes.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.auth.db import get_db_connection
from backend.enterprise.database import init_enterprise_tables
from backend.enterprise.models import (
    Recommendation,
    RecommendationStatus,
    RecommendationUpdate,
    RiskSeverity,
)
from backend.enterprise.risk_engine import get_risk_engine
from backend.lineage.egress import get_egress_tracker

logger = logging.getLogger("privsight.enterprise.recommendations")


class RecommendationEngine:
    """Derives and tracks evidence-backed privacy corrective recommendations."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        init_enterprise_tables()

    def generate_recommendations(self) -> List[Recommendation]:
        """
        Synthesizes concrete, actionable recommendations from actual risk and evidence findings.
        Persists new recommendations safely to the database without overwriting existing status.
        """
        risk_engine = get_risk_engine()
        snapshot = risk_engine.assess_enterprise_risk()
        egress_tracker = get_egress_tracker()
        egress_events = egress_tracker.get_egress_events(limit=50)

        existing_recs = {r.id: r for r in self.list_recommendations(limit=200)}
        new_recs: List[Recommendation] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Recommendations for Critical & High Risk Direct Identifiers
        for f in snapshot.top_risk_fields:
            if f.is_direct_identifier and f.severity in (RiskSeverity.CRITICAL, RiskSeverity.HIGH):
                rec_id = f"REC-ENC-{abs(hash(f.field_key)) % 100000:05d}"
                if rec_id not in existing_recs:
                    new_recs.append(
                        Recommendation(
                            id=rec_id,
                            title=f"Enforce Field-Level Masking & Cryptographic Hashing on `{f.column_name}`",
                            description=(
                                f"Direct personal identifier `{f.column_name}` ({f.pii_class}) in `{f.dataset}` is currently exposed "
                                f"with a calculated risk score of {f.risk_score}/100. Implement AES-256 field-level encryption or format-preserving pseudonymization."
                            ),
                            action_type="PSEUDONYMIZE",
                            severity=f.severity,
                            priority=1 if f.severity == RiskSeverity.CRITICAL else 2,
                            target_dataset=f.dataset,
                            target_table=f.table_name,
                            target_column=f.column_name,
                            entity_name=f.entity_name,
                            rationale=f.rationale,
                            supporting_evidence=[
                                f"Evidence Inventory item `{f.field_key}`",
                                f"Risk assessment score {f.risk_score} (Factor: {f.pii_class})",
                            ],
                            expected_impact="Reduces sensitive exposure surface and lowers entity vulnerability score by up to 35 points.",
                            status=RecommendationStatus.PENDING,
                            created_at=now_iso,
                            updated_at=now_iso,
                        )
                    )

        # 2. Recommendations for Unverified Relationships & Missing Proofs
        for t in snapshot.top_risk_tables:
            if t.missing_proofs_count > 0 or t.unverified_relationships_count > 0:
                rec_id = f"REC-REL-{abs(hash(t.table_key)) % 100000:05d}"
                if rec_id not in existing_recs:
                    new_recs.append(
                        Recommendation(
                            id=rec_id,
                            title=f"Establish Database Foreign Key Constraint on `{t.table_name}` ({t.dataset})",
                            description=(
                                f"Table `{t.table_name}` contains {t.unverified_relationships_count} unverified relationship(s) "
                                f"and {t.missing_proofs_count} missing proof(s). Create an explicit SQL foreign key constraint or secondary index to eliminate relational drift."
                            ),
                            action_type="ENFORCE_CONSTRAINT",
                            severity=RiskSeverity.HIGH if t.missing_proofs_count > 1 else RiskSeverity.MEDIUM,
                            priority=2 if t.missing_proofs_count > 1 else 3,
                            target_dataset=t.dataset,
                            target_table=t.table_name,
                            entity_name=t.entity_name,
                            rationale="Unverified foreign keys create unbacked data linkages susceptible to false-positive classification and orphaned records.",
                            supporting_evidence=[
                                f"Missing Proofs audit report for `{t.table_key}`",
                                f"Directional lineage unverified edges in `{t.dataset}`",
                            ],
                            expected_impact="Elevates evidence verification confidence to 100% and resolves active Missing Proof items.",
                            status=RecommendationStatus.PENDING,
                            created_at=now_iso,
                            updated_at=now_iso,
                        )
                    )

        # 3. Recommendations for Observable Egress Events
        for ev in egress_events:
            if ev.operation_type == "CSV_EXPORT":
                rec_id = f"REC-EGR-{abs(hash(ev.id)) % 100000:05d}"
                if rec_id not in existing_recs:
                    new_recs.append(
                        Recommendation(
                            id=rec_id,
                            title=f"Review & Validate CSV Egress Export: `{ev.source_dataset}` ➔ `{ev.destination_dataset}`",
                            description=(
                                f"Personal data egress operation detected exporting {ev.record_count} records of `{ev.entity_name}` "
                                f"containing classes {', '.join(ev.pii_classes or ['PII'])}. Confirm data export authorization and data subject consent."
                            ),
                            action_type="REMEDIATE_EGRESS",
                            severity=RiskSeverity.HIGH,
                            priority=2,
                            target_dataset=ev.source_dataset,
                            target_table=ev.source_table,
                            target_column=ev.source_column,
                            entity_name=ev.entity_name,
                            rationale=f"Observable egress event `{ev.id}` transferred personal data across filesystem boundary.",
                            supporting_evidence=[
                                f"Egress Event `{ev.id}` timestamp `{ev.timestamp}`",
                                f"Proof: `{getattr(ev, 'ledger_block_hash', None) or ev.evidence}`",
                            ],
                            expected_impact="Ensures compliance with GDPR Article 30 and Article 32 egress transfer logging.",
                            status=RecommendationStatus.PENDING,
                            created_at=now_iso,
                            updated_at=now_iso,
                        )
                    )

        # Persist newly created recommendations
        if new_recs:
            self._save_recommendations(new_recs)

        return self.list_recommendations()

    def list_recommendations(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        limit: int = 100,
    ) -> List[Recommendation]:
        """Queries persisted recommendations with optional filters."""
        conn = get_db_connection(self.db_path)
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM enterprise_recommendations WHERE 1=1"
            params: List[Any] = []

            if status:
                query += " AND status = ?"
                params.append(status)
            if severity:
                query += " AND severity = ?"
                params.append(severity)

            query += " ORDER BY priority ASC, created_at DESC LIMIT ?"
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()

            results: List[Recommendation] = []
            for r in rows:
                results.append(
                    Recommendation(
                        id=r["id"],
                        title=r["title"],
                        description=r["description"],
                        action_type=r["action_type"],
                        severity=RiskSeverity(r["severity"]),
                        priority=r["priority"],
                        target_dataset=r["target_dataset"],
                        target_table=r["target_table"],
                        target_column=r["target_column"],
                        entity_name=r["entity_name"],
                        rationale=r["rationale"],
                        supporting_evidence=json.loads(r["supporting_evidence"]),
                        expected_impact=r["expected_impact"],
                        status=RecommendationStatus(r["status"]),
                        assigned_to=r["assigned_to"],
                        created_at=r["created_at"],
                        updated_at=r["updated_at"],
                        resolution_notes=r["resolution_notes"],
                    )
                )
            return results
        finally:
            conn.close()

    def update_recommendation(
        self,
        rec_id: str,
        update_data: RecommendationUpdate,
        user_email: str = "security_lead@privsight.local",
    ) -> Optional[Recommendation]:
        """Updates recommendation status, notes, and assignment."""
        conn = get_db_connection(self.db_path)
        now_iso = datetime.now(timezone.utc).isoformat()
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM enterprise_recommendations WHERE id = ?", (rec_id,))
                row = cursor.fetchone()
                if not row:
                    return None

                assigned = update_data.assigned_to or row["assigned_to"] or user_email
                cursor.execute(
                    """
                    UPDATE enterprise_recommendations
                    SET status = ?, resolution_notes = ?, assigned_to = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        update_data.status.value,
                        update_data.notes or row["resolution_notes"],
                        assigned,
                        now_iso,
                        rec_id,
                    ),
                )
            # Re-fetch updated
            updated_list = [r for r in self.list_recommendations() if r.id == rec_id]
            return updated_list[0] if updated_list else None
        finally:
            conn.close()

    def _save_recommendations(self, recs: List[Recommendation]) -> None:
        conn = get_db_connection(self.db_path)
        try:
            with conn:
                for r in recs:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO enterprise_recommendations
                        (id, title, description, action_type, severity, priority,
                         target_dataset, target_table, target_column, entity_name,
                         rationale, supporting_evidence, expected_impact, status,
                         assigned_to, created_at, updated_at, resolution_notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            r.id,
                            r.title,
                            r.description,
                            r.action_type,
                            r.severity.value,
                            r.priority,
                            r.target_dataset,
                            r.target_table,
                            r.target_column,
                            r.entity_name,
                            r.rationale,
                            json.dumps(r.supporting_evidence),
                            r.expected_impact,
                            r.status.value,
                            r.assigned_to,
                            r.created_at,
                            r.updated_at,
                            r.resolution_notes,
                        ),
                    )
        finally:
            conn.close()


_recommendation_engine_instance: Optional[RecommendationEngine] = None


def get_recommendation_engine() -> RecommendationEngine:
    global _recommendation_engine_instance
    if _recommendation_engine_instance is None:
        _recommendation_engine_instance = RecommendationEngine()
    return _recommendation_engine_instance
