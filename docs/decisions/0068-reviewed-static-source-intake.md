# ADR 0068: Review exact source for local static intake

- Status: Accepted under directing-operator delegation
- Date: 2026-11-08
- Decision owners: framework maintainers and the directing operator
- Roadmap: [SOURCE-STATIC-INTAKE-001](../roadmap/active-work.md#source-static-intake-001)
- Issue: [#368](https://github.com/jordanhubbard/literate-ai/issues/368)

## Context

Default inventory conservatively excludes credential-shaped JavaScript and
TypeScript content. A variable-backed `clientSecret` property and an explicitly
public fixed local-test value both reproduce that exclusion. A property-name
control derives successfully. Input source is never executed and no model is
called. The sensitive-content heuristic on current upstream main matches the
reviewed installation.

A directly authored library with a valid ordinary lock is separately refused by
`spec qualify` with `qualification.authority_projection_required`. Qualification
requires accepted source-promotion evidence. Direct Component authoring cannot
supply this evidence. The original source, conservative inventory, origin
attestation, contract drafts and independent verifier remain preserved.

The current inventory identity includes classification. Changing a `sensitive`
entry to `source` would change the snapshot and break origin and qualification
bindings. A permitted analysis view must preserve the canonical inventory.

Current source result bundles write version 5. Asset-free promotion provenance
writes version 3; reviewed-asset provenance writes version 4. Readers accept
versions 2, 3 and 4. Its exact field sets reject undeclared additions.
The forward generation allowlist excludes the provenance subtree and accepts only
specifications, Component intent, reviewed Flavors, forward skills, workflow,
routing and project configuration. These properties must remain true.

## Decision

Add an explicit signed permission for local static analysis of exact reviewed
files. Preserve the default classifier and original inventory. Scope the first
implementation to JavaScript and TypeScript source files and the static translator.
Keep normal signed specification review, explicit policy opt-in when selected, source promotion and regenerative
qualification mandatory.

### Review record and commands

Add a typed `source-static-intake-review@1` record with a distinct signing purpose.
It contains the original inventory identity, verified origin-attestation identity,
an explicit sorted file set with content identities and review reasons, reviewer,
the fixed purpose `local-static-intake`, review authority, and signature metadata. It contains no
source excerpt, credential value, private command, glob or filesystem root.

The named reviewer attests that every selected file is credential-free code
and that any fixed local-test value is deliberately public. The record explicitly
binds human or authorized-policy review authority. Human review remains the
default. Policy review requires an explicit actor and authority selector and
separate caller opt-in at derivation and acceptance; a record never grants its
own permission. An authorized-policy review never represents operator security
acceptance. The tool verifies
identities and custody; it does not infer that arbitrary credential literals are
public from their spelling. Default exclusion remains in force without a valid
review. A signature binds the reviewer's assertion; it cannot prove that an
arbitrary literal was deliberately public. The reviewer must never approve
actual credential material. Hard-denied private keys, sensitive filenames and
unsupported classes remain refused even if a reviewer tries to include them.
The granted operation stays local static analysis with no model egress.

Use two CLI stages:

1. `spec intake plan SOURCE --file PATH ... --attestation ATTESTATION --trust-key KEY`
   creates a read-only plan. It reports paths, classifications, content identities,
   review scope and blocking conditions without printing sensitive matches.
2. `spec intake approve PLAN --source SOURCE --attestation ATTESTATION --actor ACTOR --reason REASON --key KEY
   --acknowledge --expect-plan ID --output REVIEW` recomputes the exact plan,
   verifies origin and writes the signed record atomically to a new regular file.

Use the same trusted local key authority as the origin attestation in the initial
implementation. The trust root comes from the caller's key argument, not from the
review record. Reuse canonical identity and signing primitives with domain
separation from source attestations and specification reviews.

An explicit set of 1 to 32 ordinary relative source paths is supported. Reject
duplicates, absolute paths, traversal, undeclared files, unsupported languages and
stale identities. Typed JSON readers reject duplicate keys and unknown fields;
reviewer and reasons are bounded non-empty strings. The review record is limited
to 64 KiB. Reviewed behavioral reads
use the existing direct-file custody reader and the inventory's 2 MiB source-file
limit. Preserve ancestor, symlink and Windows reparse checks. Sensitive filenames,
key-file extensions, private-key material, binary, generated, minified and oversized
content remain ineligible. Repeat these hard exclusions independently because the
current inventory returns `sensitive` before testing several other classes. A
sensitive classification alone must never hide another ineligible condition.
This work does not broaden the inventory's default read
policy or address unrelated cache ingress. Require the file to satisfy the remaining
ordinary source classification after only the credential-content heuristic is
set aside. Do not relabel tests, configuration, assets or documentation as runtime
source through this permission.

### Static derivation

`spec derive --intake-review REVIEW` verifies the review and original attestation
against a freshly inventoried source before admitting any excluded file as
behavioral evidence. The option is valid only for the local static translator.
Combining it with model translation or model-egress authorization is rejected.

Keep the original `SourceInventory`, policy identity, classification, file hashes
and snapshot identity unchanged in the result. An ephemeral view admits only the
explicit reviewed files to existing inert static analysis and lexical symbol
collection. Other excluded files remain excluded. The view is not an alternate
inventory and is never used to compute the source identity.

Write result bundle version 6 with the exact review and identity in a separate
typed field. The source request and evidence still refer to the original snapshot.
Retain the original sensitive-path report. The static translation record continues
to have no model intelligence or journals. Do not serialize raw reviewed source or
literal values into this new record or admit them to forward generation.

### Acceptance and permanent custody

Normal `spec review` remains the specification acceptance point. `spec accept`
must re-inventory the source, reverify origin and review signatures, check every
reviewed path and digest, and bind the exact review identity to the promotion.
Missing or malformed review is rejected when the bundle declares this route.
The existing source fingerprint guard remains active through materialization.

Write review-bearing promotion-provenance version 5 with an exact review reference and
a bounded private `static-intake-review.json` sidecar. Retain the original snapshot,
reviewed SpecificationSet, normal signed intent review and generation-input audit
references. Materialize no original implementation. A review reference points to
one fixed sidecar name and its exact content identity, with no arbitrary locator.

Derivation and acceptance verify the signature using their explicit trust-key
argument. Add a public `spec qualify --intake-trust-key KEY` for this reviewed
route, requiring it when the promoted source declares a static-intake review.
Do not reuse the hidden legacy qualification signing-key option. Measured
qualification verifies the review signature before any generation and again
before admitting the qualification, using this explicit operator-held key. Qualification reopens the
sidecar, checks scope and matches it to the promotion's original snapshot. When
live source is available, its inventory must still match. Qualification never
creates or edits a review. The permission supplies no qualified state and
expresses no execution, cache-publication or external-write authorization.

Persist a bounded `source-static-intake-validation@1` record at successful
qualification. It contains the exact original source, promotion reference, review,
qualification lifecycle result and trust-key identities, plus the fixed verified
purpose. The key identity is a digest, never key material. Preserve it under a
fixed private provenance location, include it in the retained evidence archive,
and add its content identity to the qualified projection's existing evidence set.
The validation refers to the completed qualification result; that result does not
refer back to this later validation, so this creates no identity cycle.
Extend typed `VerifiedSourcePromotionEvidence` so the normal qualification
transition requires this exact validation for a promotion declaring a review.
Recheck source, review, promotion and key custody across the measured lifecycle;
write no validation or qualified transition after an intervening change.

Later library consumers must work without the operator's private HMAC key. They
reopen the review and validation records, validate exact schemas and identities,
and require all of the following: the current trusted qualified projection binds
the exact promotion reference; that reference binds the review; the projection's
evidence set includes the validation identity; the validation binds that same
source, promotion, review and current qualification lifecycle result. A missing
record or mismatch fails closed through normal source-promotion verification.
Requalification or recertification must create fresh validation for its new
qualification result rather than reusing an earlier validation.

This uses the existing trusted authority ledger, source pins and retained-library
admission boundary. Current Standard lifecycle runs are content-addressed evidence;
they are not HMAC attestations of this review. The review signature is verified
when the trusted qualification transition is created. Later consumers check its
durable binding and do not claim to independently verify an HMAC without its key.
A bare sidecar, self-declared reviewer or rewritten untrusted ledger is insufficient.
This capability does not introduce a new trust root or make an arbitrary project
ledger externally trustworthy. Ship no secret in Git, the source cache, a wheel,
an image or a generation request.
The review, sidecar and qualification validation remain private provenance. Add
no forward input kind for them. Do not put their identities in the declared
forward generation inputs or the generation audit tree; their qualification
binding lives in the authority projection and private evidence. Existing source-exclusion audits must reject original paths and bytes, and
generation request inspection must show no review payload, original implementation
or private oracle. Authored public contracts remain the generation authority.

### Compatibility and distribution

Keep frozen versions 1 through 5 of source result bundles and versions 2, 3 and 4
of promotion provenance readable through explicit legacy readers. Never reinterpret
their absent review field as a reviewed permission. Default legacy intake and
qualified evidence retain their existing behavior and identities. Only review-
bearing bundles use version 6 and review-bearing promotion uses version 5, with
schema-specific exact field sets. Ordinary writers retain bundle version 5,
asset-free provenance version 3 and asset-bearing provenance version 4. A reviewed
source that also declares ordinary immutable assets retains exact asset bindings
in its new version 5 provenance. The permission cannot admit a sensitive asset.

Do not rewrite old qualified projects, locks, cached source or decisions. Verify
that new readers accept unchanged legacy evidence and reject malformed new review
records. Old runtimes may reject the new provenance version; do not conceal this
by writing old schema identifiers with new fields.

Build an approved clean non-editable distribution for the changed SDK. Bind the
new authentication child to it through the reviewed lifecycle flow before
qualification. Upgrade the consuming parent only through an explicit Standard
rebind plan and apply after local distribution acceptance. Prove that its existing
existing qualified providers retain their identities and that legacy verification still
works. Complete the consuming application and image workflow after integration.
Commit, push and publication permissions remain separate.

## Planning and execution order

Issue [#368](https://github.com/jordanhubbard/literate-ai/issues/368) records
the portable reproduction. The directing agent accepted the bounded planning
decision under the operator's existing authorization after the prior proposal
and compatibility review. No independent maintainer approval or operator
security acceptance is implied. Record SOURCE-STATIC-INTAKE-001 before source
implementation.

Implement typed review/signature validation and inert planning first, then static
admission, versioned bundle/promotion custody, qualification verification and
legacy readers. Complete managed, documentation, skill, layout and export checks.
After the separately approved local commit, verify the installed clean wheel using
public CLI fixtures. Recover the unchanged authentication source through normal
review, promotion, two clean generations, separate admission, real configured
adapter acceptance and consuming integration. The independent verifier is already
prepared and must remain a private acceptance input.

## Acceptance

Positive fixtures cover a variable-backed credential property and an explicitly
reviewed public local-test value. Their original sensitive inventory and snapshot
remain exact. The field-name control continues to work without a review.

Reject unreviewed or changed files, stale origin, wrong key or signing purpose,
altered signatures, missing sidecars, altered review references, traversal, globbing,
duplicate paths, ancestor links, reparse points, unsupported classes and bounds.
Prove that admitting one file does not admit another excluded file. Reject model
translation and model-egress flags on the reviewed route. No fixture source runs.

Installed CLI acceptance must exercise plan, approval, static derive, ordinary signed
intent review, explicit policy opt-in when selected, accept, qualification and later qualified-library consumption. Check
source fingerprints, exact profile and lock identities, first actual generation
requests, clean rebuild independence, separate admission and custody reopen.
A clean consuming container must verify the qualified library without the private
review key; swapped review, validation or promotion records must fail, including a validation
from another source, review, key identity or qualification result. Reopen every
record through the bounded custody reader. Inspect the retained archive and the
current projection rather than treating a CLI success flag as sufficient. Legacy bundle and
promotion fixtures must still verify without mutation. New
malformed records and attempted use through old readers fail with typed errors.

## Consequences and rejected alternatives

This adds an operator review step and private provenance, preserving conservative
default intake. It avoids special-casing test strings, editing application property
names to evade the classifier, replacing source identity with a sanitized copy,
or manufacturing qualification projections. A general native-authored qualification
API is deferred because it expands a different authority lifecycle. Automatic
language-aware disproof of safe environment references is a separate possible
improvement and does not solve the reviewed public-literal case by itself.

The accepted scope preserves the original source snapshot and conservative
defaults. Changes that weaken its admission, no-egress or qualification boundary
require a new planning review before implementation.
