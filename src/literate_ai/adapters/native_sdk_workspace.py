"""Live ownership for SDK outputs outside an unchanged source checkout.

This is cooperative filesystem custody, not containment of hostile host code.
The workspace and partial products survive the scope; the execution capability
does not. Existing reservation owners retain substituted or foreign entries.
"""

from __future__ import annotations

import re
import secrets
import unicodedata
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import stat_identity_value
from literate_ai.adapters._write_reservations import (
    WriteReservationTarget,
    acquire_write_reservations,
)
from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_path

_CREATION_KEY = object()
_SLOTS = ("@SDK_SOURCE_ROOT@", "@SDK_WORKSPACE_ROOT@", "@SDK_OUTPUT_ROOT@")
_SLOT_PATTERN = re.compile("|".join(map(re.escape, _SLOTS)))


def _require_slots(value: str) -> None:
    if not isinstance(value, str):
        raise TypeError("SDK command arguments must be strings")
    for slot in _SLOTS:
        value = value.replace(slot, "")
    if "@SDK_" in value:
        raise ValueError("SDK command contains an unknown or incomplete path slot")


def _portable_parts(path: Path) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFC", part).casefold() for part in path.parts)


@dataclass(slots=True)
class _Lifetime:
    active: bool = True


@dataclass(init=False, frozen=True, eq=False)
class NativeSdkBuildWorkspace:
    """An acquired output owner, never a decoded or transferable capability."""

    def __init__(self, *, key, root, parent, reservations, lifetime, node, identity):
        if key is not _CREATION_KEY:
            raise TypeError("SDK workspaces must be acquired through their owner")
        for name, value in (
            ("root", root),
            ("_parent", parent),
            ("_reservations", reservations),
            ("_lifetime", lifetime),
            ("_node", node),
            ("_identity", identity),
        ):
            object.__setattr__(self, name, value)

    def __copy__(self):
        raise TypeError("SDK workspace capabilities cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("SDK workspace capabilities cannot be copied")

    def __reduce_ex__(self, protocol):
        raise TypeError("SDK workspace capabilities cannot be serialized")

    def __getstate__(self):
        raise TypeError("SDK workspace capabilities cannot be serialized")

    @property
    def identity(self):
        self.require_unchanged()
        return self._identity

    def require_unchanged(self) -> None:
        if not self._lifetime.active:
            raise ValueError("SDK workspace execution scope has ended")
        self._reservations.verify_all()
        if directory_node(self.root) != self._node:
            raise ValueError("SDK workspace directory was substituted or changed")
        self._reservations.verify_all()

    def require_for_source(self, source: Path) -> None:
        self.require_unchanged()
        if not source.is_absolute() or ".." in source.parts:
            raise ValueError("SDK source requires a direct absolute path")
        source_node = directory_node(source)
        a, b = _portable_parts(source), _portable_parts(self.root)
        if (
            a == b[: len(a)]
            or b == a[: len(b)]
            or source_node[:2] == self._node[:2]
            or source_node[:2] in {directory_node(p)[:2] for p in self.root.parents}
            or self._node[:2] in {directory_node(p)[:2] for p in source.parents}
        ):
            raise ValueError("SDK source and output workspace must be disjoint")
        self.require_unchanged()

    def require_command_inputs(self, commands, tools, environment) -> None:
        """Only authored argv may contain the three explicit path slots."""
        self.require_unchanged()
        for command in commands:
            if "@SDK_" in command.working_directory:
                raise ValueError("SDK path slots are only supported in command argv")
            for argument in command.argv[1:]:
                _require_slots(argument)
            for item in command.environment:
                if "@SDK_" in item.name or "@SDK_" in item.value:
                    raise ValueError(
                        "SDK path slots are only supported in command argv"
                    )
        for tool in tools.values():
            for argument in tool.command:
                if "@SDK_" in argument:
                    raise ValueError("SDK tool bindings cannot contain path slots")
        for values in (
            environment,
            *(dict(tool.environment) for tool in tools.values()),
        ):
            if any("@SDK_" in key or "@SDK_" in value for key, value in values.items()):
                raise ValueError("SDK environment cannot contain path slots")

    def expand_arguments(
        self, arguments: tuple[str, ...], *, source: Path, sdk_root: str
    ) -> tuple[str, ...]:
        self.require_for_source(source)
        canonical_relative_posix_path(sdk_root, label="SDK output root")
        paths = (source, self.root, self.root / sdk_root)
        replacements = dict(zip(_SLOTS, map(str, paths), strict=True))
        result = []
        for argument in arguments:
            _require_slots(argument)
            result.append(
                _SLOT_PATTERN.sub(lambda match: replacements[match[0]], argument)
            )
        self.require_for_source(source)
        return tuple(result)


@contextmanager
def native_sdk_build_workspace(parent: Path):
    """Acquire a fresh private output directory beneath an existing safe parent.

    The live descriptor-backed marker and directory identity are revalidated by
    the builder. Neither existing directories nor crash markers are adopted.
    Closing the scope retires execution authority and preserves all products.
    """
    parent = Path(parent)
    if not parent.is_absolute() or ".." in parent.parts:
        raise ValueError("SDK workspace parent requires a direct absolute path")
    anchor = directory_node(parent)
    root = parent / ("native-sdk-" + secrets.token_hex(12))
    target = WriteReservationTarget(root / "owner.lock", parent, anchor)
    lifetime = _Lifetime()
    with acquire_write_reservations((target,)) as reservations:
        if not reservations.owns_directory(root):
            raise ValueError("SDK workspace must be created by this reservation owner")
        node = directory_node(root)
        identity = canonical_identity(
            {
                "schema": "literate-ai/native-sdk-build-workspace@1",
                "root": str(root),
                "directory": [
                    stat_identity_value(node[0]),
                    stat_identity_value(node[1]),
                    node[2],
                ],
                "allocation": secrets.token_hex(32),
            }
        )
        scope = NativeSdkBuildWorkspace(
            key=_CREATION_KEY,
            root=root,
            parent=parent,
            reservations=reservations,
            lifetime=lifetime,
            node=node,
            identity=identity,
        )
        scope.require_unchanged()
        # Keep the fresh root and partial products after the scope; release only
        # our unchanged marker. Ownership of this root was proved above.
        reservations.transfer_committed_directories((root,))
        try:
            yield scope
            scope.require_unchanged()
        finally:
            lifetime.active = False
