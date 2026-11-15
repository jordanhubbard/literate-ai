"""Explicit source-link policy, target identity and immutable quarantine custody."""

import hashlib
import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters.source.git import GitSourceAdapter
from literate_ai.contracts import SourceEntryType, canonical_identity
from literate_ai.sources import (
    InternalSymlinkSnapshotPolicy,
    QuarantineError,
    QuarantineStore,
    SnapshotPolicy,
    SourceSnapshotError,
    SourceSnapshotter,
    internal_links,
)
from literate_ai.storage import FileSystemCAS


@unittest.skipIf(os.name == "nt", "Explicit POSIX source-link custody")
class SourceLinkCustodyTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "src").mkdir()
        (self.source / "src/main.c").write_bytes(b"int main(void) { return 0; }\n")
        self.snapshotter = SourceSnapshotter(InternalSymlinkSnapshotPolicy())

    def capture(self):
        return self.snapshotter.snapshot_local(self.source)

    def store(self):
        return QuarantineStore(self.root / "cache", FileSystemCAS(self.root / "cas"))

    def writable_cache(self, path):
        # Do not follow aliases even in fixture teardown/tamper setup.
        for current, _directories, files in os.walk(path):
            os.chmod(current, 0o700)
            for name in files:
                child = Path(current) / name
                if not child.is_symlink():
                    os.chmod(child, 0o600)

    def test_legacy_policy_and_provider_identities_remain_unchanged(self):
        policy = SnapshotPolicy()
        self.assertEqual(
            policy.to_dict(),
            {
                "schema": "urn:literate-ai:schema:v1:snapshot-policy",
                "excluded_top_level": [".codegraph", ".git"],
                "reject_symlinks": True,
            },
        )
        default = SourceSnapshotter().snapshot_local(self.source)
        self.assertEqual(
            default.snapshot.provider_configuration,
            canonical_identity(policy.to_dict()),
        )
        with self.assertRaises(ValueError):
            SnapshotPolicy(reject_symlinks=False)
        (self.source / "alias").symlink_to("src/main.c")
        with self.assertRaises(SourceSnapshotError):
            SourceSnapshotter().snapshot_local(self.source)

    def test_raw_target_kind_and_identity_are_preserved(self):
        (self.source / "alias").symlink_to("src/./main.c")
        capture = self.capture()
        entry = next(e for e in capture.snapshot.entries if e.path == "alias")
        self.assertIs(entry.entry_type, SourceEntryType.SYMLINK)
        self.assertEqual(entry.mode, 0o777)
        self.assertEqual(entry.size, len(b"src/./main.c"))
        self.assertEqual(
            entry.identity.digest, hashlib.sha256(b"src/./main.c").hexdigest()
        )
        (self.source / "alias").unlink()
        (self.source / "alias").symlink_to("src/main.c")
        self.assertNotEqual(capture.snapshot.identity, self.capture().snapshot.identity)

    def test_directory_alias_and_finite_parent_alias_are_not_walked(self):
        (self.source / "headers").symlink_to("src", target_is_directory=True)
        (self.source / "src/self").symlink_to(".", target_is_directory=True)
        (self.source / "src/parent").symlink_to("..", target_is_directory=True)
        self.assertEqual(
            {e.path for e in self.capture().snapshot.entries},
            {"headers", "src/main.c", "src/self", "src/parent"},
        )

    def test_escape_dangling_cycles_and_link_ancestors_are_refused(self):
        cases = [
            ("alias", "../outside"),
            ("alias", "/etc/passwd"),
            ("alias", "missing"),
            ("alias", "alias"),
            ("alias", "src/main.c/../main.c"),
        ]
        for name, target in cases:
            with self.subTest(target=target):
                (self.source / name).symlink_to(target)
                with self.assertRaises(SourceSnapshotError):
                    self.capture()
                (self.source / name).unlink()
        (self.source / "one").symlink_to("two")
        (self.source / "two").symlink_to("one")
        with self.assertRaises(SourceSnapshotError):
            self.capture()
        (self.source / "one").unlink()
        (self.source / "two").unlink()
        (self.source / "headers").symlink_to("src", target_is_directory=True)
        (self.source / "alias").symlink_to("headers/main.c")
        with self.assertRaises(SourceSnapshotError):
            self.capture()

    def test_git_selected_closure_cannot_borrow_untracked_targets(self):
        subprocess.run(["git", "init", "-q", str(self.source)], check=True)
        subprocess.run(
            [
                "git",
                "-C",
                str(self.source),
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "--allow-empty",
                "-qm",
                "empty",
            ],
            check=True,
        )
        (self.source / "alias").symlink_to("src/main.c")
        subprocess.run(["git", "-C", str(self.source), "add", "alias"], check=True)
        adapter = GitSourceAdapter(snapshotter=self.snapshotter)
        with self.assertRaises(SourceSnapshotError):
            adapter.capture(self.source)
        subprocess.run(["git", "-C", str(self.source), "add", "src/main.c"], check=True)
        self.assertEqual(len(adapter.capture(self.source).snapshot.entries), 2)

    def test_quarantine_roundtrip_preserves_links_and_original_source_can_retire(self):
        (self.source / "alias").symlink_to("src/./main.c")
        (self.source / "headers").symlink_to("src", target_is_directory=True)
        (self.source / "chain").symlink_to("alias")
        capture = self.capture()
        store = self.store()
        record = store.materialize(capture, self.source)
        self.addCleanup(self.writable_cache, self.root / "cache")
        self.source.rename(self.root / "retired")
        record.verify()
        reopened = store.materialize(capture, self.root / "retired")
        self.assertEqual(reopened.tree_path, record.tree_path)
        for name, target in [
            ("alias", "src/./main.c"),
            ("headers", "src"),
            ("chain", "alias"),
        ]:
            self.assertTrue((record.tree_path / name).is_symlink())
            self.assertEqual(os.readlink(record.tree_path / name), target)
        self.assertEqual(
            stat.S_IMODE((record.tree_path / "src/main.c").stat().st_mode), 0o400
        )

    def test_source_target_drift_and_quarantine_link_drift_are_refused(self):
        (self.source / "alias").symlink_to("src/main.c")
        capture = self.capture()
        (self.source / "alias").unlink()
        (self.source / "alias").symlink_to("src/./main.c")
        store = self.store()
        with self.assertRaises(QuarantineError):
            store.materialize(capture, self.source)
        (self.source / "alias").unlink()
        (self.source / "alias").symlink_to("src/main.c")
        record = store.materialize(capture, self.source)
        self.addCleanup(self.writable_cache, self.root / "cache")
        os.chmod(record.tree_path, 0o700)
        (record.tree_path / "alias").unlink()
        (record.tree_path / "alias").symlink_to("../record.json")
        with self.assertRaises(QuarantineError):
            record.verify()

    def test_unexpected_link_and_regular_file_replaced_by_link_are_refused(self):
        capture = self.capture()
        record = self.store().materialize(capture, self.source)
        self.addCleanup(self.writable_cache, self.root / "cache")
        os.chmod(record.tree_path, 0o700)
        (record.tree_path / "extra").symlink_to("src")
        with self.assertRaises(QuarantineError):
            record.verify()
        (record.tree_path / "extra").unlink()
        os.chmod(record.tree_path / "src", 0o700)
        (record.tree_path / "src/main.c").unlink()
        (record.tree_path / "src/main.c").symlink_to("/etc/passwd")
        with self.assertRaises(QuarantineError):
            record.verify()

    def test_aggregate_preserves_closed_member_aliases(self):
        (self.source / "alias").symlink_to("src", target_is_directory=True)
        capture = self.capture()
        store = self.store()
        record = store.materialize(capture, self.source)
        self.addCleanup(self.writable_cache, self.root / "cache")
        aggregate = SourceSnapshotter.aggregate((("member", "vendor/member", capture),))
        result = store.materialize_aggregate(aggregate, {"member": record})
        result.verify()
        self.assertEqual(os.readlink(result.tree_path / "vendor/member/alias"), "src")
        self.assertTrue((result.tree_path / "vendor/member/alias/main.c").is_file())

    def test_regular_source_ancestor_redirect_is_refused_before_copy(self):
        capture = self.capture()
        (self.source / "src").rename(self.source / "retired-src")
        (self.source / "src").symlink_to("retired-src", target_is_directory=True)
        with self.assertRaises(QuarantineError):
            self.store().materialize(capture, self.source)

    def test_quarantine_regular_ancestor_redirect_is_refused(self):
        record = self.store().materialize(self.capture(), self.source)
        self.addCleanup(self.writable_cache, self.root / "cache")
        os.chmod(record.tree_path, 0o700)
        (record.tree_path / "src").rename(record.tree_path / "retired-src")
        (record.tree_path / "src").symlink_to("retired-src", target_is_directory=True)
        with self.assertRaises(QuarantineError):
            record.verify()

    def test_ancestor_swap_during_link_read_is_refused(self):
        (self.source / "alias").symlink_to("src/main.c")
        real_readlink = os.readlink

        def swap(*args, **kwargs):
            data = real_readlink(*args, **kwargs)
            self.source.rename(self.root / "old-source")
            self.source.mkdir()
            return data

        with mock.patch.object(internal_links.os, "readlink", side_effect=swap):
            with self.assertRaises(ValueError):
                internal_links.read_source_entry(self.source, "alias", symlink=True)

    def test_payload_change_invalidates_identity_even_when_link_text_is_same(self):
        (self.source / "alias").symlink_to("src/main.c")
        before = self.capture()
        (self.source / "src/main.c").write_bytes(b"different payload")
        self.assertNotEqual(before.snapshot.identity, self.capture().snapshot.identity)
        with self.assertRaises(QuarantineError):
            self.store().materialize(before, self.source)

    def test_link_unaware_intelligence_is_refused_before_provider_execution(self):
        (self.source / "alias").symlink_to("src", target_is_directory=True)
        store = self.store()
        record = store.materialize(self.capture(), self.source)
        self.addCleanup(self.writable_cache, self.root / "cache")
        provider = mock.Mock()
        with self.assertRaisesRegex(QuarantineError, "link-aware"):
            store.attach_source_intelligence(record, provider)
        provider.assert_not_called()

    def test_failed_materialization_cleanup_does_not_chmod_link_targets(self):
        outside = self.root / "outside"
        outside.write_bytes(b"private")
        outside.chmod(0o400)
        (self.source / "alias").symlink_to("src/main.c")
        capture = self.capture()
        real_symlink = os.symlink

        def redirect(_target, destination, **kwargs):
            return real_symlink(str(outside), destination, **kwargs)

        with mock.patch(
            "literate_ai.sources.quarantine.os.symlink", side_effect=redirect
        ):
            with self.assertRaises(QuarantineError):
                self.store().materialize(capture, self.source)
        self.assertEqual(stat.S_IMODE(outside.stat().st_mode), 0o400)

    def test_low_level_reader_refuses_noncanonical_relative_paths(self):
        for name in ("../outside", "/etc/passwd", "src/../src/main.c"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    internal_links.read_source_entry(self.source, name, symlink=False)

    def test_mode_change_between_selection_and_open_is_refused(self):
        real_read = internal_links.read_source_entry

        def change(root, relative, **kwargs):
            (root / relative).chmod(0o755)
            return real_read(root, relative, **kwargs)

        with mock.patch(
            "literate_ai.sources.snapshot.read_source_entry", side_effect=change
        ):
            with self.assertRaises(SourceSnapshotError):
                self.capture()
