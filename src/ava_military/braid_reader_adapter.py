"""Bounded read-only JSONL adapter for historical COLD evidence."""
from __future__ import annotations
import json, os
from dataclasses import dataclass
from types import MappingProxyType
from .braid_provenance import ColdHistoryProvenanceClassifier, ColdSnapshot, AnchorBaseline, MonotonicCheckpoint, ProvenanceReport, ProvenanceStatus

@dataclass(frozen=True)
class BraidedStreamSnapshotView:
    records: tuple[dict,...]
    report: ProvenanceReport
    cold_evidence_verified: bool
    evidence_available: bool
    inspection_complete: bool
    consistent_read_guaranteed: bool
    omitted_records_count: int
    omitted_count_exact: bool

def _safe_view(value):
    if isinstance(value,dict): return MappingProxyType(dict(value))
    return MappingProxyType({"_malformed":repr(type(value).__name__)})

def _read_jsonl(path, *, max_records=100000, max_line_bytes=1048576):
    if type(max_records) is not int or max_records<1: raise ValueError("max_records must be positive")
    if type(max_line_bytes) is not int or max_line_bytes<1: raise ValueError("max_line_bytes must be positive")
    flags=os.O_RDONLY|getattr(os,"O_NOFOLLOW",0)
    fd=os.open(path,flags); records=[]; buf=bytearray(); omitted=0; line_no=0; complete=True; diagnostics=[]
    try:
        if not __import__("stat").S_ISREG(os.fstat(fd).st_mode): raise ValueError("COLD source must be a regular file")
        eof=False; truncated=False
        while not eof:
            chunk=os.read(fd,65536)
            if not chunk: eof=True
            pos=0
            while pos<len(chunk):
                nl=chunk.find(b"\n",pos)
                end=len(chunk) if nl<0 else nl
                part=chunk[pos:end]
                if not truncated and line_no<max_records:
                    if len(buf)+len(part)>max_line_bytes:
                        diagnostics.append(f"line {line_no} exceeds max_line_bytes")
                        # Drain only through this line's newline; tail remains in chunk.
                        truncated=True; complete=False; buf.clear()
                    else:
                        buf.extend(part)
                else:
                    truncated=True; complete=False
                    if nl>=0: omitted+=1
                    elif eof and part: omitted+=1
                if nl>=0:
                    if not truncated and line_no<max_records:
                        try:
                            item=json.loads(buf.decode("utf-8"))
                            if not isinstance(item,dict): raise ValueError("record must be an object")
                            records.append(item)
                        except Exception as exc: records.append({"_malformed":str(exc)}); diagnostics.append(f"line {line_no} malformed")
                    elif truncated and line_no>=max_records:
                        omitted+=0
                    line_no+=1; buf.clear()
                    if line_no>=max_records: truncated=True; complete=False
                    pos=nl+1
                else:
                    if not truncated and line_no<max_records: buf.extend(b"")
                    pos=len(chunk)
            if eof and buf and not truncated and line_no<max_records:
                try:
                    item=json.loads(buf.decode("utf-8"))
                    if not isinstance(item,dict): raise ValueError("record must be object")
                    records.append(item)
                except Exception as exc: records.append({"_malformed":str(exc)}); diagnostics.append(f"line {line_no} malformed")
                buf.clear()
            if eof and truncated: complete=False
        # Exact cutoff: if exactly max_records terminated by EOF, it is complete.
        if line_no==max_records and eof and not truncated:
            complete=True
    finally: os.close(fd)
    return records,complete,omitted,diagnostics

def read_braided_stream(path, *, classifier: ColdHistoryProvenanceClassifier, snapshot: ColdSnapshot,
                        baseline: AnchorBaseline, checkpoint: MonotonicCheckpoint,
                        max_records=100000,max_line_bytes=1048576, sync_guard=None):
    consistent=callable(sync_guard)
    if consistent:
        with sync_guard():
            records,complete,omitted,diags=_read_jsonl(path,max_records=max_records,max_line_bytes=max_line_bytes)
    else:
        records,complete,omitted,diags=_read_jsonl(path,max_records=max_records,max_line_bytes=max_line_bytes)
    report=classifier.classify(records,snapshot,baseline,checkpoint,consistent_read_guaranteed=consistent,
                                inspection_complete=complete,omitted_records_count=omitted,
                                omitted_count_exact=False if omitted or not complete else True)
    if diags:
        from dataclasses import replace
        report=replace(report,diagnostics=report.diagnostics+tuple(diags))
    verified=report.cold_evidence_verified and report.inspection_complete and not omitted
    return BraidedStreamSnapshotView(tuple(dict(x) for x in records),report,verified,True,complete,consistent,omitted,False if omitted else True)
