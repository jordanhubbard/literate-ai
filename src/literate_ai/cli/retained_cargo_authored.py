"""Actual authored retained consumer CLI composition after closed dispatch."""

import json
import os
import re
from contextlib import ExitStack
from pathlib import Path

from literate_ai.adapters.authored_qualification_receiving import (
    _bind_authored_qualification_read_ports,
)
from literate_ai.adapters.authored_retained_cargo_admission import (
    admit_authored_retained_cargo_consumer,
)
from literate_ai.adapters.authored_retained_cargo_provisioning import (
    provision_authored_retained_cargo_consumer,
)
from literate_ai.adapters.authored_retained_cargo_review import (
    read_authored_retained_cargo_review,
)
from literate_ai.adapters.builders.cargo import discover_cargo_toolchain
from literate_ai.adapters.builders.make import discover_make_toolchain
from literate_ai.adapters.builders.rust import discover_rust_toolchain
from literate_ai.adapters.evidence_storage import HttpsEvidenceStore
from literate_ai.adapters.lifecycle.standard_local import LocalComponentToolBinding
from literate_ai.adapters.retained_cargo_current import _unique_object
from literate_ai.application.generation_preparation import GenerationPreparationRequest
from literate_ai.contracts.authored_retained_cargo_permissions import (
    AuthoredRetainedCargoExclusionAuthority,
)
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)
from literate_ai.contracts.retained_cargo_test_protocol import (
    RetainedCargoCustomProtocol,
    RetainedCargoExcludedProtocol,
)
from literate_ai.projects import PinnedInputClosure, discover_project
from literate_ai.security.evidence.storage import EvidenceReadLimits

from .authored_sdk import reopen_authored_sdk_inputs
from .retained_cargo_routing import reviewed_json, selected_limit

_read_ports = _bind_authored_qualification_read_ports()
del _bind_authored_qualification_read_ports

_ARCHIVE_LIMIT = 64 * 1024**2


def _exclusion_reader(args, reviewed):
    needed = frozenset(
        target.protocol.permission_identity
        for target in reviewed.inventory.targets
        if isinstance(target.protocol, RetainedCargoExcludedProtocol)
    )
    selected = getattr(args, "exclusion_authority", None)
    if selected is None:
        if needed:
            raise ValueError("retained.cargo.independent-exclusion-authority-required")
        return None, None
    canonical_relative_posix_path(selected, label="independent exclusion authority")
    reference = reviewed_json(
        args.reviewed_exclusion_authority,
        args.exclusion_authority_size,
        maximum=4 * 1024**2,
    )
    root = reviewed.project.root
    pins = PinnedInputClosure(
        maximum_files=1, maximum_file_bytes=4 * 1024**2, maximum_total_bytes=4 * 1024**2
    )
    content = pins.pin(
        root / selected,
        boundary=root,
        label="independent exclusion authority",
        expected_identity=reference.identity,
    )
    if len(content) != reference.size:
        raise ValueError("retained.cargo.exclusion-authority-size-mismatch")
    authority = AuthoredRetainedCargoExclusionAuthority.from_dict(
        json.loads(content, object_pairs_hook=_unique_object)
    )
    authority.require_binding(reviewed.binding)
    allowed = frozenset(authority.permissions)
    if not needed <= allowed:
        raise ValueError("retained.cargo.independent-exclusion-authority-incomplete")

    def read(identity):
        pins.require_unchanged()
        return identity if identity in allowed else None

    return read, pins


def _archive(args, reference):
    if not 0 < reference.size <= _ARCHIVE_LIMIT:
        raise ValueError("retained.cargo.archive-selection-invalid")
    token = None
    if args.archive_token_env is not None:
        if (
            not args.archive_https
            or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", args.archive_token_env) is None
        ):
            raise ValueError("retained.cargo.credentials-selection-invalid")
        token = os.environ.get(args.archive_token_env)
        if not token:
            raise ValueError("retained.cargo.credentials-required")
    if args.archive_https:
        transport = HttpsEvidenceStore(
            args.archive_https,
            bearer_token=token,
            limits=EvidenceReadLimits(_ARCHIVE_LIMIT, _ARCHIVE_LIMIT, 1),
        )
        return transport.get_bytes(reference), None
    path = Path(args.archive).absolute()
    pins = PinnedInputClosure(
        maximum_files=1,
        maximum_file_bytes=_ARCHIVE_LIMIT,
        maximum_total_bytes=_ARCHIVE_LIMIT,
    )
    content = pins.pin(
        path,
        boundary=path.parent,
        label="authored qualification archive",
        expected_identity=reference.identity,
    )
    if len(content) != reference.size:
        raise ValueError("retained.cargo.archive-size-mismatch")
    return content, pins


def run_authored_retained_cargo(args, *, binding_reference):
    with ExitStack() as owners:
        return _run_authored_retained_cargo(
            args, binding_reference=binding_reference, owners=owners
        )


def _run_authored_retained_cargo(args, *, binding_reference, owners):
    if any(
        getattr(args, name, None) in (None, "")
        for name in (
            "producer_review",
            "reviewed_producer_review",
            "producer_review_size",
        )
    ):
        raise ValueError("retained.cargo.independent-producer-review-required")
    root = Path(args.project).absolute()
    # Actual reviewed plan/policy/inventory pins precede provider discovery,
    # SDK acquisition, archive transport and all consumer output effects.
    review_options = {}
    if getattr(args, "producer_review", None) is not None:
        review_options = dict(
            producer_review_path=args.producer_review,
            reviewed_producer=reviewed_json(
                args.reviewed_producer_review, args.producer_review_size
            ),
        )
    reviewed = read_authored_retained_cargo_review(
        root,
        binding_path=args.binding,
        reviewed_binding=binding_reference,
        plan_path=args.plan,
        gate_policy_path=args.gate_policy,
        test_inventory_path=args.tests,
        **review_options,
        maximum_file_bytes=16 * 1024**2,
        maximum_total_bytes=64 * 1024**2,
    )
    if reviewed.binding.evidence_store_id != args.store_id:
        raise ValueError("retained.cargo.archive-store-mismatch")
    if review_options:
        intent = reviewed.producer_review
        if (
            args.provider_profile != intent.profile_path
            or selected_limit(args, "provider_output_root", "litai/qualification")
            != intent.provider_plan.output_root
            or (args.model is not None and args.model != intent.pipeline_model)
        ):
            raise ValueError(
                "retained.cargo.authored-reviewed-producer-selection-mismatch"
            )
    permission_reader, _permission_pins = (
        _exclusion_reader(args, reviewed)
        if args.retained_cargo_command == "admit"
        else (None, None)
    )
    provider_root = Path(args.provider_project).absolute()
    provider = discover_project(provider_root)
    if provider is None or provider.root != provider_root:
        raise ValueError("retained.cargo.current-provider-project-required")
    if args.provider_component != ".":
        canonical_relative_posix_path(
            args.provider_component, label="authored provider Component"
        )
    selection = GenerationPreparationRequest(
        component_root=provider.root / args.provider_component,
        target_name=args.target,
        flavor_selectors=tuple(getattr(args, "provider_flavor", ())),
        flavor_roots=provider.roots("flavor"),
    )
    sdk_inputs = reopen_authored_sdk_inputs(provider, selection, args)
    current = owners.enter_context(
        _read_ports(
            "open",
            root,
            binding_path=args.binding,
            reviewed_binding=binding_reference,
            plan_path=args.plan,
            gate_policy_path=args.gate_policy,
            test_inventory_path=args.tests,
            **review_options,
            provider_root=provider.root,
            selection=selection,
            configured_store_id=args.store_id,
            profile_path=args.provider_profile,
            output_root=selected_limit(
                args, "provider_output_root", "litai/qualification"
            ),
            native_sdk_inputs=sdk_inputs,
            max_review_file_bytes=16 * 1024**2,
            max_review_total_bytes=64 * 1024**2,
        )
    )
    _read_ports("full", current)
    if (
        reviewed.identity != current.reviewed.identity
        or reviewed._context != current.reviewed._context
        or reviewed.project.root != current.reviewed.project.root
    ):
        raise ValueError("retained.cargo.authored-original-reviewed-inputs-mismatch")
    payload, archive_pins = _archive(args, reviewed.binding.provider_reference.archive)
    environment = dict(os.environ)
    cargo = discover_cargo_toolchain(environment)
    rustc = discover_rust_toolchain(environment)
    common = dict(
        binding_path=args.binding,
        reviewed_binding=binding_reference,
        plan_path=args.plan,
        gate_policy_path=args.gate_policy,
        test_inventory_path=args.tests,
        **review_options,
        provider_current=current,
        configured_store_id=args.store_id,
        consumer_cargo=cargo,
        consumer_rustc=rustc,
        archive_payload=payload,
        archive_inputs=archive_pins,
        native_sdk_inputs=sdk_inputs,
        old_output_budget=RetainedCargoOutputBudget(
            args.old_output_file_bytes, args.old_output_total_bytes
        ),
        maximum_output_files=selected_limit(args, "output_files", 10000),
        maximum_output_entries=selected_limit(args, "output_entries", 10000),
        maximum_output_metadata_bytes=selected_limit(
            args, "output_metadata_bytes", 1024**3
        ),
        timeout_seconds=selected_limit(args, "timeout_seconds", 900),
    )
    reviewed.require_unchanged()
    if args.retained_cargo_command == "admit":
        tools = {}
        names = {command.argv[0] for command in reviewed.plan.common.gates}
        names.update(
            target.protocol.command.argv[0]
            for target in reviewed.inventory.targets
            if isinstance(target.protocol, RetainedCargoCustomProtocol)
            and target.protocol.command.argv[0] != "{target_executable}"
        )
        for name in names:
            if name == "cargo":
                measured = cargo
            elif name == "rustc":
                measured = rustc
            elif name in {"make", "gmake"}:
                measured = discover_make_toolchain(environment, pinned_command=name)
            else:
                raise ValueError("retained.cargo.gate-tool-unsupported")
            tools[name] = LocalComponentToolBinding.from_observed_toolchain(measured)
        receipt = admit_authored_retained_cargo_consumer(
            root,
            **common,
            environment=environment,
            gate_tools=tools,
            new_output_budget=RetainedCargoOutputBudget(
                args.new_output_file_bytes, args.new_output_total_bytes
            ),
            retirement_path=args.retirement,
            reviewed_retirement=reviewed_json(
                args.reviewed_retirement, args.retirement_size, maximum=4 * 1024**2
            ),
            acknowledge_source_retirement=args.acknowledge_source_retirement,
            allow_host_execution=args.allow_host_execution,
            read_exclusion_permission=permission_reader,
            offline=args.offline,
        )
        result = receipt.to_dict()
    else:
        result = provision_authored_retained_cargo_consumer(
            root,
            operation=args.retained_cargo_command,
            **common,
        )
    return result
