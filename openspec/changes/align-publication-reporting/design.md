## Context

A build writes one machine-readable report to `.build/report.json`. Besides its
status, schema and offline verification verdict, that document carries five
diagnostic keys: `changes` (the package ids added and removed per variant since
the previous output, or null when composition did not complete),
`sourceAdmissions` (each admitted committed codm2000 candidate with its source,
project URL, entry kind and committed id), `denylistRemovals` (each denial that
excluded a candidate, with the package id, variant, family and reason),
`staleExclusions` (each denial that matched no candidate) and `selections` (each
family's winner per variant, with the candidates it beat and the reason it won).

`format_reports` displays `selections`, then the failing stage and error when
the build failed, then the offline verification verdict. It never reads the
other four keys. The report command requirement says the command shows
"recorded failures, warnings, incomplete attempts, verification mode and
observation time". No module produces a warning: the string does not appear in
the source, the scripts or the tests. `pack verify` builds its report in one
literal with `"complete": True` and writes it once, after every check has run,
so a report recording an incomplete attempt is unreachable through the CLI.

The publication capability has a parallel problem in prose rather than in code.
One requirement, "Actions records publication outcomes", carries nine scenarios
and two subjects: what a run writes to its step summary and uploads as
artifacts, and which job may hold the publication credential and what that job
may run. Three of its claims do not match the workflows. The read-only job's
summary line is `no-op at <sha>`, `prepared <sha>` or the failing stage, and the
requirement enumerates only the published commit, a no-op and the failing stage.
Both `actions/upload-artifact` steps live in the read-only job, which finishes
before the write job starts, so no upload can fail after a successful push.
And the write job's push step, having pushed, checks the published commit out;
when that checkout fails it logs the landed push, returns a summary naming the
published commit and exits nonzero, which leaves the release step skipped. The
comment in that branch says why: a release step running on the base checkout
would publish the wrong pair. The publication requirement nonetheless says the
publisher synchronizes the release after a successful main push.

## Goals / Non-Goals

**Goals:**

- Display every non-blocking diagnostic the build report already records.
- Say what `pack report` shows in terms of outcomes that exist.
- Separate what a publication run reports from which job holds its credential.
- Make the publication requirements true of the workflows as they are.

**Non-Goals:**

- Changing what a build records, the build report schema, or any workflow.
- Adding a blocking policy to any of these diagnostics: they stay non-blocking.
- Fixing the duplicated release rules that two capabilities both state; that
  consolidation is separate work and this change stays out of its way.
- Prescribing the printed layout. The requirement states what is displayed, not
  how a line is shaped.
- Addressing the scheduled nightly run. It runs `pack build` and `pack verify`
  and never invokes the report command, and this change touches no workflow, so
  the new display is reachable only in the local build-and-review loop.

## Decisions

### Display all four lists, including the candidate comparison

Excluding `changes` would be the harder position to defend: the build report
requirement obliges the report to record the apps added and removed since the
previous output, and that list is the first thing a maintainer wants after an
overlay edit. All four are displayed.

A null `changes` is not an empty `changes`. The build report requirement already
says a null comparison exists because no complete candidate output was produced
and must not be read as an empty pack, so displaying it as "no apps added or
removed" would state the opposite of what the report means. It is displayed as
an unavailable comparison, distinct from a build that added and removed nothing.

### Format-time validation, not stricter stored-report validation

The section is emitted in `format_reports` between the selections loop and the
stage and error lines, so a failed build still reads as diagnostics first, then
what stopped it. Element fields are checked where they are formatted, with the
existing string TypeGuard, raising the report format error, exactly as the
selection winner and considered-candidate formatters already do. The stored
report validator is not tightened: it accepts each of these keys as a list of
objects today, that acceptance is what keeps older reports readable, and moving
per-element field checks into it would reject reports the command can display.

### The schema version does not change

`BUILD_SCHEMA_VERSION` stays 3. Every key being displayed is already written by
every build, already a member of the accepted build field set, and already
validated. Displaying a key that is present changes nothing a validator inspects
and makes no previously written report unreadable, so a bump would force a
pointless regeneration of evidence that is still correct.

### Nothing recorded prints nothing

Each category contributes output only when the run recorded something in it.
This governs the genuinely empty categories, and it keeps existing assertions
about the command's output honest: a test that checks a substring is absent is
checking for a claim the command should not make, not for a section that should
never exist.

It does not make the ordinary build quiet. `sourceAdmissions` records one entry
per retained committed codm2000 catalog entry, and the catalog holds 30 apps;
`denylistRemovals` records one entry per denied candidate per eligible variant,
from five standing denials. Neither is empty in steady state, so the steady-state
report is long and every recorded entry is listed in full.

### The split assigns the credential-and-source-text scenario to reporting

Eight of the nine scenarios fall cleanly on one side. "Sensitive or executable
source text" does not: its outcome is that reporting neither executes upstream
diagnostic text nor exposes credentials, which reads as both a reporting rule
and a credential rule. Duplicating it would leave one requirement's scenario
living on both sides of the split, which is exactly what a split must avoid.

It goes to the reporting requirement, and the sentence it rests on goes with it:
what a summary or an artifact may contain, and that source text is data rather
than executable input, is a property of the output a run produces. The isolation
requirement keeps the boundary itself: which job holds the credential, which
steps receive it, that git runs with hooks disabled, that no checkout persists
it, and that the write job installs nothing and builds nothing. Read together
they are unchanged; read apart, each is about one thing.

### The publication findings are spec corrections, not code bugs

For each of the three, the code's behavior is the one a maintainer would choose:

- The read-only job genuinely has a fourth outcome to report. A prepared
  candidate that has been handed off but not yet pushed is neither a published
  commit nor a no-op nor a failure, and hiding it would make the summary less
  informative, not more correct. The enumeration gains it.
- Artifact upload cannot follow a push, because diagnostics are uploaded by the
  job that produces them. The scenario is restated over the two sequences that
  can occur, and keeps the outcome that already holds for both: the failing step
  stays visible and nothing already done is undone.
- Refusing to write the release after a push whose commit could not be checked
  out is deliberate. The alternative, synchronizing from whatever the workspace
  holds, would publish the base revision's pair under the new commit. The rule
  becomes: a release write requires the publisher to establish the pushed
  commit locally, and a run that cannot fails with the push reported and no
  release write. The existing repair path already covers what happens next, so
  nothing new is promised about recovery.

### The release precondition is stated where release writes are owned

Two capabilities both state release-write preconditions today, and separate work
will give those rules one owner, the rolling release capability. Writing this
new precondition into the publication capability would mean writing it twice and
deleting one copy later, so it goes straight to the owner: it joins the
requirement that already says release assets may only come from a verified pair
associated with a successful push or a verified no-op, and that mutation
requires main to still be at that commit.

The publication capability still has to stop asserting the opposite. Its
requirement "Nightly completion includes rolling release synchronization" opens
by promising synchronization after every successful push, which would contradict
the owner's precondition once both are main specs. That opening sentence is
conditioned on the publisher being able to establish the pushed commit locally
and nothing else in the requirement moves: the precondition's consequences, what
the run does when it cannot, stay with the owner.

### Scenario names change only where a requirement is new

A modified requirement must carry every scenario it has, so renaming one would
force removing and re-adding the whole requirement for no gain. The report
command requirement and the verification requirement keep every scenario name
and change only bodies. The two requirements the split produces are new, so
their scenario names are chosen fresh; eight are carried over unchanged and the
one naming a sequence that cannot occur is renamed to the sequences that can.

The scenario "Candidate verifies with warnings" keeps its name even though its
body stops saying warnings. The ruling on this finding was that the spec is
right and the word is made precise rather than retired, the scenario is about a
build whose non-blocking diagnostics do not block publication, and that is what
it still describes.

## Risks / Trade-offs

- Every build produces a longer report, not just an eventful one. Admissions and
  exclusions are listed in full on each run, and both are populated in steady
  state, so a routine `pack report` grows by tens of lines. That is the point of
  the change: a list that is only printed when something is wrong cannot show
  that a denial stopped matching. Only the genuinely empty categories stay
  silent.
- Output tests that assert on the whole of `pack report` need updating. Tests
  that assert substrings, which is the house style here, do not.
- Splitting one requirement into two means a later reader must consult both to
  reconstruct the full publication contract. The two subjects are independent
  enough that this is the smaller cost.
- The release precondition lands in a capability that separate work will
  reorganize. That work has to read this requirement either way; it reads one
  copy rather than two.

## Migration Plan

No migration. The build report document is unchanged, so reports written before
this change display with their diagnostics and no regeneration is prompted. The
workflows and publication scripts are untouched: the publication deltas describe
what they already do. Implement on the change branch with the deltas, run the
full suite and repository checks, and confirm on a real build that the section
appears with recorded diagnostics and is absent when there are none. Rollback
reverts the module, its tests and the deltas.
