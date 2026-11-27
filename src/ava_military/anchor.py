"""Fail-closed COLD anchoring and wake verification reference interfaces.

The AnchorAuthority is intentionally abstract. A sibling file, local HMAC key,
or same-host process is NOT an independent rollback boundary. Production must
supply a separately administered monotonic authority and authenticated receipts.
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import struct
import tempfile
from typing import Iterator, Protocol

MAX_FRAME_BYTES = 1_048_576
MAX_SIGNATURE_HEX = 4096
_STREAM_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_RECORD_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA_RE = re.compile(r"^[0-9a-f]{64}$")


class AnchorError(PermissionError):
    """Any inability to prove anchored continuity denies use."""


@dataclass(frozen=True)
class AnchorSnapshot:
    stream_id: str
    generation: int
    record_count: int
    head_hash: str
    authority_id: str
    signature_hex: str


@dataclass(frozen=True)
class SpineReceipt:
    checkpoint_seq: int
    checkpoint_head: str
    spine_digest: str
    verifier_id: str
    signature_hex: str


@dataclass(frozen=True)
class BrickPin:
    brick_id: str
    version: str
    manifest_digest: str


class AnchorAuthority(Protocol):
    """Must be backed by a trust/failure domain outside the COLD archive."""
    def read(self, stream_id: str) -> AnchorSnapshot | None: ...
    def provision(self, initial: AnchorSnapshot) -> AnchorSnapshot: ...
    def compare_and_advance(
        self, expected_generation: int, proposed: AnchorSnapshot
    ) -> AnchorSnapshot: ...
    def verify(self, snapshot: AnchorSnapshot) -> bool: ...


class SpineReceiptVerifier(Protocol):
    def verify_spine_receipt(self, receipt: SpineReceipt) -> bool: ...


class BrickTrustVerifier(Protocol):
    def verify_exact_pin(self, pin: BrickPin) -> bool: ...
    def is_revoked(self, pin: BrickPin) -> bool: ...


@contextmanager
def _exclusive_writer_lock(lock_path: Path) -> Iterator[None]:
    """Cross-process advisory lock; kernel releases it if the process dies."""
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+b")
    try:
        if os.name == "nt":
            import msvcrt
            handle.seek(0)
            if handle.read(1) == b"":
                handle.write(b"0")
                handle.flush()
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _validate_stream_id(stream_id: str) -> None:
    if not isinstance(stream_id, str) or not _STREAM_RE.fullmatch(stream_id):
        raise AnchorError("stream_id is empty or contains unsafe characters")


def _validate_snapshot(snapshot: AnchorSnapshot, stream_id: str) -> None:
    if not isinstance(snapshot, AnchorSnapshot):
        raise AnchorError("anchor has an invalid type")
    _validate_stream_id(snapshot.stream_id)
    if snapshot.stream_id != stream_id:
        raise AnchorError("anchor stream identity mismatch")
    if type(snapshot.generation) is not int or snapshot.generation < 0:
        raise AnchorError("anchor generation is invalid")
    if type(snapshot.record_count) is not int or snapshot.record_count < 0:
        raise AnchorError("anchor record_count is invalid")
    if snapshot.generation != snapshot.record_count:
        raise AnchorError("anchor generation/count mismatch")
    if not isinstance(snapshot.head_hash, str) or not _SHA_RE.fullmatch(snapshot.head_hash):
        raise AnchorError("anchor head hash is invalid")
    if not isinstance(snapshot.authority_id, str) or not snapshot.authority_id.strip():
        raise AnchorError("anchor authority identity is missing")
    if (
        not isinstance(snapshot.signature_hex, str)
        or not snapshot.signature_hex
        or len(snapshot.signature_hex) > MAX_SIGNATURE_HEX
        or len(snapshot.signature_hex) % 2
        or not re.fullmatch(r"[0-9a-fA-F]+", snapshot.signature_hex)
    ):
        raise AnchorError("anchor signature encoding/size is invalid")


class AnchoredColdLog:
    """Append-only framed log checked against an external monotonic authority.

    Provisioning is explicit. A failed append/anchor update leaves the stream
    unusable until an operator-led recovery reconciles the durable log and
    independently stored checkpoint. This class never auto-repairs or resets.
    """

    GENESIS = "0" * 64

    def __init__(
        self, path: str | os.PathLike[str], stream_id: str,
        authority: AnchorAuthority,
    ) -> None:
        _validate_stream_id(stream_id)
        self.path = Path(path)
        self.stream_id = stream_id
        self.authority = authority
        self.lock_path = self.path.with_name(self.path.name + ".writer.lock")
        if not self.path.exists():
            if authority.read(stream_id) is not None:
                raise AnchorError("MISSING_ARCHIVE: external anchor exists but COLD log is absent")
            raise AnchorError("UNPROVISIONED: explicit provisioning is required")
        snapshot = authority.read(stream_id)
        if snapshot is None:
            raise AnchorError("MISSING_ANCHOR: COLD log exists without external anchor")
        self._verify_snapshot(snapshot)

    @classmethod
    def provision_empty(
        cls, path: str | os.PathLike[str], stream_id: str,
        authority: AnchorAuthority,
    ) -> "AnchoredColdLog":
        """Explicit first-time provisioning only; never resets existing state."""
        _validate_stream_id(stream_id)
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with _exclusive_writer_lock(target.with_name(target.name + ".writer.lock")):
            if target.exists() or authority.read(stream_id) is not None:
                raise AnchorError("provisioning refused: log or anchor already exists")
            fd = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            try:
                os.fsync(fd)
            finally:
                os.close(fd)
            cls._fsync_directory(target.parent)
            unsigned = AnchorSnapshot(stream_id, 0, 0, cls.GENESIS, "pending", "00")
            try:
                authority.provision(unsigned)
            except Exception as exc:
                raise AnchorError("provisioning failed; empty log remains untrusted") from exc
        return cls(target, stream_id, authority)

    @staticmethod
    def _fsync_directory(directory: Path) -> None:
        if os.name == "nt":
            return
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)

    def _verify_snapshot(self, snapshot: AnchorSnapshot) -> None:
        _validate_snapshot(snapshot, self.stream_id)
        try:
            if not self.authority.verify(snapshot):
                raise AnchorError("external anchor authentication failed")
        except AnchorError:
            raise
        except Exception as exc:
            raise AnchorError("external anchor verifier failed") from exc
        count, head, _ = self._scan()
        if count != snapshot.record_count or head != snapshot.head_hash:
            raise AnchorError("COLD log does not match independent monotonic checkpoint")

    def _scan(self, target_record_id: str | None = None) -> tuple[int, str, bool]:
        """Stream frames; use a disk-backed temporary uniqueness index, not a RAM set."""
        previous = self.GENESIS
        count = 0
        target_seen = False
        try:
            with tempfile.TemporaryDirectory(prefix="ava-cold-verify-") as temp_dir:
                db = sqlite3.connect(str(Path(temp_dir) / "seen.sqlite"))
                try:
                    db.execute("PRAGMA cache_size=-1024")
                    db.execute("PRAGMA temp_store=FILE")
                    db.execute("CREATE TABLE seen_ids (record_id TEXT PRIMARY KEY) WITHOUT ROWID")
                    with self.path.open("rb") as stream:
                        while True:
                            prefix = stream.read(4)
                            if not prefix:
                                break
                            if len(prefix) != 4:
                                raise AnchorError("truncated COLD frame length")
                            size = struct.unpack(">I", prefix)[0]
                            if size < 1 or size > MAX_FRAME_BYTES:
                                raise AnchorError("COLD frame size outside bounds")
                            raw = stream.read(size)
                            if len(raw) != size:
                                raise AnchorError("truncated COLD frame body")
                            try:
                                envelope = json.loads(raw, object_pairs_hook=self._unique_json_object)
                            except AnchorError:
                                raise
                            except Exception as exc:
                                raise AnchorError("malformed COLD frame JSON") from exc
                            if not isinstance(envelope, dict) or set(envelope) != {
                                "sequence", "previous_hash", "record_id", "kind", "payload", "entry_hash"
                            }:
                                raise AnchorError("COLD frame schema mismatch")
                            rid, kind, payload = envelope["record_id"], envelope["kind"], envelope["payload"]
                            if not isinstance(rid, str) or not _RECORD_RE.fullmatch(rid):
                                raise AnchorError("record_id is invalid")
                            try:
                                db.execute("INSERT INTO seen_ids(record_id) VALUES (?)", (rid,))
                            except sqlite3.IntegrityError as exc:
                                raise AnchorError("duplicate record_id in COLD archive") from exc
                            if target_record_id is not None and rid == target_record_id:
                                target_seen = True
                            if not isinstance(kind, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", kind):
                                raise AnchorError("record kind is invalid")
                            if not isinstance(payload, dict):
                                raise AnchorError("record payload must be an object")
                            if type(envelope["sequence"]) is not int or envelope["sequence"] != count:
                                raise AnchorError("COLD sequence mismatch")
                            if envelope["previous_hash"] != previous:
                                raise AnchorError("COLD previous hash mismatch")
                            body = {k: envelope[k] for k in ("sequence", "previous_hash", "record_id", "kind", "payload")}
                            digest = hashlib.sha256(_canonical(body)).hexdigest()
                            if envelope["entry_hash"] != digest:
                                raise AnchorError("COLD frame digest mismatch")
                            previous = digest
                            count += 1
                finally:
                    db.close()
        except AnchorError:
            raise
        except Exception as exc:
            raise AnchorError("COLD stream verification failed") from exc
        return count, previous, target_seen

    @staticmethod
    def _unique_json_object(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise AnchorError("duplicate JSON object key")
            result[key] = value
        return result

    def append(self, record_id: str, kind: str, payload: dict) -> AnchorSnapshot:
        if not isinstance(record_id, str) or not _RECORD_RE.fullmatch(record_id):
            raise AnchorError("record_id is invalid")
        if not isinstance(kind, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,63}", kind):
            raise AnchorError("record kind is invalid")
        if not isinstance(payload, dict):
            raise AnchorError("payload must be an object")
        try:
            # Validate serializability and reject NaN/Infinity before taking the lock.
            _canonical(payload)
        except Exception as exc:
            raise AnchorError("payload is not strict canonical JSON") from exc

        with _exclusive_writer_lock(self.lock_path):
            current = self.authority.read(self.stream_id)
            if current is None:
                raise AnchorError("MISSING_ANCHOR: refusing append")
            self._verify_snapshot(current)
            count, head, duplicate = self._scan(record_id)
            if duplicate:
                raise AnchorError("duplicate record_id")
            body = {
                "sequence": count, "previous_hash": head, "record_id": record_id,
                "kind": kind, "payload": payload,
            }
            digest = hashlib.sha256(_canonical(body)).hexdigest()
            envelope = {**body, "entry_hash": digest}
            raw = _canonical(envelope)
            if len(raw) > MAX_FRAME_BYTES:
                raise AnchorError("serialized frame exceeds maximum size")
            try:
                with self.path.open("ab") as stream:
                    stream.write(struct.pack(">I", len(raw)))
                    stream.write(raw)
                    stream.flush()
                    os.fsync(stream.fileno())
                proposed = AnchorSnapshot(
                    self.stream_id, current.generation + 1, count + 1,
                    digest, current.authority_id, current.signature_hex,
                )
                advanced = self.authority.compare_and_advance(current.generation, proposed)
                _validate_snapshot(advanced, self.stream_id)
                if not self.authority.verify(advanced):
                    raise AnchorError("advanced anchor authentication failed")
                if advanced.generation != count + 1 or advanced.head_hash != digest:
                    raise AnchorError("authority returned an unexpected checkpoint")
                return advanced
            except Exception as exc:
                # Log may now be ahead of anchor. Do not roll back or auto-reconcile.
                if isinstance(exc, AnchorError):
                    raise
                raise AnchorError("append/checkpoint transaction incomplete; quarantine required") from exc

    def verify(self) -> AnchorSnapshot:
        with _exclusive_writer_lock(self.lock_path):
            snapshot = self.authority.read(self.stream_id)
            if snapshot is None:
                raise AnchorError("MISSING_ANCHOR")
            self._verify_snapshot(snapshot)
            return snapshot


class CompositeWakeVerifier:
    """Wake gate over authenticated receipts and exact immutable Brick pins."""

    def __init__(
        self, anchor_authority: AnchorAuthority,
        spine_verifier: SpineReceiptVerifier,
        brick_verifier: BrickTrustVerifier,
        required_bricks: tuple[BrickPin, ...],
    ) -> None:
        self._anchor_authority = anchor_authority
        self._spine_verifier = spine_verifier
        self._brick_verifier = brick_verifier
        self._required_bricks = tuple(
            BrickPin(p.brick_id, p.version, p.manifest_digest) for p in required_bricks
        )

    def verify_wake(
        self, snapshot: AnchorSnapshot, receipt: SpineReceipt,
        expected_stream_id: str,
    ) -> bool:
        try:
            _validate_snapshot(snapshot, expected_stream_id)
            current = self._anchor_authority.read(expected_stream_id)
            if current is None:
                raise AnchorError("MISSING_ANCHOR: wake denied")
            _validate_snapshot(current, expected_stream_id)
            if (
                current.generation != snapshot.generation
                or current.record_count != snapshot.record_count
                or current.head_hash != snapshot.head_hash
            ):
                raise AnchorError("stale anchor replay: supplied checkpoint is not current")
            if not self._anchor_authority.verify(current) or not self._anchor_authority.verify(snapshot):
                raise AnchorError("anchor receipt rejected")
            if (
                type(receipt.checkpoint_seq) is not int
                or receipt.checkpoint_seq != current.generation
                or receipt.checkpoint_head != current.head_hash
                or not isinstance(receipt.spine_digest, str)
                or not _SHA_RE.fullmatch(receipt.spine_digest)
                or not isinstance(receipt.verifier_id, str)
                or not receipt.verifier_id
                or not isinstance(receipt.signature_hex, str)
                or len(receipt.signature_hex) == 0
                or len(receipt.signature_hex) > MAX_SIGNATURE_HEX
                or len(receipt.signature_hex) % 2
                or not re.fullmatch(r"[0-9a-fA-F]+", receipt.signature_hex)
            ):
                raise AnchorError("spine receipt is not bound to exact current checkpoint")
            if not self._spine_verifier.verify_spine_receipt(receipt):
                raise AnchorError("spine receipt authentication failed")
            for pin in self._required_bricks:
                if (
                    not pin.brick_id or not pin.version
                    or not _SHA_RE.fullmatch(pin.manifest_digest)
                    or self._brick_verifier.is_revoked(pin)
                    or not self._brick_verifier.verify_exact_pin(pin)
                ):
                    raise AnchorError("required Brick version/digest is revoked or unverified")
            return True
        except Exception as exc:
            if isinstance(exc, AnchorError):
                raise
            raise AnchorError("wake verifier exception: wake denied") from exc
