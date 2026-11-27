"""Genuine original runtime capture: sealed owner and cheap metadata polling.

One existing tiny owned C lifecycle supplies the real live workspace. Only the
canonical capture/writer boundaries are observed; no owner is decoded or issued
by a test, and no cached success substitutes for before/after live currentness.
"""

import copy
import multiprocessing
import os
import pickle
import shutil
import stat
import time
import unittest
from unittest.mock import patch

from literate_ai.adapters import retained_promotion_evidence as capture
from literate_ai.adapters import retained_receipt_promotion_evidence as issuer
from literate_ai.adapters import retained_unit_run_evidence as run_writer
from literate_ai.contracts import ContentIdentity, canonical_json_bytes
from tests.critical import test_retained_receipt_promotion as fixture


@unittest.skipUnless(
    os.name == "posix" and hasattr(os, "fork") and shutil.which("cc"),
    "requires existing owned POSIX C lifecycle and genuine fork refusal",
)
class RetainedPromotionCaptureScopeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixture.RetainedReceiptPromotionTests.setUpClass()
        cls.addClassCleanup(fixture.RetainedReceiptPromotionTests.doClassCleanups)

    def test_original_runtime_scope_polling_and_full_closing_refusals(self):
        original_capture = capture.retain_retained_promotion_evidence
        original_writer = capture.retain_retained_unit_run_evidence
        observed = {}

        def inspect_live(admission, workspace, **kwargs):
            scope = kwargs["_scope"]
            observed["scope"] = scope
            self.assertEqual(issuer._original(scope), (admission, workspace))
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.assertRaisesRegex(TypeError, "cannot-be"):
                    operation(scope)
            with self.assertRaisesRegex(TypeError, "original-live-capture"):
                issuer._LiveCapture(object())
            with self.assertRaisesRegex(ValueError, "original-live-capture"):
                original_capture(admission, workspace)
            for name in ("_native_sdks", "_promotion_contexts"):
                before = getattr(workspace, name)
                try:
                    setattr(workspace, name, object())
                    with self.assertRaisesRegex(ValueError, "retargeted"):
                        issuer._original(scope)
                finally:
                    setattr(workspace, name, before)

            # The actual fork sees inherited Python bytes, not issuer authority.
            context = multiprocessing.get_context("fork")
            receiver, sender = context.Pipe(duplex=False)

            def child():
                receiver.close()
                try:
                    issuer._original(scope)
                except ValueError:
                    sender.send(True)
                else:
                    sender.send(False)
                finally:
                    sender.close()

            process = context.Process(target=child)
            process.start()
            sender.close()
            try:
                self.assertTrue(receiver.poll(2), "owned fork did not report")
                self.assertIs(receiver.recv(), True)
                process.join(2)
                self.assertEqual(process.exitcode, 0)
            finally:
                if process.is_alive():
                    process.terminate()
                    process.join(2)
                receiver.close()
                self.assertFalse(process.is_alive())

            member = next(
                row for row in workspace.manifest.members if row.symlink_target is None
            )
            captured = workspace.inputs / member.path
            before = captured.read_bytes()
            original_node = captured.lstat()
            before_mode = stat.S_IMODE(original_node.st_mode)
            original_identity = (original_node.st_dev, original_node.st_ino)
            self.assertTrue(stat.S_ISREG(original_node.st_mode))
            self.assertEqual(original_node.st_uid, os.getuid())
            self.assertEqual(original_node.st_nlink, 1)

            def mutate_captured(content):
                # Only this fixture's owned file: captured inputs are genuinely
                # read-only. Restore the mode BEFORE the guard so it must reject
                # byte drift, rather than merely noticing our temporary chmod.
                readonly = os.open(
                    captured, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                )
                try:
                    node = os.fstat(readonly)
                    self.assertEqual((node.st_dev, node.st_ino), original_identity)
                    self.assertTrue(stat.S_ISREG(node.st_mode))
                    self.assertEqual((node.st_uid, node.st_nlink), (os.getuid(), 1))
                    os.fchmod(readonly, before_mode | stat.S_IWUSR)
                    descriptor = os.open(
                        captured, os.O_WRONLY | os.O_NOFOLLOW | os.O_NONBLOCK
                    )
                    try:
                        opened = os.fstat(descriptor)
                        self.assertEqual(
                            (opened.st_dev, opened.st_ino), original_identity
                        )
                        os.ftruncate(descriptor, 0)
                        remaining = memoryview(content)
                        while remaining:
                            count = os.write(descriptor, remaining)
                            self.assertGreater(count, 0)
                            remaining = remaining[count:]
                    finally:
                        os.close(descriptor)
                finally:
                    os.fchmod(readonly, before_mode)
                    os.close(readonly)
                self.assertEqual(stat.S_IMODE(captured.lstat().st_mode), before_mode)

            def restore_captured():
                mutate_captured(before)

            try:
                mutate_captured(before + b"owned captured-input mutation")
                with (
                    patch.object(
                        admission.store,
                        "put_bytes",
                        side_effect=AssertionError("no metadata before private guard"),
                    ),
                    self.assertRaises(ValueError),
                ):
                    original_capture(admission, workspace, **kwargs)
            finally:
                restore_captured()

            # Only the SDK closure traversal boundary is modeled here; all
            # admission, CAS and per-document read/write guards are real. This
            # protocol control does not claim an SDK execution/admission.
            sdk_content = canonical_json_bytes({"padding": "x" * 2048})
            sdk_reference = admission.store.put_bytes(
                sdk_content, media_type="application/json"
            )
            get_bytes = admission.store.get_bytes
            target_reads = []

            def read_bytes(reference):
                if reference.identity == sdk_reference.identity:
                    target_reads.append(reference)
                return get_bytes(reference)

            def modeled_sdk_document(_identities, *, read_document, **_options):
                read_document(
                    ContentIdentity.parse_uri(sdk_reference.identity),
                    reference=sdk_reference,
                )
                return {}

            with (
                patch.object(
                    run_writer, "retained_sdk_metadata_closure", modeled_sdk_document
                ),
                patch.object(admission.store, "get_bytes", read_bytes),
            ):
                with self.assertRaisesRegex(ValueError, "document-policy-exceeded"):
                    original_writer(
                        admission,
                        maximum_bytes=capture.MAX_METADATA,
                        maximum_memory_bytes=2 * 1024**3,
                        maximum_document_bytes=len(sdk_content) - 1,
                    )
                self.assertEqual(target_reads, [], "oversized SDK document was read")
                default_reference = original_writer(
                    admission,
                    maximum_bytes=capture.MAX_METADATA,
                    maximum_memory_bytes=2 * 1024**3,
                )
                self.assertEqual(len(target_reads), 1)
                default_document = admission.store.get_manifest(default_reference)
                self.assertEqual(
                    default_document["sdk_metadata_records"],
                    [sdk_reference.to_dict()],
                )

            # A closure record that fits the OLD unreserved remainder but exceeds
            # the actual final-envelope remainder must refuse BEFORE its read.
            # This catches charging only the small returned root BlobRef.size.
            planning_size = []
            original_planning = capture.retain_retained_unit_planning_evidence
            standing = (
                sum(row.size for _, row in admission.receipt.roots)
                + len(canonical_json_bytes(workspace._promotion_contexts))
                + len(admission.run.resolved_bom.tool_observation)
                + len(admission.run.resolved_bom.export_observation)
            )
            sufficient_budget = standing + 256 * 1024
            self.assertLessEqual(sufficient_budget, capture.MAX_METADATA)
            bounded = capture.HistoricalReadPolicy(
                max_provider_metadata_bytes=sufficient_budget
            )
            boundary_reached = []

            def observe_planning(*args, **options):
                reference = original_planning(*args, **options)
                planning_size.append(reference.size)
                return reference

            def near_limit_writer(*args, **options):
                context_bytes = len(canonical_json_bytes(workspace._promotion_contexts))
                root_bytes = sum(row.size for _, row in admission.receipt.roots)
                old_available = (
                    bounded.max_provider_metadata_bytes
                    - root_bytes
                    - context_bytes
                    - planning_size[-1]
                )
                target_size = old_available - 16384
                self.assertGreater(target_size, options["maximum_bytes"])
                content = canonical_json_bytes({"padding": "y" * (target_size - 14)})
                self.assertEqual(len(content), target_size)
                reference = admission.store.put_bytes(
                    content, media_type="application/json"
                )

                def closure(_identities, *, read_document, **_settings):
                    boundary_reached.append(reference.identity)
                    read_document(
                        ContentIdentity.parse_uri(reference.identity),
                        reference=reference,
                    )
                    return {}

                def refused_read(selected):
                    if selected.identity == reference.identity:
                        raise AssertionError("unreserved SDK closure document was read")
                    return get_bytes(selected)

                with (
                    patch.object(run_writer, "retained_sdk_metadata_closure", closure),
                    patch.object(admission.store, "get_bytes", refused_read),
                ):
                    return original_writer(*args, **options)

            with (
                patch.object(
                    capture, "retain_retained_unit_planning_evidence", observe_planning
                ),
                patch.object(
                    capture, "retain_retained_unit_run_evidence", near_limit_writer
                ),
                self.assertRaisesRegex(ValueError, "metadata-policy-exceeded"),
            ):
                original_capture(admission, workspace, **(kwargs | {"policy": bounded}))
            self.assertEqual(len(boundary_reached), 1)

            def inspect_writer(*args, **writer_kwargs):
                poll = writer_kwargs["metadata_poll_guard"]
                self.assertIsNot(poll, writer_kwargs["admission_guard"])
                with patch.object(
                    workspace,
                    "_require_current_plan",
                    side_effect=AssertionError("poll replanned live authority"),
                ):
                    for _ in range(128):
                        poll()
                # The same genuine callback also refuses its original deadline.
                future = time.monotonic() + 301
                with (
                    patch.object(capture.time, "monotonic", return_value=future),
                    self.assertRaisesRegex(ValueError, "capture-deadline"),
                ):
                    poll()
                reference = original_writer(*args, **writer_kwargs)
                if observed.get("mutate_at_close"):
                    mutate_captured(before + b"owned closing mutation")
                observed["polls"] = observed.get("polls", 0) + 128
                return reference

            with patch.object(
                capture, "retain_retained_unit_run_evidence", inspect_writer
            ):
                observed["mutate_at_close"] = True
                try:
                    # Metadata already written remains immutable; the complete
                    # closing guard must refuse a returned promotion assertion.
                    with self.assertRaises(ValueError):
                        original_capture(admission, workspace, **kwargs)
                finally:
                    restore_captured()
                    observed["mutate_at_close"] = False
                reference = original_capture(admission, workspace, **kwargs)
            observed["reference"] = reference
            return reference

        case = fixture.RetainedReceiptPromotionTests()
        self.addCleanup(case.doCleanups)
        with patch.object(capture, "retain_retained_promotion_evidence", inspect_live):
            case.setUp()
        self.assertEqual(observed["polls"], 256)
        self.assertEqual(
            case.admission.promotion_evidence_reference, observed["reference"]
        )
        with self.assertRaisesRegex(ValueError, "original-live-capture"):
            issuer._original(observed["scope"])
        # The ordinary historical verifier still consumes all actual context
        # facts and never reconstructs the sealed live issuer after it closes.
        verified = case.verify()
        candidate = case.promote(verified)
        self.assertEqual(candidate.receipt.summary.passed, 1)
