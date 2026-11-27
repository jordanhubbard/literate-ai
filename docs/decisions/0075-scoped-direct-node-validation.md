# ADR 0075: Add an explicit scoped profile for direct Node runtime observations

- Status: Accepted as written by the directing user on 2026-11-19
- Date: 2026-11-19
- Decision owners: directing user and literate-ai maintainers
- Related work: [sealed Node SDK composition, #452](https://github.com/jordanhubbard/literate-ai/issues/452)
- Roadmap: existing sealed Node SDK composition item under #452; scoped-profile implementation and acceptance subtasks admitted
- Governance: [ADR 0006](0006-significant-feature-request-governance.md)

## Context

The original two-provider/root-subpath typed SDK lifecycle remains unqualified.
Its native matrix failed after 2,008.415 seconds when an ordinary provider BUILD
grant expired. A separately reviewed sampling diagnostic reproduced that expiry
after 1,918.561 seconds with complete cleanup. Neither run permits extending the
ordinary 30-minute BUILD policy or renewing an uncertain operation.

Node toolchain revalidation currently launches a new bounded runtime probe.
That child in turn polls the active liveness owners. A historical active-cohort
profile shows substantial repeated owner validation during one such probe; the
current sampler also observes this path. Current configuration-only profiles
show one snapshot validation per guard call, rather than multiplied snapshots
inside those guards. These observations identify a design candidate, not an
established optimization benefit or native expiry margin.

A binary digest alone cannot replace the existing runtime observations. The
effective environment, working directory, loader behavior and mutable runtime
dependencies can affect what a direct executable does. The existing detached
Node witness is a file observation, not runtime provenance or execution authority.

## Proposed decision

Add an explicitly selected, versioned validation profile for a narrowly supported
direct native Node invocation. Preserve the existing probe-at-each-boundary profile
as the default. Manual identities, callbacks and current typed acknowledgements
retain their existing behavior. An acknowledgement for the new profile must bind
its exact validation policy; existing intent must never silently select it.

The new profile would make one original bounded runtime probe at scope entry and
another at successful scope close. Intermediate checks would use fresh validation
of the original tool and a separately qualified, closed launch-input readset.
This deliberately changes when runtime behavior is observed; it is not presented
as a transparent binary-hash cache. Approval accepts this proposed temporal policy,
subject to all implementation and native acceptance gates below.

An explicitly selected Flavor/profile owns the backend; do not infer eligibility
from the host OS or silently change validation profiles. The first backend targets
the existing macOS direct-Node SDK cell. Eligibility
requires exactly one absolute resolved native executable, with matching original
launcher/runtime paths and digests and no wrapper, alias or extra command operand.
The backend must account explicitly for effective environment, working-directory
assumptions, loader inputs and mutable non-system runtime dependencies. It must
state its operating-system trust boundary. Unsupported or unclosed launch inputs
remain on ordinary probing before enrollment; they cannot acquire this profile
through an identity-only digest, environment normalization or a caller assertion.
Any ordinary-profile fallback retains its actual ordinary identity; an explicit
new-profile request may instead refuse. Never label an unenrolled or unqualified
operation as using the scoped profile.
Do not claim the installed Node toolchain is eligible until that backend is proven.

Only an original successful bounded probe, bracketed by original metadata and
binary-custody checks, may create private original-owner membership. Exact input
and policy identities participate in that membership. A forged, copied, reentrant,
foreign or retired observation refuses. Once enrolled, failed validation cannot
fall back to an ordinary probe or acquire a replacement observation implicitly.

Keep execution authorization separate. Every original liveness, owner, revocation,
expiry, cancellation, capture and publication fence remains required. Removing an
introspection child must not accidentally remove the surrounding required owner
checks. A final original runtime probe follows callback-bearing work; original
byte/ancestry, metadata and finite membership checks close after that probe before
success can escape. Failed close, missing evidence or uncertain cleanup withholds
success and retires the original observation while preserving the primary error.

Use bounded scopes tied to the original enclosing operation and its existing
deadline, with no automatic renewal. Retained observations and launch-input
storage count against existing resource limits; do not enlarge those limits to
fit the implementation. Copied contexts cannot extend scope lifetime. The profile
grants no command, model, network, source or verifier permission.

## Acceptance and consequences

Independent state/security review must accept the precise backend and lifecycle
before any native qualification. Tests must exercise original probe provenance;
environment/CWD drift; binary, mode, ancestor and restored-mtime replacement;
loader/dependency or launchability change; forged/copy/foreign/reentrant/retired
observations; original probe/closing failures; cancellation and resource cleanup;
and owner or grant loss previously detected during process polling. A controlled
native dependency or launchability change must demonstrate the backend's boundary.
Existing wrapper/default-profile tests and identities must remain valid.

Measure actual probe counts and full original lifecycle time, with unchanged
grants and clocks. Qualify the genuine serial two-provider SDK, packaged root and
subpath runtime/type acceptance and the separate installed distribution. A small
guard benchmark is insufficient. Retain all earlier failures and per-profile
limits; do not relabel an old or different-profile test as passing. Browser,
other-platform, model-backed CLI and downstream cutover gates remain separate.

This proposal authorizes no implementation while its status is Proposed. Acceptance
would authorize planning and implementation under #452, not profile activation,
source-authority retirement, a policy-limit increase, publication or deployment.
If its closed launch-input boundary cannot be established, retain ordinary probes
and report that result rather than weaken the profile to obtain a passing test.

## Directing-user acceptance

On 2026-11-19 the directing user explicitly stated, "I agree with ADR0075 as
written." The decision above is accepted without amendment. Planning and
implementation under #452 may proceed through the linked work queue. Acceptance
does not activate the profile, enlarge limits, retire source authority, publish
or deploy anything, or establish native/installed qualification.
