# Security Boundaries and Operating Rules

**Status:** DESIGN baseline. Host-level enforcement and integration evidence are not yet established here.

## 1. Protected assets

AVA identity keys and epochs; Constitution/Soul Seed/Logic Spine; memory records and lineage; proof ledger and external anchors; policy and capability grants; Clip Brick manifests; checkpoints; user data; audit records; operator credentials; and mode state.

## 2. Trust zones

1. **Offline reasoning zone:** local text-only model and constrained inference bridge. No direct internet, DNS, cloud model, browser, telemetry, remote tools, or online-node route in STRICT_OFFLINE.
2. **Governance zone:** identity, role/scope policy, approvals, capability grants, and signed decision receipts. Must be outside model control.
3. **Protected state zone:** identity, Constitution, memory authority, ledger, checkpoints, and keys. Separate write paths and key custody.
4. **Quarantine zone:** all untrusted ingress, external documents, removable media, node payloads, model-generated candidates, and recovery candidates.
5. **Online transport zone:** untrusted by default. Transport connectivity does not confer data trust or authority.
6. **Operator interface zone:** authenticated user-facing controls. UI state is never authoritative for permission decisions.

## 3. Network and data-flow rules

- STRICT_OFFLINE must be enforced by host/VM/container network policy, not merely by application URL checks or prompts.
- No external LLM fallback. No silent provider switching.
- No browser speech recognition or cloud speech service in the offline profile.
- No direct inbound connection from an online node to the offline brain.
- Ingress is a one-way, explicitly authorized data-transfer workflow: receive → quarantine → scan → validate format/purpose → verify signatures/lineage where applicable → human/policy release → ingest.
- Egress is denied by default. Any exception must be a named, scoped, time-bounded, logged capability with human approval.
- Disable ambient proxy inheritance for local clients; validate actual host routing with packet/firewall tests.
- Offline protected actions are refused, not queued for later execution.

## 4. Authority rules

The model may analyze, summarize, compare, draft, and recommend within its data grant. It cannot:
- Grant itself capabilities or change operator rank.
- Authorize its own output or certify its own memory.
- Change protected Constitution, Soul Seed, Logic Spine, policy, or trusted keys.
- Execute privileged, destructive, external, or irreversible operations without the required external authorization.
- Convert predictions or simulations into observed facts.
- Suppress or erase incident evidence.

Rank is an identity attribute, not permission. Effective authorization is authenticated identity + assigned role + explicit capability + scope + risk + current policy + required approval.

## 5. Fail-closed behavior

Unknown schema, invalid signature, expired credential, replay, missing evidence, digest mismatch, policy conflict, unavailable witness, timeout, unverified recovery source, or out-of-scope request must DEFER, REJECT, or QUARANTINE. No fallback to weaker authentication or broader permissions.

## 6. Evidence and integrity

Hashes and signatures establish integrity/provenance relative to keys and records; they do not prove semantic truth, safety, or correctness. Preserve raw evidence and lineage. Use independently controlled external anchors to detect truncation/fork/rollback. If all keys and all copies are controlled by one adversary, the system cannot claim independent tamper resistance.

## 7. Human control and emergency behavior

Human operators retain responsibility for mission decisions. Emergency freeze may stop affected capabilities and preserve evidence. Recovery is staged and reviewable. There is no hidden memory-wipe mechanism or secret universal bypass. Destructive recovery requires separately authenticated human authorization and a verified recovery plan.

## 8. Prohibited repository content

Never commit classified information, CUI, export-controlled technical data, controlled unclassified personal information, credentials, private keys, operational network maps, vulnerabilities in third-party systems, or sensitive mission details. This public repository is not an approved government information system.
