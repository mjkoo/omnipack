## 1. Single workspace and candidate refresh

- [ ] 1.1 Select main explicitly in the Actions checkout, capture its base revision and use that workspace directly; remove disposable attempt checkouts and reject initial tracked modifications. Verify eligible/ineligible invocations, clean-tree rejection and a controlled refresh that never switches revisions or creates another checkout.
- [ ] 1.2 Keep locked setup once in the workflow and reduce refresh commands to one build followed by one fresh structural verification. Verify command-boundary tests show no duplicate setup, development CI checks or pre-build verification, while build failure stops before candidate verification.
- [ ] 1.3 Preserve evidence freshness and candidate capture, README, file-mode, staging and commit-byte protections in the direct workspace. Run retained boundary tests for stale/incomplete evidence, changed verified bytes, symlinks, unrelated tracked changes, handwritten README mutations, cache/catalog-only changes and byte-identical no-ops.

## 2. One main attempt and independent release stage

- [ ] 2.1 Remove the second refresh attempt and automatic push retry; compare main before push or no-op and retain remote-history reconciliation. Verify advancement before push/no-op and a race after comparison produce no rebuild or second push, while lost acknowledgements confirm ancestor commits and unreadable remote results remain uncertain.
- [ ] 2.2 Remove seed preflight from main eligibility and synchronize releases only after confirmed main publication or a verified no-op from captured JSON bytes. Verify missing, malformed and unowned seeds allow valid main publication but fail release synchronization without unauthorized writes; failed or uncertain main outcomes must perform no release writes.
- [ ] 2.3 Preserve release state, shared revision, digest checks, explicit bootstrap and asset repair with separate main/release outcomes. Run retained release tests and a two-run controlled integration case proving a failed release is repaired after a later freshly verified main no-op without duplicate revision advancement.

## 3. Actions reporting and removal of issue automation

- [ ] 3.1 Remove the issue reconciler, issue-only interfaces and issue-write permission while preserving shared release transport. Verify no runtime issue operations or imports remain and retained release authentication, origin and redirect tests pass; remove tests exclusively covering the retired issue lifecycle.
- [ ] 3.2 Replace multi-attempt/fallback finalization with one run result and concise best-effort summary; log and flush confirmed main outcome before release work. Remove obsolete finalize/setup/upload commands, completion markers and reload recovery. Verify handled release failures and injected reporting/helper failures preserve earlier log confirmation and expose failure without issue calls or fabricated success.
- [ ] 3.3 Wire available allowlisted reports to Actions artifact upload with 14-day retention after success or failure, accepting missing reports after early failure while keeping actual upload errors visible. Verify workflow/helper tests cover setup failure, build failure, summary failure, upload failure, secret redaction and source text treated as data, with no serialized claim about an unknown upload outcome.

## 4. Documentation and integrated validation

- [ ] 4.1 Update current publishing, verification, development and operational-acceptance guidance for one attempt, CI-owned code checks, Actions diagnostics and release/main independence. Verify active documentation no longer promises managed issues, disposable-checkout cleanup, pre-main seed checks or fallback reconstruction, while archived plans and dated evidence remain preserved.
- [ ] 4.2 Run the full project development checks and controlled pipeline/publication integration tests. Record results and implementation/test reductions without a quota, and verify fixture exports, curation configuration and protected review records are unchanged; do not perform real main pushes, release writes or issue migration.
- [ ] 4.3 Verify implementation against both capability deltas, complete required implementation reviews and task-evidence audit, and synchronize specs through the archive workflow. Confirm strict change validation and main-spec validation pass and the implementation branch remains available without pushing or merging.
