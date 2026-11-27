import pytest
from dataclasses import replace

from ava_military.ledger import HashChainLedger


def test_clean_chain_verifies():
    ledger = HashChainLedger()
    ledger.append({"event": "BOOT", "state": "OBSERVED"})
    ledger.append({"event": "CHECKPOINT", "id": "cp-1"})
    assert HashChainLedger.verify(ledger.entries)


def test_payload_mutation_is_detected():
    ledger = HashChainLedger()
    ledger.append({"event": "BOOT"})
    ledger.append({"event": "ACTION", "approved": True})
    changed = list(ledger.entries)
    changed[1] = replace(changed[1], payload={"event": "ACTION", "approved": False})
    assert not HashChainLedger.verify(changed)


def test_valid_prefix_requires_external_head_anchor_to_detect_truncation():
    ledger = HashChainLedger()
    ledger.append({"n": 1})
    ledger.append({"n": 2})
    ledger.append({"n": 3})
    trusted_head = ledger.entries[-1].entry_hash
    prefix = ledger.entries[:2]
    # A prefix is internally valid. The external head anchor exposes truncation.
    assert HashChainLedger.verify(prefix)
    assert not HashChainLedger.verify(prefix, expected_head_hash=trusted_head)


def test_reordering_is_detected():
    ledger = HashChainLedger()
    ledger.append({"n": 1})
    ledger.append({"n": 2})
    ledger.append({"n": 3})
    assert not HashChainLedger.verify(list(reversed(ledger.entries)))


def test_empty_chain_verifies():
    assert HashChainLedger.verify(())


def test_mutating_original_nested_payload_cannot_alter_history():
    ledger = HashChainLedger()
    payload = {"event": "ADMIT", "detail": {"brick": "x", "caps": ["read"]}}
    entry = ledger.append(payload)
    payload["detail"]["brick"] = "EVIL"
    payload["detail"]["caps"].append("write")
    assert ledger.entries[0].payload == {"event": "ADMIT", "detail": {"brick": "x", "caps": ["read"]}}
    assert ledger.entries[0].entry_hash == entry.entry_hash
    assert HashChainLedger.verify(ledger.entries)


def test_mutating_returned_entries_cannot_alter_history():
    ledger = HashChainLedger()
    ledger.append({"a": {"b": 1}})
    returned = ledger.entries
    returned[0].payload["a"]["b"] = 2
    returned[0].payload["injected"] = True
    assert not HashChainLedger.verify(returned)
    assert ledger.entries[0].payload == {"a": {"b": 1}}
    assert HashChainLedger.verify(ledger.entries)


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf")])
def test_non_standard_json_numbers_are_rejected(bad):
    ledger = HashChainLedger()
    with pytest.raises(ValueError):
        ledger.append({"x": bad})
    assert ledger.entries == ()


def test_hashes_for_valid_payloads_are_unchanged():
    import hashlib, json
    payload = {"z": 1, "a": [1, 2, {"k": "v"}], "u": "ä"}
    body = {"sequence": 0, "previous_hash": "0" * 64, "payload": payload}
    legacy = hashlib.sha256(json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")).hexdigest()
    assert HashChainLedger().append(payload).entry_hash == legacy
