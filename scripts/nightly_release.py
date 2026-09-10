"""Owned rolling-release state and the explicit seed bootstrap operation."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Protocol

REPOSITORY = "mjkoo/omnipack"
TAG = "continuous"
OWNERSHIP_MARKER = "<!-- omnipack:rolling-pack -->"
STATE_START = "<!-- omnipack:rolling-state\n"
STATE_END = "\n-->"
RELEASE_PATH = f"/repos/{REPOSITORY}/releases/tags/{TAG}"
TAG_REF_PATH = f"/repos/{REPOSITORY}/git/ref/tags/{TAG}"
RELEASES_PATH = f"/repos/{REPOSITORY}/releases"
ASSET_NAMES = ("single-screen.json", "dual-screen.json")
_DIGEST = re.compile(r"[0-9a-f]{64}").fullmatch
_TITLE = re.compile(r"omnipack revision ([0-9]+)").fullmatch


class ReleaseError(RuntimeError):
    """The rolling release cannot be read or safely changed."""


class BootstrapConflict(ReleaseError):
    """Bootstrap found state it does not own or cannot safely replace."""


class Response(Protocol):
    @property
    def status(self) -> int: ...

    @property
    def body(self) -> bytes: ...


class GitHubApi(Protocol):
    def request(
        self, method: str, path: str, body: Mapping[str, object] | None = None
    ) -> Response: ...


@dataclass(frozen=True)
class DigestPair:
    single: str | None
    dual: str | None


@dataclass(frozen=True)
class PublishedTarget:
    revision: int
    source_commit: str | None
    digests: DigestPair


@dataclass(frozen=True)
class RollingState:
    completed: PublishedTarget
    pending: PublishedTarget | None


@dataclass(frozen=True)
class ReleaseAsset:
    asset_id: int
    name: str
    api_url: str


@dataclass(frozen=True)
class OwnedRelease:
    release_id: int
    title_revision: int
    state: RollingState
    assets: tuple[ReleaseAsset, ...]

    @property
    def asset_names(self) -> tuple[str, ...]:
        return tuple(asset.name for asset in self.assets)


@dataclass(frozen=True)
class BootstrapResult:
    release: OwnedRelease
    created: bool


def seed_body() -> str:
    """Return the canonical, machine-readable revision-zero seed body."""
    return state_body(
        RollingState(PublishedTarget(0, None, DigestPair(None, None)), None),
        introduction="Initial pack publication is pending; JSON assets are not yet published.",
    )


def state_body(
    state: RollingState, *, introduction: str = "Rolling pack publication state."
) -> str:
    """Encode the canonical owned state body without losing completed state."""

    def target(value: PublishedTarget) -> dict[str, object]:
        return {
            "revision": value.revision,
            "sourceCommit": value.source_commit,
            "digests": {
                ASSET_NAMES[0]: value.digests.single,
                ASSET_NAMES[1]: value.digests.dual,
            },
        }

    value = {
        "schemaVersion": 1,
        "completed": target(state.completed),
        "pending": None if state.pending is None else target(state.pending),
    }
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return f"{OWNERSHIP_MARKER}\n\n{introduction}\n\n{STATE_START}{encoded}{STATE_END}"


def parse_owned_release(document: object) -> OwnedRelease:
    """Parse and strictly validate an owned release for bootstrap or synchronization."""
    if not isinstance(document, dict):
        raise BootstrapConflict("release response must be an object")
    release_id = document.get("id")
    if (
        not isinstance(release_id, int)
        or isinstance(release_id, bool)
        or release_id <= 0
    ):
        raise BootstrapConflict("release id must be a positive integer")
    if document.get("tag_name") != TAG:
        raise BootstrapConflict("release tag does not match continuous")
    if document.get("draft") is not False or document.get("prerelease") is not True:
        raise BootstrapConflict("release must be a published prerelease")
    if "immutable" in document and not isinstance(document["immutable"], bool):
        raise BootstrapConflict("release immutable flag is malformed")
    if document.get("immutable") is True:
        raise BootstrapConflict("release is immutable")
    title = document.get("name")
    match = _TITLE(title) if isinstance(title, str) else None
    if match is None:
        raise BootstrapConflict("release title is malformed")
    state = parse_state(document.get("body"))
    title_revision = int(match.group(1))
    if title_revision != state.completed.revision:
        raise BootstrapConflict("release title disagrees with completed revision")
    assets = document.get("assets")
    if not isinstance(assets, list):
        raise BootstrapConflict("release assets must be a list")
    parsed_assets: list[ReleaseAsset] = []
    names: list[str] = []
    for asset in assets:
        if not isinstance(asset, dict) or not isinstance(asset.get("name"), str):
            raise BootstrapConflict("release asset metadata is malformed")
        name = asset["name"]
        if name not in ASSET_NAMES:
            raise BootstrapConflict(f"unexpected release asset: {name}")
        if name in names:
            raise BootstrapConflict(f"duplicate release asset: {name}")
        names.append(name)
        asset_id = asset.get("id")
        api_url = asset.get("url")
        if (
            not isinstance(asset_id, int)
            or isinstance(asset_id, bool)
            or asset_id <= 0
            or not isinstance(api_url, str)
            or not api_url.startswith("https://api.github.com/")
        ):
            raise BootstrapConflict("release asset metadata is malformed")
        parsed_assets.append(ReleaseAsset(asset_id, name, api_url))
    return OwnedRelease(release_id, title_revision, state, tuple(parsed_assets))


def parse_state(body: object) -> RollingState:
    if not isinstance(body, str) or not body.startswith(OWNERSHIP_MARKER + "\n"):
        raise BootstrapConflict("release ownership marker is absent")
    if body.count(OWNERSHIP_MARKER) != 1 or body.count(STATE_START) != 1:
        raise BootstrapConflict("release ownership state is ambiguous")
    start = body.find(STATE_START) + len(STATE_START)
    end = body.find(STATE_END, start)
    if end < 0 or body[end + len(STATE_END) :].strip():
        raise BootstrapConflict("release state block is malformed")
    try:
        value = json.loads(
            body[start:end],
            object_pairs_hook=_unique_object,
            parse_constant=lambda value: (_ for _ in ()).throw(
                ValueError(f"invalid JSON constant {value}")
            ),
        )
    except (json.JSONDecodeError, UnicodeError, ValueError) as error:
        raise BootstrapConflict("release state JSON is malformed") from error
    if not isinstance(value, dict) or set(value) != {
        "schemaVersion",
        "completed",
        "pending",
    }:
        raise BootstrapConflict("release state fields are malformed")
    if value["schemaVersion"] != 1 or isinstance(value["schemaVersion"], bool):
        raise BootstrapConflict("release state schema is unsupported")
    completed = _parse_target(value["completed"], "completed")
    pending_value = value["pending"]
    pending = None if pending_value is None else _parse_target(pending_value, "pending")
    if completed.revision == 0:
        if completed.source_commit is not None or completed.digests != DigestPair(
            None, None
        ):
            raise BootstrapConflict("revision zero must not claim published content")
    elif completed.source_commit is None or None in (
        completed.digests.single,
        completed.digests.dual,
    ):
        raise BootstrapConflict("completed publication metadata is incomplete")
    if pending is not None:
        if pending.revision != completed.revision + 1:
            raise BootstrapConflict("pending revision must follow completed revision")
        if pending.source_commit is None or None in (
            pending.digests.single,
            pending.digests.dual,
        ):
            raise BootstrapConflict("pending publication metadata is incomplete")
    return RollingState(completed, pending)


def _parse_target(value: object, label: str) -> PublishedTarget:
    if not isinstance(value, dict) or set(value) != {
        "revision",
        "sourceCommit",
        "digests",
    }:
        raise BootstrapConflict(f"{label} target fields are malformed")
    revision = value["revision"]
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        raise BootstrapConflict(f"{label} revision must be a nonnegative integer")
    commit = value["sourceCommit"]
    if commit is not None and (
        not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}", commit) is None
    ):
        raise BootstrapConflict(f"{label} source commit is malformed")
    digests = value["digests"]
    if not isinstance(digests, dict) or set(digests) != set(ASSET_NAMES):
        raise BootstrapConflict(f"{label} digest pair is malformed")
    values = [digests[name] for name in ASSET_NAMES]
    if any(
        item is not None and (not isinstance(item, str) or _DIGEST(item) is None)
        for item in values
    ):
        raise BootstrapConflict(f"{label} digest is malformed")
    return PublishedTarget(revision, commit, DigestPair(values[0], values[1]))


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field {key}")
        result[key] = value
    return result


def bootstrap_release(api: GitHubApi) -> BootstrapResult:
    """Create the canonical seed once, reconciling an ambiguous create by readback."""
    existing = _get_optional(api, RELEASE_PATH, "release")
    if existing is not None:
        return BootstrapResult(parse_owned_release(existing), False)
    if _get_optional(api, TAG_REF_PATH, "tag") is not None:
        raise BootstrapConflict(
            "continuous tag already exists without the owned release"
        )
    payload: dict[str, object] = {
        "tag_name": TAG,
        "target_commitish": "main",
        "name": "omnipack revision 0",
        "body": seed_body(),
        "draft": False,
        "prerelease": True,
    }
    try:
        response = api.request("POST", RELEASES_PATH, payload)
    except OSError:
        return _reconcile_creation(api)
    if response.status == 201:
        return BootstrapResult(
            parse_owned_release(_json(response, "created release")), True
        )
    if response.status in {409, 422, 500, 502, 503, 504}:
        return _reconcile_creation(api)
    raise BootstrapConflict(f"release creation failed with status {response.status}")


def _reconcile_creation(api: GitHubApi) -> BootstrapResult:
    try:
        document = _get_optional(api, RELEASE_PATH, "release readback")
    except ReleaseError as error:
        raise BootstrapConflict("release creation outcome is unknown") from error
    if document is None:
        raise BootstrapConflict("release creation outcome is unknown")
    return BootstrapResult(parse_owned_release(document), True)


def _get_optional(api: GitHubApi, path: str, label: str) -> object | None:
    try:
        response = api.request("GET", path)
    except OSError as error:
        raise ReleaseError(f"{label} request failed") from error
    if response.status == 404:
        return None
    if response.status != 200:
        raise ReleaseError(f"{label} request failed with status {response.status}")
    return _json(response, label)


def _json(response: Response, label: str) -> object:
    try:
        return json.loads(response.body)
    except (json.JSONDecodeError, UnicodeError) as error:
        raise BootstrapConflict(f"{label} response is malformed") from error
