# Historical release closure: 0.10 recovery

- **Status:** historical
- **Owning queue item:** [RELEASE-CLOSURE-001](../../roadmap/active-work.md#release-closure-001-make-release-closure-executable-and-continuous)
- **Completion / archival evidence:** [Historical reconciliation](../../../verification/historical-release-closure-reconciliation.json); this preserves a publication-proof gap and is not a blanket completion claim.

The following text preserves the former execution queue verbatim. Its commands
and unchecked 0.10 candidate/publication actions are historical, not instructions
for the current release. Original source commits and the imported marker tags are
different identities. The three recovered implementations are established on the
original 0.10.1 line; later operator-adoption document publication remains unproven.
Current assurance continues under the linked owner and the current release manifest.

### [~] RELEASE-CLOSURE-001 — Make release closure executable and continuous

- **Priority:** P0
- **Release target:** 1.1.0
- **Previous release target:** 0.10.0
- **Owner:** release-project skills, release policy, release CLI, publication adapters, and release gates
- **Direction:** For 0.10.0, turn the 0.9.0 omissions into executable release policy: every major or minor release must regenerate, validate, preflight, publish, export back, and verify its terminal document pair; every release cycle must repeatedly inventory and disposition current tracker work, reviews, unmerged branches, worktrees, and external contributions before publication.
- **Conclusion:** The 0.9.0 failure was a split contract: prose required terminal collateral and broad peer review, but release plans, receipts, gates, and published verification bound neither. The release engineer must consume deterministic Python inventory and publication helpers, make semantic scope decisions, leave machine-readable milestone plus audit-comment dispositions, and repeat the sweep until no current-release blocker or unclassified contribution remains.
- **Depends on:** RELEASE-015
- **Next action:** Preserve the published `v0.10.0` tag, land the portable preflight-test fixture on `main`, and complete a versioned recovery containing the three intended 0.10 operator-adoption commits that the stale release line omitted. This late CI correction was applied before queue recording as reversible emergency containment after the exact-head matrix exposed the invalid fixture.
- **Implementation:**
  - [x] Add an accepted ADR and release policy for release-class derivation, required collateral, authenticated publication preflight, exact publication receipts, and continuous contribution disposition.
  - [x] Add Python-owned release contribution inventory and validation covering open issues, open reviews, remote branches, attached worktrees, milestones, durable release-disposition comments, and exact-head branch-lifecycle markers for GitHub and GitLab tracker contracts.
  - [x] Bind the current contribution sweep and required major/minor collateral receipt into release planning, prepared-candidate checking, publication, and post-publication verification without requiring live credentials on verification workers.
  - [x] Make the document-pair publisher preflight both stable resources and the explicit active account before either mutation, support idempotent recovery, export accepted remote state back to local authority, and emit release-bound hashes and resource identities.
  - [x] Update release-project, evidence, verification, presentation, tracking, and user-work skills plus Make targets and generated template copies so the virtual release engineer follows one executable loop.
  - [~] Repair 0.10.0 packaging metadata drift and continuously triage newly discovered regressions or blocking contributions into 0.10.0, deferring the rest with explicit next-cycle annotations until the release closes.
  - [~] Recover the premature stable cut without rewriting `v0.10.0`: the published tag is rooted at `03d3257e`, while intended 0.10 commits `ce88a6d8`, `2f4a34a1`, and `4b739a92` remained on `main`.
  - [x] Replace the project-index preflight tests' fabricated `/project` root with a real platform-native temporary directory while retaining strict production path resolution.
  - [x] Enforce in Python that a first stable initial, major, or minor candidate contains the live remote default branch throughout plan, prepare, check, and publish; keep patch selection independent of unrelated later trunk work.
  - [x] Derive checked-in Homebrew metadata from one Ruby version constant, declare it as a release version mirror, and restore its 0.11.0 value after the automatic default-branch version advance so patch preparation can update it atomically.
  - [x] Persist repair-gate completion in global execution order, invalidate anything other than the exact current fail-fast prefix, and require a clean follow-up pass after repaired completion before accepting release evidence.
  - [x] Treat an attached clean default-branch checkout as release authority when a
        patch is planned from a linked `release/*` worktree, rather than requiring a
        contribution disposition for `main` that branch enumeration intentionally
        excludes.
  - [x] Use a platform-native absolute synthetic executable in the Codex
        unauthenticated-status regression so Windows exercises the authentication
        probe and no-model-request invariant instead of failing fixture construction.
- **Evidence:**
  - [x] Contract, parser, policy, tracker-adapter, contribution-inventory, publication-preflight, partial-failure, receipt, release-plan, prepare/check/publish/verify, and generated-template parity tests pass in focused suites.
  - [~] A no-write dry run inventories this repository current issues, reviews, unmerged branches, and worktrees; unresolved items fail closed. Tracker dispositions and exact-head lifecycle markers are being bound before the final repeated sweep.
  - [x] Remote tag, release, wheel, ancestry, and changelog inspection proves that stable `v0.10.0` omitted the final operator-adoption commits; the tag remains immutable.
  - [ ] The focused project-index preflight regression, full Python gate, and fresh exact-head cross-platform CI pass with the portable fixture.
  - [x] Release-plan contract tests reject a stale first stable line at plan, prepare, check, and publish while accepting a selective patch line; historical verification remains valid after the default branch advances, and release preparation atomically renders an indented quoted-constant package mirror while skill/template parity plus the Homebrew renderer test pass.
  - [x] Inserted prerequisites and cross-pin gate reordering force a restart; a successful repaired run exits with rerun-required status 2, and only the subsequent gate-one pass exits 0.
  - [x] The linked-release-worktree regression reproduces the false unresolved `main`
        result before the classifier correction and passes afterward; the live 0.10.1
        sweep now classifies `main` only by its actual worktree state. The Windows CI
        traceback identifies the POSIX-only `/tools/codex` fixture before the
        authentication call, and the focused operator-adoption suite passes with a
        host-native absolute path.
  - [ ] The 0.10.0 document pair validates locally, publication preflight reports the active account and both resource capabilities before mutation, authenticated publication and export-back produce an exact receipt, and post-publication verification proves the bound artifacts.
  - [ ] Focused checks pass first, then release-relevant gates and exact-head CI pass for the 0.10.0 candidate.
