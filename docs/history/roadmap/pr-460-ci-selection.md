# Historical exact CI selection repair

- **Status:** historical
- **Owning queue item:** [SDLC-001](../../roadmap/active-work.md#sdlc-001-make-existing-repository-delivery-the-primary-14-adoption-path)
- **Completion / archival evidence:** [Original selector source review](../../../verification/ci-run-selection-review.json); current combined and release qualification remain separate.

This is the original PR #460 repair and development record. The current release
owner has since extracted the collector into `adapters/github_observation.py`
and added separate tested-file and cell-coverage enforcement. Those newer owners
and their complete tests remain unchanged. Historical diagnostics and source
review do not qualify the current combined candidate or a release.

## Exact CI run selection repair

SDLC-001's qualification work and the existing RELEASE-CLOSURE-001 release owner
cover this discovered defect; no second release-readiness authority is added.
The release gate currently selects the first completed response, omitting pending
runs, while release-candidate creation accepts any successful response. Neither
selection establishes the latest workflow run or its current attempt.

A [controlled provider-response probe](../../../verification/ci-run-selection-diagnostic.json)
over a real temporary Git repository shows an older success satisfying both
selectors while another exact-head run is pending. With that other run failed,
the ordinary release gate refuses but release-candidate CI selection still passes.
The probe stops before the tag-existence check; authorization prerequisites are
simulated, and no tag, network request or publication occurs. The relevant source
is byte-identical at `8839ffc915604e72f13cfc19e8639807ffbb8059` and current main
`ebf88985be10f733dd64f469b7cd4aa685ce9083`.

Next action: review and implement one shared, bounded CI selection rule in the
existing release owner. Establish workflow, source, run and attempt identity from
validated provider metadata without assuming response order. A newer pending,
failed, cancelled or malformed run must not be satisfied by an older success.
A successful retry must remain usable; optional CI must retain its explicit
failure policy. Exercise reordered results, retry recovery, missing/ambiguous
metadata and the public release paths using local fixtures before qualification.
Native PR adoption must not inherit these selectors unchanged. Production release
publication and changes to forge protection remain outside this work's authority.

The [development checkpoint](../../../verification/ci-run-selection-development.json)
uses one validated workflow/run selector, ordered by documented workflow run
number and retry attempt. The collector accepts up to 100 workflows and 50
exact-head runs; it requests an extra row and refuses a larger inventory.
Metadata stdout/stderr use the
existing bounded process owner. Pending selection cannot regress to an older
success; optional CI retains unresolved failures while permitting a later success.
RC tagging re-observes the selected run/attempt and source/policy, then names the
captured commit explicitly. Independent review found and corrected real CLI
empty-string conclusions, unbounded collection before decoding, untyped invalid
UTF-8 and changed run-number identity across polls.

The maintained release cohort passes 24 cases in 20.433s, including seven new
public-path controls with real Git, project/release policy and actor authorization.
GitHub transport is simulated; overflow, decode and timeout controls execute
actual local child responders. Private temporary remotes receive only fixture
tags. These controls also preserve successful retry, refuse an advanced
source, and detect a changed policy even when Git's assume-unchanged stat shortcut
hides its working-tree edit. Final review, full and native qualification remain
pending; selection metadata does not establish artifact provenance.

For repositories with working required checks, the next native adoption slice
should observe and verify their exact-head CI through this corrected owner.
Native CI and branch protection retain execution and merge authority. Keep native
bootstrap unadmitted and its release-entry refusal intact. Add a separate local
runner only when earlier feedback demonstrates enough value to justify duplicate
execution; do not require another local plan/run/result lifecycle to adopt CI.
