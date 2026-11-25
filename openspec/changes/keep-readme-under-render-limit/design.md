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
- The nightly's prepare step runs the build, which writes `README.md` in the
  runner's checkout; the alert step that follows turns build report fields into
  `build/` findings. Every successful build report re-checks all `build/` keys,
  so a key a later run does not raise is closed.

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
A record whose settings are not a string holding a JSON object is linked
unchanged. A value equals a default only when both have the same JSON type as
well as the same value, so a `0` is never trimmed against a `false` default
even though Python's `==` treats them as equal.

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

### The alert step reads the README's size directly

When the build report records a successful build, the nightly-prepare alert
step reads the size of `README.md` in the checkout and raises
`build/readme-size` when it exceeds 460,800 bytes. The threshold and GitHub's
512,000-byte limit are named constants in `scripts/alerts.py`. The size is that
of the whole rendered README, handwritten text included, because GitHub's limit
applies to the file. Gating on a successful build keeps the check inside the
`build/` re-check scope, so a successful nightly under the threshold closes the
issue, and a failed build neither raises nor closes it.

The title says whether the README is nearing or past the limit and carries no
byte count, so a growing README does not retitle the issue every night; the
details give the size, the threshold and the limit, so a changed size updates
the issue body as any finding's new details do. A single nightly can add
enough apps to cross both numbers at once, and the title then says the README
is already truncated. With one README there is one key and no subject.

Alternatives considered:

- *A nullable build report field.* Lets `pack report` show the warning
  locally, but needs a schema version advance, report validation and display
  code for a number the nightly can read from the file it already has.
- *A nonfatal offline-verification finding.* Verification findings describe
  the packs, not the README, and the alert step does not read them.

## Risks / Trade-offs

- [Obtainium changes a GitHub or GitLab default] → A trimmed link would import
  the new default where the pack holds the old value. The packs keep the full
  records and the defaults table's docstring records the version it was checked
  against, but nothing forces the table to follow Obtainium; this drift risk is
  accepted, with no recurring check.
- [GitHub changes its render limit] → The threshold is one constant; the alert
  documentation names the limit it guards.
- [Growth outpaces the warning] → At about 1.5 KiB per new app, 50 KiB of
  headroom is roughly 30 apps, several weekly sweeps at the current pace; a
  jump past both numbers at once is reported as past the limit.
- [No local display] → `pack report` does not show the size; a maintainer
  checks `README.md` directly. The nightly is where the warning matters.

## Migration Plan

Nothing to migrate; the build report schema is unchanged. The README shrinks
at the first nightly after merge.
Rollback is reverting the change; the next nightly restores full links.
