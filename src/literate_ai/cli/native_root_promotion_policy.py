"""Explicit original finite native policy input for a new promoted project.

This is authored policy data, never an execution owner, deadline or qualification
claim. Existing promotion commits the canonical value with its original manifest
before lock/audit. Future work revalidates that audited manifest independently.
"""

import json
import os
from pathlib import Path
from types import MethodType

from literate_ai._filesystem import require_safe_directory
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from literate_ai.projects import PinnedInputClosure

from .errors import CliFailure

_CREATION_KEY = object()


def _require(condition):
    if not condition:
        raise CliFailure(
            "promotion.native_root_policy_changed",
            "original native root policy input changed",
        )


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate native policy field")
        value[key] = item
    return value


class PinnedNativeRootPromotionPolicy:
    __slots__ = (
        "_value",
        "_original_value",
        "_canonical",
        "_pins",
        "_guard",
        "_guard_function",
        "_entries",
        "_identity",
        "_attributes",
        "_limits",
    )

    def __init__(self, *, _key, value, pins):
        if (
            _key is not _CREATION_KEY
            or type(value) is not NativeRootRunPolicy
            or type(pins) is not PinnedInputClosure
        ):
            raise TypeError("use read_native_root_promotion_policy")
        self._value, self._canonical = value, canonical_json_bytes(value.to_dict())
        self._original_value = value
        self._pins, self._guard = pins, pins.require_unchanged
        self._guard_function = self._guard.__func__
        self._entries, self._identity = tuple(pins._entries.items()), pins.identity
        self._attributes = frozenset(vars(pins))
        self._limits = (
            pins.maximum_files,
            pins.maximum_file_bytes,
            pins.maximum_total_bytes,
        )

    def __copy__(self):
        raise TypeError("policy input custody cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("policy input custody cannot be copied")

    def __reduce_ex__(self, protocol):
        raise TypeError("policy input custody cannot be serialized")

    def _seal(self):
        pins, guard = self._pins, self._guard
        current = pins.require_unchanged
        _require(
            type(pins) is PinnedInputClosure
            and type(guard) is MethodType
            and type(current) is MethodType
            and guard.__self__ is pins
            and current.__self__ is pins
            and guard.__func__ is self._guard_function
            and current.__func__ is self._guard_function
            and type(pins._entries) is dict
            and frozenset(vars(pins)) == self._attributes
            and tuple(pins._entries.items()) == self._entries
            and PinnedInputClosure.identity.fget(pins) == self._identity
            and (pins.maximum_files, pins.maximum_file_bytes, pins.maximum_total_bytes)
            == self._limits
            and self._value is self._original_value
            and type(self._value) is NativeRootRunPolicy
            and len(self._entries) == 1
            and canonical_json_bytes(
                NativeRootRunPolicy.from_dict(
                    json.loads(
                        self._entries[0][1].content, object_pairs_hook=_unique_object
                    )
                ).to_dict()
            )
            == self._canonical
            and canonical_json_bytes(self._value.to_dict()) == self._canonical
        )

    def require_current(self):
        self._seal()
        pins, guard, value, canonical = (
            self._pins,
            self._guard,
            self._value,
            self._canonical,
        )
        guard()
        _require(
            self._pins is pins
            and self._guard is guard
            and self._value is value
            and self._canonical == canonical
        )
        self._seal()

    @property
    def value(self):
        self.require_current()
        return self._value


def read_native_root_promotion_policy(args):
    selected = getattr(args, "native_root_policy", None)
    if selected is None:
        return None
    if not getattr(args, "project_target", None) and not getattr(
        args, "integrate_project", None
    ):
        raise CliFailure(
            "promotion.native_root_policy_project_required",
            "native root policy requires creation of a promoted project",
        )
    if getattr(args, "plan_native_child_replacement", False) or getattr(
        args, "replace_native_child", None
    ):
        raise CliFailure(
            "promotion.native_root_policy_replacement_unsupported",
            "select native root policy when creating a new promoted project",
        )
    path = Path(selected).absolute()
    if ".." in path.parts:
        raise CliFailure(
            "promotion.native_root_policy_invalid", "native root policy path is unsafe"
        )
    require_safe_directory(path.parent)
    pins = PinnedInputClosure(
        maximum_files=1, maximum_file_bytes=4096, maximum_total_bytes=4096
    )
    try:
        content = pins.pin(
            path, boundary=path.parent, label="explicit native root promotion policy"
        )
        value = NativeRootRunPolicy.from_dict(
            json.loads(content, object_pairs_hook=_unique_object)
        )
    except (OSError, ValueError) as error:
        raise CliFailure(
            "promotion.native_root_policy_invalid",
            "native root policy requires strict bounded policy JSON",
        ) from error
    selected = PinnedNativeRootPromotionPolicy(
        _key=_CREATION_KEY, value=value, pins=pins
    )
    selected.require_current()
    return selected


def commit_native_root_policy_project(selection, staging, destination):
    """Sample original input at existing rename commit; never delete final output.

    No callback/guard follows successful rename: the exact canonical policy is
    already inside the audited manifest. Later edits to the operator input file
    cannot change that committed authority or retroactively reconfigure it.
    """
    if type(selection) is not PinnedNativeRootPromotionPolicy:
        raise TypeError("original native root policy input custody required")
    selection.require_current()
    os.replace(staging, destination)
