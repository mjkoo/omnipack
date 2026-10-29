# Spec Delta

## Purpose

Keeps a durable, versioned mirror of each packed app's current release, release
description and source history in an S3-compatible bucket, so an app stays
recoverable when its upstream disappears.

## ADDED Requirements

### Requirement: Archive runs follow nightly publishing

The system SHALL start an archive run after each nightly publishing run completes,
whatever that run's result, and on manual dispatch. Only main in the canonical
repository is eligible. Each run SHALL read both committed packs from main as they
stand when it starts. Archive runs SHALL be serialized without canceling an active
run. A run's outcome SHALL NOT affect nightly publication.

#### Scenario: Nightly publication completes

- **WHEN** a nightly publishing run finishes, whether it succeeds or fails
- **THEN** an archive run starts and reads both packs from the current main revision

#### Scenario: Ineligible invocation

- **WHEN** the archive is dispatched from another ref or runs in a fork
- **THEN** no bucket write occurs

#### Scenario: Archive fails

- **WHEN** an archive run fails
- **THEN** the nightly publishing run that preceded it keeps its outcome, and the next nightly publication proceeds as usual

### Requirement: Bucket credentials reach only the archive job

The bucket endpoint, bucket name and access keys SHALL come from the
secrets of a deployment environment that only the archive job uses. No nightly publishing job and no
source catalog job SHALL receive them. The archive job SHALL hold read-only
repository contents access, SHALL NOT persist a checkout credential, SHALL use
no caches and SHALL pin every action by commit SHA. The job that holds the
secrets SHALL install only the project and the `archive` dependency group.

#### Scenario: Publishing runs without the bucket credential

- **WHEN** a nightly publishing job runs
- **THEN** none of the archive secrets is available to it

### Requirement: Archive targets are the packs' fetchable projects

A run SHALL archive each distinct normalized project URL across both packs once,
using the first entry found when the single-screen pack is read before the
dual-screen pack. Entries marked track-only, and entries whose source is not
GitHub, GitLab or HTML, SHALL be reported as skipped and archived nothing.

#### Scenario: An app in both packs

- **WHEN** one project URL appears in the single-screen and dual-screen packs
- **THEN** it is resolved and archived once, using its single-screen entry's settings

#### Scenario: A track-only entry

- **WHEN** a pack entry is track-only
- **THEN** the run reports it skipped and makes no request for it

### Requirement: The archived version is the version Obtainium would report

For each target, the run SHALL select the release and compute the version string
that Obtainium would select and display for that entry's source and
`additionalSettings`. That includes prerelease inclusion, release title and notes
filters, sort method, fallback to older releases, APK filters, version extraction,
and the HTML intermediate-link, link-filter and request-header settings.

#### Scenario: Prereleases excluded

- **WHEN** a GitHub entry does not include prereleases and the newest release is a prerelease
- **THEN** the newest non-prerelease that passes the entry's filters is selected

#### Scenario: Fallback to an older release

- **WHEN** fallback to older releases is enabled and the newest release has no asset matching the APK filter
- **THEN** the newest older release with a matching asset is selected

#### Scenario: Version extraction

- **WHEN** an entry sets a version extraction pattern and match group
- **THEN** the archived version is the extracted value, not the raw tag

#### Scenario: HTML intermediate links

- **WHEN** an HTML entry lists intermediate link steps and a final link filter
- **THEN** each step's matching link is followed in order, and the APK and version come from the final page as Obtainium would resolve them

### Requirement: Some HTML versioning settings are stated exceptions

An HTML entry versioned by `partialAPKHash`, `ETag` or `releaseDateAsVersion`
SHALL be reported failed, and one versioned by `APKLinkHash` SHALL get a stable
stand-in version rather than the value Obtainium displays.

#### Scenario: An entry versioned by the release date

- **WHEN** an HTML entry sets `releaseDateAsVersion`
- **THEN** the target is reported failed and nothing is stored for it

### Requirement: Unchanged versions are not downloaded

When a target's resolved version already has a manifest in the bucket,
the run SHALL download no asset or source history for it, and SHALL
report it as unchanged. A prefix holding a manifest SHALL NOT be written again: a
resolved version whose prefix already has one SHALL be reported unchanged, with
nothing downloaded.

#### Scenario: Nothing changed since the last run

- **WHEN** two consecutive runs resolve the same version for every target
- **THEN** the second run reports every target as unchanged and downloads no release asset or repository

#### Scenario: A new release appears

- **WHEN** a target's resolved version has no manifest in the bucket
- **THEN** the new version is archived and the earlier version's objects are left in place

#### Scenario: Returning to an earlier archived version

- **WHEN** a target was archived at version A, then at version B, and a later run resolves A again
- **THEN** A's manifest exists, nothing is downloaded, and A's objects and manifest are left exactly as stored, even if that run is interrupted

### Requirement: Each archived version has its own prefix

Each archived version SHALL be stored under a prefix keyed by the target's
normalized project URL and that version, so that no two versions share a prefix,
together with a manifest naming every stored object with its size and SHA-256 and
recording the entry, the resolved version, the tag and the dates.

#### Scenario: Two versions of one app

- **WHEN** a target is archived at one version and later at a newer one
- **THEN** both versions' objects and manifests remain in the bucket under distinct prefixes

### Requirement: Retention keeps each target's three most recent versions

After a new version's manifest is stored, the target SHALL keep its three most
recently archived versions, ranked by when their manifests were stored, and SHALL
delete older ones. Each pruned version's manifest SHALL be deleted before its
other objects, so a partly pruned version never reads as archived. Prefixes
without a manifest SHALL NOT be pruned. The version just archived SHALL always
be kept. A pruned version that is selected again SHALL be archived again.

#### Scenario: A fourth version prunes the oldest

- **WHEN** a target holding three archived versions has a fourth archived
- **THEN** the oldest version's manifest is deleted first and then its other objects, and the three most recent versions remain

#### Scenario: An incomplete prefix is not pruned

- **WHEN** a target has a prefix without a manifest and a new version is archived
- **THEN** that prefix is left untouched

#### Scenario: A pruned version is selected again

- **WHEN** a later run resolves a version whose objects were pruned
- **THEN** it has no manifest and is archived again

### Requirement: A forge release stores its assets, description and history

For a GitHub or GitLab target, an archived version SHALL store every asset on the
selected release and every installable file Obtainium's resolution selects for it,
including files linked only from the release description, each stored once and
listed in the manifest, the release notes and the forge's release record.

#### Scenario: A GitHub release with desktop and Android builds

- **WHEN** the selected release carries APKs, desktop archives and checksum files
- **THEN** every one of those assets is stored, and the manifest lists each one with its size and SHA-256

#### Scenario: A GitLab APK linked only from the release description

- **WHEN** a GitLab release has no asset links and its description links the APK Obtainium would install
- **THEN** that APK is stored and listed in the manifest, and the version counts as archived only once it is stored

### Requirement: Source history is one bundle per target

The source history SHALL be one uncompressed git bundle of every branch and tag at
`apps/<source-key>/source/repo.bundle`, outside the version prefixes, replaced
only by a successful fresh capture made when a new version is archived. The
version's manifest SHALL record the bundle it captured (key, size and SHA-256)
or why none was captured.

#### Scenario: Restoring source history

- **WHEN** the stored git bundle is cloned directly
- **THEN** it yields every branch and tag the repository had at the latest capture

### Requirement: An HTML release stores its resolved file

For an HTML target, an archived version SHALL store the resolved file and its
manifest recording the source URLs fetched while resolving it, and no git bundle.

#### Scenario: An HTML source

- **WHEN** an HTML entry resolves a new version through one intermediate page
- **THEN** the resolved APK is stored, the manifest records both fetched URLs, and no git bundle is stored

### Requirement: A version counts as archived only when complete

A version SHALL count as archived exactly when its manifest is stored. The
manifest SHALL be written after every other object of that version has been
stored. A run that is interrupted or fails before then SHALL leave the version
without a manifest, so a later run archives it again.

#### Scenario: An asset download fails

- **WHEN** one of a new release's assets returns HTTP 404 while it is being archived
- **THEN** no manifest is stored for that version, the target is reported failed, and the next run attempts the version again

#### Scenario: The run hits its time limit mid-upload

- **WHEN** the job stops partway through a version's uploads
- **THEN** that version is not recorded as archived, and the next run archives it in full

### Requirement: Each target's outcome is reported and isolated

A run SHALL report one outcome per target: archived, unchanged, unreachable (HTTP
404 or 410), no release (none qualifies under the entry's settings), failed,
skipped or not checked. It SHALL write the report and a summary to the run's
output. No target's outcome SHALL prevent others being processed. Targets not
reached within the run's time budget SHALL be reported not checked.

#### Scenario: A deleted repository

- **WHEN** a GitHub target's repository answers HTTP 404
- **THEN** the target is reported unreachable, its earlier archived versions are untouched, and the run continues with the other targets

#### Scenario: The time budget runs out

- **WHEN** the run's time budget is exhausted with targets still unprocessed
- **THEN** those targets are reported as not checked, and the run does not fail for that reason alone

### Requirement: Missing source history does not fail a release

When a forge target's source history cannot be obtained, the version SHALL be
archived without a fresh bundle, its manifest SHALL record why, the earlier
bundle SHALL remain in place, and the target SHALL NOT be reported failed for
that reason alone.

#### Scenario: The source clone fails

- **WHEN** a new release's assets download but cloning its repository fails
- **THEN** the version is archived with its assets and description, its manifest records the clone failure, and the earlier bundle is left in place

### Requirement: The archive command runs and supports a dry run

The system SHALL provide `pack archive`, which performs an archive run against
the bucket configured by the `ARCHIVE_S3_*` environment variables and prints
each target's outcome, or its resolved version in a dry run, with the error
when there is one, otherwise the version, otherwise the reason. With
`--dry-run`, it SHALL resolve every target without bucket credentials and
download, clone and write nothing. `--budget-minutes` SHALL accept only a
positive, finite number.

#### Scenario: Dry run without credentials

- **WHEN** `pack archive --dry-run` runs with no bucket configured
- **THEN** it reports each target's resolved version and makes no asset download, clone or bucket write

#### Scenario: A target fails

- **WHEN** one target fails and the others are archived
- **THEN** the printed line and the report for the failed target show its error even when a version was resolved

#### Scenario: An invalid budget

- **WHEN** `--budget-minutes` is zero, negative, not a number or infinite
- **THEN** the command rejects it as invalid usage and starts no run

### Requirement: The archive command's exit status and report

The command SHALL exit nonzero only when the committed packs cannot be read,
the bucket cannot be reached or refuses the credentials, or the report cannot
be written; failed, unreachable or not-checked targets leave it zero. It SHALL
write, whole, a report and a summary under `.build/archive/` on every
invocation, a failed report recording the error when the run fails as a whole,
and SHALL rewrite them after each target, listing the targets not yet reached
as not checked.

#### Scenario: The bucket cannot be used

- **WHEN** the bucket is not configured or refuses the credentials
- **THEN** the command exits nonzero and writes a failed report recording the error

#### Scenario: The report cannot be written

- **WHEN** the report or its summary cannot be written
- **THEN** the command exits nonzero with a concise diagnostic whatever the targets' outcomes

#### Scenario: A killed run

- **WHEN** a run is killed after some targets were processed
- **THEN** the report on disk lists those targets' outcomes and the rest as not checked

### Requirement: The archive command's budget deadline

The run's time budget SHALL bound the whole run: no target SHALL start once it
is spent, and the target in flight when it passes SHALL be abandoned without a
manifest and reported failed.

#### Scenario: The deadline arrives mid-target

- **WHEN** the run's time budget passes while a target's files are being fetched or stored
- **THEN** that target is reported failed with no manifest stored, and the next run archives it in full

### Requirement: The archive command publishes only safe text and credentials

A bucket error's full message, which can name the endpoint or bucket, SHALL go
only to standard error; the failed report and the summary SHALL carry a fixed
description of its kind. The summary SHALL HTML-escape every URL, name, version,
error and reason inside a preformatted block. The `GITHUB_TOKEN` environment
variable, when non-empty, SHALL go only to the GitHub API and never across a
redirect.

#### Scenario: A bucket error names the bucket

- **WHEN** the bucket error's message contains the endpoint
- **THEN** the endpoint appears on standard error and in neither the report nor the summary

#### Scenario: Markup in a target's text

- **WHEN** a target's name, version or error contains markup
- **THEN** the run summary shows it escaped

#### Scenario: A download redirects off GitHub

- **WHEN** a GitHub asset download answers with a redirect to another host
- **THEN** the redirected request carries no token
