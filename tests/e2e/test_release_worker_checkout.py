"""Worker release custody with real Git and a local-only transport substitute."""

from __future__ import annotations

import base64
import gzip
import os
import re
import shlex
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai import project_releases as releases
from literate_ai.adapters import remote_transport
from literate_ai.adapters.release_worker_checkout import ReleaseWorkerCheckout
from literate_ai.adapters.ssh_transport import SshTransportError
from literate_ai.contracts import (
    ExecutionRequirements,
    ExecutionWorker,
    ExecutionWorkerKind,
)
from literate_ai.evidence_ledger import open_run


class LocalTransport:
    def run(self, argv, *, cwd, timeout_seconds):
        if argv[0] not in {"/bin/sh", "/bin/cp"}:
            raise AssertionError("the release checkout control admits local transport")
        return subprocess.run(
            argv, cwd=cwd, capture_output=True, timeout=timeout_seconds, check=False
        )


@unittest.skipIf(os.name == "nt", "uses a local POSIX worker")
class ReleaseWorkerCustodyTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.worker = self.worker_at("worker")
        self.runner = LocalTransport()
        self.uploads = []
        for replacement in (
            patch.object(
                releases,
                "remote_execute_arguments",
                lambda _worker, command, *args, **options: ("/bin/sh", "-c", command),
            ),
            patch.object(remote_transport, "scp_arguments", self.local_copy),
            patch.object(releases, "BoundedRemoteProcessRunner", LocalTransport),
            patch.object(releases, "_remote_live_gate_overlay", return_value={}),
            patch.dict(
                os.environ,
                {
                    "OBJ_DIR": str(self.root / "objects"),
                    "GIT_ALLOW_PROTOCOL": "file",
                    "LITAI_EVIDENCE_RUN": "",
                    "LITAI_EVIDENCE_PARENT": "",
                },
            ),
        ):
            replacement.start()
            self.addCleanup(replacement.stop)

    def worker_at(self, label):
        workspace = self.root / label
        workspace.mkdir()
        return ExecutionWorker(
            worker_id=label,
            kind=ExecutionWorkerKind.SSH,
            endpoint=f"fixture@{label}.invalid",
            workspace=str(workspace),
            transport="ssh",
            requirements=ExecutionRequirements(os_family="linux"),
        )

    def git(self, root, *args):
        return subprocess.check_output(
            ("git", "-C", str(root), *args),
            text=True,
            timeout=15,
        ).strip()

    def project(self, path, value):
        path.mkdir(parents=True)
        self.git(path, "init", "-q")
        (path / "payload").write_text(value)
        (path / ".gitignore").write_text("cache/\n")
        self.git(path, "add", ".")
        self.git(
            path,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgSign=false",
            "commit",
            "-qm",
            "Fixture",
        )
        return path, self.git(path, "rev-parse", "HEAD")

    def policy(self, owner):
        return SimpleNamespace(
            provider_kind="github",
            provider_repository=f"{owner}/sample",
            remote="origin",
            gate_timeout_seconds=10,
            gate_argv=(
                sys.executable,
                "-c",
                "from pathlib import Path; assert Path('payload').is_file()",
            ),
        )

    def local_copy(self, source, _endpoint, destination, *_args, **_options):
        self.uploads.append(destination)
        return ("/bin/cp", str(source), destination)

    def sync(self, root, revision, policy, worker=None):
        return releases._sync_worker_checkout(
            root,
            policy,
            worker or self.worker,
            revision,
            self.runner,
            windows=False,
            evidence_node=None,
        )

    def gate(self, checkout, revision, status=0):
        command = checkout.gate(
            revision, (sys.executable, "-c", f"raise SystemExit({status})"), {}
        )
        terminal = self.runner.run(
            ("/bin/sh", "-c", command), cwd=self.root, timeout_seconds=15
        )
        self.assertEqual(terminal.returncode, status, terminal.stderr)
        self.assertTrue(terminal.stderr.endswith(checkout.terminal_receipt))

    def test_full_repository_key_never_reuses_legacy_or_foreign_checkout(self):
        workspace = Path(self.worker.workspace)
        legacy, old = self.project(workspace / "release/sample", "operator base\n")
        (legacy / "payload").write_text("operator tracked edit\n")
        (legacy / "notes").write_text("operator untracked note\n")
        original_index = (legacy / ".git/index").read_bytes()
        first, first_head = self.project(self.root / "one" / "sample", "source one\n")
        second, second_head = self.project(self.root / "two" / "sample", "source two\n")
        self.git(
            first,
            "remote",
            "add",
            "origin",
            "https://fixture-user:fixture-token@example.invalid/one/sample?key=fixture-query",
        )
        self.git(
            second, "remote", "add", "origin", "https://example.invalid/two/sample"
        )
        a = self.sync(first, first_head, self.policy("one"))
        self.gate(a, first_head, status=11)
        b = self.sync(second, second_head, self.policy("two"))
        self.gate(b, second_head)
        self.assertNotEqual(a.directory, b.directory)
        self.assertEqual(
            self.git(Path(a.directory), "remote", "get-url", "origin"),
            "https://example.invalid/one/sample",
        )
        self.assertEqual(self.git(legacy, "rev-parse", "HEAD"), old)
        self.assertEqual((legacy / "payload").read_text(), "operator tracked edit\n")
        self.assertEqual((legacy / "notes").read_text(), "operator untracked note\n")
        self.assertEqual((legacy / ".git/index").read_bytes(), original_index)

        checkout = Path(a.directory)
        cache = checkout / "cache"
        cache.mkdir()
        (cache / "sentinel").write_text("native ignored cache\n")
        resumed = self.sync(first, first_head, self.policy("one"))
        self.gate(resumed, first_head)
        self.assertEqual(len(self.uploads), 2)
        self.assertEqual((cache / "sentinel").read_text(), "native ignored cache\n")

        (checkout / "payload").write_text("tracked operator edit after admission\n")
        (checkout / "notes").write_text("untracked operator data after admission\n")
        with self.assertRaises(releases.ProjectReleaseError) as dirty:
            self.sync(first, first_head, self.policy("one"))
        self.assertEqual(dirty.exception.code, "release.worker_checkout_dirty")
        self.assertEqual(len(self.uploads), 2)
        self.assertEqual(
            (checkout / "payload").read_text(),
            "tracked operator edit after admission\n",
        )
        self.assertEqual(
            (checkout / "notes").read_text(),
            "untracked operator data after admission\n",
        )
        self.assertFalse((checkout / ".git/litai-release-reservation").exists())

        (checkout / "notes").unlink()
        self.git(checkout, "update-index", "--assume-unchanged", "payload")
        with self.assertRaises(releases.ProjectReleaseError) as hidden:
            self.sync(first, first_head, self.policy("one"))
        self.assertEqual(hidden.exception.code, "release.worker_checkout_dirty")
        self.assertEqual(len(self.uploads), 2)
        self.assertEqual(
            (checkout / "payload").read_text(),
            "tracked operator edit after admission\n",
        )

        (checkout / ".git/litai-release-owner").unlink()
        (checkout / "payload").write_text("foreign tracked change\n")
        (checkout / "notes").write_text("foreign untracked note\n")
        with self.assertRaises(releases.ProjectReleaseError) as refused:
            self.sync(first, first_head, self.policy("one"))
        self.assertEqual(refused.exception.code, "release.worker_checkout_unsafe")
        self.assertEqual(len(self.uploads), 2)
        self.assertEqual((checkout / "payload").read_text(), "foreign tracked change\n")
        self.assertEqual((checkout / "notes").read_text(), "foreign untracked note\n")

    def test_ssh_accounts_cannot_share_a_repository_checkout(self):
        for style, first_origin, second_origin in (
            ("scp", "alice@host.invalid:sample", "bob@host.invalid:sample"),
            (
                "uri",
                "ssh://alice@host.invalid/~/sample",
                "ssh://bob@host.invalid/~/sample",
            ),
        ):
            with self.subTest(style=style):
                first, first_head = self.project(
                    self.root / style / "one" / "sample", "first account\n"
                )
                second, second_head = self.project(
                    self.root / style / "two" / "sample", "second account\n"
                )
                self.git(first, "remote", "add", "origin", first_origin)
                self.git(second, "remote", "add", "origin", second_origin)
                policy = self.policy("same")
                policy.provider_kind = None
                policy.provider_repository = None
                a = self.sync(first, first_head, policy)
                self.gate(a, first_head)
                b = self.sync(second, second_head, policy)
                self.gate(b, second_head)
                self.assertNotEqual(a.directory, b.directory)
                self.assertEqual(
                    (Path(a.directory) / "payload").read_text(), "first account\n"
                )
                self.assertEqual(
                    (Path(b.directory) / "payload").read_text(), "second account\n"
                )

    def test_ssh_password_syntax_refuses_before_worker_access(self):
        project, revision = self.project(self.root / "invalid-origin", "source\n")
        self.git(project, "remote", "add", "origin", "ssh://alice:@host.invalid/sample")
        with patch.object(
            self.runner, "run", side_effect=AssertionError("unexpected worker access")
        ) as dispatch:
            with self.assertRaises(releases.ProjectReleaseError) as refused:
                self.sync(project, revision, self.policy("same"))
        self.assertEqual(refused.exception.code, "release.worker_checkout_unsafe")
        dispatch.assert_not_called()
        self.assertEqual(self.uploads, [])

    def test_busy_worker_keeps_exact_token_and_fleet_reports_all_outcomes(self):
        project, revision = self.project(self.root / "project", "native input\n")
        policy = self.policy("test")
        other = self.worker_at("worker-z")
        held = self.sync(project, revision, policy)
        reservation = Path(held.directory) / ".git/litai-release-reservation/token"
        run = open_run(project, operation="release.check")
        self.assertIsNotNone(run)
        with (
            patch.object(
                releases,
                "_select_release_workers",
                return_value=((self.worker, other), ()),
            ),
            self.assertRaises(releases.ProjectReleaseError) as refused,
        ):
            releases._run_release_gate_on_workers(
                project,
                policy,
                {"head": revision},
                evidence_run=run,
            )
        self.assertEqual(refused.exception.code, "release.worker_checkout_busy")
        self.assertIn(run.run_id, refused.exception.message)
        self.assertIn("refused=1, released=1", refused.exception.message)
        nodes = [
            n
            for n in run.reduced()["nodes"]
            if n["operation"] == "release.target.local.worker"
        ]
        self.assertEqual(
            {
                node["pins"]["worker_id"]: node["pins"]["checkout_state"]
                for node in nodes
            },
            {"worker": "refused", "worker-z": "released"},
        )
        self.assertEqual(reservation.read_text(), held.token)
        run.close("failed")
        self.gate(held, revision)
        self.assertFalse(reservation.exists())

    def test_new_tracked_file_cannot_overwrite_an_existing_ignored_cache(self):
        project, head = self.project(self.root / "project", "fixture\n")
        policy = self.policy("one")
        first = self.sync(project, head, policy)
        self.gate(first, head)
        cache = Path(first.directory) / "cache"
        cache.mkdir()
        (cache / "sentinel").write_text("worker cache\n")
        (project / "cache").mkdir()
        (project / "cache/sentinel").write_text("new authored file\n")
        self.git(project, "add", "-f", "cache/sentinel")
        self.git(
            project,
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.invalid",
            "-c",
            "commit.gpgSign=false",
            "commit",
            "-qm",
            "Track previous cache name",
        )
        candidate = self.git(project, "rev-parse", "HEAD")
        with self.assertRaises(releases.ProjectReleaseError) as collision:
            self.sync(project, candidate, policy)
        self.assertEqual(collision.exception.code, "release.worker_sync_failed")
        self.assertEqual((cache / "sentinel").read_text(), "worker cache\n")
        self.assertEqual(self.git(Path(first.directory), "rev-parse", "HEAD"), head)

    def test_live_gate_retains_reservation_until_the_native_process_exits(self):
        project, head = self.project(self.root / "project", "fixture\n")
        policy = self.policy("one")
        lease = self.sync(project, head, policy)
        started = self.root / "started"
        terminal = self.root / "finish"
        gate = (
            sys.executable,
            "-c",
            "import time; from pathlib import Path; "
            f"Path({str(started)!r}).touch(); "
            f"stop = Path({str(terminal)!r}); "
            "exec('while not stop.exists(): time.sleep(0.01)')",
        )
        process = subprocess.Popen(
            ("/bin/sh", "-c", lease.gate(head, gate, {})),
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            deadline = time.monotonic() + 10
            while (
                not started.exists()
                and process.poll() is None
                and time.monotonic() < deadline
            ):
                time.sleep(0.01)
            self.assertTrue(started.exists())
            with self.assertRaises(releases.ProjectReleaseError) as busy:
                self.sync(project, head, policy)
            self.assertEqual(busy.exception.code, "release.worker_checkout_busy")
        finally:
            terminal.touch()
            _, stderr = process.communicate(timeout=15)
        self.assertEqual(process.returncode, 0, stderr)
        self.assertTrue(stderr.endswith(lease.terminal_receipt))
        resumed = self.sync(project, head, policy)
        self.gate(resumed, head)
        self.assertEqual(len(self.uploads), 1)

    def test_interrupted_transfer_requires_exact_operator_disposition(self):
        project, head = self.project(self.root / "project", "fixture\n")
        policy = self.policy("one")
        with (
            patch.object(
                remote_transport,
                "scp_arguments",
                side_effect=SshTransportError(
                    "execution.ssh_timed_out", "controlled transfer interruption"
                ),
            ),
            self.assertRaises(releases.ProjectReleaseError) as interrupted,
        ):
            self.sync(project, head, policy)
        self.assertEqual(interrupted.exception.code, "release.worker_sync_failed")
        namespace = Path(self.worker.workspace) / ".litai-release-v2"
        (checkout,) = (item for item in namespace.iterdir() if item.is_dir())
        reservation = checkout / ".git/litai-release-reservation"
        token = (reservation / "token").read_bytes()
        with self.assertRaises(releases.ProjectReleaseError) as busy:
            self.sync(project, head, policy)
        self.assertEqual(busy.exception.code, "release.worker_checkout_busy")
        self.assertEqual((reservation / "token").read_bytes(), token)

        # The transport substitute establishes that no transfer or gate ran.
        # Preserve the exact reservation as the operator's recovery record.
        archived = self.root / "reviewed-reservation"
        reservation.rename(archived)
        resumed = self.sync(project, head, policy)
        self.assertEqual(Path(resumed.directory), checkout)
        self.gate(resumed, head)
        self.assertEqual((archived / "token").read_bytes(), token)
        self.assertEqual(len(self.uploads), 1)

    def test_unowned_namespace_and_redirected_workspaces_refuse_before_git(self):
        workspace = Path(self.worker.workspace)
        original, _ = self.project(workspace / ".litai-release-v2", "foreign\n")
        request = ReleaseWorkerCheckout.create(str(workspace), "e" * 64, windows=False)
        outcome = self.runner.run(
            ("/bin/sh", "-c", request.prepare()), cwd=self.root, timeout_seconds=10
        )
        self.assertEqual(outcome.returncode, 73)
        self.assertEqual(
            set(p.name for p in original.iterdir()), {".git", ".gitignore", "payload"}
        )
        target = self.root / "unowned"
        target.mkdir()
        link = self.root / "link"
        link.symlink_to(target, target_is_directory=True)
        request = ReleaseWorkerCheckout.create(str(link), "f" * 64, windows=False)
        outcome = self.runner.run(
            ("/bin/sh", "-c", request.prepare()), cwd=self.root, timeout_seconds=10
        )
        self.assertEqual(outcome.returncode, 73)
        self.assertEqual(list(target.iterdir()), [])


class WindowsReleaseWorkerCustodyTests(unittest.TestCase):
    def test_windows_mutation_commands_include_native_ownership_and_reparse_guards(
        self,
    ):
        checkout = ReleaseWorkerCheckout.create(r"~\ws", "a" * 64, windows=True)

        def decode(command):
            self.assertLess(len(command), 8191)
            loader = base64.b64decode(shlex.split(command)[-1]).decode("utf-16-le")
            payload = re.search(r"FromBase64String\('([A-Za-z0-9+/=]+)'\)", loader)
            self.assertIsNotNone(payload)
            return gzip.decompress(base64.b64decode(payload[1])).decode("utf-8")

        prepared = decode(checkout.prepare())
        self.assertIn("[IO.FileAttributes]::ReparsePoint", prepared)
        self.assertLess(
            prepared.rindex("if (-not (Namespace-Owned))"),
            prepared.index("New-Item -ItemType Directory -Path $d"),
        )
        applied = decode(
            checkout.apply(
                "b" * 40, "https://example.invalid/one/sample", uploaded=True
            )
        )
        self.assertLess(
            applied.rindex("if (-not (Reserved))"), applied.index("git fetch")
        )
        self.assertLess(
            applied.index("git fetch"),
            applied.index("checkout -q --detach --no-overwrite-ignore"),
        )
        terminal = decode(checkout.gate("b" * 40, ("cmd.exe", "/c", "exit 0"), {}))
        self.assertLess(
            terminal.rindex("if (-not (Reserved)"),
            terminal.rindex("Release-Reservation"),
        )
        self.assertIn("litai-release-reservation-released $token", terminal)
        self.assertIn("git status --porcelain --untracked-files=all", applied)
        self.assertNotIn("git clean", applied)
        self.assertNotIn("checkout -q --detach --force", applied)

    @unittest.skipUnless(os.name == "nt", "requires native Windows and PowerShell")
    def test_native_windows_checkout_holds_then_releases_exact_reservation(self):
        import shutil

        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            project = workspace / "source"
            project.mkdir()

            def git(cwd, *arguments):
                return subprocess.check_output(
                    ("git", "-C", str(cwd), *arguments),
                    text=True,
                    timeout=15,
                ).strip()

            git(project, "init", "-q")
            (project / "fixture.txt").write_text("Windows fixture\n")
            git(project, "add", "fixture.txt")
            git(
                project,
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.invalid",
                "-c",
                "commit.gpgSign=false",
                "commit",
                "-qm",
                "Fixture",
            )
            revision = git(project, "rev-parse", "HEAD")
            request = ReleaseWorkerCheckout.create(
                str(workspace), "b" * 64, windows=True
            )

            def command(script, status):
                result = subprocess.run(
                    shlex.split(script),
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
                self.assertEqual(result.returncode, status, result.stderr)
                return result

            command(request.prepare(), 0)
            competitor = ReleaseWorkerCheckout.create(
                str(workspace), "b" * 64, windows=True
            )
            command(competitor.prepare(), 75)
            bundle = workspace / "local.bundle"
            git(project, "bundle", "create", str(bundle), "HEAD")
            checkout = Path(request.directory)
            shutil.copyfile(bundle, checkout / request.bundle)
            command(request.apply(revision, str(project), uploaded=True), 0)
            gate = command(
                request.gate(
                    revision, (sys.executable, "-c", "raise SystemExit(11)"), {}
                ),
                11,
            )
            self.assertTrue(gate.stderr.endswith(request.terminal_receipt))
            self.assertEqual(git(checkout, "rev-parse", "HEAD"), revision)
            self.assertFalse((checkout / ".git/litai-release-reservation").exists())

    @unittest.skipUnless(
        os.name == "nt", "requires native Windows junction and PowerShell"
    )
    def test_native_windows_workspace_junction_is_refused_without_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            target = root / "original"
            target.mkdir()
            junction = root / "worker"
            subprocess.run(
                ("cmd.exe", "/c", "mklink", "/J", str(junction), str(target)),
                capture_output=True,
                timeout=10,
                check=True,
            )
            try:
                request = ReleaseWorkerCheckout.create(
                    str(junction), "e" * 64, windows=True
                )
                result = subprocess.run(
                    shlex.split(request.prepare()),
                    capture_output=True,
                    timeout=20,
                    check=False,
                )
                self.assertEqual(result.returncode, 73, result.stderr)
                self.assertEqual(list(target.iterdir()), [])
            finally:
                junction.rmdir()
