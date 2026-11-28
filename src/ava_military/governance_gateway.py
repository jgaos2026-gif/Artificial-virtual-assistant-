"""Runtime binding adapter for the existing pure governance policy primitive.

This module binds a versioned policy descriptor to an operating mode and
delegates authorization decisions to ava_military.governance. It can append
bounded local decision receipts, but it does not authenticate actors, protect
policy storage, provide an external monotonic anchor, or authorize side effects.
Those integrations remain separate acceptance gates.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any

from .decision_receipts import DecisionReceipt, DecisionReceiptError, DecisionReceiptLog

from .governance import (
    ActionClass,
    AuthorizationResult,
    AuthorityContext,
    Decision,
    Mode,
    authorize as evaluate_policy,
)


class PolicyBindingError(ValueError):
    """Raised when a policy bundle cannot be safely bound to this runtime."""


MAX_POLICY_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class BoundAuthorizationResult:
    """A policy decision annotated with the binding that produced it."""

    decision: Decision
    reason: str
    policy_version: str
    policy_digest: str

    @classmethod
    def from_policy_result(
        cls,
        result: AuthorizationResult,
        *,
        policy_version: str,
        policy_digest: str,
    ) -> "BoundAuthorizationResult":
        return cls(
            decision=result.decision,
            reason=result.reason,
            policy_version=policy_version,
            policy_digest=policy_digest,
        )


@dataclass(frozen=True, slots=True)
class RecordedAuthorizationResult:
    """A policy result returned only after its receipt is durable."""

    authorization: BoundAuthorizationResult
    receipt: DecisionReceipt


@dataclass(frozen=True, slots=True)
class GovernanceGateway:
    """Immutable policy binding for one runtime instance."""

    policy_version: str
    policy_digest: str
    mode: Mode

    def authorize(
        self,
        context: AuthorityContext | None,
        capability: str,
        required_scope: str,
    ) -> BoundAuthorizationResult:
        """Evaluate using the bound mode; never trust a caller-selected mode."""
        if context is None:
            result = AuthorizationResult(Decision.DENY, "MISSING_AUTHORITY_CONTEXT")
        elif context.mode is not self.mode:
            result = AuthorizationResult(Decision.DENY, "BOUND_MODE_MISMATCH")
        else:
            result = evaluate_policy(context, capability, required_scope)

        return BoundAuthorizationResult.from_policy_result(
            result,
            policy_version=self.policy_version,
            policy_digest=self.policy_digest,
        )


    def authorize_with_receipt(
        self,
        context: AuthorityContext | None,
        capability: str,
        required_scope: str,
        *,
        request_id: str,
        receipt_log: DecisionReceiptLog,
    ) -> RecordedAuthorizationResult:
        """Evaluate and durably record a decision before returning it.

        The supplied AuthorityContext is recorded as caller-provided context.
        This method does NOT authenticate that context or prove approval
        authenticity. A caller must obtain context through a separately
        authenticated authority boundary. If receipt persistence fails, this
        method raises and returns no authorization result.
        """
        if (
            not isinstance(request_id, str)
            or not request_id.strip()
            or len(request_id) > 128
        ):
            raise ValueError("request_id must be a non-empty string of at most 128 characters")

        result = self.authorize(context, capability, required_scope)
        supplied_context = None
        if context is not None:
            supplied_context = {
                "actor_id": context.actor_id,
                "authenticated_claim": context.authenticated,
                "scope": context.scope,
                "mode": getattr(context.mode, "value", context.mode),
                "action_class": getattr(context.action_class, "value", context.action_class),
                "human_approval_claim": context.human_approval,
            }
        payload = {
            "event_type": "GOVERNANCE_DECISION",
            "request_id": request_id.strip(),
            "policy_version": self.policy_version,
            "policy_digest": self.policy_digest,
            "capability": capability,
            "required_scope": required_scope,
            "supplied_authority_context": supplied_context,
            "decision": result.decision.value,
            "reason": result.reason,
        }
        try:
            receipt = receipt_log.append(payload)
        except Exception as exc:
            raise DecisionReceiptError(
                "decision receipt could not be durably appended; do not execute request"
            ) from exc
        return RecordedAuthorizationResult(authorization=result, receipt=receipt)

    @staticmethod
    def require_allow(result: BoundAuthorizationResult) -> None:
        """Raise for DEFER/DENY; callers must never treat either as permission."""
        if result.decision is not Decision.ALLOW:
            raise PermissionError(result.reason)


_ALLOWED_POLICY_FIELDS = {"schema_version", "policy_version", "mode"}
_SUPPORTED_POLICY_SCHEMA_VERSION = 1


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise PolicyBindingError(f"duplicate policy field: {key}")
        result[key] = value
    return result


def bind_policy(
    path: str | Path,
    *,
    operating_mode: str | Mode,
) -> GovernanceGateway:
    """Load a strict policy descriptor and bind its digest and operating mode.

    The policy descriptor is a versioned JSON object containing exactly
    schema_version, policy_version, and mode. The configured mode must match
    the descriptor. The digest identifies the exact source bytes; it does not
    prove protected storage or authenticity.
    """
    try:
        configured_mode = operating_mode if isinstance(operating_mode, Mode) else Mode(operating_mode)
    except (TypeError, ValueError) as exc:
        raise PolicyBindingError("unsupported configured operating mode") from exc

    policy_path = Path(path)
    try:
        # Bound the read itself, rather than trusting a prior stat() result.
        with policy_path.open("rb") as stream:
            raw = stream.read(MAX_POLICY_BYTES + 1)
    except OSError as exc:
        raise PolicyBindingError("policy bundle is unavailable") from exc

    if len(raw) > MAX_POLICY_BYTES:
        raise PolicyBindingError(
            f"policy bundle exceeds the {MAX_POLICY_BYTES}-byte limit"
        )

    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except RecursionError as exc:
        raise PolicyBindingError("policy bundle exceeds the JSON nesting limit") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PolicyBindingError("policy bundle is not valid UTF-8 JSON") from exc

    if not isinstance(document, dict):
        raise PolicyBindingError("policy bundle root must be a JSON object")

    unknown = set(document) - _ALLOWED_POLICY_FIELDS
    missing = _ALLOWED_POLICY_FIELDS - set(document)
    if unknown:
        raise PolicyBindingError(f"unsupported policy fields: {', '.join(sorted(unknown))}")
    if missing:
        raise PolicyBindingError(f"missing policy fields: {', '.join(sorted(missing))}")

    version = document["schema_version"]
    if type(version) is not int or version != _SUPPORTED_POLICY_SCHEMA_VERSION:
        raise PolicyBindingError("unsupported or invalid policy schema_version")

    policy_version = document["policy_version"]
    if not isinstance(policy_version, str) or not policy_version.strip():
        raise PolicyBindingError("policy_version must be a non-empty string")

    try:
        bundle_mode = Mode(document["mode"])
    except (TypeError, ValueError) as exc:
        raise PolicyBindingError("policy bundle contains an unsupported mode") from exc

    if bundle_mode is not configured_mode:
        raise PolicyBindingError("configured operating mode does not match policy bundle")

    return GovernanceGateway(
        policy_version=policy_version.strip(),
        policy_digest=hashlib.sha256(raw).hexdigest(),
        mode=configured_mode,
    )


__all__ = [
    "ActionClass",
    "AuthorityContext",
    "BoundAuthorizationResult",
    "Decision",
    "GovernanceGateway",
    "Mode",
    "PolicyBindingError",
    "RecordedAuthorizationResult",
    "bind_policy",
]
