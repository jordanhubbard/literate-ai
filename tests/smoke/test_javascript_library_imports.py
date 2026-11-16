"""Real Node imports from bounded sealed bytes; no provider-admission claims."""

from __future__ import annotations

import hashlib
import json
import shutil
import stat
import subprocess
import tempfile
import unittest
from dataclasses import fields, replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    encode_directory_export,
)
from literate_ai.adapters.lifecycle.javascript_libraries import (
    materialize_javascript_library_imports,
    prepare_javascript_library_imports,
)
from literate_ai.adapters.standard_project import (
    project_locked_standard_toolchain_closure,
)
from literate_ai.contracts import ArtifactExport, BlobRef, canonical_identity
from literate_ai.contracts.executable_components.commands import LibraryConsumerBinding
from tests.support.fixtures_test_standard_command_projection import (
    _locked_snapshot,
    _observation,
    _tool,
)


class JavaScriptLibraryImportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        # Synthetic sealed bytes mirror directory_export_bytes: preserve the
        # actual host mode, including Windows chmod semantics. This is not a
        # cross-host or target-platform qualification.
        probe = self.root / "mode-probe.js"
        probe.write_bytes(b"")
        probe.chmod(0o644)
        self.file_mode = stat.S_IMODE(probe.stat().st_mode)
        probe.unlink()
        _, snapshot, execution = _locked_snapshot(
            self.root, language="javascript", no_entrypoint=True
        )
        self.contract = project_locked_standard_toolchain_closure(
            snapshot,
            execution,
            host_platform="macos",
            toolchain_discoverer=lambda name, constraint, environment: _tool(name),
            dependency_observer=_observation,
        ).contracts[0]
        self.consumer = replace(
            self.contract, component_revision=canonical_identity("consumer")
        )
        self.surface = self.contract.library_import_surface
        self.capability = self.surface.capabilities[0]
        self.import_name = self.capability.module
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node unavailable")
        names = json.loads(
            subprocess.check_output(
                [
                    node,
                    "-e",
                    "process.stdout.write(JSON.stringify(require('node:module').builtinModules))",
                ],
                text=True,
            )
        )
        self.builtins = frozenset(
            n.removeprefix("node:").split("/", 1)[0] for n in names
        )
        self.blobs = {}
        self.contracts = {self.contract.component_revision.uri: self.contract}
        self.artifact, self.binding = self.provider(
            self.contract,
            "exports." + self.capability.symbols[0] + " = (a,b) => a+b;\n",
            extra=(
                DirectoryExportFile(
                    "source/secret.js", b"module.exports=999;", self.file_mode
                ),
            ),
        )

    def provider(self, contract, body, extra=(), dependencies=()):
        cap = contract.library_import_surface.capabilities[0]
        content = encode_directory_export(
            (
                DirectoryExportFile(
                    "source/" + cap.module + ".js", body.encode(), self.file_mode
                ),
                *extra,
            ),
            max_bytes=1048576,
            max_entries=1000,
        )
        declaration = contract.artifact_export
        artifact = ArtifactExport(
            **{f.name: getattr(declaration, f.name) for f in fields(declaration)},
            component_revision=contract.component_revision,
            source_tree_identity=canonical_identity("source"),
            toolchain_identity=contract.language_compiler_identity,
            authorization_identity=canonical_identity("fixture authorization"),
            dependency_artifact_identities=dependencies,
            blob=BlobRef(
                hashlib.sha256(content).hexdigest(),
                len(content),
                media_type=declaration.media_type,
            ),
        )
        self.blobs[artifact.blob.identity] = content
        binding = LibraryConsumerBinding(
            self.consumer.component_revision,
            contract.component_revision,
            cap.capability,
            cap.interface_identity,
            artifact.identity,
            contract.library_import_surface.identity,
            artifact.target_identity,
            dependencies,
        )
        return artifact, binding

    def prepare(self, artifacts=None, bindings=None, reader=None):
        return prepare_javascript_library_imports(
            self.consumer,
            (self.artifact,) if artifacts is None else artifacts,
            (self.binding,) if bindings is None else bindings,
            self.contracts,
            reader or (lambda blob: self.blobs[blob.identity]),
            builtin_modules=self.builtins,
        )

    def artifact_root(self):
        root = self.root / "artifact"
        (root / "source").mkdir(parents=True)
        return root

    def node(self, root, code, esm=False):
        node = shutil.which("node")
        if node is None:
            self.skipTest("Node unavailable")
        path = root / "source" / ("main.mjs" if esm else "main.js")
        path.write_text(code)
        return subprocess.run(
            [node, str(path)], capture_output=True, text=True, timeout=10
        )

    def test_cjs_and_esm_native_imports_after_artifact_relocation(self):
        imports = self.prepare()
        root = self.artifact_root()
        before = dict(self.blobs)
        materialize_javascript_library_imports(imports, root)
        moved = self.root / "relocated"
        root.rename(moved)
        symbol = self.capability.symbols[0]
        for esm, code in [
            (
                False,
                "const {" + symbol + "}=require(" + json.dumps(self.import_name) + ");",
            ),
            (
                True,
                "import {" + symbol + "} from " + json.dumps(self.import_name) + ";",
            ),
        ]:
            with self.subTest(esm=esm):
                result = self.node(
                    moved, code + "console.log(" + symbol + "(2,3));", esm
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(result.stdout.strip(), "5")
        self.assertEqual(self.blobs, before)
        self.assertNotIn(
            str(self.root),
            (
                moved / "node_modules" / self.surface.package / "package.json"
            ).read_text(),
        )

    def test_undeclared_subpath_is_not_exposed(self):
        root = self.artifact_root()
        materialize_javascript_library_imports(self.prepare(), root)
        result = self.node(
            root, "require(" + json.dumps(self.surface.package + "/secret") + ")"
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ERR_PACKAGE_PATH_NOT_EXPORTED", result.stderr)

    def test_foreign_missing_duplicate_and_substituted_bindings(self):
        for bindings in [
            (),
            (self.binding, self.binding),
            (
                replace(
                    self.binding,
                    consumer_component_revision=canonical_identity("foreign"),
                ),
            ),
            (replace(self.binding, interface_identity=canonical_identity("foreign")),),
            (
                replace(
                    self.binding, import_surface_identity=canonical_identity("foreign")
                ),
            ),
            (replace(self.binding, artifact_identity=canonical_identity("foreign")),),
            (replace(self.binding, target_identity=canonical_identity("foreign")),),
            (
                replace(
                    self.binding,
                    dependency_artifact_identities=(canonical_identity("foreign"),),
                ),
            ),
        ]:
            with self.subTest(bindings=bindings), self.assertRaises(ValueError):
                self.prepare(bindings=bindings)

    def test_provider_byte_drift_is_rejected(self):
        with self.assertRaises(ValueError):
            self.prepare(reader=lambda blob: self.blobs[blob.identity] + b"drift")

    def test_claimed_oversize_refuses_before_read(self):
        calls = []
        with patch(
            "literate_ai.adapters.lifecycle.javascript_libraries.MAX_BUILD_ARCHIVE_BYTES",
            1,
        ):
            with self.assertRaises(ValueError):
                self.prepare(reader=lambda blob, calls=calls: calls.append(blob))
        self.assertEqual(calls, [])

    def test_missing_module_is_rejected(self):
        bad = replace(self.capability, module=self.surface.package + "/absent")
        surface = replace(self.surface, capabilities=(bad,))
        self.contracts[self.contract.component_revision.uri] = replace(
            self.contract, library_import_surface=surface
        )
        with self.assertRaises(ValueError):
            self.prepare(
                bindings=(
                    replace(self.binding, import_surface_identity=surface.identity),
                )
            )

    def test_same_name_provider_collision_is_rejected(self):
        contract = replace(
            self.contract, component_revision=canonical_identity("second-provider")
        )
        self.contracts[contract.component_revision.uri] = contract
        artifact, binding = self.provider(contract, "module.exports={};")
        with self.assertRaises(ValueError):
            self.prepare(
                artifacts=(self.artifact, artifact), bindings=(self.binding, binding)
            )

    def test_foreign_package_namespace_is_rejected(self):
        surface = replace(
            self.surface,
            capabilities=(replace(self.capability, module="foreign/module"),),
        )
        self.contracts[self.contract.component_revision.uri] = replace(
            self.contract, library_import_surface=surface
        )
        with self.assertRaises(ValueError):
            self.prepare(
                bindings=(
                    replace(self.binding, import_surface_identity=surface.identity),
                )
            )

    def test_destination_or_link_collision_is_preserved(self):
        imports = self.prepare()
        root = self.artifact_root()
        outside = self.root / "outside"
        outside.mkdir()
        (root / "node_modules").symlink_to(outside, target_is_directory=True)
        with self.assertRaises((ValueError, OSError)):
            materialize_javascript_library_imports(imports, root)
        self.assertTrue((root / "node_modules").is_symlink())
        self.assertEqual(list(outside.iterdir()), [])

    def test_second_materialization_is_refused(self):
        imports = self.prepare()
        root = self.artifact_root()
        materialize_javascript_library_imports(imports, root)
        with self.assertRaises(ValueError):
            materialize_javascript_library_imports(imports, root)

    def test_materialization_identity_binds_exact_provider_and_edges(self):
        first = self.prepare()
        self.assertEqual(first.identity, self.prepare().identity)
        other, binding = self.provider(self.contract, "module.exports={changed:true};")
        self.assertNotEqual(first.identity, self.prepare((other,), (binding,)).identity)

    def test_current_node_builtin_names_are_rejected_before_blob_reads(self):
        for name in ["fs", "path", "crypto", "_stream_readable"]:
            with self.subTest(name=name):
                self.assertIn(name, self.builtins)
                capability = replace(self.capability, module=name)
                surface = replace(
                    self.surface, package=name, capabilities=(capability,)
                )
                contract = replace(self.contract, library_import_surface=surface)
                self.contracts[contract.component_revision.uri] = contract
                artifact, binding = self.provider(contract, "exports.fake=true;")
                calls = []
                with self.assertRaises(ValueError):
                    self.prepare(
                        (artifact,),
                        (binding,),
                        lambda blob, calls=calls: calls.append(blob),
                    )
                self.assertEqual(calls, [])
        root = self.artifact_root()
        for esm, code in [
            (False, "console.log(require('node:module').isBuiltin('fs'));"),
            (
                True,
                "import {isBuiltin} from 'node:module'; console.log(isBuiltin('fs'));",
            ),
        ]:
            result = self.node(root, code, esm)
            self.assertEqual((result.returncode, result.stdout.strip()), (0, "true"))

    def test_nearer_packages_and_self_references_are_rejected_before_publication(self):
        imports = self.prepare()
        symbol = self.capability.symbols[0]
        subpath = (
            "."
            if self.import_name == self.surface.package
            else "./" + self.import_name[len(self.surface.package) + 1 :]
        )
        for location in ["source/node_modules/" + self.surface.package, "source", "."]:
            with (
                self.subTest(location=location),
                tempfile.TemporaryDirectory(dir=self.root) as temporary,
            ):
                root = Path(temporary).resolve()
                (root / "source").mkdir()
                scope = root / location
                scope.mkdir(parents=True, exist_ok=True)
                metadata = {
                    "name": self.surface.package,
                    "exports": {subpath: "./fake.js"},
                }
                (scope / "package.json").write_text(json.dumps(metadata))
                (scope / "fake.js").write_text("exports." + symbol + "=()=>999;")
                for esm, code in [
                    (
                        False,
                        "const {"
                        + symbol
                        + "}=require("
                        + json.dumps(self.import_name)
                        + ");",
                    ),
                    (
                        True,
                        "import {"
                        + symbol
                        + "} from "
                        + json.dumps(self.import_name)
                        + ";",
                    ),
                ]:
                    result = self.node(
                        root, code + "console.log(" + symbol + "());", esm
                    )
                    self.assertEqual(
                        (result.returncode, result.stdout.strip()),
                        (0, "999"),
                        result.stderr,
                    )
                with self.assertRaises(ValueError):
                    materialize_javascript_library_imports(imports, root)
                self.assertFalse((root / "node_modules").exists())
                self.assertEqual(
                    json.loads((scope / "package.json").read_text()), metadata
                )

    def test_node_reserved_export_target_segment_is_rejected(self):
        surface = replace(
            self.surface,
            capabilities=(
                replace(
                    self.capability,
                    module=self.surface.package + "/node_modules/hidden",
                ),
            ),
        )
        contract = replace(self.contract, library_import_surface=surface)
        self.contracts[contract.component_revision.uri] = contract
        artifact, binding = self.provider(contract, "exports.hidden=1;")
        with self.assertRaises(ValueError):
            self.prepare((artifact,), (binding,))

    def test_source_bom_requires_exact_generic_provider_and_root_edge(self):
        import copy

        from literate_ai.adapters.lifecycle.javascript_libraries import (
            require_javascript_library_source_bom,
        )
        from literate_ai.application.library_artifacts import (
            javascript_library_source_component,
        )

        imports = self.prepare()
        component = javascript_library_source_component(
            self.artifact.component_revision, self.surface
        )
        document = {
            "metadata": {"component": {"bom-ref": "app"}},
            "components": [component],
            "dependencies": [{"ref": "app", "dependsOn": [component["bom-ref"]]}],
        }
        require_javascript_library_source_bom(imports, json.dumps(document).encode())
        for change in ["missing", "substituted", "duplicate", "no-edge"]:
            bad = copy.deepcopy(document)
            if change == "missing":
                bad["components"] = []
            if change == "substituted":
                bad["components"][0]["version"] = "foreign"
            if change == "duplicate":
                bad["components"].append(component)
            if change == "no-edge":
                bad["dependencies"][0]["dependsOn"] = []
            with self.subTest(change=change), self.assertRaises(ValueError):
                require_javascript_library_source_bom(imports, json.dumps(bad).encode())

    def test_project_library_bom_passes_real_metadata_admission(self):
        import copy

        from literate_ai.adapters.dependencies import build_cyclonedx_bom
        from literate_ai.adapters.models.coding_cli import (
            CodingCliError,
            _reconcile_authoritative_source_sbom,
        )
        from literate_ai.application.library_artifacts import (
            javascript_library_source_component,
        )
        from literate_ai.contracts import (
            CYCLONEDX_SOURCE_SBOM_PATH,
            CycloneDxLifecycle,
        )
        from tests.support.fixtures_test_coding_cli_generation import flavor, recipe

        value = recipe(flavor("javascript"))
        canonical, _ = build_cyclonedx_bom(
            lifecycle=CycloneDxLifecycle.SOURCE,
            managed_graph=value.managed_sbom_graph,
            composition_aggregate="complete",
        )
        document = json.loads(canonical)
        component = javascript_library_source_component(
            self.artifact.component_revision, self.surface
        )
        document["components"].append(component)
        root_ref = document["metadata"]["component"]["bom-ref"]
        root_edge = next(d for d in document["dependencies"] if d["ref"] == root_ref)
        root_edge["dependsOn"].append(component["bom-ref"])
        document["dependencies"].append({"ref": component["bom-ref"], "dependsOn": []})
        workspace = self.root / "metadata-admission"
        workspace.joinpath(CYCLONEDX_SOURCE_SBOM_PATH).parent.mkdir(parents=True)

        def admit(content):
            files = {CYCLONEDX_SOURCE_SBOM_PATH: json.dumps(content)}
            _reconcile_authoritative_source_sbom(value, workspace, files)
            return files[CYCLONEDX_SOURCE_SBOM_PATH].encode()

        admitted = admit(document)
        self.assertIn(component, json.loads(admitted)["components"])
        from literate_ai.adapters.lifecycle.javascript_libraries import (
            require_javascript_library_source_bom,
        )

        require_javascript_library_source_bom(self.prepare(), admitted)
        for reserved in [
            "literate-ai:provider-component-revision",
            "literate-ai:library-import-surface",
            "literate-ai:component-revision",
        ]:
            bad = copy.deepcopy(document)
            bad["components"][-1]["properties"].append(
                {"name": reserved, "value": self.artifact.component_revision.uri}
            )
            with (
                self.subTest(property=reserved),
                self.assertRaises(CodingCliError) as raised,
            ):
                admit(bad)
            self.assertEqual(
                raised.exception.code, "coding_cli.generated_metadata_invalid"
            )

    def test_generation_prompt_has_exact_bom_declarations_without_npm_authority(self):
        from literate_ai.adapters.models.coding_cli import RecipeLibraryDependency
        from literate_ai.application.library_artifacts import (
            javascript_library_source_component,
        )
        from literate_ai.contracts import CYCLONEDX_SOURCE_SBOM_PATH
        from tests.support.fixtures_test_coding_cli_generation import flavor, recipe

        dependency = RecipeLibraryDependency(
            self.artifact.component_revision,
            self.capability.capability,
            self.capability.interface_identity,
            self.surface,
        )
        value = replace(
            recipe(flavor("javascript")), library_dependencies=(dependency,)
        )
        prompt = value.prompt()
        expected = javascript_library_source_component(
            self.artifact.component_revision, self.surface
        )
        self.assertIn(
            json.dumps([expected], sort_keys=True, separators=(",", ":")), prompt
        )
        section = prompt.split("### JavaScript sealed-library source BOM", 1)[1]
        self.assertIn(CYCLONEDX_SOURCE_SBOM_PATH, section)
        self.assertIn("Do not add them to npm dependencies", section)
        python_surface = replace(
            self.surface,
            language="python",
            capabilities=(replace(self.capability, module="counter_lib.add"),),
        )
        python_dependency = replace(dependency, import_surface=python_surface)
        self.assertNotIn(
            "### JavaScript sealed-library source BOM",
            replace(
                recipe(flavor("python")), library_dependencies=(python_dependency,)
            ).prompt(),
        )


class JavaScriptLibraryCommandAdapterTests(unittest.TestCase):
    """Typed two-node adapter flow; not an ordinary model-backed rebuild."""

    def test_native_imports_during_build_test_execute_and_cache_reuse(self):
        self._exercise_native_chain(False)

    def test_transitive_native_imports_preserve_nested_provider_packages(self):
        self._exercise_native_chain(True)

    def _exercise_native_chain(self, transitive):
        import sys

        from literate_ai.adapters.lifecycle import (
            LocalComponentToolBinding,
            LocalSourceTreeRegistry,
            LocalStandardLifecyclePorts,
        )
        from literate_ai.adapters.standard_project import (
            _STANDARD_BUILD_DRIVER,
            _encoded_toolchain_environment,
        )
        from literate_ai.contracts import (
            ComponentArtifactExportShape,
            ComponentCommandContract,
            ComponentCommandPhase,
            ComponentCommandToolBinding,
            ComponentLifecycleCommand,
            LibraryCapabilityImport,
            LibraryImportSurface,
        )
        from tests.support.fixtures_test_component_node_generation_preparation import (
            _fixture,
        )
        from tests.support.standard_source_evidence_fixture import (
            register_strict_source,
        )

        node = shutil.which("node")
        if node is None:
            self.skipTest("Node unavailable")
        snapshot, execution = _fixture(
            root_name="application" if transitive else "service",
            library_names=frozenset({"storage", "service"})
            if transitive
            else frozenset({"storage"}),
        )
        python_tool, node_tool = (
            LocalComponentToolBinding(sys.executable),
            LocalComponentToolBinding(node),
        )
        contracts = []
        names = {
            n.revision.identity.uri: n.revision.coordinate.name
            for n in snapshot.authority.lock.nodes
        }
        for plan in execution.generation_plans:
            name = names[plan.component_revision.uri]
            package = "counter_lib" if name == "storage" else "mid_lib"
            library = plan.component_revision != snapshot.authority.lock.root_revision
            public = next(
                n
                for n in snapshot.authority.lock.nodes
                if n.revision.identity == plan.component_revision
            ).revision.public_interfaces
            surface = (
                LibraryImportSurface(
                    "javascript",
                    package,
                    (
                        LibraryCapabilityImport(
                            name + "-api",
                            public[0].identity,
                            package + "/add",
                            ("add",),
                        ),
                    ),
                )
                if library
                else None
            )
            export = name + "-tree"
            commands = (
                ComponentLifecycleCommand(
                    ComponentCommandPhase.BUILD,
                    (
                        "{tool}",
                        "-c",
                        _STANDARD_BUILD_DRIVER,
                        "javascript-tree",
                        json.dumps([node]),
                        _encoded_toolchain_environment(()),
                        "{source_root}",
                        ".",
                        "{object_root}",
                        "{export_path}",
                    ),
                ),
                ComponentLifecycleCommand(
                    ComponentCommandPhase.TEST,
                    (
                        "{tool}",
                        "-e",
                        "require(require('node:path').join(process.argv[1],'source/main.js'))",
                        "{export_path}",
                        "--litai-test",
                        "{artifact_root}",
                    ),
                ),
                ComponentLifecycleCommand(
                    ComponentCommandPhase.EXECUTE,
                    (
                        "{tool}",
                        "-e",
                        "require(require('node:path').join(process.argv[1],'source/main.js'))",
                        "{export_path}",
                        "--litai-smoke",
                        "{artifact_root}",
                    ),
                ),
            )
            contracts.append(
                ComponentCommandContract(
                    plan.component_revision,
                    canonical_identity("authority"),
                    canonical_identity("resolver"),
                    python_tool.toolchain_identity,
                    node_tool.toolchain_identity,
                    node_tool.toolchain_identity,
                    commands,
                    tuple(
                        ComponentCommandToolBinding(
                            p,
                            python_tool.toolchain_identity
                            if p == ComponentCommandPhase.BUILD
                            else node_tool.toolchain_identity,
                        )
                        for p in ComponentCommandPhase
                    ),
                    ComponentArtifactExportShape(
                        export,
                        "library" if library else "executable",
                        canonical_identity("abi"),
                        canonical_identity("target"),
                        "application/vnd.literate-ai.javascript-package-tree"
                        if library
                        else "application/javascript",
                        canonical_identity("producer"),
                    ),
                    library_import_surface=surface,
                )
            )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            registry = LocalSourceTreeRegistry()
            ports = LocalStandardLifecyclePorts(
                source_trees=registry,
                object_root=root / "objects",
                contracts=tuple(contracts),
                tool_bindings=(python_tool, node_tool),
                provider_environment={
                    c.artifact_export.export_id: (
                        "LITAI_PROVIDER_" + c.component_revision.digest[:16].upper(),
                        c.artifact_export.export_id,
                    )
                    for c in contracts
                    if c.is_library
                },
            )
            exports = ()
            previous = None
            by_revision = {c.component_revision.uri: c for c in contracts}
            ordered = sorted(
                execution.generation_plans,
                key=lambda p: {"storage": 0, "service": 1, ("application"): 2}[
                    names[p.component_revision.uri]
                ],
            )
            for plan in ordered:
                name = names[plan.component_revision.uri]
                contract = by_revision[plan.component_revision.uri]
                library = (
                    plan.component_revision != snapshot.authority.lock.root_revision
                )
                source = root / (name + "-source")
                (source / "source").mkdir(parents=True)
                if library:
                    module = source / (
                        "source/"
                        + contract.library_import_surface.capabilities[0].module
                        + ".js"
                    )
                    module.parent.mkdir()
                    module.write_text(
                        "exports.add=(a,b)=>a+b;\n"
                        if previous is None
                        else (
                            "const base=require('counter_lib/add');exports.add=(a,b"
                            ")=>base.add(a,b);\n"
                        )
                    )
                imports = (
                    "const {add}=require("
                    + json.dumps(
                        "./"
                        + contract.library_import_surface.capabilities[0].module
                        + ".js"
                    )
                    + ");"
                    if library
                    else "const {add}=require("
                    + json.dumps(previous.library_import_surface.capabilities[0].module)
                    + ");"
                )
                script = imports + (
                    "if(add(2,3)!==5)throw Error('native import mismatch');"
                    "if(process.argv.includes('--litai-test'))console.log(J"
                    "SON.stringify({schema:'literate-ai/generated-test-resu"
                    "lts@1',cases:['example','boundary','invariant'].map(x="
                    ">({case_id:'fixture-'+x,outcome:'passed'}))}));else co"
                    "nsole.log(JSON.stringify({result:add(2,3)}));"
                )
                (source / "source/main.js").write_text(script)
                from literate_ai.application.library_artifacts import (
                    javascript_library_source_component,
                )

                component = (
                    javascript_library_source_component(
                        previous.component_revision,
                        previous.library_import_surface,
                    )
                    if exports
                    else None
                )
                candidate = register_strict_source(
                    registry,
                    source,
                    snapshot=snapshot,
                    generation_plan=plan,
                    identity_namespace="javascript-command-import-fixture",
                    additional_components=() if component is None else (component,),
                    root_dependency_refs=()
                    if component is None
                    else (component["bom-ref"],),
                )
                intent = ports.create(execution, plan, candidate, exports, ())
                index = ports.index(
                    candidate.component_revision, candidate.tree_identity
                )
                build_plan = ports.finalize(intent, ports.authorize(intent, index))
                built = ports.build(build_plan, exports)
                self.assertEqual(ports.test(build_plan, built.exports).passed_count, 3)
                ports.execute(build_plan, built.exports)
                reused = ports.build(build_plan, exports)
                self.assertEqual(reused.exports, built.exports)
                if not library:
                    self.assertEqual(len(ports.library_consumer_bindings(intent)), 1)
                    target = ports.artifact_path(built.exports[0])
                    self.assertTrue(
                        (
                            target
                            / "node_modules"
                            / previous.library_import_surface.package
                            / "package.json"
                        ).is_file()
                    )
                    if transitive:
                        self.assertTrue(
                            (
                                target
                                / (
                                    "node_modules/mid_lib/.litai-provider/node_modules/coun"
                                    "ter_lib/package.json"
                                )
                            ).is_file()
                        )
                exports = built.exports
                previous = contract
            self.assertEqual(ports.build_cache_hits, len(execution.generation_plans))
