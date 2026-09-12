"""Standard-library write-side publication: push the candidate, sync the release.

This module runs on the runner's preinstalled `python3` in the write job, with
no project environment installed. It imports only the standard library and the
`scripts` package, so it must not import anything from `omnipack` or from a
module that does.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from scripts.workflow_support import (
    FULL_SHA,
    DiffEntry,
    GhRunner,
    HandoffRejected,
    SubprocessGhRunner,
    append_summary,
    git,
    ls_remote_sha,
    verify_handoff,
)

ALLOWED_PATHS = (
    "dist/single-screen.json",
    "dist/dual-screen.json",
    "README.md",
)
ASSET_NAMES = ("single-screen.json", "dual-screen.json")
TAG = "continuous"
MARKER = "<!-- omnipack:rolling-pack -->"
_TITLE = re.compile(r"omnipack revision ([0-9]+)")
_RECORD = re.compile(
    r"<!-- omnipack:digests single-screen\.json=([0-9a-f]{64})"
    r" dual-screen\.json=([0-9a-f]{64}) commit=([0-9a-f]{40}) -->"
)
BOOTSTRAP_GUIDANCE = (
    'bootstrap it once as "One-time rolling release bootstrap" in '
    "docs/publishing.md describes: "
    '`gh release create continuous --prerelease --title "omnipack revision 0" '
    "--notes-file <file>`"
)


class PushFailure(RuntimeError):
    def __init__(self, summary: str) -> None:
        super().__init__(summary)
        self.summary = summary


class ReleaseFailure(RuntimeError):
    def __init__(self, reason: str, *, bootstrap: bool = False) -> None:
        super().__init__(reason)
        self.reason = reason
        self.bootstrap = bootstrap


@dataclass(frozen=True)
class PushOutcome:
    status: str  # "published" or "failed"
    summary: str


@dataclass(frozen=True)
class ReleaseOutcome:
    status: str  # "unchanged", "repaired", "advanced" or "failed"
    summary: str


def run_push(
    root: Path,
    bundle_path: Path,
    candidate_sha: str,
    base_sha: str,
    *,
    gh: GhRunner | None = None,
) -> PushOutcome:
    """Verify the handed-off commit and push it to main, detaching afterward.

    Every check below runs before any push, so a rejected hand-off changes
    neither the local checkout nor the remote.
    """
    selected_gh = gh or SubprocessGhRunner()
    if (
        FULL_SHA.fullmatch(candidate_sha) is None
        or FULL_SHA.fullmatch(base_sha) is None
    ):
        return PushOutcome("failed", "push failed")

    generic = f"push failed for {candidate_sha}"
    try:
        try:
            entries = verify_handoff(root, bundle_path, candidate_sha, base_sha)
        except HandoffRejected:
            raise PushFailure(generic) from None
        if not _allowed_diff(entries):
            raise PushFailure(generic)

        auth_result = selected_gh.run(["auth", "setup-git"])
        if auth_result.returncode != 0:
            raise PushFailure(generic)
        remote_main = ls_remote_sha(root, "refs/heads/main")
        if remote_main is None:
            raise PushFailure(generic)
        if remote_main != base_sha:
            raise PushFailure(f"{generic}: main advanced")

        push_result = git(root, "push", "origin", f"{candidate_sha}:refs/heads/main")
        if push_result.returncode != 0:
            raise PushFailure(generic)

        detach_result = git(root, "checkout", "--detach", candidate_sha)
        if detach_result.returncode != 0:
            raise PushFailure(generic)
    except PushFailure as failure:
        return PushOutcome("failed", failure.summary)
    return PushOutcome("published", f"published {candidate_sha}")


def run_release(root: Path, *, gh: GhRunner | None = None) -> ReleaseOutcome:
    """Synchronize the owned rolling release from the JSON pair at `HEAD`."""
    selected_gh = gh or SubprocessGhRunner()
    try:
        try:
            single = (root / "dist/single-screen.json").read_bytes()
            dual = (root / "dist/dual-screen.json").read_bytes()
        except OSError:
            raise ReleaseFailure("could not read release assets") from None
        single_digest = sha256(single).hexdigest()
        dual_digest = sha256(dual).hexdigest()

        head_result = git(root, "rev-parse", "HEAD")
        if head_result.returncode != 0:
            raise ReleaseFailure("could not read HEAD")
        head = head_result.stdout.strip()

        auth_result = selected_gh.run(["auth", "setup-git"])
        if auth_result.returncode != 0:
            raise ReleaseFailure("gh auth setup-git failed")

        remote_main = ls_remote_sha(root, "refs/heads/main")
        if remote_main is None:
            raise ReleaseFailure("could not read remote main")
        if remote_main != head:
            raise ReleaseFailure("main advanced")

        view_result = selected_gh.run(
            [
                "release",
                "view",
                TAG,
                "--json",
                "name,body,assets,isDraft,isPrerelease,isImmutable",
            ]
        )
        if view_result.returncode != 0:
            raise ReleaseFailure("release is missing", bootstrap=True)
        try:
            document = json.loads(view_result.stdout)
        except json.JSONDecodeError:
            raise ReleaseFailure(
                "release response is malformed", bootstrap=True
            ) from None
        if not isinstance(document, dict):
            raise ReleaseFailure("release response is malformed", bootstrap=True)

        body = document.get("body")
        if not isinstance(body, str) or body.count(MARKER) != 1:
            raise ReleaseFailure("release ownership marker is absent", bootstrap=True)
        title = document.get("name")
        title_match = _TITLE.fullmatch(title) if isinstance(title, str) else None
        if title_match is None:
            raise ReleaseFailure("release title is malformed", bootstrap=True)
        title_revision = int(title_match.group(1))
        if document.get("isDraft") is not False:
            raise ReleaseFailure("release is a draft", bootstrap=True)
        if document.get("isPrerelease") is not True:
            raise ReleaseFailure("release is not a prerelease", bootstrap=True)
        if document.get("isImmutable") is not False:
            raise ReleaseFailure("release is immutable", bootstrap=True)

        served = _served_digests(document.get("assets"))
        record = _parse_record(body)
        record_matches = record is not None and record[:2] == (
            single_digest,
            dual_digest,
        )
        served_matches = (
            served.get("single-screen.json") == single_digest
            and served.get("dual-screen.json") == dual_digest
        )

        if record_matches and served_matches:
            return ReleaseOutcome(
                "unchanged", f"unchanged at revision {title_revision}"
            )

        if record_matches:
            _upload(selected_gh)
            return ReleaseOutcome("repaired", f"repaired at revision {title_revision}")

        _upload(selected_gh)
        new_revision = title_revision + 1
        _edit(
            selected_gh, new_revision, _canonical_body(single_digest, dual_digest, head)
        )
        return ReleaseOutcome("advanced", f"revision {new_revision}")
    except ReleaseFailure as failure:
        guidance = f"; {BOOTSTRAP_GUIDANCE}" if failure.bootstrap else ""
        return ReleaseOutcome("failed", f"release failed: {failure.reason}{guidance}")


def _upload(gh: GhRunner) -> None:
    result = gh.run(
        [
            "release",
            "upload",
            TAG,
            "dist/single-screen.json",
            "dist/dual-screen.json",
            "--clobber",
        ]
    )
    if result.returncode != 0:
        raise ReleaseFailure("asset upload failed")


def _edit(gh: GhRunner, revision: int, body: str) -> None:
    with tempfile.TemporaryDirectory() as directory:
        notes_path = Path(directory) / "release-notes.md"
        notes_path.write_text(body, encoding="utf-8")
        result = gh.run(
            [
                "release",
                "edit",
                TAG,
                "--title",
                f"omnipack revision {revision}",
                "--notes-file",
                str(notes_path),
            ]
        )
    if result.returncode != 0:
        raise ReleaseFailure("release edit failed")


def _canonical_body(single_digest: str, dual_digest: str, commit_sha: str) -> str:
    return (
        f"{MARKER}\n\n"
        "Download the current pack pair directly from the stable URLs:\n"
        "- https://github.com/mjkoo/omnipack/releases/download/continuous/single-screen.json\n"
        "- https://github.com/mjkoo/omnipack/releases/download/continuous/dual-screen.json\n\n"
        f"<!-- omnipack:digests single-screen.json={single_digest} "
        f"dual-screen.json={dual_digest} commit={commit_sha} -->\n"
    )


def _served_digests(assets: object) -> dict[str, str | None]:
    served: dict[str, str | None] = {}
    if not isinstance(assets, list):
        return served
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = asset.get("name")
        if name not in ASSET_NAMES:
            continue
        digest = asset.get("digest")
        served[name] = (
            digest.removeprefix("sha256:")
            if isinstance(digest, str) and digest.startswith("sha256:")
            else None
        )
    return served


def _parse_record(body: str) -> tuple[str, str, str] | None:
    matches = _RECORD.findall(body)
    if len(matches) != 1:
        return None
    return matches[0]


def _allowed_diff(entries: Sequence[DiffEntry]) -> bool:
    """At least one entry, each an allowed path at mode 100644 on both sides."""
    return bool(entries) and all(
        entry.path in ALLOWED_PATHS
        and entry.old_mode == "100644"
        and entry.new_mode == "100644"
        for entry in entries
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python3 -m scripts.nightly_write")
    subparsers = parser.add_subparsers(dest="command", required=True)
    push_parser = subparsers.add_parser("push")
    push_parser.add_argument("--bundle", required=True, type=Path)
    subparsers.add_parser("release")
    arguments = parser.parse_args(argv)
    environ = os.environ

    if arguments.command == "push":
        outcome: PushOutcome | ReleaseOutcome = run_push(
            Path.cwd(),
            arguments.bundle,
            environ.get("CANDIDATE_SHA", ""),
            environ.get("BASE_SHA", ""),
        )
        append_summary(environ, outcome.summary + "\n")
        return 0 if outcome.status == "published" else 1

    outcome = run_release(Path.cwd())
    append_summary(environ, outcome.summary + "\n")
    return 0 if outcome.status != "failed" else 1


if __name__ == "__main__":
    sys.exit(main())
