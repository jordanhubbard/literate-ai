# Explicit Python host configuration for Node SDKs

[ADR 0073](../decisions/0073-sealed-node-sdk-composition.md) owns the opt-in
sealed Node SDK profile. Trusted Python hosts can supply
`LocalNodeSDKHostConfiguration` from `literate_ai.adapters.node_sdk_host` to
`assemble_filesystem_standard_project_runtime(node_sdk_host=configuration)`.
This configuration connects the existing provider admission and root package
acceptance owners. It grants no command, model, network or verifier permission.

Construct it with the original `LockedGenerationAuthoritySnapshot`, an
`expected_execution` plan, `provider_oracles` keyed by exact provider revision URI,
the original loaded `root_oracle`, a synchronous `require_current` callback and
the selected clean `environment`. Choose exactly one verifier mode: an explicit
`authorize_verifier` callback, or `verifier_acknowledgement` from the fixed
`acknowledge_node_sdk_verifier_execution` factory. Neither mode is inferred from
ordinary host-execution permission. Manual configuration keeps its version-1
identity and callback ordering. Typed configuration uses version 2, binds the
original acknowledgement identity and consumes it once for its original runtime
before the first host-owner callback. Failed/reused binding poisons that intent;
it cannot be replayed or copied into a new configuration.
Generic toolchain projection and ordinary ports assembly remain independent:
their existing guards confer no verifier permission. Inside typed `bind`, original
binding metadata is installed and intent is consumed before that binding invokes
toolchain/dependency validation or the host-owner callback. Fresh typed-bind checks
still reject mutation or reentry attempted during earlier generic preparation.
The configuration requires one TypeScript dual-format SDK root and a nonempty
exact inventory of sealed CommonJS JavaScript providers with declarations. Its
count ceiling shares the composition profile's existing 32-provider bound;
aggregate byte/custody and liveness budgets remain independent and can refuse a
smaller inventory. Earlier exact source revisions qualified the complete explicit two-provider
SDK lifecycle and independent packaged root/subpath acceptance on the macOS cell.
Authored-generator `runtime.execute` orchestration is also qualified separately
below for the one-provider control and two-provider/root-subpath cell. A
32-provider performance cell remains open. Zero providers, mixed native toolchain graphs,
and dependency-bearing provider layouts remain outside this host configuration's
supported boundary.
Identical public-interface bytes from distinct selected providers are rendered
once. Both the locked adapter and bounded-context owner use the least selected
provider revision URI as the source representative. Every selected origin is
read and validated before deduplication, and the exact graph edges, provider
resolution identities and recipe imports remain intact. The segment describes a
shared interface rather than claiming a sole origin. Distinct selected providers
still count separately against the dependency fan-in budget; displayed byte,
token and document counts reflect the rendered projection. This DATA attribution
rule supplies no provider admission or execution grant. Complete current-candidate
multi-provider SDK acceptance remains a separate qualification obligation.

A declaration-bearing `LibraryImportSurface@2` carries its complete runtime and
TypeScript declaration records into the existing JavaScript library EXEC owner.
Logical root and subpath exports resolve to their exact declared `.js` or `.cjs`
files beneath `source/<package>/`; they do not fall back to convention-based
filenames. Legacy surfaces retain their existing convention. This does not change
the JavaScript Flavor's `source/main.js` TEST dispatcher requirement.

The standalone driver and host share CommonJS metadata and declared-file
membership checks. Before Node evaluation, the v2 driver checks bounded regular
file membership and rejects links, foreign nodes and conflicting package type
boundaries. Original immutable artifact custody remains independently required.
The single JavaScript loader is embedded as fixed support code; its dispatcher
checks that support argument's SHA256 before execution. Both arguments fit the
existing 4,096-character ceiling. This introduces no provider-supplied code into
the driver and supplies no execution authorization.

The execution plan supplies expected facts, not execution authority. An equal
replanned record can match those facts, but each operation retains its actual
execution object and original owned invocation. One configuration binds once to
the original assembled ports and measured toolchain closure. Runtime entry checks
the original snapshot, configuration, ports, closure and admission selection.
Source-cache and checkpoint recomposition carry that selection forward; losing
the configuration while retaining its ports binding is refused.

`require_current` must be child-free because process polling calls it. Native
toolchain checks remain in the existing closure and command owners. The host
retains original callback, tool binding, source registry, target, oracle and graph
identities across callbacks. Each earlier provider remains in its original
custody scope while later providers are verified. Closing checks every original
witness and independent verifier grant, including after nested contexts retire.
Earlier nested cleanup could surface a retired-scope error above the original
witness or expiry failure. Reviewed cleanup now preserves the primary failure at
the corrected boundaries; broader arbitrary nested-frame cleanup is not claimed.
The terminal SDK operation uses the shared process-liveness context for entry and
successful-exit validation. Standalone calls immediately adjacent to that context
are redundant and removed. The context still polls the complete original cohort;
recursive provider exits and the post-exit finite input/grant checks remain.
Owner loss after binding prevents consumption; owner, grant or provider-file loss
at body return withholds the result and retires escaped operation guards.
A substituted delegate cannot acquire an owned invocation or build-intent
operation. Host-currentness failure retires an active managed scope.

The root acceptance policy exists only inside the accepted provider invocation.
Its context selects the original policy without replacing the ports' manual
policy field. Nested, foreign, malformed and retired copied contexts refuse;
they cannot fall back to manual acceptance. Cleanup retires the scope and resets
its context token, preserving concurrent configuration writes rather than
restoring old values. The legacy manual path applies only when no managed
context exists.

Provider verification and root package acceptance obtain separate constrained
grants through the explicit authorizer. Ordinary SDK BUILD authorization remains
separate too. Original loaded oracle custody, exact package/source/legal bytes,
registered TEST/EXEC evidence, expiry and final finite checks remain enforced by
the existing shared verifier. Configuring this Python API adds no CLI flag,
serialized private policy or default activation.

Operation closing checks also follow the final clock callback: sample once,
then check every original oracle/file stamp, required live membership and host
configuration before validating all verifier grants at that captured time.
The closing cut retains the original baselines; it does not recapture changed
files or allow a completed operation to escape after a callback changes them.

The public host also pins its original snapshot input-closure object. Before
entering a provider operation it captures that closure's validated original
stamps. After the lower operation returns, the host closes original runtime
metadata, installed binding, delegate/closure identity and those same authority
stamps. There is no later owner callback, byte reread or clock sample. This
withholds results if the lower operation's last clock changes host inputs; a
later caller-side runtime guard cannot substitute for this return-boundary check.

Development acceptance is tracked under LIBRARY-ARTIFACT-001 in the
[active work queue](../roadmap/active-work.md). An earlier deterministic authored
candidate exercised complete `runtime.execute` orchestration on the native macOS cell:
real provider admission before SDK generation, distinct finalization policy with
the same original invocation identity, retirement of the generation context,
original packaged six-TypeScript/two-runtime verification, and source membership
publication after root acceptance. That retained fixture passed in 1081.895
seconds. At clean commit `71f2c585`, the retained one-provider authored-generator
orchestration case passes in 830.255 seconds with all 2,016 frozen Python files
unchanged. It retains six TypeScript compiler checks and the existing two runtime formats;
this cell's ESM harness uses its existing file URL, not the separate staged case's
bare root/subpath namespace. Its provider and root verifier grants each retain
their original 30-minute policy, alongside ordinary 30-minute BUILD authorization.
Fresh explicit grant requests have distinct IDs; no live grant is extended. The
generator binds actual prepared source requests, recipes and workspaces;
all build and acceptance evidence comes from the runtime. The local default
publisher observes membership identity, not durable cache persistence. The
original checker, acceptance and publisher run behind observation wrappers;
finalization re-enters the original host binding after the generation context
retires. Original packaged-root acceptance returns before both source membership
publications. Multi-provider orchestration remained required at that checkpoint.

At clean commit `f4f9781c`, the uninstrumented serial class now passes both the
revised one-provider control and two-provider/root-subpath orchestration cases
in 2,655.489 seconds total, with no skips, errors or failures. All 2,016 frozen
Python files, clean Git/head and the selected Node 22.23.4 binary remain unchanged;
loaded test and verifier origins bind to that checkout. Both original packaged
root acceptances return before accepted-source membership publication and the
original `runtime.execute` returns. The two-provider cell retains the complete
twelve-TypeScript/two-bare-runtime root/subpath matrix. All ordinary BUILD and
explicit verifier grants retain their original 30-minute policies, and all child
deadlines remain unchanged. No profiler, success replacement, grant renewal or
clock/deadline extension supplies this pass. Earlier failed ordinary and diagnostic
runs remain retained. This qualifies these authored orchestration cells, not
32-provider performance or a quantified expiry-margin guarantee.

Authored orchestration does not establish ordinary model generation, retained
source/recovery, the supported-platform matrix or noneditable installed
qualification. Downstream SDK cutover remains gated on those separate obligations.

The opt-in cold-start regression in `test_canonical_sdk_cold_cache.py` passes at
clean `91aaa4bf`: one native two-phase lifecycle case and two planning controls,
three executed passes, zero skips/failures, in 2,518.249 seconds. All 2,017 frozen
Python hashes/modes, selected Node 22.23.4 and the 140-file TypeScript 6.0.3 tree
match before and after. Independent evidence review confirms this authored macOS
one-provider cell under the original 30-minute grants and child deadlines, with
no profiler, successful replacement delegate, renewal or clock extension.

Within the fixture, accepted seed cache/CAS inputs remain available while fresh
host bindings, ports, registries, object roots and workspaces are created. The
original seed workspace/object paths become unavailable; old ports remain only
for identity comparison. The cold provider restores the same source tree into
its new workspace and undergoes fresh custody and acceptance. Its new acceptance
changes the receipt-bound SDK recipe and lookup key. The SDK therefore misses
that exact cache key, generates new authored source and completes the original
lifecycle and independent packaged-root acceptance. Original acceptance is not
transplanted. This proves no cold SDK hit, cross-acceptance semantic rebinding,
whole-node/checkpoint recovery, live-model, installed/platform or downstream cell.

The provider-copy integration preserves private cache restoration at 0600 and
uses composition policy `artifact-bytes-preserving-npm-modes-cjs-forwarders@2`.
Original sealed records and artifact identity retain their modes; only the new
SDK-owned non-executable copy becomes 0644. Generic SDK inventories remain strict.
The independent declaration image binds the original artifact identity and complete
projected files. The focused SDK Make suite selects 215 cases: 146 pass, 69 retain
declared prerequisite skips, zero fail, in 114.328 seconds. Private input identity,
source preservation, unsafe modes, callback-time output-mode drift and canonical
tar modes are covered. Independent review approves the two-file production drift
and canonical TCB `3b4a7a4a3b5591fac413c8e2f46b1afc12f9f0755f6c6e5e25290000c676b3ff`.

Earlier failures remain failed: `109a9cb5` completes seed acceptance but rejects
its contradictory authority-change/no-regeneration record before cold execution
(one error, 1,265.063 seconds). `67633e19` uses valid phase decisions and completes
seed acceptance, then fails cold SDK processing on restored private modes
(one failure, 1,320.109 seconds). Both retain unchanged source/tool inventories;
neither is a cold pass or an expiry failure. The successful source-replacement
record preserves the original authority-change rejection.

At the earlier runner-plan checkpoint, the next step was to qualify the authored
noneditable installed Python API using the two original
runtime controls. Reuse the existing wheel runner, qualified-wheel artifact custody
and fresh installed-distribution observations. A frozen test-helper-only bundle
must obtain its Flavors/skills and schemas from the exact installed wheel, verify
resource origins and before/after helper/package bytes, and check initial and lazy
framework module origins. Run outside the checkout with no bundle `src/`, explicit
private `LITAI_CONFIG_DIR` and `LITAI_MCP_TRANSPORT=off`; select only the original
runtime methods. Preserve their actual lifecycle, full matrices, separate grants
and deadlines. This reviewed plan grants no installed result, model execution,
CLI/default activation, retained-adapter, other-platform or browser qualification.

The opt-in runner is implemented as `make wheel-check WHEEL_NODE_SDK_RUNTIME=1`;
the default wheel gate retains its existing selection. The installed interpreter
uses `-I -B` and a fresh empty private bytecode-cache prefix so stale installer
bytecode cannot supersede the verified source. Controller and child retain the
same original namespace observations through execution, including package,
metadata, schemas, helpers and private cache. Resource and pre-capture reads reuse
the shared bounded no-follow/nonblocking regular-file reader. Fourteen focused
controls and seven existing wheel controls pass with no skips. The installed
runtime matrix was still pending at that implementation checkpoint; the later
installed results below supply their own separate evidence.

The first complete opt-in wheel attempt at `886ccf14` stopped before either SDK
case: the existing installed public Rust rebuild rejected the shared assembler's
`node_sdk_targets` argument. All 2,019 frozen Python files and selected Node and
TypeScript inputs remained unchanged. The specialized Cargo and Bazel ports now
forward that optional typed selection to their existing shared validator; Mix
inherits the Cargo correction. Focused Cargo execution also reproduced a second
shared-interface mismatch: specialized SBOM overrides did not accept the base
owner's `write_evidence` keyword. Cargo, Bazel and Mix now preserve that exact
writer through both fallback and selected resolution rather than bypassing its
custody. The original failed attempt remains evidence,
with no installed SDK result. Thirty-eight focused checks pass with no skips:
ten SDK projections, two argument/writer controls, ten Cargo lifecycle checks,
three Bazel lifecycle checks and thirteen Mix authority checks. Independent
source review approves the three-file correction; fresh complete installed-wheel
qualification remains required before it establishes an installed outcome.

The second complete wheel attempt at `d692f0e1` reaches both original installed
SDK cases. The one-provider case passes; the two-provider/root-subpath case
first fails on `security.authorization_expired` for an original provider BUILD
grant in packaged-root runtime pre-launch liveness validation. Later retired-scope
cleanup errors are secondary. The two-case class runs for 2,746.365 seconds with
one pass, one error and no skips; the original one-hour outer bound does not expire.
Independent evidence review confirms all 2,020 frozen Python files/modes and the
selected Node and 140 TypeScript files remain unchanged. CPU saturation was
observed, but causation was not established. No installed qualification or
qualified-wheel export follows. Preserve the original grants, deadlines and full
matrices; hold heavy reruns until fresh resource recovery observations, while
investigating shared freshness cost without weakening custody.

The harness reports `unittest`'s already-collected per-case elapsed times on
stderr after the original runner returns, when that standard result supports
them. This diagnostic includes cleanup time; it is not remaining grant lifetime.
Older result objects remain supported. Add no clocks, profiler, in-case callback,
verdict change or stdout protocol data. Fifteen focused guard checks pass,
including unchanged success/error verdicts, stdout isolation and older results
without elapsed observations. This reporting does not establish native success.

The subsequent complete R3 wheel run at exact source `403386cb` passes both
original installed SDK runtime cases with no skips. The canonical qualified-wheel
manifest binds revision `403386cbde600d616f8d5bbc91fa947f40c1de83` and wheel
`sha256:fd1508c9e9c88279637520c3c0cb9fec581ed99f1af545be92d10894f0e646d5`.
Its noneditable distribution is
`sha256:9ca69ebb4b2139a6a05203c7e4fabe9b2fc3ae317a2e1737e558bba77497df55`
with 1,418 installed members. Independent artifact review verifies both manifest
identities, all 25 test-helper hashes, 364 wheel-resource bindings, installed-module
origins and original namespace custody. All 2,020 frozen Python files/modes, selected
Node 22.23.4 and 140 TypeScript 6.0.3 files remain unchanged. Production TCB stays
`sha256:81c412259f316a6159f6ed617dfe2d936b3d19d2878bf0ccfa8094be54532d4d`.
The original matrices, separate 30-minute grants and deadlines remain intact.

This qualifies the authored macOS noneditable installed Python API at that exact
source. R1 and R2 remain failed attempts; no grant renewal, clock alteration,
profiler or success replacement supplies R3. Successful child stderr and per-case
durations were not retained after its temporary directory was removed; no per-case
timing or expiry-margin claim follows. Other platforms, ordinary model generation,
broader cache/fault/recovery, CLI/default activation and downstream consumer/SDK
cutover remain separate gates. No wheel publication or installed-user upgrade occurs.


### Explicit Standard rebuild adapter routing

The filesystem Standard rebuild assembler accepts the original optional
`LocalNodeSDKHostConfiguration` and forwards that same object to the existing
runtime assembler. Before generation it checks original prepared-snapshot
ownership and agreement with the actual planned execution. It refuses retained
source, a competing native SDK input owner, explicit action workers and configured
action execution before worker admission. An explicit different root oracle
refuses; an omitted oracle preserves the lower runtime's original default.
The existing host remains the authority for supported graph shape and binding.
No callback, verifier grant or cached receipt is serialized or manufactured.

Nine maintained assembler-routing controls pass through focused `make
python-check`, with no skips. They intentionally mock configuration integrity and
stop the positive control at the existing runtime assembler. They establish
pre-generation routing/refusal only, not original SDK admission, generated-source
execution, cache recovery or CLI acceptance. The unchanged baseline lacks this
parameter and fails the new supported-call controls.

An additional direct run of two support fixture classes and their action/finalize
consumers remains failed: 23 tests, nine passing and 14 errors, with no skips.
Every ordered test/error signature matches the unchanged assembler baseline:
six missing explicit worker-result transports and eight stale receipt-policy
fixture objects. Keep this diagnostic failure separate from the passing focused
gate; it is neither a full compatibility pass nor a new SDK lifecycle result.
Independent review confirms the routing delta and its exact 1,277-member TCB
`sha256:9c07d5d88d8acb82a15d756522a56d66812d1b2c43a793916d27544bb26db2fc`.
The earlier installed wheel remains qualified only at source `403386cb`.

At that adapter checkpoint, actual authored generation was the next action. The
later authored results below do not finish ordinary model-backed CLI integration,
which still requires verifier-owned oracle
resolution and a separately constrained verifier-authorization owner. Build-intent
authorization does not authorize the SDK verifier's exact `BuildRequest`.


### Authored source-runner preflight

A deterministic fixture executable now supplies files through the supported
coding-CLI command shape. Its explicit environment contains the fixture PATH
and provider selection, with no copied credentials. The original generator and
cached source runner retain ownership of workspace validation, dynamic recipe
metadata, invocation provenance, candidate lookup and accepted-cache publication.
The child is controlled test code, not a model, full protocol emulator or hostile
filesystem writer. The copied executable includes the selected absolute Python path and is
checked against its actual executable digest.

Four macOS preflight controls exercise an actual child and exact candidate-key /
request / recipe provenance, accepted-cache replay without another child, changed
recipe key plus a second child and exact stale-suite refusal, and unsafe payload
path refusal. The locked SDK-provider source case reuses the existing
scenario's extracted write-only content/metadata helper. The real generator keeps
implementation/suite bytes and reconciles authoritative source-SBOM components and
edges; the returned SBOM binding names that recipe's managed graph and matches
an independent byte digest of the actual resulting file. No native SDK build, independent
acceptance, model or installed-wheel result follows from these source controls.

At source checkpoint `945f0aec`, the extraction preserves the two original
runtime tests, shared exercise, grants, matrices and candidate/provenance suffix.
A source AST comparison confirms the moved write/metadata statements differ only
by a plain Component-revision argument. The later explicit rebuild hooks extend
the shared exercise while preserving both original test methods and their default
runtime path, original assertions and 30-minute verifier grants. At that
checkpoint the TCB was `9c07d5d8...26db2fc`; its next installed authored rebuild
case required fresh candidate wheel bytes and the existing installation,
namespace and module-origin guards. Give that focused case a separate closed
inventory; preserve the original two-case wheel gate and forbid qualified-wheel
manifest output for a focused preflight.


### Installed authored rebuild preflight

`make wheel-sdk-rebuild-preflight` uses the existing wheel builder, fresh isolated
installer, installed module-origin checks and namespace custody. It selects one
separate fixed authored rebuild method. The source must be committed and clean;
Node/npm and the explicit TypeScript SDK are required. The ordinary `wheel-check`
and its original optional two-case runtime matrix retain their own inventory.
The focused script mode refuses supplied wheels, the runtime-matrix flag and any
qualified-wheel manifest argument. Its retained reports always say
`qualified: false`; success would qualify only the named authored case.

The case initializes a real project, places reusable Components under
`components/`, replaces fixture-only workflow/routing references with canonical
project references, then creates fresh locks/audits and records the normal review
marker for those authored inputs. Public preparation captures the final authority.
The Standard binding comes from the actual isolated installed wheel. A test-only
source observer calls the captured original runner exactly once and returns its
unchanged output, delegating key lookup and publication to that original owner.
Declared assets are omitted from the fixture CLI payload only after matching their
exact admitted CAS bytes; the normal runner materializes them.

Explicit hooks call actual `adapter.rebuild`, preserve shared generation/acceptance/
publication checks, and verify the receipt/finalized candidate against the real
project, lock, driver, installed distribution and invocation. Missing hooks or a
different graph refuse before work. No completed candidate, provenance record or
cache bookkeeping is synthesized. The fixture CLI supplies authored files; no
model is called. Success/failure outputs, exact candidate wheel, helper hashes and
fixture-program bytes are retained privately beneath the build directory; failed
attempts remain failed and unavailable diagnostic files are recorded as unknown.

The first installed authored rebuild reached SDK generation after the provider
stage, then failed because the CLI collector required `source/` while the SDK
compiler requires `src/*.ts`. The frozen source and tool inputs were unchanged.
The failed attempt remains retained and does not establish lifecycle acceptance.

Collection now captures the exact bound SDK recipe shape before starting the
child. Only that shape permits TypeScript files under `src/`; ordinary `source/`
checks and refusal of root package manifests, compiled output and dependencies
remain. A profile CID is DATA, not profile-content or execution authority: live
binding, provider admission and build owners retain those responsibilities.
Recipe identity checks reject changes at child return, collection and result
construction. The installed attempt also exposed strict diagnostic custody
rejecting macOS temporary-parent aliases. The controller canonicalizes its newly
created temporary root once, before child paths exist; failed case roots and log
members remain subject to no-follow custody.

The second installed attempt passed source collection, then rejected checkpoint
stage evidence because its attempt had been published against the static recipe.
It retained all four diagnostic files and unchanged frozen inputs; it remains a
failed lifecycle attempt.

SDK checkpoint startup now keeps the original static preparation pending without
publishing an attempt. Inside live admission, before source lookup or generation,
the recorder validates original execution/preparation pointers and captured
plan/key/workspace/recipe values, the permitted bound recipe transformation and
unchanged durable predecessors. It publishes a new immutable attempt for the
bound recipe with normal attempt numbering and lineage. Complete fences follow
live callbacks; recursive binding/reset/replacement poisons the pending entry
even when the nested refusal is swallowed. Failure retires that allocation.
Repairs retain the bound recipe. Ordinary attempts keep their existing behavior;
SDK checkpoint records remain audit DATA and refuse historical source recovery.

Seventeen deterministic checkpoint controls pass, together with four ordinary
repair, five lifecycle and seven SDK generation controls, all without skips.
These are source/DATA regression checks, not installed lifecycle acceptance.

The third installed attempt generated both nodes, then failed while recording a
node failure against its static preparation. Failure reporting now uses the
returned bound preparation, preserving the original failure rather than masking
it with a generation-identity error. The authored fixture retains lower-level
failure text before temporary cleanup: its observation is capped at 64 KiB of
serialized JSON, reserving the rest of the attempt keeper's 256 KiB envelope for
the fixture program and other metadata. Escaping, type names, keys, row count and
messages are bounded; malformed diagnostic capture records unknown and rethrows
the exact original exception. This data is private and never a success receipt.
Nineteen SDK lifecycle and 23 diagnostic/installer controls pass without skips.
The fourth attempt exposed that failure: BUILD toolchain revalidation exceeded
its unchanged 15-second Node probe deadline after 25.519 seconds. Inputs remained
unchanged. An original unguarded discovery and three revalidations at the same
priority took about 70 milliseconds each; this baseline does not establish what
dominated the guarded timeout or exclude contention.

`make wheel-sdk-rebuild-probe-diagnostic` reuses the same builder, fresh isolated
installer and fixed authored case, explicitly selecting its test-only observer.
The ordinary preflight remains uninstrumented. The diagnostic uses a separate
schema/scope and retention prefix; even a successful case reports
`qualified: false`, `preflight_passed: false` and `diagnostic_only: true`.
It cannot supply wheel or final preflight acceptance.

The observer delegates each original operation once, keeps the original Popen
object, and restores observed methods/functions and data contexts. It records
bounded probe/guard depth and counts, inclusive and outer guard time, process
factory, first wait/poll, pipe-close and termination intervals. It retains at most
32 probes with recent failure coverage and 32 KiB serialized output; overflow is
explicit. The attempt's existing 256-KiB keeper accommodates this profile beside
the separately bounded failure and fixture-program data. Capture/restoration
failures remain secondary to the original outcome and mark data incomplete.

Monotonic reads, locks and wait/poll wrappers add overhead. Inclusive guard,
wait and poll times overlap; only outer guard time is a nonoverlapping guard
subtotal. No subtraction establishes an uninstrumented outcome. Six original-call
observer controls and 26 installer/diagnostic guards pass without skips, including
post-restoration failure, original exception identity and cross-mode refusal.
A separate original Node probe exercised the observer successfully without SDK
scopes; it is instrumentation evidence only. Actual guarded BUILD profiling at
`ff78ea62` reproduced failure with frozen inputs unchanged: 41.628 of the failing
probe's 41.632 seconds were outer guard work, with 18 guard calls and 0.004 seconds
in process creation. Its first wait was cleanup, not Node execution latency.
These are instrumented measurements, not an unprofiled performance result.

The authored rebuild callback now owns only its additional project-configuration
root, content and directory-binding checks. The original production host owner
continues to check the full original snapshot after that callback; the fixture's
preceding duplicate snapshot traversal is removed. Real filesystem controls
verify callback-before-snapshot ordering, exactly one owner snapshot check,
refusal of callback-induced locked-input drift and retirement of the affected
host context, plus changed project bytes and replaced project directories.
Those focused controls substitute unrelated assembly and do not qualify tools,
oracles or admission. Independent review approves this fixture-only change;
fresh measurement and unprofiled installed acceptance remain required. Process
polls, production checks and the 15-second probe deadline are unchanged.

The fresh diagnostic at `213b1fa1` passed its guarded probes and failed later in
BUILD on legal-file inventory modes (559.920 seconds for the case), with unchanged
frozen inputs and no observer capture errors. Original authored immutable assets
are deliberately materialized as private `0600` files. SDK compilation now makes
a separate byte-preserving legal copy under
`authored-legal-bytes-preserving-npm-modes@1`, accepting only original private
`0600` and existing portable modes and mapping private copies to `0644`. Original
source files, modes, custody identities and stamp guards remain authoritative.
Root LICENSE/NOTICE paths and inventory bounds/aliases remain enforced; generic
SDK inventories still reject private modes. Composition and compiled-cache
identities explicitly bind the new policy, preventing historical cache reuse
under changed semantics. This preserves Windows mode conventions without
claiming Windows qualification. Installed acceptance remains required.

The unprofiled installed attempt at `60b686ef` then failed in npm literal
dependency revalidation: 19.072 seconds exceeded the original 15-second deadline
(761.738 seconds for the case). Both authored nodes and frozen input identities
were retained. This is not yet evidence of npm guard domination.

The default-off observer now recognizes only four fixed original JavaScript
builder prefixes: Node version, npm version, npm dependencies and npm literal
dependencies. Rows distinguish `whole-node-probe` from `bounded-subprocess`
measurement. The latter excludes surrounding request-file creation and result
decoding; compare only the stated scopes. Existing outer Node rows are reused,
not duplicated. Unknown prefixes and application checks create no new rows.
Only fixed kind/scope labels, timings and bounded counters/type names are added;
commands, paths, environment and request data are not captured. Original process
objects, arguments, calls, deadlines, polls, cleanup, recent-failure ring and
serialized bounds remain unchanged. Independent source review approves the
extension; fresh diagnostic measurement and ordinary installed acceptance remain
separate gates.
Focused actual-child and diagnostic controls accompany these fixes. The earlier
zero-child probe passed full project authority validation, two-node preparation
and canonical workflow compilation. A fresh installed authored rebuild is still
required. No installed lifecycle, full-wheel qualification, ordinary CLI/model
integration or downstream cutover follows from these controls.


The shared independent SDK checker stages the canonical declaration projection's
exact package image beside the original runtime harnesses. This supplies native
bare ESM package resolution without a new resolver or package acquisition. It
snapshots bounded immutable path/bytes/mode data before callbacks, binds the image
identity into runtime observations, and writes the fresh bounded batch without
callbacks before capturing original POSIX stamps. The same guard closes after
runtime children, observers and the combined verifier's outer oracle exit.
Unsupported strong namespace custody refuses before compiler children; ordinary
legacy runtime checks retain their existing two-file namespace and identities.
This mechanism alone does not establish native Windows or complete multi-provider
qualification. The full native case below supplies a separate bounded result.

Within provider verification, fixed request description is separate from full
subject custody. The public description API still performs full validation;
the established verifier uses pinned original registry-entry and scope-field
identities for its private metadata-only checks. Full subject/catalog, oracle,
file, process and grant checks remain at their original boundaries. Failed
original membership is retired without deleting concurrent replacement state.


SDK BUILD keeps each original export and reserved-file observation through
compiler/packer observers, manifest and resolved-SBOM creation, and the final
owned invocation close. The complete output must match exactly the bounded
original projection and reserved records. Native exclusive directory publication
never replaces an occupied destination; a read-only single-use observation
transfer permits only the known rename's root-ctime change while retaining every
original descendant stamp. The package owner uses the same shared observations
and exclusive mover, retaining partial copies until their exact path/content/mode
inventory joins the whole package. Parent creation uses the shared no-follow
directory owner before any redirected descendant can be created.

Unknown occupied SDK artifact, package and checkpoint destinations refuse.
Known live compiled-plan cache hits retain their original output witness through
closing callbacks. Failed or uncertain SDK stages remain for diagnosis; recursive
cleanup must not discard a callback's unknown files. These conservative refusals
do not qualify durable cold-cache recovery. Strong original namespace custody
remains POSIX-only; generic cache publication separately uses Windows native
handle identity and does not infer persistent identity from a zero Python inode.

Compiler and declaration operations snapshot caller-supplied path/bytes/mode and
identity data before callbacks; result labels bind those same snapshots. Oracle
retention budgets charge every declaration-case source reference conservatively,
including repeated paths. The shared SDK tool environment policy v2 removes
case-insensitive `NODE_`, `NPM_` and `LITAI_PROVIDER_` ambient variables after host
binding composition, while retaining the explicitly selected clean tool inputs.
None of these observations supplies an execution grant or extends BUILD expiry.


Pinned authority revalidation uses a fresh bounded POSIX directory batch when the
ordinary reader and native descriptor operations support it. It retains every
ancestor, reserves one of the 64 descriptors for a file, preflights the complete
file set, reads exact bounded bytes and closes original descriptor/name/directory
observations and entry metadata before returning. There is no plan, metadata or
payload cache across calls. Catalog discovery, original lock/audit checks and
owner/clock/grant boundaries still run. Capacity or unavailable identity declines
batching before payload validation; drift and I/O/close errors refuse. Windows
and custom readers retain their existing ordinary path. This underlying reader
fallback does not relax the SDK profile's separate strong-namespace requirement.

The saved pinned-input stamp observation keeps primitive entry values, including
original paths, boundaries, bytes and labels. Equal-value idempotent pinning is
ordinary DATA; changing an aliased frozen entry cannot silently retarget an
already captured observation. Local read benchmarks do not establish complete
SDK throughput or extend the ordinary 30-minute BUILD authorization.


Local catalog-reference capture also shares bounded original directory topology
within one synchronous validation. The strict default POSIX reader holds at most
62 directory descriptors, reserving two for legacy fallback. Each payload uses
its original entry's parent FD and complete original ancestor chain, with fresh
named/held checks before and after bounded reading. No currentness or payload
result is cached. The constructor's immutable tuple slot retains its original
cleanup stack independently of mutable lookup/projection fields; substitution
refuses admission while cleanup closes only original handles. This does not claim
protection against arbitrary changes to trusted methods or ExitStack internals.
Reentrant include/read/close attempts permanently fail the active capture even
when a callback catches their immediate exception.

Expected content identity is detached before blocking reads in both the ordinary
pin and strict capture paths. A declined strict read preserves its original path
and expectation through the complete ordinary validation path. Capacity or
unavailable native identity declines before payload reading; I/O, drift and
cleanup failures never retry. Remote/custom/unsupported reference or Flavor
shapes close the shared view before ordinary dispatch, including a second Flavor
shape check after its blocking manifest read. Local asset resolution remains on
its existing owner; catalog membership discovery and final input-closure
validation run after the shared view closes. These checks add no execution grant
or BUILD duration and do not qualify native Windows or identity-less filesystems.


At clean commit `e713cc8d`, the complete canonical two-provider public-host case
passes in 1,762.745 seconds. Both actual producers use their exact nested CommonJS
runtime paths, with the throwing decoy retained. SDK BUILD/cache/TEST/EXEC/PACKAGE,
packaged TEST/EXEC and independent packaged-root acceptance complete. The original
root plus `sample/math` matrix retains twelve TypeScript children and two bare
CommonJS/ESM runtime children, with the existing child deadlines and ordinary
30-minute BUILD authorization. Provider verifier grants retain their explicit
45-minute fixture policy; independent root acceptance retains its 15-minute grant.
No grant is renewed or replayed to get this result. All 2,016 frozen
Python source files remain unchanged and the source tree stays clean. Late CPU
samples were busy; this pass is not a paired full-lifecycle performance measurement
or a guarantee of expiry margin. The earlier failed full attempts remain evidence.
This explicit staged host case is separate from the authored `runtime.execute`
qualification above. It does not establish ordinary model generation, durable cold recovery, installed/platform qualification,
default activation or downstream Aviation cutover.

### Absent process observers

The original library verifier keeps oracle checks on both sides of every process
observation. If no observer is supplied (`None`), one full owner/authority guard
runs between those oracle checks; no callback or other effect separates an
additional adjacent guard. With an observer, the original before/after guards
and `finally` cleanup remain in force, including mutation and exception paths.
This local deduplication does not cache authority, change grants or establish
multi-provider orchestration expiry margin.

<a id="planned-continuation-of-inspected-verifier-custody"></a>
### Inspected verifier custody and remaining authorization

Status: bounded original capture/closing transfer, accounting, cleanup/ticket
ordering and fresh primitive compiler views are integrated and source reviewed.
The current native candidate, verifier-specific authorization and ordinary CLI
qualification remain pending. Historical support checkpoints below retain their
original evidence scope; the wired producer/consumer is described afterward.
The owning work remains LIBRARY-ARTIFACT-001. Current capture, scan and membership
results do not grant classification or execution authority.

Original provider scopes legitimately retire before the outer runtime operation
finishes. A continuation must be captured from the exact enrolled CAPTURING
entry, bracketed by the original full validation, and become usable only after
that entry reports successful CLOSED status. It may run only during the original
operation's CLOSING phase. It cannot recreate or call a retired provider scope.
Fresh publication entry receives fresh witnesses.

Capture cleanup now owns terminal ticket publication. Enrollment records the same
weak membership pair in the live entry and its reservation. Only the outer owner
reports CLOSED, after identity removal, settlement/drain and journal removal;
cleanup failure or uncertain reporting fails the exact original ticket. Journal
recovery releases resources without replaying CLOSED. Focused synthetic and
actual provider controls cover enrollment/terminal publication cancellation.

The existing `capture_materialized_files` observation already retains only
original paths, file/directory stamps and ancestry observations after readback.
Provider and registered package roots persist beyond their inspection scopes, so
this observation can continue their file custody without retaining captured
artifact rows. Original namespace, replacement, mode, link and POSIX ctime checks
must remain intact.

`PinnedInputClosure.capture_current_stamps` has a different lifetime: its entry
check retains the original closure and content. Reusing it after releasing the
capture's byte reservation would retain uncharged payloads. Native-tool
continuation instead needs detached exact command/launcher/runtime/version/digest
preimages and original path/stamp/ancestry observations, bracketed by the existing
full tool checks. Tool binary bytes remain identity-only inputs and their capture
readsets must still collect after release.

At the standalone-observer checkpoint, the detached direct-Node helper was
implemented separately from runtime integration. It brackets metadata capture with the original full byte
checks, preserves the two existing labels and retains no pinned-input closure or
binary payload. Its sticky continuation checks original tool metadata, file
stamps and directory ancestry without reopening the readset. Sixteen synthetic
POSIX controls pass, including closure collection, substitution, replacement,
restored-mtime writes and ancestor changes. This is source-level observation
support only. At that checkpoint, membership and closing joins were unwired.
Those bounded joins are now integrated; native execution and performance
qualification remain separate.

At the earlier storage-observer checkpoint, live captures snapshotted the
original compiler, SDK, Node, file and identity
field storage through original C descriptors and class/namespace fences. The
identity algorithm's primitive instance storage is independently fenced. The
sticky guard retains original source references and does not independently admit
initial digests; both original full `_rows` validations bracket its capture.
Compiler/SDK identities or length/digest records alone remain insufficient for
continuing original-object membership. Closing must still transfer the necessary
original compiler, SDK and snapshot references under quota.

That earlier capture reserved an additional 256 MiB before constructing the
storage snapshot, then retained its measured conservative charge alongside
portable rows and tool bytes. The later capped-view integration replaces that
up-front maximum with prepaid sizing and fresh bounded observations.
The shared 512-MiB ceiling is unchanged; this stronger accounting may refuse
concurrent captures previously admitted by the incomplete byte accounting.
After all original closing checks, explicit release severs guard cells and source
references even when body exception tracebacks survive. Live-entry removal gates
lease settlement: an uncertain removal keeps the exact lease charged in the
existing journal until metadata cleanup resumes. Release remains outside locks,
and registry/release failures preserve the original body error or cancellation.
Provider and root wrapper references also clear before outer settlement.

The focused controls include a retained original body traceback, external compiler
owner removal, actual compiler collection and private source-reference collection.
They do not establish compiler custody after capture retirement. Retain the
necessary original compiler, SDK and snapshot references under transferred quota.
Deduplicate only within one operation and only for the identical original compiler
and snapshot facts. Do not share such witnesses across operations.

The quota now accepts bounded exact tuple descriptions of those facts. It checks
tuple structure and original leaf identity, without value equality or caller
iteration. Equivalent freshly allocated containers can deduplicate within the
same operation; changed leaf references fail. This is accounting support only:
the fixed compiler owner must still capture original mutable field storage,
reserve its retention first and perform the required full byte validations.

Live capture now creates an oracle observation with fresh weak references to the
original oracle, loaded registry entry and pinned-input authority. It checks the
same original registry entry, exact C field storage, closed JSON/CID metadata and
original file/ancestry stamps. The existing loaded weakref's callback and bound
scope/file-checking methods are not retained. Neither registry replacement nor a
reloaded entry can supply a new baseline. Detached file observation permits
unrelated sibling activity while rejecting file replacement, ctime and ancestry
changes. The factory itself admits no initial bytes: the live owner brackets it
with the original full oracle scope checks.

Reserve 128 MiB before retaining oracle metadata. Sequence this after measured
compiler storage admission, retaining the unchanged shared ceiling. The measured
charge includes primitive source estimates and 32 MiB for bounded metadata/path
observations; the primitive estimate alone is not a heap/quota measurement. The
shared finite metadata observer preserves its default callable API and adds an
exact-bool opt-in returning guard, idempotent release and primitive estimate,
including mapping keys. It severs snapshot/iteration cells on release and failed
construction, with retained-traceback controls for this closed JSON/CID projection.
The shared `_record_values` reader now clears its original record/dictionary,
current item and partial field buffer in `finally`. Source-bearing RecipeDocument
controls retain actual validation/construction failure tracebacks and prove source
release with substituted getters uncalled. This extends field-reader cleanup
coverage; it does not establish runtime phase ownership or general heap authority.
Oracle release clears its observation cells before final resource-charge removal.
Successful handoffs retain those cells through capture settlement.

The standalone observation works after original input-scope exit but grants no
runtime phase ownership. The later original-operation join supplies bounded
closing transfer. The observation alone cannot revive a
scope, reload an oracle, authorize execution or stand in for phase enrollment.
Closing must transfer the original references, charge and release ownership as
one transaction rather than releasing them when the live capture ends.

The pool now supports durable cleanup of an exact private closing payload before
it detaches that payload or removes its charge. The original class release entry
and helper are bound explicitly; class/MRO/namespace checks and original C-slot
failure bookkeeping refuse substituted helpers/getters. Compiler, oracle and file
release components progress independently. An uncertain completion retries only
idempotent DATA cleanup, while recorded completed components are not called again.
All three components run outside quota locks with the original record/charge retained.
Allocation failure after component cleanup resumes detachment without replaying
completed releases. Closing-reader borrow still defers retirement cleanup. This
support was integrated into pool draining before operations could create, enroll
or transfer payloads into CLOSING. The later original producer now supplies those
joins.

Original compiler tuple-valued fields (SDK files and Node command) now use an
immutable tuple-backed identity anchor distinct from structural fact tuples.
Fresh structural containers can deduplicate, while replacement of an original
tuple field refuses immediately. The anchor cannot be rebased through attribute
or item assignment; captured original tuple operations read its storage without
getter dispatch. Compiler
source deduplication also needs each observation's metadata charged separately.
The runtime handoff preparation support now adds 2 MiB for every retained
compiler observation, including the first; live file/path accounting is described
below. Retain the full active base until durable ownership,
record PREPARED versus COMMITTED joins, and release closing views outside the
binding lock, preserving the original body/closing failure.

The runtime now lazily allocates one resource owner per operation and original
pool. A bounded publication journal precedes allocation, and the pool records
the opaque owner in that journal before returning it. Concurrent losing owners
and interrupted allocations retire outside the binding lock. Operation publication
is inside the cancellation cleanup boundary. Failed retirement keeps its original
pool/owner and active binding until metadata cleanup succeeds; recovery does not
replay the operation body, closing checks or CLOSED reporting. This lifecycle
support initially did not attach captures or closing payloads to those owners.
The later producer now attaches them through original operation membership.

Before bounding retained file metadata, the original materialization helpers now
clear source-bearing locals in their own `finally` blocks. This includes both
persistent APIs, immediate readback, primitive row snapshotting, file reads and
the complete/selected capture engine. An explicit snapshot loop makes partial
construction cleanup visible rather than leaving a generator failure frame.
Retained byte-mismatch/cancellation tracebacks release their source references
without replacing the original exception or clearing external traceback frames.
Successful guards retain only metadata, including their owned-move continuation.
That frame cleanup alone does not account path/stamp storage; the subsequent
live-accounting integration is described below. That cleanup alone supplies no
transfer; full native handoff qualification remains open.

The capture owner's cleanup boundary now includes initial field extraction,
reservations and file/tool capture. Explicit snapshot loops and local `finally`
cleanup also cover `_compiler_values` and `_rows` source-bearing frames. Both
public wrappers protect initial entry failures while preserving their original
inner cleanup before reservation settlement. The original body/cancellation
remains primary, absent cleanup owners are skipped, and live detachment still
precedes quota settlement. These are bounds on the reviewed original frames,
not a claim that arbitrary nested failure tracebacks cannot retain source.

A standalone file-metadata preflight now returns detached root/rows and a
conservative charge. Its caller must reserve 32 MiB before construction and
separately retain the original live source-byte charge. Exact primitive bounds
precede path parsing: root length 4,096/depth 64, at most 16,384 rows with paths
up to 1,024 characters/depth 64, and at most 65,536 derived rows. Each root
ancestor and each file/parent prefix is charged without deduplication, using the
full path length to overcount quadratic parent-string construction. The model
includes temporary dictionaries/sets, path components, stamps, owned-move names
and a fixed allowance for one unexpected filesystem entry before refusal.
The complete detached set still passes canonical cross-host alias/tree checks.
Original file C-slot reads reuse the compiler observer's namespace fence.
Partial construction clears its own source references through retained errors.
This is a bounded accounting model, not a general heap measurement or initial
filesystem admission. Live capture now reserves its 32-MiB maximum alongside the
compiler reservation before preflight and original full materialization checks.
All subsequent resizes and final admission retain the measured file charge.
The materialization and ancestry observers have exact-bool opt-in guard/release
pairs. Failed opt-in guards remain retired after restoration; release clears
original shared cells and iteration locals, including retained failure frames.
Default callable APIs and owned moves remain compatible. Opt-in observers refuse
moves until descendant release ownership and metadata accounting are supported.
Capture attempts file release independently after live detachment and before
quota settlement, outside the capture lock, preserving the original failure.
Closing transfer and native qualification remain separate.

Enrollment now records the original shared pool and opaque capture lease with
each ticket. Transaction support journals only pool/owner/lease handles and its
PREPARING/PREPARED/COMMITTING/COMMITTED state under the binding lock. Pool
preparation, payload attachment and commit run outside that lock. Repeated,
foreign or uncertain joins poison the operation; commit and CLOSED are never
replayed. Any prepared join must be COMMITTED before successful CLOSED reporting.
The closing-pool interface can require the exact bounded original lease set,
rejecting duplicates, foreign handles and active/failed/uncommitted captures.
New journal maps detach under binding and clear outside it. Pool preparation,
attachment and error decorators clear their own source-bearing failure locals;
caller cleanup cannot sever those nested frames. Exact ticket types precede
weak/dict lookups, so foreign hashing/equality cannot run at this boundary.
The capture engine now calls the transaction APIs and transfers its original
observations after every original closing callback succeeds. A capture-owned
pending payload journal retains cleanup custody before preparation and through
uncertain commit or release. Full live base charge remains required until the
transaction and original cleanup settle. Failed or unacknowledged transfer never
publishes CLOSED; metadata recovery cannot replay commit.

Actual provider controls with an injected operation binding close detached
observations after original source scopes exit. They establish bounded producer
behavior, not original native invocation provenance. Compiler sizing now shares
one exact-slot traversal with capped observation construction. Both compiler
serializers accept only its immutable primitive view; fresh observations reread
original slots and reject reference changes before retaining rows. The same
baseline guard brackets both full byte/identity checks. A fresh view also proves
the original direct Node identity preimage, closing the sizing-boundary gap.
Scratch remains charged through every resize until views and observers drop.

The conservative ASCII source policy uses two bytes per character only on
reviewed CPython 3.12–3.14: character storage plus a separate possible UTF-8 copy,
with independent record/header/container allowance. Python 3.11 retains the old
policy because its legacy wchar cache requires more storage. Other interpreters,
unreviewed versions, non-ASCII strings and bytes keep their previous accounting.
The storage distinction follows [PEP 623](https://peps.python.org/pep-0623/)
and [CPython's Unicode size accounting](https://github.com/python/cpython/blob/3.13/Objects/unicodeobject.c#L12895-L12918).
This is a source-accounting policy, not total interpreter heap measurement.
The absolute compiler and shared ceilings remain 256 and 512 MiB. Two actual
independent provider operations fit without cross-operation compiler deduplication.
A three-lease quota control reuses actual reservation sizes and one original
compiler; its extra leases are synthetic and establish no provider/root provenance.
The full two-provider-plus-root native case remains a separate qualification.
Original Pin failure frames can retain their own readsets; this support does not
claim arbitrary nested-frame cleanup.

The closing consumer now checks complete original enrollment/commit membership,
borrows exactly those leases outside binding and calls the captured original
typed payload observer. A private C-slot publication records pool/owner/token
before borrowing, including an unreturned view. After dropping every local and
iteration reference, the reader publishes its dropped proof and completes only
that original token. Exact owner/token/flag DATA checks prevent foreign lookups.
Failed or repeated preparation cannot clear another active reader, even when a
mutable claimed flag is inaccurate. Retirement retains the owner/publication and
charge while a reader is active or its drop proof is unknown. Once the proof is
recorded, metadata completion is idempotent through failures before or after its
transition; recovery never borrows, reruns observations or publishes CLOSED.
Closing rechecks original active identity, phase, poison, joined leases and
metadata witnesses after guards and after successful settlement, whose draining
can run cleanup outside locks. The old binding-lock decorator no longer encloses
pool calls or observations. The wired producer/consumer support does not qualify
the full multi-capture native scenario, expiry recovery or typed execution
permission.

A single capture-to-closing lease must preserve the shared 33-slot/512-MiB bound
without double-counting slots or briefly releasing a retained payload's charge.
Reserve before retaining source references and outside the binding lock; commit
membership under that lock. Abort and retirement release outside it as well.
Do not hold a quota lock while running owner callbacks or releasing the final
payload reference. Keep its charge until that release settles. Release is allowed
only after operation retirement and the final in-flight capture reference are
both settled, including early unwind and concurrent completion. Failed or
uncommitted handoffs remain sticky failures and never become closing witnesses.

Required controls include refusal before retention at capacity, operation-local
exact compiler deduplication versus changed snapshots, concurrent reserve/retire,
early unwind, double release and source-reference collection. Integration must
also prove successful scope handoff, replacement/mode/restored-mtime/ancestor
refusal, original oracle retirement/replacement refusal, final-clock mutation and
zero scope revival. Native integration, typed verifier-specific permission,
classification, installed CLI qualification and Aviation cutover remain separate.

### Planned verifier-specific authorization join

The source implementation joins the existing original capture, enrollment, scan and
closing owners. It does not replace the manual authorizer or infer verifier
permission from the ordinary host-execution acknowledgement. This section is the
implementation contract; typed source selection now joins original issuance and
live/closing enforcement. The qualification limits below remain separate.

One opaque, explicit acknowledgement selects the original locked snapshot and
execution, the fixed verifier policy and scanner, actor/reason, a finite grant
lifetime and the original overall deadline. Its API separately acknowledges that
the selected Node executable and non-source DATA receive identity checks rather
than text scanning. A copied value or a digest lookup is not acknowledgement
ownership. The fixed factory creates its original registration; host assembly
consumes it once and binds that registration to the original configuration and
runtime. Failed or foreign binding poisons the registration. Keep this bounded
registration in a dependency-light authority module; it must not import the
runtime, scanner or issuer or introduce a general callback-based policy factory.

Configuration selects exactly one mode before callbacks: the existing manual
authorizer or the genuine typed acknowledgement. Manual configuration/request
identities and callback ordering remain unchanged. Typed configuration gets its
own versioned identity. Do not expose this configuration branch with a placeholder
or permissive fallback: add it only with working original-capture issuance. The
runtime retains an opaque registration and bounded primitive witnesses, rather
than recursively inspecting policy/scanner objects through finite metadata.

The fixed issuer reserves an operation-local issuing slot before callbacks and
accepts only the exact live operation, original capture and enrolled ticket. It
obtains both canonical preimages and the scan through their original owners,
checking custody and enrollment again after scanning and before publication.
Caller-supplied scan JSON, request documents, classifications and attestations
cannot enter this route. The local observation binds the full role/path/mode/
content inventory, both preimages, owner revision, scan policy/report, original
acknowledged authority and identity-only Node binding. Its attestation records
local custody, with `vendor_signature_verified:false`; it makes no vendor-origin
claim. Preserve the six source suffixes' text-rule coverage and explicit
identity-only coverage for other DATA. Apart from the separately acknowledged
direct Node binding, executable-mode files outside those source suffixes refuse.
The initial DATA-only set is JSON, source maps, plain text/Markdown and the
original license/notice names; an unrecognized suffix is unsupported rather than
silently treated as non-executable. This is a narrow policy choice, not a claim
that static text rules prove arbitrary program safety.

The selected original TypeScript SDK also contains two executable JavaScript
launchers without suffixes: `compiler/bin/tsc` and `compiler/bin/tsserver`.
The version-2 scan policy recognizes only those exact role/path pairs with their
canonical UTF-8 bytes: `#!/usr/bin/env node\nrequire('../lib/tsc.js')\n` and
`#!/usr/bin/env node\nrequire('../lib/tsserver.js')\n`, respectively. It scans
them as CommonJS under deterministic logical paths ending in `.cjs`, while the
inventory retains each original role, path, mode and content identity and records
the scan path. Their disjoint `compiler-launcher/` scan namespace cannot alias an
ordinary original role; duplicate mapped paths refuse before scanning. The policy
identity includes the mapping and those exact required content digests.
This is explicit source coverage, not an executable-DATA exception. Changed
launcher bytes, other paths or roles do not acquire this coverage; unsupported
executable DATA still refuses. The six ordinary source suffixes and the existing
bounded rule set remain unchanged.

Classification and issuance reuse `SecurityPolicy` and `PolicyBuildAuthorizer`.
The fixed policy knows only `execute-library-verifier`, accepts only the two
existing verifier builders and their exact sandbox/compiler/revision/source/
output contracts, and never enables YOLO. Use the existing maximum lifetime and
original deadline as ceilings; no grant renewal, deadline extension or mutation
replay follows from this workflow. Validate the issued original authorization
against the unchanged request before returning it.

The issuer constructs one original immutable-empty `AuthorizationRevocationSet`
and a fixed live verifier over that original state. Supplied feeds/providers are
unsupported in the first profile. Its closing witness checks original identity
and empty contents without callbacks; this supplies no external-revocation
coverage. Every live/closing join still validates the original grant's request,
expiration and revocation fields.

Register each grant before returning it in that operation's existing bounded
aggregate: at most 32 providers and the reserved root slot. Publication requires
the original successful capture handoff, exact request/grant joins and CLOSED
membership. After all callback-bearing closing/cleanup work, obtain the final
shared clock cut and finish with callback-free identity checks; do not adopt a
new baseline after it. A fresh publication operation gets a fresh aggregate.
Failure poisons its original operation without reviving a scope or grant.

Required controls cover absent/foreign/copied acknowledgements and tickets,
manual/typed mutual exclusion before callbacks, substituted preimages/results,
blocked findings, unsupported coverage, reentry, callback-time mutation, exact
request/lifetime/deadline constraints, immutable-empty revocation, aggregate
capacity and uncertain cleanup. The original authored native case, installed
wheel, ordinary model-backed CLI and Aviation consumer/cutover gates remain
separate from metadata and injected-state controls.

The current source implements the explicit fixed acknowledgement factory, a
private original-capture classifier and a private operation-owned grant issuer.
The factory binds the original snapshot,
execution, scanner/policy identities, actor/reason, finite lifetime and original
UTC deadline. Its fixed source witness has explicit release ownership through
both explicit and weak registration retirement; release runs outside the
registry mutex, including when a guard failure traceback remains retained.
The acknowledgement remains weakly referenced by its fixed policy owner.
Capture and original provider-request construction fence description and
serialization dependencies after their own custody callbacks, including nested
request construction. The classifier produces a local-custody observation and
existing `SecurityPolicy` classification, then rechecks original membership and
deadline. These detached classification values grant no execution permission.

The private issuer obtains that classification itself and reuses the original
`PolicyBuildAuthorizer` with its acknowledged actor/reason, lifetime, original
deadline and YOLO disabled. Each intent owns an original immutable-empty
revocation set and fixed live verifier; substituted providers or nonempty state
refuse. A bounded journal holds at most 64 original operations with their original
request/grant/witness pointers and identities, separately from the runtime's
mutable metadata maps. Independent runtime membership prevents clearing an
intent field from disabling enforcement and covers cancellation before intent
publication. Every original ticket receives one reservation before callbacks;
prior grant expiry prevents later issuance. All issued grants remain valid
through live use, committed capture handoff and exact CLOSED membership.

Typed table keys, records, intent, phase and boolean flags are checked as closed
DATA before hashing, equality or truthiness. Closing records original successful
membership after view settlement. Actual resource-owner retirement then performs
the final authority/revocation preparation and shared clock cut before checking
the original aggregate, grants and configuration again. Swallowed retirement
reentry, late poison, expiry and configuration replacement withhold success.
An in-flight token prevents nested cleanup from draining ownership early. Terminal
validation failure still drains grant metadata, records authoritative retirement
completion and propagates failure. Original grant witnesses and intent references
release outside operation and journal mutexes; uncertain cleanup retains the
original registration and denies further typed issuance when necessary.

The shared provider/root verifier runner also accepts an explicitly threaded
`verifier_operation`. Its fixed grant-use boundary requires the original issued
grant object from that operation's independent journal, its successfully closed
capture and committed handoff, original ports and an exact current request
identity. A fresh equal request description is allowed; a copied grant refuses.
Closed metadata validation precedes request serialization. The boundary runs
before execution and after the runner's final clock, subject and ownership
callbacks, so a late loss withholds results. Omitting the operation cannot select
manual execution while the original bound operation has typed grant membership,
including when its mutable intent field is cleared. An absent typed operation
preserves the existing manual authorization path. These checks neither issue
authority nor supply an operation from ambient context.
The independent marker retains weak original ports/state references until grant
retirement finishes. Marker publication, removal and snapshots share a mutex;
unrelated manual execution does not depend on a retiring operation's live lookup.
Original execution seams are captured during trusted module initialization and
checked before use; explicit operations without typed membership refuse before
authorization lookup.

Typed host configuration now selects this producer explicitly. Provider admission
captures the original accepted scope; root acceptance captures the original
prepared package inputs. Both enroll in their exact operation, issue through the
fixed owner, finish successful capture settlement and check the exact original
grant against the actual request before entering the shared runner. Typed policy
identities are version 2; manual identities and callbacks remain version 1.
Typed base construction performs finite checks only until host binding consumes
the intent; the binding's original closure/dependency validation and host-owner
callbacks run afterward. Manual construction retains its original validation
sequence. Fixed original helper references survive custody callbacks, and a
substituted integration helper refuses before the replacement can run.
These source and injected-construction controls do not establish original-root
issuance, native or installed host-mode acceptance, ordinary model-backed CLI
qualification or Aviation cutover. The combined native matrix finished in
2,008.415 seconds with three passes and one error: the full typed lifecycle
reached packaged-root acceptance, then its original provider's ordinary BUILD
grant expired during declaration-check custody validation. Root acceptance did
not return and publication was not qualified. The typed verifier's one-hour
acknowledgement does not extend the separate ordinary 30-minute BUILD policy.
Keep that policy, clocks and original grants unchanged; diagnose legitimate
overhead before another qualification attempt.

A separate opt-in sampling diagnostic ran the original typed fixture with
`SDKRuntimeDiagnostic.observe(observe_grants=False)`. It installs no grant-method
wrapper, leaves the fixed acknowledgement factory's namespace intact and records
`grant_observation_enabled:false` with an empty grant list. Default diagnostic
behavior is unchanged. Sampling retains only bounded logical file/function/line
metadata from the original test thread, with existing persistence and cleanup
protections; it cannot establish worker CPU distribution or reliable expiry
margin. Scenario cancellation remains primary through later cleanup/persistence
errors. A cleanup error after a successful scenario remains a failure even when
the caller is handling an unrelated exception. These diagnostics always remain
`qualified:false` and do not establish native or installed acceptance.

That diagnostic failed with the same ordinary BUILD expiry after 1,918.561s.
Observer and lifecycle cleanup complete, with zero capture errors. Its 9,293
samples include dropped frames and depth truncation: 4,308 show the original
thread waiting for lifecycle workers, so they do not attribute worker CPU.
Separate three-call configuration profiles measure about 72ms per bound-host
check and 83ms per base-admission check, each with one snapshot check per call.
Those profiles omit active invocations and grant aggregates.

[Accepted ADR 0075](../decisions/0075-scoped-direct-node-validation.md) describes
an opt-in direct-native runtime-observation profile. The directing user accepted
it as written on November 19. It changes
the temporal validation policy and requires a qualified closed launch-input
boundary; an executable digest or detached file witness cannot supply it. No
activation or native qualification follows from acceptance. Planning and
implementation are now admitted under #452; current default runtime probing and
every grant limit remain unchanged.

### Installed typed-host preflight

`make wheel-sdk-typed-host-preflight` builds a fresh candidate from a clean exact
Git revision and runs a separate installed-Python cell. It preserves the existing
manual two-case wheel matrix. This mode refuses supplied wheels, rebuild/probe
diagnostics and qualified-wheel publication; it cannot create whole-wheel or
release qualification.

The reviewed helper extension selects exactly the genuine binding/dependency-guard
case and the two-provider/root-subpath typed authored runtime case. The latter
retains its original acceptance/publication receipt checks, observes actual
provider-plus-root grant roles and asserts that the manual verifier authorizer never ran.
Both cases execute outside the checkout under `-I -B`, with an empty private
bytecode-cache prefix and original installed namespace/origin custody checks.

The separate `installed-node-sdk-typed-host-preflight@1` protocol records
`qualified:false`, `preflight_passed:true`, exact case IDs/counts and
`authorization_mode:"inspected-verifier@1"`. Both the result file and stdout must
match that typed scope; old manual result schemas refuse. Evidence retains the
exact wheel, installed distribution, helper manifest and driver hashes. Declared
fixture inputs are separately labelled: binding lifetime/deadline offset of
600/1,200 seconds, runtime limits of 3,600/3,600 seconds, explicit identity-only
input coverage, no renewal and constructor-owned immutable-empty revocations.
Those are hash-bound fixture inputs, not observations of grant timestamps or
remaining expiry margin.

The source/protocol and filesystem controls do not establish installed execution.
The actual preflight remains pending passing source-native qualification and exact candidate
artifact review. An eventual pass proves only this authored macOS installed
Python API cell; ordinary model-backed CLI, other platform/browser, retained
consumer and Aviation cutover gates remain separate.
