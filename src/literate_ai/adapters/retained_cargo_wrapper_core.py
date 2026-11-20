"""Private current retained-consumer wrapper custody shared by closed entrypoints.

This owns the actual importing conversion, source parity and selected wrapper
lock independently of provider origin. It grants no scratch or execution rights.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from dataclasses import dataclass

from literate_ai.adapters.authored_retained_cargo_review import (
    AuthoredRetainedCargoReviewedFiles,
)
from literate_ai.adapters.component_lock_application import (
    current_project_component_lock_bindings,
    current_project_component_lock_identities,
)
from literate_ai.adapters.component_locks import ComponentLockStore
from literate_ai.adapters.conversion_authority import (
    CONVERSION_AUTHORITY_FILE,
    FilesystemConversionAuthorityStore,
)
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock
from literate_ai.adapters.project_validation import validated_project_authority_identity
from literate_ai.adapters.retained_cargo_review_v2 import RetainedCargoReviewedFilesV2
from literate_ai.adapters.retained_harness_receipts import (
    _implementation_root,
    _load_retained_documents,
    _require_qualified_parity,
    _retained_project_authority_observation,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.projects import (
    PinnedInputClosure,
    ProjectConfigurationStore,
    ProjectContext,
)

_CREATION_KEY = object()
_DOCUMENTS = (
    ("inventory", ".literate/harness-inventory.json"),
    ("baseline", ".literate/legacy-harness-baseline.json"),
    ("parity", ".literate/legacy-wrapper-parity.json"),
    ("lift_shift", ".literate/legacy-lift-shift.json"),
)


@dataclass(slots=True)
class _WrapperLifetime:
    active: bool = True


class _UnsavableConsumerWrapper:
    """Neither private cores nor public views can renew ended custody."""

    def __copy__(self):
        raise TypeError("retained.cargo.v2-wrapper-context-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.cargo.v2-wrapper-context-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.cargo.v2-wrapper-context-not-serializable")

    def __getstate__(self):
        raise TypeError("retained.cargo.v2-wrapper-context-not-serializable")


@dataclass(init=False, eq=False, frozen=True)
class _CurrentCargoConsumerWrapper(_UnsavableConsumerWrapper):
    """Private original consumer custody; public entries keep nominal type gates."""

    def __init__(
        self,
        *,
        _key,
        reviewed,
        revision,
        conversion,
        documents,
        bindings,
        lifetime,
        configuration,
    ):
        if _key is not _CREATION_KEY:
            raise TypeError("retained.cargo.v2-live-wrapper-context-required")
        for name, value in (
            ("reviewed", reviewed),
            ("revision", revision),
            ("conversion", conversion),
            ("bindings", bindings),
            ("_lifetime", lifetime),
            ("implementation", _implementation_root(reviewed.project, documents)),
            ("workspace", reviewed.project.root / reviewed.plan.common.workspace_root),
        ):
            object.__setattr__(self, name, value)
        if not self.workspace.is_relative_to(self.implementation):
            raise ValueError("retained.cargo.v2-workspace-outside-retained-wrapper")
        object.__setattr__(
            self, "_implementation_node", directory_node(self.implementation)
        )
        object.__setattr__(self, "_workspace_node", directory_node(self.workspace))
        object.__setattr__(
            self,
            "_inputs",
            PinnedInputClosure(
                maximum_files=7,
                maximum_file_bytes=16 * 1024**2,
                maximum_total_bytes=112 * 1024**2,
            ),
        )
        root = reviewed.project.root
        context = ProjectContext(
            root, configuration.manifest_path.parent, configuration.directory_binding
        )
        object.__setattr__(self, "_project_context", context)
        self._inputs.pin(
            configuration.manifest_path,
            boundary=root,
            label=configuration.manifest_path.relative_to(root).as_posix(),
            expected_content=configuration.content,
        )
        for name, relative in _DOCUMENTS:
            path = context.framework_path(relative)
            content = self._inputs.pin(
                path, boundary=root, label=path.relative_to(root).as_posix()
            )
            if content not in {
                documents[name]["bytes"],
                documents[name]["bytes"] + b"\n",
            }:
                raise ValueError("retained.cargo.v2-wrapper-documents-changed")
        self._inputs.pin(
            root / "litai.harness.mk",
            boundary=root,
            label="retained harness wrapper",
            expected_content=documents["wrapper"]["bytes"],
        )
        conversion_bytes = self._inputs.pin(
            context.framework_path(CONVERSION_AUTHORITY_FILE),
            boundary=root,
            label="retained conversion authority",
        )
        if canonical_json_bytes(json.loads(conversion_bytes)) != canonical_json_bytes(
            conversion.to_dict()
        ):
            raise ValueError("retained.cargo.v2-wrapper-conversion-changed")
        object.__setattr__(
            self,
            "_closures",
            tuple(
                catalog.locked_input_closure(
                    lock,
                    lock_path=ComponentLockStore(catalog.root).path,
                    lock_boundary=ComponentLockStore(catalog.root).storage_root,
                )
                for lock, catalog in bindings
            ),
        )
        source_authority, _ = _retained_project_authority_observation(
            reviewed.project,
            revision,
            documents=documents,
            implementation=self.implementation,
        )
        object.__setattr__(self, "source_authority", source_authority)

    def require_unchanged(self):
        if not self._lifetime.active:
            raise ValueError("retained.cargo.v2-wrapper-operation-ended")
        reviewed = self.reviewed
        reviewed.require_unchanged()
        self._require_context()
        self._inputs.require_unchanged()
        if (
            directory_node(self.implementation) != self._implementation_node
            or directory_node(self.workspace) != self._workspace_node
            or ProjectConfigurationStore(reviewed.project.root).read().definition
            != reviewed.project.definition
            or FilesystemConversionAuthorityStore(reviewed.project.root).load_optional()
            != self.conversion
            or validated_project_authority_identity(
                reviewed.project.root, synchronize_source_intelligence=False
            )
            != self.revision
        ):
            raise ValueError("retained.cargo.v2-wrapper-authority-changed")
        for (lock, catalog), closure in zip(self.bindings, self._closures, strict=True):
            catalog.require_unchanged()
            ComponentLockStore(catalog.root).require_current(lock)
            closure.require_unchanged()
        documents = _load_retained_documents(reviewed.project)
        _require_qualified_parity(documents)
        current, _ = _retained_project_authority_observation(
            reviewed.project,
            self.revision,
            documents=documents,
            implementation=self.implementation,
        )
        if current != self.source_authority:
            raise ValueError("retained.cargo.v2-wrapper-source-changed")
        self._inputs.require_unchanged()
        reviewed.require_unchanged()
        self._require_context()
        if (
            directory_node(self.implementation) != self._implementation_node
            or directory_node(self.workspace) != self._workspace_node
            or current_project_component_lock_identities(reviewed.project)
            != tuple(lock.identity for lock, _ in self.bindings)
        ):
            raise ValueError("retained.cargo.v2-wrapper-ancestry-or-lock-set-changed")

    def _require_context(self):
        if (
            ProjectConfigurationStore.context(self.reviewed.project.root)
            != self._project_context
        ):
            raise ValueError("retained.cargo.v2-wrapper-project-context-changed")


class _CargoConsumerWrapperView(_UnsavableConsumerWrapper):
    """Read-only facade mechanics; no public constructor or decoder."""

    _IDENTITY_SCHEMA = "literate-ai/retained-cargo-wrapper-context@2"
    _EXPOSED = frozenset(
        {
            "reviewed",
            "revision",
            "conversion",
            "bindings",
            "implementation",
            "workspace",
            "source_authority",
            "_lifetime",
            "_inputs",
            "_closures",
            "_implementation_node",
            "_workspace_node",
        }
    )

    def __getattr__(self, name):
        if name in self._EXPOSED:
            return getattr(self._core, name)
        raise AttributeError(name)

    @property
    def identity(self):
        self.require_unchanged()
        self.reviewed.require_unchanged()
        return self._captured_identity()

    def _captured_identity(self):
        return canonical_identity(
            {
                "schema": self._IDENTITY_SCHEMA,
                "reviewed": self.reviewed._captured_identity().uri,
                "revision": self.revision.uri,
                "conversion": self.conversion.identity.uri,
                "source_authority": self.source_authority.uri,
                "implementation": self.implementation.relative_to(
                    self.reviewed.project.root
                ).as_posix(),
                "locks": [lock.identity.uri for lock, _ in self.bindings],
            }
        )

    def require_unchanged(self):
        self._core.require_unchanged()


@contextmanager
def _open_consumer_wrapper_context(reviewed):
    """Join current authorities under the lifecycle lock, invalidating on exit.

    The current canonical wrapper coordinate is used directly; custom retained
    layouts require the separately tracked layout resolver, not an alias shim.
    """
    if type(reviewed) not in (
        RetainedCargoReviewedFilesV2,
        AuthoredRetainedCargoReviewedFiles,
    ):
        raise TypeError("retained.cargo.consumer-reviewed-files-required")
    project = reviewed.project
    operation = (
        "retained-cargo.v2"
        if type(reviewed) is RetainedCargoReviewedFilesV2
        else "retained-cargo.authored"
    )
    with project_lifecycle_lock(project.root, operation=operation):
        reviewed.require_unchanged()
        configuration = ProjectConfigurationStore(project.root).read()
        if (
            configuration.root != project.root
            or configuration.definition != project.definition
        ):
            raise ValueError("retained.cargo.v2-wrapper-project-changed")
        revision = validated_project_authority_identity(
            project.root, synchronize_source_intelligence=False
        )
        conversion = FilesystemConversionAuthorityStore(project.root).load_optional()
        if (
            conversion is None
            or conversion.project_id != project.definition.project_id
            or conversion.release_authority != "original-source"
        ):
            raise ValueError("retained.cargo.v2-original-authority-required")
        documents = _load_retained_documents(project)
        _require_qualified_parity(documents)
        bindings = current_project_component_lock_bindings(project)
        wrapper = project.root / "components/legacy-project-wrapper"
        selected = tuple((lock, c) for lock, c in bindings if c.root == wrapper)
        if len(selected) != 1:
            raise ValueError("retained.cargo.v2-current-wrapper-lock-required")
        lock, catalog = selected[0]
        root_revision = next(
            node.revision
            for node in lock.nodes
            if node.revision.identity == lock.root_revision
        )
        if (
            catalog.project is None
            or catalog.project.root != project.root
            or catalog.root_authoring != root_revision.definition
        ):
            raise ValueError("retained.cargo.v2-wrapper-owner-mismatch")
        lifetime = _WrapperLifetime()
        context = _CurrentCargoConsumerWrapper(
            _key=_CREATION_KEY,
            reviewed=reviewed,
            revision=revision,
            conversion=conversion,
            documents=documents,
            bindings=bindings,
            lifetime=lifetime,
            configuration=configuration,
        )
        try:
            yield context
        finally:
            lifetime.active = False
