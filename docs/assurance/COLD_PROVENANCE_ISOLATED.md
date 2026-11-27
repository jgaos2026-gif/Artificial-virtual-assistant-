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


## Shared cross-process lock

The isolated reference writer and reader now derive one advisory lock identity
from the canonical resolved COLD resource path using
`shared_cross_process_lock.lock_path_for()`. The lock file is persistent and
must not be unlinked while a process may hold it. Cooperating processes on the
same host serialize reads and writes by entering the same exclusive lock.

This is an advisory protocol, not a mandatory access-control boundary. A
process with filesystem write access can bypass it. The adversarial test writes
directly to the COLD file while the reader holds the lock and checks that
pre/post content currency detects the mutation. A successful lock acquisition
does not establish that all writers are cooperative.

The reader's `consistent_read_guaranteed` flag means that this read operation
entered the shared advisory lock contract. It does not mean the file cannot be
modified by a privileged or uncooperative process, nor does it prove distributed
locking across hosts or network filesystems.

## AVO summary gate

`avo_provenance_gate.py` is a read-only adapter over the actual
`ProvenanceReport` and `BraidedStreamSnapshotView` fields. It does not create
record classifications, advance checkpoints, certify evidence, or grant Clip
Brick authority. Missing raw identity fields remain absent. Duplicate raw
record indices are rejected.

The guarded read API owns the shared lock and runs pre-read and post-read
currency checks around the read callback. The resulting session object is an
API capability intended to prevent accidental caller assertion. Python module
privacy is not a security boundary against hostile code running in the same
interpreter. AVO must run inside a controlled process boundary.

## Acceptance gate status

The following acceptance areas are pending execution against the final branch
commit SHA. A test definition is not a test result.

1. NOT YET RUN — actual branch Gate 1 interface compatibility.
2. NOT YET RUN — read-only AVO behavior; no trust promotion or certification.
3. NOT YET RUN — raw identity mapping and duplicate-index rejection.
4. NOT YET RUN — guarded pre-read/post-read session behavior.
5. NOT YET RUN — cross-process lock serialization.
6. NOT YET RUN — concurrent writer behavior and unique temporary files.
7. NOT YET RUN — durability failure behavior.
8. NOT YET RUN — snapshot signature and checkpoint binding.
9. NOT YET RUN — post-read currency and uncooperative-writer detection.
10. NOT YET RUN — full-store rollback limitation.
11. NOT YET RUN — complete regression suite and CI on the final SHA.

The current branch adds shared locking and the AVO read-only adapter. It does
not yet implement the proposed file-backed checkpoint custody store, unique
custody temp files, fsync ambiguity exception, or independent monotonic
custody. Those remain open engineering work and must not be marked accepted.
