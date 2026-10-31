"""
backend/lineage/models.py
=========================
Pydantic data models for Phase 5.1:
- Directional Data Lineage DAG
- SHA-256 Evidence Integrity Ledger
- Cross-System Data Egress Tracking
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

LineageStage = Literal["Ingestion", "Storage", "Processing", "Egress", "Unknown"]
VerificationStatus = Literal[
    "Verified",
    "Inferred",
    "Unverified",
    "No Match",
    "Possible",
    "Needs Review",
    "Rejected",
]


class LineageNode(BaseModel):
    """Represents a specific column, field, or dataset in the directional lineage graph."""
    id: str = Field(description="Unique node identifier, e.g. 'customers.csv:email'")
    label: str = Field(description="Human-readable node label")
    dataset: str = Field(description="Dataset or file name")
    table: Optional[str] = Field(default=None, description="Table name if SQL")
    column: str = Field(description="Column or attribute name")
    stage: LineageStage = Field(default="Storage", description="Data lifecycle stage")
    entity: str = Field(description="Underlying entity name e.g. 'Customer'")
    data_class: Optional[str] = Field(default=None, description="Detected personal data class")
    is_pii: bool = Field(default=False, description="Whether this column holds candidate personal data")
    masked_preview: Optional[str] = Field(default=None, description="Safe masked sample preview")
    is_origin: bool = Field(default=False, description="True if this is the initial origin point")
    is_egress: bool = Field(default=False, description="True if this node represents an export/egress point")


class LineageEdge(BaseModel):
    """Represents directional movement or constraint linking an upstream to a downstream node."""
    id: str = Field(description="Unique edge identifier")
    source: str = Field(description="Source/upstream node ID")
    target: str = Field(description="Target/downstream node ID")
    direction: str = Field(default="upstream_to_downstream", description="Directional flow indicator")
    edge_type: str = Field(description="'foreign_key_flow', 'identifier_replication', 'export_egress', 'reporting_aggregation'")
    verification_status: VerificationStatus = Field(default="Verified", description="Verification level")
    confidence: float = Field(ge=0.0, le=1.0, default=1.0)
    evidence: str = Field(description="Detailed verification evidence explanation")
    cardinality: str = Field(default="1:N", description="1:1, 1:N, N:M")
    discovery_method: str = Field(description="e.g. 'SQLite FK Constraint', 'Exact Identifier Overlap', 'Report Export'")
    evidence_hash: Optional[str] = Field(default=None, description="SHA-256 hash in integrity ledger")


class LineageDAG(BaseModel):
    """Complete directed acyclic graph representing end-to-end data lineage."""
    nodes: List[LineageNode] = Field(default_factory=list)
    edges: List[LineageEdge] = Field(default_factory=list)
    origins: List[str] = Field(default_factory=list, description="IDs of origin/source nodes")
    egress_points: List[str] = Field(default_factory=list, description="IDs of egress/export destination nodes")
    total_stages: Dict[str, int] = Field(default_factory=dict, description="Node counts per lifecycle stage")
    summary: str = Field(description="Summary of lineage topology and verification posture")


class EvidenceLedgerEntry(BaseModel):
    """An immutable, append-only evidence block with SHA-256 cryptographic linkage."""
    id: str
    sequence: int
    timestamp: str
    source_ref: str
    target_ref: str
    evidence_type: str
    verification_status: str
    confidence: float
    proof_details: str
    previous_hash: str
    current_hash: str


class LedgerVerificationResult(BaseModel):
    """Audit report for SHA-256 hash-chain verification."""
    is_valid: bool
    total_entries: int
    verified_entries: int
    genesis_hash: str
    tip_hash: str
    tampered_entries: List[int] = Field(default_factory=list)
    verification_message: str
    verified_at: str

    @property
    def total_records(self) -> int:
        return self.total_entries

    @property
    def message(self) -> str:
        return self.verification_message

    @property
    def failed_block_sequence(self) -> Optional[int]:
        return self.tampered_entries[0] if self.tampered_entries else None


class EgressEvent(BaseModel):
    """Record of an observable data egress or cross-dataset copying operation."""
    id: str
    timestamp: str
    operation_type: str  # 'CSV_EXPORT', 'REPORTING_REPLICATION', 'DATABASE_MIRROR', 'FILE_DOWNLOAD'
    source_dataset: str
    source_table: Optional[str] = None
    source_column: str
    destination_dataset: str
    destination_type: str  # 'CSV_FILE', 'SQL_TABLE', 'REPORT_EXPORT', 'EXTERNAL_STORE'
    entity_name: str
    record_count: int
    evidence: str
    verification_status: str
    pii_classes: List[str] = Field(default_factory=list)
    ledger_block_hash: Optional[str] = None
