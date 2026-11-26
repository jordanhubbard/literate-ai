"""Real consumer conversion custody, separately from inert authored provider intent.

Contained metadata unit controls explicitly inject source admission and empty
lock observations; they exercise file/context custody, not migration qualification.
Public facade controls use the actual retained consumer authority readers.
"""

import copy
import hashlib
import os
import pickle
import stat
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_wrapper as authored_wrapper
from literate_ai.adapters import retained_cargo_wrapper_core as core
from literate_ai.adapters.authored_retained_cargo_scratch import (
    reserve_authored_retained_cargo_scratch,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    AuthoredRetainedCargoWrapperContext,
    AuthoredRetainedCargoWrapperObservation,
    authored_retained_cargo_wrapper_context,
)
from literate_ai.adapters.lifecycle_lock import (
    ProjectLifecycleLockError,
    project_lifecycle_lock,
)
from literate_ai.adapters.project_scaffold_placement import ScaffoldLayout
from literate_ai.adapters.retained_cargo_scratch_v2 import (
    reserve_retained_cargo_scratch_v2,
)
from literate_ai.adapters.retained_cargo_wrapper_v2 import (
    RetainedCargoWrapperContextV2,
    retained_cargo_wrapper_context_v2,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.projects import ProjectConfigurationStore, ProjectError
from tests.critical import test_authored_retained_cargo_review as declarations
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture


class AuthoredRetainedCargoWrapperTests(unittest.TestCase):
    @contextmanager
    def fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(Path(directory).resolve(strict=True)) as old:
                helper = declarations.AuthoredRetainedCargoReviewTests("runTest")
                binding = helper.fixture(old)
                reference = helper.write_binding(old.project.root, binding)
                reviewed = helper.read(old.project.root, reference)
                yield old, reviewed

    def test_actual_consumer_authority_is_distinct_and_expires_without_outputs(self):
        with self.fixture() as (_old, reviewed):
            with authored_retained_cargo_wrapper_context(reviewed) as context:
                self.assertIs(type(context), AuthoredRetainedCargoWrapperContext)
                self.assertNotIsInstance(context, RetainedCargoWrapperContextV2)
                self.assertEqual(
                    context.conversion.release_authority, "original-source"
                )
                self.assertTrue(
                    context.workspace.is_relative_to(context.implementation)
                )
                self.assertTrue(context.bindings)
                self.assertIsNotNone(context.source_authority)
                identity = context.identity
                self.assertEqual(identity, context.identity)
                for _identity, path in reviewed.binding.destinations:
                    self.assertFalse((reviewed.project.root / path).exists())
                for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                    for owner in (context, context._core):
                        with self.subTest(
                            operation=operation.__name__, owner=type(owner)
                        ):
                            with self.assertRaises(TypeError):
                                operation(owner)
                with self.assertRaisesRegex(TypeError, "v2-live-wrapper-required"):
                    with reserve_retained_cargo_scratch_v2(context):
                        self.fail("authored wrapper entered source-v2 scratch")
            with self.assertRaisesRegex(ValueError, "wrapper-operation-ended"):
                context.require_unchanged()
            with self.assertRaisesRegex(ValueError, "wrapper-operation-ended"):
                _ = context.identity

    def test_cross_origin_public_gates_refuse_before_private_core_or_lock(self):
        with self.fixture() as (old, reviewed):
            with (
                patch(
                    "literate_ai.adapters.retained_cargo_wrapper_v2._open_consumer_wrapper_context",
                    side_effect=AssertionError("source core entered"),
                ) as source,
                patch(
                    "literate_ai.adapters.authored_retained_cargo_wrapper._open_consumer_wrapper_context",
                    side_effect=AssertionError("authored core entered"),
                ) as authored,
            ):
                with self.assertRaisesRegex(TypeError, "v2-reviewed-files-required"):
                    with retained_cargo_wrapper_context_v2(reviewed):
                        self.fail("authored declarations entered source view")
                with self.assertRaisesRegex(
                    TypeError, "authored-reviewed-files-required"
                ):
                    with authored_retained_cargo_wrapper_context(old):
                        self.fail("source declarations entered authored view")
                source.assert_not_called()
                authored.assert_not_called()

    def test_source_wrapper_identity_document_retains_exact_legacy_shape(self):
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(
                Path(directory).resolve(strict=True)
            ) as reviewed:
                with retained_cargo_wrapper_context_v2(reviewed) as context:
                    expected = canonical_identity(
                        {
                            "schema": "literate-ai/retained-cargo-wrapper-context@2",
                            "reviewed": reviewed._captured_identity().uri,
                            "revision": context.revision.uri,
                            "conversion": context.conversion.identity.uri,
                            "source_authority": context.source_authority.uri,
                            "implementation": context.implementation.relative_to(
                                reviewed.project.root
                            ).as_posix(),
                            "locks": [
                                lock.identity.uri for lock, _catalog in context.bindings
                            ],
                        }
                    )
                    self.assertEqual(context.identity, expected)
                    self.assertEqual(context._captured_identity(), expected)

    def test_both_entries_contend_with_the_existing_project_mutation_lock(self):
        with self.fixture() as (old, reviewed):
            with project_lifecycle_lock(
                reviewed.project.root, operation="peer-fixture"
            ):
                for entry, value in (
                    (retained_cargo_wrapper_context_v2, old),
                    (authored_retained_cargo_wrapper_context, reviewed),
                ):
                    with self.subTest(entry=entry.__name__):
                        with self.assertRaisesRegex(
                            ProjectLifecycleLockError, "peer-fixture"
                        ):
                            with entry(value):
                                self.fail("wrapper bypassed existing mutation lock")

    def test_readonly_facts_do_not_acquire_or_mutate_a_live_peer_lock_or_grant_scratch(
        self,
    ):
        def snapshot(root):
            result = {}
            for path in root.rglob("*"):
                node = path.lstat()
                name = path.relative_to(root).as_posix()
                if stat.S_ISLNK(node.st_mode):
                    result[name] = node.st_mode, os.readlink(path)
                elif stat.S_ISREG(node.st_mode):
                    result[name] = (
                        node.st_mode,
                        hashlib.sha256(path.read_bytes()).hexdigest(),
                    )
                else:
                    result[name] = (node.st_mode,)
            return result

        with self.fixture() as (_old, reviewed):
            root = reviewed.project.root
            with project_lifecycle_lock(root, operation="actual-peer-original-owner"):
                before = snapshot(root)
                with authored_retained_cargo_wrapper_context(
                    reviewed, read_only=True
                ) as context:
                    self.assertIs(
                        type(context), AuthoredRetainedCargoWrapperObservation
                    )
                    self.assertIs(
                        type(context._core), core._ReadOnlyCargoConsumerWrapper
                    )
                    self.assertIsNotNone(context.identity)
                    self.assertEqual(snapshot(root), before)
                    with patch.object(
                        os,
                        "open",
                        side_effect=AssertionError(
                            "readonly scratch attempted native open"
                        ),
                    ):
                        with self.assertRaisesRegex(
                            TypeError, "authored-live-wrapper-required"
                        ):
                            with reserve_authored_retained_cargo_scratch(context):
                                self.fail("read-only observation reserved output")
                        with self.assertRaisesRegex(
                            TypeError, "authored-live-wrapper-context-required"
                        ):
                            AuthoredRetainedCargoWrapperContext(
                                _key=authored_wrapper._CREATION_KEY, core=context._core
                            )
                    for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                        for owner in (context, context._core):
                            with self.assertRaises(TypeError):
                                operation(owner)
                self.assertEqual(snapshot(root), before)
            with self.assertRaisesRegex(ValueError, "wrapper-operation-ended"):
                context.require_unchanged()

    def test_reviewed_document_drift_refuses_closing_consumer_owner(self):
        for read_only in (False, True):
            with self.subTest(read_only=read_only), self.fixture() as (_old, reviewed):
                path = reviewed.project.root / "review/policy.json"
                with self.assertRaises(ValueError):
                    with authored_retained_cargo_wrapper_context(
                        reviewed, read_only=read_only
                    ):
                        path.write_bytes(path.read_bytes() + b" ")
                self.assertTrue(path.read_bytes().endswith(b" "))

    def test_actual_retained_source_drift_refuses_and_keeps_changed_source(self):
        for read_only in (False, True):
            with self.subTest(read_only=read_only), self.fixture() as (_old, reviewed):
                with self.assertRaises((ValueError, RuntimeError)):
                    with authored_retained_cargo_wrapper_context(
                        reviewed, read_only=read_only
                    ) as context:
                        path = context.implementation / "app.py"
                        self.assertTrue(path.is_file())
                        path.write_bytes(b"changed original consumer source\n")
                self.assertEqual(
                    path.read_bytes(), b"changed original consumer source\n"
                )

    @contextmanager
    def contained_core(self):
        with tempfile.TemporaryDirectory() as directory:
            with scratch_review_fixture(
                Path(directory).resolve(strict=True),
                _layout=ScaffoldLayout.LEGACY_ROOT_FIXTURE,
            ) as old:
                root = old.project.root
                # Capture real original consumer observations before creating a
                # layout-only fixture. No renewal/migration admission is inferred.
                with retained_cargo_wrapper_context_v2(old) as original:
                    revision, conversion = original.revision, original.conversion
                    source = original.source_authority
                    documents = core._load_retained_documents(old.project)
                helper = declarations.AuthoredRetainedCargoReviewTests("runTest")
                (root / "literate.project.json").unlink()
                configuration = ProjectConfigurationStore(root).create(
                    replace(old.project.definition, framework_directory="litai")
                )
                (root / ".literate").rename(root / "litai/.literate")
                binding = helper.fixture(old)
                reference = helper.write_binding(root, binding)
                reviewed = helper.read(root, reference)
                lifetime = core._WrapperLifetime()
                with (
                    patch.object(
                        core,
                        "validated_project_authority_identity",
                        return_value=revision,
                    ),
                    patch.object(
                        core,
                        "_retained_project_authority_observation",
                        return_value=(source, None),
                    ),
                    patch.object(
                        core,
                        "current_project_component_lock_identities",
                        return_value=(),
                    ),
                ):
                    owner = core._CurrentCargoConsumerWrapper(
                        _key=core._CREATION_KEY,
                        reviewed=reviewed,
                        revision=revision,
                        conversion=conversion,
                        documents=documents,
                        bindings=(),
                        lifetime=lifetime,
                        configuration=configuration,
                    )
                    try:
                        owner.require_unchanged()
                        yield owner, configuration
                    finally:
                        lifetime.active = False

    def test_contained_core_pins_actual_framework_metadata_and_detects_drift(self):
        with self.contained_core() as (owner, _configuration):
            root = owner.reviewed.project.root
            self.assertFalse((root / ".literate").exists())
            metadata = root / "litai/.literate/legacy-wrapper-parity.json"
            self.assertTrue(metadata.is_file())
            owner.require_unchanged()
            metadata.write_bytes(metadata.read_bytes() + b" ")
            with self.assertRaises(ValueError):
                owner.require_unchanged()

    def test_contained_core_refuses_conflicting_root_manifest(self):
        with self.contained_core() as (owner, configuration):
            root = owner.reviewed.project.root
            (root / "literate.project.json").write_bytes(configuration.content)
            with self.assertRaises(ProjectError):
                owner.require_unchanged()
