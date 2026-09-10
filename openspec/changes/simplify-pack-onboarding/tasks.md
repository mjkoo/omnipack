## 1. Consumer documentation

- [ ] 1.1 Reorder README with device-labeled raw downloads directly below the title and prominent numbered installation steps; verify instructions against supported Obtainium UI/source and inspect rendered Markdown, including the distinction between import and installation.
- [ ] 1.2 Convert credits into bullets preserving all source links; move development/build/verification guidance to `docs/development.md`, add `docs/README.md`, and replace root development content with a brief Contributing link; verify relative links and that all moved guidance remains accessible.
- [ ] 1.3 Document manual removal of the previously imported RJNY tracker and the investigated self-tracking follow-up in curation docs, updating project context as needed; verify claims match cited Obtainium source and do not imply automatic re-import or completed device validation.

## 2. Schedule and curation

- [ ] 2.1 Change nightly schedule to 03:00 America/New_York, update publishing documentation and the existing workflow assertion to check both cron and timezone; verify the workflow test passes and publication guards remain intact.
- [ ] 2.2 Exclude tracker id `904332840` through the denylist for both variants; add a regression using upstream input containing the tracker and an ordinary eligible RJNY app, proving tracker removal across refreshes while ordinary ingestion remains intact.
- [ ] 2.3 Run the normal build to regenerate packs and catalog; inspect the diff for absent tracker in both variants and catalog, preserved attribution, and separately identified upstream drift. Verify unchanged README prose around the generated markers survives regeneration.

## 3. Integrated validation

- [ ] 3.1 Run `just check-all` and `uv run pack verify`; verify all required checks pass and the generated catalog agrees with both pack files.
- [ ] 3.2 Run metadata-only live verification on regenerated candidates using configured credentials; inspect fresh evidence and record any external blockers without claiming a passed check or device acceptance.
- [ ] 3.3 Verify implementation against all delta scenarios, including rendered documentation and schedule semantics; complete project review gates and sync the deltas when archiving so observable behavior and specifications land together on the implementation branch.
