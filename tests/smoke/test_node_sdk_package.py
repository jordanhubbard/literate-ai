"""Bounded SDK product capture and exact original artifact-custody comparison."""

import hashlib
import os
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path, PurePosixPath
from types import SimpleNamespace

from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    capture_materialized_files,
    encode_directory_export,
)
from literate_ai.adapters.node_sdk_package import (
    LocalNodeSDKPackageResources,
    _capture,
    _original_stamps,
    require_node_sdk_build_custody,
)
from literate_ai.application.standard_plan_finalization import (
    StandardPlanFinalizationInputs,
)
from literate_ai.contracts import BlobRef, canonical_identity
from literate_ai.contracts.executable_components.packages import (
    PackageFileKind,
    PackageInput,
    PackageKind,
    PackagePlan,
)
from literate_ai.security.policy import (
    AuthorizationError,
    BuildAuthorization,
    BuildRequest,
    SecurityProfile,
)


class NodeSDKPackageCustodyTests(unittest.TestCase):
    def guard_fixture(self, root):
        """Exercise the real closing guard, without constructing admission."""
        revision = canonical_identity("unit guard revision")
        source = canonical_identity("unit guard source")
        plan = SimpleNamespace(
            component_revision=revision,
            request=SimpleNamespace(source_tree_identity=source),
        )
        export = SimpleNamespace(
            identity=canonical_identity("unit guard export"), export_id="library"
        )
        request = BuildRequest(
            effective_revision_digest=revision.uri,
            source_bundle_digest=source.uri,
            builder_id="unit-sdk-package-guard@1",
            toolchain_digest=canonical_identity("tool").uri,
            sandbox_profile="local-explicit-host-process",
            requested_privileges=(),
            allowed_outputs=("artifact",),
        )
        issued = datetime.now(UTC)
        times = [issued]
        digest = canonical_identity(request.to_dict()).uri
        grant = BuildAuthorization(
            "unit-grant",
            digest,
            digest,
            revision.uri,
            "unit operator",
            "unit only",
            SecurityProfile.CONSTRAINED,
            (),
            issued,
            issued + timedelta(seconds=1),
        )
        contract = SimpleNamespace(identity=canonical_identity("unit contract"))
        inputs = StandardPlanFinalizationInputs(
            intent=SimpleNamespace(
                build_request=request, identity=canonical_identity("unit intent")
            ),
            authorization=SimpleNamespace(
                grant=grant, identity=canonical_identity("unit authorization")
            ),
            contract=contract,
            providers=(),
            package_artifacts=(),
            dependency_resolution="none",
        )
        custody = SimpleNamespace(identity=canonical_identity("unit source custody"))
        target = SimpleNamespace(identity=canonical_identity("unit target"))
        evidence = SimpleNamespace(
            identity=canonical_identity("unit evidence"),
            source_custody_identity=custody.identity,
        )
        ports = SimpleNamespace(
            build_evidence_for_test=lambda *_args: evidence,
            clock=lambda: times[0],
            _plans_by_revision={revision.uri: plan},
            _contract=lambda _revision: contract,
            node_sdk_targets={revision.uri: target},
            _exports_by_identity={export.identity.uri: export},
            _build_evidence={evidence.identity.uri: evidence},
            _artifact_paths={export.identity.uri: root},
            _plan_inputs_by_revision={revision.uri: inputs},
            source_trees=SimpleNamespace(
                registered_root=lambda _source: root,
                registered_evidence=lambda _source: custody,
            ),
        )
        resource = object.__new__(LocalNodeSDKPackageResources)
        resource._owner = lambda: None
        resource._original_owner = resource._owner
        resource._ports, resource._plan, resource._export = ports, plan, export
        resource._original_ports = ports
        resource._root = resource._source_root = root
        resource._source_custody = custody
        resource._target, resource._target_identity = target, target.identity
        resource._contract, resource._evidence = contract, evidence
        resource._inputs = inputs
        resource._original_input_values = resource._input_values()
        resource._stamps = resource._source_stamps = lambda: None
        resource._original_stamps = resource._stamps
        resource._original_source_stamps = resource._source_stamps
        resource._original_resources = None
        resource._package_records = None
        resource._export_inputs = resource._original_export_inputs = ()
        return resource, ports, times, issued

    def test_real_plan_input_record_and_late_metadata_changes(self):
        resource, ports, _times, issued = self.guard_fixture(Path("/unit-fixture"))
        self.assertIsInstance(resource._inputs, StandardPlanFinalizationInputs)
        self.assertFalse(hasattr(resource._inputs, "identity"))
        resource.require_current()

        def clock():
            object.__setattr__(resource._inputs, "dependency_resolution", "npm")
            return issued

        ports.clock = clock
        with self.assertRaisesRegex(ValueError, "original build membership"):
            resource.require_current()

    def test_packaged_command_path_plan_and_registry_substitutions_are_rejected(self):
        for mutation in ("path", "plan", "coordinated-plan-result", "registry"):
            with self.subTest(mutation=mutation), tempfile.TemporaryDirectory() as raw:
                root = Path(raw).resolve()
                resource, ports, _times, issued = self.guard_fixture(root)
                export = resource._export
                target = canonical_identity("target")
                plan = PackagePlan(
                    resource._plan.component_revision,
                    canonical_identity("lock"),
                    target,
                    canonical_identity("graph"),
                    canonical_identity("link"),
                    export.identity,
                    PackageKind.DIRECTORY,
                    canonical_identity("packager"),
                    (
                        PackageInput(
                            "root/library",
                            "library",
                            PackageFileKind.ARTIFACT,
                            export.identity,
                            target,
                            BlobRef("0" * 64, 0),
                        ),
                    ),
                    (),
                    (),
                )
                result = SimpleNamespace(
                    identity=canonical_identity("package result"),
                    package_plan_identity=plan.identity,
                )
                custody = SimpleNamespace(
                    node_sdk_resources=resource,
                    package_plan=plan,
                    package_result=result,
                    root_plan=resource._plan,
                    root=root,
                    artifact_paths={export.identity.uri: root / "root/library"},
                )
                ports._project_packages = {result.identity.uri: custody}
                package_file = root / "root/library/index.js"
                package_file.parent.mkdir(parents=True)
                package_file.write_bytes(b"original")
                package_file.chmod(0o644)
                resource._package_root = root
                resource._package_stamps = _original_stamps(
                    root,
                    (DirectoryExportFile("root/library/index.js", b"original", 0o644),),
                )
                resource.bind_package_metadata(
                    plan,
                    result,
                    plan_identity=plan.identity,
                    result_identity=result.identity,
                )
                resource.command_inputs(custody)

                def clock(
                    mutation=mutation,
                    custody=custody,
                    export=export,
                    root=root,
                    plan=plan,
                    ports=ports,
                    issued=issued,
                    result=result,
                ):
                    if mutation == "path":
                        custody.artifact_paths[export.identity.uri] = root / "outside"
                    elif mutation in {"plan", "coordinated-plan-result"}:
                        object.__setattr__(
                            plan,
                            "packager_identity",
                            canonical_identity("foreign packager"),
                        )
                        if mutation == "coordinated-plan-result":
                            result.package_plan_identity = plan.identity
                    else:
                        ports._project_packages.clear()
                    return issued

                ports.clock = clock
                with self.assertRaisesRegex(
                    ValueError, "original (packaged custody|metadata changed)"
                ):
                    resource.command_inputs(custody)
                resource._package_stamps()
                self.assertEqual(package_file.read_bytes(), b"original")

    def setUp(self):
        self.plan = SimpleNamespace(identity=canonical_identity("original build plan"))
        self.exports = (
            SimpleNamespace(identity=canonical_identity("original export")),
        )
        self.files = (
            DirectoryExportFile("sdk/index.js", b"exports.value=1;\n", 0o644),
            DirectoryExportFile("node-sdk.tgz", b"fixture archive bytes", 0o644),
        )
        tree = canonical_identity(
            {
                "schema": "literate-ai/local-source-tree@1",
                "files": [
                    {"path": f.path, "sha256": hashlib.sha256(f.content).hexdigest()}
                    for f in sorted(
                        self.files, key=lambda f: PurePosixPath(f.path).parts
                    )
                ],
            }
        )
        self.evidence = SimpleNamespace(
            exports=self.exports,
            artifact_custody_identity=canonical_identity(
                {
                    "schema": "literate-ai/local-artifact-custody@1",
                    "build_plan_identity": self.plan.identity.uri,
                    "artifact_tree_identity": tree.uri,
                    "export_identities": [item.identity.uri for item in self.exports],
                }
            ),
        )

    def test_full_inventory_not_only_the_export_is_bound(self):
        require_node_sdk_build_custody(self.plan, self.evidence, self.files)
        for files in (
            self.files[:1],
            (self.files[0], replace(self.files[1], content=b"different archive")),
            (*self.files, DirectoryExportFile("extra", b"extra", 0o644)),
        ):
            with self.subTest(paths=[f.path for f in files]):
                with self.assertRaisesRegex(ValueError, "registered BUILD custody"):
                    require_node_sdk_build_custody(self.plan, self.evidence, files)
        with self.assertRaises(ValueError):
            require_node_sdk_build_custody(
                SimpleNamespace(identity=canonical_identity("foreign build plan")),
                self.evidence,
                self.files,
            )

    @unittest.skipUnless(os.name == "posix", "live capture needs POSIX change stamps")
    def test_capture_rejects_aliases_and_special_files_before_generic_hashing(self):
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw).resolve()
            root = parent / "product"
            root.mkdir()
            (root / "node-sdk.tgz").write_bytes(b"archive")
            self.assertEqual(_capture(root, parent)[0].content, b"archive")
            (root / "outside-link").symlink_to(parent / "missing")
            with self.assertRaises((ValueError, TypeError)):
                _capture(root, parent)
            (root / "outside-link").unlink()
            if hasattr(os, "mkfifo"):
                os.mkfifo(root / "node-sdk.tgz.fifo")
                with self.assertRaises(ValueError):
                    _capture(root, parent)

    def test_resource_mutations_cannot_redirect_materialization(self):
        # Unit seam for the immutable resource check; this deliberately mints no
        # real ports, invocation or BUILD authority. The canonical case uses all
        # original lifecycle owners.
        content = b"original distribution"
        blob = BlobRef(hashlib.sha256(content).hexdigest(), len(content))
        inputs = (
            PackageInput(
                "root/node-sdk.tgz",
                "node-sdk-distribution",
                PackageFileKind.RESOURCE,
                canonical_identity("original custody"),
                canonical_identity("target"),
                blob,
            ),
        )
        for field, value in (
            ("inputs", (replace(inputs[0], path="elsewhere/node-sdk.tgz"),)),
            ("inputs", (SimpleNamespace(path="../escaped.tgz"),)),
            ("_content", b"substituted distribution"),
            ("_blob", BlobRef("0" * 64, len(content))),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as raw:
                root = Path(raw) / "package"
                resource, ports, _times, issued = self.guard_fixture(root)
                resource.inputs, resource._blob, resource._content = (
                    inputs,
                    blob,
                    content,
                )
                resource._original_resources = (inputs, blob, content)
                resource._original_resource_identity = resource._resource_identity()

                # Inject corruption from the final clock callback before opening.
                def clock(resource=resource, field=field, value=value, issued=issued):
                    setattr(resource, field, value)
                    return issued

                ports.clock = clock
                root.mkdir()
                (root / "root").mkdir()
                with self.assertRaisesRegex(ValueError, "original resource inputs"):
                    resource.materialize(root)
                self.assertFalse((root / "root/node-sdk.tgz").exists())
                self.assertFalse((root.parent / "escaped.tgz").exists())

    def test_expiry_during_custody_checks_uses_the_final_clock_sample(self):
        with tempfile.TemporaryDirectory() as raw:
            resource, _ports, times, issued = self.guard_fixture(Path(raw))
            resource.require_current()

            def slow_stamp_check():
                times[0] = issued + timedelta(seconds=2)

            resource._source_stamps = slow_stamp_check
            resource._original_source_stamps = slow_stamp_check
            with self.assertRaises(AuthorizationError):
                resource.require_current()

    def test_in_place_input_mutation_cannot_change_original_provenance(self):
        for field, value in (
            ("path", "elsewhere/node-sdk.tgz"),
            ("source_identity", canonical_identity("foreign custody")),
            ("target_identity", canonical_identity("foreign target")),
        ):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as raw:
                root = Path(raw) / "package"
                root.mkdir()
                (root / "root").mkdir()
                resource, ports, _times, issued = self.guard_fixture(root)
                content = b"original distribution"
                blob = BlobRef(hashlib.sha256(content).hexdigest(), len(content))
                item = PackageInput(
                    "root/node-sdk.tgz",
                    "node-sdk-distribution",
                    PackageFileKind.RESOURCE,
                    canonical_identity("original custody"),
                    canonical_identity("target"),
                    blob,
                )
                resource.inputs, resource._blob, resource._content = (
                    (item,),
                    blob,
                    content,
                )
                resource._original_resources = (resource.inputs, blob, content)
                resource._original_resource_identity = resource._resource_identity()

                def clock(item=item, field=field, value=value, issued=issued):
                    object.__setattr__(item, field, value)
                    return issued

                ports.clock = clock
                with self.assertRaisesRegex(ValueError, "original resource inputs"):
                    resource.materialize(root)
                self.assertFalse((root / "root/node-sdk.tgz").exists())

    @unittest.skipUnless(os.name == "posix", "live capture needs POSIX change stamps")
    def test_package_capture_cannot_adopt_changed_staged_files(self):
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw).resolve()
            root = parent / "package"
            path = root / "root/library/index.js"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"original")
            path.chmod(0o644)
            content = encode_directory_export(
                (DirectoryExportFile("index.js", b"original", 0o644),),
                max_bytes=4096,
                max_entries=10,
            )
            blob = BlobRef(hashlib.sha256(content).hexdigest(), len(content))
            plan = SimpleNamespace(
                inputs=(
                    PackageInput(
                        "root/library",
                        "library",
                        PackageFileKind.ARTIFACT,
                        canonical_identity("export"),
                        canonical_identity("target"),
                        blob,
                    ),
                )
            )
            resource = object.__new__(LocalNodeSDKPackageResources)
            resource._ports = SimpleNamespace(object_root=parent)
            resource.require_current = lambda: None
            files, stamps = resource.capture_package(root, plan, lambda _blob: content)
            stamps()
            self.assertEqual(files[0].content, b"original")

            def substituted(_blob):
                path.write_bytes(b"modified")
                return content

            with self.assertRaisesRegex(ValueError, "exact planned inputs"):
                resource.capture_package(root, plan, substituted)

    @unittest.skipUnless(os.name == "posix", "live capture needs POSIX change stamps")
    def test_final_clock_provider_substitution_is_rejected_before_materializing(self):
        for kind in ("link", "fifo"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as raw:
                parent = Path(raw).resolve()
                root = parent / "provider/lib"
                root.mkdir(parents=True)
                path = root / "index.js"
                path.write_bytes(b"original")
                path.chmod(0o644)
                rows = (DirectoryExportFile("index.js", b"original", 0o644),)
                stamps = capture_materialized_files(root, rows)
                resource, ports, _times, issued = self.guard_fixture(parent / "sdk")
                provider = SimpleNamespace(identity=canonical_identity("provider"))
                ports._exports_by_identity[provider.identity.uri] = provider
                ports._artifact_paths[provider.identity.uri] = root.parent
                resource._export_inputs = (
                    (
                        provider,
                        provider.identity,
                        root,
                        b"archive",
                        (("index.js", b"original", 0o644),),
                        stamps,
                    ),
                )
                resource._original_export_inputs = resource._export_inputs

                def clock(path=path, kind=kind, issued=issued, parent=parent):
                    path.unlink()
                    if kind == "link":
                        path.symlink_to(parent / "outside")
                    else:
                        os.mkfifo(path)
                    return issued

                ports.clock = clock
                destination = parent / "destination"
                with self.assertRaises(ValueError):
                    resource.materialize_export(provider, destination)
                self.assertFalse(destination.exists())

    @unittest.skipUnless(os.name == "posix", "live capture needs POSIX change stamps")
    def test_parent_alias_cannot_reuse_unchanged_child_inodes(self):
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw).resolve()
            original = parent / "original"
            root = original / "library"
            root.mkdir(parents=True)
            (root / "index.js").write_bytes(b"original")
            (root / "index.js").chmod(0o644)
            close = _original_stamps(
                root, (DirectoryExportFile("index.js", b"original", 0o644),)
            )
            moved = parent / "moved"
            original.rename(moved)
            original.symlink_to(moved, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "ancestry"):
                close()
            self.assertEqual((moved / "library/index.js").read_bytes(), b"original")

    @unittest.skipUnless(os.name == "posix", "live capture needs POSIX change stamps")
    def test_export_materialization_uses_original_immutable_rows(self):
        with tempfile.TemporaryDirectory() as raw:
            parent = Path(raw).resolve()
            source = parent / "provider/library"
            (source / "source").mkdir(parents=True)
            path = source / "source/api.js"
            path.write_bytes(b"exports.value=1;")
            path.chmod(0o644)
            files = (DirectoryExportFile("source/api.js", path.read_bytes(), 0o644),)
            content = encode_directory_export(files, max_bytes=4096, max_entries=10)
            resource, ports, _times, _issued = self.guard_fixture(parent / "sdk")
            provider = SimpleNamespace(identity=canonical_identity("provider"))
            ports._exports_by_identity[provider.identity.uri] = provider
            ports._artifact_paths[provider.identity.uri] = source.parent
            resource._export_inputs = (
                (
                    provider,
                    provider.identity,
                    source,
                    content,
                    (("source/api.js", path.read_bytes(), 0o644),),
                    _original_stamps(source, files),
                ),
            )
            resource._original_export_inputs = resource._export_inputs
            destination = parent / "destination"
            self.assertEqual(
                resource.materialize_export(provider, destination), content
            )
            self.assertEqual(
                (destination / "source/api.js").read_bytes(), path.read_bytes()
            )


if __name__ == "__main__":
    unittest.main()
