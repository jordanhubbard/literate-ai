"""Explicit SDK distribution resources joined to original registered BUILD custody.

No cache record, path or serialized resource value supplies execution authority.
The local lifecycle owns selection and retains its live invocation/build grants.
"""

import hashlib
import stat
import tempfile
from pathlib import Path, PurePosixPath

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    capture_materialized_files,
    encode_directory_export,
    read_directory_export,
)
from literate_ai.adapters.native_sdk_tree_custody import capture_native_sdk_tree
from literate_ai.adapters.node_sdk_packaging import require_node_sdk_tarball_files
from literate_ai.application.standard_node_sdk_admission import (
    capture_node_sdk_lifecycle,
)
from literate_ai.contracts import BlobRef, canonical_identity
from literate_ai.contracts.executable_components.packages import (
    PackageFileKind,
    PackageInput,
)
from literate_ai.contracts.retained_project import RetainedProjectLimits
from literate_ai.storage.cas import FileSystemCAS

_LIMITS = RetainedProjectLimits(8192, 40 * 1024**2, 128 * 1024**2)


def _original_stamps(root, files):
    require_safe_directory(root)
    files_current = capture_materialized_files(root, files)
    parents = tuple(
        (parent, (value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode)))
        for parent in root.parents
        for value in (parent.lstat(),)
    )

    def close():
        for parent, expected in parents:
            value = parent.lstat()
            if (value.st_dev, value.st_ino, stat.S_IFMT(value.st_mode)) != expected:
                raise ValueError("SDK package original directory ancestry changed")
        files_current()

    close()
    return close


def _capture(root, parent):
    """Use the existing bounded no-follow capture before generic tree readers."""
    require_safe_directory(root)
    with tempfile.TemporaryDirectory(prefix="sdk-package-capture-", dir=parent) as raw:
        store = FileSystemCAS(Path(raw) / "cas")
        tree = capture_native_sdk_tree(
            root, store=store, limits=_LIMITS, case_sensitive=False
        )
        if tree.aliases:
            raise ValueError("SDK packaging cannot capture aliases")
        files = tuple(
            DirectoryExportFile(
                item.path,
                store.get_bytes(item.blob),
                stat.S_IMODE((root / item.path).lstat().st_mode),
            )
            for item in tree.files
        )
        _original_stamps(root, files)()
        return files


def require_node_sdk_build_custody(plan, evidence, files):
    """Compare bounded captured DATA with the BUILD owner's exact custody digest.

    The caller must obtain ``evidence`` from its original registered build owner;
    constructing this digest or matching a copied record grants no admission.
    """
    tree = canonical_identity(
        {
            "schema": "literate-ai/local-source-tree@1",
            "files": [
                {"path": item.path, "sha256": hashlib.sha256(item.content).hexdigest()}
                for item in sorted(
                    files, key=lambda item: PurePosixPath(item.path).parts
                )
            ],
        }
    )
    if (
        canonical_identity(
            {
                "schema": "literate-ai/local-artifact-custody@1",
                "build_plan_identity": plan.identity.uri,
                "artifact_tree_identity": tree.uri,
                "export_identities": [item.identity.uri for item in evidence.exports],
            }
        )
        != evidence.artifact_custody_identity
    ):
        raise ValueError("SDK package artifact differs from registered BUILD custody")


class LocalNodeSDKPackageResources:
    """Finite original source/product stamps through local package registration.

    This object is an internal resource adapter, never a reusable capability.
    It cannot outlive the original admitted SDK operation. New operations must
    select current original build evidence and capture their inputs again.
    """

    def __init__(self, ports, plan, export, *, exports):
        from literate_ai.adapters.lifecycle.standard_local import (
            LocalStandardLifecyclePorts,
        )

        if type(ports) is not LocalStandardLifecyclePorts:
            raise TypeError("SDK package resources require original local ports")
        owner = capture_node_sdk_lifecycle()
        if owner is None:
            raise ValueError("SDK packaging requires original live invocation")
        self._owner = owner
        self._ports, self._plan, self._export = ports, plan, export
        self._original_ports = ports
        self._root = ports.artifact_path(export).parent
        self._target = ports.node_sdk_targets[plan.component_revision.uri]
        self._contract = ports._contract(plan.component_revision)
        self._target.require_contract(self._contract)
        # The first access is a bounded capture, not a generic tree hash.
        owner()
        files = _capture(self._root, ports.object_root)
        self._stamps = _original_stamps(self._root, files)
        self._source_root = ports.source_trees.registered_root(
            plan.request.source_tree_identity
        )
        self._source_custody = ports.source_trees.registered_evidence(
            plan.request.source_tree_identity
        )
        source_files = _capture(self._source_root, ports.object_root)
        self._source_stamps = _original_stamps(self._source_root, source_files)
        self._original_stamps = self._stamps
        self._original_source_stamps = self._source_stamps
        ports.source_trees.resolve(plan.request.source_tree_identity)
        self._evidence = ports.build_evidence_for_test(plan, (export,))
        self._inputs = ports.build_execution_inputs(plan)
        self._original_input_values = self._input_values()
        self._target_identity = self._target.identity
        self._original_owner = owner
        self._original_resources = None
        self._package_records = None
        self._export_inputs = self._original_export_inputs = ()
        self.require_current()
        self._export_inputs = self._capture_exports(exports)
        self._original_export_inputs = self._export_inputs
        if export.identity not in {entry[1] for entry in self._export_inputs}:
            raise ValueError("SDK package closure lacks the original root export")
        self.require_current()
        require_node_sdk_build_custody(plan, self._evidence, files)
        prefix = export.export_id + "/"
        sdk_files = tuple(
            sorted(
                (
                    DirectoryExportFile(
                        item.path[len(prefix) :], item.content, item.mode
                    )
                    for item in files
                    if item.path.startswith(prefix)
                ),
                key=lambda item: item.path,
            )
        )
        encoded = encode_directory_export(
            sdk_files, max_bytes=40 * 1024**2, max_entries=4096
        )
        if (
            len(encoded) != export.blob.size
            or hashlib.sha256(encoded).hexdigest() != export.blob.digest
        ):
            raise ValueError("SDK package export differs from original BUILD")
        distributions = tuple(item for item in files if item.path == "node-sdk.tgz")
        if len(distributions) != 1 or distributions[0].mode & 0o111:
            raise ValueError("SDK package requires one nonexecutable distribution")
        self._content = distributions[0].content
        require_node_sdk_tarball_files(sdk_files, self._content)
        self._blob = BlobRef(
            hashlib.sha256(self._content).hexdigest(),
            len(self._content),
            media_type="application/gzip",
        )
        self.inputs = (
            PackageInput(
                "root/node-sdk.tgz",
                "node-sdk-distribution",
                PackageFileKind.RESOURCE,
                self._evidence.artifact_custody_identity,
                export.target_identity,
                self._blob,
            ),
        )
        self._original_resources = (self.inputs, self._blob, self._content)
        self._original_resource_identity = self._resource_identity()
        self._package_root = self._package_stamps = None
        self._package_records = None
        self.require_current()

    def _require_original_resources(self):
        if self._original_resources is None:
            return  # Private construction before any package consumer is called.
        inputs, blob, content = self._original_resources
        if (
            self.inputs != inputs
            or self._blob != blob
            or self._content is not content
            or len(content) != blob.size
            or hashlib.sha256(content).hexdigest() != blob.digest
            or self._resource_identity() != self._original_resource_identity
        ):
            raise ValueError("SDK package original resource inputs changed")

    def _resource_identity(self):
        return canonical_identity(
            {
                "inputs": [item.to_dict() for item in self.inputs],
                "blob": self._blob.to_dict(),
            }
        )

    def _input_values(self):
        inputs = self._inputs
        return (
            inputs.intent.identity,
            inputs.authorization.identity,
            inputs.contract.identity,
            tuple(item.identity for item in inputs.providers),
            tuple(item.identity for item in inputs.package_artifacts),
            inputs.dependency_resolution,
            inputs.build_binding,
        )

    def _capture_exports(self, exports):
        entries = []
        total = count = 0
        identities = set()
        for candidate in exports:
            identity = candidate.identity
            export = self._ports._exports_by_identity.get(identity.uri)
            if (
                export is None
                or export != candidate
                or export.role != "library"
                or identity in identities
            ):
                raise ValueError(
                    "SDK package requires exact registered library exports"
                )
            identities.add(identity)
            if export.blob.size > _LIMITS.max_total_bytes:
                raise ValueError("SDK package export exceeds capture limits")
            content = self._ports.read_artifact_blob(export.blob)
            rows = read_directory_export(
                content,
                export.blob,
                max_bytes=_LIMITS.max_total_bytes,
                max_entries=_LIMITS.max_entries,
            )
            total += len(content)
            count += len(rows)
            if total > _LIMITS.max_total_bytes or count > _LIMITS.max_entries:
                raise ValueError("SDK package closure exceeds capture limits")
            root = self._ports._artifact_paths[identity.uri] / export.export_id
            stamps = _original_stamps(root, rows)
            # Primitive immutable rows cannot change with an aliased file DTO.
            primitives = tuple((row.path, row.content, row.mode) for row in rows)
            entries.append((export, identity, root, content, primitives, stamps))
        return tuple(entries)

    def require_current(self):
        if (
            self._owner is not self._original_owner
            or self._ports is not self._original_ports
        ):
            raise ValueError("SDK package original operation owner changed")
        self._owner()
        ports, plan, export = self._ports, self._plan, self._export
        current = ports.build_evidence_for_test(plan, (export,))
        self._owner()
        self._stamps()
        self._source_stamps()
        now = ports.clock()
        self._require_original_resources()
        self._require_package_metadata()
        if (
            self._owner is not self._original_owner
            or self._ports is not self._original_ports
            or self._stamps is not self._original_stamps
            or self._source_stamps is not self._original_source_stamps
            or self._export_inputs is not self._original_export_inputs
            or ports._plans_by_revision.get(plan.component_revision.uri) is not plan
            or ports._contract(plan.component_revision) is not self._contract
            or ports.node_sdk_targets.get(plan.component_revision.uri)
            is not self._target
            or self._target.identity != self._target_identity
            or ports._exports_by_identity.get(export.identity.uri) != export
            or ports._build_evidence.get(self._evidence.identity.uri)
            is not self._evidence
            or ports._artifact_paths.get(export.identity.uri) != self._root
            or current is not self._evidence
            or ports._plan_inputs_by_revision.get(plan.component_revision.uri)
            is not self._inputs
            or self._input_values() != self._original_input_values
            or ports.source_trees.registered_root(plan.request.source_tree_identity)
            != self._source_root
            or ports.source_trees.registered_evidence(plan.request.source_tree_identity)
            is not self._source_custody
            or self._source_custody.identity != self._evidence.source_custody_identity
        ):
            raise ValueError("SDK package original build membership changed")
        # All blocking policy/input reads precede final finite original stamps.
        self._stamps()
        self._source_stamps()
        for original, identity, root, _content, _rows, stamps in self._export_inputs:
            if (
                original.identity != identity
                or ports._exports_by_identity.get(identity.uri) is not original
                or ports._artifact_paths.get(identity.uri) != root.parent
            ):
                raise ValueError("SDK package original export membership changed")
            stamps()
        self._inputs.authorization.grant.require_valid(
            self._inputs.intent.build_request, now=now
        )

    def owns_blob(self, reference):
        return reference == self._blob

    def read_blob(self, reference):
        self.require_current()
        if not self.owns_blob(reference):
            raise ValueError("SDK resource is outside the explicit package inputs")
        content = self._content
        self.require_current()
        return content

    def materialize(self, root):
        self.require_current()
        destination = root / "root/node-sdk.tgz"
        content = self._original_resources[2]
        require_safe_directory(root)
        require_safe_directory(destination.parent)
        with destination.open("xb") as stream:
            stream.write(content)
        destination.chmod(0o644)
        self.require_current()

    def materialize_export(self, export, destination):
        """Write immutable validated rows; never copy or traverse producer paths."""
        self.require_current()
        entries = tuple(
            entry for entry in self._export_inputs if entry[1] == export.identity
        )
        if len(entries) != 1:
            raise ValueError("SDK package export is outside the original closure")
        _original, _identity, _source, content, rows, _stamps = entries[0]
        require_safe_directory(destination.parent)
        destination.mkdir()
        for path, payload, mode in rows:
            target = destination.joinpath(*PurePosixPath(path).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            require_safe_directory(target.parent)
            with target.open("xb") as stream:
                stream.write(payload)
            target.chmod(mode)
        self.require_current()
        _original_stamps(
            destination,
            tuple(
                DirectoryExportFile(path, payload, mode) for path, payload, mode in rows
            ),
        )()
        return content

    def capture_package(self, root, plan, read_blob):
        self.require_current()
        expected = []
        total = 0
        for item in plan.inputs:
            if item.blob.size > _LIMITS.max_total_bytes:
                raise ValueError("SDK package input exceeds capture limits")
            content = read_blob(item.blob)
            if item.kind is PackageFileKind.ARTIFACT:
                if item.role != "library":
                    raise ValueError("SDK package requires directory library artifacts")
                rows = read_directory_export(
                    content,
                    item.blob,
                    max_bytes=_LIMITS.max_total_bytes,
                    max_entries=_LIMITS.max_entries,
                )
                rows = tuple(
                    DirectoryExportFile(
                        item.path + "/" + row.path, row.content, row.mode
                    )
                    for row in rows
                )
            elif item.kind is PackageFileKind.RESOURCE and self.owns_blob(item.blob):
                rows = (DirectoryExportFile(item.path, content, 0o644),)
            else:
                raise ValueError("SDK package contains an unsupported resource")
            total += sum(len(row.content) for row in rows)
            expected.extend(rows)
            if total > _LIMITS.max_total_bytes or len(expected) > _LIMITS.max_entries:
                raise ValueError("SDK package exceeds capture limits")
        expected = tuple(sorted(expected, key=lambda row: row.path))
        files = _capture(root, self._ports.object_root)
        if tuple(sorted(files, key=lambda row: row.path)) != expected:
            raise ValueError(
                "SDK materialized package differs from exact planned inputs"
            )
        self.require_current()
        stamps = _original_stamps(root, files)
        stamps()
        return files, stamps

    def bind_package(self, root, files):
        self.require_current()
        self._package_root = root
        self._package_stamps = _original_stamps(root, files)
        self.require_packaged(root)

    def bind_package_metadata(self, plan, result, *, plan_identity, result_identity):
        if self._package_records is not None:
            raise ValueError("SDK package metadata is already bound")
        self._package_records = (plan, result, plan_identity, result_identity)
        self.require_current()
        self._require_package_metadata()

    def _require_package_metadata(self):
        if self._package_records is None:
            return  # Internal construction before any package is registered.
        plan, result, plan_identity, result_identity = self._package_records
        if plan.identity != plan_identity or result.identity != result_identity:
            raise ValueError("SDK package original metadata changed")

    def require_packaged(self, root):
        self.require_current()
        self._require_package_metadata()
        if self._package_root != root or self._package_stamps is None:
            raise ValueError("SDK package has no original materialized custody")
        self._package_stamps()

    def command_inputs(self, custody):
        """Select only the original registered package's SDK and protected tests.

        These are command DATA; the caller still needs the original operation,
        selected runtime and phase permission. No arbitrary packaged path lookup.
        """
        self.require_packaged(custody.root)
        export = self._export
        path = custody.root / "root" / export.export_id
        if (
            custody.node_sdk_resources is not self
            or self._package_records is None
            or custody.package_plan is not self._package_records[0]
            or custody.package_result is not self._package_records[1]
            or self._ports._project_packages.get(custody.package_result.identity.uri)
            is not custody
            or custody.root_plan is not self._plan
            or custody.package_plan.root_component_revision
            != self._plan.component_revision
            or custody.package_plan.root_artifact_identity != export.identity
            or custody.package_result.package_plan_identity
            != custody.package_plan.identity
            or custody.artifact_paths.get(export.identity.uri) != path
        ):
            raise ValueError("SDK command differs from original packaged custody")
        return self._contract, self._source_root, path
