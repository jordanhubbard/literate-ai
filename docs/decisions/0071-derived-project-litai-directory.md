# ADR 0071: Contain derived-project framework authority and state under litai/

- Status: Accepted under the directing-user implementation delegation in ADR 0074
- Date: 2026-11-10
- Decision owners: directing user and literate-ai maintainers
- Release target: 1.4.0
- Roadmap: [PROJECT-LAYOUT-001](../roadmap/active-work.md#project-layout-001-contain-derived-project-literate-ai-files-under-litai)
- Governance: [ADR 0006](0006-significant-feature-request-governance.md)

## Context

The directing user requires all Literate AI files in each derived project to live
under a `litai/` subdirectory, beginning with the release currently in progress.
Current project storage and discovery read `literate.project.json` directly from
the repository root. Templates also spread framework Components, Flavors, skills,
workflow/routing declarations, orchestration and roadmap files across that root.
Changing template paths alone would leave lifecycle, inheritance, update and
release consumers disagreeing about project authority.

The containing repository remains the application project. Its native source,
package metadata and user-owned documentation need not move. ADR 0057 separately
permits retained implementation at the repository root; framework containment
must compose with that requirement without relocating retained application bytes.

## Decision

### One project, one framework directory

Every derived project has one canonical framework directory at `<project>/litai/`.
Its project manifest is `litai/literate.project.json`; framework release/test/worker
configuration, Components, Flavors, skills, workflows, routing, orchestration,
locks, framework documentation, roadmap, durable receipts and framework-managed
runtime/cache/build state also live beneath `litai/`. Authored authority remains
separate from disposable output, for example `litai/components/`,
`litai/generated/` and `litai/_build/`. Cleanup must not remove authored authority,
durable evidence or another session's environment.

The application repository root and framework directory are distinct coordinates
in the shared project context. Preserve the existing meaning of project-relative
paths: resolve them against the application project root. Store new framework-owned
coordinates with their `litai/` prefix, and rewrite moved references through the
migration owner. Do not silently rebase all application paths against `litai/` or
make `litai/` a second independent project. CLI discovery from either coordinate
or a descendant selects that same containing project. Nested independent projects
retain their own roots and `litai/` directories.

Use this context for configuration storage, catalog roots, inherited authority,
locks, source inventories, lifecycle/worker execution, receipts, package/release
policy and agent discovery. Refuse conflicting legacy and contained authority,
redirected directories, escaping references and ambiguous nested ownership.
A directory name alone does not establish disposable ownership or permission to
exclude it from retained-source capture.

### Required root integrations

Keep only integrations whose external consumers require root placement, such as
coding-agent discovery files, a native build entry point or root Git ignore rules.
Framework-owned text in those files delegates into `litai/`; it must not duplicate
specifications, policy, skills or mutable framework state. Preserve custom text
through the existing owned-region/entrypoint mechanism. Document and test a finite
inventory of these exceptions rather than allowing arbitrary root framework files.
Application README, PROJECT, changelog, source, tests, package manifests and product
documentation remain application-owned when they serve the product itself. Move
framework-only roadmap, instructions and generated harness material into `litai/`.
A shared file requires an explicit ownership partition; its filename is not proof
that all its contents belong to the framework.

This requirement governs derived projects. The framework repository's own package,
canonical catalog and authoring layout remain separate from the generated-project
layout; its tests must exercise the actual derived layout.

### New projects and existing-project migration

Create/adopt/init produce the contained layout. Update and reparent preserve it.
Existing root-layout projects remain inspectable so users can plan migration, but
must migrate before being reported as conforming to the 1.4 layout requirement.
Do not silently move files on a read, verification, build or ordinary discovery.

Provide a read-only migration plan and explicitly acknowledged apply through the
public project lifecycle. Bind the exact project, source/metadata ownership,
bytes/modes/link topology, affected references, destination occupancy and current
locks/receipts. Refuse collisions, mixed authority, cross-boundary aliases and
cross-filesystem movement before changing any files. Preserve application bytes,
Git administration, custom instructions and independent nested projects.

Hold the canonical lifecycle lock and live namespace reservations through
revalidation and publication. Journal bounded recovery intent before mutation;
multi-file publication is recoverable, not a single atomic directory rename.
Recovery may change only still-owned exact states. Preserve concurrent or foreign
changes and report unresolved recovery explicitly. Remove legacy owned authority
only through this transaction; do not leave a second root manifest or symlink shim.

Path-bound identities and receipts become stale when their inputs change. Renew
locks and acceptance through their ordinary owners; retain historical evidence as
history and never rewrite it into a new positive receipt. Coordinate this migration
with ADR 0057's retained-layout resolver and source partition.

### Acceptance

Qualify noneditable installed create, adopt, legacy migration, update and reparent
journeys on Linux, macOS and Windows. Audit the resulting filesystem against the
owned-path and required-root-integration inventories. Exercise root/subdirectory
CLI discovery, nested independent projects, inherited catalogs, agent entrypoints,
verify/lock/plan/rebuild, worker dispatch and release policy discovery.

Prove application byte/mode/link preservation, stale-plan and destination-collision
refusal, ambiguous dual-authority refusal, interrupted publication/recovery,
concurrent-owner preservation, and refusal of stale pre-migration receipts.
Qualify genuine post-migration lock and receipt renewal, independent source review
and the full integrated release gates before closing the requirement.

## Consequences

Derived projects gain a clear framework boundary while retaining native application
layouts. This affects public discovery, configuration, templates and lifecycle
identities, so migration and end-to-end qualification are release deliverables.
The requirement remains included in 1.4.0. [ADR 0074](0074-existing-repository-delivery.md)
records the subsequent explicit delegation to implement the review recommendations
in this release, including containment through this shared context. This records
delegated implementation authority, not a claim of a separate user review of this
text. No existing release goal is deferred.

## Implementation inventory prerequisite

The current update planner combines several independent exclusion signals. A
shared projection belongs with an actual layout-plan consumer; an extraction that
is immediately flattened by its only caller adds no ownership decision. Existing
update exclusions are protection evidence, not a relocation inventory or migration
permission. A future layout plan must combine initialization-baseline and update
identities with current topology, references and application ownership before
selecting any move.

| Existing owner or signal | Established scope | Remaining containment work |
| --- | --- | --- |
| Initialization baseline and framework update bases | Finite previously materialized paths and historical byte identities | Resolve current semantic ownership, modes, links and references; a baseline entry alone does not authorize relocation |
| Catalog-import manifest and catalog update bases | Independent evidence protecting inherited authority from template replacement | Preserve exact parent provenance and application-relative path meanings; normalize implicit metadata through the shared context |
| Project generation inputs and retained-shim authority | Paths current local Components and retained execution still require | Preserve authored authority and retained application bytes, including mixed framework/application Component directories |
| Shared `ProjectContext` | Application root, explicitly declared framework root, discovery and coordination | Route remaining consumers through the same context; retain refusal of conflicting authority |
| Native bootstrap inventory | A finite contained profile with no added external adapters | It does not classify legacy canonical projects or authorize converting their baseline into a native one |
| Producer-owned locks, receipts, caches and outputs | Their own identities and lifecycle rules | Classify historical preservation, invalidation/renewal or recreation through each producer; no directory-name sweep |

The existing eligible agent entrypoint names are `AGENTS.md`, `CLAUDE.md`,
`.cursor/rules/literate-ai.mdc` and `agents/openai.yaml`. Eligibility does not
establish ownership of custom contents or require every profile to install them.
The entrypoint auditor is read-only. The README parent-attribution writer owns
only its explicit paired marker region. Neither is a general editor for shared
instructions, build files, Git-ignore rules or CI workflows.

Before migration can publish a plan, each supported profile must enumerate the
external consumers that require root files and define their exact delegates or
owned regions. Application CI, package metadata, source and product documentation
remain application content. Unresolved shared ownership, mixed directories and
unknown references block relocation; they do not create additional exceptions.
This prerequisite leaves the public migration transaction and installed/platform
acceptance above open.
