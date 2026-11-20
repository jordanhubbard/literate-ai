"""Real Git sync must preserve raw bytes and recover without converting checkout."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.cli import main
from literate_ai.cli import shadow as shadow_module
from tests.support.native_repository import git_at


def _git(root: Path, *arguments: str) -> str:
    return git_at(root, *arguments).decode().strip()


def _run_owned(command, timeout):
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("GIT_")
    }
    if sys.pycache_prefix is not None:
        environment["PYTHONPYCACHEPREFIX"] = sys.pycache_prefix
    else:
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
    return run_bounded_process(
        command,
        cwd=None,
        environment=environment,
        timeout_seconds=timeout,
        stdout_limit_bytes=64 * 1024,
        stderr_limit_bytes=64 * 1024,
        error_prefix="shadow.test-process",
        terminate_descendants=True,
        trace=False,
    )


class ShadowSyncCustodyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.upstream = self.root / "upstream"
        self.upstream.mkdir()
        self.shadow = self.root / "shadow"
        _git(self.upstream, "init", "-q", "-b", "main")
        _git(self.upstream, "config", "user.name", "Shadow Test")
        _git(self.upstream, "config", "user.email", "shadow@example.test")
        _git(
            self.upstream, "remote", "add", "origin", "git@github.com:owner/example.git"
        )
        self.readme = self.upstream / "README.md"
        self.readme.write_bytes(b"initial\n")
        _git(self.upstream, "add", "README.md")
        _git(self.upstream, "commit", "-qm", "initial")
        remote = patch.object(
            shadow_module,
            "_remote_heads",
            side_effect=lambda upstream, refs: {
                ref: _git(upstream, "rev-parse", f"{ref}^{{commit}}") for ref in refs
            },
        )
        remote.start()
        self.addCleanup(remote.stop)
        self.create_shadow()

    def create_shadow(self):
        location = ("--upstream", str(self.upstream), "--shadow", str(self.shadow))
        status, planned = self.invoke("plan", *location)
        self.assertEqual(status, 0, planned)
        status, created = self.invoke(
            "create",
            *location,
            "--expect-plan",
            planned["result"]["plan_identity"],
            "--acknowledge",
        )
        self.assertEqual(status, 0, created)

    def invoke(self, *arguments):
        stdout, stderr = StringIO(), StringIO()
        status = main(("--json", "shadow", *arguments), stdout=stdout, stderr=stderr)
        return status, json.loads((stderr if status else stdout).getvalue())

    def plan_sync(self):
        self.readme.write_bytes(self.readme.read_bytes() + b"advanced\n")
        _git(self.upstream, "commit", "-qam", "advance")
        status, planned = self.invoke("sync", "plan", "--shadow", str(self.shadow))
        self.assertEqual(status, 0, planned)
        return planned["result"]["plan_identity"]

    def apply(self, identity, *extra):
        return self.invoke(
            "sync",
            "apply",
            "--shadow",
            str(self.shadow),
            "--expect-plan",
            identity,
            "--acknowledge",
            *extra,
        )

    def test_configured_filters_never_run_during_sync(self):
        marker = self.root / "filter-executed"
        script = self.root / "filter.py"
        script.write_text(
            "import sys\nfrom pathlib import Path\n"
            f"Path({str(marker)!r}).write_bytes(b'executed')\n"
            "sys.stdout.buffer.write(sys.stdin.buffer.read())\n",
            encoding="utf-8",
        )
        command = shlex.join([Path(sys.executable).as_posix(), script.as_posix()])
        for direction in ("clean", "smudge"):
            _git(self.shadow, "config", f"filter.marker.{direction}", command)
        info = self.shadow / ".git" / "info"
        info.mkdir(exist_ok=True)
        (info / "attributes").write_text("* filter=marker\n", encoding="utf-8")
        identity = self.plan_sync()
        self.assertFalse(marker.exists())
        status, applied = self.apply(identity)
        self.assertEqual(status, 0, applied)
        self.assertFalse(marker.exists(), "sync executed a repository content filter")
        status, state = self.invoke("status", "--shadow", str(self.shadow))
        self.assertEqual(status, 0, state)
        self.assertTrue(state["result"]["upstream_current"])

    def test_missing_acknowledgement_does_not_create_write_locks(self):
        identity = self.plan_sync()
        status, result = self.invoke(
            "sync",
            "apply",
            "--shadow",
            str(self.shadow),
            "--expect-plan",
            identity,
        )
        self.assertEqual(status, 2, result)
        self.assertEqual(result["error"]["code"], "shadow.acknowledgement_required")
        for name in (
            "index.lock",
            "literate-shadow.lock",
            "literate-shadow.pending.json",
        ):
            self.assertFalse((self.shadow / ".git" / name).exists())

    def test_directory_entry_link_hint_does_not_replace_full_stat(self):
        objects = self.shadow / ".git" / "objects"
        leaf = next(path for path in objects.rglob("*") if path.is_file())
        actual_scandir = os.scandir
        observed = []

        class StatHint:
            st_nlink = 0

            def __init__(self, actual):
                self.actual = actual

            def __getattr__(self, name):
                return getattr(self.actual, name)

        class EntryHint:
            def __init__(self, actual):
                self.actual = actual
                observed.append(actual.path)

            def __getattr__(self, name):
                return getattr(self.actual, name)

            def __fspath__(self):
                return os.fspath(self.actual)

            def stat(self, *, follow_symlinks=True):
                return StatHint(self.actual.stat(follow_symlinks=follow_symlinks))

        with actual_scandir(leaf.parent) as entries:
            entry = next(item for item in entries if item.name == leaf.name)
            self.assertEqual(EntryHint(entry).stat(follow_symlinks=False).st_nlink, 0)
        self.assertEqual(os.stat(leaf, follow_symlinks=False).st_nlink, 1)

        class HintedScandir:
            def __init__(self, path="."):
                self.entries = actual_scandir(path)
                self.selected = not isinstance(path, int) and Path(
                    os.fsdecode(path)
                ).is_relative_to(objects)

            def __iter__(self):
                return self

            def __next__(self):
                entry = next(self.entries)
                return EntryHint(entry) if self.selected else entry

            def __enter__(self):
                self.entries.__enter__()
                return self

            def __exit__(self, *args):
                return self.entries.__exit__(*args)

            def close(self):
                self.entries.close()

        with patch("literate_ai.cli.shadow.os.scandir", side_effect=HintedScandir):
            iterator = os.scandir(self.root)
            with iterator:
                self.assertIs(iter(iterator), iterator)
                list(iterator)
            iterator.close()
            status, state = self.invoke("status", "--shadow", str(self.shadow))
            self.assertEqual(status, 0, state)
            identity = self.plan_sync()
            status, result = self.apply(identity)
            self.assertEqual(status, 0, result)
        self.assertGreater(len(observed), 1)

    def test_hardlinked_git_object_refuses_without_touching_foreign_bytes(self):
        identity = self.plan_sync()
        objects = self.shadow / ".git" / "objects"
        leaf = next(path for path in objects.rglob("*") if path.is_file())
        foreign = self.root / "foreign-object"
        try:
            os.link(leaf, foreign)
        except OSError:
            self.skipTest("hardlinks are unavailable on this filesystem")
        before, modified = foreign.read_bytes(), foreign.stat().st_mtime_ns
        status, result = self.apply(identity)
        self.assertEqual(status, 2, result)
        self.assertEqual(result["error"]["code"], "shadow.root_invalid")
        self.assertEqual(foreign.read_bytes(), before)
        self.assertEqual(foreign.stat().st_mtime_ns, modified)

    def test_configured_fsmonitor_is_disabled_for_status_and_sync(self):
        marker = self.root / "fsmonitor-executed"
        script = self.root / "fsmonitor.py"
        script.write_text(
            "import sys\nfrom pathlib import Path\n"
            f"Path({str(marker)!r}).write_bytes(b'executed')\n"
            "sys.stdout.buffer.write(b'test-token\\x00/\\x00')\n",
            encoding="utf-8",
        )
        _git(
            self.shadow,
            "config",
            "core.fsmonitor",
            shlex.join([Path(sys.executable).as_posix(), script.as_posix()]),
        )
        _git(self.shadow, "config", "core.fsmonitorHookVersion", "2")
        negative = _run_owned(
            ["git", "-C", str(self.shadow), "status", "--porcelain"], 10
        )
        self.assertEqual(negative.returncode, 0, negative.stderr)
        self.assertTrue(marker.exists(), "fixture must prove the configured hook runs")
        marker.unlink()
        status, state = self.invoke("status", "--shadow", str(self.shadow))
        self.assertEqual(status, 0, state)
        identity = self.plan_sync()
        self.assertFalse(marker.exists())
        status, result = self.apply(identity)
        self.assertEqual(status, 0, result)
        self.assertFalse(marker.exists(), "custody invoked a configured fsmonitor")

    def test_process_exit_after_index_retention_can_resume_from_disk(self):
        identity = self.plan_sync()
        code = (
            "import os,sys\n"
            "from literate_ai.cli import main\n"
            "from literate_ai.cli import shadow\n"
            "shadow._remote_heads=lambda upstream,refs:{"
            "ref:shadow._git(upstream,'rev-parse',ref+'^{commit}') for ref in refs}\n"
            "move=shadow.move_file_between_owned_parents_exclusive\n"
            "def stop_after_index(source,destination,**keywords):\n"
            " move(source,destination,**keywords)\n"
            " if destination.name == 'previous.index': os._exit(86)\n"
            "shadow.move_file_between_owned_parents_exclusive=stop_after_index\n"
            "raise SystemExit(main(['--json','shadow','sync','apply','--shadow',"
            "sys.argv[1],'--expect-plan',sys.argv[2],'--acknowledge']))\n"
        )
        child = _run_owned(
            [sys.executable, "-c", code, str(self.shadow), identity],
            30,
        )
        self.assertEqual(child.returncode, 86, child.stderr)
        git = self.shadow / ".git"
        self.assertFalse((git / "index").exists())
        self.assertTrue((git / "index.lock").is_file())
        status, result = self.apply(identity, "--resume")
        self.assertEqual(status, 0, result)
        self.assertFalse((git / "index.lock").exists())
        self.assertFalse((git / "literate-shadow.pending.json").exists())
        self.assertEqual(self.invoke("status", "--shadow", str(self.shadow))[0], 0)

    def test_normal_git_writer_is_excluded_while_index_is_reserved(self):
        identity = self.plan_sync()
        real_git = shadow_module._git
        commit = _git(self.shadow, "rev-parse", "HEAD")
        observed = []

        def writer_before_private_read_tree(root, *arguments, **keywords):
            index_path = (keywords.get("environment") or {}).get("GIT_INDEX_FILE")
            if (
                root == self.shadow
                and arguments[0] == "read-tree"
                and index_path
                and Path(index_path).name == "next.index"
            ):
                before = (self.shadow / ".git" / "index").read_bytes()
                writer = _run_owned(
                    [
                        "git",
                        "-C",
                        str(root),
                        "update-index",
                        "--add",
                        "--cacheinfo",
                        f"160000,{commit},FOREIGN",
                    ],
                    10,
                )
                self.assertNotEqual(writer.returncode, 0)
                self.assertIn(b"index.lock", writer.stderr)
                self.assertEqual((self.shadow / ".git" / "index").read_bytes(), before)
                observed.append(writer.returncode)
            return real_git(root, *arguments, **keywords)

        with patch.object(
            shadow_module, "_git", side_effect=writer_before_private_read_tree
        ):
            status, result = self.apply(identity)
        self.assertEqual(status, 0, result)
        self.assertEqual(len(observed), 1)

    def test_shared_git_administration_refuses_before_pending_access(self):
        identity = self.plan_sync()
        self.interrupt_after_move(identity, 1)
        pending = self.shadow / ".git" / "literate-shadow.pending.json"
        before = pending.read_bytes()
        (self.shadow / ".git" / "commondir").write_text(
            str(self.upstream / ".git"), encoding="utf-8"
        )
        status, result = self.apply(identity, "--resume")
        self.assertEqual(status, 2, result)
        self.assertEqual(result["error"]["code"], "shadow.root_invalid")
        self.assertEqual(pending.read_bytes(), before)

    def interrupt_after_move(self, identity, ordinal):
        move = shadow_module.move_file_between_owned_parents_exclusive
        count = 0

        def interrupt(*arguments, **keywords):
            nonlocal count
            move(*arguments, **keywords)
            count += 1
            if count == ordinal:
                raise OSError("Simulated interruption after a completed move")

        with patch.object(
            shadow_module,
            "move_file_between_owned_parents_exclusive",
            side_effect=interrupt,
        ):
            status, result = self.apply(identity)
        self.assertEqual(status, 2, result)
        self.assertEqual(result["error"]["code"], "shadow.pending_conflict")
        self.assertEqual(count, ordinal)

    def test_each_publication_boundary_resumes_with_retained_old_metadata(self):
        for ordinal in range(1, 10):
            with self.subTest(after_move=ordinal):
                if ordinal > 1:
                    self.shadow = self.root / f"shadow-{ordinal}"
                    self.create_shadow()
                old = {
                    name: (self.shadow / ".literate-shadow" / name).read_bytes()
                    for name in ("registry.json", "journal.jsonl")
                }
                identity = self.plan_sync()
                self.interrupt_after_move(identity, ordinal)
                pending = self.shadow / ".git" / "literate-shadow.pending.json"
                status, result = self.apply(
                    identity, *(("--resume",) if pending.exists() else ())
                )
                self.assertEqual(status, 0, result)
                self.assertFalse(pending.exists())
                commit = _git(self.shadow, "rev-parse", "HEAD")
                recovery = self.shadow / ".git" / ("literate-shadow.apply-" + commit)
                for index, name in enumerate(old):
                    self.assertEqual(
                        (recovery / f"{index}.old").read_bytes(), old[name]
                    )
                completed = (
                    self.shadow
                    / ".git"
                    / ("literate-shadow.completed-" + commit + ".json")
                )
                self.assertEqual(
                    json.loads(completed.read_bytes())["plan_identity"], identity
                )
                self.assertEqual(
                    self.invoke("status", "--shadow", str(self.shadow))[0], 0
                )

    def test_foreign_destination_after_backup_is_preserved(self):
        identity = self.plan_sync()
        self.interrupt_after_move(identity, 1)
        registry = self.shadow / ".literate-shadow" / "registry.json"
        self.assertFalse(registry.exists())
        registry.write_bytes(b"foreign writer payload\n")
        status, result = self.apply(identity, "--resume")
        self.assertEqual(status, 2, result)
        self.assertEqual(result["error"]["code"], "shadow.pending_conflict")
        self.assertEqual(registry.read_bytes(), b"foreign writer payload\n")
        registry.unlink()  # The fixture owns this deliberate collision.
        self.assertEqual(self.apply(identity, "--resume")[0], 0)

    def test_foreign_stage_and_hidden_index_are_preserved(self):
        identity = self.plan_sync()
        self.interrupt_after_move(identity, 1)
        commit = _git(self.shadow, "rev-parse", "HEAD")
        stage = self.shadow / ".git" / ("literate-shadow.apply-" + commit)
        before = (stage / "0.old").read_bytes()
        foreign = stage / "peer.txt"
        foreign.write_bytes(b"preserve stage peer\n")
        status, result = self.apply(identity, "--resume")
        self.assertEqual(status, 2, result)
        self.assertEqual(result["error"]["code"], "shadow.pending_conflict")
        self.assertEqual(foreign.read_bytes(), b"preserve stage peer\n")
        self.assertEqual((stage / "0.old").read_bytes(), before)
        foreign.unlink()
        _git(self.shadow, "config", "diff.ignoreSubmodules", "all")
        main_index = self.shadow / ".git" / "index"
        original_bytes = main_index.read_bytes()
        foreign_index = self.root / "foreign-recovery.index"
        environment = {"GIT_INDEX_FILE": str(foreign_index)}
        shadow_module._git(self.shadow, "read-tree", commit, environment=environment)
        shadow_module._git(
            self.shadow,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{commit},FOREIGN",
            environment=environment,
        )
        os.replace(foreign_index, main_index)
        index_before = main_index.read_bytes()
        status, result = self.apply(identity, "--resume")
        self.assertEqual(status, 2, result)
        self.assertEqual(result["error"]["code"], "shadow.pending_conflict")
        self.assertEqual(main_index.read_bytes(), index_before)
        self.assertEqual((stage / "0.old").read_bytes(), before)
        main_index.write_bytes(original_bytes)  # Restore this fixture-owned collision.
        self.assertEqual(self.apply(identity, "--resume")[0], 0)

    def test_redirected_git_directory_refuses_before_pending_access(self):
        identity = self.plan_sync()
        self.interrupt_after_move(identity, 1)
        git = self.shadow / ".git"
        retained = self.root / "retained-git"
        git.rename(retained)
        try:
            git.symlink_to(retained, target_is_directory=True)
        except OSError:
            retained.rename(git)
            self.skipTest("directory symlinks require additional platform permission")
        pending = (retained / "literate-shadow.pending.json").read_bytes()
        status, result = self.apply(identity, "--resume")
        self.assertEqual(status, 2, result)
        self.assertEqual(result["error"]["code"], "shadow.root_invalid")
        self.assertEqual(
            (retained / "literate-shadow.pending.json").read_bytes(), pending
        )

    def test_index_writer_at_read_tree_boundary_is_preserved(self):
        identity = self.plan_sync()
        foreign = self.root / "foreign.index"
        environment = {"GIT_INDEX_FILE": str(foreign)}
        commit = _git(self.shadow, "rev-parse", "HEAD")
        shadow_module._git(self.shadow, "read-tree", commit, environment=environment)
        shadow_module._git(
            self.shadow,
            "update-index",
            "--add",
            "--cacheinfo",
            f"160000,{commit},FOREIGN",
            environment=environment,
        )
        foreign_bytes = foreign.read_bytes()
        real_git = shadow_module._git
        injected = False

        def publish_foreign_before_read_tree(root, *arguments, **keywords):
            nonlocal injected
            index_path = (keywords.get("environment") or {}).get("GIT_INDEX_FILE")
            if (
                not injected
                and root == self.shadow
                and arguments[0] == "read-tree"
                and (index_path is None or Path(index_path).name == "next.index")
            ):
                os.replace(foreign, self.shadow / ".git" / "index")
                injected = True
            return real_git(root, *arguments, **keywords)

        with patch.object(
            shadow_module, "_git", side_effect=publish_foreign_before_read_tree
        ):
            status, result = self.apply(identity)
        self.assertTrue(injected)
        self.assertEqual((self.shadow / ".git" / "index").read_bytes(), foreign_bytes)
        self.assertEqual(status, 2, result)
        self.assertEqual(result["error"]["code"], "shadow.pending_conflict")

    def test_git_ref_parent_alias_cannot_redirect_sync_into_foreign_storage(self):
        identity = self.plan_sync()
        heads = self.shadow / ".git" / "refs" / "heads"
        saved, foreign = self.root / "saved-heads", self.root / "foreign-heads"
        heads.rename(saved)
        shutil.copytree(saved, foreign)
        try:
            heads.symlink_to(foreign, target_is_directory=True)
        except OSError:
            saved.rename(heads)
            self.skipTest("directory symlinks require additional platform permission")
        before = (foreign / "main").read_bytes()
        status, result = self.apply(identity)
        self.assertEqual((foreign / "main").read_bytes(), before)
        self.assertEqual(status, 2, result)
        self.assertEqual(result["error"]["code"], "shadow.root_invalid")


if __name__ == "__main__":
    unittest.main()
