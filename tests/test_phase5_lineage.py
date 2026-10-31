"""
tests/test_phase5_lineage.py
============================
Comprehensive Automated Test Suite for PrivSight Phase 5.1:
- Directional Data Lineage DAG
- SHA-256 Cryptographic Evidence Integrity Ledger
- Cross-System Data Egress Tracking
- TRACERA Lineage & Integrity Query Intelligence
- Security, Authentication, and Migration Safety

Validates all 14 criteria specified in Phase 5.1 instructions.
"""

import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path
import pytest
from starlette.testclient import TestClient

from backend.api.main import app
from backend.auth.db import get_db_connection
from backend.lineage.egress import EgressTracker, get_egress_tracker
from backend.lineage.engine import DirectionalLineageEngine, get_lineage_engine
from backend.lineage.ledger import (
    GENESIS_HASH,
    EvidenceIntegrityLedger,
    compute_evidence_hash,
    get_evidence_ledger,
    init_lineage_tables,
)
from backend.lineage.models import (
    EgressEvent,
    EvidenceLedgerEntry,
    LedgerVerificationResult,
    LineageDAG,
)
from backend.relationships.ai_assistant import AIAssistant


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def auth_headers(client):
    """Creates a test user and logs in to get session cookie."""
    import uuid
    email = f"phase5.{uuid.uuid4().hex[:8]}@example.com"
    password = "TesterPassword123!"
    client.post("/api/auth/register", json={"full_name": "Phase 5 Tester", "email": email, "password": password})
    login_res = client.post("/api/auth/login", json={"email": email, "password": password})
    assert login_res.status_code == 200
    return login_res.cookies


# ============================================================================
# Criterion 1 & 2: Source Identification & Directional Lineage DAG
# ============================================================================

def test_01_directional_lineage_dag_structure():
    """Validates that Lineage DAG is constructed with strict lifecycle stages and directional flow."""
    engine = get_lineage_engine()
    dag = engine.build_directional_dag()

    assert isinstance(dag, LineageDAG)
    assert len(dag.nodes) > 0
    assert len(dag.edges) > 0
    assert len(dag.origins) > 0

    # Verify nodes have valid lifecycle stages
    valid_stages = {"Ingestion", "Storage", "Processing", "Egress", "Unknown"}
    for node in dag.nodes:
        assert node.stage in valid_stages
        assert node.dataset is not None
        assert node.column is not None

    # Verify origin nodes are Ingestion or Storage
    for orig_id in dag.origins:
        node = next((n for n in dag.nodes if n.id == orig_id), None)
        assert node is not None
        assert node.stage in ("Ingestion", "Storage")


def test_02_source_identification_and_origin_tracing():
    """Validates tracing backwards to discover original source system (e.g. customers.csv)."""
    engine = get_lineage_engine()
    res = engine.get_origin_for_field("customer_id")

    assert res["status"] == "success"
    assert res["origin_found"] is True
    assert len(res["primary_origins"]) > 0

    first_origin = res["primary_origins"][0]
    assert first_origin["stage"] in ("Ingestion", "Storage")
    assert "customer_id" in first_origin["column"].lower() or "customer" in first_origin["dataset"].lower()


# ============================================================================
# Criterion 3 & 4: Direct and Multi-Hop Relationships
# ============================================================================

def test_03_direct_and_multihop_directional_paths():
    """Validates that direct and multi-hop paths preserve directional source-to-destination progression."""
    engine = get_lineage_engine()
    dag = engine.build_directional_dag()

    # Verify edges maintain directional upstream-to-downstream semantics
    for edge in dag.edges:
        assert edge.direction == "upstream_to_downstream"
        assert edge.verification_status in ("Verified", "Inferred")
        assert edge.discovery_method is not None


# ============================================================================
# Criterion 5: Unknown or Incomplete Lineage
# ============================================================================

def test_04_unknown_field_gracefully_handled():
    """Validates that nonexistent fields do not invent synthetic lineage."""
    engine = get_lineage_engine()
    res = engine.get_origin_for_field("nonexistent_unknown_col_xyz")
    assert res["status"] == "not_found"
    assert res["origin_found"] is False


# ============================================================================
# Criterion 6, 7 & 8: SHA-256 Evidence Hash Generation & Tamper Detection
# ============================================================================

def test_05_evidence_hash_generation():
    """Validates deterministic SHA-256 calculation."""
    h1 = compute_evidence_hash(
        sequence=1,
        timestamp="2026-10-31T12:00:00Z",
        source_ref="customers.csv:customer_id",
        target_ref="orders.csv:customer_id",
        evidence_type="foreign_key",
        verification_status="Verified",
        confidence=1.0,
        proof_details="FK constraint verified",
        previous_hash=GENESIS_HASH,
    )
    assert len(h1) == 64
    assert isinstance(h1, str)

    # Identical payload produces identical hash
    h2 = compute_evidence_hash(
        sequence=1,
        timestamp="2026-10-31T12:00:00Z",
        source_ref="customers.csv:customer_id",
        target_ref="orders.csv:customer_id",
        evidence_type="foreign_key",
        verification_status="Verified",
        confidence=1.0,
        proof_details="FK constraint verified",
        previous_hash=GENESIS_HASH,
    )
    assert h1 == h2


def test_06_evidence_ledger_chain_integrity_verification():
    """Validates that ledger verification succeeds on an untampered database."""
    ledger = get_evidence_ledger()
    # Record an evidence entry
    entry = ledger.record_evidence(
        source_ref="test_source:id",
        target_ref="test_dest:id",
        evidence_type="TEST_VERIFICATION",
        verification_status="Verified",
        confidence=1.0,
        proof_details="Automated Test Proof",
    )
    assert entry.sequence > 0
    assert len(entry.current_hash) == 64

    # Run verification from genesis to tip
    res = ledger.verify_ledger_integrity()
    assert isinstance(res, LedgerVerificationResult)
    assert res.is_valid is True
    assert res.total_records >= 1
    assert res.genesis_hash == GENESIS_HASH


def test_07_tamper_detection_in_evidence_ledger():
    """Validates that corrupting a hash or modifying payload immediately breaks verification."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        tmp_db_path = Path(tmp.name)

    try:
        init_lineage_tables(tmp_db_path)
        isolated_ledger = EvidenceIntegrityLedger(tmp_db_path)

        # Append 3 blocks
        isolated_ledger.record_evidence("srcA", "tgtA", "PROOF_A", "Verified", 1.0, "details A")
        isolated_ledger.record_evidence("srcB", "tgtB", "PROOF_B", "Verified", 1.0, "details B")
        isolated_ledger.record_evidence("srcC", "tgtC", "PROOF_C", "Verified", 1.0, "details C")

        # Initial check must pass
        audit1 = isolated_ledger.verify_ledger_integrity()
        assert audit1.is_valid is True
        assert audit1.total_records == 3

        # Tamper: Modifying block 2 payload in SQLite directly
        conn = sqlite3.connect(tmp_db_path)
        with conn:
            conn.execute("UPDATE evidence_chain_ledger SET proof_details = 'TAMPERED DATA' WHERE sequence = 2")
        conn.close()

        # Audit must detect tamper and fail
        audit2 = isolated_ledger.verify_ledger_integrity()
        assert audit2.is_valid is False
        assert audit2.failed_block_sequence == 2
        assert "tamper" in audit2.message.lower() or "integrity failure" in audit2.message.lower()
    finally:
        if tmp_db_path.exists():
            tmp_db_path.unlink()


# ============================================================================
# Criterion 9 & 10: Observable Egress Tracking & Scope Limits
# ============================================================================

def test_08_observable_egress_tracking():
    """Validates recording and querying observable cross-system data egress operations."""
    tracker = get_egress_tracker()
    synced = tracker.sync_observable_egress()
    assert synced > 0

    events = tracker.get_egress_events(limit=50)
    assert len(events) > 0

    first_ev = events[0]
    assert isinstance(first_ev, EgressEvent)
    assert first_ev.operation_type in ("CSV_EXPORT", "DATABASE_MIRROR", "REPORTING_REPLICATION", "FILE_DOWNLOAD")
    assert first_ev.source_dataset is not None
    assert first_ev.destination_dataset is not None
    assert first_ev.verification_status == "Verified"


def test_09_unsupported_egress_disclaimer():
    """Validates that PrivSight never claims unobserved external network surveillance."""
    assistant = AIAssistant()
    report = assistant.process_query("Has customer data been exported to external networks or the internet?")
    assert "observable" in report.explanation.lower()
    assert ("network" in report.explanation.lower() or "sensor" in report.explanation.lower() or "perimeter" in report.explanation.lower())


# ============================================================================
# Criterion 11: Security & Permission Enforcement
# ============================================================================

def test_10_auth_enforcement_on_lineage_endpoints(client):
    """Validates that unauthenticated requests receive 401 Unauthorized."""
    endpoints = [
        "/api/lineage/dag",
        "/api/lineage/ledger",
        "/api/lineage/egress",
    ]
    for ep in endpoints:
        res = client.get(ep)
        assert res.status_code == 401


def test_11_authenticated_lineage_endpoints(client, auth_headers):
    """Validates that authenticated requests can retrieve DAG, ledger, and egress."""
    # GET DAG
    res_dag = client.get("/api/lineage/dag", cookies=auth_headers)
    assert res_dag.status_code == 200
    dag_json = res_dag.json()
    assert "nodes" in dag_json
    assert "edges" in dag_json

    # GET Ledger
    res_ledger = client.get("/api/lineage/ledger", cookies=auth_headers)
    assert res_ledger.status_code == 200
    assert isinstance(res_ledger.json(), list)

    # POST Verify
    res_verify = client.post("/api/lineage/ledger/verify", cookies=auth_headers)
    assert res_verify.status_code == 200
    assert res_verify.json()["is_valid"] is True

    # GET Egress
    res_egress = client.get("/api/lineage/egress", cookies=auth_headers)
    assert res_egress.status_code == 200
    assert isinstance(res_egress.json(), list)


# ============================================================================
# Criterion 12: TRACERA AI Assistant Integration
# ============================================================================

def test_12_tracera_lineage_queries():
    """Validates TRACERA answers lineage, origin, egress, and ledger verification questions."""
    assistant = AIAssistant()

    # Query 1: Origin
    r1 = assistant.process_query("Where did customer data originate?")
    assert "origin" in r1.explanation.lower() or "provenance" in r1.explanation.lower()
    assert "customers.csv" in r1.explanation or "customer" in r1.explanation.lower()

    # Query 2: Complete Lineage
    r2 = assistant.process_query("Show complete lineage of customer data")
    assert "lineage" in r2.explanation.lower()
    assert "ingestion" in r2.explanation.lower()
    assert "storage" in r2.explanation.lower()

    # Query 3: Evidence Ledger Integrity
    r3 = assistant.process_query("Is the supporting evidence integrity verified?")
    assert "sha-256" in r3.explanation.lower() or "ledger" in r3.explanation.lower()
    assert "genesis" in r3.explanation.lower()
    assert "valid" in r3.explanation.lower()

    # Query 4: Egress Events
    r4 = assistant.process_query("Has this data been exported?")
    assert "egress" in r4.explanation.lower() or "export" in r4.explanation.lower()

    # Query 5: Inferred vs Unverified
    r5 = assistant.process_query("Which parts of this lineage are inferred or unverified?")
    assert "verified" in r5.explanation.lower()
    assert "inferred" in r5.explanation.lower()


# ============================================================================
# Criterion 13: HTML and Page Routing
# ============================================================================

def test_13_lineage_page_serving(client, auth_headers):
    """Validates that /lineage serves the Phase 5.1 HTML page for authenticated users."""
    res = client.get("/lineage", cookies=auth_headers)
    assert res.status_code == 200
    assert "Directional Data Lineage" in res.text
    assert "cyLineageContainer" in res.text
    assert "lineage.js" in res.text


# ============================================================================
# Criterion 14: Safe, Idempotent Database Migrations
# ============================================================================

def test_14_database_migration_safety():
    """Validates that init_lineage_tables is strictly idempotent and does not drop tables."""
    conn = get_db_connection()
    try:
        # Re-run migration multiple times
        init_lineage_tables()
        init_lineage_tables()

        # Check existing user and conversation tables are intact
        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {r[0] for r in cur.fetchall()}

        # Verify core tables persist
        assert "users" in tables
        assert "sessions" in tables
        assert "ai_conversations" in tables
        assert "ai_chat_messages" in tables

        # Verify new tables exist
        assert "evidence_chain_ledger" in tables
        assert "data_egress_events" in tables
    finally:
        conn.close()
