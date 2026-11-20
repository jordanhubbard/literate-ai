"""Original lock selections survive only exact local completion observations.

These are original converted-consumer fixtures with inert authored bindings.
No native execution, provider admission or completed receipt is claimed.
"""

import copy
import os
import pickle
import re
import shutil
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_lock_observation as raw
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    AuthoredRetainedCargoWrapperContext,
    authored_retained_cargo_wrapper_context,
)
from literate_ai.adapters.component_lock_application import project_component_roots
from literate_ai.adapters.component_lock_planning import ComponentCatalogSnapshot
from literate_ai.adapters.component_locks import (
    ComponentLockStore,
    ComponentLockStoreError,
)
from literate_ai.adapters.retained_cargo_wrapper_v2 import (
    retained_cargo_wrapper_context_v2,
)
from tests.critical import test_authored_retained_cargo_wrapper as wrappers
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture
from tests.support.fixtures_test_project_cli import refresh_authority_review

_MATRIX = "LITAI_MATRIX_CELL_ROOT"


class AuthoredConsumerLockObservationTests(unittest.TestCase):
    @contextmanager
    def project(self, *, unlocked=False):
        helper = wrappers.AuthoredRetainedCargoWrapperTests("runTest")
        with patch.dict(os.environ):
            os.environ.pop(_MATRIX, None)
            with helper.fixture() as (old, reviewed):
                candidate = None
                if unlocked:
                    source = project_component_roots(reviewed.project)[0]
                    candidate = source.parent / "unlocked-candidate"
                    shutil.copytree(source, candidate)
                    lock_path = candidate / "component.lock.json"
                    if lock_path.exists():
                        lock_path.unlink()
                    manifest = candidate / "component.md"
                    content, count = re.subn(
                        r"(?m)^version: .+$",
                        "version: 1.0.999",
                        manifest.read_text(),
                        count=1,
                    )
                    self.assertEqual(count, 1)
                    manifest.write_text(content)
                    refresh_authority_review(reviewed.project.root)
                yield old, reviewed, candidate

    def capture(self, reviewed):
        with authored_retained_cargo_wrapper_context(reviewed) as wrapper:
            return raw._capture_authored_consumer_lock_set(wrapper)

    def test_original_raw_files_after_close_never_reopen_authority_or_commands(self):
        # Authored setup replaces review/binding.json; keep source-v2's
        # independently pinned review in a separate actual source fixture.
        with patch.dict(os.environ):
            os.environ.pop(_MATRIX, None)
            with tempfile.TemporaryDirectory() as directory:
                with scratch_review_fixture(
                    Path(directory).resolve(strict=True)
                ) as source_review:
                    with retained_cargo_wrapper_context_v2(source_review) as source:
                        with self.assertRaisesRegex(
                            TypeError, "authored-live-wrapper-required"
                        ):
                            raw._capture_authored_consumer_lock_set(source)
        with self.project() as (_old, reviewed, _candidate):
            observation = self.capture(reviewed)
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with (
                    self.subTest(operation=operation.__name__),
                    self.assertRaises(TypeError),
                ):
                    operation(observation)
            with (
                patch.object(
                    raw, "ComponentLockStore", side_effect=AssertionError("new store")
                ),
                patch(
                    "literate_ai.adapters.component_lock_application._read_current_component_lock",
                    side_effect=AssertionError("new reader"),
                ),
                patch.object(
                    ComponentCatalogSnapshot,
                    "locked_input_closure",
                    side_effect=AssertionError("new closure"),
                ),
                patch("urllib.request.urlopen", side_effect=AssertionError("network")),
                patch("subprocess.run", side_effect=AssertionError("command")),
            ):
                observation.require_original_files()

    def test_new_canonical_record_on_original_unlocked_candidate_refuses(self):
        with self.project(unlocked=True) as (_old, reviewed, candidate):
            observation = self.capture(reviewed)
            original_store = observation._selections[0][0]
            payload = original_store.path.read_bytes()
            (candidate / "component.lock.json").write_bytes(payload)
            with self.assertRaisesRegex(ValueError, "lock-presence-changed"):
                observation.require_original_files()
            self.assertEqual(original_store.path.read_bytes(), payload)

    def test_noncanonical_equal_meaning_selected_bytes_refuse(self):
        with self.project() as (_old, reviewed, _candidate):
            observation = self.capture(reviewed)
            path = observation._selections[0][0].path
            before = path.read_bytes()
            path.write_bytes(before + b" ")
            with self.assertRaises(ComponentLockStoreError):
                observation.require_original_files()
            self.assertEqual(path.read_bytes(), before + b" ")

    def test_same_byte_component_directory_replacement_refuses(self):
        with self.project() as (_old, reviewed, _candidate):
            observation = self.capture(reviewed)
            source = observation._selections[0][0].root
            saved = reviewed.project.root.parent / "original-component"
            source.rename(saved)
            shutil.copytree(saved, source)
            with self.assertRaisesRegex(ValueError, "lock-directory-changed"):
                observation.require_original_files()
            source.rename(reviewed.project.root.parent / "replacement-component")
            saved.rename(source)
            observation.require_original_files()

    def test_matrix_original_effective_file_and_selector_stay_bound(self):
        with self.project() as (_old, reviewed, _candidate):
            matrix = reviewed.project.root.parent / "cell"
            matrix.mkdir()
            payloads = {
                component: (component / "component.lock.json").read_bytes()
                for component in project_component_roots(reviewed.project)
                if (component / "component.lock.json").exists()
            }
            with patch.dict(os.environ, {_MATRIX: str(matrix)}):
                for component, content in payloads.items():
                    store = ComponentLockStore(component)
                    store.storage_root.mkdir(parents=True, exist_ok=True)
                    store.path.write_bytes(content)
                observation = self.capture(reviewed)
                with patch.object(
                    raw, "ComponentLockStore", side_effect=AssertionError("new store")
                ):
                    observation.require_original_files()
                with patch.dict(
                    os.environ, {_MATRIX: str(matrix.parent / "other-cell")}
                ):
                    with self.assertRaisesRegex(ValueError, "matrix-selection-changed"):
                        observation.require_original_files()
                effective = observation._selections[0][0].path
                self.assertTrue(effective.is_relative_to(matrix))
                before = effective.read_bytes()
                effective.write_bytes(before + b" ")
                with self.assertRaises(ComponentLockStoreError):
                    observation.require_original_files()

    def test_final_capture_callback_cannot_change_matrix_selection(self):
        with self.project() as (_old, reviewed, _candidate):
            with authored_retained_cargo_wrapper_context(reviewed) as wrapper:
                original = AuthoredRetainedCargoWrapperContext.require_unchanged
                calls = 0

                def changed(current):
                    nonlocal calls
                    original(current)
                    if current is wrapper:
                        calls += 1
                        if calls == 2:
                            os.environ[_MATRIX] = str(
                                reviewed.project.root.parent / "foreign"
                            )

                with (
                    patch.dict(os.environ),
                    patch.object(
                        AuthoredRetainedCargoWrapperContext,
                        "require_unchanged",
                        changed,
                    ),
                ):
                    with self.assertRaisesRegex(ValueError, "matrix-selection-changed"):
                        raw._capture_authored_consumer_lock_set(wrapper)
                self.assertEqual(calls, 2)

    def test_between_enumerations_new_lock_cannot_escape_final_presence_check(self):
        with self.project(unlocked=True) as (_old, reviewed, candidate):
            observation = self.capture(reviewed)
            original = ComponentLockStore.require_current
            selected = observation._selections[0][0]
            payload = selected.path.read_bytes()

            def changed(store, lock):
                original(store, lock)
                if store is selected:
                    (candidate / "component.lock.json").write_bytes(payload)

            with patch.object(ComponentLockStore, "require_current", changed):
                with self.assertRaisesRegex(ValueError, "lock-presence-changed"):
                    observation.require_original_files()
