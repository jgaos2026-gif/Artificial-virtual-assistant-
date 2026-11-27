# DON27BZ02-NV010 — Separate Platform Track

**Relationship to this repository:** supporting platform capability only; not the primary NV012 mission application.  
**Source basis:** AVA for the Military and Navy design, November 2026.

## 1. Keep the topics distinct

The military design describes two different Navy needs:
- **DON27BZ02-NV010 (SBIR):** automated Linux minimization, hardening, scoring, and proof on representative COTS systems.
- **DON27TZ02-NV012 (STTR):** mission training and knowledge assistant grounded in authoritative documents.

The applications may share AVA's governance spine, but neither track borrows the other's deliverables, results, or eligibility requirements. NV012 requires an STTR research-institution partner. Do not imply that the NV010 SBIR path satisfies that requirement.

## 2. NV010 workflow described in the design

baseline → analyze → plan → approve → apply → verify → rollback → report

Analysis is limited to the platform's installed software, running processes, listening services, dependencies, and declared mission profile. A component is unnecessary only when evidence shows it is not running, not required by anything running, and not required by the mission profile. Otherwise retain it or flag it for review.

Differentiators described in the design:
- Explainable 0–100 hardening posture score.
- Baseline and drift detection.
- Approved change plan.
- Retained-functionality regression checks.
- Pre-change checkpoint and exact rollback verification.
- Report of attack-surface changes and unknowns.

## 3. Evidence boundary

The military design reports a demonstration-host result of score 76 → 88, four changes applied, two proposed but not applied, regression 7/7, exact rollback, and 49/49 unit tests. These are claims reported by that design document for a representative unclassified Linux host. They are not independently re-run by this repository and are not STIG/CIS certification, a penetration test, FIPS validation, ATO, or proof of military authorization.

The design explicitly states that the integrated military AVA is not built, the eleven-test acceptance gate has not been run, and no real-hardware offline proof, independent multi-node quorum, or CUI authorization is established.

## 4. Repository boundary

NV010 implementation should be a separate Clip Brick or separately governed project with its own:
- Target platform and baseline definition.
- Mission profile and approved hardening policy.
- Change preview and explicit operator approval.
- Rollback checkpoint and independent post-change verification.
- Regression suite and raw evidence.
- Security review and deployment authorization.

Do not add host-hardening execution to the NV012 learner assistant's model process. The model must never directly execute arbitrary system changes.
