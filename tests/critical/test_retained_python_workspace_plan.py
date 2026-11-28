"""Strict Python receiving intent only; fixtures establish no live admission."""

import copy
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.repositories import RepositoryBuildCommand
from literate_ai.contracts.retained_libraries import RetainedLibraryGatePolicy
from literate_ai.contracts.retained_python import RetainedPythonWorkspacePlan
from literate_ai.contracts.retained_python_inputs import (
    RetainedPythonExportMount,
    RetainedPythonSourceChange,
    RetainedPythonWorkspaceBudget,
)
from literate_ai.schema_catalog import verify_schema_catalog
from tests.support import fixtures_test_retained_library_exports as export_fixtures
from tests.support.fixtures_test_schema_catalog import SchemaCatalog


class RetainedPythonWorkspacePlanTests(unittest.TestCase):
    def plan(self):
        exports = export_fixtures.RetainedLibraryExportTests().fixture()
        exports = replace(
            exports,
            libraries=tuple(
                replace(
                    product,
                    import_surface=replace(
                        product.import_surface,
                        language="python",
                        capabilities=tuple(
                            replace(
                                capability,
                                module=product.import_surface.package + ".logic",
                            )
                            for capability in product.import_surface.capabilities
                        ),
                    ),
                )
                for product in exports.libraries
            ),
        )
        interpreter = canonical_identity("fixture interpreter")
        metadata = BlobRef("a" * 64, 128, media_type="application/json")
        return RetainedPythonWorkspacePlan(
            "importer",
            "components/wrapper",
            metadata,
            canonical_identity("original scope"),
            metadata,
            RetainedLibraryGatePolicy(
                "importer",
                (
                    RepositoryBuildCommand("build", ("make",)),
                    RepositoryBuildCommand("test", ("python", "-m", "unittest")),
                    RepositoryBuildCommand("package", ("make", "package")),
                ),
                (interpreter,),
            ),
            interpreter,
            canonical_identity("target"),
            canonical_identity("environment"),
            exports,
            tuple(
                (identity, "packages/p" + str(i))
                for i, identity in enumerate(
                    sorted(
                        (
                            export.identity
                            for manifest in exports.graph.manifests
                            for export in manifest.exports
                        ),
                        key=lambda item: item.uri,
                    )
                )
            ),
            tuple(
                RetainedPythonExportMount(
                    product.artifact_export.identity,
                    canonical_identity("original artifact" + str(i)),
                    "wheel" if i else "source",
                    ".",
                    metadata if i else None,
                )
                for i, product in enumerate(exports.libraries)
            ),
            (
                RetainedPythonSourceChange("legacy.py", BlobRef("b" * 64, 32), None),
                RetainedPythonSourceChange(
                    "main.py", BlobRef("c" * 64, 64), BlobRef("d" * 64, 64)
                ),
            ),
            ("legacy.py",),
            RetainedPythonWorkspaceBudget(
                16, 1024, 4096, 1024**2, 1024**3, 16 * 1024**2
            ),
        )

    def test_roundtrip_retains_full_graph_original_inventories_gates_and_both_profiles(
        self,
    ):
        plan = self.plan()
        self.assertEqual(RetainedPythonWorkspacePlan.from_dict(plan.to_dict()), plan)
        self.assertEqual(len(plan.destinations), 3)
        self.assertEqual(len(plan.mounts), 2)
        self.assertEqual({mount.profile for mount in plan.mounts}, {"source", "wheel"})
        self.assertEqual(
            tuple(command.step_id for command in plan.gate_policy.commands),
            ("build", "test", "package"),
        )
        self.assertFalse(hasattr(plan, "qualified"))
        SchemaCatalog().validate(plan.SCHEMA, plan.to_dict())
        verify_schema_catalog("v2", Path(__file__).resolve().parents[2] / "schemas/v2")

    def test_foreign_missing_duplicate_mount_or_nonlibrary_destination_refuses(self):
        plan = self.plan()
        for changes in (
            {"mounts": plan.mounts[:-1]},
            {"mounts": plan.mounts[::-1]},
            {"mounts": plan.mounts + plan.mounts[:1]},
            {
                "mounts": (
                    replace(
                        plan.mounts[0], export_identity=canonical_identity("foreign")
                    ),
                    *plan.mounts[1:],
                )
            },
            {"destinations": plan.destinations[:-1]},
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(plan, **changes)

    def test_private_destinations_cannot_alias_nest_escape_or_own_source(self):
        plan = self.plan()
        for paths in (
            ("packages/A", "packages/a", "packages/c"),
            ("packages/a", "packages/a/child", "packages/c"),
            ("../escape", "packages/b", "packages/c"),
            ("implementation/dependency", "packages/b", "packages/c"),
            (".git/library", "packages/b", "packages/c"),
        ):
            with self.subTest(paths=paths), self.assertRaises(ValueError):
                replace(
                    plan,
                    destinations=tuple(
                        (row[0], path)
                        for row, path in zip(plan.destinations, paths, strict=True)
                    ),
                )

    def test_python_namespace_collision_foreign_language_and_startup_shadow_refuse(
        self,
    ):
        plan = self.plan()
        first, second = plan.exports.libraries

        def renamed(package):
            return replace(
                first.import_surface,
                package=package,
                capabilities=tuple(
                    replace(capability, module=package + ".logic")
                    for capability in first.import_surface.capabilities
                ),
            )

        for surface in (
            replace(first.import_surface, language="rust"),
            renamed(second.import_surface.package),
            renamed(second.import_surface.package.upper()),
            renamed("sys"),
        ):
            with self.subTest(surface=surface), self.assertRaises(ValueError):
                replace(
                    plan,
                    exports=replace(
                        plan.exports,
                        libraries=(replace(first, import_surface=surface), second),
                    ),
                )

    def test_missing_runtime_or_unsafe_root_or_unbound_retirement_refuses(self):
        plan = self.plan()
        wheel = next(mount for mount in plan.mounts if mount.profile == "wheel")
        with self.assertRaises(ValueError):
            replace(wheel, runtime_manifest=None)
        with self.assertRaises(ValueError):
            replace(wheel, import_root="../ambient")
        for changes in (
            {"retired_roots": ()},
            {"retired_roots": ("absent.py",)},
            {
                "source_changes": (
                    replace(plan.source_changes[0], after=BlobRef("e" * 64, 32)),
                    *plan.source_changes[1:],
                )
            },
        ):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                replace(plan, **changes)

    def test_every_reviewed_identity_changes_intent_without_changing_exports(self):
        plan = self.plan()
        for name in plan._IDENTITIES:
            changed = replace(
                plan,
                **{name: canonical_identity("different " + name)},
                **(
                    {
                        "gate_policy": replace(
                            plan.gate_policy,
                            toolchains=(canonical_identity("different " + name),),
                        )
                    }
                    if name == "interpreter_identity"
                    else {}
                ),
            )
            self.assertNotEqual(changed.identity, plan.identity)
            self.assertEqual(changed.exports, plan.exports)

    def test_closed_shapes_finite_bounds_and_interpreter_policy_refuse(self):
        plan = self.plan()
        for mutate in (
            lambda wire: wire.update(accepted=True),
            lambda wire: wire["mounts"][0].update(trusted=True),
            lambda wire: wire["budget"].update(maximum_files=True),
            lambda wire: wire.update(
                schema="literate-ai/retained-cargo-workspace-plan@1"
            ),
        ):
            wire = copy.deepcopy(plan.to_dict())
            mutate(wire)
            with self.assertRaises((ValueError, TypeError)):
                RetainedPythonWorkspacePlan.from_dict(wire)
        with self.assertRaises(ValueError):
            replace(
                plan, interpreter_identity=canonical_identity("unreviewed interpreter")
            )
