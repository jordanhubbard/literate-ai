# Check, provision, and admit a retained Cargo library

`litai project retained-cargo check` verifies reviewed importer files, current
provider qualification, the supplied archive and any packages already present.
It reports missing packages without creating them. `materialize` performs the same
verification and provisions complete packages under the declared disposable roots.
An existing package must match exactly; neither command repairs foreign changes.

These commands implement the retained native-library bridge from
[ADR 0040](../decisions/0040-retained-cargo-library-bridge.md). `check` and
`materialize` do not run consumer gates, admit an importer, edit Cargo manifests or
locks, or retire source. `admit` is the separately authorized final operation: it
provisions the exact package, requires reviewed retired roots already to be absent,
runs the complete ordered gates and independently reviewed per-target test inventory
under current custody, and returns a canonical admission receipt.

## Prepare reviewed inputs

The importing maintainer supplies the reviewed retained-library binding, Cargo
workspace plan and ordered gate plan. Use the exact canonical JSON binding bytes:
`--reviewed-binding` is its `sha256:…` content identity and `--binding-size` is its
byte count. Independently supply the gate-plan identity and size through
`--reviewed-gates` and `--gate-size`. A candidate's own claims do not substitute for
this review. The workspace's authored manifests and lock must already match the
reviewed after-state; apply no source retirement to prepare this check.

The gate file uses `literate-ai/retained-library-gate-policy@1`, with
`importer_project_id` matching the consumer, `commands` containing the ordered
typed build commands, and `toolchains` containing unique tool content identities
in identity order. It has no repository source lock: normal consumer source edits
belong to a new execution snapshot and invalidate consumer evidence without
changing this policy or requalifying the provider. Changing commands or tools
requires a new policy review. Policy parsing alone does not prove full test
coverage or authorize consumer execution.

Select the current provider project, Component, qualification profile and target.
The configured installed framework, provider lock, recipes, oracle and native tools
must still match its qualification. `--provider-id` and optional `--model` select
that existing generation authority; neither command generates or requalifies code.
Native tool measurement can invoke installed tools.

Supply the exact qualification archive as a local file with `--archive`, or choose
an explicit HTTPS evidence CAS base URL with `--archive-https`. Both use the
binding's logical artifact source selected by `--store-id` and verify its exact
archive digest, size and media type before package provisioning. Remote bytes
pass through the same qualification verifier as local bytes. Neither path falls
back to a registry, local cache or model regeneration.

For private HTTPS artifacts, `--archive-token-env NAME` reads a bearer token from
that explicitly named environment variable; an absent or invalid token refuses
the operation. Keep credentials out of URLs and command arguments. The transport
uses TLS verification, refuses redirects and ambient proxy/authentication settings,
and issues a read-only GET at `BASE/blobs/sha256/DIGEST_PREFIX/DIGEST`, where the
prefix is the first two digest characters. The server must return the exact pinned
media type and byte count without content or transfer encoding. The per-I/O timeout
is 30 seconds; it is not a total elapsed-time limit.

Use `--archive FILE --offline` for supplied-artifact delivery without network
access. `--offline` with `--archive-https` refuses before provider discovery or
transport. It controls artifact delivery and does not provide OS network containment
for native tool measurement. These commands create no artifact service or account.

## Run the check

```sh
litai project retained-cargo check \
  --project ./consumer \
  --binding retained-binding.json --plan retained-plan.json \
  --gates retained-gates.json \
  --reviewed-binding "$REVIEWED_BINDING_ID" --binding-size "$BINDING_BYTES" \
  --reviewed-gates "$REVIEWED_GATES_ID" --gate-size "$GATE_BYTES" \
  --provider-project ./provider --provider-component components/library \
  --provider-profile components/library/qualification/profile.json \
  --provider-id "$CODING_PROVIDER" --model "$QUALIFIED_MODEL" \
  --target host --archive ./qualified-library.zip --store-id reviewed-store
```

Binding, plan and gate paths are relative to the consumer project. The Component
and profile paths are relative to the provider project. The archive path is relative
to the invoking working directory. Use the reviewed values for the shell variables.

To provision missing packages, replace `check` with `materialize`. Configure
`BUILD_DIR` and `OBJ_DIR` consistently with the reviewed package destinations and
Cargo output directory. They must be distinct, and `BUILD_DIR` cannot be beneath
`OBJ_DIR`. Materialization uses project and package write custody and refuses
conflicting destinations. A repeat invocation reuses exact existing packages.

The result reports the binding, plan and qualification identities, verified present
package count and missing package count. For `check` and `materialize`,
`consumer_gates_executed`, `importer_admission` and `source_retirement` remain false.
A successful provisioning result is not permission to delete the original source or
omit retained tests.

## Admit after reviewed source retirement

Commit a canonical `literate-ai/retained-cargo-test-inventory@1` document covering
every target in the reviewed Cargo graph. Commit a separate canonical
`literate-ai/retained-cargo-source-retirement@1` document naming the importer project,
the exact retained-library binding identity and sorted project-relative source roots
which the boundary transfer retires. The roots must already be absent and must not
overlap authored after-state manifests or materialized package destinations. `admit`
does not delete files.

Set an explicit absolute `CARGO_HOME` populated with the reviewed offline registry or
Git dependency closure. Then run the same arguments as `materialize`, plus:

```sh
litai project retained-cargo admit \
  ... \
  --tests retained-tests.json \
  --reviewed-tests "$REVIEWED_TESTS_ID" --tests-size "$TESTS_BYTES" \
  --retirement retained-retirement.json \
  --reviewed-retirement "$REVIEWED_RETIREMENT_ID" \
  --retirement-size "$RETIREMENT_BYTES" \
  --offline --allow-host-execution --acknowledge-source-retirement
```

The initial public adapter supports reviewed Cargo and GNU Make gate executables.
Every selected executable is measured and must match the identities in the reviewed
gate policy. Admission refuses without both explicit acknowledgements, complete
package and consumer-input custody, exact tool matches, a current positive test
inventory, and absent retired roots. The returned
`literate-ai/retained-cargo-admission-receipt@1` binds the provider qualification,
binding, workspace plan, gate policy, test inventory, source retirement, consumer
inputs and every successful command observation. Retain that JSON as CI evidence;
changing consumer source, tools, policy, tests, package bytes, provider authority or
retirement declaration requires a new receipt.

## Public Python v2 receiving transaction

The source-derived CLI commands above retain their v1 wire contracts. Versioned workspace
patches, internal scratch ownership, complete input custody and typed test
protocols use the public Python adapters below. A v2 document must never be cast
to a v1 importer or passed through the v1 CLI to discard those declarations.

The importing maintainer first authors and independently reviews the exact v2
binding, after-manifests and lock, workspace plan, gate policy and complete test
inventory. Resolve the provider through `read_retained_provider_authority` and
`read_retained_provider_native`; their installed distribution, lifecycle policy,
recipes, tools and oracle must still match the actual retained qualification.
A new receiving SDK is not permission to rebind an older provider distribution.
`compose_retained_cargo_current_inputs_v2` joins those live native inputs to the
reviewed files, an independently supplied binding identity and configured store
identifier. It does not generate or requalify source.

When the provider tools live on a different host, the native reader also accepts
the locked projection's explicit `host_platform`, `toolchain_discoverer`,
`dependency_observer`, `observer_identity` and `dependency_guard` parameters.
Select `command_phases=()` for custody-only observation; every returned tool and
dependency observation must have a real currentness guard on its original host.
This mode requires an explicit callable `dependency_guard`.
An archived identity or an unavailable observer is insufficient. This adapter
does not supply a network transport or execute provider commands remotely.

Measure the importing worker's actual `CargoToolchain` and `RustToolchain`
separately and pass both as `consumer_cargo` and `consumer_rustc` to
`compose_retained_cargo_current_inputs_v2`. Their exact identities must match the
reviewed importing plan and gate policy; their guards remain live in the joined
inputs. The original provider command contracts and qualification products keep
their original tool identities. Omit both arguments to retain the local
convenience behavior; one-sided or wrong-role arguments refuse. The same measured
consumer tools can be adapted with
`LocalComponentToolBinding.from_observed_toolchain` for consumer execution.

Use this operation order:

1. `read_retained_cargo_review_v2` reopens the exact independently reviewed files.
2. Enter `retained_cargo_wrapper_context_v2(reviewed)`, then enter
   `reserve_retained_cargo_scratch_v2(context)`. Both context managers must remain
   live through every later step. The scratch declarations name ignored, absent
   enclosing member-package and Cargo-output roots. Package destinations must be
   absent direct children of their enclosing member root; they are not the root
   itself. Existing output cannot be adopted or reopened by initial provisioning.
3. `read_retained_cargo_files_v2(reviewed, manifest_state="after",
   package_state="absent")` binds actual authored inputs and destination absence.
4. Call `materialize_retained_cargo_archive_v2(files, scratch=scratch,
   read_current=read_current, read_archive=read_archive, ...)`. The current reader
   must reopen the same live importer/provider authority; archive transport must
   honor the supplied bounds and configured store. All graph exports are
   published, including non-library artifacts. Exact package bytes and original
   source custody are checked around publication. On failure only unchanged
   owned publications may be moved back; foreign changes and uncertain private
   stages are preserved for review.
5. Finish authorized dependency provisioning and exact-command cache warming,
   then call `read_retained_cargo_execution_inputs_v2(materialized,
   environment=environment)`. It captures the entire Cargo home, complete
   workspace and declared external roots, plus ancestor Cargo configuration.
   Only the still-live scratch owner supplies output exclusions. Do not renew an
   input snapshot after drift to erase a failed execution.
6. `execute_retained_cargo_consumer_v2` requires independently measured Cargo,
   Rust and gate tool bindings, the exact environment and explicit
   `allow_host_execution=True`. It verifies native patch-aware metadata before
   and after the full ordered gates and every reviewed test target. One finite
   deadline and output budget cover all commands. This is same-user execution,
   not an operating-system sandbox.
7. Durable admission additionally requires
   `read_retained_cargo_retirement_authority_v2` and
   `admit_retained_cargo_consumer_v2`. Retirement must name nonempty independent
   reviewed original roots that were actually retired before the live receiving
   snapshot. The reader never deletes them, permits overlap with current
   manifests/packages/review/scratch, or supplies a no-retirement mode. Admission
   reruns the actual guarded consumer transaction, requires explicit retirement
   acknowledgement and returns the v2 receipt from its real observations.

The typed inventory distinguishes named libtest passes and reviewed ignored
cases from custom-harness command success and permitted exclusions. A custom
protocol binds exact measured executable bytes, fixed input identities and finite
command bounds; it cannot invent libtest counts. Exclusion requires an independent
current permission reader, rechecked through the operation. Returning a candidate's
permission identity without reopening its authority is not a valid implementation
of that reader. An excluded target records no executed command or passing case.

Publication and execution alone do not admit a consumer, retire source, prove an
entire application migrated, or authorize reuse of stale provider authority.


## Authored qualification bindings

The same public commands accept the independently reviewed
`literate-ai/authored-retained-cargo-binding@1` format from
[ADR 0072](../decisions/0072-authored-native-graph-qualification.md). The binding
selects its origin; there is no origin override. Unknown formats, mixed fields
and source-derived v2 CLI bindings refuse. Source-derived v2 continues through
its Python receiving transaction above.

For providers explicitly qualified with Cargo profile v3 (`shared-siblings`),
place library destinations beneath one reviewed parent, naming each destination
with its full Component revision digest. Their sealed relative Cargo dependencies
then select the same physical package across incoming edges. Keep the complete
graph and target inventory in the reviewed consumer plan. Materialization copies
these exact packages without manifest repair. Older embedded exports keep their
original format; selecting the new layout requires fresh provider qualification.

An authored binding pins its provider reference, selected run, every export,
workspace plan, gate policy and typed test inventory. Supply the actual authored
policy with `--gate-policy` and the inventory with `--tests` for all three
operations. The source-v1 `--gates`, `--reviewed-gates`, `--gate-size`,
`--provider-id`, `--reviewed-tests` and `--tests-size` options do not apply.
The independently supplied binding digest and size remain required; a file's own
identity fields cannot approve its contents.

For example, after independently reviewing the real qualification and consumer
files, select the current provider and bounded old output observation:

```sh
litai project retained-cargo check \
  --project ./consumer \
  --binding authored-binding.json --plan authored-plan.json \
  --gate-policy authored-policy.json --tests authored-tests.json \
  --reviewed-binding "$REVIEWED_BINDING_ID" --binding-size "$BINDING_BYTES" \
  --provider-project ./provider --provider-component components/library \
  --provider-profile litai/qualification.json --target host \
  --archive ./authored-qualified.zip --store-id reviewed-store \
  --old-output-file-bytes 536870912 --old-output-total-bytes 4294967296
```

Use independently chosen finite limits appropriate to the reviewed consumer.
`--output-files`, `--output-entries` and `--output-metadata-bytes` bound each
complete old or fresh output forest. Source and exact package custody retain their
own policy limits. Old outputs are observed as read-only data and are never
accepted as current execution evidence.

Run `materialize` before `admit`. Initial materialization exclusively publishes
complete packages into absent declared roots; partial or foreign roots refuse.
A subsequent materialization verifies the existing packages and returns a no-op
report. It allocates no execution child and runs no consumer gate. Checks and
materialization return the inert
`literate-ai/authored-retained-cargo-provisioning@1` report.

For admission, keep the same reviewed arguments and add the actual reviewed
retirement file, its independent digest and size, both execution/retirement
acknowledgements shown above, and `--new-output-file-bytes` plus
`--new-output-total-bytes`. The retired source roots must already be absent.
Every admission reserves a fresh exclusive child within each declared output
parent and executes the complete consumer gates and typed targets there. Prior
outputs are preserved. Commands or Cargo configuration that require incompatible
fixed output paths refuse. A successful
`literate-ai/authored-retained-cargo-admission-receipt@1` is created only after
all owned scopes close and original provider, tools, package, complete output,
consumer and retirement facts pass their final checks. The command does not
delete original source.

An excluded target additionally requires an independent operator-reviewed
`literate-ai/authored-retained-cargo-exclusion-authority@1` file, supplied using
`--exclusion-authority`, `--reviewed-exclusion-authority` and
`--exclusion-authority-size`. Its exact importer and binding must match, and its
sorted distinct `permissions` must cover every reviewed excluded target. The
command retains that original authority through the final permission refresh.
An excluded target contributes no executed command or passing case. Decoding a
candidate's inventory or permission document grants nothing by itself.

For a project with locked native SDK dependencies, first prepare the selected
Component and target on the provider host. For example:

```sh
litai project qualify prepare-sdk COMPONENT --project PROVIDER --target TARGET \
  --sdk-cache CACHE --sdk-revocations /absolute/path/to/revocations.json --allow-sdk-builds
```

This command fetches and builds the locked SDKs. Save the returned
`sdk_completion` and `sdk_completion_size` from that trusted preparation.
For `project qualify plan`, `project qualify apply`, and authored retained Cargo
operations, pass `--sdk-cache CACHE --sdk-completion SHA256_URI
--sdk-completion-size BYTES` with the same Component and target selection.
Pass the current operator-managed authorization revocation file with
`--sdk-revocations` on each operation. The reader checks it again at authorization.
Relative cache paths resolve under the provider project. Planning and checking
read the selected SDK from that cache. When project inputs or SDK tools change,
prepare the current selection again and review the new completion.

Authored retained operations reject `--offline` before provider discovery because
current project authority can resolve remote assets. Source-v1 offline receiving remains available. No-SDK qualification
remains available without SDK flags. These operations do not requalify a stale provider
or replace the required genuine generated runs and independent acceptance.
