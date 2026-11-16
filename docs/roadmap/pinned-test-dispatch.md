# Pinned test dispatch

- **Status:** active
- **Owning queue item:** [TEST-CACHE-001](active-work.md#test-cache-001-complete-dependency-bound-qualification-reuse)
- **Completion / archival evidence:** pending combined qualification and remaining acceptance
- **Release target:** 1.4.0 under [ADR 0074](../decisions/0074-existing-repository-delivery.md)

## Current behavior and observed gaps

`test_checkpointing.run_gates` and `run_unittest_suite` already use
`PinDispatchService`. `_try_framework_pins` binds the framework TCB and documentation
authority, and `_resolve_unittest_pin` includes selected test-source bytes. This
supersedes the historical description of both paths as purely name/file based.
The [historical design and queue record](../history/roadmap/pinned-test-dispatch-before-sdlc.md)
remain available; their present-tense implementation claims are not current guidance.

A controlled unmanaged native fixture did expose a narrower fallback defect:
without resolved project authority, a failed run's retry skipped a previously
passing native test after its input changed. The branch now reruns checks when
that authority is unavailable. It preserves diagnostic progress without treating
a suite name or unchanged test module as a complete dependency identity.

A real `make -n release-check` also invoked the recursive checkpoint wrapper and
recorded unexecuted subcommands as passing. The branch refuses to record or clear
checkpoint evidence under Make preview, query and touch modes. The regression
uses real Make and includes an ordinary failing run to prove execution still works.
These controlled observations are development evidence, not production incidents
or release attestations.

## One ownership model

Native build tools retain source/object/link dependency semantics. The existing
authority graph supplies reviewed Component, Flavor, skill and framework inputs;
`pinned_test_dispatch` owns scheduling decisions; existing receipt and qualified
release-file owners retain results and artifact bytes. Skills explain the choice
and exceptions. Do not add a second dependency tracker, receipt or mutable tested
flag to save a repeated command.

A content hash establishes identity only for the inputs it covers. Result reuse
also needs the exact ordered check plan, native target and accelerator requirements,
toolchain and dependency closure, declared execution inputs, harness identity,
artifact bytes and applicable policy. Unknown inputs mean rerun. Revalidate
current signatures, trust/revocation and validity periods when consuming evidence;
a previously trusted signature or old platform observation is not permanent approval.

A generated Component remains distinct from an original-source repository.
Generated-source admission events and independent acceptance are retained for the
former. Original/native projects use their existing source and command authorities;
they do not require generation merely to run a native check.

## Artifact reuse before result reuse

The release gate sequence now shares a wheel selected under an exact commit.
`wheel-check` still runs its complete qualification. Successful selection uses the
existing qualified-release-files manifest; competing different bytes cannot replace
it. Later prefix installations snapshot and hash the selected file, check revision,
version and embedded origin, then run their own behavior checks. They expose the
wheel digest in their results. Requalification uses the selected bytes again.
The independent source-install check and native CI installation coverage remain.

This eliminates two repeated source-to-wheel installation builds in the ordinary
release sequence. It does not eliminate dependency setup, installed checks, live
inference or platform runs, and its wall-clock saving has not yet been measured
on a clean full framework candidate. It does not enable pre-CI result reuse.

Repair resumes remain diagnostic. Preserve the required clean complete release
pass until the result-reuse contract below is qualified and integrated with the
release authority owner. Do not optimize a no-op resume by relabeling it as a
fresh release or bypassing final currentness checks.

## Remaining acceptance and historical requirement mapping

- [x] Existing closure-change and cross-pin controls exercise the shared dispatch
      owner (`tests/critical/test_pinned_test_dispatch.py`).
- [x] Real native and Python fixtures reject reuse when project inputs are unknown.
- [x] Real Make preview/query/touch controls cannot create success evidence or clear
      pending repair progress; normal execution still records actual outcomes.
- [x] Two real fixture prefix installations consume identical retained wheel bytes;
      concurrent replacement, changed bytes, wrong origin, stale revision and dirty
      source are refused. The fixture is not a qualified framework distribution.
- [ ] Demonstrate complete dependency coverage for each reusable pipeline, including
      runtime-read inputs, toolchain/environment changes and test-policy changes.
      Unknown or newly discovered dependencies always re-enter execution.
- [ ] Bind composed/integration pipelines to all participants and prove changes to
      any participant invalidate reuse without opening unrelated admitted siblings.
- [ ] Complete native build/test, Standard lifecycle and CI adoption of the shared
      receipt/dispatch owner where it adds value; do not wrap a native build cache
      with a redundant dependency graph.
- [ ] Preserve generated-source admission as the generation trigger. Prove no
      unrelated generated artifact is scheduled without its admission event.
- [ ] Qualify existing committed receipts and packaged SBOM/provenance as exact
      tested-pin evidence, including changed pipeline, revoked trust, expired
      evidence and artifact substitution. A provenance property alone is not proof.
- [ ] Exercise source mutation during execution, interrupted writes and concurrent
      consumers. Protect exact results without accepting a mixed candidate.
- [ ] Distinguish bounded infrastructure retry from assertion failure and flakiness;
      retain every attempt and require a real successful run. No silent retry-to-green.
- [ ] Run the complete installed framework and native platform qualification for
      this candidate. Source/fixture passes alone cannot close this requirement.
- [ ] Measure cold, warm development resume and fresh release paths separately.
      Compare elapsed wall time, actual runner occupancy, duplicate jobs and manual
      intervention; quantify unknown time. Keep existing assurance while reducing
      repeated work before claiming an improvement.

These rows retain the historical closure, no-input-read skip, admission event,
receipt propagation, shared entrypoint, no-op cost, completeness, composition,
concurrent-writer and infrastructure-retry requirements. The no-input-read and
no-op goals are conditional on complete admitted inputs and current trust; they
cannot authorize skipping required currentness or clean release checks.
