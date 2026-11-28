"""Actual offline wheel build, followed by inert original-input reconstruction."""

import copy
import json
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.dependencies.types import DependencyObservationError
from literate_ai.adapters.lifecycle.standard_local import LocalStandardLifecyclePorts
from literate_ai.adapters.lifecycle.standard_runtime import (
    STANDARD_PYTHON_RUNTIME_DRIVER,
)
from literate_ai.adapters.qualification_capture import (
    QualificationEvidenceReader,
    QualificationEvidenceRecorder,
    verify_qualification_build,
)
from literate_ai.adapters.qualification_python import verify_python_build_inputs
from literate_ai.contracts import (
    ComponentCommandPhase,
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from tests.smoke import test_standard_python_lifecycle as fixtures
from tests.support.fixtures_test_component_node_generation_preparation import _fixture
from tests.support.fixtures_test_standard_local_command_adapter import (
    _python_copy_lifecycle,
)
from tests.support.standard_source_evidence_fixture import register_strict_source


class PythonBuildSemanticReplayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.StandardPythonLifecycleTests.setUpClass()

    def test_native_file_build_replay_and_coherent_missing_context_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            snapshot, execution = _fixture()
            generation = execution.generation_plans[0]
            old, _, _, _ = _python_copy_lifecycle(
                root, prepared=(snapshot, execution), generation_plan=generation
            )
            original = next(iter(old.contracts.values()))
            runtime = replace(
                original.command(ComponentCommandPhase.EXECUTE),
                argv=(
                    "{tool}",
                    "-I",
                    "-S",
                    "-B",
                    "-c",
                    STANDARD_PYTHON_RUNTIME_DRIVER,
                    "{artifact_root}",
                    "{export_path}",
                    "file",
                    "-",
                    "--litai-smoke",
                ),
            )
            command = replace(
                original,
                commands=tuple(
                    runtime if item.phase == ComponentCommandPhase.EXECUTE else item
                    for item in original.commands
                ),
            )
            source = root / "modern-source"
            source.mkdir()
            (source / "app.py").write_text("print('known-output')\n")
            candidate = register_strict_source(
                old.source_trees,
                source,
                snapshot=snapshot,
                generation_plan=generation,
                identity_namespace="python-file-replay",
            )
            ports = LocalStandardLifecyclePorts(
                source_trees=old.source_trees,
                object_root=root / "modern-objects",
                contracts=(command,),
                tool_bindings=tuple(old.tool_bindings.values()),
            )
            recorder = QualificationEvidenceRecorder(
                max_bytes=5000000, max_records=1000
            )
            ports.retain_evidence_with(recorder)
            intent = ports.create(execution, generation, candidate, (), ())
            plan = ports.finalize(
                intent,
                ports.authorize(
                    intent,
                    ports.index(candidate.component_revision, candidate.tree_identity),
                ),
            )
            output = ports.build(plan, ())
            self.assertIsNotNone(ports.execute(plan, output.exports))
            reader = QualificationEvidenceReader(
                recorder.entries, max_bytes=5000000, max_records=1000
            )
            verify_qualification_build(
                reader, plan=plan, build=output.evidence, python_command=command
            )
            # Rehash a complete weaker historical chain, leaving expected original
            # command authority and the provider-free artifact bytes unchanged.
            records = dict(recorder.entries)

            def remember(value):
                identity = canonical_identity(value)
                records[identity] = canonical_json_bytes(value)
                return identity

            observation = reader.read_json(output.evidence.build_observation_identity)
            process = reader.read_json(
                ContentIdentity.parse_uri(observation["process_observation_identity"])
            )
            process.pop("python_build_inputs_identity")
            observation["process_observation_identity"] = remember(process).uri
            observation_id = remember(observation)
            custody = reader.read_json(output.evidence.artifact_custody_identity)
            tree = reader.read_json(
                ContentIdentity.parse_uri(custody["artifact_tree_identity"])
            )
            manifest = next(
                item
                for item in tree["files"]
                if item["path"] == "artifact-manifest.json"
            )
            document = json.loads(
                reader.read_bytes(
                    ContentIdentity.parse_uri("sha256:" + manifest["sha256"])
                )
            )
            document["build_observation"] = observation_id.uri
            manifest["sha256"] = remember(document).digest
            custody["artifact_tree_identity"] = remember(tree).uri
            weaker = replace(
                output.evidence,
                build_observation_identity=observation_id,
                artifact_custody_identity=remember(custody),
            )
            candidate_reader = QualificationEvidenceReader(
                tuple(sorted(records.items(), key=lambda item: item[0].uri)),
                max_bytes=5000000,
                max_records=1000,
            )
            with self.assertRaisesRegex(ValueError, "python-inputs-missing"):
                verify_qualification_build(
                    candidate_reader, plan=plan, build=weaker, python_command=command
                )

    def test_actual_build_reopens_inertly_and_refuses_changed_original_inputs(self):
        fixture = fixtures.StandardPythonLifecycleTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        recorder = QualificationEvidenceRecorder(max_bytes=20000000, max_records=10000)
        fixture.ports.retain_evidence_with(recorder)
        output = fixture.build()
        reader = QualificationEvidenceReader(
            recorder.entries, max_bytes=20000000, max_records=10000
        )
        command = fixture.closure.contracts[0]
        observation = reader.read_json(output.evidence.build_observation_identity)
        process = reader.read_json(
            ContentIdentity.parse_uri(observation["process_observation_identity"])
        )
        context = reader.read_json(
            ContentIdentity.parse_uri(process["python_build_inputs_identity"])
        )
        tree = reader.read_json(
            ContentIdentity.parse_uri(observation["artifact_tree_identity"])
        )
        # Native build/install above used original owners. Replay below has only
        # immutable records, with path reads and subprocess launches forbidden.
        with (
            patch("builtins.open", side_effect=AssertionError("file access")),
            patch.object(Path, "open", side_effect=AssertionError("path access")),
            patch.object(subprocess, "Popen", side_effect=AssertionError("process")),
        ):
            verify_qualification_build(
                reader, plan=fixture.plan, build=output.evidence, python_command=command
            )
            changes = {
                "missing-runtime": lambda value: value.update(runtime_files=[]),
                "foreign-runtime-commitment": lambda value: value.update(
                    runtime_evidence_identity=canonical_identity("foreign").uri
                ),
                "foreign-recipe": lambda value: value.update(
                    recipe_identity=canonical_identity("foreign").uri
                ),
                "extra-field": lambda value: value.update(extra=True),
            }
            original_dependency = reader.read_json(
                ContentIdentity.parse_uri(context["runtime_evidence_identity"])
            )
            measured = reader.read_json(
                ContentIdentity.parse_uri(original_dependency["target_identity"])
            )
            if measured["environment"]["os_name"] != "nt":
                changes["runtime-permissions"] = lambda value: value["runtime_files"][
                    0
                ].update(mode=value["runtime_files"][0]["mode"] ^ 0o111)
            for name, change in changes.items():
                changed = copy.deepcopy(context)
                change(changed)
                identity = canonical_identity(changed)
                records = dict(recorder.entries)
                records[identity] = canonical_json_bytes(changed)
                candidate_reader = QualificationEvidenceReader(
                    tuple(sorted(records.items(), key=lambda item: item[0].uri)),
                    max_bytes=20000000,
                    max_records=10000,
                )
                with (
                    self.subTest(change=name),
                    self.assertRaises((ValueError, DependencyObservationError)),
                ):
                    verify_python_build_inputs(
                        candidate_reader,
                        plan=fixture.plan,
                        build=output.evidence,
                        process={"python_build_inputs_identity": identity.uri},
                        artifact_files=tree["files"],
                        expected_command=command,
                    )
