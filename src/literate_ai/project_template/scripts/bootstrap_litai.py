"""Read-only bootstrap check for a generated Literate AI project.

This file uses only the Python standard library so it works before LitAI exists.
It never installs packages or changes the project pin.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import threading
import time
import types
from contextlib import suppress
from pathlib import Path

_OUTPUT_LIMIT = 1024 * 1024
_OWNER_DIGEST = "26ecb3c53bec50fb967f586628a7f75739f8eefb258c557620626e196c0dd67c"


def _process_owner():
    """Load only the bundled, reviewed stdlib helper, including under Python -I."""
    path = Path(__file__).with_name("_bootstrap_processes.py")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0)
    )
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_size > 65536:
            raise ValueError("Bootstrap process helper is not a bounded regular file")
        content = stream.read(65537)
    if (
        len(content) != opened.st_size
        or hashlib.sha256(content).hexdigest() != _OWNER_DIGEST
    ):
        raise ValueError("Bootstrap process helper does not match its reviewed content")
    module = types.ModuleType("_litai_bootstrap_owner")
    name = f"_litai_bootstrap_owner_{id(module)}"
    module.__name__ = name
    sys.modules[name] = module
    try:
        exec(compile(content, str(path), "exec"), module.__dict__)
    finally:
        sys.modules.pop(name, None)
    return module


def _probe_now() -> float:
    return time.monotonic()


def _owned_probe_launcher(command: list[str]) -> int:
    # Windows: do not start the selected executable until the controller has
    # assigned this waiting launcher to its Job. Descendants then inherit it.
    if sys.stdin.buffer.read(3) != b"go\n" or not command:
        return 1
    return subprocess.call(command, stdin=subprocess.DEVNULL)


def _run_version_probe(command: list[str], *, cwd: Path, timeout: float = 30):
    owner_module = _process_owner()
    process = None
    readers = []
    buffers = [bytearray(), bytearray()]
    errors = []
    failed = threading.Event()

    def drain(stream, buffer):
        try:
            while chunk := stream.read(65536):
                if len(buffer) + len(chunk) > _OUTPUT_LIMIT:
                    raise ValueError(
                        "LitAI version check output exceeded its byte bound"
                    )
                buffer.extend(chunk)
        except (OSError, ValueError):
            errors.append(
                "LitAI version check output could not be captured within its bound"
            )
            failed.set()

    ownership = owner_module.create_process_tree_ownership()
    try:
        deadline = _probe_now() + timeout
        if os.name == "nt" and ownership.job is None:
            raise ValueError("Bootstrap process Job ownership is unavailable")
        selected = command
        if os.name == "nt":
            selected = [
                sys.executable,
                "-I",
                str(Path(__file__).resolve()),
                "--_owned-probe",
                *command,
            ]
        process = subprocess.Popen(
            selected,
            cwd=cwd,
            stdin=subprocess.PIPE if os.name == "nt" else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            **ownership.popen_options,
        )
        ownership.bind(process.pid)
        if os.name == "nt":
            if ownership.job is None:
                raise ValueError("Bootstrap process Job assignment failed")
            process.stdin.write(b"go\n")
            process.stdin.close()
        for stream, buffer in zip(
            (process.stdout, process.stderr), buffers, strict=True
        ):
            reader = threading.Thread(target=drain, args=(stream, buffer), daemon=True)
            reader.start()
            readers.append(reader)
        while True:
            if failed.is_set():
                raise ValueError(
                    "LitAI version check output exceeded its capture bound"
                )
            if _probe_now() >= deadline:
                raise subprocess.TimeoutExpired(command, timeout)
            returncode = process.poll()
            if returncode is not None:
                break
            failed.wait(0.01)
    finally:
        # Retire the original group/Job even after a successful launcher exit;
        # otherwise closed-stdio helpers can survive an apparently ready probe.
        try:
            if process is not None:
                owner_module.terminate_process_tree(process, ownership=ownership)
                with suppress(subprocess.TimeoutExpired):
                    process.wait(timeout=1)
        finally:
            ownership.release()
            join_deadline = time.monotonic() + 1
            for reader in readers:
                reader.join(max(0, join_deadline - time.monotonic()))
            if process is not None:
                for stream in (process.stdin, process.stdout, process.stderr):
                    if stream is not None:
                        stream.close()
    if any(reader.is_alive() for reader in readers):
        raise ValueError(
            "LitAI version check readers did not retire within their bound"
        )
    if errors:
        raise ValueError(errors[0])
    return subprocess.CompletedProcess(
        command, returncode, buffers[0].decode("utf-8"), buffers[1].decode("utf-8")
    )


def _native_directory(path: Path) -> None:
    # Bootstrap intentionally precedes framework imports. Select the same finite
    # declared root/contained layout using stdlib-only, no-follow inspections.
    for ancestor in (*reversed(path.parents), path):
        observed = ancestor.lstat()
        if not stat.S_ISDIR(observed.st_mode) or (
            getattr(observed, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            raise ValueError("Bootstrap project ancestry is redirected or unavailable")


def _native_manifest(path: Path, *, _observed=None) -> dict[str, object]:
    _native_directory(path.parent)
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode) or (
        getattr(before, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    ):
        raise ValueError("Bootstrap project manifest is redirected or unavailable")
    flags = (
        os.O_RDONLY
        | getattr(os, "O_NOFOLLOW", 0)
        | getattr(os, "O_NONBLOCK", 0)
        | getattr(os, "O_BINARY", 0)
    )
    with os.fdopen(os.open(path, flags), "rb") as stream:
        opened = os.fstat(stream.fileno())
        if not stat.S_ISREG(opened.st_mode) or opened.st_size > 1024 * 1024:
            raise ValueError(
                "Bootstrap project manifest exceeds its regular-file bound"
            )
        content = stream.read(1024 * 1024 + 1)
        after = os.fstat(stream.fileno())
    _native_directory(path.parent)
    final = path.lstat()

    def identity(value):
        return (
            value.st_dev,
            value.st_ino,
            value.st_mode,
            value.st_nlink,
            value.st_size,
            value.st_mtime_ns,
        )

    # Windows Python 3.12 exposes creation time through pathname ctime and
    # native ChangeTime through fstat. Keep both clocks within their own channel.
    if not (
        identity(before) == identity(opened) == identity(after) == identity(final)
        and before.st_ctime_ns == final.st_ctime_ns
        and opened.st_ctime_ns == after.st_ctime_ns
    ):
        raise ValueError("Bootstrap project manifest changed during read")
    if len(content) != opened.st_size:
        raise ValueError("Bootstrap project manifest changed size during read")
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("Bootstrap project manifest must be an object")
    if _observed is not None:
        _observed.append(
            (path, content, identity(final), final.st_ctime_ns, after.st_ctime_ns)
        )
    return value


def _declared_project(project: Path, *, _observed=None):
    project = project.absolute()
    _native_directory(project)
    direct = project / "literate.project.json"
    child = project / "litai"
    contained = child / "literate.project.json"
    if os.path.lexists(child):
        _native_directory(child)
    if os.path.lexists(contained):
        definition = _native_manifest(contained, _observed=_observed)
        if definition.get("framework_directory") == "litai":
            if os.path.lexists(direct):
                raise ValueError("Root and contained project manifests are ambiguous")
            return project, contained, definition
    definition = _native_manifest(direct, _observed=_observed)
    if definition.get("framework_directory") == "litai":
        if project.name != "litai" or os.path.lexists(
            project.parent / "literate.project.json"
        ):
            raise ValueError(
                "Declared contained project manifest has the wrong location"
            )
        return project.parent, direct, definition
    return project, direct, definition


def _check_snapshot(
    project: Path, executable: str | None, observed
) -> dict[str, object]:
    try:
        project, manifest, definition = _declared_project(project, _observed=observed)
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
            "detail": "LitAI is not on PATH; follow "
            + (
                manifest.parent.relative_to(project) / "docs/user/bootstrap.md"
            ).as_posix(),
        }
    try:
        completed = _run_version_probe(
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
            timeout=30,
        )
        output = completed.stdout if completed.stdout.strip() else completed.stderr
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


def check(project: Path, executable: str | None) -> dict[str, object]:
    observed = []
    result = _check_snapshot(project, executable, observed)
    if observed:
        try:
            current = []
            _declared_project(project, _observed=current)
            if current != observed:
                raise ValueError("Bootstrap project changed during runtime check")
        except (OSError, UnicodeError, ValueError, KeyError, TypeError) as error:
            return {"state": "project-invalid", "ok": False, "detail": str(error)}
    return result


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
        else check(args.project.absolute(), args.litai)
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
    if len(sys.argv) > 1 and sys.argv[1] == "--_owned-probe":
        raise SystemExit(_owned_probe_launcher(sys.argv[2:]))
    raise SystemExit(main())
