## 1. Families keyed by project URL

- [ ] 1.1 In composition policy loading and family formation, name a default family by its normalized project URL, make a family rule cover every candidate at its URL when the URL's rules agree and only candidates with its selector's id when they disagree, stop joining candidates through shared package ids, and delete the joined-explicit-families failure; verify with composition tests for one project from several sources, different repositories sharing an id staying separate, a rule covering rule-less builds at its URL, two rules splitting one repository with a third build left in the URL family, and conflicting rules on one id and URL
- [ ] 1.2 Remove `packageId` from candidate rules and the effective-id concept from candidates, selections and reports, delete the track-only id-equality restriction, and drop `packageId` from the reserved source-record fields; verify with tests that a rule carrying `packageId` fails as an unknown field, a selection reports one package id, and a source record carrying `packageId` is ingested and rendered unchanged
- [ ] 1.3 Accept `app:` names and normalized URLs as category map keys and pin families, rejecting a key not already in normalized form; delete the composition-time pairing check; verify with policy tests for a URL key, a non-normalized key and a pin naming a URL family

## 2. URL denials and overlays

- [ ] 2.1 Parse denylist records as `{url, reason}`, exclude every candidate at the normalized URL, and report exclusions and stale exclusions by URL; verify with tests for differently spelled URLs, an unknown field, a stale denial, and a denial leaving another repository with the same package id selectable
- [ ] 2.2 Parse overlay records as `{url, patch}`, patch every selected entry at the normalized URL, fail on two records with one normalized URL and on a record matching nothing; verify with overlay tests including the duplicate-URL and stale-record cases

## 3. Rendering, repeated package ids and reporting

- [ ] 3.1 Render `allowIdChange: true` on every app, overriding a source or overlay value, and let rendering accept a repeated id; verify with rendering tests for both cases
- [ ] 3.2 Record each package id that more than one selected entry of a variant carries, with families and URLs, without failing; verify with a test where two URL families share an id and one where a family rule resolves it
- [ ] 3.3 Add the repeated-id list to the build report, bump its schema version, key the added and removed comparison on (id, normalized URL), and display the list in `pack report`; verify with report tests for the new field, an old-schema report and an id-and-URL change

## 4. Offline verification and the README catalog

- [ ] 4.1 Label each rendered entry from the family rules as composition applies them, otherwise by its normalized URL, pair single and dual entries by label in one pass, fail on a label repeated within a variant, check denials and overlay targets by URL, require `allowIdChange: true`, and report a repeated package id as a nonfatal finding; verify with offline tests for URL pairing, a split URL, a repeated label, a repeated package id under different labels, a missing `allowIdChange` and an entry at a denied URL
- [ ] 4.2 Build README catalog rows from the same labels; verify with catalog tests for two repositories sharing an id in separate rows and one repository publishing two families

## 5. Configuration migration

- [ ] 5.1 Migrate `config/composition.json` (remove `packageId` everywhere and delete the rules left with nothing else, add `app:melonds` and `app:melonds-nightly` rules, join Minish Cap through the BBoi `tmc-android` rules and a new extras Picori rule, URL category keys and pins), `config/deny.json` (five URL denials) and `config/overlay.json` (records without `id`); verify that `uv run pack build` succeeds with each pack holding the same number of entries and the same project URL per family as the previous `dist/`, ids differing only where a correction was removed, every entry carrying `allowIdChange: true`, empty repeated-id, uncategorized and stale-category lists, and `uv run pack verify` passing
- [ ] 5.2 Update curation and fixture tests that name `package:` families, id denials or corrected ids, and add a curation check that melonDS stable and nightly both ship and that each pack carries exactly one Minish Cap build; verify with `just check-all`
- [ ] 5.3 With the owner's explicit approval obtained first, on the AYN Thor import a rebuilt pack, install an app whose source id differs from its APK's, re-import the pack, and confirm Obtainium holds one working entry for that app; record the dated observation in `docs/curation.md`, and if it fails stop and report rather than restoring corrections

## 6. Documentation

- [ ] 6.1 Update `docs/composition.md`, `docs/curation.md`, `docs/development.md` and any other page describing `package:` families, package denials, `packageId` corrections or id-keyed overlays; verify with a search for `package:`, `packageId` and "package denial" in `docs/` and `just check-links`
