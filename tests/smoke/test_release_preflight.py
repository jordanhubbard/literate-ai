"""Exercise the real Make entry point with inert gate bodies."""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


@unittest.skipUnless(shutil.which("make"), "requires the native Make entry point")
class ReleasePreflightTests(unittest.TestCase):
    def test_parallel_validate_waits_for_preflight_and_preserves_standalone_scope(self):
        root = Path(__file__).resolve().parents[2]
        preflight = (
            "schema-check",
            "repository-layout-check",
            "lint",
            "format-check",
            "openspec-check",
            "documentation-check",
            "driver-review",
            "runner-review",
        )
        expensive = ("python-check", "skills-check", "installed-e2e")
        for target, failing in (
            ("validate", "schema-check"),
            ("validate", "openspec-check"),
            ("validate", "driver-review"),
            ("validate", "none"),
            ("through-validate", "none"),
            ("python-check", "none"),
        ):
            with (
                self.subTest(target=target, failing=failing),
                tempfile.TemporaryDirectory() as temporary,
            ):
                directory = Path(temporary)
                events = directory / "events"
                events.mkdir()
                probe = directory / "gate.py"
                probe.write_text(
                    "import pathlib,sys\n"
                    "root=pathlib.Path(__file__).parent/'events'\n"
                    "gate,failing,enforce=sys.argv[1:]\n"
                    f"preflight={preflight!r}\n"
                    "(root/(gate+'.started')).open('x').close()\n"
                    f"if gate in {expensive!r} and enforce=='1':\n"
                    "    assert all((root/(n+'.passed')).is_file() "
                    "for n in preflight)\n"
                    "if gate==failing: sys.exit(7)\n"
                    "(root/(gate+'.passed')).open('x').close()\n",
                    encoding="utf-8",
                )
                # Recursive Make must read the same actual graph and inert gate
                # bodies from its default file; -f options are not inherited.
                include = (root / "Makefile").as_posix().replace(" ", "\\ ")
                bodies = [f"include {include}\n"]
                for gate in (*preflight, *expensive):
                    bodies.append(
                        f'{gate}:\n\t$(PYTHON) "{probe.as_posix()}" '
                        f"{gate} {failing} {int(target != 'python-check')}\n"
                    )
                bodies.append(".PHONY: through-validate\nthrough-validate: validate\n")
                (directory / "Makefile").write_text("\n".join(bodies), encoding="utf-8")
                # Satisfy retained tool prerequisites without installing tools.
                (directory / "scripts").mkdir()
                (directory / "scripts/stage_node_tool.py").write_text(
                    "raise SystemExit('unexpected tool installation')\n"
                )
                stamps = []
                for name in (
                    "NODE_AUDIT_STAMP",
                    "OPENSPEC_TOOL_STAMP",
                    "DOCUMENTATION_TOOL_STAMP",
                ):
                    path = directory / name
                    path.write_text("fixture tools already installed\n")
                    stamps.append(f"{name}={path.as_posix()}")
                result = subprocess.run(
                    [
                        shutil.which("make"),
                        "-j4",
                        target,
                        f'PYTHON="{sys.executable}"',
                        f"OBJ_DIR={directory.as_posix()}/objects",
                        *stamps,
                    ],
                    cwd=directory,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                if failing != "none":
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertTrue((events / f"{failing}.started").is_file())
                    self.assertFalse(
                        any((events / f"{gate}.started").exists() for gate in expensive)
                    )
                else:
                    self.assertEqual(
                        result.returncode, 0, result.stdout + result.stderr
                    )
                    expected = (
                        {"python-check"}
                        if target == "python-check"
                        else set(preflight + expensive)
                    )
                    self.assertEqual(
                        {p.stem for p in events.glob("*.passed")}, expected
                    )

    def test_stale_authority_refuses_before_release_gate_runner(self):
        root = Path(__file__).resolve().parents[2]
        preflight = (
            "schema-check",
            "driver-review",
            "runner-review",
            "documentation-review",
        )
        for failing in preflight:
            with (
                self.subTest(failing=failing),
                tempfile.TemporaryDirectory() as temporary,
            ):
                directory = Path(temporary)
                override = directory / "gates.mk"
                bodies = []
                for gate in preflight:
                    marker = str(directory / gate).encode("utf-8").hex()
                    code = (
                        "import pathlib,sys;"
                        f"pathlib.Path(bytes.fromhex('{marker}').decode()).write_text('ran');"
                        f"sys.exit({7 if gate == failing else 0})"
                    )
                    bodies.append(f'{gate}:\n\t$(PYTHON) -c "{code}"\n')
                override.write_text("\n".join(bodies), encoding="utf-8")
                checkpoint = directory / "release-checkpoint.json"
                result = subprocess.run(
                    [
                        shutil.which("make"),
                        "-f",
                        str(root / "Makefile"),
                        "-f",
                        str(override),
                        "release-check",
                        f'PYTHON="{sys.executable}"',
                        f"OBJ_DIR={directory}",
                        f"RELEASE_CHECKPOINT={checkpoint}",
                        "RUNTIME_PREREQUISITE=",
                        "RELEASE_GATES=must-not-run",
                    ],
                    cwd=root,
                    capture_output=True,
                    text=True,
                    timeout=20,
                )
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertTrue((directory / failing).is_file(), result.stderr)
                self.assertFalse(checkpoint.exists())
                self.assertNotIn("run_checkpointed_gates.py", result.stdout)
                if failing == "driver-review":
                    self.assertFalse((directory / "runner-review").exists())
