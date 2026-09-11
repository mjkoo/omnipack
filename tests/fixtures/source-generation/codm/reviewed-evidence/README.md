# Reviewed source-generation evidence

These fixtures capture the observations used to review the initial codm project
policy on 2026-09-11. `observations.json` records the selected GitHub release and
asset metadata. The three manifest text files retain the package line emitted by
`aapt dump badging` for the downloaded APK; each observation also records the
SHA-256 of that APK and its extracted binary `AndroidManifest.xml`.

The Kanto Gear release asset was inspected with `unzip -Z1`. It contained Lua,
image, font and JSON resources, including `main.lua` and `manifest.json`, and no
`.apk` member. Its upstream README directs users to install the official
[Gen1Recomp](https://github.com/bryanthaboi/gen1recomp) host, then install Kanto
Gear through the [official Mod Index](https://bryanthaboi.github.io/gen1recomp-mod-index/)
or import the release ZIP.

`project-policy.json` is reviewed input, not generated output. `index.json`
binds its exact bytes, each individual rule in canonical sorted-key JSON, the
observation document and the retained manifest text. `expected-additions.json`
keeps the requested additions separate from the frozen baseline and binds that
baseline by path and SHA-256.
