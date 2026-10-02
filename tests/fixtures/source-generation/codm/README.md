# Source-generation fixtures

The `baseline` directory is a current-policy, pre-migration reproduction. It
runs the existing source adapters, composition policy, overlays, deny rules and
renderer against the source catalogs captured for the September 10, 2026
reconciliation, the full captured codm README and the captured package-ID cache.
Its index binds every input by hash, then records exact rendered bytes and
family winners derived from the pipeline.

`pre-migration-config/` holds the frozen configuration inputs for that
reproduction. The index binds them by hash. They keep their original content,
including documentation paths that predate later moves, except where a
configuration field was retired: current parsing reads these files, so a
retired field leaves them in the same change that retires it, and the index
hash is rebound. The rendered goldens stay byte-identical, except where a
change deliberately alters what composition renders: then they are re-rendered
in that change and rebound, and only the altered fields and the resulting entry
order may differ. Category assignment from the closed taxonomy did this,
moving the two overlay category patches into the policy's category map and
dropping categories outside the taxonomy.

`pre-migration-captures/` holds those source catalogs byte for byte. The live
inputs under `../../reconciliation/` are refreshed as upstream moves, so the
reproduction keeps its own frozen copy, bound by hash in the index.
