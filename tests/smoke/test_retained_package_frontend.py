"""Public retained packaging preserves read-only and live-admission boundaries."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.cli.dispatch import _parser
from literate_ai.cli.errors import CliFailure
from literate_ai.cli.package import package_from_args
from literate_ai.contracts import ContentIdentity, StandardProjectLifecycleDriver


class RetainedPackageFrontendTests(unittest.TestCase):
    def setUp(self):
        self.lock = ContentIdentity.parse_uri("sha256:" + "a" * 64)
        self.revision = ContentIdentity.parse_uri("sha256:" + "b" * 64)
        self.project = SimpleNamespace(
            definition=SimpleNamespace(
                lifecycle_driver=StandardProjectLifecycleDriver(
                    self.lock, self.revision
                )
            )
        )

    def arguments(self, *extra):
        return _parser().parse_args(
            [
                "package",
                "retained-project",
                "--retained-project",
                "manifest.json",
                "--retained-project-profile",
                "profile.json",
                "--provider-lock",
                self.lock.uri,
                *extra,
            ]
        )

    def invoke(self, args, lifecycle):
        from literate_ai.cli import retained_project_package as module

        with (
            patch.object(module, "discover_project", return_value=self.project),
            patch(
                "literate_ai.cli.rebuild._resolve_standard_binding",
                return_value=object(),
            ),
            patch.object(
                module,
                "_selected_zip_provider",
                return_value=(self.lock, self.revision),
            ),
            patch.object(module, "retained_project_from_args", side_effect=lifecycle),
            patch.object(module, "RetainedProjectZipPackage") as owner,
        ):
            return package_from_args(args), owner

    def test_read_only_intent_does_not_construct_or_claim_admission(self):
        result, owner = self.invoke(
            self.arguments("--retained-project-plan"),
            lambda *_a, **_k: {"admitted": False, "release_authorized": False},
        )
        document, status = result
        self.assertEqual(status, 0)
        self.assertFalse(document["package_qualified"])
        self.assertFalse(document["project_receipt_qualified"])
        self.assertFalse(document["admitted"])
        self.assertEqual(document["package_intent"]["provider_lock"], self.lock.uri)
        owner.assert_not_called()

    def test_decoded_admission_assertion_cannot_substitute_for_live_consumer(self):
        with self.assertRaisesRegex(CliFailure, "live-consumer-required"):
            self.invoke(self.arguments(), lambda *_a, **_k: {"admitted": True})

    def test_read_only_intent_refuses_an_unexpected_live_consumer_call(self):
        def unexpected(*_a, consume_admission, **_k):
            consume_admission(object(), SimpleNamespace(objects="objects"))
            return {"admitted": True}

        with self.assertRaisesRegex(CliFailure, "read-only-intent"):
            self.invoke(self.arguments("--retained-project-plan"), unexpected)

    def test_failed_lifecycle_does_not_grant_packaging(self):
        def failed(*_a, **_k):
            raise CliFailure(
                "retained_project.execution_failed", "original tests failed"
            )

        with self.assertRaisesRegex(CliFailure, "original tests failed"):
            self.invoke(self.arguments(), failed)

    def test_provider_is_reopened_before_live_consumption(self):
        from literate_ai.cli import retained_project_package as module

        def run(*_args, consume_admission, **_kwargs):
            consume_admission(object(), SimpleNamespace(objects="objects"))
            return {"admitted": True}

        with (
            patch.object(module, "discover_project", return_value=self.project),
            patch(
                "literate_ai.cli.rebuild._resolve_standard_binding",
                return_value=object(),
            ),
            patch.object(
                module,
                "_selected_zip_provider",
                side_effect=[(self.lock, self.revision), (self.revision, self.lock)],
            ),
            patch.object(module, "retained_project_from_args", side_effect=run),
            patch.object(module, "RetainedProjectZipPackage") as owner,
            self.assertRaisesRegex(CliFailure, "provider-changed"),
        ):
            package_from_args(self.arguments())
        owner.assert_not_called()


if __name__ == "__main__":
    unittest.main()
