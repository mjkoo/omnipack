## Why

A read of all ten main specs against the code found no requirement the system
fails, but it found three kinds of rot that will mislead the next change: rules
the code enforces that no requirement states, sentences that are false in an
edge nobody has hit yet, and rules stated in three to six places with nothing
keeping the copies in agreement. It also found one retired state the code still
guards and tests. Every copy agrees today, and no active change holds a delta,
so this is the cheapest moment to give each rule one owner and make each
sentence true.

## What Changes

Spec text brought up to the shipped behavior, with no behavior change:

- `source-ingestion`: `meta` is RJNY catalog metadata and is dropped from a
  record of any source; the "every unmodeled field is retained" rule says so
  instead of claiming no other field name is reserved.
- `source-ingestion`: a committed codm2000 entry's declared source type wins
  over URL inference, exactly as for extras, and an RJNY or BBoi34 record that
  declares none fails. The requirement names the sources instead of relying on
  "upstream catalog", which the spec uses in two senses.
- `pack-composition`: an identity correction's manifest evidence is the
  maintainer's obligation, which the pipeline does not verify, matching the
  wording already used for GitLab extras.
- `pack-composition`: three shipped behaviors are stated. A policy selector's
  URL is validated like an overlay record's. A denial whose only matches are
  eligible for neither pack counts as matched, removes nothing and is not
  stale. The reported selection reason is defined for each case, including
  that dual reports ordinary fallback whenever the family has no available
  dual-screen build.
- `readme-source-generation`: the scenario "Exported title filter and consumer
  fallback reach the client" no longer sets up a state in which generation
  fails; the reviewed-regex rule states the whole accepted subset instead of
  eight of the rejected escapes; a track-only rule's required `rationale` and
  the shape of its installation text are stated; the base revision is required
  in the run summary of a run whose staging succeeds, not unconditionally.
- `nightly-publishing`: a failure in the job that prepares the candidate,
  including a summary or upload failure there, means the run publishes nothing
  and a later run makes its own attempt; a completed push is never undone. The
  phrase "without undoing a prepared candidate" goes. A rerun of a write job
  whose own push already landed fails as "main advanced", and recovery is a new
  run; this was already the decided behavior and is now written down.
- `pack-curation`: the requirement protecting curated decisions states guarded
  outcomes and what may block a source proposal, without legislating "the test
  suite". The two catalog validity rules no pipeline stage checks stay owned
  here.

One owner per rule, with pointers elsewhere:

- Pin-first selection is owned by "Explicit selections identify an eligible
  candidate". "A denial removes builds, not families" is owned by "Package
  denials exclude candidates from both variants". "No composition setting
  changes a build's eligibility or dual preference" is owned by "Each build is
  a baseline build or a dual-screen build". The restatements in
  `pack-composition` and in four `source-ingestion` requirements become
  pointers, and two `source-ingestion` scenarios that duplicated
  `pack-composition` scenarios are narrowed to their ingestion half. Every
  scenario stays under the requirement it sits in today: a modified requirement
  cannot drop or rename a scenario, and moving one would force a requirement to
  be removed and re-added for no gain.
- `pack-cli`'s report-command requirement states each rule once. Freshness
  points at the fingerprint set `pack-verification` defines instead of
  restating part of it, and the stored-report content rule is left to
  `pack-verification`, which already owns it.
- `nightly-publishing`: "Release fails after a confirmed push" and "Main push
  succeeds and release write fails" state the same WHEN and THEN under two
  requirements. The first is narrowed to what its own requirement owns, the
  summary's two separate outcomes; that the workflow fails stays with the
  second.

Retired by this change:

- Two requirement sentences that describe a past change rather than a fact
  ("Existing non-GitHub URL comparison semantics SHALL remain unchanged",
  "Unconfigured projects SHALL preserve their existing defaults"), and three
  restatements of rules owned elsewhere (the tracker sentence in
  `readme-source-generation`, the raw-main and tracker-exclusion sentence in
  `pack-curation`, the selector-validation sentences in the codm2000
  requirement).
- The composition halves of three twin scenarios, each narrowed rather than
  removed: `nightly-publishing` "Release fails after a confirmed push",
  `source-ingestion` "Ordinary extra competes with a dual fork" and "Id present
  in both BBoi34 assets".
- The requirement title "Entries are unioned by package id under a fixed
  precedence", renamed to describe per-family selection. Nothing outside the
  spec cites it.
- **BREAKING** for stored diagnostics only: the verification report's
  `complete` field and its `running` status, which `pack verify` has not been
  able to write since it began writing once on completion. The report schema
  version advances, so an existing `.build/verify.json` draws the documented
  regeneration diagnostic. The `Complete:` line leaves `pack report`.

Code and tests:

- Delete the unreachable incomplete-verification state from the report reader,
  its display line and its test; update `docs/verification.md`.
- An unreadable verification input is reported as unreadable, not also as
  missing. `pack report`'s help text describes both reports.
- Tests for scenarios that have none: an empty configured location for BBoi34
  and codm2000, `meta` on a non-RJNY record, a codm2000 record declaring a
  source type that differs from its URL, an upstream record declaring no source
  type, a policy selector URL with no host, a denial matching only
  never-eligible candidates, an APK rule's exported `fallbackToOlderReleases`,
  a track-only title filter, a designated curated extra shown to fail its guard
  when denied, an absent losing candidate leaving offline verification clean,
  and an interrupted verification through the command.

Wording-only edits to text no delta touches, made directly in the main specs:
the Purposes of `pack-composition`, `source-ingestion`, `nightly-publishing`
and `pack-cli`; "the helper" with no antecedent; one name for stale exclusions
in `pack-cli`; an overlay scenario whose WHEN reads as the wrong failure;
formatting. Scenario titles whose bodies moved on are retitled the same way. A
title inside a requirement this change modifies is edited in the main spec and
in the delta together, since the two must agree for the change to validate.

Deliberately left alone: the 65536-character cap on rendered retained failures
and the PR-body edit on an unchanged tree are diagnostic formats, and a visible
failure plus a rerun covers both. The 60-minute, 14-day and one-day workflow
values stay untested, as already decided. `rolling-pack-release` and
`pack-verification` need no delta.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `source-ingestion`: `meta` handling; declared versus derived source type per
  source; pointers replacing restated composition rules in the RJNY, BBoi34,
  extras and codm2000 requirements; two change-era sentences in the GitLab
  requirement.
- `pack-composition`: one owner each for pin-first, denial and eligibility
  rules; identity-correction evidence as a maintainer obligation; selector URL
  validation; denial of never-eligible candidates; selection reason semantics;
  one requirement renamed.
- `pack-curation`: curated-decision protection restated as outcomes; the
  tracker requirement loses a restatement and its two scenarios describe their
  own WHEN.
- `readme-source-generation`: the fallback-export scenario; the accepted regex
  subset; track-only rule fields; change-era sentences; the base-revision
  summary condition.
- `nightly-publishing`: what a preparing-job failure means; rerun after a
  landed push; one retired twin scenario.
- `pack-cli`: the report-command requirement states each rule once and points
  at `pack-verification` for the fingerprint set and stored-report content.

## Impact

- Specs: six capabilities, 23 modified requirements, one of them also renamed.
- Code: `src/omnipack/report.py`, `src/omnipack/verify.py`,
  `src/omnipack/offline.py`, `src/omnipack/cli.py`. No change to pack bytes,
  composition, ingestion, generation or the workflows.
- Docs: `docs/verification.md`.
- A stored `.build/verify.json` from before this change needs `pack verify`
  rerun. The file is gitignored and the nightly regenerates it every run.

Estimate: 0 requirements added, 0 removed, 1 renamed, 23 modified. 13 scenarios
added, none retired or moved, 3 narrowed. Implementation: about 40 lines removed
and 15 added. Tests: about 220 lines added and 25 removed.
