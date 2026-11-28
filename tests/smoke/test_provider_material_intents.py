"""Real native retry metadata with explicit fixture generation authority.

This reproduces build-intent leakage; it is not genuine model qualification.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from literate_ai.adapters.lifecycle.standard_local import LocalStandardLifecycleError
from literate_ai.adapters.models.coding_cli import RecipeLibraryDependency
from literate_ai.adapters.qualification_capture import (
    QualificationEvidenceReader,
    QualificationEvidenceRecorder,
    verify_qualification_build,
)
from tests.smoke import test_native_cargo_standard as native_fixture
from tests.support.fixtures_test_component_node_generation_preparation import _fixture
from tests.support.standard_source_evidence_fixture import register_strict_source


@unittest.skipUnless(
    shutil.which("cargo") and shutil.which("rustc"), "native Rust tools unavailable"
)
class ProviderMaterialIntentTests(unittest.TestCase):
    def test_regenerated_native_consumer_records_only_its_current_exact_bindings(self):
        self._exercise("embedded")

    def test_shared_layout_retry_replays_exact_source_and_provider_siblings(self):
        self._exercise("shared-siblings")

    def _exercise(self, layout):
        with tempfile.TemporaryDirectory(prefix="provider-intent-") as temporary:
            root = Path(temporary)
            helper = native_fixture.NativeCargoStandardTests("runTest")
            ports, execution, candidates = helper.system(root, package_layout=layout)
            recorder = QualificationEvidenceRecorder(
                max_bytes=64 * 1024**2, max_records=10000
            )
            ports.retain_evidence_with(recorder)
            ordered = sorted(
                execution.generation_plans, key=lambda p: len(p.direct_generation_edges)
            )
            leaf, consumer = ordered
            candidate = candidates[leaf.component_revision]
            intent = ports.create(execution, leaf, candidate, (), ())
            index = ports.index(candidate.component_revision, candidate.tree_identity)
            leaf_plan = ports.finalize(intent, ports.authorize(intent, index))
            output = ports.build(leaf_plan, ())
            providers = output.exports
            original = candidates[consumer.component_revision]
            first_intent = ports.create(execution, consumer, original, providers, ())
            index = ports.index(original.component_revision, original.tree_identity)
            first_plan = ports.finalize(
                first_intent, ports.authorize(first_intent, index)
            )
            first = ports.build(first_plan, providers)
            first_path = (
                ports.artifact_path(first.exports[0]).parent / "artifact-manifest.json"
            )
            first_bytes = first_path.read_bytes()
            snapshot, equivalent_execution = _fixture(
                root_name="service", library_names=frozenset({"service", "storage"})
            )
            self.assertEqual(execution.identity, equivalent_execution.identity)
            source = root / "regenerated"
            shutil.copytree(ports.source_trees.resolve(original.tree_identity), source)
            with (source / "source/src/lib.rs").open("a") as stream:
                stream.write(
                    "\n// Independently authored second generated-source fixture.\n"
                )
            second_candidate = register_strict_source(
                ports.source_trees,
                source,
                snapshot=snapshot,
                generation_plan=consumer,
                identity_namespace="native-cargo-retry",
            )
            second_intent = ports.create(
                execution, consumer, second_candidate, providers, ()
            )
            self.assertNotEqual(first_intent.identity, second_intent.identity)
            self.assertEqual(
                ports.library_consumer_bindings(first_intent),
                ports.library_consumer_bindings(second_intent),
            )
            index = ports.index(
                second_candidate.component_revision, second_candidate.tree_identity
            )
            second_plan = ports.finalize(
                second_intent, ports.authorize(second_intent, index)
            )
            second = ports.build(second_plan, providers)
            second_path = (
                ports.artifact_path(second.exports[0]).parent / "artifact-manifest.json"
            )
            materials = json.loads(second_path.read_bytes())["provider_materials"]
            self.assertEqual(len(materials), 1)
            self.assertEqual(
                materials[0]["library_consumer_bindings"],
                [b.to_dict() for b in ports.library_consumer_bindings(second_intent)],
            )
            # The generation envelope remains the explicit fixture. Retain its
            # actual source coordinate and native export bytes, as complete
            # production capture does, without replacing provider semantics.
            for candidate in (*candidates.values(), second_candidate):
                source_root = ports.source_trees.resolve(candidate.tree_identity)
                files = []
                for path in sorted(source_root.rglob("*")):
                    if (
                        path.is_file()
                        and ".codegraph" not in path.relative_to(source_root).parts
                    ):
                        payload = path.read_bytes()
                        identity = recorder.remember_bytes(payload)
                        files.append(
                            {
                                "path": path.relative_to(source_root).as_posix(),
                                "size": len(payload),
                                "digest": identity.uri,
                            }
                        )
                self.assertEqual(recorder.remember_json(files), candidate.tree_identity)
            for node in (output, first, second):
                for export in node.exports:
                    recorder.remember_bytes(ports.read_artifact_blob(export.blob))
            reader = QualificationEvidenceReader(
                recorder.entries,
                max_bytes=64 * 1024**2,
                max_records=10000,
            )
            recipe = SimpleNamespace(
                library_dependencies=tuple(
                    RecipeLibraryDependency(
                        edge.provider_revision,
                        edge.capability,
                        edge.public_interface_identity,
                        ports.contracts[
                            edge.provider_revision.uri
                        ].library_import_surface,
                    )
                    for edge in consumer.direct_generation_edges
                )
            )
            build_evidence = ports.build_evidence_for_test(second_plan, second.exports)
            verify_qualification_build(
                reader,
                plan=second_plan,
                build=build_evidence,
                provider_exports={
                    export.identity: export
                    for node in (output, first, second)
                    for export in node.exports
                },
                current_commands={
                    c.component_revision: c for c in ports.contracts.values()
                },
                current_recipe=recipe,
            )
            if layout == "shared-siblings":
                from literate_ai.adapters.qualification_cargo_shared import (
                    verify_shared_cargo_artifact,
                )
                from literate_ai.contracts.identity import ContentIdentity

                observed = reader.read_json(build_evidence.build_observation_identity)
                tree = reader.read_json(
                    ContentIdentity.parse_uri(observed["artifact_tree_identity"])
                )
                files = {r["path"]: "sha256:" + r["sha256"] for r in tree["files"]}
                target = ports.cargo_targets[second_plan.component_revision.uri]
                native = ports._current_native_cargo_inputs(second_plan, providers)
                arguments = dict(
                    reader=reader,
                    plan=second_plan,
                    target=target,
                    native=native,
                    lock_bytes=(
                        ports.artifact_path(second.exports[0]) / "source/Cargo.lock"
                    ).read_bytes(),
                )
                manifest = second.exports[0].export_id + "/source/Cargo.toml"
                for changed in (
                    {**files, manifest: "sha256:" + "0" * 64},
                    {p: identity for p, identity in files.items() if p != manifest},
                    {
                        **files,
                        "unreviewed-provider/source/lib.rs": "sha256:" + "0" * 64,
                    },
                ):
                    with self.subTest(layout=layout, files=len(changed)):
                        with self.assertRaisesRegex(
                            ValueError, "cargo-shared-artifact-mismatch"
                        ):
                            verify_shared_cargo_artifact(
                                **arguments, artifact_files=changed
                            )
            self.assertEqual(first_path.read_bytes(), first_bytes)
            self.assertNotEqual(first.exports[0].identity, second.exports[0].identity)
            with self.assertRaises(LocalStandardLifecycleError):
                ports._provider_materials(providers, consumer_plan=first_plan)
            self.assertEqual(
                list(ports._provider_materials(providers, consumer_plan=second_plan)),
                materials,
            )
