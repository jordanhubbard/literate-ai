"""Original initializer Git observations borrowing the actual source allowance."""

from __future__ import annotations

import os
import time
from contextvars import ContextVar
from dataclasses import dataclass, replace
from pathlib import Path

from .bounded_role_observation import current_role_observation
from .builders._process import run_bounded_process
from .retained_layout_partition import _lineage
from .retained_layout_source_preparation import _state

_KEY = object()
_OWNERS = {}
_BOUND = {}
_ROUND = ContextVar("source_provider_read_round", default=None)


def _fail(message):
    raise ValueError("layout.source-provider: " + message)


@dataclass(frozen=True, slots=True)
class _Binding:
    fields: tuple
    mappings: tuple
    trees: tuple
    roster: tuple


@dataclass(frozen=True, slots=True)
class _Record:
    owner: object
    admission: object
    original: object
    root: Path
    origin: object
    objects: object = None
    roster: object = None
    binding: object = None
    discovery: object = None
    preparation: object = None


def _binding(objects, roster):
    return _Binding(
        tuple(
            (name, getattr(objects, name))
            for name in (
                "root",
                "origin",
                "budget",
                "limit",
                "node",
                "environment",
                "deadline",
                "tree",
                "git_paths",
                "object_stores",
                "configuration",
                "file_count",
                "total",
                "charged",
                "entries",
                "scratch_size",
            )
        ),
        tuple(
            (name, getattr(objects, name), tuple(getattr(objects, name).items()))
            for name in ("cache", "snapshots", "ancestry", "directories")
        ),
        (
            objects.trees,
            tuple(
                (key, tree, tuple(tree.items())) for key, tree in objects.trees.items()
            ),
        ),
        (
            roster._objects,
            roster._templates,
            roster._inputs,
            roster._identity,
            roster._pid,
        ),
    )


def _require_binding(value):
    objects, binding, roster = value.objects, value.binding, value.roster
    if objects is None or objects._shared is not value.owner:
        _fail("actual original provider object observer required")
    if binding is None:
        return
    if (
        not roster._active
        or roster._shared is not value.owner
        or any(
            getattr(objects, name) is not expected for name, expected in binding.fields
        )
        or any(
            getattr(objects, name) is not mapping
            or len(mapping) != len(items)
            or any(mapping.get(key) is not item for key, item in items)
            for name, mapping, items in binding.mappings
        )
        or objects.trees is not binding.trees[0]
        or len(objects.trees) != len(binding.trees[1])
        or any(
            objects.trees.get(key) is not tree
            or len(tree) != len(items)
            or any(tree.get(name) is not item for name, item in items)
            for key, tree, items in binding.trees[1]
        )
        or any(
            a is not b
            for a, b in zip(
                (
                    roster._objects,
                    roster._templates,
                    roster._inputs,
                    roster._identity,
                    roster._pid,
                ),
                binding.roster,
                strict=True,
            )
        )
    ):
        _fail("original provider witness or lifetime changed")


def _record(owner, *, reading=False, role=False):
    if type(owner) is not _Provider:
        _fail("actual original provider participant required")
    try:
        return _read_record(owner, reading=reading, role=role)
    except BaseException:
        value = _OWNERS.get(owner)
        if value is not None and value.preparation is not None:
            from .retained_layout_source_roles import _revoke_preparation

            _revoke_preparation(value.preparation)
        raise


def _read_record(owner, *, reading=False, role=False):
    from .retained_layout_source_admission import _ADMISSIONS

    value = _OWNERS.get(owner)
    if (
        type(owner) is not _Provider
        or type(value) is not _Record
        or value.owner is not owner
    ):
        _fail("actual original provider participant required")
    admission = value.admission
    if value.discovery is not None:
        from .retained_layout_source_roles import _require_provider

        _require_provider(value, reading=reading, role=role)
        if value.objects is not None:
            _require_binding(value)
        return value
    if (
        _state(admission.preparation) is not value.original
        or admission.provider is not owner
        or value.original is not admission.original
    ):
        _fail("original provider source operation changed or ended")
    if _ADMISSIONS.get(admission.preparation) is not admission:
        from .retained_layout_source_finalization import _terminal

        terminal = _terminal(admission.preparation)
        if terminal is None or terminal.provider is not owner:
            _fail("original provider admission ended without terminal handoff")
    if role:
        admission.phase._live()
    if reading and current_role_observation() is not value.original.reader:
        _fail("actual active original provider read scope required")
    if value.objects is not None:
        _require_binding(value)
    return value


def _bind_provider_run_failure_notes(implementation):
    """Attach cached numeric evidence without changing a native read or failure."""
    attach, base_error = BaseException.add_note, BaseException
    exact, integer, size, pair, text, some = type, int, len, zip, str, any
    labels = (
        "requested_stdout",
        "remaining_stdout",
        "chosen_stdout",
        "stderr_limit",
        "input_bytes_before",
        "input_reserve",
        "metadata_charged_before",
        "metadata_limit",
        "file_limit",
        "total_input_limit",
        "scratch_stdout",
    )

    def note(error, values):
        try:
            if size(values) != size(labels) or some(
                exact(value) is not integer or value.bit_length() > 128
                for value in values
            ):
                return
            message = "source-provider cached native allowance: " + ", ".join(
                label + "=" + text(value)
                for label, value in pair(labels, values, strict=True)
            )
            if size(message) <= 1024:
                attach(error, message)
        except base_error:
            pass

    note_code, note_defaults, note_keywords = (
        note.__code__,
        note.__defaults__,
        note.__kwdefaults__,
    )

    def checked_note(error, values):
        if (
            note.__code__ is note_code
            and note.__defaults__ is note_defaults
            and note.__kwdefaults__ is note_keywords
        ):
            note(error, values)

    descriptor = (
        checked_note,
        checked_note.__code__,
        checked_note.__defaults__,
        checked_note.__kwdefaults__,
    )
    original_code = implementation.__code__
    original_defaults, original_keywords = (
        implementation.__defaults__,
        implementation.__kwdefaults__,
    )
    failure = ValueError

    def run(self, objects, arguments, maximum):
        if (
            implementation.__code__ is not original_code
            or implementation.__defaults__ is not original_defaults
            or implementation.__kwdefaults__ is not original_keywords
        ):
            raise failure("original provider native read implementation changed")
        return implementation(
            self, objects, arguments, maximum, _failure_note=descriptor
        )

    return run


class _Provider:
    __slots__ = ()

    def __init__(self, key):
        if key is not _KEY:
            raise TypeError("actual source provider participant required")

    def require_profile(self, instance):
        value = _record(self)
        if instance is not value.objects and instance is not value.roster:
            _fail("foreign or ended provider construction profile")

    def select_root(self, checkout):
        value = _record(self, reading=True)
        if checkout is not None and Path(checkout) != value.root:
            _fail("original provider selector changed")
        return value.root

    def bind_objects(self, objects):
        from .retained_layout_provider import _Objects

        value = _record(self, reading=True)
        if (
            value.objects is not None
            or type(objects) is not _Objects
            or objects.root != value.root
            or objects.origin is not value.origin
        ):
            _fail("one actual creating original provider observer required")
        _OWNERS[self] = replace(value, objects=objects)
        self.directory(objects.root)

    def directory(self, path):
        _record(self, reading=True)
        _lineage(path)

    def records(self, count, size=0):
        value = _record(self, reading=True)
        value.original.ledger.charge_records(count, size)

    def object_input(self):
        value = _record(self, reading=True)
        ledger = value.original.ledger
        ledger.files += 1
        ledger.charge_records(1)

    def remaining(self):
        ledger = _record(self, reading=True).original.ledger
        return min(
            ledger.budget.maximum_file_bytes,
            ledger.budget.maximum_total_bytes - ledger.bytes - ledger.reserve - 4096,
            (ledger.metadata - ledger.charged) // 64 - 4096,
        )

    def shape_limit(self, content, maximum):
        nodes = min(maximum, 2 * len(content) + 16)
        self.records(1, 8 * nodes + 4 * len(content))
        return nodes

    def roster_allowance(self, objects, templates, inputs):
        self.records(
            32
            + 4
            * (
                len(objects.cache)
                + len(objects.directories)
                + len(templates)
                + len(inputs)
            ),
            65536 + 8 * sum(len(str(path).encode()) for path in objects.snapshots),
        )

    @_bind_provider_run_failure_notes
    def run(self, objects, arguments, maximum, *, _failure_note):
        value = _record(self, reading=True)
        if objects is not value.objects:
            _fail("foreign provider native reader")
        active = _ROUND.get()
        deadline = objects.deadline if active is None else active[1]
        if active is not None and active[0] is not self:
            _fail("foreign provider read round")
        timeout = min(30, deadline - time.monotonic())
        objects.calls += 1
        requested_maximum, remaining_maximum = maximum, self.remaining()
        maximum = min(requested_maximum, remaining_maximum)
        reader, ledger = value.original.reader, value.original.ledger
        cached = None
        if (
            value.binding is not None
            and type(arguments) is tuple
            and len(arguments) == 3
            and all(type(part) is str for part in arguments)
            and arguments[0] == "cat-file"
            and arguments[1] in {"commit", "tree", "blob"}
            and type(requested_maximum) is int
            and remaining_maximum >= 1
        ):
            key = arguments[1:]
            for name, mapping, entries in value.binding.mappings:
                if name == "cache" and mapping is objects.cache:
                    for original_key, original_bytes in entries:
                        if (
                            type(original_key) is tuple
                            and len(original_key) == 2
                            and all(type(part) is str for part in original_key)
                            and original_key == key
                            and type(original_bytes) is bytes
                            and requested_maximum == max(1, len(original_bytes))
                            and requested_maximum
                            <= min(
                                ledger.reserve,
                                ledger.budget.maximum_file_bytes,
                                objects.scratch_size,
                            )
                        ):
                            cached = original_bytes
                            maximum = requested_maximum
                            break
                    break
        if (
            timeout <= 0
            or maximum < 1
            or objects.calls
            > objects.budget.maximum_entries + objects.budget.maximum_files + 8
        ):
            _fail("original provider read allowance exhausted")
        reader._begin_io()
        diagnostic_values = (
            requested_maximum,
            remaining_maximum,
            maximum,
            4096,
            ledger.bytes,
            ledger.reserve,
            ledger.charged,
            ledger.metadata,
            ledger.budget.maximum_file_bytes,
            ledger.budget.maximum_total_bytes,
            maximum if cached is not None else 0,
        )
        # Exact bound-cache revalidation retains no new stdout: the original
        # ledger already funds its one nonreentrant maximum-file scratch buffer.
        # Stderr and work still use the original shared allowance.
        retained_stdout = maximum if cached is None else 0
        ledger.bytes += retained_stdout + 4096
        ledger.charged += 64 * (retained_stdout + 4096)
        ledger.require_capacity()
        try:
            try:
                result = run_bounded_process(
                    (
                        "git",
                        "--no-pager",
                        "-c",
                        "core.fsmonitor=false",
                        "-c",
                        "core.hooksPath=" + os.devnull,
                        *arguments,
                    ),
                    cwd=objects.root,
                    environment=objects.environment,
                    timeout_seconds=timeout,
                    stdout_limit_bytes=maximum,
                    stderr_limit_bytes=4096,
                    poll_interval_seconds=0.01,
                    error_prefix="layout.source-provider",
                )
            except BaseException as error:
                try:
                    callback, code, defaults, keywords = _failure_note
                    if (
                        callback.__code__ is code
                        and callback.__defaults__ is defaults
                        and callback.__kwdefaults__ is keywords
                    ):
                        callback(error, diagnostic_values)
                except BaseException:
                    pass
                raise
            if result.returncode or time.monotonic() >= deadline:
                _fail("original provider objects unavailable during bounded read")
            scratch_stderr = None
            if cached is not None:
                scratch_stdout, scratch_stderr = result.stdout, result.stderr
                if (
                    type(scratch_stdout) is not bytes
                    or type(scratch_stderr) is not bytes
                ):
                    _fail("original provider reread requires exact byte streams")
                ledger.charge_records(1)
                _record(self, reading=True)
                if scratch_stdout != cached:
                    _fail("original provider object bytes changed")
            unused = (
                (maximum - len(result.stdout) if cached is None else 0)
                + 4096
                - len(result.stderr if cached is None else scratch_stderr)
            )
            ledger.bytes -= unused
            ledger.charged -= 64 * unused
            # Binary object revalidation compares original bytes directly.
            # Tree/path/AST decoders fund their own retained records; raw blob
            # newlines are not newly decoded configuration records.
            records = 1
            if arguments[0] == "config":
                records += result.stdout.count(b"\0") + result.stdout.count(b"\n")
            if cached is None:
                ledger.charge_records(records)
            _record(self, reading=True)
            return result.stdout if cached is None else cached
        except BaseException:
            reader._poisoned = True
            raise
        finally:
            reader._io_active = False

    @property
    def objects(self):
        return _record(self, role=True).objects

    @property
    def templates(self):
        return _record(self, role=True).roster.templates

    @property
    def inputs(self):
        return _record(self, role=True).roster.inputs

    @property
    def identity(self):
        return _record(self, role=True).roster.identity

    def require_current(self):
        from .retained_layout_source_admission import _control_reads

        value = _record(self, role=True)
        if value.discovery is not None:
            from .retained_layout_source_roles import _provider_reads

            with _provider_reads(value.discovery):
                _payload(value)
            self.close_native()
            return
        with _control_reads(value.admission.preparation, value.admission.pool):
            _payload(value)
        self.close_native()

    def close_native(self):
        value = _record(self)
        _native(value)


del _bind_provider_run_failure_notes


def _payload(value):
    owner = value.owner
    if (
        _record(owner, reading=True) is not value
        or value.binding is None
        or _ROUND.get() is not None
    ):
        _fail("actual original unborrowed provider verification required")
    token = _ROUND.set((owner, time.monotonic() + 120))
    try:
        objects = value.objects
        objects.close_locator()
        for (kind, oid), content in objects.cache.items():
            observed = objects.run("cat-file", kind, oid, maximum=max(1, len(content)))
            if observed != content:
                _fail("original provider object bytes changed")
        objects.close_locator()
        _native(value)
    finally:
        _ROUND.reset(token)
    if _record(owner) is not value:
        _fail("original provider verification lifetime changed")


def _native(value):
    if _record(value.owner) is not value:
        _fail("original provider native span changed")
    value.roster.close_native()
    _record(value.owner)


def _join(admission, origin, definition, *, checkout, budget, metadata_limit):
    from . import project_initialization
    from .retained_layout_provider import _build_original_roster
    from .retained_layout_source_admission import _phase_record
    from .retained_layout_source_roles import _CREATED

    if admission.preparation in _CREATED:
        _fail("original provider must be selected before acknowledgement")

    if (
        _phase_record(admission.phase) is not admission
        or not admission.observing
        or admission.provider is not None
    ):
        _fail("one actual creating admitted provider join required")
    root = (
        Path(project_initialization.__file__).parents[3]
        if checkout is None
        else Path(checkout)
    )
    if not root.is_absolute() or ".." in root.parts:
        _fail("direct absolute original provider checkout required")
    ledger = admission.original.ledger
    ledger.charge_records(
        64,
        65536
        + 16 * len(str(root).encode())
        + 8 * sum(len(k) + len(v) for k, v in os.environ.items()),
    )
    owner = _Provider(_KEY)
    value = _Record(owner, admission, admission.original, root, origin)
    _OWNERS[owner] = value
    _BOUND[admission.preparation] = owner
    admission.provider = owner
    try:
        roster = _build_original_roster(
            origin,
            definition,
            checkout=checkout,
            budget=budget,
            metadata_limit=metadata_limit,
            _shared=owner,
        )
        value = _record(owner)
        value = replace(value, roster=roster, binding=_binding(value.objects, roster))
        _OWNERS[owner] = value
        _separate(value)
        owner.require_current()
        return owner
    except BaseException:
        admission.failed = True
        _OWNERS.pop(owner, None)
        raise


def _join_preparation(
    discovery, origin, definition, *, checkout, budget, metadata_limit
):
    from .retained_layout_provider import _build_original_roster
    from .retained_layout_source_roles import (
        _provider_construction,
        _register_provider,
    )

    context, root = _provider_construction(discovery, checkout)
    context.ledger.charge_records(
        64,
        65536
        + 16 * len(str(root).encode())
        + 8 * sum(len(k) + len(v) for k, v in os.environ.items()),
    )
    owner = _Provider(_KEY)
    value = _Record(
        owner,
        None,
        context.original,
        root,
        origin,
        discovery=discovery,
        preparation=context.preparation,
    )
    _OWNERS[owner] = value
    _BOUND[context.preparation] = owner
    _register_provider(discovery, value)
    try:
        roster = _build_original_roster(
            origin,
            definition,
            checkout=checkout,
            budget=budget,
            metadata_limit=metadata_limit,
            _shared=owner,
        )
        value = _record(owner)
        value = replace(value, roster=roster, binding=_binding(value.objects, roster))
        _OWNERS[owner] = value
        _separate(value)
        owner.require_current()
        return owner
    except BaseException:
        _OWNERS.pop(owner, None)
        raise


def _separate(value):
    if value.discovery is not None:
        from .retained_layout_source_roles import _separate_provider

        _separate_provider(value)
        return
    plan = value.original.plan
    source = {
        plan.tree._physical[0][:2],
        *(node[:2] for _, node in plan.tree._physical[1]),
    }
    for path, identity in _roots(value):
        lineage = _lineage(path)
        if lineage[-1][1:3] != identity or any(row[1:3] in source for row in lineage):
            _fail("original provider overlaps moving source")
        for private in (value.admission.pool.root, value.admission.journal_root):
            other = _lineage(private)
            if identity in {row[1:3] for row in other} or other[-1][1:3] in {
                row[1:3] for row in lineage
            }:
                _fail("original provider overlaps actual private control state")
    for item in value.objects.snapshots.values():
        lineage = value.original.reader._lineages[item.path.parent]
        if any(row[1:3] in source for row in lineage):
            _fail("original provider input overlaps moving source")
    _record(value.owner)


def _roots(value):
    objects = value.objects
    return (
        (objects.root, objects.node),
        *((path, objects.directories[path][:2]) for path in objects.git_paths[:2]),
        *((path, signature[:2]) for path, signature in objects.object_stores),
    )


def _require_registration(admission):
    if _BOUND.get(admission.preparation) is not admission.provider:
        _fail("original provider registration was replaced or removed")
    if admission.provider is not None:
        value = _record(admission.provider)
        if value.discovery is not None:
            from .retained_layout_source_roles import _require_admission

            _require_admission(value.discovery, admission)
        elif value.admission is not admission:
            _fail("foreign original provider registration")


def _require_payload(admission):
    if admission.provider is not None:
        admission.provider.require_current()


def _close_native(admission):
    if admission.provider is not None:
        admission.provider.close_native()


def _terminal_payload(terminal):
    if terminal.provider is not None:
        _payload(_record(terminal.provider, reading=True))


def _separate_effects(admission, candidate_lineage):
    if admission.provider is None:
        return
    value = _record(admission.provider, reading=True)
    candidate, ancestors = (
        candidate_lineage[-1][1:3],
        {row[1:3] for row in candidate_lineage},
    )
    for path, identity in _roots(value):
        actual = _lineage(path)
        if (
            actual[-1][1:3] != identity
            or identity in ancestors
            or candidate in {row[1:3] for row in actual}
        ):
            _fail("private effects overlap original provider")
    for item in value.objects.snapshots.values():
        # A sibling of a named configuration file is not its descendant.
        # Refuse effect areas containing the actual observed input itself.
        if candidate in {row[1:3] for row in _lineage(item.path.parent)}:
            _fail("private effects contain original provider input")
    _record(value.owner)


def _end(preparation):
    _BOUND.pop(preparation, None)
    for owner, value in tuple(_OWNERS.items()):
        if (
            value.preparation
            if value.discovery is not None
            else value.admission.preparation
        ) is preparation:
            if value.roster is not None:
                value.roster._active = False
            _OWNERS.pop(owner, None)
