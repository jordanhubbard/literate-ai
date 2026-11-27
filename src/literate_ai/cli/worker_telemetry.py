"""Public opt-in, one-shot observation; private configuration supplies trust."""

from __future__ import annotations

import json
import os
from pathlib import Path

from literate_ai.adapters.worker_telemetry_controller import query_worker_telemetry
from literate_ai.adapters.worker_telemetry_namespace import (
    initialize_worker_telemetry_namespace,
)
from literate_ai.adapters.worker_telemetry_wire_v2 import WorkerTelemetryWireError
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.worker_telemetry_v2 import MAX_OPERATIONS

from .errors import CliFailure


def add_telemetry_arguments(commands):
    commands.add_parser(
        "telemetry-native-initialize",
        help="initialize absent private FreeBSD observer build/provider namespaces",
    )
    native_plan = commands.add_parser(
        "telemetry-native-plan",
        help="read the exact current FreeBSD observer source/compiler build plan",
    )
    native_plan.add_argument(
        "--compiler", type=Path, help="explicit native compiler executable"
    )
    native = commands.add_parser(
        "telemetry-native-provision",
        help="explicitly build, probe and provision the current FreeBSD observer",
    )
    native.add_argument("--acknowledge-plan", required=True)
    native.add_argument(
        "--compiler", type=Path, help="same explicit native compiler as plan"
    )
    commands.add_parser(
        "telemetry-initialize",
        help="initialize an absent private observation namespace",
    )
    parser = commands.add_parser(
        "telemetry", help="observe one finite authenticated worker sample batch"
    )
    parser.add_argument("--configuration", type=Path, required=True)
    parser.add_argument("--worker-id", required=True)
    selection = parser.add_mutually_exclusive_group(required=True)
    selection.add_argument(
        "--operation",
        action="append",
        default=[],
        help="exact dispatch request SHA-256",
    )
    selection.add_argument("--worker-host", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=10000)
    parser.add_argument("--maximum-sample-age-ms", type=int, default=5000)
    parser.add_argument("--allow-cached-observations", action="store_true")


def worker_telemetry_from_args(args):
    try:
        if args.worker_command == "telemetry-native-initialize":
            from literate_ai.adapters.worker_telemetry_native_namespace import (
                initialize_native_provider_namespaces,
            )

            return {
                "schema": "literate-ai/worker-telemetry-native-initialization@1",
                "namespace_identities": initialize_native_provider_namespaces(),
                "created": True,
                "provider_admitted": False,
                "execution_authority": False,
            }, 0
        if args.worker_command in {
            "telemetry-native-plan",
            "telemetry-native-provision",
        }:
            from literate_ai.adapters.worker_telemetry_native_build import (
                build_native_resource_provider,
                plan_native_resource_provider_build,
            )

            with plan_native_resource_provider_build(
                compiler_executable=args.compiler
            ) as plan:
                if args.worker_command == "telemetry-native-plan":
                    return {
                        "schema": (
                            "literate-ai/worker-telemetry-native-build-planning@1"
                        ),
                        "plan_identity": plan.identity,
                        "plan": json.loads(plan.document),
                        "provider_admitted": False,
                        "execution_authority": False,
                    }, 0
                from literate_ai.adapters.worker_telemetry_native_probe import (
                    qualify_native_resource_provider,
                )
                from literate_ai.adapters.worker_telemetry_native_provision import (
                    provision_native_resource_provider,
                )

                with build_native_resource_provider(
                    plan, acknowledge_plan_identity=args.acknowledge_plan
                ) as build:
                    with qualify_native_resource_provider(build) as qualified:
                        return provision_native_resource_provider(qualified), 0
        if args.worker_command == "telemetry-initialize":
            try:
                identity = initialize_worker_telemetry_namespace()
            except FileExistsError as exc:
                raise WorkerTelemetryWireError(
                    "worker_telemetry.namespace_exists"
                ) from exc
            return {
                "schema": "literate-ai/worker-telemetry-namespace-initialization@1",
                "observation_namespace_identity": identity.to_dict(),
                "created": True,
            }, 0
        if len(args.operation) > MAX_OPERATIONS:
            raise WorkerTelemetryWireError(
                "worker_telemetry.operation_selection_invalid"
            )
        operations = tuple(ContentIdentity.parse_uri(value) for value in args.operation)
        observed = query_worker_telemetry(
            args.configuration,
            worker_id=args.worker_id,
            operations=operations,
            worker_host=args.worker_host,
            timeout_ms=args.timeout_ms,
            maximum_sample_age_ms=args.maximum_sample_age_ms,
            allow_cached_observations=args.allow_cached_observations,
            environment=os.environ,
        )
        return observed, 0
    except WorkerTelemetryWireError as exc:
        raise CliFailure(exc.code, "Worker telemetry observation refused") from exc
    except (OSError, ValueError, TypeError, RuntimeError) as exc:
        raise CliFailure(
            "worker_telemetry.query_unavailable",
            "Worker telemetry observation unavailable",
        ) from exc
