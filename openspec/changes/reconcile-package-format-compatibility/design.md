## Context

See proposal.md for motivation. The GitHub and GitLab resolvers recognize four
package extensions; tests/test_resolution_github.py already expects APKM.
HTML's default extension filter is replaced by a nonempty custom-link regex.
Without a custom filter, HTML chooses the configured URL-or-text input,
percent-decodes it, parses it as a URL and checks the parsed path suffix, so a
query or fragment does not become part of the extension comparison.
Generated package-id discovery independently inspects only .apk assets.

## Goals / Non-Goals

Align documentation with existing behavior and protect meaningful format/filter
boundaries with focused tests. No runtime, configuration, dependency, generated
output, warning-policy or device-behavior changes are part of this change.

## Decisions

Preserve package-container recognition instead of restricting it: the existing
GitHub test makes the intended compatibility explicit. Describe provider-specific
filter inputs rather than inventing one global extension gate. Package/container
metadata and bounded outer-response probes remain separate from binary evidence.

Keep the existing ZIP-member warning scoped to GitHub ZIP candidates. Describe
inspection limits in documentation for all containers without adding warnings.
Use the established fake HTTP fixtures for focused regression coverage, reusing
existing ZIP, probe and generated-ID tests where they already discriminate the
contract. These verification-only tests should pass against unchanged production
code; a failing regression requires checking the spec premise before any fix.

## Risks / Trade-offs

Container terminology can imply extraction support. Explicitly deny that inference
and distinguish generic ZIP settings, recognized package formats and arbitrary
HTML custom links. A future upstream adapter may change behavior; the contract
continues to describe the pinned compatibility baseline.

## Migration Plan

Update docs/verification.md and focused tests, verify the approved deltas, then
sync and archive. No consumer migration or output regeneration is required.
Operational and on-device acceptance remain deferred. GitLab consolidation is a
separate subsequent change against the synchronized requirements.
