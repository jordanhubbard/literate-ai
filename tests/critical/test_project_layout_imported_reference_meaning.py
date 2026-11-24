"""Actual captured imported link spellings retain meaning without byte edits."""

from __future__ import annotations

import unittest
from dataclasses import replace

from literate_ai.contracts import canonical_json_bytes
from literate_ai.contracts.catalog_imports import CatalogImportFile
from tests.critical import test_project_layout_catalog_continuation as support


class ImportedReferenceMeaningTests(unittest.TestCase):
    def test_original_dot_and_encoded_relative_links_remain_byte_identical(self):
        for name, link in (
            ("helper.md", "./helper.md"),
            ("helper name.md", "./helper%20name.md"),
        ):
            with self.subTest(link=link):
                fixture = support.CatalogContinuationTests("runTest")
                fixture.setUp()
                self.addCleanup(fixture.doCleanups)
                path = "skills/demo/" + name
                authored = ("[helper](" + link + ")\n").encode()
                fixture.write("skills/demo/SKILL.md", authored)
                fixture.write(path, b"# Helper\n")
                original = fixture.imports.imports[0]
                fixture.imports = replace(
                    fixture.imports,
                    imports=(
                        replace(
                            original,
                            files=(
                                CatalogImportFile(
                                    "skills/demo/SKILL.md", support.digest(authored)
                                ),
                                CatalogImportFile(path, support.digest(b"# Helper\n")),
                            ),
                        ),
                    ),
                )
                fixture.write(
                    "litai/.literate/imports.json",
                    canonical_json_bytes(fixture.imports.to_dict()) + b"\n",
                )
                fixture.refresh()
                selected = fixture.select(approved_references=("docs/guide.md",))
                self.assertTrue(selected.public_plan["applicable"])
                self.assertEqual(len(selected.placements), 2)
                self.assertEqual(
                    selected.original_contents["skills/demo/SKILL.md"], authored
                )
                self.assertNotIn("skills/demo/SKILL.md", selected.rewritten_contents)

    def test_unobserved_root_relative_subject_cannot_silently_change_meaning(self):
        fixture = support.CatalogContinuationTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        authored = b"[unknown](../../unobserved/guide.md)\n"
        fixture.write("skills/demo/SKILL.md", authored)
        original = fixture.imports.imports[0]
        fixture.imports = replace(
            fixture.imports,
            imports=(
                replace(
                    original,
                    files=(
                        CatalogImportFile(
                            "skills/demo/SKILL.md", support.digest(authored)
                        ),
                    ),
                ),
            ),
        )
        fixture.write(
            "litai/.literate/imports.json",
            canonical_json_bytes(fixture.imports.to_dict()) + b"\n",
        )
        fixture.refresh()
        self.assertFalse(fixture.select().placements)
