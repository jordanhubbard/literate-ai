"""Owned local absence/resource tests; no creation or runtime qualification.

Distribution origin and absent Git authority are explicit resource-fixture seams.
"""

from __future__ import annotations

import copy
import hashlib
import os
import unittest
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import project_layout_finite_creations as production
from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters.project_layout_framework_source_proofs import (
    prove_initialized_framework_file,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_json_bytes,
)
from tests.critical import test_project_layout_framework_resources as support


class FiniteFrameworkCreationTests(unittest.TestCase):
    def fixture(self, *, bootstrap=False, root_ignore=None):
        project, observed, origin = support.framework_fixture(self)
        if root_ignore is not None:
            project.write(".gitignore", root_ignore)
        if bootstrap:
            logical = "scripts/bootstrap_litai.py"
            content = resources.initialization._template_text(logical).encode()
            project.write(logical, content)
            project.baseline = replace(
                project.baseline,
                files=tuple(
                    sorted(
                        (
                            *project.baseline.files,
                            ProjectInitializationBaselineFile(
                                logical,
                                len(content),
                                ContentIdentity.parse_uri(
                                    "sha256:" + hashlib.sha256(content).hexdigest()
                                ),
                            ),
                        ),
                        key=lambda row: row.path,
                    )
                ),
            )
            project.write(
                "litai/.literate/initialization-baseline.json",
                canonical_json_bytes(project.baseline.to_dict()) + b"\n",
            )
            bases = UpdateBases(project.root)
            bases.advance("framework", logical, content)
            project.write("litai/.literate/update-bases.json", bases.serialized())
        project.refresh()
        project.inventory["retained_implementation"] = None
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
        owner = resources.observe_original_framework_resources(observed)
        proof = None
        if bootstrap:
            proof = prove_initialized_framework_file(
                project.snapshot,
                project.context,
                logical="scripts/bootstrap_litai.py",
                source_path="scripts/bootstrap_litai.py",
                resources=owner,
                update_bases=project.bases,
                contents=project.contents,
                observations=project.observations,
            )
        return project, owner, proof

    def ignore(self, resources):
        owner = production.observe_original_finite_framework_creation(
            resources, ".gitignore"
        )
        self.addCleanup(production.close_original_finite_framework_creation, owner)
        return owner

    def helper(self, resources, proof):
        return production.observe_original_finite_framework_creation(
            resources,
            production._HELPER,
            bootstrap_proof=proof,
            coordinate_map={
                production._BOOTSTRAP: "litai/" + production._BOOTSTRAP,
                production._HELPER: "litai/" + production._HELPER,
            },
        )

    def test_helper_absence_refuses_oversized_real_sibling_census(self):
        project, resource_owner, proof = self.fixture(bootstrap=True)
        target = project.root / "litai/scripts"
        target.mkdir()
        for index in range(8200):
            (target / f"unrelated-{index}").touch()
        with self.assertRaisesRegex(ProjectLayoutPlanError, "census bound"):
            self.helper(resource_owner, proof)
        self.assertFalse((target / "_bootstrap_processes.py").exists())
        self.assertEqual(sum(1 for _ in target.iterdir()), 8200)

    def test_actual_absence_original_ignore_bytes_and_no_writes(self):
        project, resource_owner, _ = self.fixture()
        owner = self.ignore(resource_owner)
        self.assertEqual(owner.content, production._IGNORE)
        self.assertEqual(owner.destination, "litai/.gitignore")
        production.require_current_finite_framework_creation(owner)
        self.assertFalse((project.root / owner.destination).exists())

    def test_application_root_ignore_remains_unchanged(self):
        original = b"# application private ignore\n"
        project, resource_owner, _ = self.fixture(root_ignore=original)
        self.ignore(resource_owner)
        self.assertEqual((project.root / ".gitignore").read_bytes(), original)

    def test_equal_existing_target_never_grants_overwrite(self):
        project, resource_owner, _ = self.fixture()
        (project.root / "litai/.gitignore").write_bytes(production._IGNORE)
        with self.assertRaises(ProjectLayoutPlanError):
            self.ignore(resource_owner)

    def test_target_created_after_admission_refuses(self):
        project, resource_owner, _ = self.fixture()
        owner = self.ignore(resource_owner)
        (project.root / owner.destination).write_bytes(b"custom\n")
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_current_finite_framework_creation(owner)

    def test_portable_alias_refuses(self):
        project, resource_owner, _ = self.fixture()
        (project.root / "litai/.GitIgnore").write_bytes(b"custom\n")
        with self.assertRaises(ProjectLayoutPlanError):
            self.ignore(resource_owner)

    def test_unknown_template_is_not_general_creation_permission(self):
        _project, resource_owner, _ = self.fixture()
        for logical in ("SKILL.md", "application.py", "../secret", "litai/.gitignore"):
            with (
                self.subTest(logical=logical),
                self.assertRaises(ProjectLayoutPlanError),
            ):
                production.observe_original_finite_framework_creation(
                    resource_owner, logical
                )

    def test_copy_field_replacement_close_and_pid_refuse(self):
        _project, resource_owner, _ = self.fixture()
        owner = self.ignore(resource_owner)
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_current_finite_framework_creation(copy.copy(owner))
        with patch.object(production.os, "getpid", return_value=os.getpid() + 1):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_original_finite_framework_creation(owner)
        original = owner.content
        object.__setattr__(owner, "content", b"forged\n")
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_finite_framework_creation(owner)
        object.__setattr__(owner, "content", original)
        production.close_original_finite_framework_creation(owner)
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_finite_framework_creation(owner)

    def test_real_bootstrap_proof_binds_original_helper_without_creating_it(self):
        project, resource_owner, proof = self.fixture(bootstrap=True)
        owner = self.helper(resource_owner, proof)
        self.addCleanup(production.close_original_finite_framework_creation, owner)
        self.assertEqual(owner.content, resource_owner.files[production._HELPER])
        self.assertFalse((project.root / owner.destination).exists())
        self.assertFalse((project.root / production._HELPER).exists())

    def test_helper_cannot_reinterpret_existing_root_helper_as_new(self):
        project, resource_owner, proof = self.fixture(bootstrap=True)
        project.write(production._HELPER, b"custom\n")
        with self.assertRaises(ProjectLayoutPlanError):
            self.helper(resource_owner, proof)

    def test_helper_requires_original_same_resource_bootstrap_proof(self):
        _project, resource_owner, proof = self.fixture(bootstrap=True)
        for candidate in (None, copy.copy(proof)):
            with self.assertRaises(ProjectLayoutPlanError):
                self.helper(resource_owner, candidate)

    def test_bootstrap_change_expires_helper_creation_owner(self):
        project, resource_owner, proof = self.fixture(bootstrap=True)
        owner = self.helper(resource_owner, proof)
        self.addCleanup(production.close_original_finite_framework_creation, owner)
        project.write(production._BOOTSTRAP, b"# application replacement\n")
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_current_finite_framework_creation(owner)

    def test_class_property_refuses_before_foreign_dispatch(self):
        _project, resource_owner, _ = self.fixture()
        owner = self.ignore(resource_owner)
        calls = []
        with patch.object(
            type(owner), "content", property(lambda _owner: calls.append(True))
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_current_finite_framework_creation(owner)
        self.assertEqual(calls, [])

    def test_symlink_target_stays_unopened(self):
        project, resource_owner, _ = self.fixture()
        (project.root / "litai/.gitignore").symlink_to("/never/open/this")
        with self.assertRaises(ProjectLayoutPlanError):
            self.ignore(resource_owner)

    def test_helper_symlink_ancestor_refuses_without_target_follow(self):
        project, resource_owner, proof = self.fixture(bootstrap=True)
        (project.root / "litai/scripts").symlink_to("/never/open/this")
        with self.assertRaises(ProjectLayoutPlanError):
            self.helper(resource_owner, proof)

    def test_late_original_resource_callback_cannot_hide_target_creation(self):
        project, resource_owner, _ = self.fixture()
        owner = self.ignore(resource_owner)
        calls = []

        def origin():
            calls.append(True)
            if len(calls) == 2:
                (project.root / owner.destination).write_bytes(b"late custom\n")
            return resource_owner.origin

        with patch.object(resources, "_read_current_origin", side_effect=origin):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_current_finite_framework_creation(owner)
        self.assertEqual(len(calls), 2)

    def test_resource_callback_cannot_dispatch_replaced_local_checker(self):
        for phase in ("factory", "first-current", "closing-current"):
            for checker in ("_absence", "_bootstrap_current", "_require"):
                with self.subTest(phase=phase, checker=checker):
                    _project, resource_owner, _ = self.fixture()
                    owner = None if phase == "factory" else self.ignore(resource_owner)
                    original = vars(production)[checker]
                    calls, foreign_calls = [], []

                    def origin(
                        calls=calls,
                        phase=phase,
                        checker=checker,
                        foreign_calls=foreign_calls,
                        resource_owner=resource_owner,
                    ):
                        calls.append(True)
                        expected = 2 if phase == "closing-current" else 1
                        if len(calls) == expected:
                            setattr(
                                production,
                                checker,
                                lambda *_a, **_k: foreign_calls.append(True),
                            )
                        return resource_owner.origin

                    try:
                        with patch.object(
                            resources, "_read_current_origin", side_effect=origin
                        ):
                            with self.assertRaises(ProjectLayoutPlanError):
                                if phase == "factory":
                                    self.ignore(resource_owner)
                                else:
                                    production.require_current_finite_framework_creation(
                                        owner
                                    )
                    finally:
                        setattr(production, checker, original)
                    self.assertEqual(foreign_calls, [])

    def test_logical_string_subclass_is_rejected_before_callbacks(self):
        _project, resource_owner, _ = self.fixture()
        calls = []

        class ForeignLogical(str):
            def __eq__(self, other):
                calls.append("equal")
                return True

            def __radd__(self, other):
                calls.append("add")
                return "application.py"

        with self.assertRaises(ProjectLayoutPlanError):
            production.observe_original_finite_framework_creation(
                resource_owner, ForeignLogical(".gitignore")
            )
        self.assertEqual(calls, [])

    def test_alias_helper_and_finite_constants_are_original(self):
        _project, resource_owner, _ = self.fixture()
        calls = []
        replacements = {
            "_alias": lambda value: calls.append(value),
            "_HELPER": "application.py",
            "_BOOTSTRAP": "SKILL.md",
            "_IGNORE": b"foreign\n",
        }
        for name, value in replacements.items():
            with self.subTest(name=name), patch.object(production, name, value):
                with self.assertRaises(ProjectLayoutPlanError):
                    self.ignore(resource_owner)
        self.assertEqual(calls, [])
