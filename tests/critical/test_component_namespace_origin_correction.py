"""Owned local lease and modeled ancestry controls; UNRUN, no native qualification."""

from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import component_locks, component_namespace
from literate_ai.adapters.component_locks import ComponentLockStore
from literate_ai.adapters.component_resolution_audits import (
    ComponentResolutionAuditStore,
)
from literate_ai.adapters.project_layout_lease import (
    ProjectLayoutLeaseError,
    current_layout_lease,
    require_layout_lease,
)
from literate_ai.projects import ProjectConfigurationStore, ProjectError


class LayoutLeaseMarkerControls(unittest.TestCase):
    def test_absent_original_git_marker_cannot_adopt_new_directory(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            self.assertFalse((root / ".git").exists())
            with self.assertRaises(ProjectError):
                with ProjectConfigurationStore.layout_lock(root):
                    lease = current_layout_lease(root)
                    (root / ".git").mkdir()
                    with self.assertRaises(ProjectLayoutLeaseError):
                        require_layout_lease(lease, root)
            self.assertIsNone(current_layout_lease(root))

    def test_original_gitfile_same_inode_byte_change_refuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary).resolve()
            root, admin = parent / "project", parent / "admin"
            subprocess.run(
                ["git", "init", "-q", "--separate-git-dir", str(admin), str(root)],
                check=True,
                capture_output=True,
                timeout=15,
            )
            marker = root / ".git"
            before = marker.stat()
            with self.assertRaises(ProjectError):
                with ProjectConfigurationStore.layout_lock(root):
                    lease = current_layout_lease(root)
                    with marker.open("ab") as stream:
                        stream.write(b"\n")
                    after = marker.stat()
                    self.assertEqual(
                        (before.st_dev, before.st_ino, before.st_mode),
                        (after.st_dev, after.st_ino, after.st_mode),
                    )
                    with self.assertRaises(ProjectLayoutLeaseError):
                        require_layout_lease(lease, root)
            self.assertIsNone(current_layout_lease(root))


class ComponentOriginControls(unittest.TestCase):
    def test_genuine_original_field_descriptor_change_never_invoked(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            for cls, args in (
                (ComponentLockStore, (root,)),
                (ComponentResolutionAuditStore, (root, "host")),
            ):
                with self.subTest(store=cls.__name__):
                    store = cls(*args)
                    calls = []

                    def foreign(instance, calls=calls):
                        calls.append(instance)
                        raise AssertionError("foreign descriptor ran")

                    with patch.object(cls, "root", property(foreign), create=True):
                        with self.assertRaises(
                            component_namespace.ComponentNamespaceError
                        ):
                            component_namespace.require_component_physical_current(
                                store
                            )
                    self.assertEqual(calls, [])
                    component_namespace.require_component_physical_current(store)

    def test_modeled_actual_base_change_refuses_before_inherited_descriptor(self):
        # Explicit origin-inventory seam, not a production unknown-type bypass.
        # Equal-layout heap bases allow a real __bases__ change without native code.
        calls = []

        class OriginalBase:
            __slots__ = ()

        class ForeignBase:
            __slots__ = ()

            @property
            def root(self):
                calls.append(self)
                raise AssertionError("foreign inherited descriptor ran")

        class Selected(OriginalBase):
            pass

        store = Selected()
        store.root = object()
        origin = (
            Selected,
            type.__getattribute__(Selected, "__bases__"),
            type.__getattribute__(Selected, "__mro__"),
            tuple((name, Selected.__dict__.get(name)) for name in ("root", "__dict__")),
        )
        with patch.object(component_locks, "_COMPONENT_NAMESPACE_ORIGIN", origin):
            self.assertIs(component_namespace._origin(store)[0], Selected)
            try:
                Selected.__bases__ = (ForeignBase,)
                with self.assertRaisesRegex(
                    component_namespace.ComponentNamespaceError, "ancestry"
                ):
                    component_namespace._origin(store)
                self.assertEqual(calls, [])
            finally:
                Selected.__bases__ = origin[1]
            # Restoring bases recomputes MRO; it does not restore its original
            # admitted tuple object. This original witness must stay refused.
            with self.assertRaisesRegex(
                component_namespace.ComponentNamespaceError, "ancestry"
            ):
                component_namespace._origin(store)

    def test_modeled_mro_change_with_same_direct_bases_refuses(self):
        class OriginalBase:
            __slots__ = ()

        class ForeignBase:
            __slots__ = ()

        class Middle(OriginalBase):
            __slots__ = ()

        class Selected(Middle):
            pass

        store = Selected()
        origin = (
            Selected,
            type.__getattribute__(Selected, "__bases__"),
            type.__getattribute__(Selected, "__mro__"),
            (("__dict__", Selected.__dict__["__dict__"]),),
        )
        with patch.object(component_locks, "_COMPONENT_NAMESPACE_ORIGIN", origin):
            try:
                Middle.__bases__ = (ForeignBase,)
                self.assertIs(type.__getattribute__(Selected, "__bases__"), origin[1])
                with self.assertRaisesRegex(
                    component_namespace.ComponentNamespaceError, "ancestry"
                ):
                    component_namespace._origin(store)
            finally:
                Middle.__bases__ = (OriginalBase,)
