## ADDED Requirements

### Requirement: External SDK outputs have live independent ownership

An externally placed SDK producer SHALL bind an acquired workspace, exact source
lock, recipe, target and tools to its current execution authorization. Source and
output roots SHALL be disjoint, including observable directory aliases. A saved
record SHALL NOT grant workspace ownership or authorize another build.

#### Scenario: Original producer needs separate objects and staging

- **WHEN** an authored native recipe selects external placement through SDK path slots
- **THEN** original commands build in an independently owned workspace while the original source remains unchanged
- **AND** license, output topology and runtime capture use the existing SDK owners

#### Scenario: Workspace is substituted or execution scope has ended

- **WHEN** the workspace, reservation or scope no longer matches current ownership
- **THEN** subsequent command execution and SDK capture refuse
- **AND** partial work and foreign replacement entries remain preserved

### Requirement: Path slots do not weaken logical paths or legacy behavior

SDK layouts SHALL retain canonical relative logical paths. External commands MAY
use only the declared source, workspace and SDK-output path slots in argv.
Unknown slots and slots supplied by tool bindings or environment SHALL refuse.
Recipes without external placement SHALL retain their prior request identities
and source-relative execution behavior.

#### Scenario: A source-built SDK is retired and received elsewhere

- **WHEN** a successful original producer is captured and its source and output directories are retired
- **THEN** a fresh placement can materialize the exact protected SDK for a separately authorized real consumer
- **AND** that result does not establish an operating-system SDK or release qualification

### Requirement: Public SDK acquisition honors authored external placement

Public source and project acquisition SHALL support the same live output owner.
Project acquisition SHALL allocate a fresh private owner when an authored recipe
explicitly uses SDK path slots, unless a trusted host supplies a live owner.
Legacy recipes SHALL NOT create an external workspace implicitly.

#### Scenario: A prior grant is used with a different output workspace

- **WHEN** a caller supplies a grant issued for another workspace identity
- **THEN** the build refuses before invoking an original build command
