## MODIFIED Requirements

### Requirement: Explicit track-only resources remain honest tracking entries

Track-only generation SHALL require, in reviewed policy, an explicit stable
numeric-string resource ID, a nonempty rationale and a documented manual
installation path. The installation path SHALL say in words where the resource
is installed from and SHALL name that place by an `https` URL carrying no
credentials, port, query or fragment, a github.com URL naming a repository and
nothing deeper; a rule with no rationale, or whose installation text holds no
acceptable `https` URL or nothing beyond one such URL, SHALL fail policy
validation with the project identified. It SHALL
validate a published release under the selected channel policy without APK or
archive downloads or package-ID discovery. It SHALL emit `trackOnly: true`,
`versionDetection: false`, `includeZips: false` and disabled APK architecture
filtering. The record SHALL contain no observed installed or latest version,
fixed download URL or claim of an Android package identity. Tracking outcomes
SHALL be separate from APK resolution in diagnostics.

A track-only resource SHALL appear under its own synthetic identity. Whether
it can replace the app it extends SHALL follow from the families
pack-composition forms once family rules apply, as "Composition policy assigns
app families by project URL" in pack-composition defines, and not from whether
their project URLs are equal. When the resource and the app belong to different
families, whether their URLs are equal or not, the resource SHALL NOT replace
the app's entry in either pack. When they belong to one family, whether by
sharing a URL or because owner family rules join their different URLs, they
compete under ordinary selection whatever their URLs, and which of them each
pack selects is governed by "One candidate per family and variant is selected
by fixed precedence" in pack-composition. Its description
SHALL carry the rule's rationale and installation path, and with consumer
guidance SHALL explain that path, and that Obtainium notifications and
acknowledgement neither install it nor detect its installed version. Enabling
ZIP extraction SHALL NOT be presented as a way to install a non-APK archive. The
pack's own notification tracker is not one of these resources; "Both packs
include one shared omnipack notification tracker" in pack-curation owns it.

A new tracker whose selected release cannot be verified SHALL block the
complete proposal. A tracker with a committed entry SHALL keep that entry on a
lookup failure, with a visible warning, only under the same unchanged-policy
rule as any other project: the current rule, rendered with the rule's tracker ID
and the committed URL, SHALL reproduce the committed entry exactly, so a changed
tracker ID blocks retention. A change of kind SHALL require fresh validation for
the destination kind, with no cross-kind fallback, and an APK package ID SHALL
NOT be reused as a tracker ID.

#### Scenario: A tracker and the app it extends are kept apart

- **WHEN** a dual-only track-only resource and the baseline app it extends
  belong to different families once family rules apply, whether their project
  URLs are equal or not
- **THEN** single holds the app's entry and not the resource's
- **AND** dual holds both entries, and neither replaces the other

#### Scenario: A tracker shares the app's family

- **WHEN** a track-only resource and the app it extends sit at one project URL
  and no family rule separates them
- **THEN** they are candidates of one family and pack-composition's precedence
  decides which entry each pack selects

#### Scenario: Owner rules join a tracker and its app at different URLs

- **WHEN** owner family rules assign a baseline app at one project URL and a
  dual-only track-only resource at another project URL to one explicit family
- **THEN** they compete within that family under ordinary selection
- **AND** single selects the app and dual selects the resource

#### Scenario: A tracked release contains only non-APK assets

- **WHEN** a track-only resource's published release is available and contains only non-APK archives
- **THEN** generation emits the tracking entry without seeking an APK or downloading an archive

#### Scenario: User acknowledges a tracking notification

- **WHEN** the user marks a tracked release as acknowledged in Obtainium
- **THEN** the documented update action remains the resource's manual installation path and no installation claim is made

#### Scenario: A new tracking resource is unavailable

- **WHEN** a new declared tracker has no verifiable permitted release
- **THEN** the source proposal fails with tracking diagnostics instead of accepting an unchecked partial catalog

#### Scenario: A tracker's resource ID changes and its lookup fails

- **WHEN** reviewed policy changes a committed tracker's resource ID and that tracker's release lookup fails
- **THEN** generation fails with no candidate catalog, and the committed entry is not retained under its old resource ID

#### Scenario: A track-only rule lacks a rationale or a usable installation path

- **WHEN** a track-only rule has no rationale, or its installation text holds no acceptable `https` URL or nothing beyond one
- **THEN** policy validation fails with the project identified, before any network request
