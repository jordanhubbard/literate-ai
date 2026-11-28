"""Reopen the stored consumer binding from a real fixture SDK build."""

import json
import subprocess
import sys
import unittest
from unittest.mock import patch

from literate_ai.adapters.native_sdk_completion_binding import read_completion_binding
from literate_ai.adapters.native_sdk_completion_cache import cache_record_ref
from literate_ai.adapters.native_sdk_completion_resolution import resolution_document
from literate_ai.adapters.native_sdk_consumer import NativeSdkConsumerInputs
from literate_ai.contracts.retained_project import RetainedProjectLimits
from tests.support import fixtures_test_native_sdk_source_build as fixtures


class CompletionBindingTests(unittest.TestCase):
    def test_completed_build_reopens_from_cas_after_original_source_removed(self):
        fixture = fixtures.NativeSdkSourceBuildTests(
            "test_real_policy_build_cache_and_relocated_native_execution"
        )
        self.addCleanup(fixture.doCleanups)
        fixture.setUp()
        service = fixture.service()
        build = service.build()
        inputs = NativeSdkConsumerInputs(snapshot=fixture.snapshot, services=(service,))
        selection = build.selection
        (expected,) = inputs.for_consumer(
            selection.component_revision, target_identity=selection.target_identity
        )
        row = {
            "selection": selection.identity.to_dict(),
            "binding": expected.to_dict(),
            "resolution": resolution_document(build.resolution),
            "cache_record": cache_record_ref(service.store, build.resolution).to_dict(),
        }
        toolchains = tuple(
            tool.toolchain_identity for tool in service.planner.tools.values()
        )
        fixture.fixture.remove_source()
        with (
            patch.object(
                service.store,
                "put_manifest",
                side_effect=AssertionError("unexpected write"),
            ),
            patch.object(
                service.store,
                "put_bytes",
                side_effect=AssertionError("unexpected write"),
            ),
        ):
            actual, _ = read_completion_binding(
                service.store,
                row,
                selection=selection,
                toolchains=toolchains,
                intelligence=service.source_intelligence_policy,
                limits=RetainedProjectLimits(10000, 128 * 1024**2, 256 * 1024**2),
                max_manifest_bytes=16 * 1024**2,
                step=lambda: None,
            )
        self.assertEqual(actual, expected)

        case = {
            "component": str(fixture.recipe_fixture.component),
            "flavors": str(fixture.recipe_fixture.flavors),
            "selectors": ["+python", "+" + selection.recipe.layout.operating_system],
            "cas": str(service.store.root),
            "tools": {
                name: tool.executable for name, tool in service.planner.tools.items()
            },
            "row": row,
            "intelligence": service.source_intelligence_policy.to_dict(),
        }
        reopened = subprocess.run(
            [sys.executable, "-B", "-m", "tests.support.reopen_sdk_completion_probe"],
            input=json.dumps(case),
            text=True,
            capture_output=True,
            timeout=180,
        )
        self.assertEqual(reopened.returncode, 0, reopened.stderr)
        self.assertEqual(reopened.stdout.strip(), expected.identity.uri)
