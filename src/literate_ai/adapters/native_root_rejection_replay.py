"""A fixed negative Rust protocol predicate, NOT full historical acceptance.

Call only after trusted policy/run/ledger/request/rejection binding verification.
The supplied identity must be that exact joined rejection's
native_execution_evidence_identity. The caller must separately reopen historical
source, build/test/export/package custody and all six NativeRootPackageBinding
coordinates. No successful StandardRootIntegrationEvidence is fabricated for a
rejected package, and no decoded record restores retry or execution authority.

This checks retained successful-process assertions, exact raw streams, executable
and tool records, current trusted oracle inputs, exact case inventory/capabilities
and at least one differing result value. It does not authenticate the producer or
prove that an untrusted archive's asserted process actually ran.
"""

from literate_ai.adapters.rust_library_harness_execution import (
    _refuse,
    _result_values_differ,
    _verify_rust_harness_execution_protocol,
)


def _require_differing_results(raw, oracle):
    if _result_values_differ(raw, oracle) is not True:
        _refuse("archive_result_matches")


def verify_closed_rust_harness_value_rejection(
    reader, identity, *, oracle, library_alias, surface
):
    """Require a complete values-only rejection; never select a relax mode.

    Matching results, process failure, malformed protocol, wrong case IDs or
    capabilities, missing payloads and changed trusted verifier custody refuse.
    Expected values always come from the caller's current trusted oracle.
    """
    return _verify_rust_harness_execution_protocol(
        reader,
        identity,
        oracle=oracle,
        library_alias=library_alias,
        surface=surface,
        _require_result=_require_differing_results,
    )
