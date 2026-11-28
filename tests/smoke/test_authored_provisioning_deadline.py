"""Expired provisioning cannot keep allocating or publishing package roots.

Native consumer ownership and publication are real; provider admission is the
existing explicit fixture seam, not genuine generation or installed acceptance.
"""

import json
import os
import shutil
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_provisioning as subject
from literate_ai.adapters import retained_cargo_test_execution as deadlines
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)
from tests.support.fixtures_authored_provisioning import authored_provisioning_fixture

LITAI_TEST_PRIORITY = 10
LITAI_TEST_SERIAL = True


@unittest.skipUnless(
    os.name != "nt" and all(shutil.which(x) for x in ("cargo", "rustc", "make", "git")),
    "requires native POSIX Cargo/Rust and actual retained Make/Git adoption",
)
class AuthoredProvisioningDeadlineTests(unittest.TestCase):
    def expired_at(self, phase):
        clock = [time.monotonic()]
        deadline = clock[0] + 900
        clock_view = SimpleNamespace(monotonic=lambda: clock[0])
        calls = []
        with authored_provisioning_fixture(self) as (
            root,
            arguments,
            _native,
            _state,
            _lifecycle,
        ):
            binding = json.loads((root / arguments["binding_path"]).read_bytes())
            destinations = [root / row["path"] for row in binding["destinations"]]
            operation = getattr(subject, phase)

            def expire(*args, **kwargs):
                calls.append(phase)
                if phase == "_capture_authored_provisioning_source":
                    result = operation(*args, **kwargs)
                    clock[0] = deadline + 1
                    return result
                clock[0] = deadline + 1
                return operation(*args, **kwargs)

            with (
                patch.object(subject, "time", clock_view),
                patch.object(deadlines, "time", clock_view),
                patch.object(subject, phase, side_effect=expire),
                self.assertRaisesRegex(ValueError, "native-completion-deadline"),
            ):
                subject.provision_authored_retained_cargo_consumer(
                    root,
                    operation="materialize",
                    **arguments,
                    old_output_budget=RetainedCargoOutputBudget(
                        512 * 1024**2, 4 * 1024**3
                    ),
                    timeout_seconds=900,
                )
            self.assertEqual(calls, [phase])
            self.assertTrue(
                all(not p.exists() for p in destinations),
                "expired operation published a package",
            )
            if phase == "_capture_authored_provisioning_source":
                plan = json.loads((root / arguments["plan_path"]).read_bytes())
                workspace = root / plan["workspace_root"]
                self.assertTrue(
                    all(
                        not (workspace / row["path"]).exists()
                        for row in plan["scratch_roots"]
                    )
                )

    def test_expiry_after_initial_source_observation_precedes_scratch_allocation(self):
        self.expired_at("_capture_authored_provisioning_source")

    def test_expiry_at_materialization_entry_precedes_package_publication(self):
        self.expired_at("materialize_authored_retained_cargo_packages")
