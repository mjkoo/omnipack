## MODIFIED Requirements

### Requirement: Release writes require an established main outcome

Release assets SHALL only come from a verified pair associated with a
successful main push or a verified main no-op; a failed or erroring main push
SHALL prohibit release mutation. Release mutation SHALL also require main to
still be at the commit that pair came from; otherwise the release stage SHALL
fail without writes, so a rerun of an earlier run's publisher cannot move the
release back to an older pair. A push that lands SHALL
authorize release mutation only while the publisher can establish that pushed
commit as its own local revision; a run that cannot SHALL fail with the push
reported and without release writes, so no run publishes the pair it happens to
hold under a commit it did not establish.

A rerun of an earlier run's write job after main moved off the revision that
run checked out, including when the run's own push is what moved it, SHALL fail
without a push or release write, and recovery SHALL be a new run, not a rerun.
When the rerun's push or release step finds main off the revision it expects,
the summary SHALL report that main advanced; a step that stops earlier for
another reason reports that reason. A run that prepared a candidate reaches
those steps only while the hand-off of that candidate from the job that
prepared it is still retained; once it is not, the rerun SHALL fail before
either step, and no particular reason is required of its summary.

#### Scenario: The push lands but its commit cannot be established

- **WHEN** the push of the verified commit succeeds and the publisher then cannot make that commit its own local revision
- **THEN** the run fails with the published commit reported and performs no release write
- **AND** a later verified run whose output is already on main synchronizes the release as a verified no-op

#### Scenario: Main outcome is uncertain

- **WHEN** the main push reports an error, whether or not the commit actually landed
- **THEN** the run fails and performs no release writes
- **AND** a later run that finds the commit on main treats it as a verified no-op and synchronizes the release

#### Scenario: Write job rerun after main advanced

- **WHEN** the write job of an earlier run is rerun after a later run changed main, and the earlier run either prepared no candidate or its candidate hand-off is still retained
- **THEN** it fails without a push or release write, and the summary reports that main advanced
- **AND** the release keeps the later run's pair and revision

#### Scenario: Write job rerun after its own push landed

- **WHEN** a write job is rerun after its own push reached main, for example to retry a failed release stage, while the run's candidate hand-off is still retained
- **THEN** the rerun fails without a push or release write, and the summary reports that main advanced, because main is then the pushed commit rather than the revision the run checked out
- **AND** a new run finds a verified no-op and synchronizes the release

#### Scenario: Write job rerun after its candidate hand-off is no longer retained

- **WHEN** the write job of a run that prepared a candidate is rerun after main moved off the revision that run checked out and the candidate's hand-off is no longer retained
- **THEN** the rerun fails before any push or release write, and no particular reason is required of its summary
- **AND** recovery is a new run, not a rerun
