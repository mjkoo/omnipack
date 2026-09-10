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
