# ADR 0074: Make existing repository delivery the primary integration

- Status: Accepted under directing-user implementation delegation
- Date: 2026-11-16
- Decision owners: directing user and literate-ai maintainers
- Release target: 1.4.0
- Roadmap: SDLC-001 in `docs/roadmap/active-work.md`
- Governance: [ADR 0006](0006-significant-feature-request-governance.md)

## Context

The directing user requested a principal-engineer review of the complete tracked
repository, execution traces, release costs, worker allocation, skills and
adoption. During that review the user explicitly directed: "once you are done
with your recommendations, implmenent them as part of the current release by
adding them to the current roadmap, reconcile the current roadmap to combine
similar items and elmiinate now obsolete items, then execute on that roadmap -
that is your new goal".

This is delegated authority to implement the resulting recommendations and
reconcile current-release work. It is not a claim that the user separately
reviewed this ADR, nor approval for live allocation, publication or deployment.
The explicit implementation delegation supplies the planning decision for this
program; no additional confirmation is inferred from ADR 0006. Existing unrelated
release acceptance obligations remain in force.

The review baseline is `f34debb73b62f9fff59a138f86b3640d7be65183`. Its advertised
adoption route preserved seven native fixture files but moved their hierarchy,
including the GitHub workflow discovery path. The fixture acquired 130 reported
created files and contained 146 files outside `litai/`. The existing original
adoption owner already preserves native source, but requires a canonical project
to have been authored first. ADR 0071 describes containment but is not implemented.

Historical release evidence shows repeated native qualification costs and large
unattributed intervals. The on-demand provisioner already prevents duplicate
allocation after uncertain failures, but lacks a general lease reconciliation
and release protocol. These findings favor completing and simplifying existing
owners rather than adding parallel orchestration.

## Decision

1. Make the native repository path primary. Keep source, tests, package manifests,
   build definitions and existing forge discovery files in their native locations.
   Bootstrap original authority through a minimal public onboarding path. Framework
   authority and state live under `litai/`, with finite, explicitly owned external
   delegates. Implement ADR 0071 through a shared application-root/framework-root
   context and coordinate with ADR 0057's source ownership and recovery work.
2. Keep one deterministic policy, job and evidence core. Native tools retain build
   and test semantics. Skills provide task selection and judgment. Generation,
   inverse conversion, media and SDK features become explicit adoption profiles;
   their existing release obligations are not silently discarded.
3. Account for release time before weakening gates. Correlate candidate, job,
   attempt, worker and artifact identities; measure queue, setup, execution,
   approval and unattributed time separately. Run inexpensive authority checks
   before expensive qualification. Reuse evidence only when exact source, inputs,
   environment, test policy, artifact bytes and trust authority match. Diagnostic
   checkpoints do not become release attestations by relabeling them.
4. Extend the existing provisioner with bounded lookup/reconciliation, idempotent
   release and explicit expiry. Keep static workers as a supported backend with
   no implicit cleanup ownership. Preserve uncertain-state duplicate prevention,
   observed hardware/tool matching and separate execution authorization.
5. Publish per-cell support evidence and test skill behavior on representative
   native tasks. Static instruction checks and inventory-only platform probes do
   not establish model effectiveness or native acceptance.
6. Reconcile the roadmap without erasing evidence. Merge duplicate owners and
   overlapping execution plans; preserve distinct acceptance obligations, historical
   IDs and explicit supersession. Retire instructions that contradict this decision.
   An implementation checkpoint, published version or old green CI run does not
   close unrun acceptance on the current candidate.

The first implementation priorities are contained in-place adoption, release
measurement and candidate-scoped qualification, and complete worker lease
lifecycle. The owning program records the dependency order and pilot oracles.

## Consequences

New consumers can adopt native verification before opting into generation or a
framework-owned release process. Current consumers need a reviewed ownership
migration and fresh evidence for changed paths. Removal preserves customized and
application-owned files. The framework keeps its artifact/source/currentness,
update-conflict, independent-acceptance and bounded-execution controls.

This decision does not authorize changing live workers, moving any real consumer,
publishing a release, deploying software, accepting stale receipts, widening
resource limits, or treating simulated qualification as native success. Such
operations retain the authorization and evidence boundaries already applicable.
