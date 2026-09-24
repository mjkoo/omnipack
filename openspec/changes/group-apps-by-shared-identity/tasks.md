## 1. Family formation

- [x] 1.1 Form families by shared identity in the composition policy, after exclusions and over
  the surviving candidates eligible for at least one variant: a transitive join on effective
  package id and on explicit family, assigning the family also to candidates at a `family`
  rule's projected key even when the ruled candidate drops out. No project URL join. Name each
  family by its explicit `app:` name or `package:<its one effective id>`, and fail when two
  explicit families join through a shared effective id, naming both families and the joining
  candidates. Report a removed candidate's exclusion under `package:<its own effective id>` or
  its explicit family. Verify with tests covering:
  - two repositories sharing one id, which form one family;
  - a rule-less candidate sharing an effective id with a candidate ruled into `app:x` at another
    URL, which joins `app:x`;
  - two explicit families joined through a shared effective id, which fails;
  - a candidate eligible for neither variant, ruled into `app:x` and sharing an effective id with
    a rule-less candidate from another source at a different URL, where the rule-less candidate
    forms `package:<id>` rather than `app:x`;
  - a denied rule-less candidate and a denied candidate ruled into `app:x`, whose exclusions are
    reported under `package:<its own effective id>` and `app:x`;
  - an `app:x` rule on an RJNY candidate eligible for no variant, a rule-less BBoi candidate at
    the same effective id and URL, and another eligible candidate ruled into `app:x`, where all
    eligible ones form `app:x` and a pin naming `app:x` works.
- [x] 1.2 Remove the rendered-projection conflict error for candidates without a rule. Keep the
  rule-versus-rule projection agreement check. Verify with tests showing that a rule-less
  candidate sharing a projected key joins that family, that two rules projecting one key to
  different families still fail, and that an identity-only rule and an `app:` rule at one key load
  and join that family (only `family` rules project a family).
- [x] 1.3 Check pin families against formed families. Keep the parse-time pin-family check only
  for pins whose selector has an explicit `app:` projection; check every pin at build time
  against its candidate's formed family. A pin whose candidate is denied or eligible for no
  variant fails as a conflict with that exclusion, naming the pin and the denial or the
  ineligibility, before the build-time family comparison; a pin contradicting its selector's
  explicit projection fails at policy load first, whatever the denylist says. Verify with tests
  showing that a pin on a rule-less candidate that joins `app:x` through a shared effective id
  succeeds naming `app:x` and fails as wrong-family naming `package:<its id>`, that a pin naming
  `package:<id>` on a rule-less candidate fails with the denial identified, not as wrong-family,
  once a denial removes it, and likewise with the ineligibility identified when its source makes
  it eligible for no variant, and that a pin naming `app:two` on a denied candidate projected to
  `app:one` fails at policy load naming the pin and `app:one`.

## 2. Selection

- [x] 2.1 Group selection by the new families and remove the distinct-family package check.
  Verify with these tests:
  - a lower source repeating a package id from another repository loses whole and appears as
    considered;
  - dual preference still outranks precedence inside a joined family;
  - `test_denials_and_package_collisions_see_the_corrected_package_id` now expects the rule-less
    candidate to lose whole to the higher source, and its corrected-id denial assertion is kept;
  - the distinct-families case in
    `test_cross_package_family_coverage_passes_and_package_collision_fails` (explicit `app:x` and
    `app:y` sharing one effective id) now expects the joined-explicit-families failure naming both
    families and both selectors.
- [x] 2.2 Make the failed build report identify each composition conflict: the family, target and
  selectors for tied candidates; both families and the joining candidates, with no target, for
  joined explicit families; the family and both entries for a family whose selected entries do
  not pair. Verify with the existing composition-diagnostics tests plus one report test for each
  of the latter two, each also asserting that prior diagnostics are preserved.
- [x] 2.3 After selection, require every family that publishes in both variants to pair its
  selected single and dual entries under the shared pairing function, and fail composition when
  they do not, naming the family and both entries and asking for a `family` rule on each selected
  entry that does not yet project the family. Depends on 3.1. Verify with an end-to-end build test
  where rules assign `app:x` only to RJNY ordinary `a` at URL X and RJNY ordinary `c` at URL W,
  extras supplies rule-less baseline `a` at URL Y and BBoi rule-less dual-preferred `c` at URL V:
  the build fails with that error naming `app:x`, `a` at Y and `c` at V, and passes, with offline
  verification passing too, once rules assign both selected entries `app:x`.

## 3. Offline pairing

- [x] 3.1 Add one pairing function shared by offline verification, the README catalog and the
  build's post-selection check. It runs two whole passes: the same package id, then the same
  explicit family through projections among entries still unpaired. No pass pairs entries whose
  projections name different explicit families. A pair is labelled by its explicit family or
  `package:<shared id>`. Verify with unit tests for each pass, the same pairs when either
  variant's order is reversed, entries with different explicit families sharing an id left
  unpaired, and a same-id pair where one entry has an identity-only rule pairing in the id pass.
- [x] 3.2 Switch offline verification to the pairing: remove `duplicate_family`, add a finding for
  an explicit family projected onto more than one entry within a variant naming the entries, keep
  the entry-level `duplicate_id` finding as the only report of a repeated package id, leave the
  entries of a repeated package id or a repeated explicit family out of pairing and coverage in
  both variants, make coverage single entries without a dual pair, and leave pin, denial and
  stale-overlay checks unchanged. Verify with `tests/test_offline.py` cases (where the offline
  composition tests live) for:
  - an explicit family repeated within a variant rejected;
  - single `a` and `b` both projected `app:x` with dual `c` projected `app:x`, and single `c`
    projected `app:x` with dual `a` and `b` both projected `app:x`, each yielding only the
    repeated-family finding and no coverage gap, in both entry orders;
  - a single entry sharing an id with a dual entry of a different explicit family reported as a
    coverage gap;
  - single `[a, a]` with dual `[a]`, and single `[a]` with dual `[a, a]`, each in both entry
    orders, reporting one `duplicate_id` and no `dual_coverage_gap`, with
    `test_raw_ids_survive_other_entry_errors` (a duplicated denied id reporting both
    `duplicate_id` and `denied_output_present`) still passing;
  - a denied entry inside an explicit family repeated within a variant still reporting the denial,
    since the denial check iterates entries rather than a map keyed by family label;
  - an entry violating both package-id and explicit-family uniqueness reporting both findings.
- [x] 3.3 Switch README catalog generation to the pairing. Fail generation on a repeated package id
  or explicit family within a variant. Verify with catalog tests for the repeated-id and repeated-family failures and for entries of
  different explicit families sharing an id as separate rows, for a single entry projecting a
  family that pairs by package id with an unprojected dual entry while another dual entry
  projects that family, rendering two rows under that label with both dual configurations and
  a deterministic order, and with the README up-to-date
  check in `pack verify`.

## 4. Regression

- [ ] 4.1 Confirm unchanged outputs: the frozen codm baseline fixture reproduces its golden exports
  and family winners byte for byte. Rebuilding from the current configuration yields
  byte-identical `dist/` exports and README. Verify with the fixture test suite and a full
  `pack build` plus `pack verify`.
- [ ] 4.2 Run the full test suite, lint and type checks and confirm they pass.
