"""Canonical metadata/role readers under a finite operation-local allowance."""

from __future__ import annotations

import os
import sys
import threading
import unittest
from contextlib import ExitStack
from contextvars import copy_context
from dataclasses import replace
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_control_roles as fixtures
from literate_ai.adapters import bounded_role_observation as reads
from literate_ai.adapters import project_identity_migration as migration
from literate_ai.adapters import repository_orchestration as orchestration
from literate_ai.adapters import repository_refresh as refresh
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.builders._process import (
    BoundedProcessResult,
    run_bounded_process,
)
from literate_ai.adapters.conversion_authority import (
    FilesystemConversionAuthorityStore,
    _native_project_roots,
    register_native_project,
)
from literate_ai.adapters.retained_layout_control_roles import _project_roles
from literate_ai.adapters.retained_layout_git_controls import (
    observe_layout_git_controls,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.projects import LoadedProject, ProjectConfigurationStore, load_project
from tests.support.fixtures_test_project_agent_development_workflow import _definition


class BoundedRoleReadTests(unittest.TestCase):
    def test_original_reader_providers_support_all_cold_import_start_orders(self):
        modules = (
            "literate_ai.adapters.bounded_role_observation",
            "literate_ai.adapters.catalog_copy_plan",
            "literate_ai.adapters.retained_layout_transaction",
            "literate_ai.adapters.catalog_copy_protection",
            "literate_ai.adapters.retained_layout_source_metadata",
        )
        source = str(Path(transaction.__file__).parents[2])
        for first in modules:
            with self.subTest(first=first):
                order = (first,) + tuple(name for name in modules if name != first)
                program = (
                    "import importlib,sys\n"
                    f"sys.path.insert(0, {source!r})\n"
                    f"for name in {order!r}: importlib.import_module(name)\n"
                    "from literate_ai.adapters.bounded_role_observation import "
                    "bounded_role_observation,_original_role_metadata_guard\n"
                    "from literate_ai.contracts.retained_cargo_custody import "
                    "RetainedCargoInputBudget\n"
                    "with bounded_role_observation(budget=RetainedCargoInputBudget"
                    "(32,4096,1024,32*1024),"
                    "maximum_metadata_bytes=64*1024**2) as owner:\n"
                    " _original_role_metadata_guard(owner)\n"
                    "print('original Role/ledger issuance ok')\n"
                )
                result = run_bounded_process(
                    (sys.executable, "-I", "-c", program),
                    cwd=self.root,
                    environment=dict(os.environ),
                    timeout_seconds=30,
                    stdout_limit_bytes=8192,
                    stderr_limit_bytes=8192,
                    error_prefix="cold_role_provider_import",
                    trace=False,
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(
                    result.stdout.strip(), b"original Role/ledger issuance ok"
                )

    git = fixtures.RetainedLayoutControlRoleTests.git
    init_git = fixtures.RetainedLayoutControlRoleTests.init_git

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutControlRoleTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutControlRoleTests.setUp(self)
        self.read_budget = RetainedCargoInputBudget(
            2048, 32768, 4 * 1024**2, 64 * 1024**2
        )

    def scope(self, budget=None):
        return reads.bounded_role_observation(
            budget=self.read_budget if budget is None else budget,
            maximum_metadata_bytes=2 * 1024**3,
        )

    def test_actual_project_conversion_and_git_roles_match_default_readers(self):
        self.init_git()
        expected_project = _project_roles(self.project)
        expected_git = observe_layout_git_controls(self.project)
        with self.scope() as scope:
            self.assertEqual(_project_roles(self.project), expected_project)
            actual = observe_layout_git_controls(self.project)
            self.assertEqual(actual, expected_git)
            actual.require_unchanged()
            scope.require_current()
        self.assertFalse(hasattr(scope, "publish"))

    def test_configuration_and_conversion_use_original_parsers(self):
        expected = ProjectConfigurationStore(self.project).read()
        conversion = FilesystemConversionAuthorityStore(self.project).load_optional()
        with self.scope() as scope:
            self.assertEqual(ProjectConfigurationStore(self.project).read(), expected)
            self.assertEqual(
                FilesystemConversionAuthorityStore(self.project).load_optional(),
                conversion,
            )
            self.assertTrue(scope._ledger.cache)

    def declared_layout(self, implementation=None):
        import json

        from literate_ai.adapters.retained_layout import RetainedLayoutDeclaration

        wrapper = "components/legacy-project-wrapper"
        implementation = implementation or f"{wrapper}/implementation"
        owned = (
            tuple(
                sorted(
                    (
                        ".literate/initialization-baseline.json",
                        transaction.RETAINED_LAYOUT_PATH,
                        "literate.project.json",
                        f"{wrapper}/component.md",
                    )
                )
            )
            if implementation == "."
            else ()
        )
        declaration = RetainedLayoutDeclaration(wrapper, implementation, owned, None)
        (self.project / transaction.RETAINED_LAYOUT_PATH).write_bytes(
            canonical_json_bytes(declaration.to_dict()) + b"\n"
        )
        path = self.project / transaction._LIFT
        lift = json.loads(path.read_bytes())
        lift.update(
            implementation_directory=implementation,
            wrapper_component=wrapper,
            layout_identity=declaration.identity,
            previous_layout_identity=None,
        )
        path.write_bytes(canonical_json_bytes(lift) + b"\n")
        return self.project / wrapper / "component.md"

    def test_source_discovery_uses_same_canonical_inputs_in_bounded_scope(self):
        expected = transaction._inputs(self.project)
        with self.scope() as scope:
            self.assertEqual(transaction._inputs(self.project), expected)
            for item in expected[1]:
                self.assertEqual(scope._ledger.cache[item.path], item)

    def test_declared_source_discovery_funds_structural_component_reads(self):
        component = self.declared_layout()
        expected = transaction._inputs(self.project)
        read_text = Path.read_text

        def guarded(path, *args, **kwargs):
            self.assertNotEqual(path, component, "unfunded structural Component read")
            return read_text(path, *args, **kwargs)

        with self.scope() as scope, mock.patch.object(Path, "read_text", guarded):
            self.assertEqual(transaction._inputs(self.project), expected)
            self.assertEqual(
                scope._ledger.cache[component].content, component.read_bytes()
            )

    def test_source_component_change_during_structural_resolution_refuses(self):
        component = self.declared_layout()
        resolve = transaction.resolve_structural_layout

        def change(*args, **kwargs):
            layout = resolve(*args, **kwargs)
            original = component.read_bytes()
            component.write_bytes(original[:-1] + b"!")
            return layout

        with self.assertRaisesRegex(ValueError, "original role input changed"):
            with (
                self.scope(),
                mock.patch.object(transaction, "resolve_structural_layout", change),
            ):
                transaction._inputs(self.project)
        self.assertTrue(component.read_bytes().endswith(b"!"))

    def test_source_discovery_refuses_root_before_structural_enumeration(self):
        self.declared_layout(".")
        with self.assertRaisesRegex(ValueError, "complete mixed-partition owner"):
            with (
                self.scope(),
                mock.patch.object(
                    transaction,
                    "resolve_structural_layout",
                    side_effect=AssertionError("root structural discovery"),
                ),
            ):
                transaction._inputs(self.project)

    def test_project_role_first_read_keeps_canonical_manifest_ceiling(self):
        from literate_ai.projects import DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES

        path = self.project / "literate.project.json"
        with path.open("r+b") as stream:
            stream.truncate(DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES + 1)
        raw_file = refresh._raw_file
        limits = []

        def observe(path, **kwargs):
            limits.append((path, kwargs["maximum_bytes"]))
            return raw_file(path, **kwargs)

        with self.assertRaises(ValueError):
            with self.scope(), mock.patch.object(refresh, "_raw_file", observe):
                transaction._inputs(self.project)
        self.assertEqual(limits[0], (path, DEFAULT_MAXIMUM_PROJECT_CONFIGURATION_BYTES))

    def test_source_discovery_exhausts_shared_allowance_before_later_inputs(self):
        raw_file = refresh._raw_file
        paths = []

        def observe(path, **kwargs):
            paths.append(path)
            return raw_file(path, **kwargs)

        budget = RetainedCargoInputBudget(2, 32768, 4 * 1024**2, 8 * 1024**2)
        with self.assertRaises(ValueError):
            with self.scope(budget), mock.patch.object(refresh, "_raw_file", observe):
                transaction._inputs(self.project)
        self.assertNotIn(self.project / transaction._ORIGIN, paths)
        self.assertNotIn(
            self.project / "components/legacy-project-wrapper/component.md", paths
        )

    def test_source_declaration_first_read_keeps_canonical_layout_ceiling(self):
        path = self.project / transaction.RETAINED_LAYOUT_PATH
        with path.open("wb") as stream:
            stream.truncate(transaction._MAX_LAYOUT_BYTES + 1)
        raw_file = refresh._raw_file
        limits = []

        def observe(selected, **kwargs):
            if selected == path:
                limits.append(kwargs["maximum_bytes"])
            return raw_file(selected, **kwargs)

        budget = RetainedCargoInputBudget(2048, 32768, 32 * 1024**2, 128 * 1024**2)
        with self.assertRaises(ValueError):
            with (
                reads.bounded_role_observation(
                    budget=budget, maximum_metadata_bytes=4 * 1024**3
                ),
                mock.patch.object(refresh, "_raw_file", observe),
            ):
                transaction._inputs(self.project)
        self.assertEqual(limits, [transaction._MAX_LAYOUT_BYTES])

    def test_source_resolver_adapter_cannot_escape_its_actual_read_scope(self):
        original = self.adapter_inputs(self.project)
        with self.scope() as scope:
            adapter = transaction._SourceMetadataObservation(
                self.project, scope, **original
            )
            self.assertIsNotNone(adapter.read("literate.project.json"))
        with self.assertRaises(TypeError):
            adapter.read("literate.project.json")

    def test_adapter_refuses_changed_ledger_method_before_foreign_charge(self):
        from literate_ai.adapters import catalog_copy_plan as accounting

        inputs = self.adapter_inputs(self.project)
        function = accounting._Observation.charge_records
        original = function.__code__
        with self.scope() as scope:
            try:
                function.__code__ = original.replace(co_name="changed")
                with self.assertRaisesRegex(ValueError, "accounting method changed"):
                    transaction._source_metadata_observation(
                        self.project, scope, **inputs
                    )
            finally:
                function.__code__ = original

    def test_original_callers_refuse_replaced_constructor_before_dispatch(self):
        from literate_ai.adapters import catalog_copy_protection as catalog
        from literate_ai.adapters import retained_layout_source_metadata as published

        with mock.patch.object(
            transaction,
            "_source_metadata_observation",
            side_effect=AssertionError("foreign constructor"),
        ) as foreign:
            for invoke in (
                lambda: transaction._inputs(self.project),
                lambda: published._published_layout(None),
                lambda: catalog._ProjectReads(None, None, None),
            ):
                with self.subTest(caller=invoke):
                    with self.assertRaisesRegex(
                        ValueError, "constructor provider changed"
                    ):
                        invoke()
            foreign.assert_not_called()

    def test_original_input_caller_refuses_same_constructor_object_code_change(self):
        function = transaction._source_metadata_observation
        original = function.__code__
        try:
            function.__code__ = original.replace(co_name="changed")
            with self.assertRaisesRegex(ValueError, "constructor provider changed"):
                transaction._inputs(self.project)
        finally:
            function.__code__ = original

    def test_original_binder_cannot_bless_changed_constructor(self):
        with mock.patch.object(
            transaction,
            "_source_metadata_observation",
            side_effect=AssertionError("foreign constructor"),
        ) as foreign:
            with self.assertRaisesRegex(ValueError, "constructor provider changed"):
                transaction._bind_original_source_metadata_ports()
            foreign.assert_not_called()

    def test_catalog_validator_refuses_replaced_guard_before_dispatch(self):
        from literate_ai.adapters import catalog_copy_protection as catalog

        # This negative cut refuses before reading any uninitialized fields.
        reader = catalog._ProjectReads.__new__(catalog._ProjectReads)
        with mock.patch.object(
            transaction,
            "_original_source_metadata_guard",
            side_effect=AssertionError("foreign guard"),
        ) as foreign:
            with self.assertRaisesRegex(ValueError, "source metadata adapter changed"):
                reader._metadata_reader()
            foreign.assert_not_called()

    def test_normal_input_call_cannot_override_private_constructor_ports(self):
        foreign = mock.Mock(side_effect=AssertionError("foreign constructor"))
        with self.assertRaisesRegex(ValueError, "constructor boundary changed"):
            transaction._inputs(self.project, _metadata_ports=(foreign, foreign))
        foreign.assert_not_called()

    def test_adapter_refuses_shadowed_issued_reader_method(self):
        inputs = self.adapter_inputs(self.project)
        with self.scope() as scope:
            with mock.patch.object(
                scope, "_begin_io", side_effect=AssertionError("foreign")
            ) as foreign:
                with self.assertRaisesRegex(ValueError, "issued Role metadata methods"):
                    transaction._source_metadata_observation(
                        self.project, scope, **inputs
                    )
                foreign.assert_not_called()

    def test_adapter_refuses_shadowed_issued_ledger_method(self):
        inputs = self.adapter_inputs(self.project)
        with self.scope() as scope:
            with mock.patch.object(
                scope._ledger, "charge_records", side_effect=AssertionError("foreign")
            ) as foreign:
                with self.assertRaisesRegex(
                    ValueError, "issued metadata accounting methods"
                ):
                    transaction._source_metadata_observation(
                        self.project, scope, **inputs
                    )
                foreign.assert_not_called()

    def test_adapter_factory_refuses_changed_constructor_code(self):
        inputs = self.adapter_inputs(self.project)
        function = transaction._SourceMetadataObservation.__init__
        original = function.__code__
        with self.scope() as scope:
            try:
                function.__code__ = original.replace(co_name="changed")
                with self.assertRaisesRegex(
                    ValueError, "source metadata adapter changed"
                ):
                    transaction._source_metadata_observation(
                        self.project, scope, **inputs
                    )
            finally:
                function.__code__ = original

    def test_adapter_refuses_changed_original_reader_closing_method(self):
        inputs = self.adapter_inputs(self.project)
        function = reads._RoleObservation.require_current
        original = function.__code__
        with self.scope() as scope:
            try:
                function.__code__ = original.replace(co_name="changed")
                with self.assertRaisesRegex(
                    ValueError, "Role metadata methods changed"
                ):
                    transaction._source_metadata_observation(
                        self.project, scope, **inputs
                    )
            finally:
                function.__code__ = original

    def test_adapter_refuses_shadowed_original_reader_closing_method(self):
        inputs = self.adapter_inputs(self.project)
        with self.scope() as scope:
            with mock.patch.object(
                scope, "require_current", side_effect=AssertionError("foreign")
            ) as foreign:
                with self.assertRaisesRegex(ValueError, "issued Role metadata methods"):
                    transaction._source_metadata_observation(
                        self.project, scope, **inputs
                    )
                foreign.assert_not_called()

    def test_adapter_factory_checks_its_guard_before_dispatch(self):
        inputs = self.adapter_inputs(self.project)
        function = transaction._original_source_metadata_guard
        original = function.__code__
        with self.scope() as scope:
            try:
                function.__code__ = original.replace(co_name="changed")
                with self.assertRaisesRegex(ValueError, "adapter guard changed"):
                    transaction._source_metadata_observation(
                        self.project, scope, **inputs
                    )
            finally:
                function.__code__ = original

    def test_original_guards_do_not_dispatch_late_vars_shadows(self):
        from literate_ai.adapters import catalog_copy_plan as accounting
        from literate_ai.adapters import project_layout_finite_creations as absences

        inputs = self.adapter_inputs(self.project)
        with self.scope() as scope:
            with ExitStack() as patches:
                foreign = [
                    patches.enter_context(
                        mock.patch.object(
                            module,
                            "vars",
                            side_effect=AssertionError("foreign"),
                            create=True,
                        )
                    )
                    for module in (reads, accounting, transaction, absences)
                ]
                transaction._source_metadata_observation(self.project, scope, **inputs)
                for callback in foreign:
                    callback.assert_not_called()

    def test_metadata_adapter_instance_cannot_shadow_its_read_methods(self):
        inputs = self.adapter_inputs(self.project)
        with self.scope() as scope:
            adapter = transaction._source_metadata_observation(
                self.project, scope, **inputs
            )
            for name in ("read", "read_coordinate", "project_context", "_live"):
                with self.subTest(method=name):
                    with self.assertRaises(AttributeError):
                        setattr(
                            adapter, name, lambda *args: self.fail("foreign method")
                        )

    def test_source_resolver_adapter_requires_present_actual_owner(self):
        with self.assertRaises(TypeError):
            transaction._SourceMetadataObservation(
                self.project, None, **self.adapter_inputs(self.project)
            )

    def adapter_inputs(self, root):
        context = ProjectConfigurationStore.context(root)
        node = root.stat()
        return {
            "manifest": refresh._file(context.manifest_path),
            "root_node": (node.st_dev, node.st_ino, node.st_mode),
            "snapshot": ProjectConfigurationStore(root).read(),
            "context": context,
        }

    def test_loader_retains_snapshot_without_changing_positional_value_behavior(self):
        loaded = load_project(self.project)
        legacy = LoadedProject(loaded.root, loaded.definition)
        self.assertIs(loaded._snapshot.definition, loaded.definition)
        self.assertEqual(loaded, legacy)
        self.assertEqual(repr(loaded), repr(legacy))
        self.assertEqual(LoadedProject.__match_args__, ("root", "definition"))
        self.assertIsNone(legacy._snapshot)

    def test_source_roles_refuse_missing_or_stale_loader_snapshot(self):
        from literate_ai.adapters import retained_layout_control_roles as roles

        loaded = load_project(self.project)
        forged_definition = replace(loaded.definition, component_roots=("foreign",))
        for foreign in (
            LoadedProject(loaded.root, loaded.definition),
            replace(loaded, definition=replace(loaded.definition)),
            replace(loaded, _snapshot=replace(loaded._snapshot, content=b"{}")),
            replace(
                loaded,
                definition=forged_definition,
                _snapshot=replace(
                    loaded._snapshot,
                    definition=forged_definition,
                ),
            ),
        ):
            with self.subTest(snapshot=foreign._snapshot is None):
                with mock.patch.object(
                    roles, "load_project", return_value=foreign
                ) as loader:
                    with self.assertRaisesRegex(ValueError, "original project loader"):
                        roles._project_roles(self.project)
                    loader.assert_not_called()

    def test_source_loader_ignores_ambient_templates_and_restores_frame(self):
        import literate_ai.projects as projects

        loaded = load_project(self.project)
        ambient = projects._ProjectConfigurationParses()
        ambient.templates[loaded._snapshot.content] = replace(
            loaded.definition, component_roots=("foreign",)
        )
        token = projects._PROJECT_CONFIGURATION_PARSES.set(ambient)
        try:
            project = _project_roles(self.project)
            self.assertEqual(project._snapshot.definition, loaded.definition)
            self.assertIs(projects._PROJECT_CONFIGURATION_PARSES.get(), ambient)
            self.assertEqual(
                ambient.templates[loaded._snapshot.content].component_roots,
                ("foreign",),
            )
        finally:
            projects._PROJECT_CONFIGURATION_PARSES.reset(token)

    def test_source_loader_restores_frame_after_original_store_failure(self):
        import inspect

        import literate_ai.projects as projects
        from literate_ai.adapters import retained_layout_control_roles as roles

        # Inspect only the test-owned port closure to exercise its failure path
        # directly. This does not issue project/source roles or a read lease.
        loader = inspect.getclosurevars(roles._project_roles).nonlocals["original_load"]
        ambient = projects._ProjectConfigurationParses()
        token = projects._PROJECT_CONFIGURATION_PARSES.set(ambient)
        try:
            with self.assertRaises(projects.ProjectError):
                loader(self.state / "missing-project")
            self.assertIs(projects._PROJECT_CONFIGURATION_PARSES.get(), ambient)
        finally:
            projects._PROJECT_CONFIGURATION_PARSES.reset(token)

    def test_source_loader_refuses_changed_original_read_code_before_native_io(self):
        from literate_ai.adapters import retained_layout_control_roles as roles

        function = ProjectConfigurationStore.read
        original = function.__code__
        try:
            function.__code__ = original.replace(co_name="foreign_read")
            with mock.patch.object(
                roles, "_lineage", side_effect=AssertionError("native discovery")
            ) as native:
                with self.assertRaisesRegex(ValueError, "original project loader"):
                    roles._project_roles(self.project)
                native.assert_not_called()
        finally:
            function.__code__ = original

    def test_source_loader_refuses_foreign_error_exports_before_dispatch(self):
        import literate_ai.projects as projects
        from literate_ai.adapters import retained_layout_control_roles as roles

        for module, name in (
            (projects, "ProjectError"),
            (projects.json, "JSONDecodeError"),
        ):
            with self.subTest(error=name):
                foreign = mock.Mock(side_effect=AssertionError("foreign error"))
                with mock.patch.object(module, name, foreign):
                    with self.assertRaisesRegex(ValueError, "original project loader"):
                        roles._project_roles(self.project)
                    foreign.assert_not_called()

    def test_source_loader_closes_port_after_final_control_read_callback(self):
        from literate_ai.adapters import retained_layout_control_roles as roles

        original_loader, original_file = roles.load_project, roles._file
        conversion = self.project / roles.CONVERSION_AUTHORITY_FILE
        calls = 0
        foreign = mock.Mock(side_effect=AssertionError("foreign loader"))

        def read(path, **kwargs):
            nonlocal calls
            value = original_file(path, **kwargs)
            if path == conversion:
                calls += 1
                if calls == 2:
                    roles.load_project = foreign
            return value

        with (
            mock.patch.object(roles, "load_project", original_loader),
            mock.patch.object(roles, "_file", read),
        ):
            with self.assertRaisesRegex(ValueError, "original project loader"):
                roles._project_roles(self.project)
            self.assertEqual(calls, 2)
            foreign.assert_not_called()

    def test_source_metadata_returns_original_snapshot_without_second_parse(self):
        from literate_ai.contracts import ProjectDefinition

        inputs = self.adapter_inputs(self.project)
        with self.scope() as scope:
            adapter = transaction._source_metadata_observation(
                self.project, scope, **inputs
            )
            parser = ProjectDefinition.from_dict.__func__
            original = parser.__code__

            def second_parser(*args, **kwargs):
                raise AssertionError("second project parser")

            try:
                parser.__code__ = second_parser.__code__
                snapshot, context = adapter.project_context()
                self.assertIs(snapshot, inputs["snapshot"])
                self.assertIs(context, inputs["context"])
            finally:
                parser.__code__ = original

    def test_source_metadata_retained_bindings_cannot_be_reassigned_or_deleted(self):
        inputs = self.adapter_inputs(self.project)
        with self.scope() as scope:
            adapter = transaction._source_metadata_observation(
                self.project, scope, **inputs
            )
            for name, value in (
                ("_snapshot", replace(inputs["snapshot"], content=b"{}")),
                ("_context", replace(inputs["context"], root=self.state)),
                ("manifest", replace(inputs["manifest"], content=b"{}")),
                ("root", self.state),
                ("owner", None),
            ):
                with self.subTest(binding=name):
                    with self.assertRaises(AttributeError):
                        setattr(adapter, name, value)
                    with self.assertRaises(AttributeError):
                        delattr(adapter, name)
            self.assertIs(adapter.project_context()[0], inputs["snapshot"])
            with self.assertRaisesRegex(TypeError, "reinitialized"):
                adapter.__init__(self.project, scope, **inputs)
            self.assertIs(adapter.project_context()[0], inputs["snapshot"])

    def test_source_metadata_refuses_foreign_context_property_before_dispatch(self):
        from literate_ai.projects import ProjectContext

        inputs = self.adapter_inputs(self.project)
        foreign = mock.Mock(side_effect=AssertionError("foreign manifest property"))
        with self.scope() as scope:
            with mock.patch.object(ProjectContext, "manifest_path", property(foreign)):
                with self.assertRaisesRegex(ValueError, "metadata adapter changed"):
                    transaction._source_metadata_observation(
                        self.project, scope, **inputs
                    )
                foreign.assert_not_called()

    def test_source_metadata_snapshot_does_not_replace_fresh_manifest_check(self):
        inputs = self.adapter_inputs(self.project)
        with self.assertRaisesRegex(ValueError, "manifest changed"):
            with self.scope() as scope:
                adapter = transaction._source_metadata_observation(
                    self.project, scope, **inputs
                )
                inputs["manifest"].path.write_bytes(inputs["manifest"].content + b"\n")
                adapter.project_context()

    def test_source_json_accounting_cannot_be_shared_between_project_roots(self):
        budget = RetainedCargoInputBudget(2, 5, 1024, 2048)
        first_inputs = self.adapter_inputs(self.project)
        (self.state / "literate.project.json").write_bytes(
            first_inputs["manifest"].content
        )
        second_inputs = self.adapter_inputs(self.state)
        with self.assertRaisesRegex(ValueError, "decoded canonical metadata"):
            with self.scope(budget) as scope:
                first = transaction._SourceMetadataObservation(
                    self.project, scope, **first_inputs
                )
                second = transaction._SourceMetadataObservation(
                    self.state, scope, **second_inputs
                )
                self.assertEqual(
                    first.json_value(b'{"state":"wrapped"}', "input.json"),
                    {"state": "wrapped"},
                )
                second.json_value(b'{"state":"wrapped"}', "input.json")

    def test_original_canonical_file_ceiling_is_not_increased(self):
        path = self.project / "metadata-input"
        path.write_bytes(b"x" * 1025)
        with self.assertRaises(ValueError):
            with self.scope():
                refresh._file(path, maximum_bytes=1024)

    def test_global_file_ceiling_applies_before_payload_read(self):
        path = self.project / "metadata-input"
        path.write_bytes(b"x" * 4097)
        budget = RetainedCargoInputBudget(32, 4096, 4096, 1024**2 // 8)
        with mock.patch.object(
            orchestration.os, "fdopen", side_effect=AssertionError("payload read")
        ):
            with self.assertRaises(ValueError):
                with self.scope(budget):
                    refresh._file(path)

    def test_cached_bytes_do_not_increase_a_later_smaller_read_limit(self):
        path = self.project / "metadata-input"
        path.write_bytes(b"x" * 64)
        with self.assertRaisesRegex(ValueError, "original read ceiling"):
            with self.scope():
                refresh._file(path)
                refresh._file(path, maximum_bytes=32)

    def test_source_change_is_not_reinterpreted_as_current_metadata(self):
        path = self.project / "metadata-input"
        path.write_bytes(b"original\n")
        with self.assertRaises(ValueError):
            with self.scope():
                refresh._file(path)
                path.write_bytes(b"changed\n")
                refresh._file(path)
        self.assertEqual(path.read_bytes(), b"changed\n")

    def test_git_command_uses_global_output_limit(self):
        self.init_git(commit=True)
        budget = RetainedCargoInputBudget(128, 4096, 4096, 128 * 4096)
        run = orchestration.run_bounded_process
        limits = []

        def record(*args, **kwargs):
            limits.append(kwargs["stdout_limit_bytes"])
            return run(*args, **kwargs)

        with self.scope(budget):
            with mock.patch.object(orchestration, "run_bounded_process", record):
                self.assertTrue(orchestration._git(self.project, "rev-parse", "HEAD"))
        self.assertEqual(limits, [4096])

    def test_actual_git_includes_are_observed_as_inputs(self):
        self.init_git()
        config = self.state / "included.gitconfig"
        config.write_bytes(b"[example]\nvalue = original\n")
        self.git("config", "include.path", str(config))
        with self.assertRaises(ValueError):
            with self.scope() as scope:
                observe_layout_git_controls(self.project)
                self.assertIn(config, scope._ledger.cache)
                config.write_bytes(b"[example]\nvalue = changed\n")
        self.assertIn(b"changed", config.read_bytes())

    def test_repeated_real_git_reads_charge_actual_empty_stderr_under_original_budget(
        self,
    ):
        self.init_git(commit=True)
        budget = RetainedCargoInputBudget(128, 4096, 4096, 32768)
        with self.scope(budget) as scope:
            size = 0
            for _ in range(32):
                size += len(orchestration._git(self.project, "rev-parse", "HEAD"))
            self.assertEqual(scope._ledger.bytes, size)
            self.assertEqual(scope.budget, budget)

    def test_successful_git_stderr_bytes_are_charged_and_channel_limits_stay_fixed(
        self,
    ):
        budget = RetainedCargoInputBudget(128, 4096, 4096, 32768)
        with self.scope(budget) as scope:
            with mock.patch.object(
                orchestration,
                "run_bounded_process",
                return_value=BoundedProcessResult(0, b"out", b"diagnostic"),
            ) as run:
                self.assertEqual(orchestration._git(self.project, "status"), b"out")
            self.assertEqual(scope._ledger.bytes, len(b"outdiagnostic"))
            self.assertEqual(run.call_args.kwargs["stdout_limit_bytes"], 4096)
            self.assertEqual(run.call_args.kwargs["stderr_limit_bytes"], 4096)

    def test_missing_canonical_git_usage_receipt_refuses_without_refund(self):
        budget = RetainedCargoInputBudget(128, 4096, 4096, 32768)
        with self.assertRaisesRegex(ValueError, "channel usage"):
            with self.scope(budget) as scope:
                with mock.patch.object(orchestration, "_raw_git", return_value=b"out"):
                    orchestration._git(self.project, "status")
        self.assertEqual(scope._ledger.bytes, 8192)

    def test_git_metadata_cannot_borrow_a_larger_independent_file_limit(self):
        self.init_git(commit=True)
        path = self.project / ".git/index"
        original = path.read_bytes()
        path.write_bytes(original + b" " * (128 * 1024))
        budget = RetainedCargoInputBudget(1024, 8192, 65536, 16 * 1024**2)
        with self.assertRaises(ValueError):
            with self.scope(budget):
                observe_layout_git_controls(self.project)
        self.assertGreater(path.stat().st_size, 65536)

    def test_optional_git_absence_stays_bound(self):
        with self.assertRaises(ValueError):
            with self.scope():
                observed = observe_layout_git_controls(self.project)
                self.assertIsNone(observed.git_root)
                (self.project / ".git").mkdir()

    def test_native_child_registry_absence_stays_bound(self):
        with self.assertRaises(ValueError):
            with self.scope():
                self.assertEqual(_native_project_roots(load_project(self.project)), ())
                (self.project / ".literate/native-projects.json").write_text("{}")

    def test_registered_child_manifest_uses_shared_canonical_reader(self):
        child = self.project / ".literate/native-projects/child"
        ProjectConfigurationStore(child).create(_definition(project_id="child"))
        manifest = child / "literate.project.json"
        # Child manifests retain their project reader's 1 MiB ceiling, rather
        # than borrowing the smaller conversion-state file ceiling.
        manifest.write_bytes(manifest.read_bytes() + b" " * (300 * 1024))
        project = load_project(self.project)
        register_native_project(project, child)
        expected = _native_project_roots(project)
        with self.scope() as scope:
            with mock.patch.object(
                Path, "read_bytes", side_effect=AssertionError("unbounded child read")
            ):
                self.assertEqual(_native_project_roots(project), expected)
            self.assertIn(child / "literate.project.json", scope._ledger.cache)

    def test_conversion_absence_is_an_observed_input(self):
        path = self.project / ".literate/conversion-authority.json"
        path.unlink()
        with self.assertRaises(ValueError):
            with self.scope():
                self.assertIsNone(
                    FilesystemConversionAuthorityStore(self.project).load_optional()
                )
                path.write_bytes(b"{}\n")

    def test_canonical_migration_history_shares_scope_and_closing_checks(self):
        store = FilesystemConversionAuthorityStore(self.project)
        previous = store.load_optional()
        identity = canonical_identity({"fixture": "migration"}).uri
        record = {
            "schema": migration.RECORD_SCHEMA,
            "previous_state": previous.to_dict(),
            "from_project_id": previous.project_id,
            "to_project_id": "renamed",
            "project_definition_identity": identity,
            "source_identity": identity,
            "historical_evidence": {"fixture": identity},
            "authority_identity": identity,
        }
        record_identity = canonical_identity(record)
        path = self.project / migration.HISTORY / (record_identity.digest + ".json")
        path.parent.mkdir()
        path.write_bytes(canonical_json_bytes(record) + b"\n")
        expected = replace(
            previous,
            project_id="renamed",
            identity_migration_identity=record_identity,
        )
        store.path.write_bytes(canonical_json_bytes(expected.to_dict()) + b"\n")
        self.assertEqual(store.load_optional(), expected)
        with self.scope() as scope:
            self.assertEqual(store.load_optional(), expected)
            self.assertIn(path, scope._ledger.cache)
        with self.assertRaises(ValueError):
            with self.scope():
                self.assertEqual(store.load_optional(), expected)
                path.write_bytes(b"{}\n")

    def test_ended_context_copy_refuses_instead_of_falling_back(self):
        with self.scope():
            context = copy_context()
        with mock.patch.object(
            refresh, "_raw_file", side_effect=AssertionError("legacy fallback")
        ):
            with self.assertRaisesRegex(ValueError, "ended"):
                context.run(refresh._file, self.project / "literate.project.json")
        self.assertIsNone(reads.current_role_observation())

    def test_copied_context_cannot_borrow_shared_budget_on_another_thread(self):
        messages = []
        with self.scope():
            context = copy_context()

            def read():
                try:
                    context.run(refresh._file, self.project / "literate.project.json")
                except ValueError:
                    messages.append("refused")

            worker = threading.Thread(target=read)
            worker.start()
            worker.join(10)
            self.assertFalse(worker.is_alive())
        self.assertEqual(messages, ["refused"])

    def test_decoded_project_records_share_entry_allowance(self):
        budget = RetainedCargoInputBudget(64, 64, 4 * 1024**2, 64 * 1024**2)
        with self.assertRaises(ValueError):
            with self.scope(budget):
                ProjectConfigurationStore(self.project).read()

    def test_nested_scope_does_not_reset_the_original_allowance(self):
        with self.scope():
            with self.assertRaisesRegex(ValueError, "nested"):
                with self.scope():
                    self.fail("nested quota reset")

    def test_default_readers_still_use_default_limits_outside_scope(self):
        path = self.project / "metadata-input"
        path.write_bytes(b"x" * 8192)
        self.assertEqual(len(refresh._file(path).content), 8192)
        self.assertIsNone(reads.current_role_observation())
