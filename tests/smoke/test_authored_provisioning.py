"""Native consumer files/tools, actual provisioning; injected provider semantics.

No generated consumer gates or genuine provider/model/archive qualification,
positive admission, installed wheel or separate-process CLI is claimed here.
"""

import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_provisioning as subject
from literate_ai.adapters.lifecycle_lock import (
    _owner_path,
    project_lifecycle_lock,
    project_lifecycle_lock_path,
)
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)
from literate_ai.projects import PinnedInputClosure
from tests.support.fixtures_authored_provisioning import authored_provisioning_fixture
from tests.support.fixtures_test_component_authoring_lock_contracts import (
    official_validator,
)

LITAI_TEST_PRIORITY = 10
LITAI_TEST_SERIAL = True


@unittest.skipUnless(
    os.name != "nt" and all(shutil.which(x) for x in ("cargo", "rustc", "make", "git")),
    "requires native POSIX Cargo/Rust and actual retained Make/Git adoption",
)
class AuthoredProvisioningTests(unittest.TestCase):
    def call(self, root, arguments, operation):
        return subject.provision_authored_retained_cargo_consumer(
            root,
            operation=operation,
            **arguments,
            old_output_budget=RetainedCargoOutputBudget(512 * 1024**2, 4 * 1024**3),
        )

    def test_same_consumer_check_materialize_check_and_verified_noop(self):
        with authored_provisioning_fixture(self) as (
            root,
            arguments,
            native,
            state,
            lifecycle,
        ):
            expected = len(
                json.loads((root / arguments["binding_path"]).read_bytes())[
                    "destinations"
                ]
            )
            output = Path(native.environment["CARGO_TARGET_DIR"])
            self.assertFalse(output.exists())
            rows = []
            for operation in ("check", "materialize", "check", "materialize"):
                if operation == "check":
                    with project_lifecycle_lock(root, operation="peer-readonly-check"):
                        owner = _owner_path(project_lifecycle_lock_path(root))
                        original_owner = owner.read_bytes()
                        row = self.call(root, arguments, operation)
                        self.assertEqual(owner.read_bytes(), original_owner)
                else:
                    row = self.call(root, arguments, operation)
                official_validator(row["schema"]).validate(row)
                self.assertFalse(row["consumer_gates_executed"])
                self.assertFalse(row["importer_admission"])
                self.assertFalse(row["source_retirement"])
                self.assertFalse(state["active"])
                rows.append(row)
            self.assertEqual(rows[0]["missing_packages"], expected)
            self.assertEqual(rows[0]["verified_present_packages"], 0)
            self.assertEqual(rows[1]["published_packages"], expected)
            self.assertEqual(rows[2]["verified_present_packages"], expected)
            self.assertEqual(rows[3]["published_packages"], 0)
            self.assertEqual(lifecycle["closed"], 4)
            # Verified no-op materialization allocates no execution child.
            self.assertFalse(any(output.iterdir()))

    def test_final_provider_closer_creating_a_prospective_selector_is_refused(self):
        captured, changed, armed = [], [], [False]
        actual = subject._capture_authored_provisioning_source

        def capture(*args, **kwargs):
            result = actual(*args, **kwargs)
            captured.append(result)
            return result

        def late(_state):
            if armed[0]:
                child = captured[-1].before.prospective_children[0]
                child.mkdir()
                (child / "keep").write_bytes(b"preserve excluded prospective child")
                changed.append(child)

        with authored_provisioning_fixture(self, close_hook=late) as (
            root,
            arguments,
            _native,
            _state,
            lifecycle,
        ):
            with patch.object(
                subject, "_capture_authored_provisioning_source", side_effect=capture
            ):
                self.call(root, arguments, "materialize")
                armed[0] = True
                with self.assertRaisesRegex(ValueError, "scratch-existing-root"):
                    self.call(root, arguments, "check")
            self.assertEqual(lifecycle["closed"], 2)
            self.assertEqual(len(changed), 1)
            self.assertEqual(
                (changed[0] / "keep").read_bytes(),
                b"preserve excluded prospective child",
            )

    def test_initial_check_has_no_exclusions_for_closer_added_root(self):
        changed = []

        def late(state):
            root = Path(state["native"].environment["CARGO_TARGET_DIR"])
            root.mkdir()
            (root / "keep").write_bytes(b"preserve foreign root from provider closer")
            changed.append(root)

        with authored_provisioning_fixture(self, close_hook=late) as (
            root,
            arguments,
            _native,
            _state,
            lifecycle,
        ):
            with self.assertRaises(ValueError):
                self.call(root, arguments, "check")
            self.assertEqual(lifecycle["closed"], 1)
            self.assertEqual(len(changed), 1)
            self.assertEqual(
                (changed[0] / "keep").read_bytes(),
                b"preserve foreign root from provider closer",
            )

    def test_initial_materialize_provider_closer_cannot_fill_empty_output(self):
        changed = []

        def late(state):
            path = (
                Path(state["native"].environment["CARGO_TARGET_DIR"])
                / "unexpected-output"
            )
            path.write_bytes(b"preserve materialization closer output")
            changed.append(path)

        with authored_provisioning_fixture(self, close_hook=late) as (
            root,
            arguments,
            _native,
            _state,
            lifecycle,
        ):
            with self.assertRaises(ValueError):
                self.call(root, arguments, "materialize")
            self.assertEqual(lifecycle["closed"], 1)
            self.assertEqual(
                changed[0].read_bytes(), b"preserve materialization closer output"
            )

    def test_partial_roots_preserve_foreign_payload_and_refuse(self):
        with authored_provisioning_fixture(self) as (
            root,
            arguments,
            native,
            _state,
            _lifecycle,
        ):
            output = Path(native.environment["CARGO_TARGET_DIR"])
            output.mkdir()
            foreign = output / "keep"
            foreign.write_bytes(b"preserve partial root")
            with self.assertRaisesRegex(ValueError, "partial-root-state-refused"):
                self.call(root, arguments, "materialize")
            self.assertEqual(foreign.read_bytes(), b"preserve partial root")

    def test_provider_closer_exception_is_not_a_successful_check(self):
        def failed(state):
            raise RuntimeError("explicit provisioning provider closer failed")

        with authored_provisioning_fixture(self, close_hook=failed) as (
            root,
            arguments,
            _native,
            state,
            lifecycle,
        ):
            with self.assertRaisesRegex(
                RuntimeError, "explicit provisioning provider closer failed"
            ):
                self.call(root, arguments, "check")
            self.assertEqual(lifecycle["closed"], 1)
            self.assertFalse(state["active"])

    def test_provider_closer_cannot_change_original_output_allowance(self):
        budget = RetainedCargoOutputBudget(16 * 1024**2, 64 * 1024**2)

        def late(_state):
            object.__setattr__(budget, "maximum_total_bytes", 128 * 1024**2)

        with authored_provisioning_fixture(self, close_hook=late) as (
            root,
            arguments,
            _native,
            _state,
            lifecycle,
        ):
            with self.assertRaisesRegex(ValueError, "original-budget-changed"):
                subject.provision_authored_retained_cargo_consumer(
                    root, operation="check", **arguments, old_output_budget=budget
                )
            self.assertEqual(lifecycle["closed"], 1)
            self.assertEqual(budget.maximum_total_bytes, 128 * 1024**2)

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

            with authored_provisioning_fixture(self, close_hook=retarget) as (
                root,
                arguments,
                _native,
                state,
                lifecycle,
            ):
                with self.assertRaises(ValueError):
                    self.call(root, dict(arguments, archive_inputs=pins), "check")
                self.assertEqual(lifecycle["closed"], 1)
                self.assertFalse(state["active"])
            self.assertEqual(
                original.read_bytes(), b"preserve changed original transport"
            )
