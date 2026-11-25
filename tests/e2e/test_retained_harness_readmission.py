"""A reviewed readmission can replace an unqualified conversion harness."""

from __future__ import annotations

import json
import os
import shutil
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import retained_harness_readmission as readmission
from literate_ai.adapters import retained_harness_remote as retained_remote
from literate_ai.adapters.harness_inventory import (
    HARNESS_BASELINE_SCHEMA,
    HARNESS_PARITY_SCHEMA,
)
from literate_ai.adapters.retained_harness_receipts import (
    retained_harness_receipt_policy,
)
from literate_ai.adapters.retained_harness_remote import (
    RetainedHarnessRemoteError,
    RetainedHarnessRemoteResult,
)
from literate_ai.contracts import canonical_identity
from literate_ai.projects import load_project
from tests.support.fixtures_test_retained_harness_receipts import (
    _adapter,
    _invoke,
    _legacy_project,
    _selectors,
)
from tests.support.fixtures_test_retained_harness_remote import _worker


class RetainedHarnessReadmissionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize the converted project once; each test copies it.
        temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(temporary.cleanup)
        cls.template = Path(temporary.name).resolve() / "project"
        _legacy_project(cls.template)
        _adapter().initialize(
            cls.template,
            flavor_selectors=_selectors(cls.template),
            source_intelligence_provider="none",
            convert=True,
            run_baseline=True,
        )

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "project"
        shutil.copytree(self.template, self.root, symlinks=True)
        self.source = self.root / "components/legacy-project-wrapper/implementation"

    def invoke(self, *arguments: str):
        return _invoke(
            "project",
            "retained-harness",
            "readmit",
            "--project",
            str(self.root),
            *arguments,
        )

    def test_readmission_preserves_authored_shim_authority(self) -> None:
        interface_bytes = b"# Owned public interface\n"
        component = self.root / "components/legacy-project-wrapper/component.md"
        owned = (
            "### Requirement: Preserve the owner's interface\n\n"
            "Keep café and 雪 intact.\n\n"
            "#### Scenario: Readmit the harness\n\n"
            "- **WHEN** the harness is readmitted\n"
            "- **THEN** owned authority remains intact\n"
        )
        content = component.read_text(encoding="utf-8").replace(
            "# Legacy Project Pipeline Wrapper\n",
            "# Legacy Project Pipeline Wrapper\n\n" + owned,
        )
        content = content.replace(
            "display_name: Legacy Project Pipeline Wrapper",
            "display_name: Owned pipeline",
        )
        content = content.replace(
            "    version: 1.0.0\nrequires: []",
            "    version: 1.0.0\n    interface:\n"
            "      uri: interfaces/owned.md\n"
            f"      pin: {readmission._identity(interface_bytes)}\n"
            "requires: []",
        )
        component.write_text(content, encoding="utf-8")
        interface = component.parent / "interfaces/owned.md"
        interface.parent.mkdir()
        interface.write_bytes(interface_bytes)
        for relative in (
            "flavors/legacy-project-shim/flavor.md",
            "flavors/legacy-project-shim/openspec/spec.md",
            "skills/specification-to-source/legacy-project-shim/SKILL.md",
            "workflows/legacy-adoption/workflow.md",
        ):
            path = self.root / relative
            path.write_bytes(
                path.read_bytes() + b"\nOwned authoring must remain intact.\n"
            )
        routing = self.root / "routing/legacy-adoption.json"
        data = json.loads(routing.read_bytes())
        data["version"] = "1.0.1"
        routing.write_text(json.dumps(data, indent=4) + "\n", encoding="utf-8")
        # A genuinely changed retained scope needs readmission, independently of
        # the authored additions that this operation must preserve.
        (self.source / "added.py").write_text(
            "VALUE = 'new source scope'\n", encoding="utf-8"
        )
        code, result = self.invoke()
        self.assertEqual(code, 0, result)
        plan = result["result"]
        before = {
            name: (self.root / name).read_bytes()
            for name in plan["new_shim_identities"]
        }
        for name, raw in before.items():
            self.assertEqual(
                plan["new_shim_identities"][name], readmission._identity(raw)
            )
        self.assertTrue(
            all(c["change"] == "preserved" for c in plan["shim_authority_changes"])
        )
        code, result = self.invoke(
            "--apply",
            "--acknowledge",
            "--expected-plan-identity",
            plan["plan_identity"],
        )
        self.assertEqual(code, 0, result)
        self.assertTrue(result["result"]["applied"])
        self.assertEqual(
            {name: (self.root / name).read_bytes() for name in before}, before
        )

        self.assertEqual(interface.read_bytes(), interface_bytes)

    def test_referenced_authority_drift_refuses_without_overwriting_owner(self) -> None:
        component = self.root / "components/legacy-project-wrapper/component.md"
        component.write_text(
            component.read_text(encoding="utf-8").replace(
                "    version: 1.0.0\nrequires: []",
                "    version: 1.0.0\n    interface:\n"
                "      uri: interfaces/owned.md\nrequires: []",
            ),
            encoding="utf-8",
        )
        interface = component.parent / "interfaces/owned.md"
        interface.parent.mkdir()
        interface.write_bytes(b"# Owned public interface\n")
        (self.source / "added.py").write_bytes(b"VALUE = 1\n")
        original_baseline = readmission._baseline_report
        from literate_ai.adapters import component_lock_commands

        original_lock = component_lock_commands._component_locks_from_args
        for when in ("after-plan", "during-baseline", "during-lock"):
            with self.subTest(when=when):
                interface.write_bytes(b"# Owned public interface\n")
                code, result = self.invoke()
                self.assertEqual(code, 0, result)
                plan = result["result"]
                before = {
                    p: (self.root / p).read_bytes() for p in plan["old_documents"]
                }

                def drift_baseline(*args, when=when, **kwargs):
                    value = original_baseline(*args, **kwargs)
                    if when == "during-baseline":
                        interface.write_bytes(b"# Owner changed the interface\n")
                    return value

                def drift_lock(*args, when=when, **kwargs):
                    value = original_lock(*args, **kwargs)
                    if when == "during-lock":
                        interface.write_bytes(b"# Owner changed the interface\n")
                    return value

                if when == "after-plan":
                    interface.write_bytes(b"# Owner changed the interface\n")
                with (
                    mock.patch.object(readmission, "_baseline_report", drift_baseline),
                    mock.patch.object(
                        component_lock_commands,
                        "_component_locks_from_args",
                        drift_lock,
                    ),
                ):
                    code, result = self.invoke(
                        "--apply",
                        "--acknowledge",
                        "--expected-plan-identity",
                        plan["plan_identity"],
                    )
                self.assertEqual(code, 2, result)
                self.assertIn(
                    result["error"]["code"],
                    {
                        "retained_harness.plan_stale",
                        "inputs.closure_changed",
                    },
                )
                self.assertEqual(
                    interface.read_bytes(), b"# Owner changed the interface\n"
                )
                self.assertEqual(
                    {p: (self.root / p).read_bytes() for p in before}, before
                )
                self.assertFalse(list((self.root / readmission.HISTORY).glob("*.json")))

    def test_late_authored_metadata_edits_refuse_and_preserve_owner(self) -> None:
        from literate_ai.adapters import component_lock_commands
        from literate_ai.adapters.project_initialization import (
            FilesystemProjectInitializationAdapter,
        )

        original_lock = component_lock_commands._component_locks_from_args
        original_review = readmission.record_project_authority_review
        original_record = (
            FilesystemProjectInitializationAdapter._record_authority_review
        )
        (self.source / "added.py").write_bytes(b"VALUE = 1\n")
        for selected, when in (
            ("component", "lock"),
            ("flavor", "lock"),
            ("review", "lock"),
            ("component", "review"),
            ("component", "before-review"),
            ("review", "before-review"),
            ("review", "inside-review"),
            ("onboarding", "lock"),
            ("onboarding", "review"),
        ):
            with self.subTest(selected=selected, when=when):
                code, result = self.invoke()
                self.assertEqual(code, 0, result)
                plan = result["result"]
                before = {
                    p: (self.root / p).read_bytes() for p in plan["old_documents"]
                }
                before["SKILL.md"] = (self.root / "SKILL.md").read_bytes()
                relative = {
                    "component": "components/legacy-project-wrapper/component.md",
                    "flavor": "flavors/legacy-project-shim/flavor.md",
                    "review": plan["authority_review"],
                    "onboarding": "SKILL.md",
                }[selected]
                target = self.root / relative
                changed = before[relative] + b"\nConcurrent owner edit.\n"

                def lock(*args, when=when, target=target, changed=changed, **kwargs):
                    value = original_lock(*args, **kwargs)
                    if when == "lock":
                        target.write_bytes(changed)
                    return value

                def review(*args, when=when, target=target, changed=changed, **kwargs):
                    if when == "before-review":
                        target.write_bytes(changed)
                    value = original_review(*args, **kwargs)
                    if when == "review":
                        target.write_bytes(changed)
                    return value

                def record(
                    instance, *args, when=when, target=target, changed=changed, **kwargs
                ):
                    if when == "inside-review":
                        target.write_bytes(changed)
                    return original_record(instance, *args, **kwargs)

                with (
                    mock.patch.object(
                        component_lock_commands, "_component_locks_from_args", lock
                    ),
                    mock.patch.object(
                        readmission, "record_project_authority_review", review
                    ),
                    mock.patch.object(
                        FilesystemProjectInitializationAdapter,
                        "_record_authority_review",
                        record,
                    ),
                ):
                    code, result = self.invoke(
                        "--apply",
                        "--acknowledge",
                        "--expected-plan-identity",
                        plan["plan_identity"],
                    )
                self.assertEqual(code, 2, result)
                self.assertEqual(
                    result["error"]["code"], "retained_harness.metadata_changed"
                )
                self.assertEqual(target.read_bytes(), changed)
                self.assertEqual(
                    {p: (self.root / p).read_bytes() for p in before if p != relative},
                    {p: raw for p, raw in before.items() if p != relative},
                )
                self.assertFalse(list((self.root / readmission.HISTORY).glob("*.json")))
                target.write_bytes(before[relative])

    def test_late_authority_deletion_rolls_back_other_writes(self) -> None:
        from literate_ai.adapters import component_lock_commands

        original_lock = component_lock_commands._component_locks_from_args
        (self.source / "added.py").write_bytes(b"VALUE = 1\n")
        code, result = self.invoke()
        self.assertEqual(code, 0, result)
        plan = result["result"]
        relative = "components/legacy-project-wrapper/component.md"
        before = {p: (self.root / p).read_bytes() for p in plan["old_documents"]}
        target = self.root / relative

        def remove(*args, **kwargs):
            value = original_lock(*args, **kwargs)
            target.unlink()
            return value

        with mock.patch.object(
            component_lock_commands, "_component_locks_from_args", remove
        ):
            code, result = self.invoke(
                "--apply",
                "--acknowledge",
                "--expected-plan-identity",
                plan["plan_identity"],
            )
        self.assertEqual(code, 2, result)
        self.assertEqual(result["error"]["code"], "retained_harness.metadata_changed")
        self.assertFalse(target.exists())
        self.assertEqual(
            {p: (self.root / p).read_bytes() for p in before if p != relative},
            {p: raw for p, raw in before.items() if p != relative},
        )
        self.assertFalse(list((self.root / readmission.HISTORY).glob("*.json")))

    def test_late_directory_replacement_preserves_owner_and_rollback(self) -> None:
        from literate_ai.adapters import component_lock_commands

        original_lock = component_lock_commands._component_locks_from_args
        (self.source / "added.py").write_bytes(b"VALUE = 1\n")
        code, result = self.invoke()
        self.assertEqual(code, 0, result)
        plan = result["result"]
        relative = "components/legacy-project-wrapper/component.md"
        before = {p: (self.root / p).read_bytes() for p in plan["old_documents"]}
        target = self.root / relative

        def remove(*args, **kwargs):
            value = original_lock(*args, **kwargs)
            target.unlink()
            target.mkdir()
            return value

        with mock.patch.object(
            component_lock_commands, "_component_locks_from_args", remove
        ):
            code, result = self.invoke(
                "--apply",
                "--acknowledge",
                "--expected-plan-identity",
                plan["plan_identity"],
            )
        self.assertEqual(code, 2, result)
        self.assertEqual(result["error"]["code"], "retained_harness.metadata_changed")
        self.assertTrue(target.is_dir())
        self.assertEqual(
            {p: (self.root / p).read_bytes() for p in before if p != relative},
            {p: raw for p, raw in before.items() if p != relative},
        )
        self.assertFalse(list((self.root / readmission.HISTORY).glob("*.json")))

    @unittest.skipIf(os.name == "nt", "requires POSIX symlink replacement")
    def test_late_link_replacement_preserves_owner_and_rollback(self) -> None:
        from literate_ai.adapters import component_lock_commands

        original_lock = component_lock_commands._component_locks_from_args
        (self.source / "added.py").write_bytes(b"VALUE = 1\n")
        code, result = self.invoke()
        self.assertEqual(code, 0, result)
        plan = result["result"]
        relative = "components/legacy-project-wrapper/component.md"
        before = {p: (self.root / p).read_bytes() for p in plan["old_documents"]}
        target = self.root / relative
        owner = self.base / "owner.md"
        owner.write_bytes(b"Owner file unchanged.\n")

        def remove(*args, **kwargs):
            value = original_lock(*args, **kwargs)
            target.unlink()
            target.symlink_to(owner)
            return value

        with mock.patch.object(
            component_lock_commands, "_component_locks_from_args", remove
        ):
            code, result = self.invoke(
                "--apply",
                "--acknowledge",
                "--expected-plan-identity",
                plan["plan_identity"],
            )
        self.assertEqual(code, 2, result)
        self.assertEqual(result["error"]["code"], "retained_harness.metadata_changed")
        self.assertTrue(target.is_symlink())
        self.assertEqual(owner.read_bytes(), b"Owner file unchanged.\n")
        self.assertEqual(
            {p: (self.root / p).read_bytes() for p in before if p != relative},
            {p: raw for p, raw in before.items() if p != relative},
        )
        self.assertFalse(list((self.root / readmission.HISTORY).glob("*.json")))

    def test_changed_phase_facts_apply_without_replacing_authored_authority(
        self,
    ) -> None:
        component = self.root / "components/legacy-project-wrapper/component.md"
        component.write_bytes(
            component.read_bytes()
            + (
                b"\n### Requirement: Keep owner intent\n\n"
                b"Owner intent SHALL remain active.\n\n"
                b"#### Scenario: Correct the retained phases\n\n"
                b"- **WHEN** the retained pipeline changes\n"
                b"- **THEN** only generated phase facts change\n"
            )
        )
        makefile = self.source / "Makefile"
        makefile.write_text(
            makefile.read_text(encoding="utf-8").split("package:", 1)[0],
            encoding="utf-8",
        )
        code, result = self.invoke()
        self.assertEqual(code, 0, result)
        plan = result["result"]
        before = {p: (self.root / p).read_bytes() for p in plan["new_shim_identities"]}
        change = next(
            c
            for c in plan["shim_authority_changes"]
            if c["change"] == "baseline-summary"
        )
        expected = before[change["path"]].replace(
            change["before_summary"].encode(), change["after_summary"].encode(), 1
        )
        self.assertIn(b"missing stages are\n`package`", expected)
        code, result = self.invoke(
            "--apply",
            "--acknowledge",
            "--expected-plan-identity",
            plan["plan_identity"],
        )
        self.assertEqual(code, 0, result)
        self.assertTrue(result["result"]["applied"])
        self.assertEqual(component.read_bytes(), expected)
        self.assertEqual(
            {p: (self.root / p).read_bytes() for p in before if p != change["path"]},
            {p: raw for p, raw in before.items() if p != change["path"]},
        )

    def test_changed_baseline_summary_preserves_surrounding_owned_bytes(self) -> None:
        component = self.root / "components/legacy-project-wrapper/component.md"
        before = component.read_bytes() + b"\n### Requirement: Keep owned behavior\n"
        component.write_bytes(before)
        inventory = json.loads((self.root / readmission.INVENTORY).read_bytes())
        inventory["commands"].pop("package", None)
        baseline = {"phases": [{"phase": "build"}, {"phase": "test"}]}
        shim, changes = readmission._readmitted_shim_authority(
            self.root, inventory, baseline
        )
        change = next(c for c in changes if c["change"] == "baseline-summary")
        self.assertIn("missing stages are\n`package`", change["after_summary"])
        rebuilt = shim["components/legacy-project-wrapper/component.md"].replace(
            change["after_summary"], change["before_summary"], 1
        )
        self.assertEqual(rebuilt.encode("utf-8"), before)

    def test_unrecognized_or_ambiguous_summary_refuses_before_qualification(
        self,
    ) -> None:
        component = self.root / "components/legacy-project-wrapper/component.md"
        original = component.read_bytes()
        summary = readmission._BASELINE_SUMMARY.search(original.decode("utf-8")).group()
        for candidate in (
            original.replace(b"This Component exposes", b"Owned wording replaces", 1),
            original + b"\n" + summary.encode("utf-8"),
            original.replace(summary.encode("utf-8"), b"Owned summary.")
            + b"\n```markdown\n"
            + summary.encode("utf-8")
            + b"\n```\n",
            original.replace(summary.encode("utf-8"), b"Owned summary.")
            + b"\nQuoted inline: "
            + summary.encode("utf-8")
            + b"\n",
        ):
            with self.subTest(candidate=candidate[-30:]):
                component.write_bytes(candidate)
                with (
                    mock.patch.object(readmission, "_baseline_report") as baseline,
                    mock.patch.object(readmission, "_parity_report") as parity,
                ):
                    code, result = self.invoke()
                self.assertEqual(code, 2, result)
                self.assertEqual(
                    result["error"]["code"], "retained_harness.shim_ownership_ambiguous"
                )
                baseline.assert_not_called()
                parity.assert_not_called()
                self.assertEqual(component.read_bytes(), candidate)

    def test_crlf_and_unicode_authority_is_byte_preserved(self) -> None:
        component = self.root / "components/legacy-project-wrapper/component.md"
        raw = (
            (component.read_text(encoding="utf-8") + "\nKeep café and 雪.\n")
            .replace("\n", "\r\n")
            .encode("utf-8")
        )
        component.write_bytes(raw)
        inventory = json.loads((self.root / readmission.INVENTORY).read_bytes())
        baseline = json.loads((self.root / readmission.BASELINE).read_bytes())
        shim, _ = readmission._readmitted_shim_authority(self.root, inventory, baseline)
        self.assertEqual(
            shim["components/legacy-project-wrapper/component.md"].encode("utf-8"), raw
        )

    def make_unqualified_false_bazel_state(self) -> None:
        (self.source / "BUILD.bazel").write_text("# packaging stub\n", encoding="utf-8")
        inventory = {
            "schema": "urn:literate-ai:schema:v1:harness-inventory",
            "findings": [
                {
                    "detector_id": "build-system.bazel",
                    "path": "BUILD.bazel",
                    "detail": "Bazel workspace",
                }
            ],
            "commands": {
                "build": {
                    "id": "build",
                    "command": "bazel build //...",
                    "cwd": ".",
                    "evidence": "BUILD.bazel",
                    "cost": "local-cheap",
                },
                "test": {
                    "id": "test",
                    "command": "bazel test //...",
                    "cwd": ".",
                    "evidence": "BUILD.bazel",
                    "cost": "local-cheap",
                },
            },
            "stages": [
                {
                    "id": "build",
                    "command": "bazel build //...",
                    "cwd": ".",
                    "evidence": "BUILD.bazel",
                    "cost": "local-cheap",
                },
                {
                    "id": "test",
                    "command": "bazel test //...",
                    "cwd": ".",
                    "evidence": "BUILD.bazel",
                    "cost": "local-cheap",
                },
            ],
            "ci": {
                "configured": False,
                "class": "not-configured",
                "state": "not-configured",
            },
            "allow_unready": True,
        }
        (self.root / readmission.INVENTORY).write_text(
            json.dumps(inventory, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        (self.root / readmission.BASELINE).write_text(
            json.dumps(
                {
                    "schema": HARNESS_BASELINE_SCHEMA,
                    "state": "skipped",
                    "phases": [],
                    "phase_count": 0,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        (self.root / readmission.PARITY).write_text(
            json.dumps(
                {
                    "schema": HARNESS_PARITY_SCHEMA,
                    "state": "skipped",
                    "phases": [],
                    "phase_count": 0,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        (self.root / "litai.harness.mk").write_text(
            "build:\n\tbazel build //...\ntest:\n\tbazel test //...\n",
            encoding="utf-8",
        )

    def admit_repo_man_test_stage(self) -> dict[str, object]:
        self.make_unqualified_false_bazel_state()
        driver = self.source / "repo.sh"
        driver.write_text("#!/bin/sh\nprintf 'Ran 1 test\\nOK\\n'\n", encoding="utf-8")
        driver.chmod(0o755)
        inventory_path = self.root / readmission.INVENTORY
        inventory = json.loads(inventory_path.read_bytes())
        retained = {
            "id": "test",
            "command": "./repo.sh test -c release",
            "cwd": ".",
            "evidence": "repo.sh",
            "cost": "host-heavy",
        }
        inventory["commands"]["test"] = retained
        inventory["stages"] = [
            retained if stage["id"] == "test" else stage
            for stage in inventory["stages"]
        ]
        inventory_path.write_text(
            json.dumps(inventory, sort_keys=True, separators=(",", ":")) + "\n",
            encoding="utf-8",
        )
        return retained

    def test_readmission_replaces_false_bazel_and_requalifies_locally(self) -> None:
        self.make_unqualified_false_bazel_state()
        before_authority = (
            self.root / readmission.CONVERSION_AUTHORITY_FILE
        ).read_bytes()

        code, result = self.invoke()

        self.assertEqual(code, 0, result)
        plan = result["result"]
        self.assertTrue(plan["changes_required"])
        self.assertTrue(plan["commands_changed"])
        self.assertNotIn(
            "build-system.bazel",
            {item["detector_id"] for item in plan["new_inventory"]["findings"]},
        )
        code, result = self.invoke(
            "--apply",
            "--acknowledge",
            "--expected-plan-identity",
            plan["plan_identity"],
        )
        self.assertEqual(code, 0, result)
        self.assertTrue(result["result"]["applied"])
        prior = self.root / result["result"]["prior_evidence_history"]
        self.assertEqual(
            (prior / readmission.BASELINE).read_text(encoding="utf-8"),
            json.dumps(
                {
                    "schema": HARNESS_BASELINE_SCHEMA,
                    "state": "skipped",
                    "phases": [],
                    "phase_count": 0,
                },
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n",
        )
        inventory = json.loads((self.root / readmission.INVENTORY).read_bytes())
        self.assertEqual(
            json.loads((self.root / readmission.BASELINE).read_bytes())["state"],
            "passed",
        )
        self.assertEqual(
            json.loads((self.root / readmission.PARITY).read_bytes())["state"],
            "passed",
        )
        self.assertEqual(
            load_project(self.root).definition.test_receipt_policy,
            retained_harness_receipt_policy(inventory),
        )
        self.assertIn(
            "+flavor://legacy-adoption/build-legacy-shim",
            load_project(self.root).definition.default_flavor_selectors,
        )
        self.assertNotIn(
            "+flavor://literate-ai/build-bazel",
            load_project(self.root).definition.default_flavor_selectors,
        )
        lock = json.loads(
            (
                self.root / "components/legacy-project-wrapper/component.lock.json"
            ).read_bytes()
        )
        selected = lock["nodes"][0]["target_flavor_selection"]["slots"][0]["selected"]
        self.assertEqual(selected[0]["value"], "legacy-shim")
        self.assertEqual(
            (self.root / readmission.CONVERSION_AUTHORITY_FILE).read_bytes(),
            before_authority,
        )

    def test_source_change_during_qualification_rolls_back_publication(self) -> None:
        self.make_unqualified_false_bazel_state()
        code, planned = self.invoke()
        self.assertEqual(code, 0, planned)
        plan = planned["result"]
        inventory_before = (self.root / readmission.INVENTORY).read_bytes()
        original = readmission._parity_report

        def mutate_after_parity(*args, **kwargs):
            result = original(*args, **kwargs)
            source = self.source / "app.py"
            source.write_text(
                source.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            return result

        with mock.patch.object(
            readmission, "_parity_report", side_effect=mutate_after_parity
        ):
            code, result = self.invoke(
                "--apply",
                "--acknowledge",
                "--expected-plan-identity",
                plan["plan_identity"],
            )

        self.assertEqual(code, 2, result)
        self.assertEqual(result["error"]["code"], "retained_harness.source_changed")
        self.assertEqual(
            (self.root / readmission.INVENTORY).read_bytes(), inventory_before
        )
        history = self.root / readmission.HISTORY
        self.assertFalse(history.exists() and any(history.rglob("*")))

    def test_remote_readmission_executes_direct_and_generated_wrapper(self) -> None:
        retained = self.admit_repo_man_test_stage()
        worker = _worker()
        catalog_identity = canonical_identity({"catalog": "fixture"})

        class Executor:
            def __init__(self) -> None:
                self.commands: list[list[str]] = []

            def execute(self, selected_worker, **kwargs):
                inventory = kwargs["inventory"]
                self.commands.append(
                    [stage["command"] for stage in inventory["stages"]]
                )
                phases = []
                for stage in inventory["stages"]:
                    collection = (
                        {
                            "state": "nonempty",
                            "total": 1,
                            "passed": 1,
                            "failed": 0,
                            "skipped": 0,
                            "known_failed": 0,
                        }
                        if stage["id"].split(".", 1)[0] == "test"
                        else {
                            "state": "not-applicable",
                            "total": None,
                            "passed": None,
                            "failed": None,
                            "skipped": None,
                            "known_failed": None,
                        }
                    )
                    phases.append(
                        {
                            "phase": stage["id"],
                            "command": stage["command"],
                            "exit_code": 0,
                            "timed_out": False,
                            "tree": {"identity": "sha256:" + "1" * 64},
                            "source_tree": {"identity": "sha256:" + "2" * 64},
                            "test_collection": collection,
                        }
                    )
                return RetainedHarnessRemoteResult(
                    canonical_identity({"request": len(self.commands)}),
                    kwargs["lifecycle_request_identity"],
                    selected_worker.identity,
                    canonical_identity(inventory),
                    kwargs["source_identity"],
                    {
                        "operating_system": "linux",
                        "operating_system_release": "fixture",
                        "machine": "x86_64",
                        "python_implementation": "cpython",
                        "python_version": "3.12",
                    },
                    tuple(phases),
                )

        executor = Executor()
        plan = readmission.plan_retained_harness_readmission(
            self.root,
            execution_worker=worker,
            worker_catalog_identity=catalog_identity,
            retained_stage_ids=("test",),
        )

        self.assertIn(retained, plan["new_inventory"]["stages"])

        result = readmission.apply_retained_harness_readmission(
            self.root,
            expected_plan_identity=plan["plan_identity"],
            acknowledge=True,
            timeout_seconds=1800,
            execution_worker=worker,
            worker_catalog_identity=catalog_identity,
            retained_stage_ids=("test",),
            remote_executor=executor,
        )

        self.assertTrue(result["applied"])
        self.assertEqual(len(executor.commands), 2)
        self.assertFalse(
            any("litai.harness.mk" in item for item in executor.commands[0])
        )
        self.assertTrue(
            all("litai.harness.mk" in item for item in executor.commands[1])
        )

    def test_wrapper_projection_preserves_admitted_generated_name_source_paths(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source_root = Path(directory).resolve()
            header = source_root / "legacy/include/build/PreHeaders.h"
            header.parent.mkdir(parents=True)
            header.write_text("#pragma once\n", encoding="utf-8")
            generated = source_root / "legacy/build/generated.o"
            generated.parent.mkdir(parents=True)
            generated.write_bytes(b"generated")
            (source_root / "litai.harness.mk").write_text(
                "build:\n\ttrue\n",
                encoding="utf-8",
            )
            inventory = {
                "source_scope": {
                    "schema": "literate-ai/retained-source-scope@1",
                    "policy": "git-visible@1",
                    "paths": ["include/build/PreHeaders.h"],
                    "paths_identity": canonical_identity(
                        ["include/build/PreHeaders.h"]
                    ).uri,
                    "excluded_roots": [],
                    "excluded": [],
                },
                "stages": [
                    {
                        "id": "build",
                        "command": "./build.sh",
                        "cwd": ".",
                        "evidence": "build.sh",
                        "cost": "host-heavy",
                    }
                ],
            }

            parity = readmission._parity_inventory(inventory, source_root)

            paths = parity["source_scope"]["paths"]
            self.assertIn("legacy/include/build/PreHeaders.h", paths)
            self.assertIn("litai.harness.mk", paths)
            self.assertNotIn("legacy/build/generated.o", paths)
            archive = source_root / "source.tar.gz"
            retained_remote._source_archive(source_root, parity, archive)
            with tarfile.open(archive, "r:gz") as stream:
                names = stream.getnames()
            self.assertIn("literate-ai/legacy/include/build/PreHeaders.h", names)
            self.assertIn("literate-ai/litai.harness.mk", names)
            self.assertNotIn("literate-ai/legacy/build/generated.o", names)

    def test_remote_readmission_retries_only_parity_source_capture(self) -> None:
        self.admit_repo_man_test_stage()
        worker = _worker()
        catalog_identity = canonical_identity({"catalog": "fixture"})

        class Executor:
            def __init__(self) -> None:
                self.attempts = 0
                self.parity_failures = 0

            def execute(self, selected_worker, **kwargs):
                self.attempts += 1
                inventory = kwargs["inventory"]
                parity = all(
                    "litai.harness.mk" in stage["command"]
                    for stage in inventory["stages"]
                )
                if parity and self.parity_failures == 0:
                    self.parity_failures += 1
                    raise RetainedHarnessRemoteError(
                        "retained_receipt.remote_source_capture_failed",
                        "source projection could not be captured",
                    )
                phases = tuple(
                    {
                        "phase": stage["id"],
                        "command": stage["command"],
                        "exit_code": 0,
                        "timed_out": False,
                        "tree": {"identity": "sha256:" + "1" * 64},
                        "source_tree": {"identity": "sha256:" + "2" * 64},
                        "test_collection": (
                            {
                                "state": "nonempty",
                                "total": 1,
                                "passed": 1,
                                "failed": 0,
                                "skipped": 0,
                                "known_failed": 0,
                            }
                            if stage["id"].split(".", 1)[0] == "test"
                            else {
                                "state": "not-applicable",
                                "total": None,
                                "passed": None,
                                "failed": None,
                                "skipped": None,
                                "known_failed": None,
                            }
                        ),
                    }
                    for stage in inventory["stages"]
                )
                return RetainedHarnessRemoteResult(
                    canonical_identity({"request": self.attempts}),
                    kwargs["lifecycle_request_identity"],
                    selected_worker.identity,
                    canonical_identity(inventory),
                    kwargs["source_identity"],
                    {
                        "operating_system": "linux",
                        "operating_system_release": "fixture",
                        "machine": "x86_64",
                        "python_implementation": "cpython",
                        "python_version": "3.12",
                    },
                    phases,
                )

        executor = Executor()
        plan = readmission.plan_retained_harness_readmission(
            self.root,
            execution_worker=worker,
            worker_catalog_identity=catalog_identity,
            retained_stage_ids=("test",),
        )
        result = readmission.apply_retained_harness_readmission(
            self.root,
            expected_plan_identity=plan["plan_identity"],
            acknowledge=True,
            timeout_seconds=1800,
            execution_worker=worker,
            worker_catalog_identity=catalog_identity,
            retained_stage_ids=("test",),
            remote_executor=executor,
        )

        self.assertTrue(result["applied"])
        self.assertEqual(executor.attempts, 3)
        self.assertEqual(
            json.loads((self.root / readmission.PARITY).read_bytes())[
                "source_capture_attempts"
            ],
            2,
        )

    def test_remote_readmission_bounds_capture_retry_and_preserves_other_errors(
        self,
    ) -> None:
        self.admit_repo_man_test_stage()
        worker = _worker()
        catalog_identity = canonical_identity({"catalog": "fixture"})

        for code, expected_attempts in (
            ("retained_receipt.remote_source_capture_failed", 3),
            ("retained_receipt.remote_source_changed", 2),
            ("retained_receipt.remote_archive_oversized", 2),
            ("retained_receipt.remote_source_scope_invalid", 2),
            ("retained_receipt.remote_transport_failed", 2),
        ):
            with self.subTest(code=code):

                class Executor:
                    def __init__(self, failure_code: str) -> None:
                        self.attempts = 0
                        self.failure_code = failure_code

                    def execute(self, selected_worker, **kwargs):
                        self.attempts += 1
                        if self.attempts >= 2:
                            raise RetainedHarnessRemoteError(
                                self.failure_code, "fixture failure"
                            )
                        inventory = kwargs["inventory"]
                        phases = tuple(
                            {
                                "phase": stage["id"],
                                "command": stage["command"],
                                "exit_code": 0,
                                "timed_out": False,
                                "tree": {"identity": "sha256:" + "1" * 64},
                                "source_tree": {"identity": "sha256:" + "2" * 64},
                                "test_collection": (
                                    {
                                        "state": "nonempty",
                                        "total": 1,
                                        "passed": 1,
                                        "failed": 0,
                                        "skipped": 0,
                                        "known_failed": 0,
                                    }
                                    if stage["id"].split(".", 1)[0] == "test"
                                    else {
                                        "state": "not-applicable",
                                        "total": None,
                                        "passed": None,
                                        "failed": None,
                                        "skipped": None,
                                        "known_failed": None,
                                    }
                                ),
                            }
                            for stage in inventory["stages"]
                        )
                        return RetainedHarnessRemoteResult(
                            canonical_identity({"request": self.attempts}),
                            kwargs["lifecycle_request_identity"],
                            selected_worker.identity,
                            canonical_identity(inventory),
                            kwargs["source_identity"],
                            {
                                "operating_system": "linux",
                                "operating_system_release": "fixture",
                                "machine": "x86_64",
                                "python_implementation": "cpython",
                                "python_version": "3.12",
                            },
                            phases,
                        )

                executor = Executor(code)
                plan = readmission.plan_retained_harness_readmission(
                    self.root,
                    execution_worker=worker,
                    worker_catalog_identity=catalog_identity,
                    retained_stage_ids=("test",),
                )
                with self.assertRaises(RetainedHarnessRemoteError) as raised:
                    readmission.apply_retained_harness_readmission(
                        self.root,
                        expected_plan_identity=plan["plan_identity"],
                        acknowledge=True,
                        timeout_seconds=1800,
                        execution_worker=worker,
                        worker_catalog_identity=catalog_identity,
                        retained_stage_ids=("test",),
                        remote_executor=executor,
                    )
                self.assertEqual(raised.exception.code, code)
                self.assertEqual(executor.attempts, expected_attempts)
