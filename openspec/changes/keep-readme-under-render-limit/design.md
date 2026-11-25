# Design

## Context

See proposal.md (Why) for the problem. The current state that shapes the
approach:

- `generate_catalog` renders each "Add to Obtainium" link from the exported app
  record as the packs hold it. Exported records carry every setting the
  source's defaults table in `settings_defaults.py` lists, so most of a link's
  bytes are settings left at their defaults, URL-encoded twice.
- Obtainium (checked in v1.7.5) imports an `obtainium://app/` deep link through
  the same path as a stored app: it starts from the source's form defaults and
  overlays the settings the link carries. For GitHub and GitLab nothing else
  reads the settings as sent. For HTML, an import migration reads the original
  settings, so an omitted HTML setting is not guaranteed to import as its
  default.
- Every value omnipack's GitHub and GitLab defaults table lists equals what
  Obtainium v1.7.5 uses when that key is absent.
- The build renders the README in memory before it writes `.build/report.json`,
  and the nightly's alert step turns build report fields into `build/` findings.
  Every successful build report re-checks all `build/` keys, so a key a later
  report does not raise is closed.

## Goals / Non-Goals

**Goals:**

- Keep the README comfortably under GitHub's render limit with today's catalog.
- Warn through the existing alert issues before growth reaches the limit again.

**Non-Goals:**

- Changing the published packs. Full-pack imports and other consumers keep the
  complete records.
- Trimming HTML entries, entries without a source type, or record fields other
  than `additionalSettings`.
- Splitting the catalog into several documents. Trimming is enough today, and
  the warning says when that stops being true.

## Decisions

### Trim at link generation against the existing defaults table

The link for an entry whose `overrideSource` is GitHub or GitLab carries its
`additionalSettings` with each key removed whose value equals that source's
entry in the defaults table the renderer already uses. The trimmed settings are
re-serialized in the same compact form; every other record field is untouched.
A record whose settings are not a JSON object string is linked unchanged.

Alternatives considered:

- *Split the catalog into one linked document per category.* Keeps exact
  records, but changes how readers browse, adds generated files the nightly must
  write and the PR guard must cover, and still grows without bound.
- *Trim the exported records in `dist/`.* Would shrink the packs too, but the
  packs are the product, and their exact records are what verification and the
  archive pipeline check.
- *A second defaults table copied from Obtainium for links only.* Two tables
  would drift apart; one table keeps rendered packs and trimmed links
  consistent.

### Leave HTML and source-less entries complete

HTML's import migration reads the settings as sent, so an omitted setting there
may not import as its default; HTML entries keep every setting. An entry without
`overrideSource` relies on Obtainium detecting the source from its URL, and
guessing that source here would duplicate Obtainium's detection for little gain,
so those entries also stay complete.

### Record the warning as one nullable build report field

The build report gains a top-level field holding `{"bytes": <size>}` when the
rendered README exceeds 460,800 bytes and `null` otherwise, including when the
build fails before the README is rendered. The build report schema version
advances by one, so `pack report` asks for a fresh `pack build` rather than
misreading an older report. The threshold is one named constant beside the
catalog code, documented with GitHub's 512,000-byte limit. The size is that of
the whole rendered README, handwritten text included, because GitHub's limit
applies to the file.

Alternative considered: a nonfatal offline-verification finding. Verification
findings describe the packs, not the README, and the alert step reads build
report fields, not verification findings.

### One alert key with no subject

`scripts/alerts.py` raises `build/readme-size` when the field is set, titled
with the size and giving the size and the threshold in its details. With one
README there is one key, so no subject encoding is needed, and the existing
re-check scope closes the issue when a successful nightly records `null`.

## Risks / Trade-offs

- [Obtainium changes a GitHub or GitLab default] → A trimmed link would import
  the new default where the pack holds the old value. The packs keep the full
  records and the defaults table's docstring records the version it was checked
  against, but nothing forces the table to follow Obtainium; this drift risk is
  accepted, with no recurring check.
- [GitHub changes its render limit] → The threshold is one constant; the alert
  documentation names the limit it guards.
- [Growth outpaces the warning] → At about 1.5 KiB per new app, 50 KiB of
  headroom is roughly 30 apps, several weekly sweeps at the current pace.

## Migration Plan

Nothing to migrate. The schema advance makes existing local `.build/report.json`
files unsupported until the next `pack build`, which is the existing behavior
for a schema change. The README shrinks at the first nightly after merge.
Rollback is reverting the change; the next nightly restores full links.
