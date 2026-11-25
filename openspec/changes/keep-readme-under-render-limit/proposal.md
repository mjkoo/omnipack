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
  `additionalSettings` key whose value equals Obtainium's default for that
  source. Obtainium fills every omitted setting with its source's default when
  it imports an app deep link, so the imported app is configured as before.
  HTML entries, entries without a source type, and every other record field keep
  their exact values. The packs in `dist/` are unchanged. This brings the README
  to about 300 KiB.
- The build records a README-size warning when the rendered README exceeds
  450 KiB (460,800 bytes), about 50 KiB before GitHub's limit.
- The nightly raises an alert issue for that warning, keyed `build/readme-size`,
  which closes when a later nightly's README is back under the threshold.
- `pack report` displays the warning like the build's other non-blocking
  outcomes.

This retires the guarantee that decoding a catalog link recovers the exported
app record exactly: for GitHub and GitLab entries it recovers the record minus
default-valued settings. It retires nothing else.

Estimated size: one modified and one added requirement in readme-catalog, one
modified requirement each in maintenance-alerts and pack-cli, and about five
scenarios; about 80 implementation lines and 80 test lines.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `readme-catalog`: catalog links omit GitHub and GitLab settings equal to
  Obtainium's defaults instead of carrying the complete exported record; the
  build records a warning when the rendered README exceeds 450 KiB.
- `maintenance-alerts`: a recorded README-size warning raises one finding.
- `pack-cli`: `pack report` displays the README-size warning among the
  build's non-blocking outcomes.

## Impact

- `src/omnipack/catalog.py`: link generation trims default-valued settings.
- `src/omnipack/settings_defaults.py`: the docstring records the Obtainium
  version the GitHub and GitLab defaults were last checked against.
- `src/omnipack/build.py` and `src/omnipack/report.py`: the build report gains
  the README-size warning and its schema version advances; `pack report`
  displays it.
- `scripts/alerts.py` and `docs/alerts.md`: the `build/readme-size` finding.
- Tests for catalog links, the build report and alerts.
- The README catalog shrinks at the next nightly; the published packs do not
  change.
