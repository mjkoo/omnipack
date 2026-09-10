## MODIFIED Requirements

### Requirement: Every entry carries a supported source type

Obtainium reads a per-app source type that decides which settings keys an app
has, so every entry must carry one before it can be rendered. An entry ingested
from an upstream catalog SHALL take the source type that upstream's record
declares for it. An extras entry with an explicit `overrideSource` SHALL use
that declared source type before URL-based inference. Only when an extras entry
omits `overrideSource`, or for a generated entry, SHALL the system derive the
source type from the URL: a github.com repository takes GitHub and any other
URL takes HTML. The pack SHALL support GitHub, HTML and GitLab, and SHALL fail
the build with an error naming the entry and offending value for any other
source type, including a malformed explicit declaration rather than silently
falling back to URL inference.

A GitLab entry SHALL use a public HTTPS gitlab.com project URL with a namespace
and project, optionally including subgroups (at most 21 path components in total). The system SHALL reject GitLab
entries with another host, scheme or missing project path, preserve the full
case-sensitive project path, and hydrate committed GitLab settings defaults
when rendering. Explicit settings SHALL override defaults. Native GitLab
selection SHALL NOT route through HTML defaults or expand generated GitHub
package-id discovery to other hosts.

#### Scenario: Upstream record declares a source type

- **WHEN** an upstream entry's record declares the HTML source type
- **THEN** the ingested entry carries the HTML source type

#### Scenario: An entry with no upstream record derives its source type

- **WHEN** a generated entry or an extras entry without `overrideSource` addresses a github.com
  repository
- **THEN** it carries the GitHub source type, while an entry addressing any
  other URL carries the HTML source type

#### Scenario: Unsupported source type

- **WHEN** an upstream or extras entry declares a source type other than GitHub, HTML or GitLab
- **THEN** the build fails with an error naming that entry and that source type

#### Scenario: Explicit GitLab declaration takes precedence over URL inference

- **WHEN** an Aurora extra declares `overrideSource: GitLab` and `https://gitlab.com/AuroraOSS/AuroraStore`
- **THEN** ingestion retains GitLab, and rendering uses GitLab defaults and preserves explicit settings in both variants instead of selecting HTML

#### Scenario: Native GitLab URL is outside the supported boundary

- **WHEN** an entry declares GitLab with a non-HTTPS URL, a host other than gitlab.com or no namespace/project path
- **THEN** the build fails with the entry and invalid URL identified
