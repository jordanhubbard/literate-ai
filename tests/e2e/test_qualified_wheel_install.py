"""Real prefix installs reuse one wheel and refuse stale or substituted inputs.

The tiny installable distribution is a custody fixture, not framework qualification.
Its source backend deliberately cannot build, so a successful pip installation
proves the installer consumed the retained wheel rather than rebuilding source.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.qualified_wheel_installation import export_qualified_wheel
from literate_ai.contracts import canonical_identity
from literate_ai.release_files import SCHEMA, file_identity
from scripts.install_litai import install


class QualifiedWheelInstallTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.source = self.root / "source"
        (self.source / "src/literate_ai").mkdir(parents=True)
        (self.source / "src/literate_ai/version.py").write_text(
            'DISTRIBUTION_VERSION = "1.4.0"\n'
        )
        (self.source / "pyproject.toml").write_text(
            '[build-system]\nrequires = []\nbuild-backend = "cannot_build"\n'
            'backend-path = ["."]\n'
        )
        (self.source / "cannot_build.py").write_text(
            'raise RuntimeError("source backend must not run for wheel reuse")\n'
        )
        (self.source / ".gitignore").write_text("_build/\n")
        (self.source / "scripts").mkdir()
        for name in ("litai-launcher", "litai-launcher.cmd"):
            (self.source / "scripts" / name).write_text("fixture launcher\n")
        self.git("init", "-q")
        self.git("config", "user.name", "Wheel fixture")
        self.git("config", "user.email", "wheel@example.invalid")
        self.git("remote", "add", "origin", "https://example.invalid/literate-ai.git")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.revision = self.git("rev-parse", "HEAD")
        self.retained = self.source / "_build/retained"
        self.retained.mkdir(parents=True)
        self.wheel = self.retained / "literate_ai-1.4.0-py3-none-any.whl"
        self.manifest = self.root / "candidate.json"
        self.make_wheel()
        self.publish()

    def git(self, *args):
        return subprocess.check_output(
            ("git", "-C", str(self.source), *args), text=True, stderr=subprocess.PIPE
        ).strip()

    def make_wheel(self, *, revision=None):
        origin = {
            "schema": "literate-ai/distribution-origin@1",
            "repository_url": "https://example.invalid/literate-ai.git",
            "git_revision": revision or self.revision,
        }
        members = {
            "literate_ai/__init__.py": 'PROBE = "qualified fixture bytes"\n',
            "literate_ai/_distribution_origin.json": json.dumps(origin),
            "literate_ai-1.4.0.dist-info/METADATA": (
                "Metadata-Version: 2.1\nName: literate-ai\nVersion: 1.4.0\n"
            ),
            "literate_ai-1.4.0.dist-info/WHEEL": (
                "Wheel-Version: 1.0\nGenerator: custody-fixture\n"
                "Root-Is-Purelib: true\nTag: py3-none-any\n"
            ),
        }
        members["literate_ai-1.4.0.dist-info/RECORD"] = "".join(
            f"{name},,\n" for name in (*members, "literate_ai-1.4.0.dist-info/RECORD")
        )
        with zipfile.ZipFile(self.wheel, "w") as archive:
            for name, content in members.items():
                archive.writestr(name, content)

    def publish(self):
        value = {
            "schema": SCHEMA,
            "revision": self.revision,
            "version": "1.4.0",
            "files": [
                {
                    "role": "wheel",
                    "path": self.wheel.name,
                    "size": self.wheel.stat().st_size,
                    "identity": file_identity(self.wheel),
                }
            ],
        }
        value["identity"] = canonical_identity(value).uri
        retained_manifest = self.retained / "manifest.json"
        retained_manifest.write_text(json.dumps(value))
        export_qualified_wheel(
            self.source,
            retained_manifest,
            self.manifest,
            revision=self.revision,
            version="1.4.0",
        )

    def test_two_real_installations_use_the_same_wheel_without_source_builds(self):
        identity = file_identity(self.wheel)
        with patch.dict(os.environ, {"PIP_NO_INDEX": "1"}):
            for name in ("first", "second"):
                result = install(
                    prefix=self.root / name,
                    source=self.source,
                    qualified_wheel_manifest=self.manifest,
                )
                self.assertEqual(result["qualified_wheel_identity"], identity)
                python = Path(result["environment"]) / (
                    "Scripts/python.exe" if os.name == "nt" else "bin/python"
                )
                probe = subprocess.check_output(
                    (
                        str(python),
                        "-I",
                        "-c",
                        "import literate_ai; print(literate_ai.PROBE)",
                    ),
                    text=True,
                    cwd=self.root,
                    timeout=30,
                )
                self.assertEqual(probe.strip(), "qualified fixture bytes")
        self.assertEqual(file_identity(self.wheel), identity)
        self.assertEqual(self.git("status", "--porcelain"), "")

    def test_substitution_stale_revision_and_false_origin_refuse_before_install(self):
        original = self.wheel.read_bytes()
        for case in ("substitution", "false-origin", "stale-revision", "dirty"):
            with self.subTest(case=case):
                self.manifest = self.root / (case + ".json")
                self.wheel.write_bytes(original)
                self.publish()
                if case == "substitution":
                    self.wheel.write_bytes(b"X" * len(original))
                elif case == "false-origin":
                    self.make_wheel(revision="b" * 40)
                    self.manifest.unlink()
                    self.publish()
                elif case == "stale-revision":
                    self.git("commit", "--allow-empty", "-qm", "new candidate")
                else:
                    (self.source / "foreign.txt").write_text("uncommitted source")
                prefix = self.root / case
                with self.assertRaises((ValueError, RuntimeError)):
                    install(
                        prefix=prefix,
                        source=self.source,
                        qualified_wheel_manifest=self.manifest,
                    )
                self.assertFalse(prefix.exists())

    def test_concurrent_candidate_publication_cannot_replace_selected_bytes(self):
        first = self.retained / "manifest.json"
        second = self.source / "_build/other"
        second.mkdir()
        alternate = second / self.wheel.name
        alternate.write_bytes(self.wheel.read_bytes() + b"different wheel bytes")
        record = json.loads(first.read_text())
        record["files"][0].update(
            size=alternate.stat().st_size, identity=file_identity(alternate)
        )
        record.pop("identity")
        record["identity"] = canonical_identity(record).uri
        other_manifest = second / "manifest.json"
        other_manifest.write_text(json.dumps(record))
        candidate = self.root / "concurrent.json"

        def publish(path):
            try:
                export_qualified_wheel(
                    self.source,
                    path,
                    candidate,
                    revision=self.revision,
                    version="1.4.0",
                )
            except ValueError:
                return False
            return True

        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(
                sorted(pool.map(publish, (first, other_manifest))), [False, True]
            )
        selected = candidate.read_bytes()
        # A retry of the winner is a no-op; the other bytes still cannot replace it.
        self.assertEqual(sorted(map(publish, (first, other_manifest))), [False, True])
        self.assertEqual(candidate.read_bytes(), selected)


if __name__ == "__main__":
    unittest.main()
