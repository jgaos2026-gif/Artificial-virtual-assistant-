import hashlib
import json
import struct

import pytest

from ava_military.anchor import (
    AnchorError, AnchorProposal, AnchorSnapshot, AnchoredColdLog, BrickPin, CompositeWakeVerifier,
    SpineReceipt,
)

GENESIS = "0" * 64
KEY = b"test-only-key-material-not-production"


class MemoryAuthority:
    """Test double only. It is not an independent or production trust authority."""
    def __init__(self):
        self.value = None

    def _sign(self, snap):
        import hmac
        body = f"{snap.stream_id}|{snap.generation}|{snap.record_count}|{snap.head_hash}|test-authority"
        return hmac.new(KEY, body.encode(), hashlib.sha256).hexdigest()

    def _signed(self, proposal):
        snap = AnchorSnapshot(
            proposal.stream_id, proposal.generation, proposal.record_count,
            proposal.head_hash, "test-authority", "00",
        )
        from dataclasses import replace
        return replace(snap, signature_hex=self._sign(snap))

    def read(self, stream_id):
        return self.value if self.value and self.value.stream_id == stream_id else None

    def provision(self, initial):
        if self.value is not None:
            raise RuntimeError("already provisioned")
        self.value = self._signed(initial)
        return self.value

    def compare_and_advance(self, expected_generation, proposed):
        if self.value is None or self.value.generation != expected_generation:
            raise RuntimeError("stale generation")
        self.value = self._signed(proposed)
        return self.value

    def verify(self, snapshot):
        import hmac
        return (
            snapshot.authority_id == "test-authority"
            and hmac.compare_digest(snapshot.signature_hex, self._sign(snapshot))
        )


class GoodSpine:
    def verify_spine_receipt(self, receipt):
        return True


class GoodBricks:
    def __init__(self):
        self.revoked = set()
        self.valid = set()

    def verify_exact_pin(self, pin):
        return (pin.brick_id, pin.version, pin.manifest_digest) in self.valid

    def is_revoked(self, pin):
        return (pin.brick_id, pin.version, pin.manifest_digest) in self.revoked


def make_log(tmp_path):
    path = tmp_path / "cold.frames"
    authority = MemoryAuthority()
    log = AnchoredColdLog.provision_empty(path, "memory-main", authority)
    return path, authority, log


def append_one(log, rid="record-1"):
    return log.append(rid, "MEMORY_COMMIT", {"text": "first"})


def test_missing_log_never_resets_existing_anchor(tmp_path):
    authority = MemoryAuthority()
    path = tmp_path / "missing.frames"
    authority.provision(AnchorSnapshot("s", 0, 0, GENESIS, "pending", "00"))
    with pytest.raises(AnchorError, match="MISSING_ARCHIVE"):
        AnchoredColdLog(path, "s", authority)


def test_existing_log_without_anchor_fails_closed(tmp_path):
    path = tmp_path / "orphan.frames"
    path.write_bytes(b"")
    with pytest.raises(AnchorError, match="MISSING_ANCHOR"):
        AnchoredColdLog(path, "orphan", MemoryAuthority())


def test_unprovisioned_stream_is_not_created_implicitly(tmp_path):
    path = tmp_path / "not-created.frames"
    with pytest.raises(AnchorError, match="UNPROVISIONED"):
        AnchoredColdLog(path, "s", MemoryAuthority())
    assert not path.exists()


def test_explicit_provisioning_refuses_existing_log_or_anchor(tmp_path):
    path, authority, _ = make_log(tmp_path)
    with pytest.raises(AnchorError, match="provisioning refused"):
        AnchoredColdLog.provision_empty(path, "memory-main", authority)


def test_truncation_is_detected_against_external_checkpoint(tmp_path):
    path, authority, log = make_log(tmp_path)
    append_one(log)
    path.write_bytes(b"")
    with pytest.raises(AnchorError):
        AnchoredColdLog(path, "memory-main", authority)


def test_stale_generation_or_old_anchor_replay_is_rejected(tmp_path):
    path, authority, log = make_log(tmp_path)
    old = authority.read("memory-main")
    append_one(log)
    assert authority.read("memory-main").generation == 1
    # A caller cannot roll the authority backward through its CAS interface.
    with pytest.raises(RuntimeError, match="stale generation"):
        authority.compare_and_advance(0, AnchorProposal("memory-main", 1, 1, "f" * 64))
    # Replaying the old signed anchor against the newer log fails count/head.
    with pytest.raises(AnchorError):
        log._verify_snapshot(old)


def test_anchor_tampering_is_detected(tmp_path):
    _, authority, _ = make_log(tmp_path)
    from dataclasses import replace
    tampered = replace(authority.read("memory-main"), head_hash="f" * 64)
    assert not authority.verify(tampered)


def test_duplicate_record_ids_are_rejected(tmp_path):
    _, _, log = make_log(tmp_path)
    append_one(log, "same-id")
    with pytest.raises(AnchorError, match="duplicate"):
        log.append("same-id", "MEMORY_COMMIT", {"text": "again"})


def test_unsafe_stream_and_record_ids_are_rejected(tmp_path):
    authority = MemoryAuthority()
    with pytest.raises(AnchorError):
        AnchoredColdLog.provision_empty(tmp_path / "x", "../bad", authority)
    _, _, log = make_log(tmp_path)
    with pytest.raises(AnchorError):
        log.append("../bad", "MEMORY_COMMIT", {})


def test_strict_payload_rejects_nan(tmp_path):
    _, _, log = make_log(tmp_path)
    with pytest.raises(AnchorError, match="canonical"):
        log.append("r1", "MEMORY_COMMIT", {"bad": float("nan")})


def test_malformed_frame_schema_is_rejected(tmp_path):
    path, authority, _ = make_log(tmp_path)
    raw = json.dumps({"wrong": "schema"}).encode()
    path.write_bytes(struct.pack(">I", len(raw)) + raw)
    # The external genesis anchor must not bless an uncheckpointed frame.
    with pytest.raises(AnchorError):
        AnchoredColdLog(path, "memory-main", authority)


def test_interrupted_append_leaves_stream_unusable_not_silently_repaired(tmp_path, monkeypatch):
    path, authority, log = make_log(tmp_path)
    from pathlib import Path
    original_open = Path.open

    class BrokenWriter:
        def __init__(self, handle):
            self.handle = handle
        def __enter__(self):
            return self
        def __exit__(self, *args):
            self.handle.close()
        def write(self, data):
            self.handle.write(data[: max(1, len(data)//2)])
            raise OSError("simulated power loss")
        def flush(self):
            self.handle.flush()
        def fileno(self):
            return self.handle.fileno()

    def broken_open(self, mode="r", *args, **kwargs):
        if self == path and mode == "ab":
            return BrokenWriter(original_open(self, "ab"))
        return original_open(self, mode, *args, **kwargs)

    monkeypatch.setattr(Path, "open", broken_open)
    with pytest.raises(AnchorError, match="incomplete"):
        log.append("interrupted", "MEMORY_COMMIT", {"text": "partial"})
    monkeypatch.setattr(Path, "open", original_open)
    with pytest.raises(AnchorError):
        log.verify()


def test_concurrent_writers_preserve_monotonic_sequence(tmp_path):
    from concurrent.futures import ThreadPoolExecutor
    _, authority, log = make_log(tmp_path)
    def write(i):
        return log.append(f"r-{i}", "MEMORY_COMMIT", {"i": i})
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(write, range(24)))
    assert log.verify().generation == 24
    assert authority.read("memory-main").record_count == 24


def test_brick_version_and_digest_are_pinned_for_wake(tmp_path):
    _, authority, log = make_log(tmp_path)
    snapshot = log.verify()
    pin = BrickPin("memory", "2.1.0", "a" * 64)
    bricks = GoodBricks()
    bricks.valid.add((pin.brick_id, pin.version, pin.manifest_digest))
    receipt = SpineReceipt(snapshot.generation, snapshot.head_hash, "b" * 64, "spine-v", "abcd")
    wake = CompositeWakeVerifier(authority, GoodSpine(), bricks, (pin,))
    assert wake.verify_wake(snapshot, receipt, "memory-main")
    wrong = BrickPin("memory", "2.1.1", "c" * 64)
    with pytest.raises(AnchorError):
        CompositeWakeVerifier(authority, GoodSpine(), bricks, (wrong,)).verify_wake(snapshot, receipt, "memory-main")


def test_wake_rejects_replayed_but_valid_old_anchor(tmp_path):
    _, authority, log = make_log(tmp_path)
    old_snapshot = log.verify()
    old_receipt = SpineReceipt(old_snapshot.generation, old_snapshot.head_hash, "b" * 64, "spine-v", "abcd")
    pin = BrickPin("memory", "1.0.0", "a" * 64)
    bricks = GoodBricks()
    bricks.valid.add((pin.brick_id, pin.version, pin.manifest_digest))
    append_one(log, "later-record")
    with pytest.raises(AnchorError, match="stale anchor replay"):
        CompositeWakeVerifier(authority, GoodSpine(), bricks, (pin,)).verify_wake(
            old_snapshot, old_receipt, "memory-main"
        )


def test_revoked_exact_brick_pin_denies_wake(tmp_path):
    _, authority, log = make_log(tmp_path)
    snapshot = log.verify()
    pin = BrickPin("memory", "1.0.0", "a" * 64)
    bricks = GoodBricks()
    key = (pin.brick_id, pin.version, pin.manifest_digest)
    bricks.valid.add(key)
    bricks.revoked.add(key)
    receipt = SpineReceipt(snapshot.generation, snapshot.head_hash, "b" * 64, "spine-v", "abcd")
    with pytest.raises(AnchorError, match="revoked"):
        CompositeWakeVerifier(authority, GoodSpine(), bricks, (pin,)).verify_wake(snapshot, receipt, "memory-main")


def test_spine_verifier_exception_denies_wake(tmp_path):
    _, authority, log = make_log(tmp_path)
    snapshot = log.verify()
    pin = BrickPin("memory", "1.0.0", "a" * 64)
    bricks = GoodBricks()
    bricks.valid.add((pin.brick_id, pin.version, pin.manifest_digest))
    receipt = SpineReceipt(snapshot.generation, snapshot.head_hash, "b" * 64, "spine-v", "abcd")
    class ExplodingSpine:
        def verify_spine_receipt(self, receipt):
            raise RuntimeError("verifier crashed")
    with pytest.raises(AnchorError, match="wake verifier exception"):
        CompositeWakeVerifier(authority, ExplodingSpine(), bricks, (pin,)).verify_wake(snapshot, receipt, "memory-main")


def test_brick_verifier_exception_denies_wake(tmp_path):
    _, authority, log = make_log(tmp_path)
    snapshot = log.verify()
    pin = BrickPin("memory", "1.0.0", "a" * 64)
    class ExplodingBricks:
        def verify_exact_pin(self, pin):
            raise RuntimeError("registry unavailable")
        def is_revoked(self, pin):
            return False
    receipt = SpineReceipt(snapshot.generation, snapshot.head_hash, "b" * 64, "spine-v", "abcd")
    with pytest.raises(AnchorError, match="wake verifier exception"):
        CompositeWakeVerifier(authority, GoodSpine(), ExplodingBricks(), (pin,)).verify_wake(snapshot, receipt, "memory-main")
