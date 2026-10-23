"""Isolated bounded traces; never lifecycle qualification or synthetic hardware."""
from __future__ import annotations

import base64
import json
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from literate_ai.adapters._processes import create_process_tree_ownership
from literate_ai.adapters.action_command_dispatch import command_worker_environment
from literate_ai.adapters.action_hardware import HARDWARE_PROTOCOL
from literate_ai.adapters.worker_capabilities import _WINDOWS_SCRIPT
from tests.smoke.test_action_execution_config import ActionExecutionConfigurationTests


def main():
    output = Path("logs/hardware-diagnostic")
    output.mkdir(parents=True, exist_ok=True)
    fixture = ActionExecutionConfigurationTests()
    fixture.setUp()
    try:
        worker = fixture.factory.admission.source.worker
        environment = command_worker_environment(
            worker, fixture.environment, protocol=HARDWARE_PROTOCOL
        )
        results = []

        def run(label, command):
            ownership = create_process_tree_ownership()
            started = time.monotonic()
            expired = False
            with (output / (label + ".stdout")).open("wb") as stdout, (
                output / (label + ".stderr")
            ).open("wb") as stderr:
                process = subprocess.Popen(
                    command, env=environment, stdin=subprocess.DEVNULL,
                    stdout=stdout, stderr=stderr, **ownership.popen_options
                )
                ownership.bind(process.pid)
                try:
                    process.wait(timeout=180)
                except subprocess.TimeoutExpired:
                    expired = True
                    ownership.terminate()
                    if process.poll() is None:
                        process.kill()
                    process.wait(timeout=10)
                finally:
                    ownership.release()
            result = dict(label=label, seconds=round(time.monotonic()-started,3),
                          expired=expired, returncode=process.returncode)
            results.append(result)
            (output / "summary.json").write_text(json.dumps(results, indent=2))
            print(json.dumps(result), flush=True)

        run("cold-import", [sys.executable, "-I", "-X", "importtime",
                            "-m", "literate_ai.action_worker", "--help"])
        for label, application_only in (("original", False), ("application-only", True)):
            script = _WINDOWS_SCRIPT
            if application_only:
                script = script.replace("Get-Command nvidia-smi.exe",
                                        "Get-Command nvidia-smi.exe -CommandType Application")
            lines = []
            for line in script.splitlines():
                stage = None
                for token, name in (("$os=Get-CimInstance", "os-cim"),
                                    ("$cs=Get-CimInstance", "computer-cim"),
                                    ("$cpus=@", "processor-cim"),
                                    ("$smi=Get-Command", "gpu-discovery"),
                                    ("$lines=@", "gpu-query")):
                    if line.strip().startswith(token):
                        stage = name
                        break
                if stage:
                    lines.append("[Console]::Error.WriteLine('begin=" + stage + "')")
                lines.append(line)
                if stage:
                    lines.append("[Console]::Error.WriteLine('end=" + stage + "')")
            encoded = base64.b64encode("\n".join(lines).encode("utf-16le")).decode()
            run(label, ["powershell.exe", "-NoLogo", "-NoProfile",
                        "-NonInteractive", "-EncodedCommand", encoded])
    finally:
        fixture.doCleanups()


if __name__ == "__main__":
    main()
