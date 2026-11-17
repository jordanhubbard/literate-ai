# Offline dual Node SDK packaging

### Requirement: Selected compiler and offline package owner

An explicit TypeScript dual library SHALL use the captured selected TypeScript
compiler and npm from the selected Node installation. All selected tool constraint
fields SHALL hold. The operator SHALL supply an absolute `LITAI_TYPESCRIPT_SDK`
package location; selection SHALL NOT install or resolve a registry package.
The shared owner SHALL emit CJS and ESM trees, their declarations, exact public
exports and sealed provider bridges, then verify an offline script-free npm pack.

#### Scenario: Package is used after relocation

- **WHEN** the separately accepted package is installed away from source/providers
- **THEN** CJS and ESM root/subpath consumers use only the packaged closure
- **AND** positive and negative TypeScript consumers retain their declared types

### Requirement: Original custody and legal inputs

BUILD SHALL retain original invocation/provider custody and a separately current
build grant through publication. The source-root LICENSE SHALL contain exact
Component-authorized text; this Flavor chooses no license. Missing legal authority
SHALL fail closed. Source SHALL NOT choose package scripts, registry dependencies,
ambient types, host paths or replacement provider implementations.

#### Scenario: Selection does not establish acceptance

- **WHEN** the canonical Flavors are locked but independent SDK acceptance is absent
- **THEN** no release, downstream adoption or generated/native qualification is claimed
