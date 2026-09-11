"""Resumable synchronization of the owned rolling pack release."""

from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from typing import Protocol

from scripts.nightly_release import (
    ASSET_NAMES,
    BootstrapConflict,
    DigestPair,
    OwnedRelease,
    PublishedTarget,
    ReleaseAsset,
    ReleaseError,
    RollingState,
    parse_owned_release,
    state_body,
)


class ReleaseRemote(Protocol):
    def discover(self) -> object: ...
    def update(self, release_id: int, *, title: str, body: str) -> None: ...
    def delete_asset(self, asset: ReleaseAsset) -> None: ...
    def upload_asset(self, release_id: int, name: str, content: bytes) -> None: ...
    def download_asset(self, asset: ReleaseAsset) -> bytes: ...


@dataclass(frozen=True)
class SyncResult:
    revision: int
    changed: bool
    repaired: bool

    @property
    def outcome(self) -> str:
        return "success"

    @property
    def pending_revision(self) -> None:
        return None


class SyncFailure(ReleaseError):
    """A failed synchronization with the last readable pending revision."""

    outcome = "failure"

    def __init__(self, detail: str, pending_revision: int | None) -> None:
        super().__init__(detail)
        self.pending_revision = pending_revision


def synchronize_release(
    remote: ReleaseRemote, single: bytes, dual: bytes, source_commit: str
) -> SyncResult:
    """Publish one verified pair, promoting only after both remote bytes match."""
    if re.fullmatch(r"[0-9a-f]{40}", source_commit) is None:
        raise ReleaseError("source commit is malformed")
    discovery = _ReleaseDiscovery(remote)
    try:
        return _synchronize_release(remote, discovery, single, dual, source_commit)
    except SyncFailure:
        raise
    except ReleaseError as error:
        pending_revision = None
        try:
            observed = discovery.read().state.pending
            pending_revision = None if observed is None else observed.revision
        except ReleaseError:
            pass
        raise SyncFailure(str(error), pending_revision) from error


def _synchronize_release(
    remote: ReleaseRemote,
    discovery: _ReleaseDiscovery,
    single: bytes,
    dual: bytes,
    source_commit: str,
) -> SyncResult:
    desired = DigestPair(sha256(single).hexdigest(), sha256(dual).hexdigest())
    release = discovery.read()
    completed = release.state.completed
    changed = desired != completed.digests
    target = (
        PublishedTarget(completed.revision + 1, source_commit, desired)
        if changed
        else completed
    )

    if changed and release.state.pending != target:
        expected = RollingState(completed, target)
        release = _update_state(
            remote, discovery, release, completed.revision, expected
        )

    repaired = False
    for name, content, digest in zip(
        ASSET_NAMES, (single, dual), (desired.single, desired.dual), strict=True
    ):
        release, replaced = _ensure_asset(
            remote, discovery, release, name, content, digest
        )
        repaired = repaired or replaced

    # An upload acknowledgement, asset metadata, or one successful download is
    # never sufficient. Independently re-read and hash both remote objects.
    release = discovery.read()
    _verify_pair(remote, release, desired)

    final_state = RollingState(target, None)
    if release.title_revision != target.revision or release.state != final_state:
        release = _update_state(
            remote, discovery, release, target.revision, final_state
        )
    release = discovery.read()
    if release.title_revision != target.revision or release.state != final_state:
        raise ReleaseError("release promotion readback does not match desired state")
    _verify_pair(remote, release, desired)
    return SyncResult(target.revision, changed, repaired and not changed)


@dataclass
class _ReleaseDiscovery:
    """Keep every readback, including diagnostics, on the initial release."""

    remote: ReleaseRemote
    release_id: int | None = None

    def read(self) -> OwnedRelease:
        try:
            release = parse_owned_release(self.remote.discover())
        except BootstrapConflict:
            raise
        except OSError as error:
            raise ReleaseError("release discovery failed") from error
        if self.release_id is None:
            self.release_id = release.release_id
        elif release.release_id != self.release_id:
            raise ReleaseError("release identity changed during synchronization")
        return release


def _update_state(
    remote: ReleaseRemote,
    discovery: _ReleaseDiscovery,
    release: OwnedRelease,
    title_revision: int,
    state: RollingState,
) -> OwnedRelease:
    title = f"omnipack revision {title_revision}"
    body = state_body(state)
    try:
        remote.update(release.release_id, title=title, body=body)
    except OSError:
        readback = discovery.read()
        if readback.title_revision == title_revision and readback.state == state:
            return readback
        raise ReleaseError("release update outcome is unknown")
    readback = discovery.read()
    if readback.title_revision != title_revision or readback.state != state:
        raise ReleaseError("release update readback does not match requested state")
    return readback


def _ensure_asset(
    remote: ReleaseRemote,
    discovery: _ReleaseDiscovery,
    release: OwnedRelease,
    name: str,
    content: bytes,
    digest: str | None,
) -> tuple[OwnedRelease, bool]:
    existing = next((asset for asset in release.assets if asset.name == name), None)
    if existing is not None:
        try:
            if sha256(remote.download_asset(existing)).hexdigest() == digest:
                return release, False
        except OSError as error:
            raise ReleaseError(
                f"{name} download failed; replacement is not authorized"
            ) from error
        try:
            remote.delete_asset(existing)
        except OSError:
            readback = discovery.read()
            if any(asset.name == name for asset in readback.assets):
                raise ReleaseError(f"{name} deletion outcome is unknown")
        release = discovery.read()
        if any(asset.name == name for asset in release.assets):
            raise ReleaseError(f"{name} remains after deletion")

    try:
        remote.upload_asset(release.release_id, name, content)
    except OSError:
        release = discovery.read()
        candidate = next(
            (asset for asset in release.assets if asset.name == name), None
        )
        if candidate is None:
            raise ReleaseError(f"{name} upload outcome is unknown")
        try:
            if sha256(remote.download_asset(candidate)).hexdigest() != digest:
                raise ReleaseError(f"{name} upload readback digest differs")
        except OSError as error:
            raise ReleaseError(f"{name} upload readback failed") from error
        return release, True

    release = discovery.read()
    candidate = next((asset for asset in release.assets if asset.name == name), None)
    if candidate is None:
        raise ReleaseError(f"{name} is absent after upload")
    try:
        actual = sha256(remote.download_asset(candidate)).hexdigest()
    except OSError as error:
        raise ReleaseError(f"{name} upload readback failed") from error
    if actual != digest:
        raise ReleaseError(f"{name} upload readback digest differs")
    return release, True


def _verify_pair(
    remote: ReleaseRemote, release: OwnedRelease, digests: DigestPair
) -> None:
    for name, expected in zip(ASSET_NAMES, (digests.single, digests.dual), strict=True):
        asset = next((item for item in release.assets if item.name == name), None)
        if asset is None:
            raise ReleaseError(f"{name} is missing from release")
        try:
            actual = sha256(remote.download_asset(asset)).hexdigest()
        except OSError as error:
            raise ReleaseError(f"{name} verification download failed") from error
        if actual != expected:
            raise ReleaseError(f"{name} verification digest differs")
