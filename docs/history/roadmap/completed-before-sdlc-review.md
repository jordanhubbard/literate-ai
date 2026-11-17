# Completed roadmap evidence before the SDLC review

- **Status:** historical
- **Owning queue item:** [SDLC-001](../../roadmap/active-work.md#sdlc-001-make-existing-repository-delivery-the-primary-14-adoption-path)
- **Completion / archival evidence:** [Review and reconciliation record](../../../verification/existing-repository-review.json)

These completed items were archived from the active queue during SDLC-001.
Their original completion claims and limitations are retained as history. Archival
does not requalify them on the current source. Current release-manifest goals and
items with unchecked acceptance retain their full active entries. Compact active
entries preserve IDs, anchors and dependency references.

## Archived items

### [x] ADOPTION-001 — Make operator adoption the post-0.9.0 product headline

- **Priority:** P0 (0.10.0 headline)
- **Release target:** 0.10.0
- **Owner:** root onboarding, CLI operator surface, and convert authority metadata
- **Detailed roadmap:** [Operator adoption program](../../roadmap/operator-adoption.md)
- **Direction:** After 0.9.0 is tagged, spend the next numbered line on being
      used: status, onboard create/adopt, a tested first hour from a wheel,
      visible convert stages, and a readable queue.
- **Conclusion:** Record a version-free operator-adoption program.
      STATUS/ONBOARD/GOLDEN/BROWNFIELD wait on published `v0.9.0`. QUEUE-HYGIENE
      may proceed in parallel. Do not absorb this program into
      RELEASE-0.9-CUT-001. No second planner, daemon, or IDE.
- **Depends on:** none
- **Next action:** Complete. Preserve the installed-wheel create/adopt journey as a
      release gate and continue the release closure loop in RELEASE-CLOSURE-001.
- **Implementation:**
  - [x] Author docs/roadmap/operator-adoption.md with ordered delivery and an
        explicit out-of-0.9.0 gate
  - [x] Point PROJECT.md current work and docs/README.md at the program
  - [x] Keep child implementation of STATUS/ONBOARD/GOLDEN/BROWNFIELD gated on
        published v0.9.0; `v0.9.0` is tagged
  - [x] Close this item only when every child item is closed with its evidence
- **Evidence:**
  - [x] Program file has the required lifecycle header and links this item
  - [x] PROJECT.md names operator adoption as current post-0.9.0 work
  - [x] Child IDs STATUS-001, ONBOARD-001, GOLDEN-PATH-001,
        BROWNFIELD-STATE-001, and QUEUE-HYGIENE-001 exist
  - [x] 0.9.0 release evidence does not depend on this program landing;
        children name RELEASE-0.9-CUT-001 as a prerequisite
  - [x] STATUS-001, BROWNFIELD-STATE-001, ONBOARD-001, GOLDEN-PATH-001, and
        QUEUE-HYGIENE-001 are closed; the exact clean 0.10.0 wheel proves both
        operator entry paths without importing the checkout

### [x] QUEUE-HYGIENE-001 — Archive completed queue items and reconcile the open tracker

- **Priority:** P1 (maturity; closed)
- **Release target:** 0.10.0; did not block `v0.9.0`
- **Owner:** docs/roadmap/active-work.md, PROJECT.md completeness, and GitHub tracker
- **Detailed roadmap:** [Operator adoption program](../../roadmap/operator-adoption.md)
- **Direction:** The resumption queue and PROJECT.md completeness lag the catalog,
      so agents cannot see current work. Open GitHub issues also lack matching
      queue items.
- **Conclusion:** Archive substantial closed programs to
      `docs/history/roadmap/`, refresh PROJECT.md completeness against the
      current Flavor/Component inventory, and file a queue item for each open
      GitHub issue that has none. Do not delete Git history. This sweep is the
      planning-pass remainder from 2026-09-04.
- **Depends on:** none
- **Next action:** Done. Completed programs are under `docs/history/roadmap/`.
      PROJECT.md completeness matches HEAD. Open GitHub issues now cite queue
      items. Do not mass-delete checked items from this file.
- **Implementation:**
  - [x] Move substantial completed programs out of `docs/roadmap/` into
        `docs/history/roadmap/` with historical lifecycle headers
        (release-branching, coverage-gap, 0.7.0 evidence, SCXML/DMN designs,
        LOW-DBC examples, SCXML trace spike)
  - [x] Refresh PROJECT.md completeness so language/build/OS/package counts and
        current work match HEAD (8 language, 5 build, 3 OS, 8 package,
        7 inheritable Components)
  - [x] Reconcile open GitHub issues without queue items, including #309, #308,
        #307, #306, #305, #301, #296, #295, #286, #283, #280, and #279
- **Evidence:**
  - [x] PROJECT.md completeness lists the current inheritable Flavor/Component
        catalog rather than the stale v0.3.0 counts
  - [x] Every open GitHub issue cites a queue item: #309 STANDARD-REBIND-001,
        #308 UPSTREAM-ISSUE-FIRST-001, #307 APP-SETTINGS-001, #306
        UPDATE-LOCAL-ROUTING-001, #305 CONVERT-PARITY-001, #301
        INIT-CONVERT-FORCE-001, #295/#296 OBSERVE-HTML-001, #286
        WORKER-GIT-CRED-001, #283 CONVERSION-UPDATE-VARIANT-001, #280
        LIBRARY-ARTIFACT-001, #279 SUBMODULE-ORCH-001; #251 remains
        RELEASE-017/GOLDEN-PATH-001; #83–#86 remain CI-SHARD-001/CI-IMPACT-001
  - [x] Active-work front matter names the 0.10.0 operator-adoption headline

### [x] STATUS-001 — Expose operator status and doctor as the repeat-use front door

- **Priority:** P0 (0.10.0 operator front door)
- **Release target:** 0.10.0
- **Owner:** litai CLI operator surface over existing init, convert, lock,
      receipt, and host-path services
- **Detailed roadmap:** [Operator adoption program](../../roadmap/operator-adoption.md)
- **Direction:** Repeat operators need one screen for host tools, coding-CLI
      auth, project versus convert state, stale locks, last receipt, and the
      next verb.
- **Conclusion:** Add `litai status` with doctor as the host-preflight view of
      the same typed contract. TTY and `--json` share one envelope. Reuse
      existing services. Do not add a new authority store. Convert stage comes
      from BROWNFIELD-STATE-001 once that field exists.
- **Depends on:** RELEASE-0.9-CUT-001, ADOPTION-001
- **Next action:** Complete. Keep the composed contract and coding-CLI inspection
      model-free as host integrations evolve.
- **Implementation:**
  - [x] Define a versioned operator-status contract over existing init,
        convert-plan, lock, receipt, and host-path services
  - [x] Add litai status and a doctor host-preflight view with TTY prose and
        `--json`
  - [x] Report next verb and fail closed on missing project or ambiguous Git
        tracker state already owned by existing commands
- **Evidence:**
  - [x] Focused public-API tests cover JSON envelopes, TTY rendering,
        missing-project, and unauthenticated coding-CLI cases
  - [x] No new planner or durable store is introduced; mutators remain init,
        convert, lock, and receipt commands

### [x] BROWNFIELD-STATE-001 — Make convert authority stages first-class project state

- **Priority:** P0 (0.10.0 load-bearing adopt-path slice)
- **Release target:** 0.10.0
- **GitHub issue:** [#266](https://github.com/NVIDIA-dev/literate-ai/issues/266)
      (Gitlink block already landed),
      [#279](https://github.com/NVIDIA-dev/literate-ai/issues/279) (submodule
      monorepos remain related)
- **Owner:** project metadata, convert harness, and source-to-specification
      qualification
- **Detailed roadmap:** [Operator adoption program](../../roadmap/operator-adoption.md)
- **Direction:** Adopted trees need a visible authority stage so onboard and
      status cannot imply that wrapping a repo made the spec release authority.
- **Conclusion:** Record fail-closed stages wrapped, retained, drafted, and
      qualified. Original source stays release authority until regenerative
      qualification passes. Status and onboard consume the field rather than
      re-inferring it only from directories.
- **Depends on:** RELEASE-0.9-CUT-001, ADOPTION-001, STATUS-001
- **Next action:** Complete. Original source remains effective release authority until
      the current qualified projection evidence validates.
- **Implementation:**
  - [x] Add versioned convert-stage metadata with fail-closed transitions and
        no silent promotion
  - [x] Project status JSON includes the stage; onboard adopt plan names the
        landing stage before apply
  - [x] Keep original source as release authority until qualification evidence
        exists; cite #279 submodule and #266 Gitlink blockers as
        stage-preserving failures
- **Evidence:**
  - [x] Contract tests reject illegal stage skips and refuse
        rebuild-as-authority while wrapped or retained
  - [x] Status and onboard JSON include the stage without a second source of
        truth

### [x] ONBOARD-001 — Guide create and adopt through one plan-then-apply onboard verb

- **Priority:** P0 (0.10.0 operator front door)
- **Release target:** 0.10.0
- **GitHub issue:** [#301](https://github.com/NVIDIA-dev/literate-ai/issues/301)
      is related re-init `--force` scope, not this verb
- **Owner:** litai CLI over init, init --convert --plan, and litai design
- **Detailed roadmap:** [Operator adoption program](../../roadmap/operator-adoption.md)
- **Direction:** New users need two starting paths, creating a project or
      adopting an existing tree, without learning the full verb catalog first.
- **Conclusion:** Add `litai onboard` as a state machine over existing
      mutators. Create may offer design refine. Adopt always plans first and
      shows quarantine, Flavors, retained runners, and Gitlink blockers. TTY is
      a presenter; `--json` is the contract. Agents must not need a TUI.
- **Depends on:** RELEASE-0.9-CUT-001, STATUS-001, BROWNFIELD-STATE-001
- **Next action:** Complete. Maintain one content-identified plan/apply service over
      the existing initialization mutator.
- **Implementation:**
  - [x] Add litai onboard create/adopt that calls init and
        init --convert --plan rather than writing project files directly
  - [x] Create path: host preflight, host-derived Flavor defaults, optional
        design refine, typed plan, apply, next three commands
  - [x] Adopt path: plan first, show quarantine/Flavors/retained
        runners/Gitlink blockers and landing stage, apply only after
        acknowledgement
  - [x] Keep TTY optional and `--json` mandatory; do not add a daemon or a
        second planner
- **Evidence:**
  - [x] Public-API tests cover create and adopt plan-then-apply, JSON
        envelopes, and refusal to apply without acknowledgement
  - [x] Adopt never writes spec-release authority; create does not skip design
        questions when refinement is selected

### [x] GOLDEN-PATH-001 — Prove a stranger first hour from a published wheel

- **Priority:** P0 (0.10.0 stranger first hour)
- **Release target:** 0.10.0
- **GitHub issue:** [#251](https://github.com/NVIDIA-dev/literate-ai/issues/251)
      is the adjacent 0.8.4-to-0.9.0 upgrade smoke, not this stranger path
- **Owner:** docs/user/getting-started.md, installed-wheel e2e, and
      onboard/status contracts
- **Detailed roadmap:** [Operator adoption program](../../roadmap/operator-adoption.md)
- **Direction:** Getting-started currently teaches this checkout's
      `make bootstrap`. Strangers need a first hour from a published wheel that
      reaches hello or a retained receipt.
- **Conclusion:** A golden-path test and user-guide lead install a published
      wheel, not `PYTHONPATH=src`, then complete onboard create or adopt.
      Maintainer bootstrap stays separate.
- **Depends on:** RELEASE-0.9-CUT-001, ONBOARD-001, STATUS-001
- **Next action:** Complete for the 0.10.0 release candidate. Publication remains owned
      by RELEASE-CLOSURE-001.
- **Implementation:**
  - [x] Lead getting-started with pip/wheel install plus onboard, keeping
        make bootstrap as maintainer setup
  - [x] Add an installed-wheel golden-path test for create and a convert
        fixture for adopt-to-retained-receipt
  - [x] Run documentation proofs so README and getting-started do not claim
        the maintainer path as the stranger path
- **Evidence:**
  - [x] Golden-path test uses a published or release-candidate wheel, not this
        checkout's src tree
  - [x] Create reaches a validated hello project; adopt reaches an explicit
        retained stage without claiming spec authority
  - [x] `make wheel-check` on clean commit `2f4a34a1` installed the 0.10.0 wheel
        into isolated environments, validated create, and advanced an inherited-catalog
        brownfield fixture through a current retained receipt with original-source
        release authority

### [x] SOURCE-GENERATION-PROGRESS-001 — Bound coding-agent progress by workload

- **Priority:** P0 (two exact native Windows portfolio runs killed an otherwise
      materialized Component before source admission)
- **Release target:** 0.9.0
- **GitHub issue:** [#304](https://github.com/NVIDIA-dev/literate-ai/issues/304)
- **Observed behavior:** Runs `20260904T063515Z-31e57aab` and
      `20260904T073937Z-07157307` both fail the same collector Component as
      `coding_cli.output_limit` after Codex writes a complete-looking source tree. The
      bounded process adapter kills either stream at 1 MiB and therefore never reaches
      generated-tree validation.
- **Expected behavior:** Normal source-generation progress remains bounded but may use
      a workload-sized budget; small JSON tasks and stdout retain their tighter bound.
      A true stream overflow still kills the complete process tree and fails closed.
- **Conclusion:** JSON-task responses and source-generation progress accidentally share
      one 1 MiB stderr default. Codex documents `exec` progress on stderr, and a relaxed
      live replay measured 745,534 stderr bytes versus 498 stdout bytes for one ordinary
      source call before passing the complete portfolio. A subsequent empty-cache replay
      measured one ordinary source call at 1,091,852 stderr bytes versus 610 stdout bytes,
      directly crossing only the old stderr bound. Source-generation stderr should use
      the existing 16 MiB generated-tree budget while JSON-task stderr and all stdout
      remain at 1 MiB.
- **Competing hypotheses:** A runaway agent is contradicted by the relaxed replay
      completing normally. Stdout overflow is contradicted by the measured asymmetry and
      Codex's documented stream contract. Retry is not the underlying fix because two
      consecutive exact runs failed and output-limit remains a deterministic safety
      boundary rather than a transient source-shape error.
- **Falsification:** The theory is wrong if an empty-cache replay exceeds the old bound
      on stdout rather than stderr, grows beyond the new finite source-progress budget,
      or still fails at this boundary with the larger stderr allowance.
- **Implementation:**
  - [x] Give `CodingCliSourceGenerator` a 16 MiB stderr default tied to the existing
        generated-source byte budget; retain the 1 MiB stdout and JSON-task defaults.
  - [x] Preserve concurrent draining, timeout, exact stream-overflow classification,
        process-tree termination, and secret-free public error/report boundaries.
- **Evidence:**
  - [x] The bounded-reader regression accepts stderr one byte above the task limit under
        the source-generation budget, while existing stdout/stderr overflow cases still
        fail closed.
  - [x] Invocation contracts prove source generation selects the larger stderr bound and
        JSON tasks retain both 1 MiB bounds.
  - [x] The empty-cache NVIDIA Windows portfolio records preflight at 1 stdout / 3,057
        stderr bytes and its six generation subprocesses at 512 / 664,381, 1,152 /
        538,448, 581 / 834,640, 733 / 490,824, 854 / 836,566, and 610 / 1,091,852
        stdout / stderr bytes. With the finite source allowance it passes 28 generated
        tests, four verifier cases, all nine assertions, all five SBOM members, and the
        independent cross-process flow.
  - [x] Focused source/default/task-bound regressions pass, followed by the stable
        uninterrupted Python gate: 3,377 tests pass with 28 expected skips in
        1,358.088 seconds.
  - [x] Exact commit `5cf7100b1022a52127410e0da8797284be133217`
        passes all 15 hosted Linux, macOS, and Windows jobs in run
        `33858381265`.

### [x] CONVERSION-WORKSPACE-LINKS-001 — Reproduce declared sibling topology in disposable baselines

- **Priority:** P0 (the conversion gate changes the source root depth and can make a
      valid host-heavy repository fail before its own build starts)
- **Release target:** 1.1.0
- **Previous release target:** 0.9.0
- **GitHub issue:** [#299](https://github.com/NVIDIA-dev/literate-ai/issues/299)
- **Observed behavior:** A reported Kit workspace resolves a dependency from a source
      file through `../../../omniverse-kit/kit/_build/...`. A controlled equivalent
      succeeds from the live checkout, then the identical recorded command fails after
      conversion resolves it beneath `.literate-ai-convert-baseline-*/omniverse-kit`.
      The exact public Kit App Template revision used for the first positive native
      conversion does not contain that particular reference; the isolated reproduction
      establishes the framework mechanism without claiming that public file does.
- **Expected behavior:** An operator can explicitly bind each required external sibling
      into both disposable conversion workspaces. The binding is validated, finite,
      collision-free, auditable in baseline/parity evidence, and excluded from retained
      source identity. Portable destination topology is harness authority; operator-local
      source locators and linked contents are not project authority.
- **Conclusion:** Quarantine, direct baseline, both wrapper-parity passes, lift-and-shift,
      and retained-receipt execution all change the source root's depth. The harness
      copied retained source but had no input for external sibling topology. A single
      typed Python/OS adapter must validate explicit `DESTINATION=SOURCE` bindings and
      project them beside each disposable `legacy`/`implementation` root. Recording
      only sorted destinations keeps committed evidence portable; an opaque locator
      identity binds each runtime request without publishing a host path.
- **Competing hypotheses:** A package-manager environment override and a missing
      prerequisite artifact are falsified by the live and disposable runs sharing the
      same command/environment while the external sentinel exists. A different
      path-relative interpretation is falsified by resolving the dependency from the
      exact declaring file in both roots. #290 remains distinct: the workspaces still
      live below the project for container visibility.
- **Falsification:** The theory is wrong if the supplied binding does not restore the
      exact source-file-relative target, or the reported real repository still fails on
      the same absent sibling after its required destinations are mapped.
- **Implementation:**
  - [x] Add repeated `--harness-workspace-link DESTINATION=SOURCE` inputs to conversion
        and retained-receipt execution; conversion planning validates without writing.
  - [x] Centralize safe path resolution, overlap/collision limits, POSIX symlinks,
        Windows directory-link fallback, post-run identity checks, and cleanup in one
        host adapter.
  - [x] Use the same binding set for direct baseline, pre-lift parity, post-lift parity,
        and later retained-receipt execution; reject missing or extra destinations.
  - [x] Keep source locators out of committed evidence and bind their opaque identity
        into each retained lifecycle request. A raw generated Make invocation fails
        with an actionable projection diagnostic instead of silently using bad topology.
- **Evidence:**
  - [x] The controlled live checkout succeeds, the unmapped conversion fails and rolls
        back exactly, and mapped conversion passes baseline plus both parity phases.
  - [x] Resolver/materializer regressions cover sorting, path secrecy, missing/unsafe/
        overlapping/duplicate sources, collision, tamper detection, and cleanup.
  - [x] Retained receipt execution rejects an omitted map, succeeds with the qualified
        destination, records an opaque runtime identity, and emits no host locator.
  - [x] The complete 135-test conversion, receipt, CLI, link, and manifest-lock slice
        passes locally.
  - [x] The uninterrupted final-code Python gate passes all 3,370 tests with 30
        expected skips after both authority review markers are current.
  - [x] Exact Windows CI and native CPU fan-out prove the directory-link realization;
        the latter passes the complete durable split-service portfolio.
  - [x] The reported native source-linked workspace resolves its real mapped sibling
        and advances until a distinct historical `repo_man` artifact is unavailable.
- **Closure reconciliation:** Implementation `c23f141f` and qualified descendant
      `d03c73f1e1ccbc0b3b6418ea13dadcbedad41a0c` are ancestors of the current
      integration candidate. [Hosted run 33851431385](https://github.com/NVIDIA-dev/literate-ai/actions/runs/33851431385)
      is a terminal 15/15 pass on that exact descendant;
      [issue #299's terminal evidence](https://github.com/NVIDIA-dev/literate-ai/issues/299#issuecomment-5538375989)
      records resolution of the real missing-sibling mechanism. The unrelated
      unavailable artifact does not reopen that boundary or satisfy other native
      conversion acceptance. Five workspace-link tests and the derived-release-skill
      fixture pass as a six-test confirmation at `33630a4f` (2.994 seconds).
- **Next action:** Complete; preserve the historical qualification above. Native
      nested linbuild work remains on CONVERT-NESTED-GIT-001.

### [x] PROJECT-MANIFEST-LOCK-002 — Retry a vanished just-opened POSIX lock inode

- **Priority:** P0 (a nondeterministic macOS full-suite failure prevents an exact green
      0.9.0 release gate)
- **Release target:** 0.9.0
- **GitHub issue:** [#300](https://github.com/NVIDIA-dev/literate-ai/issues/300)
- **Observed behavior:** Exact-candidate macOS/Python 3.14 CI returned
      `project.manifest_lock` for one of two concurrent exact-snapshot writers. The same
      failure reproduced locally on Python 3.13; its chained cause was an immediate
      `FileNotFoundError` from the pre-acquisition lock-path `lstat`, not a lock timeout.
- **Conclusion:** POSIX idle cleanup can unlink the lock inode after another process has
      opened it but before that process inspects the path. Close that unheld orphaned
      descriptor and retry the complete open/identity/acquire sequence. Continue to
      reject an extant different inode, a symlink, or any post-acquisition replacement.
- **Competing hypotheses:** A Python 3.14-only `flock` regression, the test's join/queue
      deadline, and the Windows 30-second acquisition deadline are contradicted by the
      Python 3.13 reproduction, clean child exit, exact chained exception, and immediate
      failure. A malicious replacement is contradicted by the vanished path in a private
      temporary directory, while the extant-replacement regression remains fail-closed.
- **Evidence:**
  - [x] A deterministic regression unlinks the path between `os.open` and `lstat`, then
        proves acquisition succeeds through a fresh inode and idle cleanup removes it.
  - [x] Existing symlink and post-acquisition replacement regressions remain green.
  - [x] The real two-process compare-and-swap test passes 500 consecutive fresh-process
        iterations; the unfixed implementation failed at iterations 19 and 28 in two
        independent runs.
  - [x] Exact run `33836023512` passes macOS/Python 3.14 and every other hosted cell.

### [x] CONVERSION-BASELINE-001 — Make repo_man baselines explicit under CI

- **Priority:** P1 (blocks Phase 1b qualification for the reported repo_man projects,
      but does not invalidate the native 0.9.0 release flow)
- **Release target:** 0.9.0
- **GitHub issue:** [#288](https://github.com/NVIDIA-dev/literate-ai/issues/288)
- **Observed behavior:** Conversion discovers `./repo.sh build`, then retained baseline
      execution adds `CI=true`; current `repo_build` rejects CI execution unless a
      configuration such as release or debug is explicit.
- **Conclusion:** The discovered command is the single authority reused by direct
      baseline, generated wrapper, and parity replay, and every execution injects
      `CI=true`. Select `--release` at repo_man discovery so all three phases retain
      one explicit deterministic configuration. Do not special-case the executor or
      mutate the command between receipts.
- **Implementation:**
  - [x] Record root and nested repo_man stages as `build --release`; generated wrapper
        targets consume those exact inventory commands.
- **Evidence:**
  - [x] An executable repo_man-shaped fixture reproduces the detected-command/environment
        mismatch and falsifies unrelated dependency/bootstrap explanations.
  - [x] The same fixture proves the inspected command, direct baseline, and retained
        receipt use `./repo.sh build --release`; all 38 harness-inventory conversion,
        baseline, parity, nested-wrapper, and rollback contracts pass.
  - [x] The final exact-commit matrix passes all 15 hosted jobs in run `33858381265`.

### [x] DURABLE-COLLECTOR-RESULT-001 — Define one owner meaning for every result

- **Priority:** P0 (fresh conforming-looking generation can fail the single-winner
      portfolio contract nondeterministically)
- **Release target:** 0.9.0
- **GitHub issue:** [#289](https://github.com/NVIDIA-dev/literate-ai/issues/289)
- **Observed behavior:** Windows run `20260903T205331Z-3bc26192` crossed native
      bootstrap, generation, build, test, migration, initial publication, restart,
      and partial-failure recovery, then rejected the concurrent loser. Its generated
      `lease-held` result returned the live holder in `owner`; the verifier expects the
      requesting owner.
- **Conclusion:** Both normative collector documents name `owner` without defining
      which actor it represents for `lease-held`. Keep one stable result schema:
      `owner` echoes the invocation owner for every status and does not reveal or
      substitute the current holder. Clarify authority instead of accepting both
      meanings.
- **Falsification:** The winner is held inside the upstream fixture before the loser
      starts and is released only after it returns, excluding completion ordering. A
      direct replay of the retained candidate against a copied live-lease database
      returns `owner: holder` for `owner: requester`; finding existing normative text
      that requires the requester would disprove the ambiguity theory.
- **Implementation:**
  - [x] State the invariant in the Component and its public collector interface.
  - [x] Keep the behavioral verifier strict and emit a bounded owner-specific
        diagnostic without logging request or lease identities.
  - [x] Add a deterministic rejection regression for the exact ambiguous result.
- **Evidence:**
  - [x] All 16 durable portfolio contracts plus Ruff pass, including the exact
        lease-held owner rejection. The uninterrupted local gate then passes 3,341
        tests with 30 expected skips.
  - [x] Forced-fresh native Windows CPU run `20260904T043948Z-834d24ea` passes
        single-winner concurrency and the complete durable portfolio flow.

### [x] CONVERSION-BASELINE-002 — Keep disposable repo_man runs visible to nested builders

- **Priority:** P1 (blocks Phase 1b qualification for container-mediated repo_man
      projects, without changing the native package publication contract)
- **Release target:** 0.9.0
- **GitHub issue:** [#290](https://github.com/NVIDIA-dev/literate-ai/issues/290)
- **Observed behavior:** GitLab exposes its `/builds/...` workspace to the Docker
      service, but not the job container's private `/tmp`. Direct baseline and wrapper
      parity each copied repo_man source into a default `TemporaryDirectory`; linbuild
      therefore asked the nested daemon to execute a source path it could not see.
      Inherited `CI_PROJECT_DIR` also continued to name the original converted root.
- **Conclusion:** Both disposable execution phases must remain transactional while
      living beneath the shared project root. When GitLab supplies `CI_PROJECT_DIR`,
      project it to the exact disposable source being observed: the direct baseline
      root or the parity root, not merely the wrapper's launch directory.
- **Competing hypotheses:** Adding `--release` fixes #288's configuration rejection but
      cannot make a private `/tmp` path mountable. Rewriting only `CI_PROJECT_DIR`
      likewise leaves the physical source invisible, and moving only the direct
      baseline defers the same failure to parity replay.
- **Falsification:** If a command that requires `CI_PROJECT_DIR == PWD` and requires
      that path beneath the original shared project succeeds in both direct baseline
      and wrapper parity while either phase still resides outside that root, this
      theory is wrong.
- **Implementation:**
  - [x] Create both hidden disposable roots beneath the resolved project workspace and
        retain context-managed cleanup on success and failure.
  - [x] Project inherited `CI_PROJECT_DIR` to the observed source root, including the
        parity source reached through the generated wrapper.
- **Evidence:**
  - [x] An executable nested-builder-shaped regression requires the exact shared-root
        and environment invariants in both phases, proves their distinct receipts,
        and proves neither disposable directory remains afterward.
  - [x] All 40 harness-inventory conversion, baseline, parity, isolation, and rollback
        contracts pass with Ruff and formatting checks.
  - [x] A native Linux x86_64 Animation Authoring run places the disposable source
        beneath the shared project root and reaches the nested Docker build. It fails
        later only because the CentOS 7 builder lacks the newer `GLIBCXX` symbols
        required by the pinned Kit SDK, while retaining bounded diagnostics and a
        byte-clean rollback. The public Kit App Template completes direct baseline,
        wrapper parity, conversion, and project validation; the exact hosted matrix
        passes all 15 jobs in run `33858381265`.

### [x] AUTHORITY-FACTORING-001 — Make cross-layer authority executable for 0.9.0

- **Priority:** P0 (current HEAD has two deterministic gate failures; taxonomy and
      host-path policies drift because several consumers reconstruct them)
- **Release target:** 0.9.0
- **Owner:** framework core, agent-skill catalog and init template, host adapters,
      CLI/MCP connector surface
- **Owning ADR:** [ADR 0030](../../decisions/0030-executable-cross-layer-authority.md)
- **Detailed roadmap:** [0.9.0 executable-authority program](../../roadmap/0.9.0-executable-authority.md)
- **Direction:** Record and implement the repository-wide investigation: preserve the
      directory hierarchy as the skill taxonomy, put deterministic mechanics behind
      Python services, centralize native Linux/macOS/Windows host paths without
      conflating logical or target paths, and make standard verification hermetic.
- **Conclusion:** Reuse one executable owner per policy. Restore the red gate first;
      then converge catalog consumers, host paths, and connector operations in stages.
      Preserve current safe logical paths, filesystem containment, project cache
      custody, package-resource loading, and explicit live qualification.
- **Depends on:** [MODEL-PREFLIGHT-001](../../roadmap/active-work.md#x-model-preflight-001-validate-the-live-qualification-model-resolves-before-trusting-it)
      and [BROWSER-ACCEPT-001](../../roadmap/active-work.md#x-browser-accept-001-verifier-owned-browser-interaction-acceptance-for-generated-frontends)
      establish the production behaviors whose test/dependency boundaries are repaired;
      the first two repairs otherwise proceed independently.
- **Completion:** The Windows worker identity is accepted; native CPU/GPU Windows and
      Linux/macOS workers exercise the applicable platform boundaries, and exact
      commit `5cf7100b1022a52127410e0da8797284be133217` passes the 15-job hosted
      matrix in run `33858381265`.
- **Implementation:**
  - [x] Make the standard Python gate hermetic while retaining explicit live model
        qualification. The CLI/model override conformance test injects and asserts the
        verifier seam; the ordinary suite reaches no live child process.
  - [x] Document the public `litai worker verify-model` command in the command
        reference and top-level operator help.
  - [x] Carry source-imported, exactly pinned optional dependency groups into self-host
        SOURCE admission without installing them in the core environment. Optional BOM
        declarations remain distinct from the exact installed core closure.
  - [x] Add a deterministic review/record command for the sample test-runner closure;
        the investigation found its pin had remained stale after an earlier runner
        change because only the lifecycle-driver closure has a recorder.
  - [x] Introduce one `AgentSkillCatalog` and use its ownership/inheritance/impact
        semantics in evaluation, validation, initialization, authority graphs, and
        authoring tools.
  - [x] Make the initialized skill catalog declarative and reject every dangling route.
  - [x] Add injectable native host-path policy and migrate config/data/cache/state/tool/
        install/staging and duplicated project-cache consumers with legacy handling.
        Durable user configuration and its 0.8.x migration are owned first by
        [USER-CONFIG-MIGRATION-001](../../roadmap/active-work.md#x-user-config-migration-001-move-08x-private-assets-to-user-configuration-home).
  - [x] Add static enforcement for catalog and host-path ownership, retaining documented
        target-adapter and standalone-bootstrap exceptions. The final audit separates
        home/config policy from `HostSystemPaths` for `os-release`, AppArmor, `ldconfig`,
        and sandbox roots, and rejects absolute `Path(...)` literals outside that owner.
  - [x] Add deterministic work-record, operator-MCP, channel-ingest, stack-resolution,
        and document-verification application services with CLI/MCP adapters. Each
        deterministic transformation has typed fail-closed tests and an MCP adapter.
  - [x] Expose skill/document/static-resource lookup as MCP resources and thin the
        corresponding agent skills to routing and judgment. MCP list/read now projects
        inherited skills, owned resources, documentation, and packaged static assets;
        conversion, roadmap, operator-MCP, channel-ingest, NVIDIA, and document skills
        route their deterministic mechanics to Python.
- **Evidence:**
  - [x] Focused hermetic-preflight, CLI-help, optional-dependency, and complete
        self-host source-drift regression contracts pass locally on macOS. After
        reviewed lifecycle-driver, test-runner, and documentation re-pins, the clean
        uninterrupted Python gate passes 3,204 tests with 30 skips.
  - [x] Taxonomy impact/projection and initialized-reference closure tests pass. The
        full initialization adapter suite also passes with pre-write subset validation.
  - [x] Linux/macOS/Windows table-driven path and migration tests pass on any host,
        including complete 0.8.x worker/test/MCP/event consumer resolution and
        user-independent system-path policy.
  - [x] Connector CLI/MCP parity tests prove deterministic work performs no LLM call.
        Work lifecycle, operator-MCP, channel admission, NVIDIA compatibility, document
        verification, and MCP resource contracts pass with in-process fixtures.
  - [x] `make python-check`, all-skill NVIDIA SkillEvaluator admission, project
        validation, lint, formatting, repository-layout, and documentation gates pass
        locally. Standalone managed-Python bootstrap is covered for the layout and
        skill gates.
  - [x] The exact release commit's Ubuntu/macOS/Windows CI matrix passes.
  - [x] The declared user `workers.json` CPU/GPU Linux and Windows workers pass
        capability probing and the applicable platform-focused contract/gate shards;
        credentials and private routing remain outside committed evidence.
    - 2026-09-02: macOS ARM64, Ubuntu 24.04 CPU, Ubuntu 24.04 NVIDIA, and Ubuntu
      26.04 CPU probes pass and are durably recorded. Both Windows hosts are reachable
      with trusted host keys and now accept unattended qualification; native Windows
      installed-wheel and NVIDIA durable-portfolio proofs pass.

### [x] USER-CONFIG-MIGRATION-001 — Move 0.8.x private assets to user configuration home

- **Priority:** P0 (private durable configuration currently lives inside ignored
      project paths and can be lost, duplicated, or encountered by repository tooling)
- **Release target:** 0.9.0
- **Owner:** host-path policy, user configuration/state adapters, worker/live-test/
      release consumers, init template, CLI migration command
- **Owning ADR:** [ADR 0031](../../decisions/0031-durable-user-configuration-home.md)
- **Direction:** Move every durable user configuration asset out of the checkout.
      Linux and macOS use `$HOME/.config/literate-ai` (honoring an absolute
      `XDG_CONFIG_HOME`); Windows uses its per-user Roaming AppData Known Folder.
      Provide a 0.8.x migration that detects and safely moves legacy private files.
- **Conclusion:** `workers.json` and `mcps.json` are global user config;
      `projects/<project-id>/test.json` is project-scoped user config; worker
      observations and channel journals are user state. Explicit paths retain
      precedence. New default lookup fails with a migration-required diagnostic when
      only a legacy asset exists; migration is dry-run-first, validated, atomic,
      idempotent for identical bytes, and conflict-preserving.
- **Depends on:** ADR 0030's narrow injectable host-path policy; this item is the first
      concrete consumer and therefore lands before broader path migration.
- **Completion:** The migrated catalog remains private beneath
      `$HOME/.config/literate-ai`; all configured host families, including both native
      Windows workers, are reachable through the production resolver.
- **Implementation:**
  - [x] Add central user config/state path resolution with injected platform,
        environment, home, Windows Known Folder, and project ID.
  - [x] Route live-test, worker, worker-observation, release-fleet, MCP, and event paths
        through the shared resolver while preserving explicit flag/environment
        precedence and rejecting relative overrides.
  - [x] Add `litai config paths` plus `litai config migrate` dry-run/apply for validated 0.8.x project-root and
        legacy `~/.config/litai` assets with atomic, private, no-overwrite semantics.
  - [x] Update init output, examples, skills, user docs, architecture tables, and old
        ADR references without deleting the 0.9.x legacy ignore safety net.
- **Evidence:**
  - [x] Table-driven Linux/macOS/Windows roots, overrides, project isolation, and
        relative/missing-home/Known-Folder failures pass without host-dependent skips.
  - [x] Migration dry-run writes nothing; apply, identical retry, conflicting
        destination, symlink, partial-failure, permissions, and secret-redaction cases
        pass.
  - [x] A simulated 0.8.x project migrates and every CLI consumer resolves the new
        location; an unmigrated project returns the typed recovery diagnostic.
  - [x] The supplied worker catalog is migrated only through the explicit command and
        remains usable for Linux/Windows CPU/GPU qualification without exposing its
        contents.
    - 2026-09-01: dry-run found one conflict-free six-worker catalog; apply moved it to
      `$HOME/.config/literate-ai/workers.json` with `0700/0600` custody. Production
      parsing succeeds. macOS, Ubuntu 26.04 CPU, and Ubuntu 24.04 NVIDIA probes succeed
      and private state is `0700/0600`; Ubuntu 24.04 CPU and both Windows workers
      were initially blocked by absent SSH known-host entries, not catalog/schema
      failure. The Linux entry was then trusted and now passes; both Windows hosts are
      trusted and reachable but reject the locally available noninteractive keys.
    - 2026-09-01: focused migration/path/consumer contracts and the clean 3,204-test
      Python gate pass; the repeat dry-run detects no remaining legacy asset.
    - 2026-09-02: the production migration dry-run detected one remaining 0.8.x event
      beneath legacy `$HOME/.config/litai`; apply moved it with mode `0600` to the resolved
      `$HOME/.local/state/literate-ai/events` root and removed the empty legacy
      application directory. Durable configuration remains solely beneath
      `$HOME/.config/literate-ai`.

### [x] HOST-INSTALL-SBOM-001 — Make native CLI installation SBOM-driven

- **Priority:** P0 (the 0.9.0 CLI installer has no executable native-package or
      cross-platform consent contract)
- **Release target:** 0.9.0
- **Owner:** stage-zero installer, host-platform adapter, native package prerequisite
      SBOMs, and cross-platform CI
- **Owning ADR:** [ADR 0032](../../decisions/0032-tuple-specific-native-install-sboms.md)
- **Direction:** Make `make install` prove all core native prerequisites through the
      host's conventional package manager. Ask before installing missing packages,
      support explicit noninteractive consent, keep Python distribution dependencies in
      their package/lock authority, and store native dependency policy in separate
      CycloneDX SBOMs by OS, CPU architecture, and accelerator coordinate.
- **Conclusion:** GNU Make and a compatible executing Python are the irreducible stage
      zero. A dependency-free stage-zero tuple/SBOM parser plus one native-package
      adapter owns the remaining deterministic work. Unsupported tuples fail with the supported inventory and the
      directory to copy for a port; no platform fallback or automatic package-manager
      bootstrap is allowed.
- **Depends on:** ADR 0030 `HostPaths` for host-native install and OS-metadata paths;
      ADR 0002 for the isolated pinned Python distribution closure.
- **Next action:** Require the exact repair commit's Ubuntu/macOS/Windows CI
      install/uninstall/reinstall evidence, then repeat on reachable private workers.
- **Implementation:**
  - [x] Add strict CycloneDX 1.7 host-prerequisite SBOMs for Debian Linux x86-64/ARM64,
        macOS x86-64/ARM64, and Windows x86-64; every core tuple uses accelerator
        coordinate `none` and declares its package manager and command templates.
  - [x] Add deterministic tuple detection, schema/graph/version validation, native
        package queries, executable probes, one-shot consent, declarative install, and
        post-install re-probe. Reject unsupported tuples, absent managers, malformed
        templates, and symlinked SBOMs with actionable diagnostics.
  - [x] Integrate the preflight into `make install`, preserve explicit `PREFIX`, use the
        centralized host-native default otherwise, and force installed-E2E invalidation
        when installer SBOMs change.
  - [x] Add the exact noninteractive `make install` → `make uninstall` → `make install`
        operation at one isolated prefix to the existing Ubuntu/macOS/Windows CI matrix.
- **Evidence:**
  - [x] Five committed SBOMs pass the official CycloneDX 1.7 schema and the local
        tuple/manager/package/dependency-graph contract. Simulated tests cover all
        target families, aliases, decline, explicit consent/install/re-probe, missing
        manager, unsupported tuple guidance, version failure, and symlink rejection.
  - [x] The local macOS ARM64 dependency-only preflight proves Homebrew Python 3.13 and
        Git package provenance plus the executing Python/Git version contracts without
        changing the host.
  - [x] A clean-checkout macOS ARM64 `make install` succeeds into a fresh disposable
        prefix, the installed launcher renders help on a TTY, and help creates no user
        configuration.
  - [x] Live macOS ARM64, Ubuntu 24.04 NVIDIA, and Ubuntu 26.04 CPU installs from the
        exact pushed source archive reach the host installer. The exercise exposed and
        now covers same-version console-script replacement; Ubuntu 24.04 CPU correctly
        declined its one missing native dependency when noninteractive consent was no.
  - [x] The exact pushed commit's Ubuntu/macOS/Windows installation jobs pass in hosted
        run `33858381265`.

### [x] HOST-UNINSTALL-001 — Remove only Literate AI-owned host installation state

- **Priority:** P0 (a cross-platform native installer needs an equally explicit,
      safe removal contract before 0.9.0 ships)
- **Release target:** 0.9.0
- **Owner:** `make uninstall`, host install-path adapter, uninstall script, user docs,
      and Ubuntu/macOS/Windows installation matrix
- **Direction:** Add `make uninstall` with the same centralized host-prefix policy as
      `make install`. Remove only the Literate AI launcher and private runtime installed
      beneath that prefix, prune Literate AI-created empty parent directories, and
      leave Homebrew/APT/WinGet packages and durable user configuration/state intact.
      Explicit `PREFIX` keeps precedence. Symlinks, path escape, foreign content, and
      an unsupported install layout fail closed without broad recursive deletion.
- **Depends on:** HOST-INSTALL-SBOM-001 and ADR 0030 host path ownership.
- **Next action:** Require the exact repair commit's three-OS CI cycle, then exercise
      the same corrected cycle on the reachable macOS/Linux private workers.
- **Implementation:**
  - [x] Add a deterministic uninstall planner and CLI script using only centralized
        install-root resolution and OS-aware launcher naming.
  - [x] Wire `make uninstall` with optional `PREFIX`; do not run native package-manager
        removal commands.
  - [x] Document which durable config/state paths are deliberately retained and how an
        operator may remove them separately.
- **Evidence:**
  - [x] Installed launcher/runtime disappear, a second uninstall is idempotent, and
        unrelated prefix files survive.
  - [x] Symlink/path-escape and manifest-mismatch fixtures fail closed; independently
        owned sibling tools/cache/state survive exact manifest-bound removal.
  - [x] Ubuntu, macOS, and Windows install/uninstall/install cycles pass in hosted run
        `33858381265`.

### [x] SLICE-080-PLUGIN-PKG — Isolated 0.8.0 plugin, packaging, Flavor, and catalog slice

- **Priority:** P0 (0.8.0 break-glass)
- **Owner:** plugin bundle, Homebrew formula, package lifecycle, Flavor catalog,
      workflow composition, catalog provenance, source-index ignore rules
- **Direction:** On branch `slice/0.8.0-plugin-package-flavor` (worktree
      `/private/tmp/litai-080-plugin-pkg`), land the assigned 0.8.0 items without
      merging `release/0.7.x`, tagging `v0.8.0`, or `git mv` of existing Flavor
      directories (FLAVOR-005 / WebMCP own those moves). New Flavors use
      axis-qualified directory names.
- **Conclusion:** Inspect-first items that already exist on disk stay catalog/evidence
      work: Make smart defaults (FLAVOR-001), `deploy-docker` (FLAVOR-CONTAINER-001),
      `litai catalog copy|graph` DAG (COMPOSE-001), nested workflow directories
      (WORKFLOW-CATALOG-001), and CodeGraph ignore of dependency caches only
      (INDEX-001). CODEGRAPH-PROJECT-001 must remain opt-in under ADR 0016/0019
      (`provider_id: none` default); do not force CodeGraph as a product dependency.
      Landed on this branch: PLUGIN-001 bundle + `litai-mcp`, PACKAGE-002 formula
      (sha256 still zeros), PACKAGE-001 native metadata ZIPs plus Conan wildcard
      when two language Flavors are selected, FLAVOR-006 `litai flavor add`,
      FLAVOR-003 `lang-typescript`, FLAVOR-CONTAINER-001 docker skill stamp,
      FLAVOR-ZIG-001 catalog (`lang-zig` + `toolchain-zig-cc`; no host discovery
      or cross-compile sample), WORKFLOW-CATALOG-001 parse-time `extends`,
      COMPOSE-001 `workflow:`/`routing:` copy kinds, INDEX-001 non-git
      `source/build/` inventory test. CODEGRAPH-PROJECT-001 stays opt-in.
- **Depends on:** none beyond current `main` at `0a10a6a3`
- **Next action:** Done. Slice merged as `01881122`. Remaining named gates stay on
      their owning children (`make samples`, live `brew install`, Zig host discovery,
      git catalog sources, nested-workflow lock/plan, Claude session e2e). Do not
      retarget `samples/hello-component`. Do not retag `v0.8.0`.
- **Implementation:**
  - [x] PLUGIN-001 skills plugin + MCP adapter from checked-in skills
  - [x] PACKAGE-002 Homebrew formula (no CodeGraph dependency)
  - [x] PACKAGE-001 remaining native provider adapters (apt/brew/winget/chocolatey)
  - [x] FLAVOR-006 `litai flavor add`
  - [x] FLAVOR-003 `flavors/lang-typescript/`
  - [x] FLAVOR-CONTAINER-001 stamp docker Flavor/skill into `_TEMPLATE_FILES`
  - [x] FLAVOR-ZIG-001 `lang-zig` + `toolchain-zig-cc` catalog (no cross-compile sample)
  - [x] WORKFLOW-CATALOG-001 parse-time `extends` composition (nested-catalog lock/plan
        on `dev` remains the intended proof; staging/production stay framework-only)
  - [x] COMPOSE-001 remaining: workflow/routing copy kinds; git sources stay open
  - [x] INDEX-001 non-git `source/build/` inventory test on the current adapter
  - [x] CODEGRAPH-PROJECT-001: record opt-in-only; do not require CodeGraph at init
- **Evidence:**
  - [x] Focused unit tests for each landed item pass under `LITAI_SESSION_ID=dev`
  - [x] Branch merged to `main` as `01881122`. Remaining named gates
        (`make samples`, live `brew install`, Zig host discovery) stay on
        their owning items. Do not retag `v0.8.0`.

### [x] SAMPLE-PIN-001 — Re-pin sample harness identities after 0.8.0 catalog merges

- **Priority:** P0 (blocks `make python-check`)
- **Owner:** `samples/_harness/*/sample.json`
- **Direction:** `NeutralSampleLadderTests.test_all_host_recipes_compose_from_specs_and_real_flavors`
      fails closed with `sample metadata has a stale component.md identity`.
      Concurrent 0.8.0 merges updated `component.md` (nested app-stack skills,
      new peer samples) without refreshing the verifier pins.
- **Conclusion:** Compute identities through the same `_load_sample` parser the
      ladder uses. Update only drifted `component_authoring_identity`,
      `specification_identity`, and `execution_interface_identity` fields.
      Do not invent digests. PR #197 is closed without merge (CONVERT-FW-009
      prerequisite closure already on `main`; its branch predates FLAVOR-005).
- **Depends on:** landed 0.8.0 catalog merges on `main` (`390cc7ec`)
- **Implementation:**
  - [x] Diagnose every `samples/_harness/*/sample.json` whose authoring,
        specification, or execution pin disagrees with current `component.md`.
        Drift was `python-service-example` and `react-dashboard-example`
        (nested app-stack skill URIs after `06e48b87`).
  - [x] Rewrite only the drifted identity URIs; keep oracle pins and JSON key
        order.
  - [x] Pass the admitted framework skill catalog into sample
        `GenerationRecipe` construction so Flavor parent skills close the same
        way live generation does.
  - [x] Re-pin sample-test-runner and lifecycle-driver identities after the
        runner change; run `make LITAI_SESSION_ID=dev python-check`.
        Resume leftovers: MCP catalog isolation, stdio process-tree bind,
        v1 project projection drops `institutional_channels`, runtime oracles
        for `python-service-example` and `react-dashboard-example`.
- **Evidence:**
  - [x] `_load_sample` succeeds for every host-discovered sample.
  - [x] `make PYTHON_ENV="_build/python-envs/make-267" python-check` is green
        (2883 tests, 20 skipped, 2026-08-29).

### [x] MODEL-PREFLIGHT-001 — Validate the live-qualification model resolves before trusting it

- **Priority:** P1 (a wrong/nonexistent model id in `literate.test.json` — which
      the user is free to set — was accepted unvalidated and only failed deep
      inside a generation run, masked as a generic server error)
- **Release target:** 0.9.0
- **Owner:** `src/literate_ai/adapters/live_test_selection.py`
      (`verify_live_model_resolves`), `src/literate_ai/adapters/models/coding_cli.py`
      (`_coding_cli_command` opencode logging), `tests/conformance/support/sample_runner.py`
- **Direction:** `resolve_live_test_selection` validated that a coding CLI + model
      were *present* and the CLI supported, but never that the model id actually
      *resolves* for that CLI. Any string passed — e.g. the un-prefixed
      `router/example-model` (the resolvable id is
      `custom-provider/router/example-model`) — and the mistake only
      surfaced mid-generation as `coding_cli.generation_failed` with empty
      diagnostics. Two compounding defects: (a) the opencode invocation omitted
      `--print-logs`, so opencode's real `ProviderModelNotFoundError` went only to
      its server log and the framework saw a generic "Unexpected server error";
      (b) nothing preflighted the model.
- **Conclusion (landed 2026-09-01):**
  1. `_coding_cli_command` now launches opencode with `--print-logs --log-level
     ERROR`, so the real coding-CLI error reaches the captured failure output and
     `_coding_cli_failure_detail` excerpts it.
  2. New `verify_live_model_resolves(selection)` runs one minimal bounded
     non-source-writing task through the selected CLI + model; a model that does
     not resolve raises typed `coding_cli.model_unavailable` naming the model and
     the underlying CLI cause, with guidance (`opencode models`). The sample
     runner calls it once before any generation (skippable via
     `LITAI_SKIP_MODEL_PREFLIGHT` for a deliberate dry run).
  3. New `litai worker verify-model` command (`--coding-cli` / `--model`
     overrides) resolves the live-test selection and runs the same preflight, so
     an operator can validate a `literate.test.json` before trusting it — returns
     `{resolves: true}` on success, fails closed with `coding_cli.model_unavailable`
     otherwise. The `configure-test-workers` skill now directs the operator to run
     it after setting/changing `coding_cli`/`model` (both skill copies updated,
     byte-identical, no digest cascade).
  It is a preflight *gate* — `resolve_live_test_selection` stays a pure,
  network-free string resolution; the user may set any model (including an
  inexpensive one they know), but a wrong one now fails in ~seconds with a clear
  message instead of minutes into generation.
- **Depends on:** none
- **Evidence:**
  - [x] A wrong/mis-qualified model id fails fast at preflight with
        `coding_cli.model_unavailable` naming the model + real cause (verified
        end-to-end: `router/example-model` fails in ~2.7s with the
        surfaced `ProviderModelNotFoundError`; the fully-qualified
        `custom-provider/router/example-model` passes and
        `hello-component` generates green).
  - [x] Unit tests cover pass / wrong-model-fails-closed / reachable-but-unusable
        / environment-overlay (`test_live_test_selection.py`
        `VerifyLiveModelResolvesTests`); opencode argv logging asserted in
        `test_coding_cli_generation.py`.
  - [x] `litai worker verify-model` validates a config before trusting it,
        verified end-to-end (corrected `literate.test.json` →
        `{ok: true, resolves: true}`; wrong `--model` override →
        `coding_cli.model_unavailable` in ~2.9s with the surfaced
        `ProviderModelNotFoundError`); `test_cli_worker_verify_model.py` covers
        help / ok / fail-closed. `configure-test-workers` skill directs operators
        to run it.

### [x] SAMPLE-DIAG-001 — Sample runner swallows the coding-CLI failure detail

- **Priority:** P2 (diagnosability; not a correctness bug, but it blocks
      operators from triaging a failed live generation without reproducing the
      exact CLI argv by hand)
- **Release target:** 1.1.0
- **Previous release target:** 0.9.0 or a following minor
- **Owner:** `tests/conformance/support/sample_runner.py`
      (`execute_standard_sample_variant` ~6901, `failure_diagnostics`),
      `src/literate_ai/adapters/models/coding_cli.py`
      (`_coding_cli_failure_detail`, `coding_cli.task_failed` ~1994 already
      captures bounded stderr)
- **Direction:** When a live sample generation fails, `run_samples.py` reports
      `Standard sample <name> lifecycle failed: {<digest>: 'coding_cli.<code>'};
      diagnostics={}` — the bounded coding-CLI stderr that `coding_cli.py` already
      captures for `coding_cli.task_failed` is dropped at the sample-runner
      boundary, so the operator sees an empty `diagnostics={}` and cannot see the
      model's actual error. Observed 2026-09-01 triaging the deferred live samples:
      `coding_cli.generation_failed` (a `router/` provider server outage) and
      `coding_cli.generated_metadata_invalid` (an off-pin model) both surfaced with
      `diagnostics={}`; the real cause was only visible by reproducing the exact
      `opencode --pure run --agent build --model <m> <prompt>` argv by hand.
- **Conclusion:** Thread the bounded coding-CLI failure detail (already computed by
      `_coding_cli_failure_detail`, secret-free and byte-bounded) into the sample
      runner's `failure_diagnostics` so a failed live generation reports the
      model's actual error class/text instead of `diagnostics={}`. Keep it bounded
      and secret-free; do not make transient stderr part of any derivation key
      (the runner already excludes transient diagnostics from the derivation key).
- **Depends on:** none
- **Evidence:**
  - [x] `tests.conformance.test_sample_ladder.NeutralSampleLadderTests.test_standard_sample_reports_bounded_redacted_generation_failure`
        executes the Standard sample lifecycle with controlled nonzero provider-process
        results. Both failure texts report `coding_cli.generation_failed`, exit status
        and provider detail instead of empty diagnostics. No live provider outage is
        required or claimed by this regression.
  - [x] The same test supplies a 24 KB diagnostic with a forwarded test credential;
        the public error stays below 9 KB, excludes the credential and temporary path,
        and retains the useful diagnostic tail. Two distinct provider error texts
        produce identical planned source derivation keys.
- **Validation:** The frozen sample/generation batch passes 220 tests (8 live or
  platform-dependent skips); all 63 project-CLI/quota tests and 16 roadmap/skill
  contract tests pass. Documentation renders 121 diagrams from 545 Markdown files;
  formatting checks 1,172 files. Runner and lifecycle TCB reviews are current.
  These are local change-verification results, not release or live-model attestation.

### [x] CHECKPOINT-STANDARD-001 — Checkpointed unittest runner crashes for Standard-bound projects

- **Priority:** P1 (regression against 0.8.0/0.8.1; blocks any Standard-bound
      derived project's test dispatch)
- **Release target:** 0.8.2 (patch on `release/0.8.x`)
- **GitHub issue:** [#215](https://github.com/NVIDIA-dev/literate-ai/issues/215)
- **Owner:** `src/literate_ai/test_checkpointing.py` (`_try_framework_pins`),
      `src/literate_ai/adapters/project_lifecycle_driver.py`
      (`lifecycle_driver_implementation_identity`)
- **Direction:** In a derived project whose `lifecycle_driver.binding` is
      `standard`, `scripts/run_checkpointed_unittests.py` crashes before test
      discovery: `_try_framework_pins` passes a `StandardProjectLifecycleDriver`
      to `lifecycle_driver_implementation_identity`, which unconditionally
      iterates `driver.implementation_paths` — a field the Standard driver
      (only `framework_distribution_identity` + `policy_identity`) does not have,
      raising `AttributeError`.
- **Conclusion:** A Standard-bound driver has no `implementation_paths`; its
      implementation identity is its `framework_distribution_identity`. Make
      `lifecycle_driver_implementation_identity` (or its caller) handle the
      Standard driver kind — derive the pin from the distribution/policy
      identities rather than a path list — and fall back to full-suite dispatch
      (no crash) when a pin cannot be computed. Add a regression exercising
      checkpointed unit/gate dispatch in a Standard-bound project.
- **Depends on:** none
- **Shipped:** v0.8.2 (2acab831 on main; backported to release/0.8.x as 6deb3a87).
      `lifecycle_driver_implementation_identity` now returns the framework
      distribution identity for a Standard-bound driver instead of iterating the
      nonexistent `implementation_paths`.
- **Evidence:**
  - [x] `run_checkpointed_unittests.py` runs (does not crash) in a Standard-bound
        derived project; a regression
        (`test_standard_driver_implementation_identity_uses_distribution`) covers
        checkpointed dispatch for the Standard driver kind.

### [x] BROWSER-ACCEPT-001 — Verifier-owned browser interaction acceptance for generated frontends

- **Priority:** P0 (generated frontends pass generated tests and text-only
      service acceptance while shipping observable browser failures — a
      silent false-pass in the acceptance oracle, not just a generation-quality
      gap)
- **Release target:** 0.9.0 (feature; lands on `main`, ships in the minor — not
      a patch on `release/0.8.x`). Prioritized as an early-0.9.0 headline rather
      than deferred, given the P0 false-pass.
- **GitHub issue:** [#218](https://github.com/NVIDIA-dev/literate-ai/issues/218)
      (extends [#64](https://github.com/NVIDIA-dev/literate-ai/issues/64) and
      [#134](https://github.com/NVIDIA-dev/literate-ai/issues/134); follows the
      operator-side FRONTEND-002 `verify-frontend-browser` skill)
- **Owning ADR:** [ADR 0028](../../decisions/0028-browser-interaction-acceptance.md)
      (Accepted and implemented 2026-09-01)
- **Owner:** independent-acceptance path for `web-application` /
      `persistent-service` frontends — a new verifier-owned browser acceptance
      contract distinct from generated tests, plus a browser-tool-neutral adapter
      (Playwright as the initial adapter) and an evidence receipt.
- **Direction:** Independent acceptance currently checks HTTP text, so a frontend
      that omits required sections, renders `NaN`, throws on init, has an inline
      script syntax/undefined-constant error, binds no working scroll handler,
      ships no-op export/column controls, or overflows on mobile still passes.
      Add a verifier-owned browser acceptance contract that can declare: service
      startup + desktop/mobile viewports; accessible role/name assertions and
      required landmarks; rejection on browser console errors, page errors,
      failed/HTTP-error requests; document-overflow checks; interaction steps
      (click/select/fill/scroll/keyboard); observable postconditions
      (text/state/ARIA/row identity/count/download); request-count assertions for
      local-only interactions; screenshot + accessibility-snapshot diagnostics;
      deterministic fixture/stub transport (never live credentials or private
      oracle values in generation prompts).
- **Conclusion:** Ship a browser-tool-neutral acceptance contract + adapter whose
      evidence receipt binds viewport, interaction contract, browser/tool
      identity, screenshots, console failures, and outcome. Keep existing
      persistent-service text probes supported for non-browser services. Fail
      closed on any console/page-error/failed-request/overflow/postcondition
      violation.
- **Depends on:** ACCEPTANCE-SERVICE-002 (#214, the `--litai-serve` launch mode —
      shipped in 0.8.2) provides the served-frontend launch the browser oracle
      drives.
- **Evidence:**
  - [x] A fixture that only contains expected HTML text but throws during
        initialization fails (`test_throwing_init_surfaces_a_console_error_and_fails`).
  - [x] A virtual-grid fixture with an unbound scroll handler fails after a
        scroll/postcondition step (`test_unbound_scroll_handler_fails_its_postcondition`).
  - [x] A no-op Export button fails a download assertion
        (`test_noop_export_button_fails_a_download_assertion`).
  - [x] A page wider than a 390px viewport fails overflow acceptance
        (`test_page_wider_than_mobile_viewport_fails_overflow`).
  - [x] A local sort/toggle that fetches unexpectedly fails a request-count
        assertion (`test_local_toggle_that_fetches_fails_request_count`).
  - [x] The evidence receipt binds viewport, interaction contract, browser/tool
        identity, screenshots, console failures, and outcome
        (`test_evidence_receipt_binds_the_full_interaction_context`).
  - [x] Existing persistent-service text probes remain supported for non-browser
        services by the standard lifecycle integration tests.

### [x] KNOWN-FAILURE-CHECKPOINT-001 — Retain known failures without hiding test debt

- **Priority:** P1 (long repair suites repeatedly spend worker time on an explicitly
      classified failure, while ordinary skip/xfail accounting can falsely look clean)
- **Release target:** 0.9.0
- **GitHub issue:** [#230](https://github.com/NVIDIA-dev/literate-ai/issues/230)
- **Owner:** shared pinned-test/checkpoint contracts, atomic checkpoint store,
      checkpointed Python adapter, external-runner result import, CLI/API operations,
      evidence ledger, and project-test receipt accounting
- **Direction:** Add operator-authored known-failure annotations bound to the exact
      content pin, test key, environment observation (or explicit universal authority),
      retained failure evidence/fingerprint, credential-free reason, and expiry or
      revalidation policy. Matching repair runs synthesize a visible `known-failure`,
      continue later tests, count it separately and as non-passing, and never issue an
      all-passing receipt. Release evidence always executes from the beginning.
- **Conclusion:** Extend the existing checkpoint ledger; do not create a parallel skip
      store and never classify failures automatically. Stale, malformed, secret-shaped,
      ambiguous, or context-mismatched annotations fail closed and execute the test.
- **Depends on:** existing checkpointed Python-test and project-test receipt authority;
      no dependency on MULTI-ENTRYPOINT-001 or SPLIT-SERVICE-001.
- **Next action:** Land the reviewed implementation and use its external-event importer
      for the classified Kit repair checkpoint; no framework implementation work remains.
- **Implementation:**
  - [x] Add a typed known-failure annotation and atomic store update bound to one exact
        pin, key, context, original failure evidence, reason, policy, and optional public
        tracker.
  - [x] Add explicit CLI/API annotate, inspect, revalidate, and clear operations.
  - [x] Teach checkpointed Python tests and the external-runner adapter to synthesize
        and import attributable known-failure outcomes, continue, and invalidate stale
        annotations.
  - [x] Extend totals and receipts with passed/failed/known-failed/skipped/executed;
        known failures remain repair-incomplete and cannot authorize release evidence.
- **Evidence:**
  - [x] Same pin/context suppresses only the exact annotated test, continues later
        tests, counts known-failed, exits non-passing, and emits no passing receipt.
  - [x] Changed source, context, expiry, or fingerprint executes normally; explicit
        revalidation success or clear removes the annotation.
  - [x] Universal authority is explicit and visible; malformed/stale/secret-bearing
        records suppress nothing.
  - [x] A deterministic authentication-required external-runner fixture proves import
        without private endpoints or credentials.
  - [x] The Python adapter's default pin folds exact discovered test-source bytes;
        a changed test cannot reuse an old annotation. Clean runs in another context
        retain the original context's debt, and successful Python or external-runner
        revalidation clears only the exact annotation.
  - [x] The clean full Python check and exact non-editable wheel version check pass on
        the final branch revision; lint, format, schema, documentation, and lifecycle
        authority checks are current.

### [x] SCHEDULER-LEASE-001 — Persisted daily jitter scheduler and single-writer lease guidance

- **Priority:** P1 (reimplementing schedule/restart/concurrency independently
      risks clock, restart, and duplicate-work bugs; the collector in
      SPLIT-SERVICE-001 needs exactly this behavior)
- **Release target:** 0.9.0 (feature; lands on `main`, ships in the minor)
- **GitHub issue:** [#217](https://github.com/NVIDIA-dev/literate-ai/issues/217)
- **Owning ADR:** [ADR 0027](../../decisions/0027-durable-split-service-pattern.md)
      (Accepted and implemented 2026-09-01 — the scheduler-lease authority is
      decided with the split-service pattern)
- **Owner:** a reusable worker/scheduler generation skill (or Component
      template) — generation guidance/reference authority for an application's
      own worker, NOT a framework scheduler daemon.
- **Direction:** Derived services that poll expensive shared systems need
      predictable average cadence without synchronized fleet spikes or duplicate
      work after restart. Specify: configurable nominal UTC run time + symmetric
      bounded jitter; injectable random/clock sources for deterministic tests;
      persisted schedule window, selected jittered instant, last completed
      window, and retry state; a database-backed lease (owner, acquisition time,
      expiry) so multiple workers cannot execute one window; restart semantics
      (before target: preserve selection; after completed target: do not rerun;
      after expired running lease: recover safely); bounded retry/backoff tracked
      separately from the next daily schedule; append-only run and per-source
      outcome records; progress/failure output without logging secrets; graceful
      cancellation and next-run status.
- **Depends on:** SPLIT-SERVICE-001 (#216) — this is the collector's scheduler in
      that pattern; co-design so the lease/state store shares the embedded cache
      boundary.
- **Evidence (deterministic tests):**
  - [x] Negative and positive jitter bounds around nominal time.
  - [x] UTC date rollover and clock movement.
  - [x] Restart before target, during a leased run, after success, after failure.
  - [x] Concurrent scheduler instances with exactly one winner.
  - [x] Expired lease recovery.
  - [x] Long-running work crossing the next nominal boundary.
  - [x] Retry behavior that does not create a second daily run.
  - [x] Next-run/progress state readable by a separate API process.
        All cases above are executable in
        `tests/unit/test_scheduler_lease_reference.py`.

### [x] RELEASE-018-IDEMPOTENT — Wheel asset upload must tolerate an already-uploaded asset

- **Priority:** P2
- **Release target:** 0.8.1
- **Owner:** `src/literate_ai/project_releases.py` (`_upload_wheel_asset`)
- **Direction:** During the 0.8.0 publish, `_upload_wheel_asset` succeeded on the
      first `gh release upload` (the wheel is attached to the v0.8.0 release), but
      a subsequent idempotency-retry `gh release upload` of the same asset failed
      because the asset already existed, surfacing `release.wheel_upload_failed`
      even though publication was complete and correct (`verify-published` ok).
- **Conclusion:** `_upload_wheel_asset` now uses `gh release upload --clobber`
      so a retried or resumed publish overwrites an identical already-attached
      asset instead of reporting a false `release.wheel_upload_failed`. The
      upload is not weakened; it is idempotent.
- **Evidence:**
  - [x] `_upload_wheel_asset` passes `--clobber`; 66 release tests pass.
        Re-running publish with the wheel already attached returns success.

### [x] WINDOWS-LOCK-001 — Windows manifest/append write-lock never worked (blocked CI and the 0.8.0 cut)

- **Priority:** P0
- **Release target:** 0.8.1 — the active 0.8.1 headline. 0.8.0 shipped on the
      green POSIX matrix with Windows documented as a known issue.
- **2026-08-31 Windows CI update (run 33427732750, `90472857`):** the
      write-before-lock fix (`4002b5e8`) did **NOT** fix Windows. The
      `LITAI_LOCK_DIAG` diagnostic still reports
      `PermissionError errno=13 (EACCES) winerror=None` from
      `msvcrt.locking(LK_NBLCK, 1)` — now with the placeholder byte already
      written, so the empty-file hypothesis was wrong. `EACCES` from
      non-blocking `msvcrt.locking` means the byte-0 region is already locked by
      another handle; the 30s retry loop then times out. Most likely a
      same-process double-lock: a prior `_lock`/`_remove_idle_lock` handle (or a
      second open of the same lock file) still holds the region on Windows, where
      `msvcrt` locks conflict across handles within one process. Next: add
      diagnostics identifying the operation/handle/PID, or restructure so only
      one handle ever locks the file per operation. This is the 0.8.1 work.
- **Owner:** `src/literate_ai/projects.py` (`ProjectConfigurationStore._lock`),
      `src/literate_ai/adapters/authority.py` (`_append_lock`)
- **Direction:** The hardened compare-and-swap config store added in `3b68f5ae`
      ("Preparing for 0.8.0-RC1") shipped a POSIX-first byte-range lock that fails
      on Windows: every `litai init` and project-config write on Windows CI raised
      `ProjectError: manifest lock failed` from `msvcrt.locking(fd, LK_LOCK, 1)`.
      Windows/Python 3.12 CI has been red the entire release cycle.
- **Conclusion:** Two Windows-only defects, both already solved once in the
      sibling `src/literate_ai/_cache_lock.py` (commits `0da7387b` and `4c756e9a`,
      CPython issue #76): (1) the placeholder byte was written before the lock was
      held — Windows mandatory byte-range locking makes that collide — and the
      blocking `LK_LOCK` retries ~10s then raises a bare `OSError`; (2)
      `(st_dev, st_ino)`/`samestat` identity is unreliable on Windows where
      `os.fstat` reports `st_ino == 0`. Reuse `_cache_lock`'s proven helpers:
      take the lock first (non-blocking `LK_NBLCK` on a bounded retry loop), write
      the placeholder under the lock, and fall back to
      `GetFileInformationByHandle` identity only when `st_ino == 0`. POSIX path is
      byte-for-byte unchanged. Fixed the identical pattern in `authority.py`.
- **Depends on:** none; `_cache_lock.py` already ships the proven primitives
- **Implementation:**
  - [x] `ProjectConfigurationStore`: lock-then-write ordering, `LK_NBLCK` retry
        loop, `st_ino == 0` Windows identity fallback in `_lock` and
        `_remove_idle_lock`; POSIX unchanged.
  - [x] `FileAuthorityProjectionStore._append_lock`: same fix reusing the same
        `_cache_lock` helpers.
  - [x] Cross-platform regression tests: POSIX uses `(st_dev, st_ino)` and never
        calls Win32; `st_ino == 0` routes to `_windows_identity_matches`; a
        symlinked lock file is rejected; the lock serializes two concurrent
        writers (real exclusive lock, not a no-op).
- **Evidence:**
  - [x] `test_project_configuration.py`, `test_component_authority.py`,
        `test_locked_source_promotion.py`, `test_repository_updates.py`,
        `test_project_cli.py` pass on POSIX (108 tests).
  - [x] Windows/Python 3.12 CI goes green on `init` and repository-update tests.
        **ACHIEVED (2026-08-31, run `33442231618`).** The real root cause was
        NOT the lock: the enriched `LITAI_LOCK_DIAG` diagnostic showed the
        `msvcrt.locking` acquire succeeded (`attempts=None`). The blocking
        `PermissionError(errno=13)` came from `_replace` calling `os.fsync` on a
        *directory* handle (`projects.py:625`), which Windows rejects
        (`FlushFileBuffers` is invalid on a directory) — and it ran inside the
        `_lock` block, so `_lock`'s `OSError` handler mislabeled it "manifest
        lock failed". Fixes that landed the green:
        (1) guard the directory `fsync` to POSIX in `_replace` (`8e3cd95d`,
        matching the existing `_fsync_directory` helpers);
        (2) converge the lock acquire on the proven `_cache_lock` primitive —
        write placeholder byte before `msvcrt.locking`, no `fsync`/`O_CLOEXEC`
        before `LockFile` (`4484deb6`);
        (3) retry the Windows delete-pending `EACCES` on concurrent lock-file
        open in both `_cache_lock` and `_open_and_acquire` (`5865db06`);
        (4) `DOC-IDENTITY` advisory path separators via `.as_posix()`
        (`2ddbe752`). `LITAI_LOCK_DIAG` diagnostic and its CI env var removed
        once green. All Windows jobs (lint/OpenSpec/wheel, tests 2/3, 3/3) pass;
        the long tests-1/3 full-suite shard runs clean. Backported to
        `release/0.8.x` for the 0.8.1 patch.

### [x] CLI-DEBUG-002 — `--debug` injects unplanned debug-spec-map authority and aborts generation

- **Priority:** P0 (0.8.0 break-glass)
- **GitHub issue:** [#212](https://github.com/NVIDIA-dev/literate-ai/issues/212)
- **Owner:** `src/literate_ai/adapters/generation_preparation.py`
- **Direction:** `--debug` injects `debug-spec-map` into coding-agent authority
      segments as `LOCAL_SKILL`, but the plan doesn't select diagnostic skills.
      The context validator rejects it as `authority_unselected`.
- **Conclusion:** Debug instrumentation is framework-owned. The debug skill is
      already added through the coding-CLI skill closure
      (`coding_cli.py:1419`) where it enters the prompt as part of the
      framework envelope. Removed the authority-segment injection in
      `_node_authority_segments`. Commit `8eba2156`.
- **Evidence:**
  - [x] 46 focused tests pass (spec_map, cli_debug, application_generation).

### [x] VERIFY-001 — `litai verify` cannot validate mixed-language projects with per-Component Flavor overrides

- **Priority:** P0 (0.8.0 break-glass)
- **GitHub issue:** [#211](https://github.com/NVIDIA-dev/literate-ai/issues/211)
- **Owner:** `src/literate_ai/cli/verify.py`, `literate.project.json` schema,
      `contracts/projects.py`
- **Direction:** `litai verify` recomputes every lock using only project
      `default_flavor_selectors` with an empty `--flavor` list.
      `default_flavor_selectors` rejects coordinate-scoped selectors. A
      mixed-language project whose JavaScript Component was locked with
      explicit `--flavor=-lang-python --flavor=+lang-javascript` overrides
      always reports that lock as stale.
- **Conclusion:** The project needs an authored way to persist per-Component
      Flavor selections. `component_flavor_selectors` is the explicit
      per-Component map; its configured selectors precede one invocation's
      explicit CLI selectors so callers can deliberately override persisted
      preferences. Lock, plan, generate, rebuild, test, and verify consume the
      same merged selector sequence.
- **Depends on:** none beyond current `main`
- **Implementation:**
  - [x] Design and add `component_flavor_selectors` to
        `literate.project.json` as an optional field mapping Component
        paths to their override selector lists.
  - [x] Resolve persisted selectors in the shared project adapter and consume
        them from lock, plan/generate, Standard/external rebuild, worker
        dispatch, build/test, and verify paths.
  - [x] Reject escaping Component paths and preserve explicit CLI selectors
        after persisted selectors.
  - [x] Validate that a lock produced with per-Component overrides passes
        direct lock, plan, and project verification gates.
- **Evidence:**
  - [x] A mixed-language downstream project with per-Component Flavor overrides
        passes `litai verify` when the overrides are persisted in
        project configuration.
  - [x] The same downstream JavaScript Component passes direct `litai lock
        --check` and `litai plan` without repeating selectors on the CLI.
  - [x] 66 focused CLI/project tests and 20 subtests pass; focused Ruff check
        and format check pass.

### [x] DOC-IDENTITY-001 — Downstream projects must establish their own identity, not bleed through to the parent

- **Priority:** P0 (0.8.0 break-glass)
- **Owner:** init template (`project_initialization.py` seeded docs),
      documentation-authoring skill, `litai update` doc-inheritance boundary,
      release acceptance
- **Direction:** User-directed: a downstream project's `docs/user/getting-started.md`
      reads as a Literate AI framework tutorial rather than as the product's own
      documentation. The init template seeds entirely framework-centric content
      (generic `litai rebuild` instructions, the Spec→Recipe→Source flowchart,
      `litai init --from` guidance). A developer opening "Getting Started" for
      `telemetry-dashboard` is told how to drive the framework, not what the service
      is, how to install it, or how to use it. Observed at
      `github.com/example-org/telemetry-dashboard/blob/main/docs/user/getting-started.md`.
- **Conclusion:** The seeded getting-started document must require the project to
      establish its own identity before framework mechanics. Specifically:
  1. The init template's `docs/user/getting-started.md` should open with clear
     placeholders that force the project to state what it is, what it does, and
     how a user installs and operates it — not the framework that built it.
     Framework workflow instructions belong in a separate section or document
     (e.g. "Contributing" or "Development workflow"), not in the product's
     user-facing front door.
  2. Self-describing should be an inheritable skill/goal: every project derived
     from literate-ai should inherit the expectation that its documentation
     describes itself, with the parent's documentation only bleeding through
     when the child has no documentation for a topic at all.
  3. `litai update` must not silently clobber project-specific documentation
     identity — if a child has customized getting-started.md, the update should
     surface that as a conflict for human review, not overwrite it.
  4. The release process should include a self-documentation acceptance check:
     does the project's getting-started doc actually describe this project?
     A document that is byte-identical to the parent template (or mentions only
     `samples/hello-component`) should fail the release gate or produce an
     advisory.
- **Depends on:** [DOC-INSTALL-001](../../roadmap/active-work.md#x-doc-install-001-require-runnable-service-installation-documentation)
      (already landed; this extends its principle from services to all projects)
- **Implementation:**
  - [x] Rewrite the init template's `getting-started.md` to lead with
        project-identity placeholders: "What is this project?", "How do I
        install and run it?", "What does it do?" — followed by a clearly
        marked framework-workflow section for contributors. Also rewrote
        `docs/README.md` template. Commit `b441d5b2`.
  - [x] Add a documentation-authoring skill requirement (step 4, both copies
        byte-identical): child projects must describe themselves;
        parent-inherited documentation is a fallback, not a substitute for
        project identity. SkillEvaluator passes.
  - [x] Verify `litai update` surfaces doc-identity edits as conflicts
        rather than silently reverting them. The three-way classification
        (`ProjectUpdateClassification.CONFLICT`) already handles this:
        any file modified both locally and upstream is surfaced as a
        conflict for human review. No code change needed.
  - [x] Add an advisory or fail-closed check to the release process for
        docs that are still the unmodified parent template. `litai project
        validate` now emits a `project.doc_identity_placeholder` advisory
        for each doc file containing the template documentation-identity marker. Commit
        `4f1ecaf1`.
- **Evidence:**
  - [x] An initialized child project's getting-started.md opens with
        "What is this project?" and DOC-IDENTITY placeholders, not the
        framework's tutorial. `test_init_creates_a_valid_starter_taxonomy_
        from_below` passes with the new assertions.
  - [x] `litai update` does not silently clobber a customized
        getting-started.md — the existing three-way classification surfaces
        it as CONFLICT when both sides changed.
  - [x] A `litai project validate` on a project whose getting-started.md
        still contains the template placeholder emits
        `project.doc_identity_placeholder` advisory. Tested in
        `test_init_creates_a_valid_starter_taxonomy_from_below`.

### [x] RELEASE-015 — Close the critical RelEng skill gaps around the cut

- **Priority:** P0 (0.8.0 break-glass; SDLC harness)
- **Owner:** `skills/agent/release-project/` nested deltas,
      `src/literate_ai/project_releases.py`, tracker inspect argv, and
      `docs/architecture/project-releases.md`
- **Direction:** The cut/publish spine is already complete. Agents fail as
      release engineers because backport, evidence, default-branch advance,
      live CI go/no-go, post-publish identity smoke, trunk landing, and
      descendant notify are CLI verbs or prose — not nested skills they are
      told to open. Address the critical (dev-loop) findings from the
      RelEng gap analysis. Do not invent staging/prod deploy, signing,
      GitLab publication, yank, advisories, or LTS windows in this item.
- **Conclusion:** Nest short wrap-Python deltas under `release-project/`
      (backport, evidence, advance, ci-status, verify-published,
      notify-descendants). Add `litai release verify-published` as a
      read-only remote identity check. Name CI and land argv on
      `litai project tracker inspect`. Land changes through a nested
      `develop-in-production-workflow/staging/dev/land` skill. Survey
      other developers' green PRs at the start of each cycle and
      leftover worktrees/branches at the end via
      `litai project peer-work` and `survey-peer-work`. Keep
      `## Unreleased` current as queue items close. Remove the dangling
      `workflows/production/hotfix/workflow.md` citation. Do not grow the
      parent `release-project` SKILL.md into a second implementation.
      Catalog and init-template copies stay byte-identical.
- **Depends on:** current `main`; existing `litai release` verbs
- **Implementation:**
  - [x] Nested `release-project` skills wrapping existing CLI plus
        `verify-published`
  - [x] Tracker inspect names `ci_status`, `land_create`, and `land_merge`
  - [x] `develop-in-*/land` plus Unreleased changelog discipline
  - [x] `peer-work` start/end survey (green PRs; leftover worktrees/branches)
  - [x] Architecture/CLI inventory, hotfix citation, skills.md table
  - [x] Catalog/template parity and focused tests
- **Evidence:**
  - [x] Focused `tests.e2e.test_project_releases` and tracker inspect tests
  - [x] `tests.smoke.test_cli_help` command-reference inventory
  - [x] Catalog/template nested skills byte-identical; `make skills-check`
        SkillEvaluator 20260829151821–20260829151824 (8 skills, 6/6 each).
  - [x] Documentation-authority marker current after architecture edits
        `docs/architecture/design-traceability.md`
        `sha256:5b66f9a8f1353e50c8f615290cbf1f3c753e99212fc1a492e9f15d7ca323a3e8`.
        Lifecycle-driver pin
        `sha256:5f51fd5f5731cc3a085670138031ec16d5826eddfef48997af154581b6a3ea84`.

### [x] RELEASE-BRANCHING-002 — Refuse a versioned release cut on the default branch

- **Priority:** P0
- **Owner:** `skills/agent/release-project/SKILL.md`, `src/literate_ai/project_releases.py`,
      and `docs/architecture/project-releases.md`
- **Direction:** A versioned cut has twice been planned and published from `main`
      because `release-project` said "default branch when its tip *is* the release."
      That exception contradicts
      [`docs/history/roadmap/release-branching-model.md`](release-branching-model.md).
      Agents follow the skill; the CLI did not stop them. Fail closed on the
      default branch as a *publish* checkout. Do not also leave branch creation as
      a raw Git homework step: that is how the cut was skipped twice. Least
      astonishment is that `prepare` cuts `release/<major>.<minor>.x` when the
      line does not exist.
- **Conclusion:** When `literate.release.json` declares `default_branch`:
      `plan` stays read-only. On the matching `release/<major>.<minor>.x` line it
      records `release_line.create: false`. On `default_branch` it records
      `create: true` only when that line is absent locally and on the remote; if
      the line already exists it fails `release.default_branch_cut_forbidden`
      (checkout / backport, then re-plan). Any other name, including a per-patch
      `release/x.y.z`, fails `release.branch_not_release_line`. `prepare` with
      `create: true` creates the line from the plan revision (no force), checks it
      out, then writes declared paths. `check` and `publish` require that named
      line, not the plan's `source_branch` when that is still the trunk. Projects
      that omit `default_branch` stay checkout-agnostic and omit `release_line`.
      Sync the init-template skill copy. Do not retag `v0.7.0`.
- **Depends on:** [RELEASE-BRANCHING-001](../../roadmap/active-work.md#x-release-branching-001-adopt-trunk-based-development-with-cut-time-release-branches)
      (model); `origin/release/0.7.x` already exists at `v0.7.0`.
- **Implementation:**
  - [x] Delete the skill's "default branch when its tip is the release" exception
        in the catalog and init template.
  - [x] Fail closed when `default_branch` is declared and the checkout is not the
        matching line *and* that line already exists.
  - [x] `plan` on `default_branch` when the line is absent records
        `release_line.create: true`; optional `release_line` on
        `literate-ai/release-plan@1`.
  - [x] `prepare` creates and checks out that line; `check` / `publish` compare
        against the cut name.
  - [x] Record the contract in the protocol, branching model, skills, CLI help,
        and changelog.
- **Evidence:**
  - [x] Planning on `main` when `release/x.y.x` is missing succeeds with
        `create: true`; the same plan fails `release.default_branch_cut_forbidden`
        once the line exists; a per-patch `release/x.y.z` name fails
        `release.branch_not_release_line`; `prepare` leaves the operator on the
        new line; `check` accepts that line even when `source_branch` is still
        the trunk. `tests.e2e.test_project_releases` 52 tests OK.
  - [x] Catalog and template `release-project` skills are byte-identical;
        `make skills-check` passes (SkillEvaluator 20260827180622).
  - [x] Focused `tests.e2e.test_project_releases` pass; `make lint` and
        `make skills-check` are current; lifecycle-driver pin
        `sha256:c9d8f0a5ad8bb71c91d69b0045f5c68c9a2a2692f0e69b5d6b1192dfa69c4457`.

### [x] SOURCE-INTELLIGENCE-001 — Restore opt-in external source intelligence

- **Authority:** [ADR 0019](../../decisions/0019-opt-in-external-source-intelligence.md)
- **Priority:** P0 downstream release blocker
- **Owner:** project source-intelligence adapter, CLI, validation, verification,
  and lifecycle boundaries
- **Direction:** Partially supersede ADR 0016 for explicit downstream use. Keep
  `provider_id: none` as the dependency-free default while restoring bounded
  `codegraph-cli` sync and check behavior for projects that opt in. Do not restore
  provider installation, package dependencies, worker companion capabilities, or
  an ambient framework prerequisite.
- **Downstream evidence:** Physics Workbench sample cannot advance its Literate AI parent past
  `809f2112` while its required source-intelligence policy is rejected.
- **Implementation:**
  - [x] Restore the project adapter and `project source-intelligence sync|check`.
  - [x] Honor stage-specific required/off policy in validation, `litai verify`, and
        lifecycle preflight.
  - [x] Cover default-none, missing binary, malformed/stale/tampered evidence, and
        cross-platform project paths.
  - [x] Open equivalent pull requests against `main` and `release/0.6.x`:
        [#182](https://github.com/NVIDIA-dev/literate-ai/pull/182) and
        [#183](https://github.com/NVIDIA-dev/literate-ai/pull/183).
- **Evidence:**
  - [x] Focused source-intelligence tests pass.
  - [x] Repository Python, lint, format, documentation, wheel, and applicable
        sample gates pass on both release lines. GitHub CI was green on
        [#182](https://github.com/NVIDIA-dev/literate-ai/pull/182) (`main`,
        merge `3d758979`) and
        [#183](https://github.com/NVIDIA-dev/literate-ai/pull/183)
        (`release/0.6.x`, merge `7c882130`).

### [x] LOCK-003 — Keep large Component-lock diffs bounded without false rejection

- **Pull requests:** [#176](https://github.com/NVIDIA-dev/literate-ai/pull/176)
  (`main` / pending 0.7.0) and
  [#177](https://github.com/NVIDIA-dev/literate-ai/pull/177)
  (`release/0.6.x`)
- **Priority:** P0 release blocker for downstream lock review
- **Owner:** framework core Component-lock comparison and CLI review evidence
- **Direction:** A valid downstream root lock can exceed the semantic diff walk's
  internal 512-entry queue even when its actual reviewable differences are bounded.
  File the fix against pending 0.7.0 and backport it for the next 0.6.x patch.
- **Conclusion:** `_semantic_diff` incorrectly treats queued traversal work as emitted
  differences. Bound completed differences independently, retain a separate deterministic
  traversal-work ceiling, and fail closed only when the actual review result or safe
  traversal budget is exceeded. Do not increase or remove bounds and do not special-case
  the downstream project.
- **Depends on:** current `main` (0.7.0 authority); latest v0.6.x release tag for the
  backport branch
- **Implementation:**
  - [x] Separate emitted-difference and traversal-work accounting.
  - [x] Add a large mostly-equal lock regression that previously failed while retaining
        genuine over-limit failure coverage.
  - [x] Forward-port to pending 0.7.0 and backport the same reviewed fix to 0.6.x.
  - [x] Keep `make samples` fail-closed on missing live pins while unit-test
        invocations of `sample_runner.main()` stay optional per ADR 0017, then
        refresh documentation authority so PR #176 CI can go green.
  - [x] Re-pin the sample-host lifecycle driver and sample-test-runner identities
        after the sample-runner live-pin split, then refresh documentation
        authority again.
- **Evidence:**
  - [x] `make target-matrix-check`, `make lint`, and `make format-check` pass.
  - [x] `make python-check` and sample-composition documentation review pass on
        the PR #176 head, including the three sample-runner tests that currently
        fail closed without `CODING_CLI` / `LITAI_LIVE_MODEL`.
  - [x] Pull requests #176 and #177 report the intended bases and shared fix.

### [x] DOC-RECONCILE-001 — Reconcile project documentation with current authority and evidence

- **Owner:** project documentation workflow and coding-CLI boundary
- **Direction:** Add a first-class `litai project documentation-update` workflow that inventories declared documentation, current Component/interface authority, project configuration, locks, and the current receipt; produces a bounded read-only drift plan by default; and applies reviewed documentation-only edits only with explicit model-egress and write authorization.
- **Acceptance:**
  - [x] The default command writes nothing and invokes no model.
  - [x] The plan identifies deterministic stale-command and retired source-intelligence candidates; semantic status, compatibility, roadmap, and link reconciliation is delegated to the bounded apply prompt over validated authority rather than guessed from generated source.
  - [x] `--apply --allow-model-egress` confines model writes to declared Markdown documentation roots and rejects specification, lock, receipt, generated-source, executable, and secret-bearing paths.
  - [x] Apply leaves the documentation authority marker stale until the operator reviews changes and runs `litai project documentation-review --record` explicitly.
  - [x] Unit and CLI tests cover no-op, drift, malformed model output, out-of-scope writes, secret egress/replacements, concurrent identities, rollback, and successful documentation-only reconciliation; `make python-check` passes.

### [x] DOC-INSTALL-001 — Require runnable service installation documentation

- **Owner:** documentation authoring skill and initialized documentation guidance
- **Direction:** Product documentation for deployable services must take a new user from prerequisites through installation, configuration, startup, readiness, and one verified request; framework build instructions alone are not a product getting-started path.
- **Conclusion:** Extend the documentation-authoring workflow with an audience-specific service-installation acceptance check and seed initialized getting-started guidance so derived projects replace the portable sample flow with real installation and operation steps before claiming usability.
- **Evidence:**
  - [x] The documentation skill distinguishes contributor build instructions from end-user service installation and requires explicit unsupported/missing steps rather than placeholders.
  - [x] Initialized getting-started guidance tells service projects to document artifacts, configuration, credentials, persistence, startup order, health checks, verification, upgrades, and uninstall/cleanup.
  - [x] SkillEvaluator passes both changed skill copies; project validation, documentation review, and the 60-test initialization/project/version suite pass.

### [x] PR-PLAN-LOCKED-ASSETS — Bind locked authored assets when Standard plan omits assets

- **Priority:** P0 (sample `plan` generation-key mismatch)
- **Pull request:** [#210](https://github.com/NVIDIA-dev/literate-ai/pull/210);
      also merged onto [#204](https://github.com/NVIDIA-dev/literate-ai/pull/204)
- **Branch / base:** `fix/standard-plan-bind-locked-assets` → `main`; merged into
      `feat/cli-sdlc-debug`
- **Owning closed item:** [CONTEXT-001](../../roadmap/active-work.md#x-context-001-admit-locked-local-asset-metadata-to-bounded-generation-context)
- **Owner:** `StandardProjectApplicationService.plan`,
      `authored_assets_from_lock`
- **Direction:** Public `plan` defaulted `assets=()`, while preparation still
      reconstructs `AuthoredBinaryAsset` identities from the lock.
- **Conclusion:** When `assets is None`, bind `authored_assets_from_lock(lock)`.
      Do not treat explicit `assets=()` as omit. Adapter
      `_locked_authored_assets` CAS-admits then reuses the same helper.
- **Evidence:**
  - [x] Focused units `test_component_execution_planning` and
        `test_standard_project_services.test_omitted_plan_binds_locked_asset_identities`
        under `LITAI_SESSION_ID=dev` (session venv).
  - [x] Pull request [#210](https://github.com/NVIDIA-dev/literate-ai/pull/210)
        targeting `main`; implementation also merged onto #204.

2026-08-28 tracker reconciliation, then break-glass the same day: **every remaining
open queue item on `main` is 0.8.0 in-scope**, including breaking changes, because
no major has shipped and this cut is treated as the first major-equivalent.
That is not durable SemVer advice. [RELEASE-012](../../roadmap/active-work.md#release-012-080-unreleased-product-and-protocol-scope)
owns the declaration.

**Still not a merge into `main`:** living patch lines `origin/release/0.7.x`
(0.7.3 / [RELEASE-013](../../roadmap/active-work.md#release-013-agent-owned-patch-content-remaining-proc-kill-call-sites-as-073)),
`origin/release/0.6.x`, and `origin/release/0.5.x`. Deleted as stale (not merged
into `main`): `planning/0.5.0-scope` (contained in `release/0.5.x`;
[FORWARD-PORT-001](../../roadmap/active-work.md#x-forward-port-001-reconcile-shipped-fixes-missing-from) already
closed), `release/0.5.0` / `0.5.1` / `0.5.2` (contained in `release/0.5.x`;
`v0.5.0` and `v0.5.1` remain tagged), `ci/0.6.3-gate` (contained in
`release/0.6.x`), and `wip/test-cache-001-dispatch` (`c0439340` obsolete).
Open process-tree GitHub issues
[#71](https://github.com/NVIDIA-dev/literate-ai/issues/71),
[#72](https://github.com/NVIDIA-dev/literate-ai/issues/72),
[#74](https://github.com/NVIDIA-dev/literate-ai/issues/74),
[#77](https://github.com/NVIDIA-dev/literate-ai/issues/77),
[#79](https://github.com/NVIDIA-dev/literate-ai/issues/79) stay owned by
[PROC-KILL-001](../../roadmap/active-work.md#proc-kill-001-windows-process-tree-kill-misses-late-spawned-grandchildren);
the remaining patch cut is 0.7.3 on `release/0.7.x`, while `main` already carries
the in-package Job Object binds.

### [x] SKILL-HIERARCHY-001 — Nest release and workflow skills; wrap Python

- **Priority:** P0
- **Pull request:** [#179](https://github.com/NVIDIA-dev/literate-ai/pull/179)
- **Owner:** `skills/agent/`, `workflows/`, `routing/`, init template
- **Direction:** Release-engineering and workflow skills were siblings that restated
  Python and claimed nesting in prose. Use the filesystem as the scoping mechanism:
  skills inherit from parent `SKILL.md` files, workflows nest under production, and
  agent skills wrap `litai` instead of duplicating it in the prompt.
- **Conclusion:** Parent `skills/agent/SKILL.md` states wrap-Python and delta
  inheritance. Development postures nest as
  `develop-in-production-workflow/staging/dev`. Generation workflows and routing
  match, with `routing.json` as the directory sentinel. `release-project` and
  `bind-lifecycle-evidence` wrap CLI/rebuild. Catalog vs init-template drift on
  `release-project` is closed. Flavor cross-axis co-requisites (`swift` plus OS
  toolchains) stay siblings. Remaining follow-up: `convert-project` still restates the
  convert harness (thin with PR #174); `cmake-build-system` is a generation-prompt
  exception at 165 lines; `package-*` Flavors stay siblings because they are
  different package axes, not nested realizations.
- **Depends on:** catalog nested-item ownership already implemented in
  `repository_catalogs.py`
- **Implementation:**
  - [x] Add `skills/agent/SKILL.md` and nest the three development postures.
  - [x] Nest `workflows/production/staging/dev` and matching `routing.json`.
  - [x] Thin `release-project` to wrap `litai release`; sync the init template.
  - [x] Thin `bind-lifecycle-evidence` to wrap rebuild/lock/evidence.
  - [x] Forward-port GitHub CI `release/**` push triggers onto this line (was only
        on `release/0.6.x`).
  - [x] Align routing policies to directory-owned `routing.json` sentinels.
  - [x] Close `record-user-directed-work` catalog/template drift.
  - [x] `make python-check` and `make skills-check` pass; documentation and
        lifecycle-driver authority re-recorded.
- **Evidence:**
  - [x] Nested catalog test proves parent `agent` owns only its `SKILL.md`.
  - [x] Init copies the parent agent skill and nested default workflow.
  - [x] Catalog and template copies of the nested agent skills are byte-identical.
  - [x] Pull request [#179](https://github.com/NVIDIA-dev/literate-ai/pull/179)
        merged to `main` as
        [`31a8e607`](https://github.com/NVIDIA-dev/literate-ai/commit/31a8e607fb46ec446e49175f2a86c3622f84da65)
        on 2026-08-27.

### [x] PR-182 — Restore opt-in project source intelligence

- **Pull request:** [#182](https://github.com/NVIDIA-dev/literate-ai/pull/182)
- **Branch / base:** `feature/opt-in-source-intelligence` → `main`
- **Owning queue item:** [SOURCE-INTELLIGENCE-001](../../roadmap/active-work.md#x-source-intelligence-001-restore-opt-in-external-source-intelligence)
- **Completion evidence:** GitHub CI green (15/15). Merged to `main` as
  [`3d758979`](https://github.com/NVIDIA-dev/literate-ai/commit/3d758979be972501d3dad217988ebb24b8f37d72)
  on 2026-08-27 after the untagged 0.7.0 cut was not published.

### [x] PR-183 — Backport opt-in project source intelligence to 0.6.x

- **Pull request:** [#183](https://github.com/NVIDIA-dev/literate-ai/pull/183)
- **Branch / base:** `backport/opt-in-source-intelligence-0.6` → `release/0.6.x`
- **Owning queue item:** [SOURCE-INTELLIGENCE-001](../../roadmap/active-work.md#x-source-intelligence-001-restore-opt-in-external-source-intelligence)
- **Completion evidence:** GitHub CI green (15/15). Merged to `release/0.6.x` as
  [`7c882130`](https://github.com/NVIDIA-dev/literate-ai/commit/7c8821300f98630f0e682b24ae5d18be24873716)
  on 2026-08-27.

### [x] PR-176 — Fix large Component lock semantic diffs

- **Pull request:** [#176](https://github.com/NVIDIA-dev/literate-ai/pull/176)
- **Branch / base:** `fix/component-lock-diff-limit` → `main`
- **Owning queue item:** [LOCK-003](../../roadmap/active-work.md#x-lock-003-keep-large-component-lock-diffs-bounded-without-false-rejection)
- **Completion evidence:** merged to `main` as
  [`48ab0cae`](https://github.com/NVIDIA-dev/literate-ai/commit/48ab0caec6faa13a73bbc258d466bfa063bbab70)
  on 2026-08-27. Identity re-pin `c11eaea0` made GitHub CI green (15/15).

### [x] PR-CONVERT-FW-007 — Honor language Flavor command-profile entrypoints

- **Pull request:** [#180](https://github.com/NVIDIA-dev/literate-ai/pull/180)
- **Branch / base:** `fix/language-command-profile-entrypoint` → `main`
- **Owning queue item:** [CONVERT-FW-007](../../roadmap/active-work.md#x-convert-fw-007-plangenerate-project-local-language-flavors-from-their-command-profile)
- **Completion evidence:** merged to `main` as
  [`fc61c8b8`](https://github.com/NVIDIA-dev/literate-ai/commit/fc61c8b80fbc590b65c40ffb97a2494955b47ff3)
  on 2026-08-27 after merging #179 and re-pinning identities (`56ffd5c0`).

### [x] PR-174 — Convert inspect-then-wrap (`repo-man`) onto current main

- **Pull request:** [#174](https://github.com/NVIDIA-dev/literate-ai/pull/174)
- **Branch / base:** `fix/0.6.0-codegraph-merge-ci` → `main`
- **Completion evidence:** merged to `main` as
  [`06bfd1e8`](https://github.com/NVIDIA-dev/literate-ai/commit/06bfd1e8c7c9511be0158e970512279d0dd9f3b9)
  on 2026-08-27 after merging #173 and re-pinning identities (`793deab8`).

### [x] PR-173 — Require service installation documentation

- **Pull request:** [#173](https://github.com/NVIDIA-dev/literate-ai/pull/173)
- **Branch / base:** `feature/service-installation-documentation` → `main`
- **Completion evidence:** merged to `main` as
  [`444dac06`](https://github.com/NVIDIA-dev/literate-ai/commit/444dac06c3887ac7299f6a43226ea7bd88d3a7a3)
  on 2026-08-27.

### [x] PR-170 — Release 0.7.0 evidence-bound release closure

- **Pull request:** [#170](https://github.com/NVIDIA-dev/literate-ai/pull/170)
- **Branch / base:** `devin/1787696693-release-evidence-0.7.0-plan` → `main`
- **Owning queue item:** [RELEASE-009](../../roadmap/active-work.md#release-009-qualify-and-publish-070-with-full-gate-fan-out)
- **Completion evidence:** merged to `main` as
  [`c132eea0`](https://github.com/NVIDIA-dev/literate-ai/commit/c132eea05e020cdee58bae55029dbd105032687a)
  on 2026-08-26. GitHub run
  [`32978891322`](https://github.com/NVIDIA-dev/literate-ai/actions/runs/32978891322)
  on `a924ef51` was green. Live fan-out remaining evidence stays on
  [GENERATION-011](../../roadmap/active-work.md#generation-011-pin-live-qualification-to-an-explicit-user-configured-cli-and-model).

### [x] PR-169 — Add documentation reconciliation workflow

- **Pull request:** [#169](https://github.com/NVIDIA-dev/literate-ai/pull/169)
- **Branch / base:** `feature/documentation-update-workflow` → `main`
- **Completion evidence:** merged to `main` as
  [`4dfb2830`](https://github.com/NVIDIA-dev/literate-ai/commit/4dfb28305cc4be74e8c492ff34b1c9c5a39e43e5)
  on 2026-08-26.

### [x] PR-166 — Retry generated-test contract failures during source generation

- **Pull request:** [#166](https://github.com/NVIDIA-dev/literate-ai/pull/166)
  (superseded by [#172](https://github.com/NVIDIA-dev/literate-ai/pull/172))
- **Branch / base:** `fix/retry-generated-test-contracts` → `main`
- **Completion evidence:** #166 closed; #172 merged to `main` as
  [`3db30191`](https://github.com/NVIDIA-dev/literate-ai/commit/3db301911100b4681a1eae77b24a7e28982c7d89)
  on 2026-08-26.

### [x] PR-CI-060 — Repair CodeGraph-removal merge leftovers on 0.6.0 CI

- **Pull request:** [#168](https://github.com/NVIDIA-dev/literate-ai/pull/168)
- **Branch / base:** `fix/0.6.0-codegraph-merge-ci` → `main`
- **Owning queue item:** [CODEGRAPH-DEPENDENCY-001](../../roadmap/active-work.md#x-codegraph-dependency-001-remove-the-source-graph-indexer-from-the-product)
- **Completion evidence:** fast-forward merged to `main` as `8d84dbda`. GitHub
  run [`32890626746`](https://github.com/NVIDIA-dev/literate-ai/actions/runs/32890626746)
  on that SHA was green, including Windows lint/OpenSpec/wheel after the
  wheel-smoke leftover fix.

### [x] PR-158 — Keep Windows/macOS CodeGraph init and persistent-service children alive

- **Pull request:** [#158](https://github.com/NVIDIA-dev/literate-ai/pull/158)
- **Completion evidence:** merged as `345e8af3` on 2026-08-25, including the
  hosted-runner timeout skips for macOS persistent-service readiness and Windows
  snapshot-replication CodeGraph init.

### [x] PR-152 — Add explicit model pinning to sample runs

- **Pull request:** [#152](https://github.com/NVIDIA-dev/literate-ai/pull/152)
- **Completion evidence:** merged as `1db3e811` on 2026-08-24.

### [x] PR-153 — Add persistent service acceptance

- **Pull request:** [#153](https://github.com/NVIDIA-dev/literate-ai/pull/153)
- **Completion evidence:** merged as `d5407b48` on 2026-08-24.

### [x] PR-154 — Add locked Cargo lifecycle support

- **Pull request:** [#154](https://github.com/NVIDIA-dev/literate-ai/pull/154)
- **Completion evidence:** merged as `7fd3356d` on 2026-08-24.

### [x] PR-155 — Reconcile managed source SBOM authority

- **Pull request:** [#155](https://github.com/NVIDIA-dev/literate-ai/pull/155)
- **Completion evidence:** merged as `483b72bf` on 2026-08-24.

### [x] PR-145 — Add authenticated Cursor inherited-session handoff

- **Pull request:** [#145](https://github.com/NVIDIA-dev/literate-ai/pull/145)
- **Completion evidence:** merged as `9756fe69` on 2026-08-24.

### [x] PR-149 — Show update progress and follow a moving parent

- **Pull request:** [#149](https://github.com/NVIDIA-dev/literate-ai/pull/149)
- **Completion evidence:** merged as `fb25a855` on 2026-08-24.

### [x] PR-151 — Record UPDATE-CONFLICT-RENDER-001 for conflict diffs

- **Pull request:** [#151](https://github.com/NVIDIA-dev/literate-ai/pull/151)
- **Completion evidence:** merged as `7b62975f` on 2026-08-24.

### [x] PR-156 — Repair 0.6.0 CI pin, CRLF, and temp-dir gates

- **Pull request:** [#156](https://github.com/NVIDIA-dev/literate-ai/pull/156)
- **Completion evidence:** merged as `665eff80` on 2026-08-24.

### [x] PR-44 — Add structured profiling and skill-edit scanning

- **Pull request:** [#44](https://github.com/NVIDIA-dev/literate-ai/pull/44)
- **Branch / base:** `add-skillspector-hook` → `main`
- **Completion evidence:** merged as `5ef0b717acbaa51bd8cb053fad2a54624814158b` on
  2026-08-15. Historical repair notes remain as landed context; this PR is no longer
  open.

### [x] PR-45 — Redesign dependency-aware test dispatch

- **Pull request:** [#45](https://github.com/NVIDIA-dev/literate-ai/pull/45)
- **Branch / base:** `worktree-release-check-run` → `main`
- **Completion evidence:** merged as `0acfb29f892d438a3f12f933fbdd5c16f2e13724`
  after all twelve GitHub checks passed, including three-platform sample composition
  and the 1h24m Windows full non-live gate.

### [x] PR-16 — Build and verify native sample packages

- **Pull request:** [#16](https://github.com/NVIDIA-dev/literate-ai/pull/16)
- **Branch / base:** `codex/native-packaging` → `main`
- **Completion evidence:** merged into `main` as `659d1baa58ccd7bffa8a54fe4bedf445c943660c`
  after its documentation, skill, three-OS sample-composition, installed-wheel, explicit
  native-toolchain, and non-live Python qualification completed.

### [x] PR-15 — Add OpenCode coding CLI support

- **Pull request:** [#15](https://github.com/NVIDIA-dev/literate-ai/pull/15)
- **Branch / base:** `feature/opencode-support` → `main`
- **Depends on:** PR-16 (completed)
- **Completion evidence:** merged into `main` through aggregate PR #18; GitHub records
  merge commit `da23d1bf79cd37082b8c09af6d4c239fba4a7b30` for this parent history.

### [x] PR-17 — Enforce detailed roadmap lifecycle

- **Pull request:** [#17](https://github.com/NVIDIA-dev/literate-ai/pull/17)
- **Branch / base:** `feature/roadmap-lifecycle` → `feature/opencode-support`
- **Depends on:** PR-15
- **Completion evidence:** the complete branch history landed through aggregate PR #18;
  the intermediate PR was closed as superseded after every commit became reachable from
  `main`.

### [x] PR-18 — Reconcile required source-index update evidence

- **Pull request:** [#18](https://github.com/NVIDIA-dev/literate-ai/pull/18)
- **Branch / base:** `fix/update-source-index` → `main`
- **Depends on:** PR-17
- **Completion evidence:** retargeted as the complete, already-qualified aggregate and
  merged into `main` as `034d03d1240320efe7ad27999eea8c84316479ba` after the local
  from-zero Python gate passed all 2,099 tests with 26 intentional skips.

### [x] PR-20 — Preserve descendant qualification authority

- **Pull request:** [#20](https://github.com/NVIDIA-dev/literate-ai/pull/20)
- **Branch / base:** `fix/descendant-qualification-contracts` → `main`
- **Completion evidence:** the complete GitHub matrix passed and the branch merged into
  `main` as `9e212a48cb5e2dd2ff64b00f047ecfd07d9b1bae`, preserving graph-bound
  descendant initialization, fresh local qualification evidence, and the cross-platform
  command/fan-out repairs.

### [x] PR-26 — Report initialization prerequisites

- **Pull request:** [#26](https://github.com/NVIDIA-dev/literate-ai/pull/26)
- **Branch / base:** `codex/sample-taxonomy-explicit-hello` → `main`
- **Depends on:** PR-20 (completed)
- **Completion evidence:** merged into `main` as `38df24dd289198160533a9c1eff0e34af9240a97`
  after wheel smoke component-coordinate fix, init prereq reporting, sample taxonomy
  enforcement, and CodeGraph dependency documentation.

### [x] PR-25 — Guard generation with graph-bound lock evidence

- **Pull request:** [#25](https://github.com/NVIDIA-dev/literate-ai/pull/25)
- **Branch / base:** `codex/lifecycle-authority-graph` → `main`
- **Depends on:** PR-26 (completed)
- **Completion evidence:** merged into `main` as `371cc55fa745639f1df9eb7b84c254f659bd94f7`
  after rebasing onto PR-26, resolving catalog inheritance and project-initialization
  conflicts, adding AppArmor mock isolation and geteuid portability fix.

### [x] PR-21 — Reject incompatible OpenCode command surfaces before generation

- **Pull request:** [#21](https://github.com/NVIDIA-dev/literate-ai/pull/21)
- **Branch / base:** `fix/opencode-capability-preflight` → `main`
- **Depends on:** PR-26 and PR-25 (both completed)
- **Completion evidence:** merged into `main` as `8a7dda699c005db151f7859b91fda45637457b5f`
  after fixing ruff E501/I001 lint violations and resolving CHANGELOG and identity
  conflicts from the PR-25/26 merge.

### [x] PR-27 — Reconcile the active pull-request queue

- **Pull request:** [#27](https://github.com/NVIDIA-dev/literate-ai/pull/27)
- **Branch / base:** `codex/pr-queue-and-next` → `main`
- **Depends on:** PR-26 (completed)
- **Completion evidence:** landed as part of the 0.3.0 release reconciliation; PR-26,
  PR-25, and PR-21 are all merged and recorded above.

### [x] AUTHORITY-RECORDING-001 — Make final authority recording an explicit workflow

- **Priority:** P0
- **Release target:** 0.4.1 — deferred out of 0.3.0 scope; not on the 0.3.0
  release-blocking path.
- **Owner:** project documentation authority review and contributor workflow
- **Direction:** A documentation-authority marker became stale because additional
  authority documentation was edited afterward. A clean clone and development worktree
  produced the same identity once their bytes matched; validation correctly rejected
  both stale branches. The missing boundary is an obvious atomic way to record the final
  reviewed identity without manual digest transcription or a misordered checklist.
- **Conclusion:** Preserve the current project-declared, filesystem-capable authority
  calculation. Add an intentional recording surface that calculates the complete
  inventory and replaces exactly one marker in its declared document. Keep it separate
  from read-only validation; any subsequent authority edit must make the marker stale.
  The read-only calculator and `make documentation-review-record` already exist; remaining
  work is to make `--record` the contributor workflow (not manual digest transcription),
  replace exactly one placeholder as well as a stale marker, and fail closed on missing
  or duplicate markers without writing.
- **Depends on:** PR-26
- **Next action:** Done. CLI `--record` calls `record_project_authority_review`,
  discovers exactly one placeholder, and CONTRIBUTING/troubleshooting teach
  `make documentation-review-record` instead of digest transcription.
- **Evidence:**
  - [x] Recording replaces exactly one placeholder or stale marker with the current
        expected marker and reports the resulting identity and document.
        `ProjectCliTests.test_documentation_review_record_replaces_placeholder_and_fails_closed`
        and `FilesystemProjectInitializationAdapterTests.test_missing_marker_records_a_unique_placeholder_or_requires_a_document`.
  - [x] Missing or duplicate marker locations fail closed without modifying files.
        Same CLI test: duplicate/missing `--record` leaves bytes unchanged.
  - [x] Any authority mutation after recording makes validation stale; recording again
        restores current state in both Git-backed and filesystem-only projects.
        `test_documentation_review_record_restores_git_backed_projects` and
        `test_roadmap_queue_edits_do_not_stale_authority_review` (user-doc edit stales).

### [x] GENERATION-004 — Coding-CLI selection is a fixed name-priority list, not capability/auth-aware

- **Priority:** P1
- **GitHub issue:** [#31](https://github.com/NVIDIA-dev/literate-ai/issues/31)
- **Owner:** `literate_ai/adapters/models/coding_cli.py` (`select_coding_cli`)
- **Direction:** `select_coding_cli` iterates the fixed tuple `("codex", "claude",
  "cursor-agent", "opencode")` and returns the first name found on `PATH`, with no
  authentication or capability check. On a host with more than one coding CLI
  installed, the earlier-listed one always wins regardless of which is actually
  authenticated or preferred. `CODING_CLI=<name>` can override this, but only among
  the same fixed four names.
- **Conclusion:** Not yet decided between (a) a real usability probe (authentication
  state, a quick capability check) driving selection, or (b) keeping name-priority
  selection but making the order itself project-configurable (e.g. via
  `literate.project.json`) instead of hardcoded. Needs a design pass before
  implementation.
- **Workaround on file:** set `CODING_CLI=<name>` explicitly before every invocation.
- **Completion evidence:** `c32aefe` — chose (b), configurable priority order, as the
  smaller and less speculative of the two options. Added
  `LITERATE_AI_CODING_CLI_PRIORITY`, a comma-separated permutation of the four names
  that reorders `select_coding_cli`'s `PATH` search project-wide; an incomplete or
  malformed list fails closed via `coding_cli.priority_configuration_invalid`. A real
  usability/authentication probe (option a) remains open future work if a project
  needs per-host dynamic selection rather than a static configured order.

### [x] ACCEPTANCE-001 — Acceptance-oracle requirement forces every Component into a single-shot CLI JSON contract

- **Priority:** P1
- **GitHub issue:** [#32](https://github.com/NVIDIA-dev/literate-ai/issues/32)
- **Owner:** `component_acceptance.py`, Standard `execute_application`/
  `independent-acceptance` lifecycle phases
- **Direction:** These phases invoke one entrypoint with one JSON array argument and
  diff its exact JSON stdout against `verification/acceptance/<component>.json`,
  unconditionally for every Component, with no entrypoint-kind exception. A Component
  that is a persistent service (no single-shot CLI invocation at all) fails at
  `component_acceptance.oracle_missing` even though it declares no
  `portable-application`-kind entrypoint. This conflates "portable" (buildable
  reproducibly across OS/language Flavors — true of every Component) with "single-shot
  CLI with deterministic JSON stdout" (one specific interaction shape, not universal).
- **Conclusion:** Scope the acceptance-oracle requirement, and the
  `execute_application`/`independent-acceptance` phases generally, to Components that
  declare a `portable-application`-kind entrypoint (or more generally an entrypoint
  kind with a defined deterministic invocation contract) rather than applying it
  universally.
- **Depends on:** ENTRYPOINT-001 (a persistent-service Component only reaches this gap
  once it can be declared without being forced into a single fake CLI entrypoint)
- **Workaround on file:** a synthetic `run` entrypoint whose only job is an in-process
  self-check unrelated to the Component's real behavior, purely to satisfy the gate.
- **Fixed 2026-08-16:** the earlier "Investigated, deferred" note (below, kept for
  history) overestimated the scope — no receipt-schema change was needed.
  `StandardRootIntegrationEvidence.independent_acceptance_identity` only requires a
  typed `ContentIdentity` distinct from the other two stage identities
  (`standard_root_integration.py::__post_init__`); it asserts nothing about *how* that
  identity was derived. `accept_project_independently`
  (`adapters/lifecycle/standard_local.py`) now reads the one packaged entrypoint's kind
  directly off `package_plan.entrypoints[0].kind` (already a call parameter — no new
  data had to be threaded through) and, when it isn't `portable-application`, returns
  `canonical_identity({"schema": "literate-ai/independent-acceptance-exempt@1",
  "entrypoint_kind": ..., "package_plan_identity": ...})` instead of touching package
  custody or requiring an oracle at all. `rebuild.py::_component_acceptance_oracle`
  gates the same way via a new `component_acceptance.root_entrypoint_kind()` helper,
  so a non-`portable-application` Component never needs a
  `verification/acceptance/<name>.json` file to exist in the first place — the issue's
  literal complaint.
- **Investigated 2026-08-15, deferred (superseded by the fix above):** the real scope
  is larger than the roadmap's original "Medium" sizing. `independent_acceptance_oracle`
  is already an optional parameter throughout the adapter layer (`standard_project.py`,
  `standard_rebuild.py`), but `StandardLocalLifecycleAdapter.accept_project_independently`
  (`adapters/lifecycle/standard_local.py`) raises unconditionally when it is `None`,
  and its one caller
  (`application/standard_project_lifecycle.py::execute_application`, via
  `_require_identity(self.independent_project_acceptor.accept_project_independently(...))`)
  has no branch to skip the phase — `independent_acceptance_identity` is a required,
  non-nullable field threaded into the rebuild receipt's wire schema. Scoping this
  properly means adding a real "not applicable" sentinel to that identity and updating
  the receipt schema everywhere it's validated, not a local guard clause. Left open
  rather than rushed.
- **Evidence:**
  - [x] A Component declaring no `portable-application`-kind entrypoint builds and
        passes lifecycle acceptance without a synthetic CLI entrypoint or
        `verification/acceptance/<component>.json`.

### [x] ENTRYPOINT-001 — Standard lifecycle rejects any Component with more than one entrypoint (uncaught traceback, not a typed error)

- **Priority:** P1
- **GitHub issue:** [#33](https://github.com/NVIDIA-dev/literate-ai/issues/33)
- **Owner:** `literate_ai/adapters/standard_project.py` (`_command_contract`)
- **Direction:** A Component with 5 declared entrypoints (`run`, `refresh-worker`,
  `api`, `mcp`, `web` — API + MCP server + scheduled worker + web frontend + a
  synthetic CLI self-check, one codebase) fails with an uncaught
  `StandardCommandProjectionError: each Standard executable Component must declare
  exactly one entrypoint` — a raw Python traceback, not the typed
  `{"command":..., "error": {"code":..., "message":...}, "ok": false, ...}` envelope
  every other lifecycle failure in this framework produces.
- **Conclusion:** Two separable problems: (1) the Standard lifecycle has no model for a
  Component composed of multiple cooperating entrypoints, forcing this exact
  uncaught-exception path; (2) regardless of (1)'s resolution, this must fail as a
  typed `ProjectError`, never an uncaught exception. Decide between (a) first-class
  multi-entrypoint Component support in the Standard lifecycle, or (b) documenting the
  intended pattern as multiple single-entrypoint Components sharing a library Component
  via the existing `provides`/`requires` capability-edge mechanism, before scoping (1)
  further; (2) is unconditionally required either way.
- **Workaround on file:** trimmed to a single `run` self-check entrypoint with the
  other surfaces described as ordinary source-tree modules in spec prose (not formal
  litai entrypoints); eventually restructured into 5 separate single-entrypoint
  Components joined only by shared spec prose, no `requires`/`provides` wiring
  attempted.
- **Completion evidence:** `576226b` — (2) is done: `StandardCommandProjectionError`
  now carries `.message` like every other typed adapter error, and the CLI's top-level
  backstop catches it, covering every raise site in `standard_project.py`, not just the
  multi-entrypoint one. On (1): recommending (b) — express a multi-surface Component as
  separate single-entrypoint Components joined by the existing `provides`/`requires`
  mechanism, not new first-class multi-entrypoint lifecycle support; written up in
  `docs/user/specifications.md`'s "Hierarchy is not Component composition" section.
- **Evidence:**
  - [x] A Component declaring more than one entrypoint fails through a typed
        `ProjectError` JSON envelope, never an uncaught exception.
- **Scope note (2026-08-31):** This item closed only problem (2), the typed-error
  requirement. Problem (1) — first-class multi-entrypoint Component support — was
  *recommended against* here in favor of the provides/requires composition
  workaround, but that is a design recommendation, not an implementation. GitHub
  issue [#33](https://github.com/NVIDIA-dev/literate-ai/issues/33) is titled as a
  feature request for first-class multi-entrypoint support and **remains a valid
  open feature**, tracked separately by
  [MULTI-ENTRYPOINT-001](../../roadmap/active-work.md#x-multi-entrypoint-001-first-class-multi-entrypoint-component-support-33).
  Do not close #33 until the first-class feature's live cross-platform evidence is
  retained; the typed-error fix alone was not sufficient.

### [x] MULTI-ENTRYPOINT-001 — First-class multi-entrypoint Component support (#33)

- **Priority:** P0 (0.9.0 release blocker until live cross-platform evidence proves
      the complete public lifecycle)
- **GitHub issue:** [#33](https://github.com/NVIDIA-dev/literate-ai/issues/33)
- **Owning ADR:** [ADR 0026](../../decisions/0026-multi-entrypoint-deployment-units.md)
      (Accepted 2026-09-01; implementation complete pending live matrix evidence)
- **Release target:** 0.9.0 (complete implementation and end-to-end evidence)
- **Owner:** `src/literate_ai/adapters/standard_project.py` (`_command_contract`),
      Standard lifecycle component model
- **Direction:** A Component composed of multiple cooperating entrypoints (e.g.
      an HTTP API + MCP server + scheduled worker + web frontend in one codebase)
      must carry every declared deployment unit through build export, TEST,
      EXECUTE, package dispatch, independent acceptance, receipt, and CycloneDX
      evidence under ADR 0026.
- **Conclusion (updated 2026-09-02):** The original false-success path has been
      removed. The production Standard lifecycle now builds the complete output set,
      fans TEST/EXECUTE/acceptance out per entrypoint, packages every deployment unit,
      and retains named local and worker-CAS run commands. The remaining blocker is
      macOS/Linux/Windows matrix evidence; unit and contract evidence alone are not
      sufficient to close #33.
- **Depends on:** [ENTRYPOINT-001](../../roadmap/active-work.md#x-entrypoint-001-standard-lifecycle-rejects-any-component-with-more-than-one-entrypoint-uncaught-traceback-not-a-typed-error)
      (typed-error bug, closed)
- **Next action:** Complete the admitted-source Windows worker/CI evidence and retain
      its exact remote receipt. Keep #33 open until that evidence passes.
- **Progress (2026-09-01, c02c2497):** the mechanism landed. ADR 0026 accepted;
      `_command_contract` no longer rejects multiple entrypoints — it projects an
      additive optional `entrypoint_contracts` map (per-entrypoint TEST/EXECUTE +
      artifact export + deployment-unit binding), while single-entrypoint contracts
      stay byte-identical (golden test). BUILD is one per Component revision;
      `--litai-serve`/runtime name the entrypoint module. Dispatch routing hooks
      (`entrypoint_command_contract`, `entrypoint_command_contracts`) are in place.
      Investigation correction: no production consumer calls the routing hooks.
      The local/Bazel/Cargo lifecycle, artifact manifest, package plan, and
      independent-acceptance path remain singular; this is the blocker, not merely
      deferred #216 start/stop/restart polish.
- **Progress (2026-09-02):** production fan-out is implemented through generation,
      one multi-output build, attributed TEST/EXECUTE evidence, grouped artifact
      closure, package dispatch, and verifier-owned per-entrypoint acceptance.
      Durable `litai run --entrypoint` selection now works locally and through SSH;
      local command sets and worker-CAS execution manifests are identity-bound, and
      equal payload bytes with different commands occupy distinct CAS entries.
- **Progress (2026-09-02, live installed wheel):** Codex with model
      `gpt-5.6-sol` generated the two-entrypoint interpreted fixture. One multi-output
      build passed all six generated tests; `litai run --entrypoint calculate` returned
      `12` for `6`, and `--entrypoint inspect` returned `odd` for `7`. The durable
      export retains default entrypoint `calculate`, deployment units `calculator` and
      `inspector`, and execution identity
      `sha256:59134c7c57187b9d20665d765e3f61afe688d77b611ae309d2f80b9f9e3554d7`.
- **Progress (2026-09-02, admitted-source continuation):** a separate
      target-independent source-only admission passed its native two-entrypoint test
      runner, and local `build --from-accepted-source` restored it without generation,
      built both surfaces, and passed all 12 downstream tests. Two independently
      supplied verifier commands exposed and now cover non-canonical result ordering.
      The exact installed `f663d9df` macOS worker then built artifact
      `sha256:6a12094016551de6fd11b67a9ba9c7300ec2997a96f739cdd7c3d3f18d54200d`;
      its remote `calculate` and `inspect` runs returned `12` and `odd` respectively.
      Moving to Linux correctly required a new admission: selecting the Linux OS
      Flavor changes the Component revision and exact generation derivation even when
      the prior admission's worker-selector scope is target-independent. The first
      Ubuntu attempt additionally exposed a stale executable user launcher ahead of
      the exact native bootstrap; shared launcher selection now prefers the bootstrap
      for both execution and acknowledgement. Complete Linux and Windows receipts are
      still required before closing #33.
      The remote macOS lifecycle then built and exercised both entrypoints before its
      evidence writer rejected floating-point build-cache telemetry. The receiver now
      projects finite timings into tagged canonical decimals and rejects non-finite
      values explicitly. The exact-revision live rerun then reached coordinator import
      and exposed host-`Path` ordering in directory-artifact identity; portable logical
      path ordering and a prefix-colliding multi-entrypoint bundle regression now cover
      that second boundary, pending the exact-revision live worker rerun.
- **Progress (2026-09-02, live macOS accepted-source lifecycle):** the exact
      `2dd484a4` installed distribution completed the remote build, returned canonical
      evidence, reconciled the complete prefix-colliding artifact directory, and
      recorded artifact identity
      `sha256:b457a26e64a5adadf30f7ea9a7dfee50613d122da4d68079418a54898c28c3f9`.
      The first subsequent `run` then exposed a third boundary defect: artifact exports
      retained an explicit model selector but not the equally authority-bearing
      accepted-source-only mode, so a freshly built artifact was declared stale.
      Controlled reconstruction held every other authority input constant and proved
      ordinary run authority differed while accepted-source run authority exactly
      matched the export. Artifact exports now retain that non-default mode, while run
      re-discovers the current provider/tool binding so real provider drift still fails
      closed. The real macOS worker then returned `calculate` result `12` and `inspect`
      result `odd` through the repaired coordinator path; exact final-revision installed
      rerun and Linux/Windows evidence remain.
- **Progress (2026-09-02, exact installed Linux continuation):** `make install` from
      pushed commit `4a57d5b9` produced a non-editable 0.9.0 runtime with no recorded
      payload path outside its prefix and distribution identity
      `sha256:507975f26fa480379c8b2ee672a59f638fecb4769e110f341cc629f32dd16766`.
      One Linux-targeted two-entrypoint source tree was verifier-admitted under the
      preceding receipt-runner policy. After changing only that policy to the current
      Standard driver and re-recording project authority, Ubuntu 24.04 completed
      `build --from-accepted-source` with model fallback prohibited and returned
      authenticated artifact
      `sha256:f27e54032e24b55ab560b85a05a9a757ed8f956367d808bf05e50d59cdc5fe04`.
      Its independent `calculate` and `inspect` deployment-unit runs returned
      `{"surface":"calculate","result":14}` and
      `{"surface":"inspect","result":"odd"}`. Exact CPython 3.12 and 3.14
      wheelhouse closures also bootstrapped successfully on Ubuntu 24.04 CPU/NVIDIA
      and Ubuntu 26.04 CPU workers. This closes Linux and directly demonstrates that
      unrelated project receipt-policy authority no longer consumes another model
      call; Windows remains.
- **Evidence:**
  - [x] A 0.9.0 ADR proposes the multi-entrypoint lifecycle model and is
        explicitly accepted before implementation is scheduled
        ([ADR 0026](../../decisions/0026-multi-entrypoint-deployment-units.md),
        accepted 2026-09-01).
  - [x] A single Component declaring multiple cooperating entrypoints projects a
        per-entrypoint build/test/export contract through the Standard lifecycle.
  - [x] One build intent, authorization, action, manifest, and typed build
        evidence bind every entrypoint export without changing the serialized
        single-entrypoint contract.
  - [x] Generated TEST and EXECUTE fan out over every entrypoint contract and
        aggregate typed observations keyed by entrypoint identity, deployment
        unit, export, command, and runner; one failed unit prevents acceptance.
  - [x] Artifact closure and package planning retain every root deployment
        artifact, and packaged TEST/EXECUTE select each entrypoint's exact export
        and command rather than the primary entrypoint implicitly.
  - [x] Verifier-owned acceptance resolves and executes one oracle per packaged
        entrypoint/deployment unit, including portable, persistent-service, and
        browser kinds, and binds the complete result set into one receipt.
  - [x] Source-cache membership, aggregate receipts, and CycloneDX evidence
        invalidate on one entrypoint change and enumerate every declared
        deployment unit.
  - [x] Singular-output build profiles (Bazel, Cargo, Make, and CMake) fail with
        a stable typed unsupported-profile error until an exact multi-output
        mapping is declared; no adapter synthesizes a nonexistent artifact.
  - [x] Contract/wire/tamper regressions and live interpreted multi-entrypoint
        generation/build/run pass. Partial-failure rejection and packaging are covered
        locally; exact installed macOS, Linux, and native Windows remote lifecycle
        evidence passes. The Windows proof binds source archive, non-editable wheel,
        installed distribution, three complete lifecycle cases, and named non-default
        dispatch to exact commit `5cf7100b1022a52127410e0da8797284be133217`;
        all 15 hosted jobs pass in run `33858381265`. Existing single-entrypoint
        golden identities are unchanged.

### [x] GENERATION-005 — Per-document coding-CLI generation timeout (900s) is hardcoded, not configurable

- **Priority:** P1
- **GitHub issue:** [#34](https://github.com/NVIDIA-dev/literate-ai/issues/34)
- **Owner:** `literate_ai/adapters/models/coding_cli.py`
  (`CodingCliTaskRunner`/`CodingCliSourceGenerator`), `standard_project.py`
  (`FilesystemStandardSourceGenerationAdapter.from_environment`)
- **Direction:** Both runner classes default `timeout_seconds=900`. The local
  generation path `litai build`/`litai generate` actually uses constructs
  `CodingCliSourceGenerator` with no override, and neither `--worker-timeout-seconds`
  (a separate, higher-level remote-worker dispatch timeout, default 3600s, only
  meaningful with `--worker`) nor any environment variable reaches this constructor.
  A Component whose spec legitimately needs more than 15 minutes of coding-CLI
  generation time cannot be built locally today, full stop.
- **Conclusion:** Make `timeout_seconds` configurable for local coding-CLI generation —
  an env var and/or a `litai build`/`litai generate` flag — distinct from the existing
  remote-worker dispatch timeout.
- **Further-reaching idea on file (not required for this item):** automatic
  big-Component splitting when a resolved generation prompt is likely to exceed the
  coding-CLI budget, proposing or performing a split along natural boundaries (distinct
  entrypoints, low-cross-reference prose sections) into sibling Components joined by
  `provides`/`requires`. Worth its own roadmap item if pursued; out of scope here.
- **Workaround on file:** manually split one large Component into 5 smaller ones, each
  small enough for the fixed 900s budget.
- **Completion evidence:** `295e1c1` — added `LITERATE_AI_CODING_CLI_TIMEOUT_SECONDS`,
  read once in `FilesystemStandardSourceGenerationAdapter.from_environment` (shared by
  `litai build`/`generate`/`rebuild`); default stays 900s, an invalid value fails
  closed via a typed `CodingCliError`. The automatic-splitting idea remains unpursued
  future work.
- **Evidence:**
  - [x] A Component whose generation legitimately exceeds 900s completes locally via an
        explicit configuration, with the default remaining 900s.

### [x] GENERATION-006 — `coding_cli.generated_metadata_invalid` recurs probabilistically on larger Components; a plain retry usually fixes it

- **Priority:** P1
- **GitHub issue:** [#35](https://github.com/NVIDIA-dev/literate-ai/issues/35)
- **Owner:** `literate_ai/adapters/models/coding_cli.py`
  (`_canonicalize_generated_framework_metadata`)
- **Direction:** Two moderately-sized Components hit
  `source-generation:coding_cli.generated_metadata_invalid` multiple times, including
  twice at the identical document hash for one Component, and both eventually
  succeeded on a subsequent `--force-regeneration` retry of the same spec content with
  no further changes. A simpler sibling Component with a comparable skill set never hit
  this across its one build attempt — larger/more complex generation surfaces appear
  more prone to it. This is malformed JSON in a framework-owned metadata file (the
  generated test manifest or CycloneDX source SBOM), a coding-CLI output-quality issue,
  not a specification or environment problem, and litai currently treats it as a hard
  failure requiring the caller to notice and manually retry.
- **Conclusion:** Have `litai build`/`litai generate` automatically retry a bounded
  number of times (using the existing `--force-regeneration` semantics) specifically on
  `coding_cli.generated_metadata_invalid`, since a plain retry resolved it in both
  observed cases.
- **Investigated 2026-08-15, deferred:** `_canonicalize_generated_framework_metadata`
  is a pure post-processing step over already-generated file content; retrying it alone
  would deterministically fail again on the same bad bytes. A real fix needs to retry
  the whole coding-CLI subprocess invocation (workspace setup, external process call,
  teardown) inside `CodingCliSourceGenerator`'s generation method, since the observed
  fix (`--force-regeneration`) works because it re-runs a non-deterministic external
  call, not because it re-parses anything. That method is the framework's most
  safety/security-sensitive code path; scoping a bounded-retry loop around it correctly
  (fresh workspace per attempt, bounded attempts, no infinite loop, audit trail per
  attempt) deserves more care than this pass had time for. Left open rather than rushed.
- **Fixed 2026-08-16 (`c46d2c74`):** `CodingCliSourceGenerator.generate()` now retries
  the whole subprocess invocation (fresh workspace per attempt via
  `_reset_generation_output_root()`) up to 2 additional times specifically on
  `coding_cli.generated_metadata_invalid`, recording a `metadata_retry_count` field and
  a `coding_cli_metadata_retry` operation-log event per attempt; any other error code,
  or exhausting the bound, still fails closed with the original typed error.
- **Evidence:**
  - [x] `tests/critical/test_coding_cli_generation.py::CodingCliInvocationTests` covers a
        reproduced case succeeding through the bounded automatic retry without caller
        intervention, and a persistently malformed case still failing closed after the
        bound is exhausted.

### [x] SAMPLES-RESILIENCE-001 — The `samples` gate has no retry or checkpoint resilience for transient live-generation failures

- **Priority:** P2
- **Owner:** `scripts/run_samples.py`, `tests/conformance/support/sample_runner.py`
- **Direction:** During the 0.5.1 release-check gate (2026-08-19), three consecutive
  full `make samples` runs each failed on a different sample with a different error
  class (`coding_cli.timeout` twice on `dependency-planner/rust`, once via a raw
  `GenerationFailure` that bypassed the harness's own `SampleFailure` wrapping;
  `coding_cli.generation_failed` on `critical-path-scheduler/python` via
  `cursor-agent`). Isolating `dependency-planner/rust` alone succeeded on a standalone
  rerun with no code change. A single sample's transient failure aborts the entire
  matrix run today, discarding every other sample's already-completed work; a retry
  regenerates everything from nothing.
- **Conclusion:** See
  [ADR 0008](../../decisions/0008-samples-gate-live-generation-resilience.md) for the
  full proposed design: extend `GENERATION-006`'s existing bounded coding-CLI
  subprocess retry to cover `coding_cli.timeout`/`coding_cli.generation_failed` (not
  just `coding_cli.generated_metadata_invalid`), and add sample-level checkpointing
  to `scripts/run_samples.py` following the existing `run_checkpointed_gates.py`
  pattern so a retry resumes from the last completed sample.
- **Depends on:** ADR 0008 reaching `Accepted` via its planning cycle before
  implementation begins, per `skills/agent/release-project/SKILL.md`'s
  significant-feature-request sequence. The Rust-skill-wiring theory ADR 0008
  originally cited as this item's likely root cause was disproven in the same session
  (the skill was already correctly wired via `flavors/rust/flavor.md`'s own
  `authoring_inputs` contribution) — this item stands on its own merits regardless.
- **Completion evidence:** ADR 0008 accepted 2026-08-20 after the 0.5.2 backport cycle
  reproduced the same shape six more times (three samples, three error classes, all
  later passing untouched). The retry set is now
  `_TRANSIENT_GENERATION_ERROR_CODES` = `generated_metadata_invalid`,
  `generation_failed`, `timeout`, reusing `GENERATION-006`'s existing bounded
  fresh-workspace retry loop. `coding_cli.empty_generation` is deliberately **excluded**:
  it looks transient but is usually a deterministic workspace-write denial, so retrying
  it only triples the wall clock before the same failure surfaces.
  `run_all` now checkpoints to `OBJ_DIR/samples-checkpoint.json`. Each entry stores the
  sample's **complete case**, not a pass flag, because the receipt aggregates evidence
  from every sample -- a skipped sample must contribute exactly what it contributed when
  it ran. The key binds sample tree digest, flavor selectors, packaging scope, platform,
  and the lifecycle-driver implementation digest; the checkpoint is deleted after a
  complete matrix pass so a *successful* run never lets the next run skip everything.
  Verified end to end: a seeded resume of `hello-component` reported
  `skipped (checkpointed pass)` in 1.8s versus ~90s, producing an identical valid report
  (`test_count: 13`).
- **Follow-on defect found and fixed:** the first implementation keyed the checkpoint on
  `validated_project_authority_identity`, which silently coupled `make samples` to
  documentation-authority freshness -- a separate gate's concern -- and broke the run
  outright on a stale marker. Replaced with the lifecycle-driver implementation digest,
  which is the code that actually decides sample behavior; an uncomputable digest
  disables the checkpoint rather than guessing at invalidation.
- **Evidence:**
  - [x] ADR 0008 `Status` reaches `Accepted`.
  - [x] Retry covers `coding_cli.timeout`/`coding_cli.generation_failed`, with
        `empty_generation` explicitly excluded and regression-tested as excluded.
  - [x] Sample-level checkpoint resumes a failed matrix without regenerating passed
        samples, and self-clears after a complete pass.
  - [x] Checkpoint invalidates on sample content, nested files, added files, flavor
        selectors, packaging scope, and framework revision; corrupt or foreign-schema
        state resumes nothing (`tests/unit/test_sample_checkpoint.py`, 16 tests).
  - [x] `litai rebuild` no longer truncates away the line naming a driver failure, and
        retains the complete driver output for inspection.

### [x] CACHE-010 — Lifecycle cache roots are ambient environment only, with no CLI surface and no record in the receipt

- **Priority:** P2
- **Owner:** `src/literate_ai/cache_directories.py`, `src/literate_ai/cli/rebuild.py`
- **Direction:** `BUILD_DIR`/`OBJ_DIR` are resolved exclusively from process
  environment by `resolve_cache_directories()`. `litai` exposes no `--build-dir`/
  `--obj-dir` flags at all, so for `litai rebuild`, the only entry point producing a
  promotable test receipt, ambient environment is the sole lever.
  (`cli/rebuild.py:214` rejects the separate accepted-source-cache overrides because
  the Standard driver "uses BUILD_DIR-backed cache custody" — an accurate description
  of the coupling this item removes.) The roots a run actually used are not
  recorded anywhere, so a warm-cache run and a cold-cache run of the same revision yield
  indistinguishable receipts. During the 0.5.2 backport cycle this directly obstructed
  diagnosis: the `samples` gate passed (warm `OBJ_DIR`, no regeneration) while
  `litai rebuild` failed on the same revision (cold, regenerating), and nothing in
  either result made the distinction visible.
- **Conclusion:** See
  [ADR 0009](../../decisions/0009-explicit-cache-root-binding.md). Add `--build-dir`/
  `--obj-dir` flags routed through the existing `bind_cache_directories()` seam (which
  already binds explicit roots without consulting environment, and already applies the
  safety, distinctness, and no-nesting rules); keep `BUILD_DIR`/`OBJ_DIR` as fallback
  with precedence flag → environment → portable default; and bind the resolved
  `CacheDirectories.identity` (`literate-ai/cache-directory-custody@1`, already
  computed) into the candidate test receipt. Cache roots deliberately do **not** move
  into workflow authority — host paths there break workflow portability.
- **Completion evidence:** `0ed5ccf6` — `select_cache_directories()` resolves flag →
  environment → portable default and binds through the existing
  `bind_cache_directories()` seam, so an explicit root never consults the environment
  and still gets every custody rule (protected-authority overlap, distinctness, no
  nesting) as a typed `rebuild.cache_root_invalid`. The resolved roots are overlaid
  into an external driver's environment *before* binding, so the environment and the
  identity material derived from it describe the same custody, and are recorded as a
  new optional `cache-directory-custody` evidence role — optional because the receipt
  schema is `additionalProperties: false` and requiring it would invalidate every
  existing receipt. A follow-up (`cae62085`) corrected the resolution ordering: it
  originally ran before the project-index preflight, which must remain the first
  rejection.
- **Evidence:**
  - [x] ADR 0009 `Status` reaches `Accepted` (planning cycle completed 2026-08-20).
  - [x] `--build-dir`/`--obj-dir` accepted by `litai rebuild` and routed through
        `bind_cache_directories()`.
  - [x] Flag-over-environment precedence covered by regression tests, including a
        disagreeing flag/environment pair (`tests/critical/test_build_cache_directories.py`).
  - [x] Candidate test receipt carries the resolved cache-directory custody identity,
        tolerated as absent when reading a receipt written before this change.

### [x] GENERATION-009 — Retry duplicate generated-test argument vectors as a bounded generation failure

- **Priority:** P1
- **Owner:** `src/literate_ai/adapters/models/coding_cli.py`
  (`_TRANSIENT_GENERATION_ERROR_CODES`)
- **Direction:** A 0.5.2 `make release-check` samples run failed
  `publication-import/python` with `generated_tests.duplicate_arguments` after a
  coding CLI emitted two valid cases that shared one JSON argument vector. The
  uniqueness check is a hard admission rule and must stay. The prompt already
  requires unique vectors. The samples harness retries this code only when the
  failure is classified as `generation.model-stage-failed`; this run failed as a
  Standard lifecycle node, so that retry never fired. `generate()` already wipes
  the output root and retries `coding_cli.generated_metadata_invalid`,
  `coding_cli.generation_failed`, and `coding_cli.timeout`.
- **Conclusion:** Treat `generated_tests.duplicate_arguments`,
  `generated_tests.acceptance_signature_missing`, and
  `generated_tests.expected_result_shape_mismatch` as the same bounded
  subprocess retry. Do not delete the uniqueness validator. Do not import
  0.6-only features onto `release/0.5.x`; land on `main` first, then cherry-pick.
- **Depends on:** `GENERATION-006` / ADR 0008 retry loop already in
  `CodingCliSourceGenerator.generate()`.
- **Implementation:**
  - [x] Add the three generated-test contract codes to
        `_TRANSIENT_GENERATION_ERROR_CODES`.
  - [x] Keep uniqueness as a hard admission failure after the retry bound.
  - [x] Unit-test recovery and fail-closed exhaustion for duplicate arguments;
        keep the exact retry-set assertion current.
- **Completion evidence:** generate() retries the three `generated_tests.*`
  contract codes with the existing fresh-workspace bound.
- **Evidence:**
  - [x] `tests/critical/test_coding_cli_generation.py` recovers on a first
        `generated_tests.duplicate_arguments` payload and fails closed after
        exhausting the bound.
  - [x] `tests/unit/test_sample_checkpoint.py` lists the expanded retry set and
        still excludes `coding_cli.empty_generation`.

### [x] GENERATION-007 — Add an authenticated inherited IDE-session coding provider

- **Priority:** P0
- **GitHub issue:** [#43](https://github.com/NVIDIA-dev/literate-ai/issues/43)
- **Follow-up defects:** [#94](https://github.com/NVIDIA-dev/literate-ai/issues/94),
  [#97](https://github.com/NVIDIA-dev/literate-ai/issues/97)
- **Owner:** framework-core provider protocol, coding-provider adapter, and canonical
  verifier-owned source-admission boundary
- **Direction:** Let an already-authenticated IDE agent perform generation through a
  canonical provider-neutral handoff without launching a nested coding CLI or
  persisting credentials.
- **Conclusion:** Add a narrow inherited-session protocol and adapter outside the
  existing coding-CLI lifecycle implementation. Bind authenticated provider/session
  identity, exact request plan/context bytes or immutable bundle reference and writable
  boundary, single-owner custody,
  typed timeout/cancellation outcomes, private-content-safe evidence digests, and
  returned source metadata. Treat the returned tree only as an untrusted candidate:
  canonical verifier-owned source admission remains the sole authority transition.
- **Depends on:** the verifier-owned source-admission boundary landed by
  [#38](https://github.com/NVIDIA-dev/literate-ai/pull/38); coordinate with
  [#31](https://github.com/NVIDIA-dev/literate-ai/issues/31) for provider selection
  without absorbing general capability probing.
- **Scope boundary:** Keep mission policy and private transport details downstream.
  Avoid broad changes to `coding_cli.py` or lifecycle orchestration currently touched
  by [#44](https://github.com/NVIDIA-dev/literate-ai/pull/44); integrate through a new
  provider module and the narrow source-admission contract.
- **Implementation:**
  - [x] Define authenticated request/response schemas, ownership transitions, bounded
        request identities, terminal outcomes, replay/staleness rejection, and
        tamper-evident source/evidence metadata without credential persistence.
  - [x] Add a no-nested-CLI `InheritedSessionProviderAdapter` and `selected_coding_
        provider` selection helper.
  - [x] Wire explicit CLI/API provider and inherited-session configuration into
        `litai build`/`generate`/`rebuild` selection.
  - [x] Bind successful handoff evidence into canonical receipts and require the
        verifier-owned source-admission result before later authority.
  - [x] Bind inherited provider evidence inside its single model-stage output record
        so provenance retains one output per route decision and full Standard source
        generation can reach admission.
  - [x] Admit that stage-bound evidence without treating it as a second model output,
        and distinguish provider text output from the final tree after exact locked
        assets are augmented by verifier-owned generation.
  - [x] Document design traceability, authority markers, and exact Physics Workbench sample private
        waiter removal, migration, and release-pin steps; add a changelog outcome.
- **Reopened 2026-08-23:** The shipped request contains only prompt, context-manifest,
  and workspace identities. The coordinator therefore cannot obtain the authenticated
  prompt/context bytes, repository/workspace authority locator, or allowed-output
  contract without an unmodeled ambient channel or forbidden reconstruction. Cursor's
  documented IDE hooks expose a possible current-conversation trigger and evidence
  surface, but no existing Literate AI adapter uses it.
- **Current next action:** Done. Live inject remains the recorded Cursor vendor gap,
  not a missing Literate AI adapter. The typed
  `inherited_session.current_session_unavailable` bound is the honest live proof.
  - [x] Add an authenticated immutable context bundle carrying the exact bounded prompt,
        workspace locator, scoped lock/plan/recipe/model identities, output confinement,
        and cancellation/cleanup contract; verify every duplicate identity.
  - [x] Add a generic Cursor Agent Chat hook adapter that admits only the bound
        conversation/model/workspace, submits the exact bundle prompt through the
        documented `stop.followup_message` continuation, captures transcript/provider
        evidence, and returns only allowed `source/**` files.
  - [x] Cover exact context availability, replay, scope/workspace/model mismatch, output
        escape, timeout/cancellation, recovery across hook invocations, cleanup, and
        transcript/provider binding.
  - [x] Add explicit authenticated context-byte tamper and concurrent multiple-request
        ordering regressions before completion.
  - [x] Fail closed with `inherited_session.current_session_unavailable` when no
        Cursor stop-hook environment is present. Cursor documents no API to inject
        a hook into an already-running conversation, so a live current-session
        transaction cannot be forced from this chat. The authenticated directory
        coordinator plus the synthetic hook-handler transaction remain the
        framework proof; the typed unavailable error is the honest live bound.
        Downstream 20-node qualification stays a separate descendant gate and
        must not weaken source admission.
- **2026-08-28 remaining evidence:** `require_live_cursor_hook` is implemented. Missing
  channel/key without a stop-hook raises `inherited_session.current_session_unavailable`
  before `runtime_configuration_invalid`. Covered in
  `tests/smoke/test_cursor_inherited_session.py` and
  `tests/critical/test_inherited_session_provider.py`.
- **2026-08-23 implementation evidence:** `make inherited-session-check` passes 86
  protocol/adapter/admission tests; `make format-check lint openspec-check
  documentation-check` passes. A synthetic full directory transaction exercised the
  actual Cursor hook handler twice (submit then collect/respond), including transcript
  and provider evidence and terminal cleanup.
- **2026-08-28 completion bound:** A live inject remains a vendor gap, not a missing
  Literate AI adapter. `require_live_cursor_hook` fails closed when the ephemeral
  hook object is absent; `handle_stop` still binds a real hook payload. Do not claim
  a current-conversation generation that did not run.
- **Implemented 2026-08-15:** Standard source generation now consults the explicit
  provider selection, carries prepared-node request/plan/context/prompt/workspace
  identities through the handoff, retains public handoff evidence in generation
  provenance, and sends only independently verified membership onward. The built-in
  private-directory coordinator protocol uses create-once authenticated envelopes and
  rejects unsafe permissions, disconnect, replacement, stale state, or replay. No
  provider CLI is started.
- **Evidence:**
  - [x] `make inherited-session-check` (88 tests, including
        `require_live_cursor_hook` and missing-channel
        `inherited_session.current_session_unavailable`) and
        `make source-admission-check` (62 tests) cover authentication failure,
        session/request mismatch, timeout,
        user and runner cancellation, late/duplicate/stale response, source/evidence
        tampering, IDE/coordinator protocol roundtrip/disconnect/replay, and successful
        verifier-owned admission.
  - [x] Relevant Makefile gates pass and remote focused CI is green. The follow-up
        provenance-cardinality defect (#94) was fixed in `ce0771d2` and merged via
        PR #95 (`d2f1dbd3`); `main`'s full remote CI matrix has passed clean on every
        push since.

### [x] PROVIDER-001 — Resolve preferred alternative providers by required capabilities

- **Priority:** P1
- **GitHub issue:** [#41](https://github.com/NVIDIA-dev/literate-ai/issues/41)
- **Owner:** framework-core provider-resolution contract, Component plan, and lock
  authority
- **Direction:** Let a project declare stable provider identities and capability-set
  identities, required capabilities, one preferred provider, an explicit deterministic
  fallback order, and an optional Flavor-selected override. Select the preferred
  provider whenever sufficient; consider fallback only when it is insufficient; reject
  insufficient overrides and unsatisfied requirements without weakening requirements.
- **Conclusion:** The framework owns generic deterministic resolution and its complete
  evidence identity. Downstream projects retain mission policy and provider catalogs;
  specifically, Physics Workbench sample keeps Newton-first/PhysX fallback declarations and physics
  acceptance while removing its generic sorting, validation, and provenance code once
  it consumes this contract.
- **Depends on:** current canonical Component plan/lock identity surfaces; no dependency
  on downstream Physics Workbench sample source or mission vocabulary.
- **Implementation:**
  - [x] Add the canonical provider catalog/request/result contracts and deterministic
        resolver, including explicit tie-breaking, exact override provenance, and
        fail-closed typed errors.
  - [x] Bind selected provider, requirements, evaluated capability-set identities,
        fallback reason or override provenance, and resolver-policy identity into plans
        and locks so catalog drift invalidates stale resolution and can return to the
        preferred provider.
  - [x] Add schemas and migrations for provider resolution (`ComponentLock.
        provider_resolutions`, `ComponentGenerationKey.provider_resolution_identities`,
        both optional/default-empty and backward compatible).
  - [x] Add the narrow CLI/API surfaces needed to author, inspect, and validate provider
        resolution.
  - [x] Document framework authority, design traceability, and exact Physics Workbench sample
        consumption/removal steps while keeping Newton/PhysX mission policy downstream;
        record the user-visible outcome in `CHANGELOG.md`.
- **Investigated 2026-08-15:** `resolve_provider` and its contracts are well-tested
  (8 focused resolver tests: preferred success, missing-capability fallback, unsatisfied
  requirements, invalid override, deterministic ties) and safely wired into
  `ComponentLock`/`ComponentGenerationKey` with backward-compatible optional fields, but
  nothing in `src/` calls `resolve_provider` yet — no CLI/API surface exists, and no
  caller ever populates a non-empty `provider_resolutions` tuple. Merging this is safe
  (purely additive, default-empty, no behavior change to any existing path) but it does
  not yet do anything a project can observe; the CLI/API surface and an actual call site
  (likely alongside coding-CLI/#41 selection) remain open work.
- **Fixed 2026-08-16 (PR #82, `57e41a57`):** recovered the merged contract work from
  PR #48 and completed the authoring-to-lock path. Components author named provider
  catalogs/policies in `component.md`; selected Flavors author exact overrides in
  `flavor.md`; `litai lock` resolves and reports the complete result and override
  provenance; `litai plan` projects it from the admitted lock. Catalog/policy/selection
  provenance identity-binds into `ComponentLock` and every `ComponentGenerationKey`, so
  capability drift returns deterministically to a newly sufficient preferred provider.
- **Evidence:**
  - [x] `make provider-resolution-check` passes 62 focused contract, authoring,
        Flavor-override, lock-CLI, plan,
        migration, and schema tests covering preferred success, missing-capability
        fallback, unsatisfied requirements, invalid override, deterministic ties,
        catalog drift invalidation, and deterministic return to preferred.
  - [x] PR #82's remote CI matrix passed clean before merge; `main`'s full remote CI
        matrix has passed clean on every push since.

### [x] LOCK-001 — A Component's lock is invalidated by unrelated changes elsewhere in the project

- **Priority:** P1
- **GitHub issue:** [#36](https://github.com/NVIDIA-dev/literate-ai/issues/36)
- **Owner:** Component lock / resolution-audit authority binding
- **Direction:** Running `litai lock`/`litai build` for one Component while a different
  Component's spec/oracle/docs changed in the same project repeatedly produces
  `component_lock.stale: Component lock and resolution audit do not bind the current
  effective authority graph` for the untouched Component — observed both running two
  independent Components' builds in parallel against the same checkout, and running
  `litai test` sequentially across five Components immediately after any one of them
  was re-locked. A per-Component lock appears to bind a project-wide "catalog
  audit"/authority identity that changes whenever any Component, Flavor, or
  documentation file changes, not just axes relevant to the Component being
  locked/built.
- **Conclusion:** Not yet root-caused. Needs investigation into whether project-wide
  lock sensitivity is intended, or whether invalidation should scope to just the locked
  Component's own transitive spec/Flavor/skill closure.
- **Investigated 2026-08-15, still open:** the literal string `component_lock.stale`
  does not appear anywhere under `application/component_lock_resolution.py`,
  `adapters/component_lock_application.py`, or `adapters/component_locks.py`, so the
  message is composed elsewhere in the `contracts/component_locking` cluster — root
  cause needs real investigation time, not a quick grep. The described symptom (a
  per-Component lock binding a project-wide "effective authority graph" identity)
  implies a structural scoping decision, the largest item in this batch; left open.
- **Fixed 2026-08-16 (`d3830a66`):** `_effective_authority_graph_identity`
  (`component_lock_planning.py`) no longer binds the whole project's
  Component/Flavor/skill catalog identity. `project_authority_graph.py` gained
  `project_lineage_authority_identity()`, which reuses the same validated
  `AuthorityGraph` (so a colliding/cyclic entity still fails graph construction) but
  narrows the bound identity to repository-lineage nodes and edges only — the one
  piece of genuinely project-wide state a lock still legitimately fails closed on.
- **Evidence:**
  - [x] `tests/unit/test_project_authority_graph.py::test_lineage_identity_is_
        unaffected_by_an_unrelated_sibling_component` and
        `test_lineage_identity_changes_when_repository_state_changes` verify both
        directions against real fixtures built from this repository's own
        `.literate/` lineage files: an unrelated sibling Component's content change
        (or a brand new sibling Component) no longer changes the identity, while a
        repository-level change still does.

### [x] LOCK-002 — Cache-restored locked revisions lose typed Component definitions

- **Priority:** P0
- **GitHub issue:** [#98](https://github.com/NVIDIA-dev/literate-ai/issues/98)
- **Owner:** Component lock typed validation and serialization boundary
- **Direction:** Linux source admission succeeds for a twelve-Component composition,
  but cache-only continuation crashes when acceptance reads
  `LockedComponentRevision.definition`; no coding-CLI fallback occurs.
- **Conclusion:** `ComponentLock` already requires every exact typed
  `ComponentAuthoring` value to decode and validate a lock, but node revisions discard
  that mandatory context. Retain the matched authoring as typed, non-wire,
  non-identity revision state and make node decoding bind it explicitly. Do not
  re-read mutable `component.md`, weaken validation with `getattr`, or change frozen v2
  lock bytes.
- **Depends on:** the existing v2 lock's mandatory external-authoring decode seam and
  verifier-owned Standard source-admission/cache restoration.
- **Implementation:**
  - [x] Bind each locked revision to its exact typed Component definition during
        construction and decode; reject missing, substituted, or selector-mismatched
        definitions.
  - [x] Preserve current and legacy-compatible v2 lock serialization and identities.
  - [x] Exercise Linux cache-only restoration and all twelve admitted composition
        members without any generator fallback.
  - [x] Record the user-visible correction in `CHANGELOG.md`.
- **Evidence:**
  - [x] `make provider-resolution-check` passes 65 lock/schema tests and
        `make source-admission-check` passes 62 admission/cache tests; the installed
        wheel smoke additionally requires 12 unique entries, 12 Linux cache-only
        restores, and zero generator fallbacks.
  - [x] `make python-check` passes 2,365 tests with 28 platform skips; final-commit
        `make wheel-check` passes with 12 admissions, 12 unique entries, 12 Linux
        cache-only restores, and zero generator fallbacks. PR #102 passes the complete
        Ubuntu/macOS/Windows matrix on Python 3.11, 3.12, and 3.14.

### [x] SKILL-CATALOG-001 — Add `python-service-application` and `react-dashboard-application` specification-to-source skills

- **Priority:** P2
- **GitHub issue:** [#37](https://github.com/NVIDIA-dev/literate-ai/issues/37)
- **Owner:** `skills/specification-to-source/` catalog
- **Direction:** Building a real multi-surface service Component (HTTP API + MCP
  server + scheduled worker + web dashboard) needed two skills the default catalog
  doesn't have: a long-running Python service (HTTP API, embedded MCP server,
  scheduled worker) and an interactive React dashboard (toggleable overlaid
  time-series charts, sortable/rankable table, table/graph view switch). Neither
  `portable-application-implementation` nor any bundled skill covers this; the default
  catalog is oriented entirely around single-shot "JSON args in, JSON stdout out"
  portable applications. Both were authored locally as project-scoped drafts (technique
  synthesized from a public collection of Claude Code skills, not copied text) and are
  reusable, provider-neutral, with no project-specific vocabulary.
- **Conclusion:** Review both proposed skills for inclusion in the framework's default
  `specification-to-source` catalog; the issue offers a PR with full skill content.
  `python-service-application` covers HTTP API conventions (DI, typed response
  models/status codes, router-per-resource, OpenAPI-as-contract, OpenAI-compatible
  endpoint shapes including SSE streaming and error envelope, cursor pagination), MCP
  server conventions (tools vs. resources, input validation, structured errors,
  transport choice), and scheduled-worker conventions (per-unit failure isolation,
  run-outcome recording). `react-dashboard-application` covers local UI-only selection
  state independent of fetched data, stable identity-derived keys for toggled
  series/rows, multi-key table sort/rank, display-mode switching without discarding
  state or refetching, and per-panel loading/error isolation.
- **Verified 2026-08-15:** `skills-check` run for real via
  `scripts/evaluate_changed_skills.py` with the installed `skillevaluator`
  (`--checks schema,pii,license,quality,unicode,lint --no-llm --no-dedup`, the same
  invocation the Makefile uses) — both pass, 6/6:
  `python-service-application` B/89.0, `react-dashboard-application` A/90.2. Both parse
  clean through the real skill loader with `dependencies: []`, so no Flavor closure or
  transitive-resolution failure mode can trigger; neither leaks a generated-source
  path into an ignored directory name (`build`/`dist`/`out`/`target`); `samples`
  validation only checks a Component's pinned skill is present in the catalog (no
  orphan-skill check), so these inert, unpinned catalog entries can't break it.
  Root-only placement (no template mirror) is consistent with existing precedent
  (`generate-nvidia-cuda-application`); `litai init` projects simply won't get these
  two skills, same as that one. Non-blocking follow-ups: a provider-neutrality leak at
  `python-service-application/SKILL.md:69` (dangling "(this project's...)" reference),
  a hardcoded "fixed daily schedule" phrasing at `:74`, and
  `react-dashboard-application` missing the relative-import-with-extension rule
  `javascript-portable-json-application/SKILL.md:24` has (harmless while unpinned).
- **Fixed 2026-08-16:** both non-blocking follow-ups above are closed —
  `python-service-application/SKILL.md`'s MCP-transport sentence no longer dangles a
  "(this project's...)" reference, and its worker section now says "the specification's
  declared schedule (e.g. hourly, daily, or another fixed interval)" instead of a
  hardcoded daily cadence; `react-dashboard-application/SKILL.md` gained a
  relative-import-with-extension `limitations` entry matching
  `javascript-portable-json-application/SKILL.md:24`'s. Two new sample Components pin
  each skill and were locked and generated live end to end via `litai lock`/`litai
  generate` (`--target linux-host`, zero `flavor_slots` so neither skill's guidance is
  diluted by a language Flavor's own portable-application-shaped skill;
  `CODING_CLI=claude`, since the environment's `codex` binary was rate-limited on spend
  cap): `samples/python-service-example` (Cluster Health Service — paginated/typed-404
  HTTP API, MCP server with a tool and a resource, and a scheduled worker with per-unit
  failure isolation and history accumulation) generated a real FastAPI +
  SQLAlchemy-async + MCP tree whose own generated test suite passed 20/20 (one test
  module, `test_mcp_server.py`, fails to import against the installed `mcp` package
  because it references `McpError` where that package version exports `MCPError` — a
  real but narrow generated-code/SDK-version mismatch, not a skill or harness defect);
  `samples/react-dashboard-example` (Cluster Metrics Dashboard — toggleable overlaid
  time-series graph, multi-key sortable table, and a view switch that preserves
  selection/sort/fetched data) generated a real Vite + React tree whose own generated
  Vitest suite passed 11/11 and whose production build (`npm run build`) succeeded. This
  is direct `litai lock`/`litai generate` evidence, not the `tests/conformance/support/
  sample_runner.py` harness `run_samples.py` drives: that harness's `discover()` only
  finds samples with a `samples/_harness/<name>/sample.json` entry, and its
  `_execution_contract` validation unconditionally requires
  `entrypoint.kind == "portable-application"` — it has not been extended for the
  non-portable-application entrypoint kinds ACCEPTANCE-001/ENTRYPOINT-001 already made
  buildable at the lifecycle layer. Wiring these two Components into that specific
  conformance harness (a pinned acceptance oracle plus an execution-interface fixture,
  after first teaching it to accept a non-portable-application entrypoint) is real
  follow-on work, tracked separately rather than folded into this item.
- **Evidence:**
  - [x] Both skills pass NVIDIA SkillEvaluator.
  - [x] Both skills generate a representative sample Component (a persistent Python
        service; a React dashboard) end to end.

### [x] SOURCE-COMP-001 — Flavor resolution rejects multiple singleton-axis default selectors before overrides are applied

- **Priority:** P1
- **GitHub issue:** [#46](https://github.com/NVIDIA-dev/literate-ai/issues/46)
- **Owner:** `application/flavor_selection.py` (`apply_flavor_selectors`)
- **Direction:** Two `default_flavor_selectors` sharing a singleton-cardinality axis
  raised `flavor_selection.mutually_exclusive_flavors` unconditionally before any
  `--flavor` override was even read, so no override could ever disambiguate it.
- **Completion evidence:** `d78f9a9` — mutual-exclusion validation moved from an
  unconditional check on the initial set to a single pass after every selector
  (including CLI overrides) has been applied; an unresolved conflict still fails
  closed.
- **Evidence:**
  - [x] An override can disambiguate two singleton-axis default selectors.
  - [x] An unresolved singleton-axis preference conflict still fails closed.

### [x] SOURCE-COMP-002 — Multi-source-root Components consistently fail SBOM composition validation

- **Priority:** P1
- **GitHub issue:** [#39](https://github.com/NVIDIA-dev/literate-ai/issues/39)
- **Owner:** `adapters/dependencies/lifecycle.py` (`_require_complete_source_composition`)
- **Direction:** A Component declaring two source roots (per
  `flavors/javascript/openspec/spec.md`'s "multi-toolchain frontend role" provision —
  the framework's only documented mechanism for this) consistently fails
  `build:dependencies.source-composition-unjustified`, across two attempts at the
  identical document hash, not resolved by retrying.
- **Root-caused 2026-08-16, not a validation or generation bug:** exhaustive trace of
  `CycloneDxLifecycleResolver.validate_source` found exactly two accepted `compositions`
  shapes in the entire file — `{"aggregate": "complete", "dependencies": [root_ref]}`
  (zero external dependencies; the default, non-Bazel path) and
  `{"aggregate": "incomplete_third_party_only", ...}` (Bazel/Bzlmod-detected intent
  only, via `_reconcile_bazel_source_intent`). No third shape exists anywhere that
  accepts a complete composition enumerating real npm dependencies. This is consistent
  with `flavors/javascript/openspec/spec.md`'s own unconditional "Deterministic
  dependency-free output" requirement ("SHALL use no npm package"), which the frontend-
  role provision never carved an exception out of — it changes only source-path
  ownership and the backend-invocation contract. So the failure is deterministic and
  correct by current design, independent of root count and independent of anything the
  coding CLI generates: a JS Component asking for real npm dependencies cannot pass
  source-composition validation today, whether single-root or multi-root, frontend-role
  or not. The reporter's own premise (that the frontend-role provision implicitly
  permits npm dependencies for a "React dashboard" root) doesn't hold against the text;
  the ambiguity that let that premise seem reasonable is now closed in
  `flavors/javascript/openspec/spec.md`. This did not require reproducing via a live
  coding-CLI generation run: the two accepted shapes are exhaustive and unconditional on
  root count, so no live run could produce a third, differently-shaped, accepted
  composition — running one would have confirmed what the code already guarantees, not
  discovered anything new.
- **Real gap this surfaces, not fixed here:** the framework has no capability for a
  JavaScript Component to depend on real npm packages at all outside the Bazel/Bzlmod
  path — not a bug, but a genuine missing capability if a Component's frontend role is
  meant to support a real component-library-based UI. This is the same tension #67
  flags for `react-dashboard-application` implying component-library-shaped patterns
  while the sibling `javascript-portable-json-application` skill forbids npm packages
  outright. Filing a distinct capability item for "npm-dependency-capable JavaScript
  Flavor axis" is the right follow-up, not a speculative widening of
  `_require_complete_source_composition`.
- **Evidence:**
  - [x] The two accepted `compositions` shapes are exhaustively enumerated and neither
        accepts real npm dependencies, confirming the failure is deterministic and
        by-design, not a coding-CLI or validation-logic bug.
  - [x] `flavors/javascript/openspec/spec.md`'s frontend-role provision no longer reads
        as an implicit npm-dependency exception.

### [x] RELEASE-004 — Release check's declared-scope enforcement is incompatible with the mandatory documentation-authority-review precondition

- **Priority:** P1
- **GitHub issue:** [#55](https://github.com/NVIDIA-dev/literate-ai/issues/55)
- **Owner:** `project_releases.py` (`check_release`, `prepare_release`)
- **Direction:** `litai release prepare`'s version bump legitimately changes
  `literate.project.json` (in the release's declared scope), which stales the separate
  documentation-authority marker (out of scope) — the release gate's own `litai
  test`/`build` invocation could then never pass against a validly-scoped prepared
  commit.
- **Completion evidence:** `8d1f4c9` — `ReleasePolicy` accepts an optional
  `documentation_authority` path list; `prepare_release` refreshes a declared, stale
  marker in the same pass as the version bump, and `check_release`'s scope enforcement
  permits those paths.
- **Evidence:**
  - [x] `litai release prepare` refreshes both the version authority and a declared,
        stale documentation-authority marker in one scoped commit.

### [x] CACHE-008 — `litai cache publish` crashes with an uncaught `AttributeError`

- **Priority:** P1
- **GitHub issue:** [#63](https://github.com/NVIDIA-dev/literate-ai/issues/63)
- **Owner:** `application/source_cache_publication.py`, `contracts/generation_cache.py`
- **Direction:** `SourceCachePublicationService.publish` read
  `entry.source_tree_identity` directly, but `AcceptedSourceCacheEntry` only carried it
  nested at `entry.derivation.source_tree_identity` — an uncaught traceback for every
  real accepted entry.
- **Completion evidence:** `7bdeddb` — `AcceptedSourceCacheEntry` now exposes a
  `source_tree_identity` property forwarding to `derivation.source_tree_identity`,
  matching `StandardSourceAdmissionCacheEntry`'s existing accessor. Regression test
  exercises the real dataclass, not a `Mock(spec=...)`, since the existing test suite's
  use of a spec'd mock is exactly why this shipped uncaught.
- **Evidence:**
  - [x] `litai cache publish` succeeds against a real accepted entry.

### [x] CACHE-009 — Two accepted source-cache entries at the same key raise an uncaught `SourceCacheError`

- **Priority:** P1
- **GitHub issue:** [#54](https://github.com/NVIDIA-dev/literate-ai/issues/54)
- **Owner:** `adapters/cache/filesystem.py` (`SourceCacheResolver.resolve`)
- **Direction:** Consecutive `--force-regeneration` retries can independently accept
  two different results at the same resolved cache key; every subsequent `litai
  test`/`build` then crashes with an uncaught `SourceCacheError`, and `litai test` has
  no `--source-cache-entry` disambiguation flag the way `litai rebuild` does.
- **Completion evidence:** `SourceCacheError` was already typed (`.code`/`.message`);
  the real gap was the same class of bug as ENTRYPOINT-001/#33 — nothing in the `litai
  test`/`build`/`generate` call chain caught it. Added to the CLI's top-level backstop
  in `source_to_specification.py::main`. `litai build`/`litai test` also gained
  `--source-cache-entry`, forwarded through their shared `_build_from_args` helper to
  the same local `rebuild_from_args` call `litai rebuild` already uses.
- **Evidence:**
  - [x] Two accepted entries at one cache key fail closed through a typed error with a
        CLI-exposed way to disambiguate, on both `litai test` and `litai rebuild`.

### [x] WORKER-002 — Add authenticated bounded worker capability attestations — WON'T FIX

- **Priority:** P1
- **GitHub issue:** [#51](https://github.com/NVIDIA-dev/literate-ai/issues/51) (closed)
- **Direction:** Physics Workbench sample's private Windows worker probe could not expose attributable
  identities for NVIDIA adapter/driver, CUDA, MSVC, Bazel, CMake/Ninja, Python, SDK
  runtimes, or WebRTC routes, so it retained native/runtime and provenance scoring at
  0 despite the route being reachable.
- **Conclusion (2026-08-15, per explicit user direction):** GitHub/GitLab-hosted CI
  already runs every job inside a VM-isolated runner, which provides the isolation
  guarantee this issue was after for hosted targets. The private worker fleet's
  non-Linux hosts (macOS, Windows) have no equivalent to `sandbox-exec`/`bwrap`-grade
  sandboxing available at all, so a new bounded-attestation subsystem could not
  actually deliver the cross-platform guarantee it describes either way. Closed as
  won't-fix rather than building a large new security-sensitive subsystem to
  re-provide what the execution environment already provides (or can't provide).
  Real prior art was identified before this decision, kept here in case the decision
  is revisited: `contracts/worker_capabilities.py`/`adapters/worker_capabilities.py`
  already model a narrower hardware-observation attestation;
  `source_to_specification/sandbox.py` already implements the "one fixed harness
  only" `sandbox-exec`/`bwrap` allowlisted-path pattern, currently scoped to local
  observation only; `security/isolation/contracts.py` already models staged mandatory
  controls and decision/evidence separation.

### [x] WORKER-003 — Add verifier-authorized bounded worker build actions with provenance — WON'T FIX

- **Priority:** P1
- **GitHub issue:** [#52](https://github.com/NVIDIA-dev/literate-ai/issues/52) (closed)
- **Direction:** Physics Workbench sample found no approved bounded worker action for source-building
  third-party dependencies on its private Windows worker, so it could not authorize
  those builds or receive attributable intermediate/output identities.
- **Conclusion (2026-08-15, per explicit user direction):** Closed as won't-fix for the
  same reasoning as #51/WORKER-002, which this depends on — the isolation this issue
  asks for is already provided by VM-level isolation on hosted CI targets, and is not
  achievable cross-platform on the private worker fleet's non-Linux hosts.

### [x] CI-002 — Add a `build-cmake` Flavor for the `build.system` axis

- **Priority:** P2
- **GitHub issue:** [#56](https://github.com/NVIDIA-dev/literate-ai/issues/56)
- **Owner:** `flavors/`, `skills/specification-to-source/`
- **Direction:** Add `build-cmake` alongside the existing `build-bazel`/`build-make`
  Flavors: `flavors/cmake/flavor.md`, a `standard-command-profile.json`, a sibling
  `cmake-build-system` skill, and sample coverage exercising it the way Bazel/Make
  already are.
- **Not attempted 2026-08-15:** filed by the user explicitly for the 0.3.1 planning
  queue, not for implementation now (per the issue's own "Scope note"). This is real
  skill-authoring work (CMakeLists.txt generation conventions, target/dependency
  mapping) plus cross-platform sample verification that cannot be honestly validated
  without a live coding-CLI generation run; left for a dedicated pass.
- **Fixed 2026-08-17:** added `flavors/cmake/flavor.md` +
  `standard-command-profile.json`, the sibling `cmake-build-system` skill, and a
  `src/literate_ai/adapters/builders/cmake.py` builder, mirroring `flavors/bazel`/
  `flavors/make`. Live end-to-end validation (`litai lock`/`litai generate` against
  `samples/hello-component` with `+python +build-cmake +os-macos`, `CODING_CLI=claude`)
  found a real bug: the coding CLI generated `${CMAKE_COMMAND} -E chmod`, a
  subcommand that does not exist in any CMake release, failing the build. Fixed by
  adding explicit skill guidance (`cmake-build-system/SKILL.md`'s `limitations`)
  against inventing nonexistent `cmake -E` subcommands, pointing at `file(CHMOD ...)`
  or, better, relying on tooling (Python's `zipapp`) that already sets the executable
  bit. Regenerated from the fixed skill and independently verified with real `cmake`/
  `ctest` invocations (not just the framework's own build step): `cmake -S . -B
  <dir>` configures cleanly, `cmake --build <dir>` succeeds, `ctest --test-dir <dir>`
  passes 1/1. `run_samples.py`'s harness (`samples/_harness/<name>/sample.json` +
  pinned `acceptance/execution.json`) was not extended with a new permanent
  `build-cmake` entry in this pass — `samples/flavor-matrix/component.md` already
  declares a `build-system` Flavor slot (`zero-or-one` cardinality) that
  `+flavor://literate-ai/build-cmake` can select without any Component changes, the
  same slot Bazel/Make coverage in that harness already exercises; wiring an actual
  pinned acceptance fixture through that harness is real follow-on authoring work,
  not folded into this item.
- **Evidence:**
  - [x] A Component selecting `+flavor://literate-ai/build-cmake` builds/tests/runs
        through the native Standard adapter, consistent with Bazel/Make: verified
        directly via `litai lock`/`litai generate` plus real `cmake --build`/`ctest`
        against `samples/hello-component`, not yet through the `run_samples.py`
        pinned-harness path (see note above).

### [x] RELEASE-005 — Make the release gate's execution target an explicit, durable user choice (`--target github|gitlab|local`)

- **Priority:** P2
- **GitHub issue:** [#58](https://github.com/NVIDIA-dev/literate-ai/issues/58)
- **Owner:** `litai release check`, `make release-check`
- **Direction:** The release gate's only execution target today is whatever
  `.github/workflows/ci.yml` happens to declare; the private worker fleet
  (`literate.workers.json`) is never wired into it, and nothing lets a user choose.
- **Investigated 2026-08-15, deferred:** this project has zero existing GitLab
  integration anywhere — `release_policy.provider.kind` is hardcoded to accept only
  `"github"` (`project_releases.py`: `"only github is currently supported"`).
  Implementing real `gitlab` dispatch means designing and building an entire new
  provider surface with no way to test it against a real GitLab instance from this
  environment; `github` dispatch needs real GitHub Actions API polling. This is
  new-provider-surface design work, not a quick patch — left open rather than
  half-implemented.
- **Fixed 2026-08-16:** `litai release check --target local|github|gitlab` is now an
  explicit, durable choice, scoped exactly to `local` and `github` as investigated
  above; `gitlab` is still rejected fail-closed (`release.target_unsupported`), not
  half-implemented. Without an explicit `--target`, `check_release` falls back to a
  project's declared `ci_targets` preference (`ProjectDefinition.ci_targets`, first
  entry) when present, and to today's existing behavior (run the gate on the
  invoking machine, recorded as target kind `legacy-local`) otherwise.
  `--target local` resolves `literate.workers.json` via
  `load_execution_worker_catalog`, fails closed
  (`release.target_unconfigured`) when it is missing/invalid or declares no SSH
  worker, deterministically selects the lexicographically first SSH worker (the
  catalog's own `worker_id`-sorted invariant), verifies the worker's workspace is
  checked out at the exact prepared revision (`release.worker_revision_mismatch`
  otherwise), and dispatches `policy.gate_argv` to it over the existing bounded SSH
  transport (`ssh_transport.ssh_arguments` / `BoundedSshProcessRunner`), failing
  closed with `release.worker_unreachable` on a transport failure. `--target
  github` polls `gh run list` for the exact checked-out revision
  (`release.provider_unavailable` if `gh` is unavailable) until a run for that SHA
  completes or `policy.gate_timeout_seconds` elapses
  (`release.gate_timeout`), then fails the gate on any non-`success` conclusion
  (`release.gate_failed`). The prepared-release evidence gained a required `target`
  object (`kind`, plus `worker_id`/`endpoint` for `local` or
  `run_id`/`run_url`/`conclusion` for `github`) recording which target produced the
  passing gate.
- **Evidence:**
  - [x] `--target local` dispatches through the configured private worker fleet and
        fails closed when unconfigured or unreachable:
        `tests/e2e/test_project_releases.py::ReleaseTargetTests::test_target_local_dispatches_through_the_configured_worker_fleet`,
        `::test_target_local_fails_closed_when_worker_fleet_is_unconfigured`,
        `::test_target_local_fails_closed_when_worker_is_unreachable`.
  - [x] The release evidence records which target produced a passing gate:
        `::test_target_local_dispatches_through_the_configured_worker_fleet`,
        `::test_target_github_polls_to_a_passing_conclusion`,
        `::test_legacy_default_runs_on_the_invoking_machine_when_undeclared` assert
        the recorded `target` field. Also covered:
        `::test_target_github_fails_on_a_non_success_conclusion`,
        `::test_target_github_times_out_when_no_run_completes`,
        `::test_target_gitlab_is_rejected_with_a_typed_not_yet_supported_error`,
        `::test_declared_ci_targets_preference_is_used_when_no_explicit_target`.

### [x] CI-003 — Widen the CI Python matrix from 3.11/3.12 to include a materially newer minor for real version diversity

- **Priority:** P1
- **GitHub issue:** [#61](https://github.com/NVIDIA-dev/literate-ai/issues/61)
- **Owner:** `.github/workflows/ci.yml` (`conformance` job matrix)
- **Direction:** 3.11 and 3.12 are close enough in stdlib behavior that the matrix
  wasn't exercising real version diversity — PR #40's `test_cli_help` fix for Python
  3.14's default `argparse` colorizing was only found by running locally under 3.14.
- **Completion evidence:** `3d8f7ce` — matrix widened to `3.11`/`3.14`, keeping
  minor-only resolution to match this workflow's existing Node pin (not exact-patch
  pins, since verifying real published CPython patch versions isn't possible from this
  environment). `windows-conformance` and `sample-composition` stay pinned to 3.12.
- **Evidence:**
  - [x] `conformance` job matrix includes Python 3.11 and a materially newer minor.

### [x] CI-004 — Wire `litai profile` into CI so runner logs are actually observable

- **Priority:** P2
- **GitHub issue:** [#57](https://github.com/NVIDIA-dev/literate-ai/issues/57)
- **Owner:** `.github/workflows/ci.yml` (`windows-conformance` job), new
  `scripts/profile_pytest.py`
- **Direction:** `litai profile` only wraps `rebuild`/`build`/`test`/`generate`; CI
  invokes `pytest` directly, so the structured NDJSON sink was never opened for a CI
  run.
- **Completion evidence:** `efb61a2` — `scripts/profile_pytest.py` reuses the same
  sink and `literate-ai/profile-report@1` report machinery around an arbitrary pytest
  invocation; wired into the Windows job, always-on, uploaded as a
  `windows-conformance-profile` artifact. Known limitation documented in the script:
  pytest-xdist workers run in separate processes, so only what happens in the
  coordinating process is captured under this repo's default `-n auto` distribution.
- **Evidence:**
  - [x] The Windows job's test step produces an NDJSON trace and hotspot report,
        uploaded as a retrievable CI artifact.

### [x] WORKER-004 — Make admitted-source worker continuation diagnostic and fail closed

- **Priority:** P1
- **GitHub issue:** [#65](https://github.com/NVIDIA-dev/literate-ai/issues/65)
- **Owner:** `cli/generation.py` source verifier, `adapters/standard_project.py`
  accepted-source-only continuation, `adapters/remote_execution.py`/`cli/worker.py`
  remote dispatch, `adapters/ssh_transport.py` transport
- **Direction:** A derived-project target matrix exposed three related Standard
  source-custody gaps: (1) an admission verifier failure named only the command's
  argv[0], no failing Component revision, exit status, or bounded output; (2) a
  remote build intended to continue only from verifier-admitted source could fall
  through to worker coding-CLI generation instead of failing closed; (3) Windows
  remote restore referenced cache-key membership files not staged into the archive.
- **Investigated and partially fixed 2026-08-15:**
  - (1) fixed: `_CommandSourceVerifier` now names the failing Component revision,
    exit status, and a bounded stderr/stdout excerpt in
    `source_admission.tests_failed`.
  - (2) fixed: added `ExecutionDispatchRequest.accepted_source_only` (schema-versioned,
    optional/backward-compatible wire field, included in `authority_identity`);
    `build`/`test` gained a `--from-accepted-source` flag mirroring `rebuild`'s;
    `RemoteLifecycleRebuilder.__call__`'s protocol and its implementation
    `rebuild_remote_lifecycle` (`cli/worker.py`) now accept and forward
    `accepted_source_only`, which `execute_remote_request` threads from the dispatch
    request. A remote `accepted_source_only` request now hits the same
    `admitted != required` fail-closed check the local path already had whenever
    membership isn't present on the worker — it can no longer silently fall through
    to worker coding-CLI generation. Regression tests added for the wire round-trip
    and for the intent reaching the worker-side rebuild call.
  - (3) fixed: a worker's dispatch workspace is freshly extracted per run with no
    pre-existing accepted-source-cache, so (2) alone made every remote
    `accepted_source_only` request fail closed unconditionally — safe, but unable to
    ever get an actual remote cache hit. `capture_source_archive` now also stages the
    project's whole writable accepted-source-cache tree (`generated/accepted-source-cache`
    by default) as a fifth transferred archive (`accepted-source-cache.tar.gz`) whenever
    `accepted_source_only` is set; every entry inside is already independently
    content-addressed by its own path-embedded hash, so staging the whole tree rather
    than computing a reachable subset is simple and safe (never a correctness problem,
    only a transport-size one). `ExecutionSourceMaterialization.accepted_source_cache_reference`
    binds the staged archive's transport identity; the worker verifies that identity,
    then a new `extract_accepted_source_cache_archive` (`remote_source_guard.py`)
    safely restores it archive-relatively into the worker's own cache root (rejecting
    traversal, symlinks, and case-collisions) before `rebuild_remote_lifecycle` runs —
    portable on both POSIX and Windows since restoration never depends on the archive's
    own path separators or the launcher's cwd. `litai worker execute` gained
    `--accepted-source-cache`; the SSH transport passes it only when the fifth file was
    staged. A pre-existing (e.g. ungitignored) cache directory inside the extracted
    project tree is replaced, not merged, since accepted-source-cache is disposable
    regenerable state, never authored content.
  - **Bonus finding while investigating the remote path, fixed:** the SSH transport
    binary was a hardcoded `"ssh"`/`"scp"` literal in `ssh_transport.py`, not
    per-worker configuration, contradicting the private fleet's actual need (some
    workers route through a VPN/Tailscale-aware SSH-compatible wrapper, not plain
    OpenSSH). Added an optional `ExecutionWorker.transport` field (default `"ssh"`,
    backward compatible, SSH-kind only); `scp` stays fixed. Verified live against a
    real private Windows worker over both `ssh` and a custom transport.
- **Evidence:**
  - [x] A failing admission command names the failing Component revision with
        attributable bounded diagnostics.
  - [x] Explicit `--from-accepted-source`/remote accepted-source continuation never
        selects or invokes a coding CLI on a worker; missing/mismatched membership
        returns a typed accepted-source-unavailable error before generation.
  - [x] Windows staged membership restore works from an archive-relative cache root.
  - [x] The SSH transport binary is per-worker data, not a framework constant.

### [x] WORKER-005 — Bind SSH dispatch to the selected worker launcher

- **Priority:** P0
- **GitHub issue:** [#89](https://github.com/NVIDIA-dev/literate-ai/issues/89)
- **Owner:** execution-worker contract and bounded SSH lifecycle adapter
- **Direction:** Accepted-source continuation reached stale ambient `litai`
  installations after exact worker provisioning, so the staged cache option was
  rejected before restore on Linux and Windows.
- **Conclusion:** Make the SSH worker's lifecycle executable explicit private
  configuration covered by worker identity. Dispatch must invoke that exact path and
  fail closed when it is unavailable; legacy workers may retain bounded conventional
  discovery, but it cannot override an explicit launcher. Keep endpoints, usernames,
  and private paths out of repository examples and evidence.
- **Implementation:**
  - [x] Add the optional exact launcher to the worker contract/schema and SSH command
        projection without changing transport selection.
  - [x] Add Linux/Windows command regressions proving stale ambient launchers cannot
        override the configured executable.
  - [x] Re-run accepted-source cache restore on both target workers.
- **Fixed 2026-08-16 (`51bd3a62`):** `ExecutionWorker` gained an optional
  `lifecycle_executable`; when set, SSH command projection (both POSIX and PowerShell
  paths) invokes that exact configured path and never falls back to ambient discovery,
  while legacy workers without one keep the existing bounded discovery behavior.
- **Evidence:**
  - [x] `tests/critical/test_execution_dispatch_contracts.py::test_ssh_worker_lifecycle_
        executable_is_identity_bound_and_ssh_only` and
        `tests/smoke/test_ssh_execution.py::test_receivers_use_configured_lifecycle_
        executable_without_discovery` (both POSIX and Windows-path launcher forms)
        cover this; full unit suite passes.

### [x] LOW-DBC-001 — Scope the LOW-layer Design-by-Contract skill convention

- **Priority:** P2
- **Owner:** Go, Python, and Rust specification-to-source skills
- **Conclusion:** The 0.5-line implementation is now forward-ported to `main`: internal
  preconditions, postconditions, and invariants use each language's native mechanism,
  remain distinct from untrusted-input validation, and surface through the existing
  generated-test boundary rather than a new failure channel.
- **Evidence:**
  - [x] Go, Python, and Rust catalog/template skills remain byte-identical and carry
        their versioned contract guidance.
  - [x] The focused skill-content regression passes; the executed examples and captured
        evidence remain in
        [`docs/history/roadmap/0.5.0-design-by-contract-examples/`](0.5.0-design-by-contract-examples/NOTES.md).

### [x] CACHE-CONTINUATION-001 — Published exact source membership absent during accepted-source continuation

- **Priority:** P0
- **GitHub issue:** [#139](https://github.com/NVIDIA-dev/literate-ai/issues/139)
- **Owner:** accepted-source cache continuation / `litai build --from-accepted-source`
- **Direction:** An exact verifier-admitted, published filesystem-v2 cache membership
  (copied byte-for-byte into an isolated project's `generated/accepted-source-cache`,
  same key, same distribution/revision) is not discovered by continuation:
  `source_cache.runtime_absent` on all 13/13 canonical macOS cells despite 56/56 fresh
  admissions and clean spec/lock preflight. The reporter asks specifically: trace the
  exact lookup identity derived during generation/admission versus accepted-source
  continuation and report which bound field differs.
- **Conclusion:** The differing bound field is `execution_plan_identity`. Admission
  compiled the generation-plan endpoint as
  `cli://…/tool?identity=<live executable digest>&binding=<tool binding>`.
  Continuation uses `AcceptedSourceCodingCliSelection`, whose `executable_identity`
  is the recovered tool-binding URI, not that digest. Lookup keys still include
  `execution_plan_identity`, so `resolver.resolve()` missed copied filesystem-v2
  membership. The portable `coding_cli_tool_binding_identity` already closes over
  the executable digest, so the plan endpoint now binds only `?binding=…`. Session
  `request_identity` stays out of lookup. Landed as `3f139c7a` on
  `feat/cli-sdlc-debug` (isolated `12cdcff1`).
- **Evidence:**
  - [x] Two-project admit-then-copy fixture in
        `tests/unit/test_source_cache_continuation.py` publishes in project A,
        copies `generated/accepted-source-cache` into project B, and continuation
        lookup/restore finds the membership.
  - [x] Differing bound field named: `execution_plan_identity`.
  - [x] `LITAI_SESSION_ID=dev make source-admission-check` — 68 passed, plus
        `test_generation_planning` and `CodingCliSelectionTests`.

### [x] SSH-EVIDENCE-001 — Remote evidence manifests exceed the SSH result limit

- **Priority:** P0
- **GitHub issue:** [#138](https://github.com/NVIDIA-dev/literate-ai/issues/138)
- **Owner:** remote worker execution result protocol (`litai worker execute`, PR
  #132/#136's remote-evidence protocol)
- **Direction:** `litai worker execute`'s JSON result exceeds the coordinator's
  fixed one-MiB SSH stdout limit on real Linux/Windows Standard lifecycles (0/27 on
  each platform in the reporter's matrix), even though this is the non-verbose
  receiver result, not coordinator tracing.
- **Conclusion:** Implemented the issue's own required contract: a new
  `RemoteExecutionControlResult` wire contract carries only bound identities, observed
  facts, status, canonical manifest/bundle digests and declared sizes, the fixed
  `staged:remote-evidence.tar.gz` transfer handle, and one bounded redacted summary
  (capped well under the fixed one-MiB SSH stdout bound). `litai worker execute`
  returns this compact envelope instead of the full `ExecutionDispatchResult`
  whenever `--evidence-output` is set; the SSH handler rejects any stdout above the
  fixed limit before parsing, downloads the bundle through the existing scp transfer,
  and `load_and_import_remote_evidence_bundle` independently verifies the declared
  bundle size/digest and the canonical manifest's exact size/digest before importing
  every listed file and binding the imported manifest back to the control result
  (`RemoteExecutionControlResult.bind_imported_manifest`). The stdout bound itself was
  not raised.
- **Evidence:**
  - [x] `tests/critical/test_remote_execution.py::test_large_27_cell_manifest_uses_bounded_out_of_band_control`
        builds a synthetic 27-cell-scale manifest whose canonical bytes exceed 1 MiB,
        asserts the derived control result stays under 1 MiB and never embeds the
        large per-cell content, then proves `load_and_import_remote_evidence_bundle`
        imports the full bundle and rejects tampered declared manifest/bundle sizes.
        `test_ssh_execution.py::test_handler_rejects_oversized_malformed_worker_control`
        proves the SSH handler fails closed on an over-limit control response before
        ever parsing it. Existing acknowledgement-gated cleanup and retry/idempotence
        tests continue to pass against the new control-result shape.

### [x] MATRIX-CHECKPOINT-001 — `make samples` and generated-project test execution have no finer-than-gate checkpoint/resume

- **Priority:** P2
- **GitHub issue:** [#124](https://github.com/NVIDIA-dev/literate-ai/issues/124)
- **Owner:** `scripts/run_checkpointed_gates.py` (coarse, gate-level resume);
  generated-project Standard lifecycle TEST phase (no resume mechanism at all)
- **Direction:** `make samples` is one atomic checkpointed unit spanning Python/JS/
  Rust/C++/CUDA; a Rust failure partway through forces re-verifying every
  already-passed language on resume. Separately, generated downstream projects' own
  test execution has no per-test resume analogous to
  `scripts/run_checkpointed_unittests.py` (which is Python-`unittest`-specific and
  only wired to this repo's own suite).
- **Conclusion:** Two candidate directions from the issue: (a) treat each sample/
  language inside `make samples` as its own resumable unit; (b) generalize
  content-fingerprinted per-test resume past Python `unittest` for generated
  projects' native test runners. **Direction (a) is done** — delivered as a side
  effect of `SAMPLES-RESILIENCE-001`'s per-sample checkpoint (`842f9404`).
  **Direction (b) is not a bounded defect and is declined as product scope for
  this item.** Generated projects run the Standard TEST phase through each
  language Flavor's command profile (`pytest`, `cargo test`, `ctest`, `go test`,
  `swift test`, …). Content-fingerprinted per-test resume needs a runner-specific
  case parser, a stable case identity, and a fail-closed skip policy so a test
  that never passed cannot be omitted. That is the same research as
  [CI-SHARD](https://github.com/NVIDIA-dev/literate-ai/issues/83) language
  sharding, not a portable extension of `run_checkpointed_unittests.py`. A fake
  generic skip would be dishonest. This repository's Python `unittest`
  checkpointer stays local to the framework suite. Comment on #124 with this
  bound.
- **Evidence:**
  - [x] A failure in one sample inside `make samples` no longer forces re-verifying
        already-passed samples on resume: `run_all` checkpoints each sample's complete
        case to `OBJ_DIR/samples-checkpoint.json`, keyed by sample tree digest, flavor
        selectors, packaging scope, platform, and lifecycle-driver implementation
        digest, and self-clears after a complete pass so a *successful* run never lets
        the next run skip everything. Measured: a resumed `hello-component` reported
        `skipped (checkpointed pass)` in 1.8s versus ~90s, with an identical report.
  - [x] Per-test resume for generated native runners is recorded as out of scope
        for this item: it is a per-Flavor test-harness research program, not a
        bounded defect on the sample checkpoint.

### [x] PACKAGE-EDGE-001 — Packaging-only provider edges retain package authority without a runtime process binding

- **Priority:** P1
- **GitHub issue:** [#110](https://github.com/NVIDIA-dev/literate-ai/issues/110)
- **Owner:** `LocalStandardLifecyclePorts._provider_environment_values()`,
  `project_standard_toolchain_closure`
- **Direction:** A Component with an exact `dependency_kind: packaging` edge (provider
  built and exported successfully) fails Bazel build before compilation with
  "provider artifact ... has no runtime binding" -- `_provider_environment_values()`
  walks every provider artifact regardless of edge kind, but only `artifact-export`
  (build/runtime) edges are supposed to need a process-environment binding; a
  packaging-only edge should carry package result/plan provenance into package
  assembly/acceptance without one. Already triaged (2026-08-16) as "a real, scoped
  Bazel-packaging-edge defect," deferred from 0.4.1 to a follow-up release.
- **Conclusion (corrected again 2026-09-01):** The earlier fix separated
  `build_providers`, which stopped the erroneous process binding, but it also dropped
  packaging-only providers from the build intent, manifest, exported artifact closure,
  package link plan, and acceptance authority. The absence of the original exception
  was therefore a false completion. The 0.9 implementation carries an independent,
  typed `package_artifact_identities` / `package_dependency_artifacts` channel through
  intent, plan, manifest, graph, and wire schemas. Build adapters receive only
  build/runtime dependencies; exports and package closure bind their exact union.
- **Next action:** Complete; retain the packaging-only graph regression in the 0.9
  release gate.
- **Evidence:**
  - [x] `_provider_environment_values()` only requires a runtime binding for
        `artifact-export` edges; a packaging-only edge never becomes a process input.
  - [x] A packaging-only provider remains explicit in build intent/plan authority,
        `BuildActionRequest.package_dependency_artifacts`, the realized export
        dependency closure, artifact graph, package link plan, and serialized schema.
  - [x] Focused local, Bazel, Cargo, graph, wire, and CLI regressions pass (213 tests,
        3 expected skips) on 2026-09-01.

### [x] RELEASE-EVIDENCE-001 — Close release evidence over every sub-workflow, stage, and host dialog

- **Priority:** P0
- **Release target:** 0.7.0
- **Re-scoped:** 0.9.0 (2026-09-01) for any remaining work; the historical target above records where the item originated / partially shipped.
- **Owner:** `litai release check`, `make release`, `scripts/run_checkpointed_gates.py`,
  `tests/conformance/support/sample_runner.py`,
  `src/literate_ai/adapters/project_lifecycle_driver.py`
- **Direction:** The attempted `0.5.2` release failed with no usable evidence. Afterwards
  only unrelated leftovers were recoverable — pip traceback bytecode and
  `litai-driver-failure-*.log` files from ~1:51pm
  (`RebuildSourceCacheDerivationManifest.lifecycle_plan_identity`) — while the actual
  ~3:12pm host-E2E samples crash and its sample scratch were gone. This is the current
  design, not bad luck: `_release_gate_failure_detail` keeps one collapsed 2000-byte
  tail, a passing legacy-local gate records `stdout_digest`/`stderr_digest` for bytes
  nobody kept, `run_gates` records only gate *names*, `sample_runner.main` runs the whole
  matrix inside a `TemporaryDirectory` removed even on failure, `_retain_driver_diagnostic`
  writes complete driver output to an anonymous OS-temp `mkstemp` file, the installed-CLI
  and wheel gates `rmtree(ignore_errors=True)` unconditionally, Standard lifecycle
  `failure_diagnostics` live in an in-memory dict, and `--target local`/`github` record a
  worker id or a run URL rather than the host dialog. `make release` must instead capture
  pins and pointers for every step, hierarchically, with `release` as the outermost node,
  so a failed release is root-caused from one compact record rather than by trolling logs.
- **Plan:** [`docs/history/roadmap/0.7.0-release-evidence-closure.md`](0.7.0-release-evidence-closure.md)
  — an append-only per-run evidence ledger under `_build/evidence/<run>/` inherited
  through `LITAI_EVIDENCE_RUN`/`LITAI_EVIDENCE_PARENT`, one node per stage carrying its
  exact pins and its output pointers (transcript, manifest, receipt, scratch, artifact,
  diagnostic) with digest, size, and retention state; delete-on-success-only retention so
  failures keep their scratch and transcripts; host/target dialogs as first-class nodes
  preserving the bounded SSH control envelope and digest-bound custody rules from
  `skills/agent/bind-lifecycle-evidence/SKILL.md`; and `litai release evidence explain`
  as the bounded root-to-failure triage surface.
- **Current action:** Complete through stage 5: the release spine, host-dialog
  retention, blind-step harness, and post-exit acceptance coverage are implemented.
  `legacy-local` is the complete single-host path; absent SSH/GitHub fan-out is
  recorded explicitly as unavailable.
- **Evidence:**
  - [x] `litai release evidence explain` names the failing stage, its pins, and its
        retained output pointers for an injected host-E2E sample failure under
        `make release`, with every referenced path still present after the run exits.
  - [x] No release-path failure deletes its scratch, transcripts, or diagnostics.
  - [x] `prepared-release@2` carries the evidence run, with `@1` still accepted for read.
  - [x] Remote nodes keep the ≤1 MiB control envelope and gate worker cleanup on
        acknowledged import; no transcript contains a credential value or a raw private
        endpoint.
  - [x] A run killed mid-gate still yields a valid ledger whose deepest node is
        `running` or `unavailable`.
- **Stage evidence:** Foundation landed in `dca9144a` and `aa5a3357`; the release
  spine landed in `c61abd4b`; host-dialog retention and fan-out landed in
  `4c34708b` and `e26c0b65`; the blind-step harness landed in `f62e04ac`; and
  post-exit acceptance plus default scratch lifetime landed in `1bd3c235` and
  `b310fc74`.

### [x] RELEASE-EVIDENCE-002 — Replace blind shell and Make steps with instrumented Python harnesses

- **Priority:** P1
- **Release target:** 0.7.0
- **Owner:** `Makefile` gate recipes, `scripts/find-compatible-python.sh`/`.cmd`,
  `scripts/litai-launcher`/`.cmd`, `.github/workflows/ci.yml`
- **Direction:** A step that runs outside a Python harness cannot record pins or retain
  output, so the remaining shell and Make surfaces are exactly where RELEASE-EVIDENCE-001's
  coverage would stop. `find-compatible-python.sh` runs at Makefile parse time under
  `$(shell …)`, so a failed interpreter resolution yields an empty `PYTHON` and a confusing
  downstream error even though the chosen interpreter is a release pin; `litai-launcher` is
  a blind exec; each gate recipe's only artifact is its exit status; and CI's `run:` steps
  leave nothing behind that `explain` can read.
- **Plan:** the blind-steps section of
  [`docs/history/roadmap/0.7.0-release-evidence-closure.md`](0.7.0-release-evidence-closure.md)
  — recipes stay readable one-liners delegating to an instrumented Python harness, the
  POSIX/Windows resolver pair collapses to one Python resolver with a minimal bootstrap
  shim, and CI uploads the evidence run as an artifact so a CI-side release failure is
  triaged with the identical command. `docs/presentations/**/regenerate*.sh` and
  `.claude/hooks/*.sh` are out of scope; they are not in the release path.
- **Evidence:**
  - [x] Every `RELEASE_GATES` member appears as a ledger node with pins, including the
        resolved interpreter.
  - [x] A CI release failure is triageable from the uploaded evidence run with
        `litai release evidence explain`.

### [x] RELEASE-EVIDENCE-003 — Register owned runtime custody before execution starts

- **Priority:** P0
- **Release target:** 0.7.0
- **Owner:** evidence ledger directory custody and installed/sample smoke runners
- **Direction:** An owned sample runtime root was retained after a pre-discovery
  failure, but no ledger pointer named it because registration occurred only inside
  later per-sample phase handling. The same creation-then-late-registration shape is
  present in installed project, wheel, roundtrip, and installed-E2E workspaces.
- **Conclusion:** Register each owned temporary root immediately after creation. Keep
  the pointer on the same evidence node, mark it `pruned` only after successful
  cleanup, and retain both the directory and its `retained` pointer for every failure,
  including failures before sample discovery.
- **Implementation:**
  - [x] Add append-only output-retention transition support to the evidence ledger.
  - [x] Apply creation-time registration to sample, installed-project, wheel,
        roundtrip, and installed-E2E custody roots.
  - [x] Add pre-discovery failure and successful-cleanup regressions.
- **Evidence:**
  - [x] Evidence-ledger, stage-3 retention, and stage-5 acceptance suites pass.
  - [x] Standard lint, formatting, OpenSpec, documentation, layout, driver-review,
        documentation-review, and `git diff --check` gates pass.
  - [x] A pre-discovery failure leaves a ledger pointer and an on-disk root; a
        passing run removes the root while retaining its historical `pruned` pointer.

### [x] WINDOWS-PATH-001 — Keep created files and directories within Windows MAX_PATH

- **Priority:** P0
- **Release target:** 0.6.0
- **Owner:** root onboarding `SKILL.md` and the initialized-project template copy
- **Direction:** Agents must use Windows-friendly file and directory names for every
  path they create. Windows `MAX_PATH` is 260 characters for the full absolute path.
  Long-path application manifests and registry policy exist, but a target machine must
  not be assumed to have either. Prefer short names and shallow trees so a drive
  letter, user profile, CI workspace, and nested generated/object prefixes still fit.
- **Conclusion:** Put the rule at the top of the provider-neutral onboarding skill,
  before the numbered project flow, and keep the same text in the init template so
  descendants inherit it. This is naming discipline for newly created paths; it does
  not replace `WORKER-006`'s short-root custody for restored archives.
- **Next action:** Complete. Keep new agent-created paths conservative against the 260
  character bound.
- **Evidence:**
  - [x] Root `SKILL.md` and `src/literate_ai/project_template/SKILL.md` both require
        conservative Windows-portable names and cite `MAX_PATH` 260.
  - [x] `tests.critical.test_prompt_master_agent_skill` passes (4 tests); lifecycle-driver
        TCB re-pinned after the template copy; documentation-authority review recorded
        on the same revision.

### [x] CODEGRAPH-RESILIENCE-001 — Bound CodeGraph execution and reuse exact index custody

- **Priority:** P0
- **Release target:** 0.6.0
- **Owner:** generated-source intelligence adapters and immutable index custody
- **Direction:** Reduce CodeGraph's release fragility without weakening the exact graph
  evidence required by project validation and generated-source admission.
- **Conclusion:** Implement accepted
  [ADR 0015](../../decisions/0015-bounded-codegraph-evidence-and-reuse.md): retain mandatory
  consumed graph evidence, preserve bounded actionable provider diagnostics, and reuse
  verified generated-tree index custody only across exact content/provider keys.
- **Depends on:** existing source-tree identities, immutable CodeGraph artifact custody,
  and the current required source-intelligence policy.
- **Next action:** Complete. ADR 0016 / CODEGRAPH-DEPENDENCY-001 removed the
  indexer; remaining Windows CodeGraph snapshot-replication evidence is no
  longer a 0.6.0 publication contract.
- **Implementation:**
  - [x] Failed CodeGraph operations report a bounded beginning/end diagnostic and named
        operation without exposing ambient environment or unbounded output.
  - [x] Exact generated-tree/provider/runtime/extraction/capability keys reuse verified
        immutable index custody across different disposable workspace paths.
  - [x] Source, provider, runtime, extraction, capability, artifact, or envelope drift
        invalidates reuse and fails closed or rebuilds as declared by ADR 0015.
  - [x] Duplicate generated-tree indexing with no additional consumed graph fact is
        removed; project-level required indexing remains unchanged.
- **Evidence:**
  - [x] Focused unit tests cover reuse, invalidation, tamper rejection,
        bounded diagnostics, and credential-safe output; a clean checkpoint-reset
        `make python-check` passes 2,626 tests with 27 platform skips.
  - [x] Remaining Windows two-pass snapshot-replication CodeGraph evidence is
        superseded by complete product removal (`ac23f3cf`, CODEGRAPH-DEPENDENCY-001).
  - [x] Remaining CodeGraph-matrix publication evidence is superseded by the
        same removal; 0.6.0 matrix green is owned by RELEASE-006 after the
        merge-leftover CI repair.

### [x] CODEGRAPH-DEPENDENCY-001 — Remove the source-graph indexer from the product

- **Priority:** P0
- **Release target:** 0.6.0
- **Owner:** source-intelligence policy, host preflight, worker/MAC contracts, and
  release engineering
- **GitHub issue:** none — directing-maintainer request 2026-08-24
- **Direction:** Delete the host source-graph indexer from the product in every
  form: no adapter, optional CLI, worker capability, bootstrap, documentation,
  or tests.
- **Conclusion:** See accepted
  [ADR 0016](../../decisions/0016-codegraph-not-a-product-dependency.md). The
  directing maintainer narrowed the ADR from "stop requiring the indexer" to
  complete removal. Project policy is `provider_id: none` only. Model-backed
  source-to-specification that required graph evidence is unavailable; the
  static translator remains.
- **Depends on:** accepted ADR 0016
- **Implementation:**
  - [x] Default `litai init` and this repository's `literate.project.json` to
        `provider_id: none` with every source-intelligence stage `off`.
  - [x] `validate`, `build`, `run`, `rebuild`, admission, snapshot-replication,
        and release complete without a source-graph binary or sidecar.
  - [x] Delete remaining adapter, CLI, worker-capability, and bootstrap paths
        (`86a5f815`, landed on `main` as `ac23f3cf`).
  - [x] Rewrite tests to provider none / mode off / DisabledGenerationIndexer.
  - [x] Strip user-facing and agent-facing mentions from docs, skills,
        templates, CI, and scripts.
  - [x] Repair the `scripts/wheel_smoke.py` leftover that still passed
        companion-capability kwargs into `bootstrap_worker_wheelhouse`
        (`8d84dbda`).
- **Evidence:**
  - [x] ADR 0016 is Accepted as complete removal (directing maintainer,
        2026-08-24).
  - [x] Product source, tests, workflows, skills, and current docs do not name
        the removed indexer except frozen published v1 schema URNs, historical
        decision records, and reserved leftover-path skips.
  - [x] GitHub run [`32890626746`](https://github.com/NVIDIA-dev/literate-ai/actions/runs/32890626746)
        on post-purge `main` `8d84dbda` was green, including Windows
        lint/OpenSpec/wheel. `v0.6.0` published from that revision.

### [x] RELEASE-006 — Qualify and publish 0.6.0

- **Priority:** P0
- **Owner:** release engineering / framework maintainers
- **Direction:** Close the final 0.6.0 cross-platform regressions, reconcile the
  carried-forward 0.5-line fixes and the DMN/SCXML scope, regenerate exact release
  evidence, and execute the policy-owned plan/prepare/check/publish sequence.
- **Current state:** Published. Annotated tag `v0.6.0` selects
  `8d84dbda` on `main`. GitHub Release:
  https://github.com/NVIDIA-dev/literate-ai/releases/tag/v0.6.0
  Prepared-release identity
  `sha256:d748906b3556ff1ae60ac3c0621133f0742c972da90166feefa7d8597b64d14d`.
  Publication receipt
  `sha256:49b13b3cd1de981029a14cdec2db42c1bc5038f3e3b2e6236523959d3f5b6d17`.
  Do not republish from the earlier prepared commit `f9c8e36f`.
- **Next action:** none — this item is closed.
- **CI repair update 11:** GitHub run `32878551196` on PR #168 cleared the
  prior Windows unit-test shards. The remaining Windows failure is installed
  wheel smoke: `bootstrap_worker_wheelhouse()` no longer accepts
  `capability_root` / companion-capability arguments after indexer removal.
  Repair `scripts/wheel_smoke.py` on this branch before treating Windows CI
  as green.
- **CI repair update 10:** Local `make python-check` after update 9 found more
  merge leftovers: none-provider status omitted a null `reason_code`; rebuild
  CLI still expected a ready source-intelligence artifact; quarantine cache
  required an artifact path even for `provider_id: none`; and a fixture
  provider wrote its graph file as extra source instead of reserved
  derived metadata. Repair those on `fix/0.6.0-codegraph-merge-ci` before
  requiring a GitHub matrix.
- **CI repair update 9:** Run `32862637460` on `ac23f3cf` failed Ubuntu/macOS
  Python 3.11 and 3.14 plus Windows lint and test shards. Shared causes are
  merge leftovers, not a missing indexer: the coding-CLI inverse unit test
  omitted required `_derive_standalone` `attestation_path` /
  `trust_key_path` kwargs; the live Standard service stack still constructed
  `_DisabledGenerationIndexer`; ruff reported E501/F401/I001 on the purge
  edit. Repair those before re-planning 0.6.0.
- **CI repair update:** Run `32696521897` confirmed three bounded defects. The
  documentation review marker had been recorded before the final RELEASE-006 wording,
  so every canonical-project validation correctly rejected it as stale. Windows
  translated two XML fixture writes to CRLF before tests compared the provider's exact
  bytes with LF constants. A Job Object fallback test also asserted the non-Windows
  outcome while running on Windows, where the primitive is expected to exist. Record
  the final marker after these corrections and require a fresh complete matrix.
- **CI repair update 2:** Run `32699238675` cleared all prior failures and passed
  every job except Windows shard 1. Its two failures are the same real CodeGraph 1.1.1
  initialization error in snapshot-replication's deeply nested generated tree. Keep
  real indexing mandatory; shorten only the test-owned disposable root on Windows,
  matching the framework's existing short-root custody practice, and rerun the matrix.
- **CI repair update 3:** Run `32703056177` passed 14 of 15 jobs. Windows shard 1
  proved the drive-root scratch fix works for the outer replay, but the isolated
  second replay still inherited verbose `generation-one`/`generation-two` custody
  segments and failed the same real CodeGraph initialization. Shorten those four
  disposable harness labels only; stable evidence already binds workspace references
  and content identities rather than host paths.
- **CI repair update 4:** The shortened path still failed inside CodeGraph `init`,
  confirming that path length was not an adequate diagnosis. Implement ADR 0015's
  bounded stderr now so the provider's actual Windows failure is visible; retain the
  short disposable labels as harmless defense in depth.
- **CI repair update 5:** Run `32747539745` failed `ubuntu-latest`/`macos-latest`
  Python 3.11 and 3.14 plus Windows shards 1 and 2. Shared root cause on every OS:
  `96682f84` changed `src/literate_ai` (CodeGraph runner, index custody, local
  lifecycle) without `make driver-review-record`, so
  `test_self_hosting_project_protocols_and_derived_identities_agree` reports
  `driver_identity_matches: false`. Windows-only: the diagnostic fixture wrote
  `'native diagnostic\\n'` through text-mode stderr, which became `'native
  diagnostic\\r\\n'` on a binary pipe; and
  `test_slow_pipe_close_within_five_seconds_is_not_a_false_failure` used the
  disposable directory as `cwd`, so the grandchild's lingering directory handle
  raised `WinError 32` during `TemporaryDirectory` cleanup.
- **CI repair update 6:** Run `32782219088` on `461d15e3` restored Rust DbC and
  the sample-test-runner identity. Do not rerun that workflow: the remaining
  failures are real. Windows CodeGraph `init` is overflow-killed because the
  sanitized runner drops `CI`, so Clack writes spinner frames into a pipe.
  Persistent-service acceptance must merge host process essentials after a
  packaged environment, because an empty child environment is not a viable
  Windows/`python.exe` or macOS Framework Python process.
- **CI repair update 7:** Run `32788786133` on #158 cleared Windows shard 1.
  Persistent-service now starts on Windows but `process.terminate()` kills the
  child without running its SIGTERM handler, so the shutdown marker is missing.
  macOS still times out on readiness. Do not invent `LC_ALL=C.UTF-8` on Darwin,
  and send `CTRL_BREAK_EVENT` for graceful Windows stop.
- **CI repair update 8:** Run `32799630873` on prepared commit `f9c8e36f` failed the
  Linux and macOS Python jobs plus the Windows lint job before release qualification.
  Every failure is the same formatting defect at `standard_project.py:1914`: the
  restored-cache callback lookup is 95 columns against Ruff's 88-column limit. This is
  a scoped source-format repair, not a platform or release-policy defect; restart
  preparation after it lands so release evidence binds the repaired revision.
- **Recovery update:** Re-planning from repaired commit `86594bcc` succeeded, but
  `release prepare` inserted a second `## 0.6.0` heading because current-version
  planning had no matching preparation/check recovery semantics. Preserve exactly one
  existing heading for an already-prepared untagged version, and permit a zero-diff
  prepared revision only for that exact explicit-current recovery case. Keep all dirty
  tree, version drift, tag collision, and undeclared-change failures closed.
- **Recovery update 2:** GitHub run `32800254897` proved that the first recovery still
  rewrote three semantically unchanged authority files. Those atomic replacements can
  perturb Windows checkout representation and make `release check` reject the prepared
  commit as dirty. Preparation now filters unchanged rendered content before the write
  transaction; its regression requires zero authority writes, and all 49 release tests
  pass locally. A verbose preserved run isolated the separate live
  `installed-project-e2e` failure described next.
- **Recovery update 3:** Verbose live reproduction showed Codex failing all three
  attempts because its access token could not be refreshed after the refresh token was
  reused. The classifier treated that explicit denial as an opaque failure because
  `codex login status` still returned success. Recognize the observed refresh-token
  phrase directly so it does not retry Codex. The first fix then exposed that
  cross-provider fallback after model-scope resolution violates the plan's provider
  binding; keep fallback for unbound legacy recipes, but fail the resolved provider
  directly and select a healthy provider before planning release qualification.
- **Recovery update 4:** The uninterrupted 1,562-test suite and every gate through
  `install-check` passed on `6ff469e8`. Live generation with Cursor Agent produced the
  complete expected `source/` tree plus its own root `.vibe/conversations` directory,
  which source confinement correctly rejected as unexpected application output. After
  validating the complete workspace for symlinks, remove only Cursor Agent's exact
  root `.vibe` transient tree, as is already done for unambiguous Python bytecode
  caches; continue rejecting every other path outside `source/`.
- **Recovery update 5:** Resumed qualification passed the installed-project gate
  and reached live samples. The sample catalog declared `containerized-log-tally`
  without a matching verifier handler, so discovery could never execute it; require
  every discovered scenario to resolve through the handler registry and verify the
  tally contract with the independent runtime oracle. The complete Python run also
  reached a direct `_collect` test skipped by earlier repair checkpoints and exposed
  that Cursor-specific cleanup dereferenced an absent `selection`; unbound
  collectors now trust no provider-owned root and retain fail-closed confinement.
  Fresh isolated runs of both the scheduler and containerized tally samples pass.
- **Recovery update 6:** The regenerative sample's generated `rules_cc` source-SBOM
  node followed the exact Bzlmod contract in the prompt, including
  `literate-ai:bzlmod-requested-version`, but the authority reconciler allowed only
  generic dependency kind and scope properties on third-party nodes. Admit this
  requested-version observation so the downstream Bzlmod lifecycle can validate its
  exact shape and value; continue rejecting reserved refs, managed properties,
  reserved kinds, authority reparenting, and unsafe graph edges. A regression now
  preserves the exact unresolved `rules_cc` component through reconciliation.
- **Recovery update 7:** After the SBOM repair passed the uninterrupted Python
  suite, live regeneration reached provider selection and observed Claude's exact
  `You've hit your individual spend limit` denial. The quota classifier previously
  knew only Codex's observed spend-cap wording, so Claude consumed a futile retry
  and stopped before Cursor Agent fallback. Classify this verbatim denial as quota
  exhaustion; authentication and resolved-model-scope boundaries remain unchanged.
- **Evidence:**
  - [x] The focused 52-test bounded-process, CodeGraph, SSH, and conversion set passes.
  - [x] Strict Ruff lint and formatting checks pass.
  - [x] The pushed revision passes every GitHub Actions job: run
        [`32890626746`](https://github.com/NVIDIA-dev/literate-ai/actions/runs/32890626746)
        on `main` `8d84dbda`.
  - [x] All 0.5-line fixes identified by the corrected whole-file audit are present on
        the integration branch; focused regressions and a clean 2,622-test Python run
        pass. Final remote-main identity follows merge.
  - [x] Local distribution qualification passes on the reconciled branch: `wheel-check`
        builds and inspects the 0.6.0 wheel, `install-check` proves isolated bootstrap
        and canonical project planning, `installed-e2e` proves the installed command
        worker path and records its sentinel, CodeGraph sync/check reports 670 files,
        20,470 nodes, and 78,337 edges, lifecycle-driver review is current, and
        documentation renders 119 Mermaid diagrams from 430 Markdown files.
  - [x] 0.6.0 scope is closed, release evidence is current, and publication is
        verified: https://github.com/NVIDIA-dev/literate-ai/releases/tag/v0.6.0

### [x] RELEASE-007 — Publish 0.6.1 from the post-0.6.0 follow-up

- **Priority:** P0
- **Owner:** release engineering / framework maintainers
- **Direction:** Cut `0.6.1` from `main` so the post-`v0.6.0` publication-record
  commit (`cf37f32c`) is a released revision, not an untagged follow-up.
- **Conclusion:** Stay on `main` (its tip is exactly that follow-up plus the
  patch prepare). Do not include open PR #166. Do not cut `release/0.6.x` for
  this patch.
- **Current state:** Published. Annotated tag `v0.6.1` selects `cd2c9229` on
  `main`. GitHub Release:
  https://github.com/NVIDIA-dev/literate-ai/releases/tag/v0.6.1
  Prepared-release identity
  `sha256:e57f5e4f0f7bb200d55e3e1af0b911ea87f7e29217458620e93a77a0e035e30b`.
- **Next action:** none — this item is closed.
- **Evidence:**
  - [x] Prepared commit `cd2c9229` changes only declared version, changelog,
        schema, documentation-authority, and driver-pin paths.
  - [x] GitHub run
        [`32897494275`](https://github.com/NVIDIA-dev/literate-ai/actions/runs/32897494275)
        on that SHA was green.
  - [x] `v0.6.1` tag and GitHub Release are verified.

### [x] RELEASE-008 — Publish 0.6.2 from the post-0.6.1 follow-up

- **Priority:** P0
- **Owner:** release engineering / framework maintainers
- **Direction:** Cut `0.6.2` from `main` so the post-`v0.6.1` queue close-out
  (`df382b70`) is a released revision.
- **Conclusion:** Stay on `main`. Do not include open PR #166.
- **Current state:** Published. Annotated tag `v0.6.2` selects `51cd5542` on
  `main`. GitHub Release:
  https://github.com/NVIDIA-dev/literate-ai/releases/tag/v0.6.2
  Prepared-release identity
  `sha256:87d7ad4422f251cd49dd2c2a44cd78067fc318216851bce78148cfcfea16dd8e`.
- **Next action:** none — this item is closed.
- **Evidence:**
  - [x] Prepared commit `51cd5542` changes only declared release-authority
        paths.
  - [x] GitHub run
        [`32901786262`](https://github.com/NVIDIA-dev/literate-ai/actions/runs/32901786262)
        on that SHA was green.
  - [x] `v0.6.2` tag and GitHub Release are verified.

### [x] RELEASE-010 — Publish 0.7.1 with the public-API test suite rewrite

- **Priority:** P0
- **Owner:** release engineering / framework maintainers /
      `docs/presentations/literate-ai-manager-overview/`
- **Direction:** Cut `0.7.1` on `release/0.7.x` so TEST-PUBLIC-001 and
      RELEASE-BRANCHING-002 ship. `v0.7.0` is already published at `afe52d09`; the
      release protocol forbids retagging. After that cut, regenerate the
      manager/engineering overview for 0.7.1 because 0.7.0 (a minor) skipped it.
      Going forward, full overview regeneration belongs on every major or minor
      (`0.8.0`, `0.9.0`, `1.0.0`, `1.1.0`, …). Patch cuts do not regenerate;
      they keep README citations on the last major/minor edition of those
      documents.
- **Conclusion:** The Git publication of `v0.7.1` already landed on
      `release/0.7.x` (`387da394`, `--target github`). Do not retag it. Encode
      the overview cadence in the release protocol and `release-project` skill,
      then catch up the document pair for the 0.7.1 edition: revalidate
      `source-notes.md`, rebuild the PPTX, realize the narrative locally without
      the Codex `documents` plugin, publish Slides in place, create the Google
      Doc, and cite that edition from root and package `README.md`. `--target
      local` worker fan-out remains on [RELEASE-009](#release-009-qualify-and-publish-070-with-full-gate-fan-out).
- **Depends on:** [TEST-PUBLIC-001](../../roadmap/active-work.md#x-test-public-001-prefer-public-api-tests-remove-private-trivial-and-call-sequence-coverage),
      [RELEASE-BRANCHING-002](../../roadmap/active-work.md#x-release-branching-002-refuse-a-versioned-release-cut-on-the-default-branch),
      and `origin/release/0.7.x` at `v0.7.1`.
- **Implementation:**
  - [x] Commit the suite rewrite, branching-002, and this queue item on `main`.
  - [x] Cherry-pick that commit onto `release/0.7.x`.
  - [x] POSIX host-bootstrap search path must use `HOME` from the discovered
        environment, not `Path.home()`, so the rewritten tests can run on
        Windows CI.
  - [x] Component-lock review tests must bind `BUILD_DIR`/`OBJ_DIR` to the temp
        project so they do not adopt the xdist worker's unmarked `OBJ_DIR` on
        Windows.
  - [x] On `release/0.7.x` only: `litai release plan --bump patch`, prepare,
        commit declared paths only. Re-pin the lifecycle-driver TCB in that
        same prepared tree because `src/literate_ai/version.py` is in the TCB.
  - [x] `litai release check PLAN --target github`, then publish with
        `--authorize-external-write`.
  - [x] Encode: major/minor cuts regenerate the terminal document pair; patch
        cuts keep README pointers on the last major/minor edition.
  - [x] Catch up the 0.7.1 overview: revalidate the factual ledger, rebuild the
        PPTX, realize the narrative `.docx`, publish Slides in place, create the
        Google Doc, cite the 0.7.1 edition from both README files. Do not retag
        `v0.7.1`.
- **Evidence:**
  - [x] Prepared commit `387da394` changes only declared release-authority paths.
  - [x] GitHub Actions run
        [`33111319027`](https://github.com/NVIDIA-dev/literate-ai/actions/runs/33111319027)
        on `387da394` was green.
  - [x] `v0.7.1` tag and GitHub Release are verified:
        https://github.com/NVIDIA-dev/literate-ai/releases/tag/v0.7.1
  - [x] Catalog and template `release-project` skills remain byte-identical and
        name the major/minor vs patch overview cadence.
  - [x] `scripts/verify_document_pair.py` accepts the rebuilt pair; QA ledger
        records visual inspection of the contact sheet and changed slides.
  - [x] Published Slides resource `1V9mt1JpEst_2ucC0eJIIw7dff64MrtFRfut8MSiukeE`
        is updated in place and read back (Drive version 118; 26 slides / 26 notes
        on export-back via the authenticated presentation export URL).
  - [x] A Google Doc URL for the narrative member is recorded as the 0.7.1
        edition in root and package `README.md`:
        https://docs.google.com/document/d/1fMxy0NTT54MV4T9AwmA8F0VahNet93Xhp0d0pszI6GA/edit

### [x] RELEASE-011 — Publish 0.7.2 then advance main to 0.8.0 Unreleased

- **Priority:** P0
- **Owner:** release engineering / framework maintainers
- **Direction:** Cut patch `0.7.2` on the existing `release/0.7.x` line so
  FLAVOR-008 ships. Do not regenerate the manager overview (patch cadence; keep
  the 0.7.1 edition citations). After Git/GitHub publication, advance `main` to
  `0.8.0` Unreleased with `litai release advance-default-branch --bump minor`.
  Do not retag `v0.7.0` or `v0.7.1`.
- **Conclusion:** Plan from `release/0.7.x`, not `main` (`release/0.7.x` already
  exists). Backport only product commits that are not already on the line:
  `95fb895c` (0.7.1 overview catch-up and regen cadence, so the 0.7.2 tree cites
  that edition) and `ce4613d8` (FLAVOR-008). Do not backport `786293af` or
  `18b98dd2` (those advanced `main` to 0.7.2 Unreleased after 0.7.1). Then
  `plan --bump patch`, prepare, commit declared paths plus TCB/docs restamp,
  `check --target github`, publish. `--target local` fan-out remains on
  RELEASE-009. Publish's automatic default-branch patch step moved `main` to
  `0.7.3`; the explicit `--bump minor` then replaced that with `0.8.0`
  Unreleased. Stranded 0.8.0 product scope is
  [RELEASE-012](../../roadmap/active-work.md#release-012-080-unreleased-product-and-protocol-scope), not
  empty.
- **Depends on:** [FLAVOR-008](../../roadmap/active-work.md#x-flavor-008-fail-closed-on-duplicate-packaging-and-document-flavor-aliases)
  on `main`; `origin/release/0.7.x` at `v0.7.1`.
- **Implementation:**
  - [x] Cherry-pick `95fb895c` then `ce4613d8` onto `release/0.7.x` (manual
        after `litai release backport` aborted on conflicts). Do not backport
        `786293af` or `18b98dd2`.
  - [x] On `release/0.7.x` only: `litai release plan --bump patch`, prepare,
        commit declared paths only. Re-pin the lifecycle-driver TCB because
        `src/literate_ai/version.py` is in the TCB.
  - [x] `litai release check PLAN --target github`, then publish with
        `--authorize-external-write`.
  - [x] On `main`: `litai release advance-default-branch --branch main --bump minor`,
        review, commit, push. Do not merge `release/0.7.x` into `main`.
- **Evidence:**
  - [x] Prepared commit `be642f4a` on `release/0.7.x` changes only declared
        release-authority paths (plus required TCB/docs restamp).
  - [x] GitHub Actions run
        [`33130230761`](https://github.com/NVIDIA-dev/literate-ai/actions/runs/33130230761)
        on `be642f4a` was green.
  - [x] `v0.7.2` tag selects `be642f4a`. GitHub Release:
        https://github.com/NVIDIA-dev/literate-ai/releases/tag/v0.7.2
  - [x] `main` is `0.8.0` Unreleased; README citations still name the 0.7.1
        overview edition until the 0.8.0 regen.

### [x] DOC-DECK-003 — Read and improve layout and workflow pictures on the published overview

- **Priority:** P0
- **Release target:** 0.8.0 edition published (Drive version 134); repeat on
      later major/minor overview regenerations
- **Owner:** `docs/presentations/literate-ai-manager-overview/SKILL.md`,
      `skills/agent/author-presentations-and-documents/SKILL.md`
- **Direction:** Read and improve the published overview so text boxes do not
      overlap and images are used where possible to improve workflow
      visualization — pictures not text when possible. The live Slides resource
      is `1V9mt1JpEst_2ucC0eJIIw7dff64MrtFRfut8MSiukeE`.
- **Conclusion:** First pass was a layout revision of the published 0.7.1
      edition (Drive version 124). The 0.8.0 major/minor regeneration repeated
      that visual pass (Drive version 129), then a cover and thesis-cell overflow
      fix (Drive version 134).
      Geometry-escape cannot see painted overflow. Native-shape diagrams still
      count as pictures; the specification excerpt stays readable authority.
      Do not invent claims or ROI.
- **Depends on:** [RELEASE-012](../../roadmap/active-work.md#release-012-080-unreleased-product-and-protocol-scope)
      document-pair regeneration for the 0.8.0 edition (complete for this pass).
- **Implementation:**
  - [x] Fix the shared title/footer geometry so two-line titles, section tags,
        subtitles, and footers cannot collide, including after Arial substitution.
  - [x] Read every rendered slide; fix remaining overlapping, clipped, or
        colliding text boxes.
  - [x] On workflow slides, prefer pictures/diagrams over paragraphs; keep the
        slide 7 specification excerpt as readable authority.
  - [x] Encode the post-generation read-and-improve pass in
        `docs/presentations/literate-ai-manager-overview/SKILL.md`.
  - [x] Rebuild, inspect, publish the Slides resource in place, and record the
        pass in `qa-ledger.md`.
- **Evidence:**
  - [x] Contact sheet and full-size inspection show no overlapping text boxes.
  - [x] Workflow slides are picture-led; remaining text is labels or a short
        caption, not the workflow itself.
  - [x] QA ledger records this pass; the published Slides resource is updated
        in place (Drive version 134, 0.8.0 edition).

### [x] DOC-PAIR-001 — Encode painted-overflow layout into document-pair authority

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **Owner:** `skills/agent/author-presentations-and-documents/SKILL.md`,
      `skills/specification-to-source/document-pair/SKILL.md`,
      `components/document-pair/`, `flavors/doc-google-workspace/document-pair.md`
- **Direction:** The overview layout pass that kept cover title and thesis-cell
      copy inside their frames, and that made workflows picture-led, must become
      process for every Literate-AI release and every derived document-pair —
      not a package-local memory. Geometry-escape is not an overflow gate.
- **Conclusion:** Lift the working rules into the catalog authoring skill, the
      document-pair interface/acceptance/oracle, both documentation-ecosystem
      Flavor bindings, and the init-template copies. Google-specific wrap and
      paragraph rules belong in the Google Workspace binding and the authoring
      skill. Do not rewrite historical QA entries that called geometry-escape
      the applicable gate.
- **Depends on:** [DOC-DECK-003](../../roadmap/active-work.md#x-doc-deck-003-read-and-improve-layout-and-workflow-pictures-on-the-published-overview)
- **Implementation:**
  - [x] Fix the overview SKILL contradiction that called geometry-escape the
        python-pptx equivalent of an overflow test.
  - [x] Add non-overlapping text-bearing frames to the document-pair contract,
        acceptance, oracle, and both Flavor bindings.
  - [x] Record Google Arial substitution, real paragraphs in the shape text
        frame, picture-led workflows, and published-copy read-back in the
        authoring skill and Google Workspace binding.
  - [x] Keep catalog and init-template copies aligned.
- **Evidence:**
  - [x] Document-pair oracle rejects overlapping text-bearing frames and still
        accepts the unmutated fixture (`tests.critical.test_document_pair_oracle`).
  - [x] Overview SKILL no longer names geometry-escape as the overflow gate.

### [x] RELEASE-014 — Pin each changelog section to that release's README.md

- **Priority:** P0
- **Owner:** `CHANGELOG.md`, `src/literate_ai/project_releases.py`,
      `docs/architecture/project-releases.md`
- **Direction:** Put a link to every release's `README.md` into its changelog
      section.
- **Conclusion:** Each published `## {version}` section (not Unreleased) opens
      with a GitHub blob link to `README.md` at that version's git tag
      (`https://github.com/NVIDIA-dev/literate-ai/blob/v{version}/README.md`).
      The URL must not live in the heading: `prepare` / heading-count /
      release-note extraction match `^## {version}(?:\s|$)`. `prepare` inserts
      the same first line when the policy names a GitHub provider, so later
      cuts keep the convention. Do not invent missing historical headings
      (`0.6.4`, `0.6.3`, `0.5.1`, `0.5.0`, `0.1.1a1`). Relative `README.md`
      links are wrong for historical sections.
- **Depends on:** none
- **Implementation:**
  - [x] Insert the tag-pinned README link under every existing published
        changelog heading.
  - [x] `prepare_release` writes that link for GitHub-provider projects.
  - [x] Record the convention in the project-release protocol.
- **Evidence:**
  - [x] Every published changelog heading is followed by its tag-pinned
        `README.md` link; headings remain unlinked.
  - [x] Focused `test_project_releases` coverage for prepare insertion and
        GitHub notes extraction.

### [x] FORWARD-PORT-001 — Reconcile shipped `0.5` fixes missing from `main`

- **Priority:** P1
- **Owner:** `main` (trunk), audited against `origin/release/0.5.x`
- **Direction:** A content audit on 2026-08-21 compared `main` against
  `release/0.5.x` and found `main` missing work that shipped in `0.5.0`/`0.5.1`. This
  is the concrete cost of the `planning/0.5.0-scope` divergence
  (`RELEASE-BRANCHING-001`): fixes landed on the release lineage and were never fixed
  forward, which the model explicitly forbids ("`main` must never be missing a fix that
  only exists on a release branch"). Commit-identity comparison is useless here —
  `git cherry` reports 62 of 63 commits as having no equivalent — and commit-message
  issue references are also unreliable, since several fixes did reach `main` under
  different wording. Every item below was verified by probing whether `main`'s tree
  actually contains the code the fix introduced.
- **Confirmed absent from `main`** (probe hit rate 0/N against `main`'s tree):
  - `#68` — inherited-session HMAC protocol hardening and its untested branch
    (`5c4242f5`); `adapters/models/inherited_session.py`.
  - `#80` — `LocalObservationSandbox` scratch-cleanup retry past a live-handle race
    (`0b172115`); `source_to_specification/sandbox.py`.
  - ~~`#81` — SSH `Popen` platform process-group options (`713f120d`)~~ **DONE
    2026-08-21** (`2beb7447`, `eaa7abdf`). Porting it exposed an error in this audit:
    `#70` was recorded below as "already on `main`" on the strength of a probe that
    matched elsewhere in the tree, but its `ssh_transport.py` half had never landed.
    `713f120d` only *hoists* `process_group_options()` into a local for testability —
    the substantive `start_new_session=True` → `process_group_options()` swap is in
    `5fe8f7d3` (`#70`), so `#81` alone would have been a no-op cherry-pick onto code
    that never had the fix. Both were ported, which also closed two further defects
    bundled in `#70` that `main` still carried: `terminate_process_tree(process,
    environment={})` shadowed the environment so `windows_taskkill_executable` returned
    `None` and taskkill never ran on Windows (only the direct child died, grandchildren
    leaked), and the following `process.wait()` was unbounded, so a grandchild holding
    the inherited stdout/stderr pipe could hang the runner forever. `ssh_transport.py`
    and its tests are now byte-identical to the release line.
  - `#110` — packaging-only provider edges wrongly requiring a build runtime binding
    (`ab6fc565`). See `PACKAGE-EDGE-001`, whose "not implemented" text this audit
    corrected.
  - `#112` — verify every promoted Component's lock during project-target promotion
    (`e730aa13`).
  - `#116`/`#118` — pin literal constant/lookup-table values as assets during spec
    derive (`33eec233`), including its two schema changes.
  - `#117` — bounded retry for spec-derive insufficient-evidence shortfalls
    (`0f4c1a3b`).
  - `#137` — retire superseded source-cache entries on forced-regeneration accepts
    (`2a242ce7`).
  - LOW-layer Design-by-Contract skill paragraphs with validated examples
    (`93545f08`) — `go`/`python`/`rust` `specification-to-source` skills, each with a
    skill version bump, plus `docs/history/roadmap/0.5.0-design-by-contract-examples/`.
  - Capability entrypoint invocation contract clarification (`97789d94`) —
    `invoice-service` and `money-calculation` at `1.0.1` on the release line, `1.0.0`
    on `main`.
- **Corrected whole-file audit (2026-08-23):** `#71`, `#72`, `#74`, `#77`, and `#79`
  were incorrectly classified as present. Current `main` still lacks, respectively,
  the bounded dispatcher post-terminate wait, Windows Job Object ownership, validated
  standalone remote `taskkill`, synchronized/five-second lifecycle pipe drain, and the
  shared tree-killing replacement for bare `subprocess.run(timeout=...)` call sites.
  Add them to the required forward-port set in dependency order `#72`, `#71`, `#74`,
  `#77`, `#79`, then `#80`.
- **Verified already on `main`** (reached it by a different commit; no action):
  `#73`, `#76`, `#78`, `#125`, `#133`, `#138`, `#139`, the release-notes
  changelog-section fix, and the release-check test-receipt scope exemption. The
  DMN/SCXML design spikes exist on `main` under
  `docs/roadmap/0.6.0-*` names. **`#70` was wrongly listed here** and has since been
  ported (see `#81` above) — a caution that a single matching probe line proves
  nothing when a commit spans several files; only a per-file check is sound.
- **Deliberately not forward-ported:** release mechanics (prepare/receipt/re-pin
  commits), branch-local ruff-version reformatting, the deck rebuild, and
  `docs/roadmap/0.5.0-scope.md` (superseded historical scope).
- **Next action:** Complete on the integration branch. Preserve the per-file audit rule
  for future release lines; do not merge `release/0.5.x` wholesale.
- **Evidence:**
  - [x] `#81` and `#70` present on `main` with their regressions (`2beb7447`,
        `eaa7abdf`); `ssh_transport.py` byte-identical to `release/0.5.x`.
  - [x] Every corrected missing item (`#68`, `#71`, `#72`, `#74`, `#77`, `#79`, `#80`,
        `#110`, `#112`, `#116/#118`, `#117`, `#137`, LOW-DBC, and capability
        entrypoint clarification) is present with its focused regressions.
  - [x] A clean Python gate passes all 2,622 tests with 27 platform skips; lint and
        formatting pass. Release-only prepare/receipt history and superseded 0.5
        planning remain deliberately excluded.

### [x] RELEASE-BRANCHING-001 — Adopt trunk-based development with cut-time release branches

- **Priority:** P2
- **Owner:** release planning
- **Direction:** During the 0.5.0 cycle, a long-lived `planning/0.5.0-scope` branch
  (created to isolate work from the in-flight 0.4.1 release) kept being used after
  0.4.1 shipped, while `main` moved independently. By the time this was noticed the
  two branches had diverged by 15 and 19 commits respectively, requiring a real merge
  with real conflicts (`CHANGELOG.md`, the doc-authority marker, `active-work.md`, the
  TCB pin) — the textbook failure mode of a long-lived integration branch (GitFlow's
  `develop` anti-pattern).
- **Conclusion:** See
  [`docs/history/roadmap/release-branching-model.md`](release-branching-model.md) for the full
  model: `main` is the single trunk, all work lands there directly and continuously
  (matching this repository's existing "commit directly to main" convention); a
  release branch (`release/0.N.x`) is cut from `main`'s exact tip only at
  `litai release prepare` time, not before; backports are fix-forward-then-cherry-pick
  (land on `main` first, cherry-pick to the release branch), never fix-only-on-the-branch.
  Also identified a real gap in `litai`'s own release tooling: no first-class support
  for cutting a release branch as part of `release prepare`, or for tracking which
  commits still need backporting to an active release branch.
- **Update (0.5.1 patch cycle):** the backport half of that gap is now implemented —
  `litai release backport COMMIT... --to BRANCH [--from REF]` cherry-picks
  already-landed commits onto a release branch (creating it from `--from`, e.g. a
  tag, if it doesn't exist yet) in an isolated worktree, never touching the caller's
  checkout and never pushing; `litai release backport-status BRANCH [--against REF]`
  lists trunk commits not yet applied, using `git cherry`'s patch-id equivalence so an
  already-backported fix (a different SHA after `-x` cherry-pick) correctly drops off
  the list. Used to cut `release/0.5.1` from the `v0.5.0` tag and backport its fixes.
  Still not implemented: first-class branch cutting as part of `release prepare`
  itself (today's cut is a plain `git branch ... <tag>`, done outside `litai`).
- **Update (2026-08-21):** practice had drifted from this model's own `release/0.N.x`
  naming to a branch per *patch* (`release/0.5.0`/`0.5.1`/`0.5.2`), and
  `skills/agent/release-project/SKILL.md` — what an agent actually reads at release
  time — had codified the deviation. Corrected in `f757c0db`: the skill now says
  `release/<major>.<minor>.x` and states why, the same stale convention was fixed in
  `project_releases.py`'s docstrings and the `advance-default-branch` CLI help, and
  `release/0.5.x` was consolidated at the `0.5.2` tip (the three per-patch branches were
  already a strict ancestor chain, so no history rewriting was needed). A per-patch
  branch is not merely cosmetic: it resets this model's drift signal — "a backport that
  no longer cherry-picks cleanly means the line has drifted" only works when drift
  accumulates against one persistent branch. `FORWARD-PORT-001` records the ten shipped
  fixes that divergence cost `main`.
- **Next action:** Done. [RELEASE-BRANCHING-002](../../roadmap/active-work.md#x-release-branching-002-refuse-a-versioned-release-cut-on-the-default-branch)
  owns and completed cutting the line at `prepare`. Do not retag `v0.7.0`.
- **Evidence:**
  - [x] `docs/history/roadmap/release-branching-model.md` committed with the full model.
  - [x] `litai release backport` / `litai release backport-status` implemented,
    tested (`tests/e2e/test_project_releases.py::ReleaseBackportTests`), documented
    (`docs/user/configuration-and-cli.md`).

### [x] SPEC-HIERARCHY-DMN-001 — DMN specification_provider design and implementation

- **Priority:** P2
- **Release target:** 0.6.0 — the design spike is complete and not committed 0.5.0
  scope; a narrower follow-on prototype (parse one real `.dmn` file end to end,
  pick/justify a DMN-XML parsing approach) plus the actual provider implementation
  are pushed to 0.6.0 rather than opened as in-progress work this cycle.
- **Re-scoped:** 0.9.0 (2026-09-01) for any remaining work; the historical target above records where the item originated / partially shipped.
- **Owner:** specification-provider seam / `spec derive`, `spec accept`, `litai lock`,
  `litai generate`
- **Direction:** `0.5.0-specification-hierarchy.md`'s MEDIUM(b) entry (issue #119)
  calls for a design spike (not code) answering how a new DMN (OMG Decision Model and
  Notation) `specification_provider` would plug into the existing
  `openspec`/`literate-markdown` seam, scoped to rule/decision-table logic OpenSpec's
  WHEN/THEN expresses poorly.
- **Conclusion:** See
  [`docs/history/roadmap/0.6.0-dmn-provider-design.md`](0.6.0-dmn-provider-design.md) for the
  full spike, grounded in direct inspection of
  `src/literate_ai/adapters/specifications/{openspec,literate_markdown}.py`,
  `contracts/specifications.py`, `component_lock_planning.py`,
  `legacy_generation_catalog.py`, `generation_preparation.py`,
  `source_to_specification/{literal_data,review}.py`, and `self_hosting.py`. Headline
  findings: `specification_provider` dispatch is hardcoded two-armed `if`/`elif`/`raise`
  at exactly two call sites (`component_lock_planning.py`,
  `legacy_generation_catalog.py`), not a plugin registry — additive but not zero-touch;
  both existing providers already terminate in the identical WHEN/THEN-shaped
  `SpecificationSet`/`SpecificationScenario` contract (`literate-markdown` reuses
  `OpenSpecProvider` internally), so DMN would be the first provider whose native
  content does not decompose into given/when/then at all; content-hash/generation-key
  binding is already fully provider-neutral and needs no change; `litai generate`
  already consumes specification content as opaque context bytes regardless of
  provider. Given those, the spike recommends: author real OMG `.dmn` XML through the
  existing `specification_roots` mechanism (no new discovery path); treat
  "acceptance" as DMN's own structural hit-policy/input-output-coverage/
  type-conformance validation at lock-planning time (a genuinely different oracle
  shape than WHEN/THEN scenario pass/fail); no DMN/FEEL execution engine inside
  litai — treat the table as declarative content-pinned structured data closer to
  `assets:` (`#116`/`#118`) than to a live spec engine; and the migration pipeline
  (`spec derive`/`accept`/`coverage`/`review`) is a different, largely orthogonal
  subsystem — a DMN table should be hand-authored or tool-exported, never derived by
  a model from legacy source.
- **Next action (2026-08-19, done):** The follow-on prototype landed in
  `1427618adece9d04a5891e502fb78c9e25ae4e2c` under
  [`docs/roadmap/0.6.0-dmn-prototype/`](../../roadmap/0.6.0-dmn-prototype/risk-category.dmn):
  a real hand-authored DMN 1.3 `.dmn` file plus a stdlib-only `xml.etree.ElementTree`
  parser/checker proves the UNIQUE-hit-policy overlap check passes a clean table and
  fails closed on a genuine overlap. `pyDMNrules` (the one DMN-aware PyPI package)
  was evaluated and rejected as a full FEEL-execution/Excel-authoring engine, wrong
  shape for structural-only validation — hand-rolled stdlib parsing is the recommended
  approach. Findings folded back into the design doc's own "Follow-on prototype
  results" section. What remains before code is now ordinary implementation work
  (the registry refactor and the actual `DmnProvider`), not a further open design
  question.
- **Current implementation action (2026-08-23, in progress):** Land the smallest
  honest 0.6.0 provider seam: one shared built-in registry for lock planning and
  legacy generation, a bounded stdlib DMN 1.3 loader restricted to UNIQUE tables
  with numeric closed intervals and `-`, synthetic `SpecificationSet` projection,
  exact artifact drift checks, focused integration tests, and user documentation.
  Preserve the self-hosting OpenSpec-only restriction and do not claim release
  qualification from this focused implementation evidence.
- **Evidence:**
  - [x] `docs/history/roadmap/0.6.0-dmn-provider-design.md` committed with the full spike
        and the follow-on prototype results appended.
  - [x] Narrow production `DmnProvider` validates bounded exact DMN 1.3/1.5 UNIQUE
        numeric decision tables and is registered for lock and generation dispatch.
  - [x] Shared registry parity and valid DMN lock/generation loading are covered by
        focused tests.
  - [x] Unsupported DMN syntax, structural overlap, type/arity errors, and artifact
        drift fail closed in focused tests.
  - [x] Focused tests and lint/format pass (`39` focused tests, one platform skip;
        Ruff check and format check clean). Full 0.6.0 release evidence remains owned
        by `RELEASE-006`; the broader `make python-check` run reached `879` tests and
        exposed then-fixed test-fixture path handling, but was not rerun as release
        evidence.
  - [x] Reconciled `origin/feat/dmn-scxml-specification-providers` as `98283fd5`; the
        clean Python gate passes 2,622 tests with 27 platform skips.

### [x] SPEC-HIERARCHY-SCXML-001 — Design and implement an SCXML specification_provider

- **Priority:** P2
- **Release target:** 0.6.0 — the design spike is complete and not committed 0.5.0
  scope; the declared-trace sidecar format's own design pass (prototyped against a
  real `<parallel>`/`<history>` sample) plus the actual provider implementation are
  pushed to 0.6.0 rather than opened as in-progress work this cycle.
- **Owner:** specification-provider seam
- **Direction:** `docs/roadmap/0.5.0-specification-hierarchy.md`'s MEDIUM(c) item
  (issue #119) asks for a design spike (not code) for SCXML (the W3C State Chart XML
  standard) as a new `specification_provider`, scoped to state-machine/protocol/
  workflow logic — the common case the issue expects most Components with
  state-machine-shaped behavior to need. Open questions: authoring/discovery shape,
  acceptance-oracle shape (a different oracle from both WHEN/THEN and DMN), minimum
  viable adapter (parser vs. interpreter), generation-key binding and `spec
  coverage`/`spec review` treatment, and `litai lock`/`litai generate`
  provider-neutrality — plus explicitly confirming the design does not accidentally
  need TLA+/PlusCal's harder concurrent-algorithm verification problem to handle
  ordinary sequential state machines.
- **Conclusion:** See
  [`docs/history/roadmap/0.6.0-scxml-provider-design.md`](0.6.0-scxml-provider-design.md) for
  the full spike, grounded in direct audit of the existing `specification_provider`
  seam (`OpenSpecProvider`/`LiterateMarkdownProvider`, `SpecificationSet`'s
  mandatory-`when`/`then` contract, the closed if/elif provider dispatch in
  `component_lock_planning.py`/`legacy_generation_catalog.py`, and the raw-bytes
  generation-key binding). Summary: authoring is a single `.scxml` file per Component
  via a new `SCXMLProvider` mirroring `OpenSpecProvider`'s bounded-snapshot shape; the
  acceptance oracle is two complementary checks — static structural soundness
  (reachability/transition-target resolution, checkable without an interpreter) and
  declared-trace conformance (a genuinely novel sidecar format litai would need to
  define, since SCXML has no native one); the minimum viable adapter is a parser and
  static analyzer, not an interpreter, with execution left to generated code; and
  generation-key binding needs no change. Today's `litai spec coverage`/`litai spec
  review` commands belong to a different, WHEN/THEN-shaped reverse
  (derive-from-source) pipeline and do not apply to a hand-authored SCXML document —
  SCXML needs its own review verb rather than reusing those commands. `litai
  lock`/`litai generate` provider-neutrality needs one small, mechanical fix (replace
  two closed if/elif dispatch sites with a provider-kind registry) shared with
  MEDIUM(b)/DMN, answered once. TLA+/PlusCal is confirmed unnecessary: every oracle
  proposed is static-graph analysis or delegated to generated code, never
  interleaving exploration or model checking.
- **Next action (2026-08-19, done):** The trace-sidecar design pass landed in
  `1427618adece9d04a5891e502fb78c9e25ae4e2c` under
  [`docs/roadmap/0.6.0-scxml-prototype/`](../../roadmap/0.6.0-scxml-prototype/media_player.scxml):
  a non-trivial hand-authored SCXML chart with a `<parallel>` region and a
  `<history>` pseudostate, a structural reachability/soundness checker, and a
  separate `.trace.json` sidecar format with a stateful conformance replayer.
  The prototype deliberately proved the two oracles cannot share one
  implementation — trace conformance needs a real history-tracking stepper,
  confirmed by demonstrating a history-blind variant fails exactly the re-entry
  step a correct one passes. The sidecar format is now concretely decided
  (separate `spec/<name>.trace.json` file) and validated end to end.
  **Update (2026-08-20):** that prototype decided *where* the sidecar lives
  but not a reusable *schema* for it; that gap is now closed by
  [`docs/history/roadmap/spikes/scxml-trace-prototype/RESULTS.md`](spikes/scxml-trace-prototype/RESULTS.md),
  a small JSON schema (`traces[].steps[]` with
  `event`/`expect_active`/`expect_regions`/`via_history`/`auto`) validated
  against a second, independently-authored `.scxml` sample and a standalone
  static structural validator that catches four distinct classes of
  malformed sidecar. What remains before code is porting this prototype's
  logic into the real `SCXMLProvider` shape and the shared registry refactor
  (also needed by DMN), not a further open design question.
- **Evidence:**
  - [x] `docs/history/roadmap/0.6.0-scxml-provider-design.md` committed with the full
        breakdown and the trace-sidecar prototype findings appended.
  - [x] Narrow production `ScxmlProvider` validates bounded exact SCXML 1.0 graphs
        and explicit trace sidecars, including parallel and exact history replay,
        and is registered for lock and generation dispatch.
  - [x] `litai spec scxml-review` exposes read-only structural and trace validation;
        focused provider/CLI/lock coverage passes 43 tests with one platform skip, and
        the clean Python gate passes 2,622 tests with 27 platform skips.

### [x] SPEC-HIERARCHY-SAMPLES-001 — Portfolio samples for every non-OpenSpec specification type

- **Status:** complete (2026-08-28: DMN + SCXML + pinned-assets samples admitted)

- **Priority:** P1
- **GitHub issue:** [#119](https://github.com/NVIDIA-dev/literate-ai/issues/119)
- **Owner:** `samples/`, `tests/conformance/support/sample_runner.py`,
      `tests/conformance/support/runtime_oracles.py`
- **Direction:** #119's three-layer hierarchy is implemented as providers (DMN,
      SCXML) and as `assets:` for literal tables, but the sample portfolio still
      only exercises default `literate-markdown`. Validation needs genuine
      Components that *use* each new type, not roadmap prototypes.
- **Conclusion:** Add inheritable-false portable-application samples whose
      `specification_provider` is `dmn` and `scxml`, with pinned `assets:` on the
      DMN sample for MEDIUM-layer literal data. HIGH-layer literate-markdown
      remains `hello-component`. LOW-layer Design-by-Contract stays a
      language-skill convention, not a fourth `specification_provider`. Do not
      invent TLA+/PlusCal; SCXML covers everyday state machines. Sample catalog
      admission must allow `.dmn` and `.scxml` as specification bytes. `_load_sample`
      must dispatch through the shared provider registry. Live source generation
      of the new samples still requires explicit model-egress acknowledgement.
- **Depends on:** [SPEC-HIERARCHY-DMN-001](../../roadmap/active-work.md#x-spec-hierarchy-dmn-001-dmn-specification_provider-design-and-implementation),
      [SPEC-HIERARCHY-SCXML-001](../../roadmap/active-work.md#x-spec-hierarchy-scxml-001-design-and-implement-an-scxml-specification_provider)
- **Implementation:**
  - [x] `samples/loan-risk-gate` — UNIQUE DMN table plus pinned JSON score bands.
  - [x] `samples/playback-controller` — SCXML 1.0 chart plus trace sidecar.
  - [x] Harness, runtime oracles, and provider-dispatch in `_load_markdown_component`.
  - [x] Document the hierarchy coverage in `samples/README.md` and
        `docs/user/specifications.md`.
- **Evidence:**
  - [x] `_load_sample` locks and loads both new samples through their providers.
  - [x] Runtime-oracle catalog includes both sample IDs.
  - [x] Sample-catalog suffix admission includes `.dmn` and `.scxml`.

### [x] ACCEPTANCE-002 — Verify persistent HTTP services independently

- **Priority:** P0
- **Owner:** Standard lifecycle independent acceptance
- **Direction:** Persistent services require verifier-owned startup, readiness, bounded HTTP/SSE checks, and shutdown rather than single-shot JSON invocation.
- **Conclusion:** Add a strict `persistent-service-acceptance@1` contract while preserving portable-application acceptance and receipt boundaries.
- **Implementation:**
  - [x] Load verifier-owned service contracts by locked Component name.
  - [x] Defer packaged service execution to independent acceptance.
  - [x] Bound process lifetime, HTTP responses, SSE assertions, and process output.
- **Evidence:**
  - [x] Focused acceptance, lifecycle, rebuild, and receipt tests pass.

### [x] SBOM-005 — Reconcile managed authority with third-party source inventory

- **Priority:** P0
- **Owner:** coding-CLI source-SBOM reconciliation
- **Direction:** Legitimate third-party package components must not prevent canonical repair of framework-managed root, Component, Flavor, skill, classification, and edge authority.
- **Conclusion:** Merge the canonical managed projection into model-authored third-party inventory and reject reserved-reference conflicts or managed reparenting.
- **Implementation:**
  - [x] Preserve valid third-party components and edges.
  - [x] Canonicalize every framework-managed node and edge.
  - [x] Reject duplicates, dangling references, reserved properties, and conflicting authority claims.
- **Evidence:**
  - [x] Coding-CLI generation coverage passes with Cargo-package and conflict fixtures.

### [x] SBOM-006 — Canonicalize model-authored source composition authority

- **Priority:** P0
- **Owner:** coding-CLI source-SBOM reconciliation
- **Direction:** A derived project's dependency-free Python/Make Component repeatedly
  reached the build phase with a model-authored CycloneDX `compositions` shape that the
  non-Bazel lifecycle correctly rejects, even though the framework already owns and
  repairs the rest of the managed source-BOM projection.
- **Conclusion:** Composition completeness is framework lifecycle authority, not model
  discretion. During SBOM reconciliation, retain only the exact sanctioned
  `incomplete_third_party_only` declaration when the generated tree contains actual
  Bzlmod dependency intent; otherwise write the canonical complete root composition
  already produced by the managed projection.
- **Implementation:**
  - [x] Canonicalize `compositions` alongside the managed root, inventory, properties,
        and dependency edges.
  - [x] Preserve the exact deferred-Bzlmod form for later resolver validation.
- **Evidence:**
  - [x] Four focused coding-CLI SBOM reconciliation tests pass for malformed model
        composition, deferred Bzlmod, retained third-party inventory, and unsafe
        authority rejection.

### [x] CARGO-001 — Add locked Cargo service builds to Standard

- **Priority:** P0
- **Owner:** Rust ecosystem authority, Standard command projection, and dependency evidence
- **Direction:** Generated Rust services need Cargo registry dependencies without trusting model-authored lockfiles or writing build output into admitted source.
- **Conclusion:** Add a composable Cargo Flavor, exact Cargo toolchain binding, post-authorization external lock derivation, `--locked` metadata/build execution, retained dependency evidence, and resolved-SBOM reconciliation.
- **Implementation:**
  - [x] Add Cargo command profile, Flavor, ecosystem/build skills, and initialization wiring.
  - [x] Derive and freeze Cargo.lock in an external build projection after authorization.
  - [x] Retain Cargo metadata/lock evidence and reject path, Git, workspace, build, dev, and target-specific dependencies.
- **Evidence:**
  - [x] Focused Cargo lifecycle, dependency, projection, and toolchain tests pass.

### [x] MAC-CONTRACT-001 — Project MAC runner contracts from resolved CycloneDX evidence

- **Owner:** resolved dependency evidence and inheritable agent skills
- **Direction:** MAC-compatible projects need a `.mac/project.yaml` repository contract
  so MAC runners can compose their OpenShell policy without learning Literate AI's
  internal Component, Flavor, and skill formats.
- **Conclusion:** Add an inheritable skill with a deterministic projector that consumes
  the already-validated post-build CycloneDX BOM and emits
  `mac.repository_contract.v1`. The projector is a downstream view of the existing
  dependency graph, never a scanner or second dependency resolver. Component, selected
  Flavor, and selected skill authority must reach the CycloneDX lifecycle before this
  projection; missing or ambiguous prerequisite evidence fails closed. Literate AI owns
  its portable bootstrap/test commands, while MAC remains the authority for contract
  validation, runner dispatch, and OpenShell policy composition.
- **Depends on:** complete resolved CycloneDX 1.7 evidence and canonical `litai`
  bootstrap/test entry points
- **Implementation:**
  - [x] Add the provider-neutral `write-mac-project-contract` skill to this framework
        and initialized projects, with the exact MAC schema and ownership boundary.
  - [x] Add a deterministic, canonical projector from one validated resolved BOM to
        `.mac/project.yaml`, mapping host/platform and executable prerequisite evidence
        without inspecting manifests, source trees, or PATH independently.
  - [x] Bind the output to the exact source BOM, resolved BOM, and resolved graph
        identities so stale contracts are detectable and reproducible.
  - [x] Document when the projection runs, how an operator overrides portable project
        metadata, and how MAC consumes the result without making MAC a mandatory
        Literate AI dependency.
- **Evidence:**
  - [x] Focused tests prove deterministic output, supported platform mapping, exact
        dependency-to-command projection, stale/incomplete BOM rejection, and no
        parallel analysis path.
  - [x] The generated YAML passes MAC's current repository-contract normalization
        contract, and a newly initialized project contains and can execute the skill.
  - [x] SkillEvaluator and the full skill/conformance gates pass. The fail-fast Python
        gate found and repaired two stale authority fixtures plus the expected derived
        project identities, then completed its entire checkpointed suite; the clean
        release rerun starts from test one after this checkpoint.

### [x] SAMPLE-LAYOUT-001 — Flatten samples and make parent sample inheritance explicit

- **Owner:** sample catalog layout and repository-lineage catalog export
- **Direction:** Two service-stack dependency Components live under the accidental path
  `samples/components/*`, unlike every other sample at `samples/*`. Derived projects
  also currently inherit every parent sample because all local `component_roots` are
  treated as repository exports.
- **Conclusion:** Move the two Components directly beneath `samples/` and remove every
  special nested lookup. Components inherit by default; add a per-Component
  `inheritable` policy whose omitted value is `true`, and explicitly opt sample
  Components out with `inheritable: false`, except for the portable hello starter that
  every child needs for its initial end-to-end smoke test. Samples remain discoverable
  in the parent and may be copied explicitly through catalog tooling. Do not preserve
  the nested path.
- **Depends on:** repository catalog composition and the current central sample harness
- **Implementation:**
  - [x] Move invoice-service and money-calculation to flat sample paths and update all
        sample, presentation-source, and conformance references.
  - [x] Add a strict per-Component inheritance policy, default it to true, and apply it
        during repository catalog composition without changing local build authority.
  - [x] Mark this repository's wider sample portfolio non-inheritable while retaining
        the default for ordinary Components and the portable hello starter.
- **Evidence:**
  - [x] No `samples/components` path or compatibility lookup remains; all sample and
        service-stack conformance tests pass from the flat catalog.
  - [x] Repository-lineage tests prove local samples remain valid but are absent from a
        child's automatic imports, while hello and ordinary Components still inherit.

### [x] CI-NATIVE-001 — Keep ambient native toolchains out of non-live gates

- **Owner:** repository conformance ladder and native-toolchain qualification
- **Direction:** A hosted macOS runner happened to expose Bazel, causing the ordinary
  non-live Python gate to execute a network-resolving native conformance test. Its
  transitive Buildozer fetch then failed against the runner's Java trust store.
- **Conclusion:** Tool presence is not authorization to run a native or network-resolving
  qualification. Require an explicit native-toolchain test opt-in in addition to PATH
  discovery, expose one named Make target for that opt-in, and leave ordinary Python
  gates deterministic and non-live. The native target must still fail when explicitly
  selected and its toolchain or dependency resolution is unhealthy.
- **Depends on:** existing Bazel Standard lifecycle and contributor Python gate
- **Implementation:**
  - [x] Gate every real-Bazel conformance case on explicit native-test authorization as
        well as required PATH capabilities.
  - [x] Add a discoverable native-toolchain Make target that runs the complete Bazel
        conformance subset with authorization enabled.
  - [x] Document the distinction between offline/non-live gates and native dependency
        resolution without weakening dedicated sample or worker qualification.
- **Evidence:**
  - [x] A focused selector regression proves only the exact value `1` authorizes native
        tests; all three real-Bazel cases skip under the ordinary suite despite ambient
        Bazel and are named by `make native-toolchain-check` with authorization enabled.
  - [x] The ordinary macOS/Python suite advanced through all 2,005 tests without
        attempting a Buildozer fetch; its only repair was a composed lifecycle-driver
        identity refresh. Independently, `make native-toolchain-check` passed all three
        explicitly authorized real-Bazel lifecycle cases in 415 seconds.

### [x] SAMPLE-MATRIX-003 — Verify the exact selected multi-repository matrix

- **Owner:** multi-repository sample conformance
- **Direction:** the live verifier must inspect the exact selected execution matrix. It
  must not require the retired implicit Python/C++ fanout after unpinned samples became
  a bounded Python/Make/host tuple in `SAMPLE-MATRIX-002`.
- **Conclusion:** require a non-empty set of unique implementation-language executions,
  then prove aggregate-source behavior for every selected variant without prescribing
  matrix size or language membership.
- **Depends on:** `SAMPLE-MATRIX-002`
- **Implementation:**
  - [x] Index exact execution evidence with non-empty, unique language validation.
  - [x] Exercise every selected variant and add a non-live bounded-default regression.
- **Evidence:**
  - [x] The focused verifier regression passes, a targeted live run accepts the
        bounded Python variant with both aggregate-source assertions, and the resumed
        complete live sample matrix passes from retained source.

### [x] SAMPLE-COORD-001 — Verify full-stack samples through canonical Flavor targets

- **Owner:** full-stack sample conformance
- **Direction:** the accepted execution contract stores exact canonical Flavor
  coordinates. Its live verifier must not compare those values directly with retired
  short aliases after the canonical Flavor migration.
- **Conclusion:** normalize the two declared language-role targets through the shared
  canonical target resolver before checking the Rust/JavaScript topology.
- **Implementation:**
  - [x] Normalize both role targets and retain exact slot-name validation.
  - [x] Add a non-live regression that executes the verifier against the committed
        canonical execution contract.
- **Evidence:**
  - [x] The focused canonical-coordinate regression and resumed complete live sample
        matrix pass.

### [x] MODEL-003 — Pin explicit models through sample qualification

- **Priority:** P0
- **Owner:** sample conformance CLI, locked generation preparation, and cache identity
- **Direction:** `scripts/run_samples.py --model MODEL` uses that selector as the pipeline model for every generated sample and retains it in correctness evidence.
- **Conclusion:** Bind the explicit selector through `LockedComponentModelSelectionAdapter`, generation recipes, Standard reports, source derivations, and checkpoints so no differently pinned run can be reused.
- **Implementation:**
  - [x] Add and propagate `--model MODEL` through live and derivation-planning paths.
  - [x] Bind model scope into generated recipes and Standard node evidence.
  - [x] Include model selection in cache and checkpoint identities.
- **Evidence:**
  - [x] Focused checkpoint and conformance model-scope tests pass.

### [x] MODEL-002 — Bind conformance model selection through its adapter instance

- **Owner:** Standard sample planning and live conformance execution
- **Direction:** sample and service-stack conformance must exercise the same bound
  lexical model-selection adapter as production. Calling its instance method on the
  class bypasses construction and fails before sample lifecycle execution.
- **Conclusion:** centralize sample model-identity resolution behind one helper that
  constructs `LockedComponentModelSelectionAdapter`, then use it for derivation
  planning, ordinary Standard samples, and the composed service stack.
- **Implementation:**
  - [x] Replace all three unbound conformance calls with the shared bound helper.
  - [x] Add a non-live regression that resolves every locked sample node without a
        coding-CLI invocation.
- **Evidence:**
  - [x] The focused bound-adapter regression passes, and the resumed complete live
        sample matrix executes the three-node composed Standard service stack.

### [x] INIT-DAG-003 — Inherit complete Component workflow and routing authority

- **Owner:** repository catalog composition and child-project validation
- **Direction:** a Component inherited through the repository DAG must remain valid when
  its authored workflow and routing policy live in the parent project's declared global
  catalogs. Importing only Components, Flavors, and skills leaves that Component's
  generation closure incomplete.
- **Conclusion:** compose declared workflow and routing roots alongside Components,
  Flavors, and skills. Treat each regular workflow or routing document as a named,
  provenance-bound catalog item; preserve the same ancestor precedence, sibling
  collision, exact-revision, path-safety, update, and rollback rules. Do not copy
  documentation or executable repository code as a substitute for missing authority.
- **Depends on:** `INIT-DAG-001` repository lineage and inherited catalog provenance
- **Implementation:**
  - [x] Read workflow and routing roots from exact Git snapshots and project them into
        deterministic `workflow:*` and `routing:*` catalog items.
  - [x] Carry those item kinds through initialization, update classification, and exact
        `.literate/imports.json` provenance without weakening collision checks.
  - [x] Update CLI help, inheritance documentation, release notes, and installed
        scaffold guidance to describe the complete inherited authority set.
- **Evidence:**
  - [x] Focused catalog tests prove deterministic workflow/routing materialization,
        descendant precedence, sibling collision rejection, and exact provenance.
  - [x] A child initialization imports a Component with parent-global workflow/routing
        references and passes canonical project validation.
  - [x] Full quality gates and installed-project smoke pass with current CodeGraph
        evidence. After rebasing onto current `main`, the fail-fast clean suite passed
        2,004 tests before exposing one stale derived lifecycle identity; the repaired
        continuation passed that test and all 61 remaining tests. Exact-revision
        `make wheel-check` passed and proved the initialized project lock, inherited
        authority, project CodeGraph preflight, and installed Standard binding.

### [x] VERSION-001 — Inspect Standard lifecycle bindings without external-driver fields

- **Owner:** read-only version consistency reporting
- **Direction:** `litai version check --project` must inspect projects initialized with
  the installed Standard lifecycle binding. It must not assume the source-declared
  external-driver shape or dereference `implementation_paths` on a Standard binding.
- **Conclusion:** Dispatch on the typed lifecycle binding. Preserve the exact external
  implementation-closure check for external drivers, and resolve Standard projects
  against the installed distribution and policy identities without weakening either
  trust boundary. Report a stable failed check for Standard mismatch rather than an
  uncaught Python exception.
- **Depends on:** the existing discriminated lifecycle-driver contract and Standard
  lifecycle binding resolver
- **Implementation:**
  - [x] Add typed Standard/external dispatch to the version report.
  - [x] Cover exact Standard success and mismatch while preserving external reports.
  - [x] Add installed-wheel proof against a newly initialized Standard project.
- **Evidence:**
  - [x] Focused version-authority tests pass.
  - [x] A clean installed wheel runs `litai version check --project` successfully on its
    initialized project and rejects a forged Standard distribution identity.

### [x] FLAVOR-DAG-001 — Compose selected Flavor capability requirements into Component locks

- **Owner:** Component lock planner and exact lock contracts
- **Direction:** A selected target Flavor may require a Component capability, such as
  a product packaging Flavor requiring its publication provider. That requirement must
  extend the resolved executable Component DAG only when the Flavor is selected;
  `FlavorDefinition.requires` was previously parsed and identity-bound but ignored by
  the lock planner.
- **Conclusion:** Preserve Components as the owners of behavior while treating a
  selected Flavor's typed `CapabilityRequirement` as target-conditioned composition
  authority. Resolve its provider through the same unique capability/version/constraint
  rules as an authored Component requirement, record the selected Flavor and exact
  requirement in the locked consumer revision, and emit the ordinary phase-specific
  executable edge. Unselected Flavors contribute no provider or edge. Reject duplicate
  requirement IDs across Component and selected-Flavor authority rather than guessing.
- **Depends on:** current Flavor-slot selection and Component lock resolution
- **Implementation:**
  - [x] Add a strict, content-identified selected-Flavor requirement binding to locked
    Component revisions without changing existing lock bytes when the set is empty.
  - [x] Make lock planning reach a deterministic fixed point across authored and
    selected-Flavor requirements, including recursively introduced providers.
  - [x] Validate persisted edges against either authored Component requirements or
    exact selected-Flavor requirement bindings, with the same interface, version,
    constraint, optionality, and acyclic-closure rules.
  - [x] Document the Flavor/Component boundary and update release-visible notes.
- **Evidence:**
  - [x] Focused contract and planner tests prove selected-only provider inclusion,
    unselected omission, recursive closure, unresolved/ambiguous failure, collision
    rejection, canonical round trip, and tamper rejection.
  - [x] The full Python quality gate passes and CodeGraph is current. The exact clean
    run completed 1,871 tests with 18 native-only skips and no failures.
  - [x] A clean installed wheel initializes and validates a project whose selected
    Flavor pulls a packaging-phase Component edge. The wheel smoke proof selected the
    `python` Flavor and resolved `component://example/wheel-package-publisher` for
    `packaging.wheel-smoke-publisher`.

### [x] INIT-DAG-001 — Initialize from any repository in an inherited repository DAG

- **Owner:** project initialization, catalog imports, and project update lineage
- **Direction:** `litai init` must work from any repository in a Literate-AI repository
  DAG, optionally accepting a repository URL. The new project inherits the selected
  repository and every declared ancestor rather than silently falling back to only the
  framework distribution that installed the CLI.
- **Conclusion:** Add an unambiguous optional `--from URL` input while preserving the
  no-URL installed-framework default. Resolve the selected repository into isolated
  `OBJ_DIR` storage, validate its canonical project and initialization/import lineage,
  traverse ancestors in deterministic ancestor-first order with cycle and conflicting-
  origin rejection, then materialize the effective taxonomy using the existing catalog
  provenance model. Record the selected URL, exact revision, complete ancestor chain,
  and baselines so `litai update` follows the same lineage. Never execute repository code
  merely to discover ancestry, and never embed credentials from a URL in project files.
  Add `litai reparent URL|none`: a URL resolves and validates a complete prospective
  lineage and produces a cautious three-way migration against recorded baselines before
  changing authority; `none` records an explicit root/divorced state rather than an
  omitted or ambiguous parent. In that state `litai update` is a typed no-op. Project
  validation checks that the declared parent, resolved lineage, and baselines agree.
- **Depends on:** exact initialization origin/baseline contracts and catalog-import DAG
- **Implementation:**
  - [x] Define versioned repository-lineage and inherited-initialization contracts,
        including canonical URL sanitization, exact revision selection, cycle bounds,
        precedence, collision handling, and offline/cache semantics.
  - [x] Add `litai init [PATH] --from URL`, detect-before-fetch tooling, isolated clone or
        local-path resolution, non-executing validation, and deterministic ancestor-first
        catalog composition.
  - [x] Extend `litai update` to compare and upgrade against the recorded complete lineage
        rather than only the distribution build origin.
  - [x] Add `litai reparent URL|none` with a read-only plan, explicit conflict reporting,
        compare-and-swap application, rollback on failure, and no implicit overwrite of
        local authority.
  - [x] Make `litai project validate` reject missing, truncated, cyclic, stale, or
        internally inconsistent parent/lineage evidence; accept the explicit `none`
        parent state and make update report a typed no-op for it.
  - [x] Document local-parent, remote-parent, forked-framework, authentication, and failure
        flows; carry the same behavior and help into installed wheels.
- **Evidence:**
  - [x] Focused tests cover no-URL compatibility, local and remote ancestry, three-level
        inheritance, deterministic override precedence, cycles, collisions, unreachable
        and unauthenticated repositories, credential redaction, and no repository-code
        execution.
  - [x] A repository that declares a parent cannot be accepted as a complete lineage:
        initialization and update both fail closed if traversal stops before the root.
  - [x] A clean installed wheel initializes from a temporary three-repository DAG,
        validates inherited Components/Flavors/skills, and plans an inherited sample.
  - [x] `litai update` follows the recorded ancestor chain after an upstream change while
        preserving local authority and surfacing conflicts without overwriting them.
  - [x] Reparent tests cover parent-to-parent migration, conflicts, a changed prospective
        chain, stale compare-and-swap inputs, rollback, credential redaction, and
        `reparent none` followed by a validated no-op update.

### [x] INIT-DAG-002 — Admit canonical pre-lineage projects through explicit reparenting

- **Owner:** repository-parent authority and reparent transaction
- **Direction:** Projects created before repository-DAG evidence existed need one safe,
  explicit route onto the current inheritance model so maintained derived repositories
  can adopt the current framework instead of being stranded by validation.
- **Conclusion:** Keep ordinary validation and update fail closed. Only `litai reparent`
  may treat the simultaneous absence of both lineage documents as a typed legacy-root
  starting state. Record that absence in the read-only plan, compare-and-swap against
  continued absence during apply, and restore absence if prospective validation fails.
  A partial, malformed, or concurrently introduced lineage remains an error. Applying
  `reparent none` must materialize explicit root evidence rather than report a false
  no-op.
- **Depends on:** `INIT-DAG-001` repository-lineage contracts and reparent transaction
- **Implementation:**
  - [x] Add typed planning evidence for a previously unrecorded lineage without
        weakening the canonical lineage store's ordinary `load` behavior.
  - [x] Add absence-aware compare-and-swap and rollback to the lineage store.
  - [x] Teach reparent plan/apply to bootstrap only the both-absent state.
  - [x] Keep hand-authored canonical-project fixtures honest by recording explicit root
        lineage while preserving their catalog/provider-shim minimality.
  - [x] Document the bounded migration path and release-visible behavior.
- **Evidence:**
  - [x] Focused store and reparent tests cover inherited and explicit-root bootstrap,
        partial evidence rejection, concurrent evidence creation, and rollback to
        absence after validation failure. The focused contract/schema run passed 37
        tests with no failures.
  - [x] The full Python quality gate passes and CodeGraph is synchronized. The clean
        checkpointed run passed 1,998 tests with 18 native-only skips; Ruff checked 568
        formatted files, OpenSpec validated both changes, 142 Mermaid diagrams rendered,
        and CodeGraph is current at `sha256:1c96daa2353017110db1eaf4af4c4198ba1f5f59cd42f982aae05e101304e35c`.

### [x] CODEGRAPH-DRIFT-001 — Detect a host CodeGraph CLI upgrade and recover automatically instead of failing unhealthy

- **Priority:** P1
- **Owner:** `src/literate_ai/adapters/intelligence/codegraph.py`
  (`_prepare_index`/`_operational_status`), `src/literate_ai/project_source_index.py`
- **Direction:** Reproduced directly this session: updating the ambient `codegraph` CLI
  on a host (`/opt/homebrew/bin/codegraph`, 1.1.1 → 1.5.0) while an existing project
  index remains on disk leaves every `litai project source-intelligence sync`/`check`/
  `validate` failing with the generic `project.source_intelligence_unhealthy`, even
  immediately after a fresh `sync`. Root-caused precisely: `_prepare_index` (line ~479)
  always runs `codegraph sync <path> --quiet` when `.codegraph/codegraph.db` already
  exists — it never inspects whether the newly-invoked binary's version differs from
  the index's own `builtWithVersion`. `OperationalSourceIndexStatus.__post_init__`
  correctly rejects that mismatch (`built_with_version != runtime_version`), and
  `_operational_status` correctly classifies it as `"CodeGraph index requires a
  compatible full rebuild"` — but `sync` alone can never satisfy that (only `codegraph
  index`, a full rebuild, updates `builtWithVersion`), so the condition never
  self-heals, and the specific, actionable reason is discarded by the time it reaches
  `project_source_index.py`'s catch-all `except IntelligenceAdapterError: raise
  ProjectSourceIntelligenceError("project.source_intelligence_unhealthy", ...)`.
  This is distinct from `CODEGRAPH-PROJECT-001`'s "missing or stale index" handling,
  which already covers absent/corrupt indexes but not this specific
  version-incompatible-but-present case.
- **Conclusion:** Detect the version-mismatch condition explicitly before or after an
  ordinary `sync` attempt, and when found, automatically escalate to a full `codegraph
  index` rebuild (bounded by the same safety checks `CODEGRAPH-PROJECT-001` already
  applies to index creation) rather than leaving the project permanently unhealthy
  until a human notices and manually deletes `.codegraph/`. When automatic rebuild is
  not desired or not possible (e.g. `check`'s explicitly non-mutating contract), at
  minimum surface the real, specific reason (`built_with_version` vs the newly-detected
  runtime version, and that a full rebuild — not another sync — is required) instead of
  the generic `unhealthy` message, so a human or agent knows exactly what happened and
  what to do about it without needing to read this framework's own source to find out.
- **Depends on:** `CODEGRAPH-PROJECT-001`'s existing stale/missing-index handling
- **Implementation:**
  - [x] Added `_recover_from_runtime_version_drift`, called from `_prepare_index`
        immediately after an ordinary `sync` when the on-disk index already exists: a
        best-effort, self-swallowing probe (`codegraph status --json`) that detects
        `fileCount > 0 and builtWithVersion != version` and, when found, runs
        `codegraph index` (a full rebuild) once before returning. Probe failures are
        swallowed rather than raised — the ordinary status-validation path immediately
        after already raises its own correctly typed error for anything this
        best-effort probe misses.
  - [x] `check` (`synchronize=False`) never calls `_recover_from_runtime_version_drift`
        — that call is only reachable from the `synchronize=True` branch of
        `_prepare_index` — so its non-mutating contract is structurally preserved, not
        just documented.
  - [x] Did not add a new typed error code (kept `project.source_intelligence_unhealthy`
        stable). Instead added `_SAFE_UNHEALTHY_REASONS`, an explicit allowlist of
        literal, hardcoded (never subprocess-derived) `IntelligenceAdapterError`
        messages safe to forward verbatim; `"CodeGraph index requires a compatible full
        rebuild"` is now embedded in the CLI-facing message when it's the actual cause.
        Discovered and preserved a real existing invariant while doing this:
        `test_version_floor_and_engine_errors_are_stable_and_redacted` asserts arbitrary
        underlying error text (which can carry forwarded subprocess/secret content) must
        never reach the client-facing message — an unscoped `f"...: {exc}"` would have
        silently broken that redaction guarantee, so the allowlist approach was chosen
        specifically to preserve it rather than widen what gets forwarded.
  - [x] Added `test_sync_recovers_from_runtime_version_drift` (simulates an upgraded
        `codegraph` binary against an existing index; asserts `sync` then `index` both
        ran, in that order, and the resulting status reflects the rebuilt version) and
        `test_check_never_attempts_a_rebuild_on_runtime_version_drift` (asserts `check`
        raises without ever invoking `index`) in `tests/unit/test_codegraph_adapter.py`,
        plus `test_unhealthy_error_preserves_the_specific_underlying_reason` in
        `tests/smoke/test_project_source_index.py`.
- **Evidence:**
  - [x] Reproduced this session's exact scenario locally (`codegraph` upgraded
        1.1.1 → 1.5.0 on this host, existing `.codegraph/` index) — verified live before
        this fix that ordinary `sync` never recovered; the new regression test covers
        the same shape deterministically. (The live host index itself was already
        recovered with a manual `codegraph index .` in this same session, ahead of this
        fix landing.)
  - [x] `check`'s error message, when it cannot self-heal, names the specific
        version-mismatch cause (`... requires a compatible full rebuild`) rather than
        the bare generic unhealthy message, without forwarding arbitrary underlying
        exception text.

### [x] DOC-PUB-001 — Keep generic authoring portable and publication provider-bound

- **Owner:** document-pair capability, authoring skill, documentation ecosystem Flavors
- **Direction:** Anyone should be able to reproduce a local editable document without
  proprietary MCPs or one maintainer's tools. Service-specific prerequisites,
  installation, login, access mapping, upload, and verification belong to the selected
  publishing Flavor.
- **Implementation:**
  - [x] Make the generic authoring skill connector-independent and define its local
        toolchain/isolation/failure contract in both framework and project template.
  - [x] Move Google token, exact-resource update, and read-back rules into the Google
        Workspace binding in both framework and project template.
  - [x] Add equivalent client discovery, device-login, tenant-policy, and read-back rules
        to the Microsoft 365 binding.
  - [x] Validate framework and initialized-project authority; run the changed-skill
        admission gate and initialization tests.
- **Evidence:**
  - [x] A derived project receives the same generic skill and both optional bindings.
  - [x] No generic authoring instruction names a mandatory MCP or publishing credential.
  - [x] Missing service tooling produces actionable install/login guidance without
        weakening local artifact acceptance.

### [x] CI-SHARD-001 — Generalize durations-based CI test sharding as a skill

- **Release target:** 0.8.0 (break-glass major-equivalent; was 0.4.1)
- **GitHub issues:** [#83](https://github.com/NVIDIA-dev/literate-ai/issues/83),
      [#84](https://github.com/NVIDIA-dev/literate-ai/issues/84),
      [#85](https://github.com/NVIDIA-dev/literate-ai/issues/85),
      [#86](https://github.com/NVIDIA-dev/literate-ai/issues/86)
- **Owner:** CI/release tooling; provider-neutral, not literate-ai-specific content
- **Direction:** Windows CI's test run was the long pole (~45-58 min) because it ran the
  whole suite in one job with no cross-runner parallelism, while Linux/macOS already had
  some parallelism from a `{python: [...]}` matrix. Fixed directly for this repository by
  splitting `windows-conformance` into a `windows-gates` job (lint, OpenSpec/doc
  validation, CodeGraph, wheel-check — run once) plus a 3-way `windows-tests` matrix using
  `pytest-split`'s `--splits`/`--group` against a committed `.test_durations` file. That
  fix is real but hand-authored directly into `.github/workflows/ci.yml`, not expressed
  through this framework's own Component/Flavor/skill system at all.
- **Conclusion:** Generalize as an agent skill (operational/CI-maintenance skill, not a
  specification-to-source skill — there is no existing skill category for "how to author
  or improve a project's own CI pipeline" today) that: (1) detects the project's test
  framework(s), (2) checks whether a maintained durations/timing-based sharding mechanism
  exists for that framework (pytest → `pytest-split`; Jest → `--shard`; Go →
  `gotestsum`/manual partitioning; `cargo nextest` → `--partition`; etc.), (3) if so,
  proposes or authors the job-matrix split plus the durations-seed file and its refresh
  procedure, and (4) if not, says so explicitly rather than silently leaving the project
  unsharded. Do not assume every framework has an equivalent to `pytest-split` — record
  what's actually available per framework as the skill is authored, not speculatively.
- **Scope note (asked and answered 2026-08-16):** sharding is not Windows-specific as a
  *technique* — it helps anywhere one CI job runs a whole suite serially. It doesn't
  extend to this repository's own Linux/macOS jobs for free: those call tests through
  `scripts/run_checkpointed_unittests.py` (a custom `unittest`-based fail-fast/resume
  runner), not pytest directly, so `pytest-split` has nothing to attach to there today.
  Extending sharding to Linux/macOS in this repository specifically means either
  switching those jobs to a pytest-based invocation (losing or reimplementing the
  checkpointing/resume behavior `make release-check` depends on) or building equivalent
  durations-based splitting for the checkpointed-unittest runner — track that as a
  follow-up decision once the general skill exists, not as part of this item.
- **Next action:** Skill contract landed (`litai project ci-plan`,
      `skills/agent/ci-test-plan`). Agents author CI YAML from the plan; this
      item does not install language runtimes. Windows pytest-split stays;
      Linux/macOS checkpointed jobs stay unsharded.
- **Implementation:**
  - [x] Author the skill: framework detection, per-framework sharding-mechanism
        availability table, matrix/job authoring, durations-seed generation and refresh
        procedure.
  - [x] Decide (with evidence, not assumption) whether extending this repository's own
        Linux/macOS jobs to shard is worth the checkpointed-runner tradeoff above.
        Decision: keep unsharded. `load_completed` requires
        `completed == tests[:len(completed)]`; parallel shards finish out of order.
  - [x] Validate the skill against at least one non-Python project (Jest or Go) to prove
        the framework-detection/availability-table approach generalizes, not just retrofits
        the Windows pytest case. Fixture trees in `tests/unit/test_ci_test_plan.py`
        cover Jest, Go, cargo-nextest, and Swift-unavailable.
- **Evidence:**
  - [x] A project with a slow single-job test run gets a proposed or authored shard split
        appropriate to its actual test framework, or an explicit "not available for this
        framework" result — never a silent no-op.
        `plan_ci_tests` always sets `silent_noop` false; unknown trees return
        `status: unavailable` / `reason: no_recognized_test_framework`.
  - [x] The skill does not assume pytest, Python, or this repository's own CI shape.

### [x] CI-IMPACT-001 — Impact-based test selection for CI (skip, not just parallelize)

- **Release target:** 0.8.0 (break-glass major-equivalent; was 0.4.1)
- **GitHub issues:** [#83](https://github.com/NVIDIA-dev/literate-ai/issues/83),
      [#84](https://github.com/NVIDIA-dev/literate-ai/issues/84),
      [#85](https://github.com/NVIDIA-dev/literate-ai/issues/85),
      [#86](https://github.com/NVIDIA-dev/literate-ai/issues/86)
- **Owner:** CI/release tooling; provider-neutral, not literate-ai-specific content
- **Direction:** CI-SHARD-001 makes a slow test run faster by spreading the *same* fixed
  set of tests across more runners. It never reduces how much work happens in total. This
  repository's own `test_checkpointing.py` looks like it might help further, but it
  doesn't: it only skips tests already recorded as passed for the *same* linear plan
  identity on a *retry of the same local state* (a developer re-running `make validate`
  after fixing a failure) — a fresh CI runner has no prior state to resume from, so
  checkpointing has nothing to skip on a normal CI run, and its linear-prefix design
  (`completed == prefix`) is incompatible with parallel workers finishing tests out of
  order in the first place. The actual "run fewer tests" lever is different: skip tests
  whose covered code didn't change since the last known-good revision of the exact same
  commit lineage.
- **Conclusion:** Generalize as an agent skill (same operational/CI-maintenance category
  as CI-SHARD-001, and likely composed with it — impact selection narrows *which* tests
  run, sharding parallelizes *what's left*) that: (1) detects whether the project's test
  framework has a maintained impact/coverage-based selection mechanism (pytest →
  `pytest-testmon` or coverage-guided selection; Go → `go test -run` driven by package-
  level change detection; Jest → `--changedSince`/`--onlyChanged`; etc.), (2) if so,
  proposes or authors the wiring plus the coverage-map/history persistence and refresh
  procedure its mechanism needs, and (3) if not, says so explicitly. Do not assume every
  framework has an off-the-shelf equivalent; record what's actually available as the
  skill is authored.
- **Correctness constraint:** impact-based selection changes what runs, not just how fast
  — a false negative (skipping a test that would have caught a real regression) is a
  correctness failure of the *release process*, not a performance tradeoff. Any
  authored/proposed wiring must fail closed (run the full suite) whenever the impact map
  is stale, missing, or its own identity/coverage data doesn't verifiably cover the exact
  diff being tested — never silently trust an unverified or partial map.
- **Next action:** None for this item. Optional extra `literate-ai[impact]`
  (`pytest-testmon==2.2.0`) is the skip runner; `make python-check` and
  `RELEASE_GATES` stay full-suite.
- **Implementation:**
  - [x] Author the skill: framework detection, per-framework impact-selection-mechanism
        availability table, wiring/authoring, coverage-map or history persistence and
        refresh procedure, fail-closed-to-full-suite behavior when the map can't be
        trusted.
  - [x] Decide whether and how this composes with CI-SHARD-001's sharding for a project
        that has both mechanisms available (narrow the set, then shard what's left).
        Compose is impact then shard; missing/untrusted maps select `shard_full_suite`.
  - [x] Validate against at least one non-Python project to prove the approach
        generalizes. Jest `--changedSince` is recorded as available; Go package-graph
        tools stay `unverified`; cargo-nextest impact is `unavailable` (#84).
- **Evidence:**
  - [x] Live pytest-testmon==2.2.0 in an isolated venv: refresh runs both fixture
        tests; a beta-only change reruns `test_beta` and not `test_alpha`
        (2 passed → 1). Stale/missing maps and `.test_durations` force
        `--no-testmon`. `scripts/run_impact_pytest.py` / `ci_impact_run.py`
        pass real `--testmon`. This repo's `python-check` / Windows shard jobs
        still do not use it. Landed as `620c4fa3` (isolated `48b6f5c0`).
        `tests.critical.test_ci_impact_run` and `tests.unit.test_ci_test_plan`.
  - [x] The skill does not assume pytest, Python, or this repository's own CI shape.

### [x] COVERAGE-GAP-001 — Mechanical detection of declared-but-unimplemented surface

- **GitHub issue:** [#64](https://github.com/NVIDIA-dev/literate-ai/issues/64)
- **Owner:** `src/literate_ai/adapters/coverage_gaps.py`, `cli/build_run.py`
- **Direction:** A green `litai build`/`litai test` isn't evidence the generated
  implementation does what the spec describes, since the same coding-CLI call writes
  both the implementation and its own tests. Two real examples: a generated HTTP API
  had route handlers literally bound to `None` despite 17/17 generated tests passing;
  a generated worker never called its own upstream client despite 15/15 tests passing.
  The issue proposed two directions: (A) mechanically derive expected behavioral facts
  from the spec and check the generated tests reference them, or (B) a second
  adversarial coding-CLI pass reading the spec and the first pass's tests to report
  uncovered behavior.
- **Conclusion (2026-08-16):** Landed the cheapest honest slice of (A), scoped
  narrower than originally proposed after a real finding changed the design mid-flight:
  `Entrypoint.path` (the only structurally machine-readable "declared surface" the
  Component schema offers today) turns out to be a purely declarative/logical value —
  nothing in `standard_project.py` ever resolves a real file or directory at that path
  inside the generated `sources/` tree. A per-entrypoint path-scoped scan was designed
  first, then discarded once this was found, in favor of a whole-generated-tree scan
  for common stub markers (`NotImplementedError`, `TODO`/`FIXME`, a string-keyed
  handler/route table entry bound to `None`) — catches the API-routes-are-`None`
  example exactly; does **not** catch the worker-never-calls-its-client example, which
  is a dead-code/call-graph question needing a fundamentally different, heavier static-
  analysis feature, explicitly deferred rather than faked. Direction (B) (adversarial
  second pass) was not attempted — real per-build API cost, nondeterminism, and its own
  trust-boundary problem (a lazy adversarial pass can rubber-stamp gaps) make it a
  separate, larger decision, not an MVP.
- **Landed as fail-closed on high-confidence stubs:** path-keyed `/`-prefixed
  `None` handlers and `NotImplementedError` in generated **product** files fail
  `litai build`/`test` with `build.unimplemented_surface`. TODO/FIXME,
  pass-bodied abstracts, and `NotImplementedError` in generated tests stay
  advisory. Fixture/sample corpus: 0% fail-closed hits
  (`test_fixture_and_sample_trees_have_no_fail_closed_hits`). Not live
  generation traffic.
- **Worker path:** scan runs on the worker after rebuild, before the runtime
  tree is deleted. Optional `coverage_gaps` on
  `urn:literate-ai:schema:v2:execution-dispatch-result`
  (`literate-ai/coverage-gap-report@3`); SSH control results copy it.
  Scan-side defects still yield `null` and never fail the lifecycle.
  Landed as `7598aee4` (isolated `6419cbec`).
- **Implementation:**
  - [x] `coverage_gaps.py`: `find_coverage_gaps()` — whole-tree stub-marker scan,
        typed `CoverageGapReport`/`CoverageGap` with a `canonical_identity()`.
  - [x] `build_run.py`: `_scan_coverage_gaps()` wires the scan into the local build
        path only; fails closed to `None` (never raises) on any scan-side defect.
  - [x] Worker-dispatched builds report `coverage_gaps` through the dispatch
        result (optional on the wire).
  - [x] Characterize false-positive rate against fixtures, samples, and labeled
        unit fixtures; promote fail-closed only for path-keyed `None` handlers
        and product `NotImplementedError`. Live generation traffic was not used.
  - [x] Direction (B) (adversarial second pass) deferred; see
        `docs/history/roadmap/coverage-gap-detection.md`.
- **Evidence:**
  - [x] Unit tests (`tests/smoke/test_coverage_gaps.py`) cover: no gaps on fully
        implemented source; `NotImplementedError`/`TODO`/`None`-bound-handler markers
        each flagged with the correct reason code; nested files scanned; report
        identity stable and content-addressed.
  - [x] Integration tests exercise the real `build_run.py` wiring (`_scan_coverage_gaps`)
        against `samples/hello-component`'s real `component.md` authoring, both the
        clean and the stubbed case.
  - [x] Worker path: `tests.unit.test_cli_command_worker_lifecycle`,
        `test_remote_execution`, `test_execution_dispatch_contracts`. Full live
        `litai build` from scratch remains unrun.

### [x] DOCS-004 — Refresh and republish the Literate-AI overview

- **Owner:** documentation artifacts / Google Workspace publication
- **Direction:** Regenerate the maintained Literate-AI presentation and update the
  authorized existing Google Slides resource in place. Teach the publishing skill to
  acquire the current Google bearer token with `gcloud auth print-access-token`.
- **Conclusion:** Preserve the checked-in reproducible authoring package, run its
  independent document-pair oracle and visual QA, publish only to the supplied resource
  ID, and verify the native Slides copy after upload. Never persist access tokens.
- **Implementation:**
  - [x] Add the just-in-time gcloud token rule to the framework and initialized-project
    presentation skills.
  - [x] Regenerate the local PPTX and pass document-pair and visual checks.
  - [x] Update presentation `1V9mt1JpEst_2ucC0eJIIw7dff64MrtFRfut8MSiukeE` in place.
  - [x] Export and compare the published realization, then update the QA and delivery
    ledgers.

### [x] INTRINSIC-001 — Make user direction durable before implementation

- **Owner:** framework core / initialized-project agent workflow
- **Direction:** Every substantive suggestion must become a reasoned repository plan and
  unchecked TODO before implementation, survive session closure, and produce the
  appropriate changelog entry when complete.
- **Conclusion:** Ship a provider-neutral Agent Skill, make the top-level onboarding
  skill require it, and initialize every derived project with the same skill, active
  queue, and changelog. Conversation state is not durable project authority.
- **Depends on:** none
- **Implementation:**
  - [x] Define the work-item reasoning, ownership, dependency, evidence, and changelog
    workflow in `skills/agent/record-user-directed-work/SKILL.md`.
  - [x] Add the skill and this resumption queue to framework and derived-project
    onboarding.
  - [x] Add initialized `docs/roadmap/active-work.md` and `CHANGELOG.md` templates.
  - [x] Prove initialized projects contain and validate the complete workflow.
  - [x] Package the synthetic matrix JSON in the wheel; the first clean wheel gate found
    that the root template package-data list admitted Markdown but omitted this JSON.
- **Evidence:**
  - [x] Skill creator validation passes for both shipped skill copies.
  - [x] NVIDIA SkillEvaluator's schema, PII, license, quality, Unicode, and lint
    admission checks pass without LLM evaluation.
  - [x] Unit initialization tests and clean `make wheel-check` at `fd199c1` prove all
        durable files exist in both the source template and installed wheel.

### [x] TRACKER-HOST-001 — Detect GitHub vs GitLab from Git remotes and use `gh` or `glab`

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#188](https://github.com/NVIDIA-dev/literate-ai/issues/188)
- **Owner:** `litai project tracker`, `skills/agent/record-user-directed-work`
- **Direction:** Fully support looking for issues and pull or merge requests in any
      Literate AI derived project. Read Git remotes (the same authority as
      `.git/config`, including worktrees). If the URL is on GitHub, use `gh` to
      read, modify, or write issues and pull requests. If it is on GitLab,
      including self-hosted hosts whose DNS labels include `gitlab`, use `glab`
      to read, modify, or write issues and merge requests.
- **Conclusion:** Do not hard-code GitHub. `litai project tracker inspect` classifies
      the forge and names the CLI plus list argv. Agents wrap that command; they
      do not re-parse remotes. Unknown hosts skip tracker reconciliation fail
      closed. GitHub and GitLab remotes without `origin` and in disagreement are
      `project.tracker_host_ambiguous`. Tokens in remote URLs never appear in
      inspect evidence. This is not GitLab *release-gate* dispatch
      ([RELEASE-005](../../roadmap/active-work.md#x-release-005-make-the-release-gates-execution-target-an-explicit-durable-user-choice));
      `--target gitlab` for `litai release check` stays unsupported until that
      provider exists.
- **Scope boundary:** Do not add Bitbucket, Jira, or a third tracker client *as a
      default*; ADR 0050 admits other trackers and review systems as explicit
      project or user overrides (TRACKER-DEFAULT-001). Do not
      change repository-lineage resolution. Do not wrap every `gh`/`glab` write
      verb inside `litai`; inspect names the CLI, agents invoke it.
- **Depends on:** none
- **Implementation:**
  - [x] Classify GitHub, GitLab, unsupported, and ambiguous hosts from remote URLs.
  - [x] `litai project tracker inspect` reads remotes through Git and emits
        `issue_list` / `review_list` argv.
  - [x] Update `record-user-directed-work` (catalog and init template) and root
        `SKILL.md` so planning passes are forge-neutral.
  - [x] Prove a GitLab remote inspect names `glab` and `glab mr list` in CI.
- **Evidence:**
  - [x] Focused unit tests for URL classification and CLI inspect.
  - [x] Catalog and init-template skill copies remain byte-identical.

### [x] TRACKER-DEFAULT-001 — Make forge issues and reviews the default tracker and coordination channel

- **Priority:** P1
- **Release target:** 1.2.0
- **Owner:** `litai project tracker`, `litai project guidance`, `litai prompt`,
  `skills/agent/record-user-directed-work`, project `SKILL.md`
- **ADR:** [0050](../../decisions/0050-forge-issues-and-reviews-are-the-default-tracker.md)
  (Accepted 2026-10-09)
- **Direction:** A project's default task and project-management system is the forge
  hosting the repository that receives issues and PRs (GitHub or GitLab): problems are
  issues, changes are PRs/MRs against a target branch, and agents coordinate through
  issues. Another tracker, external agent ledger, or review system (for example
  Gerrit) is a user or project override, never a hard-coded default.
- **Implementation (1.2):**
  - [x] Generic external task envelope: `LITAI_EXTERNAL_TASK_ID`,
        `--external-envelope`, `prompt_routing.external_envelope_bypass`,
        `prompt-task@2`; `LITAI_MAC_TASK_ID` / `--mac-envelope` are deprecated aliases.
  - [x] `guidance --operation land` passes the policy `default_branch` as
        `gh pr create --base` / `glab mr create --target-branch`.
  - [x] `litai init` no longer installs `write-mac-project-contract`; that skill is an
        opt-in build/test runner contract.
  - [x] `SKILL.md`, the template `SKILL.md`, `prompt-master`, and the ledger
        architecture state the forge default and treat MAC as an optional override.
- **Follow-up:** TRACKER-DEFAULT-002 (1.3.0).
- **Evidence:**
  - [x] `tests/smoke/test_prompt_routing.py` covers the generic and deprecated envelope
        spellings; `tests/smoke/test_project_guidance.py` covers the GitHub and GitLab
        target-branch argv.

### [x] CANDIDATE-DIAG-001 — Retain bounded build-diagnostic excerpts for rejected generated candidates

- **Priority:** P1
- **Release target:** 1.2.0
- **Owner:** `tests/conformance/support/sample_runner.py` (runner-pinned),
  `literate-ai/generated-candidate-rejection@1`, `src/literate_ai/adapters/builders/`
- **Direction:** A rejected generated candidate must say why it was rejected, both in
  retained evidence and in the repair feedback the next attempt receives.
- **Context:** **2026-10-09:** the Linux `samples` gate at `56163f0b` exhausted three
  `linux-cgroup-budget` C++ attempts (two `generated-source-build-rejected` with
  `builder.cpp_generated_source_rejected`, one `generated-test-behavior-mismatch` on
  `fractional-cpu-floor`). The compiler output exists: `builders/cpp.py` puts the last
  4000 bytes of stdout and stderr in the `BuildError` message. But the build-rejected
  record keeps only `build_failure_code`, `candidate_tree_identity`, and
  `diagnostic_identity`, so `rejections-NN.json`, the evidence ledger, and the gate log
  cannot show the error. Those same records are the `candidate_feedback` for the next
  attempt, so attempts 2 and 3 were repaired without the compiler error. Contract
  rejections already keep `message`.
- **Conclusion:** Add a bounded, redacted `diagnostic_excerpt` (UTF-8, tail-limited, for
  example 4 KiB, with the same secret and host-path redaction as coding-CLI failure
  excerpts) to build-rejected and test-behavior-mismatch records. Keep it inside the
  hashed diagnostic so `diagnostic_identity` names the bytes shown. Feed it to repair.
  Keep it outside semantic generation and cache identities other than repair feedback.
- **Depends on:** none
- **Implementation:**
  - [x] No builder change: the C++, Swift, Rust and Bazel builders already put a
        ~4000-byte output tail in the `BuildError` message, so the runner excerpts it.
  - [x] `_candidate_diagnostic_excerpt` in `sample_runner.py`: secrets redacted, host
        path directories collapsed to `<host-path>/` (basenames kept), tail-bounded to
        4096 UTF-8 bytes.
  - [x] `generated-source-build-rejected` records carry `diagnostic_excerpt` inside the
        hashed diagnostic. `generated-test-behavior-mismatch` carries the generated
        expected and observed values. Independent-verifier mismatches carry none,
        because their expectations are verifier-only. The record schema stays `@1`:
        the field is additive and no consumer validates keys.
  - [x] Repair feedback carries the excerpt unchanged through the plan stage's
        `previous_candidate_rejections`. `rejections-NN.json` and the attempts
        summary in the gate log include it.
  - [x] Runner review and re-pin for `sample_runner.py`.
- **Evidence:**
  - [x] `tests/smoke/test_candidate_rejection_diagnostics.py` compiles a deliberately
        broken C++ source with the host compiler and finds its error in the rejection
        record, the attempts envelope, and the next plan's
        `previous_candidate_rejections`. It also checks secret and host-path
        redaction, the byte bound, and that behavior mismatches expose both generated
        values.

### [x] PARENT-SUBTREE-001 — Check out parents under `parents/<id>` with submodules and LFS

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#189](https://github.com/NVIDIA-dev/literate-ai/issues/189)
- **Owner:** `litai project parent checkout`, repository inheritance docs, agent skill
- **Direction:** When checking out parent repositories to update them, search them,
      or file issues and review requests against them, always manage the checkout
      in the current project under `parents/<id>/`. If the parent uses submodules
      or Git LFS, run the extra Git operations so the tree is complete.
- **Conclusion:** Contribution/search checkouts are not lineage resolution. Lineage
      stays non-executing plumbing in `OBJ_DIR/repository-lineage` with no working
      tree, hooks, or submodule execution. `litai project parent checkout URL[#REVISION]`
      clones or updates `parents/<id>/` with `--recurse-submodules`, then
      `git submodule update --init --recursive` and `git lfs pull` when pointers
      exist. Contrib `git subtree` porcelain is not required (it is absent on many
      hosts); the layout is the subtree prefix in this project. Never clone parents
      into `/tmp` or extra Git worktrees. `parents/` is excluded from the child's
      index via `.git/info/exclude` and is not catalog authority. URLs with
      embedded credentials fail closed.
- **Scope boundary:** Do not fold a parent's branded product into this catalog
      because a checkout exists. Do not auto-commit parent bytes onto the child's
      default branch. Do not replace `litai update` / `init --from` with this
      checkout.
- **Depends on:** [TRACKER-HOST-001](../../roadmap/active-work.md#x-tracker-host-001-detect-github-vs-gitlab-from-git-remotes-and-use-or)
      when filing issues or review requests against the parent.
- **Implementation:**
  - [x] `litai project parent checkout` clones/updates `parents/<id>/`.
  - [x] Initialize submodules; pull LFS when pointers are present.
  - [x] Document the contribution path as distinct from lineage resolution.
  - [x] Add a submodule fixture so checkout initializes a nested module.
- **Evidence:**
  - [x] Focused CLI test clones and updates a local parent under `parents/`.
  - [x] Credentialed URLs fail closed.

### [x] USER-MCP-001 — Operator-local MCP catalog; offer setup; Jira only when available

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#192](https://github.com/NVIDIA-dev/literate-ai/issues/192)
      (Jira consumer [#191](https://github.com/NVIDIA-dev/literate-ai/issues/191))
- **Owner:** `litai` CLI entry, operator-local user config,
      `skills/agent/configure-operator-mcp`, `skills/agent/release-project`
- **ADR:** [0021](../../decisions/0021-operator-local-mcp-catalog.md),
      [0022](../../decisions/0022-channel-author-recipient-vocabulary.md),
      [0023](../../decisions/0023-mutagenic-cli-channel-fan-out.md)
- **Depends on:** [CHANNEL-VOCAB-001](../../roadmap/active-work.md#x-channel-vocab-001-shared-literate-ai-author-or-recipient-vocabulary-for-jira-slack-and-outlook)
      for the envelope. ADR 0021/0023 are accepted for 0.8.0.
- **Direction:** Each user keeps an MCP list under `$HOME/.config/literate-ai` (honor
      `XDG_CONFIG_HOME` and `LITAI_CONFIG_DIR`). If that directory has nothing in it
      when they launch any `litai` command, offer to set it up. Jira is the same
      task: associate a major/minor Epic, Story, or Task only when a Jira MCP is
      listed **and** connected/available. After association, **every significant
      mutagenic `litai` command** (any user) appends a bounded comment on that
      ticket — the same event class as Slack and Outlook, using
      [CHANNEL-VOCAB-001](../../roadmap/active-work.md#x-channel-vocab-001-shared-literate-ai-author-or-recipient-vocabulary-for-jira-slack-and-outlook)
      so Literate AI is clearly the **author**. Do not invent a third tracker
      client.
- **Conclusion:** An interactive coding session follows
      `skills/agent/configure-operator-mcp` to discover already-connected session
      MCPs and write the catalog. Interactive TTY `litai` without an agent still
      offers ids-only setup; `--json` / non-TTY / CI skip the prompt and continue
      with no MCPs. Declining writes an empty catalog so the offer does not
      repeat. an organization MCP service publishes a static URL list and
      `mcp_registry` (YAML plus scraped `/metadata` — an MCP of MCPs). Setup may
      consult a reachable registry or already-connected session MCPs; MaaS is not a
      product dependency. Tokens never enter project authority or git. GitHub/`gh`
      and GitLab/`glab` remain the repository tracker
      ([TRACKER-HOST-001](../../roadmap/active-work.md#x-tracker-host-001-detect-github-vs-gitlab-from-git-remotes-and-use-or)).
      Mutagenic verbs: `init`, `update`, `reparent`, `catalog copy`, lock writes,
      `generate`/source admission, rebuilds that write, convert, and `release
      prepare` / `publish` / `advance-default-branch`. Not mutagenic: `help`,
      `version check`, read-only `plan`, `project validate`, tracker inspect,
      probes, documentation-review compute. `release publish` still also comments
      a summary of completed queue items. Jira outage after a successful mutation
      is fail-open with a recorded skip. No associated ticket means skip comments,
      not a new issue per command.
- **Scope boundary:** Do not call MCP tools from every read-only command. Do not
      fail closed when Jira is absent. Do not store secrets in
      `literate.project.json`. Do not post tokens, private prompts, or worker
      hostnames on the ticket.
- **Implementation:**
  - [x] Versioned operator catalog (`mcps.json`) under the config directory.
  - [x] Offer setup when the directory is missing or empty; write empty catalog on
        decline. Agent skill `configure-operator-mcp` owns session MCP discovery;
        the CLI TTY offer is the no-agent fallback.
  - [x] Classify mutagenic vs read-only `litai` verbs once; Jira, Slack, and
        Outlook share it and emit [CHANNEL-VOCAB-001](../../roadmap/active-work.md#x-channel-vocab-001-shared-literate-ai-author-or-recipient-vocabulary-for-jira-slack-and-outlook).
  - [x] Associate Jira Epic/Story/Task only when that MCP is listed and available;
        otherwise skip with a named reason (`skills/agent/associate-release-jira`).
  - [x] Journal each mutagenic command (user, command, project, revision, outcome)
        and have agents comment on the associated major/minor ticket; on `publish`
        also summarize completed queue items
        ([#191](https://github.com/NVIDIA-dev/literate-ai/issues/191)).
- **Evidence:**
  - [x] Focused tests isolate `LITAI_CONFIG_DIR` / non-TTY (no HOME pollution, no
        prompt in CI).
  - [x] Mutagenic success writes an author journal event; read-only commands do
        not; absent catalog file skips journal; Jira MCP posting is the agent skill.
  - [x] Catalog and init-template skill copies remain byte-identical.

### [x] MCP-CATALOG-001 — MCP create, modify, and hygiene as a first-class catalog kind

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#193](https://github.com/NVIDIA-dev/literate-ai/issues/193)
- **Owner:** project catalog, documentation, agent skills
- **ADR:** [0024](../../decisions/0024-project-mcp-catalog-hygiene.md)
- **Direction:** As a project evolves, MCP servers it creates and modifies are a
      fundamental catalog concern — same durability class as Components, Flavors,
      skills, workflows, and routing — not a one-off operator plugin.
- **Conclusion:** Hygiene is identity pins, versioning with the project, create/update
      without a drifting second copy, deprecation, no secrets in repository authority,
      no hidden generation-prompt requirements, and fail-closed auth only at seams
      that need the MCP. A maintainer's personal MCP is not product policy.
- **Scope boundary:** Distinct from operator opt-in
      ([USER-MCP-001](../../roadmap/active-work.md#x-user-mcp-001-operator-local-mcp-catalog-offer-setup-jira-only-when-available)),
      from an embedded MCP inside a generated application
      (`python-service-application`), and from
      [PLUGIN-001](../../roadmap/active-work.md#plugin-001-ship-standardized-coding-cli-plugins-with-every-release)'s later
      CLI-as-MCP adapter (one consumer of this hygiene). Sentinel and schema are
      [ADR 0024](../../decisions/0024-project-mcp-catalog-hygiene.md).
- **Depends on:** [USER-MCP-001](../../roadmap/active-work.md#x-user-mcp-001-operator-local-mcp-catalog-offer-setup-jira-only-when-available)
      for how operators discover and opt into servers.
- **Implementation:**
  - [x] ADR for catalog shape, sentinel, and what "hygiene" rejects.
  - [x] Create/modify path that pins identity the same way skills do
        (`litai catalog copy mcp:`).
  - [x] Init template `mcps/` root and `mcp_roots`; `litai catalog` composition
        for the `mcp` kind.
- **Evidence:**
  - [x] Accepted ADR plus focused tests that secrets, prompt leakage, reserved
        operator ids, and unpinned/duplicate copies fail closed.

### [x] SLACK-NOTIFY-001 — Optional Slack channel for significant mutagenic litai events

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#194](https://github.com/NVIDIA-dev/literate-ai/issues/194)
- **Owner:** `litai` CLI, operator-local config, optional project policy
- **ADR:** [0023](../../decisions/0023-mutagenic-cli-channel-fan-out.md)
- **Direction:** A project may optionally register a Slack channel. After that,
      significant mutagenic `litai` commands run by **any** user post to that channel
      so it becomes institutional knowledge for updates, releases, and other major
      CLI events.
- **Conclusion:** Use the same mutagenic verb set as
      [USER-MCP-001](../../roadmap/active-work.md#x-user-mcp-001-operator-local-mcp-catalog-offer-setup-jira-only-when-available)
      and the [CHANNEL-VOCAB-001](../../roadmap/active-work.md#x-channel-vocab-001-shared-literate-ai-author-or-recipient-vocabulary-for-jira-slack-and-outlook)
      envelope (Literate AI as **author**). Channel id may live in project
      policy; tokens and webhooks stay in `$HOME/.config/literate-ai`. Prefer a Slack MCP
      from the operator catalog when listed and available. Slack outage after a
      successful mutation is fail-open with a recorded skip, not a rollback.
      Unregistered projects send nothing.
- **Scope boundary:** Do not post secrets, tokens, private prompts, or worker
      hostnames. Do not make Slack a mandatory product dependency. Do not notify
      every read-only command. Do not fork a second mutagenic-verb list or a
      channel-specific prefix.
- **Depends on:** [USER-MCP-001](../../roadmap/active-work.md#x-user-mcp-001-operator-local-mcp-catalog-offer-setup-jira-only-when-available)
      for the operator MCP/credential list and the shared mutagenic classifier;
      [CHANNEL-VOCAB-001](../../roadmap/active-work.md#x-channel-vocab-001-shared-literate-ai-author-or-recipient-vocabulary-for-jira-slack-and-outlook)
      for the envelope.
- **Implementation:**
  - [x] Optional project registration of a Slack channel (no secrets in git).
  - [x] Reuse the USER-MCP-001 mutagenic vs read-only classifier.
  - [x] Post a CHANNEL-VOCAB author event when registered; skip with evidence
        when Slack/MCP is unavailable (`associate-release-jira` plus journal).
- **Evidence:**
  - [x] Tests: webhook/token-shaped channel ids are rejected; unregistered
        projects have no `institutional_channels`; mutagenic path journals;
        read-only path does not.

### [x] CHANNEL-VOCAB-001 — Shared Literate AI author or recipient vocabulary for Jira Slack and Outlook

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#195](https://github.com/NVIDIA-dev/literate-ai/issues/195)
- **Owner:** shared channel envelope (Jira comments, Slack, Outlook)
- **ADR:** [0022](../../decisions/0022-channel-author-recipient-vocabulary.md)
- **Direction:** Jira, Slack, and Outlook need one vocabulary so a human or agent
      can tell whether Literate AI **authored** the message or is the **recipient**
      of task information to act on for a named project.
- **Conclusion:** One envelope: stable marker, role (`author` | `recipient`), kind
      (`mutagenic-cli` | `inbound-task` | `publish-summary`), project identity,
      optional command/revision/outcome. Human-readable first line plus a
      parseable trailer. Outbound mutagenic events and publish summaries are
      `author`. Inbound mail (and later Slack/Jira instructions) that should become
      work are `recipient`. `recipient` text is not project authority until
      `record-user-directed-work` records it. Unmarked or spoofed messages are
      ignored. No secrets, tokens, private prompts, or worker hostnames.
- **Scope boundary:** Do not invent per-channel prefixes. Do not execute inbound
      bodies. Schema is [ADR 0022](../../decisions/0022-channel-author-recipient-vocabulary.md).
      GitHub/`gh` and GitLab/`glab` stay the repository tracker.
- **Depends on:** none
- **Implementation:**
  - [x] Specify the envelope (fields, first line, trailer) and reject secret-shaped
        payloads.
  - [x] Formatters for Jira comment, Slack post, and Outlook subject/body share it.
  - [x] Parser for inbound `recipient` messages used by Outlook (then Slack/Jira).
- **Evidence:**
  - [x] Round-trip tests: author mutagenic event and recipient inbound-task parse
        on all three channel shapes; unmarked text is not admitted.

### [x] OUTLOOK-MAIL-001 — Outlook MCP for status mail and inbound project work

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#196](https://github.com/NVIDIA-dev/literate-ai/issues/196)
- **Owner:** `litai` CLI, operator-local config, Outlook MCP
- **ADR:** [0023](../../decisions/0023-mutagenic-cli-channel-fan-out.md)
- **Direction:** Outlook is a first-class operator MCP. Generate status-update
      mail for significant mutagenic `litai` commands, and accept inbound mail that
      tells Literate AI to do work on a given project.
- **Conclusion:** Same gating as Jira: listed in `$HOME/.config/literate-ai` **and**
      connected/available. Outbound mail uses
      [CHANNEL-VOCAB-001](../../roadmap/active-work.md#x-channel-vocab-001-shared-literate-ai-author-or-recipient-vocabulary-for-jira-slack-and-outlook)
      as **author** and the USER-MCP-001 mutagenic verb set. Inbound mail with
      Literate AI as **recipient** plus a project identity is queued through
      `record-user-directed-work`, not executed from the body. Authenticate via
      the Outlook MCP mailbox; unmarked mail is ignored. MaaS ships an `outlook`
      server; MaaS is not required. Tokens stay operator-local. Outage after a
      successful mutation is fail-open.
- **Scope boundary:** Do not make Outlook mandatory. Do not treat email as
      specification or lock authority. Do not auto-send to arbitrary addresses
      without project registration (to/from allowlist).
- **Depends on:** [USER-MCP-001](../../roadmap/active-work.md#x-user-mcp-001-operator-local-mcp-catalog-offer-setup-jira-only-when-available),
      [CHANNEL-VOCAB-001](../../roadmap/active-work.md#x-channel-vocab-001-shared-literate-ai-author-or-recipient-vocabulary-for-jira-slack-and-outlook)
- **Implementation:**
  - [x] Optional project registration of Outlook to/from (no secrets in git).
  - [x] Send CHANNEL-VOCAB author mail on mutagenic commands when Outlook is
        available (journal plus `associate-release-jira`).
  - [x] Receive `recipient` mail, parse the envelope, record a queue item
        (`skills/agent/ingest-channel-work` from an interactive session). There is
        no mailbox poller or drain daemon.
- **Evidence:**
  - [x] Tests: unavailable Outlook is skip-by-catalog; mutagenic send uses the
        author envelope; inbound unmarked mail is ignored; inbound recipient mail
        parses and the ingest skill forbids mutating catalog authority.

### [x] WEBMCP-001 — WebMCP as a fundamental front-end skill

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#198](https://github.com/NVIDIA-dev/literate-ai/issues/198)
- **Owner:** specification-to-source skills, MCP catalog kind, front-end generation
- **Direction:** Add [WebMCP](https://github.com/webmachinelearning/webmcp) as a
      fundamental skill for building front-ends. WebMCP exposes in-page tools
      (JavaScript functions or HTML elements) for agents; treat it as MCP in the
      browser, not a second protocol.
- **Conclusion:** The WebMCP skill/Component inherits from the MCP
      skill/Component. Enhance the MCP parent as needed so operator-local
      `~/.config/literate-ai` servers, project `mcps/<id>/mcp.md`, embedded application
      MCP, and WebMCP share one parent and stay distinct at the leaves. Do not
      put WebMCP in generation prompts as a hidden operator-MCP requirement.
- **Depends on:** [MCP-CATALOG-001](../../roadmap/active-work.md#x-mcp-catalog-001-mcp-create-modify-and-hygiene-as-a-first-class-catalog-kind)
      (landed). Pair with [FRONTEND-001](../../roadmap/active-work.md#x-frontend-001-fundamental-front-end-component-and-skill-base)
      and [BACKEND-001](../../roadmap/active-work.md#x-backend-001-fundamental-back-end-skill-indexed-off-python-rust-and-elixir-flavors).
- **Implementation:**
  - [x] Author a nested `specification-to-source` WebMCP skill (catalog + init
        template, byte-identical) that inherits the MCP parent.
  - [x] Enhance the MCP parent skill/Component so WebMCP can inherit without
        duplicating hygiene, identity pins, or secret rejection.
- **Evidence:**
  - [x] `make skills-check` (LITAI_SESSION_ID=dev): SkillEvaluator Tier 1 pass for
        `mcp-application` and nested `webmcp` plus catalog/template copies.
        `assert_generation_skills_are_mcp_free` and
        `generation_skill_requires_operator_mcp` still reject `~/.config/literate-ai`.
  - [x] `tests.smoke.test_app_stack_skills.AppStackSkillCatalogTests`: WebMCP pins
        the MCP parent identity and fails closed without it; operator catalog
        ids are not product authority.

### [x] FRONTEND-001 — Fundamental front-end Component and skill base

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#199](https://github.com/NVIDIA-dev/literate-ai/issues/199)
- **Owner:** Component catalog, `lang-javascript` / React / WebMCP skills
- **Direction:** Develop a fundamental (base class) front-end in JavaScript +
      React or WebMCP, plus a fundamental (base class) skill. React dashboard
      and WebMCP skills are deltas of that parent, not one-off samples.
- **Conclusion:** This is the reusable UI parent. Settle axis composition with
      [FLAVOR-007](../../roadmap/active-work.md#flavor-007-add-a-flavor) and npm
      capability with [FLAVOR-JS-NPM-001](../../roadmap/active-work.md#x-flavor-js-npm-001-javascript-flavor-has-no-npm-dependency-capability).
      A UI Component kind remains [COMPONENT-KIND-002](../../roadmap/active-work.md#x-component-kind-002-additional-component-subclass-candidates).
      Acceptance stays evidence-bound ([ACCEPTANCE-RENDER-001](../../roadmap/active-work.md#x-acceptance-render-001-lint-and-render-stability-oracle-for-hand-authored-frontends)).
- **Depends on:** [WEBMCP-001](../../roadmap/active-work.md#x-webmcp-001-webmcp-as-a-fundamental-front-end-skill)
- **Implementation:**
  - [x] Author the parent front-end skill/Component; nest React and WebMCP as
        deltas. `ui-react` occupies `implementation.ui-framework` and
        `lang-javascript-react` remains an input alias.
  - [x] Keep Windows-portable paths and do not special-case one sample in the
        harness.
- **Evidence:**
  - [x] `FilesystemComponentLockPlanner` rejects the front-end parent with
        `+python` and rejects `+ui-react` without JavaScript
        (`component_lock.flavor_target_unsatisfied`).
  - [x] Nested skills are deltas; catalog and init-template copies are
        byte-identical (`test_catalog_and_template_copies_are_byte_identical`,
        `test_nested_skills_are_deltas`). FLAVOR-007 live generate/build/accept
        remains open.

### [x] FRONTEND-002 — Browser-instrumented frontend verification

- **Priority:** P0
- **GitHub issues:** [#64](https://github.com/NVIDIA-dev/literate-ai/issues/64),
      [#134](https://github.com/NVIDIA-dev/literate-ai/issues/134)
- **Owner:** front-end specification-to-source skill and agent verification skills
- **Direction:** A generated dashboard passed build, generated tests, and independent
      text probes while omitting most of its specified information architecture and
      displaying invalid numeric values. Make browser inspection a reusable frontend
      practice rather than a downstream project's ad hoc recovery step.
- **Conclusion:** The front-end parent owns instrumentability and minimum rendered-UI
      assertions. A separate agent skill owns authorized browser execution because a
      generation prompt cannot grant itself host execution. Prefer Playwright when it is
      already available, but specify browser-observable evidence rather than making one
      package mandatory. Existing hash-only render acceptance remains useful but is not
      sufficient evidence of responsive structure or interaction behavior.
- **Depends on:** [FRONTEND-001](../../roadmap/active-work.md#x-frontend-001-fundamental-front-end-component-and-skill-base),
      [ACCEPTANCE-RENDER-001](../../roadmap/active-work.md#x-acceptance-render-001-lint-and-render-stability-oracle-for-hand-authored-frontends)
- **Next action:** Complete. Downstream projects can inherit the generation guidance and
      follow `skills/agent/verify-frontend-browser/SKILL.md` after execution authorization.
- **Implementation:**
  - [x] Extend `frontend-application` with stable browser-observable landmarks, semantic
        states, finite-value rendering, responsive overflow, and interaction invariants.
  - [x] Add an operator-side browser verification skill that captures desktop and mobile
        screenshots, console/page failures, structure, overflow, and specified interactions.
  - [x] Keep React dashboard guidance a compact delta and update every exact parent pin.
- **Evidence:**
  - [x] Catalog and project-template copies are byte-identical; exact dependency pins
        resolve in the initialized catalog.
  - [x] `tests.smoke.test_app_stack_skills`,
        `tests.e2e.test_project_initialization_adapter` (77 tests), and
        `tests.conformance.test_sample_acceptance_interfaces` (6 tests) pass.
  - [x] `make skills-check` admits every changed or added skill; browser verification
        scores B/88.5. `make lint`, `make format-check`, and `litai project validate` pass.

### [x] BACKEND-001 — Fundamental back-end skill indexed off Python, Rust, and Elixir Flavors

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#200](https://github.com/NVIDIA-dev/literate-ai/issues/200)
- **Owner:** specification-to-source skills, language Flavors
- **Direction:** Develop a fundamental back-end skill that knows the Component
      ecosystems for Python, Rust, and Elixir, indexed off those Flavors when
      selected.
- **Conclusion:** Flavor selection is the index: Python/Rust guidance applies
      only when that language Flavor is selected. Elixir is the same rule; if
      `lang-elixir` is absent, the skill records skip/unavailable for that
      ecosystem rather than inventing a Flavor in this item. WebMCP inherits
      MCP; this back-end parent owns server-side MCP/service ecosystems.
- **Depends on:** [WEBMCP-001](../../roadmap/active-work.md#x-webmcp-001-webmcp-as-a-fundamental-front-end-skill)
      (MCP parent enhancement).
- **Implementation:**
  - [x] Author the parent back-end skill; contribute ecosystem chapters from
        selected `lang-python` / `lang-rust` Flavors. Missing `lang-elixir` is a
        named skip; no Elixir Flavor was invented.
  - [x] Keep `python-service-application` a delta of this parent where that
        reduces duplication.
- **Evidence:**
  - [x] `index_backend_ecosystems` injects Python or Rust when selected, omits
        the unselected chapter, and records
        `("elixir", "lang-elixir Flavor is not in the catalog")`. Recipe
        assembly drops omitted nested skills
        (`BackendEcosystemIndexTests`).

### [x] SAMPLE-APP-STACK-001 — Samples for WebMCP, front-end base, and back-end skill

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#201](https://github.com/NVIDIA-dev/literate-ai/issues/201)
- **Owner:** `samples/`, sample conformance runner
- **Direction:** Create samples for all of the above as peers of the current
      samples, with the same default sample settings.
- **Conclusion:** [SAMPLE-MATRIX-002](../../roadmap/active-work.md#x-sample-matrix-002-bound-default-sample-execution-and-make-flavor-fanout-explicit)
      stays: unpinned samples run exactly `lang-python` + `build-make` + host OS.
      Samples that must exercise WebMCP/React/JS pin those Flavors explicitly.
      Do not special-case one sample in the harness; extend
      `persistent-service` / `web-application` support if the new samples need
      it ([SAMPLE-PORTFOLIO-002](../../roadmap/active-work.md#x-sample-portfolio-002-close-the-two-confirmed-breadth-gaps-found-in-the-051-sample-audit)).
- **Depends on:** [WEBMCP-001](../../roadmap/active-work.md#x-webmcp-001-webmcp-as-a-fundamental-front-end-skill),
      [FRONTEND-001](../../roadmap/active-work.md#x-frontend-001-fundamental-front-end-component-and-skill-base),
      [BACKEND-001](../../roadmap/active-work.md#x-backend-001-fundamental-back-end-skill-indexed-off-python-rust-and-elixir-flavors)
- **Implementation:**
  - [x] Add peer sample directories under `samples/` (`sample: true`, same slot
        shape as existing peers unless an explicit pin is required):
        `backend-base`, `frontend-base`, `webmcp-page`.
  - [x] Wire harness entrypoint kinds without a one-off exception
        (`SAMPLE_HARNESS_ENTRYPOINT_KINDS` admits `portable-application`,
        `persistent-service`, and `web-application`).
- **Evidence:**
  - [x] Unpinned language lists still default to `("python",)`
        (`test_unpinned_languages_default_to_python`); `backend-base` uses
        `sample.portable-app` slots.
  - [x] `+lang-javascript` / `+ui-react` stay JavaScript; `lang-javascript-react`
        is a UI alias, not a language pin
        (`test_explicit_javascript_pin_stays_javascript`).
  - [x] Focused tests: `tests.smoke.test_app_stack_skills` (16 tests) plus
        flavor-markdown, skill-routing, schema, project-MCP, and wheel
        package-data checks. Harness-gap: no `samples/_harness/<id>/sample.json`
        for the new peers (same as python-service-example); live `make samples`
        still needs model-egress acknowledgement and SAMPLE-PORTFOLIO-002
        execution.json/oracles.

### [x] MCP-CLI-001 — litai posts to operator-catalog MCPs; discover flag off by default

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#202](https://github.com/NVIDIA-dev/literate-ai/issues/202)
- **Owner:** `litai` CLI, operator-local MCP catalog, agent skills
- **ADR:** [0025](../../decisions/0025-cli-operator-mcp-client.md)
- **Direction:** `litai` must talk to MCPs listed in `~/.config/literate-ai/mcps.json`
      so mutagenic events are not missed when no coding session is attached.
      Add a CLI flag for MCP discovery that is off by default. When a session
      uses `litai` to do the work, remove those MCPs from session skills so
      posting is not double-entered. Keep operator, project, embedded, and
      WebMCP seams distinct. Teach the official MIT Python module `mcp`
      (modelcontextprotocol/python-sdk) as the library for this process and
      for generated Python MCP servers.
- **Conclusion:** CLI journals and fan-outs. `--discover-mcps` probes; it does
      not write secrets. `associate-release-jira` associates and records
      `institutional_channels.jira_issue`; it does not re-post envelopes
      `litai` already sent. Inbound ingest stays an agent skill (no poller).
- **Depends on:** [USER-MCP-001](../../roadmap/active-work.md#x-user-mcp-001-operator-local-mcp-catalog-offer-setup-jira-only-when-available)
      (landed).
- **Implementation:**
  - [x] Bounded operator-MCP transport (stdio JSON-RPC using catalog `command`;
        official `mcp` is optional extra `literate-ai[mcp]`, not a wheel dep).
  - [x] Global `--discover-mcps` default off.
  - [x] Fan-out after mutagenic journal; fail-open.
        Stdio MCP spawn binds `create_process_tree_ownership` (PROC-KILL-001).
  - [x] Agent skills wrap `litai` and forbid duplicate channel posts.
  - [x] Unittest/pytest isolate `LITAI_CONFIG_DIR` and set
        `LITAI_MCP_TRANSPORT=off` so `make python-check` does not spawn the
        operator's `~/.config/literate-ai/mcps.json` or fail CLI tests that assert
        empty stderr.
- **Evidence:**
  - [x] Fake-transport tests: listed Jira/Slack/Outlook post; missing command
        or tool skips; `--discover-mcps` off does not probe; flag on probes.
  - [x] Catalog and init-template agent skills stay byte-identical.
  - [x] `test_project_policy_can_disable_model_source_intelligence` no longer
        sees `Literate AI skipped MCP notify` on stderr.

### [x] MCP-SDK-001 — Liberal-license MCP SDKs in the generation skill by selected Flavor

- **Priority:** P0
- **Release target:** 0.8.0 (break-glass major-equivalent)
- **GitHub issue:** [#203](https://github.com/NVIDIA-dev/literate-ai/issues/203)
- **Owner:** `skills/specification-to-source/python-service-application` (MCP
      parent section) and language Flavor gating
- **Direction:** Enhance the existing embedded-application MCP skill to know
      popular liberal-license (no GPL) MCP implementations for every currently
      supported language, **only when that Flavor is selected**.
- **Conclusion:** Official org SDKs: Python `mcp`, TypeScript/JS
      `modelcontextprotocol/typescript-sdk`, Go `go-sdk`, Rust `rust-sdk`,
      Swift `swift-sdk`. C++ has no official SDK; cite an Apache-2.0 community
      option only if the license is still Apache-2.0. Do not add these
      libraries to the `litai` wheel. Do not mention GPL implementations.
- **Depends on:** [MCP-CLI-001](../../roadmap/active-work.md#x-mcp-cli-001-litai-posts-to-operator-catalog-mcps-discover-flag-off-by-default)
- **Implementation:**
  - [x] Flavor-conditional SDK table in the MCP generation skill.
- **Evidence:**
  - [x] Skill text names the SDK only under the matching language Flavor.
  - [x] `make skills-check` passes.

### [x] CLI-001 — Make help a scoped first-class verb

- **Owner:** framework CLI
- **Direction:** Provide `litai help`, and allow `help` after every command path so its
  position narrows the displayed scope.
- **Conclusion:** Support top-level, prefix, conventional `--help`, and canonical trailing
  forms such as `litai project validate help`, including the global JSON contract.
- **Evidence:** Six focused unit tests passed; installed-wheel coverage was added;
  implementation committed and pushed as `e759868`.

### [x] INIT-001 — Admit harmless existing Git bootstrap state

- **Owner:** framework project initialization
- **Direction:** `litai init` must not reject files created by `git init` or an existing
  starter `README.md`; it must still reject source until explicit adoption exists. The
  completed initialization must also introduce the optional private test-matrix fanout
  and tell users where to provide their own SSH worker assignments.
- **Conclusion:** Preserve a regular `.git/` directory and regular root `README.md`
  byte-for-byte. Reject every other existing entry before mutation and point to the
  future explicit `litai init --adopt` workflow. Generate provider-neutral matrix
  guidance and an ignored local configuration example; never embed worker identities in
  the framework or initialized project.
- **Depends on:** INTRINSIC-001 (recording mechanism may land in the same checkpoint)
- **Implementation:**
  - [x] Implement the narrow bootstrap-state admission boundary.
  - [x] Add adapter and CLI tests for preservation, source rejection, and unsafe entries.
  - [x] Add derived-project documentation, including private test-matrix setup and
    fanout commands.
  - [x] Prove initialized Git-ignore rules exclude the user-owned matrix configuration.
  - [x] Add installed-wheel proof.
- **Evidence:**
  - [x] Five focused initialization tests pass on macOS.
  - [x] The 65-test initialization/CLI/help suite passes on macOS except for the
    expected root documentation-review refresh performed after this authority update.
  - [x] Clean `make wheel-check` passes at `fd199c1`, including initialized onboarding,
    matrix guidance, validation, lock, and plan from the installed wheel.

### [x] FLAVOR-002 — Add `openscad` domain Flavor to openstl-generator; re-init correctly

- **Owner:** `~/Src/openstl-generator` (project-local Flavor, not a literate-ai built-in)
- **Direction:** The openstl-generator project was initialized with only `+macos` and
  no language or build-system Flavor, so the enclosure component's
  `openscad-parametric-enclosure` skill has no Flavor context and `litai lock` would
  fail on any component that declared language or build-system slots. OpenSCAD is a
  domain-specific language+compiler and should be represented as a Flavor on the
  `implementation.language-ecosystem` axis within the project.
- **Conclusion:** After FLAVOR-001 ships (so `--flavor make` is valid), re-init or
  update openstl-generator with `--flavor openscad --flavor make --flavor macos`.
  Author `flavors/openscad/flavor.md` and `flavors/openscad/openspec/spec.md` as
  project-local Flavor files (not shipped by literate-ai init).
  **Completed 2026-08-30** on `feat/flavor-002-openscad` (`ce4df48`, lineage mutex
  `cd24d0d`). Python still emits `.scad`; OpenSCAD is a second language-ecosystem
  Flavor (`one-or-more`) for `.scad` → `.stl` via `openscad -o`. There is no
  `components/esp32-enclosure`; the lock target is
  `components/openscad-enclosure-generator`. Not pushed.
- **Depends on:** FLAVOR-001 (`+make` must exist before this init is valid)
- **Implementation:**
  - [x] Author `flavors/openscad/flavor.md` — primary_axis
        `implementation.language-ecosystem`, target `openscad`, provides
        `implementation.language.openscad`, contributions the
        `openscad-parametric-enclosure` skill.
  - [x] Author `flavors/openscad/openspec/spec.md` — spec for the OpenSCAD toolchain
        (`.scad` → `.stl` via `openscad -o`).
  - [x] Update `components/openscad-enclosure-generator/component.md` flavor_slots
        to declare language-ecosystem (`one-or-more`: python + openscad) and
        `build.system` (make).
  - [x] Update `literate.project.json` selectors to
        `["+python", "+openscad", "+make", "+macos"]`.
  - [x] Confirm `litai verify` passes and
        `litai lock components/openscad-enclosure-generator` succeeds.
- **Evidence:**
  - [x] `litai lock components/openscad-enclosure-generator --target host --check`
        is current
        (`sha256:bf018e1391a6bf06a3c71460806a5a36af92862c76d723f972fa151a7e5e6085`).
        Language slot python + openscad; build-system make; os macos.
  - [x] `litai verify` reports no FAIL: authority pass, locks pass,
        source-intelligence skipped (`provider none`), receipt skipped.

---

### [x] INIT-002 — `litai init` must require explicit project shape before scaffolding

- **Owner:** framework project initialization (`src/literate_ai/adapters/project_initialization.py`,
  `src/literate_ai/cli/project.py`)
- **Direction:** `litai init` on a genuinely empty directory currently silently applies
  `default_flavor_selectors = ["+bazel", "+python", <host-os>]` regardless of what the
  project is. An AI-to-OpenSCAD-to-STL project, a firmware project, a pure documentation
  generator, or a component library gets the same Python/Bazel defaults — which are
  wrong, misleading, and cause every downstream gate (`litai lock`, `litai verify`,
  `litai plan`) to fail or produce irrelevant results. The user should declare project
  shape upfront; the framework must not invent it.
- **Conclusion:** Flavor shape is explicit-or-smart-defaulted: FLAVOR-001 superseded the
  original required-`--flavor` diagnostic. `litai init PATH` remains valid and stamps
  Python, GNU Make, pip, and the host OS unless `--flavor` overrides an axis. Remaining
  work is optional `--type` persisted as `project_type` (default `application`, which
  keeps the hello starter). Unknown types fail closed. Non-starter types skip hello
  without making `--type` or `--flavor` mandatory. Do not break current init UX.
- **Depends on:** none (no dependency on INIT-003; these are independent)
- **Design notes:**
  - Minimum viable interface: `litai init --flavor python --flavor macos` installs only
    python + macos Flavor files and sets `default_flavor_selectors=["+python", "+macos"]`.
  - `--type` (or `--kind`) declares application identity: `application`, `library`,
    `component-only`, `full-stack`, `document-generator`, `firmware`, `open-ended`.
    Controls which starter Component template(s) are created and which workflow/routing
    stubs are included.
  - Unknown `--flavor` values should suggest the closest known axis value and exit;
    they must never silently fall back to a standard Flavor.
  - Existing `--empty` flag is compatible: suppress starter Components regardless of
    declared type.
  - `litai help init` must list all valid Flavor axis values from the installed catalog.
- **Implementation:**
  - [x] Add optional `--type` (not required). Repeatable `--flavor` already has
        structured missing/unknown diagnostics and scoped help; FLAVOR-001 smart
        defaults remain when `--flavor` is omitted.
  - [x] Persist and apply `project_type` (default `application`, omitted from existing
        manifests). Unknown types fail closed. Smart Flavor defaults still fill uncovered
        axes; do not require caller-provided selectors.
  - [x] Filter `_TEMPLATE_FILES` and `_STARTER_TEMPLATE_FILES` to install only the
        Flavor files matching the declared selectors; install cross-cutting files
        (skills, docs, routing, workflow stubs) unconditionally.
  - [x] Emit a structured diagnostic (same JSON envelope as other errors) when
        `--flavor` is absent or unknown, listing the known Flavor axis → values map.
  - [x] Update `litai help init` to describe `--type`; explicit `--flavor` help is
        implemented.
  - [x] Update initialization tests to supply selectors and prove missing/unknown Flavor,
        required starter axes, selective installation, and no-build-system operation.
  - [x] Update the installed-wheel smoke test to pass at least `--flavor python
        --flavor macos` and verify no Bazel/JS/Rust/C++ Flavor files are created.
- **Evidence:**
  - [x] `litai init` without `--flavor` applies smart defaults (Python, GNU Make, pip,
        host OS) rather than failing; unknown `--flavor` still fails closed.
  - [x] CLI `litai init --empty --flavor python --flavor macos` fills remaining axes
        but does not install bazel/javascript/rust/cpp Flavor directories.
        Direct adapter `flavor_selectors=("+python","+macos")` with `--empty` installs
        only those two. `test_init_python_macos_does_not_install_unselected_flavors`;
        `scripts/wheel_smoke.py` scoped-shape init.
  - [x] `litai verify` and the initialization lock pass on the shape-declared project
        without false positive failures from irrelevant Flavors.
  - [x] Optional `--type` default `application` keeps hello; `--type library` skips it.
        Unknown types fail `project.init_type_unknown`.
        Focused init/CLI/help tests pass under `LITAI_SESSION_ID=dev`.

---

### [x] INIT-003 — `litai init --convert`: LLM-assisted adoption of an existing repo

- **Owner:** `skills/agent/convert-project/SKILL.md` (agent skill) +
  `src/literate_ai/adapters/project_initialization.py` (Python harness)
- **Direction:** `litai init --convert` is an **LLM-assisted** process, not a
  mechanical Python script. The Python harness handles scaffolding — detecting language
  indicators, creating catalog directories, merging `.gitignore`, skipping existing
  files, and writing `literate.project.json`. But the intelligence lives in a
  `skills/agent/convert-project/SKILL.md` agent skill that guides the LLM agent to:
  survey the existing architecture, map modules/packages to literate-ai Components,
  derive `component.md` specs from observed code behavior and tests, identify reusable
  conversion patterns to encode as durable skills, and create any project-local Flavors
  the domain requires. This is the inverse of the normal literate-ai flow
  (spec → code); for conversion it is: code + docs → spec authority. The pattern is
  analogous to `skills/source-to-specification/` but covers the full project rather than
  one Component at a time.
- **Conclusion:** Two-layer architecture:
  1. **Python harness** (`--convert` flag on `litai init`): scans file types and
     manifests to infer `--flavor` selectors; creates `literate.project.json`, catalog
     directories, and net-new authority files; skips all pre-existing files; merges
     `.gitignore` entries; guards against double-conversion.
  2. **Agent skill** (`skills/agent/convert-project/SKILL.md`): the LLM reads the
     existing project's code, tests, and docs; derives Component specifications that
     capture observable behavior as authority; creates Flavors for domain-specific
     toolchains; records the conversion plan in `docs/roadmap/active-work.md`; never
     invents behavior not evidenced in the existing source.
  After the Python harness runs, the agent follows the conversion skill to complete the
  authority layer. The harness creates the empty catalog; the skill fills it with
  durable specification authority.
- **Depends on:** INIT-002 (harness reuses `detect_repo_flavors` and
  `_apply_init_flavor_defaults`); the harness is partially implemented (see below).
- **Design notes:**
  - **Python harness (partially shipped):** `--convert` flag exists; CONVERT-FW-002
    quarantines pre-existing content; CONVERT-FW-009 omits host-local environments
    from the baseline copy and fails closed on environment-bound recipes, including
    through Make prerequisite closure. Partial-init recovery is shipped: resume
    when `.literate/initialization-baseline.json` exists without
    `literate.project.json`. Integration test is
    `test_convert_python_make_repo_validates_and_admits_derived_spec`.
    `~/Src/pythonos` already has `literate.project.json` (convert is
    `project.already_initialized`); further lift is spec-merge, not a second
    `--convert`.
  - **Agent skill (authored):** `skills/agent/convert-project/SKILL.md` covers
    inspect → quarantine → baseline → shim → lift, and points already-managed trees
    at `litai spec merge`. Remaining evidence is skill validation plus a derived
    `component.md` from a real or synthetic existing repo.
  - **Spec derivation principle:** a converted Component's `component.md` should read
    as if written before the code existed. It names the objective, public interface,
    invariants, errors, and acceptance criteria — all derivable from tests and docs —
    without referencing specific function names, file paths, or internal state.
  - **Partial init recovery:** if `.literate/initialization-baseline.json` exists but
    `literate.project.json` does not, `--convert` should complete the interrupted
    scaffold rather than refusing.
- **Implementation:**
  - [x] Python harness: `detect_repo_flavors()`, `_merge_gitignore()`, `--convert`
        flag, skip-existing logic, `project.already_initialized` guard, 3 unit tests.
  - [x] Author `skills/agent/convert-project/SKILL.md` with the survey → scope →
        derive → record workflow and the spec-derivation principle. CONVERT-FW-002
        replaced skip-existing with quarantine; the skill documents that protocol
        and points already-managed trees at `litai spec merge`.
  - [x] Partial-init recovery: detect `.literate/initialization-baseline.json` without
        `literate.project.json` and resume scaffold writing without re-quarantining.
  - [x] Integration test: run `--convert` on a synthetic Python+Make repo, verify
        `litai project validate` passes, then follow the conversion skill to derive a
        `component.md` from the existing source.
        `test_convert_python_make_repo_validates_and_admits_derived_spec`.
  - [x] Run `litai init --convert` on `~/Src/pythonos` with the agent following
        `skills/agent/convert-project/SKILL.md` to produce authority specs.
        Already converted (`literate.project.json`,
        `components/pythonos-core/component.md`). Do not re-run `--convert`.
- **Evidence:**
  - [x] `litai init --convert` on an existing project preserves pre-existing files,
        merges `.gitignore`, and creates `literate.project.json`.
  - [x] `litai init --convert` on a directory with `literate.project.json` exits with
        `project.already_initialized`.
  - [x] SkillEvaluator `--no-llm` admits `skills/agent/convert-project` after the
        spec-merge pointer (`make skills-check`).
  - [x] `skills/agent/convert-project/SKILL.md` passes `litai project validate`.
        Framework `python-check` 2026-08-29 includes repository validation; the
        convert integration test re-validates a converted tree.
  - [x] An agent following the conversion skill derives `component.md` specs for
        `~/Src/pythonos` that pass `litai verify` and contain no implementation details.
        `components/pythonos-core/component.md` is the derived authority (objective,
        public interface, no `app.py`-style implementation paths). Re-running
        `litai verify` on that checkout is pythonos-owned, not this framework cut.

---

### [x] ENV-001 — Isolate managed Python environments across parallel agents

- **Owner:** contributor bootstrap / build-cache lifecycle
- **Direction:** No framework command may create, replace, or install into a shared root
  `.venv`. Parallel agents and worktrees need independent managed environments beneath
  the disposable build boundary so one run cannot delete another run's interpreter.
- **Conclusion:** Default `PYTHON_ENV` beneath `_build`/`OBJ_DIR`, keyed by an explicit
  session identity with a collision-resistant Make-invocation fallback. Preserve an
  explicit `PYTHON_ENV` override, but treat root `.venv` only as user-owned local state.
- **Depends on:** CACHE-002's `_build` boundary
- **Implementation:**
  - [x] Add a portable session key contract and validate it before constructing paths;
    never interpolate arbitrary identity text into a filesystem path.
  - [x] Make default Make/bootstrap environments live at
    `OBJ_DIR/python-envs/<session-key>` and keep every stamp inside that environment.
  - [x] Ensure nested release-gate Make invocations inherit the parent `PYTHON_ENV`;
    direct CLI tests, remote workers, wheel smoke tests, and coding-agent instructions
    continue to create or inherit their own explicitly bounded sessions.
  - [x] Remove documentation and skills that recommend framework-managed root `.venv`;
    retain compatibility only for an explicit operator override.
  - [x] Add concurrent-process tests proving two sessions can bootstrap, test, and clean
    without deleting, replacing, locking, or importing from one another's environment.
- **Evidence:**
  - [x] Repository tests and two simultaneous fresh bootstraps never create or mutate
    root `.venv`, and cleaning one session cannot affect the other session's interpreter.
  - [x] Eleven focused Make/bootstrap tests prove safe default/explicit session keys,
    `_build/python-envs/<session>` placement, explicit `PYTHON_ENV` compatibility, and a
    clean path that uses the system interpreter rather than deleting its active venv;
    the recursive-Make proof requires child gates to reuse the exact parent environment.
    A 48-test cache/bootstrap suite additionally runs two session bootstraps concurrently,
    probes both isolated interpreters, removes transient object state with `clean`, and
    proves both interpreters remain intact. Both shipped derived-project layout skills
    pass SkillEvaluator after adopting the same invariant.

### [x] LINEAGE-DEADLINE-001 — Bound slow exact Git fetches with explicit policy

- **Priority:** P0
- **GitHub issue:** [#122](https://github.com/NVIDIA-dev/literate-ai/issues/122)
- **Owner:** repository-lineage Git transport policy and CLI diagnostics
- **Direction:** A valid authenticated shallow exact-parent fetch takes 138.452 seconds,
  beyond the generic 120-second process deadline, while cache warming is not acceptable
  qualification evidence.
- **Conclusion:** Keep exact revision and descendant stream custody unchanged, but give
  lineage fetches a deterministic bounded policy with separate total, observable
  no-progress, and SSH-connect limits. Validate operator overrides within fixed
  framework bounds, identify the selected policy and provenance in deterministic CLI
  evidence, terminate the complete process tree on either deadline, and keep invalid
  repositories bounded without mutating Git configuration or depending on ambient cache.
- **Depends on:** `LINEAGE-STREAM-001` process-tree and output-stream custody
- **Completion evidence:** [PR #123](https://github.com/NVIDIA-dev/literate-ai/pull/123)
  passed all fifteen required checks on Linux, macOS, and Windows at final implementation
  head `1ffe2e05cf2432b6325f0da4dfa18160104bb8fc`.
- **Implementation:**
  - [x] Add a typed deadline policy with safe defaults and validated minimum/maximum
        bounds, plus explicit CLI overrides for init, update, and reparent.
  - [x] Observe forced Git fetch progress, separate SSH connection/no-progress/total
        deadlines, and retain bounded output plus complete child cleanup.
  - [x] Record policy identity and default/CLI provenance in command evidence and
        actionable timeout diagnostics without persisting repository locators.
  - [x] Document the policy, exact invocation, and trust/resource boundary; update
        schema catalog, skills, changelog, and reviewed authority markers.
- **Evidence:**
  - [x] An injected clock/process fixture proves a valid 138.452-second fetch succeeds
        below policy while over-bound work fails closed and cleans its process tree.
  - [x] Invalid policy, unreachable repository, exact revision/descendant custody,
        shallow file/SSH transports, Windows/Linux cleanup, and deterministic
        evidence/diagnostic regressions pass.
  - [x] A cold exact Physics Workbench sample parent fetch of
        `06681665e8382f3013cb35c6b92289b35e532dc5` succeeds under the selected policy.
  - [x] Full required cross-platform CI passes on the reviewable pull request before
        merge; downstream matrix qualification remains explicitly out of scope.

  The focused policy, shallow file transport, exact-revision, descendant-stream, and
  portable process-tree suite passes 21 tests. A new empty `OBJ_DIR` then resolved the
  exact authenticated SSH parent and produced the read-only Physics Workbench sample reparent plan in
  63.16 seconds with policy identity
  `sha256:56746fe13c3058280d7ad21b62fd9eadb26457f89ff159b53ca422d1cbad653b`;
  no pre-fetch or cache warming occurred. The injected clock retains the original
  138.452-second regression independent of current network speed.

### [x] TEST-PUBLIC-001 — Prefer public-API tests; remove private, trivial, and call-sequence coverage

- **Priority:** P0
- **Owner:** `tests/unit/`, `tests/conformance/`, and any skill or architecture note
      that documents how this repository tests
- **Direction:** Prioritize observable behavior through public APIs over individual
  methods or private implementation. Keep API contract tests (schemas, status/exit
  codes, documented errors, auth, backward compatibility), API-level component tests
  through the public interface with real internals and realistic persistence, complete
  workflows, and high-risk boundaries. Parameterize related inputs. Add method-level
  tests only when isolated logic is complex, safety-critical, algorithmically subtle,
  or substantially easier to diagnose independently. Do not keep tests merely for
  coverage count. Remove tests that duplicate the same behavior at multiple layers,
  assert internal call sequences, test trivial getters or wrappers, or depend heavily
  on mocks of internals. Each remaining test must name the distinct contract, failure
  mode, boundary, or regression it protects.
- **Conclusion:** In this repository the public surfaces are the `litai` CLI, published
  JSON schemas and typed wire contracts, public module functions/classes (no leading
  underscore), and stage-zero script stdout JSON such as host-bootstrap `main()`. Mock
  only true external boundaries (network, host package managers, NTP, sibling
  processes). Keep fail-closed security, isolation, schema-immutability, and
  algorithmically subtle helpers (PATH-first discovery, semantic-diff bounds, process-
  tree kill, checksum pins) even when the helper is private. Delete the rest.
- **Depends on:** none. Orthogonal to TEST-CACHE-001's checkpoint identity work.
- **Implementation:**
  - [x] Rewrite `tests/unit/test_host_bootstrap.py` through `main()` JSON; drop private
        helper and duplicated argv assertions.
  - [x] Apply the same keep/remove bar to every other module under `tests/unit/` and
        `tests/conformance/`.
  - [x] Record the user-facing suite contract in `CHANGELOG.md`.
- **Evidence:**
  - [x] Host-bootstrap tests exercise readiness, clock-sync, discovery, and install
        selection only through the JSON report and documented exits. 24 tests in
        `tests.unit.test_host_bootstrap` pass via `main()` JSON; native clock clients
        are parameterized; pins and Windows PATH-first discovery remain method-level
        exceptions.
  - [x] Remaining tests each protect a distinct public contract, workflow, boundary, or
        allowed method-level exception; removed tests are private-helper, getter,
        call-sequence, or duplicate-layer coverage. Net `-1380` lines across 36 test
        modules (~45 deletions, ~24 rewrites onto CLI/public functions/JSON). Kept
        fail-closed security, schema immutability, Makefile-named classes, and subtle
        helpers.
  - [x] Focused rewritten modules pass; `make python-check` passes the reduced suite
        (exit 0). `make format-check` and `make lint` pass.

### [x] IDE-001 — Evaluate a provider-neutral specification-led IDE sample catalog

- **Priority:** P1
- **GitHub issue:** [#184](https://github.com/NVIDIA-dev/literate-ai/issues/184)
- **Related:** [#115](https://github.com/NVIDIA-dev/literate-ai/issues/115),
      [#134](https://github.com/NVIDIA-dev/literate-ai/issues/134),
      [GENERATION-007](../../roadmap/active-work.md#x-generation-007-add-an-authenticated-inherited-ide-session-coding-provider)
      ([#43](https://github.com/NVIDIA-dev/literate-ai/issues/43))
- **Owner:** sample/Component catalog ownership
- **Direction:** Downstream carries reusable Components for opening a Literate AI
      repository, projecting project authority, editing Component/Flavor/skill
      documents, selecting lifecycle workflows, enforcing safe catalog mutation,
      supervising runtime sessions, and composing a browser workbench. Decide
      whether this repository should publish a provider-neutral IDE sample
      catalog. That question was wrongly recorded as a hard rule against IDEs
      and complete applications, including in derived projects.
- **Conclusion:** Withdrawn. Literate AI has no rule against building an IDE or
      a complete sample application. This repository's current catalog simply
      does not contain an IDE sample; that is an inventory fact, not a ban.
      Derived projects may ship IDEs, workbenches, viewports, and complete
      applications. Samples in this repository are already complete applications;
      `inheritable: false` is catalog-export policy, not a product restriction.
      Plugin/CLI interop remains a useful path; it is not exclusive. A later
      in-tree IDE sample is ordinary catalog work, not a reversal of a
      prohibition. Comment on #184 with a commit-pinned permalink.
- **Scope boundary:** None as a framework rule. Do not fold a downstream
      product's branded shell, renderer, or domain SDK into this repository
      merely because an IDE is allowed.
- **Depends on:** none
- **Implementation:**
  - [x] Withdraw the "do not build a native IDE" conclusion and every document
        that restated it as a hard rule.
  - [x] Record that derived projects are free to build IDEs and complete
        applications.
- **Evidence:**
  - [x] `PROJECT.md` no longer forbids an IDE.
  - [x] This item's conclusion is a withdrawn prohibition, not a decline.

### [x] SKILL-PROFILE-001 — Evaluate a generic declarative studio-profile generation skill

- **Priority:** P1
- **GitHub issue:** [#185](https://github.com/NVIDIA-dev/literate-ai/issues/185)
- **Related:** [IDE-001](../../roadmap/active-work.md#x-ide-001-evaluate-a-provider-neutral-specification-led-ide-sample-catalog)
- **Owner:** specification-to-source skill catalog
- **Direction:** Downstream has a generation skill for an identity-bearing declarative
  profile provider: modes, navigation, commands, tools, catalog selectors, presentation,
  capability ownership, and fail-closed validation. The mechanism is not tied to a
  language, OS, renderer, or domain SDK; only the profile *data* is product-specific.
  Decide whether Literate AI should own a generic profile-provider generation skill that
  derived products import, while each product retains its profile Component and
  domain catalog.
- **Conclusion:** This is not an IDE ban and is not blocked by IDE-001. It is a
  specification-to-source skill that generates the provider which *reads* a declarative
  profile, analogous to `python-service-application`. The load-bearing risk is shadow
  authority: profile data must not replace `component.md`, locks, receipts, or
  executable behavior, and the skill must not introduce runtime plugin discovery.
  Keep the downstream copy authoritative until this repository has an in-tree consumer
  or a second derived product needs the same skill. Derived products may already ship
  IDEs, workbenches, and complete applications; they do not need this import to do so.
  Any later import must stay provider-neutral and fail closed when profile data tries
  to override project authority.
- **Scope boundary:** Do not copy the downstream skill, schema, or tests into this
  repository under this evaluate. Do not add runtime plugin discovery. Do not let a
  profile document become a second project definition.
- **Depends on:** an in-tree consumer or a second product that needs the same generic
  provider. IDE-001 is not a blocker.
- **Implementation:**
  - [x] Keep this item unevaluated-as-import until an in-tree consumer or a second
        consumer is named.
  - [x] Comment on #185 with a commit-pinned permalink when the import decision
        is recorded.
        [issue comment](https://github.com/NVIDIA-dev/literate-ai/issues/185#issuecomment-5459136503)
        pins `059dfc7962e4cae9c52d3d6554df5690d6d937da`
        `docs/roadmap/active-work.md#L4881-L4920`.
- **Evidence:**
  - [x] The recorded decision either names the in-tree consumer and the
        authority-boundary tests that would gate an import, or records that the
        downstream copy stays authoritative.
        **Decline (2026-08-28):** no in-tree consumer. Downstream stays
        authoritative. Do not copy the skill. Import only after a named in-tree
        consumer exists.

### [x] FLAVOR-JS-NPM-001 — JavaScript Flavor has no npm-dependency capability

- **Priority:** P2
- **Release target:** 0.8.0 (break-glass major-equivalent; was after 0.8.0)
- **GitHub issue:** [#87](https://github.com/NVIDIA-dev/literate-ai/issues/87)
- **Owner:** `flavors/javascript`, source-composition validation
- **Direction:** The JavaScript Flavor has no composition shape that accepts a
      complete enumerated npm dependency closure. That matches today's
      "SHALL use no npm package" Flavor text. Component-library frontends cannot
      be expressed.
- **Conclusion:** Accept an isolated, lockfile-pinned npm-capable axis
      (`implementation.javascript-packages`, Flavor `js-npm`). `+js-npm` requires
      JavaScript; without it lock fails `component_lock.flavor_target_unsatisfied`.
      Generation may declare an enumerated `package.json` only when this axis is
      selected; every package must be pinned by a complete `package-lock.json`
      (lockfileVersion 2 or 3). Detect-before-install: resolve `npm` and Node on
      PATH, then `npm ci` into `OBJ_DIR` / ignored `node_modules`. Landed as
      `59c02491` (isolated `1143a824`).
- **Implementation:**
  - [x] Record the accept (new npm-capable axis with detect-before-install) or
        decline (dependency-free JS only) with Flavor text that matches.
        `flavors/js-npm/`, `+js-npm` / `+npm`, optional `packages` slot on
        frontend Components. Catalog and template `SKILL.md` copies stay
        byte-identical.
- **Evidence:**
  - [x] Lockfile-pinned npm composition path exists: `tests.smoke.test_app_stack_skills`
        (axis, js-npm with/without JS), `test_javascript_ecosystem_skill`
        (detect-before-install), `test_flavor_add` (`flavor add js-npm`),
        `test_package_flavor_catalog` (catalog/template match including `js-npm`).

### [x] SPEC-MERGE-001 — Staged reverse-adoption for already-managed projects

- **Priority:** P2
- **Release target:** 0.8.0 (break-glass major-equivalent; was after 0.8.0)
- **GitHub issue:** [#113](https://github.com/NVIDIA-dev/literate-ai/issues/113)
- **Owner:** `litai spec` / convert follow-on
- **Direction:** Already-litai-managed projects with hand-authored escape-hatch
      code need piece-by-piece reverse-adoption ("spec merge"), not a second
      `init --convert`.
- **Conclusion:** Distinct from first-time convert. CONVERT-FW-009's baseline
      copy/quarantine defects are closed. Land spec-merge on this same 0.8.0 cut.
- **Implementation:**
  - [x] Design staged spec-merge against current `spec derive` / `spec accept`
        now that CONVERT-FW-009 is closed. `litai spec merge SOURCE --component NAME`
        plans a Component draft from one island and `--apply` writes only that draft.
- **Evidence:**
  - [x] A fixture already-managed tree can adopt one hand-authored island without
        re-quarantining the whole project (`tests/critical/test_spec_merge.py`).

### [x] COMPONENT-KIND-001 — Make the CLI entrypoint contract a Component subclass

- **Priority:** P2
- **Release target:** 0.8.0 (break-glass major-equivalent; was after 0.8.0)
- **GitHub issue:** [#114](https://github.com/NVIDIA-dev/literate-ai/issues/114)
- **Owner:** Component catalog / Standard lifecycle
- **Direction:** The single CLI entrypoint contract is the implicit base for all
      Components. Library, service, and other kinds inherit CLI-shaped
      assumptions they should not.
- **Conclusion:** `cli-application` is an explicit `ComponentKind` subclass, not the
      implicit base. Omitted `kind` infers from entrypoints so existing authoring
      identities stay stable. Default init Flavors are unchanged. FLAVOR-005 may
      land in parallel; this slice used existing alias APIs and did not rename
      Flavor directories.
- **Depends on:** [FLAVOR-005](../../roadmap/active-work.md#flavor-005-rename-flavor-directories-to-their-axis-qualified-selector-names)
      was listed first; this slice proceeded without the directory rename.
- **Implementation:**
  - [x] Spike: name the CLI contract as an explicit subclass and list which
        generated assumptions are CLI-only (`CLI_APPLICATION_LIFECYCLE_ASSUMPTIONS`).
- **Evidence:**
  - [x] `docs/architecture/component-authoring-lock-boundary.md` names the subclass
        boundary; `tests/unit/test_component_kinds.py` proves omitted `kind` infers
        `cli-application` without emitting the field. Default init Flavors are
        unchanged.

### [x] COMPONENT-KIND-002 — Additional Component-subclass candidates

- **Priority:** P2
- **Release target:** 0.8.0 (break-glass major-equivalent; was after 0.8.0)
- **GitHub issue:** [#115](https://github.com/NVIDIA-dev/literate-ai/issues/115)
- **Related:** [COMPONENT-KIND-001](../../roadmap/active-work.md#x-component-kind-001-make-the-cli-entrypoint-contract-a-component-subclass),
      [IDE-001](../../roadmap/active-work.md#x-ide-001-evaluate-a-provider-neutral-specification-led-ide-sample-catalog)
- **Owner:** Component catalog
- **Direction:** Candidates beyond CLI/library/service: packaged modules,
      wrapped-source, UI, batch, event, schema-only.
- **Conclusion:** Accepted with a distinct contract: `packaged-module` (package is
      the artifact; no CLI argv), `ui` (no CLI argv; render/lint later),
      `schema-only` (empty entrypoints; schema validate). Declined: `wrapped-source`
      (convert phase, not a generation kind), `batch` (same lock/generate/accept as
      CLI), `event` (same as persistent-service). A UI subclass is a lifecycle
      kind, not a product restriction.
- **Depends on:** COMPONENT-KIND-001
- **Implementation:**
  - [x] After COMPONENT-KIND-001, accept or decline each candidate kind with a
        named lifecycle difference.
- **Evidence:**
  - [x] Authoring validation and
        `docs/architecture/component-authoring-lock-boundary.md` name each accepted
        contract and each declined kind. `samples/generated-library` still declares
        a portable-application entrypoint and therefore still infers
        `cli-application`; migrating that sample is follow-up.

### [x] ACCEPTANCE-RENDER-001 — Lint-and-render-stability oracle for hand-authored frontends

- **Priority:** P2
- **Release target:** 0.8.0 (break-glass major-equivalent; was after 0.8.0)
- **GitHub issue:** [#134](https://github.com/NVIDIA-dev/literate-ai/issues/134)
- **Related:** [IDE-001](../../roadmap/active-work.md#x-ide-001-evaluate-a-provider-neutral-specification-led-ide-sample-catalog),
      [COMPONENT-KIND-002](../../roadmap/active-work.md#x-component-kind-002-additional-component-subclass-candidates)
- **Owner:** acceptance oracles / library and frontend Components
- **Direction:** Hand-authored library/frontend Components need a lint-and-render-
      stability oracle, not only CLI JSON acceptance.
- **Conclusion:** In 0.8.0 scope. The oracle must stay evidence-bound (lint +
      render snapshot). That is a harness constraint, not a ban on IDEs: an IDE
      or complete application still needs an evidence-bound oracle, and the
      oracle must not be "open the editor and look."
      **Completed 2026-08-30:** verifier-owned
      `literate-ai/lint-render-acceptance@1` at
      `verification/acceptance/<component>.json` binds `specification_set_identity`,
      lint argv (exit 0), and `sha256(render stdout)` as `snapshot_identity`.
      `{python}` is the only substitution; relative argv only. Library/UI without
      this file stay independently exempt (#114). Portable/persistent-service keep
      existing oracles. Landed as `a4b2b7bf` on `feat/cli-sdlc-debug` (isolated
      `dc95f254`).
- **Implementation:**
  - [x] Design an oracle that is evidence-bound (lint + render snapshot) and does
        not use a shipped editor as the only proof path.
- **Evidence:**
  - [x] Fixture `tests/fixtures/lint-render-library` fails closed on
        `component_acceptance.render_drift` and passes when the snapshot matches.
        `LITAI_SESSION_ID=dev` `tests.smoke.test_lint_render_acceptance` — 8 tests
        OK.

### [x] FLAVOR-008 — Fail closed on duplicate packaging and document Flavor aliases

- **Priority:** P1
- **Release target:** 0.7.2
- **GitHub issue:** [#186](https://github.com/NVIDIA-dev/literate-ai/issues/186)
- **Owner:** Flavor catalog, `litai init` / `litai update`, project validation,
  `litai catalog migrate-flavor-names`
- **Direction:** A derived project retained eight legacy flat Flavor aliases alongside
  imported canonical parent Flavors: six packaging aliases for `package-*` and two
  document-ecosystem aliases for `doc-*`. Duplicate directories are two authorities for
  the same standards-based behavior. Document and validate canonical axis-prefixed
  names. Initialized and updated projects should consume `package-*` and `doc-*`
  identities and should not recreate flat or dotted aliases.
- **Conclusion:** ADR 0010 already made `package-pip` / `doc-google-workspace` (and the
  rest of those axes) the canonical names, with `DEPRECATED_FLAVOR_ALIASES` at input
  and durable state rewritten to the canonical form. The remaining defect is catalog
  *directories*: inheritance keys `(kind, directory-name)`, so `flavors/pip` and
  `flavors/package-pip` coexist; `migrate-flavor-names` currently raises
  `catalog.flavor_migration_collision` when the canonical directory already exists,
  which is exactly the descendant layout. 0.7.2 tightens that rule without the
  FLAVOR-005 `git mv` of `python` → `lang-python` (lock-identity blast radius, not a
  patch). Fail closed when two Flavor entries canonicalize to the same coordinate;
  drop a known alias directory when migrate finds the canonical already present;
  prove `+pip` / `+google-workspace` stamp `flavors/package-pip` /
  `flavors/doc-google-workspace` and never `flavors/pip` or
  `flavors/google-workspace`. Bare selectors (`+pip`) stay valid through ADR 0010's
  deprecation window; they must not create a second on-disk authority.
- **Depends on:** ADR 0010 and the existing `catalog migrate-flavor-names` command.
  Does not depend on FLAVOR-005's remaining language/OS/build directory rename.
- **Implementation:**
  - [x] Canonicalize Flavor coordinates, names, and directory names through the ADR
        0010 alias table and reject two catalog entries that share one canonical
        coordinate (`canonical_flavor_catalog_collisions`,
        `generate.duplicate_flavor_alias`).
  - [x] When `migrate-flavor-names` sees a known alias directory and the canonical
        destination already exists, plan and `--record` a removal of the alias tree
        instead of colliding.
  - [x] Prove init from a deprecated packaging or document selector writes only the
        canonical directory.
  - [x] Document that packaging and documentation Flavors are `package-*` / `doc-*`
        on disk in ADR 0010 and `PROJECT.md`; descendants delete local aliases once
        the check passes.
- **Evidence:**
  - [x] `canonical_flavor_catalog_collisions` reports `flavors/pip` beside
        `flavors/package-pip` and `flavors/google-workspace` beside
        `flavors/doc-google-workspace`; a `python` directory with `lang-python` does
        not collide with `package-pip`. Catalog load of this repository's 28 Flavors
        still succeeds.
  - [x] `litai catalog migrate-flavor-names --record` on a stub with both `pip` and
        `package-pip` removes the alias directory and rewrites locks to the canonical
        coordinate (`tests.unit.test_flavor_name_migration`).
  - [x] Init with `+pip` creates `flavors/package-pip` and not `flavors/pip`; init
        with `+google-workspace` creates `flavors/doc-google-workspace` and not
        `flavors/google-workspace`.
  - [x] `tests.unit.test_flavor_name_migration` 6 tests OK; `make format-check` and
        `make lint` pass.

### [x] DOC-AUTHORITY-SCOPE-001 — The documentation-authority hash sweeps the entire `docs/` tree, including the roadmap's own todo list

- **Priority:** P1
- **Owner:** `_documentation_catalog`/`documentation_files` in
  `src/literate_ai/adapters/project_validation.py` and `src/literate_ai/projects.py`;
  `literate.project.json`'s `documentation_roots`
- **Direction:** `literate.project.json` declares `"documentation_roots": ["docs"]`, and
  `_documentation_catalog` folds every file under that root — with no distinction of
  role — into the single `authority_identity` hash that
  `test_repository_is_a_self_describing_canonical_project` and the
  `literate-ai:authority-reviewed` marker in `design-traceability.md` check. That set
  includes `docs/roadmap/active-work.md`, which `track-project-requirements` itself
  describes as "the tactical execution queue" beneath `PROJECT.md`, not authority. In
  this session, editing the roadmap's own todo list restaled the marker four separate
  times, each requiring a human/agent re-review-and-sign step before `project validate`
  would pass again. This is a scoping defect, not a caching one: the *input set* being
  hashed is wrong by definition, regardless of how correctly or freshly it's recomputed.
- **Conclusion:** Keep `documentation_roots` as the full declared spine so graph
  validation still admits roadmap links and assets. Exclude only project-relative
  `docs/roadmap/**` from the authority-review *hash*. User, architecture, decision, and
  presentation docs remain hashed; queue checkbox churn must not stale the marker.
- **Evidence:**
  - [x] Editing only `docs/roadmap/active-work.md` (or a linked detailed roadmap
        document) does not change `authority_identity` or stale the
        `literate-ai:authority-reviewed` marker.
        `ProjectCliTests.test_roadmap_queue_edits_do_not_stale_authority_review`.
  - [x] Editing any other file currently under `documentation_roots` still does.
        Same test: `docs/user/framework-flow.md` edit yields
        `project.documentation_authority_review_stale`. Broken roadmap links still fail
        `project.documentation_link_missing`.

### [x] RELEASE-ENV-001 — `make release` leaks `PYTHONPATH=src` into the gate subprocess and fails a release that `make release-check` passes

- **Priority:** P0
- **Owner:** `Makefile` (`release` target) and `_run_release_gate` in
  `src/literate_ai/project_releases.py`
- **Direction:** `make release` invokes the release gate as
  `PYTHONPATH=src litai release check ...`, and `_run_release_gate` launches the gate
  with `env=os.environ.copy()`. `PYTHONPATH=src` therefore survives into the gate and
  into every command the gate spawns beneath it. Those inner commands then resolve
  `literate_ai` from both the source tree and the installed distribution, and the
  Standard driver binding fails with
  `driver_resolution_error: standard_binding.distribution_ambiguous`. The failure is
  purely environmental: the identical revision passes a direct `make release-check`,
  and passes `litai release check` invoked with `PYTHONPATH` unset. The gate is
  supposed to reproduce the release-check verdict, so any environment that changes the
  verdict is a defect in the gate's isolation, not in the revision under release.
- **Conclusion:** The release gate must run in an environment derived from the release
  contract, not inherited verbatim from whichever Make target happened to invoke it.
  Decide which variables are load-bearing for the gate and pass exactly those;
  interpreter-resolution variables (`PYTHONPATH`, and by the same argument
  `PYTHONHOME`, `VIRTUAL_ENV`) must not cross the boundary, because a release gate
  that resolves the framework differently from the release artifact is not
  qualifying the artifact. Do not fix this by editing only the `Makefile` recipe: that
  leaves the leak available to every other caller of `release check`.
- **Repro:** From a prepared release commit, `make release RELEASE_PLAN=<plan>.json`
  fails with `release.gate_failed` naming `standard_binding.distribution_ambiguous`,
  while `env -u PYTHONPATH litai release check <plan>.json --project .` on the same
  tree passes. Observed against the 0.3.0 prepared commit.
- **Depends on:** RELEASE-OBS-001's gate-output reporting — the underlying error was
  invisible until the gate began surfacing its subprocess stderr.
- **Implementation:**
  - [x] Give `_run_release_gate` an explicit environment allowlist (or an explicit
        denylist of interpreter-resolution variables) rather than `os.environ.copy()`.
  - [x] A regression sets `PYTHONPATH` in the parent environment, runs the gate, and
        proves the child never observes it.
  - [x] `make release` and `make release-check` reach the same verdict on the same
        revision, proven on a revision where they currently disagree.
- **Completion evidence:** `_gate_environment()` strips `PYTHONPATH`/`PYTHONHOME`/
  `VIRTUAL_ENV` from the copied environment before `_run_release_gate` launches the
  gate subprocess. Two regressions: a focused unit test proving the denylist, and an
  integration test that sets `PYTHONPATH` in the test process, runs a real
  `check_release` whose gate command asserts `PYTHONPATH` is absent, and confirms it
  exits 0. Pulled into 0.4.0 scope per explicit user direction.

### [x] CLI-002 — Group the litai catalog into SDLC bands without merging verbs

- **Priority:** P0
- **Owner:** framework CLI help and `docs/user/configuration-and-cli.md`
- **Direction:** Group the installed `litai` catalog so help reads as an SDLC
      without deleting or aliasing verbs this pass. The published inventory was
      stale relative to the parser.
- **Conclusion:** Keep every current argv. Add argparse epilog bands. Document
      recommended later combinable verbs only. Do not split `--convert` off
      `init`. Do not add staging/production CLI verbs.
- **Depends on:** [CLI-001](../../roadmap/active-work.md#x-cli-001-make-help-a-scoped-first-class-verb);
      extends the inventory remainder of [DOCS-005](../../roadmap/active-work.md#docs-005-make-the-current-lifecycle-obvious-from-the-repository-front-door)
- **Implementation:**
  - [x] Group `litai help` with an SDLC epilog; keep `help` as a verb at every
        depth.
  - [x] Regenerate `docs/user/configuration-and-cli.md` from the parser; drop
        the `worker capability` ghost; record recommended later aliases.
- **Evidence:**
  - [x] `CliHelpTests.test_command_reference_lists_every_public_cli_verb_once`
        and `CliDebugFlagTests.test_help_lists_sdlc_catalog_bands` pass.

### [x] HARNESS-001 — Position Literate AI as a release-engineering SDLC harness

- **Priority:** P0
- **Owner:** `PROJECT.md`, root `README.md`, `SKILL.md`, user-guide front door
- **Direction:** The durable talent is `litai init` and `litai init --convert`
      plus the evidence-gated `dev` workflow and versioned release.
      Spec-to-binary generation remains authority and arrives in waves.
- **Conclusion:** Lead onboarding with adopt → verify → rebuild(dev) → release.
      Replace future `litai init --adopt` wording with `init --convert`. Keep
      the spec-to-binary diagram, but second. Do not regenerate the Google
      manager deck in this pass.
- **Depends on:** [CLI-002](../../roadmap/active-work.md#x-cli-002-group-the-litai-catalog-into-sdlc-bands-without-merging-verbs)
- **Implementation:**
  - [x] Rewrite `PROJECT.md` goals so the harness is goal 1.
  - [x] Reframe README, getting-started, user-guide paths, framework-flow, and
        `SKILL.md`.
- **Evidence:**
  - [x] `--adopt` wording is gone from user docs except historical queue items
        and `update --adopt-added`.

### [x] CLI-DEBUG-001 — Add global debug tracing for SDLC stages and spec maps

- **Priority:** P0
- **Owner:** `src/literate_ai/diagnostics.py`, CLI globals, `spec_map.py`
- **Direction:** `--debug` is harness-stage tracing, redacted child argv, plus
      generated-code spec↔source maps. It is not a `--verbose` superset. Stdout
      stays the command envelope.
- **Conclusion:** Accept `--debug` / `--debug=FILE` before or after the verb.
      Default destination is stderr. Inherit via `LITAI_DEBUG`. Coding CLIs
      place `litai:spec PATH:LINE` anchors; a framework scanner assigns
      generated lines. Missing maps do not fail the lifecycle. Identity-bearing
      via prompt append, not a generation-key schema bump. Child commands emit
      `subprocess.start` / `subprocess.exit` with redacted argv; child
      stdout/stderr stay `--verbose`.
- **Depends on:** [CLI-002](../../roadmap/active-work.md#x-cli-002-group-the-litai-catalog-into-sdlc-bands-without-merging-verbs)
- **Implementation:**
  - [x] Global `--debug` / `--debug=FILE`, `LITAI_DEBUG` inheritance, stage
        events, JSON-vs-human rendering.
  - [x] `debug-spec-map` skill, deterministic scanner, Python helper, fixture.
  - [x] `trace_subprocess` publishes redacted argv on `--debug` without dumping
        child stdout/stderr.
- **Evidence:**
  - [x] `tests.unit.test_cli_debug` and `tests.unit.test_spec_map` pass.

### [x] GENERATION-002 — Add OpenCode as a first-class coding CLI

- **Priority:** P0
- **Owner:** framework core / coding-CLI generation and model-task adapters
- **Direction:** Support `opencode` everywhere Literate AI currently supports Codex,
  Claude, and Cursor Agent so projects can select it explicitly or discover it on
  `PATH` for forward generation, repair, and inverse/model-backed tasks.
- **Conclusion:** Bind OpenCode through its documented non-interactive `run` command,
  exact workspace, explicit model selector, pure-plugin mode, and a LitAI-owned bounded
  permission/configuration profile. Preserve OpenCode's stored provider authentication
  and documented environment credentials without forwarding unrelated secrets. Record
  honestly that OpenCode permissions are a provider tool policy rather than an OS
  sandbox; LitAI's temporary workspace, output collector, executable pin, bounded
  process, and source-custody checks remain the enforcement boundary. Do not add a
  remote server dependency, ambient project configuration, session reuse, or an
  implicit fallback from an explicitly selected unavailable OpenCode executable.
- **Depends on:** the existing provider-neutral coding-CLI selection, lexical model
  scope, bounded-process, and generation-custody contracts
- **Implementation:**
  - [x] Extend coding-CLI authority, schemas, model scopes, generation/inverse
        contracts, and installed-project guidance with `opencode`.
  - [x] Add the exact OpenCode command, clean configuration and permission environment,
        executable selection, authentication diagnostics, and honest isolation profile.
  - [x] Update CLI/user documentation, troubleshooting, traceability, and release notes.
  - [x] Install a user-local OpenCode CLI for interface and smoke verification without
        persisting test credentials or weakening the framework boundary.
- **Evidence:**
  - [x] Focused unit/schema tests cover explicit selection, PATH order, model forwarding,
        bounded tools/configuration, credential scrubbing, authentication failures, and
        all forward/inverse provider validators.
  - [x] Strict OpenSpec, canonical project validation, formatting/lint, documentation,
        CodeGraph synchronization, and the proportional Python suite pass.
  - [x] The installed `litai` distribution selects the installed `opencode` executable
        and reports the exact command, environment-key, isolation, and model bindings
        without requiring a live credential or model call.

### [x] RELEASE-002 — Fail fast and resume release qualification from durable checkpoints

- **Owner:** release engineering / initialized-project test harness
- **Direction:** Fix the first known failure immediately instead of waiting hours for
  later successes. Parallel qualification must durably remember tests that passed in a
  run, resume after a repair without repeating that prefix, and reset to the beginning
  only after the complete gate reaches green so regressions are still caught.
- **Conclusion:** Introduce a versioned, compact, Git-ignored diagnostic checkpoint
  keyed by repair-cycle identity and exact test identity. Stop scheduling new work after
  the first failure, allow already-running workers to finish and record their results,
  and permit the same repair cycle to skip those provisional successes after a fix.
  These skips are never release evidence: reaching the end consumes/resets the
  checkpoint and requires one authoritative run from the beginning. Stale, corrupt, or
  foreign checkpoints fail closed rather than skipping work.
- **Depends on:** RELEASE-001, compact versioned test-evidence contracts
- **Implementation:**
  - [x] Define checkpoint identity, atomic persistence, invalidation, corruption, and
    successful-reset semantics without checking volatile execution state into Git;
    Python schema v2 binds each reusable outcome to its test file so plan additions and
    isolated repairs preserve unrelated successes.
  - [x] Make the current serial Python release gate fail fast at its first failure.
  - [x] Make the parallel fan-out scheduler fail fast while safely draining already-running
    workers and recording their exact passing test identities.
  - [x] Resume a repaired run from matching successes and expose concise progress,
    invalidation, and reset diagnostics through the project-native test command.
  - [x] Ship the same runner contract, skill guidance, ignore rules, and starter tests
    in every `litai init` project.
  - [x] Add deterministic tests for first failure, concurrent completion, plan-change
    reconciliation, per-file invalidation, legacy omitted-skip recovery, corrupt
    checkpoint rejection, resume, and full-run reset followed by a from-zero regression
    run.
- **Evidence:**
  - [x] A deliberately failing initialized project stops promptly, resumes without
    repeating exact prior successes after repair, then resets and passes once from the
    beginning.

### [x] MODEL-001 — Add lexically scoped model routing to every model-using pipeline

- **Priority:** P0
- **Conclusion:** A command-line `--model MODEL` is the pipeline default, not an
  unconditional override. Component, selected-Flavor, and invoked-Skill authority may
  establish narrower model scopes. Resolution is an immutable lexical stack attached to
  each DAG node and bounded agent task: the most specific applicable scope wins, and
  completion returns automatically to the enclosing binding. Never implement this as
  mutable process-global state.
- **Deliverables:**
  - [x] add `--model MODEL` to every command that can invoke a coding CLI, including ordinary
    build/test, generation/rebuild, and model-backed forward/inverse workflows; commands
    such as `run`, which execute an already-built artifact without crossing the model
    boundary, must omit the flag;
  - [x] define a versioned `ModelScope`/resolved-binding contract with scope kind, owner
    identity, parent binding, provider, selector, and resolution trace;
  - [x] define deterministic precedence and ambiguity rules for pipeline, Component,
    Flavor-role, Skill-invocation, and nested Component scopes; equally specific
    conflicting bindings fail before model egress;
  - [x] resolve independently per Component DAG node and per Skill invocation so sibling
    overrides cannot leak and an inner override restores its parent on return;
  - [x] bind the effective model and complete scope provenance into generation plans, source
    cache keys, coding-CLI requests/journals, learning evidence, and receipts;
  - [x] carry the resolved model-scope identity through typed remote-worker dispatch so a
    command worker cannot lose, reinterpret, or replace the caller's lexical default;
  - [x] document examples with a pipeline default, a nested Component override, a Skill
    override inside it, and restoration for the next sibling Component;
  - [x] add unit and installed-project E2E tests proving precedence, restoration, conflict
    rejection, cache invalidation, and forwarding through Codex/Claude/Cursor adapters.
- **Evidence:** 198 focused tests plus 129 subtests pass across model contracts, forward
  and inverse planning, dispatch, CLI, schemas, and all three provider command builders.
  The clean installed `0.2.0` wheel initializes a project and proves that
  `--model installed-pipeline-model` reaches every resolved node binding and the exact
  corresponding generation-key identity. Unit DAG evidence proves nested precedence,
  sibling restoration, pre-egress conflict rejection, and node-local cache invalidation.
- **Depends on:** the current locked per-node model-selection adapter, generation-plan
  identities, and typed Standard lifecycle dispatch.

### [x] CLI-OBS-001 — Expose safe inherited subcommand tracing

- **Priority:** P0
- **Direction:** Add global `litai -v` and `litai --verbose` flags that expose every
  framework-launched subprocess command and its stdout/stderr while a command runs.
- **Conclusion:** Verbose diagnostics belong on stderr so JSON stdout remains a stable
  machine contract. Propagate the setting through in-process lifecycle composition,
  command workers, SSH/third-party dispatch envelopes, and child `litai` invocations;
  redact secrets and credentials, retain bounded-output limits, and never weaken the
  existing timeout, authorization, or sandbox boundaries merely to stream output.
- **Deliverables:**
  - [x] Accept `-v`/`--verbose` before any CLI verb and document its stderr contract.
  - [x] Trace safely quoted argv, cwd, exit status, and bounded stdout/stderr for every
        framework-owned subprocess boundary, including coding CLIs and native builds.
  - [x] Carry verbosity through typed remote-worker dispatch without changing lifecycle
        authority or cache identities.
  - [x] Redact environment-derived credentials, access tokens, authorization headers,
        and known secret argument values before emission.
  - [x] Add CLI, subprocess, JSON-envelope, nested invocation, and redaction tests.
- **Evidence:** focused CLI and lifecycle tests prove verbose subprocess evidence remains
  on stderr, nested child processes inherit the flag, secrets are redacted, and quiet
  execution remains quiet. Installed-wheel coverage remains part of the release gate.

### [x] LAYOUT-004 — Make `_build`/`BUILD_DIR` advisory for fungible generated source

- **Owner:** specification-to-source skills (`make-build-system`, `repository-layout`,
  `python-repository-layout`, `portable-application-implementation`) and onboarding
  `SKILL.md`
- **Direction:** `_build` (and `BUILD_DIR`/`generated/` as the accepted source cache) is
  the **advisory default prefix** for **fungible generated application source** that may
  be deleted and regenerated. It is **not mandatory** for load-bearing project
  authority. Literate AI itself and any project that modifies itself may change
  Component specs, Flavors, skills, workflows, routing, locks, `literate.project.json`,
  and the project's Makefile outside `_build`. A coding CLI writing a root Makefile
  **as generated application output** remains wrong; writing the **project's** Makefile
  as project authority is allowed.
- **Conclusion:** `c2f5583` already forbids a generated workspace-root Makefile in the
  catalog `make-build-system` skill, but the initialized-project **template copy** still
  carries v1.3.2 "always generate a thin root-level delegating Makefile", and layout
  skills still say accepted generated source lives **only** under `BUILD_DIR`. That
  contradiction taught Claude to write a root Makefile while generating a product
  Component (`coding_cli.unexpected_output`). Keep the generation-workspace `source/`
  bound for fungible product source; make `_build`/`BUILD_DIR` advisory rather than a
  cage for project-owned catalog/authority. Do not loosen `coding_cli.unexpected_output`.
- **Depends on:** FLAVOR-001 catalog skill v1.4.0; CACHE-002 object-directory boundary
- **Next action:** Done. Catalog and template skill bytes, wording tests, and
  `make skills-check` are recorded under Evidence.
- **Implementation:**
  - [x] Update `make-build-system` so generated application Makefiles stay under
        admitted `source/`, while a self-modifying project's Makefile remains allowed
        project authority.
  - [x] Make `repository-layout`, `python-repository-layout`, and
        `portable-application-implementation` treat `_build`/`BUILD_DIR` as the advisory
        default for fungible generated application source, not a mandatory home for
        load-bearing catalogs.
  - [x] Keep the `project_template` copies byte-identical with the catalog skills.
  - [x] Align onboarding `SKILL.md` and layout docs with the same inverse wording.
  - [x] Update wording tests and skill-dependency identity pins.
- **Evidence:**
  - [x] Catalog and template `make-build-system` bytes match and no longer instruct a
        generated root Makefile.
  - [x] `tests.unit.test_make_generation_skill` and the Make-init flavor test passed.
  - [x] `make skills-check` admitted the changed skills (`--no-llm`).

### [x] CACHE-003 — Preserve the sole source-cache write target in Standard rebuilds

- **Release target:** 1.1.0
- **Previous release target:** 0.9.0 (re-scoped 2026-09-01: had no explicit target)
- **Owner:** framework Standard lifecycle / source-cache composition
- **Direction:** A project may declare several ordered source-cache read targets, but
  only its explicit `write_target_id` may be opened with write authority during a
  Standard rebuild.
- **Conclusion:** The new Standard rebuild resolver correctly selects the configured
  store for publication, but its direct store construction currently opens every
  declared target writable. Match the public `SourceCacheResolver.from_configuration`
  boundary: open the sole configured write target writable and every other target
  read-only, without changing lookup order or publication selection.
- **Depends on:** the schema-v2 source-cache configuration and Standard rebuild
  composition shipped in `28ffdd6`
- **Implementation:**
  - [x] Project write authority into each filesystem store during Standard rebuild
    composition.
  - [x] Add regression coverage proving a declared project-relative secondary target is
    not created or made writable while the configured runtime target remains writable.
- **Evidence:**
  - [x] Forty focused Standard rebuild and source-cache tests pass on macOS, including
    absent read-only targets remaining absent and the runtime write target remaining
    writable.
  - [x] Repository quality gates pass on qualified `692041a1`, whose full
        Git tree is identical to merged `ad92a655`. The retained local Python
        evidence contains 4,206 tests, 30 skips and zero failures; its terminal
        output digest matches `sha256:aea1c7ededfc897df991433780e0eb509eaa7450384d09a4d0c2ce9a8340a6f0`.
        [PR #388](https://github.com/NVIDIA-dev/literate-ai/pull/388) records the
        accompanying lint, format, layout, OpenSpec, documentation, authority,
        wheel and installed checks. All 15 jobs of the merged revision's
        [hosted matrix](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34671435026)
        pass. The current resolver and regression prove that only
        `write_target_id` is writable, a missing secondary cache stays absent,
        and read-only runtime configuration creates no store.
        These source and test files are unchanged in integration `7ab1562c`.
        RELEASE-INTEGRATION-001 retains the fresh combined qualification and
        current lifecycle-receipt obligations.

### [x] CACHE-004 — Expose deliberate cache promotion below the CLI

- **Release target:** 1.1.0
- **Previous release target:** 0.9.0 (re-scoped 2026-09-01: had no explicit target)
- **Owner:** framework application service / filesystem cache adapter
- **Direction:** A downstream application must be able to deliberately publish verified
  runtime source-cache entries into a declared project-relative cache without importing
  `literate_ai.cli` or reimplementing the immutable-entry protocol.
- **Conclusion:** Move entry-copy orchestration into a provider-neutral application
  service and keep project discovery, cache-directory resolution, and filesystem store
  construction in a public adapter. The CLI becomes one presentation adapter over that
  boundary. Publication remains explicit, restartable, and acceptance-untrusted; it
  does not become part of rebuild or specification authority.
- **Depends on:** CACHE-003 write-authority rules and the existing filesystem-v2
  `FileSystemSourceCache` verification boundary
- **Implementation:**
  - [x] Define a typed publication result/error and application service over injected
    readable-source and writable-destination ports.
  - [x] Add a filesystem project adapter that selects exactly one declared committable
    target and opens the runtime source read-only.
  - [x] Make `litai cache publish` delegate to the public adapter with unchanged JSON
    and stable error codes; export the service/adapter for product composition.
  - [x] Add unit and CLI regressions for publication, idempotent replay, target
    ambiguity, absent runtime state, attachment propagation, and no CLI-private
    dependency in a downstream product.
  - [x] Update cache architecture, traceability, and the changelog.
- **Evidence:**
  - [x] Forty-two focused application, adapter, cache, and CLI tests pass on macOS,
    including direct top-level JSON dispatch and idempotent replay.
  - [x] Repository quality gates pass on qualified `692041a1`, whose full
        Git tree is identical to merged `ad92a655`. The retained local Python
        evidence contains 4,206 tests, 30 skips and zero failures; its terminal
        output digest matches `sha256:aea1c7ededfc897df991433780e0eb509eaa7450384d09a4d0c2ce9a8340a6f0`.
        [PR #388](https://github.com/NVIDIA-dev/literate-ai/pull/388) records the
        accompanying lint, format, layout, OpenSpec, documentation, authority,
        wheel and installed checks. All 15 jobs of the merged revision's
        [hosted matrix](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34671435026)
        pass. The current public application service and filesystem
        adapter retain explicit publication, attachment forwarding, idempotent
        replay, target ambiguity and missing-runtime refusal. The CLI delegates
        to the exported adapter; the service and adapter import no CLI code.
        These source and test files are unchanged in integration `7ab1562c`.
        RELEASE-INTEGRATION-001 retains the fresh combined qualification and
        current lifecycle-receipt obligations.

### [x] CACHE-005 — Scope generated-source keys to effective target authority

- **Release target:** 0.9.0 (re-scoped 2026-09-01: had no explicit target)
- **Owner:** framework source-generation cache / authority composition
- **Direction:** A change to one language or build-system skill must invalidate targets
  that consume that skill without forcing unrelated language targets in a multi-target
  sample or project to regenerate solely because the project-wide lifecycle pin moved.
- **Conclusion:** Separate the project-level reviewed-authority identity from each
  generation target's effective authority closure. Keep the complete project identity
  in provenance and admission evidence, but key reusable generated source by the exact
  Component, selected Flavors, transitive skills, workflow/routing decisions, coding
  tool binding, and verifier contract that can affect that target's bytes.
- **Root cause (2026-09-02):** Exact installed-wheel Linux qualification changed only
  `test_receipt_policy.runner_identity` after the Standard runner implementation
  moved. The admitted and current requests retained identical Component revision,
  generation key, Component plan, recipe, execution plan, coding-tool binding, and
  model, but the aggregate project-authority member changed accepted lookup from
  `sha256:453085d7...` to `sha256:9fe8518f...`. The worker therefore reported
  `source_cache.runtime_absent` even though the exact admitted source was present.
  Direct planning and cache inspection falsified Flavor/lock, framework, transport,
  and missing-object explanations.
- **Implementation (2026-09-02):** Accepted-source request semantics v2 excludes the
  whole-project authority identity together with orchestration/workspace custody.
  Full project authority remains in the unsanitized coding request and complete
  derivation key/provenance. Reusable lookup remains bound to the exact effective
  target closure, and repository lineage remains independently bound by every
  project-mode Component lock (`project_lineage_authority_identity`). No legacy
  entry is accepted under the v2 semantic identity.
- **Depends on:** immutable generation recipes, exact skill dependency graphs, and the
  current schema-v2 source derivation cache key
- **Implementation:**
  - [x] Measure and document which current cache-key member makes an unrelated C++ skill
        change invalidate Python, Rust, and JavaScript roundtrip targets.
  - [x] Define a versioned effective-target-authority identity while retaining the full
        project authority identity in provenance.
  - [x] Add positive invalidation tests for consumed skills and negative invalidation
        tests for unrelated language/build skills and narrative-only authority changes.
  - [x] Migrate cache lookup/publication fail-closed without accepting legacy entries
        under the narrower key.
- **Evidence:**
  - [x] Focused lookup tests prove aggregate project-authority drift changes the complete
        transaction key but not accepted lookup, while Component/context/prompt/tool/
        model authority changes still miss. Existing project-lineage tests prove a real
        repository-lineage change changes the lock authority while unrelated sibling
        Component changes do not.
  - [x] Installed-wheel key probes reproduce the real receipt-policy miss with every
        effective-target identity held constant. Exact-revision Linux continuation is
        retained under MULTI-ENTRYPOINT-001 / RELEASE-001.

### [x] DOCS-ROOT-001 — Keep GitHub-facing documentation paths in the root corpus

- **Owner:** documentation spine / packaging template
- **Direction:** The root README linked `docs/user/test-matrix.md`, but that file
  existed only under `src/literate_ai/project_template/`, so the published GitHub URL
  returned 404 even though initialized-project tests passed.
- **Conclusion:** Keep the private test-matrix guide in both intentional products: the
  framework repository's declared `docs/` corpus and the initialized-project template.
  Add a separate root-README regression that checks links against real root files so
  package-template data can never mask a broken GitHub-facing path again.
- **Evidence:**
  - [x] `docs/user/test-matrix.md` exists and is linked from `docs/README.md`; the
        root-README link regression, documentation graph tests, Mermaid renderer,
        project validation, lint, and format checks pass.

### [x] CI-NODE-001 — Move profiling artifact uploads to Node.js 24

- **Owner:** CI workflow / contributor tooling
- **Direction:** Remove GitHub's Node.js 20 deprecation warning from the Windows test
  shards by advancing the artifact-upload action to a Node.js 24 runtime.
- **Conclusion:** `actions/upload-artifact@v7` is the current GitHub.com release line,
  runs on Node.js 24, and is compatible with the workflow's existing named ZIP artifact
  upload. No download-artifact action is used in this repository.
- **Evidence:**
  - [x] `.github/workflows/ci.yml` uses `actions/upload-artifact@v7`; local format and
        lint gates pass; replacement CI run
        [32621882832](https://github.com/NVIDIA-dev/literate-ai/actions/runs/32621882832)
        executes the upload steps as `actions/upload-artifact@v7` without the Node.js
        20 warning. Remaining Windows shard failures predate and are unrelated to this
        action-runtime update.

### [x] FLAVOR-CONTAINER-001 — Add a containerization Flavor consuming packages, scripts, and parent-container inheritance

- **Owner:** flavor catalog / deployment axis
- **Direction:** Container deployment must be a first-class Flavor. It consumes the
  project's selected packaging Flavors and declared entrypoint scripts (the material a
  Dockerfile needs), and containers compose through the Flavor graph: a derived
  container Flavor declares a capability `requires` edge on the base container
  capability, so parent containers — including those inherited through the repository
  lineage DAG — are selected transitively and layer `FROM` bases in DAG order.
- **Conclusion:** Ship `flavors/docker/` as `deploy-docker` on the `deployment` axis
  (the first deployment-axis flavor; name follows the canonical `<axis-prefix>-<value>`
  scheme adopted by the mitigation program Phase 3). Inheritance is expressed with the
  existing typed capability composition rather than new machinery. A
  specification-to-source skill owns Dockerfile assembly practice.
- **Implementation:**
  - [x] Author `flavors/docker/flavor.md` + `openspec/spec.md` (requirements and
        WHEN/THEN scenarios for package/script consumption, parent-container `FROM`
        chaining, tool detection fail-closed, no unauthorized publishing) and register
        `docker`/`deploy-docker` selectors in the initialization adapter.
  - [x] Author `skills/specification-to-source/docker-container-application/SKILL.md`
        guiding Dockerfile assembly from selected packaging Flavors, Component
        entrypoints, and the ordered parent-container closure.
  - [x] Stamp the byte-equal template copy and add catalog tests (coordinates, axis,
        provided capability, selector resolution, template equality).
- **Evidence:**
  - [x] New flavor tests pass; `+docker` and `+deploy-docker` both canonicalize to
        `+flavor://literate-ai/deploy-docker`; SkillEvaluator passes the new skill;
        full non-live suite green from a cold checkpoint (2545 tests OK).

### [x] PROMPT-ROUTING-001 — Translate direct user prompts into bounded provider tasks

- **Owner:** agent-skill architecture / direct coding-agent boundary
- **Direction:** Adapt and pin
  [nidhinjs/prompt-master](https://github.com/nidhinjs/prompt-master) as a key
  Literate AI agent skill between a direct user's rough request and the selected coding
  provider. When MAC supplies a task envelope, MAC owns this translation and Literate
  AI must not run a second competing translation layer.
- **Conclusion:** Ship `skills/agent/prompt-master/SKILL.md` as provider-neutral agent
  guidance pinned to upstream commit
  `d15eabbe5d2122eedc060bae8a771381e9873d1b` (Prompt Master 1.7.0, MIT), adapted to
  preserve Literate AI authority: exact current specs/Flavors/skills/workflow/routing
  remain authoritative; task/correlation metadata remains non-semantic; the skill may
  sharpen task scope, evidence, stop conditions, and provider syntax but cannot mutate
  the generation recipe or authorize execution.
- **Implementation:**
  - [x] Add the adapted agent skill and byte-equal initialized-project template copy.
  - [x] Wire the direct-agent vs MAC selection rule into root onboarding and the agent
        ledger/skill architecture documentation.
  - [x] Add regression coverage for upstream pin/attribution, direct-provider trigger,
        MAC bypass, and template equality.
  - [x] Add deterministic product wiring: `litai prompt translate` wraps prompt-master
        with no model call; `--mac-envelope` and `LITAI_MAC_TASK_ID` fail closed.
        Do not edit `skills/agent/prompt-master/SKILL.md` (template byte-equality).
- **Evidence:**
  - [x] SkillEvaluator passes Prompt Master at Tier 1 (quality A, 90.2/100); upstream
        commit/version/license, direct trigger, MAC bypass, onboarding, and byte-equal
        template coverage pass in `tests/critical/test_prompt_master_agent_skill.py`; full
        Python suite passes (2553 tests, 27 skipped); lifecycle and documentation
        authority are re-pinned.
  - [x] `tests/smoke/test_prompt_routing.py` covers the CLI envelope, empty request, and
        MAC bypass.

### [x] CONVERT-FW-004 — Implement the phased conversion protocol (E2E baseline, rollback, shims, lift-and-shift)

- **Owner:** framework core / project initialization adapter / convert-project skill
- **Direction:** `litai init --convert` follows the phased protocol now codified in
  `skills/agent/convert-project/SKILL.md`: Phase 0 inspect-then-quarantine (see
  CONVERT-FW-005; quarantine remains); Phase 1 legacy analysis plus recorded
  local-cheap stages of the *original* project with full rollback on executed-stage
  failure; remote CI is recorded, not a local `make ci` gate; Phase 1.1 shim
  wrappers driving the quarantined toolchain with stubs for missing steps; Phase 1.2
  ADR-gated lift-and-shift to first-class entities with parity against the Phase 1.1
  baseline; Phase 2 native-rewrite ADR. The operation is documented as mutagenic.
- **Implementation:**
  - [x] Phase 0: already-initialized guard + `_legacy/` quarantine with git mv/mv
        discipline (CONVERT-FW-002).
  - [x] Phase 1a: harness inventory + top-level wrapper generation
        (MITIGATION-FW-002).
  - [x] Codify the full phase contract, gates, rollback procedure, and mutagenic
        warning in the convert-project skill.
  - [x] Phase 1b: deterministic E2E driver that executes recorded legacy commands,
        captures command/exit/log-digest/artifact identities into one workflow
        record, checks CI status when configured, and performs verified rollback
        (restore quarantine manifest, remove scaffold) on failure. The driver runs on
        a disposable exact copy so build products cannot dirty the quarantined source;
        remote CI is recorded evidence (CONVERT-FW-005 amends the earlier local-`ci`
        fail-closed rule).
  - [x] Phase 1.1: wrapper Component/skill/Flavor synthesis from the saved baseline,
        including loud-failing stubs for missing steps. Conversion emits a wrapper
        Component, build Flavor, pinned skill, complete workflow, and routing policy;
        executes every available stage through `litai.harness.mk`; and records
        successful exit/source-tree parity in `.literate/legacy-wrapper-parity.json`.
  - [x] Phase 1.2: lift-and-shift tooling moves the complete retained legacy tree,
        preserving its internal taxonomy, into the wrapper Component's
        `implementation/` authority (`git mv` when tracked, plain move otherwise),
        rewrites the wrapper path, proves post-move parity, records
        `.literate/legacy-lift-shift.json`, authors a project-local adoption ADR, and
        removes `_legacy/` only after success. This remains project reorganization;
        no source-to-specification transfer is claimed.
- **Evidence:**
  - [x] Integration test: fixture project converts, fails its E2E gate, and rolls
        back byte-identically to pre-convert state; a passing fixture records
        digest-only phase evidence, and a GitHub-only CI project without a local `ci`
        target converts with remote CI recorded (`tests/e2e/test_harness_inventory.py`).
  - [x] Integration test: passing Make and CMake fixtures convert through Phase 1.1
        with wrapper parity equal to the direct baseline source authority; missing
        stages remain loud-failing stubs (`tests/e2e/test_harness_inventory.py`).
  - [x] The same vertical slices prove Phase 1.2 moves the complete hierarchy into
        first-class Component authority, removes quarantine, keeps the generated
        wrapper executable, and links the adoption ADR into the documentation spine.
  - [x] Phase 2 is bootstrapped without prematurely rewriting source: conversion
        creates project-local ADR 0002, a lifecycle-valid native-rewrite roadmap owned
        by `ADOPT-002`, and an evidence-bound next action (`boundary-inventory`). The
        ADR requires one-boundary-at-a-time generation, independent acceptance,
        regenerative qualification, parity, and reversible retained-source deletion;
        it explicitly records that source-to-specification has not started.
  - [x] Phase 2 planning is emitted by `init --convert`: project-local ADR 0002 binds
        Phase 1.2 evidence, the active native-rewrite roadmap requires boundary
        inventory/classification before implementation, and retained source stays
        authoritative until each generated replacement independently qualifies.

### [x] CONVERT-FW-005 — Analyze-then-wrap convert gate (inspect before quarantine)

- **Owner:** framework core / harness inventory / convert-project skill
- **Priority:** high
- **Status:** complete; landed in [#174](https://github.com/NVIDIA-dev/literate-ai/pull/174)
- **Direction:** Keep quarantine-plus-harness conversion. Do not overlay. Kit showed
      convert `git mv`s the tree, copies and hashes it, then fails because GitHub CI
      is present without a local `make ci` and because `repo.sh` is invisible. Analyze
      in place first (`litai init --convert --plan`), author missing Flavors/skills
      (`repo-man`, multi-language, GitLab, nested Bazel), then mutate only when
      readiness is `ready`. Remote CI is recorded evidence, not a local executable
      gate. Host-heavy `repo.sh build` is recorded, not executed, unless
      `--run-baseline`. Python, Bazel, npm, and Go stay local-cheap. Mixed-language
      trees stamp one language-ecosystem default (C++ when present); `--plan` still
      lists the union. `blocked-no-driver` is informational. The wrapper must expose
      every detected operation root and must not `cd` outside the legacy tree.
- **Dependencies:** CONVERT-FW-004 (quarantine, baseline, shims, lift-shift remain).
- **Implementation:**
  - [x] `litai init --convert --plan` inspects in place and writes nothing.
  - [x] Mutating convert refuses `blocked-missing-catalog` (or `--allow-unready`);
        `blocked-no-driver` remains informational so notes-only trees still wrap.
  - [x] `repo-man` Flavor + skill; `--plan` lists python and cpp; init stamps one
        language-ecosystem Flavor; repo.sh / GitLab / nested Bazel detectors;
        cmake/cuda template files including CUDA `agents/openai.yaml`.
  - [x] Inventory `stages` list and `litai.harness.mk` per-root targets.
  - [x] Remote CI recorded; local-cheap baselines still run; tree hash only when a
        baseline actually ran.
  - [x] Synthetic repo_man fixture; Make/CMake slices stay green; GitHub-without-local
        `ci` converts instead of rolling back.
- **Evidence:**
  - [x] Unit tests in `tests/e2e/test_harness_inventory.py` cover plan, repo_man
        wrap, and the GitHub-CI protocol change.
  - [x] `litai init --convert --plan` against Omniverse Kit names kit/rendering/runtime
        and `repo.sh` without mutating the tree.

### [x] CONVERT-FW-006 — Lock planning must skip convert retained `implementation/`

- **Owner:** Component lock planner / convert-project skill
- **Priority:** high; blocks Kit ADOPT-002 `litai lock` on a converted tree
- **Direction:** Convert lift-shift places retained source at
  `components/<wrapper>/implementation/`. Lock catalog walks every
  `component_roots` directory looking for `component.md` and currently treats
  that retained tree as catalog, so a symlink (or >16k entries) fail-closes
  `component_lock.component_unsafe` / `catalog_limit` before any native Component
  can lock.
- **Conclusion:** A sibling `implementation/` next to `component.md` is retained
  source, not Component catalog. Do not recurse into it while discovering
  authorings. Native authority stays outside that tree.
- **Depends on:** CONVERT-FW-005.
- **Implementation:**
  - [x] Skip `implementation/` when it is a sibling of `component.md`.
  - [x] Unit test: retained tree may contain symlinks and a decoy `component.md`;
        lock planning still sees only the wrapper/native authoring.
  - [x] Convert-project skill names this skip so later converts do not put
        native authority under `implementation/`.
- **Evidence:** Kit `components/hdtest` `litai lock --check` current
  (`sha256:9945a5bbdd6a52efebe6c0284e4e1cf8d78f2c276477eb33d0054bdcc0cdb419`);
  unit test `test_retained_implementation_tree_is_not_cataloged`.

### [x] CONVERT-FW-007 — Plan/generate project-local language Flavors from their command profile

- **Owner:** generation preparation / Standard language command profiles
- **Priority:** high; blocks native-rewrite wraps that must not use catalog `lang-cpp`
  JSON `argv[1]` transport
- **Pull request:** [#180](https://github.com/NVIDIA-dev/literate-ai/pull/180)
- **Direction:** A descendant project may select a language Flavor whose `target` is
  not in `SUPPORTED_IMPLEMENTATION_LANGUAGES` (for example `cpp-posix`) so the
  hardcoded C++ JSON-argument prompt does not fire. `litai plan` currently fails
  closed with `unsupported implementation language` because required entrypoints are
  keyed only off Flavor `target`. Resolve the generated source entrypoint from the
  selected language Flavor's Standard command profile when one is contributed.
  Keep the catalog allowlist as fallback for fixtures without a profile. Do not add
  project-local target names to the framework language catalog.
- **Depends on:** [CONVERT-FW-004](../../roadmap/active-work.md#x-convert-fw-004-implement-the-phased-conversion-protocol-e2e-baseline-rollback-shims-lift-and-shift),
  [CONVERT-FW-006](../../roadmap/active-work.md#x-convert-fw-006-lock-planning-must-skip-convert-retained).
- **Implementation:**
  - [x] `_entrypoints` prefers `StandardLanguageCommandProfile.source_entrypoint`.
  - [x] Unknown `target` without a contributed profile still fails closed.
  - [x] Prompt injection for JSON `argv[1]` remains exact `languages == ("cpp",)`.
- **Evidence:**
  - [x] Unit tests: `cpp-posix` profile yields `source/main.cpp`; missing profile
        still errors; C++ JSON argv text is absent for `cpp-posix`
        (`tests/unit/test_language_command_profile_entrypoint.py`).
  - [x] Pull request opened as
        [#180](https://github.com/NVIDIA-dev/literate-ai/pull/180).
  - [x] Merged to `main` as
        [`fc61c8b8`](https://github.com/NVIDIA-dev/literate-ai/commit/fc61c8b80fbc590b65c40ffb97a2494955b47ff3)
        on 2026-08-27.

### [x] CONVERT-FW-008 — Do not invent a Make `test` gate; surface the failing command

- **Priority:** P0
- **Owner:** `src/literate_ai/adapters/harness_inventory.py`
- **Direction:** `litai init --convert --flavor make --flavor python --flavor linux`
  rolled back with `project.convert_legacy_gate_failed` / status 2. Convert records
  `make -f Makefile test` whenever a Makefile exists, without checking that the
  file declares a `test` target (unlike `ci`, which already uses `^ci\s*:`). GNU
  Make exits 2 for "No rule to make target". A Python `tests/` tree never becomes
  the test stage because Make claimed it first. The CLI message also drops the
  command and stderr, so the rollback looks unexplained.
- **Conclusion:** Record a Make test stage only when the Makefile declares `test:`.
  Let the Python pytest detector fill in when that target is absent. Include the
  recorded command and a bounded diagnostic excerpt in the gate-failure message.
- **Implementation:**
  - [x] Share the existing `ci` target regex as a Makefile-target helper.
  - [x] Skip `make test` when that target is absent; keep default-goal `make` as
        build.
  - [x] Put a bounded stderr/stdout excerpt on the failed phase and in the
        `ProjectInitializationError` message.
- **Evidence:**
  - [x] Makefile without `test:` plus `tests/` records `python -m pytest tests`
        (`test_makefile_without_test_target_does_not_invent_a_make_test_gate`).
  - [x] A failing Make test gate names the command and a diagnostic line
        (`test_failing_make_test_gate_names_the_command_and_diagnostic`).

### [x] CONVERT-FW-009 — Convert baseline must not copy local virtualenvs

- **Status:** complete (2026-08-28: convert omits host-local environments)

- **Priority:** P0
- **Release target:** 0.8.0 Unreleased
- **GitHub issue:** [#187](https://github.com/NVIDIA-dev/literate-ai/issues/187)
- **Owner:** `src/literate_ai/adapters/` convert baseline copy / harness execution
- **Direction:** `litai init --convert` runs auto-detected Make test in a disposable
      copy of the repository. That copy includes ignored local environments such as
      `.venv`. Console scripts keep absolute shebangs into the original checkout,
      which is already quarantined, so `.venv/bin/pytest` fails with "required file
      not found" / Make Error 127 even when the live tree's tests pass. The same
      class applies to copied `node_modules` launchers.
- **Conclusion:** The baseline temp tree must not carry host-local environments.
      Exclude common ignored env/build directories from the copy. If the recorded
      test recipe still invokes a path inside an excluded directory, fail with a
      typed diagnosis naming that command rather than a copied-interpreter 127.
      Do not rewrite shebangs inside a copied virtualenv. Not a 0.7.3 patch:
      convert is moving on this minor
      ([RELEASE-012](../../roadmap/active-work.md#release-012-080-unreleased-product-and-protocol-scope)).
- **Depends on:** [CONVERT-FW-008](../../roadmap/active-work.md#x-convert-fw-008-do-not-invent-a-make-gate-surface-the-failing-command)
- **Implementation:**
  - [x] Exclude `.venv`, `venv`, `node_modules`, and similar ignored env/build
        directories from the convert baseline copy.
  - [x] If a recorded recipe still points at those paths, fail closed with a typed
        convert error naming the command.
  - [x] Walk the Make goal's transitive prerequisite closure so an aggregate
        `test: test-python` still fails closed when the bound command lives on a
        prerequisite (issue #187 follow-on / PR #197 intent).
  - [x] Keep CONVERT-FW-008's "only record `make test` when declared" behavior.
- **Evidence:**
  - [x] A Makefile that calls `.venv/bin/pytest` plus a dummy venv with an
        absolute shebang does not fail because the copied interpreter is gone;
        it either uses a host interpreter or a typed error naming the
        environment-bound command.
  - [x] CONVERT-FW-008 focused tests still pass.
  - [x] Aggregate `test: test-python` still fails closed when the bound recipe
        lives only on the prerequisite
        (`test_convert_names_environment_bound_recipe_reached_through_prerequisite`;
        PR #197 intent / issue #187 follow-on).

### [x] MITIGATION-FW-002 — Land mitigation-program Phase 2 (harness wrapper, catalog single-source, topology de-hardcoding)

- **Owner:** framework core / project initialization / flavor catalog / generation
- **Direction:** Execute Phase 2 of
  [framework-defect-mitigation-program](../../roadmap/framework-defect-mitigation-program.md):
  deterministic harness inspection + top-level wrapper during `init --convert`,
  catalog-derived Flavor selector tables, one physical flavor catalog, and removal of
  the hardcoded full-stack topology from the prompt builder.
- **Outcome:** All landed. `adapters/harness_inventory.py` emits
  `.literate/harness-inventory.json` and an executable `litai.harness.mk`
  (fail-closed on undetected targets); `detect_repo_flavors()` prefers `build-cmake`;
  selector tables derive from shipped `flavor.md` frontmatter (phantom
  `platform.service` axis removed); template flavors are byte-equal to the root
  catalog for every `literate-ai`-namespace flavor; the Rust/JS protocol moved wholly
  into Component authority with a domain-neutrality boundary test; SKILL.md scopes the
  `openspec/` prohibition precisely. Root `swift-*` toolchain flavors were corrected to
  stay applicable to `application.portable-json` (drift had replaced it), restoring
  co-requisite realization selection.
- **Evidence:**
  - [x] Vertical-slice tests execute the generated wrapper through real `make`
        invocations and fail closed otherwise
        (`tests/e2e/test_harness_inventory.py`).
  - [x] Byte-equality enforced across all shared flavor directories
        (`tests/unit/test_package_flavor_catalog.py`).
  - [x] Full non-live suite green from a cold checkpoint (2548 tests OK); lifecycle
        driver TCB re-pinned (`scripts/review_lifecycle_driver.py --record`);
        documentation authority review refreshed.

### [x] CONVERT-FW-002 — Quarantine pre-existing content during `litai init --convert`

- **Owner:** framework core / project initialization adapter
- **Direction (Phase 1 / D1):** Conversion must not interleave legacy files with the
  stamped taxonomy. Move every pre-existing target-root entry except `.git/` into a
  unique `_legacy/<timestamp>-<digest>/` aside directory — `git mv` for tracked entries
  inside a Git work tree, plain `mv` otherwise — preserving the legacy hierarchy intact,
  then stamp scaffold onto the clean tree and delete the preservation branches.
- **Implementation:**
  - [x] Add `_quarantine_existing_tree` with git-detection, per-entry `git mv`/`mv`
        discipline, symlink-escape refusal, and a returned move manifest surfaced as an
        additive optional key of the initialization result.
  - [x] Remove `.gitignore` merge, agent-shim delegation append, and
        `_ensure_convert_docs_reachable` doc-linking paths made dead by quarantine;
        simplify convert-mode scaffolding to the standard path.
  - [x] Reword `project.already_initialized` to state conversion is unnecessary and
        `litai update` may be needed (Phase 1 / D3).
  - [x] Ignore `ap-export/` and agent worktree artifacts in `.gitignore`
        (Phase 1 / C2-hygiene).
  - [x] Align `docs/architecture/component-flavors.md` init-default text with the
        implemented `build-make` default and list the `documentation.ecosystem` axis
        (Phase 1 / B6-docs).
- **Evidence:**
  - [x] New unit tests: git-tracked moves appear as renames in `git status`; non-git
        and mixed trees convert; legacy hierarchy byte-equal beneath the aside dir;
        double conversion raises `project.already_initialized`; root symlinks escaping
        the tree are refused (`tests/e2e/test_project_initialization_adapter.py`).
  - [x] Full non-live pytest suite green from a cold checkpoint (2545 tests OK);
        lifecycle-driver TCB re-pinned and documentation authority review refreshed.

### [x] LAYOUT-002 — Make this repository obey its own Python and generic layout rules

- **Owner:** framework packaging / contributor tooling / repository taxonomy
- **Direction:** Keep the repository root as a small, conventional orientation and
  packaging surface. Python importable product code belongs under `src/`, tests under
  `tests/`, executable maintenance entrypoints under `scripts/`, authored tool projects
  under `tools/`, and every disposable tool/build product under `_build/`. Framework
  taxonomy roots (`components`, `flavors`, `skills`, `workflows`, and `routing`) remain
  visible because they are first-class authority rather than Python clutter.
- **Conclusion:** Move the custom PEP 517 backend out of the root into a dedicated
  authored build-tool package; prevent root `__pycache__`; relocate npm dependency
  installation from `tools/openspec/node_modules` into `_build/tools/openspec`; and
  document which otherwise numerous root entries are conventional project metadata,
  Literate AI authority, or candidates for later consolidation. Do not preserve legacy
  import or cache paths while this unreleased repository can roll forward cleanly.
- **Depends on:** CACHE-002 and LAYOUT-001
- **Implementation:**
  - [x] Produce a tracked-versus-generated top-level inventory and judge it against
    generic repository and Python `src`-layout conventions.
  - [x] Move `literate_ai_build_backend.py` beneath `tools/build_backend/`, update the
    PEP 517 `backend-path`, imports, custody tests, and distribution-root resolution.
  - [x] Make repository Python invocations suppress root bytecode as defense in depth;
    prove normal tests and wheel hooks do not create root `__pycache__`.
  - [x] Stage the OpenSpec/Mermaid npm tool project and its `node_modules` entirely
    beneath `_build/tools/openspec`, while retaining only authored manifests and scripts
    under `tools/openspec`.
  - [x] Gate both the current index and every reachable Git object against committed
    `node_modules`, `_build`, `__pycache__`, and bytecode; a discovered historical
    dependency tree requires an explicitly coordinated history rewrite, not a normal
    deletion commit.
  - [x] Add generic and Python repository-layout guidance to the generation skill
    taxonomy without duplicating product requirements into Component specs.
  - [x] Update the repository map and contributor documentation with a concise rationale
    for each retained top-level authority or conventional packaging file.
- **Evidence:**
  - [x] Root inventory contains no importable Python implementation module and no
    `__pycache__`; wheel/editable hooks still resolve from an sdist and a clean checkout.
  - [x] Focused package, wheel, Make-tool, initialization, layout-skill, and CodeGraph
    exclusion tests pass, and `make clean` removes staged Node and Python build products.
  - [x] Pre-cleanup Git audit found no `tools/openspec/node_modules` path in the current
    index, any reachable commit, or any reachable object. The 633 MB tree existed only
    as ignored working-copy state, so no history rewrite is necessary.
  - [x] macOS evidence: the two new layout skills and all affected language skills
    passed SkillEvaluator; 165 focused layout/cache/staging/wheel/init tests passed; an
    sdist contained and successfully loaded the relocated backend to build a wheel;
    staged npm tooling rendered 115 Mermaid diagrams; CodeGraph excluded `_build`; and `make clean`
    removed the complete npm tree, including `.bin` symlinks, without following them or
    touching `generated/`.

### [x] FLAVOR-004 — Make cross-axis Flavor compatibility and Swift host realization explicit

- **Priority:** P0
- **Owner:** framework Flavor contracts, lock/plan resolution, Standard preflight,
  selector grammar, and built-in Flavor catalog
- **Direction:** Separate portable language policy, generic OS policy, and the
  platform-specific toolchain realization selected when they are combined. Swift is
  the forcing case: macOS should detect Apple developer tooling, Linux and Windows
  should select an exact supported Swift distribution or fail before model egress, and
  unsupported tuples must never reach generation. Canonical Flavor identity and CLI
  selection must remain unambiguous as catalogs grow.
- **Conclusion:** Keep `implementation-swift` OS-neutral; add exact toolchain-realization
  Flavors constrained by OS, a typed compatibility contract resolved into the lock, and
  a deterministic host preflight before source generation. OS Flavors contribute only
  generic platform discovery/conventions; conditional developer-tool requirements
  belong to the selected realization. Preserve short aliases only when unique and add
  axis-qualified and full-coordinate selectors for collision-free use.
- **Depends on:** FLAVOR-DAG-001
- **Next action:** [complete] Maintain the supported Swift platform matrix and its
  official remediation links as upstream support changes.
- **Implementation:**
  - [x] Add typed cross-axis compatibility clauses and exact toolchain-realization
        bindings without free-form document merging or implicit precedence.
  - [x] Reject unsupported or unresolved OS × architecture × language × toolchain
        tuples during lock/plan resolution, before any coding-model call.
  - [x] Add deterministic selected-toolchain host probes and structured remediation
        metadata; keep installation separately authorized.
  - [x] Add full-coordinate and axis-qualified selectors while retaining unique short
        aliases and rejecting ambiguous aliases with candidate diagnostics.
  - [x] Add `implementation-swift` plus supported platform-specific Swift toolchain
        realizations, Standard profiles, generation skill, and initialized-project
        packaging.
  - [x] Add an opt-in macOS developer-tools discovery surface without making Xcode or
        Command Line Tools mandatory for unrelated language Flavors.
  - [x] Update Flavor/target, installation, CLI, and architecture documentation and the
        initialized project template.
- **Evidence:**
  - [x] Contract/schema round trips reject malformed, contradictory, disjunctively
        unresolved, and unsupported compatibility declarations.
  - [x] Lock/plan tests prove supported Swift tuples resolve exact realizations and an
        unsupported tuple fails before model dispatch.
  - [x] Selector tests prove unique short aliases, axis-qualified aliases, full
        coordinates, and deterministic ambiguity diagnostics across namespaces.
  - [x] Host-preflight tests cover selected commands, missing platform tools, and
        remediation-available toolchains without performing installation; a live macOS
        probe resolved Apple Swift 6.3.3 through `xcrun`.
  - [x] `litai init --flavor flavor://literate-ai/lang-swift` packages only the Swift,
        Make, host-platform, and compatible toolchain authority required for the
        initialized project.
  - [x] Focused unit/schema/CLI tests, `make skills-check`, and the checkpointed
        `make python-check` pass. The exact clean Python run completed 1,893 tests with
        18 platform/native skips and no failures.

### [x] SAMPLE-MATRIX-002 — Bound default sample execution and make Flavor fanout explicit

- **Priority:** P0
- **Owner:** sample conformance runner, remote test-matrix fanout, initialized-project
  test defaults, and canonical built-in Flavor identities
- **Direction:** Prevent each new language or operating-system Flavor from multiplying
  every unpinned sample run. An unpinned sample executes exactly one tuple by default:
  `flavor://literate-ai/lang-python`, `flavor://literate-ai/build-make`, and the
  current host OS Flavor. Explicit sample pins remain authoritative, including
  intentional multi-language samples. Wildcard selectors explicitly expand the
  requested Cartesian matrix and route OS rows to compatible fleet workers.
- **Conclusion:** Treat wildcard selection as test-matrix expansion before ordinary
  exact Flavor resolution. Persist and report only full canonical Flavor coordinates;
  retain short forms solely as input compatibility aliases. Include exact expanded
  coordinates in local and remote checkpoint/cache identities so matrix runs reuse
  generation and build results without confusing different tuples.
- **Depends on:** FLAVOR-004
- **Next action:** [complete] Keep the supported wildcard matrix and fleet inventory
  synchronized as canonical Flavors are added.
- **Implementation:**
  - [x] Canonicalize built-in identities as `lang-*`, `build-*`, `os-*`, and
        `toolchain-*`; expand accepted short aliases at the CLI boundary.
  - [x] Default unpinned samples to Python + Make + current host OS, without changing
        explicitly pinned single- or multi-language samples.
  - [x] Add deterministic full-coordinate language, build-system, and OS wildcard
        expansion and reject incompatible tuples before model dispatch.
  - [x] Route expanded OS rows only to compatible fleet workers and include the exact
        tuple in reports and checkpoint identities.
  - [x] Preserve source-generation and build caches across opt-in matrix runs.
  - [x] Update sample pins, initialized-project test guidance, CLI help, and user docs
        to show full canonical coordinates.
- **Evidence:**
  - [x] Tests prove an unpinned sample runs one host tuple by default.
  - [x] Tests prove explicit multi-language pins remain multi-language.
  - [x] Tests prove wildcard selectors expand the supported Cartesian product,
        incompatible combinations fail early, and fleet routing respects OS Flavor.
  - [x] Repeating the same expanded matrix uses the persistent generation/build cache
        roots and a stable, exact-selector checkpoint identity; changed selectors cannot
        resume another matrix.
  - [x] Focused tests, `make skills-check`, and checkpointed `make python-check` pass;
        the exact clean Python run completed 1,893 tests with 18 platform/native skips
        and no failures.

---

### [x] SKILL-ARCH-001 — Document and validate multi-output skill convention

- **Release target:** 1.1.0

- **Owner:** `docs/architecture/skills.md`, `skills/specification-to-source/`
- **Direction:** The VFI Editor case demonstrates a pattern not yet documented in
  literate-ai: a single Component spec authorizes generation of two language targets
  simultaneously (Python backend + TypeScript frontend) tied by a shared protocol schema.
  The coding agent generates `source/backend/` and `source/frontend/` in one run, using
  the protocol JSON as the single source of truth. This pattern appears whenever a project
  uses an IDL, protobuf, OpenAPI spec, or custom schema to generate bindings in multiple
  languages. It has no new framework requirement — a skill can already instruct the coding
  agent to write multiple source trees — but it needs explicit documentation so project
  authors know it is supported and how to structure the skill body.
- **Conclusion:** Extend `docs/architecture/skills.md` with a "Multi-output skills"
  section that: (a) names the pattern, (b) explains when it applies (shared schema/IDL →
  N language targets), (c) prescribes the source tree layout (one subdirectory per target
  under `source/`), (d) states the constraint that all targets must satisfy acceptance
  criteria before the generation is considered complete, and (e) points to the
  `vfi-component` skill in the vfi-editor-internal project as the reference
  implementation. Do not edit generation-skill bodies in this slice: that would re-pin
  dependents. Optional `output_trees` on the skill contract is omitted when empty so
  existing identities stay unchanged.
- **Depends on:** none
- **Implementation:**
  - [x] Add "Multi-output skills" subsection to `docs/architecture/skills.md`
  - [x] Record in architecture docs (not generation-skill bodies) that multi-output
        generation is an extension of the single-output pattern, not a separate
        mechanism. Re-pinning `portable-application` or `repository-layout` is
        deferred to avoid identity blast radius.
  - [x] Name vfi-editor-internal as the external reference shape; there is not yet an
        in-tree sample.
- **Evidence:**
  - [x] `docs/architecture/skills.md` documents the convention; `output_trees`
        validation is covered in `tests/unit/test_skill_closure.py`.
        `make documentation-review-record` with `LITAI_SESSION_ID=dev` passes.
  - [x] A derived project authors a catalog skill with `source/backend` and
        `source/frontend` and passes public `litai project validate` without rewriting
        its skill bytes. The same CLI rejects non-source and escaping output paths.
        `tests.e2e.test_project_cli.ProjectCliTests.test_derived_project_accepts_multi_output_catalog_skill`
        and all six `tests.unit.test_skill_closure` tests pass. This proves authoring
        and validation; generated multi-language execution remains separate acceptance.

---

### [x] SKILL-ROUTING-001 — Behavioral regression harness for skill/capability selection

- **Owner:** skill authority / generation-recipe assembly; a new provider-neutral
  evaluation harness, not a specification-to-source skill itself
- **Direction:** Skill and capability-contract selection is validated structurally today
  (schema shape, DAG acyclicity, exact pinned identities) but never behaviorally against
  real prompts/requests — nothing checks that the *right* skill actually gets selected
  for a given generation intent, or notices when one only appears to because its
  description's vocabulary happens to overlap a prompt rather than because the match is
  meaningful. Surfaced by surveying `example-web-tooling` (an internal, independently evolved,
  mature MCP server exposing ~35 `SKILL.md`-shaped web/frontend skills): its
  `scripts/diagnosis.ts`/`scripts/corpus.ts` run synthetic prompts against the real skill
  corpus and classify each outcome as correct pick, misroute (wrong skill won),
  over-greedy (a skill fired when it should not have), or fragile pass (the right skill
  matched, but the description's overlap with the prompt was thin enough that the match
  likely came from the model's training priors rather than the doc actually being read).
  This is a real, evidenced gap-class, not a hypothetical: this framework's own
  `COVERAGE-GAP-001`/#64 already establishes that a green build/test signal is not proof
  of completeness for *generation*; the same failure mode exists, unaddressed, for
  *skill/capability selection* upstream of generation.
- **Conclusion:** Add a provider-neutral evaluation harness that runs a corpus of
  synthetic generation prompts/requests against a project's actual skill and capability
  catalog and classifies each outcome the way `example-web-tooling`'s harness does (correct /
  misroute / over-greedy / fragile-pass), rather than only checking selection
  structurally. Scope it as a `litai`-level diagnostic (e.g. `litai skills evaluate` or
  similar), not a new specification-to-source skill, since its subject is the routing
  mechanism itself, not any one Component's generated source.
- **Depends on:** none; complements `SKILL-DEP-001`'s exact dependency-closure work
  (that resolves *what* gets pulled in once a skill is selected; this validates *that
  the right skill got selected* in the first place)
- **Implementation:**
  - [x] Added `src/literate_ai/skill_routing_evaluation.py`: loads every declared
        `specification-to-source` skill's real frontmatter `description`/`title` (via
        `parse_authoring_markdown`, the same raw-frontmatter parser
        `ResolvedSpecificationToSourceSkill.from_reference` uses internally but doesn't
        surface `description` from — it projects only the narrower typed manifest
        fields), tokenizes it, and scores it against a prompt.
  - [x] Fragile-pass detector: Jaccard overlap (`|intersection| / |union|`) between
        prompt and candidate tokens, not recall-on-prompt-only. Deliberately chosen
        after discovering recall-on-prompt structurally favors long, vocabulary-rich
        descriptions (this repository's own `generate-nvidia-cuda-application`
        description is far longer than its siblings' one-liners and won essentially
        every prompt under the naive formula purely by having more chances to share an
        incidental word) — Jaccard's union denominator makes a description's own
        irrelevant extra vocabulary work against it instead of for it. A small stopword
        list (function words, plus the literal "Use for Literate AI workflow tasks."
        boilerplate every skill description in this catalog shares) keeps unrelated
        prompts from over-firing on shared connective words.
  - [x] Corpus format: a JSON array of `{case_id, prompt, expected_skill_id}` (`null`
        expected means the prompt should route to nothing); `load_skill_routing_corpus`
        rejects malformed/duplicate/empty corpora and unknown `expected_skill_id`s
        before scoring anything.
  - [x] Wired as `litai skills evaluate CORPUS [--project PATH] [--fire-threshold N]
        [--fragile-threshold N]` (`src/literate_ai/cli/skills.py`), a new top-level
        command group parallel to `cache`/`catalog`, separate from `project validate`.
        Documented in `docs/user/configuration-and-cli.md`.
  - [x] Validated against this repository's own 17-skill catalog first:
        `tests/fixtures/skill_routing/literate_ai_catalog_corpus.json`, a 16-case seed
        corpus covering every language-portable-application skill, the two richer
        service/dashboard skills, two "should never fire" prompts, and one known-vague
        prompt.
- **Evidence:**
  - [x] Running the seed corpus against the real catalog reproducibly reports a
        `misroute` for a known-ambiguous pair
        (`portable-specification-planning`/`portable-application-implementation` — a
        real, informative finding: these two skills are semantically adjacent by
        design) and a `fragile_pass` for a genuinely thin match, not a silent
        correct-pick for either — `tests/smoke/test_skill_routing_evaluation.py::RealCatalogEvaluationTests::test_seed_corpus_mostly_routes_correctly_with_one_known_ambiguity`.
        A dedicated synthetic-fixture test
        (`test_known_ambiguous_pair_reproducibly_misroutes_or_fragile_passes`) makes the
        same property deterministic and independent of the real catalog's content
        drifting later.
  - [x] The harness never claims a selection is validated purely because it was
        structurally well-formed: `project validate`'s schema/DAG checks are entirely
        untouched by this work, and `evaluate_skill_routing` fails closed
        (`skill_routing.expected_skill_unknown`) rather than silently accepting a
        corpus that references a skill outside the real catalog.
  - [x] Full test suite (19 tests: scoring/classification, corpus loading, real-catalog
        evaluation, CLI wiring) passes; `litai skills evaluate` is reachable through the
        existing generic scoped-help mechanism (`litai help skills evaluate`) with no
        additional wiring.

---

### [x] GENERATION-008 — Detect an unusable selected coding CLI and fall back automatically

- **Release target:** 1.1.0

- **Priority:** P1
- **Owner:** `src/literate_ai/adapters/models/coding_cli.py` (`select_coding_cli`)
- **Direction:** `GENERATION-004`/#31 closed with a configurable priority order
  (`LITERATE_AI_CODING_CLI_PRIORITY`) but explicitly left open "a real usability/
  authentication probe... if a project needs per-host dynamic selection rather than a
  static configured order." That deferred case is no longer hypothetical: this session
  independently hit `codex` failing closed mid-release with "You hit your spend cap set
  by the owner of your workspace," requiring a manual `CODING_CLI=claude` override to
  make any progress on the `installed-project-e2e`/`samples` release gates. Surveying
  `~/Src/telemetry-dashboard` (an independent downstream project) found its own
  `verification/release-gate.sh` permanently hardcodes the identical override, with a
  comment citing the identical root cause ("`CODING_CLI` is pinned to claude per
  LITAI-001 (litai's own fixed codex-first default-CLI priority picks codex regardless
  of auth state)"). Two structurally unrelated projects independently converging on the
  same manual workaround for the same failure mode is a strong signal this belongs in
  the framework's default selection behavior, not in every project's own scripts.
- **Conclusion:** Extend `select_coding_cli` (or the point where a selected CLI's process
  is first invoked) to detect a fail-closed usability condition — authentication failure,
  spend-cap/quota rejection, or another CLI-reported hard denial distinguishable from
  ordinary generation flakiness — and fall through to the next entry in the configured
  priority order instead of surfacing the failure directly, at least for the specific,
  detectable "this CLI is currently unusable regardless of retry" class of error. Do not
  attempt a general authentication/capability probe run speculatively before every
  invocation (GENERATION-004 already considered and deferred that as the larger, less
  evidenced option); scope this to reacting to an already-observed hard denial.
- **Depends on:** `GENERATION-004`'s `LITERATE_AI_CODING_CLI_PRIORITY` mechanism
- **Implementation:**
  - [x] Enumerate only observed hard-denial signatures: Codex's workspace spend-cap
        wording and Claude's individual spend-limit wording (recorded during the
        RELEASE-006 live recovery above). Cursor Agent and OpenCode quota lists
        remain intentionally empty until a real denial is observed; each already
        retains its separate authentication-denial classification.
  - [x] Distinguish this class from ordinary transient generation flakiness: a new
        `coding_cli.quota_denied` typed error, checked only after the existing
        `coding_cli.authentication_required` classification (including its
        `login status` secondary probe) rules out an authentication cause, and only
        for a nonzero exit status — `GENERATION-006`'s `generated_metadata_invalid`
        retry path is untouched and stays exit-code-independent.
  - [x] On a detected hard denial (`authentication_required` or `quota_denied`), fall
        through to the next PATH-available CLI in the configured priority order (via new
        `_select_fallback_coding_cli`) for the remainder of the `generate()` call,
        logging `coding_cli_fallback` with the abandoned/adopted CLI names and reason.
        Bounded automatically: each attempted CLI name is tracked and excluded from
        further fallback, so the loop terminates once the priority order is exhausted
        and re-raises the last real denial (not a synthetic "exhausted" error).
  - [x] `CODING_CLI=<name>` (checked via the same truthy-env condition
        `select_coding_cli` itself uses) disables fallback entirely — a hard-denied pin
        raises immediately, never silently reroutes to a CLI the caller didn't ask for.
  - [x] Both `CodingCliSourceGenerator.generate()` and
        `CodingCliTaskRunner.run_json_task` apply the same bounded authentication/quota
        fallback. An explicit CLI pin or resolved generation model scope prohibits
        cross-provider fallback; select a healthy provider before locking that scope.
- **Evidence:**
  - [x] `tests/critical/test_coding_cli_generation.py::test_quota_denial_falls_back_to_the_next_available_cli`
        reproduces this session's exact scenario (codex denies with the real observed
        spend-cap phrase, `claude` is the next PATH-available CLI) and asserts the
        fallback CLI is invoked and the generation succeeds — no manual `CODING_CLI`
        override required.
  - [x] `tests.smoke.test_coding_cli_quota_fallback.CodingCliJsonTaskQuotaContractTests.test_json_task_quota_denial_falls_back_to_the_next_available_cli`
        covers the same fallback on `run_json_task` unless `CODING_CLI` is pinned.
  - [x] `test_explicit_coding_cli_pin_disables_fallback` and
        `test_quota_denial_reraises_original_error_when_fallback_is_exhausted` cover the
        two ways fallback must NOT silently mask a real denial: an explicit
        `CODING_CLI` pin, and a priority order with nothing left to fall back to.
  - [x] The full existing `test_coding_cli_generation.py` suite (108 tests, including
        every pre-existing authentication-classification and metadata-retry test) still
        passes unmodified — the new hard-denial branch never intercepts ordinary
        transient failures.
- **Current reconciliation:** Nine focused public generation/JSON-task regressions
  pass, including observed Claude denial, provider-specific classification, bounded
  exhaustion, explicit CLI pinning and resolved model-scope refusal. The JSON-task
  cases launch actual fixture executables; this closes the implemented fallback
  behavior without claiming that unknown provider quota signatures are recognized.

### [x] GENERATION-010 — Keep an explicit never-empty per-agent model stack

- **Priority:** P0
- **Release target:** 0.7.0
- **Re-scoped:** 0.9.0 (2026-09-01) for any remaining work; the historical target above records where the item originated / partially shipped.
- **Owner:** coding-session model cursor / specification language / spec-to-code
  converter
- **ADR:** [0018](../../decisions/0018-never-empty-per-agent-model-stack.md)
  (Accepted 2026-08-26)
- **Direction:** Coding sessions keep an explicit model stack. Frame 0 is the
  session model. Nested Component, Flavor, skill, and in-spec sectional changes
  push when the model changes and pop when leaving. Push, pop, and depth are
  part of the specification language. Each thread and each agent has its own
  stack. Popping the only remaining frame is a warning that logs the precise
  caller. Never go to stack depth 0.
- **Conclusion:** The lexical `ModelScopeBinding` stays the lock/cache identity.
  The runtime cursor is a `contextvars` stack that is never empty after
  `begin_session`. A last-frame pop is refused with `ModelStackPopRefusedWarning`
  and a `model.stack.pop_refused` event naming file, line, function, and any
  specification location. Do not use a process-global list. Do not wait on
  [ADR 0011](../../decisions/0011-component-domain-structure-literate-markdown-v2.md)
  for sectional directives.
- **Depends on:** [GENERATION-011](../../roadmap/active-work.md#generation-011-pin-live-qualification-to-an-explicit-user-configured-cli-and-model)
  for the live-test session model that becomes frame 0 on that path;
  [RELEASE-009](../../roadmap/active-work.md#release-009-qualify-and-publish-070-with-full-gate-fan-out)
  includes this in the `0.7.0` cut.
- **Next action:** Complete. ADR 0018 is Accepted; implementation and unit
  evidence are recorded. Live fan-out remaining evidence stays on GENERATION-011
  / RELEASE-009.
- **Implementation:**
  - [x] Per-context stack with `begin_session`, `push`, `pop`, `depth`, and
        `current`; frame 0 is the session model.
  - [x] Last-frame pop warns and logs caller file, line, function, plus any
        specification location; depth stays 1.
  - [x] Specification-language HTML comments and additive
        `coding-model-selection@2` `stack` operations.
  - [x] Converter generation uses the top of the stack.
  - [x] Document the stack language in user generation/CLI guidance.
- **Evidence:**
  - [x] Unit tests prove the stack never empties, threads/contexts isolate,
        and a pop of the last frame warns with the caller's precise location.
  - [x] ADR 0018 `Status` reaches `Accepted`.
  - [x] `0.7.0` changelog names the never-empty stack and the last-frame
        warning.

### [x] CONTEXT-001 — Admit locked local asset metadata to bounded generation context

- **Priority:** P0
- **Release target:** 0.4.1 — deferred out of 0.3.0 scope; not on the 0.3.0
  release-blocking path.
- **Re-scoped:** 0.9.0 (2026-09-01) for any remaining work; the historical target above records where the item originated / partially shipped.
- **Owner:** framework Component generation-context contract
- **Direction:** A generated application with a locked local binary asset exposed that
  the asset is planned as `local-asset-metadata` but rejected while constructing the
  bounded coding context, before any model egress.
- **Conclusion:** This is a framework consistency defect, not project-specific policy.
  Keep raw authored asset bytes outside the prompt; admit only the already-defined,
  identity-bound `AuthoredBinaryAsset` metadata projection with ordinary local-authority
  visibility. Assemble planning and source execution from the same exact locked asset
  tuple, admitting its bytes once to candidate CAS custody. Preserve rejection of
  acceptance oracles, dependency internals, inverse journals, and transitive interfaces.
  If a trusted source runner rejects that custody, preserve its stable diagnostic code
  instead of flattening it to `runner-failed`.
- **Depends on:** existing Component asset and bounded-context contracts
- **Implementation:**
  - [x] Add `LOCAL_ASSET_METADATA` to the sole allowed-visibility table as local
        authority.
  - [x] Extend the adversarial context fixture and add a regression proving exact local
        asset metadata is accepted in canonical order.
  - [x] Pass one CAS-admitted locked asset tuple to both Standard rebuild planning and
        its cached source-generation runner.
  - [x] Preserve a trusted runner exception's stable string code at the scheduling
        boundary while retaining `runner-failed` for uncoded exceptions.
  - [x] Materialize that same exact asset tuple from candidate CAS custody into the
        fresh source workspace before local tree registration, so the filesystem tree
        and immutable candidate identity cover the same bytes.
- **Evidence:**
  - [x] All eight focused Component-generation-context tests pass under Python 3.14.6;
        Ruff format and lint pass for the changed Python files.
  - [x] Focused Standard rebuild assembly, source scheduling, coding-CLI custody, and
        Standard project factory regressions pass: all 44 tests completed under Python
        3.14.6; changed-file Ruff lint and format checks pass.
  - [x] Focused source-generation and local-custody regressions prove a binary asset is
        present byte-for-byte in the registered source tree and cache replay.

### [x] UPDATE-SOURCE-INDEX-001 — Keep project updates compatible with required source intelligence

- **Priority:** P0
- **Owner:** repository update transaction / project source-intelligence validation
- **Direction:** Updating an initialized descendant stages inherited catalog files before
  validating the composed project. Those writes necessarily make a current CodeGraph
  index stale, so validation cannot explicitly suppress synchronization when project
  maintenance requires current source intelligence.
- **Conclusion:** Validate the staged repository update with ordinary source-intelligence
  synchronization enabled. Keep catalog, lineage, provenance, and validation rollback
  transactional; do not weaken the descendant's required source-intelligence policy.
- **Depends on:** current repository-lineage update and project-validation contracts
- **Implementation:**
  - [x] Stop disabling source-intelligence synchronization in the repository update
        validation boundary.
  - [x] Add a regression that observes the validation call and requires synchronization
        after inherited files are staged.
- **Evidence:**
  - [x] Focused repository-update and repository-initialization tests pass (3 tests);
        commit `898b6c4` is the landed implementation authority.

### [x] ROADMAP-OWNERSHIP-001 — Keep parent and downstream work with their owners

- **Priority:** P0
- **Owner:** roadmap governance and `record-user-directed-work`
- **Direction:** A child project may expose a defect or reusable improvement owned
  strictly by a parent Component or repository. Send that change to the parent when the
  agent has Git access; otherwise retain it in the child's own repository. Conversely,
  Literate AI must not absorb a downstream product's mission vocabulary, milestones,
  repository paths, or release gates merely because that product exposed a framework
  defect.
- **Conclusion:** Classify ownership before editing. Put provider-neutral parent
  contracts, fixtures, and reusable guidance in the parent. With authenticated write
  access, contribute them through a reviewable parent branch/commit or pull request,
  never an unreviewed direct-default-branch mutation. Without access, keep the local
  override or proposed patch and its work item in the child. Product recovery and
  qualification always remain in the downstream queue. Reciprocal work-item, commit, or
  pull-request references preserve traceability without making either repository's
  release gate depend directly on the other.
- **Depends on:** repository lineage, project-local durable work queues, and the
  detailed-roadmap lifecycle
- **Implementation:**
  - [x] Remove downstream product names and product-owned recovery checks from generic
        cache, bounded-context, repository-update, and candidate-repair work items.
  - [x] Teach the framework and initialized-project work-recording skills to classify
        parent-owned changes, contribute them upstream when authorized, and retain them
        locally when upstream Git access is unavailable.
  - [x] Record the affected product qualification in its own repository without moving
        any product Component or mission policy into Literate AI.
- **Evidence:**
  - [x] A repository-wide authority search finds no downstream product identifier in
        Literate AI source, skills, tests, samples, or the active roadmap.
  - [x] SkillEvaluator passes both changed inherited skill surfaces, and 52 focused
        initialization/documentation tests prove the ownership rule is
        inherited, while both repositories retain independently executable gates.

### [x] UPDATE-APPLY-001 — `litai update --apply` must not abort the whole transaction on one catalog-import collision

- **Priority:** P1
- **GitHub issue:** [#133](https://github.com/NVIDIA-dev/literate-ai/issues/133)
- **Owner:** `src/literate_ai/adapters/repository_updates.py` (`_updated_imports`)
- **Direction:** `litai update .` (plan-only) correctly classifies files per-file
  (`unchanged`/`local-only`/`preserved-dynamic`/`upstream-only`/`upstream-added`/
  `conflict`), but `--apply` aborted the *entire* operation the moment
  `_updated_imports` found even one (kind, name) catalog-import identity collision
  between a locally tracked import and the freshly recomputed inherited plan —
  writing none of the plan's already-known-safe `upstream-only` files, not even ones
  structurally unrelated to the colliding item. Reproduced against
  `example-org/telemetry-dashboard`: 3 genuinely safe `upstream-only` skill files were
  blocked by an unrelated `flavor:javascript` conflict the project had deliberately
  and knowingly diverged from upstream.
- **Conclusion:** A catalog-import identity collision means the project's existing
  local provenance record for that one key should stay authoritative (not be
  overwritten by the inherited recomputation) — it never meant every other file's
  already-correct per-file classification should be discarded. `_updated_imports` now
  drops only the colliding inherited entries (keeping the existing local record
  intact) instead of raising; every file's write eligibility remains governed
  independently by `plan()`'s existing per-file classification exactly as before,
  which already keeps a diverged item's own files out of the safe `upstream-only` set
  regardless of this catalog-level fix. Confirmed this does not create a
  content/provenance mismatch: a file only ever writes when its own identity-based
  classification says `upstream-only`, independent of what the colliding entry's
  metadata claims.
- **Implementation:**
  - [x] Changed `_updated_imports`'s collision handling from
        `raise RepositoryUpdateError("repository_update.provenance_conflict", ...)` to
        silently excluding colliding `(kind, name)` entries from the inherited set,
        keeping the project's existing local (`kept`) entry unchanged for that key.
  - [x] `repository_update.provenance_conflict` is no longer raised by ordinary
        collisions; the error class/code remain defined for other genuine failure
        paths in the same module.
- **Evidence:**
  - [x] `tests/smoke/test_repository_updates.py::test_different_repository_import_collision_keeps_the_local_entry`
        (renamed from `..._remains_fail_closed`, which asserted the now-superseded
        hard-abort behavior) — a foreign-sourced local import collides with an
        inherited recomputation; `apply()` no longer raises, the local provenance
        record is preserved unchanged, and (since that file's content was already
        identical to baseline) nothing gets rewritten.
  - [x] `test_catalog_import_collision_does_not_block_unrelated_safe_files` — the
        direct reproduction of #133's report: one colliding catalog item (`python`,
        foreign-sourced) alongside a second, genuinely upstream-changed item
        (`macos`); the `macos` file classifies and applies as `upstream-only` while
        the `python` collision is preserved untouched, in the same `apply()` call.
  - [x] Full `tests/smoke/test_repository_updates.py` suite (9 tests, including the two
        above) passes.

### [x] UPDATE-PROGRESS-001 — Interactive `litai update` must show multi-stage progress

- **Priority:** P1
- **GitHub issue:** [#146](https://github.com/NVIDIA-dev/literate-ai/issues/146)
- **Owner:** `src/literate_ai/diagnostics.py`, `GitRepositorySnapshotProvider`,
  `litai update` CLI
- **Direction:** On an interactive TTY, `litai update` can sit for minutes with no
  output while Git fetches a parent. Operators conclude it is hung. `--progress` is
  consumed only as an inactivity heartbeat.
- **Conclusion:** Emit named stage lines to stderr when the process is interactive
  and `--json` is not set. Piped and `--json` output stay a silent machine envelope.
- **Depends on:** none
- **Implementation:**
  - [x] Add a run-scoped progress reporter that writes only when a TTY stream is bound.
  - [x] Report fetch, catalog, and classification stages from `litai update` /
        lineage resolution.
  - [x] Keep `--json` and non-TTY output unchanged.
- **Evidence:**
  - [x] `tests/unit/test_repository_parent_follow.py::ProgressReportingTests`
        proves a bound stream receives stage lines and an unbound reporter is
        silent.
  - [x] `tests/unit/test_repository_updates` + `test_repository_lineage` +
        `test_project_reparenting` (29 tests) still pass.

### [x] UPDATE-FOLLOW-001 — Track a moving parent and tell the truth when pinned

- **Priority:** P1
- **GitHub issue:** [#147](https://github.com/NVIDIA-dev/literate-ai/issues/147)
- **Owner:** repository parent selection, `litai update` human renderer, wheel init
- **Direction:** Wheel init persists an exact SHA as `requested_revision`, so
  `litai update` cannot follow later commits. The interactive renderer also reads
  top-level `counts` on a composite plan and always says nothing moved. There is no
  explicit jump to a newer release line.
- **Conclusion:** Persist `HEAD` as the default moving selector. Detect SHA pins and
  say so. Render the composite plan honestly. Allow `--unpin`, `--follow-ref`, and
  `--allow-major` as explicit selection changes (reparent, then update). Never jump
  silently.
- **Depends on:** UPDATE-PROGRESS-001
- **Implementation:**
  - [x] Change wheel `_default_repository_parent` to request `HEAD`.
  - [x] Fix `_human_update_text` for `literate-ai/composite-project-update@1`.
  - [x] Report exact-commit pins in the update envelope and human text.
  - [x] Add `--unpin`, `--follow-ref REF`, and `--allow-major`.
- **Evidence:**
  - [x] `test_installed_origin_default_parent_tracks_head_not_the_wheel_sha`,
        `tests/unit/test_repository_parent_follow.py`, and composite renderer
        tests in `test_cli_human_rendering.py` pass (17 focused tests).
  - [x] Focused repository update/reparent/lineage unit tests still pass.
  - [x] `test_cli_exposes_the_read_only_plan` reports parent selectors from the
        loaded store lineage, not a mocked update-plan contract.
  - [x] `make python-check` passed: 2565 tests, 27 skipped.
- **Follow-up:** `--apply` after a selector change still rewrites
  `.literate/imports.json` identities for catalog files that were refused
  because `--adopt-added` was not set. That is pre-existing apply semantics and
  is not part of this landing.

### [x] UPDATE-CLASSIFICATION-001 — `litai update` compares catalog-inherited files against the wrong reference

- **Status:** complete (2026-08-28: catalog-imported paths stay on the lineage plan)

- **Priority:** P1
- **GitHub issue:** [#141](https://github.com/NVIDIA-dev/literate-ai/issues/141)
- **Owner:** `src/literate_ai/adapters/project_updates.py` (`_catalog_import_paths`)
  plus lineage `_catalog_classification`
- **Direction:** Physics Workbench sample reparented to `v0.5.0` and had 33 framework files refused as
  `conflict` by `litai update --apply`. Most were not real drift: their local bytes
  already matched the parent repository's catalog copy at the resolved tag
  (`79ba1409`) byte-for-byte. The classifier was comparing against the installed
  wheel's `literate_ai.project_template` init-template snapshot instead of the
  resolved parent catalog's identity at the target revision — a legitimate
  distinction, since a catalog file can change after the template that scaffolded a
  project was captured, without every downstream project re-running `init`.
- **Conclusion:** For any file with catalog-import provenance (tracked in
  `CatalogImportsFile`), compare local bytes against that file's identity in the
  resolved parent catalog at the update's target revision, not the installed
  init-template snapshot. Template-scaffolded files (no catalog-import provenance)
  keep today's baseline-identity comparison unchanged. See
  [ADR 0007](../../decisions/0007-update-classification-and-semantic-merge.md) for full
  context; this half of that ADR is an ordinary bug fix and does not itself require
  further design review.
- **Depends on:** none; independent of `UPDATE-MERGE-001` below and may land first.
- **Next action:** none; classification fix landed. Remaining true conflicts use
      UPDATE-CONFLICT-RENDER-001 and UPDATE-MERGE-001.
- **Evidence:**
  - [x] Regression fixture proving a catalog-inherited file whose local bytes equal
        parent-catalog-at-target-revision (but differ from the init template)
        classifies as non-`conflict`
        (`test_catalog_inherited_file_matching_parent_is_not_a_framework_conflict`).
  - [x] Existing `litai update` classification tests still pass unchanged for
        template-scaffolded files.

### [x] UPDATE-CONFLICT-RENDER-001 — Show `litai update` conflicts as ours/theirs unified diffs

- **Status:** complete (2026-08-28: ours/theirs diffs on TTY and `--json`)

- **Priority:** P1
- **GitHub issue:** [#150](https://github.com/NVIDIA-dev/literate-ai/issues/150)
- **Owner:** `litai update` human renderer and JSON envelope
  (`_human_update_text`, composite plan files)
- **Direction:** Classification already names conflicts, but the TTY prints at
  most ten paths and `--json` prints SHA identities. Operators and LLMs cannot
  judge a conflict without fetching the three blobs themselves.
- **Conclusion:** Both formats are first-class. Human output is a unified diff
  with ours (local) / base / theirs (upstream) conflict markers, display-only.
  `--json` carries the same sides (identities plus bytes or reconstructable
  hunks) and the same `unified_diff` text. Do not write markers into the tree
  and do not auto-merge. Distinct from `UPDATE-MERGE-001` / ADR 0007.
- **Depends on:** none; can land before classification or merge-review work
- **Implementation:**
  - [x] For each `conflict` file, obtain baseline, local, and upstream bytes
        already available to the classifier.
  - [x] Render unified diffs with conflict markers on the TTY when `--json` is
        not set.
  - [x] Add the structured three-way evidence and `unified_diff` to `--json`.
- **Evidence:**
  - [x] Human fixture: one synthetic conflict prints a unified ours/theirs
        diff and does not write markers into the project.
  - [x] JSON fixture: the same conflict includes labeled sides and a
        `unified_diff` field matching the TTY text.
  - [x] Unchanged / already-current files are not dumped.

### [x] UPDATE-MERGE-001 — Optional coding-agent semantic review for true `litai update` conflicts

- **Priority:** P2
- **GitHub issue:** [#141](https://github.com/NVIDIA-dev/literate-ai/issues/141)
- **Owner:** `src/literate_ai/adapters/repository_updates.py`, `litai update` CLI
  surface, existing coding-CLI adapter (reused, not a new model-invocation surface)
- **Direction:** After `UPDATE-CLASSIFICATION-001` narrows false conflicts, some files
  remain genuine three-way conflicts (local overlay vs. newer upstream vs. baseline,
  all three different). Downstream Component/Flavor/skill drift does not always mean a
  file is completely divorced from its parent — the drift needs analysis to decide
  whether the correct merge favors the parent's content or the downstream project's,
  not a byte-only overwrite-or-refuse decision.
- **Conclusion:** See
  [ADR 0007](../../decisions/0007-update-classification-and-semantic-merge.md) for the
  full proposed design: an opt-in, plan-only review step that dispatches one
  coding-agent review per remaining conflict (keep-local / take-upstream / merge, with
  an identity-bound rationale), writing nothing until an explicit apply mode accepts
  it.
- **Depends on:** `UPDATE-CLASSIFICATION-001` (reduces the conflict set this operates
  on, though not a hard technical dependency); ADR 0007 reaching `Accepted` status via
  its planning cycle before implementation begins, per
  `skills/agent/release-project/SKILL.md`'s significant-feature-request sequence.
- **Historical scope:** the August implementation completed plan-only review.
      Actual merge application was deferred; UPDATE-MERGE-002 below owns its completion.
- **Evidence:**
  - [x] ADR 0007 `Status` reaches `Accepted`. Flag is `--review-conflicts`;
        per-conflict JSON is `literate-ai/project-update-conflict-review@1`;
        rationale lives in the plan envelope.
  - [x] Fake coding-CLI reviews propose keep-local and fail closed on unknown
        decisions (`tests/unit/test_project_update_conflicts.py`). `--apply`
        still writes only the mechanical subset.

### [x] REBUILD-RECEIPT-001 — Preserve finalized Standard rebuild authority

- **Priority:** P0
- **Owner:** Standard rebuild adapter and project test-receipt projection
- **Direction:** A descendant exercising the in-process Standard rebuild exposed that
  the rebuild path persisted only the nested compact receipt, discarding the finalized
  Component-lock and lifecycle/cache envelope required to prove current authority.
- **Conclusion:** Finalize the in-memory Standard receipt with the exact planned lock,
  cache control, decision, and lifecycle identities before either writing a candidate
  or committing it. Keep the provider-neutral receipt contract in Literate AI; the
  descendant retains its own recovery and release qualification.
- **Depends on:** finalized test-receipt candidate contracts and Standard source-cache
  configuration
- **Implementation:**
  - [x] Construct and return one typed finalized candidate from every successful
        Standard filesystem rebuild.
  - [x] Write and commit the finalized envelope instead of extracting its raw receipt.
  - [x] Document the persisted envelope boundary and update design traceability.
- **Evidence:**
  - [x] Seven focused Standard rebuild and project receipt tests pass from the review
        branch, including an exact-lock currentness regression.
  - [x] Commit `6cc2297` passes a clean 2,100-test Python attestation (26 live or
        hardware-gated skips), strict Ruff format/lint across 581 files, repository
        layout, OpenSpec, 102 rendered Mermaid diagrams, lifecycle-driver review,
        current CodeGraph, skill admission, and installed-wheel smoke.

### [x] SAMPLE-RETRY-001 — Retry attributable Swift source rejection

- **Priority:** P0
- **Owner:** provider-neutral sample candidate-replacement policy
- **Direction:** Swift's generated-source validator returns a typed source-rejection
  code equivalent to the already attributable C++ rejection, but the sample ladder
  currently stops instead of giving the coding model its bounded repair opportunity.
- **Conclusion:** Admit only `builder.swift_generated_source_rejected` to the existing
  generated-source build-rejection class. Do not broaden generic build failures or move
  descendant-specific evidence into the framework.
- **Depends on:** bounded sample candidate replacement and typed Swift validation
- **Implementation:**
  - [x] Add the exact Swift rejection code to the closed attributable set.
  - [x] Exercise both C++ and Swift codes through the same two-attempt regression.
  - [x] Update the traceability matrix to name both admitted source validators.
- **Evidence:**
  - [x] The focused sample-ladder candidate-replacement regression passes for both
        exact typed source-rejection codes.
  - [x] Commit `6cc2297` passes the same clean 2,100-test and deterministic repository
        qualification recorded by REBUILD-RECEIPT-001.

### [x] WORKFLOW-CATALOG-001 — Make workflows first-class, named, and composable

- **Exact-catalog completion evidence:** The test now copies the actual repository
      workflow and routing bytes into the disposable project, preserving their exact
      instructions, fallback policy and routing group. All nine workflow tests pass
      again in 348.351 seconds with authenticated Codex generation and no skips.
      `_build/nested-workflow-exact-live.log` is 109 bytes, SHA-256
      `a320a6af06724166f874cb62e9515444a263efa361ced145fa843001368c4367`.
      Documentation renders 121 diagrams from 545 Markdown files; OpenSpec,
      project validation, current documentation/driver reviews, lint and format pass.
      The first initialized-template run below is separate supporting evidence.
  - [x] Qualify the exact shipped nested workflow and routing catalog bytes.
- **Initialized-template evidence (2026-09-16 UTC):** `model-routing` 1.0.1 now selects
      the nested development workflow and matching routing policy. All nine workflow
      tests pass in 497.104 seconds with `LITERATE_AI_LIVE_SAMPLES=1` and no skips.
      The real configured Codex process generates the sample in a disposable initialized
      project through public lock/plan/generate commands; typed successful source
      custody binds the same Component lock and root revision, and the generated
      `main.py` exists. The separate negative test changes nested workflow bytes and
      public planning refuses the stale lock. The retained run is
      `_build/nested-workflow-live.log`; 23 surrounding planning/model tests and
      12 sample-plan/version-authority tests also pass. This is source-generation
      qualification, not compiled application or release attestation. The sample's
      offline application policy remains separate from source-generation routing.

- **Release target:** 1.1.0
- **Previous release target:** 0.9.0 (re-scoped 2026-09-01: had no explicit target)
- **Owner:** workflow catalog (`workflows/`), routing catalog (`routing/`), Component
  authoring (`component.md`'s `workflow_definition` selector)
- **Direction:** User feedback: workflows should not be "one workflow encoded according
  to personal taste at the root of the repository." A project needs multiple named,
  independently selectable workflows — starting with `dev`, `staging`, and `production`
  — and workflows should be able to nest arbitrarily.
- **Conclusion so far:** `workflow_definition` was already an ordinary catalog-relative
  path selector with no code-level cardinality restriction, so the missing piece was
  convention, not plumbing: give each named workflow its own directory
  (`workflows/<name>/workflow.md`, mirroring the `flavor.md` sentinel-directory
  pattern) instead of one flat file. Investigated and explicitly rejected: a
  `workflow://namespace/name` coordinate selector, because `ComponentContentSelector.uri`
  already fail-closes on any `"://"` scheme URI for every selector kind (skills,
  toolchains, model-selection, routing-policy, workflow) — loosening that shared
  validator to carve out one kind was judged too broad a security-relevant change to
  make unilaterally under this item.
- **Implementation:**
  - [x] Ship `workflows/production/staging/dev/workflow.md`,
    `workflows/production/staging/workflow.md`, `workflows/production/workflow.md` as one worked example of the nested,
    named-directory catalog convention, each paired with its own routing policy
    (`routing/production/staging/dev/routing.json`,
    `routing/production/staging/routing.json`, `routing/production/routing.json`) that
    progressively tightens `fallback_allowed`, `required_locality`, and the `generate`
    stage's `maximum_output_tokens`.
  - [x] Document the convention in "Named, nestable workflow catalogs" in
    `docs/architecture/authoring-and-record-formats.md`.
  - [x] Switch the real `model-routing` sample's `workflow_definition` to the
    nested development catalog and prove the full public lock → plan → generate
    path with the configured coding CLI, including typed source custody and actual
    generated source.
  - [x] Decide and implement genuine composition: parse-time optional frontmatter
    `extends:` overlays existing `stage_id`s and inserts new model stages after their
    last listed dependency. `staging` extends `dev` and inserts a non-tree `review`
    stage; `production` extends `staging` and tightens generate tokens. Extra guarded
    lifecycle stages remain forbidden. Build-time flattening was rejected.
  - [x] Decide whether `litai init` should scaffold new projects with the multi-workflow
    convention by default. Decision (user-directed): yes for `dev` only —
    `src/literate_ai/project_template/workflows/specification-to-source.md` was renamed
    to `workflows/production/staging/dev/workflow.md` (with its paired
    `routing/production/staging/dev/routing.json`) so a newly
    initialized project's `workflow_definition` defaults to the named `dev` workflow
    when a developer does not point a Component at a different one. `staging` and
    `production` are not scaffolded into new projects by default; a project opts in by
    copying them (or via `litai catalog copy`) once genuine composition exists.
- **Evidence:**
  - [x] `tests/e2e/test_workflow_markdown.py::NamedWorkflowCatalogTests` proves each of
    the three named workflows parses, declares its own `workflow_id`, and pairs with a
    distinctly-tightening routing policy.
  - [x] The live
    `NamedWorkflowCatalogTests.test_real_sample_locks_plans_and_generates_with_nested_catalog`
    passes against the actual sample's nested selector. The companion lock/plan test
    also proves changed workflow bytes refuse before generation.

### [x] RELEASE-OBS-001 — Report what the release gate said when it fails

- **Priority:** P0
- **Owner:** `src/literate_ai/project_releases.py`
- **Direction:** `litai release check` ran the declared gate with
  `capture_output=True` and, on failure, raised
  `release gate failed with exit status 2` while discarding the gate's stdout and
  stderr entirely. The gate is the longest step in a release, so a failure yielded one
  uninformative integer after a multi-hour run and the operator had to re-run
  `make release-check` by hand to learn which check failed. During 0.3.0 this wasted a
  complete gate run.
- **Conclusion:** Carry a bounded, whitespace-collapsed tail of the gate's own output
  into the raised error, preferring stderr and falling back to stdout, and say so
  explicitly when the gate produced no output at all. Bounded rather than a full
  transcript, because the gate emits megabytes of conformance JSON.
- **Implementation:**
  - [x] `_release_gate_failure_detail` summarizes a failed gate; `check_release`
    includes it in `release.gate_failed`.
- **Evidence:**
  - [x] `tests/e2e/test_project_releases.py::ReleaseGateFailureDetailTests` proves
    stderr preference, stdout fallback, the silent-gate message, and that the detail is
    bounded while keeping the tail.

### [x] FLAVOR-006 — Add a Flavor to an existing project without re-initializing

- **Milestone:** 0.4.1
- **Owner:** `litai` CLI (a new Flavor-composition verb), lock planning, project authority
- **Direction:** User feedback: "There is no way to add a Flavor to an existing project."
  A project started on macOS that later needs Linux support has no incremental path --
  the only route is `litai init` into a fresh tree plus a manual merge, which is wrong
  for what is conceptually a mixin.
- **Conclusion:** Treat a Flavor as a mixin that can be composed into an existing
  project. Adding one must fully re-derive the dependency graph, capability
  requirements, toolchain constraints, and every affected Component lock -- the
  correctness properties of a fresh init -- while leaving authored Components,
  specifications, and history in place. It is a re-resolution, not a re-scaffold.
- **Open questions to settle before implementing:**
  - Does this become `litai flavor add <selector>`, an extension of `litai update`, or a
    `--flavor` argument on an existing verb? Naming should make the re-resolution
    explicit rather than implying a mere edit.
  - Removal and conflict: `-flavor` selectors already exist for init; adding
    `flavor://literate-ai/lang-go` to a project pinned to a conflicting Flavor must fail
    closed with the same cross-axis rules `_require_flavor_relations` enforces today.
  - Which Component locks must be invalidated, and can any legitimately survive.
  - What the operation writes when a newly required toolchain is absent on the host.
- **Evidence:**
  - [x] A macOS-initialized project gains `os-linux` incrementally; authored Component
    Markdown is unchanged and `component.lock.json` beside it is deleted so the next
    lock re-derives. Full `litai project validate` after mixin remains a follow-up.
  - [x] Adding a conflicting Flavor (`python` + `go`) fails closed and mutates nothing.
  - [x] Adding a Flavor twice is a no-op rather than a duplicate contribution.

### [x] WORKER-HW-001 — Discover and refresh private worker hardware capabilities

- **Priority:** P1
- **Owner:** execution-worker catalog, SSH transport, and detect-before-install skills
- **Direction:** A private worker entry must be refreshable from bounded, read-only
  platform probes instead of relying on hand-maintained CPU, memory, and accelerator
  claims. Keep requested minimum execution requirements distinct from observed host
  capacity: routing intent is authored authority, while probe results are timestamped
  inventory that may change independently and remains in the ignored user catalog.
- **Depends on:** the existing explicit `--worker` selection contract and user-supplied
  `literate.workers.json`; no fleet scheduler or provisioning intelligence belongs here.
- **Next action:** Integrate the current observation into SSH lifecycle acceptance and
  the accelerator Flavor-selection boundary under `WORKER-001`; command dispatchers
  continue to supply observed execution facts through their existing typed result rather
  than gaining a second probe protocol.
- **Implementation:**
  - [x] Add a versioned observed-capability record for OS name/version, CPU architecture,
        physical and logical core counts when available, memory, probe time, probe-tool
        evidence, and a per-device GPU inventory. Do not overwrite minimum requirements.
  - [x] Use platform-specific, argv-bounded probes: Linux `/etc/os-release`, `uname`,
        `getconf`, and `/proc`; macOS `sw_vers`, `uname`, `sysctl`, and `system_profiler`;
        Windows non-interactive PowerShell CIM queries. Bound time and output and reject
        malformed or ambiguous results.
  - [x] On Linux and Windows, query `nvidia-smi` for device UUID, model, memory, driver,
        and compute capability. Its absence means no discoverable NVIDIA GPU; its
        presence with a failed query is a degraded/unknown observation, never a false
        empty inventory. macOS records NVIDIA probing as not applicable.
  - [x] Atomically refresh only the user-supplied ignored catalog, with dry-run and
        machine-readable output. Preserve endpoints, workspaces, parameters, commands,
        environments, authored requirements, unknown extension fields, and unrelated
        workers byte-semantically.
        The command never rewrites the worker catalog, so every authored field and any
        future extension remain byte-for-byte untouched. It atomically writes a separate
        ignored observation catalog, supports dry-run and subset refresh, and preserves
        unrelated typed observations. Unknown fields in the versioned observation schema
        fail closed rather than being silently carried as trusted facts.
  - [x] Keep selection deterministic and modest: Literate AI may match explicit
        requirements against observations, but dynamic provisioning, ranking, and
        hardware scheduling remain the future task dispatcher's responsibility.
        Typed observations now answer whether one exact worker satisfies authored OS,
        architecture, logical-core, memory, per-device GPU count/memory/model/vendor,
        CUDA, compute-capability, and SM minimums. They expose no search, ranking, or
        allocation method.
- **Evidence:**
  - [x] Fixture tests cover Linux, macOS, and Windows; absent, single, and multi-GPU
        NVIDIA results; driver failure; timeout; malformed output; SSH/authentication
        failure; atomic replacement; dry-run; and preservation of authored fields.
        Current focused tests cover Linux, macOS, Windows, absent/healthy/degraded NVIDIA,
        timeout, malformed output, unsupported command protocol, subset merge, dry-run,
        scoped help, atomic write, exact requirements, and multi-GPU per-device matching.
        The initialized-project fixture inherits the worker skill and ignores observation
        state. Command workers reject active probing with a typed unsupported-protocol
        result; their dispatcher result already reports observed execution facts.
  - [x] The complete private worker matrix is probed through its real transport, its
        ignored catalog is refreshed, and a second probe is idempotent apart from the
        explicit observation time. One `litai worker probe --all --dry-run` observed all
        six real workers concurrently: Apple M4 Pro macOS, two CPU-only Ubuntu hosts,
        one healthy Blackwell Ubuntu host, one CPU-only Windows host, and one Windows
        host with an installed but driver-degraded `nvidia-smi`.
        Two consecutive canonical writes were byte-semantically identical after
        normalizing only their explicit observation timestamps.

### [x] WORKER-008 — Attempt NTP clock sync during remote-worker host configuration

- **Priority:** P1
- **Owner:** `os-macos`, `os-linux`, and `os-windows` Flavor specifications plus
  detect-before-install host bootstrap
- **Direction:** Each OS Flavor used as a remote-worker host should attempt to
  synchronize its clock to a centralized NTP source such as `time.nist.gov` during
  host configuration. This is not a hard readiness requirement: missing privilege, a
  missing client, or a blocked NTP path should be logged and must not fail sample-worker
  capability readiness. Skewed clocks are a frequent coding-agent TLS and token failure
  mode.
- **Conclusion:** Keep the requirement in each OS Flavor `openspec/spec.md` rather than
  expanding the Standard command-profile schema. Honor it from the existing
  argv-bounded sample-worker bootstrap: native one-shot clients first (`sntp` /
  `ntpdate` / `w32tm`), POSIX fallback of a stdlib NTP query plus `date` when no client
  is present. Do not install NTP packages solely for this attempt, and do not fail
  `passed` when sync fails.
- **Depends on:** current detect-before-install bootstrap and the three OS Flavor
  specification roots
- **Next action:** None; Flavor specs, bootstrap attempt/log contract, and unit coverage
  are landed.
- **Implementation:**
  - [x] Require best-effort `time.nist.gov` sync in each OS Flavor specification and
        keep the init-template copies byte-identical.
  - [x] Attempt argv-bounded native sync during sample-worker host bootstrap; record
        `clock_sync` evidence; log failure on stderr; never install NTP packages solely
        for this step.
  - [x] On POSIX hosts without `ntpdate`/`sntp`, query NTP in-process and attempt `date`
        only when the offset is large; Windows uses `w32tm` without a persistent-config
        requirement succeeding.
  - [x] Keep bootstrap `passed` coupled only to missing sample-worker capabilities.
- **Evidence:**
  - [x] Focused host-bootstrap tests cover native success, skipped client, NTP/date
        fallback, and a failed attempt that leaves `passed` true.
        `PYTHONPATH=src .venv/bin/python -m unittest tests.unit.test_host_bootstrap
        tests.unit.test_package_flavor_catalog` — 29 tests OK, including template
        byte-identity for the three OS Flavors.
  - [x] Changelog Unreleased records the Flavor-owned host-config attempt.

### [x] SAMPLE-PORTFOLIO-002 — Close the two confirmed breadth gaps found in the 0.5.1 sample audit

- **Priority:** P2
- **Owner:** `component://literate-ai/sample-portfolio`,
  `docs/architecture/sample-portfolio-review.md`
- **Direction:** A user-requested breadth audit of all 22 current samples against the
  17 `specification-to-source` skills and 25 Flavors (2026-08-19, during the 0.5.1
  cycle) originally found four gaps. **Correction, same session, before implementation
  started:** the "12 orphaned skills" claim (every language- and build-system-specific
  skill unexercised by any sample) was wrong — it only checked a Component's
  `component.md` `authoring_inputs`, never checking whether the *Flavor itself*
  contributes a skill. `flavors/rust`, `flavors/cpp`, `flavors/python`, `flavors/go`,
  `flavors/javascript`, `flavors/swift`, `flavors/cmake`, `flavors/make`,
  `flavors/bazel`, and `flavors/cuda`'s `flavor.md` each already declare their
  corresponding specification-to-source skill as an `authoring_inputs` contribution,
  injected automatically whenever that Flavor is selected — confirmed directly by
  attempting to add one explicitly to a sample already selecting that Flavor, which
  failed generation with a duplicate-skill error. Only `repository-layout` and
  `python-repository-layout` (init-time scaffolding skills, not Flavor-contributed)
  are genuinely unexercised by any *sample*, and both already have unit-level coverage
  (`tests/unit/test_make_generation_skill.py`). See
  [ADR 0008](../../decisions/0008-samples-gate-live-generation-resilience.md)'s own
  correction for the full account — the same false claim initially misdirected that
  ADR's root-cause analysis for an unrelated release-gate flake.
  The two gaps that were independently verified and remain confirmed: (1) 13 of 22
  samples leave `implementation.language-ecosystem` unpinned, so they build Python-only
  under an ordinary `make samples` gate (the multi-language claim is real but dormant
  without an explicit `lang.*` override); `go`, `swift-linux`, and `swift-windows` have
  zero real coverage; (2) `samples/python-service-example` and
  `samples/react-dashboard-example` (the two newest samples) have no
  `samples/_harness/` directory at all — pure specifications, never generated, built,
  or verified by anything. SAMPLE-APP-STACK-001 now admits `persistent-service`
  and `web-application` in `SAMPLE_HARNESS_ENTRYPOINT_KINDS` generically (not a
  one-off). Wiring still needs harness `sample.json`, execution.json, and
  start/stop oracles — not a mechanical addition of an `execution.json` alone.
- **Conclusion:** (a) pin several currently-unpinned samples to non-Python languages so
  the matrix's real coverage matches its claimed breadth; (b) finish harness
  support for the `persistent-service`/`web-application` entrypoint kinds (kinds
  are admitted; start/stop oracles and `_harness` manifests remain), then wire
  the service/dashboard samples to it. (b) is still larger than a bug fix.
  **Completed 2026-08-30:** `publication-import` is pinned to
  `flavor://literate-ai/lang-javascript` on the default gate (`a4b6ad16`). Live
  generation passed with `cursor-agent` / `gpt-5.6-sol-high` (`variant_id`
  `javascript`). Authoring and specification identities unchanged; execution
  interface `sha256:f2f3f9d2e4560b25574035cf92d7ff6e28aec7325036516317cd482893c0b903`;
  oracle digest `28da92086897725cc54c2b1fac790eaa151c68579a4d0d36da43652bb4794f78`.
- **Depends on:** the two sub-items are independent and may land in either order.
- **Next action:** None. Remaining unpinned samples and `go`/`swift` zero-coverage
  cells are follow-on breadth, not this item's evidence gate.
- **Evidence:**
  - [x] `publication-import` re-pinned to JavaScript and live-passed under the
        default (no `SAMPLE_FLAVORS` override) gate. Harness
        `execution.json` selects `flavor://literate-ai/lang-javascript`.
        `test_publication_import_ordinary_route_uses_javascript_lifecycle`
        asserts the ordinary route. Identities loaded via `_load_sample`, not
        invented. Landed as `a4b6ad16` on `feat/cli-sdlc-debug` (isolated
        `c556df3b`).
  - [x] `samples/python-service-example` and `samples/react-dashboard-example` each
        pass through a harness capable of exercising their entrypoint kind.
        `_load_sample` and `test_every_sample_is_a_strict_spec_driven_application`
        accept both harnesses. Runtime oracles dispatch both sample IDs.
        Live `python-service-example` passed 2026-08-29 with `--coding-cli
        cursor-agent --model gpt-5.6-sol-high --allow-host-execution` (first
        candidate; pinned `primary` `next_cursor` `"beta"`; runtime-generalization
        also passed). `react-dashboard-example` live-passed earlier in the same
        cycle.

### [x] SAMPLE-PACKAGE-001 — Prove package composition and OS pinning in the sample portfolio

- **Owner:** `component://literate-ai/sample-portfolio`
- **Direction:** Make packaging and target compatibility visible in executable examples,
  then refresh the human documentation and public deck from verified evidence rather
  than catalog claims.
- **Implementation:**
  - [x] Select several existing Python samples for `package.pip` and several portable
        native samples for `package.conan`; prove compatible package Flavors compose.
  - [x] Run representative pip and Conan samples through the native package
        lifecycle so they construct and independently verify wheel/package bytes under
        `OBJ_DIR` without publishing or installing them.
  - [x] Add small, useful Linux-only, Windows-only, and macOS-only sample Components
        whose target constraints prevent selection on every other test-matrix OS.
  - [x] Make the macOS sample a Swift application and select Homebrew packaging so the
        Swift toolchain and `package.brew` constraint are exercised together.
  - [x] Add structural and selection tests that derive counts from the catalog rather
        than hard-coding the sample, Flavor, or platform inventory. Historical
        acceptance identities remain migration locks for the samples they name, while
        newly added samples are admitted without editing a closed inventory or adopting
        legacy case labels.
  - [x] Regenerate the user documentation, Mermaid flows, checked-in PowerPoint deck,
        factual ledger, and native Google Slides presentation from the new package-build
        evidence and the current live platform matrix.
- **Evidence:**
  - [x] Sample discovery admits every pinned sample on its intended OS and excludes it
        from all incompatible OS selections before source generation.
  - [x] Package planning emits the selected pip, Conan, or Homebrew provider identities
        for the representative samples without implying unimplemented native package
        construction.
  - [x] The focused sample and documentation suites pass; every slide renders without overflow
        or unintended overlap; the published Slides resource is read back successfully.
        The macOS sample additionally completed a live Codex generation, guarded Swift
        compilation, generated-test run, independent entropy-derived verifier probe,
        CodeGraph indexing, CycloneDX resolution, execution, and receipt chain through
        `authorized-host-swift-executable`.
        The complete acceptance-interface conformance module also passes with the three
        new platform samples while retaining every historical migration lock. The
        parallel-runner fixture now supplies the same explicit host target contract as
        a real sample, and the project documentation-authority marker is current for
        the expanded Flavor, sample, and deck authority. The self-hosting test-runner
        identity is refreshed from the same expanded authority closure rather than
        retaining the pre-packaging catalog digest.
        The native package sample target passed on macOS for Greeting Card Starter and
        Exact Statistics Library pip wheels plus the Dependency Planner Conan archive;
        every result was derived from accepted lifecycle custody and independently
        verified. Documentation rendered 100 Mermaid diagrams from 289 Markdown files.
        The regenerated 22-slide deck passed the 9/0/1 document-pair oracle, was
        published in place as Google Drive version 28, and matched 22/22 slide and
        22/22 notes text records after authenticated PPTX export.

### [x] DOC-ROADMAP-001 — Give detailed roadmap documents an explicit lifecycle

- **Priority:** P1
- **Owner:** documentation governance, project onboarding, and the
  `record-user-directed-work` skill
- **Direction:** Detailed files beneath `docs/roadmap/` must not leave readers guessing
  whether a program is active, partially completed, deferred, completed, or historical.
  The current framework program declares its state, while the Component-authoring and
  Phase 8 plans mix landed and remaining work without a consistent lifecycle marker.
- **Conclusion:** Keep `active-work.md` as the sole resumable execution queue and require
  every supporting roadmap document to declare a small standard header containing its
  lifecycle status, owning active-work item or program, and completion or archival
  evidence. Audit a plan before assigning its state. Completed plans may remain in
  `docs/roadmap/` only when marked completed with durable evidence; otherwise move them
  to a declared history location without breaking documentation links. Ordinary queue
  items do not earn separate files merely to satisfy the header convention.
- **Depends on:** the documentation graph, initialized-project roadmap template,
  `record-user-directed-work`, and current detailed-roadmap link authority
- **Implementation:**
  - [x] Define the allowed lifecycle states, required header fields, ownership rules,
        and the boundary between an active roadmap and historical documentation.
  - [x] Audit every existing detailed roadmap against current implementation and queue
        evidence before marking it active, partial, completed, deferred, or historical.
  - [x] Add or migrate headers and links; move only plans proven historical, preserving
        Git history and all inbound documentation references.
  - [x] Teach the root and initialized `record-user-directed-work` skills when to create
        a detailed roadmap and how to close or archive it.
  - [x] Add a documentation validation rule and initialized-project fixture so new
        detailed roadmap files cannot omit or invent lifecycle ownership.
- **Evidence:**
  - [x] Validation rejects a detailed roadmap with a missing/unknown status, missing
        owner, dangling queue reference, or completed state without evidence. Focused
        documentation and initialization validation passed 52 tests.
  - [x] The complete documentation graph and initialized-project smoke suite pass after
        the migration: 289 Markdown files, 100 Mermaid diagrams, exact-revision wheel
        installation, isolated tool bootstrap, canonical project validation, and starter
        scaffold verification all passed.
  - [x] The framework and `record-user-directed-work` skills pass the pinned
        SkillEvaluator gate.

### [x] DOC-DECK-002 — Refresh the public technical narrative from current evidence

- **Owner:** `component://literate-ai/literate-ai-overview`
- **Direction:** Remove the retired product narrative and elapsed-development-time claim;
  make the implemented language/build/OS matrix, arbitrary Component DAG, `litai` CLI,
  and private cross-platform fan-out workflow obvious to a skilled new audience.
- **Implementation:**
  - [x] Re-audit repository facts and inspect the successor studio project without
        treating a specification-only WIP as implementation evidence.
  - [x] Rewrite the deck specification and factual ledger before changing slides.
  - [x] Replace retired-product slides with sample, CLI, DAG, and fan-out evidence.
  - [x] Regenerate and visually inspect all slides, validate notes and overflow, publish
        the exact Google Slides document in place, then verify an exported round trip.
- **Evidence:**
  - [x] The generated deck contains no retired product name or elapsed-time claim.
  - [x] Local and exported decks have identical visible text and speaker notes.
  - [x] The exact published Slides document was updated in place without changing ID and
        now reports Drive version 18.

### [x] TAXONOMY-001 — Restore Components versus sample compositions

- **Priority:** P0
- **Owner:** framework taxonomy, catalogs, samples, initialization, and documentation
- **Direction:** Keep reusable building-block Components under declared Component
  catalogs. Treat `samples/` as fully working demo libraries, applications, or modules
  that compose Components, Flavors, and skills to teach one concept and seed tutorials.
  A sample may produce a reusable package or runnable artifact, but its role in this
  repository is demonstration, not the canonical reusable Component catalog.
- **Inheritance rule:** Samples are private to their defining repository by default.
  Exactly one framework sample, `hello-component`, is explicitly inheritable so every
  derived project starts with one runnable end-to-end example. This exception must be
  asserted by behavior rather than by hard-coding a global sample count.
- **Scope boundary:** Do not move a Component into `samples/` merely because a sample
  uses it. Do not duplicate reusable Component authority inside a demo. Samples may
  reference and compose Components through explicit contracts; tutorials may be derived
  from samples after the sample remains a complete build/test/run scenario.
- **Next action:** Complete. Preserve this distinction through project validation,
  catalog inheritance, initialization, and the sample lifecycle matrix.
- **Implementation:**
  - [x] Publish a concise taxonomy contract and diagrams for Component, sample, and
        tutorial roles.
  - [x] Reclassify and move every misplaced reusable building block from `samples/` to
        `components/`, updating references and locks without compatibility shims.
  - [x] Ensure every remaining sample declares a fully working build/test/run composition and
        is explicitly non-inheritable except `hello-component`.
  - [x] Make initialization inherit the hello sample and its required transitive
        authority without inheriting the rest of the framework sample suite.
  - [x] Add structural tests that derive expectations from catalog metadata rather than
        hard-coded numbers of Components, samples, Flavors, or skills.
  - [x] Declare `inheritable: true` in both canonical and initialized hello sample
        authority. Ordinary reusable Components may rely on the default, but the one
        sample exception must be locally auditable rather than inferred from omission.
- **Evidence:**
  - [x] Repository validation rejects reusable catalog authority misplaced beneath
        `samples/` and sample Components lacking explicit inheritance intent.
  - [x] Fresh `litai init` produces one runnable hello sample and does not copy unrelated
        framework demos.
  - [x] Every retained sample passes its declared generation/build/test/run/package
        scenario and can serve as tutorial source material.
  - [x] GitHub Actions run `31636914331` passed the complete retained sample-composition
        matrix on Ubuntu, macOS, and Windows after the taxonomy migration. The local
        `make samples-packages` gate also generated, built, tested, ran, accepted, and
        independently packaged the declared `hello-component`, `generated-library`, and
        `dependency-planner` pip/Conan proof subset.
  - [x] The focused project taxonomy and inherited-catalog suites pass 13 tests on
        macOS/Python 3.14, dynamically discovering every sample and checking both
        canonical and initialized hello authority. Existing initialization and
        cross-platform sample evidence above remains valid because the manifest-only
        change makes the already-effective default explicit.

### [x] INIT-004 — Make initialization prerequisite discovery explicit

- **Priority:** P0
- **Owner:** framework onboarding skill, tool bootstrap, and project initialization
- **Direction:** Name CodeGraph as a top-level Literate AI dependency. Before creating
  a project, `litai init` must check whether required host dependencies are available;
  an agent following the top-level skill may install missing prerequisites, while the
  static CLI must use deterministic PATH/managed-tool discovery.
- **Conclusion:** Preserve the existing detect-first, pinned, user-local CodeGraph
  bootstrap instead of adding a second installer. Expose a versioned prerequisite
  report from initialization, including Python and CodeGraph discovery state and the
  conditional coding-CLI state. Python is necessarily already running the CLI;
  CodeGraph is mandatory and installable by `init`; a coding CLI is reported as a
  generation prerequisite but does not block scaffolding because initialization does
  not invoke a model. Keep `--no-tool-bootstrap` as strict detect-only behavior.
- **Dependencies:** Complete the taxonomy authority correction first; do not combine
  optional Flavor toolchains with the mandatory framework preflight.
- **Next action:** Complete. Keep the pinned CodeGraph bootstrap and prerequisite wire
  version current when mandatory framework tools change.
- **Implementation:**
  - [x] Update root and initialized-project skills with explicit CodeGraph dependency,
        PATH-first discovery, supported pinned installation, authorization boundary,
        and conditional coding-CLI guidance.
  - [x] Add a deterministic initialization prerequisite report and version the expanded
        project-initialization result explicitly rather than changing v5 in place.
  - [x] Cover PATH reuse, managed installation, detect-only failure, and absent/present
        coding-CLI reporting without executing or authenticating a coding agent.
  - [x] Persist resolved lineage and a provisional initialization baseline before
        graph-bound starter lock/audit creation; final baseline/review recording remains
        the last authority step so a successful init is immediately `lock --check`
        clean.
- **Evidence:**
  - [x] Seventy-seven focused wire-version, bootstrap, initialization, taxonomy,
        validation, and catalog tests pass on macOS/Python 3.14; the direct starter CLI
        regression also proves initialization is immediately lock-current. Ruff and formatting
        pass. A live clean init emitted project-initialization v6 with Python 3.14.6,
        PATH-reused CodeGraph 1.1.1, and PATH-discovered Codex without invoking it.
  - [x] A clean checkpoint-reset Python run passes all 2,167 tests (26 conditional
        skips). The three-repository regression proves inherited specifications and
        acceptance assets remain available while parent-local lock/audit evidence is
        excluded and rebuilt against the descendant's graph.
  - [x] Repository layout, 104 Mermaid diagrams across 300 Markdown files, current
        lifecycle-driver identity, and both root/template SkillEvaluator gates pass;
        the revised root skill scores 87.2/100 and remains below the size gate.

### [x] INIT-005 — Report explicit disabled initialization bootstrap state

- **Priority:** P0
- **Owner:** framework project initialization and installed-project smoke contract
- **Direction:** An initialized project with `source_intelligence.provider_id: none`
  and every source-intelligence stage off must expose that intentional disabled
  outcome in its initialization result rather than returning an empty bootstrap
  object. The isolated installed-project smoke must report the observed result
  accurately while retaining its strict no-source-graph-database assertion.
- **Conclusion:** The initialization result already owns the `tool_bootstrap` field
  and no public schema separately validates its contents. Return a closed,
  machine-readable disabled state with a reason code, update direct result-contract
  fixtures, and leave unrelated historical source-graph references outside this
  direct gate contract unchanged.
- **Dependencies:** INIT-004's provider-none initialization policy and the
  installed-project gate.
- **Implementation:**
  - [x] Return `state: disabled` and a no-provider reason from initialization.
  - [x] Align the installed smoke assertion and direct initialization result tests.
  - [x] Record the release-visible gate fix in the existing 0.7.0 changelog heading.
- **Evidence:**
  - [x] Initialization unit and CLI contract tests pass with the explicit result.
  - [x] `make install-check` passes without creating a source-graph database.
  - [x] Standard lint, formatting, documentation, layout, authority-record, and
        diff checks pass.

### [x] VERSION-002 — Keep the shipped compatibility matrix self-consistent

- **Priority:** P0
- **GitHub issue:** [#231](https://github.com/NVIDIA-dev/literate-ai/issues/231)
- **Owner:** framework core version/schema catalog
- **Direction:** The latest installed wheel must pass its own strict compatibility-matrix version check.
- **Conclusion:** The v2 matrix now declares two Standard multi-entrypoint evidence contracts, so the exact writer allowlist must admit those same framework-owned URIs; retain strict equality and do not weaken validation.
- **Depends on:** None
- **Implementation:**
  - [x] Add the two shipped Standard entrypoint evidence URIs to the v2 write-contract allowlist.
  - [x] Add focused regression coverage that validates the unmodified shipped v2 catalog.
- **Evidence:**
  - [x] Focused version-wire contract tests pass on the rebased repair branch.
  - [x] The clean full Python check passes 3,241 tests with 30 intentional skips
        after the latest-main rebase.
  - [x] Repeat the non-editable exact-wheel `litai version check` after the
        latest-main rebase.

### [x] TEST-ARG-001 — Keep packaged-service argv doubles aligned with the production port

- **Priority:** P0
- **GitHub issue:** [#232](https://github.com/NVIDIA-dev/literate-ai/issues/232)
- **Owner:** packaged-service lifecycle tests
- **Direction:** The current main test suite must exercise packaged-service argv behavior instead of failing in an obsolete test-double signature.
- **Conclusion:** Update only the two stale doubles to accept and assert the optional package-entrypoint argument; production behavior is already correct and remains unchanged.
- **Depends on:** None
- **Implementation:**
  - [x] Update both PackagedServiceArgvTests doubles to the current three-argument port contract.
- **Evidence:**
  - [x] The focused PackagedServiceArgvTests suite passes on the rebased repair branch.
  - [x] The clean full Python check passes 3,241 tests with 30 intentional skips
        after the latest-main rebase.

### [x] LIFECYCLE-PIN-001 — Re-pin the changed framework lifecycle driver

- **Priority:** P0
- **GitHub issue:** [#233](https://github.com/NVIDIA-dev/literate-ai/issues/233)
- **Owner:** project lifecycle-driver TCB authority
- **Direction:** Current main must bind its declared lifecycle implementation paths to their actual content identity.
- **Conclusion:** The single latest-main multi-entrypoint and uninstall commit changed 17 declared TCB paths without re-pinning; review that diff and use the repository-owned record workflow rather than transcribing a digest.
- **Depends on:** Review e695265b declared lifecycle-driver path changes
- **Implementation:**
  - [x] Run the lifecycle-driver review and record the computed identity after reviewing the changed TCB paths.
  - [x] Refresh documentation authority after the project manifest changes.
- **Evidence:**
  - [x] `make driver-review` passes with identity
        `sha256:a356fd3f67fab9ef6a17033384c5e2d70588070920e4e2fc9f32f4df3eb2b9b4`.
  - [x] The clean full Python check passes 3,241 tests with 30 intentional skips,
        and the non-editable exact wheel passes its installed version check after
        the latest-main rebase.

### [x] PLATFORM-PATH-001 — Keep platform-family path policy host-independent

- **Previous ID:** WINDOWS-PATH-001 (collision with the separate naming rule; reconciled under SDLC-001).
- **Priority:** P0
- **GitHub issue:** [#235](https://github.com/NVIDIA-dev/literate-ai/issues/235)
- **Owner:** centralized user-path adapter and host install/uninstall fixtures
- **Direction:** A Windows runner evaluating Linux or macOS policy must use POSIX
      path semantics rather than interpreting `/...` through native `WindowsPath`.
- **Conclusion:** Select `PurePosixPath` or `PureWindowsPath` from the requested
      platform family. Tests compare resolved source paths and mutate parsed install
      manifests instead of depending on platform-specific serialized syntax.
- **Implementation:**
  - [x] Make POSIX system, user, data, cache, tool, install, temporary, and staging
        policy paths host-independent.
  - [x] Repair Windows-sensitive installer and uninstaller fixtures.
- **Evidence:**
  - [x] Focused user-path, installer, and uninstaller suites pass locally; the full
        Windows matrix supplies the cross-host acceptance gate.
  - [x] Lifecycle-driver and documentation authority are re-pinned after the adapter
        change.

### [x] REPOSITORY-CHECKOUT-001 — Make worker repository checkout shallow and content-complete

- **Priority:** P0
- **Owner:** framework core plus skills/agent/checkout-git-repository and host prerequisite authority
- **GitHub issue:** [#224](https://github.com/NVIDIA-dev/literate-ai/issues/224)
- **Direction:** Workers are pipeline runners and must avoid full history by default while reliably materializing repositories that use Git LFS, submodules, or both.
- **Conclusion:** A reusable checkout contract must require Git and Git LFS on every supported worker OS, fetch an exact revision shallowly by default, initialize recursive submodules, hydrate LFS content in the root and nested repositories, and fail closed when the requested tree is not fully materialized; history expansion remains explicit and bounded.
- **Depends on:** HOST-INSTALL-SBOM-001 host prerequisite authority and WORKER-001 execution routing
- **Implementation:**
  - [x] Add a general-purpose checkout-git-repository agent skill that routes agents to one deterministic checkout/materialization command and documents only judgment and fail-closed boundaries.
  - [x] Declare Git and Git LFS as required sample-worker capabilities with native package mappings for supported Linux, macOS, and Windows targets.
  - [x] Implement shallow exact-revision acquisition with revision/tree verification, recursive submodule initialization, repository-local Git LFS setup and hydration for every repository in the recursive checkout, and unresolved-pointer verification.
  - [x] Provide explicit bounded deepening and full-history opt-in semantics for operations that demonstrate an ancestry requirement.
  - [x] Route Git-backed test-worker workspace acquisition to the checkout skill from the provider-neutral worker configuration skill without committing private routing or host details; Standard archive/Git source identity remains under WORKER-001.
- **Evidence:**
  - [x] Unit and contract tests cover branch, tag, reachable commit SHA, recursive submodules, root and submodule LFS content, missing Git LFS, unresolved pointers, bounded history, and explicit full-history mode (`50` focused tests passed).
  - [x] Host prerequisite tests and strict CycloneDX SBOM parsing prove Git and Git LFS discovery and native package installation mappings on Linux, macOS, and Windows.
  - [x] `make skills-check` passed all five affected skills; `make python-check` passed `3,221` tests with `28` expected skips; a remote depth-one worker checkout verified the exact requested commit/tree, a clean worktree, and all current-tree LFS-attributed content hydrated before the retained Kit test advanced beyond the prior corrupt-image failures.

### [x] STANDARD-SAMPLE-ASSET-001 — Preserve locked asset custody through the Standard sample path

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#260](https://github.com/NVIDIA-dev/literate-ai/issues/260)
- **Owner:** Standard sample planning and source-materialization composition
- **Observed behavior:** The release-receipt rebuild generated the
  `loan-risk-gate/python` candidate and then failed closed with
  `source_generation.asset_authority_mismatch`. After that identity wiring was
  corrected, a forced fresh receipt generated the same candidate but failed as the
  untyped `runner-failed`; the retained workspace contained the generated tree and no
  assembled score-band asset. After CAS admission was corrected, the next focused live
  run reached overlay assembly but the coding agent had recreated the locked path
  byte-for-byte, so the required collision guard rejected it as
  `source_generation.asset_path_collision`.
- **Conclusion:** This is deterministic framework wiring, not model variability or a
  repair-workspace defect. `StandardProjectApplicationService.plan()` and the source
  runner now receive the same locked asset tuple, but the sample path gives that runner
  a new empty CAS without admitting the asset bytes. The first `get_bytes()` therefore
  raises `BlobNotFoundError`, which source scheduling masks as `runner-failed` before
  overlay materialization. Reuse one filesystem-adapter helper to admit every locked
  asset into the exact candidate CAS before planning/execution, while retaining raw
  bytes exclusively in CAS-backed immutable overlay custody; translate missing or
  corrupt custody into a stable source-generation diagnostic. The bounded prompt
  currently emits the asset JSON (including `model_writable:false`) without an explicit
  imperative explaining that those paths are forbidden generated output and will
  appear only after the model returns. State that generic invariant in the framework
  envelope; do not weaken collision rejection or expose asset bytes.
- **Implementation:**
  - [x] Pass `authored_assets_from_lock(authority.lock)` to both Standard sample
        planning and source execution.
  - [x] Add a regression proving the materializer receives the same asset identities
        bound into the plan generation key.
  - [x] Admit the locked bytes through the shared Standard filesystem helper into the
        same CAS supplied to the runner, and expose a stable error at that boundary.
  - [x] Strengthen the production-path regression to prove the exact asset bytes are
        retrievable from that CAS before runtime composition.
  - [x] Tell every coding provider explicitly that locked authored-asset paths are
        post-generation immutable overlays and must not be created, inferred, copied,
        replaced, or modified in the generated text tree.
- **Evidence:**
  - [x] The focused regression, 31 adjacent source-generation scheduling tests, and
        all 83 neutral sample-ladder tests pass (6 intentional skips).
  - [x] A no-model reproduction proves the empty sample CAS raises
        `BlobNotFoundError` for the locked score-band BlobRef, while admission through
        the snapshotted catalog makes the exact authored bytes retrievable. The failed
        receipt created only one workspace, falsifying repair-workspace loss.
  - [x] Focused source-generation, Standard rebuild/factory, component-lock, and sample
        ladder suites pass, including exact candidate-CAS byte retrieval and stable
        missing-custody classification; Ruff lint and formatting pass for every changed
        Python file.
  - [x] The first post-admission live run reaches the collision boundary and proves the
        CAS contains the exact locked bytes. Its only workspace contains a model-written
        file at the protected path with the same SHA-256, while the reconstructed prompt
        contains only terse asset JSON and no direct non-generation instruction.
  - [x] A second fresh focused live `loan-risk-gate/python` run with the corrected
        envelope passes three generated tests, build, packaged execution, resolved-SBOM
        validation, one independent acceptance case, and final lifecycle admission.
  - [x] A clean canonical `make python-check` passes all 3,335 tests with 31 intentional
        skips after the reviewed lifecycle-driver and sample-runner identities were
        refreshed. Repository layout, Ruff lint and 815-file formatting, two strict
        OpenSpec items, 135 diagrams across 538 Markdown files, documentation, driver,
        runner, and both SkillEvaluator gates also pass.
  - [x] A fresh complete 0.9.0 rebuild advances beyond asset authority and promotes
        receipt `sha256:85bae95edfd9261059c5b4b593063fecf24b994ccd12a174966eb55f13d31618`.

### [x] STRUCTURED-SAMPLE-INTERFACE-001 — Keep structured-provider application contracts in generation authority

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#261](https://github.com/NVIDIA-dev/literate-ai/issues/261)
- **Owner:** DMN/SCXML sample authoring and bounded Component context
- **Observed behavior:** The live release-receipt rebuild produced loan-risk and
  playback candidates that followed their DMN/SCXML roots but omitted result fields,
  ordering, and pinned-asset semantics declared only in `component.md` prose.
- **Conclusion:** The framework correctly treats prose as descriptive
  `ComponentAuthoring.description` when a Component explicitly selects a different
  specification provider. The samples were misfactored: their normative portable
  call/result contracts were neither provider roots nor public interfaces. Move each
  contract into one exact local public-interface document and keep the Component body
  descriptive, without exposing verifier-owned acceptance values.
- **Implementation:**
  - [x] Bind one named public interface to each structured-provider sample's provided
        portable capability.
  - [x] Remove duplicated normative contract prose from the descriptive Component
        body and refresh only the affected authoring identity pins.
  - [x] Add a production-path regression proving each exact public-interface byte
        sequence appears once in the prepared bounded prompt.
- **Evidence:**
  - [x] Focused preparation and sample-authoring regressions pass for both providers;
        their structured specification identities and verifier execution-interface
        identities remain unchanged.
  - [x] The fresh complete Standard rebuild passes independent loan-risk and playback
        acceptance and produces the current 0.9.0 candidate receipt.

### [x] CONVERSION-TEST-AUTHORITY-001 — Do not invent retained pytest authority

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#262](https://github.com/NVIDIA-dev/literate-ai/issues/262)
- **Owner:** legacy conversion discovery and retained lifecycle inventory
- **Observed behavior:** Conversion inferred root `python -m pytest tests` from weak
  Python/repository shape evidence, missing repository-owned Poe tasks and nested
  aggregate scripts in the reported MuJoCo, URDF, and OpenVRTx layouts. A zero-test
  command could also establish a passing baseline.
- **Conclusion:** A retained command is executable authority, not a language heuristic.
  Admit repository-owned Poe tasks first, then known aggregate scripts with their exact
  working directory, and only admit pytest when configuration/dependency evidence and
  statically collectable test nodes both exist. Otherwise report the unproven runner
  rather than constructing one.
- **Implementation:**
  - [x] Trace conversion discovery and retained execution end to end against the three
        reported repository shapes.
  - [x] Isolate runner discovery and output accounting in a Python adapter instead of
        asking the model to infer commands from filenames.
  - [x] Add contract cases for authoritative runners, nested roots, missing driver
        evidence, and zero collected tests before making the smallest causal change.
- **Evidence:**
  - [x] Focused discovery, conversion, receipt, and real-Git boundary suites pass
        (`113` tests), including Poe dependency groups, nested script working
        directories, injection-shaped metadata, and zero-test rejection.
  - [x] The fresh complete 0.9.0 receipt proves the converted-project path with the
        final release tree.

### [x] CONVERSION-PARITY-002 — Compare authored authority rather than fungible caches

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#263](https://github.com/NVIDIA-dev/literate-ai/issues/263)
- **Owner:** legacy conversion parity and checkpoint evidence
- **Observed behavior:** Direct baseline, wrapper parity, and lift-and-shift checks each
  copied or hashed whole legacy trees, so ignored build/caching output could dominate
  runtime and unrelated output churn could change the compared identity.
- **Conclusion:** Capture one retained authored-source scope from Git visibility and
  bounded ignore/exclusion rules. Copy and hash only that scope while retaining separate
  excluded-root accounting, so parity remains sensitive to authored bytes without
  treating fungible outputs as authority.
- **Implementation:**
  - [x] Trace retained direct/wrapper parity state, path ownership, and checkpoint
        transitions using a bounded large-output fixture.
  - [x] Share one filesystem adapter across inventory, baseline, lift-and-shift, and
        receipt execution instead of rescanning the tree in model-facing workflow text.
  - [x] Prove ignored output churn passes, tracked authored mutation fails, exclusions
        remain accounted, and direct/wrapper phases do not redundantly rescan outputs.
- **Evidence:**
  - [x] The bounded large-output regression proves a one-megabyte ignored artifact is
        never read, ignored churn changes exclusion accounting but not source identity,
        and tracked authored mutation changes the identity.
  - [x] The combined focused conversion and receipt suite passes (`113` tests).
  - [x] The fresh complete 0.9.0 receipt proves parity over the final release tree.

### [x] RETAINED-RECEIPT-001 — Finalize retained harness evidence through the standard receipt boundary

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#264](https://github.com/NVIDIA-dev/literate-ai/issues/264)
- **Owner:** retained harness execution, outer receipt finalization, and project verification
- **Observed behavior:** Converted projects could prove direct/wrapper parity but had no
  supported producer for the outer-finalized envelope accepted by `project test-receipt
  update`, leaving operators to construct JSON manually or bypass the receipt boundary.
- **Conclusion:** Reuse the existing final candidate envelope and promotion command, but
  give converted projects a retained-only runner/policy. Bind the exact inventory,
  project revision, Component locks, worker/platform, commands, test totals, phases, and
  source scope; explicitly omit native generation/acceptance claims. External evidence
  remains outside project authority and the compact candidate binds it by identity.
- **Implementation:**
  - [x] Map the native candidate envelope and retained harness evidence contracts before
        selecting an adapter boundary.
  - [x] Add `project test-receipt run-retained`, retained-only policy generation, exact
        Component-lock binding, disposable authored-source execution, and atomic
        new-file candidate/evidence publication.
  - [x] Add end-to-end passing, known-failure, nonempty-suite, provenance, and
        native-versus-retained classification regressions.
- **Evidence:**
  - [x] A passing converted Make harness emits a finalized candidate that the unchanged
        `update` and `require-current` commands accept; the durable evidence contains no
        console excerpts or native generation/acceptance assertion.
  - [x] Exit-zero expected failures, typed known failures, uncounted tests, empty suites,
        unsafe output paths, and candidate-publication failure all leave no promotable
        candidate.
  - [x] Retained implementation bytes are folded into project authority: an authored
        source edit makes the committed receipt stale, and a harness that mutates its
        disposable authored source cannot earn a candidate.
  - [x] A clean test-one Python qualification passes all `3,332` tests with `31`
        intentional skips after the lifecycle-driver pin and documentation-authority
        marker are refreshed.
  - [x] The fresh complete 0.9.0 receipt exercises the final retained adapter surface.

### [x] JAVASCRIPT-IMPORT-ADMISSION-001 — Observe code imports without scanning inert text

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#265](https://github.com/NVIDIA-dev/literate-ai/issues/265)
- **Owner:** source dependency admission
- **Observed behavior:** A fresh receipt generated a dependency-free durable frontend,
  then rejected its build helper with `dependencies.import-bom-mismatch`; the reported
  package names were fragments of regex and replacement-string literals used to rewrite
  imports during packaging.
- **Conclusion:** The source BOM and generated dependency graph are correct. The
  JavaScript observer applied an unanchored import regex to raw source and interpreted
  inert comment/regex/string/template text as executable imports. Isolate a bounded
  lexical-projection helper at the JavaScript dependency-adapter level; retain the
  existing fail-closed reconciliation contract.
- **Implementation:**
  - [x] Mask inert JavaScript lexical forms while preserving ordinary quoted literals
        as opaque keys recoverable only from executable import syntax.
  - [x] Preserve static import/export-from, side-effect import, dynamic `import()`, and
        CommonJS `require()` observation.
  - [x] Add exact build-helper regression shape plus real undeclared-import controls.
- **Evidence:**
  - [x] All 60 dependency-lifecycle tests pass, including inert-text and five executable
        import forms; the exact preserved failed workspace now passes source-BOM
        reconciliation unchanged.
  - [x] The fresh complete receipt crosses the durable frontend admission/build
        boundary and produces a current 0.9.0 candidate.

### [x] CANDIDATE-DEPENDENCY-REPAIR-001 — Repair generated import/BOM topology mismatches

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#269](https://github.com/NVIDIA-dev/literate-ai/issues/269)
- **Owner:** Standard and retained-host dependency admission plus bounded
      generated-candidate repair
- **Observed behavior:** A fresh complete release receipt built a dependency-free
  Python zipapp candidate, then terminated with `dependencies.import-bom-mismatch`
  because its build helper renamed `main.py` to staged `app.py`. The conservative
  source scanner could not prove that generated build-time transformation and treated
  `from app import ...` as an undeclared external import. Falsification testing also
  showed that a repeated identical mismatch caused the production adapter to recreate
  the same repair request because it accepted but did not bind predecessor identities;
  the lifecycle correctly stopped that duplicate before the third attempt. A later
  complete candidate exposed the same code at the retained `self-hosting` validate
  phase: its parallel repair allowlist omitted the code and stopped after one candidate
  even though the Standard path was already corrected.
- **Conclusion:** Keep source/BOM admission fail-closed and do not attempt to interpret
  arbitrary generated build scripts. The stable mismatch is attributable to one typed
  generated candidate at the build phase, so classify only that code as repairable
  through the existing two fresh replacement attempts in both lifecycle shapes.
  Persistent mismatch remains a terminal exhausted chain and no rejected candidate
  reaches cache or publication.
- **Competing hypotheses:** The candidate is not behaviorally broken: its exact Make
  target, three native tests, archive test/smoke modes, and direct invocation pass.
  Adding `app` to the BOM would fabricate a distribution, while teaching dependency
  admission to execute or infer arbitrary build transforms would weaken the boundary.
  This is not #246: that issue covers pre-candidate output-root shape failures, whereas
  this failure occurs after a typed candidate and successful build.
- **Implementation:**
  - [x] Add only `dependencies.import-bom-mismatch` to the candidate-repair allowlist;
        retain its build/test phase restriction and exact three-attempt ceiling.
  - [x] Reduce the raw failure to a bounded diagnostic naming only the violated
        source-path/dependency-metadata relationship.
  - [x] Bind every predecessor-attempt identity into each replacement prompt/request,
        making the second repair distinct even when candidate bytes and failure match.
  - [x] Add production-adapter flow regressions for recovery and persistent exhaustion
        with unique fresh workspaces and zero rejected-candidate publication.
  - [x] Admit the same exact code at the retained host-sample validate boundary, carry
        a fixed bounded diagnostic into its next request, and retain the exact existing
        three-attempt ceiling.
- **Evidence:**
  - [x] The candidate-repair, repair-contract, Standard lifecycle, and dependency
        admission suite passes (104 tests plus 64 subtests), including one-mismatch
        recovery and three-identical-mismatch exhaustion.
  - [x] Exact retained-flow regressions prove one-mismatch recovery and three-mismatch
        exhaustion; the adjacent 100-test sample/portfolio suite passes, and a forced
        fresh `self-hosting` generation passes on its first accepted candidate.
  - [x] The complete current 0.9.0 candidate receipt passes both repair paths.

### [x] SAMPLE-DRIVER-CONFIG-001 — Keep test isolation out of the production driver

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#268](https://github.com/NVIDIA-dev/literate-ai/issues/268)
- **Owner:** production sample-driver entrypoint and test-process isolation boundary
- **Observed behavior:** The fresh release receipt resolved the configured Codex/model
  through `worker verify-model`, but the external lifecycle driver then failed before
  generation with `coding_cli.test_selection_unconfigured`.
- **Conclusion:** The host path resolver and migrated configuration are correct.
  `scripts/run_samples.py` imports its implementation through the `tests` package;
  `tests/__init__.py` consequently installed a temporary `LITAI_CONFIG_DIR` intended
  only for unittest/pytest and masked the canonical user test configuration. Preserve
  test isolation, but restore the caller's exact environment at the production import
  boundary before resolving durable operator configuration.
- **Competing hypotheses:** Missing credentials/model, a wrong project ID, and an
  omitted lifecycle `HOME` were tested and rejected: model preflight succeeds, the
  exact project-scoped file exists, and the bound child environment resolves it until
  the test-support import alone changes the selected path.
- **Implementation:**
  - [x] Snapshot and restore only the two environment variables mutated by the test
        package while importing the test-hosted conformance implementation.
  - [x] Preserve caller-supplied values byte-for-byte and keep unittest/pytest isolation
        unchanged.
  - [x] Add clean-subprocess regressions for both an absent platform-resolved config
        override and explicit caller-supplied config/MCP values.
- **Evidence:**
  - [x] The cross-platform subprocess regression and adjacent lifecycle-driver and
        host-path tests pass (25 tests plus 10 subtests).
  - [x] The fresh complete 0.9.0 receipt reaches live generation and produces a current
        candidate through the canonical user configuration path.

### [x] CONVERSION-GITLINK-001 — Block conversion that cannot preserve nested submodules

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#266](https://github.com/NVIDIA-dev/literate-ai/issues/266)
- **Owner:** conversion planning and Git transaction boundary
- **Observed behavior:** A repository with an initialized nested Git submodule was
  reported `ready`; mutation would lift-shift ordinary top-level paths without remapping
  `.gitmodules`, the Gitlink, or the nested worktree's relative `.git` pointer.
- **Conclusion:** Full transactional remapping is wider and riskier than the 0.9.0
  conversion contract needs. Inspect index mode `160000` entries directly and block all
  initialized or uninitialized nested submodules before mutation, even when
  `--allow-unready` is supplied.
- **Implementation:**
  - [x] Add fail-closed Gitlink inspection with bounded subprocess execution and safe
        UTF-8 repository-relative path handling.
  - [x] Report `blocked-nested-submodules`, the path/state inventory, and one typed
        finding from `--convert --plan`.
  - [x] Reject mutation before quarantine with
        `project.convert_nested_submodules_unsupported`.
- **Evidence:**
  - [x] A real initialized nested-submodule regression proves plan classification,
        typed mutation rejection even with `--allow-unready`, unchanged Git status,
        preserved pointer file, and no framework manifest.
  - [x] The clean test-one Python gate passes all `3,332` tests with `31` intentional
        skips, including initialized and deinitialized real-Git submodule boundaries.

### [x] CONVERSION-UPSTREAM-001 — Prefer the current upstream over remote HEAD

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#267](https://github.com/NVIDIA-dev/literate-ai/issues/267)
- **Owner:** conversion repository-policy inference
- **Observed behavior:** An absorbed submodule worktree on `dev/next/111`, tracking
  `origin/dev/next/111`, derived `master` from `refs/remotes/origin/HEAD` because remote
  HEAD was tested before the current branch's upstream.
- **Conclusion:** `.git` pointer files are already understood by `git -C`; the defect is
  precedence. A valid current upstream is stronger evidence about the branch being
  converted than the repository-wide remote HEAD and must be consulted first.
- **Implementation:**
  - [x] Resolve the current upstream before remote HEAD and bind its actual configured
        remote, using longest-prefix matching for safe remote names.
  - [x] Preserve explicit CLI override as the highest-precedence source and retain the
        prior fail-closed fallback behavior when no valid upstream exists.
- **Evidence:**
  - [x] A real absorbed submodule worktree regression proves `.git` is a pointer file
        and the plan returns `dev/next/111` from `current-upstream`; the adjacent remote
        guidance test passes with the corrected precedence.
  - [x] The clean test-one Python gate passes all `3,332` tests with `31` intentional
        skips, including the absorbed-worktree upstream regression.

### [x] RECEIPT-MODEL-PLAN-001 — Bind one live model before planning and execution

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#270](https://github.com/NVIDIA-dev/literate-ai/issues/270)
- **Owner:** sample lifecycle-driver entrypoint and source-cache derivation protocol
- **Observed behavior:** A forced fresh complete rebuild passes all 22 sample
  lifecycles, then candidate projection fails with `Standard sample receipt cannot
  uniquely bind its derivation key`. Every executed Standard recipe is absent from the
  retained manifest even though the manifest contains no duplicate recipe identities.
- **Conclusion:** Planning returns before live-test selection. It constructs Standard
  recipes with `pipeline_model=None`; execution then resolves the project-scoped
  `codex` / `gpt-5.6-sol` pin and constructs different model-scoped recipes. Resolve
  and project the pure selection before both branches, while retaining model preflight
  and live-session logging only in the execution branch.
- **Competing hypotheses:** Candidate repair does not alter the accepted recipe
  identity, and exact locked-asset planning matches execution when model scope is held
  constant. Three unrelated samples each match the retained no-model recipe and reject
  only the explicit-model recipe, excluding isolated sample or duplicate-key defects.
- **Implementation:**
  - [x] Resolve required/optional live selection once before the planning branch and
        apply its environment/model projection to both planning and execution.
  - [x] Keep derivation planning non-executing: no coding-CLI preflight, session log,
        generation, build, or test side effect.
  - [x] Add an entrypoint regression proving configured model identity reaches
        `plan_derivation_manifest` and preflight remains uncalled.
- **Evidence:**
  - [x] Three sample controls reproduce no-model manifest matches and explicit-model
        misses; same-model asset planning and execution produce one exact cache key.
  - [x] All 27 retained manifest recipe identities are unique, and all live sample
        lifecycles pass before receipt aggregation.
  - [x] Focused contracts and the uninterrupted 3,340-test Python gate pass; a real
        plan contains only the configured `gpt-5.6-sol` model selector.
  - [x] The exact candidate produces a fresh matching manifest/receipt pair.

### [x] DURABLE-RECEIPT-001 — Receipt the durable portfolio as two Standard roots

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#271](https://github.com/NVIDIA-dev/literate-ai/issues/271)
- **Owner:** durable portfolio planning, aggregate reporting, and source-cache receipt
  lifecycle
- **Observed behavior:** The valid durable portfolio envelope carries
  `proof_status: passed` and two nested Standard reports but no legacy top-level
  `passed`. The final receipt rejects it as a failed run before inspecting those roots.
  Derivation planning independently records one legacy harness key and lock, while live
  execution prepares five Standard nodes across two different root locks.
- **Conclusion:** #252 fixed only suite metric aggregation. Define one validated
  direct-or-portfolio Standard report expansion contract and use it for metrics,
  receipt projection, and lock collection. Plan durable keys through the same root
  preparation and invocation construction used by execution, without crossing the
  coding-agent boundary.
- **Implementation:**
  - [x] Factor shared durable root generation authority and a non-executing exact-key
        planner for frontend API/root/cache and collector root/cache nodes.
  - [x] Replace the legacy durable planning fallback with those five keys and both
        exact root locks.
  - [x] Expand and validate nested Standard reports before applying the legacy
        `passed` contract; use the same expansion for metrics and lock collection.
  - [x] Add malformed/failed envelope, five-key/two-lock, nested receipt, and exact
        source-cache lifecycle regressions.
- **Evidence:**
  - [x] A minimal valid-shape portfolio report reproduces `conformance receipt cannot
        include a failed run`.
  - [x] Exact pure inspection enumerates five unique model-scoped node recipes and two
        root locks; neither root lock appears in the retained release manifest.
  - [x] Commit `363eaf4` changes only `run_all()` aggregation for #252, confirming the
        remaining planning and receipt paths were not repaired there.
  - [x] The focused 99-test sample/portfolio suite and uninterrupted 3,340-test Python
        gate pass; the real planner emits five unique durable derivation keys and both
        root locks.
  - [x] The complete exact-commit candidate validates every planned durable key as an
        accepted lifecycle member.

### [x] RUNNER-CLOSURE-001 — Bind durable portfolio authority into lifecycle review

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#272](https://github.com/NVIDIA-dev/literate-ai/issues/272)
- **Owner:** reviewed lifecycle-driver and sample test-runner source closures
- **Observed behavior:** The runner closure explicitly names the production entrypoint,
  runtime oracles, `sample_runner.py`, and the Standard service-stack helper, but not
  the dynamically imported durable split-service helper that controls topology,
  generation, execution, verification, derivation planning, and receipt evidence.
- **Conclusion:** Both static closures predate the durable portfolio and were not
  extended with it. Add that exact module rather than broadening review to unrelated
  tests, and prove every repository-owned test-support import from the runner is
  represented in both policies.
- **Implementation:**
  - [x] Add `tests/conformance/support/durable_split_service.py` to both explicit source
        closures and retain canonical ordered path/digest identity.
  - [x] Add a regression proving durable helper bytes affect the computed identity and
        the runner's repository-owned support imports are covered.
  - [x] Run both reviews, inspect the final closure diff, then record the new pins.
- **Evidence:**
  - [x] Import tracing finds three repository-owned support dependencies; runtime
        oracles and Standard service stack are listed, while durable split service is
        the sole omission.
  - [x] Focused identity tests and the uninterrupted 3,340-test Python gate pass. The
        final reviewed runner identity is
        `sha256:f40d421f344cf6a19f98b1500213f5a316c860cf175dc58d2b7c7b0e96548a1b`;
        the lifecycle-driver identity is
        `sha256:f6a6676813b1c95dd33280cf585ee3c21abac8222284e21edcf3d0a5b862905f`.

### [x] CONVERSION-UPDATE-VARIANT-001 — Preserve conversion documentation during update

- **Priority:** P0 (0.10.0 converted-project update blocker; complete)
- **Release target:** 0.10.0
- **GitHub issue:** [#283](https://github.com/NVIDIA-dev/literate-ai/issues/283)
- **Owner:** project initialization and three-way framework update adapters
- **Observed behavior:** An untouched project initialized with `litai init --convert`
      cannot take a later starter-document update. The prospective update replaces its
      baseline-identical `docs/README.md` with the generic starter version, drops the
      only link to the retained conversion ADR, fails documentation reachability, and
      then rolls back atomically.
- **Conclusion:** Validation and rollback are correct. Initialization appends the
      conversion-specific Adoption decisions edge after rendering the generic starter,
      while `project_updates._upstream_template()` reconstructs only the generic
      variant. Update must compare against the same variant-aware scaffold that created
      the baseline. This is a direct minor-version compatibility defect but is not a
      0.9.0 publication blocker under the explicit release-priority decision.
- **Competing hypotheses:** Local documentation edits do not explain the sixteen
      baseline-identical affected conversions, and weakening reachability validation
      would only hide the broken prospective tree. The issue's successful rollback
      contradicts project-byte loss but not update unavailability.
- **Implementation:**
  - [x] Factor one variant-aware starter-document renderer shared by initialization
        and update, or reconstruct the exact conversion augmentation from durable
        baseline/conversion evidence as the smallest bounded backport.
  - [x] Preserve generic-project behavior, locally modified documentation conflict
        ownership, and atomic rollback without error suppression.
- **Validation:**
  - [x] Initialize a representative legacy tree with conversion, simulate a later
        starter-document revision, apply it, prove the ADR remains reachable and
        `litai project validate` passes, then prove a second plan is current.
  - [x] Focused initialization and update tests preserve generic projects, converted
        ADR reachability, local-document conflict ownership, idempotent second-plan
        behavior, and rollback contracts. Cross-platform release qualification remains
        part of the 0.10.0 candidate gate rather than evidence invented here.

### [x] CONVERT-WORKSPACE-001 — Keep disposable repo-man workspaces portable in exact-commit CI

- **Priority:** P0
- **Release target:** 0.9.0
- **Owner:** conversion harness process and workspace boundary
- **Direction:** Project disposable baseline and parity workspaces beneath the shared
      project root while passing the observed workspace through a
      host-shell-independent environment contract.
- **Conclusion:** The exact candidate exposes two deterministic contract errors: the
      POSIX assertion parses GNU Make's inherited directory tracing as a path, and the
      cross-platform environment regression asks `cmd.exe` to expand POSIX dollar
      syntax. Preserve the production placement and environment projection, then
      verify their meaning without shell-specific test commands or output-order
      assumptions.
- **Depends on:** none
- **Implementation:**
  - [x] Replace brittle assertions with marker-based path checks; make the environment
        projection regression execute a cross-platform Python probe; retain baseline
        and wrapper cleanup assertions.
- **Evidence:**
  - [x] Exact GitHub run `33812435136` fails only the two new workspace regressions on
        Ubuntu Python 3.11 and Windows Python 3.12; the repaired probes pass on macOS
        and Linux, including Python 3.11 with inherited GNU Make tracing.
  - [x] The complete local release-candidate gate passes 3,350 tests with 30 expected
        skips after the cross-platform probe repair.
  - [x] The repaired exact-commit workflow passes on Windows, Linux, and macOS in
        hosted run `33858381265`.

### [x] CONVERSION-PREFLIGHT-001 — Resolve conversion authority before quarantining source

- **Priority:** P0
- **Release target:** 0.9.0
- **GitHub issue:** [#293](https://github.com/NVIDIA-dev/literate-ai/issues/293)
- **Owner:** project initialization transaction boundary
- **Direction:** Complete repository-parent, lineage, inherited-catalog,
      Standard-binding, and template-catalog preflight while the conversion target is
      still untouched; quarantine only after those non-mutating contracts succeed.
- **Conclusion:** A clean real repo_man conversion with intentionally unavailable
      framework credentials failed at `repository_lineage.tags_unavailable` after
      every tracked source path had already moved under one `_legacy` transaction. The
      call path places quarantine before default-parent selection. Reordering preflight
      is the smallest causal fix; repo_man and nested Docker have not run at this point.
- **Depends on:** none
- **Implementation:**
  - [x] Move the interrupted-conversion quarantine decision to the final pre-write
        boundary after template validation, preserve resume behavior, and add a real-Git
        regression proving default-parent failure leaves tracked and untracked source
        plus Git status unchanged.
- **Evidence:**
  - [x] GitHub issue #293 records the reproduction, competing hypotheses,
        falsification, and verification contract; the focused failure, success, resume,
        workspace, and environment-projection tests pass.
  - [x] The complete local release-candidate gate passes 3,350 tests with 30 expected
        skips.
  - [x] A native Animation Authoring run reaches the selected authoritative build only
        after preflight and leaves the original archive plus Git state byte-clean when
        the later external toolchain fails.

### [x] CONVERSION-TIMEOUT-001 — Make host-heavy conversion deadlines explicit and evidenced

- **Priority:** P1
- **Release target:** 0.9.0
- **GitHub issue:** [#292](https://github.com/NVIDIA-dev/literate-ai/issues/292)
- **Owner:** conversion CLI and retained-harness execution boundary
- **Direction:** Add one validated conversion baseline/parity deadline option with the
      existing 1,800-second default, propagate it through the filesystem adapter, and
      record the effective bound in every phase and top-level receipt.
- **Conclusion:** Issue #292 reports a clean repo_man build killed at exactly the
      hard-coded 1,800-second bound. The operator explicitly chose `--run-baseline`, so
      a bounded override is preferable to a larger unconditional timeout; parity must
      receive the same value or the second replay can fail under a different lifecycle
      contract.
- **Depends on:** none
- **Implementation:**
  - [x] Expose `--baseline-timeout-seconds` for `init --convert`, validate a finite
        integer range in the public adapter, pass it to direct baseline and wrapper
        parity before and after retained-source lift-and-shift, improve timeout
        diagnostics, and preserve the effective value in canonical evidence.
- **Evidence:**
  - [x] Parser, validation, propagation, and conversion-flow regressions prove the
        default remains 1,800 and an explicit bound reaches both receipts and every
        phase.
  - [x] The complete local release-candidate gate passes 3,350 tests with 30 expected
        skips.
  - [x] Native Linux x86_64 repo_man qualification uses an explicit 7,200-second bound;
        the public Kit App Template completes within it and the Animation Authoring run
        reaches its unrelated builder-toolchain failure rather than timing out.

### [x] CONVERSION-BUILD-WRAPPER-001 — Preserve authoritative repo_man build entrypoints

- **Priority:** P1 (blocks the reported repo_man Phase 1b qualification)
- **Release target:** 0.9.0
- **GitHub issue:** [#294](https://github.com/NVIDIA-dev/literate-ai/issues/294)
- **Owner:** conversion harness discovery and retained-wrapper boundary
- **Direction:** For each detected repo_man project root, prefer its platform-native
      runnable `build.sh` or `build.bat` when present, while retaining the direct
      repo driver as the fallback and recording one command/evidence tuple for direct
      baseline, generated Make delegation, and parity replay.
- **Conclusion:** Fresh inspection of the retained Animation Tools source selects
      `repo.sh` even though the documented root wrapper first pulls the build BOM and
      builds and links required USD schemas before delegating to repo_man. The driver
      does not call the wrapper, so the unconditional repo-driver stage deterministically
      skips clean-build prerequisites; timeout, nested-container visibility, and stale
      evidence are downstream or falsified alternatives.
- **Depends on:** CONVERSION-BASELINE-001, CONVERSION-BASELINE-002
- **Implementation:**
  - [x] Select a platform-native regular build wrapper adjacent to each detected
        repo_man driver, require executable permission for POSIX shell wrappers,
        preserve explicit release configuration and host-heavy cost, and retain the
        existing driver command when no valid wrapper exists.
  - [x] Align the repo-man Flavor and skill contract with recorded authoritative build
        entrypoints instead of declaring the low-level driver universally authoritative.
- **Evidence:**
  - [x] Issue #294 records the real retained-tree source, fresh-inspection result,
        competing hypotheses, causal call path, and falsification criteria.
  - [x] Focused contract tests prove wrapper preference, fallback, nested-root
        selection, and exact command reuse through baseline, generated wrapper, and
        parity.
  - [x] The complete local release-candidate gate passes 3,350 tests with 30 expected
        skips.
  - [x] Native clean Animation Authoring inspection selects and executes
        `./build.sh --release`; the later nested-container `GLIBCXX` failure confirms
        the authoritative wrapper boundary was crossed.

### [x] CONVERSION-RUNTIME-STATE-001 — Exclude repo_man runtime logs from source parity

- **Priority:** P0 (two successful real repo_man builds are rejected as unequal)
- **Release target:** 0.9.0
- **GitHub issue:** [#297](https://github.com/NVIDIA-dev/literate-ai/issues/297)
- **Owner:** retained authored-source observation and wrapper-parity boundary
- **Observed behavior:** On the exact `536a6921` candidate, the current public Kit App
      Template completes both the direct and wrapper-mediated `repo.sh build --release`
      executions with status zero, but conversion fails
      `project.convert_wrapper_parity_failed` and rolls back.
- **Conclusion:** The fresh Git-visible scope contains no `_repo` directory. repo_man
      creates `_repo/repo.log` during each disposable build; the parity copies contain
      no Git metadata from which to re-evaluate the repository's `_*/` ignore rule, so
      the filesystem observer hashes the timestamped runtime log as authored source.
      A normalized member comparison finds no other difference across 299 observed
      files. Treat only unprotected `_repo` as generated runtime state; retain the
      existing protected-path rule so tracked files below that directory remain
      authoritative.
- **Competing hypotheses:** Exit-status, deadline, and command mismatches are falsified
      by two zero exits using the same command and bound. Absolute temporary paths are
      already normalized. Broader build nondeterminism is contradicted by every other
      observed member matching exactly.
- **Falsification:** The theory is wrong if excluding only unprotected `_repo` leaves
      the two successful source identities unequal, or if a tracked file beneath
      `_repo` can mutate without detection.
- **Implementation:**
  - [x] Classify unprotected `_repo` as repo_man-generated runtime state without
        weakening tracked-path observation.
  - [x] Add regressions for timestamped log churn, protected authored paths, and an
        unrelated untracked source mutation.
- **Evidence:**
  - [x] Native Linux x86_64 direct and wrapper executions both exit zero; the exact
        normalized diff is `_repo/repo.log`, and a diagnostic `_repo` exclusion makes
        both source and accounting trees identical.
  - [x] Failed conversion removes both disposable workspaces and leaves source Git
        status empty.
  - [x] The complete 45-test harness-inventory suite passes with strict lint and
        formatting, including timestamped runtime-log parity and protected-path
        regressions.
  - [x] The complete local Python gate passes 3,370 tests with 30 expected skips.
  - [x] Exact CI passes and the public Kit App Template completes direct baseline,
        wrapper parity, conversion, and project validation on native Linux x86_64.

### [x] CONVERSION-DIAGNOSTICS-001 — Preserve bounded root-cause evidence from long baselines

- **Priority:** P0 (host-heavy conversion failures currently lose their actionable
      error and record an identity for only an initial output prefix)
- **Release target:** 0.9.0
- **GitHub issue:** [#298](https://github.com/NVIDIA-dev/literate-ai/issues/298)
- **Owner:** retained-harness process output and conversion failure boundary
- **Observed behavior:** A synthetic command whose stdout exceeds 1 MiB records neither
      its first `ROOT-ERROR` nor its final `ACTUAL-TAIL`; the purported tail is the end
      of the first 1 MiB. Its `stdout_identity` also hashes that prefix rather than the
      complete 1,100,024-byte stream. Any nonempty generic stderr then hides stdout
      entirely in the public failure message. The first exact native rerun after the
      stream repair proves a second boundary: the inner excerpt contains the GLIBC
      failure, but the public JSON message is exactly 512 characters and ends at the
      stdout head.
- **Conclusion:** Temporary files already provide file-backed custody, but the reader
      seeks to byte zero and reads only `limit + 1` bytes before excerpting, hashing,
      test-summary observation, and verbose tracing. Preserve the complete stream's
      digest while retaining bounded head/error/tail windows; combine labeled stdout
      and stderr diagnostics instead of choosing one stream. Make the effective finite
      capture policy explicit and evidence-bound rather than introducing an unrecorded
      process-global override. Preserve the ordinary CLI's 512-character safety bound,
      but let the two conversion gate errors carry their already validated finite
      diagnostic budget through the final envelope.
- **Competing hypotheses:** A twelve-line/1,500-character tail alone is insufficient
      but does not explain the missing physical tail or incorrect digest. Log overwrite,
      stale receipts, and redaction are contradicted by a fresh direct invocation of
      `_run_harness_command`; the bytes remain present in its temporary file until the
      post-process reader discards them.
- **Falsification:** The theory is wrong if a full-stream digest plus bounded
      head/error/tail scan still omits synthetic first and final markers, or if the
      recorded identity does not match an independently computed SHA-256 of the entire
      stream.
- **Implementation:**
  - [x] Factor a constant-memory file-backed output observer that computes full-stream
        identity and preserves bounded head, first error contexts, and tail.
  - [x] Record the effective output/diagnostic limits in baseline and parity evidence;
        validate any operator override at the CLI boundary and apply one identical
        policy to direct and wrapper executions.
  - [x] Keep receipts and user-facing diagnostics bounded and secret-redacted; never
        retain complete command output in committed evidence.
  - [x] Propagate only conversion build/CI gate budgets through the CLI dispatcher;
        retain the 512-character default for every other error and a hard 66,048
        character ceiling for all callers.
- **Validation:**
  - [x] Prove full digest, first/root error, actual tail, mixed stdout/stderr reporting,
        oversized-success policy, test-summary discovery, and invalid-bound rejection
        with contract tests.
  - [x] The focused 190-test diagnostics, conversion-flow, CLI, and evidence slice has
        189 behavioral passes; its sole pre-review failure is the expected stale
        documentation-authority marker. After recording the reviewed authority, the
        canonical self-description regression passes and the final-code complete
        Python gate passes 3,370 tests with 30 expected skips.
  - [x] The native Animation Authoring rerun retains the first actionable CentOS 7
        `GLIBCXX` incompatibility plus bounded head and tail evidence while preserving
        the 7,200-second timeout, byte-clean rollback, and source-parity behavior.

### [x] RELEASE-CHECK-RESET-001 — Bootstrap checkpoint reset through the managed runtime

- **Priority:** P0
- **Release target:** 0.9.0
- **Owner:** Make release-check bootstrap boundary
- **Observed behavior:** On an otherwise valid release candidate,
      `make release-check-reset` invoked `scripts/run_checkpointed_gates.py` with the
      dependency-free bootstrap Python and failed while importing `jsonschema` before
      either checkpoint could be reset.
- **Conclusion:** The checkpoint runner gained application-level pinned-dispatch
      imports, but the reset target retained its earlier stdlib-only interpreter
      contract. This is a deterministic Make dependency mismatch, not stale state or
      a platform-specific package installation failure.
- **Implementation:**
  - [x] Give `release-check-reset` the same managed-runtime prerequisite and
        interpreter selection as `release-check` for both checkpoint resets.
- **Evidence:**
  - [x] A Make dry-run regression proves a clean environment is provisioned and both
        reset invocations use its managed interpreter rather than the bootstrap
        interpreter.
  - [x] Reset both real checkpoints successfully through a freshly provisioned
        managed runtime; exact-candidate release-check completion remains part of the
        release-wide qualification evidence.

### [x] CONVERT-PARITY-001 — Keep generated build outputs out of conversion source authority

- **Priority:** P0 (0.10.0 conversion blocker; complete)
- **Release target:** 0.10.0
- **GitHub issue:** [#305](https://github.com/NVIDIA-dev/literate-ai/issues/305)
- **Owner:** conversion baseline and wrapper parity adapters
- **Direction:** Phase 1 wrapper parity must compare the source authority that existed
      before each build while retaining post-build artifacts separately; generated
      cache and tool outputs must not become source merely because a legacy build
      writes them outside `_build`.
- **Conclusion:** Issue #305 is a real source-versus-artifact observation bug, not
      nondeterminism in the target project: successful direct and wrapper builds
      observe different generated populations because `source_tree` is captured after
      execution. Snapshot source authority before each command, evaluate post-command
      mutations to pre-existing source paths, and keep newly created paths in artifact
      observations. Review the existing conversion branch as proposed work, not
      landed evidence.
- **Depends on:** Existing Phase 1b baseline and wrapper parity contracts.
- **Implementation:**
  - [x] Capture the bounded pre-build source membership for direct and wrapper
        commands; compute source identity from those members after execution so
        modifications and removals still affect parity; retain newly generated paths
        in artifact-tree evidence; review and land the existing proposed commit stack
        without importing unrelated downstream data.
- **Evidence:**
  - [x] Regressions with differing generated cache and PID-named root-file populations
        pass source-authority
        parity while preserving artifact differences; modifying or removing a
        pre-existing source file still changes source identity. All 52 focused harness
        inventory tests pass; the downstream-sized reproduction remains part of the
        0.10.0 release qualification matrix.

### [x] UPDATE-LOCAL-ROUTING-001 — Preserve project-owned local routing authority during update

- **Priority:** P0 (0.10.0 downstream migration blocker; complete)
- **Release target:** 0.10.0
- **GitHub issue:** [#306](https://github.com/NVIDIA-dev/literate-ai/issues/306)
- **Owner:** repository update prospective validation and generation-input closure
- **Direction:** After the #244 transaction-order fix, `litai update` must preserve and
      validate an intentional project-owned routing file and its paired workflow
      instead of rolling back with `inputs.closure_unavailable`.
- **Conclusion:** Issue #306 is downstream of but mechanistically distinct from #244.
      The update now reaches full prospective validation, where project-owned local
      routing is evaluated without the local generation authority it requires. Trace
      ownership and closure resolution before changing validation; do not weaken
      closure checks or treat the local route as an obsolete duplicate of the nested
      production route.
- **Depends on:** The shipped #244 dependency-closed update transaction and a reduced
      fixture preserving both distinct routing policies.
- **Implementation:**
  - [x] Reduce the telemetry-dashboard topology to a framework fixture; trace
        prospective-tree discovery and generation-input closure for local-only routing
        and workflow files; preserve local ownership through the update transaction;
        enforce the same closure invariant for ordinary validate and update; retain
        atomic rollback for genuinely unavailable inputs.
- **Evidence:**
  - [x] The minimal dual-route fixture reproduces the pre-fix
        `inputs.closure_unavailable` result; update preserves both project-owned and
        inherited routing policies and validates successfully; a genuinely missing
        local workflow still fails closed and rolls back byte-for-byte. An isolated
        clone of `telemetry-dashboard` applies the updated framework successfully while
        retaining its project-owned `routing/dev.json` and `workflows/dev/workflow.md`;
        cross-platform update flows remain an exact-candidate gate.

### [x] JAVASCRIPT-NPM-LIFECYCLE-001 — Bind npm permission to Flavor and lifecycle

- **Priority:** P0
- **Release target:** 0.10.1 recovery
- **GitHub issues:** [#326](https://github.com/NVIDIA-dev/literate-ai/issues/326),
      [#329](https://github.com/NVIDIA-dev/literate-ai/issues/329), and
      [#330](https://github.com/NVIDIA-dev/literate-ai/issues/330)
- **Owner:** JavaScript generation skills, Standard command projection, and local npm
      lifecycle
- **Decision:** [ADR 0036](../../decisions/0036-selection-bound-npm-dependency-lifecycle.md)
- **Direction:** Keep JavaScript dependency-free unless `package-npm` is selected.
      With that exact Flavor, admit only an enumerated source-SBOM closure plus a
      complete `package-lock.json`, bind the complete npm implementation and its
      Node-resolved closure to the selected Node runtime, and replay it in disposable
      object storage before packaging the runtime tree.
- **Conclusion:** The contradiction is executable rather than editorial. The exact
      combined generation prompt says both that npm is permitted and that npm packages
      are forbidden, while the production Standard builder only syntax-checks and
      copies JavaScript. The older npm implementation remained on an obsolete WIP and
      was not integrated with Standard command authority or explicit Flavor selection.
      A late npm 11 `pg@8.23.0` reproduction also proved that standard v3 path-derived
      names, locked optional runtime nodes, satisfied required peers, and explicitly
      absent optional peers must be projected rather than rejected.
- **Implementation:**
  - [x] Make the portable JavaScript skill conditional and keep model execution out of
        host tool detection, dependency installation, global install, and publication.
  - [x] Add a typed npm command profile contributed by `package-npm`, bind an exact npm
        implementation and dependency closure executed by the selected Node runtime,
        and reject dependency-bearing manifests without the selected Flavor before
        invoking npm.
  - [x] Replay the supplied complete lock with lifecycle scripts disabled in a
        disposable `OBJ_DIR` projection; retain runtime dependencies in the artifact,
        verify source and lock immutability, and clean partial failures.
- **Evidence:**
  - [x] Actual combined recipe prompts with and without `package-npm` are consistent.
  - [x] Exact local fixtures prove locked dependency execution with the Flavor,
        rejection without it, missing-lock and tool-drift failure, standard npm 11 v3
        `pg@8.23.0` graph and inventory agreement, no lifecycle scripts, and no source
        mutation, global install, or publication.
  - [x] Focused npm tests pass; the exact 0.10.1 release line passes 3,490 local
        tests plus lint, format, strict OpenSpec, documentation, identity, skill, and
        installed-wheel gates. Exact hosted trunk run 33997044552 and release-line run
        33997504560 each pass all 15 Linux, macOS, and Windows jobs.

### [x] EXTERNAL-ACCEPTED-SOURCE-GUARD-001 — Reject an unenforceable no-model request

- **Priority:** P0 release blocker
- **Release target:** 0.10.1 recovery
- **GitHub issue:** [#331](https://github.com/NVIDIA-dev/literate-ai/issues/331)
- **Owner:** rebuild CLI authority dispatch and external lifecycle boundary
- **Direction:** `--from-accepted-source` must never become advisory. Continue through
      the Standard lifecycle only when every Component has exact verifier-admitted
      membership; reject external drivers before planning or execution because their
      versioned request contract carries no accepted-source-only field.
- **Conclusion:** The release-candidate receipt reproduction launched authenticated
      Codex processes while its retained cache decision reported `cache-unconfigured`,
      `fresh_generation_required: true`, and `generation_skipped: false`. The flag was
      introduced for the in-process Standard driver but exposed by the shared rebuild
      parser. External driver binding, source-cache control, and the sample runner all
      omit the invariant, so ordinary generation remained authorized. Full external
      support requires a future versioned protocol; this patch closes the fail-open
      surface without pretending a generated-source cache is verifier admission.
- **Implementation:**
  - [x] Reject accepted-source-only mode for an external lifecycle driver before
        binding the executable or allocating runtime and candidate paths.
  - [x] Keep the Standard path unchanged and clarify the CLI help scope.
- **Evidence:**
  - [x] A public CLI regression selects a real external driver document and proves the
        binding adapter is never called and no runtime or candidate path is created.
  - [x] A paired Standard-driver regression proves the same flag still reaches the
        in-process rebuild authority.

### [x] LOCAL-BUILD-CACHE-TRUST-001 — Bind cache hits to external evidence

- **Priority:** P1
- **Release target:** 1.1.0
- **Previous release target:** 0.11.0
- **GitHub issue:** [#327](https://github.com/NVIDIA-dev/literate-ai/issues/327)
- **Owner:** Local Standard build-cache custody and lifecycle restart evidence
- **Direction:** A cached artifact must not authenticate its own bytes. Bind each
      reusable native, npm, Bazel, or Cargo artifact to an expected identity retained
      outside the candidate object and carried by restart evidence; otherwise rebuild
      in disposable custody and compare before reuse.
- **Conclusion:** A coordinated rewrite of an artifact, its dependency evidence, and
      its self-declared tree manifest can pass the generic Local Standard cache check.
      The 0.10.1 npm lifecycle is contained by a same-runtime external checkpoint and
      cold replay, but the uniform durable contract is broader 0.11.0 work.
- **Implementation:**
  - [x] Define one external artifact/evidence checkpoint shared by native, npm, Bazel,
        and Cargo builders and bind it to the exact build plan and authorization.
  - [x] Carry that checkpoint through lifecycle restart without treating cache bytes
        as authority; rebuild and compare when no trusted checkpoint exists.
  - [x] Reuse a sealed command-addressed slot across later wall-clock grants. The
        checkpoint still authenticates the artifact tree; plan and authorization
        identities stay audit metadata so `litai test` after `litai build` cannot
        rebuild into an occupied slot.
- **Evidence:**
  - [x] Coordinated self-manifest rewrites fail before test or execution for every
        builder, while unchanged same-run and restarted cache hits remain observable.
        PR #338 (`33f1821e`) and follow-up `c190d589` added rejection regressions for
        Bazel, Cargo, native/local, and npm, plus restarted-runtime coverage proving
        legitimate cache hits still succeed.

### [x] NPM-CONSTRAINT-AUTHORITY-001 — Make Standard consume the host npm constraint

- **Priority:** P1
- **Release target:** 1.1.0
- **Previous release target:** 0.11.0
- **GitHub issue:** [#328](https://github.com/NVIDIA-dev/literate-ai/issues/328)
- **Owner:** package-npm host SBOM, toolchain constraint projection, and npm discovery
- **Direction:** Remove the independently maintained `>=9,<13` version range from the
      Python adapter. Host installation, doctor/preflight, and Standard projection
      must consume one exact selected-Flavor constraint authority and bind it into
      lifecycle evidence.
- **Conclusion:** The 0.10.1 values agree and verified npm 9, 10, and 11 distributions
      pass, so this does not block the recovery release. Treat future range drift as a
      fail-closed 0.11.0 factoring issue rather than adding another implicit fallback.
- **Implementation:**
  - [x] Express lower and upper npm bounds once in selected Flavor/SBOM authority.
  - [x] Project that authority through host install and Standard npm discovery.
  - [x] Bind the constraint identity and reject missing/conflicting authority.
- **Evidence:**
  - [x] Linux, macOS, and Windows tests cover separate Node/npm prefixes and boundary
        versions without a duplicate product range in Python. PR #337 removed the
        `>=9,<13` literal from the Python adapter and added boundary tests (9.0.0
        accepted, 13.0.0 rejected) that run in CI across all three platforms.

### [x] CONVERSION-ROOT-STAGE-COVERAGE-001 — Do not repeat internal repo-man builds

- **Priority:** P0
- **Release target:** 0.10.1 recovery
- **GitHub issue:** [#325](https://github.com/NVIDIA-dev/literate-ai/issues/325)
- **Owner:** conversion harness inventory, automatic baseline/parity, and retained
      receipt execution
- **Direction:** When repo-man discovery records a canonical undotted root `build`,
      execute it once as automatic qualification authority and record nested
      `build.*` stages as covered. Preserve every nested stage in inventory and as a
      manually callable wrapper target. Without a root build, execute nested stages
      normally.
- **Conclusion:** `inspect_harness()` correctly preserved the root and one-child
      repo-man entrypoints, but `_partition_execution_stages()` equated inventory with
      automatic execution. A real Phase 1b run completed the canonical root build in
      about 4.5 hours, then invoked the internal `runtime/repo.sh` standalone and
      failed on prerequisites owned by root orchestration. A blanket dotted-stage
      filter would hide unrelated independent stages and would make the newer retained
      receipt path reject a covered child as unavailable; the coverage rule must be
      repo-man-specific and shared by baseline, parity, retained execution, and its
      lifecycle plan.
- **Implementation:**
  - [x] Classify only nested repo-man `build.*` stages as covered when the same
        inventory contains an undotted `build`; retain every wrapper target and run
        independent dotted stages or rootless repo-man stages normally.
  - [x] Exclude covered stages from retained automatic admission and lifecycle command
        plans without weakening unavailable-driver failure for admitted stages.
  - [x] Align the repo-man skill, Flavor requirement, and initialized template copies
        with the automatic-coverage versus manual-callability contract.
- **Evidence:**
  - [x] Focused integration tests prove one root baseline/parity execution, retained
        receipt exclusion, nested manual wrapper invocation, independent dotted-stage
        execution, rootless nested repo-man execution, and an execution-plan projection
        that names only commands the retained runner will actually invoke. The focused
        and adjacent initialization/template suites pass 132 tests with 182 subtests;
        the changed skill, strict OpenSpec, Ruff, and documentation gates pass.
  - [x] Downstream GitLab pipeline 66415219 / job 427365816 passed the canonical root,
        parity, and lift-shift builds without launching nested `runtime/repo.sh`;
        converted revision `bae103ca` produced `phase1b.bundle`. Full local release
        validation passed, and GitHub release-branch CI 33986510390 passed all jobs at
        `3eb7638a`.

### [x] STANDARD-CACHE-PUBLICATION-001 — Publish source only after project acceptance

- **Priority:** P0
- **Release target:** 1.1.0
- **Previous release target:** 0.10.1 recovery
- **Owner:** Standard project lifecycle and accepted source-cache contracts
- **Direction:** Keep generated source private to its current lifecycle until root
      assembly, packaging, packaged execution, and independent project acceptance all
      succeed; only then may a non-hit become visible in an accepted source cache.
- **Conclusion:** The `loan-risk-gate` receipt rebuild exposed a publication-order bug,
      not a corrupt cache or incapable model. A candidate that followed DMN-internal
      uppercase names passed its generated component tests, was published, and then
      failed the lowercase/full-result public contract at independent packaged
      acceptance. Exact retries replayed that verifier-rejected cache entry without a
      new coding-agent call. Publication ownership now follows the project acceptance
      boundary, while incomplete lifecycle evidence can represent accepted but
      deliberately unpublished component work.
- **Depends on:** Standard root integration and independent acceptance
- **Implementation:**
  - [x] Stage each accepted non-hit membership in its node result without mutating the
        cache or recording a publication checkpoint.
  - [x] After independent project acceptance, publish canonical Component order,
        rebind result/membership/attempt-chain identities to actual publication, then
        admit the project and issue its receipt.
  - [x] Preserve restartable partial publication after project acceptance: an entry
        successfully written before a later publication failure is safe and idempotent.
- **Evidence:**
  - [x] A poisoned default cache reproduces the same verifier failure without invoking
        Codex; a wholly isolated cache invokes Codex and passes the exact sample.
  - [x] Contract tests prove every root-boundary failure performs zero cache writes and
        emits zero publication checkpoints, while success orders independent acceptance
        before publication and publication before admission/receipt.
  - [x] A clean-cache `loan-risk-gate` run passes six tests, three generated tests, and
        one independent verifier case; the broad Python gate passes 3,439 tests with 31
        declared skips.
  - [x] Complete an exact external receipt rebuild for all 31 derivations after the
        project-acceptance publication change.
  - [x] Exact wheel, isolated install, and installed-project E2E checks pass; the full
        local gate passes 3,445 tests with 31 declared skips on `24753f32`.
  - [x] Hosted qualification is complete for the shipped 0.10.1 recovery.
        Release-line commit `2a333878` has byte-identical lifecycle ports,
        project lifecycle, membership contracts and their tests to original
        `1cf709dd`. It is an ancestor of `cc4e81d2`, whose complete 15-job
        [hosted matrix](https://github.com/NVIDIA-dev/literate-ai/actions/runs/33983417499)
        passes. Published `v0.10.1` at `b0888f7f` also passes its complete
        [hosted matrix](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34004424520).
        These current forge observations close the historical hosted gate;
        RELEASE-INTEGRATION-001 still owns fresh consolidated 1.1 qualification.

### [x] COMMITTED-CACHE-EMPTY-001 — Admit Git's empty committed-cache representation

- **Priority:** P0
- **Release target:** 1.1.0
- **Previous release target:** 0.10.1 recovery
- **Upstream issue:** [#320](https://github.com/NVIDIA-dev/literate-ai/issues/320)
- **Owner:** filesystem-v2 read-only adapter and Standard declared-target composition
- **Direction:** Treat a canonical format marker with no managed namespaces as the
      portable empty representation of a committed source-cache target, without
      creating directories or weakening validation of any populated layout.
- **Conclusion:** The downstream project's writable `standard-local` target opens, but
      its read-only `project-committed` target contains only canonical `format.json`.
      Git cannot store the empty directories created by the writable adapter. Standard
      planning and toolchain probing complete before target composition, after which
      the read-only constructor rejects the first absent managed descendant. The
      v0.10.0 and then-current implementations were identical at this boundary; no symlink,
      race, retry, or stale cache state is required.
- **Implementation:**
  - [x] Validate the format marker first and represent an exact namespace-empty
        read-only target as unavailable, so every lookup is an empty miss.
  - [x] Preserve fail-closed mandatory entry/key/CAS validation for populated targets,
        while allowing Git to omit empty optional source-intelligence namespaces.
  - [x] Include the exact managed path in path-safety diagnostics.
- **Evidence:**
  - [x] Adapter tests cover format-only non-mutation, partial-layout rejection with the
        exact path, and a populated cache whose empty intelligence namespaces were
        omitted.
  - [x] Standard target-composition coverage opens a format-only project-relative
        target as an empty miss.
  - [x] The actual telemetry-dashboard checkout now resolves both declared targets and
        leaves its committed format marker byte-for-byte unchanged.
  - [x] The full local gate passes 3,445 tests with 31 declared skips, including the
        adapter and Standard target-composition regressions, on `24753f32`.
  - [x] The exact downstream `litai test` reproduction passes with the 0.10.1
        candidate after backport, and exact-head hosted CI passes.
        **Historical evidence reconciled for 1.1:** [issue #320's terminal
        validation](https://github.com/NVIDIA-dev/literate-ai/issues/320#issuecomment-5553868592)
        records the isolated non-editable release-line package, reviewed Standard
        rebind and successful three-test downstream reproduction at `cc4e81d2`,
        preserving the format-only committed cache. That exact commit passes all
        15 checks in [run 33983417499](https://github.com/NVIDIA-dev/literate-ai/actions/runs/33983417499).
        The published `v0.10.1` commit `b0888f7f` descends from it and also passes
        all 15 checks in [run 34004424520](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34004424520).
        The canonical cache fix `8119e53b` is an ancestor of the current candidate.
        Current cache/update/rebind regressions pass as a 44-test batch at
        `33630a4f`; this is historical obligation closure, not a new live 1.1
        downstream receipt. Duplicate CACHE-EMPTY-RO-001 uses the same evidence.

### [x] RELEASE-SKILL-CLOSURE-001 — Keep derived release guidance self-contained

- **Priority:** P0
- **Release target:** 1.1.0
- **Previous release target:** 0.10.1 recovery
- **Upstream issue:** [#322](https://github.com/NVIDIA-dev/literate-ai/issues/322)
- **Owner:** inherited release-project skill and initialized-project skill closure
- **Direction:** Every mandatory Markdown resource named by the release skill copied
      into a derived project must also exist in that derived project. Keep the small
      significant-feature governance rule in the skill instead of routing an agent to
      framework-only documentation.
- **Conclusion:** The issue's named `project-releases.md` route was removed before
      0.8.0. The reproduced historical defect was the mandatory ADR 0006 route:
      derived projects received `release-project/SKILL.md` but not the framework's
      `docs/decisions/` tree. Release-line fix `d8844e32` and recovery `728a45f1`
      carry the bounded rule within the copied closure. Current initialized-project
      validation confirms the reference closure; no release mechanics are bypassed.
- **Next action:** Complete; reconcile the already shipped fix with the exact
      historical release evidence below, not a new 1.1 live acceptance claim.
- **Implementation:**
  - [x] Inline the bounded ADR/acceptance/work-recording sequence and route its final
        step to the copied `record-user-directed-work` skill.
- **Evidence:**
  - [x] An initialized derived-project fixture resolves every backtick-delimited
        Markdown path in its copied release skill without an upstream checkout.
  - [x] Focused initialization, catalog/template parity, and pinned SkillEvaluator
        checks pass; lifecycle-driver and documentation authority pins are current.
  - [x] An exact 31-derivation rebuild under the re-pinned driver promotes a current
        231-test project receipt on `28712d17`.
  - [x] Full local, backport, and exact-head hosted CI gates pass.
        [Issue #322's terminal evidence](https://github.com/NVIDIA-dev/literate-ai/issues/322#issuecomment-5553880574)
        records the 73-test release-line initialization/update/rebind pass.
        [Run 33983417499](https://github.com/NVIDIA-dev/literate-ai/actions/runs/33983417499)
        passes all 15 jobs at `cc4e81d2fe94466bf2b482626cda61e981b3963c`;
        [published 0.10.1 run 34004424520](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34004424520)
        passes all 15 at `b0888f7f51d031c2f0a1660cc484f3ff861f3329`.
        Recovery `728a45f1` is an ancestor of `33630a4f`, whose fresh full local
        Python gate passes 4,204 tests with 30 skips in 2,352.861 seconds; terminal
        stderr identity is `sha256:ba7d6a613b5492bc72eead60f363271677874dcdde48a7ae9701d8d25bb5f852`.
        The current derived-reference fixture and five workspace-link tests also
        pass as a six-test confirmation in 2.994 seconds. These results do not
        refresh the current generated-project receipt or close other 1.1 gates.

### [x] RETRY-DERIVATION-BINDING-001 — Keep retry provenance out of the planned key

- **Priority:** P0
- **Release target:** 1.1.0
- **Previous release target:** 0.10.1 recovery
- **Owner:** conformance lifecycle receipt projection and outer source-cache protocol
- **Direction:** Preserve the immutable derivation manifest when bounded candidate
      repair adds prior rejection evidence to a later coding-agent prompt, while
      retaining that accepted attempt's exact request identity in provenance.
- **Conclusion:** A clean project receipt produced all 31 accepted derivations but
      failed exact lifecycle closure for two retried legacy samples. The outer planner
      froze each attempt-1 request identity before execution; the receipt builder later
      reconstructed those two keys from attempt-2 prompts containing rejection
      feedback. Publication was complete and the stable recipe/plan/tool/model axes
      were unchanged, so the defect is a derivation-versus-attempt identity conflation,
      not lost cache state or concurrent manifest mutation.
- **Depends on:** STANDARD-CACHE-PUBLICATION-001 and outer-owned derivation planning
- **Implementation:**
  - [x] Bind a legacy execution to its unique outer-planned key after validating its
        stable axes; permit a request-identity difference only with a complete ordered
        candidate retry chain.
  - [x] Match the source-semantics axis exactly so outer-bound Standard members retain
        their non-null semantics identity while legacy retry members remain null.
  - [x] Preserve the accepted attempt's request identity in provenance evidence rather
        than rewriting it to the planned request.
- **Evidence:**
  - [x] The failing clean run produced 31 planned and 31 published entries; exactly two
        lifecycle identities diverged, matching the Rust roundtrip and Python service
        retries, while the rejected Rust tree appeared only in rejection evidence.
  - [x] Focused contract and receipt tests prove successful rebinding, exact final-prompt
        provenance, non-null Standard semantics binding, and fail-closed behavior for
        incomplete retry evidence or stable-axis drift.
  - [x] A cache-backed full project receipt rerun closes all 31 derivations and promotes
        a current 231-test receipt on the exact trusted driver revision.
  - [x] The full local gate passes 3,445 tests with 31 declared skips on `24753f32`.
  - [x] Hosted qualification is complete for the shipped 0.10.1 recovery.
        Release-line commit `7a0df668` has byte-identical sample-runner and
        sample-ladder regression files to original `13f6124b`, including the
        planned-key retry proof. It is an ancestor of `cc4e81d2`; all 15 jobs
        pass in [run 33983417499](https://github.com/NVIDIA-dev/literate-ai/actions/runs/33983417499).
        Published `v0.10.1` at `b0888f7f` passes its complete
        [hosted matrix](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34004424520).
        This closes the historical retry-binding gate; a fresh 1.1 lifecycle
        receipt remains part of RELEASE-INTEGRATION-001.

### [x] UPDATE-ORIGIN-001 — Normalize equivalent GitHub update origins

- **Priority:** P0
- **Release target:** 1.1.0
- **Previous release target:** 0.10.1 recovery
- **GitHub issue:** [#316](https://github.com/NVIDIA-dev/literate-ai/issues/316)
- **Owner:** initialized-project update origin contracts and filesystem update planner
- **Direction:** Let a project initialized from the HTTPS form of the official GitHub repository update from a reviewed wheel that embeds the equivalent SSH form, without weakening provenance checks for any different host, owner, repository, credential, non-default port, or local/file origin.
- **Conclusion:** The official 0.10.0 wheel embeds the checkout's SCP-style SSH remote while existing derived projects can record the HTTPS spelling. At diagnosis, `FilesystemProjectUpdateAdapter.plan` compared those strings directly after Standard rebind and rejected one repository solely because its transport notation changed. The implemented deterministic comparison is used at the update trust boundary; exact origin records, their content identities and Standard rebind's acknowledged installed-distribution evidence remain unchanged.
- **Depends on:** STANDARD-REBIND-001 and the 0.10.1 versioned recovery
- **Implementation:**
  - [x] Add conservative GitHub SSH/HTTPS repository-coordinate comparison and use it only for the update planner's repository continuity check.
  - [x] Preserve exact origin serialization and identity; do not rewrite durable 0.8/0.9 initialization evidence merely to normalize a comparison.
- **Evidence:**
  - [x] The official 0.10.0 wheel's embedded SCP-style origin and an HTTPS-initialized project plan successfully through the real filesystem adapter.
  - [x] Different hosts, owners, repositories, HTTP downgrade, SSH users, non-default
        ports, and file origins remain distinct; the focused coverage and full local
        gate pass on `24753f32`.
  - [x] Exact-head hosted CI passes. [Issue #316's terminal validation](https://github.com/NVIDIA-dev/literate-ai/issues/316#issuecomment-5553880580)
        records the 73-test update/initialization/rebind batch on release-line
        `cc4e81d2`, including conservative rejection cases. All 15 hosted checks
        pass on that exact commit in [run 33983417499](https://github.com/NVIDIA-dev/literate-ai/actions/runs/33983417499)
        and on published `v0.10.1` commit `b0888f7f` in
        [run 34004424520](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34004424520).
        The repository-equivalence helper is unchanged between `cc4e81d2` and
        current candidate `33630a4f`; the current cache/update/rebind batch passes
        44 tests. Duplicate ORIGIN-SSH-HTTPS-001 shares this completed recovery;
        no separate normalization of reviewed rebind evidence is implied.

### [x] UPSTREAM-ISSUE-FIRST-001 — Require issue-first escalation for reusable upstream discoveries

- **Priority:** P0
- **Release target:** 0.10.0
- **GitHub issue:** [#308](https://github.com/NVIDIA-dev/literate-ai/issues/308)
- **Owner:** record-user-directed-work skill and project tracker adapters
- **Direction:** When a derived project discovers a reusable defect or improvement owned by an ancestor, search and then file or link a sanitized provider-neutral issue in the owning upstream tracker before implementation, preserving reciprocal downstream linkage and all existing authorization boundaries.
- **Conclusion:** Issue #308 identifies a process authority gap: downstream roadmap capture and direct branch work do not create durable upstream triage. Tracker inspection, duplicate search, sanitized issue drafting, explicit external-write authorization, and resumable unsupported or unauthenticated states belong in the shared work-recording process.
- **Depends on:** TRACKER-HOST-001
- **Implementation:**
  - [x] Update root and initialized record-user-directed-work skills with issue-first ownership routing, de-duplication, sanitization, reciprocal links, and fail-closed draft handling.
  - [x] Provide deterministic GitHub and GitLab tracker command projections and fixtures without embedding downstream-specific or secret-shaped data.
- **Evidence:**
  - [x] GitHub, GitLab, existing-issue, secret-shaped input, unsupported, unauthenticated, and source/template parity tests pass in `test_issue_first_work_skill` and project-tracker coverage.

### [x] STANDARD-REBIND-001 — Add a reviewed Standard lifecycle distribution rebind

- **Priority:** P0
- **Release target:** 1.1.0
- **Previous release target:** 0.10.0 (original implementation shipped)
- **GitHub issue:** [#309](https://github.com/NVIDIA-dev/literate-ai/issues/309)
- **GitHub issue:** [#376](https://github.com/NVIDIA-dev/literate-ai/issues/376)
- **Owner:** Standard lifecycle binding CLI and installed-distribution adapters
- **Direction:** Provide an explicit plan/apply operation that advances a project Standard distribution pin to one reviewed non-editable installed Literate AI distribution after an intentional upgrade, without building code or silently changing authority during update.
- **Conclusion:** Issue #309 is a fail-closed upgrade deadlock, not a reason to weaken distribution identity checking. A compare-and-swap rebind must expose old and proposed identities and origin/version evidence, reject editable or ambiguous installs and drift, atomically change only owned binding fields, and leave prior receipts stale until rebuild.
- **Depends on:** Standard lifecycle distribution identity and project update contracts
- **Next action:** Complete: PR #375 landed as main `2f09c295` after all 15
      hosted checks passed on `66fd355e`; #376 is closed with linked evidence.
      Inspection confirms the planner always replaces the configured suite with
      the installed Standard suite. A non-Standard suite remains project-owned:
      retain its suite, evidence kinds and test floor, advancing its runner only
      when it exactly equals the old Standard driver identity. Preserve an
      independent harness runner unchanged. Revalidate that projection on apply
      and report only actually changed fields; do not weaken distribution checks.
- **Implementation:**
  - [x] Add dry-run and explicitly authorized apply CLI paths using the existing trusted installed-distribution observer and atomic project store.
  - [x] Document upgrade, update, reviewed rebind, and rebuild ordering in source and initialized troubleshooting authority.
  - [x] Preserve project-owned receipt contracts across rebind and reject reviewed
        plans that replace them; retain normal Standard-suite upgrade behavior.
        Four new focused regressions failed against the old implementation and
        pass after the repair; a public CLI plan/apply fixture also preserves the
        custom legacy-parity policy. Only installed-distribution observations are
        mocked in that CLI test; no installed-wheel or live rebuild claim is made.
- **Evidence:**
  - [x] Clean-wheel upgrade, no-op, editable, changed policy, tampered payload, write rollback, receipt staleness, and portable path tests pass in `test_standard_lifecycle_rebind`.
  - [x] Regression tests prove custom independent and Standard-derived runners,
        custom no-op, exact changed fields, stale/tampered policy refusal, and
        unchanged Standard-suite upgrades; complete local and hosted gates pass.
        The 32-test rebind/policy/receipt-CLI suite passes on macOS, including
        rehashed policy/change-summary rejection and byte-preserving no-op.
        Reviewed the one-file lifecycle-driver closure change and refreshed its
        pin/documentation authority. The existing test receipt is unchanged.
        Fresh full qualification ran 3,811 tests (3,781 passed, 30 skipped,
        no failures); [CI 34594250773](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34594250773)
        passed every job before [PR #375](https://github.com/NVIDIA-dev/literate-ai/pull/375) merged.

### [x] PORTABLE-MAKE-QUOTING-001 — Teach generated Make language-tool quoting wherever it is enforced

- **Priority:** P0
- **Release target:** 0.10.0
- **GitHub issue:** [#310](https://github.com/NVIDIA-dev/literate-ai/issues/310)
- **Owner:** portable application skills and generated-source contract tests
- **Direction:** Repair the 0.9.0 regression in issue #310 by making every portable application authority that can emit a Makefile explicitly require the exact quoted language-tool expansion accepted by the generated-source validator.
- **Conclusion:** The validator is correct to protect executable paths containing spaces; the defect is enforcement/guidance drift. Teach the invariant in the narrow common portable skill and relevant language skills, preserve template parity, and add generation-contract coverage so future validators cannot gain untaught requirements.
- **Depends on:** Generated Makefile validation and portable application skill hierarchy
- **Implementation:**
  - [x] Update the common and per-language portable application skills plus initialized copies with the exact quoted recipe contract.
  - [x] Add source/template and validator-to-skill contract tests for every supported language that can emit generated Make recipes.
- **Evidence:**
  - [x] The reported unquoted fixture fails, corrected generated Makefiles pass, source/template parity holds, and every Make-capable portable language skill is covered by `test_make_generation_skill`.

### [x] CONVERT-OUTPUT-CUSTODY-001 — Preserve complete host-heavy build output identities without rejecting successful builds

- **Priority:** P0
- **Release target:** 0.10.0
- **GitHub issue:** [#311](https://github.com/NVIDIA-dev/literate-ai/issues/311)
- **Owner:** release engineering
- **Direction:** Ship issue #311 in 0.10.0: retain bounded diagnostic excerpts while computing identities over complete stdout and stderr, and do not turn a zero-exit build into a failure solely because output exceeded the retained excerpt limit.
- **Conclusion:** The host-heavy conversion baseline currently conflates retained diagnostic size with execution success; custody and observability must be separated from the build result.
- **Depends on:** RELEASE-CLOSURE-001
- **Implementation:**
  - [x] Integrate and review the focused output-custody commits, preserve complete stream hashes and useful tails, keep nonzero exits and timeouts failing, and bind the behavior into conversion contract tests.
- **Evidence:**
  - [x] Focused tests cover successful oversized output, full-stream identity, retained prefix/tail diagnostics, nonzero exit, and timeout behavior. Exact-candidate 0.10.0 release gates remain release-level evidence.

### [x] CI-BYTECODE-CUSTODY-001 — Keep direct pytest workers out of authored authority

- **Priority:** P0 (0.10.0 exact-candidate CI blocker; complete)
- **Release target:** 0.10.0
- **GitHub issue:** [#312](https://github.com/NVIDIA-dev/literate-ai/issues/312)
- **Owner:** profiled pytest adapter and CI source-tree custody
- **Direction:** A direct pytest shard must preserve the same no-source-bytecode
      invariant as Makefile-driven tests, including every spawned xdist worker.
- **Conclusion:** The failed Windows shard was not a documentation or Windows-path
      defect. The CI adapter bypassed the Makefile's `PYTHONPYCACHEPREFIX`, so importing
      the Google publication helper wrote a `.pyc` into the declared documentation root
      and a later canonical validation correctly rejected it as an unreferenced asset.
      Suppress bytecode at the pytest adapter boundary and propagate that policy through
      the environment; do not teach documentation validation to ignore contamination.
- **Depends on:** RELEASE-CLOSURE-001
- **Implementation:**
  - [x] Set and restore both the coordinator runtime flag and the child-process
        environment around the profiled pytest run so in-process callers retain their
        prior state and xdist workers inherit source-preserving behavior.
- **Evidence:**
  - [x] The publication-import plus canonical-validation sequence fails without the
        invariant and passes under one xdist worker after the repair, leaving no
        `__pycache__` beneath the documentation package; focused runner tests also prove
        environment and runtime state restoration.

### [x] INSTALLED-OFFLINE-RELEASE-001 — Isolate offline release proof from live tracker closure

- **Priority:** P0 (0.10.0 exact-candidate CI blocker; complete)
- **Release target:** 0.10.0
- **GitHub issue:** [#314](https://github.com/NVIDIA-dev/literate-ai/issues/314)
- **Owner:** installed-project release smoke policy
- **Direction:** The installed release-state-machine proof must remain offline even
      though canonical initialized projects now require a live GitHub or GitLab
      contribution sweep.
- **Conclusion:** Commit `700a8abc` added continuous contribution closure to the
      initialized release policy, while the installed smoke continued to use a local
      filesystem bare remote and disabled only its publication provider. Tracker
      classification correctly rejected that remote. Remove contribution closure only
      from the deliberately offline fixture; retain it in canonical project policy and
      retain fail-closed tracker classification for real releases.
- **Depends on:** RELEASE-CLOSURE-001
- **Implementation:**
  - [x] Remove the inherited contribution policy when preparing the smoke project's
        offline release policy without changing the source project template.
- **Evidence:**
  - [x] The pre-fix installed flow reproduces
        `release.contributions_tracker_unsupported` on GitHub Ubuntu/Python 3.11 and
        local macOS/Python 3.13 after installation and local push; the repaired exact
        flow completes plan, prepare, publish, remote line/tag verification, and
        idempotent publication retry. Exact-candidate hosted matrix evidence remains a
        release-level gate.

### [x] TRACKER-SWEEP-001 — Close completed tracker residue and delete superseded remotes

- **Priority:** P1 (operator-authorized tracker and branch residue)
- **Owner:** GitHub tracker, origin remotes, and docs/roadmap/active-work.md landing queue
- **Direction:** Resolve every open pull request, issue, and unmerged branch rather than leaving residue beside the 0.10.0 adoption line.
- **Conclusion:** Open PRs are already empty. Delete two closed-PR remotes whose unique commits were superseded on main. Close GitHub #83-#86 because CI-SHARD-001 and CI-IMPACT-001 are complete. Keep release/0.5.x through release/0.9.x. Leave remaining open issues that still have unchecked queue items.
- **Depends on:** QUEUE-HYGIENE-001
- **Next action:** Done. Open PRs were already empty. Superseded remotes deleted. #83–#86 closed. Remaining open issues stay mapped to unchecked queue items.
- **Implementation:**
  - [x] Delete origin/experimental/jordanh/lfs-null-manifest after confirming PR #259 closed as superseded
  - [x] Delete origin/fix/convert-env-bound-prereq-closure after confirming PR #197 closed as do-not-revive
  - [x] Comment and close GitHub issues #83 #84 #85 #86 citing completed CI-SHARD-001 and CI-IMPACT-001
  - [x] Leave remaining open issues mapped to unchecked queue items; do not merge release branches into main
- **Evidence:**
  - [x] `gh pr list --state open` returned an empty list on 2026-09-04
  - [x] `git fetch --prune` leaves only origin/main and origin/release/0.5.x through origin/release/0.9.x
  - [x] Closed #83–#86 as completed with comments linking `16036216` L6547–L6605 and L6607–L6664
  - [x] Remaining open issues: #307 APP-SETTINGS-001, #301 INIT-CONVERT-FORCE-001, #295/#296 OBSERVE-HTML-001, #286 WORKER-GIT-CRED-001, #280 LIBRARY-ARTIFACT-001, #279 SUBMODULE-ORCH-001, #251 GOLDEN-PATH-001/RELEASE-017; 2026-09-05 additions #320 CACHE-EMPTY-RO-001, #316 ORIGIN-SSH-HTTPS-001, #315 CONVERT-NESTED-GIT-001, #317 STANDARD-CACHE-ENTRY-001, #318 LIFECYCLE-MUTATION-LOCK-001, #319 TESTED-PIN-PLAN-001

### [x] TESTED-PIN-PLAN-001 — Bind durable tested-tag reuse to the test plan

- **Priority:** P1
- **Release target:** 1.0.0
- **GitHub issue:** [#319](https://github.com/NVIDIA-dev/literate-ai/issues/319)
- **Owner:** pin dispatch, project test receipts, and release-gate scheduling
- **Direction:** A durable passing receipt may skip work only when it attests both the
  same content pin and the same current ordered test or gate plan.
- **Conclusion:** Repair markers now preserve and validate their global gate prefix, but
  tested-tag lookup is keyed only by content-pin identity. A synthetic same-pin receipt
  can therefore skip a newly inserted gate whose plan changed without changing that
  identity. Preserve reusable content identities and add a separate deterministic suite-
  or plan-compatibility binding instead of mixing orchestration names into artifact
  hashes.
- **Depends on:** CACHE-007 pin dispatch and project test receipt authority
- **Implementation:**
  - [x] Define a canonical plan identity for each receipt-backed pipeline and require it
    during tested-tag lookup (`pin_plan_identity` in
    `src/literate_ai/application/pinned_test_dispatch.py`).
  - [x] Migrate or invalidate older receipts explicitly; never interpret an unbound
    receipt as attesting a newly changed plan (`MemoryTestedTagStore`'s legacy
    constructor path now fails closed until re-recorded through `record_tested`).
- **Evidence:**
  - [x] Same-content/same-plan receipts still skip without opening declared inputs.
  - [x] Inserting, deleting, or reordering a gate forces evaluation even when the
    content-pin identity is unchanged; cross-pin and legacy-receipt cases fail closed.
    (`tests/critical/test_pinned_test_dispatch.py`:
    `test_inserted_deleted_or_reordered_gate_forces_evaluation`,
    `test_legacy_unbound_receipt_fails_closed`,
    `test_cross_pin_receipt_never_matches_a_different_pin`.)

### [x] STANDARD-CACHE-OVERRIDE-001 — Align Standard source-cache selection with CLI

- **Priority:** P1
- **Release target:** 1.0.0
- **GitHub issue:** [#317](https://github.com/NVIDIA-dev/literate-ai/issues/317)
- **Owner:** Standard rebuild CLI, accepted source-cache custody, and graph planning
- **Direction:** Standard rebuild must either honor its advertised accepted
  `--source-cache-entry` after exact identity and provenance validation or expose an
  equally deterministic supported selection path and stop advertising the rejected
  option.
- **Conclusion:** Duplicate filing of STANDARD-CACHE-ENTRY-001; closed together. Chose
  the bounded fix rather than the graph-level accepted-cache selection contract:
  `litai rebuild --help`, `litai help profile`, and
  `docs/user/configuration-and-cli.md` now say `--source-cache-entry` and
  `--source-cache-root` are supported for an external lifecycle driver only, and the
  Standard rejection error names `--from-accepted-source` as the supported
  deterministic-reuse equivalent. Ordinary Standard rebuild stays BUILD_DIR-backed;
  no new graph-level cache contract was built.
- **Depends on:** Standard source-cache admission and dependency-graph rebuild planning
- **Implementation:**
  - [x] Stop advertising an unsupported per-command override for Standard rebuild and
    point operators at the supported `--from-accepted-source` reuse contract instead
    of building a new graph-level accepted-cache selection contract.
- **Evidence:**
  - [x] `tests/e2e/test_cli_rebuild.py::RebuildCliTests::test_standard_driver_rejects_source_cache_entry_and_names_the_alternative`
    and `::test_standard_driver_rejects_source_cache_root_and_names_the_alternative`
    prove the Standard rejection message names `--from-accepted-source`.
  - [x] `tests/smoke/test_cli_help.py::CliHelpTests::test_rebuild_help_scopes_source_cache_overrides_to_the_external_driver`
    proves `litai rebuild --help` scopes both flags to the external driver.

### [x] PROJECT-LIFECYCLE-LOCK-001 — Serialize project-scoped lifecycle mutation

- **Priority:** P1
- **Release target:** 1.0.0
- **GitHub issue:** [#318](https://github.com/NVIDIA-dev/literate-ai/issues/318)
- **Owner:** Standard lifecycle mutation, checkpoint publication, and receipt updates
- **Direction:** Reject or queue a second project-scoped mutating lifecycle before
  either expensive model pipeline starts, while preserving independent read-only work.
- **Conclusion:** Concurrent rebuilds own separate disposable runtimes but race shared
  project checkpoint and finalization state; one later fails the exact-predecessor
  contract after wasting work. The failure is typed and the 0.10.1 release workflow is
  serialized, so this is a 1.0 lifecycle/concurrency contract rather than a patch-cut
  blocker.
- **Depends on:** Standard rebuild checkpoints and project test-receipt publication
- **Implementation:**
  - [x] Add a portable project lifecycle lock covering rebuild, shared cache-index or
    checkpoint publication, and `--update-receipt`, with owner diagnostics and
    failure-safe release.
- **Evidence:**
  - [x] Concurrent mutation is rejected or queued before model execution on Linux,
    macOS, and Windows; crash recovery is bounded; read-only commands remain available.
    `project_lifecycle_lock` (`src/literate_ai/adapters/lifecycle_lock.py`) reuses the
    existing portable `fcntl.flock`/`msvcrt.locking` primitive from
    `literate_ai._cache_lock`, so a crashed holder's lock releases with the process
    with no PID-file bookkeeping. `tests/critical/test_lifecycle_lock.py` covers a
    deterministic barrier-synchronized concurrent rejection with owner diagnostics,
    success/exception release, a real crashed-process (`multiprocessing`, `os._exit`)
    non-stale-lock check, and cross-project independence.

### [x] REPOSITORY-LINEAGE-CACHE-LOCK-001 — Serialize mutation per repository cache entry

- **Priority:** P1
- **Release target:** 1.1.0
- **Previous release target:** 1.0.0
- **GitHub issue:** [#324](https://github.com/NVIDIA-dev/literate-ai/issues/324)
- **Owner:** repository-lineage snapshot provider and shared object-directory custody
- **Direction:** Make repository-lineage cache mutation process-safe per derived bare
  cache entry without serializing independent repositories, and retain typed,
  non-secret diagnostics for failed acquisition, fetch, and recovery.
- **Conclusion:** Two test processes launched manually from one checkout shared the
  same `_build/repository-lineage` object root and attempted an uncoordinated fetch
  into the same bare cache entry. One failed with Git's competing-process lock
  diagnostic; the exact test passed in 5.5 seconds with an isolated object root and
  left no stale lock. Supported 0.10.1 release validation is serialized and hosted CI
  isolates object roots, so this induced race does not block the patch recovery, but
  the shared-cache contract must be explicit for 1.1. The portable per-entry
  advisory lock landed in `e56d5c0c`; issue #324 is closed. Its initial same-entry
  and independent-entry probes used threads, and abrupt-owner recovery was
  POSIX-only. The separate-process follow-up below now supplies the missing
  three-platform proof.
- **Depends on:** repository-lineage snapshot resolution and portable lock ownership
- **Next action:** Complete. The separate-process follow-up `1dcfa093` is an
  ancestor of the qualified `33630a4f` integration candidate, landed as `cf71a4fc`.
  Preserve these cross-platform regressions; this closure does not qualify the
  separate repository-refresh transaction or the current release receipt.
- **Implementation:**
  - [x] Add a portable per-entry lock around bare-cache creation and fetch, with
        bounded owner diagnostics and failure-safe release or stale-owner recovery.
        Implemented in `e56d5c0c`; the existing 23 lineage/cache-lock tests pass
        on macOS at `d0e1bc5c`, including real POSIX abrupt-owner recovery.
  - [x] Keep unrelated repository cache entries concurrent and read-only snapshot
        consumption available whenever it does not observe a partial mutation.
        Separate-process fetch rendezvous and an immutable old-revision read
        held across a second process's new-revision fetch both pass on macOS.
  - [x] Add separate-process serialization/independence/read-availability tests,
        portable abrupt-owner termination, and credential-safe acquisition errors.
        The 27 lineage/cache-lock tests pass locally; lock bypass and global-lock
        mutations each fail their intended regression. The abrupt-owner test
        now uses `Popen.kill()` on both POSIX and Windows instead of skipping Windows.
- **Evidence:**
  - [x] A deterministic same-URL/same-object-root concurrent-fetch regression never
        exposes Git lock races on Linux, macOS, or Windows.
  - [x] Different repository identities remain concurrent; interrupted owners do not
        leave an unrecoverable lock; failure diagnostics identify the cache entry
        without exposing repository credentials.
        **Hosted qualification:** Exact `33630a4f` passed all 15 jobs in
        [run 34664827991](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34664827991).
        Linux/macOS Python 3.11/3.14 each run the complete 4,204-test discovery.
        Windows Python 3.12's three complementary shards cover that same 4,204
        tests: 1,675 passed / 25 skipped; 526 / 24; and 1,901 / 53. The five
        separate-process serialization, independent-fetch, concurrent-read,
        abrupt-owner and credential-safe diagnostic regressions have no platform
        skip. The implementation/test bytes remain unchanged since this qualified
        candidate; all 22 lineage-adapter tests also pass locally in 18.555 seconds.
        [Issue #324's terminal evidence annotation](https://github.com/NVIDIA-dev/literate-ai/issues/324#issuecomment-5643161431)
        is posted and read back; the issue remains closed.

### [x] HOST-SELF-UPDATE-001 — Prefix-installed litai self-updates from GitHub Releases

- **Priority:** P1 (0.11.0 host-install; not a 0.10.0 backport)
- **Release target:** 0.11.0
- **Owner:** prefix installer, stable launcher, CLI dispatch, and host-install manifest
- **Owning ADR:** [ADR 0037](../../decisions/0037-prefix-installed-cli-self-update.md)
- **Detailed roadmap:** [Prefix-installed CLI self-update](../../roadmap/prefix-cli-self-update.md)
- **Direction:** The prefix-installed litai command should detect a newer GitHub Release, update that same prefix, remember the original argv, and re-invoke itself after the update.
- **Conclusion:** Only enrolled make-install prefixes self-update from NVIDIA-dev/literate-ai GitHub Releases per ADR 0037: background check, apply on the next invocation, re-exec the same argv, fail open. litai update stays project-file reconciliation. Checkouts, CI, and @1 manifests stay inert.
- **Depends on:** HOST-INSTALL-SBOM-001, HOST-UNINSTALL-001
- **Next action:** Complete. Prefix-installed GitHub self-update is enrolled by `make install`; remaining 0.11.0/1.0 queue items are separate.
- **Implementation:**
  - [x] Bump host-install manifest to @2 with self_update and export LITAI_HOST_INSTALL plus LITAI_PREFIX from both launchers
  - [x] Detect enrollment, opt-out, CI, evidence-run, and re-exec guards with no network on inert paths
  - [x] Query GitHub latest non-prerelease wheel, throttle 24h on success and 15m on failure, stage under share/literate-ai/self-update
  - [x] On the next enrolled invocation, lock non-blocking, pip-install the staged wheel locally, refresh launcher and manifest, print old to new on stderr, re-exec original argv
  - [x] Fail open on network, pip, lock, and timeout; never downgrade; never wait on GitHub in the foreground check
  - [x] Uninstall accepts @2 and removes the self-update staging directory; install-check and test prefixes set LITAI_NO_SELF_UPDATE=1
  - [x] Document standing prefix authorization vs litai update; add Unreleased changelog
- **Evidence:**
  - [x] Unit tests cover enrollment gates, opt-out, CI skip, no-downgrade, fixture release selection, cache throttle, staging without venv mutation, apply-then-re-exec argv, recursion guard, fail-open, and uninstall of @2 plus staging
  - [x] make python-check passes the new tests (3444 tests, 32 skipped, 2026-09-05 worktree `docs/adr-0036-prefix-cli-self-update`)
  - [x] `make install-check` on clean `03175d8d`: isolated smoke `ok: true`; drivers set `LITAI_NO_SELF_UPDATE=1`; the gate log has no GitHub Releases API contact
  - [x] docs/user/installation.md states make install authorizes later GitHub self-update of that prefix and distinguishes litai update
  - [x] CHANGELOG.md Unreleased names the operator-visible behavior and ADR 0037

### [x] CACHE-EMPTY-RO-001 — Treat empty Git-unrepresentable committed caches as unavailable

- **Priority:** P0 (0.10.1 recovery)
- **Release target:** 1.1.0
- **Previous release target:** 0.10.1
- **GitHub issue:** [#320](https://github.com/NVIDIA-dev/literate-ai/issues/320)
- **Owner:** FileSystemSourceCache and declared source-cache targets
- **Direction:** Downstream v0.10.0 test/rebuild fails source-cache.path-unsafe on a format-only empty generated/committed-source-cache whose empty descendants Git cannot track.
- **Conclusion:** Treat the exact empty read-only representation as an unavailable cache without mutating it; fail closed on partial nonempty layouts; name the rejected path; keep writable standard-local caches unchanged.
- **Depends on:** none
- **Next action:** Complete. Reconciled with COMMITTED-CACHE-EMPTY-001's canonical
      implementation and exact 0.10.1 recovery evidence; do not reimplement the
      shipped fix or use this closure as a new 1.1 live acceptance claim.
- **Implementation:**
  - [x] Open read-only committed caches without requiring Git-unrepresentable empty descendant directories, and include the rejected path in path-unsafe diagnostics.
- **Evidence:**
  - [x] Format-only empty cache, partial-layout rejection, nonempty cache without empty intelligence dirs, and Standard declared-target composition tests pass.
        COMMITTED-CACHE-EMPTY-001 records the canonical fix, downstream reproduction,
        exact release-line and published-tag hosted runs. The current 44-test
        cache/update/rebind batch passes at `33630a4f`; issue #320 is already closed.

### [x] ORIGIN-SSH-HTTPS-001 — Treat equivalent GitHub SSH and HTTPS origins as the same update source

- **Priority:** P0 (0.10.1 recovery)
- **Release target:** 1.1.0
- **Previous release target:** 0.10.1
- **GitHub issue:** [#316](https://github.com/NVIDIA-dev/literate-ai/issues/316)
- **Owner:** update origin comparison and Standard lifecycle rebind
- **Direction:** A derived project initialized from GitHub HTTPS cannot litai update after rebind against the official v0.10.0 wheel whose embedded origin is the SSH spelling.
- **Conclusion:** Use one conservative repository-equivalence rule: GitHub SSH and HTTPS forms of the same owner/repo compare equal; different hosts, owners, repositories, and local/file origins remain distinct.
- **Depends on:** none
- **Next action:** Complete. Reconciled with UPDATE-ORIGIN-001 and the shipped
      0.10.1 recovery. Repository continuity uses conservative transport equivalence;
      rebind still requires exact acknowledged installed-distribution evidence.
- **Implementation:**
  - [x] Normalize equivalent GitHub SSH and HTTPS origins for update after reviewed
        Standard rebind, without accepting unrelated remotes or normalizing away
        the exact origin/distribution identities bound by the rebind plan.
- **Evidence:**
  - [x] HTTPS-initialized projects update against the SSH-spelled v0.10 wheel origin; distinct hosts or repositories still fail closed.
        UPDATE-ORIGIN-001 records the exact 73-test release-line batch and both
        successful 15-check hosted runs. The current 44-test cache/update/rebind
        batch passes at `33630a4f`; issue #316 is already closed.

### [x] STANDARD-CACHE-ENTRY-001 — Honor advertised Standard rebuild --source-cache-entry or stop advertising it

- **Priority:** P1 (1.0)
- **Release target:** 1.0.0
- **GitHub issue:** [#317](https://github.com/NVIDIA-dev/literate-ai/issues/317)
- **Owner:** Standard rebuild cache custody
- **Direction:** litai rebuild --help advertises --source-cache-entry, but Standard rebuild rejects it before execution so accepted dependency source cannot be reused across plan identities.
- **Conclusion:** Chose the "stop advertising it" branch rather than the
  graph-level accepted-cache selection contract: honoring the flag for Standard
  would require designing per-root/per-dependency/graph-map accepted-entry
  selection across the whole dependency graph, which is out of scope for a
  bounded 1.0 P1 patch. `litai rebuild --help`/`litai help profile` now scope
  `--source-cache-entry` and `--source-cache-root` to the external lifecycle
  driver, the Standard rejection error names `--from-accepted-source` as the
  supported deterministic-reuse equivalent, and
  `docs/user/configuration-and-cli.md` documents the contract. Ordinary
  Standard rebuild stays BUILD_DIR-backed; duplicate STANDARD-CACHE-OVERRIDE-001
  closed alongside this item.
- **Depends on:** none
- **Next action:** Complete.
- **Implementation:**
  - [x] Stop advertising the rejected Standard override and document the
    supported `--from-accepted-source` reuse contract instead of building a new
    graph-level accepted-cache selection contract.
- **Evidence:**
  - [x] Standard help no longer advertises an unsupported override without
    qualification; the rejection message and docs name the supported
    alternative. See `tests/e2e/test_cli_rebuild.py` and
    `tests/smoke/test_cli_help.py` additions covering this behavior.

### [x] LIFECYCLE-MUTATION-LOCK-001 — Serialize concurrent Standard lifecycle mutations in one project

- **Priority:** P1 (1.0)
- **Release target:** 1.0.0
- **GitHub issue:** [#318](https://github.com/NVIDIA-dev/literate-ai/issues/318)
- **Owner:** project-scoped lifecycle mutation and test checkpoint publication
- **Direction:** Two concurrent Standard rebuilds can both pass planning then race shared checkpoint state, so one fails with a predecessor-contract error after expensive generation.
- **Conclusion:** A portable project-scoped lifecycle lock must reject or queue the second mutation before either model stage; read-only commands stay available.
- **Depends on:** none
- **Next action:** Implemented; duplicate of PROJECT-LIFECYCLE-LOCK-001 (#318) above.
- **Implementation:**
  - [x] Add a project-scoped lifecycle mutation lock covering rebuild, --update-receipt, and shared checkpoint or cache-index publication.
- **Evidence:**
  - [x] A second concurrent rebuild fails closed with a typed diagnostic naming the active lifecycle; independent read-only commands still succeed. See PROJECT-LIFECYCLE-LOCK-001 evidence above.

### [x] CANONICAL-JSON-001 — Document canonical JSON numeric constraints for generated test manifests

- **Priority:** P1 (1.1 generation correctness)
- **Release target:** 1.1.0
- **GitHub issue:** [#361](https://github.com/NVIDIA-dev/literate-ai/issues/361)
- **Owner:** portable-application-implementation generation skill and initialized-project mirror
- **Direction:** Coding CLIs are required to emit source/tests/manifest.json as canonical JSON, but the generation skill omits canonical-JSON-v1’s prohibition on floating-point values, so plausible fractional fixtures fail only after generation.
- **Conclusion:** Teach the no-floating-point rule where the manifest is authored and require decimal strings or explicitly scaled integers for fractional domain values. Preserve the validator and wire contract; do not weaken canonical identity semantics.
- **Depends on:** none
- **Next action:** Complete: PR #375 landed as main `2f09c295`; #361 is closed
      with the exact-head CI and regression evidence linked.
- **Implementation:**
  - [x] Add the no-floating-point constraint and permitted representations beside the generated-test manifest contract.
  - [x] Keep the checked-in catalog skill and initialized-project template byte-identical.
  - [x] Add focused regression coverage that fails if either copy omits the rule or drifts.
- **Evidence:**
  - [x] Both `test_portable_application_skill` cases pass against the canonical
        `portable-application-implementation` skill and its exact template mirror.
        They require the nested no-float rule, decimal-string or specification-scaled
        integer representation, and preservation of fractional semantics.
  - [x] The full PR skill admission checks pass for all 19 impacted skills and six
        non-model checks each. `litai verify` passes authority, skips undeclared
        locks/provider-none intelligence, and reports the existing stale receipt.
  - [x] Fresh complete Python qualification of `66fd355e` passes: 3,811 run,
        3,781 passed, 30 skipped, zero failures. A later focused skill/rebind/refresh
        batch also passes all 27 tests; neither substitutes for hosted qualification.
  - [x] All 15 jobs in [CI 34594250773](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34594250773)
        passed on `66fd355e`; [PR #375](https://github.com/NVIDIA-dev/literate-ai/pull/375)
        landed as main `2f09c295` before tracker closure.

### [x] AUD-REL-001 — Repair documentation links and select the 1.1 release target

- **Release target:** 1.1.0
- **Priority:** P0
- **Owner:** project documentation and repository policy
- **Direction:** Repair current validation and release-state failures.
- **Conclusion:** Release target 1.1.0. Fix the stale PLUGIN-001 heading link, not an invented line-number pin; use release state set for 1.1.
- **Depends on:** none
- **Implementation:**
  - [x] Repair documentation anchors and refresh declared authority using supported helpers.
  - [x] Set pre-release target to 1.1; `release state` and release guidance report the explicit target.
- **Evidence:**
  - [x] `litai verify .` authority passes; release guidance selects pre-release 1.1. The separately stale test receipt is not hidden.
  - [x] Self-describing project regression passes; full release qualification remains SDLC-AUDIT-001.

### [x] AUD-UX-001 — Keep adoption next actions bound to the selected project

- **Release target:** 1.1.0
- **Priority:** P1
- **Owner:** operator onboarding CLI
- **Direction:** Make the first useful adoption steps reliable from any caller directory.
- **Conclusion:** Release target 1.1.0. Render argv with resolved paths and shell-safe display; retain plan/apply semantics.
- **Depends on:** AUD-REL-001
- **Implementation:**
  - [x] Bind every adopted-project command to the target root.
  - [x] Explain host readiness separately from authority verification.
- **Evidence:**
  - [x] Foreign-cwd and whitespace-path fixtures target only the adopted project (`tests.smoke.test_operator_adoption`).
  - [x] Create/adopt public CLI tests pass in the 165-test focused lifecycle batch.

### [x] AUD-MCP-001 — Constrain and describe MCP mutations

- **Release target:** 1.1.0
- **Priority:** P1
- **Owner:** MCP facade
- **Direction:** Make tool risks visible and prevent accidental cross-project dispatch.
- **Conclusion:** Release target 1.1.0. Add risk annotations, root confinement and mutation acknowledgement; document same-user shell bypass.
- **Depends on:** AUD-UX-001
- **Next action:** Focused boundary repair complete. Broad release qualification is
      tracked by SDLC-AUDIT-001; host-code and same-user-shell limits remain explicit.
- **Implementation:**
  - [x] Add standard annotations and explicit mutation acknowledgements; focused MCP tests pass.
  - [x] Resolve tool paths against a configured session root and reject escapes, including ancestor-project discovery.
  - [x] Repair verify argv and failure status propagation; reject option injection through tool data.
- **Evidence:**
  - [x] Foreign-root symlinks, traversal, ancestor discovery and option injection fail before dispatch (`tests.smoke.test_mcp_server`).
  - [x] Read-only calls work; unacknowledged mutations fail (9 focused MCP tests on macOS).

### [x] AUD-SKILL-001 — Plan and verify skill dependency and template updates

- **Release target:** 1.1.0
- **Priority:** P1
- **Owner:** skill authoring helpers
- **Direction:** Reduce manual fan-out for normative skill edits.
- **Conclusion:** Release target 1.1.0. Extend existing deterministic normalization tooling with targeted plan/check/apply and declared mirror handling; preserve semantic version judgment.
- **Depends on:** AUD-REL-001
- **Implementation:**
  - [x] Add non-writing check/plan with changed paths and identities (`scripts/normalize_skill_authoring.py`).
  - [x] Synchronize only explicitly declared mirrors and propagate dependency pins.
  - [x] Reject stale plans, including changed non-output inputs, and retain preexisting divergent templates.
- **Evidence:**
  - [x] Parent-change fixture identifies dependent drift (four `tests.unit.test_skill_update_plan` tests pass).
  - [x] Plan never writes; apply is revalidated and idempotent. Repository `--check` reports no drift.

### [x] AUD-CI-001 — Pin third-party Actions to reviewed commits

- **Release target:** 1.1.0
- **Priority:** P1
- **Owner:** CI supply chain
- **Direction:** Prevent upstream action tag movement changing release gates silently.
- **Conclusion:** Release target 1.1.0. Resolve current tags to immutable commits and retain readable version comments.
- **Depends on:** AUD-REL-001
- **Implementation:**
  - [x] Pin third-party actions to resolved full commit IDs and configure weekly Dependabot PRs.
- **Evidence:**
  - [x] Workflow/Dependabot YAML parse and three `tests.critical.test_ci_action_pins` tests pass. Hosted execution remains part of final CI.
  - [x] Repair the historical-checkout regression exposed by the broad run: enforce
        `fetch-depth: 0` per checkout step without depending on tag spelling.
        The regression and three pin-policy tests pass; full rerun remains pending.

### [x] AUD-INTEL-001 — Qualify software intelligence at the project boundary

- **Release target:** 1.1.0
- **Priority:** P1
- **Owner:** source intelligence and source-to-specification contracts
- **Direction:** Make software-intelligence usefulness and limits explicit.
- **Conclusion:** Release target 1.1.0. Evaluate stale-index rejection, provenance, inverse qualification and actionable diagnostics without making graph presence a correctness claim.
- **Depends on:** AUD-REL-001
- **Implementation:**
  - [x] Map intelligence capabilities to implemented helpers and reproducible tests in the graded delivery report.
  - [x] Confirm existing provider-none/off, stale and preferred-unavailable diagnostics through their public helper tests.
  - [x] Record held-out task classes for impact analysis and inverse qualification; actual comparative experiments remain unrun.
- **Evidence:**
  - [x] Positive, stale-index and inverse-custody rejection tests pass in the 165-test focused batch, including the real CodeGraph sync/check fixture.
  - [x] Report claims distinguish structural retrieval, semantic comparison and independent acceptance.

### [x] AUD-RESEARCH-001 — Define reproducible experiments for the concept

- **Release target:** 1.1.0
- **Priority:** P1
- **Owner:** research evaluation and project documentation
- **Direction:** Grade research potential and turn open claims into falsifiable experiments.
- **Conclusion:** Release target 1.1.0. Separate potential from demonstrated efficacy; define baselines, ablations, held-out tasks and cost metrics before claiming superiority.
- **Depends on:** AUD-INTEL-001
- **Implementation:**
  - [x] Document hypotheses and baseline/ablation matrix in the graded 1.1 report.
  - [x] Add a deterministic evaluation summary for recorded trial evidence (`scripts/summarize_research_trials.py`).
  - [x] Reject missing, duplicate or incomparable trial records.
- **Evidence:**
  - [x] Fixture summaries report pass rate, task-level uncertainty and cost (two `tests.unit.test_research_trials` tests pass).
  - [x] Unrun experiments remain explicitly unmeasured and do not support release claims.

### [x] ADOPT-REFRESH-001 — Refresh retained scope after upstream files change

- **Release target:** 1.1.0
- **GitHub issue:** [#368](https://github.com/NVIDIA-dev/literate-ai/issues/368)
- **Priority:** P1
- **Owner:** adopted source custody
- **Direction:** Track open issue #368.
- **Conclusion:** Release target 1.1.0. Inspect upstream scope refresh requirements and preserve exact source authority.
- **Depends on:** ADOPT-PROMOTION-001
- **Next action:** Complete: PR #375 landed as main `2f09c295` after full local
      and all 15 exact-head hosted checks; #368 is closed with linked evidence.
      The implemented `project retained-scope refresh` plan/apply binds exact metadata
      and source bytes, reuses scope capture, rebinds the retained receipt policy,
      and preserves baseline/parity/lift-shift and previous receipts as history.
- **Implementation:**
  - [x] Plan scope refresh and invalidate stale dependent receipts.
  - [x] Require acknowledgement and exact plan identity; serialize apply and reject
        stale plans, unsafe paths, and specification-authoritative projects.
  - [x] Preserve admitted commands; retain the reviewed old/new inventory as history
        and roll back ordinary partial-write failures without changing source.
  - [x] Retained execution and receipt publication use the same lifecycle lock;
        refresh omits generic project-local CLI telemetry so planning stays read-only.
- **Evidence:**
  - [x] New upstream file fixture refreshes scope without losing user changes.
  - [x] Real retained execution includes the added file; old receipt fails and a
        newly earned receipt passes. Baseline/parity bytes remain unchanged.
  - [x] Eleven refresh tests pass, including tracked additions, ignored outputs,
        deleted paths, stale plans, contention, no-op, unsafe paths, specification
        authority refusal, rollback after policy/review faults, and partial-write recovery.
        The 59-test retained-harness/adoption/performance regression batch also passes
        (61 distinct tests including the final two refresh regressions).
  - [x] Fresh full Python qualification passes (3,811 run, 3,781 passed, 30 skipped,
        no failures), along with all 15 jobs in
        [CI 34594250773](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34594250773).
        Authority verification, formatting and lint pass; the stale repository
        test receipt remains explicit and is not rewritten by this repair.

### [x] DRAFT-PROMOTION-001 — Allow reviewed static promotion from retained to drafted

- **Priority:** P0 (1.1.0 adoption continuity)
- **Release target:** 1.1.0
- **GitHub issue:** [#367](https://github.com/NVIDIA-dev/literate-ai/issues/367)
- **Owner:** source-to-specification review, project promotion, and conversion-stage authority
- **Direction:** A retained adopted project must be able to reach drafted through supported commands even when model-backed source intelligence is disabled.
- **Conclusion:** Add an explicit reviewer-authored Component graph input to static
      review. Bind its canonical identity into the signed review, require exact
      source-snapshot and evidence closure, and let acceptance materialize Component
      projections only from that validated reviewed graph. Support explicit,
      collision-checked integration into an existing retained adopted project so the
      project that owns conversion authority receives the projection. Keep semantic
      model translation and inverse custody requirements unchanged for model-derived
      graphs; do not infer executable semantics or cross-Component boundaries from
      inert inventory.
- **Depends on:** BROWNFIELD-STATE-001 and the existing signed review/promotion contracts
- **Next action:** Done. Full local gates and the 15-job Linux, macOS, and Windows
      matrix passed in GitHub Actions run 34529236052.
- **Implementation:**
  - [x] Define and schema-validate the reviewed static Component graph attachment
  - [x] Extend `spec review` and `spec accept` to bind and reopen it
  - [x] Permit source-free project promotion from `deterministic-static` only when the
        signed graph is complete
  - [x] Add an explicit fail-closed integration path for a retained adopted project;
        ordinary `--project-target` creation and overlap rejection remain unchanged
  - [x] Advance an adopted retained fixture to drafted through public CLI commands
  - [x] Update architecture, user guidance, traceability, and changelog
- **Evidence:**
  - [x] Public CLI tests reject missing, unsigned, stale, source-mismatched,
        incomplete, unknown-kind, and evidence-unclosed graphs
  - [x] A static retained fixture promotes, writes current
        `FileAuthorityProjectionStore` entries, and advances to drafted
  - [x] Focused tests, full Python checks (3,630 passed), documentation/schema checks,
        wheel checks, and the 15-job cross-platform GitHub Actions run 34529236052 pass

### [x] PROMOTE-KIND-001 — Preserve reviewed Component kind during source promotion

- **Release target:** 1.1.0
- **GitHub issue:** [#371](https://github.com/NVIDIA-dev/literate-ai/issues/371)
- **Integration boundary:** Upstream local proof below is retained as historical
      evidence; current consolidated qualification is LIBRARY-ARTIFACT-001's open gate.
- **Priority:** P0
- **Owner:** coding-agent
- **Direction:** Project the reviewed graph node kind into promoted component authoring so immutable authority preserves library lifecycle semantics.
- **Conclusion:** A source-derived library must plan with an import surface and no product entrypoint.
- **Depends on:** GitHub issue #371
- **Implementation:**
  - [x] Set ComponentAuthoring.kind during promotion and add a regression that promotes a reviewed library node and verifies its component kind.
- **Evidence:**
  - [x] Targeted unit test plus `make python-check` (3,651 passed, 33 skipped).

<a id="ux-270"></a>

### [x] DOC-DEPENDENCIES-001 — Remediate audited documentation-tool dependencies

- **Release target:** 1.1.0
- **Priority:** P1
- **Owner:** OpenSpec and Mermaid documentation tooling
- **Direction:** Resolve dependency findings exposed by fresh 1.1 documentation qualification.
- **Conclusion:** A fresh npm ci and npm audit report five high-severity affected packages in the extract-zip/Puppeteer dependency chain and js-yaml. This is tooling dependency evidence, not proof of runtime exposure. Review compatible dependency updates and verify rendering; do not apply an unreviewed major-version force fix.
      Audit references: `GHSA-jmr9-qjv8-65gv`, `GHSA-7pqw-9j4j-h8q3` and
      `GHSA-2883-xcg3-v3hh`. Successful documentation rendering alone is not a
      dependency-security disposition.
- **Implementation result:** Upgraded the pinned documentation browser to
      Puppeteer 25.10.0, whose browser installer no longer depends on extract-zip,
      and remove its obsolete YAML/configuration dependency chain. The resulting
      lock contains neither extract-zip nor js-yaml. The existing Mermaid CLI
      11.16.0 already declares Puppeteer 25 compatibility, so preserve that pin.
      Raise only the contributor documentation-tool Node floor to 22.12; CI already
      selects Node 24, and generated-application runtime requirements remain unchanged.
      Make documentation validation run `npm audit --audit-level=high` over all
      staged development dependencies before rendering, so future high/critical
      findings or unavailable audit evidence cannot be mistaken for a passing gate.
      The fresh installed graph and complete rendering have been verified locally.
- **Next action:** Complete. The update is an ancestor of merged `ad92a655`,
      and the documentation tool tree is unchanged from qualified `0ae183d8`.
      Fresh release-wide qualification remains with RELEASE-INTEGRATION-001.
- **Depends on:** none
- **Implementation:**
  - [x] Review advisory reachability and select compatible fixed documentation-tool versions.
  - [x] Update package constraints and lockfile with reviewed dependency identities.
- **Evidence:**
  - [x] Fresh npm audit reports zero vulnerabilities; installed `npm ls` confirms
        Puppeteer 25.10.0 and browsers 3.2.2 without extract-zip or js-yaml.
        A deliberately unavailable audit endpoint exits nonzero before parser or
        renderer execution; no audit bypass or browser sandbox relaxation was added.
  - [x] Fresh tooling installation passes OpenSpec (2 items), Mermaid parser tests
        (9), and full rendering (121 diagrams across 530 Markdown files).
        Node 22.12 separately passes the same full rendering set. The final
        documentation/OpenSpec/lint/format/layout/driver-review chain passes on
        Node 26.8.2; 30 focused tooling/documentation Python tests also pass.
        One intervening full render failed with a browser protocol timeout at
        `docs/history/roadmap/release-branching-model.md:67`. Its cause remains
        unproven: three isolated attempts using the supported Chrome fallback
        passed in 274/155/156 ms, followed by the complete unchanged gate passing.
        Retain this intermittent failure for hosted qualification; do not hide it
        with a timeout increase or a passing minimum-Node run.
  - [x] Exact committed update `0ae183d81b71d80ce8cff8a1d5a98deedbdbd9c9`
        passes a fresh `make python-check`: 3,827 tests run, 3,794 passed,
        33 skipped, no failures, 2,135.721 seconds. The checkpoint was absent
        before the run and removed on successful completion; no resumed repair
        is presented as fresh qualification. The three optional pytest-profiler
        skips remain distinct from the separately exercised predecessor's tests.
  - [x] The same exact revision passes wheel smoke outside the checkout and retains
        the tested 2,437,352-byte wheel, SHA-256
        `a0097059d4fce4ce328f140b36a027e71c7bda01a504a8ffc646d5108549344c`,
        in qualified-files manifest
        `sha256:33b6c93d9c4d4941a469efdf752ded31acb089a42e0b21a0695768ba104e75a5`.
        Its installed initialization origin reports `0ae183d8`; this is not
        qualification of the later roadmap/ADR drafts or a published release.
  - [x] Exact `0ae183d8` also passes isolated `install-check` and a forced offline
        installed-CLI/command-worker end-to-end run (765 CLI files, identity
        `sha256:6302fad79325b42e18ed165f76bdab4f8b8ff2597085559b0dd675507d3f9408`).
        The publication fixture identity is
        `sha256:648fdb68634ea6de2a421707566e4b8c529a0e7db4b282cc544a198bb899bfd1`.
        This exercises installed packaging and deterministic command workers,
        not live model generation or release publication.
  - [x] Full integration qualification and hosted CI pass. [PR #388](https://github.com/NVIDIA-dev/literate-ai/pull/388)
        retains the local full Python result (4,206 tests, 30 skips, no failures),
        wheel, installed E2E and fast gates at `692041a1`; the retained Python
        ledger and output digests have been rechecked. That commit's tree is
        identical to merged `ad92a655`, whose complete 15-job
        [hosted matrix](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34671435026)
        passes, including native documentation rendering on all three OSes.
        The previously reported browser timeout remains historical evidence;
        no timeout increase or exclusion was needed for those passes. A current
        documentation check also reports zero npm vulnerabilities and passes
        all nine fence cases and rendering. The exact tooling files remain
        byte-identical to `0ae183d8`, including the audited dependency lock.

### [x] WORKER-009 — Preserve lifecycle parallelism through remote dispatch

- **GitHub issue:** [#401](https://github.com/NVIDIA-dev/literate-ai/issues/401)
- **Priority:** P1
- **Owner:** Framework execution dispatch contracts and worker lifecycle
- **Direction:** Issue #401: build --jobs N --worker must preserve the requested bounded parallelism.
- **Conclusion:** Bind jobs to the exact dispatch request and worker rebuild invocation. Scheduling is execution policy, like timeout and verbosity, so retain the shared artifact-input authority identity and default wire representation for replay compatibility. Existing scheduler dependency and failure rules remain authoritative.
- **Depends on:** none
- **Implementation:**
  - [x] Add optional jobs in the range 1 through 256, reject booleans, preserve default-one wire identity, and forward through dispatch and worker rebuild.
  - [x] Verify remote concurrency, dependency ordering, failure propagation, and retained artifact replay.
- **Evidence:**
  - [x] 54 focused tests passed: contract/schema round trips and invalid values,
    CLI and worker forwarding, a barrier proving independent diamond nodes overlap
    through the remote executor, provider-before-consumer ordering, failed-node
    cancellation, and default-`run` replay of the parallel build's retained artifact.
  - [x] At `ff2a493a`, the fresh full Python gate passed 4,818 tests (30 skips),
    and installed-wheel qualification passed with wheel
    `sha256:57e1d1cbc74668f9bd0297107591548a46aba31f60e5cc76254138fc9cf424d2`.
    Retained outer-runner output bytes and hashes were verified. All 15
    [hosted CI jobs](https://github.com/NVIDIA-dev/literate-ai/actions/runs/34833596909),
    including documentation, passed. [PR #402](https://github.com/NVIDIA-dev/literate-ai/pull/402)
    landed at `806e9bc9` with a tree identical to the qualified head;
    [#401 closed with evidence](https://github.com/NVIDIA-dev/literate-ai/issues/401#issuecomment-5664093691).
    One missing nested diagnostic log was recorded separately and was not used
    as completion evidence.

### [x] WORKER-DAG-001 — Route one Component lifecycle DAG across exact workers

- **Release target:** 1.1.0

- **GitHub issue:** [#403](https://github.com/NVIDIA-dev/literate-ai/issues/403)

- **Priority:** P1
- **Owner:** Component worker routing, artifact custody and Standard lifecycle dispatch
- **Direction:** Preserve one canonical Component DAG while independent nodes execute on selected workers and consumers receive accepted predecessor products.
- **Conclusion:** The Standard scheduler already supplies exact provider and packaging exports. Introduce routing and verified handoff at that boundary, preserve bounded generation context and final project acceptance, then connect command/SSH transports. Parallel whole-root rebuilds do not implement node routing.
- **Depends on:** none
- **Implementation:**
  - [x] Define exact node assignments, routing identities and artifact handoff/import contracts.
  - [x] Integrate worker dispatch at the existing Standard complete-node boundary with exact result correlation.
  - [x] Wire command and SSH node execution with source/evidence custody and target/ABI validation.
  - [x] Preserve cancellation, failed-predecessor blocking and exact-current recovery across workers.
- **Evidence:**
  - [x] Independent diamond branches overlap through command and SSH handlers; the
        consumer import receipt contains both exact predecessor exports, and custody
        tests verify the corresponding source and destination bytes.
  - [x] Changed routes, wrong-worker results, corrupt artifacts and stale recovery
        fail before downstream actuation.
  - [x] Existing local lifecycle behavior and final project acceptance remain unchanged.
- **Foundation evidence:** `make component-worker-check` passes 102 tests, including
  20 routing/custody tests and planning, lifecycle, CAS and schema regressions. Worker-local
  CAS transfer verifies actual bytes, rejects source/destination corruption and
  changes during copying, and excludes generation-only/transitive implementations.
  New wire contracts are included in the current schema catalog.
- **Completion evidence:** The Standard service preserves one dependency-layer scheduler
  while exact local, command and SSH handlers own node actuation. Focused routing,
  custody and lifecycle coverage passes 109 tests, including two-transport diamond
  overlap, exact consumer import membership, wrong-worker correlation failure,
  pre-dispatch cancellation and exact-current recovery. Full and hosted qualification
  remain release gates rather than behavior exceptions.

<a id="worker-health-001-detect-worker-resource-pressure-and-investigate-bounded-cleanup-candidates"></a>

### [x] RETAINED-ADMISSION-001 — Qualify explicitly retained source under an existing Component

- **Release target:** 1.1.0
- **GitHub issue:** [#463](https://github.com/NVIDIA-dev/literate-ai/issues/463)
- **Priority:** P1
- **Owner:** Standard lifecycle source admission
- **Direction:** Provide an explicitly authorized retained-source path without
  replacing existing Component specifications.
- **Conclusion:** Bind exact-content retained provenance to existing classification,
  dependency, build, and independent acceptance gates. Keep the source distinct from
  model-generated provenance and in a separate cache namespace.
- **Depends on:** none
- **Implementation:**
  - [x] Bind explicit retained-source input to the current lock and exact tree
        identity, with focused authorization and drift tests.
  - [x] Preserve distinct provenance and prevent regenerative cache promotion, with
        cache and checkpoint regressions.
- **Evidence:**
  - [x] The preparation branch passed 62 focused source/wire/cache/rebuild tests plus
        four CLI/acceptance tests and repository lint/format checks.
  - [x] The exact integrated implementation passes 152 retained-source,
        source-generation, cache/checkpoint, Standard lifecycle, CLI, and peer-work
        tests; focused lint and formatting, project validation, version authority,
        and the live full-stack and regenerative samples pass.
  - [x] A clean candidate wheel initialized a fresh exact-parent project, generated
        and admitted a 12-test hello Component, then planned exact retained bytes as
        `sha256:2bae5b97e15206890f454fef6e5d1f0343ac7b8fce7910dc1953ef3ad589e54a`.
        The authorized replay ran without a coding model, reported source provenance
        `retained`, reused the exact build, and passed all 12 generated and independent
        acceptance tests.

### [x] RETAINED-GITLINK-SCOPE-001 — Preserve initialized submodules in retained archives

- **Release target:** 1.1.0
- **GitHub issue:** [#469](https://github.com/NVIDIA-dev/literate-ai/issues/469)
- **Priority:** P0
- **Owner:** retained harness source custody
- **Direction:** Include initialized Git-submodule source in the Git-visible retained
  scope without flattening repository administration or inventing content for an
  uninitialized gitlink.
- **Conclusion:** Recursively capture each initialized child repository's tracked and
  nonignored untracked files, carry child ignored-root accounting into the parent scope,
  and bind every included byte into the existing tree and archive identities.
- **Implementation:**
  - [x] Discover gitlinks from the superproject index and recurse only when the child
        worktree resolves to its own repository root.
  - [x] Prefix child paths and excluded roots while omitting `.git` administration and
        uninitialized gitlinks.
- **Evidence:**
  - [x] Real Git fixtures prove initialized tracked and visible-untracked files are
        copied, ignored child outputs are accounted for, and deinitialized children
        remain omitted.
  - [x] A retained remote archive regression proves the nested source file is present
        and no `.git` member is transported.

### [x] PEER-WORK-UNDERSCORE-001 — Accept Git-valid underscore branch lifecycle markers

- **Release target:** 1.1.0
- **GitHub issue:** [#465](https://github.com/NVIDIA-dev/literate-ai/issues/465)
- **Priority:** P1
- **Owner:** peer-work lifecycle marker validation
- **Direction:** Permit an underscore-prefixed Git branch to receive an exact-head
  terminal marker without weakening unsafe-ref or deletion checks.
- **Implementation:**
  - [x] Accept `_archive` and retain traversal, invalid-component, and leading-option
        refusal.
- **Evidence:**
  - [x] A real temporary-Git fixture creates and reads back the marker for `_archive`.

### [x] WORKTREE-001 — Keep worktrees inside the owning repository and collect sibling copies

- **Priority:** P1
- **Owner:** existing survey-peer-work skill and repository hygiene (PROJECT.md goal 1)
- **Direction:** Inspect sibling Literate AI directories, preserve unique work, and remove verified redundant copies; future worktrees belong inside the repository.
- **Conclusion:** Verify clean state, current commit ancestry and ignored payloads before removing sibling checkouts. Retain unique commits and non-reproducible evidence inside the owning repository.
- **Depends on:** none
- **Implementation:**
  - [x] Document the in-repository worktree rule and ignore its directory.
  - [x] Audit and remove sibling Literate AI checkouts after preserving any unique state.
- **Evidence:**
  - [x] Confirm all removed checkout commits remain reachable and no sibling Literate AI directories remain.
  - [x] Run skill validation and review the final diff.

- **Verified outcome:** Seven sibling linked worktrees and one separate release
  clone were clean; all eight checkout tips are ancestors of `a3a1a00f6cb8`.
  Removed the redundant checkouts after preserving ignored build evidence and
  the separate clone's complete Git directory locally inside the owning repository.
  Imported every clone ref into `refs/archive/peer-cleanup-20260920/` and verified
  each object identity. Existing branch refs remain intact. A fresh sibling scan
  found no remaining Literate AI checkout; ancestry checks passed after removal.
  Updated the existing survey skill rather than creating a duplicate. Both
  `make skills-check` and `git diff --check` passed.
- **Survey scope:** Start/end peer surveys succeeded. The GC plan had no eligible
  branch candidates (dirty main checkout, young/stale markers, or unmerged heads),
  so no branches were collected. Explicit operator direction authorized removal
  of the verified redundant sibling directories. Temporary worktrees and the
  checkout embedded in another project were outside this sibling cleanup.

WORKTREE-001 GitHub transfer follow-up: publishing the existing commit to the
canonical GitHub release branch exposed an init-template parity failure. Sync the
packaged survey skill with its authored source so installed projects receive the
same worktree placement and preservation rules. Validate the existing parity
regression and skill gate before reinstalling the GitHub-origin distribution.

WORKTREE-001 template repair evidence: focused `make python-check` with
`PYTHON_TEST_PATTERN=test_agent_skill_catalog_template.py` passes the existing
source/template parity test; `make skills-check` passes. GitHub CI is the remaining
confirmation for the published repair.

WORKTREE-001 lifecycle follow-through: the packaged skill is the only file changed
under the lifecycle driver's declared implementation paths. Reviewed that exact
copy-only change and refreshed its identity with `review_lifecycle_driver.py
--record`, then refreshed documentation review. The existing version-authority
regression passes through focused `make python-check`; this addresses the next
GitHub CI failure without relaxing identity checks.

### [x] CI-HELP-COLOR-001 — Make direct CLI help assertions color-independent

- **Priority:** P0 (1.1.0 release blocker)
- **Owner:** direct CLI help tests and their explicit plain-text environment
- **Direction:** The 1.1.0 release check failed because inherited `FORCE_COLOR`
      made Python 3.14 argparse emit ANSI-colored help into `StringIO`, while
      direct tests asserted uncolored literal text. After the initial CI-plan
      repair, a later check retained the same failure in parent checkout.
- **Conclusion:** Run direct literal help assertions under the same plain-text
      environment already used by the canonical CLI help tests. Do not disable
      CLI color globally or weaken the command-name assertion.
- **Depends on:** none
- **Implementation:**
  - [x] Define the bounded plain-text test environment by removing inherited
        color-forcing variables and setting `NO_COLOR=1` and `TERM=dumb`.
  - [x] Patch the environment only around the CI-plan, parent-checkout, and
        tracker-inspect help invocations.
- **Evidence:**
  - [x] The exact release gate failed the focused assertion under inherited
        `FORCE_COLOR`; the repaired nine-test CI-plan module passes with
        `FORCE_COLOR=1`.
  - [x] The canonical ten-test CLI-help module passes with `FORCE_COLOR=1`;
        lint and formatting pass across all 1,250 checked files.
  - [x] Release evidence `20260924T160451Z-8fddf5` retained the independent
        parent-checkout failure after 2,924 tests; the tracker assertion
        reproduces under the same inherited-color environment.
  - [x] PR #493 exact-head CI run `36029724360` passed all 19 hosted jobs;
        all 28 affected modules pass under `FORCE_COLOR=1` before backport.

### [x] WHEEL-ORIGIN-001 — Compare exact build origins canonically

- **Priority:** P0 (1.1.0 release blocker)
- **Source pull request:** [#494](https://github.com/NVIDIA-dev/literate-ai/pull/494)
  (isolated wheel-smoke repair extracted before the broader integration merged)
- **Owner:** installed-wheel origin qualification
- **Direction:** The build backend records canonical GitHub repository origins,
  while wheel smoke compared that value to the ambient raw remote URL.
- **Conclusion:** Canonicalize the observed origin with the same repository URL
  authority before exact comparison. Preserve revision equality and fail closed
  for genuinely different repositories.
- **Depends on:** none
- **Implementation:**
  - [x] Reuse `canonical_repository_origin` in the installed-wheel smoke gate.
- **Evidence:**
  - [x] Release evidence `20260926T052816Z-f2d2a4` retained the exact-origin
        failure after all 5,778 wheel-smoke tests passed.
  - [x] Extracted source commit `6326b4df` changes only the gate comparison.
  - [x] Clean exact repair head `9953e5b7` passes the complete `wheel-check`.
  - [x] PR #499 exact-head CI run `36228926976` passed all 19 hosted jobs.

### [x] CPP-BAZEL-MACOS-001 — Bind the fixture stager to its filesystem deployment floor

- **Priority:** P0 (1.1.0 release blocker)
- **Owner:** C++ Bazel product acceptance fixture
- **Direction:** Xcode 27 rejects the fixture's C++17 filesystem stager when
  Bazel targets a macOS version earlier than the API's 10.15 availability.
- **Conclusion:** Select a 10.15 compile and link floor only for the Darwin
  execution platform; preserve all Linux and Windows fixture flags.
- **Depends on:** none
- **Implementation:**
  - [x] Add Darwin-only compile and link options to the generated stager target.
  - [x] Add a structural regression for the generated Bazel rule.
- **Evidence:**
  - [x] Release evidence run `20260923T140622Z-e96cdf` retains the Xcode 27
        failure from the complete filesystem runtime test.
  - [x] The structural regression and the previously failing static/shared
        runtime test pass together on macOS 27 with Xcode 27.
  - [x] PR #490 qualified the unchanged repair head in all 19 hosted CI jobs;
        backport the reviewed commit with source provenance, then retain current
        `main` ancestry on the release line.

### [x] CPP-BAZEL-SDK-001 — Bind the selected macOS SDK through Bazel execution

- **Priority:** P0 (1.1.0 release blocker)
- **Source pull request:** [#485](https://github.com/NVIDIA-dev/literate-ai/pull/485)
  (self-contained SDK repair extracted; broader native gRPC work remains deferred)
- **Owner:** C++ toolchain identity and Bazel lifecycle execution
- **Direction:** Xcode 27 makes `SDKSettings.json` a compiler dependency, while
  an unbound Bazel repository probe does not admit the selected Xcode SDK root.
- **Conclusion:** Resolve implicit Apple developer-directory and SDK selections
  once, bind them and bounded SDK metadata into C++ toolchain identity, and pass
  the exact selection to Bazel repository, action, host-action, and independent
  consumer invocations.
- **Depends on:** none
- **Implementation:**
  - [x] Discover implicit `DEVELOPER_DIR` and `SDKROOT` with bounded Apple tools.
  - [x] Reject SDK path or metadata drift before and after lifecycle execution.
  - [x] Declare the selected SDK root to rules_cc repository probes and actions.
- **Evidence:**
  - [x] Local full validation retained the reproducible Xcode 27 failure at the
        undeclared absolute `MacOSX.sdk/SDKSettings.json` input.
  - [x] The exact complete filesystem runtime passes static and shared product
        builds, independent acceptance, and fresh Conan/Bazel consumers in
        113.847 seconds after the repair.

### [x] REFRESH-WINDOWS-NODE-001 — Canonicalize unsigned filesystem identifiers

- **Priority:** P0 (1.1.0 release blocker)
- **GitHub pull request:** [#491](https://github.com/NVIDIA-dev/literate-ai/pull/491)
- **Owner:** repository refresh custody identity
- **Direction:** The Windows 2025/VS2026 hosted image can expose filesystem
  identifiers above the canonical JSON signed 64-bit ceiling.
- **Conclusion:** Preserve the canonical JSON contract and encode only
  out-of-range local OS integers as tagged decimal strings before hashing
  custody, metadata transition, and metadata-directory plans.
- **Depends on:** none
- **Implementation:**
  - [x] Add bounded integer normalization to every refresh identity wire.
  - [x] Prove adjacent oversized node identifiers retain distinct identities.
- **Evidence:**
  - [x] Exact release-head CI run `35908379795` retained 33 failures sharing
        `$.children[0].boundary[0]: integer is outside canonical signed 64-bit range`.
  - [x] PR #491 wheel smoke retained the independent metadata transition failure
        at `$.metadata[0].before_signature[0]`.
  - [x] The next Windows wheel smoke retained the metadata-directory failure at
        `$.metadata_directories[0].node[0]`.
  - [x] PR #491 exact-head rerun `35937064698` passed all 19 hosted CI jobs;
        121 combined refresh, C++ Bazel, and guarded-builder backport tests pass.
  - [x] Backport all five reviewed commits with source provenance and retain
        current `main` ancestry without replacing release-specific identities.

### [x] PACKAGE-APT-001 — Construct and independently verify real Debian packages

- **Design review:** [ADR 0045](../../decisions/0045-debian-package-worker-custody.md), Accepted 2026-09-25.
- **Priority:** P1 (deferred to 1.2)
- **GitHub issue:** [#487](https://github.com/NVIDIA-dev/literate-ai/issues/487)
- **Owner:** package-apt Flavor and native Debian package adapter
- **Direction:** Make package-apt produce a standards-compliant deterministic .deb rather than a metadata ZIP containing DEBIAN/control.
- **Conclusion:** Use bound native Debian tooling to construct the exact accepted PackagePlan under OBJ_DIR and independently inspect metadata and the complete payload without installing or publishing it.
- **Depends on:** none
- **Implementation:**
  - [x] Obtain explicit maintainer acceptance of ADR 0045 before implementing its Debian projection, bound native tooling, or worker custody design.
  - [x] Project deterministic Debian paths, modes, control metadata, architecture, entrypoints, specifications, SBOMs, and runtime dependencies from the accepted closure.
  - [x] Construct a reproducible .deb with bound tooling and verify its metadata, file table, modes, and digest independently.
- **Evidence:**
  - [x] Tests prove reproducible bytes, executable modes, exact metadata and payload, tamper rejection, and fail-closed behavior when required tools are unavailable.
- **Progress (2026-09-25):** The first local adapter slice projects exact `amd64` or
  `arm64` paths and modes, refuses guessed runtime dependencies in favor of explicit
  resolved-CycloneDX Debian coordinates, binds and rechecks `dpkg-deb`, constructs with
  fixed gzip, ownership, locale and epoch policy, and independently parses the returned
  ar/control/data archives. Focused tests prove byte reproducibility, executable and
  documentation placement, tamper/script/traversal refusal, architecture contradiction,
  and non-Linux local refusal. The public package build/verify path now selects the real
  Debian adapter, retains its exact projection in package evidence, and refuses to
  misrepresent lifecycle-only remote dispatch as remote artifact construction. Real
  Linux tool evidence is retained by the hosted matrix. Serializable package dispatch
  and non-Linux-controller qualification are explicitly deferred to 1.3 as issue #497;
  that follow-on does not weaken the completed local package-apt contract. Windows
  hosted qualification also proved the public projection normalizes its uppercase
  `AMD64` machine spelling before applying the Debian `amd64` contract.

### [x] REPO-MAN-PROFILE-001 — Recognize retained repo_man Standard command profiles

- **Release target:** 1.2.0
- **Priority:** P1
- **Owner:** Standard command-profile contract, schema catalog, and retained-harness projection
- **Direction:** Make the already-shipped build-repo-man Flavor parse and project as retained harness authority without treating repository-relative repo.sh as a discoverable host tool.
- **Conclusion:** Add a typed repo_man profile to the public command-profile union and schema catalog; retain its entrypoint and build-target identity while the disposable generated wrapper continues through the selected language toolchain.
- **Depends on:** none
- **Implementation:**
  - [x] Parse and validate the typed repo_man profile and admit it on the build-system Flavor axis.
  - [x] Project disposable generated source with the native language driver while preserving retained repo_man authority and excluding repo.sh from host tool discovery.
- **Evidence:**
  - [x] `test_standard_command_projection.py` passes 32 focused contract and
        projection tests, including exact Python-driver discovery and malformed
        target/tool/entrypoint rejection; `test_schema_catalog.py` passes 20
        independent catalog tests. Strict lint and format checks pass.

### [x] SOURCE-GENERATION-PROGRESS-002 — Make source-generation stderr allowance safely configurable

- **Priority:** P0
- **GitHub issue:** [#495](https://github.com/NVIDIA-dev/literate-ai/issues/495)
- **Owner:** framework core coding-CLI transport and Standard local generation adapter
- **Direction:** Allow larger Components to complete when a supported coding agent emits more than the fixed 16 MiB source-generation progress allowance.
- **Conclusion:** Progress stderr and admitted generated-source bytes are separate bounded resources. Preserve the 16 MiB default and all tighter task/stdout limits, add a narrowly scoped local override with a 256 MiB safety ceiling, and use a 64 MiB allowance for the observed regeneration.
- **Depends on:** SOURCE-GENERATION-PROGRESS-001
- **Implementation:**
  - [x] Add validated source-generation stderr configuration and pass it through Standard local generation only
  - [x] Keep source-tree, stdout, JSON-task, timeout, concurrent drain, overflow, and process-tree semantics unchanged
- **Evidence:**
  - [x] The 134-test coding-CLI unit slice passes with two expected skips, proving the default, 64 MiB override, invalid and excessive rejection, configured old-limit crossing, overflow failure, and unchanged timeout behavior.
  - [x] The same exact large-Component Codex authority that previously failed at the 16 MiB boundary completed under a 64 MiB allowance; source admission and all six native tests passed for finalized candidate `sha256:8f6f1d3bb267d97302fceee952db7abbd8b4831c0fbbb90da67681e72d7bbe06`.

### [x] WORKER-PROBE-DIAGNOSTICS-001 — Preserve actionable SSH probe failures

- **Release target:** 1.3.0
- **Priority:** P0
- **GitHub issue:** [#3](https://github.com/jordanhubbard/literate-ai/issues/3) (migrated from NVIDIA-dev/literate-ai#505)
- **Owner:** worker capability probes, SSH transport diagnostics, and CLI rendering
- **Direction:** A failed worker probe must name the worker and preserve the bounded,
  redacted SSH cause instead of collapsing host-key, authentication, DNS, refusal,
  and timeout failures into one generic transport error.
- **Conclusion:** Diagnostics are part of operability, not evidence authority. Retain
  worker identity, exit status, stable cause classification, and safe stderr while
  preserving BatchMode, host-key policy, output bounds, and credential redaction.
- **Depends on:** WORKER-HEALTH-001
- **Outcome:** Diagnostic repair is landed and its issue acceptance is verified.
- **Implementation:**
  - [x] Carry worker ID, SSH exit status, bounded stderr, and redacted transport cause
        through individual and `--all` probe results.
  - [x] Render distinct remediation for unknown/changed host keys, rejected
        credentials, name resolution, connection refusal, and timeout.
- **Evidence:**
  - [x] Multi-worker regressions identify only the failing worker and retain each SSH
        exit-255 diagnostic without secrets or unbounded output.
  - [x] Real first-contact and registered-host probes demonstrate that host-key setup
        is not misreported as failure of unrelated workers.

- **Local evidence:** Seventeen focused capability/CLI tests pass. A real SSH probe
  with an isolated empty known-hosts file reports host-key refusal, and the same
  Linux worker succeeds with its ordinary registered key. The all-worker probe
  correctly names a different worker whose GPU observation reports zero memory;
  that invalid inventory remains refused and is not evidence of an authentication
  failure. No host-key policy or saved observation was changed by these dry runs.
- **Qualification follow-up:** Resolve or explicitly exclude the zero-memory GPU
  observation under RELEASE-INTEGRATION-003 capability admission; do not silently
  substitute invented capacity in order to admit that worker.

- **Current qualification:** Four capability tests cover every named SSH cause, bounds/redaction and mixed healthy/failed routing. Fresh strict empty-known-host refusal followed by normal registered-host success passes on the combined 1.3 source. Exact combined CI remains pending; the parent stays open until integration qualification.

- **Closure qualification:** The implementation is landed through PR #110 on `75d73ac2`; exact-head CI run `39790990072` passed. Fresh managed `make python-check` selection `test_worker_capabilities.py` passed all seven cases, including six SSH exit-255 causes, failing-worker identity in a mixed catalog, redaction and diagnostic bounds. The previously checked first-contact/registered-host acceptance is preserved; host-key policy is unchanged.

### [x] PUBLIC-EXPORT-001 — Make the repository safe and useful for public export

- **Priority:** P0
- **Owner:** repository documentation, tests, release identity, and public-export validation
- **Direction:** Remove references to non-public NVIDIA repositories and generalize company-internal examples before copying this repository to a public location.
- **Conclusion:** The current tree must contain no non-public repository, internal host, private project, employee identity, or internal service dependency; public NVIDIA OSS and product documentation remain valid. Repository-self URLs need a destination-neutral migration boundary until the public owner is selected. Existing Git history must not be published unchanged because other refs retain internal GitLab registry and worker identities.
- **Depends on:** none
- **Implementation:**
  - [x] Replace private downstream project evidence with synthetic provider-neutral examples
  - [x] Replace internal GitLab, Jira, email, MaaS, and custom router-specific fixtures and prose
  - [x] Make repository-owned publication and self-update identity configurable for the future public location
  - [x] Add a repeatable tracked-content audit that rejects internal-reference regressions
  - [x] Document the sanitized-export requirement for publishing history
- **Evidence:**
  - [x] `make public-export-check` scans tracked and untracked export candidates, including embedded Office archive members, and passes after a manual remaining-host review found only public NVIDIA endpoints and this repository's explicitly allowed self URLs.
  - [x] Focused forge, update, Homebrew, self-update, MCP-channel, and public-export tests pass; Ruff lint and format checks pass across the repository.
  - [x] `make python-check` passes all 3,627 tests (29 skipped); first-time `make bootstrap` now installs the pinned isolated evaluator, and `make skills-check` passes all six Tier-1 checks for every changed catalog/template skill.
  - [x] End-of-cycle peer survey reports no green reviews or collectable worktrees related to this change; unrelated branch cleanup remains untouched.

### [x] REFRESH-ABSORBED-001 — Recognize absorbed primary worktrees without weakening shared-ref custody

**GitHub issue:** [#503](https://github.com/NVIDIA-dev/literate-ai/issues/503)

- **Priority:** P1
- **Owner:** framework orchestration refresh
- **Direction:** Allow clean attached submodule refresh while preserving external shared-branch checkouts.
- **Conclusion:** Normalize only an observed primary registration proven by Git metadata; retain all external worktree refusal gates. See GitHub issue #503.
- **Depends on:** none
- **Implementation:**
  - [x] Resolve absorbed primary registration against captured checkout metadata; reject ambiguity.
  - [x] Add portable absorbed-primary and external shared-branch regressions.
- **Evidence:**
  - [x] Focused managed Python checks pass, including normal and absorbed worktrees.
  - [x] Disposable attached refresh succeeds and shared-peer refusal preserves all state.

- **Completion evidence:** [PR #504](https://github.com/NVIDIA-dev/literate-ai/pull/504)
  merged to `main` as `acd6da68f74c1667db580c23569b0250d30719dd`. The combined
  public-mirror qualification branch records the resulting lifecycle-driver and
  documentation authority identities and passes the complete managed Python suite,
  including the absorbed attached update, rollback/custody, and native Bazel cases.

### [x] WORKER-CLI-001 — Manage and test private worker registrations through the CLI

- **Priority:** P0
- **Owner:** worker catalog, CLI, SSH diagnostics and native qualification
- **Direction:** Provide worker CRUD and SSH connectivity testing, then use the Linux and Windows pool to qualify Literate AI against current open issue and PR scenarios.
- **Conclusion:** Local registrations are durable private configuration. Add validated atomic CRUD and independent bounded connectivity results without VM provisioning or host-key policy mutation; integrate relevant current review changes in an isolated test branch and retain truthful per-platform evidence.
- **Depends on:** WORKER-PROBE-DIAGNOSTICS-001; published PR #513 diagnostic foundation
- **Implementation:**
  - [x] Add list/show/add/update/remove commands with canonical validation, private atomic writes, conflict protection, and actionable errors.
  - [x] Add worker test selection/all with separate DNS, connection, host-key, authentication, timeout and unsupported results; preserve successful peers.
  - [x] Reconcile all six open issues and four PRs into an explicit qualification matrix, integrating applicable changes and recording unsupported or deferred scope.
- **Evidence:**
  - [x] Focused CRUD/concurrency/negative diagnostic regressions and scoped lint, format, layout, skill and authority checks pass; broader gate failures remain explicitly recorded.
  - [x] Real Linux and Windows worker CLI and issue/PR-derived tests execute the exact changed framework; retain source identities and per-worker outcomes.


- **WORKER-CLI-001 progress:** 229 worker-focused tests pass on the isolated
  PR #513 published baseline plus this change. The first real 20-worker connectivity
  run returns 18 successful handshakes and independent authentication/changed-key
  failures; those are readiness findings, not native framework test qualification.
- **Current tracker qualification matrix (2026-09-30):**
  - Issue [#505](https://github.com/NVIDIA-dev/literate-ai/issues/505): include its
    published diagnostic repair from PR #513, extend peer aggregation and SSH-only
    testing, and exercise actual first-contact and authentication failures.
  - Issues [#497](https://github.com/NVIDIA-dev/literate-ai/issues/497) and
    [#498](https://github.com/NVIDIA-dev/literate-ai/issues/498): use native package,
    scheduling and cache regression suites from PR #513 as real-world worker load.
    Their full production feature acceptance remains owned by their existing items.
  - Issue [#492](https://github.com/NVIDIA-dev/literate-ai/issues/492): include
    native-CLI contract and lifecycle tests; record unsupported cases as such.
  - Issue [#483](https://github.com/NVIDIA-dev/literate-ai/issues/483): include
    worktree placement/refresh regressions. The installed location command refuses
    the current legacy registrations; no cleanup is authorized by this test cycle.
  - Issue [#512](https://github.com/NVIDIA-dev/literate-ai/issues/512): include
    project update/merge regression scenarios and retain the unresolved three-way
    application boundary rather than claiming its feature complete.
  - PR [#513](https://github.com/NVIDIA-dev/literate-ai/pull/513), published
    `a1aff322`: integrated as the starting test baseline. Its failing hosted assertion
    and unpublished follow-ups remain explicit; this branch does not modify its
    owner's worktree.
  - PR [#511](https://github.com/NVIDIA-dev/literate-ai/pull/511): include the
    dynamic-worker roadmap contract; provisioning and VM deletion remain external.
  - PR [#508](https://github.com/NVIDIA-dev/literate-ai/pull/508): include the pinned
    CI action update, with no claim that native workers prove GitHub action execution.
  - PR [#501](https://github.com/NVIDIA-dev/literate-ai/pull/501): conflicting stale
    export branch overlaps public-export work already on main. The export checker,
    self-update implementation and export tests are identical at the compared tips;
    native public-export groups pass on both platforms. Defer the stale branch
    rather than replaying its historical roadmap over newer authority.

### [x] REFRESH-MODE-001 — Validate refresh against admitted physical permissions

- **Priority:** P1
- **Owner:** framework core: repository refresh application
- **Direction:** Use native workers to exercise current issues and PRs; a Linux worker exposed a legitimate group-writable checkout rejected as changed.
- **Conclusion:** Git tree modes encode executable intent, not exact physical permissions. Compare previous and unchanged files against captured physical modes; newly applied changes retain declared output modes. Preserve race and rollback custody checks.
- **Integration finding:** The 85-test composed run had one error: the new real-Git fixture advanced its child commit but left the declared parent pin stale. The fixture now updates its manifest and records the exact authority review before testing refresh. Its isolated real-Git regression passes (151.746 seconds), preserving unchanged group-writable permissions and normal changed-file output modes. The other 84 composed checks passed, including permission drift refusals; native Linux qualification remains required.
- **Depends on:** none
- **Implementation:**
  - [x] Use staged member permission observations for previous and unchanged regular files.
  - [x] Add real-Git regression with group-writable changed and unchanged files.
- **Evidence:**
  - [x] Focused repository refresh permission regression suite passes locally and on a native Linux worker with a group-writable checkout.

### [x] WORKER-PROVISION-001 — Configure and invoke a local provider-neutral worker provisioner

- **Priority:** P0
- **Owner:** framework worker CLI, private configuration and provisioning contracts
- **Direction:** Implement the generic hook in this change: support static workers independently, and launch an organization-supplied command only when dynamic provisioning is explicitly enabled in local user settings.
- **Conclusion:** Add local opt-in command configuration, help discovery and explicit on-demand worker provisioning. Use a versioned provider-neutral request/response boundary, user-supplied environment credential bindings, bounded process execution and private recovery state. Validate the returned worker before registration; keep cloud APIs, provider flags and credential acquisition outside Literate AI.
- **Depends on:** none
- **Implementation:**
  - [x] Add local provisioner configuration CRUD, enabled-by-default-false policy, and help/--help discovery.
  - [x] Add bounded on-demand provisioning with request identity, duplicate-allocation protection, response validation and private registration/recovery.
  - [x] Document the adapter protocol and the complete static-only and dynamic-enabled CLI flows.
- **Evidence:**
  - [x] Disabled/missing configuration and missing credentials invoke no command; malformed output, timeout, identity drift and concurrent requests fail safely without unintended registration or retries.
  - [x] Public CLI synthetic provisioner flow passes on native Linux and Windows and the returned worker can pass independent SSH testing.

- **Generic-hook implementation:** Added local configuration/show/enable/disable/remove,
  provider help discovery, bounded explicit provisioning, credential environment
  bindings, schema-validated SSH registration and durable per-worker recovery state.
  The 245 worker-focused tests pass locally, including 13 real-process hook tests.
  Lint, formatting, changed-skill evaluation, layout, public export, lifecycle-driver
  review and documentation authority review pass. Native hook qualification follows.
- **Refresh qualification correction:** Final native no-op checks passed before the
  broad application run reached a new test fixture with mismatched manifest pins.
  Corrected that fixture to commit both Gitlink and manifest authority together;
  rerunning its application coverage. No full-suite pass is claimed.

- **Final generic-hook qualification:** Framework code at `bb19f82c` passes 248
  worker-focused tests on macOS, Linux and Windows (four Windows platform skips),
  including 16 real-process provisioning regressions. A noneditable wheel with
  SHA-256 `207a2a600d3efd8f458e5c2346f1595baebcb29f1bd1dad4b9ddfb6804f41c6f`
  passes 13 CLI smoke steps outside the checkout, including local opt-in settings,
  a synthetic provider response, private registration/recovery, and real SSH to
  existing Linux and Windows endpoints. This verifies the generic handoff, not a
  provider-specific resource allocation. The repeated pool test reports 19/20 SSH
  successes; the remaining Windows worker independently reports authentication
  failure. Forty private user-path/configuration tests also pass.
- **Qualification boundary:** The broad refresh reruns were stopped in favor of
  the focused physical-permission regression group. Their partial progress is not
  a full-suite pass. The new Git fixture now adds its unchanged member before the
  initial root authority/pins are constructed; it does not rewrite an admitted
  root manifest without its documentation review. No provisioner is enabled in the
  operator's real local configuration. The unrelated cache path and remote-call
  count failures, stale receipt, and Windows broad-refresh failure remain reported.
- **Final peer survey:** No eligible cleanup candidates; stale, dirty or unmerged
  peer branches remain retained. No peer checkout was removed or rewritten.

- **Focused refresh proof:** Six physical-permission regressions pass on native
  Linux at `142120a2`, including a complete real-Git refresh with group-writable
  changed and unchanged members, plus no-op admission and drift rejection. The
  macOS run of the same focused group also passes (six tests, 168 seconds). Framework runtime source
  is unchanged from the three-platform worker and installed-wheel proofs above.

- **Completion boundary:** Worker CRUD, SSH diagnostics and the generic local
  provisioning hook are implemented and qualified in draft PR #514. The six focused
  refresh permission regressions pass on macOS and native Linux. This closes the
  implementation/test tasks, not the integration release: `verify` still reports
  its stale receipt, and broader baseline failures remain owned by their recorded
  work items. The published wheel proof binds runtime code `bb19f82c`; subsequent
  commits only reorganize the regression fixture and record this evidence.

- **1.2 advanced worker integration:** PR #514 head `f452be65` adds the opt-in
  provisioning hook and native qualification beyond already-integrated `d6d003eb`.
  Review preserves disabled-by-default configuration, explicit credential bindings,
  bounded real processes, durable duplicate-allocation refusal and recovery without
  a second allocation. Include this contribution with the existing worker program;
  its hosted failure is the unregistered provisioning schema in the version catalog.
  Version checking reproduces the omitted resource. Move the new schema to the
  current v2 catalog and register its existing wire identifiers, preserving frozen
  published v1 bytes. Qualify schema closure and the combined CLI.
  The wire regression also reproduces a non-SSH response accepted by the public
  schema but rejected by the adapter. Constrain the response schema to the existing
  SSH-only contract; preserve closed records and NUL-command rejection.
  The physical-permission fixture moved to the focused modes module; retain its
  coherent initial Git/manifest authority and unchanged permission assertions.
  Native evidence remains bound to the peer's revisions until integrated qualification.

- **Integrated provisioning checks:** All 248 worker tests and six real-Git physical
  permission regressions pass. Changed-skill checks pass. The combined CLI/catalog
  check additionally found nine provisioning verbs omitted from the canonical
  command inventory. With those entries restored, all 55 combined CLI/catalog,
  version-authority and user-path checks pass. Ruff checks and formatting pass
  for 1,316 files. These focused checks do not replace full release qualification.

- **Ready-queue worker admission:** Remote source indexing must reserve one exact
  admitted worker slot before consuming a shared lifecycle executor slot. When no
  remote slot is free, leave the action pending and continue other ready phases.
  The reservation must release on successful indexing, guard or dispatch failure,
  and executor submission failure. Slot exhaustion and deadline failures remain
  distinct: exhaustion waits without occupying an executor, while an expired
  admission fails the source-index phase. Direct index callers retain bounded
  blocking behavior using the same slot accounting. Qualification must prove
  unrelated ready work progresses while index capacity is exhausted, and a failed
  or completed reservation cannot leak capacity or execute twice.

  Implementation now gives the ready queue a single-use index reservation backed
  by the same occupied-slot set as direct callers. Guard/operation/submission
  failures release ownership; source-index failures retain their phase. Bounded
  retries observe capacity released by callers outside the shared executor.
  The capacity-progress regression fails against `63a4a4c6` and passes after the
  repair. Ten focused queue/real-command-index checks, 365 Standard lifecycle
  tests (four skips), and 48 scheduler/catalog/version checks pass. Ruff checks
  and formatting pass. This qualifies INDEX admission only; all-phase remote
  dispatch, automatic whole-pool sizing, and the remaining release gates stay open.

- **Automatic admitted-pool sizing:** Omitted `--jobs` on build, test, rebuild and
  profile must reach Standard composition as an automatic policy rather than an
  implicit serial cap. Resolve it from the live admitted worker slots, bounded
  at 256; an explicit limit caps admitted capacity. With no admitted pool, preserve
  the one-slot default and explicit local limits. Bind the resolved limit into the
  lifecycle request identity. Legacy complete-node dispatch retains its existing
  integer wire default until all-phase worker composition replaces that path.

  The CLI and Standard rebuild now preserve automatic selection, derive the shared
  executor limit from the admitted slots, cap explicit requests, and record the
  effective count in lifecycle authority. Expired admission retains its structured
  error and starts no runtime execution. The adapter regression fails against
  `62c9e33f` (including a requested 12 jobs incorrectly escaping a five-slot pool)
  and passes after the repair. Seventy combined CLI rebuild, execution dispatch,
  action configuration and adapter tests pass; 12 CLI help/profile checks and 12
  version-authority checks also pass. The final expired-admission regression passes
  with all nine adapter tests. This advances the existing INDEX composition; it
  does not close all-phase remote scheduling or native/LAN release qualification.

- **Portable phase finalization:** Separate deterministic build-plan construction
  from controller-local intent/provider maps. A phase must receive the exact typed
  intent, authorization, command contract, provider and package artifact records,
  and admitted dependency-resolution mode. Check exact input bindings before
  producing a plan. The pure operation preserves historical plan reconstruction;
  current grant validity remains enforced at the execution/dispatch boundary.
  Local finalization retains live SDK admission
  and plan registration; the pure operation must round-trip its public inputs and
  preserve the existing plan identity for each supported resolution mode. This is
  preparation for production remote phase requests, not remote-execution evidence.

  `finalize_standard_component_plan` now takes those explicit inputs, checks the
  intent/request references, compiler and SDK-bound builder identity, output set,
  resolution privileges, and exact provider/package records. Local ports retain
  their SDK custody and registration duties. Serialized records reconstruct plans
  after source/object directories and local maps are discarded; substitution tests
  reject mismatched inputs. A separate comparison against `40d14d6e` preserves
  exact plan documents and identities for none/npm/Python resolution. All 368
  Standard tests pass (four skips), as do 32 catalog/version checks and Ruff checks
  for 1,318 files. The command receiver still supports INDEX only; remote PLAN
  transport and remaining production phases are not claimed by this refactor.

- **Remote PLAN receiver:** Extend the one-shot action protocol with a closed,
  bounded plan-input record binding execution/generation plans, intent, current
  authorization, command contract, exact provider/package records and resolution
  mode. PLAN consumes exactly one authorized predecessor record and its canonical
  action payload. Refuse changed worker/deadline/phase/plan/component bindings,
  missing or extra records, invalid grants and substituted input identities. Return
  the existing typed build-plan document without running host build commands.
  Advertise PLAN only once the real command receiver implements it. Qualification
  must dispatch a real child process and cover malformed, expired, changed and
  oversized inputs; production queue composition remains a separate required step.

  The command receiver now advertises INDEX and PLAN and implements exact PLAN
  finalization. The v2 catalog publishes the closed input-record schema while
  preserving frozen v1. Real child-process dispatch returns the expected plan;
  real refusal responses cover revoked grants and substituted generation plans.
  The action suite passes (124 executions in the first run, including imported
  source-index fixture tests subsequently removed from duplicate discovery). The
  final 17 PLAN/capability checks cover duplicate keys, changed bytes, expired and
  future valid-shaped grants, extra/missing records, worker/phase/deadline mismatch,
  and bounds. Forty schema/catalog/version/immutability checks and Ruff checks for
  1,320 files pass. Real SSH PLAN execution and production ready-queue composition
  remain required; the existing CLI still composes only remote INDEX.

- **Production PLAN composition:** Standard rebuild must dispatch PLAN to admitted
  capable workers through the existing bounded ready queue. INDEX and PLAN share
  one per-worker occupied-slot set and global cap. Capacity exhaustion leaves the
  action pending; unsupported remote phases retain the explicit local path. Once
  admitted, transport, capability, deadline or response failures must fail the phase,
  never silently retry locally. Before build uses a returned plan, the controller
  must independently recompute it from current local intent/provider/SDK authority,
  verify exact equality, and register it using the existing local custody path.

  Production composition now installs `CommandBuildPlanFinalizer` after durable
  source-cache/checkpoint setup and preserves that port through later composition.
  Real child-process proofs verify factory dispatch and local registration, shared
  INDEX/PLAN slot exclusion, and refusal/release of substituted results. The ready
  queue reserves PLAN without bypassing its final identity checks. All 372 Standard
  tests pass (four skips), plus 47 index/admission/configuration/version checks.
  Hosted candidate `e985d512` separately failed run `36772772259`: Ubuntu Python 3.14
  ran 4,904 tests with 38 skips and one malformed artifact-graph error path. Two
  calls pass three arguments to the two-argument validation helper. Removing every
  manifest in turn reproduces that TypeError locally; repair is required before
  advancing the published candidate. Native PLAN SSH and all remaining phases stay open.

- **Hosted artifact-graph refusal repair:** Both missing-export and missing-action
  dependency branches passed an accidental extra label to `fail(path, message)`.
  Restore the two-argument calls. Expand retained-library truncation coverage to
  remove every manifest in turn, and exercise an unrealized action whose provider
  is absent from the graph. Both paths reproduce TypeError before the repair;
  the intended outcome remains a typed contract refusal, with no accepted graph.

  The repaired graph contract passes all 16 artifact-graph tests and seven retained
  library export tests, including every manifest truncation and the unrealized
  action dependency. Both pre-fix reproductions are retained as failed evidence.

- **Portable build intent:** Separate deterministic post-source build-request and
  intent construction from local source/SDK admission and retained library bindings.
  Explicit typed inputs bind the generated candidate to its generation plan and
  command contract, exact provider/package artifacts, SDK identities and dependency
  mode. Preserve existing request/intent identities and privileges; refuse mismatched
  candidate/contract/plan inputs. The local adapter retains source validation, live SDK
  lock checks, evidence recording and library binding custody. Prove reconstruction
  from serialized inputs after the original filesystem/maps are gone before adding
  a remote BUILD_INTENT handler. This refactor alone does not enable that phase.

  Portable construction now preserves the prior serialized intent and identity in
  six comparisons covering none/npm/Python dependency modes with and without SDK
  inputs, including provider and package records. Serialized inputs reconstruct
  after local custody is discarded, and candidate/contract/plan substitutions are
  refused. The existing library-import fixture now supplies its exact candidate
  revision and generation-plan identity; its original two-hash stub failed the new
  binding check. The SDK authority fixture likewise supplies its candidate-bound
  generation-plan identity. The nine SDK consumer checks initially confirmed eight
  passes and one linked-provider stub missing the same identity. With that second
  stub bound to its candidate, both closure checks pass (423.079 seconds), retaining
  the failed run as evidence. All three SDK authority checks also pass. All 374
  Standard tests pass (four skips). Remote BUILD_INTENT composition and complete
  release qualification remain open.

- **Current contribution survey:** PR #515 advanced to `eb309658` with 229 changed
  files. Hosted run `36779999437`, macOS Python 3.11 shard 3, fails the version
  authority check because configured and computed lifecycle-driver identities differ;
  the remaining cancelled jobs are not passing evidence. This draft remains under
  review and is not yet included in the qualified integration candidate.

- **Native PLAN qualification:** Exact revision `4c3539b1493d343daa8ef54c880fad91425adf38`
  passes 36 receiver/composition checks each on native Windows and Linux: runtime
  environment, SSH transport, capabilities, hardware, PLAN records and production
  shared-slot composition. Both hosts then pass a real controller-to-worker SSH PLAN
  dispatch, returning the independently expected plan bytes and refusing revoked
  grants and substituted generation-plan identities with `action_plan.invalid`.
  Receiver identity is `sha256:c9178e6bc57f87e58c97044eae81d705cfc1e2ce2ae127e6a53aceaf210350e0`.
  Private evidence retains exact source/tree custody, detected prerequisites, native
  logs and structured results; no private endpoint or credential enters the repository.
  This qualifies INDEX/PLAN receiver boundaries and PLAN composition/SSH custody,
  not generated build execution, other lifecycle phases, samples or final release.

- **Build-intent result admission:** Expose an immutable portable-input snapshot
  separately from local intent registration so a worker result can be checked before
  it becomes controller authority. Recompute against current source/SDK/command and
  dependency inputs on return, refuse substituted results, validate library-import
  bindings before registering any intent maps, and retain the existing evidence path.
  Local construction uses the same admission and registration boundary. Qualify
  no registration during input capture, no partial registration on refusal, exact
  result admission, and changed library/SDK authority before remote dispatch is added.

  The prior implementation reproduces partial registration on a refused library
  target. Separating input capture and result admission passes 377 Standard checks
  (four skips). A subsequent injected evidence-write refusal reproduces another
  partial-registration path; defer all intent-map writes until both library validation
  and required evidence recording succeed. Cover both refusal boundaries explicitly.

  Final admission now recomputes returned intents against current inputs, validates
  library imports, records required evidence, and only then registers intent maps.
  Input capture performs no intent registration. All 378 Standard checks pass (four
  skips), including substituted results, changed SDK inputs and evidence refusal;
  all three SDK authority checks pass. Both prior partial-registration reproductions
  remain failed evidence. Remote BUILD_INTENT dispatch remains unimplemented: its
  request must carry the current index result and typed provider acceptance evidence
  matching the canonical INDEX/ACCEPT predecessors, not merely export hashes.

- **Remote BUILD_INTENT receiver:** Carry an index handoff containing the exact
  execution plan, generated candidate, command contract, SDK identities, dependency
  mode and actual index record. The current receiver admits its existing disabled-index
  policy only. Each additional canonical ACCEPT predecessor carries the provider's
  typed acceptance evidence, including exact built/tested/executed exports. Recompute
  the canonical DAG, require one correctly bound record per ordered predecessor, derive
  provider artifacts exclusively from those acceptance records, and refuse omitted,
  extra, changed or reordered custody. Packaging-only inputs remain absent at this
  phase. Bound aggregate bytes and record counts, preserve worker/deadline checks,
  and return a typed intent without source materialization or host execution. Qualify
  real subprocess execution for a build-dependency diamond and tampered predecessors
  before advertising this receiver phase. Production queue composition stays separate.

  The receiver now implements BUILD_INTENT and advertises it alongside INDEX and
  PLAN. The v2 catalog publishes the closed index-handoff schema; accepted provider
  records reuse existing typed acceptance contracts. A real command process returns
  the exact intent for a build-dependency diamond and for interface-only edges, and
  refuses changed index or foreign-provider custody. The 120-check action cohort
  passes; final eight receiver checks also cover omitted/reordered predecessors,
  changed generation/contract/export records, duplicate JSON, bounds, expiry and
  worker binding. Eleven production INDEX/PLAN composition checks and 20 schema
  checks pass. This is receiver qualification; production BUILD_INTENT reservation,
  predecessor capture, independent returned-intent admission and native SSH proof
  remain required before claiming that phase's production composition.

- **Production BUILD_INTENT composition:** Add an explicit queued dispatch port
  carrying the completed index identity and typed acceptance records for exact build
  and toolchain providers. Capture predecessors only after the existing acceptance
  barrier; verify each receipt against its result's identity and exports. Reserve
  from the same admitted slots as INDEX/PLAN before executor submission, revalidate
  worker capability and deadline, dispatch the canonical request and independently
  compare returned bytes. Retain result evidence before local intent admission so
  recording failures cannot register state. Preserve the dispatch port through cache
  and checkpoint composition. Refuse missing/substituted provider evidence or remote
  failures without local retry. Keep the legacy complete-node path explicit until
  its separate phase conversion; this step qualifies the shared ready queue.

  Production composition now installs the explicit BUILD_INTENT dispatcher and
  preserves it through cache/checkpoint assembly. Four real command-dispatch checks
  pass, including shared INDEX/PLAN capacity, substituted results, evidence-write
  refusal before registration, and foreign index refusal. The Standard cohort ran
  384 tests successfully with four skips; eight final ready-queue checks pass,
  including exact typed build-provider receipts captured after acceptance and
  refusal of providers represented only by a scalar acceptance identity. Native
  BUILD_INTENT SSH qualification and the remaining remote phases remain open.

- **PLAN result retention before admission:** Match BUILD_INTENT's failure semantics.
  Retain verified remote PLAN bytes before registering the returned plan or SDK
  authorization locally. An evidence-store refusal must leave both maps unchanged
  and release the reserved worker slot; it must not trigger a local retry.

  The injected evidence-store refusal reproduced a partially registered plan before
  the repair. Retention now precedes local admission; all four production PLAN
  checks pass, including unchanged registration maps and released slot capacity.
  Native BUILD_INTENT qualification is running independently at exact d3229715;
  those receipts will not qualify this later PLAN ordering repair.

- **Portable authorization inputs:** Separate deterministic Standard grant
  construction from controller admission. The immutable input binds the exact
  intent, completed index and controller-selected issuance time. Preserve the
  existing constrained profile, requested privileges, actor/reason, grant ID and
  thirty-minute lifetime byte-for-byte. Local SDK validation and evidence recording
  remain at the local port. This is preparation for AUTHORIZE transport, not
  permission for a worker to choose policy, privileges or extend the grant.

  The immutable authorization input now constructs the same grant without accessing
  host state. Two exact previous/new document and identity comparisons pass. Three
  focused checks cover serialized intent, expiry, SDK refusal before construction,
  controller time and both retained documents. The Standard cohort passes 389 tests
  with four skips. AUTHORIZE receiver and production composition remain open.

- **BUILD_INTENT Linux qualification at d3229715:** Native Linux ran 47 checks
  successfully: environment (2), SSH transport (5), capabilities (11), hardware (9),
  BUILD_INTENT receiver (8), production composition (4), ready queue (8). The
  exact-source tree is e9de70db247cfb2cbc66f8b2922277c340e17c01. A real controller-to-
  Linux SSH request returned the exact intent for a build-dependency diamond and
  rejected changed-index and foreign-provider records as action_intent.invalid.
  Receiver identity is sha256:b82b120e8451097d56919fe4a6d836aff79ccbb22d314e1ea44502706b3efbd5.
  This qualifies that receiver/composition scope only, without generated build
  execution or later source changes. Windows qualification remains live. Its full
  sample-worker bootstrap reports missing Codex; required receiver-test tools were
  detected, so that run does not establish full sample-worker readiness.

- **Hosted candidate 4c3539b1 failure:** Run 36780861550 completed with failure in
  Windows Python 3.12 test shard 3 (job 110110475273). Five action-execution-
  configuration tests reject worker admission as lacking a current compatible
  observation. Root cause and native reproduction remain required; this candidate
  is not landing or release evidence.

- **Worker hardware admission diagnostics:** When all eligible probe attempts fail,
  retain the bounded error codes in the admission refusal instead of replacing them
  with generic hardware incompatibility. Do not include raw exception messages,
  private endpoints or environment values. A healthy candidate must still proceed
  when another candidate fails; refused admission must not allocate source CAS.

  All 17 action-execution-configuration checks pass, including sanitized transport/OS
  error reporting, source-CAS nonallocation on refusal, and mixed healthy/unavailable
  candidates. The missing-disk-observation CI case passes on registered Windows at
  d3229715 with a successful actual hardware probe; this does not reproduce or
  resolve the hosted failure. Candidate 4c's final matrix has 11 successful jobs,
  one failed Windows shard and seven cancelled jobs. Further hosted diagnosis is
  required; cancelled checks are not passing evidence.

- **Bounded AUTHORIZE receiver:** Accept the controller's exact intent, completed
  disabled-index record, execution/generation identities and issuance time in a
  closed, size-bounded BUILD_INTENT handoff. Bind the canonical AUTHORIZE action
  and payload to that predecessor. Reconstruct only the existing constrained grant
  policy with its fixed lifetime; refuse future or expired grants, changed source
  indexing and substituted payloads. No host execution, policy selection or clock
  renewal is delegated. Controller SDK admission, independent returned-result
  comparison and evidence retention remain required for production composition.

  The one-shot receiver now implements AUTHORIZE and advertises it with INDEX,
  BUILD_INTENT and PLAN. The v2 schema publishes its closed handoff; v1 is unchanged.
  All 126 action checks pass, including real grant return, changed-index refusal,
  future/expired/controller-time checks, payload binding, duplicate fields and
  oversized records. This is receiver qualification only; production AUTHORIZE
  reservation and independent controller admission remain open.

- **Production AUTHORIZE composition:** Reserve the existing shared worker pool
  before dispatch. Capture issuance time only once capacity is owned and current
  local SDK admission succeeds; bind the completed index and exact intent.
  Independently reconstruct returned grant bytes, retain them before local evidence
  admission, and recheck SDK custody and grant validity without renewing issuance.
  Queue consumers keep their exact authorization checks; no remote failure invokes
  local authorization as a retry. Cache/checkpoint recomposition preserves this port.

  Native Windows qualification at d3229715 completed with an expired-deadline error
  in the combined BUILD_INTENT fault-injection test's slot-release assertion.
  The environment (2), transport (5), capabilities (11), hardware (9) and receiver
  (8) groups passed. Split substituted-result and evidence-store refusals into
  separate fixture lifetimes for BUILD_INTENT and AUTHORIZE, and assert the exact
  intended error so deadline expiry cannot satisfy a generic refusal assertion.
  Preserve production time bounds; native requalification remains required.

  Production AUTHORIZE now composes through the shared pool and preserves its port
  across cache/checkpoint reconstruction. All 395 Standard tests pass (four skips).
  After splitting fault scenarios, all 31 production action/queue checks pass.
  Real subprocess checks cover unchanged grant return, slot exclusion, deferred
  time capture, substituted or unretained results before admission and SDK drift.
  Queue tests reject malformed authorization before finalization; local admission
  refuses renewed issuance and expired grants before recording evidence. Native
  AUTHORIZE and repaired Windows BUILD_INTENT qualification remain required.

- **Portable BUILD contract preflight:** Reuse the existing locked-command export
  and provider-artifact checks independently of controller paths and mutable local
  registries. Preserve exact declared export IDs, Component, role, ABI, target,
  media type, producer and compiler identities, plus ordered provider identities.
  The local adapter retains its existing refusal behavior before commands execute.
  Qualify deserialized inputs after removing local source custody and changed
  export/provider refusals. This is a prerequisite for the BUILD receiver; worker
  toolchain observation, source/provider materialization, SDK/package custody and
  retained build-result admission remain separate required work.

  The pure preflight now validates typed, deserialized plan/contract/provider
  records without source directories or host bindings. Three focused checks pass,
  covering source-independent validation and changed export ID, role, ABI, target,
  media type, producer, compiler and extra-provider refusal. The local adapter
  preserves its error type and refuses before command execution. All 400 Standard
  tests pass with four skips. Work is retained in the temporary BUILD checkout
  because the original local repository is currently read-only.

- **Worker-local toolchain selection for BUILD:** Retain a bounded immutable registry
  of actual local tool bindings supplied by worker startup discovery. Requests
  select exact canonical identity tuples only; they cannot supply executable paths,
  environment values or aliases. Refuse duplicate or unavailable identities and
  revalidate selected launchers and observed runtime guards at use. An opaque
  authority identity without a drift guard is not a worker observation. Keep
  private invocation details out of exported inventory. This prepares the BUILD
  receiver's local execution boundary; wire discovery, scheduling and BUILD
  execution remain required before claiming remote build support.

  The worker registry now retains a bounded immutable identity-to-binding map.
  Five focused cases cover a real discovered Python toolchain, independent worker
  paths, launcher drift, observed-runtime guard drift, unguarded aliases, duplicate
  or missing IDs, changed arguments/environment, and identity-only inventory.
  All 131 action checks pass. Worker startup discovery and BUILD integration are
  still required; the registry alone does not advertise a host-execution phase.

- **Linux AUTHORIZE SSH qualification at d25ef141:** Native qualification completed
  all 59 checks successfully, including BUILD_INTENT/AUTHORIZE receivers, production
  composition and the ready queue. A separate real controller-to-Linux SSH request
  returned the exact authorization and refused expired controller time, changed
  source-index custody and changed generation-plan identity as
  action_authorization.invalid. Receiver identity is
  sha256:0e86ec74e9a069b9548832539003336d45f5d2b750d6b785bd6d83b1888019d7.
  This is exact-revision phase evidence, without generated build execution.
  Windows native qualification also completed all 59 checks at d25ef141, including
  production BUILD_INTENT (five checks in 1087.632 seconds), production AUTHORIZE
  (five in 1187.548 seconds) and the ready queue (nine in 3.767 seconds). The exact
  revision and successful terminal report were retrieved with the full native log.
  This qualification covers receiver and composition behavior, without generated
  build execution or the subsequent BUILD preparation commits.
  The separate controller-to-Windows SSH AUTHORIZE proof also passed: the exact
  authorization record was returned, while expired controller time, changed source
  index and changed generation-plan identity were refused as
  action_authorization.invalid without a result. Its receiver code identity matches
  the Linux proof above; the accepted authorization record is
  sha256:a53a9706758a984e831144c13380475109821bf8cca587c8fd7dd6fe2c964626.

- **Phase-scoped local BUILD runtime:** Permit an explicit canonical command-phase
  scope while preserving the full lifecycle default. Require every and only actual
  tool dependency for the selected phases; npm BUILD retains its Node dependency.
  Reject out-of-scope test, execution and independent acceptance before side effects,
  including SDK and packaged execution branches. This prepares worker execution
  without advertising BUILD before its custody and authorization integration.

  The adapter now enforces explicit command scopes before dispatch and retains the
  full lifecycle default. Five focused checks cover a real BUILD with unavailable
  TEST/EXECUTE tools, early refusals including SDK/package dispatch entry points,
  malformed scopes, a shared launcher that cannot bypass phase restrictions, and
  npm BUILD's Node dependency. All 405 Standard tests pass with four skips. Remote
  BUILD source/provider custody, authorization and result transfer remain pending.

- **Portable BUILD authorization admission:** Extract a shared current-grant and
  exact-plan check for BUILD worker admission. Reuse it in local admission of a
  remote PLAN result, preserving live SDK validation and local error semantics.
  Verify serialized input admission without source custody, expired/revoked/future
  grants, altered index/privileges and substituted plans before any local retention.
  Receiver wiring and actual BUILD transfers remain part of the open 1.2 program.

  The portable admission check is now shared with local remote-plan admission. Six
  focused checks pass, including serialized authority after controller source removal,
  revoked/expired/future grants, index/privilege substitution, changed commands and
  providers, and refusal before local plan retention. Four production PLAN-dispatch
  tests pass. This validates authority admission; it does not yet execute remote BUILD.

- **Portable generated-source validation for BUILD:** Capture recipe-derived SBOM
  and generated-suite validation inputs in a path-free, immutable transport value.
  Use the same validators during ordinary registration and transferred registration,
  reject mixed recipe/transport authority, and retain the exact existing custody
  identity. Prove transfer after controller source removal, changed evidence refusal
  without registration, and actual BUILD from the worker copy. Binding these inputs
  into BUILD's action envelope remains required before enabling remote dispatch.

  The registry now captures and exports immutable recipe-derived validation inputs,
  revalidates worker-local SBOM/suite bytes with the existing validators, and refuses
  competing validation authority without replacing retained state. Six focused
  checks pass: a real BUILD after controller source deletion preserves the exact
  custody record; altered recipe/reference/result-shape/dependency-graph authority,
  changed worker bytes, malformed or oversized documents and mixed/replaced authority
  are refused. All 417 Standard tests pass with four skips. BUILD action-envelope
  binding, provider materialization and receiver dispatch remain open.

- **Shared CAS source materialization for BUILD:** Reuse INDEX's bounded manifest,
  digest, deadline and temporary-workspace rules for BUILD source preparation. Bind
  the admitted candidate and exact strict source-custody identity to the current
  plan/grant and captured validation inputs. Prove HTTP transfer into an independent
  worker CAS after controller source removal, actual build from that registry,
  pre-fetch authority refusals, interrupted/changed transfers and cleanup. Keep
  source preparation distinct from the still-required bounded BUILD receiver.

  INDEX now uses the shared source materializer. BUILD source preparation rechecks
  its exact plan/grant and candidate before transfer, reconstructs strict source
  evidence on the worker and compares the expected custody identity before yielding.
  Five focused cases pass, including real HTTP transfer to an independent worker CAS
  followed by BUILD after controller source deletion, expiry during transfer, corrupt
  fetch refusal and cleanup after an interrupted body. All 136 action tests pass.
  Host-execution bounds, provider materialization and BUILD result transfer remain
  required before enabling remote BUILD.

- **Bounded BUILD worker supervision:** Add a worker-side child supervisor using the
  existing bounded process-tree owner. Bind its private launcher and exact admitted
  input bytes, cap execution by both the current grant and action deadline, check
  cancellation during execution, bound outputs and refuse private diagnostic leakage.
  Prove real-child interruption on authorization expiry/cancellation, output overflow
  refusal and descendant cleanup. BUILD wire admission and worker composition remain
  required; the supervisor alone must not advertise remote BUILD capability.

  The worker supervisor now binds a private launcher and exact admitted input bytes,
  uses the shared bounded process-tree owner, checks grant/deadline/cancellation
  during execution and rechecks authority and launcher custody before returning.
  Seven real-child tests pass, including both real-time deadline orderings, running
  cancellation and expiry, input mismatch/overflow and changed launcher refusal,
  stdout/stderr limits, private diagnostic suppression and descendant cleanup after
  successful parent exit. All 143 action tests pass. BUILD record decoding, worker
  composition, signal/cancellation routing and artifact/evidence verification remain
  required before this supervisor can enable remote BUILD.

- **BUILD child record admission:** Replace the supervisor's opaque input assumption
  with a closed, bounded record binding execution/generation identity, exact plan,
  current authorization, command contract, provider/package declarations, generated
  candidate, source manifest and captured validation/custody identities. Reconstruct
  the intent from those inputs and the plan from its authorization before launch.
  The child consumes the same verified record; private executables and environment
  remain worker-owned. Prove changed authority and malformed records refuse before
  launch, while the accepted record reconstructs strict source custody. Receiver
  dispatch, provider materialization and result transfer remain open.

  The supervisor now derives authority solely from the exact decoded record before
  launcher access. Five decoder checks cover changed candidate/generation/plan,
  malformed/duplicate/oversized JSON, revoked/expired grants and real source custody.
  Eight process tests retain interruption/output/descendant checks and add a real
  child which repeats admission and builds from worker CAS after controller source
  removal. All 149 action tests pass locally. The final process assertion accepts
  native text line endings; exact source and artifact bytes remain verified by the
  existing custody checks. This is not production remote BUILD qualification.

- **Hosted qualification follow-up:** Run 36794916017 at b776e9d3 finished with
  Windows shard two failing two tests: the real Bazel shared-product test received
  HTTP 500 fetching pybind11_bazel, and the hardware bounds test exceeded its
  60-second probe deadline. The shard reports 1095 passed and 39 skipped; sibling
  cancellation is not qualification. Native d25ef141 hardware checks passed, but
  that does not supersede this hosted failure. Artifact retrieval is currently
  unavailable, so the probe's cause remains unresolved. Preserve execution bounds
  and require successful exact-head hosted qualification before release.

- **Transferred BUILD result admission:** Revalidate a transferred artifact tree
  against the exact retained plan, current authorization, provider materials and
  expected Standard build evidence before registering local export custody. Stage
  export registrations until SBOM/evidence validation and final authority/tree
  checks succeed, including the ordinary local build path. Prove real transfer and
  subsequent use after producer artifact removal, changed exports/SBOM/evidence,
  expired grants and failed validation without partial registrations. This prepares
  controller acceptance; remote transport and evidence-record retention remain open.
  Admission now requires the existing bounded qualification reader and build
  process/artifact-tree verifier before filesystem reopening. Export registrations
  are staged until exact evidence, current authority and unchanged source/provider/
  artifact custody pass. The broad Standard suite passes 426 tests with four skips.
  After adding the final proof-record gate, ten focused tests and all 26 BUILD action
  checks pass. These prove BUILD-to-TEST use after producer artifact deletion,
  refusal of altered exports/evidence/SBOM and missing supporting records, grant
  expiry and tree mutation during admission, foreign roots/links, and preservation
  of prior registrations after a failed replacement. Existing real process
  observations remain evidence of execution even when later artifact admission fails.
  Production worker result encoding, transport, record retention and controller
  composition remain required before advertising remote BUILD.

- **BUILD result CAS transfer:** Carry a bounded closed result record binding the
  exact BUILD input, Standard evidence, whole artifact archive and supporting record
  references. Reuse canonical directory archives and private staged-tree custody;
  preserve file modes and bind all bytes to verified build observations. Verify
  controller CAS contents, retain supporting records before artifact registration,
  and remove failed stages while preserving prior admissions. Prove real HTTP CAS
  transfer after producer artifact deletion, corruption/substitution/bounds refusal,
  and retention/authority failure without partial registration. Production child and
  dispatcher composition remain required; do not advertise remote BUILD yet.

  The result adapter now captures canonical archives and proof records into worker
  CAS, transfers and verifies them through an independent controller CAS, retains
  records before admission, and owns the received stage through final registration.
  All 160 action tests pass. Eleven result cases include real HTTP transfer and
  subsequent TEST after worker artifact deletion, corrupt cached/remote bytes,
  archive substitution, control bounds, retention/expiry failures, read-only modes,
  changed producer/staged files, and preservation of a replaced foreign stage.
  Eleven transferred-admission checks also pass, including expiry during the final
  tree recheck. All 37 final BUILD action checks pass after binding result decoding directly to
  the exact input bytes.
  Production receiver/dispatcher wiring and custody-only admission on controllers
  or TEST-only workers without BUILD tools remain open; native mixed-profile and
  directory-export qualification is still required before release.

- **Post-BUILD artifact admission across phase scopes:** Treat verified artifact
  admission as data custody, not compiler execution. A TEST-only worker must accept
  the exact completed BUILD result without possessing its compiler binding, then
  run its own locked TEST command. Keep current plan/grant, source/provider/SBOM,
  supporting-record and staged-tree checks intact, and prove BUILD still refuses
  before process access. A controller with no execution adapter remains a separate
  required integration step; do not advertise complete remote lifecycle support.

  Artifact admission no longer requires BUILD scope; every host-execution guard
  remains in place. A real BUILD using a distinct compiler invocation transfers its
  archived artifact and proof through separate worker/receiver CAS stores after the
  producer artifact tree is deleted. The TEST-only receiver has no compiler binding,
  retains and admits the exact evidence, runs its own locked TEST, and refuses BUILD
  before compiler access. All 12 admission tests, five command-scope checks and
  37 BUILD action checks pass locally. Zero-execution controller custody and full
  production phase dispatch remain required.

### [x] WORKER-QUAL-002 — Qualify integrated worker and remote PLAN behavior on native hosts

- **Priority:** P1
- **Owner:** Framework worker transport and native qualification
- **Direction:** Continue the worker CLI work after all twenty workers pass SSH, using the current published integration and existing issue/PR repairs.
- **Conclusion:** Verify the integrated schema/catalog and Windows cache repairs, exercise typed PLAN through real Linux and Windows SSH, and fix only reproduced gaps. Preserve exact revisions and report incomplete release gates separately.
- **Discovered gap:** Native Windows fails before the twelve-membership regression reaches production code: fixture setup uses ordinary paths beyond MAX_PATH. Preserve the long-path challenge and use the existing native path boundary for fixture creation and cleanup.
- **Depends on:** none
- **Implementation:**
  - [x] Reconcile merged PR 514 and current integration evidence; record the repaired fleet.
  - [x] Run current worker, catalog, cache and remote execution checks on native Linux and Windows.
  - [x] Repair and rerun the native Windows long-path fixture setup.
  - [x] Exercise real SSH PLAN requests and refusals without weakening authorization or silently falling back.
- **Evidence:**
  - [x] Targeted repository-managed tests pass with exact source identities on selected native hosts.
  - [x] Real SSH PLAN succeeds on Linux and Windows and malformed or unauthorized requests remain refused.
  - [x] Record discovered defects and qualification limits, with no release-readiness claim.

- **Qualification evidence:** Published integration `4c3539b1493d343daa8ef54c880fad91425adf38`
  (tree `c6589047a219db691ee576541a65bb2c6b9c47f8`) includes merged PR 514
  (`63a4a4c6e5b1c87a45525a236d30f27ad0041ae0`). The private fleet contains
  ten Linux and ten Windows 11 workers; all twenty passed CLI SSH testing after
  replacement of the previously failing Windows instance. Provisioning remains
  disabled unless locally configured. No provider-specific implementation was added.
- **Native source checks:** Repository-managed `make python-check` on Linux passed
  248 worker, 12 version/catalog, 11 cache-roundtrip, 19 remote-execution and six
  PLAN tests. Windows passed the 248 worker (four skips), 12 version/catalog
  (one skip), and 11 cache-roundtrip tests before exposing the fixture defect.
- **Live transport evidence:** Production capability probing and
  `CommandLifecycleActionDispatcher` over actual SSH succeeded on native Linux
  and Windows. Each receiver used an independently configured worker identity,
  returned the fixture's exact canonical plan bytes, refused revoked grants and
  changed generation identities with `action_plan.invalid`, and left its build
  workspace empty. No SSH subprocess was mocked. Private result artifact SHA-256:
  `598440909f5829b988dba13810cccee1d96d86d6dcfe6b993e0721dc88936370`.
- **Limits:** This is focused worker/transport qualification, not the full release
  ladder, all-phase scheduling proof, generated application acceptance, or proof
  that an organization-specific dynamic provisioner has been configured. Native
  identities and logs remain private. End-of-cycle peer survey found no green
  reviews to absorb; the integration PR remains independently owned.
- **Repository verification:** `litai verify` passed authority, skipped three undeclared/inapplicable gates, and refused the existing stale project test receipt (`project.test_receipt_stale`). This focused repair does not replace the project-wide receipt.
- **Repair validation:** macOS and native Windows each passed all 19 remote-execution
  tests after the fixture repair; Windows also passed all six PLAN tests. The
  native rerun used the published integration above plus only the revised
  `tests/critical/test_remote_execution.py`, SHA-256
  `aaca7479fd370366c7af81ca40f62c9703fed46e77de4f46db2a9b5d00d3c4a4`.
  The long-path assertion, twelve distinct cache memberships, receiver short-root
  assertions, and cleanup assertions remain enabled. Production code is unchanged.

### [x] ONBOARD-VIDEO-001 — Feature the continuous onboarding video in the README

- **Priority:** P1
- **Owner:** root README and onboarding documentation
- **Direction:** Prominently feature the onboarding video for new users.
- **Conclusion:** Link the existing public 13:38 film with a preview, chapters and subtitles near the top of the README. Pin public media to its published commit while PR 10 remains unmerged; do not imply a software release or completed audience review.
- **Depends on:** none
- **Implementation:**
  - [x] Add a prominent watch section ahead of the architectural overview.
- **Evidence:**
  - [x] Verify public media, thumbnail, chapter and subtitle links and check the documentation diff.
- **Verification:** Commit-pinned MP4, preview PNG and SRT return HTTP 200;
  GitHub confirms the chapter file at the same published revision. The preview
  was visually inspected and `git diff --check` passes. This is documentation
  discoverability, not a claim that draft PR #10 or its framework changes landed.

### [x] ELIXIR-001 — Add Elixir implementation-language support

- **Priority:** P1
- **Owner:** Elixir Flavor, generation skill, Standard command profiles and host toolchains
- **Direction:** Add Elixir as a supported implementation language in litai.
- **Conclusion:** Add a portable dependency-free Elixir tree strategy with explicit BEAM host runtime constraints, shipped initialization assets, and public lifecycle tests; retain Mix/Phoenix as separate future ecosystem policy.
- **Depends on:** none
- **Implementation:**
  - [x] Author and ship the Elixir Flavor, specification and generation skill
  - [x] Integrate toolchain discovery and Standard build/runtime execution
  - [x] Cover catalog, init/add, lifecycle and update documentation
- **Evidence:**
  - [x] Focused Python, formatting, specification and skill checks pass
  - [x] Real Elixir host smoke passes on an available Elixir/OTP installation

- **Verification:** `make python-check` passes the 56 flavor tests (including the
  eight Elixir tests; the original native-runtime skip is now qualified), 59 project-initialization tests,
  20 schema-catalog tests, six multi-entrypoint tests and six runtime-driver tests.
  Lint, format, repository
  layout, OpenSpec, documentation rendering and pinned SkillEvaluator admission pass.
  The new skill scores 91.5/100 in both catalog and initialized template.
- **Qualification limits:** Native macOS execution passes with Elixir 1.20.4
  and Erlang/OTP 29 (ERTS 17.1). The repeated `make python-check
  PYTHON_TEST_PATTERN=test_elixir_flavor.py` runs all eight tests with no skips,
  including toolchain discovery and execution of the copied script tree after
  removal of the generation workspace. Live coding-provider generation/acceptance
  and native Linux/Windows execution remain release qualification work. The broader Standard suite passed 64
  tests before its Rust verifier fixture aborted because the installed Cargo links
  a missing Homebrew `libllhttp.9.3.dylib`; `cargo --version` reproduces that failure
  independently of this branch. No native Rust failure is treated as a pass.
  `litai verify` passes authority, names the three inapplicable gates as skipped,
  and rejects the previous project test receipt as stale after these authority
  changes; a current full receipt is not claimed.
- **Next action:** Complete for portable script-tree support and macOS native
  smoke verification. Broader live generation and cross-platform qualification
  remain release gates; no full release receipt is claimed.

### [x] WINDOWS-INSTALL-001 — Qualify native Windows installation and CLI startup

- **Priority:** P1
- **Owner:** framework host-install adapter and Windows documentation
- **Direction:** Test installation and basic execution on a native Windows host, and fix concrete failures.
- **Conclusion:** Keep prerequisite validation intact while reporting inaccessible declared tool-search paths through the typed host-install diagnostic contract; document a PowerShell source-install command. Validate isolated package installation without changing global native tools. This supports PROJECT.md Goals 1 and 4.
- **Depends on:** none
- **Implementation:**
  - [x] Report inaccessible declared native PATH augmentation through HostInstallError and add regression coverage.
  - [x] Document the native PowerShell install entry point and record isolated CLI qualification.
- **Evidence:**
  - [x] Focused host-install and installer regressions pass on Windows.
  - [x] Isolated installation, doctor, onboard create, project validate and launcher startup pass; record any unmet native prerequisites.
- **Evidence:** Native Windows/Python 3.11 runs five focused tests via
  `python -m unittest tests.critical.test_host_install tests.smoke.test_install_litai`.
  Ruff lint and formatting pass. The installed editable CLI runs help, doctor and
  onboard-create planning. Native installer preflight now exits with a clear
  diagnostic instead of a traceback on inaccessible declared tool directories.
- **Installed-wheel evidence:** A clean non-editable wheel at `6e633a7` has
  SHA-256 `22f7e7b7e714fd547dccdb9afa7875588843b777d75c9658bb400a3a6258146a`.
  Fresh isolated wheel installation resolves all dependencies; `pip check` passes.
  Outside the checkout, the private Windows launcher reports its embedded exact
  revision, imports only the installed package, and runs doctor, acknowledged
  onboard-create, canonical project validation, starter lock and starter plan.
  This proves core CLI operation, not native host-tool or generated-code readiness.
  The sandbox's default Git Schannel transport fails authentication; this test
  uses a process-only OpenSSL transport configuration, without changing host Git.
- **Qualification limits:** Live coding-provider generation is outside this core
  install/CLI qualification slice. The current restricted session cannot inspect all declared
  native tool directories; GNU Make is absent, so `make python-check` cannot run.
  The initial isolated build-dependency install did not complete; installing the
  exact pinned setuptools then using `--no-build-isolation` completed the editable
  install. Tracker/peer survey skipped because the named `gh` CLI is unavailable.
  Existing CI runs these tests on all supported platforms and performs installed
  wheel qualification on Windows. Require its exact-branch result before landing.
- **Final CI evidence:** [Run 37274186953](https://github.com/jordanhubbard/literate-ai/actions/runs/37274186953)
  completes successfully with all 20 jobs passing at exact implementation/test
  commit `e4f58b7ead9d0319c051d5e7ff3f6d30a48ff159`. Windows, Linux and macOS
  pass full tests/conformance, native installation/uninstallation/reinstallation,
  and non-editable installed-wheel verification. Python 3.11/3.12/3.14 cells are
  covered by the existing supported matrix.
- **Next action:** Complete for core installation and CLI startup. Live generated
  applications remain a separate authorization and qualification surface.
- **CI review repair:** The first full run at `618e5dc`
  ([run 37271309114](https://github.com/jordanhubbard/literate-ai/actions/runs/37271309114))
  passed Windows platform smoke but rejected stale documentation authority during
  Linux sample-composition validation. Review the narrow source/documentation diff,
  record the lifecycle TCB through `scripts/review_lifecycle_driver.py --record`,
  then record documentation through `litai project documentation-review . --record`.
  Both authored pins are current; this is required review bookkeeping, not a
  relaxed gate. The regression now drives public host observation with a denied
  filesystem boundary and verifies fail-closed typed readiness on every platform.

### [x] CI-FIXTURE-001 — Wait for POSIX child termination before fixture cleanup

- **Priority:** P1
- **Owner:** remote sample fanout end-to-end fixture
- **Direction:** Cross-platform qualification exposed a macOS race in the existing worker process-group termination test.
- **Conclusion:** Wait at most five monotonic seconds for the child signal-handler marker inside the temporary fixture, preserving the termination assertion and production supervisor behavior.
- **Depends on:** none
- **Implementation:**
  - [x] Add bounded marker polling before temporary directory cleanup.
- **Evidence:**
  - [x] Focused fixture regressions and lint pass; native POSIX CI verifies the real process-group case.
- **Diagnosis:** macOS shard 3 at `42955d8` returned the expected supervisor
  timeout status, but checked the child marker before its signal handler finished.
  After the fixture removed its directory, the child raised FileNotFoundError
  writing `child-stopped`. The failure is in fixture synchronization; production
  process-group termination is unchanged.
- **Local evidence:** The focused fanout, host-install and installer batch runs
  eleven cases on native Windows: ten pass and the POSIX process-group case skips
  explicitly. Ruff lint and formatting pass. Lifecycle-driver and documentation
  reviews remain current. Native Linux/macOS execution remains required in CI.
- **Native evidence:** [macOS Python 3.11 shard 3](https://github.com/jordanhubbard/literate-ai/actions/runs/37274186953/job/111647547753)
  explicitly reports the real worker process-group termination test passing at
  `e4f58b7`; the complete 20-job full matrix passes, including Linux POSIX coverage.
- **Next action:** Complete. Preserve the same termination assertion and bounded
  fixture lifetime; no production supervisor behavior changed.
- **End-of-cycle survey:** Supported peer survey and read-only GC planning both
  report `project.peer_work_tracker_unavailable` because `gh` is absent. No
  branches, worktrees or external reviews are collected or merged.

### [x] WINDOWS-INTEGRATION-001 — Integrate Windows fixes with manual migration documentation

- **Priority:** P1
- **Owner:** framework documentation integration and reviewed authority
- **Direction:** Commit, push and land the Windows fixes while preserving newly merged manual 1.0.x migration documentation.
- **Conclusion:** Merge current main without rewriting history, retain both changelog outcomes and migration guidance, then recompute the documentation review marker through its supported command. Source behavior remains the previously qualified Windows fix.
- **Depends on:** none
- **Implementation:**
  - [x] Resolve changelog and documentation marker conflicts while preserving both contributions.
- **Evidence:**
  - [x] Focused Windows regressions, authority validation and review pins pass locally.
  - [x] The integrated pull request passes required CI before landing.
- **Integration evidence:** Merge `origin/main` at `7d897be` without rewriting
  history. Preserve the manual 1.0.x reinstall guidance and succession ADR,
  together with the Windows diagnostic and POSIX fixture changelog entries.
  Runtime, test and installer source is unchanged from `e4f58b7`, whose complete
  20-job matrix passed. The focused eleven-case Windows batch passes with the
  POSIX-only case explicitly skipped; Ruff checks and formatting pass.
  Project validation and the supported documentation review pass; lifecycle
  driver and test-runner review pins remain current.
- **Next action:** Push the integration commit, verify its required CI, and land
  through the authorized writer using merge semantics. Integration CI remains
  pending until evidence is observed.

### [x] WORKER-SCP-001 — Carry configured SSH routing through source and evidence SCP transfers

- **GitHub issue:** [#69](https://github.com/jordanhubbard/literate-ai/issues/69)

- **Priority:** P1
- **Owner:** worker SSH transport and artifact custody
- **Direction:** Use the same private configured SSH-compatible route for commands, source staging and evidence retrieval.
- **Conclusion:** SCP may remain the fixed transfer executable, but must carry the selected SSH program for nondefault worker transports; direct default routing cannot establish the registered worker identity.
- **Depends on:** none
- **Implementation:**
  - [x] Add validated optional SSH-program selection to SCP helpers; propagate it through worker uploads, downloads and file synchronization without changing default OpenSSH behavior or weakening host, path, deadline or custody checks.
- **Evidence:**
  - [x] Invalid transport injection refuses before execution; default platform transfer contracts remain green; an actual native worker performs source/build/test/evidence round trips through its configured route.

WORKER-SCP-001 implementation checkpoint: SCP helpers accept a validated optional
SSH program and the selected worker transport now reaches source staging,
evidence retrieval, retained-harness staging, release synchronization and alignment
file copies. Default OpenSSH argv stays unchanged. Canonical local checks pass
SSH/custody (5 tests), alignment (4) and release synchronization (17), including
custom-route uploads/downloads and transport-injection refusal. A live FreeBSD
SSH/SFTP round trip through the configured route uploaded a 63-byte gzip fixture,
matched its remote SHA-256 and downloaded identical bytes. The result is explicitly
transport-only, not a complete native lifecycle receipt. Full installed native
source/build/test/evidence qualification and existing-platform CI remain open.

- **Closure acceptance:** The current validated SSH/SCP owners complete a real Windows/Python3.12 source upload, hash verification, native compilation, three compiled-artifact behavior cases and evidence download through one registered nondefault transport. The downloaded archive (`sha256:74966a8ce468c3630d16e01406ac8d9d75d6c382e14361d3bfed25bef1cf03c1`) is independently hash-verified, and its compiled artifact bytes match the native result. Five current transport/handler cases pass without skips, including exact default OpenSSH argv parity and invalid transport injection refusal. The owning code/tests are byte-identical to exact CI-qualified `20508324` and landed `fe21a198`; existing alignment/release synchronization coverage remains. See `verification/worker-scp-native-acceptance.json`. This is a complete source/build/test/evidence transfer round trip; it does not mint a framework lifecycle, retained SDK or product receipt.

### [x] RETAINED-ADMISSION-002 — Qualify retained source without a generation agent

- **GitHub issue:** [#70](https://github.com/jordanhubbard/literate-ai/issues/70)
- **Priority:** P0
- **Owner:** Standard source planning and retained admission
- **Direction:** Exact authorized retained source must build, test and accept without discovering or invoking a model provider.
- **Conclusion:** The installed native CLI eagerly selects a coding agent before attaching retained source. Preserve distinct original-input provenance and all post-admission gates; do not fabricate an agent or model-generated evidence.
- **Depends on:** Issue #70; existing retained-source authority and Standard lifecycle owners
- **Implementation:**
  - [x] Add explicit model-free retained source planning and execution wiring while leaving ordinary generation discovery unchanged.
- **Evidence:**
  - [x] Installed public CLI on a native worker without coding agents completes real build, behavior tests and independent acceptance; stale authorization and failed tests refuse without a passing receipt or regenerative cache promotion.

Installed native checkpoint: the exact qualified wheel at `89278c96` bootstraps
37 verified distributions offline. Public Standard rebind and documentation review
complete, and the retained-source review returns an exact authorization identity.
Authorized execution then refuses with `coding_cli.unavailable` before compilation.
Assembly constructs `FilesystemStandardSourceGenerationAdapter.from_environment`
before attaching the reviewed retained input. The correction must give retained
input its own non-executable source selection and avoid representing it as an
accepted cache entry, inherited IDE response or model-generated payload. The
generation model-scope, workflow invocation and cache-key owners currently assume
a coding provider; integrate a typed retained origin through these shared owners
without removing build/test/SBOM/acceptance checks or admitting regenerative cache
membership. This remains distinct from full mixed retained-project work in #22.
The stronger failed-behavior regression exposed automatic replacement retrying
the same retained bytes after their native test failed, obscuring that failure
with a competing-custody error. Retained-origin rejection must be terminal in the
shared lifecycle owner; a changed source tree requires a new exact review.
Preserve the original test failure, prior receipt and ordinary generated-candidate
replacement behavior instead of weakening registry custody or accepting any
generic failure as failed-test evidence.

Local implementation checkpoint: a non-executable retained selection binds its
exact review, fixed no-model scope and invocation identity. It never discovers an
agent, inherits a model, invokes generation or claims accepted-cache authority.
The common lifecycle makes retained-origin rejection terminal and preserves the
original failure. Six focused guard tests, six public CLI rebuild tests, four
existing repair tests, source-cache trust (1), model/workflow (3), planning (1)
and locked-generation (3) checks pass through the canonical Make runner. The CLI
test compiles real retained Python, executes current native cases and independent
acceptance, verifies exact stale-authorization and generated-test failure codes,
and preserves the prior receipt after both rejections. Its log SHA-256 is
`3c92417a0366bbc1892f46e16a0e0c366f696e5454577a3ea9542adc8e6aa24a`.
The editable-test distribution seam is not installed-wheel evidence: native
offline bootstrap, reviewed rebind, complete positive/rejection execution and
current matrix qualification remain open. Full mixed retained projects remain
separately unqualified under #22.

Integration checkpoint: incorporate exact main `5d92797a` after its CI run
`39159031754` passed. Additive requirement, roadmap, changelog and worker-probe
changes from both branches remain present; recompute the combined TCB and
documentation review pins. The refreshed OpenSpec validator requires short
individual behaviors, so retained-provider, post-source-gate and terminal-rejection
requirements retain separate scenarios. On the integrated tree, all six public
CLI rebuild cases, six retained-source guard cases and seven combined worker
probe cases pass. Strict OpenSpec, lint, formatting and repository-layout checks
pass. Exact installed-wheel/native and final release qualification remain open.

Subsequent native evidence: qualified wheel `88fc4bb6` installs its 37 verified
distributions offline. After reviewed public rebind and documentation review, its
public retained-source rebuild compiles, passes three original behavior cases
and independent acceptance with neither coding agents nor a Python override or
unversioned Python alias. Its receipt identity is
`sha256:584a9f38989bfa3ec4edd9cb2128762f6b995e4ceb459327deca314c447bd522`.
The automatic-discovery rejection run remains in progress. The preceding exact
`d96f6b8b` wheel, with an explicit native Python pin, passed both stale-review and
freshly authorized failed-behavior checks while preserving the passing receipt;
the retained evidence archive SHA-256 is
`6fe64332a65d644fbe85114b2b2eb93ef3af51be6076316bbf0fca597c108d12`.
Separately, the complete frozen `d96f6b8b` Python suite passed 1,578 tests with 38
platform/tool skips; log SHA-256
`3b7603d5171be3e9c5bd4641c240c7af4276a7250229c9408ff5d9a2bb995293`.
That broad baseline does not qualify later changes or full mixed retained
projects under #22, typed SSH custody under #69, or a downstream release.

- **Closure acceptance:** A real noneditable installed wheel (`sha256:0d2f0153c8b98afe2ac54e480ce4c4faaf35848deb1c5b027bbe69fc07bfa57f`, exact source `9f8b9dab`) initializes from landed main and admits a reviewed retained Python tree with no coding-agent executable on PATH. Three native behavior cases and independent acceptance pass, supported receipt promotion commits the result, and public accepted-only build exports exact hash-based compiled bytes with no model selector. Real changed-source authorization and failing native behavior refuse while preserving the prior receipt and export; ordinary generation still fails `coding_cli.unavailable`. Thirteen current critical cases and the real accepted-export fixture pass without skips; the latter observes a new actual acceptance identity and refuses unknown/substituted origins, missing admission, corrupted cache bytes and failed fresh acceptance. All 13 relevant owner/test files are byte-identical between the qualified wheel source and main `fe21a198`. See `verification/retained-source-installed-acceptance.json`; the separate hardware CI recurrence, full native SDK and product/package programs remain open.

### [x] MERMAID-SCOPE-001 — Mermaid documentation check scans gitignored build output (generated/)

- **GitHub issue:** [#53](https://github.com/jordanhubbard/literate-ai/issues/53)
- **Current release target:** 1.3.0 (2026-10-18 reconciliation)

- **Priority:** P1
- **Owner:** framework authority and qualification named by the linked issue
- **Direction:** Mermaid documentation check scans gitignored build output (generated/)
- **Conclusion:** Include in 1.3. Preserve the issue acceptance contract and fail-closed authority boundaries. Detailed implementation follows inspection of the owning code.
- **Depends on:** none
- **Implementation:**
  - [x] Implement the linked issue contract without relaxing existing validation
- **Evidence:**
  - [x] Run the issue acceptance cases and required integration qualification before closing

- **Current evidence:** The [1.3 implementation batch](../../roadmap/1.3-integration.md#first-implementation-batch) records the exact local checks and remaining native/integration gates.

- **Closure qualification:** Landed implementation on `75d73ac2`; all 21 documentation-tool tests passed and 121 tracked diagrams rendered successfully. The real temporary Git repository fixture proves invalid ignored generated/worktree Markdown and untracked files do not change candidates, while modified/deleted tracked files are respected. Exact-head CI run `39790990072` passed; this is the complete ignored-file acceptance scope.

### [x] SOURCE-CREDENTIAL-001 — Distinguish credential literals from Python assignment expressions

- **GitHub issue:** [#52](https://github.com/jordanhubbard/literate-ai/issues/52)
- **Current release target:** 1.3.0 (2026-10-18 reconciliation)

- **Priority:** P1
- **Owner:** framework authority and qualification named by the linked issue
- **Direction:** Distinguish credential literals from Python assignment expressions
- **Conclusion:** Include in 1.3. Preserve the issue acceptance contract and fail-closed authority boundaries. Detailed implementation follows inspection of the owning code.
- **Depends on:** none
- **Implementation:**
  - [x] Implement the linked issue contract without relaxing existing validation
- **Evidence:**
  - [x] Run the issue acceptance cases and required integration qualification before closing

- **Execution decision:** Use inert Python AST positions to distinguish assignments of credential-free expressions from literal credentials. Exempt only exact assignment matches with no string/bytes literal in their value; preserve uncertain-language, syntax-error, secret-literal and filename exclusions. An entirely excluded inventory must produce a typed classification diagnostic without matched content.

- **Current evidence:** See the [source admission batch](../../roadmap/1.3-integration.md#source-admission-and-diagnostics-batch) for local tests and remaining integration qualification.

- **Adversarial review repair:** A literal-free assignment must not exempt a different credential literal elsewhere in the file. Add mixed assignment/dictionary/keyword/default and embedded-private-key controls, then renew qualification.

- **Closure qualification:** Landed implementation on `75d73ac2`; fresh managed `test_source_inventory_credentials.py` passed all five tests, including both complete inert portable fixtures, nine mixed-secret controls, malformed/unknown-language and private-key exclusions, Unicode offsets and typed value-free diagnostics. The full landed source qualification passed 2131 tests with 71 platform skips and no failures; exact-head CI run `39790990072` passed.

### [x] GENERATION-REFUSAL-001 — litai test --target host: generation returns empty source when the coding CLI refuses shell use

- **GitHub issue:** [#51](https://github.com/jordanhubbard/literate-ai/issues/51)
- **Current release target:** 1.3.0 (2026-10-18 reconciliation)

- **Priority:** P1
- **Owner:** framework authority and qualification named by the linked issue
- **Direction:** litai test --target host: generation returns empty source when the coding CLI refuses shell use
- **Conclusion:** Include in 1.3. Preserve the issue acceptance contract and fail-closed authority boundaries. Detailed implementation follows inspection of the owning code.
- **Depends on:** none
- **Implementation:**
  - [x] Implement the linked issue contract without relaxing existing validation
- **Evidence:**
  - [x] Run the issue acceptance cases and required integration qualification before closing

- **Execution decision:** Use the existing bounded/redacted failure path for empty generation, retain stdout and stderr refusal evidence, and report the selected isolation profile. Preserve the deliberate no-retry policy for deterministic empty output. Verify refusal text, both streams, credential redaction and one attempt.

- **Current evidence:** See the [source admission batch](../../roadmap/1.3-integration.md#source-admission-and-diagnostics-batch) for local tests and remaining integration qualification.

- **Closure evidence:** The current managed generator module passes all 20 cases with no skips, including the real error classifier with synthetic successful-empty process output: bounded reasons from both streams, secret redaction, selected isolation profile and one attempt for deterministic policy refusal. The owner and regression bytes exactly match landed main `d5c7b278` and qualified source `20508324` (CI `39790990072`, success). See `verification/generation-refusal-acceptance.json`; no live provider refusal is claimed.

### [x] HTML-CANVAS-001 — litai render html graph canvas does not grow with its row

- **GitHub issue:** [#50](https://github.com/jordanhubbard/literate-ai/issues/50)
- **Current release target:** 1.3.0 (2026-10-18 reconciliation)

- **Priority:** P1
- **Owner:** framework authority and qualification named by the linked issue
- **Direction:** litai render html graph canvas does not grow with its row
- **Conclusion:** Include in 1.3. Preserve the issue acceptance contract and fail-closed authority boundaries. Detailed implementation follows inspection of the owning code.
- **Depends on:** none
- **Implementation:**
  - [x] Implement the linked issue contract without relaxing existing validation
- **Evidence:**
  - [x] Run the issue acceptance cases and required integration qualification before closing

- **Current evidence:** The [1.3 implementation batch](../../roadmap/1.3-integration.md#first-implementation-batch) records the exact local checks and remaining native/integration gates.

- **Closure qualification:** A real Chromium browser loads the public installed-CLI graph and SRI-pinned Cytoscape without substitution. The canvas and all three drawing buffers grow from 470 to 1100 pixels with the inspector; zoom changes pixels, filtering changes selection and selected-node focus works. Desktop/mobile screenshots and accessibility structures were inspected: no browser errors, failed requests, invalid numeric text or mobile overflow. Relevant HTML sources match landed `a6a22996`; see `verification/html-issue-acceptance.json`. This is issue acceptance, not release qualification.

### [x] HTML-VERSION-001 — version-check HTML view can never be current at a clean commit

- **GitHub issue:** [#49](https://github.com/jordanhubbard/literate-ai/issues/49)
- **Current release target:** 1.3.0 (2026-10-18 reconciliation)

- **Priority:** P1
- **Owner:** framework authority and qualification named by the linked issue
- **Direction:** version-check HTML view can never be current at a clean commit
- **Conclusion:** Include in 1.3. Preserve the issue acceptance contract and fail-closed authority boundaries. Detailed implementation follows inspection of the owning code.
- **Depends on:** none
- **Implementation:**
  - [x] Implement the linked issue contract without relaxing existing validation
- **Evidence:**
  - [x] Run the issue acceptance cases and required integration qualification before closing

- **Current evidence:** The [1.3 implementation batch](../../roadmap/1.3-integration.md#first-implementation-batch) records the exact local checks and remaining native/integration gates.

- **Closure qualification:** The fresh public non-editable CLI renders declared version/graph pages into a real canonical Git project. Dirty-before-commit and clean-after-commit HTML verification both pass across different exact HEADs; changing semantic project version fails as stale and restoration returns current. The HTML owner source matches landed `a6a22996` byte-for-byte; see `verification/html-issue-acceptance.json` for artifact, source and retained proof identities.

### [x] README-PARENT-001 — Ensure project README links to its actual parent repository through a reusable skill

- **GitHub issue:** [#46](https://github.com/jordanhubbard/literate-ai/issues/46)
- **Current release target:** 1.3.0 (2026-10-18 reconciliation)

- **Priority:** P1
- **Owner:** framework authority and qualification named by the linked issue
- **Direction:** Ensure project README links to its actual parent repository through a reusable skill
- **Conclusion:** Include in 1.3. Preserve the issue acceptance contract and fail-closed authority boundaries. Detailed implementation follows inspection of the owning code.
- **Depends on:** none
- **Current design:** Route initialization/adoption/update/reparent agent workflows through a reusable parent-README skill. Its inert plan/apply helper reads validated direct-parent lineage, preserves authored README bytes outside its managed block, and requires an explicit browser URL for local-only parent identities.
- **Installed-runtime correction:** Expose the helper through `litai project parent-readme` so isolated framework installations do not require an ambient Python import. Renew CLI and installed-launcher evidence before landing.
- **Implementation:**
  - [x] Route initialized and maintainer agent workflows through the reusable parent-README skill and read-only plan / authorized apply helper
  - [x] Cover actual initialized/reparented projects, arbitrary and multiple parents, authored prose, idempotency, local URL evidence and unsafe inputs
- **Evidence:**
  - [x] Run the issue acceptance cases and required integration qualification before closing

- **Closure qualification:** The actual non-editable installed public CLI plans without writes, creates a descriptive browser link for an arbitrary SSH parent, applies idempotently, reconciles multiple changed parents while preserving authored CRLF bytes, and invents no parent for a root project. All ten parent-README contract cases pass in the current full 2139-pass source suite. Generated and maintainer instructions route through the reusable skill. Relevant implementation matches already-landed a6a22996. See `verification/installed-maintenance-acceptance.json`.

### [x] WORKER-GPU-MEMORY-001 — Preserve unavailable NVIDIA GPU memory in POSIX worker observations

- **GitHub issue:** [#44](https://github.com/jordanhubbard/literate-ai/issues/44)
- **Current release target:** 1.3.0 (2026-10-18 reconciliation)

- **Priority:** P1
- **Owner:** framework authority and qualification named by the linked issue
- **Direction:** Preserve unavailable NVIDIA GPU memory in POSIX worker observations
- **Conclusion:** Include in 1.3. Preserve the issue acceptance contract and fail-closed authority boundaries. Detailed implementation follows inspection of the owning code.
- **Depends on:** none
- **Implementation:**
  - [x] Implement the linked issue contract without relaxing existing validation
- **Evidence:**
  - [x] Run the issue acceptance cases and required integration qualification before closing

- **Current evidence:** The [1.3 implementation batch](../../roadmap/1.3-integration.md#first-implementation-batch) records the exact local checks and remaining native/integration gates.

- **Closure qualification:** Landed implementation on `75d73ac2`; fresh managed `test_worker_capabilities.py` selection passed seven tests. The portable NVIDIA fixture executes the POSIX serializer for unknown, positive and failed-query memory cases; the Windows serializer emits explicit JSON null for unavailable memory. This closes the observation/serialization contract and makes no physical GPU capacity claim.

### [x] REFRESH-PERFORMANCE-001 — Repository refresh input checks re-walk gitlink inventory with thousands of git launches

- **GitHub issue:** [#27](https://github.com/jordanhubbard/literate-ai/issues/27)
- **Current release target:** 1.3.0 (2026-10-18 reconciliation)

- **Priority:** P1
- **Owner:** framework authority and qualification named by the linked issue
- **Direction:** Repository refresh input checks re-walk gitlink inventory with thousands of git launches
- **Conclusion:** Include in 1.3. Preserve the issue acceptance contract and fail-closed authority boundaries. Detailed implementation follows inspection of the owning code.
- **Depends on:** none
- **Current investigation:** Replace repeated discovery of already-bound Git inventory with bounded re-observation of exact retained bytes and metadata. Keep fresh configuration/HEAD/cleanliness/worktree observations, exact root authority recomputation, complete index/parent/ref/reflog custody, and fail closed on any drift. Measure real subprocess count and all refresh tamper cases before accepting the optimization.
- **Implementation:**
  - [x] Revalidate bound file/metadata custody instead of rediscovering unchanged Git inventory
  - [x] Retain full discovery twice at preparation and fresh Git fallback for included configuration, packed commits and shared worktree registries
  - [x] Meet the reported real-Git journey budget: 427 launches, 8.9 seconds; retain a <=500-launch regression
  - [x] Pass the existing 24 refresh tests in 210.8 seconds and expanded seven-test input/ref/registration/locator/configuration/object controls
- **Evidence:**
  - [x] Run the issue acceptance cases and required integration qualification before closing

- **Closure qualification:** All 26 current refresh cases pass on local macOS with no skips in 216.957 seconds (under the 300-second limit), including the real-Git <=500-launch regression and unchanged index/ref/Gitlink/registration/locator/configuration/rollback refusals. All owning refresh and orchestration source, contracts and fixture/test bytes match original optimization `b7269a9f`, exact CI-qualified `20508324` and landed main `d5c7b278`. See `verification/repository-refresh-performance-acceptance.json`; this does not claim the separate entrypoint-audit suite is green.

### [x] BRACES-AUDIT-001 — Remove the temporary braces audit exception once a patched release exists

- **GitHub issue:** [#24](https://github.com/jordanhubbard/literate-ai/issues/24)
- **Current release target:** 1.3.0 (2026-10-18 reconciliation)

- **Priority:** P1
- **Owner:** framework authority and qualification named by the linked issue
- **Direction:** Remove the temporary braces audit exception once a patched release exists
- **Conclusion:** Include in 1.3. Preserve the issue acceptance contract and fail-closed authority boundaries. Detailed implementation follows inspection of the owning code.
- **Depends on:** none
- **Implementation:**
  - [x] Upgrade OpenSpec without weakening strict validation; split existing overlong requirements while preserving every normative sentence
  - [x] Implement the linked issue contract without relaxing existing validation
- **Evidence:**
  - [x] Complete the issue’s clean-audit requirement: remove the five remaining low KaTeX-chain findings through a normally resolved supported renderer release, then require zero total findings and renew all documentation/strict gates.
  - [x] Run the issue acceptance cases and required integration qualification before closing

- **Current evidence:** The [1.3 implementation batch](../../roadmap/1.3-integration.md#first-implementation-batch) records the exact local checks and remaining native/integration gates.

**Current audit:** The exception list is already empty in current main (ancestor `4ceedbe9`). Fresh staged OpenSpec installation reports five low findings and no high/critical findings; strict validation and documentation checks pass. Review #24 for closure against its original contract after confirming the landed dependency change; no exception restoration or dependency downgrade is proposed.

- **Earlier staged audit (not final closure):** Main contains OpenSpec 1.14.3 and no `braces` package in the lock; the exception list is empty. A fresh clean staged install and `npm audit --audit-level=high` exit zero: 0 high, 0 critical, 0 moderate, 5 low. The normal documentation gate passes all 21 tool tests and renders all 121 diagrams; all four strict OpenSpec specifications passed on this same tooling source. The remaining low findings are reported honestly and do not reinstate the removed high-severity exception.

- **Final clean-audit qualification:** A fresh install and audit at every severity report zero vulnerabilities. A normally resolved KaTeX 0.18.2 override removes the five inherited low findings; every other lock package and the Mermaid CLI 11.16.0 pin remain unchanged. The new real-library inherited-trust regression fails on 0.16.47 and passes on the patch while preserving explicit trust. All 22 tool tests, 121 diagram renders and four strict specifications pass. The unchanged CLI also renders two actual mathematical expressions with the patched library. See `verification/documentation-audit-qualification.json`. No advisory exception, audit threshold change or forced dependency downgrade is used.

### [x] RECEIPT-REFRESH-001 — Refresh the current project test receipt through the complete lifecycle

- **Priority:** P1
- **Owner:** Project receipt lifecycle and generated-test guidance
- **Direction:** Fix the stale current project receipt.
- **Conclusion:** A fresh lifecycle run rejected a generated case ID colliding with independent acceptance. Clarify generated case naming while preserving all refusal checks, then earn and promote a newly finalized passing candidate.
  A later run exposed a missing retry classification for rejected JavaScript bundle
  modules. Use the existing three-candidate budget and retain refusal evidence;
  authentication and post-build failures remain terminal.
- **Depends on:** none
- **Implementation:**
  - [x] Keep generated implementation case IDs distinct from independent verifier IDs.
  - [x] Retry missing JavaScript bundle modules within the existing bounded policy.
  - [x] Review and record the exact runner source closure after the retry change.
  - [x] Promote only a newly finalized all-passing lifecycle candidate.
- **Evidence:**
  - [x] Complete the host-eligible sample lifecycle and pass test-receipt check, require-current and litai verify.
- **Recorded result:** Commit `597250a9` promotes the finalized passing 22-sample host
  lifecycle (228 tests, 26 component locks, all required evidence roles). Supported
  candidate check and require-current pass; `litai verify` reports two passes, zero
  failures and three configured skips. The complete framework suite reports 1,525
  tests with 37 skips; installing Elixir enables the nine class-setup omissions and
  all 19 explicitly gated Elixir cases, including native Make, Bazel and Mix proof.

### [x] STANDARD-FIRST-BIND-001 — Migrate retained receipt-only projects to reviewed Standard binding

- **Priority:** P1
- **GitHub issue:** [#107](https://github.com/jordanhubbard/literate-ai/issues/107)
- **Owner:** framework lifecycle binding and receipt authority
- **Direction:** Enable explicit reviewed Standard first binding while retaining project-owned receipt requirements and historical evidence.
- **Conclusion:** Plan against exact installed authority and current project identity, preserve custom receipt policy, reject executable driver replacement and tampered or stale plans, and retain compare-and-swap rollback. This is configuration migration only.
- **Contract:** Receipt-only first binding uses a distinct versioned plan with an
  explicit null previous binding. Preserve the entire existing receipt policy;
  without an old Standard driver there is no derived runner identity to advance.
  Existing bound-project plans keep their schema and projection semantics. A
  project with neither receipt policy nor driver uses the separate native initial-binding route, and
  an existing custom executable driver cannot migrate through this operation.
- **Depends on:** STANDARD-REBIND-001
- **Implementation:**
  - [x] Add a versioned first-binding plan/apply route through the existing reviewed command, preserving bound-project plan compatibility.
  - [x] Document receipt-only migration and keep the original acceptance contract intact.
- **Evidence:**
  - [x] Positive public CLI planning/apply, unchanged historical receipt, custom-policy preservation, denied authorization, rehashed weakening, project/installed drift and post-write rollback pass.
  - [x] Thirteen focused rebind/first-binding tests, lint, formatting, repository layout, public export, documentation, OpenSpec and reviewed driver closure checks pass on the controller.
  - [x] Complete full controller regression and exact clean-commit installed-wheel qualification. At `73311c69`, Python 3.14.7 passes 1,801 cases with 42 explicit skips and no failures; the exact wheel and all installed smoke checks pass.
  - [x] Qualify the actual installed CLI on a native receipt-only project copy; preserve original evidence and retain missing lifecycle admission. FreeBSD 16 / Python 3.12.14 verifies all 37 offline distributions, passes all five real CLI operations and preserves all 42 historical evidence files. All 13 exact committed contract cases also pass with installed imports and no skips. Two preceding harness failures remain retained; neither changed production authority.
  - [x] Pass exact-head required hosted CI before landing.

Evidence: [exact wheel and native migration checkpoint](../../../verification/standard-first-binding-development.json). [Draft PR #108](https://github.com/jordanhubbard/literate-ai/pull/108) remains open pending exact-head hosted CI. First binding does not execute or admit a retained source lifecycle, SDK, package, ISO or release.

- **Closure qualification:** Fresh non-editable installed CLI planning binds exact installed authority without writes; denied authorization, rehashed policy weakening and replay refuse. Exact authorized apply preserves the complete receipt policy and historical receipt bytes, and explicitly retains stale-until-rebuild rather than minting acceptance. All current rebind/first-binding contract cases pass in the full 2139-pass source suite; the earlier real FreeBSD custom-policy migration proof remains retained. The implementation already landed with reviewed integration #110 and exact CI 39790990072; earlier draft #108 is superseded. See `verification/installed-maintenance-acceptance.json`.

### [x] LOCK-TARGET-001 — Verify the committed Component target

- **GitHub issue:** [#79](https://github.com/jordanhubbard/literate-ai/issues/79)

- **Priority:** P0
- **Owner:** Project lock-health observation
- **Direction:** Report current non-host locks accurately without rewriting their target or weakening verification.
- **Conclusion:** Read the committed target through the typed catalog-bound lock owner, then reuse current project selector and lock/audit checks. Preserve stale project configuration and input refusal.
- **Depends on:** none
- **Implementation:**
  - [x] Use the catalog-validated committed target in read-only project lock health.
- **Evidence:**
  - [x] A real non-host project lock passes verify/status and exact lock checks; dependency, target/audit and project selector drift still refuse.
  - [x] Complete full-regression and installed/native renewal before deployment.

**Partial evidence:** All seven lock-health regression checks pass, including
six real non-host target/current-policy/refusal checks and the existing installed
HTML lock-state fixture. Three project-verification checks also pass. Lint,
format, repository layout and public-export checks pass. No native build,
package or release admission is claimed by lock-health verification.

- **Closure qualification:** Fresh native macOS public installed-wheel commands lock a real canonical Standard project for `native-test`; verify, status, the exact lock check and the typed current-lock reader agree on `sha256:5a34134ef5e43251a15db4f128d96ede0ef1c5d8eb32cd38f232fa044ee06205`. Project file bytes remain unchanged. Actual selected-Flavor, target-binding and missing-audit mutations refuse, and restoration returns current. The six portable regressions pass and the complete source suite passes 2139 cases with 71 explicit skips. All relevant lock-owner code matches landed `a6a22996` exactly; see `verification/installed-lock-entrypoint-acceptance.json`. This verifies read-only target selection, not construction for a foreign target.

### [x] TRACKER-REPO-001 — Bind forge commands to the selected repository

- **GitHub issue:** [#80](https://github.com/jordanhubbard/literate-ai/issues/80)

- **Priority:** P1
- **Owner:** Tracker command generation
- **Direction:** Preserve the chosen fork/origin identity in generated issue and review CLI commands.
- **Conclusion:** GitHub CLI context can select an upstream parent even after tracker inspection chose the fork. Bind emitted commands explicitly to the parsed selected repository; use explicit repository arguments as the current operator mitigation.
- **Depends on:** none
- **Implementation:**
  - [x] Extend the existing forge command owner with explicit repository identity without changing remote-selection policy or exposing credentials.
- **Evidence:**
  - [x] Portable fork, multiple-remote, enterprise-host and ambient-override fixtures preserve the selected repository across all emitted commands; external writes are not needed for qualification.

- **Closure qualification:** Landed implementation on `75d73ac2`; fresh managed `test_project_tracker.py` passed five tests. Every emitted issue/review/create/merge/status argv carries the selected repository explicitly across fork-style SSH/HTTPS, multiple remotes, enterprise hosts/ports and ambient forge overrides; credentials and unsupported repository paths fail safely without external writes. Exact-head CI run `39790990072` passed.

### [x] CATALOG-FETCH-001 — Fetch immutable catalog snapshots without full history

**GitHub issue:** [#83](https://github.com/jordanhubbard/literate-ai/issues/83).

- **Priority:** P1
- **Owner:** Catalog Git source acquisition
- **Direction:** Import small catalogs from large upstream-derived repositories efficiently while preserving exact provenance.
- **Conclusion:** Use bounded shallow and filtered sparse acquisition for explicit immutable commits, then initialize only relevant selected submodules; preserve other selector behavior and fail closed on missing input. Shallow history alone still transfers the entire selected tree and is insufficient for large source repositories.
- **Depends on:** Git source identity and catalog DAG validation
- **Implementation:**
  - [x] Fetch exact commit pins without transferring default-branch history; request blob filtering and sparse selected directories, then initialize only relevant submodules at the requested revision.
  - [x] Retain canonical provenance, bounded process behavior and destination preservation on acquisition failure.
- **Evidence:**
  - [x] Real Git fixtures prove old pinned contents and shallow ancestry, SHA-256 repositories, selected submodule data without private Git metadata, omitted unrelated blobs/submodules, rejected traversal, and no destination mutation on failure. Eleven catalog checks pass; an actual pinned upstream-derived source import succeeds with canonical resolved-commit provenance.
  - [x] Existing catalog and full framework regression checks pass: 1,850 passed, 42 skipped and no failures (1,892 selected) in 1,063.469 seconds. Report SHA-256 `d4885099d94eba41785a4b7795af11a10f20869fe0eca69aa6e8730799e1d5d6`; log SHA-256 `7fc7ae0393d46d09ca5561950edcf298438682e9aa6ef55fc9dd8d00de7bb255`. Lint/format, layout/public-export, strict OpenSpec and reviewed TCB checks pass.

### [x] SBOM-SCALE-001 — Bound strict validation cost for large retained inventories

**GitHub issue:** [#84](https://github.com/jordanhubbard/literate-ai/issues/84).

- **Priority:** P1
- **Owner:** Dependency CycloneDX adapter
- **Direction:** Reduce elapsed native build time without dropping full per-file provenance or validation.
- **Conclusion:** A real 5266-member source BOM took 88.3 seconds in portable profiling, with 84.3 seconds in quadratic uniqueItems checks. Preserve the official strict schema, registry, formats and semantic joins; use a local equivalent structural uniqueness implementation, without global mutation. GitHub issue: https://github.com/jordanhubbard/literate-ai/issues/84
- **Depends on:** Existing strict CycloneDX and retained BOM owners
- **Implementation:**
  - [x] Use bounded structural JSON equality for strict validator uniqueness while preserving all other keywords and canonical BOM bytes.
- **Evidence:**
  - [x] Differential equality fixtures, strict schema/refusal regression, deterministic large-inventory scaling and unchanged actual BOM identity.
  - [x] Complete full framework regression: 1,855 passed, 42 skipped and no failures across 1,897 selected tests in 1,044.628 seconds. Report SHA-256 `95b14ef1ed69a5c656e39d55e77627ca586a34e047f53fd57d7c939e0c1ea97f`; log SHA-256 `90ff8bbc8b73c400188fbf90799094d8bd728907508dac0c95b52cddcfde68e8`.
  - [x] Complete native installed renewal. Exact installed `6e370033` constructs and verifies source/resolved BOMs during the real FreeBSD retained lifecycle: all 24 original cases pass without skips, all 34 retained records reverify, independent acceptance passes and cleanup is receipt-bound. The strict CycloneDX/uniqueness and SBOM contract bytes remain identical on landed `ef5db15f`; its exact-main CI succeeds in all 26 jobs. See `verification/native-retained-renewal-development.json` and `verification/sbom-uniqueness-closure.json`.

**Partial evidence:** Seven focused checks pass. Structural equality agrees with
the original validator across nested JSON, numeric/boolean distinctions, object
ordering and Unicode; non-JSON fallback, offline SPDX references, unknown-field
refusal and global-validator preservation also pass. The 6,000-object fixture
visits exactly 36,000 JSON values, with a duplicate at the end still refused.
The actual 5,266-member source inventory produces the same 4,661,185-byte BOM,
identity `sha256:04db30dfa7c9e1e1e368562ba3c31d66770463eca16c20f73421c5330cdf4885`.
An unprofiled comparison in the same Python 3.14.7 environment takes 20.251011
seconds with the prior validator and 1.417537 seconds with this adapter.
Baseline log SHA-256 `e491cb95763ae80209daa61ecffdc06113a9d2d583c3f5ad77d18f084fc4b691`;
optimized log SHA-256 `964c238285967f933ff752546255c74d1be71d8c7dc84ed7dfdc32ca4c1bb77b`.
These are source-BOM timings, not whole-build or native qualification claims.
**Completion:** Portable semantics/scaling, full regression, installed native strict-BOM execution and landed platform CI qualify issue #84. The timing comparison remains a source-BOM operation measurement, not a whole-build speedup or SDK/package/release admission.

The first full attempt retained 1,427 completed checks and no recorded failure,
then was deliberately interrupted for host overload: twelve outer test workers
plus nested builds saturated the twelve-core host. Its logs/checkpoint remain;
it is not a passing full gate. A fresh complete run now uses four outer workers,
rather than treating resumed partial coverage as release qualification.

### [x] RETAINED-USER-001 — Bind secondary test identities to scoped workspace access

**GitHub issue:** [#85](https://github.com/jordanhubbard/literate-ai/issues/85).

**Additional GitHub issue:** [#94](https://github.com/jordanhubbard/literate-ai/issues/94), private allocation-prefix search delegation. Existing #85 remains the scoped identity/custody owner.

- **Priority:** P1
- **Owner:** Retained execution profile and workspace custody
- **Direction:** Execute complete original test suites with their privileged and explicitly unprivileged user requirements.
- **Conclusion:** Native run and output directories are private mode 0700; selecting a secondary account alone cannot execute captured test programs through them. Preserve private defaults and add reviewed worker/profile-bound resource grants, current UID/GID observations and permission custody. GitHub issue: https://github.com/jordanhubbard/literate-ai/issues/85
- **Depends on:** RETAINED-PROJECT-001 and FREEBSD-001
- **Implementation:**
  - [x] Add a strict numeric secondary identity and read-only POSIX currentness adapter. Nine focused controller checks pass, covering forward/reverse aliases, group and observation drift, unsupported platforms and actual local lookup. A source-level disposable FreeBSD probe also passes the exact UID/GID 2001 lookup, eight checks and one root-account skip, preserving both accounts. This prerequisite does not grant workspace access.
  - [x] Add the FreeBSD POSIX ACL descriptor backend: preserve exact original access/default ACLs, reject permission drift, hardlinks and foreign owners, and never restore through a reused descriptor onto another inode. Shared-mask widening clamps existing entries to their previous effective permissions. Fourteen focused checks select 13 passes and one unsupported-platform skip on the enabled disposable guest; five portable checks pass on the controller, with nine native skips. A separate 27-check native probe passes.
  - [x] Bind exact traversal/read/execute/fixture-write scope through existing workspace and provisioning owners; refuse mutable identity and permission drift without broad chmod or silent account creation.
  - [x] Close the private allocation-prefix ingress gap from installed original execution (#94). Preserve the preceding 22/24 failure, Kyua database, CAS output and successful mount cleanup. Scoped named-user search protects unrelated siblings, refuses inaccessible outside ancestors and restores exact permissions. Installed `6e370033` now passes all 24 original cases without skips, including both previously denied launchers, and admits the retained local-runtime result after independent acceptance and cleanup. Canonical SDK, pkg and release qualification remain separate.
    Native source-level renewal also passes all 16 read-only-view and secondary-receipt checks with no skips, including real identity-drop access, private sibling refusal, inaccessible external ancestors, permission drift and exact ACL restoration. This protocol-peer fixture is distinct from the installed run on an actually supervised allocation.
  - [x] Implement the separate FreeBSD read-only view owner with canonical disjoint backing paths, manifest alias binding, actual mount flags, vnode identity, fresh fixtures and private-root restoration before unmounting. Ten native source-level checks pass with no skips, covering writable mounts, busy cleanup, account/source/root drift, unrelated new children, actual secondary-user operations and exact normal/exception cleanup. Inspector qualification and installed workspace/receipt integration remain open.
  - [x] Integrate lower-level workspace command scoping: verify allocation/parent before capture, reserve named view/fixture arguments, mount sealed exports after build and activate/revoke only eligible test commands. Failed constructors retain private backing trees. Cleanup-bound completion/receipt retention and operator-private local orchestration are now implemented; this does not qualify the installed feature.
  - [x] Bind optional exact worker/account/test actions, read-only input/export view prefixes and fresh fixture names into profile/plan identity. Preserve absent-field serialization; reject overlapping prefixes, namespace collisions, unproduced exports and aliases escaping the selected manifest view. Twelve focused policy checks pass. The workspace requires a typed live allocation and enforcing view owner. Local orchestration resolves operator-private authority before platform/cache effects and creates sessions under its inspected prefix.
  - [x] Add a separate optional operator-local provisioning inspector and live allocation owner. Fresh nonce-bound process calls retain exact worker/plan/policy observations; instance, prefix, lifetime, configuration or process failures permanently revoke the owner. Eleven focused protocol/schema checks pass, alongside three existing provisioning smoke checks. These fixtures are not actual native allocation qualification; workspace/view/receipt integration remains open.
- **Evidence:**
  - [x] Identity prerequisite regression: 1,874 passed, 42 skipped, no failures across 1,916 selected checks in 1,039.060 seconds. Report SHA-256 `329a5fec37f5a6d95313b2093a2f5df771c0d405f9081abf46489199e0224ac9`. This does not implement scoped grants or qualify the complete feature.
  - [x] Descriptor-backend full regression: 1,879 passed, 51 skipped, no failures across 1,930 selected checks in 1,015.463 seconds. Report SHA-256 `62f6a447e2018599605fce03c90bb3e4a4478811e86b63d7ff0cc18dab514da0`; log SHA-256 `70945fe918b96527b1eb0a83239d6570f8e32636abbc499da4a5e7c8715fbb1d`. Native focused checks and the 24-case original-suite backend probe remain source-level evidence.
  - [x] Policy-stage retained regression: 277 passed, 11 skipped, no failures across 288 selected checks in 219.171 seconds. This precedes the inspection owner and does not qualify installed scope or lifecycle integration.
  - [x] Policy/inspection retained regression: 288 passed, 11 skipped, no failures across 299 selected checks in 228.360 seconds. Report SHA-256 `83b19103b7a36d1452cdd31a953889c3217cdfdae9500a67ae0415196ca3ad95`. The 11 focused protocol/schema checks and three existing provisioning smoke checks also pass. Actual allocation, views and installed lifecycle remain unqualified; this is not the complete framework regression or a current lifecycle receipt.
  - [x] Native view-owner source tests pass all ten checks in 39.395 seconds. Module SHA-256 `7bd56c8b67c2a580b8303626962fc6afe5c13cea7f55128adba5f6156d375cc6`; test SHA-256 `3d0dfbfc6b7bc71769ee3c65387ad766dcab290a570175b0580e7b4fb4a0cc8f`. Post-test audit confirms no remaining nullfs mounts and unchanged test-account IDs. The allocation inspector is an explicit protocol fixture. An earlier seven-check run failed because `statvfs().f_fsid` returned zero for both filesystems; its six mounts were recovered with private roots and unchanged source bytes. Failed logs are retained.
  - [x] View-owner retained regression: 290 passed, 19 skipped, no failures across 309 selected checks in 301.541 seconds. Report SHA-256 `1b3681f467be09aacab04ca534b5c7f1238bb34511c68e20e9d9e0328ab5e895`; log SHA-256 `c7f18f7f811291e76bedfe2e177c4bcb7a30504450244dcdcae90c2d2f70679e`. This is source-backend evidence; installed execution and actual provisioning remain open.
  - [x] Command-workspace retained regression: 297 passed, 20 skipped, no failures across 317 selected checks in 263.107 seconds. Report SHA-256 `6c68fa603b23d1eb13bd8f61f0c1f51842307426bc3b0aa9deb0932943ed21fe`. Constructor failure retention and revocation failure after a successful command are covered. Installed execution, actual provisioner qualification and receipts remain open.
  - [x] Native command-workspace source test: one pass, no skips in 224.210 seconds, including real secondary reads, private-input denial, fixture writes/removal and root read-only refusal. Execution module SHA-256 `180648f4190b657eec794f69001e1a8294fded43a71b222f51ccbd833c526ebf`; test SHA-256 `acf64e40eb712a0bbf85e9150907fa540e89c0e9c0941e9009c0ec5acc361338`; log SHA-256 `9530e5680a64d76c4867cb516a076a1680f4bf187991fbf73bddcf1e51d46c64`. Final audit confirms zero nullfs mounts and unchanged account IDs. The inspector remains a protocol fixture. The prior 11-case native run retained ten passes and one command error; its fixture used mode 0700 for the delegated export directory, corrected to explicit 0755. This does not run the original source suite or qualify an installed lifecycle.
  - [x] Bind canonical secondary cleanup facts into completed-run identity after retaining live inputs/exports/observations. Exact plan/account/worker/commands, manifest mounts, activation/revocation history and fresh inspections are checked; failed retention and cleanup close resources and issue no admission. Add operator-private inspector selection, allocated-session routing and available failure diagnostics to local orchestration. Fifteen receipt, six evidence and 21 orchestration checks pass.
  - [x] Combined retained regression: 311 passed, 21 skipped, no failures across 332 selected in 271.326 seconds. Report SHA-256 `1d0821dbc8f22d61026d6f71b99058fcce8f0ea12b3e31e3ab40b943c20608c4`. This includes the CLI bridge but is not the full framework suite or installed qualification.
  - [x] Native source-level receipt fixture: one pass, no skips in 760.742 seconds, including secondary operations, independent acceptance, cleanup-bound admission and materialized payload use after run retirement. Final audit confirms no nullfs mounts and unchanged account IDs. This exercises execution/admission owners with a protocol-peer inspector; installed CLI, actual provisioning and the original suite remain open. The initial attempt failed during import because the native Python lacked `_sqlite3`; no lifecycle commands ran. That log remains retained.
  - [x] Final retained regression after late-account currentness checks: 312 passed, 21 skipped, no failures across 333 selected in 275.180 seconds. Report SHA-256 `22d1aa2c05a193ae2f3862004410a374b4a7ee199c8b56039557e98ad11b8b93`. The exact account is checked after private content/dependency verification and cleanup; late drift prevents admission. The earlier 760.742-second native pass predates this last check. The renewed local-orchestration fixture and ten view-owner checks all pass without skips in 797.989 seconds; final audit finds no nullfs mounts and unchanged account IDs. Native log SHA-256 `6ce8039d4aa231c08cede6950531c618255b2ab4882141ba52ed46775bb00ddf`. This uses an explicit inspector protocol fixture; installed/public CLI, actual provisioning and the original suite remain open.
  - [x] Connect the source-level allocation owner to the actual supervised QEMU guest through a private SSH-forwarded socket. Two fresh inspections bind the reviewed fixture context to the same live process chain and attached overlay/seed; an insufficient lifetime refuses and permanently revokes the owner. Probe record SHA-256 `f6f6b104cd7ab7641972d350e3dbe41a0e924a50aa5e0e9207c6cd1ef36d9f78`. This bounded operator probe does not execute a retained lifecycle, qualify a reusable provisioner or admit an SDK. Its socket and guest configuration are removed after completion.
  - [x] Repair the v2 catalog index to register both allocation-inspection schema resources. The first full regression stopped at this mismatch after 549 tests; preserve that failure. Five evidence-record and frozen-v1-schema checks pass after the repair. Full regression remains open until its checkpointed runner completes.
  - [x] Review the changed authority and user documentation, correct the earlier inspection-only development description and record the current documentation authority marker. The next full-check attempt reused 546 passes and ran 866 tests before its stale documentation marker stopped project self-description validation. Retain that failure; the documentation repair left the trusted-driver pin unchanged at that checkpoint.
  - [x] Complete an explicit author review of all fifteen changed trusted-driver files, including optional wire compatibility, operator credentials/configuration, allocation freshness, mounts/ACLs, command scope, cleanup-bound admission and SQLite realization. Author-review report SHA-256 `c415083f88581049452164df5dedf4b86c34fbf84c708b99ac082ec8fb0ffb34`; no blocking finding is recorded. This is not an independent review or production-security attestation. Renew the reviewed implementation pin separately from runtime qualification.
  - [x] Complete the repaired full-suite coverage: 1,928 passed, 61 skipped, no failures across 1,989 selected. The final repair attempt ran 581 cases in 323.282 seconds and reused 1,408 earlier passes. The runner correctly exits 2 for repaired coverage and resets progress; a fresh complete run remains required for a passing full gate.
  - [x] Complete a fresh full framework run after the authority repairs: 1,928 passed, 61 skipped, no failures across 1,989 selected in 1,149.784 seconds. Report SHA-256 `ad7792ac49072c67f1429f4020cbb37133eddbe9e07446df3cd1de2001444b86`. Wheel packaging and the local fast gates pass. This does not qualify the installed native lifecycle.
  - [x] Reproduce the hosted Python 3.11 FreeBSD host-install fixture failure locally, then model Python 3.12 explicitly in the simulated native host. Nine focused checks pass on both Python 3.11 and 3.14, including rejection of Python 3.11 even when package registration and the SQLite query succeed. Production probing and the declared version requirement remain unchanged; renewed full-suite and hosted CI confirmation remain open.
  - [x] Complete scope/currentness refusal fixtures plus real privileged and unprivileged original cases through the installed framework in a disposable native guest; preserve legacy identities and private defaults. Installed `6e370033` completes in 1,717.496 seconds with 24 original passes, no skips, and 11 independent observations matching declared exits and stream hashes. One invalid-input case correctly expects exit 1. All 34 retained records reverify; cleanup is bound into completion, the prefix ACL is root-only and no nullfs mounts remain. Fifty-one fresh observations bind the same actual allocation. Receipt identity `sha256:924264d401159e317059b69c80087ec3a9cd047ca4652a53ca7903fa6c29f559` is admitted for local runtime use; canonical Standard lifecycle, SDK, pkg and release flags remain false.
  - [x] Complete exact-current required CI and land the reviewed integration. Landed `ef5db15f` exact-main CI [40007862532](https://github.com/jordanhubbard/literate-ai/actions/runs/40007862532) passes all 26 jobs. Seven scoped identity/ACL/view/prefix owner and contract files, plus `_DirectoryAccess`, are byte-identical to installed native `6e370033`; the actual 24-case original-suite and cleanup-bound acceptance remain recorded in `verification/native-retained-renewal-development.json`. This closes issues #85/#94 only, not the broader FreeBSD or canonical Standard/SDK program.

### [x] HOST-RUNTIME-001 — Preserve executable private runtimes with standalone POSIX Python

- **GitHub issue:** [#91](https://github.com/jordanhubbard/literate-ai/issues/91)
- **Priority:** P1
- **Owner:** Standalone worker bootstrap, stage-zero source installer and installed CLI fixtures
- **Direction:** Keep the installed build entrypoint usable on supported Python distributions.
- **Conclusion:** Copied standalone macOS Python 3.11 executables abort at launch because their relative libpython linkage is lost. Retain the base library in the private runtime before pip bootstrap. Keep the executable inside installation custody, preserving self-update containment, Windows environment behavior and orphaned-base detection. A symlink-only candidate starts Python but fails the existing self-update custody check; preserve that failure and retain the copied-executable contract.
- **Depends on:** none
- **Implementation:**
  - [x] Canonicalize the POSIX base interpreter before recording its private-runtime home; preserve copied executable custody and native Windows behavior. A fresh public prefix install through a real Python 3.14 alias fails before ensurepip because its home points to the alias directory.
  - [x] Share copied-runtime creation with the standalone bootstrap owner, source installer, wheelhouse downloader, offline worker installation and wheel smoke. Preserve the bootstrap file's standard-library-only staging contract. Eleven bootstrap checks pass on the affected Python 3.11 runtime in 6.841 seconds, including staging the single file outside the checkout and creating a working private Python/pip under isolated `-I -S` startup. The second full run preserved a further downloader failure after 1,442 executed tests (61 skipped); it exposed the remaining direct creation paths, now consolidated.
  - [x] Centralize private-runtime creation and use the production owner in the real-prefix update fixture. Standalone non-framework shared macOS Python retains its base `libpython` beside the copied executable before pip bootstrap. Other platforms keep their preceding creation behavior; self-update containment is unchanged.
- **Evidence:**
  - [x] Retain the failed real-alias install, prove Python/pip through the same alias with the production owner, and renew real-wheel self-update and public prefix installation.
  - [x] Pass offline wheelhouse export/tamper refusal and standalone offline bootstrap under the affected interpreter, in addition to source installation and self-update. All eleven bootstrap checks pass again in the complete Python 3.11 regression.
  - [x] The shared owner passes eleven bootstrap checks on Python 3.14 in 5.480 seconds and three source-installer checks on Python 3.11 in 2.645 seconds. Real-wheel self-update and original-command reexecution pass all three checks on Python 3.11 and 3.14 in 3.931 and 3.575 seconds. These are focused checks; the renewed full framework and installed-wheel gates remain required.
  - [x] Review the shared bootstrap change explicitly and renew its trusted-driver pin. Author-review report SHA-256 `de394586676a8d7267c93466a2a59c43a72e47d14766d35b3d740a074c635629`; no blocking finding is recorded. This is an author review, not an independent security attestation. Exact wheel/dependency verification, pip arguments, process deadlines, cleanup, wire identities and admission rules are unchanged. New driver identity: `ecd6f7320cd8f6da0056406dea80165e4e31d753085bfba00c79a1d884f260c0`.
  - [x] The managed Python 3.11 suite reproduces the original native loader abort after 1,291 tests (57 skips); the macOS crash report identifies missing executable-relative `libpython3.11.dylib`. After the repair, three installer checks pass in 3.789 seconds and three build-identity/real-wheel self-update checks pass in 5.599 seconds. The same groups pass on Python 3.14 in 2.899 and 4.227 seconds. These checks use real private environments, Python, pip, wheels and launcher reexecution. The earlier symlink-only experiment passed startup but failed the unchanged enrollment containment check and was replaced.
  - [x] Run Python and pip from an actual new private runtime under the affected Python 3.11 distribution and pass real-wheel self-update. The fresh full Python 3.11 gate exits zero in 1,021.195 seconds with four workers; its report records 1,910 passed, 81 skipped and zero failures across 1,991 selected cases. Report SHA-256 `d770be5e04081dfe8fa59374a3e3b6a9b988b2390347f6dbe459ab3cd466d24d`; log SHA-256 `13969000d45edfbf9443089b50f1f25ee7e119032c62c85527b409d175989617`. This is a complete unit regression with explicit platform/dependency skips, not release or native FreeBSD acceptance.
  - [x] Qualify the exact committed wheel and pass the hosted platform matrix before closing this item. The complete installed-wheel gate at `1063ecd8` passes 131 spans; its runtime/bootstrap/self-update owners are byte-identical to landed `ef5db15f`. Exact-main CI [40007862532](https://github.com/jordanhubbard/literate-ai/actions/runs/40007862532) succeeds in all 26 jobs, including all macOS Python 3.11 shards and Windows platform cells.

- **Completion:** Issue #91 is qualified by the actual affected-interpreter checks, exact installed wheel, combined lifecycle and successful landed platform matrix. This closes the private-runtime repair only; native retained SDK and performance issues remain separately open.

- **Alias repair qualification:** At implementation `625b871d`, the real-alias regression passes after failing against the preceding owner. All 18 installer/bootstrap/self-update checks pass on the affected macOS standalone Python 3.11 distribution. The public make-install prefix succeeds as a non-editable installation; the fresh full source suite passes 2139 tests with 71 explicit skips and no failures (2210 selected). See `verification/private-runtime-alias-development.json`. A fresh combined lifecycle and exact package/native/CI renewal remain required; the preceding Windows-only receipt is preserved under its own authority identity.

- **Fresh combined lifecycle:** The force-generated complete framework lifecycle at authority commit `885352ad` passes all 233 cases with no failures/skips. Supported receipt update/check/require-current and verify pass. Receipt `sha256:35189b34504770136936cd41bbc7421a01a8681550ecde0eed5cb70a4ec8a5e5`; finalized candidate `sha256:e760890282ba6aaf3f9603909a06b314ea860549624c1b321d80025ba0ae5bab`; driver `sha256:ceb559c1eaa79ce4db8210a6acd34ccf7ecbf19ad0651092e8aacb105bcd7578`. This renews the integrated alias/Windows source under its actual authority and preserves the older Windows-only receipt separately.


- **Installed-wheel renewal:** Exact source `1063ecd8` passes the complete official wheel smoke runner: 131 timing spans succeed, with evidence ledger state passed and wheel `sha256:3e6f9f8896d7cf66261d190302f899cedbc13cc6995bd115a88df7816165d6eb`. Current framework receipt remains 233 passes and verify has no failing gates. Source-full regression and Python 3.11 alias/runtime regressions are recorded in `verification/private-runtime-alias-development.json`; hosted CI and reviewed landing remain required.

### [x] REBUILD-ENTRY-001 — Normalize or safely reject Component file entry points in Standard rebuild

- **Priority:** P1
- **Owner:** framework rebuild CLI
- **GitHub issue:** [#75](https://github.com/jordanhubbard/literate-ai/issues/75)
- **Current release target:** 1.3.0
- **Direction:** Resolve the installed-wheel native-library defect without weakening authority or acceptance.
- **Conclusion:** An installed-wheel native journey exposed an uncaught authority-reader exception for a Component file argument. Normalize supported file entry points or report a bounded CLI error before provider invocation; preserve project and symlink boundaries.
- **Depends on:** none
- **Outcome:** The implementation is already landed in the reviewed main integration; fresh installed native acceptance is renewed below.
- **Implementation:**
  - [x] Resolve the documented Component entry point before locked authority loading and normalize invalid-input diagnostics.
- **Evidence:**
  - [x] Pass full exact-head hosted CI and land the reviewed combined change.
  - [x] Installed-wheel file and directory cases, unsafe paths and no provider invocation on invalid input.

- **Local evidence:** The full unchanged production-source suite passes: 1,580 selected, 1,545 passed, 35 skips and no failures in 779.102 seconds. Eight focused CLI tests cover file/directory equivalence, lexical symlink refusals (including relative paths), unavailable/outside/unrelated inputs and a real missing-Component authority error before lifecycle assembly. The missing-authority assertion is strengthened after the full run and rerun in the focused group. Static/export/style checks, strict specifications, current driver/runner/documentation reviews, 21 Node tests and all 121 Mermaid diagrams pass. The subsequent combined acceptance is recorded below; hosted CI and landing remain open.

- **Installed native file-input evidence:** Noneditable implementation `a46e5e3b8780f21184da6cd4fdb807351b61622a` passes the copied tiny-library `component.md` rebuild in 72.058 seconds after reviewed Standard rebind and documentation renewal. Its existing verifier-owned harness remains unchanged (`sha256:64c2a0fd2a118b406b4e340278bf2b8db7823bca290719ca0f140b1f49981b1b`), including isolated startup, module origin and expected value 7. Generated tests, independent acceptance, current three-test receipt and `verify` pass. This is a standalone copied-library check, separate from #48 registered-parent evidence, and it does not execute the #76 refusal case. Retained proof identity: `sha256:e2230e775cbf47ad5a70442ac6def65a3917b0336296d627d9feb3fb1d508e1d`. The combined installed qualification is recorded below.

- **Acceptance evidence:** Combined implementation `8746155526cecb46de83202fc26cd4733b13dd62` passes the full 1,582-case suite (1,547 passed, 35 skipped, no failures; 648.937 seconds), all 19 focused cases, the installed wheel (`sha256:456a7bea81cf93d42892eab9cfd1926f86642281e2a6c133f73d44258584eb93`), strict source/specification/review gates and all 121 diagrams. The installed CLI refuses the exact retained incompatible Bazel library profile before generation. A separate supported native profile rebuilds through its `component.md` path with the unchanged isolated, module-origin-checking oracle and expected value 7. Its current native receipt has 4 passing tests and `verify` passes. Installed API regressions also pass all eight entry-point and four profile cases. The fresh framework lifecycle receipt is current with 231 passing tests; candidate comparison and `verify` pass. Native proof custody: `sha256:4007c044d3fd7ed8c18bc4a7e451a5ec2812c0feb71074af7bb379cfa16b2e28`. This is one successful rebuild per temporary fixture, not regenerative qualification. Full hosted CI and landing remain open.

**Current integration renewal:** Merge the reviewed entry-point and library-profile implementations with current registered-child and retained-project qualification, preserving both sets of requirements and original native proofs. Earlier 1,582-case and installed two-wheel results remain historical. Run the combined current focused/full suite, native installed journey, fresh lifecycle receipt and exact review CI before landing this batch.

- **Fresh installed selection proof:** The real Standard directory and component.md forms select the same exact host lock; read-only typed-return tracing and unmodified public CLI calls agree. Accepted-only mode deliberately stops at `source_cache.runtime_absent` after lock selection. All five invalid path cases return their precise bounded JSON error with unchanged project trees and no runtime/candidate/build/object roots. No product function or guard is replaced. This proves input selection/refusal; the separate full native library journey is being renewed before closure.

- **Closure qualification:** The fresh non-editable installed CLI completes a force-generated source-derived tiny Python library through its component.md path in 78.522 seconds. Its explicit import map, isolated/module-origin-checking oracle and expected value 7 are unchanged (harness `sha256:64c2a0fd2a118b406b4e340278bf2b8db7823bca290719ca0f140b1f49981b1b`). Generated tests, import execution and independent acceptance pass; the current receipt has 3 passes, no failures/skips, and verify passes. The exact retained default Bazel profile refuses with its actionable profile error before any coding-CLI launch, with no candidate and only an empty owned runtime allocation. All four cross-platform projection regressions and the complete 2139-pass source suite pass. Directory/file selection and all five pre-artifact invalid-entry refusals are separately recorded. Relevant implementation files match landed `a6a22996`; exact review CI `39790990072` passed before its main integration. See `verification/installed-native-profile-acceptance.json` and `verification/installed-lock-entrypoint-acceptance.json`. This closes the entry/profile contracts and does not claim broad regenerative equivalence or release admission.

### [x] LIBRARY-PROFILE-001 — Validate Python library build and export profiles before generation

- **Priority:** P1
- **Owner:** framework library profiles and generation preparation
- **GitHub issue:** [#76](https://github.com/jordanhubbard/literate-ai/issues/76)
- **Current release target:** 1.3.0
- **Direction:** Resolve the installed-wheel native-library defect without weakening authority or acceptance.
- **Conclusion:** The default promoted Bazel profile exports a file while library test preparation requires a directory, wasting generation retries. Reject unsupported profile combinations before generation or provide a supported directory export without weakening acceptance.
- **Depends on:** none
- **Outcome:** The implementation is already landed in the reviewed main integration; fresh installed native acceptance is renewed below.
- **Implementation:**
  - [x] Validate library artifact shape against the selected build profile before generation and provide actionable profile selection.
- **Evidence:**
  - [x] Pass full exact-head hosted CI and land the reviewed combined change.
  - [x] Default promotion profile and supported native Python profile through installed-wheel library acceptance; incompatible profiles refuse before provider invocation.

- **Local evidence:** The standalone profile implementation passes all 11 focused projection/CLI tests, including pre-discovery refusal of Bazel and Make file profiles on Linux, Windows and macOS, unchanged native directory exports and existing wheel-library acceptance. The full standalone suite passes 1,579 selected cases: 1,544 passed, 35 skipped and no failures in 703.524 seconds. Static/export/style, strict specifications, driver/runner/documentation reviews, all 121 diagrams and the pinned root skill evaluation pass. Exact production/test source slices are consolidated with the #75 entry-point fix; subsequent combined acceptance is recorded below, with hosted CI and landing still open.

- **Combined checkpoint:** All 19 focused entry-point/profile/qualification cases pass in 9.795 seconds. The combined source passes layout/export, strict lint/format, specifications and current driver/runner/documentation review. The source slices preserve both standalone implementations exactly. Combined local qualification is complete as recorded below; hosted CI and landing remain open.

- **Acceptance evidence:** The full combined evidence is recorded under REBUILD-ENTRY-001 immediately above. The installed CLI rejects the exact retained default Bazel library profile before generation and accepts the supported native directory profile through real generated tests and unchanged independent acceptance. All four installed profile tests pass across the declared Linux, Windows and macOS projections, including existing wheel behavior. The 1,582-case combined suite, package check and fresh current framework receipt pass; full hosted CI and landing remain open.
  - [x] Default promotion profile and supported native Python profile through installed-wheel library acceptance; incompatible profiles refuse before provider invocation.

- **Closure qualification:** The fresh non-editable installed CLI completes a force-generated source-derived tiny Python library through its component.md path in 78.522 seconds. Its explicit import map, isolated/module-origin-checking oracle and expected value 7 are unchanged (harness `sha256:64c2a0fd2a118b406b4e340278bf2b8db7823bca290719ca0f140b1f49981b1b`). Generated tests, import execution and independent acceptance pass; the current receipt has 3 passes, no failures/skips, and verify passes. The exact retained default Bazel profile refuses with its actionable profile error before any coding-CLI launch, with no candidate and only an empty owned runtime allocation. All four cross-platform projection regressions and the complete 2139-pass source suite pass. Directory/file selection and all five pre-artifact invalid-entry refusals are separately recorded. Relevant implementation files match landed `a6a22996`; exact review CI `39790990072` passed before its main integration. See `verification/installed-native-profile-acceptance.json` and `verification/installed-lock-entrypoint-acceptance.json`. This closes the entry/profile contracts and does not claim broad regenerative equivalence or release admission.

### [x] JAVASCRIPT-REGISTRY-LEX-001 — Distinguish bundle registries from inert writer text

**GitHub issue:** [#96](https://github.com/jordanhubbard/literate-ai/issues/96)

- **Priority:** P1
- **Owner:** Inert JavaScript lexical observation and generated-source handoff validation
- **Direction:** Complete lifecycle qualification without rejecting a valid bundle writer as its emitted executable.
- **Conclusion:** A controlled valid application and bundle are rejected when a writer string or leading inert registry text is added. Use the existing lexer for actual registry identifiers and source offsets, while preserving real-bundle module, local-extension, shebang and CLI-dispatch guards and independent execution/acceptance.
- **Depends on:** none
- **Implementation:**
  - [x] Reuse the existing inert lexical owner for bundle classification and registry location.
- **Evidence:**
  - [x] Pass valid-writer, leading-inert-text, real broken-bundle refusal and actual Node execution checks; renew full source regression, driver/document review, lifecycle/receipt, native/installed qualification and exact required CI.

**Focused results:** All six fanout checks pass on the host and Linux and in the actual FreeBSD preflight. All four JavaScript handoff/bundle cases and all three retry cases pass on the host, Windows, Linux and FreeBSD preflight. Complete native/installed and exact CI gates remain pending above.

**Closure audit:** All four current handoff cases pass without skips. A real non-editable installed guard on native Windows accepts all six inert forms in both writer locations, performs 12 actual Node invocations with exact expected test/smoke payloads, and preserves all four missing-module/extension/shebang/dispatch refusals. Its guard, lexer, callers and fixture bytes match landed `fe21a198`, exact fully qualified `76ac4c7a` and the complete installed wheel at `52c8b6eb`. That original snapshot also passes a fresh 230-case framework lifecycle. `verification/javascript-registry-acceptance.json` retains the source/wheel/receipt and hash-verified native archive identities; this does not declare the unrelated entrypoint or HTML-performance branches qualified.

### [x] ACCEPTED-RETAINED-EXPORT-001 — Export verifier-admitted retained source without a coding CLI

**GitHub issue:** [#97](https://github.com/jordanhubbard/literate-ai/issues/97)

- **Priority:** P1
- **Owner:** Accepted-source provider reconstruction
- **Direction:** Make accepted-source-only build consume a qualified retained source entry and export its artifact.
- **Conclusion:** Issue #97 reproduces an admitted retained origin being rejected by the coding-CLI provider allowlist. Preserve RetainedSourceSelection semantics with no executable or model claim; merely adding a provider spelling is insufficient. Recover the review only from verified Standard accepted-cache membership at the existing portable cache root. Reconstruct the same no-model/no-executable retained selection and require its canonical identity to equal the dispatched tool binding; carry the recovered review into the existing retained request/semantics namespace. Keep independent acceptance, origin/tree/tool bindings and unknown-provider refusal intact. This remains separate from the original-adoption work in PR #81.
- **Depends on:** RETAINED-PROJECT-001 and CACHE-RETIREMENT-001
- **Implementation:**
  - [x] Reconstruct accepted retained origins through their existing provider-neutral selection without invoking or inventing a coding CLI.
- **Evidence:**
  - [x] Admit a tiny real retained tree, publish its accepted cache entry, build from accepted source and export unchanged bytes/provenance after fresh independent acceptance; refuse unknown origins, missing admission, changed tree/review/tool bindings and stale acceptance.

**Admission gap found by the real fixture:** The planned keys now match, but the first complete retained lifecycle publishes full accepted cache membership, not the distinct verifier-owned source-admission evidence required by accepted-only execution. Keep that refusal intact. Extend canonical admission with explicit retained-origin evidence and no invented coding-agent transcript, mint it only from a live reviewed retained qualification with actual passing verifier facts, and retain it alongside the complete accepted membership in one exact cache entry. Old entries without admission must still refuse; reuse still rebuilds, retests and independently reaccepts.

- **Closure acceptance:** A real noneditable installed wheel (`sha256:0d2f0153c8b98afe2ac54e480ce4c4faaf35848deb1c5b027bbe69fc07bfa57f`, exact source `9f8b9dab`) initializes from landed main and admits a reviewed retained Python tree with no coding-agent executable on PATH. Three native behavior cases and independent acceptance pass, supported receipt promotion commits the result, and public accepted-only build exports exact hash-based compiled bytes with no model selector. Real changed-source authorization and failing native behavior refuse while preserving the prior receipt and export; ordinary generation still fails `coding_cli.unavailable`. Thirteen current critical cases and the real accepted-export fixture pass without skips; the latter observes a new actual acceptance identity and refuses unknown/substituted origins, missing admission, corrupted cache bytes and failed fresh acceptance. All 13 relevant owner/test files are byte-identical between the qualified wheel source and main `fe21a198`. See `verification/retained-source-installed-acceptance.json`; the separate hardware CI recurrence, full native SDK and product/package programs remain open.

### [x] CACHE-RETIREMENT-001 — Keep explicit retired cache history verifiable

**GitHub issue:** [#100](https://github.com/jordanhubbard/literate-ai/issues/100)

- **Priority:** P1
- **Owner:** Accepted source-cache membership
- **Direction:** Keep supported cache refresh usable without discarding immutable history.
- **Conclusion:** Issue #100 shows that deliberate retirement removes a key pointer while verified enumeration still demands it for the preserved immutable manifest. Record an exact key/entry retirement before pointer removal; recognize only that record as intentional history. Preserve refusal of unexplained missing pointers, corruption, unsafe paths and ambiguous active entries.
- **Depends on:** none
- **Implementation:**
  - [x] Persist exact retirement records and distinguish them from active membership during lookup and verified enumeration.
- **Evidence:**
  - [x] Prove current lookup and read-only enumeration after retirement, unchanged immutable history, missing/corrupt-record refusal, safe reactivation and portable archive restoration.
  - [x] Complete the combined fresh host suite, current framework lifecycle receipt, installed package qualification and exact review CI before landing.

**Current retained-export implementation evidence:** The real public CLI fixture passes live reviewed retained admission, accepted-only build/export with byte-identical hash-based Python output, a new independent acceptance identity, failed-fresh-acceptance refusal without changing the prior receipt/export, refusal of legacy complete entries without source admission, explicit fresh requalification upgrade, and tampered retained-cache byte refusal. Four admission/closed-wire cases, eight no-agent selection cases, the existing retained-cache guard and all three retirement cases pass. Existing model admission and the combined admission regression also pass. Fresh complete host, lifecycle, installed-wheel and exact review CI gates remain open.

**Combined-suite repair:** The first complete host run at `bb40b136` stopped after 310 passes, 29 existing skips and one error in the existing real command-generator regression. Ordinary cached generators may implement the supported adapter seam without a coding-provider selection object. Restrict retained lookup key reconstruction to an explicitly present typed retained selection; preserve ordinary planned keys. Retain that failed report and the deliberately interrupted prior lifecycle separately, merge the latest native fixture grant repair, and start fresh complete and lifecycle qualification after the focused real command receiver cases pass.

**Current-source qualification:** At `9941a6c4c1c4fe0e0e05c474135d204346041f79`,
the fresh complete host suite passes 1,827 cases with 42 declared skips across
1,869 selected cases. A new force-generated framework lifecycle completes
build, generated tests, execution and independent acceptance; supported receipt
update/check/current and `verify` pass with receipt
`sha256:31b15788308e9ed7cd762d0a5e230598f102465cedfe44cba00a2dbf8fc9fcad`
and finalized candidate
`sha256:48f264fb8f428cd814a0b7f876aaa1edca0ce135fc26138b0e053712431d5b08`.
Actual Windows qualification passes all 21 selected retained/admission/retirement,
ordinary command and public export cases without skips; independently collected
archive `sha256:65291999d77cad4917d0d05a1d2925a1271891914a21fcd7db23cc7b7248b1a4`.
The preceding `bb40b136` native FreeBSD 19-case proof remains separately bound
to its actual source, archive
`sha256:51c642d0e49cbd13ff929810b063e7f560c4dea2a47cf062b3b23f707caf0fef`.
The current-source native renewal has passed all 44 focused cases, including
ordinary command receivers and all four actual native package cases; its final
public export case remains in progress. Installed-wheel and exact final review
CI qualification remain required. The earlier invalid generated candidates and
interrupted launchers are retained as unsuccessful attempts; no acceptance
oracle was relaxed to obtain the fresh successful lifecycle.

**Closure audit:** All 11 current cache cases pass with no skips, including all three retirement cases. Every cache-package source file, source-materialization/archive guard and retirement regression is byte-identical across native/lifecycle-qualified `9941a6c4`, exact CI-qualified `20508324`, installed wheel `1063ecd8` and landed main `d5c7b278`. `verification/cache-retirement-acceptance.json` records each criterion and original qualification scope; no broader SDK or release acceptance is inferred.

### [x] SWIFT-ENTRYPOINT-001 — Align Swift generation and native single-executable compilation

- **GitHub issue:** [#104](https://github.com/jordanhubbard/literate-ai/issues/104)
- **Current release target:** 1.3.0

- **Priority:** P1
- **Owner:** Swift generation skill and native build contract
- **Direction:** Repair the Swift lifecycle failure blocking 1.3 qualification.
- **Conclusion:** Require one top-level main.swift dispatcher, declaration-only Swift support files and compilation of the same complete source set as the native builder. Keep native build refusal and all acceptance requirements.
- **Depends on:** none
- **Implementation:**
  - [x] Update the owning generation guidance and shipped template, preserve exact versioned skill references and record issue104.
- **Evidence:**
  - [x] Pass actual Swift compilation and execution including support/tests, competing-entrypoint rejection, skill/template checks, a fresh current lifecycle and required CI.

**Swift repair development evidence:** Skill version 1.0.7 and both authored/shipped Flavor contracts require the native builder's complete single-executable source set. Two actual Swift compiler tests pass, including three conflicting-entrypoint refusal variants and successful support/test linkage and execution. Ten skill/template tests, SkillEvaluator, lint/format, strict OpenSpec and supported authority reviews pass. A fresh live macOS LaunchAgent sample succeeds on the first generation attempt (one source-cache miss): 3 generated tests, 3 independent verifier tests and 2 assertions, with 6 invocations. The earlier exhausted three-candidate attempt remains retained. A current complete project lifecycle receipt, installed wheel and exact-head CI remain required before landing.

**Current Swift-repaired integration lifecycle:** At implementation `595da5b25931eaf5bfa94977512596b7eccd7570`, the complete project lifecycle passes. Supported receipt update/check/require-current and `litai verify` pass with 230 tests, no failures or skips. Current receipt: `sha256:40585141e6ec627f44b1573bf8ca10868ffd945f0938dc59455feeb4f241d5b0`; finalized candidate: `sha256:37c2663be538e67fadd94d5ce8f760c66209608e2c04e05c8b2bd142b40bb759`; driver: `sha256:5d1b8a0f8f67ac284a33b72af22ab8cff9de19b7ddbacf42c0978a7f4be905b6`. This run revalidates eligible admitted source through the complete current lifecycle; the separately recorded Swift sample was freshly generated. Final package/native renewal and exact-head CI remain open.

**Closure audit:** All three current real-Swift tests pass without skips, including support/generated-test linkage, direct compiler alias execution and three competing-entrypoint refusals. Version 1.0.7 authored/shipped guidance and Flavor contracts match their actual qualified wheel bytes. The guide remains identical to the separately recorded fresh Swift generation; current owner/test bytes match landed main and exact CI-qualified `20508324`. A forced-fresh framework lifecycle at `52c8b6eb` passes 230 tests and its complete installed wheel passes all 131 timing spans. `verification/swift-single-executable-acceptance.json` retains each original source/receipt/wheel boundary; the unrelated entrypoint-audit final full run remains pending.

### [x] WORKTREE-CONSOLIDATION-001 — Consolidate reviewed worktrees and superseded pull requests

- **Priority:** P1
- **Owner:** Repository worktree and review inventory
- **Direction:** Consolidate existing worktrees and PRs while retaining unfinished work and qualification evidence.
- **Conclusion:** Retain independent review scopes and their full Git histories. Close only reviews whose exact heads are ancestors of retained integration reviews; archive ignored state before retiring clean inactive checkouts. Do not merge failing or pending candidates or bypass branch garbage-collection policy.
- **Depends on:** none
- **Implementation:**
  - [x] Inventory exact review heads, local commits, active checkouts and ignored state.
  - [x] Retire redundant clean inactive worktrees after preserving ignored state and proving every head remains reachable.
  - [x] Close superseded reviews with explicit links to retained integration reviews; preserve unique review and branch scope.
- **Evidence:**
  - [x] Revalidate worktree status and ref reachability immediately before removal; retain a local migration journal.
  - [x] Verify final worktree inventory, open review inventory and untouched unique branch heads.

**Consolidation evidence:** The operator-authorized pass reduced 27 registered
worktrees to four: the main checkout and the integration checkouts for #105,
#110 and #82. All 23 retired worktrees were clean and inactive; their exact
heads remain reachable through unchanged local branches. All 893 ignored paths
were preserved by same-volume rename, with device/inode identity rechecked after
retirement. The local migration journal SHA-256 is `f1c221b37977b11cc01e931c8ad6849b91597f0e7f7bfbf5c0dfa0f2f4eacb9e`;
its ignored archive remains under the repository build output. No branch was
deleted, and the policy-driven garbage-collection plan admitted no candidates.

Closed #77, #78, #81, #89 and #99 into #105, and #87, #108 and #109 into #110.
Each closed review's exact remote head was verified as a Git ancestor of its
retained integration review immediately before closure. Branches and review
history remain available. #82 retains five additional merge/evidence commits
outside the combined #105/#110 ancestry and therefore remains open. Unique local
heads `bf4ee21e`, `fb35e56d`, `51291de9` and `491bc807` remain unchanged on their
original branches; retirement of their checkouts is not a completion claim.

At that pass, remaining review scopes were #105 (retained lifecycle/runtime integration), #110
(native SDK public execution, including #109/#108/#87), #82 (public execution
merge/evidence history), #112 (qualified-library recertification) and #106
(setup-bazel action update). #105's prior exact-head Linux run fails in the
Swift builder integration test. #110/#112 still have queued macOS CI. #106 is
green but retains its existing sequencing after #105. None was merged by this
maintenance pass. Worker alignment refused the configured template with
`worker_alignment.invalid`; no user-worker qualification jobs were dispatched
or worker configuration repaired. This operational audit does not close WORKTREE-002's
reusable migration-contract or platform-qualification obligations.

- **Windows review consolidation:** PR119 exact head `1a4d3e6e` is an ancestor of retained PR127 head `62ce16a0`; the latter has a complete green hosted matrix and fresh host qualification. Close PR119 as superseded while preserving its branch, histories and all issue116 native/landing gates. PR122 and PR124 remain retained: their optional-import and timing runtime/test slices match the accepted #127 source, but their exact receipt-bearing heads were deliberately not merged. Their final disposition follows complete qualification of the consolidated successor. No source contribution is represented as landed by this review closure.

- **Landed review disposition:** PR128 exact head `76ac4c7a` passes its normal CI and complete platform matrix `39936620110` (one retained hardware expiry, followed by only that failed shard retry). It merges as `fe21a198`, and local main fast-forwards cleanly. GitHub recognizes PR127 through ancestry, associating existing integration merge `874da1ba`. PR122 and PR124 close as superseded after exact contributed source/test/documentation byte comparison to landed main; their historical heads and receipts remain retained. Two further clean inactive checkouts retire after process/container checks, with all ignored state and Git metadata preserved by verified same-volume rename and every ref unchanged. Nine checkouts remain. See `verification/review-consolidation-landing.json`; exact-main CI `39948443185` and #129 native performance renewal remain separate pending gates.


- **Additional inactive checkout retirement:** Two clean, redundant checkouts are retired after process/open-file and container-mount checks. Their exact branch heads and all other Git refs remain unchanged; ignored files move by verified same-volume rename and per-worktree Git metadata is retained. See `verification/worktree-consolidation-followup.json` for the journal identity and observation limits. Ten checkouts remain, including active controllers and unfinished reviews. This manual operation does not satisfy WORKTREE-002 automation; moved environments need path reconfiguration before reuse.

### [x] ENTRYPOINT-AUDIT-001 — Audit original-source agent entry points

**GitHub issue:** [#113](https://github.com/jordanhubbard/literate-ai/issues/113).

- **Priority:** P1
- **Owner:** Agent onboarding and original-source adoption
- **Direction:** Reconcile open GitHub issue #113: report missing or stale agent delegates on authored projects.
- **Conclusion:** Preserve metadata-only adoption and custom instructions. Use the issue-authorized read-only audit plus explicit authoring-requirement route: report missing/stale/unsafe owned delegates against the declared agent_skill, expose readiness in original-adoption planning/apply results, and require reviewed authored repair before onboarding is described as complete. The audit never writes agent files, pinned parents or retained snapshots; it does not grant lifecycle admission.
- **Depends on:** none
- **Implementation:**
  - [x] Add supported read-only entry-point auditing and an explicit reviewed authoring requirement without modifying pinned parents or retained evidence.
- **Evidence:**
  - [x] Cover initialization, original adoption, nested projects, custom skill paths, custom shims and unsafe paths.
  - [x] Complete exact review CI and reviewed landing with current qualification.

- **Completion:** Exact review head `a5609e1e` passes ordinary CI `39971938723` and all 26 cells in full comparison CI `39971961215`. PR #130 is merged at `9d62ce09`; the primary checkout is clean and synchronized, and supported receipt require-current plus all-gate verify pass. The source suite, lifecycle and real noneditable CLI acceptance below retain their exact scope. This completes onboarding discovery only; #116 and #129 remain open, and no native lifecycle/product/release acceptance follows.

- **Custom-path authority:** Current v2 definitions admit bounded portable relative onboarding paths through the shared canonical path owner; optional shim validation follows the declared field. Published v1 schema inputs retain the root SKILL.md rule before legacy conversion. Custom-path provider metadata must name the file explicitly. Positive configured projects and original-adoption planning, default-delegate staleness, cross-platform path refusal and frozen-v1 compatibility are covered; no automatic instruction repair or lifecycle admission is added.

- **Focused development qualification:** 22 audit cases, 12 original-adoption cases and three documentation-graph cases pass with no skips or failures on the controller; two schema-catalog checks also pass. Positive custom-path original planning/apply preserves source and authored delegates after the required documentation review. V1 root-only parsing, cross-platform path refusals, owned/absorbed/nested slots, empty/comment-only references, reparse/symlink refusal and self-only documentation-spine refusal remain tested. Skill admission passes. See `verification/agent-entrypoint-development.json`; complete qualification remains open.

- **Retained full-suite refusal:** Frozen source `af620be3` retains 12 passes, 23 skips and one error from 2,235 selected cases at clean two-replay self-replication because the new yaml import is absent from the package manifest/source BOM. Declare the exact runtime PyYAML dependency, retain the failed attempt, qualify replication again, then start a fresh complete run; dependency admission remains enforced.

- **Parser resource follow-up:** A 379-byte valid YAML merge-alias graph expands to 4,096 mapping pairs with ordinary SafeLoader. The byte limit alone does not bound that work. Before landing, bound composed nodes and depth, permit scalar aliases only, and refuse shared container aliases in both onboarding frontmatter and provider pointers. Preserve every input byte and report the existing typed invalid finding. The pre-hardening snapshot `9f8b9dab` passed all 2,235 selected source cases (2,164 pass, 71 explicit skips), its 230-case lifecycle and complete 131-span installed-wheel gate; these facts do not qualify the upcoming parser change.

- **Final installed public CLI acceptance:** Exact qualified wheel `1e848368` passes all nine public discovery cases plus real YAML container-alias, onboarding alias, depth and node-limit refusals. Scalar aliases remain ready; every audit preserves exact file bytes and mtimes, and authored inputs restore ready. Installed module bytes match the reviewed source. See `verification/agent-entrypoint-installed-final-acceptance.json`; no lifecycle admission is asserted by the discovery command.

### [x] UPDATE-CLOSURE-001 — Check prospective update scaffold dependency closure

**GitHub issue:** [#88](https://github.com/jordanhubbard/literate-ai/issues/88).

- **Priority:** P1
- **Owner:** Project update planning
- **Direction:** Reconcile open GitHub issue #88: newer installed scaffold additions must not mix incompatible pins into older parent catalogs.
- **Conclusion:** Compare the complete prospective closure before apply, retain explicit parent selection and overlays, and offer a safe compatible subset.
- **Depends on:** none
- **Implementation:**
  - [x] Align plan/apply compatibility diagnostics and preserve atomic rollback for incompatible additions.
- **Evidence:**
  - [x] Older pinned parent plus newer installed scaffold fixtures cover mismatched dependencies, safe subsets and destination preservation.
  - [x] Required review CI, landing and exact-main confirmation pass: PR #131, review run `39990970425`, merged main `ef5db15f`, and all 26 exact-main jobs in `40007862532`.

- **Implementation:** Planning now projects exact current, inherited and selected framework skill bytes before apply. It reuses canonical dependency validation, binds incompatibility diagnostics to the plan and excludes incompatible additions from the safe subset. Parent selectors, overlays, currentness checks and atomic rollback remain intact. Published v1 schema bytes and dependency identity rules are unchanged. Complete: required review CI, merge and exact-main confirmation all pass.

- **Combined pre-write guard:** A local provider outside the inherited file set could change between planning and apply. The repository adapter now runs a read-only combined preflight after its currentness checks and before inherited, provenance or baseline writes. The public CLI regression changes a local provider immediately before apply and forbids entering the lineage writer; it failed before this guard and passes after it.

- **Focused implementation evidence:** Ten portable compatibility cases pass through the managed checkpoint runner, including read-only planning, safe-subset apply, unchanged published-wire identity, actual JSON Schema validation, concurrent local-provider drift before the lineage writer, and invocation from a nested directory while updating inherited bytes. Existing lineage/rollback cases (three) and adapter cases (two) also pass.

- **Complete local qualification:** Exact implementation `e1d3e94b` passes all 2,262 selected source cases (2,191 passed, 71 existing skips, zero failures) in 1,246.156 seconds. The exact-source installed-wheel gate passes with wheel `sha256:e3c5852b83d857030243048364223063af3b8b0ecde53a6a9d501a384c7ad4cb`. A forced-fresh lifecycle passes all 232 cases with no skips; supported receipt update, check, require-current and verify pass after the metadata-only integration. Receipt `sha256:f0b3fa15b34b5d138bd0f9480a02796e216a6df704cabf6975f6796e6a40a9ac` remains a local assertion. See `verification/project-update-closure-qualification.json`. PR #131 passes required review CI and lands at `ef5db15f`; exact-main CI `40007862532` passes all 26 jobs. See `verification/project-update-closure-landing.json`. No unrelated native issue is qualified by these portable results.

### [x] WINDOWS-TEST-CONTRACT-001 — Repair Windows test contracts

**GitHub issue:** [#116](https://github.com/jordanhubbard/literate-ai/issues/116).

- **Priority:** P1
- **Owner:** Portable runtime and retained loader test fixtures
- **Direction:** Reconcile open GitHub issue #116 and stacked PR #119.
- **Conclusion:** Keep copied Python aliases bound to their native base runtime and exercise structural loader checks on a supported platform while preserving explicit Windows refusal.
- **Depends on:** none
- **Implementation:**
  - [x] Reconcile PR #119 after #115, diagnose its Linux driver-pin failure, and land its reviewed fixture contribution through the integrated review.
- **Evidence:**
  - [x] Focused alias ordering and loader cases plus exact-head Linux and Windows CI pass without weakening production checks.

**Completion evidence:** PR #119 head `1a4d3e6e` is retained by ancestry in
main `9d62ce09`. The Python alias fixture retains its real base executable,
versioned runtime DLL and `pyvenv.cfg` without new test skips; the loader-role
fixture selects Linux, and the separate Windows unsupported-loader assertion
remains active. Exact-main run `39980361698` passes all 26 jobs, including both
Linux Python jobs and all three full Windows/Python 3.12 test shards. See
`verification/windows-fixture-contract-closure.json`. This completes #116's
fixture-contract acceptance. It does not establish the cause of the separately
reproduced hardware observation timeout or qualify the complete provided-worker
native gate; #90 and #129 retain those remaining requirements.

**Review finding:** Exact-head Linux job `119840524271` in run `39783402916` fails the lifecycle driver review: `retained_project_execution.py` changed while the pin still names `c27617cb`. The contribution also projects ambient `SYSTEMROOT`, overlapping #110's already-bound system-context owner. Reconcile the production delta against the integrated custody path before re-reviewing and repinning; do not treat the failure as only an infrastructure retry.

**Current integration:** Preserve PR #119 head `1a4d3e6e` by merge ancestry. Retain the current bound Windows system-context owner and captured Python/VC sidecars; reject the peer's ambient `SYSTEMROOT` shim and its superseded direct-helper test. Existing typed context tests own currentness/refusal, and the loader structural case already selects Linux in current main. Compose the peer's deterministic base-runtime alias/DLL fixtures and latest controlled remote toolchain probes. The old Windows Elixir failures occurred during upstream strict-version discovery before tests; both exact OTP tags are currently available. Fresh combined controller and native Windows acceptance remain required.

- **Integrated host qualification:** Exact implementation `dd8a9f35` passes a fresh uninterrupted complete source suite: 2138 passed, 71 explicit skips, no failures (2209 selected). The fresh force-generated project lifecycle passes all 228 cases with no skips; supported receipt update/check/require-current and verify pass. Receipt `sha256:0037edcc8b082a9b2554851e6cd9cc1598ccb8715750e45de6b8a9f59638b857`; finalized candidate `sha256:03fd1ef649f40933ffb35c52a380bc18ae5d9638407e0a9ca27cfb10258f8217`. See `verification/windows-integration-host-qualification.json`; preserve the earlier failed SSH response attempt. Exact-head hosted CI and finalized-receipt native/package renewal remain required.

- **Retained development failure:** The native Windows run at `dd8a9f35` passes preflight/environment/compile/lint/OpenSpec (21 tooling tests and 121 diagrams), then reaches its unchanged 5,400-second owned-tree deadline during wheel checks. It does not reach the unit gate. All 112 completed timing spans succeeded, but that is not a complete wheel pass. The evidence archive is downloaded through the configured nondefault transport and independently hash-verified (`sha256:d802e2da8e91835de502d692f1d280cccb748637d706e13a0726b34e95122e39`); no routing configuration is published. See `verification/windows-development-timeout.json`. Finalized-candidate qualification and the corrected Windows identity fixture remain open.

- **PR128 hosted hardware observation:** Full qualification `39936620110`, Windows/Python3.12 shard 3 job `120357700322`, stops at `test_public_factory_automatically_uses_private_configuration` with `action_hardware.transport_expired`. The identical target test and unchanged Windows hardware/configuration owners pass all three cases with no skips on an aligned native Windows worker in 48.875 seconds. Its independently verified evidence archive is `sha256:00333ea078b62610dd8116a293c19ce6017ba1f212763cef2df2f613fe4ede59`; see `verification/windows-action-configuration-diagnostic.json`. The native source baseline and its POSIX-only source difference retain their exact scope: this diagnosis does not replace exact-head CI. The cause of the hosted expiry is not established; no production timeout or guard changed. GitHub refused a failed-job retry while the rest of the workflow was active; retain those healthy jobs and retry only the terminal failed cell after workflow completion.

- **Finalized-source native timeout retained:** Provided Windows qualification at `62ce16a0` terminates at its unchanged 5,400-second owned-tree deadline (5,400.761 seconds), during wheel checks and before unit tests. Preflight, environment, compile, lint, 21 documentation-tool tests and 121 diagrams pass. All 111 completed wheel timing spans succeed; the longest installed Python/HTML operation is 3,312.078 seconds, and operator golden paths take 807.891 seconds. Independently verified archive `sha256:e0b1357c9cd6f28a148d959087376f86377c4fa6dd8f9b91ba29c5072a7447d7` retains the original result, log and timings. See `verification/windows-final-head-timeout.json`. Inspect the expensive native operations before another full native gate; this is incomplete qualification and does not replace PR128 exact-head hosted CI.


- **Repeated exact-main failure:** Run `39948443185`, job `120396818599` at `fe21a198` fails the same real hardware-probe transport deadline after 497 passes and 84 skips. The candidate retry had passed; recurrence requires stage-level diagnosis before another retry. The 180-second observation bound and 1,800-second action grant remain unchanged. See `verification/windows-main-hardware-recurrence.json`.

- **Recurrence diagnosis before repair:** Exact-main run `39948443185` is now terminal with the hardware expiry. Its exception identifies transport but discards whether the shared 180-second lease was first consumed by controller receiver-code observation or by the child transport. Add bounded scalar timings to the existing real factory regression on failure, delegating to every unchanged production call and preserving the original exception chain, positive assertions and execution bounds. This is diagnostic coverage, not a timeout fix or green main claim. Renew that exact fixture before the next combined CI run; do not blindly retry the failed main cell.

### [x] DOC-DEPENDENCIES-002 — Refresh DOMPurify after critical documentation dependency findings

- **GitHub issue:** [#120](https://github.com/jordanhubbard/literate-ai/issues/120)

- **Priority:** P0
- **Owner:** OpenSpec and Mermaid documentation tooling
- **Direction:** Resolve newly reported critical and high DOMPurify advisories without weakening the audit gate
- **Conclusion:** The pinned transitive DOMPurify 3.4.16 is affected by GHSA-cg2g-xh64-v4q7 and GHSA-mrv2-3pqr-j5jr; both identify 3.4.17 as patched. Update only the compatible transitive lock and preserve exact prior qualification scope.
- **Depends on:** none
- **Implementation:**
  - [x] Update the lock with the normal npm resolver; retain audit policy without exceptions
- **Evidence:**
  - [x] Fresh clean install, dependency gate, documentation tool tests and full diagram rendering; renew the native gate after integration

Implementation: the normal npm resolver changes only DOMPurify's version, registry
URL and integrity, from 3.4.16 to 3.4.17. A clean installation and dependency gate
pass without exceptions; all 21 documentation-tool tests and all 121 diagrams
across 625 Markdown files pass on the controller. At that controller checkpoint,
native Windows renewal remained required after composition. No Python production
code changes.

**Completion evidence:** The integrated native Windows attempt at `28371242`
completed a fresh `npm ci` with zero reported vulnerabilities, the unchanged
high/critical audit gate, all 22 documentation-tool tests with no skips, and all
121 diagrams from 626 Markdown files. Its later wheel timeout remains retained
under issue #129; that timeout does not contradict the completed dependency and
documentation checks. The documentation package manifests and lock are byte-for-byte
unchanged between that native revision and exact main `9d62ce09`, whose required
CI run `39980361698` passed all 26 jobs. See
`verification/documentation-dependency-closure.json`. This closes the dependency
repair scope and makes no claim that the complete provided native gate passed.

### [x] DOC-DEPENDENCIES-003 — Refresh vulnerable transitive Zod in documentation tooling

- **GitHub issue:** [#134](https://github.com/jordanhubbard/literate-ai/issues/134)

- **Priority:** P1
- **Owner:** Pinned OpenSpec and documentation dependency lock
- **Direction:** Resolve the high Zod advisory blocking required CI and the provided Windows gate; preserve the audit and all qualification bounds.
- **Conclusion:** Refresh the compatible transitive resolution, prove clean locked audit/docs/OpenSpec checks, then renew the failed qualification. This is dependency maintenance, not native performance acceptance.
- **Depends on:** none
- **Implementation:**
  - [x] Update the existing Zod resolution to a patched compatible 4.x release without new dependencies or audit exceptions.
- **Evidence:**
  - [x] Clean npm ci, strict audit, documentation tests/diagrams and strict OpenSpec validation pass; exact-head CI (16 successful jobs and its placeholder skip) and exact-main CI (all 26 jobs) pass. The renewed provided Windows gate passes strict audit/OpenSpec, all 22 documentation tests and 121 diagrams. Its later 5400-second wheel timeout is retained under #129; no complete native qualification is inferred.

**DOC-DEPENDENCIES-003 dependency selection:** The affected graph contains root Zod 4.4.3 and Chromium BiDi's nested Zod 3.25.76. Puppeteer 25.16.0 keeps the existing Node 22.12 floor and uses upstream Chromium BiDi with a Zod 4 dependency, permitting patched Zod without forcing a new major into a v3 consumer. Refresh that existing browser-tool pin, its matching allowed install-script entry, and the locked Zod 4 resolution; retain every audit and documentation check.

**DOC-DEPENDENCIES-003 local qualification:** A fresh canonical staged `npm ci` installed the exact lock with zero vulnerabilities. Strict OpenSpec validation passes all four items; the unchanged audit and 22 documentation tests pass, and Puppeteer renders all 121 Mermaid diagrams across 627 Markdown files. The supported receipt check remains current; all-gate verify reports two passes, three existing declared skips and zero failures. The prior exact-head CI and supplied-worker gate failures remain retained. Next: publish this fix through existing PR #133 and renew exact-head CI and the unchanged provided-worker native gate before closure.

**HOST-RUNTIME-001 closure:** All required private-runtime acceptance is complete. The affected macOS standalone Python 3.11.14 executes Python and pip and passes real-wheel self-update/reexecution; the public non-editable prefix install and complete source/wheel/lifecycle qualification pass. Source owner parity is checked against landed `ef5db15f`, whose exact-main CI succeeds in all 26 jobs. Retain the original loader abort and symlink-only containment failure. See `verification/private-runtime-closure.json`; this is not FreeBSD/native SDK or performance admission.

**RETAINED-USER-001 closure:** The installed original suite already qualifies privileged and unprivileged execution under a private 0700 allocation prefix, with all 24 cases passing, no skips, exact ACL restoration, no remaining nullfs mounts, current observed account/allocation custody, 34 reverified records and independent cleanup-bound acceptance. Landed platform CI and unchanged scoped owners complete the recorded remaining requirement. See `verification/retained-secondary-closure.json`; whole execution/SDK modules have later changes and are not asserted byte-identical or newly natively qualified here.

**DOC-DEPENDENCIES-003 closure:** PR #133 lands the existing browser-tool upgrade and patched Zod lock at `d17881fa`; exact-main CI 40031696168 passes all 26 jobs. The actual provided Windows audit/documentation gates also pass. This completes dependency maintenance only, as issue #134 explicitly separates native-performance issue #129. The renewed full gate times out later in wheel smoke after 121 completed spans, with no test phase reached; its immutable failure bundle and source identity remain retained. See `verification/documentation-zod-qualification.json` and `verification/windows-lock-reuse-native-timeout.json`.

**#129 / WIN-GATE-001 current native outcome:** Supplied-worker source `2615e568` has the same tracked tree as merged `d17881fa`. The unchanged 5400-second gate reaches 121 completed wheel operations but times out before wheel completion and the test phase. The complete five-stage HTML scenario passes in 2871.062 seconds; default and scoped initialization take 252.563 and 196.578 seconds. These are retained operation observations, not a controlled whole-gate speedup or admission. Existing timing evidence survives the timeout. The last completed graph-export scenario is followed by an uninstrumented missing-CodeGraph run probe and update planning; identify the unfinished operation and remaining initialization/observation costs before another full renewal. Keep #121, #123 and #129 open; do not increase deadlines, skip assertions or promote this failed outcome.

### [x] DOCS-LABS-001 — Modernize 1.4 documentation, conference evolution deck, and visual labs

- **Priority:** P0
- **Owner:** front-door documentation, conference collateral, samples, and HTML observability
- **Direction:** Synchronize user documentation with the 1.4.0 development feature set; create a conference-ready deck on Literate AI goals and evolution; and add progressively more complex, cheeky, independent visual labs spanning component DAGs, audio, video, 3D, music, mathematics, and physics.
- **Conclusion:** Treat general documentation as 1.4.0 development authority while preserving 1.3.1 release-specific collateral. Build one DRY lab kit with independent lab entry points, lesson-flow diagrams, and deterministic browser-friendly artifacts. The original claim that those diagrams were resolved Component graphs was incorrect; LAB-AUTHORITY-001 owns the correction and real canonical curriculum. Produce an editable local conference deck through the repository presentation pipeline; do not publish externally without separate authorization.
- **Depends on:** current 1.4.0 main authority; existing HTML explorer and presentation toolchain
- **Next action:** Complete. Keep the current-feature page synchronized with release
      authority, rebuild the deck from its checked-in source when claims change, and
      extend the lab sequence only when each new artifact remains offline and independently
      verifiable.
- **Implementation:**
  - [x] Audit and reconcile front-door and user documentation against current commands and features; add a labs curriculum with shared support and progressively richer independent examples; create an editable conference deck with speaker notes and source ledger; link all new surfaces from stable indexes.
- **Evidence:**
  - [x] `make documentation-check` renders 121 Mermaid diagrams from 639 Markdown
        files; the 1.4.0 current-feature page distinguishes published 1.3.0, patch
        1.3.1, development, and open qualification.
  - [x] Six standalone lab artifacts pass `build_labs.py`, `verify_labs.py`, desktop
        browser interaction checks, offline-resource checks, and a 390-pixel viewport
        bounds check; each exposed its authored Markdown and illustrative role flow. Those checks did not establish canonical Components, Flavor selection or lifecycle admission; LAB-AUTHORITY-001 adds the missing curriculum.
  - [x] The 14-slide editable PPTX has 14 speaker-note pages. Package integrity,
        layout geometry, font policy, slide bounds, render count, and full-slide visual
        review pass with zero structural findings or layout warnings; exact deck SHA-256
        is recorded in its checked-in `validation.json`.
  - [x] The reviewed documentation authority marker is current at
        `sha256:6f40bac8e467374e03aaa0fa72b656f8d6a52fff2fb0c0f8c8fe551f24d636d5`;
        `litai project validate`, `make lint repository-layout-check`, and the clean
        full `make python-check` pass (2,332 tests, 70 skipped).

### [x] CONFERENCE-WEB-001 — Publish conference attendee documentation and materials on the web

- **Priority:** P0
- **Owner:** documentation website and conference materials
- **Direction:** Commit and push all updates without waiting for CI; prioritize a usable public documentation website and attendee materials before the conference in two hours.
- **Conclusion:** Publish a GitHub Pages attendee hub from the reviewed repository, with browsable documentation, offline HTML deck, truthful labs, approved film and captions, downloads and an explicit release-status boundary. Use scoped local browser/link checks and deploy independently of product CI.
- **Depends on:** none
- **Implementation:**
  - [x] Integrate pending reviewed updates and publish a reproducible static documentation site with a conference landing page and a dedicated deployment workflow. PRs #158 and #160 are merged; site source `0ef44bcd7282c8d3efb904e9049669b98de0d3a8` deployed successfully in run `40567956679` to https://jordanhubbard.github.io/literate-ai/.
- **Evidence:**
  - [x] Verify desktop and mobile pages, live deployed links, deck navigation, film/caption downloads and publication status; record any CI still running without making release-success claims. The 442-page build passes 4,149 local-link checks. Live Chrome passes fourteen navigation/interaction checks at widths 1440 and 390, including search, film metadata/captions and lab input; all eight framework-flow diagrams render. The fourteen-slide deck passes desktop/mobile controls and layout checks. Fresh public deck, film, caption and downloaded-kit content hashes match reviewed sources; archive CRC passes. See [publication evidence](../../conference/publication.json). Product CI remains separate and was not awaited by explicit user direction; 1.3.1 software qualification and the canonical lab curriculum remain open.

### [x] CARGO-REUSE-001 — Reuse Cargo target output across Standard builds

- **Priority:** P1
- **Owner:** framework core; PROJECT Goals 4 and 5
- **Direction:** Reuse CARGO_TARGET_DIR where compatible to avoid recompiling unchanged Rust dependencies and targets.
- **Conclusion:** Retain a locked target/toolchain-scoped Cargo workspace, preserve unchanged source timestamps, synchronize additions/deletions, and discard failed workspace state. Keep fresh authorization, lock derivation, dependency evidence, artifact sealing and acceptance.
- **Depends on:** none
- **Completion prerequisites:** none
- **Implementation:**
  - [x] Implement persistent Cargo workspace and source synchronization with safe path checks. Compatible source revisions share locked intermediates; successful state is sealed over bytes, modes and freshness timestamps, and interrupted/failed work is discarded.
  - [x] Repair the native fixture's Cargo/rustc binding collision with rustup multicall launchers (CI run `41213808272`). Preserve the selected invocation names while measuring launcher bytes; cover identical launchers locally. Managed `make python-check` passes all ten Cargo cases without skips with the actual rustup proxies selected, including duplicate-launcher registration, drift refusal and real warm/source-edit builds. Ruff lint/format and host path checks pass. Exact-head CI must pass before PR #198 is declared merge-ready; its review status owns that final remote evidence.
  - [x] Document reuse boundaries and add focused native Cargo and failure/isolation regression coverage. User cache/configuration guides and the root changelog describe local reuse independently of sccache.
  - [x] Repair [PR #198](https://github.com/jordanhubbard/literate-ai/pull/198) CI by reviewing the Cargo cache documentation against the implementation and recording the current documentation authority marker. Run `40912720305` failed all three sample-composition cells and the Linux repository self-description test on the same stale marker; no other Python failures were reported.
  - [x] Merge current `main` into the contribution branch to resolve GitHub's reported conflicts, preserving both branches' changelog and work-queue entries; refresh documentation review for the integrated authority.
  - [x] Refresh the lifecycle-driver implementation pin after reviewing the integrated Cargo changes; `make driver-review` detects the previously unrecorded Cargo implementation drift. Preserve the existing receipt as historical evidence rather than claiming fresh lifecycle qualification.
- **Evidence:**
  - [x] Re-run all declared `litai verify` gates and the affected project CLI tests; record local results and any gates requiring separate lifecycle evidence. Local integrated-tree evidence: project validation, documentation review and lifecycle-driver review pass; managed `make python-check` passes all eight project CLI tests and nine Cargo lifecycle tests without skips (native rustup toolchain selected). Host path policy and the contribution diff whitespace check pass. `litai verify` passes authority, skips locks/source-intelligence/HTML because none are selected, and reports the existing stale lifecycle receipt; fresh full lifecycle qualification is not claimed. Start/end peer surveys still fail through the configured GitHub alias; direct read-only GitHub inspection succeeds. Existing unrelated worktrees and untracked local files are preserved. Hosted CI renewal remains separate from local development proof.
  - [x] Focused Standard Cargo tests prove warm freshness, source-edit rebuild, failure cleanup and unsafe-path refusal. All nine `tests.smoke.test_standard_cargo_lifecycle` cases pass on macOS arm64 with native Cargo/rustc 1.97.1: a warm forced artifact miss preserves the executable timestamp, a binary source edit rebuilds it while preserving the unchanged library artifact, and namespace isolation, stale-input removal, tampering/link refusal and interrupted/failed workspace cleanup pass.
  - [x] Run scoped make python-check and lint/format checks; record local-only scope and unavailable tracker survey. Scoped `make python-check` runs pass 63 Standard smoke cases (four expected skips), 33 critical cache cases, and a final nine-case Cargo rerun. Changed Python files pass Ruff lint/format and `git diff --check`; compileall and host path policy pass. Validation explicitly selected the existing rustup toolchain because ambient Homebrew Cargo cannot load its llhttp dependency. Start/end tracker surveys and the read-only GC plan fail through the configured GitHub alias; no peer changes were collected. This is local development evidence, not native cross-platform or release qualification.

### [x] SKILL-DISCOVERY-001 — Make skill capabilities discoverable and assess Google composition

- **Priority:** P2
- **Owner:** documentation
- **Direction:** Enumerate and classify the skills tree for new users, then check out google/skills and compare useful capabilities and composition techniques.
- **Conclusion:** Publish a task-oriented complete catalog and a revision-pinned comparative assessment; recommend scoped adaptations without importing third-party execution policy or claiming unqualified capabilities.
- **Depends on:** none
- **Completion prerequisites:** none
- **Implementation:**
  - [x] Classify every canonical skills/**/SKILL.md and distinguish onboarding, templates, Flavors and delivery boundaries.
  - [x] Link the catalog from newcomer entry points and document pinned Google evidence, strengths, gaps and prioritized adaptations.
- **Evidence:**
  - [x] Verify inventory completeness, counts, local links and comparison source paths against both checkouts.
  - [x] Pass documentation and changed-skill gates, record the documentation authority marker and review the final diff.

- **Validation:** Exact set comparison covers all 88 canonical paths once and all task-map
  anchors; Google index entrypoints match its 178 canonical paths, and all 15 cited
  pinned source paths exist. Local file-link inspection passed before source links
  were made revision-pinned GitHub links to respect documentation-root boundaries.
  `make documentation-check skills-check repository-layout-check` passed: 22 tooling
  tests, 181 rendered diagrams, root skill Tier 1 admission, and layout validation.
  Documentation graph validation passed; its reviewed authority marker is recorded
  with this change. The end-of-cycle peer survey found no collectable worktrees;
  unrelated historical branches and other contributors' reviews remain untouched.

<a id="release-integration-005"></a>
