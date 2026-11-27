"""Deterministic local SIMULATED_CUSTODY reference authority.

This module is a test/reference implementation only. SQLite state, process-local
HMAC keys, and same-host filesystem durability do NOT provide independent
anti-rollback custody. An attacker able to restore/replace the complete DB and
its environment can roll this simulator back. Production must use a separately
administered authority with independently protected keys, journal, backups,
and monotonic state.

The simulator's atomic COMMIT is one SQLite transaction containing the floor,
transaction outcome, signed receipt, and append-only authenticated journal event.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sqlite3
import time
import uuid
from typing import Any, Callable, Mapping

CUSTODY_MODE = "SIMULATED_CUSTODY"
SCHEMA_VERSION = 1
CANONICALIZATION_VERSION = 1
DOMAIN_SEPARATOR = "JGA.SIMULATED_CUSTODY.RECEIPT.V1"
GENESIS_DIGEST = "0" * 64
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class ReceiptStatus(str, Enum):
    PREPARED = "PREPARED"
    COMMITTED = "COMMITTED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    RECOVERY_AUTHORIZED = "RECOVERY_AUTHORIZED"


class VerificationOutcome(str, Enum):
    VALID = "VALID"
    INVALID_SIGNATURE = "INVALID_SIGNATURE"
    WRONG_SCOPE = "WRONG_SCOPE"
    REVOKED_KEY = "REVOKED_KEY"
    STALE_EPOCH = "STALE_EPOCH"
    EXPIRED = "EXPIRED"
    WRONG_STATUS = "WRONG_STATUS"
    UNKNOWN_AUTHORITY = "UNKNOWN_AUTHORITY"
    INVALID_CANONICALIZATION = "INVALID_CANONICALIZATION"


class CustodyError(RuntimeError):
    """Base class for explicit custody refusal or integrity failures."""


class CustodyRejected(CustodyError):
    def __init__(self, reason_code: str, message: str = "custody request rejected"):
        super().__init__(f"{reason_code}: {message}")
        self.reason_code = reason_code


class CustodyConflict(CustodyRejected):
    pass


class CustodyUnavailable(CustodyError):
    pass


class CustodyIntegrityError(CustodyError):
    pass


class AmbiguousCommitError(CustodyUnavailable):
    """The caller did not receive the result; query the journal by transaction ID."""
    def __init__(self, transaction_id: str):
        super().__init__(f"COMMIT response ambiguous for transaction {transaction_id}")
        self.transaction_id = transaction_id


@dataclass(frozen=True)
class CheckpointCandidate:
    stream_id: str
    lineage_id: str
    generation: int
    sequence_no: int
    checkpoint_digest: str
    previous_checkpoint_digest: str
    recovery_authorization_id: str | None = None
    previous_lineage_id: str | None = None
    lineage_parent_id: str | None = None
    previous_generation: int | None = None
    target_generation: int | None = None

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PersistenceEvidence:
    transaction_id: str
    reservation_id: str
    checkpoint_digest: str
    artifact_bytes: bytes
    evidence_id: str
    evidence_kind: str = "SIMULATOR_READBACK_BYTES"


@dataclass(frozen=True)
class CustodyReceipt:
    schema_version: int
    canonicalization_version: int
    domain_separator: str
    receipt_id: str
    transaction_id: str
    reservation_id: str | None
    operation: str
    custody_state: str
    authority_id: str
    key_id: str
    authority_epoch: int
    policy_version: str
    signature_algorithm: str
    stream_id: str | None
    lineage_id: str | None
    generation: int | None
    sequence_no: int | None
    checkpoint_digest: str | None
    previous_checkpoint_digest: str | None
    lease_expires_at: float | None
    lease_policy_version: str | None
    previous_lineage_id: str | None
    lineage_parent_id: str | None
    previous_generation: int | None
    target_generation: int | None
    recovery_authorization_id: str | None
    issued_at: float
    custody_mode: str
    reason_code: str | None
    signature: str

    def payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("signature")
        return value

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CustodyReceipt":
        return cls(**dict(value))


@dataclass(frozen=True)
class FloorAttestation:
    authority_id: str
    authority_epoch: int
    custody_mode: str
    stream_id: str
    lineage_id: str | None
    generation: int | None
    sequence_no: int | None
    checkpoint_digest: str | None
    previous_checkpoint_digest: str | None
    receipt_id: str | None
    revoked_key_ids: tuple[str, ...]
    issued_at: float
    key_id: str
    signature_algorithm: str
    signature: str

    def payload(self) -> dict[str, Any]:
        value = asdict(self)
        value.pop("signature")
        return value


@dataclass(frozen=True)
class VerificationResult:
    outcome: VerificationOutcome
    valid: bool
    custody_mode: str
    reason: str


@dataclass(frozen=True)
class TransactionRecord:
    transaction_id: str
    status: str
    candidate: dict[str, Any]
    reservation_id: str | None
    lease_expires_at: float | None
    receipt: CustodyReceipt | None
    custody_mode: str


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


class SimulatedCustodyAuthority:
    """SQLite-backed deterministic authority with an explicit simulated label.

    `keys` must be supplied explicitly. HMAC-SHA256 is deliberately test-only;
    it is not a production public-key signature or independent key custody.
    `fault_injector(point)` may raise to simulate failures at transaction edges.
    """

    def __init__(
        self,
        database_path: str | os.PathLike[str],
        *,
        authority_id: str,
        keys: Mapping[str, bytes],
        active_key_id: str,
        clock: Callable[[], float] = time.time,
        lease_seconds: float = 60.0,
        policy_version: str = "simulated-policy-v1",
        lease_policy_version: str = "simulated-lease-v1",
        fault_injector: Callable[[str], None] | None = None,
    ) -> None:
        if not _ID.fullmatch(authority_id):
            raise ValueError("invalid authority_id")
        if active_key_id not in keys:
            raise ValueError("active_key_id must exist in keys")
        if not keys or any(not isinstance(k, bytes) or len(k) < 32 for k in keys.values()):
            raise ValueError("simulated HMAC keys must be explicit byte strings of at least 32 bytes")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        self.path = Path(database_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.authority_id = authority_id
        self._keys = dict(keys)
        self._initial_active_key_id = active_key_id
        self._clock = clock
        self.lease_seconds = float(lease_seconds)
        self.policy_version = policy_version
        self.lease_policy_version = lease_policy_version
        self.fault_injector = fault_injector
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.path), timeout=10.0, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA busy_timeout=10000")
        conn.execute("PRAGMA synchronous=FULL")
        conn.execute("PRAGMA journal_mode=DELETE")
        return conn

    def _initialize(self) -> None:
        existed = self.path.exists()
        conn = self._connect()
        try:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY, value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS floors (
                    stream_id TEXT PRIMARY KEY,
                    lineage_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    sequence_no INTEGER NOT NULL,
                    checkpoint_digest TEXT NOT NULL,
                    previous_checkpoint_digest TEXT NOT NULL,
                    authority_epoch INTEGER NOT NULL,
                    receipt_id TEXT NOT NULL,
                    transaction_id TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS transactions (
                    transaction_id TEXT PRIMARY KEY,
                    request_digest TEXT NOT NULL,
                    candidate_json TEXT NOT NULL,
                    stream_id TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    sequence_no INTEGER NOT NULL,
                    checkpoint_digest TEXT NOT NULL,
                    previous_checkpoint_digest TEXT NOT NULL,
                    reservation_id TEXT,
                    lease_expires_at REAL,
                    lease_policy_version TEXT,
                    status TEXT NOT NULL,
                    receipt_json TEXT,
                    updated_at REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS positions (
                    stream_id TEXT NOT NULL,
                    lineage_id TEXT NOT NULL,
                    generation INTEGER NOT NULL,
                    sequence_no INTEGER NOT NULL,
                    transaction_id TEXT NOT NULL,
                    checkpoint_digest TEXT NOT NULL,
                    PRIMARY KEY(stream_id,lineage_id,generation,sequence_no)
                );
                CREATE TABLE IF NOT EXISTS receipts (
                    receipt_id TEXT PRIMARY KEY,
                    transaction_id TEXT NOT NULL,
                    custody_state TEXT NOT NULL,
                    receipt_json TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS recovery_authorizations (
                    recovery_authorization_id TEXT PRIMARY KEY,
                    stream_id TEXT NOT NULL,
                    previous_lineage_id TEXT NOT NULL,
                    target_lineage_id TEXT NOT NULL,
                    lineage_parent_id TEXT NOT NULL,
                    previous_generation INTEGER NOT NULL,
                    target_generation INTEGER NOT NULL,
                    receipt_json TEXT NOT NULL,
                    consumed_by TEXT
                );
                CREATE TABLE IF NOT EXISTS revocations (
                    key_id TEXT PRIMARY KEY,
                    revoked_at REAL NOT NULL,
                    authority_epoch INTEGER NOT NULL,
                    reason_code TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS journal_events (
                    event_no INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    transaction_id TEXT,
                    payload_json TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    key_id TEXT NOT NULL,
                    mac TEXT NOT NULL
                );
            """)
            existing = conn.execute("SELECT value FROM meta WHERE key='authority_id'").fetchone()
            if existing is None:
                conn.execute("BEGIN IMMEDIATE")
                self._meta_set(conn, "authority_id", self.authority_id)
                self._meta_set(conn, "authority_epoch", "0")
                self._meta_set(conn, "active_key_id", self._initial_active_key_id)
                self._meta_set(conn, "authority_revoked", "0")
                self._meta_set(conn, "event_head", GENESIS_DIGEST)
                conn.commit()
            elif existing["value"] != self.authority_id:
                raise CustodyIntegrityError("database authority identity mismatch")
            else:
                active = self._meta_get(conn, "active_key_id")
                if active not in self._keys:
                    raise CustodyIntegrityError("active signing key is unavailable")
        finally:
            conn.close()
        if not existed and os.name != "nt":
            fd = os.open(self.path.parent, os.O_RDONLY)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
        try:
            os.chmod(self.path, 0o600)
        except OSError:
            pass

    @staticmethod
    def _meta_get(conn: sqlite3.Connection, key: str) -> str:
        row = conn.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        if row is None:
            raise CustodyIntegrityError(f"missing custody metadata: {key}")
        return str(row["value"])

    @staticmethod
    def _meta_set(conn: sqlite3.Connection, key: str, value: str) -> None:
        conn.execute("INSERT INTO meta(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, value))

    def _now(self) -> float:
        value = float(self._clock())
        if value < 0:
            raise ValueError("custody clock must return a non-negative timestamp")
        return value

    def _fault(self, point: str) -> None:
        if self.fault_injector is not None:
            self.fault_injector(point)

    def _active_key(self, conn: sqlite3.Connection) -> tuple[str, bytes, int]:
        if self._meta_get(conn, "authority_revoked") == "1":
            raise CustodyUnavailable("authority is revoked")
        key_id = self._meta_get(conn, "active_key_id")
        if conn.execute("SELECT 1 FROM revocations WHERE key_id=?", (key_id,)).fetchone():
            raise CustodyIntegrityError("active key is revoked")
        if key_id not in self._keys:
            raise CustodyUnavailable("active signing key unavailable")
        return key_id, self._keys[key_id], int(self._meta_get(conn, "authority_epoch"))

    def _sign(self, key: bytes, payload: Mapping[str, Any]) -> str:
        return hmac.new(key, canonical(payload), hashlib.sha256).hexdigest()

    def _make_receipt(
        self, conn: sqlite3.Connection, *, transaction_id: str,
        operation: str, custody_state: ReceiptStatus,
        candidate: CheckpointCandidate | None = None,
        reservation_id: str | None = None, lease_expires_at: float | None = None,
        recovery_authorization_id: str | None = None,
        reason_code: str | None = None, issued_at: float | None = None,
        key_override: tuple[str, bytes, int] | None = None,
        recovery_scope: Mapping[str, Any] | None = None,
    ) -> CustodyReceipt:
        key_id, key, epoch = key_override or self._active_key(conn)
        c = candidate
        r = dict(recovery_scope or {})
        unsigned = CustodyReceipt(
            schema_version=SCHEMA_VERSION,
            canonicalization_version=CANONICALIZATION_VERSION,
            domain_separator=DOMAIN_SEPARATOR,
            receipt_id=str(uuid.uuid4()),
            transaction_id=transaction_id,
            reservation_id=reservation_id,
            operation=operation,
            custody_state=custody_state.value,
            authority_id=self.authority_id,
            key_id=key_id,
            authority_epoch=epoch,
            policy_version=self.policy_version,
            signature_algorithm="HMAC-SHA256-TEST-ONLY",
            stream_id=c.stream_id if c else r.get("stream_id"),
            lineage_id=c.lineage_id if c else r.get("target_lineage_id"),
            generation=c.generation if c else r.get("target_generation"),
            sequence_no=c.sequence_no if c else None,
            checkpoint_digest=c.checkpoint_digest if c else None,
            previous_checkpoint_digest=c.previous_checkpoint_digest if c else r.get("previous_checkpoint_digest"),
            lease_expires_at=lease_expires_at,
            lease_policy_version=self.lease_policy_version if lease_expires_at is not None else None,
            previous_lineage_id=c.previous_lineage_id if c else r.get("previous_lineage_id"),
            lineage_parent_id=c.lineage_parent_id if c else r.get("lineage_parent_id"),
            previous_generation=c.previous_generation if c else r.get("previous_generation"),
            target_generation=c.target_generation if c else r.get("target_generation"),
            recovery_authorization_id=recovery_authorization_id or (c.recovery_authorization_id if c else None),
            issued_at=self._now() if issued_at is None else float(issued_at),
            custody_mode=CUSTODY_MODE,
            reason_code=reason_code,
            signature="",
        )
        return CustodyReceipt(**{**unsigned.as_dict(), "signature": self._sign(key, unsigned.payload())})

    def _store_receipt(self, conn: sqlite3.Connection, receipt: CustodyReceipt) -> None:
        raw = canonical(receipt.as_dict()).decode("utf-8")
        conn.execute(
            "INSERT INTO receipts(receipt_id,transaction_id,custody_state,receipt_json) VALUES(?,?,?,?)",
            (receipt.receipt_id, receipt.transaction_id, receipt.custody_state, raw),
        )

    def _append_event(self, conn: sqlite3.Connection, event_type: str, transaction_id: str | None, payload: Mapping[str, Any]) -> None:
        key_id, key, _ = self._active_key(conn)
        previous = self._meta_get(conn, "event_head")
        payload_json = canonical(dict(payload)).decode("utf-8")
        body = {
            "event_type": event_type, "transaction_id": transaction_id,
            "payload_json": payload_json, "previous_hash": previous,
            "key_id": key_id,
        }
        event_hash = sha256_hex(canonical(body))
        mac = hmac.new(key, canonical({**body, "event_hash": event_hash}), hashlib.sha256).hexdigest()
        conn.execute(
            "INSERT INTO journal_events(event_type,transaction_id,payload_json,previous_hash,event_hash,key_id,mac) VALUES(?,?,?,?,?,?,?)",
            (event_type, transaction_id, payload_json, previous, event_hash, key_id, mac),
        )
        self._meta_set(conn, "event_head", event_hash)

    def _verified_journal_events(self, conn: sqlite3.Connection) -> list[tuple[sqlite3.Row, dict[str, Any]]]:
        """Authenticate an ordered, gap-free, duplicate-free event chain."""
        previous = GENESIS_DIGEST
        seen_hashes: set[str] = set()
        seen_entries: set[tuple[str, str | None, str]] = set()
        verified: list[tuple[sqlite3.Row, dict[str, Any]]] = []
        rows = conn.execute("SELECT * FROM journal_events ORDER BY event_no").fetchall()
        for expected_no, row in enumerate(rows, start=1):
            if row["event_no"] != expected_no:
                raise CustodyIntegrityError("custody journal event sequence has a gap or reordering")
            if row["previous_hash"] != previous:
                raise CustodyIntegrityError("custody journal hash-chain discontinuity")
            body = {
                "event_type": row["event_type"],
                "transaction_id": row["transaction_id"],
                "payload_json": row["payload_json"],
                "previous_hash": row["previous_hash"],
                "key_id": row["key_id"],
            }
            event_hash = sha256_hex(canonical(body))
            key = self._keys.get(row["key_id"])
            if key is None:
                raise CustodyIntegrityError("custody journal signing key unavailable")
            expected = hmac.new(key, canonical({**body, "event_hash": event_hash}), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(event_hash, row["event_hash"]) or not hmac.compare_digest(expected, row["mac"]):
                raise CustodyIntegrityError("custody journal authentication failed")
            if event_hash in seen_hashes:
                raise CustodyIntegrityError("duplicate custody journal event hash")
            entry_identity = (row["event_type"], row["transaction_id"], row["payload_json"])
            if entry_identity in seen_entries:
                raise CustodyIntegrityError("duplicate custody journal event entry")
            try:
                payload = json.loads(row["payload_json"])
            except Exception as exc:
                raise CustodyIntegrityError("custody journal payload is not valid JSON") from exc
            if not isinstance(payload, dict):
                raise CustodyIntegrityError("custody journal payload must be an object")
            seen_hashes.add(event_hash)
            seen_entries.add(entry_identity)
            previous = event_hash
            verified.append((row, payload))
        if self._meta_get(conn, "event_head") != previous:
            raise CustodyIntegrityError("custody journal head does not match authenticated history")
        return verified

    def _verify_journal(self, conn: sqlite3.Connection) -> None:
        self._verified_journal_events(conn)

    def _verify_state(self, conn: sqlite3.Connection) -> None:
        """Reconstruct custody state from authenticated events and compare every mutable table."""
        events = self._verified_journal_events(conn)
        receipt_rows = conn.execute("SELECT * FROM receipts ORDER BY receipt_id").fetchall()
        receipts: dict[str, CustodyReceipt] = {}
        for row in receipt_rows:
            receipt = self._decode_receipt(row["receipt_json"])
            if receipt is None or receipt.receipt_id != row["receipt_id"]:
                raise CustodyIntegrityError("receipt history identity mismatch")
            if row["transaction_id"] != receipt.transaction_id or row["custody_state"] != receipt.custody_state:
                raise CustodyIntegrityError("receipt history metadata disagrees with signed receipt")
            if not self._verify_signature_only(receipt):
                raise CustodyIntegrityError("receipt history contains an unauthenticated receipt")
            if receipt.receipt_id in receipts:
                raise CustodyIntegrityError("duplicate receipt history identity")
            receipts[receipt.receipt_id] = receipt

        referenced_receipts: set[str] = set()
        latest_tx_receipt: dict[str, CustodyReceipt] = {}
        tx_status: dict[str, str] = {}
        tx_prepared_payload: dict[str, dict[str, Any]] = {}
        latest_committed: dict[str, dict[str, Any]] = {}
        recovery_events: dict[str, tuple[sqlite3.Row, dict[str, Any], CustodyReceipt]] = {}
        consumed_recoveries: dict[str, str] = {}
        recovery_commit_scopes: dict[str, tuple[str, dict[str, Any]]] = {}
        epoch = 0
        active_key_id = self._initial_active_key_id
        authority_revoked = False
        revoked: dict[str, dict[str, Any]] = {}

        state_events = {
            "PREPARED": ReceiptStatus.PREPARED.value,
            "PREPARE_REJECTED": ReceiptStatus.REJECTED.value,
            "COMMIT_REJECTED": ReceiptStatus.REJECTED.value,
            "RESERVATION_EXPIRED": ReceiptStatus.EXPIRED.value,
            "COMMIT_EXPIRED": ReceiptStatus.EXPIRED.value,
            "COMMITTED": ReceiptStatus.COMMITTED.value,
            "RECOVERY_AUTHORIZED": ReceiptStatus.RECOVERY_AUTHORIZED.value,
            "AUTHORITY_KEY_REVOKED": ReceiptStatus.COMMITTED.value,
            "AUTHORITY_REVOKED": ReceiptStatus.COMMITTED.value,
        }
        for row, payload in events:
            event_type = row["event_type"]
            txid = row["transaction_id"]
            receipt: CustodyReceipt | None = None
            receipt_id = payload.get("receipt_id")
            if receipt_id is not None:
                if not isinstance(receipt_id, str) or receipt_id in referenced_receipts:
                    raise CustodyIntegrityError("journal contains a duplicate or invalid receipt reference")
                receipt = receipts.get(receipt_id)
                if receipt is None:
                    raise CustodyIntegrityError("journal references a missing receipt-history record")
                if receipt.transaction_id != txid:
                    raise CustodyIntegrityError("journal receipt transaction binding mismatch")
                expected_status = state_events.get(event_type)
                if event_type == "COMMIT_REPLAY_REJECTED":
                    expected_status = ReceiptStatus.REJECTED.value
                if expected_status is None or receipt.custody_state != expected_status:
                    raise CustodyIntegrityError("journal event lifecycle does not match signed receipt status")
                referenced_receipts.add(receipt_id)
                transaction_state_event = event_type in (
                    "PREPARED", "COMMIT_REJECTED", "RESERVATION_EXPIRED",
                    "COMMIT_EXPIRED", "COMMITTED",
                )
                if transaction_state_event and txid is not None:
                    latest_tx_receipt[txid] = receipt
                    tx_status[txid] = expected_status
                if event_type == "PREPARED":
                    tx_prepared_payload[txid] = payload
                if event_type == "RECOVERY_AUTHORIZED":
                    auth_id = payload.get("recovery_authorization_id")
                    if not isinstance(auth_id, str) or auth_id in recovery_events:
                        raise CustodyIntegrityError("duplicate or invalid recovery authorization event")
                    recovery_events[auth_id] = (row, payload, receipt)

            elif event_type in state_events or event_type == "COMMIT_REPLAY_REJECTED":
                raise CustodyIntegrityError("state-changing journal event is missing its receipt reference")

            if event_type == "COMMITTED":
                required = (
                    "stream_id", "lineage_id", "generation", "sequence_no",
                    "checkpoint_digest", "previous_checkpoint_digest",
                )
                if any(field not in payload for field in required):
                    raise CustodyIntegrityError("committed event is missing checkpoint ordering fields")
                stream_id = payload["stream_id"]
                if not isinstance(stream_id, str):
                    raise CustodyIntegrityError("committed event has invalid stream identity")
                receipt = receipts.get(receipt_id)
                if receipt is None or (
                    receipt.stream_id != stream_id
                    or receipt.lineage_id != payload["lineage_id"]
                    or receipt.generation != payload["generation"]
                    or receipt.sequence_no != payload["sequence_no"]
                    or receipt.checkpoint_digest != payload["checkpoint_digest"]
                    or receipt.previous_checkpoint_digest != payload["previous_checkpoint_digest"]
                    or receipt.recovery_authorization_id != payload.get("recovery_authorization_id")
                    or receipt.previous_lineage_id != payload.get("previous_lineage_id")
                    or receipt.lineage_parent_id != payload.get("lineage_parent_id")
                    or receipt.previous_generation != payload.get("previous_generation")
                    or receipt.target_generation != payload.get("target_generation")
                ):
                    raise CustodyIntegrityError("committed event disagrees with its signed receipt")
                previous = latest_committed.get(stream_id)
                if previous is None:
                    valid_order = (
                        payload["generation"] == 0
                        and payload["sequence_no"] == 0
                        and payload["previous_checkpoint_digest"] == GENESIS_DIGEST
                        and payload.get("recovery_authorization_id") is None
                    )
                elif (
                    payload["lineage_id"] == previous["lineage_id"]
                    and payload["generation"] == previous["generation"]
                ):
                    valid_order = (
                        payload["sequence_no"] == previous["sequence_no"] + 1
                        and payload["previous_checkpoint_digest"] == previous["checkpoint_digest"]
                        and payload.get("recovery_authorization_id") is None
                    )
                else:
                    auth_id = payload.get("recovery_authorization_id")
                    valid_order = (
                        isinstance(auth_id, str)
                        and payload["generation"] > previous["generation"]
                        and payload["sequence_no"] == 0
                        and payload["previous_checkpoint_digest"] == previous["checkpoint_digest"]
                        and payload.get("previous_lineage_id") == previous["lineage_id"]
                        and payload.get("previous_generation") == previous["generation"]
                        and payload.get("target_generation") == payload["generation"]
                        and payload.get("lineage_parent_id") is not None
                    )
                    if valid_order:
                        if auth_id in consumed_recoveries:
                            raise CustodyIntegrityError("recovery authorization was consumed more than once")
                        consumed_recoveries[auth_id] = str(txid)
                        recovery_commit_scopes[auth_id] = (str(txid), payload)
                if not valid_order:
                    raise CustodyIntegrityError("committed checkpoint history is non-monotonic or has a broken chain link")
                latest_committed[stream_id] = {
                    "stream_id": stream_id,
                    "lineage_id": payload["lineage_id"],
                    "generation": payload["generation"],
                    "sequence_no": payload["sequence_no"],
                    "checkpoint_digest": payload["checkpoint_digest"],
                    "previous_checkpoint_digest": payload["previous_checkpoint_digest"],
                    "receipt_id": receipt_id,
                    "transaction_id": txid,
                    "authority_epoch": receipt.authority_epoch,
                }

            if event_type == "AUTHORITY_KEY_REVOKED":
                target = payload.get("target_key_id")
                new_active = payload.get("new_active_key_id")
                next_epoch = payload.get("authority_epoch")
                if (
                    not isinstance(target, str) or target in revoked
                    or next_epoch != epoch + 1
                    or not isinstance(new_active, str) or new_active not in self._keys
                    or new_active == target or new_active in revoked
                    or authority_revoked
                ):
                    raise CustodyIntegrityError("authority key transition is inconsistent or non-monotonic")
                if (
                    receipt is None or receipt.key_id != new_active
                    or receipt.authority_epoch != next_epoch
                    or payload.get("target_authority_id") is not None
                    or payload.get("authority_revoked") is not False
                ):
                    raise CustodyIntegrityError("authority key transition receipt binding mismatch")
                revoked[target] = {
                    "authority_epoch": next_epoch,
                    "reason_code": payload.get("reason"),
                    "revoked_at": payload.get("revoked_at"),
                }
                epoch = next_epoch
                active_key_id = new_active
            elif event_type == "AUTHORITY_REVOKED":
                next_epoch = payload.get("authority_epoch")
                if authority_revoked or next_epoch != epoch + 1:
                    raise CustodyIntegrityError("authority revocation epoch is inconsistent")
                if (
                    receipt is None or receipt.authority_epoch != next_epoch
                    or payload.get("target_authority_id") != self.authority_id
                    or payload.get("authority_revoked") is not True
                    or payload.get("new_active_key_id") != receipt.key_id
                ):
                    raise CustodyIntegrityError("authority revocation receipt binding mismatch")
                epoch = next_epoch
                active_key_id = payload.get("new_active_key_id")
                authority_revoked = True

        if set(receipts) != referenced_receipts:
            raise CustodyIntegrityError("receipt history contains orphaned or unreferenced records")

        transactions = conn.execute("SELECT * FROM transactions ORDER BY transaction_id").fetchall()
        transaction_ids = {tx["transaction_id"] for tx in transactions}
        if transaction_ids != set(latest_tx_receipt):
            raise CustodyIntegrityError("transaction table does not match authenticated lifecycle history")
        for tx in transactions:
            receipt = latest_tx_receipt[tx["transaction_id"]]
            if (
                tx["status"] != tx_status[tx["transaction_id"]]
                or self._decode_receipt(tx["receipt_json"]) != receipt
                or receipt.transaction_id != tx["transaction_id"]
                or receipt.custody_state != tx["status"]
            ):
                raise CustodyIntegrityError("transaction status/receipt authentication mismatch")
            prepared_payload = tx_prepared_payload.get(tx["transaction_id"])
            if prepared_payload is None:
                raise CustodyIntegrityError("transaction has no authenticated PREPARED event")
            candidate_json = canonical(prepared_payload.get("candidate")).decode("utf-8")
            if (
                tx["candidate_json"] != candidate_json
                or tx["reservation_id"] != prepared_payload.get("reservation_id")
                or tx["lease_expires_at"] != prepared_payload.get("lease_expires_at")
                or receipt.reservation_id != tx["reservation_id"]
            ):
                raise CustodyIntegrityError("transaction fields disagree with authenticated PREPARED event")
            position = conn.execute(
                "SELECT * FROM positions WHERE stream_id=? AND lineage_id=? AND generation=? AND sequence_no=?",
                (tx["stream_id"], tx["lineage_id"], tx["generation"], tx["sequence_no"]),
            ).fetchone()
            if (
                position is None
                or position["transaction_id"] != tx["transaction_id"]
                or position["checkpoint_digest"] != tx["checkpoint_digest"]
            ):
                raise CustodyIntegrityError("transaction position reservation binding mismatch")

        positions = conn.execute("SELECT * FROM positions").fetchall()
        if len(positions) != len(transactions):
            raise CustodyIntegrityError("position table contains missing or orphaned reservations")

        floors = conn.execute("SELECT * FROM floors").fetchall()
        if {floor["stream_id"] for floor in floors} != set(latest_committed):
            raise CustodyIntegrityError("floor table does not match committed journal streams")
        for floor in floors:
            latest = latest_committed[floor["stream_id"]]
            for field in (
                "lineage_id", "generation", "sequence_no", "checkpoint_digest",
                "previous_checkpoint_digest", "receipt_id", "transaction_id", "authority_epoch",
            ):
                if floor[field] != latest[field]:
                    raise CustodyIntegrityError("custody floor regresses or disagrees with latest committed journal state")

        authorization_rows = conn.execute("SELECT * FROM recovery_authorizations").fetchall()
        if {row["recovery_authorization_id"] for row in authorization_rows} != set(recovery_events):
            raise CustodyIntegrityError("recovery authorization table does not match authenticated events")
        for auth in authorization_rows:
            auth_id = auth["recovery_authorization_id"]
            _, payload, signed_receipt = recovery_events[auth_id]
            if (
                auth["stream_id"] != payload.get("stream_id")
                or auth["previous_lineage_id"] != payload.get("previous_lineage_id")
                or auth["target_lineage_id"] != payload.get("target_lineage_id")
                or auth["lineage_parent_id"] != payload.get("lineage_parent_id")
                or auth["previous_generation"] != payload.get("previous_generation")
                or auth["target_generation"] != payload.get("target_generation")
                or auth["stream_id"] != signed_receipt.stream_id
                or auth["previous_lineage_id"] != signed_receipt.previous_lineage_id
                or auth["target_lineage_id"] != signed_receipt.lineage_id
                or auth["lineage_parent_id"] != signed_receipt.lineage_parent_id
                or auth["previous_generation"] != signed_receipt.previous_generation
                or auth["target_generation"] != signed_receipt.target_generation
                or auth_id != signed_receipt.recovery_authorization_id
                or canonical(json.loads(auth["receipt_json"])) != canonical(signed_receipt.as_dict())
                or auth["consumed_by"] != consumed_recoveries.get(auth_id)
            ):
                raise CustodyIntegrityError("recovery authorization row disagrees with signed receipt or journal history")
            committed_scope = recovery_commit_scopes.get(auth_id)
            if committed_scope is not None:
                _, commit_payload = committed_scope
                if (
                    commit_payload.get("stream_id") != auth["stream_id"]
                    or commit_payload.get("lineage_id") != auth["target_lineage_id"]
                    or commit_payload.get("previous_lineage_id") != auth["previous_lineage_id"]
                    or commit_payload.get("lineage_parent_id") != auth["lineage_parent_id"]
                    or commit_payload.get("previous_generation") != auth["previous_generation"]
                    or commit_payload.get("target_generation") != auth["target_generation"]
                    or commit_payload.get("generation") != auth["target_generation"]
                    or commit_payload.get("sequence_no") != 0
                    or commit_payload.get("previous_checkpoint_digest") != signed_receipt.previous_checkpoint_digest
                ):
                    raise CustodyIntegrityError("committed recovery transition exceeds its signed authorization scope")

        revocation_rows = conn.execute("SELECT * FROM revocations").fetchall()
        if {row["key_id"] for row in revocation_rows} != set(revoked):
            raise CustodyIntegrityError("revocation table does not match authenticated authority history")
        for row in revocation_rows:
            expected = revoked[row["key_id"]]
            if (
                row["authority_epoch"] != expected["authority_epoch"]
                or row["reason_code"] != expected["reason_code"]
                or row["revoked_at"] != expected["revoked_at"]
            ):
                raise CustodyIntegrityError("revocation row disagrees with authenticated authority history")

        if (
            int(self._meta_get(conn, "authority_epoch")) != epoch
            or self._meta_get(conn, "active_key_id") != active_key_id
            or self._meta_get(conn, "authority_revoked") != ("1" if authority_revoked else "0")
        ):
            raise CustodyIntegrityError("authority metadata disagrees with authenticated journal history")
        if active_key_id in revoked:
            raise CustodyIntegrityError("authenticated authority state attempts to resurrect a revoked key")

    @staticmethod
    def _decode_receipt(raw: str | None) -> CustodyReceipt | None:
        if not raw:
            return None
        try:
            return CustodyReceipt.from_dict(json.loads(raw))
        except Exception as exc:
            raise CustodyIntegrityError("stored receipt cannot be decoded") from exc

    def _verify_signature_only(self, receipt: CustodyReceipt) -> bool:
        key = self._keys.get(receipt.key_id)
        if key is None:
            return False
        expected = self._sign(key, receipt.payload())
        return hmac.compare_digest(expected, receipt.signature)

    @staticmethod
    def _validate_candidate(candidate: CheckpointCandidate) -> None:
        if not isinstance(candidate, CheckpointCandidate):
            raise TypeError("candidate must be CheckpointCandidate")
        for name in ("stream_id", "lineage_id"):
            value = getattr(candidate, name)
            if not isinstance(value, str) or not _ID.fullmatch(value):
                raise ValueError(f"invalid {name}")
        if type(candidate.generation) is not int or candidate.generation < 0:
            raise ValueError("generation must be a non-negative integer")
        if type(candidate.sequence_no) is not int or candidate.sequence_no < 0:
            raise ValueError("sequence_no must be a non-negative integer")
        if not _HEX64.fullmatch(candidate.checkpoint_digest):
            raise ValueError("checkpoint_digest must be lowercase SHA-256 hex")
        if not _HEX64.fullmatch(candidate.previous_checkpoint_digest):
            raise ValueError("previous_checkpoint_digest must be lowercase SHA-256 hex")

    def _candidate_ordering(self, conn: sqlite3.Connection, candidate: CheckpointCandidate) -> None:
        floor = conn.execute("SELECT * FROM floors WHERE stream_id=?", (candidate.stream_id,)).fetchone()
        if floor is None:
            if candidate.generation != 0 or candidate.sequence_no != 0 or candidate.previous_checkpoint_digest != GENESIS_DIGEST:
                raise CustodyRejected("NO_RECOVERY_AUTH", "first checkpoint must begin at genesis generation/sequence")
            if candidate.recovery_authorization_id:
                raise CustodyRejected("WRONG_SCOPE", "genesis checkpoint cannot consume recovery authorization")
            return
        same_lineage = candidate.lineage_id == floor["lineage_id"]
        if same_lineage and candidate.generation == floor["generation"]:
            if candidate.sequence_no != floor["sequence_no"] + 1:
                raise CustodyRejected("NON_MONOTONIC_POSITION", "sequence must advance exactly one position")
            if candidate.previous_checkpoint_digest != floor["checkpoint_digest"]:
                raise CustodyRejected("CHAIN_LINK_MISMATCH", "previous checkpoint digest does not match current floor")
            if any((candidate.recovery_authorization_id, candidate.previous_lineage_id, candidate.lineage_parent_id,
                    candidate.previous_generation is not None, candidate.target_generation is not None)):
                raise CustodyRejected("UNEXPECTED_RECOVERY_FIELDS", "ordinary checkpoint cannot carry transition fields")
            return
        auth_id = candidate.recovery_authorization_id
        if not auth_id:
            raise CustodyRejected("NO_RECOVERY_AUTH", "generation or lineage transition requires recovery authorization")
        auth = conn.execute("SELECT * FROM recovery_authorizations WHERE recovery_authorization_id=?", (auth_id,)).fetchone()
        if auth is None or auth["consumed_by"] is not None:
            raise CustodyRejected("NO_RECOVERY_AUTH", "recovery authorization missing, unknown, or already consumed")
        auth_receipt = self._decode_receipt(auth["receipt_json"])
        if auth_receipt is None or not self._verify_signature_only(auth_receipt):
            raise CustodyRejected("NO_RECOVERY_AUTH", "recovery authorization receipt failed authentication")
        if auth_receipt.authority_epoch != int(self._meta_get(conn, "authority_epoch")):
            raise CustodyRejected("STALE_EPOCH", "recovery authorization belongs to a stale authority epoch")
        if conn.execute("SELECT 1 FROM revocations WHERE key_id=?", (auth_receipt.key_id,)).fetchone():
            raise CustodyRejected("REVOKED_KEY", "recovery authorization signing key is revoked")
        expected = (
            auth["stream_id"] == candidate.stream_id
            and auth["previous_lineage_id"] == floor["lineage_id"]
            and auth["target_lineage_id"] == candidate.lineage_id
            and auth["lineage_parent_id"] == candidate.lineage_parent_id
            and auth["previous_generation"] == floor["generation"]
            and auth["target_generation"] == candidate.generation
            and candidate.previous_lineage_id == floor["lineage_id"]
            and candidate.previous_generation == floor["generation"]
            and candidate.target_generation == candidate.generation
            and candidate.generation > floor["generation"]
            and candidate.sequence_no == 0
            and candidate.previous_checkpoint_digest == floor["checkpoint_digest"]
        )
        if not expected:
            raise CustodyRejected("WRONG_SCOPE", "recovery authorization does not bind this exact transition")

    def _rejection_receipt(self, conn: sqlite3.Connection, transaction_id: str, candidate: CheckpointCandidate,
                           reason_code: str) -> CustodyReceipt:
        receipt = self._make_receipt(conn, transaction_id=transaction_id, operation="prepare",
                                     custody_state=ReceiptStatus.REJECTED, candidate=candidate,
                                     reason_code=reason_code)
        self._store_receipt(conn, receipt)
        self._append_event(conn, "PREPARE_REJECTED", transaction_id, {"reason_code": reason_code, "candidate": candidate.as_dict(), "receipt_id": receipt.receipt_id})
        return receipt

    def prepare(self, candidate: CheckpointCandidate, transaction_id: str) -> CustodyReceipt:
        self._validate_candidate(candidate)
        if not isinstance(transaction_id, str) or not _ID.fullmatch(transaction_id):
            raise ValueError("invalid transaction_id")
        request_digest = sha256_hex(canonical(candidate.as_dict()))
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._verify_state(conn)
            existing = conn.execute("SELECT * FROM transactions WHERE transaction_id=?", (transaction_id,)).fetchone()
            if existing is not None:
                if existing["request_digest"] != request_digest:
                    receipt = self._rejection_receipt(conn, transaction_id, candidate, "TRANSACTION_ID_CONFLICT")
                    conn.commit()
                    raise CustodyConflict("TRANSACTION_ID_CONFLICT", "transaction ID reused with a different candidate digest")
                if existing["status"] == ReceiptStatus.PREPARED.value and existing["lease_expires_at"] <= self._now():
                    expired = self._make_receipt(conn, transaction_id=transaction_id, operation="prepare",
                        custody_state=ReceiptStatus.EXPIRED, candidate=candidate,
                        reservation_id=existing["reservation_id"], lease_expires_at=existing["lease_expires_at"],
                        reason_code="LEASE_EXPIRED")
                    conn.execute("UPDATE transactions SET status=?,receipt_json=?,updated_at=? WHERE transaction_id=?",
                                 (ReceiptStatus.EXPIRED.value, canonical(expired.as_dict()).decode(), self._now(), transaction_id))
                    self._store_receipt(conn, expired)
                    self._append_event(conn, "RESERVATION_EXPIRED", transaction_id, {"receipt_id": expired.receipt_id})
                    conn.commit()
                    return expired
                stored = self._decode_receipt(existing["receipt_json"])
                conn.commit()
                if stored is None:
                    raise CustodyIntegrityError("transaction journal receipt missing")
                return stored
            try:
                self._candidate_ordering(conn, candidate)
            except CustodyRejected as exc:
                receipt = self._rejection_receipt(conn, transaction_id, candidate, exc.reason_code)
                conn.commit()
                return receipt
            pos = conn.execute("SELECT * FROM positions WHERE stream_id=? AND lineage_id=? AND generation=? AND sequence_no=?",
                (candidate.stream_id, candidate.lineage_id, candidate.generation, candidate.sequence_no)).fetchone()
            if pos is not None:
                receipt = self._rejection_receipt(conn, transaction_id, candidate, "POSITION_ALREADY_RESERVED")
                conn.commit()
                return receipt
            reservation_id = str(uuid.uuid4())
            now = self._now()
            lease_expires_at = now + self.lease_seconds
            receipt = self._make_receipt(conn, transaction_id=transaction_id, operation="prepare",
                custody_state=ReceiptStatus.PREPARED, candidate=candidate,
                reservation_id=reservation_id, lease_expires_at=lease_expires_at, issued_at=now)
            conn.execute("INSERT INTO transactions(transaction_id,request_digest,candidate_json,stream_id,lineage_id,generation,sequence_no,checkpoint_digest,previous_checkpoint_digest,reservation_id,lease_expires_at,lease_policy_version,status,receipt_json,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (transaction_id, request_digest, canonical(candidate.as_dict()).decode(), candidate.stream_id,
                 candidate.lineage_id, candidate.generation, candidate.sequence_no, candidate.checkpoint_digest,
                 candidate.previous_checkpoint_digest, reservation_id, lease_expires_at, self.lease_policy_version,
                 ReceiptStatus.PREPARED.value, canonical(receipt.as_dict()).decode(), now))
            conn.execute("INSERT INTO positions(stream_id,lineage_id,generation,sequence_no,transaction_id,checkpoint_digest) VALUES(?,?,?,?,?,?)",
                (candidate.stream_id, candidate.lineage_id, candidate.generation, candidate.sequence_no, transaction_id, candidate.checkpoint_digest))
            self._store_receipt(conn, receipt)
            self._append_event(conn, "PREPARED", transaction_id, {"candidate": candidate.as_dict(), "reservation_id": reservation_id,
                "lease_expires_at": lease_expires_at, "receipt_id": receipt.receipt_id})
            self._fault("prepare.before_atomic_commit")
            conn.commit()
            return receipt
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    @staticmethod
    def _evidence_matches(tx: sqlite3.Row, transaction_id: str, reservation_id: str,
                          evidence: PersistenceEvidence) -> tuple[bool, str]:
        if tx["reservation_id"] != reservation_id or evidence.reservation_id != reservation_id:
            return False, "WRONG_RESERVATION"
        if evidence.transaction_id != transaction_id or evidence.checkpoint_digest != tx["checkpoint_digest"]:
            return False, "WRONG_EVIDENCE_SCOPE"
        if not isinstance(evidence.artifact_bytes, bytes) or sha256_hex(evidence.artifact_bytes) != tx["checkpoint_digest"]:
            return False, "PERSISTENCE_EVIDENCE_INVALID"
        if not evidence.evidence_id or not evidence.evidence_kind:
            return False, "PERSISTENCE_EVIDENCE_INVALID"
        return True, ""

    def _record_commit_replay_rejection(self, conn: sqlite3.Connection, tx: sqlite3.Row,
                                        reason_code: str) -> CustodyReceipt:
        candidate = CheckpointCandidate(**json.loads(tx["candidate_json"]))
        receipt = self._make_receipt(conn, transaction_id=tx["transaction_id"], operation="commit",
            custody_state=ReceiptStatus.REJECTED, candidate=candidate,
            reservation_id=tx["reservation_id"], lease_expires_at=tx["lease_expires_at"],
            reason_code=reason_code)
        self._store_receipt(conn, receipt)
        self._append_event(conn, "COMMIT_REPLAY_REJECTED", tx["transaction_id"],
            {"reason_code": reason_code, "receipt_id": receipt.receipt_id,
             "original_committed_receipt": self._decode_receipt(tx["receipt_json"]).receipt_id})
        conn.commit()
        return receipt

    def _record_commit_rejection(self, conn: sqlite3.Connection, tx: sqlite3.Row,
                                 reason_code: str, message: str) -> CustodyReceipt:
        candidate = CheckpointCandidate(**json.loads(tx["candidate_json"]))
        receipt = self._make_receipt(conn, transaction_id=tx["transaction_id"], operation="commit",
            custody_state=ReceiptStatus.REJECTED, candidate=candidate,
            reservation_id=tx["reservation_id"], lease_expires_at=tx["lease_expires_at"],
            reason_code=reason_code)
        conn.execute("UPDATE transactions SET status=?,receipt_json=?,updated_at=? WHERE transaction_id=?",
            (ReceiptStatus.REJECTED.value, canonical(receipt.as_dict()).decode(), self._now(), tx["transaction_id"]))
        self._store_receipt(conn, receipt)
        self._append_event(conn, "COMMIT_REJECTED", tx["transaction_id"],
            {"reason_code": reason_code, "message": message, "receipt_id": receipt.receipt_id})
        self._fault("commit.rejection_before_atomic_commit")
        conn.commit()
        return receipt

    def commit(self, transaction_id: str, reservation_id: str, evidence: PersistenceEvidence) -> CustodyReceipt:
        if not isinstance(evidence, PersistenceEvidence):
            raise TypeError("evidence must be PersistenceEvidence")
        conn = self._connect()
        committed_receipt: CustodyReceipt | None = None
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._verify_state(conn)
            tx = conn.execute("SELECT * FROM transactions WHERE transaction_id=?", (transaction_id,)).fetchone()
            if tx is None:
                raise CustodyRejected("UNKNOWN_TRANSACTION", "transaction is not present in custody journal")
            if tx["status"] == ReceiptStatus.COMMITTED.value:
                evidence_ok, evidence_reason = self._evidence_matches(tx, transaction_id, reservation_id, evidence)
                if not evidence_ok:
                    return self._record_commit_replay_rejection(conn, tx, evidence_reason)
                receipt = self._decode_receipt(tx["receipt_json"])
                conn.commit()
                if receipt is None:
                    raise CustodyIntegrityError("committed transaction has no receipt")
                return receipt
            if tx["status"] != ReceiptStatus.PREPARED.value:
                prior = self._decode_receipt(tx["receipt_json"])
                conn.commit()
                if prior is not None:
                    return prior
                raise CustodyRejected("WRONG_STATUS", f"transaction is {tx['status']}")
            prepared_receipt = self._decode_receipt(tx["receipt_json"])
            current_epoch = int(self._meta_get(conn, "authority_epoch"))
            if prepared_receipt is None or prepared_receipt.authority_epoch != current_epoch:
                return self._record_commit_rejection(conn, tx, "STALE_EPOCH", "reservation was prepared under a stale authority epoch")
            if conn.execute("SELECT 1 FROM revocations WHERE key_id=?", (prepared_receipt.key_id,)).fetchone():
                return self._record_commit_rejection(conn, tx, "REVOKED_KEY", "reservation signing key has been revoked")
            evidence_ok, evidence_reason = self._evidence_matches(tx, transaction_id, reservation_id, evidence)
            if not evidence_ok:
                return self._record_commit_rejection(conn, tx, evidence_reason, "persistence evidence failed binding or digest validation")
            accepted_at = self._now()
            if accepted_at > float(tx["lease_expires_at"]):
                expired = self._make_receipt(conn, transaction_id=transaction_id, operation="commit",
                    custody_state=ReceiptStatus.EXPIRED, candidate=CheckpointCandidate(**json.loads(tx["candidate_json"])),
                    reservation_id=reservation_id, lease_expires_at=tx["lease_expires_at"],
                    reason_code="LEASE_EXPIRED", issued_at=accepted_at)
                conn.execute("UPDATE transactions SET status=?,receipt_json=?,updated_at=? WHERE transaction_id=?",
                    (ReceiptStatus.EXPIRED.value, canonical(expired.as_dict()).decode(), accepted_at, transaction_id))
                self._store_receipt(conn, expired)
                self._append_event(conn, "COMMIT_EXPIRED", transaction_id, {"receipt_id": expired.receipt_id})
                conn.commit()
                return expired
            candidate = CheckpointCandidate(**json.loads(tx["candidate_json"]))
            try:
                self._candidate_ordering(conn, candidate)
            except CustodyRejected as exc:
                return self._record_commit_rejection(conn, tx, exc.reason_code, str(exc))
            receipt = self._make_receipt(conn, transaction_id=transaction_id, operation="commit",
                custody_state=ReceiptStatus.COMMITTED, candidate=candidate,
                reservation_id=reservation_id, lease_expires_at=tx["lease_expires_at"], issued_at=accepted_at)
            # Prepare the complete signed outcome before entering the atomic DB commit.
            receipt_json = canonical(receipt.as_dict()).decode()
            floor = conn.execute("SELECT * FROM floors WHERE stream_id=?", (candidate.stream_id,)).fetchone()
            if floor is None:
                conn.execute("INSERT INTO floors(stream_id,lineage_id,generation,sequence_no,checkpoint_digest,previous_checkpoint_digest,authority_epoch,receipt_id,transaction_id) VALUES(?,?,?,?,?,?,?,?,?)",
                    (candidate.stream_id, candidate.lineage_id, candidate.generation, candidate.sequence_no,
                     candidate.checkpoint_digest, candidate.previous_checkpoint_digest, receipt.authority_epoch, receipt.receipt_id, transaction_id))
            else:
                conn.execute("UPDATE floors SET lineage_id=?,generation=?,sequence_no=?,checkpoint_digest=?,previous_checkpoint_digest=?,authority_epoch=?,receipt_id=?,transaction_id=? WHERE stream_id=?",
                    (candidate.lineage_id, candidate.generation, candidate.sequence_no, candidate.checkpoint_digest,
                     candidate.previous_checkpoint_digest, receipt.authority_epoch, receipt.receipt_id, transaction_id, candidate.stream_id))
            conn.execute("UPDATE transactions SET status=?,receipt_json=?,updated_at=? WHERE transaction_id=?",
                (ReceiptStatus.COMMITTED.value, receipt_json, accepted_at, transaction_id))
            self._store_receipt(conn, receipt)
            self._append_event(conn, "COMMITTED", transaction_id, {
                "receipt_id": receipt.receipt_id, "checkpoint_digest": candidate.checkpoint_digest,
                "previous_checkpoint_digest": candidate.previous_checkpoint_digest,
                "stream_id": candidate.stream_id, "lineage_id": candidate.lineage_id,
                "generation": candidate.generation, "sequence_no": candidate.sequence_no,
                "recovery_authorization_id": candidate.recovery_authorization_id,
                "previous_lineage_id": candidate.previous_lineage_id,
                "lineage_parent_id": candidate.lineage_parent_id,
                "previous_generation": candidate.previous_generation,
                "target_generation": candidate.target_generation,
                "persistence_evidence_id": evidence.evidence_id,
                "persistence_evidence_kind": evidence.evidence_kind,
                "persistence_digest_verified": True,
            })
            if candidate.recovery_authorization_id:
                conn.execute("UPDATE recovery_authorizations SET consumed_by=? WHERE recovery_authorization_id=? AND consumed_by IS NULL",
                    (transaction_id, candidate.recovery_authorization_id))
            self._fault("commit.before_atomic_commit")
            conn.commit()
            committed_receipt = receipt
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()
        # This fault models a lost response after the atomic transaction committed.
        try:
            self._fault("commit.after_atomic_commit")
        except Exception as exc:
            raise AmbiguousCommitError(transaction_id) from exc
        assert committed_receipt is not None
        return committed_receipt

    def read_floor(self, stream_id: str) -> FloorAttestation:
        if not isinstance(stream_id, str) or not _ID.fullmatch(stream_id):
            raise ValueError("invalid stream_id")
        self._fault("read_floor.before_response")
        conn = self._connect()
        try:
            self._verify_state(conn)
            key_id, key, epoch = self._active_key(conn)
            row = conn.execute("SELECT * FROM floors WHERE stream_id=?", (stream_id,)).fetchone()
            revoked = tuple(r["key_id"] for r in conn.execute("SELECT key_id FROM revocations ORDER BY key_id"))
            unsigned = FloorAttestation(
                authority_id=self.authority_id, authority_epoch=epoch, custody_mode=CUSTODY_MODE,
                stream_id=stream_id, lineage_id=row["lineage_id"] if row else None,
                generation=row["generation"] if row else None, sequence_no=row["sequence_no"] if row else None,
                checkpoint_digest=row["checkpoint_digest"] if row else None,
                previous_checkpoint_digest=row["previous_checkpoint_digest"] if row else None,
                receipt_id=row["receipt_id"] if row else None, revoked_key_ids=revoked,
                issued_at=self._now(), key_id=key_id, signature_algorithm="HMAC-SHA256-TEST-ONLY", signature="")
            signature = self._sign(key, unsigned.payload())
            return FloorAttestation(**{**asdict(unsigned), "signature": signature})
        finally:
            conn.close()

    def verify_floor_attestation(self, attestation: FloorAttestation) -> bool:
        if not isinstance(attestation, FloorAttestation) or attestation.authority_id != self.authority_id:
            return False
        if attestation.custody_mode != CUSTODY_MODE or attestation.key_id not in self._keys:
            return False
        conn = self._connect()
        try:
            self._verify_state(conn)
            if self._meta_get(conn, "authority_revoked") == "1":
                return False
            if int(self._meta_get(conn, "authority_epoch")) != attestation.authority_epoch:
                return False
            if conn.execute("SELECT 1 FROM revocations WHERE key_id=?", (attestation.key_id,)).fetchone():
                return False
        finally:
            conn.close()
        return hmac.compare_digest(self._sign(self._keys[attestation.key_id], attestation.payload()), attestation.signature)

    def verify_receipt(
        self, receipt: CustodyReceipt | Mapping[str, Any], *,
        expected_status: str | ReceiptStatus | None = None,
        expected_operation: str | None = None,
        expected_scope: Mapping[str, Any] | None = None,
    ) -> VerificationResult:
        try:
            item = receipt if isinstance(receipt, CustodyReceipt) else CustodyReceipt.from_dict(receipt)
        except Exception:
            return VerificationResult(VerificationOutcome.INVALID_CANONICALIZATION, False, CUSTODY_MODE, "receipt schema invalid")
        if item.authority_id != self.authority_id:
            return VerificationResult(VerificationOutcome.UNKNOWN_AUTHORITY, False, CUSTODY_MODE, "authority identity mismatch")
        if item.schema_version != SCHEMA_VERSION or item.canonicalization_version != CANONICALIZATION_VERSION or item.domain_separator != DOMAIN_SEPARATOR:
            return VerificationResult(VerificationOutcome.INVALID_CANONICALIZATION, False, CUSTODY_MODE, "unsupported receipt schema/canonicalization/domain")
        if item.custody_mode != CUSTODY_MODE or item.signature_algorithm != "HMAC-SHA256-TEST-ONLY":
            return VerificationResult(VerificationOutcome.INVALID_CANONICALIZATION, False, CUSTODY_MODE, "simulator environment/algorithm mismatch")
        if not self._verify_signature_only(item):
            return VerificationResult(VerificationOutcome.INVALID_SIGNATURE, False, CUSTODY_MODE, "receipt signature invalid")
        conn = self._connect()
        try:
            self._verify_state(conn)
            if conn.execute("SELECT 1 FROM revocations WHERE key_id=?", (item.key_id,)).fetchone():
                return VerificationResult(VerificationOutcome.REVOKED_KEY, False, CUSTODY_MODE, "receipt signing key is revoked")
            epoch = int(self._meta_get(conn, "authority_epoch"))
            if item.authority_epoch != epoch:
                return VerificationResult(VerificationOutcome.STALE_EPOCH, False, CUSTODY_MODE, "receipt authority epoch is not current")
        except CustodyError:
            raise
        finally:
            conn.close()
        if item.lease_expires_at is not None and item.custody_state in (ReceiptStatus.PREPARED.value, ReceiptStatus.RECOVERY_AUTHORIZED.value):
            if self._now() > item.lease_expires_at:
                return VerificationResult(VerificationOutcome.EXPIRED, False, CUSTODY_MODE, "receipt reservation lease expired")
        if expected_operation is not None and item.operation != expected_operation:
            return VerificationResult(VerificationOutcome.WRONG_SCOPE, False, CUSTODY_MODE, "operation mismatch")
        if expected_scope:
            for field, expected in expected_scope.items():
                if getattr(item, field, object()) != expected:
                    return VerificationResult(VerificationOutcome.WRONG_SCOPE, False, CUSTODY_MODE, f"{field} mismatch")
        if expected_status is not None:
            status = expected_status.value if isinstance(expected_status, ReceiptStatus) else str(expected_status)
            if item.custody_state != status:
                return VerificationResult(VerificationOutcome.WRONG_STATUS, False, CUSTODY_MODE, "receipt lifecycle status mismatch")
        return VerificationResult(VerificationOutcome.VALID, True, CUSTODY_MODE, "signature, authority, epoch, and requested scope verified")

    def authorize_recovery(
        self, *, stream_id: str, previous_lineage_id: str, target_lineage_id: str,
        lineage_parent_id: str, previous_generation: int, target_generation: int,
        authorization_proof: str, transaction_id: str | None = None,
    ) -> CustodyReceipt:
        if not authorization_proof or not isinstance(authorization_proof, str):
            raise CustodyRejected("NO_RECOVERY_AUTH", "explicit recovery authorization proof is required")
        if target_generation <= previous_generation:
            raise CustodyRejected("NON_MONOTONIC_GENERATION", "target generation must exceed previous generation")
        txid = transaction_id or f"recovery:{uuid.uuid4()}"
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._verify_state(conn)
            floor = conn.execute("SELECT * FROM floors WHERE stream_id=?", (stream_id,)).fetchone()
            if floor is None or floor["lineage_id"] != previous_lineage_id or floor["generation"] != previous_generation:
                raise CustodyRejected("WRONG_SCOPE", "recovery request does not match current floor")
            auth_id = str(uuid.uuid4())
            receipt = self._make_receipt(conn, transaction_id=txid, operation="authorize_recovery",
                custody_state=ReceiptStatus.RECOVERY_AUTHORIZED, recovery_authorization_id=auth_id,
                reason_code="OWNER_AUTHORIZATION_RECORDED", recovery_scope={
                    "stream_id": stream_id, "previous_lineage_id": previous_lineage_id,
                    "target_lineage_id": target_lineage_id, "lineage_parent_id": lineage_parent_id,
                    "previous_generation": previous_generation, "target_generation": target_generation,
                    "previous_checkpoint_digest": floor["checkpoint_digest"],
                })
            # Recovery coordinates are recorded in the authorization journal row and event.
            conn.execute("INSERT INTO recovery_authorizations(recovery_authorization_id,stream_id,previous_lineage_id,target_lineage_id,lineage_parent_id,previous_generation,target_generation,receipt_json,consumed_by) VALUES(?,?,?,?,?,?,?,?,NULL)",
                (auth_id, stream_id, previous_lineage_id, target_lineage_id, lineage_parent_id,
                 previous_generation, target_generation, canonical(receipt.as_dict()).decode()))
            self._store_receipt(conn, receipt)
            self._append_event(conn, "RECOVERY_AUTHORIZED", txid, {
                "recovery_authorization_id": auth_id, "stream_id": stream_id,
                "previous_lineage_id": previous_lineage_id, "target_lineage_id": target_lineage_id,
                "lineage_parent_id": lineage_parent_id, "previous_generation": previous_generation,
                "target_generation": target_generation, "authorization_proof_digest": sha256_hex(authorization_proof.encode()),
                "receipt_id": receipt.receipt_id,
            })
            self._fault("authorize_recovery.before_atomic_commit")
            conn.commit()
            return receipt
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def revoke_authority(
        self, *, new_authority_epoch: int, reason: str, authorization_proof: str,
        target_key_id: str | None = None, target_authority_id: str | None = None,
        next_active_key_id: str | None = None, transaction_id: str | None = None,
    ) -> CustodyReceipt:
        if not reason or not authorization_proof:
            raise CustodyRejected("UNAUTHORIZED_REVOCATION", "reason and authorization proof are required")
        txid = transaction_id or f"revoke:{uuid.uuid4()}"
        conn = self._connect()
        try:
            conn.execute("BEGIN IMMEDIATE")
            self._verify_state(conn)
            current_epoch = int(self._meta_get(conn, "authority_epoch"))
            if new_authority_epoch != current_epoch + 1:
                raise CustodyRejected("NON_MONOTONIC_EPOCH", "authority epoch must advance exactly one step")
            if (target_key_id is None) == (target_authority_id is None):
                raise CustodyRejected("INVALID_REVOCATION_TARGET", "specify exactly one key_id or authority_id")
            active = self._meta_get(conn, "active_key_id")
            if target_authority_id is not None:
                if target_authority_id != self.authority_id:
                    raise CustodyRejected("UNKNOWN_AUTHORITY", "target authority identity mismatch")
                new_active = active
                receipt_reason = f"AUTHORITY_REVOKED:{target_authority_id}"
                event_type = "AUTHORITY_REVOKED"
            else:
                if target_key_id not in self._keys:
                    raise CustodyRejected("UNKNOWN_KEY", "target key is not configured")
                if conn.execute("SELECT 1 FROM revocations WHERE key_id=?", (target_key_id,)).fetchone():
                    raise CustodyRejected("ALREADY_REVOKED", "key is already revoked")
                new_active = next_active_key_id or active
                if new_active == target_key_id or new_active not in self._keys:
                    raise CustodyRejected("NO_ACTIVE_SIGNING_KEY", "a distinct configured signing key is required")
                if conn.execute("SELECT 1 FROM revocations WHERE key_id=?", (new_active,)).fetchone():
                    raise CustodyRejected("REVOKED_KEY", "replacement signing key is revoked")
                receipt_reason = f"REVOKED:{target_key_id}"
                event_type = "AUTHORITY_KEY_REVOKED"
            # Sign the revocation outcome with the post-transition epoch.
            receipt = self._make_receipt(conn, transaction_id=txid, operation="revoke_authority",
                custody_state=ReceiptStatus.COMMITTED, reason_code=receipt_reason,
                key_override=(new_active, self._keys[new_active], new_authority_epoch))
            revoked_at = self._now() if target_key_id is not None else None
            if target_key_id is not None:
                conn.execute("INSERT INTO revocations(key_id,revoked_at,authority_epoch,reason_code) VALUES(?,?,?,?)",
                    (target_key_id, revoked_at, new_authority_epoch, reason))
            self._meta_set(conn, "authority_epoch", str(new_authority_epoch))
            self._meta_set(conn, "active_key_id", new_active)
            self._store_receipt(conn, receipt)
            self._append_event(conn, event_type, txid, {
                "target_key_id": target_key_id, "target_authority_id": target_authority_id,
                "authority_epoch": new_authority_epoch, "reason": reason,
                "new_active_key_id": new_active,
                "authority_revoked": target_authority_id is not None,
                "revoked_at": revoked_at,
                "authorization_proof_digest": sha256_hex(authorization_proof.encode()),
                "receipt_id": receipt.receipt_id,
            })
            if target_authority_id is not None:
                self._meta_set(conn, "authority_revoked", "1")
            self._fault("revoke_authority.before_atomic_commit")
            conn.commit()
            return receipt
        except Exception:
            if conn.in_transaction:
                conn.rollback()
            raise
        finally:
            conn.close()

    def query_transaction(self, transaction_id: str) -> TransactionRecord | None:
        """Authenticated local journal query used for post-crash reconciliation."""
        self._fault("query_transaction.before_response")
        conn = self._connect()
        try:
            self._verify_state(conn)
            row = conn.execute("SELECT * FROM transactions WHERE transaction_id=?", (transaction_id,)).fetchone()
            if row is not None:
                return TransactionRecord(
                    transaction_id=transaction_id, status=row["status"],
                    candidate=json.loads(row["candidate_json"]), reservation_id=row["reservation_id"],
                    lease_expires_at=row["lease_expires_at"], receipt=self._decode_receipt(row["receipt_json"]),
                    custody_mode=CUSTODY_MODE,
                )
            # Rejected PREPARE attempts have no reservation row, but their
            # authenticated event and signed REJECTED receipt remain queryable.
            event = conn.execute(
                "SELECT * FROM journal_events WHERE transaction_id=? ORDER BY event_no DESC LIMIT 1",
                (transaction_id,),
            ).fetchone()
            if event is None or event["event_type"] != "PREPARE_REJECTED":
                return None
            payload = json.loads(event["payload_json"])
            receipt_row = conn.execute("SELECT receipt_json FROM receipts WHERE receipt_id=?",
                                       (payload.get("receipt_id"),)).fetchone()
            receipt = self._decode_receipt(receipt_row["receipt_json"] if receipt_row else None)
            return TransactionRecord(
                transaction_id=transaction_id, status=ReceiptStatus.REJECTED.value,
                candidate=payload.get("candidate", {}), reservation_id=None,
                lease_expires_at=None, receipt=receipt, custody_mode=CUSTODY_MODE,
            )
        finally:
            conn.close()

    def journal_history(self, transaction_id: str | None = None) -> tuple[dict[str, Any], ...]:
        """Return authenticated event history; intended for tests and diagnostics."""
        conn = self._connect()
        try:
            self._verify_state(conn)
            if transaction_id is None:
                rows = conn.execute("SELECT * FROM journal_events ORDER BY event_no").fetchall()
            else:
                rows = conn.execute("SELECT * FROM journal_events WHERE transaction_id=? ORDER BY event_no", (transaction_id,)).fetchall()
            return tuple({
                "event_no": row["event_no"], "event_type": row["event_type"],
                "transaction_id": row["transaction_id"], "payload": json.loads(row["payload_json"]),
                "event_hash": row["event_hash"], "key_id": row["key_id"], "mac": row["mac"],
            } for row in rows)
        finally:
            conn.close()