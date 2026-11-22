"""Actual provisioning source facts with optional monorepo completion.

This distinct frontdoor consumes an internally captured readonly source partition.
It never fabricates ExecutionInputs, CARGO_HOME/config capture or materialization.
Selected additional source files debit the original source aggregate allowance.
"""

from literate_ai.adapters.authored_retained_cargo_monorepo_observation import (
    _KEY,
    _find,
    _OriginalAuthoredMonorepoFiles,
    _present,
    _SupplementalOriginalFiles,
)
from literate_ai.adapters.authored_retained_cargo_provisioning_source import (
    _OriginalAuthoredProvisioningSource,
    _OriginalInitialScratchSource,
)
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.harness_tree import _validated_scope
from literate_ai.adapters.monorepo_adoption import _direct
from literate_ai.adapters.monorepo_components import (
    INSTALLATION_ROOT,
    check_installed_monorepo_components,
)
from literate_ai.adapters.streamed_file_custody import _physical
from literate_ai.contracts.identity import canonical_identity


class _ProvisioningSupplementalFiles(_SupplementalOriginalFiles):
    """Same bounded file mechanics, based only on ACTUALLY observed source."""

    def __init__(self, source, maximum_metadata_bytes):
        if type(source) not in (
            _OriginalAuthoredProvisioningSource,
            _OriginalInitialScratchSource,
        ):
            raise TypeError("retained.provision.original-source-partition-required")
        self.source = source
        reviewed = source.current.reviewed
        self.root = reviewed.project.root
        aggregate = reviewed.policy.input_custody.aggregate
        self.aggregate = aggregate
        counts = source.source_counts
        self.files_left = aggregate.maximum_files - counts["files"]
        self.entries_left = aggregate.maximum_entries - counts["entries"]
        self.bytes_left = aggregate.maximum_total_bytes - counts["bytes"]
        if min(self.files_left, self.entries_left, self.bytes_left) < 0:
            raise ValueError("retained.provision.source-aggregate-exhausted")
        limits = reviewed.project.definition.scale_limits
        if limits is not None:
            self.files_left = min(self.files_left, limits.pinned_input_files)
            self.bytes_left = min(self.bytes_left, limits.pinned_input_total_bytes)
        self.member_limit = aggregate.maximum_file_bytes
        if type(maximum_metadata_bytes) is not int or not (
            1 <= maximum_metadata_bytes <= source.source.maximum_metadata_bytes
        ):
            raise ValueError("retained.monorepo.completion-metadata-allowance")
        self.metadata_left = maximum_metadata_bytes
        self.references, self.groups, self.directories = {}, {}, {}
        self.closures = (
            reviewed._inputs,
            source.wrapper._core._inputs,
            *source.wrapper._core._closures,
        )
        self._charge_metadata(256 * len(self.closures))
        self.covered = {}
        self.streamed = None
        self.document_paths = set()
        # No execution ancestor/config or CARGO_HOME owner was captured here.
        # Reusing actual wrapper pins saves hashing, never the source allowance.
        self.configuration_files = set()

    def _tree_coverage(self, path):
        tree = self.source.source
        if path == tree.root or not path.is_relative_to(tree.root):
            return None
        name = path.relative_to(tree.root).as_posix()
        row = _find(tree.files, name, key=lambda item: item[0])
        if row is None:
            alias = _find(tree.aliases, name, key=lambda item: item.path)
            if alias is not None and alias.kind == "hardlink":
                row = _find(tree.files, alias.target, key=lambda item: item[0])
        return None if row is None else row[1]

    def _covered_directory(self, path):
        if path in (self.root, self.source.current.reviewed.project.framework_root):
            return True
        tree = self.source.source
        if path == tree.root:
            return True
        return (
            path.is_relative_to(tree.root)
            and _find(tree.directories, path.relative_to(tree.root).as_posix())
            is not None
        )

    def require_original_files(self):
        self.source.require_original_files()
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
        if any(directory_node(path) != node for path, node in self.directories.items()):
            raise ValueError("retained.monorepo.completion-directory-changed")
        for group in self.groups.values():
            if not group["closed_tree"] and group["physical"][5] != len(group["paths"]):
                raise ValueError("retained.monorepo.completion-unowned-hardlink")


def _capture_provisioning_monorepo(source, *, maximum_metadata_bytes=None):
    if type(source) not in (
        _OriginalAuthoredProvisioningSource,
        _OriginalInitialScratchSource,
    ):
        raise TypeError("retained.provision.original-source-partition-required")
    source.require_live()
    wrapper = source.wrapper
    project = source.current.reviewed.project
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
            source.source.maximum_metadata_bytes
            if maximum_metadata_bytes is None
            else maximum_metadata_bytes
        )
        files = _ProvisioningSupplementalFiles(source, allowance)
        # Preserve actual legacy checker coordinates, distinct from its gate selector.
        installation = _direct(project.root, INSTALLATION_ROOT + "/installation.json")
        installed = files.document(installation)
        if {**installed, "identity": canonical_identity(installed).uri} != original:
            raise ValueError("retained.monorepo.completion-installation-changed")
        bundle = _direct(project.root, INSTALLATION_ROOT + "/bundle")
        manifest = files.document(bundle / "bundle.json")
        plan = files.document(bundle / "plan.json")
        paths, _excluded = _validated_scope(plan["source_scope"])
        installed_source = _direct(project.root, installed["source_root"])
        nodes += tuple(
            (path, directory_node(path)) for path in (installed_source, bundle)
        )
        limits = source.current.reviewed.policy.input_custody.aggregate
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
            select(_direct(installed_source, relative))
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
    source.require_live()
    result.require_original_files()
    return result
