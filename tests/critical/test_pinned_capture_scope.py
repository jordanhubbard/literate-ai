"""Native POSIX capture controls; zero-ID facades are not platform qualification."""

import errno
import hashlib
import os
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai import _filesystem as filesystem
from literate_ai import projects
from literate_ai.adapters import component_lock_planning as planning
from literate_ai.contracts.identity import (
    ContentIdentity,
    ContentReference,
    canonical_identity,
)


@unittest.skipUnless(
    projects._pinned_read_batch_supported(), "requires native POSIX dirfd"
)
class PinnedCaptureScopeTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="pinned-capture-scope-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.path = self.root / "a/b/value.txt"
        self.path.parent.mkdir(parents=True)
        self.content = b"capture data\n"
        self.path.write_bytes(self.content)
        self.closure = projects.PinnedInputClosure()
        # Wrappers below retain REAL native operations; replacing os.open/stat
        # otherwise changes their identity in supports_dir_fd. No Windows proof.
        self.enterContext(
            mock.patch.object(
                projects, "_pinned_read_batch_supported", return_value=True
            )
        )

    def reference(self, path=None):
        path = path or self.path
        return ContentReference(
            "specification",
            path.relative_to(self.root).as_posix(),
            ContentIdentity.parse_uri(
                "sha256:" + hashlib.sha256(self.content).hexdigest()
            ),
        )

    def pin(self, capture, *, path=None, label="capture"):
        return planning._pin_catalog_reference(
            self.closure,
            self.root,
            self.reference(path),
            boundary=self.root,
            label=label,
            component=False,
            capture=capture,
        )

    def test_capture_matches_ordinary_bytes_identity_and_quota_accounting(self):
        ordinary = projects.PinnedInputClosure()
        expected = ordinary.pin(
            self.path,
            boundary=self.root,
            label="capture",
            expected_identity=self.reference().identity,
        )
        with planning._reference_capture_scope(self.closure) as capture:
            self.assertEqual(self.pin(capture), expected)
            first = dict(capture.descriptors)
            self.assertEqual(self.pin(capture), expected)
            self.assertEqual(dict(capture.descriptors), first)
            self.assertEqual(self.closure.identity, ordinary.identity)
            self.assertEqual(self.closure.total_bytes, len(self.content))
        for descriptor in first.values():
            with self.assertRaises(OSError) as caught:
                os.fstat(descriptor)
            self.assertEqual(caught.exception.errno, errno.EBADF)
        self.closure.require_unchanged()

    def test_component_capture_uses_real_contained_catalog_placement(self):
        from tests.support.fixtures_test_retained_harness_receipts import _adapter

        root = self.root / "contained"
        _adapter().initialize(root, empty=True, source_intelligence_provider="none")
        context = projects.ProjectConfigurationStore.context(root)
        self.assertEqual(context.framework_root, root / "litai")
        for kind, uri in (
            ("workflow", "workflows/production/staging/dev/workflow.md"),
            ("routing-policy", "routing/production/staging/dev/routing.json"),
            (
                "specification-to-source-skill",
                "skills/specification-to-source/python-portable-application/SKILL.md",
            ),
        ):
            with self.subTest(kind=kind):
                content = context.framework_path(uri).read_bytes()
                reference = ContentReference(
                    kind,
                    uri,
                    ContentIdentity.parse_uri(
                        "sha256:" + hashlib.sha256(content).hexdigest()
                    ),
                )
                ordinary = projects.PinnedInputClosure()
                captured = projects.PinnedInputClosure()
                arguments = dict(
                    boundary=root,
                    label="contained-reference",
                    component=True,
                )
                expected = planning._pin_catalog_reference(
                    ordinary, root, reference, capture=None, **arguments
                )
                with planning._reference_capture_scope(captured) as capture:
                    self.assertEqual(
                        planning._pin_catalog_reference(
                            captured, root, reference, capture=capture, **arguments
                        ),
                        expected,
                    )
                self.assertEqual(expected, content)
                self.assertEqual(captured.identity, ordinary.identity)
                self.assertEqual(captured.total_bytes, ordinary.total_bytes)
                captured.require_unchanged()
                self.assertFalse((root / uri).exists())
                target = context.framework_path(uri)
                outside = self.root / f"foreign-{kind}"
                outside.write_bytes(content)
                target.unlink()
                target.symlink_to(outside)
                errors = []
                try:
                    for direct in (False, True):
                        closure = projects.PinnedInputClosure()
                        with self.assertRaises(
                            (
                                planning.ComponentLockPlanningError,
                                projects.PinnedInputClosureError,
                            )
                        ) as caught:
                            with planning._reference_capture_scope(closure) as scope:
                                planning._pin_catalog_reference(
                                    closure,
                                    root,
                                    reference,
                                    capture=scope if direct else None,
                                    **arguments,
                                )
                        errors.append(caught.exception.code)
                    self.assertEqual(errors, ["component_lock.content_unsafe"] * 2)
                finally:
                    target.unlink()
                    target.write_bytes(content)

    def test_byte_replacement_and_same_byte_rewrite_during_read_refuse_admission(self):
        read = os.read
        for replace in (False, True):
            fired = []

            def changed(descriptor, count, *, _fired=fired, _replace=replace):
                result = read(descriptor, count)
                if not _fired:
                    _fired.append(True)
                    before = self.path.stat()
                    if _replace:
                        temporary = self.path.with_name("replacement")
                        temporary.write_bytes(self.content)
                        temporary.replace(self.path)
                    else:
                        self.path.write_bytes(self.content)
                    os.utime(self.path, ns=(before.st_atime_ns, before.st_mtime_ns))
                return result

            with self.subTest(replace=replace), mock.patch.object(os, "read", changed):
                with self.assertRaises(projects.PinnedInputClosureError) as caught:
                    with planning._reference_capture_scope(self.closure) as capture:
                        self.pin(capture)
                self.assertEqual(caught.exception.code, "inputs.closure_replaced")
            self.assertEqual(fired, [True])
            self.assertEqual(self.closure.file_count, 0)

    def test_redirected_original_ancestor_cannot_be_reused_or_adopted(self):
        with self.assertRaises(planning.ComponentLockPlanningError):
            with planning._reference_capture_scope(self.closure) as capture:
                self.pin(capture)
                descriptors = dict(capture.descriptors)
                original = self.root / "a"
                retained = self.root / "retained"
                original.rename(retained)
                original.symlink_to(retained, target_is_directory=True)
                self.pin(capture, label="must-not-be-admitted")
        self.assertEqual(self.closure.file_count, 1)
        self.assertNotIn("must-not-be-admitted", self.closure._labels)
        with self.assertRaises(planning.ComponentLockPlanningError):
            self.pin(capture, label="retired")
        for descriptor in descriptors.values():
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_missing_symlink_directory_and_fifo_keep_path_error_policy(self):
        cases = ("missing", "symlink", "directory", "fifo")
        for kind in cases:
            path = self.root / kind
            if kind == "symlink":
                path.symlink_to(self.path)
            elif kind == "directory":
                path.mkdir()
            elif kind == "fifo":
                os.mkfifo(path)
            errors = []
            for direct in (False, True):
                # This private seam precedes the catalog owner's existing
                # PinnedInputClosureError -> ComponentLockPlanningError wrapper.
                with self.assertRaises(
                    (
                        planning.ComponentLockPlanningError,
                        projects.PinnedInputClosureError,
                    )
                ) as caught:
                    if direct:
                        with planning._reference_capture_scope(self.closure) as capture:
                            self.pin(capture, path=path, label=kind)
                    else:
                        planning._resolve_path(self.root, path.name, boundary=self.root)
                errors.append(caught.exception.code)
            self.assertEqual(errors[0], errors[1], kind)
        self.assertEqual(self.closure.file_count, 0)

    def test_limits_and_expected_hash_keep_common_admission(self):
        self.closure.maximum_file_bytes = 2
        with self.assertRaises(projects.PinnedInputClosureError) as caught:
            with planning._reference_capture_scope(self.closure) as capture:
                self.pin(capture)
        self.assertEqual(caught.exception.code, "inputs.closure_file_size_limit")
        self.assertEqual(self.closure.file_count, 0)
        self.closure.maximum_file_bytes = 1024
        wrong = ContentReference(
            "specification", "a/b/value.txt", canonical_identity("wrong")
        )
        with self.assertRaises(projects.PinnedInputClosureError) as caught:
            with planning._reference_capture_scope(self.closure) as capture:
                planning._pin_catalog_reference(
                    self.closure,
                    self.root,
                    wrong,
                    boundary=self.root,
                    label="wrong",
                    component=False,
                    capture=capture,
                )
        self.assertEqual(caught.exception.code, "inputs.closure_identity_changed")
        self.assertEqual(self.closure.file_count, 0)

    def test_unknown_file_id_declines_before_fast_payload_and_keeps_old_pin(self):
        stat = os.stat

        def unknown(path, *args, **kwargs):
            result = stat(path, *args, **kwargs)
            if str(path) == "value.txt" and kwargs.get("dir_fd") is not None:
                return SimpleNamespace(
                    **{
                        key: 0 if key == "st_ino" else getattr(result, key)
                        for key in dir(result)
                        if key.startswith("st_")
                    }
                )
            return result

        with (
            mock.patch.object(os, "stat", unknown),
            mock.patch.object(
                os, "read", side_effect=AssertionError("fast payload ran")
            ),
        ):
            with planning._reference_capture_scope(self.closure) as capture:
                self.assertEqual(self.pin(capture), self.content)
        self.assertEqual(self.closure.file_count, 1)

    def test_partial_unknown_directory_id_closes_new_fds_and_preserves_originals(self):
        parent = self.root / "new/unknown"
        parent.mkdir(parents=True)
        target = parent.stat()
        fstat, opened, closed = os.fstat, [], []
        open_directory = filesystem._open_readonly_directory_component
        close = os.close

        def observed(parent_fd, name):
            descriptor, value = open_directory(parent_fd, name)
            opened.append(descriptor)
            return descriptor, value

        def unknown(descriptor):
            result = fstat(descriptor)
            if (result.st_dev, result.st_ino) == (target.st_dev, target.st_ino):
                return SimpleNamespace(
                    st_dev=result.st_dev, st_ino=0, st_mode=result.st_mode
                )
            return result

        def closed_fd(descriptor):
            close(descriptor)
            closed.append(descriptor)

        with filesystem._ReadonlyDirectoryScope(reserved_descriptors=2) as capture:
            self.assertTrue(capture.include((self.path.parent,)))
            originals = dict(capture.descriptors)
            with (
                mock.patch.object(
                    filesystem, "_open_readonly_directory_component", observed
                ),
                mock.patch.object(os, "fstat", unknown),
                mock.patch.object(os, "close", closed_fd),
            ):
                self.assertFalse(capture.include((parent,)))
                self.assertEqual(dict(capture.descriptors), originals)
                self.assertEqual(set(opened), set(closed))
                for descriptor in opened:
                    with self.assertRaises(OSError):
                        fstat(descriptor)
                capture.current()
            for descriptor in originals.values():
                fstat(descriptor)

    def test_capacity_and_legacy_fallback_stay_within_64_owned_handles(self):
        opened, peak = set(), [0]
        open_file, close = os.open, os.close

        def tracked_open(*args, **kwargs):
            descriptor = open_file(*args, **kwargs)
            opened.add(descriptor)
            peak[0] = max(peak[0], len(opened))
            return descriptor

        def tracked_close(descriptor):
            close(descriptor)
            opened.discard(descriptor)

        paths = []
        for index in range(70):
            path = self.root / str(index) / "value.txt"
            path.parent.mkdir()
            path.write_bytes(self.content)
            paths.append(path)
        with (
            mock.patch.object(os, "open", tracked_open),
            mock.patch.object(os, "close", tracked_close),
        ):
            with planning._reference_capture_scope(self.closure) as capture:
                for index, path in enumerate(paths):
                    self.assertEqual(
                        self.pin(capture, path=path, label=str(index)), self.content
                    )
                self.assertLessEqual(len(capture.descriptors), 62)
            self.assertEqual(opened, set())
        self.assertLessEqual(peak[0], 64)
        self.assertGreaterEqual(peak[0], 62)
        self.assertEqual(self.closure.file_count, len(paths))
        self.closure.require_unchanged()

    def test_custom_reader_retires_held_view_before_dispatch(self):
        read = self.closure._read
        with planning._reference_capture_scope(self.closure) as capture:
            self.pin(capture)
            descriptors = dict(capture.descriptors)

            def custom(*args, **kwargs):
                self.assertTrue(capture.closed)
                for descriptor in descriptors.values():
                    with self.assertRaises(OSError):
                        os.fstat(descriptor)
                return read(*args, **kwargs)

            self.closure._read = custom
            self.assertEqual(self.pin(capture, label="custom"), self.content)
        self.assertEqual(self.closure.file_count, 1)

    def test_limit_drift_during_final_directory_check_withholds_capture(self):
        read, stat = os.read, os.stat
        payload, altered = [], []

        def reading(*args):
            payload.append(True)
            return read(*args)

        def changed(path, *args, **kwargs):
            result = stat(path, *args, **kwargs)
            if (
                payload
                and not altered
                and str(path) == "b"
                and kwargs.get("dir_fd") is not None
            ):
                altered.append(True)
                self.closure.maximum_file_bytes += 1
            return result

        with (
            mock.patch.object(os, "read", reading),
            mock.patch.object(os, "stat", changed),
        ):
            with self.assertRaises(projects.PinnedInputClosureError) as caught:
                with planning._reference_capture_scope(self.closure) as capture:
                    self.pin(capture)
        self.assertEqual(altered, [True])
        self.assertEqual(caught.exception.code, "inputs.closure_changed")
        self.assertEqual(self.closure.file_count, 0)

    def test_direct_pin_keeps_expected_identity_from_before_read(self):
        expected = canonical_identity("original expectation differs from payload")
        reference = ContentReference("specification", "a/b/value.txt", expected)
        correct = self.reference().identity.digest
        read = os.read

        def changed(*args):
            result = read(*args)
            object.__setattr__(expected, "digest", correct)
            return result

        with mock.patch.object(os, "read", changed):
            with self.assertRaises(projects.PinnedInputClosureError) as caught:
                with planning._reference_capture_scope(self.closure) as capture:
                    planning._pin_catalog_reference(
                        self.closure,
                        self.root,
                        reference,
                        boundary=self.root,
                        label="original",
                        component=False,
                        capture=capture,
                    )
        self.assertEqual(caught.exception.code, "inputs.closure_identity_changed")
        self.assertEqual(expected.digest, correct)
        self.assertEqual(self.closure.file_count, 0)

    def test_custom_flavor_contribution_is_not_dereferenced_until_view_retires(self):
        from tests.smoke.test_node_sdk_cross_language import with_provider

        _, snapshot, _ = with_provider(self.root / "catalog")
        flavor = snapshot._catalog._flavors[0]
        touched = []
        reference = self.reference()

        class CustomContribution:
            @property
            def content(self):
                touched.append(capture.closed)
                return reference

        with planning._reference_capture_scope(self.closure) as capture:
            self.assertTrue(capture.include((self.path.parent,)))
            descriptors = dict(capture.descriptors)
            planning._prepare_capture_flavor(capture, self.closure, flavor)
            self.assertFalse(capture.closed)
            original = flavor.definition.contributions
            object.__setattr__(
                flavor.definition, "contributions", (*original, CustomContribution())
            )
            planning._prepare_capture_flavor(capture, self.closure, flavor)
            self.assertTrue(capture.closed)
            self.assertEqual(touched, [])
            observed = tuple(item.content for item in flavor.definition.contributions)
            self.assertEqual(observed[-1], reference)
            self.assertEqual(touched, [True])
            for descriptor in descriptors.values():
                with self.assertRaises(OSError):
                    os.fstat(descriptor)

    def test_manifest_read_rechecks_custom_contribution_before_actual_loop_getter(self):
        from tests.smoke.test_node_sdk_cross_language import with_provider

        _, snapshot, _ = with_provider(self.root / "catalog")
        require = planning._require_inputs_unchanged
        arguments = {}

        def observed(**kwargs):
            arguments.update(kwargs)
            return require(**kwargs)

        with mock.patch.object(planning, "_require_inputs_unchanged", observed):
            snapshot.require_unchanged()
        flavor = arguments["flavors"][0]
        reference = ContentReference(
            "specification", flavor.path.name, flavor.source_identity
        )
        views, changed, live_at_read, touched, descriptors = [], [], [], [], {}
        scope, open_file = planning._reference_capture_scope, Path.open
        original_contributions = flavor.definition.contributions

        @contextmanager
        def tracking(closure):
            with scope(closure) as capture:
                views.append(capture)
                yield capture

        class CustomContribution:
            @property
            def content(self):
                touched.append(views[-1].closed)
                return reference

        class ManifestStream:
            def __init__(self, stream):
                self.stream = stream

            def __enter__(self):
                self.stream.__enter__()
                return self

            def read(self, count):
                result = self.stream.read(count)
                if not changed:
                    changed.append(True)
                    live_at_read.append(not views[-1].closed)
                    descriptors.update(views[-1].descriptors)
                    object.__setattr__(
                        flavor.definition,
                        "contributions",
                        (*original_contributions, CustomContribution()),
                    )
                return result

            def __exit__(self, *args):
                return self.stream.__exit__(*args)

        def opening(path, *args, **kwargs):
            result = open_file(path, *args, **kwargs)
            if Path(path) == flavor.path and views and not changed:
                return ManifestStream(result)
            return result

        # Actual catalog capture loop with synthetic malformed metadata. This
        # proves retirement/dispatch ordering, not acceptance of that metadata.
        with (
            mock.patch.object(planning, "_reference_capture_scope", tracking),
            mock.patch.object(Path, "open", opening),
        ):
            require(**arguments)
        self.assertEqual(changed, [True])
        self.assertEqual(live_at_read, [True])
        self.assertEqual(touched, [True])
        self.assertTrue(descriptors)
        for descriptor in descriptors.values():
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_unsupported_file_id_does_not_rebind_expected_identity_on_fallback(self):
        expected = canonical_identity("original expectation differs from payload")
        reference = ContentReference("specification", "a/b/value.txt", expected)
        correct, changed = self.reference().identity.digest, []
        stat = os.stat

        def unknown(path, *args, **kwargs):
            value = stat(path, *args, **kwargs)
            if str(path) == "value.txt" and kwargs.get("dir_fd") is not None:
                changed.append(True)
                object.__setattr__(expected, "digest", correct)
                return SimpleNamespace(
                    **{
                        key: 0 if key == "st_ino" else getattr(value, key)
                        for key in dir(value)
                        if key.startswith("st_")
                    }
                )
            return value

        with mock.patch.object(os, "stat", unknown):
            with self.assertRaises(projects.PinnedInputClosureError) as caught:
                with planning._reference_capture_scope(self.closure) as capture:
                    planning._pin_catalog_reference(
                        self.closure,
                        self.root,
                        reference,
                        boundary=self.root,
                        label="original",
                        component=False,
                        capture=capture,
                    )
        self.assertEqual(changed, [True])
        self.assertEqual(caught.exception.code, "inputs.closure_identity_changed")
        self.assertEqual(self.closure.file_count, 0)

    def test_swallowed_payload_reentry_never_opens_or_admits_and_closes_handles(self):
        read, open_file = os.read, os.open
        for action in ("include", "capture", "close"):
            fired, denied, accepted, payload, new_opens = [], [], [], [], []
            self.closure = projects.PinnedInputClosure()
            with self.subTest(action=action):
                with self.assertRaises(
                    (
                        projects.PinnedInputClosureError,
                        planning.ComponentLockPlanningError,
                    )
                ):
                    with planning._reference_capture_scope(self.closure) as capture:
                        self.assertTrue(capture.include((self.path.parent,)))
                        descriptors = dict(capture.descriptors)

                        def reading(
                            descriptor,
                            count,
                            *,
                            _action=action,
                            _fired=fired,
                            _denied=denied,
                            _accepted=accepted,
                            _payload=payload,
                            _capture=capture,
                        ):
                            result = read(descriptor, count)
                            _payload.append(descriptor)
                            if not _fired:
                                _fired.append(True)
                                try:
                                    if _action == "include":
                                        _capture.include((self.root,))
                                    elif _action == "close":
                                        _capture.close()
                                    else:
                                        with _capture.capture(self.path.parent):
                                            _accepted.append("nested payload entered")
                                except filesystem.UnsafeFilesystemPathError:
                                    _denied.append(True)
                                else:
                                    _accepted.append("reentry returned")
                            return result

                        def opening(*args, _fired=fired, _opens=new_opens, **kwargs):
                            if _fired:
                                _opens.append(True)
                            return open_file(*args, **kwargs)

                        with (
                            mock.patch.object(os, "read", reading),
                            mock.patch.object(os, "open", opening),
                        ):
                            self.pin(capture)
                self.assertEqual(fired, [True])
                self.assertEqual(denied, [True])
                self.assertEqual(accepted, [])
                self.assertEqual(new_opens, [])
                self.assertEqual(self.closure.file_count, 0)
                for descriptor in (*descriptors.values(), *payload):
                    with self.assertRaises(OSError):
                        os.fstat(descriptor)

    def _assert_foreign_owner_substitution(self, kind):
        foreign_path = self.root / "foreign"
        foreign_path.mkdir()
        read, substituted, denied = os.read, [], []
        with filesystem._ReadonlyDirectoryScope(reserved_descriptors=2) as foreign:
            self.assertTrue(foreign.include((foreign_path,)))
            foreign_entry = foreign._entries[str(foreign_path)]
            foreign_descriptors = dict(foreign.descriptors)

            def changed(*args):
                result = read(*args)
                if not substituted:
                    substituted.append(True)
                    if kind == "index":
                        capture._entries[str(self.path.parent)] = foreign_entry
                    else:
                        capture._stack = foreign._stack
                        for name in ("_original_stack", "closed", "failed"):
                            try:
                                object.__setattr__(capture, name, foreign._stack)
                            except AttributeError:
                                denied.append(name)
                return result

            with self.assertRaises(
                (projects.PinnedInputClosureError, planning.ComponentLockPlanningError)
            ):
                with planning._reference_capture_scope(self.closure) as capture:
                    self.assertTrue(capture.include((self.path.parent,)))
                    original_descriptors = dict(capture.descriptors)
                    with mock.patch.object(os, "read", changed):
                        self.pin(capture)
            self.assertEqual(substituted, [True])
            self.assertEqual(
                denied,
                ["_original_stack", "closed", "failed"] if kind == "stack" else [],
            )
            self.assertEqual(self.closure.file_count, 0)
            self.assertEqual(dict(foreign.descriptors), foreign_descriptors)
            foreign.current()
            for descriptor in original_descriptors.values():
                with self.assertRaises(OSError):
                    os.fstat(descriptor)
            for descriptor in foreign_descriptors.values():
                os.fstat(descriptor)

    def test_index_substitution_withholds_capture_and_preserves_foreign_owner(self):
        self._assert_foreign_owner_substitution("index")

    def test_cleanup_owner_substitution_refuses_and_preserves_foreign_descriptors(self):
        self._assert_foreign_owner_substitution("stack")

    def test_file_io_failure_never_retries_legacy_and_closes_owned_handles(self):
        open_file, close = os.open, os.close
        for operation in ("open", "close"):
            payload, reached = [], []

            def opening(
                path,
                *args,
                _operation=operation,
                _payload=payload,
                _reached=reached,
                **kwargs,
            ):
                if str(path) == "value.txt":
                    _reached.append(True)
                    if _operation == "open":
                        raise OSError("owned file open failure")
                    descriptor = open_file(path, *args, **kwargs)
                    _payload.append(descriptor)
                    return descriptor
                return open_file(path, *args, **kwargs)

            def closing(descriptor, *, _payload=payload):
                close(descriptor)
                if descriptor in _payload:
                    raise OSError("owned file close failure")

            with self.subTest(operation=operation):
                with self.assertRaises(projects.PinnedInputClosureError) as caught:
                    with planning._reference_capture_scope(self.closure) as capture:
                        self.assertTrue(capture.include((self.path.parent,)))
                        descriptors = dict(capture.descriptors)
                        with (
                            mock.patch.object(os, "open", opening),
                            mock.patch.object(os, "close", closing),
                            mock.patch.object(
                                Path,
                                "open",
                                side_effect=AssertionError("legacy payload retried"),
                            ),
                        ):
                            self.pin(capture)
                self.assertEqual(
                    caught.exception.code, "component_lock.content_unavailable"
                )
                self.assertEqual(reached, [True])
                self.assertEqual(self.closure.file_count, 0)
                for descriptor in (*descriptors.values(), *payload):
                    with self.assertRaises(OSError):
                        os.fstat(descriptor)

    def test_partial_directory_open_failure_is_sticky_and_closes_handles(self):
        open_file = os.open
        staged, failed, denied, partial_closed = [], [], [], []

        def opening(path, *args, **kwargs):
            if str(path) == "b":
                raise OSError("owned directory open failure")
            descriptor = open_file(path, *args, **kwargs)
            staged.append(descriptor)
            return descriptor

        with self.assertRaises(filesystem.UnsafeFilesystemPathError):
            with filesystem._ReadonlyDirectoryScope(reserved_descriptors=2) as capture:
                self.assertTrue(capture.include((self.root,)))
                descriptors = dict(capture.descriptors)
                with mock.patch.object(os, "open", opening):
                    try:
                        capture.include((self.path.parent,))
                    except OSError as error:
                        failed.append(str(error))
                for descriptor in staged:
                    try:
                        os.fstat(descriptor)
                    except OSError:
                        partial_closed.append(descriptor)
                try:
                    capture.include((self.root,))
                except filesystem.UnsafeFilesystemPathError:
                    denied.append(True)
        self.assertEqual(failed, ["owned directory open failure"])
        self.assertEqual(denied, [True])
        self.assertEqual(staged, partial_closed)
        for descriptor in descriptors.values():
            with self.assertRaises(OSError):
                os.fstat(descriptor)

    def test_swallowed_reentry_cannot_restore_original_scope(self):
        stat, intercepted, denied, accepted, failed = os.stat, [], [], [], []

        def reentered(path, *args, **kwargs):
            if not intercepted:
                intercepted.append(True)
                try:
                    capture.include((self.root,))
                except filesystem.UnsafeFilesystemPathError:
                    denied.append(True)
                else:
                    accepted.append(True)
            return stat(path, *args, **kwargs)

        with self.assertRaises(filesystem.UnsafeFilesystemPathError):
            with filesystem._ReadonlyDirectoryScope(reserved_descriptors=2) as capture:
                self.assertTrue(capture.include((self.root,)))
                descriptors = dict(capture.descriptors)
                with mock.patch.object(os, "stat", reentered):
                    try:
                        capture.current(self.root)
                    except filesystem.UnsafeFilesystemPathError:
                        failed.append(True)
        self.assertEqual(intercepted, [True])
        self.assertEqual(denied, [True])
        self.assertEqual(accepted, [])
        self.assertEqual(failed, [True])
        for descriptor in descriptors.values():
            with self.assertRaises(OSError):
                os.fstat(descriptor)


if __name__ == "__main__":
    unittest.main()
