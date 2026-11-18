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
smaller inventory. Native qualification currently covers two distinct-interface
providers, not a 32-provider performance cell or a complete multi-provider SDK
lifecycle. Zero providers, mixed native toolchain graphs and dependency-bearing
provider layouts remain outside this host configuration's supported boundary.
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
seconds. Subsequent custody repairs have separate focused checks; complete
current-candidate orchestration remains required. Its generator binds actual
prepared source requests, recipes and workspaces;
all build and acceptance evidence comes from the runtime. The local default
publisher observes membership identity, not durable cache persistence.

Authored orchestration does not establish ordinary model generation, retained
source/recovery, the supported-platform matrix or noneditable installed
qualification. Downstream SDK cutover remains gated on those separate obligations.

The shared independent SDK checker stages the canonical declaration projection's
exact package image beside the original runtime harnesses. This supplies native
bare ESM package resolution without a new resolver or package acquisition. It
snapshots bounded immutable path/bytes/mode data before callbacks, binds the image
identity into runtime observations, and writes the fresh bounded batch without
callbacks before capturing original POSIX stamps. The same guard closes after
runtime children, observers and the combined verifier's outer oracle exit.
Unsupported strong namespace custody refuses before compiler children; ordinary
legacy runtime checks retain their existing two-file namespace and identities.
This mechanism is not native Windows or complete multi-provider qualification.

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
