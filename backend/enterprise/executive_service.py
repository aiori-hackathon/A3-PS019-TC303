"""
backend/enterprise/executive_service.py
=======================================
Module 5.6: Executive Intelligence Dashboard Aggregator
- Compiles consolidated executive metrics, privacy posture score,
  evidence coverage, risk distributions, and recent audit events.
- Never uses fabricated demo numbers; calculates strictly from actual findings.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from backend.enterprise.compliance_engine import get_compliance_engine
from backend.enterprise.models import (
    ExecutiveDashboardData,
    ExecutiveKPICards,
    RiskSeverity,
)
from backend.enterprise.monitoring_alerts import get_monitoring_service
from backend.enterprise.recommendations import get_recommendation_engine
from backend.enterprise.risk_engine import get_risk_engine
from backend.lineage.engine import get_lineage_engine
from backend.lineage.ledger import get_evidence_ledger

logger = logging.getLogger("privsight.enterprise.executive")


class ExecutiveDashboardService:
    """Aggregates enterprise-level privacy intelligence for C-level dashboards."""

    def __init__(self):
        pass

    def get_dashboard_summary(self) -> ExecutiveDashboardData:
        """
        Compiles consolidated executive data from Risk Engine, Compliance Engine,
        Recommendation Engine, Monitoring Service, and Lineage DAG.
        """
        risk_engine = get_risk_engine()
        snapshot = risk_engine.assess_enterprise_risk()
        rec_engine = get_recommendation_engine()
        all_recs = rec_engine.generate_recommendations()
        comp_engine = get_compliance_engine()
        frameworks = comp_engine.evaluate_frameworks()
        monitoring = get_monitoring_service()
        all_alerts = monitoring.sync_and_evaluate_alerts()
        audit_events = comp_engine.list_audit_events(limit=10)
        lineage_eng = get_lineage_engine()
        lineage_dag = lineage_eng.build_directional_dag()
        ledger = get_evidence_ledger()
        ledger_result = ledger.verify_ledger_integrity()

        # 1. Calculate KPI Metrics
        total_attrs = snapshot.total_assessed_fields
        crit_high_count = snapshot.critical_count + snapshot.high_count
        missing_count = sum(t.missing_proofs_count for t in snapshot.top_risk_tables)
        
        # Evidence coverage percentage: verified items / total items
        verified_items = total_attrs - missing_count
        evidence_cov = round((verified_items / total_attrs) * 100.0, 1) if total_attrs > 0 else 100.0

        # Verified vs Inferred edges from Lineage DAG
        verified_edges = sum(1 for e in lineage_dag.edges if e.verification_status == "Verified")
        inferred_edges = sum(1 for e in lineage_dag.edges if e.verification_status != "Verified")

        # Open recommendations
        open_recs = [r for r in all_recs if r.status in ("Pending", "Accepted", "In Progress")]
        active_crit_alerts = [a for a in all_alerts if a.status == "Active" and a.severity == "Critical"]

        # Overall Privacy Posture Score (0 - 100)
        # Higher is better: 100 - risk_deductions
        base_posture = 100.0 - (snapshot.overall_risk_score * 0.45)
        evidence_bonus = (evidence_cov / 100.0) * 25.0
        compliance_avg = sum(f.overall_readiness_pct for f in frameworks) / len(frameworks) if frameworks else 80.0
        compliance_contrib = (compliance_avg / 100.0) * 20.0
        ledger_bonus = 10.0 if ledger_result.is_valid else 0.0

        posture_score = round(min(100.0, max(0.0, (base_posture * 0.45) + evidence_bonus + compliance_contrib + ledger_bonus)), 1)
        if posture_score >= 80.0:
            posture_status = "Robust"
        elif posture_score >= 65.0:
            posture_status = "Moderate"
        elif posture_score >= 50.0:
            posture_status = "Elevated Risk"
        else:
            posture_status = "Critical"

        kpis = ExecutiveKPICards(
            overall_privacy_posture_score=posture_score,
            posture_status=posture_status,
            total_sensitive_attributes=total_attrs,
            critical_and_high_risk_findings=crit_high_count,
            evidence_coverage_pct=evidence_cov,
            verified_relationships_count=verified_edges,
            unverified_relationships_count=inferred_edges,
            missing_proofs_count=missing_count,
            open_recommendations_count=len(open_recs),
            active_critical_alerts_count=len(active_crit_alerts),
        )

        # 2. Risk Distribution
        risk_dist = {
            "Critical": snapshot.critical_count,
            "High": snapshot.high_count,
            "Medium": snapshot.medium_count,
            "Low": snapshot.low_count,
        }

        # 3. Framework Readiness summary
        fw_summary = []
        for fw in frameworks:
            fw_summary.append({
                "framework": fw.framework,
                "name": fw.framework_name,
                "readiness_pct": fw.overall_readiness_pct,
                "verified_controls": fw.verified_controls,
                "total_controls": fw.total_controls,
            })

        # 4. Top Vulnerable Datasets
        top_datasets = []
        for t in snapshot.top_risk_tables[:6]:
            top_datasets.append({
                "dataset": t.dataset,
                "table_name": t.table_name,
                "entity": t.entity_name,
                "max_risk_score": t.max_risk_score,
                "severity": t.severity.value,
                "missing_proofs": t.missing_proofs_count,
                "critical_factors": t.critical_factors,
            })

        # 5. Historical Trend
        history = risk_engine.get_historical_risk_trend(limit=8)

        return ExecutiveDashboardData(
            kpis=kpis,
            risk_distribution=risk_dist,
            framework_readiness=fw_summary,
            top_vulnerable_datasets=top_datasets,
            recent_audit_events=audit_events,
            active_alerts=all_alerts[:6],
            high_priority_recommendations=open_recs[:6],
            historical_trend=history,
        )


_executive_service_instance: Optional[ExecutiveDashboardService] = None


def get_executive_service() -> ExecutiveDashboardService:
    global _executive_service_instance
    if _executive_service_instance is None:
        _executive_service_instance = ExecutiveDashboardService()
    return _executive_service_instance
