"""Closed origin dispatch from independently reviewed binding bytes first.

Unknown, mixed and unsupported schemas refuse before credential lookup, transport,
provider/tool discovery or output operations. Legacy v1 keeps its actual handler.
"""

import json
import math
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.retained_cargo_current import _unique_object
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.contracts.retained_cargo_authored import AuthoredRetainedCargoBinding
from literate_ai.contracts.retained_libraries import RetainedLibraryBinding
from literate_ai.projects import PinnedInputClosure

from .errors import CliFailure

_FILE_LIMIT = 16 * 1024**2
_SOURCE_V2 = "literate-ai/retained-cargo-binding@2"
_LEGACY_FIELDS = ("gates", "reviewed_gates", "gate_size", "provider_id")
_AUTHORED_FIELDS = (
    "gate_policy",
    "provider_output_root",
    "provider_flavor",
    "old_output_file_bytes",
    "old_output_total_bytes",
    "output_files",
    "output_entries",
    "output_metadata_bytes",
    "new_output_file_bytes",
    "new_output_total_bytes",
    "sdk_completion",
    "sdk_completion_size",
    "sdk_revocations",
    "sdk_cache",
    "exclusion_authority",
    "reviewed_exclusion_authority",
    "exclusion_authority_size",
)


def _require_args(args, names):
    missing = [
        "--" + name.replace("_", "-")
        for name in names
        if getattr(args, name, None) is None or getattr(args, name, None) == ""
    ]
    if missing:
        raise CliFailure("cli.usage", "Missing required options: " + ", ".join(missing))


def _reject_args(args, names):
    selected = [
        "--" + name.replace("_", "-")
        for name in names
        if (
            getattr(args, name, None) is not None
            and getattr(args, name, None) is not False
            and getattr(args, name, None) != []
        )
    ]
    if selected:
        raise CliFailure(
            "cli.usage",
            "Options do not apply to this binding schema: " + ", ".join(selected),
        )


def reviewed_json(identity, size, *, maximum=_FILE_LIMIT):
    selected = ContentIdentity.parse_uri(identity)
    if type(size) is not int or not 0 < size <= maximum:
        raise ValueError("retained.cargo.review-size-invalid")
    return BlobRef(selected.digest, size, media_type="application/json")


def selected_limit(args, name, default):
    value = getattr(args, name, None)
    return default if value is None else value


def _validate_arguments(args, *, authored):
    if args.retained_cargo_command not in {"check", "materialize", "admit"}:
        raise ValueError("retained.cargo.operation-invalid")
    admit = args.retained_cargo_command == "admit"
    if authored:
        if args.offline:
            raise CliFailure(
                "qualification.authored.offline_unsupported",
                "Authored provider authority has no offline reader; "
                "this operation requires a supported online invocation.",
            )
        _reject_args(args, _LEGACY_FIELDS + ("reviewed_tests", "tests_size"))
        _require_args(
            args,
            ("gate_policy", "tests", "old_output_file_bytes", "old_output_total_bytes"),
        )
        if admit:
            _require_args(args, ("new_output_file_bytes", "new_output_total_bytes"))
        else:
            _reject_args(
                args,
                (
                    "new_output_file_bytes",
                    "new_output_total_bytes",
                    "exclusion_authority",
                    "reviewed_exclusion_authority",
                    "exclusion_authority_size",
                ),
            )
        permissions = (
            "exclusion_authority",
            "reviewed_exclusion_authority",
            "exclusion_authority_size",
        )
        if any(getattr(args, name, None) is not None for name in permissions):
            _require_args(args, permissions)
            reviewed_json(
                args.reviewed_exclusion_authority,
                args.exclusion_authority_size,
                maximum=4 * 1024**2,
            )
        sdk_options = (
            "sdk_cache",
            "sdk_completion",
            "sdk_completion_size",
            "sdk_revocations",
        )
        if any(getattr(args, key, None) is not None for key in sdk_options):
            _require_args(args, sdk_options)
            reviewed_json(args.sdk_completion, args.sdk_completion_size)
        # Resource values are actual typed declarations, never execution grants.
        from literate_ai.adapters.retained_cargo_native_output_tree import (
            _NativeOutputTreeBudget,
        )
        from literate_ai.contracts.retained_cargo_native_custody import (
            RetainedCargoOutputBudget,
        )

        _NativeOutputTreeBudget(
            RetainedCargoOutputBudget(
                args.old_output_file_bytes, args.old_output_total_bytes
            ),
            selected_limit(args, "output_files", 10000),
            selected_limit(args, "output_entries", 10000),
            _metadata_limit=selected_limit(args, "output_metadata_bytes", 1024**3),
        )
        if admit:
            RetainedCargoOutputBudget(
                args.new_output_file_bytes, args.new_output_total_bytes
            )
    else:
        _require_args(args, _LEGACY_FIELDS)
        _reject_args(args, _AUTHORED_FIELDS)
        if admit:
            _require_args(args, ("tests", "reviewed_tests", "tests_size"))
        else:
            _reject_args(
                args, ("tests", "reviewed_tests", "tests_size", "timeout_seconds")
            )
    if admit:
        _require_args(args, ("retirement", "reviewed_retirement", "retirement_size"))
        if not args.allow_host_execution or not args.acknowledge_source_retirement:
            raise ValueError("retained.cargo.admission-authorization-required")
        reviewed_json(
            args.reviewed_retirement, args.retirement_size, maximum=4 * 1024**2
        )
        if getattr(args, "timeout_seconds", None) is None:
            args.timeout_seconds = 900
    duration = getattr(args, "timeout_seconds", None)
    if duration is not None and (
        type(duration) not in (int, float)
        or not math.isfinite(duration)
        or duration <= 0
    ):
        raise ValueError("retained.cargo.timeout-invalid")
    if bool(args.archive) == bool(args.archive_https):
        raise ValueError("retained.cargo.archive-selection-invalid")
    if args.offline and args.archive_https:
        raise ValueError("retained.cargo.offline")


def retained_cargo_closed(args):
    root = Path(args.project).absolute()
    if ".." in root.parts:
        raise ValueError("retained.cargo.project-path-unsafe")
    require_safe_directory(root)
    canonical_relative_posix_path(args.binding, label="reviewed retained Cargo binding")
    reference = reviewed_json(args.reviewed_binding, args.binding_size)
    pins = PinnedInputClosure(
        maximum_files=1, maximum_file_bytes=_FILE_LIMIT, maximum_total_bytes=_FILE_LIMIT
    )
    content = pins.pin(
        root / args.binding,
        boundary=root,
        label="retained Cargo binding dispatch",
        expected_identity=reference.identity,
    )
    if len(content) != reference.size:
        raise ValueError("retained.cargo.binding-size-mismatch")
    document = json.loads(content, object_pairs_hook=_unique_object)
    if not isinstance(document, dict):
        raise ValueError("retained.cargo.binding-object-required")
    schema = document.get("schema")
    if schema == RetainedLibraryBinding.SCHEMA:
        RetainedLibraryBinding.from_dict(document)
        authored = False
    elif schema == AuthoredRetainedCargoBinding.SCHEMA:
        AuthoredRetainedCargoBinding.from_dict(document)
        authored = True
    elif schema == _SOURCE_V2:
        raise CliFailure(
            "retained.cargo.origin_unsupported",
            (
                "Source-v2 binding requires its actual receiving API; "
                "it cannot use source-v1 or authored authority"
            ),
        )
    else:
        raise ValueError("retained.cargo.binding-schema-unsupported")
    _validate_arguments(args, authored=authored)
    pins.require_unchanged()
    if authored:
        from .retained_cargo_authored import run_authored_retained_cargo

        return run_authored_retained_cargo(args, binding_reference=reference)
    from .retained_cargo import _run_source_v1

    result = _run_source_v1(args)
    pins.require_unchanged()
    return result
