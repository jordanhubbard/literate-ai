# Pure TypeScript library Flavor

### Requirement: Explicit SDK library source

With `lang-typescript-library` and `package-node-sdk`, a library Component SHALL
supply pure TypeScript implementation under `src/` and explicit dual public root
and subpath declarations. Native generated tests SHALL use
`source/tests/litai_test.cjs` and exercise the built SDK supplied by the lifecycle.
The selected compiler SHALL supply strict ES2022 types without ambient Node or
registry types. Existing TypeScript application policy is unchanged.

#### Scenario: SDK source is compiled by its selected owner

- **WHEN** original provider custody and separately current execution grants exist
- **THEN** the shared lifecycle compiles both formats and emits declarations
- **AND** generated tests execute the built SDK rather than a producer checkout

### Requirement: Preserve authority and qualification boundaries

Generation SHALL use only exact supplied direct public provider facts and bridge
paths. It SHALL NOT discover or install tools, copy provider implementations,
produce package-manager state or fabricate declaration or acceptance evidence.
Canonical Flavor selection SHALL NOT grant execution, independent acceptance,
recovery, publication or downstream adoption.

#### Scenario: A required sealed input is unavailable during generation

- **WHEN** the original owner has not admitted a required provider or compiler
- **THEN** generation reports the unavailable check without a stub or success claim
