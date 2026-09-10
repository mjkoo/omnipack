## Context

See proposal.md for motivation. The package-format compatibility requirements
are already synchronized. No other active change holds a delta against these
capabilities. Pipeline capabilities are the established organizing boundary.

## Goals / Non-Goals

Give native ingestion and release verification one detailed owner each. Preserve
all obligations and scenarios, runtime modules, tests, configuration and exports.
No provider behavior, version policy or acceptance policy is changed.

## Decisions

Move both complete GitLab requirement blocks verbatim to the receiving specs.
Replace detailed duplicate paragraphs in the existing general requirements with
references to their new local owners, retaining their existing scenarios.
This avoids inventing a new source taxonomy or splitting every provider into
another capability. The general offline serialized-document requirements retain
independent structural checks; those checks are not duplicates of live resolution.

The ingestion summary retains explicit-setting precedence and the prohibition
on using HTML defaults. The moved native requirement retains URL case and depth,
manifest evidence, discovery limits, defaults and rendering identity. The moved
release requirement retains package formats, upload routes, supported settings,
release limits, error behavior, HTTP guarantees, credentials and evidence.

## Clause and scenario mapping

| Origin obligation | Surviving owner |
| --- | --- |
| Public HTTPS project, subgroup depth, case-sensitive path and existing URL comparison | source-ingestion: Public GitLab entries retain native source identity |
| Explicit manifest-backed package IDs and no expansion of generated discovery | source-ingestion: Public GitLab entries retain native source identity |
| GitLab defaults and rendered source identity | source-ingestion: Public GitLab entries retain native source identity; general pack-rendering hydration still applies |
| Explicit settings override defaults; no HTML defaults | source-ingestion: Every entry carries a supported source type |
| Aurora extra reaches both exports scenario | source-ingestion: Public GitLab entries retain native source identity, verbatim |
| Package extensions, name-or-path eligibility, name filter and upload syntax | pack-verification: GitLab release resolution includes uploaded description APKs |
| Numeric project route, API-order window, fallback and extraction | same detailed GitLab release requirement |
| Malformed metadata, no qualifying package, unsupported active settings and rate failures | same detailed GitLab release requirement |
| Shared timeouts, retry/deduplication/concurrency, exact-host credentials and evidence identity | same detailed GitLab release requirement, plus existing shared verification requirements |
| All six GitLab release scenarios | same detailed GitLab release requirement, verbatim |
| GitHub credential and HTML compatibility remain unchanged | pack-verification: Live checks honor a declared compatibility boundary |

## Risks / Trade-offs

A move can silently drop a clause or scenario. Compare both moved blocks verbatim
and account for every sentence removed from the two summary paragraphs. Preserve
all pre-existing scenarios in those modified summaries. Record the comparison in
a durable validation summary and have independent reviewers check it.

A retired capability can leave dangling references. Search living specs and docs
for operational references; preserve historical references in archived artifacts.
Keeping the old capability would avoid a path migration but retain split ownership.

## Migration Plan

Deliver the mapping and verification evidence before archive. Implementation is
documentation-only; main-spec relocation happens during sync after review. Use
explicit retirement metadata prescribed by the OpenSpec CLI before removal of the
last old requirement, preserving its safety checks. The final inventory has nine
capabilities and the same 81 total requirements. No consumer migration is needed.
Operational and on-device acceptance remain deferred until the branch settles.
