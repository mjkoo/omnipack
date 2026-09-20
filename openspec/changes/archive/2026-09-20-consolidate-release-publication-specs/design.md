## Context

See proposal.md for motivation and the ownership table. Two constraints shape
the deltas.

The first is the archive tooling. A MODIFIED block replaces the whole
requirement, and both validation and archive refuse a MODIFIED block that omits
a scenario the current requirement has. A requirement cannot appear in both
REMOVED and ADDED under one name. So a requirement can gain scenarios or change
text in place, but it can lose a scenario only by being removed and re-added
under a new name. RENAMED plus MODIFIED on one requirement is accepted, with
the MODIFIED block under the new name.

The second is reviewability. A reviewer has to be able to tell text that moved
from text that changed, across two specs.

## Goals / Non-Goals

**Goals:**

- One normative statement per release rule, in its owner, with one reference
  from the other capability by requirement name. `pack-curation` already
  references the release title format this way.
- Every owner rule ends with at least one scenario.
- Carried text is byte-identical to its source except where the proposal names
  an edit.

**Non-Goals:**

- Any change to what the publisher does, including the accepted non-atomic
  asset replacement, which carries forward untouched.
- Removing every restatement. See "Left in place" below.
- The `pack-cli` and `pack-verification` overlap. It was re-read for this
  change and already reads as intended: `pack-cli` says it adds only the
  command-surface obligations and cites `pack-verification` by name.

## Decisions

**Own rules by subject, not by file.** `rolling-pack-release` owns when a
release write is permitted and what it does. `nightly-publishing` owns what the
run does around the release stage. The alternative, moving every release rule
into `rolling-pack-release`, would have a release spec governing workflow exit
status and summary layout, which it cannot otherwise speak to. The opposite
alternative, giving `nightly-publishing` all run sequencing, would leave "when
may the release be written" outside the release spec, where a reader looks
first.

**Give the write preconditions their own requirement.** The reference from
`nightly-publishing` needs a target whose name says what it governs, and
"Revision changes follow completed content publication" is two long paragraphs
about digests and revisions. Because one scenario leaves it, the tooling
requires that requirement to be removed and re-added under a new name anyway,
so the split costs nothing extra. The alternative, leaving the three sentences
where they are and adding the moved scenarios beside the digest scenarios, was
rejected for the unclear reference target.

**Replace, do not modify, the nightly completion requirement.** It loses four
scenarios, so it is removed and re-added as "Release synchronization follows
main publication without gating it". The new name states what is left.

**Generate the deltas mechanically.** The delta files were produced by copying
requirement blocks from the main specs and applying exact-match substitutions
that fail when a match is absent or ambiguous. Line breaks inside carried
paragraphs are deliberately left ragged where a clause was cut, so a diff
against the main spec shows only the named edits.

**Left in place, deliberately.**

- Scenario clauses that observe the other capability's outcome, such as "the
  main result remains valid" under the bootstrap scenarios. They demonstrate
  their own requirement and are not rule statements.
- "Main advances before a no-op" stays under "Main publication is one normal
  push". Its WHEN is a run event, and moving one scenario would force that
  requirement to be removed and re-added for no change in its text. The
  main-must-not-have-moved rule still gets a scenario in its owner through
  "Write job rerun after main advanced".
- "Release fails after a confirmed push" (summary requirement) and "Main push
  succeeds and release write fails" (completion requirement) share a WHEN.
  Both are inside `nightly-publishing`, so this is not cross-capability
  duplication, and dropping one would force a third remove-and-re-add.
- The main push requirement's "fail without a push or release write". It
  describes the job failing, not a second statement of the write precondition.

**Relocate the acceptance paragraph to the curation guide.** That guide
already says device import, notification, acknowledgement and re-import need
separate device acceptance. It gains unchanged polling and both stable JSON
downloads as acceptance checks, preserves the revision-change notification
wording, and states that controlled tests are not completed device or live
publication acceptance.

## Risks / Trade-offs

- [A reviewer reads a removed sentence as a dropped rule] → the proposal's
  sentence map names the governing text for each, and the two wording
  divergences are called out with the text chosen.
- [A divergence turns out to be substantive under review] → settle that
  wording in its own change first and let this one perform only the move.
- [Three requirement names change, and the archived changes cite the old
  names] → archives are history and are not edited; nothing live cites them,
  which the tasks re-check by search.
- [The restated no-install rule is read as weaker than the standard-library
  rule] → it is broader: it forbids any installed dependency rather than naming
  one language's standard library. The import-guard test is unchanged.
