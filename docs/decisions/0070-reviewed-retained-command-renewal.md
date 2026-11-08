# ADR 0070: Renew Explicit Retained Commands Through Reviewed Readmission

- Status: Proposed
- Date: 2026-11-08
- Decision owners: directing user and literate-ai maintainers
- Release target: 1.4.0, subject to explicit design acceptance
- GitHub issue: [#366](https://github.com/jordanhubbard/literate-ai/issues/366)
- Roadmap: planning gate beside ADOPT-BASELINE-COMMANDS-001; renewal subtasks follow acceptance
- Governance: [ADR 0006](0006-significant-feature-request-governance.md)
- Approval: pending; this proposal authorizes no implementation or execution

## Context

A Makefile's default target can print help and return zero. The retained detector
currently proposes `make -f Makefile` as a build command. That command's successful
execution does not establish that it compiled an application. Guessing another
target is unsafe: a target named `build` may provision the machine.

The installed public CLI from `cad30c4e7` reproduces this distinction with a native
fixture. Its default help target exits zero without an executable; explicit
`build-all` compiles an executable that runs successfully. A read-only initial
`onboard adopt --root-plan` can select that exact command, changes the plan identity
and leaves source unchanged. Neither planning operation runs a target or setup.
The retained diagnostic is described in [issue #366's evidence](https://github.com/jordanhubbard/literate-ai/issues/366#issuecomment-6723842204).

That initial-selection support belongs to #207. Existing post-adoption
`project retained-harness readmit` freshly inspects source and can preserve an exact
previously admitted stage with `--retain-stage`; it cannot select a new command.
Renewal changes executable authority and historical evidence, so it needs a
separate reviewed transition rather than editing inventory JSON or old receipts.

## Proposed decision

### Select exact commands without inferring their meaning

Extend the existing retained readmission flow with an explicit, versioned command
selection. Reuse initial adoption's phase, command, working-directory and evidence
validation and its per-root ownership rules. Bind each selection to its actual
retained wrapper or refined Component; reject ambiguous owners, duplicate phases,
indirect paths, foreign evidence and unsupported contexts.

Retain every unselected admitted phase. A request to remove a phase is unsupported
by this selection and refuses; an absent override does not remove it. Do not add
an automatic target fallback, execute source to discover
targets, or treat `make -n` as a safe read-only inspection. Selecting a command
does not prove that its effects are non-provisioning.

Keep detected commands and their origin visible in the plan. A detected default
target has unknown compilation coverage. Reports distinguish the exact command's
exit status from compilation or artifact claims. A passing help-only command must
not become evidence that an application compiled. This rule also applies to
explicit commands: their spelling alone proves no coverage.

### Review and bind a read-only renewal plan

Planning performs no target invocation, installation, provider call or mutation.
It binds the exact old and proposed commands, source membership and bytes,
supporting build files, working directories, current layout and ownership,
project/conversion authority, affected Component bindings and locks, current
inventory/wrapper/policy bytes, worker selection and execution bounds. Show the
retained and replaced phases and the prior evidence that will cease to be current.

Application requires acknowledgement of that exact plan and the existing current
host-execution authorization. An acknowledged command selection grants no separate
permission to provision, fetch dependencies, contact providers or weaken sandbox,
egress, containment, toolchain or resource policies. Missing prerequisites follow
their existing authorized provisioning owner; they are not guessed Make targets.

Revalidate all bound inputs under the canonical lifecycle lock immediately before
execution and publication. A changed command, source, supporting file, ownership,
layout, worker or authority refuses the stale plan before it can earn admission.

### Reuse readmission and preserve evidence

Use the existing retained readmission owner for disposable-source baseline and
wrapper-parity execution, current authority validation and publication. Extend its
transaction and recovery where necessary; do not introduce a parallel receipt or
journal authority. Renew each affected inventory, wrapper, policy and Component
binding through its existing owner. Preserve concurrent edits and foreign nodes;
rollback restores only exact bytes and nodes still owned by this attempt.

Preserve the original source, historical command definitions and all old receipts
and failures. Changed command identities invalidate their use for current
execution, packaging and lifecycle admission. New passing command results do not
rewrite old coverage, advance conversion stage or create semantic acceptance.
Ordinary fresh locks and receipt/admission gates must establish currentness.

Existing projects and requests without a command selection retain their published
v1 behavior and identities. Use a new versioned plan/binding wherever closed
contracts cannot represent the transition; support complete read-back before
publishing it. Never reinterpret a saved v1 plan or edit an old receipt in place.
Selected layouts remain governed by ADR 0057 and its qualification requirements.

## Acceptance after design approval

- Through a fresh noneditable installed public CLI, retain the help-only default
  result with its actual scope; explicitly select a compiling, non-provisioning
  fixture command and verify the produced native executable's behavior.
- Apply initial selection and post-adoption renewal separately. Reopen their exact
  bindings, renew locks and genuine retained receipts, and reject the previous
  receipt for changed commands while preserving its original bytes.
- Verify unselected phases remain, unsupported omissions refuse, and neither
  planning nor an unacknowledged or stale request invokes setup or compilation.
- Refuse changed commands, supporting build files, source, layout, owners, locks,
  policies and worker bindings. Prove failed execution, interrupted publication
  and concurrent replacement preserve source, old evidence and foreign bytes or
  report precisely unresolved recovery state.
- Preserve default discovery, initial #207 behavior, existing v1 readmission and
  its refusal controls. Complete independent source review, current authority
  records, full source, installed/native and integrated release qualification.

## Consequences

Operators can deliberately renew retained command authority without changing source
merely to influence target discovery. This adds a reviewed execution transition,
not a heuristic compiler detector. Initial onboarding remains separately qualified;
post-adoption renewal remains unimplemented until the directing user accepts or
amends this proposal and its implementation work is recorded.
