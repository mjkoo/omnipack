## 1. Establish the supported transition

- [x] 1.1 Refresh the GitHub/Reddit findings and compare current selected Sam/Picori release APKs; deliver validation.md with primary URLs, hashes, package/version fields, SDK/ABI, permissions and certificate/rotation observations, distinguishing source claims from inspected bytes.
- [x] 1.2 Record the owner's explicit no-users exception to save migration for this switch; document incompatible signing, the unresolved preservation route and fresh-install-only scope in `docs/curation.md` under "Unresolved identity and selection findings", with raw observations in `validation.md`. Do not claim an ordinary update or supported save migration; proceed with configuration under the exception without device access.

## 2. Curated variant selection

- [x] 2.1 Add the inspected Picori baseline extra and necessary family/selection/settings configuration while retaining Sam for dual; both BBoi `com.samyost1.tmcandroid` identity rules stay, and any explicit family rule goes on the extra and on both Sam rules. Outcome tests assert, per pack, exactly one selected entry whose normalized project URL is either Minish Cap repository, with single selecting `github.com/999sian/tmc` and dual selecting `github.com/samyost1/tmc-android`, and that the single-screen selection's considered list contains the `bboi-standard-asset` build.
- [x] 2.2 Preserve or deliberately replace affected overlays and outcome fixtures; refresh-simulation tests prove maintained settings and the per-variant choice survive upstream changes, including optional lower-precedence Quiver coverage when available.
- [x] 2.3 Write consumer migration/setup guidance and rebuild packs/README; compare outputs to confirm only intended selection changes and clearly state signing, version-ordering, save and device-validation limits.

## 3. Implementation review and completion audit

- [x] 3.1 Complete required per-group evidencing reviews and the parallel implementation review wave; record findings and resolutions with no unresolved blocking issue.
- [x] 3.2 Run repository-required checks, curation/composition regressions, pack build and pack verify; record results and confirm the APK evidence and explicit no-users exception precede the source switch.
- [x] 3.3 Audit checkbox completion against configuration, tests and evidence; leave the change active and report the branch without invoking the separate OpenSpec verification or archive workflows.
