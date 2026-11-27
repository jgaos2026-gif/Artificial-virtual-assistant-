# AVA Engineering Terminology and Claim Standard

**Status:** Controlled vocabulary for engineering, assurance, installation, and external technical communications.

Preserve canonical JGA project names, but pair them with precise engineering descriptions. A project term is not evidence that the named capability has been implemented.

## 1. Product and architecture names

| Canonical term | Professional engineering description | Usage rule |
|---|---|---|
| **AVA — Artificial Virtual Assistant** | The system identity and governed assistant application being developed | Do not imply that a complete integrated runtime exists until end-to-end evidence is recorded |
| **Digital Organism** | AVA's canonical architecture concept for persistent identity, state, memory, and governed lifecycle | Project terminology, not a claim of biological life, sentience, consciousness, or subjective experience |
| **OASIS** | The intended local runtime and operating environment for AVA | Integration is not complete until the actual runtime is connected and tested |
| **Soul Seed** | The canonical values charter: COMPASSION, DECENCY, and LOVE | A values concept; not a cryptographic seed, root key, or authorization credential |
| **Logic Spine** | Protected policy and invariant layer | Not a hardware or cryptographic root of trust unless independent key custody and enforcement exist |
| **Spine / integrity spine** | Integrity, provenance, admission, and governed state-transition services | Name the actual module/interface; do not imply every SB component is integrated |
| **Clip Brick** | Versioned, bounded capability package with manifest, interfaces, permissions, evidence, lifecycle, revocation, and rollback | Use “capability package” on first reference |
| **Braid** | Project-specific term for coordinated multi-stage workflows or linked state/evidence structures | Not a standardized computing or cryptographic primitive; define the exact implementation |
| **Stitch** | Project term for the connective protocol and memory/state fabric | Describe the implemented protocol and version |
| **Phoenix** | Recovery orchestration and verified restoration workflow | Not an independent authority, backup, or guarantee of automatic repair |
| **IronLink** | Intended liveness, continuity, and communications interface | A heartbeat does not establish identity, trust, or authorization |
| **Node Brigade / Trios** | Proposed distributed verifier, observer, containment, and recovery roles | Independent assurance requires separate identities, keys, administration, storage, and failure domains |

## 2. Memory and cognition

| Canonical term | Professional engineering description | Usage rule |
|---|---|---|
| **COLD** | Durable archival record store | State the format, integrity mechanism, retention, encryption, and external anchoring status |
| **WARM** | Intermediate staging and retrieval tier | Do not claim active WARM operation unless data movement is implemented and measured |
| **HOT** | Bounded active working cache | Distinguish cache contents from durable or authoritative records |
| **Memory Braid** | Proposed lineage-aware lifecycle across archival, staging, and active tiers | Reference modules do not prove full OASIS integration |
| **Cognition braid** | Four-domain analysis workflow: state, evidence/trust, consequence/future, recovery/action | A project reasoning workflow, not a validated cognitive-science model |
| **Affective Braid / affective state** | Bounded advisory state used only to modulate permitted cognitive resource budgets | Never describe it as subjective emotion, feeling, consciousness, or an authority signal |
| **Dream / dream sandbox** | Isolated scenario-generation process whose outputs are labeled simulated | Simulated output must never be promoted silently to observed fact or trusted memory |

## 3. Security and assurance terms

| Term | Correct meaning | Do not confuse it with |
|---|---|---|
| **Integrity** | Evidence that data has not changed relative to a defined digest, signature, or trusted reference | Truth, correctness, safety, or authorization |
| **Authenticity** | Evidence that an artifact or message came from the holder of a particular credential | Current authorization or permission to act |
| **Authorization** | Policy decision for an authenticated principal, action, resource, scope, and time | Identity, rank, UI state, or model output |
| **Provenance** | Traceable origin, lineage, transformations, and custody of data | Semantic truth |
| **Tamper-evident** | Changes can be detected within stated trust and anchoring assumptions | Tamper-proof or impossible for an administrator to alter |
| **External anchor** | Separately protected expected state outside the archive's rollback and writer failure domain | Hash/HMAC file or second directory on the same host |
| **Independent witness** | Verifier with independent identity, keys, administration, storage, and relevant failure domain | Second container or process controlled by the same administrator |
| **Fail closed** | A defined failure or unknown state denies the protected operation and preserves evidence | Catching an exception, returning a warning, or silently falling back |
| **Zero-trust principles** | Explicit identity, least privilege, continuous verification, and no implicit trust based on network location | A claim that the product implements a complete Zero Trust Architecture |
| **Verified** | A named verification procedure passed against specified evidence | Validated, certified, or operationally approved |
| **Validated** | A named validation procedure established that specified requirements or intended use were met | Formal certification or government authorization |
| **Certified** | An authorized certification body issued formal certification for a defined scope | A data field, test fixture, or developer assertion |
| **Quarantine** | State that prevents suspect material from entering protected use while preserving evidence | Deletion or repair |
| **Recovery** | Controlled restoration from a selected checkpoint followed by verification and authorization | Automatic self-healing or automatic re-certification |
| **SIMULATED_CUSTODY** | Local SQLite/process-key reference simulator for custody and receipt lifecycle testing | Production custody, independent key custody, or SB712 quorum proof |

## 4. Claims requiring specific evidence

- **Offline / strict offline:** use only after host, VM, or container network policy is enforced and tested with route inspection and packet capture. Application URL checks are insufficient.
- **Sovereign / locally sovereign:** qualify the claim by identifying who controls execution, data, keys, updates, network paths, and recovery. Local execution alone does not establish full sovereignty.
- **Self-protecting / self-healing:** replace with the specific implemented control, such as detecting a digest mismatch, quarantining an input, or restoring from a verified checkpoint.
- **Hardened:** name the baseline, platform, controls, configuration, tests, and residual risks. An internal posture score is not a STIG/CIS score unless mapped to and assessed against that named standard.
- **Navy-ready / DoD-ready / mission-ready / field-ready:** do not use without sponsor-defined acceptance, independent evidence, applicable security assessment, and formal authorization.
- **Production-ready:** do not use for the current reference implementation.
- **Quantum-ready:** do not use as a security property or cryptographic claim without a defined threat model, algorithm suite, implementation, and validation.
- **Certified Clip Brick:** use only when a real certification authority, signed evidence, scope, version, and revocation process exist. A non-empty certification identifier is only a reference string.
- **Triple verification:** name the distinct verification, validation, and certification procedures and responsible authorities.

## 5. Navy track naming

Keep the two opportunity tracks separate in every proposal, README, architecture, and status report:

- **DON27TZ02-NV012 (STTR):** document-grounded training and knowledge assistant. Phase I planning calls for a working proof of concept using representative, publicly releasable proxy data, source ingestion, retrieval, grounded answers, validated citations, abstention behavior, and a quantitative evaluation plan. The STTR research institution must lead and conduct the R&D.
- **DON27BZ02-NV010 (SBIR):** Linux platform minimization and hardening. Its workflow is baseline, analyze, plan, approve, apply, verify, rollback, and report. It is a separate platform capability with its own target baseline, policy, tests, and evidence.

Do not present NV010 hardening results as NV012 application results, or vice versa. Do not imply a research partner, sponsor, award, endorsement, data access, or authorization is secured unless documented.

## 6. Writing standard

1. Lead with the measurable engineering function, then give the canonical project name in parentheses.
2. State implementation status: DESIGN, IMPLEMENTED, TESTED, MEASURED, INDEPENDENTLY REVIEWED, CERTIFIED, OPEN, BLOCKED, or NOT RUN.
3. Attach quantitative claims to commit, environment, method, raw result, and limitations.
4. Distinguish component, simulated, integration, hardware, and independent-evaluation evidence.
5. Prefer “designed to,” “reference implementation,” “prototype,” and “not yet integrated” over unsupported present-tense capability claims.
6. Preserve unresolved conflicts. Do not silently promote a candidate term into an adopted implementation contract.
