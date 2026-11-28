"""Native intermediate-span checks; no source-phase execution acceptance.

The parking fixture uses the real exclusive native primitive in an unmanaged
scratch tree and records its actual post-move native observations. It supplies
no fabricated project phase, receipt capability, or decoded movement permission.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_source_admission as fixtures
from literate_ai.adapters import retained_layout_forest_span as spans
from literate_ai.adapters import retained_project_inputs as inputs
from literate_ai.adapters.exclusive_entry import (
    layout_entry_node,
    move_layout_entry_exclusive,
)
from literate_ai.adapters.retained_cargo_tree_v2 import capture_retained_cargo_tree_v2
from literate_ai.adapters.retained_layout_partition import _lineage
from literate_ai.adapters.retained_layout_source_preparation import (
    prepared_retained_layout_source_move,
)
from literate_ai.adapters.retained_layout_transaction import _native_tree
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


@unittest.skipUnless(os.name == "posix", "actual no-follow parked alias custody")
class ForestRuntimeSpanTests(unittest.TestCase):
    def setUp(self):
        temporary = self.enterContext(
            tempfile.TemporaryDirectory(prefix="forest-span-")
        )
        self.base = Path(temporary).resolve()
        self.root, self.park = self.base / "project", self.base / "park"
        (self.root / "source").mkdir(parents=True)
        self.park.mkdir()
        (self.root / "source/target.bin").write_bytes(b"retained original payload\n")
        (self.root / "alias").symlink_to("source/target.bin")
        self.budget = RetainedCargoInputBudget(128, 1024, 1024**2, 8 * 1024**2)
        self.metadata = 32 * 1024**2

    def capture(self):
        tree = capture_retained_cargo_tree_v2(
            self.root, budget=self.budget, maximum_metadata_bytes=self.metadata
        )
        native = _native_tree(tree)
        root = spans._from_namespace(tree, native, _lineage(self.root))
        return tree, spans._ForestSpan((root,), self.budget, self.metadata)

    def test_full_large_payload_uses_bounded_native_stream_and_eof(self):
        payload = self.root / "source/target.bin"
        body = bytes(range(256)) * 3073
        payload.write_bytes(body)
        _tree, span = self.capture()
        original = inputs.os.fdopen
        requests, observed = [], []

        class Stream:
            def __init__(self, actual):
                self.actual = actual

            def __enter__(self):
                self.actual.__enter__()
                return self

            def __exit__(self, *args):
                return self.actual.__exit__(*args)

            def fileno(self):
                return self.actual.fileno()

            def read(self, size):
                requests.append(size)
                data = self.actual.read(size)
                observed.append(data)
                return data

        with mock.patch.object(
            inputs.os, "fdopen", side_effect=lambda *a, **k: Stream(original(*a, **k))
        ):
            spans._require_current(span)
        self.assertGreater(len(requests), 10)
        self.assertLessEqual(max(requests), spans._NATIVE_PAYLOAD_CHUNK)
        self.assertEqual(b"".join(observed), body)
        self.assertEqual(observed[-1], b"")

    def test_large_stream_still_closes_late_original_native_mutation(self):
        payload = self.root / "source/target.bin"
        payload.write_bytes(b"original" * 100000)
        _tree, span = self.capture()
        original = spans._stream
        changed = b"changed!" * 100000

        def mutate(*args, **kwargs):
            result = original(*args, **kwargs)
            payload.write_bytes(changed)
            return result

        with mock.patch.object(spans, "_stream", side_effect=mutate):
            with self.assertRaisesRegex(ValueError, "native facts changed"):
                spans._require_current(span)
        self.assertEqual(payload.read_bytes(), changed)

    def test_complete_original_namespace_closes_without_following_alias(self):
        _tree, span = self.capture()
        spans._require_current(span)

    def test_temporarily_dangling_original_alias_closes_with_parked_payload(self):
        tree, original = self.capture()
        before = dict(original.roots[0].native)
        source = self.root / "source"
        target = self.park / "carrier-0"
        move_layout_entry_exclusive(
            source,
            target,
            expected_source=before["source"],
            expected_source_parent=before[""],
            expected_destination_parent=layout_entry_node(self.park),
            maximum_directory_entries=self.budget.maximum_entries,
        )
        self.assertFalse((self.root / "alias").exists())
        self.assertTrue((self.root / "alias").is_symlink())
        project = spans._SpanRoot(
            self.root,
            original.roots[0].lineage,
            (("", layout_entry_node(self.root)), ("alias", before["alias"])),
            (),
            original.roots[0].links,
        )
        carrier = layout_entry_node(target)
        self.assertEqual(carrier.after_rename(), before["source"].after_rename())
        parked = spans._SpanRoot(
            self.park,
            _lineage(self.park),
            (
                ("", layout_entry_node(self.park)),
                ("carrier-0", carrier),
                ("carrier-0/target.bin", before["source/target.bin"]),
            ),
            (("carrier-0/target.bin", tree.files[0][1], tree.files[0][2]),),
        )
        span = spans._ForestSpan((project, parked), self.budget, self.metadata)
        spans._require_current(span)
        # Ordinary logical tree validation remains strict during this temporary
        # physical state. The raw span cannot be used as SDK acceptance.
        with self.assertRaises(ValueError):
            capture_retained_cargo_tree_v2(
                self.root, budget=self.budget, maximum_metadata_bytes=self.metadata
            )
        self.assertEqual(
            (target / "target.bin").read_bytes(), b"retained original payload\n"
        )

    def test_unknown_entry_refuses_before_any_payload_read(self):
        _tree, span = self.capture()
        foreign = self.root / "foreign.bin"
        foreign.write_bytes(b"preserve foreign input\n")
        with mock.patch.object(spans, "_stream", side_effect=AssertionError("payload")):
            with self.assertRaisesRegex(ValueError, "unexpected entry"):
                spans._require_current(span)
        self.assertEqual(foreign.read_bytes(), b"preserve foreign input\n")

    def test_late_insertion_after_last_payload_refuses_native_closure(self):
        _tree, span = self.capture()
        stream = spans._stream
        foreign = self.root / "late.bin"

        def insert(*args, **kwargs):
            result = stream(*args, **kwargs)
            foreign.write_bytes(b"late foreign input\n")
            return result

        with mock.patch.object(spans, "_stream", side_effect=insert):
            with self.assertRaisesRegex(ValueError, "native facts changed"):
                spans._require_current(span)
        self.assertEqual(foreign.read_bytes(), b"late foreign input\n")

    def test_complete_hardlink_names_share_one_bounded_payload_read(self):
        os.link(self.root / "source/target.bin", self.root / "hard.bin")
        _tree, span = self.capture()
        with mock.patch.object(spans, "_stream", wraps=spans._stream) as stream:
            spans._require_current(span)
        self.assertEqual(stream.call_count, 1)

    def test_symbolic_text_has_an_explicit_commitment(self):
        _tree, span = self.capture()
        with mock.patch.object(spans, "_link_bytes", return_value=b"different/target"):
            with self.assertRaisesRegex(ValueError, "symbolic text changed"):
                spans._require_current(span)

    def test_overlapping_roots_cannot_hide_membership(self):
        _tree, span = self.capture()
        overlapping = replace(span, roots=(span.roots[0], span.roots[0]))
        with mock.patch.object(spans, "_stream", side_effect=AssertionError("payload")):
            with self.assertRaisesRegex(ValueError, "roots must be disjoint"):
                spans._require_current(overlapping)

    def test_metadata_policy_refuses_before_native_directory_access(self):
        _tree, span = self.capture()
        restricted = replace(span, maximum_metadata_bytes=65536)
        with mock.patch.object(
            spans, "_directory_access", side_effect=AssertionError("native")
        ):
            with self.assertRaisesRegex(ValueError, "metadata or entry policy"):
                spans._require_current(restricted)

    def test_copied_native_root_identity_cannot_describe_a_disjoint_root(self):
        _tree, span = self.capture()
        node = span.roots[0].native[0][1]
        second = replace(
            span.roots[0],
            root=self.park,
            lineage=(
                *_lineage(self.park)[:-1],
                (
                    str(self.park),
                    node.device,
                    node.inode,
                    node.mode,
                    node.uid,
                    node.gid,
                ),
            ),
        )
        copied = replace(span, roots=(*span.roots, second))
        with mock.patch.object(
            spans, "_directory_access", side_effect=AssertionError("native")
        ):
            with self.assertRaisesRegex(ValueError, "physically overlap"):
                spans._require_current(copied)

    def test_grown_file_cannot_open_with_a_larger_than_committed_read_ceiling(self):
        (self.root / "a-first.bin").write_bytes(b"a" * (600 * 1024))
        self.budget = replace(self.budget, maximum_total_bytes=1024**2)
        _tree, span = self.capture()
        stream = spans._stream
        grown = self.root / "source/target.bin"

        def grow(root, name, limit, **kwargs):
            if name == "source/target.bin":
                grown.write_bytes(b"x" * (600 * 1024))
                with mock.patch.object(
                    inputs, "_open_file", side_effect=AssertionError("over-budget open")
                ) as opened:
                    try:
                        return stream(root, name, limit, **kwargs)
                    finally:
                        opened.assert_not_called()
            return stream(root, name, limit, **kwargs)

        with mock.patch.object(spans, "_stream", side_effect=grow):
            with self.assertRaises(ValueError):
                spans._require_current(span)
        self.assertEqual(grown.stat().st_size, 600 * 1024)

    def test_grown_link_text_refuses_before_reading_beyond_its_commitment(self):
        self.budget = replace(
            self.budget, maximum_file_bytes=64, maximum_total_bytes=64
        )
        _tree, span = self.capture()
        readlink = spans._link_bytes
        alias = self.root / "alias"

        def grow(root, name, limit, access):
            alias.unlink()
            alias.symlink_to("x" * 200)
            with mock.patch.object(
                inputs.os,
                "readlink",
                side_effect=AssertionError("over-budget link read"),
            ) as read:
                try:
                    return readlink(root, name, limit, access)
                finally:
                    read.assert_not_called()

        with mock.patch.object(spans, "_link_bytes", side_effect=grow):
            with self.assertRaises(ValueError):
                spans._require_current(span)
        self.assertEqual(os.readlink(alias), "x" * 200)


@unittest.skipUnless(os.name == "posix", "actual original forest participant")
class OriginalForestSpanParticipantTests(unittest.TestCase):
    git = fixtures.SourceAdmissionTests.git
    init_git = fixtures.SourceAdmissionTests.init_git

    @classmethod
    def setUpClass(cls):
        fixtures.SourceAdmissionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.SourceAdmissionTests.setUp(self)
        self.input_budget = replace(self.input_budget, maximum_entries=131072)

    def prepare(self):
        return prepared_retained_layout_source_move(
            self.project,
            ".",
            budget=self.input_budget,
            maximum_metadata_bytes=self.metadata_limit,
        )

    def test_genuine_original_namespace_funds_complete_runtime_description(self):
        (self.source / "alias.py").symlink_to("app.py")
        with self.prepare() as owner:
            before = owner.usage
            with owner._reads():
                span = spans._original_span(owner)
                self.assertEqual(span.roots[0].root, self.project)
                self.assertIn("literate.project.json", dict(span.roots[0].native))
                self.assertIn(
                    (
                        self.source.relative_to(self.project).as_posix() + "/alias.py",
                        "app.py",
                    ),
                    span.roots[0].links,
                )
                spans._require_current(span)
            self.assertGreater(owner.usage["entries"], before["entries"])
            owner.require_current()
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def test_expired_preparation_cannot_construct_another_funded_span(self):
        with self.prepare() as owner:
            with owner._reads():
                span = spans._original_span(owner)
        # The retained description is data. It grants no fresh original owner.
        self.assertIsInstance(span, spans._ForestSpan)
        with mock.patch.object(
            spans, "_from_namespace", side_effect=AssertionError("capture")
        ):
            with self.assertRaisesRegex(ValueError, "ended|foreign"):
                spans._original_span(owner)
