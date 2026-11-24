"""Owned local source + actual read owners; retained metadata explicitly modeled.

Installed-origin lookup is the established resource-fixture seam. No baseline,
native process, executable, source move, receipt or release success is fabricated.
"""

from __future__ import annotations

import copy
import os
import unittest
from unittest.mock import patch

from literate_ai.adapters import (
    project_layout_framework_observation as source_observation,
)
from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters import (
    project_layout_retained_source_observation as production,
)
from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.adapters.harness_inventory import HARNESS_INVENTORY_SCHEMA
from literate_ai.adapters.harness_tree import (
    SOURCE_SCOPE_SCHEMA,
    _identity,
    observe_retained_source_bytes,
    observe_retained_tree,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from literate_ai.contracts import canonical_json_bytes
from tests.critical import test_project_layout_framework_resources as support


class BoundedRetainedSourceTests(unittest.TestCase):
    def fixture(self):
        project, _observed, origin = support.framework_fixture(self)
        implementation = "components/legacy-project-wrapper/implementation"
        source_root = project.root / implementation
        payload = b"# original never executed\r\n" + str(source_root).encode() + b"\r\n"
        project.write(implementation + "/main.py", payload)
        project.write(
            "litai/components/legacy-project-wrapper/component.md",
            b"# Original legacy wrapper role fixture; no execution admission\n",
        )
        scope = {
            "schema": SOURCE_SCOPE_SCHEMA,
            "policy": "filesystem-pruned@1",
            "paths": ["main.py"],
            "paths_identity": _identity(["main.py"]),
            "excluded_roots": [],
            "excluded": [],
        }
        inventory = {
            "schema": HARNESS_INVENTORY_SCHEMA,
            "findings": [],
            "commands": {},
            "stages": [],
            "ci": {},
            "source_scope": scope,
        }
        project.write(
            "litai/.literate/legacy-lift-shift.json",
            canonical_json_bytes({"implementation_directory": implementation}) + b"\n",
        )
        project.write(
            "litai/.literate/harness-inventory.json",
            canonical_json_bytes(inventory) + b"\n",
        )
        project.refresh()
        project.inventory["retained_implementation"] = implementation
        project.rehash()
        observed = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        self.enterContext(
            patch.object(resources, "_read_current_origin", return_value=origin)
        )
        resource_owner = resources.observe_original_framework_resources(observed)
        owner = production.observe_original_bounded_retained_source(
            observed, resource_owner
        )
        self.addCleanup(production.close_original_bounded_retained_source, owner)
        return project, owner

    def test_actual_raw_and_normalized_source_protocol_match_original_observer(self):
        _project, owner = self.fixture()
        raw = observe_retained_source_bytes(owner.root, owner.scope)
        source_tree = observe_retained_tree(owner.root, owner.scope)["source_tree"]
        self.assertEqual(owner.raw, raw)
        self.assertEqual(
            production.bounded_retained_source_tree_for(
                owner, owner.root, owner.inventory
            ),
            source_tree,
        )
        with (
            patch.object(
                readmission,
                "capture_retained_source_scope",
                side_effect=AssertionError("legacy fallback"),
            ),
            patch.object(
                readmission,
                "observe_retained_source_bytes",
                side_effect=AssertionError("legacy source read"),
            ),
            patch.object(
                readmission,
                "observe_retained_tree",
                side_effect=AssertionError("legacy tree read"),
            ),
            patch.object(
                readmission,
                "_source_native_inputs",
                side_effect=AssertionError("legacy native inputs"),
            ),
            readmission._readmission_source_inputs(
                owner.root,
                owner.inventory,
                expected_tree=source_tree,
                _bounded_source=owner,
            ) as inputs,
        ):
            self.assertIs(inputs.scope, owner.scope)
            self.assertIs(inputs.raw, owner.raw)
            inputs.require_for(owner.root, owner.inventory)

    def test_absent_option_keeps_original_source_path(self):
        _project, owner = self.fixture()
        with patch.object(
            readmission, "capture_retained_source_scope", return_value=owner.scope
        ) as legacy:
            with readmission._readmission_source_inputs(
                owner.root, owner.inventory
            ) as inputs:
                self.assertIsNone(readmission._bounded_readmission(inputs))
                self.assertEqual(inputs.raw, owner.raw)
        self.assertGreater(legacy.call_count, 0)

    def test_changed_source_refuses_with_original_readmission_error_and_cause(self):
        _project, owner = self.fixture()
        with self.assertRaises(readmission.RetainedHarnessReadmissionError):
            with readmission._readmission_source_inputs(
                owner.root, owner.inventory, _bounded_source=owner
            ) as inputs:
                original = (owner.root / "main.py").read_bytes()
                (owner.root / "main.py").write_bytes(original + b"changed\n")
                with self.assertRaises(
                    readmission.RetainedHarnessReadmissionError
                ) as refused:
                    inputs.require_current()
                self.assertIsInstance(
                    refused.exception.__cause__, ProjectLayoutPlanError
                )
                # Restore exact bytes does not adopt a new inode/stamp baseline.
                (owner.root / "main.py").write_bytes(original)
                with self.assertRaises(ProjectLayoutPlanError):
                    production.require_current_bounded_retained_source(owner)

    def test_exact_original_inventory_and_root_pointers_required(self):
        _project, owner = self.fixture()
        with self.assertRaises(readmission.RetainedHarnessReadmissionError):
            with readmission._readmission_source_inputs(
                owner.root, copy.deepcopy(owner.inventory), _bounded_source=owner
            ):
                self.fail("foreign inventory adopted")

    def test_closed_parent_source_owner_cannot_be_reopened_from_saved_data(self):
        _project, owner = self.fixture()
        production.close_original_bounded_retained_source(owner)
        with self.assertRaises(readmission.RetainedHarnessReadmissionError):
            with readmission._readmission_source_inputs(
                owner.root, owner.inventory, _bounded_source=owner
            ):
                self.fail("closed owner reopened")
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_bounded_retained_source(copy.copy(owner))

    def test_copied_or_forged_scope_and_changed_callback_never_dispatch(self):
        _project, owner = self.fixture()
        forged = object.__new__(type(owner))
        for name in production._FIELDS:
            object.__setattr__(forged, name, object.__getattribute__(owner, name))
        for foreign in (copy.copy(owner), forged):
            with self.assertRaises(ProjectLayoutPlanError) as refusal:
                production.require_current_bounded_retained_source(foreign)
            self.assertIn("factory", str(refusal.exception))
        calls = []
        object.__setattr__(owner, "_guard", lambda: calls.append(True))
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_current_bounded_retained_source(owner)
        self.assertEqual(calls, [])

    def test_original_process_identity_cannot_be_recreated_from_saved_scope(self):
        _project, owner = self.fixture()
        original_pid = os.getpid()
        with patch.object(production.os, "getpid", return_value=original_pid + 1):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_original_bounded_retained_source(owner)

    def test_borrowed_lifetime_cannot_be_reset_and_copies_are_not_admitted(self):
        _project, owner = self.fixture()
        with readmission._readmission_source_inputs(
            owner.root, owner.inventory, _bounded_source=owner
        ) as inputs:
            copied = copy.copy(inputs)
            with self.assertRaises(readmission.RetainedHarnessReadmissionError):
                readmission._current_readmission(copied)
        inputs.closed = False
        with self.assertRaises(readmission.RetainedHarnessReadmissionError):
            readmission._current_readmission(inputs)

    def test_foreign_class_descriptor_before_first_borrow_never_runs(self):
        _project, owner = self.fixture()
        calls = []

        class Foreign:
            def __get__(self, *_args):
                calls.append(True)
                return lambda: None

        with patch.object(
            readmission._ReadmissionSourceInputs, "require_current", Foreign()
        ):
            with self.assertRaises(readmission.RetainedHarnessReadmissionError):
                with readmission._readmission_source_inputs(
                    owner.root, owner.inventory, _bounded_source=owner
                ):
                    self.fail("foreign getter adopted")
        self.assertEqual(calls, [])

    def test_foreign_class_descriptor_during_body_never_runs_on_close(self):
        _project, owner = self.fixture()
        calls = []

        class Foreign:
            def __get__(self, *_args):
                calls.append(True)
                return lambda: None

        with self.assertRaises(readmission.RetainedHarnessReadmissionError):
            with readmission._readmission_source_inputs(
                owner.root, owner.inventory, _bounded_source=owner
            ):
                patcher = patch.object(
                    readmission._ReadmissionSourceInputs, "require_current", Foreign()
                )
                patcher.start()
                self.addCleanup(patcher.stop)
        self.assertEqual(calls, [])

    def test_primary_baseexception_survives_closing_source_refusal(self):
        _project, owner = self.fixture()

        class OriginalFailure(BaseException):
            @property
            def __notes__(self):
                raise KeyboardInterrupt("hostile annotation")

        original = OriginalFailure("original lifecycle failure")
        with self.assertRaises(OriginalFailure) as caught:
            with readmission._readmission_source_inputs(
                owner.root, owner.inventory, _bounded_source=owner
            ):
                (owner.root / "main.py").write_bytes(b"changed\n")
                raise original
        self.assertIs(caught.exception, original)

    def test_changed_original_scope_record_is_not_readopted(self):
        project, owner = self.fixture()
        path = "litai/.literate/harness-inventory.json"
        project.write(path, project.contents[path] + b" ")
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_current_bounded_retained_source(owner)

    def test_source_root_replacement_and_new_undeclared_file_are_terminal(self):
        for mutation in ("replace", "extra"):
            with self.subTest(mutation=mutation):
                _project, owner = self.fixture()
                if mutation == "replace":
                    owner.root.rename(owner.root.with_name("original-retained"))
                    owner.root.mkdir()
                    (owner.root / "main.py").write_bytes(b"replacement\n")
                else:
                    (owner.root / "undeclared.py").write_bytes(b"not adopted\n")
                with self.assertRaises(ProjectLayoutPlanError):
                    production.require_current_bounded_retained_source(owner)

    def test_even_declared_private_source_stays_unopened_before_native_probe(self):
        _project, owner = self.fixture()
        (owner.root / ".env.local").write_bytes(b"public dummy fixture; never a key\n")
        native = owner.root.lstat()
        original = source_observation._named

        def named(cursor, name):
            if name == ".env.local":
                raise AssertionError("private fixture native probe")
            return original(cursor, name)

        with patch.object(source_observation, "_named", named):
            _nodes, contents, held = source_observation._capture_bound_source_scope(
                owner.root,
                (native.st_dev, native.st_ino, native.st_mode),
                required_paths=(".env.local", "main.py"),
            )
        self.assertNotIn(".env.local", contents)
        self.assertTrue(
            any(row["path"] == ".env.local" and row["source"] for row in held)
        )

    def test_last_original_resource_callback_cannot_change_source_or_producer(self):
        for subject in ("source", "producer"):
            with self.subTest(subject=subject):
                project, owner = self.fixture()
                calls = []

                def origin(calls=calls, subject=subject, owner=owner, project=project):
                    calls.append(True)
                    if len(calls) == 2:
                        if subject == "source":
                            (owner.root / "main.py").write_bytes(b"late mutation\n")
                        else:
                            path = "litai/.literate/harness-inventory.json"
                            project.write(path, project.contents[path] + b" ")
                    return owner.resources.origin

                with patch.object(resources, "_read_current_origin", origin):
                    with self.assertRaises(ProjectLayoutPlanError):
                        production.require_current_bounded_retained_source(owner)
                self.assertEqual(len(calls), 2)
