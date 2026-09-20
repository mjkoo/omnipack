## Context

See proposal.md for why. The constraints that shape how:

- A MODIFIED requirement replaces its whole block at archive, and the CLI
  refuses one that omits or renames a scenario the main spec still has. So a
  scenario cannot be dropped, moved to another requirement or retitled by a
  delta alone.
- A capability's Purpose is not a delta operation; it is edited in the main spec.
- 24 requirements are restated in full, several of them over 60 lines. Hand
  copying that much converged text invites silent loss.
- Two rulings already stand and are not reopened: only decision-changing
  behavior becomes spec text, and development tooling is out of scope.
- The owner's rulings taken for this change: spec follows code for `meta` and
  for generated source types; identity-correction evidence is a maintainer
  obligation; the nightly wording is fixed rather than the workflow; the
  curation requirement is restated as outcomes.

## Goals / Non-Goals

**Goals:**

- Every sentence in the seven touched specs is true of the shipped system.
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
only intended edits. The one exception is a paragraph holding an over-long line:
it is rewrapped in the delta with its words unchanged, because a rewrap made
only in the main spec would be reverted when the block is replaced at archive.
Alternative: write blocks by hand. Rejected for the
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

What a rerun of a write job does after main moved belongs to "Release writes
require an established main outcome" in `rolling-pack-release`, which already
holds the scenario "Write job rerun after main advanced" and already says why a
rerun must not move the release back. It states the rule once for every cause,
a later run's change and the run's own landed push alike, and says when the
"main advanced" summary is owed: whenever the rerun reaches its push or release
step, which a run that prepared a candidate does only while that candidate's
hand-off is still retained. After that the rerun fails at the workflow's
download step, before any push or release write, with no summary reason. "Main
publication is one normal push" in `nightly-publishing` keeps its own rule, the
check before the push, and points at the owner for reruns. Alternative: state
the retained-versus-expired rule in `nightly-publishing` beside the push.
Rejected: the `rolling-pack-release` scenario would go on promising the summary
unconditionally, and the two specs would disagree. The retention period is a
workflow value and is not stated.

**`pack-verification` gets no delta.** It already owns the fingerprint set, the
stored-report content rule and the regeneration rule. The duplication is removed
from the `pack-cli` side only, which keeps the display obligations.

**An interrupted verification is characterized, not handled.** The `verify`
command catches only its report error, so an interruption propagates out of the
command's entry point and the interpreter supplies the nonzero exit. The test
asserts that propagation and that no report is written. Alternative: catch the
interruption and return nonzero. Rejected: it is an exit-path change, which the
goals exclude.

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

**The regex rule is the reject list.** The normative statement is the enumerated
set of constructs validation rejects today: alphanumeric escapes other than
`\n`, `\r`, `\t`, `\f` and `\v`, `(?` groups other than `(?:`, `(?=` and `(?!`,
and possessive quantifiers. That their meaning differs or may differ between the
validating engine and the Obtainium client is the stated reason for the list,
not a rule of its own. Alternative: state the outcome, "only constructs that
mean the same to both engines are accepted". Rejected: it is false of the
shipped validator, which checks the list and then compiles the pattern, so it
accepts constructs such as `{,3}` or a class opening with `]` whose meaning may
differ. Making the outcome true would need new rejections, which is a behavior
change this change does not make. The delta says outright that passing the list
does not establish equivalence.

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
