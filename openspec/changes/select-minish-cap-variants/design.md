## Context

See proposal.md for motivation. Existing composition corrects both BBoi Minish
Cap candidates to dev.picori.tmc and preserves the standard/dual distinction.
Extras can supply a higher-ranked baseline without displacing a real dual build.
No new source mechanism is needed to select a different baseline.

The September 22, 2026 delegated GitHub/Reddit survey supports a per-variant
choice, not a reputation claim that one maintainer is inherently safer:

- [Picori v0.9.3](https://github.com/999sian/tmc/releases/tag/v0.9.3), observed
  September 12, supplies Android assets and regional/stability fixes.
- [Sam v1.2](https://github.com/samyost1/tmc-android/releases/tag/v1.2), observed
  August 19, adds dual-screen controls and acknowledges EU text problems.
- [Sam's credits](https://github.com/samyost1/tmc-android#built-on) identify Picori
  and Android packaging lineage. Its panel supplies map, quests and inventory.
- The [AynThor discussion](https://www.reddit.com/r/AynThor/comments/1v7lp7x/the_legend_of_zelda_minish_cap_dualscreen_mod_for/)
  includes an endorsement from an account identifying itself as Picori's author,
  alongside freezes and save-loss reports. Account identity is not authenticated.
- The positive [Steam Deck report](https://www.reddit.com/r/SteamDeckEmu/comments/1vfsqtf/zelda_minish_cap_recomp/)
  is desktop evidence. The older [Android discussion](https://www.reddit.com/r/retroid/comments/1th3zio/zelda_minish_cap_has_an_android_port_now/)
  mixes forks and cannot establish current APK reliability.
- [Freeze](https://github.com/samyost1/tmc-android/issues/19),
  [save import](https://github.com/samyost1/tmc-android/issues/11) and
  [autosave](https://github.com/samyost1/tmc-android/issues/20) reports are relevant
  known limitations, not evidence of maliciousness.

These observations are research inputs. No release APK comparison or device
validation has yet been performed for this proposed switch.

## Goals / Non-Goals

**Goals:** retain second-screen functionality, select the upstream Android
baseline when adequately vetted, and make the migration implications explicit.

**Non-Goals:** blanket fork replacement, installing/uninstalling software,
copying saves, repairing upstream bugs, adding Quiver support or comparing
release tag numbers as Android version codes. No ADB access is authorized.

## Decisions

### Split preference by variant using existing configuration

Add a baseline extra for 999sian/tmc with an inspected identity and reviewed
release/APK settings. Preserve Sam's BBoi dual candidate. No single-screen
preference setting exists in configuration: no pin, denial or overlay names
Minish Cap, and the only Minish Cap composition rules are the two BBoi identity
rules correcting `com.samyost1.tmcandroid` to `dev.picori.tmc` for the
`bboi-standard-asset` and `bboi-dual-asset` builds. Sam wins single today only
as the family's sole baseline build, so the extra displaces it by source
precedence. Both identity rules remain. Group via the shared manifest-backed
package family if actual APKs agree; otherwise explicitly group the builds as
one app family using existing configuration, placing the family rule on the
extra and on both Sam rules so neither Sam build falls outside the family.
Never duplicate both builds within one export and never deny their shared
package to remove just one fork. Keep current source-specific overlays where
they still match; add Picori settings deliberately rather than inheriting Sam's
by package ID.

A blanket move would lose the dual panel. Retaining Sam everywhere would forgo
Picori's newer general baseline. Making the change depend on Quiver would add
unnecessary coupling; an extra expresses the preference even after Quiver is
admitted. If an existing pin changes that result, update it deliberately.

### Treat the APK comparison as an implementation gate

Inspect current official release APKs, recording URL, asset/hash, manifest
package/versionName/versionCode, SDK/ABI, permissions and signing-certificate
SHA-256. Compare the currently selected Sam release with Picori's selected
Android release, including signature rotation lineage if relevant. Both source
build configurations declare dev.picori.tmc, but source declarations do not prove
released package identity. Sam documents debug signing; Picori's build can use a
persistent CI key or a debug fallback. The release certificates must settle it.

An incompatible certificate or lower version code does not by itself disqualify
Picori, but makes an ordinary update claim invalid. Document a fresh-install or
other supported transition only when there is a substantiated save-preservation
route. Verify the route from upstream documentation/source and reproducible
non-device checks where possible; label absence of device testing explicitly.
While the save route remains unresolved, the modified requirement forbids
moving the pack's selection to Picori's build: the previous selection is
retained and the unresolved migration is recorded in `docs/curation.md` under
"Unresolved identity and selection findings", naming the family, dated
observations and unresolved save-preservation route. Raw APK and route
observations remain in this change's `validation.md`; the durable entry must
stand on its own without depending on that change-local evidence. That retention
is what the modified requirement demands; the implementation reports the blocker and
leaves the exports unchanged while the route is unresolved. Do not mark the
switch implemented merely because research was completed. Any device-dependent
follow-up requires separate approval.

### Keep evidence separate from consumer guidance

Write actual observations to validation.md in this change directory and stable
fixtures where required by tests. Put maintained preference, setup/migration
instructions and known limitations into consumer documentation. The unresolved-migration entry
in `docs/curation.md` is required even when configuration work never starts.
Do not present community reputation, a package match or structural verification as proof of
successful in-place installation or save compatibility.

## Risks / Trade-offs

- Same-package forks may have incompatible certificates. Compare released
  artifacts and state the required transition before changing the baseline.
- Save import/autosave has reported defects. Establish a preservation route and
  retain current selection if that cannot be done without unsupported claims.
- Available releases may differ from the dated survey. Refresh observations and
  use maintained selection settings, not a hard-coded release pin.
- Upstream can remove the dual candidate later. Preserve existing composition
  fallback semantics; do not invent an availability guarantee or unrelated pin.

## Migration Plan

First complete the artifact comparison and save-route evidence. Then update
configuration and outcome fixtures together, rebuild both exports and README,
and verify only the intended per-variant selection changed. Single should choose
Picori; dual should retain Sam. Run regression checks with refreshed source
settings to show the curated choice survives.

Rollback restores previous configuration and rebuilds both exports. It cannot
promise an installed-app downgrade or restore saves; those are separate user
actions governed by the documented compatibility evidence. This change and the
Quiver change touch different pack-curation requirement blocks and have no
ordering dependency; rebuild outputs against whichever configuration is current.
