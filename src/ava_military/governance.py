"""Fail-closed reference authorization policy.

This module is a pure policy primitive. Production authorization requires
authenticated identities, protected policy storage, key custody, replay
protection, durable receipts, and independent review outside this module.
"""
from dataclasses import dataclass
from enum import StrEnum


class Mode(StrEnum):
    STRICT_OFFLINE = "STRICT_OFFLINE"
    LOCAL_NODE_MESH = "LOCAL_NODE_MESH"
    CONTROLLED_INGEST = "CONTROLLED_INGEST"
    DEGRADED_CONTAINMENT = "DEGRADED_CONTAINMENT"
    RECOVERY = "RECOVERY"
    MAINTENANCE = "MAINTENANCE"


class ActionClass(StrEnum):
    READ_ONLY = "READ_ONLY"
    REVERSIBLE_LOCAL = "REVERSIBLE_LOCAL"
    PROTECTED = "PROTECTED"
    DESTRUCTIVE_OR_EXTERNAL = "DESTRUCTIVE_OR_EXTERNAL"


class Decision(StrEnum):
    ALLOW = "ALLOW"
    DEFER = "DEFER"
    DENY = "DENY"


@dataclass(frozen=True)
class AuthorityContext:
    actor_id: str
    authenticated: bool
    capabilities: frozenset[str]
    scope: str
    mode: Mode
    action_class: ActionClass
    human_approval: bool = False


@dataclass(frozen=True)
class AuthorizationResult:
    decision: Decision
    reason: str


def authorize(context: AuthorityContext | None, capability: str, required_scope: str) -> AuthorizationResult:
    """Evaluate a narrowly scoped request; missing/unknown context fails closed."""
    if context is None:
        return AuthorizationResult(Decision.DENY, "MISSING_AUTHORITY_CONTEXT")
    if not context.actor_id or not context.authenticated:
        return AuthorizationResult(Decision.DENY, "ACTOR_NOT_AUTHENTICATED")
    if not capability or not required_scope:
        return AuthorizationResult(Decision.DENY, "MISSING_CAPABILITY_OR_SCOPE")
    if context.scope != required_scope:
        return AuthorizationResult(Decision.DENY, "SCOPE_MISMATCH")
    if capability not in context.capabilities:
        return AuthorizationResult(Decision.DENY, "CAPABILITY_NOT_GRANTED")
    if context.mode == Mode.DEGRADED_CONTAINMENT:
        return AuthorizationResult(Decision.DENY, "DEGRADED_MODE_BLOCKS_ACTION")
    if context.mode == Mode.RECOVERY and context.action_class not in {
        ActionClass.READ_ONLY, ActionClass.REVERSIBLE_LOCAL
    }:
        return AuthorizationResult(Decision.DEFER, "RECOVERY_MODE_RESTRICTS_ACTION")
    if context.mode == Mode.STRICT_OFFLINE and context.action_class in {
        ActionClass.PROTECTED, ActionClass.DESTRUCTIVE_OR_EXTERNAL
    }:
        return AuthorizationResult(Decision.DENY, "OFFLINE_PROTECTED_ACTION_REFUSED")
    if context.action_class in {
        ActionClass.PROTECTED, ActionClass.DESTRUCTIVE_OR_EXTERNAL
    } and not context.human_approval:
        return AuthorizationResult(Decision.DEFER, "HUMAN_APPROVAL_REQUIRED")
    return AuthorizationResult(Decision.ALLOW, "POLICY_CHECKS_PASSED")


def require_allow(result: AuthorizationResult) -> None:
    """Raise rather than accidentally treating DEFER as permission."""
    if result.decision is not Decision.ALLOW:
        raise PermissionError(result.reason)
