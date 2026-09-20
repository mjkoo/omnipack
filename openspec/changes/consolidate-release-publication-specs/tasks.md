## 1. Main specs

- [ ] 1.1 Synchronize both deltas into the main specs without archiving the change, and verify `openspec validate --specs --strict` passes all 10 specs and `openspec list --specs --json` reports 4 requirements for `rolling-pack-release` and 7 for `nightly-publishing`
- [ ] 1.2 Verify carried text by diffing each main spec against its pre-change version: the only differences are the edits proposal.md names, the two removed scenarios are absent, the three moved scenarios appear exactly once across the two specs, and "Main advances before a no-op" and "Release fails after a confirmed push" are untouched
- [ ] 1.3 Search `openspec/specs/`, `README.md`, `AGENTS.md`, `docs/`, `tests/`, `scripts/` and `src/` for the three retired requirement names and verify nothing outside `openspec/changes/` cites them

## 2. Documentation

- [ ] 2.1 Extend the device-acceptance note in `docs/curation.md` to say that acceptance also covers both stable JSON downloads and that controlled tests are not device or live publication acceptance, and verify the guide cites no change artifact

## 3. No-behavior-change evidence

- [ ] 3.1 Verify `git diff --stat main` lists only the two main specs, `docs/curation.md` and this change's directory, with nothing under `src/`, `scripts/`, `tests/`, `.github/`, `config/` or `dist/`
- [ ] 3.2 Run `just check-all` and verify it is green, including the write-side import guard that enforces the restated no-install rule
- [ ] 3.3 Record the results of 1.1 to 3.2 in `validation.md` in this change's directory

## 4. Review

- [ ] 4.1 Have an independent reviewer check every row of the proposal's sentence map against the synchronized main specs and the publisher's release step, confirming each removed sentence is governed by the text named and no rule lost its only statement; resolve or record each finding
