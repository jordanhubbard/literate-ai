"""Actual retained receipt and parent readers with protocol-qualified child data.

The retained Make harness executes; the child's qualification uses the existing
controlled lifecycle fixture. This is no genuine native two-build acceptance.
"""

from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import conversion_authority as conversion
from literate_ai.adapters import native_child_publication as publication
from literate_ai.adapters.native_child_inputs import QualifiedNativeChildError
from literate_ai.adapters.native_child_plans import read_current_parent
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.operator_adoption import ConversionAuthorityStage
from literate_ai.projects import LoadedProject, ProjectConfigurationStore
from tests.support import fixtures_test_retained_harness_receipts as retained
from tests.support import fixtures_test_retained_provider_authority as child_fixtures


class NativeChildParentReaderTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        base = Path(temporary.name).resolve()
        self.root = base / "parent"
        retained._legacy_project(self.root)
        retained._adapter().initialize(
            self.root,
            flavor_selectors=retained._selectors(self.root),
            source_intelligence_provider="none",
            convert=True,
        )
        candidate = base / "retained-receipt.json"
        for argv in (
            ("run-retained", str(candidate), "--worker-id", "local"),
            ("update", str(candidate)),
        ):
            status, result = retained._invoke(
                "project", "test-receipt", *argv, "--project", str(self.root)
            )
            self.assertEqual(status, 0, result)
        child = child_fixtures.RetainedProviderAuthorityTests()
        child.setUp()
        self.addCleanup(child.doCleanups)
        destination = self.root / ".literate/native-projects/a"
        destination.parent.mkdir(exist_ok=True)
        shutil.copytree(child.root, destination)
        snapshot = ProjectConfigurationStore(self.root).read()
        project = LoadedProject(snapshot.root, snapshot.definition)
        conversion.register_native_project(project, destination)
        evidence = conversion.evidence_for_conversion_stage(
            project, ConversionAuthorityStage.QUALIFIED
        )
        store = conversion.FilesystemConversionAuthorityStore(self.root)
        # Establish only protocol history around the fixture's already qualified
        # child. Normal parent qualification and actual receipt readers run below.
        for stage, items in (
            (
                ConversionAuthorityStage.RETAINED,
                (conversion._current_receipt_identity(project),),
            ),
            (ConversionAuthorityStage.DRAFTED, evidence),
            (ConversionAuthorityStage.QUALIFIED, evidence),
        ):
            store.advance(stage, evidence_identities=items)
        self.parent = read_current_parent(self.root)

    def prepare(self):
        metadata = {
            "native-projects.json": self.parent.registry_bytes,
            "conversion-authority.json": self.parent.state_bytes,
        }
        return publication.prepare_native_child_publication(
            self.root,
            plan_identity=canonical_identity(
                {"protocol-fixture": "unchanged membership"}
            ).uri,
            previous=metadata,
            proposed=metadata,
            validate=self.parent.require_source_unchanged,
        )

    def test_parent_reopens_wrapper_and_declared_platform_without_execution(
        self,
    ):
        with mock.patch(
            "subprocess.Popen", side_effect=AssertionError("reader executed a process")
        ):
            current = read_current_parent(self.root)
            current.require_source_unchanged()
        self.assertTrue(current.composition_supported)
        self.assertEqual(current.summary["receipt"], self.parent.summary["receipt"])
        self.assertTrue(
            any(p["axis"] == "platform.os" for p in current.summary["platform"])
        )

    def test_pending_publication_checks_actual_sources_and_reopens_complete_parent(
        self,
    ):
        identity = self.prepare()
        with self.assertRaises(conversion.ConversionAuthorityError):
            read_current_parent(self.root)
        observed = []
        publication.recover_native_child_publication(
            self.root,
            publication_identity=identity,
            finish=True,
            before_mutation=self.parent.require_source_unchanged,
            validate=lambda: observed.append(read_current_parent(self.root)),
        )
        self.assertEqual(len(observed), 1)
        self.assertEqual(
            read_current_parent(self.root).summary["receipt"],
            self.parent.summary["receipt"],
        )
        self.assertEqual(
            self.parent.receipt_path.read_bytes(), self.parent.receipt_bytes
        )

    def test_actual_retained_source_drift_refuses_before_any_metadata_move(self):
        identity = self.prepare()
        source = self.root / "components/legacy-project-wrapper/implementation/app.py"
        source.write_bytes(b"foreign retained source edit\n")
        with self.assertRaises(QualifiedNativeChildError):
            publication.recover_native_child_publication(
                self.root,
                publication_identity=identity,
                finish=True,
                before_mutation=self.parent.require_source_unchanged,
                validate=lambda: read_current_parent(self.root),
            )
        self.assertEqual(
            (self.root / conversion.NATIVE_PROJECTS_FILE).read_bytes(),
            self.parent.registry_bytes,
        )
        self.assertEqual(
            (self.root / conversion.CONVERSION_AUTHORITY_FILE).read_bytes(),
            self.parent.state_bytes,
        )
        self.assertEqual(source.read_bytes(), b"foreign retained source edit\n")
