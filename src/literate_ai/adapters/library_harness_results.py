"""One exact result protocol for independently owned library harnesses."""

from __future__ import annotations

import json

from literate_ai.contracts.product_json import product_json_values_equal


class LibraryHarnessResultError(ValueError):
    """A harness did not return every exact, finite expected result."""


def _pairs(rows):
    value = dict(rows)
    if len(value) != len(rows):
        raise LibraryHarnessResultError(
            "library acceptance emitted duplicate JSON fields"
        )
    return value


def _nonfinite(_value):
    raise LibraryHarnessResultError("library acceptance emitted nonfinite JSON")


def validate_library_harness_results(oracle, content, *, oracle_identity):
    """Return checked case rows as data, without recording or granting acceptance.

    The execution owner supplies bounded output and retains its current oracle,
    input, artifact and process custody through actual evidence publication.
    """
    try:
        result = json.loads(
            content, object_pairs_hook=_pairs, parse_constant=_nonfinite
        )
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise LibraryHarnessResultError(
            "independent library acceptance emitted invalid JSON"
        ) from exc
    raw_cases = result.get("cases") if isinstance(result, dict) else None
    if (
        not isinstance(result, dict)
        or set(result) != {"schema", "cases"}
        or result.get("schema") != "literate-ai/library-acceptance-results@1"
        or not isinstance(raw_cases, list)
    ):
        raise LibraryHarnessResultError(
            "independent library acceptance emitted an invalid protocol"
        )
    observed = {}
    for item in raw_cases:
        if (
            not isinstance(item, dict)
            or set(item) != {"case_id", "capability", "result"}
            or not isinstance(item.get("case_id"), str)
            or item["case_id"] in observed
        ):
            raise LibraryHarnessResultError(
                "independent library acceptance emitted a malformed case"
            )
        observed[item["case_id"]] = item
    expected = {item.case_id: item for item in oracle.cases}
    if set(observed) != set(expected):
        raise LibraryHarnessResultError(
            "independent library acceptance did not run every exact case"
        )
    if oracle.identity != oracle_identity:
        raise LibraryHarnessResultError("library acceptance oracle changed")
    for case_id, case in expected.items():
        item = observed[case_id]
        try:
            matches = product_json_values_equal(item["result"], case.expected_result)
        except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
            raise LibraryHarnessResultError(
                "library acceptance result is not finite product JSON"
            ) from exc
        if item["capability"] != case.capability or not matches:
            raise LibraryHarnessResultError(
                f"independent library acceptance result differs for {case_id!r}"
            )
    if oracle.identity != oracle_identity:
        raise LibraryHarnessResultError("library acceptance oracle changed")
    return observed
