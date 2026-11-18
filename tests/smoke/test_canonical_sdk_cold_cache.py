"""Cold durable source reuse with fresh native admission, never a model claim.

A fresh provider acceptance changes the SDK's receipt-bound recipe. The cold
cell therefore requires provider source reuse AND an honest SDK cache miss/new
SDK generation. It does not retag a cached SDK under a different receipt.
"""

import hashlib
import os
import shutil
import sys
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from literate_ai.adapters.cache import FileSystemSourceCache, SourceCacheResolver
from literate_ai.adapters.intelligence.standard import DisabledGenerationIndexer
from literate_ai.adapters.models import CodingCliSelection
from literate_ai.adapters.node_sdk_host import (
    LocalNodeSDKHostConfiguration,
    current_node_sdk_project_acceptance,
)
from literate_ai.adapters.standard_project import (
    PlannedStandardProject,
    StandardProjectExecutionRequest,
    assemble_filesystem_standard_project_runtime,
    compose_filesystem_standard_source_cache,
    project_locked_standard_toolchain_closure,
)
from literate_ai.contracts import (
    ContentIdentity,
    SourceCacheConfiguration,
    SourceCacheMode,
    SourceCacheTarget,
    SourceDerivationCacheKey,
    canonical_identity,
)
from literate_ai.contracts.executable_components import (
    ComponentChangeSurface,
    ComponentInvalidationDecision,
    SourceGenerationDisposition,
)
from literate_ai.contracts.generation_cache import (
    SourceCacheModelBinding,
    SourceCacheRootKind,
)
from literate_ai.security.policy import BuildAuthorization, SecurityProfile
from literate_ai.storage import FileSystemCAS
from tests.smoke import test_canonical_sdk_admission as admission
from tests.smoke.test_canonical_sdk_runtime import _authored_source
from tests.smoke.test_node_sdk_cross_language import with_provider
from tests.support.fixtures_test_component_generation_context import _budget


def _phase_invalidations(root_revision, nodes):
    # Validate BOTH requests before the seed lifecycle starts. Restoring source
    # retains authority and rebuilds/retests; it is not a new authority change.
    return {
        "seed": ComponentInvalidationDecision(
            "authored-sdk-seed",
            root_revision,
            ComponentChangeSurface.LOCAL_AUTHORITY,
            nodes,
            nodes,
            nodes,
        ),
        "cold": ComponentInvalidationDecision(
            "authored-sdk-cold",
            root_revision,
            ComponentChangeSurface.SOURCE_REPLACEMENT,
            (),
            nodes,
            nodes,
        ),
    }


class ColdCachePlanningTests(unittest.TestCase):
    def test_both_phase_decisions_are_valid_before_native_execution(self):
        root, provider = canonical_identity("root"), canonical_identity("provider")
        nodes = tuple(sorted((root, provider), key=lambda value: value.uri))
        decisions = _phase_invalidations(root, nodes)
        self.assertEqual(decisions["seed"].regenerate, nodes)
        self.assertEqual(decisions["cold"].regenerate, ())
        for decision in decisions.values():
            self.assertEqual(decision.rebuild, nodes)
            self.assertEqual(decision.retest, nodes)
            self.assertEqual(
                ComponentInvalidationDecision.from_dict(decision.to_dict()), decision
            )

    def test_empty_regeneration_still_refuses_an_authority_change(self):
        from literate_ai.contracts._validation import ContractValidationError

        root = canonical_identity("root")
        with self.assertRaisesRegex(ContractValidationError, "contradicts"):
            ComponentInvalidationDecision(
                "invalid-cold",
                root,
                ComponentChangeSurface.LOCAL_AUTHORITY,
                (),
                (root,),
                (root,),
            )


def _authorizer(phase, grants, phase_grants, ports_reference):
    # Each callback owns its phase and original ports, never the next loop frame.
    def authorize(request):
        now = ports_reference[0].clock()
        digest = canonical_identity(request.to_dict()).uri
        grant = BuildAuthorization(
            "cold-sdk-" + phase + "-" + str(len(grants)),
            digest,
            digest,
            request.effective_revision_digest,
            "fixture-operator",
            "exact isolated cold SDK verifier",
            SecurityProfile.CONSTRAINED,
            request.requested_privileges,
            now,
            now + timedelta(minutes=30),
        )
        grants.append(grant)
        phase_grants.append(request.builder_id)
        return grant

    return authorize


class _AuthoredCacheSource:
    """Test-only authored semantics; no real coding CLI/model cache namespace."""

    def __init__(self, execution, selection, providers, *, phase, ports):
        self.execution, self.selection, self.providers = execution, selection, providers
        self.phase, self.ports = phase, ports
        self.generated = []
        self.keys = {}
        self.planned = {}

    def planned_cache_key(self, prepared):
        request = prepared.request.request
        recipe = ContentIdentity.parse_uri(prepared.recipe.identity)
        key = SourceDerivationCacheKey(
            recipe_identity=recipe,
            execution_plan_identity=self.execution.identity,
            coding_cli_tool_binding_identity=ContentIdentity.parse_uri(
                self.selection.tool_binding_identity
            ),
            model_binding=SourceCacheModelBinding("authored-fixture", "no-model"),
            request_identity=canonical_identity(
                {"authored-sdk-runtime-request": request.identity.uri}
            ),
            source_semantics_identity=canonical_identity(
                {
                    "schema": "authored-sdk-cold-cache-semantics@1",
                    "recipe": recipe.uri,
                    "plan": prepared.plan.identity.uri,
                    "context": request.context_manifest_identity.uri,
                    "prompt": request.prompt_identity.uri,
                }
            ),
        )
        if prepared.recipe.node_sdk_providers:
            # The production deferred lookup must run inside fresh SDK admission.
            assert current_node_sdk_project_acceptance(self.ports) is not None
        self.planned[prepared.plan.component_revision] = key
        return key

    def cache_key_for_candidate(self, candidate):
        return self.keys[candidate.identity]

    def record_restored_cache_key(self, candidate, key):
        assert candidate.recipe_identity == key.recipe_identity
        self.keys[candidate.identity] = key

    def __call__(self, prepared):
        revision = prepared.plan.component_revision
        if self.phase == "cold":
            assert revision == self.execution.root_revision, "provider cache was missed"
        key = self.planned_cache_key(prepared)
        output = _authored_source(
            prepared, self.execution.root_revision, self.providers
        )
        assert (
            output.candidate.planned_coding_cli_request_identity == key.request_identity
        )
        self.keys[output.candidate.identity] = key
        self.generated.append(revision)
        print(
            "Cold SDK source: " + self.phase + " generated " + revision.uri, flush=True
        )
        return output


@unittest.skipUnless(
    sys.platform == "darwin"
    and os.environ.get("LITERATE_TYPESCRIPT_SDK")
    and shutil.which("node"),
    "macOS native-observer cell requires selected Node/npm/TypeScript",
)
class CanonicalSDKColdCacheTests(unittest.TestCase):
    def test_fresh_runtime_restores_provider_and_regenerates_receipt_bound_sdk(self):
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
            providers = {
                c.component_revision: c
                for c in closure.contracts
                if c.component_revision != execution.root_revision
            }
            self.assertEqual(len(providers), 1)
            revisions = {
                n.revision.identity: n.revision for n in snapshot.authority.lock.nodes
            }
            root_oracle = admission.CanonicalSDKAdmissionTests._root_oracle(
                self, snapshot, consumer
            )
            oracles = {
                revision.uri: admission.CanonicalSDKAdmissionTests._provider_oracle(
                    self, revisions[revision], contract
                )
                for revision, contract in providers.items()
            }
            interpreter = Path(sys.executable).resolve(strict=True)
            selection = CodingCliSelection(
                "codex",
                str(interpreter),
                "sha256:" + hashlib.sha256(interpreter.read_bytes()).hexdigest(),
            )
            nodes = tuple(p.component_revision for p in execution.generation_plans)
            invalidations = _phase_invalidations(execution.root_revision, nodes)
            target = SourceCacheTarget(
                target_id="cold-sdk",
                root_kind=SourceCacheRootKind.OPERATOR_BOUND,
                root_reference="cold-sdk",
            )
            configuration = SourceCacheConfiguration(
                mode=SourceCacheMode.READ_WRITE,
                targets=(target,),
                write_target_id=target.target_id,
                require_unique=True,
            )
            observations, retained_ports, grants = [], [], []
            for phase in ("seed", "cold"):
                phase_root = root / phase
                print("Cold SDK runtime: enter " + phase, flush=True)
                phase_grants = []
                ports_reference = []
                authorize = _authorizer(phase, grants, phase_grants, ports_reference)
                host = LocalNodeSDKHostConfiguration(
                    snapshot=snapshot,
                    expected_execution=execution,
                    provider_oracles=oracles,
                    root_oracle=root_oracle,
                    authorize_verifier=authorize,
                    require_current=snapshot.require_unchanged,
                    environment=environment,
                )
                # New registry, ports, object root, host binding and source resolver.
                runtime = assemble_filesystem_standard_project_runtime(
                    generator=lambda _: self.fail("uncomposed generator used"),
                    object_root=phase_root / "objects",
                    toolchain_closure=closure,
                    node_sdk_host=host,
                )
                ports_reference.append(runtime.lifecycle_ports)
                source = _AuthoredCacheSource(
                    execution,
                    selection,
                    providers,
                    phase=phase,
                    ports=runtime.lifecycle_ports,
                )
                resolver = SourceCacheResolver(
                    configuration,
                    {
                        target.target_id: FileSystemSourceCache(
                            target.target_id, root / "cache"
                        )
                    },
                )
                runtime = compose_filesystem_standard_source_cache(
                    runtime,
                    generator=source,
                    resolver=resolver,
                    caller_cas=FileSystemCAS(root / "cas"),
                    indexer=DisabledGenerationIndexer(runtime.source_trees),
                )
                self.assertTrue(runtime.durable_source_cache_configured)
                for old in retained_ports:
                    self.assertIsNot(runtime.lifecycle_ports, old)
                    self.assertIsNot(runtime.source_trees, old.source_trees)
                result = runtime.execute(
                    snapshot,
                    StandardProjectExecutionRequest(
                        PlannedStandardProject(selection, execution),
                        phase_root / "workspaces",
                        invalidations[phase],
                        max_parallelism=1,
                        budget=_budget(),
                        fresh_source=phase == "seed",
                    ),
                )
                self.assertTrue(
                    result.lifecycle.successful,
                    (
                        [
                            (n.failure_code, n.failure_evidence)
                            for n in result.lifecycle.node_results
                        ],
                        runtime.lifecycle_ports.failure_diagnostics,
                    ),
                )
                by_revision = {
                    n.component_revision: n for n in result.lifecycle.node_results
                }
                self.assertIn("local-node-sdk-project-verifier@1", phase_grants)
                self.assertIsNone(
                    current_node_sdk_project_acceptance(runtime.lifecycle_ports)
                )
                runtime._require_sdk_host(snapshot)
                observations.append((source, by_revision))
                retained_ports.append(runtime.lifecycle_ports)
                if phase == "seed":
                    self.assertEqual(set(source.generated), set(nodes))
                    self.assertTrue(
                        all(
                            n.source_cache_publication_identity
                            for n in by_revision.values()
                        )
                    )
                    phase_root.rename(root / "retired-seed")
                    self.assertFalse(phase_root.exists())
                else:
                    self.assertEqual(source.generated, [execution.root_revision])
                    self.assertEqual(
                        by_revision[execution.root_revision].disposition,
                        SourceGenerationDisposition.GENERATED,
                    )
                    self.assertFalse((root / "seed").exists())
                    for revision in providers:
                        self.assertEqual(
                            by_revision[revision].disposition,
                            SourceGenerationDisposition.REUSED,
                        )
                        restored = runtime.source_trees.resolve(
                            by_revision[revision].source_output.candidate.tree_identity
                        )
                        self.assertTrue(
                            restored.is_relative_to(phase_root / "workspaces")
                        )
                        self.assertTrue(restored.is_dir())
                        old = observations[0][1][revision]
                        self.assertNotEqual(
                            old.source_output.identity,
                            by_revision[revision].source_output.identity,
                        )
                        self.assertNotEqual(
                            old.acceptance_identity,
                            by_revision[revision].acceptance_identity,
                        )
                        self.assertEqual(
                            old.source_output.candidate.tree_identity,
                            by_revision[revision].source_output.candidate.tree_identity,
                        )
                    old_key = observations[0][0].planned[execution.root_revision]
                    new_key = source.planned[execution.root_revision]
                    self.assertNotEqual(
                        old_key.recipe_identity, new_key.recipe_identity
                    )
                    self.assertNotEqual(
                        old_key.accepted_source_lookup, new_key.accepted_source_lookup
                    )
                print("Cold SDK runtime: " + phase + " returned accepted", flush=True)
            self.assertEqual(len({g.authorization_id for g in grants}), len(grants))
