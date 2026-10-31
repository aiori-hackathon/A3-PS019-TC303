"""
backend/lineage/ledger.py
=========================
SHA-256 Cryptographic Evidence Integrity Ledger for PrivSight Phase 5.1.

Implements an append-only, verifiable hash chain:
- Each evidence record is bound to its predecessor via SHA-256.
- Prevents silent alteration, tampering, or deletion of compliance proof.
- Provides full integrity verification from Genesis block to Tip.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from backend.auth.db import get_db_connection
from backend.lineage.models import EvidenceLedgerEntry, LedgerVerificationResult

logger = logging.getLogger("privsight.lineage.ledger")

GENESIS_HASH = hashlib.sha256(b"PRIVSIGHT_EVIDENCE_LEDGER_GENESIS_2026").hexdigest()


def init_lineage_tables(db_path: Optional[Path] = None) -> None:
    """Creates the append-only evidence ledger and egress tracking tables safely and idempotently."""
    conn = get_db_connection(db_path)
    try:
        with conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS evidence_chain_ledger (
                    id TEXT PRIMARY KEY,
                    sequence INTEGER UNIQUE NOT NULL,
                    timestamp TEXT NOT NULL,
                    source_ref TEXT NOT NULL,
                    target_ref TEXT NOT NULL,
                    evidence_type TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    proof_details TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    current_hash TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS data_egress_events (
                    id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    operation_type TEXT NOT NULL,
                    source_dataset TEXT NOT NULL,
                    source_table TEXT,
                    source_column TEXT NOT NULL,
                    destination_dataset TEXT NOT NULL,
                    destination_type TEXT NOT NULL,
                    entity_name TEXT NOT NULL,
                    record_count INTEGER NOT NULL,
                    evidence TEXT NOT NULL,
                    verification_status TEXT NOT NULL,
                    pii_classes TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_ledger_seq ON evidence_chain_ledger(sequence);
                CREATE INDEX IF NOT EXISTS idx_ledger_src_tgt ON evidence_chain_ledger(source_ref, target_ref);
                CREATE INDEX IF NOT EXISTS idx_egress_ts ON data_egress_events(timestamp);
                CREATE INDEX IF NOT EXISTS idx_egress_src ON data_egress_events(source_dataset, source_column);
                """
            )
    finally:
        conn.close()


def compute_evidence_hash(
    sequence: int,
    timestamp: str,
    source_ref: str,
    target_ref: str,
    evidence_type: str,
    verification_status: str,
    confidence: float,
    proof_details: str,
    previous_hash: str,
) -> str:
    """Calculates deterministic SHA-256 digest over evidence payload and predecessor hash."""
    canonical_payload = (
        f"{sequence}|{timestamp}|{source_ref.strip()}|{target_ref.strip()}|"
        f"{evidence_type.strip()}|{verification_status.strip()}|"
        f"{confidence:.4f}|{proof_details.strip()}|{previous_hash}"
    )
    return hashlib.sha256(canonical_payload.encode("utf-8")).hexdigest()


class EvidenceIntegrityLedger:
    """Manages appending and verifying cryptographically linked evidence blocks."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path
        init_lineage_tables(self.db_path)

    def _conn(self) -> sqlite3.Connection:
        return get_db_connection(self.db_path)

    def record_evidence(
        self,
        source_ref: str,
        target_ref: str,
        evidence_type: str,
        verification_status: str,
        confidence: float,
        proof_details: str,
        timestamp: Optional[str] = None,
    ) -> EvidenceLedgerEntry:
        """
        Appends a new verified evidence record to the hash chain.
        Retrieves the tip block to establish the link.
        """
        conn = self._conn()
        try:
            now_iso = timestamp or datetime.now(timezone.utc).isoformat()
            with conn:
                cur = conn.cursor()
                cur.execute(
                    "SELECT sequence, current_hash FROM evidence_chain_ledger ORDER BY sequence DESC LIMIT 1"
                )
                last_row = cur.fetchone()

                if last_row:
                    next_seq = int(last_row["sequence"]) + 1
                    prev_hash = str(last_row["current_hash"])
                else:
                    next_seq = 1
                    prev_hash = GENESIS_HASH

                curr_hash = compute_evidence_hash(
                    sequence=next_seq,
                    timestamp=now_iso,
                    source_ref=source_ref,
                    target_ref=target_ref,
                    evidence_type=evidence_type,
                    verification_status=verification_status,
                    confidence=confidence,
                    proof_details=proof_details,
                    previous_hash=prev_hash,
                )

                entry_id = f"ev-{uuid.uuid4().hex[:12]}"
                conn.execute(
                    """
                    INSERT INTO evidence_chain_ledger (
                        id, sequence, timestamp, source_ref, target_ref,
                        evidence_type, verification_status, confidence,
                        proof_details, previous_hash, current_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry_id,
                        next_seq,
                        now_iso,
                        source_ref,
                        target_ref,
                        evidence_type,
                        verification_status,
                        confidence,
                        proof_details,
                        prev_hash,
                        curr_hash,
                    ),
                )

                return EvidenceLedgerEntry(
                    id=entry_id,
                    sequence=next_seq,
                    timestamp=now_iso,
                    source_ref=source_ref,
                    target_ref=target_ref,
                    evidence_type=evidence_type,
                    verification_status=verification_status,
                    confidence=confidence,
                    proof_details=proof_details,
                    previous_hash=prev_hash,
                    current_hash=curr_hash,
                )
        finally:
            conn.close()

    def verify_ledger_integrity(self) -> LedgerVerificationResult:
        """
        Audits the entire evidence ledger from Genesis to Tip.
        Recomputes all SHA-256 hashes and verifies predecessor chaining.
        Flags any modified, deleted, or out-of-order records.
        """
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM evidence_chain_ledger ORDER BY sequence ASC"
            )
            rows = cur.fetchall()

            total_count = len(rows)
            now_iso = datetime.now(timezone.utc).isoformat()

            if total_count == 0:
                return LedgerVerificationResult(
                    is_valid=True,
                    total_entries=0,
                    verified_entries=0,
                    genesis_hash=GENESIS_HASH,
                    tip_hash=GENESIS_HASH,
                    tampered_entries=[],
                    verification_message="Evidence ledger is clean and empty (Genesis initialized).",
                    verified_at=now_iso,
                )

            expected_prev = GENESIS_HASH
            tampered_seqs: List[int] = []
            verified_count = 0

            for row in rows:
                seq = row["sequence"]
                actual_prev = row["previous_hash"]
                actual_curr = row["current_hash"]

                # 1. Verify chain continuity
                if actual_prev != expected_prev:
                    tampered_seqs.append(seq)
                    expected_prev = actual_curr
                    continue

                # 2. Recompute expected hash for this block
                recomputed = compute_evidence_hash(
                    sequence=seq,
                    timestamp=row["timestamp"],
                    source_ref=row["source_ref"],
                    target_ref=row["target_ref"],
                    evidence_type=row["evidence_type"],
                    verification_status=row["verification_status"],
                    confidence=float(row["confidence"]),
                    proof_details=row["proof_details"],
                    previous_hash=actual_prev,
                )

                if recomputed != actual_curr:
                    tampered_seqs.append(seq)
                else:
                    verified_count += 1

                expected_prev = actual_curr

            is_valid = len(tampered_seqs) == 0
            tip = rows[-1]["current_hash"] if rows else GENESIS_HASH
            msg = (
                f"Ledger verified successfully: {verified_count}/{total_count} blocks valid."
                if is_valid
                else f"CRITICAL: Integrity failure / tampering detected in {len(tampered_seqs)} block(s): {tampered_seqs}."
            )

            return LedgerVerificationResult(
                is_valid=is_valid,
                total_entries=total_count,
                verified_entries=verified_count,
                genesis_hash=GENESIS_HASH,
                tip_hash=tip,
                tampered_entries=tampered_seqs,
                verification_message=msg,
                verified_at=now_iso,
            )
        finally:
            conn.close()

    def get_ledger_history(self, limit: int = 100) -> List[EvidenceLedgerEntry]:
        """Retrieves most recent ledger entries in reverse chronological order."""
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                "SELECT * FROM evidence_chain_ledger ORDER BY sequence DESC LIMIT ?",
                (limit,),
            )
            rows = cur.fetchall()
            return [
                EvidenceLedgerEntry(
                    id=r["id"],
                    sequence=r["sequence"],
                    timestamp=r["timestamp"],
                    source_ref=r["source_ref"],
                    target_ref=r["target_ref"],
                    evidence_type=r["evidence_type"],
                    verification_status=r["verification_status"],
                    confidence=float(r["confidence"]),
                    proof_details=r["proof_details"],
                    previous_hash=r["previous_hash"],
                    current_hash=r["current_hash"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def get_evidence_for_field(self, field_key: str) -> List[EvidenceLedgerEntry]:
        """Finds all ledger blocks mentioning a specific dataset or column."""
        conn = self._conn()
        try:
            cur = conn.cursor()
            cur.execute(
                """
                SELECT * FROM evidence_chain_ledger
                WHERE source_ref LIKE ? OR target_ref LIKE ?
                ORDER BY sequence DESC
                """,
                (f"%{field_key}%", f"%{field_key}%"),
            )
            rows = cur.fetchall()
            return [
                EvidenceLedgerEntry(
                    id=r["id"],
                    sequence=r["sequence"],
                    timestamp=r["timestamp"],
                    source_ref=r["source_ref"],
                    target_ref=r["target_ref"],
                    evidence_type=r["evidence_type"],
                    verification_status=r["verification_status"],
                    confidence=float(r["confidence"]),
                    proof_details=r["proof_details"],
                    previous_hash=r["previous_hash"],
                    current_hash=r["current_hash"],
                )
                for r in rows
            ]
        finally:
            conn.close()


_LEDGER_INSTANCE: Optional[EvidenceIntegrityLedger] = None


def get_evidence_ledger() -> EvidenceIntegrityLedger:
    global _LEDGER_INSTANCE
    if _LEDGER_INSTANCE is None:
        _LEDGER_INSTANCE = EvidenceIntegrityLedger()
    return _LEDGER_INSTANCE
