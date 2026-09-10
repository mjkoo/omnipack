## 1. Document and verify existing package-format compatibility

- [x] 1.1 Update docs/verification.md with provider-specific package-container, generic ZIP and HTML custom-link boundaries and outer-response inspection limits; verify the wording against the delta scenarios and focused resolver tests.
- [x] 1.2 Add focused regression coverage for GitHub/GitLab recognized extensions and filter inputs plus HTML default versus custom filtering, including link-text selection with a recognized package path followed by a query or fragment; verify it with existing ZIP-selection, bounded-probe and generated .apk-only package-ID tests against unchanged runtime code.
- [x] 1.3 Record a durable verification summary with test results and a comparison confirming unchanged runtime, configuration and generated outputs; verify strict OpenSpec validation and the required project checks pass while operational acceptance stays deferred.
