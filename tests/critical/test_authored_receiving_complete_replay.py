"""Develop complete original capture on a real reviewed two-library project.

The Codex-shaped child is a deterministic source fixture, not a model. Framework
distribution observation is explicit fixture data. Project review, host target,
source generation custody, Standard execution and private oracle checks use their
original owners. No receiving, SDK or installed acceptance is implied by setup.
"""

import hashlib
import json
import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import qualification as qualification_adapter
from literate_ai.adapters.authored_qualification_planning import (
    FilesystemAuthoredQualificationPlanner,
)
from literate_ai.adapters.authored_qualification_publication import (
    apply_authored_qualification,
)
from literate_ai.adapters.component_acceptance import load_versioned_library_acceptance
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
    InstalledFrameworkDistribution,
    InstalledFrameworkDistributionMember,
    ResolvedStandardProjectLifecycleDriver,
)
from literate_ai.adapters.standard_project import (
    FilesystemStandardProjectPlanningAdapter,
    FilesystemStandardSourceGenerationAdapter,
    project_locked_standard_toolchain_closure,
)
from literate_ai.application.generation_preparation import GenerationPreparationRequest
from literate_ai.contracts import (
    ProjectTestReceiptPolicy,
    RepositoryParentSelection,
    StandardProjectLifecycleDriver,
    load_current_standard_lifecycle_policy,
)
from literate_ai.contracts.authored_qualification_profiles import (
    AuthoredQualificationOracleSelection,
    AuthoredQualificationProfile,
)
from literate_ai.contracts.authoring_markdown import (
    parse_authoring_markdown,
    render_authoring_markdown,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore
from tests.critical.test_authored_graph_acceptance import HARNESS
from tests.support.authored_coding_cli import AuthoredCodingCLI
from tests.support.fixtures_test_component_lock_planning import _component_document
from tests.support.fixtures_test_locked_generation_authority import _write_lock
from tests.support.host_platform import host_os_family
from tests.support.standard_source_evidence_fixture import write_strict_source_evidence


class _SourceFilesRunner:
    """Supply files, then return the one original runner's unchanged output."""

    def __init__(self, original, fixture):
        self.original = original
        self.fixture = fixture

    def __getattr__(self, name):
        return getattr(self.original, name)

    def __call__(self, node):
        fixture = self.fixture
        recipe = node.recipe
        surface = recipe.library_import_surface
        fixture.assertIsNotNone(surface)
        capability = surface.capabilities[0]
        module_path = "source/" + capability.module.replace(".", "/") + ".py"
        if recipe.library_dependencies:
            dependency = recipe.library_dependencies[0]
            imported = dependency.import_surface.capability(dependency.capability)
            implementation = (
                f"from {imported.module} import {imported.symbols[0]}"
                " as provider_value\n"
                f"def {capability.symbols[0]}(argument):\n"
                " return provider_value(argument)\n"
            )
        else:
            implementation = (
                f"def {capability.symbols[0]}(argument):\n return argument\n"
            )
        stage = fixture.work / ("payload-" + str(fixture.generated))
        stage.mkdir()
        target = stage / module_path
        target.parent.mkdir(parents=True)
        target.write_text(implementation)
        adapter = (
            "import json,pathlib,sys\n"
            "p=pathlib.Path(__file__).resolve().parent\n"
            "if p.name=='tests': p=p.parent\n"
            "sys.path.insert(0,str(p))\n"
            f"from {capability.module} import {capability.symbols[0]} as value\n"
            "if '--litai-test' in sys.argv:\n"
            " cases=[]\n"
            " for category in ('example','boundary','invariant'):\n"
            "  argument={'component':'generated-'+category}\n"
            "  cases.append({'case_id':'fixture-'+category,'outcome':"
            "'passed' if value(argument)==argument else 'failed'})\n"
            " print(json.dumps({'schema':'literate-ai/generated-test-results@1',"
            "'cases':cases}))\n"
            "else:\n print(json.dumps(value({'component':'smoke'})))\n"
        )
        for relative in ("source/main.py", "source/tests/litai_test.py"):
            path = stage / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(adapter)
        write_strict_source_evidence(
            stage, recipe=recipe, component_name=recipe.application_id
        )
        fixture.child.set_files(
            {
                path.relative_to(stage).as_posix(): path.read_text()
                for path in stage.rglob("*")
                if path.is_file()
            }
        )
        planned = self.original.planned_cache_key(node)
        result = self.original(node)
        fixture.assertEqual(
            self.original.cache_key_for_candidate(result.candidate), planned
        )
        fixture.generated += 1
        return result


@unittest.skipUnless(os.name == "posix", "requires deterministic POSIX fixture CLI")
class CompleteAuthoredReceivingReplayTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.work = Path(temporary.name).resolve(strict=True)
        self.root = self.work / "project"
        self.child = AuthoredCodingCLI(self.work / "fixture-cli")
        self.generated = 0
        environment = {
            "PATH": str(self.child.root) + os.pathsep + os.environ["PATH"],
            "CODING_CLI": "codex",
            "LITAI_CODING_PROVIDER": "coding-cli",
            "LITAI_CONFIG_DIR": str(self.work / "private-config"),
            "LITAI_MCP_TRANSPORT": "off",
        }
        for name in ("TMPDIR", "LITAI_REQUIRE_PINNED_PIP_WHEEL"):
            if name in os.environ:
                environment[name] = os.environ[name]
        self.enterContext(patch.dict(os.environ, environment, clear=True))
        initialize_project(
            self.root,
            project_id="coherent-authored-replay",
            flavor_selectors=("+" + host_os_family(), "+python"),
            parent_selection=RepositoryParentSelection.root(),
            source_intelligence_provider="none",
            empty=True,
            bootstrap_tools=False,
        )
        context = ProjectConfigurationStore.context(self.root)
        framework = context.framework_root
        for name in ("greeting", "provider"):
            component = framework / "components" / name
            component.mkdir(parents=True)
            document, _body = parse_authoring_markdown(
                _component_document().encode(), source="authored fixture"
            )
            document.update(
                kind="library",
                entrypoints=[],
                acceptance_contracts=[],
                workflow_definition="workflows/sample-host.md",
                routing_policy="routing/sample-host.json",
                authoring_inputs=[
                    {
                        "kind": "specification-to-source-skill",
                        "uri": (
                            "skills/specification-to-source/"
                            "portable-application-implementation/SKILL.md"
                        ),
                        "pin": None,
                    }
                ],
                provides=[
                    {
                        "name": name + ".value",
                        "version": "1.0.0",
                        "interface": {"uri": "interfaces/value.md", "pin": None},
                    }
                ],
            )
            if name == "greeting":
                document["requires"] = [
                    {
                        "requirement_id": "provider",
                        "capability": "provider.value",
                        "version_range": ">=1,<2",
                        "dependency_kind": "generation",
                        "optional": False,
                        "constraints": [],
                    },
                    {
                        "requirement_id": "provider-artifact",
                        "capability": "provider.value",
                        "version_range": ">=1,<2",
                        "dependency_kind": "build",
                        "optional": False,
                        "constraints": [],
                    },
                ]
            (component / "component.md").write_bytes(
                render_authoring_markdown(
                    document, "A library returning its input mapping unchanged.\n"
                )
            )
            (component / "interfaces").mkdir()
            (component / "interfaces/value.md").write_text(
                "# Value\n\nThe library SHALL return the supplied mapping unchanged.\n"
            )
            (component / "specs").mkdir()
            (component / "specs/spec.md").write_text(
                "# Identity library\n\n### Requirement: Preserve the input mapping\n\n"
                "The library SHALL return its supplied mapping unchanged.\n\n"
                "#### Scenario: Mapping value\n\n- **WHEN** value receives a mapping\n"
                "- **THEN** it returns that mapping without changing any field\n"
            )
        distribution = InstalledFrameworkDistribution(
            "literate-ai",
            "1.4.0",
            (
                InstalledFrameworkDistributionMember(
                    "literate_ai/__init__.py", 1, "sha256:" + "a" * 64
                ),
            ),
        )
        policy = load_current_standard_lifecycle_policy()
        driver = StandardProjectLifecycleDriver(distribution.identity, policy.identity)
        self.binding = ResolvedStandardProjectLifecycleDriver(
            driver, distribution, policy, lambda: distribution, lambda: policy
        )
        store = ProjectConfigurationStore(self.root)
        snapshot = store.read()
        store.update(
            snapshot,
            replace(
                snapshot.definition,
                lifecycle_driver=driver,
                test_receipt_policy=ProjectTestReceiptPolicy(
                    policy.policy_id,
                    policy.policy_version,
                    driver.identity,
                    tuple(sorted(policy.required_evidence_kinds)),
                    policy.minimum_test_count,
                ),
            ),
        )
        component = framework / "components/greeting"
        target = host_os_family() + "-host"
        # These choices are already declared as project defaults. Repeating a
        # selector that changes no slot correctly fails the original planner.
        selectors = ()
        lock = _write_lock(
            component, framework / "flavors", target=target, selectors=selectors
        )
        self.selection = GenerationPreparationRequest(
            component, target, selectors, (framework / "flavors",)
        )
        prepared = FilesystemLockedGenerationApplicationAdapter().prepare(
            self.selection
        )
        self.delegate = CodingCliSourceGenerator(environment=dict(os.environ))
        planned = FilesystemStandardProjectPlanningAdapter(
            coding_cli_selector=lambda: self.delegate.selection,
            model_selector=LockedComponentModelSelectionAdapter(
                pipeline_model="fixture-model"
            ),
        ).plan(prepared.locked_authority_snapshot)
        closure = project_locked_standard_toolchain_closure(
            prepared.locked_authority_snapshot, planned.execution_plan
        )
        oracle_root = framework / "verification/acceptance/examples"
        oracle_root.mkdir(parents=True)
        (oracle_root / "harness.py").write_bytes(HARNESS)
        selections = []
        by_revision = {c.component_revision: c for c in closure.contracts}
        for node in sorted(lock.nodes, key=lambda item: item.revision.coordinate.uri):
            coordinate = node.revision.coordinate
            surface = by_revision[node.revision.identity].library_import_surface
            self.assertIsNotNone(surface)
            record = {
                "schema": "literate-ai/library-acceptance-oracle@1",
                "component": coordinate.name,
                "specification_set_identity": (
                    node.revision.specification_set_identity.uri
                ),
                "public_interface_identities": sorted(
                    item.identity.uri for item in node.revision.public_interfaces
                ),
                "import_surface_identity": surface.identity.uri,
                "language": "python",
                "harness": "harness.py",
                "harness_identity": "sha256:" + hashlib.sha256(HARNESS).hexdigest(),
                "cases": [
                    {
                        "case_id": "independent-mapping",
                        "capability": surface.capabilities[0].capability,
                        "arguments": [{"component": "private-case-7613"}],
                        "expected_result": {"component": "private-case-7613"},
                    }
                ],
            }
            path = oracle_root / (coordinate.name + ".json")
            path.write_bytes(canonical_json_bytes(record))
            oracle = load_versioned_library_acceptance(path, coordinate.name)
            selections.append(
                AuthoredQualificationOracleSelection(coordinate, oracle.identity)
            )
        profile = AuthoredQualificationProfile("authored-graph@1", tuple(selections))
        (framework / "qualification.json").write_bytes(
            canonical_json_bytes(profile.to_dict())
        )
        review = record_project_authority_review(self.root)
        self.assertEqual(review["state"], "current")
        self.current = FilesystemAuthoredQualificationPlanner(
            reviewer=validated_project_authority_identity,
            binding_resolver=lambda _driver: self.binding,
            coding_selector=lambda: self.delegate.selection,
        ).plan(self.root, self.selection, pipeline_model="fixture-model")

    def test_original_publication_captures_both_complete_clean_runs(self):
        original = FilesystemStandardSourceGenerationAdapter.runner
        original_assembler = (
            qualification_adapter.assemble_filesystem_standard_rebuild_adapter
        )
        adapters = []

        def assemble(adapter, *arguments, **options):
            runner, cache = original(adapter, *arguments, **options)
            return _SourceFilesRunner(runner, self), cache

        def observe_runtime(**arguments):
            adapter = original_assembler(**arguments)
            adapters.append(adapter)
            return adapter

        scratch = self.work / "scratch"
        scratch.mkdir()
        with (
            patch.object(FilesystemStandardSourceGenerationAdapter, "runner", assemble),
            patch.object(
                qualification_adapter,
                "assemble_filesystem_standard_rebuild_adapter",
                observe_runtime,
            ),
        ):
            try:
                published = apply_authored_qualification(
                    self.current,
                    self.selection,
                    acknowledged_plan=self.current.plan.identity,
                    allow_host_execution=True,
                    scratch_parent=scratch,
                    max_parallelism=1,
                )
            except Exception as failure:
                # Observe original diagnostics without changing the failure,
                # runtime owners, outputs or acceptance decisions.
                observation = {
                    "generated": self.generated,
                    "child_calls": self.child.executions,
                    "runtime_failures": [
                        adapter.runtime.lifecycle_ports.failure_diagnostics
                        for adapter in adapters
                    ],
                }
                failure.add_note(json.dumps(observation, default=str)[:16384])
                raise
        self.assertEqual(published.reference.plan_identity, self.current.plan.identity)
        self.assertEqual(self.generated, 4)
        self.assertEqual(self.child.executions, 4)
        base = (self.root / published.reference_path).parent
        intent = json.loads((base / "intent.json").read_bytes())
        retired = json.loads((base / "retirement.json").read_bytes())
        run = Path(intent["scratch_root"])
        self.assertEqual(
            canonical_identity(intent), published.reference.intent_identity
        )
        self.assertEqual(retired["attempt"], published.reference.attempt)
        self.assertEqual(retired["scratch_root"], str(run))
        self.assertEqual(
            retired["intent_identity"], published.reference.intent_identity.to_dict()
        )
        self.assertEqual(run.parent.parent, scratch)
        self.assertFalse(run.exists())
        self.assertEqual(list(scratch.iterdir()), [run.parent])
        self.assertTrue(run.parent.is_dir())
        self.assertFalse(list(run.parent.iterdir()))
