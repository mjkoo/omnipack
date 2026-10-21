# Tasks

## 1. Scoped credential in the HTTP client

- [ ] 1.1 Add an optional `credential` argument to `HttpClient.get` that sends an `Authorization` value as an unredirected header, update the module and class docstrings, and verify with new tests in `tests/test_http.py`: the header is present on the request, absent from the redirected request urllib builds, and absent when no credential is passed
- [ ] 1.2 Confirm every existing caller passes no credential, and verify that `uv run pytest tests/test_http.py tests/test_live_check.py` still passes unchanged

## 2. Forge health lookups

- [ ] 2.1 Create `src/omnipack/forge_health.py` with URL classification for `github.com/<owner>/<repo>`, and verify with synthetic tests that other hosts, gitlab.com project URLs included, and repository-less GitHub URLs are not forge targets, and that a GitHub releases-page URL is one
- [ ] 2.2 Implement the GitHub lookups and release qualification: draft exclusion, prerelease opt-in, track-only, APK container extensions with `.zip` under `includeZips`, the asset date under `useLatestAssetDateAsReleaseDate`, date ordering and the 180-day boundary, dropping drafts and non-opted prereleases before parsing or sorting dates. Verify with synthetic tests over the fake transport, one per pack-cli health scenario: old APK release, 179-day fresh release, prerelease opt-in, track-only, rolling asset date, no qualifying release, and archived independently of stale; plus a test where a draft with a null `published_at` sits beside a fresh APK release and the result is fresh
- [ ] 2.3 Make every lookup failure health-inconclusive with a reason: error status, retried status after retries, timeout, unexpected JSON shape, unparseable date and undecodable settings. Verify with synthetic tests that each gives an inconclusive result and never stale or archived
- [ ] 2.4 Send `Bearer <token>` only on `api.github.com` requests, and verify with a recording transport that GitHub project-page and other-host project-page requests carry no `Authorization`, and that on the API request it sits in `unredirected_hdrs` and not in `headers`

## 3. Live check integration

- [ ] 3.1 Extend `check_live` with `now` and `github_token` parameters, and have each live-check target carry the first entry's `name` alongside its settings so every stale, archived and health-inconclusive result records it. Run the health lookup after each forge URL's reachability request unless that URL was unreachable, keep it within the shared budget, and add the `stale`, `archived` and `healthInconclusive` report lists in pack order. Update the `live_check.py` module and `Target` docstrings, which say the check is the same for every host. Verify with `tests/test_live_check.py` cases for the gone-project, other-host, gitlab.com, budget-spent and exit-status scenarios, a project page answering 2xx whose repository is archived and stale and is listed as both, and a project page answering 2xx whose GitHub release lookup is rate limited and is listed as health-inconclusive with its reason
- [ ] 3.2 Extend `render_summary` and the CLI's printed output with the three new lists, HTML-escaped, and verify with a summary test that includes a name and a tag containing markup characters
- [ ] 3.3 Read `GITHUB_TOKEN` in the `check-live` CLI handler and pass it through, and verify with a CLI test that the token reaches the GitHub API request and an unset variable gives anonymous lookups
- [ ] 3.4 Update the `pack check-live` documentation in `docs/development.md` and `docs/source-generation.md` with the health lookups, the token and the report lists, and verify with `just check-links`

## 4. Alerts

- [ ] 4.1 Add the `live-check/stale/` and `live-check/archived/` prefixes and the emitter mapping in `scripts/alerts.py`, with titles and details as the design gives them, scoped when the report succeeded and kept out of `accounted`. Verify with `tests/test_alerts.py` cases for the health-findings scenario and for a URL whose page answers HTTP 403 and whose health lookup is rate limited, which raises the 403 finding and leaves its stale and archived issues unchanged
- [ ] 4.2 Put both health keys in `unchecked` for health-inconclusive, unreachable and budget-unchecked URLs, and verify with tests that a rate-limited lookup leaves an open stale issue unchanged, that a muted stale issue is cleared by a run whose lookup finds a fresh release, and that, for a URL no longer in the packs, both an open stale issue and an open archived issue are closed as completed and a muted stale or archived issue is marked closed as completed with a comment naming the run
- [ ] 4.3 Set `GITHUB_TOKEN: ${{ github.token }}` on the `pack check-live` step in `.github/workflows/source-catalog.yml`, leaving job permissions unchanged, and verify with `just lint-actions` and an updated live-check job test in `tests/test_publication_workflows.py`: the steps carrying `env` are exactly the check-live and emit steps, the check-live step's env is exactly the token, neither job nor workflow `env` defines `GITHUB_TOKEN`, and permissions stay `contents: read`
- [ ] 4.4 Document the stale and archived findings, their keys, muting a dormant project and the expected first-run issues in `docs/alerts.md`, and verify with `just check-links`

## 5. Integration

- [ ] 5.1 Run `just check-all` and verify that it passes
- [ ] 5.2 Run `uv run pack check-live` locally against the committed packs with a token, and verify that the report lists stale and archived GitHub URLs and no URL is health-inconclusive for a rate limit
