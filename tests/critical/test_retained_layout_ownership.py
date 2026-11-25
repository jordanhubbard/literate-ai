"""Real initializer/control roles consumed by an actual acknowledged source move."""

from __future__ import annotations

import json
import os
import unittest
from contextlib import ExitStack, contextmanager
from unittest import mock

import tests.critical.test_retained_layout_finalization as fixtures
import tests.critical.test_retained_layout_recovery_data as recovery_fixtures
import tests.support.fixtures_test_retained_harness_receipts as initializer_fixtures
from literate_ai.adapters import retained_layout_ownership as ownership
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.retained_layout_partition import (
    capture_retained_layout_partition,
)
from literate_ai.contracts import (
    ProjectInitializationBaseline,
    ProjectInitializationBaselineFile,
)
from literate_ai.contracts.identity import (
    ContentIdentity,
    HashAlgorithm,
    canonical_json_bytes,
)
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget


@unittest.skipUnless(os.name == "posix", "actual POSIX source/control owner")
class RetainedLayoutOwnershipTests(unittest.TestCase):
    plan = fixtures.RetainedLayoutFinalizationTests.plan
    pool = fixtures.RetainedLayoutFinalizationTests.pool
    phase = fixtures.RetainedLayoutFinalizationTests.phase
    git = fixtures.RetainedLayoutFinalizationTests.git
    init_git = fixtures.RetainedLayoutFinalizationTests.init_git

    @classmethod
    def setUpClass(cls):
        with mock.patch.object(
            initializer_fixtures,
            "_origin",
            ownership.discover_installed_initialization_origin,
        ):
            fixtures.RetainedLayoutFinalizationTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.RetainedLayoutFinalizationTests.setUp(self)
        self.namespace_budget = RetainedCargoInputBudget(
            1024, 2048, 4 * 1024**2, 32 * 1024**2
        )

    def observe(self, phase, **kwargs):
        return phase.complete_partition(
            budget=self.namespace_budget,
            maximum_metadata_bytes=512 * 1024**2,
            **kwargs,
        )

    @contextmanager
    def inspecting(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            completed = False
            try:
                with self.phase(plan, pool) as phase:
                    yield phase
                    completed = True
            except ValueError as error:
                if completed and "source phase remains incomplete" in str(error):
                    return
                raise
            self.fail("inspection unexpectedly finalized an actual source phase")

    def test_actual_roles_cover_source_framework_controls_and_unknown_entries(self):
        (self.project / ".literate/unclaimed.py").write_bytes(
            b"unclaimed metadata neighbor\n"
        )
        (self.source / ".ignored-looking").write_bytes(b"source\n")
        (self.project / "unclaimed-empty").mkdir()
        with self.inspecting() as phase:
            with self.observe(phase) as owner:
                roles = dict(owner.roles)
                self.assertEqual(roles["literate.project.json"], "framework")
                self.assertEqual(
                    roles["components/legacy-project-wrapper/implementation/app.py"],
                    "source",
                )
                self.assertEqual(roles[".literate/unclaimed.py"], "unclaimed")
                self.assertEqual(roles["litai/layout.pending"], "control")
                self.assertIn("unclaimed", dict(owner.directories)["unclaimed-empty"])
                self.assertEqual(owner.census.tree.exclusions, ())
                owner.require_current()
            with self.assertRaisesRegex(ValueError, "owner ended"):
                owner.require_current()

    def test_canonical_role_calculation_needs_no_acquired_source_phase(self):
        unknown = self.project / ".literate/unclaimed.py"
        unknown.write_bytes(b"unknown stays unclaimed\n")
        before = sorted(self.project.rglob("*"))
        with (
            ExitStack() as providers,
            mock.patch.object(
                transaction,
                "acquire_retained_layout_control_roles",
                side_effect=AssertionError("control acquisition reached"),
            ),
            mock.patch.object(
                transaction,
                "plan_retained_layout_source_move",
                side_effect=AssertionError("source phase plan required"),
            ),
        ):
            framework, children, inputs, origin, provider = (
                ownership._initializer_role_inputs(
                    self.project,
                    self.source.parent.relative_to(self.project).as_posix(),
                    self.namespace_budget,
                    512 * 1024**2,
                    providers=providers,
                    provider_checkout=None,
                )
            )
            census = capture_retained_layout_partition(
                self.project,
                framework_files=tuple(sorted(framework)),
                budget=self.namespace_budget,
                maximum_metadata_bytes=512 * 1024**2,
            )
            roles, directories = ownership._classify_observed_roles(
                self.project,
                self.source.relative_to(self.project).as_posix(),
                census,
                framework,
                children,
                (),
                (),
            )
            self.assertEqual(dict(roles)["literate.project.json"], "framework")
            self.assertEqual(
                dict(roles)[
                    (self.source / "app.py").relative_to(self.project).as_posix()
                ],
                "source",
            )
            self.assertEqual(dict(roles)[".literate/unclaimed.py"], "unclaimed")
            self.assertIn("unclaimed", dict(directories)[".literate"])
            self.assertTrue(inputs)
            self.assertEqual(
                origin, ownership.discover_installed_initialization_origin()
            )
            self.assertIsNone(provider)
        self.assertEqual(sorted(self.project.rglob("*")), before)
        self.assertEqual(unknown.read_bytes(), b"unknown stays unclaimed\n")
        self.assertFalse((self.project / "litai/layout.pending").exists())
        self.assertFalse(self.destination.exists())

    def test_full_owner_is_journaled_and_spent_before_actual_source_effect(self):
        plan = self.plan()
        with self.pool(plan) as (pool, journal):
            with self.phase(plan, pool) as phase:
                with self.observe(phase) as owner:
                    identity = owner.identity.uri
                    result = phase.move_source()
                    self.assertEqual(result["state"], "source-moved-metadata-pending")
                    with self.assertRaisesRegex(ValueError, "spent"):
                        owner.require_current()
                phase.publish_metadata(self.metadata)
                phase.finalize_controls(self.retired)
            events = [
                event
                for event in journal.events
                if event["kind"] == "source-partition-observed"
            ]
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["data"]["partition_identity"], identity)
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertFalse(self.source.exists())

    def test_new_unclaimed_entry_invalidates_complete_owner(self):
        changed = False
        with self.inspecting() as phase:
            with self.assertRaises(ValueError):
                with self.observe(phase) as owner:
                    (self.project / ".literate/new-source.py").write_bytes(b"new\n")
                    changed = True
                    owner.require_current()
        self.assertTrue(changed)

    def forged_baseline_entry(self, relative, content=b"original user source\n"):
        import hashlib
        from dataclasses import replace

        source = self.project / relative
        self.assertFalse(source.exists())
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(content)
        path = self.project / ".literate/initialization-baseline.json"
        baseline = ProjectInitializationBaseline.from_dict(
            json.loads(path.read_bytes())
        )
        forged = ProjectInitializationBaselineFile(
            relative,
            source.stat().st_size,
            ContentIdentity(
                HashAlgorithm.SHA256, hashlib.sha256(source.read_bytes()).hexdigest()
            ),
        )
        baseline = replace(
            baseline,
            files=tuple(sorted((*baseline.files, forged), key=lambda item: item.path)),
        )
        path.write_bytes(canonical_json_bytes(baseline.to_dict()) + b"\n")
        return source

    def test_forged_baseline_cannot_claim_an_arbitrary_source_neighbor(self):
        source = self.forged_baseline_entry("unclaimed.py")
        with self.inspecting() as phase:
            with self.assertRaisesRegex(ValueError, "outside actual initializer roles"):
                with self.observe(phase):
                    self.fail("arbitrary record supplied an ownership grant")
        self.assertEqual(source.read_bytes(), b"original user source\n")

    def test_forged_baseline_cannot_claim_an_inactive_template_endpoint(self):
        source = self.forged_baseline_entry("flavors/os-windows/flavor.md")
        with self.inspecting() as phase:
            with self.assertRaisesRegex(ValueError, "outside actual initializer roles"):
                with self.observe(phase):
                    self.fail("inactive template record supplied an ownership grant")
        self.assertEqual(source.read_bytes(), b"original user source\n")

    def test_conversion_cannot_claim_a_starter_it_never_created(self):
        source = self.forged_baseline_entry("samples/hello-component/component.md")
        with self.inspecting() as phase:
            with self.assertRaisesRegex(ValueError, "outside actual initializer roles"):
                with self.observe(phase):
                    self.fail("conversion claimed an unproduced hello starter")
        self.assertEqual(source.read_bytes(), b"original user source\n")

    def test_current_manifest_cannot_legitimize_an_originally_inactive_endpoint(self):
        source = self.forged_baseline_entry("flavors/os-windows/flavor.md")
        path = self.project / "literate.project.json"
        manifest = json.loads(path.read_bytes())
        manifest["default_flavor_selectors"].append("+flavor://literate-ai/os-windows")
        path.write_bytes(canonical_json_bytes(manifest) + b"\n")
        with self.inspecting() as phase:
            with self.assertRaisesRegex(ValueError, "outside actual initializer roles"):
                with self.observe(phase):
                    self.fail("current selectors legitimized a forged original role")
        self.assertEqual(source.read_bytes(), b"original user source\n")

    def test_initializer_cannot_claim_an_unproduced_audit_target(self):
        source = self.forged_baseline_entry(
            "components/legacy-project-wrapper/component.resolution-audit.foreign.json"
        )
        with self.inspecting() as phase:
            with self.assertRaisesRegex(ValueError, "outside actual initializer roles"):
                with self.observe(phase):
                    self.fail("canonical foreign audit path supplied ownership")
        self.assertEqual(source.read_bytes(), b"original user source\n")

    def test_unavailable_historical_provider_refuses_without_source_effect(self):
        from dataclasses import replace

        path = self.project / ".literate/initialization-origin.json"
        origin = ownership.ProjectInitializationOrigin.from_dict(
            json.loads(path.read_bytes())
        )
        origin = replace(origin, git_revision="0" * 40)
        path.write_bytes(canonical_json_bytes(origin.to_dict()) + b"\n")
        path = self.project / ".literate/initialization-baseline.json"
        baseline = ProjectInitializationBaseline.from_dict(
            json.loads(path.read_bytes())
        )
        baseline = replace(baseline, origin_identity=origin.identity)
        path.write_bytes(canonical_json_bytes(baseline.to_dict()) + b"\n")
        with self.inspecting() as phase:
            with self.assertRaisesRegex(
                ValueError, "local provider objects are unavailable"
            ):
                with self.observe(phase):
                    self.fail("current catalog claimed a historical provider's roster")
        self.assertTrue((self.source / "app.py").is_file())

    def test_actual_provider_change_revokes_the_live_partition(self):
        from dataclasses import replace

        with self.inspecting() as phase:
            with self.assertRaisesRegex(ValueError, "initializer provider changed"):
                with self.observe(phase) as owner:
                    changed = replace(owner._provider_origin, git_revision="0" * 40)
                    with mock.patch.object(
                        ownership,
                        "discover_installed_initialization_origin",
                        return_value=changed,
                    ):
                        owner.require_current()
        self.assertTrue((self.source / "app.py").is_file())

    def test_original_selected_flavor_remains_framework_after_manifest_edit(self):
        path = self.project / "literate.project.json"
        manifest = json.loads(path.read_bytes())
        original_selector = initializer_fixtures.host_platform_selector()
        self.assertIn(original_selector, manifest["default_flavor_selectors"])
        manifest["default_flavor_selectors"] = [
            selector
            for selector in manifest["default_flavor_selectors"]
            if selector != original_selector
        ]
        path.write_bytes(canonical_json_bytes(manifest) + b"\n")
        relative = f"flavors/{original_selector.rsplit('/', 1)[-1]}/flavor.md"
        source = self.project / relative
        source.write_bytes(
            source.read_bytes() + b"\nCustom initialized Flavor notes.\n"
        )
        with self.inspecting() as phase:
            with self.observe(phase) as owner:
                self.assertEqual(dict(owner.roles)[relative], "framework")
        self.assertTrue(
            source.read_bytes().endswith(b"Custom initialized Flavor notes.\n")
        )

    def test_original_manifest_blob_must_match_its_baseline_identity(self):
        import base64

        path = self.project / ".literate/update-bases.json"
        bases = json.loads(path.read_bytes())
        baseline = ProjectInitializationBaseline.from_dict(
            json.loads(
                (self.project / ".literate/initialization-baseline.json").read_bytes()
            )
        )
        manifest = next(
            item for item in baseline.files if item.path == "literate.project.json"
        )
        bases["blobs"][manifest.identity.uri] = base64.b64encode(b"{}\n").decode(
            "ascii"
        )
        path.write_bytes(canonical_json_bytes(bases) + b"\n")
        with self.inspecting() as phase:
            with self.assertRaisesRegex(ValueError, "manifest bytes disagree"):
                with self.observe(phase):
                    self.fail("changed original manifest bytes supplied ownership")
        self.assertTrue((self.source / "app.py").is_file())

    def test_missing_original_manifest_blob_refuses_without_source_effect(self):
        path = self.project / ".literate/update-bases.json"
        bases = json.loads(path.read_bytes())
        baseline = ProjectInitializationBaseline.from_dict(
            json.loads(
                (self.project / ".literate/initialization-baseline.json").read_bytes()
            )
        )
        manifest = next(
            item for item in baseline.files if item.path == "literate.project.json"
        )
        del bases["blobs"][manifest.identity.uri]
        path.write_bytes(canonical_json_bytes(bases) + b"\n")
        with self.inspecting() as phase:
            with self.assertRaisesRegex(ValueError, "manifest bytes are missing"):
                with self.observe(phase):
                    self.fail("missing original selection supplied ownership")
        self.assertTrue((self.source / "app.py").is_file())

    def test_invalid_catalog_checkpoint_refuses_before_source_effect(self):
        path = self.project / ".literate/update-bases.json"
        bases = json.loads(path.read_bytes())
        bases["catalog"] = []
        path.write_bytes(canonical_json_bytes(bases) + b"\n")
        with self.inspecting() as phase:
            with self.assertRaisesRegex(ValueError, "inventories must be mappings"):
                with self.observe(phase):
                    self.fail("partial checkpoint parsing supplied ownership")
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_checkpoint_records_share_entry_budget_before_blob_decoding(self):
        from literate_ai.adapters import update_merge

        path = self.project / ".literate/update-bases.json"
        bases = json.loads(path.read_bytes())
        bases["sources"] = {
            f"components/import-{index}/component.md": "git:example.invalid/source"
            for index in range(self.namespace_budget.maximum_entries)
        }
        path.write_bytes(canonical_json_bytes(bases) + b"\n")
        with self.inspecting() as phase:
            with mock.patch.object(update_merge.base64, "b64decode") as decode:
                with self.assertRaisesRegex(ValueError, "entries exceed"):
                    with self.observe(phase):
                        self.fail("checkpoint records escaped the shared budget")
            decode.assert_not_called()
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())

    def test_alias_to_actual_control_is_not_unclaimed_source(self):
        with self.inspecting() as phase:
            (self.project / "control-alias").symlink_to("litai/layout.pending")
            with self.assertRaisesRegex(ValueError, "ownership roles"):
                with self.observe(phase):
                    self.fail("cross-role alias was accepted")

    def test_budget_failure_precedes_initializer_payload_observation(self):
        plan = self.plan()
        with self.pool(plan) as (pool, _):
            with self.assertRaisesRegex(ValueError, "source phase remains incomplete"):
                with self.phase(plan, pool) as phase:
                    with mock.patch.object(ownership, "_initializer_roles") as roles:
                        with self.assertRaises(ValueError):
                            with phase.complete_partition(
                                budget=RetainedCargoInputBudget(1, 2, 4, 4),
                                maximum_metadata_bytes=512 * 1024**2,
                            ):
                                self.fail("incomplete capture was accepted")
                        roles.assert_not_called()

    def test_actual_git_administration_is_control_without_directory_exclusion(self):
        self.init_git()
        with self.inspecting() as phase:
            with self.observe(phase) as owner:
                roles = dict(owner.roles)
                self.assertEqual(roles[".git/HEAD"], "control")
                self.assertEqual(roles[".git/config"], "control")
                self.assertEqual(roles[".gitignore"], "framework")
                self.assertIn(".git/objects", owner.census.tree.directories)
                self.assertEqual(owner.census.tree.exclusions, ())

    def test_registered_independent_child_remains_its_own_nonmoving_role(self):
        from literate_ai.adapters.conversion_authority import register_native_project
        from literate_ai.projects import ProjectConfigurationStore, load_project
        from tests.support.fixtures_test_retained_harness_receipts import (
            _adapter,
            _selectors,
        )

        child = self.project / ".literate/native-projects/child"
        child.mkdir(parents=True)
        _adapter().initialize(
            child,
            empty=True,
            flavor_selectors=_selectors(child),
            source_intelligence_provider="none",
        )
        register_native_project(load_project(self.project), child)
        context = ProjectConfigurationStore.context(child)
        self.assertEqual(context.root, child)
        self.assertEqual(context.framework_root, child / "litai")
        manifest = context.manifest_path.relative_to(self.project).as_posix()
        self.assertTrue(context.manifest_path.is_file())
        with self.inspecting() as phase:
            with self.observe(phase) as owner:
                self.assertEqual(
                    dict(owner.roles)[manifest],
                    "independent:.literate/native-projects/child",
                )
                self.assertEqual(
                    dict(owner.roles)[".literate/native-projects.json"], "framework"
                )
                owner.require_current()

    def test_portable_nested_manifest_requires_registered_independent_owner(self):
        from tests.support.fixtures_test_catalog_import import make_project

        child = make_project(self.project / "unclaimed-child", "nested")
        (child / "literate.project.json").rename(child / "LITERATE.PROJECT.JSON")
        with self.inspecting() as phase:
            with self.assertRaisesRegex(ValueError, "independent project candidate"):
                with self.observe(phase):
                    self.fail("portable manifest spelling hid an independent project")

    def test_registered_child_manifest_case_preserves_actual_independent_role(self):
        from literate_ai.adapters.conversion_authority import register_native_project
        from literate_ai.projects import ProjectConfigurationStore, load_project
        from tests.support.fixtures_test_project_agent_development_workflow import (
            _definition,
        )

        child = self.project / ".literate/native-projects/child"
        ProjectConfigurationStore(child).create(_definition(project_id="child"))
        register_native_project(load_project(self.project), child)
        manifest = child / "literate.project.json"
        manifest.rename(child / "LITERATE.PROJECT.JSON")
        if not manifest.is_file():
            self.skipTest("canonical manifest alias requires a case-insensitive volume")
        with self.inspecting() as phase:
            with self.observe(phase) as owner:
                self.assertEqual(
                    dict(owner.roles)[
                        ".literate/native-projects/child/LITERATE.PROJECT.JSON"
                    ],
                    "independent:.literate/native-projects/child",
                )

    def test_late_foreign_entry_after_partition_journal_refuses_source_effect(self):
        plan = self.plan()
        changed = False
        foreign = self.project / "late-unclaimed.py"
        with self.pool(plan) as (pool, journal):
            append = journal.append

            def changed_append(kind, data):
                nonlocal changed
                result = append(kind, data)
                if kind == "source-partition-observed":
                    foreign.write_bytes(b"concurrent input\n")
                    changed = True
                return result

            with self.assertRaises(ValueError):
                with self.phase(plan, pool) as phase:
                    with self.observe(phase):
                        with mock.patch.object(journal, "append", changed_append):
                            phase.move_source()
        self.assertTrue(changed)
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())
        self.assertEqual(foreign.read_bytes(), b"concurrent input\n")

    def test_roles_changed_during_discovery_do_not_adopt_a_later_namespace(self):
        discover = ownership._initializer_roles
        foreign = self.project / "late-discovery-input"
        changed = False

        def changed_discover(*args, **kwargs):
            nonlocal changed
            result = discover(*args, **kwargs)
            foreign.write_bytes(b"new original input\n")
            changed = True
            return result

        with self.inspecting() as phase:
            with mock.patch.object(ownership, "_initializer_roles", changed_discover):
                with self.assertRaisesRegex(ValueError, "namespace changed"):
                    with self.observe(phase):
                        self.fail("later namespace was adopted")
        self.assertTrue(changed)
        self.assertEqual(foreign.read_bytes(), b"new original input\n")

    def test_public_observation_fields_are_read_only_and_documents_detached(self):
        neighbor = self.project / "unclaimed.py"
        neighbor.write_bytes(b"user original input\n")
        plan = self.plan()
        with self.pool(plan) as (pool, journal):
            with self.phase(plan, pool) as phase:
                with self.observe(phase) as owner:
                    original = owner.document
                    changed_roles = tuple(
                        (name, "framework" if name == "unclaimed.py" else role)
                        for name, role in owner.roles
                    )
                    for name, value in (
                        ("roles", changed_roles),
                        ("directories", ()),
                        ("census", owner.census),
                    ):
                        with self.assertRaises(AttributeError):
                            setattr(owner, name, value)
                    detached = owner.document
                    detached["roles"] = changed_roles
                    self.assertEqual(owner.document, original)
                    phase.move_source()
                phase.publish_metadata(self.metadata)
                phase.finalize_controls(self.retired)
            event = next(
                e for e in journal.events if e["kind"] == "source-partition-observed"
            )
            recorded = json.loads(
                journal.read_payload(event["data"]["partition_payload_digest"])
            )
            self.assertEqual(dict(recorded["roles"])["unclaimed.py"], "unclaimed")
            self.assertEqual(recorded["identity"], original["identity"])
        self.assertEqual(neighbor.read_bytes(), b"user original input\n")

    def late_private_member(self, *, stages=False, joined=True, record=False):
        from contextlib import nullcontext

        plan = self.plan()
        foreign = (
            self.state
            / ("stages" if stages else "journal")
            / ("header.json" if record else "foreign-late")
        )
        before_effect = transaction._close_before_effect
        inventory = transaction._inventory
        armed = changed = False
        target = self.project if joined else self.source

        def arm(*args, **kwargs):
            nonlocal armed
            armed = True
            return before_effect(*args, **kwargs)

        def read_namespace(root, *args, **kwargs):
            nonlocal changed
            result = inventory(root, *args, **kwargs)
            if root == target and armed and not changed:
                foreign.write_bytes(b"new external member\n")
                changed = True
            return result

        with self.assertRaises(ValueError):
            with self.pool(plan) as (pool, _):
                with self.phase(plan, pool) as phase:
                    with self.observe(phase) if joined else nullcontext():
                        with (
                            mock.patch.object(transaction, "_close_before_effect", arm),
                            mock.patch.object(
                                transaction, "_inventory", read_namespace
                            ),
                        ):
                            phase.move_source()
        self.assertTrue(changed)
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())
        self.assertEqual(foreign.read_bytes(), b"new external member\n")

    def test_journal_member_after_final_project_inventory_refuses_move(self):
        self.late_private_member()

    def test_journal_record_after_final_project_inventory_refuses_move(self):
        self.late_private_member(record=True)

    def test_stage_member_after_final_project_inventory_refuses_move(self):
        self.late_private_member(stages=True)

    def test_original_source_only_final_inventory_closes_external_journal(self):
        self.late_private_member(joined=False)


@unittest.skipUnless(os.name == "posix", "actual joined source/recovery owners")
class JoinedOwnershipRecoveryTests(unittest.TestCase):
    plan = recovery_fixtures.RetainedLayoutDataRecoveryTests.plan
    pool = recovery_fixtures.RetainedLayoutDataRecoveryTests.pool
    reopened = recovery_fixtures.RetainedLayoutDataRecoveryTests.reopened
    proposal = recovery_fixtures.RetainedLayoutDataRecoveryTests.proposal
    acquire = recovery_fixtures.RetainedLayoutDataRecoveryTests.acquire
    interrupted = recovery_fixtures.RetainedLayoutDataRecoveryTests.interrupted
    owner = recovery_fixtures.RetainedLayoutDataRecoveryTests.owner
    apply = recovery_fixtures.RetainedLayoutDataRecoveryTests.apply
    assert_original = recovery_fixtures.RetainedLayoutDataRecoveryTests.assert_original
    git = recovery_fixtures.RetainedLayoutDataRecoveryTests.git
    init_git = recovery_fixtures.RetainedLayoutDataRecoveryTests.init_git

    @classmethod
    def setUpClass(cls):
        with mock.patch.object(
            initializer_fixtures,
            "_origin",
            ownership.discover_installed_initialization_origin,
        ):
            recovery_fixtures.RetainedLayoutDataRecoveryTests.setUpClass.__func__(cls)

    def setUp(self):
        recovery_fixtures.RetainedLayoutDataRecoveryTests.setUp(self)

    @contextmanager
    def phase(self, plan, pool, **overrides):
        with recovery_fixtures.RetainedLayoutDataRecoveryTests.phase(
            self, plan, pool, **overrides
        ) as phase:
            with phase.complete_partition(
                budget=RetainedCargoInputBudget(1024, 2048, 4 * 1024**2, 32 * 1024**2),
                maximum_metadata_bytes=512 * 1024**2,
            ):
                yield phase

    def test_interrupted_joined_move_restores_original_source_and_inode(self):
        from literate_ai.adapters import retained_layout_recovery_data as recovery

        self.interrupted()
        with self.owner() as (pool, _, roles):
            plan = recovery.plan_layout_data_recovery(pool, roles, self.recovery)
            self.assertEqual(plan.issues, ())
            result = self.apply(pool, roles, plan)
            self.assertEqual(result["state"], "original-data-restored-controls-pending")
        self.assert_original()
