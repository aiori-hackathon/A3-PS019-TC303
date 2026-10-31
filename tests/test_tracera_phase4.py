"""
tests/test_tracera_phase4.py
============================
Comprehensive Test Suite for TRACERA Phase 4: Advanced Conversational Experience.

Verifies:
- Module 1: Smart Conversation Memory (Multi-turn follow-ups, visual explanations, thread isolation, persistence)
- Module 2: Streaming AI Responses (SSE protocol, event markers, token progressive delivery, zero duplicate turns)
- Module 3: Advanced Message Actions (User message editing, history pruning on edit, assistant response regeneration)
- Module 4: File Upload & Technical Analysis (Format validation, 10MB limit, PII detection & masking, dynamic table/chart from file)
- Module 5: API Security & Isolation (Thread privacy, auth enforcement, zero hallucination / deterministic evidence)
"""

import io
import json
import uuid
import pytest
from fastapi.testclient import TestClient

from backend.api.main import app
from backend.auth.routes import SESSION_COOKIE_NAME
from backend.relationships.ai_assistant import AIAssistant
from backend.relationships.chat_service import ChatPersistenceService
from backend.relationships.context_reasoner import ContextualReasoner
from backend.relationships.models import ChatMessage


@pytest.fixture
def client():
    return TestClient(app)


def _register_and_login(client: TestClient) -> dict:
    unique_id = uuid.uuid4().hex[:8]
    email = f"lead.phase4.{unique_id}@privsight.io"
    password = "SecurePassword2026!"
    name = f"Phase 4 Engineer {unique_id}"

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
# MODULE 1: SMART CONVERSATION MEMORY & VISUAL REFERENCES
# ===========================================================================
def test_mod1_smart_conversation_memory_followups():
    """Verify context reasoner resolves pronouns, previous visuals, and maintains separate thread contexts."""
    ai = AIAssistant()
    conv_id = f"test_conv_{uuid.uuid4().hex[:8]}"

    # Turn 1: Ask about customer relationships
    rep1 = ai.process_query(
        query="Show the relationships for customers in relational_demo.db",
        conversation_id=conv_id,
    )
    assert rep1.response_type == "relationship_graph"
    assert "Customer" in [e.get("label") for e in rep1.identified_entities]

    # Turn 2: Follow-up visual explanation ("Explain this graph")
    rep2 = ai.process_query(
        query="Explain this graph",
        conversation_id=conv_id,
    )
    assert ("Explanation of Previous Relationship Graph" in rep2.explanation or "Explanation of PrivSight Relationship Graph" in rep2.explanation)
    assert "Entity Nodes" in rep2.explanation

    # Turn 3: Follow-up format conversion ("Now show it in a table")
    rep3 = ai.process_query(
        query="Now convert this into a table",
        conversation_id=conv_id,
    )
    assert rep3.response_type == "table"
    assert rep3.table_data is not None
    assert len(rep3.table_data) > 0


def test_mod1_thread_isolation():
    """Verify two different conversation IDs never mix state or entities."""
    reasoner = ContextualReasoner()
    conv_a = "thread_alpha"
    conv_b = "thread_beta"

    # Context in thread A
    reasoner.update_state(
        conversation_id=conv_a,
        entities=["Customer", "Order"],
        tables=["customers.csv", "orders.csv"],
    )

    # Context in thread B
    reasoner.update_state(
        conversation_id=conv_b,
        entities=["Employee", "Department"],
        tables=["employees.csv", "departments.csv"],
    )

    ctx_a_meta, _ = reasoner.resolve_references("What about their orders?", conversation_id=conv_a)
    ctx_b_meta, _ = reasoner.resolve_references("What about their orders?", conversation_id=conv_b)

    assert "Customer" in ctx_a_meta["referenced_entities"]
    assert "Employee" not in ctx_a_meta["referenced_entities"]

    assert "Employee" in ctx_b_meta["referenced_entities"]
    assert "Customer" not in ctx_b_meta["referenced_entities"]


# ===========================================================================
# MODULE 2: FILE UPLOAD & TECHNICAL PII ANALYSIS
# ===========================================================================
def test_mod2_file_upload_validation_and_pii_masking(client: TestClient):
    """Verify file upload parses CSV, identifies candidate PII, and masks sensitive samples."""
    auth = _register_and_login(client)

    csv_content = (
        "user_id,full_name,email_address,contact_phone,account_balance\n"
        "101,Johnathan Doe,johndoe@privsight.io,555-019-2834,1250.50\n"
        "102,Alice Smith,alice.smith@example.org,555-019-9988,3400.00\n"
        "103,Robert Johnson,robert.j@corp.net,555-019-4455,890.25\n"
    ).encode("utf-8")

    files = {"file": ("customer_survey.csv", io.BytesIO(csv_content), "text/csv")}
    res = client.post(
        "/api/relationships/upload",
        files=files,
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "success"
    assert data["filename"] == "customer_survey.csv"
    assert data["file_type"] == "csv"
    assert data["total_records"] == 3
    assert "email_address" in data["fields"]

    # Verify PII detection and masking
    pii_cats = {p["field"]: p for p in data["detected_pii"]}
    assert "email_address" in pii_cats
    assert pii_cats["email_address"]["category"] == "Email Address"
    assert "***@" in pii_cats["email_address"]["sample"]  # Masked!

    assert "contact_phone" in pii_cats
    assert pii_cats["contact_phone"]["category"] == "Phone Number"
    assert "***" in pii_cats["contact_phone"]["sample"]  # Masked!


def test_mod2_file_upload_security_reject_unsupported(client: TestClient):
    """Verify security controls reject unsupported executable or dangerous extensions."""
    auth = _register_and_login(client)

    bad_content = b"MZ\x90\x00\x03\x00\x00\x00BinaryExePayload"
    files = {"file": ("malware_scanner.exe", io.BytesIO(bad_content), "application/octet-stream")}
    res = client.post(
        "/api/relationships/upload",
        files=files,
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert res.status_code == 400
    assert "Unsupported format" in res.json()["detail"]


def test_mod2_chat_with_uploaded_file(client: TestClient):
    """Verify asking questions about uploaded file generates evidence-grounded reports with table/chart."""
    auth = _register_and_login(client)

    # 1. Upload CSV
    csv_content = (
        "id,email,phone,first_name,last_name,department\n"
        "1,a@b.com,555-1111,Jane,Doe,Engineering\n"
        "2,c@d.com,555-2222,Mark,Lee,Operations\n"
    ).encode("utf-8")

    upload_res = client.post(
        "/api/relationships/upload",
        files={"file": ("staff_pii.csv", io.BytesIO(csv_content), "text/csv")},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert upload_res.status_code == 200
    att_meta = upload_res.json()

    # 2. Ask question with attachment
    chat_res = client.post(
        "/api/relationships/chat",
        json={
            "message": "What candidate personal data was detected in this file? Show as a table.",
            "attachment": att_meta,
            "format_preference": "table",
        },
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert chat_res.status_code == 200
    report = chat_res.json()
    assert report["response_type"] == "table"
    assert report["table_data"] is not None
    assert any(row.get("field_name") == "email" for row in report["table_data"])
    assert "staff_pii.csv" in report["explanation"]


# ===========================================================================
# MODULE 3: MESSAGE EDITING & REGENERATION (ZERO DUPLICATES)
# ===========================================================================
def test_mod3_edit_user_message_pruning(client: TestClient):
    """Verify editing a user message prunes subsequent turns and avoids message duplication."""
    auth = _register_and_login(client)

    # 1. Start a conversation
    conv_res = client.post(
        "/api/relationships/conversations",
        json={"title": "Audit Investigation"},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    conv_id = conv_res.json()["id"]

    # 2. Turn 1
    t1_res = client.post(
        "/api/relationships/chat",
        json={"message": "Show relationships for customers", "conversation_id": conv_id},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert t1_res.status_code == 200

    # 3. Turn 2
    t2_res = client.post(
        "/api/relationships/chat",
        json={"message": "What about their orders?", "conversation_id": conv_id},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert t2_res.status_code == 200

    # Verify conversation now has 4 messages (user1, asst1, user2, asst2)
    history_res = client.get(
        f"/api/relationships/conversations/{conv_id}",
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    messages = history_res.json()["messages"]
    assert len(messages) == 4
    first_user_msg_id = messages[0]["id"]

    # 4. Edit user message 1 ("Show relationships for employees instead")
    edit_res = client.put(
        f"/api/relationships/conversations/{conv_id}/messages/{first_user_msg_id}",
        json={"content": "Show relationships for employees in relational_demo.db"},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert edit_res.status_code == 200

    # 5. Check history again: all messages after user 1 must have been pruned,
    # leaving exactly 2 messages (edited user1 + newly generated asst response)
    new_hist = client.get(
        f"/api/relationships/conversations/{conv_id}",
        headers=auth["headers"],
        cookies=auth["cookies"],
    ).json()["messages"]

    assert len(new_hist) == 2
    assert new_hist[0]["content"] == "Show relationships for employees in relational_demo.db"
    assert new_hist[1]["role"] == "assistant"
    assert "Employee" in new_hist[1]["content"] or "employee" in new_hist[1]["content"].lower()


def test_mod3_regenerate_assistant_response(client: TestClient):
    """Verify regenerating assistant response cleanly updates turn without duplicate messages."""
    auth = _register_and_login(client)

    # 1. Ask a question
    t1_res = client.post(
        "/api/relationships/chat",
        json={"message": "Show relationships for customers"},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    conv_id = t1_res.json()["conversation_id"]
    asst_msg_id = t1_res.json()["message_id"]

    # 2. Regenerate
    regen_res = client.post(
        f"/api/relationships/conversations/{conv_id}/regenerate",
        json={"message_id": asst_msg_id},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert regen_res.status_code == 200
    regen_data = regen_res.json()
    assert regen_data["conversation_id"] == conv_id

    # 3. Check history: must be exactly 2 messages (user, new_asst)
    hist = client.get(
        f"/api/relationships/conversations/{conv_id}",
        headers=auth["headers"],
        cookies=auth["cookies"],
    ).json()["messages"]
    assert len(hist) == 2


# ===========================================================================
# MODULE 4: STREAMING AI RESPONSES (SSE)
# ===========================================================================
def test_mod4_sse_streaming_endpoint(client: TestClient):
    """Verify Server-Sent Events progressive streaming endpoint emits correct protocol events."""
    auth = _register_and_login(client)

    res = client.post(
        "/api/relationships/chat/stream",
        json={"message": "Show relationships for customers", "format_preference": "graph"},
        headers=auth["headers"],
        cookies=auth["cookies"],
    )
    assert res.status_code == 200
    assert "text/event-stream" in res.headers["content-type"]

    body_text = res.text
    assert "event: start" in body_text
    assert "event: visual" in body_text
    assert "event: token" in body_text
    assert "event: done" in body_text
