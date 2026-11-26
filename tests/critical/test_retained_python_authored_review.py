"""Original review/retained-wrapper owners with an explicit authored codec.

Inert provider declarations remain synthetic. Inherited file controls exercise
real current configuration/byte/ancestry custody. Wrapper control performs the
existing actual conversion/parity fixture BEFORE read-only observation; neither
provider qualification nor native original-gate/consumer admission is claimed.
"""

import unittest
from unittest.mock import patch

from literate_ai.adapters import retained_python_authored as authored_plan
from literate_ai.adapters import retained_python_review as subject
from literate_ai.adapters.retained_python_plan import reopen_retained_python_plan
from literate_ai.adapters.retained_python_wrapper import (
    observed_retained_python_wrapper,
)
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.retained_python_authored import AuthoredRetainedPythonBinding
from tests.critical import test_authored_retained_cargo_binding as authored
from tests.critical import test_retained_python_review as original
from tests.critical import test_retained_python_wrapper as wrappers


def binding_for(source):
    fixture = authored.AuthoredRetainedCargoBindingTests("runTest")
    fixture.setUp()
    return AuthoredRetainedPythonBinding(
        source.importer_project_id,
        source.source_store_id,
        fixture.binding.provider_reference,
        fixture.binding.selected_run_identity,
        source.exports,
        source.workspace_plan,
        source.destinations,
    )


class AuthoredPythonReviewTests(original.RetainedPythonReviewedFilesTests):
    def setUp(self):
        super().setUp()
        self.source_binding = self.binding
        self.binding = binding_for(self.binding)
        content = canonical_json_bytes(self.binding.to_dict())
        self.documents["binding.json"] = content
        (self.root / "binding.json").write_bytes(content)
        self.arguments["reviewed_binding"] = original.blob(content)

    def read(self, **changes):
        return subject.read_authored_retained_python_review(
            self.root, **{**self.arguments, **changes}
        )

    def test_late_original_replacement_closes_on_success_and_candidate_refusal(self):
        decoder = authored_plan._reopen_authored_python_plan
        for refuse in (False, True):
            with self.subTest(refuse=refuse):

                def change(*args, refusal=refuse, **kwargs):
                    self.configuration.write_bytes(b"foreign configuration")
                    if refusal:
                        raise ValueError("candidate-refused")
                    return decoder(*args, **kwargs)

                before = original.serialize_project_configuration(
                    original.projects._definition()
                )
                self.configuration.write_bytes(before)
                with (
                    patch.object(
                        authored_plan,
                        "_reopen_authored_python_plan",
                        side_effect=change,
                    ),
                    self.assertRaisesRegex(
                        ValueError, "review-native-inputs-changed"
                    ) as caught,
                ):
                    self.read()
                self.assertNotIn("candidate-refused", str(caught.exception))
                self.assertEqual(
                    self.configuration.read_bytes(), b"foreign configuration"
                )

    def test_fixed_v1_source_reader_and_plan_decoder_refuse_authored_binding(self):
        with self.assertRaisesRegex(ValueError, "document-invalid"):
            subject.read_retained_python_review(self.root, **self.arguments)
        with self.assertRaisesRegex(ValueError, "plan-bytes-refused"):
            reopen_retained_python_plan(
                self.plan_bytes, self.binding, max_bytes=16 * 1024**2
            )
        source_bytes = canonical_json_bytes(self.source_binding.to_dict())
        (self.root / "binding.json").write_bytes(source_bytes)
        arguments = {**self.arguments, "reviewed_binding": original.blob(source_bytes)}
        source = subject.read_retained_python_review(self.root, **arguments)
        self.assertEqual(source.binding, self.source_binding)
        with self.assertRaisesRegex(ValueError, "document-invalid"):
            subject.read_authored_retained_python_review(self.root, **arguments)

    def test_explicit_authored_reader_refuses_mixed_and_unknown_versions(self):
        wire = self.binding.to_dict()
        for change in (
            {"schema": "literate-ai/authored-retained-python-binding@2"},
            {
                "qualification_identity": (
                    self.source_binding.qualification_identity.to_dict()
                )
            },
            {"provider_reference": {"schema": "unknown"}},
        ):
            content = canonical_json_bytes({**wire, **change})
            (self.root / "binding.json").write_bytes(content)
            with self.assertRaisesRegex(ValueError, "document-invalid"):
                self.read(reviewed_binding=original.blob(content))


class AuthoredPythonOriginalWrapperTests(unittest.TestCase):
    def test_same_original_wrapper_observation_preserves_authored_binding(self):
        fixture = wrappers.RetainedPythonWrapperTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        binding = binding_for(fixture.reviewed.binding)
        content = canonical_json_bytes(binding.to_dict())
        (fixture.root / "review/binding.json").write_bytes(content)
        reviewed = subject.read_authored_retained_python_review(
            fixture.root,
            reviewed_binding=original.blob(content),
            **fixture.read_arguments,
        )
        with (
            patch("subprocess.Popen", side_effect=AssertionError("read-only process")),
            observed_retained_python_wrapper(reviewed, budget=fixture.budget) as owner,
        ):
            self.assertIs(owner.reviewed, reviewed)
            self.assertEqual(owner.reviewed.binding, binding)
            self.assertEqual(
                owner.source_scope_identity, fixture.plan.source_scope_identity
            )
            owner.require_unchanged()
        with self.assertRaisesRegex(ValueError, "operation-ended"):
            owner.require_unchanged()
