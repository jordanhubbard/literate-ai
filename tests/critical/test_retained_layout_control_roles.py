"""Actual configured project and native Git roles feed real staged descriptors."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from literate_ai._cache_lock import CacheLockError
from literate_ai.adapters import retained_layout_control_roles as roles
from literate_ai.adapters import retained_layout_git_controls as git_controls
from literate_ai.adapters.conversion_authority import (
    CONVERSION_AUTHORITY_FILE,
    FilesystemConversionAuthorityStore,
)
from literate_ai.adapters.lifecycle_lock import (
    ProjectLifecycleLockError,
    project_lifecycle_lock,
)
from literate_ai.adapters.repository_orchestration import OrchestrationInventoryError
from literate_ai.adapters.retained_layout_control_publication import (
    staged_layout_controls,
)
from literate_ai.adapters.retained_layout_git_controls import (
    observe_layout_git_controls,
)
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
    retained_layout_journal,
)
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.projects import PROJECT_FILENAME
from tests.support.fixtures_test_retained_harness_receipts import (
    _adapter,
    _legacy_project,
    _selectors,
)


@unittest.skipUnless(os.name == "posix", "POSIX staged role acquisition dependency")
class RetainedLayoutControlRoleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        temporary = tempfile.TemporaryDirectory(prefix="layout-role-template-")
        cls.addClassCleanup(temporary.cleanup)
        cls.template = Path(temporary.name).resolve() / "project"
        _legacy_project(cls.template)
        _adapter().initialize(
            cls.template,
            flavor_selectors=_selectors(cls.template),
            source_intelligence_provider="none",
            convert=True,
        )

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="layout-role-")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.root.chmod(0o700)
        self.project = self.root / "project"
        shutil.copytree(self.template, self.project, symlinks=True)
        self.state = self.root / "state"
        self.state.mkdir(mode=0o700)
        (self.state / "stages").mkdir(mode=0o700)

    @contextmanager
    def pool(self):
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=b"{}",
            budget=LayoutJournalBudget(),
        ) as journal:
            with staged_layout_controls(self.state / "stages", journal) as pool:
                yield pool, journal

    def git(self, *arguments, root=None, check=True):
        if shutil.which("git") is None:
            self.skipTest("native Git is unavailable")
        environment = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        environment.update(
            GIT_CONFIG_NOSYSTEM="1",
            GIT_CONFIG_GLOBAL=os.devnull,
            GIT_TERMINAL_PROMPT="0",
        )
        return subprocess.run(
            ["git", *arguments],
            cwd=root or self.project,
            env=environment,
            timeout=15,
            capture_output=True,
            check=check,
        )

    def init_git(self, *, root=None, commit=False):
        root = root or self.project
        self.git("init", "-q", "--initial-branch=main", "--template=", root=root)
        if commit:
            (root / "native-source.txt").write_bytes(b"native source\n")
            self.git("add", "native-source.txt", root=root)
            self.git(
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "-c",
                "commit.gpgsign=false",
                "-c",
                "core.hooksPath=" + os.devnull,
                "commit",
                "-q",
                "-m",
                "fixture",
                root=root,
            )

    def test_no_git_uses_actual_conversion_and_all_canonical_framework_mutexes(self):
        observed = observe_layout_git_controls(self.project)
        self.assertIsNone(observed.git_root)
        self.assertEqual(observed.targets(), ())
        with self.pool() as (pool, _):
            with roles.acquire_retained_layout_control_roles(
                self.project, pool
            ) as lease:
                lease.require_initial_inputs()
                self.assertEqual(lease.fixed_anchors, (self.project,))
                self.assertEqual(lease.protected_admin_entries, ())
                with self.assertRaises(ProjectLifecycleLockError) as caught:
                    with project_lifecycle_lock(self.project, operation="contender"):
                        self.fail("lifecycle mutex acquired twice")
                self.assertEqual(caught.exception.code, "lifecycle.project_locked")
                script = (
                    "import sys; from pathlib import Path; "
                    "from literate_ai.projects import ProjectConfigurationStore; "
                    "root=Path(sys.argv[1]); print('ready',flush=True); "
                    "\nwith ProjectConfigurationStore(root)._lock(root): "
                    "print('acquired',flush=True)"
                )
                with self.assertRaises(subprocess.TimeoutExpired) as waited:
                    subprocess.run(
                        [os.sys.executable, "-c", script, str(self.project)],
                        capture_output=True,
                        timeout=2,
                        env={
                            **os.environ,
                            "PYTHONPATH": str(
                                Path(roles.__file__).resolve().parents[2]
                            ),
                        },
                    )
                self.assertIn(b"ready", waited.exception.output or b"")
                self.assertNotIn(b"acquired", waited.exception.output or b"")
                with self.assertRaises(CacheLockError):
                    from literate_ai._cache_lock import exclusive_cache_lock

                    with exclusive_cache_lock(
                        FilesystemConversionAuthorityStore(self.project).lock_path,
                        timeout_seconds=0.0,
                    ):
                        self.fail("conversion writer bypassed actual owner")
                self.assertTrue(lease.identity.digest)
            with self.assertRaisesRegex(ValueError, "context ended"):
                lease.require_current()

    def test_unborn_repository_and_absent_index_are_real_control_roles(self):
        self.init_git()
        observed = observe_layout_git_controls(self.project)
        self.assertIsNone(observed.files.commit)
        self.assertIsNone(observed.files.index.content)
        with self.pool() as (pool, _):
            with roles.acquire_retained_layout_control_roles(
                self.project, pool
            ) as lease:
                self.assertEqual(lease.git.git_root, self.project)
                self.assertIn(self.project / ".git", lease.protected_admin_entries)
                self.assertTrue(
                    lease.reservations.owns(self.project / ".git/index.lock")
                )
                result = self.git("add", PROJECT_FILENAME, check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"index.lock", result.stderr)
                lease.require_initial_inputs()

    def test_unborn_existing_index_is_preserved(self):
        self.init_git()
        self.git("add", PROJECT_FILENAME)
        index = self.project / ".git/index"
        before = index.read_bytes()
        with self.pool() as (pool, _):
            with roles.acquire_retained_layout_control_roles(
                self.project, pool
            ) as lease:
                self.assertIsNone(lease.git.files.commit)
                self.assertEqual(lease.git.files.index.content, before)
                lease.require_current()
        self.assertEqual(index.read_bytes(), before)

    def test_committed_and_packed_head_bind_actual_reference_and_config_writers(self):
        self.init_git(commit=True)
        self.git("config", "--local", "test.concurrent", "baseline")
        self.git("pack-refs", "--all", "--prune")
        observed = observe_layout_git_controls(self.project)
        self.assertTrue(observed.files.commit)
        self.assertIsNone(observed.files.references[-1].file.content)
        with self.pool() as (pool, _):
            with roles.acquire_retained_layout_control_roles(
                self.project, pool
            ) as lease:
                for args, marker in (
                    (("update-ref", "HEAD", observed.files.commit), b"HEAD.lock"),
                    (("config", "--local", "test.concurrent", "no"), b"config"),
                ):
                    result = self.git(*args, check=False)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertIn(marker, result.stderr)
                    self.assertIn(b"lock", result.stderr)
                lease.require_current()

    def test_detached_head_does_not_invent_a_symbolic_branch_role(self):
        self.init_git(commit=True)
        self.git("checkout", "-q", "--detach", "HEAD")
        with self.pool() as (pool, _):
            with roles.acquire_retained_layout_control_roles(
                self.project, pool
            ) as lease:
                self.assertEqual(lease.git.files.references, ())
                self.assertTrue(lease.git.files.commit)
                self.assertTrue(
                    lease.reservations.owns(self.project / ".git/HEAD.lock")
                )
                lease.require_initial_inputs()

    def test_project_inside_containing_repository_does_not_invent_local_git_directory(
        self,
    ):
        container = self.root / "container"
        container.mkdir()
        self.init_git(root=container)
        inner = container / "inner"
        self.project.rename(inner)
        self.project = inner
        with self.pool() as (pool, _):
            with roles.acquire_retained_layout_control_roles(
                self.project, pool
            ) as lease:
                self.assertEqual(lease.git.git_root, container)
                self.assertEqual(set(lease.fixed_anchors), {self.project, container})
                self.assertTrue(lease.reservations.owns(container / ".git/index.lock"))
                self.assertFalse((self.project / ".git").exists())
                lease.require_initial_inputs()

    def test_linked_worktree_uses_actual_common_and_per_worktree_administration(self):
        self.init_git(commit=True)
        linked = self.root / "linked"
        self.git("worktree", "add", "-q", "--detach", str(linked))
        shutil.copytree(
            self.project,
            linked,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns(".git"),
        )
        original = self.project
        self.project = linked
        with self.pool() as (pool, _):
            with roles.acquire_retained_layout_control_roles(
                self.project, pool
            ) as lease:
                self.assertEqual(lease.git.files.common_directory, original / ".git")
                self.assertNotEqual(lease.git.files.git_directory, original / ".git")
                self.assertTrue(
                    lease.reservations.owns(lease.git.files.git_directory / "locked")
                )
                result = self.git(
                    "worktree",
                    "move",
                    str(linked),
                    str(self.root / "moved"),
                    root=original,
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"locked", result.stderr)
                self.assertTrue(linked.is_dir())
                lease.require_current()

    def test_git_spelling_without_registration_never_mints_control_roles(self):
        (self.project / ".git").mkdir()
        with self.pool() as (pool, journal):
            with self.assertRaises(OrchestrationInventoryError):
                with roles.acquire_retained_layout_control_roles(self.project, pool):
                    self.fail("spelling-only administration accepted")
            self.assertEqual(journal.events, ())
            self.assertFalse((self.project / ".litai-locks").exists())

    def test_project_conversion_identity_mismatch_refuses_before_publication(self):
        path = self.project / CONVERSION_AUTHORITY_FILE
        value = json.loads(path.read_bytes())
        value["project_id"] = "different-project"
        path.write_bytes(canonical_json_bytes(value) + b"\n")
        with self.pool() as (pool, journal):
            with self.assertRaisesRegex(ValueError, "conversion authority"):
                with roles.acquire_retained_layout_control_roles(self.project, pool):
                    self.fail("conversion identity mismatch accepted")
            self.assertEqual(journal.events, ())

    def test_canonical_roles_do_not_claim_initial_manifest_unchanged(self):
        with self.pool() as (pool, _):
            with roles.acquire_retained_layout_control_roles(
                self.project, pool
            ) as lease:
                path = self.project / PROJECT_FILENAME
                value = json.loads(path.read_bytes())
                path.write_text(json.dumps(value, indent=4) + "\n")
                lease.require_current()
                with self.assertRaisesRegex(ValueError, "prepared project manifest"):
                    lease.require_initial_inputs()

    def test_same_byte_conversion_replacement_refuses_and_keeps_both_nodes(self):
        path = self.project / CONVERSION_AUTHORITY_FILE
        displaced = self.state / "original-conversion"
        with self.pool() as (pool, _):
            with self.assertRaisesRegex(ValueError, "control roles changed"):
                with roles.acquire_retained_layout_control_roles(
                    self.project, pool
                ) as lease:
                    path.rename(displaced)
                    path.write_bytes(displaced.read_bytes())
                    lease.require_current()
            self.assertEqual(path.read_bytes(), displaced.read_bytes())
            self.assertNotEqual(path.stat().st_ino, displaced.stat().st_ino)

    def test_final_configuration_read_cannot_hide_changed_head_bytes(self):
        self.init_git()
        path = self.project / ".git/HEAD"
        original = git_controls._configuration_files

        def changed(*args):
            result = original(*args)
            path.write_bytes(b"ref: refs/heads/late\n")
            return result

        with mock.patch.object(
            git_controls, "_configuration_files", side_effect=changed
        ):
            with self.assertRaises(ValueError):
                observe_layout_git_controls(self.project)
        self.assertEqual(path.read_bytes(), b"ref: refs/heads/late\n")

    def test_final_configuration_read_cannot_hide_changed_index_bytes(self):
        self.init_git()
        self.git("add", PROJECT_FILENAME)
        path = self.project / ".git/index"
        original = git_controls._configuration_files

        def changed(*args):
            result = original(*args)
            path.write_bytes(b"foreign changed index")
            return result

        with mock.patch.object(
            git_controls, "_configuration_files", side_effect=changed
        ):
            with self.assertRaises(ValueError):
                observe_layout_git_controls(self.project)
        self.assertEqual(path.read_bytes(), b"foreign changed index")

    def test_git_observation_cannot_hide_late_conversion_inode_replacement(self):
        self.init_git()
        path = self.project / CONVERSION_AUTHORITY_FILE
        displaced = self.state / "prior-conversion"
        original = git_controls._configuration_files
        injected = False

        def changed(*args):
            nonlocal injected
            result = original(*args)
            if not injected:
                injected = True
                path.rename(displaced)
                path.write_bytes(displaced.read_bytes())
            return result

        with self.pool() as (pool, _):
            with self.assertRaisesRegex(ValueError, "control roles changed"):
                with roles.acquire_retained_layout_control_roles(
                    self.project, pool
                ) as lease:
                    with mock.patch.object(
                        git_controls, "_configuration_files", side_effect=changed
                    ):
                        lease.require_current()
                    self.fail(
                        "role check returned across replaced conversion authority"
                    )
            self.assertTrue(injected)
            self.assertEqual(path.read_bytes(), displaced.read_bytes())

    def test_actual_included_configuration_files_have_native_writer_roles(self):
        self.init_git()
        included = self.root / "included.cfg"
        included.write_text("[test]\n value = original\n")
        self.git("config", "--local", "include.path", str(included))
        observed = observe_layout_git_controls(self.project)
        self.assertIn(
            included, {file.path for file in observed.files.configuration_files}
        )
        before = included.read_bytes()
        with self.pool() as (pool, _):
            with roles.acquire_retained_layout_control_roles(
                self.project, pool
            ) as lease:
                self.assertTrue(
                    lease.reservations.owns(included.with_name(included.name + ".lock"))
                )
                result = self.git(
                    "config",
                    "--file",
                    str(included),
                    "test.value",
                    "changed",
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"lock", result.stderr)
                lease.require_current()
        self.assertEqual(included.read_bytes(), before)

    def _assert_declared_include_writer_is_reserved(self, included):
        before = included.read_bytes() if included.exists() else None
        observed = observe_layout_git_controls(self.project)
        with self.pool() as (pool, _):
            with roles.acquire_retained_layout_control_roles(
                self.project, pool
            ) as lease:
                result = self.git(
                    "config",
                    "--file",
                    str(included),
                    "test.concurrent",
                    "changed",
                    check=False,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(b"lock", result.stderr)
                self.assertTrue(
                    lease.reservations.owns(included.with_name(included.name + ".lock"))
                )
                lease.require_current()
        self.assertIn(
            included, {file.path for file in observed.files.configuration_files}
        )
        self.assertEqual(included.read_bytes() if included.exists() else None, before)

    def test_empty_included_configuration_blocks_actual_native_writer(self):
        self.init_git()
        included = self.root / "empty.cfg"
        included.write_bytes(b"")
        self.git("config", "--local", "include.path", str(included))
        self._assert_declared_include_writer_is_reserved(included)

    def test_missing_included_configuration_blocks_actual_native_writer(self):
        self.init_git()
        included = self.root / "missing.cfg"
        self.git("config", "--local", "include.path", str(included))
        self._assert_declared_include_writer_is_reserved(included)

    def test_relative_nested_include_uses_declaring_file_parent(self):
        self.init_git()
        directory = self.root / "config-files"
        directory.mkdir()
        included = directory / "empty.cfg"
        included.write_bytes(b"")
        parent = directory / "parent.cfg"
        parent.write_text("[include]\n path = empty.cfg\n")
        self.git("config", "--local", "include.path", str(parent))
        self._assert_declared_include_writer_is_reserved(included)

    def test_native_path_expansion_selects_tilde_include_target(self):
        self.init_git()
        included = self.root / "empty.cfg"
        included.write_bytes(b"")
        self.git("config", "--local", "include.path", "~/empty.cfg")
        with mock.patch.dict(os.environ, {"HOME": str(self.root)}):
            self._assert_declared_include_writer_is_reserved(included)

    def test_inactive_conditional_target_is_conservatively_reserved(self):
        self.init_git()
        included = self.root / "conditional.cfg"
        included.write_bytes(b"")
        self.git(
            "config", "--local", "includeIf.gitdir:never-matching.path", str(included)
        )
        self._assert_declared_include_writer_is_reserved(included)

    def test_parent_relative_include_preserves_actual_writer_coordinate(self):
        self.init_git()
        included = self.root / "parent.cfg"
        included.write_bytes(b"")
        self.git("config", "--local", "include.path", "../../parent.cfg")
        self._assert_declared_include_writer_is_reserved(included)

    def test_parent_traversal_cannot_hide_redirected_include_ancestor(self):
        self.init_git()
        actual = self.root / "actual"
        (actual / "child").mkdir(parents=True)
        (actual / "empty.cfg").write_bytes(b"")
        (self.root / "empty.cfg").write_bytes(b"")
        (self.root / "redirect").symlink_to(actual / "child", target_is_directory=True)
        self.git(
            "config",
            "--local",
            "include.path",
            str(self.root / "redirect/../empty.cfg"),
        )
        with self.pool() as (pool, journal):
            with self.assertRaises(ValueError):
                with roles.acquire_retained_layout_control_roles(self.project, pool):
                    self.fail("redirected include ancestry gained roles")
            self.assertEqual(journal.events, ())
