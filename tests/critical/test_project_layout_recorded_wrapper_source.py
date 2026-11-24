"""Actual local read-owner custody, with historical execution DATA modeled.

No conversion/harness/native execution or native success claim. The existing
resource fixture explicitly models current distribution-origin lookup. Typed
retained reports and initialization preimages here are source-control fixtures,
never portable claims capable of restoring a live owner.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import unittest
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import harness_inventory as renderer
from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters import project_layout_recorded_wrapper_source as production
from literate_ai.adapters import project_layout_retained_source_observation as retained
from literate_ai.adapters.harness_tree import (
    SOURCE_SCOPE_SCHEMA,
    _identity,
    observe_retained_tree,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from literate_ai.adapters.retained_harness_receipts import (
    retained_harness_receipt_policy,
)
from literate_ai.contracts import (
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_json_bytes,
)
from literate_ai.contracts.operator_adoption import (
    ConversionAuthorityStage,
    ConversionAuthorityState,
)
from literate_ai.projects import serialize_project_configuration
from tests.critical import test_project_layout_framework_resources as support


def ci(content):
    return ContentIdentity.parse_uri("sha256:" + hashlib.sha256(content).hexdigest())


class RecordedWrapperSourceTests(unittest.TestCase):
    def fixture(self, *, edited=None, missing_baseline=None, historical=False):
        project, _observation, origin = support.framework_fixture(self)
        implementation = "components/legacy-project-wrapper/implementation"
        project.write(implementation + "/main.py", b"# source never executed\n")
        source_root = project.root / implementation
        scope = {
            "schema": SOURCE_SCOPE_SCHEMA,
            "policy": "filesystem-pruned@1",
            "paths": ["main.py"],
            "paths_identity": _identity(["main.py"]),
            "excluded_roots": [],
            "excluded": [],
        }
        source = observe_retained_tree(source_root, scope)["source_tree"]
        commands = {
            name: {"command": "make " + name, "evidence": "historical-fixture"}
            for name in ("build", "test", "package")
        }
        inventory = {
            "schema": renderer.HARNESS_INVENTORY_SCHEMA,
            "commands": commands,
            "stages": [
                {"id": name, "cwd": ".", **command}
                for name, command in commands.items()
            ],
            "source_scope": scope,
        }
        phases = [
            {"phase": name, "exit_code": 0, "timed_out": False, "source_tree": source}
            for name in commands
        ]
        baseline = {
            "schema": renderer.HARNESS_BASELINE_SCHEMA,
            "state": "passed",
            "phase_count": len(phases),
            "phases": phases,
            "source_scope": scope,
            "legacy_source_tree_before": source,
            "legacy_source_tree_after": source,
        }
        parity = {
            "schema": renderer.HARNESS_PARITY_SCHEMA,
            "state": "passed",
            "phase_count": len(phases),
            "phases": [
                {**row, "parity": True, "baseline_source_tree": source}
                for row in phases
            ],
        }
        lift = {
            "schema": "literate-ai/legacy-lift-shift@1",
            "state": "passed",
            "implementation_directory": implementation,
            "phase_11_parity_identity": ci(
                json.dumps(parity, sort_keys=True, separators=(",", ":")).encode()
            ).uri,
            "phase_12_parity": parity,
        }
        project.definition = replace(
            project.definition,
            test_receipt_policy=retained_harness_receipt_policy(inventory),
        )
        project.write(
            project.manifest, serialize_project_configuration(project.definition)
        )
        entries = {
            name: content.encode()
            for name, content in renderer.legacy_shim_authority(
                inventory, baseline
            ).items()
        }
        entries["litai.harness.mk"] = renderer.render_harness_wrapper(
            inventory, legacy_directory=implementation
        ).encode()
        if historical:
            # Model a historical producer newline convention. Exact baseline
            # equality does not make it output of the available current renderer.
            entries["routing/legacy-adoption.json"] += b"\n"
        for path, content in entries.items():
            project.write(path, content)
        files = {row.path: row for row in project.baseline.files}
        files.update(
            {
                name: ProjectInitializationBaselineFile(name, len(content), ci(content))
                for name, content in entries.items()
            }
        )
        if missing_baseline is not None:
            files.pop(missing_baseline)
        project.baseline = replace(
            project.baseline,
            files=tuple(sorted(files.values(), key=lambda row: row.path)),
        )
        project.write(
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(project.baseline.to_dict()) + b"\n",
        )
        if edited is not None:
            project.write(edited, entries[edited] + b"\n# custom\n")
        conversion = ConversionAuthorityState(
            project.definition.project_id,
            ConversionAuthorityStage.WRAPPED,
            (ContentIdentity.parse_uri("sha256:" + "d" * 64),),
        )
        records = {
            "harness-inventory.json": inventory,
            "legacy-harness-baseline.json": baseline,
            "legacy-wrapper-parity.json": parity,
            "legacy-lift-shift.json": lift,
            "conversion-authority.json": conversion.to_dict(),
        }
        for name, value in records.items():
            project.write(
                "litai/.literate/" + name, canonical_json_bytes(value) + b"\n"
            )
        project.refresh()
        project.inventory["retained_implementation"] = implementation
        project.rehash()
        observation = ProjectLayoutObservation(
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
        resource_owner = resources.observe_original_framework_resources(observation)
        source = retained.observe_original_bounded_retained_source(
            observation, resource_owner
        )
        self.addCleanup(retained.close_original_bounded_retained_source, source)
        return project, resource_owner, source

    def admit(self, project, resource_owner, source):
        owner = production.observe_original_recorded_wrapper_source(
            project.snapshot,
            project.context,
            resources=resource_owner,
            retained_source=source,
        )
        self.addCleanup(production.close_original_recorded_wrapper_source, owner)
        return owner

    def test_actual_seven_native_preimages_and_noop_projection_no_writes(self):
        project, resources, source = self.fixture()
        before = dict(source.records)
        owner = self.admit(project, resources, source)
        self.assertIs(owner.retained_source, source)
        self.assertIs(owner.resources, resources)
        self.assertEqual(len(owner.projection.entries), 7)
        self.assertEqual(
            owner.projection.before_definition_bytes,
            owner.projection.prospective_definition_bytes,
        )
        for entry in owner.projection.entries:
            self.assertEqual(entry.original_coordinate, entry.prospective_coordinate)
            self.assertEqual(entry.original_bytes, entry.prospective_bytes)
        production.require_current_recorded_wrapper_source(owner)
        self.assertEqual(dict(source.records), before)

    def test_close_does_not_close_borrowed_owners(self):
        project, resource_owner, source = self.fixture()
        owner = self.admit(project, resource_owner, source)
        production.close_original_recorded_wrapper_source(owner)
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_original_recorded_wrapper_source(owner)
        retained.require_current_bounded_retained_source(source)
        resources.require_current_framework_resources(resource_owner)

    def test_copied_decoded_or_wrong_process_owners_cannot_restore_origin(self):
        project, resources, source = self.fixture()
        owner = self.admit(project, resources, source)
        for value in (copy.copy(owner), object()):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_original_recorded_wrapper_source(value)
        with patch.object(production.os, "getpid", return_value=os.getpid() + 1):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_original_recorded_wrapper_source(owner)

    def test_genuine_borrowed_owner_close_expires_wrapper_owner(self):
        project, resources, source = self.fixture()
        owner = self.admit(project, resources, source)
        retained.close_original_bounded_retained_source(source)
        with self.assertRaises(ProjectLayoutPlanError):
            production.require_current_recorded_wrapper_source(owner)

    def test_same_snapshot_context_and_resources_are_required(self):
        project, resources, source = self.fixture()
        with self.assertRaises(ProjectLayoutPlanError):
            production.observe_original_recorded_wrapper_source(
                replace(project.snapshot),
                project.context,
                resources=resources,
                retained_source=source,
            )

    def test_matching_renderer_without_all_seven_original_baseline_entries_refuses(
        self,
    ):
        project, resources, source = self.fixture(
            missing_baseline="routing/legacy-adoption.json"
        )
        with self.assertRaisesRegex(
            ProjectLayoutPlanError, "original update owner required"
        ):
            self.admit(project, resources, source)

    def test_custom_beforebytes_are_not_normalized_to_current_renderer(self):
        project, resources, source = self.fixture(edited="routing/legacy-adoption.json")
        with self.assertRaises(ProjectLayoutPlanError):
            self.admit(project, resources, source)

    def test_changed_source_or_producer_native_facts_refuse(self):
        for what in ("source", "entry", "producer"):
            with self.subTest(what=what):
                project, resources, source = self.fixture()
                owner = self.admit(project, resources, source)
                path = (
                    source.root / "main.py"
                    if what == "source"
                    else project.root
                    / (
                        "routing/legacy-adoption.json"
                        if what == "entry"
                        else "litai/.literate/legacy-harness-baseline.json"
                    )
                )
                path.write_bytes(path.read_bytes() + b"\nchanged\n")
                with self.assertRaises(ProjectLayoutPlanError):
                    production.require_current_recorded_wrapper_source(owner)

    def test_field_and_projection_replacement_refuse_before_borrowed_callbacks(self):
        project, resources, source = self.fixture()
        owner = self.admit(project, resources, source)
        original = owner.projection.input_identity
        object.__setattr__(owner.projection, "input_identity", "sha256:" + "f" * 64)
        try:
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_current_recorded_wrapper_source(owner)
        finally:
            object.__setattr__(owner.projection, "input_identity", original)

    def test_class_descriptor_refuses_before_foreign_getter(self):
        project, resources, source = self.fixture()
        owner = self.admit(project, resources, source)
        calls = []
        with patch.object(
            type(owner), "projection", property(lambda _self: calls.append(True))
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_current_recorded_wrapper_source(owner)
        self.assertEqual(calls, [])

    def test_origin_callback_cannot_substitute_next_projector_or_native_closer(self):
        for module, name in (
            (production.projector, "project_recorded_legacy_wrapper_authority"),
            (production, "_close_bound_source_nodes"),
            (production, "require_current_bounded_retained_source"),
        ):
            with self.subTest(name=name):
                project, resource_owner, source = self.fixture()
                owner = self.admit(project, resource_owner, source)
                original = getattr(module, name)
                calls = []

                def foreign(*_args, calls=calls, **_kwargs):
                    calls.append(True)

                def origin(
                    module=module,
                    name=name,
                    foreign=foreign,
                    resource_owner=resource_owner,
                ):
                    setattr(module, name, foreign)
                    return resource_owner.origin

                try:
                    with patch.object(resources, "_read_current_origin", origin):
                        with self.assertRaises(ProjectLayoutPlanError):
                            production.require_current_recorded_wrapper_source(owner)
                finally:
                    setattr(module, name, original)
                self.assertEqual(calls, [])

    def test_factory_callback_cannot_substitute_public_factory_or_cleanup(self):
        for name in (
            "observe_original_recorded_wrapper_source",
            "close_original_recorded_wrapper_source",
        ):
            with self.subTest(name=name):
                project, resource_owner, source = self.fixture()
                original = getattr(production, name)
                calls = []

                def origin(name=name, calls=calls, resource_owner=resource_owner):
                    setattr(
                        production, name, lambda *_args, **_kwargs: calls.append(True)
                    )
                    return resource_owner.origin

                try:
                    with patch.object(resources, "_read_current_origin", origin):
                        with self.assertRaises(ProjectLayoutPlanError):
                            self.admit(project, resource_owner, source)
                finally:
                    setattr(production, name, original)
                self.assertEqual(calls, [])
                retained.require_original_bounded_retained_source(source)

    def test_callback_close_refuses_before_next_borrowed_owner_callback(self):
        project, resource_owner, source = self.fixture()
        owner = self.admit(project, resource_owner, source)
        calls = []

        def origin():
            calls.append(True)
            production.close_original_recorded_wrapper_source(owner)
            return resource_owner.origin

        with patch.object(resources, "_read_current_origin", origin):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_current_recorded_wrapper_source(owner)
        self.assertEqual(calls, [True])
        retained.require_original_bounded_retained_source(source)

    def test_matching_historical_baseline_is_not_reinterpreted_as_current_renderer(
        self,
    ):
        project, resources, source = self.fixture(historical=True)
        with self.assertRaisesRegex(ValueError, "differ from original producer"):
            self.admit(project, resources, source)
        retained.require_original_bounded_retained_source(source)

    def test_last_borrowed_callback_source_mutation_cannot_escape_native_closure(self):
        project, resource_owner, source = self.fixture()
        owner = self.admit(project, resource_owner, source)
        calls = []

        def origin():
            calls.append(True)
            if len(calls) == 6:
                (source.root / "main.py").write_bytes(b"changed at final callback\n")
            return resource_owner.origin

        with patch.object(resources, "_read_current_origin", origin):
            with self.assertRaises(ProjectLayoutPlanError):
                production.require_current_recorded_wrapper_source(owner)
        self.assertEqual(len(calls), 6)

    def test_primary_callback_baseexception_is_preserved(self):
        project, resource_owner, source = self.fixture()
        owner = self.admit(project, resource_owner, source)

        class OriginalFailure(BaseException):
            pass

        primary = OriginalFailure("original callback")
        original = production.close_original_recorded_wrapper_source

        def origin():
            production.close_original_recorded_wrapper_source = lambda *_args: None
            raise primary

        try:
            with patch.object(resources, "_read_current_origin", origin):
                with self.assertRaises(OriginalFailure) as caught:
                    production.require_current_recorded_wrapper_source(owner)
            self.assertIs(caught.exception, primary)
        finally:
            production.close_original_recorded_wrapper_source = original
