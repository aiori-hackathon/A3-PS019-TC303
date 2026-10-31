"""
backend/enterprise/routes.py
============================
Enterprise REST APIs for Phase 5.2 - 5.7:
- Module 5.2: Intelligent Risk Assessment
- Module 5.3: AI Recommendations & Actionable Insights
- Module 5.4: Compliance & Audit Intelligence (ROPA, GDPR, DPDP, CCPA)
- Module 5.5: Continuous Monitoring & Alerts
- Module 5.6: Executive Intelligence Dashboard
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth.models import UserResponse
from backend.auth.routes import get_authenticated_user
from backend.enterprise.compliance_engine import get_compliance_engine
from backend.enterprise.executive_service import get_executive_service
from backend.enterprise.models import (
    AlertStatusUpdate,
    AuditLogEntry,
    ExecutiveDashboardData,
    FrameworkReadiness,
    MonitoringAlert,
    Recommendation,
    RecommendationUpdate,
    RiskSnapshot,
    ROPAReport,
)
from backend.enterprise.monitoring_alerts import get_monitoring_service
from backend.enterprise.recommendations import get_recommendation_engine
from backend.enterprise.risk_engine import get_risk_engine

logger = logging.getLogger("privsight.enterprise.routes")

enterprise_router = APIRouter(prefix="/api/enterprise", tags=["Enterprise Privacy Intelligence"])


# ============================================================================
# Module 5.2: Risk Assessment Endpoints
# ============================================================================

@enterprise_router.get("/risk", response_model=RiskSnapshot)
def get_enterprise_risk_assessment(
    user: UserResponse = Depends(get_authenticated_user),
) -> RiskSnapshot:
    """Computes and returns current explainable privacy risk assessment snapshot."""
    engine = get_risk_engine()
    return engine.assess_enterprise_risk()


@enterprise_router.get("/risk/trend", response_model=List[Dict[str, Any]])
def get_risk_trend(
    limit: int = Query(10, ge=1, le=50),
    user: UserResponse = Depends(get_authenticated_user),
) -> List[Dict[str, Any]]:
    """Retrieves chronological risk score snapshots for trend visualization."""
    engine = get_risk_engine()
    return engine.get_historical_risk_trend(limit=limit)


# ============================================================================
# Module 5.3: Actionable Recommendations Endpoints
# ============================================================================

@enterprise_router.get("/recommendations", response_model=List[Recommendation])
def list_recommendations(
    status: Optional[str] = Query(None, description="Filter by status: Pending, Accepted, In Progress, Completed, Dismissed"),
    severity: Optional[str] = Query(None, description="Filter by severity: Critical, High, Medium, Low"),
    limit: int = Query(100, ge=1, le=500),
    user: UserResponse = Depends(get_authenticated_user),
) -> List[Recommendation]:
    """Retrieves evidence-backed corrective recommendations."""
    engine = get_recommendation_engine()
    # Trigger refresh to include latest risk/egress findings
    engine.generate_recommendations()
    return engine.list_recommendations(status=status, severity=severity, limit=limit)


@enterprise_router.patch("/recommendations/{rec_id}", response_model=Recommendation)
def update_recommendation(
    rec_id: str,
    update_data: RecommendationUpdate,
    user: UserResponse = Depends(get_authenticated_user),
) -> Recommendation:
    """Updates status, assignment, or resolution notes for a recommendation."""
    engine = get_recommendation_engine()
    comp_engine = get_compliance_engine()
    updated = engine.update_recommendation(rec_id=rec_id, update_data=update_data, user_email=user.email)
    if not updated:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Recommendation with ID '{rec_id}' not found.",
        )
    # Log audit event
    comp_engine.log_audit_event(
        user_email=user.email,
        action_type="RECOMMENDATION_UPDATE",
        target_resource=f"Recommendation:{rec_id}",
        details={"status": update_data.status.value, "notes": update_data.notes},
    )
    return updated


# ============================================================================
# Module 5.4: Compliance & Audit Endpoints
# ============================================================================

@enterprise_router.get("/compliance/frameworks", response_model=List[FrameworkReadiness])
def get_framework_readiness(
    user: UserResponse = Depends(get_authenticated_user),
) -> List[FrameworkReadiness]:
    """Evaluates readiness against GDPR, India DPDP Act 2023, and CCPA/CPRA."""
    engine = get_compliance_engine()
    return engine.evaluate_frameworks()


@enterprise_router.get("/compliance/ropa", response_model=ROPAReport)
def get_ropa_report(
    user: UserResponse = Depends(get_authenticated_user),
) -> ROPAReport:
    """Generates automated Article 30 Records of Processing Activities (ROPA)."""
    engine = get_compliance_engine()
    report = engine.generate_ropa_report()
    engine.log_audit_event(
        user_email=user.email,
        action_type="ROPA_GENERATE",
        target_resource="ROPA Report",
        details={"total_activities": report.total_activities, "verified_pct": report.verified_activities_pct},
    )
    return report


@enterprise_router.get("/compliance/audit-log", response_model=List[AuditLogEntry])
def list_audit_log(
    limit: int = Query(50, ge=1, le=200),
    user: UserResponse = Depends(get_authenticated_user),
) -> List[AuditLogEntry]:
    """Retrieves immutable audit trail of major application actions."""
    engine = get_compliance_engine()
    return engine.list_audit_events(limit=limit)


# ============================================================================
# Module 5.5: Continuous Monitoring & Alerts Endpoints
# ============================================================================

@enterprise_router.get("/alerts", response_model=List[MonitoringAlert])
def list_alerts(
    status: Optional[str] = Query(None, description="Active, Acknowledged, Resolved, Suppressed"),
    severity: Optional[str] = Query(None, description="Critical, High, Medium, Low, Info"),
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    user: UserResponse = Depends(get_authenticated_user),
) -> List[MonitoringAlert]:
    """Queries active and historical continuous monitoring alerts."""
    service = get_monitoring_service()
    return service.list_alerts(status=status, severity=severity, category=category, limit=limit)


@enterprise_router.post("/alerts/sync", response_model=List[MonitoringAlert])
def sync_monitoring_alerts(
    user: UserResponse = Depends(get_authenticated_user),
) -> List[MonitoringAlert]:
    """Scans system state and synchronizes deduplicated monitoring alerts."""
    service = get_monitoring_service()
    return service.sync_and_evaluate_alerts()


@enterprise_router.post("/alerts/{alert_id}/acknowledge", response_model=MonitoringAlert)
def acknowledge_alert(
    alert_id: str,
    user: UserResponse = Depends(get_authenticated_user),
) -> MonitoringAlert:
    """Transitions alert status to Acknowledged."""
    service = get_monitoring_service()
    comp_engine = get_compliance_engine()
    alert = service.acknowledge_alert(alert_id, user_email=user.email)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found or already acknowledged.",
        )
    comp_engine.log_audit_event(
        user_email=user.email,
        action_type="ALERT_ACKNOWLEDGE",
        target_resource=f"Alert:{alert_id}",
        details={"status": "Acknowledged"},
    )
    return alert


@enterprise_router.post("/alerts/{alert_id}/resolve", response_model=MonitoringAlert)
def resolve_alert(
    alert_id: str,
    update_data: AlertStatusUpdate,
    user: UserResponse = Depends(get_authenticated_user),
) -> MonitoringAlert:
    """Transitions alert status to Resolved with remediation notes."""
    service = get_monitoring_service()
    comp_engine = get_compliance_engine()
    alert = service.resolve_alert(alert_id, user_email=user.email, notes=update_data.notes)
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert with ID '{alert_id}' not found.",
        )
    comp_engine.log_audit_event(
        user_email=user.email,
        action_type="ALERT_RESOLVE",
        target_resource=f"Alert:{alert_id}",
        details={"status": "Resolved", "notes": update_data.notes},
    )
    return alert


# ============================================================================
# Module 5.6: Executive Dashboard Endpoints
# ============================================================================

@enterprise_router.get("/executive/dashboard", response_model=ExecutiveDashboardData)
def get_executive_dashboard(
    user: UserResponse = Depends(get_authenticated_user),
) -> ExecutiveDashboardData:
    """Compiles unified Executive Intelligence Dashboard metrics and posture KPIs."""
    service = get_executive_service()
    return service.get_dashboard_summary()
