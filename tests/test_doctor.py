from ava_military.doctor import inspect_environment


def test_doctor_marks_missing_package_and_old_python_as_blockers(monkeypatch):
    import ava_military.doctor as doctor
    monkeypatch.setattr(doctor.sys, "version_info", (3, 10, 0))
    monkeypatch.setattr(doctor.importlib.util, "find_spec", lambda name: None)
    report = inspect_environment()
    assert report["classification"] == "FOUNDATION_DIAGNOSTICS_ONLY"
    assert len(report["blockers"]) == 2
    assert report["integrated_runtime"] == "NOT_IMPLEMENTED"


def test_doctor_detects_invalid_source(tmp_path):
    report = inspect_environment(source=tmp_path)
    assert report["checks"]["source_exists"] is True
    assert report["checks"]["source_pyproject_exists"] is False
    assert any("pyproject.toml" in item for item in report["blockers"])


def test_doctor_does_not_claim_security_or_recovery_assurance():
    report = inspect_environment()
    assert report["production_security"] == "NOT_ASSESSED"
    assert report["backup_restore_drill"] == "NOT_RUN"
    assert report["external_anchor_and_sb712_quorum"] == "NOT_IMPLEMENTED"
