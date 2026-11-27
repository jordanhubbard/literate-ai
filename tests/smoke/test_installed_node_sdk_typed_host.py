"""Metadata and filesystem controls only; no installed SDK qualification."""

import copy
import hashlib
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from unittest import mock

from scripts import wheel_smoke
from tests.support import installed_node_sdk_journey as fixture


class InstalledTypedHostGuardTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.repository = Path(__file__).resolve().parents[2]

    def report(self):
        return {
            "schema": fixture.TYPED_HOST_SCHEMA,
            "scope": fixture.TYPED_HOST_SCOPE,
            "qualified": False,
            "preflight_passed": True,
            "authorization_mode": "inspected-verifier@1",
            "selected": 2,
            "passed": 2,
            "skipped": 0,
            "cases": list(fixture.TYPED_HOST_CASES),
            "declared_acknowledgement_profile": copy.deepcopy(
                fixture.TYPED_HOST_ACKNOWLEDGEMENT_PROFILE
            ),
            "installed_module_origins_verified": True,
            "source_execution_policy": "isolated-no-write-empty-private-pycache@1",
            "original_namespace_custody_verified": True,
            "wheel_sha256": "1" * 64,
            "driver_sha256": "2" * 64,
            "helper_manifest_sha256": "3" * 64,
            "framework_distribution": "sha256:" + "4" * 64,
        }

    def test_typed_helper_manifest_adds_only_the_original_native_case_owner(self):
        digest, paths = wheel_smoke.stage_node_sdk_typed_helpers(
            self.repository, self.root
        )
        self.assertEqual(set(paths), set(wheel_smoke.NODE_SDK_TYPED_HELPERS))
        self.assertEqual(
            set(paths) - set(wheel_smoke.NODE_SDK_HELPERS),
            {
                "tests/smoke/test_node_sdk_typed_host_native.py",
            },
        )
        content = (self.root / "helpers.json").read_bytes()
        self.assertEqual(hashlib.sha256(content).hexdigest(), digest)
        self.assertEqual(
            fixture.file_table(self.root / "helpers"), json.loads(content)["files"]
        )
        self.assertFalse((self.root / "helpers/src").exists())

    def test_incompatible_preflight_modes_refuse_before_tools_or_installs(self):
        for incompatible in (
            ["--node-sdk-runtime"],
            ["--node-sdk-rebuild-preflight"],
            ["--diagnostic-node-probes"],
            ["--qualified-wheel-manifest", "unused.json"],
            ["--wheel", "unused.whl"],
        ):
            with self.subTest(incompatible=incompatible):
                with (
                    mock.patch.object(
                        sys,
                        "argv",
                        [
                            "wheel_smoke.py",
                            "--node-sdk-typed-host-preflight",
                            *incompatible,
                        ],
                    ),
                    mock.patch.object(
                        wheel_smoke, "require_node_sdk_prerequisites"
                    ) as tools,
                    mock.patch.object(wheel_smoke, "run") as run,
                    redirect_stderr(io.StringIO()),
                    self.assertRaises(SystemExit) as caught,
                ):
                    wheel_smoke._main()
                self.assertEqual(caught.exception.code, 2)
                tools.assert_not_called()
                run.assert_not_called()

    def test_controller_cannot_mix_typed_and_rebuild_cell(self):
        with mock.patch.object(wheel_smoke, "require_node_sdk_prerequisites") as tools:
            with self.assertRaisesRegex(ValueError, "separate fixed cell"):
                wheel_smoke._installed_node_sdk_cell(
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    rebuild_preflight=True,
                    typed_host_preflight=True,
                )
            tools.assert_not_called()

    def test_controller_refuses_non_boolean_mode_before_tools(self):
        with mock.patch.object(wheel_smoke, "require_node_sdk_prerequisites") as tools:
            with self.assertRaises(ValueError):
                wheel_smoke._installed_node_sdk_cell(
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    rebuild_preflight=False,
                    typed_host_preflight=1,
                )
            tools.assert_not_called()

    def test_closed_protocol_refuses_manual_whole_wheel_and_different_case_claims(self):
        for changes in (
            {"schema": "literate-ai/installed-node-sdk-qualification@1"},
            {"scope": "authored-macos-installed-python-api"},
            {"qualified": True},
            {"preflight_passed": 1},
            {"passed": True},
            {"selected": 1},
            {"skipped": 1},
            {"authorization_mode": "manual"},
            {"cases": list(reversed(fixture.TYPED_HOST_CASES))},
            {"cases": list(fixture.METHODS)},
            {"installed_module_origins_verified": False},
            {"original_namespace_custody_verified": False},
            {"source_execution_policy": "ambient-imports"},
            {"wheel_sha256": "not-a-digest"},
        ):
            with self.subTest(changes=changes):
                report = self.report() | changes
                with self.assertRaises(RuntimeError):
                    fixture.require_typed_host_report(report)

    def test_declared_acknowledgement_limits_are_exact_and_bound_to_helper_profile(
        self,
    ):
        report = self.report()
        self.assertIsNone(fixture.require_typed_host_report(report))
        for branch, key, value in (
            ("runtime", "lifetime_seconds", 7200),
            ("binding", "deadline_offset_seconds", 3600),
        ):
            altered = copy.deepcopy(report)
            altered["declared_acknowledgement_profile"][branch][key] = value
            with self.assertRaises(RuntimeError):
                fixture.require_typed_host_report(altered)
        altered = copy.deepcopy(report)
        altered["declared_acknowledgement_profile"]["renewal"] = 0
        with self.assertRaises(RuntimeError):
            fixture.require_typed_host_report(altered)

    def test_closed_case_inventory_refuses_legacy_methods_without_execution(self):
        from tests.smoke import test_canonical_sdk_runtime as original_manual

        with mock.patch.object(fixture, "_run_runtime_methods") as run:
            with self.assertRaises((ValueError, RuntimeError)):
                fixture.run_typed_host_cases(original_manual.CanonicalSDKRuntimeTests)
            run.assert_not_called()

    def retention_inputs(self):
        repository = self.root / "repository"
        driver = repository / "tests/support/installed_node_sdk_journey.py"
        driver.parent.mkdir(parents=True)
        shutil.copyfile(
            self.repository / "tests/support/installed_node_sdk_journey.py", driver
        )
        wheel = self.root / "unqualified-fixture.whl"
        wheel.write_bytes(b"metadata control only; not a built wheel")
        case = self.root / "case"
        case.mkdir()
        report = self.report() | {
            "wheel_sha256": hashlib.sha256(wheel.read_bytes()).hexdigest()
        }
        evidence = case / "result.json"
        evidence.write_text(json.dumps(report))
        for name in ("stdout.log", "stderr.log"):
            (case / name).write_bytes(b"isolated metadata control\n")
        result = report | {
            "_evidence_path": str(evidence),
            "evidence_sha256": hashlib.sha256(evidence.read_bytes()).hexdigest(),
        }
        return repository, wheel, case, result

    def test_retention_preserves_exact_bytes_and_never_creates_wheel_qualification(
        self,
    ):
        repository, wheel, case, result = self.retention_inputs()
        retained = wheel_smoke._retain_node_sdk_typed_host_preflight(
            repository,
            wheel,
            revision="isolated-metadata-fixture",
            result=result,
        )
        self.assertEqual((retained / wheel.name).read_bytes(), wheel.read_bytes())
        self.assertEqual(
            (retained / "result.json").read_bytes(), (case / "result.json").read_bytes()
        )
        manifest = json.loads((retained / "manifest.json").read_text())
        self.assertIs(manifest["qualified"], False)
        self.assertIs(manifest["preflight_passed"], True)
        self.assertEqual(manifest["authorization_mode"], "inspected-verifier@1")
        self.assertFalse((repository / "_build/release-wheels").exists())

    def test_changed_result_protocol_cannot_be_retained_as_typed_success(self):
        repository, wheel, _case, result = self.retention_inputs()
        result["qualified"] = True
        with self.assertRaises(RuntimeError):
            wheel_smoke._retain_node_sdk_typed_host_preflight(
                repository,
                wheel,
                revision="isolated-metadata-fixture",
                result=result,
            )
        self.assertFalse((repository / "_build/node-sdk-typed-host-preflight").exists())

    def test_linked_evidence_cannot_be_retained(self):
        repository, wheel, case, result = self.retention_inputs()
        evidence = case / "result.json"
        evidence.rename(case / "foreign.json")
        evidence.symlink_to(case / "foreign.json")
        with self.assertRaises((RuntimeError, ValueError)):
            wheel_smoke._retain_node_sdk_typed_host_preflight(
                repository,
                wheel,
                revision="isolated-metadata-fixture",
                result=result,
            )
