## Why

An audit of the main specs against the code found the same defect in four
capabilities: requirements that describe mechanisms instead of outcomes,
requirements that assert behavior the pipeline does not have, and requirements
that embed one app's data. These are not four problems. They are one habit,
and the specs cannot be trusted as the source of truth while any of them
stands.

The worst of them asserts behavior that does not exist. A generation scenario
says an explicitly enabled prerelease resolves "despite a 404 from the stable
latest endpoint", but generation chooses its endpoint from the rule before it
makes any request and looks a release up once against it: when prereleases are
enabled it asks for the releases list and never asks for the stable latest
release, so no 404 is possible and no reader can tell what the system is supposed to do when the
stable endpoint fails. A composition requirement forbids "a separate lookup of
the selected project's release metadata" after building, machinery no module
has ever had, and two of its three scenarios describe a reselection path that
cannot occur. An ingestion scenario has the newest upstream release chosen by
comparing published versions "rather than from a pinned or previously cached
version", describing a version comparison and a cache that do not exist. A
curation requirement embeds one tracker's synthetic id, name, repository URL
and release-title regex in normative text, which this project's own spec rules
forbid.

The same reading also found shipped rules that change a maintainer's decisions
and that no requirement states: which GitLab URLs the native adapter accepts,
what makes two non-GitHub links the same project, how many release assets each
configured pattern must match, which policy selectors are valid, which fields
an overlay record may carry, and which settings a track-only rule may set. A
maintainer editing reviewed configuration has no way to learn these except by
triggering them.

These four capabilities are disjoint from each other and from every other
planned work item, so splitting this into three changes would buy three
separate review and archive rounds and nothing else. One change, one reading of
the code, one reconciliation.

## What Changes

- Retire the composition requirement "Selected build verification does not
  change composition". It prohibits a post-build release metadata lookup that
  composition never performs, and selection runs once over the candidates
  ingestion supplied. Its one live rule, that dual falls back to an ordinary
  candidate when no preferred candidate survives and no pin requires one, is
  carried forward to the requirement that already states the fallback, together
  with its scenario.
- Correct the generation scenario that claims a prerelease resolves despite a
  404 from the stable latest endpoint. State the actual contract: the rule
  decides the endpoint before any request, exactly one release lookup is made
  against that endpoint, a transport retry of it is not a second lookup, and an
  enabled prerelease or release-title rule reads the bounded releases list
  instead of the stable latest release.
- Separate the two bounded-scan failures generation already distinguishes: a
  releases-list response longer than the bound fails, and a response within the
  bound containing no permitted release fails. One requirement described only
  the second, and only the first had a test.
- Restate as outcomes the ingestion rules that named mechanisms: upstream
  assets come from the release the upstream publishes as its latest, with no
  version comparison and no reuse of a previously read release; each configured
  asset pattern must match exactly one asset in that release.
- State the shipped rules that change a maintainer's decisions and that no
  requirement covered: the native GitLab URL boundary, the identity of two
  links that differ only in query, fragment or port, the asset count each
  configured pattern must match, the uniqueness of a normalized project URL
  within the accepted source catalog, the validity of a policy selector's
  source and origin pairing, the fields an overlay record may carry, and the
  consumer settings a track-only rule may set.
- Replace the unenforceable GitLab clause "Package ids for these explicit
  extras SHALL be supplied and backed by manifest evidence" with the maintainer
  obligation it actually is. The same sentence forbids extending package
  discovery to non-GitHub hosts, so no check inside the system can enforce it.
- Reconcile duplicate ids. Ingestion leaves duplicates from an upstream catalog
  for composition to resolve, as one requirement says, but a committed source
  catalog carrying one id twice fails ingestion naming both project URLs, which
  contradicted that requirement for that source.
- Take the mechanism out of the curation requirement that prescribes the test
  suite line by line, down to where a check derives its expected set from and
  what a fixture holds, and out of the scenario that restates the catalog
  check list inline. State what must be true instead of how to check it.
- Take one tracker's id, name, repository URL and release-title regex out of
  normative curation text. Those values belong to reviewed configuration and
  are asserted by a regression check; the requirement keeps the behavior that
  makes the tracker correct.
- Rename the committed-catalog ingestion requirement, whose title still carries
  vocabulary the capability retired.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-composition`: retire the requirement that prohibits a post-build
  release metadata lookup, carrying its live fallback rule and scenario into
  the union and precedence requirement; state that a policy selector names a
  supported source and an origin belonging to that source; state the fields an
  overlay record may carry and the form its `url` must take.
- `source-ingestion`: state upstream asset reading as an outcome with the
  required asset count per configured pattern; state that query and fragment
  identify a non-GitHub project and that an explicit port identifies a project
  on every host, while a GitHub link reduces to owner and repository; state that a committed catalog repeating an id fails ingestion
  while upstream duplicates reach composition; state the native GitLab URL
  boundary, including that its host must be `gitlab.com` without a `www.`
  prefix, and that it is an earlier stage than normalized comparison rather than
  the same rule; restate
  the package-id clause as a maintainer obligation; rename
  the committed-catalog requirement.
- `readme-source-generation`: correct the prerelease resolution scenario, scope
  the consumer settings a track-only rule may carry, separate the over-bound
  response from the bounded response with no permitted release, and state that
  generation rejects an accepted catalog holding one normalized project twice,
  which is where that uniqueness rule is enforced.
- `pack-curation`: restate the curated-decision protections as outcomes rather
  than a description of the test suite, cross-reference each catalog validity
  rule the pipeline enforces to the stage that actually enforces it while owning
  the two no stage checks as suite obligations, and remove one tracker's per-app
  data from normative text.

## Impact

No source behavior changes: every delta states what the code already does, so
`src/` is untouched and rendered packs stay byte-identical. Tests grow, in
`tests/test_sources.py`, `tests/test_urls.py`, `tests/test_composition.py`,
`tests/test_composition_policy.py` and `tests/test_source_generation.py` or
their nearest equivalents, to guard the rules this change states for the first
time.

One dependency reaches outside this change. Removing the tracker's id, name,
repository URL and release-title regex from normative text is safe only while a
regression check asserts the tracker's rendered identity, its notification
settings and its exact rendered key set against reviewed configuration. That
check is on the default branch, among the tracker regression tests.
Implementation confirms it covers all of that, and fails when the configured
values change, before removing the data, so the requirement is never left
without a regression net.

Estimate: this change retires one requirement, "Selected build verification
does not change composition", and adds none. It modifies twelve: three in
`pack-composition`, four in `source-ingestion`, three in
`readme-source-generation` and two in `pack-curation`, and renames one more in
`source-ingestion` through a rename section carrying no other edit. It adds
thirteen scenarios, carries one more unchanged from the retired requirement
into the requirement that inherits its rule, and rewrites five in place,
keeping every existing scenario name so no surviving requirement has to be
removed and re-added. It
adds no implementation lines, because no shipped behavior changes, and roughly
140 to 210 test lines across ten new guards. No new requirement about
retries, ownership, races, diagnostic formats or evidence is introduced: every
rule stated here is a configuration or ingestion rule whose violation already
fails a build visibly, and a rerun of an unchanged input reproduces it exactly.
