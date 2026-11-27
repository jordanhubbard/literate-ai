"""Original compiler storage observations; neither byte admission nor authority.

The fixed capture owner reserves metadata scratch before sizing, then the measured
bound before capped snapshot construction. The absolute 256-MiB profile remains.
Fresh original observations bracket both full byte checks without adopting newer
fields. Keep source and detached DATA charged until every view and observer drops.
"""

import sys
import types

from literate_ai.adapters.builders.javascript import NodeToolchain
from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.node_sdk_typescript import (
    NodeSDKTypeScriptCompiler,
    TypeScriptSDK,
)
from literate_ai.adapters.node_sdk_verifier_resources import _tuple_field_reference
from literate_ai.contracts.identity import ContentIdentity, HashAlgorithm

MAXIMUM_COMPILER_STORAGE_BYTES = 256 * 1024 * 1024
COMPILER_OBSERVATION_METADATA_BYTES = 2 * 1024 * 1024
_ASCII = str.isascii


def _supports_compact_ascii(implementation, version):
    if (
        type(implementation) is not str
        or type(version) is not tuple
        or len(version) != 2
        or type(version[0]) is not int
        or type(version[1]) is not int
    ):
        return False
    # 3.11 can retain a third, independent legacy wchar_t cache. Preserve its
    # original policy; the reviewed two-copy profile starts with PEP 623.
    return implementation == "cpython" and (3, 12) <= version <= (3, 14)


_COMPACT_ASCII_PROFILE = _supports_compact_ascii(
    sys.implementation.name, sys.version_info[:2]
)
_FIELDS = {
    NodeSDKTypeScriptCompiler: (
        "sdk",
        "node",
        "selection_identity",
        "identity",
        "_helper",
        "_bootstrap",
        "_sdk_packet",
        "_helper_sha256",
        "_sdk_packet_sha256",
    ),
    TypeScriptSDK: ("files", "version", "identity"),
    NodeToolchain: (
        "command",
        "launcher_executable",
        "launcher_digest",
        "runtime_executable",
        "runtime_digest",
        "version",
        "identity",
    ),
    DirectoryExportFile: ("path", "content", "mode"),
    ContentIdentity: ("algorithm", "digest"),
}
_SLOTS = {
    cls: tuple(vars(cls)[name] for name in names) for cls, names in _FIELDS.items()
}
_ABSENT = object()
_FENCES = {
    cls: (
        type.__getattribute__(cls, "__mro__"),
        tuple(
            (base, tuple(type.__getattribute__(base, "__dict__").items()))
            for base in type.__getattribute__(cls, "__mro__")
        ),
    )
    for cls in (*_FIELDS, HashAlgorithm)
}
_ALGORITHM = HashAlgorithm.SHA256
_ENUM_DICT = next(
    type.__getattribute__(base, "__dict__")["__dict__"]
    for base in type.__getattribute__(HashAlgorithm, "__mro__")
    if type(type.__getattribute__(base, "__dict__").get("__dict__"))
    is types.GetSetDescriptorType
)
_ENUM_VALUES = tuple(
    types.GetSetDescriptorType.__get__(_ENUM_DICT, _ALGORITHM, HashAlgorithm).items()
)


def _require_namespace(cls):
    mro, namespaces = _FENCES[cls]
    if type.__getattribute__(cls, "__mro__") is not mro:
        raise ValueError("original compiler storage class changed")
    for base, original in namespaces:
        current = type.__getattribute__(base, "__dict__")
        if len(current) != len(original) or any(
            current.get(name, _ABSENT) is not value for name, value in original
        ):
            raise ValueError("original compiler storage namespace changed")


def _read_slots(value, cls):
    values = []
    try:
        if type(value) is not cls:
            raise TypeError("compiler storage requires its exact original record type")
        _require_namespace(cls)
        for slot in _SLOTS[cls]:
            values.append(types.MemberDescriptorType.__get__(slot, value, cls))
        return tuple(values)
    finally:
        value = slot = None
        values.clear()


def _require_algorithm():
    _require_namespace(HashAlgorithm)
    data = types.GetSetDescriptorType.__get__(_ENUM_DICT, _ALGORITHM, HashAlgorithm)
    if (
        type(data) is not dict
        or len(data) != len(_ENUM_VALUES)
        or any(type(name) is not str for name in dict.keys(data))
        or any(
            dict.get(data, name, _ABSENT) is not value for name, value in _ENUM_VALUES
        )
    ):
        raise ValueError("original compiler identity algorithm changed")


def _resource_facts(records):
    facts, fields = [], []
    original = values = value = None
    try:
        for original, _cls, values in records:
            fields = []
            for value in values:
                fields.append(
                    _tuple_field_reference(value) if type(value) is tuple else value
                )
            facts.append((original, tuple(fields)))
        return (tuple(facts),)
    finally:
        records = original = values = value = None
        fields.clear()
        facts.clear()


def _primitive_view(records):
    """Closed immutable DATA; contains no compiler, SDK, node or file objects."""
    rows = []
    fields = node_fields = row = None
    try:
        fields = records[0][2]
        node_fields = records[2][2]
        has_selection = fields[2] is not None
        offset = 6 if has_selection else 5
        for index in range(offset, len(records)):
            row = records[index][2]
            rows.append(row)
        return (
            records[3][2][1],
            records[5][2][1] if has_selection else None,
            records[4][2][1],
            node_fields,
            fields[4],
            fields[5],
            fields[6],
            fields[7],
            fields[8],
            tuple(rows),
        )
    finally:
        records = fields = node_fields = row = None
        rows.clear()


def _same_fields(before, after):
    try:
        if len(before) != len(after):
            return False
        for index in range(len(before)):
            if before[index] is not after[index]:
                return False
        return True
    finally:
        before = after = None


def _source_storage_charge(value):
    """Conservative source policy, not total interpreter heap measurement.

    Reviewed CPython ASCII storage permits one character byte plus a separate
    UTF-8 byte per character. Record/header/container costs remain independent.
    Other strings and interpreters retain the original four-byte allowance.
    """
    try:
        if type(value) is bytes:
            return len(value)
        if type(value) is str:
            width = 2 if _COMPACT_ASCII_PROFILE and _ASCII(value) else 4
            return width * len(value)
        raise TypeError("source accounting requires exact primitive storage")
    finally:
        value = None


def require_compiler_data_view(view):
    """Require closed primitive DATA before any serializer can follow it."""
    node = rows = row = value = None
    try:
        if type(view) is not tuple or len(view) != 10:
            raise TypeError("compiler serialization requires a closed primitive view")
        for index in (0, 2, 7, 8):
            value = view[index]
            if type(value) is not str or len(value) != 64:
                raise ValueError("compiler view digest differs from its profile")
        if view[1] is not None and (type(view[1]) is not str or len(view[1]) != 64):
            raise ValueError("compiler view selection differs from its profile")
        for index, maximum in ((4, 16384), (5, 4096), (6, 48 * 1024 * 1024)):
            value = view[index]
            if type(value) is not str or not 1 <= len(value) <= maximum:
                raise ValueError("compiler view source exceeds its profile")
        node, rows = view[3], view[9]
        if (
            type(node) is not tuple
            or len(node) != 7
            or type(node[0]) is not tuple
            or len(node[0]) != 1
            or type(node[0][0]) is not str
            or not 1 <= len(node[0][0]) <= 4096
        ):
            raise TypeError("compiler view requires a primitive direct Node binding")
        for index in range(1, 7):
            if type(node[index]) is not str or not 1 <= len(node[index]) <= 4096:
                raise TypeError("compiler view requires primitive Node fields")
        if type(rows) is not tuple or not 1 <= len(rows) <= 1024:
            raise TypeError("compiler view requires bounded primitive file rows")
        total = 0
        for row in rows:
            if (
                type(row) is not tuple
                or len(row) != 3
                or type(row[0]) is not str
                or not 1 <= len(row[0]) <= 512
                or type(row[1]) is not bytes
                or len(row[1]) > 16 * 1024 * 1024
                or type(row[2]) is not int
                or not 0 <= row[2] <= 0o777
            ):
                raise TypeError("compiler view requires closed primitive file fields")
            total += len(row[1])
            if total > 32 * 1024 * 1024:
                raise ValueError("compiler view source exceeds its profile")
    finally:
        view = node = rows = row = value = None


def _compiler_storage(compiler, *, measure_only, maximum_bytes, with_view):
    """Return (original facts, retained-byte charge, sticky guard, release).

    No properties, serializers, file reads, compiler invocations or supplied
    callbacks run here. This observation does not validate initial content
    identities, prove enrollment or authorize execution. The original owner must
    supply those checks before and after this already-reserved capture.
    """
    records = []
    byte_count = 1024 * 1024
    seen_source = set()

    def record(value, cls):
        nonlocal byte_count
        values = item = None
        try:
            values = _read_slots(value, cls)
            byte_count += 512
            for item in values:
                if type(item) in (str, bytes) and id(item) not in seen_source:
                    seen_source.add(id(item))
                    byte_count += _source_storage_charge(item)
            if byte_count > maximum_bytes:
                raise ValueError("compiler retained storage exceeds its reservation")
            if not measure_only:
                records.append((value, cls, values))
            return values
        finally:
            value = values = item = None

    def identity(value):
        algorithm = digest = None
        try:
            algorithm, digest = record(value, ContentIdentity)
            if (
                algorithm is not _ALGORITHM
                or type(digest) is not str
                or len(digest) != 64
            ):
                raise ValueError("compiler storage has malformed identity fields")
            return digest
        finally:
            value = algorithm = digest = None

    def text(value, maximum):
        try:
            if type(value) is not str or not 1 <= len(value) <= maximum:
                raise ValueError("compiler storage text exceeds its bound")
        finally:
            value = None

    try:
        if (
            type(measure_only) is not bool
            or type(with_view) is not bool
            or type(maximum_bytes) is not int
            or not 1024 * 1024 <= maximum_bytes <= MAXIMUM_COMPILER_STORAGE_BYTES
            or (measure_only and with_view)
        ):
            raise ValueError("compiler storage requires an original bounded profile")
        _require_algorithm()
        fields = record(compiler, NodeSDKTypeScriptCompiler)
        (
            sdk,
            node,
            selection,
            compiler_identity,
            helper,
            bootstrap,
            packet,
            helper_hash,
            packet_hash,
        ) = fields
        text(helper, 16 * 1024)
        text(bootstrap, 4096)
        text(packet, 48 * 1024 * 1024)
        text(helper_hash, 64)
        text(packet_hash, 64)
        sdk_fields = record(sdk, TypeScriptSDK)
        files, version, sdk_identity = sdk_fields
        text(version, 256)
        if type(files) is not tuple or not 1 <= len(files) <= 1024:
            raise ValueError("compiler storage file inventory exceeds its bound")
        node_fields = record(node, NodeToolchain)
        command = node_fields[0]
        if type(command) is not tuple or len(command) != 1:
            raise ValueError(
                "compiler storage requires the original direct Node profile"
            )
        for value in (*command, *node_fields[1:]):
            text(value, 4096)
        # Command operands are tuple leaves rather than direct record fields.
        for value in command:
            if id(value) not in seen_source:
                seen_source.add(id(value))
                byte_count += _source_storage_charge(value)
        if byte_count > maximum_bytes:
            raise ValueError("compiler retained storage exceeds its reservation")
        identity(compiler_identity)
        identity(sdk_identity)
        if selection is not None:
            identity(selection)
        file_bytes = 0
        for item in files:
            path, content, mode = record(item, DirectoryExportFile)
            text(path, 512)
            if (
                type(content) is not bytes
                or len(content) > 16 * 1024 * 1024
                or type(mode) is not int
                or not 0 <= mode <= 0o777
            ):
                raise ValueError(
                    "compiler storage file differs from its bounded profile"
                )
            file_bytes += len(content)
        if file_bytes > 32 * 1024 * 1024 or byte_count > maximum_bytes:
            raise ValueError("compiler retained storage exceeds its reservation")
        if measure_only:
            return byte_count
        records = tuple(records)
        # The fresh tuple containers are structural. Original mutable records and
        # all their field references are explicit leaves, never computed URI values.
        facts = _resource_facts(records)
        slot_reader, algorithm_current = _read_slots, _require_algorithm
        same_fields = _same_fields
        failed = False
        view_builder = _primitive_view

        def require_original():
            nonlocal failed
            if failed:
                raise ValueError("original compiler storage observation already failed")
            try:
                algorithm_current()
                for value, cls, before in records:
                    after = slot_reader(value, cls)
                    if not same_fields(before, after):
                        raise ValueError("original compiler field storage changed")
            except BaseException:
                failed = True
                raise
            finally:
                value = cls = before = after = None

        def fresh_view():
            nonlocal failed
            current_records = []
            value = cls = before = after = None
            try:
                require_original()
                for value, cls, before in records:
                    after = slot_reader(value, cls)
                    if not same_fields(before, after):
                        raise ValueError("original compiler field storage changed")
                    current_records.append((value, cls, after))
                require_original()
                return view_builder(current_records)
            except BaseException:
                failed = True
                raise
            finally:
                value = cls = before = after = None
                current_records.clear()

        def release():
            nonlocal records, failed
            try:
                failed = True
            finally:
                records = ()

        require_original()
        if with_view:
            return (
                facts,
                byte_count,
                require_original,
                release,
                fresh_view(),
                fresh_view,
            )
        return facts, byte_count, require_original, release
    except BaseException:
        records = ()
        compiler = fields = sdk_fields = node_fields = facts = None
        sdk = node = selection = compiler_identity = sdk_identity = files = None
        helper = bootstrap = packet = helper_hash = packet_hash = None
        item = path = content = command = value = None
        raise
    finally:
        compiler = fields = sdk_fields = node_fields = facts = None
        sdk = node = selection = compiler_identity = sdk_identity = files = None
        helper = bootstrap = packet = helper_hash = packet_hash = None
        item = path = content = command = value = None


def measure_node_compiler_storage(compiler):
    """Sizing-only original-slot walk; retains no source record or DATA view."""
    try:
        return _compiler_storage(
            compiler,
            measure_only=True,
            maximum_bytes=MAXIMUM_COMPILER_STORAGE_BYTES,
            with_view=False,
        )
    finally:
        compiler = None


def capture_node_compiler_storage(
    compiler, *, maximum_bytes=MAXIMUM_COMPILER_STORAGE_BYTES, _with_view=False
):
    """Capture within prepaid source capacity; optionally return immutable DATA."""
    try:
        return _compiler_storage(
            compiler,
            measure_only=False,
            maximum_bytes=maximum_bytes,
            with_view=_with_view,
        )
    finally:
        compiler = None
