## Context

The codm2000 adapter builds a set of normalized URLs from higher-precedence
dual-eligible candidates and drops committed entries whose URL is in it. Ingestion
calls the adapter last so it can pass those candidates in. Everything downstream
already handles same-app builds from several sources: families form from a
shared package ID or an explicit family, dual preference and precedence select
inside a family, pins override selection, and denials remove package IDs.

## Goals / Non-Goals

**Goals:** codm2000 goes through the same path as every other source; the
published packs and README do not change.

**Non-Goals:** changing codm2000's dual-only, dual-preferred mapping; auditing
other sources' package IDs; any Quiver work.

## Decisions

### Resolve the hidden entries in configuration, not code

Each entry the rule hides is settled where the owner already records app
identity and selection. Six need nothing: their package IDs already meet
BBoi dual-asset builds, which are also dual-preferred and outrank codm2000 by
precedence. Two dual pins keep RJNY's Pixel Guide and EmuLnk renderings in dual,
because a codm2000 rendering would otherwise win on dual preference. One denial
covers the retired Super Metroid codm2000 build.

Alternative considered: make codm2000 entries ordinary instead of dual-preferred,
so precedence alone keeps RJNY's builds. Rejected here because it changes how
every codm2000-only app is selected, a larger behavior change than two pins.

### Prove "unchanged" against the committed outputs

The change is correct only if the rebuilt `dist/` packs and README match the
committed ones. A rebuild with the new code and configuration, compared
byte-for-byte with the current outputs, is the acceptance check. The captured
fixtures that encode suppression are updated to the new pipeline, not preserved.

## Risks / Trade-offs

- [An upstream refresh later changes a higher source's package ID for one of
  these apps] → The codm2000 build then forms its own family and appears in dual.
  It shows up in the nightly output diff, and the fix is a composition
  correction or denial, like any other identity change.
- [A pin's RJNY candidate disappears upstream] → Composition fails naming the
  pin, which is the existing behavior for stale pins.

## Migration Plan

Land code, configuration and tests together, rebuild, and confirm the outputs are
unchanged. Rollback is reverting the change.
