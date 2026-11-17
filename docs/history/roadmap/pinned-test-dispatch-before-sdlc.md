# Historical pinned-test-dispatch design

This is the superseded execution guidance retained by the 2026-11-16 SDLC review.
TEST-CACHE-001 remains open under the [current plan](../../roadmap/pinned-test-dispatch.md).
Historical unchecked requirements are mapped there; this archive is not completion evidence.

# Pinned test dispatch

- **Status:** historical
- **Owning queue item:** [TEST-CACHE-001](../../roadmap/active-work.md#test-cache-001-checkpointgate-skip-logic-is-not-dependency-aware-it-only-detects-a-changed-test-file-not-a-changed-dependency)
- **Completion / archival evidence:** [2026-11-16 reconciliation and retained requirements](../../roadmap/pinned-test-dispatch.md); TEST-CACHE-001 remains open
- **Release target:** 1.1.0. TEST-CACHE-001 owns every remaining evidence item below;
  reconcile its already-recorded partial results before claiming final completion.

## Problem

`make release-check` has two checkpoint/resume mechanisms today
(`src/literate_ai/test_checkpointing.py`), and neither is dependency-aware:

- The outer gate chain (`run_gates`) skips a gate solely because its *name* is recorded
  `"ok"` in the checkpoint file. It fingerprints nothing a gate reads.
- The inner Python test runner (`run_unittest_suite`) skips a test solely because *that
  test's own module file* is byte-identical to when it last passed. It does not know
  what production module, config file, or fixture the test actually exercises.

Both are under-approximations of "has anything this decision depends on actually
changed." A shared production module, or a config file like `literate.project.json`,
can change without invalidating any test that depends on it, as long as the dependent
test's own file is untouched. This was reproduced directly in the session that filed
this document: editing `literate.project.json` and `docs/architecture/design-traceability.md`
between checkpointed `release-check` resumes would not have invalidated any
already-`"ok"` Python test that reads either file at runtime, purely because neither is
a test file.

This is not scoped to `python-check`. The same shape of problem — "was this decision's
input actually the same as last time, or did we just not look?" — recurs anywhere this
framework reuses a prior result: Standard lifecycle node build/test/sample execution,
generated-source cache membership, and CI's own job-level caching all currently answer
that question with their own local, inconsistent heuristic, if they answer it at all.

## Direction

Build one **pin**, one **test pipeline**, one **marker** model, and one shared
dispatch service that every workflow entry point consults — not a per-mechanism
fingerprint bolted onto each existing checkpoint file.

**Pin.** A pin is any content-addressed node already tracked by this framework's
authority/dependency graph: a Component revision, a Flavor revision, a
specification-to-source or source-to-specification skill version, a workflow/routing
identity, or — extending the same model inward — a framework-internal source module
covered by an existing hashed set (the lifecycle-driver TCB identity in
`literate.project.json`, or the documentation-authority marker's inventory). Critically,
this framework **already computes most of the needed identities**:
`ComponentAuthorityReviewEntry.input_closure_identity` folds a Component's transitive
dependency closure into its own hash; Flavor `revision_identity` and skill `identity`
do the same for their own graphs. GRAPH-001's canonical effective-authority DAG is the
natural substrate — this system should consume that solved graph, not re-walk
dependencies itself.

**Pins compose within one Component's build, not only across Components.** A single
Component's own lifecycle is itself a derivation chain of pins, not one monolithic pin
with one pipeline: source pin → object pin(s) → binary/library pin → executable/package
pin. Each tier is separately content-addressed already — this is exactly what `OBJ_DIR`
(the object/binary cache, distinct from `BUILD_DIR`'s generated-source cache) and the
`CACHE-002` through `CACHE-007` family exist to key correctly. Each tier's hash folds in
the tier below it plus its own tier-specific inputs — an object pin folds in its source
pin plus toolchain/compiler-flag identity; a binary or library pin folds in the exact
object pins it links; an executable or package pin folds in the binary/library pins it
composes plus its packaging Flavor. Each tier has its own test pipeline bound to it:
generated-test suite at the source tier, compile/unit checks at the object tier,
link-time and integration tests at the binary/library tier, installed/acceptance smoke
at the executable/package tier.

Because each tier's hash already folds in every tier beneath it, a downstream tier's
gate does not need to separately re-walk and re-verify its whole upstream chain — the
single check "does a `tested` receipt exist for *my own* hash" is already sufficient,
precisely because that hash cannot match unless everything upstream matched too. This
is the same closure property as the cross-Component case above, just applied to the
tiers inside one Component's own lifecycle: an executable/library pin only ever reaches
`tested` after every binary/object pin beneath it already has, and CACHE-007's own
receipt-composition rule already states this for the whole lifecycle — "a downstream
failure records diagnostics but cannot finalize or overwrite the current passing
receipt." That existing rule *is* chain-gating; this design generalizes it into the
same pin/marker vocabulary used everywhere else instead of being Standard-lifecycle-only
phrasing.

**Test pipeline.** The ordered set of checks bound to one pin. Component, Flavor, and
skill pins are **not symmetric** here, and the design must not pretend otherwise:

- A **Component** genuinely owns a pipeline: the generated-test suite the coding-CLI
  produces from its `component.md` Requirement/Scenario prose, plus the independent
  acceptance oracle at `verification/acceptance/<name>.json`
  (`src/literate_ai/adapters/component_acceptance.py`) — hand-authored, never
  referenced from `component.md` so the generator can't see the answers, and bound to
  the exact specification-set identity so a spec change invalidates stale expectations
  rather than silently keeping them.
- A **Flavor** owns no pipeline of its own — checked `flavors/lang-go/flavor.md`: it declares
  generation policy (`specification_roots`, `authoring_inputs`, build-system
  `contributions`), nothing test-shaped.
- A **skill** owns no correctness pipeline either — `skills-check`
  (`scripts/evaluate_changed_skills.py`) runs NVIDIA SkillEvaluator's
  `schema,pii,license,quality,unicode,lint` checks against the `SKILL.md` document
  itself, not against whether following it produces correct generated code.

Flavor and skill pins are validated only **transitively**, through whichever Component
pins currently select them and run *that Component's* pipeline. For a framework-internal
module covered by the lifecycle-driver TCB, the pipeline is the subset of `python-check`
that exercises it — same shape as a Component's own pipeline, since it is source the
framework directly owns and tests, unlike a Flavor or skill.

**Marker.** How far execution has progressed through one pin's pipeline, keyed by
**that pin's own hash** — not by a separately-computed file fingerprint. A marker is
only ever meaningful for the exact pin identity it was recorded against. When a pin's
hash changes (because its own content changed, or because anything in its already-folded
dependency closure changed), there is by construction no marker for the new hash: the
pin starts `untested` without needing separate invalidation logic to notice staleness.
This is a stronger property than today's fingerprint comparison, which has to actively
detect drift; here, drift is structurally impossible to observe as "unchanged," because
the identity itself would already differ.

**State.** `tested` is derived, not a separately toggled flag: a pin is `tested` exactly
when its marker has reached the end of its pipeline with every step passing. Reaching
that state is what the last test in the pipeline does, not a separate bookkeeping step
after it.

**Dispatch.** One shared service, consulted by every workflow (release-check gates,
`litai build`/`test`/`run`, Standard lifecycle node execution, sample generation, CI),
walks the current DAG from GRAPH-001, and for each pin: if its hash matches a recorded
`tested` state, skip its entire pipeline outright — do not open the pin's files at all.
If its hash matches a recorded marker short of `tested`, resume from the marker. If its
hash has no recorded state, run the full pipeline from the start. Nothing not reachable
from a changed pin is ever inspected.

**The real pin is Component × Flavor-combination × skill-set, and mixing changes
behavior — this is already correctly captured.** Selecting Go vs. Python vs. Rust as
the language Flavor produces entirely different generated source from the same
Component spec; a skill directly shapes what the coding-CLI is told to produce for that
Flavor. Checked, not assumed: `LockedComponentRevision` in
`src/literate_ai/contracts/component_locking/locks.py` already binds
`selected_flavor_revisions: tuple[ContentIdentity, ...]` into its canonical, hashed lock
content. "Component X built with `{go, linux, make}`" and "Component X built with
`{python, macos, bazel}`" are already, correctly, two distinct pins in the framework's
existing data model — a pass on one implies nothing about the other, and this design
does not need to invent that granularity.

**Coverage is a different problem than caching, and this design only solves caching.**
The pin model correctly tells you *when* an already-selected combination needs
retesting. It says nothing about *whether a given combination has ever been tested at
all* — that space (language × OS × build-system × toolchain × packaging × skill) is
combinatorial, and the framework only ever exercises whichever combinations the sample
matrix happens to select today (`MATRIX-001`, `SAMPLE-MATRIX-002`, `SAMPLE-MATRIX-003`).
A Flavor or skill with no sample currently selecting it has zero coverage regardless of
how correct this dispatch design is. Pinned-test-dispatch is scoped to "don't rerun what
provably hasn't changed"; it is explicitly not a fix for "make sure everything that
matters gets run at least once" — that boundary belongs to the matrix-coverage items
above, not here.

## Artifact derivation and the tested tag

The dispatch loop above describes evaluating a DAG that already exists. It does not by
itself explain what puts a *new* pin in front of that loop, or where "tested" is
recorded such that it outlives the local checkpoint file. Both halves already exist in
this framework, separately, unwired to each other.

**Creation is an event, not a poll.** A new pin does not appear because dispatch went
looking for one — it appears because something derived it: a spec/Flavor/skill edit
drove generation, and generation produced a new content-addressed source artifact. That
production step is the trigger that pushes the artifact's test pipeline into the
scheduler. This is exactly the shape CACHE-007 ("Admit verified generated source before
target builds," currently unmerged WIP, not yet on `main`) already describes for the
build side: `generated source candidate -> independent verification -> accepted-source
admission evidence and cache membership -> ...`. Dispatch should consume CACHE-007's
admission evidence as its creation trigger rather than defining a second one — a pin
enters the scheduler when an admission record names it, not when a periodic walk
happens to notice it.

The converse matters as much as the trigger: a sibling artifact that was **not**
re-derived this run — its Component/Flavor/skill inputs are byte-identical to its last
recorded pin — never fires this event. It doesn't get looked up, compared, and found
unchanged; no event exists for it to react to, so it never touches the scheduler at
all. It just continues to carry whatever tag it already has.

**The tag is the existing receipt, not a new artifact.** `REBUILD-RECEIPT-001` already
established a "finalized candidate envelope" — a project test receipt bound to exact
lock identities, written and *committed through Git* rather than left in disposable
`_build/` state (README: "compact passing receipts preserve test history through
Git"). That receipt already is the `tested` tag this design needs; it does not need to
be reinvented, only re-keyed. Today it's keyed by an ad hoc lock-list identity assembled
per rebuild; under this design it should be keyed by the same pin hash
(`input_closure_identity` / Flavor `revision_identity` / skill `identity`) that GRAPH-001
already computes, so "does a receipt exist for this exact pin" becomes dispatch's entire
skip check — one lookup, no separate fingerprint comparison.

**Packaging carries the tag forward.** Components already produce CycloneDX SBOM and
provenance evidence as part of their build/package lifecycle. Once the receipt is keyed
by pin hash, "tested at pin X" is a natural field in that same provenance record —
released artifacts carry their own test-pass evidence, and a downstream consumer (or a
future release of this framework, importing a Component) can verify "was this tested"
without re-deriving anything, the same way it already verifies dependency provenance.
No new packaging step is required; the existing SBOM/provenance surface is where this
belongs.

## Explicitly not doing

- Not building a second dependency tracker parallel to GRAPH-001. If GRAPH-001's closure
  identities are insufficient for some pin kind (e.g. they don't yet cover a production
  module's *runtime-read* files, only its imports), that is a GRAPH-001 gap to close,
  not a reason to invent parallel tracking here.
- Not building a second artifact-creation trigger parallel to CACHE-007, and not a
  second tag/receipt format parallel to REBUILD-RECEIPT-001's finalized envelope — this
  design consumes both rather than duplicating either.
- Not a general-purpose build cache or artifact store. This system governs the
  *decision to skip a test pipeline*, not object/binary caching (see the CACHE-002
  through CACHE-007 family for that).
- Not turning `make release-check` into a distributed/remote cache. Local, filesystem
  checkpoint state is in scope; a shared team-wide cache is out of scope until this
  local model is proven.

## Migration

`test_checkpointing.py`'s two existing schemas (gate-name-list, per-test-file-fingerprint)
are superseded, not extended. A migration must define how the framework's own
`python-check` suite — which does not currently have declared "pins" the way Components/
Flavors/skills do — gets partitioned into pin-sized units with pipelines, likely aligned
with existing TCB/authority-hashed file sets (lifecycle-driver TCB, documentation
authority) as the first pin boundaries, expanding coverage from there rather than
requiring every source file to have a declared pin on day one.

## Design review — does this actually minimize re-running passing tests?

A self-review against the stated goal, not just a defense of the design as drafted.

**Already correct, and a real upgrade over today:**

- The `tested` tag is a Git-committed receipt, not `_build/`-scoped throwaway state, so
  it survives across process launches. Today's checkpoint only ever helps *resume after
  your own failure within one continuous session* — a normal clean invocation always
  reruns everything, because the checkpoint file starts empty every time. That is
  arguably the single biggest existing gap, and this design closes it by construction.
- Closure-hash composition means a read-time check is "does a receipt exist for my own
  hash," with no separate upstream re-walk, for both cross-Component and cross-tier
  (source→object→binary→executable) dependencies.
- Event-driven creation means an untouched artifact generates zero scheduler traffic,
  rather than being checked and found unchanged.

**Gaps that must close before this design can be trusted:**

- **Pin-hash completeness is the load-bearing assumption, and nothing enforces it.**
  The entire "skip is safe" guarantee rests on every real dependency being folded into
  the pin's hash. A missing one (external tool version, environment variable, coding-CLI
  model identity) doesn't just under-optimize — it makes the system **wrong**: it skips
  a test that should have rerun, which is strictly worse than today's over-caution.
  "Unknown dependency" must default to *not tested*, never to *tested*, and hash
  completeness needs to be a provable, checked property, not an assumption.
- **Cross-cutting tests don't fit "one pin, one pipeline."** Composite/integration
  tests — this repository's own `service-stack` sample, which exercises three
  Components together — aren't owned by a single pin. They need representation as
  synthetic composition pins (hash = combination of every pin they exercise), or they
  fall through to always-rerun or, worse, get attributed to the wrong pin.
- **Concurrent-writer safety isn't specified, and this session hit exactly this bug
  live.** Editing a file in the same worktree a background test process was reading
  produced a real, reproducible false failure. Marker writes and pin reads need an
  explicit locking/isolation contract, generalizing the
  `_copy_status_source_snapshot`/`_require_status_source_snapshot_unchanged` isolation
  pattern CodeGraph already uses for the same reason, not left implicit.
- **No handling for flaky or non-deterministic tests.** A pin that passes once by luck
  is marked `tested` and never re-verified until its hash changes.
- **No distinction between infrastructure-retry-safe failure and genuine test
  failure.** Connects directly to `GENERATION-006`
  (`coding_cli.generated_metadata_invalid` — "a plain retry usually fixes it"): marker
  semantics need to know a transient generation blip shouldn't poison a pin the same way
  a real assertion failure should, or the system either wastes full reruns on flakes or
  masks real problems behind silent retries.
- **The framework's own `python-check` migration (see Migration, above) is a stated
  intention, not a design.** Until it is actually specified, this framework's own test
  suite keeps using the weaker per-file fingerprint — meaning the exact bug that
  motivated this document (`literate.project.json`/`design-traceability.md` staleness)
  is pointed at, not yet fixed by anything written down.

## Evidence

- [ ] A regression proves a pin whose dependency-closure identity changes (not its own
      file) re-enters `untested` and its pipeline reruns, while sibling pins whose
      closure did not change are never opened.
- [ ] A regression proves a pin recorded `tested` at its current hash is skipped without
      any of its declared inputs being read.
- [ ] A regression proves an artifact not re-derived this run (no CACHE-007 admission
      event fired for it) never enters the scheduler at all.
- [ ] The `tested` tag is the same committed receipt REBUILD-RECEIPT-001 already writes,
      re-keyed by pin hash, and is readable from a packaged Component's own
      SBOM/provenance evidence without re-deriving it.
- [ ] `make release-check`, `litai build`/`test`, and CI all consult the same dispatch
      service rather than independent checkpoint files.
- [ ] Full `make release-check` wall-clock time on a no-op resume (no source changed)
      is dominated by DAG-walk cost, not by re-running any pipeline.
- [ ] A completeness check (static or CodeGraph-derived) proves each pin kind's declared
      hash inputs cover everything its pipeline actually reads at runtime; an unproven
      or newly-discovered dependency defaults the pin to `untested`.
- [ ] A composite/integration test (e.g. `service-stack`) is represented as a synthetic
      composition pin and reruns whenever any pin it exercises changes.
- [ ] A regression reproduces this session's concurrent-writer bug (a pin's source
      mutated while its pipeline is mid-run) and proves it now fails closed instead of
      producing a false result.
- [ ] A retryable infrastructure failure (matching `GENERATION-006`'s
      `coding_cli.generated_metadata_invalid`) does not poison a pin's marker the same
      way a genuine assertion failure does, and does not silently mark a pin `tested`
      without an evidenced passing run.

## Historical active-queue entry

### [~] TEST-CACHE-001 — Checkpoint/gate skip logic is not dependency-aware; it only detects a changed test file, not a changed dependency

- **Priority:** P0
- **Release target:** 1.1.0
- **Previous release target:** 0.8.0. Filed mid-0.3.0 as a P0; the design (PR #45,
  `docs/roadmap/pinned-test-dispatch.md`) landed, but every implementation checkbox
  below is still unchecked. `v0.3.0` shipped on a manually authorized tag once `main`'s
  CI was green rather than waiting on this. Keep the P0 on the designed pin/dispatch
  service; do not substitute a parallel fingerprint in a patch cut.
- **Owner:** `src/literate_ai/test_checkpointing.py`, `scripts/run_checkpointed_gates.py`,
  `scripts/run_checkpointed_unittests.py`, GRAPH-001's canonical DAG, and by extension
  every Standard lifecycle/sample execution path that reuses cached build/test results
  by identity rather than re-deriving it
- **Direction:** `make release-check` has two independent checkpoint/resume layers, and
  neither is content-addressed against what a test or gate actually depends on:
  1. Gate-level (`run_gates`, the outer `repository-layout-check`/`python-check`/`lint`/
     `format-check`/... chain): `plan_identity` hashes only the ordered list of gate
     *names*. A passed gate is skipped on resume purely because it is recorded
     `"ok"`, with no fingerprint of anything the gate reads.
  2. Python-test-level (`run_unittest_suite`, inside `python-check`):
     `_test_source_fingerprint` hashes only the test's *own module file bytes* — not
     the transitive closure of production modules, fixtures, or config it imports or
     reads at runtime.
  Demonstrated concretely in this session: edits to `literate.project.json` and
  `docs/architecture/design-traceability.md` between checkpointed `make release-check`
  resumes are not test files, so no already-`"ok"` Python test that reads either at
  runtime would have been re-verified against those edits had it already been
  checkpointed as passing before the edit landed. This session avoided a false-green
  result only because the specific tests exercising those exact files happened to sit
  at the checkpoint's unexplored frontier, not because the mechanism guarantees it.
  This is a fail-open correctness gap in the tool intended to give release-check its
  "trust a resumed run" property, not a one-off bug.
- **Conclusion:** Decided: replace both ad hoc checkpoint schemas with one pin/test
  pipeline/marker/dispatch model, keyed off identities this framework's authority graph
  (GRAPH-001) already computes — a Component's `input_closure_identity` and a Flavor's
  or skill's `revision_identity`/`identity` already fold in their dependency closure, so
  a pin's own hash is sufficient to detect "did anything this depends on change,"
  without a second parallel dependency tracker. Full rationale, the explicit
  not-doing boundary, and the migration path for `python-check`'s own currently-unpinned
  test suite are in the detailed plan.
  2026-08-27 judgment: the 2026-08-15 WIP (`c0439340` on
  `worktree-agent-a1920861b1f6354a5`, merge-base `d1af57ab`) is obsolete as a
  land-as-is: it is a python-check `sys.addaudithook("open")` slice, not the
  designed service. It does not bump `PYTHON_SCHEMA_VERSION`, misses import-time
  production modules, does not touch `run_gates` name-only `plan_identity`, and
  would regress class-level `SkipTest` `_record_known`. Do not cherry-pick or
  rebase it. 2026-08-28: the designed item is in 0.8.0
  ([RELEASE-012](../../roadmap/active-work.md#release-012-080-unreleased-product-and-protocol-scope)); a later
  `open()` fingerprint that keeps `_record_known` is still not TEST-CACHE-001
  shipped. **2026-08-30:** pin/pipeline/marker dispatch landed as `acb161ff`
  (isolated `3b5d0c10`, not `c0439340`). `PYTHON_SCHEMA_VERSION = 3`.
  `run_gates` / `run_unittest_suite` consult `pinned_test_dispatch`. Live
  rebuild still writes lock-list `subject_identity` until callers use
  `rekey_receipt_to_pin`. `litai build`/`test`/CI and no-op `release-check`
  wall-clock remain open.
- **Detailed plan:** [Pinned test dispatch](../../roadmap/pinned-test-dispatch.md)
- **Remaining acceptance scope:** Every unchecked item in the detailed plan's
      Evidence section remains owned here, including completeness, composition,
      concurrent-writer, and infrastructure-retry proof. Reconcile already-proven
      outcomes across both checklists before closing this parent.
- **Depends on:** GRAPH-001's canonical effective-authority DAG as the substrate this
  system walks rather than re-deriving; CACHE-007's source-admission evidence (currently
  unmerged WIP) as the artifact-creation event that pushes a new pin into the scheduler;
  REBUILD-RECEIPT-001's finalized candidate envelope as the `tested` tag itself, re-keyed
  by pin hash instead of its current ad hoc lock-list identity. Directly affects trust in
  RELEASE-001's resumed gate runs.
- **Evidence:**
  - [x] `tests.critical.test_pinned_test_dispatch` — pin whose closure identity
        changes re-enters untested; sibling never opened.
  - [x] Tested pin skipped without reading declared inputs.
  - [x] No CACHE-007 admission → never scheduled; admitted pin enqueued.
  - [x] Service re-keys the existing receipt (`rekey_receipt_to_pin`,
        `literate-ai:tested-at-pin`). Live rebuild still writes lock-list
        `subject_identity` until callers use the helper.
  - [ ] `make release-check` and python-check consult this service.
        `litai build`/`test` and CI are not wired in this slice.
  - [ ] Full `make release-check` wall-clock time on a no-op resume (no source changed)
        is dominated by DAG-walk cost, not by re-running any pipeline.
        Clean runs still reset local markers; not measured.
