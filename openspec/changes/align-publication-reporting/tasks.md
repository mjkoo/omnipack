## 1. Display the recorded build diagnostics in the report command

- [x] 1.1 Add failing report tests: a build report recording candidate changes,
  denylist exclusions, denials that matched no candidate and admitted committed
  candidates displays each of them, identifying the variant and package id of a
  change, the package id, variant, family and reason of an exclusion, the
  package id and reason of a stale denial, and the source, project URL, entry
  kind and committed id of an admission, with a fixture carrying one added and
  one removed package id in the same variant whose rendered lines differ by
  direction; a report recording none of them
  displays the build section with no diagnostic output and exits zero; a report
  whose candidate comparison is null displays it as unavailable and never as a
  build that added and removed nothing; a failed build's populated comparison
  displays as candidates that were not published rather than as apps added and
  removed since the previous output; a malformed element in any of the four
  lists raises the report format error rather than printing a partial line; and
  a stored report written before this change still displays. Keep the existing
  absent-substring assertions passing.
- [x] 1.2 Emit the diagnostics between the selection lines and the stage and
  error lines in `format_reports`, validating element fields where they are
  formatted with the existing string type guard and raising the report format
  error, leaving `_validate_build_report` and `BUILD_SCHEMA_VERSION` untouched;
  confirm the focused report tests pass.
- [x] 1.3 Add one command-level case that builds and then reports, confirming
  the diagnostics reach the command's output and that the build report file is
  unchanged by reporting. Pass the group's independent evidencing review and
  record the result in the change directory.

## 2. Align the maintainer guide with the command

- [x] 2.1 Replace the passage in the development guide that tells readers the
  report command prints selections but not the denylist removals, stale
  exclusions or candidate changes, and stop describing the command's output as
  warnings; keep the guidance on what each list means and on checking a new
  denial against the exclusions and the stale denials. Confirm the link and
  documentation checks pass. Pass the group's independent evidencing review and
  record the result in the change directory.

## 3. Confirm the publication requirements against the workflows and scripts

- [ ] 3.1 Confirm against the checked-in workflow and publication scripts, and
  record the evidence in the change directory, that the read-only job summarizes
  a prepared candidate as a distinct outcome from a published commit, a no-op
  and a failing stage; that both diagnostics and hand-off uploads run in the
  read-only job and so cannot follow a push; and that a push that lands but
  whose commit cannot then be checked out reports the published commit, exits
  nonzero and leaves the release step unrun. Confirm that no unconditional claim
  that a successful push is followed by release synchronization survives in the
  publication capability, by reading the change's nightly-publishing delta
  against the main spec and finding the release-synchronization requirement
  conditioned on the publisher establishing the pushed commit locally. Confirm
  no workflow or script change is required by these deltas, and that the
  existing publication tests still pass unchanged.
- [ ] 3.2 Confirm the split carries every rule and scenario of the removed
  requirement into the two that replace it, with no rule dropped and no scenario
  living on both sides, and that the credential boundary reads the same when the
  two are read together. Pass the group's independent evidencing review and
  record the result in the change directory.

## 4. Complete implementation validation and reviews

- [ ] 4.1 Run the full suite and applicable repository checks, including offline
  pack verification and strict artifact validation; confirm configuration,
  committed packs, distribution files and workflows remain unchanged, and record
  the results in the change directory.
- [ ] 4.2 Complete the implementation workflow's independent whole-diff review
  wave and checkbox and evidence audit, resolve findings, rerun affected checks
  after fixes, and retain a self-contained validation record. Leave the change
  active and report the implementation branch.
