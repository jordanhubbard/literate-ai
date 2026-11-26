"""Queue replacement respects selected namespace and retained owner custody."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.project_updates import _protect_dangling_roadmap_queue_owners
from literate_ai.contracts import ProjectUpdateClassification as Kind
from literate_ai.contracts import ProjectUpdateFile
from literate_ai.projects import ProjectContext


class UpdateRoadmapOwnerTests(unittest.TestCase):
    def check_owner(self, prefix, replacement, *, target=None, observed=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            framework = root / prefix if prefix else root
            framework.mkdir(exist_ok=True)
            queue = prefix + "docs/roadmap/active-work.md"
            plan = prefix + "docs/roadmap/native-rewrite-program.md"
            content = (
                "# Native rewrite\n\n- **Status:** active\n"
                "- **Owning queue item:** [ADOPT-002]("
                + (target or "active-work.md#adopt-002")
                + ")\n- **Completion / archival evidence:** pending\n"
            ).encode()
            path = root / plan
            path.parent.mkdir(parents=True)
            path.write_bytes(content)
            files = (
                ProjectUpdateFile(queue, Kind.UPSTREAM_ONLY, None, None, None),
                ProjectUpdateFile(plan, Kind.PRESERVED_DYNAMIC, None, None, None),
            )
            reads = []

            class Observation:
                def read(self, relative, *, optional=False):
                    reads.append(relative)
                    self.assert_optional = optional
                    return content

            observation = Observation() if observed else None
            with patch(
                "literate_ai.adapters.project_updates.ProjectConfigurationStore.context",
                return_value=ProjectContext.observe(root, framework),
            ):
                result = _protect_dangling_roadmap_queue_owners(
                    root, files, {queue: replacement}, observation
                )
            self.assertEqual(path.read_bytes(), content)
            self.assertFalse((root / queue).exists())
            self.assertEqual(result[1], files[1])
            if observed:
                self.assertEqual(reads, [plan])
                self.assertTrue(observation.assert_optional)
            return result[0].classification

    def test_root_and_contained_queue_replacements_cannot_orphan_retained_owner(self):
        for prefix in ("", "litai/"):
            with self.subTest(prefix=prefix):
                self.assertEqual(self.check_owner(prefix, b"# Work\n"), Kind.CONFLICT)

    def test_root_and_contained_queue_replacements_keep_existing_owner(self):
        for prefix in ("", "litai/"):
            with self.subTest(prefix=prefix):
                self.assertEqual(
                    self.check_owner(prefix, b"# Work\n\n### ADOPT-002\n"),
                    Kind.UPSTREAM_ONLY,
                )

    def test_host_owner_cannot_substitute_for_selected_framework_owner(self):
        self.assertEqual(
            self.check_owner(
                "litai/",
                b"# Work\n\n### ADOPT-002\n",
                target="../../../docs/roadmap/active-work.md#adopt-002",
            ),
            Kind.CONFLICT,
        )

    def test_contained_guard_uses_existing_observation_reader(self):
        self.assertEqual(
            self.check_owner("litai/", b"# Work\n", observed=True), Kind.CONFLICT
        )
