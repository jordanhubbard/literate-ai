"""Real temp Git/filesystem journal controls; planner classification is modeled.

No test here qualifies the public planner or native Windows migration.
"""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import project_layout_continuation as writer
from literate_ai.adapters import project_layout_migration as owner
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.project_layout_planning import _capture, _git_state
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore, ProjectError


class _ModeledTransition:
    """Models original typed-owner callbacks, not real Component qualification."""

    def __init__(self, root, endpoint, payload, records=None, originals=None):
        self.root = root
        self.source_root = endpoint.source_root
        self.destination_root = endpoint.destination_root
        self.manifest_identity = endpoint.manifest_identity
        self.imported_source = endpoint.imported_source
        self.target_names = endpoint.target_names
        names = {".component.operation.write.lock", ".component.lock.write.lock"}
        names.update(
            ".component.resolution-audit." + name + ".json.write.lock"
            for name in self.target_names
        )
        self.coordination_paths = tuple(
            self.source_root + "/" + name for name in sorted(names)
        )
        self.records = records if records is not None else {}
        self.original_contents = originals if originals is not None else {}
        self.original_catalog = object()
        self.original_lock_store = object()
        self.original_audit_store = None
        self.payload = payload
        self.source_calls = self.destination_calls = 0
        self.fail_destination = False
        self.source_effect = None
        self.destination_effect = None

    def require_current(self):
        self.source_calls += 1
        if (self.root / self.source_root / "component.md").read_bytes() != self.payload:
            raise ValueError("modeled source changed")
        for path, data in self.original_contents.items():
            if (self.root / path).read_bytes() != data:
                raise ValueError("modeled producer changed")
        if self.source_effect is not None:
            self.source_effect(self)

    def verify_destination_current(self, expected_snapshot):
        self.destination_calls += 1
        if self.fail_destination:
            raise ValueError("modeled destination renewal_required")
        if expected_snapshot.root != self.root:
            raise ValueError("modeled destination snapshot mismatch")
        if (
            self.root / self.destination_root / "component.md"
        ).read_bytes() != self.payload:
            raise ValueError("modeled destination payload mismatch")
        if self.destination_effect is not None:
            self.destination_effect(self, expected_snapshot)


@unittest.skipUnless(os.name == "posix", "owned POSIX controls; Windows unqualified")
class CatalogContinuationWriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.source = "skills/example/SKILL.md"
        self.target = "litai/" + self.source
        for name, payload in {
            self.source: b"# Imported immutable Skill\n",
            "litai/literate.project.json": b"original configuration\n",
            "litai/.literate/imports.json": b"original imports\n",
            "litai/.literate/v1-retained-history/original": b"retained v1 evidence\n",
            "application.py": b"print('application')\n",
        }.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        self.git("init", "-q", "-b", "main")
        self.git("add", ".")
        self.git(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=fixture@example.test",
            "commit",
            "-qm",
            "original contained fixture",
        )
        self.index = self.git("ls-files", "--stage", "-z")
        self.head = self.git("rev-parse", "HEAD")
        self.history = self.root / "litai/.literate/v1-retained-history/original"
        self.history_node = self.history.stat().st_ino
        self.selection = self.select()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], timeout=15)

    def select(self):
        observations, contents = _capture(self.root)
        identity = owner._identity
        manifest = "litai/literate.project.json"
        plan = {
            "schema": writer._PLAN,
            "mode": "read-only",
            "project_id": "literate-ai",
            "inventory_identity": canonical_identity(
                {"modeled": "writer selection"}
            ).uri,
            "framework_git_state": _git_state(self.root / "litai"),
            "held": [],
            "blockers": [],
            "blocked_references": [],
            "renewal": ["Component resolution"],
            "writes": False,
            "full_containment": False,
            "transaction_mode": "contained-catalog-continuation",
            "framework_directory": "litai",
            "project": str(self.root),
            "root_node": list(directory_node(self.root)),
            "framework_node": list(directory_node(self.root / "litai")),
            "git_state": _git_state(self.root),
            "applicable": True,
            "placements": {
                self.source: {
                    "destination": self.target,
                    "from": identity(contents[self.source]),
                    "to": identity(contents[self.source]),
                    "mode": observations[self.source]["mode"],
                }
            },
            "resident_edits": {
                manifest: {
                    "from": identity(contents[manifest]),
                    "to": identity(b"rewritten configuration\n"),
                    "mode": observations[manifest]["mode"],
                    "owner": "modeled project configuration",
                }
            },
            "reference_edits": {},
        }
        plan["plan_identity"] = canonical_identity(plan).uri
        context = SimpleNamespace(
            root=self.root,
            directory_binding=(
                tuple(directory_node(self.root)),
                tuple(directory_node(self.root / "litai")),
            ),
        )
        return SimpleNamespace(
            public_plan=plan,
            context=context,
            original_contents=contents,
            rewritten_contents={manifest: b"rewritten configuration\n"},
            observations=observations,
            component_endpoints=(),
        )

    def apply(self):
        with ProjectConfigurationStore.layout_lock(self.root):
            return writer.apply_catalog_continuation(
                self.selection, self.selection.public_plan["plan_identity"]
            )

    def recover(self):
        with ProjectConfigurationStore.layout_lock(self.root):
            return writer.recover_catalog_continuation(
                self.root, self.selection.public_plan["plan_identity"]
            )

    def assert_custody(self):
        self.assertEqual(self.git("ls-files", "--stage", "-z"), self.index)
        self.assertEqual(self.git("rev-parse", "HEAD"), self.head)
        self.assertEqual(self.history.read_bytes(), b"retained v1 evidence\n")
        self.assertEqual(self.history.stat().st_ino, self.history_node)
        self.assertEqual(
            (self.root / "application.py").read_bytes(), b"print('application')\n"
        )

    def test_per_entry_apply_and_rollback_preserve_existing_litai_and_history(self):
        original_node = (self.root / self.source).stat().st_ino
        framework_node = (self.root / "litai").stat().st_ino
        result = self.apply()
        journal = Path(result["journal"])
        self.assertFalse((self.root / self.source).exists())
        self.assertEqual(
            (self.root / self.target).read_bytes(), b"# Imported immutable Skill\n"
        )
        self.assertTrue((journal / "before/00000").exists())
        self.assertEqual((self.root / "litai").stat().st_ino, framework_node)
        self.recover()
        self.assertEqual((self.root / self.source).stat().st_ino, original_node)
        self.assertFalse((self.root / self.target).exists())
        self.assertEqual(
            (self.root / "litai/literate.project.json").read_bytes(),
            b"original configuration\n",
        )
        self.assert_custody()
        self.recover()  # exact already-restored state is repeatable

    def test_backed_up_interruption_retains_exact_original_and_recovers(self):
        original = writer._move

        def move(source, target, entry, *, original: bool, namespace):
            if not original:
                raise OSError("injected process-boundary failure after backup")
            return delegate(
                source, target, entry, original=original, namespace=namespace
            )

        delegate = original
        with (
            patch.object(writer, "_move", move),
            self.assertRaisesRegex(ValueError, "retained catalog journal"),
        ):
            self.apply()
        journal, intent = writer._load(
            self.root, self.selection.public_plan["plan_identity"]
        )
        self.assertEqual(
            writer._entry_state(
                self.root, journal, self.source, intent["entries"][self.source]
            ),
            "backed-up",
        )
        self.recover()
        self.assertTrue((self.root / self.source).is_file())
        self.assert_custody()

    def test_same_bytes_replaced_source_inode_is_not_adopted(self):
        path = self.root / self.source
        copy = path.with_suffix(".replacement")
        copy.write_bytes(path.read_bytes())
        copy.chmod(path.stat().st_mode & 0o7777)
        copy.replace(path)
        with self.assertRaisesRegex(ValueError, "original observation"):
            self.apply()
        self.assertFalse((self.root / self.target).exists())
        self.assert_custody()

    def test_replaced_source_parent_with_original_file_inode_refuses(self):
        parent = (self.root / self.source).parent
        moved = parent.with_name("held-original-parent")
        parent.rename(moved)
        parent.mkdir()
        (moved / "SKILL.md").rename(parent / "SKILL.md")
        with self.assertRaisesRegex(ValueError, "parent changed"):
            self.apply()
        self.assertFalse((self.root / self.target).exists())
        self.assert_custody()

    def test_destination_collision_preserves_foreign_file(self):
        path = self.root / self.target
        path.parent.mkdir(parents=True)
        path.write_bytes(b"foreign destination\n")
        with self.assertRaisesRegex(ValueError, "appeared"):
            self.apply()
        self.assertEqual(path.read_bytes(), b"foreign destination\n")
        self.assertTrue((self.root / self.source).exists())

    def test_recovery_preserves_foreign_content_and_all_original_backups(self):
        result = self.apply()
        journal = Path(result["journal"])
        before = {p.name: p.read_bytes() for p in (journal / "before").iterdir()}
        (self.root / self.target).write_bytes(b"foreign post-publication edit\n")
        with self.assertRaisesRegex(ValueError, "unresolved state"):
            self.recover()
        self.assertEqual(
            {p.name: p.read_bytes() for p in (journal / "before").iterdir()}, before
        )
        self.assertEqual(
            (self.root / self.target).read_bytes(), b"foreign post-publication edit\n"
        )
        self.assert_custody()

    def test_rehashed_journal_slot_path_escape_refuses_before_effect(self):
        result = self.apply()
        path = Path(result["journal"]) / "intent.json"
        value = json.loads(path.read_bytes())
        value["entries"][self.source]["slot"] = "../outside"
        value.pop("identity")
        value["identity"] = canonical_identity(value).uri
        path.write_bytes(canonical_json_bytes(value) + b"\n")
        with self.assertRaisesRegex(ValueError, "journal entry differs"):
            self.recover()
        self.assertTrue((self.root / self.target).exists())
        self.assert_custody()

    def test_unknown_journal_member_refuses_without_deletion(self):
        result = self.apply()
        path = Path(result["journal"]) / "foreign"
        path.write_bytes(b"foreign journal content\n")
        with self.assertRaisesRegex(ValueError, "unknown content"):
            self.recover()
        self.assertEqual(path.read_bytes(), b"foreign journal content\n")
        self.assertTrue((self.root / self.target).exists())

    def test_nested_git_created_after_apply_blocks_recovery(self):
        self.apply()
        marker = self.root / "litai/skills/.git"
        marker.mkdir()
        with self.assertRaises(ValueError) as caught:
            self.recover()
        self.assertEqual(caught.exception.code, "project.layout.git_boundary")
        self.assertTrue(marker.is_dir())
        self.assertTrue((self.root / self.target).exists())
        self.assert_custody()

    def test_component_without_original_target_inventory_refuses_before_journal(self):
        self.selection.component_endpoints = (SimpleNamespace(target_names=None),)
        with self.assertRaisesRegex(ValueError, "original Component target"):
            self.apply()
        self.assertFalse(
            writer.journal_path(
                self.root, self.selection.public_plan["plan_identity"]
            ).exists()
        )
        self.assertTrue((self.root / self.source).is_file())

    def test_matrix_override_refuses_without_touching_override_target(self):
        with patch.dict(
            os.environ, {"LITAI_MATRIX_CELL_ROOT": "/unselected/never-access"}
        ):
            with self.assertRaisesRegex(ValueError, "matrix storage owner"):
                self.apply()
        self.assertFalse(
            writer.journal_path(
                self.root, self.selection.public_plan["plan_identity"]
            ).exists()
        )

    def test_new_destination_directory_foreign_child_refuses_before_restore(self):
        self.apply()
        selected = self.root / self.target
        foreign = selected.parent / "foreign.txt"
        foreign.write_bytes(b"unrelated child\n")
        before = selected.read_bytes()
        with self.assertRaisesRegex(ValueError, "unrelated content"):
            self.recover()
        self.assertEqual(selected.read_bytes(), before)
        self.assertFalse((self.root / self.source).exists())
        self.assertEqual(foreign.read_bytes(), b"unrelated child\n")

    def test_rehashed_directory_slot_mode_mismatch_refuses(self):
        result = self.apply()
        path = Path(result["journal"]) / "intent.json"
        value = json.loads(path.read_bytes())
        row = next(iter(value["new_directories"].values()))
        row["mode"] ^= 0o100
        value.pop("identity")
        value["identity"] = canonical_identity(value).uri
        path.write_bytes(canonical_json_bytes(value) + b"\n")
        with self.assertRaisesRegex(ValueError, "directory mode differs"):
            self.recover()
        self.assertTrue((self.root / self.target).exists())

    @contextmanager
    def component_fixture(self, names=(), *, history=False):
        self.source = "components/example/component.md"
        self.target = "litai/" + self.source
        path = self.root / self.source
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = b"modeled selected Component manifest\n"
        path.write_bytes(payload)
        # Use genuine parsable configuration for the actual closing snapshot
        # reader; Component catalog selection remains an explicitly modeled seam.
        config = json.loads(
            (Path(__file__).resolve().parents[2] / "literate.project.json").read_bytes()
        )
        config["framework_directory"] = "litai"
        config["component_roots"] = ["components", "litai/components"]
        (self.root / "litai/literate.project.json").write_bytes(
            canonical_json_bytes(config) + b"\n"
        )
        originals, records = {}, {}
        if history:
            producer = "components/example/component.lock.json"
            data = b"modeled historical producer bytes\n"
            (self.root / producer).write_bytes(data)
            originals[producer] = data
            records[producer] = {
                "identity": owner._identity(data),
                "mode": (self.root / producer).stat().st_mode & 0o7777,
                "kind": "ModeledProducer",
                "typed_identity": canonical_identity({"modeled": "producer"}).uri,
            }
        self.selection = self.select()
        self.selection.public_plan["resident_edits"] = {}
        self.selection.rewritten_contents = {}
        if history:
            for producer, record in records.items():
                self.selection.public_plan["placements"][producer] = {
                    "destination": "litai/" + producer,
                    "from": record["identity"],
                    "to": record["identity"],
                    "mode": record["mode"],
                }
        plan = self.selection.public_plan
        plan.pop("plan_identity")
        plan["plan_identity"] = canonical_identity(plan).uri
        endpoint = SimpleNamespace(
            source_root="components/example",
            destination_root="litai/components/example",
            manifest_identity=owner._identity(payload),
            target_names=names,
            imported_source=object(),
        )
        transition = _ModeledTransition(
            self.root, endpoint, payload, records, originals
        )
        endpoint.producer_transition = transition
        self.selection.component_endpoints = (endpoint,)
        original_source = _ModeledTransition.require_current
        original_destination = _ModeledTransition.verify_destination_current

        def modeled_admission(owner):
            # Explicit writer-protocol seam: actual origin/producer proof is
            # exercised by Component admission tests and the public journey.
            if (
                owner is not transition
                or writer._raw_method(owner, "require_current") is not original_source
                or writer._raw_method(owner, "verify_destination_current")
                is not original_destination
            ):
                raise ValueError("modeled transition/guard changed")

        with (
            patch.object(writer, "_transition_type", return_value=_ModeledTransition),
            patch.object(writer, "_admit_transition", modeled_admission),
        ):
            yield transition

    def test_original_component_operation_write_and_audit_fences_are_respected(self):
        from literate_ai._cache_lock import CacheLockError, exclusive_cache_lock

        with self.component_fixture(("host",)):
            path = self.root / self.source
            for name in (
                ".component.operation.write.lock",
                ".component.lock.write.lock",
                ".component.resolution-audit.host.json.write.lock",
            ):
                with (
                    self.subTest(lock=name),
                    exclusive_cache_lock(path.parent / name, timeout_seconds=0),
                ):
                    with self.assertRaises(CacheLockError):
                        self.apply()
                self.assertFalse(
                    writer.journal_path(
                        self.root, self.selection.public_plan["plan_identity"]
                    ).exists()
                )
                self.assertTrue(path.is_file())

    def test_interruption_before_intent_never_creates_live_destination_directories(
        self,
    ):
        delegate = owner._write

        def write(path, content, mode=0o600):
            if path.name == "intent.json":
                raise OSError("intent fsync boundary failed")
            return delegate(path, content, mode)

        with (
            patch.object(owner, "_write", write),
            self.assertRaises(ProjectError) as caught,
        ):
            self.apply()
        self.assertEqual(caught.exception.code, "project.manifest_lock")
        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertIn("intent fsync", str(caught.exception.__cause__))
        self.assertTrue((self.root / self.source).is_file())
        self.assertFalse((self.root / "litai/skills").exists())
        self.assertFalse(
            writer.journal_path(
                self.root, self.selection.public_plan["plan_identity"]
            ).exists()
        )
        self.assertTrue(
            list((self.root / "litai/.literate").glob(".catalog-placement-*"))
        )
        self.assert_custody()

    def test_interrupted_rollback_reopens_exact_backed_up_state(self):
        self.apply()
        delegate = writer._move

        def move(source, target, entry, *, original, namespace):
            if original and target == self.root / self.source:
                raise OSError("restore boundary interrupted")
            return delegate(
                source, target, entry, original=original, namespace=namespace
            )

        with (
            patch.object(writer, "_move", move),
            self.assertRaises(ProjectError) as caught,
        ):
            self.recover()
        self.assertEqual(caught.exception.code, "project.manifest_lock")
        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertIn("restore boundary", str(caught.exception.__cause__))
        journal, intent = writer._load(
            self.root, self.selection.public_plan["plan_identity"]
        )
        self.assertEqual(
            writer._entry_state(
                self.root, journal, self.source, intent["entries"][self.source]
            ),
            "backed-up",
        )
        self.recover()
        self.assertTrue((self.root / self.source).is_file())
        self.assert_custody()

    def test_same_bytes_replaced_published_inode_refuses_recovery(self):
        self.apply()
        target = self.root / self.target
        replacement = target.with_suffix(".replacement")
        replacement.write_bytes(target.read_bytes())
        replacement.chmod(target.stat().st_mode & 0o7777)
        replacement.replace(target)
        with self.assertRaisesRegex(ValueError, "unresolved state"):
            self.recover()
        self.assertFalse((self.root / self.source).exists())
        self.assertTrue(target.is_file())
        self.assert_custody()

    def test_proved_empty_targets_retain_exact_coordination_scaffolding_on_rollback(
        self,
    ):
        with self.component_fixture(()) as transition:
            result = self.apply()
            self.assertGreaterEqual(transition.source_calls, 3)
            self.assertEqual(transition.destination_calls, 1)
            journal, intent = writer._load(
                self.root, self.selection.public_plan["plan_identity"]
            )
            before = {
                path: (self.root / path).stat().st_ino
                for path in (*intent["coordination"], *intent["source_coordination"])
            }
            self.assertTrue(before)
            restored = self.recover()
            self.assertTrue(restored["retained_scaffolding"])
            self.assertEqual(
                set(restored["retained_scaffolding"]),
                {"litai/components", "litai/components/example"},
            )
            self.assertFalse((self.root / self.target).exists())
            self.assertTrue((self.root / self.source).is_file())
            self.assertEqual(
                {path: (self.root / path).stat().st_ino for path in before}, before
            )
            repeated = self.recover()
            self.assertEqual(
                repeated["retained_scaffolding"], restored["retained_scaffolding"]
            )
            self.assertEqual(
                {path: (self.root / path).stat().st_ino for path in before}, before
            )
            self.assertTrue((Path(result["journal"]) / "rolled-back").is_file())
            self.assert_custody()

    def test_coordination_is_staged_before_intent_without_live_destination(self):
        with self.component_fixture(()) as transition:
            delegate = owner._write

            def write(path, content, mode=0o600):
                if path.name == "intent.json":
                    self.assertEqual(
                        len(list((path.parent / "coordination").iterdir())), 2
                    )
                    self.assertFalse((self.root / "litai/components").exists())
                    self.assertEqual(transition.destination_calls, 0)
                    raise OSError("coordination intent boundary")
                return delegate(path, content, mode)

            with (
                patch.object(owner, "_write", write),
                self.assertRaises(ProjectError) as caught,
            ):
                self.apply()
            self.assertIsInstance(caught.exception.__cause__, OSError)
            self.assertTrue((self.root / self.source).is_file())
            self.assertFalse((self.root / "litai/components").exists())

    def test_partial_coordination_publication_never_mints_missing_inode_on_recovery(
        self,
    ):
        with self.component_fixture(()):
            delegate = owner._move_file
            moved = []

            def move(source, target, item, **kwargs):
                if source.parent.name == "coordination":
                    if moved:
                        raise OSError("second coordination publication interrupted")
                    moved.append(target)
                return delegate(source, target, item, **kwargs)

            with (
                patch.object(owner, "_move_file", move),
                self.assertRaisesRegex(ValueError, "retained catalog journal"),
            ):
                self.apply()
            journal, intent = writer._load(
                self.root, self.selection.public_plan["plan_identity"]
            )
            states = writer._coordination_states(self.root, journal, intent)
            self.assertEqual(sorted(states.values()), ["published", "staged"])
            missing = next(path for path, state in states.items() if state == "staged")
            node = moved[0].stat().st_ino
            restored = self.recover()
            self.assertFalse((self.root / missing).exists())
            self.assertEqual(moved[0].stat().st_ino, node)
            self.assertTrue(restored["retained_scaffolding"])
            self.assertTrue((self.root / self.source).is_file())
            self.recover()
            self.assertFalse((self.root / missing).exists())

    def test_replaced_destination_coordination_refuses_before_payload_restoration(self):
        with self.component_fixture(()):
            self.apply()
            _, intent = writer._load(
                self.root, self.selection.public_plan["plan_identity"]
            )
            path = self.root / next(iter(intent["coordination"]))
            replacement = path.with_suffix(".new")
            replacement.write_bytes(path.read_bytes())
            replacement.chmod(path.stat().st_mode & 0o7777)
            replacement.replace(path)
            with self.assertRaisesRegex(ValueError, "coordination"):
                self.recover()
            self.assertTrue((self.root / self.target).is_file())
            self.assertFalse((self.root / self.source).exists())

    def test_foreign_scaffold_child_refuses_before_payload_restoration(self):
        with self.component_fixture(()):
            self.apply()
            foreign = (self.root / self.target).parent / "foreign.txt"
            foreign.write_bytes(b"foreign coordination scaffold child\n")
            with self.assertRaisesRegex(ValueError, "unrelated content"):
                self.recover()
            self.assertTrue((self.root / self.target).is_file())
            self.assertFalse((self.root / self.source).exists())
            self.assertEqual(
                foreign.read_bytes(), b"foreign coordination scaffold child\n"
            )

    def test_transition_pointer_substitution_during_callback_refuses_before_intent(
        self,
    ):
        with self.component_fixture(()) as transition:
            endpoint = self.selection.component_endpoints[0]

            def changed(instance):
                endpoint.producer_transition = object()

            transition.source_effect = changed
            with self.assertRaisesRegex(ValueError, "transition/guard changed"):
                self.apply()
            self.assertEqual(transition.destination_calls, 0)
            self.assertFalse(
                writer.journal_path(
                    self.root, self.selection.public_plan["plan_identity"]
                ).exists()
            )
            self.assertTrue((self.root / self.source).is_file())

    def test_destination_renewal_refusal_does_not_create_completed_marker(self):
        with self.component_fixture(()) as transition:
            transition.fail_destination = True
            with self.assertRaisesRegex(ValueError, "renewal_required"):
                self.apply()
            journal, _ = writer._load(
                self.root, self.selection.public_plan["plan_identity"]
            )
            self.assertFalse((journal / "completed").exists())
            self.assertTrue((self.root / self.target).is_file())
            self.recover()
            self.assertTrue((self.root / self.source).is_file())

    def test_historical_producer_bytes_remain_in_journal_after_rollback(self):
        with self.component_fixture((), history=True):
            self.apply()
            journal, intent = writer._load(
                self.root, self.selection.public_plan["plan_identity"]
            )
            self.assertEqual(len(intent["history"]), 1)
            row = next(iter(intent["history"].values()))
            historical = journal / "history" / row["slot"]
            payload, inode = historical.read_bytes(), historical.stat().st_ino
            self.recover()
            self.assertEqual(historical.read_bytes(), payload)
            self.assertEqual(historical.stat().st_ino, inode)
            self.assertEqual(
                (self.root / "components/example/component.lock.json").read_bytes(),
                payload,
            )
            self.assertTrue(historical.is_file())

    def test_late_git_boundary_preserves_original_error_code_and_recovery_hint(self):
        delegate = writer._move
        introduced = False

        def move(source, target, entry, *, original, namespace):
            nonlocal introduced
            result = delegate(
                source, target, entry, original=original, namespace=namespace
            )
            if original and not introduced:
                introduced = True
                (self.root / "litai/skills/.git").mkdir()
            return result

        with (
            patch.object(writer, "_move", move),
            self.assertRaises(ValueError) as caught,
        ):
            self.apply()
        self.assertEqual(caught.exception.code, "project.layout.git_boundary")
        self.assertIn("retained catalog journal", str(caught.exception))
        self.assertIn(
            self.selection.public_plan["plan_identity"], str(caught.exception)
        )
        self.assertTrue((self.root / "litai/skills/.git").is_dir())

    def test_raw_destination_descriptor_substitution_refuses_without_binding_it(self):
        with self.component_fixture(()) as transition:
            called = []
            original_destination = _ModeledTransition.verify_destination_current

            class ForeignDescriptor:
                def __get__(self, instance, cls):
                    called.append("foreign descriptor")
                    raise AssertionError("foreign descriptor must never bind")

            def changed(instance):
                _ModeledTransition.verify_destination_current = ForeignDescriptor()

            transition.source_effect = changed
            with patch.object(
                _ModeledTransition, "verify_destination_current", original_destination
            ):
                with self.assertRaisesRegex(ValueError, "transition/guard changed"):
                    self.apply()
            self.assertEqual(called, [])
            self.assertTrue((self.root / self.source).is_file())

    def test_source_coordination_inode_swap_under_lock_refuses_before_intent(self):
        with self.component_fixture(()) as transition:

            def changed(instance):
                if instance.source_calls == 2:
                    path = (
                        self.root
                        / instance.source_root
                        / ".component.operation.write.lock"
                    )
                    replacement = path.with_suffix(".new")
                    replacement.write_bytes(path.read_bytes())
                    replacement.chmod(path.stat().st_mode & 0o7777)
                    replacement.replace(path)

            transition.source_effect = changed
            with self.assertRaisesRegex(ValueError, "coordination descriptor changed"):
                self.apply()
            self.assertFalse(
                writer.journal_path(
                    self.root, self.selection.public_plan["plan_identity"]
                ).exists()
            )
            self.assertTrue((self.root / self.source).is_file())

    def test_actual_writer_result_uses_strict_separate_envelope_and_unchanged_plan(
        self,
    ):
        original_plan = canonical_json_bytes(self.selection.public_plan)
        result = self.apply()
        self.assertEqual(
            result["schema"], "literate-ai/project-layout-catalog-continuation-result@1"
        )
        self.assertEqual(
            set(result),
            {
                "schema",
                "operation",
                "plan",
                "writes",
                "full_containment",
                "qualification",
                "journal",
                "retained_scaffolding",
                "applied",
            },
        )
        self.assertEqual(canonical_json_bytes(result["plan"]), original_plan)
        self.assertEqual(
            canonical_json_bytes(self.selection.public_plan), original_plan
        )
        self.assertIs(result["qualification"], False)
        restored = self.recover()
        self.assertEqual(restored["operation"], "recover")
        self.assertEqual(canonical_json_bytes(restored["plan"]), original_plan)
        self.assertEqual(restored["retained_scaffolding"], [])

    def test_destination_closing_callback_payload_change_refuses_before_completion(
        self,
    ):
        with self.component_fixture(()) as transition:

            def changed(instance, snapshot):
                (self.root / self.target).write_bytes(b"foreign callback replacement\n")

            transition.destination_effect = changed
            with self.assertRaises(ValueError):
                self.apply()
            journal = writer.journal_path(
                self.root, self.selection.public_plan["plan_identity"]
            )
            self.assertFalse((journal / "completed").exists())
            self.assertEqual(
                (self.root / self.target).read_bytes(),
                b"foreign callback replacement\n",
            )
            self.assertTrue((journal / "before/00000").is_file())

    def test_unadmitted_type_matched_owner_never_enters_source_callback(self):
        original_admission = writer._admit_transition
        with self.component_fixture(()) as transition:
            with patch.object(writer, "_admit_transition", original_admission):
                with self.assertRaisesRegex(ValueError, "original factory admission"):
                    self.apply()
            self.assertEqual(transition.source_calls, 0)
            self.assertEqual(transition.destination_calls, 0)
            self.assertTrue((self.root / self.source).is_file())

    def test_changed_prebind_function_refuses_without_foreign_invocation(self):
        with self.component_fixture(()) as transition:
            calls = []

            def foreign(instance):
                calls.append(instance)

            with patch.object(_ModeledTransition, "require_current", foreign):
                with self.assertRaisesRegex(ValueError, "transition/guard changed"):
                    self.apply()
            self.assertEqual(calls, [])
            self.assertEqual(transition.destination_calls, 0)
            self.assertFalse(
                writer.journal_path(
                    self.root, self.selection.public_plan["plan_identity"]
                ).exists()
            )
