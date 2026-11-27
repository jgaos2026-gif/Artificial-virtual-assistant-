"""External custody contract only; no production transport is implemented."""
from __future__ import annotations
from typing import Any, Mapping, Protocol, runtime_checkable

from .custody_authority import (
    CheckpointCandidate, CustodyReceipt, CustodyUnavailable, FloorAttestation,
    PersistenceEvidence, VerificationResult,
)


@runtime_checkable
class CustodyAuthorityProtocol(Protocol):
    def prepare(self, candidate: CheckpointCandidate, transaction_id: str) -> CustodyReceipt: ...
    def commit(self, transaction_id: str, reservation_id: str, evidence: PersistenceEvidence) -> CustodyReceipt: ...
    def read_floor(self, stream_id: str) -> FloorAttestation: ...
    def verify_receipt(self, receipt: CustodyReceipt | Mapping[str, Any], **kwargs: Any) -> VerificationResult: ...
    def authorize_recovery(self, **kwargs: Any) -> CustodyReceipt: ...
    def revoke_authority(self, **kwargs: Any) -> CustodyReceipt: ...
    def query_transaction(self, transaction_id: str): ...


class ExternalCustodyAdapter:
    """Unconfigured placeholder, not a production custody service.

    A future adapter must target a separately administered service and pass its
    own threat model, key-custody, durability, and rollback acceptance gates.
    This class has no endpoint, credentials, or persistence.
    """
    custody_mode = "EXTERNAL_CUSTODY_NOT_CONFIGURED"

    def _unavailable(self, *_: Any, **__: Any):
        raise CustodyUnavailable("external custody is not implemented or configured")

    prepare = _unavailable
    commit = _unavailable
    read_floor = _unavailable
    verify_receipt = _unavailable
    authorize_recovery = _unavailable
    revoke_authority = _unavailable
    query_transaction = _unavailable