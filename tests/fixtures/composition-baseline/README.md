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
