"""Explicit managed installed-layout cell; retain all fixture bytes for inspection.

Select with make python-check PYTHON_TEST_PATTERN=installed_project_layout_journey.py.
LITAI_INSTALLED_LAYOUT_SOURCE must name a clean qualification checkout and
LITAI_INSTALLED_LAYOUT_OUTPUT an existing local output parent. This is a real
noneditable wheel/launcher proof for that exact commit, not dirty-candidate,
model execution, native lifecycle or complete layout/release qualification.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.builders import run_bounded_process

INSTALL = r"""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(sys.argv[1])/"scripts"))
from install_litai import install
result=install(source=Path(sys.argv[1]),prefix=Path(sys.argv[2]))
Path(sys.argv[3]).write_text(json.dumps(result,sort_keys=True)+"\n")
"""
PROBE = r"""
import importlib.metadata as md,json,sys
from importlib.resources import files
from pathlib import Path
import literate_ai
from literate_ai.adapters.standard_lifecycle_binding import (
    observe_installed_framework_distribution,
)
assert sys.flags.isolated and sys.prefix != sys.base_prefix
package=Path(literate_ai.__file__).resolve()
assert package.is_relative_to(Path(sys.prefix).resolve())
d=md.distribution("literate-ai")
direct=json.loads(d.read_text("direct_url.json"))
assert not direct.get("dir_info",{}).get("editable",False)
origin=json.loads(files("literate_ai").joinpath("_distribution_origin.json").read_bytes())
print(json.dumps({"package":str(package),"prefix":sys.prefix,"direct_url":direct,"origin":origin,"distribution_identity":observe_installed_framework_distribution().identity.uri},sort_keys=True))
"""


def isolated_layout_environment(root: Path) -> dict[str, str]:
    home, temporary = root / "home", root / "tmp"
    home.mkdir()
    temporary.mkdir()
    environment = {
        name: os.environ[name]
        for name in ("PATH", "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT")
        if name in os.environ
    }
    environment.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "TMPDIR": str(temporary),
            "TMP": str(temporary),
            "TEMP": str(temporary),
            "XDG_CONFIG_HOME": str(home / "config"),
            "XDG_CACHE_HOME": str(home / "cache"),
            "XDG_DATA_HOME": str(home / "data"),
            "XDG_STATE_HOME": str(home / "state"),
            "LITAI_NO_SELF_UPDATE": "1",
            "LITAI_TOOL_DIR": str(root / "tools"),
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_NO_INPUT": "1",
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "PYTHONDONTWRITEBYTECODE": "1",
        }
    )
    return environment


class InstalledProjectLayoutJourney(unittest.TestCase):
    def test_exact_noneditable_wheel_and_public_contained_discovery(self):
        source = Path(os.environ["LITAI_INSTALLED_LAYOUT_SOURCE"]).absolute()
        parent = Path(os.environ["LITAI_INSTALLED_LAYOUT_OUTPUT"]).absolute()
        require_safe_directory(source)
        require_safe_directory(parent)
        self.root = Path(tempfile.mkdtemp(prefix="il-", dir=parent))
        print("retained installed layout fixture:", self.root, flush=True)
        self.environment = isolated_layout_environment(self.root)
        self.results = []
        head = (
            self.run_command("source-head", ["git", "rev-parse", "HEAD"], source)
            .stdout.decode()
            .strip()
        )
        self.assertFalse(
            self.run_command(
                "source-clean-before",
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                source,
            ).stdout
        )
        self.run_command(
            "install",
            [
                sys.executable,
                "-I",
                "-c",
                INSTALL,
                str(source),
                str(self.root / "prefix"),
                str(self.root / "installation.json"),
            ],
            self.root,
        )
        installation = json.loads((self.root / "installation.json").read_text())
        environment = Path(installation["environment"])
        python = environment / (
            "Scripts/python.exe" if os.name == "nt" else "bin/python"
        )
        probe = json.loads(
            self.run_command(
                "installed-distribution", [str(python), "-I", "-c", PROBE], self.root
            ).stdout
        )
        self.assertEqual(probe["origin"]["git_revision"], head)
        launcher = installation["launcher"]
        project = self.root / "project"
        parent_source = f"{source.as_uri()}#{head}"
        self.cli(
            "initialize",
            launcher,
            "init",
            str(project),
            "--from",
            parent_source,
            "--no-tool-bootstrap",
            cwd=self.root,
        )
        self.assertTrue((project / "litai/literate.project.json").is_file())
        self.assertFalse((project / "literate.project.json").exists())
        manifest = json.loads((project / "litai/literate.project.json").read_bytes())
        self.assertEqual(manifest["framework_directory"], "litai")
        self.cli(
            "validate-root",
            launcher,
            "project",
            "validate",
            str(project),
            cwd=self.root,
        )
        component = project / "litai/samples/hello-component"
        self.cli(
            "validate-subdirectory",
            launcher,
            "project",
            "validate",
            str(component),
            cwd=self.root,
        )
        self.cli(
            "lock-root",
            launcher,
            "lock",
            "litai/samples/hello-component",
            "--check",
            cwd=project,
        )
        self.cli(
            "plan-root", launcher, "plan", "litai/samples/hello-component", cwd=project
        )
        self.cli(
            "lock-component-directory", launcher, "lock", ".", "--check", cwd=component
        )
        self.cli("plan-component-directory", launcher, "plan", ".", cwd=component)
        self.cli(
            "agent-entrypoints",
            launcher,
            "project",
            "agent-entrypoints",
            str(project),
            cwd=self.root,
        )
        allowed = {
            "litai",
            "AGENTS.md",
            "CLAUDE.md",
            "agents",
            ".cursor",
            "CHANGELOG.md",
        }
        self.assertLessEqual({p.name for p in project.iterdir()}, allowed)
        self.assertFalse(
            self.run_command(
                "source-clean-after",
                ["git", "status", "--porcelain=v1", "--untracked-files=all"],
                source,
            ).stdout
        )
        receipt = {
            "schema": "literate-ai/installed-project-layout-observation@1",
            "source_revision": head,
            "source": str(source),
            "installed_distribution": probe,
            "fixture": str(self.root),
            "commands": self.results,
            "scope": (
                "Actual installed fresh canonical creation, root/subdirectory "
                "validation and lock/plan, agent entrypoints. No native lifecycle, "
                "model, configured worker, migration, other-platform, "
                "dirty-candidate or release qualification."
            ),
            "release_qualification": False,
        }
        (self.root / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")

    def run_command(self, label, command, cwd):
        print("installed layout phase:", label, flush=True)
        result = run_bounded_process(
            command,
            cwd=cwd,
            environment=self.environment,
            timeout_seconds=900,
            stdout_limit_bytes=8 * 1024**2,
            stderr_limit_bytes=2 * 1024**2,
            error_prefix="installed.layout",
            terminate_descendants=True,
            trace=False,
        )
        for suffix, data in (("stdout", result.stdout), ("stderr", result.stderr)):
            with (self.root / f"{label}.{suffix}").open("xb") as stream:
                stream.write(data)
        record = {
            "phase": label,
            "returncode": result.returncode,
            "elapsed_seconds": result.elapsed_seconds,
            "stdout_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "stderr_sha256": hashlib.sha256(result.stderr).hexdigest(),
        }
        self.results.append(record)
        with (self.root / f"{label}.json").open("x") as stream:
            json.dump(record, stream, indent=2)
        self.assertEqual(
            result.returncode,
            0,
            result.stderr.decode(errors="replace")[-6000:]
            + result.stdout.decode(errors="replace")[-2000:],
        )
        return result

    def cli(self, label, launcher, *arguments, cwd):
        result = json.loads(
            self.run_command(label, [str(launcher), "--json", *arguments], cwd).stdout
        )
        self.assertTrue(result.get("ok"), result)
        return result
