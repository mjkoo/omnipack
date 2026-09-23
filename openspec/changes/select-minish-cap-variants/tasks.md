## 1. Establish the supported transition

- [x] 1.1 Refresh the GitHub/Reddit findings and compare current selected Sam/Picori release APKs; deliver validation.md with primary URLs, hashes, package/version fields, SDK/ABI, permissions and certificate/rotation observations, distinguishing source claims from inspected bytes.
- [ ] 1.2 Establish the save-preservation and installation route from upstream documentation/source and reproducible non-device checks; record whether an ordinary update or fresh installation is supported. While the save-preservation route remains unresolved, the requirement forbids moving the selection: retain the previous selection, record the unresolved migration in `docs/curation.md` under "Unresolved identity and selection findings" with the family, dated observations and unresolved save-preservation route, leave both exports unchanged and report the blocker before configuration work. Keep raw APK and route observations in this change's `validation.md`; the durable entry must stand on its own and is required even if task 2.3 is never reached.

## 2. Curated variant selection

- [ ] 2.1 Add the inspected Picori baseline extra and necessary family/selection/settings configuration while retaining Sam for dual; both BBoi `com.samyost1.tmcandroid` identity rules stay, and any explicit family rule goes on the extra and on both Sam rules. Outcome tests assert, per pack, exactly one selected entry whose normalized project URL is either Minish Cap repository, with single selecting `github.com/999sian/tmc` and dual selecting `github.com/samyost1/tmc-android`, and that the single-screen selection's considered list contains the `bboi-standard-asset` build.
- [ ] 2.2 Preserve or deliberately replace affected overlays and outcome fixtures; refresh-simulation tests prove maintained settings and the per-variant choice survive upstream changes, including optional lower-precedence Quiver coverage when available.
- [ ] 2.3 Write consumer migration/setup guidance and rebuild packs/README; compare outputs to confirm only intended selection changes and clearly state signing, version-ordering, save and device-validation limits.

## 3. Implementation review and completion audit

- [ ] 3.1 Complete required per-group evidencing reviews and the parallel implementation review wave; record findings and resolutions with no unresolved blocking issue.
- [ ] 3.2 Run repository-required checks, curation/composition regressions, pack build and pack verify; record results and confirm the supported transition evidence precedes the source switch.
- [ ] 3.3 Audit checkbox completion against configuration, tests and evidence; leave the change active and report the branch without invoking the separate OpenSpec verification or archive workflows.
