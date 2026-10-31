"""
backend/enterprise/monitoring_alerts.py
=======================================
Module 5.5: Continuous Monitoring & Alert Management System
- Detects observable changes across personal data inventory, evidence ledger, egress, and risk scores.
- Classifies alert severity: Critical, High, Medium, Low, Info.
- Deduplicates notifications via deterministic dedup_key.
- Full alert lifecycle workflow: Active -> Acknowledged -> Resolved (with user audit trail).
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
    AlertCategory,
    AlertSeverity,
    AlertStatus,
    AlertStatusUpdate,
    MonitoringAlert,
    RiskSeverity,
)
from backend.enterprise.risk_engine import get_risk_engine
from backend.lineage.egress import get_egress_tracker
from backend.lineage.ledger import get_evidence_ledger

logger = logging.getLogger("privsight.enterprise.monitoring")


class ContinuousMonitoringService:
    """Manages continuous monitoring checks and privacy security alerts."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path
        init_enterprise_tables()

    def sync_and_evaluate_alerts(self) -> List[MonitoringAlert]:
        """
        Evaluates current operational state against detection rules to generate alerts.
        Deduplicates against existing active alerts to prevent notification fatigue.
        """
        risk_engine = get_risk_engine()
        snapshot = risk_engine.assess_enterprise_risk()
        egress_tracker = get_egress_tracker()
        egress_events = egress_tracker.get_egress_events(limit=50)
        ledger = get_evidence_ledger()
        ledger_result = ledger.verify_ledger_integrity()

        now_iso = datetime.now(timezone.utc).isoformat()
        generated_alerts: List[MonitoringAlert] = []

        # 1. Critical Direct Identifier Exposure Alerts
        for f in snapshot.top_risk_fields:
            if f.severity == RiskSeverity.CRITICAL and f.is_direct_identifier:
                dedup = f"PII_EXP:{f.dataset}:{f.column_name}:CRIT"
                generated_alerts.append(
                    MonitoringAlert(
                        id=f"ALT-{uuid.uuid4().hex[:10]}",
                        timestamp=now_iso,
                        title=f"Critical Exposure: Direct Identifier `{f.column_name}` ({f.pii_class})",
                        message=(
                            f"Direct personal identifier `{f.column_name}` in `{f.dataset}` calculated at risk score "
                            f"{f.risk_score}/100 without schema encryption or access restriction."
                        ),
                        severity=AlertSeverity.CRITICAL,
                        category=AlertCategory.PII_EXPOSURE,
                        source_dataset=f.dataset,
                        source_table=f.table_name,
                        source_column=f.column_name,
                        entity_name=f.entity_name,
                        status=AlertStatus.ACTIVE,
                        dedup_key=dedup,
                        evidence_ref=f.field_key,
                    )
                )

        # 2. Observable Data Egress Alerts
        for ev in egress_events:
            if ev.operation_type == "CSV_EXPORT":
                dedup = f"EGR_ANOMALY:{ev.source_dataset}:{ev.source_column}:{ev.destination_dataset}"
                generated_alerts.append(
                    MonitoringAlert(
                        id=f"ALT-{uuid.uuid4().hex[:10]}",
                        timestamp=now_iso,
                        title=f"Observable Egress: Personal Data Export to `{ev.destination_dataset}`",
                        message=(
                            f"Observable CSV export detected: {ev.record_count} records of `{ev.entity_name}` "
                            f"exported from `{ev.source_dataset}`. Evidence: {ev.evidence[:40]}..."
                        ),
                        severity=AlertSeverity.HIGH,
                        category=AlertCategory.EGRESS_ANOMALY,
                        source_dataset=ev.source_dataset,
                        source_table=ev.source_table,
                        source_column=ev.source_column,
                        entity_name=ev.entity_name,
                        status=AlertStatus.ACTIVE,
                        dedup_key=dedup,
                        evidence_ref=f"EgressEvent:{ev.id}",
                    )
                )

        # 3. Evidence Integrity Ledger Verification Alert
        if not ledger_result.is_valid:
            dedup = f"LEDGER_GAP:BLOCK_TAMPER:{ledger_result.failed_block_sequence}"
            generated_alerts.append(
                MonitoringAlert(
                    id=f"ALT-{uuid.uuid4().hex[:10]}",
                    timestamp=now_iso,
                    title="Evidence Ledger Integrity Failure / Tampering Detected",
                    message=(
                        f"Cryptographic hash chain verification failed at block sequence #{ledger_result.failed_block_sequence}. "
                        "Recomputed SHA-256 does not match stored block hash. Immediate forensic review required."
                    ),
                    severity=AlertSeverity.CRITICAL,
                    category=AlertCategory.EVIDENCE_INTEGRITY_GAP,
                    source_dataset="reports/evidence_inventory.json",
                    source_table="evidence_chain_ledger",
                    source_column="current_hash",
                    entity_name="EvidenceLedger",
                    status=AlertStatus.ACTIVE,
                    dedup_key=dedup,
                    evidence_ref=f"LedgerBlockSeq:{ledger_result.failed_block_sequence}",
                )
            )

        # 4. Unverified Relationship & Missing Proof Alerts
        for t in snapshot.top_risk_tables:
            if t.missing_proofs_count >= 2:
                dedup = f"REL_UNVERIFIED:{t.dataset}:{t.table_name}:MISSING_PROOFS"
                generated_alerts.append(
                    MonitoringAlert(
                        id=f"ALT-{uuid.uuid4().hex[:10]}",
                        timestamp=now_iso,
                        title=f"Multiple Missing Proofs in `{t.table_name}` ({t.dataset})",
                        message=(
                            f"Table `{t.table_name}` has {t.missing_proofs_count} active missing proof items "
                            f"and {t.unverified_relationships_count} unverified relationship hops requiring technical evidence."
                        ),
                        severity=AlertSeverity.MEDIUM,
                        category=AlertCategory.RELATIONSHIP_UNVERIFIED,
                        source_dataset=t.dataset,
                        source_table=t.table_name,
                        entity_name=t.entity_name,
                        status=AlertStatus.ACTIVE,
                        dedup_key=dedup,
                        evidence_ref=f"Table:{t.table_key}",
                    )
                )

        # Persist alerts with deduplication check
        self._persist_new_alerts(generated_alerts)
        return self.list_alerts()

    def list_alerts(
        self,
        status: Optional[str] = None,
        severity: Optional[str] = None,
        category: Optional[str] = None,
        limit: int = 100,
    ) -> List[MonitoringAlert]:
        """Queries persisted monitoring alerts with optional filters."""
        conn = get_db_connection(self.db_path)
        try:
            cursor = conn.cursor()
            query = "SELECT * FROM enterprise_alerts WHERE 1=1"
            params: List[Any] = []

            if status:
                query += " AND status = ?"
                params.append(status)
            if severity:
                query += " AND severity = ?"
                params.append(severity)
            if category:
                query += " AND category = ?"
                params.append(category)

            # Order by severity priority (Critical -> High -> Medium -> Low), then timestamp
            query += """
            ORDER BY 
              CASE severity 
                WHEN 'Critical' THEN 1 
                WHEN 'High' THEN 2 
                WHEN 'Medium' THEN 3 
                WHEN 'Low' THEN 4 
                ELSE 5 
              END ASC,
              timestamp DESC
            LIMIT ?
            """
            params.append(limit)

            cursor.execute(query, params)
            rows = cursor.fetchall()
            alerts = []
            for r in rows:
                alerts.append(
                    MonitoringAlert(
                        id=r["id"],
                        timestamp=r["timestamp"],
                        title=r["title"],
                        message=r["message"],
                        severity=AlertSeverity(r["severity"]),
                        category=AlertCategory(r["category"]),
                        source_dataset=r["source_dataset"],
                        source_table=r["source_table"],
                        source_column=r["source_column"],
                        entity_name=r["entity_name"],
                        status=AlertStatus(r["status"]),
                        dedup_key=r["dedup_key"],
                        evidence_ref=r["evidence_ref"],
                        acknowledged_by=r["acknowledged_by"],
                        acknowledged_at=r["acknowledged_at"],
                        resolved_by=r["resolved_by"],
                        resolved_at=r["resolved_at"],
                        resolution_notes=r["resolution_notes"],
                    )
                )
            return alerts
        finally:
            conn.close()

    def acknowledge_alert(
        self,
        alert_id: str,
        user_email: str = "security_analyst@privsight.local",
    ) -> Optional[MonitoringAlert]:
        """Transitions alert status to ACKNOWLEDGED."""
        now_iso = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection(self.db_path)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE enterprise_alerts
                    SET status = 'Acknowledged', acknowledged_by = ?, acknowledged_at = ?
                    WHERE id = ? AND status = 'Active'
                    """,
                    (user_email, now_iso, alert_id),
                )
            results = [a for a in self.list_alerts() if a.id == alert_id]
            return results[0] if results else None
        finally:
            conn.close()

    def resolve_alert(
        self,
        alert_id: str,
        user_email: str = "security_lead@privsight.local",
        notes: Optional[str] = None,
    ) -> Optional[MonitoringAlert]:
        """Transitions alert status to RESOLVED with resolution notes."""
        now_iso = datetime.now(timezone.utc).isoformat()
        conn = get_db_connection(self.db_path)
        try:
            with conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE enterprise_alerts
                    SET status = 'Resolved', resolved_by = ?, resolved_at = ?, resolution_notes = ?
                    WHERE id = ?
                    """,
                    (user_email, now_iso, notes or "Remediated in active inventory", alert_id),
                )
            results = [a for a in self.list_alerts() if a.id == alert_id]
            return results[0] if results else None
        finally:
            conn.close()

    def _persist_new_alerts(self, alerts: List[MonitoringAlert]) -> None:
        conn = get_db_connection(self.db_path)
        try:
            with conn:
                for a in alerts:
                    conn.execute(
                        """
                        INSERT OR IGNORE INTO enterprise_alerts
                        (id, timestamp, title, message, severity, category,
                         source_dataset, source_table, source_column, entity_name,
                         status, dedup_key, evidence_ref, acknowledged_by,
                         acknowledged_at, resolved_by, resolved_at, resolution_notes)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            a.id,
                            a.timestamp,
                            a.title,
                            a.message,
                            a.severity.value,
                            a.category.value,
                            a.source_dataset,
                            a.source_table,
                            a.source_column,
                            a.entity_name,
                            a.status.value,
                            a.dedup_key,
                            a.evidence_ref,
                            a.acknowledged_by,
                            a.acknowledged_at,
                            a.resolved_by,
                            a.resolved_at,
                            a.resolution_notes,
                        ),
                    )
        finally:
            conn.close()


_monitoring_service_instance: Optional[ContinuousMonitoringService] = None


def get_monitoring_service() -> ContinuousMonitoringService:
    global _monitoring_service_instance
    if _monitoring_service_instance is None:
        _monitoring_service_instance = ContinuousMonitoringService()
    return _monitoring_service_instance
