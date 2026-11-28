"""SDK consent/order controls; acquisition is an explicit fixture boundary.

These tests establish refusal before acquisition and owner plumbing, not an SDK
build or generated native qualification. Native SDK service suites remain needed.
"""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.cli import authored_sdk as subject
from literate_ai.cli.dispatch import _parser
from literate_ai.cli.errors import CliFailure


class AuthoredSdkCliTests(unittest.TestCase):
    def setUp(self):
        self.snapshot = SimpleNamespace(
            authority=SimpleNamespace(
                lock=SimpleNamespace(
                    nodes=(
                        SimpleNamespace(
                            revision=SimpleNamespace(
                                repository_sources=("fixture-source",),
                                identity="fixture-revision",
                            )
                        ),
                    )
                )
            )
        )
        self.authority = SimpleNamespace(locked=self.snapshot)
        self.authority_reader = self.enterContext(
            patch.object(
                subject,
                "read_current_authored_qualification_authority",
                return_value=self.authority,
            )
        )
        self.recipes = self.enterContext(
            patch.object(
                subject, "select_native_sdk_recipes", return_value=("fixture-recipe",)
            )
        )
        self.acquisition = self.enterContext(
            patch.object(subject, "NativeSdkProjectAcquisition")
        )
        self.binding = self.enterContext(
            patch.object(subject, "resolve_standard_project_lifecycle_driver")
        )
        self.config = self.enterContext(
            patch.object(subject, "ProjectConfigurationStore")
        )
        self.project = SimpleNamespace(root="fixture-project")

    def test_no_locked_sdk_dependency_allocates_no_sdk_service(self):
        self.recipes.return_value = ()
        self.assertIsNone(
            subject.reopen_authored_sdk_inputs(
                self.project, object(), SimpleNamespace()
            )
        )
        self.acquisition.assert_not_called()
        self.binding.assert_not_called()
        self.config.assert_not_called()

    def test_offline_locked_sdk_refuses_before_acquisition_even_with_consent(self):
        with self.assertRaises(CliFailure) as failure:
            subject.reopen_authored_sdk_inputs(
                self.project,
                object(),
                SimpleNamespace(offline=True, allow_sdk_builds=True, sdk_cache="cache"),
            )
        self.assertEqual(
            failure.exception.code, "qualification.authored.offline_unsupported"
        )
        self.authority_reader.assert_not_called()
        self.recipes.assert_not_called()
        self.acquisition.assert_not_called()
        self.binding.assert_not_called()
        self.config.assert_not_called()

    def test_consumer_host_consent_does_not_authorize_sdk_builds(self):
        for acknowledged in (False, None):
            with (
                self.subTest(acknowledged=acknowledged),
                self.assertRaises(CliFailure) as failure,
            ):
                subject.prepare_authored_sdk(
                    self.project,
                    object(),
                    SimpleNamespace(
                        allow_host_execution=True,
                        allow_sdk_builds=acknowledged,
                        sdk_cache="cache",
                    ),
                )
            self.assertEqual(
                failure.exception.code, "native_sdk.host_build_not_acknowledged"
            )
        self.acquisition.assert_not_called()
        self.binding.assert_not_called()
        self.config.assert_not_called()

    def test_sdk_build_consent_requires_explicit_cache(self):
        with self.assertRaises(CliFailure) as failure:
            subject.prepare_authored_sdk(
                self.project, object(), SimpleNamespace(allow_sdk_builds=True)
            )
        self.assertEqual(failure.exception.code, "cli.usage")
        self.acquisition.assert_not_called()
        self.binding.assert_not_called()
        self.config.assert_not_called()

    def test_read_only_route_requires_independently_selected_completion(self):
        for options in (
            {},
            {"sdk_completion": "sha256:" + "a" * 64},
            {"sdk_completion_size": 100},
            {"sdk_completion": "sha256:" + "a" * 64, "sdk_completion_size": 0},
        ):
            with (
                self.subTest(options=options),
                self.assertRaises(CliFailure) as failure,
            ):
                subject.reopen_authored_sdk_inputs(
                    self.project,
                    object(),
                    SimpleNamespace(
                        sdk_cache="cache", allow_sdk_builds=True, **options
                    ),
                )
            self.assertEqual(failure.exception.code, "cli.usage")
        self.binding.assert_not_called()
        self.config.assert_not_called()
        self.acquisition.assert_not_called()

    def test_prepare_and_plan_offer_distinct_public_options(self):
        parser = _parser()
        prefix = ["project", "qualify"]
        args = parser.parse_args(
            [
                *prefix,
                "prepare-sdk",
                "greeting",
                "--sdk-cache",
                "cache",
                "--sdk-revocations",
                "/authority/revocations.json",
                "--allow-sdk-builds",
            ]
        )
        self.assertEqual(args.project_qualify_command, "prepare-sdk")
        self.assertTrue(args.allow_sdk_builds)
        with self.assertRaises(CliFailure):
            parser.parse_args([*prefix, "plan", "greeting", "--allow-sdk-builds"])
        args = parser.parse_args(
            [
                *prefix,
                "plan",
                "greeting",
                "--sdk-cache",
                "cache",
                "--sdk-completion",
                "sha256:" + "a" * 64,
                "--sdk-completion-size",
                "500",
                "--sdk-revocations",
                "/authority/revocations.json",
            ]
        )
        self.assertEqual(args.sdk_completion_size, 500)
        self.assertFalse(hasattr(args, "allow_sdk_builds"))
