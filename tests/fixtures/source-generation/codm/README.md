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

The `baseline` directory is a current-policy, pre-migration reproduction. It
runs the existing source adapters, composition policy, overlays, deny rules and
renderer against the captured reconciliation catalogs, the full captured codm
README and the captured package-ID cache. Its index binds every input by hash,
then records exact rendered bytes and family winners derived from the pipeline.

The older 88-entry single and 111-entry dual files under
`tests/fixtures/composition-baseline` remain protected historical evidence for
the policy revision they captured. They are intentionally not refreshed or
presented as the current migration baseline.
