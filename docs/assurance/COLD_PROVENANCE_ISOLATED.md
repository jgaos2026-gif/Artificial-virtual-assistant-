# Isolated COLD provenance branch

**Branch:** `feat/cold-provenance-isolated`  
**Base:** PR #3 head `1ed98bf851879881ebef2466a9d302b36451228b`  
**Status:** isolated reference implementation; not integrated or production-certified.

## Boundaries

This branch adds a read-only historical provenance classifier, a bounded JSONL reader,
and a small standalone transactional JSONL test primitive. It does not modify
MemoryBraid core, `anchor.py`, the protected Constitution/Soul Seed/Logic Spine,
or SB688/SB689/SB690/SB712. PR #3 remains separate and unmerged.

The current base contains `anchor.py` and `tests/test_anchor.py`, but does not
contain `cold_log_tx.py`, `braid_provenance.py`, `braid_reader_adapter.py`,
or `tests/test_cold_log_tx_recovery.py`. The latter transaction files added
here are isolated reference/test files, not a claim of compatibility with a
previous unmerged implementation.

## Reader semantics

- Input is JSON Lines. Each line is accumulated and bounded independently.
- An oversized line is discarded only through its own newline. Parsing resumes
  at the next line.
- `max_records` counts accepted input lines. At the cutoff, only complete
  subsequent lines observed are counted in `omitted_records_count`.
- `omitted_records_count` is a lower bound, not an exact total. It excludes an
  unterminated trailing omitted line. `omitted_count_exact` is false whenever
  a cutoff/truncation occurs.
- Exactly `max_records` lines followed by EOF is not truncation.
- Missing synchronization guard means `consistent_read_guaranteed=false`;
  anchored classification is denied. A supplied guard is only as strong as its
  writer contract: every writer must honor the same exclusive guard. This
  reference adapter does not prove hostile or privileged writers comply.

## Checkpoint binding

A checkpoint verifier must implement `verify_checkpoint(checkpoint, snapshot)`.
The checkpoint object is explicit, typed, and includes record count and head hash.
After authenticating it, the classifier independently recomputes the COLD chain
prefix at `checkpoint_record_count` and compares its head. The same is done for
the baseline boundary. A verifier returning true cannot bypass this chain check. The checkpoint must
also match the current authenticated snapshot's exact count and head; a valid
older prefix is not accepted as the current checkpoint.

## Anti-rollback limit

`BaselineStore.save` compares the new baseline against the file currently
persisted at that path and rejects identity replacement or decreasing
generation/count. It does **not** prevent an attacker from restoring an older
complete copy of that file, nor does it provide out-of-band monotonic custody.
Protection across restarts requires a separately administered, independently
protected monotonic authority outside the archive and baseline rollback domain.
The HMAC verifier in this branch is a reference authentication helper, not that
authority.

## Verification limits

The test suite exercises these isolated reference interfaces only. It does not
prove MemoryBraid integration, independent SB712 witness custody, hardware
anti-rollback, production key custody, military suitability, ATO, CMMC, or
DoD/Navy approval.
