"""Genuine framework application handed to an acknowledged live source phase."""

from __future__ import annotations

import errno
import json
import os
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_ownership as fixtures
from literate_ai.adapters import framework_update_roles as updates
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


@unittest.skipUnless(os.name == "posix", "native POSIX source/control effects")
class FrameworkUpdateRoleTests(unittest.TestCase):
    pool = fixtures.RetainedLayoutOwnershipTests.pool
    phase = fixtures.RetainedLayoutOwnershipTests.phase
    git = fixtures.RetainedLayoutOwnershipTests.git
    init_git = fixtures.RetainedLayoutOwnershipTests.init_git

    @classmethod
    def setUpClass(cls):
        fixtures.RetainedLayoutOwnershipTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutOwnershipTests.setUp(self)
        self.update_budget = RetainedCargoInputBudget(
            2048, 32768, 4 * 1024**2, 64 * 1024**2
        )
        self.update_sequence = 0

    @contextmanager
    def updated(self, **kwargs):
        self.update_sequence += 1
        retirement = self.state / f"update-retired-{self.update_sequence}"
        retirement.mkdir(mode=0o700)
        with updates.applied_framework_update_roles(
            self.project,
            budget=self.update_budget,
            maximum_metadata_bytes=2 * 1024**3,
            retirement_directory=retirement,
            **kwargs,
        ) as handoff:
            yield handoff

    def plan(self, handoff=None):
        return transaction.plan_retained_layout_source_move(
            self.project, "retained", budget=self.budget, framework_update=handoff
        )

    def observe(self, phase, handoff=None):
        return phase.complete_partition(
            budget=self.update_budget,
            maximum_metadata_bytes=2 * 1024**3,
            framework_update=handoff,
        )

    def test_genuine_handoff_is_bound_journaled_and_consumed_by_source_move(
        self,
    ):
        with self.updated(adopt_added=True) as handoff:
            with project_lifecycle_lock(
                self.project, operation="independent-contender"
            ):
                pass
            plan = self.plan(handoff)
            self.assertEqual(plan.framework_update, handoff.identity.uri)
            with self.pool(plan) as (pool, journal):
                with self.phase(plan, pool) as phase:
                    with self.observe(phase, handoff) as owner:
                        observation = owner.document["framework_update"]
                        self.assertEqual(
                            observation["checkpoint"], handoff.document["checkpoint"]
                        )
                        observation["paths"].append("forged")
                        self.assertNotIn("forged", handoff.document["paths"])
                        roles = dict(owner.roles)
                        self.assertIn("flavors/os-windows/flavor.md", handoff.paths)
                        self.assertEqual(
                            roles["flavors/os-windows/flavor.md"], "framework"
                        )
                        phase.move_source()
                        with self.assertRaisesRegex(RuntimeError, "spent"):
                            handoff.require_current()
                    phase.publish_metadata(self.metadata)
                    phase.finalize_controls(self.retired)
                self.assertIn(
                    "source-partition-observed", [e["kind"] for e in journal.events]
                )
        self.assertTrue((self.destination / "app.py").is_file())

    def test_ended_and_saved_handoffs_cannot_plan(self):
        with self.updated() as handoff:
            saved = {"identity": handoff.identity.uri, "paths": handoff.paths}
        with self.assertRaisesRegex(RuntimeError, "ended"):
            self.plan(handoff)
        with self.assertRaises(TypeError):
            self.plan(saved)

    def _require_revocation_before_descriptor_teardown(self, error=None):
        close = os.close
        handoff = descriptor = directory = None
        intercepted = accepted = verified_closed = same_descriptor = False

        def actual_close_then_probe(fd):
            nonlocal intercepted, accepted, verified_closed, same_descriptor
            if fd != descriptor or intercepted:
                return close(fd)
            intercepted = True
            close(fd)
            try:
                os.fstat(fd)
            except OSError as failure:
                verified_closed = failure.errno == errno.EBADF
            borrowed = os.open(directory, os.O_RDONLY | os.O_DIRECTORY)
            try:
                same_descriptor = borrowed == fd
                try:
                    handoff.require_current()
                    accepted = True
                except RuntimeError as failure:
                    self.assertIn("ended", str(failure))
            finally:
                close(borrowed)

        with mock.patch.object(os, "close", actual_close_then_probe):
            context = self.updated()
            handoff = context.__enter__()
            descriptor = handoff._retirement_descriptor
            directory = handoff._retirement_directory
            if error is None:
                context.__exit__(None, None, None)
            else:
                self.assertFalse(context.__exit__(type(error), error, None))
        self.assertTrue(intercepted)
        self.assertTrue(verified_closed)
        self.assertTrue(same_descriptor)
        self.assertFalse(accepted)

    def test_normal_exit_revokes_before_original_descriptor_teardown(self):
        self._require_revocation_before_descriptor_teardown()

    def test_exceptional_exit_revokes_before_original_descriptor_teardown(self):
        self._require_revocation_before_descriptor_teardown(ValueError("caller failed"))

    def test_changed_post_update_checkpoint_cannot_be_rebound(self):
        with self.assertRaises(RuntimeError):
            with self.updated() as handoff:
                path = self.project / ".literate/update-bases.json"
                foreign = path.read_bytes() + b" "
                path.write_bytes(foreign)
                with self.assertRaises(RuntimeError):
                    self.plan(handoff)
        self.assertEqual(path.read_bytes(), foreign)
        self.assertTrue(self.source.exists())

    def test_pre_update_plan_cannot_adopt_later_live_handoff(self):
        plan = self.plan()
        with self.updated() as handoff:
            with self.pool(plan) as (pool, _):
                with self.assertRaises(ValueError):
                    with self.phase(plan, pool) as phase:
                        with self.observe(phase, handoff):
                            self.fail("earlier source plan adopted later update")

    def test_fresh_unbound_plan_cannot_adopt_a_live_handoff(self):
        with self.updated() as handoff:
            plan = self.plan()
            with self.pool(plan) as (pool, _):
                with self.assertRaisesRegex(
                    ValueError, "source phase remains incomplete"
                ):
                    with self.phase(plan, pool) as phase:
                        with self.assertRaisesRegex(RuntimeError, "does not bind"):
                            with self.observe(phase, handoff):
                                self.fail("unbound source plan adopted update roles")

    def test_forged_checkpoint_and_local_conflict_remain_unclaimed(self):
        from literate_ai.adapters.project_updates import _upstream_template
        from literate_ai.adapters.update_merge import UpdateBases

        relative = "flavors/os-windows/flavor.md"
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"arbitrary local bytes\n")
        bases = UpdateBases(self.project)
        bases.advance("framework", relative, _upstream_template(set())[relative])
        bases.write()
        with self.updated() as handoff:
            self.assertNotIn(relative, handoff.paths)
            plan = self.plan(handoff)
            with self.pool(plan) as (pool, _):
                with self.assertRaisesRegex(
                    ValueError, "source phase remains incomplete"
                ):
                    with self.phase(plan, pool) as phase:
                        with self.observe(phase, handoff) as owner:
                            self.assertEqual(dict(owner.roles)[relative], "unclaimed")
        self.assertEqual(path.read_bytes(), b"arbitrary local bytes\n")

    def test_reviewed_keep_local_resolution_supplies_actual_update_role(self):
        from literate_ai.adapters.project_updates import FilesystemProjectUpdateAdapter

        relative = "flavors/os-windows/flavor.md"
        path = self.project / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"reviewed local overlay\n")
        plan = FilesystemProjectUpdateAdapter().plan(self.project)
        item = next(item for item in plan.files if item.path == relative)
        resolutions = {
            relative: {
                "file_identity": item.identity.to_dict(),
                "decision": "keep-local",
            }
        }
        with self.updated(resolutions=resolutions) as handoff:
            self.assertIn(relative, handoff.paths)
            plan = self.plan(handoff)
            with self.pool(plan) as (pool, _):
                with self.assertRaisesRegex(
                    ValueError, "source phase remains incomplete"
                ):
                    with self.phase(plan, pool) as phase:
                        with self.observe(phase, handoff) as owner:
                            self.assertEqual(dict(owner.roles)[relative], "framework")
        self.assertEqual(path.read_bytes(), b"reviewed local overlay\n")

    def test_strict_path_does_not_use_legacy_project_payload_readers(self):
        original_bytes, original_text = Path.read_bytes, Path.read_text

        def bounded_only(path, *args, **kwargs):
            if path.is_relative_to(self.project):
                raise AssertionError("legacy project payload read")
            return original_bytes(path, *args, **kwargs)

        def bounded_text_only(path, *args, **kwargs):
            if path.is_relative_to(self.project):
                raise AssertionError("legacy project payload read")
            return original_text(path, *args, **kwargs)

        with (
            mock.patch.object(Path, "read_bytes", bounded_only),
            mock.patch.object(Path, "read_text", bounded_text_only),
        ):
            with self.updated() as handoff:
                handoff.require_current()

    def test_foreign_added_target_during_fsync_is_preserved(self):
        target = self.project / "flavors/os-windows/flavor.md"
        real_fsync = os.fsync
        changed = False

        def fsync_then_change(descriptor):
            nonlocal changed
            real_fsync(descriptor)
            if changed or not target.parent.exists():
                return
            node = os.fstat(descriptor)
            for temporary in target.parent.glob(".litai-update-*"):
                if temporary.stat().st_ino == node.st_ino:
                    target.write_bytes(b"foreign source after fsync\n")
                    changed = True

        with mock.patch.object(os, "fsync", fsync_then_change):
            with self.assertRaisesRegex(RuntimeError, "observed state retained"):
                with self.updated(adopt_added=True):
                    self.fail("foreign target was overwritten")
        self.assertTrue(changed)
        self.assertEqual(target.read_bytes(), b"foreign source after fsync\n")
        self.assertTrue(self.source.exists())

    def test_foreign_checkpoint_during_fsync_never_enters_legacy_rollback(self):
        from literate_ai.adapters.update_merge import UpdateBases

        checkpoint = self.project / ".literate/update-bases.json"
        real_fsync = os.fsync
        changed = False

        def fsync_then_change(descriptor):
            nonlocal changed
            real_fsync(descriptor)
            if changed:
                return
            node = os.fstat(descriptor)
            for temporary in checkpoint.parent.glob(".litai-update-*"):
                if temporary.stat().st_ino == node.st_ino:
                    checkpoint.write_bytes(b"foreign checkpoint after fsync\n")
                    changed = True

        with mock.patch.object(
            UpdateBases, "rollback", side_effect=AssertionError("blind rollback")
        ):
            with mock.patch.object(os, "fsync", fsync_then_change):
                with self.assertRaisesRegex(RuntimeError, "observed state retained"):
                    with self.updated():
                        self.fail("foreign checkpoint was overwritten")
        self.assertTrue(changed)
        self.assertEqual(checkpoint.read_bytes(), b"foreign checkpoint after fsync\n")
        self.assertTrue(self.source.exists())

    def test_initial_namespace_and_provider_share_payload_budget(self):
        total = sum(
            path.stat().st_size for path in self.project.rglob("*") if path.is_file()
        )
        budget = RetainedCargoInputBudget(
            2048, 8192, 4 * 1024**2, total + 4 * 1024**2 + 65536
        )
        owner = updates._FrameworkUpdateRoles(
            updates._KEY, self.project, budget, 2 * 1024**3
        )
        try:
            with self.assertRaises((ValueError, RuntimeError)):
                owner._provider()
        finally:
            owner._active = False
        self.assertTrue(self.source.exists())

    def test_handoff_configuration_is_read_only(self):
        with self.updated() as handoff:
            for name, value in (
                ("budget", self.budget),
                ("metadata", 16 * 1024**3),
                ("root", self.state),
            ):
                with self.assertRaises(AttributeError):
                    setattr(handoff, name, value)

    def test_target_added_after_other_input_closes_is_preserved(self):
        target = self.project / "flavors/os-windows/flavor.md"
        close = updates._FrameworkUpdateRoles._close_file
        before = updates._FrameworkUpdateRoles.before_replace
        armed = changed = False
        last = None

        def before_replace(owner, path, *args, **kwargs):
            nonlocal armed, last
            armed = path == target
            last = tuple(owner._cache)[-1]
            return before(owner, path, *args, **kwargs)

        def close_then_change(owner, item):
            nonlocal changed
            close(owner, item)
            if armed and not changed and item.path == last:
                target.write_bytes(b"foreign after other input closes\n")
                changed = True

        with (
            mock.patch.object(
                updates._FrameworkUpdateRoles, "before_replace", before_replace
            ),
            mock.patch.object(
                updates._FrameworkUpdateRoles, "_close_file", close_then_change
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "observed state retained"):
                with self.updated(adopt_added=True):
                    self.fail("late target was overwritten")
        self.assertTrue(changed)
        self.assertEqual(target.read_bytes(), b"foreign after other input closes\n")

    def test_current_head_native_binding_closes_after_final_payload_read(self):
        actual_signature = updates._signature
        check = updates._FrameworkUpdateRoles._check
        changed = False
        with self.updated() as handoff:
            head = handoff._git.git_paths[0] / "HEAD"
            self.assertIn(head, handoff._cache)
            last = tuple(handoff._cache)[-1]

            def after_payload(owner, item):
                nonlocal changed
                check(owner, item)
                if owner is handoff and item.path == last:
                    changed = True

            def changed_head(path):
                value = actual_signature(path)
                return (
                    (*value[:-1], value[-1] + 1) if changed and path == head else value
                )

            with (
                mock.patch.object(
                    updates._FrameworkUpdateRoles, "_check", after_payload
                ),
                mock.patch.object(updates, "_signature", changed_head),
            ):
                with self.assertRaisesRegex(RuntimeError, "native facts changed"):
                    handoff.require_current()
            self.assertTrue(changed)
            handoff.require_current()

    def test_strict_interruption_preserves_exception_type_and_source(self):
        with mock.patch.object(
            updates._FrameworkUpdateRoles,
            "before_replace",
            side_effect=KeyboardInterrupt("injected owned update interruption"),
        ):
            with self.assertRaises(KeyboardInterrupt) as interrupted:
                with self.updated(adopt_added=True):
                    self.fail("interrupted update yielded a handoff")
        self.assertTrue(
            any(
                "handoff unavailable" in note
                for note in interrupted.exception.__notes__
            )
        )
        self.assertTrue(self.source.exists())

    def test_foreign_checkpoint_without_any_update_effect_is_preserved(self):
        from literate_ai.adapters import roadmap_dependencies
        from literate_ai.adapters.update_merge import UpdateBases

        with self.updated():
            pass
        checkpoint = self.project / ".literate/update-bases.json"
        require = roadmap_dependencies.require_project_roadmap_acyclic
        publications = []
        after = updates._FrameworkUpdateRoles.after_publication

        def check_then_change(*args, **kwargs):
            require(*args, **kwargs)
            checkpoint.write_bytes(b"foreign checkpoint before any publication\n")

        def record_publication(owner, path, *args):
            publications.append(path)
            return after(owner, path, *args)

        with (
            mock.patch.object(
                roadmap_dependencies,
                "require_project_roadmap_acyclic",
                check_then_change,
            ),
            mock.patch.object(
                UpdateBases, "rollback", side_effect=AssertionError("blind rollback")
            ),
            mock.patch.object(
                updates._FrameworkUpdateRoles, "after_publication", record_publication
            ),
        ):
            with self.assertRaisesRegex(RuntimeError, "observed state retained"):
                with self.updated():
                    self.fail("foreign checkpoint was overwritten")
        self.assertEqual(publications, [])
        self.assertEqual(
            checkpoint.read_bytes(), b"foreign checkpoint before any publication\n"
        )
        self.assertTrue(self.source.exists())

    def test_actual_context_ending_during_final_native_close_refuses_currentness(self):
        context = self.updated()
        handoff = context.__enter__()
        close = handoff._git.close_native
        check = handoff._check
        last = tuple(handoff._cache)[-1]
        armed = ended = False

        def check_then_arm(item):
            nonlocal armed
            check(item)
            if item.path == last:
                armed = True

        def close_then_end():
            nonlocal ended
            close()
            if armed and not ended:
                ended = True
                context.__exit__(None, None, None)

        try:
            with (
                mock.patch.object(handoff._git, "close_native", close_then_end),
                mock.patch.object(handoff, "_check", check_then_arm),
            ):
                with self.assertRaisesRegex(RuntimeError, "ended"):
                    handoff.require_current()
            self.assertTrue(ended)
            self.assertFalse(handoff._active)
        finally:
            if not ended:
                context.__exit__(None, None, None)

    def test_packaged_module_cannot_borrow_an_ambient_git_origin(self):
        from literate_ai.adapters import project_updates

        self.init_git()
        self.git("remote", "add", "origin", "ssh://example.invalid/provider.git")
        fake = self.project / ".venv/lib/literate_ai/adapters/project_updates.py"
        fake.parent.mkdir(parents=True)
        fake.write_bytes(b"# nonexecuting installed-layout fixture\n")
        owner = updates._FrameworkUpdateRoles(
            updates._KEY, self.project, self.update_budget, 2 * 1024**3
        )
        try:
            with mock.patch.object(project_updates, "__file__", str(fake)):
                with self.assertRaisesRegex(RuntimeError, "physical source provider"):
                    owner.current_origin()
        finally:
            owner._active = False

    def test_real_clean_merge_preserves_overlay_with_bounded_merge_process(self):
        from literate_ai.adapters.project_updates import _upstream_template
        from literate_ai.adapters.update_merge import UpdateBases

        current = _upstream_template(set())[".gitignore"]
        base = current.replace(b"*.egg-info/", b"*.old-egg-info/")
        ours = base.replace(b"# Literate AI local", b"# Custom local")
        self.assertNotEqual(base, current)
        self.assertNotEqual(ours, base)
        bases = UpdateBases(self.project)
        bases.advance("framework", ".gitignore", base)
        bases.write()
        path = self.project / ".gitignore"
        path.write_bytes(ours)
        with self.updated() as handoff:
            self.assertIn(".gitignore", handoff.result["merged"])
            self.assertIn(".gitignore", handoff.paths)
        self.assertEqual(
            path.read_bytes(), ours.replace(b"*.old-egg-info/", b"*.egg-info/")
        )

    def test_post_move_checkpoint_growth_refuses_before_payload_allocation(self):
        checkpoint = self.project / ".literate/update-bases.json"
        move = transaction.move_layout_entry_exclusive
        read = os.read
        grown = payload_read = False
        checkpoint_node = None

        def move_then_grow(source, destination, **kwargs):
            nonlocal grown, checkpoint_node
            result = move(source, destination, **kwargs)
            if source == self.source and destination == self.destination:
                with checkpoint.open("r+b") as stream:
                    stream.truncate(self.update_budget.maximum_file_bytes + 1)
                node = checkpoint.stat()
                checkpoint_node = node.st_dev, node.st_ino
                grown = True
            return result

        def bounded_read(descriptor, size):
            nonlocal payload_read
            if grown:
                node = os.fstat(descriptor)
                if (node.st_dev, node.st_ino) == checkpoint_node:
                    payload_read = True
            return read(descriptor, size)

        with self.updated() as handoff:
            plan = self.plan(handoff)
            with self.pool(plan) as (pool, _):
                with self.assertRaises((ValueError, RuntimeError)):
                    with self.phase(plan, pool) as phase:
                        with self.observe(phase, handoff):
                            with (
                                mock.patch.object(
                                    transaction,
                                    "move_layout_entry_exclusive",
                                    move_then_grow,
                                ),
                                mock.patch.object(os, "read", bounded_read),
                            ):
                                phase.move_source()
        self.assertTrue(grown)
        self.assertFalse(payload_read)
        self.assertTrue(self.destination.exists())
        self.assertEqual(
            checkpoint.stat().st_size, self.update_budget.maximum_file_bytes + 1
        )

    def test_retirement_parent_replacement_preserves_original_and_foreign_files(self):
        from literate_ai.adapters.update_merge import UpdateBases

        relative = "flavors/obsolete-controlled-dir/retired.txt"
        target = self.project / relative
        target.parent.mkdir()
        target.write_bytes(b"prior framework bytes\n")
        bases = UpdateBases(self.project)
        bases.advance("framework", relative, target.read_bytes())
        bases.write()
        before = updates._FrameworkUpdateRoles.before_replace
        moved = target.parent.with_name(target.parent.name + "-original")
        changed = False

        def before_then_replace_parent(owner, path, *args, **kwargs):
            nonlocal changed
            result = before(owner, path, *args, **kwargs)
            if path == target and not changed:
                target.parent.rename(moved)
                target.parent.mkdir()
                target.write_bytes(b"foreign replacement directory file\n")
                changed = True
            return result

        with mock.patch.object(
            updates._FrameworkUpdateRoles, "before_replace", before_then_replace_parent
        ):
            with self.assertRaises(RuntimeError):
                with self.updated():
                    self.fail("changed retirement parent supplied ownership")
        self.assertTrue(changed)
        self.assertEqual((moved / target.name).read_bytes(), b"prior framework bytes\n")
        self.assertEqual(target.read_bytes(), b"foreign replacement directory file\n")

    def test_retired_original_nodes_and_durable_intents_remain_as_private_evidence(
        self,
    ):
        target = self.project / "components/legacy-project-wrapper/component.lock.json"
        original, inode = target.read_bytes(), target.stat().st_ino
        with self.updated() as handoff:
            directory = Path(handoff.document["retirement_directory"])
            nodes = tuple(directory.glob("node-*"))
            self.assertTrue(
                any(
                    path.stat().st_ino == inode and path.read_bytes() == original
                    for path in nodes
                )
            )
            intents = tuple(directory.glob("intent-*.json"))
            self.assertTrue(intents)
            self.assertTrue(
                any(
                    json.loads(path.read_bytes())["source"] == str(target)
                    for path in intents
                )
            )
        self.assertFalse(target.exists())
        self.assertTrue((directory / "owner.json").exists())
        self.assertTrue(
            any(
                path.stat().st_ino == inode and path.read_bytes() == original
                for path in nodes
            )
        )

    def test_read_only_handoff_cannot_call_updater_publication_callbacks(self):
        with self.updated() as handoff:
            target = self.project / ".gitignore"
            item = handoff._cache[target]
            with self.assertRaisesRegex(RuntimeError, "write scope"):
                handoff.after_publication(target, item.content, item.signature)
            with self.assertRaisesRegex(RuntimeError, "write scope"):
                handoff.retire(target)

    def test_foreign_private_retirement_neighbor_revokes_handoff_without_collection(
        self,
    ):
        with self.assertRaises(RuntimeError):
            with self.updated() as handoff:
                foreign = (
                    Path(handoff.document["retirement_directory"])
                    / "unclaimed-user-file"
                )
                foreign.write_bytes(b"foreign private evidence\n")
                with self.assertRaises(RuntimeError):
                    handoff.require_current()
        self.assertEqual(foreign.read_bytes(), b"foreign private evidence\n")
        self.assertTrue(self.source.exists())

    def test_framework_hardlink_mutation_requires_group_ownership_before_writes(self):
        from literate_ai.adapters.project_updates import _upstream_template
        from literate_ai.adapters.update_merge import UpdateBases

        target = self.project / ".gitignore"
        older = _upstream_template(set())[".gitignore"] + b"\n# older upstream\n"
        target.write_bytes(older)
        alias = self.project / "unclaimed-hardlink"
        os.link(target, alias)
        bases = UpdateBases(self.project)
        bases.advance("framework", ".gitignore", older)
        bases.write()
        with self.assertRaisesRegex(RuntimeError, "alias-group mutations"):
            with self.updated():
                self.fail("unjoined framework/source alias group was mutated")
        self.assertEqual(target.read_bytes(), older)
        self.assertEqual(alias.read_bytes(), older)
        self.assertEqual(target.stat().st_ino, alias.stat().st_ino)

    def test_canonical_resource_selector_cannot_be_replaced_by_a_parallel_reader(self):
        directory = self.state / "foreign-resources"
        directory.mkdir()
        with mock.patch("importlib.resources.files", return_value=directory):
            with self.assertRaisesRegex(RuntimeError, "physical source resources"):
                with self.updated():
                    self.fail("alternate resource selector supplied source authority")
        self.assertTrue(self.source.exists())
