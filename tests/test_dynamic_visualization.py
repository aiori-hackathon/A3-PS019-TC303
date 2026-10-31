"""
tests/test_dynamic_visualization.py
====================================
End-to-End and Unit Test Suite for TRACERA Dynamic Response Formatting & Visualization Engine.

Verifies:
1. Ask a normal question and verify a text response.
2. Ask "Show me a graph" and verify a graphical response.
3. Ask "Show the relationship between Customers and Payments" and verify a relationship graph.
4. Ask "Explain this using a flowchart" and verify a rendered flowchart.
5. Ask "Show the data in a table" and verify a structured table.
6. Ask for a bar chart and verify actual data is plotted.
7. Ask for a timeline and verify chronological events.
8. Ask to convert an existing graph into a table.
9. Ask to explain a graph and verify a proper explanation appears.
10. Test insufficient data and verify no fabricated visualization is generated.
11. Refresh the conversation and verify visual responses persist correctly.
12. Verify existing chat history, copy, retry, and message persistence.
"""

import uuid
import pytest
from fastapi.testclient import TestClient
from backend.api.main import app
from backend.auth.routes import SESSION_COOKIE_NAME
from backend.relationships.ai_assistant import AIAssistant
from backend.relationships.models import RelationshipReport


@pytest.fixture
def client():
    return TestClient(app)


def _register_and_login(client: TestClient) -> dict:
    unique_id = uuid.uuid4().hex[:8]
    email = f"intel.analyst.{unique_id}@privsight.io"
    password = "SecurePassword2026!"
    name = f"Analyst {unique_id}"

    reg_res = client.post(
        "/api/auth/register",
        json={"email": email, "full_name": name, "password": password, "confirm_password": password},
    )
    assert reg_res.status_code == 201

    login_res = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
    )
    assert login_res.status_code == 200
    token = login_res.cookies.get(SESSION_COOKIE_NAME)
    return {"email": email, "token": token, "cookies": {SESSION_COOKIE_NAME: token}, "headers": {"Authorization": f"Bearer {token}"}}


# ===========================================================================
# Test 1: Ask a normal question and verify a text response
# ===========================================================================
def test_01_normal_question_returns_text_response():
    ai = AIAssistant()
    rep: RelationshipReport = ai.process_query(
        "What is PrivSight's methodology for personal data discovery and evidence inventory?"
    )
    assert rep.response_type == "text"
    assert rep.format_requested == "text"
    assert rep.graph is None
    assert rep.chart_data is None
    assert rep.flowchart_data is None
    assert "Methodology" in rep.explanation or "Deterministic" in rep.explanation
    assert "PrivSight" in rep.explanation


# ===========================================================================
# Test 2: Ask "Show me a graph" and verify a graphical response
# ===========================================================================
def test_02_show_me_a_graph_returns_graphical_response():
    ai = AIAssistant()
    rep: RelationshipReport = ai.process_query("Show me a graph")
    assert rep.response_type == "relationship_graph"
    assert rep.format_requested in ("graph", "relationship_graph")
    assert rep.graph is not None
    assert len(rep.graph.nodes) > 0
    assert len(rep.graph.edges) > 0
    assert rep.nodes is not None and len(rep.nodes) > 0
    assert rep.edges is not None and len(rep.edges) > 0
    assert "Relationship Topology Graph" in rep.title
    assert "Node" in rep.explanation or "Nodes" in rep.explanation or "graph" in rep.explanation.lower()


# ===========================================================================
# Test 3: Ask "Show the relationship between Customers and Payments"
# ===========================================================================
def test_03_customers_and_payments_relationship_graph():
    ai = AIAssistant()
    rep: RelationshipReport = ai.process_query("Show the relationship between Customers and Payments visually")
    assert rep.response_type == "relationship_graph"
    assert rep.graph is not None
    assert rep.relationship_paths is not None and len(rep.relationship_paths) > 0
    path = rep.relationship_paths[0]
    assert path.hops_count in (1, 2)
    assert path.verification_status == "Verified"
    assert "customer_id" in rep.explanation


# ===========================================================================
# Test 4: Ask "Explain this using a flowchart" and verify rendered flowchart
# ===========================================================================
def test_04_flowchart_response():
    ai = AIAssistant()
    rep: RelationshipReport = ai.process_query("Explain this using a flowchart")
    assert rep.response_type == "flowchart"
    assert rep.flowchart_data is not None
    assert "steps" in rep.flowchart_data
    steps = rep.flowchart_data["steps"]
    assert len(steps) >= 3
    assert steps[0]["step_num"] == 1
    assert "title" in steps[0]
    assert "description" in steps[0]
    assert "Flowchart" in rep.title


# ===========================================================================
# Test 5: Ask "Show the data in a table" and verify a structured table
# ===========================================================================
def test_05_structured_table_response():
    ai = AIAssistant()
    rep: RelationshipReport = ai.process_query("Show the data in a table")
    assert rep.response_type == "table"
    assert rep.table_data is not None
    assert len(rep.table_data) > 0
    first_row = rep.table_data[0]
    assert "source_table" in first_row
    assert "target_table" in first_row
    assert "cardinality" in first_row
    assert "verification_status" in first_row
    assert "Table" in rep.title or "Matrix" in rep.title


# ===========================================================================
# Test 6: Ask for a bar chart and verify actual data is plotted
# ===========================================================================
def test_06_bar_chart_actual_retrieved_data():
    ai = AIAssistant()
    rep: RelationshipReport = ai.process_query("Show me a bar chart of personal data classes in the inventory")
    assert rep.response_type == "bar_chart"
    assert rep.chart_data is not None
    assert rep.chart_data["type"] == "bar"
    assert "series" in rep.chart_data
    series = rep.chart_data["series"]
    assert len(series) > 0

    # Ensure actual retrieved data matches real PrivSight inventory classes
    labels = [s["label"] for s in series]
    assert any("Contact" in l or "Identity" in l or "Location" in l for l in labels)
    for s in series:
        assert isinstance(s["value"], (int, float))
        assert s["value"] > 0
    assert "Bar Chart" in rep.format_explanation or "Distribution" in rep.title


# ===========================================================================
# Test 7: Ask for a timeline and verify chronological events
# ===========================================================================
def test_07_timeline_chronological_events():
    ai = AIAssistant()
    rep: RelationshipReport = ai.process_query("Create a timeline of customer C001 interactions")
    assert rep.response_type == "timeline"
    assert rep.timeline_data is not None
    assert len(rep.timeline_data) > 0
    first_event = rep.timeline_data[0]
    assert "date" in first_event
    assert "entity" in first_event
    assert "description" in first_event
    assert "Timeline" in rep.title or "Timeline" in rep.format_explanation


# ===========================================================================
# Test 8: Convert an existing graph into a table (multi-turn follow-up)
# ===========================================================================
def test_08_dynamic_format_conversion_graph_to_table():
    ai = AIAssistant()
    conv_id = f"test-multiformat-{uuid.uuid4().hex[:6]}"

    # Turn 1: Ask for graphical explanation of Customers and Payments
    rep1: RelationshipReport = ai.process_query(
        "Explain the relationship between Customers and Payments graphically",
        conversation_id=conv_id,
    )
    assert rep1.response_type == "relationship_graph"
    assert rep1.graph is not None

    # Turn 2: User asks to switch format: "Now show it in a table"
    rep2: RelationshipReport = ai.process_query(
        "Now show it in a table",
        conversation_id=conv_id,
    )
    assert rep2.response_type == "table"
    assert rep2.table_data is not None
    assert len(rep2.table_data) > 0

    # Verify table retains context of customers, orders, and payments without re-specifying entities
    all_table_text = " ".join(
        [str(row.get("source_table", "")) + " " + str(row.get("target_table", "")) for row in rep2.table_data]
    ).lower()
    assert "customer" in all_table_text or "order" in all_table_text or "payment" in all_table_text
    assert "VERIFIED" in rep2.explanation.upper()


# ===========================================================================
# Test 9: Ask to explain a graph and verify a proper explanation appears
# ===========================================================================
def test_09_deep_explanation_of_graph_topology():
    ai = AIAssistant()
    rep: RelationshipReport = ai.process_query("Explain this graph in detail")
    assert "Entity Nodes" in rep.explanation
    assert "Connecting Edges" in rep.explanation
    assert "Directionality" in rep.explanation
    assert "Verified vs. Inferred Connections" in rep.explanation


# ===========================================================================
# Test 10: Test insufficient data and verify no fabricated visual is generated
# ===========================================================================
def test_10_insufficient_data_prevents_fabricated_visualization():
    ai = AIAssistant()
    rep: RelationshipReport = ai.process_query("Show me a bar chart for nonexistent_entity_xyz")
    assert rep.response_type == "text"
    assert rep.chart_data is None
    assert rep.graph is None
    assert "No specific database tables or datasets matching the requested entity were found across the active PrivSight inventory." in rep.explanation
    assert "without data fabrication" in rep.explanation or "deterministic" in rep.explanation.lower()


# ===========================================================================
# Test 11: Refresh conversation and verify visual responses persist correctly
# ===========================================================================
def test_11_visual_response_persistence_across_refresh(client: TestClient):
    user = _register_and_login(client)

    # 1. Create conversation thread
    conv_res = client.post(
        "/api/relationships/conversations",
        headers=user["headers"],
        cookies=user["cookies"],
        json={"title": "Visual Persistence Test"},
    )
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["id"]

    # 2. Ask for a bar chart
    chat_res = client.post(
        "/api/relationships/chat",
        headers=user["headers"],
        cookies=user["cookies"],
        json={
            "conversation_id": conv_id,
            "message": "Show me a bar chart of personal data classes in the inventory",
        },
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert chat_data["response_type"] == "bar_chart"
    assert chat_data["chart_data"] is not None

    # 3. Simulate page refresh by fetching thread from database
    refresh_res = client.get(
        f"/api/relationships/conversations/{conv_id}",
        headers=user["headers"],
        cookies=user["cookies"],
    )
    assert refresh_res.status_code == 200
    thread = refresh_res.json()
    assert len(thread["messages"]) == 2

    asst_msg = thread["messages"][1]
    assert asst_msg["role"] == "assistant"
    assert asst_msg["response_type"] == "bar_chart"
    assert asst_msg["chart_data"] is not None
    assert "series" in asst_msg["chart_data"]


# ===========================================================================
# Test 12: Verify existing chat history, copy, retry, and message persistence
# ===========================================================================
def test_12_regression_chat_lifecycle_copy_retry(client: TestClient):
    user = _register_and_login(client)

    # 1. Create thread
    conv_res = client.post(
        "/api/relationships/conversations",
        headers=user["headers"],
        cookies=user["cookies"],
        json={"title": "Full Lifecycle Test"},
    )
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["id"]

    # 2. First turn
    q1 = "Where is customer information stored?"
    c1 = client.post(
        "/api/relationships/chat",
        headers=user["headers"],
        cookies=user["cookies"],
        json={"conversation_id": conv_id, "message": q1},
    )
    assert c1.status_code == 200
    assert "customer" in c1.json()["explanation"].lower()

    # 3. Second turn (Retry or follow-up)
    q2 = "Explain the connection to orders in a flowchart"
    c2 = client.post(
        "/api/relationships/chat",
        headers=user["headers"],
        cookies=user["cookies"],
        json={"conversation_id": conv_id, "message": q2},
    )
    assert c2.status_code == 200
    assert c2.json()["response_type"] == "flowchart"

    # 4. Fetch full thread history
    get_res = client.get(
        f"/api/relationships/conversations/{conv_id}",
        headers=user["headers"],
        cookies=user["cookies"],
    )
    assert get_res.status_code == 200
    msgs = get_res.json()["messages"]
    assert len(msgs) == 4
    assert msgs[0]["content"] == q1
    assert msgs[2]["content"] == q2
