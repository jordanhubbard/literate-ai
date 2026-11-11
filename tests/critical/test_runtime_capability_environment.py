"""Controlled factory tests; installed graph proof is recorded separately."""

from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

from literate_ai.adapters.lifecycle import LocalSourceTreeRegistry
from literate_ai.adapters.lifecycle.standard_local import LocalStandardLifecycleError
from literate_ai.adapters.standard_project import (
    assemble_standard_lifecycle_ports,
    project_standard_toolchain_closure,
)
from literate_ai.contracts import (
    ArtifactExport,
    BlobRef,
    ComponentCommandPhase,
    ComponentLifecycleCommand,
    DependencyKind,
    ExecutableComponentEdge,
    canonical_identity,
)
from tests.support.fixtures_test_standard_project_factory import (
    _command_contracts,
    _fixture,
    _toolchain_closure,
)

READ_CAPABILITIES = (
    "import json,os,subprocess,sys; "
    "names=('LITAI_CAPABILITY_SERVICE_API','LITAI_CAPABILITY_STORAGE_API',"
    "'LITAI_CAPABILITY_GHOST'); "
    "values=dict((name,os.environ.get(name)) for name in names); "
    "values['outputs']=[json.loads(subprocess.run([sys.executable,value],"
    "capture_output=True,text=True,check=True,timeout=5).stdout) "
    "for name,value in values.copy().items() if value]; "
    "print(json.dumps(values,sort_keys=True))"
)


class RuntimeCapabilityEnvironmentTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        snapshot, self.execution = _fixture(dependency_kind=DependencyKind.RUNTIME)
        self.names = {
            node.revision.identity.uri: node.revision.coordinate.name
            for node in snapshot.authority.lock.nodes
        }
        contracts, self.tools = _command_contracts(self.execution)
        self.contracts = tuple(
            replace(
                contract,
                commands=tuple(
                    ComponentLifecycleCommand(
                        ComponentCommandPhase.EXECUTE,
                        ("{tool}", "-c", READ_CAPABILITIES, "{artifact_root}"),
                    )
                    if command.phase is ComponentCommandPhase.EXECUTE
                    else command
                    for command in contract.commands
                ),
            )
            for contract in contracts
        )
        self.ports = self.make_ports(self.execution, "initial")

    def make_ports(self, execution, label):
        initial = _toolchain_closure(execution, self.contracts, self.tools)
        by_export = {
            contract.artifact_export.export_id: contract for contract in self.contracts
        }
        bindings = {
            export_id: (value[0], export_id)
            for export_id, value in initial.provider_environment.items()
        }
        closure = project_standard_toolchain_closure(
            execution,
            contracts=self.contracts,
            tool_bindings=self.tools,
            provider_environment=bindings,
            dependency_observation=initial.dependency_observation,
            observer_identity=initial.record.observer_identity,
        )
        ports = assemble_standard_lifecycle_ports(
            object_root=self.root / label,
            toolchain_closure=closure,
            source_trees=LocalSourceTreeRegistry(),
        ).ports
        exports = []
        for export_id, contract in sorted(by_export.items()):
            if export_id not in bindings:
                continue
            name = self.names[contract.component_revision.uri]
            payload = (
                "import json; print(json.dumps(dict(provider=" + repr(name) + ")))\n"
            ).encode()
            directory = self.root / label / name
            directory.mkdir()
            (directory / export_id).write_bytes(payload)
            shape = contract.artifact_export
            export = ArtifactExport(
                export_id,
                contract.component_revision,
                shape.role,
                shape.abi_identity,
                shape.target_identity,
                shape.media_type,
                shape.producer_identity,
                canonical_identity({"fixture-source": name}),
                self.tools[0].toolchain_identity,
                canonical_identity({"fixture-authorization-data": name}),
                (),
                BlobRef(
                    hashlib.sha256(payload).hexdigest(),
                    len(payload),
                    media_type=shape.media_type,
                ),
            )
            exports.append(export)
            ports._artifact_paths[export.identity.uri] = directory
            ports._exports_by_identity[export.identity.uri] = export
        self.exports = tuple(exports)
        return ports

    def contract(self, name):
        return next(
            item
            for item in self.contracts
            if self.names[item.component_revision.uri] == name
        )

    def invoke(self, name="application", *, ports=None):
        ports = ports or self.ports
        contract = self.contract(name)
        directory = self.root / (name + "-consumer")
        directory.mkdir(exist_ok=True)
        completed = ports._run_locked(
            contract,
            ComponentCommandPhase.EXECUTE,
            source_root=directory,
            object_root=directory,
            artifact_root=directory,
            export_path=directory / contract.artifact_export.export_id,
            providers=self.exports,
        )
        return json.loads(completed.stdout)

    def test_public_binding_reaches_real_provider_process(self):
        result = self.invoke()
        self.assertEqual(result["outputs"], [{"provider": "service"}])
        self.assertIsNone(result["LITAI_CAPABILITY_STORAGE_API"])
        self.assertIsNone(result["LITAI_CAPABILITY_GHOST"])

    def test_transitive_provider_is_not_a_direct_consumer_alias(self):
        result = self.invoke("service")
        self.assertEqual(result["outputs"], [{"provider": "storage"}])
        self.assertIsNone(result["LITAI_CAPABILITY_SERVICE_API"])

    def test_ambient_alias_cannot_override_or_add_a_runtime_input(self):
        with mock.patch.dict(
            "os.environ",
            {
                "LITAI_CAPABILITY_SERVICE_API": str(self.root / "unapproved"),
                "LITAI_CAPABILITY_GHOST": str(self.root / "foreign"),
            },
        ):
            result = self.invoke()
        self.assertEqual(result["outputs"], [{"provider": "service"}])
        self.assertIsNone(result["LITAI_CAPABILITY_GHOST"])

    def test_no_automatic_runtime_aliases_during_build_or_generated_tests(self):
        for phase in (ComponentCommandPhase.BUILD, ComponentCommandPhase.TEST):
            with self.subTest(phase=phase):
                values = self.ports._runtime_capability_environment(
                    {}, self.exports, self.execution.root_revision, phase
                )
                self.assertEqual(values, {})

    def test_changed_or_removed_held_plan_refuses_before_process_launch(self):
        for value in (
            replace(self.execution, planner_identity=canonical_identity("changed")),
            None,
        ):
            with self.subTest(value=value is None):
                self.ports._runtime_execution_plan = value
                with self.assertRaisesRegex(
                    LocalStandardLifecycleError, "runtime execution plan changed"
                ):
                    self.invoke()
        self.ports._runtime_execution_plan = self.execution

    def test_distinct_providers_cannot_share_a_capability_alias(self):
        storage = self.contract("storage").component_revision
        extra = ExecutableComponentEdge(
            self.execution.root_revision,
            storage,
            "additional-service",
            "other.service-api",
            DependencyKind.RUNTIME,
            None,
        )
        actions = tuple(
            replace(
                action,
                dependency_edges=tuple(
                    sorted(
                        (*action.dependency_edges, extra),
                        key=lambda edge: (
                            edge.consumer_revision.uri,
                            edge.provider_revision.uri,
                            edge.requirement_id,
                            edge.kind.value,
                        ),
                    )
                ),
            )
            if any(
                edge.kind is DependencyKind.RUNTIME for edge in action.dependency_edges
            )
            else action
            for action in self.execution.action_plans
        )
        execution = replace(self.execution, action_plans=actions)
        ports = self.make_ports(execution, "collision")
        with mock.patch.object(ports, "_run_with_environment") as launch:
            with self.assertRaisesRegex(
                LocalStandardLifecycleError, "alias is ambiguous"
            ):
                self.invoke(ports=ports)
            launch.assert_not_called()

    def test_missing_provider_cannot_be_replaced_by_an_ambient_path(self):
        self.exports = tuple(
            item
            for item in self.exports
            if self.names[item.component_revision.uri] != "service"
        )
        with (
            mock.patch.dict("os.environ", {"LITAI_CAPABILITY_SERVICE_API": "/foreign"}),
            mock.patch.object(self.ports, "_run_with_environment") as launch,
        ):
            with self.assertRaisesRegex(
                LocalStandardLifecycleError, "runtime provider is unavailable"
            ):
                self.invoke()
            launch.assert_not_called()
