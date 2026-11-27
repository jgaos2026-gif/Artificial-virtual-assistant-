import pytest

from ava_military.governance import (
    ActionClass, AuthorityContext, Decision, Mode, authorize, require_allow,
)


def context(**overrides):
    values = dict(
        actor_id="operator-1",
        authenticated=True,
        capabilities=frozenset({"report.read", "maintenance.local"}),
        scope="unit-test",
        mode=Mode.LOCAL_NODE_MESH,
        action_class=ActionClass.READ_ONLY,
        human_approval=False,
    )
    values.update(overrides)
    return AuthorityContext(**values)


def test_scoped_read_is_allowed():
    result = authorize(context(), "report.read", "unit-test")
    assert result.decision is Decision.ALLOW


def test_unauthenticated_actor_is_denied():
    result = authorize(context(authenticated=False), "report.read", "unit-test")
    assert result.decision is Decision.DENY
    assert result.reason == "ACTOR_NOT_AUTHENTICATED"


def test_scope_mismatch_is_denied():
    result = authorize(context(), "report.read", "other-scope")
    assert result.decision is Decision.DENY


def test_offline_protected_action_is_refused_even_with_grant_and_approval():
    result = authorize(
        context(mode=Mode.STRICT_OFFLINE, action_class=ActionClass.PROTECTED, human_approval=True),
        "maintenance.local",
        "unit-test",
    )
    assert result.decision is Decision.DENY
    assert result.reason == "OFFLINE_PROTECTED_ACTION_REFUSED"


def test_protected_action_without_human_approval_defers():
    result = authorize(
        context(action_class=ActionClass.PROTECTED),
        "maintenance.local",
        "unit-test",
    )
    assert result.decision is Decision.DEFER


def test_defer_cannot_be_treated_as_allow():
    with pytest.raises(PermissionError):
        require_allow(authorize(context(action_class=ActionClass.PROTECTED), "maintenance.local", "unit-test"))
