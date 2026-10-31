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
    # Phase 4: Visual & Artifact Memory
    last_visualization_type: Optional[str] = None
    last_visualization_title: Optional[str] = None
    last_graph_nodes: List[str] = field(default_factory=list)
    last_graph_edges: List[Dict[str, Any]] = field(default_factory=list)
    last_chart_data: Optional[Dict[str, Any]] = None
    last_table_data: Optional[List[Dict[str, Any]]] = None
    last_flowchart_data: Optional[Dict[str, Any]] = None
    last_timeline_data: Optional[List[Dict[str, Any]]] = None
    active_uploaded_file: Optional[Dict[str, Any]] = None


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
        Resolves pronouns, references, follow-up entity switches,
        previously generated visualizations (graphs/charts/tables), and file attachments.
        Returns (resolution_metadata, rewritten_or_resolved_summary).
        """
        ctx = self.get_or_create_context(conversation_id)
        q_lower = query.lower().strip()

        # Re-populate from history if memory was evacuated or fresh page load
        if history:
            self._rehydrate_from_history(ctx, history)

        resolved_meta: Dict[str, Any] = {
            "has_table_reference": False,
            "has_entity_pronoun": False,
            "referenced_tables": [],
            "referenced_entities": [],
            "referenced_fields": [],
            "entity_switch": None,
            "has_visual_reference": False,
            "visual_reference_action": None,  # "explain", "convert", "summarize"
            "last_visual_type": ctx.last_visualization_type,
            "has_file_reference": False,
            "uploaded_file": ctx.active_uploaded_file,
        }

        # 1. Detect "What about <entity>?" switch
        switch_match = FOLLOW_UP_SWITCH_PATTERN.search(query)
        if switch_match:
            new_ent = switch_match.group(1).lower().rstrip("s")
            if new_ent not in ("their", "they", "them", "these", "those", "this", "that", "the", "its", "it"):
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

        # 4. Check for reference to previously generated visualization ("explain this graph", "convert into a table")
        is_visual_explain = False
        if re.search(r"\b(?:explain|describe|break down|analyze|detail)\s+(?:this|the)\s+(?:graph|chart|diagram|visualization|flowchart|table|timeline|visual)\b", q_lower):
            is_visual_explain = True
        elif q_lower in ("explain this", "explain this graph", "explain this chart", "explain this diagram", "explain the graph", "explain it", "explain visualization"):
            is_visual_explain = True
        elif re.search(r"\b(?:explain|describe|break down|analyze)\s+(?:this|it)\b", q_lower) and not any(w in q_lower for w in ["difference", "methodology", "gdpr", "quasi", "direct", "concept", "origin", "lineage", "ledger", "egress"]):
            if ctx.last_visualization_type:
                is_visual_explain = True

        if is_visual_explain:
            resolved_meta["has_visual_reference"] = True
            resolved_meta["visual_reference_action"] = "explain"

        if re.search(r"\b(?:convert|turn|switch|change|make)\s+(?:this|it)\s+(?:in|into|to)\s+(?:a|an)?\s*(table|graph|chart|flowchart|timeline|step-by-step)\b", q_lower) or q_lower in ("convert it into a table", "convert this into a table", "now show it in a table", "convert to table", "show as a table"):
            resolved_meta["has_visual_reference"] = True
            resolved_meta["visual_reference_action"] = "convert"

        # 5. Check for reference to uploaded file ("this file", "in this file", "uploaded file")
        if (re.search(r"\b(?:this|the)\s+file\b", q_lower) or re.search(r"\b(?:uploaded|attached)\s+file\b", q_lower) or "in this csv" in q_lower or "in this pdf" in q_lower or "in this xlsx" in q_lower or "in this json" in q_lower) and ctx.active_uploaded_file:
            resolved_meta["has_file_reference"] = True

        summary = ""
        if resolved_meta["has_table_reference"]:
            summary += f"Resolved table reference to: {', '.join(resolved_meta['referenced_tables'][:3])}. "
        if resolved_meta["has_entity_pronoun"]:
            summary += f"Resolved entity reference to: {', '.join(resolved_meta['referenced_entities'])}. "
        if resolved_meta["has_visual_reference"]:
            summary += f"Resolved visual reference to previous {ctx.last_visualization_type or 'visualization'}. "
        if resolved_meta["has_file_reference"]:
            summary += f"Resolved file reference to uploaded file '{ctx.active_uploaded_file.get('filename')}'. "

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
        visualization_type: Optional[str] = None,
        visualization_title: Optional[str] = None,
        graph_data: Optional[Dict[str, Any]] = None,
        chart_data: Optional[Dict[str, Any]] = None,
        table_data: Optional[List[Dict[str, Any]]] = None,
        flowchart_data: Optional[Dict[str, Any]] = None,
        timeline_data: Optional[List[Dict[str, Any]]] = None,
        uploaded_file: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update active conversation state with current turn entities and visualizations."""
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
        if visualization_type:
            ctx.last_visualization_type = visualization_type
        if visualization_title:
            ctx.last_visualization_title = visualization_title
        if graph_data:
            nodes = [n.get("label") or n.get("id") for n in graph_data.get("nodes", [])]
            if nodes:
                ctx.last_graph_nodes = nodes
                for n in nodes:
                    if n not in ctx.active_entities:
                        ctx.active_entities.append(n)
            ctx.last_graph_edges = graph_data.get("edges", [])
        if chart_data:
            ctx.last_chart_data = chart_data
        if table_data:
            ctx.last_table_data = table_data
        if flowchart_data:
            ctx.last_flowchart_data = flowchart_data
        if timeline_data:
            ctx.last_timeline_data = timeline_data
        if uploaded_file:
            ctx.active_uploaded_file = uploaded_file

    def _rehydrate_from_history(self, ctx: ConversationContext, history: List[ChatMessage]) -> None:
        """Inspect conversation history to recover active entities, previous visuals, and files."""
        for msg in reversed(history):
            # 1. Recover file attachment
            if msg.attachment and not ctx.active_uploaded_file:
                ctx.active_uploaded_file = msg.attachment

            # 2. Recover previous visualization
            if msg.role == "assistant":
                if msg.graph_data and not ctx.last_graph_nodes:
                    ctx.last_visualization_type = "relationship_graph"
                    nodes = [n.get("label") or n.get("id") for n in msg.graph_data.get("nodes", [])]
                    ctx.last_graph_nodes = nodes
                    for n in nodes:
                        if n not in ctx.active_entities:
                            ctx.active_entities.append(n)
                elif msg.chart_data and not ctx.last_chart_data:
                    ctx.last_visualization_type = msg.response_type or "bar_chart"
                    ctx.last_chart_data = msg.chart_data
                elif msg.table_data and not ctx.last_table_data:
                    ctx.last_visualization_type = "table"
                    ctx.last_table_data = msg.table_data
                elif msg.flowchart_data and not ctx.last_flowchart_data:
                    ctx.last_visualization_type = "flowchart"
                    ctx.last_flowchart_data = msg.flowchart_data
                elif msg.timeline_data and not ctx.last_timeline_data:
                    ctx.last_visualization_type = "timeline"
                    ctx.last_timeline_data = msg.timeline_data

            # 3. Recover active entities & tables from message content
            content_l = msg.content.lower()
            for ent in ["customer", "employee", "order", "payment", "department", "transaction"]:
                if ent in content_l:
                    if ent.title() not in ctx.active_entities:
                        ctx.active_entities.append(ent.title())

            for tbl in ["customers.csv", "employees.csv", "orders.csv", "payments.csv", "departments.csv", "transactions.csv"]:
                if tbl in content_l:
                    if tbl not in ctx.active_tables:
                        ctx.active_tables.append(tbl)

