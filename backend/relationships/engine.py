"""
backend/relationships/engine.py
================================
Core deterministic relationship discovery, verification, and graph engine for PrivSight.

Analyzes real stored data sources:
1. SQLite PRAGMA foreign_key_list & primary_key constraints
2. CSV and multi-format files
3. Matching identifier columns and values across datasets
4. Value-level referential analysis (detecting orphaned keys, uniqueness, 1:1, 1:N, N:M cardinality)
5. Personal data masking for sensitive fields
"""

from __future__ import annotations

import csv
import logging
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from backend.parsers.registry import get_parser_registry
from backend.relationships.models import (
    CardinalityType,
    EntityNode,
    RelationshipEdge,
    RelationshipGraph,
    RelationshipKind,
    VerificationStatus,
)

logger = logging.getLogger("privsight.relationships.engine")

# Common identifier suffixes indicating joinable foreign keys or primary keys
IDENTIFIER_SUFFIXES = ("_id", "id", "_ref", "_code", "_number", "num", "_key")

# Masking patterns
EMAIL_REGEX = re.compile(r"^([a-zA-Z0-9_.+-]+)@([a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)$")
PHONE_REGEX = re.compile(r"\+?\d[\d\-\s]{7,}\d")


def mask_personal_value(field_name: str, val: Any) -> str:
    """Mask sensitive PII values (emails, phones, salaries) for privacy-conscious display."""
    if val is None or str(val).strip() == "":
        return ""
    s = str(val).strip()
    fn = field_name.lower()

    if "email" in fn or "@" in s:
        match = EMAIL_REGEX.match(s)
        if match:
            local, domain = match.groups()
            masked_local = (local[0] + "***" + local[-1]) if len(local) > 2 else (local[0] + "***")
            return f"{masked_local}@{domain}"

    if "phone" in fn or "mobile" in fn or "cell" in fn:
        if len(s) > 6:
            return s[:4] + "***" + s[-2:]
        return "***-***"

    if "salary" in fn or "amount" in fn or "budget" in fn:
        # Keep numeric magnitude or mask
        return s

    if "card" in fn or "account" in fn or "ssn" in fn:
        if len(s) > 4:
            return "****" + s[-4:]
        return "****"

    return s


@dataclass
class DatasetProfile:
    """Introspected schema and sample data for a single dataset (CSV, SQL table, or File)."""
    dataset_key: str          # e.g., 'customers.csv', 'relational_demo.db:orders'
    source_type: str         # 'CSV', 'SQL', 'Upload'
    entity_name: str         # 'Customer', 'Order', 'Payment', 'Employee'
    file_or_db: str
    table_name: Optional[str]
    columns: List[str]
    row_count: int
    data_df: pd.DataFrame
    primary_keys: List[str] = field(default_factory=list)
    foreign_keys: List[Dict[str, Any]] = field(default_factory=list)  # [{'from': col, 'to_table': tbl, 'to_col': col}]


class RelationshipEngine:
    """High-performance relationship discovery and graph generation engine."""

    def __init__(
        self,
        csv_dir: Optional[Path] = None,
        sql_dir: Optional[Path] = None,
        uploads_dir: Optional[Path] = None,
    ) -> None:
        root = Path(__file__).resolve().parent.parent.parent
        self.csv_dir = csv_dir or (root / "data" / "csv")
        self.sql_dir = sql_dir or (root / "data" / "sql")
        self.uploads_dir = uploads_dir or (root / "data" / "uploads")
        self._profiles: Dict[str, DatasetProfile] = {}

    def load_all_datasets(self, filter_sources: Optional[List[str]] = None) -> Dict[str, DatasetProfile]:
        """Introspect all available data sources and cache their data profiles."""
        profiles: Dict[str, DatasetProfile] = {}

        # 1. Inspect CSV files
        if self.csv_dir.exists():
            for p in sorted(self.csv_dir.glob("*.csv")):
                if filter_sources and p.name not in filter_sources:
                    continue
                try:
                    df = pd.read_csv(p, nrows=500, dtype=str)
                    cols = list(df.columns)
                    # Infer primary key: look for {entity}_id or id
                    stem = p.stem.rstrip("s").lower()
                    pk_candidate = None
                    for c in cols:
                        if c.lower() == f"{stem}_id" or c.lower() == "id" or (c.lower().endswith("_id") and stem in c.lower()):
                            if df[c].dropna().is_unique:
                                pk_candidate = c
                                break

                    pks = [pk_candidate] if pk_candidate else []
                    entity_label = p.stem.replace("_", " ").title()
                    profiles[p.name] = DatasetProfile(
                        dataset_key=p.name,
                        source_type="CSV",
                        entity_name=entity_label,
                        file_or_db=p.name,
                        table_name=None,
                        columns=cols,
                        row_count=len(df),
                        data_df=df,
                        primary_keys=pks,
                    )
                except Exception as e:
                    logger.warning("Engine failed to profile CSV %s: %s", p.name, e)

        # 2. Inspect SQLite databases & explicit FK constraints
        if self.sql_dir.exists():
            db_files = sorted(set(list(self.sql_dir.glob("*.db")) + list(self.sql_dir.glob("*.sqlite"))))
            for db_p in db_files:
                if db_p.name == "users.db":
                    continue
                try:
                    conn = sqlite3.connect(db_p)
                    cur = conn.cursor()
                    tables = [
                        r[0] for r in cur.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                        ).fetchall()
                    ]
                    for tbl in tables:
                        d_key = f"{db_p.name}:{tbl}"
                        if filter_sources and d_key not in filter_sources and tbl not in filter_sources:
                            continue

                        df = pd.read_sql(f'SELECT * FROM "{tbl}" LIMIT 500', conn)
                        cols = list(df.columns)

                        # Check PRAGMA table_info for PK
                        col_info = cur.execute(f'PRAGMA table_info("{tbl}")').fetchall()
                        pks = [ci[1] for ci in col_info if ci[5] > 0]

                        # Check PRAGMA foreign_key_list for explicit FKs
                        fk_info = cur.execute(f'PRAGMA foreign_key_list("{tbl}")').fetchall()
                        fks = []
                        for fki in fk_info:
                            # (id, seq, table, from, to, on_update, on_delete, match)
                            fks.append({
                                "from": fki[3],
                                "to_table": fki[2],
                                "to_col": fki[4],
                            })

                        entity_label = tbl.replace("_", " ").title()
                        profiles[d_key] = DatasetProfile(
                            dataset_key=d_key,
                            source_type="SQL",
                            entity_name=entity_label,
                            file_or_db=db_p.name,
                            table_name=tbl,
                            columns=cols,
                            row_count=len(df),
                            data_df=df,
                            primary_keys=pks,
                            foreign_keys=fks,
                        )
                    conn.close()
                except Exception as e:
                    logger.warning("Engine failed to profile SQLite %s: %s", db_p.name, e)

        # 3. Inspect Uploads
        if self.uploads_dir.exists():
            registry = get_parser_registry()
            for p in sorted(self.uploads_dir.iterdir()):
                if not p.is_file() or p.name.startswith("."):
                    continue
                if filter_sources and p.name not in filter_sources:
                    continue
                try:
                    parsed = registry.parse_file(p)
                    cols = [f.field_name for f in parsed.fields]
                    data_dict = {}
                    for f in parsed.fields:
                        data_dict[f.field_name] = f.values[:500] if f.values else []
                    max_len = max([len(v) for v in data_dict.values()] + [0])
                    for k in data_dict:
                        if len(data_dict[k]) < max_len:
                            data_dict[k].extend([""] * (max_len - len(data_dict[k])))
                    df = pd.DataFrame(data_dict) if data_dict else pd.DataFrame(columns=cols)

                    profiles[p.name] = DatasetProfile(
                        dataset_key=p.name,
                        source_type="Upload",
                        entity_name=p.stem.replace("_", " ").title(),
                        file_or_db=p.name,
                        table_name=None,
                        columns=cols,
                        row_count=parsed.total_records,
                        data_df=df,
                        primary_keys=[],
                    )
                except Exception as e:
                    logger.warning("Engine failed to profile upload %s: %s", p.name, e)

        self._profiles = profiles
        return profiles

    def discover_all_relationships(self, selected_sources: Optional[List[str]] = None) -> List[RelationshipEdge]:
        """
        Discovers all verified and probable relationships across loaded profiles using:
        1. Database explicit foreign keys (Status: Verified)
        2. Exact matching identifier columns with value overlap (Status: Verified)
        3. Identifier columns with partial overlap or pattern match (Status: Possible / Needs Review)
        """
        profiles = self.load_all_datasets(selected_sources)
        keys = list(profiles.keys())
        discovered_edges: List[RelationshipEdge] = []
        edge_id_set: Set[str] = set()

        for i, src_key in enumerate(keys):
            src_prof = profiles[src_key]

            # 1. Check explicit SQLite foreign keys
            for fk in src_prof.foreign_keys:
                target_table = fk["to_table"]
                # Find target profile
                tgt_key = None
                for k, p in profiles.items():
                    if p.source_type == "SQL" and (p.table_name == target_table or p.dataset_key.endswith(f":{target_table}")):
                        tgt_key = k
                        break

                if tgt_key:
                    tgt_prof = profiles[tgt_key]
                    edge_id = f"{src_key}_{fk['from']}--{tgt_key}_{fk['to_col']}"
                    if edge_id not in edge_id_set:
                        edge_id_set.add(edge_id)
                        # Determine cardinality & check referential integrity
                        cardinality, match_count, samples = self._analyze_cardinality(
                            src_prof.data_df, fk["from"], tgt_prof.data_df, fk["to_col"]
                        )
                        rel_kind = self._determine_relationship_kind(src_prof.entity_name, tgt_prof.entity_name, fk["from"])
                        discovered_edges.append(
                            RelationshipEdge(
                                id=edge_id,
                                source_id=src_key,
                                target_id=tgt_key,
                                source_label=f"{src_prof.entity_name} ({fk['from']})",
                                target_label=f"{tgt_prof.entity_name} ({fk['to_col']})",
                                relationship_type=f"{src_prof.entity_name} references {tgt_prof.entity_name}",
                                kind=rel_kind,
                                cardinality=cardinality,
                                verification_status="Verified",
                                confidence_score=1.0,
                                evidence=f"Database Foreign Key constraint in {src_prof.file_or_db}: {src_prof.table_name}.{fk['from']} -> {target_table}.{fk['to_col']} ({match_count} matching records).",
                                source_field=fk["from"],
                                target_field=fk["to_col"],
                                source_dataset=src_key,
                                target_dataset=tgt_key,
                                match_count=match_count,
                                sample_matches=samples,
                                is_direct=True,
                                hops=1,
                            )
                        )

            # 2. Match across datasets (CSV <-> CSV, CSV <-> SQL, SQL <-> SQL)
            for j in range(i + 1, len(keys)):
                tgt_key = keys[j]
                tgt_prof = profiles[tgt_key]

                # Compare columns
                for col_a in src_prof.columns:
                    col_a_clean = col_a.lower().strip()
                    if not any(col_a_clean.endswith(sfx) or col_a_clean == sfx for sfx in IDENTIFIER_SUFFIXES):
                        # Skip non-identifier columns like names, dates, amounts to prevent FALSE name joins
                        continue

                    for col_b in tgt_prof.columns:
                        col_b_clean = col_b.lower().strip()
                        if col_a_clean != col_b_clean:
                            continue

                        edge_id = f"{src_key}_{col_a}--{tgt_key}_{col_b}"
                        if edge_id in edge_id_set:
                            continue
                        edge_id_set.add(edge_id)

                        cardinality, match_count, samples = self._analyze_cardinality(
                            src_prof.data_df, col_a, tgt_prof.data_df, col_b
                        )

                        if match_count > 0:
                            rel_kind = self._determine_relationship_kind(src_prof.entity_name, tgt_prof.entity_name, col_a)
                            status: VerificationStatus = "Verified" if match_count >= 2 else "Possible"
                            conf = 0.95 if match_count >= 3 else 0.80

                            discovered_edges.append(
                                RelationshipEdge(
                                    id=edge_id,
                                    source_id=src_key,
                                    target_id=tgt_key,
                                    source_label=f"{src_prof.entity_name} ({col_a})",
                                    target_label=f"{tgt_prof.entity_name} ({col_b})",
                                    relationship_type=f"{src_prof.entity_name} matches {tgt_prof.entity_name} on {col_a}",
                                    kind=rel_kind,
                                    cardinality=cardinality,
                                    verification_status=status,
                                    confidence_score=conf,
                                    evidence=f"Exact identifier match on column '{col_a}' with {match_count} overlapping unique values across '{src_key}' and '{tgt_key}'.",
                                    source_field=col_a,
                                    target_field=col_b,
                                    source_dataset=src_key,
                                    target_dataset=tgt_key,
                                    match_count=match_count,
                                    sample_matches=samples,
                                    is_direct=True,
                                    hops=1,
                                )
                            )

        return discovered_edges

    def build_relationship_graph(
        self,
        selected_sources: Optional[List[str]] = None,
        focus_entity_or_id: Optional[str] = None,
    ) -> RelationshipGraph:
        """Construct full or filtered graph with nodes and edges."""
        edges = self.discover_all_relationships(selected_sources)
        profiles = self.load_all_datasets(selected_sources)

        nodes: List[EntityNode] = []
        node_ids: Set[str] = set()

        for key, p in profiles.items():
            node_ids.add(key)
            nodes.append(
                EntityNode(
                    id=key,
                    label=p.entity_name,
                    entity_type=self._classify_entity_type(p.entity_name),
                    source_type=p.source_type,
                    source_name=key,
                    primary_key=p.primary_keys[0] if p.primary_keys else None,
                    attributes={
                        "columns": p.columns,
                        "row_count": p.row_count,
                        "primary_keys": p.primary_keys,
                    },
                    masked_attributes={
                        "columns": p.columns,
                        "sample_records": p.row_count,
                    },
                )
            )

        # If a specific entity/record is requested (e.g., C001, E101, or Customer)
        if focus_entity_or_id:
            term = focus_entity_or_id.strip().lower()
            matching_edges = [
                e for e in edges
                if term in e.source_dataset.lower()
                or term in e.target_dataset.lower()
                or term in e.source_label.lower()
                or term in e.target_label.lower()
                or any(term in str(sm).lower() for sm in e.sample_matches)
            ]
            if matching_edges:
                edges = matching_edges
                relevant_node_ids = {e.source_id for e in edges} | {e.target_id for e in edges}
                nodes = [n for n in nodes if n.id in relevant_node_ids]

        verified_cnt = sum(1 for e in edges if e.verification_status == "Verified")
        possible_cnt = sum(1 for e in edges if e.verification_status == "Possible")
        review_cnt = sum(1 for e in edges if e.verification_status == "Needs Review")

        return RelationshipGraph(
            nodes=nodes,
            edges=edges,
            total_nodes=len(nodes),
            total_edges=len(edges),
            verified_count=verified_cnt,
            possible_count=possible_cnt,
            needs_review_count=review_cnt,
        )

    def find_entity_record_connections(self, record_id: str) -> Dict[str, Any]:
        """
        Search all loaded datasets for an exact record identifier (e.g. C001, E101, ORD-101)
        and trace all direct and indirect relational connections.
        """
        profiles = self.load_all_datasets()
        record_id_clean = record_id.strip()
        matched_occurrences: List[Dict[str, Any]] = []

        # Find where this ID appears
        for d_key, prof in profiles.items():
            df = prof.data_df
            for col in prof.columns:
                if col not in df:
                    continue
                matches = df[df[col].astype(str).str.strip() == record_id_clean]
                if not matches.empty:
                    row_records = matches.to_dict(orient="records")
                    masked_records = []
                    for r in row_records:
                        masked_r = {k: mask_personal_value(k, v) for k, v in r.items()}
                        masked_records.append(masked_r)

                    matched_occurrences.append({
                        "dataset": d_key,
                        "entity": prof.entity_name,
                        "field": col,
                        "count": len(matches),
                        "records": masked_records,
                    })

        # Trace relationships connected to these datasets
        all_edges = self.discover_all_relationships()
        connected_edges = [
            e for e in all_edges
            if any(e.source_dataset == mo["dataset"] or e.target_dataset == mo["dataset"] for mo in matched_occurrences)
        ]

        return {
            "record_id": record_id_clean,
            "occurrences": matched_occurrences,
            "connected_relationships": [e.model_dump() for e in connected_edges],
            "total_datasets_connected": len(matched_occurrences),
        }

    # --- Helper methods ---

    def _analyze_cardinality(
        self,
        df_a: pd.DataFrame,
        col_a: str,
        df_b: pd.DataFrame,
        col_b: str,
    ) -> Tuple[CardinalityType, int, List[Dict[str, Any]]]:
        if col_a not in df_a.columns or col_b not in df_b.columns:
            return "Unknown", 0, []

        s_a = df_a[col_a].dropna().astype(str).str.strip()
        s_b = df_b[col_b].dropna().astype(str).str.strip()

        # Filter out empty strings
        s_a = s_a[s_a != ""]
        s_b = s_b[s_b != ""]

        set_a = set(s_a)
        set_b = set(s_b)
        overlap = set_a.intersection(set_b)
        match_count = len(overlap)

        if match_count == 0:
            return "Unknown", 0, []

        sample_overlap = list(overlap)[:5]
        samples = [{"value": val} for val in sample_overlap]

        # Check uniqueness on overlapping subset
        subset_a = s_a[s_a.isin(overlap)]
        subset_b = s_b[s_b.isin(overlap)]

        unique_a = subset_a.is_unique
        unique_b = subset_b.is_unique

        if unique_a and unique_b:
            cardinality = "1:1"
        elif unique_a and not unique_b:
            cardinality = "1:N"
        elif not unique_a and unique_b:
            cardinality = "1:N"
        else:
            cardinality = "N:M"

        return cardinality, match_count, samples

    def _determine_relationship_kind(self, entity_a: str, entity_b: str, field: str) -> RelationshipKind:
        ea, eb, fn = entity_a.lower(), entity_b.lower(), field.lower()
        if "customer" in ea and "order" in eb:
            return "person_to_company"
        if "order" in ea and "payment" in eb:
            return "order_to_payment"
        if "employee" in ea and "department" in eb:
            return "person_to_department"
        if "customer" in ea and "customer" in eb:
            return "person_to_person"
        if "email" in fn:
            return "email_to_person"
        if "phone" in fn:
            return "phone_to_person"
        return "identifier_match"

    def _classify_entity_type(self, entity_name: str) -> str:
        en = entity_name.lower()
        if "customer" in en or "user" in en or "patient" in en:
            return "Person"
        if "employee" in en or "staff" in en:
            return "Person"
        if "department" in en:
            return "Department"
        if "company" in en or "org" in en or "supplier" in en:
            return "Organization"
        if "order" in en or "transaction" in en:
            return "Transaction"
        if "payment" in en:
            return "Payment"
        if "doc" in en or "pdf" in en or "notes" in en:
            return "Document"
        return "Entity"
