## MODIFIED Requirements

### Requirement: Publish only verified pack outputs and the README catalog

The publisher SHALL limit commits to `dist/single-screen.json`,
`dist/dual-screen.json` and `README.md`. It SHALL reject the run when any other
tracked file is modified, added or deleted, when an allowed file is missing, or
when an allowed file is not a regular file of mode 100644, such as a symbolic
link or a file whose executable bit changed.
Committed source catalogs and other configuration SHALL NOT be published or modified by nightly. README changes SHALL be restricted to
the interior of exactly one valid catalog marker pair; bytes outside it,
including the markers, SHALL match the checked-out main. Changed allowed files
SHALL be published in one commit, and a candidate with no tracked changes SHALL
create no commit. Reports and transient caches SHALL NOT be committed. Before
pushing, the write job SHALL re-check that the handed-off commit changes only
allowed files, and that each changed file has mode 100644 in both the base
revision and the commit, rejecting symbolic links, submodule entries, additions,
deletions and mode changes.

Publication SHALL use a conventional commit identifying the UTC date, run and
base revision, and a normal fast-forward push to main. It SHALL NOT force-push
or alter repository protection settings to bypass a rejection.

#### Scenario: Candidate changes an out-of-scope tracked input

- **WHEN** a nightly candidate changes a committed source catalog or other configuration
- **THEN** publication is rejected as an out-of-scope tracked mutation

#### Scenario: Successful no-op

- **WHEN** no allowed file differs from the checked-out main
- **THEN** the run records a successful no-op without creating a commit

#### Scenario: Unexpected mutation

- **WHEN** an unrelated tracked file changes or an allowed file is deleted
- **THEN** publication is rejected

#### Scenario: Generated catalog refresh

- **WHEN** verified generated catalog bytes differ from the checked-out main
- **THEN** the README change is published with any changed packs in one commit

#### Scenario: Handwritten README mutation

- **WHEN** a candidate changes README content outside the generated section
- **THEN** publication fails even if structural verification succeeds

#### Scenario: Allowed file becomes a symlink or changes mode

- **WHEN** a candidate or a handed-off commit replaces an allowed file with a symbolic link, or changes an allowed file's mode
- **THEN** publication is rejected before any push or release write, and the release step reads no file through a link
