## 1. Refresh orchestration and candidate gates

- [x] 1.1 Add the repository automation helper with explicit stage outcomes and injectable process/API boundaries. Add failing controlled tests for check/build/live-verification order, early failure, warning-only success, and absent/stale/incomplete evidence; verify the implementation passes them without external writes.
- [x] 1.2 Implement disposable attempt setup, lockfile sync, existing offline Python checks, fresh build and metadata-only verification. Verify tests assert fresh commands per attempt, no probe flag, preserved soft-failure policy, and no publication after any failed gate.
- [x] 1.3 Implement verified-byte snapshots and the three-file publication allowlist. Verify missing files, symlink replacements, unexpected tracked changes, post-verification mutations, staged-content mismatches, cache-only changes, and byte-identical no-ops with temporary fixtures.

## 2. Git publication and concurrent updates

- [x] 2.1 Implement bot commits containing UTC date, run URL and base SHA, plus normal fast-forward publication. Verify local disposable Git repository tests show one commit containing only changed allowed files, no empty commits, and no force-push behavior.
- [x] 2.2 Implement the two-attempt budget with fresh checkout, sync, checks, build and verification after main advancement. Verify concurrent-change tests reject stale candidates, retain earlier attempt diagnostics, check main for no-ops, and fail on a second advancement.
- [x] 2.3 Implement remote reconciliation after rejected or ambiguous pushes. Verify intended-commit ancestry recognizes successful publication, an unchanged rejected main fails, advancement consumes only the remaining retry, and unreadable remote state reports uncertainty without another blind push.

## 3. Failure issue and diagnostics

- [ ] 3.1 Implement paginated discovery of bot-authored marked issues, canonical selection, create/update/reopen behavior and duplicate closure. Verify controlled API tests cover closed issues, pagination, PR exclusion, unrelated same-title issues, and rediscovery after ambiguous creation.
- [ ] 3.2 Implement recovery after publication and verified no-op, with no issue creation on success. Verify issue API failures fail the workflow result without undoing confirmed publication, and a later successful run retries closure.
- [ ] 3.3 Implement bounded issue bodies, run summaries and per-attempt diagnostic output. Verify early failures identify missing reports, upstream text is passed as data, credential values are redacted, and artifact selection excludes APKs, raw caches and unrelated files.

## 4. Workflow integration

- [ ] 4.1 Add the daily 06:23 UTC and manual workflow with canonical-repository/main guards, shared publisher concurrency, 60-minute timeout, existing pinned tool conventions, and explicit token permissions. Verify workflow inspection and actionlint/zizmor cover trigger guards, no automatic asset probes, and no credential persistence.
- [ ] 4.2 Wire helper execution and finalization so handled setup/check/build/verify/publication failures reach issue reporting and available diagnostics upload with 14-day retention. Verify controlled workflow-boundary tests cover setup failure, publication success followed by issue/upload failure, and distinct final outcomes; inspect cancellation limitations.
- [ ] 4.3 Verify official GitHub documentation for token-authored push triggers and direct-push prerequisites, and ensure pre-publication checks do not depend on recursive CI. Confirm the helper is covered by repository lint/type/test commands and verify the focused orchestration suite passes.

## 5. Documentation and complete validation

- [ ] 5.1 Add durable publishing guidance and update README with schedule, manual dispatch, commit allowlist, metadata-only gate, cache-only/no-op behavior, retry budget, issue recovery, retention, required repository permissions and rollback procedure. Verify all instructions describe implemented behavior and keep asset probing as manual troubleshooting.
- [ ] 5.2 Run focused orchestration tests, actionlint, zizmor and `just check-all`; record outcomes in durable validation documentation. Verify tests did not change real dist/config/cache files, push to GitHub, dispatch workflows, or create real issues.
- [ ] 5.3 Document the post-landing operational acceptance procedure: check repository prerequisites, explicitly dispatch on main, inspect fresh live evidence and confirmed publication/no-op, and inspect issue recovery if applicable. Verify this is clearly a future maintainer operation rather than a claimed completed live test or an automatic implementation step.
