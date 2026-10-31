"""
backend/relationships/routes.py
================================
FastAPI REST routes for the AI Relationship Intelligence Assistant:
- POST   /api/relationships/chat              Send query, get context-aware response & format
- GET    /api/relationships/conversations     List user's saved conversations
- POST   /api/relationships/conversations     Create new conversation
- GET    /api/relationships/conversations/{id} Retrieve message history
- PATCH  /api/relationships/conversations/{id} Rename conversation
- DELETE /api/relationships/conversations/{id} Delete conversation
- GET    /api/relationships/graph             Direct graph data access
- GET    /api/relationships/sources           Available sources for relationship explorer
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from backend.auth.models import UserResponse
from backend.auth.routes import get_authenticated_user
from backend.parsers.base import ParsedDocument
from backend.parsers.registry import ParserRegistry
from backend.relationships.ai_assistant import AIAssistant
from backend.relationships.chat_service import ChatPersistenceService
from backend.relationships.engine import RelationshipEngine
from backend.relationships.models import (
    ChatMessage,
    ChatQueryRequest,
    ConversationDetail,
    ConversationSummary,
    ConversationUploadResponse,
    CreateConversationRequest,
    EditMessageRequest,
    RegenerateRequest,
    RelationshipGraph,
    RelationshipReport,
    RenameConversationRequest,
)

logger = logging.getLogger("privsight.relationships.routes")

relationships_router = APIRouter(prefix="/api/relationships", tags=["Relationship Intelligence"])
engine = RelationshipEngine()
ai_assistant = AIAssistant(engine)
chat_service = ChatPersistenceService()
parser_registry = ParserRegistry()
ACTIVE_ATTACHMENTS: Dict[str, Dict[str, Any]] = {}


def _inspect_and_mask_pii(parsed_doc: ParsedDocument) -> List[Dict[str, Any]]:
    """Heuristic personal data classification and sample masking for file uploads."""
    pii_results: List[Dict[str, Any]] = []
    for f in parsed_doc.fields:
        f_name_lower = f.field_name.lower()
        cat = None
        conf = 0.0

        if any(k in f_name_lower for k in ["email", "mail"]):
            cat = "Email Address"
            conf = 0.99
        elif any(k in f_name_lower for k in ["phone", "mobile", "cell", "tel"]):
            cat = "Phone Number"
            conf = 0.95
        elif any(k in f_name_lower for k in ["name", "firstname", "lastname", "fullname", "surname"]):
            cat = "Person Name"
            conf = 0.92
        elif any(k in f_name_lower for k in ["ssn", "social_security", "national_id"]):
            cat = "Government ID / SSN"
            conf = 0.99
        elif any(k in f_name_lower for k in ["address", "street", "city", "postal", "zipcode"]):
            cat = "Physical Address"
            conf = 0.90
        elif any(k in f_name_lower for k in ["credit_card", "card_number", "pan", "iban", "account_number"]):
            cat = "Financial Account"
            conf = 0.98
        elif any(k in f_name_lower for k in ["ip_address", "ip", "mac_address"]):
            cat = "Network Identifier"
            conf = 0.92

        if cat:
            raw_sample = str(f.sample_preview or (f.values[0] if f.values else "")).strip()
            if "@" in raw_sample:
                parts = raw_sample.split("@")
                masked = f"{parts[0][:2]}***@{parts[1]}"
            elif len(raw_sample) > 4:
                masked = f"{raw_sample[:2]}***{raw_sample[-2:]}"
            elif raw_sample:
                masked = "***"
            else:
                masked = "[Masked PII Value]"

            pii_results.append({
                "field": f.field_name,
                "category": cat,
                "confidence": conf,
                "sample": masked,
            })
    return pii_results


@relationships_router.get("/sources", response_model=Dict[str, Any])
def get_relationship_sources(
    user: UserResponse = Depends(get_authenticated_user),
):
    """List all available datasets and schemas accessible for relationship exploration."""
    profiles = engine.load_all_datasets()
    sources = []
    for k, p in profiles.items():
        sources.append({
            "key": k,
            "label": p.entity_name,
            "source_type": p.source_type,
            "file_or_db": p.file_or_db,
            "columns_count": len(p.columns),
            "columns": p.columns,
            "row_count": p.row_count,
            "primary_keys": p.primary_keys,
        })
    return {
        "status": "success",
        "total_sources": len(sources),
        "sources": sources,
    }


@relationships_router.get("/graph", response_model=RelationshipGraph)
def get_full_graph(
    focus: Optional[str] = Query(None, description="Optional entity or record ID filter"),
    user: UserResponse = Depends(get_authenticated_user),
):
    """Retrieve raw graph nodes and edges for visualization rendering."""
    return engine.build_relationship_graph(focus_entity_or_id=focus)


@relationships_router.get("/conversations", response_model=List[ConversationSummary])
def list_user_conversations(
    user: UserResponse = Depends(get_authenticated_user),
):
    """List all saved conversation threads belonging to the current user."""
    return chat_service.list_conversations(user.id)


@relationships_router.post("/conversations", response_model=ConversationSummary)
def create_new_conversation(
    payload: Optional[CreateConversationRequest] = None,
    title: Optional[str] = Query(None),
    user: UserResponse = Depends(get_authenticated_user),
):
    """Create a new conversational thread for the user."""
    conv_title = (payload.title if payload and payload.title else None) or title or "New Exploration"
    return chat_service.create_conversation(user.id, conv_title)


@relationships_router.get("/conversations/{conv_id}", response_model=ConversationDetail)
def get_conversation_history(
    conv_id: str,
    user: UserResponse = Depends(get_authenticated_user),
):
    """Retrieve full message history for a specific conversation."""
    conv = chat_service.get_conversation(conv_id, user.id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found or access denied.",
        )
    return conv


@relationships_router.patch("/conversations/{conv_id}", response_model=Dict[str, Any])
def rename_conversation(
    conv_id: str,
    payload: RenameConversationRequest,
    user: UserResponse = Depends(get_authenticated_user),
):
    """Rename a conversation title."""
    ok = chat_service.rename_conversation(conv_id, user.id, payload.title)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "success", "title": payload.title, "message": "Conversation renamed successfully"}


@relationships_router.delete("/conversations/{conv_id}", response_model=Dict[str, Any])
def delete_conversation(
    conv_id: str,
    user: UserResponse = Depends(get_authenticated_user),
):
    """Delete a conversation and its messages."""
    ok = chat_service.delete_conversation(conv_id, user.id)
    if not ok:
        raise HTTPException(status_code=404, detail="Conversation not found")
    ai_assistant.context_reasoner.clear_context(conv_id)
    return {"status": "success", "message": "Conversation deleted successfully"}


@relationships_router.delete("/conversations", response_model=Dict[str, Any])
def clear_all_conversations(
    user: UserResponse = Depends(get_authenticated_user),
):
    """Delete all conversations and message history for the current user."""
    count = chat_service.clear_all_conversations(user.id)
    return {"status": "success", "deleted_count": count, "message": "All conversations cleared successfully"}


@relationships_router.post("/upload", response_model=ConversationUploadResponse)
async def upload_conversation_attachment(
    file: UploadFile = File(...),
    conversation_id: Optional[str] = Query(None),
    user: UserResponse = Depends(get_authenticated_user),
):
    """
    Secure file upload & PII analysis endpoint:
    - Enforces maximum 10MB file size limit
    - Whitelists supported extensions (PDF, CSV, XLSX, TXT, JSON, SQLite)
    - Automatically parses schema & records using PrivSight ParserRegistry
    - Heuristically detects and masks sensitive personal data preview values
    - Persists file context to active conversation memory
    """
    MAX_SIZE = 10 * 1024 * 1024  # 10 MB limit
    ALLOWED_EXTS = {".pdf", ".csv", ".tsv", ".xlsx", ".xls", ".json", ".txt", ".db", ".sqlite", ".sqlite3"}

    ext = Path(file.filename or "").suffix.lower()
    if ext not in ALLOWED_EXTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported format '{ext}'. TRACERA supports PDF, CSV, XLSX, TXT, JSON, and SQLite files.",
        )

    contents = await file.read()
    if len(contents) > MAX_SIZE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File size exceeds maximum allowed 10MB limit.",
        )

    # Secure scratch storage
    upload_dir = Path("scratch/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    att_id = f"att-{uuid.uuid4().hex[:8]}"
    clean_filename = Path(file.filename or "uploaded_file").name
    temp_path = upload_dir / f"{att_id}_{clean_filename}"

    with open(temp_path, "wb") as f:
        f.write(contents)

    try:
        parsed = parser_registry.parse_file(temp_path)
    except Exception as err:
        logger.error(f"Failed to parse uploaded document: {err}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unable to parse document: {str(err)}",
        )

    pii_matches = _inspect_and_mask_pii(parsed)
    field_names = [f.field_name for f in parsed.fields]
    clean_type = ext.lstrip(".").lower()

    att_data = {
        "attachment_id": att_id,
        "filename": clean_filename,
        "file_type": clean_type,
        "file_size": len(contents),
        "total_records": parsed.total_records,
        "fields_count": len(field_names),
        "fields": field_names,
        "detected_pii": pii_matches,
        "summary": f"{clean_type.upper()} document with {parsed.total_records} record(s) and {len(field_names)} field(s), containing {len(pii_matches)} candidate personal data attribute(s).",
    }
    ACTIVE_ATTACHMENTS[att_id] = att_data

    if conversation_id:
        ai_assistant.context_reasoner.update_state(conversation_id=conversation_id, uploaded_file=att_data)

    return ConversationUploadResponse(
        status="success",
        attachment_id=att_id,
        filename=clean_filename,
        file_type=clean_type,
        file_size=len(contents),
        total_records=parsed.total_records,
        fields_count=len(field_names),
        fields=field_names,
        detected_pii=pii_matches,
        summary=att_data["summary"],
    )


@relationships_router.post("/chat", response_model=RelationshipReport)
def chat_with_assistant(
    payload: ChatQueryRequest,
    user: UserResponse = Depends(get_authenticated_user),
):
    """
    Main conversational endpoint:
    - Persists user query & attachment to SQLite
    - Evaluates query with multi-turn context
    - Discovers actual relationships & generates requested format
    - Adheres to GENERATE FORMAT -> EXPLAIN FORMAT -> ANALYZE RELATIONSHIPS -> CONCLUDE
    - Persists assistant response & returns structured report
    """
    conv_id = payload.conversation_id
    if not conv_id:
        new_conv = chat_service.create_conversation(user.id)
        conv_id = new_conv.id

    # Rehydrate attachment from cache if only attachment_id provided
    att_payload = payload.attachment
    if att_payload and "attachment_id" in att_payload and att_payload["attachment_id"] in ACTIVE_ATTACHMENTS:
        cached_att = ACTIVE_ATTACHMENTS[att_payload["attachment_id"]]
        cached_att.update(att_payload)
        att_payload = cached_att

    # Get conversation history for context resolution
    conv = chat_service.get_conversation(conv_id, user.id)
    history = conv.messages if conv else []

    # Save user message
    chat_service.add_message(
        conv_id=conv_id,
        user_id=user.id,
        role="user",
        content=payload.message,
        format_requested=payload.format_preference or "text",
        attachment=att_payload,
    )

    # Process query with AI Assistant
    report = ai_assistant.process_query(
        query=payload.message,
        conversation_history=history,
        selected_sources=payload.selected_sources,
        explicit_format=payload.format_preference,
        conversation_id=conv_id,
        attachment=att_payload,
    )

    # Save assistant response
    asst_msg = chat_service.add_message(
        conv_id=conv_id,
        user_id=user.id,
        role="assistant",
        content=report.explanation,
        format_requested=report.format_requested,
        format_explanation=report.format_explanation,
        graph_data=report.graph.model_dump() if report.graph else None,
        table_data=report.table_data,
        timeline_data=report.timeline_data,
        flowchart_data=report.flowchart_data,
        chart_data=report.chart_data,
        structured_data=report.comparison_data or report.data,
        response_type=report.response_type,
        sources_used=report.evidence_sources,
        attachment=att_payload,
    )

    report.conversation_id = conv_id
    report.message_id = asst_msg.id

    return report


@relationships_router.post("/chat/stream")
async def chat_stream_endpoint(
    payload: ChatQueryRequest,
    user: UserResponse = Depends(get_authenticated_user),
):
    """
    Streaming AI Response endpoint via Server-Sent Events (SSE):
    - Validates user & ensures thread isolation
    - Emits start, visual artifacts, token delta stream, and final completion marker
    - Persists cleanly without message duplication
    """
    conv_id = payload.conversation_id
    if not conv_id:
        new_conv = chat_service.create_conversation(user.id)
        conv_id = new_conv.id

    att_payload = payload.attachment
    if att_payload and "attachment_id" in att_payload and att_payload["attachment_id"] in ACTIVE_ATTACHMENTS:
        cached_att = ACTIVE_ATTACHMENTS[att_payload["attachment_id"]]
        cached_att.update(att_payload)
        att_payload = cached_att

    conv = chat_service.get_conversation(conv_id, user.id)
    history = conv.messages if conv else []

    # Persist user turn
    user_msg = chat_service.add_message(
        conv_id=conv_id,
        user_id=user.id,
        role="user",
        content=payload.message,
        format_requested=payload.format_preference or "text",
        attachment=att_payload,
    )

    # Synthesize complete report
    report = ai_assistant.process_query(
        query=payload.message,
        conversation_history=history,
        selected_sources=payload.selected_sources,
        explicit_format=payload.format_preference,
        conversation_id=conv_id,
        attachment=att_payload,
    )
    report.conversation_id = conv_id

    async def sse_event_stream():
        try:
            # 1. Start event
            yield f"event: start\ndata: {json.dumps({'conversation_id': conv_id, 'user_message_id': user_msg.id, 'title': report.title, 'response_type': report.response_type, 'format_requested': report.format_requested})}\n\n"

            # 2. Visual payload event if visual artifacts generated
            if report.response_type != "text" or report.graph or report.chart_data or report.table_data or report.flowchart_data or report.timeline_data:
                visual_payload = {
                    "response_type": report.response_type,
                    "title": report.title,
                    "format_explanation": report.format_explanation,
                    "graph": report.graph.model_dump() if report.graph else None,
                    "chart_data": report.chart_data,
                    "table_data": report.table_data,
                    "flowchart_data": report.flowchart_data,
                    "timeline_data": report.timeline_data,
                    "steps": report.steps,
                    "comparison_data": report.comparison_data,
                    "data": report.data,
                }
                yield f"event: visual\ndata: {json.dumps(visual_payload)}\n\n"

            # 3. Stream markdown explanation tokens progressively
            text = report.explanation or ""
            words = re.split(r"(\s+)", text)
            chunk_size = 4
            for i in range(0, len(words), chunk_size):
                chunk = "".join(words[i : i + chunk_size])
                yield f"event: token\ndata: {json.dumps({'chunk': chunk})}\n\n"
                await asyncio.sleep(0.015)

            # 4. Persist completed assistant response in database
            asst_msg = chat_service.add_message(
                conv_id=conv_id,
                user_id=user.id,
                role="assistant",
                content=report.explanation,
                format_requested=report.format_requested,
                format_explanation=report.format_explanation,
                graph_data=report.graph.model_dump() if report.graph else None,
                table_data=report.table_data,
                timeline_data=report.timeline_data,
                flowchart_data=report.flowchart_data,
                chart_data=report.chart_data,
                structured_data=report.comparison_data or report.data,
                response_type=report.response_type,
                sources_used=report.evidence_sources,
                attachment=att_payload,
            )
            report.message_id = asst_msg.id

            # 5. Done event with final report metadata
            yield f"event: done\ndata: {json.dumps({'message_id': asst_msg.id, 'conversation_id': conv_id, 'report': report.model_dump()})}\n\n"
        except Exception as ex:
            logger.error(f"Error in TRACERA stream: {ex}")
            yield f"event: error\ndata: {json.dumps({'error': str(ex)})}\n\n"

    return StreamingResponse(sse_event_stream(), media_type="text/event-stream")


@relationships_router.put("/conversations/{conv_id}/messages/{message_id}", response_model=RelationshipReport)
def edit_user_message_endpoint(
    conv_id: str,
    message_id: str,
    payload: EditMessageRequest,
    user: UserResponse = Depends(get_authenticated_user),
):
    """
    Edits a previous user message, prunes subsequent turns to prevent duplicates,
    and re-executes the assistant response.
    """
    edited_msg = chat_service.edit_user_message(conv_id, user.id, message_id, payload.content)
    if not edited_msg:
        raise HTTPException(status_code=404, detail="Message not found or access denied")

    conv = chat_service.get_conversation(conv_id, user.id)
    history = [m for m in (conv.messages if conv else []) if m.id != message_id]

    report = ai_assistant.process_query(
        query=payload.content,
        conversation_history=history,
        conversation_id=conv_id,
        attachment=edited_msg.attachment,
    )

    asst_msg = chat_service.add_message(
        conv_id=conv_id,
        user_id=user.id,
        role="assistant",
        content=report.explanation,
        format_requested=report.format_requested,
        format_explanation=report.format_explanation,
        graph_data=report.graph.model_dump() if report.graph else None,
        table_data=report.table_data,
        timeline_data=report.timeline_data,
        flowchart_data=report.flowchart_data,
        chart_data=report.chart_data,
        structured_data=report.comparison_data or report.data,
        response_type=report.response_type,
        sources_used=report.evidence_sources,
        attachment=edited_msg.attachment,
    )
    report.conversation_id = conv_id
    report.message_id = asst_msg.id
    return report


@relationships_router.post("/conversations/{conv_id}/regenerate", response_model=RelationshipReport)
def regenerate_response_endpoint(
    conv_id: str,
    payload: RegenerateRequest,
    user: UserResponse = Depends(get_authenticated_user),
):
    """
    Regenerates an assistant response by pruning the assistant response and re-running
    the preceding user query without creating duplicate turns.
    """
    conv = chat_service.get_conversation(conv_id, user.id)
    if not conv or not conv.messages:
        raise HTTPException(status_code=404, detail="Conversation has no messages to regenerate")

    # Find target message or last assistant message
    target_idx = -1
    if payload.message_id:
        for i, m in enumerate(conv.messages):
            if m.id == payload.message_id:
                target_idx = i
                break
    else:
        for i in range(len(conv.messages) - 1, -1, -1):
            if conv.messages[i].role == "assistant":
                target_idx = i
                break

    if target_idx <= 0:
        raise HTTPException(status_code=400, detail="No preceding user message found to regenerate")

    user_msg = None
    for i in range(target_idx - 1, -1, -1):
        if conv.messages[i].role == "user":
            user_msg = conv.messages[i]
            break

    if not user_msg:
        raise HTTPException(status_code=400, detail="Cannot find user query preceding this response")

    # Prune all messages after the user message (including target assistant message)
    chat_service.prune_messages_after(conv_id, user.id, user_msg.id)

    preceding_history = [m for m in conv.messages if m.created_at < user_msg.created_at]

    report = ai_assistant.process_query(
        query=user_msg.content,
        conversation_history=preceding_history,
        conversation_id=conv_id,
        attachment=user_msg.attachment,
    )

    asst_msg = chat_service.add_message(
        conv_id=conv_id,
        user_id=user.id,
        role="assistant",
        content=report.explanation,
        format_requested=report.format_requested,
        format_explanation=report.format_explanation,
        graph_data=report.graph.model_dump() if report.graph else None,
        table_data=report.table_data,
        timeline_data=report.timeline_data,
        flowchart_data=report.flowchart_data,
        chart_data=report.chart_data,
        structured_data=report.comparison_data or report.data,
        response_type=report.response_type,
        sources_used=report.evidence_sources,
        attachment=user_msg.attachment,
    )
    report.conversation_id = conv_id
    report.message_id = asst_msg.id
    return report


class SaveExportTestRequest(BaseModel):
    filename: str
    dataUri: str


@relationships_router.post("/save-export-test")
def save_export_test(payload: SaveExportTestRequest):
    """Utility endpoint to persist actual exported visualization files for inspection."""
    import base64
    import os
    from urllib.parse import unquote

    os.makedirs("test_exports", exist_ok=True)
    clean_filename = os.path.basename(payload.filename)
    dest_path = os.path.join("test_exports", clean_filename)

    data = payload.dataUri
    if "," in data:
        header, encoded = data.split(",", 1)
        if ";base64" in header:
            raw_bytes = base64.b64decode(encoded)
        else:
            raw_bytes = unquote(encoded).encode("utf-8")
    else:
        raw_bytes = data.encode("utf-8")

    with open(dest_path, "wb") as f:
        f.write(raw_bytes)

    return {"status": "ok", "path": dest_path, "size": len(raw_bytes)}

