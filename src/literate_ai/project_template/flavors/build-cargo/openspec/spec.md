# Cargo build-system Flavor

### Requirement: Cargo uses locked registry dependency authority

When `build.system=cargo` is selected, generated Rust source MUST contain
`source/Cargo.toml` and MUST NOT contain `source/Cargo.lock`. The authorized lifecycle
SHALL derive the lock from the admitted manifest in a disposable build projection. The
derived lock MUST bind checksummed registry packages and any exact locked native
library graph. Generated manifests MUST NOT supply path, Git, workspace, build,
target-specific or development dependency authority. Native path edges are projected
only from the exact current library bindings and immutable provider exports.

#### Scenario: Standard builds a locked package

- **WHEN** a Rust Component selects the Cargo build-system Flavor
- **THEN** the lifecycle copies admitted source to an external build projection and runs `cargo generate-lockfile`
- **AND** freezes the derived lock, runs `cargo metadata --locked --format-version=1`, and retains their exact evidence
- **AND** runs `cargo build --locked` for the profile's named binary
- **AND** both commands use `CARGO_TARGET_DIR` beneath the framework object root
- **AND** neither command changes the admitted source tree, which contains no `Cargo.lock`

### Requirement: The exported binary retains Standard runtime checks

The Cargo binary MUST implement the selected Rust Flavor's `--litai-test` and
`--litai-smoke` modes. This profile does not require `cargo test`; broad native Cargo test
execution remains outside the initial contract.

#### Scenario: Generated tests run from the exported artifact

- **WHEN** the locked Cargo build succeeds
- **THEN** the Standard test phase invokes the exported binary with `--litai-test`
- **AND** any nonzero result rejects the generated candidate

### Requirement: Shared native packages remain independently consumable

The v3 profile SHALL explicitly select `shared-siblings`. Each native package SHALL
occupy a full Component-revision directory in a shared sibling forest. Every incoming
edge SHALL reach the same physical provider package. Provider manifests, source,
locks and modes SHALL remain byte-for-byte unchanged during forest assembly. A
provider with embedded native edges SHALL refuse this layout rather than be rewritten.
The builder SHALL compile the same root manifest and exact provider forest that the
exported relative dependencies describe. Closed replay SHALL independently recompute
the source transformation and complete provider file membership without path I/O or
native execution. The v2 profile SHALL preserve its existing format and behavior.

#### Scenario: Independent exact exports share one nominal type

- **WHEN** a native library graph is built with the explicitly selected shared layout
- **THEN** independent consumer dependencies may select each exact library export
- **AND** Cargo resolves one package per provider and accepts the same nominal type across incoming edges
- **AND** whole-project packaging preserves those shared sibling coordinates
- **AND** mismatched provider manifests, projection records, source or file membership refuse
