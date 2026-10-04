# Reconciliation fixtures

Captured public source inputs and dated APK observations. The current
composition tests pair the committed configuration with these inputs, so they
are live-data outcome checks.

`bboi-release.json`, `bboi-standard.json`, `bboi-dual.json` and `rjny.json` are
the latest upstream inputs, captured byte for byte on September 26, 2026 from
the locations in `config/sources.json`: the Codeberg latest-release API, its
two catalog assets, and the raw GitHub catalog. Refresh them from those
locations whenever the maintained configuration starts depending on newer
upstream rows. They preserve original catalog IDs, URLs and origins
independently of the maintained composition rules.

`selected-observations.json` and `codm-relevant-readme.md` are dated
observations from the September 10, 2026 installed-app reconciliation and are
not refreshed with the live inputs.

Fixture SHA-256 values:

```text
7dcfd7717ca21f9a8942a1e2cf5b3ff1417aefd1b732ae84f48f40618d422f5c  bboi-release.json
fe9694649fc75f4b9265982fc8bef60d2c9375b34fad98ed3b3352c056abeb2d  bboi-standard.json
a841696871b351afec38277c2344aa35242358c533e099338d91faca79e3dc5f  bboi-dual.json
aff8d285128eb24cfd2e9e9d34eaa8422e9f58865c3b99467b81700dd04a06a5  rjny.json
721f1a73a31cb991503c0c25c329d7060873d4e0fb0c0fef828ecefd6c3f8a3f  selected-observations.json
3e326f7de286a60be35c2ab12197e2a3a8147afef8f5169efec79b13a5f92c45  codm-relevant-readme.md
```

`selected-observations.json` records the public release, selected asset URL,
manifest package and version, APK digest and signer certificate digest for each
corrected retained source. `../curation/reconciliation.json` records the bounded
identity map and official Ghostship ZIP/member observation. Runtime behavior does
not pin these dated hashes.

`formed-families.json` records the families the current composition forms from
these inputs, by the original selectors of their members, where more than one
surviving candidate eligible for some variant and not from a committed generated
catalog joins the family. Generated catalogs change only through reviewed
catalog updates, so their membership is not frozen here. The test requires the
recorded members to stay partitioned exactly as recorded, so merging two of
these families or splitting one fails. It is an expected output, so it changes
whenever the maintained rules or captured inputs change these families.
