"""
backend/relationships/chat_service.py
=====================================
Persistent database service for user conversation threads and messages.
Stored securely in SQLite (data/users.db) and tied directly to the authenticated user.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.auth.db import get_db_connection
from backend.relationships.models import (
    ChatMessage,
    ConversationDetail,
    ConversationSummary,
    ExplanationFormat,
)

logger = logging.getLogger("privsight.relationships.chat")


def init_chat_tables(db_path: Optional[Path] = None) -> None:
    """Ensure conversation and chat message tables exist in the database."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS ai_conversations (
                    id TEXT PRIMARY KEY,
                    user_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
                );

                CREATE TABLE IF NOT EXISTS ai_chat_messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    format_requested TEXT DEFAULT 'text',
                    format_explanation TEXT,
                    graph_data TEXT,
                    table_data TEXT,
                    timeline_data TEXT,
                    flowchart_data TEXT,
                    chart_data TEXT,
                    structured_data TEXT,
                    response_type TEXT,
                    sources_used TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (conversation_id) REFERENCES ai_conversations(id) ON DELETE CASCADE
                );

                CREATE INDEX IF NOT EXISTS idx_ai_conv_user ON ai_conversations(user_id);
                CREATE INDEX IF NOT EXISTS idx_ai_msg_conv ON ai_chat_messages(conversation_id);
                """
            )
            # Schema migrations for existing SQLite databases
            for col in ["chart_data", "structured_data", "response_type", "attachment"]:
                try:
                    conn.execute(f"ALTER TABLE ai_chat_messages ADD COLUMN {col} TEXT")
                except Exception:
                    pass
    finally:
        conn.close()


class ChatPersistenceService:
    """Handles conversation threads and message persistence with user isolation."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path
        init_chat_tables(self.db_path)

    def _conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    def create_conversation(self, user_id: int, title: str = "New Exploration") -> ConversationSummary:
        conv_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        try:
            with conn:
                conn.execute(
                    """
                    INSERT INTO ai_conversations (id, user_id, title, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (conv_id, user_id, title, now, now),
                )
            return ConversationSummary(
                id=conv_id,
                user_id=user_id,
                title=title,
                created_at=now,
                updated_at=now,
                message_count=0,
            )
        finally:
            conn.close()

    def list_conversations(self, user_id: int) -> List[ConversationSummary]:
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT c.id, c.user_id, c.title, c.created_at, c.updated_at,
                       COUNT(m.id) as message_count
                FROM ai_conversations c
                LEFT JOIN ai_chat_messages m ON c.id = m.conversation_id
                WHERE c.user_id = ?
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                """,
                (user_id,),
            )
            rows = cur.fetchall()
            return [
                ConversationSummary(
                    id=r["id"],
                    user_id=r["user_id"],
                    title=r["title"],
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    message_count=r["message_count"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def get_conversation(self, conv_id: str, user_id: int) -> Optional[ConversationDetail]:
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT id, user_id, title, created_at, updated_at FROM ai_conversations WHERE id = ? AND user_id = ?",
                (conv_id, user_id),
            )
            conv_row = cur.fetchone()
            if not conv_row:
                return None

            cur.execute(
                """
                SELECT id, conversation_id, role, content, format_requested,
                       format_explanation, graph_data, table_data, timeline_data,
                       flowchart_data, chart_data, structured_data, response_type,
                       sources_used, attachment, created_at
                FROM ai_chat_messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
                """,
                (conv_id,),
            )
            msg_rows = cur.fetchall()
            messages: List[ChatMessage] = []
            for m in msg_rows:
                messages.append(
                    ChatMessage(
                        id=m["id"],
                        conversation_id=m["conversation_id"],
                        role=m["role"],
                        content=m["content"],
                        format_requested=m["format_requested"] or "text",
                        format_explanation=m["format_explanation"],
                        graph_data=json.loads(m["graph_data"]) if m["graph_data"] else None,
                        table_data=json.loads(m["table_data"]) if m["table_data"] else None,
                        timeline_data=json.loads(m["timeline_data"]) if m["timeline_data"] else None,
                        flowchart_data=json.loads(m["flowchart_data"]) if m["flowchart_data"] else None,
                        chart_data=json.loads(m["chart_data"]) if ("chart_data" in m.keys() and m["chart_data"]) else None,
                        structured_data=json.loads(m["structured_data"]) if ("structured_data" in m.keys() and m["structured_data"]) else None,
                        response_type=m["response_type"] if "response_type" in m.keys() else None,
                        sources_used=json.loads(m["sources_used"]) if m["sources_used"] else [],
                        attachment=json.loads(m["attachment"]) if ("attachment" in m.keys() and m["attachment"]) else None,
                        created_at=m["created_at"],
                    )
                )

            return ConversationDetail(
                id=conv_row["id"],
                user_id=conv_row["user_id"],
                title=conv_row["title"],
                created_at=conv_row["created_at"],
                updated_at=conv_row["updated_at"],
                messages=messages,
            )
        finally:
            conn.close()

    def add_message(
        self,
        conv_id: str,
        user_id: int,
        role: str,
        content: str,
        format_requested: ExplanationFormat = "text",
        format_explanation: Optional[str] = None,
        graph_data: Optional[Dict[str, Any]] = None,
        table_data: Optional[List[Dict[str, Any]]] = None,
        timeline_data: Optional[List[Dict[str, Any]]] = None,
        flowchart_data: Optional[Dict[str, Any]] = None,
        chart_data: Optional[Dict[str, Any]] = None,
        structured_data: Optional[Dict[str, Any]] = None,
        response_type: Optional[str] = None,
        sources_used: Optional[List[str]] = None,
        attachment: Optional[Dict[str, Any]] = None,
    ) -> ChatMessage:
        conn = self._conn()
        try:
            # Verify user owns conversation
            cur = conn.cursor()
            cur.execute("SELECT id, title FROM ai_conversations WHERE id = ? AND user_id = ?", (conv_id, user_id))
            conv = cur.fetchone()
            if not conv:
                raise ValueError("Conversation not found or access denied")

            msg_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc).isoformat()

            with conn:
                conn.execute(
                    """
                    INSERT INTO ai_chat_messages (
                        id, conversation_id, role, content, format_requested,
                        format_explanation, graph_data, table_data, timeline_data,
                        flowchart_data, chart_data, structured_data, response_type,
                        sources_used, attachment, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        msg_id,
                        conv_id,
                        role,
                        content,
                        format_requested,
                        format_explanation,
                        json.dumps(graph_data) if graph_data else None,
                        json.dumps(table_data) if table_data else None,
                        json.dumps(timeline_data) if timeline_data else None,
                        json.dumps(flowchart_data) if flowchart_data else None,
                        json.dumps(chart_data) if chart_data else None,
                        json.dumps(structured_data) if structured_data else None,
                        response_type or format_requested,
                        json.dumps(sources_used) if sources_used else None,
                        json.dumps(attachment) if attachment else None,
                        now,
                    ),
                )

                # Auto-generate title if it's the first user message
                if role == "user" and (conv["title"] == "New Exploration" or conv["title"].startswith("New ")):
                    clean_title = content.strip().replace("\n", " ")
                    if len(clean_title) > 40:
                        clean_title = clean_title[:37] + "..."
                    conn.execute(
                        "UPDATE ai_conversations SET title = ?, updated_at = ? WHERE id = ?",
                        (clean_title, now, conv_id),
                    )
                else:
                    conn.execute(
                        "UPDATE ai_conversations SET updated_at = ? WHERE id = ?",
                        (now, conv_id),
                    )

            return ChatMessage(
                id=msg_id,
                conversation_id=conv_id,
                role=role,
                content=content,
                format_requested=format_requested,
                format_explanation=format_explanation,
                graph_data=graph_data,
                table_data=table_data,
                timeline_data=timeline_data,
                flowchart_data=flowchart_data,
                chart_data=chart_data,
                structured_data=structured_data,
                response_type=response_type or format_requested,
                sources_used=sources_used or [],
                attachment=attachment,
                created_at=now,
            )
        finally:
            conn.close()

    def edit_user_message(
        self,
        conv_id: str,
        user_id: int,
        message_id: str,
        new_content: str,
    ) -> Optional[ChatMessage]:
        """
        Edits a previous user message, updates its content,
        and deletes all subsequent messages in the conversation to allow
        clean regeneration without duplicate turns.
        """
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM ai_conversations WHERE id = ? AND user_id = ?", (conv_id, user_id))
            if not cur.fetchone():
                return None

            cur.execute("SELECT id, created_at, role, format_requested, attachment FROM ai_chat_messages WHERE id = ? AND conversation_id = ?", (message_id, conv_id))
            target_msg = cur.fetchone()
            if not target_msg:
                return None

            target_time = target_msg["created_at"]
            now = datetime.now(timezone.utc).isoformat()

            with conn:
                # Prune trailing messages created after this user message
                conn.execute(
                    "DELETE FROM ai_chat_messages WHERE conversation_id = ? AND id != ? AND created_at >= ?",
                    (conv_id, message_id, target_time),
                )
                conn.execute(
                    "UPDATE ai_chat_messages SET content = ? WHERE id = ?",
                    (new_content.strip(), message_id),
                )
                conn.execute(
                    "UPDATE ai_conversations SET updated_at = ? WHERE id = ?",
                    (now, conv_id),
                )

            return ChatMessage(
                id=message_id,
                conversation_id=conv_id,
                role=target_msg["role"],
                content=new_content.strip(),
                format_requested=target_msg["format_requested"] or "text",
                attachment=json.loads(target_msg["attachment"]) if ("attachment" in target_msg.keys() and target_msg["attachment"]) else None,
                created_at=target_time,
            )
        finally:
            conn.close()

    def prune_messages_after(self, conv_id: str, user_id: int, message_id: str) -> bool:
        """Deletes all messages strictly after the specified message in the conversation."""
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM ai_conversations WHERE id = ? AND user_id = ?", (conv_id, user_id))
            if not cur.fetchone():
                return False

            cur.execute("SELECT created_at FROM ai_chat_messages WHERE id = ? AND conversation_id = ?", (message_id, conv_id))
            row = cur.fetchone()
            if not row:
                return False

            with conn:
                conn.execute(
                    "DELETE FROM ai_chat_messages WHERE conversation_id = ? AND id != ? AND created_at >= ?",
                    (conv_id, message_id, row["created_at"]),
                )
                now = datetime.now(timezone.utc).isoformat()
                conn.execute("UPDATE ai_conversations SET updated_at = ? WHERE id = ?", (now, conv_id))
            return True
        finally:
            conn.close()

    def delete_message(self, conv_id: str, user_id: int, message_id: str) -> bool:
        """Deletes a specific message and any following response."""
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute("SELECT id FROM ai_conversations WHERE id = ? AND user_id = ?", (conv_id, user_id))
            if not cur.fetchone():
                return False
            with conn:
                cur = conn.execute("DELETE FROM ai_chat_messages WHERE id = ? AND conversation_id = ?", (message_id, conv_id))
                return cur.rowcount > 0
        finally:
            conn.close()

    def rename_conversation(self, conv_id: str, user_id: int, new_title: str) -> bool:
        conn = self._conn()
        try:
            now = datetime.now(timezone.utc).isoformat()
            with conn:
                cur = conn.execute(
                    "UPDATE ai_conversations SET title = ?, updated_at = ? WHERE id = ? AND user_id = ?",
                    (new_title.strip() or "Untitled", now, conv_id, user_id),
                )
                return cur.rowcount > 0
        finally:
            conn.close()

    def delete_conversation(self, conv_id: str, user_id: int) -> bool:
        conn = self._conn()
        try:
            with conn:
                cur = conn.execute(
                    "DELETE FROM ai_conversations WHERE id = ? AND user_id = ?",
                    (conv_id, user_id),
                )
                return cur.rowcount > 0
        finally:
            conn.close()

    def clear_all_conversations(self, user_id: int) -> int:
        conn = self._conn()
        try:
            with conn:
                cur = conn.execute(
                    "DELETE FROM ai_conversations WHERE user_id = ?",
                    (user_id,),
                )
                return cur.rowcount
        finally:
            conn.close()
