"""Writer-side report records and their shared wire vocabularies."""

from enum import StrEnum
from typing import Literal, NotRequired, TypedDict


class Status(StrEnum):
    """How a build, verification or source generation run ended."""

    SUCCESS = "success"
    FAILED = "failed"


class OfflineStatus(StrEnum):
    """The offline gate's verdict within a build, which may never reach it."""

    NOT_RUN = "not-run"
    SUCCESS = "success"
    FAILED = "failed"


class InputState(StrEnum):
    """Whether a verification input could be read when it was captured."""

    PRESENT = "present"
    MISSING = "missing"
    UNREADABLE = "unreadable"


class BuildStage(StrEnum):
    """The step of `pack build` that was running, as a failed build reports it."""

    INGESTION = "ingestion"
    COMPOSITION = "composition"
    RENDERING = "rendering"
    OFFLINE_VERIFICATION = "offline verification"
    REPORT_WRITING = "report writing"
    PUBLICATION = "publication"


class FindingRecord(TypedDict):
    stage: str
    code: str
    message: str
    variant: NotRequired[str]
    entry_id: NotRequired[str]
    index: NotRequired[int]
    field: NotRequired[str]


class OfflineVerdict(TypedDict):
    status: OfflineStatus
    findings: list[FindingRecord]


class Fingerprint(TypedDict):
    state: InputState
    sha256: NotRequired[str]
    error: NotRequired[str]


class VerificationReport(TypedDict):
    schemaVersion: int
    verifier: dict[str, str]
    mode: Literal["offline"]
    startedAt: str
    completedAt: str
    status: Status
    inputs: dict[str, Fingerprint]
    errors: list[FindingRecord]


def not_run_verdict() -> OfflineVerdict:
    return {"status": OfflineStatus.NOT_RUN, "findings": []}
