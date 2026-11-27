# Memory and Affective Physiology Clip Brick

**Brick ID:** `ava.memory-affective-physiology`  
**Version:** `0.1.0`  
**Status:** Research reference implementation, not production-certified  
**Admission:** Add-only package; no protected core files are modified.

## Purpose

Provide bounded HOT/WARM/COLD memory staging, append-only COLD event framing, non-destructive contradiction links, a bounded affective state used only for cognitive resource allocation, isolated dream-result labels, and a fail-closed sleep/wake gate.

## Interfaces

- `MemoryBraid.commit_observation(..., assurance=...)`: requires source lineage, contradiction review, gateway checks, and a non-empty certification reference. It rejects simulated data.
- `MemoryBraid.link_contradiction(left_id, right_id)`: appends a relationship event without mutating either record.
- `MemoryBraid.retrieve(..., limit=...)`: bounded retrieval (1..7).
- `MemoryBraid.release_hot()`: releases volatile HOT cache entries only.
- `AffectiveState`: validates valence/arousal and computes bounded attention, retrieval, and scenario budgets.
- `run_dream_sandbox(...)`: emits only `SIMULATED_STATE` records, with a maximum of three.
- `transition_sleep(...)`: failed wake integrity check enters `RECOVERY_SLEEP`.

## Security invariants

1. Affective state is not accepted by authorization, trust, payment, certification, or memory admission APIs.
2. Affect changes resource allocation only; it does not change evidence or trust scores.
3. Simulated dream outputs cannot be committed as observations.
4. Memory admission fails closed unless every required assurance field is present.
5. Contradictory records remain intact; links are separately appended.
6. HOT/WARM caches are bounded. Releasing HOT does not delete COLD history.
7. COLD records use length-prefixed canonical JSON and a SHA-256 chain with fsync after append.
8. Hash chaining is not tamper-proof storage. The expected head must be independently protected/anchored; keys, immutable storage, replay protection, crash recovery, and cross-process locking remain production work.

## Deliberate limitations

- The current reference scans and verifies COLD records on demand, so it does not retain an unbounded full-record index in RAM. This is intentionally simple and may be slow for large archives; a bounded, verified on-disk index is future work.
- It does not implement authenticated identities, signatures, independent SB712 witnesses, policy service integration, OS-level resource isolation, encrypted storage, or multi-process locking.
- `certification_id` is a required reference string, not a cryptographic certificate or proof of actual certification.
- Sleep states are lifecycle primitives, not an autonomous scheduler.
- No subjective feeling, consciousness, or biological experience is claimed.

## Test scope

The accompanying tests exercise local reference behavior only. They do not prove production security, integrated OASIS operation, military suitability, or hardware resilience.
