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


def test_deletion_and_reordering_are_detected():
    ledger = HashChainLedger()
    ledger.append({"n": 1})
    ledger.append({"n": 2})
    ledger.append({"n": 3})
    assert not HashChainLedger.verify(ledger.entries[:2])
    assert not HashChainLedger.verify(list(reversed(ledger.entries)))


def test_empty_chain_verifies():
    assert HashChainLedger.verify(())
