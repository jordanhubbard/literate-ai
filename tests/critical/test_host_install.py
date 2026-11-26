"""Contracts for composed Flavor host-toolchain installation."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import host_install
from literate_ai.adapters.host_install import (
    HostInstallError,
)
from literate_ai.bootstrap.host_install_requirements import (
    HostInstallTarget,
    HostManagedArtifact,
)


def _artifact(archive: Path, *, digest: str | None = None) -> HostManagedArtifact:
    return HostManagedArtifact(
        "urn:test:artifact",
        "fixture agent",
        "1.0.0",
        ("codex",),
        "https://example.invalid/fixture.tar.gz",
        "sha256",
        digest or hashlib.sha256(archive.read_bytes()).hexdigest(),
        "tar.gz",
        "bundle",
        (".",),
        "agent-source",
        "codex",
    )


class HostInstallContractTests(unittest.TestCase):
    def test_arm64_images_and_companions_cannot_be_proven_by_versions(self):
        """Foreign images never become native proof or trigger silent replacement.

        PE files and the OS command runner are deliberate counterexample fixtures,
        not an executable Windows program or native platform qualification.
        """
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            catalog = root / "flavors"
            repository = Path(__file__).resolve().parents[2]
            shutil.copytree(repository / "flavors", catalog)
            original = catalog / "os-windows/host-install/windows/x86_64/none.cdx.json"
            document = json.loads(original.read_text())
            for item in document["metadata"]["properties"]:
                if item["name"] == "literate-ai:host-install:architecture":
                    item["value"] = "arm64"
            leaf = catalog / "os-windows/host-install/windows/arm64/none.cdx.json"
            leaf.parent.mkdir()
            leaf.write_text(json.dumps(document))
            target = HostInstallTarget("windows", "arm64")
            path, sbom = host_install.load_host_install_sbom(catalog, target)
            artifact = next(a for a in sbom.artifacts if "codex" in a.capabilities)
            bundle = root / "bundle"
            executable = bundle / artifact.executable_path
            required = [bundle / name for name in artifact.required_runtime_paths]

            def image(path, machine):
                content = bytearray(88)
                content[:2] = b"MZ"
                content[60:64] = (64).to_bytes(4, "little")
                content[64:68] = b"PE\0\0"
                content[68:70] = machine.to_bytes(2, "little")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)

            installs = []

            def runner(arguments, **kwargs):
                if "install" in arguments:
                    installs.append(arguments)
                    self.fail("architecture refusal must not replace an existing tool")
                output = (
                    "\n".join(p.manager_package for p in sbom.packages)
                    if "list" in arguments
                    else "codex 0.153.0"
                )
                return subprocess.CompletedProcess(arguments, 0, output, "")

            def locator(command, _path):
                if command in {"codex", "codex.exe", "codex.cmd"}:
                    return str(executable)
                if command == "winget.exe":
                    return str(root / "winget.exe")
                return None

            environment = {"CODING_CLI": "codex", "LITAI_INSTALL_DEPENDENCIES": "yes"}
            for variant in (
                "native",
                "foreign-main",
                "foreign-helper",
                "missing-helper",
            ):
                with self.subTest(variant=variant):
                    image(executable, 0xAA64)
                    for companion in required:
                        companion.parent.mkdir(parents=True, exist_ok=True)
                        if companion.suffix == ".json":
                            companion.write_text("{}")
                        else:
                            image(companion, 0xAA64)
                    helper = next(p for p in required if p.suffix == ".exe")
                    if variant == "foreign-main":
                        image(executable, 0x8664)
                    elif variant == "foreign-helper":
                        image(helper, 0x8664)
                    elif variant == "missing-helper":
                        helper.unlink()
                    before = {
                        p.relative_to(bundle): p.read_bytes()
                        for p in bundle.rglob("*")
                        if p.is_file()
                    }
                    report = host_install.observe_host_install_dependencies(
                        sbom_path=path,
                        sbom=sbom,
                        environment=environment,
                        runner=runner,
                        locator=locator,
                        managed_tool_root=root / "managed",
                    )
                    agent = next(
                        item
                        for item in report.observations
                        if item.requirement.capability == "codex"
                    )
                    self.assertTrue(agent.probe_satisfied)
                    self.assertEqual(agent.ready, variant == "native")
                    wire = agent.to_dict()["image_architecture"]
                    self.assertEqual(wire["verified"], variant == "native")
                    self.assertEqual(len(wire["images"]), len(required))
                    if variant != "native":
                        with self.assertRaises(HostInstallError) as refused:
                            host_install.install_host_dependencies(
                                sbom_root=catalog,
                                target=target,
                                environment=environment,
                                runner=runner,
                                locator=locator,
                                interactive=False,
                                managed_tool_root=root / "managed",
                            )
                        self.assertEqual(
                            refused.exception.code,
                            "host-install.native-image-unverified",
                        )
                        self.assertIn("codex", refused.exception.message)
                    self.assertEqual(installs, [])
                    self.assertEqual(
                        before,
                        {
                            p.relative_to(bundle): p.read_bytes()
                            for p in bundle.rglob("*")
                            if p.is_file()
                        },
                    )

    def test_inaccessible_native_search_path_reports_typed_error(self) -> None:
        # Native host readiness must fail closed when declared tool paths cannot
        # be inspected, with a typed error the installer and doctor can report.
        root = Path(__file__).resolve().parents[2]
        sbom_path, sbom = host_install.load_host_install_sbom(
            root / "flavors", HostInstallTarget("windows", "x86_64")
        )
        with tempfile.TemporaryDirectory() as temporary:
            environment = {"PATH": "existing-tools", "LOCALAPPDATA": temporary}
            for failure in (PermissionError("access denied"), OSError("unavailable")):
                with (
                    self.subTest(failure=type(failure).__name__),
                    mock.patch.object(Path, "is_dir", side_effect=failure),
                    self.assertRaises(HostInstallError) as raised,
                ):
                    host_install.observe_host_install_dependencies(
                        sbom_path=sbom_path,
                        sbom=sbom,
                        environment=environment,
                        managed_tool_root=Path(temporary) / "tools",
                    )
                self.assertEqual(raised.exception.code, "host-install.path-unreadable")
                self.assertIn("account with access", raised.exception.message)
                self.assertEqual(environment["PATH"], "existing-tools")

    def test_managed_artifact_verifies_digest_and_normalizes_name(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            archive = root / "fixture.tar.gz"
            content = b"fixture executable"
            with tarfile.open(archive, "w:gz") as bundle:
                info = tarfile.TarInfo("bundle/agent-source")
                info.size = len(content)
                info.mode = 0o755
                bundle.addfile(info, io.BytesIO(content))
            artifact = _artifact(archive)

            def download(_url: str, destination: Path) -> None:
                shutil.copy2(archive, destination)

            installed = host_install._install_managed_artifact(
                artifact, tool_root=root / "tools", downloader=download
            )
            self.assertEqual((installed / "codex").read_bytes(), content)
            self.assertTrue(
                host_install._artifact_manifest_matches(installed, artifact)
            )

            manifest_path = installed / ".literate-ai-artifact.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest.pop("required_runtime_paths")
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertTrue(
                host_install._artifact_manifest_matches(installed, artifact)
            )

    def test_managed_artifact_rejects_digest_mismatch_and_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            safe = root / "safe.tar.gz"
            with tarfile.open(safe, "w:gz") as bundle:
                info = tarfile.TarInfo("bundle/agent-source")
                info.size = 1
                bundle.addfile(info, io.BytesIO(b"x"))

            def download_safe(_url: str, destination: Path) -> None:
                shutil.copy2(safe, destination)

            with self.assertRaises(HostInstallError) as digest_error:
                host_install._install_managed_artifact(
                    _artifact(safe, digest="0" * 64),
                    tool_root=root / "digest-tools",
                    downloader=download_safe,
                )
            self.assertEqual(
                digest_error.exception.code, "host-install.artifact-digest-mismatch"
            )

            unsafe = root / "unsafe.tar.gz"
            with tarfile.open(unsafe, "w:gz") as bundle:
                info = tarfile.TarInfo("../escape")
                info.size = 1
                bundle.addfile(info, io.BytesIO(b"x"))

            def download_unsafe(_url: str, destination: Path) -> None:
                shutil.copy2(unsafe, destination)

            with self.assertRaises(HostInstallError) as traversal_error:
                host_install._install_managed_artifact(
                    _artifact(unsafe),
                    tool_root=root / "traversal-tools",
                    downloader=download_unsafe,
                )
            self.assertEqual(
                traversal_error.exception.code, "host-install.archive-traversal"
            )


if __name__ == "__main__":
    unittest.main()
