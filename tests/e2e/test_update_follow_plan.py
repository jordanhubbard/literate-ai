from __future__ import annotations

import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.project_updates import FilesystemProjectUpdateAdapter
from literate_ai.adapters.repository_lineage import FilesystemRepositoryLineageStore
from literate_ai.cli.errors import CliFailure
from literate_ai.cli.project import update_project_from_args
from literate_ai.contracts import (
    RepositoryParentSelection,
)
from literate_ai.projects import load_project
from tests.support.fixtures_test_repository_updates import origin
from tests.support.root_parent_adapter import (
    RootParentProjectInitializationAdapter as FilesystemProjectInitializationAdapter,
)


class UpdateFollowPlanTests(unittest.TestCase):
    def test_exact_git_revisions_plan_and_apply_the_same_skill_changes(self):
        self._prove_real_git_follow(empty=True)

    def test_real_git_follow_preserves_a_starter_component(self):
        self._prove_real_git_follow(empty=False)

    def _prove_real_git_follow(self, *, empty):
        import os

        from literate_ai.adapters import project_initialization as init_module
        from literate_ai.adapters.repository_lineage import repository_parent_reference
        from tests.support.fixtures_test_repository_initialization_e2e import (
            commit_project,
            git,
        )

        go_skill = "skills/specification-to-source/go-portable-application/SKILL.md"
        legacy_templates = {
            k: v for k, v in init_module._TEMPLATE_FILES.items() if k != go_skill
        }

        def initialize(target, selection):
            # Build the A-side with the pre-repair distribution's exact omission.
            with patch.dict(init_module._TEMPLATE_FILES, legacy_templates, clear=True):
                return FilesystemProjectInitializationAdapter(
                    standard_binding_provider=lambda: None,
                    initialization_origin_provider=origin,
                ).initialize(
                    target,
                    flavor_selectors=("+python", "+macos"),
                    source_intelligence_provider="none",
                    parent_selection=selection,
                    empty=empty,
                )

        with tempfile.TemporaryDirectory() as directory:
            temporary = Path(directory)
            parent = temporary / "parent"
            child = temporary / "derived"
            with patch.dict(os.environ, {"OBJ_DIR": str(temporary / "objects")}):
                initialize(parent, RepositoryParentSelection.root())
                parent_skills = load_project(parent).framework_root / "skills"

                def write_skill(name, text):
                    p = parent_skills / name / "SKILL.md"
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(
                        f"---\nname: {name}\n"
                        "description: Local Git update fixture.\n---\n\n"
                        f"# {name}\n\n{text}\n",
                        encoding="utf-8",
                        newline="\n",
                    )
                    return p.relative_to(parent).as_posix()

                def child_path(parent_path):
                    # Both trees are contained; follow each one's framework root.
                    logical = (parent / parent_path).relative_to(parent_skills.parent)
                    return (child_framework / logical).relative_to(child).as_posix()

                parent_changed = write_skill("git-follow-change", "Revision A.")
                parent_conflict = write_skill("git-follow-conflict", "Revision A.")
                commit_project(parent)
                revision_a = git(parent, "rev-parse", "HEAD")
                initialize(
                    child,
                    RepositoryParentSelection.inherit(
                        (repository_parent_reference(str(parent) + "#" + revision_a),)
                    ),
                )
                child_framework = load_project(child).framework_root
                changed = child_path(parent_changed)
                conflict = child_path(parent_conflict)
                go_path = (child_framework / go_skill).relative_to(child).as_posix()
                local = child / conflict
                local.write_text(
                    local.read_text() + "\nLocal ownership.\n",
                    encoding="utf-8",
                    newline="\n",
                )
                write_skill("git-follow-change", "Revision B.")
                write_skill("git-follow-conflict", "Upstream revision B.")
                parent_added = write_skill("git-follow-added", "Added by B.")
                added = child_path(parent_added)
                git(parent, "add", parent_skills.relative_to(parent).as_posix())
                git(parent, "commit", "-m", "Advance parent skills to B")
                revision_b = git(parent, "rev-parse", "HEAD")
                before = {
                    p.relative_to(child).as_posix(): p.read_bytes()
                    for p in child.rglob("*")
                    if p.is_file()
                }
                args = Namespace(
                    path=child,
                    apply=False,
                    adopt_added=True,
                    record_work_items=False,
                    unpin=False,
                    follow_ref=revision_b,
                    allow_major=False,
                    review_conflicts=False,
                )
                with patch(
                    "literate_ai.cli.project.FilesystemProjectUpdateAdapter",
                    side_effect=lambda **kw: FilesystemProjectUpdateAdapter(
                        origin_provider=origin, **kw
                    ),
                ):
                    plan = update_project_from_args(args)
                    self.assertEqual(
                        before,
                        {
                            p.relative_to(child).as_posix(): p.read_bytes()
                            for p in child.rglob("*")
                            if p.is_file()
                        },
                    )
                    files = {f["path"]: f for f in plan["repository_lineage"]["files"]}
                    self.assertEqual(files[changed]["classification"], "upstream-only")
                    self.assertEqual(files[conflict]["classification"], "conflict")
                    self.assertEqual(files[added]["classification"], "upstream-added")
                    framework_files = {f["path"]: f for f in plan["framework"]["files"]}
                    self.assertEqual(
                        framework_files[go_path]["classification"], "upstream-added"
                    )
                    args.apply = True
                    if empty:
                        original_template = init_module._template_text

                        def incomplete_template(resource):
                            content = original_template(resource)
                            return (
                                content.replace(
                                    "go-portable-application", "missing-go-authority"
                                )
                                if resource == "flavors/lang-go/flavor.md"
                                else content
                            )

                        with patch(
                            "literate_ai.adapters.project_updates._template_text",
                            side_effect=incomplete_template,
                        ):
                            with self.assertRaises(CliFailure) as rejected:
                                update_project_from_args(args)
                        self.assertIn("validation", str(rejected.exception))
                        self.assertEqual(
                            before,
                            {
                                p.relative_to(child).as_posix(): p.read_bytes()
                                for p in child.rglob("*")
                                if p.is_file()
                            },
                        )
                    applied = update_project_from_args(args)
                self.assertTrue((child / go_path).is_file())
                self.assertEqual(
                    plan["repository_lineage"]["files"],
                    applied["repository_lineage"]["files"],
                )
                self.assertEqual(
                    plan["repository_lineage"]["identity"],
                    applied["repository_lineage"]["identity"],
                )
                self.assertEqual(plan["parent_selectors"], applied["parent_selectors"])
                self.assertEqual(
                    (child / changed).read_bytes(),
                    (parent / parent_changed).read_bytes(),
                )
                self.assertEqual(
                    (child / added).read_bytes(), (parent / parent_added).read_bytes()
                )
                self.assertEqual(local.read_bytes(), before[conflict])
                self.assertEqual(
                    FilesystemRepositoryLineageStore(child)
                    .load()[0]
                    .parents[0]
                    .requested_revision,
                    revision_b,
                )
