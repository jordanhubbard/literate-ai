"""Authored link selection and SDK-scoped custody retain default identities."""

import dataclasses
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters.native_sdk_source_custody import NativeSdkSourceInputClosure
from literate_ai.application.repository_sources import (
    RepositoryCheckout,
    RepositorySourceLockResolver,
    RepositorySourceResolutionError,
)
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.component_locking.authoring import (
    AuthoredRepositorySourceDependency,
)
from literate_ai.contracts.sbom import repository_dependency_identity
from literate_ai.sources import InternalSymlinkSnapshotPolicy, SourceSnapshotter
from tests.support.fixtures_test_repository_sources import dependency
from tests.support.fixtures_test_schema_catalog import SchemaCatalog


class SourceLinkSelectionContractTests(unittest.TestCase):
    def test_legacy_dictionary_identity_and_false_normalization(self):
        original = dependency()
        self.assertNotIn("allow_internal_symlinks", original.to_dict())
        self.assertEqual(
            dataclasses.replace(original, allow_internal_symlinks=False), original
        )
        raw = original.to_dict()
        raw["allow_internal_symlinks"] = False
        self.assertEqual(type(original).from_dict(raw).to_dict(), original.to_dict())
        selected = dataclasses.replace(original, allow_internal_symlinks=True)
        self.assertNotEqual(selected.identity, original.identity)
        self.assertNotEqual(
            repository_dependency_identity(selected),
            repository_dependency_identity(original),
        )
        self.assertEqual(type(original).from_dict(selected.to_dict()), selected)
        SchemaCatalog().validate(selected.SCHEMA, selected.to_dict())

    def test_authored_roundtrip_and_strict_boolean(self):
        source = dependency()
        authored = AuthoredRepositorySourceDependency(
            source.dependency_id,
            source.repository_url,
            source.revision_selector,
            source.dependency_kind,
            allow_internal_symlinks=True,
        )
        self.assertEqual(type(authored).from_dict(authored.to_dict()), authored)
        self.assertNotIn(
            "allow_internal_symlinks",
            dataclasses.replace(authored, allow_internal_symlinks=False).to_dict(),
        )
        for value in (1, 0, None, "true", [], {}):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    dataclasses.replace(source, allow_internal_symlinks=value)
                raw = authored.to_dict()
                raw["allow_internal_symlinks"] = value
                with self.assertRaises(ValueError):
                    type(authored).from_dict(raw)
                with self.assertRaises(AssertionError):
                    SchemaCatalog().validate(
                        source.SCHEMA,
                        {**source.to_dict(), "allow_internal_symlinks": value},
                    )

    def test_acquisition_selection_mismatch_refuses_before_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "file").write_bytes(b"source")
            capture = SourceSnapshotter().snapshot_local(root)
            checkout = RepositoryCheckout(
                root, "a" * 40, canonical_identity("resolver")
            )
            with self.assertRaisesRegex(
                RepositorySourceResolutionError, "authored link"
            ):
                RepositorySourceLockResolver._source_lock(
                    dataclasses.replace(dependency(), allow_internal_symlinks=True),
                    checkout,
                    capture,
                )

    def test_markdown_render_and_parse_preserve_explicit_selection(self):
        from literate_ai.adapters.component_markdown import (
            parse_component_markdown,
            render_component_markdown,
        )
        from tests.support.fixtures_test_component_lock_contracts import (
            component_authoring,
        )

        source = dependency()
        selected = AuthoredRepositorySourceDependency(
            source.dependency_id,
            source.repository_url,
            source.revision_selector,
            source.dependency_kind,
            allow_internal_symlinks=True,
        )
        authored = dataclasses.replace(
            component_authoring("sample"), source_dependencies=(selected,)
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory).resolve()
            path = root / "sample/component.md"
            path.parent.mkdir()
            text = render_component_markdown(authored, path, project_root=root)
            self.assertIn("allow_internal_symlinks: true", text)
            self.assertEqual(
                parse_component_markdown(path, text, project_root=root), authored
            )
            legacy = dataclasses.replace(
                authored,
                source_dependencies=(
                    dataclasses.replace(selected, allow_internal_symlinks=False),
                ),
            )
            self.assertNotIn(
                "allow_internal_symlinks",
                render_component_markdown(legacy, path, project_root=root),
            )

    def test_public_authoring_projection_preserves_source_policy(self):
        from literate_ai.application.component_authoring_migration import (
            project_component_authoring,
        )
        from tests.support.fixtures_test_component_authoring_migration import (
            definition,
            pretty_repository_bytes,
            raw_identity,
            repository_dependency,
        )

        selected = dataclasses.replace(
            repository_dependency(), allow_internal_symlinks=True
        )
        legacy = definition()
        legacy = dataclasses.replace(
            legacy,
            source_dependencies=tuple(
                dataclasses.replace(
                    ref, identity=raw_identity(pretty_repository_bytes(selected))
                )
                for ref in legacy.source_dependencies
            ),
        )
        authored = project_component_authoring(
            legacy, repository_dependencies=(selected,)
        )
        self.assertTrue(authored.source_dependencies[0].allow_internal_symlinks)


@unittest.skipIf(os.name == "nt", "Explicit POSIX source-link custody")
class ScopedSdkSourceLinkTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        (self.root / "code.txt").write_bytes(b"eval('7')\n")
        (self.root / "alias.py").symlink_to("code.txt")
        (self.root / "chain.py").symlink_to("alias.py")
        (self.root / "self").symlink_to(".", target_is_directory=True)
        self.capture = SourceSnapshotter(
            InternalSymlinkSnapshotPolicy()
        ).snapshot_local(self.root)

    def closure(self):
        return NativeSdkSourceInputClosure(self.root, self.capture.snapshot.entries)

    def test_alias_resolution_uses_original_regular_custody(self):
        closure = self.closure()
        self.assertEqual(
            closure.file_aliases, (("alias.py", "code.txt"), ("chain.py", "code.txt"))
        )
        entry = next(e for e in self.capture.snapshot.entries if e.path == "code.txt")
        self.assertEqual(
            closure.pin(
                self.root / entry.path,
                boundary=self.root,
                label="source",
                expected_identity=entry.identity,
            ),
            b"eval('7')\n",
        )
        closure.require_unchanged()
        (self.root / "alias.py").unlink()
        (self.root / "alias.py").symlink_to("./code.txt")
        with self.assertRaisesRegex(ValueError, "exact capture"):
            closure.require_unchanged()

    def test_regular_owner_still_refuses_pinning_an_alias(self):
        closure = self.closure()
        with self.assertRaises(ValueError):
            closure.pin(self.root / "alias.py", boundary=self.root, label="unsafe")

    def test_alias_scan_expansion_has_existing_finite_budget(self):
        total = sum(e.size for e in self.capture.snapshot.entries)
        largest = max(e.size for e in self.capture.snapshot.entries)
        with (
            patch(
                "literate_ai.adapters.native_sdk_source_custody._MAX_TOTAL_BYTES", total
            ),
            patch(
                "literate_ai.adapters.native_sdk_source_custody._MAX_FILE_BYTES",
                largest,
            ),
        ):
            with self.assertRaisesRegex(ValueError, "scan expansion"):
                self.closure()


@unittest.skipUnless(
    os.environ.get("LITAI_SDK_SOURCE_LINK_CORPUS"),
    "requires explicit real Git SDK source corpus",
)
@unittest.skipIf(os.name == "nt", "Explicit POSIX SDK source-link custody")
class ActualSdkSourceLinkCorpusTests(unittest.TestCase):
    def test_every_real_captured_input_is_pinned_or_has_exact_link_custody(self):
        import json
        import subprocess

        from literate_ai.adapters.source.repository_git import (
            GitRepositorySourceCapturer,
        )

        root = Path(os.environ["LITAI_SDK_SOURCE_LINK_CORPUS"]).resolve(strict=True)
        revision = subprocess.check_output(
            ["git", "--no-optional-locks", "-C", str(root), "rev-parse", "HEAD"],
            text=True,
            timeout=60,
        ).strip()
        checkout = RepositoryCheckout(
            root, revision, canonical_identity("read-only-corpus"), True
        )
        capture = GitRepositorySourceCapturer().capture(checkout)
        self.assertFalse(capture.git.dirty)
        self.assertFalse(capture.git.submodules)
        self.assertFalse(capture.lfs_pointers)
        closure = NativeSdkSourceInputClosure(root, capture.snapshot.entries)
        files = links = payload = 0
        for entry in capture.snapshot.entries:
            if entry.entry_type.value == "file":
                data = closure.pin(
                    root / entry.path,
                    boundary=root,
                    label="sdk-source:" + entry.path,
                    expected_identity=entry.identity,
                )
                self.assertEqual(len(data), entry.size)
                files += 1
            else:
                data = closure.target_bytes(entry)
                links += 1
            payload += len(data)
        self.assertGreater(links, 0)
        self.assertEqual(files + links, len(capture.snapshot.entries))
        closure.require_unchanged()
        self.assertEqual(
            subprocess.check_output(
                [
                    "git",
                    "--no-optional-locks",
                    "-C",
                    str(root),
                    "status",
                    "--porcelain",
                    "--untracked-files=no",
                ],
                timeout=60,
            ),
            b"",
        )
        result = {
            "revision": revision,
            "snapshot_identity": capture.snapshot_id,
            "entries": files + links,
            "regular_files": files,
            "symlinks": links,
            "file_aliases": len(closure.file_aliases),
            "payload_bytes": payload,
            "all_regular_inputs_pinned_and_current": True,
            "all_link_targets_pinned_and_current": True,
            "scope": (
                "actual full source input custody; no SDK build or release acceptance"
            ),
        }
        report = os.environ.get("LITAI_SDK_SOURCE_LINK_CORPUS_REPORT")
        if report:
            target = Path(report).absolute()
            self.assertFalse(target == root or root in target.parents)
            with target.open("x") as output:
                json.dump(result, output, indent=2)
                output.write("\n")
        print(json.dumps(result))
