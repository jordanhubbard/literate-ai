"""Cheap real-adapter guard regression; native command results are protocol seams.

No Cargo/Rust executable is run and no native Rust qualification is claimed.
Current oracle/lock/source owners and the whole public adapter path are real.
Instrument original native-owner methods to refuse ambient/default-budget entry.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import rust_library_harness_execution as executor
from literate_ai.adapters.builders.cargo import CargoToolchain
from literate_ai.adapters.builders.rust import RustToolchain
from literate_ai.adapters.component_acceptance import ComponentAcceptanceError
from literate_ai.adapters.lifecycle.standard_local import (
    LocalComponentToolBinding,
    LocalStandardLifecycleError,
    local_tree_identity,
)
from literate_ai.contracts import ContentIdentity
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.product_json import product_json_bytes
from tests.support.fixtures_rust_library_harness import (
    GRAPH,
    NativeRustVerifierFixture,
)


@unittest.skipUnless(
    os.name == "posix", "owned POSIX adapter fixture; not Windows native proof"
)
class RustHarnessGuardBudgetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix="rust guard protocol ")
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.clock = 0.0
        self.probes = []
        self.commands = []
        self.near_deadline = False
        self.mutation = None
        tools = self.root / "tools"
        tools.mkdir()
        files = []
        for name in ("cargo", "rustc"):
            path = tools / name
            path.write_bytes(b"protocol fixture; never executed\n")
            path.chmod(0o700)
            files.append(path)
        digest = "sha256:" + hashlib.sha256(files[0].read_bytes()).hexdigest()
        cargo = CargoToolchain(
            (str(files[0]),), str(files[0]), digest, "1.90.0", (1, 90, 0)
        )
        rust = RustToolchain(
            (str(files[1]),),
            str(files[1]),
            digest,
            str(files[1]),
            digest,
            "rustc 1.90.0 (guard fixture)",
        )
        self.cargo_owner, self.rust_owner = cargo, rust
        self.cargo = LocalComponentToolBinding.from_observed_toolchain(cargo)
        self.rustc = LocalComponentToolBinding.from_observed_toolchain(rust)
        seed = self.root / "seed"
        (seed / "library/src").mkdir(parents=True)
        (seed / "library/Cargo.toml").write_text(
            '[package]\nname="qualified-fixture"\nversion="1.0.0"\n'
        )
        (seed / "library/src/lib.rs").write_text("// nonexecuted input\n")
        for name, (version, _features, _edges) in GRAPH.items():
            directory = seed / "vendor" / (name + "-" + version)
            directory.mkdir(parents=True)
            (directory / "Cargo.toml").write_text(
                "[package]\nname="
                + json.dumps(name)
                + "\nversion="
                + json.dumps(version)
                + "\n"
            )
        (seed / "cargo-home").mkdir()
        (seed / "workspace/src").mkdir(parents=True)
        (seed / "workspace/src/main.rs").write_text("fn main() {}\n")
        (seed / "workspace/Cargo.lock").write_text(
            "# exact reviewed protocol fixture, no native Cargo parsing\n"
        )
        project = self.root / "project"
        project.mkdir()
        # Fixture authoring explicitly uses modeled native observations. Only the
        # operation below is armed to reject ANY implicit native guard call.
        with (
            patch.object(CargoToolchain, "require_unchanged", lambda *a, **k: None),
            patch.object(RustToolchain, "require_unchanged", lambda *a, **k: None),
        ):
            self.cargo = replace(
                self.cargo, _authority_guard=self.cargo_owner.require_unchanged
            )
            self.rustc = replace(
                self.rustc, _authority_guard=self.rust_owner.require_unchanged
            )
            self.fixture = NativeRustVerifierFixture(
                project, seed, self.cargo, self.rustc
            )
        self.stage = self.root / "stage"
        self.stage.mkdir()
        self.library_identity = local_tree_identity(self.fixture.export)

    def library_current(self):
        # Same pure callback contract used by Standard; no native observations.
        self.cargo.require_command_unchanged()
        if local_tree_identity(self.fixture.export) != self.library_identity:
            raise ValueError("real library custody changed")
        if self.near_deadline and not self.probes:
            self.clock = 179.5

    def observe(self, kind, owner, environment, timeout_seconds):
        self.assertIs(owner, self.cargo_owner if kind == "cargo" else self.rust_owner)
        self.assertIsNotNone(environment, "ambient native guard invoked")
        self.assertIsNotNone(timeout_seconds, "default-budget native guard invoked")
        self.assertGreater(timeout_seconds, 0)
        self.assertLessEqual(timeout_seconds, 180 - self.clock)
        self.assertEqual(environment["HOME"], str(self.stage))
        self.assertEqual(
            environment["CARGO_HOME"], str(self.fixture.authority / "cargo-home")
        )
        self.assertEqual(environment["CARGO_NET_OFFLINE"], "true")
        self.assertNotIn("RUSTUP_TOOLCHAIN", environment)
        self.assertNotIn("AMBIENT_GUARD_SENTINEL", environment)
        self.probes.append((kind, timeout_seconds, self.clock))
        if self.near_deadline:
            # Each actual native observation respects its admitted timeout.
            self.clock += (
                timeout_seconds / 2 if kind == "cargo" else timeout_seconds * 2
            )

    def metadata(self):
        resolution = self.fixture.oracle.rust_harness.resolution
        by_identity = {row.identity: row for row in resolution.packages}
        owners = {
            "harness": self.stage,
            "library": self.fixture.export,
            **{
                "input:" + scope: self.fixture.authority / path
                for scope, path in self.fixture.oracle.rust_harness.inputs.roots
            },
        }
        return json.dumps(
            {
                "version": 1,
                "workspace_root": str(self.stage),
                "target_directory": str(self.stage / "target"),
                "packages": [
                    {
                        "id": row.identity.uri,
                        "name": row.name,
                        "version": row.version,
                        "source": row.source,
                        "manifest_path": str(owners[row.scope] / row.manifest),
                    }
                    for row in resolution.packages
                ],
                "resolve": {
                    "root": resolution.root.uri,
                    "nodes": [
                        {
                            "id": row.identity.uri,
                            "features": list(row.features),
                            "deps": [
                                {
                                    "name": edge.alias,
                                    "pkg": by_identity[edge.provider].identity.uri,
                                    "dep_kinds": [
                                        {"kind": edge.kind, "target": edge.target}
                                    ],
                                }
                                for edge in row.dependencies
                            ],
                        }
                        for row in resolution.packages
                    ],
                },
            }
        ).encode()

    def native_protocol(self, argv, **kwargs):
        self.assertGreater(kwargs["timeout_seconds"], 0)
        self.assertLessEqual(kwargs["timeout_seconds"], 180 - self.clock)
        self.commands.append(tuple(argv))
        if argv[0] == self.cargo.command[0] and argv[1] == "metadata":
            stdout = self.metadata()
        elif argv[0] == self.cargo.command[0] and argv[1] == "build":
            path = self.stage / "target/debug/litai-library-acceptance"
            path.parent.mkdir(parents=True)
            path.write_bytes(b"protocol verifier; never executed\n")
            stdout = b""
        else:
            stdout = json.dumps(
                {
                    "schema": "literate-ai/library-acceptance-results@1",
                    "cases": [
                        {
                            "case_id": row.case_id,
                            "capability": row.capability,
                            "result": row.expected_result,
                        }
                        for row in self.fixture.oracle.cases
                    ],
                }
            ).encode()
        if self.mutation and len(self.commands) == 1:
            target = (
                self.cargo.executable
                if self.mutation == "tool"
                else self.fixture.authority / "vendor/serde_json-1.0.151/Cargo.toml"
            )
            with Path(target).open("ab") as stream:
                stream.write(b"\nactual guarded input changed\n")
        return SimpleNamespace(returncode=0, stdout=stdout, stderr=b"")

    def operate(self):
        def cargo_guard(owner, environment=None, *, timeout_seconds=None, **_kwargs):
            self.observe("cargo", owner, environment, timeout_seconds)

        def rust_guard(owner, environment=None, *, timeout_seconds=None, **_kwargs):
            self.observe("rust", owner, environment, timeout_seconds)

        with (
            patch.object(CargoToolchain, "require_unchanged", cargo_guard),
            patch.object(RustToolchain, "require_unchanged", rust_guard),
            patch.object(executor, "run_bounded_process", self.native_protocol),
            patch.object(
                executor, "time", SimpleNamespace(monotonic=lambda: self.clock)
            ),
            patch.dict(
                os.environ,
                AMBIENT_GUARD_SENTINEL="not child authority",
                RUSTUP_TOOLCHAIN="ambient-unreviewed",
            ),
        ):
            # Capture the instrumented BOUND methods as the actual bindings'
            # guard fields. Patching a class alone cannot replace an already
            # saved bound method; an old implicit call must hit this sentinel.
            self.cargo = replace(
                self.cargo, _authority_guard=self.cargo_owner.require_unchanged
            )
            self.rustc = replace(
                self.rustc, _authority_guard=self.rust_owner.require_unchanged
            )
            with executor.execute_rust_library_harness(
                self.fixture.oracle,
                stage=self.stage,
                export=self.fixture.export,
                library_manifest=self.fixture.export / "Cargo.toml",
                library_alias=self.fixture.surface.package,
                cargo=self.cargo,
                rustc=self.rustc,
                cases_document=product_json_bytes(
                    [
                        {
                            "case_id": row.case_id,
                            "capability": row.capability,
                            "arguments": row.arguments,
                        }
                        for row in self.fixture.oracle.cases
                    ]
                ).decode(),
                surface_document=canonical_json_bytes(
                    self.fixture.surface.to_dict()
                ).decode(),
                environment=dict(os.environ),
                require_library_current=self.library_current,
                record_bytes=lambda b: ContentIdentity.parse_uri(
                    "sha256:" + hashlib.sha256(b).hexdigest()
                ),
                evidence_root=self.root / "evidence",
                allow_host_execution=True,
            ) as (_result, observation):
                self.assertEqual(
                    observation["cargo_toolchain_identity"],
                    self.cargo.authority_identity.uri,
                )
                self.assertEqual(
                    observation["rust_toolchain_identity"],
                    self.rustc.authority_identity.uri,
                )

    def test_whole_adapter_has_no_implicit_or_ambient_native_probes(self):
        self.operate()
        self.assertEqual(len(self.commands), 4)
        self.assertGreaterEqual(
            len(self.probes), 12
        )  # before/after all commands + closing
        self.assertEqual(
            [kind for kind, *_ in self.probes],
            ["cargo", "rust"] * (len(self.probes) // 2),
        )

    def test_remaining_deadline_charged_to_both_native_observers_before_command(self):
        self.near_deadline = True
        with self.assertRaises(ComponentAcceptanceError) as refused:
            self.operate()
        self.assertEqual(
            refused.exception.code, "component_acceptance.rust_harness_deadline"
        )
        self.assertEqual(self.commands, [])
        self.assertEqual(
            [(kind, timeout) for kind, timeout, _ in self.probes],
            [("cargo", 0.5), ("rust", 0.125)],
        )
        self.assertEqual(self.clock, 180)

    def test_actual_launcher_change_refuses_even_when_native_observer_is_permissive(
        self,
    ):
        self.mutation = "tool"
        with self.assertRaises(LocalStandardLifecycleError):
            self.operate()
        self.assertEqual(len(self.commands), 1)

    def test_actual_provisioned_source_change_still_refuses(self):
        self.mutation = "source"
        with self.assertRaises(ValueError):
            self.operate()
        self.assertEqual(len(self.commands), 1)

    def test_ordinary_binding_keeps_native_guard_while_pure_check_does_not_call_it(
        self,
    ):
        calls = []
        binding = LocalComponentToolBinding(
            self.cargo.executable, _authority_guard=lambda: calls.append("native")
        )
        binding.require_command_unchanged()
        self.assertEqual(calls, [])
        binding.require_unchanged()
        self.assertEqual(calls, ["native"])
        with Path(binding.executable).open("ab") as stream:
            stream.write(b"changed command")
        with self.assertRaises(LocalStandardLifecycleError):
            binding.require_command_unchanged()
        self.assertEqual(calls, ["native"])
