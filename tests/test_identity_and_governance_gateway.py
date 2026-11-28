from __future__ import annotations

import hashlib
import json

import pytest

from ava_military.governance import ActionClass, AuthorityContext, Decision, Mode
from ava_military.governance_gateway import PolicyBindingError, bind_policy
from ava_military.identity.loader import IdentityLoadError, load_identity


def test_identity_loader_accepts_explicit_development_fixture(tmp_path):
    path = tmp_path / "identity.json"
    path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "identity_id": "ava-test",
                "epoch": 1,
                "lineage_reference": "fixture:root",
                "verification_key_reference": "test-key:public",
                "capabilities": ["descriptive.only"],
            }
        ),
        encoding="utf-8",
    )

    identity = load_identity(path, profile="development")

    assert identity.identity_id == "ava-test"
    assert identity.epoch == 1
    assert identity.capabilities == ("descriptive.only",)
    assert identity.verification_key_reference == "test-key:public"


@pytest.mark.parametrize(
    "document",
    [
        [],
        {"schema_version": 2, "identity_id": "x", "epoch": 1, "lineage_reference": "r"},
        {"schema_version": 1, "identity_id": "x", "epoch": True, "lineage_reference": "r"},
        {"schema_version": 1, "identity_id": " ", "epoch": 1, "lineage_reference": "r"},
        {
            "schema_version": 1,
            "identity_id": "x",
            "epoch": 1,
            "lineage_reference": "r",
            "unexpected": True,
        },
    ],
)
def test_identity_loader_rejects_invalid_schema(tmp_path, document):
    path = tmp_path / "identity.json"
    path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(IdentityLoadError):
        load_identity(path, profile="test")


def test_identity_loader_rejects_duplicate_json_keys(tmp_path):
    path = tmp_path / "identity.json"
    path.write_text(
        '{"schema_version":1,"identity_id":"first","identity_id":"second",'
        '"epoch":1,"lineage_reference":"root"}',
        encoding="utf-8",
    )

    with pytest.raises(IdentityLoadError, match="duplicate"):
        load_identity(path, profile="test")


def test_identity_loader_rejects_production_profile_without_crypto_validator(tmp_path):
    path = tmp_path / "identity.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(IdentityLoadError, match="development or test"):
        load_identity(path, profile="production")


def test_governance_gateway_binds_policy_version_mode_and_exact_digest(tmp_path):
    path = tmp_path / "policy.json"
    raw = b'{"schema_version":1,"policy_version":"policy-7","mode":"LOCAL_NODE_MESH"}'
    path.write_bytes(raw)

    gateway = bind_policy(path, operating_mode=Mode.LOCAL_NODE_MESH)

    assert gateway.policy_version == "policy-7"
    assert gateway.mode is Mode.LOCAL_NODE_MESH
    assert gateway.policy_digest == hashlib.sha256(raw).hexdigest()


def test_governance_gateway_rejects_mode_mismatch(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(
        '{"schema_version":1,"policy_version":"p1","mode":"STRICT_OFFLINE"}',
        encoding="utf-8",
    )

    with pytest.raises(PolicyBindingError, match="does not match"):
        bind_policy(path, operating_mode=Mode.LOCAL_NODE_MESH)


@pytest.mark.parametrize(
    "raw",
    [
        b"not-json",
        b'{"schema_version":1,"schema_version":1,"policy_version":"p1","mode":"LOCAL_NODE_MESH"}',
        b'{"schema_version":2,"policy_version":"p1","mode":"LOCAL_NODE_MESH"}',
        b'{"schema_version":1,"policy_version":"","mode":"LOCAL_NODE_MESH"}',
        b'{"schema_version":1,"policy_version":"p1","mode":"UNKNOWN"}',
    ],
)
def test_governance_gateway_rejects_invalid_policy_bundle(tmp_path, raw):
    path = tmp_path / "policy.json"
    path.write_bytes(raw)

    with pytest.raises(PolicyBindingError):
        bind_policy(path, operating_mode=Mode.LOCAL_NODE_MESH)


def test_governance_gateway_delegates_to_existing_policy_primitive(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(
        '{"schema_version":1,"policy_version":"p1","mode":"LOCAL_NODE_MESH"}',
        encoding="utf-8",
    )
    gateway = bind_policy(path, operating_mode=Mode.LOCAL_NODE_MESH)
    context = AuthorityContext(
        actor_id="operator-1",
        authenticated=True,
        capabilities=frozenset({"report.read"}),
        scope="unit-test",
        mode=Mode.LOCAL_NODE_MESH,
        action_class=ActionClass.READ_ONLY,
    )

    result = gateway.authorize(context, "report.read", "unit-test")

    assert result.decision is Decision.ALLOW
    assert result.reason == "POLICY_CHECKS_PASSED"
    assert result.policy_version == "p1"


def test_governance_gateway_denies_context_with_different_bound_mode(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(
        '{"schema_version":1,"policy_version":"p1","mode":"LOCAL_NODE_MESH"}',
        encoding="utf-8",
    )
    gateway = bind_policy(path, operating_mode=Mode.LOCAL_NODE_MESH)
    context = AuthorityContext(
        actor_id="operator-1",
        authenticated=True,
        capabilities=frozenset({"report.read"}),
        scope="unit-test",
        mode=Mode.STRICT_OFFLINE,
        action_class=ActionClass.READ_ONLY,
    )

    result = gateway.authorize(context, "report.read", "unit-test")

    assert result.decision is Decision.DENY
    assert result.reason == "BOUND_MODE_MISMATCH"


def test_governance_gateway_never_promotes_defer_to_allow(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(
        '{"schema_version":1,"policy_version":"p1","mode":"LOCAL_NODE_MESH"}',
        encoding="utf-8",
    )
    gateway = bind_policy(path, operating_mode=Mode.LOCAL_NODE_MESH)
    context = AuthorityContext(
        actor_id="operator-1",
        authenticated=True,
        capabilities=frozenset({"protected.write"}),
        scope="unit-test",
        mode=Mode.LOCAL_NODE_MESH,
        action_class=ActionClass.PROTECTED,
        human_approval=False,
    )

    result = gateway.authorize(context, "protected.write", "unit-test")

    assert result.decision is Decision.DEFER
    with pytest.raises(PermissionError):
        gateway.require_allow(result)
