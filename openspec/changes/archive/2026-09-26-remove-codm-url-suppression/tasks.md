## 1. Ingestion

- [x] 1.1 Remove the covered-URL filter and the higher-precedence input from the codm2000 adapter and ingestion wiring, keeping its dual-only, dual-preferred mapping, duplicate-ID check and admission reporting; verify every committed entry becomes a candidate and the admissions report lists all of them.
- [x] 1.2 Replace the codm2000 suppression tests with one test where a higher-precedence source lists the same project URL and both builds reach composition; keep the policy-field check covering every codm2000 record. Update the captured-fixture pipeline to stop filtering by URL. Verify the full test suite passes.

## 2. Configuration

- [x] 2.1 Add a package denial for `com.raekwon.supermetroid` and dual pins selecting the RJNY builds in the `package:app.nanostack.pixelguide` and `package:com.emulnk` families, each with a rationale. Verify composition validates the policy.

## 3. Outputs and review

- [x] 3.1 Rebuild both packs and the README and verify they match the committed outputs byte-for-byte; record the comparison in a `validation.md` in this change directory.
- [x] 3.2 Run formatting, lint, typing and tests, complete the implementation review wave and address its findings, and audit every checkbox against code, tests and evidence.
