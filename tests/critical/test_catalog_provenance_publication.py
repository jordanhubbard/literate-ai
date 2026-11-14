"""Actual catalog provenance retains old bytes and remains an incomplete apply."""

from __future__ import annotations

import hashlib
import json
import os
import stat
import unittest
from pathlib import Path
from unittest import mock

import tests.critical.test_catalog_copy_protection as fixtures
from literate_ai.adapters import catalog_entry_publication as publication
from literate_ai.contracts.catalog_imports import (
    CatalogImport,
    CatalogImportFile,
    CatalogImportsFile,
    CatalogImportSource,
    CatalogInheritanceDecision,
)


@unittest.skipUnless(os.name == "posix", "actual POSIX catalog provenance effects")
class CatalogProvenancePublicationTests(unittest.TestCase):
    owners = fixtures.CatalogCopyProtectionTests.owners
    git = fixtures.CatalogCopyProtectionTests.git
    init_git = fixtures.CatalogCopyProtectionTests.init_git

    @classmethod
    def setUpClass(cls):
        fixtures.CatalogCopyProtectionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.CatalogCopyProtectionTests.setUp(self)
        self.metadata = self.project / CatalogImportsFile.PATH

    def application(self, stages, controls, journal_root):
        return publication.catalog_entry_publication(
            stages, controls, control_journal_root=journal_root
        )

    def publish(self, owner, stages, tokens):
        for token in tokens:
            owner.publish(token, acknowledged_plan_identity=stages.plan.identity)
        return owner.publish_provenance(acknowledged_plan_identity=stages.plan.identity)

    def old_imports(self):
        source = CatalogImportSource(
            "unrelated", "sha256:" + "1" * 64, "local:/unrelated", ()
        )
        files = (CatalogImportFile("skills/keep/SKILL.md", "sha256:" + "2" * 64),)
        return CatalogImportsFile(
            (
                CatalogImport(
                    "skill", "keep", source, files, "2026-01-01T00:00:00+00:00"
                ),
            ),
            (
                CatalogInheritanceDecision(
                    "skill", "keep", source, files, "shadowed", "selected"
                ),
            ),
        )

    def test_absent_metadata_is_published_from_actual_files_and_canonical_source(self):
        self.metadata.unlink(missing_ok=True)
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            original = next(i for i in stages.plan._inputs if i.path == self.metadata)
            with self.assertRaisesRegex(
                ValueError, "control finalization and imported-role"
            ):
                with self.application(stages, controls, journal_root) as owner:
                    result = self.publish(owner, stages, [token])
                    loaded = CatalogImportsFile.load(self.project)
                    new = loaded.imports[-1]
                    self.assertEqual(new.source.ref, "local:" + str(self.upstream))
                    expected_source = (
                        "sha256:"
                        + hashlib.sha256(
                            (self.upstream / "literate.project.json").read_bytes()
                        ).hexdigest()
                    )
                    self.assertEqual(new.source.project_identity, expected_source)
                    expected = {
                        "flavors/local-toolchain/flavor.md": "sha256:"
                        + hashlib.sha256(
                            (self.item / "flavor.md").read_bytes()
                        ).hexdigest()
                    }
                    self.assertEqual({f.path: f.identity for f in new.files}, expected)
                    self.assertIsNone(original.content)
                    self.assertIsNone(result["retired"])
                    self.assertFalse(result["grants_imported_roles"])
                    owner.require_current()
                    self.assertEqual(
                        owner.inspect()["state"],
                        "provenance-published-controls-pending",
                    )
            stages.require_current()
            with self.assertRaisesRegex(ValueError, "writer ended"):
                owner.publish_provenance(
                    acknowledged_plan_identity=stages.plan.identity
                )
        with self.assertRaisesRegex(ValueError, "ended"):
            owner.require_current()

    def test_original_metadata_node_bytes_unrelated_imports_and_decisions_survive(self):
        old = self.old_imports()
        old.save(self.project)
        self.metadata.chmod(0o640)
        raw, inode = self.metadata.read_bytes(), self.metadata.stat().st_ino
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            with self.assertRaisesRegex(
                ValueError, "control finalization and imported-role"
            ):
                with self.application(stages, controls, journal_root) as owner:
                    result = self.publish(owner, stages, [token])
                    retained = Path(result["retired"])
                    self.assertEqual(retained.read_bytes(), raw)
                    self.assertEqual(retained.stat().st_ino, inode)
                    self.assertEqual(stat.S_IMODE(self.metadata.stat().st_mode), 0o640)
                    loaded = CatalogImportsFile.load(self.project)
                    self.assertEqual(loaded.imports[0], old.imports[0])
                    self.assertEqual(loaded.decisions, old.decisions)
                    self.assertEqual(
                        stages.plan._inputs[
                            [i.path for i in stages.plan._inputs].index(self.metadata)
                        ].content,
                        raw,
                    )
                    owner.require_current()

    def test_incomplete_items_and_wrong_acknowledgement_cannot_publish_metadata(self):
        with self.owners() as (stages, controls, journal_root):
            token = stages.stage_item(0)
            with self.application(stages, controls, journal_root) as owner:
                with self.assertRaisesRegex(ValueError, "acknowledgement"):
                    owner.publish_provenance(acknowledged_plan_identity=None)
                with self.assertRaisesRegex(ValueError, "every actual selected item"):
                    owner.publish_provenance(
                        acknowledged_plan_identity=stages.plan.identity
                    )
                owner._published[token] = "invented inspection result"
                with self.assertRaisesRegex(ValueError, "every actual selected item"):
                    owner.publish_provenance(
                        acknowledged_plan_identity=stages.plan.identity
                    )
                owner.require_current()

    def test_published_provenance_is_single_use_and_later_tampering_is_preserved(self):
        with self.assertRaises(ValueError):
            with self.owners() as (stages, controls, journal_root):
                token = stages.stage_item(0)
                with self.application(stages, controls, journal_root) as owner:
                    self.publish(owner, stages, [token])
                    with self.assertRaisesRegex(ValueError, "single-use"):
                        owner.publish_provenance(
                            acknowledged_plan_identity=stages.plan.identity
                        )
                    self.metadata.write_bytes(b"foreign metadata\n")
                    owner.require_current()
        self.assertEqual(self.metadata.read_bytes(), b"foreign metadata\n")

    def test_original_hardlinked_metadata_refuses_before_item_effects(self):
        self.old_imports().save(self.project)
        os.link(self.metadata, self.project / "metadata-alias")
        with self.owners() as (stages, controls, journal_root):
            stages.stage_item(0)
            with self.assertRaisesRegex(ValueError, "single-link"):
                with self.application(stages, controls, journal_root):
                    self.fail("hardlinked metadata was admitted")
        self.assertFalse((self.project / "flavors/local-toolchain").exists())

    def test_post_retirement_failure_preserves_original_and_prospective_files(self):
        self.old_imports().save(self.project)
        raw = self.metadata.read_bytes()
        with self.assertRaises(OSError):
            with self.owners() as (stages, controls, journal_root):
                token = stages.stage_item(0)
                private = stages.root
                with self.application(stages, controls, journal_root) as owner:
                    owner.publish(
                        token, acknowledged_plan_identity=stages.plan.identity
                    )
                    move = publication.move_layout_entry_exclusive

                    def interrupted(source, destination, **kwargs):
                        if destination == self.metadata:
                            raise OSError("metadata publication interrupted")
                        return move(source, destination, **kwargs)

                    with mock.patch.object(
                        publication, "move_layout_entry_exclusive", interrupted
                    ):
                        owner.publish_provenance(
                            acknowledged_plan_identity=stages.plan.identity
                        )
        self.assertEqual((private / "imports-original.json").read_bytes(), raw)
        self.assertFalse(self.metadata.exists())
        self.assertTrue((private / "imports-prospective.json").is_file())
        events = [
            json.loads(p.read_bytes()) for p in (private / "journal").glob("e-*.json")
        ]
        self.assertTrue(any(e["kind"] == "catalog-provenance-intent" for e in events))
        self.assertFalse(
            any(e["kind"] == "catalog-provenance-observed" for e in events)
        )

    def test_all_items_share_one_timestamp_and_keep_canonical_source_ancestors(self):
        other = self.upstream / "flavors/other"
        other.mkdir()
        (other / "flavor.md").write_bytes(b"second item\n")
        ancestor = self.old_imports()
        ancestor.save(self.upstream)
        with self.owners(specs=("flavor:local-toolchain", "flavor:other")) as (
            stages,
            controls,
            journal_root,
        ):
            tokens = [stages.stage_item(index) for index in range(2)]
            with self.assertRaisesRegex(
                ValueError, "control finalization and imported-role"
            ):
                with self.application(stages, controls, journal_root) as owner:
                    self.publish(owner, stages, tokens)
                    loaded = CatalogImportsFile.load(self.project)
                    self.assertEqual(len(loaded.imports), 2)
                    self.assertEqual(len({i.copied_at for i in loaded.imports}), 1)
                    for item in loaded.imports:
                        upstream = next(
                            a
                            for a in item.source.transitive_ancestors
                            if a.project_id == "unrelated"
                        )
                        self.assertEqual(
                            upstream.project_identity,
                            ancestor.imports[0].source.project_identity,
                        )
                        self.assertEqual(upstream.ref, ancestor.imports[0].source.ref)
                    owner.require_current()

    def test_provenance_events_are_reserved_before_any_project_entry_effect(self):
        create = fixtures.staged_catalog_copies

        def limited(*args, **kwargs):
            budget = kwargs["journal_budget"]
            kwargs["journal_budget"] = type(budget)(
                8,
                budget.maximum_payload_bytes,
                budget.maximum_storage_bytes,
                budget.maximum_stages,
            )
            return create(*args, **kwargs)

        with mock.patch.object(fixtures, "staged_catalog_copies", limited):
            with self.owners() as (stages, controls, journal_root):
                stages.stage_item(0)
                with self.assertRaisesRegex(ValueError, "journal allowance"):
                    with self.application(stages, controls, journal_root):
                        self.fail("provenance borrowed journal room after item effects")
                self.assertFalse((self.project / "flavors/local-toolchain").exists())

    def test_foreign_metadata_after_item_effect_refuses_provenance_and_retains_it(self):
        with self.assertRaises(ValueError):
            with self.owners() as (stages, controls, journal_root):
                token = stages.stage_item(0)
                with self.application(stages, controls, journal_root) as owner:
                    owner.publish(
                        token, acknowledged_plan_identity=stages.plan.identity
                    )
                    self.metadata.write_bytes(b"foreign metadata after item\n")
                    owner.publish_provenance(
                        acknowledged_plan_identity=stages.plan.identity
                    )
        self.assertEqual(self.metadata.read_bytes(), b"foreign metadata after item\n")


if __name__ == "__main__":
    unittest.main()
