## Context

See proposal.md for why. The constraints that shape how:

- A MODIFIED requirement replaces its whole block at archive, and the CLI
  refuses one that omits or renames a scenario the main spec still has. So a
  scenario cannot be dropped, moved to another requirement or retitled by a
  delta alone.
- A capability's Purpose is not a delta operation; it is edited in the main spec.
- 23 requirements are restated in full, several of them over 60 lines. Hand
  copying that much converged text invites silent loss.
- Two rulings already stand and are not reopened: only decision-changing
  behavior becomes spec text, and development tooling is out of scope.
- The owner's rulings taken for this change: spec follows code for `meta` and
  for generated source types; identity-correction evidence is a maintainer
  obligation; the nightly wording is fixed rather than the workflow; the
  curation requirement is restated as outcomes.

## Goals / Non-Goals

**Goals:**

- Every sentence in the six touched specs is true of the shipped system.
- Each duplicated rule has one normative statement; other sites point at it by
  exact requirement name.
- No pack byte, composition result, workflow step or exit code changes.

**Non-Goals:**

- Moving or merging capabilities. No boundary is wrong, so this is not a
  restructure.
- Specifying defensive plumbing, diagnostic text formats or workflow limits.
- Making the pipeline verify manifest evidence, or fetching any APK.
- Changing what the nightly publishes when a preparing step fails.

## Decisions

**Deltas are generated, not typed.** Each MODIFIED block was produced by copying
the requirement out of the main spec and applying exact-match replacements, each
asserted to match once. Everything outside a replacement is byte-identical to
the main spec, so a reviewer can diff a delta block against its source and see
only intended edits. Alternative: write blocks by hand. Rejected for the
transcription risk across roughly 1,300 lines.

**Scenarios stay where they are.** The owning requirement takes the normative
sentence; scenarios illustrating it remain under the requirement they sit in,
and twin scenarios are narrowed to the half their own requirement owns instead
of deleted. Alternative: REMOVED plus ADDED to move them. Rejected: it renames
requirements to relocate text whose content does not change.

**Owners.** Pin-first belongs to "Explicit selections identify an eligible
candidate" because that requirement already defines what a pin is and when it
fails. Denials belong to "Package denials exclude candidates from both
variants". Eligibility belongs to "Each build is a baseline build or a
dual-screen build" in `pack-composition`, not to `source-ingestion`, because the
prohibition is on composition settings; each source's requirement keeps its own
half, that the source alone decides kind and eligibility. Stage order keeps
"honoring a valid explicit pin first" because the order of pin and tier is that
requirement's own rule; it gains the pointer.

**`pack-verification` gets no delta.** It already owns the fingerprint set, the
stored-report content rule and the regeneration rule. The duplication is removed
from the `pack-cli` side only, which keeps the display obligations.

**The dead verification state is deleted with a schema bump.** Dropping the
`complete` field changes the stored report's shape, and the reader validates an
exact shape, so the verification schema version advances and an older report
draws the existing regeneration diagnostic. Alternative: keep writing
`complete: true` forever. Rejected: a field that can hold one value is retired
state under another name. No spec enumerates the field, so no delta follows.

**One requirement is renamed and modified together.** The delta carries the
RENAMED pair and the MODIFIED block under the new name; strict validation
accepts the combination. Nothing outside the spec cites the old title.

**Scenario titles are retitled outside the delta mechanism.** A stale title in a
requirement this change modifies is edited in the main spec and the delta in one
commit, so the names agree and validation passes. A title elsewhere is a plain
direct edit.

**The regex rule states the accepted subset as an outcome.** "Constructs that
mean the same to the validating engine and to the Obtainium client" is the rule;
the listed rejections follow from it and match what validation rejects today.

**The installation-path rule is stated at the level a policy author needs:**
words plus an acceptable `https` URL. The list of filler words validation
ignores is not specified; it is plumbing behind "say in words".

## Risks / Trade-offs

- [A pointer names a requirement that is later renamed] → Every pointer uses the
  exact title; the rename in this change was grepped across specs, docs and
  code. The audit that found these is the backstop.
- [A generated replacement changes meaning while looking like a tidy] →
  Converge reviews each block against its source; the replacement list is short
  and every entry is named in the proposal.
- [Narrowed twin scenarios lose a behavior assertion] → Each narrowed scenario's
  composition half remains asserted by its twin in `pack-composition` or by
  "Main push succeeds and release write fails", and by existing tests.
- [The schema bump strands a local report] → The diagnostic names the command to
  run; the file is gitignored and the nightly deletes and regenerates it.
- [One large change is harder to review than several] → Accepted by the owner in
  exchange for one PR. Commits are split by capability so each can be read
  alone.

## Migration Plan

Rerun `pack verify` once after the change lands to regenerate
`.build/verify.json`. Nothing else migrates. Rollback is a revert of the branch;
no published file, release or workflow depends on it.
