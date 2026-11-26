"""Portable guard-protocol counts; no producer qualification is represented.

Derivation and delegated guard implementations are explicitly modeled. The
original materialization/current guard orchestration runs, including both live
reader callbacks. The separate thirteen receiving controls retain real archive,
namespace, and package validation; none is replaced or skipped by these controls.
"""

import hashlib
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai import projects
from literate_ai.adapters import native_root_qualified_provider as bridge
from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.retained_cargo_import_v2 import RetainedCargoCurrentInputsV2
from literate_ai.adapters.retained_cargo_materialization_v2 import (
    RetainedCargoMaterializationV2,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_root_continuation import (
    NativeRootQualifiedDependencyBinding,
)
from literate_ai.contracts.repositories import RepositoryBuildCommand


def _record(label, **fields):
    return SimpleNamespace(identity=canonical_identity(label), **fields)


class QualifiedProviderOperationProtocolTests(unittest.TestCase):
    def setUp(self):
        self.events = []
        self.frames = []
        self.reads = 0
        self.on_read = None
        self.failure_phase = None
        self.refusal = RuntimeError("original delegated custody refusal")
        reviewed = SimpleNamespace(
            require_unchanged=lambda: self.events.append("reviewed"),
            _captured_identity=lambda: canonical_identity("reviewed"),
        )
        self.plan = _record("plan")
        qualification = _record("qualification")
        revision = canonical_identity("provider")
        self.provider = SimpleNamespace(
            require_unchanged=self.provider_guard,
            authority=SimpleNamespace(lock=_record("lock")),
            promotion=SimpleNamespace(qualification_lifecycle_result=qualification),
            current_generation_closure=SimpleNamespace(to_dict=lambda: {"closure": 1}),
            oracle=_record("oracle"),
            current_profile=_record("profile"),
            current_driver=_record("driver"),
            current_recipes={revision: _record("recipe")},
            current_commands={revision: _record("command")},
            current_gates=(RepositoryBuildCommand("gate", ("modeled",)),),
            current_verifier_identity=canonical_identity("verifier"),
            current_policy_identity=canonical_identity("policy"),
            reviewed_binding_identity=canonical_identity("reviewed-binding"),
            importer_project_id="consumer",
            configured_store_id="reviewed-store",
            current_cargo_identity=canonical_identity("cargo"),
            current_rustc_identity=canonical_identity("rustc"),
        )
        # Nominal instances are protocol placeholders under patched derivation;
        # this deliberately does not exercise or claim receiving admission.
        self.current = object.__new__(RetainedCargoCurrentInputsV2)
        object.__setattr__(self.current, "reviewed", reviewed)
        object.__setattr__(self.current, "current", self.provider)
        packages = tuple(
            SimpleNamespace(
                root=Path("modeled") / str(index),
                files=(DirectoryExportFile("source/lib.rs", b"modeled", 0o644),),
                directories=(),
                nodes=(),
                require_unchanged=lambda index=index: self.package_guard(index),
            )
            for index in range(2)
        )
        payload = b"modeled immutable export"
        blob = BlobRef(hashlib.sha256(payload).hexdigest(), len(payload))
        exports = (_record("export", blob=blob),)
        receipts = (_record("receipt"),)
        source = _record("source", provenance=_record("provenance"))
        node = _record(
            "node",
            source_generation=_record("generation"),
            source_output=source,
            build_evidence=_record("build"),
            acceptance_evidence=receipts[0],
        )
        product = _record(
            "product", import_surface=_record("surface"), native_layout=None
        )
        lifecycle = _record(
            "lifecycle",
            root_integration=_record("root-integration"),
            native_root_execution=None,
        )
        run = _record("run")
        binding = NativeRootQualifiedDependencyBinding(
            revision,
            receipts[0].identity,
            product.identity,
            source.provenance.identity,
            (exports[0].identity,),
            canonical_identity("target"),
            (canonical_identity("toolchain"),),
            (),
        )
        self.values = bridge._ProviderValues(
            binding,
            lifecycle,
            node,
            _record("build-plan"),
            product,
            receipts,
            exports,
            qualification,
            run,
        )
        self.materialized = object.__new__(RetainedCargoMaterializationV2)
        for name, value in {
            "current": self.current,
            "plan": self.plan,
            "packages": packages,
            "files": SimpleNamespace(
                reviewed=reviewed, require_authored_unchanged=self.authored_guard
            ),
            "scratch": SimpleNamespace(
                context=object(), require_unchanged=self.namespace_guard
            ),
            "capture": SimpleNamespace(
                run=run,
                exports=_record("export-set"),
                acceptances=receipts,
                blobs=((blob, payload),),
                verified_lifecycle=lifecycle,
            ),
            "_read_current": self.read_current,
        }.items():
            object.__setattr__(self.materialized, name, value)
        original_materialization = RetainedCargoMaterializationV2.require_unchanged
        original_current = RetainedCargoCurrentInputsV2.require_unchanged

        def materialization_guard(owner):
            self.events.append("materialization-entry")
            self.frames.append(projects._PROJECT_CONFIGURATION_PARSES.get())
            original_materialization(owner)
            self.events.append("materialization-exit")

        def current_guard(owner):
            self.events.append("current")
            original_current(owner)

        def pure_preflight(owner, *, max_plan_bytes):
            self.events.append("pure-preflight")
            return self.plan

        def modeled_derivation(owner):
            owner.current._preflight_values(max_plan_bytes=1)
            return self.values

        self.enterContext(
            mock.patch.object(
                RetainedCargoMaterializationV2,
                "require_unchanged",
                materialization_guard,
            )
        )
        self.enterContext(
            mock.patch.object(
                RetainedCargoCurrentInputsV2, "require_unchanged", current_guard
            )
        )
        self.enterContext(
            mock.patch.object(
                RetainedCargoCurrentInputsV2, "_preflight_values", pure_preflight
            )
        )
        self.enterContext(mock.patch.object(bridge, "_values", modeled_derivation))

    def reset_counts(self):
        self.events.clear()
        self.frames.clear()
        self.reads = 0

    def read_current(self):
        self.reads += 1
        self.events.append("foreign-reader")
        if self.on_read is not None:
            self.on_read(self.reads)
        return self.current

    def provider_guard(self):
        self.events.append("provider")
        if self.failure_phase in {"promotion", "tool"}:
            raise self.refusal

    def namespace_guard(self):
        self.events.append("namespace")
        if self.failure_phase == "namespace":
            raise self.refusal

    def authored_guard(self):
        self.events.append("source")
        if self.failure_phase == "source":
            raise self.refusal

    def package_guard(self, index):
        self.events.append(("package", index))
        if self.failure_phase == "package":
            raise self.refusal

    def assert_operation_counts(self, operations=1):
        self.assertEqual(self.events.count("materialization-entry"), operations * 2)
        self.assertEqual(self.events.count("materialization-exit"), operations * 2)
        self.assertEqual(self.events.count("foreign-reader"), operations * 2)
        self.assertEqual(self.events.count("current"), operations * 4)
        self.assertEqual(self.events.count("provider"), operations * 4)
        self.assertEqual(self.events.count("pure-preflight"), operations)
        # Each materialization brackets its reader with source/namespace guards.
        self.assertEqual(self.events.count("source"), operations * 4)
        self.assertEqual(self.events.count("namespace"), operations * 4)
        # Only the original CurrentInputs guard reads reviewed bytes here:
        # identity projection must not add another guarded reviewed.identity.
        self.assertEqual(self.events.count("reviewed"), operations * 8)
        for index in range(len(self.materialized.packages)):
            self.assertEqual(self.events.count(("package", index)), operations * 3)
        self.assertEqual(self.events[-2:], [("package", 0), ("package", 1)])

    def test_factory_admission_is_one_complete_entry_exit_bracket(self):
        with bridge.hold_native_root_qualified_provider(self.materialized):
            self.assert_operation_counts()

    def test_projection_checks_once_and_returned_fields_are_inert_data(self):
        with bridge.hold_native_root_qualified_provider(self.materialized) as held:
            self.reset_counts()
            view = held.data_projection()
            self.assert_operation_counts()
            before = list(self.events)
            self.assertIs(view.binding, self.values.binding)
            self.assertIs(view.lifecycle, self.values.lifecycle)
            self.assertIs(view.root_node, self.values.node)
            self.assertIs(view.source_output, self.values.node.source_output)
            self.assertIs(view.build_plan, self.values.build_plan)
            self.assertIs(view.product, self.values.product)
            self.assertIs(view.accepted_receipts, self.values.receipts)
            self.assertIs(view.exports, self.values.exports)
            self.assertEqual(self.events, before)
            self.assertFalse(hasattr(view, "require_current"))
            with self.assertRaises(ValueError):
                with bridge.hold_native_root_qualified_provider(view):
                    self.fail("inert projection restored namespace ownership")

    def test_every_independent_getter_still_performs_fresh_checks(self):
        with bridge.hold_native_root_qualified_provider(self.materialized) as held:
            for name in (
                "binding",
                "lifecycle",
                "root_node",
                "source_output",
                "build_plan",
                "product",
                "accepted_receipts",
                "exports",
                "qualification_result",
                "run",
                "root_integration",
            ):
                with self.subTest(getter=name):
                    self.reset_counts()
                    getattr(held, name)
                    self.assert_operation_counts()

    def test_byte_read_retains_fresh_before_and_after_operations(self):
        with bridge.hold_native_root_qualified_provider(self.materialized) as held:
            view = held.data_projection()
            self.reset_counts()
            payload = held.read_artifact_blob(view.exports[0].blob)
            self.assertEqual(payload, b"modeled immutable export")
            self.assert_operation_counts(operations=2)

    def test_each_operation_isolates_parse_templates_and_restores_ambient_scope(self):
        with projects.read_only_project_configuration_parses(isolated=True):
            ambient = projects._PROJECT_CONFIGURATION_PARSES.get()
            with bridge.hold_native_root_qualified_provider(self.materialized) as held:
                self.assertIs(projects._PROJECT_CONFIGURATION_PARSES.get(), ambient)
                self.reset_counts()
                held.data_projection()
                first = self.frames[0]
                self.assertIsNot(first, ambient)
                self.assertTrue(all(frame is first for frame in self.frames))
                self.assertIs(projects._PROJECT_CONFIGURATION_PARSES.get(), ambient)
                self.reset_counts()
                held.data_projection()
                self.assertIsNot(self.frames[0], first)
                self.assertIsNot(self.frames[0], ambient)

    def test_public_preflight_keeps_original_guard_bracket(self):
        self.reset_counts()
        self.assertIs(self.current.preflight(max_plan_bytes=1), self.plan)
        self.assertEqual(self.events.count("current"), 2)
        self.assertEqual(self.events.count("provider"), 2)
        self.assertEqual(self.events.count("pure-preflight"), 1)
        self.assertLess(
            self.events.index("current"), self.events.index("pure-preflight")
        )
        self.assertGreater(
            len(self.events) - 1 - self.events[::-1].index("current"),
            self.events.index("pure-preflight"),
        )

    def test_public_preflight_preserves_original_pure_validation_error(self):
        with mock.patch.object(
            RetainedCargoCurrentInputsV2, "_preflight_values", side_effect=self.refusal
        ):
            with self.assertRaises(RuntimeError) as caught:
                self.current.preflight(max_plan_bytes=1)
        self.assertIs(caught.exception, self.refusal)
        self.assertEqual(self.events.count("current"), 1)

    def test_all_original_delegated_refusals_stay_terminal_after_latest_reader(self):
        for phase in ("source", "promotion", "tool", "namespace", "package"):
            with self.subTest(phase=phase):
                self.failure_phase = None
                self.on_read = None
                with bridge.hold_native_root_qualified_provider(
                    self.materialized
                ) as held:
                    self.reset_counts()

                    def change(index, phase=phase):
                        if index == 2:
                            self.failure_phase = phase

                    self.on_read = change
                    with self.assertRaises(RuntimeError) as caught:
                        held.data_projection()
                    self.assertIs(caught.exception, self.refusal)
                    self.assertEqual(self.reads, 2)
                    if phase == "package":
                        last_reader = (
                            len(self.events)
                            - 1
                            - self.events[::-1].index("foreign-reader")
                        )
                        package_failure = len(self.events) - 1
                        self.assertGreater(package_failure, last_reader)
                        self.assertEqual(self.events[-1], ("package", 0))
                self.failure_phase = None
                self.on_read = None

    def test_closing_field_gate_and_map_seals_follow_latest_foreign_callback(self):
        for field in ("configured_store_id", "current_gates", "current_commands"):
            with self.subTest(field=field):
                self.on_read = None
                original = getattr(self.provider, field)
                if field == "configured_store_id":
                    changed = "changed-store"
                elif field == "current_gates":
                    changed = tuple(list(original))
                else:
                    changed = dict(original)
                with bridge.hold_native_root_qualified_provider(
                    self.materialized
                ) as held:
                    self.reset_counts()

                    def change(index, field=field, changed=changed):
                        if index == 2:
                            setattr(self.provider, field, changed)

                    self.on_read = change
                    try:
                        with self.assertRaisesRegex(ValueError, "binding_changed"):
                            held.data_projection()
                    finally:
                        setattr(self.provider, field, original)
                        self.on_read = None

    def test_prior_projection_is_not_a_cached_currentness_success(self):
        with bridge.hold_native_root_qualified_provider(self.materialized) as held:
            view = held.data_projection()
            self.failure_phase = "tool"
            try:
                with self.assertRaises(RuntimeError) as caught:
                    held.data_projection()
                self.assertIs(caught.exception, self.refusal)
                self.assertIs(view.binding, self.values.binding)
            finally:
                self.failure_phase = None

    def test_in_place_gate_drift_is_recomputed_after_closing_callback(self):
        gate = self.provider.current_gates[0]
        original = gate.argv
        with bridge.hold_native_root_qualified_provider(self.materialized) as held:
            self.reset_counts()

            def change(index):
                if index == 2:
                    object.__setattr__(gate, "argv", ("different-modeled-gate",))

            self.on_read = change
            try:
                with self.assertRaisesRegex(ValueError, "binding_changed"):
                    held.data_projection()
            finally:
                object.__setattr__(gate, "argv", original)
                self.on_read = None

    def test_final_package_scan_follows_original_run_closing_callback(self):
        run_calls = []

        def run_guard():
            run_calls.append(True)
            self.events.append("original-run")
            if len(run_calls) == 2:
                self.failure_phase = "package"

        original = SimpleNamespace(require_current=run_guard)
        with mock.patch.object(
            bridge, "current_native_root_run", return_value=original
        ):
            with bridge.hold_native_root_qualified_provider(self.materialized) as held:
                self.reset_counts()
                run_calls.clear()
                try:
                    with self.assertRaises(RuntimeError) as caught:
                        held.data_projection()
                    self.assertIs(caught.exception, self.refusal)
                    self.assertEqual(self.events[-2:], ["original-run", ("package", 0)])
                finally:
                    self.failure_phase = None
