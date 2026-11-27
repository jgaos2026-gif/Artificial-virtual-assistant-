"""Read-only historical COLD provenance classification.

This module is isolated from MemoryBraid and from the protected authority spine.
Local HMAC helpers are test/reference mechanisms, not independent anti-rollback custody.
"""
from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
import hashlib, hmac, json
from typing import Callable, Iterable, Protocol

def canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")

def sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()

class ProvenanceStatus(str, Enum):
    ANCHORED = "ANCHORED"
    UNANCHORED = "UNANCHORED"
    INVALID = "INVALID"
    NOT_INSPECTED = "NOT_INSPECTED"

@dataclass(frozen=True)
class ColdSnapshot:
    stream_id: str
    authority_id: str
    lineage_id: str
    generation: int
    record_count: int
    head_hash: str
    signature: str = ""

@dataclass(frozen=True)
class AnchorBaseline:
    stream_id: str
    authority_id: str
    lineage_id: str
    anchor_start_index: int
    baseline_generation: int
    baseline_record_count: int
    baseline_head_hash: str
    baseline_proof: str = ""

@dataclass(frozen=True)
class MonotonicCheckpoint:
    stream_id: str
    authority_id: str
    lineage_id: str
    seq: int
    checkpoint_generation: int
    checkpoint_record_count: int
    checkpoint_head_hash: str
    auth_mac_hex: str = ""

@dataclass(frozen=True)
class RecordResult:
    index: int
    status: ProvenanceStatus
    reason: str

@dataclass(frozen=True)
class ProvenanceReport:
    results: tuple[RecordResult, ...]
    inspection_complete: bool
    evidence_available: bool
    consistent_read_guaranteed: bool
    authority_verified: bool
    cold_evidence_verified: bool
    anchoring_eligible: bool
    omitted_records_count: int
    omitted_count_exact: bool
    diagnostics: tuple[str, ...]

class CheckpointVerifier(Protocol):
    def verify_checkpoint(self, checkpoint: MonotonicCheckpoint, snapshot: ColdSnapshot) -> bool: ...

class BaselineStore:
    """Atomic local baseline file. Save compares against the currently persisted file only.

    Restoring an older copy of this entire file defeats this local floor. Production
    anti-rollback requires separately administered, non-rollbackable custody.
    """
    def __init__(self, path, max_bytes: int = 16384):
        self.path = path
        self.max_bytes = max_bytes
    def load_readonly(self) -> AnchorBaseline | None:
        try:
            with open(self.path, "rb") as f:
                raw = f.read(self.max_bytes + 1)
            if len(raw) > self.max_bytes: raise ValueError("baseline exceeds size limit")
            obj = json.loads(raw, object_pairs_hook=self._unique)
            if set(obj) != {"stream_id","authority_id","lineage_id","anchor_start_index","baseline_generation","baseline_record_count","baseline_head_hash","baseline_proof"}:
                raise ValueError("baseline schema mismatch")
            return AnchorBaseline(**obj)
        except FileNotFoundError:
            return None
    @staticmethod
    def _unique(pairs):
        d={}
        for k,v in pairs:
            if k in d: raise ValueError("duplicate JSON key")
            d[k]=v
        return d
    def save(self, baseline: AnchorBaseline) -> None:
        old=self.load_readonly()
        if old is not None:
            identity=(old.stream_id,old.authority_id,old.lineage_id)
            new_identity=(baseline.stream_id,baseline.authority_id,baseline.lineage_id)
            if identity != new_identity: raise ValueError("baseline identity replacement requires explicit migration")
            if (baseline.baseline_generation,baseline.baseline_record_count) < (old.baseline_generation,old.baseline_record_count):
                raise ValueError("baseline rollback refused")
        import os, tempfile
        parent=os.path.dirname(os.path.abspath(self.path))
        os.makedirs(parent,exist_ok=True)
        fd,tmp=tempfile.mkstemp(prefix=".baseline-",dir=parent)
        try:
            with os.fdopen(fd,"wb") as f:
                raw=canonical(baseline.__dict__)
                if len(raw)>self.max_bytes: raise ValueError("baseline exceeds size limit")
                f.write(raw); f.flush(); os.fsync(f.fileno())
            os.replace(tmp,self.path)
            if os.name != "nt":
                dfd=os.open(parent,os.O_RDONLY)
                try: os.fsync(dfd)
                finally: os.close(dfd)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)

class HmacBaselineVerifier:
    """Reference HMAC verifier; key custody must be external in production."""
    def __init__(self,key: bytes, expected_lineage_id: str):
        if len(key)<32: raise ValueError("key must be at least 32 bytes")
        self.key=key; self.expected_lineage_id=expected_lineage_id
    def sign(self,b: AnchorBaseline) -> str:
        body={k:v for k,v in b.__dict__.items() if k!="baseline_proof"}
        return hmac.new(self.key,canonical(body),hashlib.sha256).hexdigest()
    def verify(self,b: AnchorBaseline,s: ColdSnapshot) -> bool:
        return (b.stream_id==s.stream_id and b.authority_id==s.authority_id and
                b.lineage_id==self.expected_lineage_id==s.lineage_id and
                hmac.compare_digest(b.baseline_proof,self.sign(b)))

class HmacMonotonicCheckpointVerifier:
    """Authenticates checkpoint contents, but is NOT a non-rollbackable store."""
    def __init__(self,key: bytes):
        if len(key)<32: raise ValueError("key must be at least 32 bytes")
        self.key=key
    def sign(self,c: MonotonicCheckpoint) -> str:
        body={k:v for k,v in c.__dict__.items() if k!="auth_mac_hex"}
        return hmac.new(self.key,canonical(body),hashlib.sha256).hexdigest()
    def verify_checkpoint(self,c: MonotonicCheckpoint,s: ColdSnapshot) -> bool:
        return (c.stream_id==s.stream_id and c.authority_id==s.authority_id and
                c.lineage_id==s.lineage_id and c.seq==c.checkpoint_generation and
                c.checkpoint_generation==c.checkpoint_record_count and
                hmac.compare_digest(c.auth_mac_hex,self.sign(c)))

class ColdHistoryProvenanceClassifier:
    def __init__(self, *, expected_lineage_id: str, snapshot_verifier: Callable[[ColdSnapshot],bool],
                 baseline_verifier: HmacBaselineVerifier, checkpoint_verifier: CheckpointVerifier):
        if not expected_lineage_id: raise ValueError("expected_lineage_id is required")
        if not callable(getattr(checkpoint_verifier,"verify_checkpoint",None)):
            raise TypeError("checkpoint verifier must implement verify_checkpoint")
        self.lineage=expected_lineage_id; self.snapshot_verifier=snapshot_verifier
        self.baseline_verifier=baseline_verifier; self.checkpoint_verifier=checkpoint_verifier
    def classify(self, records: Iterable[dict], snapshot: ColdSnapshot, baseline: AnchorBaseline,
                 checkpoint: MonotonicCheckpoint, *, consistent_read_guaranteed: bool,
                 inspection_complete: bool=True, omitted_records_count: int=0,
                 omitted_count_exact: bool=True) -> ProvenanceReport:
        diagnostics=[]
        try:
            authority=(snapshot.lineage_id==self.lineage and self.snapshot_verifier(snapshot)
                       and self.baseline_verifier.verify(baseline,snapshot)
                       and self.checkpoint_verifier.verify_checkpoint(checkpoint,snapshot))
        except Exception:
            authority=False
        results=[]; prev="0"*64; valid=True; prefix_heads={0:prev}
        material=list(records)
        for i,r in enumerate(material):
            try:
                if not isinstance(r,dict) or set(r)!={"index","prev_hash","payload","entry_hash"}: raise ValueError("schema")
                if type(r["index"]) is not int or r["index"]!=i: raise ValueError("index")
                if r["prev_hash"]!=prev: raise ValueError("previous hash")
                digest=sha256(canonical({"index":i,"prev_hash":prev,"payload":r["payload"]}))
                if not hmac.compare_digest(str(r["entry_hash"]),digest): raise ValueError("digest")
                prev=digest; prefix_heads[i+1]=prev
            except Exception as exc:
                valid=False; results.append(RecordResult(i,ProvenanceStatus.INVALID,f"invalid record: {exc}"))
                # Continue inspecting, but chain cannot become trusted again.
                continue
            status=ProvenanceStatus.UNANCHORED
            reason="no authenticated anchor boundary"
            if authority and valid and i>=baseline.anchor_start_index:
                boundary=baseline.baseline_record_count
                cp_count=checkpoint.checkpoint_record_count
                boundary_ok=(boundary in prefix_heads and prefix_heads[boundary]==baseline.baseline_head_hash)
                cp_ok=(cp_count in prefix_heads and prefix_heads[cp_count]==checkpoint.checkpoint_head_hash)
                if boundary_ok and cp_ok and i>=boundary and i<cp_count:
                    status=ProvenanceStatus.ANCHORED; reason="record falls within authenticated baseline/checkpoint chain"
            results.append(RecordResult(i,status,reason))
        if not inspection_complete:
            results.append(RecordResult(len(material),ProvenanceStatus.NOT_INSPECTED,"input inspection incomplete"))
        evidence=valid and inspection_complete and omitted_records_count==0
        eligible=bool(authority and evidence and consistent_read_guaranteed and all(x.status!=ProvenanceStatus.INVALID for x in results))
        if not authority: diagnostics.append("authority verification failed")
        if not consistent_read_guaranteed: diagnostics.append("consistent read was not guaranteed")
        if omitted_records_count: diagnostics.append("record limit truncated input; omitted count is a lower bound")
        anchored=sum(x.status==ProvenanceStatus.ANCHORED for x in results)
        return ProvenanceReport(tuple(results),inspection_complete,True,consistent_read_guaranteed,bool(authority),bool(evidence),eligible,omitted_records_count,False if omitted_records_count else omitted_count_exact,tuple(diagnostics))
