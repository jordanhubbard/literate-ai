# Existing repository delivery program

- **Status:** active
- **Owning queue item:** [SDLC-001](active-work.md#sdlc-001-make-existing-repository-delivery-the-primary-14-adoption-path)
- **Completion / archival evidence:** pending implementation and pilot qualification

[ADR 0074](../decisions/0074-existing-repository-delivery.md) records the directing
user's implementation delegation and the target architecture. The baseline review
is tied to `f34debb73b62f9fff59a138f86b3640d7be65183`, not to unfinished worktrees.

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

## Consolidated ownership

| Workstream | Existing owners to reuse | Added acceptance |
| --- | --- | --- |
| Native adoption and containment | ORIGINAL-ADOPT-001, ADOPT-CLI-001, ADOPT-RELOCATE-001, PROJECT-LAYOUT-001; ADRs 0057 and 0071 | Public minimal onboarding preserves native source and CI; repeat, upgrade, recovery and removal use an exact external-file allowlist. |
| Qualification cost and evidence | TEST-CACHE-001, TEST-PARALLEL-001, RELEASE-CLOSURE-001, RETAINED-RECEIPT-PROMOTE-001, existing observation-cost items | Correlated timing, early cheap refusal, exact candidate/environment/artifact cell reuse, no duplicate native assertions. |
| Worker lifecycle | WORKER-001, COMMAND-WORKER-001, WORKER-TELEMETRY-001, RELEASE-CANCEL-001 | Observe lost replies, release owned leases idempotently, enforce expiry, preserve static workers and uncertain refusal. |
| Roadmap and guidance | AUD-STATE-001, RELEASE-INTEGRATION-005, SKILL-DISCOVERY-001 | Unique IDs, current execution view, explicit supersession, no conflicting Superpowers activation, behavioral skill comparison. |
| Support and optional capabilities | Current native/GPU/SDK goals and RELEASE-COLLATERAL-001 | Revision-bound support cells; native adoption does not require generator/media setup; production deployment boundary is explicit. |

The table combines execution ownership; it does not mark the listed goals
complete. The current release's existing 79 goal records remain obligations until
their own terminal evidence or an explicit recorded disposition establishes
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

For skill comparison use three tasks, current/alternative/no-skill arms, a pinned
model/tool image, randomized order and at least five independent repetitions per
cell. Measure activation, task success, unsafe actions, unnecessary steps, tokens,
elapsed time and manual interventions. The review's instruction comparison is
not a behavioral benchmark and does not satisfy this acceptance.

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
