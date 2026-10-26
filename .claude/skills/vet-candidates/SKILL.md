---
name: vet-candidates
description: Vet candidate Android apps for inclusion in the omnipack packs - a user's list, newly released projects found by discovery, the docs/watchlist.md sweep, or a new catalog arrival flagged by an uncategorized-family alert. Use when the user lists apps to consider, asks whether an app belongs in the pack, a scheduled run asks for the weekly sweep and discovery, or an omnipack-alert issue reports an uncategorized family.
---

# Vetting pack candidates

omnipack ships two Obtainium import packs (single-screen and dual-screen). Every
app in them must be trackable by Obtainium and trustworthy enough to recommend.
This skill covers four modes:

- **Intake**: the user hands over a list of candidates (names, links, feed notes).
- **Watchlist sweep**: re-evaluate every entry in `docs/watchlist.md`.
- **Discovery**: find projects released recently that no pack, denial or
  watchlist entry covers yet, so vetted additions land before the catalogs
  pick them up. The scheduled weekly run does discovery, then the sweep.
- **Arrival triage**: a catalog brought a new family into the packs and the
  nightly build raised a `build/uncategorized/<family>` alert. Vet the arrival
  and categorize or deny it (section 6).

Intake, sweep and discovery end with the same output: additions in
`config/extras.json`, an updated `docs/watchlist.md`, and a report.

## 1. Pre-filter

Before researching anything, drop what needs no research:

- **Already in a pack.** Search `dist/single-screen.json`,
  `dist/dual-screen.json` and `config/extras.json` (the packs lag merged extras
  until the next nightly) by name and URL fragment, `config/deny.json` for
  earlier rejections, and `docs/watchlist.md` (waiting and declined entries). Note near matches (a dual-screen fork of the candidate, a
  sibling build) rather than silently dropping them.
- **Obviously out of scope.** Paid store games, PC-only tools, ROM hacks or
  patches, homebrew for other consoles. These get a one-line reason in the
  report and nothing else.

## Discovery

Look for Android projects first released or first given an Android build
recently (since the previous weekly run, or the last two weeks when unsure):

- GitHub: repositories created or pushed recently with APK release assets in
  the pack's space - static recomps (N64Recomp, Xbox, GameCube and Wii U
  recomps), decomp-based native ports, emulators and emulator forks,
  frontends, handheld utilities (AYN Thor, Retroid, Odin). Search by topic and
  keyword, and check what established porters and emulator projects shipped.
- Community and press: r/EmulationOnAndroid, r/SBCGaming, r/AYNThor and
  r/RetroidPocket, portcove intake issues, and the port-news coverage that
  links Android builds. Reddit refuses direct requests from cloud sessions, so
  reach it through web search (`site:reddit.com/r/<subreddit> <terms>`) and
  follow the projects linked from the results.

Run every find through the pre-filter, then research and judge it exactly as an
intake candidate. Consider at most about ten new candidates per run, most
promising first; leave the rest for the next run rather than rushing them.
Discovery adds only clear passes. Anything borderline goes to the watchlist, or
to the report's owner questions when it is the owner's call.

## 2. Research each remaining candidate

Use subagents for breadth (about seven candidates per agent, run in parallel).
Research is read-only: `gh api`, `gh release list`, web search and fetch.

In a cloud session, `gh api` may be refused for repositories other than this
one. Do not ask for access to them; fall back in this order:

1. The unauthenticated REST API, for example
   `curl -s https://api.github.com/repos/<owner>/<repo>/releases?per_page=10`
   (rate limited, so batch the calls).
2. The release asset list for one tag, which the releases page loads lazily:
   `https://github.com/<owner>/<repo>/releases/expanded_assets/<tag>`. The
   releases page itself often omits asset names, so never conclude that a
   release has no APK from that page alone.
3. A shallow clone (`git clone --depth 1`) to read gradle files and manifests
   for the package id.

If a fact still cannot be established, say so in the report rather than
inferring it. Each candidate needs:

1. **Identity**: the canonical repository (follow redirects and transfers; an
   old URL that 301s means the entry uses the new one), author, what it is
   (native port, decomp, recomp, emulator or emulator fork, utility), license,
   whether source is published, and its relationship to any upstream.
2. **Trackability**: Obtainium tracks GitHub, GitLab and Codeberg releases,
   F-Droid, direct APK links and HTML pages linking APKs. CI artifacts, Google
   Drive, Mediafire, Discord and "coming soon" are not trackable. Record the
   latest releases' asset names, whether a release carries more than one APK,
   whether APKs ship inside zips, prerelease usage, and other release streams
   sharing the repository (data packs, drivers, config files).
3. **Freshness**: the newest release that carries an APK. Anything 180 or more
   days old raises a stale alert from `pack check-live`; that does not
   disqualify an app, but say when the alert will fire.
4. **Package id**: confirm from the repository (`applicationId` in the app's
   gradle file, including flavor or overlay gradle files that override the
   base one, or the manifest `package`). It must not collide with any id in
   either pack: Obtainium keys apps by id, so two entries with one id cannot
   coexist, and a fork reusing upstream's id cannot be offered beside it.
5. **Provenance and blast radius** (the bar, below).
6. **Fit**: required user-supplied data, dual-screen support (decides the
   `dualScreen: true` flag, and whether a single-scoped denial keeps the build
   out of the single-screen pack).

### The bar

- Closed source is acceptable with decent provenance. Open source or
  source-available code with a real track record passes. AI-assisted
  development is not disqualifying by itself.
- Weigh trust as provenance times reach. Flag unclear origin combined with
  account or credential access, all-files storage, accessibility services,
  Shizuku or root, or package installation. Explain what a sensitive permission
  is used for by reading the code before judging it (a self-updater that only
  installs its own checksummed release asset is benign).
- Suspicious signs: a brand-new account or organization with a single burst of
  commits, reuploaded binaries with no source, impersonation of an established
  project, releases with no downloads, a one-off fork far behind its upstream.
- Signals that help clear a project: stars, issues and outside contributors,
  download counts, press or community coverage, a real upstream it builds on, a
  small reviewable diff from upstream.
- Legal murk (reverse-engineered closed code, for example) is a takedown risk,
  not a malware risk. Surface it and let the owner decide.
- No requirement may exceed what Obtainium itself requires: no host, signing or
  agreement prerequisites of our own.

Verdicts: **ADD**, **WAIT** (would pass but is not trackable or mature yet;
state what would promote it), or **SKIP** (out of scope or rejected; one line).
Questions that are genuinely the owner's call (legal risk, a fork replacing an
established entry, a borderline high-reach app) go to the owner with the
background needed to decide, not as a bare question.

## 3. Write additions

Additions are entries in `config/extras.json`, inserted before the omnipack
tracking entry. Follow the existing entries:

- `id` (confirmed package id), `url`, `name`, `author`, `categories`, and
  `dualScreen: true` only for dual-screen builds. A dual-screen extra still
  reaches the single-screen pack when its family has no baseline build, unless
  a single-scoped denial keeps it out.
- **Names** follow the pack style: the game first, the project in parentheses
  when the project name differs (`Halo: Combat Evolved (OpenCE)`).
- **Categories** use the approved taxonomy with upstream spellings: Emulator,
  Decomps/Recomps, PC Ports, Frontend, Utilities, Streaming, Track Only.
- **Settings stay at Obtainium defaults** unless the release shape requires
  otherwise. Add a filter only when a release carries more than one APK, and
  make it exclude the unwanted asset rather than name the wanted one, so an
  upstream rename surfaces as an install prompt instead of a silent fallback.
  Any setting combination beyond that gets a short paragraph in the "Policies"
  section of `docs/curation.md`.
- A user note in `docs/app-notes.md` only when the pack's own configuration
  changes what a user sees; never restate upstream requirements.
- Rejections need a `config/deny.json` denial only when a catalog actually
  brings the app in. Denials apply to every source; never write a rule scoped to
  one source. A denial without `packs` removes the app from both packs;
  `"packs": ["single"]` (or `["dual"]`) removes it from that pack only, for an
  app that belongs in one pack and not the other. The reason says why it does
  not belong there.

Then run `uv run pack build` (regenerates `dist/` and `README.md`),
`uv run pack verify` and `uv run pytest`, and check that each new id appears in
the intended packs with no duplicate ids. Never commit the rebuilt `dist/` or
README catalog: the nightly publishes them, and CI fails a PR that changes
them. Discard them with `git restore dist/ README.md` before committing, and
say in the PR body that the packs update at the next nightly.

## 4. Maintain the watchlist

`docs/watchlist.md` holds every WAIT verdict, and under "Declined" one line per
SKIP verdict for a project a later discovery could plausibly find again, so it is
not re-proposed every week. A declined app that changes materially (an Android
build appears, a package id conflict goes away) may be reconsidered. Each entry gives the name,
canonical URL, why it waits and what would promote it, stated as stable facts:
no counts, dates or other details that go stale quickly.

In a sweep, re-check each entry against its promotion condition, plus a fresh
provenance look (a project can change hands or go bad). Promote entries that now
meet the bar into extras and remove them from the doc; update the reason when
the situation changed; drop entries that are abandoned (archived, deleted, or
superseded by another candidate). Also check whether a waiting app has
meanwhile reached a pack through a catalog, and remove it from the doc if so.

## 5. Deliver

- Work on a branch off main (`feat/feed-additions-<date>` for intake,
  `chore/watchlist-sweep-<date>` for a sweep or discovery run, unless the
  request names a branch), confirming the branch before each
  commit. Never commit on main. Stage files by name. Conventional commit with
  the co-author trailer.
- Do not push, open a PR or merge unless the request (or the scheduled task's
  prompt) explicitly authorizes it. A PR body carries a "## Specs" section
  ruling that specs are skipped: adding apps is configuration, not behavior.
- A sweep or discovery run with nothing to change makes no branch and no
  commit; it reports what was re-checked and what was considered.
- The report lists, per candidate: verdict, canonical URL, package id, and a
  one-line reason; then the promotions, drops and owner questions.
- No device checks: never use ADB or test on a device as part of vetting.
- Plain hyphens only; no em or en dashes in anything written.

## 6. Arrival triage

An issue labeled `omnipack-alert` whose first body line is
`<!-- omnipack-alert-key: build/uncategorized/<family> -->` means a family in
the built packs has no category. Usually a catalog (RJNY, BBoi, Quiver or codm)
added an app that nobody has reviewed. The family is a normalized project URL
(`github.com/<owner>/<repo>`) or an `app:<label>` family from
`config/composition.json`.

1. Find the family's entries in `dist/*.json` and the app's project.
2. Vet it with section 2 and the bar, as any candidate.
3. If it clears, add a category for the family to the `categories` map in
   `config/composition.json`, keyed as the alert names it, using the taxonomy in
   section 3.
4. If its only builds are dual-screen builds (every codm arrival, for one), it
   reaches the single-screen pack too, so decide whether it belongs there. A
   build's kind shows in the family's `selections` in `.build/report.json` (an
   origin of `codm-generated`, or a dual winner with reason `dual-preferred`),
   or in its entry in `config/catalogs/codm.json` or `"dualScreen": true` in
   `config/extras.json`. When it is pointless or broken on one display (a
   second-screen panel, a companion that does not run the game, a mod that only
   draws on the second screen) or duplicates an app single already carries, add
   a single-scoped denial, `"packs": ["single"]`, with a reason, beside the
   category. Read its README or code for a single-screen layout or fallback
   before deciding it runs on one display. Denials are owner decisions: say so
   prominently in the PR body so the owner reviews it before merging.
5. If it fails the bar, add a `config/deny.json` record with a reason instead.
   Denials are owner decisions: say so prominently in the PR body so the owner
   reviews it before merging.
6. Build, verify and test as in section 3, then open a PR whose body links the
   issue. The PR carries only the category and any denial; the nightly rebuilds the
   packs and README. Do not close the issue: the next nightly build closes it when the
   warning stops.

Several uncategorized alerts open at once go into one PR. An issue already
closed, or a family already categorized on main, needs nothing.

