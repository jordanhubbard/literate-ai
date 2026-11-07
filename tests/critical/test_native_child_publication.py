"""Real-filesystem interruption controls, not child qualification fixtures."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import native_child_publication as publication
from literate_ai.contracts.identity import canonical_identity


class NativeChildPublicationTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.metadata = self.root / ".literate"
        self.metadata.mkdir()
        self.old = {
            "native-projects.json": b"old registry\n",
            "conversion-authority.json": b"old evidence\n",
        }
        self.new = {
            "native-projects.json": b"new registry\n",
            "conversion-authority.json": b"new evidence\n",
        }
        self.original = {}
        for name, content in self.old.items():
            path = self.metadata / name
            path.write_bytes(content)
            path.chmod(0o640)
            self.original[name] = publication._key(path.stat())
        self.plan = canonical_identity({"reviewed": "test-metadata-only"}).uri

    def prepare(self):
        identity = publication.prepare_native_child_publication(
            self.root, plan_identity=self.plan, previous=self.old, proposed=self.new
        )
        active = json.loads((self.metadata / publication._ACTIVE).read_bytes())
        self.attempt = self.metadata / publication._HISTORY / active["attempt"]
        return identity

    def verify(self, expected):
        publication.require_no_native_child_publication(self.root)
        self.assertEqual(
            {name: (self.metadata / name).read_bytes() for name in expected}, expected
        )

    def recover(self, identity, *, finish=True):
        expected = self.new if finish else self.old
        return publication.recover_native_child_publication(
            self.root,
            publication_identity=identity,
            finish=finish,
            validate=lambda: self.verify(expected),
        )

    def test_finish_retains_original_nodes_and_requires_validation(self):
        identity = self.prepare()
        self.assertEqual(
            {n: (self.metadata / n).read_bytes() for n in self.old}, self.old
        )
        with self.assertRaisesRegex(publication.NativeChildPublicationError, "pending"):
            publication.require_no_native_child_publication(self.root)
        self.assertEqual(self.recover(identity)["state"], "committed")
        self.verify(self.new)
        for index, name in enumerate(self.old):
            self.assertEqual(
                publication._key((self.attempt / f"{index}.before").stat()),
                self.original[name],
            )
        self.assertTrue((self.attempt / "committed.json").read_bytes())

    def test_rollback_after_each_rename_preserves_old_inodes_modes_and_mtimes(self):
        for fail_after in range(1, 5):
            with self.subTest(fail_after=fail_after):
                # Separate real trees and metadata for every interruption point.
                self.setUp()
                identity = self.prepare()
                rename = publication._move_exclusive
                count = 0

                def fault(
                    source, destination, expected, guard, move=rename, stop=fail_after
                ):
                    nonlocal count
                    move(source, destination, expected, guard)
                    count += 1
                    if count == stop:
                        raise OSError("injected after durable rename")

                with mock.patch.object(
                    publication, "_move_exclusive", side_effect=fault
                ):
                    with self.assertRaises(OSError):
                        self.recover(identity)
                with self.assertRaisesRegex(
                    publication.NativeChildPublicationError, "pending"
                ):
                    publication.require_no_native_child_publication(self.root)
                self.assertEqual(
                    self.recover(identity, finish=False)["state"], "rolled-back"
                )
                self.verify(self.old)
                for name in self.old:
                    self.assertEqual(
                        publication._key((self.metadata / name).stat()),
                        self.original[name],
                    )

    def test_finish_after_abrupt_process_exit_between_files(self):
        identity = self.prepare()
        code = r"""
import os,sys
from pathlib import Path
from literate_ai.adapters import native_child_publication as p
rename=p._move_exclusive
count=0
def fault(source,destination,expected,guard):
 global count
 rename(source,destination,expected,guard)
 count+=1
 if count==2:os._exit(73)
p._move_exclusive=fault
p.recover_native_child_publication(Path(sys.argv[1]),publication_identity=sys.argv[2],finish=True,validate=lambda:None)
"""
        result = subprocess.run(
            [sys.executable, "-c", code, str(self.root), identity],
            capture_output=True,
            timeout=30,
        )
        self.assertEqual(result.returncode, 73, result.stderr)
        self.assertEqual(self.recover(identity)["state"], "committed")
        self.verify(self.new)

    def test_foreign_equal_byte_target_replacement_is_preserved(self):
        identity = self.prepare()
        target = self.metadata / "conversion-authority.json"
        foreign = self.metadata / "foreign"
        foreign.write_bytes(target.read_bytes())
        os.replace(foreign, target)
        node = target.stat().st_ino
        with self.assertRaisesRegex(
            publication.NativeChildPublicationError, "foreign_node"
        ):
            self.recover(identity)
        self.assertEqual(target.stat().st_ino, node)
        self.assertEqual(target.read_bytes(), self.old[target.name])
        self.assertEqual(
            (self.metadata / "native-projects.json").read_bytes(),
            self.old["native-projects.json"],
        )
        # No companion mutation is allowed after another bound node has drifted.
        with self.assertRaisesRegex(publication.NativeChildPublicationError, "pending"):
            publication.require_no_native_child_publication(self.root)

    def test_foreign_member_and_staged_inode_refuse_before_mutation(self):
        identity = self.prepare()
        foreign = self.attempt / "foreign"
        foreign.write_bytes(b"preserve")
        with self.assertRaisesRegex(
            publication.NativeChildPublicationError, "foreign_member"
        ):
            self.recover(identity)
        self.assertEqual(foreign.read_bytes(), b"preserve")
        self.assertEqual(
            {n: (self.metadata / n).read_bytes() for n in self.old}, self.old
        )
        foreign.unlink()
        stage = self.attempt / "0.after"
        replacement = self.attempt / "replacement"
        replacement.write_bytes(stage.read_bytes())
        os.replace(replacement, stage)
        node = stage.stat().st_ino
        with self.assertRaisesRegex(
            publication.NativeChildPublicationError, "foreign_node"
        ):
            self.recover(identity)
        self.assertEqual(stage.stat().st_ino, node)
        self.assertEqual(
            {n: (self.metadata / n).read_bytes() for n in self.old}, self.old
        )

    def test_validation_failure_remains_pending_and_can_restore_original(self):
        identity = self.prepare()
        with self.assertRaisesRegex(ValueError, "current qualification"):
            publication.recover_native_child_publication(
                self.root,
                publication_identity=identity,
                finish=True,
                validate=lambda: (_ for _ in ()).throw(
                    ValueError("current qualification refused")
                ),
            )
        with self.assertRaisesRegex(publication.NativeChildPublicationError, "pending"):
            publication.require_no_native_child_publication(self.root)
        self.recover(identity, finish=False)
        self.verify(self.old)

    def test_validation_cannot_mutate_published_bytes_then_report_success(self):
        identity = self.prepare()

        def tamper():
            self.verify(self.new)
            (self.metadata / "native-projects.json").write_bytes(
                b"foreign callback edit"
            )

        with self.assertRaisesRegex(
            publication.NativeChildPublicationError, "foreign_node"
        ):
            publication.recover_native_child_publication(
                self.root, publication_identity=identity, finish=True, validate=tamper
            )
        self.assertTrue((self.metadata / publication._ACTIVE).exists())
        self.assertEqual(
            (self.metadata / "native-projects.json").read_bytes(),
            b"foreign callback edit",
        )

    def test_wrong_acknowledgement_and_duplicate_prepare_refuse(self):
        identity = self.prepare()
        wrong = canonical_identity({"other": "plan"}).uri
        with self.assertRaisesRegex(
            publication.NativeChildPublicationError, "acknowledgement_mismatch"
        ):
            self.recover(wrong)
        with self.assertRaisesRegex(publication.NativeChildPublicationError, "pending"):
            self.prepare()
        self.recover(identity, finish=False)

    @unittest.skipUnless(hasattr(os, "symlink"), "requires native links")
    def test_linked_metadata_is_never_followed(self):
        target = self.metadata / "native-projects.json"
        external = self.root / "external"
        external.write_bytes(target.read_bytes())
        target.unlink()
        target.symlink_to(external)
        with self.assertRaises(publication.NativeChildPublicationError):
            self.prepare()
        self.assertEqual(external.read_bytes(), self.old[target.name])

    def test_partial_terminal_write_recovers_by_verified_append(self):
        identity = self.prepare()
        write = publication.os.write
        injected = False

        def partial(fd, content):
            nonlocal injected
            if not injected and bytes(content).startswith(b'{"plan_identity"'):
                injected = True
                write(fd, content[:17])
                raise OSError("partial terminal write")
            return write(fd, content)

        with mock.patch.object(publication.os, "write", side_effect=partial):
            with self.assertRaises(OSError):
                self.recover(identity)
        slot = self.attempt / "committed.json"
        before = slot.read_bytes()
        self.assertEqual(len(before), 17)
        inode = slot.stat().st_ino
        self.recover(identity)
        self.assertEqual(slot.stat().st_ino, inode)
        self.assertTrue(slot.read_bytes().startswith(before))
        self.verify(self.new)

    @unittest.skipIf(os.name == "nt", "POSIX native rename injection")
    def test_raced_destination_is_never_replaced(self):
        identity = self.prepare()
        original = publication._native_rename
        inserted = False

        def race(source_parent, source, destination, target_parent=None):
            nonlocal inserted
            if not inserted:
                inserted = True
                fd = os.open(
                    destination,
                    os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                    0o600,
                    dir_fd=target_parent,
                )
                try:
                    os.write(fd, b"foreign raced destination")
                finally:
                    os.close(fd)
            return original(source_parent, source, destination, target_parent)

        with mock.patch.object(publication, "_native_rename", side_effect=race):
            with self.assertRaises(FileExistsError):
                self.recover(identity)
        self.assertEqual(
            (self.attempt / "0.before").read_bytes(), b"foreign raced destination"
        )
        self.assertEqual(
            {n: (self.metadata / n).read_bytes() for n in self.old}, self.old
        )

    def test_canonical_readers_refuse_mixed_metadata(self):
        from literate_ai.adapters.conversion_authority import (
            ConversionAuthorityError,
            FilesystemConversionAuthorityStore,
            _native_project_roots,
        )
        from literate_ai.projects import LoadedProject, ProjectError
        from literate_ai.test_receipts import inspect_project_test_receipt
        from tests.support.fixtures_test_project_agent_development_workflow import (
            _definition,
        )

        identity = self.prepare()
        move = publication._move_exclusive
        count = 0

        def interrupt(source, destination, expected, guard):
            nonlocal count
            move(source, destination, expected, guard)
            count += 1
            if count == 2:
                raise OSError("between registry and evidence publication")

        with mock.patch.object(publication, "_move_exclusive", side_effect=interrupt):
            with self.assertRaises(OSError):
                self.recover(identity)
        project = LoadedProject(self.root, _definition(project_id="metadata-test"))
        with self.assertRaisesRegex(ConversionAuthorityError, "transition"):
            FilesystemConversionAuthorityStore(self.root).load_optional()
        with self.assertRaisesRegex(ConversionAuthorityError, "transition"):
            _native_project_roots(project)
        with self.assertRaisesRegex(ProjectError, "transition"):
            inspect_project_test_receipt(
                project,
                project_revision_identity=canonical_identity({"test": "revision"}),
            )
        self.recover(identity, finish=False)
        self.verify(self.old)

    def test_equal_byte_foreign_terminal_slot_refuses_before_publication(self):
        identity = self.prepare()
        slot = self.attempt / "committed.json"
        foreign = self.attempt / "foreign-slot"
        foreign.write_bytes(slot.read_bytes())
        os.replace(foreign, slot)
        node = slot.stat().st_ino
        with self.assertRaisesRegex(
            publication.NativeChildPublicationError, "foreign_node"
        ):
            self.recover(identity)
        self.assertEqual(slot.stat().st_ino, node)
        self.assertEqual(
            {n: (self.metadata / n).read_bytes() for n in self.old}, self.old
        )

    def test_copied_validation_context_expires_on_failure(self):
        import contextvars

        identity = self.prepare()
        contexts = []

        def verify_then_fail():
            self.verify(self.new)
            contexts.append(contextvars.copy_context())
            raise ValueError("validation interrupted")

        with self.assertRaisesRegex(ValueError, "validation interrupted"):
            publication.recover_native_child_publication(
                self.root,
                publication_identity=identity,
                finish=True,
                validate=verify_then_fail,
            )
        with self.assertRaisesRegex(publication.NativeChildPublicationError, "pending"):
            contexts[0].run(publication.require_no_native_child_publication, self.root)
        self.recover(identity, finish=False)
        self.verify(self.old)
