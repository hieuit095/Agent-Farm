"""Explicit candidate and PoC states used by both hunting pipelines."""

from dataclasses import dataclass
from enum import StrEnum


class CandidateStatus(StrEnum):
    DISCOVERED = "DISCOVERED"
    INVESTIGATING = "INVESTIGATING"
    CONFIRMED = "CONFIRMED"
    RULED_OUT = "RULED_OUT"
    OPEN_PROOF_GAP = "OPEN_PROOF_GAP"
    NEEDS_MANUAL_REVIEW = "NEEDS_MANUAL_REVIEW"


class PoCStatus(StrEnum):
    TRIGGERED = "triggered"
    NOT_TRIGGERED = "not_triggered"
    EXECUTION_ERROR = "execution_error"
    INCONCLUSIVE = "inconclusive"


@dataclass(frozen=True)
class PoCResult:
    status: PoCStatus
    reason: str


class EvidenceKind(StrEnum):
    POC_TRIGGERED = "POC_TRIGGERED"
    COUNTEREVIDENCE = "COUNTEREVIDENCE"
    PROOF_GAP = "PROOF_GAP"


class SecurityGateError(RuntimeError):
    """The requested state transition or publication lacks verified evidence."""
