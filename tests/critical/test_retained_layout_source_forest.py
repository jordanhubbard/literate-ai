"""Original logical root source over genuine initializer and namespace owners.

The fixture arranges a genuinely converted project at root using canonical
declaration serializers. It is not production root relocation acceptance.
"""

from __future__ import annotations

import copy
import json
import os
import unittest
from dataclasses import replace
from unittest import mock

import tests.critical.test_retained_layout_source_admission as fixtures
from literate_ai.adapters import retained_layout_control_publication as publications
from literate_ai.adapters import retained_layout_source_state as saved_state
from literate_ai.adapters.retained_layout import (
    RETAINED_LAYOUT_PATH,
    RetainedLayoutDeclaration,
)
from literate_ai.adapters.retained_layout_control_roles import (
    layout_pending_control_path,
)
from literate_ai.adapters.retained_layout_journal import retained_layout_journal
from literate_ai.adapters.retained_layout_source_preparation import (
    prepared_retained_layout_source_move,
)
from literate_ai.contracts.identity import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "actual original root source preparation")
class OriginalSourceForestTests(unittest.TestCase):
    git = fixtures.SourceAdmissionTests.git
    init_git = fixtures.SourceAdmissionTests.init_git
    prepare = fixtures.SourceAdmissionTests.prepare
    pool = fixtures.SourceAdmissionTests.pool

    @classmethod
    def setUpClass(cls):
        fixtures.SourceAdmissionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.SourceAdmissionTests.setUp(self)
        self.input_budget = replace(self.input_budget, maximum_entries=131072)
        self.wrapper = self.source.parent
        for path in tuple(self.source.iterdir()):
            target = self.project / (
                "native-build.mk" if path.name == "Makefile" else path.name
            )
            self.assertFalse(target.exists())
            path.rename(target)
        self.source.rmdir()
        self.source = self.project
        baseline = json.loads(
            (self.project / ".literate/initialization-baseline.json").read_bytes()
        )
        owned = {item["path"] for item in baseline["files"]}
        owned.update(
            path.relative_to(self.project).as_posix()
            for path in (self.project / ".literate").rglob("*")
            if path.is_file()
        )
        owned.add(RETAINED_LAYOUT_PATH)
        declaration = RetainedLayoutDeclaration(
            self.wrapper.relative_to(self.project).as_posix(),
            ".",
            tuple(sorted(owned)),
            None,
        )
        (self.project / RETAINED_LAYOUT_PATH).write_bytes(
            canonical_json_bytes(declaration.to_dict()) + b"\n"
        )
        lift_path = self.project / ".literate/legacy-lift-shift.json"
        lift = json.loads(lift_path.read_bytes())
        old_coordinate = lift["implementation_directory"]
        lift.update(
            state="requalification-required",
            implementation_directory=".",
            wrapper_component=declaration.wrapper_component,
            layout_identity=declaration.identity,
            previous_layout_identity=None,
        )
        lift_path.write_bytes(canonical_json_bytes(lift) + b"\n")
        harness = self.project / "litai.harness.mk"
        before = harness.read_bytes()
        line = f"LITAI_LEGACY := {old_coordinate}\n".encode()
        self.assertEqual(before.splitlines(keepends=True).count(line), 1)
        harness.write_bytes(before.replace(line, b"LITAI_LEGACY := .\n"))

    def test_actual_root_preparation_binds_complete_logical_source_forest(self):
        self.init_git(commit=True)
        unknown = self.project / ".literate/application.bin"
        unknown.write_bytes(b"ordinary source beside framework metadata\n")
        (self.project / ".literate/application.lock").write_bytes(b"ordinary source\n")
        neighbor = self.wrapper / "application.txt"
        neighbor.write_bytes(b"source beside the actual wrapper\n")
        (self.project / "empty-source").mkdir()
        os.link(self.project / "app.py", self.project / "z-app-hard.py")
        (self.project / "app-link.py").symlink_to("app.py")
        before = self.project.stat().st_ino
        with self.prepare() as owner:
            plan = owner.plan
            from literate_ai.adapters.retained_layout_source_roles import (
                _source_forest_for_plan,
            )

            with owner._reads():
                forest = _source_forest_for_plan(plan)
                self.assertEqual(plan.source_forest, forest.identity.uri)
                self.assertEqual(forest.source, ".")
                files = {name for name, _blob, _executable in forest.files}
                self.assertTrue(
                    {
                        "app.py",
                        "native-build.mk",
                        ".literate/application.bin",
                        ".literate/application.lock",
                        neighbor.relative_to(self.project).as_posix(),
                    }
                    <= files
                )
                self.assertIn("empty-source", forest.directories)
                self.assertEqual(
                    {alias.path for alias in forest.aliases},
                    {"z-app-hard.py", "app-link.py"},
                )
                self.assertIn(".literate", forest.shared_directories)
                self.assertFalse(any(name.startswith(".git/") for name in files))
                self.assertNotIn("literate.project.json", files)
                self.assertNotIn(
                    self.wrapper.relative_to(self.project).as_posix() + "/component.md",
                    files,
                )
            owner.require_current()
        self.assertEqual(self.project.stat().st_ino, before)
        self.assertFalse(self.destination.exists())
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def persist_guarded_root(self):
        destination_inode = (
            self.destination.stat().st_ino if self.destination.exists() else None
        )
        before = tuple(
            sorted(p.relative_to(self.project) for p in self.project.rglob("*"))
        )
        with self.prepare() as owner:
            plan = owner.plan
            self.saved_binding = canonical_json_bytes(plan.binding)
            self.saved_phase = plan.identity.uri
            self.saved_forest = plan.source_forest
            with self.pool(plan) as (pool, journal):
                self.saved_budget = journal._budget
                with mock.patch.object(
                    publications,
                    "move_layout_entry_exclusive",
                    side_effect=AssertionError("root public control publication"),
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "root/shared admission requires the complete "
                        "multi-carrier executor",
                    ):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=plan.identity,
                            allow_host_execution=True,
                        ):
                            self.fail("root entered the single-rename executor")
                owner.require_current()
                self.original_payloads = tuple(
                    body
                    for name, (_node, body) in journal._known.items()
                    if name.startswith("p-")
                )
        self.assertEqual(
            tuple(sorted(p.relative_to(self.project) for p in self.project.rglob("*"))),
            before,
        )
        if destination_inode is None:
            self.assertFalse(self.destination.exists())
        else:
            self.assertEqual(self.destination.stat().st_ino, destination_inode)
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def reopen(self):
        return retained_layout_journal(
            self.state / "journal",
            canonical_binding=self.saved_binding,
            budget=self.saved_budget,
            recover=True,
        )

    def read_saved(self, journal):
        return saved_state._read_original_state(
            journal,
            self.saved_phase,
            budget=self.input_budget,
            maximum_metadata_bytes=self.metadata_limit,
        )

    def test_root_forest_is_durable_while_public_phase_admission_stays_guarded(self):
        unknown = self.project / ".literate/application.bin"
        unknown.write_bytes(b"source, not a declared framework exclusion\n")
        self.persist_guarded_root()
        from literate_ai.adapters.retained_layout_source_forest import _FOREST_PROFILE

        self.assertEqual(
            json.loads(self.saved_binding)["source_profile"], _FOREST_PROFILE
        )
        with self.reopen() as journal:
            saved = self.read_saved(journal)
            forest = saved.document["partition"]["forest"]
            from literate_ai.contracts.identity import canonical_identity

            self.assertEqual(canonical_identity(forest).uri, self.saved_forest)
            self.assertEqual(forest["forest"]["source"], ".")
            self.assertIn(
                ".literate/application.bin",
                {name for name, _, _ in forest["forest"]["files"]},
            )
            self.assertNotIn(
                ".literate/repository-lineage.lock",
                {name for name, _, _ in forest["forest"]["files"]},
            )
            self.assertEqual(
                saved.plan_document["plan"]["source_forest"], self.saved_forest
            )
        self.assertEqual(
            unknown.read_bytes(), b"source, not a declared framework exclusion\n"
        )

    def test_actual_forest_journal_refuses_legacy_recovery_before_acquisition(self):
        from literate_ai.adapters import retained_layout_recovery_controls as controls
        from literate_ai.adapters import retained_layout_recovery_roles as roles
        from literate_ai.adapters.retained_layout_control_publication import (
            staged_layout_controls,
        )
        from literate_ai.adapters.retained_layout_control_roles import _project_roles

        self.persist_guarded_root()
        before = tuple(sorted(self.project.rglob("*")))
        (self.state / "recovery-stages").mkdir(mode=0o700)
        with self.reopen() as journal:
            with staged_layout_controls(
                self.state / "recovery-stages", journal
            ) as pool:
                targets = _project_roles(self.project).targets()
                with mock.patch.object(
                    controls,
                    "_records",
                    side_effect=AssertionError(
                        "unsupported forest reached history inference"
                    ),
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "source forest requires complete multi-carrier recovery",
                    ):
                        controls.plan_layout_control_recovery(pool, targets)
                with mock.patch.object(
                    roles,
                    "_RecoveryReservations",
                    side_effect=AssertionError(
                        "unsupported forest reached role acquisition"
                    ),
                ):
                    with self.assertRaisesRegex(
                        ValueError,
                        "source forest requires complete multi-carrier recovery",
                    ):
                        roles.plan_recovered_layout_roles(self.project, pool, ())
                # The same data-only decoder remains available with its own
                # explicit fresh policy, without granting any recovery role.
                self.assertEqual(
                    self.read_saved(journal).plan_document["plan"]["source_forest"],
                    self.saved_forest,
                )
        self.assertEqual(tuple(sorted(self.project.rglob("*"))), before)
        self.assertFalse((self.project / "litai/layout.pending").exists())
        self.assertFalse(self.destination.exists())

    def test_profile_inspection_never_invokes_foreign_cached_key_equality(self):
        from literate_ai.adapters.retained_layout_recovery_controls import (
            _require_legacy_recovery_profile,
        )

        comparisons = []

        class CollidingForeignKey:
            def __hash__(self):
                return hash("header.json")

            def __eq__(self, other):
                comparisons.append(other)
                raise AssertionError(
                    "foreign cache-key callback before owner validation"
                )

        with self.prepare() as owner:
            with self.pool(owner.plan) as (pool, journal):
                original = journal._known
                try:
                    # Deliberately malformed cached data, never a new live owner.
                    # Restore it before any mandatory/native pool validation.
                    journal._known = {CollidingForeignKey(): original["header.json"]}
                    _require_legacy_recovery_profile(pool)
                finally:
                    journal._known = original
                self.assertEqual(comparisons, [])
                with self.assertRaisesRegex(
                    ValueError, "source forest requires complete multi-carrier recovery"
                ):
                    _require_legacy_recovery_profile(pool)

    def test_declaration_cannot_promote_unknown_metadata_to_framework(self):
        unknown = self.project / ".literate/application.bin"
        unknown.write_bytes(b"source survives unproven ownership claim\n")
        path = self.project / RETAINED_LAYOUT_PATH
        declaration = RetainedLayoutDeclaration.from_dict(json.loads(path.read_bytes()))
        declaration = replace(
            declaration,
            framework_owned_paths=tuple(
                sorted(
                    {*declaration.framework_owned_paths, ".literate/application.bin"}
                )
            ),
        )
        path.write_bytes(canonical_json_bytes(declaration.to_dict()) + b"\n")
        lift_path = self.project / ".literate/legacy-lift-shift.json"
        lift = json.loads(lift_path.read_bytes())
        lift["layout_identity"] = declaration.identity
        lift_path.write_bytes(canonical_json_bytes(lift) + b"\n")
        with self.assertRaisesRegex(ValueError, "root declaration ownership differs"):
            with self.prepare():
                self.fail("unproven root declaration granted ownership")
        self.assertEqual(
            unknown.read_bytes(), b"source survives unproven ownership claim\n"
        )
        self.assertFalse(self.destination.exists())

    def test_new_original_root_source_revokes_preparation_without_cleanup(self):
        unknown = self.project / ".literate/late-source.bin"
        original = (self.project / "app.py").read_bytes()
        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                unknown.write_bytes(b"foreign late source\n")
                owner.require_current()
        self.assertEqual(unknown.read_bytes(), b"foreign late source\n")
        self.assertEqual((self.project / "app.py").read_bytes(), original)
        self.assertFalse(self.destination.exists())

    def test_existing_source_destination_binds_its_overlapping_projection(self):
        self.destination.mkdir()
        original = self.destination / "old-source.bin"
        original.write_bytes(b"source already at the selected destination\n")
        node = self.destination.stat().st_ino
        with self.prepare() as owner:
            from literate_ai.adapters.retained_layout_source_roles import (
                _BOUND,
                _FACTS,
                _source_forest_for_plan,
            )

            with owner._reads():
                forest = _source_forest_for_plan(owner.plan)
                self.assertIn(
                    "retained/old-source.bin", {n for n, _, _ in forest.files}
                )
                graph = _FACTS[_BOUND[owner]].graph
                self.assertIn(("retained", "retained/retained"), graph.carriers)
                self.assertIn("retained", graph.create_directories)
            owner.require_current()
        self.assertEqual(self.destination.stat().st_ino, node)
        self.assertEqual(
            original.read_bytes(), b"source already at the selected destination\n"
        )
        self.assertFalse(layout_pending_control_path(self.project).exists())
        self.persist_guarded_root()
        with self.reopen() as journal:
            saved = self.read_saved(journal)
            self.assertIn(
                ["retained", "retained/retained"],
                saved.document["partition"]["graph"]["carriers"],
            )

    def test_existing_canonical_directory_without_source_ownership_refuses(self):
        original = (self.project / ".literate/legacy-lift-shift.json").read_bytes()
        with self.assertRaisesRegex(
            ValueError, "lacks actual original source ownership"
        ):
            with prepared_retained_layout_source_move(
                self.project,
                ".literate",
                budget=self.input_budget,
                maximum_metadata_bytes=self.metadata_limit,
            ):
                self.fail("fixed metadata directory became a source destination")
        self.assertEqual(
            (self.project / ".literate/legacy-lift-shift.json").read_bytes(), original
        )
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_portable_alias_of_existing_source_destination_refuses(self):
        alias = self.project / "RETAINED"
        alias.mkdir()
        original = alias / "original.bin"
        original.write_bytes(b"retain portable alias custody\n")
        with self.assertRaisesRegex(ValueError, "exists or aliases"):
            with self.prepare():
                self.fail("portable destination alias was accepted")
        self.assertEqual(original.read_bytes(), b"retain portable alias custody\n")
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_changed_existing_source_destination_payload_revokes_preparation(self):
        self.destination.mkdir()
        original = self.destination / "old-source.bin"
        original.write_bytes(b"original input\n")
        with self.assertRaises(ValueError):
            with self.prepare() as owner:
                original.write_bytes(b"concurrently changed input must survive\n")
                owner.require_current()
                self.fail("changed destination source remained current")
        self.assertEqual(
            original.read_bytes(), b"concurrently changed input must survive\n"
        )
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_structurally_copied_forest_cannot_replace_original_before_native_reads(
        self,
    ):
        from literate_ai.adapters.retained_layout_source_preparation import _state

        with self.assertRaisesRegex(
            ValueError, "original prepared plan fields changed"
        ):
            with self.prepare() as owner:
                original = _state(owner)
                object.__setattr__(owner.plan, "tree", replace(owner.plan.tree))
                with mock.patch.object(
                    type(original.reader),
                    "file",
                    side_effect=AssertionError(
                        "unregistered forest caused native reads"
                    ),
                ):
                    owner.require_current()

    def test_valid_journal_chain_cannot_substitute_the_root_forest(self):
        self.persist_guarded_root()
        with self.reopen() as journal:
            saved = self.read_saved(journal)
            document = copy.deepcopy(saved.document)
        document["partition"]["forest"]["forest"]["shared_directories"].append(
            "invented"
        )
        with retained_layout_journal(
            self.state / "substituted-forest",
            canonical_binding=self.saved_binding,
            budget=self.saved_budget,
        ) as journal:
            for body in self.original_payloads:
                journal.store_payload(body)
            digest = journal.store_payload(canonical_json_bytes(document))
            journal.append(
                "source-original-state-durable",
                canonical_json_bytes(
                    {
                        "source_phase_identity": self.saved_phase,
                        "state_payload_digest": digest,
                        "grants_move_authority": False,
                    }
                ),
            )
            with self.assertRaisesRegex(
                ValueError, "original logical source forest differs"
            ):
                self.read_saved(journal)


@unittest.skipUnless(os.name == "posix", "actual mixed destination preparation")
class OriginalMixedDestinationTests(unittest.TestCase):
    git = fixtures.SourceAdmissionTests.git
    init_git = fixtures.SourceAdmissionTests.init_git
    pool = fixtures.SourceAdmissionTests.pool

    @classmethod
    def setUpClass(cls):
        fixtures.SourceAdmissionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.SourceAdmissionTests.setUp(self)
        self.input_budget = replace(self.input_budget, maximum_entries=131072)

    def prepare_to(self, destination):
        return prepared_retained_layout_source_move(
            self.project,
            destination,
            budget=self.input_budget,
            maximum_metadata_bytes=self.metadata_limit,
        )

    def selected_storage(self, *, present):
        from literate_ai.adapters.component_locks import ComponentLockStore

        matrix = self.source / "selected-storage"
        matrix.mkdir()
        self.enterContext(
            mock.patch.dict(os.environ, {"LITAI_MATRIX_CELL_ROOT": str(matrix)})
        )
        selected = ComponentLockStore(self.source.parent).path
        if present:
            selected.parent.mkdir(parents=True)
            selected.write_bytes(b"stale selected canonical evidence\n")
        return matrix, selected

    def test_actual_absent_canonical_store_inside_source_keeps_shared_ancestors(self):
        from literate_ai.adapters.retained_layout_source_roles import _BOUND, _FACTS

        matrix, selected = self.selected_storage(present=False)
        namesake = matrix / "component.lock.json"
        namesake.write_bytes(b"ordinary source namesake\n")
        original = matrix.stat().st_ino
        with self.prepare_to("retained") as owner:
            self.assertEqual(owner.plan.authored_lock, selected)
            self.assertIsNotNone(owner.plan.source_forest)
            with owner._reads():
                facts = _FACTS[_BOUND[owner]]
                logical = {name for name, _, _ in facts.forest.files}
                self.assertIn("selected-storage/component.lock.json", logical)
                self.assertIn(
                    matrix.relative_to(self.project).as_posix(),
                    facts.graph.fixed_directories,
                )
                self.assertIn(
                    selected.relative_to(self.project).as_posix(), facts.controls
                )
            owner.require_current()
        self.assertFalse(selected.exists())
        self.assertEqual(matrix.stat().st_ino, original)
        self.assertEqual(namesake.read_bytes(), b"ordinary source namesake\n")
        self.assertFalse((self.project / "retained").exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_actual_canonical_lock_stays_fixed_while_namesakes_remain_source(
        self,
    ):
        from literate_ai.adapters.retained_layout_source_roles import _BOUND, _FACTS

        matrix, selected = self.selected_storage(present=True)
        namesake = matrix / "ordinary.lock"
        namesake.write_bytes(b"unknown ordinary source\n")
        before = selected.read_bytes()
        node = selected.stat().st_ino
        with self.prepare_to("retained") as owner:
            with owner._reads():
                facts = _FACTS[_BOUND[owner]]
                self.assertEqual(
                    dict(facts.roles)[selected.relative_to(self.project).as_posix()],
                    "authored",
                )
                logical = {name for name, _, _ in facts.forest.files}
                self.assertNotIn(selected.relative_to(self.source).as_posix(), logical)
                self.assertIn("selected-storage/ordinary.lock", logical)
                self.assertIn(
                    selected.parent.relative_to(self.project).as_posix(),
                    facts.graph.fixed_directories,
                )
            with self.pool(owner.plan) as (pool, _journal):
                with self.assertRaisesRegex(ValueError, "multi-carrier executor"):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ):
                        self.fail("shared store entered legacy source executor")
            owner.require_current()
        self.assertEqual(selected.stat().st_ino, node)
        self.assertEqual(selected.read_bytes(), before)
        self.assertEqual(namesake.read_bytes(), b"unknown ordinary source\n")
        self.assertFalse((self.project / "retained").exists())

    def test_late_selected_canonical_store_insertion_revokes_without_cleanup(self):
        _matrix, selected = self.selected_storage(present=False)
        with self.assertRaises(ValueError):
            with self.prepare_to("retained") as owner:
                selected.parent.mkdir(parents=True)
                selected.write_bytes(b"concurrent canonical evidence\n")
                owner.require_current()
                self.fail("late selected canonical evidence remained current")
        self.assertEqual(selected.read_bytes(), b"concurrent canonical evidence\n")
        self.assertFalse((self.project / "retained").exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_source_projection_cannot_create_selected_canonical_storage(self):
        _matrix, selected = self.selected_storage(present=False)
        namesake = self.source / "component.lock.json"
        namesake.write_bytes(b"source namesake must remain owned\n")
        with self.assertRaisesRegex(ValueError, "canonical lock storage overlaps"):
            with self.prepare_to(selected.parent.relative_to(self.project).as_posix()):
                self.fail("source projection created canonical storage")
        self.assertEqual(namesake.read_bytes(), b"source namesake must remain owned\n")
        self.assertFalse(selected.parent.exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_descendant_with_missing_parents_retains_original_destination_state(self):
        selected = self.source / "new-parent/next/implementation"
        coordinate = selected.relative_to(self.project).as_posix()
        original = self.source.stat().st_ino
        with self.prepare_to(coordinate) as owner:
            state = owner.plan.destination_state
            self.assertEqual(state.anchor, self.source)
            self.assertIsNone(state.parent_node)
            self.assertIsNone(owner.plan.destination_parent)
            self.assertEqual(owner.plan.destination_lineage, ())
            self.assertEqual(
                [name for name, node in state.prefixes if node is None],
                [
                    (self.source / suffix).relative_to(self.project).as_posix()
                    for suffix in (
                        "new-parent",
                        "new-parent/next",
                        "new-parent/next/implementation",
                    )
                ],
            )
            owner.require_current()
        self.assertEqual(self.source.stat().st_ino, original)
        self.assertFalse((self.source / "new-parent").exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_missing_destination_prefix_insertion_revokes_original_plan(self):
        selected = self.source / "new-parent/next/implementation"
        coordinate = selected.relative_to(self.project).as_posix()
        with self.assertRaises(ValueError):
            with self.prepare_to(coordinate) as owner:
                inserted = self.source / "new-parent"
                inserted.mkdir()
                (inserted / "foreign.bin").write_bytes(b"concurrent source\n")
                owner.require_current()
                self.fail("inserted destination prefix remained current")
        self.assertEqual(
            (inserted / "foreign.bin").read_bytes(), b"concurrent source\n"
        )
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_missing_destination_state_reopens_without_public_effects(self):
        selected = self.source / "new-parent/next/implementation"
        coordinate = selected.relative_to(self.project).as_posix()
        with self.prepare_to(coordinate) as owner:
            plan = owner.plan
            binding, identity = canonical_json_bytes(plan.binding), plan.identity.uri
            with self.pool(plan) as (pool, journal):
                journal_budget = journal._budget
                with mock.patch.object(
                    publications,
                    "move_layout_entry_exclusive",
                    side_effect=AssertionError("missing-parent public effect"),
                ):
                    with self.assertRaisesRegex(ValueError, "multi-carrier executor"):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=plan.identity,
                            allow_host_execution=True,
                        ):
                            self.fail("missing-parent forest entered legacy executor")
                owner.require_current()
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=binding,
            budget=journal_budget,
            recover=True,
        ) as journal:
            saved = saved_state._read_original_state(
                journal,
                identity,
                budget=self.input_budget,
                maximum_metadata_bytes=self.metadata_limit,
            )
            description = saved.plan_document["plan"]["destination_state"]
            self.assertEqual(description["anchor"], str(self.source))
            self.assertIsNone(description["parent_node"])
            self.assertEqual(
                sum(node is None for _, node in description["prefixes"]), 3
            )
        self.assertFalse((self.source / "new-parent").exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def arrange_nonroot_source(self):
        # Fixture-only layout arrangement using real canonical prospective
        # bytes; this is not execution or public relocation acceptance.
        with self.prepare_to("retained/inner") as owner:
            prospective = owner.plan.prospective
        parent = self.project / "retained"
        parent.mkdir()
        relocated = parent / "inner"
        self.source.rename(relocated)
        self.source = relocated
        for name, content in prospective:
            (self.project / name).write_bytes(content)

    def test_source_only_ancestor_destination_keeps_original_container_custody(self):
        self.arrange_nonroot_source()
        before = self.source.stat().st_ino
        with self.prepare_to("retained") as owner:
            from literate_ai.adapters.retained_layout_source_roles import _BOUND, _FACTS

            with owner._reads():
                graph = _FACTS[_BOUND[owner]].graph
                self.assertEqual(graph.source, "retained/inner")
                self.assertIn("retained/inner", graph.retain_directories)
                self.assertIsNotNone(owner.plan.source_forest)
            owner.require_current()
        self.assertEqual(self.source.stat().st_ino, before)
        self.assertFalse((self.project / "retained/app.py").exists())

    def test_ancestor_with_unclaimed_occupant_refuses_without_borrowing_ownership(self):
        self.arrange_nonroot_source()
        foreign = self.project / "retained/foreign.bin"
        foreign.write_bytes(b"unrelated original occupant\n")
        with self.assertRaisesRegex(
            ValueError, "lacks actual original source ownership"
        ):
            with self.prepare_to("retained"):
                self.fail("source ancestry authorized unrelated original occupants")
        self.assertEqual(foreign.read_bytes(), b"unrelated original occupant\n")
        self.assertTrue((self.source / "app.py").exists())

    def test_portable_alias_of_missing_destination_prefix_refuses(self):
        existing = self.source / "NEW-PARENT"
        existing.mkdir()
        (existing / "original.bin").write_bytes(b"portable prefix custody\n")
        coordinate = (
            (self.source / "new-parent/next/implementation")
            .relative_to(self.project)
            .as_posix()
        )
        with self.assertRaisesRegex(ValueError, "portable destination prefix alias"):
            with self.prepare_to(coordinate):
                self.fail("portable prefix alias became an observed absence")
        self.assertEqual(
            (existing / "original.bin").read_bytes(), b"portable prefix custody\n"
        )

    def test_copied_destination_description_cannot_replace_creating_facts(self):
        coordinate = (
            (self.source / "new-parent/next/implementation")
            .relative_to(self.project)
            .as_posix()
        )
        with self.assertRaisesRegex(
            ValueError, "original prepared plan fields changed"
        ):
            with self.prepare_to(coordinate) as owner:
                object.__setattr__(
                    owner.plan,
                    "destination_state",
                    replace(owner.plan.destination_state),
                )
                owner.require_current()
                self.fail("copied destination data replaced creating observation")
        self.assertFalse((self.source / "new-parent").exists())
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_actual_root_destination_metadata_binds_only_canonical_ownership(self):
        self.init_git(commit=True)
        unknown = self.project / ".literate/application.cfg"
        unknown.write_bytes(b"unclaimed stationary source remains visible\n")
        original = self.source.stat().st_ino
        with self.prepare_to(".") as owner:
            plan = owner.plan
            self.assertEqual(plan.destination, self.project)
            proposed = RetainedLayoutDeclaration.from_dict(
                json.loads(dict(plan.prospective)[RETAINED_LAYOUT_PATH])
            )
            self.assertEqual(proposed.implementation_directory, ".")
            self.assertIn(RETAINED_LAYOUT_PATH, proposed.framework_owned_paths)
            self.assertIn("literate.project.json", proposed.framework_owned_paths)
            self.assertNotIn(
                ".literate/application.cfg", proposed.framework_owned_paths
            )
            self.assertNotIn("app.py", proposed.framework_owned_paths)
            from literate_ai.adapters.retained_layout_source_roles import (
                _source_forest_for_plan,
            )

            with owner._reads():
                forest = _source_forest_for_plan(plan)
                self.assertEqual(
                    forest.source, self.source.relative_to(self.project).as_posix()
                )
                self.assertEqual(plan.source_forest, forest.identity.uri)
                self.assertIn("app.py", {name for name, _, _ in forest.files})
            owner.require_current()
        self.assertEqual(self.source.stat().st_ino, original)
        self.assertEqual(
            unknown.read_bytes(), b"unclaimed stationary source remains visible\n"
        )
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def test_root_destination_refuses_actual_framework_collision_without_effects(self):
        # The real initializer owns litai.harness.mk. Ordinary source cannot
        # replace that endpoint merely by projecting an identically named file.
        collision = self.source / "litai.harness.mk"
        collision.write_bytes(b"ordinary source must retain custody\n")
        original = collision.read_bytes()
        framework = (self.project / "litai.harness.mk").read_bytes()
        with self.assertRaisesRegex(ValueError, "collid|fixed namespace"):
            with self.prepare_to("."):
                self.fail("source replaced genuine framework ownership")
        self.assertEqual(collision.read_bytes(), original)
        self.assertEqual((self.project / "litai.harness.mk").read_bytes(), framework)
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def test_root_destination_persists_original_forest_without_publication(self):
        before = tuple(sorted(self.project.rglob("*")))
        source_inode = self.source.stat().st_ino
        with self.prepare_to(".") as owner:
            plan = owner.plan
            binding = canonical_json_bytes(plan.binding)
            identity, forest_identity = plan.identity.uri, plan.source_forest
            with self.pool(plan) as (pool, journal):
                journal_budget = journal._budget
                with mock.patch.object(
                    publications,
                    "move_layout_entry_exclusive",
                    side_effect=AssertionError("root destination public publication"),
                ):
                    with self.assertRaisesRegex(ValueError, "multi-carrier executor"):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=plan.identity,
                            allow_host_execution=True,
                        ):
                            self.fail("root destination entered single-rename executor")
                owner.require_current()
        with retained_layout_journal(
            self.state / "journal",
            canonical_binding=binding,
            budget=journal_budget,
            recover=True,
        ) as journal:
            saved = saved_state._read_original_state(
                journal,
                identity,
                budget=self.input_budget,
                maximum_metadata_bytes=self.metadata_limit,
            )
            self.assertEqual(
                saved.plan_document["plan"]["source_forest"], forest_identity
            )
            self.assertEqual(saved.document["partition"]["graph"]["destination"], ".")
        self.assertEqual(tuple(sorted(self.project.rglob("*"))), before)
        self.assertEqual(self.source.stat().st_ino, source_inode)
        self.assertFalse(layout_pending_control_path(self.project).exists())

    def test_fixed_root_destination_membership_change_revokes_preparation(self):
        addition = self.project / "new-unclaimed-file"
        with self.assertRaises(ValueError):
            with self.prepare_to(".") as owner:
                addition.write_bytes(b"must remain under original namespace custody\n")
                owner.require_current()
        self.assertEqual(
            addition.read_bytes(), b"must remain under original namespace custody\n"
        )
        self.assertFalse(layout_pending_control_path(self.project).exists())
