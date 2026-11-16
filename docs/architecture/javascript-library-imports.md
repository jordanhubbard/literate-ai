# Default JavaScript sealed-library consumption

[ADR 0038](../decisions/0038-importable-library-artifact-authority.md) requires exact accepted libraries to be consumed in process. Issue #447
tracks the default JavaScript adapter gap: typed bindings exist, but the generic
builder copies/syntax-checks source without materializing a native import map.
A generated npm dependency declaration is correctly refused without package-npm;
that refusal must remain. This document defines the adapter implementation, not
new registry permission or a claim of native consumer acceptance.

For the generic JavaScript tree path, only current typed direct library bindings
may introduce packages. Verify the exact consumer/provider revision, capability,
public interface, complete import surface, target, artifact and dependency closure.
Reject missing/substituted/ambiguous bindings or package-name collisions before
publishing an artifact. A package/module path must remain in its declared portable
package namespace; never infer an ambient package from arbitrary text imports.

The lifecycle creates a fresh artifact-local node_modules package for each selected
sealed provider. A closed package exports map exposes only the exact declared
module paths. The complete original sealed provider directory is retained inside
that package without edits, preserving its existing nested dependency placement.
Generated metadata maps each public subpath to its exact provider module. There
is no host-absolute import, NODE_PATH, checkout lookup, symlink, npm install,
network acquisition or same-named package fallback. Generated source and provider
artifacts stay unchanged. Nested native packages remain independently qualified;
this increment does not claim package-npm consumer composition.

Provider bytes must match their sealed blob before copying and the copied directory
must match afterward. Recheck original provider/source custody before sealing.
All file acquisition uses existing bounded directory-export constraints. Reject
preexisting destination packages and any unsafe/link paths. The copied provider
and generated exports metadata participate in the consumer's sealed artifact hash.
A materialization version participates in the build cache key; an older copied-only
artifact cannot satisfy a new binding merely because its old key is present.

Acceptance must run actual Node imports through the normal generic consumer build,
generated tests and execution, not a callback that returns accepted data. Cover
multiple capabilities, CJS and ESM consumers where the accepted provider format
supports them, transitive provider imports, cache reuse and artifact relocation.
Deny foreign/missing/substituted bindings, undeclared subpaths, same-name ambiguity,
source/provider drift, destination collisions and links. Existing npm admission
and non-JavaScript behavior remain unchanged. An isolated two-Component ordinary
rebuild is required before a downstream native cutover claim.

The selected, current Node compiler binding supplies its actual built-in namespace
through a fixed guarded metadata probe; reject any colliding package before use.
Bind that captured namespace in the materialization identity. Before publication,
reject node_modules anywhere in the original consumer export and a matching
package self-reference in any consumer package.json. Reject Node-reserved module
segments as well as filesystem traversal. Namespace scans use the archive-entry
ceiling, and package metadata reads are capped at 64 KiB.

A pre-generation generic source-BOM component records each exact provider revision
and import-surface identity, with a root dependency edge. The shared pure projection
supplies the same complete declaration to the model and validates it against live
typed bindings; missing/substituted declarations fail. This is not an npm dependency
or a claim that an authoring revision is a compiled-byte hash. Existing source and
resolved dependency admission remain unchanged. Actual sealed provider blob,
interface, target and dependency identities remain in the consumer build binding
and artifact evidence. No runtime import allowlist exempts imports from the BOM.
