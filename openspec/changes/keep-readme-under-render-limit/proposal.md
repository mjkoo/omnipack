# Proposal

## Why

GitHub stops rendering a README after 500 KiB (512,000 bytes) and gives no sign
that it did. The generated catalog has grown the README to about 815 KiB, so the
rendered page on GitHub ends inside one catalog row: the later category tables
and the Sources and credits section are missing, and the row at the cut shows a
raw URL instead of its "Add to Obtainium" link. Nothing in the pipeline noticed.

Almost all of that size is the "Add to Obtainium" links. Each one embeds the
complete exported app record, including every setting left at its default,
URL-encoded twice inside the redirect URL: about 2.4 KB per link, across a few
hundred links.

## What Changes

- Catalog links for GitHub and GitLab entries leave out each
  `additionalSettings` key whose value equals that source's value in
  omnipack's committed settings defaults table. Each listed value equals what
  Obtainium (checked in v1.7.5) uses when the key is absent from an imported
  app deep link, so the imported app is configured as before.
  HTML entries, entries without a source type, and every other record field keep
  their exact values. The packs in `dist/` are unchanged. This brings the README
  to about 300 KiB.
- After a successful build, the nightly raises an alert issue keyed
  `build/readme-size` when the rendered README exceeds 450 KiB (460,800
  bytes), about 50 KiB before GitHub's limit. Its title says whether the
  README is already past the limit. The issue closes when a later nightly's
  README is back under the threshold.

This retires the guarantee that decoding a catalog link recovers the exported
app record exactly: for GitHub and GitLab entries it recovers the record minus
default-valued settings. It retires nothing else.

Estimated size: two modified requirements in readme-catalog, one each in
maintenance-alerts and pack-verification, and about five scenarios; about 50
implementation lines and 60 test lines.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `readme-catalog`: catalog links omit GitHub and GitLab settings equal to
  the committed defaults table instead of carrying the complete exported
  record.
- `maintenance-alerts`: a README a successful nightly build rendered over
  450 KiB raises one finding.
- `pack-verification`: the stale-import-link scenario describes a link left
  behind by an earlier configuration, since a trimmed link legitimately
  differs from the exported record.

## Impact

- `src/omnipack/catalog.py`: link generation trims default-valued settings.
- `src/omnipack/settings_defaults.py`: the docstring records the Obtainium
  version the GitHub and GitLab defaults were last checked against.
- `scripts/alerts.py` and `docs/alerts.md`: the `build/readme-size` finding,
  read from the README's size on disk; the build report is unchanged.
- Tests for catalog links and alerts.
- The README catalog shrinks at the next nightly; the published packs do not
  change.
