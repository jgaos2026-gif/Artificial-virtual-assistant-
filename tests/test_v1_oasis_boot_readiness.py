"""AVA v1 OASIS boot acceptance precondition guards.

These are NOT integrated acceptance tests. They deliberately report BLOCKED
while the repository exposes only the research-foundation doctor and no
OASIS runtime/health contract. When a real runtime contract is introduced,
replace these guards with contract-driven end-to-end tests; do not change the
expected marker merely to turn a skip into a pass.
"""
from __future__ import annotations

import pytest

from ava_military.doctor import inspect_environment


def _foundation_report() -> dict:
    return inspect_environment()


def test_ob01_runtime_boot_is_blocked_until_oasis_runtime_exists() -> None:
    """OB-01 remains BLOCKED; package diagnostics are not runtime boot."""
    report = _foundation_report()

    assert report["classification"] == "FOUNDATION_DIAGNOSTICS_ONLY"

    if report["integrated_runtime"] == "NOT_IMPLEMENTED":
        pytest.skip(
            "BLOCKED: main has no integrated OASIS runtime entry point, "
            "identity/policy lifecycle binding, or runtime health contract."
        )

    pytest.fail(
        "The foundation doctor no longer reports NOT_IMPLEMENTED. "
        "Do not promote OB-01: replace this precondition guard with real "
        "boot/identity/policy/health end-to-end acceptance tests."
    )


def test_ob02_live_health_is_blocked_until_real_health_contract_exists() -> None:
    """OB-02 remains BLOCKED; environment checks are not component health."""
    report = _foundation_report()

    assert report["classification"] == "FOUNDATION_DIAGNOSTICS_ONLY"

    if report["integrated_runtime"] == "NOT_IMPLEMENTED":
        pytest.skip(
            "BLOCKED: no OASIS health interface is present; the package "
            "doctor reports Python/package/environment facts only."
        )

    pytest.fail(
        "An integrated runtime marker appeared. Replace this guard with "
        "fault-injection tests proving health follows actual component state."
    )


def test_foundation_doctor_never_claims_integrated_runtime_health() -> None:
    """Regression guard: foundation diagnostics must remain honestly scoped."""
    report = _foundation_report()

    assert report["classification"] == "FOUNDATION_DIAGNOSTICS_ONLY"
    assert report["integrated_runtime"] == "NOT_IMPLEMENTED"
