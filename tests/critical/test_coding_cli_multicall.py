"""A pinned native image retains its selected CLI name without reopening PATH."""

import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters.models import coding_cli as cli


@unittest.skipUnless(
    os.name == "posix" and shutil.which("cc"), "native POSIX C compiler"
)
class CodingCliMulticallTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="cli-multicall-image-")
        cls.addClassCleanup(temporary.cleanup)
        root = Path(temporary.name)
        source = root / "launcher.c"
        cls.image = root / "multicall"
        source.write_text(
            "#include <stdio.h>\n#include <string.h>\n#include <unistd.h>\n"
            "int main(int argc, char **argv) {\n"
            ' if (strcmp(argv[0], "codex") && strcmp(argv[0], "claude") &&\n'
            '     strcmp(argv[0], "cursor-agent") && strcmp(argv[0], "opencode"))\n'
            "  return 79;\n"
            ' if (argc == 3 && !strcmp(argv[1], "--helper")) {\n'
            "  int ready[2]; char started;\n"
            "  if (pipe(ready)) return 80;\n"
            "  pid_t child = fork(); if (child < 0) return 81;\n"
            "  if (!child) {\n"
            "   close(ready[0]);\n"
            '   if (write(ready[1], "!", 1) != 1) _exit(82);\n'
            "   close(ready[1]);\n"
            "   close(1); close(2); usleep(600000);\n"
            '   FILE *out = fopen(argv[2], "w");\n'
            '   if (out) { fputs("survived", out); fclose(out); }\n'
            "   _exit(0);\n"
            "  }\n"
            "  close(ready[1]);\n"
            "  if (read(ready[0], &started, 1) != 1) return 83;\n"
            "  close(ready[0]);\n"
            " }\n"
            " puts(argv[0]); return 0;\n}\n"
        )
        compiled = subprocess.run(
            [shutil.which("cc"), str(source), "-o", str(cls.image)],
            capture_output=True,
            timeout=30,
        )
        if compiled.returncode:
            raise AssertionError(compiled.stderr.decode(errors="replace"))

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="cli-multicall-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.binary = self.root / "original-image"
        shutil.copy2(self.image, self.binary)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        for name in cli.CODING_CLIS:
            (self.bin / name).symlink_to(self.binary)

    def select(self, name):
        return cli.select_coding_cli({"CODING_CLI": name, "PATH": str(self.bin)})

    def run_selected(self, selection, *arguments):
        return cli._run_bounded(
            (selection.name, *arguments),
            selection=selection,
            cwd=self.root,
            environment={"PATH": str(self.bin)},
            timeout_seconds=5,
            maximum_stdout_bytes=1024,
            maximum_stderr_bytes=1024,
        )

    def test_all_native_cli_names_reach_the_original_pinned_image(self):
        for name in cli.CODING_CLIS:
            with self.subTest(name=name):
                selection = self.select(name)
                self.assertEqual(selection.executable, str(self.binary))
                identity = selection.executable_identity
                result = self.run_selected(selection, "--version")
                self.assertEqual(result.returncode, 0)
                self.assertEqual(result.stdout, name.encode() + b"\n")
                self.assertEqual(result.stderr, b"")
                selection.require_unchanged()
                self.assertEqual(selection.executable_identity, identity)

    def test_alias_retarget_cannot_redirect_the_selected_image(self):
        selection = self.select("codex")
        alias = self.bin / "codex"
        alias.unlink()
        alias.symlink_to("/definitely-unavailable-provider")
        result = self.run_selected(selection, "--version")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"codex\n")
        selection.require_unchanged()

    def test_image_drift_refuses_before_spawn(self):
        selection = self.select("codex")
        with self.binary.open("ab") as stream:
            stream.write(b"changed image")
        with mock.patch.object(cli, "run_bounded_process", side_effect=AssertionError):
            with self.assertRaises(cli.CodingCliError) as caught:
                self.run_selected(selection, "--version")
        self.assertEqual(caught.exception.code, "coding_cli.executable_drift")

    def test_authentication_probe_keeps_image_and_invocation_distinct(self):
        report = cli.inspect_coding_cli_authentication(
            {"CODING_CLI": "codex", "PATH": str(self.bin)}
        )
        self.assertEqual(report["state"], "authenticated")
        self.assertEqual(report["executable"], str(self.binary))
        self.assertEqual(report["status_command"], ["codex", "login", "status"])

    def test_authentication_probe_refuses_image_changed_after_native_return(self):
        def run_then_change(*args, **kwargs):
            result = subprocess.run(*args, **kwargs)
            self.assertEqual(result.returncode, 0)
            with self.binary.open("ab") as stream:
                stream.write(b"changed after native return")
            return result

        with self.assertRaises(cli.CodingCliError) as caught:
            cli.inspect_coding_cli_authentication(
                {"CODING_CLI": "codex", "PATH": str(self.bin)}, runner=run_then_change
            )
        self.assertEqual(caught.exception.code, "coding_cli.executable_drift")
        self.assertTrue(
            self.binary.read_bytes().endswith(b"changed after native return")
        )

    def test_pinned_factory_still_retires_native_helpers(self):
        marker = self.root / "survived"
        result = self.run_selected(self.select("codex"), "--helper", str(marker))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout, b"codex\n")
        time.sleep(0.8)
        self.assertFalse(marker.exists())


class CodingCliWindowsLauncherRouteTests(unittest.TestCase):
    def test_batch_keeps_existing_route_and_native_image_uses_explicit_pin(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            with mock.patch.object(cli, "_is_windows_host", return_value=True):
                for suffix in (".cmd", ".BAT", ".exe"):
                    with self.subTest(suffix=suffix):
                        executable = str(root / ("codex" + suffix))
                        selection = cli.CodingCliSelection(
                            "codex", executable, "sha256:" + "a" * 64
                        )
                        self.assertEqual(
                            cli._coding_cli_argv0(selection),
                            "codex" if suffix == ".exe" else executable,
                        )
                        self.assertEqual(
                            cli._coding_cli_launch_options(selection),
                            {"executable": executable} if suffix == ".exe" else {},
                        )
