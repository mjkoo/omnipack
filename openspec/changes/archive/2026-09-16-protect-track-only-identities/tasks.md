## 1. Enforce track-only candidate-rule restrictions

- [x] 1.1 Add failing policy tests for track-only family assignments, changed/restated package ids, and an ordinary candidate whose effective id equals a track-only candidate's id, both through a `packageId` correction and through an ingested id without a rule, plus a case where the offending candidate shares an id and normalized URL with an earlier-ordered candidate and the error names the offending candidate, plus descriptive-rule and ordinary APK controls; implement the matched-candidate guard and the reserved track-only-id invariant in one pass over all collapsed candidates before rule transforms and the rendered-projection check, and confirm the focused tests pass with selector-bearing errors.
- [x] 1.2 Exercise composition with a pin and with a denial that would otherwise hide the invalid track-only candidate; confirm both fail before selection, and use one CLI integration case to confirm prior outputs remain intact.
- [x] 1.3 Run current-configuration composition and tracker checks with captured sources, confirming no current candidate's effective id, ingested or corrected, collides with a track-only id; compare pre-change and post-change rendered bytes for both variants and confirm no configuration migration is needed. Pass the implementation group's independent evidencing review and record the result in the change directory.

## 2. Complete implementation validation and reviews

- [x] 2.1 Run the full suite and applicable repository checks, including offline pack verification and strict artifact validation; record results and confirm configuration, committed packs and workflows remain unchanged.
- [x] 2.2 Complete the implementation workflow's independent whole-diff review wave and checkbox/evidence audit, resolve findings, rerun affected checks after fixes, and retain a self-contained validation record. Leave the change active and report the implementation branch.
