"""Exercise initial command selection and renewal through an exact installed CLI."""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import shlex
import shutil
import sys
from pathlib import Path

from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.retained_harness_readmission import (
    reopen_retained_command_renewal_execution_plan,
)
from literate_ai.adapters.standard_lifecycle_binding import (
    observe_installed_framework_distribution,
)
from literate_ai.contracts import canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore


def require(value, message):
    if not value:
        raise RuntimeError(message)


def main():
    require(
        len(sys.argv) in (4, 5),
        "workspace, distribution, parent and optional case required",
    )
    workspace = Path(sys.argv[1]).absolute()
    expected_distribution, parent_source = sys.argv[2:4]
    case_names = (
        "initial-selection",
        "post-adoption-renewal",
        "refined-component-renewal",
    )
    selected_case = sys.argv[4] if len(sys.argv) == 5 else None
    require(
        selected_case is None or selected_case in case_names, "unknown installed case"
    )
    require(
        sys.flags.isolated and sys.prefix != sys.base_prefix,
        "isolated installation required",
    )
    require(
        os.name == "posix" and shutil.which("make") and shutil.which("cc"),
        "native POSIX Make/C tools required",
    )
    distribution = importlib.metadata.distribution("literate-ai")
    direct_url = distribution.read_text("direct_url.json")
    require(
        not direct_url
        or not json.loads(direct_url).get("dir_info", {}).get("editable"),
        "noneditable wheel required",
    )
    require(
        observe_installed_framework_distribution().identity.uri
        == expected_distribution,
        "installed distribution mismatch",
    )
    prefix = Path(sys.prefix).resolve(strict=True)

    def installed_origins():
        for name, module in tuple(sys.modules.items()):
            if name == "literate_ai" or name.startswith("literate_ai."):
                path = getattr(module, "__file__", None)
                require(
                    path is not None
                    and Path(path).resolve(strict=True).is_relative_to(prefix),
                    "framework imported outside installation",
                )

    installed_origins()
    workspace.mkdir()
    logs = workspace / "logs"
    logs.mkdir(mode=0o700)
    sequence = [0]
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PYTHON") and key != "VIRTUAL_ENV"
    }
    environment.update(
        LITAI_NO_SELF_UPDATE="1",
        CODING_CLI="no-generation-provider",
        LITAI_CODING_PROVIDER="coding-cli",
        BUILD_DIR=str(workspace / "build"),
        OBJ_DIR=str(workspace / "obj"),
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
    )

    def run(arguments, cwd=workspace):
        result = run_bounded_process(
            arguments,
            cwd=cwd,
            environment=environment,
            timeout_seconds=1800,
            stdout_limit_bytes=4 * 1024**2,
            stderr_limit_bytes=64 * 1024,
            terminate_descendants=True,
            trace=False,
            error_prefix="installed.command_renewal",
        )
        sequence[0] += 1
        stem = logs / f"command-{sequence[0]:03d}"
        stem.with_suffix(".stdout").write_bytes(result.stdout)
        stem.with_suffix(".stderr").write_bytes(result.stderr)
        return result

    def cli(*arguments, expected_error=None):
        result = run(
            (sys.executable, "-I", "-m", "literate_ai.cli", "--json", *arguments)
        )
        if expected_error is not None:
            require(result.returncode != 0, "expected command refusal")
            envelope = json.loads(result.stderr)
            code = envelope["error"]["code"]
            require(expected_error in code, f"unexpected refusal code: {code}")
            return code
        require(
            result.returncode == 0,
            "installed command failed: "
            + (result.stderr + result.stdout).decode(errors="replace")[-4000:],
        )
        envelope = json.loads(result.stdout)
        require(envelope["ok"] is True, "installed CLI returned a failed envelope")
        return envelope["result"]

    def git(project, *arguments):
        result = run(("git", *arguments), cwd=project)
        require(result.returncode == 0, "owned fixture Git command failed")

    def selection(path, *, initial=False, help_only=False):
        value = {
            "schema": "literate-ai/monorepo-adoption-selection@1",
            "components": [
                {
                    "name": "native-initial" if initial else "legacy-project-wrapper",
                    "root": ".",
                    "commands": [
                        {
                            "id": "build",
                            "command": "make -f Makefile help"
                            if help_only
                            else "make -f Makefile build-all",
                            "cwd": ".",
                            "evidence": "Makefile",
                        }
                    ],
                }
            ],
            "shared_sources": [],
        }
        if initial:
            # Initial refined ownership explicitly declares its complete harness.
            # Renewal separately overrides only build and retains admitted tests.
            value["components"][0]["commands"].append(
                {
                    "id": "test",
                    "command": "make -f Makefile test",
                    "cwd": ".",
                    "evidence": "Makefile",
                }
            )
        path.write_bytes(canonical_json_bytes(value) + b"\n")

    def current_receipt(project, candidate):
        cli(
            "project",
            "test-receipt",
            "run-retained",
            str(candidate),
            "--project",
            str(project),
            "--worker-id",
            "local",
        )
        cli(
            "project",
            "test-receipt",
            "update",
            str(candidate),
            "--project",
            str(project),
        )
        cli("project", "test-receipt", "require-current", "--project", str(project))
        definition = ProjectConfigurationStore(project).read().definition
        path = project / definition.test_receipt
        return path, path.read_bytes()

    def observations(project, *, compiled):
        records = {}
        context = ProjectConfigurationStore.context(project)
        for name in ("legacy-harness-baseline.json", "legacy-wrapper-parity.json"):
            path = context.framework_path(f".literate/{name}")
            report = json.loads(path.read_bytes())
            require(report["state"] == "passed", "baseline/parity failed")
            phases = {phase["phase"]: phase for phase in report["phases"]}
            require(phases["build"]["exit_code"] == 0, "build command failed")
            output = phases["build"]["stdout_excerpt"].splitlines()
            require(
                ("42" in output) if compiled else ("help-only" in output),
                "native/help behavior missing",
            )
            tests = phases["test"]
            require(
                tests["test_collection"]["total"] == 2
                and tests["test_collection"]["failed"] == 0,
                "original test count changed",
            )
            require(
                "test_original_value" in tests["stderr_excerpt"]
                and "test_c_entrypoint" in tests["stderr_excerpt"],
                "original test identities changed",
            )
            records[name] = hashlib.sha256(path.read_bytes()).hexdigest()
        return records

    results = {}
    for kind in case_names:
        if selected_case is not None and kind != selected_case:
            continue
        refined = kind == "refined-component-renewal"
        project = workspace / kind
        project.mkdir()
        original = {
            "app.py": b"def value():\n    return 42\n",
            "main.c": b'#include <stdio.h>\nint main(void) { puts("42"); return 0; }\n',
            "test_original.py": (
                b"import unittest\nfrom pathlib import Path\nfrom app import value\n"
                b"class OriginalTests(unittest.TestCase):\n"
                b"    def test_original_value(self): self.assertEqual(value(), 42)\n"
                b"    def test_c_entrypoint(self):\n"
                b"        self.assertIn('int main(void)', Path('main.c').read_text())\n"
            ),
            ".gitignore": b"build/\n__pycache__/\n",
            "Makefile": (
                ".PHONY: help build-all test\nhelp:\n\t@printf 'help-only\\n'\n"
                "build-all:\n\tmkdir -p build\n\tcc -o build/native main.c\n"
                '\t@test "$$(./build/native)" = 42\n\t@./build/native\n'
                f"test:\n\t{shlex.quote(sys.executable)} -m unittest -v test_original\n"
            ).encode(),
        }
        for name, content in original.items():
            (project / name).write_bytes(content)
        git(project, "init", "-b", "main")
        git(project, "add", ".")
        git(
            project,
            "-c",
            "user.name=Native Command Fixture",
            "-c",
            "user.email=native@example.invalid",
            "-c",
            "commit.gpgsign=false",
            "commit",
            "-m",
            "Original native application",
        )
        selected = workspace / (kind + ".json")
        selection(
            selected,
            initial=kind == "initial-selection" or refined,
            help_only=refined,
        )
        arguments = (
            "onboard",
            "adopt",
            str(project),
            "--profile",
            "convert",
            "--from",
            parent_source,
            "--default-branch",
            "main",
            "--run-baseline",
        )
        if kind == "initial-selection" or refined:
            arguments += ("--root-plan", str(selected))
        planned = cli(*arguments)
        require(
            not (project / "build/native").exists(), "adoption plan invoked compilation"
        )
        cli(
            *arguments,
            "--apply",
            "--acknowledge",
            "--expect-plan",
            planned["plan_identity"],
        )
        source = project / "components/legacy-project-wrapper/implementation"
        for name, content in original.items():
            require(
                (source / name).read_bytes() == content,
                "adoption changed original source",
            )
        initial = observations(project, compiled=kind == "initial-selection")
        receipt_path, old_receipt = current_receipt(
            project, workspace / (kind + "-old-receipt.json")
        )
        cli(
            "project",
            "convert-stage",
            "advance",
            "--to",
            "retained",
            "--project",
            str(project),
        )
        if kind == "initial-selection":
            results[kind] = {
                "observations": initial,
                "original_tests": 2,
                "receipt_sha256": hashlib.sha256(old_receipt).hexdigest(),
            }
            continue
        prior_component = None
        if refined:
            selected_value = json.loads(selected.read_bytes())
            commands = selected_value["components"][0]["commands"]
            commands[:] = [{**commands[0], "command": "make -f Makefile build-all"}]
            selected.write_bytes(canonical_json_bytes(selected_value) + b"\n")
            component_receipt_path = ProjectConfigurationStore.context(
                project
            ).framework_path(
                ".literate/monorepo-components/receipts/native-initial.json"
            )
            prior_component = component_receipt_path.read_bytes()
        require(
            not (source / "build/native").exists(),
            "help-only path unexpectedly compiled",
        )
        readmit = (
            "project",
            "retained-harness",
            "readmit",
            "--project",
            str(project),
            "--command-selection",
            str(selected),
        )
        plan = cli(*readmit)
        require(
            plan["command_renewal"]["compilation_coverage"] == "unknown",
            "plan inferred compilation",
        )
        require(
            reopen_retained_command_renewal_execution_plan(
                project,
                canonical_json_bytes(plan),
                reviewed_plan_identity=plan["plan_identity"],
                command_selection=selected,
            )
            == plan,
            "installed request read-back changed",
        )
        cli(
            *readmit,
            "--apply",
            "--expected-plan-identity",
            plan["plan_identity"],
            expected_error="acknowledgement",
        )
        result = cli(
            *readmit,
            "--apply",
            "--acknowledge",
            "--expected-plan-identity",
            plan["plan_identity"],
        )
        require(result["applied"] is True, "renewal was not applied")
        renewed = observations(project, compiled=not refined)
        component_observation = None
        if refined:
            require(
                plan["schema"] == "literate-ai/retained-harness-readmission-plan@4",
                "refined execution did not use its distinct request version",
            )
            installed_component = component_receipt_path.read_bytes()
            component_observation = json.loads(installed_component)
            phases = {
                phase["phase"]: phase
                for phase in component_observation["evidence"]["phases"]
            }
            require(
                phases["build"]["exit_code"] == 0
                and phases["build"]["stdout_identity"]
                == "sha256:"
                + hashlib.sha256(
                    b"mkdir -p build\ncc -o build/native main.c\n42\n"
                ).hexdigest(),
                "refined native build/result does not match the actual C harness",
            )
            require(
                phases["test"]["exit_code"] == 0
                and phases["test"]["test_collection"]
                == {
                    "state": "nonempty",
                    "total": 2,
                    "passed": 2,
                    "failed": 0,
                    "known_failed": 0,
                    "skipped": 0,
                },
                "refined renewal did not retain both real original tests",
            )
            require(
                installed_component != prior_component
                and (
                    project
                    / result["prior_evidence_history"]
                    / ".literate/monorepo-components/receipts/native-initial.json"
                ).read_bytes()
                == prior_component,
                "refined renewal lost the original Component receipt",
            )
            require(
                result["component_renewal"]["executed_components"] == ["native-initial"]
                and result["component_renewal"]["qualification_granted"] is False,
                "unexpected refined execution or qualification claim",
            )
        archive = (
            project
            / result["prior_evidence_history"]
            / receipt_path.relative_to(project)
        )
        require(
            archive.read_bytes() == old_receipt
            and receipt_path.read_bytes() == old_receipt,
            "old receipt was rewritten",
        )
        cli(
            "project",
            "test-receipt",
            "require-current",
            "--project",
            str(project),
            expected_error="stale",
        )
        _path, new_receipt = current_receipt(
            project, workspace / (kind + "-renewed-receipt.json")
        )
        require(
            new_receipt != old_receipt and archive.read_bytes() == old_receipt,
            "renewed receipt lost original evidence",
        )
        for name, content in original.items():
            require(
                (source / name).read_bytes() == content,
                "renewal changed original source",
            )
        results[kind] = {
            "help_only": initial,
            "preserved_root_harness" if refined else "compiled": renewed,
            "original_tests": 2,
            "old_receipt_sha256": hashlib.sha256(old_receipt).hexdigest(),
            "new_receipt_sha256": hashlib.sha256(new_receipt).hexdigest(),
            "old_receipt_preserved": True,
        }
        if refined:
            results[kind]["component_execution"] = component_observation
    installed_origins()
    require(
        observe_installed_framework_distribution().identity.uri
        == expected_distribution,
        "installed framework changed",
    )
    print(
        json.dumps(
            {
                "schema": "literate-ai/installed-command-renewal@1",
                "passed": True,
                "distribution": expected_distribution,
                "platform": sys.platform,
                "installed_module_origins_verified": True,
                "cases": results,
                "release_evidence": False,
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
