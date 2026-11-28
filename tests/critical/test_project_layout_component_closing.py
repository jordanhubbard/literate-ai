"""Original namespace witnesses precede readers; SAME Git scope closes last."""

from __future__ import annotations

import unittest
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters import project_layout_component_transition as component
from literate_ai.adapters import project_layout_planning as planning
from literate_ai.contracts import CatalogImportsFile
from literate_ai.contracts.catalog_imports import CatalogImportSource
from literate_ai.projects import ProjectConfigurationStore
from tests.critical import test_project_layout_catalog_continuation as catalog_support
from tests.critical import test_project_layout_component_transition as component_support
from tests.support.fixtures_test_repository_lineage import fixture


class ComponentClosingTests(unittest.TestCase):
    def source_fixture(self):
        source = component_support.ComponentProducerTransitionTests("runTest")
        source.setUp()
        self.addCleanup(source.doCleanups)
        _parent, root, _child, lineage = fixture()
        imported = replace(
            source.imported,
            source=CatalogImportSource(
                root.project_id,
                root.project_identity.uri,
                f"git:{root.repository_url}@{root.resolved_revision}",
                (),
            ),
        )
        snapshot = ProjectConfigurationStore(source.root).read()
        context = ProjectConfigurationStore.context(source.root)
        nodes, contents = planning._capture(source.root)
        observation = planning.ProjectLayoutObservation(
            snapshot, context, {"protected_application_members": []}, nodes, contents
        )
        return source, imported, lineage, observation

    def test_replaced_source_inode_refuses_before_catalog_reader(self):
        source, imported, lineage, observed = self.source_fixture()
        source.component.rename(source.component.with_name("original"))
        source.component.mkdir()
        with patch.object(
            component, "_LOAD_CATALOG", side_effect=AssertionError("reader entered")
        ):
            with self.assertRaises(planning.ProjectLayoutPlanError):
                component.capture_component_layout_transitions(
                    observed, CatalogImportsFile((imported,)), lineage
                )

    def test_parent_alias_refuses_without_descendant_lstat_or_reader(self):
        source, imported, lineage, observed = self.source_fixture()
        parent = source.component.parent
        parent.rename(source.root / "original-components")
        outside = source.root / "foreign"
        outside.mkdir()
        parent.symlink_to(outside, target_is_directory=True)
        path_type = type(source.component)
        original_lstat = path_type.lstat
        descendants = []

        def no_descendant(path, *args, **kwargs):
            if path == source.component or str(path).startswith(
                str(source.component) + "/"
            ):
                descendants.append(str(path))
                raise AssertionError("descendant reached through alias")
            return original_lstat(path, *args, **kwargs)

        with (
            patch.object(path_type, "lstat", no_descendant),
            patch.object(
                component, "_LOAD_CATALOG", side_effect=AssertionError("reader entered")
            ),
        ):
            with self.assertRaises(planning.ProjectLayoutPlanError):
                component.capture_component_layout_transitions(
                    observed, CatalogImportsFile((imported,)), lineage
                )
        self.assertEqual(descendants, [])

    def test_already_contained_and_mixed_items_do_not_open_original_reader(self):
        _source, imported, lineage, observed = self.source_fixture()
        rows = tuple(replace(row, path="litai/" + row.path) for row in imported.files)
        for files in (rows, (imported.files[0], *rows[1:])):
            with self.subTest(paths=tuple(row.path for row in files)):
                with patch.object(
                    component,
                    "_LOAD_CATALOG",
                    side_effect=AssertionError("reader entered"),
                ):
                    self.assertEqual(
                        component.capture_component_layout_transitions(
                            observed,
                            CatalogImportsFile((replace(imported, files=files),)),
                            lineage,
                        ),
                        (),
                    )

    def catalog_fixture(self):
        source = catalog_support.CatalogContinuationTests("runTest")
        source.setUp()
        self.addCleanup(source.doCleanups)
        return source, planning.ProjectLayoutObservation(
            source.snapshot,
            source.context,
            source.inventory,
            source.observations,
            source.contents,
            source.bases,
        )

    def test_original_git_change_after_additional_catalog_reads_refuses(self):
        source, observed = self.catalog_fixture()
        foreign = {"head": "sha256:" + "a" * 64, "index": "sha256:" + "b" * 64}
        with (
            patch.object(planning, "observe_project_layout", return_value=observed),
            patch.object(
                component, "capture_component_layout_transitions", return_value=()
            ),
            patch.object(planning, "_git_state", side_effect=(None, foreign)),
        ):
            with self.assertRaises(planning.ProjectLayoutPlanError) as raised:
                planning.plan_contained_catalog_continuation(
                    source.root, ("docs/guide.md",)
                )
        self.assertEqual(raised.exception.code, "project.layout.capture_changed")

    def test_original_git_pair_is_rechecked_with_exact_original_roots(self):
        source, observed = self.catalog_fixture()
        with (
            patch.object(planning, "observe_project_layout", return_value=observed),
            patch.object(
                component, "capture_component_layout_transitions", return_value=()
            ),
            patch.object(planning, "_git_state", side_effect=(None, None)) as current,
        ):
            public, selected = planning.plan_contained_catalog_continuation(
                source.root, ("docs/guide.md",)
            )
        self.assertTrue(public["applicable"])
        self.assertEqual(
            [args.args[0] for args in current.call_args_list],
            [source.snapshot.root, source.context.framework_root],
        )
        self.assertIs(selected.snapshot, source.snapshot)

    def test_reader_cannot_redirect_original_observation_before_store_entry(self):
        source, imported, lineage, observed = self.source_fixture()
        original_root = observed.snapshot.root
        original_load = component._LOAD_CATALOG
        stores = []

        def drift(reader, selected):
            catalog = original_load(reader, selected)
            object.__setattr__(observed.snapshot, "root", source.root / "foreign-root")
            return catalog

        def no_store(*args, **kwargs):
            stores.append(args)
            raise AssertionError("redirected store entered")

        try:
            with (
                patch.object(component, "_LOAD_CATALOG", drift),
                patch.object(component, "ComponentLockStore", no_store),
            ):
                with self.assertRaises(planning.ProjectLayoutPlanError):
                    component.capture_component_layout_transitions(
                        observed, CatalogImportsFile((imported,)), lineage
                    )
        finally:
            object.__setattr__(observed.snapshot, "root", original_root)
        self.assertEqual(stores, [])
