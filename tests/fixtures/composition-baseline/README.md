# Composition baseline fixtures

`single-screen.json` and `dual-screen.json` are byte-for-byte copies of the
committed outputs at source commit
`9a33d26fd0b5eb22ad0f2a0ba52ee59ac9eac565`. `index.json` records their hashes,
settings, entry counts, and representative candidates from every source origin.

These fixtures let composition and reporting tests compare migration behavior
without fetching an upstream catalog. They are a historical baseline and must
not be refreshed merely because a later build changes its selection.

`replacement-candidates.json` preserves the six full records for OpenMW, Super
Metroid and Dusklight standard/dual pairs, captured from the recorded BBoi release
on 2026-09-09. The asset origin fields identify the source of each record.

The same file also retains Simon CTR's original standard-asset record, before
its manifest-backed package correction. `codm-ctr-readme.md` is the exact Project
table header and CTR-DS row captured on 2026-09-09 from
<https://raw.githubusercontent.com/codm2000/Dual-Screen-Games/main/README.md>.
The composition regression routes these excerpts through the BBoi and codm
adapters, using the recorded Codeberg release fixture and the maintained
`config/package-ids.json` CTR identity. Package resolution is a cache-backed test
double; this offline regression makes no fresh APK or live catalog claim.
It exercises all active rules in `config/composition.json`, whole-build selection,
source settings and original provenance. Existing curation fixtures separately
exercise maintained overlays on historical selected output records.
