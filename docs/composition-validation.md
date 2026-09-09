# Composition migration validation

Validation was performed on 2026-09-09 against the configured upstream sources.
The authenticated build completed successfully and rendered 88 single-screen apps
and 107 dual-screen apps. The outputs have these SHA-256 fingerprints:

- `dist/single-screen.json`: `f4e453383742cd71101da1a2cbb5ad233bec215b14f0796c16bc9d4505e407bc`
- `dist/dual-screen.json`: `5a3b8d455255f5ed8006b59541e0a5246289643b789cf8c5a8568faaa57f51fc`
- `config/composition.json`: `c2959aa0c2dcab5e14727f698b485dbaed8839acc33478469470999f975050a8`

## Complete output comparison

The current configured-source build produced no unrelated project or package
drift from the retained 88-entry single and 111-entry dual baseline. Every
identity transition was policy-driven:

| Target | Family | Previous rendered entry | Current rendered entry | Explanation |
| --- | --- | --- | --- | --- |
| Single | `app:ctr` | `com.simon358.ctrnative`, `Simon358/ctr-native-android` | `com.ctrnative`, same project | The primary APK manifest declares `com.ctrnative`; the project remains the standard CTR build. |
| Dual | `app:ctr` | Simon standard and `com.ctrnative`, `igawa6/ctr-native-android` | igawa6 only | The configured dual catalog identifies igawa6 as CTR-DS with dual-screen support, so the preferred dual candidate replaces the standard candidate in this family. |
| Dual | `app:openmw` | Standard `com.xyzz.openmw` and dual `com.joshdaniels.openmwds` | Dual candidate only | The standard and dual builds are explicit alternatives in one family. |
| Dual | `app:super-metroid` | Standard `com.raekwon1603.supermetroid` and dual `com.raekwon1603.supermetroidds` | Dual candidate only | The standard and dual assets are explicit alternatives in one family. |
| Dual | `app:dusklight` | Standard `com.twilitrealm.dusklight` and dual `com.igawa6.dusklight` | Dual candidate only | The standard and dual builds are explicit alternatives in one family. |

All four families were retained in both targets. No family was added or removed,
and no previous entry lacked a historical family mapping. No exclusion matched or
was stale. Four non-GitHub rows in the dual catalog were skipped with the existing
`not a GitHub repository` reason. Cinderbox remains in both outputs. Ludashi
retains `com.winlator.ludashi`, the `bionic-vanilla` APK filter, disabled version
detection, and its existing release-selection policy.

## Automated validation

- Authenticated `uv run pack build`: success against every configured source.
  It published both rendered files only after source acquisition, strict
  composition, and build-bound offline verification completed.
- `UV_CACHE_DIR=/private/tmp/omnipack-uv-cache uv run pytest
  tests/test_composition.py tests/test_composition_policy.py
  tests/test_composition_baseline.py tests/test_sources.py
  tests/test_curation.py tests/test_curation_evidence.py tests/test_offline.py
  tests/test_verify.py tests/test_build.py tests/test_cli.py -q`: `219 passed in
  1.98s`.
- `UV_CACHE_DIR=/private/tmp/omnipack-uv-cache just check-all`: success. The
  full suite passed `727` tests in `20.94s` with `92%` coverage. Lock,
  formatting, lint, type, dependency audit, Python package build, offline pack
  verification, actionlint, zizmor, Nix formatting, and native flake checks all
  passed. The dependency audit found no known vulnerabilities or adverse
  project statuses in 10 packages.
- `UV_CACHE_DIR=/private/tmp/omnipack-uv-cache uv run pack verify`: success in
  0.009 seconds with verifier `0.4.0`, no errors, warnings, or entry findings.
- Authenticated `uv run pack verify --live`: success from
  `2026-09-09T17:20:13.579960+00:00` through
  `2026-09-09T17:24:04.853989+00:00` (231.274 seconds). It checked 195 rendered
  entries with verifier `0.4.0` and Obtainium `1.6.14`, with no errors or
  warnings.

Both offline and live verification recorded the same eight current input
fingerprints. In addition to the output and composition fingerprints above:

- `config/deny.json` and `config/overlay.dual.json`:
  `37517e5f3dc66819f61f5a7bb8ace1921282415f10551d2defa5c3eb0985b570`
- `config/overlay.json`:
  `925aed91485c750529efb3e4263e8033a9402a7ec5d6eda3c0b4dccd7c0044ae`
- `config/settings.json`:
  `ca3d163bab055381827226140568f3bef7eaac187cebd76878e0b63e9e442356`
- `config/http.json`:
  `c82f5ae80567692d2ccefcbef9ac11f995d379f20187dda04e583b8120e80929`

## Device acceptance

`adb devices -l` found no connected Android device on 2026-09-09. Import,
re-import, installation, signature compatibility, and app-data continuity remain
outstanding. Automated metadata validation does not establish any of them.

When a device is available:

1. Back up app data and record the installed package, version, and signing
   certificate for each affected app.
2. Import `dist/single-screen.json` or `dist/dual-screen.json` into Obtainium as
   appropriate and confirm the expected family winner appears once.
3. Re-import the same file and confirm Obtainium updates the existing entry
   without creating an unintended duplicate.
4. For the single-screen CTR identity change, treat `com.ctrnative` as a manual
   migration from `com.simon358.ctrnative`: back up data, install or update the
   corrected entry, and confirm whether Android accepts the signature and whether
   data can be restored. Do not remove the old package until those checks pass.
5. For each dual replacement, confirm the preferred dual package installs and
   launches. Preserve the old standard package and its data until the replacement
   has passed functional checks.
6. Record actual import, installation, launch, signature, and data observations
   before declaring device acceptance complete.
