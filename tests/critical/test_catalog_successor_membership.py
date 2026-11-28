"""A catalog-created parent later receives exact initialized framework siblings."""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_catalog_finalization as finalization
from literate_ai.adapters import project_layout_catalog_renewal as catalog_renewal
from literate_ai.adapters import project_layout_catalog_successor as successor
from literate_ai.adapters import project_layout_continuation as catalog
from literate_ai.adapters import project_layout_framework_finalization as frame_close
from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_renewal as frame_renewal
from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters.component_lock_planning import FilesystemComponentLockPlanner
from literate_ai.adapters.project_layout_lease import (
    ProjectLayoutLeaseError,
    current_layout_lease,
)
from literate_ai.adapters.project_layout_migration import (
    apply_legacy_layout_migration,
    plan_legacy_layout_migration,
    recover_legacy_layout_migration,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_mixed_component_channels as support
from tests.critical import test_project_layout_public_producer_renewal as public_cli


class CatalogSuccessorMembershipTests(unittest.TestCase):
    def fixture(self, *, with_peer_lock=True, import_flavor=False):
        helper = support.MixedComponentChannelTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, original, inodes = helper.fixture(
            shared_parent=True,
            with_peer_lock=with_peer_lock,
            import_flavor=import_flavor,
        )
        self.assertFalse((project.root / "litai/samples").exists())
        plan = plan_legacy_layout_migration(
            project.root, (), place_forward_skills=False, place_imported_catalogs=True
        )
        self.assertTrue(plan["applicable"], plan["blocked_references"])
        apply_legacy_layout_migration(
            project.root,
            plan["plan_identity"],
            acknowledge=True,
            references=(),
            place_forward_skills=False,
            place_imported_catalogs=True,
        )
        _, intent = catalog._decode_intent(project.root, plan["plan_identity"])
        self.assertIn("litai/samples", intent["new_directories"])
        public, selected = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        self.assertTrue(public["applicable"], public["required_owners"])
        with ProjectConfigurationStore.layout_lock(project.root):
            framework.apply_framework_authority(selected, public["plan_identity"])
        return project, original, inodes, plan, public

    def finalize(self, project, plan, public, *, renew_peer=True):
        with ProjectConfigurationStore.layout_lock(project.root):
            snapshot = ProjectConfigurationStore(project.root).read()
            roots = tuple(
                project.root / path for path in snapshot.definition.flavor_roots
            )
            prepared = operations.prepare_component_lock(
                project.root / "litai/samples/hello-component",
                target="macos-host",
                flavors=(),
                flavor_roots=roots,
                planner=FilesystemComponentLockPlanner(),
            )
            self.assertTrue(
                frame_renewal.renew_placed_framework_component(
                    project.root,
                    public["plan_identity"],
                    prepared=prepared,
                    layout_lease=current_layout_lease(project.root),
                )["current"]
            )
            if renew_peer:
                prepared = operations.prepare_component_lock(
                    project.root / "litai/samples/peer",
                    target="macos-host",
                    flavors=(),
                    flavor_roots=roots,
                    planner=FilesystemComponentLockPlanner(),
                )
                self.assertTrue(
                    catalog_renewal.renew_placed_catalog_component(
                        project.root,
                        plan["plan_identity"],
                        prepared=prepared,
                        layout_lease=current_layout_lease(project.root),
                        successor_plan_identity=public["plan_identity"],
                    )["current"]
                )
            self.assertTrue(
                frame_close.finalize_framework_components(
                    project.root, public["plan_identity"]
                )["components_finalized"]
            )
            result = finalization.finalize_catalog_components(
                project.root,
                plan["plan_identity"],
                successor_plan_identity=public["plan_identity"],
            )
            self.assertTrue(result["components_finalized"])

    def test_exact_framework_sibling_closes_then_recovers_original_inodes(self):
        project, original, inodes, plan, public = self.fixture()
        self.finalize(project, plan, public)
        with ProjectConfigurationStore.layout_lock(project.root):
            framework.recover_framework_authority(project.root, public["plan_identity"])
        recover_legacy_layout_migration(
            project.root,
            plan["plan_identity"],
            acknowledge=True,
            successor_plan_identity=public["plan_identity"],
        )
        for name, content in original.items():
            self.assertEqual((project.root / name).read_bytes(), content)
            self.assertEqual((project.root / name).stat().st_ino, inodes[name])

    def test_default_stays_strict_and_unknown_sibling_or_descendant_is_preserved(self):
        project, _, _, plan, public = self.fixture()
        parent, intent = catalog._decode_intent(project.root, plan["plan_identity"])
        with ProjectConfigurationStore.layout_lock(project.root):
            lease = current_layout_lease(project.root)
            binding = successor.observe_catalog_successor(
                project.root, parent, intent, lease, None, public["plan_identity"]
            )
            with self.assertRaisesRegex(ProjectLayoutPlanError, "unrelated content"):
                catalog._current(project.root, parent, intent, None)
            for coordinate in (
                "litai/samples/foreign.txt",
                "litai/samples/hello-component/foreign.txt",
            ):
                with self.subTest(coordinate=coordinate):
                    foreign = project.root / coordinate
                    foreign.write_bytes(b"owned negative fixture")
                    inode = foreign.stat().st_ino
                    try:
                        with self.assertRaises(ProjectLayoutPlanError):
                            catalog._current(
                                project.root,
                                parent,
                                intent,
                                None,
                                lease=lease,
                                successor=binding,
                            )
                        self.assertEqual(
                            foreign.read_bytes(), b"owned negative fixture"
                        )
                        self.assertEqual(foreign.stat().st_ino, inode)
                    finally:
                        foreign.unlink()
            catalog._current(
                project.root, parent, intent, None, lease=lease, successor=binding
            )

    def test_foreign_member_observer_is_refused_before_invocation_and_lease_expires(
        self,
    ):
        project, _, _, plan, public = self.fixture()
        parent, intent = catalog._decode_intent(project.root, plan["plan_identity"])
        with ProjectConfigurationStore.layout_lock(project.root):
            lease = current_layout_lease(project.root)
            binding = successor.observe_catalog_successor(
                project.root, parent, intent, lease, None, public["plan_identity"]
            )
            with mock.patch.object(
                successor, "require_catalog_successor_members"
            ) as foreign:
                with self.assertRaises(ProjectLayoutPlanError):
                    catalog._current(
                        project.root,
                        parent,
                        intent,
                        None,
                        lease=lease,
                        successor=binding,
                    )
                foreign.assert_not_called()
            with self.assertRaisesRegex(ProjectLayoutPlanError, "already bound"):
                catalog._install_successor_directories(
                    successor,
                    successor.require_catalog_successor_members,
                    successor._bindings,
                )
        with self.assertRaises(ProjectLayoutLeaseError):
            catalog._current(
                project.root, parent, intent, None, lease=lease, successor=binding
            )

    def test_changed_private_census_code_or_defaults_refuses_before_use(self):
        function = catalog._guard_directories
        cells = dict(
            zip(function.__code__.co_freevars, function.__closure__, strict=True)
        )
        census = cells["census"].cell_contents

        def foreign(root, journal, intent, members):
            raise AssertionError("foreign census must never run")

        for attribute, value in (
            ("__code__", foreign.__code__),
            ("__defaults__", (("foreign",),)),
            ("__kwdefaults__", {"foreign": None}),
        ):
            with self.subTest(attribute=attribute):
                original = getattr(census, attribute)
                try:
                    setattr(census, attribute, value)
                    with self.assertRaisesRegex(
                        ProjectLayoutPlanError, "census/helper changed"
                    ):
                        catalog._guard_directories(None, None, None)
                finally:
                    setattr(census, attribute, original)

    def test_changed_private_member_dispatcher_refuses_before_foreign_census(self):
        function = catalog._guard_directories
        cells = dict(
            zip(function.__code__.co_freevars, function.__closure__, strict=True)
        )
        dispatcher = cells["members"].cell_contents
        # Compile matching closure shape; the foreign body would grant a member
        # without a successor proof if it were ever invoked.
        names = dispatcher.__code__.co_freevars
        body = "def outer():\n"
        body += "".join(f"    {name} = None\n" for name in names)
        body += "    def foreign(*args, **kwargs):\n"
        body += "        _ = (" + ",".join(names) + ",)\n"
        body += "        raise AssertionError('foreign member dispatcher invoked')\n"
        body += "    return foreign\n"
        namespace = {}
        exec(body, namespace)
        original = dispatcher.__code__
        try:
            dispatcher.__code__ = namespace["outer"]().__code__
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "census/helper changed"
            ):
                catalog._guard_directories(None, None, None, successor={})
        finally:
            dispatcher.__code__ = original

    def test_replaced_recovery_query_refuses_before_foreign_callback(self):
        with mock.patch.object(catalog, "_successor_directory_query") as foreign:
            with self.assertRaisesRegex(ProjectLayoutPlanError, "query changed"):
                catalog.recover_catalog_continuation(
                    None,
                    "sha256:" + "0" * 64,
                    successor_plan_identity="sha256:" + "1" * 64,
                )
            foreign.assert_not_called()

    def test_cold_no_catalog_history_recovers_and_retains_exact_empty_anchor(
        self,
    ):
        project, original, inodes, plan, public = self.fixture(
            with_peer_lock=False, import_flavor=True
        )
        parent, intent = catalog._decode_intent(project.root, plan["plan_identity"])
        _, frame_intent = framework._decode(project.root, public["plan_identity"])
        self.assertIn("litai/flavors", intent["new_directories"])
        self.assertIn("litai/flavors", frame_intent["original_directories"])
        self.assertFalse(
            any(
                path.startswith("litai/flavors/")
                for path in frame_intent["coordination"]
            )
        )
        self.finalize(project, plan, public, renew_peer=False)
        self.assertEqual(
            list((project.root / "litai/.literate").glob("catalog-renewal-*")), []
        )
        repository = Path(__file__).parents[2]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(repository / "src")

        def run(arguments):
            child = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    public_cli.CHILD,
                    "--json",
                    "project",
                    "layout",
                    "recover",
                    "--project",
                    str(project.root),
                    "--acknowledge",
                    *arguments,
                ],
                cwd=repository,
                env=environment,
                capture_output=True,
                text=True,
                timeout=180,
            )
            self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
            return json.loads(child.stdout)["result"]

        run(["--place-framework-authority", "--plan-identity", public["plan_identity"]])
        for _repeat in range(2):
            result = run(
                [
                    "--plan-identity",
                    plan["plan_identity"],
                    "--successor-plan-identity",
                    public["plan_identity"],
                ]
            )
            self.assertTrue(result["rolled_back"])
            self.assertFalse(result["qualification"])
            self.assertFalse(result["full_containment"])
            self.assertIn("litai/flavors", result["retained_scaffolding"])
            for name, content in original.items():
                self.assertEqual((project.root / name).read_bytes(), content)
                self.assertEqual((project.root / name).stat().st_ino, inodes[name])

    def test_framework_scope_rejects_empty_and_nonempty_successor_before_recovery(self):
        cli = public_cli.PublicProducerRenewalTests("runTest")
        for identity in ("", "sha256:" + "1" * 64):
            with self.subTest(identity=identity):
                with mock.patch.object(
                    framework, "recover_framework_authority"
                ) as effect:
                    status, packet = cli.invoke(
                        [
                            "--json",
                            "project",
                            "layout",
                            "recover",
                            "--project",
                            str(Path.cwd()),
                            "--place-framework-authority",
                            "--acknowledge",
                            "--plan-identity",
                            "sha256:" + "0" * 64,
                            "--successor-plan-identity",
                            identity,
                        ]
                    )
                    self.assertEqual(status, 2, packet)
                    self.assertEqual(
                        packet["error"]["code"],
                        "project.layout.framework_scope_conflict",
                    )
                    effect.assert_not_called()

    def test_explicit_successor_rejects_noncatalog_fallback_before_rollback(self):
        from literate_ai.adapters import project_layout_migration as migration

        helper = support.MixedComponentChannelTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, original, inodes = helper.fixture(shared_parent=True)
        with mock.patch.object(migration, "_rollback") as effect:
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "requires a catalog journal"
            ):
                migration.recover_legacy_layout_migration(
                    project.root,
                    "sha256:" + "0" * 64,
                    acknowledge=True,
                    successor_plan_identity="sha256:" + "1" * 64,
                )
            effect.assert_not_called()
        for name, content in original.items():
            self.assertEqual((project.root / name).read_bytes(), content)
            self.assertEqual((project.root / name).stat().st_ino, inodes[name])

    def test_late_census_callback_cannot_replace_original_helpers(self):
        for name in ("members", "require_helpers"):
            with self.subTest(helper=name):
                state = {}

                def census(root, journal, intent, members, *, _state=state):
                    target = _state["target"]
                    target.__code__ = _state["foreign_code"]

                _, guarded, _ = catalog._bind_successor_directories(census)
                cells = dict(
                    zip(guarded.__code__.co_freevars, guarded.__closure__, strict=True)
                )
                target = cells[name].cell_contents
                names = target.__code__.co_freevars
                body = "def outer():\n"
                body += "".join(f"    {value} = None\n" for value in names)
                body += "    def foreign(*args, **kwargs):\n"
                body += "        _ = (" + ",".join(names) + ",)\n"
                body += "        raise AssertionError('late foreign helper invoked')\n"
                body += "    return foreign\n"
                namespace = {}
                exec(body, namespace)
                state.update(target=target, foreign_code=namespace["outer"]().__code__)
                original = target.__code__
                try:
                    with self.assertRaisesRegex(ProjectLayoutPlanError, "changed"):
                        guarded(None, None, None)
                finally:
                    target.__code__ = original

    def test_rolled_back_moved_reference_rejects_foreign_destination(self):
        template = resources.initialization._template_text("SKILL.md").encode()
        before = template + b"\n[peer](samples/peer/component.md)\n"
        retained = template + b"\n[peer](litai/samples/peer/component.md)\n"
        helper = support.MixedComponentChannelTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, original, inodes = helper.fixture(
            shared_parent=True, original_skill_content=retained
        )
        project.write("SKILL.md", before)
        project.refresh()
        original["SKILL.md"] = before
        inodes["SKILL.md"] = (project.root / "SKILL.md").stat().st_ino
        plan = plan_legacy_layout_migration(
            project.root,
            ("SKILL.md",),
            place_forward_skills=False,
            place_imported_catalogs=True,
        )
        self.assertTrue(plan["applicable"], plan["blocked_references"])
        self.assertIn("SKILL.md", plan["reference_edits"])
        apply_legacy_layout_migration(
            project.root,
            plan["plan_identity"],
            acknowledge=True,
            references=("SKILL.md",),
            place_forward_skills=False,
            place_imported_catalogs=True,
        )
        self.assertEqual((project.root / "SKILL.md").read_bytes(), retained)
        public, selected = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selected)
        self.assertTrue(public["applicable"], public["required_owners"])
        self.assertEqual(
            public["owned_placements"]["SKILL.md"]["destination"], "litai/SKILL.md"
        )
        with ProjectConfigurationStore.layout_lock(project.root):
            framework.apply_framework_authority(selected, public["plan_identity"])
            framework.recover_framework_authority(project.root, public["plan_identity"])
        foreign = project.root / "litai/SKILL.md"
        self.assertFalse(foreign.exists())
        foreign.write_bytes(b"foreign post-rollback file")
        inode = foreign.stat().st_ino
        try:
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "handback custody changed"
            ):
                recover_legacy_layout_migration(
                    project.root,
                    plan["plan_identity"],
                    acknowledge=True,
                    successor_plan_identity=public["plan_identity"],
                )
            self.assertEqual(foreign.read_bytes(), b"foreign post-rollback file")
            self.assertEqual(foreign.stat().st_ino, inode)
        finally:
            foreign.unlink()
        recover_legacy_layout_migration(
            project.root,
            plan["plan_identity"],
            acknowledge=True,
            successor_plan_identity=public["plan_identity"],
        )
        for name, content in original.items():
            self.assertEqual((project.root / name).read_bytes(), content)
            self.assertEqual((project.root / name).stat().st_ino, inodes[name])

    def test_cold_import_orders_bind_the_same_single_original_owner(self):
        repository = Path(__file__).parents[2]
        environment = dict(os.environ)
        environment["PYTHONPATH"] = str(repository / "src")
        program = """
import importlib, sys
importlib.import_module('literate_ai.adapters.' + sys.argv[1])
from literate_ai.adapters import project_layout_continuation as native
from literate_ai.adapters import project_layout_catalog_successor as successor
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
try:
    native._install_successor_directories(
        successor, successor.require_catalog_successor_members, successor._bindings
    )
except ProjectLayoutPlanError as error:
    assert 'already bound' in str(error)
else:
    raise AssertionError('original owner link was not initialized')
"""
        for first in (
            "project_layout_continuation",
            "project_layout_catalog_successor",
            "project_layout_catalog_renewal",
        ):
            with self.subTest(first=first):
                child = subprocess.run(
                    [sys.executable, "-c", program, first],
                    cwd=repository,
                    env=environment,
                    capture_output=True,
                    text=True,
                    timeout=60,
                )
                self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
