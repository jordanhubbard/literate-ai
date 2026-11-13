"""Read-only bootstrap check for a generated Literate AI project.

This file uses only the Python standard library so it works before LitAI exists.
It never installs packages or changes the project pin.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path


def check(project: Path, executable: str | None) -> dict[str, object]:
    manifest = project / "literate.project.json"
    try:
        definition = json.loads(manifest.read_text(encoding="utf-8"))
        driver = definition["lifecycle_driver"]
        if not isinstance(driver, dict):
            raise ValueError("project has no Standard framework distribution pin")
        pin = driver.get("framework_distribution_identity")
        if driver.get("binding") != "standard" or not isinstance(pin, dict):
            raise ValueError("project has no Standard framework distribution pin")
        if pin.get("algorithm") != "sha256" or not isinstance(pin.get("digest"), str):
            raise ValueError("project framework distribution pin is invalid")
        digest = pin["digest"]
        if len(digest) != 64 or any(
            character not in "0123456789abcdef" for character in digest
        ):
            raise ValueError("project framework distribution pin is invalid")
    except (
        OSError,
        UnicodeError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
    ) as exc:
        return {"state": "project-invalid", "ok": False, "detail": str(exc)}
    required = "sha256:" + digest
    selected = executable or shutil.which("litai")
    if not selected:
        return {
            "state": "missing",
            "ok": False,
            "required_distribution": required,
            "detail": "LitAI is not on PATH; follow docs/user/bootstrap.md",
        }
    try:
        completed = subprocess.run(
            [
                selected,
                "--json",
                "version",
                "check",
                "--project",
                str(project),
                "--require-project",
            ],
            cwd=project,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        output = completed.stdout if completed.stdout.strip() else completed.stderr
        if len(output) > 1024 * 1024:
            raise ValueError("LitAI version check output exceeded its bound")
        envelope = json.loads(output)
        report = envelope["result"]
        project_report = report["project"]
        matches = project_report["derived_identities"]["driver_identity_matches"]
    except (
        OSError,
        UnicodeError,
        ValueError,
        KeyError,
        TypeError,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
    ) as exc:
        return {
            "state": "check-unavailable",
            "ok": False,
            "required_distribution": required,
            "detail": f"Installed LitAI could not verify this project: {exc}",
        }
    if matches is not True:
        diagnostic = project_report.get("derived_identities", {}).get(
            "driver_resolution_error"
        )
        return {
            "state": "incompatible",
            "ok": False,
            "required_distribution": required,
            "detail": diagnostic or "Installed LitAI does not satisfy this project",
        }
    if completed.returncode or not envelope.get("ok") or not report.get("ok"):
        return {
            "state": "check-failed",
            "ok": False,
            "required_distribution": required,
            "detail": (
                "The installed runtime matches the pin, but another version "
                "check failed; inspect `litai --json version check --project . "
                "--require-project`"
            ),
        }
    return {
        "state": "ready",
        "ok": True,
        "required_distribution": required,
        "detail": "Installed LitAI matches the project pin",
    }


def verify_wheel(path: Path, expected: str) -> dict[str, object]:
    if len(expected) != 64 or any(
        character not in "0123456789abcdefABCDEF" for character in expected
    ):
        return {
            "state": "checksum-invalid",
            "ok": False,
            "detail": (
                "Provide the wheel's 64-character SHA-256 from its trusted source"
            ),
        }
    try:
        with path.open("rb") as stream:
            actual = hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError as exc:
        return {
            "state": "wheel-unavailable",
            "ok": False,
            "detail": f"Wheel could not be read: {exc}",
        }
    if actual != expected.lower():
        return {
            "state": "checksum-mismatch",
            "ok": False,
            "detail": (
                "Wheel SHA-256 differs from the supplied checksum; do not install it"
            ),
        }
    return {
        "state": "wheel-verified",
        "ok": True,
        "detail": "Wheel file matches the supplied SHA-256",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument(
        "--litai", help="explicit LitAI executable from an isolated environment"
    )
    parser.add_argument(
        "--wheel", type=Path, help="wheel file to verify before installation"
    )
    parser.add_argument("--wheel-sha256", help="trusted SHA-256 of the wheel file")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if sys.version_info < (3, 11):  # noqa: UP036 - bootstrap reports older hosts
        result = {
            "state": "python-incompatible",
            "ok": False,
            "detail": "Python 3.11 or newer is required before LitAI setup",
        }
        if args.json:
            print(json.dumps(result, sort_keys=True))
        else:
            print(f"LitAI bootstrap: {result['state']}")
            print(result["detail"])
        return 1
    if bool(args.wheel) != bool(args.wheel_sha256):
        parser.error("--wheel and --wheel-sha256 must be supplied together")
    result = (
        verify_wheel(args.wheel, args.wheel_sha256)
        if args.wheel is not None
        else check(args.project.resolve(), args.litai)
    )
    if args.json:
        print(json.dumps(result, sort_keys=True))
    else:
        print(f"LitAI bootstrap: {result['state']}")
        required = result.get("required_distribution", "unavailable")
        print(f"Required distribution: {required}")
        print(result["detail"])
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
