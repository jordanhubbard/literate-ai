"""Actual native builder records; authored fixture source, not genuine model proof."""

import copy
import shutil
import tempfile
import unittest
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters.lifecycle.native_cargo_projection import (
    reopen_native_cargo_metadata,
    validate_native_cargo_metadata,
)
from literate_ai.adapters.models.coding_cli import RecipeLibraryDependency
from literate_ai.adapters.qualification_capture import (
    QualificationCaptureError,
    QualificationEvidenceReader,
    QualificationEvidenceRecorder,
    verify_qualification_build,
)
from literate_ai.adapters.qualification_cargo import verify_qualification_cargo_build
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.native_cargo_provider_graph import NativeCargoProviderGraph
from tests.smoke import test_native_cargo_standard as native_fixture


@unittest.skipUnless(
    shutil.which("cargo") and shutil.which("rustc"), "native Rust tools unavailable"
)
class QualificationCargoNativeTests(unittest.TestCase):
    def test_actual_leaf_and_native_provider_build_records_reopen(self):
        with tempfile.TemporaryDirectory(prefix="cargo-reopen-") as temporary:
            helper = native_fixture.NativeCargoStandardTests("runTest")
            ports, execution, candidates = helper.system(Path(temporary))
            recorder = QualificationEvidenceRecorder(
                max_bytes=64 * 1024**2, max_records=10000
            )
            ports.retain_evidence_with(recorder)
            outputs, plans = {}, {}
            ordered = sorted(
                execution.generation_plans,
                key=lambda row: len(row.direct_generation_edges),
            )
            for generation in ordered:
                candidate = candidates[generation.component_revision]
                providers = tuple(
                    outputs[edge.provider_revision].exports[0]
                    for edge in generation.direct_generation_edges
                )
                intent = ports.create(execution, generation, candidate, providers, ())
                index = ports.index(
                    candidate.component_revision, candidate.tree_identity
                )
                plan = ports.finalize(intent, ports.authorize(intent, index))
                outputs[generation.component_revision] = ports.build(plan, providers)
                plans[generation.component_revision] = plan
            # The fixture supplies real bytes but synthetic generation envelopes.
            # Retain the actual source-only coordinate that complete source capture
            # verifies and retains in production, checking its existing exact ID.
            for candidate in candidates.values():
                source = ports.source_trees.resolve(candidate.tree_identity)
                files = []
                for path in sorted(source.rglob("*")):
                    if (
                        path.is_file()
                        and ".codegraph" not in path.relative_to(source).parts
                    ):
                        payload = path.read_bytes()
                        digest = recorder.remember_bytes(payload)
                        files.append(
                            {
                                "path": path.relative_to(source).as_posix(),
                                "size": len(payload),
                                "digest": digest.uri,
                            }
                        )
                self.assertEqual(recorder.remember_json(files), candidate.tree_identity)
            # Full qualification capture retains exact export payloads as well as
            # the builder's process/tree records. No provider semantics are replaced.
            for output in outputs.values():
                for export in output.exports:
                    recorder.remember_bytes(ports.read_artifact_blob(export.blob))
            recipes = {
                generation.component_revision: SimpleNamespace(
                    library_dependencies=tuple(
                        RecipeLibraryDependency(
                            edge.provider_revision,
                            edge.capability,
                            edge.public_interface_identity,
                            ports.contracts[
                                edge.provider_revision.uri
                            ].library_import_surface,
                        )
                        for edge in generation.direct_generation_edges
                    )
                )
                for generation in ordered
            }
            reader = QualificationEvidenceReader(
                recorder.entries, max_bytes=64 * 1024**2, max_records=10000
            )
            for generation in ordered:
                plan = plans[generation.component_revision]
                output = outputs[generation.component_revision]
                build = ports.build_evidence_for_test(plan, output.exports)
                with self.subTest(
                    native_providers=len(plan.provider_artifact_identities)
                ):
                    verify_qualification_build(
                        reader,
                        plan=plan,
                        build=build,
                        provider_exports={
                            export.identity: export
                            for node in outputs.values()
                            for export in node.exports
                        },
                        current_recipe=recipes[generation.component_revision],
                        current_commands={
                            contract.component_revision: contract
                            for contract in ports.contracts.values()
                        },
                    )

            leaf = ordered[0].component_revision
            leaf_plan = plans[leaf]
            leaf_build = ports.build_evidence_for_test(leaf_plan, outputs[leaf].exports)
            leaf_record = reader.read_json(leaf_build.build_observation_identity)
            leaf_observation = reader.read_json(
                ContentIdentity.parse_uri(leaf_record["process_observation_identity"])
            )
            leaf_files = copy.deepcopy(
                reader.read_json(
                    ContentIdentity.parse_uri(leaf_record["artifact_tree_identity"])
                )["files"]
            )
            leaf_files.append(
                {
                    "path": ".literate/cargo/native-provider-graph.json",
                    "sha256": "0" * 64,
                }
            )
            with (
                self.subTest(tamper="provider-free native provenance"),
                self.assertRaisesRegex(
                    QualificationCaptureError, "cargo-build-mismatch"
                ),
            ):
                verify_qualification_cargo_build(
                    reader,
                    plan=leaf_plan,
                    observation=leaf_observation,
                    files=leaf_files,
                )
            final = ordered[-1].component_revision
            self.check_rehashed_tampering(
                recorder,
                reader,
                plans[final],
                recipes[final],
                ports.build_evidence_for_test(plans[final], outputs[final].exports),
                {
                    export.identity: export
                    for node in outputs.values()
                    for export in node.exports
                },
                {
                    contract.component_revision: contract
                    for contract in ports.contracts.values()
                },
            )

    def check_rehashed_tampering(
        self, recorder, reader, plan, recipe, build, exports, commands
    ):
        parse = ContentIdentity.parse_uri
        build_record = reader.read_json(build.build_observation_identity)
        observation = reader.read_json(
            parse(build_record["process_observation_identity"])
        )
        files = reader.read_json(parse(build_record["artifact_tree_identity"]))["files"]
        custody = reader.read_json(build.artifact_custody_identity)
        final_files = reader.read_json(parse(custody["artifact_tree_identity"]))[
            "files"
        ]
        artifact_manifest = next(
            row for row in final_files if row["path"] == "artifact-manifest.json"
        )
        materials = reader.read_json(parse("sha256:" + artifact_manifest["sha256"]))[
            "provider_materials"
        ]
        by_path = {row["path"]: row["sha256"] for row in files}
        native_path = ".literate/cargo/native-provider-graph.json"
        manifest_path = ".literate/cargo/evidence-manifest.json"
        native = reader.read_json(parse("sha256:" + by_path[native_path]))
        dependency_manifest = reader.read_json(
            parse("sha256:" + by_path[manifest_path])
        )

        def check(
            changed=None,
            *,
            metadata=None,
            altered_materials=None,
            remove=False,
            extra=False,
            altered_recipe=None,
        ):
            records = dict(recorder.entries)
            selected_files = copy.deepcopy(files)
            selected_observation = copy.deepcopy(observation)
            manifest = copy.deepcopy(dependency_manifest)

            def put(value):
                payload = canonical_json_bytes(value)
                identity = canonical_identity(value)
                records[identity] = payload
                return identity

            def replace_file(path, identity):
                for row in selected_files:
                    if row["path"] == path:
                        row["sha256"] = identity.digest
                        return
                selected_files.append({"path": path, "sha256": identity.digest})

            if changed is not None:
                replace_file(native_path, put(changed))
            if remove:
                selected_files = [
                    row for row in selected_files if row["path"] != native_path
                ]
            if extra:
                replace_file(
                    ".literate/cargo/unexpected.json", put({"unexpected": True})
                )
            if metadata is not None:
                identity = put(metadata)
                replace_file(".literate/cargo/metadata.json", identity)
                manifest["metadata_identity"] = identity.uri
                process = copy.deepcopy(
                    reader.read_json(parse(observation["metadata"]))
                )
                process["stdout_identity"] = identity.uri
                selected_observation["metadata"] = put(process).uri
            manifest["files"] = [
                {"path": row["path"], "digest": "sha256:" + row["sha256"]}
                for row in sorted(selected_files, key=lambda row: row["path"])
                if row["path"].startswith(".literate/cargo/")
                and row["path"] != manifest_path
            ]
            replace_file(manifest_path, put(manifest))
            candidate = QualificationEvidenceReader(
                tuple(sorted(records.items(), key=lambda row: row[0].uri)),
                max_bytes=64 * 1024**2,
                max_records=10000,
            )
            verify_qualification_cargo_build(
                candidate,
                plan=plan,
                observation=selected_observation,
                files=selected_files,
                provider_exports=exports,
                current_commands=commands,
                current_recipe=recipe if altered_recipe is None else altered_recipe,
                provider_materials=materials
                if altered_materials is None
                else altered_materials,
            )

        # Record rehashing alone cannot turn altered provenance into current authority.
        mutations = {}
        value = copy.deepcopy(native)
        value["graph"]["nodes"][0]["package"] += "_substituted"
        mutations["provider graph"] = value
        value = copy.deepcopy(native)
        value["original_manifest_identity"] = "sha256:" + "0" * 64
        mutations["original manifest"] = value
        value = copy.deepcopy(native)
        value["metadata_binding"]["packages"][0]["cargo_package_id"] += "_substituted"
        mutations["metadata binding"] = value
        value = copy.deepcopy(native)
        value["provider_locks"][0]["lock_identity"] = "sha256:" + "0" * 64
        mutations["qualified provider lock"] = value
        value = copy.deepcopy(native)
        value["unreviewed"] = True
        mutations["unknown native evidence field"] = value
        for name, value in mutations.items():
            with self.subTest(tamper=name):
                with self.assertRaises(ValueError):
                    check(value)
        for name, options in (
            ("missing native graph", {"remove": True}),
            ("unknown evidence member", {"extra": True}),
        ):
            with self.subTest(tamper=name):
                with self.assertRaises(ValueError):
                    check(**options)
        value = copy.deepcopy(materials)
        value[0]["library_consumer_bindings"][0]["target_identity"]["digest"] = "0" * 64
        with self.subTest(tamper="current consumer binding"):
            with self.assertRaises(ValueError):
                check(altered_materials=value)
        metadata = reader.read_json(
            parse("sha256:" + by_path[".literate/cargo/metadata.json"])
        )
        value = copy.deepcopy(metadata)
        next(row for row in value["resolve"]["nodes"] if row["deps"])["deps"].pop()
        with self.subTest(tamper="native metadata edge"):
            with self.assertRaises(ValueError):
                check(metadata=value)
        value = copy.deepcopy(metadata)
        provider = next(
            row for row in value["packages"] if "providers" in row["manifest_path"]
        )
        provider["manifest_path"] = provider["manifest_path"].replace(
            "providers", "providers-substituted", 1
        )
        with self.subTest(tamper="native projection coordinate"):
            with self.assertRaises(ValueError):
                check(metadata=value)
        with self.subTest(tamper="missing current generation interfaces"):
            with self.assertRaises(ValueError):
                check(altered_recipe=SimpleNamespace(library_dependencies=()))
        with self.subTest(tamper="duplicated current generation interface"):
            with self.assertRaises(ValueError):
                check(
                    altered_recipe=SimpleNamespace(
                        library_dependencies=recipe.library_dependencies * 2
                    )
                )
        with (
            patch("pathlib.Path.open", side_effect=AssertionError("recorded path I/O")),
            patch("os.open", side_effect=AssertionError("filesystem open")),
            patch("subprocess.Popen", side_effect=AssertionError("native execution")),
        ):
            check()


class QualificationCargoCoordinateTests(unittest.TestCase):
    def arguments(self):
        return dict(
            graph=NativeCargoProviderGraph(canonical_identity("root"), (), ()),
            root_manifest=b'[package]\nname="fixture"\nversion="1.0.0"\n',
            root_manifest_path="source/Cargo.toml",
            sources=(),
            metadata={
                "workspace_root": r"C:\owned\projection\source",
                "packages": [
                    {
                        "id": "root-id",
                        "name": "fixture",
                        "version": "1.0.0",
                        "source": None,
                        "manifest_path": r"C:\owned\projection\source\Cargo.toml",
                    }
                ],
                "resolve": {
                    "root": "root-id",
                    "nodes": [{"id": "root-id", "deps": []}],
                },
            },
        )

    def test_windows_archive_coordinates_are_data_without_host_io(self):
        with patch("os.open", side_effect=AssertionError("recorded path opened")):
            result = reopen_native_cargo_metadata(**self.arguments())
        self.assertEqual(result["packages"][0]["cargo_package_id"], "root-id")

    def test_live_build_still_requires_a_concrete_owned_host_path(self):
        with self.assertRaisesRegex(ValueError, "projection_root"):
            validate_native_cargo_metadata(
                **self.arguments(),
                projection_root=PureWindowsPath(r"C:\owned\projection"),
            )

    def test_relative_and_escaping_archive_coordinates_refuse(self):
        for value in (r"relative\source", r"C:\owned\..\projection\source"):
            with self.subTest(coordinate=value), self.assertRaises(ValueError):
                args = self.arguments()
                args["metadata"]["workspace_root"] = value
                reopen_native_cargo_metadata(**args)
