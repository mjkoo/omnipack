# Pack verification

`pack verify` checks existing pack files, local configuration and the generated
README catalog without network access. It validates structure and consistency.
Obtainium evaluates release selection, regular expressions and effective versions
on the device; the pack builder no longer maintains an independent implementation
of those behaviors.

## Commands and evidence

Run commands from the repository root:

| Command | Work performed |
| --- | --- |
| `uv run pack verify` or `just verify` | Validate the existing serialized pair, catalog and local configuration offline |
| `uv run pack report` | Display available build and verification evidence without fetching or writing files |
| `uv run pack build` | Ingest and compose sources, validate rendered bytes, then publish both packs and the catalog as a recoverable unit |

The retired `--live` and `--probe-assets` arguments fail before verification starts
and leave existing evidence untouched. Replace those invocations with `pack verify`.
There is no generic whole-pack replacement. The separate `pack generate-source
codm` operation resolves only the explicitly configured codm source candidate;
it does not extend structural verification or change committed files.

Standalone verification writes schema 2 evidence to `.build/verify.json`, separately
from the build report. It first writes an incomplete running record and atomically
replaces it on completion, including failure. Reports contain offline mode,
verifier identity, observation times, completion, status, contextual errors and
SHA-256 fingerprints of both distribution files, the denylist, both overlays,
composition policy, pack settings and README. Missing and unreadable inputs are
explicit. HTTP configuration and environment credentials are not consulted or
fingerprinted.

Independent errors are collected across both variants. Input changes during a
run prevent success. An interrupted run leaves incomplete evidence. Verification
exits zero only for a complete run without errors; report persistence failure
also causes a nonzero exit and a stderr diagnostic.

Verification never rebuilds or changes the packs, README, configuration,
package-ID state or `.build/report.json`. Building performs source ingestion but
does not discover package IDs; codm discovery belongs to source generation.

`pack report` labels supported evidence stale when any input fingerprint or the
verifier identity differs. Older verification schemas require regeneration with
`pack verify` and cannot authorize publication. Existing build reports remain
readable. One available report is enough; missing both, corrupt reports and
unsupported schemas fail display. Displaying a recorded failed operation exits
successfully.

## Structural checks and limits

The validator checks JSON types, required app fields, source URL shapes,
source-specific default settings and known setting types, package uniqueness,
family composition constraints, configured pack settings and category colours.
Unknown settings are acceptable when structurally valid. Regex strings are not
compiled or evaluated, so even a malformed pattern can pass structural checks.

Composition checks cover rendered families, projected pins, eligibility,
exclusions, package uniqueness, family coverage and overlay targets. Rendered
output omits losing candidates, so verification cannot reconstruct provenance,
candidate presence, preference or source ranking, or prove that a patch produced
the rendered values. Fixture-driven composition and rendering tests protect
maintained IDs, URLs, variant membership and override values across refreshes.

Catalog verification compares the generated marker interior against the captured
packs and policy. Missing, unreadable, malformed or stale catalogs fail. Handwritten
content is excluded from catalog comparison but included in the README fingerprint.
A handwritten edit permits fresh verification while making old evidence stale.
Verification never repairs the catalog.

Success does not establish upstream health, release or download availability,
effective versions, APK identity, signatures, installation, architecture support,
re-import behavior or absence of spurious notifications. Investigate source
selection and version behavior in Obtainium. See [version detection](version-detection.md)
and [maintained curation](curation.md) for intended policies and their limitations.

## Publication and historical evidence

See [structural validation results](structural-verification-validation.md) for
the retained test suite, publication boundaries and byte-preservation checks.

Nightly publication requires fresh structural evidence for each built candidate,
validated in the selected revision's runtime after one build. Nightly does not
run pre-build verification or repeat development CI checks. Exact bytes, staging, publishable-path restrictions and the README
handwritten-content boundary remain enforced. Structural failure blocks publication
without selecting a different project. App release metadata becoming unavailable
after a successful build does not add a verification gate or cause reselection.

The publisher separately checks the rolling release seed's existence and ownership
after confirmed main publication or a verified no-op. A seed failure blocks only
release synchronization. Verification itself never queries that release, including
when the tracker is present. See [publishing](publishing.md) for explicit bootstrap,
release synchronization and recovery.

Dated observations in [verification validation](verification-validation.md),
[curation validation](curation-validation.md), and retained fixture provenance
describe the checks performed at those times. Historical resolver fixtures and
archived changes remain evidence of the retired implementation, without implying
current compatibility coverage or upstream health.

The RJNY verifier was evaluated as an implementation reference at revision
[`5bb57f833652c389c3b063d3b4af9b42ee11602a`](https://github.com/RJNY/Obtainium-Emulation-Pack/tree/5bb57f833652c389c3b063d3b4af9b42ee11602a),
particularly `scripts/test-apps.py`, under the Unlicense. No RJNY helper was copied
or adapted into the retired compatibility classifier. Its independent upstream
identity and historical attribution remain unchanged.
