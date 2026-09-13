# Source-generation fixtures

The `baseline` directory is a current-policy, pre-migration reproduction. It
runs the existing source adapters, composition policy, overlays, deny rules and
renderer against the captured reconciliation catalogs, the full captured codm
README and the captured package-ID cache. Its index binds every input by hash,
then records exact rendered bytes and family winners derived from the pipeline.

`pre-migration-config/` holds the frozen configuration inputs for that
reproduction. The index binds them by hash. They keep their original content,
including documentation paths that predate later moves, except where a
configuration field was retired: current parsing reads these files, so a
retired field leaves them in the same change that retires it, and the index
hash is rebound. The rendered goldens stay byte-identical.
