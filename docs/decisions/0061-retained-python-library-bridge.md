# ADR 0061: Bind Qualified Python Libraries Into Retained Test Workspaces

- Status: Accepted
- Date: 2026-11-04
- Decision owners: literate-ai maintainers
- Release target: 1.4.0
- Roadmap: [RETAINED-PYTHON-BRIDGE-001](../roadmap/active-work.md#retained-python-bridge-001-consume-qualified-native-library-children-from-retained-python-projects)
- GitHub issue: [#307](https://github.com/jordanhubbard/literate-ai/issues/307)
- Approval: The directing user's 2026-11-21 release-resumption instruction authorizes all outstanding roadmap work and states, "all items are already reviewed on the roadmap." This accepts the already-recorded design; implementation and every validation outcome below remain required.

## Context

A retained Python project can qualify a provider as a native library Component,
yet its retained test workspace contains only the implementation-relative harness
source inventory. Qualified children and their committed caches are outside that
inventory. Looking up the original project or an ambient cache from the disposable
workspace cannot provide a reproducible sealed dependency. Copying generated source
into authored implementation directories would create a second source authority.

[ADR 0040](0040-retained-cargo-library-bridge.md) establishes reviewed importer
bindings, current provider qualification and transactional materialization for
Cargo. It explicitly leaves Python consumers to another decision. Existing library
products already describe Python import surfaces and exact sealed exports. The
missing behavior is their integration into retained Python execution and receipts.

## Decision

### Bind the provider and consumer explicitly

Add a versioned Python workspace plan using the existing retained-library binding
and closed artifact/evidence graph wherever their semantics already apply. Keep
existing Cargo schemas, defaults and admission unchanged. A plan binds:

- The importing project and current retained wrapper, harness inventory, complete
  test inventory and source scope, including the prospective source-retirement delta.
- Every provider's Component/interface/import-surface identities, exact qualified
  Python export, target/interpreter requirements, transitive package closure,
  qualification evidence, current policy/verifier and reviewed importer trust.
- Package/module names, exact import roots within the disposable workspace,
  consumer packaging metadata and dependency lock identities where applicable,
  and the full admitted build/test commands and runtime environment projection.
- Explicit artifact sources and finite byte, entry, package and path budgets.

A committed-cache directory is an artifact location, not qualification evidence.
Reopen the existing qualification and source-promotion evidence under current
custody before using its export. A digest or decoded success field alone cannot
establish current admission. No host path, environment variable, package name or
mutable version range may silently select a provider.

### Materialize inside the execution seal

Compose a complete disposable execution workspace from two separately attributed
input classes: the retained authored source inventory and verified library exports.
Library inputs live under short declared private package roots owned by that
attempt, outside the authored implementation tree. Their identities and import
mapping participate in the workspace, execution request and receipt identities.
They must remain included when the receipt is reopened or promoted.

Materialize the exact export bytes through existing bounded archive and filesystem
custody owners. Preserve modes; reject traversal, links or reparse points not
supported by the export contract, duplicate/case-colliding destinations, namespace
overlap and conflicting package roots. Reserve and publish only attempt-owned
destinations. Recheck provider and consumer inputs before execution and before
admission; preserve foreign files and concurrent changes on failure.

Use the selected Python runtime and the framework-owned isolated launcher to add
only these verified roots and the declared retained execution roots. Retain the
standard library. Do not enable ambient site packages, user-site initialization,
unreviewed `.pth` execution, an inherited `PYTHONPATH`, editable installs or an
escape to the original project/cache. Validate actual imported module origins
against the selected export roots during the real consumer journey. Reject
ambiguous namespace-package contributions and module shadowing unless the exact
combined namespace is explicitly bound and verified.

The adapter must consume both existing supported Python library export forms and
the selected packaging profile honestly. If a wheel is required, verify its exact
qualified bytes and complete installed file projection in a private environment;
do not rebuild an accepted wheel or run a backend during read-only inspection.
If an admitted source export requires a build, bind the exact backend and offline
build closure and execute it only as an acknowledged lifecycle stage. Neither
pip resolution nor setuptools discovery may fetch or substitute a provider.
Ordinary external dependencies retain their reviewed lock/provisioning policy.
Missing dependencies refuse instead of falling back to ambient packages or a
network index. Unsupported export or native-extension/ABI forms refuse explicitly;
they are not reported as qualified Python consumption.

### Integrate with retained commands and evidence

Expose Python check, materialize and admit operations through the retained-library
front door with an explicit Python adapter. Read-only check and plan perform no
materialization, import, test, tool installation, backend execution, model call or
network retrieval. An acknowledged, identity-bound materialization/execution plan
owns those effects. Use existing model-free exact artifact retrieval where
supported; credentials remain operator-local and offline mode performs no network.

Integrate the bound library inputs into retained harness execution and readmission,
including the sealed receipt workspace that currently copies only source scope.
Do not enlarge the authored source scope to include arbitrary project ancestors.
Keep existing no-bridge receipts and Cargo behavior unchanged. Use a versioned
receipt/inventory extension when new fields change their closed contracts; old
readers must refuse unfamiliar authority rather than silently dropping it.

All previously admitted full consumer gates and their complete test identities
remain required. Missing imports, zero executed tests, changed test membership,
policy drift or an unqualified provider cannot yield a successful receipt. Reuse
the current independent acceptance and receipt-promotion rules without exemptions.
Remote execution requires complete transfer and revalidation of the same bound
package/evidence inputs; a remote path or local workspace link is not equivalent.
Until that transport is supported, refuse the requested remote operation before
dispatch and report the unsupported capability explicitly.

### Retire source only after prospective qualification

First apply the proposed import/packaging changes and source removal to the
disposable complete workspace. Require the exact prospective consumer to pass
its full original gates against the independently qualified providers. Preserve
shared ownership and unaffected boundaries. Only then may a separately
acknowledged integration plan retire the original source and publish the reviewed
binding/packaging delta. Never delete source merely to discover whether a package
works. Repeating the workflow with an unchanged valid provider is model-free.

## Implementation ownership and execution order

The 2026-11-21 recovery trace identifies these existing boundaries. This map
specifies where the accepted design must compose; it is not an implementation
or a qualification claim.

| Boundary | Current owner | Required Python integration |
| --- | --- | --- |
| Exact artifact graph and native import declarations | `contracts/retained_libraries.py`, `contracts/library_products.py`, `contracts/library_imports.py` | Reuse the complete export graph and Python import surface; retain non-library dependencies and reject undeclared package substitutions. |
| Current provider authority | `adapters/retained_provider_authority.py`, `adapters/retained_provider_native.py`, `adapters/retained_provider_promotion.py` | Reopen current source-derived provider qualification and promotion under their live input guards. A decoded export or a committed cache alone grants no permission. |
| Authored provider qualification | `adapters/authored_qualification_reopening.py`, `adapters/authored_retained_cargo_products.py` | Reuse authored archive reopening independently of the Cargo receiver. Preserve genuinely authored origin and every clean run; never invent source-promotion history. |
| Explicit immutable delivery | `adapters/retained_bundle_delivery.py`, `adapters/directory_artifacts.py` | Retrieve only the exact declared closure and verify bounded package bytes before exclusive attempt-owned materialization. |
| Wheel bytes and installed projection | `adapters/dependencies/python_archive.py`, `adapters/dependencies/python_install.py`, `adapters/dependencies/python_installed.py` | Reuse complete RECORD validation and exact installation projection. Read-only inspection must not invoke the installer or a build backend. |
| Python execution drivers | `adapters/lifecycle/standard_runtime.py` | Compose with isolated `-I -S -B` startup and declared package roots. The existing wheel drivers supply a starting boundary, not retained-provider admission or complete collision/origin checks. |
| Retained source ownership | `adapters/harness_tree.py`, `adapters/harness_inventory.py`, `adapters/retained_layout.py` | Preserve the authored implementation inventory and wrapper ownership; do not widen source scope to capture a provider ancestor or cache. |
| Local disposable execution | `adapters/retained_harness_receipts.py` | Materialize verified packages beside the `implementation` copy, retain both input classes through execution, and bind them to the request, workspace and final receipt. |
| Harness replacement and receipt currency | `adapters/retained_harness_readmission.py`, `application/standard_test_receipts.py`, `test_receipts.py` | Reopen the same package/evidence inputs on readmission and promotion; changed bridge authority must make prior receipts stale. |
| Remote retained transport | `adapters/retained_harness_remote.py` | Refuse bridge execution before dispatch until this owner transfers and independently revalidates the complete bound package/evidence closure. |

Source paths in this table are relative to `src/literate_ai/`. The proposed
Python contracts and adapter must use their own explicit versioned codecs;
Cargo v1/v2 records and no-bridge retained receipts keep their exact meanings.

### First implement the inert plan and current-authority join

The workspace plan must bind the importing project, exact retained wrapper and
source scope, full gate and test inventory, selected interpreter/target, runtime
environment projection, package roots, full export closure, exact packaging and
lock inputs, prospective source-removal delta and finite observation budgets.
Reference the existing typed export and import-surface records rather than
copying their fields into an unvalidated dictionary. Match current provider
recipes, interfaces, original oracles, qualification and policy independently of
the archive's own declarations. Guard the originating bytes through the final
operation. A plan describes intent; neither its digest nor its decoded fields
approve the importer or establish successful consumer execution.

### Then add owned materialization and local execution

Read-only check must finish without creating package roots, importing code,
starting native tools, invoking a backend or accessing a network. An acknowledged
plan may reserve and populate only its exclusive package roots. Both source and
wheel profiles need real execution paths and complete closed inventories. Refuse
unsupported native/ABI forms explicitly before execution. Reuse existing bounded
archive and filesystem owners; do not create a second path/link policy.

The current retained receipt path computes `workspace_runtime_identity` from
external workspace-link locators, copies only `source_scope` into
`implementation`, then executes its harness. That locator identity cannot stand
in for provider bytes or qualification. Add a separate versioned bound-library
workspace input to the request/receipt path and its reopening, without changing
the legacy empty-bridge calculation. External sibling links are likewise not a
substitute for immutable provider materialization.

The isolated launcher must include the standard library and only reviewed
retained/package roots. Validate complete package ownership and collisions before
launch and actual module origins during the consumer journey. Reuse source/wheel
runtime owners while adding the missing namespace/shadowing checks; merely
prepending a directory to `sys.path` cannot establish those facts. Ambient
`PYTHONPATH`, user sites and `.pth` initialization remain excluded.

### Finally integrate prospective retirement and public receipt reopening

Prove the full proposed consumer, with its source removal and import/packaging
delta, in an owned disposable workspace before any acknowledged integration
retires authored source. Require its complete original test identities and all
gates, with independently qualified providers. A successful provider replay or a
new subset of consumer tests is insufficient. Recheck both provider and consumer
custody before admission, then reopen the exact bound package/evidence closure
when promoting or requiring the receipt. Add the public check/materialize/admit
routing only when it can reach these real owners; do not expose placeholder
success or reinterpret a Cargo binding as Python intent.

The capture prerequisite now retains the original whole wheel-backed library
artifact's bytes under its already-live dependency observer and exact existing
build/custody tree. Export blobs still describe only their selected exports. This
does not turn a retained byte record into provider authority: the Python receiver
must reopen the complete matching build, original artifact tree, runtime manifest,
current source/target/lock and every named file before materialization. An older
archive missing any required runtime byte refuses; neither a mutable cache read
nor a new sidecar hash may fill the gap during read-only admission. The initial
controls exercise real native installation/build with explicit source/dependency
fixtures; no qualified provider or retained consumer is asserted.

The initial inert workspace codec now binds the complete typed export graph,
original retained inventories, interpreter/target and environment projection,
reviewed full gates, source/wheel mounts, prospective removal delta and finite
bounds. It preserves non-library dependencies and rejects ambiguous package
ownership. Its package destinations address the disposable execution workspace;
they must not be silently reinterpreted as project-relative publication paths in
an older binding. The provider join must retain each source-derived or genuinely
authored origin and authenticate its original evidence independently. Structural
codecs and schema registration grant no current provider trust, import permission,
owned materialization, backend execution, source retirement or receipt admission.

The internal interpreter observation now compares an independently pinned running
Python with bounded original executable bytes, process metadata and freshly
resolved command names. It uses the existing pinned-input reader, starts no tool,
and closes original ownership and input fields after native callbacks. Other
interpreters and command flags refuse explicitly. Eight native controls compare
against an independently executed interpreter probe and exercise substitution,
limits, actual alias replacement, expiry, non-copyability, reentry and late owner
or input replacement. This observation grants no native version-probe authority,
execution, provider qualification or consumer admission. The complete bridge must
independently select its expected interpreter pin and current provider/consumer
authority; it must not accept those expectations from an archive or decoded DTO.

The complete bridge implementation remains outstanding. The validation list below, including
both real packaging profiles, fresh offline repeat, foreign-origin failures,
unchanged Cargo/no-bridge behavior, independent source review and installed plus
integrated release gates, remains required in full.

## Validation

1. Exercise the public conversion, provider qualification, committed-cache
   publication, Python bridge, prospective retirement, retained full workflow and
   receipt reopening with a real multi-module Python library and consumer.
2. Repeat from a fresh checkout with empty ambient caches and model access
   disabled, supplying the exact artifact closure offline. Verify imports resolve
   to the sealed package roots, with standard-library imports working.
3. Exercise supported source and wheel packaging profiles and actual locked
   dependencies. Refuse absent artifacts, unbound dependencies, index fallback,
   unsupported ABI/export forms and package/module/namespace collisions.
4. Refuse provider/source/cache/evidence/policy/verifier/lock/interpreter drift,
   stale consumer receipts, changed inventories and missing or zero test execution.
   Exercise actual wrong-result and foreign-origin failures through public commands.
5. Verify read-only commands cause no execution or writes; exercise concurrent
   replacement, foreign-file preservation, interruption and bounded inputs.
6. Run unchanged Cargo and no-bridge Python regressions, independent source review,
   complete source gates, fresh noneditable installed qualification and the exact
   integrated platform/release gates.

These are required outcomes, not claims established by this proposal. Approval
authorizes implementation; source retirement and lifecycle execution retain their
existing separate acknowledgements.
