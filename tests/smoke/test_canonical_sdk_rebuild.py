"""Explicit authored installed rebuild case; no model or wheel qualification."""

import base64
import hashlib
import os
import shutil
import sys
import unittest
from contextlib import nullcontext
from dataclasses import replace
from pathlib import Path
from unittest import mock

import literate_ai
from literate_ai.adapters.component_lock_planning import FilesystemComponentLockPlanner
from literate_ai.adapters.component_locks import ComponentLockStore
from literate_ai.adapters.component_resolution_audits import (
    ComponentResolutionAuditStore,
)
from literate_ai.adapters.generation_preparation import (
    FilesystemLockedGenerationApplicationAdapter,
    LockedComponentModelSelectionAdapter,
)
from literate_ai.adapters.models import CodingCliSourceGenerator
from literate_ai.adapters.project_initialization import (
    initialize_project,
    record_project_authority_review,
)
from literate_ai.adapters.project_validation import validated_project_authority_identity
from literate_ai.adapters.standard_lifecycle_binding import (
    observe_installed_framework_distribution,
    resolve_standard_project_lifecycle_driver,
)
from literate_ai.adapters.standard_project import (
    FilesystemStandardProjectPlanningAdapter,
    FilesystemStandardSourceGenerationAdapter,
    admit_locked_authored_assets,
)
from literate_ai.adapters.standard_rebuild import (
    FilesystemStandardRebuildRequest,
    assemble_filesystem_standard_rebuild_adapter,
)
from literate_ai.application.component_lock_resolution import ComponentLockResolver
from literate_ai.application.generation_preparation import GenerationPreparationRequest
from literate_ai.contracts import (
    ProjectTestReceiptPolicy,
    RepositoryParentSelection,
    StandardProjectLifecycleDriver,
    canonical_identity,
    load_current_standard_lifecycle_policy,
    rebuild_project_authority_identity,
)
from literate_ai.contracts.authoring_markdown import (
    parse_authoring_markdown,
    render_authoring_markdown,
)
from literate_ai.projects import ProjectConfigurationStore, load_project
from literate_ai.storage import FileSystemCAS
from tests.smoke import test_canonical_sdk_runtime as runtime_fixture
from tests.smoke.test_node_sdk_cross_language import with_provider
from tests.support.authored_coding_cli import AuthoredCodingCLI

REBUILD_EVIDENCE = None
REBUILD_ATTEMPT = None


class _ObservedRunner:
    """Keep original key/publication methods and surround its one actual call."""

    def __init__(self, original, setup, observer):
        self.original, self.setup, self.observer = original, setup, observer

    def __getattr__(self, name):
        return getattr(self.original, name)

    def __call__(self, prepared):
        if self.setup.active_node is not None:
            raise AssertionError("authored rebuild source observation cannot nest")
        self.setup.active_node = prepared
        self.setup.original_calls = 0
        try:
            result = self.observer(prepared)
            if self.setup.original_calls != 1 or result is not self.setup.last_output:
                raise AssertionError("original source runner result required unchanged")
            return result
        finally:
            self.setup.active_node = None
            self.setup.last_output = None


def _bounded_failure_observation(failure, diagnostics):
    """Keep at most 64 KiB serialized, reserving the attempt's other 192 KiB."""
    import json

    if type(diagnostics) is not dict:
        raise TypeError("authored diagnostic table required")
    maximum = 65536
    count = min(len(diagnostics), 8)
    message_budget = min(16384, (maximum - 4096) // (count + 1))
    truncated = len(diagnostics) > count

    def text(value, budget):
        nonlocal truncated
        if type(value) is not str:
            raise TypeError("authored diagnostic must be text")
        # Bound before encoding, then account for the actual keeper's JSON
        # escaping, including control characters and non-BMP Unicode.
        captured = value[: budget - 2]
        while len(json.dumps(captured, ensure_ascii=True)) > budget:
            captured = captured[: len(captured) // 2]
        truncated |= len(captured) != len(value)
        return captured

    rows = []
    for index, (revision, diagnostic) in enumerate(diagnostics.items()):
        if index == count:
            break
        rows.append(
            {
                "component_revision": text(revision, 256),
                "message": text(diagnostic, message_budget),
            }
        )
    message = text(str(failure), message_budget)
    exception_type = text(type(failure).__name__, 128)
    observation = {
        "qualified": False,
        "state": "captured",
        "exception_type": exception_type,
        "message": message,
        "diagnostics": rows,
        "truncated": truncated,
    }
    if len(json.dumps(observation, sort_keys=True).encode("utf-8")) > maximum:
        raise ValueError("authored diagnostic observation exceeded serialized budget")
    return observation


class AuthoredSDKRebuildSetup:
    def __init__(self, owner, *, diagnostic_observer=None):
        self.owner = owner
        if diagnostic_observer is not None:
            from tests.support.sdk_probe_timing import SDKProbeTiming

            if type(diagnostic_observer) is not SDKProbeTiming:
                raise TypeError("original diagnostic observer required")
        self.diagnostic_observer = diagnostic_observer
        self.probe_observation = None
        self.active_node = self.last_output = self.original_runner = None
        self.generated = self.attempts = 0
        self.evidence = self.program_observation = self.failure_observation = None

    def prepare_authority(self, root):
        if not sys.flags.isolated or not Path(
            literate_ai.__file__
        ).resolve().is_relative_to(Path(sys.prefix).resolve()):
            raise AssertionError("rebuild cell requires the isolated installed wheel")
        self.root = root
        self.work = root.parent
        self.child = AuthoredCodingCLI(self.work / "fixture-cli")
        program = self.child.executable.read_bytes()
        self.program_observation = {
            "sha256": self.child.identity,
            "bytes_base64": base64.b64encode(program).decode(),
        }
        environment = {
            key: os.environ[key]
            for key in (
                "PATH",
                "LITERATE_TYPESCRIPT_SDK",
                "LITAI_TYPESCRIPT_SDK",
                "TMPDIR",
            )
            if key in os.environ
        }
        environment.update(
            PATH=str(self.child.root) + os.pathsep + environment.get("PATH", ""),
            CODING_CLI="codex",
            LITAI_CODING_PROVIDER="coding-cli",
            LITAI_CONFIG_DIR=str(self.work / "private-config"),
            LITAI_MCP_TRANSPORT="off",
        )
        environment["LITAI_TYPESCRIPT_SDK"] = environment["LITERATE_TYPESCRIPT_SDK"]
        scope = mock.patch.dict(os.environ, environment, clear=True)
        scope.start()
        self.owner.addCleanup(scope.stop)
        graph = self.work / "graph-fixture"
        old_component, old_snapshot, _ = with_provider(graph)
        initialize_project(
            root,
            parent_selection=RepositoryParentSelection.root(),
            source_intelligence_provider="none",
            empty=True,
            bootstrap_tools=False,
        )
        for path in graph.iterdir():
            if path.is_dir() and (path / "component.md").is_file():
                shutil.copytree(path, root / "components" / path.name)
        for document in (root / "components").rglob("component.md"):
            value, body = parse_authoring_markdown(
                document.read_bytes(), source=str(document)
            )
            value["workflow_definition"] = "workflows/sample-host.md"
            value["routing_policy"] = "routing/sample-host.json"
            document.write_bytes(render_authoring_markdown(value, body))
        for relative in ("flavors", "skills/specification-to-source"):
            shutil.copytree(graph / relative, root / relative, dirs_exist_ok=True)
        observed = observe_installed_framework_distribution()
        policy = load_current_standard_lifecycle_policy()
        driver = StandardProjectLifecycleDriver(observed.identity, policy.identity)
        config = ProjectConfigurationStore.discover(root)
        receipt_policy = ProjectTestReceiptPolicy(
            policy.policy_id,
            policy.policy_version,
            driver.identity,
            tuple(sorted(policy.required_evidence_kinds)),
            policy.minimum_test_count,
        )
        ProjectConfigurationStore(root).update(
            config,
            replace(
                config.definition,
                lifecycle_driver=driver,
                test_receipt_policy=receipt_policy,
            ),
        )
        self.project = load_project(root)
        self.binding = resolve_standard_project_lifecycle_driver(driver)
        component = root / "components" / old_component.name
        # Every fixture-authority edit precedes a fresh public lock/audit.
        target, selectors = old_snapshot._target_name, old_snapshot._flavor_selectors
        plan = FilesystemComponentLockPlanner().plan(
            component,
            target_name=target,
            flavor_selectors=selectors,
            flavor_roots=(root / "flavors",),
        )
        resolution = ComponentLockResolver().resolve(
            plan, expected_input_evidence_identity=plan.identity
        )
        ComponentResolutionAuditStore(component, target).update(
            resolution.catalog_audit
        )
        ComponentLockStore(component).update(resolution.lock)
        # All fixture inputs are authored/reviewed test data. Record their normal
        # review marker before capturing the generation authority; do not waive it.
        review = record_project_authority_review(root)
        self.owner.assertEqual(review["state"], "current")
        self.config = ProjectConfigurationStore.discover(root)
        self.prepared = FilesystemLockedGenerationApplicationAdapter().prepare(
            GenerationPreparationRequest(
                component, target, selectors, (root / "flavors",)
            )
        )
        self.owner.assertEqual(self.prepared.boundary, self.project.root)
        self.snapshot = self.prepared.locked_authority_snapshot
        self.delegate = CodingCliSourceGenerator(environment=environment)
        self.cas_root = self.work / "candidate-cas"
        assets = admit_locked_authored_assets(
            self.snapshot, cas=FileSystemCAS(self.cas_root)
        )
        planning = FilesystemStandardProjectPlanningAdapter(
            coding_cli_selector=lambda: self.delegate.selection,
            model_selector=LockedComponentModelSelectionAdapter(
                pipeline_model="fixture-model"
            ),
        )
        self.execution = planning.plan(self.snapshot, assets=assets).execution_plan
        return self.snapshot, self.execution

    def require_current(self):
        self.snapshot.require_unchanged()
        current = ProjectConfigurationStore.discover(self.project.root)
        if (
            current is None
            or current.root != self.config.root
            or current.content_identity != self.config.content_identity
            or current.directory_binding != self.config.directory_binding
        ):
            raise AssertionError("original authored project configuration changed")

    def assemble(self, configuration, observer):
        original_factory = FilesystemStandardSourceGenerationAdapter.runner

        def capture(source_adapter, *args, **kwargs):
            if self.original_runner is not None:
                raise AssertionError("exactly one source runner must be assembled")
            runner, cache = original_factory(source_adapter, *args, **kwargs)
            self.original_runner = runner
            return _ObservedRunner(runner, self, observer), cache

        with mock.patch.object(
            FilesystemStandardSourceGenerationAdapter, "runner", capture
        ):
            self.adapter = assemble_filesystem_standard_rebuild_adapter(
                project=self.project,
                prepared=self.prepared,
                object_root=self.work / "objects",
                generated_source_cache_root=self.work / "generated-cache",
                source_cache_root=self.work / "source-cache",
                candidate_cas_root=self.cas_root,
                accepted_cas_root=self.work / "accepted-cas",
                checkpoint_root=self.work / "checkpoints",
                node_sdk_host=configuration,
                binding=self.binding,
                pipeline_model="fixture-model",
            )
        return self.adapter.runtime

    def generate(self, prepared, provider_contracts):
        if prepared is not self.active_node or self.original_calls:
            raise AssertionError(
                "one original call for the current prepared node required"
            )
        stage = self.work / ("authored-payload-" + str(self.attempts))
        self.attempts += 1
        stage.mkdir()
        runtime_fixture._write_authored_source_files(
            stage, prepared.recipe, provider_contracts, prepared.plan.component_revision
        )
        files = {
            path.relative_to(stage).as_posix(): path.read_text()
            for path in stage.rglob("*")
            if path.is_file()
        }
        # Locked assets belong to the original runner's CAS materializer. Never
        # replace that owner with a generated copy, even when bytes are identical.
        for asset in self.original_runner.assets_by_revision.get(
            prepared.plan.component_revision.uri, ()
        ):
            content = files.pop(asset.path).encode()
            self.owner.assertEqual(len(content), asset.blob.size)
            self.owner.assertEqual(
                "sha256:" + hashlib.sha256(content).hexdigest(), asset.blob.identity
            )
        self.child.set_files(files)
        self.original_calls += 1
        output = self.original_runner(prepared)
        self.owner.assertEqual(
            self.original_runner.cache_key_for_candidate(output.candidate),
            self.original_runner.planned_cache_key(prepared),
        )
        self.generated += 1
        self.last_output = output
        return output

    def execute(self, *, source_root, invalidation, budget):
        try:
            with (
                self.diagnostic_observer.observe()
                if self.diagnostic_observer is not None
                else nullcontext()
            ):
                result = self.adapter.rebuild(
                    FilesystemStandardRebuildRequest(
                        self.prepared,
                        source_root,
                        invalidation,
                        update_receipt=False,
                        max_parallelism=1,
                        budget=budget,
                    )
                )
        except Exception as failure:
            try:
                self.failure_observation = _bounded_failure_observation(
                    failure, self.adapter.runtime.lifecycle_ports.failure_diagnostics
                )
            except Exception:
                self.failure_observation = {"qualified": False, "state": "unknown"}
            raise
        finally:
            if self.diagnostic_observer is not None:
                try:
                    self.probe_observation = self.diagnostic_observer.snapshot()
                except Exception:
                    self.probe_observation = {
                        "qualified": False,
                        "instrumentation_active": True,
                        "state": "unknown",
                    }
        owner = self.owner
        lock = self.snapshot.authority.lock.identity
        expected_project = rebuild_project_authority_identity(
            validated_project_authority_identity(self.project.root), (lock,)
        )
        owner.assertEqual(result.project_revision_identity, expected_project)
        owner.assertEqual(result.receipt.project_revision_identity, expected_project)
        owner.assertEqual(result.receipt.project_id, self.project.definition.project_id)
        expected_invocation = canonical_identity(
            {
                "schema": "literate-ai/standard-in-process-invocation@1",
                "lifecycle_request_identity": result.lifecycle_request_identity.uri,
                "driver_identity": self.binding.driver.identity.uri,
                "policy_identity": self.binding.policy.identity.uri,
                "framework_distribution_identity": (
                    self.binding.distribution.identity.uri
                ),
                "toolchain_closure_identity": (
                    self.adapter.runtime.toolchain_closure.record.identity.uri
                ),
            }
        )
        owner.assertEqual(result.lifecycle_invocation_identity, expected_invocation)
        evidence = {item.kind: item.identity for item in result.receipt.evidence}
        owner.assertEqual(evidence["test-runner"], self.binding.driver.identity)
        owner.assertEqual(evidence["lifecycle-command"], expected_invocation)
        owner.assertEqual(
            evidence["lifecycle-request"], result.lifecycle_request_identity
        )
        finalized = result.finalized_receipt
        owner.assertEqual(finalized.receipt, result.receipt)
        owner.assertEqual(finalized.receipt_identity, result.receipt.identity)
        owner.assertEqual(finalized.component_lock_identities, (lock,))
        owner.assertEqual(
            finalized.lifecycle_request_identity, result.lifecycle_request_identity
        )
        owner.assertEqual(finalized.lifecycle_command_identity, expected_invocation)
        owner.assertIsNone(result.receipt_update)
        owner.assertEqual(self.generated, len(self.execution.generation_plans))
        owner.assertEqual(self.child.executions, self.generated)
        program = self.child.executable.read_bytes()
        owner.assertLessEqual(len(program), 65536)
        owner.assertEqual(
            "sha256:" + hashlib.sha256(program).hexdigest(), self.child.identity
        )
        self.evidence = {
            "schema": "literate-ai/authored-installed-sdk-rebuild-case@1",
            "project": expected_project.uri,
            "lock": lock.uri,
            "driver": self.binding.driver.identity.uri,
            "framework_distribution": self.binding.distribution.identity.uri,
            "invocation": expected_invocation.uri,
            "receipt": result.receipt.identity.uri,
            "finalized_receipt": finalized.identity.uri,
            "generated_nodes": self.generated,
            "fixture_child_executions": self.child.executions,
            "fixture_program_sha256": self.child.identity,
            "fixture_program_base64": base64.b64encode(program).decode(),
        }
        return result.execution


@unittest.skipUnless(
    sys.platform == "darwin"
    and os.environ.get("LITAI_NODE_SDK_REBUILD_PREFLIGHT") == "1",
    "explicit authored installed rebuild preflight required",
)
class AuthoredInstalledSDKRebuildTests(unittest.TestCase):
    def test_original_installed_adapter_rebuild_returns_bound_receipts(self):
        global REBUILD_EVIDENCE, REBUILD_ATTEMPT
        if REBUILD_EVIDENCE is not None:
            raise AssertionError("installed authored rebuild case cannot be replayed")
        setup = AuthoredSDKRebuildSetup(
            self, diagnostic_observer=getattr(self, "sdk_probe_observer", None)
        )
        try:
            runtime_fixture.CanonicalSDKRuntimeTests._exercise_authored_runtime(
                self, rebuild_setup=setup
            )
        finally:
            REBUILD_ATTEMPT = {
                "schema": "literate-ai/authored-installed-sdk-rebuild-attempt@1",
                "qualified": False,
                "completed": setup.evidence is not None,
                "fixture_program": setup.program_observation,
                "source_attempts": setup.attempts,
                "generated_nodes": setup.generated,
                "failure": setup.failure_observation,
                "diagnostic_only": setup.diagnostic_observer is not None,
                "probe_profile": setup.probe_observation,
            }
        self.assertIsNotNone(setup.evidence)
        REBUILD_EVIDENCE = setup.evidence
