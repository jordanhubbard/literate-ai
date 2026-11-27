"""Weak original-oracle observation; no scope revival or execution authority.

Reserve MAXIMUM_ORACLE_STORAGE_BYTES first. The original live owner must bracket
capture with its full oracle byte checks. Only that owner can establish phase
membership and transfer these retained references into charged closing custody.
"""

import math
import os
import types
import weakref
from pathlib import PosixPath

from literate_ai._filesystem import capture_directory_ancestries
from literate_ai.adapters import node_library_acceptance as loader
from literate_ai.adapters.component_acceptance import (
    DeclaredLibraryAcceptanceCase,
    LibraryAcceptance,
)
from literate_ai.adapters.node_sdk_declarations import NodeDeclarationCase
from literate_ai.adapters.node_sdk_verifier_compiler_witness import _require_algorithm
from literate_ai.adapters.node_sdk_verifier_runtime import _finite_metadata
from literate_ai.adapters.node_sdk_verifier_tool_witness import _file_stamp
from literate_ai.contracts.identity import ContentIdentity, HashAlgorithm
from literate_ai.projects import PinnedInputClosure, _PinnedInput

MAXIMUM_ORACLE_STORAGE_BYTES = 128 * 1024 * 1024
_REGISTRY, _REGISTRY_LOCK = loader._LOADED, loader._LOCK
_LSTAT = os.lstat
_ORACLE = loader.NodeLibraryAcceptance
_LOADED = loader._LoadedOracle
_ABSENT = object()
_ORACLE_FIELDS = (
    "component",
    "specification_set_identity",
    "public_interface_identities",
    "import_surface_identity",
    "language",
    "harness_identity",
    "harness_content",
    "cases",
    "esm_harness_identity",
    "esm_harness_content",
    "declaration_cases",
)
_SLOT_NAMES = {
    _ORACLE: _ORACLE_FIELDS,
    DeclaredLibraryAcceptanceCase: (
        "case_id",
        "capability",
        "arguments",
        "expected_result",
    ),
    NodeDeclarationCase: (
        "case_id",
        "capability",
        "cjs_positive",
        "cjs_negative",
        "esm_positive",
        "esm_negative",
        "diagnostic_codes",
    ),
    _PinnedInput: ("path", "boundary", "content", "labels"),
    ContentIdentity: ("algorithm", "digest"),
}
_DICT_NAMES = {
    _LOADED: (
        "original",
        "authority",
        "identity",
        "harness_content",
        "esm_harness_content",
        "verifier_inputs",
        "retained_bytes",
    ),
    PinnedInputClosure: (
        "maximum_files",
        "maximum_file_bytes",
        "maximum_total_bytes",
        "_entries",
        "_total_bytes",
        "_labels",
    ),
}
_CLASSES = (
    *_SLOT_NAMES,
    *_DICT_NAMES,
    LibraryAcceptance,
    loader.NodeLibraryVerifierInputs,
    loader.NodeLibraryDeclarationInputs,
    PosixPath,
)
_FENCES = {
    cls: (
        type.__getattribute__(cls, "__mro__"),
        tuple(
            (base, tuple(type.__getattribute__(base, "__dict__").items()))
            for base in type.__getattribute__(cls, "__mro__")
        ),
    )
    for cls in _CLASSES
}
_SLOTS = {
    cls: tuple(
        next(
            type.__getattribute__(base, "__dict__")[name]
            for base in type.__getattribute__(cls, "__mro__")
            if name in type.__getattribute__(base, "__dict__")
        )
        for name in names
    )
    for cls, names in _SLOT_NAMES.items()
}
_DICTS = {cls: vars(cls)["__dict__"] for cls in _DICT_NAMES}


def _namespace(cls):
    mro, namespaces = _FENCES[cls]
    if type.__getattribute__(cls, "__mro__") is not mro:
        raise ValueError("original oracle storage class changed")
    for base, expected in namespaces:
        current = type.__getattribute__(base, "__dict__")
        if len(current) != len(expected) or any(
            current.get(name, _ABSENT) is not item for name, item in expected
        ):
            raise ValueError("original oracle storage namespace changed")


def _slots(value, cls):
    result = []
    try:
        if type(value) is not cls:
            raise TypeError("oracle observation requires original exact record types")
        _namespace(cls)
        for slot in _SLOTS[cls]:
            result.append(types.MemberDescriptorType.__get__(slot, value, cls))
        return tuple(result)
    finally:
        value = slot = None
        result.clear()


def _dictionary(value, cls):
    data = None
    try:
        if type(value) is not cls:
            raise TypeError(
                "oracle observation requires original exact dictionary storage"
            )
        _namespace(cls)
        data = types.GetSetDescriptorType.__get__(_DICTS[cls], value, cls)
        names = _DICT_NAMES[cls]
        if (
            type(data) is not dict
            or len(data) != len(names)
            or any(type(key) is not str for key in dict.keys(data))
            or any(not dict.__contains__(data, name) for name in names)
        ):
            raise ValueError("original oracle dictionary storage changed")
        return tuple(dict.__getitem__(data, name) for name in names)
    finally:
        value = data = None


def _membership(oracle_ref, loaded_ref, authority_ref=None):
    oracle = loaded = values = original = None
    try:
        if loader._LOADED is not _REGISTRY or loader._LOCK is not _REGISTRY_LOCK:
            raise ValueError("original oracle registry changed")
        oracle, loaded = oracle_ref(), loaded_ref()
        if oracle is None or loaded is None:
            raise ValueError("original oracle observation owner retired")
        with _REGISTRY_LOCK:
            if dict.get(_REGISTRY, id(oracle)) is not loaded:
                raise ValueError("original loaded oracle registry entry changed")
        values = _dictionary(loaded, _LOADED)
        original = values[0]
        if type(original) is not weakref.ReferenceType or original() is not oracle:
            raise ValueError("loaded oracle lost its original root")
        if authority_ref is not None and (
            authority_ref() is None or values[1] is not authority_ref()
        ):
            raise ValueError("original oracle file authority changed")
        return oracle, loaded
    finally:
        oracle = loaded = values = original = None


def _same(before, after):
    try:
        if len(before) != len(after):
            return False
        for index in range(len(before)):
            if before[index] is not after[index]:
                return False
        return True
    finally:
        before = after = None


def _closed_json(root):
    ancestors = set()
    count = 0

    def visit(value, depth):
        nonlocal count
        item = key = None
        try:
            count += 1
            if depth > 64 or count > 65536:
                raise ValueError("oracle JSON metadata exceeds its bound")
            kind = type(value)
            if kind in (str, bool, type(None)):
                return
            if kind is int and -(2**63) <= value < 2**63:
                return
            if kind is float and math.isfinite(value):
                return
            if kind not in (list, dict):
                raise TypeError("oracle metadata requires closed original JSON DATA")
            if id(value) in ancestors:
                raise ValueError("oracle JSON metadata contains a cycle")
            ancestors.add(id(value))
            try:
                if kind is dict:
                    for key, item in dict.items(value):
                        if type(key) is not str:
                            raise TypeError(
                                "oracle JSON metadata requires original string keys"
                            )
                        visit(item, depth + 1)
                else:
                    for item in value:
                        visit(item, depth + 1)
            finally:
                ancestors.remove(id(value))
        finally:
            value = item = key = None

    try:
        visit(root, 0)
    finally:
        root = None


def _declaration_values(values):
    try:
        if (
            type(values[0]) is not str
            or type(values[1]) is not str
            or any(
                type(content) is not bytes or not 1 <= len(content) <= 65536
                for content in values[2:6]
            )
            or type(values[6]) is not tuple
            or len(values[6]) > 1024
            or any(type(code) is not int or not 0 < code <= 65535 for code in values[6])
        ):
            raise TypeError("oracle declaration payload has substituted storage")
    finally:
        values = None


def capture_node_oracle_observation(oracle):
    """Return (conservative charge, sticky guard, release), without byte admission.

    All source-bearing snapshots remain charged until release and until the
    owner's in-flight readers settle. Registry/oracle/authority references are
    fresh native weakrefs without callbacks. No existing weakref callback or
    bound loader/scope method is retained.
    """
    state = {}
    failed = False
    oracle_ref = loaded_ref = authority_ref = None
    oracle_values = loaded_values = pin_values = projection = records = None
    loaded = authority = entries = labels = entry_rows = item = values = None
    metadata_guard = metadata_release = ancestry = None
    try:
        if os.name != "posix" or type(oracle) is not _ORACLE:
            raise TypeError("oracle continuation requires an original POSIX oracle")
        with _REGISTRY_LOCK:
            loaded = dict.get(_REGISTRY, id(oracle))
        if type(loaded) is not _LOADED:
            raise ValueError("oracle continuation requires an original loaded entry")
        oracle_ref, loaded_ref = weakref.ref(oracle), weakref.ref(loaded)
        _membership(oracle_ref, loaded_ref)
        _require_algorithm()
        oracle_values = _slots(oracle, _ORACLE)
        if (
            type(oracle_values[0]) is not str
            or type(oracle_values[4]) is not str
            or type(oracle_values[6]) is not bytes
            or len(oracle_values[6]) > 1024**2
            or type(oracle_values[9]) is not bytes
            or len(oracle_values[9]) > 1024**2
        ):
            raise TypeError("original oracle root has substituted primitives")
        loaded_values = _dictionary(loaded, _LOADED)
        if (
            type(loaded_values[3]) is not bytes
            or len(loaded_values[3]) > 1024**2
            or type(loaded_values[4]) is not bytes
            or len(loaded_values[4]) > 1024**2
            or type(loaded_values[6]) is not int
            or not 0 < loaded_values[6] <= 128 * 1024**2
        ):
            raise TypeError("original oracle loader payload exceeds its profile")
        authority = loaded_values[1]
        if type(authority) is not PinnedInputClosure:
            raise TypeError("oracle file authority is not original pinned storage")
        authority_ref = weakref.ref(authority)
        pin_values = _dictionary(authority, PinnedInputClosure)
        maximum_files, maximum_file, maximum_total, entries, total, labels = pin_values
        if (
            any(
                type(value) is not int
                for value in (maximum_files, maximum_file, maximum_total, total)
            )
            or not 1 <= maximum_files <= 515
            or not 1 <= maximum_file <= 1024**2
            or not maximum_file <= maximum_total <= 36 * 1024**2
            or not 0 < total <= maximum_total
        ):
            raise ValueError("oracle pinned-input limits exceed the original profile")
        if (
            type(entries) is not dict
            or not 1 <= len(entries) <= maximum_files
            or type(labels) is not dict
            or len(labels) > 1024
        ):
            raise ValueError("oracle pinned-input inventory exceeds its bound")
        for name, label in dict.items(labels):
            if (
                type(name) is not str
                or len(name) > 4096
                or type(label) is not tuple
                or len(label) != 3
                or type(label[0]) is not PosixPath
                or type(label[1]) is not PosixPath
                or type(label[2]) is not bytes
                or len(label[2]) > maximum_file
            ):
                raise TypeError("oracle pinned label has substituted storage")
        entry_rows = tuple(dict.items(entries))
        records = []
        projection = [
            tuple(
                value
                for index, value in enumerate(oracle_values)
                if index not in (7, 10)
            ),
            loaded_values[2:5],
            pin_values[:3],
            total,
            labels,
        ]
        files = []
        observed_total = 0
        for key, item in entry_rows:
            values = _slots(item, _PinnedInput)
            path, boundary, content, names = values
            if (
                type(path) is not PosixPath
                or type(boundary) is not PosixPath
                or type(key) is not tuple
                or len(key) != 2
                or any(type(part) is not PosixPath for part in key)
                or type(content) is not bytes
                or len(content) > maximum_file
                or type(names) is not tuple
                or len(names) > 1024
                or any(type(name) is not str for name in names)
            ):
                raise ValueError("oracle pinned entry has substituted storage")
            _namespace(PosixPath)
            if key != (path, boundary):
                raise ValueError("oracle pinned entry lost its original namespace")
            filename = str(path)
            if not 1 <= len(filename) <= 4096 or len(path.parts) > 65:
                raise ValueError("oracle file observation exceeds its path bound")
            records.append((item, _PinnedInput, values))
            projection.extend((key, values))
            files.append((path, filename, _file_stamp(_LSTAT(filename))))
            observed_total += len(content)
        if observed_total != total:
            raise ValueError("oracle pinned content differs from its accounted total")
        for index, cls, maximum in (
            (7, DeclaredLibraryAcceptanceCase, 64),
            (10, NodeDeclarationCase, 128),
        ):
            cases = oracle_values[index]
            if type(cases) is not tuple or not 1 <= len(cases) <= maximum:
                raise ValueError("oracle case inventory exceeds its original profile")
            for item in cases:
                values = _slots(item, cls)
                if type(values[0]) is not str or type(values[1]) is not str:
                    raise TypeError("oracle case identifiers require original strings")
                if cls is DeclaredLibraryAcceptanceCase:
                    if type(values[2]) is not list:
                        raise TypeError(
                            "oracle runtime arguments require an original list"
                        )
                    _closed_json(values[2])
                    _closed_json(values[3])
                else:
                    _declaration_values(values)
                records.append((item, cls, values))
                projection.append(values)
        identities = [oracle_values[index] for index in (1, 3, 5, 8)]
        if type(oracle_values[2]) is not tuple or len(oracle_values[2]) > 1024:
            raise ValueError("oracle interface metadata exceeds its bound")
        identities.extend(oracle_values[2])
        identities.append(loaded_values[2])
        for item in identities:
            values = _slots(item, ContentIdentity)
            if (
                values[0] is not HashAlgorithm.SHA256
                or type(values[1]) is not str
                or len(values[1]) != 64
            ):
                raise ValueError("oracle identity has substituted storage")
            records.append((item, ContentIdentity, values))
        inputs = loaded_values[5]
        if type(inputs) is not loader.NodeLibraryVerifierInputs:
            raise TypeError("oracle payload inputs are not original typed storage")
        _namespace(loader.NodeLibraryVerifierInputs)
        input_values = tuple(tuple.__getitem__(inputs, index) for index in range(6))
        if type(input_values[0]) is not str or any(
            type(content) is not bytes for content in input_values[1:5]
        ):
            raise TypeError("oracle loader payload has substituted primitives")
        declarations = input_values[5]
        if type(declarations) is not tuple or not 1 <= len(declarations) <= 128:
            raise ValueError("oracle payload declarations exceed their bound")
        projection.append(input_values[:5])
        for item in declarations:
            if type(item) is not loader.NodeLibraryDeclarationInputs:
                raise TypeError("oracle declaration input storage changed")
            _namespace(loader.NodeLibraryDeclarationInputs)
            values = tuple(tuple.__getitem__(item, index) for index in range(7))
            _declaration_values(values)
            projection.append(values)
        metadata_guard, metadata_release, source_estimate = _finite_metadata(
            tuple(projection), _with_release=True
        )
        charge = 32 * 1024**2 + source_estimate
        if charge > MAXIMUM_ORACLE_STORAGE_BYTES:
            raise ValueError("oracle observation exceeds its reserved storage")
        ancestry = capture_directory_ancestries(
            tuple(path.parent for path, _name, _stamp in files)
        )
        state.update(
            oracle_values=oracle_values,
            loaded_values=loaded_values[2:],
            pin_values=pin_values,
            entries=entry_rows,
            records=tuple(records),
            files=tuple(files),
            metadata=metadata_guard,
            metadata_release=metadata_release,
            ancestry=ancestry,
        )

        def require_original():
            nonlocal failed
            current_oracle = current_loaded = current_authority = view = current = (
                value
            ) = before = None
            try:
                if failed or not state:
                    raise ValueError(
                        "oracle continuation observation retired or failed"
                    )
                view = state
                current_oracle, current_loaded = _membership(
                    oracle_ref, loaded_ref, authority_ref
                )
                _require_algorithm()
                if not _same(view["oracle_values"], _slots(current_oracle, _ORACLE)):
                    raise ValueError("original oracle root storage changed")
                current = _dictionary(current_loaded, _LOADED)
                if not _same(view["loaded_values"], current[2:]):
                    raise ValueError("original loaded oracle storage changed")
                current_authority = authority_ref()
                if not _same(
                    view["pin_values"],
                    _dictionary(current_authority, PinnedInputClosure),
                ):
                    raise ValueError("original oracle authority storage changed")
                current = tuple(dict.items(view["pin_values"][3]))
                if len(current) != len(view["entries"]) or any(
                    a[0] is not b[0] or a[1] is not b[1]
                    for a, b in zip(current, view["entries"], strict=True)
                ):
                    raise ValueError("original oracle pinned membership changed")
                for value, cls, before in view["records"]:
                    if not _same(before, _slots(value, cls)):
                        raise ValueError("original oracle nested storage changed")
                _namespace(loader.NodeLibraryVerifierInputs)
                _namespace(loader.NodeLibraryDeclarationInputs)
                _namespace(PosixPath)
                view["metadata"]()
                view["ancestry"]()
                for path, filename, stamp in view["files"]:
                    if str(path) != filename or _file_stamp(_LSTAT(filename)) != stamp:
                        raise ValueError("original oracle file observation changed")
                view["ancestry"]()
                _membership(oracle_ref, loaded_ref, authority_ref)
            except BaseException:
                failed = True
                raise
            finally:
                current_oracle = current_loaded = current_authority = view = current = (
                    value
                ) = before = None

        def release():
            nonlocal failed
            try:
                failed = True
                if state:
                    state["metadata_release"]()
            finally:
                state.clear()

        require_original()
        return charge, require_original, release
    except BaseException:
        if metadata_release is not None:
            metadata_release()
        state.clear()
        raise
    finally:
        oracle = loaded = authority = oracle_values = loaded_values = pin_values = None
        entries = labels = entry_rows = item = values = projection = records = None
        files = path = boundary = content = names = key = cases = inputs = (
            input_values
        ) = declarations = None
        identities = None
        name = label = None
        metadata_guard = metadata_release = ancestry = None
