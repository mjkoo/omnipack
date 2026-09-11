# Source-generation fixtures

The `accepted` directory is a controlled accepted-state example. Its catalog,
source metadata, and resolution state are one coherent unit; they are synthetic
and make no claim that the captured live README is currently publishable.

`candidate-layout.json` records the current-run output boundary. `cases.json`
names the migration cases that later generator and ingestion tests must exercise.
`migration-inventory.json` records the 24 normalized GitHub repositories in the
captured README, their relationship to captured higher-source inputs, and an
exact mapping to the maintained package-ID cache. An unresolved, unadmitted
project remains distinct from both accepted fallback and higher-source coverage.

The composition output hashes and family winners are anchored to the protected
historical fixtures under `tests/fixtures/composition-baseline`; those files are
inputs to this evidence and are not regenerated here.
