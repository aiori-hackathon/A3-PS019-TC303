"""
backend/enterprise/models.py
============================
Enterprise Pydantic schemas for Phase 5.2 - 5.7:
- Module 5.2: Intelligent Risk Assessment
- Module 5.3: AI Recommendations & Actionable Insights
- Module 5.4: Compliance & Audit Intelligence (ROPA, GDPR, DPDP, CCPA)
- Module 5.5: Continuous Monitoring & Alerts
- Module 5.6: Executive Intelligence Dashboard
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


# ============================================================================
# Enums
# ============================================================================

class RiskSeverity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    UNKNOWN = "Unknown"


class RecommendationStatus(str, Enum):
    PENDING = "Pending"
    ACCEPTED = "Accepted"
    IN_PROGRESS = "In Progress"
    COMPLETED = "Completed"
    DISMISSED = "Dismissed"


class ComplianceStatus(str, Enum):
    VERIFIED = "Verified"
    PARTIALLY_SUPPORTED = "Partially Supported"
    MISSING_EVIDENCE = "Missing Evidence"
    NOT_ASSESSED = "Not Assessed"


class AlertSeverity(str, Enum):
    CRITICAL = "Critical"
    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    INFO = "Info"


class AlertStatus(str, Enum):
    ACTIVE = "Active"
    ACKNOWLEDGED = "Acknowledged"
    RESOLVED = "Resolved"
    SUPPRESSED = "Suppressed"


class AlertCategory(str, Enum):
    PII_EXPOSURE = "PII_EXPOSURE"
    EVIDENCE_INTEGRITY_GAP = "EVIDENCE_INTEGRITY_GAP"
    EGRESS_ANOMALY = "EGRESS_ANOMALY"
    RELATIONSHIP_UNVERIFIED = "RELATIONSHIP_UNVERIFIED"
    COMPLIANCE_DRIFT = "COMPLIANCE_DRIFT"


# ============================================================================
# Module 5.2: Risk Assessment Models
# ============================================================================

class RiskContributingFactor(BaseModel):
    category: str  # e.g., "Data Sensitivity", "Relational Exposure", "Evidence Gaps", "Egress Surface"
    description: str
    weight: float
    score_contribution: float  # Points added to total risk score (0-100)


class FieldRiskRecord(BaseModel):
    field_key: str  # e.g., "customers.csv:email" or "privacy_demo.db:customers.ssn"
    dataset: str
    table_name: str
    column_name: str
    entity_name: str
    pii_class: str
    is_direct_identifier: bool
    risk_score: float  # 0.0 - 100.0
    severity: RiskSeverity
    contributing_factors: List[RiskContributingFactor]
    rationale: str
    evidence_status: str  # "Verified", "Unverified", "Missing Proof"
    egress_observed: bool = False
    hop_distance_from_origin: int = 0


class TableRiskRecord(BaseModel):
    table_key: str  # e.g. "privacy_demo.db:customers"
    dataset: str
    table_name: str
    entity_name: str
    total_fields: int
    pii_fields_count: int
    max_risk_score: float
    average_risk_score: float
    severity: RiskSeverity
    critical_factors: List[str]
    unverified_relationships_count: int
    missing_proofs_count: int


class RiskSnapshot(BaseModel):
    snapshot_id: str
    timestamp: str
    overall_risk_score: float
    severity: RiskSeverity
    total_assessed_fields: int
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    unknown_count: int
    top_risk_tables: List[TableRiskRecord]
    top_risk_fields: List[FieldRiskRecord]
    scoring_methodology: str


# ============================================================================
# Module 5.3: Recommendations Models
# ============================================================================

class Recommendation(BaseModel):
    id: str
    title: str
    description: str
    action_type: str  # e.g., "ENFORCE_CONSTRAINT", "PSEUDONYMIZE", "REMEDIATE_EGRESS", "VERIFY_EVIDENCE"
    severity: RiskSeverity
    priority: int  # 1 (Highest) to 5 (Lowest)
    target_dataset: str
    target_table: Optional[str] = None
    target_column: Optional[str] = None
    entity_name: Optional[str] = None
    rationale: str
    supporting_evidence: List[str]
    expected_impact: str
    status: RecommendationStatus = RecommendationStatus.PENDING
    assigned_to: Optional[str] = None
    created_at: str
    updated_at: str
    resolution_notes: Optional[str] = None


class RecommendationUpdate(BaseModel):
    status: RecommendationStatus
    notes: Optional[str] = None
    assigned_to: Optional[str] = None


# ============================================================================
# Module 5.4: Compliance & Audit Models
# ============================================================================

class ComplianceControl(BaseModel):
    control_id: str  # e.g. "GDPR-ART-5-MINIMIZATION", "DPDP-SEC-6-CONSENT"
    framework: str  # "GDPR", "DPDP_ACT_2023", "CCPA_CPRA"
    name: str
    description: str
    status: ComplianceStatus
    compliance_score: float  # 0.0 - 100.0
    evidence_count: int
    evidence_details: List[str]
    gaps_identified: List[str]
    remediation_guidance: str


class FrameworkReadiness(BaseModel):
    framework: str
    framework_name: str
    overall_readiness_pct: float
    verified_controls: int
    partial_controls: int
    missing_evidence_controls: int
    total_controls: int
    controls: List[ComplianceControl]
    audit_disclaimer: str


class ROPAProcessingActivity(BaseModel):
    activity_id: str
    activity_name: str
    business_purpose: str
    data_subjects: List[str]
    categories_of_personal_data: List[str]
    storage_locations: List[str]
    retention_policy: str
    recipients_and_egress: List[str]
    security_safeguards: str
    verification_status: str
    evidence_refs: List[str]


class ROPAReport(BaseModel):
    generated_at: str
    organization_name: str
    activities: List[ROPAProcessingActivity]
    total_activities: int
    verified_activities_pct: float
    evidence_inventory_timestamp: str


class AuditLogEntry(BaseModel):
    id: str
    timestamp: str
    user_email: str
    action_type: str  # e.g. "SCAN_EXECUTE", "RECOMMENDATION_ACCEPT", "ALERT_RESOLVE", "ROPA_EXPORT"
    target_resource: str
    details: Dict[str, Any]
    ip_address: Optional[str] = None


# ============================================================================
# Module 5.5: Continuous Monitoring & Alerts Models
# ============================================================================

class MonitoringAlert(BaseModel):
    id: str
    timestamp: str
    title: str
    message: str
    severity: AlertSeverity
    category: AlertCategory
    source_dataset: str
    source_table: Optional[str] = None
    source_column: Optional[str] = None
    entity_name: Optional[str] = None
    status: AlertStatus = AlertStatus.ACTIVE
    dedup_key: str
    evidence_ref: Optional[str] = None
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[str] = None
    resolved_by: Optional[str] = None
    resolved_at: Optional[str] = None
    resolution_notes: Optional[str] = None


class AlertStatusUpdate(BaseModel):
    status: AlertStatus
    notes: Optional[str] = None


# ============================================================================
# Module 5.6: Executive Dashboard Models
# ============================================================================

class ExecutiveKPICards(BaseModel):
    overall_privacy_posture_score: float  # 0 - 100
    posture_status: str  # "Robust", "Moderate", "Elevated Risk", "Critical"
    total_sensitive_attributes: int
    critical_and_high_risk_findings: int
    evidence_coverage_pct: float
    verified_relationships_count: int
    unverified_relationships_count: int
    missing_proofs_count: int
    open_recommendations_count: int
    active_critical_alerts_count: int


class ExecutiveDashboardData(BaseModel):
    kpis: ExecutiveKPICards
    risk_distribution: Dict[str, int]  # {"Critical": X, "High": Y, "Medium": Z, "Low": W}
    framework_readiness: List[Dict[str, Any]]
    top_vulnerable_datasets: List[Dict[str, Any]]
    recent_audit_events: List[AuditLogEntry]
    active_alerts: List[MonitoringAlert]
    high_priority_recommendations: List[Recommendation]
    historical_trend: List[Dict[str, Any]]
