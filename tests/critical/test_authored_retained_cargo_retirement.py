"""Independent consumer retirement under actual original source custody.

Actual pre-adoption app.py is retired before consumer capture. Provider admission
is the explicit closed fixture; no native execution or admission is claimed.
"""

import copy
import pickle
import unittest
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_retirement as authored
from literate_ai.adapters import retained_cargo_admission_v2 as source
from tests.critical import test_authored_retained_cargo_inputs as joins
from tests.support.fixtures_authored_retained_cargo_retirement import (
    authored_retirement_fixture,
)


class AuthoredRetainedCargoRetirementTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        joins.AuthoredRetainedCargoInputsTests.setUpClass()

    def read(self, materialized, path, reference):
        return authored.read_authored_retained_cargo_retirement_authority(
            materialized, retirement_path=path, reviewed_retirement=reference
        )

    def test_actual_original_consumer_file_is_retired_and_owner_expires(self):
        with authored_retirement_fixture(self) as (
            materialized,
            path,
            reference,
            original,
            before,
        ):
            self.assertEqual(before, b"print('retained')\n")
            self.assertFalse(original.exists())
            owner = self.read(materialized, path, reference)
            owner.require_unchanged()
            self.assertIs(owner.materialized, materialized)
            self.assertEqual(
                owner.retirement.retired_roots,
                (
                    original.relative_to(
                        materialized.files.reviewed.project.root
                    ).as_posix(),
                ),
            )
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with (
                    self.subTest(operation=operation.__name__),
                    self.assertRaises(TypeError),
                ):
                    operation(owner)
        with self.assertRaisesRegex(ValueError, "scratch-operation-ended"):
            owner.require_unchanged()

    def test_still_present_original_source_refuses_without_deletion(self):
        with authored_retirement_fixture(self, retire=False) as (
            materialized,
            path,
            reference,
            original,
            before,
        ):
            with self.assertRaisesRegex(ValueError, "expected-absence-changed"):
                self.read(materialized, path, reference)
            self.assertEqual(original.read_bytes(), before)

    def test_unrelated_absent_sentinel_and_descendant_below_original_file_refuse(self):
        for suffix in ("invented-absent", "app.py/invented"):

            def roots(reviewed, suffix=suffix):
                return (reviewed.plan.common.workspace_root + "/" + suffix,)

            with self.subTest(suffix=suffix):
                with authored_retirement_fixture(self, roots=roots) as (
                    materialized,
                    path,
                    reference,
                    _original,
                    _before,
                ):
                    with self.assertRaisesRegex(ValueError, "outside-original-scope"):
                        self.read(materialized, path, reference)

    def test_manifest_and_package_boundaries_cannot_be_declared_retired(self):
        for kind in ("manifest", "package", "metadata", "locks"):

            def roots(reviewed, kind=kind):
                if kind in ("metadata", "locks"):
                    name = ".literate" if kind == "metadata" else ".litai-locks"
                    return (
                        reviewed.project.context.framework_path(name)
                        .relative_to(reviewed.project.root)
                        .as_posix(),
                    )
                return (
                    (reviewed.plan.common.workspace_root + "/Cargo.toml")
                    if kind == "manifest"
                    else reviewed.binding.destinations[0][1],
                )

            with self.subTest(kind=kind):
                with authored_retirement_fixture(self, roots=roots) as (
                    materialized,
                    path,
                    reference,
                    _original,
                    _before,
                ):
                    with self.assertRaisesRegex(ValueError, "retirement-overlap"):
                        self.read(materialized, path, reference)

    def test_independent_reference_and_cross_origin_gate_precede_admission(self):
        with authored_retirement_fixture(self) as (
            materialized,
            path,
            reference,
            _original,
            _before,
        ):
            with self.assertRaisesRegex(TypeError, "v2-materialization-required"):
                source.read_retained_cargo_retirement_authority_v2(
                    materialized, retirement_path=path, reviewed_retirement=reference
                )
            root = materialized.files.reviewed.project.root
            (root / path).write_bytes((root / path).read_bytes() + b" ")
            with self.assertRaises(ValueError):
                self.read(materialized, path, reference)
            self.assertTrue((root / path).read_bytes().endswith(b" "))

    def test_final_callback_reappearance_refuses_and_preserves_changed_source(self):
        refused = closing_refused = False
        preserved = None
        try:
            with authored_retirement_fixture(self) as (
                materialized,
                path,
                reference,
                original,
                _before,
            ):
                owner = self.read(materialized, path, reference)
                guard = type(materialized).require_unchanged
                calls = 0

                def changed(candidate):
                    nonlocal calls
                    guard(candidate)
                    if candidate is materialized:
                        calls += 1
                        if calls == 2:
                            original.write_bytes(
                                b"preserve late original-source reappearance"
                            )

                with patch.object(type(materialized), "require_unchanged", changed):
                    try:
                        owner.require_unchanged()
                    except ValueError:
                        refused = True
                preserved = original.read_bytes()
        except ValueError:
            closing_refused = True
        self.assertTrue(refused)
        self.assertTrue(closing_refused)
        self.assertEqual(preserved, b"preserve late original-source reappearance")

    def test_membership_matching_requires_leaf_or_ancestor_not_string_prefix(self):
        paths = ("alpha-other", "alpha/file.rs", "beta.rs")
        self.assertTrue(authored._belongs_to_original_scope("alpha", paths))
        self.assertTrue(authored._belongs_to_original_scope("beta.rs", paths))
        self.assertFalse(authored._belongs_to_original_scope("beta.rs/child", paths))
        self.assertFalse(authored._belongs_to_original_scope("alph", paths))
