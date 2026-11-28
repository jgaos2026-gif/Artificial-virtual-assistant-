"""Versioned AVA identity-fixture loading.

This loader performs strict structural validation for explicitly selected
development/test profiles. It does NOT authenticate an identity, verify a
signature, establish key custody, or grant capabilities.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


class IdentityLoadError(ValueError):
    """Raised when an identity fixture is missing or violates its schema."""


MAX_IDENTITY_BYTES = 64 * 1024

@dataclass(frozen=True, slots=True)
class IdentityRecord:
    schema_version: int
    identity_id: str
    epoch: int
    lineage_reference: str
    verification_key_reference: str | None
    capabilities: tuple[str, ...]
    profile: str


_ALLOWED_FIELDS = {
    "schema_version",
    "identity_id",
    "epoch",
    "lineage_reference",
    "verification_key_reference",
    "capabilities",
}
_SUPPORTED_SCHEMA_VERSION = 1
_ALLOWED_PROFILES = {"development", "test"}


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    """Reject duplicate JSON keys instead of silently accepting the last one."""
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise IdentityLoadError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _non_empty_string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise IdentityLoadError(f"{field} must be a non-empty string")
    return value.strip()


def load_identity(
    path: str | Path,
    *,
    profile: str,
) -> IdentityRecord:
    """Load a structurally valid identity fixture in an explicit dev/test profile.

    Production profiles are deliberately rejected until a cryptographic trust
    validator and key-custody integration are implemented and independently
    verified. The artifact's capabilities are descriptive metadata only.
    """
    if profile not in _ALLOWED_PROFILES:
        raise IdentityLoadError(
            "identity schema-only loading is permitted only in development or test profile"
        )

    identity_path = Path(path)
    try:
        # Read at most one byte beyond the limit so oversized input is rejected
        # without loading an attacker-controlled file completely into memory.
        with identity_path.open("rb") as stream:
            raw = stream.read(MAX_IDENTITY_BYTES + 1)
    except OSError as exc:
        raise IdentityLoadError("identity artifact is unavailable") from exc

    if len(raw) > MAX_IDENTITY_BYTES:
        raise IdentityLoadError(
            f"identity artifact exceeds the {MAX_IDENTITY_BYTES}-byte limit"
        )

    try:
        document = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except RecursionError as exc:
        raise IdentityLoadError("identity artifact exceeds the JSON nesting limit") from exc
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IdentityLoadError("identity artifact is not valid UTF-8 JSON") from exc

    if not isinstance(document, dict):
        raise IdentityLoadError("identity artifact root must be a JSON object")

    unknown = set(document) - _ALLOWED_FIELDS
    if unknown:
        raise IdentityLoadError(f"unsupported identity fields: {', '.join(sorted(unknown))}")

    version = document.get("schema_version")
    if type(version) is not int or version != _SUPPORTED_SCHEMA_VERSION:
        raise IdentityLoadError("unsupported or invalid identity schema_version")

    identity_id = _non_empty_string(document.get("identity_id"), "identity_id")
    epoch = document.get("epoch")
    if type(epoch) is not int or epoch < 1:
        raise IdentityLoadError("epoch must be a positive integer")

    lineage_reference = _non_empty_string(
        document.get("lineage_reference"), "lineage_reference"
    )

    key_reference_value = document.get("verification_key_reference")
    key_reference = (
        None
        if key_reference_value is None
        else _non_empty_string(key_reference_value, "verification_key_reference")
    )

    capabilities_value = document.get("capabilities", [])
    if not isinstance(capabilities_value, list) or any(
        not isinstance(item, str) or not item.strip() for item in capabilities_value
    ):
        raise IdentityLoadError("capabilities must be an array of non-empty strings")

    return IdentityRecord(
        schema_version=version,
        identity_id=identity_id,
        epoch=epoch,
        lineage_reference=lineage_reference,
        verification_key_reference=key_reference,
        capabilities=tuple(item.strip() for item in capabilities_value),
        profile=profile,
    )
