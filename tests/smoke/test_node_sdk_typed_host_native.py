"""Original typed host, provider/root issuance and actual authored SDK lifecycle."""

import os
import shutil
import sys
import tempfile
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path

from tests.smoke import test_canonical_sdk_runtime as runtime_fixture


@unittest.skipUnless(
    sys.platform == "darwin"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "requires actual selected macOS authored SDK runtime fixture",
)
class TypedVerifierHostNativeTests(unittest.TestCase):
    def test_original_binding_dependency_guard_observes_consumed_acknowledgement(self):
        from literate_ai.adapters import node_sdk_verifier_authority as membership
        from literate_ai.adapters.node_sdk_host import LocalNodeSDKHostConfiguration
        from literate_ai.adapters.node_sdk_verifier_authorization import (
            acknowledge_node_sdk_verifier_execution,
        )
        from literate_ai.adapters.standard_project import (
            LocalSourceTreeRegistry,
            assemble_standard_lifecycle_ports,
            project_locked_standard_toolchain_closure,
        )
        from tests.smoke import test_canonical_sdk_admission as admission_fixture
        from tests.smoke.test_node_sdk_cross_language import with_provider

        fixture = admission_fixture.CanonicalSDKAdmissionTests()
        self.addCleanup(fixture.doCleanups)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw).resolve()
            _, snapshot, execution = with_provider(root / "authority")
            environment = dict(os.environ)
            environment["LITAI_TYPESCRIPT_SDK"] = environment["LITERATE_TYPESCRIPT_SDK"]
            closure = project_locked_standard_toolchain_closure(
                snapshot, execution, host_platform="macos", environment=environment
            )
            consumer = next(
                c
                for c in closure.contracts
                if c.component_revision == execution.root_revision
            )
            root_oracle = fixture._root_oracle(snapshot, consumer)
            providers = {
                node.revision.identity.uri: fixture._provider_oracle(
                    node.revision,
                    next(
                        c
                        for c in closure.contracts
                        if c.component_revision == node.revision.identity
                    ),
                )
                for node in snapshot.authority.lock.nodes
                if node.revision.identity != execution.root_revision
            }
            ports = assemble_standard_lifecycle_ports(
                object_root=root / "objects",
                toolchain_closure=closure,
                source_trees=LocalSourceTreeRegistry(),
                independent_acceptance_oracle=root_oracle,
            ).ports
            acknowledgement = acknowledge_node_sdk_verifier_execution(
                snapshot=snapshot,
                execution=execution,
                actor="isolated binding fixture",
                reason="original dependency guard ordering",
                authorization_lifetime=timedelta(minutes=10),
                authorization_deadline=datetime.now(UTC) + timedelta(minutes=20),
                acknowledge_identity_only_inputs=True,
            )
            self.addCleanup(membership._retire_acknowledgement, acknowledgement)
            observed = []
            original_guard = closure.dependency_guard

            def require_consumed():
                bound = membership._values(membership._state(acknowledgement))[3]
                self.assertIsNotNone(bound)
                self.assertIs(bound[0](), configuration)
                self.assertIs(bound[1](), ports._node_sdk_host_binding)

            def dependency_guard():
                require_consumed()
                observed.append("original closure dependency guard")
                if original_guard is not None:
                    original_guard()

            closure = replace(closure, dependency_guard=dependency_guard)
            configuration = LocalNodeSDKHostConfiguration(
                snapshot=snapshot,
                expected_execution=execution,
                provider_oracles=providers,
                root_oracle=root_oracle,
                verifier_acknowledgement=acknowledgement,
                require_current=require_consumed,
                environment=environment,
            )
            configuration.bind(ports, closure)
            self.assertEqual(observed, ["original closure dependency guard"])
            configuration._require_bytes()

    def test_original_two_provider_root_subpath_typed_runtime(self):
        fixture = runtime_fixture.CanonicalSDKRuntimeTests()
        self.addCleanup(fixture.doCleanups)
        fixture._exercise_authored_runtime(
            second_provider=True,
            public_subpath=True,
            provider_runtime="source/counter/runtime/add.cjs",
            typed_verifier=True,
        )
