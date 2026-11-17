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
The current graph supports one TypeScript dual-format SDK root and one sealed
CommonJS JavaScript provider with declarations. Zero or multiple providers,
mixed native toolchain graphs and dependency-bearing provider layouts remain
outside this host configuration's supported boundary.

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
identities across callbacks. A substituted delegate cannot acquire an owned
invocation or build-intent operation. Host-currentness failure retires an active
managed scope.

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
[active work queue](../roadmap/active-work.md). A deterministic authored generator
now exercises complete `runtime.execute` orchestration on the native macOS cell:
real provider admission before SDK generation, distinct finalization policy with
the same original invocation identity, retirement of the generation context,
original packaged six-TypeScript/two-runtime verification, and source membership
publication after root acceptance. The fixture passes in 1081.895 seconds.
Its generator binds actual prepared source requests, recipes and workspaces;
all build and acceptance evidence comes from the runtime. The local default
publisher observes membership identity, not durable cache persistence.

Authored orchestration does not establish ordinary model generation, retained
source/recovery, the supported-platform matrix or noneditable installed
qualification. Downstream SDK cutover remains gated on those separate obligations.
