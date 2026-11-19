"""Opt-in, read-only qualification against an operator-selected real Git tree."""

import hashlib
import json
import os
import subprocess
import unittest
from pathlib import Path

from literate_ai.adapters.source.repository_git import GitRepositorySourceCapturer
from literate_ai.application.repository_sources import RepositoryCheckout
from literate_ai.contracts import SourceEntryType, canonical_identity
from literate_ai.sources import InternalSymlinkSnapshotPolicy, SourceSnapshotter


@unittest.skipUnless(
    os.environ.get("LITAI_SOURCE_LINK_CORPUS"), "requires explicit Git corpus"
)
@unittest.skipIf(os.name == "nt", "Explicit POSIX link custody")
class SourceLinkCorpusTests(unittest.TestCase):
    def test_actual_git_modes_names_payloads_and_raw_link_targets(self):
        root = Path(os.environ["LITAI_SOURCE_LINK_CORPUS"]).resolve(strict=True)

        def git(*args):
            return subprocess.check_output(
                [
                    "git",
                    "--no-optional-locks",
                    "-c",
                    "core.hooksPath=/dev/null",
                    "-c",
                    "diff.external=",
                    "-C",
                    str(root),
                    *args,
                ],
                timeout=60,
            )

        revision = git("rev-parse", "HEAD").decode().strip()
        self.assertEqual(git("status", "--porcelain", "--untracked-files=no"), b"")
        expected = {}
        for row in git("ls-tree", "-rz", revision).split(b"\0"):
            if row:
                metadata, name = row.split(b"\t", 1)
                mode, kind, oid = metadata.decode().split()
                self.assertEqual(kind, "blob")
                expected[name.decode()] = mode, oid
        captured = GitRepositorySourceCapturer(
            snapshotter=SourceSnapshotter(InternalSymlinkSnapshotPolicy())
        ).capture(
            RepositoryCheckout(root, revision, canonical_identity("corpus-resolver"))
        )
        self.assertEqual(captured.git.head_commit, revision)
        self.assertFalse(captured.git.dirty)
        entries = captured.snapshot.entries
        self.assertEqual({e.path for e in entries}, set(expected))
        links = []
        for entry in entries:
            mode, oid = expected[entry.path]
            if mode == "120000":
                self.assertIs(entry.entry_type, SourceEntryType.SYMLINK)
                target = git("cat-file", "blob", oid)
                self.assertEqual(entry.size, len(target))
                self.assertEqual(
                    entry.identity.digest, hashlib.sha256(target).hexdigest()
                )
                self.assertEqual(os.fsencode(os.readlink(root / entry.path)), target)
                links.append(entry.path)
            else:
                self.assertIs(entry.entry_type, SourceEntryType.FILE)
                self.assertEqual(entry.mode, {"100644": 0o644, "100755": 0o755}[mode])
        self.assertTrue(links)
        # Independently compare every snapshot SHA-256 with the exact committed
        # Git blob. Stream one request/body at a time; never retain all payloads.
        process = subprocess.Popen(
            ["git", "--no-optional-locks", "-C", str(root), "cat-file", "--batch"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
        verified_bytes = 0
        try:
            for entry in entries:
                oid = expected[entry.path][1]
                process.stdin.write((oid + "\n").encode())
                process.stdin.flush()
                header = process.stdout.readline().decode().split()
                self.assertEqual(header[:2], [oid, "blob"])
                remaining = int(header[2])
                self.assertEqual(remaining, entry.size)
                digest = hashlib.sha256()
                while remaining:
                    block = process.stdout.read(min(1024 * 1024, remaining))
                    self.assertTrue(block, "Git blob ended before declared size")
                    digest.update(block)
                    remaining -= len(block)
                    verified_bytes += len(block)
                self.assertEqual(process.stdout.read(1), b"\n")
                self.assertEqual(digest.hexdigest(), entry.identity.digest)
            process.stdin.close()
            self.assertEqual(process.wait(timeout=120), 0)
        finally:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=10)
            process.stdout.close()
            if not process.stdin.closed:
                process.stdin.close()
        self.assertEqual(git("rev-parse", "HEAD").decode().strip(), revision)
        self.assertEqual(git("status", "--porcelain", "--untracked-files=no"), b"")
        result = {
            "revision": revision,
            "snapshot_identity": captured.snapshot_id,
            "tree_identity": captured.tree_id,
            "entries": len(entries),
            "symlinks": len(links),
            "git_names_modes_and_raw_targets_match": True,
            "all_snapshot_sha256_match_committed_git_blobs": True,
            "independently_verified_bytes": verified_bytes,
            "scope": "actual source snapshot only; no quarantine, build or acceptance",
        }
        report = os.environ.get("LITAI_SOURCE_LINK_CORPUS_REPORT")
        if report:
            path = Path(report).absolute()
            self.assertFalse(path == root or root in path.parents)
            with path.open("x") as output:
                json.dump(result, output, indent=2)
                output.write("\n")
        print(json.dumps(result))
