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

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status

from backend.auth.models import UserResponse
from backend.auth.routes import get_authenticated_user
from backend.relationships.ai_assistant import AIAssistant
from backend.relationships.chat_service import ChatPersistenceService
from backend.relationships.engine import RelationshipEngine
from backend.relationships.models import (
    ChatQueryRequest,
    ConversationDetail,
    ConversationSummary,
    CreateConversationRequest,
    RelationshipGraph,
    RelationshipReport,
    RenameConversationRequest,
)

logger = logging.getLogger("privsight.relationships.routes")

relationships_router = APIRouter(prefix="/api/relationships", tags=["Relationship Intelligence"])
engine = RelationshipEngine()
ai_assistant = AIAssistant(engine)
chat_service = ChatPersistenceService()


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
    return {"status": "success", "message": "Conversation deleted successfully"}


@relationships_router.post("/chat", response_model=RelationshipReport)
def chat_with_assistant(
    payload: ChatQueryRequest,
    user: UserResponse = Depends(get_authenticated_user),
):
    """
    Main conversational endpoint:
    - Persists user query to SQLite
    - Evaluates query with multi-turn context
    - Discovers actual relationships & generates requested format
    - Adheres to GENERATE FORMAT -> EXPLAIN FORMAT -> ANALYZE RELATIONSHIPS -> CONCLUDE
    - Persists assistant response & returns structured report
    """
    conv_id = payload.conversation_id
    if not conv_id:
        new_conv = chat_service.create_conversation(user.id)
        conv_id = new_conv.id

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
    )

    # Process query with AI Assistant
    report = ai_assistant.process_query(
        query=payload.message,
        conversation_history=history,
        selected_sources=payload.selected_sources,
        explicit_format=payload.format_preference,
    )

    # Save assistant response
    chat_service.add_message(
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
        sources_used=report.evidence_sources,
    )

    return report
