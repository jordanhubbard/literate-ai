"""Actual alias-bearing worker source custody with explicit copy-command fixtures.

These operations grant no native Python import, provider acceptance or execution.
"""

import json
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from literate_ai.adapters.action_build_record import BuildWorkerInput
from literate_ai.adapters.action_build_source import materialize_build_source
from literate_ai.adapters.action_dispatch_wire import (
    ActionDispatchDeadline,
    ActionWireError,
    record_identity,
)
from literate_ai.adapters.source_evidence_validation import (
    SourceEvidenceValidationInputs,
)
from literate_ai.contracts import canonical_json_bytes
from literate_ai.contracts.generation_cache import CachedSourceFile
from literate_ai.storage import FileSystemCAS
from tests.support.action_deadline import ACTION_TEST_DEADLINE
from tests.support.fixtures_test_component_node_generation_preparation import _fixture
from tests.support.fixtures_test_standard_local_command_adapter import (
    _python_copy_lifecycle,
)


class ManagedPythonSourceTransferTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        snapshot, self.execution = _fixture(
            root_name="service", library_names=frozenset({"storage"})
        )
        revision = next(
            n.revision.identity
            for n in snapshot.authority.lock.nodes
            if n.revision.coordinate.name == "service"
        )
        self.generation = next(
            p
            for p in self.execution.generation_plans
            if p.component_revision == revision
        )
        controller = self.root / "controller"
        controller.mkdir()
        self.ports, _, self.candidate, intent = _python_copy_lifecycle(
            controller,
            prepared=(snapshot, self.execution),
            generation_plan=self.generation,
        )
        authorization = self.ports.authorize(
            intent, self.ports.index(revision, self.candidate.tree_identity)
        )
        self.inputs = self.ports.plan_finalization_inputs(intent, authorization)
        self.plan = self.inputs.finalize()
        self.custody = self.ports.source_trees.evidence(self.candidate.tree_identity)
        original = self.ports.source_trees.validation_inputs(
            self.candidate.tree_identity
        )
        self.validation = SourceEvidenceValidationInputs.from_dict(original.to_dict())
        self.assertEqual(self.validation, original)
        self.assertEqual(
            self.validation.to_dict()["schema"],
            "literate-ai/source-evidence-validation@4",
        )
        self.assertTrue(self.validation.managed_python_imports)
        source = self.ports.source_trees.resolve(self.candidate.tree_identity)
        self.before = {
            p.relative_to(source).as_posix(): p.read_bytes()
            for p in source.rglob("*")
            if p.is_file()
        }
        self.controller_cas = FileSystemCAS(self.root / "controller-cas")
        self.files = tuple(
            CachedSourceFile(name, self.controller_cas.put_bytes(content))
            for name, content in sorted(self.before.items())
        )
        self.cas = FileSystemCAS(self.root / "worker-cas")
        self.workspace = self.root / "workspace"
        self.workspace.mkdir()
        self.deadline = ActionDispatchDeadline(datetime.now(UTC) + ACTION_TEST_DEADLINE)
        self.now = authorization.grant.issued_at + timedelta(seconds=1)

    def scope(self, **changes):
        arguments = dict(
            plan=self.plan,
            inputs=self.inputs,
            candidate=self.candidate,
            files=self.files,
            validation_inputs=self.validation,
            source_generation_identity=self.custody.source_generation_identity,
            source_custody_identity=self.custody.identity,
            deadline=self.deadline,
            cas=self.cas,
            workspace_root=self.workspace,
            blob_source=self.controller_cas.get_bytes,
            clock=lambda: self.now,
        )
        arguments.update(changes)
        return materialize_build_source(**arguments)

    def test_original_worker_materializer_retains_exact_alias_inputs_and_custody(self):
        with self.scope() as registry:
            self.assertEqual(
                registry.evidence(self.candidate.tree_identity).identity,
                self.custody.identity,
            )
            self.assertEqual(
                registry.validation_inputs(self.candidate.tree_identity),
                self.validation,
            )
            source = registry.resolve(self.candidate.tree_identity)
            self.assertEqual(
                {
                    p.relative_to(source).as_posix(): p.read_bytes()
                    for p in source.rglob("*")
                    if p.is_file()
                },
                self.before,
            )
        self.assertFalse(list(self.workspace.iterdir()))
        source = self.ports.source_trees.resolve(self.candidate.tree_identity)
        self.assertEqual(
            {
                p.relative_to(source).as_posix(): p.read_bytes()
                for p in source.rglob("*")
                if p.is_file()
            },
            self.before,
        )

    def test_changed_or_stripped_alias_authority_refuses_actual_original_source(self):
        provider, _alias = self.validation.managed_python_imports[0]
        for declarations in ((), ((provider, "foreign_module"),)):
            changed = replace(
                self.validation,
                managed_python_imports=declarations,
                recipe_document=None,
            )
            restored = SourceEvidenceValidationInputs.from_dict(changed.to_dict())
            with self.subTest(declarations=declarations), self.assertRaises(ValueError):
                with self.scope(validation_inputs=restored):
                    self.fail("changed portable authority admitted original source")
            self.assertFalse(list(self.workspace.iterdir()))

    def test_original_action_digest_binds_alias_record_before_materialization(self):
        record = BuildWorkerInput(
            self.execution.identity,
            self.generation.identity,
            self.candidate,
            self.plan,
            self.inputs,
            self.files,
            self.validation,
            self.custody.source_generation_identity,
            self.custody.identity,
            self.generation,
            self.execution,
        )
        content = record.to_bytes()
        identity = record_identity(content)
        restored = BuildWorkerInput.admit(
            content, identity, self.deadline, now=self.now
        )
        self.assertEqual(restored.source_validation, self.validation)
        changed = json.loads(content)
        changed["source_validation"]["managed_python_imports"][0][
            "top_level_import"
        ] = "foreign_module"
        with self.assertRaises(ActionWireError):
            BuildWorkerInput.admit(
                canonical_json_bytes(changed), identity, self.deadline, now=self.now
            )
        self.assertFalse(list(self.workspace.iterdir()))

    def test_revocation_during_alias_source_fetch_refuses_before_admission(self):
        revoked = False

        def guard():
            if revoked:
                raise ActionWireError("fixture.revoked", "source admission revoked")

        def fetch(reference):
            nonlocal revoked
            content = self.controller_cas.get_bytes(reference)
            revoked = True
            return content

        with self.assertRaises(ActionWireError) as error:
            with self.scope(blob_source=fetch, admission_guard=guard):
                self.fail("revoked source admitted")
        self.assertEqual(error.exception.code, "fixture.revoked")
        self.assertFalse(list(self.workspace.iterdir()))
