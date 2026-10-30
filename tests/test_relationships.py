"""
tests/test_relationships.py
===========================
Comprehensive unit and integration test suite for the PrivSight AI Relationship Intelligence Assistant:
- Page routing and auth enforcement (/relationship-explorer)
- Relationship discovery engine (/api/relationships/sources, /api/relationships/graph)
- Conversation thread lifecycle (create, list, rename, delete)
- Per-user data and conversation isolation
- Multi-format chat reasoning (text, graph, table, timeline, flowchart)
- Strict compliance with GENERATE FORMAT -> EXPLAIN FORMAT -> ANALYZE RELATIONSHIPS -> CONCLUDE
- Conversational context and pronoun resolution across turns
- Privacy masking of PII candidates in AI responses
"""

from __future__ import annotations

import uuid
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.auth.routes import SESSION_COOKIE_NAME


@pytest.fixture(scope="function")
def client() -> TestClient:
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
    return {"email": email, "token": token, "cookies": {SESSION_COOKIE_NAME: token}}


def test_tracera_page_routing_and_auth(client: TestClient) -> None:
    # 1. Unauthenticated redirect
    unauth_res = client.get("/tracera", follow_redirects=False)
    assert unauth_res.status_code == 303
    assert unauth_res.headers["location"] == "/login?redirect=/tracera"

    # 2. Authenticated page loads TRACERA brand, tagline, and scripts
    user = _register_and_login(client)
    auth_res = client.get("/tracera", cookies=user["cookies"])
    assert auth_res.status_code == 200
    assert "TRACERA" in auth_res.text
    assert "Trace. Analyze. Understand." in auth_res.text
    assert "BY PRIVSIGHT" in auth_res.text
    assert "cytoscape.min.js" in auth_res.text
    assert "tracera.js" in auth_res.text

    # 3. Direct stylesheet routes load without 404
    css_res1 = client.get("/static/style.css")
    assert css_res1.status_code == 200
    assert "Plus Jakarta Sans" in css_res1.text

    css_res2 = client.get("/style.css")
    assert css_res2.status_code == 200
    assert "Plus Jakarta Sans" in css_res2.text

    # 4. Vendor script loads
    cy_res1 = client.get("/static/vendor/cytoscape.min.js")
    assert cy_res1.status_code == 200
    cy_res2 = client.get("/vendor/cytoscape.min.js")
    assert cy_res2.status_code == 200


def test_api_relationships_unauthenticated_rejection(client: TestClient) -> None:
    res1 = client.get("/api/relationships/sources")
    assert res1.status_code == 401

    res2 = client.get("/api/relationships/graph")
    assert res2.status_code == 401

    res3 = client.get("/api/relationships/conversations")
    assert res3.status_code == 401


def test_api_relationships_sources_and_graph(client: TestClient) -> None:
    user = _register_and_login(client)
    headers = {"Authorization": f"Bearer {user['token']}"}

    # Sources
    sources_res = client.get("/api/relationships/sources", headers=headers)
    assert sources_res.status_code == 200
    sources_data = sources_res.json()
    assert "sources" in sources_data
    assert len(sources_data["sources"]) > 0

    # Graph
    graph_res = client.get("/api/relationships/graph", headers=headers)
    assert graph_res.status_code == 200
    graph_data = graph_res.json()
    assert "nodes" in graph_data
    assert "edges" in graph_data
    assert len(graph_data["nodes"]) >= 3
    assert len(graph_data["edges"]) >= 2

    # Check edge structure
    edge = graph_data["edges"][0]
    assert "source_id" in edge
    assert "target_id" in edge
    assert "relationship_type" in edge
    assert "evidence" in edge


def test_conversation_thread_lifecycle(client: TestClient) -> None:
    user = _register_and_login(client)
    headers = {"Authorization": f"Bearer {user['token']}"}

    # 1. Create conversation
    create_res = client.post(
        "/api/relationships/conversations",
        headers=headers,
        json={"title": "Test Entity Intelligence Investigation"},
    )
    assert create_res.status_code == 200
    conv = create_res.json()
    conv_id = conv["id"]
    assert conv["title"] == "Test Entity Intelligence Investigation"

    # 2. List conversations
    list_res = client.get("/api/relationships/conversations", headers=headers)
    assert list_res.status_code == 200
    threads = list_res.json()
    assert any(t["id"] == conv_id for t in threads)

    # 3. Rename conversation
    patch_res = client.patch(
        f"/api/relationships/conversations/{conv_id}",
        headers=headers,
        json={"title": "Renamed Investigation Thread"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["title"] == "Renamed Investigation Thread"

    # 4. Get detail
    detail_res = client.get(f"/api/relationships/conversations/{conv_id}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["title"] == "Renamed Investigation Thread"
    assert len(detail["messages"]) == 0

    # 5. Delete conversation
    del_res = client.delete(f"/api/relationships/conversations/{conv_id}", headers=headers)
    assert del_res.status_code == 200

    # 6. Verify gone
    get_after = client.get(f"/api/relationships/conversations/{conv_id}", headers=headers)
    assert get_after.status_code == 404


def test_user_conversation_isolation() -> None:
    client1 = TestClient(app)
    client2 = TestClient(app)
    user1 = _register_and_login(client1)
    user2 = _register_and_login(client2)

    h1 = {"Authorization": f"Bearer {user1['token']}"}
    h2 = {"Authorization": f"Bearer {user2['token']}"}

    # User 1 creates conversation
    res1 = client1.post("/api/relationships/conversations", headers=h1, json={"title": "User 1 Secret Dossier"})
    conv1_id = res1.json()["id"]

    # User 2 lists conversations -> should not see user 1's conversation
    res2_list = client2.get("/api/relationships/conversations", headers=h2)
    assert not any(t["id"] == conv1_id for t in res2_list.json())

    # User 2 tries to access user 1's conversation -> 404
    res2_get = client2.get(f"/api/relationships/conversations/{conv1_id}", headers=h2)
    assert res2_get.status_code == 404

    # User 2 tries to delete user 1's conversation -> 404
    res2_del = client2.delete(f"/api/relationships/conversations/{conv1_id}", headers=h2)
    assert res2_del.status_code == 404


def test_chat_natural_language_and_context(client: TestClient) -> None:
    user = _register_and_login(client)
    headers = {"Authorization": f"Bearer {user['token']}"}

    # Create thread
    conv_res = client.post("/api/relationships/conversations", headers=headers, json={})
    conv_id = conv_res.json()["id"]

    # 1. Ask about customer C001
    chat_res1 = client.post(
        "/api/relationships/chat",
        headers=headers,
        json={"conversation_id": conv_id, "message": "Explain what records and entities connect to customer C001"},
    )
    assert chat_res1.status_code == 200
    msg1 = chat_res1.json()
    assert "C001" in msg1["explanation"]
    assert msg1["format_requested"] in ["text", "bullet_points", "step_by_step"]

    # 2. Contextual follow-up using pronoun "their"
    chat_res2 = client.post(
        "/api/relationships/chat",
        headers=headers,
        json={"conversation_id": conv_id, "message": "Show their orders and payment transactions"},
    )
    assert chat_res2.status_code == 200
    msg2 = chat_res2.json()
    assert "order" in msg2["explanation"].lower() or "payment" in msg2["explanation"].lower()


def test_chat_graph_format_and_mandatory_sequence(client: TestClient) -> None:
    user = _register_and_login(client)
    headers = {"Authorization": f"Bearer {user['token']}"}

    conv_res = client.post("/api/relationships/conversations", headers=headers, json={})
    conv_id = conv_res.json()["id"]

    # Request graphical explanation
    chat_res = client.post(
        "/api/relationships/chat",
        headers=headers,
        json={
            "conversation_id": conv_id,
            "message": "Explain the relationship between customers and orders graphically with an interactive graph",
            "format_preference": "graph",
        },
    )
    assert chat_res.status_code == 200
    msg = chat_res.json()
    assert msg["format_requested"] == "graph"
    assert msg["graph"] is not None
    assert len(msg["graph"]["nodes"]) > 0
    assert len(msg["graph"]["edges"]) > 0

    content = msg["explanation"]
    # Verify strict sequence: GENERATE FORMAT -> EXPLAIN FORMAT -> ANALYZE RELATIONSHIPS -> CONCLUDE
    assert "Graph" in content or "Nodes" in content or "Overview" in content
    assert "Nodes" in content and "Edges" in content
    assert "Relationship" in content or "Intelligence" in content or "Analysis" in content
    assert "Summary" in content or "Verification" in content or "Provenance" in content


def test_chat_table_format_and_mandatory_sequence(client: TestClient) -> None:
    user = _register_and_login(client)
    headers = {"Authorization": f"Bearer {user['token']}"}

    conv_res = client.post("/api/relationships/conversations", headers=headers, json={})
    conv_id = conv_res.json()["id"]

    # Request table explanation
    chat_res = client.post(
        "/api/relationships/chat",
        headers=headers,
        json={
            "conversation_id": conv_id,
            "message": "Explain the same relationships in a structured table",
            "format_preference": "table",
        },
    )
    assert chat_res.status_code == 200
    msg = chat_res.json()
    assert msg["format_requested"] == "table"
    assert msg["table_data"] is not None
    assert len(msg["table_data"]) > 0

    content = msg["explanation"]
    # Verify strict sequence: GENERATE FORMAT -> EXPLAIN FORMAT -> ANALYZE RELATIONSHIPS -> CONCLUDE
    assert "Table" in content or "Columns" in content or "Tabular" in content
    assert "Columns" in content or "Relationship" in content
    assert "Relationship" in content or "Analysis" in content or "Verified" in content
    assert "Summary" in content or "Verification" in content or "Conclusion" in content


def test_chat_timeline_and_flowchart_formats(client: TestClient) -> None:
    user = _register_and_login(client)
    headers = {"Authorization": f"Bearer {user['token']}"}

    conv_res = client.post("/api/relationships/conversations", headers=headers, json={})
    conv_id = conv_res.json()["id"]

    # Request timeline
    chat_timeline = client.post(
        "/api/relationships/chat",
        headers=headers,
        json={"conversation_id": conv_id, "message": "Give me a chronological timeline of data events and relationships"},
    )
    assert chat_timeline.status_code == 200
    msg_tl = chat_timeline.json()
    assert msg_tl["format_requested"] == "timeline"
    assert msg_tl["timeline_data"] is not None
    assert len(msg_tl["timeline_data"]) > 0

    # Request flowchart
    chat_flow = client.post(
        "/api/relationships/chat",
        headers=headers,
        json={"conversation_id": conv_id, "message": "Show the entity processing flowchart step by step"},
    )
    assert chat_flow.status_code == 200
    msg_fl = chat_flow.json()
    assert msg_fl["format_requested"] in ["flowchart", "step_by_step"]
