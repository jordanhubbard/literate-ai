# Historical optional-policy branch record

The following is the original PR #442 record, retained during release recovery.
The parser fix is already present under current `RELEASE-CLOSURE-001`. Its
proposed separate goal is historical context; the current release manifest and
lifecycle implementation pin remain unchanged. Earlier branch validation does
not establish combined source, installed, platform or release qualification.

### [ ] RELEASE-MANIFEST-001 — Preserve optional contribution manifest policy round trips

- **Priority:** P1
- **Owner:** framework release policy parser
- **GitHub issue:** [#441](https://github.com/jordanhubbard/literate-ai/issues/441)
- **Goal:** PROJECT.md Goal 1, reliable release-engineering policy.
- **Direction:** Fix upstream issue #441: omitted optional roadmap_goal_manifest must be accepted, including the parser own serialized default.
- **Conclusion:** Treat only the manifest field as optional; retain required milestone, unknown-key and relative-path validation. No downstream policy or installed SDK changes.
- **Depends on:** none
- **Completion prerequisites:** none
- **Implementation:**
  - [x] Parse the optional manifest separately before exact required-key validation.
  - [x] Add omitted, null, configured and invalid policy regression coverage.
- **Evidence:**
  - [x] Run maintained make python-check for contribution-policy and project-release tests, plus formatting and lint.
  - [x] Independently review the parser change and refresh its lifecycle driver pin through the maintained review command.
- **Validation:** 31 maintained local release tests pass, with formatting/lint clean. The first PR CI run exposed a stale lifecycle driver pin for the changed parser; the same refusal was reproduced locally. Independent source review confirmed the optional-field behavior and retained strict validation before supported re-pinning. Hosted confirmation and main integration remain pending.

- **Qualification:** Maintained `make python-check PYTHON_TEST_START_DIRECTORY=tests/e2e PYTHON_TEST_PATTERN=test*release*.py PYTHON_TEST_WORKERS=2` passed all 31 selected cases, including four new contribution-policy regressions. Changed Python files pass Ruff lint and format checks.
- **Next action:** Upstream review and integration; this source fix does not upgrade downstream SDKs.
