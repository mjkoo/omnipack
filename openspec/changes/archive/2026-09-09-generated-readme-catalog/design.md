## Context

See proposal.md for motivation. Build currently renders and validates two JSON
documents before recoverable replacement. Standalone verification fingerprints
eight inputs; nightly commits only those packs and the package-ID cache. Current
exports contain 107 selected families; encoded per-app links add roughly 330 KB
before surrounding markup and outer query encoding.

## Goals / Non-Goals

Goals: reuse final export records and current policy for reproducible catalog
generation, preserve handwritten README bytes, and bind publication to verification.

Non-goals: changing composition, introducing a catalog service, importing a remote
pack through an unsupported URL handler, or claiming unperformed Android acceptance.

## Decisions

- Add a pure catalog module taking serialized variant documents and a loaded
  composition policy. Parse the final app records rather than rendering partial
  composed objects again. Both build and verify use this same generator. Reject
  duplicate projected families rather than silently dropping an entry.
- Group by current rendered-family projection. Single-screen supplies the display
  name and first category when available, otherwise dual does. Empty categories
  become Other. Sort by casefolded category/name, exact category/name, then family.
  Each category uses a closed HTML details/summary wrapper around a Markdown table.
  Escape source text including Markdown punctuation, HTML, pipes and line breaks.
  Each variant cell shows its record's source label and URL plus its import link.
- Follow https://wiki.obtainium.imranr.dev/deep_links/ using the official
  https://apps.obtainium.imranr.dev/redirect endpoint. Compact JSON is percent
  encoded into obtainium://app/; the complete deep link is query encoded as r.
  Verify the redirect's real decode behavior and record a round-trip fixture.
  Full app payloads preserve settings and unknown fields; pack settings stay out.
- Parse README as bytes around the two exact standalone markers. Preserve marker
  lines and surrounding bytes; generate the interior with deterministic LF bytes.
  Malformed markers fail rather than creating a second catalog or guessing bounds.
- Capture README before generation, then validate candidate packs and catalog
  before publication. Recheck captured README and consumed policy before replacing
  files. Generalize the existing recoverable writer to stage files beside their
  destinations, clean up temporary files on every handled failure, and restore
  replaced files from snapshots. This is exception recovery, not crash atomicity.
- Include README as a ninth standalone verification input and add catalog errors
  before live resolution. Advance verifier identity; accept historical report
  input sets for display while current fingerprint/identity comparison rejects
  them as publication evidence. Update report schema validators and test fixtures.
- Extend nightly's allowlist with README and require identical prefix and suffix
  against HEAD at capture and staged validation. Reuse existing exact-byte evidence,
  candidate mode, retry and no-op checks rather than adding another publishing path.

## Risks / Trade-offs

- Long links and GitHub HTML rendering need a rendered preview and representative
  browser/Android smoke checks. Automated round trips prove payload fidelity, not
  Android handoff. If no device is available, explicitly document pending acceptance.
- A manual edit during a build must not be overwritten. Snapshot checks cover
  detected edits before publication; this does not introduce filesystem locking.
- Strict README verification means migration must include the initial generated
  catalog with the code so existing offline checks do not block the next refresh.
- Variant categories can differ. Single-screen presentation takes precedence for
  one family row; each payload retains its own original category unchanged.

## Migration Plan

Implement on a separate branch based on the completed composition branch, retaining
that dependency without rewriting its commits. Add the handwritten README guide
and markers, generate the catalog from the committed exports without refreshing
upstreams, and verify all links and current outputs. Sync the behavior delta to
main specs in the same branch. Run the required review and completion gates.
Do not push, merge, dispatch GitHub workflows or archive either change implicitly.
Rollback is a reviewed revert of this change's code, documentation and specs together.
