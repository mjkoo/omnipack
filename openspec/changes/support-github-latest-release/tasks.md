## 1. Latest metadata and release priority

- [x] 1.1 Add failing resolver fixtures for latest lookup, exact/name identity, list-record reuse, absent latest supplementation, both supported sort modes, and disabled/absent settings; verify the new cases fail for the current unsupported behavior.
- [x] 1.2 Implement latest acquisition, response validation and prioritization in the existing GitHub resolver, then classify `verifyLatestTag` as implemented; verify the new fixtures pass, including the 100-plus-one inspection count and no extra requests when disabled.
- [x] 1.3 Cover promoted-record draft/prerelease eligibility, title/notes/APK mismatches with fallback on and off, and title/regex/date version processing; verify existing selection tests and these regression cases pass.

## 2. Failure, fallback and shared evidence

- [ ] 2.1 Add tests and endpoint-specific diagnostics for latest HTTP errors including 404, transport failure, invalid JSON, non-object bodies and invalid identities; verify failure prevents the corresponding list request and does not trigger fallback.
- [ ] 2.2 Extend track-only fallback to apply latest acquisition and prioritization on the tags path; verify controlled success, tags/latest failure before the tag list, retained release inspection count, and no fallback after version/date extraction failure.
- [ ] 2.3 Add live integration coverage for latest response/failure reuse, mixed-setting variant selection without cached-document mutation, report round-trip of 101 inspected releases, and zero routine asset requests; verify these cases through the existing live client and report reader.

## 3. Compatibility evidence and validation

- [ ] 3.1 Update committed-pack compatibility expectations and set verifier identity to `0.3.0` while retaining schema `1`; verify no currently active pack settings remain unsupported and evidence recorded with `0.2.2` is displayed as stale.
- [ ] 3.2 Update verification guidance for latest prioritization, HTTP and tags-fallback failures, request budget and inspection counts; preserve historical observations and add a dated explanation distinguishing fixture validation from live upstream health.
- [ ] 3.3 Run focused resolver, compatibility, live integration and report tests, then `just check-all`; record results and verify distribution, configuration and package-id-cache bytes remain unchanged.
