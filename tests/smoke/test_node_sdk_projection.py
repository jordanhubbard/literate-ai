"""Real selected SDK tools through locked projection and runtime assembly.

Reviewed canonical SDK Flavors/generation policy remain a separate gate. These
fixtures author explicit local profiles; no generated source or SDK acceptance.
"""

import json
import os
import shutil
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import yaml

from literate_ai.adapters.lifecycle import LocalSourceTreeRegistry
from literate_ai.adapters.lifecycle.standard_bazel import StandardBazelLifecyclePorts
from literate_ai.adapters.lifecycle.standard_cargo import StandardCargoLifecyclePorts
from literate_ai.adapters.lifecycle.standard_mix import StandardMixLifecyclePorts
from literate_ai.adapters.node_sdk_typescript import NodeSDKTypeScriptCompiler
from literate_ai.adapters.standard_project import (
    StandardCommandProjectionError,
    assemble_standard_lifecycle_ports,
    project_locked_standard_toolchain_closure,
)
from literate_ai.contracts import (
    ComponentCommandPhase,
    StandardNodeSDKCommandProfile,
)
from literate_ai.contracts.authoring_markdown import render_authoring_markdown
from literate_ai.contracts.node_sdk import NodeSDKExportDeclaration
from tests.smoke.test_standard_command_projection import _locked_snapshot, _observation


def edit_header(path, change):
    _opening, header, body = path.read_text().split("---", 2)
    value = yaml.safe_load(header)
    change(value)
    path.write_bytes(render_authoring_markdown(value, body))


def sdk_snapshot(
    root,
    *,
    profile=True,
    constraint=True,
    build_system=None,
    compiler_policy=None,
    npm_policy=None,
):
    def configure(component, flavors):
        def component_policy(value):
            value["library_imports"] = [
                {
                    "language": "typescript",
                    "package": "sample",
                    "capability": "sample.portable-app",
                    "module": "sample",
                    "symbols": ["add"],
                    "node_sdk_exports": [
                        NodeSDKExportDeclaration("sample", "index").to_dict()
                    ],
                }
            ]

        edit_header(component / "component.md", component_policy)

        def language_policy(value):
            value["target"] = "typescript"
            for contribution in value["contributions"]:
                if contribution["kind"] == "toolchain":
                    contribution["slot"] = "node"

        edit_header(flavors / "lang-python/flavor.md", language_policy)
        repository = Path(__file__).resolve().parents[2]
        shutil.copyfile(
            repository / "flavors/lang-typescript/standard-command-profile.json",
            flavors / "lang-python/standard-command-profile.json",
        )
        (flavors / "lang-python/toolchain.json").write_text(
            json.dumps(
                {
                    "schema": "urn:literate-ai:schema:v2:toolchain-constraint",
                    "toolchain": "node",
                    "minimum_version": [20],
                }
            )
        )

        def package_policy(value):
            value["target"] = "node-sdk"
            value["secondary_constraints"][0]["value"] = "typescript"
            value["co_requisites"] = ["flavor://literate-ai/lang-python"]
            if not profile:
                value["contributions"] = [
                    c for c in value["contributions"] if c["kind"] != "builder"
                ]
            if constraint:
                value["contributions"].append(
                    {
                        "contribution_id": "typescript-image",
                        "kind": "toolchain",
                        "merge_operator": "exact-singleton",
                        "slot": "typescript",
                        "content": {
                            "kind": "toolchain-constraint",
                            "uri": "typescript.json",
                        },
                    }
                )

        edit_header(flavors / "package-npm/flavor.md", package_policy)
        (flavors / "package-npm/standard-command-profile.json").write_text(
            json.dumps(
                StandardNodeSDKCommandProfile(
                    "node-sdk", "npm", "typescript", "src", ("LICENSE",)
                ).to_dict()
            )
        )
        (flavors / "package-npm/typescript.json").write_text(
            json.dumps(
                {
                    "schema": "urn:literate-ai:schema:v2:toolchain-constraint",
                    "toolchain": "typescript",
                    "minimum_version": [5, 8],
                    "maximum_exclusive_version": [7],
                }
            )
        )
        if compiler_policy:
            path = flavors / "package-npm/typescript.json"
            value = json.loads(path.read_text())
            value.update(compiler_policy)
            path.write_text(json.dumps(value))
        if npm_policy:
            path = flavors / "package-npm/toolchain.json"
            value = json.loads(path.read_text())
            value.update(npm_policy)
            path.write_text(json.dumps(value))

    return _locked_snapshot(
        root,
        no_entrypoint=True,
        package_npm=True,
        build_system=build_system,
        before_lock=configure,
    )


@unittest.skipUnless(
    os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node")
    and os.name == "posix",
    "requires selected Node/npm/TypeScript package",
)
class NodeSDKProjectionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.environment = dict(os.environ)
        self.environment["LITAI_TYPESCRIPT_SDK"] = os.environ["LITERATE_TYPESCRIPT_SDK"]

    def project(self, **options):
        phases = options.pop("phases", tuple(ComponentCommandPhase))
        _component, snapshot, execution = sdk_snapshot(self.root, **options)
        closure = project_locked_standard_toolchain_closure(
            snapshot,
            execution,
            environment=self.environment,
            host_platform="macos",
            dependency_observer=_observation,
            command_phases=phases,
        )
        return closure

    def test_selected_sdk_targets_survive_specialized_backend_construction(self):
        closure = self.project()
        for backend, selected in (
            (StandardCargoLifecyclePorts, {"cargo_targets": ()}),
            (StandardBazelLifecyclePorts, {"bazel_targets": ()}),
            (StandardMixLifecyclePorts, {"mix_targets": ()}),
        ):
            with self.subTest(backend=backend.__name__):
                arguments = dict(
                    source_trees=LocalSourceTreeRegistry(),
                    object_root=self.root / backend.__name__,
                    contracts=closure.contracts,
                    tool_bindings=closure.tool_bindings,
                    node_sdk_targets=closure.node_sdk_targets,
                    **selected,
                )
                ports = backend(**arguments)
                target = closure.node_sdk_targets[0]
                self.assertIs(
                    ports.node_sdk_targets[target.component_revision.uri], target
                )
                with self.assertRaisesRegex(TypeError, "exact SDK targets"):
                    backend(**{**arguments, "node_sdk_targets": (object(),)})
        closure.require_unchanged()

    def test_real_selected_target_assembles_and_retains_exact_membership(self):
        closure = self.project()
        closure.require_unchanged()
        self.assertEqual(len(closure.node_sdk_targets), 1)
        target = closure.node_sdk_targets[0]
        contract = closure.contracts[0]
        target.require_contract(contract)
        self.assertIn(
            target.typescript.snapshot_identity.uri,
            json.dumps(closure.dependency_observation.components),
        )
        self.assertIn(
            target.typescript.compiler.sdk.identity.uri,
            json.dumps(closure.dependency_observation.components),
        )
        self.assertEqual(
            target.identity,
            closure.record.component_authorities[0].build_target_identity,
        )
        composition = assemble_standard_lifecycle_ports(
            object_root=self.root / "objects",
            toolchain_closure=closure,
            source_trees=LocalSourceTreeRegistry(),
        )
        self.assertIs(
            composition.ports.node_sdk_targets[contract.component_revision.uri], target
        )
        self.assertEqual(
            set(composition.ports.tool_bindings),
            {
                target.typescript.identity,
                target.npm.identity,
                target.typescript.node.identity,
            },
        )
        for changed in (
            replace(closure, node_sdk_targets=()),
            replace(closure, node_sdk_targets=(replace(target, version="1.0.1"),)),
            replace(closure, node_sdk_targets=(target, target)),
            replace(
                closure,
                tool_bindings=tuple(
                    b
                    for b in closure.tool_bindings
                    if b.toolchain_identity.uri != target.npm.identity
                ),
            ),
        ):
            with (
                self.subTest(changed=changed.record.identity),
                self.assertRaises(ValueError),
            ):
                changed.require_unchanged()
        last = closure.toolchain_authorities[-1]

        def lose_membership():
            last.require_unchanged()
            object.__setattr__(closure, "node_sdk_targets", (target, target))

        altered = replace(last, _guard=lose_membership)
        original_authorities = closure.toolchain_authorities
        try:
            object.__setattr__(
                closure, "toolchain_authorities", (*original_authorities[:-1], altered)
            )
            with self.assertRaisesRegex(
                ValueError, "membership changed during validation"
            ):
                closure.require_unchanged()
        finally:
            object.__setattr__(closure, "node_sdk_targets", (target,))
            object.__setattr__(closure, "toolchain_authorities", original_authorities)

    def test_test_only_scope_has_no_build_binding_or_phase(self):
        phases = (ComponentCommandPhase.TEST,)
        closure = self.project(phases=phases)
        ports = assemble_standard_lifecycle_ports(
            object_root=self.root / "objects",
            toolchain_closure=closure,
            source_trees=LocalSourceTreeRegistry(),
            command_phases=phases,
        ).ports
        target = closure.node_sdk_targets[0]
        self.assertEqual(set(ports.tool_bindings), {target.typescript.node.identity})
        with self.assertRaisesRegex(RuntimeError, "phase"):
            ports._require_command_phase(ComponentCommandPhase.BUILD)

    def test_dual_surface_without_sdk_profile_is_refused(self):
        with self.assertRaises(StandardCommandProjectionError) as failure:
            self.project(profile=False)
        self.assertEqual(
            failure.exception.code, "standard_command.node_sdk_profile_required"
        )

    def test_missing_compiler_constraint_is_refused(self):
        with self.assertRaises(StandardCommandProjectionError) as failure:
            self.project(constraint=False)
        self.assertEqual(
            failure.exception.code,
            "standard_command.node_sdk_compiler_constraint_missing",
        )

    def test_relative_compiler_selection_is_refused_without_install(self):
        self.environment["LITAI_TYPESCRIPT_SDK"] = "relative/compiler"
        with self.assertRaises(StandardCommandProjectionError) as failure:
            self.project()
        self.assertEqual(
            failure.exception.code, "standard_command.node_sdk_compiler_unavailable"
        )

    def test_competing_build_profile_is_refused(self):
        with self.assertRaises(StandardCommandProjectionError) as failure:
            self.project(build_system="make")
        self.assertEqual(
            failure.exception.code, "standard_command.node_sdk_profile_unsupported"
        )

    def test_required_compiler_prefix_is_enforced_without_compilation(self):
        version = json.loads(
            (
                Path(self.environment["LITAI_TYPESCRIPT_SDK"]) / "package.json"
            ).read_text()
        )["version"]
        mismatched = 5 if version.startswith("6.") else 6
        with mock.patch.object(
            NodeSDKTypeScriptCompiler,
            "run",
            side_effect=AssertionError("compiler must not execute"),
        ):
            with self.assertRaises(StandardCommandProjectionError) as failure:
                self.project(compiler_policy={"required_version": [mismatched]})
        self.assertEqual(
            failure.exception.code, "standard_command.node_sdk_compiler_unavailable"
        )

    def test_exact_compiler_command_is_enforced_without_compilation(self):
        with mock.patch.object(
            NodeSDKTypeScriptCompiler,
            "run",
            side_effect=AssertionError("compiler must not execute"),
        ):
            with self.assertRaises(StandardCommandProjectionError) as failure:
                self.project(compiler_policy={"command": ["unselected-tsc"]})
        self.assertEqual(
            failure.exception.code, "standard_command.node_sdk_compiler_unavailable"
        )

    def test_exact_npm_command_is_enforced_without_compilation(self):
        with mock.patch.object(
            NodeSDKTypeScriptCompiler,
            "run",
            side_effect=AssertionError("compiler must not execute"),
        ):
            with self.assertRaises(StandardCommandProjectionError) as failure:
                self.project(npm_policy={"command": ["unselected-npm"]})
        self.assertEqual(
            failure.exception.code, "standard_command.node_sdk_compiler_unavailable"
        )
