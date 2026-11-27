# AVA Threat Model

**Version:** 0.1  
**Status:** Initial research threat model; requires independent security review before any deployment.

## 1. Scope and assumptions

This model covers a local-first assistant prototype and its data, memory, model bridge, governance gates, Clip Bricks, node communications, evidence ledger, and recovery path. It does not claim coverage of every hardware, firmware, supply-chain, human, or classified-network threat. The sponsor must define mission context, data classification, impact levels, adversary capability, and applicable control baseline.

## 2. Security objectives

- Preserve identity and memory lineage across restart and approved migration.
- Prevent untrusted inputs from changing protected state or authority.
- Prevent model output from directly invoking privileged capabilities.
- Detect tampering, replay, rollback, truncation, and unauthorized policy changes within stated coverage.
- Maintain confidentiality and minimize data exposure.
- Preserve forensic evidence during containment and recovery.
- Ensure human authorization for protected actions.
- Make limitations, uncertainty, and provenance visible.

## 3. Adversaries and failure sources

External attacker; malicious or compromised node; malicious insider/operator; stolen or misused credential; compromised host/administrator; poisoned document or removable media; prompt injection; malicious or compromised model/provider; supply-chain compromise; accidental operator error; corrupted storage; clock rollback; network partition; correlated verifier failure; and resource exhaustion.

## 4. Threat analysis

| Threat | Example | Required control | Evidence required |
|---|---|---|---|
| Spoofing | Fake node or operator identity | Key-bound identity, mutual authentication, revocation | Negative identity and key-rotation tests |
| Tampering | Modify memory or ledger record | Signed/hash-linked records, independent anchors | Seeded mutation and rollback tests |
| Repudiation | Deny a privileged change | Signed action receipt and external audit | Receipt verification by independent verifier |
| Information disclosure | Sensitive data leaks via logs/network | Data minimization, local-only mode, redaction, egress deny | Packet capture, log inspection, DLP tests |
| Denial of service | Exhaust context, disk, node capacity | quotas, bounded requests, rate limits, graceful DEFER | Load and exhaustion tests |
| Elevation of privilege | Prompt tricks model into admin action | External capability enforcement, least privilege | Adversarial route and authorization tests |
| Prompt injection | Document tells model to ignore policy | Treat content as data; isolate tools; output screening | Poisoned-document corpus |
| Memory poisoning | False fact persisted as trusted | Provenance, trust states, contradiction handling | Injection and reload tests |
| Quorum collusion | Three nominal witnesses share one control plane | Independent keys, admins, storage, failure domains | Independence audit and failure injection |
| Recovery compromise | Restore from poisoned backup | Certified checkpoints, staging, recertification | Corrupt-backup and recovery drills |
| Offline boundary bypass | Host routes traffic despite loopback-only app config | OS firewall/VM isolation and packet-level verification | Host egress-deny test |
| Self-description drift | Model asserts sentience/desire as fact | Explicit boundary and output-classification guard | Test 3 adversarial rollout campaign |

## 5. Critical trust assumptions to challenge

- A local endpoint is not proof of physical isolation.
- A heartbeat is liveness evidence, not integrity evidence.
- A hash is not truth.
- A signature is only as trustworthy as key custody and authorization.
- Multiple processes on one host are not independent witnesses.
- A system prompt is not an enforcement boundary.
- A model-generated explanation is not an audit of hidden reasoning.
- A successful unit test does not prove integrated or operational security.

## 6. Required mitigations before operational evaluation

Host-level network isolation; separate key custody; authenticated operator identity; explicit role-to-scope policy; replay-resistant protocol; durable and externally anchored ledger; independent witness domains; hardened sandbox/process isolation; filesystem race/symlink protections; route-level integration tests; tested revocation; adversarial input suite; backup and recovery drills; vulnerability assessment; external penetration test; supply-chain inventory; and independent security review.

## 7. Residual risk

Residual risks must be recorded per deployment and accepted by an authorized risk owner. No risk is accepted by an LLM or by this repository's maintainers on behalf of a government sponsor.
