# Proposal

## Why

The build and source generation read only upstream lists, so nothing notices
when a published pack entry's project disappears. A deleted or private
repository stays in the packs until a user's Obtainium fails to update it. A
single request per project URL detects that on hosts that answer a missing
project with 404 or 410, without the release or APK inspection the generator
dropped for its complexity. A host that redirects an anonymous request for a
missing project to a sign-in page is detected only as far as that page's final
status allows: the project is inconclusive when the page answers an error
status (gitlab.com answers 403) and is not detected at all when it answers 2xx.

## What Changes

- New `pack check-live` command. It requests each distinct project URL in the
  committed packs once, following redirects. A final success (2xx) status marks
  the project reachable and leaves it out of the report; an HTTP 404 or 410
  marks it unreachable; any other outcome (another error status such as 403,
  429 or 5xx, a timeout or a connection error) is inconclusive. The check is the same for every host and inspects no releases,
  assets or archive state.
- Each request carries the request headers the pack entry declares in its
  `requestHeader` setting, as Obtainium does, or omnipack's default user agent
  when it declares none. dolphin-emu.org answers 403 to anything but the
  `User-Agent: Obtainium/1.0` its entry declares, so this checks it with no
  host rule.
- An inconclusive reason names its cause: the HTTP status the last attempt
  received, otherwise the failure's message, so a rate limit and a timeout read
  differently.
- The command stops starting requests after a 20-minute budget and reports
  each URL not yet checked as inconclusive, so a slow host cannot outrun the
  job's 30-minute timeout.
- Every invocation writes a report under `.build/live-check/`, on success and
  failure alike, recording its status, the error on failure, and the
  unreachable and inconclusive URLs with their reasons. The command exits
  nonzero when a project is unreachable, the packs cannot be read, or the
  report cannot be written. It never writes committed files.
- The daily source catalog workflow gains a read-only job that runs
  `pack check-live` against main's committed packs, retains its report and
  lists the unreachable and inconclusive URLs in the run summary. The run ends
  failed when a project is unreachable, so the owner is notified. It changes no
  branch, PR or committed file.
- Retires nothing. Denial stays owner-only: the owner reads the report and adds
  any deny record by hand.

Estimate: 2 added requirements with 12 scenarios; about 160 implementation
lines (the command, request headers in `HttpClient` and the workflow job);
about 250 test lines.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `pack-cli`: adds the `check-live` command.
- `source-generation`: the daily source catalog workflow runs `pack check-live`
  and reports its findings without proposing anything.

## Impact

- Code: a new `src/omnipack/live_check.py`, `cli.py`, and `http.py` (request
  headers).
- Workflows: `.github/workflows/source-catalog.yml` gains the check job.
- Docs: `docs/source-generation.md` (the scheduled check and how the owner acts
  on it) and `docs/development.md` (the command).
- Network: about 150 unauthenticated GET requests a day, mostly to
  github.com.
