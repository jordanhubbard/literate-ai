"""Canonical Git acquisition held through the actual catalog copy borrower."""

from __future__ import annotations

import os
import re
import stat
import threading
from contextlib import ExitStack, contextmanager
from pathlib import Path

from literate_ai.contracts.identity import canonical_identity

from . import catalog_import
from .catalog_copy_plan import _anchor, _Observation, _root
from .exclusive_entry import _from_stat
from .repository_refresh import _raw_file, _signature
from .retained_layout_control_publication import _pinned_directory
from .retained_layout_partition import _lineage

_LIVE = {}
_FIELDS = (
    "pinned",
    "identity",
    "reference",
    "root",
    "source_root",
    "specs",
    "items",
    "ledger",
    "censuses",
    "inputs",
    "framework_update",
    "framework_identity",
    "forest",
)


def _fail(message):
    raise ValueError("catalog.source-lease: " + message)


def _close(owner, record, binding):
    # No guard/native callback after the original registry lifetime close.
    if (
        _LIVE.get(owner) is not record
        or record["pid"] != os.getpid()
        or record["thread"] != threading.get_ident()
        or record["binding"] is not binding
        or any(
            record[name] is not value
            for name, value in zip(_FIELDS, binding, strict=True)
        )
    ):
        _fail("original canonical source acquisition ended")


def _record(owner):
    if type(owner) is not _SourceLease or (record := _LIVE.get(owner)) is None:
        raise TypeError("actual live canonical Git source lease required")
    binding = record["binding"]
    _close(owner, record, binding)
    for path, descriptor, guard, node in record["pinned"]:
        guard()
        if _from_stat(os.fstat(descriptor)) != node or _from_stat(path.lstat()) != node:
            _fail("original canonical checkout native custody changed")
    _close(owner, record, binding)
    return record


class _SourceLease:
    def _lifetime(self):
        record = _record(self)
        return record, record["binding"]

    def _close_lifetime(self, lifetime):
        _close(self, *lifetime)

    @property
    def identity(self):
        return _record(self)["identity"]

    @property
    def reference(self):
        return _record(self)["reference"]

    def close_native(self):
        record = _record(self)
        binding = record["binding"]
        for item, anchor in record["inputs"]:
            if (
                _anchor(item.path) != anchor
                or (_signature(item.path) if os.path.lexists(item.path) else None)
                != item.signature
            ):
                _fail("original checkout input node or ancestry changed")
        for census, native in record["censuses"]:
            if _lineage(census.tree.root) != census._lineage:
                _fail("original checkout item ancestry changed")
            for name, node in native:
                if _from_stat((census.tree.root / name).lstat()) != node:
                    _fail("original checkout item native node changed")
        _record(self)
        _close(self, record, binding)

    def require_current(self):
        record = _record(self)
        binding = record["binding"]
        for item, _anchor_value in record["inputs"]:
            if item.content is None and not os.path.lexists(item.path.parent):
                continue
            if (
                _raw_file(
                    item.path,
                    optional=item.content is None,
                    maximum_bytes=max(1, len(item.content or b"")),
                )
                != item
            ):
                _fail("original canonical checkout input changed")
        for census, _native in record["censuses"]:
            census.require_unchanged()
        self.close_native()
        _close(self, record, binding)


def _ledger(owner, root, source_root, item_specs, budget, metadata, framework_update):
    record = _record(owner)
    if (
        record["claimed"]
        or record["root"] != root
        or record["source_root"] != source_root
        or record["specs"] != item_specs
        or record["ledger"].budget != budget
        or record["ledger"].metadata != metadata
        or record["framework_update"] is not framework_update
        or (
            framework_update is not None
            and framework_update.identity != record["framework_identity"]
        )
    ):
        _fail("one exact creating source/copy policy and borrower required")
    owner.require_current()
    record["claimed"] = True
    return record["ledger"]


def _inputs(owner, ledger, root, source_root, items):
    record = _record(owner)
    if (
        not record["claimed"]
        or record["ledger"] is not ledger
        or record["root"] != root
        or record["source_root"] != source_root
        or record["items"] != items
    ):
        _fail("actual creating source ledger and selectors required")
    owner.require_current()
    return record["censuses"], record["forest"]


@contextmanager
def prepared_git_catalog_copy_roles(
    root,
    source_spec,
    item_specs,
    *,
    budget,
    maximum_metadata_bytes,
    **copy_options,
):
    """Acquire canonically, prepare a copy, then keep its actual source alive.

    Existing canonical acquisition owns Git subprocess policy and clone cleanup.
    Checkout observations consume the same original ledger as the copy. The
    nested copy factory always revokes its borrower before source teardown.
    """
    from .catalog_copy_roles import prepared_catalog_copy_roles

    root = _root(root)
    ledger = _Observation(budget, maximum_metadata_bytes, (root,))
    framework_update = copy_options.get("framework_update")
    framework_identity = None
    if framework_update is not None:
        from .framework_update_roles import _require_handoff

        _require_handoff(framework_update).bind(root)
        framework_identity = framework_update.identity
        ledger.bytes += framework_update._used_bytes
        ledger.files += framework_update._used_files
        ledger.records += framework_update._used_entries
        ledger.charged += max(
            0, framework_update._used_metadata - 64 * framework_update._reserve
        )
        ledger.require_capacity()
    if (
        type(source_spec) is not str
        or len(source_spec) * 4 > budget.maximum_file_bytes
        or not catalog_import._is_git_source_spec(source_spec)
        or type(item_specs) is not tuple
        or not item_specs
    ):
        _fail("bounded Git source and finite selector tuple required")
    ledger.charge_records(len(item_specs), 4 * len(source_spec))
    for spec in item_specs:
        if type(spec) is not str or 4 * len(spec) > budget.maximum_file_bytes:
            _fail("bounded canonical selector required")
        ledger.charge_records(1, 4 * len(spec))
    items = tuple(catalog_import._parse_item_spec(spec) for spec in item_specs)
    for kind, name in items:
        directory = catalog_import._KIND_DIR[kind]
        if (
            type(directory) is not str
            or 4 * (len(directory) + len(name)) > budget.maximum_file_bytes
        ):
            _fail("canonical source selector exceeds original policy")
        ledger.charge_records(1, 4 * (len(directory) + len(name)))
    paths = tuple(
        sorted(
            {".literate", *(catalog_import._KIND_DIR[k] + "/" + n for k, n in items)}
        )
    )
    with catalog_import._open_source(source_spec, paths) as (source_root, reference):
        # macOS's canonical temporary directory may pass through /var. Resolve
        # that acquisition spelling once, before admission, while proving the
        # actual leaf is the same direct directory; subsequent paths stay direct.
        acquired_node = _from_stat(source_root.lstat())
        if not stat.S_ISDIR(acquired_node.mode):
            _fail("canonical acquisition leaf is not a direct directory")
        source_root = source_root.resolve(strict=True)
        if _from_stat(source_root.lstat()) != acquired_node:
            _fail("canonical acquisition root changed during path normalization")
        commit = reference.rsplit("@", 1)[-1]
        if (
            not reference.startswith("git:")
            or re.fullmatch(r"[0-9a-fA-F]{40}|[0-9a-fA-F]{64}", commit) is None
        ):
            _fail("canonical acquisition did not return a resolved Git reference")
        # This checkout belongs to canonical acquisition. Detach only this owned
        # clone so HEAD itself is a bounded, exact commit witness.
        catalog_import._run_git(
            ("git", "checkout", "--quiet", "--detach", "HEAD"), cwd=source_root
        )
        ledger.roots = root, source_root
        owner = _SourceLease()
        with ExitStack() as pins:
            pinned = []
            # Canonical acquisition collects this entire private parent. Retain
            # its original FD/native receipt as well as checkout/admin roots so
            # successors cannot place durable backups in a collected sibling.
            cleanup_root = source_root.parent
            cleanup_paths = (cleanup_root, *cleanup_root.parents)
            ledger.charge_records(
                2 * len(cleanup_paths),
                2 * sum(len(str(path).encode("utf-8")) for path in cleanup_paths),
            )
            for path in (cleanup_root, source_root, source_root / ".git"):
                descriptor, guard = pins.enter_context(_pinned_directory(path))
                pinned.append(
                    (path, descriptor, guard, _from_stat(os.fstat(descriptor)))
                )
            for name in ("HEAD", "config", "index", "packed-refs", "shallow"):
                ledger.snapshot(
                    source_root / ".git" / name,
                    optional=name not in {"HEAD", "config", "index"},
                )
            if ledger.cache[
                source_root / ".git/HEAD"
            ].content.strip().lower() != commit.lower().encode("ascii"):
                _fail("actual detached HEAD differs from canonical resolved commit")
            catalog_import._read_source_project(source_root, ledger)
            catalog_import._read_source_ancestors(source_root, ledger)
            ledger.snapshot(Path(__file__))
            forest = None
            if len(items) == 1:
                for kind, name in items:
                    ledger.capture(
                        catalog_import._source_item_dir(source_root, kind, name)
                    )
            else:
                selected = tuple(
                    sorted(
                        catalog_import._source_item_dir(source_root, kind, name)
                        .relative_to(source_root)
                        .as_posix()
                        for kind, name in items
                    )
                )
                forest = ledger.capture(source_root, _source_roots=selected)
            original = tuple(zip(ledger.censuses, ledger.native, strict=True))
            # Transfer actual original censuses, preserving all incurred usage.
            # Planning adds its destination first, then these exact known trees.
            ledger.censuses, ledger.native = [], []
            bound = (
                8192
                + 12 * (len(reference.encode()) + len(str(source_root).encode()))
                + 4096 * len(items)
            )
            if bound > budget.maximum_file_bytes:
                _fail("source identity exceeds original file policy")
            ledger.bytes += bound
            ledger.charge_records(8 + len(items), bound)
            identity = canonical_identity(
                dict(
                    root=str(source_root),
                    reference=reference,
                    nonce=os.urandom(16).hex(),
                    items=items,
                    censuses=[c.identity.uri for c, _ in original],
                )
            )
            record = dict(
                pinned=tuple(pinned),
                pid=os.getpid(),
                thread=threading.get_ident(),
                identity=identity,
                reference=reference,
                root=root,
                source_root=source_root,
                specs=item_specs,
                items=items,
                ledger=ledger,
                claimed=False,
                censuses=original,
                inputs=tuple(
                    (item, ledger.ancestry[path]) for path, item in ledger.cache.items()
                ),
                framework_update=framework_update,
                framework_identity=framework_identity,
                forest=forest,
            )
            record["binding"] = tuple(record[name] for name in _FIELDS)
            _LIVE[owner] = record
            try:
                owner.require_current()
                with prepared_catalog_copy_roles(
                    root,
                    source_root,
                    item_specs,
                    budget=budget,
                    maximum_metadata_bytes=maximum_metadata_bytes,
                    _source_lease=owner,
                    **copy_options,
                ) as borrower:
                    yield borrower
            finally:
                _LIVE.pop(owner, None)
