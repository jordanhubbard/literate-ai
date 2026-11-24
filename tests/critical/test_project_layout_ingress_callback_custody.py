"""Actual resource-origin callback mutations; no native/effect qualification."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from literate_ai.adapters import project_layout_framework_ingress as production
from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters import project_layout_retained_source_observation as retained
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from tests.critical import test_project_layout_bounded_retained_source as converted
from tests.critical import test_project_layout_framework_ingress as support
from tests.critical import test_project_layout_framework_source_proofs as proofs


class IngressCallbackCustodyTests(unittest.TestCase):
    def observed(self):
        helper = support.FrameworkIngressTests("runTest")
        self.addCleanup(helper.doCleanups)
        return helper.fixture()

    def unobserved(self):
        helper = proofs.InitializedFrameworkProofTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, owner = helper.fixture(content=b"# Original framework authority\n")
        observation = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        return owner, observation

    def test_first_and_final_current_callbacks_refuse_foreign_capture_dispatch(self):
        for ordinal in (1, 2):
            for name in (
                "_capture",
                "capture_framework_source_scope",
                "_producer_namespace",
                "_close_bound_source_nodes",
                "_git_pair",
            ):
                with self.subTest(ordinal=ordinal, name=name):
                    _project, owner, _public, selection = self.observed()
                    calls, foreign = [], []

                    def substituted(*_args, foreign=foreign, **_kwargs):
                        foreign.append(True)

                    original = getattr(production, name)

                    def origin(
                        calls=calls,
                        ordinal=ordinal,
                        name=name,
                        owner=owner,
                        substituted=substituted,
                    ):
                        calls.append(True)
                        if len(calls) == ordinal:
                            setattr(production, name, substituted)
                        return owner.origin

                    try:
                        with patch.object(resources, "_read_current_origin", origin):
                            with self.assertRaises(ProjectLayoutPlanError):
                                production.require_current_observed_framework_selection(
                                    selection
                                )
                    finally:
                        setattr(production, name, original)
                    self.assertEqual(len(calls), ordinal)
                    self.assertEqual(foreign, [])

    def test_factory_callback_refuses_before_any_next_local_getter_or_capture(self):
        for name in (
            "_capture",
            "_metadata_paths",
            "_class_current",
            "_require",
            "_data",
            "_plain",
            "_check",
            "_invoke",
        ):
            with self.subTest(name=name):
                owner, observation = self.unobserved()
                foreign = []

                def substituted(*_args, foreign=foreign, **_kwargs):
                    foreign.append(True)

                original = getattr(production, name)

                def origin(name=name, owner=owner, substituted=substituted):
                    setattr(production, name, substituted)
                    return owner.origin

                try:
                    with patch.object(resources, "_read_current_origin", origin):
                        with self.assertRaises(ProjectLayoutPlanError):
                            production.observe_existing_framework_authority(
                                observation, resources=owner
                            )
                finally:
                    setattr(production, name, original)
                self.assertEqual(foreign, [])

    def test_checker_self_substitution_does_not_loosen_admitted_currentness(self):
        for name in (
            "_class_current",
            "_require",
            "_data",
            "_plain",
            "_check",
            "_invoke",
            "_cleanup",
        ):
            with self.subTest(name=name):
                _project, owner, _public, selection = self.observed()
                foreign = []

                def substituted(*_args, foreign=foreign, **_kwargs):
                    foreign.append(True)

                original = getattr(production, name)

                def origin(name=name, owner=owner, substituted=substituted):
                    setattr(production, name, substituted)
                    return owner.origin

                try:
                    with patch.object(resources, "_read_current_origin", origin):
                        with self.assertRaises(ProjectLayoutPlanError):
                            production.require_current_observed_framework_selection(
                                selection
                            )
                finally:
                    setattr(production, name, original)
                self.assertEqual(foreign, [])

    def test_mutated_tables_cannot_rebaseline_original_checker(self):
        for name in (
            "_ORIGINAL_CALLS",
            "_ORIGINAL_CONSTANTS",
            "_CLASSES",
            "_PRODUCERS",
            "_ACTIONS",
            "_SOURCE_FIELDS",
            "_OWNER_FIELDS",
        ):
            with self.subTest(name=name):
                _project, owner, _public, selection = self.observed()
                original = getattr(production, name)

                def origin(name=name, owner=owner):
                    setattr(production, name, ())
                    return owner.origin

                try:
                    with patch.object(resources, "_read_current_origin", origin):
                        with self.assertRaises(ProjectLayoutPlanError):
                            production.require_current_observed_framework_selection(
                                selection
                            )
                finally:
                    setattr(production, name, original)

    def test_actual_retained_current_callbacks_refuse_before_ingress_dispatch(self):
        for ordinal in (2, 3):
            with self.subTest(ordinal=ordinal):
                helper = converted.BoundedRetainedSourceTests("runTest")
                self.addCleanup(helper.doCleanups)
                project, old = helper.fixture()
                observation = ProjectLayoutObservation(
                    project.snapshot,
                    project.context,
                    project.inventory,
                    project.observations,
                    project.contents,
                    project.bases,
                )
                _public, selection = production.observe_existing_framework_authority(
                    observation,
                    resources=old.resources,
                )
                original_close = production.close_observed_framework_selection
                self.addCleanup(original_close, selection)
                calls, foreign = [], []
                original_capture = production._capture

                def origin(calls=calls, foreign=foreign, ordinal=ordinal, old=old):
                    calls.append(True)
                    if len(calls) == ordinal:
                        production._capture = lambda *_args, **_kwargs: foreign.append(
                            True
                        )
                    return old.resources.origin

                try:
                    with patch.object(resources, "_read_current_origin", origin):
                        with self.assertRaises(ProjectLayoutPlanError):
                            production.require_current_observed_framework_selection(
                                selection
                            )
                finally:
                    production._capture = original_capture
                self.assertEqual(len(calls), 3)
                self.assertEqual(foreign, [])

    def test_primary_baseexception_survives_checker_and_annotation_refusal(self):
        _project, owner, _public, selection = self.observed()
        foreign = []

        class OriginalFailure(BaseException):
            @property
            def __notes__(self):
                raise KeyboardInterrupt("annotation refusal")

        primary = OriginalFailure("original callback failure")
        original = production._check

        def origin():
            production._check = lambda: foreign.append(True)
            raise primary

        try:
            with patch.object(resources, "_read_current_origin", origin):
                with self.assertRaises(OriginalFailure) as caught:
                    production.require_current_observed_framework_selection(selection)
                self.assertIs(caught.exception, primary)
        finally:
            production._check = original
        self.assertEqual(foreign, [])

    def test_acquisition_cleanup_uses_original_closer_after_callback_substitution(self):
        helper = converted.BoundedRetainedSourceTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, old = helper.fixture()
        observation = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        acquired, foreign = [], []
        original_register = retained._register
        original_close = production.close_original_bounded_retained_source

        def register(owner, values):
            original_register(owner, values)
            acquired.append(owner)

        def origin():
            if acquired:
                production.close_original_bounded_retained_source = lambda *_args: (
                    foreign.append(True)
                )
            return old.resources.origin

        try:
            with (
                patch.object(retained, "_register", register),
                patch.object(resources, "_read_current_origin", origin),
            ):
                with self.assertRaises(ProjectLayoutPlanError):
                    production.observe_existing_framework_authority(
                        observation, resources=old.resources
                    )
        finally:
            production.close_original_bounded_retained_source = original_close
        self.assertEqual(len(acquired), 1)
        self.assertEqual(foreign, [])
        with self.assertRaises(ProjectLayoutPlanError):
            retained.require_original_bounded_retained_source(acquired[0])
