# Specification maintenance validation

## Package-format compatibility

On September 10, 2026, verification documentation was reconciled with the
existing resolver behavior. The production implementation was preserved.
The focused resolver, compatibility, package-ID and probe suite passed all
325 tests. The full suite passed all 999 tests with 92% package coverage. Ruff lint and formatting, ty, ordinary offline pack verification,
and strict OpenSpec change validation passed.

| Contract | Evidence |
| --- | --- |
| GitHub package formats use asset names independently of generic ZIP selection | `test_package_containers_use_asset_names_without_enabling_generic_zips` |
| GitHub container regex and inversion inspect asset names | `test_package_container_filter_and_inversion_use_asset_name` |
| GitLab recognition uses name or URL path; filtering uses the name | `test_package_containers_qualify_by_name_or_url_but_filter_by_name` |
| GitLab description containers use numeric project upload routes and filename filtering | `test_description_package_containers_use_numeric_project_and_filename_filter` |
| HTML default filtering recognizes package formats | `test_default_html_filter_recognizes_package_containers` |
| HTML custom filtering can admit an extensionless URL | `test_custom_html_filter_replaces_default_extension_gate` |
| HTML text filtering decodes and parses the URL path before checking its suffix | `test_default_html_text_filter_checks_decoded_url_path` |
| Generated package-ID discovery excludes XAPK containers | `test_all_eligible_apk_extensions_resolve_and_non_apk_is_ignored` |

The first seven tests are in the corresponding files under
`tests/test_resolution_*.py`; the last is in `tests/test_package_id.py`.
Existing ZIP-selection and live-probe tests continue to cover the generic ZIP
setting and bounded outer-response guarantee. The new regressions passed against
unchanged production code; no production failure was introduced to manufacture
a red/green cycle for this documentation reconciliation.

A Git comparison against `5c3911e` confirmed unchanged `src/`, `scripts/`,
`config/`, `dist/` and `README.md`. Test fixtures and dependencies were unchanged.
These checks establish local specification alignment and regression coverage.
They do not establish binary identity, extraction, installation, notification,
or device behavior. Operational and on-device acceptance remain deferred until
the branch has settled, with any findings handled in follow-up work.

## GitLab specification ownership

The pre-archive comparison on September 10, 2026 verified that both detailed
GitLab requirements move verbatim into their pipeline capabilities:

| Receiving specification | Requirement | Preserved scenarios |
| --- | --- | --- |
| [Source ingestion](../openspec/specs/source-ingestion/spec.md) | Public GitLab entries retain native source identity | 1 |
| [Pack verification](../openspec/specs/pack-verification/spec.md) | GitLab release resolution includes uploaded description APKs | 6 |

The modified source-type summary retains its five existing scenarios verbatim;
the modified live-compatibility summary retains its three. Every detailed
statement in both moved requirements is unchanged. Repeated summary clauses
have the following surviving owners:

| Summary clause | Surviving obligation |
| --- | --- |
| Public HTTPS gitlab.com project URL, namespace/project, subgroup depth and case preservation | Native identity requirement; the source-type summary retains the invalid-URL rejection scenario |
| GitLab settings defaults, explicit-setting precedence and avoiding HTML defaults | Native identity requirement and source-type summary |
| No expansion of generated GitHub package-ID discovery | Native identity requirement |
| Explicit installable public projects, tag versions, APK filtering, extraction and older-release fallback | Detailed GitLab release requirement; native identity requirement supplies the gitlab.com URL boundary |
| Named assets, description uploads and at most 100 releases in API order | Detailed GitLab release requirement |
| Reject unsupported active options before HTTP and classify inactive defaults | Detailed GitLab release requirement |
| Token-free public requests, exact-host credentials, bounded requests, per-variant evidence and optional probes | Detailed GitLab release requirement and shared verification requirements |
| Preserve existing GitHub credential and HTML compatibility checks | Live-compatibility summary |

Strict change validation passed. An in-memory merge check produced nine
capabilities and 81 requirements, compared with ten capabilities and the same
81 requirements before consolidation. A search of living specs, `docs/` and
`README.md` found no operational references to the retiring capability beyond
its own title. Historical archives remain unchanged.

A Git comparison against `e0b4abd` confirmed unchanged runtime, tests, scripts,
configuration, generated exports, README, dependencies and workflows. The
999-test baseline above therefore remains applicable; no additional behavior
or tests were introduced. These are pre-archive preservation checks. Final
acceptance of the relocation requires verifying the receiving main specs,
retiring the empty capability with explicit metadata, and strict validation of
the resulting nine-capability inventory. Operational and device acceptance
remain deferred.

Final synchronization on September 10, 2026 verified every delta against its
receiving main spec. Both moved blocks and all retained summary scenarios match
the reviewed text. The empty provider capability and its Purpose were retired
using the CLI-prescribed `retire_capabilities: true` marker after its safety
check refused retirement without that marker. All nine main capabilities passed
strict validation, retaining 81 requirements. Both maintenance changes are
archived; operational and device acceptance remain deferred.
