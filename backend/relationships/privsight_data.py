"""
backend/relationships/privsight_data.py
======================================
Unified Data Integration Layer for PrivSight TRACERA Phase 2.

Integrates real data from all core PrivSight systems:
1. Personal Data Inventory (reports/evidence_inventory.json)
2. Scanned Database Metadata (CSV schemas, SQLite PRAGMA table_info & foreign_key_list, uploads)
3. Detection Rules (backend/config/rules.json: Identity, Contact, Financial, Location, Sensitive/Health)
4. Declared Metadata & Missing Proofs (backend/metadata/metadata.json: purpose, retention, gaps)
5. Ground Truth & Evaluation Results (reports/evaluation_summary.json)
6. Dynamic refresh capabilities ensuring newly scanned or uploaded data is immediately available.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from backend.parsers.registry import get_parser_registry

logger = logging.getLogger("privsight.relationships.data")

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
REPORTS_DIR = PROJECT_ROOT / "reports"
CONFIG_DIR = PROJECT_ROOT / "backend" / "config"
METADATA_DIR = PROJECT_ROOT / "backend" / "metadata"
DATA_DIR = PROJECT_ROOT / "data"


@dataclass
class TableInfo:
    """Introspected table or file metadata."""
    key: str                    # e.g. 'customers.csv', 'relational_demo.db:orders'
    entity_name: str            # e.g. 'Customer', 'Order', 'Payment'
    source_type: str            # 'CSV', 'SQL', 'Upload'
    file_or_db: str             # 'customers.csv', 'relational_demo.db'
    table_name: Optional[str]   # 'orders' or None
    columns: List[str]
    row_count: int
    primary_keys: List[str] = field(default_factory=list)
    foreign_keys: List[Dict[str, Any]] = field(default_factory=list)
    data_df: Optional[pd.DataFrame] = None


class PrivSightDataManager:
    """
    Unified, singleton-friendly data gateway connecting TRACERA
    directly to all actual PrivSight backend resources.
    """

    def __init__(
        self,
        csv_dir: Optional[Path] = None,
        sql_dir: Optional[Path] = None,
        uploads_dir: Optional[Path] = None,
        inventory_path: Optional[Path] = None,
        rules_path: Optional[Path] = None,
        metadata_path: Optional[Path] = None,
        eval_path: Optional[Path] = None,
    ) -> None:
        self.csv_dir = csv_dir or (DATA_DIR / "csv")
        self.sql_dir = sql_dir or (DATA_DIR / "sql")
        self.uploads_dir = uploads_dir or (DATA_DIR / "uploads")
        self.inventory_path = inventory_path or (REPORTS_DIR / "evidence_inventory.json")
        self.rules_path = rules_path or (CONFIG_DIR / "rules.json")
        self.metadata_path = metadata_path or (METADATA_DIR / "metadata.json")
        self.eval_path = eval_path or (REPORTS_DIR / "evaluation_summary.json")

        self.tables: Dict[str, TableInfo] = {}
        self.inventory_records: List[Dict[str, Any]] = []
        self.inventory_by_source_field: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self.inventory_by_class: Dict[str, List[Dict[str, Any]]] = {}
        self.gaps_records: List[Dict[str, Any]] = []
        self.detection_rules: Dict[str, Any] = {}
        self.declared_metadata: List[Dict[str, Any]] = []
        self.evaluation_summary: Dict[str, Any] = {}

        self.refresh()

    def refresh(self) -> None:
        """Reload all data dynamically from disk and databases."""
        self._load_tables_and_schemas()
        self._load_detection_rules()
        self._load_declared_metadata()
        self._load_inventory_and_gaps()
        self._load_evaluation_summary()
        logger.info(
            "PrivSightDataManager refreshed: %d tables, %d inventory records, %d gaps, %d rules",
            len(self.tables),
            len(self.inventory_records),
            len(self.gaps_records),
            len(self.detection_rules.get("classes", {})),
        )

    def _load_tables_and_schemas(self) -> None:
        """Introspect all CSV files, SQLite databases, and uploads."""
        tables: Dict[str, TableInfo] = {}

        # 1. CSV Files
        if self.csv_dir.exists():
            for p in sorted(self.csv_dir.glob("*.csv")):
                try:
                    df = pd.read_csv(p, nrows=500, dtype=str)
                    cols = list(df.columns)
                    stem = p.stem.rstrip("s").lower()
                    pk_candidate = None
                    for c in cols:
                        cl = c.lower()
                        if cl == f"{stem}_id" or cl == "id" or (cl.endswith("_id") and stem in cl):
                            if df[c].dropna().is_unique:
                                pk_candidate = c
                                break
                    pks = [pk_candidate] if pk_candidate else []
                    entity_label = p.stem.replace("_", " ").title()

                    tables[p.name] = TableInfo(
                        key=p.name,
                        entity_name=entity_label,
                        source_type="CSV",
                        file_or_db=p.name,
                        table_name=None,
                        columns=cols,
                        row_count=len(df),
                        primary_keys=pks,
                        data_df=df,
                    )
                except Exception as e:
                    logger.warning("Error reading CSV %s: %s", p.name, e)

        # 2. SQLite Databases
        if self.sql_dir.exists():
            db_files = sorted(set(list(self.sql_dir.glob("*.db")) + list(self.sql_dir.glob("*.sqlite"))))
            for db_p in db_files:
                if db_p.name == "users.db":
                    continue
                try:
                    conn = sqlite3.connect(db_p)
                    cur = conn.cursor()
                    table_names = [
                        r[0] for r in cur.execute(
                            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                        ).fetchall()
                    ]
                    for tbl in table_names:
                        d_key = f"{db_p.name}:{tbl}"
                        df = pd.read_sql(f'SELECT * FROM "{tbl}" LIMIT 500', conn)
                        cols = list(df.columns)

                        # PKs from PRAGMA table_info
                        col_info = cur.execute(f'PRAGMA table_info("{tbl}")').fetchall()
                        pks = [ci[1] for ci in col_info if ci[5] > 0]

                        # FKs from PRAGMA foreign_key_list
                        fk_info = cur.execute(f'PRAGMA foreign_key_list("{tbl}")').fetchall()
                        fks = []
                        for fki in fk_info:
                            fks.append({
                                "from": fki[3],
                                "to_table": fki[2],
                                "to_col": fki[4],
                            })

                        entity_label = tbl.replace("_", " ").title()
                        tables[d_key] = TableInfo(
                            key=d_key,
                            entity_name=entity_label,
                            source_type="SQL",
                            file_or_db=db_p.name,
                            table_name=tbl,
                            columns=cols,
                            row_count=len(df),
                            primary_keys=pks,
                            foreign_keys=fks,
                            data_df=df,
                        )
                    conn.close()
                except Exception as e:
                    logger.warning("Error reading SQLite %s: %s", db_p.name, e)

        # 3. Multi-format Uploads
        if self.uploads_dir.exists():
            registry = get_parser_registry()
            for p in sorted(self.uploads_dir.iterdir()):
                if not p.is_file() or p.name.startswith("."):
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

                    tables[p.name] = TableInfo(
                        key=p.name,
                        entity_name=p.stem.replace("_", " ").title(),
                        source_type="Upload",
                        file_or_db=p.name,
                        table_name=None,
                        columns=cols,
                        row_count=parsed.total_records,
                        data_df=df,
                    )
                except Exception as e:
                    logger.warning("Error reading Upload %s: %s", p.name, e)

        self.tables = tables

    def _load_detection_rules(self) -> None:
        """Load configured detection rules from rules.json."""
        if self.rules_path.exists():
            try:
                with open(self.rules_path, encoding="utf-8") as f:
                    self.detection_rules = json.load(f)
            except Exception as e:
                logger.warning("Error reading rules.json: %s", e)
                self.detection_rules = {}
        else:
            self.detection_rules = {}

    def _load_declared_metadata(self) -> None:
        """Load declared purposes and retention periods from metadata.json."""
        if self.metadata_path.exists():
            try:
                with open(self.metadata_path, encoding="utf-8") as f:
                    data = json.load(f)
                    self.declared_metadata = data.get("metadata", [])
            except Exception as e:
                logger.warning("Error reading metadata.json: %s", e)
                self.declared_metadata = []
        else:
            self.declared_metadata = []

    def _load_inventory_and_gaps(self) -> None:
        """Load evidence inventory and evidence gaps from evidence_inventory.json."""
        records: List[Dict[str, Any]] = []
        records_map: Dict[Tuple[str, str], Dict[str, Any]] = {}
        by_class: Dict[str, List[Dict[str, Any]]] = {}
        gaps: List[Dict[str, Any]] = []

        if self.inventory_path.exists():
            try:
                with open(self.inventory_path, encoding="utf-8") as f:
                    data = json.load(f)
                    records = data.get("inventory", [])
                    for r in records:
                        src = r.get("source_name", "")
                        fld = r.get("field_name", "")
                        records_map[(src, fld)] = r

                        cls_name = r.get("detected_class")
                        if cls_name:
                            by_class.setdefault(cls_name, []).append(r)

                        if r.get("overall_status") != "Complete":
                            gaps.append(r)
            except Exception as e:
                logger.warning("Error reading evidence_inventory.json: %s", e)

        self.inventory_records = records
        self.inventory_by_source_field = records_map
        self.inventory_by_class = by_class
        self.gaps_records = gaps

    def _load_evaluation_summary(self) -> None:
        """Load ground-truth evaluation results."""
        if self.eval_path.exists():
            try:
                with open(self.eval_path, encoding="utf-8") as f:
                    self.evaluation_summary = json.load(f)
            except Exception as e:
                logger.warning("Error reading evaluation_summary.json: %s", e)
                self.evaluation_summary = {}
        else:
            self.evaluation_summary = {}

    # --- Query Interface ---

    def get_all_tables(self) -> List[TableInfo]:
        """Return all active tables and dataset sources."""
        return list(self.tables.values())

    def get_table_info(self, source_name: str) -> Optional[TableInfo]:
        """Look up TableInfo by key (e.g. 'customers.csv' or 'relational_demo.db:customers')."""
        if source_name in self.tables:
            return self.tables[source_name]
        # Match by table_name or stem
        for k, t in self.tables.items():
            if t.table_name == source_name or k.endswith(f":{source_name}") or Path(k).stem == source_name:
                return t
        return None

    def find_tables_for_entity(self, entity_keyword: str) -> List[TableInfo]:
        """Find tables matching an entity concept (e.g. 'customer', 'employee', 'order', 'payment')."""
        ek = entity_keyword.lower().strip().rstrip("s")
        matches = []
        for k, t in self.tables.items():
            en = t.entity_name.lower()
            key_l = k.lower()
            tbl_l = (t.table_name or "").lower()
            if ek in en or ek in key_l or ek in tbl_l:
                matches.append(t)
        return matches

    def get_inventory_for_table(self, source_name: str) -> List[Dict[str, Any]]:
        """Get all personal-data inventory records for a specific table."""
        res = []
        tbl = self.get_table_info(source_name)
        target_keys = {source_name}
        if tbl:
            target_keys.add(tbl.key)
            if tbl.table_name:
                target_keys.add(tbl.table_name)
                target_keys.add(f"{tbl.file_or_db}:{tbl.table_name}")

        for r in self.inventory_records:
            if r.get("source_name") in target_keys:
                res.append(r)
        return res

    def get_inventory_record(self, source_name: str, field_name: str) -> Optional[Dict[str, Any]]:
        """Retrieve an exact inventory record for a source and field."""
        if (source_name, field_name) in self.inventory_by_source_field:
            return self.inventory_by_source_field[(source_name, field_name)]
        tbl = self.get_table_info(source_name)
        if tbl and (tbl.key, field_name) in self.inventory_by_source_field:
            return self.inventory_by_source_field[(tbl.key, field_name)]
        return None

    def find_fields_by_class(self, class_name: str) -> List[Dict[str, Any]]:
        """Get all fields classified under a specific privacy category (Identity, Contact, Financial, Location, Sensitive/Health)."""
        cn = class_name.strip()
        for k, v in self.inventory_by_class.items():
            if k.lower() == cn.lower():
                return v
        return []

    def find_fields_by_term(self, term: str) -> List[Dict[str, Any]]:
        """Search fields by keyword in column name (e.g. 'email', 'phone', 'salary', 'date_of_birth')."""
        t = term.lower().strip()
        matches = []
        for r in self.inventory_records:
            fn = r.get("field_name", "").lower()
            if t in fn or fn == t:
                matches.append(r)
        return matches

    def get_evidence_gaps(self, source_name: Optional[str] = None, field_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve Missing Proofs / evidence gaps with optional filtering."""
        if not source_name and not field_name:
            return self.gaps_records

        res = []
        for g in self.gaps_records:
            if source_name and g.get("source_name") != source_name:
                continue
            if field_name and g.get("field_name") != field_name:
                continue
            res.append(g)
        return res

    def get_declared_metadata(self, source_name: Optional[str] = None, field_name: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve declared metadata entries from metadata.json."""
        res = []
        for m in self.declared_metadata:
            if source_name and m.get("source_name") != source_name:
                continue
            if field_name and m.get("field_name") != field_name:
                continue
            res.append(m)
        return res

    def get_detection_rule(self, class_name: str) -> Optional[Dict[str, Any]]:
        """Look up detection rule specifications for a class."""
        classes = self.detection_rules.get("classes", {})
        for cn, rule in classes.items():
            if cn.lower() == class_name.lower():
                return {"class_name": cn, **rule}
        return None

    def get_summary_stats(self) -> Dict[str, Any]:
        """Return system-wide statistics for overview synthesis."""
        return {
            "total_tables": len(self.tables),
            "total_inventory_candidates": len(self.inventory_records),
            "total_evidence_gaps": len(self.gaps_records),
            "complete_metadata_count": sum(1 for r in self.inventory_records if r.get("overall_status") == "Complete"),
            "categories": {k: len(v) for k, v in self.inventory_by_class.items()},
            "evaluation": self.evaluation_summary.get("detection_metrics", {}),
        }


# Global singleton instance
_data_manager_instance: Optional[PrivSightDataManager] = None


def get_privsight_data_manager() -> PrivSightDataManager:
    """Access the global PrivSightDataManager instance."""
    global _data_manager_instance
    if _data_manager_instance is None:
        _data_manager_instance = PrivSightDataManager()
    return _data_manager_instance
