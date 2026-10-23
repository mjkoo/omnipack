# Tasks

## 1. Overlay keys that change nothing

- [ ] 1.1 Add a pure function beside `apply_overlay` in `src/omnipack/overlay.py` that, given the selected entries of every variant and the parsed records, returns each record's dotted leaf keys that change no targeted entry, comparing against entries hydrated with the rendering defaults for their source type. Verify with synthetic tests in `tests/test_composition.py` for each pack-composition scenario on keys: a value the entry already ships, one live and one dead key, a key that changes only the dual entry (not recorded), a rendering default the entry does not carry, and a null on an absent key
- [ ] 1.2 Call it in `compose` before overlays apply and record `redundant_overlay_keys` on `CompositionReport`, sorted by URL, left empty when overlay validation fails. Verify with a composition test that the published entries are unchanged and the record is present, and one that an invalid overlay leaves it empty

## 2. Extras a catalog lists

- [ ] 2.1 In `compose`, for each selected entry won by extras, find the formed candidates of other sources at the same normalized URL eligible for that variant, and record `extras_listed_by_catalog` with the URL, package id and, per source, the differing top-level and `additionalSettings` fields between the extra's entry after overlay and the candidate's import data with the same record applied, both hydrated, excluding `categories`, merged per URL across variants. Verify with tests for the pack-composition scenarios: an extra over a Quiver candidate at the same URL with a differing name and APK filter, an extra over a catalog candidate at another URL in the same family (not recorded), a denied catalog candidate at the same URL (not recorded), and a candidate identical after overlay (recorded with no differing fields)

## 3. Build report and display

- [ ] 3.1 Serialize both records as `redundantOverlayKeys` and `extrasListedByCatalog` in `src/omnipack/report.py` and validate them in `src/omnipack/report_model.py`, raising `BUILD_SCHEMA_VERSION`. Verify with `tests/test_report_model.py` round-trip and malformed-field cases and a test that the previous schema version is directed to `pack build`
- [ ] 3.2 Display both in `pack report` in full, and verify with `tests/test_report.py` cases for the pack-cli scenarios: overrides as the only diagnostics, alongside other diagnostics, and absent from a report with no diagnostics
- [ ] 3.3 Document both diagnostics and how to retire an override (delete a dead key or record; move an extra's differing fields into an overlay record and delete the extra) in the "Denials and patches" and "Build report" sections of `docs/composition.md`, and verify with `just check-links`

## 4. Alerts

- [ ] 4.1 Add the `build/redundant-patch/` and `build/listed-extra/` key kinds to `_build_warnings` in `scripts/alerts.py` with the titles and details the design gives. Verify with `tests/test_alerts.py` cases for the maintenance-alerts scenario (two findings, one per item, naming the keys and the listing source with its differing fields, verdict unchanged), a URL needing percent-encoding, and a muted redundant-patch issue cleared by a successful build that no longer reports it
- [ ] 4.2 Add both keys to the key table and a short section on reviewing and muting them, with the expected first-run issues, in `docs/alerts.md`, and verify with `just check-links`

## 5. Integration

- [ ] 5.1 Run `just check-all` and verify that it passes
- [ ] 5.2 Run `uv run pack build` and `uv run pack report` on the live inputs and verify the report lists the redundant overlay keys and the extras Quiver lists that the proposal counted, adjusting the proposal's counts only if upstream changed
