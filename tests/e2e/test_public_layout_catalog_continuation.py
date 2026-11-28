"""Actual inherited converted-project public layout continuation and rollback."""

from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.repository_lineage import REPOSITORY_PARENT_FILE
from literate_ai.adapters.retained_layout import resolve_structural_layout
from literate_ai.contracts import (
    CatalogImportsFile,
    RepositoryParentReference,
    RepositoryParentSelection,
    canonical_json_bytes,
)
from literate_ai.projects import PROJECT_FILENAME
from tests.e2e import test_retained_harness_receipts as retained
from tests.support.fixtures_test_repository_initialization_e2e import (
    commit_project,
    git,
)


@unittest.skipUnless(os.name == "posix", "original POSIX migration owner")
class PublicCatalogContinuationTests(unittest.TestCase):
    def test_existing_contained_project_places_imported_skill_and_recovers_exactly(
        self,
    ):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            template = workspace / "template"
            retained._legacy_project(template)
            retained._adapter().initialize(
                template,
                flavor_selectors=retained._selectors(template),
                source_intelligence_provider="none",
                convert=True,
            )
            upstream = workspace / "parent"
            upstream.mkdir()
            definition = json.loads((template / PROJECT_FILENAME).read_bytes())
            definition["project_id"] = "layout-continuation-parent"
            (upstream / PROJECT_FILENAME).write_bytes(canonical_json_bytes(definition))
            selection = upstream / REPOSITORY_PARENT_FILE
            selection.parent.mkdir()
            selection.write_bytes(
                canonical_json_bytes(RepositoryParentSelection.root().to_dict())
            )
            skill = "skills/specification-to-source/contained-example/SKILL.md"
            content = (
                b"---\nname: contained-example\ndescription: Layout fixture.\n"
                b"metadata:\n  author: Literate AI maintainers "
                b"<literate-ai-maintainers@users.noreply.github.com>\n"
                b"schema: urn:literate-ai:schema:v1:specification-to-source-skill\n"
                b"skill_id: contained-example\nversion: 1.0.0\ntitle: Layout fixture\n"
                b"stages:\n  - generate\ndependencies: []\nlimitations:\n"
                b"  - Use local fixture inputs.\ntrust: repository-reviewed\n---\n"
                b"# Layout fixture\n\nGenerate the local fixture.\n"
            )
            path = upstream / skill
            path.parent.mkdir(parents=True)
            path.write_bytes(content)
            component = "components/contained-example/component.md"
            component_content = (
                "---\nnamespace: contained-fixture\nversion: 1.0.0\n"
                "display_name: Contained fixture\nprofiles:\n  - application\n"
                "sample: false\nprovides: []\nrequires: []\nauthoring_inputs:\n"
                "  - kind: specification-to-source-skill\n"
                f"    uri: {skill}\n"
                "workflow_definition: workflows/sample-host.md\n"
                "routing_policy: routing/sample-host.json\nflavor_slots: []\n"
                "entrypoints: []\nacceptance_contracts: []\nsource_dependencies: []\n"
                "---\n# Imported contained Component\n"
            ).encode()
            component_path = upstream / component
            component_path.parent.mkdir(parents=True)
            component_path.write_bytes(component_content)
            commit_project(upstream)
            reference = RepositoryParentReference(
                upstream.as_uri(), git(upstream, "rev-parse", "HEAD")
            )
            project = workspace / "consumer"
            retained._legacy_project(project)
            with patch.dict(
                os.environ,
                {"OBJ_DIR": str(workspace / "objects"), "GIT_ALLOW_PROTOCOL": "file"},
            ):
                retained._adapter().initialize(
                    project,
                    flavor_selectors=retained._selectors(project),
                    source_intelligence_provider="none",
                    convert=True,
                    parent_selection=RepositoryParentSelection.inherit((reference,)),
                )
            commit_project(project)
            lift = json.loads(
                (project / ".literate/legacy-lift-shift.json").read_bytes()
            )
            application = resolve_structural_layout(project, lift).implementation_root
            app = application / "app.py"
            before_app = app.read_bytes()
            index = git(project, "ls-files", "--stage", "-z")
            head = git(project, "rev-parse", "HEAD")

            def layout(command, *arguments):
                status, packet = retained._invoke(
                    "--json",
                    "project",
                    "layout",
                    command,
                    "--project",
                    str(project),
                    *arguments,
                )
                self.assertEqual(status, 0, packet)
                return packet["result"]

            def reviewed(scope):
                plan = layout("plan", "--migration", *scope)
                approval = tuple(
                    value
                    for name in sorted(
                        {item["path"] for item in plan["blocked_references"]}
                    )
                    for value in ("--rewrite-reference", name)
                )
                return layout("plan", "--migration", *scope, *approval), approval

            legacy, approval = reviewed(())
            legacy_identity = legacy["plan_identity"]
            layout(
                "apply", "--acknowledge", "--plan-identity", legacy_identity, *approval
            )
            framework_inode = (project / "litai").stat().st_ino
            original = (project / skill).read_bytes()
            original_inode = (project / skill).stat().st_ino
            original_component_inode = (project / component).stat().st_ino
            self.assertEqual((project / component).read_bytes(), component_content)
            imports_before = CatalogImportsFile.load(project)
            self.assertIsNotNone(imports_before)
            scope = ("--place-imported-catalogs",)
            plan, approval = reviewed(scope)
            self.assertEqual(plan["transaction_mode"], "contained-catalog-continuation")
            self.assertIn(skill, plan["placements"])
            self.assertIn(component, plan["placements"])
            self.assertFalse(plan["full_containment"])
            identity = plan["plan_identity"]
            selected_skill = project / skill
            selected_skill.write_bytes(original + b"\nLocal authority changed.\n")
            status, packet = retained._invoke(
                "--json",
                "project",
                "layout",
                "apply",
                "--project",
                str(project),
                "--acknowledge",
                "--plan-identity",
                identity,
                *scope,
                *approval,
            )
            self.assertEqual(status, 2, packet)
            self.assertEqual(packet["error"]["code"], "project.layout.plan_stale")
            self.assertEqual(
                selected_skill.read_bytes(), original + b"\nLocal authority changed.\n"
            )
            self.assertFalse((project / "litai" / skill).exists())
            selected_skill.write_bytes(original)
            repeated, repeated_approval = reviewed(scope)
            self.assertEqual(repeated["plan_identity"], identity)
            self.assertEqual(repeated_approval, approval)
            applied = layout(
                "apply",
                "--acknowledge",
                "--plan-identity",
                identity,
                *scope,
                *approval,
            )
            self.assertTrue(applied["applied"])
            self.assertEqual(applied["plan"], plan)
            self.assertEqual(
                (project / "litai" / component).read_bytes(), component_content
            )
            self.assertFalse((project / component).exists())
            self.assertEqual((project / "litai" / skill).read_bytes(), original)
            self.assertFalse((project / skill).exists())
            self.assertEqual((project / "litai").stat().st_ino, framework_inode)
            self.assertEqual(app.read_bytes(), before_app)
            self.assertEqual(git(project, "ls-files", "--stage", "-z"), index)
            self.assertEqual(git(project, "rev-parse", "HEAD"), head)
            imports_after = CatalogImportsFile.load(project)
            self.assertEqual(
                tuple(item.source for item in imports_before.imports),
                tuple(item.source for item in imports_after.imports),
            )
            stdout, stderr = io.StringIO(), io.StringIO()
            descendant_status = retained.main(
                ("--json", "project", "layout", "plan", "--project", str(application)),
                stdout=stdout,
                stderr=stderr,
            )
            self.assertEqual(
                descendant_status,
                1,
                {"stdout": stdout.getvalue(), "stderr": stderr.getvalue()},
            )
            descendant = json.loads(stdout.getvalue())
            self.assertTrue(descendant["ok"])
            self.assertFalse(descendant["result"]["planning_complete"])
            self.assertEqual(descendant["result"]["project_id"], plan["project_id"])
            self.assertEqual(
                descendant["result"]["manifest"], "litai/" + PROJECT_FILENAME
            )
            root_stdout, root_stderr = io.StringIO(), io.StringIO()
            root_status = retained.main(
                ("--json", "project", "layout", "plan", "--project", str(project)),
                stdout=root_stdout,
                stderr=root_stderr,
            )
            self.assertEqual(root_status, descendant_status, root_stderr.getvalue())
            self.assertEqual(json.loads(root_stdout.getvalue()), descendant)
            placed = project / "litai" / skill
            placed.write_bytes(original + b"\nConcurrent owner change.\n")
            status, packet = retained._invoke(
                "--json",
                "project",
                "layout",
                "recover",
                "--project",
                str(project),
                "--acknowledge",
                "--plan-identity",
                identity,
            )
            self.assertEqual(status, 2, packet)
            self.assertEqual(
                packet["error"]["code"], "project.layout.recovery_conflict"
            )
            self.assertEqual(
                placed.read_bytes(), original + b"\nConcurrent owner change.\n"
            )
            self.assertFalse((project / skill).exists())
            placed.write_bytes(original)
            recovered = layout("recover", "--acknowledge", "--plan-identity", identity)
            self.assertIn(
                "litai/components/contained-example", recovered["retained_scaffolding"]
            )
            layout("recover", "--acknowledge", "--plan-identity", identity)
            self.assertEqual((project / component).read_bytes(), component_content)
            self.assertEqual(
                (project / component).stat().st_ino, original_component_inode
            )
            self.assertEqual((project / skill).read_bytes(), original)
            self.assertEqual((project / skill).stat().st_ino, original_inode)
            self.assertEqual((project / "litai").stat().st_ino, framework_inode)
            self.assertEqual(CatalogImportsFile.load(project), imports_before)
            self.assertEqual(app.read_bytes(), before_app)
            self.assertEqual(git(project, "ls-files", "--stage", "-z"), index)
            self.assertEqual(git(project, "rev-parse", "HEAD"), head)
            self.assertTrue(Path(applied["journal"]).is_dir())
            self.assertTrue((project / ".git/literate-layout-migration").is_dir())
