# Reviewed codm source generation

Normal pack builds consume the accepted Obtainium document at
`config/catalogs/codm.json`. Source generation is a separate operation that reads
the codm README, applies reviewed project policy, resolves APK identities, and
writes an isolated candidate under `.build/source-generation/codm/`. It never
changes the committed catalog, metadata, package-ID state, packs, README, or git
history.

## Inputs and policy

The configured source in `config/sources.json` names three inputs:

- the upstream README URL, whose Project catalog tables supply eligible GitHub
  repositories;
- `config/codm-projects.json`, the reviewed per-project policy; and
- `config/catalogs/codm.json`, the accepted complete catalog used by builds.

The accepted catalog is bound by `config/catalogs/codm.source.json` to the exact
README bytes, exact policy-file bytes, source URL, and catalog bytes. Formatting
the README or policy can therefore require a metadata-only proposal. Canonical
policy fingerprints separately allow semantic reuse when policy formatting alone
changes. Acceptance means those files are present on main; an open proposal does
not become an accepted fallback or no-op baseline.

Policy keys use normalized GitHub repository identities. An absent rule means a
stable-release APK project with legacy defaults. A reviewed `apk` rule can set a
name and supported Obtainium discovery settings such as prerelease inclusion,
release-title and APK filename filters, version extraction, and consumer
`fallbackToOlderReleases`. APK package IDs always come from inspected manifests;
policy cannot supply them. Every eligible APK in the selected release must be
readable and agree on its package ID.

A `track-only` rule instead supplies a stable resource ID, rationale, installation
instruction, and optional supported settings. It creates an Obtainium release
tracker without downloading an APK or adding a package-ID record. Failed APK
resolution never converts a project into a tracker, and kind changes require
fresh validation.

Kanto Gear is intentionally track-only. Obtainium reports its releases but cannot
install the Lua mod or detect its installed version. Install or update Kanto
through official [Gen1Recomp](https://github.com/bryanthaboi/gen1recomp) using
its Mod Index or ZIP import. Gen1Recomp remains the Android host in both packs.

## Generate and inspect a candidate

Run from the repository root:

```sh
uv run pack generate-source codm
```

Inspect `.build/source-generation/codm/report.json` and the candidate files named
below. `pack report` remains the build and structural-verification report viewer.

Use `uv run pack generate-source codm --force` to inspect current releases even
when the accepted README and policy bytes are unchanged. Force does not guarantee
a change and does not relax validation.

After successful generation, the candidate directory contains `catalog.json`,
`source.json`, `resolution-state.json`, `report.json`, and `readme-input.bin`.
When unchanged inputs skip generation, it contains only `report.json` and
`readme-input.bin`. Generation fails if the README tables
are malformed or empty, any eligible project is unaccounted for, a new APK or
tracker cannot be resolved, eligible APKs disagree, an ID collides, accepted
state is inconsistent, or a selected release has no eligible APK. Partial
catalogs are never accepted.

An accepted entry may be retained with a warning when a refresh fails and its
effective policy is unchanged. After that warning-bearing proposal is accepted
on main, unchanged README and policy bytes skip generation. A later scheduled
run retries an unaccepted failure because main's accepted hashes did not change.
Refreshing an accepted fallback against newer release data requires a README or
policy-byte change, or `--force`.

Heimdall illustrates the distinction between generator and client behavior. The
generator selects the newest release matching its reviewed title rule and fails
if that release has no eligible readable APK; it never searches an older release.
The generated Obtainium entry sets `fallbackToOlderReleases: true`, allowing the
client to search older matching releases when its selected release lacks an
eligible asset. Showdown and EmuLnk explicitly set that client option to false.

## Proposal workflow

The **Reviewed source catalog** Actions workflow runs daily at 04:17 UTC and can
be dispatched manually with the `force` input. It runs only for
`mjkoo/omnipack` on `main`, uses one non-canceling concurrency group, and performs
one attempt:

```sh
uv run --no-sync python -m scripts.source_publication observe --base "$GITHUB_SHA"
uv run --no-sync pack generate-source codm
uv run --no-sync python -m scripts.source_publication check --base "$GITHUB_SHA"
uv run --no-sync python -m scripts.source_publication publish
```

The forced workflow substitutes `pack generate-source codm --force`. The check
overlays the three candidate source files onto the selected main revision, runs a
normal build and structural verification, and rechecks source and policy bytes.
Only `config/catalogs/codm.json`, `config/catalogs/codm.source.json`, and
`config/package-ids.json` may enter the owned `automation/codm-catalog` branch.
Pack and README differences are diagnostics for review and remain outside that
source commit. Policy is read-only to automation.

The job needs scoped `contents: write` and `pull-requests: write`; checkout does
not persist credentials. Repository rules must allow the owned branch write and
pull-request operation. The workflow neither writes main nor merges its proposal.
It updates the one owned open proposal when safe, rejects foreign or ambiguous
branch state, and creates no duplicate proposal after an uncertain write.
Current-run summaries and the `source-catalog-<run-id>` artifact retain only
redacted run, generation, and pack-diff JSON for 14 days. Source text, APKs, HTTP
bodies, caches, credentials, and unrelated files are excluded.

Nightly pack publication remains independent. It reads only the accepted source
files on main and publishes `dist/single-screen.json`, `dist/dual-screen.json`,
and the generated interior of `README.md`; it cannot stage catalog, policy, or
package-ID state changes.
