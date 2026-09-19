## Context

Four capabilities carry the same kind of defect, found by reading each
requirement against the module that implements it.

`readme-source-generation` states that an explicitly enabled prerelease
resolves "despite a 404 from the stable latest endpoint". Release selection
computes one endpoint from the rule's settings, asks for the bounded releases
list when prereleases or a release-title filter are enabled and for the stable
latest release otherwise, and issues exactly one request. The stable endpoint
is never requested in the prerelease case, so it cannot 404, and the scenario
describes a fallback the generator does not have. The same requirement says an
APK rule may set `fallbackToOlderReleases`, while policy validation forbids
only `apkFilterRegEx`, `versionExtractionRegEx` and `matchGroupToUse` on a
track-only rule and therefore accepts both `fallbackToOlderReleases` and
`includePrereleases` there. Release selection raises two distinct failures, one
for a list longer than the bound and one for a bounded list with no permitted
release, and the requirement describes only the second while the only test
drives the first.

`pack-composition` still carries "Selected build verification does not change
composition", whose vocabulary predates the rewrite of the file around it. It
forbids publication eligibility depending on "a separate lookup of the selected
project's release metadata" after a successful build. No module performs such a
lookup, selection runs once over the candidate set ingestion produced, and two
of its three scenarios describe a reselection that cannot happen. Its third
scenario describes real fallback behavior that the union and precedence
requirement already states in its own words.

`source-ingestion` has a scenario in which the newest upstream release is
chosen because its assets are "named for a version later than any seen before"
and read "rather than from a pinned or previously cached version". The adapter
asks the upstream for its latest release and reads the assets it finds there;
there is no version parsing and no cache. The same adapter requires each
configured asset pattern to match exactly one asset in that release and fails
naming the pattern otherwise, which no requirement states. Elsewhere the
capability promises that package ids for GitLab extras are "backed by manifest
evidence" while the same sentence forbids extending package discovery beyond
GitHub, so nothing in the system can check it. A requirement says duplicate ids
within a variant are resolved during composition rather than dropped during
ingestion, which holds for an upstream catalog but not for the committed
catalog, where a repeated id aborts ingestion naming both project URLs.

`pack-curation` prescribes the test suite: which file a check derives its
expected set from, that it must not use a hand-kept list, what "fixture" means
inside a scenario, and an inline enumeration of every catalog check, repeated
in the requirement and again in a scenario. It also embeds one tracker's
synthetic id, name, repository URL and release-title regex in normative text.
The project's own spec rules say to state required outcomes rather than
mechanisms and to keep per-app data out of normative requirements, so both are
violations of rules this project already agreed to.

Alongside these, the same reading found shipped rules that change what a
maintainer writes in reviewed configuration and that no requirement covers: the
native GitLab adapter rejects a URL with credentials, a port, a query, a
fragment, a path component that is exactly `-`, or more than twenty-one path
components, beyond the three rejections the current scenario names; URL
normalization keeps query, fragment and port for a non-GitHub link while
reducing a GitHub link to owner and repository and discarding its query and
fragment; a policy selector must name one of the supported sources and an
origin belonging to that source; and an overlay record carrying any field other
than `id`, `url` and `patch`, or a `url` that is not a project URL, fails with
the record identified.

## Goals / Non-Goals

**Goals:**

- Every requirement in these four capabilities describes behavior the pipeline
  has, in terms of outcomes rather than the mechanism that produces them.
- Every shipped rule that changes what a maintainer writes in reviewed
  configuration is stated somewhere a maintainer will read.
- Requirements carry no per-app data and no description of the test suite.
- Rules that only one capability can own are owned once.

**Non-Goals:**

- Changing any shipped behavior. This change adds no implementation lines and
  leaves rendered packs byte-identical.
- Specifying defensive plumbing. Numeric guards, record type checks and
  whitespace handling inside parsing are implementation robustness: they change
  no decision a maintainer or an operator makes, and stating them would turn
  the specs into a second copy of the code.
- Moving requirements between capabilities. Every capability keeps its current
  boundary, so nothing here depends on a restructure or blocks one.
- Consolidating duplicated release publication rules, which belongs to the
  capabilities those rules span and not to these four.

## Decisions

### One change rather than three

The defect is one habit, not three findings, and the four capabilities are
disjoint from each other and from every other planned work item. Three changes
would mean three proposals, three review rounds and three archive gates for
work that shares one reading of the code and one set of conventions. The cost
of the single change is a longer review; the cost of splitting is paid three
times in coordination and again in the risk that one of the three is left
undone.

### Retiring the verification requirement, and why its twin survives

A reviewer will ask why `pack-composition` loses a requirement about
verification and publication eligibility while `nightly-publishing` keeps one
that reads similarly. The two are not the same claim.

The nightly requirement states nightly's own eligibility contract: what the
publication workflow may and may not do with a build whose verification failed.
It is backed by the publication scripts, and it governs a decision that is
really made.

The composition requirement instead prohibits machinery composition never had.
There is no post-build release metadata lookup to forbid, so the prohibition
protects nothing, and its scenarios assert that a reselection does not happen in
a pipeline that has no reselection step. Retiring it removes a false statement,
not a protection. The one rule inside it that is true, that dual falls back to
an eligible ordinary candidate when no preferred candidate survives and no pin
requires one, is already stated by the union and precedence requirement, so the
rule and its scenario are carried there rather than lost.

### The pin-first collapse is dropped from this change

Pin-first selection is stated in three places: the canonical requirement on
explicit selections, a sentence in the build-kind requirement, and a clause in
the union and precedence requirement. Collapsing it to one home was considered
and is not done here.

The build-kind sentence is not a pure duplicate. Its trailing clause, that a
dual pin keeps a family's baseline build whether or not it shares a package id
with the family's dual-screen build, is the only normative basis for that
requirement's scenario about a pin keeping a baseline build that shares its
package. Deleting the sentence would orphan that scenario, and moving the
scenario to the canonical requirement would drop it from its current one, which
forces that requirement to be removed and re-added and turns an editorial tidy
into a restructure. A restructure would make `pack-composition` an involved
capability and block this change against it. The tidy is worth less than the
blockage, so the duplication stays and the decision is recorded rather than
left for the next reader to rediscover.

### Only decision-changing behavior becomes spec text

An unspecified behavior earns a requirement when knowing it changes what
someone writes or does. The native GitLab boundary, non-GitHub URL identity,
the asset count per configured pattern, selector source and origin validity,
overlay record fields and track-only consumer settings all decide whether a
maintainer's edit to reviewed configuration is accepted, and all of them
currently announce themselves only as a build failure. They are stated.

Numeric and boolean type guards, publication-date parsing, whitespace handling
around a selector and similar internal defenses are not stated. They make the
implementation robust, they change no decision, and each one added to the specs
would have to be maintained against the code forever.

### The committed catalog's build-time rule moves, its test rules do not

The curation capability's inline catalog check list mixes two different things.
One of them, that a catalog repeating an entry id fails, is a build-time rule
the ingestion adapter enforces on every build, and it contradicts an ingestion
requirement that promises duplicates survive to composition. That rule is
stated in `source-ingestion`, where the contradiction is, and the ingestion
requirement is narrowed to the upstream catalogs it is true of.

The rest of the list, unique normalized project URLs, kind-appropriate ids and
flags, and canonical byte rendering, is asserted by the test suite and not by
any build-time check. Moving it into `source-ingestion` would state a
requirement the code does not implement, exactly the defect this change exists
to remove. It stays in `pack-curation`, restated as the outcome the suite owes:
a candidate catalog the pipeline accepts and that composes, builds and verifies
over the suite's captured records does not fail the suite because of which
projects it contains or how they resolved.

### Delta operations are chosen to keep every scenario name

A modified requirement restates its whole text and may gain scenarios, but
dropping one forces removal and re-addition under a new name. Every rewrite
here therefore keeps its scenario names and edits the WHEN and THEN in place,
including the prerelease resolution scenario, the newest-release scenario, the
duplicate-id scenario and the catalog check scenario. No scenario moves between
requirements. The one requirement whose title carries retired vocabulary is
renamed through a rename section carrying no other edit, which is a normal
change operation rather than a restructure, since the capability boundary does
not move.

### The tracker's per-app data leaves only once its check is in place

Removing the tracker's id, name, repository URL and release-title regex from
normative text is only safe while something else fails when they change. The
values live in reviewed configuration, and a regression check asserts the
rendered tracker's identity, notification settings and exact rendered key set
against it. That check is written but sits on a separate test branch that has
not merged. Implementation confirms it is present in the working branch before
the data is removed, so there is no window in which neither the requirement nor
a check protects the tracker.

## Risks / Trade-offs

- The change is large for a review round: four capabilities, twelve requirement
  operations and roughly a dozen scenarios touched. The mitigation is that no
  delta changes behavior, so each one can be checked against a named module
  rather than argued about.
- Stating a previously unstated rule freezes it. The native GitLab boundary and
  the asset count per pattern become promises, and loosening them later needs a
  change. That is the point of stating them, and each is already load-bearing
  for a maintainer.
- Retiring a requirement loses its text from the living specs. The rule worth
  keeping is carried forward explicitly, and the removal records where it went.
- The tracker data removal depends on a check that has not landed on the
  default branch. If that branch is abandoned, the removal has to be held back
  or the check rewritten in this change.

## Migration Plan

No configuration, workflow or data migration. No published artifact changes,
because no shipped behavior changes.

Implementation adds each new guard as a failing test first, confirms it fails
for the stated reason against the current code, and confirms the code already
satisfies it without modification. Any guard that does not pass against
unmodified code means the delta misread the code, and the delta is corrected
rather than the code.

Before the tracker's per-app data is removed, implementation confirms the
regression check over the rendered tracker is present in the working branch and
fails when the reviewed configuration's tracker values change, rebasing onto
the branch that carries that check if it has not merged.

Rollback reverts the deltas and the tests together; there is nothing else to
undo.
