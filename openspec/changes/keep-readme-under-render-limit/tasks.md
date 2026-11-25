# Tasks

## 1. Catalog links leave out default-valued settings

- [x] 1.1 Make catalog link generation drop each GitHub and GitLab
  `additionalSettings` key equal to that source's value in the defaults table,
  leaving HTML entries, entries without a source type and every other field
  unchanged; verify with catalog tests where a GitHub default-valued setting
  and a GitLab default-valued setting are absent from the decoded link while
  their other settings survive, a `0` kept against a `false` default, a GitHub entry whose settings string is not a
  JSON object round-trips exactly, and the HTML redirect fixture still
  round-trips exactly (`uv run pytest tests/test_catalog.py`)
- [x] 1.2 Record in the `settings_defaults.py` docstring that every listed
  GitHub and GitLab value equals what Obtainium v1.7.5 uses when the key is
  absent, and why catalog links depend on them; verify the docstring reads
  correctly without any other document

## 2. The nightly raises an alert when the README nears the limit

- [x] 2.1 After a build report records a successful build, make the
  nightly-prepare alert step read `README.md`'s size and raise the
  `build/readme-size` finding when it exceeds the 460,800-byte threshold,
  titled by whether it exceeds GitHub's 512,000-byte limit with no byte count,
  and giving the size, threshold and limit in its details; verify with alert
  tests for a README of 470,000 bytes (nearing), 520,000 bytes (past), exactly
  460,800 bytes (no finding), and a failed build (no finding, not in scope),
  adding rows to an existing build-warning table where one fits
- [x] 2.2 Document the `build/readme-size` key and what it guards in
  `docs/alerts.md`, beside the other `build/` keys; verify the key table and
  the prose agree with the alert code

## 3. Integration check

- [ ] 3.1 Run `uv run pack build`, confirm the rendered README is under 460,800
  bytes and every catalog row still has its "Add to Obtainium" links, run
  `uv run pack verify` and the full `uv run pytest`, then discard the rebuilt
  `dist/` and README so the branch carries sources only
