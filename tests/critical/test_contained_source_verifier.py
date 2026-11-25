"""Actual local candidate/test processes; model preparation is explicit fixture data."""

import shutil
import stat
import sys
import time
import unittest
from contextlib import nullcontext
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import project_runtime, scaffold_custody
from literate_ai.adapters.builders import run_bounded_process
from literate_ai.adapters.project_runtime import (
    allocate_project_runtime,
    close_project_runtime,
    project_runtime_scope,
)
from literate_ai.cli import generation as cli
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_runtime_cli as fixture
from tests.support.fixtures_test_cli_generation import bind_tree
from tests.support.fixtures_test_standard_source_admission import generation


class ContainedSourceVerifierTests(unittest.TestCase):
    def setUp(self):
        self.f = fixture.ProjectLayoutRuntimeCliTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.source = self.f.project.root / "candidate"
        suite = self.source / "source/tests"
        suite.mkdir(parents=True)
        (suite / "manifest.json").write_text('{"cases":[{}]}')
        (self.source / "empty/nested").mkdir(parents=True)
        self.authored = self.source / "source/app.py"
        self.authored.write_bytes(b"VALUE = 42\n")
        self.authored.chmod(0o755)
        self.original = self.authored.stat()
        self.generated = bind_tree(generation(), self.source)
        self.owner = allocate_project_runtime(self.f.project, nested=True)
        self.addCleanup(self.close)
        self.seen = []
        self.timeout = None
        self.children = []
        self.script = (
            "import pathlib,stat;root=pathlib.Path.cwd();"
            "assert (root/'source/app.py').read_bytes()==b'VALUE = 42\\n';"
            "assert stat.S_IMODE((root/'source/app.py').stat().st_mode)==493;"
            "assert (root/'empty/nested').is_dir();"
            "(root/'test-output').write_bytes(b'owned original test output')"
        )

    def close(self):
        if self.owner is not None:
            owner, self.owner = self.owner, None
            close_project_runtime(owner, keep=False)

    def verify(self, after=None, project=None):
        def observe(original):
            def run(command, *args, **kwargs):
                self.seen.append(kwargs["cwd"])
                if "timeout_seconds" in kwargs and self.timeout is not None:
                    kwargs["timeout_seconds"] = self.timeout
                    kwargs["poll_interval_seconds"] = 0.01
                result = original(command, *args, **kwargs)
                if after is not None:
                    after(kwargs["cwd"])
                return result

            return run

        # The original public admission caller already has this actual project.
        # Before the fix its constructor loses it; both routes execute real tests.
        options = (
            {"project": self.f.project if project is None else project}
            if "project" in cli._CommandSourceVerifier.__dataclass_fields__
            else {}
        )
        verifier = cli._CommandSourceVerifier(
            self.source,
            self.generated.output.candidate.source_manifest_identity,
            ((sys.executable, "-I", "-c", self.script),),
            **options,
        )
        scope = (
            project_runtime_scope(self.owner, self.f.project)
            if self.owner is not None
            else nullcontext()
        )
        with scope:
            with (
                patch.object(
                    cli, "run_with_tree_kill", observe(cli.run_with_tree_kill)
                ),
                patch.object(
                    cli,
                    "run_bounded_process",
                    observe(run_bounded_process),
                    create=True,
                ),
            ):
                return verifier.verify(self.generated)

    def test_02_original_test_copy_is_contained_and_retires(self):
        self.verify()
        self.assertEqual(len(self.seen), 1)
        self.assertTrue(
            self.seen[0].is_relative_to(self.f.framework / "_build"), self.seen
        )
        self.assertFalse(self.seen[0].exists())
        self.assertEqual(self.authored.stat().st_ino, self.original.st_ino)
        self.assertEqual(self.authored.read_bytes(), b"VALUE = 42\n")
        self.assertEqual(stat.S_IMODE(self.authored.stat().st_mode), 0o755)

    def test_00_private_state_after_original_process_is_preserved(self):
        paths = []

        def private(directory):
            path = directory / "operator-private"
            path.write_bytes(b"retain private source verifier state")
            paths.append((path, path.stat().st_ino))

        try:
            self.verify(private)
        except (ValueError, cli.CliFailure):
            pass
        self.close()
        path, inode = paths[0]
        self.assertTrue(
            path.exists(), "original recursive cleanup deleted private state"
        )
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(path.read_bytes(), b"retain private source verifier state")

    def test_equal_byte_foreign_test_output_is_retained(self):
        paths = []

        def replace_output(directory):
            path = directory / "test-output"
            retained = self.f.project.root / "retained-original-test-output"
            path.rename(retained)
            shutil.copyfile(retained, path)
            paths.append((path, path.stat().st_ino, retained, retained.stat().st_ino))

        with self.assertRaises(cli.CliFailure) as caught:
            self.verify(replace_output)
        self.assertEqual(caught.exception.code, "source_admission.source_changed")
        self.close()
        path, inode, retained, original = paths[0]
        self.assertNotEqual(inode, original)
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(retained.stat().st_ino, original)
        self.assertEqual(path.read_bytes(), retained.read_bytes())

    def test_original_failed_command_wins_over_private_cleanup(self):
        self.script += ";raise SystemExit(7)"
        paths = []

        def private(directory):
            path = directory / "operator-private"
            path.write_bytes(b"retain failed-command state")
            paths.append((path, path.stat().st_ino))

        with self.assertRaises(cli.CliFailure) as caught:
            self.verify(private)
        self.assertEqual(caught.exception.code, "source_admission.tests_failed")
        self.assertTrue(
            any("disposal refused" in n for n in caught.exception.__notes__)
        )
        self.close()
        path, inode = paths[0]
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(path.read_bytes(), b"retain failed-command state")

    def test_original_callback_error_identity_survives_private_disposal(self):
        refused = RuntimeError("original source verifier callback rejection")
        paths = []

        def reject(directory):
            path = directory / "operator-private"
            path.write_bytes(b"retain original rejection")
            paths.append((path, path.stat().st_ino))
            raise refused

        with self.assertRaises(RuntimeError) as caught:
            self.verify(reject)
        self.assertIs(caught.exception, refused)
        self.assertTrue(any("disposal refused" in n for n in refused.__notes__))
        self.close()
        path, inode = paths[0]
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(path.read_bytes(), b"retain original rejection")

    def test_foreign_equal_byte_source_copy_cannot_inherit_cleanup(self):
        paths = []

        def foreign(directory):
            path = directory / "source/app.py"
            retained = self.f.project.root / "retained-original-source-copy"
            path.rename(retained)
            shutil.copyfile(retained, path)
            path.chmod(0o755)
            paths.append((path, path.stat().st_ino, retained, retained.stat().st_ino))

        with self.assertRaises(cli.CliFailure) as caught:
            self.verify(foreign)
        self.assertEqual(caught.exception.code, "source_admission.source_changed")
        self.close()
        path, inode, retained, original = paths[0]
        self.assertNotEqual(inode, original)
        self.assertEqual(path.stat().st_ino, inode)
        self.assertEqual(retained.stat().st_ino, original)
        self.assertEqual(path.read_bytes(), retained.read_bytes())
        self.assertEqual(self.authored.stat().st_ino, self.original.st_ino)

    def test_actual_candidate_mutation_refuses_after_command(self):
        self.script += (
            ";pathlib.Path(" + repr(str(self.authored)) + ").write_bytes(b'changed')"
        )
        with self.assertRaises(cli.CliFailure) as caught:
            self.verify()
        self.assertEqual(caught.exception.code, "source_admission.source_changed")
        self.assertEqual(self.authored.read_bytes(), b"changed")
        self.assertFalse(self.seen[0].exists())

    def test_drift_before_command_refuses_without_process(self):
        self.authored.write_bytes(b"changed")
        with self.assertRaises(cli.CliFailure) as caught:
            self.verify()
        self.assertEqual(caught.exception.code, "source_admission.source_changed")
        self.assertEqual(self.seen, [])

    def test_actual_output_overflow_and_timeout_refuse_and_retire_owned_copy(self):
        for script, timeout in (
            ("import sys;sys.stdout.buffer.write(b'x'*1048577)", None),
            ("import time;time.sleep(60)", 0.15),
        ):
            with self.subTest(script=script):
                self.script, self.timeout = script, timeout
                with self.assertRaises(cli.CliFailure) as caught:
                    self.verify()
                self.assertEqual(caught.exception.code, "source_admission.tests_failed")
                self.assertFalse(self.seen[-1].exists())

    def test_standalone_declared_receiver_uses_original_project(self):
        self.close()
        self.verify()
        self.assertTrue(self.seen[0].is_relative_to(self.f.framework / "_build"))
        self.assertFalse(self.seen[0].exists())

    def test_foreign_active_runtime_cannot_supply_receiving_authority(self):
        other = self.f.project.root.parent / "foreign-source-test-receiver"
        store = ProjectConfigurationStore(other)
        store.create(
            replace(self.f.project.definition, project_id="foreign-source-test")
        )
        from literate_ai.projects import load_project

        with self.assertRaises(cli.CliFailure) as caught:
            self.verify(project=load_project(other))
        self.assertEqual(caught.exception.code, "source_admission.source_changed")
        self.assertEqual(self.seen, [])
        self.assertFalse((other / "litai/_build").exists())

    def test_readonly_source_overlap_refuses_before_original_allocation(self):
        original_source = self.source
        for source in (self.f.project.root, self.owner.path):
            with self.subTest(source=source):
                self.source = source
                with patch.object(
                    project_runtime,
                    "evidence_staging",
                    side_effect=AssertionError("allocated in read-only source"),
                ) as allocate:
                    with self.assertRaises(cli.CliFailure) as caught:
                        self.verify()
                self.assertEqual(
                    caught.exception.code, "source_admission.source_changed"
                )
                allocate.assert_not_called()
        self.source = original_source
        self.assertEqual(self.seen, [])
        self.assertEqual(self.authored.read_bytes(), b"VALUE = 42\n")

    def test_standalone_readonly_overlap_refuses_before_lock_control_creation(self):
        self.close()
        self.source = self.f.project.root
        with patch.object(
            scaffold_custody,
            "prepare_scaffold_inspection_control",
            side_effect=AssertionError("created control in read-only source"),
        ) as prepare:
            with self.assertRaises(cli.CliFailure) as caught:
                self.verify()
        self.assertEqual(caught.exception.code, "source_admission.source_changed")
        prepare.assert_not_called()
        self.assertEqual(self.seen, [])
        self.assertEqual(self.authored.read_bytes(), b"VALUE = 42\n")

    def test_successful_original_test_stops_background_writer_before_consumer(self):
        child = (
            "import pathlib,time\n"
            "with pathlib.Path('background-counter').open('ab',buffering=0) as f:\n"
            " while True:\n  f.write(b'x')\n  time.sleep(0.01)\n"
        )
        self.script = (
            "import pathlib,subprocess,sys,time\n"
            "subprocess.Popen([sys.executable,'-I','-c'," + repr(child) + "],"
            "stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)\n"
            "path=pathlib.Path('background-counter')\n"
            "deadline=time.monotonic()+5\n"
            "while (not path.exists() or path.stat().st_size==0) "
            "and time.monotonic()<deadline:\n"
            " time.sleep(0.01)\n"
            "assert path.exists()\n"
        )
        observed = []

        def consume(directory):
            path = directory / "background-counter"
            before = path.read_bytes()
            self.assertGreater(len(before), 0)
            time.sleep(0.1)
            self.assertEqual(path.read_bytes(), before)
            observed.append(before)

        self.verify(consume)
        self.assertEqual(len(observed), 1)
        self.assertFalse(self.seen[0].exists())
        self.assertEqual(self.authored.read_bytes(), b"VALUE = 42\n")

    def test_missing_or_aliased_source_keeps_original_cli_refusal(self):
        original = self.source
        alias = self.f.project.root / "candidate-alias"
        alias.symlink_to(original, target_is_directory=True)
        for path in (self.f.project.root / "missing-candidate", alias):
            with self.subTest(path=path):
                self.source = path
                with self.assertRaises(cli.CliFailure) as caught:
                    self.verify()
                self.assertEqual(
                    caught.exception.code, "source_admission.source_changed"
                )
        self.source = original
        self.assertEqual(self.seen, [])
        self.assertEqual(self.authored.read_bytes(), b"VALUE = 42\n")
