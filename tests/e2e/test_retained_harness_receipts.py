"""End-to-end retained-harness receipt and promotion regressions."""

from __future__ import annotations

import io
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters.harness_inventory import (
    HARNESS_PARITY_SCHEMA,
    execute_retained_harness,
)
from literate_ai.adapters.project_initialization import (
    detect_repo_flavors,
    host_platform_selector,
    record_project_authority_review,
)
from literate_ai.adapters.project_scaffold_placement import ScaffoldLayout
from literate_ai.adapters.retained_evidence_migration import (
    LEGACY_WRAPPER_PARITY_SCHEMA_V1,
    migrate_retained_evidence,
)
from literate_ai.adapters.retained_harness_receipts import (
    retained_harness_receipt_policy,
    retained_harness_worker_identity,
)
from literate_ai.adapters.retained_harness_remote import (
    RetainedHarnessRemoteError,
    RetainedHarnessRemoteResult,
)
from literate_ai.adapters.retained_layout import (
    LEGACY_WRAPPER_COMPONENT,
    RetainedLayoutDeclaration,
)
from literate_ai.cli import main
from literate_ai.contracts import (
    CatalogImportsFile,
    ExecutionRequirements,
    ExecutionWorker,
    ExecutionWorkerCatalog,
    ExecutionWorkerKind,
    ProjectInitializationOrigin,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.projects import PROJECT_FILENAME
from tests.support.root_parent_adapter import (
    RootParentProjectInitializationAdapter as FilesystemProjectInitializationAdapter,
)


def _origin() -> ProjectInitializationOrigin:
    return ProjectInitializationOrigin(
        repository_url="ssh://git.example.test/operator/literate-ai.git",
        git_revision="c" * 40,
        distribution_name="literate-ai",
        distribution_version="0.9.0",
    )


class _LegacyMigrationInitializationAdapter(FilesystemProjectInitializationAdapter):
    """Build the old root layout that these compatibility/migration cases consume.

    Actual new contained creation/conversion is exercised separately by the
    scaffold publication cohort. Root-parent selection itself remains contained.
    """

    def initialize(self, target, **kwargs):
        kwargs["_layout"] = ScaffoldLayout.LEGACY_ROOT_FIXTURE
        return super().initialize(target, **kwargs)


def _adapter() -> FilesystemProjectInitializationAdapter:
    return _LegacyMigrationInitializationAdapter(
        initialization_origin_provider=_origin,
        standard_binding_provider=lambda: None,
    )


def _selectors(target: Path) -> tuple[str, ...]:
    return (
        *(f"+{selector}" for selector in detect_repo_flavors(target)),
        host_platform_selector(),
    )


def _invoke(*arguments: str) -> tuple[int, dict[str, object]]:
    stdout = io.StringIO()
    stderr = io.StringIO()
    status = main(arguments, stdout=stdout, stderr=stderr)
    content = stdout.getvalue() if status == 0 else stderr.getvalue()
    return status, json.loads(content)


def _legacy_project(target: Path, test_summary: str = "Ran 2 tests") -> None:
    target.mkdir()
    (target / "app.py").write_text("print('retained')\n", encoding="utf-8")
    (target / "Makefile").write_text(
        "build:\n"
        "\tmkdir -p build\n"
        "\tprintf 'artifact\\n' > build/app\n"
        "test:\n"
        f"\t@printf '{test_summary}\\n'\n"
        "\t@printf 'OK\\n'\n"
        "package:\n"
        "\tmkdir -p dist\n"
        "\tprintf 'package\\n' > dist/app.txt\n",
        encoding="utf-8",
    )


def _write_workers(path: Path, *workers: ExecutionWorker) -> None:
    path.write_bytes(
        canonical_json_bytes(ExecutionWorkerCatalog(tuple(workers)).to_dict())
    )


class RetainedHarnessReceiptTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize the default converted project once; tests copy it.
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.template = Path(temporary.name).resolve() / "converted"
        _legacy_project(cls.template)
        cls.initialized = _adapter().initialize(
            cls.template,
            flavor_selectors=_selectors(cls.template),
            source_intelligence_provider="none",
            convert=True,
        )

    @unittest.skipUnless(os.name == "posix", "requires POSIX exclusive rename")
    def test_converted_release_policy_placement_preserves_authority_and_rollback(self):
        from tests.support.fixtures_test_schema_catalog import V2_ROOT, SchemaCatalog

        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            project = workspace / "consumer"
            shutil.copytree(self.template, project)
            if not (project / CatalogImportsFile.PATH).exists():
                CatalogImportsFile(()).save(project)
            policy = project / "literate.release.json"
            legacy = json.loads(policy.read_bytes())
            legacy["schema"] = "literate-ai/release-policy@1"
            for key in ("contributions", "default_branch", "collateral"):
                legacy.pop(key, None)
            legacy["provider"] = None
            legacy["gate"]["argv"][2] = LEGACY_WRAPPER_COMPONENT
            policy.write_bytes(canonical_json_bytes(legacy))
            original = policy.read_bytes()

            def command(*arguments):
                return _invoke("--json", *arguments, "--project", str(project))

            def git(*arguments):
                return subprocess.check_output(
                    ["git", "-C", str(project), *arguments], timeout=15
                )

            git("init", "-q", "-b", "main")
            git("add", ".")
            git(
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "-qm",
                "converted repository",
            )
            remote = workspace / "origin.git"
            git("clone", "--bare", "--no-hardlinks", ".", str(remote))
            git("remote", "add", "origin", str(remote))
            index = git("ls-files", "--stage", "-z")
            head = git("rev-parse", "HEAD")
            status, packet = command("release", "plan", "--bump", "patch")
            self.assertEqual(status, 0, packet)
            before = packet["result"]
            old_plan = workspace / "old-plan.json"
            old_plan.write_bytes(canonical_json_bytes(before))
            selection = ("--place-release-policy",)
            status, packet = command(
                "project", "layout", "plan", "--migration", *selection
            )
            self.assertEqual(status, 0, packet)
            references = {
                item["path"] for item in packet["result"]["blocked_references"]
            }
            self.assertTrue(
                references <= {"docs/user/releasing.md", "docs/user/project-layout.md"},
                references,
            )
            for reference in sorted(references):
                selection += ("--rewrite-reference", reference)
            status, packet = command(
                "project", "layout", "plan", "--migration", *selection
            )
            self.assertEqual(status, 0, packet)
            intent = (
                "--acknowledge",
                "--plan-identity",
                packet["result"]["plan_identity"],
            )
            status, packet = command("project", "layout", "apply", *intent, *selection)
            self.assertEqual(status, 0, packet)
            contained = project / "litai" / policy.name
            self.assertFalse(policy.exists())
            self.assertEqual(contained.read_bytes(), original)
            status, packet = command("release", "plan", "--bump", "patch")
            self.assertEqual(status, 0, packet)
            after = packet["result"]
            SchemaCatalog(V2_ROOT).validate(after["schema"], after)
            self.assertIn("authority_placement_identity", after)
            for key in (
                "policy_identity",
                "version_bindings",
                "gate",
                "changelog",
                "next_version",
            ):
                self.assertEqual(after[key], before[key])
            output = workspace / "prepared.json"
            status, packet = command(
                "release", "check", str(old_plan), "--output", str(output)
            )
            self.assertEqual(status, 2, packet)
            self.assertEqual(packet["error"]["code"], "release.plan_stale")
            self.assertFalse(output.exists())

            no_authority = b"host-owned policy\n"
            policy.write_bytes(no_authority)
            status, packet = command("release", "state")
            self.assertEqual(status, 2, packet)
            self.assertEqual(packet["error"]["code"], "release.policy_ambiguous")
            self.assertEqual(policy.read_bytes(), no_authority)
            policy.unlink()

            status, packet = command("project", "layout", "recover", *intent)
            self.assertEqual(status, 0, packet)
            self.assertFalse(contained.exists())
            self.assertEqual(policy.read_bytes(), original)
            self.assertEqual(git("ls-files", "--stage", "-z"), index)
            self.assertEqual(git("rev-parse", "HEAD"), head)

    @unittest.skipUnless(os.name == "posix", "requires POSIX exclusive rename")
    def test_public_layout_migration_edits_only_reviewed_link_and_rolls_back(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve() / "consumer"
            shutil.copytree(self.template, project)
            imports = project / CatalogImportsFile.PATH
            if not imports.exists():
                CatalogImportsFile(()).save(project)
            document = project / "docs/user/project-layout.md"
            document.write_bytes(
                document.read_bytes()
                + b"\nSee the [project manifest](../../literate.project.json).\n"
            )
            before = document.read_bytes()
            manifest = project / PROJECT_FILENAME
            inode = manifest.stat().st_ino
            original = manifest.read_bytes()

            def git(*arguments):
                return subprocess.check_output(
                    ["git", "-C", str(project), *arguments], timeout=15
                )

            git("init", "-q")
            git("add", ".")
            git(
                "-c",
                "user.name=Fixture",
                "-c",
                "user.email=fixture@example.test",
                "commit",
                "-qm",
                "converted repository",
            )
            index = git("ls-files", "--stage", "-z")

            def action(verb, *args):
                return _invoke(
                    "--json",
                    "project",
                    "layout",
                    verb,
                    "--project",
                    str(project),
                    *args,
                )

            status, packet = action("plan", "--migration")
            self.assertEqual(status, 0, packet)
            self.assertFalse(packet["result"]["applicable"])
            arguments = (
                "--acknowledge",
                "--plan-identity",
                packet["result"]["plan_identity"],
            )
            status, packet = action("apply", *arguments)
            self.assertEqual(status, 2, packet)
            self.assertEqual(
                packet["error"]["code"], "project.layout.reference_authority"
            )
            self.assertTrue(manifest.exists())
            self.assertFalse((project / "litai").exists())
            approval = ("--rewrite-reference", "docs/user/project-layout.md")
            status, packet = action("plan", "--migration", *approval)
            self.assertEqual(status, 0, packet)
            edits = packet["result"]["reference_edits"]
            self.assertEqual(set(edits), {approval[-1]})
            arguments = (
                "--acknowledge",
                "--plan-identity",
                packet["result"]["plan_identity"],
            )
            status, packet = action("apply", *arguments, *approval)
            self.assertEqual(status, 0, packet)
            self.assertFalse(manifest.exists())
            self.assertTrue((project / "litai" / PROJECT_FILENAME).is_file())
            self.assertEqual(git("ls-files", "--stage", "-z"), index)
            rewritten = document.read_bytes()
            self.assertEqual(
                rewritten,
                before.replace(
                    b"../../literate.project.json", b"../../litai/literate.project.json"
                ),
            )
            document.write_bytes(b"local change after placement\n")
            status, packet = action("recover", *arguments)
            self.assertEqual(status, 2, packet)
            self.assertEqual(
                packet["error"]["code"], "project.layout.recovery_conflict"
            )
            self.assertEqual(document.read_bytes(), b"local change after placement\n")
            document.write_bytes(rewritten)
            placed = project / "litai"
            nested = placed / ".literate"
            for git_root, separate in (
                (placed, False),
                (placed, True),
                (nested, False),
            ):
                with self.subTest(path=git_root, separate_gitdir=separate):
                    storage = project.parent / "independent-gitdir"
                    init = ("--separate-git-dir", str(storage)) if separate else ()
                    git("-C", str(git_root), "init", "-q", *init)
                    git("-C", str(git_root), "add", ".")
                    marker = git_root / ".git"
                    administration = storage if separate else marker
                    files = {
                        str(path.relative_to(administration)): path.read_bytes()
                        for path in administration.rglob("*")
                        if path.is_file()
                    }
                    marker_bytes = marker.read_bytes() if separate else None
                    status, packet = action("recover", *arguments)
                    self.assertEqual(status, 2, packet)
                    self.assertEqual(
                        packet["error"]["code"], "project.layout.git_boundary"
                    )
                    self.assertEqual(git("ls-files", "--stage", "-z"), index)
                    self.assertTrue((placed / PROJECT_FILENAME).is_file())
                    self.assertEqual(document.read_bytes(), rewritten)
                    self.assertEqual(
                        {
                            str(path.relative_to(administration)): path.read_bytes()
                            for path in administration.rglob("*")
                            if path.is_file()
                        },
                        files,
                    )
                    if separate:
                        self.assertEqual(marker.read_bytes(), marker_bytes)
                        marker.unlink()
                    else:
                        shutil.rmtree(administration)
            status, packet = action("recover", *arguments)
            self.assertEqual(status, 0, packet)
            self.assertEqual(manifest.read_bytes(), original)
            self.assertEqual(manifest.stat().st_ino, inode)
            self.assertEqual(document.read_bytes(), before)
            self.assertEqual(git("ls-files", "--stage", "-z"), index)

            git("-C", str(document.parent), "init", "-q")
            status, packet = action("plan", "--migration", *approval)
            self.assertEqual(status, 2, packet)
            self.assertEqual(packet["error"]["code"], "project.layout.git_boundary")
            self.assertEqual(document.read_bytes(), before)
            self.assertEqual(git("ls-files", "--stage", "-z"), index)

    @unittest.skipUnless(os.name == "posix", "requires POSIX exclusive rename")
    def test_public_imported_layout_keeps_host_and_local_paths_and_rolls_back(self):
        from literate_ai.adapters.repository_lineage import REPOSITORY_PARENT_FILE
        from literate_ai.contracts import (
            RepositoryParentReference,
            RepositoryParentSelection,
        )
        from literate_ai.contracts.authoring_markdown import (
            AGENT_SKILL_EVALUATION_AUTHOR,
        )
        from tests.support.fixtures_test_repository_initialization_e2e import (
            commit_project,
            git,
        )

        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            upstream = workspace / "layout-parent"
            upstream.mkdir()
            manifest = json.loads((self.template / PROJECT_FILENAME).read_bytes())
            manifest["project_id"] = "layout-parent"
            (upstream / PROJECT_FILENAME).write_bytes(canonical_json_bytes(manifest))
            selection = upstream / REPOSITORY_PARENT_FILE
            selection.parent.mkdir()
            selection.write_bytes(
                canonical_json_bytes(RepositoryParentSelection.root().to_dict())
            )
            skill = "skills/specification-to-source/layout-example/SKILL.md"
            component = "components/layout-example/component.md"
            held = "components/layout-native/component.md"
            authoring = (
                "---\nnamespace: layout-fixture\nversion: 1.0.0\n"
                "display_name: Layout fixture\nprofiles:\n  - application\n"
                "sample: false\n"
                "provides: []\nrequires: []\nauthoring_inputs:\n"
                "  - kind: specification-to-source-skill\n"
                f"    uri: {skill}\n"
                "workflow_definition: workflows/sample-host.md\n"
                "routing_policy: routing/sample-host.json\n"
                "flavor_slots: []\nentrypoints: []\nacceptance_contracts: []\n"
                "source_dependencies: []\n---\n"
            ).encode()
            imported = {
                skill: (
                    "---\nname: layout-example\ndescription: Fixture pipeline skill.\n"
                    "metadata:\n"
                    f"  author: {json.dumps(AGENT_SKILL_EVALUATION_AUTHOR)}\n"
                    "schema: urn:literate-ai:schema:v1:specification-to-source-skill\n"
                    "skill_id: layout-example\nversion: 1.0.0\ntitle: Layout fixture\n"
                    "stages:\n  - generate\ndependencies: []\n"
                    "limitations:\n  - Use only local fixture files.\n"
                    "trust: repository-reviewed\n---\n# Layout fixture\n"
                    "\nGenerate the layout fixture.\n"
                ).encode(),
                component: authoring + b"# Selected imported Component\n",
                held: authoring + b"# Host-referenced imported Component\n",
            }
            for relative, content in imported.items():
                path = upstream / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            commit_project(upstream)
            revision = git(upstream, "rev-parse", "HEAD")
            parent = RepositoryParentReference(upstream.as_uri(), revision)

            project = workspace / "converted"
            _legacy_project(project)
            with mock.patch.dict(
                os.environ,
                {"OBJ_DIR": str(workspace / "objects"), "GIT_ALLOW_PROTOCOL": "file"},
            ):
                _adapter().initialize(
                    project,
                    flavor_selectors=_selectors(project),
                    source_intelligence_provider="none",
                    convert=True,
                    parent_selection=RepositoryParentSelection.inherit((parent,)),
                )
            host = ".github/workflows/native.yml"
            local = "skills/agent/local-layout-example/SKILL.md"
            for relative, content in {
                host: f"# Host CI refers to {held}.\n".encode(),
                local: b"# Locally authored Skill\n",
            }.items():
                path = project / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            root_skill = project / "SKILL.md"
            line = f"litai plan components/layout-example # read `{skill}`\n"
            with root_skill.open("ab") as document:
                document.write(("\n" + line).encode())
            original = root_skill.read_bytes()
            contained_line = (
                f"litai plan litai/components/layout-example # read `litai/{skill}`\n"
            )
            rewritten = original.replace(line.encode(), contained_line.encode())
            records = CatalogImportsFile.load(project)
            self.assertIsNotNone(records)
            self.assertEqual(len(records.imports), 3)
            self.assertTrue(
                all(
                    item.source.ref == f"git:{upstream.as_uri()}@{revision}"
                    for item in records.imports
                )
            )
            layout_document = "docs/user/project-layout.md"
            paths = (
                *imported,
                host,
                local,
                "SKILL.md",
                layout_document,
                CatalogImportsFile.PATH,
            )

            def state(relative):
                path = project / relative
                return (path.read_bytes(), path.stat().st_mode, path.stat().st_ino)

            before = {relative: state(relative) for relative in paths}
            commit_project(project)
            index = git(project, "ls-files", "--stage")
            head = git(project, "rev-parse", "HEAD")
            scope = ("--place-imported-catalogs",)

            def layout(verb, *arguments, expected=0):
                status, packet = _invoke(
                    "--json",
                    "project",
                    "layout",
                    verb,
                    *arguments,
                    "--project",
                    str(project),
                )
                self.assertEqual(status, expected, packet)
                return packet["error" if expected else "result"]

            denied = layout("plan", "--migration", *scope)
            self.assertFalse(denied["applicable"])
            self.assertEqual(
                {item["path"] for item in denied["blocked_references"]},
                {"SKILL.md", layout_document},
            )
            error = layout(
                "apply",
                *scope,
                "--acknowledge",
                "--plan-identity",
                denied["plan_identity"],
                expected=2,
            )
            self.assertEqual(error["code"], "project.layout.reference_authority")
            self.assertEqual({relative: state(relative) for relative in paths}, before)

            scope += (
                "--rewrite-reference",
                "SKILL.md",
                "--rewrite-reference",
                layout_document,
            )
            plan = layout("plan", "--migration", *scope)
            self.assertTrue(plan["applicable"])
            placed = {relative: f"litai/{relative}" for relative in (skill, component)}
            self.assertEqual(plan["catalog_placements"], placed)
            self.assertEqual(
                [
                    (item["path"], item["owner"])
                    for item in plan["catalog_placement_blockers"]
                ],
                [(host, "layout-native")],
            )
            approval = ("--acknowledge", "--plan-identity", plan["plan_identity"])
            layout("apply", *approval, *scope)
            self.assertEqual(root_skill.read_bytes(), rewritten)
            for source, destination in placed.items():
                self.assertFalse((project / source).exists())
                self.assertEqual(state(destination)[:2], before[source][:2])
            for relative in (held, host, local):
                self.assertEqual(state(relative), before[relative])
            self.assertEqual(git(project, "ls-files", "--stage"), index)

            layout("recover", *approval)
            self.assertFalse((project / "litai").exists())
            self.assertEqual({relative: state(relative) for relative in paths}, before)
            self.assertEqual(git(project, "ls-files", "--stage"), index)
            self.assertEqual(git(project, "rev-parse", "HEAD"), head)

    def test_retained_receipt_refuses_redirected_implementation_ancestor(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "converted"
            shutil.copytree(self.template, project, symlinks=True)
            alias = project / "retained-alias"
            try:
                alias.symlink_to(
                    project / "components/legacy-project-wrapper",
                    target_is_directory=True,
                )
            except (OSError, NotImplementedError):
                self.skipTest("directory symlinks are unavailable on this host")
            lift = project / ".literate/legacy-lift-shift.json"
            document = json.loads(lift.read_bytes())
            document["implementation_directory"] = "retained-alias/implementation"
            lift.write_bytes(canonical_json_bytes(document))
            candidate = root / "candidate.json"
            status, result = _invoke(
                "project",
                "test-receipt",
                "run-retained",
                str(candidate),
                "--project",
                str(project),
                "--worker-id",
                "local",
            )
            self.assertEqual(status, 2, result)
            self.assertEqual(
                result["error"]["code"], "retained_receipt.lift_shift_invalid"
            )
            self.assertFalse(candidate.exists())

    def test_passing_retained_harness_emits_and_promotes_finalized_candidate(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "converted"
            shutil.copytree(self.template, project, symlinks=True)
            candidate = root / "candidate.json"

            status, run = _invoke(
                "project",
                "test-receipt",
                "run-retained",
                str(candidate),
                "--project",
                str(project),
                "--worker-id",
                "local",
            )

            self.assertEqual(status, 0, run)
            self.assertEqual(self.initialized["standard_binding"], "retained-harness")
            result = run["result"]
            self.assertEqual(result["classification"], "retained-legacy-parity")
            self.assertEqual(result["tests"], 2)
            self.assertFalse(result["native_component_generation"])
            self.assertFalse(result["native_component_acceptance"])
            finalized = json.loads(candidate.read_text(encoding="utf-8"))
            receipt = finalized["receipt"]
            self.assertEqual(receipt["suite"]["id"], "retained-legacy-parity")
            self.assertNotIn("acceptance-result", receipt["evidence"])
            self.assertNotIn("generation-provenance", receipt["evidence"])
            self.assertIn("build-result", receipt["evidence"])
            self.assertIn("package-result", receipt["evidence"])
            evidence = json.loads(Path(result["evidence"]).read_text(encoding="utf-8"))
            self.assertEqual(evidence["tests"], 2)
            self.assertTrue(
                all("stdout_excerpt" not in item for item in evidence["phases"])
            )
            self.assertEqual(
                [item["command"] for item in evidence["phases"]],
                [
                    "make -f Makefile",
                    "make -f Makefile test",
                    "make -f Makefile package",
                ],
            )

            status, updated = _invoke(
                "project",
                "test-receipt",
                "update",
                str(candidate),
                "--project",
                str(project),
            )
            self.assertEqual(status, 0, updated)
            status, current = _invoke(
                "project",
                "test-receipt",
                "require-current",
                "--project",
                str(project),
            )
            self.assertEqual(status, 0, current)
            self.assertEqual(current["result"]["state"], "current")

            implementation = (
                project / "components/legacy-project-wrapper/implementation/app.py"
            )
            implementation.write_text("print('changed')\n", encoding="utf-8")
            status, stale = _invoke(
                "project",
                "test-receipt",
                "require-current",
                "--project",
                str(project),
            )
            self.assertEqual(status, 2, stale)
            self.assertEqual(stale["error"]["code"], "project.test_receipt_stale")

    def test_contained_retained_receipt_renews_from_explicit_evidence_location(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory).resolve()
            project = workspace / "converted"
            shutil.copytree(self.template, project, symlinks=True)
            implementation = project / LEGACY_WRAPPER_COMPONENT / "implementation"
            workflow = project / ".github/workflows/host.yml"
            workflow.parent.mkdir(parents=True, exist_ok=True)
            workflow.write_bytes(b"name: Native host\non: push\njobs: {}\n")
            note = project / "operator-note.txt"
            note.write_bytes(b"Keep this custom application file.\n")
            preserved = {
                path: path.read_bytes()
                for path in (*implementation.rglob("*"), workflow, note)
                if path.is_file()
            }

            def receipt(command, candidate=None, *, selected=project):
                extra = (str(candidate),) if candidate else ()
                return _invoke(
                    "project",
                    "test-receipt",
                    command,
                    *extra,
                    "--project",
                    str(selected),
                )

            initial = workspace / "legacy-candidate.json"
            status, result = receipt("run-retained", initial)
            self.assertEqual(status, 0, result)
            status, result = receipt("update", initial)
            self.assertEqual(status, 0, result)
            status, result = receipt("require-current")
            self.assertEqual(status, 0, result)
            current_path = project / result["result"]["path"]
            historical_receipt = current_path.read_bytes()

            # Construct an explicit partial placement fixture. This test supplies
            # the owner-selected inputs; it does not exercise a migration writer.
            framework = project / "litai"
            selected_metadata = framework / ".literate"
            selected_metadata.mkdir(parents=True)
            for name in (
                "conversion-authority.json",
                "harness-inventory.json",
                "imports.json",
                "initialization-baseline.json",
                "initialization-origin.json",
                "legacy-harness-baseline.json",
                "legacy-lift-shift.json",
                "legacy-wrapper-parity.json",
                "repository-lineage.json",
                "repository-parent.json",
                "update-bases.json",
            ):
                artifact = project / ".literate" / name
                if artifact.is_file():
                    artifact.rename(selected_metadata / name)
            manifest = project / PROJECT_FILENAME
            authority = json.loads(manifest.read_bytes())
            authority["framework_directory"] = "litai"
            (framework / PROJECT_FILENAME).write_bytes(
                canonical_json_bytes(authority) + b"\n"
            )
            manifest.unlink()
            guide = project / "docs/user/project-layout.md"
            old_link = b"](../../literate.project.json)"
            guide_bytes = guide.read_bytes()
            self.assertEqual(guide_bytes.count(old_link), 1)
            guide.write_bytes(
                guide_bytes.replace(old_link, b"](../../litai/literate.project.json)")
            )
            status, review = _invoke(
                "project", "documentation-review", str(implementation), "--record"
            )
            self.assertEqual(status, 0, review)

            status, stale = receipt("require-current", selected=implementation)
            self.assertEqual(status, 2, stale)
            self.assertEqual(stale["error"]["code"], "project.test_receipt_stale")
            self.assertEqual(current_path.read_bytes(), historical_receipt)

            renewed = workspace / "contained-candidate.json"
            status, result = receipt("run-retained", renewed, selected=implementation)
            self.assertEqual(status, 0, result)
            self.assertEqual(result["result"]["tests"], 2)
            status, result = receipt("update", renewed, selected=implementation)
            self.assertEqual(status, 0, result)
            status, result = receipt("require-current", selected=implementation)
            self.assertEqual(status, 0, result)
            self.assertEqual(result["result"]["state"], "current")
            self.assertNotEqual(current_path.read_bytes(), historical_receipt)
            self.assertEqual({path: path.read_bytes() for path in preserved}, preserved)

            # A byte-identical shadow at the old root cannot supply a missing
            # record for the declared framework directory.
            inventory = selected_metadata / "harness-inventory.json"
            original = inventory.read_bytes()
            (project / ".literate" / inventory.name).write_bytes(original)
            inventory.unlink()
            absent_candidate = workspace / "absent-candidate.json"
            status, missing = receipt("run-retained", absent_candidate)
            self.assertEqual(status, 2, missing)
            self.assertEqual(
                missing["error"]["code"], "retained_receipt.evidence_invalid"
            )
            self.assertFalse(absent_candidate.exists())
            inventory.write_bytes(original)

            layout = RetainedLayoutDeclaration(
                LEGACY_WRAPPER_COMPONENT,
                f"{LEGACY_WRAPPER_COMPONENT}/implementation",
                (),
                None,
            )
            (selected_metadata / "retained-layout.json").write_bytes(
                canonical_json_bytes(layout.to_dict()) + b"\n"
            )
            blocked_candidate = workspace / "declared-candidate.json"
            current_receipt_before = current_path.read_bytes()
            with mock.patch(
                "literate_ai.adapters.retained_harness_receipts.execute_retained_harness",
                side_effect=AssertionError("unqualified layout executed its harness"),
            ) as executed:
                status, blocked = receipt("run-retained", blocked_candidate)
            executed.assert_not_called()
            self.assertEqual(status, 2, blocked)
            self.assertEqual(
                blocked["error"]["code"], "retained_receipt.layout_unqualified"
            )
            self.assertFalse(blocked_candidate.exists())
            self.assertEqual(current_path.read_bytes(), current_receipt_before)

    def test_remote_worker_is_selected_exactly_and_finalized_by_coordinator(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "converted"
            shutil.copytree(self.template, project, symlinks=True)
            worker = ExecutionWorker(
                "ubuntu-24.04-nvidia",
                ExecutionWorkerKind.SSH,
                endpoint="runner@worker.example",
                workspace="~/literate-ai",
                requirements=ExecutionRequirements(os_family="linux"),
            )
            catalog_path = root / "workers.json"
            _write_workers(catalog_path, worker)
            candidate = root / "candidate.json"

            def execute(_self, selected, **values):
                self.assertEqual(selected, worker)
                self.assertEqual(
                    values["worker_catalog_identity"],
                    ExecutionWorkerCatalog((worker,)).identity,
                )
                report = execute_retained_harness(
                    values["inventory"],
                    legacy_root=values["source_root"],
                    timeout_seconds=values["timeout_seconds"],
                )
                phases = tuple(
                    {
                        key: value
                        for key, value in phase.items()
                        if key not in {"stdout_excerpt", "stderr_excerpt"}
                    }
                    for phase in report["phases"]
                )
                return RetainedHarnessRemoteResult(
                    canonical_identity({"mock": "remote-request"}),
                    values["lifecycle_request_identity"],
                    selected.identity,
                    canonical_identity(values["inventory"]),
                    values["source_identity"],
                    {
                        "operating_system": "linux",
                        "operating_system_release": "6.8.0",
                        "machine": "x86_64",
                        "python_implementation": "cpython",
                        "python_version": "3.13.7",
                    },
                    phases,
                )

            with mock.patch(
                "literate_ai.adapters.retained_harness_receipts."
                "RetainedHarnessSshExecutor.execute",
                autospec=True,
                side_effect=execute,
            ) as dispatched:
                status, result = _invoke(
                    "project",
                    "test-receipt",
                    "run-retained",
                    str(candidate),
                    "--project",
                    str(project),
                    "--worker-id",
                    worker.worker_id,
                    "--worker-config",
                    str(catalog_path),
                )

            self.assertEqual(status, 0, result)
            dispatched.assert_called_once()
            evidence = json.loads(
                Path(result["result"]["evidence"]).read_text(encoding="utf-8")
            )
            self.assertEqual(evidence["worker_id"], worker.worker_id)
            self.assertEqual(evidence["platform"]["operating_system"], "linux")
            self.assertEqual(evidence["platform"]["machine"], "x86_64")
            self.assertEqual(
                evidence["worker_identity"],
                retained_harness_worker_identity(worker.worker_id, worker).uri,
            )

    def test_remote_receiver_failure_exposes_no_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "converted"
            shutil.copytree(self.template, project, symlinks=True)
            worker = ExecutionWorker(
                "linux",
                ExecutionWorkerKind.SSH,
                endpoint="runner@linux.example",
                workspace="~/literate-ai",
                requirements=ExecutionRequirements(os_family="linux"),
            )
            catalog_path = root / "workers.json"
            _write_workers(catalog_path, worker)
            candidate = root / "candidate.json"
            with mock.patch(
                "literate_ai.adapters.retained_harness_receipts."
                "RetainedHarnessSshExecutor.execute",
                side_effect=RetainedHarnessRemoteError(
                    "retained_receipt.remote_execution_failed",
                    "receiver reported no passing result: "
                    + ("bounded diagnostic " * 40)
                    + "retained-tail",
                ),
            ):
                status, result = _invoke(
                    "project",
                    "test-receipt",
                    "run-retained",
                    str(candidate),
                    "--project",
                    str(project),
                    "--worker-id",
                    worker.worker_id,
                    "--worker-config",
                    str(catalog_path),
                )

            self.assertEqual(status, 2, result)
            self.assertEqual(
                result["error"]["code"],
                "retained_receipt.remote_execution_failed",
            )
            self.assertIn("retained-tail", result["error"]["message"])
            self.assertFalse(candidate.exists())
            self.assertFalse((root / "candidate.evidence.json").exists())

    def test_harness_cannot_mutate_authored_source_while_earning_receipt(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "converted"
            shutil.copytree(self.template, project, symlinks=True)
            implementation = (
                project / "components/legacy-project-wrapper/implementation"
            )
            (implementation / "Makefile").write_text(
                "build:\n"
                "\tprintf '# generated\\n' >> app.py\n"
                "test:\n"
                "\t@printf 'Ran 2 tests\\n'\n"
                "\t@printf 'OK\\n'\n"
                "package:\n"
                "\t@true\n",
                encoding="utf-8",
            )
            candidate = root / "candidate.json"

            status, rejected = _invoke(
                "project",
                "test-receipt",
                "run-retained",
                str(candidate),
                "--project",
                str(project),
            )

            self.assertEqual(status, 2, rejected)
            self.assertEqual(
                rejected["error"]["code"], "retained_receipt.source_mutated"
            )
            self.assertFalse(candidate.exists())
            self.assertFalse((root / "candidate.evidence.json").exists())

    def test_nonpassing_or_collection_only_count_cannot_become_receipt(self):
        for summary in ("1 passed, 1 xfailed", "collected 8 items"):
            with self.subTest(summary=summary):
                with tempfile.TemporaryDirectory() as directory:
                    root = Path(directory)
                    project = root / "converted"
                    _legacy_project(project, summary)
                    _adapter().initialize(
                        project,
                        flavor_selectors=_selectors(project),
                        source_intelligence_provider="none",
                        convert=True,
                    )
                    candidate = root / "candidate.json"

                    status, rejected = _invoke(
                        "project",
                        "test-receipt",
                        "run-retained",
                        str(candidate),
                        "--project",
                        str(project),
                    )

                    self.assertEqual(status, 2, rejected)
                    self.assertEqual(
                        rejected["error"]["code"],
                        "retained_receipt.tests_not_all_passing",
                    )
                    self.assertFalse(candidate.exists())
                    self.assertFalse((root / "candidate.evidence.json").exists())

    def test_update_migrates_0_9_0_retained_evidence_before_run_retained(self):
        # Reproduces issue #342: a project converted and Phase 1-qualified
        # under 0.9.0 recorded qualified parity at schema @1 and a
        # harness-inventory.json with no source_scope. 0.11.0's run-retained
        # front door refuses both until they are migrated.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            project = root / "converted"
            shutil.copytree(self.template, project, symlinks=True)

            parity_path = project / ".literate" / "legacy-wrapper-parity.json"
            parity_document = json.loads(parity_path.read_text(encoding="utf-8"))
            self.assertEqual(parity_document["schema"], HARNESS_PARITY_SCHEMA)
            self.assertEqual(parity_document["state"], "passed")
            parity_document["schema"] = LEGACY_WRAPPER_PARITY_SCHEMA_V1
            parity_path.write_bytes(canonical_json_bytes(parity_document) + b"\n")

            inventory_path = project / ".literate" / "harness-inventory.json"
            inventory_document = json.loads(inventory_path.read_text(encoding="utf-8"))
            original_source_scope = inventory_document["source_scope"]
            self.assertIsInstance(original_source_scope, dict)
            del inventory_document["source_scope"]
            inventory_path.write_bytes(canonical_json_bytes(inventory_document) + b"\n")

            # Mirror issue #342's reproduction step 3: rebind the test receipt
            # policy emitted by retained_harness_receipt_policy(inventory) for
            # the now-0.9.0-shaped inventory, so the only gaps under test are
            # the parity schema and the missing source scope.
            project_path = project / PROJECT_FILENAME
            project_document = json.loads(project_path.read_text(encoding="utf-8"))
            project_document["test_receipt_policy"] = retained_harness_receipt_policy(
                inventory_document
            ).to_dict()
            project_path.write_bytes(canonical_json_bytes(project_document) + b"\n")
            record_project_authority_review(project)

            candidate = root / "candidate.json"
            status, blocked = _invoke(
                "project",
                "test-receipt",
                "run-retained",
                str(candidate),
                "--project",
                str(project),
                "--worker-id",
                "local",
            )
            self.assertEqual(status, 2, blocked)
            self.assertEqual(
                blocked["error"]["code"], "retained_receipt.parity_unqualified"
            )

            migration = migrate_retained_evidence(project)

            self.assertIn(".literate/legacy-wrapper-parity.json", migration.migrated)
            self.assertIn(".literate/harness-inventory.json", migration.migrated)

            migrated_parity = json.loads(parity_path.read_text(encoding="utf-8"))
            self.assertEqual(migrated_parity["schema"], HARNESS_PARITY_SCHEMA)
            self.assertEqual(migrated_parity["state"], "passed")

            migrated_inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
            self.assertEqual(
                migrated_inventory["source_scope"]["paths"],
                original_source_scope["paths"],
            )
            self.assertEqual(
                migrated_inventory["source_scope"]["schema"],
                "literate-ai/retained-source-scope@1",
            )

            status, run = _invoke(
                "project",
                "test-receipt",
                "run-retained",
                str(candidate),
                "--project",
                str(project),
                "--worker-id",
                "local",
            )
            self.assertEqual(status, 0, run)
            self.assertEqual(run["result"]["classification"], "retained-legacy-parity")

            # Migrating an already-current project is a no-op.
            self.assertEqual(migrate_retained_evidence(project).migrated, ())


if __name__ == "__main__":
    unittest.main()
