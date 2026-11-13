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
