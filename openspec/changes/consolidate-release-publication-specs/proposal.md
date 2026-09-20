## Why

The rules for writing the rolling release are stated twice, once in
`nightly-publishing` and once in `rolling-pack-release`, in different words.
Both specs say a release write needs a successful main push whose commit the
publisher established, or a verified main no-op. Both say main must still be at
the commit the pair came from. Both list the same six release states that earn
bootstrap guidance. `rolling-pack-release` in turn says three times that
release trouble never blocks or undoes main, which is a promise only the run
can keep. One implementation satisfies all of it: the release step of the
write-side publication script and the step ordering of the nightly workflow.

Two statements of one rule drift. The last publication change had to edit the
"established commit" precondition in both specs at once, and the two
main-must-not-have-moved sentences already read differently enough that a
reviewer has to check the code to learn they mean the same thing. Nothing
blocks fixing it now: no active change holds a delta on either capability.

## What Changes

Specified behavior is unchanged. No code, test, workflow or pack byte changes.
This is not a whole-requirement move, so "organization only" would undersell
it: sentences are deleted from one spec because the other already governs, and
the sentence map below is how a reviewer can tell moved text from edited text.

Each rule gets one owner, chosen by what the rule is about:

| Rule | Owner |
|---|---|
| A release write needs a verified pair from an established successful push or a verified no-op; a failed or erroring push prohibits it | `rolling-pack-release` |
| A release write needs main to still be at the pair's commit | `rolling-pack-release` |
| Which release states fail the stage with bootstrap guidance | `rolling-pack-release` |
| A later verified run repairs or advances the release from its own pair | `rolling-pack-release` |
| Release trouble never gates or undoes main, fails the workflow, and is summarized separately | `nightly-publishing` |

- `rolling-pack-release` gains "Release writes require an established main
  outcome", built from three sentences that today sit inside "Revision changes
  follow completed content publication", plus the scenarios that demonstrate
  them. The rest of that requirement continues as "The revision advances only
  when the published pair changes" with its text and remaining scenarios
  unchanged.
- `nightly-publishing`'s "Nightly completion includes rolling release
  synchronization" is replaced by "Release synchronization follows main
  publication without gating it", which keeps the four run-level rules and
  points at the write preconditions instead of restating them.
- The bootstrap-state list in `nightly-publishing`'s summary requirement
  becomes a reference to the requirement that owns the list.
- `rolling-pack-release` stops restating main's independence: one clause is
  dropped, one becomes a pointer to `nightly-publishing`, and a restated timing
  clause is dropped.
- The maintainer-acceptance paragraph leaves `rolling-pack-release`, and the
  requirement is renamed "Bootstrap is explicit". The paragraph has no scenario
  and nothing in the repository can implement it; it is a process note. The
  curation guide already lists import, notification, acknowledgement and
  re-import as needing device acceptance. It gains unchanged polling and both
  stable JSON downloads as acceptance checks, plus the limitation that controlled
  tests are not completed device or live publication acceptance.
- Separate line item, same capability: the credential requirement obliges the
  write job to run "scripts that import nothing outside the standard library,
  on the runner's preinstalled Python". That names how the boundary is met. It
  is restated as what the boundary buys: the job holding the credential runs
  only publication code that needs nothing installed, so it executes none of
  the project's dependencies. The rule stays a rule, and the existing test that
  rejects non-standard-library imports in write-side modules keeps enforcing
  it.

### Wording divergences and the governing text

- Main must not have moved. `nightly-publishing`: "at the run's pushed commit
  or, after a verified no-op, at the run's base revision".
  `rolling-pack-release`: "at the commit that pair came from". The publisher
  makes one comparison, remote main against its own checked-out revision, which
  is the pushed commit after a push and the base after a no-op.
  `rolling-pack-release`'s wording governs. It gains one clause from the other
  side, "otherwise the release stage SHALL fail without writes", because its
  own sentence required the condition without saying the stage fails. This is
  the only carried sentence that is not a verbatim copy.
- Failed push. `nightly-publishing`: "rejected or reports an error".
  `rolling-pack-release`: "failed or erroring". A rejected push is a failed
  push; `rolling-pack-release`'s wording governs.

### Sentence map

| Removed text | From | Governed by |
|---|---|---|
| "whose pushed commit the publisher can establish as its own local revision" | nightly completion | "A push that lands SHALL authorize release mutation only while..." in the new write-preconditions requirement |
| "A main push that is rejected or reports an error SHALL prohibit release writes in that run." | nightly completion | "a failed or erroring main push SHALL prohibit release mutation" |
| "Release writes SHALL also require main to still be at..." | nightly completion | "Release mutation SHALL also require main to still be at the commit that pair came from; otherwise the release stage SHALL fail without writes" |
| "A later run whose verified output is already on main SHALL synchronize the release as a verified no-op." | nightly completion | Follows from three retained rules: landed output is a verified no-op (main push requirement), a verified no-op authorizes a release write, and the run synchronizes after a verified no-op |
| The six bootstrap states | summary requirement | "An absent, unowned, malformed, draft, non-prerelease or immutable release SHALL fail that stage with bootstrap guidance" in "Bootstrap is explicit" |
| "or blocking otherwise valid main publication" | one owned release | "Release readiness SHALL NOT be a prerequisite for otherwise valid main output." |
| "after a successful main push or a verified main no-op" | bootstrap | First sentence of the write-preconditions requirement |
| "without undoing or preventing main publication" | bootstrap | "Release failure SHALL fail the workflow without undoing a successful main push", reached by a pointer sentence |
| Maintainer-acceptance paragraph | bootstrap | Curation guide retains both stable JSON downloads, import, unchanged polling, revision-change notification, acknowledgement, re-import and the controlled-test limitation; no longer normative |
| Scenario "Missing release seed" | nightly completion | "First normal run has no seed" and "Unowned release conflicts with synchronization", both of which keep their main-outcome clause |
| Scenario "Later main no-op repairs the release" | nightly completion | "Served asset is missing or unverifiable", "Interrupted upload, then the recorded pair returns", "Explicit seed creation enables a later run" |

Moved unchanged: "Main outcome is uncertain" and "Write job rerun after main
advanced" go from `nightly-publishing` to the write-preconditions requirement,
which today has no scenario for a failed push or for main having moved. "The
push lands but its commit cannot be established" moves with its sentence inside
`rolling-pack-release`.

### Retired and added

Retires 2 scenarios, 3 normative sentences and 5 normative clauses that
restated another spec, and one process paragraph. Adds 1 requirement net, made
of existing sentences (`rolling-pack-release` goes from 3 to 4;
`nightly-publishing` stays at 7), 0 new scenarios, 0 implementation lines, 0
test lines, and about two sentences in the curation guide.

The write-preconditions requirement concerns a race (main moving under a run).
It introduces no rule. Its content is already the visible-failure-plus-rerun
policy: the stage fails without writes and a later run repairs the release.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `rolling-pack-release`: becomes the single owner of when a release write is
  permitted; splits one two-subject requirement; drops its restatements of
  main's independence; drops a process paragraph and renames that requirement.
- `nightly-publishing`: keeps only the run-level release rules and references
  the rest; references the bootstrap-state list; restates the write job's
  no-install rule as a guarantee.

## Impact

- `openspec/specs/rolling-pack-release/spec.md` and
  `openspec/specs/nightly-publishing/spec.md`.
- `docs/curation.md`: unchanged polling, both stable JSON downloads and the
  controlled-test limitation added to its existing device-acceptance note.
- No change to `src/`, `scripts/`, `tests/`, `.github/workflows/`, `config/` or
  `dist/`. No other spec, doc or test cites a requirement this change renames;
  `pack-curation` cites "One owned rolling release publishes both variants",
  which keeps its name.
