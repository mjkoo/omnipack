# Source-generation fixtures

The `baseline` directory is a current-policy, pre-migration reproduction. It
runs the existing source adapters, composition policy, overlays, deny rules and
renderer against the captured reconciliation catalogs, the full captured codm
README and the captured package-ID cache. Its index binds every input by hash,
then records exact rendered bytes and family winners derived from the pipeline.

`pre-migration-config/` holds the frozen configuration inputs for that
reproduction. The index binds them by hash, so they keep their original bytes,
including documentation paths that predate later moves.
