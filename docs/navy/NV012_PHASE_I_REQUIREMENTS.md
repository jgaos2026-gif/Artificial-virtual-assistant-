# DON27TZ02-NV012 — Phase I Mission Requirements

**Primary mission track for this repository**  
**Source basis:** DON27TZ02 General FAQ; DON27TZ02-NV012 Office Hour Q&A Summary (19 November 2026); AVA for the Military and Navy design, November 2026.  
**Status:** Requirements interpretation for engineering planning, not a solicitation response or government direction.

## 1. Mission focus

NV012 is an STTR mission application: a document-grounded training and knowledge assistant. The preferred early test setting identified in the design is a schoolhouse because curricula and learning outcomes are more structured. Fleet/on-the-job support is a longer-term Phase II/III direction. Medical and Defense Health Agency training pipelines are in scope according to the FAQ.

The first pilot community is not selected by the government in these source documents. The offeror must propose and justify a focused pilot community and explain how results generalize.

## 2. Phase I must deliver a working proof of concept

A feasibility report alone is insufficient. Phase I should deliver:
- A working proof of concept on representative, publicly releasable proxy data.
- End-to-end source ingestion, retrieval, grounded answer generation, and citations.
- A technical feasibility report describing architecture and the hallucination-reduction approach.
- A quantitative evaluation plan and baseline for Phase II.

Do not assume government-furnished data will be available during Phase I. Use public proxies that resemble target materials in structure and complexity, such as unclassified training manuals, doctrine, public qualification standards, and open technical manuals. Synthetic learner data may be used where justified.

The STTR research institution's role is to lead and conduct the research and development. A teaming arrangement must be established through the official process; this repository does not assert that a partner is already secured.

## 3. Required answer pipeline

1. Admit a source through integrity and policy checks.
2. Extract and index passages while retaining document identity and version.
3. Retrieve relevant passages under the user's authorization.
4. Generate only from admitted retrieved evidence.
5. Validate every citation against an actual passage in the correct document and version.
6. Display citations and the exact supporting passages for inspection.
7. Abstain clearly when evidence is weak, missing, stale, conflicting, or outside scope.
8. Record retrieval, answer, citation, and evaluation events in the evidence ledger.
9. Keep integrity-failed or superseded sources out of trusted retrieval until resolved.

Minimum citation provenance: document, section, version, and retrieved passage. A citation-shaped string is not sufficient; the target passage must exist and support the associated claim.

## 4. Evaluation measures

The FAQ does not prescribe fixed numerical thresholds. The offeror must propose and justify measurable targets. Required candidate measures include:
- Unsupported-claim / hallucination rate.
- Citation accuracy.
- Retrieval precision and recall.
- Answer correctness against expert-validated answers.
- Comparison against a general-purpose LLM baseline using the same proxy corpus and evaluation set.

The design and office-hour summary elevate retention and transfer as primary learning outcomes. Faster time to proficiency is a desired benefit, but cannot be achieved by lowering standards or creating short-lived memorization. A strong Phase II evaluation should examine durable foundational knowledge and subsequent performance across contexts.

Subject-matter experts must review the proxy evaluation set and answer key. Citations alone do not establish faithfulness.

## 5. Learner and instructor boundaries

- Demonstrate tailored behavior for different learner needs or experience levels; Phase I need not cover every rating or community.
- Support individual tailoring and cohort-based learning in the target architecture.
- A learning-objective or qualification framework may be selected and justified; no single framework is mandated in the supplied FAQ.
- Learner-facing instructional delivery is the primary focus.
- Instructor/curriculum tools may be included only when they support rather than displace learner-facing delivery.
- AVA may identify persistent learning gaps and present evidence, but instructors retain decisions about intervention, progression, and attrition.
- Do not let an automated score alone decide that a learner fails, advances, or is removed.

## 6. Content currency and conflict handling

The architecture must be able to represent document version, effective date, source authority, supersession, distribution marking, and conflict status. Detect potentially superseded instructions and conflicting sources; do not silently choose one. Present the conflict and the source metadata for human resolution when authority cannot be established.

## 7. Model and deployment strategy

The FAQ advises favoring open-weight models, or explaining how a commercial model can operate inside government-controlled infrastructure. Model provenance, supply chain, deployment rights, and transition must be addressed. Explain when model-weight adaptation (for example, LoRA or continued pretraining) adds value beyond retrieval alone.

Design for portability across:
- Accredited cloud environments at the required impact level.
- On-premises enclaves.
- Disconnected or bandwidth-limited edge environments.

Report compute footprint for training and inference. Demonstrate graceful degradation to smaller or quantized models. Keep retrieval, authorization, integrity, citations, and audit independent of model availability.

Phase I may use the offeror's environment and does not require CUI or classified data. The proposal should explain a future controlled-data path, including identity-based access, least privilege, per-request retrieval authorization, distribution marking carried through retrieval and outputs, and separate data enclaves. CMMC Level 2 (Self) is described as a projected Phase II requirement in the office-hour summary, subject to the actual solicitation and contract.

## 8. Integration and transition

No single transition host or sponsor is specified in the supplied Q&A. Avoid binding the design to one LMS, data platform, or vendor. Use containerized deployment and standards-based APIs. Phase II planning should include transition relationships and operational stakeholder engagement, but participation is not guaranteed.

LMS integration, portable deployment, and austere-environment executables are not stated Phase I requirements. The architecture should not preclude them.

## 9. Data rights and research partnership

Clearly distinguish JGA background IP (for example, generic integrity pipeline, tools, and reusable methods) from artifacts, model weights, or other outputs derived from government-furnished data. State data-rights assertions clearly and follow the applicable SBIR/STTR clauses and contract. The research institution is expected to lead and conduct R&D for this STTR topic.

## 10. Phase I exclusions and non-claims

This repository is not an approved CUI or classified environment. No Navy data access, research institution partnership, stakeholder availability, government endorsement, award, transition sponsor, accreditation, ATO, or CMMC status is implied. Do not use learner data or human-subject research without the required approvals and controls. The Q&A indicates limited Phase I validation may be appropriate and that IRB approval is not required for Phase I, though an offeror may pursue it; actual research design and applicable rules must be reviewed by the institution and sponsor.
