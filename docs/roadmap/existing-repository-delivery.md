# Existing repository delivery program

- **Status:** active
- **Owning queue item:** [SDLC-001](active-work.md#sdlc-001-make-existing-repository-delivery-the-primary-14-adoption-path)
- **Completion / archival evidence:** pending implementation and pilot qualification

[ADR 0074](../decisions/0074-existing-repository-delivery.md) records the directing
user's implementation delegation and the target architecture. The baseline review
is tied to `f34debb73b62f9fff59a138f86b3640d7be65183`, not to unfinished worktrees.

## Stronger-model system review and implementation handoff

Review date: 18 November 2026.

The directing user requested a GPT-6.2-Astra review augmentation before a smaller,
faster model implements its actionable conclusions. The [system assessment](../architecture/existing-repository-review.html)
challenges the earlier findings against current source and retained executions;
[the evidence index](../../verification/system-review-augmentation.json) records
scope, measurements and limitations. This is a review/roadmap checkpoint, not a
new source, installed-wheel, platform or release qualification.

**Current execution instruction.** Qualify one combined candidate from commit
`91e06e9c4`. That parent’s fresh source run passed 3,148 tests with 101 declared skips
and zero failures in 73 minutes 22 seconds. The subsequent wheel check
refused an installed test inventory that omitted the new CUDA portability
case. The combined candidate also adds the shared qualification diamond case.
Source discovery found exactly those two additions across nine maintained
scopes and 24 fixture classes, yielding 215 cases. The corrected installed
diagnostics and CUDA cohorts passed 32 and 16 cases respectively. Removing
a different expected method still made the installed check refuse.

Check the schema catalog, interpreter origin and maintained case names before
the next long run. Use the exact installed wheel for the executable check.
Preserve the first wheel refusal and the interrupted successor. The earlier
3,228-case run had revealed a catalog omission reproducible in 1.49 seconds.
On the first 3,249-case attempt, a shared editable install pointed an isolated
child at a different checkout after 360 passing tests and 29 skips. The
packaging receiver detected it. The successful rerun used its own checkout
environment and verified both import origins.

For [issue 484](https://github.com/jordanhubbard/literate-ai/issues/484),
34 focused tests passed after independent review found and the author fixed
two failures in lock cleanup and checkpoint rollback. For
[issue 485](https://github.com/jordanhubbard/literate-ai/issues/485), the
corrected launcher exercised the intended code from both editable interpreters,
including from a consumer with a conflicting package name. The reviewed
artifact check binds one staged file to the producer’s actual test job.
Installed qualification, hosted results and publication custody remain separate.

Use the combined local and hosted timeline for work packages C and E. In the
1.2 lead-up 5.04 hours of previously unattributed time overlapped hosted jobs
outside the local runs. A further 60.71 hours still lack either kind of
observation. Windows CI failed on the exact tag 18 minutes after publication,
as the release policy allowed hosted CI to be optional. Test the effect of a
required prepublication cell failing or running late, including exact attempt
and artifact selection. Post-tag failure belongs to recovery and readback.
[Windows result](https://github.com/jordanhubbard/literate-ai/actions/runs/38234884516/job/114763068950)

For work package E, bind the annotated Git tag object as well as its target
commit and the tested artifact digest. An independent local Git receiver
replaced the annotation after a push. The candidate accepted it because both
Git and the provider double read back the replacement at the intended commit.
Keep exact-object authorization through each provider mutation and through a
retry. A matching object may resume. A different object at the same commit
must stop the operation before the next write. Retain the normal push control.

For work package C, include caller-wide permissions and job selection when
deciding whether a reusable CI workflow is affected. A changed caller permission
selected the broad ordinary matrix while skipping the SDK workflow. Exercise
the affected cell or select it conservatively when the scope is ambiguous.
The independently reviewed selector implements this fallback. All 26 independent
selector tests passed, including caller-wide permissions. The hosted execution
of the selected steps remains to be observed on the composed candidate.

Under work package F, retain an
observed expired lease generation across clock rollback and later uncertain
responses, then require the provider’s exact acknowledgement for cleanup. The
stub-control suite passed all 44 worker cases. Older readers reject the new
journal state, so recovery of a journal containing it requires a capable reader.
Under CUDA-SIGNAL-001, the independently reviewed source now retains the five
missing toolchain, runtime-type and driver-call signals from
[PR 410](https://github.com/jordanhubbard/literate-ai/pull/410), together with
multiline attribution exclusions. Seven source tests passed on composed bytes.
Installed and exact-head qualification remain open.

Under work package G and RELEASE-CLOSURE-001, make the work writer and release
sweep use the same visible goal sections and complete identifiers. In real Git
fixtures the sweep accepted a checked example inside a fence or comment while
the visible goal remained open. Public close could change a prefix-sharing goal
or miss unchecked acceptance under a prose subheading. Recheck normal closure,
the three refusals, duplicate visible identifiers and the complete 1.4 manifest.
A read-only audit of the actual queue found identical dispositions with examples
filtered, and close refused all 46 open goals. [Issue 486](https://github.com/jordanhubbard/literate-ai/issues/486)

Preserve complete acceptance text in the operator summary for package G. Its
1.4 projection omitted wrapped lines on at least 34 unfinished checkboxes across
TEST-CACHE-001, RELEASE-CLOSURE-001, WORKER-001 and WORKTREE-002. Changing a
real continuation in a disposable copy changed the outstanding work while
leaving the entire public report and its identity byte-identical. Require the
summary to display the complete visible requirement and its identity to change
when that requirement changes. Retain the 81 selected goals, the 46 open states
and the existing exclusions for fenced examples and comments.

Under PROJECT-LAYOUT-001, verify that public work closure updates the declared
framework queue when a host backlog contains the same ID. Preserve the host
backlog byte for byte and refuse redirected or missing destinations.
[Issue 487](https://github.com/jordanhubbard/literate-ai/issues/487)

Under RELEASE-CANCEL-001, exercise the actual nested gate launcher. On macOS,
interrupting a direct step reaped its finite child. Interrupting the same step
under a bounded supervisor left the child alive under PID 1. A source-gate
interruption also left the checkpoint runner and two workers alive until
explicit cleanup. Verify cancellation through the outer entry point, exit
status, terminal evidence and absence of owned descendants before retry.

The first three delivery priorities are the cheap source and interpreter checks
in C, the contained native adoption and result-observation path in A and D,
and exact promotion custody in E. The paired Cargo measurement in B kept all
59 validations and saved 7.82 seconds in one run. Keep that implementation
bounded and require repeated improvement before assigning it release-time credit.

**Security check disposition.** PR 421's two occurrences refer to one incident
on two commits. Both match the SHA-256 of the same public PyYAML module. PR 475's
three reported values match three public Literate AI module files at the
framework revision recorded by their evidence producer. Each comparison used the
exact GitHub line linked by GitGuardian. Retain these five comparisons for
incident-specific security review and keep both original check results visible.
[Reproduction inputs and provider check IDs](../../verification/release-security-finding-provenance.json).

### Consolidated release work packages

These refine existing 1.4 owners; they introduce no parallel goal manifest and
retire none of the 81 existing release obligations. SDLC-001 owns this acceptance
where an associated historical owner has another release target. Do not reopen
completed SKILL-DISCOVERY-001 merely to track the remaining activation work.

| Order / owner | Action and boundary | Acceptance before closure |
| --- | --- | --- |
| A — PROJECT-LAYOUT-001 / SDLC-001 | Close CP-4 and record the finite authority scopes for layout observation: application and distinct framework Git HEAD/index, current manifest, directory topology, producer provenance and unknown members. Apply the same scope/boundary review to existing update/removal writers before extending them. Use current owners rather than a universal snapshot service. | Real enclosing/nested/linked Git fixtures change one authority at a time; staged-only and during-observation drift refuse or change identity as appropriate. Preserve no-write behavior, native source, custom files, root modes and collisions. Renew independent source review and final composed qualification. |
| B — CARGO-CUSTODY-PERF-001 / TEST-CACHE-001 | Separate pure identity projection from implicit recursive observation within the existing live Cargo owner. First test the chain `current_identity -> scope.identity -> scratch.context.identity -> require_unchanged`; retain the validating public accessor. Reuse captured immutable fields only inside the already bracketed operation, never a saved currentness verdict. | Paired runs show identical identities/refusals and count the exact observations removed. Preserve pre/post process, mutable callback, permission/revocation, lifetime, membership, namespace and tool checks. Report currentness and complete admission time separately; no optimization is accepted without a measured gain. |
| C — TEST-CACHE-001 / TEST-PARALLEL-001 / SDLC-001 | Freeze the authored batch after independent boundary/counterexample review, run cheap guards, then the required complete source gate and one exact wheel. Share those wheel bytes across equivalent installed cells. Keep source qualification per CONTRIBUTING; whole-wheel qualification is a separate requirement, not universally a per-commit rule. | A candidate ledger names source/tree, selected inputs, test inventory, environment, wheel, superseding changes and invalidated cells. No failed/interrupted run becomes passing. Compare total lead time, summed runner envelopes, duplicate jobs and unknown time; scheduling, fixtures and custody costs remain separately measured. |
| D — ORIGINAL-ADOPT-001 / ADOPT-CLI-001 / SDLC-001 | Prove the first useful governed native PR independently of legacy canonical-layout migration. Native adoption already leaves source and CI in place; do not serialize its value pilot behind the harder legacy migration writer. Exercise explicit skill loading first, then a host-required minimal discovery delegate only if needed. | Installed public onboarding, native defect/fix, base-policy CI observation, required-check failure/retry, upgrade and removal preserve the host's existing commands and exact external-file allowlist. Show which layer prevents merge/release and which only advises. Automatic activation needs actual host evidence; simulated transport and supplied guidance do not qualify it. |
| E — RELEASE-CLOSURE-001 / existing release-artifact owners | Close the distinction between required CI cells and promoted binary custody. Strict coverage currently refuses publication, and its proof explicitly says `tested_artifacts: false`; do not enable it as if delivery were complete or weaken the refusal. Extend the existing artifact/release owner before claiming end-to-end promotion. | A controlled release target accepts the exact tested artifact and rejects substitution, changed source/environment/policy, stale attempts and interrupted export. Record tag/publication/readback and recovery responsibilities separately. Live publication remains separately authorized. Preserve legacy-policy compatibility explicitly; no silent fallback from strict coverage. |
| F — COMMAND-WORKER-001 / WORKER-001 / RELEASE-CANCEL-001 | Keep static execution and managed lease allocation as backends of the existing dispatch contract. Make physical lease expiry a provider responsibility that survives controller death; retain logical drain/cancel, custody import and exact cleanup acknowledgement. Add a finite operator recovery path for every uncertain state. | Faults at allocate/reply, SSH start, result/import, import/ack and terminal release converge to a verified resource state or explicit bounded escalation without duplicate allocation or rerun. Stub expiry proves protocol only; actual provider TTL/termination remains unqualified until separately authorized and observed. |
| G — SDLC-001 / RELEASE-INTEGRATION-005, coordinating AUD-STATE-001 | Produce one concise current execution projection from the existing queue/manifest; archive obsolete narrative while retaining IDs, links and unchecked acceptance. Reconcile stacked reviews by exact ancestry and unique diffs rather than treating every open PR as another implementation. | All 81 obligations retain their target/status/acceptance; the projection names one next action and blockers per active owner and refuses stale/duplicate IDs. Compare retained acceptance before/after archival. The 21 open heads already contained in this review base require disposition, not blind replay; non-ancestor heads still require semantic comparison. |
| H — SDLC-001, coordinating existing capability/collateral owners | Keep native delivery's default path independent of generation, inverse conversion, SDK/media and dynamic allocation setup. Qualify optional capabilities through their existing profiles; publish evidence by source/artifact, language, OS, architecture and accelerator. Retain current-release obligations. | An unchanged native fixture completes its governed path without generation/media/provider setup or duplicate native execution. Optional imports may be deferred only with measured reliability/startup benefit and installed origin checks; the observed 0.39–0.47s import is not a release bottleneck. Actual activation and unsupported platform cells remain explicit. |

A is the prerequisite for the current layout batch. B can be developed and measured
independently; C consumes all reviewed changes before expensive qualification.
D's fresh-native value pilot can run alongside the separate legacy migration and
changed-version upgrade work. E and F preserve their existing custody dependencies.
G's opt-in execution view reads the configured release goal manifest and its
queue. Use `python scripts/summarize_release_roadmap.py 1.4.0 --execution-view`
from the project root to see each open owner's stated next action or first
unchecked criterion. Declared work and release dependencies retain their
current authority, and external inputs remain unverified.
H changes defaults
and evidence presentation, not the approved release scope. New implementation is
left to the smaller-model handoff requested by the user.

**Source-test origin in package C.** [Issue 485](https://github.com/jordanhubbard/literate-ai/issues/485) documents the reproducer. Reusing an editable interpreter from another
worktree changed the result of the same public removal plan in a real Git fixture.
The test parent imported the intended owner. A child CLI launched from the
consumer imported the other worktree and exhibited its protection. Bind the
child origin in the existing source-test invocation, or refuse the mismatch
before recording a pass. Exercise a correct interpreter, a deliberately foreign
editable interpreter and an installed wheel from outside the checkout. Preserve
the installed path’s isolated imports and its separate qualification. This is a
source-receipt integrity requirement under TEST-CACHE-001 and SDLC-001.

**Native value pilot in package D.** A local installed journey exercised the
host’s native test and public adoption, CI observation, revision update and
removal. It took 22.673 seconds and added 15 framework files under `litai/`,
with zero external changes from adoption and zero duplicate verifier jobs.
The native defect and repair were real. GitHub transport and job identities
were simulated. The later hosted pilot below covers actual required checks and
failed-job retry. Automatic activation and a changed-version contained upgrade remain open.

A later installed C++ pilot restored the exact original Git tree after both
cold and post-update removal. The framework's one-byte lifecycle lock still
occupied `litai/`, so the exclusive adoption destination correctly refused
another bootstrap. Under ORIGINAL-ADOPT-001 and ADOPT-CLI-001, make the
owned lock-only state recoverable while excluding active and already-open
lifecycle contenders. Prove repeated cold and post-update adoption and preserve
foreign or redirected runtime contents and strict destination collision checks.

A second installed pilot used the public ToolScheme v0.3.0 source at
`b0a4d06db331a072681990cdb6773db0c0eaf551`, with its actual Makefile,
C++ tests, release workflow and existing roadmap. The host had already run
Linux and macOS on x86-64 and ARM64 and published the tag.
[Main run](https://github.com/jordanhubbard/toolscheme/actions/runs/35908701993)
and [tag run](https://github.com/jordanhubbard/toolscheme/actions/runs/35908702822).

On a local clone, the installed intermediate framework wheel at `96c404e18`
added 15 files under `litai/` in a 0.90-second plan and 1.66-second apply.
The host's 1,683 native checks passed before and after adoption. A seeded
integer-rendering defect failed eight existing checks. Repair restored the
full native pass. A separate clone confirmed all 98 external filesystem entries
retained their types, modes and contents through repeated adoption refusal,
same-version update and removal. Removal preserved a one-byte framework lock
under `litai/.litai-locks/` as its runtime-state policy declares. Both clones
retained the host's original CI and roadmap. The four hosted platform jobs
preceded adoption. The separate hosted CSV pilot below covers a governed PR.
Changed-version upgrade remains open.

For work package D, credit each pilot failure to the check that first caught it.
With the same defect in an unadopted ToolScheme checkout, the host command
failed the same eight checks and emitted identical diagnostics. It took
29.29 seconds there and 29.16 seconds after adoption. This trial gives the
framework zero additional application defects caught. For the governed pilot,
record separately any wrong-commit, stale-attempt or substituted-artifact
decision that native CI alone would accept, the time to feedback, and the
number of repeated native jobs. A pilot can earn credit for consuming an exact
existing result or avoiding a second build. Record zero when neither changes.

In the installed native observer control, four distinct PR, failure and retry
jobs executed. Observing those results added zero native jobs. In a separate
local Git/provider experiment with a real built artifact, the release gate
refused substituted bytes in 1.754 seconds, stale artifact size evidence in
1.731 seconds and re-use of an earlier successful attempt in 1.522 seconds.
The independently reviewed successor refused a replacement annotation pointing
to the correct commit. A fresh verifier accepted the original using an
operator-trusted object ID, and refused a missing or incorrect ID. These
measurements cover the controlled promotion path. The later hosted consumer
pilot observes native jobs separately. Final release qualification remains open.

On a fresh clone of the same ToolScheme revision, source tree `c548bc608`
planned native adoption without writes and separately completed the explicit
`onboard adopt --profile convert` operation in 154.2 seconds. The original
source, roadmap and CI workflow moved together under
`components/legacy-project-wrapper/implementation/`. This opt-in effect is
documented in the getting started guide and the conversion skill. These
experiments satisfy the three implementation criteria of ADOPT-CLI-001.
The release item remains open for its end-to-end evidence.

### Hosted governed PR and partial retry

The installed wheel from `96c404e18` observed a private draft PR through the
actual GitHub API. Both required jobs ran Python 3.11 against the application's
existing tests. The CSV parser failed on a UTF-8 byte-order mark on Linux and
Windows. The native failure identified the parser defect. Its repair passed on
both platforms. Strict branch protection required both GitHub Actions jobs,
including for administrators. Across the four observations GitHub reported
the merge state as blocked on failure and clean on success. The PR remained a
draft throughout.

A separate fixture test failed only on the first Windows attempt. Rerunning
failed jobs kept the same source and run. GitHub gave the earlier Linux job
a new row ID carrying the same runner and step timestamps. Windows ran
again and passed. Four installed observations took 23.487 seconds in total
and triggered zero additional native jobs. These counts exclude the two
successful base-branch setup jobs. Eight PR job rows represent
seven distinct native executions, spanning 90 summed job-seconds and 72
seconds with at least one native job active. An earlier locally checked-out
green revision was rejected against the newer green PR in 1.533 seconds.

The pinned checkout action logged the Git commit actually tested by each of
the seven native executions. All three PR heads were tested through a synthetic
merge commit with the expected base and head parents. In each case its tree
matched the proposed head tree exactly. The observer itself reported the
tested tree as unknown. The independent log and Git object comparison supplies
that evidence for this fixture.

This satisfies the real hosted governed-PR and partial-retry pilot for package
D. Continue with the changed-version contained upgrade, automatic skill
activation and final-candidate qualification. The observer leaves tested
artifact identity and merge authorization with their existing owners.
[Hosted evidence and timing boundaries](../../verification/native-ci-hosted-governed-pr.json).

### Show what changed in the workflow behind a required job

In a real local Git fixture, an installed observer correctly reported a
failing application test. Removing just the test step from the selected
workflow kept the two required job names and their compile step. Compilation
succeeded, the unchanged application test still failed, and the observer
returned `verified` for the simulated successful jobs. Restoring the original
workflow and repairing the application made both checks pass. GitHub responses
were simulated in all three cases. The observer made no merge or release
decision in any case.
[Exact commits, workflow blobs and CLI results](../../verification/native-ci-workflow-definition-observation.json).

Package D should show the base and head Git blob identities of the configured
workflow and distinguish changed, unchanged and unavailable definitions. Keep
the named job outcomes visible. Route a changed definition to the host's
workflow review, and keep the initial unconfigured-policy path available.
Changes to scripts and reusable workflows can also alter job behavior. Report
the reach of the comparison explicitly. Exercise all three fixture cases
without running duplicate native jobs or treating the report as merge approval.

The reviewed implementation exposes the base and head blob IDs in
`workflow_definition`. Four local Git and simulated-provider cases exercised
both an omitted test and a benign timeout change. Both changes required
workflow review. Native job outcomes still determined the observation status.
The four cases reused two actual native application-test results. Installed
and final-candidate qualification remain open.

### Make native removal followed by adoption work in the same checkout

The installed framework adopted the existing Confusion MDL C++ interpreter on
Apple Silicon in 0.904 seconds to plan and 1.823 seconds to apply. All 15
framework files landed under `litai/`. The host Makefile built an ARM64
executable before and after adoption. A seeded arithmetic defect compiled
successfully and changed the interpreter's answer from 42 to 43. The pilot's
output assertion caught it. Framework project validation passed with both
the original and defective sources. Repair restored 42, including after
framework removal.

Removal restored the original Git tree and all 33 original files with their
modes. After committing the removal, a second adoption in the same checkout
refused with `original_adoption.already-initialized`. Both a direct removal
and a removal following update left one untracked lifecycle lock under
`litai/`. A fresh clone of the exact removed commit planned adoption.
Introducing an empty `litai/`, the retained lock, or a host file in that
directory each reproduced the refusal. This establishes the consequence of
the lock already observed in the ToolScheme pilot.
[Recorded executable results and four controlled comparisons](../../verification/native-cpp-adoption-cycle.json).

Under the existing package D repeat/removal criterion, support a full
adopt–remove–adopt cycle in the same checkout. Cover the cold and warm cases
and provide a recovery path for existing retained locks. Preserve active
lock owners, host files, redirected paths and exclusive destination
publication. Acceptance requires a second successful apply followed by a
native run on the original application. Keep this criterion open through
installed qualification.

### Preserve a converted project's release process during migration

A disposable project converted by the published 1.3.1 framework kept its
canonical manifest profile, generated initialization baseline and release policy
bytes through a partial move under `litai/`. The original `release state`
reported a free main branch. The moved copy refused both state and plan with
`release.native_profile_unsupported`. On each copy the two commands preserved
working files, Git HEAD and the raw index.

The original template policy also checks hosted contributions. In a second
pair, both copies used the same explicit pre-release mode and local-only policy.
The original produced a patch plan and the moved copy still refused. Keep the
original tracker check for teams whose policy requires it. The minimal native
bootstrap separately passed its existing release-refusal control.
[Commands, exact results and fixture changes](../../verification/contained-converted-release-observation.json).

Package A owns the placement decision and package E owns release authority.
Use the initialization profile and the recorded placement when resolving the
version manifest and the Component named by the gate. The same policy bytes
can address different files after a move. Require a stale plan or a competing
root file to refuse before a write. The migrated project must pass the same
legitimate state, plan and local recovery checks as its predecessor and
preserve host files through rollback. A native-only application continues to
release with its own tooling.

### Tracker and obsolete-instruction reconciliation

The read-only refresh found 87 open issues and 48 open PRs. Twenty-one PR heads
are ancestors of review base `8ba81d598`: 475, 471, 470, 465, 464, 463, 457,
437, 435, 434, 431, 428, 425, 423, 416, 414, 413, 398, 391, 349 and 333.
This is exact Git ancestry, not permission to merge/close, proof of resulting-main
checks, or evidence that the other 27 reviews are obsolete. Retain each distinct
review/evidence requirement in the integration owner; compare non-ancestor diffs
before assigning a superseded disposition. Do not land every contained ancestor
again merely to empty the forge queue.

A follow-up compared all 27 remaining heads to the release base. Twenty-five
trial merges conflicted. The two clean trials, PRs 473 and 474, both change
the CI workflow. The histories contain 187 distinct commits, including 42
repeat appearances across branches. PR 467 contains PRs 444 and 445, and
PR 440 contains PR 401. PR 472’s single distinct commit has its Make and
test file tree entries already present, its changelog and program section
retained, and its former next action superseded by the observed early refusal.
It needs no code replay onto this candidate. Actual forge disposition and
resulting-main qualification remain with RELEASE-INTEGRATION-005.

**Exercise the action that an update changes.** In private trial merges onto
source tree `c548bc60865bf754acafe5b9d45de355c82e2bb4`, applying PRs
473 and 474 in either order produced the same tree. All three action references
remained pinned and their declared inputs accepted the existing workflow arguments.

The existing CI selector classified both PRs as policy-only. In the actual
Bazel pin run, the new setup action was skipped while an unrelated FreeBSD ACL
step ran for 66 seconds. The FreeBSD pin run exercised the changed action on
14.3 for 325 seconds. Its separate 15.1 installed-SDK workflow is manual.
The local selector reproduced the same matrix choices for a PR and a push to
main. Under RELEASE-INTEGRATION-005 and SDLC-001, select an existing native
cell that calls the changed action, then verify the step conclusion at the
candidate revision. Keep the 15.1 SDK evidence separate and preserve full
qualification for release refs. Unknown or shared workflow edits must retain
broad coverage. [Bazel run](https://github.com/jordanhubbard/literate-ai/actions/runs/44261266692)
and [FreeBSD run](https://github.com/jordanhubbard/literate-ai/actions/runs/44261298366).

The following newer records lacked links across the current roadmap snapshot;
reuse the named owners rather than creating a second backlog:

| Records | Owner and disposition |
| --- | --- |
| [#469](https://github.com/jordanhubbard/literate-ai/issues/469) | SDLC-001 / RELEASE-INTEGRATION-005: inspect migration discovery's foreign-descriptor boundary; preserve native dependency trees. |
| [#468](https://github.com/jordanhubbard/literate-ai/issues/468) | ORIGINAL-ADOPT-001 / NATIVE-CHILD-UPDATE-001: retain reviewed multi-boundary native revision and parent-integration acceptance. |
| [#466](https://github.com/jordanhubbard/literate-ai/issues/466), [#461](https://github.com/jordanhubbard/literate-ai/issues/461), [PR 467](https://github.com/jordanhubbard/literate-ai/pull/467) | RETAINED-SDK-PUBLIC-001 / RELEASE-INTEGRATION-005: explicit SDK output custody, real UFS stability and FreeBSD prerequisite evidence. A proposed prerequisite change does not qualify a native cell. |
| [#462](https://github.com/jordanhubbard/literate-ai/issues/462) | RETAINED-OBSERVATION-PERF-001 / SDLC-001: bound allocation by actual input size under existing byte ceilings; measure memory separately from wall time. |
| [#455](https://github.com/jordanhubbard/literate-ai/issues/455), [#454](https://github.com/jordanhubbard/literate-ai/issues/454) | PACKAGE-001: preserve declared Python floor and actual importable package surface in installed artifacts. |
| [#452](https://github.com/jordanhubbard/literate-ai/issues/452), [PR 453](https://github.com/jordanhubbard/literate-ai/pull/453) | NPM-PACKAGE-001 / NATIVE-SDK-001: ADR 0073 remains a proposal until reviewed; retain SDK composition request without inferring implementation. |
| [PR 474](https://github.com/jordanhubbard/literate-ai/pull/474), [PR 473](https://github.com/jordanhubbard/literate-ai/pull/473) | RELEASE-INTEGRATION-005: review dependency-action updates and affected native cells; dependency automation is not acceptance. |
| [PR 472](https://github.com/jordanhubbard/literate-ai/pull/472), [PR 471](https://github.com/jordanhubbard/literate-ai/pull/471), [PR 470](https://github.com/jordanhubbard/literate-ai/pull/470) | SDLC-001: compare to the contained PR 475 composition; preserve unique early-refusal and dependency-audit behavior. PR 472 is not an ancestor by head identity, so equivalence requires a diff. |
| [PR 464](https://github.com/jordanhubbard/literate-ai/pull/464), [PR 463](https://github.com/jordanhubbard/literate-ai/pull/463), [PR 460](https://github.com/jordanhubbard/literate-ai/pull/460) | RELEASE-CLOSURE-001 / SDLC-001: keep exact-attempt CI and coverage requirements; the strict-promotion refusal remains open acceptance. |
| [PR 459](https://github.com/jordanhubbard/literate-ai/pull/459), [PR 458](https://github.com/jordanhubbard/literate-ai/pull/458), [PR 457](https://github.com/jordanhubbard/literate-ai/pull/457), [PR 398](https://github.com/jordanhubbard/literate-ai/pull/398) | RELEASE-INTEGRATION-005 / SDLC-001: preserve portable native refusals, fixture bytes, custody and CUDA signal corrections; compare unique changes against the composed candidate. |

Supersede the instruction that the skill behavior comparison is still pending:
45 adjudicated supplied-guidance attempts are complete; automatic activation and
larger-task replication remain open. Supersede the instruction to repair the old
OpenSpec advisory as if it were still the current failure: upstream withdrew that
advisory; exact B CI run `44381132281` passes. Keep both dependency audits and the
separate unresolved GitGuardian disposition. The successful B and C source runs
do not qualify the later combined candidate or its CP-4 correction.

## Evidence and outcome

The [complete baseline review](../architecture/existing-repository-review.html)
contains the executive verdict, lifecycle map, platform matrix, coverage ledger,
gate dispositions, findings, uncertainty and first three recommended changes.

The review inventoried 5,329 tracked files and structurally indexed 1,932 Python
files, inspected representative entry points across 21 subsystem groups, and
passed 63 maintained tests. A seven-file native adoption fixture preserved all
bytes but moved its GitHub workflow out of `.github/workflows`; adoption reported
130 created files and the resulting fixture had 146 files outside `litai/`.
A real child-process allocator stub timed out after one side effect. Repeating
the request did not allocate again, and recovery correctly refused absent a
validated response. Provider lookup and resource release remained unavailable.

In the observed 1.2 release lead-up window, 31 local gate/check attempts were
retained, 27 with terminal timestamps. Their nonoverlapping root spans cover
34.02 of 99.77 hours; 65.75 hours cannot be attributed to inference, humans,
other workers or idle time. Python gate spans total 24.22 hours. The shorter
successful 1.3.0 cut took 58 minutes, with 30 minutes in its observed local gate
and 28 minutes lacking child-level attribution. These are observed windows, not
claims about a statistically typical release.

Exact baseline CI run `43353550664` passed all 27 jobs. Its jobs sum to 10.34
runner-hours; the final job ended after 83m06s. The longest job spent 51m46s in
conformance and 28m11s in installed-wheel verification. Queue/setup did not
dominate that job. The historical 1.3.1 Windows exception remains an explicit
coverage waiver, not a Windows pass.

The review report distinguishes its 16 November baseline from later experiments.
A status reconciliation on 18 November found an obsolete passage in the dated
17 November update that still called the guidance comparison unfinished. The
completed 45-attempt comparison is recorded in the report's later evidence
section; automatic skill activation remains untested. This narrative correction
changes no acceptance requirement, release goal, disposition or completion state.

## Consolidated ownership

| Workstream | Existing owners to reuse | Added acceptance |
| --- | --- | --- |
| Native adoption and containment | ORIGINAL-ADOPT-001, ADOPT-CLI-001, ADOPT-RELOCATE-001, PROJECT-LAYOUT-001; ADRs 0057 and 0071 | Public minimal onboarding preserves native source and CI; repeat, upgrade, recovery and removal use an exact external-file allowlist. |
| Qualification cost and evidence | TEST-CACHE-001, TEST-PARALLEL-001, RELEASE-CLOSURE-001, RETAINED-RECEIPT-PROMOTE-001, existing observation-cost items | Correlated timing, early cheap refusal, exact candidate/environment/artifact cell reuse, no duplicate native assertions. |
| Worker lifecycle | WORKER-001, COMMAND-WORKER-001, WORKER-TELEMETRY-001, RELEASE-CANCEL-001 | Observe lost replies, release owned leases idempotently, enforce expiry, preserve static workers and uncertain refusal. |
| Roadmap and guidance | AUD-STATE-001, RELEASE-INTEGRATION-005, SKILL-DISCOVERY-001 | Unique IDs, current execution view, explicit supersession, no conflicting Superpowers activation, behavioral skill comparison. |
| Support and optional capabilities | Current native/GPU/SDK goals and RELEASE-COLLATERAL-001 | Revision-bound support cells; native adoption does not require generator/media setup; production deployment boundary is explicit. |

The table combines execution ownership; it does not mark the listed goals
complete. Every goal record in the current release manifest remains an obligation
until its own terminal evidence or an explicit recorded disposition establishes
otherwise. Add new obligations to the same manifest instead of inventing a
second release-readiness authority.

## Execution order

1. Record the report evidence, reconcile duplicate and obsolete roadmap entries,
   preserve historical aliases and unchecked acceptance, and validate the dependency
   graph. Survey open issues, reviews and relevant worktrees before implementation.
2. Complete the shared project context and owned-path inventory for ADR 0071.
   Reuse original/retained source owners and the existing reviewed layout work.
   Make native onboarding opt into deeper generation rather than converting source
   by default. Qualify installation, update and removal through the public CLI.
3. Instrument missing release spans and expose a deterministic critical-path and
   runner-use report. Distinguish terminal execution, pending/unknown, human wait
   and gaps. Move cheap guards early without removing final currentness checks.
4. Introduce candidate-scoped qualification planning and share a single exact
   wheel across equivalent installed checks. Require adversarial stale-input,
   changed-toolchain, revoked-signature and artifact-substitution controls before
   reusing pre-CI results or retiring duplicate work.
5. Complete worker observe/release/expiry in the existing versioned command
   protocol. Use stubs for timeout, crash, duplicate, vanished-worker and cleanup
   failures; a live provider pilot requires separate authorization.
6. Qualify skill activation/export naming and publish supported platform cells.
   Keep original generator and independent-oracle acceptance for generation changes.
   Add a stub deployment failure/recovery contract without claiming production
   deployment support that has not been exercised.

## Pilot criteria

Use a Python/Make repository with a known failing test, a Rust/Cargo repository
with uneven coverage, and a platform-specific C++/CUDA or Windows repository.
Preserve native build/test/CI behavior and host-owned files. Measure onboarding,
first verified PR, failures caught, manual interventions, duplicate jobs and
release p50/p95 against the prior native workflow.

Targets are under 15 minutes to onboard and under 30 minutes to the first verified
native PR on warm suitable hardware, no source relocation, no unexpected edits
outside `litai/`, no diff on repeat installation, safe upgrade/removal, every seeded
fault detected, at least 50% fewer duplicate native jobs and at least 30% lower
median release wall time. These are acceptance targets, not measured promises.

The supplied-guidance behavioral comparison is complete: three tasks, three arms
and five randomized repetitions per cell, with independent adjudication. Its
configured model selector was held fixed; provider weights were not pinned.
Current guidance and no optional skill both achieved 13/15 overall successes.
Retain the measured evidence in the report. Remaining pilots exercise actual
host activation and representative larger/platform-specific tasks, preserving
the current/alternative/no-skill arms, held model/tool configuration, randomized
order and at least five independent repetitions per cell where feasible. Record
any provider-weight revision that is unavailable. Continue measuring activation,
task success, unsafe actions, unnecessary steps, tokens, elapsed time and manual
interventions. Do not rerun the completed cohort merely because an older progress
paragraph called it pending; it remains bounded evidence rather than universal
completion of that measurement contract.

## Recovery and scope boundaries

Migrations use a read-only exact plan, existing lifecycle locks and owned-state
recovery; preserve concurrent application changes. Renew affected path-bound
evidence instead of rewriting old receipts. Remove only still-owned unchanged
framework content and delegates; retain custom files for explicit disposition.

Static workers remain supported. Local simulation does not prove GPU execution,
remote cancellation, cloud cleanup or production rollback. Currentness, exact
artifact custody, independent acceptance, bounded execution and update conflict
preservation remain mandatory through simplification. Do not widen budgets or
drop platform/feature goals to manufacture a faster green release.

## Native CI verification implementation

The earlier [exact CI selection repair](../history/roadmap/pr-460-ci-selection.md)
and its three verification records are retained from PR #460. History
reconciliation preserves the current extracted collector, tested-file and
cell-coverage owners, complete tests and original lifecycle pin. This adds no
current source or release qualification.

SDLC-001 and ORIGINAL-ADOPT-001 own the next contained-adoption slice; no new
roadmap owner or local execution lifecycle is introduced. The independent design
review selects a read-only `litai project ci verify --pr NUMBER` observation of
native CI. The initial supported contract is one GitHub Actions workflow and a
finite exact required-job set in the existing contained repository policy.
Complete, provenanced forge-required-check discovery is preferred when supported;
an empty or incomplete reported-check list is unconfigured, never success.

The base commit's policy governs a PR so its head cannot certify a reduction in
requirements. Bind the actual configured remote, open same-repository PR, local
HEAD, base/head identities, workflow, run, attempt and job provenance. Refuse
missing, skipped, failed or ambiguous required jobs and drift during observation.
Keep native execution, retries, matrix selection and merge policy in the host CI.
Return observations on stdout without another cache, receipt or scheduler.
Native bootstrap remains unadmitted; release entry refusal stays intact.

Observed PR 458 metadata associates CI run `44000908565` and all 13 jobs with
head `48e3d1ef30fb0f11ba27cc55dcfdab9253c15a68`; it does not identify the tree
actually checked out. The verifier must report that distinction. GitHub CLI's
required-check view reports no required checks for that PR, so it supplies no
acceptance set. That observation does not establish that all forge rules are absent.

**In progress:** compose the reviewed CI selector with retained process cleanup,
add the opt-in policy and thin observer, then exercise a legacy fixture's successful
PR, failure/retry, missing-job refusal, policy reduction, upgrade and removal.
Require real provider history before claiming how partial retries are represented.
The acceptance target is zero duplicate native jobs and no edits outside `litai/`.

The development observer and extracted shared collector pass a 32-case public
native/release cohort in 31.245 seconds. The native fixture uses real Git and
public onboarding/verification/update/removal entry points with simulated GitHub
transport; it is not a hosted CI or installed-wheel qualification. Missing and
skipped jobs, stale attempt, base-policy reduction and hidden local policy edits
refuse. Upgrade preserves configured policy; removal preserves modified authority
by refusing pending explicit disposition. The first bounded real-provider history
search found a whole one-job retry. An expanded search and independent inspection
of runs `42474316001` and `42472364032` subsequently found 16 earlier successful
executions represented by new job IDs in the current attempt. The unchanged
collector accepts these provider-confirmed rows; older-only or unconfirmed rows
remain incomplete. This historical collector observation is not a hosted adopted-PR
pilot: the old runs no longer supply the required PR association. Independent review
reproduced a base-policy
bypass through Git replacement refs, an implicit promisor fetch and a case-only
remote refusal. The corrected observer ignores replacement refs, disables lazy
fetches, distinguishes absent from unreadable base policy and preserves immutable
repository-ID checks across spelling differences. Actual private Git fixtures
cover missing commit/tree/blob objects without object-store writes; an unsupported
Git refusal is simulated. This command requires Git 2.45+. Independent source and
composition reviews passed; full combined source, installed and native platform
qualification remain pending. See the [development evidence](../../verification/native-ci-development.json)
and [subsequent provider observations](../../verification/native-ci-provider-observations.json).

RELEASE-CLOSURE-001 separately owns the aggregate-coverage assurance gap. A public
`qualify_release` experiment over real temporary Git/policy with simulated provider
metadata records both Linux and Windows cells for three successful-workflow arms:
both jobs successful, Windows missing and Windows skipped. It asks for no jobs;
all three arms complete in 1.903 seconds without a build, allocation, tag or
publication. This matches the documented aggregate delegation, but cannot prove a
selected CI profile enforces every declared cell. Review an explicit native
aggregate/cell contract and compatibility transition before changing release
semantics. This observation is not a claim that a published release missed a cell.

## Containment inventory and implementation boundary

The current native implementation is a development checkpoint, not completion of
PROJECT-LAYOUT-001 or ADOPT-CLI-001. The public minimal profile preserves a
seven-file Python/Make fixture, its custom agent instructions and native GitHub
workflow discovery. Its 15 repository additions are all under `litai/`; it neither
executes a native build nor produces a release receipt. Explicit `--profile
convert` retains the larger conversion path. The legacy compatibility cohort
passed 38 tests in 66.126 seconds before the subsequent custody corrections;
those corrections still require the full source and installed qualification.

Independent review caught four real issues: snapshots dropped the observed
directory identity, legacy and contained creators used different locks, lexical
discovery followed a redirected framework path, and application-root catalog
metadata could suppress a contained update. Corrections have 18 passing focused
tests in 24.074 seconds. Two successive simulated template upgrades through the
real CLI preserve a local overlay, and a conflicting edit preserves its file and
baseline. This is controlled template behavior, not a released-wheel upgrade.

Local child-process exits before and after exclusive bootstrap publication leave,
respectively, unchanged application source or complete unqualified original
authority. A competing bootstrap/legacy publication control has one winner.
The initial synchronization fixture had a classmethod-binding error; the corrected
race passed in 0.773 seconds. Before-publication crashes can retain a sibling
temporary staging directory; orphan cleanup is still open. The first private-state reservation split on case aliases and configurable
state roots. Its replacement uses the actual worktree Git administration
directory and the existing manifest-lock protocol. Non-Git scaffold
creation uses a transient root reservation. These transaction files are explicit
coordination exceptions, not tracked application integration files. The POSIX manifest
lock acquisition can block on another holder; it does not yet have the bounded
wait described by the newer Windows retry path. Native publication with this
correction still needs its final alias/concurrency qualification.

Removal reuses committed Git before-images and index publication rather than a
new deletion journal. The development CLI plans finite owned paths, preserves
custom documents and unrelated staging, applies exact deletion patches, and
removes the manifest in a separate final step. Both index and filesystem must
confirm removal even when Git returns zero. Recovery requires the recorded full
source commit and finite path set; it never guesses from history or restores
worktree bytes. Unknown Git locks remain a native recovery prerequisite.

Six public fixture tests passed in 39.778 seconds, including actual process exits
before and after manifest deletion and fresh-process recovery. The initial
three recovery cases failed because copied worktrees had stale Git stat caches;
finite `git add --refresh` plus semantic index comparison corrected that without
staging content. Seven subsequent tests passed in 49.838 seconds, adding parent
directory custody and truthful already-absent result accounting. Independent
review then identified changed authority metadata being treated like custom
product documents; its refusal correction and negative control passed in an eight-case run
(48.864 seconds). These local development runs do not establish installed or native
Windows/Linux qualification. Runtime and custom files are retained; removal does
not promise an empty directory or commit the staged deletions.

The subsequent 31-case cohort passed in 133.329 seconds. Independent real-Git
probes still found alternate-index bootstrap admission, a recovery index-restore
race that discarded new staging, catalog copies outside containment, and legacy
root release-policy selection. The corrected design refuses Git scope overrides,
removes automatic index restoration, uses exact indexed deletion patches for
already-missing files, and explicitly refuses optional catalog, parent and
release owners until contained support exists. Those corrections require renewed
review and qualification. A permission-fault recovery control passed in 12.210
seconds after correcting test cleanup for a directory Git had already pruned.

Native execution binding, migrations, optional external adapters, other implicit
owners, and native Windows/Linux installed qualification remain acceptance
obligations. The supported Git index inspection is bounded to 4 MiB; an oversized
index refuses instead of claiming large-repository support. The complete current
native-batch qualification is recorded in the current checkpoint below.

The exact `d90d8704c26f7192224238727526e72a1f4eceb4` candidate separately passed
wheel verification, offline installation and actual configured-model generation,
local build/test/run using one identical wheel. The
[candidate artifact record](../../verification/candidate-artifact-development.json)
binds those results to wheel `sha256:2ef9e1dc02770185980f076d23014f6b26c8200c3694449ae61a24aa1da23e7a`.
It does not qualify later worker/native changes or other target platforms. An
initial live attempt refused an ambient CLI/configured-model mismatch after
installation. Moving that inexpensive check before runtime creation now has a
real subprocess negative control; a full installed requalification of that
changed script is still required.

The baseline has 146 direct project-manifest references in 60 Python modules;
five release-policy references in four modules; eight worker-catalog references
in eight modules; and 135 `.literate/` references in 43 modules. These are text
inventory counts, not independent runtime owners. The 965 `_build` references in
165 modules include fixture and command literals and require classification,
not a blanket replacement. The initialization template itself has 19 top-level source
entries (including its Python packaging module) and also synthesizes project configuration and harness files in Python.

| Authority or state | Existing owner | Contained destination and invariant |
| --- | --- | --- |
| Project manifest and its write lock | `projects.ProjectConfigurationStore` | `litai/literate.project.json`; one shared context keeps the application root distinct from the framework directory. Compare-and-swap must bind the selected manifest location as well as its bytes. |
| Release and test policy | `project_releases`, retained/project test owners | `litai/literate.release.json` and declared test policy. Native commands and product version mirrors continue to resolve against the application root. |
| Catalogs, generation, routing and workflows | Project definition, initialization and catalog inheritance | `litai/components`, `litai/flavors`, `litai/skills`, `litai/workflows`, `litai/routing`, `litai/orchestration`; these are opt-in native-adoption profiles. Preserve explicit application-relative coordinates. |
| Origin and three-way update baseline | `project_initialization`, `project_updates`, `project_update_apply` | `litai/.literate/initialization-*`; preserve customized files, exact baseline identities and stale-plan refusal. |
| Original/conversion/native-child and lineage authority | `original_project_adoption`, `conversion_authority`, `repository_lineage` | `litai/.literate/` owned metadata; preserve source custody and historical identities. Integrate the retained-layout owner before allowing root-retained source. |
| Receipts, locks and execution state | Existing lifecycle and evidence stores | Declared locations under `litai/`; renew affected path-bound receipts. A directory name does not authorize exclusion from source capture or cleanup. |
| Worker configuration | Private worker registry plus project selection policy | User-global private configuration stays user-global; any project-owned override lives under `litai/`. Do not copy credentials into a consumer. |
| Managed runtime and disposable output | Existing object-directory and cache owners | `litai/_build` and declared generated roots. Native application build outputs remain owned by the native build. Explicit user paths retain their documented ownership and limits. |
| Agent discovery | Existing owned-region/entrypoint mechanism | Only selected clients' externally required discovery files delegate to `litai/SKILL.md`; preserve custom instructions. Installing every provider adapter is not a minimal-adoption prerequisite. |
| Native build and forge integration | Consuming repository | Keep existing Make/Cargo/CMake/package and CI files. An optional native CI step invokes the pinned CLI; a separate forge-required workflow file is an explicit adapter, not permission to relocate existing workflows. |
| Product documentation | Consuming repository | Native README, PROJECT, changelog and product docs stay with the application. Framework-only roadmap and generated harness documentation belong under `litai/`. |

Discovery must distinguish a contained manifest from an independent repository
whose name happens to be `litai`. Refuse dual manifests, redirected framework
directories and stale location bindings. Merely returning the application parent
from discovery would leave direct manifest, lineage and state readers inconsistent.
Each admitted profile must carry its resolver and consuming owners together.
The initial native profile admits bootstrap, authority inspection, three-way
policy update and committed removal; optional owners must refuse before work
until their contained paths are qualified. Existing consumers keep the legacy
layout until an explicit migration qualifies source preservation, upgrade,
removal and evidence renewal. This phased boundary does not close the broader
layout or adoption release goals.

## Current native review checkpoint

The [native development record](../../verification/native-adoption-development.json)
binds independent approval of 51 exact authored subjects. Its final review also
rechecked all 33 changed/untracked source modules against native and earlier
main/worker approvals. A real `diff.noprefix` counterexample had redirected a
patch toward an identically named application file; fixed diff prefixes, strict
whitespace matching and finite apply inclusion now preserve application files in
both index-plus-worktree and index-only removal. The latest 29 maintained removal
and release controls pass in 68.027 seconds; two final independent controls pass
in 9.770 seconds. Earlier failure records remain retained. Full source and
installed/platform evidence are recorded separately; no layout or release goal
is closed by this review alone.

The fresh native source run selected 2,885 tests: 2,793 passed and 92 skipped in
842.390 seconds. Driver, runner, documentation, lint, formatting, changed-skill,
repository-layout and public-export gates passed. The earlier stopped run remains
retained: a legacy release fixture omitted the typed project definition. Four
corrected critical cases passed in 3.328 seconds without weakening the native
release guard. The final run used a fresh checkpoint.

An incremental independent review approved five additional harness/fixture files.
Existing installed conversion scenarios now select `--profile convert` explicitly.
The installed-wheel harness also exercises native bootstrap, unchanged update,
native test pass/fail/repair, and committed removal preserving custom policy.
Its development invocation preserved five application files and staged fourteen
owned deletions. This is not yet an installed-wheel result, a released-version
upgrade, a hosted native PR, or target-platform qualification. Those remain
separate obligations.

The first installed run of the combined `b2465356` candidate refused the harness's
macOS `/var` temporary-directory alias before native publication. No qualified
wheel manifest was exported. The repaired harness resolves its own temporary
directory; the CLI continues to reject redirected user paths and now reports
`original_adoption.unsafe-root` as structured JSON. A maintained public control
covers both leaf and ancestor aliases for plan and apply, preserving the Git
index and application files. The pre-fix control reproduced the traceback;
nine focused source controls pass in 26.855 seconds. The corrected harness also
passes against the previously installed candidate, but that diagnostic run does
not qualify the repaired source or replace fresh whole-wheel qualification.

The final source composition includes the independently reviewed Windows
JavaScript path correction from main `b9fc61770` and preserves the published worker
history. Its fresh four-worker run selected 2,886 tests: 2,794 passed and 92 skipped
in 1,566.179 seconds. All source/trust/static/skill gates passed. The
[composition record](../../verification/native-windows-composition-review.json)
binds the exact reviewed subjects; installed and exact-head CI results remain
separate. The earlier twelve-worker run took 842.390 seconds for 2,885 tests on
the same busy host. These observations do not isolate concurrency from host load
and the additional Windows regression, so they do not establish a speedup claim.

TEST-PARALLEL-001 retains the remaining measurement work: the earlier native run's
611 module logs contain no recorded durations, although its Python step ledger
records 844.445 seconds. Filesystem timestamp estimates suggest dependency-proof
reopening and complete rebuild journeys as profiling candidates, not measured
causes. Retain bounded module spans before changing scheduling or assurance.

The first implementation PR's exact `43809001d` CI run `43922384703` passed eleven
jobs with two named skips in 41m26s wall time. Its longest Linux job spent 27m19s
in conformance and 12m35s in installed-wheel verification; queue/setup does not
explain that critical path. Job spans sum to 79m43s and are not pure CPU usage.
This ordinary PR profile is not comparable to the baseline's full qualification
matrix. PR 450 contains every PR 449 commit and the reviewed worker follow-up;
one combined landing avoids an intermediate main qualification run. The older
passing head never substitutes for the combined head's checks.

## First implementation checkpoint

The read-only `release evidence timing` command accounts for completed wall-clock
intervals and gaps using the freshly reduced ledger. Child interval unions avoid
double-counting parallel or nested work; unfinished, malformed, orphaned and
clock-skewed spans remain explicit. Dependency critical path and runner occupancy
are unknown unless separately observed. The new artifact and final receipt spans
record both passing and failing release checks without changing their decisions.

Maintained local checks pass: eight timing cases, 17 release cases and three
roadmap-summary cases. The original release suite exposed its exact expected-node
list, which was updated for the newly recorded receipt span before the clean
17-case rerun. The timing CLI reproduces run `20261025T150404Z-1c3082`'s
1,675.023 seconds outside its recorded gate children. This does not retroactively
attribute that time to artifact qualification.

Seven duplicate-ID groups are reconciled; distinct Windows fixes now have distinct
IDs. The current manifest retains all 75 original goals and adds SDLC-001,
ADOPT-CLI-001 and the existing WORKER-001 and TEST-CACHE-001 owners for lease and
qualification reuse acceptance: 79 current-release goals in total.
Completed history outside release manifests is archived with stable
active IDs, anchors and dependency fields. Two historical checked parents retain
unchecked sublists (`RETAINED-LIBRARY-BRIDGE-001`, `WORKER-HEALTH-001`); their long
records need evidence reconciliation before archival or any renewed completion
claim. No acceptance is inferred solely from their parent checkboxes.

The release entry point now checks driver, runner and documentation review before starting its
checkpointed gate sequence. A real Make invocation with inert guard bodies proves
each stale guard stops before expensive work; the existing checkpoint controls
still require a clean rerun for release evidence. Manifest reads and writer lock
coordinates are being consolidated through `ProjectConfigurationStore`; current
storage and application-relative semantics remain unchanged. This is preparation
for the shared context, not a contained-layout acceptance claim.

The first worker lifecycle slice adds explicit provider lookup and acknowledged
idempotent release to the existing journal. It recovers a lost allocation reply,
preserves release intent through retries, refuses changed ownership and gates
recovery on observed expiry. Automatic expiry-aware dispatch, provider lifetime
enforcement, active-job drainage and fleet reaping remain open; this slice alone
does not close WORKER-001 or SDLC-001.

Documentation links, lifecycle headers and dependency graph are revalidated after
reconciliation. The consolidated production source has independent approval in
[the review record](../../verification/sdlc-independent-review.json). Its archived
Windows-waiver evidence link is corrected. The approved driver pin is recorded;
the runner pin was already current. Refresh documentation authority before
qualification. The fresh full source gate now passes; installed
and current-candidate CI qualification remain required before integration. Native
onboarding, migration/removal, result reuse, worker lease lifecycle and platform
and skill pilots are still open. No program completion is claimed by this checkpoint.

## Qualification reuse and checkpoint correction

The next slice shares the candidate's exact qualified wheel across the two later
installation checks. It retains full wheel qualification, independent prefix
behavior tests and the existing source-install path. Candidate selection is
immutable; the installer stages and hashes the bytes and verifies current Git
revision, declared version and embedded origin. Two actual fixture installations
prove no source build occurs. Concurrent replacement and stale/substituted inputs
refuse. This is artifact reuse; platform, environment and test-result reuse remain
unimplemented. Clean framework-wheel qualification and latency measurement remain.

Two controlled experiments strengthened the checkpoint boundary. Recursive
`make -n release-check` had recorded printed subcommands as successful gates.
Preview/query/touch modes now record no success evidence and preserve repair
progress. Separately, an unmanaged native fixture changed an input after a failed
attempt; the fallback suite identity allowed its retry to skip the changed test.
Unknown project authority now disables that reuse for both Make and Python paths.
The normal authority-bound repair and known-failure controls still pass.

The first worktree-specific full source attempt stopped on the stale documentation
authority marker after 1,285.767 seconds: 1,842 reported passes, one failure and 87
skips. The parallel runner logged 1,933 tests while its reconciled outcome report
contains 1,930 terminal outcomes; neither count is a complete pass of the 2,821
selected tests. Refresh reviewed documentation before rerunning. The new
`documentation-review --require-current` gate makes this refusal explicit and
moves it before the release sequence. It does not renew the independent source
review pin.

The TEST-CACHE-001 plan now describes the already-landed pin service and its actual
fallback gap. Its earlier present-tense claims are archived, with every unproven
closure, composition, receipt, concurrency and retry requirement mapped to the
current acceptance. No-op performance goals no longer imply that repair progress
can satisfy a fresh release gate.

The independently reviewed full source attempt ended after 1,644.791 seconds:
2,412 reported passes, one failure and 91 skips. The parallel runner counted
2,507 tests; the outcome report contains 2,504 terminal outcomes from 2,827
selected. The failure is an old parallel fixture expecting unmanaged repair
reuse. The corrected fixture now preserves declared-authority repair and
known-failure coverage alongside explicit unmanaged rerun assertions. All 14
module tests pass in 36.782 seconds, and the final test-only delta has independent
approval. The production source remains
unchanged from independent review. This failed attempt is retained, not promoted
to successful qualification. After the fixture correction and authority refresh,
a fresh complete source run passes all 2,827 selected tests: 2,735 passes and 92
skips in 1,557.303 seconds. The independent reviewer also approved the final
formatting-only fixture change by exact AST comparison. This is local source
qualification with live round trips disabled; installed and native CI evidence
remain outstanding.

## Current tracker reconciliation

Read-only snapshot: 2026-11-16, 72 open issues and 33 open PRs on
`jordanhubbard/literate-ai`. Historical NVIDIA-dev issue numbers are a different
namespace and must not be treated as the same requests. This table connects the
previously unlinked current-repository records to existing execution owners.
Open does not mean unimplemented, and a green review head does not close current
combined acceptance. No issue was closed, no PR merged and no external comment
posted by this reconciliation.

| Workstream | Existing owners | Open issues | Open PRs | Disposition and next check |
| --- | --- | --- | --- | --- |
| Original adoption and containment | ORIGINAL-ADOPT-001, ADOPT-RELOCATE-001, PROJECT-LAYOUT-001, ADOPT-CLI-001 | [#222](https://github.com/jordanhubbard/literate-ai/issues/222), [#366](https://github.com/jordanhubbard/literate-ai/issues/366), [#332](https://github.com/jordanhubbard/literate-ai/issues/332) | [PR 333](https://github.com/jordanhubbard/literate-ai/pull/333), [PR 349](https://github.com/jordanhubbard/literate-ai/pull/349), [PR 437](https://github.com/jordanhubbard/literate-ai/pull/437) | Integrate bootstrap and selected placement only after the contained native journey is qualified; retain legacy conversion compatibility. |
| Native Cargo custody and receiver | CARGO-COMPAT-001, RETAINED-OBSERVATION-PERF-001, COMMAND-WORKER-001 | [#223](https://github.com/jordanhubbard/literate-ai/issues/223), [#224](https://github.com/jordanhubbard/literate-ai/issues/224), [#225](https://github.com/jordanhubbard/literate-ai/issues/225), [#226](https://github.com/jordanhubbard/literate-ai/issues/226), [#424](https://github.com/jordanhubbard/literate-ai/issues/424), [#429](https://github.com/jordanhubbard/literate-ai/issues/429), [#430](https://github.com/jordanhubbard/literate-ai/issues/430), [#432](https://github.com/jordanhubbard/literate-ai/issues/432), [#433](https://github.com/jordanhubbard/literate-ai/issues/433) | [PR 425](https://github.com/jordanhubbard/literate-ai/pull/425), [PR 431](https://github.com/jordanhubbard/literate-ai/pull/431), [PR 434](https://github.com/jordanhubbard/literate-ai/pull/434), [PR 435](https://github.com/jordanhubbard/literate-ai/pull/435), [PR 438](https://github.com/jordanhubbard/literate-ai/pull/438), [PR 439](https://github.com/jordanhubbard/literate-ai/pull/439) | Review the dependent stack in order and qualify the combined current candidate. Keep original bounds and all custody assertions; no individual green PR proves the combined stack. |
| Private command receiver tool bindings | COMMAND-WORKER-001 | [#446](https://github.com/jordanhubbard/literate-ai/issues/446) | — | Add explicit private BUILD/TEST configuration through the public surface; observed tools still require exact admission. |
| Native libraries and runtime composition | NATIVE-SDK-001, RETAINED-LIBRARY-BRIDGE-001 | [#345](https://github.com/jordanhubbard/literate-ai/issues/345), [#422](https://github.com/jordanhubbard/literate-ai/issues/422), [#447](https://github.com/jordanhubbard/literate-ai/issues/447) | [PR 347](https://github.com/jordanhubbard/literate-ai/pull/347), [PR 423](https://github.com/jordanhubbard/literate-ai/pull/423), [PR 448](https://github.com/jordanhubbard/literate-ai/pull/448) | Qualify Rust provider edges, locked runtime capabilities and JavaScript sealed imports through actual native consumers. |
| Promotion and revised membership | NATIVE-CHILD-UPDATE-001, QUALIFIED-CHILD-ADD-001, QUALIFIED-CHILD-REVISION-001, ORIGINAL-ADOPT-001 | [#216](https://github.com/jordanhubbard/literate-ai/issues/216), [#363](https://github.com/jordanhubbard/literate-ai/issues/363), [#368](https://github.com/jordanhubbard/literate-ai/issues/368), [#379](https://github.com/jordanhubbard/literate-ai/issues/379), [#443](https://github.com/jordanhubbard/literate-ai/issues/443) | [PR 313](https://github.com/jordanhubbard/literate-ai/pull/313), [PR 359](https://github.com/jordanhubbard/literate-ai/pull/359), [PR 381](https://github.com/jordanhubbard/literate-ai/pull/381), [PR 382](https://github.com/jordanhubbard/literate-ai/pull/382), [PR 440](https://github.com/jordanhubbard/literate-ai/pull/440), [PR 444](https://github.com/jordanhubbard/literate-ai/pull/444), [PR 445](https://github.com/jordanhubbard/literate-ai/pull/445) | Preserve original source, assets, links and scratch ownership. Treat proposed ADRs and unrun membership recovery as unfinished. |
| Release contribution policy | RELEASE-INTEGRATION-005 | [#441](https://github.com/jordanhubbard/literate-ai/issues/441) | [PR 442](https://github.com/jordanhubbard/literate-ai/pull/442) | Integrate optional-manifest refusal repair and rerun contribution/dependency validation against the combined roadmap. |
| Windows process and export scan cost | RELEASE-CANCEL-001, RELEASE-INTEGRATION-005 | [#426](https://github.com/jordanhubbard/literate-ai/issues/426), [#427](https://github.com/jordanhubbard/literate-ai/issues/427) | [PR 428](https://github.com/jordanhubbard/literate-ai/pull/428) | Preserve Windows process ownership and export safety while eliminating measured redundant cleanup and pathological scanning. |
| Bounded model runtime | CODEX-STATE-001 | [#412](https://github.com/jordanhubbard/literate-ai/issues/412) | [PR 413](https://github.com/jordanhubbard/literate-ai/pull/413) | Qualify isolated Codex state and finite file ceilings with remote catalog behavior explicit. |
| Telemetry and CUDA evidence | WORKER-TELEMETRY-001, CUDA-SIGNAL-001 | — | [PR 410](https://github.com/jordanhubbard/literate-ai/pull/410), [PR 416](https://github.com/jordanhubbard/literate-ai/pull/416) | Integrate reviewed inventory and deadline fixes; native GPU execution remains a separate support cell. |
| Native qualification and failure recovery | AUTHORED-GRAPH-QUALIFICATION-001, NATIVE-ACCEPTANCE-REPAIR-001, QUALIFICATION-DIAGNOSTICS-001 | — | [PR 391](https://github.com/jordanhubbard/literate-ai/pull/391), [PR 401](https://github.com/jordanhubbard/literate-ai/pull/401), [PR 409](https://github.com/jordanhubbard/literate-ai/pull/409), [PR 414](https://github.com/jordanhubbard/literate-ai/pull/414) | Combine only compatible reviewed authority and retain failure diagnostics, independent acceptance and finite repair attempts. |
| Shadow and integration stack | SHADOW-001, RELEASE-INTEGRATION-005 | — | [PR 312](https://github.com/jordanhubbard/literate-ai/pull/312), [PR 322](https://github.com/jordanhubbard/literate-ai/pull/322) | Inspect dependent source identities before integration; shadow automation remains opt-in. |
| Optional collaboration and tracker proposals | SDLC-001, RELEASE-INTEGRATION-005 | [#321](https://github.com/jordanhubbard/literate-ai/issues/321), [#323](https://github.com/jordanhubbard/literate-ai/issues/323) | [PR 326](https://github.com/jordanhubbard/literate-ai/pull/326), [PR 334](https://github.com/jordanhubbard/literate-ai/pull/334) | Triage proposed ADRs separately from native delivery. No implementation or current-release promotion is inferred from an open proposal; retain the request for an explicit value/scope decision. |
| Optional explicit source intelligence | INDEX-001 | [#146](https://github.com/jordanhubbard/literate-ai/issues/146) | — | Preserve the explicit indexing request; do not make automatic external indexing a prerequisite for native adoption. |
| Native Mix platform acceptance | ELIXIR-002 | [#137](https://github.com/jordanhubbard/literate-ai/issues/137), [#138](https://github.com/jordanhubbard/literate-ai/issues/138) | — | Retain OTP application and Rebar3/Hex dependency cases in native Elixir acceptance; catalog presence alone is insufficient. |

### Reused peer fixes

[Development evidence](../../verification/sdlc-development.json) binds the changed
source bytes, local cohorts, peer heads and remaining qualification limits.

The development branch incorporates the reviewed implementation and tests from
[PR 442](https://github.com/jordanhubbard/literate-ai/pull/442) at
`4c102f1267e51e4b60d980b00e9516b1f43193a1` and
[PR 428](https://github.com/jordanhubbard/literate-ai/pull/428) at
`6f060715206a54b45ab0eed9353cb444eed1993b`. Their old authority pins are not copied.

The optional contribution-manifest parser copies its input before extracting the
optional field; required milestone, unknown keys and unsafe paths still refuse.
All 31 maintained release cases pass. The export matcher exposes existence only:
matching the final permitted prefix character before the denied suffix recognizes
the same inputs without repeated greedy scanning. Four export cases pass. The
original whole-tree scan was still running after 88 seconds and was explicitly
stopped; layout, export and skill checks then completed in 21.30 seconds together.
This is a local before/after bound, not a historical release-time attribution.

Windows cleanup records only confirmed Job Object termination under its lock. A
pending claim, missing/failed ownership or released handle retains fallback; the
root process kill remains. Four portable ownership cases pass, with three native
Windows cases skipped on macOS. The surrounding process selection passes 18 cases
with four FreeBSD-specific skips. These skips are not native Windows or FreeBSD
qualification. Both PRs and final integrated qualification remain open.


## Preserve existing worker checkouts during release sync

A controller-only experiment mistakenly selected `release check --target local`.
That selector uses the configured SSH fleet. Seven workers received connection
attempts. Four received the fixture and ran its one native test. Three
connections failed during preparation. The overall check failed and produced
no prepared release record. Local logs confirm forced checkout and
`git clean -fdq` on the four successful workers. Their previous contents are
unknown. The project may also select remote execution through policy when
`--target` is omitted.

A separate network-denied test exercised the production POSIX checkout code
with Git bundles and local transport. Two repositories named `sample` in
different organizations selected the same worker destination. The first sync
overwrote a pre-existing dirty tracked file and removed a deliberately seeded
untracked note. A sibling file and ignored cache survived. The existing
incremental-sync test places the operator's sentinel outside the destination.
A second local trial put synthetic HTTPS userinfo in the controller's Git
origin. Sync copied it verbatim into the simulated worker's Git configuration.
Use a credential-free repository identity and display URL for worker provenance.
[Observed and simulated results](../../verification/static-release-checkout-scope.json).

Prioritize this fix under WORKER-001 before further real fleet qualification.
Bind a checkout to its full repository identity and verify exclusive ownership
before the first mutation. Preserve existing unmarked directories and report
their path for explicit migration. Serialize competing attempts and
exercise a crash between directory creation, ownership recording and checkout.
Retain incremental bundle transfer and reuse of valid ignored caches in owned
checkouts. Cover POSIX and Windows command paths, same-name repositories,
redirects, foreign checkouts and overlapping attempts. Give agents an explicit
controller-only selection that cannot resolve to SSH or hosted CI. Preserve
strict release-policy coverage requirements when that selection cannot satisfy
a release. Keep the existing fleet selector compatible and make its meaning
visible in CLI help and evidence.

## Managed dispatch follow-up

The separate lease follow-up binds SSH admission to a fresh ready observation,
exact registration and the whole bounded job duration. One durable attempt per
managed worker serializes dispatch with release. Ordinary release withdraws the
registration and preserves intent while the admitted job drains; interrupted
controllers retain uncertain work. Explicit cancellation names that exact attempt,
uses the existing idempotent release request, and rejects late results. Static
workers remain independent of this protocol.

Local child-provider and transport-boundary checks currently pass: 29 cases in
7.318 seconds, including an actual controller `os._exit(23)`, clock rollback,
short/expired leases, concurrent drain, explicit CLI cancellation and late result
refusal. These are development checks, not native SSH/provider qualification.
The final corrected production delta has independent source approval; combined
installed checks and exact-candidate CI remain required. Background reaping, provider lifetime enforcement and live cleanup
are still open under WORKER-001 and SDLC-001; no additional roadmap owner is added.


Independent review found and reproduced delayed-publication admission after
expiry, the incorrect ten-second cleanup assumption and terminal cancellation
accepting a wrong token. The follow-up now checks lifetime again after durable
publication, propagates one absolute monotonic execution deadline, derives cleanup
wait allowance from the actual process owner, and checks terminal cancellation
against the retained cancelled attempt. Local controls cover expired and still-live
but insufficient headroom, no handler entry, and exact terminal retry. The independent reviewer approved all nine production files and exercised 32
focused cases plus failed-publication and lost-reply probes. The final author
selection passed 40 cases with seven native-platform skips. A fresh complete
local source gate passed 2,836 selected cases: 2,744 passes and 92 skips in
1,555.305 seconds. See [the development evidence](../../verification/managed-lease-development.json).
Live round trips were disabled; installed, native-provider and exact-candidate CI
qualification remain separate. The corrected source hashes match the reviewed
subject, and no full worker-program or release completion is claimed.

## Preserve module timing through CI handoff

Timing candidate `51afb59ca17676f4df89825b59bffba66f873542` passes ordinary PR
CI run `43991908658` (11 successful jobs, two declared skips). Downloading its
actual evidence artifact `14292940153` exposes a retention gap: all 60 members
omit the module timing file, while the ledger points to an absolute worker spool
outside the uploaded evidence directory. The reader correctly has no module
elapsed time after download, but its aggregate availability label was misleading.

The correction writes attached timing beneath its owning evidence node and
registers a relative pointer. Standalone or disabled evidence keeps the original
private spool; a disabled node cannot redirect writes into the current directory.
One registration, record/byte bounds, fail-soft diagnostics, process ownership and
test deadlines stay unchanged. Missing records report unavailable at both levels.

The maintained real-subprocess control now archives only the ordinary evidence
upload directory, removes the original evidence and worker spool, and reopens the
archive at a different path. It fails on the original writer in 0.788s and passes
after the correction; 13 reader/retention controls pass in 0.771s. The combined
reader/scheduler cohort passes all 30 controls in 40.095s, including the previously
reviewed shutdown-barrier repair for the fixed-sleep fixture race. Independent
review and fresh complete source checks passed at corrected head
`af4ab36e03b0784d7758b5599f16fb79ff28fbb2`. Exact CI `44011402262` passed;
its actual artifact `14298408131` was downloaded and unpacked at a different
local path. The public reader reports all 611 modules complete with zero issues,
without the original runner files. This establishes portable diagnostic timing;
it does not establish release qualification or CPU/billed runner time.
## Post-merge platform failure recovery

Main `ebf88985be10f733dd64f469b7cd4aa685ce9083`, CI run `43990299543`,
exposed failures that the ordinary PR profile did not catch. These remain failed
qualification evidence until corrected candidates pass the affected native cells.

- Linux/Python3.14's checkpoint repair fixture assumed another process would
  finish within a 300ms sleep. Delaying that worker by 700ms reproduced the exact
  `b\n` versus `b\nb\n` execution-count mismatch. A bounded completion barrier
  now waits for the other worker's shutdown marker after it flushes its report. The same
  delayed-process control passes in 8.080s; all 18 scheduler-module controls pass
  in 41.298s. Checkpoint reuse and fail-fast behavior are unchanged.
- Windows/Python3.12 shard1 lost an HTTP403 response with WinError10053. The
  cache's pre-body rejection closed over an unread upload. A real local loopback
  control with a delayed 25-byte body reproduced a connection reset, establishing
  the transport defect but not the exact native Windows error sequence. Rejected
  finite PUT bodies now have bounded disposal after the error response and write
  half-close, under the original connection timer. Invalid framing, Expect and
  oversized bodies receive no drain; discarded bytes never enter publication.
  Native Windows confirmation remains required.
- The same Windows shard timed out during fixture Git commit setup after 20s,
  before its public-planning assertion. The log does not identify Git execution,
  inherited hooks, descendant-held pipes or contention as the cause. The timeout
  remains unchanged; targeted native diagnosis is still open.

The native bootstrap byte-restoration failure is handled by the separately
reviewed documentation/CI batch. No failure is waived by a local or simulated
pass, and no test budgets, skips or required platform cells are relaxed.

## Qualification cost and documentation checks after the first landing

The initial native-adoption/worker/review batch landed through
[PR 450](https://github.com/jordanhubbard/literate-ai/pull/450) at
`ebf88985be10f733dd64f469b7cd4aa685ce9083`. Its exact source candidate `101315c4`
passed [ordinary PR CI run 43984309076](https://github.com/jordanhubbard/literate-ai/actions/runs/43984309076):
11 successful jobs, two declared skips, 42m45s wall time. The longest Linux job
spent 28m22s in conformance and 13m in installed-wheel verification. Summed job
spans were 4,973 seconds; they include setup and idle and are not CPU or billable
runner time. This is ordinary PR evidence, not full release qualification.

The timing follow-up at `51afb59ca17676f4df89825b59bffba66f873542`
([PR 456](https://github.com/jordanhubbard/literate-ai/pull/456)) passed 2,894 selected
local tests: 2,802 passed, 92 skipped, zero failures, 1,587.324 seconds. All 611
module envelopes are accounted for without reader issues. The diagnostic file is
1,169,864 bytes across 6,112 records. Four concurrent slots were occupied almost
continuously; module envelopes sum to 6,320.705 seconds. These are overlapping
observations on a busy macOS host, not a critical path or speedup comparison.

The two slowest observed modules were model-free CLI rebuild (434.629 seconds,
seven cases) and command LINK dependencies (415.543 seconds, one case with its
shared PACKAGE/FINALIZE controls). More than 99.99% of their combined envelope
was inside their test subprocesses. A separate controlled run of the seven CLI
setup/cleanup cycles measured 8.968 seconds of setup, including 8.961 seconds of
initialization, and 0.110 seconds of cleanup. It used actual local initialization
with no builds or live model calls. This different timing window cannot be
subtracted from the full-suite trace as exact attribution. Even ideal reuse of
six initializations would save about 7.7 seconds before copying costs. Prioritize
measuring lifecycle, proof decoding and verified CAS reads before optimizing
fixtures or removing safeguards. No such production optimization is claimed here.

The subsequent [site run 43990299670](https://github.com/jordanhubbard/literate-ai/actions/runs/43990299670)
failed before publication because the raw HTML report linked to a Markdown route
that the site rendered as HTML. Full Python conformance had passed. The existing
site verifier caught the missing route in approximately 1.6 seconds. The report
now links to the repository roadmap, which works both in the checkout and copied
site. On the independently reviewed retained-layout composition, a local full-site
check passed 1,742 pages and 14,121 local links. That run used Node 26.8.1; CI
retains Node 24 selection. This is separate from this follow-up's qualification.

The SDLC-001 follow-up therefore adds the existing site build/link check to
relevant PRs, with read-only permissions and no publication job for PR events.
The deployment job depends on validation of the same run's artifact. The local
presentation/roadmap exception in CONTRIBUTING requires independent scope review,
actual roadmap/diagram/site checks and current authority; code, templates, skills,
policy, acceptance and uncertain changes still require the complete local suite.
Documentation-only CI already selects a focused profile. Neither that profile nor
this exception is full release qualification or an authorization to publish.
This policy/CI change itself must pass the full local gate before landing.


The exact post-merge Windows shard
[133728953509](https://github.com/jordanhubbard/literate-ai/actions/runs/43990299543/job/133728953509)
reported 707 passes, 113 skips and one failure in 1,176.68 seconds. Native adoption
and update passed their source-preservation checks; the fixture's final repair
used text-mode writing, converting the original LF source to CRLF. The observed
hashes exactly match the LF and CRLF forms of the fixture. Capture and restore the
original bytes instead, retaining the strict digest/mode/Git assertion and fresh
bytecode directory. A local Windows-newline simulation reproduced the original
failure; it is not native Windows qualification. Add the existing adoption and
publication modules to both platform smoke cells so this behavior is exercised
before merge. Repaired head `48e3d1ef30fb0f11ba27cc55dcfdab9253c15a68` passed 27 actual
Windows smoke controls in run `44000908565`, including native bootstrap and
publication refusals. Combined-candidate platform qualification remains open. This is
another reason to choose platform checks by changed behavior rather than relying
on a passing generic installation smoke check.


## Combined qualification after independent batch review

SDLC-001, RELEASE-INTEGRATION-005 and the existing focused owners retain this
work. Compose the independently reviewed timing-retention, platform-repair and
CI/documentation-gate batches with the native CI observer and qualified retained
Cargo parsing batch. Preserve each exact reviewed production subject; merge only
the existing CI fixture list, byte-restoration test and roadmap narrative where
the branches overlap. Reuse the identical scheduler completion-barrier repair.

The next full source run must cover this combined candidate. Current individual
passes and review records establish their own subjects, not the composition.
Then qualify the noneditable wheel and affected native platform cells. Source
pin renewal requires independent review of the composition and changed narrative.
GitGuardian incident classification, the unresolved native Windows Git setup
timeout and publication authorization remain explicit outstanding boundaries.
The first native observer still reports only a configured CI observation; no
bootstrap admission, artifact provenance, merge readiness or release claim follows.

The first combined full run selected 3,173 tests and stopped after 2,461 passes,
102 skips and one failure in 2,059.805 seconds. The maintained command-reference
check found the new `litai project ci verify` verb missing from the reference.
Add its public reference entry, correct the retry limitation from the later actual
provider observations and remove the archive's extra final blank line in one
reviewed batch before a fresh full gate. Preserve this failed run; unexecuted
tests and prior branch passes do not qualify this composition.

RELEASE-CLOSURE-001 retains the next opt-in coverage contract. Reuse the existing
workflow selector and native matrix; a finite CI-produced report must identify
the actual tested source, policy, completed platform/action cells, supporting
jobs and any tested deliverable digests. Resolve its exact attempt-specific
artifact and corroborate a freshly executed producer before closing the run
observation. An actual diagnostic archive (`14298408131`, run `44011402262`)
matched the provider's SHA-256 and run/head metadata, but that API returned no
attempt field. Its archive digest proves report integrity, not tested binaries.
Do not opt the framework into this contract before an actual producer/transport
pilot, including partial reruns. Keep legacy aggregate delegation explicit;
strict opt-in must never fall back to it. This records design progress without
closing or weakening any existing release acceptance requirement.

## Explicit CI coverage consumer implementation

SDLC-001 and RELEASE-CLOSURE-001 own this in-progress implementation. Start with
an opt-in qualification/evidence-preparation consumer: parse one versioned report
binding, reuse the selected workflow and bounded job history, validate exact
source/policy/action/cell facts, and collect one finite attempt-specific archive.
Keep native execution and matrix selection in the host workflow. Strict mode must
refuse unsupported promotion and target shortcuts before writes; compatibility
without the opt-in remains explicit. Do not enable this profile in the framework
until the real producer/transport and native action contract are proven.

The implementation-boundary review identifies a concrete mismatch: Linux/macOS CI
runs `make validate` and `wheel-check`, while the configured `release-gate` action
is `make release-check`, which additionally includes installation, live installed
project, samples, export and receipt gates. Windows category overlap also lacks a
receipt proving the complete script/shard equivalence. A full-CI label cannot
supply those missing action facts. Use a small real native fixture action for the
first failure/recovery controls; never stamp the framework's release-gate from
job names or a matrix profile alone. The reviewed design identity is
`sha256:1b04d0627a746183e293ad352f5f834b43e7f6dc0e6f343d251cfdbd4655fd34`.

Acceptance remains open for the complete consumer's wrong-source/policy/action,
missing/skipped cell, stale/retried attempt, invalid archive, drift and mutation
bypass controls; a noneditable wheel; an actual hosted producer including partial
retry; strict promotion and exact tested artifacts; and the final release gates.
This slice adds no new execution scheduler, release authority or publication.

The first consumer implementation has independent source approval after correcting
Git-state, missing-object, malformed-job and worker-thread context findings. The
public release-CI module passes 15 methods in 31.452 seconds; the final two
strengthened missing-object/worker controls pass in 3.176 seconds. The worker
regression fails against the pre-fix source, while the corrected probe adds no
objects, changes no refs and uploads nothing. These use actual temporary Git and
local commands with simulated provider/remote transport. See the
[scoped review record](../../verification/ci-coverage-review.json). Full source,
installed/native and actual hosted producer qualification remain pending, and
strict promotion remains explicitly unsupported. No release acceptance is closed.

The first Linux source gate stopped after 1,770 passes, 95 skips and one failure
in 420.071 seconds: the existing telemetry fixture assumed a 4 MiB temporary-file
write must increment Linux storage-accounted bytes. Actual kernel observations
show `/tmp` is tmpfs and reports `wchar=4194304`, `write_bytes=0`; ext4 reports
`write_bytes=4194304` for the same fsynced workload, and the unchanged test passes
there. Correct the fixture's oracle against the owned blocked child's independent
`/proc/<pid>/io` reading, retain actual payload/CPU/RSS/lifetime assertions, and
exercise both tmpfs and file-backed temporary roots. Production telemetry must
continue reporting storage accounting without substituting syscall byte counts.
Retain the failed gate and run a fresh complete gate after the reviewed correction.

## Hosted producer pilot implementation

RELEASE-CLOSURE-001 retains this next in-progress action. Use a dedicated native
Linux/Windows fixture workflow and small real build/test commands with matching
committed fixture policy. An exporter depends on all contributing jobs, gathers
their actual result artifacts and provider execution identities, and uploads the
versioned coverage report during its own job. Observe it only after the workflow
completes, through the existing read-only adapter; a dependent job in the same
workflow cannot require that workflow to be completed. No new public CLI command
or framework production-policy opt-in is needed for this experiment.

The pilot must refuse complete coverage after native failure/cancellation or a
missing action, wrong source/command, stale report or copied exporter. A partial
retry must preserve original successful execution facts and require a freshly
executed dependent exporter and attempt-specific report. Bind the actual checkout
commit/tree separately from associated head, exact fixture policy/action identity,
observed OS/CPU and provider job/run/attempt identities. Prove actual archive
transfer and matching digest, while retaining that report integrity does not
qualify binary artifacts. This initial hosted adapter/transport pilot cannot
close the unchanged public release CLI's consuming-repository acceptance. That
requires an actual repository whose root owns the selected release policy.

Keep the current source-gate candidate frozen in its own worktree. Pilot workflow,
fixture commands, exporter and failure/recovery controls require independent
review and applicable gates before a PR can supply real hosted evidence. Local
simulation and a workflow declaration alone cannot satisfy that acceptance.

The pilot source has independent approval after correcting a missing required
policy field, cross-OS Windows executable parsing and a recovery test that reused
old receipts. Its maintained cohort passes 16 methods in 37.856 seconds, including
real local native commands, exporter process, ZIP and adapter consumption with
provider transport and foreign-job facts simulated. Recovery now regenerates the
native facts after a real seeded failure. See the
[pilot source review](../../verification/ci-coverage-pilot-review.json). Full gates,
actual hosted Linux/Windows execution, partial retry, uploaded archive transfer and
consuming-repository public release qualification remain open.

The existing retained-observation performance owner retains a measured gate-cost
follow-up. Source inspection finds eight receiving cases each perform adoption
and three Cargo preparation commands, including three pre-execution refusals that
never launch a receiving subprocess. During the Linux gate this single module
was the last active worker; its process remained CPU-active and the final selected
case was the real patch-workspace/protocol/retired-admission journey. This does
not attribute that time to Cargo: setup, fresh runtime/source byte checks and
assertion phases remain unmeasured. Preserve both positive custody paths and the
qualified parse optimizations. Measure those phases before choosing cheaper refusal
fixtures, safe immutable pre-capture reuse or distributing the long e2e/critical
cases through the existing module scheduler. No full-gate case is removed or
reclassified by this observation. The assessment identity is
`sha256:8190461757a5afc71da0dc4eb29e8d4c00aab47700a98a0493ea4abe437f254c`.

The architecture review now distinguishes its original baseline from subsequent
implementation evidence at `c1038afa2`, and records the passed Linux source gate
and its measured module costs. The three longest observed module envelopes were
750.615 seconds (retained Cargo receiving), 591.124 seconds (command-link
dependencies) and 485.934 seconds (model-free rebuild). Those are diagnostic
worker intervals, not CPU, billed runner use or an attributed historical release
critical path. The update preserves all remaining hosted, artifact-promotion,
legacy-adoption, skill-comparison and native acceptance boundaries; no queue item
is closed, moved or weakened by the narrative.


### Separate documentation and specification tool dependency ownership

RELEASE-CLOSURE-001 owns this in-progress follow-up to the measured dependency
failure. The final documentation gate and hosted PR 465 CI stopped on
[GHSA-fc5q-39xc-vjpf](https://github.com/advisories/GHSA-fc5q-39xc-vjpf) in
OpenSpec's picomatch dependency. The actual OpenSpec public status command on an
owned disposable repository completes a normal pattern in 0.475 seconds, while a
hostile schema output pattern exceeds a three-second subprocess bound. The risk
is reachable; no audit exception or unreviewed upstream parser patch is justified
by an earlier passing check.

Documentation rendering never invokes OpenSpec. Give the browser-bearing
Mermaid/Puppeteer/yauzl toolchain its own locked package and retain the pinned
OpenSpec CLI in a separate package. Reuse the existing safe Node-tool staging
owner and one shared audit implementation. Each package must audit its complete
development dependency graph before execution; unavailable audit, high/critical
advisories, expired or stale exceptions must still fail. Add the missing explicit
audit to OpenSpec validation. Preserve both checks in full CI, Windows qualification
and release qualification. Ordinary documentation work must not install the CLI
or its unused dependency tree. Do not duplicate browsers, change browser sandbox
policy or claim that a dependency split remediates OpenSpec's vulnerability.

Verify the split through actual Make and npm entry points with isolated disposable
object roots: documentation audits/renders normally without OpenSpec installed,
while OpenSpec validation refuses the currently vulnerable locked graph before
validation. Check direct Windows CI/qualification commands and the website's
module-resolution/cache paths as well as Make. Run independent source review,
full source qualification and affected hosted checks before landing. OpenSpec and
release readiness remain blocked until an actual dependency repair or separately
reviewed policy decision exists; this work closes no release acceptance item.

### Observed local source, wheel and installation qualification

[PR 470](https://github.com/jordanhubbard/literate-ai/pull/470) records the
documentation/OpenSpec separation at exact commit
`18d98aab3588b3112323ead2fdd959fd785803f4`. Its complete local macOS ARM64 / Python
3.14 source gate selected 3,182 cases: 3,079 passed, 103 retained their declared
skips, and none failed. The Python suite took 2,683.591 seconds; the complete
source/review/lint/format invocation ran 04:21:55–05:07:02 UTC on 2026-11-18.
The retained canonical test report has SHA-256
`281bb05a91800f429f7cdf3424e8fff4bb71632020d89a0a4ff5fa4aaf5e6afd`.

The canonical local noneditable wheel gate passed at the same clean commit,
05:25:21–05:39:00 UTC. All 182 retained operation-timing spans report success;
their durations overlap and must not be summed as release wall time. The tested
wheel has identity
`sha256:7d06fb98510f526e6d75b7a6e43e3c94d01a1ba31a3517193725e2f7ab680215`.
Its installed native-adoption journey preserves five application files, writes
zero external files, detects and repairs the native test failure, and preserves
custom policy during no-churn update and staged owned removal. This renews that
local installed journey; it does not establish an upgrade between two released
framework versions or qualification on another platform.

A separate canonical model-free `install-check` then passed, 05:55:41–05:58:35 UTC,
installing those same wheel bytes through the supported qualified-wheel exporter
and installer. The first invocation supplied a portable retained manifest where
the installer requires repository-relative paths; it refused before installation.
That caller error and its log remain separate from the corrected passing run.
No wheel was rebuilt or substituted, no live model was used, and no source or
release acceptance was changed. OpenSpec's dependency advisory, unresolved
security-check findings, exact-head hosted checks and the remaining native and
release requirements remain separate gates.

The subsequent hosted Linux / Python 3.11 job in
[run 44243126217](https://github.com/jordanhubbard/literate-ai/actions/runs/44243126217)
is terminal-failed, not green: its raw unittest summary reports 3,142 tests with
114 skips and no failures in 3,101.812 seconds, followed by the required OpenSpec
audit refusal for the same advisory. These are raw unittest counts, not a new
canonical unique-case reconciliation. The job spans 05:17:01–06:09:44 UTC;
installation already reports four derived high findings at 05:17:32.477 UTC,
while strict audit refusal arrives at 06:09:40.736 UTC, 52 minutes 8.259 seconds
later. RELEASE-CLOSURE-001's existing early-refusal work therefore has another
measured case: preserve the dependency audit and move cheap failure feedback
ahead of the long suite. This would avoid long execution on this already-bad
candidate, not eliminate the suite from a repaired release. No new gate ordering,
latency improvement or waived check is claimed by this observation.

### Controlled OpenCode V1 ambient-configuration evidence

SDLC-001's existing isolation review and OPENCODE-COMPAT-001 retain ownership of
this evidence. At the reviewed adapter bytes in `18d98aa`, the actual pinned
OpenCode 1.19.5 CLI retains a synthetic global instruction file and a disabled MCP
entry despite the product's inline `instructions: []`, `mcp: {}` and wildcard
tool denial. The empty-global control retains neither entry. These prompt-free
checks run with synthetic default-discovery roots, OS-level network denial and
writes limited to the disposable fixture; actual user configuration is untouched.

A second controlled run uses the production command/environment owners, the same
synthetic roots, an owned stdio helper and a loopback provider that always returns
HTTP 400. The OS permits only that fixture's loopback port. The seeded global
configuration starts the stdio helper and places the instruction sentinel in the
captured provider request; the empty-global control does neither. Both requests
retain the explicit task sentinel and both end with the expected provider refusal.
No real provider credential, model inference, external MCP or live deployment is
involved. An initial sandbox-profile parse refusal is retained independently;
it is not evidence about CLI behavior.

This establishes the pre-fix mechanism under controlled global inputs, not an
observation of this user's actual configuration or production egress. Existing
empty-global native tests and permission-map assertions do not cover the merge
boundary. Saved-login and custom-provider compatibility remain required; importing
an entire global configuration or copying opaque account state into a private
directory would not establish isolation. The source repair and its compatibility,
installed/native and release checks remain unperformed; this narrative neither
closes nor changes any existing acceptance obligation.

### Observed hosted producer and interrupted-export recovery

[PR 465](https://github.com/jordanhubbard/literate-ai/pull/465) supplied actual
GitHub-hosted evidence on exact source `af11434c90d58489a923114a8d8f0c7bdb1ebba0`.
[Attempt 1](https://github.com/jordanhubbard/literate-ai/actions/runs/44128504174/attempts/1)
completed native Linux and Windows build/test jobs and a dependent exporter. The
production adapter consumed all four cells using actual provider transport and
verified the 820-byte uploaded archive, artifact `14349306208`, against digest
`sha256:2fcb34e8005101a1320c4053dd724952168237d4fe6801bae678235ff484f5d8`.
The first job start to last completion was 60 seconds; summed job envelopes were
68 seconds (Linux 11, Windows 26, exporter 31). These fixture intervals measure
neither a full framework release nor CPU or billed runner use.

The bounded recovery experiment reran only this pilot workflow. Both native jobs
finished before cancellation; the exporter was cancelled during dependency
installation in attempt 2. This proves interrupted export, not interruption of a
native build/test action. With that attempt terminal-cancelled, the unchanged
production adapter refused coverage with `incomplete`, despite the retained
attempt-1 success and archive. Failed-jobs retry created a fresh attempt-3
exporter, job `134202153982`, while GitHub retained both native successes under
new current-attempt job IDs with their original attempt-2 execution timestamps.
[Attempt 3](https://github.com/jordanhubbard/literate-ai/actions/runs/44128504174/attempts/3)
completed successfully, and actual adapter consumption again accepted all four
cells. The new 821-byte archive, artifact `14349336871`, has digest
`sha256:61a7834414e1c3b60457f53d58345e83504c744f4671e1319935a5a178f2a420`.
The older source-review record's pending hosted fields describe its earlier
checkpoint; these later observed results add evidence without changing its scope.

The pilot demonstrates actual native Python execution on hosted Linux and Windows,
artifact transfer and interrupted-export retry. It does not establish other
languages, CPU/GPU targets, installed-consumer or consuming-repository public
release qualification, binary artifact custody, strict promotion, deployment or
recovery of a delivered application. Those existing acceptance requirements and
all unresolved security findings remain in force; no roadmap goal is closed or
weakened by this narrative.

### Completed supplied-guidance measurement, acceptance boundaries retained

SDLC-001 now has 45 actual fresh-cohort attempts: three native tasks, three arms,
five randomized repetitions per task/arm on one pinned CLI/toolchain and configured
model selector. The current native-adoption SKILL plus linked policy is compared
with pinned Superpowers verification-before-completion and no optional guidance.
The provider's immutable model revision is unavailable. This exercises supplied
guidance, not natural activation, an installed governed PR, or a platform matrix.

Independent review finds 44 normal completions with correct repairs, preserved
original test semantics/authority and model-performed fresh local checks. Nine
completed attempts nevertheless make unsupported release-readiness claims. One
remaining baseline attempt patches correctly but aborts after malformed tool calls
before verification/reporting; it stays a failed attempt and is never replaced.
A prospective reviewed continuation resumes only untouched slots. The nine earlier
exploratory attempts, whose strict byte guard falsely rejected valid Go test
changes, remain separate. Raw verdicts and interrupted output are not rewritten.

| Arm | Native/private checks complete | Overall success | Median CLI seconds | Median tool events |
| --- | --- | --- | --- | --- |
| Current native-adoption guidance | 15/15 | 13/15 | 41.473 | 20 |
| Superpowers verification-before-completion | 15/15 | 9/15 | 46.643 | 19 |
| No optional skill | 14/15 | 13/15 | 36.563 | 17 |

The shared prompt requests `release_ready`; required macOS/Windows platforms are
in immutable repository policy, with expanded prose only in the handoff task.
These are unsupported claims, not nine bad repairs or observed unsafe releases.
The current arm reads all three supplied resources on every attempt but does not
establish an overall success gain over baseline in this small sample. Keep the
minimal context and deterministic qualification; do not infer a need for more
prompt ceremony or a justification to retire all guidance.

The measured cohort spans 3,193.280 seconds between first recorded start and last
finish: 1,975.786 seconds summed CLI time, 1,139.635 seconds of interruption-to-next-
attempt review/continuation gap, and 77.858 seconds unattributed. This is not pure
inference or release time. Setup, review labor, underlying model weights and actual
billing remain incompletely observed. Reported token/cache counters are separate
fields; reported zero cost does not mean free inference.

The [dated report update](../architecture/existing-repository-review.html)
contains per-task outcomes, usage, protocol/aggregate identities and limitations.
This records a completed bounded measurement, not completion of SDLC-001 or its
activation, governed-adoption, changed-version upgrade, platform or release gates.

### V1 selected-profile isolation in progress

SDLC-001 and the existing OPENCODE-COMPAT-001 implementation owner retain the
controlled ambient-input finding in this release. Use the existing coding-CLI
process/configuration owners: establish private discovery, database, cache and
temporary roots before the first child, then passively select the requested
provider and supported API credentials. Preserve selected custom-provider
configuration, saved API keys, bounded JSONC/file-credential handling and explicit
model selection. Do not execute native debug configuration against ambient state
to discover its contents. Preserve the existing V2 profile and detached workspace.

The narrow initial profile supports demonstrable API authentication. Stored
rotating OAuth, remote integration/account configuration, managed overrides and
unsupported credential/SDK sources require explicit native ownership support or
a typed refusal before model execution; they must not silently become API billing
or another provider. API projection must not rewrite user credentials, and a
generic copy-back or competing refresh manager is outside this repair. These
limits are not evidence that OAuth was previously unsupported, nor completion or
retirement of broader compatibility requirements.

Verify the actual pinned V1 with owned loopback targets and synthetic credentials:
saved API and custom-provider positives, JSONC/relative credential handling,
retained explicit task instructions, and refusal or absence of ambient global
instructions, MCP helpers, optional skills and unsupported stored integration.
The native project-config flag already suppresses initial ancestor instruction
discovery; test parent AGENTS/CONTEXT sentinels and a deliberately enabled positive
control without adding a temporary Git abstraction. Keep nested-read and provider
internals limitations explicit. Redact individual projected credentials from
verbose output and retained diagnostics, invalidate the old isolation profile,
then independently review and renew source, installed/native and platform checks.
No profile repair or expanded compatibility is claimed by this plan.

The draft additionally filters the selected provider's models to the exact model
and checks model-level SDK overrides before child execution. Serialize projected
literal values so native config parsing cannot expand file/env placeholders a
second time. These two boundaries were found during independent source review;
maintained public-runner controls cover both, along with saved API, env/file keys,
refresh/well-known refusal, ambiguous/oversized input, missing model and original
state preservation. They are repair evidence, not broader provider qualification.

A renewed pinned V1 control uses six synthetic profiles and a write/network-
restricted loopback provider that deliberately returns HTTP 400. Supported API
profiles send one task request, the selected refresh profile sends none, global
instructions/MCP remain absent, a deliberately enabled parent-discovery positive
control is detected, and a literal placeholder credential reaches the endpoint
unchanged. This is native transport/refusal evidence on macOS ARM64, not successful
model delivery. The maintained native V1 workspace-write/outside-read checks pass;
V2 was initially skipped because its native binary was unavailable. The later
source/native qualification below supersedes that local skip; installed and
other-platform acceptance remain open.

### Early Make refusal before expensive qualification work

RELEASE-CLOSURE-001 owns this in-progress implementation of the measured late
audit finding. Keep the same validation and release gates, existing safe tool
staging, dependency audits, source checks, checkpoint freshness and exact wheel
custody. Complete cheap validation before starting the long Python workload;
ordinary `python-check` remains independently runnable for source diagnosis.
Parallel Make must not race the expensive phase past a failing preflight. The
implementation must remain compatible with the native GNU Make 3.81 entry point.

Verify the real Make entry points with bounded controls: a failing dependency or
authority gate must not start expensive work, including under parallel execution;
the passing control must retain every original gate. Reorder the existing release
gate sequence without changing its membership or allowing diagnostic repair state
to become release admission. A changed gate order must retain the existing
checkpoint-plan reset/refusal behavior. Renew the complete source gate and affected
documentation/CI checks after independent source review. This slice changes the
framework's own Make harness; it does not replace a consuming repository's native
tools or waive the advisory, security incidents, installed or platform acceptance.

### Repeated skill metadata parsing under native currentness

CARGO-CUSTODY-PERF-001 owns the next bounded cost reduction. An instrumented
single native-fixture currentness call rebuilds 68 catalogs while retaining its
17 wrapper authority checks. Reuse only immutable parsed metadata for identical
manifest bytes within the existing project-parse lifetime. Every read, namespace
check, digest, dependency/reference decision and process boundary stays live.
Bound entry count, individual key size and total retained key bytes, restore
ambient frames after isolated calls, and fall back to uncached parsing at limits.
Validate semantic drift/refusal and equivalent identities before any performance
claim. A profiled call is not a release critical path or a paired speedup result.

The [paired metadata observation](../../verification/skill-metadata-parsing-measurement.json)
uses one real retained native fixture and toggles only the new syntax cache.
All eight calls return the same identity and retain 17 wrapper guards, 6,630
current document reads and 4,352 manifest hashes each. Four samples per arm show
3.795s versus 3.472s median currentness time; 667 parses remain, including first
observations and oversized manifests that bypass the 8 KiB admission limit. Keep the claim scoped:
this is an 8.5% observed single-fixture reduction, not a release speedup or proof
that more custody checks should be removed. Independent final review, memory/
concurrency controls and full composed qualification remain prerequisites.

### Module scheduling after observing the complete tail

TEST-PARALLEL-001 owns a small dispatch change justified by the completed parent
module trace. Keep every module intact and preserve default order and serial
barriers. Admit an explicit bounded `LITAI_TEST_PRIORITY` hint on test modules,
stably ordering only contiguous nonserial segments; mark the observed expensive
native-Cargo group. Successful qualification still requires every selected case;
none is reused or independently split. Fail-fast may change which peers had
started before a failure; validated outcomes and cleanup remain authoritative. Compare
real subprocess dispatch and the next complete run against the fixed-duration
[counterfactual replay](../../verification/module-priority-replay.json). The
simulation is a candidate scheduling estimate, not achieved release latency.

### Reviewed source composition checkpoint — 2026-11-18

The [private-profile local proof](../../verification/opencode-private-profile-local-source.json)
records the frozen source gate committed as `57d31db17`: 3,183 selected cases,
3,082 passed, 101 declared skips and zero failed/known-failed; Python time
2,694.916s. All 13 independently reviewed subjects remain exact. A receipted
native run binds both real V1.19.5/V2.2.5 binaries and passes two owned-loopback
write/outside-read cases without skips. This supersedes the earlier unavailable-V2
checkpoint, not installed, paid-model, foreign-platform or release acceptance.

The next candidate combines that source with the independently reviewed early
Make gates, bounded metadata parsing and measured-module priority. Runtime,
maintained test and evidence bytes are copied exactly from their approvals;
roadmap/changelog conflicts are additive unions. Record new supported authority
pins only after independent composition review, then freeze and qualify the
whole union. Prior source, CI, wheel and installation results do not qualify it.
The actual 57-second audit refusal belongs to Make source `d383f294`, while the
665-second scheduling improvement is still a fixed-duration simulation.

### Qualified local composition and early hosted refusal

[PR 475](https://github.com/jordanhubbard/literate-ai/pull/475) publishes exact
commit `8ada5c649a14539c2882f57618b364ba55b0067b`, combining the independently
reviewed OpenCode private profile, early Make barrier, bounded immutable skill
metadata parsing and explicit module priorities. Its fresh complete local source
gate selected 3,185 cases: 3,084 passed, 101 retained their declared skips, none
failed. Python took 1,971.460 seconds and the complete invocation 1,996.558 seconds.
The canonical report SHA-256 is
`ec1b9f507a7da46d2e841c8aef1d656f2ef236f116c650e85ed11bc33bd128d3`.
Driver/documentation reviews, lint, formatting, documentation, layout and exports
passed. All 25 reviewed subjects remained exact during qualification.

The actual eight-case native Cargo group began setup at 0.030 seconds and
finished before the suite's final module; the earlier native-only tail was absent.
The preceding qualified source invocation took 2,720.671 seconds. This observed
pair combines multiple changes and shared-host/cache effects, so it establishes
neither a causal per-change speedup nor a general release-time reduction.

The canonical noneditable wheel gate passed at that clean commit with all 182
recorded operation spans successful, 09:48:36–10:02:29 UTC on 2026-11-18. Its
wheel identity is
`sha256:55fb5b9e916fb24fe8f5c54fa3f80d27b0da4e113483edf878f3b4b6d1b92b47`.
The separate canonical model-free installation check passed using those same
exported bytes, 10:02:52–10:05:48 UTC (176.191 seconds). Dependency installation
used the configured package source; this is not a network-offline run or
foreign-platform/release qualification.

Actual exact-head [CI run 44282187110](https://github.com/jordanhubbard/literate-ai/actions/runs/44282187110)
Linux job `134725632383` failed its mandatory OpenSpec dependency audit on
`GHSA-fc5q-39xc-vjpf` in picomatch before the complete Python suite began. The
job ran 10:06:36–10:07:20 UTC, 44 seconds. The retained pre-barrier job took
52m43s before the same refusal. This proves earlier refusal while preserving
the failed dependency gate. GitGuardian also fails; incident disposition,
remaining current-head checks, landing and release acceptance stay open.

### Additional local Rust adoption fixture

A realistic dependency-free Rust/Cargo fixture uses native Cargo manifests,
lockfile, source, tests, Make wrapper and its existing CI file. Actual installed
baseline 18d98aab3 preserves all eight original files and adds 15 files only under
`litai/`; plan takes 0.937 seconds and apply 1.481 seconds. Public authority
validation and read-only parent-README/agent-entrypoint audits succeed, with no
README change. A seeded overflow case fails real Cargo tests in both debug and
release modes; checked addition repairs both. This is an owned local macOS ARM64
fixture and uneven-coverage experiment, not a hosted governed PR or additional
platform qualification. Original application bytes are restored after probing.
At this checkpoint the hosted Python pilot was awaiting authorization. Its later
[governed PR and partial retry](#hosted-governed-pr-and-partial-retry) exercised both platforms.

The authentic installed 18d98aab3-to-8ada5c6 revision transition subsequently
passes for both Python and Rust fixtures. Both distributions declare 1.4.0;
this is not a changed-version migration. The supported installer reuses the
exact qualified current wheel, and installed import paths and archive digests
are checked before and after. Native file hashes, custom policy, Git HEAD/index
and durable framework metadata are unchanged. The first update's stable ignored
lifecycle lock is inventoried separately. Unchanged templates mean this also
does not establish changed-template migration behavior.

A separate current-wheel Rust removal journey preserves all eight native files,
the custom operating note and HEAD while staging fourteen owned deletions.
Repeated adoption first returns `original_adoption.already-initialized` without
file/index changes. After removal, Cargo's original ordinary-quantity test still
passes in release compilation mode; the overflow regression/repair is the
separate earlier experiment. Deleting the owned ignore file exposes retained
`.litai-locks/` as untracked, so the removed fixture is deliberately not reported
clean. An earlier caller parsed error JSON from stdout instead of its actual
stderr channel and stopped before removal; that failed attempt is retained.
Neither journey is a hosted governed PR, release publication or foreign-platform
qualification. Independent closing review rechecked the logs and preserved bytes.

### In-progress release goals remain incomplete

The read-only 1.4 contribution sweep at 8ada5c6 reports two existing in-progress
goals as missing and one historical item as absent from the manifest. Its reader
accepts only space/x checkbox states, skipping the supported `~` section boundary
and attributing the following release target to the historical item. The narrow
correction in [issue 476](https://github.com/jordanhubbard/literate-ai/issues/476)
recognizes that boundary and keeps `~` incomplete; only `x` establishes completion.
The maintained real-Git contribution fixture reproduces both errors on the old
reader while space/x controls pass. All seven contribution methods pass after the
correction in 3.238 seconds. No goal, release target or manifest membership changes;
full source/authority qualification remains a separate gate.

### Owned wheel workspace path aliases

The complete clean-candidate wheel gate at c37ea0c fails twice during uv dependency
installation: first a package-index route failure, then a dependency-read timeout.
A third complete attempt using independently reviewed local native dependency
wheels passes uv installation, then fails the verified-wheel source-path guard.
The harness created its own snapshot beneath macOS’s redirected `/var` temporary
root. An actual installed public-CLI causal probe rejects that lexical spelling
and accepts the canonical `/private/var` spelling with the same 36 wheel hashes
unchanged. [Issue 477](https://github.com/jordanhubbard/literate-ai/issues/477) owns
canonicalizing only the newly created harness workspace before staging snapshots.
Arbitrary redirected user-input paths retain their fail-closed guard. The probe
is diagnostic evidence; a fresh complete source gate and complete installed-wheel
gate remain required, and none of the three failed attempts qualifies c37ea0c.

### Fresh candidate platform and worker protocol evidence

At `98c23928add1c8c524a8aa3f36a0555479e59ca0`, the owned-workspace correction
passes the complete fresh macOS source gate (3,084 pass, 101 declared skips),
182 complete wheel spans and a separate canonical model-free install. The same
wheel passes native Linux ARM64/Python 3.15.2 and 3.11.18 complete whole-wheel
runs, each with 183 successful spans and non-null ordinary/uv worker paths.
Framework and dependency identities are checked across installation; actual
empty and redirected dependency-input controls refuse before observed Python
subprocess launches. The earlier network, alias and copied-interpreter loader
failures stay failed. Historical missing raw evidence is not reconstructed.

A separate actual static-worker Linux x86_64/Python 3.14 adoption journey passes
native failure/repair, unchanged/no-op update and removal while preserving
application bytes,
HEAD, existing application staging and custom content while staging only owned
removals. A restricted downloader initially refuses its
private evidence path; bounded read-only SSH recovers the existing digest-verified
bundle without rerunning the job. This is not a hosted governed PR or GPU proof.

A 35.6-second experiment then exercises the installed current dispatcher over
real SSH beneath a private simulated lease provider. It verifies lifetime
refusal before launch, active-job drain, exact cancellation with lost-reply
recovery while allocation is disabled, late-result rejection and recovery without
a duplicate allocation call. Both finite remote children finish; the private
catalog is empty and actual static registrations are unchanged. The explicit
fixture lifecycle handler does not prove canonical receiver execution, custody
import/acknowledgement, real provider termination, mid-job controller cleanup
or release qualification. Those acceptance boundaries remain open.

A separate 34.4-second post-result interruption control completes a real finite
SSH command, then exits its coordinator with status 23 before the managed dispatch
context can record completion. The active journal survives; retry refuses before
the handler or SSH launch. Ordinary release drains without calling the provider;
a wrong token leaves the journal unchanged; exact cancellation and retry use one
logical release. Retained static catalog bytes match before/after. Its first
attempt fails on a private fixture float in canonical JSON before the intended
exit; that failed run and separate logical-lease recovery remain preserved.
This proves the post-result/pre-publication boundary, not mid-job process loss,
remote physical termination or canonical lifecycle artifact acceptance.

Current-head CI run `44312804737` reports 14 passing jobs, one skip and a mandatory
OpenSpec advisory failure in the Linux Python 3.11 job, which completes in 62
seconds. Documentation validation and the native coverage pilot pass; GitGuardian remains failed without
a disposition. This continues to demonstrate early refusal rather than remediation.
The source and wheel evidence above belongs to the exact named candidate; no
result is promoted to resulting-main or complete-release acceptance.

A fresh installed Linux x86_64/Python 3.14 admission supplies genuine accepted
source for the canonical receiver in 51.4 seconds. All 37 installed distributions
are verified and 147 original project/cache files are transferred unchanged. The
harness neither reads nor directly invokes private acceptance values; the normal
verifier retains that authority. The same qualified `98c23928a` wheel then passes
a 65.8-second public SSH lifecycle through the canonical handler, installed
receiver, actual archive transfer, verified import and cleanup acknowledgement.
TEST transports the accepted artifact; RUN passes valid input and returns actual
application exit 1 with a typed failed dispatch for invalid input. All three
bundles (80 file entries) are independently reimported and their three raw
acknowledgements verified. RUN reuses the TEST export and transports fresh
execution evidence, without another artifact copy. Original project bytes remain
unchanged; exactly one validated execution export is added. A first private
preflight assertion incorrectly treats explicit Flavor overrides as resolved
defaults and stops before public dispatch; its failure and separate idle-lease
recovery remain retained.

A separate 49.8-second controlled fault run changes one byte only after an actual
SCP download succeeds. Public RUN returns exit 2 with
`execution.remote_evidence_bundle_mismatch`; the coordinator evidence store stays
unchanged, the exact managed attempt remains uncertain, and the original worker
ticket, bundle and work roots remain without a successful acknowledgement.
Unfaulted real transfer retrieves that same original bundle. The existing importer
verifies it before the existing public worker acknowledgement path removes the
exact owned attempt roots and incoming directory. No application rerun occurs.
The original public failure stays failed; manual custody recovery is recorded
separately. Exact-attempt cancellation then closes one simulated logical release.
Prior completed evidence, source inputs and static registrations remain unchanged.

These records establish canonical custody and controlled post-download corruption
recovery using existing owners. They do not establish a genuine network-failure
recovery, automatic public dispatch resume, physical provider termination,
automatic lease release, total allocation-through-cleanup deadlines, Windows/GPU
acceptance or release readiness. The earlier offline corrupt-copy control still
represents a distinct check performed after acknowledgement.

## Reviewed action updates in the 1.4 recovery queue

The refreshed contribution survey retains all 81 release goals, including the
46 still open, without target changes or invalid entries. PRs
[#474](https://github.com/jordanhubbard/literate-ai/pull/474) and
[#473](https://github.com/jordanhubbard/literate-ai/pull/473) each have five passing
or declared-skipped checks at their observed exact heads. Their three action
references were absent from the combined candidate and are now merged into its
separate local reconciliation queue: FreeBSD VM is pinned to
`811efaaac0668df8bfb8308c3ec997b5ab50037b` (1.6.0), and Bazel setup to
`f34d6a05eae3c24acab7fa54587492daeaeffdab` (0.19.2).

The two changed workflow documents parse successfully as YAML; no job, native
platform selection, source scope or execution deadline changed. This queue does
not alter the source-frozen candidate already undergoing native qualification.
The integrated native and full CI gates remain pending; these dependency updates
do not close FreeBSD, Bazel or release acceptance requirements.
