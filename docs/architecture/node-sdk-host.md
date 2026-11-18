# Explicit Python host configuration for Node SDKs

[ADR 0073](../decisions/0073-sealed-node-sdk-composition.md) owns the opt-in
sealed Node SDK profile. Trusted Python hosts can supply
`LocalNodeSDKHostConfiguration` from `literate_ai.adapters.node_sdk_host` to
`assemble_filesystem_standard_project_runtime(node_sdk_host=configuration)`.
This configuration connects the existing provider admission and root package
acceptance owners. It grants no command, model, network or verifier permission.

Construct it with the original `LockedGenerationAuthoritySnapshot`, an
`expected_execution` plan, `provider_oracles` keyed by exact provider revision URI,
the original loaded `root_oracle`, an explicit `authorize_verifier` callback,
a synchronous `require_current` callback and the selected clean `environment`.
The configuration requires one TypeScript dual-format SDK root and a nonempty
exact inventory of sealed CommonJS JavaScript providers with declarations. Its
count ceiling shares the composition profile's existing 32-provider bound;
aggregate byte/custody and liveness budgets remain independent and can refuse a
smaller inventory. Native qualification covers the complete explicit two-provider
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
Nested error cleanup can surface a retired-scope error above the original witness
or expiry failure; the exception chain retains that original diagnostic.
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

Next qualify the authored noneditable installed Python API using the two original
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
runtime matrix itself is still pending; these controls do not establish it.

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

The next action is actual authored generation through this rebuild adapter,
followed by ordinary model-backed CLI integration with verifier-owned oracle
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

The extraction preserves the two original runtime tests, their shared exercise,
grants, matrices and candidate/provenance suffix. A source AST comparison confirms
the moved write/metadata statements differ only by a plain Component-revision
argument. Production TCB remains `9c07d5d8...26db2fc`. The next installed authored
rebuild case must use fresh candidate wheel bytes and the existing installation,
namespace and module-origin guards. Give that focused case a separate closed
inventory; preserve the original two-case wheel gate and forbid qualified-wheel
manifest output for a focused preflight.


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
