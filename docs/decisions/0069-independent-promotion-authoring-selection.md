# ADR 0069: Select Promotion Authoring Independently of Repository Lineage

- Status: Proposed
- Date: 2026-11-08
- Decision owners: directing user and literate-ai maintainers
- Release target: 1.4.0, subject to explicit design acceptance
- GitHub issue: [#379](https://github.com/jordanhubbard/literate-ai/issues/379)
- Roadmap: planning gate for RUST-HARNESS-DEPS-001; implementation subtasks follow acceptance
- Governance: [ADR 0006](0006-significant-feature-request-governance.md)
- Approval: pending; this proposal authorizes no implementation or qualification

## Context

An adopted host records repository lineage that can supply its inherited catalogs.
A newly promoted native child also needs reviewed generation skills, workflow and
routing. Those are distinct choices: preserving the host's lineage does not imply
that its inherited authoring material matches the child's independently reviewed
qualification profile.

Issue #379 reports a preparation refusal before any model invocation. The signed
source intent, qualification profile and accepted artifacts remained unchanged,
but inherited authoring differed from the reviewed strict material shipped in the
installed framework. Editing the child afterward would invalidate the sealed
promotion audit. The refusal preserves the intended boundary.

At `bc7e56f06`, `spec accept --integrate-project` loads the host's parent selection
and passes it through `_create_promoted_project` into initialization. Explicit
parent selection materializes inherited catalogs. Implicit standalone
initialization uses shipped project templates while recording default lineage.
Promotion currently exposes no separate authoring choice before Component pins
and audit inputs are sealed.

## Proposed decision

### Make the two choices explicit

Add an optional authoring-source selection to creation of a new promoted project.
The initial supported choices are:

- `inherited`: preserve the existing explicit-parent behavior and default.
- `framework-template`: use the reviewed forward-generation authoring closure
  shipped in one exact noneditable framework distribution.

Effective catalog provenance must attribute each selected role to its actual
supplier; overridden bytes must not remain attributed to an inherited parent.

The choice changes authoring provenance, not repository genealogy. Preserve the
host's recorded parent selection, resolved lineage and signed accepted intent.
Ordinary Flavor selection and its domain/build semantics remain under their
existing authority. The operation selects material for a new audit; it does not
alter an existing child, qualification or accepted audit.

The framework-template choice covers the generation skills, workflow and routing
needed by the selected Component recipes, including their complete declared
authoring dependencies. Reject incompatible Flavor references, missing roles,
duplicate destinations, unsupported versions and incomplete closures. Do not mix
unreviewed inherited fragments into a selected shipped closure or silently change
Flavor semantics to make the selection fit. Arbitrary directories, environment
variables and ambient installed packages are not authoring suppliers in this
initial scope.

The selector name does not establish that its material is strict or qualified.
The independent qualification profile still compares the actual effective bytes
and requirements, including fallback policy.

### Plan and acknowledge the exact authoring closure

Expose the choice in the public acceptance/promotion flow before target creation.
A read-only plan identifies the mode, exact supplier distribution, every effective
role/path/content identity and size, complete dependency closure, lineage,
accepted specification and qualification-profile bindings. Reuse the existing
bounded input readers and currentness owners. Planning performs no generation,
build, test, provider call or target mutation; missing material refuses rather
than installing or retrieving a substitute.

Application requires acknowledgement of the reviewed plan identity. Revalidate
the supplier, complete authoring closure, lineage, intent, profile and target
reservation before staging and publication. A changed supplier or role, incomplete
selection, changed profile, stale acknowledgement or foreign target refuses.
Apply through the existing promotion publication/recovery owner, preserving
foreign bytes and attributable failure evidence. No parallel journal protocol is
introduced.

### Bind provenance before sealing a new audit

Materialize the selected closure before computing Component authoring references,
initial locks, recipes or promotion audit inputs. Bind both repository lineage
and the separately selected authoring provenance, including supplier and closure
identities, in the new audit and its qualification inputs. Reopening and later
lock/currentness checks must verify the same complete selection under current
custody; a digest or selector label alone supplies no ownership or execution
authority.

Preserve published v1 record meanings and existing default behavior. Use a new
versioned audit/binding form wherever the current closed contracts cannot express
the independent selection; support its complete read-back before producing it.
Do not add a field to a frozen schema, silently reinterpret old audits, or upgrade
their evidence in place. A new child revision follows the existing independent
qualification and parent-switch rules in ADRs 0062 and 0066.

### Keep acceptance and execution separate

Authoring selection does not change the signed specification, accepted artifacts,
independent expected results, qualification profile, model choice, runtime target,
resource budgets, provider/egress policy or containment requirements. It grants no
model invocation, source replay, importer admission, retirement, parent switch,
release publication or downstream framework-pin update.

The actual native qualification must still pass its ordinary independent builds,
execution, import/export and currentness gates. Preserve the reported failed
preparation as a failure; a successful new plan alone does not qualify the child.

## Acceptance required after design approval

- Prove unchanged default inheritance and existing v1 audit/read-back behavior.
- Through a fresh installed public CLI, preserve explicit host lineage and signed
  intent while selecting the exact reviewed shipped authoring before a new audit.
- Independently verify the effective skills, workflow, routing and dependency
  closure, with the original qualification profile and accepted artifacts intact.
- Refuse stale plans, changed suppliers/roles/profiles, missing or conflicting
  dependencies, unsupported provenance, foreign targets and late mutation before
  execution or publication; preserve original and concurrent bytes.
- Reopen the new binding/audit and current locks, then complete actual native
  child qualification. Post-audit edits must continue to invalidate the audit.
- Obtain independent source review, current canonical authority records, complete
  source/installed/platform gates and exact integration verification. Protocol
  fixtures and preparation success remain distinct from native acceptance.

## Alternatives and consequences

Changing the host's parent revision couples genealogy to authoring and does not
solve a current root whose developer authoring is intentionally different.
Changing the canonical root globally would alter unrelated inherited behavior.
Editing accepted child files afterward would discard the sealed boundary.

An explicit selection adds provenance and versioned read-back work, but retains
the original inheritance behavior and keeps the independently reviewed intent and
qualification requirements authoritative. Implementation waits for the directing
user to accept or amend this proposed decision.
