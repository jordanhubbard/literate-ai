from __future__ import annotations

import contextlib
import hashlib
import json
import os
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters.repository_lineage import (
    REPOSITORY_PARENT_FILE,
    GitRepositoryLineageError,
    GitRepositorySnapshotProvider,
    repository_parent_reference,
)
from literate_ai.application.repository_lineage import resolve_repository_lineage
from literate_ai.contracts import (
    ContentIdentity,
    RepositoryParentReference,
    RepositoryParentSelection,
)

ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = str(ROOT / "src")

# A standalone child-process body (run via `python -c`, not `multiprocessing`)
# that acquires `lock_path`, signals readiness by creating `ready_path`, then
# blocks. Deliberately outside `multiprocessing`: a `multiprocessing.Process`
# holds Event/semaphore state that a SIGKILL leaves in a half-torn-down state,
# hanging the *parent* interpreter's shutdown waiting on its resource
# tracker -- a plain OS process avoids that entirely and is what a genuinely
# crashed owner looks like.
_LOCK_HOLDER_CHILD_SOURCE = """
import sys, time
from pathlib import Path
lock_path = Path(sys.argv[1])
ready_path = Path(sys.argv[2])
sys.path.insert(0, sys.argv[3])
from literate_ai._cache_lock import exclusive_cache_lock
with exclusive_cache_lock(lock_path):
    ready_path.write_text("ready")
    time.sleep(30)
"""

_RESOLVER_CHILD_SOURCE = """
import contextlib, json, sys, time
from pathlib import Path
sys.path.insert(0, sys.argv[1])
from literate_ai.adapters import repository_lineage as lineage
from literate_ai.adapters.builders._process import run_bounded_process

repository, cache, coordination = map(Path, sys.argv[2:5])
name = sys.argv[5]
stage, revision = sys.argv[6:8]
real_lock = lineage.exclusive_cache_lock

@contextlib.contextmanager
def observed_lock(path):
    (coordination / (name + ".attempt")).touch()
    with real_lock(path):
        yield

def runner(command, **kwargs):
    if stage in command:
        (coordination / (name + "." + stage)).touch()
        deadline = time.monotonic() + 40
        while not (coordination / (name + ".release")).exists():
            if time.monotonic() >= deadline:
                raise RuntimeError("parent did not release the fetch probe")
            time.sleep(0.01)
    return run_bounded_process(command, **kwargs)

lineage.exclusive_cache_lock = observed_lock
provider = lineage.GitRepositorySnapshotProvider(cache, process_runner=runner)
resolved = provider.resolve(
    lineage.repository_parent_reference(str(repository) + "#" + revision)
)
print(json.dumps({"revision": resolved.resolved_revision,
                  "project_id": resolved.project_id}), flush=True)
"""


def _stop_child(process: subprocess.Popen[str]) -> None:
    if process.poll() is None:
        process.kill()
    process.communicate(timeout=15)


def git(repository: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository,
        env={**os.environ, "LC_ALL": "C"},
        stdin=subprocess.DEVNULL,
        capture_output=True,
        text=True,
        check=False,
    )
    if completed.returncode != 0:
        raise AssertionError(completed.stderr)
    return completed.stdout.strip()


def create_repository(
    parent: Path,
    name: str,
    selection: RepositoryParentSelection,
    *,
    include_parent: bool = True,
) -> Path:
    repository = parent / name
    repository.mkdir()
    git(repository, "init")
    git(repository, "config", "user.name", "Literate AI Test")
    git(repository, "config", "user.email", "litai@example.invalid")
    manifest = json.loads((ROOT / "literate.project.json").read_bytes())
    manifest["project_id"] = name
    (repository / "literate.project.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    if include_parent:
        destination = repository / REPOSITORY_PARENT_FILE
        destination.parent.mkdir(parents=True)
        destination.write_text(
            json.dumps(selection.to_dict(), indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
    git(repository, "add", ".")
    git(repository, "commit", "-m", f"Create {name}")
    return repository


def reference(repository: Path) -> RepositoryParentReference:
    return RepositoryParentReference(repository.resolve().as_uri(), "HEAD")


class GitRepositorySnapshotProviderTests(unittest.TestCase):
    def test_cached_objects_use_complete_metadata_instead_of_directory_hints(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repository = create_repository(
                temporary, "parent", RepositoryParentSelection.root()
            )
            revision = git(repository, "rev-parse", "HEAD")
            pinned = RepositoryParentReference(repository.resolve().as_uri(), revision)
            provider = GitRepositorySnapshotProvider(temporary / "cache")
            self.assertEqual(provider.resolve(pinned).resolved_revision, revision)
            actual_scandir = os.scandir

            class CachedDirectoryEntry:
                def __init__(self, entry):
                    self.entry = entry

                def __getattr__(self, name):
                    return getattr(self.entry, name)

                def stat(self, *, follow_symlinks=True):
                    actual = self.entry.stat(follow_symlinks=follow_symlinks)
                    fields = {
                        name: getattr(actual, name)
                        for name in dir(actual)
                        if name.startswith("st_")
                    }
                    fields["st_nlink"] = 0
                    return SimpleNamespace(**fields)

            @contextlib.contextmanager
            def windows_directory_hints(path):
                with actual_scandir(path) as entries:
                    yield (CachedDirectoryEntry(entry) for entry in entries)

            with patch.object(os, "scandir", windows_directory_hints):
                self.assertEqual(provider.resolve(pinned).resolved_revision, revision)

    def test_hard_linked_cached_object_is_still_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repository = create_repository(
                temporary, "parent", RepositoryParentSelection.root()
            )
            revision = git(repository, "rev-parse", "HEAD")
            pinned = RepositoryParentReference(repository.resolve().as_uri(), revision)
            cache = temporary / "cache"
            provider = GitRepositorySnapshotProvider(cache)
            provider.resolve(pinned)
            bare = cache / (
                hashlib.sha256(pinned.repository_url.encode()).hexdigest() + ".git"
            )
            backing = next(
                path for path in (bare / "objects").rglob("*") if path.is_file()
            )
            original = backing.read_bytes()
            mode = stat.S_IMODE(backing.stat().st_mode)
            outside = temporary / "borrowed-object"
            try:
                os.link(backing, outside)
            except OSError as exc:
                self.skipTest(f"requires file hard links: {exc}")
            try:
                with self.assertRaises(GitRepositoryLineageError) as refused:
                    provider.resolve(pinned)
                self.assertEqual(
                    refused.exception.code, "repository_lineage.cache_unsafe"
                )
                self.assertEqual(outside.read_bytes(), original)
            finally:
                # Windows Git objects are read-only; restore the owned fixture's
                # original mode after removing the additional link.
                outside.chmod(mode | stat.S_IWUSR)
                outside.unlink()
                backing.chmod(mode)
            self.assertEqual(provider.resolve(pinned).resolved_revision, revision)

    def test_redirected_cached_object_refuses_before_using_external_backing(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repository = create_repository(
                temporary, "parent", RepositoryParentSelection.root()
            )
            revision = git(repository, "rev-parse", "HEAD")
            pinned = RepositoryParentReference(repository.resolve().as_uri(), revision)
            cache = temporary / "cache"
            provider = GitRepositorySnapshotProvider(cache)
            provider.resolve(pinned)
            bare = cache / (
                hashlib.sha256(pinned.repository_url.encode()).hexdigest() + ".git"
            )
            loose = bare / "objects" / revision[:2] / revision[2:]
            backing = (
                loose
                if loose.is_file()
                else next((bare / "objects/pack").glob("*.pack"))
            )
            outside = temporary / "outside-object"
            backing.rename(outside)
            try:
                try:
                    backing.symlink_to(outside)
                except OSError as exc:
                    self.skipTest(
                        f"object-link control requires symlink support: {exc}"
                    )
                with self.assertRaises(GitRepositoryLineageError) as redirected:
                    provider.resolve(pinned)
                self.assertEqual(
                    redirected.exception.code, "repository_lineage.cache_unsafe"
                )
            finally:
                if backing.is_symlink():
                    backing.unlink()
                outside.rename(backing)
            self.assertEqual(provider.resolve(pinned).resolved_revision, revision)

    def test_exact_cached_authority_survives_remote_loss_without_staling_mutable_refs(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repository = create_repository(
                temporary, "parent", RepositoryParentSelection.root()
            )
            catalog_file = repository / "flavors/example/flavor.md"
            catalog_file.parent.mkdir(parents=True)
            catalog_file.write_text("original catalog\n", encoding="utf-8")
            git(repository, "add", ".")
            git(repository, "commit", "-m", "Publish original catalog")
            revision = git(repository, "rev-parse", "HEAD")
            pinned = RepositoryParentReference(repository.resolve().as_uri(), revision)
            cache = temporary / "cache"
            provider = GitRepositorySnapshotProvider(cache)
            lineage = resolve_repository_lineage(
                RepositoryParentSelection.inherit((pinned,)), provider
            )
            node = lineage.nodes[0]

            # This removes the real transport target, rather than mocking an
            # object read or supplying a pre-approved catalog result.
            unavailable = temporary / "unavailable"
            repository.rename(unavailable)
            try:
                self.assertEqual(provider.resolve(pinned).resolved_revision, revision)
                catalog = provider.catalog(node)
                self.assertEqual(len(catalog.files), 1)
                self.assertEqual(catalog.files[0].content, b"original catalog\n")
            finally:
                unavailable.rename(repository)

            manifest = repository / "literate.project.json"
            value = json.loads(manifest.read_bytes())
            value["project_id"] = "advanced-parent"
            manifest.write_text(json.dumps(value) + "\n", encoding="utf-8")
            catalog_file.write_text("new catalog\n", encoding="utf-8")
            git(repository, "add", ".")
            git(repository, "commit", "-m", "Advance mutable parent")
            advanced = provider.resolve(reference(repository))
            self.assertEqual(advanced.project_id, "advanced-parent")
            self.assertEqual(
                advanced.resolved_revision, git(repository, "rev-parse", "HEAD")
            )
            self.assertNotEqual(advanced.resolved_revision, revision)

            key = hashlib.sha256(pinned.repository_url.encode()).hexdigest()
            bare = cache / (key + ".git")
            git(bare, "replace", revision, advanced.resolved_revision)
            self.assertEqual(provider.resolve(pinned).project_id, "parent")
            self.assertEqual(
                provider.catalog(node).files[0].content, b"original catalog\n"
            )
            with self.assertRaises(GitRepositoryLineageError) as wrong_identity:
                provider.catalog(
                    replace(
                        node,
                        project_identity=ContentIdentity.parse_uri(
                            "sha256:" + "f" * 64
                        ),
                    )
                )
            self.assertEqual(
                wrong_identity.exception.code, "repository_lineage.project_changed"
            )

            alternate = bare / "objects/info/alternates"
            alternate.write_text(
                str(repository / ".git/objects") + "\n", encoding="utf-8"
            )
            try:
                with self.assertRaises(GitRepositoryLineageError) as redirected:
                    provider.resolve(pinned)
                self.assertEqual(
                    redirected.exception.code, "repository_lineage.cache_unsafe"
                )
            finally:
                alternate.unlink()
            self.assertEqual(provider.resolve(pinned).project_id, "parent")

            # Older supported Git versions do not implement the lazy-fetch
            # suppression variable. A promisor cache must refuse before any
            # object read can delegate to that transport.
            git(bare, "config", "remote.cache-control.promisor", "true")
            try:
                with self.assertRaises(GitRepositoryLineageError) as partial:
                    provider.resolve(pinned)
                self.assertEqual(
                    partial.exception.code, "repository_lineage.cache_unsafe"
                )
            finally:
                git(bare, "config", "--remove-section", "remote.cache-control")
            self.assertEqual(provider.resolve(pinned).project_id, "parent")

    def test_cli_source_rejects_embedded_credentials_without_echoing_them(self) -> None:
        secret = "do-not-repeat"
        with self.assertRaises(GitRepositoryLineageError) as raised:
            repository_parent_reference(
                f"https://user:{secret}@example.test/parent.git"
            )
        self.assertEqual(raised.exception.code, "repository_lineage.source_invalid")
        self.assertNotIn(secret, str(raised.exception))

    def test_reads_a_three_repository_chain_without_checkout_or_hook_execution(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            root = create_repository(
                temporary, "root", RepositoryParentSelection.root()
            )
            marker = temporary / "hook-ran"
            hook = root / ".git" / "hooks" / "post-checkout"
            hook.parent.mkdir(parents=True, exist_ok=True)
            hook.write_text(
                f"#!/bin/sh\nprintf ran > {marker}\n",
                encoding="utf-8",
                newline="\n",
            )
            hook.chmod(hook.stat().st_mode | stat.S_IXUSR)
            parent = create_repository(
                temporary,
                "parent",
                RepositoryParentSelection.inherit((reference(root),)),
            )
            selected = create_repository(
                temporary,
                "selected",
                RepositoryParentSelection.inherit((reference(parent),)),
            )
            provider = GitRepositorySnapshotProvider(temporary / "cache")

            lineage = resolve_repository_lineage(
                RepositoryParentSelection.inherit((reference(selected),)), provider
            )

            self.assertEqual(
                tuple(item.project_id for item in lineage.nodes),
                ("root", "parent", "selected"),
            )
            self.assertTrue(
                all(len(item.resolved_revision) == 40 for item in lineage.nodes)
            )
            self.assertFalse(marker.exists())
            self.assertFalse(any((temporary / "cache").rglob(".git/index")))

    def test_missing_parent_authority_fails_instead_of_truncating_the_chain(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            incomplete = create_repository(
                temporary,
                "incomplete",
                RepositoryParentSelection.root(),
                include_parent=False,
            )
            provider = GitRepositorySnapshotProvider(temporary / "cache")

            with self.assertRaises(GitRepositoryLineageError) as raised:
                provider.resolve(reference(incomplete))
        self.assertEqual(raised.exception.code, "repository_lineage.authority_missing")

    def test_separate_processes_serialize_same_repository_fetches(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            contextlib.ExitStack() as stack,
        ):
            temporary = Path(directory)
            repository = create_repository(
                temporary, "first", RepositoryParentSelection.root()
            )
            revision = git(repository, "rev-parse", "HEAD")

            def start(name: str) -> subprocess.Popen[str]:
                process = subprocess.Popen(
                    [
                        sys.executable,
                        "-c",
                        _RESOLVER_CHILD_SOURCE,
                        SRC_ROOT,
                        str(repository),
                        str(temporary / "cache"),
                        str(temporary),
                        name,
                        "fetch",
                        "HEAD",
                    ],
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                )
                stack.callback(_stop_child, process)
                return process

            def wait_for(marker: str, process: subprocess.Popen[str]) -> None:
                deadline = time.monotonic() + 20
                while not (temporary / marker).exists():
                    if process.poll() is not None:
                        stdout, stderr = process.communicate(timeout=5)
                        self.fail(f"child exited before {marker}: {stdout}\n{stderr}")
                    self.assertLess(time.monotonic(), deadline, marker)
                    time.sleep(0.01)

            first = start("first")
            wait_for("first.fetch", first)
            second = start("second")
            wait_for("second.attempt", second)
            # Hold the first real fetch while the second process attempts
            # the same OS lock. It must not reach its fetch until release.
            deadline = time.monotonic() + 0.5
            while time.monotonic() < deadline:
                self.assertIsNone(second.poll())
                self.assertFalse((temporary / "second.fetch").exists())
                time.sleep(0.01)
            (temporary / "first.release").touch()
            wait_for("second.fetch", second)
            (temporary / "second.release").touch()
            for process in (first, second):
                stdout, stderr = process.communicate(timeout=30)
                self.assertEqual(process.returncode, 0, stderr)
                self.assertEqual(
                    json.loads(stdout), {"revision": revision, "project_id": "first"}
                )

    def test_an_interrupted_lock_owner_does_not_leave_an_unrecoverable_lock(
        self,
    ) -> None:
        """A process holding the per-entry lock that is killed outright (no
        graceful shutdown, no `finally` block executed) must not leave a
        permanently stuck lock behind: the OS-level advisory lock is tied to
        the killed process's file descriptor and is released when that
        descriptor closes, so a subsequent resolve should succeed promptly
        rather than exhaust the lock-acquisition timeout."""

        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            repository = create_repository(
                temporary, "interrupted", RepositoryParentSelection.root()
            )
            cache_root = (temporary / "cache").resolve()
            cache_root.mkdir()
            selected = reference(repository)
            key = hashlib.sha256(selected.repository_url.encode("utf-8")).hexdigest()
            lock_path = cache_root / f"{key}.lock"
            ready_path = temporary / "lock-holder-ready"

            holder = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    _LOCK_HOLDER_CHILD_SOURCE,
                    str(lock_path),
                    str(ready_path),
                    SRC_ROOT,
                ]
            )
            try:
                deadline = time.monotonic() + 15
                while time.monotonic() < deadline and not ready_path.exists():
                    time.sleep(0.02)
                self.assertTrue(
                    ready_path.exists(), "lock holder never acquired the lock"
                )

                # Popen.kill is SIGKILL on POSIX and TerminateProcess on
                # Windows: neither runs the holder's Python finally blocks.
                holder.kill()
                returncode = holder.wait(timeout=15)
                if os.name == "posix":
                    self.assertEqual(returncode, -signal.SIGKILL)
                else:
                    self.assertNotEqual(returncode, 0)

                provider = GitRepositorySnapshotProvider(cache_root)
                started = time.monotonic()
                resolved = provider.resolve(selected)
                elapsed = time.monotonic() - started

                self.assertEqual(
                    resolved.resolved_revision, git(repository, "rev-parse", "HEAD")
                )
                self.assertLess(
                    elapsed,
                    15.0,
                    "resolve waited out the full lock timeout instead of "
                    "recovering the killed owner's lock",
                )
            finally:
                if holder.poll() is None:
                    holder.kill()
                    holder.wait()


if __name__ == "__main__":
    unittest.main()
