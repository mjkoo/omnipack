# Tasks

## 1. Catalog links leave out default-valued settings

- [ ] 1.1 Make catalog link generation drop each GitHub and GitLab
  `additionalSettings` key equal to that source's default, leaving HTML
  entries, entries without a source type and every other field unchanged;
  verify with catalog tests where a GitHub default-valued setting and a GitLab
  default-valued setting are absent from the decoded link while their other
  settings survive, and the HTML redirect fixture still round-trips exactly
  (`uv run pytest tests/test_catalog.py`)
- [ ] 1.2 Record in the `settings_defaults.py` docstring that the GitHub and
  GitLab defaults were checked against Obtainium v1.7.5's form defaults, and
  why catalog links depend on them; verify the docstring reads correctly
  without any other document

## 2. The build records a README-size warning

- [ ] 2.1 Add the 460,800-byte threshold constant, documented with GitHub's
  512,000-byte render limit, and make the build record the nullable README-size
  field (the rendered README's size in bytes, or null when under the threshold
  or when no README was rendered); advance the build report schema version and
  its validation; verify with build tests that a README over the threshold
  records its size, one under it records null, and the build succeeds and
  publishes either way
- [ ] 2.2 Make `pack report` display a recorded README-size warning with its
  size and display nothing for it when the field is null; verify with report
  tests for both cases

## 3. The nightly raises an alert for the warning

- [ ] 3.1 Raise the `build/readme-size` finding from a build report that records
  the warning, titled with the size and giving the size and threshold in its
  details, and none when the field is null; verify with alert tests, adding a
  row to the existing build-warning table where one fits
- [ ] 3.2 Document the `build/readme-size` key and what it guards in
  `docs/alerts.md`, beside the other `build/` keys; verify the key table and
  the prose agree with the alert code

## 4. Integration check

- [ ] 4.1 Run `uv run pack build`, confirm the rendered README is under 460,800
  bytes and every catalog row still has its "Add to Obtainium" links, run
  `uv run pack verify` and the full `uv run pytest`, then discard the rebuilt
  `dist/` and README so the branch carries sources only
