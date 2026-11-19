"""Actual external SDK production and refusal at live ownership boundaries."""

import copy
import dataclasses
import os
import pickle
import shutil
import stat
import subprocess
import sys
import unittest
from contextlib import ExitStack
from unittest import mock

from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.native_sdk_acquisition import NativeSdkProjectAcquisition
from literate_ai.adapters.native_sdk_build import NativeSdkRepositoryBuilder
from literate_ai.adapters.native_sdk_custody import materialize_native_sdk
from literate_ai.adapters.native_sdk_recipes import select_native_sdk_recipes
from literate_ai.adapters.native_sdk_tree_custody import (
    materialize_native_sdk_tree_snapshot,
)
from literate_ai.adapters.native_sdk_workspace import native_sdk_build_workspace
from literate_ai.contracts import SourceIntelligenceMode
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_sdk_tree_products import NativeSdkTreeBuildLayout
from literate_ai.contracts.repositories import RepositoryBuildCommand
from literate_ai.contracts.retained_project import RetainedProjectLimits
from literate_ai.security import (
    AuthorizationError,
    AuthorizationRevocationSet,
    DirectBuildAuthorizationVerifier,
    SecurityPolicy,
)
from tests.support import fixtures_test_native_sdk_build as support
from tests.support import fixtures_test_native_sdk_recipes as recipes
from tests.support.fixtures_test_repository_sources import source_intelligence_policy


class NativeSdkExternalWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.fixture = support.NativeSdkBuildTests(
            "test_real_repository_pipeline_retains_native_sdk_for_relocation"
        )
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()

    def builder(self, workspace=None):
        f = self.fixture
        return NativeSdkRepositoryBuilder(
            layout=f.layout,
            tools=f.tools,
            store=f.store,
            grant_lookup=lambda identity: f.grants[identity.uri],
            environment=dict(os.environ),
            authorization_verifier=DirectBuildAuthorizationVerifier(),
            workspace=workspace,
        )

    def external_plan(self):
        f = self.fixture
        return dataclasses.replace(
            f.plan,
            commands=(
                RepositoryBuildCommand(
                    "configure",
                    (
                        "cmake",
                        "-S",
                        "@SDK_SOURCE_ROOT@",
                        "-B",
                        "@SDK_WORKSPACE_ROOT@/_build",
                    ),
                ),
                RepositoryBuildCommand(
                    "build",
                    (
                        "cmake",
                        "--build",
                        "@SDK_WORKSPACE_ROOT@/_build",
                        "--config",
                        "Release",
                        "--parallel",
                        "2",
                    ),
                ),
            ),
        )

    def test_read_only_source_external_outputs_retire_and_real_consumer(self):
        f = self.fixture
        originals = [f.source, *f.source.rglob("*")]
        modes = {p: stat.S_IMODE(p.stat().st_mode) for p in originals}
        with native_sdk_build_workspace(f.root) as workspace:
            f.builder = self.builder(workspace)
            f.plan = self.external_plan()
            try:
                for path in originals:
                    path.chmod(modes[path] & ~0o222)
                verification = f.verify()
            finally:
                for path in originals:
                    path.chmod(modes[path])
            product = f.builder.product(verification)
            self.assertFalse((f.source / "_build").exists())
            self.assertTrue((workspace.root / f.layout.sdk_root / "LICENSE").is_file())
            result = f.store.get_manifest(product.result_blob)
            self.assertEqual(result["workspace"], workspace.identity.to_dict())
            self.assertEqual(len(result["commands"]), 2)
            self.assertTrue(
                all(
                    "@SDK_" not in arg
                    for step in result["commands"]
                    for arg in step["argv"]
                )
            )
            root = workspace.root
        with self.assertRaisesRegex(ValueError, "ended"):
            workspace.require_unchanged()
        f.remove_source()
        shutil.rmtree(root)
        relocated = materialize_native_sdk(
            product.snapshot,
            expected_identity=product.snapshot.identity,
            store=f.store,
            parent=f.root,
        )
        run = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import sys; sys.path.insert(0,sys.argv[1]); "
                "import vendor_math; print(vendor_math.scale(1.5,3))",
                str(relocated / "python"),
            ),
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "4.5")

    def test_legacy_request_identity_is_unchanged(self):
        f = self.fixture
        expected = canonical_identity(
            {
                "plan": f.plan.identity.to_dict(),
                "layout": f.layout.identity.to_dict(),
                "tools": {
                    name: tool.toolchain_identity.to_dict()
                    for name, tool in f.tools.items()
                },
                "environment": dict(os.environ),
                "timeout_seconds": "300",
            }
        )
        request = self.builder().request(f.lock, f.plan)
        self.assertEqual(request.builder_id, "native-sdk-repository:" + expected.uri)

    def test_scope_is_not_copyable_or_serializable_and_products_are_retained(self):
        with native_sdk_build_workspace(self.fixture.root) as workspace:
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.assertRaises(TypeError):
                    operation(workspace)
            root = workspace.root
            (root / "partial").write_text("retained")
        self.assertEqual((root / "partial").read_text(), "retained")
        self.assertFalse((root / "owner.lock").exists())

    def test_source_overlap_refuses_before_any_build_command(self):
        f = self.fixture
        with native_sdk_build_workspace(f.source) as workspace:
            f.builder = self.builder(workspace)
            f.plan = self.external_plan()
            with mock.patch(
                "literate_ai.adapters.native_sdk_build.run_bounded_process"
            ) as run:
                with self.assertRaisesRegex(ValueError, "disjoint"):
                    f.verify()
                run.assert_not_called()

    def test_grant_cannot_move_to_another_workspace(self):
        f = self.fixture
        with native_sdk_build_workspace(f.root) as first:
            with native_sdk_build_workspace(f.root) as second:
                f.builder = self.builder(first)
                f.plan = self.external_plan()
                approval = f.approve()
                f.builder = self.builder(second)
                with mock.patch(
                    "literate_ai.adapters.native_sdk_build.run_bounded_process"
                ) as run:
                    with self.assertRaises(AuthorizationError):
                        f.verify(approval)
                    run.assert_not_called()

    def test_unknown_path_slot_refuses_before_authorization(self):
        f = self.fixture
        with native_sdk_build_workspace(f.root) as workspace:
            f.builder = self.builder(workspace)
            plan = dataclasses.replace(
                f.plan,
                commands=(
                    RepositoryBuildCommand("bad", ("cmake", "@SDK_OTHER_ROOT@")),
                ),
            )
            with self.assertRaisesRegex(ValueError, "unknown"):
                f.approve(plan)

    def test_physical_path_slot_text_is_not_expanded_a_second_time(self):
        f = self.fixture
        source = f.root / "literal-@SDK_WORKSPACE_ROOT@"
        source.mkdir()
        with native_sdk_build_workspace(f.root) as workspace:
            expanded = workspace.expand_arguments(
                ("@SDK_SOURCE_ROOT@/input", "@SDK_OUTPUT_ROOT@"),
                source=source,
                sdk_root="sdk",
            )
            self.assertEqual(
                expanded, (str(source / "input"), str(workspace.root / "sdk"))
            )

    def test_ended_scope_refuses_an_existing_grant_before_execution(self):
        f = self.fixture
        with native_sdk_build_workspace(f.root) as workspace:
            f.builder = self.builder(workspace)
            f.plan = self.external_plan()
            approval = f.approve()
        with mock.patch(
            "literate_ai.adapters.native_sdk_build.run_bounded_process"
        ) as run:
            with self.assertRaisesRegex(ValueError, "ended"):
                f.verify(approval)
            run.assert_not_called()

    def test_environment_cannot_supply_path_slots(self):
        f = self.fixture
        with native_sdk_build_workspace(f.root) as workspace:
            f.builder = self.builder(workspace)
            f.builder.environment["SDK_FIXTURE_VALUE"] = "@SDK_SOURCE_ROOT@"
            with self.assertRaisesRegex(ValueError, "environment"):
                f.approve()

    def test_source_mutation_preserves_partial_work_and_stops_next_command(self):
        f = self.fixture
        with native_sdk_build_workspace(f.root) as workspace:
            f.builder = self.builder(workspace)
            f.plan = self.external_plan()

            def mutate(*args, **kwargs):
                result = run_bounded_process(*args, **kwargs)
                self.assertEqual(result.returncode, 0, result.stderr)
                with (f.source / "vendor_math.c").open("a") as changed:
                    changed.write("\n/* changed after configuration */\n")
                return result

            with mock.patch(
                "literate_ai.adapters.native_sdk_build.run_bounded_process",
                side_effect=mutate,
            ) as run:
                with self.assertRaisesRegex(ValueError, "source differs"):
                    f.verify()
                self.assertEqual(run.call_count, 1)
            self.assertTrue((workspace.root / "_build").is_dir())

    @unittest.skipIf(os.name == "nt", "original SDK alias fixture requires POSIX")
    def test_tree_sdk_external_capture_retains_aliases_and_relocates(self):
        f = self.fixture
        old = f.layout
        original = old.native_libraries[-1]
        hard, symbolic = original + ".hard", original + ".symbolic"
        f.layout = NativeSdkTreeBuildLayout(
            **{
                field.name: getattr(old, field.name)
                for field in dataclasses.fields(old)
                if field.name != "native_libraries"
            },
            native_libraries=tuple(sorted((old.native_libraries[0], hard, symbolic))),
            limits=RetainedProjectLimits(1000, 64 * 1024 * 1024, 128 * 1024 * 1024),
        )
        with native_sdk_build_workspace(f.root) as workspace:
            f.builder = self.builder(workspace)
            f.plan = dataclasses.replace(
                self.external_plan(),
                evidence=(f.layout.identity,),
                commands=(
                    *self.external_plan().commands,
                    RepositoryBuildCommand(
                        "hardlink",
                        (
                            "cmake",
                            "-E",
                            "create_hardlink",
                            "@SDK_OUTPUT_ROOT@/" + original,
                            "@SDK_OUTPUT_ROOT@/" + hard,
                        ),
                    ),
                    RepositoryBuildCommand(
                        "symlink",
                        (
                            "cmake",
                            "-E",
                            "create_symlink",
                            original.rsplit("/", 1)[-1],
                            "@SDK_OUTPUT_ROOT@/" + symbolic,
                        ),
                    ),
                ),
            )
            product = f.builder.product(f.verify())
            self.assertEqual(
                {a.kind for a in product.snapshot.tree.aliases}, {"hardlink", "symlink"}
            )
            root = workspace.root
        f.remove_source()
        shutil.rmtree(root)
        relocated = materialize_native_sdk_tree_snapshot(
            product.snapshot,
            expected_identity=product.snapshot.identity,
            store=f.store,
            limits=f.layout.limits,
            parent=f.root,
        )
        self.assertEqual(
            (relocated / hard).stat().st_ino, (relocated / original).stat().st_ino
        )
        self.assertTrue((relocated / symbolic).is_symlink())
        run = subprocess.run(
            (
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import sys;sys.path.insert(0,sys.argv[1]);"
                "import vendor_math;print(vendor_math.scale(1.5,3))",
                str(relocated / product.snapshot.import_root),
            ),
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertEqual(run.stdout.strip(), "4.5")

    def test_public_project_acquisition_owns_output_for_authored_path_slots(self):
        self._qualify_public_acquisition(use_factory=False)

    def test_public_project_acquisition_accepts_live_host_owned_placement(self):
        self._qualify_public_acquisition(use_factory=True)

    def _qualify_public_acquisition(self, *, use_factory):
        case = recipes.NativeSdkRecipeTests(
            "test_selected_flavor_recipe_drives_real_native_build_and_relocation"
        )
        self.addCleanup(case.doCleanups)
        case.setUp()
        case.recipe = dataclasses.replace(
            case.recipe, commands=self.external_plan().commands
        )
        case.write_recipe(case.recipe)
        snapshot = case.snapshot()
        revision = next(
            n.revision.identity
            for n in snapshot.authority.lock.nodes
            if n.revision.repository_sources
        )
        (selected,) = select_native_sdk_recipes(snapshot, revision)
        with ExitStack() as owners:
            options = {}
            if use_factory:
                workspace = owners.enter_context(
                    native_sdk_build_workspace(case.fixture.root)
                )
                options["workspace_factory"] = lambda selection: workspace
            acquire = NativeSdkProjectAcquisition(
                cache_root=case.fixture.root / "sdk-cache",
                source_intelligence_policy=source_intelligence_policy(
                    "none", SourceIntelligenceMode.OFF
                ),
                security_policy=SecurityPolicy(canonical_identity("policy").uri),
                revocations=lambda: AuthorizationRevocationSet(),
                environment=dict(os.environ),
                actor="SDK fixture operator",
                reason="Qualify original external SDK production",
                host_build_acknowledged=True,
                store=case.fixture.store,
                **options,
            )
            inputs = acquire(snapshot)
            (binding,) = inputs.for_consumer(
                revision, target_identity=selected.target_identity
            )
            self.assertEqual(
                binding.build.product.snapshot.source_lock_identity,
                selected.source_lock.identity,
            )
            roots = (
                [workspace.root]
                if use_factory
                else list((case.fixture.root / "sdk-cache").glob("native-sdk-*"))
            )
        self.assertEqual(len(roots), 1)
        self.assertFalse((roots[0] / "owner.lock").exists())
        shutil.rmtree(roots[0])
        case.fixture.remove_source()
        inputs.require_unchanged()
        parent = case.fixture.root / "received"
        parent.mkdir()
        with inputs.materialize(
            revision, target_identity=selected.target_identity, parent=parent
        ) as placed:
            self.assertEqual(len(placed), 1)
            self.assertTrue((placed[0].root / "LICENSE").is_file())

    def test_substituted_output_root_is_retained_and_stops_next_command(self):
        f = self.fixture
        saved = None
        with self.assertRaisesRegex(
            (ValueError, ExceptionGroup), "reservation|workspace"
        ):
            with native_sdk_build_workspace(f.root) as workspace:
                f.builder = self.builder(workspace)
                f.plan = self.external_plan()
                saved = workspace.root.with_name("saved-output")

                def substitute(*args, **kwargs):
                    result = run_bounded_process(*args, **kwargs)
                    self.assertEqual(result.returncode, 0, result.stderr)
                    workspace.root.rename(saved)
                    workspace.root.mkdir()
                    (workspace.root / "foreign").write_text("preserve")
                    return result

                with mock.patch(
                    "literate_ai.adapters.native_sdk_build.run_bounded_process",
                    side_effect=substitute,
                ) as run:
                    try:
                        f.verify()
                    finally:
                        self.assertEqual(run.call_count, 1)
        self.assertEqual((workspace.root / "foreign").read_text(), "preserve")
        self.assertTrue((saved / "_build").is_dir())
