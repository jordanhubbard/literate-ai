"""Local receiver/native lifetime joins; rebuild, model and probe ports are fixtures.

Archive extraction, path admission, candidate publication, artifact/evidence IO and
original descriptor retirement are real. No SSH/worker/native acceptance is claimed.
"""

from __future__ import annotations

import copy
import json
import sys
import tarfile
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock, patch

from literate_ai.adapters import remote_execution as remote
from literate_ai.adapters.generation_preparation import (
    FilesystemLockedGenerationApplicationAdapter,
)
from literate_ai.adapters.project_runtime import (
    ProjectRuntimeError,
    allocate_project_runtime,
    current_project_runtime,
    project_runtime_scope,
    require_project_runtime,
)
from literate_ai.adapters.source_materialization import capture_source_archive
from literate_ai.cache_directories import (
    bind_cache_directories,
    resolve_cache_directories,
)
from literate_ai.cli import rebuild as rebuild_cli
from literate_ai.cli import worker as worker_cli
from literate_ai.contracts import LifecycleDispatchAction
from literate_ai.projects import load_project
from literate_ai.remote_source_guard import SourceGuardError
from tests.critical import test_project_layout_receiver_cache as cache_fixture
from tests.critical import test_project_layout_runtime_cli as cli_fixture
from tests.support.fixtures_test_remote_execution import (
    identity,
    materialization,
    observation,
    request,
    worker,
)


class BoundaryReached(Exception):
    pass


class ReceiverRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.f = cache_fixture.ProjectLayoutReceiverCacheTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.project = load_project(self.f.root)

    def nested_custody(self, project=None):
        project = self.project if project is None else project
        owner = allocate_project_runtime(project, nested=True)
        directories = resolve_cache_directories(project.root, environment={})
        custody = remote.RemoteLifecycleCustody(
            project.root.parent,
            bind_cache_directories(
                project.root, build_dir=directories.build_dir, obj_dir=owner.object_root
            ),
            owner.path,
            owner.candidate_receipt,
            owner,
        )
        return owner, custody

    def capture(self, selected):
        with patch.dict("os.environ", {"BUILD_DIR": "", "OBJ_DIR": ""}):
            return capture_source_archive(
                self.project.root, selected, directory=self.f.staging
            )

    def test_original_scope_and_absent_nested_scope_are_distinct(
        self,
    ):
        owner, custody = self.nested_custody()
        try:
            with project_runtime_scope(owner, self.project):
                self.assertIs(current_project_runtime(self.project), owner)
                self.assertEqual(
                    rebuild_cli._external_runtime_root(self.project, str(owner.path)),
                    owner.path,
                )
                self.assertEqual(
                    rebuild_cli._external_candidate(
                        self.project, str(owner.candidate_receipt)
                    ),
                    owner.candidate_receipt,
                )
                with self.assertRaises(ValueError):
                    rebuild_cli._external_candidate(
                        self.project, str(owner.path / "foreign.json")
                    )
                with project_runtime_scope(None, None):
                    self.assertIsNone(current_project_runtime())
                    with self.assertRaises(rebuild_cli.CliFailure):
                        rebuild_cli._external_runtime_root(
                            self.project, str(owner.path)
                        )
                self.assertIs(current_project_runtime(), owner)
            self.assertIsNone(current_project_runtime())
            with self.assertRaises(ProjectRuntimeError):
                with project_runtime_scope(copy.copy(owner), self.project):
                    self.fail("copied owner became a scope")
            with self.assertRaises(ProjectRuntimeError):
                replace(custody, project_runtime=copy.copy(owner))
        finally:
            owner.close(keep=False)

    def test_original_standard_cli_borrows_owner_and_writes_only_exact_candidate(self):
        f = cli_fixture.ProjectLayoutRuntimeCliTests("runTest")
        f.setUp()
        self.addCleanup(f.doCleanups)
        owner, custody = self.nested_custody(f.project)
        try:

            def rebuild(selected):
                self.assertIs(selected.project_runtime, owner)
                require_project_runtime(owner, f.project, selected.source_root)
                rebuild_cli._write_standard_candidate(
                    custody.candidate_receipt,
                    SimpleNamespace(to_dict=lambda: {"fixture": "not-qualification"}),
                )
                raise BoundaryReached

            args = SimpleNamespace(
                flavor=[],
                force_regeneration=False,
                allow_host_execution=True,
                runtime_root=str(custody.runtime_root),
                candidate_receipt=str(custody.candidate_receipt),
                keep_runtime=True,
                target="host",
                source_cache_entry=[],
            )
            with (
                project_runtime_scope(owner, f.project),
                patch.object(
                    FilesystemLockedGenerationApplicationAdapter,
                    "prepare",
                    return_value=f.prepared,
                ),
                patch(
                    "literate_ai.cli.rebuild._component_acceptance_oracle",
                    return_value=None,
                ),
                patch(
                    "literate_ai.cli.rebuild."
                    "assemble_filesystem_standard_rebuild_adapter",
                    return_value=SimpleNamespace(rebuild=rebuild),
                ),
                self.assertRaises(BoundaryReached),
            ):
                rebuild_cli._standard_rebuild_one_component(
                    f.project,
                    f.f.binding,
                    args,
                    f.specification,
                    "litai/components/example",
                    update_receipt=False,
                    write_candidate=True,
                    hold_lock=False,
                )
            require_project_runtime(owner, f.project, owner.path / "sources")
            self.assertEqual(
                json.loads(custody.candidate_receipt.read_bytes()),
                {"fixture": "not-qualification"},
            )
            self.assertIsNone(current_project_runtime())
        finally:
            owner.close(keep=False)

    def test_worker_local_callback_enters_actual_owner_scope(self):
        selected = request(LifecycleDispatchAction.BUILD)
        source = materialization(selected, self.project.root)
        paths = {}
        for name, value in (
            ("worker_file", worker().to_dict()),
            ("request", selected.to_dict()),
            ("materialization", source.to_dict()),
        ):
            path = self.f.staging / (name + ".json")
            path.write_text(json.dumps(value))
            paths[name] = str(path)
        owner, custody = self.nested_custody()
        observed = []
        try:

            def rebuild(args, *, cache_directories):
                self.assertIs(current_project_runtime(self.project), owner)
                self.assertIs(cache_directories, custody.cache_directories)
                self.assertEqual(
                    rebuild_cli._external_runtime_root(self.project, args.runtime_root),
                    owner.path,
                )
                self.assertEqual(
                    rebuild_cli._external_candidate(
                        self.project, args.candidate_receipt
                    ),
                    owner.candidate_receipt,
                )
                observed.append(True)
                raise BoundaryReached

            def transport(_worker, _request, _source, **values):
                return values["rebuild"](
                    component_path=selected.component_path,
                    project_root=self.project.root,
                    custody=custody,
                    flavor_selectors=selected.flavor_selectors,
                    target_profile=selected.target_profile,
                    model_selector=None,
                    accepted_source_only=False,
                    accepted_source_provider_id=None,
                    accepted_source_provider_identity=None,
                    jobs=1,
                )

            args = SimpleNamespace(
                **paths,
                archive=str(self.f.staging / "not-consumed.tar.gz"),
                workspace=str(self.f.base / "not-dispatched"),
                cas_root=str(self.f.base / "cas"),
            )
            with (
                patch.object(remote, "materialize_and_execute", side_effect=transport),
                patch.object(rebuild_cli, "rebuild_from_args", side_effect=rebuild),
                self.assertRaises(BoundaryReached),
            ):
                worker_cli._execute_from_args(args)
            self.assertEqual(observed, [True])
            self.assertIsNone(current_project_runtime())
            require_project_runtime(owner, self.project)
        finally:
            owner.close(keep=False)

    def test_archive_evidence_import_has_disjoint_scopes_and_no_live_control_token(
        self,
    ):
        selected = request(LifecycleDispatchAction.BUILD)
        captured = self.capture(selected)
        seen = []

        def rebuild(**values):
            custody = values["custody"]
            project = load_project(values["project_root"])
            require_project_runtime(
                custody.project_runtime, project, custody.runtime_root / "sources"
            )
            self.assertNotEqual(custody.cache_directories.obj_dir, custody.runtime_root)
            custody.cache_directories.obj_dir.mkdir()
            (custody.cache_directories.obj_dir / "invocation-only.txt").write_bytes(
                b"object fixture\n"
            )
            custody.candidate_receipt.write_bytes(b'{"fixture":"not-qualification"}\n')
            artifact = custody.runtime_root / "app.bin"
            artifact.write_bytes(b"artifact fixture; never executed\n")
            seen.append((custody, custody.identity))
            return {
                "artifact": str(artifact),
                "execution_command": {
                    "argv": [sys.executable, str(artifact)],
                    "environment": {},
                },
                "runtime_root": str(custody.runtime_root),
                "candidate_receipt": str(custody.candidate_receipt),
                "observed_toolchain_identities": [identity("5").uri],
            }

        workspace = self.f.base / (selected.identity.digest[:24] + "-contained")
        bundle = self.f.staging / "evidence.tar.gz"
        ticket = self.f.staging / "cleanup.json"
        with patch.object(
            remote, "probe_worker_capabilities", return_value=observation()
        ):
            result = remote.materialize_and_execute(
                worker(),
                selected,
                captured.materialization,
                archive=captured.path,
                workspace=workspace,
                cas_root=self.f.base / "cas",
                rebuild=rebuild,
                evidence_output=bundle,
                cleanup_ticket=ticket,
            )
        self.assertEqual(len(seen), 1)
        custody, original_identity = seen[0]
        self.assertEqual(
            custody.identity, original_identity
        )  # Inert history, not a live grant.
        with self.assertRaises(ProjectRuntimeError):
            require_project_runtime(
                custody.project_runtime,
                load_project(custody.cache_directories.project_root),
            )
        with tarfile.open(bundle, "r:gz") as archive:
            names = archive.getnames()
        self.assertIn("receipt/candidate.json", names)
        self.assertIn("source/runtime/app.bin", names)
        self.assertIn("object/cache/invocation-only.txt", names)
        self.assertFalse(
            any(".runtime.write" in name or ".rt-" in name for name in names)
        )
        self.assertEqual(sum(name.endswith("invocation-only.txt") for name in names), 1)
        self.assertTrue(workspace.is_dir())
        self.assertTrue(ticket.is_file())
        imported, _ = remote.import_remote_evidence_bundle(
            bundle,
            result.evidence_manifest,
            expected_bundle_identity=result.evidence_reference.identity,
            store_root=self.f.base / "coordinator-cas",
        )
        self.assertIsNotNone(imported)
        self.assertEqual(
            (self.project.root / "native.txt").read_bytes(), b"application source\n"
        )

    def test_exact_source_verification_precedes_runtime_allocation(self):
        selected = request(LifecycleDispatchAction.BUILD)
        captured = self.capture(selected)
        original = remote.extract_source_archive_with_manifest

        def substituted(*args):
            value = original(*args)
            (args[1] / "literate-ai/native.txt").write_bytes(b"changed source\n")
            return value

        with (
            patch.object(
                remote, "extract_source_archive_with_manifest", side_effect=substituted
            ),
            patch.object(
                remote,
                "allocate_project_runtime",
                side_effect=AssertionError(
                    "runtime allocated before source verification"
                ),
            ) as allocate,
            self.assertRaises(SourceGuardError),
        ):
            remote.materialize_and_execute(
                worker(),
                selected,
                captured.materialization,
                archive=captured.path,
                workspace=self.f.base / "tampered",
                cas_root=self.f.base / "cas",
                rebuild=Mock(),
            )
        allocate.assert_not_called()

    def test_failed_rebuild_preserves_foreign_runtime_and_extraction_workspace(self):
        selected = request(LifecycleDispatchAction.BUILD)
        captured = self.capture(selected)
        foreign = []

        def rebuild(**values):
            custody = values["custody"]
            old = custody.runtime_root.with_name("original-runtime")
            custody.runtime_root.rename(old)
            custody.runtime_root.mkdir()
            path = custody.runtime_root / "foreign.txt"
            path.write_bytes(b"preserve concurrent runtime\n")
            foreign.append((path, path.stat().st_ino))
            raise BoundaryReached

        workspace = self.f.base / "interrupted"
        with self.assertRaises(BoundaryReached) as caught:
            remote.materialize_and_execute(
                worker(),
                selected,
                captured.materialization,
                archive=captured.path,
                workspace=workspace,
                cas_root=self.f.base / "cas",
                rebuild=rebuild,
            )
        self.assertTrue(caught.exception.__notes__)
        self.assertTrue(workspace.is_dir())
        self.assertEqual(foreign[0][0].stat().st_ino, foreign[0][1])
        self.assertEqual(foreign[0][0].read_bytes(), b"preserve concurrent runtime\n")
