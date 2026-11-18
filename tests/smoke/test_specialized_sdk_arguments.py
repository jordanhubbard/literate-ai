"""Regress public non-SDK backend startup after shared SDK argument addition."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters.lifecycle.standard_bazel import StandardBazelLifecyclePorts
from literate_ai.adapters.lifecycle.standard_cargo import StandardCargoLifecyclePorts
from literate_ai.adapters.lifecycle.standard_local import (
    LocalSourceTreeRegistry,
    LocalStandardLifecyclePorts,
)
from literate_ai.adapters.lifecycle.standard_mix import StandardMixLifecyclePorts


class SpecializedSDKArgumentsTests(unittest.TestCase):
    def test_empty_sdk_selection_preserves_existing_backend_startup(self):
        with tempfile.TemporaryDirectory() as temporary:
            for backend, selected in (
                (StandardCargoLifecyclePorts, {"cargo_targets": ()}),
                (StandardBazelLifecyclePorts, {"bazel_targets": ()}),
                (StandardMixLifecyclePorts, {"mix_targets": ()}),
            ):
                with self.subTest(backend=backend.__name__):
                    ports = backend(
                        source_trees=LocalSourceTreeRegistry(),
                        object_root=Path(temporary) / backend.__name__,
                        contracts=(),
                        node_sdk_targets=(),
                        **selected,
                    )
                    self.assertEqual(ports.node_sdk_targets, {})

    def test_evidence_writer_survives_all_backend_fallbacks(self):
        """An opaque custody writer must reach the original shared resolver."""
        for backend in (
            StandardCargoLifecyclePorts,
            StandardBazelLifecyclePorts,
            StandardMixLifecyclePorts,
        ):
            with self.subTest(backend=backend.__name__):
                ports = object.__new__(backend)
                ports.cargo_targets = {}
                ports.mix_targets = {}
                ports.python_targets = {}
                ports.npm_targets = {}
                ports._bazel_resolution_builds = {}
                plan = SimpleNamespace(
                    identity=SimpleNamespace(uri="plan"),
                    component_revision=SimpleNamespace(uri="component"),
                )
                writer = object()
                with patch.object(
                    LocalStandardLifecyclePorts, "_resolve_and_write_sbom"
                ) as resolver:
                    result = ports._write_resolved_sbom(
                        plan, Path("owned-artifact"), write_evidence=writer
                    )
                self.assertIs(result, resolver.return_value)
                self.assertIs(resolver.call_args.kwargs["write_evidence"], writer)
