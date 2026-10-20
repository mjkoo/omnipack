# Tasks

## 1. Scoped credential in the HTTP client

- [ ] 1.1 Add an optional `credential` argument to `HttpClient.get` that sends an `Authorization` value as an unredirected header, update the module and class docstrings, and verify with new tests in `tests/test_http.py`: the header is present on the request, absent from the redirected request urllib builds, and absent when no credential is passed
- [ ] 1.2 Confirm every existing caller passes no credential, and verify that `uv run pytest tests/test_http.py tests/test_live_check.py` still passes unchanged

## 2. Forge health lookups

- [ ] 2.1 Create `src/omnipack/forge_health.py` with URL classification for `github.com/<owner>/<repo>` and `gitlab.com/<path>`, and verify with synthetic tests that other hosts and repository-less GitHub URLs are not forge targets
- [ ] 2.2 Implement the GitHub and gitlab.com lookups and release qualification: draft exclusion, prerelease opt-in, track-only, APK container extensions with `.zip` under `includeZips`, the asset date under `useLatestAssetDateAsReleaseDate`, date ordering and the 180-day boundary. Verify with synthetic tests over the fake transport, one per pack-cli health scenario: old APK release, 179-day fresh release, prerelease opt-in, track-only, rolling asset date, no qualifying release, and archived independently of stale
- [ ] 2.3 Make every lookup failure health-inconclusive with a reason: error status, retried status after retries, timeout, unexpected JSON shape, unparseable date and undecodable settings. Verify with synthetic tests that each gives an inconclusive result and never stale or archived
- [ ] 2.4 Send `Bearer <token>` only on `api.github.com` requests, and verify with a recording transport that project-page, gitlab.com and redirected requests carry no `Authorization`

## 3. Live check integration

- [ ] 3.1 Extend `check_live` with `now` and `github_token` parameters. Run the health lookup after each forge URL's reachability request unless that URL was unreachable, keep it within the shared budget, and add the `stale`, `archived` and `healthInconclusive` report lists in pack order. Verify with `tests/test_live_check.py` cases for the gone-project, other-host, budget-spent and exit-status scenarios
- [ ] 3.2 Extend `render_summary` and the CLI's printed output with the three new lists, HTML-escaped, and verify with a summary test that includes a name and a tag containing markup characters
- [ ] 3.3 Read `GITHUB_TOKEN` in the `check-live` CLI handler and pass it through, and verify with a CLI test that the token reaches the GitHub API request and an unset variable gives anonymous lookups
- [ ] 3.4 Update the `pack check-live` documentation in `docs/development.md` and `docs/source-generation.md` with the health lookups, the token and the report lists, and verify with `just check-links`

## 4. Alerts

- [ ] 4.1 Add the `live-check/stale/` and `live-check/archived/` prefixes and the emitter mapping in `scripts/alerts.py`, with titles and details as the design gives them, scoped when the report succeeded and kept out of `accounted`. Verify with `tests/test_alerts.py` cases for the health-findings scenario
- [ ] 4.2 Put both health keys in `unchecked` for health-inconclusive, unreachable and budget-unchecked URLs, and verify with tests that a rate-limited lookup leaves an open stale issue unchanged, that a muted stale issue is cleared by a run whose lookup finds a fresh release, and that the issue of a URL no longer in the packs is closed
- [ ] 4.3 Set `GITHUB_TOKEN: ${{ github.token }}` on the `pack check-live` step in `.github/workflows/source-catalog.yml`, leaving job permissions unchanged, and verify with `just lint-actions` and any workflow-shape tests in `tests/test_publication_workflows.py`
- [ ] 4.4 Document the stale and archived findings, their keys, muting a dormant project and the expected first-run issues in `docs/alerts.md`, and verify with `just check-links`

## 5. Integration

- [ ] 5.1 Run `just check-all` and verify that it passes
- [ ] 5.2 Run `uv run pack check-live` locally against the committed packs with a token, and verify that the stale and archived lists match the dormant upstreams observed on the device, apart from the curation fixes already made on their own branch
