"""
backend/lineage/routes.py
=========================
FastAPI API endpoints for Phase 5.1:
- Directional Data Lineage DAG
- SHA-256 Evidence Integrity Ledger
- Cross-System Data Egress Tracking
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend.auth.models import UserResponse
from backend.auth.routes import get_authenticated_user
from backend.lineage.egress import get_egress_tracker
from backend.lineage.engine import get_lineage_engine
from backend.lineage.ledger import get_evidence_ledger
from backend.lineage.models import (
    EgressEvent,
    EvidenceLedgerEntry,
    LedgerVerificationResult,
    LineageDAG,
    LineageEdge,
)

logger = logging.getLogger("privsight.lineage.routes")

lineage_router = APIRouter(prefix="/api/lineage", tags=["Directional Data Lineage & Evidence Integrity"])


@lineage_router.get("/dag", response_model=LineageDAG)
def get_directional_lineage_dag(
    focus_entity: Optional[str] = Query(None, description="Optional entity filter e.g. Customer, Order"),
    focus_field: Optional[str] = Query(None, description="Optional column or field filter"),
    user: UserResponse = Depends(get_authenticated_user),
) -> LineageDAG:
    """
    Returns the directional Data Lineage DAG:
    - Preserves directional movement: Ingestion -> Storage -> Processing -> Egress
    - Connects database foreign keys and verified value overlaps
    - Integrates observable data egress events
    """
    engine = get_lineage_engine()
    return engine.build_directional_dag(focus_entity=focus_entity, focus_field=focus_field)


@lineage_router.get("/origin/{field_key}")
def trace_field_origin(
    field_key: str,
    user: UserResponse = Depends(get_authenticated_user),
) -> Dict[str, Any]:
    """Traces backwards across directional flows to identify the initial source of origin."""
    engine = get_lineage_engine()
    res = engine.get_origin_for_field(field_key)
    if res.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=res.get("message"))
    return res


@lineage_router.get("/path", response_model=Dict[str, Any])
def trace_lineage_path(
    source: str = Query(..., description="Source field e.g. 'customers.csv:customer_id'"),
    target: str = Query(..., description="Target field e.g. 'relational_demo.db:orders:customer_id'"),
    user: UserResponse = Depends(get_authenticated_user),
) -> Dict[str, Any]:
    """Computes directional step-by-step lineage path between two fields."""
    engine = get_lineage_engine()
    path = engine.get_complete_lineage_path(source, target)
    if path is None:
        raise HTTPException(
            status_code=404,
            detail=f"No directional lineage path discovered from '{source}' to '{target}'.",
        )
    return {
        "status": "success",
        "source": source,
        "target": target,
        "hops_count": len(path),
        "path": [e.model_dump() for e in path],
    }


@lineage_router.get("/evidence-chain/{field_key}", response_model=List[EvidenceLedgerEntry])
def get_field_evidence_chain(
    field_key: str,
    user: UserResponse = Depends(get_authenticated_user),
) -> List[EvidenceLedgerEntry]:
    """Retrieves all cryptographically hashed evidence blocks associated with a specific field."""
    ledger = get_evidence_ledger()
    return ledger.get_evidence_for_field(field_key)


@lineage_router.get("/ledger", response_model=List[EvidenceLedgerEntry])
def get_evidence_ledger_blocks(
    limit: int = Query(50, ge=1, le=500),
    user: UserResponse = Depends(get_authenticated_user),
) -> List[EvidenceLedgerEntry]:
    """Returns recent blocks from the append-only SHA-256 evidence integrity ledger."""
    ledger = get_evidence_ledger()
    return ledger.get_ledger_history(limit=limit)


@lineage_router.post("/ledger/verify", response_model=LedgerVerificationResult)
def verify_ledger_integrity(
    user: UserResponse = Depends(get_authenticated_user),
) -> LedgerVerificationResult:
    """
    Audits the entire evidence integrity ledger from Genesis block to Tip:
    - Recomputes SHA-256 hashes for all evidence blocks
    - Validates cryptographic chaining
    - Detects any tampered, modified, or missing evidence
    """
    ledger = get_evidence_ledger()
    return ledger.verify_ledger_integrity()


@lineage_router.get("/egress", response_model=List[EgressEvent])
def list_data_egress_events(
    source: Optional[str] = Query(None),
    entity: Optional[str] = Query(None),
    operation: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=500),
    user: UserResponse = Depends(get_authenticated_user),
) -> List[EgressEvent]:
    """Retrieves observable cross-system data egress, copy, and export operations."""
    tracker = get_egress_tracker()
    return tracker.get_egress_events(source=source, entity=entity, operation=operation, limit=limit)


@lineage_router.post("/egress/scan", response_model=Dict[str, Any])
def scan_and_sync_egress(
    user: UserResponse = Depends(get_authenticated_user),
) -> Dict[str, Any]:
    """Syncs observable egress events from existing data exports and database mirrors."""
    tracker = get_egress_tracker()
    synced = tracker.sync_observable_egress()
    return {
        "status": "success",
        "synced_events_count": synced,
        "message": f"Synchronized {synced} observable cross-system egress events.",
    }
