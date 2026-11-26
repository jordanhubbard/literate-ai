"""Real provenance reads remain live while duplicate pure parsing is bounded."""

import errno
import unittest
from contextlib import nullcontext
from unittest.mock import patch

from literate_ai.adapters import catalog_import as catalog
from literate_ai.projects import ProjectConfigurationStore
from tests.smoke import test_catalog_import as fixture


class CatalogProvenanceParseTemplates(unittest.TestCase):
    def setUp(self):
        self.f = fixture.ContainedCatalogProvenanceTests("runTest")
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.metadata = self.f._place()
        self.snapshot = ProjectConfigurationStore.discover(self.f.source)

    def test_repeated_parse_keeps_all_real_provenance_reads(self):
        frame = getattr(catalog, "read_only_catalog_provenance_parses", nullcontext)
        with (
            frame(),
            patch.object(
                catalog, "_provenance_bytes", wraps=catalog._provenance_bytes
            ) as reads,
            patch.object(
                catalog,
                "_contained_catalog_records",
                wraps=catalog._contained_catalog_records,
            ) as parses,
        ):
            first = catalog.read_contained_catalog_imports(self.snapshot)
            second = catalog.read_contained_catalog_imports(self.snapshot)
            self.assertEqual(first, second)
            self.assertEqual(reads.call_count, 4)
            self.assertEqual(parses.call_count, 1)

    def test_without_frame_preserves_uncached_behavior(self):
        with patch.object(
            catalog,
            "_contained_catalog_records",
            wraps=catalog._contained_catalog_records,
        ) as parses:
            self.assertEqual(
                catalog.read_contained_catalog_imports(self.snapshot),
                catalog.read_contained_catalog_imports(self.snapshot),
            )
            self.assertEqual(parses.call_count, 2)

    def test_changed_actual_file_bytes_are_observed_inside_frame(self):
        import json

        path = self.metadata / "imports.json"
        with catalog.read_only_catalog_provenance_parses():
            first = catalog.read_contained_catalog_imports(self.snapshot)
            data = json.loads(path.read_bytes())
            data["imports"][0]["files"][0]["identity"] = "sha256:" + "a" * 64
            path.write_text(json.dumps(data))
            second = catalog.read_contained_catalog_imports(self.snapshot)
            self.assertNotEqual(first, second)
            self.assertEqual(second.imports[0].files[0].identity, "sha256:" + "a" * 64)

    def test_caller_cannot_mutate_private_origin_or_import_templates(self):
        with catalog.read_only_catalog_provenance_parses():
            documents = catalog._catalog_provenance(self.snapshot)
            origin, imports = catalog._parse_provenance(documents, contained=True)
            self.assertTrue(imports.imports)
            original = origin["distribution_name"]
            origin["distribution_name"] = "caller mutation"
            object.__setattr__(imports, "imports", ())
            observed, records = catalog._parse_provenance(
                catalog._catalog_provenance(self.snapshot), contained=True
            )
            self.assertEqual(observed["distribution_name"], original)
            self.assertTrue(records.imports)

    def test_malformed_changed_bytes_do_not_reuse_a_previous_result(self):
        path = self.metadata / "imports.json"
        original = path.read_bytes()
        with catalog.read_only_catalog_provenance_parses():
            first = catalog.read_contained_catalog_imports(self.snapshot)
            path.write_bytes(b'{"schema":"x","schema":"y","imports":[]}')
            with self.assertRaises(catalog.CatalogImportError) as caught:
                catalog.read_contained_catalog_imports(self.snapshot)
            self.assertEqual(caught.exception.code, "catalog.provenance_invalid")
            path.write_bytes(original)
            self.assertEqual(
                catalog.read_contained_catalog_imports(self.snapshot), first
            )

    def test_alias_after_first_read_still_refuses_before_template_lookup(self):
        path = self.metadata / "imports.json"
        original = path.read_bytes()
        private = self.f.root / "private.json"
        private.write_bytes(original)
        identity = private.stat().st_ino
        with catalog.read_only_catalog_provenance_parses():
            catalog.read_contained_catalog_imports(self.snapshot)
            path.rename(path.with_suffix(".original"))
            try:
                path.symlink_to(private)
            except (NotImplementedError, OSError) as error:
                if isinstance(error, NotImplementedError) or getattr(
                    error, "errno", None
                ) in {errno.EPERM, errno.EACCES, errno.ENOSYS, errno.ENOTSUP}:
                    self.skipTest("filesystem cannot create the file-symlink fixture")
                raise
            with self.assertRaises(catalog.CatalogImportError):
                catalog.read_contained_catalog_imports(self.snapshot)
        self.assertEqual(private.read_bytes(), original)
        self.assertEqual(private.stat().st_ino, identity)

    def test_nested_scope_joins_and_isolated_scope_restores_original(self):
        with patch.object(
            catalog,
            "_contained_catalog_records",
            wraps=catalog._contained_catalog_records,
        ) as parses:
            with catalog.read_only_catalog_provenance_parses():
                catalog.read_contained_catalog_imports(self.snapshot)
                with catalog.read_only_catalog_provenance_parses():
                    catalog.read_contained_catalog_imports(self.snapshot)
                self.assertEqual(parses.call_count, 1)
                with catalog.read_only_catalog_provenance_parses(isolated=True):
                    catalog.read_contained_catalog_imports(self.snapshot)
                self.assertEqual(parses.call_count, 2)
                catalog.read_contained_catalog_imports(self.snapshot)
                self.assertEqual(parses.call_count, 2)
            self.assertIsNone(catalog._PROVENANCE_PARSES.get())
            catalog.read_contained_catalog_imports(self.snapshot)
            self.assertEqual(parses.call_count, 3)

    def test_storage_bounds_bypass_reuse_without_rejecting_valid_data(self):
        for name, bound in (
            ("_PROVENANCE_PARSE_MAX_BYTES", 32),
            ("_PROVENANCE_PARSE_MAX_NODES", 1),
            ("_PROVENANCE_PARSE_MAX_ENTRIES", 0),
        ):
            with (
                self.subTest(name=name),
                patch.object(catalog, name, bound),
                catalog.read_only_catalog_provenance_parses(),
                patch.object(
                    catalog,
                    "_contained_catalog_records",
                    wraps=catalog._contained_catalog_records,
                ) as parses,
            ):
                first = catalog.read_contained_catalog_imports(self.snapshot)
                self.assertEqual(
                    catalog.read_contained_catalog_imports(self.snapshot), first
                )
                self.assertEqual(parses.call_count, 2)
                self.assertEqual(catalog._PROVENANCE_PARSES.get().templates, {})

    def test_mutable_document_arguments_preserve_original_uncached_contract(self):
        documents = [
            bytearray(value) if value is not None else None
            for value in catalog._catalog_provenance(self.snapshot)
        ]
        with (
            catalog.read_only_catalog_provenance_parses(),
            patch.object(
                catalog,
                "_contained_catalog_records",
                wraps=catalog._contained_catalog_records,
            ) as parses,
        ):
            first = catalog._parse_provenance(documents, contained=True)
            self.assertEqual(
                catalog._parse_provenance(documents, contained=True), first
            )
            self.assertEqual(parses.call_count, 2)

    def test_accounting_includes_instance_dictionary_and_extra_data(self):
        from dataclasses import dataclass

        @dataclass
        class Data:
            value: str

        value = Data("small")
        value.extra = b"x" * 8192
        with patch.object(catalog, "_PROVENANCE_PARSE_MAX_BYTES", 4096):
            self.assertIsNone(catalog._provenance_parse_size((), value))

    def test_uncopyable_data_falls_back_without_retaining_a_template(self):
        from copy import Error as CopyError

        for failure in (CopyError, RecursionError, MemoryError, TypeError):
            with (
                self.subTest(failure=failure.__name__),
                catalog.read_only_catalog_provenance_parses(),
                patch.object(catalog, "deepcopy", side_effect=failure),
                patch.object(
                    catalog,
                    "_contained_catalog_records",
                    wraps=catalog._contained_catalog_records,
                ) as parses,
            ):
                first = catalog.read_contained_catalog_imports(self.snapshot)
                self.assertEqual(
                    catalog.read_contained_catalog_imports(self.snapshot), first
                )
                self.assertEqual(parses.call_count, 2)
                self.assertEqual(catalog._PROVENANCE_PARSES.get().templates, {})

    def test_hit_copy_failure_reparses_current_bytes_and_keeps_template_private(self):
        with (
            catalog.read_only_catalog_provenance_parses(),
            patch.object(
                catalog,
                "_contained_catalog_records",
                wraps=catalog._contained_catalog_records,
            ) as parses,
        ):
            first = catalog.read_contained_catalog_imports(self.snapshot)
            with patch.object(catalog, "deepcopy", side_effect=RecursionError):
                second = catalog.read_contained_catalog_imports(self.snapshot)
                self.assertEqual(first, second)
                object.__setattr__(second, "imports", ())
            self.assertEqual(
                catalog.read_contained_catalog_imports(self.snapshot), first
            )
            self.assertEqual(parses.call_count, 2)

    def test_legacy_parse_cannot_satisfy_strict_contained_parse(self):
        origin, records = catalog._catalog_provenance(self.snapshot)
        duplicate = records.replace(
            b'"schema":', b'"schema":"legacy-only","schema":', 1
        )
        self.assertNotEqual(duplicate, records)
        with catalog.read_only_catalog_provenance_parses():
            legacy = catalog._parse_provenance((origin, duplicate), contained=False)
            self.assertTrue(legacy[1].imports)
            with self.assertRaises(catalog.CatalogImportError) as caught:
                catalog._parse_provenance((origin, duplicate), contained=True)
            self.assertEqual(caught.exception.code, "catalog.provenance_invalid")
