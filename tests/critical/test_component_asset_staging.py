"""Actual asset stream/CAS custody; HTTP response is an inert fixture."""

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import component_lock_planning as planning
from literate_ai.storage.cas import FileSystemCAS


class Response(io.BytesIO):
    def geturl(self):
        return "https://assets.invalid/fixture"


class ComponentAssetStagingTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.cas = FileSystemCAS(self.base / "project/litai/_build/candidate-cas")
        self.payload = b"actual asset bytes" * 100

    def fetch(self):
        with patch.object(
            planning.urllib.request, "urlopen", return_value=Response(self.payload)
        ):
            return planning._remote_asset_to_cas(
                "https://assets.invalid/fixture",
                media_type="application/octet-stream",
                cas=self.cas,
            )

    def test_actual_stream_stays_in_original_candidate_cas(self):
        original = self.cas.put_file
        observed = []

        def admit(source, **kwargs):
            observed.append(Path(source))
            self.assertEqual(Path(source).read_bytes(), self.payload)
            return original(source, **kwargs)

        with patch.object(self.cas, "put_file", side_effect=admit):
            reference = self.fetch()
        self.assertEqual(reference.size, len(self.payload))
        self.assertEqual(len(observed), 1)
        self.assertTrue(observed[0].is_relative_to(self.cas.root), observed)
        self.assertFalse(observed[0].exists())

    def test_declared_stream_limit_refuses_and_retires_original_partial(self):
        with patch.object(planning, "_MAXIMUM_ASSET_BYTES", 4):
            with self.assertRaises(planning.ComponentLockPlanningError) as caught:
                self.fetch()
        self.assertEqual(caught.exception.code, "component_lock.asset_limit")
        self.assertFalse(list(self.cas.root.glob(".asset-*")))

    def test_non_http_redirect_refuses_and_retires_original_creator(self):
        with patch.object(Response, "geturl", return_value="file:///fixture"):
            with self.assertRaises(planning.ComponentLockPlanningError) as caught:
                self.fetch()
        self.assertEqual(caught.exception.code, "component_lock.asset_unsafe")
        self.assertFalse(list(self.cas.root.glob(".asset-*")))

    def test_partial_response_failure_retires_actual_stream(self):
        reads = []

        def read(response, count):
            if reads:
                raise OSError(5, "fixture partial response failure")
            reads.append(count)
            return b"actual partial bytes"

        with patch.object(Response, "read", read):
            with self.assertRaises(planning.ComponentLockPlanningError) as caught:
                self.fetch()
        self.assertEqual(caught.exception.code, "component_lock.asset_unavailable")
        self.assertEqual(reads, [planning._ASSET_READ_CHUNK])
        self.assertFalse(list(self.cas.root.glob(".asset-*")))

    def test_foreign_file_retains_original_download_rejection(self):
        observed = {}

        def read(response, count):
            roots = list(self.cas.root.glob(".asset-*"))
            self.assertEqual(len(roots), 1)
            private = roots[0] / "operator-private"
            private.write_bytes(b"preserve original foreign payload")
            observed.update(path=private, inode=private.stat().st_ino)
            raise OSError(5, "fixture original response rejected")

        with patch.object(Response, "read", read):
            with self.assertRaises(planning.ComponentLockPlanningError) as caught:
                self.fetch()
        self.assertEqual(caught.exception.code, "component_lock.asset_unavailable")
        self.assertEqual(observed["path"].stat().st_ino, observed["inode"])
        self.assertEqual(
            observed["path"].read_bytes(), b"preserve original foreign payload"
        )
        self.assertTrue(
            any("Stage disposal refused" in note for note in caught.exception.__notes__)
        )

    def test_equal_byte_foreign_replacement_is_never_unlinked(self):
        from literate_ai.adapters.evidence_staging import EvidenceStagingError

        original = self.cas.put_file
        observed = {}

        def admit(source, **kwargs):
            result = original(source, **kwargs)
            path = Path(source)
            retained = self.base / "actual-original-asset"
            path.rename(retained)
            path.write_bytes(retained.read_bytes())
            observed.update(path=path, inode=path.stat().st_ino, retained=retained)
            return result

        with patch.object(self.cas, "put_file", side_effect=admit):
            with self.assertRaises(EvidenceStagingError):
                self.fetch()
        self.assertEqual(observed["path"].stat().st_ino, observed["inode"])
        self.assertEqual(observed["path"].read_bytes(), self.payload)
        self.assertEqual(observed["retained"].read_bytes(), self.payload)
