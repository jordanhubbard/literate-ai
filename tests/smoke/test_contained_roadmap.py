"""Roadmap validators keep selected framework and declared host namespaces distinct."""

from __future__ import annotations

import json
import posixpath
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from literate_ai.adapters.project_validation import (
    ProjectValidationError,
    _documentation_catalog,
)

QUEUE = "# Work\n\n### [ ] NAMESPACE-001 — Work\n\n"


class ContainedRoadmapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()

    def fixture(self, prefix="litai/", *, historical=False):
        self.prefix = prefix
        self.queue = prefix + "docs/roadmap/active-work.md"
        self.plan = prefix + (
            "docs/history/roadmap/program.md"
            if historical
            else "docs/roadmap/program.md"
        )
        guide = prefix + "docs/README.md"
        owner = posixpath.relpath(self.queue, posixpath.dirname(self.plan))
        self.documents = {
            guide: "# Guide\n\n[Work](roadmap/active-work.md)\n[Plan]("
            + posixpath.relpath(self.plan, posixpath.dirname(guide))
            + ")\n",
            self.queue: QUEUE,
            self.plan: "# Program\n\n- **Status:** "
            + ("historical" if historical else "active")
            + "\n- **Owning queue item:** [NAMESPACE-001]("
            + owner
            + "#namespace-001-work)\n"
            + "- **Completion / archival evidence:** pending\n",
        }
        self.skill = prefix + "SKILL.md"
        self.put(self.skill, "# Skill\n\n[Guide](docs/README.md)\n")
        self.roots = [prefix + "docs"]
        return self

    def put(self, path, content):
        p = self.root / path
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def validate(self):
        for name, content in self.documents.items():
            self.put(name, content)
        project = SimpleNamespace(
            root=self.root,
            agent_skill=self.root / self.skill,
            definition=SimpleNamespace(
                agent_skill=self.skill,
                framework_directory="litai" if self.prefix else None,
            ),
            roots=lambda kind: tuple(self.root / path for path in self.roots),
        )
        return _documentation_catalog(project)

    def refused(self, code):
        with self.assertRaises(ProjectValidationError) as caught:
            self.validate()
        self.assertEqual(caught.exception.code, code)

    def test_legacy_and_contained_plans_pass_the_real_project_adapter(self):
        for prefix in ("", "litai/"):
            with self.subTest(prefix=prefix):
                self.fixture(prefix)
                self.assertIn(self.queue, self.validate()["document_contents"])

    def test_contained_plan_cannot_skip_its_lifecycle_header(self):
        self.fixture().documents[self.plan] = "# Missing lifecycle header\n"
        self.refused("project.roadmap_lifecycle_header_missing")

    def test_host_queue_with_same_id_cannot_replace_missing_framework_queue(self):
        self.fixture()
        del self.documents[self.queue]
        self.documents["docs/roadmap/active-work.md"] = QUEUE
        self.documents["docs/README.md"] = (
            "# Application\n\n[Work](roadmap/active-work.md)\n"
        )
        self.documents["litai/docs/README.md"] += (
            "\n[Application](../../docs/README.md)\n"
        )
        self.roots.append("docs")
        self.refused("project.roadmap_lifecycle_queue_missing")

    def test_cross_namespace_owner_is_rejected_even_with_matching_ids(self):
        self.fixture()
        self.documents["docs/roadmap/active-work.md"] = QUEUE
        self.documents["docs/README.md"] = (
            "# Application\n\n[Work](roadmap/active-work.md)\n"
        )
        self.documents["litai/docs/README.md"] += (
            "\n[Application](../../docs/README.md)\n"
        )
        self.roots.append("docs")
        self.documents[self.plan] = self.documents[self.plan].replace(
            "(active-work.md#", "(../../../docs/roadmap/active-work.md#"
        )
        self.refused("project.roadmap_lifecycle_owner_invalid")

    def test_framework_queue_cycle_is_rejected(self):
        self.fixture().documents[self.queue] += (
            "- **Completion prerequisites:** NAMESPACE-001\n"
        )
        self.refused("roadmap.dependency_cycle")

    def test_undeclared_host_queue_does_not_control_framework_validation(self):
        self.fixture()
        self.put(
            "docs/roadmap/active-work.md",
            QUEUE + "- **Completion prerequisites:** NAMESPACE-001\n",
        )
        self.assertIn(self.queue, self.validate()["document_contents"])

    def test_declared_host_plans_keep_their_lifecycle_checks(self):
        self.fixture()
        self.roots.append("docs")
        self.documents["docs/README.md"] = "# Host\n\n[Plan](roadmap/host.md)\n"
        self.documents["docs/roadmap/active-work.md"] = QUEUE
        self.documents["docs/roadmap/host.md"] = "# Invalid host plan\n"
        self.documents["litai/docs/README.md"] += "\n[Host](../../docs/README.md)\n"
        self.refused("project.roadmap_lifecycle_header_missing")

    def test_archived_framework_plan_requires_linked_evidence(self):
        self.fixture(historical=True)
        self.refused("project.roadmap_lifecycle_evidence_missing")

    def test_host_and_framework_plans_validate_independently(self):
        self.fixture()
        self.roots.append("docs")
        self.documents["docs/README.md"] = "# Host\n\n[Plan](roadmap/host.md)\n"
        self.documents["docs/roadmap/active-work.md"] = QUEUE
        self.documents["docs/roadmap/host.md"] = self.documents[self.plan]
        self.documents["litai/docs/README.md"] += "\n[Host](../../docs/README.md)\n"
        documents = self.validate()["document_contents"]
        self.assertIn(self.queue, documents)
        self.assertIn("docs/roadmap/active-work.md", documents)

    def test_framework_owner_heading_must_exist(self):
        self.fixture()
        self.documents[self.plan] = self.documents[self.plan].replace(
            "#namespace-001-work", "#missing-work"
        )
        self.refused("project.roadmap_lifecycle_owner_dangling")

    def test_framework_plan_status_cannot_conflict_with_its_location(self):
        self.fixture()
        self.documents[self.plan] = self.documents[self.plan].replace(
            "**Status:** active", "**Status:** historical"
        )
        self.refused("project.roadmap_lifecycle_location_invalid")

    def test_contained_release_manifest_cycles_are_checked_before_graph_use(self):
        self.fixture()
        self.put(
            "litai/literate.release.json",
            json.dumps(
                {"contributions": {"roadmap_goal_manifest": "litai/release-goals.json"}}
            ),
        )
        self.put(
            "litai/release-goals.json",
            json.dumps(
                {
                    "roadmap": self.queue,
                    "releases": {"1.4.0": [{"id": "NAMESPACE-001"}]},
                }
            ),
        )
        self.documents[self.queue] += (
            "- **Release target:** 1.4.0\n"
            "- **Completion prerequisites:** release:1.4.0:ready\n"
        )
        self.refused("roadmap.dependency_cycle")


if __name__ == "__main__":
    unittest.main()
