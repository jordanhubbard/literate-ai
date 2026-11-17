"""Actual authored Git locks, scanner aliases, native compilation and cache custody."""

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.native_sdk_custody import materialize_native_sdk
from literate_ai.adapters.native_sdk_recipes import select_native_sdk_recipes
from literate_ai.adapters.native_sdk_source_build import NativeSdkSourceBuildService
from literate_ai.application.repository_sources import RepositorySourceResolutionError
from literate_ai.contracts import SourceIntelligenceMode, canonical_identity
from literate_ai.contracts.authoring_markdown import (
    parse_authoring_markdown,
    render_authoring_markdown,
)
from literate_ai.security import (
    AuthorizationRevocationSet,
    FindingSeverity,
    SecurityPolicy,
)
from literate_ai.sources import QuarantineStore
from literate_ai.storage import BlobRef, ReferenceIndex
from tests.support import fixtures_test_native_sdk_recipes as recipe_fixtures
from tests.support.fixtures_test_repository_sources import source_intelligence_policy


@unittest.skipIf(os.name == "nt", "Explicit POSIX original-source link custody")
class NativeSdkSourceLinkTests(unittest.TestCase):
    def setUp(self):
        self.recipe = recipe_fixtures.NativeSdkRecipeTests(
            "test_selected_flavor_recipe_drives_real_native_build_and_relocation"
        )
        self.addCleanup(self.recipe.doCleanups)
        self.recipe.source_link_targets = {"vendor_math.c": "vendor_math.txt"}
        if (
            self._testMethodName
            == "test_alias_filename_is_scanned_before_authorization"
        ):
            self.recipe.source_extra_files = {"dynamic.txt": b"eval('7')\n"}
            self.recipe.source_link_targets["dynamic.py"] = "dynamic.txt"
        self.recipe.setUp()
        self.fixture = self.recipe.fixture
        self.revocations = AuthorizationRevocationSet()

    def service(self, *, host_build_acknowledged=True):
        snapshot = self.recipe.snapshot()
        (selection,) = select_native_sdk_recipes(
            snapshot,
            next(
                n.revision.identity
                for n in snapshot.authority.lock.nodes
                if n.revision.repository_sources
            ),
        )
        self.assertTrue(selection.source_lock.dependency.allow_internal_symlinks)
        work = Path(tempfile.mkdtemp(prefix="links-", dir=self.fixture.root))
        self.quarantine = QuarantineStore(work / "quarantine", self.fixture.store)
        self.references = ReferenceIndex(work / "references", self.fixture.store)
        return NativeSdkSourceBuildService(
            snapshot=snapshot,
            selection=selection,
            tools=self.fixture.tools,
            store=self.fixture.store,
            quarantine=self.quarantine,
            source_intelligence_policy=source_intelligence_policy(
                "none", SourceIntelligenceMode.OFF
            ),
            security_policy=SecurityPolicy(
                canonical_identity("policy").uri,
                blocked_at_or_above=FindingSeverity.HIGH,
            ),
            revocations=lambda: self.revocations,
            actor="native-fixture-operator",
            reason="Build actual authored SDK source aliases",
            environment=dict(os.environ),
            host_build_acknowledged=host_build_acknowledged,
            references=self.references,
        )

    def test_actual_lock_native_build_relocation_and_quarantine_alias(self):
        service = self.service()
        built = service.build()
        inventory = self.fixture.manifest(built.resolution.index_binding.index)
        self.assertEqual(
            inventory["schema"], "literate-ai/native-sdk-source-inventory@2"
        )
        self.assertEqual(
            inventory["file_aliases"],
            [{"path": "vendor_math.c", "source_path": "vendor_math.txt"}],
        )
        record = next(
            x for x in inventory["files"] if x["entry"]["path"] == "vendor_math.c"
        )
        self.assertEqual(record["entry"]["entry_type"], "symlink")
        self.assertEqual(
            self.fixture.store.get_bytes(BlobRef.from_dict(record["blob"])),
            b"vendor_math.txt",
        )
        cached = (
            self.quarantine.quarantine_root
            / built.resolution.lock.source_snapshot.digest
            / "tree"
        )
        self.assertTrue((cached / "vendor_math.c").is_symlink())
        self.assertEqual(os.readlink(cached / "vendor_math.c"), "vendor_math.txt")
        self.fixture.remove_source()
        parent = self.fixture.root / "consumer"
        parent.mkdir()
        sdk = materialize_native_sdk(
            built.product.snapshot,
            expected_identity=built.product.snapshot.identity,
            store=self.fixture.store,
            parent=parent,
        )
        executed = subprocess.run(
            [
                sys.executable,
                "-I",
                "-B",
                "-c",
                "import sys;sys.path.insert(0,sys.argv[1]);"
                "import vendor_math;print(vendor_math.scale(1.5,3))",
                str(sdk / built.product.snapshot.import_root),
            ],
            capture_output=True,
            text=True,
            timeout=20,
        )
        self.assertEqual(executed.returncode, 0, executed.stderr)
        self.assertEqual(executed.stdout.strip(), "4.5")

    def test_alias_filename_is_scanned_before_authorization(self):
        service = self.service(host_build_acknowledged=False)
        original = service.scanner.scan
        observed = []
        observed_modules = []

        def scan(modules):
            observed_modules.append(tuple((m.path, m.content) for m in modules))
            result = original(modules)
            observed.append(result)
            return result

        with patch.object(service.scanner, "scan", side_effect=scan):
            with self.assertRaises(RepositorySourceResolutionError) as raised:
                service.build()
        self.assertRegex(str(raised.exception.__cause__), "security.build_blocked")
        self.assertEqual(len(observed), 1)
        report = observed[0].to_dict()
        self.assertIn(("dynamic.py", b"eval('7')\n"), observed_modules[0])
        self.assertTrue(
            any(
                f["category"] == "dynamic-code-execution"
                and f["message"].startswith("dynamic.py:")
                for f in report["findings"]
            )
        )
        self.assertFalse(self.references.path.exists())
        self.assertFalse(list(self.quarantine.quarantine_root.iterdir()))

    def test_default_authored_policy_refuses_real_source_links(self):
        path = self.recipe.component_document
        document, body = parse_authoring_markdown(path.read_bytes(), source=str(path))
        document["source_dependencies"][0].pop("allow_internal_symlinks")
        path.write_bytes(render_authoring_markdown(document, body))
        from tests.support.fixtures_test_cli_component_locks import _run

        status, result, _ = _run(self.recipe.cli)
        self.assertNotEqual(status, 0, result)
        self.assertIn("repository_source_unresolved", str(result))

    def test_changed_link_before_authorization_cannot_issue_a_grant(self):
        service = self.service()
        original = service.planner.plan
        changed = []

        def plan(*args, **kwargs):
            result = original(*args, **kwargs)
            if not changed:
                inspection = next(iter(service._inspections.values()))
                link = inspection.files.root / "vendor_math.c"
                link.unlink()
                link.symlink_to("./vendor_math.txt")
                changed.append(True)
            return result

        with patch.object(service.planner, "plan", side_effect=plan):
            with self.assertRaises(RepositorySourceResolutionError) as raised:
                service.build()
        self.assertRegex(str(raised.exception.__cause__), "source link differs")
        self.assertEqual(service._grants, {})
        self.assertFalse(self.references.path.exists())

    def test_changed_link_after_configure_stops_compile_and_admission(self):
        from literate_ai.adapters.builders._process import run_bounded_process

        service = self.service()
        commands = []

        def run(command, **kwargs):
            result = run_bounded_process(command, **kwargs)
            self.assertEqual(result.returncode, 0, result.stderr)
            commands.append(command)
            link = kwargs["cwd"] / "vendor_math.c"
            link.unlink()
            link.symlink_to("./vendor_math.txt")
            return result

        with patch(
            "literate_ai.adapters.native_sdk_build.run_bounded_process", side_effect=run
        ):
            with self.assertRaises(RepositorySourceResolutionError):
                service.build()
        self.assertEqual(len(commands), 1)
        self.assertIn("-S", commands[0])
        self.assertFalse(self.references.path.exists())
        self.assertFalse(list(self.quarantine.quarantine_root.iterdir()))

    def test_live_revocation_stops_link_aware_build_after_configure(self):
        from literate_ai.adapters.builders._process import run_bounded_process

        service = self.service()
        commands = []

        def run(command, **kwargs):
            result = run_bounded_process(command, **kwargs)
            self.assertEqual(result.returncode, 0, result.stderr)
            commands.append(command)
            for grant in service._grants.values():
                self.revocations = self.revocations.revoke(
                    grant.authorization_id, actor="operator", reason="Stop this build"
                )
            return result

        with patch(
            "literate_ai.adapters.native_sdk_build.run_bounded_process", side_effect=run
        ):
            with self.assertRaises(RepositorySourceResolutionError) as raised:
                service.build()
        self.assertRegex(str(raised.exception.__cause__), "authorization_revoked")
        self.assertEqual(len(commands), 1)
        self.assertFalse(self.references.path.exists())
        self.assertFalse(list(self.quarantine.quarantine_root.iterdir()))

    def test_link_policy_does_not_grant_host_build_authorization(self):
        service = self.service(host_build_acknowledged=False)
        with patch("literate_ai.adapters.native_sdk_build.run_bounded_process") as run:
            with self.assertRaises(RepositorySourceResolutionError):
                service.build()
            run.assert_not_called()
        self.assertFalse(self.references.path.exists())
        self.assertFalse(list(self.quarantine.quarantine_root.iterdir()))
