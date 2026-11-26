"""Native developmental relocation custody, with explicit framework-fixture seams.

These tests exercise real files and canonical lifecycle/journal operations. The
framework distribution/origin observers are synthetic; no installed/native
framework qualification or public CLI completion is inferred.
"""

from __future__ import annotations

import os
import shutil
import stat
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import retained_layout_journal as journal
from literate_ai.adapters.retained_harness_receipts import RetainedHarnessReceiptError
from literate_ai.adapters.retained_layout import (
    RetainedLayoutError,
    require_qualified_retained_layout,
    resolve_retained_layout,
)
from literate_ai.adapters.retained_layout_service import (
    apply_retained_layout_relocation,
    plan_retained_layout_relocation,
)
from literate_ai.adapters.standard_lifecycle_binding import (
    InstalledFrameworkDistribution,
    InstalledFrameworkDistributionMember,
)
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.project_initialization import ProjectInitializationOrigin
from literate_ai.contracts.retained_layout import RetainedLayoutDeclaration
from literate_ai.contracts.retained_project import RetainedProjectLimits
from literate_ai.projects import load_project
from tests.support.fixtures_test_retained_harness_receipts import (
    _adapter,
    _legacy_project,
    _selectors,
)


def _framework():
    return InstalledFrameworkDistribution(
        "literate-ai",
        "0.9.0",
        (
            InstalledFrameworkDistributionMember(
                "literate_ai/__init__.py", 1, "sha256:" + "a" * 64
            ),
        ),
    )


def _origin(version):
    return ProjectInitializationOrigin(
        "ssh://git.example.test/operator/literate-ai.git",
        "c" * 40,
        "literate-ai",
        version,
    )


def _view(root):
    result = {}
    for path in root.rglob("*"):
        node = path.lstat()
        result[path.relative_to(root).as_posix()] = (
            node.st_dev,
            node.st_ino,
            node.st_mode,
            node.st_uid,
            node.st_gid,
            node.st_nlink,
            node.st_size,
            node.st_mtime_ns,
            node.st_ctime_ns,
            os.readlink(path)
            if path.is_symlink()
            else (path.read_bytes() if path.is_file() else None),
        )
    return result


@contextmanager
def _fixture():
    directory = Path(tempfile.mkdtemp(prefix="layout-publish-")).resolve()
    try:
        yield directory
    except BaseException as exc:
        exc.add_note("actual retained layout fixture: " + str(directory))
        raise
    else:
        shutil.rmtree(directory)


@unittest.skipIf(os.name == "nt", "original POSIX transaction owner")
class RetainedLayoutPublicationTests(unittest.TestCase):
    def test_real_relocation_keeps_source_inodes_and_invalidates_qualification(self):
        with _fixture() as base:
            root = base / "project"
            _legacy_project(root)
            _adapter().initialize(
                root,
                flavor_selectors=_selectors(root),
                source_intelligence_provider="none",
                convert=True,
                run_baseline=True,
            )
            original = root / "components/legacy-project-wrapper/implementation"
            os.link(original / "app.py", original / "app-hard")
            (original / "app-link").symlink_to("app.py")
            (original / "empty").mkdir()
            original_app_bytes = (original / "app.py").read_bytes()
            expected = {
                name: (
                    (original / name).lstat().st_ino,
                    stat.S_IMODE((original / name).lstat().st_mode),
                )
                for name in ("app.py", "app-hard", "empty")
            }
            state = base / "state"
            state.mkdir(mode=0o700)
            declaration = RetainedLayoutDeclaration(
                "components/chosen-wrapper", "retained"
            )
            options = dict(
                limits=RetainedProjectLimits(10000, 16 * 1024**2, 64 * 1024**2),
                case_sensitive=True,
                distribution_observer=_framework,
                origin_observer=_origin,
            )
            plan = plan_retained_layout_relocation(root, declaration, **options)
            result = apply_retained_layout_relocation(
                root,
                declaration,
                **options,
                acknowledged_plan_identity=ContentIdentity.parse_uri(
                    plan["plan_identity"]
                ),
                authorize_relocation=True,
                state_root=state,
            )
            self.assertEqual(result["status"], "relocated")
            self.assertTrue(result["requalification_required"])
            self.assertFalse(result["old_receipt_rewritten"])
            layout = resolve_retained_layout(load_project(root))
            self.assertEqual(layout.declaration, declaration)
            for name, expected_node in expected.items():
                actual = (root / "retained" / name).lstat()
                self.assertEqual(stat.S_IMODE(actual.st_mode), expected_node[1])
                if name == "empty":
                    # Root transitions may share existing framework ancestors;
                    # finite directory recreation preserves modes/topology, not
                    # the inode of every original directory on a forward move.
                    self.assertTrue(stat.S_ISDIR(actual.st_mode))
                    self.assertEqual(list((root / "retained" / name).iterdir()), [])
                else:
                    self.assertEqual(actual.st_ino, expected_node[0])
            self.assertEqual(
                (root / "retained/app.py").read_bytes(), original_app_bytes
            )
            self.assertEqual(
                (root / "retained/app-hard").read_bytes(), original_app_bytes
            )
            self.assertEqual(os.readlink(root / "retained/app-link"), "app.py")
            self.assertFalse((root / ".litai-retained-layout-pending.json").exists())
            self.assertTrue(list(state.glob("retained-layout-*/journal.jsonl")))
            with self.assertRaises(RetainedHarnessReceiptError) as caught:
                require_qualified_retained_layout(load_project(root))
            self.assertEqual(
                caught.exception.code, "retained_receipt.baseline_unqualified"
            )

    def test_refusals_and_real_interrupted_publication_preserve_original_custody(self):
        with _fixture() as base:
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
            source_inode = source.lstat().st_ino
            original = {}
            for path in root.rglob("*"):
                if path.is_file() and not path.is_symlink():
                    original[path.relative_to(root).as_posix()] = (
                        path.read_bytes(),
                        path.lstat().st_ino,
                        stat.S_IMODE(path.lstat().st_mode),
                    )
            state = base / "state"
            state.mkdir(mode=0o700)
            declaration = RetainedLayoutDeclaration(
                "components/chosen-wrapper", "retained"
            )
            options = dict(
                limits=RetainedProjectLimits(10000, 16 * 1024**2, 64 * 1024**2),
                case_sensitive=True,
                distribution_observer=_framework,
                origin_observer=_origin,
            )
            plan = plan_retained_layout_relocation(root, declaration, **options)
            acknowledgement = ContentIdentity.parse_uri(plan["plan_identity"])
            untouched = (_view(root), _view(state))
            with self.assertRaises(RetainedLayoutError) as refused:
                apply_retained_layout_relocation(
                    root,
                    declaration,
                    **options,
                    acknowledged_plan_identity=acknowledgement,
                    authorize_relocation=False,
                    state_root=state,
                )
            self.assertEqual(
                refused.exception.code, "retained.layout.host_authorization_required"
            )
            self.assertEqual(list(state.iterdir()), [])
            self.assertEqual((_view(root), _view(state)), untouched)
            app = source / "app.py"
            app.write_bytes(app.read_bytes() + b"# actual stale-plan source mutation\n")
            stale_before = (_view(root), _view(state))
            with self.assertRaises(RetainedLayoutError) as stale:
                apply_retained_layout_relocation(
                    root,
                    declaration,
                    **options,
                    acknowledged_plan_identity=acknowledgement,
                    authorize_relocation=True,
                    state_root=state,
                )
            self.assertEqual(stale.exception.code, "retained.layout.plan_changed")
            self.assertEqual(list(state.iterdir()), [])
            self.assertEqual((_view(root), _view(state)), stale_before)
            # Reauthor the plan over actual changed source; do not erase the
            # mutation or substitute a serialized grant to reach publication.
            original[app.relative_to(root).as_posix()] = (
                app.read_bytes(),
                app.lstat().st_ino,
                stat.S_IMODE(app.lstat().st_mode),
            )
            plan = plan_retained_layout_relocation(root, declaration, **options)
            native_publication = journal._LayoutJournal.publish_metadata
            calls = []

            def interrupted(owner, *args, **kwargs):
                native_publication(owner, *args, **kwargs)
                calls.append(args[0])
                if len(calls) == 3:
                    raise OSError(
                        "actual injected interruption after third publication"
                    )

            with patch.object(journal._LayoutJournal, "publish_metadata", interrupted):
                with self.assertRaises(RetainedLayoutError) as interrupted_error:
                    apply_retained_layout_relocation(
                        root,
                        declaration,
                        **options,
                        acknowledged_plan_identity=ContentIdentity.parse_uri(
                            plan["plan_identity"]
                        ),
                        authorize_relocation=True,
                        state_root=state,
                    )
            self.assertEqual(
                interrupted_error.exception.code, "retained.layout.transaction_failed"
            )
            self.assertIsInstance(interrupted_error.exception.__cause__, OSError)
            self.assertIn(
                "after third publication", str(interrupted_error.exception.__cause__)
            )
            self.assertEqual(len(calls), 3)
            self.assertEqual(source.lstat().st_ino, source_inode)
            for name, (raw, inode, mode) in original.items():
                path = root / name
                self.assertEqual(path.read_bytes(), raw, name)
                self.assertEqual(path.lstat().st_ino, inode, name)
                self.assertEqual(stat.S_IMODE(path.lstat().st_mode), mode, name)
            self.assertFalse((root / "retained").exists())
            self.assertFalse((root / "components/chosen-wrapper").exists())
            self.assertFalse((root / ".litai-retained-layout-pending.json").exists())
            logs = list(state.glob("retained-layout-*/journal.jsonl"))
            self.assertEqual(len(logs), 1)
            self.assertIn(b'"event":"transaction-rolled-back"', logs[0].read_bytes())

    def test_foreign_metadata_after_real_publication_is_preserved_as_incomplete(self):
        with _fixture() as base:
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
            source_bytes = (source / "app.py").read_bytes()
            source_inode = (source / "app.py").lstat().st_ino
            state = base / "state"
            state.mkdir(mode=0o700)
            declaration = RetainedLayoutDeclaration(
                "components/chosen-wrapper", "retained"
            )
            options = dict(
                limits=RetainedProjectLimits(10000, 16 * 1024**2, 64 * 1024**2),
                case_sensitive=True,
                distribution_observer=_framework,
                origin_observer=_origin,
            )
            plan = plan_retained_layout_relocation(root, declaration, **options)
            native_publication = journal._LayoutJournal.publish_metadata
            injected = []

            def foreign_after_real_publication(owner, coordinate, **kwargs):
                native_publication(owner, coordinate, **kwargs)
                if not injected:
                    path = root / coordinate
                    path.rename(base / "original-published-metadata-preserved")
                    path.write_bytes(b"foreign concurrently published metadata\n")
                    injected.append((coordinate, path.lstat().st_ino))
                    raise OSError("actual interruption after foreign replacement")

            with patch.object(
                journal._LayoutJournal,
                "publish_metadata",
                foreign_after_real_publication,
            ):
                with self.assertRaises(RetainedLayoutError) as incomplete:
                    apply_retained_layout_relocation(
                        root,
                        declaration,
                        **options,
                        acknowledged_plan_identity=ContentIdentity.parse_uri(
                            plan["plan_identity"]
                        ),
                        authorize_relocation=True,
                        state_root=state,
                    )
            self.assertEqual(
                incomplete.exception.code, "retained.layout.recovery_incomplete"
            )
            self.assertIsInstance(incomplete.exception.__cause__, ExceptionGroup)
            self.assertEqual(len(injected), 1)
            path = root / injected[0][0]
            self.assertEqual(
                path.read_bytes(), b"foreign concurrently published metadata\n"
            )
            self.assertEqual(path.lstat().st_ino, injected[0][1])
            self.assertEqual((root / "retained/app.py").read_bytes(), source_bytes)
            self.assertEqual((root / "retained/app.py").lstat().st_ino, source_inode)
            self.assertTrue((root / ".litai-retained-layout-pending.json").is_file())
            self.assertTrue(list(state.glob("retained-layout-*/journal.jsonl")))
            self.assertTrue((base / "original-published-metadata-preserved").is_file())
