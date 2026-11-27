import inspect
import pytest

from ava_military.sovereign import (
    AdmissionError, AffectiveBudget, BrickManifest, BrickState, OwnerApproval,
    SovereignBrickAdmission, VerificationReceipt, affective_budget,
)


DIGEST = "a" * 64
OP_DIGEST = "b" * 64
CHECKS = (
    "identity", "manifest", "dependencies", "permissions", "resource_limits",
    "network_policy", "tests", "lineage", "rollback", "revocation",
)


class GoodVerifier:
    def inspect(self, manifest):
        return VerificationReceipt("independent-verifier", manifest.digest_sha256, CHECKS, "ev:inspect")
    def validate(self, manifest, receipt):
        return VerificationReceipt("independent-validator", manifest.digest_sha256, ("independent_validation",), "ev:validate")
    def certify(self, manifest, receipt):
        return VerificationReceipt("independent-certifier", manifest.digest_sha256, ("certification",), "ev:certify")
    def verify_operation(self, manifest, operation_digest):
        return VerificationReceipt("runtime-monitor", manifest.digest_sha256, ("operation_integrity", "permission_scope"), "ev:operation")


class BadRuntimeVerifier(GoodVerifier):
    def verify_operation(self, manifest, operation_digest):
        raise RuntimeError("integrity drift")


class GoodOwner:
    def approve(self, manifest):
        return OwnerApproval(manifest.brick_id, manifest.version, manifest.digest_sha256, "owner-approval:1")


def manifest(**changes):
    data = dict(brick_id="memory-affect", version="1.0.0", digest_sha256=DIGEST,
                protected_core_write=False, requested_capabilities=("memory.read",))
    data.update(changes)
    return BrickManifest(**data)


def test_full_admission_requires_all_gates_and_owner():
    runner = SovereignBrickAdmission(GoodVerifier(), GoodOwner())
    assert runner.admit(manifest()) is BrickState.ADMITTED


def test_no_owner_means_pending_not_admitted():
    runner = SovereignBrickAdmission(GoodVerifier())
    assert runner.admit(manifest()) is BrickState.OWNER_PENDING
    with pytest.raises(AdmissionError):
        runner.verify_operation("memory-affect", "1.0.0", OP_DIGEST)


def test_core_write_manifest_is_rejected_before_admission():
    with pytest.raises(AdmissionError, match="protected core"):
        SovereignBrickAdmission(GoodVerifier(), GoodOwner()).admit(manifest(protected_core_write=True))


def test_wrong_digest_receipt_quarantines_candidate():
    class WrongDigest(GoodVerifier):
        def inspect(self, m):
            return VerificationReceipt("verifier", "0" * 64, CHECKS, "ev:wrong")
    runner = SovereignBrickAdmission(WrongDigest(), GoodOwner())
    with pytest.raises(AdmissionError, match="different manifest"):
        runner.admit(manifest())
    assert runner.state("memory-affect", "1.0.0") is BrickState.QUARANTINED


def test_runtime_integrity_failure_quarantines_admitted_brick():
    runner = SovereignBrickAdmission(BadRuntimeVerifier(), GoodOwner())
    runner.admit(manifest())
    with pytest.raises(RuntimeError):
        runner.verify_operation("memory-affect", "1.0.0", OP_DIGEST)
    assert runner.state("memory-affect", "1.0.0") is BrickState.QUARANTINED


def test_revoked_version_cannot_operate():
    runner = SovereignBrickAdmission(GoodVerifier(), GoodOwner())
    runner.admit(manifest())
    runner.revoke("memory-affect", "1.0.0")
    with pytest.raises(AdmissionError):
        runner.verify_operation("memory-affect", "1.0.0", OP_DIGEST)


def test_new_version_is_distinct_from_admitted_version():
    runner = SovereignBrickAdmission(GoodVerifier(), GoodOwner())
    runner.admit(manifest())
    assert runner.admit(manifest(version="1.0.1")) is BrickState.ADMITTED


def test_affective_budget_is_hard_bounded_and_rejects_nonfinite():
    budget = affective_budget(1.0, 1.0)
    assert budget.attention_multiplier == pytest.approx(1.2)
    assert budget.retrieval_breadth == 7
    assert budget.simulation_branches == 3
    with pytest.raises(ValueError):
        affective_budget(float("nan"), 0.5)
    with pytest.raises(ValueError):
        affective_budget(0.0, float("inf"))


def test_authority_contract_has_no_affective_argument():
    # Admission and runtime verification signatures must not accept affect.
    assert "affect" not in inspect.signature(SovereignBrickAdmission.admit).parameters
    assert "affect" not in inspect.signature(SovereignBrickAdmission.verify_operation).parameters
