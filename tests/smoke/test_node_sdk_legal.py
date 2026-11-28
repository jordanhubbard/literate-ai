"""Original canonical Component assets, not source text, authorize legal bytes."""

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.locked_generation_authority import (
    LockedGenerationAuthorityReaderError,
)
from literate_ai.adapters.node_sdk_legal import require_locked_node_sdk_legal_files
from literate_ai.contracts import StandardNodeSDKCommandProfile, canonical_identity
from literate_ai.contracts.authoring_markdown import (
    parse_authoring_markdown,
    render_authoring_markdown,
)
from tests.smoke.test_node_sdk_flavors import canonical_snapshot

LEGAL = b"Fixture-only packaging text. No distribution license is granted.\n"
PROFILE = StandardNodeSDKCommandProfile(
    "node-sdk", "npm", "typescript", "src", ("LICENSE",)
)


class NodeSDKLegalAuthorityTests(unittest.TestCase):
    def fixture(self, root, *, role="node-sdk-legal", declared=True):
        def configure(component, _flavors):
            (component / "legal").mkdir()
            (component / "legal/LICENSE").write_bytes(LEGAL)
            path = component / "component.md"
            value, body = parse_authoring_markdown(path.read_bytes(), source=str(path))
            value["assets"] = (
                [
                    {
                        "asset_id": "sdk-license",
                        "source": "legal/LICENSE",
                        "path": "LICENSE",
                        "role": role,
                        "media_type": "text/plain",
                    }
                ]
                if declared
                else []
            )
            path.write_bytes(render_authoring_markdown(value, body))

        component, snapshot, execution = canonical_snapshot(root, before_lock=configure)
        return SimpleNamespace(
            component=component,
            snapshot=snapshot,
            execution=execution,
            revision=snapshot.authority.lock.nodes[0].revision.identity,
        )

    def compare(self, fixture, *, content=LEGAL, files=None, **changes):
        args = dict(
            component_revision=fixture.revision,
            profile=PROFILE,
            files=(DirectoryExportFile("LICENSE", content, 0o644),)
            if files is None
            else files,
        )
        args.update(changes)
        return require_locked_node_sdk_legal_files(fixture.snapshot, **args)

    def test_canonical_lock_assets_bind_exact_bytes_without_selecting_a_license(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = self.fixture(Path(raw))
            self.assertIsNone(self.compare(fixture))
            # A model-authored implementation is not one of the legal assets.
            self.assertIsNone(
                self.compare(
                    fixture,
                    files=(
                        DirectoryExportFile("LICENSE", LEGAL, 0o644),
                        DirectoryExportFile("src/index.ts", b"export {};\n", 0o644),
                    ),
                )
            )
            generation = next(
                p
                for p in fixture.execution.generation_plans
                if p.component_revision == fixture.revision
            )
            self.assertTrue(generation.generation_key.asset_identities)

    def test_source_presence_and_wrong_role_supply_no_legal_authority(self):
        for options in ({"declared": False}, {"role": "runtime-data"}):
            with self.subTest(options=options), tempfile.TemporaryDirectory() as raw:
                fixture = self.fixture(Path(raw), **options)
                with self.assertRaisesRegex(ValueError, "immutable assets"):
                    self.compare(fixture)

    def test_missing_modified_duplicate_and_foreign_files_are_rejected(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = self.fixture(Path(raw))
            for files in (
                (),
                (DirectoryExportFile("NOTICE", LEGAL, 0o644),),
                (
                    DirectoryExportFile(
                        "LICENSE", LEGAL.replace(b"Fixture", b"Changed"), 0o644
                    ),
                ),
                (DirectoryExportFile("LICENSE", LEGAL + b"\n", 0o644),),
                (DirectoryExportFile("LICENSE", LEGAL, 0o644),) * 2,
            ):
                with self.subTest(paths=[f.path for f in files]):
                    with self.assertRaises(ValueError):
                        self.compare(fixture, files=files)
            with self.assertRaisesRegex(ValueError, "exact Component revision"):
                self.compare(fixture, component_revision=canonical_identity("foreign"))

    def test_unselected_legal_filename_policy_cannot_replace_selected_profile(self):
        with tempfile.TemporaryDirectory() as raw:
            fixture = self.fixture(Path(raw))
            with self.assertRaisesRegex(ValueError, "selected packaging authority"):
                self.compare(
                    fixture,
                    profile=StandardNodeSDKCommandProfile(
                        "node-sdk", "npm", "typescript", "src", ("NOTICE",)
                    ),
                )

    def test_original_legal_input_and_component_changes_invalidate_comparison(self):
        for relative in ("legal/LICENSE", "component.md"):
            with self.subTest(relative=relative), tempfile.TemporaryDirectory() as raw:
                fixture = self.fixture(Path(raw))
                self.compare(fixture)
                path = fixture.component / relative
                path.write_bytes(path.read_bytes() + b"\n")
                with self.assertRaises(LockedGenerationAuthorityReaderError):
                    self.compare(fixture)


if __name__ == "__main__":
    unittest.main()
