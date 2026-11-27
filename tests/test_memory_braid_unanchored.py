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
    p.write_bytes(b'{"a":1}\n{"b":2}\n{"c":3}\n')
    records,complete,omitted,diags=_read_jsonl(p,max_records=10,max_line_bytes=8)
    assert len(records)==3 and complete and omitted==0
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
    view=read_braided_stream(p,classifier=classifier,snapshot=snap,baseline=baseline,checkpoint=cp,sync_guard=None)
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
