"""Closed independent-review CLI routing; backend seam is explicitly a fixture."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import authored_qualification_receiving as receiving
from literate_ai.cli import retained_cargo_authored as authored
from literate_ai.cli.errors import CliFailure
from literate_ai.cli.retained_cargo_routing import retained_cargo_closed
from tests.critical import test_authored_qualification_receiving as fixture
from tests.critical import test_cli_retained_cargo_dispatch as dispatch


class ProducerReviewDispatchTests(unittest.TestCase):
    setUp = dispatch.RetainedCargoClosedDispatchTests.setUp
    args = dispatch.RetainedCargoClosedDispatchTests.args
    authored_options = dispatch.RetainedCargoClosedDispatchTests.authored_options
    assert_no_backend = dispatch.RetainedCargoClosedDispatchTests.assert_no_backend

    def options(self):
        return [
            "--producer-review",
            "review/producer.json",
            "--reviewed-producer-review",
            "sha256:" + "a" * 64,
            "--producer-review-size",
            "1024",
        ]

    def test_partial_review_selection_refuses_before_all_backends(self):
        for name in (
            "producer_review",
            "reviewed_producer_review",
            "producer_review_size",
        ):
            args = self.args(
                self.binding.to_dict(), extra=self.authored_options() + self.options()
            )
            setattr(args, name, None)
            self.assert_no_backend(args, error=CliFailure)

    def test_exact_review_operands_reach_authored_backend_unchanged(self):
        args = self.args(
            self.binding.to_dict(), extra=self.authored_options() + self.options()
        )
        marker = {"fixture": "closed dispatch only"}
        with patch.object(
            authored, "run_authored_retained_cargo", return_value=marker
        ) as backend:
            self.assertIs(retained_cargo_closed(args), marker)
        self.assertIs(backend.call_args.args[0], args)
        self.assertEqual(args.producer_review, "review/producer.json")
        self.assertEqual(args.producer_review_size, 1024)
        self.assertEqual(args.reviewed_producer_review, "sha256:" + "a" * 64)

    def test_source_v1_refuses_authored_review_before_any_backend(self):
        legacy = [
            "--gates",
            "gates.json",
            "--reviewed-gates",
            "sha256:" + "a" * 64,
            "--gate-size",
            "100",
            "--provider-id",
            "fixture",
        ]
        self.assert_no_backend(
            self.args(self.legacy.to_dict(), extra=legacy + self.options()),
            error=CliFailure,
        )


class ProducerReviewHandlerTests(unittest.TestCase):
    setUpClass = classmethod(
        fixture.AuthoredQualificationReceivingTests.setUpClass.__func__
    )
    setUp = fixture.AuthoredQualificationReceivingTests.setUp

    def arguments(self):
        return SimpleNamespace(
            project=str(self.importer.root),
            binding="review/binding.json",
            plan="review/plan.json",
            gate_policy="review/policy.json",
            tests="review/tests.json",
            store_id=self.importer.binding.evidence_store_id,
            producer_review="review/producer.json",
            reviewed_producer_review=self.importer.review_reference.identity,
            producer_review_size=self.importer.review_reference.size,
            provider_project=str(self.provider.fixture.root),
            provider_component=self.provider.request.component_root.relative_to(
                self.provider.fixture.root
            ).as_posix(),
            provider_profile="litai/qualification.json",
            provider_output_root=None,
            provider_flavor=list(self.provider.request.flavor_selectors),
            target=self.provider.request.target_name,
            model=None,
            retained_cargo_command="check",
            offline=False,
            sdk_cache=None,
            sdk_completion=None,
            sdk_completion_size=None,
            sdk_revocations=None,
            old_output_file_bytes=1024,
            old_output_total_bytes=4096,
        )

    def test_mismatched_approved_intent_refuses_before_provider_sdk_or_transport(self):
        for name, value in (
            ("model", "foreign-model"),
            ("provider_profile", "litai/foreign.json"),
            ("provider_output_root", "litai/qualification/foreign"),
        ):
            args = self.arguments()
            setattr(args, name, value)
            with self.subTest(name=name):
                with (
                    patch.object(authored, "discover_project") as provider,
                    patch.object(authored, "reopen_authored_sdk_inputs") as sdk,
                    patch.object(authored, "_archive") as transport,
                ):
                    with self.assertRaisesRegex(
                        ValueError, "reviewed-producer-selection-mismatch"
                    ):
                        authored.run_authored_retained_cargo(
                            args, binding_reference=self.importer.binding_reference
                        )
                    provider.assert_not_called()
                    sdk.assert_not_called()
                    transport.assert_not_called()

    def test_handler_holds_original_model_free_owner_until_backend_closes(self):
        original_port = authored._read_ports
        observed = []

        def port(operation, *args, **kwargs):
            if operation == "open":
                # Explicit fixture framework/review observation ports, while
                # retaining the actual original six-file/live read factory.
                kwargs.update(
                    reviewer=self.provider.planner.reviewer,
                    binding_resolver=self.provider.planner.binding_resolver,
                )
                return receiving.open_reviewed_authored_qualification_inputs(
                    *args, **kwargs
                )
            return original_port(operation, *args, **kwargs)

        def backend(root, *, provider_current, **kwargs):
            self.assertEqual(root, self.importer.root)
            self.assertIs(
                type(provider_current), receiving.ReviewedAuthoredQualificationInputs
            )
            receiving.require_reviewed_authored_qualification_inputs(provider_current)
            self.assertEqual(kwargs["producer_review_path"], "review/producer.json")
            self.assertEqual(
                kwargs["reviewed_producer"], self.importer.review_reference
            )
            self.assertEqual(
                provider_current.reviewed.identity, self.importer.reviewed().identity
            )
            observed.append(provider_current)
            return {"fixture": "provisioning backend not executed"}

        with (
            patch.object(authored, "_read_ports", side_effect=port),
            patch(
                "literate_ai.adapters.authored_qualification_planning.FilesystemAuthoredQualificationPlanner.plan",
                side_effect=AssertionError("coding planner forbidden"),
            ),
            patch.object(authored, "_archive", return_value=(b"", None)),
            patch.object(authored, "discover_cargo_toolchain", return_value=object()),
            patch.object(authored, "discover_rust_toolchain", return_value=object()),
            patch.object(
                authored,
                "provision_authored_retained_cargo_consumer",
                side_effect=backend,
            ),
        ):
            result = authored.run_authored_retained_cargo(
                self.arguments(), binding_reference=self.importer.binding_reference
            )
        self.assertEqual(result, {"fixture": "provisioning backend not executed"})
        self.assertEqual(len(observed), 1)
        with self.assertRaisesRegex(ValueError, "expired"):
            receiving.require_reviewed_authored_qualification_inputs(observed[0])

    def test_missing_review_refuses_without_provider_sdk_model_or_transport(self):
        args = self.arguments()
        args.producer_review = None
        args.reviewed_producer_review = None
        args.producer_review_size = None
        with (
            patch.object(authored, "discover_project") as provider,
            patch.object(authored, "reopen_authored_sdk_inputs") as sdk,
            patch.object(authored, "_archive") as archive,
            patch(
                "literate_ai.adapters.authored_qualification_planning.FilesystemAuthoredQualificationPlanner.plan"
            ) as planner,
        ):
            with self.assertRaisesRegex(
                ValueError, "independent-producer-review-required"
            ):
                authored.run_authored_retained_cargo(
                    args, binding_reference=self.importer.binding_reference
                )
            provider.assert_not_called()
            sdk.assert_not_called()
            archive.assert_not_called()
            planner.assert_not_called()
