"""
backend/relationships/models.py
===============================
Pydantic data models for the AI Relationship Intelligence Assistant.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field


VerificationStatus = Literal[
    "Verified",
    "Inferred",
    "Unverified",
    "No Match",
    "Possible",
    "Needs Review",
    "Rejected",
]
CardinalityType = Literal["1:1", "1:N", "N:M", "Unknown"]
RelationshipKind = Literal[
    "person_to_person",
    "person_to_company",
    "person_to_department",
    "document_to_entity",
    "email_to_person",
    "phone_to_person",
    "order_to_payment",
    "identifier_match",
    "foreign_key",
    "indirect_connection",
    "unknown"
]
ExplanationFormat = Literal[
    "text",
    "graph",
    "relationship_graph",
    "table",
    "tabular",
    "bar_chart",
    "line_chart",
    "pie_chart",
    "chart",
    "flowchart",
    "diagram",
    "timeline",
    "bullet_points",
    "step_by_step",
    "comparison",
    "structured_report",
]


class RelationshipHop(BaseModel):
    """Represents one step in a multi-hop relationship path."""
    hop_number: int = 1
    source_entity: str
    source_dataset: str
    source_field: str
    target_entity: str
    target_dataset: str
    target_field: str
    relationship_type: str
    cardinality: CardinalityType = "1:N"
    verification_status: VerificationStatus = "Verified"
    confidence_score: float = 1.0
    evidence: str


class RelationshipPath(BaseModel):
    """Represents a direct or multi-hop path connecting two entities across datasets."""
    source_entity: str
    target_entity: str
    hops_count: int
    hops: List[RelationshipHop] = Field(default_factory=list)
    path_summary: str
    overall_cardinality: CardinalityType = "1:N"
    verification_status: VerificationStatus = "Verified"
    confidence_score: float = 1.0
    explanation: str


class EvidenceItem(BaseModel):
    """Structured evidence record backing an AI assistant statement or relationship."""
    source_table: str
    source_column: str
    target_table: Optional[str] = None
    target_column: Optional[str] = None
    relationship_type: str
    evidence_reference: str
    verification_status: VerificationStatus = "Verified"
    confidence_score: float = 1.0
    notes: Optional[str] = None


class EntityNode(BaseModel):
    """Represents a node in the relationship graph."""
    id: str
    label: str
    entity_type: str  # e.g., 'Person', 'Company', 'Department', 'Order', 'Payment', 'Document', 'Email', 'Phone'
    source_type: str  # 'CSV', 'SQL', 'Upload', 'Document'
    source_name: str  # e.g. 'customers.csv', 'relational_demo.db:orders'
    primary_key: Optional[str] = None
    record_id: Optional[str] = None
    attributes: Dict[str, Any] = Field(default_factory=dict)
    masked_attributes: Dict[str, Any] = Field(default_factory=dict)


class RelationshipEdge(BaseModel):
    """Represents a directed or undirected connection between two entities."""
    id: str
    source_id: str
    target_id: str
    source_label: str
    target_label: str
    relationship_type: str
    kind: RelationshipKind = "identifier_match"
    cardinality: CardinalityType = "1:N"
    verification_status: VerificationStatus = "Verified"
    confidence_score: float = 1.0
    evidence: str
    source_field: str
    target_field: str
    source_dataset: str
    target_dataset: str
    match_count: int = 0
    sample_matches: List[Dict[str, Any]] = Field(default_factory=list)
    is_direct: bool = True
    hops: int = 1
    warnings: List[str] = Field(default_factory=list)


class RelationshipGraph(BaseModel):
    """Graph structure containing nodes and edges."""
    nodes: List[EntityNode] = Field(default_factory=list)
    edges: List[RelationshipEdge] = Field(default_factory=list)
    total_nodes: int = 0
    total_edges: int = 0
    verified_count: int = 0
    possible_count: int = 0
    needs_review_count: int = 0


class RelationshipReport(BaseModel):
    """Full structured response for natural language relationship intelligence."""
    query: str
    selected_sources: List[str] = Field(default_factory=list)
    format_requested: ExplanationFormat = "text"
    response_type: str = "text"
    title: Optional[str] = None
    explanation: str
    format_explanation: Optional[str] = None
    graph: Optional[RelationshipGraph] = None
    table_data: Optional[List[Dict[str, Any]]] = None
    timeline_data: Optional[List[Dict[str, Any]]] = None
    flowchart_data: Optional[Dict[str, Any]] = None
    chart_data: Optional[Dict[str, Any]] = None
    data: Optional[Dict[str, Any]] = None
    steps: Optional[List[Dict[str, Any]]] = None
    comparison_data: Optional[Dict[str, Any]] = None
    nodes: Optional[List[Dict[str, Any]]] = None
    edges: Optional[List[Dict[str, Any]]] = None
    verification_status: Optional[str] = None
    summary: Dict[str, Any] = Field(default_factory=dict)
    warnings: List[str] = Field(default_factory=list)
    evidence_sources: List[str] = Field(default_factory=list)
    conversation_id: Optional[str] = None
    message_id: Optional[str] = None
    relationship_paths: Optional[List[RelationshipPath]] = None
    evidence_items: Optional[List[EvidenceItem]] = None
    identified_entities: Optional[List[Dict[str, Any]]] = None
    context_state: Optional[Dict[str, Any]] = None


# --- Chat & Conversation Persistence Models ---

class ChatMessage(BaseModel):
    """A single conversational turn."""
    id: str
    conversation_id: str
    role: Literal["user", "assistant", "system"]
    content: str
    format_requested: ExplanationFormat = "text"
    response_type: Optional[str] = None
    format_explanation: Optional[str] = None
    graph_data: Optional[Dict[str, Any]] = None
    table_data: Optional[List[Dict[str, Any]]] = None
    timeline_data: Optional[List[Dict[str, Any]]] = None
    flowchart_data: Optional[Dict[str, Any]] = None
    chart_data: Optional[Dict[str, Any]] = None
    structured_data: Optional[Dict[str, Any]] = None
    sources_used: List[str] = Field(default_factory=list)
    created_at: str


class ConversationSummary(BaseModel):
    """Overview of a user's conversation thread."""
    id: str
    user_id: int
    title: str
    created_at: str
    updated_at: str
    message_count: int = 0


class ConversationDetail(BaseModel):
    """Full conversation with message history."""
    id: str
    user_id: int
    title: str
    created_at: str
    updated_at: str
    messages: List[ChatMessage] = Field(default_factory=list)


class ChatQueryRequest(BaseModel):
    """Request payload sent by frontend chat."""
    message: str
    conversation_id: Optional[str] = None
    selected_sources: Optional[List[str]] = None
    format_preference: Optional[ExplanationFormat] = None


class CreateConversationRequest(BaseModel):
    """Create a new conversation thread."""
    title: Optional[str] = "New Exploration"


class RenameConversationRequest(BaseModel):
    """Rename a conversation title."""
    title: str
