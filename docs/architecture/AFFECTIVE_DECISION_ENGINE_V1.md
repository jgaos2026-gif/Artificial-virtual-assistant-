# Affective Decision Engine V1

**Status:** Research reference implementation on a feature branch. Not integrated into a deployable AVA/OASIS runtime and not production-certified.

## Purpose

Extend the existing `AffectiveState` / `run_dream_sandbox` physiology primitive with explicit affective strands and a traceable decision-assessment record. This is an add-only capability. It does not replace the existing physiology API.

## Canonical reasoning

The engine requires all six canonical AVA review perspectives:

- **A, Self/Internal:** AVA's state, assumptions, memory, intent, and uncertainty.
- **B, Other/External:** independent evidence, environment, and other nodes or agents.
- **C, Relationship/Consequence:** causality, dependencies, and downstream effects.
- **X, Native View:** initial evidence-supported interpretation.
- **Y, Opposition/Inverted View:** strongest credible alternative, including what could make X wrong.
- **Z, Whole-System View:** explanation accounting for the strongest parts of X and Y.

Equal examination does not require equal conclusions. Stronger verified evidence governs.

## Affective inputs

Each strand records an emotion label, intensity, confidence, source, context identifier, and optional evidence identifiers. Inputs are finite and bounded. The initial vocabulary includes curiosity, compassion, caution, fear, courage, frustration, envy, grief, anger, joy, patience, and restraint.

## Decision behavior

The engine emits a recommendation and a SHA-256 digest over the canonical assessment inputs. Affect is advisory only. It cannot modify evidence trust, certify information, authorize an action, or execute a candidate. When the supplied options do not distinguish themselves through evidence, the deterministic selection rule prefers reversible options and then a PREFERABLE-labeled option. This is a conservative tie-breaker, not a prediction of correctness.

The three Soul Seed roots remain exactly COMPASSION, DECENCY, LOVE.

## Tests

The tests cover bounded affect values, all emotion labels, required ABC×XYZ perspectives, context binding, deterministic output, duplicate option rejection, preference for reversible candidates, and the non-authority invariant.

## Limitations

- No subjective emotion, consciousness, or biological experience is claimed.
- The engine does not infer affect from voice, face, biometrics, or other sensors.
- It does not perform natural-language ABC×XYZ analysis itself. A caller must supply the six review perspectives.
- It does not verify the truth of supplied facts, forecasts, or emotional sources.
- The digest is an integrity identifier, not a digital signature or independently anchored receipt.
- No persistent decision-receipt integration, API wiring, user interface, runtime integration, Clip Brick admission, or live model connection is included in this first module.
- Unit tests do not prove integrated AVA/OASIS security or operational readiness.
