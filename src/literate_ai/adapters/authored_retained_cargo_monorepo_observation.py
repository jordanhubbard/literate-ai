"""Original optional monorepo facts for an owning authored completion.

The full existing checker can invoke Git. Refresh it before all final local
comparisons. These private observations issue no lease, execution or admission
and do not promise future/global Git or filesystem stability.
"""

import hashlib
import stat
from bisect import bisect_left
from dataclasses import dataclass, field

from literate_ai._filesystem import require_safe_directory, stat_is_link_or_reparse
from literate_ai.adapters.authored_retained_cargo_execution_inputs import (
    AuthoredRetainedCargoExecutionInputs,
)
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.harness_tree import _validated_scope
from literate_ai.adapters.monorepo_adoption import _direct, _read_direct_bytes
from literate_ai.adapters.monorepo_components import (
    INSTALLATION_ROOT,
    _parse_document,
    check_installed_monorepo_components,
)
from literate_ai.adapters.retained_cargo_execution_inputs import _state
from literate_ai.adapters.retained_cargo_test_execution import (
    _require_native_completion_deadline,
)
from literate_ai.adapters.streamed_file_custody import StreamedFileCustody, _physical
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity
from literate_ai.projects import ProjectConfigurationStore

_KEY = object()


def _present(path):
    try:
        path.lstat()
    except FileNotFoundError:
        return False
    return True


def _find(rows, name, *, key=lambda item: item):
    index = bisect_left(rows, name, key=key)
    return rows[index] if index < len(rows) and key(rows[index]) == name else None


class _SelectedMonorepoFileCustody(StreamedFileCustody):
    def _observe(self, path, boundary, *, maximum_bytes):
        if path in self._document_paths:
            maximum_bytes = min(maximum_bytes, 16 * 1024**2)
        if (path, boundary) not in self._entries:
            maximum_bytes = min(maximum_bytes, self._supplement.bytes_left)
        return super()._observe(path, boundary, maximum_bytes=maximum_bytes)


class _SupplementalOriginalFiles:
    """Selected exact files, aliases and ancestors; never a complete input scope."""

    def __init__(self, inputs, maximum_metadata_bytes):
        self.inputs = inputs
        self.root = inputs.materialized.files.reviewed.project.root
        aggregate = inputs.scope.policy.input_custody.aggregate
        self.aggregate = aggregate
        counts = inputs.scope.owners.counts
        self.files_left = (
            aggregate.maximum_files
            - counts["files"]
            - len(inputs._configuration._entries)
        )
        self.entries_left = (
            aggregate.maximum_entries - counts["entries"] - len(inputs._states)
        )
        self.bytes_left = (
            aggregate.maximum_total_bytes
            - counts["bytes"]
            - (inputs._configuration._total_bytes)
        )
        limits = inputs.materialized.files.reviewed.project.definition.scale_limits
        if limits is not None:
            self.files_left = min(self.files_left, limits.pinned_input_files)
            self.bytes_left = min(self.bytes_left, limits.pinned_input_total_bytes)
        self.member_limit = aggregate.maximum_file_bytes
        if type(maximum_metadata_bytes) is not int or not (
            1 <= maximum_metadata_bytes <= inputs.scope.owners.maximum_metadata_bytes
        ):
            raise ValueError("retained.monorepo.completion-metadata-allowance")
        self.metadata_left = maximum_metadata_bytes
        self.references = {}
        self.groups = {}
        self.directories = {}
        self._charge_metadata(
            256 * (3 + len(inputs.materialized.scratch.context._core._closures))
        )
        self.closures = (
            inputs.materialized.files.reviewed._inputs,
            inputs.materialized.scratch.context._core._inputs,
            inputs._configuration,
            *inputs.materialized.scratch.context._core._closures,
        )
        self.covered = {}
        self.streamed = None
        self.document_paths = set()
        configuration = inputs._configuration._labels.values()
        self._charge_metadata(
            sum(256 + len(str(item[0]).encode()) * 4 for item in configuration)
        )
        self.configuration_files = {
            item[0] for item in inputs._configuration._labels.values()
        }

    def _charge_metadata(self, count):
        if count > self.metadata_left:
            raise ValueError("retained.monorepo.completion-metadata-limit")
        self.metadata_left -= count

    def _tree_coverage(self, path):
        for _, tree in self.inputs.scope.owners.trees:
            if path == tree.root or not path.is_relative_to(tree.root):
                continue
            name = path.relative_to(tree.root).as_posix()
            row = _find(tree.files, name, key=lambda x: x[0])
            if row is None:
                alias = _find(tree.aliases, name, key=lambda x: x.path)
                if alias is not None and alias.kind == "hardlink":
                    row = _find(tree.files, alias.target, key=lambda x: x[0])
            if row is not None:
                return row[1]
        return None

    def _covered_directory(self, path):
        if any(
            path == selected and before[2] is not None and len(before[2]) == 3
            for selected, before in self.inputs._states
        ):
            return True
        if path in (
            self.root,
            self.inputs.materialized.files.reviewed.project.framework_root,
        ):
            return True
        for _, tree in self.inputs.scope.owners.trees:
            if path == tree.root:
                return True
            if path.is_relative_to(tree.root):
                name = path.relative_to(tree.root).as_posix()
                if _find(tree.directories, name) is not None:
                    return True
        return False

    def cover_selected_closures(self, paths):
        # Only index the needed selected paths. Do not duplicate entire catalogs.
        for closure in self.closures:
            for path, _boundary, content in closure._labels.values():
                if path in paths and path not in self.covered:
                    self._charge_metadata(256 + len(str(path).encode()) * 4)
                    self.covered[path] = BlobRef(
                        hashlib.sha256(content).hexdigest(), len(content)
                    )

    def _ancestors(self, path):
        for parent in path.parents:
            if not parent.is_relative_to(self.root):
                break
            if parent not in self.directories and not self._covered_directory(parent):
                if self.entries_left < 1:
                    raise ValueError("retained.monorepo.completion-entry-limit")
                self._charge_metadata(256 + len(str(parent).encode()) * 4)
                self.directories[parent] = directory_node(parent)
                self.entries_left -= 1

    def observe(self, path):
        if path in self.references:
            return self.references[path][0]
        require_safe_directory(path.parent)
        node = path.lstat()
        if stat_is_link_or_reparse(node) or not stat.S_ISREG(node.st_mode):
            raise ValueError("retained.monorepo.completion-file-unsafe")
        if path in self.document_paths and node.st_size > 16 * 1024**2:
            raise ValueError("retained.monorepo.completion-document-limit")
        self._charge_metadata(512 + len(str(path).encode()) * 4)
        tree_blob = self._tree_coverage(path)
        blob = tree_blob or self.covered.get(path)
        physical = _physical(node)
        previous = self.groups.get(physical[:2])
        if previous is not None and previous["physical"] != physical:
            raise ValueError("retained.monorepo.completion-file-changed")
        if blob is None and previous is not None:
            blob = previous["blob"]
        already_charged = tree_blob is not None or path in self.configuration_files
        if not already_charged:
            # Reusing a closure saves hashing/retention, not consumer allowance.
            if node.st_size > self.member_limit:
                raise ValueError("retained.monorepo.completion-source-file-limit")
            if self.entries_left < 1:
                raise ValueError("retained.monorepo.completion-entry-limit")
            self.entries_left -= 1
            self._ancestors(path)
        group_charged = already_charged or (
            previous is not None and previous["charged"]
        )
        if not group_charged and (
            self.files_left < 1 or node.st_size > self.bytes_left
        ):
            raise ValueError("retained.monorepo.completion-source-allowance")
        if blob is None:
            if self.files_left < 1 or self.bytes_left < 0:
                raise ValueError("retained.monorepo.completion-source-allowance")
            if self.streamed is None:
                # Keep the actual reviewed source declaration. The ledger and
                # per-new-file read cap enforce its residual allowance, including
                # a legal empty member when zero payload bytes remain.
                self.streamed = _SelectedMonorepoFileCustody._from_source_budget(
                    self.aggregate
                )
                self.streamed._document_paths = self.document_paths
                self.streamed._supplement = self
            self._charge_metadata(
                sum(256 + len(str(parent).encode()) * 4 for parent in path.parents)
            )
            blob = self.streamed.pin(
                path,
                boundary=self.root,
                label=hashlib.sha256(
                    path.relative_to(self.root).as_posix().encode()
                ).hexdigest(),
            )
        if blob.size != node.st_size:
            raise ValueError("retained.monorepo.completion-file-changed")
        if not group_charged:
            if blob.size > self.member_limit or blob.size > self.bytes_left:
                raise ValueError("retained.monorepo.completion-source-byte-limit")
            self.files_left -= 1
            self.bytes_left -= blob.size
        if previous is None:
            previous = {
                "blob": blob,
                "physical": physical,
                "paths": [],
                "closed_tree": tree_blob is not None,
                "charged": True,
            }
            self.groups[physical[:2]] = previous
        elif previous["blob"] != blob:
            raise ValueError("retained.monorepo.completion-file-changed")
        previous["closed_tree"] |= tree_blob is not None
        previous["charged"] = True
        previous["paths"].append(path)
        self.references[path] = blob, physical
        return blob

    def document(self, path):
        self.document_paths.add(path)
        blob = self.observe(path)
        if blob.size > self.metadata_left:
            raise ValueError("retained.monorepo.completion-metadata-limit")
        if blob.size > 16 * 1024**2:
            raise ValueError("retained.monorepo.completion-document-limit")
        content = _read_direct_bytes(
            path, min(16 * 1024**2, blob.size, self.metadata_left)
        )
        if (
            len(content) != blob.size
            or hashlib.sha256(content).hexdigest() != blob.digest
        ):
            raise ValueError("retained.monorepo.completion-document-changed")
        # Reserve a conservative decoded-container/string/temporary-encoding
        # estimate BEFORE the additional JSON decode. This is accounting for
        # this observation, not a whole-process or existing-checker memory bound.
        tokens = sum(content.count(bytes((value,))) for value in b'{}[],:"')
        self._charge_metadata(8 * len(content) + 256 * (tokens + 1))
        return _parse_document(content)

    def require_original_files(self):
        self.inputs.scope.owners.require_unchanged()
        for path, before in self.inputs._states:
            if _state(path) != before:
                raise ValueError("retained.monorepo.completion-configuration-changed")
        for closure in self.closures:
            closure.require_unchanged()
        for path, (_blob, physical) in self.references.items():
            if _physical(path.lstat()) != physical:
                raise ValueError("retained.monorepo.completion-file-changed")
        if self.streamed is not None:
            self.streamed.require_unchanged()
        for path, (_blob, physical) in self.references.items():
            if _physical(path.lstat()) != physical:
                raise ValueError("retained.monorepo.completion-file-changed")
        if any(directory_node(p) != node for p, node in self.directories.items()):
            raise ValueError("retained.monorepo.completion-directory-changed")
        for group in self.groups.values():
            if not group["closed_tree"] and group["physical"][5] != len(group["paths"]):
                raise ValueError("retained.monorepo.completion-unowned-hardlink")


@dataclass(frozen=True, slots=True, eq=False)
class _OriginalAuthoredMonorepoFiles:
    project: object = field(repr=False)
    context: object = field(repr=False)
    gate: object = field(repr=False)
    present: bool
    original: object = field(repr=False)
    files: object = field(repr=False)
    nodes: tuple = field(repr=False)
    _key: object = field(repr=False)

    def __post_init__(self):
        if self._key is not _KEY:
            raise TypeError("retained.monorepo.original-operation-required")

    def __copy__(self):
        raise TypeError("retained.monorepo.observation-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.monorepo.observation-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.monorepo.observation-not-serializable")

    def require_original_files(self):
        if ProjectConfigurationStore.context(self.project.root) != self.context:
            raise ValueError("retained.monorepo.completion-context-changed")
        if _present(self.gate) != self.present:
            raise ValueError("retained.monorepo.completion-gate-changed")
        if any(directory_node(path) != node for path, node in self.nodes):
            raise ValueError("retained.monorepo.completion-directory-changed")
        if self.files is not None:
            self.files.require_original_files()

    def refresh_current(self, *, deadline):
        """Same full legacy checker; caller supplies ORIGINAL operation deadline."""
        _require_native_completion_deadline(deadline)
        self.require_original_files()
        if self.present:
            current = check_installed_monorepo_components(self.project.root)
            _require_native_completion_deadline(deadline)
            if current != self.original:
                raise ValueError("retained.monorepo.completion-currentness-changed")
        self.require_original_files()
        _require_native_completion_deadline(deadline)


def _capture_authored_monorepo_files(
    inputs, *, environment, maximum_metadata_bytes=None
):
    if type(inputs) is not AuthoredRetainedCargoExecutionInputs:
        raise TypeError("retained.monorepo.original-authored-inputs-required")
    inputs.current_identity(environment=environment)
    wrapper = inputs.materialized.scratch.context
    project = inputs.materialized.files.reviewed.project
    context = wrapper._core._project_context
    gate = project.framework_root / INSTALLATION_ROOT / "installation.json"
    present = _present(gate)
    original, files = None, None
    nodes = tuple(
        (path, directory_node(path))
        for path in (
            project.root,
            project.framework_root,
        )
    )
    if present:
        original = check_installed_monorepo_components(project.root)
        allowance = (
            inputs.scope.owners.maximum_metadata_bytes
            if maximum_metadata_bytes is None
            else maximum_metadata_bytes
        )
        files = _SupplementalOriginalFiles(inputs, allowance)
        # Preserve actual legacy checker coordinates, distinct from its gate selector.
        installation = _direct(project.root, INSTALLATION_ROOT + "/installation.json")
        installed = files.document(installation)
        if {**installed, "identity": canonical_identity(installed).uri} != original:
            raise ValueError("retained.monorepo.completion-installation-changed")
        bundle = _direct(project.root, INSTALLATION_ROOT + "/bundle")
        manifest = files.document(bundle / "bundle.json")
        plan = files.document(bundle / "plan.json")
        paths, _excluded = _validated_scope(plan["source_scope"])
        source = _direct(project.root, installed["source_root"])
        nodes += tuple((path, directory_node(path)) for path in (source, bundle))
        limits = inputs.scope.policy.input_custody.aggregate
        selected = set()

        def select(path, *, metadata=False):
            if metadata:
                files.document_paths.add(path)
            if path not in selected:
                if len(selected) >= limits.maximum_entries:
                    raise ValueError("retained.monorepo.completion-selection-limit")
                files._charge_metadata(256 + len(str(path).encode()) * 4)
                selected.add(path)

        for relative in manifest["files"]:
            select(_direct(bundle, relative), metadata=True)
        for name in installed["components"]:
            select(
                _direct(project.root, INSTALLATION_ROOT + f"/receipts/{name}.json"),
                metadata=True,
            )
            for leaf in ("binding.json", "component.md"):
                select(
                    _direct(project.root, f"components/{name}/{leaf}"), metadata=True
                )
        for relative in paths:
            select(_direct(source, relative))
        files.cover_selected_closures(selected)
        for path in sorted(selected):
            files.observe(path)
        if check_installed_monorepo_components(project.root) != original:
            raise ValueError("retained.monorepo.completion-currentness-changed")
        files.require_original_files()
    result = _OriginalAuthoredMonorepoFiles(
        project,
        context,
        gate,
        present,
        original,
        files,
        nodes,
        _KEY,
    )
    inputs.current_identity(environment=environment)
    result.require_original_files()
    return result
