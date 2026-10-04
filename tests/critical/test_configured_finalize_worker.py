"""Receiver transport metadata must not change private FINALIZE identity."""

import sys
import unittest

from literate_ai.adapters.action_capabilities import CAPABILITY_PROTOCOL
from literate_ai.adapters.action_dispatch_wire import ACTION_WIRE_PROTOCOL
from literate_ai.adapters.action_finalize_worker import ConfiguredFinalizeWorker
from literate_ai.adapters.lifecycle import LocalComponentToolBinding
from literate_ai.contracts import canonical_identity


class ConfiguredFinalizeWorkerTests(unittest.TestCase):
    def worker(self, environment):
        profile = canonical_identity("private-finalize-test-runtime")
        return ConfiguredFinalizeWorker(
            LocalComponentToolBinding(sys.executable),
            environment=environment,
            runtime_identity=profile,
            observe_runtime=lambda: profile,
            require_execution_authority=lambda value: None,
            verify_package=lambda *args: None,
            verify_stages=lambda *args: None,
        )

    def test_discovery_and_execution_have_same_private_profile(self):
        plain = self.worker({"RUNTIME_MODE": "production"})
        for key in ("LITAI_DISPATCH_PROTOCOL", "litai_dispatch_protocol"):
            for protocol in (CAPABILITY_PROTOCOL, ACTION_WIRE_PROTOCOL):
                with self.subTest(key=key, protocol=protocol):
                    worker = self.worker({"RUNTIME_MODE": "production", key: protocol})
                    self.assertEqual(worker.identity, plain.identity)
                    self.assertEqual(dict(worker.environment), dict(plain.environment))

    def test_runtime_environment_remains_bound_and_owned(self):
        environment = {"RUNTIME_MODE": "production"}
        worker = self.worker(environment)
        identity = worker.identity
        environment["RUNTIME_MODE"] = "development"
        self.assertEqual(worker.identity, identity)
        self.assertNotEqual(self.worker(environment).identity, identity)
        with self.assertRaises(TypeError):
            worker.environment["RUNTIME_MODE"] = "development"

    def test_nontext_environment_is_refused_before_filtering(self):
        for environment in ({1: "value"}, {"LITAI_DISPATCH_PROTOCOL": None}):
            with self.subTest(environment=environment), self.assertRaises(TypeError):
                self.worker(environment)
