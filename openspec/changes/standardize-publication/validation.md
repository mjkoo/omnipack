# Validation

## Live generation comparison

Ran `uv run pack generate-source codm` against the live network. The command
exited zero and `.build/source-generation/codm/report.json` reported
`"status": "success"`.

`.build/source-generation/codm/catalog.json` differs from the committed
`config/catalogs/codm.json`: the generator picked up two projects added to
the upstream README since the committed catalog was last generated
(`github.com/igawa6/tomba2recompds` and `github.com/kalenjohnson/chrono-duo`),
matching the report's `changes.added` list. No entries were removed or
changed (`changes.removed` and `changes.changed` are both empty), and every
other committed project resolved identically. The run also recorded one
retained failure, for `github.com/rsigristc/dw3-ds-android`: its eligible APK
assets currently declare disagreeing package IDs
(`com.digitaladventure.dw2003` and `com.digitaladventure.dw2003.remote`), a
transient upstream condition, so the generator kept that project's committed
entry rather than failing the whole run, since its effective policy is
unchanged.

This is the expected behavior of stateless generation: real upstream drift
since the catalog was last committed, not a defect in this change. The
generated candidate was not copied over the committed catalog.
