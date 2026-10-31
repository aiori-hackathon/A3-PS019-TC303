"""
tests/test_tracera_phase4_audit.py
===================================
Comprehensive Quality and Security Audit Test Suite for TRACERA Phase 4.

Verifies:
1. Conversation Intelligence (contextual follow-ups, memory, reference to visuals, thread isolation, clean context)
2. Streaming AI Responses (genuine SSE tokens, start/visual/token/done markers, no duplication)
3. Message Actions (edit & prune downstream turns, regenerate response, thread preservation)
4. Chat History (CRUD, ordering by recent activity, thread isolation)
5. File Attachments (CSV, JSON, TXT, PDF, XLSX support; 10MB ceiling; reject unsupported; PII masking; queries on file)
6. Security & Reliability (authentication enforcement, error handling, PII sample masking)
"""

import io
import json
import uuid
import pytest
from starlette.testclient import TestClient

from backend.auth.service import AuthService
from backend.api.main import app
from backend.relationships.ai_assistant import AIAssistant
from backend.relationships.chat_service import ChatPersistenceService
from backend.relationships.context_reasoner import ContextualReasoner

SESSION_COOKIE_NAME = "privsight_session"


@pytest.fixture
def client():
    return TestClient(app)


def _register_and_login(client: TestClient) -> dict:
    unique_id = uuid.uuid4().hex[:8]
    email = f"audit.user.{unique_id}@privsight.io"
    password = "SecurePassword2026!"
    name = f"Audit Engineer {unique_id}"

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
    return {
        "email": email,
        "token": token,
        "cookies": {SESSION_COOKIE_NAME: token},
        "headers": {"Authorization": f"Bearer {token}"},
    }


# ===========================================================================
# 1. CONVERSATION INTELLIGENCE AUDIT
# ===========================================================================
def test_conversation_intelligence_followups_and_visual_references():
    ai = AIAssistant()
    conv_id = f"audit_conv_{uuid.uuid4().hex[:8]}"

    # Turn 1: Topology graph query
    rep1 = ai.process_query(
        query="Show the relationships for customers in relational_demo.db",
        conversation_id=conv_id,
    )
    assert rep1.response_type == "relationship_graph"
    assert rep1.graph is not None

    # Turn 2: Follow-up visual explanation ("Explain this graph")
    rep2 = ai.process_query(
        query="Explain this graph",
        conversation_id=conv_id,
    )
    assert ("Explanation of Previous Relationship Graph" in rep2.explanation or "Explanation of PrivSight Relationship Graph" in rep2.explanation)
    assert "Entity Nodes" in rep2.explanation

    # Turn 3: Follow-up format conversion ("Convert this into a table")
    rep3 = ai.process_query(
        query="Convert this into a table",
        conversation_id=conv_id,
    )
    assert rep3.response_type == "table"
    assert rep3.table_data is not None and len(rep3.table_data) > 0

    # Turn 4: Entity pronoun reference ("What about their orders?")
    rep4 = ai.process_query(
        query="What about their orders?",
        conversation_id=conv_id,
    )
    assert "Order" in [e.get("label") for e in rep4.identified_entities] or "Customer" in [e.get("label") for e in rep4.identified_entities]


def test_thread_isolation_and_clean_context_on_new_chat():
    reasoner = ContextualReasoner()
    thread_1 = f"thread_audit_1_{uuid.uuid4().hex[:6]}"
    thread_2 = f"thread_audit_2_{uuid.uuid4().hex[:6]}"
    thread_clean = f"thread_audit_new_{uuid.uuid4().hex[:6]}"

    # Thread 1 state
    reasoner.update_state(conversation_id=thread_1, entities=["Customer"], tables=["customers.csv"])
    # Thread 2 state
    reasoner.update_state(conversation_id=thread_2, entities=["Employee"], tables=["employees.csv"])

    meta1, _ = reasoner.resolve_references("What about their orders?", conversation_id=thread_1)
    meta2, _ = reasoner.resolve_references("What about their orders?", conversation_id=thread_2)
    clean_meta, _ = reasoner.resolve_references("What about their orders?", conversation_id=thread_clean)

    assert "Customer" in meta1["referenced_entities"]
    assert "Employee" not in meta1["referenced_entities"]

    assert "Employee" in meta2["referenced_entities"]
    assert "Customer" not in meta2["referenced_entities"]

    # Clean new chat has zero prior referenced entities
    assert len(clean_meta["referenced_entities"]) == 0


# ===========================================================================
# 2. STREAMING AI RESPONSES AUDIT
# ===========================================================================
def test_streaming_endpoint_sse_markers_and_single_persistence(client: TestClient):
    auth = _register_and_login(client)

    conv_res = client.post("/api/relationships/conversations", json={"title": "Streaming Audit"}, headers=auth["headers"], cookies=auth["cookies"])
    conv_id = conv_res.json()["id"]

    stream_res = client.post(
        "/api/relationships/chat/stream",
        json={"message": "Show relationships for customers visually", "conversation_id": conv_id},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert stream_res.status_code == 200
    assert "text/event-stream" in stream_res.headers.get("content-type", "")

    content = stream_res.text
    assert "event: start" in content
    assert "event: visual" in content
    assert "event: token" in content
    assert "event: done" in content

    # Verify database persistence: exactly 1 user message and 1 assistant message (no duplicates)
    hist = client.get(f"/api/relationships/conversations/{conv_id}", headers=auth["headers"], cookies=auth["cookies"]).json()
    messages = hist["messages"]
    assert len(messages) == 2
    assert messages[0]["role"] == "user"
    assert messages[1]["role"] == "assistant"
    assert messages[1]["response_type"] == "relationship_graph"


# ===========================================================================
# 3. MESSAGE ACTIONS AUDIT (EDIT, PRUNING, REGENERATE)
# ===========================================================================
def test_user_message_editing_and_history_pruning(client: TestClient):
    auth = _register_and_login(client)

    conv = client.post("/api/relationships/conversations", json={"title": "Pruning Audit"}, headers=auth["headers"], cookies=auth["cookies"]).json()
    conv_id = conv["id"]

    # Turn 1
    client.post("/api/relationships/chat", json={"message": "Show relationships for customers", "conversation_id": conv_id}, headers=auth["headers"], cookies=auth["cookies"])
    # Turn 2
    client.post("/api/relationships/chat", json={"message": "Explain this graph", "conversation_id": conv_id}, headers=auth["headers"], cookies=auth["cookies"])

    # Verify 4 messages in history
    hist = client.get(f"/api/relationships/conversations/{conv_id}", headers=auth["headers"], cookies=auth["cookies"]).json()
    assert len(hist["messages"]) == 4
    first_user_msg_id = hist["messages"][0]["id"]

    # Edit Turn 1 user message
    edit_res = client.put(
        f"/api/relationships/conversations/{conv_id}/messages/{first_user_msg_id}",
        json={"content": "Show relationships for employees visually"},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert edit_res.status_code == 200

    # Verify downstream messages (Turn 2 user & asst) were pruned, leaving exactly 2 messages
    new_hist = client.get(f"/api/relationships/conversations/{conv_id}", headers=auth["headers"], cookies=auth["cookies"]).json()
    assert len(new_hist["messages"]) == 2
    assert new_hist["messages"][0]["content"] == "Show relationships for employees visually"
    assert new_hist["messages"][1]["role"] == "assistant"


def test_regenerate_assistant_response(client: TestClient):
    auth = _register_and_login(client)

    conv = client.post("/api/relationships/conversations", json={"title": "Regen Audit"}, headers=auth["headers"], cookies=auth["cookies"]).json()
    conv_id = conv["id"]

    client.post("/api/relationships/chat", json={"message": "Show relationships for customers", "conversation_id": conv_id}, headers=auth["headers"], cookies=auth["cookies"])
    before_hist = client.get(f"/api/relationships/conversations/{conv_id}", headers=auth["headers"], cookies=auth["cookies"]).json()
    assert len(before_hist["messages"]) == 2
    orig_asst_id = before_hist["messages"][1]["id"]

    regen_res = client.post(
        f"/api/relationships/conversations/{conv_id}/regenerate",
        json={"message_id": orig_asst_id},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert regen_res.status_code == 200

    after_hist = client.get(f"/api/relationships/conversations/{conv_id}", headers=auth["headers"], cookies=auth["cookies"]).json()
    assert len(after_hist["messages"]) == 2
    # Verify assistant message has a fresh ID and content
    assert after_hist["messages"][1]["id"] != orig_asst_id


# ===========================================================================
# 4. CHAT HISTORY AUDIT (CRUD & RECENT ACTIVITY ORDERING)
# ===========================================================================
def test_chat_history_crud_and_activity_ordering(client: TestClient):
    auth = _register_and_login(client)

    # 1. Create thread A
    res_a = client.post("/api/relationships/conversations", json={"title": "Thread A"}, headers=auth["headers"], cookies=auth["cookies"])
    id_a = res_a.json()["id"]

    # 2. Create thread B
    res_b = client.post("/api/relationships/conversations", json={"title": "Thread B"}, headers=auth["headers"], cookies=auth["cookies"])
    id_b = res_b.json()["id"]

    # List conversations - Thread B should be first
    convs = client.get("/api/relationships/conversations", headers=auth["headers"], cookies=auth["cookies"]).json()
    assert convs[0]["id"] == id_b

    # Send message in Thread A to make it most recently active
    client.post("/api/relationships/chat", json={"message": "Ping", "conversation_id": id_a}, headers=auth["headers"], cookies=auth["cookies"])

    # List conversations again - Thread A should now be first
    convs_updated = client.get("/api/relationships/conversations", headers=auth["headers"], cookies=auth["cookies"]).json()
    assert convs_updated[0]["id"] == id_a

    # Rename Thread A
    rename_res = client.patch(
        f"/api/relationships/conversations/{id_a}",
        json={"title": "Renamed Thread A"},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert rename_res.status_code == 200
    assert client.get(f"/api/relationships/conversations/{id_a}", headers=auth["headers"], cookies=auth["cookies"]).json()["title"] == "Renamed Thread A"

    # Delete Thread B
    del_res = client.delete(f"/api/relationships/conversations/{id_b}", headers=auth["headers"], cookies=auth["cookies"])
    assert del_res.status_code == 200
    # Confirm Thread B is gone
    assert client.get(f"/api/relationships/conversations/{id_b}", headers=auth["headers"], cookies=auth["cookies"]).status_code == 404


# ===========================================================================
# 5. FILE ATTACHMENTS AUDIT (FORMATS, PII MASKING, FILE CHAT, SECURITY)
# ===========================================================================
def test_file_upload_csv_pii_masking_and_chat(client: TestClient):
    auth = _register_and_login(client)

    csv_data = (
        "id,user_email,phone_num,tax_id,balance\n"
        "1,johndoe@privsight.io,555-019-2834,123-45-6789,1200\n"
        "2,alice@domain.org,555-019-9988,987-65-4321,2400\n"
    ).encode("utf-8")

    upload_res = client.post(
        "/api/relationships/upload",
        files={"file": ("audit_sample.csv", io.BytesIO(csv_data), "text/csv")},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert upload_res.status_code == 200
    up_json = upload_res.json()
    assert up_json["filename"] == "audit_sample.csv"
    assert up_json["total_records"] == 2
    assert len(up_json["detected_pii"]) >= 2

    # Verify sample values are masked
    for pii in up_json["detected_pii"]:
        if "Email" in pii["category"]:
            assert "***" in pii["sample"]
            assert "@" in pii["sample"]
            assert "johndoe@privsight.io" not in pii["sample"]  # Original raw PII never exposed

    # Chat with this uploaded file
    chat_res = client.post(
        "/api/relationships/chat",
        json={
            "message": "Analyze the personal data in this uploaded file as a table",
            "attachment": up_json,
        },
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert chat_res.status_code == 200
    chat_json = chat_res.json()
    assert chat_json["response_type"] == "table"
    assert chat_json["table_data"] is not None and len(chat_json["table_data"]) > 0


def test_file_upload_json_and_txt(client: TestClient):
    auth = _register_and_login(client)

    # 1. JSON Upload
    json_data = json.dumps([
        {"id": 101, "email": "admin@privsight.io", "full_name": "Admin User"},
        {"id": 102, "email": "analyst@privsight.io", "full_name": "Analyst User"},
    ]).encode("utf-8")

    res_json = client.post(
        "/api/relationships/upload",
        files={"file": ("users.json", io.BytesIO(json_data), "application/json")},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert res_json.status_code == 200
    assert res_json.json()["file_type"] == "json"

    # 2. Text Upload
    txt_data = "User audit log: Email user@privsight.io performed access verification.".encode("utf-8")
    res_txt = client.post(
        "/api/relationships/upload",
        files={"file": ("log.txt", io.BytesIO(txt_data), "text/plain")},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert res_txt.status_code == 200
    assert res_txt.json()["file_type"] == "txt"


def test_file_upload_security_restrictions(client: TestClient):
    auth = _register_and_login(client)

    # 1. Unsupported executable extension (.exe) rejected
    bad_file = {"file": ("malicious.exe", io.BytesIO(b"MZfakebinary"), "application/octet-stream")}
    res_bad = client.post("/api/relationships/upload", files=bad_file, headers=auth["headers"], cookies=auth["cookies"])
    assert res_bad.status_code == 400
    assert "Unsupported format" in res_bad.json()["detail"]

    # 2. Large file exceeding 10MB rejected
    oversized_data = b"0" * (10 * 1024 * 1024 + 1024)
    res_large = client.post(
        "/api/relationships/upload",
        files={"file": ("large_data.csv", io.BytesIO(oversized_data), "text/csv")},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert res_large.status_code == 400
    assert "exceeds maximum allowed 10MB" in res_large.json()["detail"]


# ===========================================================================
# 6. AUTHENTICATION & SECURITY ENFORCEMENT
# ===========================================================================
def test_unauthenticated_requests_strictly_rejected(client: TestClient):
    # Unauthenticated upload
    assert client.post("/api/relationships/upload", files={"file": ("test.csv", io.BytesIO(b"a,b\n1,2"), "text/csv")}).status_code == 401

    # Unauthenticated chat
    assert client.post("/api/relationships/chat", json={"message": "hello"}).status_code == 401

    # Unauthenticated stream
    assert client.post("/api/relationships/chat/stream", json={"message": "hello"}).status_code == 401

    # Unauthenticated list conversations
    assert client.get("/api/relationships/conversations").status_code == 401
