"""Explicit source-reader diagnostic using retained installed-project metadata.

This proves template admission and fresh native reads for the real dataset. It
is not installed-CLI performance, native lifecycle or release qualification.
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters import catalog_import as catalog
from literate_ai.projects import ProjectConfigurationStore


class ActualCatalogTemplateAdmission(unittest.TestCase):
    def test_real_retained_catalog_keeps_native_reads_and_admits_one_private_template(
        self,
    ):
        project = Path(os.environ["LITAI_INSTALLED_LAYOUT_PROJECT"]).absolute()
        parent = Path(os.environ["LITAI_INSTALLED_LAYOUT_OUTPUT"]).absolute()
        require_safe_directory(project)
        require_safe_directory(parent)
        output = Path(tempfile.mkdtemp(prefix="ia-parse-", dir=parent))
        snapshot = ProjectConfigurationStore.discover(project)
        started = time.monotonic()
        with (
            catalog.read_only_catalog_provenance_parses(),
            patch.object(
                catalog,
                "_contained_catalog_records",
                wraps=catalog._contained_catalog_records,
            ) as parses,
            patch.object(
                catalog, "_provenance_bytes", wraps=catalog._provenance_bytes
            ) as reads,
        ):
            first = catalog.read_contained_catalog_imports(snapshot)
            for _ in range(3):
                self.assertEqual(
                    catalog.read_contained_catalog_imports(snapshot), first
                )
            self.assertEqual(parses.call_count, 1)
            self.assertEqual(reads.call_count, 8)
            frame = catalog._PROVENANCE_PARSES.get()
            self.assertEqual(len(frame.templates), 1)
            self.assertLessEqual(
                frame.retained_bytes, catalog._PROVENANCE_PARSE_MAX_BYTES
            )
            result = {
                "scope": "Source-reader admission diagnostic, actual retained dataset",
                "release_qualification": False,
                "catalog_items": len(first.imports),
                "native_reads": reads.call_count,
                "strict_parses": parses.call_count,
                "retained_bytes": frame.retained_bytes,
                "elapsed_seconds": time.monotonic() - started,
            }
        self.assertEqual(
            result["catalog_items"],
            int(os.environ["LITAI_INSTALLED_LAYOUT_CATALOG_ITEMS"]),
        )
        (output / "receipt.json").write_text(json.dumps(result, indent=2) + "\n")
        print("retained source-reader diagnostic:", output, flush=True)
