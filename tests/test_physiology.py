import pytest

from ava_military.physiology import (
    AffectiveState, Assurance, MemoryBraid, SleepMode, TrustStage,
    run_dream_sandbox, transition_sleep,
)


def assurance(**changes):
    values = dict(
        source_lineage_verified=True,
        contradictions_checked=True,
        gateway_checks_passed=True,
        certification_id="cert-test-001",
    )
    values.update(changes)
    return Assurance(**values)


def test_memory_requires_all_assurance_gates(tmp_path):
    memory = MemoryBraid(tmp_path / "cold.bin")
    with pytest.raises(PermissionError):
        memory.commit_observation(
            source_id="manual:v1", content="valve status normal",
            assurance=assurance(gateway_checks_passed=False),
        )
    assert not (tmp_path / "cold.bin").exists()


def test_commit_writes_cold_and_loads_hot_warm(tmp_path):
    memory = MemoryBraid(tmp_path / "cold.bin")
    record = memory.commit_observation(
        source_id="manual:v1", content="valve status normal",
        assurance=assurance(), observed_at=100.0,
    )
    assert record.stage is TrustStage.COMMIT
    assert record.record_id in memory.hot
    assert record.record_id in memory.warm
    assert memory.verify_cold()


def test_cold_framing_detects_truncation_and_tampering(tmp_path):
    path = tmp_path / "cold.bin"
    memory = MemoryBraid(path)
    memory.commit_observation(source_id="s", content="first", assurance=assurance(), observed_at=1)
    with path.open("ab") as stream:
        stream.write(b"\x00\x00")
    with pytest.raises(ValueError, match="truncated"):
        memory.verify_cold()


def test_contradictions_are_linked_without_mutating_records(tmp_path):
    memory = MemoryBraid(tmp_path / "cold.bin")
    a = memory.commit_observation(source_id="sensor:A", content="temperature normal", assurance=assurance(), observed_at=1)
    b = memory.commit_observation(source_id="sensor:B", content="temperature high", assurance=assurance(), observed_at=2)
    original = (memory.record(a.record_id), memory.record(b.record_id))
    link = memory.link_contradiction(a.record_id, b.record_id)
    assert link.left_id == a.record_id and link.right_id == b.record_id
    assert (memory.record(a.record_id), memory.record(b.record_id)) == original
    assert memory.contradiction_links == (link,)


def test_ram_release_does_not_delete_cold_history(tmp_path):
    memory = MemoryBraid(tmp_path / "cold.bin")
    record = memory.commit_observation(source_id="s", content="persist me", assurance=assurance())
    head = memory.head_hash
    assert memory.release_hot() == 1
    assert not memory.hot
    assert memory.record(record.record_id) == record
    assert memory.head_hash == head
    assert memory.verify_cold()


def test_hot_and_warm_limits_are_enforced(tmp_path):
    memory = MemoryBraid(tmp_path / "cold.bin", hot_limit=2, warm_limit=2)
    records = [
        memory.commit_observation(source_id="s", content=f"item-{i}", assurance=assurance(), observed_at=i)
        for i in range(4)
    ]
    assert len(memory.hot) == 2
    assert len(memory.warm) == 2
    assert memory.record(records[0].record_id) is not None


def test_simulated_state_cannot_be_committed(tmp_path):
    memory = MemoryBraid(tmp_path / "cold.bin")
    with pytest.raises(PermissionError, match="SIMULATED_STATE"):
        memory.commit_observation(
            source_id="dream", content="hypothesis", assurance=assurance(), simulated=True,
        )


def test_affect_is_bounded_and_only_modulates_cognitive_budgets():
    calm = AffectiveState(valence=-1.0, arousal=0.0, context_id="ctx")
    alert = AffectiveState(valence=1.0, arousal=1.0, context_id="ctx")
    assert calm.attention_multiplier == pytest.approx(0.8)
    assert alert.attention_multiplier == pytest.approx(1.2)
    assert calm.retrieval_breadth == 3
    assert alert.retrieval_breadth == 7
    assert calm.simulation_branches == 1
    assert alert.simulation_branches == 3
    with pytest.raises(ValueError):
        AffectiveState(valence=1.1, arousal=0.5, context_id="bad")


def test_dream_results_are_bounded_and_marked_simulated():
    state = AffectiveState(valence=0.2, arousal=1.0, context_id="dream-context")
    results = run_dream_sandbox(state, ["a", "b", "c", "d"])
    assert len(results) == 3
    assert all(result.label == "SIMULATED_STATE" for result in results)


def test_wake_verification_failure_enters_recovery_sleep():
    assert transition_sleep(SleepMode.DEEP_SLEEP, SleepMode.AWAKE, integrity_ok=False) is SleepMode.RECOVERY_SLEEP
    assert transition_sleep(SleepMode.DEEP_SLEEP, SleepMode.AWAKE, integrity_ok=True) is SleepMode.AWAKE


def test_cold_records_are_retrievable_after_reopening_without_unbounded_index(tmp_path):
    path = tmp_path / "cold.bin"
    first = MemoryBraid(path, hot_limit=1, warm_limit=1)
    one = first.commit_observation(source_id="s", content="older record", assurance=assurance(), observed_at=1)
    first.commit_observation(source_id="s", content="newer record", assurance=assurance(), observed_at=2)
    reopened = MemoryBraid(path, hot_limit=1, warm_limit=1)
    restored = reopened.record(one.record_id)
    assert restored == one
    assert len(reopened.hot) <= 1
    assert len(reopened.warm) <= 1
