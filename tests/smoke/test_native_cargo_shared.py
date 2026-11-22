"""Pure layout and real Cargo checks with explicit fixture package authority.

No model generation, public qualification or retained admission is claimed.
"""

import os
import shutil
import subprocess
import tempfile
import tomllib
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.directory_artifacts import DirectoryExportFile as File
from literate_ai.adapters.lifecycle.native_cargo_shared import (
    project_shared_cargo_graph,
)
from tests.smoke import test_native_cargo_projection as fixture
from tests.smoke import test_native_cargo_standard as standard_fixture
from tests.support import (
    fixtures_test_component_node_generation_preparation as preparation,
)


class NativeCargoSharedTests(unittest.TestCase):
    def setUp(self):
        self.helper = fixture.NativeCargoProjectionTests("runTest")
        self.helper.setUp()
        self.beta = self.helper.beta
        alpha = replace(
            self.helper.alpha,
            files=tuple(
                replace(f, content=f.content + b"pub use beta::Event;\n")
                if f.path == "source/src/lib.rs"
                else f
                for f in self.helper.alpha.files
            ),
        )
        graph = fixture.Graph(
            alpha.node.component_revision,
            (self.beta.node,),
            (
                fixture.Edge(
                    alpha.node.component_revision,
                    self.beta.node.component_revision,
                    "beta",
                ),
            ),
        )
        rewritten, additions = project_shared_cargo_graph(
            graph=graph,
            root_manifest=alpha.original_manifest,
            root_manifest_path=alpha.manifest,
            sources=(self.beta,),
        )
        prefix = alpha.node.component_revision.digest + "/"
        self.alpha = replace(
            alpha,
            files=tuple(
                replace(f, content=rewritten) if f.path == alpha.manifest else f
                for f in alpha.files
            )
            + tuple(
                replace(f, path=f.path.removeprefix(prefix))
                for f in additions
                if f.path.startswith(prefix)
            ),
        )
        self.arguments = dict(
            graph=self.helper.graph,
            root_manifest=fixture.manifest("gamma"),
            root_manifest_path="source/Cargo.toml",
            sources=(self.alpha, self.beta),
        )

    def test_deterministic_forest_preserves_all_exact_provider_files(self):
        first = project_shared_cargo_graph(**self.arguments)
        second = project_shared_cargo_graph(
            **{**self.arguments, "sources": tuple(reversed(self.arguments["sources"]))}
        )
        self.assertEqual(first, second)
        files = {f.path: f for f in first[1]}
        for source in (self.alpha, self.beta):
            for original in source.files:
                copied = files[
                    source.node.component_revision.digest + "/" + original.path
                ]
                self.assertEqual(copied.content, original.content)
                self.assertEqual(copied.mode, original.mode)
        self.assertFalse(any("/providers/" in f.path for f in first[1]))
        self.assertIn(self.alpha.node.component_revision.digest.encode(), first[0])
        self.assertIn(self.beta.node.component_revision.digest.encode(), first[0])

    def test_legacy_embedded_provider_refuses_without_manifest_repair(self):
        old = self.helper.sealed_alpha()
        before = old.files
        with self.assertRaisesRegex(ValueError, "shared_provider_manifest"):
            project_shared_cargo_graph(
                **{**self.arguments, "sources": (old, self.beta)}
            )
        self.assertIs(old.files, before)

    def test_missing_duplicate_and_substituted_sources_refuse(self):
        for sources in (
            (self.beta,),
            (self.beta, self.beta),
            (
                replace(
                    self.alpha,
                    node=replace(
                        self.alpha.node, artifact_identity=fixture.identity("other")
                    ),
                ),
                self.beta,
            ),
        ):
            with self.subTest(sources=len(sources)):
                with self.assertRaisesRegex(ValueError, "source_graph"):
                    project_shared_cargo_graph(**{**self.arguments, "sources": sources})

    def test_changed_manifest_and_record_refuse(self):
        for path in (self.alpha.manifest, ".literate/native-cargo/projection.json"):
            files = tuple(
                replace(f, content=f.content + b" ") if f.path == path else f
                for f in self.alpha.files
            )
            candidate = replace(self.alpha, files=files)
            with self.subTest(path=path):
                with self.assertRaisesRegex(
                    ValueError, "shared_provider_(manifest|record)"
                ):
                    project_shared_cargo_graph(
                        **{**self.arguments, "sources": (candidate, self.beta)}
                    )

    def test_projection_performs_no_filesystem_or_native_observation(self):
        with (
            patch("builtins.open", side_effect=AssertionError("open")),
            patch("os.stat", side_effect=AssertionError("stat")),
            patch("os.lstat", side_effect=AssertionError("lstat")),
            patch("os.scandir", side_effect=AssertionError("scandir")),
            patch("subprocess.Popen", side_effect=AssertionError("Popen")),
        ):
            project_shared_cargo_graph(**self.arguments)

    def test_profile_versions_preserve_legacy_bytes_and_require_explicit_layout(self):
        from literate_ai.contracts import (
            StandardCargoCommandProfile,
            parse_standard_command_profile,
        )

        legacy = StandardCargoCommandProfile(
            "cargo", "cargo", "source/Cargo.toml", "app"
        )
        old = {
            "schema": "urn:literate-ai:schema:v2:standard-cargo-command-profile",
            "target": "cargo",
            "toolchain": "cargo",
            "manifest": "source/Cargo.toml",
            "binary": "app",
        }
        self.assertEqual(legacy.to_dict(), old)
        self.assertEqual(parse_standard_command_profile(old), legacy)
        shared = replace(legacy, package_layout="shared-siblings")
        self.assertNotEqual(shared.identity, legacy.identity)
        self.assertEqual(parse_standard_command_profile(shared.to_dict()), shared)
        for bad in (
            {**old, "package_layout": "shared-siblings"},
            {**shared.to_dict(), "package_layout": "embedded"},
            {**shared.to_dict(), "package_layout": "unknown"},
            {**old, "schema": shared.SHARED_SCHEMA},
        ):
            with self.assertRaises(ValueError):
                parse_standard_command_profile(bad)

    def test_target_layout_identity_and_closed_decoder_preserve_legacy(self):
        from literate_ai.adapters.lifecycle.standard_cargo import StandardCargoTarget
        from literate_ai.adapters.qualification_capture import (
            QualificationEvidenceReader,
            QualificationEvidenceRecorder,
        )
        from literate_ai.adapters.qualification_native_cargo import cargo_target

        legacy = StandardCargoTarget(
            *(fixture.identity(s) for s in ("revision", "resolver", "cargo", "rustc")),
            "source/Cargo.toml",
            "app",
            ("rustc",),
            library=True,
        )
        self.assertEqual(
            legacy.identity_document()["schema"], "literate-ai/standard-cargo-target@1"
        )
        self.assertNotIn("package_layout", legacy.identity_document())
        shared = replace(legacy, package_layout="shared-siblings")
        self.assertNotEqual(shared.identity, legacy.identity)
        for target in (legacy, shared):
            recorder = QualificationEvidenceRecorder(max_bytes=16384, max_records=10)
            identity = recorder.remember_json(target.identity_document())
            reader = QualificationEvidenceReader(
                recorder.entries, max_bytes=16384, max_records=10
            )
            self.assertEqual(cargo_target(reader, identity), target)
        for document in (
            {**legacy.identity_document(), "package_layout": "shared-siblings"},
            {
                k: v
                for k, v in shared.identity_document().items()
                if k != "package_layout"
            },
        ):
            recorder = QualificationEvidenceRecorder(max_bytes=16384, max_records=10)
            identity = recorder.remember_json(document)
            reader = QualificationEvidenceReader(
                recorder.entries, max_bytes=16384, max_records=10
            )
            with self.assertRaisesRegex(ValueError, "cargo-target-mismatch"):
                cargo_target(reader, identity)

    def test_shared_record_and_complete_forest_budgets_refuse(self):
        from literate_ai.adapters.lifecycle import native_cargo_shared as shared

        for constant in (
            "MAX_PROJECTION_FILES",
            "MAX_PROJECTION_BYTES",
            "MAX_MANIFEST_BYTES",
        ):
            with self.subTest(constant=constant), patch.object(shared, constant, 1):
                with self.assertRaisesRegex(ValueError, "(closure_bound|record_bound)"):
                    project_shared_cargo_graph(**self.arguments)
        provider_bytes = sum(
            len(f.content) for s in self.arguments["sources"] for f in s.files
        )
        with patch.object(shared, "MAX_PROJECTION_BYTES", provider_bytes):
            with self.assertRaisesRegex(ValueError, "projection_bound"):
                project_shared_cargo_graph(**self.arguments)

    def test_provider_free_leaf_preserves_original_manifest(self):
        graph = fixture.Graph(fixture.identity("leaf"), (), ())
        raw = fixture.manifest("leaf")
        self.assertEqual(
            project_shared_cargo_graph(
                graph=graph,
                root_manifest=raw,
                root_manifest_path="source/Cargo.toml",
                sources=(),
            ),
            (raw, ()),
        )

    @unittest.skipUnless(
        shutil.which("cargo") and shutil.which("rustc"), "native Cargo required"
    )
    def test_ordinary_consumer_uses_three_separate_exports_with_one_nominal_type(self):
        rewritten, additions = project_shared_cargo_graph(**self.arguments)
        gamma = self.helper.root.digest
        with tempfile.TemporaryDirectory(prefix="cargo-shared-") as temporary:
            root = Path(temporary).resolve(strict=True)
            forest = root / "packages"
            for f in (
                File(gamma + "/source/Cargo.toml", rewritten, 0o644),
                File(
                    gamma + "/source/src/lib.rs",
                    b"pub use beta::Event;\n"
                    b"pub fn total(e:&Event)->u32{alpha::read(e)+e.value}\n",
                    0o644,
                ),
                *additions,
            ):
                destination = forest / f.path
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(f.content)
                destination.chmod(f.mode)
            consumer = root / "consumer"
            (consumer / "src").mkdir(parents=True)
            (consumer / "Cargo.toml").write_text(
                '[package]\nname="shared-consumer"\nversion="1.0.0"\nedition="2021"\n[dependencies]\n'
                + "\n".join(
                    name + '={path="../packages/' + revision + '/source"}'
                    for name, revision in (
                        ("alpha", self.alpha.node.component_revision.digest),
                        ("beta", self.beta.node.component_revision.digest),
                        ("gamma", gamma),
                    )
                )
                + "\n"
            )
            (consumer / "src/main.rs").write_text(
                "fn main(){let e=beta::Event{value:37};"
                "assert_eq!(alpha::read(&e),37);assert_eq!(gamma::total(&e),74);"
                "let a:&alpha::Event=&e;let g:&gamma::Event=a;"
                "assert_eq!(g.value,37);}\n"
            )
            result = subprocess.run(
                [
                    shutil.which("cargo"),
                    "run",
                    "--offline",
                    "--quiet",
                    "--target-dir",
                    str(root / "outputs"),
                ],
                cwd=consumer,
                env={**os.environ, "CARGO_INCREMENTAL": "0"},
                capture_output=True,
                timeout=60,
            )
            self.assertEqual(
                result.returncode, 0, result.stderr.decode(errors="replace")
            )


@unittest.skipUnless(
    shutil.which("cargo") and shutil.which("rustc"), "native Cargo required"
)
class NativeCargoSharedStandardTests(unittest.TestCase):
    def test_explicit_layout_builds_independent_exact_exports_and_keeps_legacy(self):
        for layout in ("embedded", "shared-siblings"):
            with (
                self.subTest(layout=layout),
                tempfile.TemporaryDirectory(prefix="cargo-layout-") as temporary,
            ):
                root = Path(temporary).resolve(strict=True)
                helper = standard_fixture.NativeCargoStandardTests("runTest")
                ports, execution, candidates = helper.system(
                    root, package_layout=layout
                )
                built, plans = {}, {}
                for generation in sorted(
                    execution.generation_plans,
                    key=lambda p: len(p.direct_generation_edges),
                ):
                    candidate = candidates[generation.component_revision]
                    providers = tuple(
                        built[e.provider_revision].exports[0]
                        for e in generation.direct_generation_edges
                    )
                    intent = ports.create(
                        execution, generation, candidate, providers, ()
                    )
                    index = ports.index(
                        candidate.component_revision, candidate.tree_identity
                    )
                    plan = ports.finalize(intent, ports.authorize(intent, index))
                    built[generation.component_revision] = ports.build(plan, providers)
                    plans[generation.component_revision] = plan
                destinations = {}
                contents = {}
                for revision, result in built.items():
                    export = result.exports[0]
                    original = ports.artifact_path(export)
                    # Read the actual package name from native output.
                    name = tomllib.loads((original / "source/Cargo.toml").read_text())[
                        "package"
                    ]["name"]
                    destination = root / "received" / revision.digest
                    shutil.copytree(original, destination)
                    destinations[name] = destination
                    contents[destination] = {
                        f.relative_to(destination): f.read_bytes()
                        for f in destination.rglob("*")
                        if f.is_file()
                    }
                consumer = root / "independent"
                (consumer / "src").mkdir(parents=True)
                (consumer / "Cargo.toml").write_text(
                    '[package]\nname="independent-consumer"\nversion="1.0.0"\nedition="2021"\n[dependencies]\n'
                    + "\n".join(
                        name + '={path="../received/' + path.name + '/source"}'
                        for name, path in sorted(destinations.items())
                    )
                    + "\n"
                )
                (consumer / "src/main.rs").write_text(
                    "fn main(){let e=beta::Event{value:37};"
                    "assert_eq!(alpha::read(&e),37);}"
                )
                result = subprocess.run(
                    [
                        shutil.which("cargo"),
                        "run",
                        "--offline",
                        "--quiet",
                        "--target-dir",
                        str(root / "independent-outputs"),
                    ],
                    cwd=consumer,
                    env={**os.environ, "CARGO_INCREMENTAL": "0"},
                    capture_output=True,
                    timeout=60,
                )
                if layout == "embedded":
                    self.assertEqual(result.returncode, 101)
                    self.assertIn(b"package collision in the lockfile", result.stderr)
                else:
                    self.assertEqual(
                        result.returncode, 0, result.stderr.decode(errors="replace")
                    )
                if layout == "shared-siblings":
                    from literate_ai.application.standard_project_lifecycle import (
                        StandardProjectBuildPlan,
                    )
                    from literate_ai.contracts import ArtifactBuildGraph, ExactLinkPlan

                    snapshot, same_execution = preparation._fixture(
                        root_name="service",
                        library_names=frozenset({"service", "storage"}),
                    )
                    self.assertEqual(execution.identity, same_execution.identity)
                    lock = snapshot.authority.lock
                    exports = tuple(
                        e for output in built.values() for e in output.exports
                    )
                    manifests = tuple(
                        replace(plans[r].manifest, exports=built[r].exports)
                        for r in sorted(plans, key=lambda identity: identity.uri)
                    )
                    root_export = built[lock.root_revision].exports[0]
                    link = ExactLinkPlan(
                        root_export.identity,
                        tuple(
                            sorted(
                                (e.identity for e in exports),
                                key=lambda identity: identity.uri,
                            )
                        ),
                    )
                    graph = ArtifactBuildGraph(
                        manifests[0].build_system_driver_identity, manifests, (link,)
                    )
                    project_plan = StandardProjectBuildPlan(
                        execution.identity,
                        tuple(
                            plans[r]
                            for r in sorted(plans, key=lambda identity: identity.uri)
                        ),
                    )
                    package_plan, packaged = ports.create_project_package(
                        lock, execution, project_plan, graph, link
                    )
                    custody = ports.project_package_custody(package_plan, packaged)
                    manifest_text = (consumer / "Cargo.toml").read_text()
                    for export in exports:
                        packaged_path = custody.artifact_paths[export.identity.uri]
                        self.assertEqual(
                            packaged_path.name, export.component_revision.digest
                        )
                        manifest_text = manifest_text.replace(
                            "../received/"
                            + export.component_revision.digest
                            + "/source",
                            os.path.relpath(packaged_path / "source", consumer),
                        )
                    (consumer / "Cargo.toml").write_text(manifest_text)
                    packaged_result = subprocess.run(
                        [
                            shutil.which("cargo"),
                            "run",
                            "--offline",
                            "--quiet",
                            "--target-dir",
                            str(root / "packaged-outputs"),
                        ],
                        cwd=consumer,
                        env={**os.environ, "CARGO_INCREMENTAL": "0"},
                        capture_output=True,
                        timeout=60,
                    )
                    self.assertEqual(
                        packaged_result.returncode,
                        0,
                        packaged_result.stderr.decode(errors="replace"),
                    )
                    ports.project_package_custody(package_plan, packaged)
                for destination, before in contents.items():
                    self.assertEqual(
                        before,
                        {
                            f.relative_to(destination): f.read_bytes()
                            for f in destination.rglob("*")
                            if f.is_file()
                        },
                    )
