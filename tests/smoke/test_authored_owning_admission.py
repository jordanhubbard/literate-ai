"""Real native consumer/close protocol, explicitly injected provider semantics.

Not genuine model generation, provider all-run replay/retirement, installed-wheel,
transported qualification, public CLI or full release acceptance evidence.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_admission as subject
from literate_ai.contracts.authored_retained_cargo_admission import (
    AuthoredRetainedCargoAdmissionReceipt,
)
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)
from literate_ai.projects import PinnedInputClosure, PinnedInputClosureError
from tests.support.fixtures_authored_owning_admission import owning_admission_fixture

LITAI_TEST_PRIORITY = 10
LITAI_TEST_SERIAL = True


@unittest.skipUnless(
    os.name != "nt" and all(shutil.which(x) for x in ("cargo", "rustc", "make", "git")),
    "requires native POSIX Cargo/Rust and actual retained Make/Git adoption",
)
class AuthoredOwningAdmissionTests(unittest.TestCase):
    def arguments(self, operator, native, retirement):
        return dict(
            **operator,
            **retirement,
            environment=native.environment,
            # Include full native execution and post-close input verification.
            timeout_seconds=3600,
            gate_tools={"cargo": native.cargo},
            read_exclusion_permission=native.read_permission,
            old_output_budget=RetainedCargoOutputBudget(512 * 1024**2, 4 * 1024**3),
            new_output_budget=RetainedCargoOutputBudget(512 * 1024**2, 4 * 1024**3),
        )

    def test_actual_native_consumer_receipt_is_minted_only_after_all_owners_close(self):
        with owning_admission_fixture(self) as (
            root,
            operator,
            native,
            state,
            lifetime,
            retirement,
        ):

            def mint(*args, **kwargs):
                self.assertTrue(lifetime["provider_closed"])
                self.assertFalse(state["active"])
                return AuthoredRetainedCargoAdmissionReceipt(*args, **kwargs)

            with patch.object(
                subject, "AuthoredRetainedCargoAdmissionReceipt", side_effect=mint
            ) as issued:
                receipt = subject.admit_authored_retained_cargo_consumer(
                    root, **self.arguments(operator, native, retirement)
                )
            issued.assert_called_once()
            self.assertIs(type(receipt), AuthoredRetainedCargoAdmissionReceipt)
            self.assertGreater(receipt.coverage_counts["passed_cases"], 0)
            self.assertGreater(receipt.coverage_counts["custom_commands"], 0)
            self.assertEqual(
                receipt.source_retirement_identity.uri,
                retirement["reviewed_retirement"].identity,
            )
            self.assertEqual(
                AuthoredRetainedCargoAdmissionReceipt.from_dict(receipt.to_dict()),
                receipt,
            )
            self.assertTrue(lifetime["provider_closed"])
            self.assertFalse(state["active"])

    def test_provider_closer_error_emits_no_receipt_after_actual_native_execution(self):
        def fail(lifetime):
            children = list(lifetime["output_parent"].glob("receive-*"))
            self.assertEqual(len(children), 1)
            self.assertTrue(any(children[0].rglob("tests-*")))
            raise RuntimeError(
                "explicit provider closer failure after native execution"
            )

        with owning_admission_fixture(self, close_hook=fail) as (
            root,
            operator,
            native,
            state,
            lifetime,
            retirement,
        ):
            with patch.object(
                subject, "AuthoredRetainedCargoAdmissionReceipt"
            ) as issued:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "explicit provider closer failure after native execution",
                ):
                    subject.admit_authored_retained_cargo_consumer(
                        root, **self.arguments(operator, native, retirement)
                    )
                issued.assert_not_called()
            self.assertTrue(lifetime["provider_closed"])
            self.assertFalse(state["active"])

    def test_provider_closer_unselected_output_drift_is_preserved_and_no_receipt_issued(
        self,
    ):
        changed = []

        def late(lifetime):
            children = list(lifetime["output_parent"].glob("receive-*"))
            self.assertEqual(len(children), 1)
            path = children[0] / "late-provider-closer-output"
            path.write_bytes(b"preserve output added by final provider closer")
            changed.append(path)

        with owning_admission_fixture(self, close_hook=late) as (
            root,
            operator,
            native,
            state,
            lifetime,
            retirement,
        ):
            with patch.object(
                subject, "AuthoredRetainedCargoAdmissionReceipt"
            ) as issued:
                with self.assertRaisesRegex(ValueError, "original-tree-changed"):
                    subject.admit_authored_retained_cargo_consumer(
                        root, **self.arguments(operator, native, retirement)
                    )
                issued.assert_not_called()
            self.assertEqual(len(changed), 1)
            self.assertEqual(
                changed[0].read_bytes(),
                b"preserve output added by final provider closer",
            )
            self.assertTrue(lifetime["provider_closed"])
            self.assertFalse(state["active"])

    def test_final_archive_observation_keeps_original_path_after_equal_byte_retarget(
        self,
    ):
        with tempfile.TemporaryDirectory(
            prefix="litai-archive-observation-"
        ) as temporary:
            directory = Path(temporary)
            original, replacement = directory / "original", directory / "replacement"
            original.write_bytes(b"original transported archive")
            replacement.write_bytes(original.read_bytes())
            pins, other = PinnedInputClosure(), PinnedInputClosure()
            pins.pin(original, boundary=directory, label="archive")
            other.pin(replacement, boundary=directory, label="archive")
            identity = pins.identity
            self.assertEqual(other.identity, identity)

            def retarget(_state):
                original.write_bytes(b"preserve changed original transport")
                pins._entries = dict(other._entries)
                pins._labels = dict(other._labels)
                pins._total_bytes = other._total_bytes
                self.assertEqual(pins.identity, identity)
                pins.require_unchanged()

            with owning_admission_fixture(self, close_hook=retarget) as (
                root,
                operator,
                native,
                state,
                lifetime,
                retirement,
            ):
                with patch.object(
                    subject, "AuthoredRetainedCargoAdmissionReceipt"
                ) as issued:
                    with self.assertRaisesRegex(
                        PinnedInputClosureError,
                        "generation authority changed during the operation: archive",
                    ):
                        subject.admit_authored_retained_cargo_consumer(
                            root,
                            **self.arguments(operator, native, retirement),
                            archive_inputs=pins,
                        )
                    issued.assert_not_called()
                self.assertTrue(lifetime["provider_closed"])
                self.assertFalse(state["active"])
            self.assertEqual(
                original.read_bytes(), b"preserve changed original transport"
            )
