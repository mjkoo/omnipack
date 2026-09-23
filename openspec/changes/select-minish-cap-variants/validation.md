# Minish Cap transition evidence

Observed September 23, 2026. The owner subsequently authorized the switch
without save migration because there are no existing users. The original
blocked assessment below records the evidence preceding that exception. No ADB command, device
inspection, installation, uninstall or save access was performed.

## Released APK observations

The GitHub latest-release API selected Sam v1.2 (published August 19, 2026)
and Picori v0.9.3 (published September 12, 2026). Each release contains one
APK. Both current pack entries point to Sam, with preferredApkIndex 0 and
an APK suffix filter, so the same Sam APK is the baseline for both variants.
The files were downloaded independently and their SHA-256 hashes match the
release API asset digests.

| Observation from bytes | Sam | Picori |
| --- | --- | --- |
| Package | `dev.picori.tmc` | `dev.picori.tmc` |
| versionName | `0.8.3` | `0.9.3` |
| versionCode | `80300` | `90300` |
| Minimum / target / compile SDK | 21 / 34 / 34 | 21 / 34 / 34 |
| Native ABIs | arm64-v8a, x86_64 | arm64-v8a, x86_64 |
| Requested permissions | android.permission.VIBRATE | android.permission.VIBRATE |
| Debuggable flag in badging | absent | absent |
| Signing certificate subject | C=US, O=Android, CN=Android Debug | CN=Project Picori, OU=TMC PC Port, O=999sian |
| Certificate SHA-256 | `3e9d065e36d575e0907aad30ea8e817a1bc1fffadb86c4edfcdd038a43eaa202` | `0982f3b7135a317d7185140fe35e805ab7f070aba930662161e1679771088458` |
| Signature verification | v1/v2 true; v3/v3.1/v3.2/v4 false | v1/v2 true; v3/v3.1/v3.2/v4 false |
| Signers / SourceStamp | 1 / false | 1 / false |
| Rotation lineage at API 33 | absent | absent |

- [tmc-dual-screen-v1.2.apk](https://github.com/samyost1/tmc-android/releases/download/v1.2/tmc-dual-screen-v1.2.apk): SHA-256 `9f666877ca468ca7944d8cd642803ed4e665fc49e23a3d88546a0d0d1c21424d`.
- [tmc-multi-android-v0.9.3.apk](https://github.com/999sian/tmc/releases/download/v0.9.3/tmc-multi-android-v0.9.3.apk): SHA-256 `dbb1b8f8c0239a21df438e615d14d9fe7d7e5985e1a2ef4c7c35d128fd5c2702`.

Android SDK build-tools 37.0.0 `aapt2` and `apksigner.jar` inspected the
actual APKs. Signature verification exited 0 for both across the tool's default
manifest-derived SDK range. An additional ApkVerifier check restricted to
API 33 returned `verified=true lineage=absent` for both. Each emitted warnings
that `META-INF/com/android/build/gradle/app-metadata.properties` and
`META-INF/version-control-info.textproto` are not protected by the JAR
signature. These warnings do not establish maliciousness or reproducible
source provenance. Both version-control records say `NO_SUPPORTED_VCS_FOUND`.
Source findings below are not a verified source-to-binary mapping.

Reproduce with the downloaded filenames above and `ANDROID_BUILD_TOOLS` set
to a local Android SDK build-tools 37.0.0 directory, and a JDK on PATH:

```sh
shasum -a 256 ./*.apk
for apk in ./*.apk; do
  "$ANDROID_BUILD_TOOLS/aapt2" dump badging "$apk"
  java -jar "$ANDROID_BUILD_TOOLS/lib/apksigner.jar" verify --verbose --print-certs "$apk"
done
```

For the API 33 lineage check, save this as `Lineage.java` and run
`java --class-path "$ANDROID_BUILD_TOOLS/lib/apksigner.jar" Lineage.java ./*.apk`:

```java
import java.io.File;
import com.android.apksig.ApkVerifier;
class Lineage {
    public static void main(String[] paths) throws Exception {
        for (String path : paths) {
            var result = new ApkVerifier.Builder(new File(path))
                .setMinCheckedPlatformVersion(33).setMaxCheckedPlatformVersion(33)
                .build().verify();
            var lineage = result.getSigningCertificateLineage();
            System.out.println(path + " verified=" + result.isVerified()
                + " lineage=" + (lineage == null ? "absent" : lineage.size()));
        }
    }
}
```

The signing subjects differ, their certificate fingerprints differ and there
is no observed rotation lineage. The replacement version code is higher, but
an ordinary update is unsupported by the signing evidence. This follows
Android's [signing compatibility model](https://developer.android.com/studio/publish/app-signing);
release tag ordering alone would give the wrong version comparison.

## Refreshed upstream and community findings

- [Sam v1.2](https://github.com/samyost1/tmc-android/releases/tag/v1.2)
  documents a dual panel, debug signing, a user-supplied ROM and unresolved
  EU text issues. Its [credits](https://github.com/samyost1/tmc-android/blob/7dbd15b797e60c2a6d9f8517bff782b2e70c67a4/README.md)
  identify Picori and Raekwon1603 Android packaging lineage.
- [Picori v0.9.3](https://github.com/999sian/tmc/releases/tag/v0.9.3)
  reports regional, rendering and stability fixes and requires a supported
  user-supplied ROM. These release notes are source claims, not device results.
- GitHub API refresh confirmed Sam issues
  [11](https://github.com/samyost1/tmc-android/issues/11),
  [19](https://github.com/samyost1/tmc-android/issues/19) and
  [20](https://github.com/samyost1/tmc-android/issues/20) remain open.
  They report partial emulator-save import, a room-transition freeze and
  autosave failure. They do not directly test Sam-to-Picori migration.
- The [AynThor discussion](https://www.reddit.com/r/AynThor/comments/1v7lp7x/the_legend_of_zelda_minish_cap_dualscreen_mod_for/)
  still contains an endorsement by an account identifying itself as Picori's
  author, plus freezes and lost-progress reports. Account identity was not
  authenticated. Community reports do not prove APK safety or save compatibility.
- The [Steam Deck discussion](https://www.reddit.com/r/SteamDeckEmu/comments/1vfsqtf/zelda_minish_cap_recomp/)
  remains desktop evidence; the older
  [Android discussion](https://www.reddit.com/r/retroid/comments/1th3zio/zelda_minish_cap_has_an_android_port_now/)
  mixes forks. Neither establishes this release pair's Android migration.
  Reddit pages were retrieved through the web index; this is a refreshed
  reading of available pages, not a guarantee of live comment completeness.

## Save route and reproducible non-device check

Inspected source revisions:

- Sam: `7dbd15b797e60c2a6d9f8517bff782b2e70c67a4` (v1.2).
- Picori: `eebb319fa4aa55c18c93de598bc0910d0608f25b` (v0.9.3 commit lookup).

GitHub's tag-addressed Picori tarball initially returned a directory ending
`fc3c87f`, while the commit endpoint resolved v0.9.3 to `eebb319...`. The
reason was not established. The source probe was repeated successfully on
an archive fetched by the explicit full commit above; only that repeat is
used as the source result here.

Both versions' `port/port_main.c` prefer the app-specific external directory,
with an SDL private-path fallback. The same-package paths do not survive
uninstall by contract: Android [removes app-specific storage](https://developer.android.com/training/data-storage/app-specific).
Sam's `port/port_save.c` restricts profile copies to local managed filenames;
the profile menu does not provide an independent external backup in the
inspected code. Merely making another profile is not preservation across
uninstall. Access to every active Android save location was not established.

Sam's `include/save.h` lacks the explicit byte at 0x25B that Picori adds.
Picori's [save loader](https://github.com/999sian/tmc/blob/eebb319fa4aa55c18c93de598bc0910d0608f25b/port/port_save.c)
shifts the legacy flags region, stamps the converted slot, updates checksums
and creates a `.bak`. It also distinguishes regional default saves and named
profiles. The [README](https://github.com/999sian/tmc/blob/eebb319fa4aa55c18c93de598bc0910d0608f25b/README.md)
claims old Picori saves are migrated. Neither that claim nor matching paths
establishes a complete Android transition from Sam.

A host C probe compiled the actual pinned Picori `port_save.c`, using a
synthetic USA EEPROM image with one checksum-valid legacy slot in wire byte
order. It checked the preserved prefix, shifted flag bytes, new layout stamp,
updated checksum, byte-identical original `.bak` and inert repeat migration.
Result: PASS. It does not exercise Android storage, released native libraries,
real story progression, other regions, sidecars or quicksave portability.

To reproduce, extract the explicit Picori commit archive, set `PICORI_SOURCE`
to its root, save the following as `save_probe.c`, and run in a disposable
empty directory (the probe writes `tmc.sav` and `tmc.sav.bak`):

```sh
cc -std=c11 -D_DEFAULT_SOURCE -DUSA -Wno-multichar \
  -I "$PICORI_SOURCE/port" -I "$PICORI_SOURCE/include" save_probe.c -o probe
./probe
```

```c
#include "port_save.c"
#include <assert.h>
int main(void) {
    u8 image[EEPROM_SIZE] = {0};
    u8 before[EEPROM_SIZE], disk[EEPROM_SIZE], backup[EEPROM_SIZE];
    memcpy(image, EEPROM_SIGNATURE_USA, 0x20);
    u8 *slot = image + 0x80, *status = image + 0x30;
    for (unsigned i = 0; i < 0x500; ++i) slot[i] = (u8)(i * 13 + 7);
    slot[0x4FF] = 0;
    u32 marker = (u32)'MCZ3';
    memcpy(status + 4, &marker, 4);
    u16 sum = CalculateImageChecksum(status + 4, 4) + CalculateImageChecksum(slot, 0x500);
    status[0] = sum; status[1] = sum >> 8;
    u16 neg = (u16)-sum; status[2] = neg; status[3] = neg >> 8;
    assert(StatusChecksumCoversData(status, slot, 0x500));
    memcpy(before, image, sizeof image);
    memcpy(disk, image, sizeof image); ReverseEepromBlocks(disk);
    FILE *f = fopen("tmc.sav", "wb"); assert(f);
    assert(fwrite(disk, 1, sizeof disk, f) == sizeof disk); assert(fclose(f) == 0);
    assert(EEPROMConfigure(0x40) == 0);
    assert(!sEepromWriteBlocked);
    assert(memcmp(sEeprom + 0x80, before + 0x80, 0x25B) == 0);
    assert(sEeprom[0x80 + 0x25B] == 0);
    assert(memcmp(sEeprom + 0x80 + 0x25C, before + 0x80 + 0x25B, 0x230) == 0);
    assert(sEeprom[0x80 + 0x4FF] == 1);
    assert(StatusChecksumCoversData(sEeprom + 0x30, sEeprom + 0x80, 0x500));
    f = fopen("tmc.sav.bak", "rb"); assert(f);
    assert(fread(backup, 1, sizeof backup, f) == sizeof backup); assert(fclose(f) == 0);
    assert(memcmp(backup, disk, sizeof disk) == 0);
    assert(MigrateEepromFlagLayout(sEeprom) == 0);
    puts("PASS: synthetic legacy slot migrated, checksum valid, original backup byte-identical, second migration inert");
}
```

## Initial gate result (before owner exception)

A complete save-preserving fresh-install route remains unresolved. The missing
evidence is reliable extraction before uninstall and restoration of actual
Sam saves, including active regional/named profiles and required sidecars,
followed by compatibility evidence sufficient to substantiate consumer steps.
The source-only probe proves one conversion property, not that end-to-end
route. An in-place update is incompatible with the inspected signing pair.
No migration is claimed supported, and no source selection is changed.

The standalone compatibility entry is maintained in
[consumer curation guidance](../../../docs/curation.md#minish-cap-publisher-transition).

### Owner-authorized exception

On September 23, 2026 the owner instructed: "disregard the save migration
requirement for this task, we have no users so it's safe". The exception
supersedes the selection blocker for this switch only. It does not turn the
unresolved route into a supported migration. Configuration may now select
Picori for single and retain Sam for dual; no device access is authorized.

## Repository checks

- Branch baseline: `uv run pytest --cov`: 816 passed, 94% overall coverage.
- `openspec validate select-minish-cap-variants --strict`, `git diff --check`
  and `uv run pack verify`: passed. Offline documentation link check:
  570 total links, zero errors.
- Before the exception, both exports were byte-identical to the branch base:
  - single-screen SHA-256: `6e7816f333b45123fa02f61b2ecb2da2b4743dcaf22bab729a2bb80bfcf42ccf`.
  - dual-screen SHA-256: `4c51ea78cd84439367d3c60e72e9a6ff5da80a4a4c9a07d2348c29bdda0ee24e`.


## Selection implementation

The Picori baseline extra uses the inspected `dev.picori.tmc` identity and a
stable Android-APK name filter, with version detection enabled. Both BBoi Sam
identity corrections remain. No explicit family, pin or overlay is needed:
extras precedence chooses Picori in single and dual preference chooses Sam in
dual. No existing Minish Cap overlay needed replacement. The historical
reconciliation fixture remains valid because both released APKs share the
corrected package identity. Quiver is not configured, so optional Quiver
coverage does not apply.

The regression initially failed in both current and refreshed cases because
single selected Sam. After the extra was added, the focused curation set passed
15 tests. The regression checks exactly one entry from either project per
variant, expected URLs, identity, Sam standard in the single considered list,
Sam dual origin, maintained Picori settings and selection under simulated Sam
settings refresh. The future-version filter check prevents a release pin.

Both BBoi identity rules remain required selectors. Removing a matched source
record causes the existing unmatched-selector failure; this change does not
promise a fallback to Picori after a required Sam record disappears. The
refresh regression therefore changes settings on retained source candidates.

`just check-all` passed: 818 Python tests (94% coverage), 108 Python 3.12 tests,
lock, formatting, lint, types, pack verification, workflow lint, offline links,
Nix formatting and native-platform flake evaluation/checks. Zizmor reported its
default offline mode and no findings. Nix reported a dirty git tree and omitted
incompatible systems; those are environment notices, not cross-platform test
claims. No device validation was performed.

Live `uv run pack build` succeeded. Parsed comparison against main found only
`dev.picori.tmc` changed in single-screen; dual-screen remained byte-identical.
Settings and every other app stayed unchanged. README comparison found exactly
one changed line, the Minish Cap catalog row. `uv run pack verify` passed again
after the build.


## Implementation reviews

The release-evidence group was independently approved against `d9dfac0`.
The explicit no-users exception was independently approved against `da6d3e9`;
its stale planning statement about unperformed APK inspection was corrected.
The selection group was independently reviewed against `7473be3`, with the
current/refreshed regression and output comparison evidencing all three tasks.

Two whole-diff reviewers examined the merge-base `fef4807` through `7473be3`:
correctness/consumer compatibility and idioms/test proportionality. Both found
no Critical, Important or Minor issues. The reviews confirmed the required
Sam selectors remain, the durable unresolved-migration record survives the
exception, and the new regression adds distinct real-composition coverage.
Historical identity evidence remains unchanged; optional Quiver coverage is
inapplicable because no Quiver source is configured. No fix round was needed.


## Completion audit

A fresh read-only auditor confirmed all seven previously checked tasks against
implementation commits and their checks, with no unevidenced boxes. The audit
itself completes the eighth task. The final post-audit suite passed all 818
tests (94% coverage); pack verification and strict change validation passed.
No implementation fixes followed the review wave or audit. The change remains
active on branch `select-minish-cap-variants`; the separate OpenSpec verification
and archive workflows have not been invoked.
