# Historical RELEASE-016 cut preparation

- **Status:** historical
- **Owning queue item:** [RELEASE-016](../../roadmap/active-work.md#release-016-prepare-the-080-rc1-cut-from-main)
- **Completion / archival evidence:** [Current release authority](../../../literate.project.json) and [published 1.3.1](https://github.com/jordanhubbard/literate-ai/releases/tag/v1.3.1) supersede the literal old cut instructions; original unchecked evidence remains unverified.

The literal 0.8.0-RC1 execution instructions below were archived as superseded
during the 1.4 delivery review. They preserve historical evidence and are not
current branch, worktree or publication instructions. Current release authority
is 1.4.0; actual published 1.3.1 metadata is independently recorded in the review.
A later published version does not prove the old RC plan or its review succeeded.

The optional upgrade obligation remains with RELEASE-017 and current installed
upgrade acceptance under SDLC-001 and PROJECT-LAYOUT-001. Current exact-release
gates remain with RELEASE-CLOSURE-001 and RELEASE-INTEGRATION-005. No current
release goal, deferral, acceptance requirement or release target changes here.

The original section follows unchanged, including every unchecked evidence item.

### [ ] RELEASE-016 — Prepare the 0.8.0-RC1 cut from `main`

- **Release target:** 1.1.0

- **Priority:** P0 (0.8.0 break-glass)
- **Owner:** default-branch landing queue, `src/literate_ai/cli/` diagnostics,
      release gates, `litai release plan/prepare`
- **Direction:** User-directed: prepare a `0.8.0-RC1` release. The work happens
      on `main`, but `main` is explicitly not release-ready: the local installed
      `litai` launcher fails to import (`ImportError: cannot import name
      'debug_diagnostics' from 'literate_ai.diagnostics'`) because
      `cli/source_to_specification.py` imports a symbol main's `diagnostics.py`
      does not define. All open roadmap items and branches must be landed in the
      correct order before planning the cut.
- **Conclusion:** Branch reconciliation (2026-08-30) found exactly one unmerged
      branch head: `feat/cli-sdlc-debug` (34 commits ahead of `main`, 0 behind)
      which already contains the three identical worktree branches
      `feat/cache-005-007-leftovers`, `feat/skill-dep-workflow-leftovers`, and
      `feat/spec-refinement-001-pi-service` (all at `d41c9f5b`) and repairs the
      `debug_diagnostics` inconsistency. `pr-197` is stale: SAMPLE-PIN-001
      records it closed without merge and its unique commit `78989809` is
      already contained in `feat/cli-sdlc-debug`. Merge
      `feat/cli-sdlc-debug` into `main` (merge-tree is conflict-free), delete the
      contained branches and their worktrees, reinstall the local launcher from
      source, then close remaining gates before `litai release plan`.
- **Depends on:** landed 0.8.0 catalog merges on `main` (`390cc7ec`);
      RELEASE-017 is explicitly deferred from the 0.9.0 gate
- **Implementation:**
  - [x] Record this item; merge `feat/cli-sdlc-debug` into `main`.
  - [x] Remove worktrees and delete contained branches
        (`feat/cache-005-007-leftovers`, `feat/skill-dep-workflow-leftovers`,
        `feat/spec-refinement-001-pi-service`, `pr-197`).
  - [x] Reinstall the local `litai` launcher from the merged source and verify
        `litai verify` / `litai project tracker inspect` run clean.
        `litai version check` and `litai project validate` both green.
        `litai verify` passes authority; receipt remains stale until
        the release gate produces one.
  - [x] Fix CLI inconsistencies discovered during gate run:
        command-reference missing `litai project guidance` and
        `litai release merge-pr`; doc-toolchain `.venv` fallback when
        `OBJ_DIR` is explicit; v1 wire-contract test missing
        `repository_policy` v2-only field drop.
  - [x] Close remaining repository gates (`python-check`, lint, format)
        on the merged `main`. `make python-check` passes 3041 tests with
        21 skips (2026-08-30, session `rc1-prep`). `make lint` and
        `make format-check` pass.
  - [ ] Run the optional RELEASE-017 upgrade smoke when that compatibility work is
        scheduled.
  - [ ] `litai release plan --version 0.8.0rc1` and review the plan.
- **Evidence:**
  - [x] Merge commit on `main` containing the full 34-commit stack (`3130bf48`).
  - [x] `litai version check` and `litai project validate` green from the
        installed launcher on the prepared tree (`0d75a25e`).
  - [x] `make python-check` passes 3041 tests; `make lint` and
        `make format-check` pass; `make skills-check` passes.
  - [ ] Release plan produced and reviewed.

<!-- end-preserved-release-016 -->
