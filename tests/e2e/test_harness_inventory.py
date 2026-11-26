"""Vertical-slice tests: convert inspects a real legacy tree and emits a working
harness wrapper, and detected flavors flow into ``litai init`` selector resolution."""

from __future__ import annotations

import hashlib
import json
import os
import shlex
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.component_markdown import parse_component_markdown
from literate_ai.adapters.harness_inventory import (
    HARNESS_INVENTORY_SCHEMA,
    HARNESS_WRAPPER_FILENAME,
    _run_harness_command,
    render_harness_wrapper,
)
from literate_ai.adapters.monorepo_adoption import (
    SELECTION_SCHEMA,
    MonorepoAdoptionError,
)
from literate_ai.adapters.monorepo_components import (
    check_installed_monorepo_components,
)
from literate_ai.adapters.project_initialization import (
    ProjectInitializationError,
    detect_repo_flavors,
    host_platform_selector,
)
from literate_ai.adapters.project_validation import (
    ProjectValidationError,
    validate_project,
)
from literate_ai.adapters.retained_scope_refresh import (
    apply_retained_scope_refresh,
    plan_retained_scope_refresh,
)
from literate_ai.contracts import ProjectInitializationOrigin
from tests.support.root_parent_adapter import (
    RootParentProjectInitializationAdapter as FilesystemProjectInitializationAdapter,
)


def _origin() -> ProjectInitializationOrigin:
    return ProjectInitializationOrigin(
        repository_url="ssh://git.example.test/operator/literate-ai.git",
        git_revision="c" * 40,
        distribution_name="literate-ai",
        distribution_version="0.2.0",
    )


def _adapter() -> FilesystemProjectInitializationAdapter:
    return FilesystemProjectInitializationAdapter(
        initialization_origin_provider=_origin,
        standard_binding_provider=lambda: None,
    )


def _write_executable(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def _write_repo_man_fixture(target: Path) -> None:
    """Synthetic NVIDIA repo.sh monorepo: root driver plus kit/rendering roots."""

    _write_executable(
        target / "repo.sh",
        "#!/bin/sh\n"
        "set -eu\n"
        'case "${1:-}" in\n'
        "  build)\n"
        "    ./kit/repo.sh build\n"
        "    ./rendering/repo.sh build\n"
        "    echo built > build.sentinel\n"
        "    ;;\n"
        "  *)\n"
        '    echo "unknown command: ${1:-}" >&2\n'
        "    exit 2\n"
        "    ;;\n"
        "esac\n",
    )
    nested = '#!/bin/sh\nset -eu\necho "$(basename "$(pwd)") ${1:-}"\nexit 0\n'
    _write_executable(target / "kit" / "repo.sh", nested)
    _write_executable(target / "rendering" / "repo.sh", nested)
    (target / "kit" / "repo.toml").write_text('name = "kit"\n', encoding="utf-8")
    (target / "rendering" / "repo.toml").write_text(
        'name = "rendering"\n', encoding="utf-8"
    )
    (target / "kit" / "main.cpp").write_text(
        "int main() { return 0; }\n", encoding="utf-8"
    )
    (target / "rendering" / "tools.py").write_text("print('hi')\n", encoding="utf-8")
    workflow = target / ".github" / "workflows"
    workflow.mkdir(parents=True)
    (workflow / "ci.yml").write_text(
        "jobs:\n"
        "  test:\n"
        "    runs-on: ${{ matrix.os }}\n"
        "    strategy:\n"
        "      matrix:\n"
        "        os: [ubuntu-latest, windows-latest]\n",
        encoding="utf-8",
    )
    (target / ".gitlab-ci.yml").write_text(
        "test:\n  script: echo ok\n", encoding="utf-8"
    )


def _signed_selectors(target: Path) -> tuple[str, ...]:
    selectors = detect_repo_flavors(target)
    return (
        *(
            f"+{selector}" if not selector.startswith("+") else selector
            for selector in selectors
        ),
        host_platform_selector(),
    )


class ConvertHarnessSliceTests(unittest.TestCase):
    """Full slice: legacy Makefile+Python repo -> convert -> executable wrapper."""

    def test_convert_produces_inventory_and_wrapper_that_executes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "legacy-project"
            target.mkdir()
            # A real, runnable legacy harness: make build/test write sentinels.
            (target / "Makefile").write_text(
                "all:\n"
                "\t@echo built > build.sentinel\n"
                "test:\n"
                "\t@echo tested > test.sentinel\n",
                encoding="utf-8",
            )
            (target / "app.py").write_text("print('hi')\n", encoding="utf-8")

            result = _adapter().initialize(
                target,
                source_intelligence_provider="none",
                convert=True,
                baseline_timeout_seconds=37,
                baseline_diagnostic_chars=4096,
            )

            # The conversion result names the evidence and the wrapper.
            summary = result["harness_inventory"]
            self.assertIsNotNone(summary)
            self.assertEqual(summary["path"], ".literate/harness-inventory.json")
            self.assertIn("build", summary["commands"])
            self.assertEqual(result["harness_wrapper"], HARNESS_WRAPPER_FILENAME)
            self.assertIn(HARNESS_WRAPPER_FILENAME, result["created"])
            self.assertEqual(result["harness_parity"]["state"], "passed")
            self.assertEqual(result["harness_parity"]["phase_count"], 2)
            lift_shift = json.loads(
                (target / ".literate" / "legacy-lift-shift.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(lift_shift["phase_12_parity"]["timeout_seconds"], 37)
            self.assertEqual(
                lift_shift["phase_12_parity"]["diagnostic_limit_chars"],
                4096,
            )
            expected_shims = {
                "components/legacy-project-wrapper/component.md",
                "flavors/legacy-project-shim/flavor.md",
                "flavors/legacy-project-shim/openspec/spec.md",
                "routing/legacy-adoption.json",
                "skills/specification-to-source/legacy-project-shim/SKILL.md",
                "workflows/legacy-adoption/workflow.md",
            }
            self.assertEqual(set(result["shim_authority"]), expected_shims)
            self.assertTrue(all((target / path).is_file() for path in expected_shims))

            # The inventory document is on disk and every command cites evidence.
            document = json.loads(
                (target / ".literate" / "harness-inventory.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(document["schema"], HARNESS_INVENTORY_SCHEMA)
            self.assertEqual(document["commands"]["build"]["evidence"], "Makefile")
            baseline = json.loads(
                (target / ".literate" / "legacy-harness-baseline.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(baseline["state"], "passed")
            self.assertEqual(baseline["timeout_seconds"], 37)
            self.assertEqual(baseline["diagnostic_limit_chars"], 4096)
            self.assertEqual(
                [phase["phase"] for phase in baseline["phases"]],
                ["build", "test"],
            )
            self.assertTrue(
                all(
                    phase["exit_code"] == 0
                    and phase["timeout_seconds"] == 37
                    and phase["diagnostic_limit_chars"] == 4096
                    and phase["stdout_identity"].startswith("sha256:")
                    and phase["stderr_identity"].startswith("sha256:")
                    for phase in baseline["phases"]
                )
            )
            parity = json.loads(
                (target / ".literate" / "legacy-wrapper-parity.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(parity["state"], "passed")
            self.assertEqual(parity["timeout_seconds"], 37)
            self.assertEqual(parity["diagnostic_limit_chars"], 4096)
            self.assertTrue(all(phase["parity"] for phase in parity["phases"]))
            for phase in parity["phases"]:
                self.assertEqual(phase["timeout_seconds"], 37)
                self.assertEqual(phase["diagnostic_limit_chars"], 4096)
                self.assertEqual(phase["source_tree"], phase["baseline_source_tree"])

            # The wrapper is framework-owned at the top level and delegates to the
            # quarantined legacy tree with the detected commands.
            wrapper = (target / HARNESS_WRAPPER_FILENAME).read_text(encoding="utf-8")
            implementation_dir = result["lift_shift"]["implementation_directory"]
            self.assertIn(f"LITAI_LEGACY := {implementation_dir}", wrapper)
            self.assertIn("make -f Makefile", wrapper)
            self.assertTrue(result["lift_shift"]["quarantine_removed"])
            self.assertFalse((target / "_legacy").exists())
            self.assertTrue((target / result["lift_shift"]["adr"]).is_file())
            self.assertEqual(result["native_rewrite"]["state"], "planned")
            self.assertEqual(
                result["native_rewrite"]["next_action"], "boundary-inventory"
            )
            self.assertFalse(
                result["native_rewrite"]["source_to_specification_started"]
            )
            self.assertTrue((target / result["native_rewrite"]["adr"]).is_file())
            self.assertTrue((target / result["native_rewrite"]["roadmap"]).is_file())
            active_work = (target / "docs" / "roadmap" / "active-work.md").read_text(
                encoding="utf-8"
            )
            self.assertIn("ADOPT-002", active_work)
            self.assertIn("boundary inventory", active_work)

            # Smoke: the generated wrapper really builds and tests the legacy tree;
            # commands run inside the lifted first-class implementation directory.
            legacy_root = target / implementation_dir
            for make_target, sentinel in (
                ("build", "build.sentinel"),
                ("test", "test.sentinel"),
            ):
                completed = subprocess.run(
                    ("make", "-f", HARNESS_WRAPPER_FILENAME, make_target),
                    cwd=target,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                self.assertTrue((legacy_root / sentinel).is_file())

    @unittest.skipIf(
        os.name == "nt", "POSIX layout owner; native Windows ownership is separate"
    )
    def test_retained_layout_source_program_moves_and_restores_original_custody(self):
        from literate_ai.adapters.native_sdk_tree_custody import (
            _capture_composed_native_tree,
        )
        from literate_ai.adapters.retained_layout_journal import _begin_layout_journal
        from literate_ai.adapters.retained_layout_partition import (
            observe_retained_layout_partition,
        )
        from literate_ai.adapters.retained_layout_transaction import (
            _compile_relocation_transaction,
        )
        from literate_ai.contracts.identity import canonical_identity
        from literate_ai.contracts.retained_layout import RetainedLayoutDeclaration
        from literate_ai.contracts.retained_project import RetainedProjectLimits
        from literate_ai.projects import load_project
        from tests.support.fixtures_test_retained_harness_receipts import (
            _legacy_project,
            _selectors,
        )

        with tempfile.TemporaryDirectory(prefix="layout-source-") as directory:
            base = Path(directory).resolve()
            root = base / "project"
            _legacy_project(root)
            _adapter().initialize(
                root,
                flavor_selectors=_selectors(root),
                source_intelligence_provider="none",
                convert=True,
                run_baseline=True,
            )
            source = root / "components/legacy-project-wrapper/implementation"
            os.link(source / "app.py", source / "app-hard")
            (source / "app-link").symlink_to("app.py")
            (source / "empty").mkdir()
            initial_nodes = {
                name: (source / name).lstat().st_ino
                for name in ("app.py", "app-hard", "empty")
            }
            original_container = source.lstat().st_ino
            original_modes = {
                name: stat.S_IMODE((source / name).lstat().st_mode)
                for name in ("app.py", "app-hard", "empty")
            }
            limits = RetainedProjectLimits(10000, 16 * 1024**2, 64 * 1024**2)
            with observe_retained_layout_partition(load_project(root)) as context:
                compiled = _compile_relocation_transaction(
                    context,
                    RetainedLayoutDeclaration("components/renamed-wrapper", "retained"),
                    limits=limits,
                    case_sensitive=True,
                )
            program = compiled["source_operations"]
            plan = compiled["source_plan"]
            state = base / "private-state"
            state.mkdir(mode=0o700)
            with _begin_layout_journal(
                root,
                state_root=state,
                plan_identity=canonical_identity(compiled),
                intent=compiled,
            ) as owner:
                # This tests only the original source transaction. No layout is
                # published and these metadata bytes cannot qualify a receipt.
                owner.stage_metadata(
                    "unpublished-layout-candidate.json", b"candidate\n"
                )
                for operation in program["create_directories"]:
                    owner.create_directory(operation["path"], mode=operation["mode"])
                for operation in program["move_leaves"]:
                    owner.move(
                        operation["source"],
                        operation["destination"],
                        expected_source=tuple(
                            int(value) for value in operation["source_node"]
                        ),
                    )
                for operation in program["remove_empty_source_directories"]:
                    owner.remove_empty_source_directory(
                        operation["path"],
                        expected_source=tuple(
                            int(value) for value in operation["source_node"]
                        ),
                    )
                actual = _capture_composed_native_tree(
                    root / "retained",
                    store=None,
                    limits=limits,
                    case_sensitive=True,
                    max_metadata_memory_bytes=1024**3,
                    retain_payloads=False,
                )
                self.assertEqual(actual.identity.uri, plan["source_tree_identity"])
                self.assertEqual(
                    (root / "retained/app.py").lstat().st_ino, initial_nodes["app.py"]
                )
                self.assertEqual(
                    (root / "retained/app-hard").lstat().st_ino,
                    initial_nodes["app-hard"],
                )
                self.assertEqual(os.readlink(root / "retained/app-link"), "app.py")
                self.assertTrue((root / "retained/empty").is_dir())
                owner.rollback_removed_directories()
                owner.rollback_moves()
                owner.rollback_created_directories()
                owner.retire_metadata_stage()
                self.assertEqual(source.lstat().st_ino, original_container)
                self.assertEqual(
                    {name: (source / name).lstat().st_ino for name in initial_nodes},
                    initial_nodes,
                )
                self.assertEqual(
                    {
                        name: stat.S_IMODE((source / name).lstat().st_mode)
                        for name in original_modes
                    },
                    original_modes,
                )
                self.assertEqual(
                    (source / "app.py").read_bytes(), b"print('retained')\n"
                )
                self.assertEqual((source / "app-hard").lstat().st_nlink, 2)
                owner.retire_pending(
                    publication_identity=canonical_identity(compiled),
                    source_identity=actual.identity,
                )
            self.assertFalse((root / "retained").exists())
            self.assertFalse((root / ".litai-retained-layout-pending.json").exists())
            self.assertFalse(
                any(
                    path.name.startswith(".litai-layout-stage-")
                    for path in root.iterdir()
                )
            )
            self.assertEqual(os.readlink(source / "app-link"), "app.py")

    @unittest.skipIf(
        os.name == "nt", "POSIX finite layout observation; Windows owner is separate"
    )
    def test_retained_layout_root_plan_is_readonly_and_baseline_is_not_an_ignore_list(
        self,
    ):
        from dataclasses import replace

        from literate_ai.adapters.retained_layout import RetainedLayoutError
        from literate_ai.adapters.retained_layout_planning import (
            plan_retained_layout_relocation,
        )
        from literate_ai.contracts.identity import (
            ContentIdentity,
            HashAlgorithm,
            canonical_json_bytes,
        )
        from literate_ai.contracts.project_initialization import (
            ProjectInitializationBaseline,
            ProjectInitializationBaselineFile,
        )
        from literate_ai.contracts.retained_layout import RetainedLayoutDeclaration
        from literate_ai.contracts.retained_project import RetainedProjectLimits
        from literate_ai.projects import load_project
        from tests.support.fixtures_test_retained_harness_receipts import (
            _legacy_project,
            _selectors,
        )

        with tempfile.TemporaryDirectory(prefix="layout-plan-") as directory:
            root = Path(directory).resolve() / "project"
            _legacy_project(root)
            _adapter().initialize(
                root,
                flavor_selectors=_selectors(root),
                source_intelligence_provider="none",
                convert=True,
                run_baseline=True,
            )
            limits = RetainedProjectLimits(10000, 16 * 1024**2, 64 * 1024**2)

            def snapshot():
                result = {}
                for path in root.rglob("*"):
                    node = path.lstat()
                    value = (
                        node.st_dev,
                        node.st_ino,
                        node.st_mode,
                        node.st_uid,
                        node.st_gid,
                        node.st_nlink,
                        node.st_size,
                        node.st_mtime_ns,
                        node.st_ctime_ns,
                    )
                    if path.is_symlink():
                        payload = os.readlink(path)
                    elif path.is_file():
                        payload = hashlib.sha256(path.read_bytes()).hexdigest()
                    else:
                        payload = None
                    result[path.relative_to(root).as_posix()] = (value, payload)
                return result

            before = snapshot()
            declaration = RetainedLayoutDeclaration("components/renamed-wrapper", ".")
            result = plan_retained_layout_relocation(
                load_project(root), declaration, limits=limits, case_sensitive=True
            )
            self.assertTrue(result["plan"]["root_existing_partition"])
            self.assertEqual(
                result["plan"]["declaration"]["implementation_directory"], "."
            )
            self.assertEqual(snapshot(), before)
            for coordinate, directory_node in (
                ("foreign.txt", False),
                ("skills/source-to-specification/new-empty", True),
            ):
                with self.subTest(unselected_member=coordinate):
                    selected = root / coordinate
                    if directory_node:
                        selected.mkdir()
                    else:
                        selected.write_bytes(b"foreign bytes\n")
                    current = snapshot()
                    with self.assertRaises(RetainedLayoutError) as caught:
                        plan_retained_layout_relocation(
                            load_project(root),
                            declaration,
                            limits=limits,
                            case_sensitive=True,
                        )
                    self.assertEqual(
                        caught.exception.code,
                        "retained.layout.root_partition_collision",
                    )
                    self.assertEqual(snapshot(), current)
                    selected.rmdir() if directory_node else selected.unlink()
            baseline_path = root / ".literate/initialization-baseline.json"
            baseline = ProjectInitializationBaseline.from_dict(
                json.loads(baseline_path.read_bytes())
            )
            relative = "components/legacy-project-wrapper/implementation/Makefile"
            actual = (root / relative).read_bytes()
            forged = ProjectInitializationBaselineFile(
                relative,
                len(actual),
                ContentIdentity(
                    HashAlgorithm.SHA256, hashlib.sha256(actual).hexdigest()
                ),
            )
            baseline_path.write_bytes(
                canonical_json_bytes(
                    replace(
                        baseline,
                        files=tuple(
                            sorted(
                                (*baseline.files, forged), key=lambda item: item.path
                            )
                        ),
                    ).to_dict()
                )
                + b"\n"
            )
            current = snapshot()
            observed = plan_retained_layout_relocation(
                load_project(root),
                RetainedLayoutDeclaration("components/renamed-wrapper", "retained"),
                limits=limits,
                case_sensitive=True,
            )
            self.assertIn(
                "Makefile",
                [
                    item["path"]
                    for item in observed["plan"]["source_inventory"]["files"]
                ],
            )
            self.assertEqual(snapshot(), current)

    @unittest.skipIf(os.name == "nt", "native POSIX retirement capture control")
    def test_retained_layout_retirement_preserves_last_window_foreign_entries(self):
        import shutil

        from literate_ai.adapters import retained_layout_journal as journal
        from literate_ai.adapters.retained_layout import RetainedLayoutError
        from literate_ai.adapters.retained_layout_partition import (
            observe_retained_layout_partition,
        )
        from literate_ai.adapters.retained_layout_transaction import (
            _compile_relocation_transaction,
        )
        from literate_ai.contracts.identity import canonical_identity
        from literate_ai.contracts.retained_layout import RetainedLayoutDeclaration
        from literate_ai.contracts.retained_project import RetainedProjectLimits
        from literate_ai.projects import load_project
        from tests.support.fixtures_test_retained_harness_receipts import (
            _legacy_project,
            _selectors,
        )

        with tempfile.TemporaryDirectory(prefix="layout-retire-") as directory:
            base = Path(directory).resolve()
            template = base / "template"
            _legacy_project(template)
            _adapter().initialize(
                template,
                flavor_selectors=_selectors(template),
                source_intelligence_provider="none",
                convert=True,
                run_baseline=True,
            )
            native_rename = journal._native_rename
            for kind in (
                "pending",
                "created-directory",
                "created-directory-empty",
                "metadata-stage",
            ):
                with self.subTest(kind=kind):
                    root = base / kind
                    shutil.copytree(template, root, symlinks=True)
                    state = base / (kind + "-state")
                    state.mkdir(mode=0o700)
                    with observe_retained_layout_partition(
                        load_project(root)
                    ) as context:
                        compiled = _compile_relocation_transaction(
                            context,
                            RetainedLayoutDeclaration(
                                "components/renamed-wrapper", "retained"
                            ),
                            limits=RetainedProjectLimits(
                                10000, 16 * 1024**2, 64 * 1024**2
                            ),
                            case_sensitive=True,
                        )
                    injected = []
                    target = None
                    saved = root / "original-entry-preserved"
                    expected_original = None

                    def make_replacement_callback(target, saved, kind, injected):
                        def replace_at_capture(
                            source_parent,
                            source_name,
                            destination_name,
                            destination_parent=None,
                        ):
                            if source_name == os.fsencode(target.name) and not injected:
                                # Actual concurrent namespace mutation occurs AFTER
                                # the caller's final compare, immediately before the
                                # real native capture. No stat/rename result is fake.
                                target.rename(saved)
                                if kind == "pending":
                                    target.write_bytes(b"foreign pending marker\n")
                                else:
                                    target.mkdir(mode=0o700)
                                    if kind != "created-directory-empty":
                                        (target / "foreign.txt").write_bytes(
                                            b"foreign directory bytes\n"
                                        )
                                injected.append(target.lstat().st_ino)
                            return native_rename(
                                source_parent,
                                source_name,
                                destination_name,
                                destination_parent,
                            )

                        return replace_at_capture

                    with self.assertRaises(RetainedLayoutError) as caught:
                        with journal._begin_layout_journal(
                            root,
                            state_root=state,
                            plan_identity=canonical_identity(compiled),
                            intent=compiled,
                        ) as owner:
                            if kind == "pending":
                                target = root / ".litai-retained-layout-pending.json"
                            elif kind.startswith("created-directory"):
                                owner.create_directory("retained", mode=0o755)
                                target = root / "retained"
                            else:
                                owner.stage_metadata(
                                    "unpublished-layout-candidate.json",
                                    b"actual staged bytes\n",
                                )
                                stages = [
                                    path
                                    for path in root.iterdir()
                                    if path.name.startswith(".litai-layout-stage-")
                                ]
                                self.assertEqual(len(stages), 1)
                                target = stages[0]
                            expected_original = target.lstat().st_ino
                            with patch.object(
                                journal,
                                "_native_rename",
                                side_effect=make_replacement_callback(
                                    target, saved, kind, injected
                                ),
                            ):
                                if kind == "pending":
                                    owner.retire_pending(
                                        publication_identity=canonical_identity(
                                            compiled
                                        ),
                                        source_identity=canonical_identity(
                                            compiled["source_plan"]["source_inventory"]
                                        ),
                                    )
                                elif kind.startswith("created-directory"):
                                    owner.rollback_created_directories()
                                else:
                                    owner.retire_metadata_stage()
                    self.assertEqual(
                        caught.exception.code, "retained.layout.retirement_changed"
                    )
                    self.assertEqual(len(injected), 1)
                    self.assertEqual(target.lstat().st_ino, injected[0])
                    self.assertEqual(saved.lstat().st_ino, expected_original)
                    if kind == "pending":
                        self.assertEqual(
                            target.read_bytes(), b"foreign pending marker\n"
                        )
                        self.assertEqual(
                            json.loads(saved.read_bytes())["schema"],
                            "literate-ai/retained-layout-pending@1",
                        )
                    else:
                        if kind == "created-directory-empty":
                            self.assertEqual(list(target.iterdir()), [])
                        else:
                            self.assertEqual(
                                (target / "foreign.txt").read_bytes(),
                                b"foreign directory bytes\n",
                            )
                        if kind == "metadata-stage":
                            self.assertEqual(
                                [path.read_bytes() for path in saved.iterdir()],
                                [b"actual staged bytes\n"],
                            )
                    self.assertTrue(
                        (root / ".litai-retained-layout-pending.json").exists()
                    )

    @unittest.skipIf(os.name == "nt", "original POSIX authority read/issuance control")
    def test_retained_layout_issuance_never_rebases_changed_authority_reads(self):
        from literate_ai.adapters import retained_layout_partition as partition
        from literate_ai.adapters.retained_layout import RetainedLayoutError
        from literate_ai.contracts.identity import canonical_json_bytes
        from literate_ai.projects import load_project
        from tests.support.fixtures_test_retained_harness_receipts import (
            _legacy_project,
            _selectors,
        )

        with tempfile.TemporaryDirectory(prefix="layout-authority-") as directory:
            root = Path(directory).resolve() / "project"
            _legacy_project(root)
            _adapter().initialize(
                root,
                flavor_selectors=_selectors(root),
                source_intelligence_provider="none",
                convert=True,
                run_baseline=True,
            )
            alternative = root / "alternative-source"
            alternative.mkdir()
            (alternative / "different.txt").write_bytes(b"new selected source\n")
            cases = (
                ".literate/legacy-lift-shift.json",
                ".literate/initialization-baseline.json",
                ".literate/initialization-origin.json",
                "components/legacy-project-wrapper/component.md",
            )
            actual_framework_paths = partition._framework_paths
            for relative in cases:
                with self.subTest(authority=relative):
                    path = root / relative
                    original = path.read_bytes()
                    if relative.endswith("component.md"):
                        changed = (
                            original + b"\n<!-- actual concurrent authority edit -->\n"
                        )
                    else:
                        value = json.loads(original)
                        if relative.endswith("legacy-lift-shift.json"):
                            value["implementation_directory"] = "alternative-source"
                        elif relative.endswith("initialization-baseline.json"):
                            value["files"][0]["size"] += 1
                        else:
                            value["distribution_version"] = "0.2.1"
                        changed = canonical_json_bytes(value) + b"\n"
                    calls = []

                    def mutate_after_real_read(
                        *args, _calls=calls, _path=path, _changed=changed, **kwargs
                    ):
                        result = actual_framework_paths(*args, **kwargs)
                        _calls.append(True)
                        _path.write_bytes(_changed)
                        return result

                    try:
                        with patch.object(
                            partition,
                            "_framework_paths",
                            side_effect=mutate_after_real_read,
                        ):
                            with self.assertRaises(RetainedLayoutError) as caught:
                                with partition.observe_retained_layout_partition(
                                    load_project(root)
                                ):
                                    self.fail(
                                        "changed authority minted a source context"
                                    )
                        self.assertEqual(
                            caught.exception.code, "retained.layout.authority_changed"
                        )
                        self.assertEqual(calls, [True])
                        self.assertEqual(path.read_bytes(), changed)
                    finally:
                        # Restore only this test-owned fixture between separate
                        # fresh factory attempts. No production rollback does it.
                        path.write_bytes(original)

    def test_refined_convert_installs_independent_retained_components(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory).resolve()
            target = base / "legacy-monorepo"
            target.mkdir()
            (target / "Makefile").write_text(
                "all:\n\t@$(MAKE) -C kit\n\t@$(MAKE) -C runtime\n"
                "test:\n\t@$(MAKE) -C kit test\n\t@$(MAKE) -C runtime test\n",
                encoding="utf-8",
            )
            for name in ("kit", "runtime"):
                root = target / name
                root.mkdir()
                # The running interpreter, not `python3`: on Windows that name
                # can resolve to the Microsoft Store alias instead of Python.
                python = Path(sys.executable).as_posix()
                (root / "Makefile").write_text(
                    f'all:\n\t@true\ntest:\n\t@"{python}" -m unittest discover -v\n',
                    encoding="utf-8",
                )
                (root / "value.py").write_text("VALUE = 1\n", encoding="utf-8")
                (root / "test_value.py").write_text(
                    "import unittest\nfrom value import VALUE\n"
                    "class T(unittest.TestCase):\n"
                    "    def test_value(self): self.assertEqual(VALUE, 1)\n",
                    encoding="utf-8",
                )
            selection = base / "selection.json"
            selection.write_text(
                json.dumps(
                    {
                        "schema": SELECTION_SCHEMA,
                        "components": [
                            {
                                "name": name,
                                "root": name,
                                "commands": [
                                    {
                                        "id": phase,
                                        "command": command,
                                        "cwd": name,
                                        "evidence": f"{name}/Makefile",
                                    }
                                    for phase, command in (
                                        ("build", "make -f Makefile"),
                                        ("test", "make -f Makefile test"),
                                    )
                                ],
                            }
                            for name in ("kit", "runtime")
                        ],
                        "shared_sources": [
                            {
                                "path": "Makefile",
                                "owner": "kit",
                                "consumers": ["runtime"],
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            original = {
                path.relative_to(target).as_posix(): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file()
            }
            with patch(
                "literate_ai.adapters.monorepo_components.install_monorepo_components",
                side_effect=MonorepoAdoptionError(
                    "injected_failure", "injected installation failure"
                ),
            ):
                with self.assertRaises(ProjectInitializationError) as raised:
                    _adapter().initialize(
                        target,
                        source_intelligence_provider="none",
                        convert=True,
                        run_baseline=True,
                        root_plan=selection,
                    )
            self.assertEqual(raised.exception.code, "monorepo.injected_failure")
            self.assertEqual(
                {
                    path.relative_to(target).as_posix(): path.read_bytes()
                    for path in target.rglob("*")
                    if path.is_file()
                },
                original,
            )

            result = _adapter().initialize(
                target,
                source_intelligence_provider="none",
                convert=True,
                run_baseline=True,
                root_plan=selection,
            )

            installed = check_installed_monorepo_components(target)
            self.assertEqual(installed["components"], ["kit", "runtime"])
            self.assertEqual(installed["stage"], "retained")
            self.assertFalse(installed["source_copied"])
            self.assertEqual(set(installed["boundary_transfer"]), {"kit", "runtime"})
            self.assertIn("monorepo_components", result)
            retained = Path(result["lift_shift"]["implementation_directory"])
            self.assertEqual(installed["source_root"], retained.as_posix())
            self.assertTrue((target / retained / "kit" / "value.py").is_file())
            validation = _adapter()._validation.validate(
                target,
                require_authority_review=True,
                include_test_receipt=False,
                synchronize_source_intelligence=False,
            )
            self.assertEqual(
                validation["monorepo_components"]["identity"], installed["identity"]
            )

            (target / retained / "kit" / "new.py").write_text(
                "NEW = True\n", encoding="utf-8"
            )
            refresh_plan = plan_retained_scope_refresh(target)
            self.assertTrue(refresh_plan["monorepo_refresh_required"])
            with self.assertRaisesRegex(Exception, "run-component-baselines"):
                apply_retained_scope_refresh(
                    target,
                    expected_plan_identity=refresh_plan["plan_identity"],
                    acknowledge=True,
                )
            refreshed = apply_retained_scope_refresh(
                target,
                expected_plan_identity=refresh_plan["plan_identity"],
                acknowledge=True,
                run_component_baselines=True,
            )["monorepo_refresh"]
            self.assertEqual(refreshed["executed_components"], ["kit"])
            self.assertEqual(refreshed["reused_components"], ["runtime"])
            self.assertEqual(
                check_installed_monorepo_components(target)["state"], "current"
            )
            self.assertEqual(
                _adapter()._validation.validate(
                    target,
                    require_authority_review=True,
                    include_test_receipt=False,
                    synchronize_source_intelligence=False,
                )["monorepo_components"]["state"],
                "current",
            )

            receipt = (
                target / ".literate" / "monorepo-components" / "receipts" / "kit.json"
            )
            receipt.write_bytes(receipt.read_bytes() + b" ")
            with self.assertRaises(ProjectValidationError) as raised:
                _adapter()._validation.validate(
                    target,
                    require_authority_review=True,
                    include_test_receipt=False,
                    synchronize_source_intelligence=False,
                )
            self.assertEqual(raised.exception.code, "monorepo.receipt_changed")

    def test_convert_python_make_repo_validates_and_admits_derived_spec(
        self,
    ) -> None:
        """INIT-003: convert a synthetic Python+Make tree, then project-validate
        and parse a spec derived from observed behavior without implementation
        paths (skills/agent/convert-project spec-derivation principle)."""

        framework = Path(__file__).resolve().parents[2]
        convert_skill = framework / "skills" / "agent" / "convert-project" / "SKILL.md"
        self.assertTrue(convert_skill.is_file())
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "python-make-app"
            target.mkdir()
            (target / "Makefile").write_text(
                "all:\n"
                "\t@echo built > build.sentinel\n"
                "test:\n"
                "\t@echo tested > test.sentinel\n",
                encoding="utf-8",
            )
            (target / "app.py").write_text("print('hi')\n", encoding="utf-8")
            _adapter().initialize(
                target,
                source_intelligence_provider="none",
                convert=True,
            )
            validation = validate_project(
                target,
                require_authority_review=True,
                include_test_receipt=False,
                synchronize_source_intelligence=False,
            )
            self.assertEqual(validation["authority_review"]["state"], "current")
            onboarding = (target / "SKILL.md").read_text(encoding="utf-8")
            self.assertIn("conversion report as the exact follow-up", onboarding)
            self.assertIn("framework-only conversion skill", onboarding)
            self.assertFalse((target / "skills" / "agent" / "convert-project").exists())
            derived = """---
namespace: legacy-adoption
version: 1.0.0
display_name: Greeting Emitter
profiles:
  - application
sample: false
provides:
  - name: legacy.pipeline
    version: 1.0.0
requires: []
authoring_inputs:
  - kind: specification-to-source-skill
    uri: skills/specification-to-source/legacy-project-shim/SKILL.md
workflow_definition: workflows/legacy-adoption/workflow.md
routing_policy: routing/legacy-adoption.json
flavor_slots:
  - slot_id: build-system
    axis: build.system
    cardinality: exactly-one
    capability_contract: legacy.pipeline
entrypoints:
  - name: run
    kind: portable-application
    path: run
acceptance_contracts: []
source_dependencies: []
---
# Greeting Emitter

The application writes one greeting line to standard output when invoked with
no arguments. It does not read files, environment variables, or network
services.

## Application contract

| Concern | Decision |
| --- | --- |
| Kind | portable application |
| Output | exactly one line of greeting text |
"""
            self.assertNotIn("app.py", derived)
            self.assertNotIn("print(", derived)
            authoring = parse_component_markdown(
                target / "components" / "greeting-emitter" / "component.md",
                derived,
                project_root=target,
            )
            self.assertEqual(authoring.coordinate.name, "greeting-emitter")

    def test_failing_legacy_gate_restores_exact_pre_conversion_tree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "failing-project"
            target.mkdir()

            def exiting_command(status: int) -> str:
                command = [
                    Path(sys.executable).as_posix(),
                    "-c",
                    f"raise SystemExit({status})",
                ]
                return (
                    subprocess.list2cmdline(command)
                    if os.name == "nt"
                    else shlex.join(command)
                )

            original = {
                "Makefile": (
                    f"all:\n\t@{exiting_command(7)}\ntest:\n\t@{exiting_command(0)}\n"
                ),
                "src/app.py": "print('legacy')\n",
                "docs/guide.md": "# Legacy guide\n",
            }
            for relative, content in original.items():
                path = target / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            # GNU and BSD Make report a failed recipe with different statuses
            # and diagnostic spelling. Observe this host's real legacy gate.
            baseline = subprocess.run(
                ["make", "-f", "Makefile"],
                cwd=target,
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertNotEqual(baseline.returncode, 0)
            recipe_failure = r"\bError(?: code)? 7\b"
            self.assertRegex(baseline.stdout + baseline.stderr, recipe_failure)

            with self.assertRaises(ProjectInitializationError) as raised:
                _adapter().initialize(
                    target,
                    source_intelligence_provider="none",
                    convert=True,
                )

            self.assertEqual(
                raised.exception.code, "project.convert_legacy_gate_failed"
            )
            self.assertIn("rolled back", raised.exception.message)
            self.assertIn("make -f Makefile", raised.exception.message)
            self.assertIn(f"status {baseline.returncode}", raised.exception.message)
            self.assertRegex(raised.exception.message, recipe_failure)
            self.assertFalse((target / "literate.project.json").exists())
            self.assertFalse((target / ".literate").exists())
            self.assertFalse((target / "_legacy").exists())
            self.assertFalse((target / HARNESS_WRAPPER_FILENAME).exists())
            restored = {
                path.relative_to(target).as_posix(): path.read_text(encoding="utf-8")
                for path in target.rglob("*")
                if path.is_file()
            }
            self.assertEqual(restored, original)


class DetectionToSelectorSliceTests(unittest.TestCase):
    """Detection feeds init: a CMake repo must convert with build-cmake selected."""

    def test_cmake_repository_converts_with_cmake_flavor_selected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "cmake-project"
            target.mkdir()
            (target / "CMakeLists.txt").write_text(
                "cmake_minimum_required(VERSION 3.15)\n"
                "project(demo LANGUAGES NONE)\n"
                "enable_testing()\n"
                "add_test(NAME demo COMMAND ${CMAKE_COMMAND} -E true)\n",
                encoding="utf-8",
            )
            (target / "main.cpp").write_text(
                "int main() { return 0; }\n", encoding="utf-8"
            )
            # CMake also generates Makefiles in practice; detection must not
            # mistake one for a plain Make project.
            (target / "Makefile").write_text("# generated\n", encoding="utf-8")

            selectors = detect_repo_flavors(target)
            self.assertIn("flavor://literate-ai/build-cmake", selectors)
            self.assertNotIn("flavor://literate-ai/build-make", selectors)

            # Multi-config Windows generators require an explicit configuration
            # when CTest locates the configured test executable.

            _adapter().initialize(
                target,
                flavor_selectors=(
                    *(
                        f"+{selector}" if not selector.startswith("+") else selector
                        for selector in selectors
                    ),
                    host_platform_selector(),
                ),
                source_intelligence_provider="none",
                convert=True,
            )

            manifest = json.loads(
                (target / "literate.project.json").read_text(encoding="utf-8")
            )
            self.assertIn(
                "+flavor://literate-ai/build-cmake",
                manifest["default_flavor_selectors"],
            )
            self.assertNotIn(
                "+flavor://literate-ai/build-make",
                manifest["default_flavor_selectors"],
            )


class RepoManConvertSliceTests(unittest.TestCase):
    """repo.sh monorepos plan and wrap without a local make ci gate."""

    def test_repo_man_convert_emits_nested_wrapper_targets(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "kitish"
            target.mkdir()
            _write_repo_man_fixture(target)

            result = _adapter().initialize(
                target,
                flavor_selectors=_signed_selectors(target),
                source_intelligence_provider="none",
                convert=True,
            )

            self.assertTrue((target / "literate.project.json").is_file())
            self.assertEqual(result["harness_baseline"]["state"], "skipped")
            self.assertEqual(result["harness_parity"]["state"], "skipped")
            wrapper = (target / HARNESS_WRAPPER_FILENAME).read_text(encoding="utf-8")
            implementation_dir = result["lift_shift"]["implementation_directory"]
            self.assertIn(f"LITAI_LEGACY := {implementation_dir}", wrapper)
            self.assertIn("build.kit:", wrapper)
            self.assertIn("build.rendering:", wrapper)
            self.assertIn(
                "cd $(LITAI_LEGACY)/kit && ./repo.sh build --release", wrapper
            )
            self.assertIn(
                "cd $(LITAI_LEGACY)/rendering && ./repo.sh build --release", wrapper
            )
            self.assertIn("cd $(LITAI_LEGACY) && ./repo.sh build --release", wrapper)
            inventory = json.loads(
                (target / ".literate" / "harness-inventory.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(inventory["ci"]["class"], "remote-configured")
            self.assertEqual(
                [stage["id"] for stage in inventory["stages"]],
                ["build", "build.kit", "build.rendering"],
            )
            manifest = json.loads(
                (target / "literate.project.json").read_text(encoding="utf-8")
            )
            self.assertIn(
                "+flavor://literate-ai/build-repo-man",
                manifest["default_flavor_selectors"],
            )
            self.assertIn(
                "+flavor://literate-ai/lang-cpp",
                manifest["default_flavor_selectors"],
            )
            self.assertNotIn(
                "+flavor://literate-ai/lang-python",
                manifest["default_flavor_selectors"],
            )
            self.assertEqual(result["detected_languages"], ["cpp", "python"])
            self.assertEqual(result["lift_shift"]["state"], "passed")
            completed = subprocess.run(
                ("make", "-f", HARNESS_WRAPPER_FILENAME, "build.kit"),
                cwd=target,
                capture_output=True,
                text=True,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIn("kit build", completed.stdout)

    def test_wrapper_recipe_rejects_cwd_escape(self) -> None:
        inventory = {
            "commands": {
                "build": {
                    "command": "true",
                    "evidence": "Makefile",
                    "cwd": "../../etc",
                }
            },
            "stages": [
                {
                    "id": "build",
                    "command": "true",
                    "evidence": "Makefile",
                    "cwd": "../../etc",
                    "cost": "local-cheap",
                }
            ],
        }
        wrapper = render_harness_wrapper(inventory, legacy_directory="_legacy/x")
        self.assertIn("$(error harness cwd escapes the legacy tree", wrapper)
        self.assertNotIn("../../etc", wrapper)
        self.assertNotIn("cd $(LITAI_LEGACY)/../", wrapper)

    def test_harness_diagnostic_excerpt_redacts_environment_secrets(self) -> None:
        secret = "conversion-secret-value"
        program = (
            "import os, sys; "
            "sys.stdout.buffer.write(os.environ['CONVERT_API_TOKEN'].encode() + b'\\n')"
        )
        command = (
            subprocess.list2cmdline([sys.executable, "-c", program])
            if os.name == "nt"
            else shlex.join([sys.executable, "-c", program])
        )
        with (
            tempfile.TemporaryDirectory() as directory,
            patch.dict(os.environ, {"CONVERT_API_TOKEN": secret}, clear=False),
        ):
            result = _run_harness_command(
                "build",
                {"command": command, "evidence": "synthetic"},
                legacy_root=Path(directory),
                timeout_seconds=30,
            )

        self.assertNotIn(secret, result["stdout_excerpt"])
        self.assertEqual(result["stdout_excerpt"], "<redacted>")
        self.assertEqual(
            result["stdout_identity"],
            "sha256:" + hashlib.sha256(f"{secret}\n".encode()).hexdigest(),
        )

    def test_repo_test_result_file_supplies_bounded_retained_count(self) -> None:
        program = (
            "from pathlib import Path; "
            "p=Path('_build/linux-x86_64/release/_testoutput/repo_test_results.txt'); "
            "p.parent.mkdir(parents=True); "
            "p.write_text('[OK] All 427 tests processes returned 0.\\n')"
        )
        command = (
            subprocess.list2cmdline([sys.executable, "-c", program])
            if os.name == "nt"
            else shlex.join([sys.executable, "-c", program])
        )
        with tempfile.TemporaryDirectory() as directory:
            result = _run_harness_command(
                "test",
                {"command": command, "evidence": "repo.toml"},
                legacy_root=Path(directory),
                timeout_seconds=30,
            )

        self.assertEqual(
            result["test_collection"],
            {
                "state": "nonempty",
                "total": 427,
                "passed": 427,
                "failed": 0,
                "skipped": 0,
                "known_failed": 0,
                "source": "repo-test-result-files",
                "files": [
                    "_build/linux-x86_64/release/_testoutput/repo_test_results.txt"
                ],
            },
        )

    def test_repo_test_result_file_must_change_during_current_command(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result_path = root / "_testoutput/repo_test_results.txt"
            result_path.parent.mkdir(parents=True)
            result_path.write_text("[OK] All 427 tests processes returned 0.\n")
            result = _run_harness_command(
                "test",
                {"command": "true", "evidence": "repo.toml"},
                legacy_root=root,
                timeout_seconds=30,
            )

        self.assertEqual(result["test_collection"]["state"], "unreported")

    def test_root_repo_test_result_file_supplies_bounded_retained_count(self) -> None:
        program = (
            "from pathlib import Path; "
            "p=Path('_testoutput/repo_test_results.txt'); "
            "p.parent.mkdir(parents=True); "
            "p.write_text('[OK] All 211 tests processes returned 0.\\n')"
        )
        command = (
            subprocess.list2cmdline([sys.executable, "-c", program])
            if os.name == "nt"
            else shlex.join([sys.executable, "-c", program])
        )
        with tempfile.TemporaryDirectory() as directory:
            result = _run_harness_command(
                "test",
                {"command": command, "evidence": "repo.toml"},
                legacy_root=Path(directory),
                timeout_seconds=30,
            )

        self.assertEqual(
            result["test_collection"],
            {
                "state": "nonempty",
                "total": 211,
                "passed": 211,
                "failed": 0,
                "skipped": 0,
                "known_failed": 0,
                "source": "repo-test-result-files",
                "files": ["_testoutput/repo_test_results.txt"],
            },
        )

    @unittest.skipIf(
        os.name == "nt", "symlink creation requires elevated Windows policy"
    )
    def test_root_repo_test_result_symlink_escape_is_not_admitted(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            tempfile.TemporaryDirectory() as outside,
        ):
            root = Path(directory)
            outside_root = Path(outside)
            (outside_root / "repo_test_results.txt").write_text(
                "[OK] All 211 tests processes returned 0.\n"
            )
            (root / "_testoutput").symlink_to(outside_root, target_is_directory=True)
            result = _run_harness_command(
                "test",
                {"command": "true", "evidence": "repo.toml"},
                legacy_root=root,
                timeout_seconds=30,
            )

        self.assertEqual(result["test_collection"]["state"], "unreported")


if __name__ == "__main__":
    unittest.main()
