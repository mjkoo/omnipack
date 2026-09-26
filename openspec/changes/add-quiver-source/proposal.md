## Why

Quiver discovers Android game ports missing from the current upstream catalogs,
but its cross-platform list lacks the package identities Obtainium needs.
A reviewed generated source lets omnipack follow those additions without
adding live APK resolution to ordinary pack builds.

## What Changes

- Add Quiver JSON discovery, fresh GitHub release/APK resolution and a committed
  Obtainium catalog, with initial reputation and APK vetting.
- Default new projects to stable APK discovery without a permanent allowlist;
  report desktop-only projects and retain reviewed exception and skip policy.
  Pruning unwanted apps uses the existing package deny list.
- Admit Quiver baseline entries in both packs at lower source precedence,
  preserving existing fork choices and dual-screen preference; all candidates
  reach ordinary family composition, with owner package denials pruning apps.
- Add `pack generate-source quiver` and extend the source proposal automation
  with independent Quiver paths, branch and review diagnostics.
- Retire the codm-only assumption in shared generation/publication plumbing,
  while preserving codm's README and dual-only behavior. No existing source is
  retired and no Minish Cap switch occurs in this change.

## Capabilities

### New Capabilities

- `quiver-source-generation`: discovery, selection, manifest-backed identities,
  skips, retention and complete deterministic candidate catalogs.

### Modified Capabilities

- `source-ingestion`: committed Quiver catalog and baseline provenance, retaining every candidate for ordinary composition.
- `pack-composition`: explicit Quiver source precedence.
- `pack-cli`: Quiver generation command and its output boundary.
- `pack-curation`: generated Quiver catalog validity and configuration-driven
  outcome checks without a frozen project roster.
- `readme-source-generation`: source proposal workflow, publication checks and
  diagnostics apply per supported source, each with its own branch, PR,
  serialization group and catalog path; codm keeps its existing branch.
- `readme-catalog`: README credits add the Quiver community app catalog.

## Impact

Touches source adapters, CLI, generation helpers, composition source validation,
configuration, verification fixtures, source proposal script/workflow, docs and
both exports. No new runtime dependency is expected. The change generalizes the existing
source proposal workflow requirements per source rather than adding new ones.

Estimate: 4 new generation requirements, 1 ingestion requirement, 1 CLI
requirement, 6 modified requirements, about 30 added scenarios, 700-1100
implementation lines and 800-1300 test lines. These are estimates, not targets.

No new retry protocol, race fencing or diagnostic serialization contract is
needed: visible failures and reruns use existing behavior, and every catalog
change, including removals, reaches main through a reviewed PR. Generation
reports distinguish skips from unresolved projects so review does not mistake
lack of Android support for an unavailable source. Existing
credential scoping is reused rather than specified again.
