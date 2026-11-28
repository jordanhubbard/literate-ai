"""Original local command admission for an explicitly selected run policy.

Filesystem custody constrains one live owner; serialized records and matching
manifest bytes cannot restore that owner or replace its original file.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from literate_ai.adapters.standard_lifecycle_binding import (
    ResolvedStandardProjectLifecycleDriver,
)
from literate_ai.application.native_root_run import (
    LiveNativeRootRun,
    NativeRootRunError,
    activate_native_root_run,
    open_native_root_run,
)
from literate_ai.contracts.projects import StandardProjectLifecycleDriver
from literate_ai.projects import (
    LoadedProject,
    PinnedInputClosure,
    ProjectConfigurationStore,
    parse_project_configuration,
)


def _file_binding(path: Path) -> tuple[int, ...]:
    observed = path.lstat()
    return (
        observed.st_dev,
        observed.st_ino,
        observed.st_mode,
        observed.st_uid,
        observed.st_gid,
        observed.st_nlink,
        observed.st_size,
        observed.st_mtime_ns,
        observed.st_ctime_ns,
    )


@contextmanager
def admit_native_root_command(
    project: LoadedProject,
    binding: ResolvedStandardProjectLifecycleDriver,
) -> Iterator[LiveNativeRootRun]:
    """Keep the original manifest and installed binding current until return.

    Call only after ordinary host-execution acknowledgement and before indexing
    or execution preparation. This lifetime grants no execution permission.
    """
    if type(binding) is not ResolvedStandardProjectLifecycleDriver:
        raise NativeRootRunError("binding_invalid")
    store = ProjectConfigurationStore(project.root)
    snapshot = store.read()
    # Parse original bytes independently of the read-only parse-template cache.
    # A mutated cached object must never select a different policy or authority.
    definition = parse_project_configuration(snapshot.content)
    identity = definition.identity
    policy = definition.native_root_run_policy
    driver = definition.lifecycle_driver
    if policy is None or type(driver) is not StandardProjectLifecycleDriver:
        raise NativeRootRunError("policy_required")
    original_file = _file_binding(snapshot.manifest_path)
    closure = PinnedInputClosure.for_project(project)
    closure.pin(
        snapshot.manifest_path,
        boundary=snapshot.root,
        label="original native root run manifest",
        expected_content=snapshot.content,
    )

    def require_current() -> None:
        binding.require_unchanged()
        if (
            binding.driver != driver
            or driver.framework_distribution_identity != binding.distribution.identity
            or driver.policy_identity != binding.policy.identity
        ):
            raise NativeRootRunError("binding_changed")
        closure.require_unchanged()
        current = store.read()
        if (
            current.root != snapshot.root
            or current.manifest_path != snapshot.manifest_path
            or current.directory_binding != snapshot.directory_binding
            or current.content != snapshot.content
            or current.definition.identity != identity
            or project.definition.identity != identity
            or parse_project_configuration(current.content).identity != identity
            or _file_binding(snapshot.manifest_path) != original_file
        ):
            raise NativeRootRunError("manifest_changed")
        # Recheck file bytes after the metadata observations as well.
        closure.require_unchanged()
        binding.require_unchanged()

    require_current()
    with open_native_root_run(
        policy,
        project_identity=identity,
        framework_distribution_identity=binding.distribution.identity,
        lifecycle_policy_identity=binding.policy.identity,
        require_current=require_current,
    ) as owner:
        with activate_native_root_run(owner):
            owner.require_current()
            yield owner
            owner.require_current()
