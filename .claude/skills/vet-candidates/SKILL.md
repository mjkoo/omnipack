---
name: vet-candidates
description: Vet candidate Android apps for inclusion in the omnipack packs, or sweep docs/watchlist.md to promote or drop waiting entries. Use when the user lists apps to consider adding, asks whether an app belongs in the pack, or a scheduled run asks for the weekly watchlist re-evaluation.
---

# Vetting pack candidates

omnipack ships two Obtainium import packs (single-screen and dual-screen). Every
app in them must be trackable by Obtainium and trustworthy enough to recommend.
This skill covers two modes:

- **Intake**: the user hands over a list of candidates (names, links, feed notes).
- **Watchlist sweep**: re-evaluate every entry in `docs/watchlist.md`, the
  scheduled weekly run.

Both modes end with the same output: additions in `config/extras.json`, an
updated `docs/watchlist.md`, and a report.

## 1. Pre-filter

Before researching anything, drop what needs no research:

- **Already in a pack.** Search `dist/single-screen.json` and
  `dist/dual-screen.json` by name and URL fragment, and `config/deny.json` for
  earlier rejections. Note near matches (a dual-screen fork of the candidate, a
  sibling build) rather than silently dropping them.
- **Obviously out of scope.** Paid store games, PC-only tools, ROM hacks or
  patches, homebrew for other consoles. These get a one-line reason in the
  report and nothing else.

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
   dual-screen-only `dualScreen: true` flag versus both packs).

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
  `dualScreen: true` only for dual-screen-only builds.
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
  one source.

Then run `uv run pack build` (regenerates `dist/` and `README.md`),
`uv run pack verify` and `uv run pytest`, and check that each new id appears in
the intended packs with no duplicate ids.

## 4. Maintain the watchlist

`docs/watchlist.md` holds every WAIT verdict. Each entry gives the name,
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
  `chore/watchlist-sweep-<date>` for a sweep), confirming the branch before each
  commit. Never commit on main. Stage files by name. Conventional commit with
  the co-author trailer.
- Do not push, open a PR or merge unless the request (or the scheduled task's
  prompt) explicitly authorizes it. A PR body carries a "## Specs" section
  ruling that specs are skipped: adding apps is configuration, not behavior.
- A sweep with nothing to change makes no branch and no commit; it reports
  that every entry was re-checked and still waits.
- The report lists, per candidate: verdict, canonical URL, package id, and a
  one-line reason; then the promotions, drops and owner questions.
- No device checks: never use ADB or test on a device as part of vetting.
- Plain hyphens only; no em or en dashes in anything written.
