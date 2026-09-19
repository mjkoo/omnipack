## Why

`pack report` is the command a maintainer runs locally, after a local build, to
find out what that build did. The report command requirement says it shows
recorded failures, warnings and incomplete attempts. Neither of the last two
exists. No build or verification code produces anything called a warning, and
`pack verify` writes its report once, at the end, with completeness hardcoded
true, so no run can record an incomplete attempt.

What the build does record, and what the build report requirement already
obliges it to record, is four lists of non-blocking outcomes: the apps added and
removed since the previous output, the denylist entries that excluded a
candidate, the denylist entries that matched no candidate, and the admitted
committed codm2000 candidates with their committed identities. All four are
written to the build report and none of them is ever displayed. The maintainer
guide tells readers to open the JSON file instead, which is the drift recorded
in prose: a denial that quietly stops excluding anything, or a family that
quietly switched packages, is invisible at the command that exists to show it.
The reach of this is the local build-and-review loop, where a maintainer builds
and then reports. The scheduled run never invokes the report command, so nothing
here changes what an unattended run surfaces.

The same region of the publication spec carries three further claims the
workflows do not support. It enumerates the main outcomes a run summarizes as
the published commit, a no-op, or the failing stage, while the read-only job
also summarizes a prepared candidate that has not been published yet. It has a
scenario for artifact upload failing after a successful push, although both
upload steps run in the read-only job, before any push exists. And it requires
release synchronization after every successful main push, although a run whose
push lands but which then cannot establish the published commit locally fails
without a release write, on purpose, so that the release stage can never run
against the base checkout.

One requirement in that region also does the work of two. "Actions records
publication outcomes" is one requirement with nine scenarios covering both what
a run reports and which job may hold the publication credential. Restating it
to fix the reporting wording means restating the credential boundary in the
same block, so the two are separated here rather than left fused.

## What Changes

- `pack report` displays the non-blocking build diagnostics the build report
  already records: the candidate changes, the denylist exclusions, the denylist
  entries that matched no candidate, and the admitted committed candidates. A
  category the run recorded nothing for contributes nothing to the output, and
  the recorded admissions and exclusions are listed in full on each run, so a
  steady-state build produces a long diagnostics section rather than a quiet
  one. A report whose candidate comparison is null is displayed as unavailable
  rather than as an empty one, which the build report requirement already
  forbids interpreting as an empty pack, and a comparison recorded by a failed
  build is displayed as candidates that were not published.
- **BREAKING**: the report command no longer promises to show warnings or
  incomplete attempts. Both name outcomes nothing produces. The recorded
  failures, verification mode, observation time and freshness labelling are
  unchanged.
- The build report schema is unchanged. Every displayed key is already written,
  already in the accepted field set, and already validated as a list of objects,
  so no stored report becomes unreadable and no regeneration is required.
- Split "Actions records publication outcomes" into one requirement for what a
  run summarizes and uploads and one for which job holds the publication
  credential and what it may run. Every rule and scenario is carried forward.
- The summarized main outcomes gain the prepared candidate that the read-only
  job hands off, which the enumeration omitted.
- The diagnostics-failure scenario is restated over the sequences that can
  actually occur: summary generation failing after a successful push, and
  artifact upload failing in the read-only job before any push exists.
- Release synchronization is required after a successful push only when the
  publisher can establish the published commit locally. A run that pushes and
  then cannot check that commit out fails with the push reported and no release
  write, and a later verified run repairs the release as a no-op.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-cli`: replace the report command requirement with one that names the
  non-blocking diagnostics the build report records instead of warnings and
  incomplete attempts, requires each recorded diagnostic to be displayed,
  requires an absent category to contribute nothing, requires the recorded
  admissions and exclusions to be listed in full each run, requires an
  unavailable candidate comparison to be distinguished from an empty one, and
  requires a failed build's comparison to be shown as candidates that were not
  published.
- `nightly-publishing`: remove "Actions records publication outcomes" and add
  the two requirements it becomes, one for run summaries, artifacts and their
  contents and one for job and credential isolation; state the prepared
  candidate as a summarized main outcome; restate the diagnostics-failure
  scenario over sequences the workflows can produce; name the release outcome
  in a run summary only when the release stage runs; replace the non-blocking
  warning sentence and its scenario in the verification requirement with the
  diagnostics the build actually records; and condition "Nightly completion
  includes rolling release synchronization" on the publisher being able to
  establish the pushed commit locally, so no unconditional claim that a
  successful push is followed by release synchronization survives this change.
- `rolling-pack-release`: require a release write to follow a push only when
  the publisher can establish the pushed commit locally, so a run that cannot
  fails with no release write and a later verified run repairs the release.

## Impact

Affects `src/omnipack/report.py` and `tests/test_report.py`. `docs/development.md`
loses the passage telling maintainers that `pack report` prints selections but
not the other three lists, and its description of the command stops naming
warnings. No workflow, configuration or schema changes: the publication
findings are all spec corrections against workflows and scripts that already
behave as described, and the build report document is byte-identical for every
build. Stored build and verification reports written before this change remain
readable and are displayed with their diagnostics.

Estimate: two requirements added and one removed, all three in the split, for a
net of one requirement; four requirements modified, two in `nightly-publishing`
and one each in `pack-cli` and `rolling-pack-release`. Five
scenarios added: three on the report command (diagnostics displayed, nothing
recorded, comparison unavailable), one for the prepared candidate, and one for
a push that lands without an establishable commit; one scenario restated during
the split and one inside a modified requirement; eight scenarios carried through
the split unchanged. Implementation adds roughly 25 to 40 lines in one module
and deletes none; tests add roughly 60 to 90 lines. What this retires: the
obligation to display warnings and incomplete attempts, neither of which any
run records; the single fused requirement covering both reporting and
credential isolation; the claim that artifact upload can fail after a
successful push; and the unconditional claim that a successful push is followed
by release synchronization in the same run. On the rule that a new requirement
about diagnostics or evidence must justify itself against a visible failure and
a rerun: it does not suffice here, and that is the finding. These four lists are
non-blocking by design, so no failure ever becomes visible and a rerun surfaces
nothing; the only way a stale denial or a switched package reaches the
maintainer is by being displayed. The two split requirements introduce no new
ownership or race rule; they carry the existing ones forward.
