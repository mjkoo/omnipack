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
repository contents access.

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
recording the entry, the resolved version, the tag and the dates. Earlier
versions SHALL be kept.

#### Scenario: Two versions of one app

- **WHEN** a target is archived at one version and later at a newer one
- **THEN** both versions' objects and manifests remain in the bucket under distinct prefixes

### Requirement: A forge release stores its assets, description and history

For a GitHub or GitLab target, an archived version SHALL store every asset on the
selected release and every installable file Obtainium's resolution selects for it,
including files linked only from the release description, each stored once and
listed in the manifest, the release notes and the forge's release record, and a
zstd-compressed git bundle of every ref.

#### Scenario: A GitHub release with desktop and Android builds

- **WHEN** the selected release carries APKs, desktop archives and checksum files
- **THEN** every one of those assets is stored, and the manifest lists each one with its size and SHA-256

#### Scenario: A GitLab APK linked only from the release description

- **WHEN** a GitLab release has no asset links and its description links the APK Obtainium would install
- **THEN** that APK is stored and listed in the manifest, and the version counts as archived only once it is stored

#### Scenario: Restoring source history

- **WHEN** a stored git bundle is decompressed and cloned
- **THEN** it yields every branch and tag the repository had when that version was archived

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
archived without a bundle, its manifest SHALL record why, and the target SHALL
NOT be reported failed for that reason alone.

#### Scenario: The source clone fails

- **WHEN** a new release's assets download but cloning its repository fails
- **THEN** the version is archived with its assets and description, and its manifest records the clone failure

### Requirement: The archive command supports a dry run

The `pack archive` command SHALL perform an archive run against the configured
bucket. With `--dry-run`, it SHALL resolve every target and report each one's
resolved version, or its skipped, unreachable or no-release outcome, without
bucket credentials. A dry run SHALL
NOT download assets, clone repositories or write to any bucket.

#### Scenario: Dry run without credentials

- **WHEN** `pack archive --dry-run` runs with no bucket configured
- **THEN** it reports each target's resolved version and makes no asset download, clone or bucket write
