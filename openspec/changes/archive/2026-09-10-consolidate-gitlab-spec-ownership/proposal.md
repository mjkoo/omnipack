## Why

Native GitLab behavior is specified both in a provider capability and in the
pipeline capabilities. Consolidate ownership after package-format reconciliation
so future adapter changes have one detailed contract to maintain.

## What Changes

- Move native GitLab identity requirements and their scenario into source-ingestion.
- Move GitLab release resolution requirements and all six scenarios into pack-verification.
- Replace repeated detailed paragraphs with references to the owning requirements.
- Retire the empty gitlab-app-sources capability through explicit archive metadata.
- Preserve every obligation, all runtime behavior, tests, configuration and generated outputs.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `source-ingestion`: Own the native GitLab identity contract.
- `pack-verification`: Own the detailed GitLab release resolution contract.
- `gitlab-app-sources`: Remove both requirements after moving them to their pipeline owners.

## Impact

Specification organization and verification documentation only. The runtime
GitLab adapter remains present and unchanged. The final main-spec inventory
contains nine capabilities. Existing historical archives remain intact.
