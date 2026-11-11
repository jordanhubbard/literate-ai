"""Provider state has a private lifetime without weakening finite file limits."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import tempfile
import tomllib
import unittest
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.models import coding_cli as cli
from tests.support.fixtures_test_coding_cli_generation import (
    flavor,
    recipe,
    write_generated_test_suite,
)


def configuration(command):
    result = {}
    for index, argument in enumerate(command[:-1]):
        if argument == "--config":
            result.update(tomllib.loads(command[index + 1]))
    return result


class CodexRuntimeStateTests(unittest.TestCase):
    def test_task_generation_and_status_own_state_through_success_and_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            home = root / "home"
            home.mkdir()
            state_parent = root / "provider state é😀"
            state_parent.mkdir()
            status_workspace = root / "status-workspace"
            status_workspace.mkdir()
            caller = {
                "CODING_CLI": "codex",
                "PATH": "/tools",
                "HOME": str(home),
                "OPENAI_API_KEY": "owned-fixture-key",
            }
            original = dict(caller)
            parent_home = os.environ.get("HOME")
            value = recipe(flavor("python"))
            observed = []
            fail = False

            def execute(command, **kwargs):
                settings = configuration(command)
                state = Path(settings["sqlite_home"])
                log = Path(settings["log_dir"])
                workspace = Path(kwargs["cwd"])
                self.assertTrue(state.is_dir())
                self.assertTrue(log.is_dir())
                self.assertEqual(state.parent, log.parent)
                self.assertFalse(state.is_relative_to(workspace))
                self.assertEqual(kwargs["environment"]["HOME"], str(home))
                with closing(sqlite3.connect(state / "actual.sqlite")) as connection:
                    connection.execute("CREATE TABLE events(value INTEGER)")
                    connection.execute("INSERT INTO events VALUES(7)")
                    connection.commit()
                observed.append(state.parent)
                if fail:
                    raise cli.CodingCliError("coding_cli.timeout", "owned failure")
                if command[-2:] == ("login", "status"):
                    return SimpleNamespace(returncode=1, stdout=b"", stderr=b"")
                task = (workspace / ".literate-ai-task-request.md").exists()
                self.assertEqual(
                    command[command.index("--model") + 1],
                    "fixture-model" if task else "base-codex-model",
                )
                if task:
                    (workspace / ".literate-ai-task-response.json").write_text(
                        '{"ready":true}'
                    )
                else:
                    source = workspace / "source/main.py"
                    source.parent.mkdir()
                    source.write_text("print('hello')\n")
                    write_generated_test_suite(workspace, value)
                return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")

            with (
                mock.patch.object(tempfile, "tempdir", str(state_parent)),
                mock.patch.object(cli.shutil, "which", return_value=sys.executable),
                mock.patch.object(cli, "_run_bounded", side_effect=execute),
            ):
                for failed in (False, True):
                    fail = failed
                    for operation in ("task", "generation"):
                        with self.subTest(operation=operation, failed=failed):
                            before = len(observed)
                            try:
                                if operation == "task":
                                    result = cli.CodingCliTaskRunner(
                                        environment=caller
                                    ).run_json_task(
                                        "Return JSON", model="fixture-model"
                                    )
                                    self.assertEqual(result.response, {"ready": True})
                                else:
                                    selected = cli.CodingCliSourceGenerator(
                                        environment=caller
                                    )
                                    selected.generate(
                                        value,
                                        output_root=root / ("output-" + str(failed)),
                                    )
                            except cli.CodingCliError as error:
                                if not failed:
                                    raise
                                self.assertEqual(error.code, "coding_cli.timeout")
                            else:
                                self.assertFalse(failed, "failure must propagate")
                            attempts = observed[before:]
                            self.assertTrue(attempts)
                            if not (failed and operation == "generation"):
                                self.assertEqual(len(attempts), 1)
                            for attempt in attempts:
                                self.assertFalse(attempt.exists())
                    selection = cli.select_coding_cli(caller)
                    before = len(observed)
                    self.assertEqual(
                        cli._coding_cli_status_requires_authentication(
                            selection, {}, {"HOME": str(home)}, status_workspace
                        ),
                        not failed,
                    )
                    self.assertEqual(len(observed), before + 1)
                    self.assertFalse(observed[-1].exists())
            self.assertEqual(len(set(observed)), len(observed))
            self.assertTrue(all(path.parent == state_parent for path in observed))
            self.assertEqual(caller, original)
            self.assertEqual(os.environ.get("HOME"), parent_home)

    @unittest.skipUnless(os.name == "posix", "native POSIX file limits required")
    def test_native_sqlite_limit_refuses_ambient_state_but_private_state_succeeds(self):
        import resource

        inherited = resource.getrlimit(resource.RLIMIT_FSIZE)
        if any(v != resource.RLIM_INFINITY and v < 512 * 1024 for v in inherited):
            self.skipTest("inherited file budget cannot create the owned large fixture")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            home = root / "home"
            ambient = home / ".codex"
            ambient.mkdir(parents=True)
            database = ambient / "logs_2.sqlite"
            with closing(sqlite3.connect(database)) as connection:
                connection.execute("CREATE TABLE events(value BLOB)")
                connection.execute("INSERT INTO events VALUES(zeroblob(300000))")
                connection.commit()
            journal = root / "observations.jsonl"
            provider = root / "sqlite_provider.py"
            provider.write_text(
                "import json,os,signal,sqlite3,sys,tomllib\n"
                "from pathlib import Path\n"
                "signal.signal(signal.SIGXFSZ,signal.SIG_DFL)\n"
                "settings={}\n"
                "for i,arg in enumerate(sys.argv[:-1]):\n"
                " if arg=='--config':settings.update(tomllib.loads(sys.argv[i+1]))\n"
                "state=Path(settings.get('sqlite_home',"
                "str(Path(os.environ['HOME'])/'.codex')))\n"
                "assert state.is_dir()\n"
                "import resource\n"
                f"with Path({str(journal)!r}).open('a') as stream:\n"
                " stream.write(json.dumps({'state':str(state),"
                "'limits':resource.getrlimit(resource.RLIMIT_FSIZE)})+'\\n')\n"
                "connection=sqlite3.connect(state/'logs_2.sqlite')\n"
                "connection.execute('PRAGMA journal_mode=OFF')\n"
                "connection.execute('CREATE TABLE IF NOT EXISTS events(value BLOB)')\n"
                "connection.execute('INSERT INTO events VALUES(zeroblob(8192))')\n"
                "connection.commit()\n"
                "connection.close()\n"
                "Path('.literate-ai-task-response.json').write_text('{\"ready\":true}')\n"
            )
            limiter = (
                "import os,resource,sys; "
                "soft,hard=resource.getrlimit(resource.RLIMIT_FSIZE); "
                "soft=65536 if soft==resource.RLIM_INFINITY else min(soft,65536); "
                "hard=65536 if hard==resource.RLIM_INFINITY else min(hard,65536); "
                "resource.setrlimit(resource.RLIMIT_FSIZE,(soft,hard)); "
                "os.execvpe(sys.argv[1],sys.argv[1:],os.environ)"
            )
            real_run = cli._run_bounded
            native_exits = []

            def execute(command, **kwargs):
                # Only the provider transport is a fixture. The exact framework
                # argv, OS process limit and SQLite writes are actually exercised.
                result = real_run(
                    (
                        sys.executable,
                        "-I",
                        "-S",
                        "-c",
                        limiter,
                        sys.executable,
                        "-I",
                        "-B",
                        str(provider),
                        *command[1:],
                    ),
                    **kwargs,
                )
                native_exits.append(result.returncode)
                return result

            environment = {
                "CODING_CLI": "codex",
                "HOME": str(home),
                "PATH": "/tools",
                "OPENAI_API_KEY": "owned-fixture-key",
            }
            with mock.patch.object(cli.shutil, "which", return_value=sys.executable):
                runner = cli.CodingCliTaskRunner(environment=environment)
            with mock.patch.object(cli, "_run_bounded", side_effect=execute):
                with mock.patch.object(
                    cli, "_codex_runtime_arguments", return_value=()
                ):
                    with self.assertRaises(cli.CodingCliError):
                        runner.run_json_task("Return JSON", model="fixture-model")
                self.assertNotEqual(native_exits[-1], 0)
                before = hashlib.sha256(database.read_bytes()).hexdigest()
                result = runner.run_json_task("Return JSON", model="fixture-model")
                self.assertEqual(result.response, {"ready": True})
                self.assertEqual(native_exits[-1], 0)
                self.assertEqual(
                    hashlib.sha256(database.read_bytes()).hexdigest(), before
                )
            observations = [json.loads(x) for x in journal.read_text().splitlines()]
            self.assertEqual(len(observations), 2)
            self.assertEqual(observations[0]["state"], str(ambient))
            private = Path(observations[1]["state"])
            self.assertNotEqual(private, ambient)
            self.assertFalse(private.exists())
            self.assertEqual([x["limits"] for x in observations], [[65536, 65536]] * 2)
            self.assertEqual(resource.getrlimit(resource.RLIMIT_FSIZE), inherited)

    def test_workspace_overlap_refuses_and_other_providers_allocate_no_codex_state(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            with mock.patch.object(tempfile, "tempdir", str(workspace)):
                with self.assertRaises(cli.CodingCliError) as caught:
                    with cli._coding_cli_runtime_state(
                        SimpleNamespace(name="codex"), workspace=workspace
                    ):
                        self.fail("overlapping state must not be yielded")
            self.assertEqual(caught.exception.code, "coding_cli.runtime_state_overlap")
            self.assertEqual(list(workspace.iterdir()), [])
            with mock.patch.object(
                tempfile, "TemporaryDirectory", side_effect=AssertionError("allocation")
            ):
                for provider in ("claude", "cursor-agent", "opencode"):
                    with cli._coding_cli_runtime_state(
                        SimpleNamespace(name=provider), workspace=workspace
                    ) as selected:
                        self.assertIsNone(selected)
