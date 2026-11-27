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
