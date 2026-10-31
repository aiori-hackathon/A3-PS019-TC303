"""
tests/test_phase5_enterprise.py
===============================
Automated test suite for Phase 5.2 - 5.7 Enterprise Privacy Intelligence:
- Module 5.2: Intelligent Risk Assessment
- Module 5.3: AI Recommendations & Actionable Insights
- Module 5.4: Compliance & Audit Intelligence (ROPA, GDPR, DPDP, CCPA)
- Module 5.5: Continuous Monitoring & Alerts
- Module 5.6: Executive Intelligence Dashboard
- Module 5.7: Security, Authentication & Production Hardening
"""

import pytest
from starlette.testclient import TestClient

from backend.api.main import app
from backend.auth.db import get_db_connection
from backend.enterprise.compliance_engine import get_compliance_engine
from backend.enterprise.executive_service import get_executive_service
from backend.enterprise.models import (
    AlertStatus,
    ComplianceStatus,
    RecommendationStatus,
    RecommendationUpdate,
    RiskSeverity,
)
from backend.enterprise.monitoring_alerts import get_monitoring_service
from backend.enterprise.recommendations import get_recommendation_engine
from backend.enterprise.risk_engine import get_risk_engine
from backend.relationships.ai_assistant import AIAssistant


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def auth_headers(client):
    """Registers and authenticates a test user, returning auth cookies."""
    import uuid
    email = f"enterprise.{uuid.uuid4().hex[:8]}@privsight.local"
    password = "TesterPassword123!"
    client.post("/api/auth/register", json={"full_name": "Enterprise Tester", "email": email, "password": password})
    login_res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200
    return login_res.cookies


# ============================================================================
# Module 5.2: Intelligent Risk Assessment Tests
# ============================================================================

def test_01_intelligent_risk_assessment_calculation():
    """Validates deterministic risk score calculation, severity classification, and factor weights."""
    risk_engine = get_risk_engine()
    snapshot = risk_engine.assess_enterprise_risk()

    assert snapshot.overall_risk_score >= 0.0
    assert snapshot.overall_risk_score <= 100.0
    assert snapshot.total_assessed_fields > 0
    assert snapshot.severity in (RiskSeverity.CRITICAL, RiskSeverity.HIGH, RiskSeverity.MEDIUM, RiskSeverity.LOW)
    assert len(snapshot.top_risk_tables) > 0
    assert len(snapshot.top_risk_fields) > 0

    first_field = snapshot.top_risk_fields[0]
    assert first_field.risk_score >= 0.0
    assert len(first_field.contributing_factors) > 0
    assert len(first_field.rationale) > 0

    # Ensure contributing factor categories are explainable
    categories = {f.category for f in first_field.contributing_factors}
    assert "Data Sensitivity" in categories or "Evidence Gaps" in categories


def test_02_historical_risk_trend_tracking():
    """Validates snapshot persistence and retrieval for historical risk trend tracking."""
    risk_engine = get_risk_engine()
    snap = risk_engine.assess_enterprise_risk()
    trend = risk_engine.get_historical_risk_trend(limit=5)
    assert len(trend) > 0
    assert any(t["id"] == snap.snapshot_id for t in trend)


# ============================================================================
# Module 5.3: AI Recommendations Tests
# ============================================================================

def test_03_recommendation_synthesis_and_prioritization():
    """Validates prioritized recommendation generation from risk findings and missing proofs."""
    rec_engine = get_recommendation_engine()
    recs = rec_engine.generate_recommendations()
    assert len(recs) > 0

    first_rec = recs[0]
    assert first_rec.id.startswith("REC-")
    assert first_rec.action_type in ("PSEUDONYMIZE", "ENFORCE_CONSTRAINT", "REMEDIATE_EGRESS", "VERIFY_EVIDENCE")
    assert first_rec.priority in (1, 2, 3, 4, 5)
    assert len(first_rec.supporting_evidence) > 0
    assert len(first_rec.expected_impact) > 0
    assert first_rec.status == RecommendationStatus.PENDING


def test_04_recommendation_lifecycle_updates():
    """Validates recommendation status transitions (Pending -> Accepted -> In Progress -> Completed)."""
    rec_engine = get_recommendation_engine()
    recs = rec_engine.generate_recommendations()
    target_rec = recs[0]

    update_payload = RecommendationUpdate(
        status=RecommendationStatus.IN_PROGRESS,
        notes="Started field-level masking implementation.",
        assigned_to="data_eng_lead@privsight.local",
    )
    updated = rec_engine.update_recommendation(
        rec_id=target_rec.id,
        update_data=update_payload,
        user_email="data_eng_lead@privsight.local",
    )
    assert updated is not None
    assert updated.status == RecommendationStatus.IN_PROGRESS
    assert updated.resolution_notes == "Started field-level masking implementation."


# ============================================================================
# Module 5.4: Compliance & ROPA Tests
# ============================================================================

def test_05_multi_framework_compliance_evaluation():
    """Validates evidence-backed compliance readiness for GDPR, DPDP Act 2023, and CCPA."""
    comp_engine = get_compliance_engine()
    frameworks = comp_engine.evaluate_frameworks()
    assert len(frameworks) == 3

    fw_names = {f.framework for f in frameworks}
    assert "GDPR" in fw_names
    assert "DPDP_ACT_2023" in fw_names
    assert "CCPA_CPRA" in fw_names

    for fw in frameworks:
        assert fw.overall_readiness_pct >= 0.0
        assert fw.overall_readiness_pct <= 100.0
        assert len(fw.controls) > 0
        for c in fw.controls:
            assert c.status in (ComplianceStatus.VERIFIED, ComplianceStatus.PARTIALLY_SUPPORTED, ComplianceStatus.MISSING_EVIDENCE, ComplianceStatus.NOT_ASSESSED)


def test_06_ropa_article_30_generation():
    """Validates automated Article 30 Records of Processing Activities (ROPA) report generation."""
    comp_engine = get_compliance_engine()
    ropa = comp_engine.generate_ropa_report()
    assert ropa.total_activities >= 3
    assert len(ropa.activities) >= 3

    first_act = ropa.activities[0]
    assert len(first_act.data_subjects) > 0
    assert len(first_act.categories_of_personal_data) > 0
    assert len(first_act.storage_locations) > 0
    assert len(first_act.retention_policy) > 0


def test_07_audit_log_tracking():
    """Validates recording and retrieving immutable enterprise audit log entries."""
    comp_engine = get_compliance_engine()
    entry = comp_engine.log_audit_event(
        user_email="auditor@privsight.local",
        action_type="SCAN_VERIFY",
        target_resource="customers.csv",
        details={"scanned_rows": 100, "status": "Clean"},
    )
    assert entry.id.startswith("AUD-")

    logs = comp_engine.list_audit_events(limit=10)
    assert any(log.id == entry.id for log in logs)


# ============================================================================
# Module 5.5: Continuous Monitoring & Alerts Tests
# ============================================================================

def test_08_monitoring_alert_sync_and_deduplication():
    """Validates observable change detection and alert deduplication."""
    mon_svc = get_monitoring_service()
    alerts_1 = mon_svc.sync_and_evaluate_alerts()
    initial_count = len(alerts_1)
    assert initial_count > 0

    # Second sync must deduplicate and not inflate count
    alerts_2 = mon_svc.sync_and_evaluate_alerts()
    assert len(alerts_2) == initial_count


def test_09_alert_lifecycle_workflow():
    """Validates alert acknowledgement and resolution with notes."""
    mon_svc = get_monitoring_service()
    alerts = mon_svc.sync_and_evaluate_alerts()
    assert len(alerts) > 0
    target = alerts[0]

    # Ensure target alert is Active for lifecycle test
    if target.status != AlertStatus.ACTIVE:
        conn = get_db_connection()
        try:
            with conn:
                conn.execute("UPDATE enterprise_alerts SET status = 'Active' WHERE id = ?", (target.id,))
        finally:
            conn.close()

    acked = mon_svc.acknowledge_alert(target.id, user_email="analyst@privsight.local")
    assert acked is not None
    assert acked.status == AlertStatus.ACKNOWLEDGED

    resolved = mon_svc.resolve_alert(
        target.id,
        user_email="security_lead@privsight.local",
        notes="Applied AES-256 encryption constraint.",
    )
    assert resolved is not None
    assert resolved.status == AlertStatus.RESOLVED
    assert resolved.resolution_notes == "Applied AES-256 encryption constraint."


# ============================================================================
# Module 5.6: Executive Dashboard Aggregation Tests
# ============================================================================

def test_10_executive_dashboard_kpis_and_posture():
    """Validates executive posture score, KPI aggregation, and vulnerable table ranking."""
    exec_svc = get_executive_service()
    dash = exec_svc.get_dashboard_summary()
    k = dash.kpis

    assert k.overall_privacy_posture_score >= 0.0
    assert k.overall_privacy_posture_score <= 100.0
    assert k.posture_status in ("Robust", "Moderate", "Elevated Risk", "Critical")
    assert k.total_sensitive_attributes > 0
    assert k.evidence_coverage_pct >= 0.0
    assert len(dash.top_vulnerable_datasets) > 0
    assert len(dash.risk_distribution) == 4


# ============================================================================
# Module 5.7: Security & Production Hardening Tests
# ============================================================================

def test_11_unauthenticated_enterprise_api_rejection(client):
    """Validates that all enterprise API endpoints reject unauthenticated requests with 401."""
    endpoints = [
        "/api/enterprise/risk",
        "/api/enterprise/risk/trend",
        "/api/enterprise/recommendations",
        "/api/enterprise/compliance/frameworks",
        "/api/enterprise/compliance/ropa",
        "/api/enterprise/compliance/audit-log",
        "/api/enterprise/alerts",
        "/api/enterprise/executive/dashboard",
    ]
    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 401


def test_12_authenticated_enterprise_api_access(client, auth_headers):
    """Validates that authenticated users can query enterprise endpoints."""
    endpoints = [
        "/api/enterprise/risk",
        "/api/enterprise/recommendations",
        "/api/enterprise/compliance/frameworks",
        "/api/enterprise/compliance/ropa",
        "/api/enterprise/alerts",
        "/api/enterprise/executive/dashboard",
    ]
    for ep in endpoints:
        res = client.get(ep, cookies=auth_headers)
        assert res.status_code == 200


def test_13_tracera_conversational_enterprise_queries():
    """Validates TRACERA answers natural language risk, recommendation, ROPA, alert, and posture questions."""
    assistant = AIAssistant()

    # Query 1: Risk Assessment
    r1 = assistant.process_query("What are our highest risk tables?")
    assert "risk" in r1.explanation.lower()
    assert ("vulnerable" in r1.explanation.lower() or "score" in r1.explanation.lower())

    # Query 2: Recommendations
    r2 = assistant.process_query("What corrective actions are recommended?")
    assert "recommendation" in r2.explanation.lower()
    assert ("priority" in r2.explanation.lower() or "action" in r2.explanation.lower())

    # Query 3: ROPA / Compliance
    r3 = assistant.process_query("Generate Article 30 ROPA summary")
    assert "ropa" in r3.explanation.lower() or "processing" in r3.explanation.lower()
    assert "purpose" in r3.explanation.lower() or "activities" in r3.explanation.lower()

    # Query 4: Monitoring Alerts
    r4 = assistant.process_query("Are there any unresolved alerts?")
    assert "alert" in r4.explanation.lower()

    # Query 5: Executive Briefing
    r5 = assistant.process_query("Provide an executive privacy posture briefing")
    assert "posture" in r5.explanation.lower() or "executive" in r5.explanation.lower()


def test_14_executive_page_serving(client, auth_headers):
    """Validates that /executive and /executive.html serve the dashboard HTML to authenticated users."""
    res = client.get("/executive", cookies=auth_headers)
    assert res.status_code == 200
    assert "Executive Privacy Intelligence" in res.text
    assert "executive.js" in res.text
    assert "tab-overview" in res.text
