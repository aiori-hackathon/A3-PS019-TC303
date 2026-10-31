"""
backend/relationships/context_reasoner.py
=========================================
Contextual AI Reasoning & Multi-Turn State Tracker for PrivSight TRACERA Phase 2.

Handles:
- Per-conversation isolated context memory
- Reference resolution ("these tables", "those records", "their connection to payments", "which of these contain email")
- Conversational entity carryover and focus switching
- Clean initialization on New Chat
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.relationships.models import ChatMessage

logger = logging.getLogger("privsight.relationships.context")

# Pronoun and anaphoric reference triggers
TABLE_REFERENCE_PATTERNS = [
    r"\bthese tables\b",
    r"\bthose tables\b",
    r"\bthe tables\b",
    r"\bwhich of these\b",
    r"\bof these tables\b",
    r"\bin these tables\b",
    r"\bacross these\b",
]

ENTITY_PRONOUN_PATTERNS = [
    r"\bthey\b",
    r"\bthem\b",
    r"\btheir\b",
    r"\bthis entity\b",
    r"\bthat entity\b",
    r"\bthese records\b",
    r"\bhow are they connected\b",
    r"\bhow is it connected\b",
]

FOLLOW_UP_SWITCH_PATTERN = re.compile(
    r"\b(?:what|how)\s+about\s+([a-zA-Z_\-]+)\b",
    re.IGNORECASE,
)


@dataclass
class ConversationContext:
    """Isolated contextual state for a single conversation thread."""
    conversation_id: str
    active_entities: List[str] = field(default_factory=list)
    active_tables: List[str] = field(default_factory=list)
    active_fields: List[str] = field(default_factory=list)
    active_classes: List[str] = field(default_factory=list)
    active_record_ids: List[str] = field(default_factory=list)
    last_intent: Optional[str] = None
    turns_count: int = 0


class ContextualReasoner:
    """
    Maintains and resolves multi-turn conversational context.
    Strictly isolates state by conversation_id to prevent cross-chat data leakage.
    """

    def __init__(self) -> None:
        self._contexts: Dict[str, ConversationContext] = {}

    def get_or_create_context(self, conversation_id: str) -> ConversationContext:
        """Get or initialize context for a conversation."""
        if conversation_id not in self._contexts:
            self._contexts[conversation_id] = ConversationContext(conversation_id=conversation_id)
        return self._contexts[conversation_id]

    def clear_context(self, conversation_id: str) -> None:
        """Reset context when a conversation is cleared or deleted."""
        if conversation_id in self._contexts:
            del self._contexts[conversation_id]

    def resolve_references(
        self,
        query: str,
        conversation_id: str,
        history: Optional[List[ChatMessage]] = None,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Resolves pronouns, references, and follow-up entity switches.
        Returns (resolution_metadata, rewritten_or_resolved_summary).
        """
        ctx = self.get_or_create_context(conversation_id)
        q_lower = query.lower().strip()

        # Re-populate from history if memory was evacuated
        if not ctx.active_entities and history:
            self._rehydrate_from_history(ctx, history)

        resolved_meta: Dict[str, Any] = {
            "has_table_reference": False,
            "has_entity_pronoun": False,
            "referenced_tables": [],
            "referenced_entities": [],
            "referenced_fields": [],
            "entity_switch": None,
        }

        # 1. Detect "What about <entity>?" switch
        switch_match = FOLLOW_UP_SWITCH_PATTERN.search(query)
        if switch_match:
            new_ent = switch_match.group(1).lower().rstrip("s")
            resolved_meta["entity_switch"] = new_ent.title()
            return resolved_meta, f"Switched entity focus to {new_ent.title()}"

        # 2. Check for "these tables" / "which of these" reference
        has_table_ref = any(re.search(p, q_lower) for p in TABLE_REFERENCE_PATTERNS)
        if has_table_ref and ctx.active_tables:
            resolved_meta["has_table_reference"] = True
            resolved_meta["referenced_tables"] = list(ctx.active_tables)

        # 3. Check for "they" / "them" / "their" / "how are they connected"
        has_entity_ref = any(re.search(p, q_lower) for p in ENTITY_PRONOUN_PATTERNS)
        if has_entity_ref and ctx.active_entities:
            resolved_meta["has_entity_pronoun"] = True
            resolved_meta["referenced_entities"] = list(ctx.active_entities)

        summary = ""
        if resolved_meta["has_table_reference"]:
            summary += f"Resolved table reference to: {', '.join(resolved_meta['referenced_tables'][:3])}. "
        if resolved_meta["has_entity_pronoun"]:
            summary += f"Resolved entity reference to: {', '.join(resolved_meta['referenced_entities'])}. "

        return resolved_meta, summary.strip()

    def update_state(
        self,
        conversation_id: str,
        entities: Optional[List[str]] = None,
        tables: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        classes: Optional[List[str]] = None,
        record_id: Optional[str] = None,
        intent: Optional[str] = None,
    ) -> None:
        """Update active conversation state with current turn entities."""
        ctx = self.get_or_create_context(conversation_id)
        ctx.turns_count += 1

        if entities:
            ctx.active_entities = list(dict.fromkeys(entities))
        if tables:
            ctx.active_tables = list(dict.fromkeys(tables))
        if fields:
            ctx.active_fields = list(dict.fromkeys(fields))
        if classes:
            ctx.active_classes = list(dict.fromkeys(classes))
        if record_id:
            ctx.active_record_ids = [record_id]
        if intent:
            ctx.last_intent = intent

    def _rehydrate_from_history(self, ctx: ConversationContext, history: List[ChatMessage]) -> None:
        """Inspect recent conversation history to recover active entities if memory was cold."""
        for msg in reversed(history[-4:]):
            content_l = msg.content.lower()
            for ent in ["customer", "employee", "order", "payment", "department", "transaction"]:
                if ent in content_l:
                    if ent.title() not in ctx.active_entities:
                        ctx.active_entities.append(ent.title())

            for tbl in ["customers.csv", "employees.csv", "orders.csv", "payments.csv", "departments.csv", "transactions.csv"]:
                if tbl in content_l:
                    if tbl not in ctx.active_tables:
                        ctx.active_tables.append(tbl)
            if ctx.active_entities:
                break
