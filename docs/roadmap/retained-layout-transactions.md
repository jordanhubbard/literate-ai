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
