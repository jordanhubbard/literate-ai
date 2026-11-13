# Retained-layout placement, relocation and recovery

- **Status:** active
- **Owning queue item:** [ADOPT-RELOCATE-001](active-work.md#adopt-relocate-001-support-selected-and-relocated-retained-implementation-layouts)
- **Completion / archival evidence:** pending while ADOPT-RELOCATE-001 remains open

[Accepted ADR 0057](../decisions/0057-retained-implementation-layout-and-relocation.md)
owns the complete behavior. This execution order preserves initial plain/root/custom
placement, relocation into and out of root, recovery and genuine evidence renewal.
Structural lookup and a read-only proposal alone do not complete the feature.

## Execution order

1. **Complete namespace and partition custody (in progress).** Capture actual raw
   bytes, executable modes, directories, internal aliases and complete hardlink
   groups under explicit finite budgets. Reuse the reviewed streaming tree reader
   with no implicit exclusions or payload copies. A proposed framework partition
   contains exact file names, never whole-directory or ignore-pattern exclusions.
   Discover every other actual namespace entry, including future files, empty
   directories and ignored-looking names. Reject nonexistent ownership entries,
   portable aliases and links crossing the proposed partition. Shared ancestors
   confer no exclusive directory ownership. A census describes bytes and proposed
   labels; it grants no movement, exclusion, execution or qualification authority.
2. **Structural renewal and qualified use.** Wire the accepted resolver through
   scope refresh, readmission, native rewrite, current locks, receipts, Cargo and
   monorepo discovery. Renewal must locate structurally current unqualified source;
   admission must refuse historical locks/receipts. Keep the unsupported apply
   guard until the transaction owner is complete.
3. **Transaction and recovery owner.** First provide separate exclusive native
   entry movement for files/directories/symlinks with expected source facts and
   pinned parents. Directory-only publication contracts stay unchanged. Occupancy,
   portable aliases, cross-device moves and unsupported native calls refuse;
   post-effect conflicts retain all observed nodes for the future journal owner.
   This helper alone does not hash a complete subtree or authorize any movement.
   The transaction caller must establish full source custody and durable intent
   before invoking it. Then bind actual project/conversion authority,
   current source/partition, exact affected authored bytes and destination absence.
   Hold canonical lifecycle locks and descriptor reservations. Bind actual Git
   administration/index and lifecycle control nodes as protected, nonmoving
   authority before deriving any move from a census; namespace labels or a `.git`
   spelling alone cannot grant that ownership. Preflight one filesystem and native
   exclusive moves. Persist bounded private old/prospective bytes and durable phase
   intents before the first effect. Implement explicit authorized recovery with
   fresh reservations, foreign-state preservation and precise incomplete results.
4. **Initial placement.** Route existing acknowledged adoption through that owner
   for a plain directory and custom wrapper, then the root overlay. Preserve legacy
   defaults and baseline/parity owners. Keep the repository and Git administration
   fixed; do not move a shared ancestor as if it belonged to one partition.
5. **Relocation.** Add exact-plan public plan/apply and recovery, including
   plain-to-plain, plain-to-root, root-to-plain and wrapper changes. Publish layout,
   lift-shift lineage, wrapper configuration and affected manifests coherently.
   Successful publication is structurally current and explicitly unqualified;
   retain old receipts unchanged and invalidate their applicability.
6. **Complete acceptance.** Qualify noneditable installed public adoption,
   relocation, update, refresh, ordinary lock renewal, baseline/parity, readmission
   and fresh receipt creation for every layout cell. Prove old-receipt refusal,
   original bytes/modes/internal aliases/hardlinks/Git custody, stale and changed
   inputs, foreign destinations, portable/escaping aliases, cross-boundary links,
   cross-device refusal, concurrency and interruption at every publication/move
   phase. Complete independent source review, applicable actual native evidence,
   exact integration and release gates before closing the owner or issue #265.

## Current capture contract

The first primitive is read-only and retains metadata/digests/link text, not payload
copies. It accepts a complete proposed exact-file framework partition and an
explicit existing streaming custody budget. Its ceilings remain those of the
reviewed reader; oversize/unsupported inputs refuse without mutation. Every
capture traverses the complete supplied root, with **no exclusions**, including
Git/control names when present. Such names are facts, not source-movement rights.
The transaction phase must obtain their actual separate control authority before
planning effects. A source/framework partition is descriptive until independently
joined to current initialization/layout/lock authority.

The census identity binds complete logical bytes/topology, physical namespace nodes,
original ancestry and proposed labels. Changing a label or physically replacing
identical bytes changes that identity. Fresh currentness
reopens the whole namespace and compares original physical nodes, bytes, modes and
link topology. Cross-partition hardlinks and symbolic aliases, including aliases to
mixed directories or through aliases in another partition, refuse. Mixed ancestors
remain shared; empty directories remain non-framework namespace entries.

## Boundaries still open

No new CLI apply cell is enabled by this first primitive. Git/control-owner
binding, actual transition/journal/recovery, renewal consumers, initial/root/custom
apply and all installed/native/full-feature acceptance remain required work.

## Durable journal dependency (source reviewed)

The POSIX private journal holds an actual writer mutex across preparation and
explicit reopening, pins its original ancestry and descriptors, and invalidates
the writer after context exit or process inheritance. Callers provide canonical
bounded project/plan binding bytes and a finite storage/event/payload/stage budget.
The storage parent is caller-selected private framework state and may be inside
the project's framework partition; no external-home or legacy metadata location
is prescribed. This dependency does not implement the pending containment migration.

Raw before/prospective payloads and hash-linked events publish from exclusive
private stages using native no-replace rename and file/directory synchronization.
Before any caller can perform an effect, the completed write closes over the
complete private namespace, original ancestors, held mutex and stored bytes.
Failed writes poison the current writer. Explicit fresh reopening validates the
same binding/budget and every present record/payload, preserves partial stages as
diagnostics, and obtains a fresh actual OS mutex. No record or saved phase grants
movement, deletion, control ownership or successful recovery. Missing historical
intent cannot prove that an external effect did not occur: the surrounding owner
must freshly classify every actual endpoint and refuse unknown state.

The fifteen maintained controls cover actual process death, competing
writer refusal, process/context lifetime, raw payloads, present hash chains,
interrupted staging/synchronization, foreign namespace and physical replacement,
finite input bounds and storage inside the framework partition. Three controls
fail the original journal: existing and race-inserted foreign empty locks gain a
placeholder byte, and currentness returns across a newly inserted foreign entry.
The repair uses existing-only, non-initializing recovery lock acquisition and
closes namespace membership after reading all records. Independent re-review
reproduces all three original failures and passes the repaired fifteen methods
plus seven supplementary controls, including actual storage/stage exhaustion and
acquisition/closing faults. The seventy-method affected neighborhood passes with
no skips. The [source evidence](../../verification/retained-layout-journal-development.json)
retains exact subjects and the unchanged shared helpers. Native Windows durability,
actual project/Git/control binding,
canonical project reservations, endpoint classification and every public L4-L6
placement/relocation/recovery/renewal cell remain required before feature acceptance.

## Retaining live reservation controls (source reviewed)

The existing descriptor-backed reservation owner gains an explicit, one-way
retention request for a complete live reservation set. A transaction selects it
before effects whose recovery needs the controls. Both normal and failed context
exit keep every marker and created parent while attempting to close every held
descriptor and release its OS lock. The owner becomes inactive. A currentness
conflict during retention also keeps all other controls; it cannot fall back to
ordinary cleanup. When both the body and descriptor release fail, retain both
errors. Callers that do not select retention keep their existing cleanup contract.

Retention neither journals acquisition nor authorizes later cleanup or source
effects. Existing generic acquisition still creates public parent/marker inodes
before they can be recorded, so it cannot implement the complete crash-recoverable
layout preparation. The layout owner must first stage known nodes privately and
persist exact publication intent before creating any public control. It must bind
actual canonical lifecycle and Git writer roles, retain ambiguous controls and
freshly classify endpoints under new descriptors for acknowledged recovery.
The initial seven controls and seventy-one-case neighborhood pass, but independent
review reproduces an interruption during release that leaves a later descriptor
open. Two new causal controls fail that exact source. The repair catches each
release failure, attempts every remaining descriptor exactly once, and preserves a
single interruption or a bounded mixed failure group. OS-only failures keep their
typed cleanup diagnostic with underlying causes; body and release errors remain
visible together. A reported failed close is not retried, since its native outcome
may be ambiguous and the descriptor number may have been reused. Nine retention
controls and the three existing critical marker controls pass after repair.
Independent re-review reproduces both original failures, passes all twelve methods
and six supplementary controls, and confirms unchanged default cleanup and shared
helpers. The seventy-nine-case selected neighborhood also covers actual Git writer
reservations, object installation and Cargo materialization. The [retention evidence](../../verification/retained-layout-reservation-retention-development.json)
binds exact source and fault-scheduling limits. Native and integrated qualification,
staged acquisition and the complete transaction/recovery owner remain required.

## Journaled control publication (source reviewed)

Create marker files and empty control directories in caller-selected private
framework state, bind actual nodes and bounded bytes, and persist exact source,
destination and parent intent before any public publication. Hold original parent
descriptors and actual journal writer custody through exclusive native movement,
file/directory synchronization and closing endpoint checks. A spent private entry
cannot be replayed; failures retain every observed node and stop further effects.
This supplies known nodes for the actual reservation owner to reopen under fresh
FD/byte/native-identity checks. It does not infer canonical lifecycle or Git roles,
grant source movement or turn journal records into recovery ownership. Complete
role binding, staged acquisition/recovery, platform and installed acceptance remain
required before public apply is enabled.

The first twelve controls pass, but independent review reproduces private
insertion after the final journal read and consumed-source repopulation after the
final destination read, both returning success before context exit. Three maintained
regressions also cover a known private-stage mutation at the journal boundary;
all three fail the exact original bytes. The repair closes bounded private names,
every remaining stage's full native facts and names again after the last journal
and endpoint/name reads, before final ancestor guards and poison clearing. Approved
independent re-review passes fifteen methods and five supplementary final mutations;
the ninety-four-case neighborhood passes without skips. The [publication evidence](../../verification/retained-layout-control-publication-development.json)
binds exact source, unchanged helpers and point-in-time/native proof limits. It
does not qualify the full transaction, recovery, native Windows or installed flows.

## Acquiring staged reservations (source reviewed)

Join the known-node publisher to the actual descriptor-backed reservation owner.
Preflight typed target occupancy, parent ancestry, one filesystem and finite
publication/journal budgets before any public effect. Publish missing parents and
marker tokens through durable intents; reopen without creation and prove exact
native nodes and bytes before acquiring advisory locks. Existing advisory files
remain unchanged; retained tokens and nonadvisory occupancy refuse. Keep original
parent descriptors and context/process custody through use. Partial and completed
sets retain controls on exit while attempting every acquired descriptor close; a later
explicitly journaled release/recovery owner must classify those real nodes anew.
Target records still do not prove project/conversion/Git/control roles, source
movement, qualification or recovery authority. Compose those actual owners before
enabling public apply, and retain every L2/L4-L6 acceptance obligation.

Thirteen actual macOS methods pass, including real canonical lifecycle mutex and
Git index writer exclusion, partial acquisition, existing advisory preservation,
same-byte/ancestry conflicts, process lifetime and release faults. Independent review
finds that final marker reads can admit a changed private stage namespace or journal
after their earlier validation, including allowing acquisition to yield an active
owner. Two maintained controls fail the exact original bytes. The repaired fifteen
methods pass: repeat real dependency currentness after marker reads, then close
native markers, private namespace, journal metadata and held ancestry without an
unchecked new payload traversal. Independent owner re-review reproduces both
original failures and passes all fifteen methods and six supplementary closing
controls. Its scope does not cover a later-discovered journal lifetime defect.

The staged-owner repair is independently approved within its exact source scope,
but composition testing finds a separate journal lifetime defect: a forked child's
inherited context cleanup explicitly unlocks the shared open-file description,
allowing a competing writer while the parent still reports currentness. Two new
controls reproduce this against the journal's exact original bytes. Capture the
acquiring PID; inherited cleanup closes its descriptor copy without unlocking the
parent's mutex. Both normal and exceptional child cleanup must keep recovery
contenders blocked until the parent exits. Approved composition re-review reproduces
both original fork failures, passes all thirty-two journal/owner methods and three
additional native cleanup/ancestry controls. The hundred-and-eleven-case selected
neighborhood passes without skips. The [staged-owner evidence](../../verification/retained-layout-staged-reservations-development.json)
binds exact source, both causal repairs and native proof limits. Complete logical
role derivation, source effects, journaled finalization/recovery and all remaining
platform, installed and feature acceptance are still required.

## Actual project and Git control roles (source reviewed)

Derive the canonical lifecycle, manifest and conversion writer roles from a real
loaded project whose typed conversion state still declares original-source
authority. Discover Git through its actual registered worktree and administration,
including no repository, unborn HEAD, absent index, linked worktrees and a project
inside a containing repository. Bind physical discovery/ancestry and exact critical
HEAD/ref/index/config inputs; malformed candidates refuse rather than becoming
ownership from a spelling or generic Git error. Acquire the derived targets through
the staged descriptor owner and revalidate actual roles while held. Distinguish
fixed repository anchors from protected administrative entries. Role ownership is
not original-source custody, selected-wrapper authority, host execution permission,
or movement/recovery/qualification; those remain the transaction owner's required
join before public apply is enabled.

The initial fifteen methods and hundred-and-twenty-six-case neighborhood pass.
Independent native probing identifies an include-target gap: Git's origin listing
omits existing empty and missing included files, so real `git config --file`
writers can change them while the lease is held. Later refusal does not establish
writer exclusion. Five actual writer controls fail the reviewed source. Ask native
Git for declared, natively expanded include paths and their declaring origins;
bind exact file presence/absence and parent ancestry before deriving writer locks.
Reserve inactive conditional targets conservatively as writer coordinates, never
source ownership/exclusion. Missing or redirected parents refuse before effects.

A further causal control proves lexical `..` normalization can hide a traversed
symbolic ancestor and mint the wrong file's writer role. Validate and retain each
canceled prefix's original physical lineage before normalizing; ordinary safe
parent-relative includes remain supported. All twenty-two maintained methods pass,
including the original three closing regressions, five native include-writer
regressions, redirected-parent refusal and ordinary parent-relative resolution.
Approved independent re-review reproduces all five original writer failures and
the intermediate redirect failure, then passes twenty-two methods and three
supplementary actual ancestry/absence/preeffect controls. The hundred-and-thirty-three-case
affected neighborhood passes without skips. The [control-role evidence](../../verification/retained-layout-control-roles-development.json)
binds exact source and preserved historical subjects. Full source custody, journaled
effects/finalization/recovery and L2/L4-L6 acceptance remain open.

## Joined source-effect owner (source reviewed; transaction unfinished)

The internal nonroot directory phase now uses the actual project/Git descriptor
owner directly. It loads the selected structural layout and actual retained-harness
Component, typed initialization origin/baseline, current affected authored files
and optional Component lock. Capture the entire original source with no exclusions,
including internal aliases, complete hardlink groups, native facts and original
ancestry. Exact acknowledgement and host-execution authorization bind a private
journal to this prepared phase. Before any source move, persist the complete
prepared plan and raw old/prospective layout, lift-and-shift and wrapper bytes,
then durable exact native intent. Revalidate actual controls and every original
input after those writes; move exclusively, synchronize both parents and recapture
original bytes/topology/native custody at the destination.

This phase reports `source-moved-metadata-pending`; normal context exit refuses
rather than report completed relocation. Old metadata, locks and receipts remain
unchanged, and every partial or moved endpoint/control remains for the unfinished
metadata/finalization and explicitly acknowledged recovery owner. Its source-only
plan is not the eventual complete public relocation plan. Root/shared-prefix source
partitions, selected wrapper changes, coherent authored publication, normal control
finalization, fresh recovery and all L2/L4-L6 acceptance remain mandatory. Public
apply stays guarded. Private framework state is caller-selected and may be inside
the project, but its actual nodes must remain outside the retained source being moved.

The initial sixteen maintained methods pass, including real source movement,
executable modes, internal file/directory aliases, complete hardlinks, actual Git
writer exclusion and unchanged index bytes, fork/context lifetime, stale source,
foreign destinations and post-effect interruption/namespace retention. Independent
review identifies three gaps: replaced plan fields can cause an external or
unrelated source move or bind arbitrary prospective authority; a case-variant
physical staging alias can enter source before source intent; and prior logical
layout lineage includes checkout-specific native facts. Five maintained causal
controls fail the exact reviewed bytes. The repair rederives source/destination and
prospective roles from current actual inputs, checks physical stage and journal
descriptors against the full source directory census, and separates portable old
layout content from local physical custody. All twenty-one maintained methods pass
on macOS without skips at this intermediate scope. The second review below
identifies remaining physical/closing defects. This is development source evidence,
not complete transition or platform/installed/feature/release acceptance.

A second review finds that post-move recapture can bind a replaced higher
parent while preserving the destination's direct parent/root/file inodes; original
ancestry must close after the observed record and later logical reads. Physical
Git administration and same-source directory aliases also bypass lexical overlap
checks on case-insensitive filesystems. Three additional maintained controls fail
the intermediate repair. Compare original full source/destination lineages and
source directories with actual registered Git/common-admin node identities;
reject a destination whose ancestry contains the original source root. Hold
original source/destination parent descriptors and ancestry through movement,
actual descriptor synchronization and final closure. Both original parent
lineages must still match before returning metadata-pending. All twenty-four
maintained methods pass on macOS without skips. These repairs do not complete
any missing root, metadata, finalization, recovery or acceptance phase.

Final independent review reproduces all three intermediate failures and passes
all twenty-four maintained methods plus four actual descriptor-lifetime/failure
controls. Original parent descriptors remain valid at native movement and observed
append, close before return/on synchronization or observation failure, and close
partial setup without moving source. The hundred-and-fifty-seven-case affected
neighborhood passes without skips. The [source-phase record](../../verification/retained-layout-source-phase-development.json)
binds all eighteen exact source/test/helper subjects and both preserved negative
reviews. This approves only the unfinished internal nonroot source phase. Next
complete coherent metadata publication, normal journaled finalization and fresh
acknowledged recovery in this same owner, retaining every root/shared/custom and
L2/L4-L6 native/installed/full-feature obligation.

## Metadata publication in the same live owner (source reviewed; transaction unfinished)

The acknowledged source owner now stages the exact prospective wrapper,
lift-and-shift and layout files in a caller-selected empty private directory under
actual descriptor/ancestry custody. The directory may be in project framework
state; actual source, stage-pool, journal and registered Git administration identities
remain forbidden through all physical aliases. Check finite remaining journal
resources and original single-link owned metadata before staging. Keep original
metadata modes and group on replacements. Every public effect follows a durable
intent binding actual known source/destination/parent nodes and payload identity.
Quarantine exact old nodes, preserve them in private state, and publish prospective
nodes exclusively through held original parents and descriptor synchronization.

Only actual observed effects advance the current authored-input map. Every step
revalidates the live canonical project/Git descriptors, complete original moved
source, exact current metadata, original parent ancestry and complete private
namespace. The final declaration resolves a structurally current, explicitly
unqualified layout. Return `metadata-published-finalization-pending`, with
`qualified: false` and `relocation_complete: false`; normal context exit still
refuses incomplete state. Old metadata nodes and receipts are retained; no normal
control finalization, fresh recovery or public success is implemented by this step.

Seventeen metadata methods and twenty-four existing source methods initially pass;
the hundred-and-seventy-four-case neighborhood passes without skips. Independent
review reproduces publication adopting a same-byte foreign inode between native
sampling and content observation, and a quarantine hole adopting a foreign optional
read. It also reopens verified-retired descriptor slots and uses a cached private
metadata writer to create a node after its owning phase ends. Three maintained
causal controls produce two failures and one closed-descriptor error against those
exact source bytes. Bind the observed signature and final full native facts to the
known moved node, record explicit quarantine absence, bind private currentness to
the live phase and invalidate that phase before descriptor teardown. Twenty metadata
and twenty-four source methods pass after repair. Approved independent re-review
reproduces the two failures and closed-descriptor error against exact original
bytes, then passes all forty-four methods and eight unique supplementary controls.
Actual original descriptors reopened into retired slots cannot revive checks or
writes; phase invalidation precedes teardown. Post-read native replacement and
hardlink changes, final public/private/journal drift and actual child writes also
refuse while retaining all observed nodes. One supplementary journal fixture first
caught only the inner refusal while the outer owner correctly refused again; only
that assertion scope was corrected and that one case rerun. The hundred-and-seventy-seven-case
neighborhood passes without skips. The [metadata record](../../verification/retained-layout-metadata-publication-development.json)
binds all nineteen source/test/helper subjects and the preserved initial report.
Next complete normal journaled control finalization/release and fresh acknowledged
recovery in this same actual owner. All root/shared/nested/wrapper placement and
L2/L4-L6 native/installed/full-feature acceptance remain required.


## Normal control finalization (source reviewed; recovery unfinished)

Derive one exact nonadvisory `litai/layout.pending` control from the loaded project
and acquire it with the same real staged descriptor owner as the canonical
project/Git controls. Read-only preparation binds its path and absence; a pending
or foreign occupant refuses a new transaction. Only the live actual descriptor
can satisfy that control during the current source phase. This grants no ownership
of `litai/` or any shared ancestor. Source may not swallow actual canonical control
or framework metadata roles, including physical/case aliases; the complete mixed
partition owner remains required for those layouts.

After real source and metadata publication, persist a bounded finalization intent
and reclose all current outputs before releasing controls. Normalize only newly
created advisory files to a NUL placeholder on their original held descriptor and
inode; preserve prior advisory contents. Hold their actual OS mutexes until the
outer context exits. Quarantine exact native Git controls without deletion or
replacement, synchronizing held original parents. Retire the actual pending
control last. Before any normalization, both the source finalizer and actual
reservation owner compare retirement state with the held control/parent, pool and
journal devices. A projected foreign device refuses with every token unchanged;
this controlled fixture does not establish actual mounted cross-volume acceptance.
Interrupted pre-commit writes or moves retain every node and pending state for
explicit fresh recovery, rather than treating a shortened token as a new lease.

After normalizing advisories and retiring non-pending native controls, reclose the
actual source, authored metadata and private/control state. Durably append
`layout-commit-observed` before retiring pending: this is the irreversible logical
commit decision for the already published, explicitly unqualified layout. Pending
retirement and the final observation record complete control handoff; they do not
undo that decision. No exception triggers automatic source or metadata rollback.
Ordinary errors after a returned commit append raise `LayoutCommitOutcomeError`
with `committed=true`, `qualified=false`, and their original cause, even if pending
is already absent. Errors during the commit append report `committed=null` (outcome
unknown), retaining pending for fresh inspection of actual durable records. An
append may have published its decision before failing; its exception alone proves
neither commitment nor absence. Preserve interrupts as interrupts with an outcome
note. The same classification covers output conflicts and owned context-release
errors after commit. A saved outcome grants no descriptor or recovery authority.

Actual retired descriptor/name/native/byte facts and a complete private retirement
namespace replace old public-marker locations in the same reservation owner. Old
role claims stop once finalization begins. Native Git writers can resume after
handoff; their later index/ref changes are not falsely frozen as transaction input.
Source and authored outputs remain checked, old metadata backups remain intact,
and the internal result is `committed-unqualified`. Normal context completion
requires every actual control disposition; no saved complete flag grants ownership,
qualification or recovery. Public apply and fresh recovery remain unfinished.

Eight initial native methods pass. An expanded ninety-two-case regression run
passes ninety-one methods and finds one fixture whose declared source disagrees
with its old harness wrapper before reaching the intended metadata-role refusal.
Correct only that fixture alignment. An earlier eighty-one-case run also reported
one conservative native `layout.move.entry-changed` during control preparation;
the exact method passes its direct recheck and in the later run. Preserve those
observations separately from passing scope. Complete independent review, maintained
finalization and the full affected neighborhood before admitting this source.

Independent initial review requests a same-filesystem preflight in both the source
finalizer and actual reservation owner. Its controlled retirement-device projection
reaches real advisory normalization before EXDEV at the initial bytes. Both layers
now check devices before control changes, with separate maintained causal tests.
A native late-journal failure also occurs after pending has retired at those bytes;
the durable decision and explicit post-commit/unknown error outcomes above address
that ambiguity. Initial review and prior evidence remain immutable; exact repaired
source review is approved at the limited normal nonroot POSIX scope. All nineteen
repaired finalizer methods pass independently, with three supplementary native
release/interrupt controls. All nineteen author methods also pass;
the affected scope passes one hundred ninety-six methods with no skips (one
hundred seventy-six critical-module methods plus twenty generic reservation
methods). Running the seven new causal methods against frozen initial source
produces seven failures and one error across eight subcases. This is scoped macOS source
evidence, not full source or installed/native-platform acceptance.

The approved [finalization record](../../verification/retained-layout-control-finalization-development.json)
binds exact reviewed source/test/helper subjects and preserves initial-review
identity. It does not extend historic source or artifact qualification. Next
complete fresh acknowledged recovery with actual new descriptor ownership and
current endpoint classification, including unknown or committed-but-incomplete
outcomes; preserve all ambiguous nodes and original receipts. Public guards and
all broader layout, lifecycle renewal and platform/installed acceptance stay open.

## Fresh recovery descriptor ownership (source reviewed; transaction recovery unfinished)

Full recovery must restore exact original bytes/custody or report precise retained
unresolved state, and must reconcile committed/unknown decisions without automatic
rollback. Start with acknowledged fresh descriptor acquisition for the completed
original reservation set. Read the actual reopened, validated bounded journal;
match the complete target coordinates/anchors to original acquisition identity,
then freshly observe every named inode, bounded raw token, recorded anchor and
current full physical ancestry. Original source custody remains the full
transaction recovery owner's separate obligation.
Classify observed native retirement (including a move whose observed event was
interrupted) using both actual endpoints and the recorded original inode. Treat
only original bytes, the first-byte-NUL intermediate, and exact NUL as supported
in-place normalization states when a matching durable intent exists. Bind actual
current native facts and bytes in the new proposal. Foreign same-byte inodes,
unknown bytes, missing/both endpoints, private insertions or redirected ancestry
refuse without changing controls. Existing foreign public occupants after an old
marker retired are descriptive facts and never owned by that old marker.

Application requires the exact fresh proposal and current execution authority
before private recovery intent or advisory mutex acquisition. Open only existing
no-follow nodes; no cache-lock initializer, token rewrite, unlink or implicit new
marker creation is permitted. Journal acquisition before yielding, recheck exact
named/descriptor/byte/ancestry/private/journal facts and retire every FD on normal,
failed or interrupted exit. Inherited or expired owners cannot grant ownership.
The recovered descriptor set owns only its actual present named nodes; a private
retired token does not satisfy its former public canonical control.

The complete transaction recovery owner must next derive current project/Git roles
under those actual descriptors, acquire any missing canonical controls through the
known staged publisher, classify all source/metadata endpoints and implement
journaled exact recovery effects. Incomplete original acquisitions and unsupported
frontiers must remain explicit incomplete results, with all observed state retained.
No source/metadata effect, cleanup, qualification or public recovery is implemented
by descriptor reacquisition alone. Native crash, concurrent-owner, stale/forged
proposal, interrupted normalization/retirement, replacement/foreign namespace and
PID/context/descriptor-release controls are required before source admission.

The first eighteen descriptor methods pass seventeen and expose an incorrect test
assumption about close order; the shared owner correctly closes in reverse order.
Correct the test to inject on the first actual close and prove every remaining
attempt. Native ASCII and expanding Unicode aliases on this host address the same
inode, so keep their fixture refusals separate from actual distinct-alias proof.
A labeled projected namespace control checks the closing portable-name guard;
its first fixture selected the wrong parent and was corrected to the real mutex
parent. An actual empty-retirement-root replacement also crosses the initial
implementation, and setup failure can leak its just-opened unregistered FD. Pin
empty retirement ancestry, close portable names after blocking writes and explicitly
close/retire setup FDs before rethrowing. Three current causal controls fail the
preserved initial source; twenty-five repaired methods pass without skips,
including real SIGKILL of the prior journal/control owner and real completed and
metadata-interrupted transaction composition. Independent source review and the
full affected neighborhood remain pending before admission.

Initial independent review passes all twenty-five maintained methods but reproduces
three actual closing counterexamples: a foreign journal node, a foreign private
stage node and mutation of a known staged file during the last marker observation
all cross the lease yield and refuse only on context exit. Three maintained native
regressions fail those exact bytes. Close actual journal membership/native facts
and private producer membership/native facts after all final marker/native/name
observations; then close exact retirement membership and current physical ancestry
without further payload reads. All twenty-eight methods pass after repair. The
initial two-hundred-twenty-one-case neighborhood passes at earlier source bytes;
retain it as historical, with repaired neighborhood and exact rereview pending.

Exact repaired descriptor source is independently approved at the limited generic
POSIX scope. All twenty-eight maintained methods and four supplementary controls
pass: late retirement insertion/root replacement refuse after dependency closure,
setup interrupt and actual-close errors remain visible together, and expired
operations refuse before any native FD access. The [descriptor record](../../verification/retained-layout-recovery-controls-development.json)
binds exact code/test/helper subjects, both causal source lineages and immutable
review identities. All two hundred twenty-four affected methods pass without skips.
Next compose actual canonical project/Git role binding, missing control publication
and exact current
source/metadata endpoint recovery; all full-program acceptance remains open.

## Canonical recovery roles and absent controls (source reviewed; endpoint recovery unfinished)

Compose actual recovered descriptor sets, not saved role labels. Re-derive project
and original-source conversion authority from the actual loaded project and Git
roles from actual registered administration/current critical inputs. The canonical
project controls must already correspond to recorded/recovered project targets;
do not use a different root to mint unrelated project controls. Current canonical
advisory mutexes must be held exactly once. A retired private token does not own
its old public coordinate; foreign live controls refuse. Newly required native
coordinates must be absent and finite before any publication.

Under those actual descriptors, prepare a fresh proposal binding current roles,
Git inputs, old recovery sets, missing targets and current immutable journal.
Require its exact acknowledgement and execution authority. Publish absent controls
using the existing staged known-node owner with durable native intents, then verify
its actual FDs and every recovered old endpoint. Only that actual separate owner
may take an old released public observation; the original raw owner continues to
own its retained private inode and never gains a public claim by relabeling.
Revoke combined canonical role rights before any constituent FD can close.

Select a complete reservation generation explicitly when needed. Associate its
normalization/retirement history with that generation's original native nodes,
retaining all other groups and all immutable history. Subsequent interrupted
native-control reacquisition can be reopened as another actual descriptor set;
ambiguous or incomplete groups report retained unresolved state. Do not infer
ownership from a group ID, completion flag or recorded successful handoff.

Prove actual Git exclusion/re-entry, released native control reacquisition, foreign
and stale/forged proposal refusal, multiple generation reopening, interruption and
late closing changes under native FD/PID/context checks. Complete independent
review and affected checks. Current source/metadata endpoint classification and
journaled recovery effects, root/mixed layouts, public recovery and all broader
acceptance remain required afterward.

Initial independent review confirms two further construction/closing defects even
though all twenty-three role and twenty-eight generic methods pass. Same-byte
actual manifest and Git HEAD replacements after the last seed read cross role
yield: project drift can escape entirely and HEAD drift refuses only on exit.
A directly constructed private role lease can also validate while the required
pending descriptor is absent, without field edits. This is an internal
construction invariant defect, not an external process security boundary or data
recovery effect. Preserve initial bytes and report. Share the established normal
role owner's post-read native validation, then close aggregate dependencies;
factory-guard construction and independently require actual canonical target/type
coverage in each lease validation. Add native manifest/HEAD and constructor/coverage
controls before exact source rereview and admission.

All three new maintained regressions fail the exact initially reviewed role source
(two actual final-read replacements and unkeyed construction). Share the existing
normal role owner’s complete post-read project/Git native validation, then close
the aggregate descriptor dependencies. Construction now requires its acquisition
factory, and every role validation independently requires actual canonical
target/type coverage; even the actual internal key cannot validate absent pending.
Normal finalization refuses because recovery effects need their separate owner.
All twenty-seven repaired methods pass without skips. The initial
247-method affected result belongs to earlier reviewed bytes, not this repair;
exact rereview and the repaired affected scope remain pending.

The repaired 251-method neighborhood passes, and exact rereview approves the
construction/closing repairs. A later author native probe identifies a separate
live-binding defect: replacing the public Git observation with a real non-Git
observation can waive the acknowledged project's changed HEAD while actual
control FDs remain held. This changes the selected input view without a new
acknowledgement; it is not a data-recovery or external privilege claim. Bind the
lease's public Git and reservation references to its actual construction inputs
before shared native validation. Preserve the earlier approval as historical and
require the new native regression plus exact narrow rereview before admission.

An entry-only reference check passes its focused controls but independent review
reproduces public Git reassignment during the second actual shared project read,
waiving the later Git native close. A maintained native regression fails exact
entry-check source. Store construction references before normal role initialization
and expose Git/catalog references with immutable setters (same-object constructor
assignment only). The normal validation path then consistently uses the original
actual references throughout current/initial checking. Both native reassignment
controls and an ordinary complete project-role path pass; final targeted rereview
and the final affected scope remain pending. Preserve the earlier 252-method result
at entry-check bytes; it does not qualify immutable-binding source.

Immutable-reference source is independently approved at the internal canonical
POSIX role scope. Five exact targeted maintained methods and two supplementary
native controls pass, including catching a setter refusal inside the final input
read and still proving the actual original Git close rejects the changed HEAD.
The [canonical-role record](../../verification/retained-layout-recovery-roles-development.json)
preserves all source/review lineages and binds current helper/test subjects. The
final affected scope passes all 253 methods without skips, including twenty-nine
current canonical role methods. Next classify current source and metadata
endpoints under this actual owner and implement exact journaled recovery; no
public, platform, receipt/admission or full-feature acceptance follows here.

## Actual source/metadata recovery effects (source reviewed; control disposition unfinished)

Validate the original canonical source-plan payload against the reopened journal
binding and actual current project, initialization and selected wrapper authority.
Independently capture the complete source at either recorded endpoint with no
exclusions, including internal aliases and complete hardlinks. Re-derive the
original/prospective metadata relationship from raw before payloads; a saved phase,
completion record or descriptive path is never sufficient ownership.

Freshly classify actual public and private metadata native nodes against durable
original/recovery move intents and observed facts. Distinct same-byte inodes,
changed content/topology/ancestry, ambiguous/missing original nodes and unknown
current public data report retained unresolved state. Unpublished private stages
lack native publication provenance: preserve and describe them without adopting,
renaming or collecting them. Original metadata backups must be the exact original
nodes with exact bytes. Bind current full observations, private namespaces, parent
identities, role owner and current journal in the new recovery proposal.

Before each effect require exact current acknowledgement/execution authority,
finite journal and same-filesystem private state. Persist an exact native intent,
then exclusively quarantine a still-owned prospective public file or restore its
still-owned original backup; synchronize the held original parents and close over
all inputs. Restore the complete source directory only after original metadata is
coherent. Preserve every quarantined prospective/staged/foreign node and all old
receipts. Fresh recovery must recognize its own interrupted moves from actual
endpoints and revalidate original source custody, not resume a saved writer.

A durable committed decision preserves the proposed layout and refuses rollback;
verify actual source and published metadata instead. Pre-commit restoration and
committed verification remain explicitly unqualified and control-disposition
pending. Full control release, incomplete/unsupported frontiers, mixed/root/shared
layouts and all public/installed/native/release acceptance remain required.

Initial independent native counterexamples reveal that late private-data
observations can invalidate journal or actual Git inputs before a real rollback
effect. Five maintained causal methods also cover private control staging,
pending markers and same-byte project-manifest replacement; all fail the frozen
initial source. Close captured Git/project native facts and aggregate actual
descriptor/journal/private-producer dependencies after the final data namespace
observations. Independent rereview approves the exact repaired source; all
twenty-eight data methods pass independently, and a real post-move parent-sync
failure closes all temporary descriptors and permits a fresh verified retry. All
two hundred eighty-one affected methods pass without skips. The
[data-recovery evidence](../../verification/retained-layout-data-recovery-development.json)
retains exact source/review identities and causal results; full recovery remains open.

Next, the recovery disposition owner must consume freshly verified actual data
under the still-live canonical owner, rather than accept the returned data result
as authority. Carry the original and supplemental real descriptor owners through
one explicit handoff; revoke ordinary canonical/data writers before controlled
marker mutation. Keep one held descriptor per advisory mutex, normalize only
exact owned tokens through those descriptors and preserve already retired private
nodes. Journal each exact native disposition before moving its still-owned public
marker, retain and synchronize the actual parents, and release the pending barrier
last after a durable restored-or-committed decision. Refresh only facts resulting
from verified owned effects, not arbitrary current observations. Reopening every
interruption must classify actual native endpoints and partial advisory bytes
without reviving an old writer. The original locks must outlive handoff, with
honest post-decision failure outcomes and no receipt renewal. Public recovery and
fresh ordinary project reentry require their own maintained acceptance afterward.

## Recovery control disposition (source reviewed; internal nonroot scope verified)

Require a fresh closed data plan with no remaining data actions or unresolved
inputs. Bind its identity, actual complete original/supplemental descriptor
inventory, original acquisition generations, preserved private retirement areas,
public observations and one new empty private retirement root. Preflight bounded
journal resources and actual same-filesystem parents before handoff. Ordinary
canonical writers expire after the durable disposition intent; their descriptor
contexts retain their actual FDs and provide only typed read-only currentness
checks against the separate effect owner until teardown.

Preserve unrelated existing advisory bytes. Normalize only an original acquired
reservation token or its validated interrupted normalization through the same held
FD; synchronize it and require exact native/byte observations before recording
success. Retire only currently public native markers, exclusively into the known
new private root, preserving previously retired private nodes and complete shared
retirement namespaces. The pending marker is last, after a durable restored or
committed recovery decision. Attempted decision writes and failures after that
decision must retain their precise outcome and original cause; interrupts remain
interrupts. The effect writer expires before any descriptor can close, while
read-only teardown checks remain bound to each original live descriptor context.

Fresh raw recovery joins the original acquisition generation with exact recovery
normalization/retirement intents and observed nodes, complete actual private
namespaces and held parent identities. A same-byte foreign inode, unknown private
entry or changed ancestry remains unresolved. Historical records alone grant no
canonical role, descriptor ownership or deletion. After full descriptor teardown,
fresh ordinary planning and a new real source/metadata/control transaction must
be possible without removing retained evidence. These internal nonroot behaviors
are independently reviewed and pass the complete affected local source scope. Public recover,
root/shared/mixed placement, genuine admission, installed/native platforms and
full-program release acceptance remain open.

The closing pass observes all complete source, control, private retirement and
journal/staging namespaces before its final known-fact checks. Capture coherent
directory stamps around those observations, then close the original known source,
metadata, held/named markers, private entries, directory stamps and producer file
facts without enumerating directories or reading payloads again. Final Git
owned-lock queries use a frozen view of actual descriptor facts, not another full
catalog traversal. Directory stamps detect later membership changes while known
file facts detect payload replacement. The source native pass uses the original
capture's `lstat` representation, preserving valid symbolic links as well as their
independently validated targets and hardlink topology.

Native predecessor cases reproduce late advisory, canonical Git, cold raw
descriptor, source and producer-read consistency gaps, plus loss of the durable
decision on actual descriptor-close errors. Preserve every exact predecessor and
review record; no earlier passing subset establishes the final composition. The
final independent review approves the exact production and test subjects. All
307 methods in nineteen affected modules pass without skips in 754.322 seconds,
including all 26 disposition methods. The [development evidence](../../verification/retained-layout-recovery-disposition-development.json)
binds those source identities, review lineage, causal failures and final log
identity. The configured full-source receipt remains stale; these checks do not
renew it or establish installed, cross-platform or release acceptance.

The internal caller still owns the outer journal and staging-pool lifetimes.
Control disposition verifies those live producers and classifies the original
control stacks through directory teardown. It does not declare completion of a
public recovery command spanning every caller-owned producer context; that
front door and its complete error/reentry boundary remain required acceptance.

## Structural renewal after relocation (in progress)

The actual internal nonroot transaction invalidates admission by publishing a
`requalification-required` lift-and-shift record. Ordinary readmission must
locate that structurally current implementation and selected wrapper even while
historical evidence is unqualified. Bind the declaration and current lineage in
its fresh acknowledged plan. Complete real direct baseline and wrapper parity,
regenerate the selected current Component lock, and publish a current readmission
binding to those exact fresh documents and the unchanged declaration. Retain the
prior lift-and-shift evidence in readmission history. Read-only lookup, schema
migration and source-scope refresh cannot promote admission. Old receipts stay
invalid; qualified readers must resolve the selected wrapper and require fresh
current admission. Changes to layout or pending relocation state before or during
execution refuse publication. Initial/root/shared placement and their full source
partition owners remain separate unfinished requirements.

The first actual-move regression fails the committed readmission predecessor at
its obsolete `lift_shift_unqualified` check. Structural renewal then passes the
initial thirteen-method neighborhood, but a maintained late-read control inserts
a real pending marker after the helper's final declaration read without refusal.
Independent execution also observes a returned plan and an applied result across
late pending insertions. These are failing development observations, not qualified
renewal. Close all remaining historical input reads before the final layout and
pending checks, then rerun the maintained and independent cases before approval.

The repaired closing helper captures original known layout/conversion file facts
and ancestry before reading inputs. It compares current layout and historical
bytes, observes pending absence after those payload reads, then closes the
original native facts without further payload reads. Apply performs its final
helper check after its historical reads. Both maintained late-pending methods
fail the exact intermediate source; all fifteen current affected methods pass
without skips, including nine actual-layout renewal controls. Independent
re-review approves the exact changed source and tests, passes all nine maintained
renewal methods and two additional native replacement controls, and reproduces
both causal failures on the preserved intermediate source. The [development
evidence](../../verification/retained-layout-structural-renewal-development.json)
binds the source subjects, immutable report identities and final fifteen-method
run. Qualified admission and the other L2 consumers remain
unfinished, and the configured full-source receipt is still stale.

## Qualified receipt and Cargo consumption (in progress)

Consume the exact current declaration through the qualified reader after requiring
matching baseline/parity layout-readmission bindings. Validate their schema,
complete passing phase coverage and executed source observations, current inventory,
wrapper bytes and original lift lineage. Retain the original lift record rather
than changing its historical state. Bind the declaration into retained admission
identity, so a prior finalized receipt cannot qualify the relocated authority.
Require a genuinely current selected wrapper Component lock and refuse root
admission until its complete partition owner exists.

Resolve source and wrapper roles from actual current structural inputs only after
that qualification check. Capture original layout/lineage native facts and ancestry,
reject pending relocation, and close the known inputs after reading them. Retained
execution still independently captures and qualifies its actual current source;
the readmission source identity describes the earlier executed baseline. Cargo's
operation-local context pins the declaration and selects the current wrapper from
its actual current Component lock/catalog bindings. A custom wrapper fixture is
independently authored and genuinely locked/readmitted; it does not establish
public wrapper movement or initial-placement acceptance.

Maintain actual nonroot move, genuine readmission, finalized receipt production
and promotion, old-candidate refusal, selected Cargo context and live declaration
change controls. Malformed, missing, mismatched or failed evidence and pending
transactions must refuse before producing positive outputs. Complete the other
renewal/discovery consumers and full partition/placement/platform qualification
before closing ADOPT-RELOCATE-001.

Initial qualified-reader review finds two causal gaps despite the first local
sixty-four-method pass. Missing direct phase source observations can still produce
and promote a receipt, and Cargo currentness can return across pending insertion
at its final actual lock read, before a later context exit refuses. Three maintained
native regressions fail that source. Require each direct phase's source to equal
its original executed baseline and each parity baseline-source reference to match
its corresponding direct phase. Close pending state and original known project,
review and selected-lock native inputs after every Cargo payload/catalog read.
Keep source-currentness checks and actual receiving/scratch custody separate.

The next review resolves those two findings but reproduces a distinct physical
root gap: replacing the implementation directory during Cargo's final lock read
still lets currentness return. Its last bound implementation/workspace identity
checks precede that read. Include both actual bound directory nodes and their
ancestry in the same original native closing set. The maintained directory
replacement control fails the preserved intermediate source; original nodes and
all changed source remain intact for the caller.

Finalized candidate files are historical observations whose promotion must still
check current authority. The existing output span can retain a candidate after
pending insertion following its last currentness guard. A separate actual
promotion control refuses such pending authority; this step makes no continuous
multi-file snapshot or pending-promotion bypass claim.

The final Cargo closing inventory must include the complete actual selected-lock
pinned input set, including workflow/specification/Flavor content, rather than a
hand-maintained subset of metadata names. Expose only the existing bounded pinned
leaf paths as a read-only inspection seam; these paths confer no ownership,
exclusion, execution or write permission. Continue validating the same actual
closures, then close their original known native facts after every payload read.

Complete selected-lock pin coverage still leaves the separately declared retained
source authority outside the closing set. A maintained actual app-file mutation
at the final lock read fails that intermediate source, independently confirmed.
Bind the exact validated harness source-scope paths and current project
onboarding/documentation/skill inputs into the same known native closing pass.
They describe the authority actually observed; they grant no source exclusions or
complete receiving namespace custody. Validate current project authority after
catalog/lock reads, then close original known source and metadata facts without
further payload reads. Keep the existing source-scope semantics; actual receiving
still proves its complete namespace and scratch ownership separately.

The final source review approves the exact declared-source admission composition.
All fourteen maintained admission methods pass independently, with native
metadata replacement/expiry controls and mutation checks across fifty-three
actual onboarding/document/forward-skill leaves after final project validation.
The fixture contains no inverse-skill leaves; no native inverse mutation result
is claimed. Existing source-policy semantics stay intact, and actual receiving
still proves complete namespace and scratch custody separately. The [development
evidence](../../verification/retained-layout-qualified-admission-development.json)
retains exact subjects, causal failures, immutable review identities and the final
affected source run. Full L2 and placement/platform/program acceptance remain open.

The complete final nine-module affected scope passes all seventy methods without
skips in 303.377 seconds, including all fourteen maintained admission methods.
Driver/runner review, lint/format, repository layout, public export and project
validation pass. All-gates verification passes authority and honestly fails the
configured stale full-source receipt; this scoped evidence does not renew it.


## Structural source-scope refresh and schema migration (in progress)

Source-scope refresh must work at the actual declared nonroot implementation
before readmission is earned. A read-only renewal observation binds original
lift/declaration/wrapper inputs, current source and wrapper coordinates, and
native ancestry. It grants no execution, namespace ownership or write rights.
Refresh retains its existing exact plan acknowledgement and lifecycle lock,
preserves historical baseline/parity/lift evidence, and makes prior receipts
stale. Genuine readmission is still required before retained receipt execution.

Schema migration uses the same actual structural location to reconstruct a
missing source scope. It never updates fresh report bindings or supplies passed
execution evidence. Existing independent parity-only schema migration remains
supported when lift/layout evidence is absent. Pending layout state prevents
publication, including dependent receipt-policy and authority-review updates.

Initial independent review reproduced four counterexamples despite eleven
passing maintained tests: late pending insertion during parity or inventory
migration, a foreign inventory edit overwritten after its original parse, and
refresh returning success after a source edit during its final layout read.
Repairs parse the exact originally observed bytes, compare original native input
facts after layout payload reads, and check pending absence last before metadata
publication. Refresh retains known source member and visited-directory facts
through its final payload reads, then closes source and metadata native facts
before success. Ordinary rollback remains limited to bytes the operation wrote;
foreign edits and pending state are preserved. This is a bounded closing check,
not a continuous filesystem snapshot or complete transaction recovery proof.

A second review confirmed those repairs but reproduced pending insertion inside
the nested manifest and review helpers, after the outer guard. Forward optional
currentness checks into the actual atomic write owners, after private temporary
output is flushed and immediately before replacement. Close the original
destination native facts after the check so its own reads cannot overwrite an
intervening manifest or review-document edit. Existing callers retain their
default behavior; these checks grant no review or mutation authority.

Maintained regressions exercise actual relocated source, refresh followed by
genuine readmission and receipt execution, schema-only compatibility, changed
layout, nested policy/review pending publication barriers and preservation of
intervening edits.
Independent review approves the exact local structural-consumer scope, all
seventeen maintained methods and two actual pending insertions during temporary
output fsync. Targets remain unchanged, pending state is preserved and private
outputs are closed and removed. The final affected suite and exact reviewed
subjects belong in [development evidence](../../verification/retained-layout-structural-consumers-development.json).
Native rewrite and monorepo discovery, complete
source partition ownership, root/shared/mixed/initial/wrapper placement, public
recovery and installed/native/full-program qualification remain open.


## Native rewrite and installed monorepo consumers (in progress)

Declared native rewrite planning must require genuine current readmission and the
selected wrapper's current lock before updating program locations. Reconcile only
recognized generated references in the existing ADR, program and ADOPT-002 item;
retain custom progress and refuse ambiguous customized location fields before any
write. Legacy initialization still prepares its original program before a wrapper
lock exists. Structural location observation never grants qualified admission.

Installed monorepo discovery resolves declared source independently of historical
installation coordinates. Layout-bound installations use a distinct version and
must match the current declaration and source coordinate. Acknowledged refresh can
use the actual structurally current source before overall readmission, but must
rerun all selected retained harnesses after a layout change and publish a fresh
layout binding. Unchanged source bytes alone cannot make a historical installation
current. Undeclared installation identities and schemas remain unchanged.

Bind original parsed/native metadata and source facts across final payload reads;
close layout, actual project/conversion and known source/output facts before
publication and success. Preserve foreign edits and pending state, keep ordinary
rollback limited to owned writes, and retain full transaction/recovery boundaries.
Independent review approves the exact local consumer source scope; final affected
checks and exact subjects are retained in development evidence. L1 complete source/metadata ownership,
L4 placement, public recovery and installed/native/full-program acceptance remain
open after these local consumers are implemented.


Initial program-consumer review reproduced two gaps despite the 149-method affected
pass: a selected workflow could change during native planning's final actual lock
read, and an installed binding could change during the check's final layout read
while success was returned. The second gap also affected initial installation.
Retain the actual selected lock/catalog context, its complete pinned leaf set and
ancestry through every later read. Retain the complete consumed installed payload
set from original observation through the final layout/source check. Initial
publication must close its known written files after validation inside rollback;
refresh must transfer original planning facts into its writer instead of sampling
intervening edits as a new baseline. Maintained regressions retain foreign edits,
restore only still-owned output bytes and require refusal before positive results.
A further review confirmed those repairs but found that original parent ancestry
was lost at the refresh writer handoff. Preserve that same original ancestry in a
separate closing callback while per-file signatures evolve under the writer. A
maintained native control substitutes a parent using preexisting hardlinks that
preserve child inode/time facts; refresh must refuse and preserve both directories.
The final independent source review approves all eighteen maintained consumer
methods, including this refusal and unchanged legacy refresh reuse. Exact subjects,
immutable review identities and the final affected run are retained in
[development evidence](../../verification/retained-layout-program-consumers-development.json).
Full namespace ownership, placement, public recovery and platform/program acceptance
remain open.
