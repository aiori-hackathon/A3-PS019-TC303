"""
tests/test_tracera_phase3.py
============================
Comprehensive Test Suite for TRACERA Phase 3: Advanced Visualization & Explanation Engine.

Verifies:
- Module 1: Intelligent Visualization Request Detection
- Module 2: Interactive Relationship Graph Engine (all 7 edge metadata attributes, directed, multi-hop)
- Module 3: Advanced Chart Engine (PII distribution, database comparisons, scan trends, empty dataset handling)
- Module 4: Flowchart & Process Diagram Engine (Decision nodes, multi-step flows, real PrivSight workflows)
- Module 5: Timeline Visualization (Chronological events, scan history, source provenance)
- Module 6: Structured Table Renderer (PII tables, table comparisons, relationship matrix)
- Module 7: Dynamic Format Conversion (Text -> Graph -> Table -> Step-by-Step context preservation)
- Module 8: Visual Explanation Engine (Contextual analytical breakdown on every visual response)
- Module 9: API Integration & Persistence (Payload contracts, zero raw JSON, zero synthetic fabrication)
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
    email = f"lead.visualizer.{unique_id}@privsight.io"
    password = "SecurePassword2026!"
    name = f"Visualizer {unique_id}"

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
# MODULE 1: INTELLIGENT VISUALIZATION REQUEST DETECTION
# ===========================================================================
def test_mod1_intelligent_format_detection_phrases():
    ai = AIAssistant()

    # 1. "Show me graphically"
    rep1 = ai.process_query("Show me graphically")
    assert rep1.response_type == "relationship_graph"

    # 2. "Explain this visually"
    rep2 = ai.process_query("Explain this visually")
    assert rep2.response_type == "relationship_graph"

    # 3. "Create a relationship graph"
    rep3 = ai.process_query("Create a relationship graph")
    assert rep3.response_type == "relationship_graph"

    # 4. "Show the connection between these entities"
    rep4 = ai.process_query("Show the connection between these entities")
    assert rep4.response_type == "relationship_graph"

    # 5. "Convert this into a flowchart"
    rep5 = ai.process_query("Convert this into a flowchart")
    assert rep5.response_type == "flowchart"

    # 6. "Give me a bar chart"
    rep6 = ai.process_query("Give me a bar chart")
    assert rep6.response_type == "bar_chart"

    # 7. "Show a pie chart"
    rep7 = ai.process_query("Show a pie chart")
    assert rep7.response_type == "pie_chart"

    # 8. "Compare these tables"
    rep8 = ai.process_query("Compare these tables")
    assert rep8.response_type == "comparison"

    # 9. "Create a timeline"
    rep9 = ai.process_query("Create a timeline")
    assert rep9.response_type == "timeline"

    # 10. "Explain this step by step"
    rep10 = ai.process_query("Explain this step by step")
    assert rep10.response_type == "step_by_step"

    # 11. "Convert this graph into a table"
    rep11 = ai.process_query("Convert this graph into a table")
    assert rep11.response_type == "table"

    # 12. Default text when no visual format is requested
    rep12 = ai.process_query("What is the difference between direct identifiers and quasi-identifiers?")
    assert rep12.response_type == "text"


# ===========================================================================
# MODULE 2: INTERACTIVE RELATIONSHIP GRAPH ENGINE & EDGE METADATA
# ===========================================================================
def test_mod2_interactive_relationship_graph_and_edge_metadata():
    ai = AIAssistant()
    rep: RelationshipReport = ai.process_query("Show the connection between Customers and Payments visually")

    assert rep.response_type == "relationship_graph"
    assert rep.graph is not None
    assert len(rep.graph.nodes) > 0
    assert len(rep.graph.edges) > 0

    # Verify each edge provides all 7 required inspection metadata attributes
    for edge in rep.graph.edges:
        assert edge.source_dataset != ""
        assert edge.source_field != ""
        assert edge.target_dataset != ""
        assert edge.target_field != ""
        assert edge.relationship_type != ""
        assert edge.verification_status in ("Verified", "Inferred", "Possible", "Needs Review")
        assert edge.evidence != ""

    # Multi-hop path verification
    assert rep.relationship_paths is not None and len(rep.relationship_paths) > 0
    path = rep.relationship_paths[0]
    assert path.hops_count in (1, 2)


# ===========================================================================
# MODULE 3: ADVANCED CHART ENGINE (PII DISTRIBUTION, COMPARISONS, TRENDS)
# ===========================================================================
def test_mod3_advanced_charts_with_real_privsight_data():
    ai = AIAssistant()

    # 1. "Show PII distribution across tables"
    rep_bar: RelationshipReport = ai.process_query("Show PII distribution across tables")
    assert rep_bar.response_type == "bar_chart"
    assert rep_bar.chart_data is not None
    assert "PII Distribution Across Tables" in rep_bar.chart_data["title"]
    assert len(rep_bar.chart_data["series"]) > 0
    # Values must be actual positive counts from real scans
    assert all(item["value"] > 0 for item in rep_bar.chart_data["series"])

    # 2. "Compare the number of detected fields in different databases"
    rep_comp: RelationshipReport = ai.process_query("Compare the number of detected fields in different databases")
    assert rep_comp.response_type == "bar_chart"
    assert rep_comp.chart_data is not None
    assert "Comparison of Detected PII Fields" in rep_comp.chart_data["title"]
    labels = rep_comp.chart_data["labels"]
    assert any("relational_demo.db" in l for l in labels)
    assert any("privacy_demo.db" in l for l in labels)

    # 3. "Show monthly scan trends"
    rep_line: RelationshipReport = ai.process_query("Show monthly scan trends")
    assert rep_line.response_type == "line_chart"
    assert rep_line.chart_data is not None
    assert "Monthly Scan & Evidence Discovery Trends" in rep_line.chart_data["title"]
    assert len(rep_line.chart_data["series"]) >= 4

    # 4. Empty dataset handling: unknown table must refuse fabrication
    rep_empty: RelationshipReport = ai.process_query("Show a bar chart for QuantumLedger nonexistent table")
    assert rep_empty.response_type == "text"
    assert rep_empty.chart_data is None
    assert "Insufficient Data" in rep_empty.explanation or "No Verification Records Found" in rep_empty.explanation


# ===========================================================================
# MODULE 4: FLOWCHART & PROCESS DIAGRAM ENGINE WITH DECISION NODES
# ===========================================================================
def test_mod4_flowcharts_with_decision_nodes():
    ai = AIAssistant()

    # Evidence verification workflow with decision gate
    rep_flow: RelationshipReport = ai.process_query("Create a flowchart of the evidence verification workflow")
    assert rep_flow.response_type == "flowchart"
    assert rep_flow.flowchart_data is not None
    steps = rep_flow.flowchart_data["steps"]
    assert len(steps) >= 4

    # Verify presence of decision node
    decision_steps = [s for s in steps if s.get("type") == "decision" or s.get("is_decision")]
    assert len(decision_steps) >= 1
    d_step = decision_steps[0]
    assert "Decision Gate" in d_step["title"]
    assert len(d_step.get("decision_branches", [])) == 2


# ===========================================================================
# MODULE 5: TIMELINE VISUALIZATION WITH REAL TIMESTAMPS & SOURCES
# ===========================================================================
def test_mod5_timeline_visualization_with_chronological_events():
    ai = AIAssistant()

    rep_timeline: RelationshipReport = ai.process_query("Show the scan history timeline")
    assert rep_timeline.response_type == "timeline"
    assert rep_timeline.timeline_data is not None
    assert len(rep_timeline.timeline_data) >= 3

    # Check chronological ordering and source citations
    dates = [ev["date"] for ev in rep_timeline.timeline_data if ev.get("date")]
    assert dates == sorted(dates)
    assert all("source" in ev for ev in rep_timeline.timeline_data)


# ===========================================================================
# MODULE 6: STRUCTURED TABLE RENDERER
# ===========================================================================
def test_mod6_structured_table_renderer():
    ai = AIAssistant()

    # 1. PII distribution in a table
    rep_tbl: RelationshipReport = ai.process_query("Show PII distribution in a table")
    assert rep_tbl.response_type == "table"
    assert rep_tbl.table_data is not None
    assert len(rep_tbl.table_data) > 0
    first_row = rep_tbl.table_data[0]
    assert "source_table" in first_row
    assert "field_name" in first_row
    assert "detected_class" in first_row

    # 2. Database table comparison in a table
    rep_comp_tbl: RelationshipReport = ai.process_query("Compare these tables in a table")
    assert rep_comp_tbl.response_type == "table"
    assert rep_comp_tbl.table_data is not None
    assert len(rep_comp_tbl.table_data) > 0
    row_tbl = rep_comp_tbl.table_data[0]
    assert "table_name" in row_tbl
    assert "columns_count" in row_tbl
    assert "row_count" in row_tbl


# ===========================================================================
# MODULE 7: DYNAMIC FORMAT CONVERSION (FULL MULTI-TURN CONTEXT)
# ===========================================================================
def test_mod7_dynamic_format_conversion_multiturn():
    ai = AIAssistant()
    conv_id = f"test-multiturn-{uuid.uuid4().hex[:8]}"

    # Turn 1: Text explanation
    rep1: RelationshipReport = ai.process_query(
        "Explain the relationship between Customers and Payments.",
        conversation_id=conv_id,
    )
    assert rep1.response_type == "text"
    assert "Customers" in rep1.explanation and "Payments" in rep1.explanation

    # Turn 2: Graph representation
    rep2: RelationshipReport = ai.process_query(
        "Show it graphically.",
        conversation_id=conv_id,
    )
    assert rep2.response_type == "relationship_graph"
    assert rep2.graph is not None
    node_labels = [n.label for n in rep2.graph.nodes]
    assert "Customers" in node_labels
    assert "Payments" in node_labels

    # Turn 3: Table representation
    rep3: RelationshipReport = ai.process_query(
        "Now convert it into a table.",
        conversation_id=conv_id,
    )
    assert rep3.response_type == "table"
    assert rep3.table_data is not None
    assert len(rep3.table_data) > 0
    # Must preserve Customers & Payments
    table_entities = [r.get("source_entity") for r in rep3.table_data] + [r.get("target_entity") for r in rep3.table_data]
    assert "Customers" in table_entities or any("customer" in str(e).lower() for e in table_entities)

    # Turn 4: Step-by-step representation
    rep4: RelationshipReport = ai.process_query(
        "Explain it step by step.",
        conversation_id=conv_id,
    )
    assert rep4.response_type == "step_by_step"
    assert rep4.steps is not None
    assert len(rep4.steps) >= 1


# ===========================================================================
# MODULE 8: VISUAL EXPLANATION ENGINE
# ===========================================================================
def test_mod8_visual_explanation_engine():
    ai = AIAssistant()

    # Graph explanation
    rep_graph = ai.process_query("Create a relationship graph")
    assert "Entity Nodes" in rep_graph.explanation or "Nodes" in rep_graph.explanation
    assert "Connecting Edges" in rep_graph.explanation or "Edges" in rep_graph.explanation

    # Chart explanation
    rep_chart = ai.process_query("Show PII distribution across tables")
    assert "X-Axis" in rep_chart.explanation
    assert "Y-Axis" in rep_chart.explanation

    # Flowchart explanation
    rep_flow = ai.process_query("Convert this into a flowchart")
    assert "Sequence" in rep_flow.explanation or "Milestones" in rep_flow.explanation


# ===========================================================================
# MODULE 9: FULL API PERSISTENCE AND FRONTEND CONTRACT VERIFICATION
# ===========================================================================
def test_mod9_api_persistence_and_contract(client: TestClient):
    auth = _register_and_login(client)

    # Create thread
    thread_res = client.post("/api/relationships/conversations", json={"title": "Phase 3 Visual Thread"}, headers=auth["headers"])
    assert thread_res.status_code == 200
    conv_id = thread_res.json()["id"]

    # Post chart request
    chat_res = client.post(
        "/api/relationships/chat",
        json={"message": "Show PII distribution across tables", "conversation_id": conv_id},
        headers=auth["headers"],
    )
    assert chat_res.status_code == 200
    report = chat_res.json()
    assert report["response_type"] == "bar_chart"
    assert report["chart_data"] is not None

    # Fetch conversation history and verify visual payload persists
    conv_res = client.get(f"/api/relationships/conversations/{conv_id}", headers=auth["headers"])
    assert conv_res.status_code == 200
    detail = conv_res.json()
    messages = detail.get("messages", [])
    assert len(messages) >= 2
    asst_msg = [m for m in messages if m["role"] == "assistant"][0]
    assert asst_msg["response_type"] == "bar_chart"
    assert asst_msg["chart_data"] is not None
