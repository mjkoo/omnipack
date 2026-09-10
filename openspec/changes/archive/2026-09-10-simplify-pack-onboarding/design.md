## Context

See proposal.md for scope and motivation. README contains a generated catalog bounded by markers; build preserves surrounding prose and nightly publishing rejects changes outside those markers. Existing specs prescribe both the old schedule and installation-first link order. The inherited RJNY tracker is package id `904332840`, mapped to `package:904332840`. The denylist supports exclusions covering both variants.

## Goals / Non-Goals

Goals: make the existing download/import path easy to follow and use existing curation and scheduling mechanisms.

Non-goals: new catalog rendering, automatic pack synchronization on devices, release packaging, removing RJNY as a catalog source, new manual apps, or changing unrelated tracker entries.

## Decisions

### Consumer-first README

Place two clearly labeled raw download links directly below the title, each with device guidance. Follow a brief description with an Install section before the individual catalog. Use four numbered actions: install Obtainium, download the appropriate JSON, open Import/Export and import the downloaded file, then choose and install desired apps from Obtainium. Explain that importing configurations does not itself install every app. Verify exact UI labels during implementation against the supported Obtainium version.

Retain individual import confirmation and track-only explanations. Turn existing credits into bullets, keeping links to both BBoi variants and all current attribution. Keep the generated markers and renderer unchanged. Move setup/build/verification prose to `docs/development.md`, and publisher operational detail to the existing publishing guide. A short Contributing section links to `docs/`, whose README offers development entry points. Repair relative links after moving prose. A brief consumer-facing daily refresh sentence is sufficient in the root README.

### Local-time scheduling

Use `cron: "0 3 * * *"` with sibling `timezone: "America/New_York"`. GitHub now supports IANA zones, so fixed UTC offsets or two triggers with a runtime DST guard are unnecessary. Update the existing workflow test, publishing guide, and spec together. Preserve all publication guards and verification gates.

Primary reference, checked 2026-09-10: [GitHub schedule documentation](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule).

### Remove only the upstream tracker

Add a denylist entry for id `904332840` with a reason and no variant restriction. This persists across upstream refreshes, unlike editing distribution files. Keep the historical composition mapping unless existing validation requires removal; it is not an inclusion directive. Regenerate both packs and the catalog through the normal build. Retain RJNY source configuration, provenance, compatibility fixtures, attribution, and legacy issue marker. Update current curation documentation and project context so they no longer imply the tracker must remain included.

An exclusion affects future exports only. Existing Obtainium installations may retain the imported tracker; explain that users can remove that tracking entry manually without removing their emulator apps.

### Self-tracking feasibility and follow-up

The current [Obtainium GitHub implementation](https://github.com/ImranR98/Obtainium/blob/main/lib/app_sources/github.dart), inspected 2026-09-10, fetches releases and falls back to tags for track-only entries. Setting `trackOnly` on the omnipack repository URL will not watch files committed to main. Creating releases merely for this is unnecessary overhead.

A promising separate change is an explicit HTML-source tracker per device variant, reading the GitHub contents API for that variant's JSON on main, extracting its blob SHA as the version and selecting its raw download URL with a custom link filter. This would track actual pack content rather than every documentation commit. The [HTML implementation](https://github.com/ImranR98/Obtainium/blob/main/lib/app_sources/html.dart) supports whole-response regex extraction, but still requires a selected link in the inspected version. Omnipack's local resolver currently permits linkless whole-page tracking, so that shortcut must not be treated as proof of Obtainium compatibility.

This is a candidate design, not verified device support. Before adding it, validate the public API response, URL preservation with explicit HTML override, raw JSON link selection, SHA extraction, nonnumeric version change detection, and import/re-import on a device. Use stable synthetic tracker IDs and static configuration; never embed the observed SHA into the pack itself, which would cause publication feedback. Verify unchanged-content no-ops, changed-content notifications, and graceful handling of API rate limits. Notifications must explain that users still download and re-import the pack; tracking does not synchronize configurations automatically. Defer this addition from the cleanup proposal and preserve these findings in durable curation documentation during implementation.

## Risks / Trade-offs

- Hour-boundary Actions queues may delay or drop runs. Preserve the existing best-effort scheduling contract; 03:00 is the scheduled time, not a guaranteed completion time.
- Live upstream changes can add unrelated build differences. Inspect output changes and distinguish the tracker exclusion from upstream drift before accepting regeneration.
- Removing an export entry does not prove deletion from an existing device. Keep migration guidance explicit and avoid claiming device acceptance without observation.

## Migration Plan

After proposal convergence, create an implementation branch off main and commit planning artifacts there first, following project policy. Implement prose, configuration, tests, and specs together; regenerate outputs and perform offline and metadata verification. Leave the branch for the owner to land. The revised schedule becomes active on main. Rollback restores the previous prose, denylist and schedule and rebuilds; it does not modify device state.
