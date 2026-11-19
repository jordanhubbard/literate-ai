"""Release CI must not change when a third-party action tag moves."""

from __future__ import annotations

import importlib.util
import json
import re
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

from literate_ai.compatibility.ova import load_yaml_subset

ROOT = Path(__file__).resolve().parents[2]
USES = re.compile(r"(?m)^\s*(?:-\s*)?uses:\s*([^\n#]+)")
PIN = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_./-]+@[0-9a-f]{40}")


class CiActionPinTests(unittest.TestCase):
    @staticmethod
    def selector():
        spec = importlib.util.spec_from_file_location(
            "select_ci_profile", ROOT / "scripts/select_ci_profile.py"
        )
        selector = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(selector)
        return selector

    def test_schema_check_precedes_fanout_on_relevant_paths_and_full_profiles(
        self,
    ) -> None:
        selector = self.selector()
        for path in (
            "schemas/v2/index.json",
            "schemas/v2/project-release.schema.json",
            "src/literate_ai/schema_catalog.py",
            "tools/build_backend/literate_ai_build_backend.py",
        ):
            with self.subTest(path=path):
                self.assertTrue(
                    selector.select_schema_preflight(
                        "pull_request", "main", ("README.md", path)
                    )
                )
        self.assertFalse(
            selector.select_schema_preflight("pull_request", "main", ("README.md",))
        )
        self.assertFalse(
            selector.select_schema_preflight("push", "refs/heads/main", ("README.md",))
        )
        self.assertTrue(selector.select_schema_preflight("pull_request", "main", None))
        self.assertTrue(
            selector.select_schema_preflight("workflow_dispatch", "main", ())
        )
        self.assertTrue(
            selector.select_schema_preflight(
                "pull_request", "release/1.4", ("README.md",)
            )
        )

    def test_change_scoped_profiles_are_narrow_and_fail_closed(self) -> None:
        selector = self.selector()

        documentation = selector.select_matrix(
            "pull_request",
            "main",
            (
                "README.md",
                "CONTRIBUTING.md",
                "PROJECT.md",
                "docs/user/html-repository-explorer.md",
                "docs/presentations/release/deck.pptx",
            ),
        )["include"]
        self.assertEqual([row["task"] for row in documentation], ["documentation"])

        policy_and_documentation = selector.select_matrix(
            "pull_request",
            "main",
            (
                "README.md",
                "scripts/select_ci_profile.py",
                "tests/critical/test_ci_action_pins.py",
            ),
        )["include"]
        self.assertEqual(
            [row["task"] for row in policy_and_documentation],
            ["documentation", "ci-policy"],
        )

        elixir = selector.select_matrix(
            "pull_request",
            "main",
            (
                "flavors/build-mix/flavor.md",
                "tests/conformance/test_elixir_mix_qualification.py",
            ),
        )["include"]
        self.assertEqual(
            len([row for row in elixir if row["task"] == "elixir-native"]), 6
        )
        self.assertIn("conformance", {row["task"] for row in elixir})

        for changed_paths in ((), ("src/literate_ai/cli/render.py",)):
            with self.subTest(changed_paths=changed_paths):
                selected = selector.select_matrix(
                    "pull_request", "main", changed_paths
                )["include"]
                self.assertTrue(selected)
                self.assertNotIn("documentation", {row["task"] for row in selected})
                self.assertNotIn("ci-policy", {row["task"] for row in selected})
                self.assertIn("conformance", {row["task"] for row in selected})

        full = selector.select_matrix("push", "", ("README.md",))["include"]
        self.assertTrue(full)
        self.assertNotIn("scoped", {key for row in full for key in row})

        self.assertFalse(
            selector.select_freebsd_acl(
                "pull_request", "main", ("README.md", "docs/user/guide.md")
            )
        )
        self.assertFalse(
            selector.select_freebsd_acl(
                "pull_request", "main", ("src/literate_ai/cli/render.py",)
            )
        )
        self.assertTrue(
            selector.select_freebsd_acl(
                "pull_request",
                "main",
                ("src/literate_ai/adapters/retained_posix_acl.py",),
            )
        )
        self.assertTrue(selector.select_freebsd_acl("pull_request", "main", None))
        self.assertTrue(
            selector.select_freebsd_acl("pull_request", "release/1.3.x", ("README.md",))
        )
        self.assertTrue(selector.select_freebsd_acl("push", "", ("README.md",)))

    def test_conference_publication_changes_scope_without_hiding_product_code(
        self,
    ) -> None:
        selector = self.selector()
        paths = (
            "README.md",
            "labs/README.md",
            "docs/conference/attendee-setup.md",
            "scripts/build_conference_site.mjs",
            "scripts/verify_conference_browser.mjs",
            "verification/1.3.1-release-publication.json",
            "verification/1.3.1-windows-qualification-exception.json",
        )
        for event, ref in (("pull_request", "main"), ("push", "refs/heads/main")):
            with self.subTest(event=event):
                rows = selector.select_matrix(event, ref, paths)["include"]
                self.assertEqual([row["task"] for row in rows], ["documentation"])
                self.assertFalse(selector.select_full_qualification(event, ref, paths))
                self.assertFalse(selector.select_freebsd_acl(event, ref, paths))
                for product in (
                    "src/literate_ai/cli.py",
                    "verification/another-release.json",
                ):
                    mixed = paths + (product,)
                    tasks = {
                        row["task"]
                        for row in selector.select_matrix(event, ref, mixed)["include"]
                    }
                    self.assertIn("conformance", tasks)
                    if event == "push":
                        self.assertTrue(
                            selector.select_full_qualification(event, ref, mixed)
                        )

    def test_only_documentation_root_manifest_changes_are_documentation_scope(self):
        selector = self.selector()
        before = {
            "project_id": "test",
            "documentation_roots": ["docs", "labs"],
            "component_roots": ["components"],
        }
        after = {**before, "documentation_roots": ["docs"]}
        with mock.patch.dict(
            selector.os.environ, {"CI_BASE_SHA": "base", "CI_HEAD_SHA": "head"}
        ):
            for proposed, expected in (
                (after, "documentation"),
                ({**after, "component_roots": ["different"]}, None),
                ({**after, "project_id": "other"}, None),
                ({**after, "documentation_roots": []}, None),
                (before, None),
            ):
                with (
                    self.subTest(proposed=proposed),
                    mock.patch.object(selector.subprocess, "run") as run,
                ):
                    run.side_effect = [
                        mock.Mock(returncode=0, stdout=json.dumps(m).encode())
                        for m in (before, proposed)
                    ]
                    self.assertEqual(selector._scope("literate.project.json"), expected)
            with mock.patch.object(
                selector.subprocess, "run", side_effect=OSError("unavailable")
            ):
                self.assertIsNone(selector._scope("literate.project.json"))
            for malformed in (
                b"{",
                b"[]",
                b'{"documentation_roots":["docs"],"project_id":"a","project_id":"b"}',
            ):
                with (
                    self.subTest(malformed=malformed),
                    mock.patch.object(selector.subprocess, "run") as run,
                ):
                    run.side_effect = [
                        mock.Mock(returncode=0, stdout=json.dumps(before).encode()),
                        mock.Mock(returncode=0, stdout=malformed),
                    ]
                    self.assertIsNone(selector._scope("literate.project.json"))
        with mock.patch.dict(
            selector.os.environ, {"CI_BASE_SHA": "", "CI_HEAD_SHA": ""}
        ):
            self.assertIsNone(selector._scope("literate.project.json"))

    def test_lab_changes_select_browser_checks_and_keep_product_changes_broad(self):
        selector = self.selector()
        paths = ("labs/00-grumpy-counter/main.js", "labs/scripts/test_lab_media.cjs")
        for event, ref in (("pull_request", "main"), ("push", "refs/heads/main")):
            rows = selector.select_matrix(event, ref, paths)["include"]
            self.assertEqual([r["task"] for r in rows], ["labs"])
            self.assertFalse(selector.select_full_qualification(event, ref, paths))
            mixed = paths + ("src/literate_ai/cli.py",)
            self.assertIn(
                "conformance",
                {
                    r["task"]
                    for r in selector.select_matrix(event, ref, mixed)["include"]
                },
            )
        workflow = load_yaml_subset((ROOT / ".github/workflows/ci.yml").read_text())
        steps = [
            s
            for s in workflow["jobs"]["checks"]["steps"]
            if s.get("if") == "matrix.task == 'labs'"
        ]
        text = json.dumps(steps)
        self.assertIn("test_labs_browser.cjs", text)
        self.assertIn("test_lab_media.cjs", text)
        self.assertNotIn("make validate", text)
        self.assertNotIn("wheel-check", text)

    def test_scoped_workflow_steps_do_not_requalify_unchanged_freebsd_job(self):
        selector = self.selector()
        # CI selector tests run in ci-policy; the actual native fixture still
        # requires its target probe.
        self.assertFalse(
            selector.select_freebsd_acl(
                "pull_request", "main", ("tests/critical/test_ci_action_pins.py",)
            )
        )
        self.assertTrue(
            selector.select_freebsd_acl(
                "pull_request", "main", ("tests/critical/test_retained_posix_acl.py",)
            )
        )
        before = (
            "jobs:\n  profile:\n    runs-on: ubuntu-latest\n"
            "  checks:\n    steps:\n      - name: Docs\n"
            "        if: matrix.task == 'documentation'\n        run: old-check\n"
            "  freebsd-posix-acl:\n    runs-on: ubuntu-latest\n"
        )
        scoped = before.replace("run: old-check", "run: new-check")
        for after, expected in (
            (scoped, False),
            ("permissions:\n  contents: write\n" + scoped, True),
            (
                scoped.replace(
                    "run: new-check", "run: new-check\n        env: &shared {}"
                ),
                True,
            ),
            (
                scoped.replace(
                    "  freebsd-posix-acl:\n    runs-on: ubuntu-latest",
                    "  freebsd-posix-acl:\n    runs-on: different",
                ),
                True,
            ),
            (
                scoped.replace(
                    "  profile:\n    runs-on: ubuntu-latest",
                    "  profile:\n    runs-on: different",
                ),
                True,
            ),
        ):
            with (
                self.subTest(after=after),
                mock.patch.dict(
                    selector.os.environ, {"CI_BASE_SHA": "base", "CI_HEAD_SHA": "head"}
                ),
                mock.patch.object(selector.subprocess, "run") as run,
            ):
                run.side_effect = [
                    mock.Mock(returncode=0, stdout=t.encode()) for t in (before, after)
                ]
                self.assertEqual(
                    selector.select_freebsd_acl(
                        "pull_request", "main", (".github/workflows/ci.yml",)
                    ),
                    expected,
                )
        with mock.patch.dict(
            selector.os.environ, {"CI_BASE_SHA": "", "CI_HEAD_SHA": ""}
        ):
            self.assertTrue(
                selector.select_freebsd_acl(
                    "pull_request", "main", (".github/workflows/ci.yml",)
                )
            )

    def test_default_branch_pushes_scope_docs_but_preserve_qualification(self) -> None:
        selector = self.selector()
        for paths, tasks in (
            (("README.md", "docs/conference/README.md"), ["documentation"]),
            (
                ("docs/README.md", "scripts/select_ci_profile.py"),
                ["documentation", "ci-policy"],
            ),
        ):
            with self.subTest(paths=paths):
                selected = selector.select_matrix("push", "refs/heads/main", paths)
                self.assertEqual([row["task"] for row in selected["include"]], tasks)
                self.assertFalse(
                    selector.select_freebsd_acl("push", "refs/heads/main", paths)
                )
                self.assertFalse(
                    selector.select_full_qualification("push", "refs/heads/main", paths)
                )

        for event, ref, paths in (
            ("push", "refs/heads/main", None),
            ("push", "refs/heads/main", ()),
            ("push", "refs/heads/main", ("README.md", "src/literate_ai/cli.py")),
            ("push", "refs/heads/main", ("unclassified-input",)),
            ("push", "refs/heads/main", ("verification/current.json",)),
            ("push", "refs/heads/release/1.3.x", ("README.md",)),
            ("push", "refs/tags/v1.3.1", ("README.md",)),
            ("workflow_dispatch", "refs/heads/main", ("README.md",)),
        ):
            with self.subTest(event=event, ref=ref, paths=paths):
                rows = selector.select_matrix(event, ref, paths)["include"]
                self.assertTrue(rows)
                self.assertTrue(all("scoped" not in row for row in rows))
                self.assertEqual(
                    len([row for row in rows if row["task"] == "elixir-native"]), 6
                )
                self.assertTrue(selector.select_freebsd_acl(event, ref, paths))
                self.assertTrue(selector.select_full_qualification(event, ref, paths))

        self.assertTrue(
            selector.select_freebsd_acl(
                "push", "refs/heads/main", (".github/workflows/ci.yml",)
            )
        )

    def test_fixture_only_changes_receive_three_native_scoped_cells(self):
        selector = self.selector()
        paths = (
            "tests/critical/test_roadmap_dependencies.py",
            "tests/critical/test_retained_posix_acl.py",
            "verification/windows-portable-fixtures-qualification.json",
            "docs/roadmap/active-work.md",
        )
        for event, ref in (("pull_request", "main"), ("push", "refs/heads/main")):
            with self.subTest(event=event):
                rows = selector.select_matrix(event, ref, paths)["include"]
                fixtures = [r for r in rows if r["task"] == "qualification-fixtures"]
                self.assertEqual(len(fixtures), 3)
                self.assertEqual(
                    {r["os"] for r in fixtures},
                    {
                        "windows-latest",
                        "macos-latest",
                        "ubuntu-latest",
                    },
                )
                self.assertTrue(all(r.get("scoped") for r in rows))
                self.assertFalse(selector.select_full_qualification(event, ref, paths))
                self.assertTrue(selector.select_freebsd_acl(event, ref, paths))
        for event, ref in (
            ("push", "refs/heads/release/1.3.x"),
            ("pull_request", "release/1.3.x"),
            ("workflow_dispatch", "refs/heads/main"),
        ):
            with self.subTest(event=event, ref=ref):
                rows = selector.select_matrix(event, ref, paths)["include"]
                self.assertTrue(all("scoped" not in r for r in rows))
                self.assertTrue(selector.select_full_qualification(event, ref, paths))

    def test_product_prs_retain_normal_cells_and_changed_fixture_cells(self):
        selector = self.selector()
        rows = selector.select_matrix(
            "pull_request",
            "main",
            (
                "src/literate_ai/application/roadmap_dependencies.py",
                "tests/critical/test_roadmap_dependencies.py",
            ),
        )["include"]
        self.assertIn("conformance", {r["task"] for r in rows})
        self.assertEqual(sum(r["task"] == "qualification-fixtures" for r in rows), 3)

    def test_native_sdk_harness_changes_select_policy_checks_not_product_builds(self):
        selector = self.selector()
        paths = (
            ".github/workflows/native-sdk-qualification.yml",
            ".github/qualifications/native_sdk/qualify_public_sdk.py",
            ".github/qualifications/native_sdk/source_transport.py",
            ".github/qualifications/native_sdk/run_cell.py",
            ".github/qualifications/native_sdk/collect_results.py",
            "tests/critical/test_native_sdk_qualification_harness.py",
            "verification/freebsd-native-sdk-qualification.json",
        )
        for event, ref in (("pull_request", "main"), ("push", "refs/heads/main")):
            with self.subTest(event=event):
                self.assertEqual(
                    [
                        r["task"]
                        for r in selector.select_matrix(event, ref, paths)["include"]
                    ],
                    ["ci-policy"],
                )
                self.assertFalse(selector.select_full_qualification(event, ref, paths))
        self.assertTrue(
            selector.select_full_qualification(
                "push",
                "refs/heads/release/1.3.x",
                paths,
            )
        )

    def test_push_diff_uses_both_endpoints_and_unknown_diff_fails_closed(self) -> None:
        selector = self.selector()
        with mock.patch.object(selector.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout=b"README.md\0")
            self.assertEqual(selector._changed_paths("before", "after"), ("README.md",))
            self.assertEqual(run.call_args.args[0][-2:], ("before", "after"))
            # Retain the old path when a schema is moved out of its catalog.
            self.assertIn("--no-renames", run.call_args.args[0])
            run.return_value = mock.Mock(returncode=128, stdout=b"")
            self.assertIsNone(selector._changed_paths("before", "after"))
            run.side_effect = selector.subprocess.TimeoutExpired("git", 30)
            self.assertIsNone(selector._changed_paths("before", "after"))
            run.side_effect = OSError("git unavailable")
            self.assertIsNone(selector._changed_paths("before", "after"))
            run.side_effect = None
            run.return_value = mock.Mock(returncode=0, stdout=b"\xff\0")
            self.assertIsNone(selector._changed_paths("before", "after"))
            run.reset_mock()
            self.assertIsNone(selector._changed_paths("", "after"))
            run.assert_not_called()

    def test_pr_comparison_uses_one_merge_base(self):
        selector = self.selector()
        base = b"a" * 40
        head = "b" * 40
        with mock.patch.object(selector.subprocess, "run") as run:
            run.return_value = mock.Mock(returncode=0, stdout=base + b"\n")
            self.assertEqual(selector._merge_base("main", head), base.decode())
            self.assertEqual(
                run.call_args.args[0], ("git", "merge-base", "--all", "main", head)
            )
            run.return_value.stdout += b"c" * 40 + b"\n"
            self.assertEqual(selector._merge_base("main", head), "")

    def test_changed_action_pins_select_their_actual_runtime_cells(self):
        selector = self.selector()
        ci_path = ".github/workflows/ci.yml"
        sdk_path = ".github/workflows/native-sdk-qualification.yml"
        ci_before = (ROOT / ci_path).read_text()
        sdk_before = (ROOT / sdk_path).read_text()

        def update_pin(text, action, old_sha, new_sha):
            pattern = re.escape(action) + "@[0-9a-f]{40}"
            before, old_count = re.subn(pattern, action + "@" + old_sha, text)
            after, new_count = re.subn(pattern, action + "@" + new_sha, text)
            self.assertEqual((old_count, new_count), (1, 1))
            return before, after

        bazel = update_pin(
            ci_before,
            "bazel-contrib/setup-bazel",
            "104e3eea9447cdaa4b00d0fb46191a3985d26ab3",
            "f34d6a05eae3c24acab7fa54587492daeaeffdab",
        )
        old_sha = "c46abacb49f09938ca4e1702d15d836285d694cc"
        new_sha = "811efaaac0668df8bfb8308c3ec997b5ab50037b"
        freebsd = update_pin(ci_before, "vmactions/freebsd-vm", old_sha, new_sha)
        sdk = update_pin(sdk_before, "vmactions/freebsd-vm", old_sha, new_sha)
        for revisions, native_rows, expected_freebsd in (
            ({ci_path: bazel}, ["ubuntu-latest", "windows-latest"], False),
            ({ci_path: freebsd, sdk_path: sdk}, [], True),
        ):
            paths = tuple(revisions)
            with mock.patch.object(
                selector, "_workflow_versions", side_effect=revisions.__getitem__
            ):
                delta = selector._workflow_delta(paths)
            for event, ref in (("pull_request", "main"), ("push", "refs/heads/main")):
                with self.subTest(paths=paths, event=event):
                    matrix = selector.select_matrix(event, ref, paths, delta=delta)
                    self.assertEqual(
                        [row["task"] for row in matrix["include"]],
                        ["ci-policy"] + ["cpp-native"] * len(native_rows),
                    )
                    self.assertEqual(
                        [
                            row["os"]
                            for row in matrix["include"]
                            if row["task"] == "cpp-native"
                        ],
                        native_rows,
                    )
                    self.assertIs(
                        selector.select_freebsd_acl(event, ref, paths, delta=delta),
                        expected_freebsd,
                    )
                    self.assertIs(delta.freebsd_sdk, expected_freebsd)
                    self.assertFalse(
                        selector.select_full_qualification(
                            event, ref, paths, delta=delta
                        )
                    )

    def test_shared_or_unresolved_workflow_changes_use_full_coverage(self):
        selector = self.selector()
        path = ".github/workflows/ci.yml"
        baseline = (ROOT / path).read_text()
        changes = (
            None,
            (baseline, baseline.replace("contents: read", "contents: write", 1)),
            (
                baseline,
                baseline.replace("  checks:\n", "  checks:\n    env: {SHARED: true}\n"),
            ),
            (
                baseline,
                baseline.replace(
                    "if: matrix.task == 'cpp-native'", "if: matrix.task == 'unknown'", 1
                ),
            ),
            (
                baseline,
                baseline.replace(
                    "if: matrix.task == 'cpp-native'",
                    "if: matrix.task == 'cpp-native' || success()",
                    1,
                ),
            ),
        )
        for change in changes:
            with (
                self.subTest(change=changes.index(change)),
                mock.patch.object(selector, "_workflow_versions", return_value=change),
            ):
                delta = selector._workflow_delta((path,))
                for event, ref in (
                    ("pull_request", "main"),
                    ("push", "refs/heads/main"),
                ):
                    self.assertTrue(
                        selector.select_full_qualification(
                            event, ref, (path,), delta=delta
                        )
                    )
                    self.assertTrue(
                        selector.select_freebsd_acl(event, ref, (path,), delta=delta)
                    )
                    rows = selector.select_matrix(event, ref, (path,), delta=delta)[
                        "include"
                    ]
                    self.assertTrue(
                        all(
                            row in rows
                            for row in selector._matrix_rows()
                            if "scoped" not in row
                        )
                    )

    def test_scoped_workflow_edit_keeps_its_cell_in_a_mixed_main_push(self):
        selector = self.selector()
        path = ".github/workflows/ci.yml"
        baseline = (ROOT / path).read_text()
        changed = baseline.replace(
            "name: Validate framework documentation ownership",
            "name: Validate source documentation ownership",
        )
        paths = (path, "src/literate_ai/cli/render.py")
        with mock.patch.object(
            selector, "_workflow_versions", return_value=(baseline, changed)
        ):
            delta = selector._workflow_delta(paths)
        self.assertEqual(delta.tasks, {"documentation"})
        rows = selector.select_matrix("push", "refs/heads/main", paths, delta=delta)[
            "include"
        ]
        self.assertIn("documentation", {row["task"] for row in rows})
        self.assertTrue(
            selector.select_full_qualification(
                "push", "refs/heads/main", paths, delta=delta
            )
        )
        release = selector.select_matrix(
            "push", "refs/heads/release/1.4.x", paths, delta=delta
        )["include"]
        self.assertTrue(all("scoped" not in row for row in release))

    def test_broad_fallback_preserves_a_detected_documentation_action(self):
        selector = self.selector()
        path = ".github/workflows/ci.yml"
        baseline = (ROOT / path).read_text()
        edited = baseline.replace(
            "name: Validate framework documentation ownership",
            "name: Validate source documentation ownership",
        )
        shared_workflow_edit = edited.replace("contents: read", "contents: write", 1)
        mixed_step = edited.replace(
            "if: matrix.task == 'cpp-native'",
            "if: matrix.task == 'cpp-native' || success()",
            1,
        )
        for after, extra in (
            (edited, (".github/ci-matrix.json",)),
            (edited, (".github/workflows/unknown-review.yml",)),
            (shared_workflow_edit, ()),
            (mixed_step, ()),
        ):
            paths = (path, *extra)
            with mock.patch.object(
                selector, "_workflow_versions", return_value=(baseline, after)
            ):
                delta = selector._workflow_delta(paths)
            self.assertTrue(delta.broad)
            self.assertIn("documentation", delta.tasks)
            for event, ref in (("pull_request", "main"), ("push", "refs/heads/main")):
                with self.subTest(paths=paths, event=event):
                    rows = selector.select_matrix(event, ref, paths, delta=delta)[
                        "include"
                    ]
                    self.assertIn("documentation", {row["task"] for row in rows})
                    self.assertTrue(
                        all(
                            row in rows
                            for row in selector._matrix_rows()
                            if "scoped" not in row
                        )
                    )

    def test_sdk_caller_runtime_edits_select_separate_guest_but_metadata_does_not(self):
        selector = self.selector()
        path = ".github/workflows/ci.yml"
        sdk_path = ".github/workflows/native-sdk-qualification.yml"
        baseline = (ROOT / path).read_text()
        scoped = baseline.replace(
            "    uses: ./.github/workflows/native-sdk-qualification.yml",
            "    name: Native SDK control\n"
            "    uses: ./.github/workflows/native-sdk-qualification.yml",
        )
        changed = baseline.replace(
            "candidate_revision: ${{ github.sha }}",
            "candidate_revision: ${{ github.event.pull_request.head.sha }}",
        )
        for candidate, expected in ((scoped, False), (changed, True)):
            with (
                self.subTest(expected=expected),
                mock.patch.object(
                    selector, "_workflow_versions", return_value=(baseline, candidate)
                ),
            ):
                delta = selector._workflow_delta((path,))
                self.assertIs(delta.freebsd_sdk, expected)
                self.assertFalse(delta.freebsd_acl)
                self.assertFalse(delta.broad)
        unchanged_sdk = (ROOT / sdk_path).read_text()
        with mock.patch.object(
            selector,
            "_workflow_versions",
            side_effect=((baseline, changed), (unchanged_sdk, unchanged_sdk)),
        ):
            self.assertTrue(selector._workflow_delta((path, sdk_path)).freebsd_sdk)

    def test_unproved_workflow_routing_runs_every_matrix_row(self):
        selector = self.selector()
        path = ".github/workflows/ci.yml"
        baseline = (ROOT / path).read_text()
        added_condition = baseline.replace(
            "      # sample-composition",
            "      - name: Additional documentation check\n"
            "        if: ${{ matrix.task == 'documentation' }}\n"
            "        run: make documentation-check\n"
            "      # sample-composition",
        )
        anchored_caller = baseline.replace(
            "env:\n  PYTHONUNBUFFERED", "env: &review_env\n  PYTHONUNBUFFERED", 1
        ).replace(
            "candidate_revision: ${{ github.sha }}",
            "candidate_revision: ${{ github.event.pull_request.head.sha }}",
        )
        for edited, other_path, sdk in (
            (added_condition, (), False),
            (anchored_caller, (), True),
            (added_condition, (".github/workflows/unknown-review.yml",), True),
        ):
            paths = (path, *other_path)
            with mock.patch.object(
                selector, "_workflow_versions", return_value=(baseline, edited)
            ):
                delta = selector._workflow_delta(paths)
            self.assertTrue(delta.broad)
            self.assertIs(delta.freebsd_sdk, sdk)
            for event, ref in (("pull_request", "main"), ("push", "refs/heads/main")):
                with self.subTest(event=event, sdk=sdk, paths=paths):
                    self.assertEqual(
                        selector.select_matrix(event, ref, paths, delta=delta)[
                            "include"
                        ],
                        selector._matrix_rows(),
                    )
                    self.assertTrue(
                        selector.select_full_qualification(
                            event, ref, paths, delta=delta
                        )
                    )
            release_rows = selector.select_matrix(
                "pull_request", "release/1.4.x", paths, delta=delta
            )["include"]
            self.assertEqual(
                release_rows,
                [row for row in selector._matrix_rows() if "scoped" not in row],
            )

    def test_sdk_qualification_remains_selected_after_shared_caller_changes(self):
        selector = self.selector()
        path = ".github/workflows/ci.yml"
        baseline = (ROOT / path).read_text()
        for after in (
            baseline.replace("  contents: read", "  contents: none", 1),
            baseline.replace(
                "  profile:\n    runs-on: ubuntu-latest",
                "  profile:\n    runs-on: ubuntu-24.04",
            ),
        ):
            self.assertNotEqual(after, baseline)
            with mock.patch.object(
                selector, "_workflow_versions", return_value=(baseline, after)
            ):
                delta = selector._workflow_delta((path,))
            self.assertTrue(delta.broad)
            self.assertTrue(delta.freebsd_sdk)
            self.assertTrue(delta.freebsd_acl)

    def test_sdk_policy_metadata_does_not_run_native_guest(self):
        selector = self.selector()
        path = ".github/workflows/native-sdk-qualification.yml"
        baseline = (ROOT / path).read_text()
        with mock.patch.object(
            selector,
            "_workflow_versions",
            return_value=(
                baseline,
                "# Scope note\n"
                + baseline.replace(
                    "name: Native FreeBSD SDK qualification", "name: Native SDK"
                ),
            ),
        ):
            self.assertFalse(selector._workflow_delta((path,)).freebsd_sdk)

    def test_sdk_caller_binds_read_only_integration_checkout(self):
        ci = load_yaml_subset((ROOT / ".github/workflows/ci.yml").read_text())
        caller = ci["jobs"]["freebsd-native-sdk"]
        self.assertEqual(caller["if"], "needs.profile.outputs.freebsd_sdk == 'true'")
        self.assertEqual(
            caller["uses"], "./.github/workflows/native-sdk-qualification.yml"
        )
        self.assertEqual(caller["permissions"], {"contents": "read"})
        self.assertNotIn("secrets", caller)
        self.assertEqual(caller["with"]["candidate_revision"], "${{ github.sha }}")
        sdk = load_yaml_subset((ROOT / caller["uses"]).read_text())
        self.assertIn("workflow_dispatch", sdk["on"])
        self.assertTrue(
            sdk["on"]["workflow_call"]["inputs"]["candidate_revision"]["required"]
        )
        self.assertEqual(sdk["permissions"], {"contents": "read"})
        steps = sdk["jobs"]["public-sdk"]["steps"]
        self.assertFalse(steps[0]["with"]["persist-credentials"])
        archive = next(
            step["run"]
            for step in steps
            if step.get("name", "").startswith("Build the exact")
        )
        self.assertIn('test "$(git rev-parse HEAD)" = "$GITHUB_SHA"', archive)
        self.assertIn('test "$(git rev-parse HEAD^2)" = "$PULL_REQUEST_HEAD"', archive)
        self.assertIn(
            '"qualification_harness_revision": os.environ["GITHUB_SHA"]', archive
        )
        self.assertIn(
            '"pull_request_head": os.environ.get("PULL_REQUEST_HEAD")', archive
        )

    def test_workflow_runs_only_the_checks_owned_by_each_scoped_profile(self) -> None:
        workflow = load_yaml_subset((ROOT / ".github/workflows/ci.yml").read_text())
        profile_steps = workflow["jobs"]["profile"]["steps"]
        profile = next(step for step in profile_steps if step.get("id") == "select")
        self.assertEqual(workflow["jobs"]["checks"]["needs"], "profile")
        [schema_check] = [
            step for step in profile_steps if "make schema-check" in step.get("run", "")
        ]
        self.assertEqual(
            schema_check["if"], "steps.select.outputs.schema_preflight == 'true'"
        )
        self.assertLess(profile_steps.index(profile), profile_steps.index(schema_check))
        self.assertEqual(
            profile["env"]["CI_BASE_REF"], "${{ github.base_ref || github.ref }}"
        )
        self.assertEqual(
            profile["env"]["CI_BASE_SHA"],
            "${{ github.event.pull_request.base.sha || github.event.before }}",
        )
        self.assertEqual(
            profile["env"]["CI_HEAD_SHA"],
            "${{ github.event.pull_request.head.sha || github.sha }}",
        )
        freebsd = workflow["jobs"]["freebsd-posix-acl"]
        self.assertEqual(freebsd["needs"], "profile")
        self.assertEqual(freebsd["if"], "needs.profile.outputs.freebsd_acl == 'true'")
        macos = workflow["jobs"]["macos-qualification"]
        self.assertEqual(macos["needs"], "profile")
        self.assertEqual(
            macos["if"], "needs.profile.outputs.full_qualification == 'true'"
        )
        steps = workflow["jobs"]["checks"]["steps"]
        documentation_steps = [
            step for step in steps if step.get("if") == "matrix.task == 'documentation'"
        ]
        policy_steps = [
            step for step in steps if step.get("if") == "matrix.task == 'ci-policy'"
        ]
        self.assertTrue(documentation_steps)
        self.assertTrue(policy_steps)
        documentation_text = json.dumps(documentation_steps)
        self.assertIn("documentation-check", documentation_text)
        self.assertIn("public-export-check", documentation_text)
        self.assertIn("test_roadmap_goal_gate", documentation_text)
        policy_text = json.dumps(policy_steps)
        self.assertIn("tests.critical.test_ci_action_pins", policy_text)
        self.assertNotIn("make validate", documentation_text + policy_text)
        self.assertNotIn("wheel-check", documentation_text + policy_text)

    def test_windows_native_receiver_runs_once_without_xdist_contention(self) -> None:
        workflow = load_yaml_subset((ROOT / ".github/workflows/ci.yml").read_text())
        steps = workflow["jobs"]["checks"]["steps"]
        shard = next(
            step for step in steps if step.get("name") == "Run this shard's tests"
        )
        receiver = next(
            step
            for step in steps
            if step.get("name")
            == "Qualify the native receiver without xdist contention"
        )
        upload = next(
            step
            for step in steps
            if step.get("name") == "Upload the profiling trace and hotspot report"
        )
        test_id = (
            "tests/smoke/test_remote_standard_toolchains.py::"
            "RemoteStandardToolchainTests::"
            "test_actual_admitted_receiver_supplies_discovery_and_live_profile_guard"
        )
        self.assertIn(f"--deselect={test_id}", shard["run"])
        self.assertEqual(
            receiver["if"], "matrix.task == 'windows-tests' && matrix.group == 3"
        )
        self.assertEqual(receiver["timeout-minutes"], 45)
        self.assertIn("-o addopts=''", receiver["run"])
        self.assertIn(test_id, receiver["run"])
        self.assertIn(
            "profile-${{ matrix.group }}-receiver.ndjson", upload["with"]["path"]
        )
        self.assertLess(steps.index(shard), steps.index(receiver))
        self.assertLess(steps.index(receiver), steps.index(upload))

    def test_all_external_actions_use_full_commit_ids(self) -> None:
        references = []
        for path in sorted((ROOT / ".github/workflows").glob("*.y*ml")):
            for match in USES.finditer(path.read_text()):
                reference = match[1].strip().strip("\"'")
                if reference.startswith("./"):
                    continue
                references.append(reference)
                with self.subTest(workflow=path.name, reference=reference):
                    self.assertRegex(reference, "^" + PIN.pattern + "$")
        self.assertTrue(references, "pin check must inspect actual action references")

    def test_policy_rejects_tags_short_hashes_and_expressions(self) -> None:
        for reference in (
            "actions/checkout@v6",
            "actions/checkout@abcdef0",
            "${{ matrix.action }}",
        ):
            self.assertIsNone(PIN.fullmatch(reference))

    def test_elixir_matrix_requires_explicit_hex_and_unskipped_native_mix(self):
        workflow = load_yaml_subset((ROOT / ".github/workflows/ci.yml").read_text())
        all_steps = workflow["jobs"]["checks"]["steps"]
        steps = [
            step
            for step in all_steps
            if str(step.get("if", "")).startswith("matrix.task == 'elixir-native'")
        ]
        for step in all_steps:
            text = json.dumps(step)
            if any(
                marker in text
                for marker in ("elixir", "setup-beam", "LITAI_HEX", "Hex")
            ):
                with self.subTest(step=step.get("name") or step.get("uses")):
                    self.assertIn(step, steps, "Elixir steps stay in Elixir cells")
        stage = next(
            step for step in steps if "stage_elixir_hex.py" in step.get("run", "")
        )
        native = next(step for step in steps if "--junitxml=" in step.get("run", ""))
        self.assertLess(steps.index(stage), steps.index(native))
        self.assertIn("${{ matrix.hex_args }}", stage["run"])
        self.assertEqual(
            native["env"]["LITAI_ELIXIR_EXPECT_OTP"], "${{ matrix.otp_major }}"
        )
        rows = json.loads((ROOT / ".github/ci-matrix.json").read_text())
        elixir_rows = [row for row in rows if row["task"] == "elixir-native"]
        self.assertEqual(len(elixir_rows), 6)
        self.assertEqual(
            {(row["os"].split("-")[0], row["elixir"]) for row in elixir_rows},
            {
                (os_name, version)
                for os_name in ("ubuntu", "macos", "windows")
                for version in ("1.18.0", "1.20.4")
            },
        )
        for row in elixir_rows:
            self.assertEqual(row["otp_major"], row["otp"].split(".")[0])
            self.assertEqual(
                row["hex_args"],
                "--build-from-source" if row["otp_major"] == "29" else "",
            )
        selector = self.selector()
        selected = selector.select_matrix("pull_request", "main")["include"]
        selected_elixir = [row for row in selected if row["task"] == "elixir-native"]
        self.assertEqual(len(selected_elixir), 1)
        self.assertEqual(selected_elixir[0]["os"], "ubuntu-24.04")
        self.assertEqual(selected_elixir[0]["elixir"], "1.18.0")

        for event, base in (("pull_request", "release/1.2"), ("push", "")):
            with self.subTest(event=event, base=base):
                selected = selector.select_matrix(event, base)["include"]
                self.assertEqual(
                    [row for row in selected if row["task"] == "elixir-native"],
                    elixir_rows,
                    "release qualification runs every native Elixir cell",
                )
        self.assertEqual(native["env"]["LITERATE_AI_ELIXIR_MIX_QUALIFICATION"], "1")
        self.assertEqual(native["env"]["LITERATE_AI_ELIXIR_BUILD_SYSTEMS"], "1")
        self.assertEqual(
            native["env"]["LITAI_HEX_EBIN"],
            "${{ github.workspace }}/_build/elixir/hex/hex-2.5.1/ebin",
        )
        self.assertIn("test_elixir_mix_qualification.py", native["run"])
        self.assertIn("test_elixir_mix_graph_qualification.py", native["run"])
        self.assertIn("test_elixir_mix_shared_qualification.py", native["run"])
        self.assertIn("-o addopts=''", native["run"])
        gate = next(step for step in steps if step.get("shell") == "python")
        probe = compile(gate["run"], "ci.yml:elixir-native-gate", "exec")
        for counts, accepted in (
            ((18, 0, 0, 0), True),
            ((18, 0, 0, 1), False),
            ((17, 0, 0, 0), False),
            ((18, 1, 0, 0), False),
            ((18, 0, 1, 0), False),
        ):
            root = ET.Element("testsuites")
            suite = ET.SubElement(
                root,
                "testsuite",
                dict(
                    zip(
                        ("tests", "failures", "errors", "skipped"),
                        map(str, counts),
                        strict=True,
                    )
                ),
            )
            for index in range(counts[0]):
                ET.SubElement(suite, "testcase", {"name": f"fixture-{index}"})
            with (
                self.subTest(counts=counts),
                mock.patch.object(ET, "parse", return_value=ET.ElementTree(root)),
                mock.patch("builtins.print"),
            ):
                if accepted:
                    exec(probe, {})
                else:
                    with self.assertRaises(SystemExit):
                        exec(probe, {})
