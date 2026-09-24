# Reconciliation fixtures

Captured public source inputs and selected APK observations for the September 10,
2026 installed-app reconciliation. The source snapshots preserve original catalog
IDs, URLs and origins independently of the maintained composition rules.

Source snapshot SHA-256 values:

```text
551eee496727b98a05500eab46963f8d5a50180c019fd938e166287856cd8729  bboi-release.json
0beed3395dd49f7c8d2a2385ba780b690e17b1badf18804bb31582e58f6b0f5b  bboi-standard.json
a841696871b351afec38277c2344aa35242358c533e099338d91faca79e3dc5f  bboi-dual.json
697a2b8d567944917fd275e0159d7816db2ecbe56f4493142325ec9e3630eb61  rjny.json
721f1a73a31cb991503c0c25c329d7060873d4e0fb0c0fef828ecefd6c3f8a3f  selected-observations.json
3e326f7de286a60be35c2ab12197e2a3a8147afef8f5169efec79b13a5f92c45  codm-relevant-readme.md
```

`selected-observations.json` records the public release, selected asset URL,
manifest package and version, APK digest and signer certificate digest for each
corrected retained source. `../curation/reconciliation.json` records the bounded
identity map and official Ghostship ZIP/member observation. Runtime behavior does
not pin these dated hashes.

`formed-families.json` records, for every family the current composition forms
from these snapshots, the original selectors of the candidates that survive
exclusions and are eligible for some variant. It is an expected output, so it
changes whenever the maintained rules or snapshots change the families.
