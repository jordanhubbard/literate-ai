# Explicit monorepo adoption boundaries

[ADR 0039](../decisions/0039-1.1-capability-boundaries.md) governs this design.
Build markers are candidate roots, not inferred Components or proof of independent
buildability. The default conversion remains a single retained wrapper.

`litai onboard adopt PATH --root-plan SELECTION.json` reviews an explicit
`literate-ai/monorepo-adoption-selection@1` document. `components` contains unique
portable `name` values, nonoverlapping detected `root` paths and explicit `commands`.
Every command specifies `id`, `command`, project-relative `cwd`, and a source-file
`evidence` path. Commands are operator-reviewed declarations, not qualification;
planning never executes them. Duplicate stage IDs within a Component are invalid.

A selection may contain one Component. For a single selected root, its explicit
commands replace the corresponding detected baseline phases in the reviewed plan
and actual conversion, including wrapper parity; all other detected phases remain.
The selected commands and replaced detector commands remain visible in findings.
The converter checks the quarantined bytes against the reviewed source membership
before applying the selection. This permits scoped baseline testing of one Cargo
workspace without inventing multiple roots or claiming coverage of unselected tests.
If that final source check fails after quarantine, conversion refuses and retains
the source, quarantine and partial scaffold for explicit recovery. It reports
incomplete recovery and does not clear the root namespace, preserving concurrent
files as well as changed quarantined inputs.
Existing multi-root staging and receipt behavior is unchanged.

Native commands own outputs in their original private execution workspace until
the original completion boundary closes them. Cleanup can retire a complete
hardlink group only when every link belongs to that workspace. It keeps an
original file descriptor and verifies exact bytes and metadata around its own
unlinks before accounting for the resulting peer link-count/change-time updates.
Changed bytes, redirected names or external peers cause preservation and refusal;
a saved path or failed runtime cannot issue fresh cleanup authority.

Retained planning binds its single release-policy input to the same declared
coordinate as the existing release owner. Its exact raw identity and repeated
custody checks apply at root and contained locations. Equal bytes at another path
cannot replace configured authority, and a root policy cannot shadow a contained
policy. The release owner's initialization/conversion eligibility checks remain
part of the read.

Files beneath a selected root belong to that Component. Every remaining captured
source file requires exactly one `shared_sources` assignment: `path` (a file or
directory prefix), `owner` (Component name), and explicit `consumers` (other Component
names, possibly empty). Assignments may not overlap one another or selected roots.
This is custody and declared usage, not an inferred dependency graph. Root-level
aggregate drivers do not automatically own their children's source. A command may
cite its own source or explicitly shared input, and may run at the repository root
or beneath its Component root. Cross-root invocation is not inferred.

The read-only result lists exact owned and shared input files per Component and
binds their raw bytes, executable bits, selection and commands into a content
identity. The source universe is the existing retained-source capture policy
(Git-visible tracked plus nonignored untracked files, or pruned filesystem fallback).
Uncaptured/ignored files are not silently admitted. A selection file inside that
universe is itself source and needs ownership. Symlink/reparse source paths and
separate Git histories are unsupported for refinement and refuse explicitly.

Selection, source, bundle and receipt reads bind an opened regular-file descriptor
to the observed named file before consuming bytes and recheck custody afterward.
On platforms that provide them, no-follow and nonblocking open flags prevent a
last-moment symlink or FIFO replacement from being followed or blocking the reader.
Source hashing reads at most the initial observed size plus one detection byte;
documents retain their existing size limits. Replacement, size/mode/time drift or
indirect ancestors refuse without publishing a successful observation. These checks
do not constitute a sandbox against a malicious same-user process. Only a disposable
directory created by the harness is canonicalized through host temporary-directory
aliases; operator-supplied input paths are not silently resolved around these checks.

Candidate discovery and selection review do not authorize movement. A refined plan
is applicable only when the operator also selects `--run-baseline`; this is explicit
consent to execute every declared Component harness in a disposable retained-source
copy before the first conversion mutation. Apply still requires acknowledgement and
the exact reviewed onboarding plan identity. The mutator revalidates the reviewed
identity, requires one passing retained receipt per Component, preserves the shared
source layout and original Git history, and publishes source-free Component
projections after the ordinary retained wrapper lift-and-shift.

Acceptance requires a real multi-root first-change journey with independent
Components, original commands, distinct receipt invalidation and rollback. Planner
unit tests alone cannot close #365 or qualify a 1.1 release.

## Staging and per-Component retained qualification

The internal staging adapter materializes source-free Component projections into a
new external bundle only after acknowledgement and exact plan revalidation. It does
not move source, alter the source repository, or initialize a project. Projections
start as `staged`, not at a conversion authority stage, and declare no generated
product entrypoint. The completion manifest is published last; an interrupted or
partially written bundle is not usable.
Colliding destinations refuse. Failed staging removes only files still owned by that
attempt, preserving concurrently replaced files.

Each Component has its own admitted command inventory and retained receipt policy.
Its current revision binds the Component projection, command/input declaration and
raw bytes/executable bits of owned files plus declared shared inputs. It does not
bind other Components' private source bytes or mutable receipts. Added/deleted files
in the applicable owned/shared prefixes require scope refresh; unrelated additions
do not invalidate this Component. Shared ownership and usage remain explicit.

An explicitly acknowledged local run copies only those admitted files into a fresh
disposable tree while preserving repository-relative paths. The existing strict
retained harness executes the exact commands and requires positive, all-passing test
counts with no source mutation. Evidence is component-scoped retained execution,
not native generation, independent semantic acceptance, conversion parity or a
project-wide release receipt. Source/descriptor drift during execution prevents
publication. These are same-user local execution guarantees, not host containment.

Component evidence and its typed receipt are retained together in one new external
file. Rechecking binds exact evidence, runner/policy and the current Component
revision; a copied receipt cannot be relabeled for another Component. The supported
API is the evidence-producing trust boundary, as for existing retained receipts;
content digests are not signatures or proof against a hostile operator.

The internal bundle-wide check requires the caller's retained bundle identity and
exactly one receipt for every selected Component. It reopens the complete manifest,
reviewed plan and planned projections, then checks all receipts against the current
source. Missing, extra, substituted or stale receipts refuse. Membership outside
every selected boundary also refuses; passing local checks cannot hide newly
unowned files. Changes to source, projections or receipts during inspection prevent
success. Shared changes require new receipts for the owner and every consumer;
private changes require only the affected Component to requalify.
The result remains a read-only `staged` observation under original-source authority,
not a project-wide release receipt, conversion parity or boundary-transfer approval.

Refined conversion consumes this staging API as an internal pre-mutation gate.
Installed custody remains at `retained-source` boundary-transfer state independently
for each Component; it does not mark a Component drafted or qualified and never
retires retained source. Normal project validation reopens the complete bundle,
receipt set, current source and published projections, so tampering or source drift
fails the project-wide gate.

`project retained-scope refresh` detects stale installed Component custody. Its
acknowledged apply additionally requires `--run-component-baselines`, rebuilds the
reviewed source-free bundle from the stored explicit selection, reruns only stale
Component harnesses and reuses receipts whose exact private/shared inputs remain
current. The complete replacement is checked before project authority review is
recorded; ambiguous newly unowned source still refuses and requires a newly reviewed
selection rather than inferred ownership.

The implementation is `adapters/monorepo_components.py`: `stage_monorepo_components`,
`component_retained_revision`, `run_component_retained_harness`, and
`check_component_retained_receipt`, plus `check_monorepo_retained_receipts` for the
complete boundary set. These are internal integration APIs, not new
CLI commands or a substitute for completing #365's adoption transaction.

## Declared retained layouts

For a project with a current retained-layout declaration, installed Component
inspection resolves source through that declaration and current project/conversion
authority. A layout-bound installation uses
`literate-ai/monorepo-component-installation@2` and records
`retained_layout_identity`. Its source coordinate and declaration identity must
match the actual current layout. A historical installation is stale even when its
Component input bytes happen to be unchanged; inspection does not execute or
repair it. Undeclared projects retain their existing `@1` installation schema.

Acknowledged refresh can locate structurally current source before overall retained
readmission. It reuses the verified boundary selection and executes every selected
Component when the layout binding changed, then publishes a new installation bound
to that declaration. Component receipts remain retained boundary evidence; this
operation grants no whole-project parity, native authority or fresh project receipt.
Pending relocation, changed layout/source/project inputs or intervening installed
payload edits refuse. Publication guards run after private temporary output is
flushed and before replacement; final inspection closes original known facts.
Installed inspection retains the complete consumed bundle, receipt and projection
file set through its final layout read. Refresh retains those original file facts
across execution and transfers them, including the same original parent ancestry,
to the replacement writer. An intervening edit or substituted parent cannot become
a later accepted baseline. Initial publication closes its known
written outputs after validation within its ordinary rollback span.
Ordinary failure restores only still-owned bytes. Full root/initial/wrapper/public
relocation and installed/native acceptance remain under ADR 0057's open owner.

## Authored authority during harness readmission

Retained-harness readmission preserves existing shim files byte for byte, except
for one unambiguous generated baseline-summary paragraph in the wrapper
Component. The plan exposes the summary's before/after facts. Missing or duplicate
summaries refuse before execution; quoted Markdown examples do not grant ownership.
The same rule applies to legacy and contained scaffold coordinates.

Referenced specifications, interfaces, contracts, Flavors, workflows and routing
remain pinned through qualification and publication. The authority comparison
excludes only this operation's declared outputs, and recording the updated review
binds both the expected authority identity and the original review-document bytes.
The current publication journal guards every replacement. A late owner edit,
deletion or nonregular replacement remains untouched; retained originals and the
reviewed plan remain available for explicit acknowledged recovery. Readmission
does not grant specification or release authority.
