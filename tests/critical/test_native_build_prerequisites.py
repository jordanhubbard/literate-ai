"""Native-package metadata controls; these fixtures do not qualify a native SDK."""

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters import host_install
from literate_ai.bootstrap.host_install_requirements import (
    HostInstallRequirementError,
    HostInstallTarget,
    compose_toolchain_sboms,
    parse_host_install_sbom,
)


class NativeBuildPrerequisiteTests(unittest.TestCase):
    def fixture(self):
        flavors = Path(__file__).resolve().parents[2] / "flavors"
        target = HostInstallTarget("windows", "arm64")
        path, original = host_install.load_host_install_sbom(flavors, target)
        document = json.loads(path.read_bytes())
        # Replace the shipped SDK only in these protocol counterexample fixtures.
        sdk_refs = {
            item["bom-ref"]
            for item in document["components"]
            if any(
                prop["name"] == "literate-ai:host-install:realization-kind"
                and prop["value"] == "native-build-prerequisite"
                for prop in item["properties"]
            )
        }
        document["components"] = [
            item for item in document["components"] if item["bom-ref"] not in sdk_refs
        ]
        document["dependencies"] = [
            {
                **item,
                "dependsOn": [ref for ref in item["dependsOn"] if ref not in sdk_refs],
            }
            for item in document["dependencies"]
            if item["ref"] not in sdk_refs
        ]
        catalog = compose_toolchain_sboms(
            (original.base, *host_install._load_flavor_toolchains(flavors).values())
        )
        reference = "pkg:generic/native-openssl-build-sdk"
        properties = {
            "realization-kind": "native-build-prerequisite",
            "manager-package": "ShiningLight.OpenSSL.Dev",
            "for-capabilities": '["python-venv"]',
            "requires-capabilities": '["cxx","rustc","cargo"]',
            "build-minimum-versions": '{"rustc":"1.83","cargo":"1.83"}',
            "probe-id": "openssl-build",
            "probe-kind": "command",
            "probe-candidates": '["%ProgramFiles%/OpenSSL/bin/openssl.exe"]',
            "probe-arguments": '["version"]',
            "sdk-executable-relative": "bin/openssl.exe",
            "required-runtime-paths": (
                '["bin/libcrypto-3-arm64.dll","bin/libssl-3-arm64.dll"]'
            ),
            "required-development-paths": '["include/openssl/ssl.h"]',
            "build-environment": '{"OPENSSL_DIR":"{sdk_root}"}',
            "reason": "Native Python source dependencies need an OpenSSL SDK.",
        }
        component = {
            "type": "library",
            "bom-ref": reference,
            "name": "OpenSSL source-build SDK",
            "version": ">=3.5,<4",
            "properties": [
                {"name": "literate-ai:host-install:" + name, "value": value}
                for name, value in properties.items()
            ],
        }
        document["components"].append(component)
        root = document["metadata"]["component"]["bom-ref"]
        next(row for row in document["dependencies"] if row["ref"] == root)[
            "dependsOn"
        ].append(reference)
        document["dependencies"].append({"ref": reference, "dependsOn": []})
        return document, original.base, catalog

    def test_target_build_prerequisites_keep_logical_capability_owners(self):
        document, base, catalog = self.fixture()
        original_capabilities = {item.capability for item in base.capabilities}
        parsed = parse_host_install_sbom(document, base=base, catalog=catalog)
        sdk = next(
            item for item in parsed.packages if item.capability == "openssl-build"
        )
        self.assertEqual(sdk.prerequisite_for, ("python-venv",))
        self.assertEqual(sdk.manager_package, "ShiningLight.OpenSSL.Dev")
        self.assertEqual(sdk.sdk_executable_relative, "bin/openssl.exe")
        self.assertEqual(dict(sdk.build_environment), {"OPENSSL_DIR": "{sdk_root}"})
        self.assertEqual(parsed.base, base)
        build_capabilities = {
            item.capability: item for item in parsed.build_capabilities
        }
        self.assertEqual(set(build_capabilities), {"cxx", "rustc", "cargo"})
        self.assertNotIn(
            "openssl-build", original_capabilities | build_capabilities.keys()
        )
        for name in ("cxx", "rustc", "cargo"):
            self.assertEqual(build_capabilities[name], catalog.capability(name))
        for name in ("rustc", "cargo"):
            requirement = next(
                item for item in parsed.packages if item.capability == name
            )
            self.assertIn(">=1.83", requirement.version_constraint.split(","))
        self.assertEqual(
            {item.capability for item in base.capabilities}, original_capabilities
        )

    def test_unknown_logical_owner_and_escaping_sdk_paths_refuse(self):
        document, base, catalog = self.fixture()
        for name, value, error in (
            ("for-capabilities", '["invented-owner"]', "build-prerequisite-owner"),
            ("probe-id", "python-venv", "build-prerequisite-probe-collision"),
            (
                "build-minimum-versions",
                '{"invented-owner":"1.83"}',
                "build-prerequisite-version",
            ),
            (
                "required-runtime-paths",
                '["../foreign.dll"]',
                "build-prerequisite-path",
            ),
            (
                "build-environment",
                '{"OPENSSL_DIR":"/foreign-sdk"}',
                "build-prerequisite-environment",
            ),
            (
                "build-environment",
                '{"OPENSSL_LIB_DIR":"{sdk_root}/../foreign"}',
                "build-prerequisite-environment",
            ),
            (
                "build-environment",
                '{"OPENSSL_INCLUDE_DIR":"{sdk_root}/{sdk_root}"}',
                "build-prerequisite-environment",
            ),
        ):
            with self.subTest(property=name):
                changed = copy.deepcopy(document)
                for prop in changed["components"][-1]["properties"]:
                    if prop["name"] == "literate-ai:host-install:" + name:
                        prop["value"] = value
                with self.assertRaises(HostInstallRequirementError) as refused:
                    parse_host_install_sbom(changed, base=base, catalog=catalog)
                self.assertIn(error, refused.exception.code)

    def sdk_fixture(self, directory):
        directory = directory.resolve()
        document, base, catalog = self.fixture()
        sbom = parse_host_install_sbom(document, base=base, catalog=catalog)
        requirement = next(
            item for item in sbom.packages if item.capability == "openssl-build"
        )
        root = directory / "OpenSSL"
        for relative in (
            requirement.sdk_executable_relative,
            *requirement.required_runtime_paths,
        ):
            self.image(root / relative, 0xAA64)
        for relative in requirement.required_development_paths:
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"explicit SDK header fixture\n")

        def runner(arguments, **kwargs):
            output = (
                requirement.manager_package
                if arguments[0] == "winget"
                else "OpenSSL 3.6.2"
            )
            return subprocess.CompletedProcess(arguments, 0, output, "")

        def locator(command, _path):
            return command if Path(command).is_file() else None

        def observe():
            environment = {"ProgramFiles": str(directory)}
            observation = host_install._observe_native_package(
                requirement,
                sbom=sbom,
                query_path="winget",
                environment=environment,
                runner=runner,
                locator=locator,
            )
            return host_install._observe_windows_arm64_images(
                observation, sbom, environment
            )

        return root, sbom, requirement, observe

    @staticmethod
    def image(path, machine):
        # These bytes are a PE architecture counterexample, never an executable.
        content = bytearray(88)
        content[:2] = b"MZ"
        content[60:64] = (64).to_bytes(4, "little")
        content[64:68] = b"PE\0\0"
        content[68:70] = machine.to_bytes(2, "little")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    def test_sdk_version_cannot_replace_development_files_or_native_runtime_images(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root, _sbom, requirement, observe = self.sdk_fixture(Path(directory))
            self.assertTrue(observe().ready)
            header = root / requirement.required_development_paths[0]
            original = header.read_bytes()
            header.unlink()
            self.assertFalse(observe().probe_satisfied)
            header.write_bytes(original)
            self.image(root / requirement.required_runtime_paths[0], 0x8664)
            foreign = observe()
            self.assertTrue(foreign.probe_satisfied)
            self.assertFalse(foreign.architecture_ready)
            self.assertFalse(foreign.ready)

    def test_build_environment_is_joined_to_the_observed_sdk_and_preserves_conflicts(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            root, sbom, requirement, observe = self.sdk_fixture(Path(directory))
            report = host_install.HostInstallReport(
                Path("fixture-base"),
                Path("fixture-realization"),
                sbom,
                (observe(),),
                "codex",
            )
            self.assertEqual(
                host_install._native_build_environment(report, {}),
                {"OPENSSL_DIR": str(root)},
            )
            original = {"OPENSSL_DIR": str(root.parent / "other-sdk")}
            with self.assertRaises(host_install.HostInstallError) as refused:
                host_install._native_build_environment(report, original)
            self.assertEqual(
                refused.exception.code, "host-install.build-environment-conflict"
            )
            self.assertEqual(original, {"OPENSSL_DIR": str(root.parent / "other-sdk")})
            runtime = root / requirement.required_runtime_paths[0]
            self.image(runtime, 0x8664)
            with self.assertRaises(host_install.HostInstallError) as refused:
                host_install._native_build_environment(report, {})
            self.assertEqual(refused.exception.code, "host-install.build-sdk-changed")
            self.image(runtime, 0xAA64)
            (root / "include/openssl/ssl.h").unlink()
            with self.assertRaises(host_install.HostInstallError) as refused:
                host_install._native_build_environment(report, {})
            self.assertEqual(refused.exception.code, "host-install.build-sdk-changed")

    def test_target_prefixed_environment_cannot_redirect_the_native_build(self):
        with tempfile.TemporaryDirectory() as directory:
            root, sbom, _requirement, observe = self.sdk_fixture(Path(directory))
            report = host_install.HostInstallReport(
                Path("fixture-base"),
                Path("fixture-realization"),
                sbom,
                (observe(),),
                "codex",
            )
            original = {
                "AARCH64_PC_WINDOWS_MSVC_OPENSSL_DIR": str(root.parent / "foreign")
            }
            with self.assertRaises(host_install.HostInstallError) as refused:
                host_install._native_build_environment(report, original)
            self.assertEqual(
                refused.exception.code, "host-install.build-environment-conflict"
            )
            self.assertEqual(
                original,
                {"AARCH64_PC_WINDOWS_MSVC_OPENSSL_DIR": str(root.parent / "foreign")},
            )

    def test_source_build_minimum_is_checked_without_changing_the_logical_contract(
        self,
    ):
        document, base, catalog = self.fixture()
        sbom = parse_host_install_sbom(document, base=base, catalog=catalog)
        requirement = next(item for item in sbom.packages if item.capability == "rustc")
        version = ["rustc 1.75.0"]

        def runner(arguments, **kwargs):
            output = (
                requirement.manager_package if arguments[0] == "winget" else version[0]
            )
            return subprocess.CompletedProcess(arguments, 0, output, "")

        def observe():
            return host_install._observe_native_package(
                requirement,
                sbom=sbom,
                query_path="winget",
                environment={},
                runner=runner,
                locator=lambda command, path: "fixture-rustc",
            )

        self.assertFalse(observe().ready)
        version[0] = "rustc 1.83.0"
        self.assertTrue(observe().ready)
        self.assertEqual(
            sbom.capability("rustc").version_constraint,
            catalog.capability("rustc").version_constraint,
        )
