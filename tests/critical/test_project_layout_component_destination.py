"""Actual normal preparation/check/update and temp journal; transition is modeled.

UNRUN. No public-transition, initialized/inherited admission or native-platform
qualification claim. No synthetic CatalogImport or decoded authority is created.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_component_destination as destination
from literate_ai.adapters import project_layout_continuation as writer
from literate_ai.adapters.component_lock_planning import (
    ComponentLockPlanningError,
    FilesystemComponentLockPlanner,
)
from literate_ai.adapters.project_layout_lease import current_layout_lease
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutPlanError,
    _capture,
)
from literate_ai.contracts import (
    CatalogImportsFile,
    RepositoryLineage,
    RepositoryParentSelection,
    RepositorySourceLock,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.projects import (
    ProjectConfigurationStore,
    serialize_project_configuration,
)
from tests.critical import test_project_layout_continuation as fixtures
from tests.support.fixtures_test_component_lock_planning import (
    _fixture,
    _flavor_variant,
)
from tests.support.fixtures_test_project_configuration import _definition


class _LocalTypedResolver:
    """Typed local test facts only; not source acquisition/qualification."""

    def __init__(self):
        self.effect = None
        self.calls = 0
        self.locks = {}

    def lock(self, dependency):
        self.calls += 1
        if dependency.identity not in self.locks:
            self.locks[dependency.identity] = RepositorySourceLock(
                dependency,
                "a" * 40,
                canonical_identity({"modeled": "source snapshot"}),
                canonical_identity({"modeled": "source tree"}),
                canonical_identity({"modeled": "original local resolver"}),
            )
        if self.effect is not None:
            self.effect()
        return self.locks[dependency.identity]


class ActualPreparationOriginControls(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.component, self.flavors = _fixture(Path(temporary.name).resolve())
        self.planner = FilesystemComponentLockPlanner()

    def prepare(self):
        return operations.prepare_component_lock(
            self.component,
            target="macos-host",
            flavors=("+macos", "+python"),
            flavor_roots=(self.flavors,),
            planner=self.planner,
        )

    def test_actual_prepare_admits_exact_selection_but_plain_copy_does_not(self):
        prepared = self.prepare()
        admitted = operations.require_original_prepared_component_lock(prepared)
        self.assertIs(admitted[0], self.planner)
        self.assertEqual(
            admitted[1:], ("macos-host", ("+macos", "+python"), (self.flavors,))
        )
        with self.assertRaises(ComponentLockPlanningError):
            operations.require_original_prepared_component_lock(replace(prepared))

    def test_original_prepared_field_and_planner_pointer_substitution_refuse(self):
        prepared = self.prepare()
        original = prepared.component_root
        try:
            object.__setattr__(prepared, "component_root", original / "foreign")
            with self.assertRaises(ComponentLockPlanningError):
                operations.require_original_prepared_component_lock(prepared)
        finally:
            object.__setattr__(prepared, "component_root", original)
        resolver = self.planner.repository_source_resolver
        try:
            self.planner.repository_source_resolver = object()
            with self.assertRaises(ComponentLockPlanningError):
                operations.require_original_prepared_component_lock(prepared)
        finally:
            self.planner.repository_source_resolver = resolver

    def test_normal_instrumented_prepare_still_returns_unadmitted_data(self):
        original = self.planner.plan_with_snapshot
        self.planner.plan_with_snapshot = original
        prepared = self.prepare()
        self.assertIsInstance(prepared, operations.PreparedComponentLock)
        with self.assertRaises(ComponentLockPlanningError):
            operations.require_original_prepared_component_lock(prepared)

    def test_prepared_class_descriptor_drift_refuses_before_foreign_access(self):
        prepared = self.prepare()
        calls = []

        def foreign(value):
            calls.append(value)
            raise AssertionError("foreign descriptor ran")

        with patch.object(operations.PreparedComponentLock, "plan", property(foreign)):
            with self.assertRaises(ComponentLockPlanningError):
                operations.require_original_prepared_component_lock(prepared)
        self.assertEqual(calls, [])

    def test_unadmitted_instrumented_normal_check_retains_legacy_behavior(self):
        self.planner.plan_with_snapshot = self.planner.plan_with_snapshot
        prepared = self.prepare()
        calls = []
        original_check = operations.ComponentLockStore.check

        def observed(store, *args, **kwargs):
            calls.append(store)
            return original_check(store, *args, **kwargs)

        with patch.object(operations.ComponentLockStore, "check", observed):
            report, status = operations.operate_component_lock(
                prepared,
                target="macos-host",
                flavors=("+macos", "+python"),
                flavor_roots=(self.flavors,),
                planner=self.planner,
                check=True,
                difference=False,
            )
        self.assertEqual(status, 1)
        self.assertFalse(report["current"])
        self.assertEqual(len(calls), 2)


@unittest.skipUnless(os.name == "posix", "owned POSIX journal; Windows unqualified")
class DestinationJournalControls(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CatalogContinuationWriterTests(methodName="runTest")
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        f = self.fixture
        component, self.flavors = _fixture(f.root)
        self.requested_flavors = ("+macos", "+flavor://literate-ai/lang-python")
        _flavor_variant(
            self.flavors / "lang-python",
            self.flavors / "lang-python-alternate",
            name="lang-python-alternate",
            value="python",
        )
        # The modeled writer's unrelated Skill is part of the real project
        # catalog now, so retain its role with a valid original Skill document.
        (f.root / "skills/example/SKILL.md").write_bytes(
            b"---\nname: example\ndescription: Local producer fixture.\n---\n"
            b"# Local fixture Skill\n"
        )
        self.component = f.root / "components/selected"
        self.component.parent.mkdir()
        component.rename(self.component)
        # Both declared catalog roots exist during the transitional observation.
        (f.root / "litai/components").mkdir()
        # The reused writer fixture has inert non-JSON metadata; the actual
        # normal reader needs genuine typed empty catalog provenance instead.
        (f.root / "litai/.literate/imports.json").write_bytes(
            canonical_json_bytes(CatalogImportsFile(()).to_dict()) + b"\n"
        )
        parent = RepositoryParentSelection.root()
        for name, value in (
            ("repository-parent", parent),
            ("repository-lineage", RepositoryLineage(parent, (), ())),
        ):
            (f.root / "litai/.literate" / (name + ".json")).write_bytes(
                canonical_json_bytes(value.to_dict()) + b"\n"
            )
        definition = replace(
            _definition(),
            framework_directory="litai",
            agent_skill="SKILL.md",
            component_roots=("components", "litai/components"),
            flavor_roots=("flavors",),
            skill_roots=("skills",),
            workflow_roots=("workflows",),
            routing_roots=("routing",),
            documentation_roots=("docs",),
            source_cache=None,
        )
        (f.root / "litai/literate.project.json").write_bytes(
            serialize_project_configuration(definition)
        )
        self.resolver = _LocalTypedResolver()
        self.planner = FilesystemComponentLockPlanner(
            repository_source_resolver=self.resolver
        )
        if self._testMethodName.startswith("test_resolver_"):
            manifest = self.component / "component.md"
            manifest.write_text(
                manifest.read_text().replace(
                    "source_dependencies: []",
                    """source_dependencies:
  - dependency_id: local-proof
    repository_url: https://example.test/local-proof.git
    revision_selector:
      kind: commit
      value: aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa
    dependency_kind: build
""",
                )
            )
        before = self.prepare(self.component)
        self.operate(before, check=False)
        f.source = "components/selected/component.md"
        f.target = "litai/" + f.source
        f.selection = f.select()
        selected = f.selection
        selected.public_plan["project_id"] = definition.project_id
        selected.public_plan["resident_edits"] = {}
        selected.rewritten_contents = {}
        nodes, contents = _capture(f.root)
        source = "components/selected"
        records, originals = {}, {}
        for path in (
            source + "/component.lock.json",
            source + "/component.resolution-audit.macos-host.json",
        ):
            payload = contents[path]
            records[path] = {
                "identity": writer._owner()._identity(payload),
                "mode": nodes[path]["mode"],
                "kind": "modeled-placement-producer",
                "typed_identity": (
                    before.result.lock.identity.uri
                    if path.endswith("component.lock.json")
                    else before.result.catalog_audit.identity.uri
                ),
            }
            originals[path] = payload
        endpoint = SimpleNamespace(
            source_root=source,
            destination_root="litai/" + source,
            manifest_identity=writer._owner()._identity(contents[f.source]),
            target_names=("macos-host",),
            imported_source=object(),
        )
        self.transition = fixtures._ModeledTransition(
            f.root, endpoint, contents[f.source], records, originals
        )
        self.transition.source_kind = "inherited"
        endpoint.producer_transition = self.transition
        selected.component_endpoints = (endpoint,)
        selected.public_plan["placements"] = {
            path: {
                "destination": "litai/" + path,
                "from": writer._owner()._identity(payload),
                "to": writer._owner()._identity(payload),
                "mode": nodes[path]["mode"],
            }
            for path, payload in contents.items()
            if path.startswith(source + "/")
            and path not in self.transition.coordination_paths
        }
        selected.public_plan.pop("plan_identity")
        selected.public_plan["plan_identity"] = canonical_identity(
            selected.public_plan
        ).uri
        with self.model_origin():
            result = f.apply()
        self.journal = Path(result["journal"])
        self.expected = ProjectConfigurationStore(f.root).read()
        self.prepared = self.prepare(f.root / endpoint.destination_root)

    def prepare(self, root):
        return operations.prepare_component_lock(
            root,
            target="macos-host",
            flavors=self.requested_flavors,
            flavor_roots=(self.flavors,),
            planner=self.planner,
        )

    def operate(self, prepared, *, check):
        return operations.operate_component_lock(
            prepared,
            target="macos-host",
            flavors=self.requested_flavors,
            flavor_roots=(self.flavors,),
            planner=self.planner,
            check=check,
            difference=False,
        )

    @contextmanager
    def model_origin(self):
        selected = self.transition

        def admission(owner):
            if owner is not selected:
                raise AssertionError("foreign modeled transition")

        with (
            patch.object(
                writer, "_transition_type", return_value=fixtures._ModeledTransition
            ),
            patch.object(writer, "_admit_transition", admission),
            patch.object(destination, "_ADMIT_TRANSITION", admission),
        ):
            with self.bind_classifier():
                yield

    @contextmanager
    def bind_classifier(self):
        # Explicit paired model factory seam, not a production origin fallback.
        guard, call, classifier = destination._build_classifier()
        with (
            patch.object(destination, "_callbacks_current", guard),
            patch.object(destination, "_call", call),
            patch.object(destination, "classify_component_destination", classifier),
        ):
            yield

    def classify(self, lease):
        return destination.classify_component_destination(
            self.transition,
            self.expected,
            prepared=self.prepared,
            layout_lease=lease,
            plan_identity=self.fixture.selection.public_plan["plan_identity"],
        )

    def test_actual_unchanged_pair_is_current_without_renewal(self):
        with (
            self.model_origin(),
            ProjectConfigurationStore.layout_lock(self.fixture.root),
        ):
            lease = current_layout_lease(self.fixture.root)
            current = self.classify(lease)
            self.assertEqual(current["state"], "current")
            self.assertFalse(current["writes"])
            self.assertEqual(self.classify(lease), current)
        self.fixture.assert_custody()

    def test_actual_changed_flavor_selection_requires_normal_renewal(self):
        self.requested_flavors = (
            "+macos",
            "+flavor://literate-ai/lang-python-alternate",
        )
        self.prepared = self.prepare(self.prepared.component_root)
        with (
            self.model_origin(),
            ProjectConfigurationStore.layout_lock(self.fixture.root),
        ):
            lease = current_layout_lease(self.fixture.root)
            stale = self.classify(lease)
            self.assertEqual(stale["state"], "renewal-required")
            # Real normal producer update, no generic migration component fences.
            self.operate(self.prepared, check=False)
            current = self.classify(lease)
            self.assertEqual(current["state"], "current")
            self.assertFalse(current["writes"])
            self.assertFalse(current["finalized"])
            self.assertEqual(self.classify(lease), current)
        self.fixture.assert_custody()

    def test_original_currentness_error_is_same_object_never_renewal(self):
        failure = OSError("owned modeled read failure")

        def fail_read(store):
            raise failure

        with (
            self.model_origin(),
            ProjectConfigurationStore.layout_lock(self.fixture.root),
        ):
            lease = current_layout_lease(self.fixture.root)
            with (
                patch.object(destination, "_PROJECT_READ", fail_read),
                self.bind_classifier(),
            ):
                with self.assertRaises(OSError) as caught:
                    self.classify(lease)
            self.assertIs(caught.exception, failure)

    def test_changed_nonproducer_postimage_refuses_even_after_normal_renewal(self):
        self.operate(self.prepared, check=False)
        (self.fixture.root / self.fixture.target).write_bytes(b"foreign authoring\n")
        with (
            self.model_origin(),
            ProjectConfigurationStore.layout_lock(self.fixture.root),
        ):
            with self.assertRaises(
                (ProjectLayoutPlanError, ComponentLockPlanningError)
            ):
                self.classify(current_layout_lease(self.fixture.root))

    def test_old_history_byte_change_refuses_without_repair(self):
        history = next((self.journal / "history").iterdir())
        original = history.read_bytes()
        history.write_bytes(original + b"foreign")
        with (
            self.model_origin(),
            ProjectConfigurationStore.layout_lock(self.fixture.root),
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                self.classify(current_layout_lease(self.fixture.root))
        self.assertEqual(history.read_bytes(), original + b"foreign")

    def test_expired_original_lease_and_foreign_expected_snapshot_refuse(self):
        with ProjectConfigurationStore.layout_lock(self.fixture.root):
            lease = current_layout_lease(self.fixture.root)
        with self.model_origin(), self.assertRaises(ValueError):
            self.classify(lease)
        self.expected = replace(self.expected, content=self.expected.content + b"\n")
        with (
            self.model_origin(),
            ProjectConfigurationStore.layout_lock(self.fixture.root),
        ):
            with self.assertRaises(ProjectLayoutPlanError):
                self.classify(current_layout_lease(self.fixture.root))

    def test_closing_callback_delegate_change_refuses_before_foreign_lease(self):
        calls = []
        original_read, original_lease = destination._PROJECT_READ, destination._LEASE

        def foreign_lease(*args):
            calls.append(args)
            raise AssertionError("foreign lease invoked")

        def change_after_read(store):
            value = original_read(store)
            destination._LEASE = foreign_lease
            return value

        with (
            self.model_origin(),
            ProjectConfigurationStore.layout_lock(self.fixture.root),
        ):
            lease = current_layout_lease(self.fixture.root)
            with (
                patch.object(destination, "_PROJECT_READ", change_after_read),
                self.bind_classifier(),
            ):
                try:
                    with self.assertRaises(ProjectLayoutPlanError):
                        self.classify(lease)
                finally:
                    destination._LEASE = original_lease
        self.assertEqual(calls, [])

    def test_initialized_kind_uses_same_actual_normal_check_without_import_decode(self):
        # Kind branch only is modeled; real initialized source origin is the
        # separate original transition factory's responsibility.
        self.transition.source_kind = "initialized"
        self.operate(self.prepared, check=False)
        with (
            self.model_origin(),
            ProjectConfigurationStore.layout_lock(self.fixture.root),
        ):
            state = self.classify(current_layout_lease(self.fixture.root))
        self.assertEqual(state["source_kind"], "initialized")
        self.assertEqual(state["state"], "current")
        self.assertFalse(state["finalized"])

    def test_before_entry_owner_file_and_constructor_and_checkers_never_invoked(self):
        calls = []

        def foreign(*args, **kwargs):
            calls.append((args, kwargs))
            raise AssertionError("foreign delegate invoked")

        with (
            self.model_origin(),
            ProjectConfigurationStore.layout_lock(self.fixture.root),
        ):
            lease = current_layout_lease(self.fixture.root)
            for module, name in (
                (destination.migration, "_file"),
                (destination.leaf, "_read"),
                (destination, "ProjectConfigurationStore"),
                (destination, "_callbacks_current"),
                (destination, "_call"),
            ):
                with self.subTest(delegate=name), patch.object(module, name, foreign):
                    with self.assertRaises(ProjectLayoutPlanError):
                        self.classify(lease)
        self.assertEqual(calls, [])

    def test_resolver_checker_and_call_replacement_never_dispatched(self):
        calls = []
        original_guard, original_call = (
            destination._callbacks_current,
            destination._call,
        )

        def foreign(*args, **kwargs):
            calls.append((args, kwargs))

        def effect():
            destination._callbacks_current = foreign
            destination._call = foreign

        with (
            self.model_origin(),
            ProjectConfigurationStore.layout_lock(self.fixture.root),
        ):
            lease = current_layout_lease(self.fixture.root)
            # Capture the actual paired model exports admitted at this entry.
            original_guard, original_call = (
                destination._callbacks_current,
                destination._call,
            )
            self.resolver.effect = effect
            try:
                with self.assertRaises(ProjectLayoutPlanError):
                    self.classify(lease)
            finally:
                self.resolver.effect = None
                destination._callbacks_current, destination._call = (
                    original_guard,
                    original_call,
                )
        self.assertEqual(calls, [])

    def test_resolver_owner_file_replacement_never_dispatched(self):
        calls = []
        original_file = destination.migration._file

        def foreign(*args, **kwargs):
            calls.append((args, kwargs))
            return original_file(*args, **kwargs)

        def effect():
            destination.migration._file = foreign

        with (
            self.model_origin(),
            ProjectConfigurationStore.layout_lock(self.fixture.root),
        ):
            lease = current_layout_lease(self.fixture.root)
            self.resolver.effect = effect
            try:
                with self.assertRaises(ProjectLayoutPlanError):
                    self.classify(lease)
            finally:
                self.resolver.effect = None
                destination.migration._file = original_file
        self.assertEqual(calls, [])

    def test_resolver_temporary_store_check_substitution_refuses_before_check(self):
        calls = []
        original_check = operations.ComponentLockStore.check
        original_calls = self.resolver.calls

        def foreign(*args, **kwargs):
            calls.append((args, kwargs))
            return original_check(*args, **kwargs)

        def effect():
            # Old code could reach two artifact checks then restore on callback3.
            if self.resolver.calls - original_calls == 1:
                operations.ComponentLockStore.check = foreign
            elif self.resolver.calls - original_calls == 3:
                operations.ComponentLockStore.check = original_check

        self.resolver.effect = effect
        try:
            with self.assertRaises(ComponentLockPlanningError):
                self.operate(self.prepared, check=True)
        finally:
            self.resolver.effect = None
            operations.ComponentLockStore.check = original_check
        self.assertEqual(self.resolver.calls - original_calls, 1)
        self.assertEqual(calls, [])

    def test_resolver_primary_error_survives_checker_mutation(self):
        failure = OSError("actual resolver callback failure")
        calls = []

        def foreign(*args, **kwargs):
            calls.append((args, kwargs))

        def effect():
            destination._callbacks_current = foreign
            destination._call = foreign
            raise failure

        with (
            self.model_origin(),
            ProjectConfigurationStore.layout_lock(self.fixture.root),
        ):
            lease = current_layout_lease(self.fixture.root)
            original_guard, original_call = (
                destination._callbacks_current,
                destination._call,
            )
            self.resolver.effect = effect
            try:
                with self.assertRaises(OSError) as caught:
                    self.classify(lease)
                self.assertIs(caught.exception, failure)
            finally:
                self.resolver.effect = None
                destination._callbacks_current, destination._call = (
                    original_guard,
                    original_call,
                )
        self.assertEqual(calls, [])
