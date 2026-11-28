"""Public retained packaging preserves read-only and live-admission boundaries."""

import io
import json
import unittest
from contextlib import ExitStack
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.cli import dispatch
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

    def test_main_read_only_plan_never_enters_implicit_host_writers(self):
        for flag in ("--retained-project-plan", "--retained-project-pla"):
            with self.subTest(flag=flag), ExitStack() as stack:
                for name in (
                    "maybe_host_self_update",
                    "ensure_user_mcp_catalog",
                    "_run_operator_mcp_discovery",
                    "journal_mutagenic_event",
                    "_fan_out_operator_mcp_event",
                ):
                    stack.enter_context(
                        patch.object(dispatch, name, side_effect=AssertionError(name))
                    )
                stack.enter_context(
                    patch.object(
                        dispatch.PerformanceRecorder,
                        "span",
                        side_effect=AssertionError("performance write"),
                    )
                )
                handler = stack.enter_context(
                    patch.object(
                        dispatch, "_handle", return_value=({"admitted": False}, 0)
                    )
                )
                output = io.StringIO()
                status = dispatch.main(
                    [
                        "--json",
                        "package",
                        "retained-project",
                        "--retained-project",
                        "manifest.json",
                        "--retained-project-profile",
                        "profile.json",
                        "--provider-lock",
                        self.lock.uri,
                        flag,
                    ],
                    stdout=output,
                    stderr=io.StringIO(),
                )
                self.assertEqual(status, 0)
                self.assertFalse(json.loads(output.getvalue())["result"]["admitted"])
                handler.assert_called_once()
                self.assertTrue(handler.call_args.args[0].retained_project_plan)

    def test_main_plan_refuses_discovery_and_debug_files_before_writers(self):
        for option in (("--discover-mcps",), ("--debug", "forbidden.log")):
            with self.subTest(option=option), ExitStack() as stack:
                for name in (
                    "maybe_host_self_update",
                    "ensure_user_mcp_catalog",
                    "_run_operator_mcp_discovery",
                    "journal_mutagenic_event",
                    "_fan_out_operator_mcp_event",
                    "_handle",
                ):
                    stack.enter_context(
                        patch.object(dispatch, name, side_effect=AssertionError(name))
                    )
                errors = io.StringIO()
                status = dispatch.main(
                    [
                        "--json",
                        *option,
                        "package",
                        "retained-project",
                        "--retained-project",
                        "manifest.json",
                        "--retained-project-profile",
                        "profile.json",
                        "--provider-lock",
                        self.lock.uri,
                        "--retained-project-plan",
                    ],
                    stdout=io.StringIO(),
                    stderr=errors,
                )
                self.assertEqual(status, 2)
                self.assertEqual(
                    json.loads(errors.getvalue())["error"]["code"],
                    "orchestration.read_only_options",
                )

    def test_main_missing_and_stale_current_locks_return_json_failure(self):
        from literate_ai.adapters.component_lock_application import (
            ProjectComponentLockSetError,
        )
        from literate_ai.cli import retained_project_package as module

        for code in (
            "component_lock.missing",
            "component_lock.project_lock_set_invalid",
        ):
            with self.subTest(code=code), ExitStack() as stack:
                stack.enter_context(
                    patch.object(module, "discover_project", return_value=self.project)
                )
                stack.enter_context(
                    patch(
                        "literate_ai.cli.rebuild._resolve_standard_binding",
                        return_value=object(),
                    )
                )
                stack.enter_context(
                    patch.object(
                        module,
                        "current_project_component_locks",
                        side_effect=ProjectComponentLockSetError(
                            code, "lock is not current"
                        ),
                    )
                )
                owner = stack.enter_context(
                    patch.object(module, "RetainedProjectZipPackage")
                )
                errors = io.StringIO()
                status = dispatch.main(
                    [
                        "--json",
                        "package",
                        "retained-project",
                        "--retained-project",
                        "manifest.json",
                        "--retained-project-profile",
                        "profile.json",
                        "--provider-lock",
                        self.lock.uri,
                        "--retained-project-plan",
                    ],
                    stdout=io.StringIO(),
                    stderr=errors,
                )
                self.assertEqual(status, 2)
                self.assertEqual(json.loads(errors.getvalue())["error"]["code"], code)
                owner.assert_not_called()

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
