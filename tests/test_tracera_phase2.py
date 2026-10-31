"""
tests/test_tracera_phase2.py
============================
Comprehensive test suite for PrivSight TRACERA Phase 2:
Intelligent AI Brain & Real Data Integration.

Tests all 15 Phase 2 requirements using ACTUAL PrivSight datasets:
1. Retrieve actual scanned tables
2. Retrieve actual column metadata
3. Identify entities
4. Identify primary-key and foreign-key relationships
5. Detect exact value matches
6. Find direct relationships
7. Find indirect relationships
8. Analyze multi-hop relationship paths (Customers -> Orders -> Payments)
9. Answer contextual follow-up questions
10. Provide evidence references
11. Distinguish verified and inferred relationships
12. Handle missing evidence
13. Respect PII masking
14. Prevent unauthorized data access
15. Handle empty or unavailable datasets
"""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.auth.routes import SESSION_COOKIE_NAME
from backend.relationships.ai_assistant import AIAssistant
from backend.relationships.engine import RelationshipEngine, mask_personal_value
from backend.relationships.entity_engine import EntityIdentificationEngine
from backend.relationships.privsight_data import PrivSightDataManager, get_privsight_data_manager


@pytest.fixture(scope="function")
def client() -> TestClient:
    return TestClient(app)


def _login(client: TestClient) -> dict:
    unique_id = uuid.uuid4().hex[:8]
    email = f"phase2.analyst.{unique_id}@privsight.io"
    password = "SecurePassword2026!"
    name = f"Phase 2 Analyst {unique_id}"

    client.post(
        "/api/auth/register",
        json={"email": email, "full_name": name, "password": password, "confirm_password": password},
    )
    login_res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    token = login_res.cookies.get(SESSION_COOKIE_NAME)
    return {"email": email, "token": token, "cookies": {SESSION_COOKIE_NAME: token}}


# ---------------------------------------------------------------------------
# Test 1 & 2: Retrieve actual scanned tables and column metadata
# ---------------------------------------------------------------------------
def test_01_retrieve_actual_scanned_tables_and_columns():
    dm = get_privsight_data_manager()
    dm.refresh()
    tables = dm.get_all_tables()
    table_keys = [t.key for t in tables]

    # Must contain actual real tables
    assert "customers.csv" in table_keys
    assert "orders.csv" in table_keys
    assert "payments.csv" in table_keys
    assert "employees.csv" in table_keys
    assert "departments.csv" in table_keys
    assert any("relational_demo.db" in k for k in table_keys)
    assert any("privacy_demo.db" in k for k in table_keys)

    # Check actual columns
    cust_table = dm.get_table_info("customers.csv")
    assert cust_table is not None
    assert "customer_id" in cust_table.columns
    assert "email" in cust_table.columns
    assert "phone" in cust_table.columns
    assert cust_table.row_count > 0


# ---------------------------------------------------------------------------
# Test 3: Identify entities (Customer, Employee, Order, Payment, Department)
# ---------------------------------------------------------------------------
def test_03_identify_entities():
    ee = EntityIdentificationEngine()

    # Customer
    ents = ee.identify_entities_in_query("Where is customer information stored?")
    assert len(ents) >= 1
    assert ents[0].label == "Customer"
    assert ents[0].primary_id == "customer_id"
    assert len(ents[0].matched_tables) >= 2

    # Employee
    ents_emp = ee.identify_entities_in_query("Which database tables contain employee records?")
    assert len(ents_emp) >= 1
    assert ents_emp[0].label == "Employee"
    assert ents_emp[0].primary_id == "employee_id"

    # Explanation test
    explanation = ee.explain_entity_location("customer")
    assert "customers.csv" in explanation
    assert "customer_id" in explanation
    assert "Personal Data Candidates" in explanation


# ---------------------------------------------------------------------------
# Test 4 & 5: Identify PK / FK relationships and exact value matches
# ---------------------------------------------------------------------------
def test_04_05_primary_foreign_keys_and_exact_value_matches():
    engine = RelationshipEngine()
    edges = engine.discover_all_relationships()
    assert len(edges) > 0

    # Explicit SQL foreign keys from relational_demo.db
    sql_fk_edges = [e for e in edges if "relational_demo.db" in e.source_dataset and e.confidence_score == 1.0]
    assert len(sql_fk_edges) > 0

    # Exact value match joins between CSVs (e.g. customers.csv <-> orders.csv on customer_id)
    cust_order_edges = [
        e for e in edges
        if ("customers" in e.source_dataset.lower() and "orders" in e.target_dataset.lower())
        or ("orders" in e.source_dataset.lower() and "customers" in e.target_dataset.lower())
    ]
    assert len(cust_order_edges) > 0
    e = cust_order_edges[0]
    assert e.source_field == "customer_id" or e.target_field == "customer_id"
    assert e.verification_status == "Verified"
    assert e.match_count > 0


# ---------------------------------------------------------------------------
# Test 6 & 7 & 8: Direct & Indirect Multi-Hop Relationship Paths
# ---------------------------------------------------------------------------
def test_06_07_08_direct_and_multihop_paths():
    engine = RelationshipEngine()

    # 1. Direct relationship: Employees -> Departments (1 hop)
    status_dir, path_dir = engine.find_multi_hop_path("employee", "department")
    assert status_dir == "Verified"
    assert path_dir is not None
    assert path_dir.hops_count == 1
    assert "Employees" in path_dir.path_summary
    assert "Departments" in path_dir.path_summary

    # 2. Multi-hop indirect path: Customers -> Orders -> Payments
    all_cust_pay_paths = engine.find_all_paths("customer", "payment")
    assert len(all_cust_pay_paths) > 0

    # Confirm indirect path through Orders exists
    indirect_paths = [p for p in all_cust_pay_paths if p.hops_count >= 2 and "Orders" in p.path_summary]
    assert len(indirect_paths) > 0
    p = indirect_paths[0]
    assert p.hops_count == 2
    assert p.verification_status == "Verified"
    assert "Orders" in p.explanation
    assert p.hops[0].source_field == "customer_id" or p.hops[0].target_field == "customer_id"
    assert p.hops[1].source_field == "order_id" or p.hops[1].target_field == "order_id"


# ---------------------------------------------------------------------------
# Test 9: Contextual follow-up reasoning
# Turn 1: "Which tables contain customer information?"
# Turn 2: "Which of these tables contain email addresses?"
# Turn 3: "How are they connected to payments?"
# ---------------------------------------------------------------------------
def test_09_contextual_multi_turn_reasoning():
    ai = AIAssistant()
    conv_id = f"test-ctx-{uuid.uuid4().hex[:6]}"

    # Turn 1: Where is customer info stored?
    rep1 = ai.process_query(
        query="Which tables contain customer information?",
        conversation_id=conv_id,
    )
    assert "customers.csv" in rep1.explanation.lower() or "customer" in rep1.explanation.lower()

    # Turn 2: "Which of these tables contain email addresses?"
    rep2 = ai.process_query(
        query="Which of these tables contain email addresses?",
        conversation_id=conv_id,
    )
    assert "email" in rep2.explanation.lower()
    assert "customers.csv" in rep2.explanation or "privacy_demo.db" in rep2.explanation

    # Turn 3: "How are they connected to payments?"
    rep3 = ai.process_query(
        query="How are they connected to payments?",
        conversation_id=conv_id,
    )
    assert "payments" in rep3.explanation.lower()
    assert ("orders" in rep3.explanation.lower() or "customer_id" in rep3.explanation.lower())
    assert "VERIFIED" in rep3.explanation


# ---------------------------------------------------------------------------
# Test 10: Provide evidence references
# ---------------------------------------------------------------------------
def test_10_provide_evidence_references():
    ai = AIAssistant()
    rep = ai.process_query("How are customers connected to orders?")
    assert rep.evidence_items is not None or "Evidence" in rep.explanation
    assert "Technical Evidence" in rep.explanation or "Evidence & Provenance" in rep.explanation or "Evidence:" in rep.explanation
    assert "customer_id" in rep.explanation
    assert "Status" in rep.explanation or "VERIFIED" in rep.explanation


# ---------------------------------------------------------------------------
# Test 11 & 12: Distinguish verified vs inferred vs unverified vs no match
# ---------------------------------------------------------------------------
def test_11_12_verified_vs_inferred_and_no_match():
    engine = RelationshipEngine()

    # Verified relationship
    status_ver, path_ver = engine.find_multi_hop_path("customers", "orders")
    assert status_ver == "Verified"
    assert path_ver is not None

    # No match relationship (Unrelated entities with 0 joinable keys)
    status_none, path_none = engine.find_multi_hop_path("departments", "payments")
    assert status_none == "No Match"
    assert path_none is None

    # AI query for unrelated entities
    ai = AIAssistant()
    rep = ai.process_query("How are departments connected to payments?")
    assert "NO MATCH" in rep.explanation or "No verified" in rep.explanation or "no relationship" in rep.explanation.lower()
    assert "never fabricate" in rep.explanation.lower() or "0 overlapping" in rep.explanation.lower()


# ---------------------------------------------------------------------------
# Test 13: Respect PII Masking
# ---------------------------------------------------------------------------
def test_13_respect_pii_masking():
    # Direct function test
    masked_email = mask_personal_value("email", "john.doe@example.com")
    assert masked_email != "john.doe@example.com"
    assert "***" in masked_email
    assert "@example.com" in masked_email

    masked_phone = mask_personal_value("phone", "+1-555-019-2831")
    assert "***" in masked_phone

    masked_card = mask_personal_value("card_last4", "4111222233334444")
    assert masked_card.startswith("****")

    # AI query record search masking test
    ai = AIAssistant()
    rep = ai.process_query("Show details for customer C001")
    assert "C001" in rep.explanation
    # Ensure raw unmasked email is not exposed if displayed
    assert "eleanor.vance@hillhouse.example" not in rep.explanation or "***" in rep.explanation


# ---------------------------------------------------------------------------
# Test 14: Prevent unauthorized data access
# ---------------------------------------------------------------------------
def test_14_prevent_unauthorized_data_access(client: TestClient):
    unauth_chat = client.post("/api/relationships/chat", json={"message": "Show customer data"})
    assert unauth_chat.status_code == 401


# ---------------------------------------------------------------------------
# Test 15: Handle empty or unavailable datasets gracefully
# ---------------------------------------------------------------------------
def test_15_handle_empty_or_unavailable_datasets():
    ai = AIAssistant()
    rep = ai.process_query("Where is nonexistent_entity_xyz stored?")
    assert "No specific database tables" in rep.explanation or "No matching" in rep.explanation


# ---------------------------------------------------------------------------
# Test 16: Phase 1 Regression (Chat API End-to-End)
# ---------------------------------------------------------------------------
def test_16_phase1_regression_chat_api(client: TestClient):
    user = _login(client)

    # Create thread
    conv_res = client.post("/api/relationships/conversations", json={"title": "Phase 2 Regression Test"}, cookies=user["cookies"])
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["id"]

    # Send Chat Query
    chat_res = client.post(
        "/api/relationships/chat",
        json={"message": "Where is customer information stored?", "conversation_id": conv_id},
        cookies=user["cookies"],
    )
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert "customers" in data["explanation"].lower()
    assert data["conversation_id"] == conv_id

    # Retrieve history
    hist_res = client.get(f"/api/relationships/conversations/{conv_id}", cookies=user["cookies"])
    assert hist_res.status_code == 200
    hist = hist_res.json()
    assert len(hist["messages"]) == 2
    assert hist["messages"][0]["role"] == "user"
    assert hist["messages"][1]["role"] == "assistant"
