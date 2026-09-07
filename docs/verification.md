# Pack verification

Pack verification uses Obtainium v1.6.14 as its compatibility baseline. The
behavioral references are the source files at that immutable tag:

- [GitHub source](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/app_sources/github.dart)
- [HTML source](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/app_sources/html.dart)
- [shared version handling](https://github.com/ImranR98/Obtainium/blob/v1.6.14/lib/providers/source_provider.dart)

The RJNY verifier was evaluated as an implementation reference at revision
[`5bb57f833652c389c3b063d3b4af9b42ee11602a`](https://github.com/RJNY/Obtainium-Emulation-Pack/tree/5bb57f833652c389c3b063d3b4af9b42ee11602a),
particularly `scripts/test-apps.py`. That repository dedicates its code to the
public domain under the Unlicense. No RJNY helper has been copied or adapted in
the compatibility classifier. Any future adaptation must retain this revision,
source path, and licence attribution.

## Commands and evidence

Run commands from the repository root:

| Command | Work performed |
| --- | --- |
| `uv run pack verify` or `just verify` | Validate both existing serialized packs and local composition settings without network access |
| `uv run pack verify --live` | Run offline validation, then resolve sources and probe selected downloads |
| `uv run pack report` | Display available build and standalone verification evidence without fetching or writing files |
| `uv run pack build` | Ingest and compose sources, validate newly rendered bytes offline, then publish the pair |

Standalone verification writes `.build/verify.json` on success or failure. An
initial incomplete record replaces previous evidence before live work starts.
The report records mode, observation times, verifier identity, baseline, findings,
and SHA-256 fingerprints of the exact distribution files, denylist, both overlays,
pack settings, and HTTP configuration. Environment credential values are excluded.
If inputs change during a run, the run fails instead of claiming to verify the
new files. Missing and unreadable inputs are reported explicitly.

Verification does not rebuild or update distribution files, overlays, package-id
caches, or `.build/report.json`. Build diagnostics remain separate and include
the offline gate's verdict. A rejected build preserves both previous output files.

`pack report` labels verification stale when local fingerprints or verifier
identity differ. It also shows incomplete attempts, mode, and observation time.
Current local fingerprints do not mean an upstream source is still healthy.
One available report is enough; missing both, corrupt reports, and unsupported
schemas fail display. Displaying a recorded failed operation is itself successful.

Verification exits zero only for a complete run without errors. Warnings alone
are successful. Offline errors prevent all live requests; after offline success,
independent live failures are collected across both variants. Report write errors
also fail the command and produce a stderr diagnostic.

## Compatibility boundary

Live verification interprets only behavior needed by the committed packs. Each
setting is classified before resolution. An unknown key is an error even if its
value is false or empty, because a value cannot be assumed inactive without
knowing its semantics.

| Settings | Classification | Live behavior |
| --- | --- | --- |
| `trackOnly`, `versionExtractionRegEx`, `matchGroupToUse`, `versionDetection`, `releaseDateAsVersion`, `apkFilterRegEx`, `invertAPKFilter` | Implemented | Applied during version and candidate selection |
| GitHub release eligibility, title and notes filters, older-release fallback, `date` or `none` sorting, asset-date selection, and release-title versions | Implemented | Applied to the first 100 release records |
| HTML intermediate links, link and text filters, outside-anchor matching, sorting controls, whole-page extraction, and non-secret request headers | Implemented | Applied to each configured page in order |
| App name, author, description, notification/background controls, Shizuku presentation, refresh behavior, and OS version-code preference | Harmless for source resolution | Retained but does not alter the device-independent check |
| `autoApkFilterByArch` and `preferredApkIndex` | Device-specific | Validated but not used to claim device compatibility |
| `includeZips`, ZIP filters, `verifyLatestTag`, GitHub credentials or request proxies, insecure TLS, and non-`date`/non-`none` GitHub sorting | Inactive unsupported or live error | Default false or empty values are accepted; active values fail by setting name |
| HTML pseudo-versioning | Inactive unsupported or live error | Ignored when explicit extraction supplies the version; otherwise active pseudo-versioning fails |
| Authorization or Cookie request headers and device-dependent intermediate filtering | Live error | Rejected before a request is made |
| Any unknown additional setting | Live error | Requires an intentional compatibility decision |

The check establishes source resolution and bounded HTTP reachability. It does
not establish APK identity, signature, installation success, architecture
coverage, or behavior on a particular Android device.

GitHub selection is limited to the first 100 releases, so failure does not rule
out a usable release beyond that window. Drafts and excluded prereleases do not
consume the first eligible release; title, notes, and APK mismatches do when
older-release fallback is disabled. Track-only sources can use filtered tags
fallback when no release qualifies. A metadata request failure never triggers
that fallback.

HTML follows up to ten nonempty intermediate filters, selecting the last link
after each configured filtering and sorting step. Excess depth fails. A selected
HTML download cannot be rescued by probing an older link. Track-only whole-page
version extraction can succeed without a final download, but still requires every
active intermediate selection; URL-based extraction always requires a selected URL.

Version extraction uses the last regex match, default group 0, and the baseline's
numeric or `$N` group substitution. Invalid patterns, invalid groups, no match,
and empty output fail. Python-only constructs, inline flags, named groups,
atomic/conditional groups, possessive quantifiers, and unsupported Unicode
property syntax are rejected explicitly. A configured date override runs after
extraction and requires a usable date, represented in epoch microseconds.

Each download probe sends a GET Range request and reads at most 1024 bytes,
closing the response even if the server ignores Range. Nonempty 200 or 206
responses establish reachability. GitHub candidates are tried in metadata order
until one succeeds; failed candidates become warnings when another succeeds.
Probe failure does not select an older release. Track-only entries need a version
and do not require a probe.

Requests use a 30-second timeout, at most two transient retries, at most ten
redirects, and a 10 MiB metadata limit. Credentials come from exact-host environment
mappings in `config/http.json` and are rebuilt at redirects. Non-secret configured
headers, including User-Agent, are honored; embedded URL credentials and pack
Authorization/Cookie headers fail. Diagnostic URLs redact credentials and query
values. Identical metadata and resolution inputs may share work within one run;
different exact HTML URLs, including trailing-slash differences, stay distinct.
No prior run's success or package-id cache can turn a failed source into a pass.

Effective GitHub versions receive the non-blocking
[numeric-shape lint](version-detection.md#lint). A title or extraction regex alone
does not suppress a warning. The lint does not compare with Android versionName.

Ordinary CI runs fixtures and offline verification of committed distribution
files. It does not rebuild from upstreams or run live checks. A full manual live
observation and any blockers for future nightly publishing are recorded in
`docs/verification-validation.md`.

## Fixture evidence

The fixture manifest at `tests/fixtures/verification/manifest.json` maps every
committed HTML entry and every distinct GitHub behavior to response evidence.
All seven HTML fixtures and the configured RJNY track-only GitHub fixture are
trimmed live captures dated in their provenance. Synthetic GitHub records cover
cases that need controlled alternatives. They are labeled as synthetic, cite the
pinned behavioral source instead of a purported capture URL, and include the
complete selection settings needed to reproduce each expectation. Cases make
incorrect sorting, traversal, asset filtering, or regex group handling produce
a different result. GitHub evidence covers prereleases, title and date versions,
concatenated extraction groups, and track-only release and tags paths.

Fixtures contain only the response fragments needed to reproduce selection.
They are deterministic compatibility evidence, not cached claims that the live
source remains reachable.
