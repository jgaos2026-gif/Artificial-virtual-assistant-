"""Affective decision support for AVA.

Research reference implementation. Simulated affect is advisory context only:
it cannot change evidence trust, authorize actions, certify state, or execute
a proposed action. ABC×XYZ definitions follow the canonical AVA register.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
import json
import math
from typing import Iterable


class Emotion(StrEnum):
    CURIOSITY = "CURIOSITY"
    COMPASSION = "COMPASSION"
    CAUTION = "CAUTION"
    FEAR = "FEAR"
    COURAGE = "COURAGE"
    FRUSTRATION = "FRUSTRATION"
    ENVY = "ENVY"
    GRIEF = "GRIEF"
    ANGER = "ANGER"
    JOY = "JOY"
    PATIENCE = "PATIENCE"
    RESTRAINT = "RESTRAINT"


class FutureLabel(StrEnum):
    POSSIBLE = "POSSIBLE"
    PLAUSIBLE = "PLAUSIBLE"
    PROBABLE = "PROBABLE"
    PREFERABLE = "PREFERABLE"


class ReviewAxis(StrEnum):
    A_SELF_INTERNAL = "A_SELF_INTERNAL"
    B_OTHER_EXTERNAL = "B_OTHER_EXTERNAL"
    C_RELATIONSHIP_CONSEQUENCE = "C_RELATIONSHIP_CONSEQUENCE"
    X_NATIVE_VIEW = "X_NATIVE_VIEW"
    Y_OPPOSITION_VIEW = "Y_OPPOSITION_VIEW"
    Z_WHOLE_SYSTEM_VIEW = "Z_WHOLE_SYSTEM_VIEW"


@dataclass(frozen=True, slots=True)
class AffectiveStrand:
    emotion: Emotion
    intensity: float
    confidence: float
    source: str
    context_id: str
    evidence_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        for name, value in (("intensity", self.intensity), ("confidence", self.confidence)):
            if not math.isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and within [0, 1]")
        if not self.source.strip() or not self.context_id.strip():
            raise ValueError("source and context_id are required")
        if any(not item.strip() for item in self.evidence_ids):
            raise ValueError("evidence identifiers must be non-empty")


@dataclass(frozen=True, slots=True)
class ABCXYZReview:
    """Canonical AVA perspectives. Equal examination, not equal conclusions."""
    a_self_internal: str
    b_other_external: str
    c_relationship_consequence: str
    x_native_view: str
    y_opposition_view: str
    z_whole_system_view: str

    def __post_init__(self) -> None:
        if any(not value.strip() for value in asdict(self).values()):
            raise ValueError("all six ABC×XYZ review perspectives are required")


@dataclass(frozen=True, slots=True)
class DecisionOption:
    option_id: str
    description: str
    future_label: FutureLabel
    consequence: str
    reversible: bool
    requires_human_authorization: bool = True

    def __post_init__(self) -> None:
        if not all(value.strip() for value in (self.option_id, self.description, self.consequence)):
            raise ValueError("option id, description, and consequence are required")


@dataclass(frozen=True, slots=True)
class AffectiveDecisionAssessment:
    context_id: str
    recommendation: str
    rationale: tuple[str, ...]
    affective_signals: tuple[str, ...]
    unresolved_risks: tuple[str, ...]
    authorization_required: bool
    execution_authorized: bool
    evidence_trust_changed: bool
    soul_seed_roots: tuple[str, ...]
    review: ABCXYZReview
    receipt_sha256: str


SOUL_SEED_ROOTS = ("COMPASSION", "DECENCY", "LOVE")
MAX_STRANDS = 32
MAX_OPTIONS = 32
MAX_TEXT = 4_000


def _bounded_text(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > MAX_TEXT:
        raise ValueError(f"{field} must be non-empty text no longer than {MAX_TEXT} characters")
    return value.strip()


def assess_decision(
    *,
    context_id: str,
    problem: str,
    strands: Iterable[AffectiveStrand],
    review: ABCXYZReview,
    options: Iterable[DecisionOption],
    verified_facts: Iterable[str] = (),
    unresolved_risks: Iterable[str] = (),
) -> AffectiveDecisionAssessment:
    """Create a traceable recommendation; never authorize or execute it.

    The engine does not calculate truth from emotion. Verified facts and
    unresolved risks are carried as explicit inputs, while affect only
    contributes advisory signals and prompts scrutiny.
    """
    context_id = _bounded_text(context_id, "context_id")
    problem = _bounded_text(problem, "problem")
    strand_list = tuple(strands)
    option_list = tuple(options)
    facts = tuple(_bounded_text(item, "verified fact") for item in verified_facts)
    risks = tuple(_bounded_text(item, "unresolved risk") for item in unresolved_risks)

    if len(strand_list) > MAX_STRANDS:
        raise ValueError("too many affective strands")
    if not option_list or len(option_list) > MAX_OPTIONS:
        raise ValueError("provide between 1 and 32 decision options")
    if len({option.option_id for option in option_list}) != len(option_list):
        raise ValueError("option identifiers must be unique")
    if any(strand.context_id != context_id for strand in strand_list):
        raise ValueError("affective strand context mismatch")

    signals = tuple(
        f"{strand.emotion.value}: intensity={strand.intensity:.2f}, "
        f"confidence={strand.confidence:.2f}, source={strand.source}"
        for strand in strand_list
    )

    # Prefer a reversible, lower-commitment option when the supplied evidence
    # does not distinguish alternatives. No emotional score can override facts.
    ranked = sorted(
        option_list,
        key=lambda option: (
            not option.reversible,
            option.future_label is not FutureLabel.PREFERABLE,
            option.requires_human_authorization,
            option.option_id,
        ),
    )
    chosen = ranked[0]
    rationale = [
        f"Problem considered: {problem}",
        "Affective strands were treated as advisory signals, not evidence of truth.",
        "ABC×XYZ perspectives were all supplied and retained for review.",
        f"Selected candidate: {chosen.option_id} ({chosen.future_label.value}).",
        f"Consequence considered: {chosen.consequence}",
    ]
    if facts:
        rationale.append("Verified facts supplied: " + " | ".join(facts))
    if risks:
        rationale.append("Unresolved risks remain open and must not be treated as cleared.")

    payload = {
        "context_id": context_id,
        "problem": problem,
        "strands": [
            {
                "emotion": strand.emotion.value,
                "intensity": strand.intensity,
                "confidence": strand.confidence,
                "source": strand.source,
                "evidence_ids": list(strand.evidence_ids),
            }
            for strand in strand_list
        ],
        "review": asdict(review),
        "options": [
            {
                "option_id": option.option_id,
                "future_label": option.future_label.value,
                "consequence": option.consequence,
                "reversible": option.reversible,
            }
            for option in option_list
        ],
        "recommendation": chosen.option_id,
        "facts": list(facts),
        "risks": list(risks),
        "execution_authorized": False,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()

    return AffectiveDecisionAssessment(
        context_id=context_id,
        recommendation=chosen.option_id,
        rationale=tuple(rationale),
        affective_signals=signals,
        unresolved_risks=risks,
        authorization_required=chosen.requires_human_authorization,
        execution_authorized=False,
        evidence_trust_changed=False,
        soul_seed_roots=SOUL_SEED_ROOTS,
        review=review,
        receipt_sha256=digest,
    )


__all__ = [
    "Emotion", "FutureLabel", "ReviewAxis", "AffectiveStrand",
    "ABCXYZReview", "DecisionOption", "AffectiveDecisionAssessment",
    "SOUL_SEED_ROOTS", "assess_decision",
]
