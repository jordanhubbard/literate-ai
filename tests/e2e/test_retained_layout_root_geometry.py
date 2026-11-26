"""Real three-geometry moves with explicit synthetic framework observations.

GNUmakefile avoids the genuine reserved framework Makefile collision; this does
not waive collision detection or substitute a synthetic source tree/native move.
"""

from __future__ import annotations

import copy
import os
import shutil
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import harness_inventory
from literate_ai.adapters import retained_layout_inspection as inspection
from literate_ai.adapters.retained_layout import (
    RetainedLayoutError,
    resolve_retained_layout,
)
from literate_ai.adapters.retained_layout_inspection import (
    _inspect_source_paths,
    _InspectionPath,
    inspect_retained_layout_harness,
)
from literate_ai.adapters.retained_layout_partition import (
    observe_retained_layout_partition,
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
from literate_ai.contracts.native_tree_shards import ComposedNativeTree
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
                "literate_ai/__init__.py",
                1,
                "sha256:" + "a" * 64,
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


@unittest.skipIf(os.name == "nt", "original POSIX transaction owner")
class RetainedLayoutRootGeometryTests(unittest.TestCase):
    def test_plain_root_and_component_nested_preserve_actual_source_geometry(self):
        base = Path(tempfile.mkdtemp(prefix="layout-root-geometries-")).resolve()
        try:
            root = base / "project"
            _legacy_project(root)
            (root / "Makefile").rename(root / "GNUmakefile")
            (root / "setup.cfg").write_text(
                "[metadata]\nname=retained-probe\n[tool:pytest]\ntestpaths=tests\n",
                encoding="utf-8",
            )
            (root / "tests").mkdir()
            (root / "tests/test_probe.py").write_text(
                "def test_source_probe():\n    assert True\n",
                encoding="utf-8",
            )
            _adapter().initialize(
                root,
                flavor_selectors=_selectors(root),
                source_intelligence_provider="none",
                convert=True,
                run_baseline=True,
            )
            original = root / "components/legacy-project-wrapper/implementation"
            (original / "app.py").chmod(0o755)
            os.link(original / "app.py", original / "app-hard")
            (original / "app-link").symlink_to("app.py")
            (original / "empty").mkdir(mode=0o700)
            expected_inode = (original / "app.py").lstat().st_ino
            expected_bytes = (original / "app.py").read_bytes()
            state = base / "state"
            state.mkdir(mode=0o700)
            options = dict(
                limits=RetainedProjectLimits(10000, 16 * 1024**2, 64 * 1024**2),
                case_sensitive=True,
                distribution_observer=_framework,
                origin_observer=_origin,
            )
            identities = []
            for declaration in (
                RetainedLayoutDeclaration("components/plain-wrapper", "retained"),
                RetainedLayoutDeclaration("components/root-wrapper", "."),
                RetainedLayoutDeclaration(
                    "components/nested-wrapper",
                    "components/nested-wrapper/implementation",
                ),
            ):
                with self.subTest(implementation=declaration.implementation_directory):
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
                    identities.append(result["source_identity"])
                    layout = resolve_retained_layout(load_project(root))
                    self.assertEqual(layout.declaration, declaration)
                    for name in ("app.py", "app-hard"):
                        path = layout.implementation / name
                        self.assertEqual(path.lstat().st_ino, expected_inode)
                        self.assertEqual(stat.S_IMODE(path.lstat().st_mode), 0o755)
                        self.assertEqual(path.read_bytes(), expected_bytes)
                    self.assertEqual(
                        os.readlink(layout.implementation / "app-link"), "app.py"
                    )
                    self.assertEqual(
                        stat.S_IMODE((layout.implementation / "empty").lstat().st_mode),
                        0o700,
                    )
                    self.assertEqual(
                        list((layout.implementation / "empty").iterdir()), []
                    )
                    self.assertFalse(
                        (root / ".litai-retained-layout-pending.json").exists()
                    )
                    self.assertTrue(result["requalification_required"])
                    with observe_retained_layout_partition(
                        load_project(root)
                    ) as context:
                        inventory = inspect_retained_layout_harness(context)
                        self.assertEqual(
                            inventory["commands"]["build"]["evidence"], "GNUmakefile"
                        )
                        self.assertEqual(
                            inventory["commands"]["test"]["evidence"], "GNUmakefile"
                        )
                        self.assertIn(
                            "test-runner.pytest",
                            {x["detector_id"] for x in inventory["findings"]},
                        )
                        with _inspect_source_paths(context) as (query, _):
                            self.assertFalse((query / "Makefile").is_file())
                            self.assertTrue((query / "GNUmakefile").is_file())
                            self.assertEqual(
                                (query / "GNUmakefile").read_bytes(),
                                (layout.implementation / "GNUmakefile").read_bytes(),
                            )
                            with self.assertRaises(TypeError):
                                copy.copy(query)
                            thread_errors = []

                            def foreign_thread(query=query, errors=thread_errors):
                                try:
                                    query.is_dir()
                                except RetainedLayoutError as exc:
                                    errors.append(exc.code)

                            thread = threading.Thread(target=foreign_thread)
                            thread.start()
                            thread.join(timeout=5)
                            self.assertFalse(thread.is_alive())
                            self.assertEqual(
                                thread_errors,
                                ["retained.layout.original_inspection_required"],
                            )
                        with self.assertRaises(RetainedLayoutError) as ended:
                            query.is_dir()
                        self.assertEqual(
                            ended.exception.code,
                            "retained.layout.original_inspection_required",
                        )
                        with self.assertRaises(RetainedLayoutError) as forged:
                            _InspectionPath().is_dir()
                        self.assertEqual(
                            forged.exception.code,
                            "retained.layout.original_inspection_required",
                        )
            self.assertEqual(len(set(identities)), 1)
            actual_commands = layout.implementation / "GNUmakefile"
            actual_commands.write_bytes(
                actual_commands.read_bytes() + b"ci:\n\t@printf 'native-ci\\n'\n"
            )
            with observe_retained_layout_partition(load_project(root)) as context:
                refreshed = inspect_retained_layout_harness(context)
            self.assertIn("ci", refreshed["commands"])
            self.assertEqual(refreshed["commands"]["ci"]["evidence"], "GNUmakefile")
            actual_detector = harness_inventory._detect_build_system
            mutation = []

            def change_after_real_detection(query_root):
                result = actual_detector(query_root)
                app = layout.implementation / "app.py"
                app.write_bytes(
                    app.read_bytes() + b"# actual during-inspection mutation\n"
                )
                mutation.append(app.read_bytes())
                return result

            with observe_retained_layout_partition(load_project(root)) as context:
                with patch.object(
                    harness_inventory,
                    "_detect_build_system",
                    change_after_real_detection,
                ):
                    with self.assertRaises(RetainedLayoutError) as changed:
                        inspect_retained_layout_harness(context)
            self.assertEqual(changed.exception.code, "retained.layout.source_changed")
            self.assertEqual(len(mutation), 1)
            self.assertEqual(
                (layout.implementation / "app.py").read_bytes(), mutation[0]
            )
        except BaseException as exc:
            exc.add_note("actual retained layout root-geometry fixture: " + str(base))
            raise
        else:
            shutil.rmtree(base)

    def test_many_real_source_queries_share_indexes_and_finite_resolution_work(self):
        base = Path(tempfile.mkdtemp(prefix="layout-query-budget-")).resolve()
        try:
            root = base / "project"
            _legacy_project(root)
            _adapter().initialize(
                root,
                flavor_selectors=_selectors(root),
                source_intelligence_provider="none",
                convert=True,
                run_baseline=True,
            )
            state = base / "state"
            state.mkdir(mode=0o700)
            declaration = RetainedLayoutDeclaration(
                "components/query-wrapper", "retained"
            )
            options = dict(
                limits=RetainedProjectLimits(10000, 16 * 1024**2, 64 * 1024**2),
                case_sensitive=True,
                distribution_observer=_framework,
                origin_observer=_origin,
            )
            plan = plan_retained_layout_relocation(root, declaration, **options)
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
            source = root / "retained"
            inputs = source / "query-inputs"
            inputs.mkdir()
            expected = {}
            for number in range(128):
                name = "q" + str(number).zfill(5) + ".txt"
                raw = ("actual retained input " + str(number) + "\n").encode()
                (inputs / name).write_bytes(raw)
                expected[name] = raw
            for number in reversed(range(32)):
                target = (
                    "query-inputs"
                    if number == 31
                    else "alias" + str(number + 1).zfill(2)
                )
                (source / ("alias" + str(number).zfill(2))).symlink_to(
                    target, target_is_directory=True
                )
            native_batch_resolver = ComposedNativeTree.resolve_all
            rebuilt = []

            def real_batch(tree, names):
                rebuilt.append(len(names))
                return native_batch_resolver(tree, names)

            with observe_retained_layout_partition(load_project(root)) as context:
                with patch.object(ComposedNativeTree, "resolve_all", real_batch):
                    with _inspect_source_paths(context) as (query, _):
                        for name, raw in expected.items():
                            path = query / "query-inputs" / name
                            self.assertTrue(path.is_file())
                            self.assertEqual(path.read_bytes(), raw)
                        self.assertEqual(
                            (query / "alias00/q00017.txt").read_bytes(),
                            expected["q00017.txt"],
                        )
                # Full captures/mode/alias bookends may rebuild a bounded number
                # of indexes. Per-leaf queries must not do so for each source.
                self.assertLessEqual(len(rebuilt), 16)
                self.assertGreater(len(expected), 8 * max(1, len(rebuilt)))
                budget_refused = []
                with self.assertRaises(RetainedLayoutError) as exhausted:
                    with _inspect_source_paths(context) as (query, _):
                        # Use the actual original issued record, never a fake
                        # source graph or a reduced/artificial policy budget.
                        record = inspection._original(inspection._PATHS[query][0])
                        for number in range(40000):
                            try:
                                self.assertIsNone(
                                    inspection._resolve(
                                        record,
                                        "alias00/absent-" + str(number),
                                    )
                                )
                            except RetainedLayoutError as error:
                                self.assertEqual(
                                    error.code, "retained.layout.metadata_limit"
                                )
                                self.assertLess(
                                    record["resolution_budget"].remaining, 0
                                )
                                budget_refused.append(number)
                                break
                        self.assertEqual(len(budget_refused), 1)
                        # Simulate a canonical malformed-JSON ValueError catch:
                        # swallowing it here must still refuse at factory close.
                self.assertEqual(
                    exhausted.exception.code, "retained.layout.metadata_limit"
                )
                self.assertEqual(len(budget_refused), 1)
            self.assertEqual(
                (inputs / "q00017.txt").read_bytes(), expected["q00017.txt"]
            )
        except BaseException as exc:
            exc.add_note("actual retained many-query fixture: " + str(base))
            raise
        else:
            shutil.rmtree(base)
