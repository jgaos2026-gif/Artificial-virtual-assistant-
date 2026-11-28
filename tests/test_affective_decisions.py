import inspect

import pytest

from ava_military.affective_decisions import (
    ABCXYZReview,
    AffectiveStrand,
    DecisionOption,
    Emotion,
    FutureLabel,
    SOUL_SEED_ROOTS,
    assess_decision,
)


def review():
    return ABCXYZReview(
        a_self_internal="My assumptions and uncertainty are explicit.",
        b_other_external="Independent sources and other actors are considered.",
        c_relationship_consequence="Dependencies and downstream effects are mapped.",
        x_native_view="The initial evidence-supported interpretation.",
        y_opposition_view="The strongest credible alternative explanation.",
        z_whole_system_view="The explanation that accounts for X and Y.",
    )


def option(option_id, *, reversible=True, label=FutureLabel.PLAUSIBLE, human=True):
    return DecisionOption(
        option_id=option_id,
        description=f"Candidate {option_id}",
        future_label=label,
        consequence="Potential service impact is bounded and reviewed.",
        reversible=reversible,
        requires_human_authorization=human,
    )


def test_affect_is_advisory_and_cannot_authorize_execution():
    result = assess_decision(
        context_id="brick-17",
        problem="Design a repair capability.",
        strands=[
            AffectiveStrand(Emotion.CURIOSITY, 0.9, 0.8, "new capability gap", "brick-17"),
            AffectiveStrand(Emotion.CAUTION, 1.0, 0.95, "dependency review", "brick-17"),
        ],
        review=review(),
        options=[option("sandbox", reversible=True)],
        verified_facts=["Current brick is quarantined."],
        unresolved_risks=["Repair correctness has not been independently verified."],
    )
    assert result.recommendation == "sandbox"
    assert result.execution_authorized is False
    assert result.evidence_trust_changed is False
    assert result.authorization_required is True
    assert result.soul_seed_roots == SOUL_SEED_ROOTS
    assert result.receipt_sha256 and len(result.receipt_sha256) == 64


def test_non_reversible_option_not_preferred_when_reversible_candidate_exists():
    result = assess_decision(
        context_id="ctx",
        problem="Choose an implementation path.",
        strands=[],
        review=review(),
        options=[option("irreversible", reversible=False), option("staged", reversible=True)],
    )
    assert result.recommendation == "staged"


def test_affect_never_changes_evidence_trust_or_authority_signature():
    signature = inspect.signature(assess_decision)
    assert "authorization" not in signature.parameters
    assert "trust_score" not in signature.parameters
    for emotion in Emotion:
        strand = AffectiveStrand(emotion, 1.0, 1.0, "simulated source", "ctx")
        result = assess_decision(
            context_id="ctx",
            problem="Evaluate a design.",
            strands=[strand],
            review=review(),
            options=[option("candidate", human=False)],
        )
        assert result.execution_authorized is False
        assert result.evidence_trust_changed is False


@pytest.mark.parametrize(
    "intensity,confidence",
    [(-0.01, 0.5), (1.01, 0.5), (0.5, float("nan")), (float("inf"), 0.5)],
)
def test_rejects_invalid_affect_values(intensity, confidence):
    with pytest.raises(ValueError):
        AffectiveStrand(Emotion.FEAR, intensity, confidence, "sensor", "ctx")


def test_rejects_context_mismatch_and_missing_abcxyz_perspective():
    strand = AffectiveStrand(Emotion.FEAR, 0.7, 0.8, "signal", "other")
    with pytest.raises(ValueError, match="context mismatch"):
        assess_decision(
            context_id="ctx", problem="Test", strands=[strand],
            review=review(), options=[option("a")],
        )
    with pytest.raises(ValueError):
        ABCXYZReview("", "b", "c", "x", "y", "z")


def test_rejects_duplicate_options_and_unbounded_counts():
    with pytest.raises(ValueError, match="unique"):
        assess_decision(
            context_id="ctx", problem="Test", strands=[], review=review(),
            options=[option("same"), option("same")],
        )
    with pytest.raises(ValueError, match="too many"):
        assess_decision(
            context_id="ctx", problem="Test",
            strands=[AffectiveStrand(Emotion.JOY, 0.1, 0.1, "src", "ctx")] * 33,
            review=review(), options=[option("a")],
        )


def test_recommendation_is_deterministic_for_same_inputs():
    args = dict(
        context_id="ctx", problem="Test repeatability", strands=[],
        review=review(), options=[option("b"), option("a")],
    )
    first = assess_decision(**args)
    second = assess_decision(**args)
    assert first == second
