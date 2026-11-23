"""Failed readmission must retain canonical and history nodes it does not own."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import component_lock_commands
from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.projects import ProjectConfigurationStore
from tests.e2e import test_retained_harness_readmission as fixtures


class ReadmissionPublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.RetainedHarnessReadmissionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedHarnessReadmissionTests.setUp(self)
        fixtures.RetainedHarnessReadmissionTests.make_unqualified_false_bazel_state(
            self
        )
        self.plan = readmission.plan_retained_harness_readmission(self.root)
        self.assertTrue(self.plan["changes_required"])

    def apply(self):
        return readmission.apply_retained_harness_readmission(
            self.root,
            expected_plan_identity=self.plan["plan_identity"],
            acknowledge=True,
            timeout_seconds=1800,
            execution_worker=None,
            worker_catalog_identity=None,
        )

    def test_failed_lock_writer_preserves_foreign_replacement(self):
        lock = self.root / self.plan["wrapper_component"] / "component.lock.json"
        foreign = b'{"foreign":"must survive failed lock publication"}\n'
        observed = []

        def foreign_writer(*args, **kwargs):
            replacement = self.base / "foreign-lock.json"
            replacement.write_bytes(foreign)
            replacement.replace(lock)
            observed.append(lock.stat().st_ino)
            raise RuntimeError("the lock producer failed after a foreign replacement")

        with mock.patch.object(
            component_lock_commands,
            "_component_locks_from_args",
            side_effect=foreign_writer,
        ):
            with self.assertRaises(RuntimeError):
                self.apply()
        self.assertEqual(lock.read_bytes(), foreign)
        self.assertEqual(lock.stat().st_ino, observed[0])

    def test_same_byte_foreign_inventory_replacement_survives_rollback(self):
        inventory = self.root / readmission.INVENTORY
        observed = []

        def foreign_writer(*args, **kwargs):
            content = inventory.read_bytes()
            replacement = self.base / "foreign-inventory.json"
            replacement.write_bytes(content)
            replacement.replace(inventory)
            observed.append((content, inventory.stat().st_ino))
            raise RuntimeError("manifest publication failed after replacement")

        with mock.patch.object(
            ProjectConfigurationStore, "update", side_effect=foreign_writer
        ):
            with self.assertRaises(RuntimeError):
                self.apply()
        self.assertEqual(inventory.read_bytes(), observed[0][0])
        self.assertEqual(inventory.stat().st_ino, observed[0][1])

    def test_foreign_evidence_history_entry_survives_rollback(self):
        observed = []
        foreign = b"unique foreign evidence; do not recursively delete\n"

        def foreign_writer(*args, **kwargs):
            directories = list((self.root / readmission.HISTORY).glob("*.evidence"))
            self.assertEqual(len(directories), 1)
            path = directories[0] / "foreign-note.txt"
            path.write_bytes(foreign)
            observed.append((path, path.stat().st_ino))
            raise RuntimeError("lock publication failed after foreign history write")

        with mock.patch.object(
            component_lock_commands,
            "_component_locks_from_args",
            side_effect=foreign_writer,
        ):
            with self.assertRaises(RuntimeError):
                self.apply()
        self.assertTrue(observed[0][0].is_file())
        self.assertEqual(observed[0][0].read_bytes(), foreign)
        self.assertEqual(observed[0][0].stat().st_ino, observed[0][1])

    def test_foreign_staged_history_entry_survives_failed_evidence_copy(self):
        original_open = Path.open
        observed = []
        foreign = b"foreign staging data; do not recursively delete\n"
        history = self.root / readmission.HISTORY

        def failed_copy(path, mode="r", *args, **kwargs):
            if (
                mode == "xb"
                and path.name == Path(readmission.INVENTORY).name
                and path.is_relative_to(history)
            ):
                note = path.parent / "foreign-staging-note.txt"
                note.write_bytes(foreign)
                observed.append((note, note.stat().st_ino))
                raise OSError("injected evidence copy failure")
            return original_open(path, mode, *args, **kwargs)

        with mock.patch.object(Path, "open", new=failed_copy):
            with self.assertRaisesRegex(OSError, "evidence copy failure"):
                self.apply()
        self.assertEqual(len(observed), 1)
        self.assertTrue(observed[0][0].is_file())
        self.assertEqual(observed[0][0].read_bytes(), foreign)
        self.assertEqual(observed[0][0].stat().st_ino, observed[0][1])
