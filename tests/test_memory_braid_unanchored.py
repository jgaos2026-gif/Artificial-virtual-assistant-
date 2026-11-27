import json, hashlib
from contextlib import nullcontext
from ava_military.braid_provenance import *
from ava_military.braid_reader_adapter import _read_jsonl, read_braided_stream
from ava_military.cold_log_tx import TransactionalColdLog

KEY=b"k"*32
def record(i,prev,payload=None):
    body={"index":i,"prev_hash":prev,"payload":payload or {"v":i}}
    return {**body,"entry_hash":hashlib.sha256(canonical(body)).hexdigest()}

def setup_auth(tmp_path):
    snap=ColdSnapshot("s","a","lineage",2,2,"")
    r0=record(0,"0"*64); r1=record(1,r0["entry_hash"])
    snap=ColdSnapshot("s","a","lineage",2,2,r1["entry_hash"],"signed")
    baseline=AnchorBaseline("s","a","lineage",0,1,1,r0["entry_hash"])
    bv=HmacBaselineVerifier(KEY,"lineage")
    baseline=AnchorBaseline(**{**baseline.__dict__,"baseline_proof":bv.sign(baseline)})
    cp=MonotonicCheckpoint("s","a","lineage",2,2,2,r1["entry_hash"])
    cv=HmacMonotonicCheckpointVerifier(KEY)
    cp=MonotonicCheckpoint(**{**cp.__dict__,"auth_mac_hex":cv.sign(cp)})
    classifier=ColdHistoryProvenanceClassifier(expected_lineage_id="lineage",snapshot_verifier=lambda s:True,baseline_verifier=bv,checkpoint_verifier=cv)
    return [r0,r1],snap,baseline,cp,classifier

def test_large_chunk_of_short_lines_is_not_one_oversized_line(tmp_path):
    p=tmp_path/"cold.jsonl"
    p.write_bytes(b'{"a":1}\n' * 9000)  # 72 KB, across multiple 64 KB reads
    records,complete,omitted,diags=_read_jsonl(p,max_records=10000,max_line_bytes=8)
    assert len(records)==9000 and complete and omitted==0
    assert not diags

def test_exact_max_records_at_eof_is_not_false_truncation(tmp_path):
    p=tmp_path/"cold.jsonl"; p.write_bytes(b'{"a":1}\n{"b":2}\n')
    records,complete,omitted,_=_read_jsonl(p,max_records=2,max_line_bytes=20)
    assert len(records)==2 and complete and omitted==0

def test_oversized_line_drain_preserves_following_record(tmp_path):
    p=tmp_path/"cold.jsonl"; p.write_bytes(b'{"long":"'+b'x'*40+b'"}\n{"ok":1}\n')
    records,complete,omitted,diags=_read_jsonl(p,max_records=5,max_line_bytes=12)
    assert len(records)==1 and records[0]=={"ok":1}
    assert not complete and diags

def test_checkpoint_must_bind_chain_and_missing_guard_denies_anchored(tmp_path,monkeypatch):
    records,snap,baseline,cp,classifier=setup_auth(tmp_path)
    wrong=MonotonicCheckpoint(**{**cp.__dict__,"checkpoint_head_hash":"f"*64})
    report=classifier.classify(records,snap,baseline,wrong,consistent_read_guaranteed=True)
    assert not report.authority_verified and report.anchoring_eligible is False
    p=tmp_path/"cold.jsonl"; p.write_text("\n".join(json.dumps(r) for r in records)+"\n")
    class NoGuard:
        def __init__(self): self.path=p
        def append(self,record): pass
    class MissingGuardLog:
        pass  # Deliberately has no _exclusive_guard method.
    view=read_braided_stream(p,classifier=classifier,snapshot=snap,baseline=baseline,checkpoint=cp,cold_log=MissingGuardLog())
    assert view.consistent_read_guaranteed is False
    assert sum(x.status==ProvenanceStatus.ANCHORED for x in view.report.results)==0

def test_baseline_store_rejects_identity_replacement_and_documents_local_floor(tmp_path):
    store=BaselineStore(str(tmp_path/"baseline.json"))
    b=AnchorBaseline("s","a","lineage",0,1,1,"0"*64,"proof")
    store.save(b)
    other=AnchorBaseline("other","a","lineage",0,2,2,"1"*64,"proof")
    import pytest
    with pytest.raises(ValueError): store.save(other)

def test_omitted_count_is_lower_bound_and_never_exact(tmp_path):
    p=tmp_path/"cold.jsonl"; p.write_bytes(b'{"a":1}\n{"b":2}\n{"c":3}\n')
    records,complete,omitted,_=_read_jsonl(p,max_records=1,max_line_bytes=20)
    assert len(records)==1 and not complete and omitted>=1

def test_custom_checkpoint_verifier_cannot_bypass_chain_head_binding(tmp_path):
    records,snap,baseline,cp,_=setup_auth(tmp_path)
    class AlwaysTrueVerifier:
        def verify_checkpoint(self, checkpoint, snapshot):
            return True
    classifier=ColdHistoryProvenanceClassifier(expected_lineage_id="lineage",
        snapshot_verifier=lambda s:True,baseline_verifier=HmacBaselineVerifier(KEY,"lineage"),
        checkpoint_verifier=AlwaysTrueVerifier())
    wrong=MonotonicCheckpoint(**{**cp.__dict__,"checkpoint_head_hash":"e"*64})
    report=classifier.classify(records,snap,baseline,wrong,consistent_read_guaranteed=True)
    assert report.authority_verified is False
    assert report.anchoring_eligible is False

def test_snapshot_head_must_match_inspected_chain(tmp_path):
    records,snap,baseline,cp,classifier=setup_auth(tmp_path)
    wrong=ColdSnapshot(snap.stream_id,snap.authority_id,snap.lineage_id,
        snap.generation,snap.record_count,"d"*64,snap.signature)
    report=classifier.classify(records,wrong,baseline,cp,consistent_read_guaranteed=True)
    assert report.authority_verified is False
    assert report.anchoring_eligible is False

def test_baseline_store_rejects_independent_record_count_rollback(tmp_path):
    store=BaselineStore(str(tmp_path/"baseline.json"))
    store.save(AnchorBaseline("s","a","lineage",0,1,10,"0"*64,"proof"))
    import pytest
    with pytest.raises(ValueError,match="record count"):
        store.save(AnchorBaseline("s","a","lineage",0,2,9,"1"*64,"proof"))

def test_checkpoint_must_match_current_snapshot_not_just_valid_prefix(tmp_path):
    records,snap,baseline,cp,_=setup_auth(tmp_path)
    class AlwaysTrueVerifier:
        def verify_checkpoint(self, checkpoint, snapshot): return True
    classifier=ColdHistoryProvenanceClassifier(expected_lineage_id="lineage",
        snapshot_verifier=lambda s:True,baseline_verifier=HmacBaselineVerifier(KEY,"lineage"),
        checkpoint_verifier=AlwaysTrueVerifier())
    stale=MonotonicCheckpoint("s","a","lineage",1,1,1,records[0]["entry_hash"],"authenticated-old")
    report=classifier.classify(records,snap,baseline,stale,consistent_read_guaranteed=True)
    assert report.authority_verified is False
    assert report.anchoring_eligible is False


def test_reader_mints_checkpoint_session_inside_shared_lock(tmp_path):
    from ava_military.avo_provenance_gate import build_avo_provenance_summary
    records, snap, baseline, cp, classifier = setup_auth(tmp_path)
    path = tmp_path / "cold.jsonl"
    path.write_text("".join(json.dumps(row) + "\n" for row in records))
    checks = []
    view = read_braided_stream(
        path, classifier=classifier, snapshot=snap, baseline=baseline, checkpoint=cp,
        pre_read_check=lambda: checks.append("pre") or True,
        post_read_check=lambda: checks.append("post") or True,
    )
    assert checks == ["pre", "post"]
    assert view.consistent_read_guaranteed
    assert view.read_session is not None and view.read_session.current_across_read
    summary = build_avo_provenance_summary(view)
    assert summary.checkpoint_current_at_read
