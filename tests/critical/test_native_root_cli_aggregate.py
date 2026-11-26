"""Original CLI owner custody with controlled accepted-component observations.

The CLI/admission/filesystem publication paths are real. Symbolic typed receipt
fixtures do not establish native generation, acceptance or release qualification.
"""

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai import test_receipts as tracked_receipts
from literate_ai.adapters import native_root_run_admission as admission_module
from literate_ai.adapters.native_root_run_admission import admit_native_root_command
from literate_ai.application import native_root_run
from literate_ai.application.native_root_run import NativeRootRunError
from literate_ai.cli import rebuild as cli
from literate_ai.projects import load_project, serialize_project_configuration
from tests.critical import test_native_root_run_admission as admission
from tests.e2e import test_standard_root_receipts as receipts
from tests.support import fixtures_test_cli_rebuild as cli_fixture


class NativeRootCliAggregateTests(unittest.TestCase):
    setUp = admission.NativeRootRunAdmissionTests.setUp

    def test_serialization_closure_prevents_candidate_file_creation(self):
        target = self.root / "candidate-after-closure.json"
        finalized = receipts.candidate(receipts.LABELS[0])
        original = cli.canonical_json_bytes
        with self.assertRaises(NativeRootRunError):
            with admit_native_root_command(self.project, self.binding) as owner:

                def serialize(value):
                    content = original(value)
                    owner.close()
                    return content

                with mock.patch.object(
                    cli, "canonical_json_bytes", side_effect=serialize
                ):
                    cli._write_standard_candidate(target, finalized)
        self.assertFalse(
            target.exists(), "candidate CREATE happened after original owner closure"
        )

    def test_candidate_fsync_closure_leaves_no_owner_route_candidate(self):
        target = self.root / "candidate-after-fsync.json"
        finalized = receipts.candidate(receipts.LABELS[0])
        original = cli.os.fsync
        with self.assertRaises(NativeRootRunError):
            with admit_native_root_command(self.project, self.binding) as owner:

                def fsync(descriptor):
                    original(descriptor)
                    owner.close()

                with mock.patch.object(cli.os, "fsync", side_effect=fsync):
                    cli._write_standard_candidate(target, finalized)
        self.assertFalse(
            target.exists(), "failed owner route retained candidate after fsync closure"
        )

    def receipt_commit_closure(self, phase):
        self.definition = replace(
            self.definition,
            project_id="fixture",
            test_receipt_policy=receipts.RECEIPT_POLICY,
            test_receipt="tracked-receipt.json",
        )
        self.path.write_bytes(serialize_project_configuration(self.definition))
        self.project = load_project(self.root)
        target = self.root / self.definition.test_receipt
        original_content = tracked_receipts._canonical_finalized_candidate_bytes(
            receipts.candidate("old-valid-observation")
        )
        target.write_bytes(original_content)
        finalized = receipts.combine(
            receipts.candidate(label) for label in receipts.LABELS
        )
        serialize = tracked_receipts._canonical_finalized_candidate_bytes
        fsync = tracked_receipts.os.fsync
        observations = []
        with self.assertRaises(NativeRootRunError):
            with admit_native_root_command(self.project, self.binding) as owner:

                def close_after_serialization(value):
                    content = serialize(value)
                    if phase == "serialization":
                        observations.append(phase)
                        owner.close()
                    return content

                def close_after_fsync(descriptor):
                    fsync(descriptor)
                    if phase == "fsync":
                        observations.append(phase)
                        owner.close()

                with (
                    mock.patch.object(
                        tracked_receipts,
                        "_canonical_finalized_candidate_bytes",
                        side_effect=close_after_serialization,
                    ),
                    mock.patch.object(
                        tracked_receipts.os, "fsync", side_effect=close_after_fsync
                    ),
                ):
                    tracked_receipts.update_project_test_receipt_finalized_value(
                        self.project,
                        finalized,
                        project_revision_identity=receipts.BASE,
                    )
        self.assertEqual(observations, [phase])
        self.assertEqual(
            target.read_bytes(),
            original_content,
            "receipt target replaced after original owner closure",
        )
        self.assertEqual(list(self.root.glob(".tracked-receipt.json.*.tmp")), [])

    def test_receipt_fsync_closure_preserves_original_before_replace(self):
        self.receipt_commit_closure("fsync")

    def test_receipt_serialization_closure_preserves_original_before_replace(self):
        self.receipt_commit_closure("serialization")

    def exercise_aggregate(self, *, selected=True, stop=None):
        self.definition = replace(
            self.definition,
            project_id="fixture",
            test_receipt_policy=receipts.RECEIPT_POLICY,
            test_receipt="aggregate-receipt.json",
            native_root_run_policy=self.definition.native_root_run_policy
            if selected
            else None,
        )
        self.path.write_bytes(serialize_project_configuration(self.definition))
        self.project = load_project(self.root)
        for label in receipts.LABELS:
            component = self.root / label
            component.mkdir(parents=True)
            (component / "component.md").write_text("# Fixed fixture\n")
            (component / "component.lock.json").write_text("{}\n")
        external = tempfile.TemporaryDirectory()
        self.addCleanup(external.cleanup)
        target = Path(external.name).resolve() / "candidate.json"
        tracked = self.root / self.definition.test_receipt
        clock = [1_000_000_000_000]
        owners = []
        labels = []
        original_open = native_root_run.open_native_root_run
        original_combine = cli.combine_standard_project_test_receipts

        def open_original(policy, **arguments):
            return original_open(
                policy,
                **arguments,
                utc_clock=lambda: clock[0],
                monotonic_clock=lambda: clock[0],
            )

        def component(project, binding, args, root, label, **arguments):
            labels.append(label)
            self.assertFalse(arguments["update_receipt"])
            self.assertFalse(arguments["write_candidate"])
            if selected:
                owner = arguments["live_run"]
                self.assertIs(native_root_run.current_native_root_run(), owner)
                owner.require_current()
                owners.append(owner)
                self.assertTrue(all(existing is owner for existing in owners))
            else:
                self.assertNotIn("live_run", arguments)
                self.assertIsNone(native_root_run.current_native_root_run())
            member = receipts.candidate(label)
            arguments["observer"](
                SimpleNamespace(finalized_receipt=member),
                None,
                SimpleNamespace(locked_authority_snapshot=mock.Mock()),
                None,
            )
            result = cli_fixture.RebuildCliTests()._component_rebuild_result(
                label, update_receipt=False
            )
            result["component_lock_identity"] = member.component_lock_identities[0].uri
            result["component_lock_identities"] = [
                member.component_lock_identities[0].uri
            ]
            if stop == "close-first" or (stop == "close-last" and len(labels) == 2):
                owners[0].close()
            if stop == "expire-last" and len(labels) == 2:
                clock[0] += 120_000_000_001
            return result

        def combine(*arguments, **keywords):
            result = original_combine(*arguments, **keywords)
            if stop == "close-combine":
                owners[0].close()
            elif stop == "expire-combine":
                clock[0] += 120_000_000_001
            return result

        with (
            mock.patch.object(
                admission_module, "open_native_root_run", side_effect=open_original
            ) as admission_call,
            mock.patch.object(
                cli, "_resolve_standard_binding", return_value=self.binding
            ),
            mock.patch.object(
                cli, "_standard_rebuild_one_component", side_effect=component
            ),
            mock.patch.object(
                cli, "validated_project_authority_identity", return_value=receipts.BASE
            ),
            mock.patch.object(
                cli,
                "current_project_component_lock_identities",
                return_value=receipts.LOCKS,
            ),
            mock.patch.object(
                cli, "combine_standard_project_test_receipts", side_effect=combine
            ),
            mock.patch.object(
                cli,
                "update_project_test_receipt_finalized_value",
                wraps=cli.update_project_test_receipt_finalized_value,
            ) as update,
        ):
            status, envelope = cli_fixture.invoke(
                "rebuild",
                ".",
                "--project",
                str(self.root),
                "--allow-host-execution",
                "--update-receipt",
                "--candidate-receipt",
                str(target),
            )
        if stop:
            self.assertNotEqual(status, 0, envelope)
            self.assertEqual(
                envelope["error"]["code"],
                "native_root_run.closed"
                if stop.startswith("close")
                else "native_root_run.expired",
            )
            update.assert_not_called()
            self.assertFalse(target.exists())
            self.assertFalse(tracked.exists())
        else:
            self.assertEqual(status, 0, envelope)
            self.assertEqual(labels, list(receipts.LABELS))
            self.assertTrue(target.exists())
            self.assertEqual(target.read_bytes(), tracked.read_bytes())
            update.assert_called_once()
        self.assertEqual(admission_call.call_count, int(selected))
        for owner in owners:
            with self.assertRaises(NativeRootRunError):
                owner.remaining()
        return labels

    def test_one_original_owner_spans_all_aggregate_components(self):
        self.exercise_aggregate()

    def test_legacy_aggregate_omits_live_keywords(self):
        self.exercise_aggregate(selected=False)

    def test_first_component_closure_prevents_remaining_components_and_publication(
        self,
    ):
        self.assertEqual(
            self.exercise_aggregate(stop="close-first"), [receipts.LABELS[0]]
        )

    def test_final_component_closure_prevents_receipt_and_candidate(self):
        self.exercise_aggregate(stop="close-last")

    def test_final_component_expiry_prevents_receipt_and_candidate(self):
        self.exercise_aggregate(stop="expire-last")

    def test_aggregate_finalization_closure_prevents_receipt_and_candidate(self):
        self.exercise_aggregate(stop="close-combine")

    def test_aggregate_finalization_expiry_prevents_receipt_and_candidate(self):
        self.exercise_aggregate(stop="expire-combine")
