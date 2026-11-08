# ADR 0067: Preserve reviewed source assets through native promotion

- Status: Accepted
- Date: 2026-11-07
- Decision owners: framework maintainers and the directing operator
- Roadmap: [SOURCE-ASSET-PROMOTION-001](../roadmap/active-work.md#source-asset-promotion-001)
- Issue: [#363](https://github.com/jordanhubbard/literate-ai/issues/363)

## Context

Ordinary source review currently drops an `assets` field on a graph node. Three
normal CLI reviews, including two different asset pins, return the same graph
and review identities. Normal project promotion then emits no asset declaration.
The fixture uses one JavaScript library and one immutable JSON file. No model or
generated source execution is involved.

Component authoring already has typed asset selectors, exact lock resolution,
metadata-only coding-agent input and immutable byte overlays. Source promotion
must connect to those owners while binding the review to the original source.
The accepted source remains release implementation authority until qualification.

The directing operator accepted the previously proposed decision on 2026-11-07,
before implementation. This records that planning acceptance under ADR 0006.
No independent maintainer or release approval is claimed.

## Decision

### Reviewable source assets

Add an optional, canonically ordered `assets` tuple to reviewed Component graph
nodes. Reuse `ComponentAssetSelector` for asset id, baseline-relative source path,
assembled runtime path, role, media type and SHA-256 pin. In this source-derived
route, require an exact pin and a plain relative source path belonging to the
accepted source inventory. Asset size comes from that inventory. Shared or remote
URI selectors continue to use their existing authored Component route and are
outside this change.

The empty tuple is omitted from canonical graph serialization, preserving
existing asset-free identities and legacy graph compatibility. Nonempty selectors
participate in the graph and review identities. Strictly decode the supported
node fields. Refuse unknown fields, malformed selectors, duplicate asset ids,
ambiguous source paths and overlapping assembled paths with named errors.

Validate every selector against exact source evidence at review and acceptance.
Bind its source path, digest and size to the accepted snapshot. Missing files,
changed bytes, symbolic paths and source paths outside the accepted inventory fail
before promotion. Existing admission size and classification rules still apply.
The declaration gives no new authority to include a previously unadmitted input.

### Normal promotion custody

Promote the exact reviewed asset bytes from the accepted immutable snapshot into
the owning Component's `assets/<asset_id>` path. Revalidate the source snapshot
before use and refuse collisions before publishing the staged project directory.
The generated Component selector uses that Component-relative custody path while
preserving the reviewed runtime path, role, media type and exact pin.

Add a typed `authored-asset` promotion input kind for these bytes. Record them in
the existing forward-input provenance and generation audit through normal
materialization. Keep asset payloads separate from generated specifications and
coding-agent text segments. Existing projects without this input kind retain
their identities and behavior.

Generate the normal Component lock with the exact asset digest, size and media
type. Use the existing metadata projection, immutable overlay, execution planning,
qualification, cache and admission owners. Do not create a separate asset cache
or a second promotion transaction.

### Scope and acceptance

Implement only the source-backed asset carry chain and its compatibility checks.
Do not expand source intake, add remote credentials, change release authority,
silently reclassify sensitive inputs or relax execution and publication gates.

The first normal CLI acceptance fixture must prove:

1. An asset-bearing graph round-trips and changes graph/review identity when its
   source, runtime path, role, media type or pin changes.
2. Changed pins, changed source bytes, missing inputs, unsafe paths, unknown
   fields, duplicate ids and asset/output collisions fail before project writes.
3. Promotion retains exact bytes, authors the selector, records provenance and
   creates a lock with exact digest, size and media type.
4. The actual generation request contains asset metadata and excludes payload
   bytes. Normal overlay, independent qualification, distinct admission and cache
   reuse retain the exact bytes. Failed execution does not transfer authority.
5. Existing asset-free graph identity fixtures, legacy reviews, native imports,
   source authority guards and promotion recovery continue to pass.

After implementation, the affected application helper must be freshly derived
with its complete admitted data input, normally reviewed and promoted, qualified
twice, separately admitted, integrated through typed consumers, and verified by
the complete application/image/current-receipt gates. The data keeps its existing
owner throughout this process.

## Consequences

Source-derived data-backed libraries can use the already documented asset
lifecycle. Review identities cover their data requirements, and promotion can
retain exact immutable inputs without asking a coding agent to recreate them.

The change adds typed review and promotion metadata. Compatibility and custody
tests are required. An asset-bearing graph cannot be treated as qualified until
its ordinary execution and independent acceptance succeed.

This accepted decision governs the bounded implementation. Execution, release,
source retirement and publication remain subject to their normal authorization
and evidence gates.
