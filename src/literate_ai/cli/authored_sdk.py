"""Prepare SDKs explicitly or reopen a selected completion for authored operations."""

import os
import shutil
import time
from pathlib import Path

from literate_ai.adapters.authored_qualification_authority import (
    read_current_authored_qualification_authority,
)
from literate_ai.adapters.lifecycle.standard_local import LocalComponentToolBinding
from literate_ai.adapters.native_sdk_acquisition import NativeSdkProjectAcquisition
from literate_ai.adapters.native_sdk_completion_producer import (
    record_authored_sdk_completion,
)
from literate_ai.adapters.native_sdk_consumer import NativeSdkConsumerInputs
from literate_ai.adapters.native_sdk_recipes import select_native_sdk_recipes
from literate_ai.adapters.native_sdk_revocation_file import SdkRevocationFile
from literate_ai.adapters.standard_lifecycle_binding import (
    resolve_standard_project_lifecycle_driver,
)
from literate_ai.contracts import BlobRef, ContentIdentity
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_project import RetainedProjectLimits
from literate_ai.projects import ProjectConfigurationStore
from literate_ai.security import SecurityPolicy

from .errors import CliFailure


def _sdk_operation(project, selection, args, *, prepare):
    """Retain the returned actual owner through plan, replay and receiving."""
    # Reading provider authority may resolve remote assets even before SDK
    # selection. Refuse before that reader until an offline authority path exists.
    if getattr(args, "offline", False):
        raise CliFailure(
            "qualification.authored.offline_unsupported",
            "Authored authority and SDK acquisition have no offline opener; "
            "use a supported online operation with explicit SDK consent if needed.",
        )
    authority = read_current_authored_qualification_authority(project.root, selection)
    snapshot = authority.locked
    selections = tuple(
        selected
        for node in snapshot.authority.lock.nodes
        if node.revision.repository_sources
        for selected in select_native_sdk_recipes(snapshot, node.revision.identity)
    )
    if not selections:
        if prepare or any(
            getattr(args, k, None) is not None
            for k in (
                "sdk_cache",
                "sdk_completion",
                "sdk_completion_size",
                "sdk_revocations",
            )
        ):
            raise CliFailure("cli.usage", "This selection declares no SDK dependencies")
        return None
    if prepare and getattr(args, "allow_sdk_builds", False) is not True:
        raise CliFailure(
            "native_sdk.host_build_not_acknowledged",
            "SDK preparation requires --allow-sdk-builds",
        )
    configured = getattr(args, "sdk_cache", None)
    if not configured:
        raise CliFailure("cli.usage", "Locked SDK dependencies require --sdk-cache")
    if not prepare:
        size = getattr(args, "sdk_completion_size", None)
        identity = getattr(args, "sdk_completion", None)
        if not identity or type(size) is not int or not 0 < size <= 16 * 1024**2:
            raise CliFailure(
                "cli.usage", "Provide --sdk-completion and --sdk-completion-size"
            )
        reference = BlobRef(
            ContentIdentity.parse_uri(identity).digest,
            size,
            media_type="application/vnd.literate-ai.manifest+json",
        )
    selected = Path(configured)
    cache = (selected if selected.is_absolute() else project.root / selected).absolute()
    if ".." in cache.parts:
        raise CliFailure("cli.usage", "SDK cache must use a canonical explicit path")
    binding = resolve_standard_project_lifecycle_driver(
        project.definition.lifecycle_driver
    )
    configuration = ProjectConfigurationStore(project.root).read()
    if configuration.definition != project.definition:
        raise ValueError("native_sdk.project_authority_changed")
    revocation_path = getattr(args, "sdk_revocations", None)
    if not revocation_path:
        raise CliFailure("cli.usage", "Provide --sdk-revocations PATH for locked SDKs")
    revocations = SdkRevocationFile(revocation_path)
    revocations()

    def current_revocations():
        binding.require_unchanged()
        authority.require_unchanged()
        current = ProjectConfigurationStore(project.root).read()
        if (
            current.content != configuration.content
            or current.definition != project.definition
        ):
            raise ValueError("native_sdk.project_authority_changed")
        return revocations()

    if not prepare:
        tools = {}
        for name in sorted({name for item in selections for name in item.recipe.tools}):
            executable = shutil.which(name, path=os.environ.get("PATH", ""))
            if executable is None:
                raise CliFailure(
                    "native_sdk.tool_unavailable", f"Unavailable SDK tool: {name}"
                )
            tools[name] = LocalComponentToolBinding(
                str(Path(executable).resolve(strict=True))
            )

        def step():
            if time.monotonic() >= deadline:
                raise ValueError("SDK completion verification deadline exceeded")

        deadline = time.monotonic() + 3600
        return NativeSdkConsumerInputs._open_authored_completion(
            authority,
            cache_root=cache,
            expected_completion=reference,
            tools=tools,
            limits=RetainedProjectLimits(1000000, 1024**3, 16 * 1024**3),
            read_limits=RetainedProjectLimits(2000000, 1024**3, 32 * 1024**3),
            max_manifest_bytes=16 * 1024**2,
            step=step,
            revocations=current_revocations,
            revocation_file=revocations,
        )
    acquisition = NativeSdkProjectAcquisition(
        cache_root=cache,
        source_intelligence_policy=project.definition.source_intelligence,
        security_policy=SecurityPolicy(
            canonical_identity(
                {
                    "policy": "standard-native-sdk-build@1",
                    "standard_policy": binding.policy.identity.uri,
                }
            ).uri
        ),
        revocations=current_revocations,
        environment=os.environ,
        actor="authored-qualification",
        reason=(
            "Acquire the operator-acknowledged locked SDK inputs "
            "for authored qualification and receiving"
        ),
        host_build_acknowledged=True,
    )
    owner = acquisition(snapshot)
    current_revocations()
    if owner is None:
        raise ValueError("native_sdk.selected_inputs_missing")
    owner.require_unchanged()
    reference = record_authored_sdk_completion(authority, owner)
    return {"sdk_completion": reference.identity, "sdk_completion_size": reference.size}


def prepare_authored_sdk(project, selection, args):
    return _sdk_operation(project, selection, args, prepare=True)


def reopen_authored_sdk_inputs(project, selection, args):
    return _sdk_operation(project, selection, args, prepare=False)
