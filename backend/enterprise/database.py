"""
backend/enterprise/database.py
==============================
Safe, idempotent SQLite migrations and database management for Phase 5.2 - 5.7:
- Risk assessment snapshots
- Actionable recommendations
- Enterprise audit trail
- Continuous monitoring alerts & resolution
- Compliance evaluation records
"""

from __future__ import annotations

import logging
import sqlite3
from typing import Optional
from backend.auth.db import get_db_connection

logger = logging.getLogger("privsight.enterprise.database")


def init_enterprise_tables(conn: Optional[sqlite3.Connection] = None) -> None:
    """
    Initializes Phase 5.2 - 5.7 enterprise tables and composite indexes safely.
    Strictly idempotent: preserves all existing data.
    """
    should_close = False
    if conn is None:
        conn = get_db_connection()
        should_close = True

    try:
        with conn:
            conn.executescript(
                """
                -- 1. Risk Assessment Snapshots Table (Module 5.2)
                CREATE TABLE IF NOT EXISTS enterprise_risk_snapshots (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    overall_risk_score REAL NOT NULL,
                    severity TEXT NOT NULL,
                    total_assessed_fields INTEGER NOT NULL,
                    critical_count INTEGER NOT NULL,
                    high_count INTEGER NOT NULL,
                    medium_count INTEGER NOT NULL,
                    low_count INTEGER NOT NULL,
                    unknown_count INTEGER NOT NULL,
                    top_risk_tables TEXT NOT NULL,
                    top_risk_fields TEXT NOT NULL,
                    scoring_methodology TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_risk_snap_ts ON enterprise_risk_snapshots(timestamp);

                -- 2. Actionable Recommendations Table (Module 5.3)
                CREATE TABLE IF NOT EXISTS enterprise_recommendations (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    description TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    priority INTEGER NOT NULL,
                    target_dataset TEXT NOT NULL,
                    target_table TEXT,
                    target_column TEXT,
                    entity_name TEXT,
                    rationale TEXT NOT NULL,
                    supporting_evidence TEXT NOT NULL,
                    expected_impact TEXT NOT NULL,
                    status TEXT NOT NULL DEFAULT 'Pending',
                    assigned_to TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    resolution_notes TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_rec_status ON enterprise_recommendations(status);
                CREATE INDEX IF NOT EXISTS idx_rec_sev ON enterprise_recommendations(severity);
                CREATE INDEX IF NOT EXISTS idx_rec_tgt ON enterprise_recommendations(target_dataset, target_table);

                -- 3. Audit Trail Table (Module 5.4 & 5.7)
                CREATE TABLE IF NOT EXISTS enterprise_audit_log (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    user_email TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    target_resource TEXT NOT NULL,
                    details TEXT NOT NULL,
                    ip_address TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_audit_ts ON enterprise_audit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_user ON enterprise_audit_log(user_email);
                CREATE INDEX IF NOT EXISTS idx_audit_action ON enterprise_audit_log(action_type);

                -- 4. Continuous Monitoring Alerts Table (Module 5.5)
                CREATE TABLE IF NOT EXISTS enterprise_alerts (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    source_dataset TEXT NOT NULL,
                    source_table TEXT,
                    source_column TEXT,
                    entity_name TEXT,
                    status TEXT NOT NULL DEFAULT 'Active',
                    dedup_key TEXT UNIQUE NOT NULL,
                    evidence_ref TEXT,
                    acknowledged_by TEXT,
                    acknowledged_at TEXT,
                    resolved_by TEXT,
                    resolved_at TEXT,
                    resolution_notes TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_alerts_status ON enterprise_alerts(status);
                CREATE INDEX IF NOT EXISTS idx_alerts_sev ON enterprise_alerts(severity);
                CREATE INDEX IF NOT EXISTS idx_alerts_cat ON enterprise_alerts(category);
                CREATE INDEX IF NOT EXISTS idx_alerts_dedup ON enterprise_alerts(dedup_key);

                -- 5. Compliance & ROPA Snapshots Table (Module 5.4)
                CREATE TABLE IF NOT EXISTS enterprise_compliance_snapshots (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    framework TEXT NOT NULL,
                    readiness_score REAL NOT NULL,
                    verified_controls INTEGER NOT NULL,
                    total_controls INTEGER NOT NULL,
                    controls_data TEXT NOT NULL,
                    ropa_activities_data TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_comp_ts ON enterprise_compliance_snapshots(timestamp);
                CREATE INDEX IF NOT EXISTS idx_comp_fw ON enterprise_compliance_snapshots(framework);
                """
            )
            logger.info("Initialized Phase 5.2 - 5.7 enterprise database tables successfully.")
    finally:
        if should_close:
            conn.close()
