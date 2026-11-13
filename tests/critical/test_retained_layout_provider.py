"""Actual older Git rosters used by genuine initialized source transactions."""

from __future__ import annotations

import ast
import os
import shutil
import subprocess
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_ownership as fixtures
import tests.support.fixtures_test_retained_harness_receipts as initializer_fixtures
from literate_ai.adapters import project_initialization as initialization
from literate_ai.adapters import retained_layout_ownership as ownership
from literate_ai.adapters import retained_layout_provider as provider
from literate_ai.adapters import retained_layout_transaction as transaction
from literate_ai.adapters.builders.python import BuildError
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.projects import load_project


@unittest.skipUnless(os.name == "posix", "actual Git and POSIX source transaction")
class HistoricalInitializerTests(unittest.TestCase):
    plan = fixtures.RetainedLayoutOwnershipTests.plan
    pool = fixtures.RetainedLayoutOwnershipTests.pool
    phase = fixtures.RetainedLayoutOwnershipTests.phase
    git = fixtures.RetainedLayoutOwnershipTests.git
    init_git = fixtures.RetainedLayoutOwnershipTests.init_git
    inspecting = fixtures.RetainedLayoutOwnershipTests.inspecting
    forged_baseline_entry = fixtures.RetainedLayoutOwnershipTests.forged_baseline_entry

    @classmethod
    def command(cls, *arguments, input=None):
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.upper().startswith("GIT_")
        }
        environment.update(GIT_CONFIG_GLOBAL=os.devnull, GIT_CONFIG_NOSYSTEM="1")
        return subprocess.check_output(
            ["git", "-c", "core.hooksPath=" + os.devnull, *arguments],
            cwd=cls.checkout,
            env=environment,
            timeout=15,
            input=input,
        )

    @classmethod
    def commit(cls):
        cls.command("add", ".")
        cls.command(
            "-c",
            "user.name=Fixture",
            "-c",
            "user.email=test@example.test",
            "commit",
            "-qm",
            "provider fixture",
        )
        return cls.command("rev-parse", "HEAD").decode().strip()

    @classmethod
    def setUpClass(cls):
        if shutil.which("git") is None:
            raise unittest.SkipTest("actual Git unavailable")
        temporary = tempfile.TemporaryDirectory(prefix="original-provider-")
        cls.addClassCleanup(temporary.cleanup)
        cls.checkout = Path(temporary.name).resolve()
        package = cls.checkout / "src/literate_ai"
        (package / "adapters").mkdir(parents=True)
        cls.initializer = package / "adapters/project_initialization.py"
        current = Path(initialization.__file__).read_text()
        line = (
            '    "scripts/_bootstrap_processes.py": '
            '"scripts/_bootstrap_processes.py",\n'
        )
        if current.count(line) != 1:
            raise AssertionError(
                "fixture requires the actual bootstrap template endpoint"
            )
        cls.initializer.write_text(current.replace(line, ""))
        shutil.copyfile(
            provider.harness_inventory.__file__,
            package / "adapters/harness_inventory.py",
        )
        resources = package / "project_template"
        shutil.copytree(
            Path(initialization.__file__).parents[1] / "project_template", resources
        )
        (resources / "scripts/_bootstrap_processes.py").unlink()
        cls.command("init", "-q", "--initial-branch=main", "--template=")
        cls.command("remote", "add", "origin", cls.checkout.as_uri())
        cls.origin = replace(
            initialization.discover_installed_initialization_origin(),
            repository_url=cls.checkout.as_uri(),
            git_revision=cls.commit(),
        )
        mapping = dict(initialization._TEMPLATE_FILES)
        mapping.pop("scripts/_bootstrap_processes.py")
        # Every emitted template has the same bytes and selected producer as the
        # verified old object tree. No generated origin/baseline is rewritten.
        with mock.patch.object(
            initializer_fixtures, "_origin", return_value=cls.origin
        ):
            with mock.patch.object(initialization, "_TEMPLATE_FILES", mapping):
                fixtures.fixtures.RetainedLayoutFinalizationTests.setUpClass.__func__(
                    cls
                )
        # HEAD is newer than the recorded initializer and now contains the new
        # endpoint. Positive observations must use the original commit instead.
        cls.initializer.write_text(current)
        shutil.copyfile(
            Path(initialization.__file__).parents[1]
            / "project_template/scripts/_bootstrap_processes.py",
            resources / "scripts/_bootstrap_processes.py",
        )
        cls.new_revision = cls.commit()

    def setUp(self):
        fixtures.RetainedLayoutOwnershipTests.setUp(self)

    def observe(self, phase):
        return phase.complete_partition(
            budget=RetainedCargoInputBudget(1024, 2048, 4 * 1024**2, 32 * 1024**2),
            maximum_metadata_bytes=1024 * 1024**2,
            provider_checkout=self.checkout,
        )

    def test_original_roster_uses_recorded_commit_and_keeps_new_endpoint_unclaimed(
        self,
    ):
        source = self.project / "scripts/_bootstrap_processes.py"
        source.write_bytes(b"operator original input\n")
        with self.inspecting() as phase:
            with self.observe(phase) as owner:
                self.assertEqual(
                    dict(owner.roles)["scripts/bootstrap_litai.py"], "framework"
                )
                self.assertEqual(
                    dict(owner.roles)["scripts/_bootstrap_processes.py"], "unclaimed"
                )
                self.assertNotEqual(self.origin.git_revision, self.new_revision)
                roster = owner._provider
                with self.assertRaises(AttributeError):
                    roster.templates = ("unclaimed.py",)
                with self.assertRaises(AttributeError):
                    roster.identity = None
        with self.assertRaisesRegex(ValueError, "observation ended"):
            roster.require_current()
        self.assertEqual(source.read_bytes(), b"operator original input\n")

    def test_baseline_only_forgery_cannot_claim_later_template_endpoint(self):
        source = self.forged_baseline_entry("scripts/_bootstrap_processes.py")
        with self.inspecting() as phase:
            with self.assertRaisesRegex(ValueError, "outside actual initializer roles"):
                with self.observe(phase):
                    self.fail(
                        "new provider's endpoint was attributed to old initializer"
                    )
        self.assertEqual(source.read_bytes(), b"original user source\n")

    def test_original_roster_is_consumed_by_actual_move_and_finalization(self):
        plan = self.plan()
        with self.pool(plan) as (pool, journal):
            with self.phase(plan, pool) as phase:
                with self.observe(phase) as owner:
                    phase.move_source()
                    with self.assertRaisesRegex(ValueError, "spent"):
                        owner.require_current()
                phase.publish_metadata(self.metadata)
                phase.finalize_controls(self.retired)
            self.assertTrue(
                any(
                    event["kind"] == "source-partition-observed"
                    for event in journal.events
                )
            )
        self.assertTrue((self.destination / "app.py").is_file())
        self.assertFalse(self.source.exists())

    def test_changed_provider_configuration_revokes_before_source_effect(self):
        path = self.checkout / ".git/config"
        original = path.read_bytes()
        try:
            with self.inspecting() as phase:
                with self.assertRaisesRegex(ValueError, "configuration changed"):
                    with self.observe(phase) as owner:
                        path.write_bytes(original + b"\n# concurrent operator input\n")
                        owner.require_current()
            self.assertTrue(
                path.read_bytes().endswith(b"# concurrent operator input\n")
            )
            self.assertTrue(self.source.exists())
            self.assertFalse(self.destination.exists())
        finally:
            path.write_bytes(original)

    def test_unrecognized_global_mutation_is_not_a_supported_producer(self):
        raw = Path(initialization.__file__).read_bytes()
        modified = raw + b'\n_TEMPLATE_FILES["unclaimed.py"] = "SKILL.md"\n'
        self.assertNotEqual(
            provider._shape(raw, initializer=True, maximum_nodes=200000)[0],
            provider._shape(modified, initializer=True, maximum_nodes=200000)[0],
        )

    def test_wrong_checkout_cannot_supply_original_role_proof(self):
        with self.inspecting() as phase:
            with self.assertRaisesRegex(ValueError, "recorded repository"):
                with phase.complete_partition(
                    budget=self.namespace_budget,
                    maximum_metadata_bytes=1024 * 1024**2,
                    provider_checkout=Path(__file__).resolve().parents[2],
                ):
                    self.fail("unrelated actual checkout was accepted")
        self.assertTrue(self.source.exists())

    def test_corrupt_blob_bytes_are_rejected_against_original_object_identity(self):
        read = provider._Objects.run
        changed = False

        def corrupt(objects, *arguments, **kwargs):
            nonlocal changed
            value = read(objects, *arguments, **kwargs)
            if arguments[:2] == ("cat-file", "blob") and not changed:
                changed = True
                return value[:-1] + bytes([value[-1] ^ 1])
            return value

        with mock.patch.object(provider._Objects, "run", corrupt):
            with self.assertRaisesRegex(
                ValueError, "bytes disagree with their identity"
            ):
                with provider.original_initializer_roster(
                    self.origin,
                    load_project(self.project).definition,
                    checkout=self.checkout,
                    budget=self.namespace_budget,
                    metadata_limit=256 * 1024**2,
                ):
                    self.fail("corrupt original object bytes supplied ownership")
        self.assertTrue(changed)
        self.assertTrue(self.source.exists())

    def test_provider_configuration_closes_after_final_project_inventory(self):
        path = self.checkout / ".git/config"
        original = path.read_bytes()
        inventory = transaction._inventory
        changed = False

        def change_after_inventory(root, *args, **kwargs):
            nonlocal changed
            result = inventory(root, *args, **kwargs)
            if root == self.project and not changed:
                changed = True
                path.write_bytes(original + b"\n# late provider input\n")
            return result

        try:
            with self.assertRaisesRegex(ValueError, "configuration changed"):
                with self.inspecting() as phase:
                    with self.observe(phase):
                        with mock.patch.object(
                            transaction, "_inventory", change_after_inventory
                        ):
                            phase.move_source()
            self.assertTrue(changed)
            self.assertTrue(self.source.exists())
            self.assertFalse(self.destination.exists())
            self.assertTrue(path.read_bytes().endswith(b"# late provider input\n"))
        finally:
            path.write_bytes(original)

    def test_small_provider_budget_refuses_before_blob_observation(self):
        read = provider._Objects.read
        payloads = []

        def observe(objects, kind, oid):
            payloads.append(kind)
            return read(objects, kind, oid)

        with mock.patch.object(provider._Objects, "read", observe):
            with self.assertRaises((ValueError, BuildError)):
                with provider.original_initializer_roster(
                    self.origin,
                    load_project(self.project).definition,
                    checkout=self.checkout,
                    budget=RetainedCargoInputBudget(1, 2, 4, 4),
                    metadata_limit=64 * 1024**2,
                ):
                    self.fail("tiny original-provider budget admitted a roster")
        self.assertNotIn("blob", payloads)
        self.assertTrue(self.source.exists())

    def test_shared_empty_subtrees_consume_path_occurrence_budget(self):
        def object_id(kind, content):
            return (
                self.command("hash-object", "-w", "-t", kind, "--stdin", input=content)
                .decode()
                .strip()
            )

        child = object_id("tree", b"")
        for _ in range(6):
            child = object_id(
                "tree",
                b"".join(
                    b"40000 " + name + b"\0" + bytes.fromhex(child)
                    for name in (b"a", b"b", b"c")
                ),
            )
        for name in reversed((b"src", b"literate_ai", b"project_template", b"flavors")):
            child = object_id("tree", b"40000 " + name + b"\0" + bytes.fromhex(child))
        commit = object_id(
            "commit",
            b"tree "
            + child.encode()
            + b"\nauthor Fixture <test@example.test> 0 +0000\n"
            + b"committer Fixture <test@example.test> 0 +0000\n"
            + b"\nbounded shared trees\n",
        )
        objects = provider._Objects(
            self.checkout,
            replace(self.origin, git_revision=commit),
            RetainedCargoInputBudget(64, 100, 1024**2, 16 * 1024**2),
            64 * 1024**2,
        )
        with self.assertRaisesRegex(ValueError, "path occurrences"):
            objects.flavor_files()
        self.assertLess(objects.reads, 20)

    def test_literal_mapping_paths_consume_entry_budget_before_roster_creation(self):
        tree = ast.parse(Path(initialization.__file__).read_bytes())
        mapping = next(
            node
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "_TEMPLATE_FILES"
                for target in node.targets
            )
        )
        mapping.value = ast.Dict(
            keys=[ast.Constant(f"scripts/added-{index}.py") for index in range(100)],
            values=[ast.Constant("SKILL.md") for _ in range(100)],
        )
        objects = provider._Objects(
            self.checkout,
            self.origin,
            RetainedCargoInputBudget(64, 100, 1024**2, 16 * 1024**2),
            64 * 1024**2,
        )
        with self.assertRaisesRegex(ValueError, "path occurrences"):
            provider._shape(
                ast.unparse(ast.fix_missing_locations(tree)),
                initializer=True,
                maximum_nodes=200000,
                charge_path=objects.entry,
            )

    def combined_budget_refusal(self, *, files):
        sizes = [
            path.stat().st_size for path in self.project.rglob("*") if path.is_file()
        ]
        total = 32 * 1024**2 if files else sum(sizes) + 65536
        budget = RetainedCargoInputBudget(
            250 if files else 1024,
            4096,
            min(4 * 1024**2, total),
            total,
        )
        borrowed = []
        factory = ownership.original_initializer_roster

        def observe(*args, **kwargs):
            borrowed.append(kwargs["budget"])
            return factory(*args, **kwargs)

        with self.inspecting() as phase:
            with mock.patch.object(ownership, "original_initializer_roster", observe):
                with self.assertRaises((ValueError, BuildError)):
                    with phase.complete_partition(
                        budget=budget,
                        maximum_metadata_bytes=1024 * 1024**2,
                        provider_checkout=self.checkout,
                    ):
                        self.fail(
                            "project and original provider each reused the whole budget"
                        )
        self.assertEqual(len(borrowed), 1)
        self.assertLess(borrowed[0].maximum_files, budget.maximum_files)
        self.assertLess(borrowed[0].maximum_total_bytes, budget.maximum_total_bytes)
        self.assertTrue(self.source.exists())
        self.assertFalse(self.destination.exists())

    def test_project_and_original_provider_share_total_payload_budget(self):
        self.combined_budget_refusal(files=False)

    def test_project_and_original_provider_share_file_budget(self):
        self.combined_budget_refusal(files=True)

    def borrowed_repository(
        self, *, administration_in_source=False, objects_in_source=False
    ):
        borrowed = self.root / "borrowed-provider"
        borrowed.mkdir()
        arguments = ["init", "-q", "--template="]
        if administration_in_source:
            arguments.append(
                "--separate-git-dir=" + str(self.source / "provider-administration")
            )
        self.git(*arguments, ".", root=borrowed)
        admin = (
            self.source / "provider-administration"
            if administration_in_source
            else borrowed / ".git"
        )
        source = self.checkout / ".git/objects"
        if objects_in_source:
            source = self.source / "provider-objects"
            (source / "info").mkdir(parents=True)
            (source / "info/alternates").write_text(
                str(self.checkout / ".git/objects") + "\n"
            )
        (admin / "objects/info/alternates").write_text(str(source) + "\n")
        self.git(
            "config", "remote.origin.url", self.origin.repository_url, root=borrowed
        )
        return borrowed, admin

    def provider_overlap_refusal(self, **kwargs):
        borrowed, administration = self.borrowed_repository(**kwargs)
        original = (administration / "config").read_bytes()
        with self.inspecting() as phase:
            with self.assertRaisesRegex(
                ValueError, "administration is part of moving source"
            ):
                with phase.complete_partition(
                    budget=self.namespace_budget,
                    maximum_metadata_bytes=1024 * 1024**2,
                    provider_checkout=borrowed,
                ):
                    self.fail("moving source contains actual provider administration")
        self.assertTrue(self.source.exists())
        self.assertFalse(self.destination.exists())
        self.assertEqual((administration / "config").read_bytes(), original)

    def test_external_checkout_with_git_administration_inside_source_refuses(self):
        self.provider_overlap_refusal(administration_in_source=True)

    def test_external_checkout_with_alternate_object_store_inside_source_refuses(self):
        self.provider_overlap_refusal(objects_in_source=True)

    def test_external_fixed_alternate_store_can_supply_original_roster(self):
        borrowed, _ = self.borrowed_repository()
        with self.inspecting() as phase:
            with phase.complete_partition(
                budget=self.namespace_budget,
                maximum_metadata_bytes=1024 * 1024**2,
                provider_checkout=borrowed,
            ) as owner:
                self.assertEqual(
                    dict(owner.roles)["scripts/bootstrap_litai.py"], "framework"
                )

    def test_provider_include_inside_moving_source_refuses(self):
        borrowed, _ = self.borrowed_repository()
        included = self.source / "provider-configuration"
        included.write_bytes(b"[core]\n  logallrefupdates = true\n")
        self.git("config", "--add", "include.path", str(included), root=borrowed)
        with self.inspecting() as phase:
            with self.assertRaisesRegex(
                ValueError, "administration is part of moving source"
            ):
                with phase.complete_partition(
                    budget=self.namespace_budget,
                    maximum_metadata_bytes=1024 * 1024**2,
                    provider_checkout=borrowed,
                ):
                    self.fail("moving source contains actual provider configuration")
        self.assertTrue(self.source.exists())
        self.assertFalse(self.destination.exists())
        self.assertEqual(included.read_bytes(), b"[core]\n  logallrefupdates = true\n")

    def test_fixed_external_provider_include_is_bound(self):
        borrowed, _ = self.borrowed_repository()
        included = self.root / "provider-configuration"
        included.write_bytes(b"[core]\n  logallrefupdates = true\n")
        self.git("config", "--add", "include.path", str(included), root=borrowed)
        with self.inspecting() as phase:
            with phase.complete_partition(
                budget=self.namespace_budget,
                maximum_metadata_bytes=1024 * 1024**2,
                provider_checkout=borrowed,
            ) as owner:
                self.assertIn(included, owner._provider.objects.snapshots)
                self.assertEqual(
                    dict(owner.roles)["scripts/bootstrap_litai.py"], "framework"
                )
