"""Finite relocation metadata intent from an actually adopted native source tree.

The existing initializer fixture supplies synthetic framework-origin/Standard
observations. These controls do not qualify an installed framework or a layout.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import tempfile
import unittest
from pathlib import Path

from literate_ai.adapters.retained_layout_compiler import (
    compile_retained_layout_transition,
)
from literate_ai.adapters.retained_layout_metadata import layout_component_footer
from literate_ai.adapters.retained_layout_partition import (
    observe_retained_layout_partition,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_layout import (
    RETAINED_LAYOUT_FILE,
    RetainedLayoutDeclaration,
    RetainedLayoutPublication,
)
from literate_ai.contracts.retained_project import RetainedProjectLimits
from literate_ai.projects import load_project, parse_project_configuration
from tests.support.fixtures_test_retained_harness_receipts import (
    _adapter,
    _legacy_project,
    _selectors,
)


def _snapshot(root):
    rows = {}
    for path in root.rglob("*"):
        node = path.lstat()
        rows[path.relative_to(root).as_posix()] = (
            node.st_dev,
            node.st_ino,
            node.st_mode,
            node.st_nlink,
            node.st_uid,
            node.st_gid,
            node.st_size,
            node.st_mtime_ns,
            node.st_ctime_ns,
            os.readlink(path)
            if path.is_symlink()
            else (
                hashlib.sha256(path.read_bytes()).hexdigest()
                if path.is_file()
                else None
            ),
        )
    return rows


@unittest.skipIf(os.name == "nt", "original POSIX source context only")
class RetainedLayoutMetadataTransitionTests(unittest.TestCase):
    def test_complete_intent_preserves_old_evidence_and_requires_renewal(self):
        with tempfile.TemporaryDirectory(prefix="layout-metadata-") as directory:
            root = Path(directory).resolve() / "project"
            _legacy_project(root)
            _adapter().initialize(
                root,
                flavor_selectors=_selectors(root),
                source_intelligence_provider="none",
                convert=True,
                run_baseline=True,
            )
            before = _snapshot(root)
            proposed = RetainedLayoutDeclaration(
                "components/chosen-wrapper", "retained"
            )
            with observe_retained_layout_partition(load_project(root)) as context:
                result = compile_retained_layout_transition(
                    context,
                    proposed,
                    limits=RetainedProjectLimits(10000, 16 * 1024**2, 64 * 1024**2),
                    case_sensitive=True,
                )
                self.assertEqual(
                    result["plan_identity"], canonical_identity(result["plan"]).uri
                )
                program = result["plan"]["metadata_operations"]
                raw = {
                    row["path"]: base64.b64decode(row["new_bytes"], validate=True)
                    for row in program["replacements"]
                }
                publication = RetainedLayoutPublication.from_dict(
                    json.loads(raw[RETAINED_LAYOUT_FILE])
                )
                self.assertEqual(publication.declaration, proposed)
                self.assertTrue(
                    raw[proposed.wrapper_component + "/component.md"].endswith(
                        layout_component_footer(publication.identity)
                    )
                )
                manifest = parse_project_configuration(raw["literate.project.json"])
                self.assertEqual(manifest.test_receipt_policy.suite_version, "2.0.0")
                for name in (
                    "legacy-harness-baseline.json",
                    "legacy-wrapper-parity.json",
                    "legacy-lift-shift.json",
                ):
                    self.assertEqual(
                        json.loads(raw[".literate/" + name])["state"],
                        "requalification-required",
                    )
                self.assertFalse(program["receipt_rewritten"])
                self.assertTrue(program["requalification_required"])
                receipt = load_project(root).definition.test_receipt
                if receipt is not None:
                    self.assertNotIn(receipt, raw)
                for operation in program["retirements"]:
                    self.assertEqual(
                        base64.b64decode(operation["old_bytes"], validate=True),
                        (root / operation["path"]).read_bytes(),
                    )
            self.assertEqual(_snapshot(root), before)
