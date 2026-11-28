"""Current consumer joins with real file/runtime custody, synthetic review facts.

No provider history, complete consumer execution or public admission is claimed.
The structural source/wheel export fixture does not contain installed packages.
"""

import hashlib
import json
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters import retained_python_plan as subject
from literate_ai.adapters.builders.python import discover_python_toolchain
from literate_ai.adapters.retained_python_interpreter import (
    observed_retained_python_interpreter,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.projects import PinnedInputClosure
from tests.critical import test_retained_python_workspace_plan as plans
from tests.support import fixtures_test_retained_library_binding as bindings


def blob(content):
    return BlobRef(
        hashlib.sha256(content).hexdigest(), len(content), media_type="application/json"
    )


class RetainedPythonConsumerInputsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # The original native probe is outside every read-only operation.
        cls.runtime = discover_python_toolchain(pinned_command=sys.executable)

    def setUp(self):
        runtime = ContentIdentity.parse_uri(self.runtime.identity)
        plan = plans.RetainedPythonWorkspacePlanTests().plan()
        self.plan = replace(
            plan,
            interpreter_identity=runtime,
            gate_policy=replace(plan.gate_policy, toolchains=(runtime,)),
        )
        self.content = canonical_json_bytes(self.plan.to_dict())
        self.binding = self.bind(self.content)
        self.root = Path(self.enterContext(tempfile.TemporaryDirectory())).resolve()
        self.marker = self.root / "reviewed-consumer.json"
        self.marker.write_bytes(self.content)
        custody = PinnedInputClosure(
            maximum_files=1,
            maximum_file_bytes=1024**2,
            maximum_total_bytes=1024**2,
        )
        custody.pin(self.marker, boundary=self.root, label=self.marker.name)
        self.current = subject.RetainedPythonConsumerInputs(
            self.plan.importer_project_id,
            self.binding.identity,
            self.binding.source_store_id,
            self.plan.wrapper_component,
            self.plan.harness_inventory,
            self.plan.source_scope_identity,
            self.plan.test_inventory,
            self.plan.gate_policy,
            self.plan.interpreter_identity,
            self.plan.target_identity,
            self.plan.environment_identity,
            custody.require_unchanged,
        )

    def bind(self, content, *, plan=None):
        plan = self.plan if plan is None else plan
        return replace(
            bindings.RetainedLibraryBindingTests().fixture(),
            exports=plan.exports,
            destinations=plan.destinations,
            workspace_plan=blob(content),
        )

    def observing(self):
        return observed_retained_python_interpreter(
            self.runtime.command,
            expected_identity=self.current.interpreter_identity,
            maximum_file_bytes=256 * 1024**2,
            maximum_metadata_bytes=1024**3,
        )

    def verify(self, observed, *, content=None, binding=None, current=None, **options):
        return subject.verify_retained_python_consumer_inputs(
            self.content if content is None else content,
            self.binding if binding is None else binding,
            current=self.current if current is None else current,
            interpreter_observation=observed,
            max_bytes=options.get("max_bytes", 1024**2),
        )

    def test_original_complete_consumer_and_both_profiles_join_without_effects(self):
        before = sorted(self.root.iterdir())
        with (
            self.observing() as observed,
            mock.patch("subprocess.Popen", side_effect=AssertionError("native tool")),
            mock.patch.object(Path, "write_bytes", side_effect=AssertionError("write")),
            mock.patch.object(Path, "mkdir", side_effect=AssertionError("mkdir")),
        ):
            result = self.verify(observed)
            self.assertEqual(result, self.plan)
            self.assertEqual({m.profile for m in result.mounts}, {"source", "wheel"})
            self.assertEqual(len(result.gate_policy.commands), 3)
            self.assertEqual(len(result.destinations), 3)
            self.assertFalse(hasattr(result, "qualified"))
        self.assertEqual(sorted(self.root.iterdir()), before)

    def test_rehashed_current_inventory_runtime_scope_and_full_gate_drift_refuse(self):
        changes = {
            "wrapper_component": "components/other",
            "harness_inventory": blob(b"different harness inventory"),
            "source_scope_identity": canonical_identity("different source"),
            "test_inventory": blob(b"no original tests"),
            "gate_policy": replace(
                self.plan.gate_policy, commands=self.plan.gate_policy.commands[:1]
            ),
            "target_identity": canonical_identity("foreign target"),
            "environment_identity": canonical_identity("ambient environment"),
        }
        with self.observing() as observed:
            for name, value in changes.items():
                with self.subTest(field=name):
                    plan = replace(self.plan, **{name: value})
                    content = canonical_json_bytes(plan.to_dict())
                    binding = self.bind(content, plan=plan)
                    current = replace(
                        self.current, reviewed_binding_identity=binding.identity
                    )
                    with self.assertRaisesRegex(
                        ValueError, "authority-mismatch:" + name
                    ):
                        self.verify(
                            observed, content=content, binding=binding, current=current
                        )

    def test_candidate_review_or_store_substitution_refuses_before_plan_parse(self):
        with self.observing() as observed:
            for binding in (
                replace(self.binding, policy_identity=canonical_identity("foreign")),
                replace(self.binding, source_store_id="other-store"),
            ):
                with (
                    self.subTest(binding=binding),
                    mock.patch.object(
                        subject,
                        "reopen_retained_python_plan",
                        side_effect=AssertionError("unreviewed candidate parsed"),
                    ),
                    self.assertRaisesRegex(ValueError, "importer-authority-mismatch"),
                ):
                    self.verify(observed, binding=binding)

    def test_exact_bytes_and_finite_limit_refuse_before_json_decode(self):
        with self.observing() as observed:
            with mock.patch.object(subject.json, "loads", side_effect=AssertionError):
                for content, limit in (
                    (self.content + b" ", 1024**2),
                    (self.content, len(self.content) - 1),
                    (self.content, True),
                    (self.content, 16 * 1024**2 + 1),
                ):
                    with (
                        self.subTest(limit=limit),
                        self.assertRaisesRegex(ValueError, "plan-bytes-refused"),
                    ):
                        self.verify(observed, content=content, max_bytes=limit)
            noncanonical = json.dumps(self.plan.to_dict(), indent=2).encode()
            binding = self.bind(noncanonical)
            with self.assertRaisesRegex(ValueError, "plan-invalid"):
                self.verify(
                    observed,
                    content=noncanonical,
                    binding=binding,
                    current=replace(
                        self.current, reviewed_binding_identity=binding.identity
                    ),
                )

    def test_rehashed_binding_cannot_redirect_complete_export_destinations(self):
        plan = replace(
            self.plan,
            destinations=tuple(
                (key, path + "-other") for key, path in self.plan.destinations
            ),
        )
        content = canonical_json_bytes(plan.to_dict())
        binding = replace(self.binding, workspace_plan=blob(content))
        with (
            self.observing() as observed,
            self.assertRaisesRegex(ValueError, "binding-plan-mismatch"),
        ):
            self.verify(
                observed,
                content=content,
                binding=binding,
                current=replace(
                    self.current, reviewed_binding_identity=binding.identity
                ),
            )

    def closing_control(self, *, refuse):
        original = json.loads
        with self.observing() as observed:

            def change_then_decode(content):
                self.marker.write_bytes(b"concurrent original consumer change")
                if refuse:
                    raise ValueError("candidate refused")
                return original(content)

            with mock.patch.object(subject.json, "loads", change_then_decode):
                with self.assertRaises(ValueError) as caught:
                    self.verify(observed)
            self.assertNotIn("plan-invalid", str(caught.exception))
            self.assertEqual(
                self.marker.read_bytes(), b"concurrent original consumer change"
            )

    def test_original_native_custody_closes_after_successful_plan_parse(self):
        self.closing_control(refuse=False)

    def test_original_native_custody_closes_after_candidate_refusal(self):
        self.closing_control(refuse=True)

    def test_lookalike_native_tool_and_expired_observation_cannot_grant_check(self):
        fake = SimpleNamespace(
            identity=self.runtime.identity,
            command=self.runtime.command,
            require_unchanged=lambda: None,
        )
        for observed in (fake, self.runtime):
            with (
                self.subTest(observed=type(observed)),
                self.assertRaisesRegex(TypeError, "original-interpreter-required"),
            ):
                self.verify(observed)
        with self.observing() as observed:
            pass
        with self.assertRaisesRegex(ValueError, "observation-ended"):
            self.verify(observed)

    def test_missing_custody_or_interpreter_identity_from_candidate_refuses(self):
        with self.assertRaisesRegex(TypeError, "consumer-custody-required"):
            replace(self.current, require_unchanged=None)
        foreign = canonical_identity("foreign candidate interpreter")
        plan = replace(
            self.plan,
            interpreter_identity=foreign,
            gate_policy=replace(self.plan.gate_policy, toolchains=(foreign,)),
        )
        content = canonical_json_bytes(plan.to_dict())
        binding = self.bind(content, plan=plan)
        with (
            self.observing() as observed,
            self.assertRaisesRegex(
                ValueError, "consumer-authority-mismatch:gate_policy"
            ),
        ):
            self.verify(
                observed,
                content=content,
                binding=binding,
                current=replace(
                    self.current, reviewed_binding_identity=binding.identity
                ),
            )

    def test_changed_current_selection_cannot_reuse_original_runtime_observation(self):
        foreign = canonical_identity("different current interpreter selection")
        current = replace(
            self.current,
            interpreter_identity=foreign,
            gate_policy=replace(self.current.gate_policy, toolchains=(foreign,)),
        )
        with (
            self.observing() as observed,
            mock.patch.object(
                subject, "reopen_retained_python_plan", side_effect=AssertionError
            ),
            self.assertRaisesRegex(ValueError, "interpreter-identity-mismatch"),
        ):
            self.verify(observed, current=current)
