"""Reference contract for sovereign Clip Brick admission and runtime assurance.

This module deliberately does not modify the protected AVA spine. It defines
interfaces and state transitions only. A production verifier must provide
independent identity, signature validation, key custody, durable evidence,
and failure-domain separation; this reference module does not supply those.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import math
from typing import Protocol


class BrickState(StrEnum):
    DISCOVERED = "DISCOVERED"
    QUARANTINED = "QUARANTINED"
    INSPECTING = "INSPECTING"
    VERIFIED = "VERIFIED"
    VALIDATED = "VALIDATED"
    CERTIFIED = "CERTIFIED"
    OWNER_PENDING = "OWNER_PENDING"
    ADMITTED = "ADMITTED"
    REVOKED = "REVOKED"


class RelationType(StrEnum):
    SUPPORTS = "SUPPORTS"
    CONTRADICTS = "CONTRADICTS"
    SUPERSEDES = "SUPERSEDES"
    DERIVED_FROM = "DERIVED_FROM"
    CORROBORATES = "CORROBORATES"
    INVALIDATES = "INVALIDATES"
    DUPLICATE_OF = "DUPLICATE_OF"


@dataclass(frozen=True)
class BrickManifest:
    brick_id: str
    version: str
    digest_sha256: str
    protected_core_write: bool
    requested_capabilities: tuple[str, ...]


@dataclass(frozen=True)
class VerificationReceipt:
    verifier_id: str
    subject_digest: str
    checks_passed: tuple[str, ...]
    evidence_ref: str


@dataclass(frozen=True)
class OwnerApproval:
    brick_id: str
    version: str
    manifest_digest: str
    approval_ref: str


class BrickVerifier(Protocol):
    def inspect(self, manifest: BrickManifest) -> VerificationReceipt: ...
    def validate(self, manifest: BrickManifest, receipt: VerificationReceipt) -> VerificationReceipt: ...
    def certify(self, manifest: BrickManifest, receipt: VerificationReceipt) -> VerificationReceipt: ...
    def verify_operation(self, manifest: BrickManifest, operation_digest: str) -> VerificationReceipt: ...


class OwnerAuthorizer(Protocol):
    def approve(self, manifest: BrickManifest) -> OwnerApproval: ...


class AdmissionError(PermissionError):
    pass


class SovereignBrickAdmission:
    """Fail-closed candidate lifecycle; sovereignty never grants core authority."""

    REQUIRED_CHECKS = frozenset({
        "identity", "manifest", "dependencies", "permissions", "resource_limits",
        "network_policy", "tests", "lineage", "rollback", "revocation",
    })

    def __init__(self, verifier: BrickVerifier, owner: OwnerAuthorizer | None = None) -> None:
        self._verifier = verifier
        self._owner = owner
        self._states: dict[tuple[str, str], BrickState] = {}
        self._manifests: dict[tuple[str, str], BrickManifest] = {}
        self._last_operation_receipts: dict[tuple[str, str], VerificationReceipt] = {}

    @staticmethod
    def _key(manifest: BrickManifest) -> tuple[str, str]:
        if not manifest.brick_id or not manifest.version:
            raise AdmissionError("brick identity and immutable version are required")
        if len(manifest.digest_sha256) != 64 or any(c not in "0123456789abcdef" for c in manifest.digest_sha256):
            raise AdmissionError("manifest digest must be lowercase SHA-256 hex")
        if manifest.protected_core_write:
            raise AdmissionError("Clip Bricks may never write or modify protected core")
        if len(set(manifest.requested_capabilities)) != len(manifest.requested_capabilities):
            raise AdmissionError("duplicate capability request")
        return manifest.brick_id, manifest.version

    @staticmethod
    def _check_receipt(receipt: VerificationReceipt, manifest: BrickManifest, required: set[str]) -> None:
        if not receipt.verifier_id or not receipt.evidence_ref:
            raise AdmissionError("verification receipt lacks verifier identity or evidence reference")
        if receipt.subject_digest != manifest.digest_sha256:
            raise AdmissionError("verification receipt is for a different manifest digest")
        if not required.issubset(set(receipt.checks_passed)):
            missing = sorted(required - set(receipt.checks_passed))
            raise AdmissionError(f"required verification checks missing: {missing}")

    def admit(self, manifest: BrickManifest) -> BrickState:
        key = self._key(manifest)
        if key in self._states:
            raise AdmissionError("this immutable Brick version has already entered admission")
        self._manifests[key] = manifest
        self._states[key] = BrickState.QUARANTINED
        try:
            self._states[key] = BrickState.INSPECTING
            inspected = self._verifier.inspect(manifest)
            self._check_receipt(inspected, manifest, set(self.REQUIRED_CHECKS))
            self._states[key] = BrickState.VERIFIED

            validated = self._verifier.validate(manifest, inspected)
            self._check_receipt(validated, manifest, {"independent_validation"})
            self._states[key] = BrickState.VALIDATED

            certified = self._verifier.certify(manifest, validated)
            self._check_receipt(certified, manifest, {"certification"})
            self._states[key] = BrickState.CERTIFIED

            if self._owner is None:
                self._states[key] = BrickState.OWNER_PENDING
                return self._states[key]
            approval = self._owner.approve(manifest)
            if (
                approval.brick_id != manifest.brick_id
                or approval.version != manifest.version
                or approval.manifest_digest != manifest.digest_sha256
                or not approval.approval_ref
            ):
                raise AdmissionError("owner approval does not bind exact Brick version and digest")
            self._states[key] = BrickState.ADMITTED
            return self._states[key]
        except Exception:
            self._states[key] = BrickState.QUARANTINED
            raise

    def admit_with_approval(self, manifest: BrickManifest, approval: OwnerApproval) -> BrickState:
        key = self._key(manifest)
        if self._states.get(key) is not BrickState.OWNER_PENDING:
            raise AdmissionError("Brick is not awaiting owner approval")
        if (
            approval.brick_id != manifest.brick_id
            or approval.version != manifest.version
            or approval.manifest_digest != manifest.digest_sha256
            or not approval.approval_ref
        ):
            raise AdmissionError("owner approval does not bind exact Brick version and digest")
        self._states[key] = BrickState.ADMITTED
        return self._states[key]

    def verify_operation(self, brick_id: str, version: str, operation_digest: str) -> VerificationReceipt:
        key = (brick_id, version)
        if self._states.get(key) is not BrickState.ADMITTED:
            raise AdmissionError("only an admitted Brick version may operate")
        if len(operation_digest) != 64 or any(c not in "0123456789abcdef" for c in operation_digest):
            self._states[key] = BrickState.QUARANTINED
            raise AdmissionError("operation digest is not valid SHA-256 hex")
        try:
            receipt = self._verifier.verify_operation(self._manifests[key], operation_digest)
            self._check_receipt(receipt, self._manifests[key], {"operation_integrity", "permission_scope"})
            self._last_operation_receipts[key] = receipt
            return receipt
        except Exception:
            self._states[key] = BrickState.QUARANTINED
            raise

    def revoke(self, brick_id: str, version: str) -> None:
        key = (brick_id, version)
        if key not in self._states:
            raise AdmissionError("unknown Brick version")
        self._states[key] = BrickState.REVOKED

    def state(self, brick_id: str, version: str) -> BrickState | None:
        return self._states.get((brick_id, version))


@dataclass(frozen=True)
class AffectiveBudget:
    attention_multiplier: float
    retrieval_breadth: int
    simulation_branches: int


def affective_budget(valence: float, arousal: float) -> AffectiveBudget:
    """Pure bounded resource hint. No authority or trust API accepts this type."""
    if not math.isfinite(valence) or not -1.0 <= valence <= 1.0:
        raise ValueError("valence must be finite and in [-1, 1]")
    if not math.isfinite(arousal) or not 0.0 <= arousal <= 1.0:
        raise ValueError("arousal must be finite and in [0, 1]")
    return AffectiveBudget(
        attention_multiplier=0.8 + ((valence + 1.0) * 0.2),
        retrieval_breadth=min(7, max(3, 3 + round(arousal * 4))),
        simulation_branches=min(3, max(1, 1 + round(arousal * 2))),
    )
