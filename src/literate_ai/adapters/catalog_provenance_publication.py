"""Canonical provenance for the actual internal catalog entry writer."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import asdict, dataclass
from datetime import UTC, datetime

from literate_ai.contracts.catalog_imports import (
    CatalogImport,
    CatalogImportFile,
    CatalogImportsFile,
    CatalogImportSource,
)

from . import catalog_import
from .exclusive_entry import _from_stat
from .repository_refresh import RefreshFileObservation, _file
from .retained_layout_control_publication import _pinned_directory


def _fail(message):
    raise ValueError("catalog.provenance: " + message)


@dataclass(frozen=True, slots=True)
class _Provenance:
    original: RefreshFileObservation
    raw: bytes
    files: tuple
    original_mode: int | None
    stage: str = "imports-prospective.json"
    retired: str = "imports-original.json"
    target: str = CatalogImportsFile.PATH


def prepare_provenance(stages):
    """Reserve prospective metadata before any public entry effect is possible."""
    plan, ledger = stages.plan, stages._ledger
    source_id, source_identity = catalog_import._read_source_project(
        plan.source_root, ledger
    )
    ancestors = catalog_import._read_source_ancestors(plan.source_root, ledger)
    catalog_import.check_dag_safe(plan.root, source_id, ancestors, ledger)
    if plan._source_lease is None:
        source_root, ref = catalog_import._resolve_local_source(str(plan.source_root))
        if source_root != plan.source_root:
            _fail("canonical local source resolved another root")
    else:
        plan._source_lease.require_current()
        ref = plan._source_lease.reference
        if (plan.document.get("source_lease"), plan.document.get("source_ref")) != (
            plan._source_lease.identity.uri,
            ref,
        ):
            _fail("actual source lease differs from acknowledged copy plan")
    imports = catalog_import._read_imports(plan.root, ledger)
    original = ledger.cache[plan.root / CatalogImportsFile.PATH]
    parent = (plan.root / CatalogImportsFile.PATH).parent
    if not stat.S_ISDIR(parent.lstat().st_mode):
        _fail("direct canonical metadata parent required")
    if original.content is not None:
        node = original.path.lstat()
        if not stat.S_ISREG(node.st_mode) or node.st_nlink != 1:
            _fail("original provenance must be a direct single-link file")
    ledger.charge_records(
        4 * sum(len(entry.files) for entry in stages._entries.values())
        + 4 * len(plan.items),
        4
        * sum(
            len(f.path.encode()) + len(f.identity.encode())
            for entry in stages._entries.values()
            for f in entry.files
        ),
    )
    entries = []
    for kind, name in plan.items:
        target = catalog_import._dest_item_dir(plan.root, kind, name)
        matches = [
            entry
            for entry in stages._entries.values()
            if entry.root.relative_to(entry.container) == target.relative_to(plan.root)
        ]
        if len(matches) != 1:
            _fail("one genuine stage for each selected item required")
        entry = matches[0]
        prefix = entry.root.relative_to(entry.container).as_posix() + "/"
        expected = tuple(
            CatalogImportFile(path, blob.identity)
            for path, blob, _executable in entry.census.tree.files
            if path.startswith(prefix)
        )
        if sorted(expected, key=lambda f: f.path) != sorted(
            entry.files, key=lambda f: f.path
        ):
            _fail("canonical file receipts differ from actual staged payloads")
        entries.append((kind, name, expected))
    # Fund serialization and retained old/prospective observations before making
    # their Python object graph. The original ledger and its ceilings stay fixed.
    bound = 32768 + 12 * len(original.content or b"")
    for path in (
        plan.source_root / CatalogImportsFile.PATH,
        plan.source_root / ".literate/initialization-origin.json",
    ):
        bound += 12 * len(ledger.cache[path].content or b"") * len(entries)
    bound += (
        12
        * (len(source_id.encode()) + len(source_identity.encode()) + len(ref.encode()))
        * len(entries)
    )
    bound += sum(
        4096 + 12 * sum(len(f.path.encode()) + len(f.identity.encode()) for f in files)
        for _kind, _name, files in entries
    )
    if bound > stages.budget.maximum_file_bytes:
        _fail("prospective provenance exceeds original per-file allowance")
    ledger.bytes += 2 * bound
    ledger.files += 4
    ledger.charge_records(
        16 + 4 * sum(len(files) for _kind, _name, files in entries), 2 * bound
    )
    ledger.charged += 128 * bound
    ledger.require_capacity()
    now = datetime.now(UTC).isoformat()
    source = CatalogImportSource(source_id, source_identity, ref, ancestors)
    for kind, name, files in entries:
        imports = imports.with_import(CatalogImport(kind, name, source, files, now))
    raw = (json.dumps(imports.to_dict(), indent=2, ensure_ascii=False) + "\n").encode()
    if len(raw) > bound:
        _fail("prospective provenance exceeded its reserved serialization bound")
    return _Provenance(
        original,
        raw,
        tuple(entries),
        None
        if original.signature is None
        else stat.S_IMODE(original.signature[2]) & 0o777,
    )


def advance_metadata(owner, source, name, destination, target, observed):
    """Advance only the canonical input changed by this exact native move."""

    record = owner._live(writing=True)
    ticket, progress = record[8:10]
    if name in source.nodes or destination.nodes.get(target) != observed:
        _fail("metadata advance requires an actual known native move")
    if source is owner._project and name == ticket.target:
        if (
            destination is not owner._private
            or target != ticket.retired
            or progress["phase"] != "staged"
        ):
            _fail("unexpected original provenance retirement")
        expected = RefreshFileObservation(ticket.original.path, None, None)
        phase = "retired"
    elif destination is owner._project and target == ticket.target:
        if (
            source is not owner._private
            or name != ticket.stage
            or progress["phase"] not in ("staged", "retired")
        ):
            _fail("unexpected prospective provenance publication")
        signature = (
            observed.device,
            observed.inode,
            observed.mode,
            observed.size,
            observed.modified_ns,
            observed.changed_ns,
        )
        expected = RefreshFileObservation(ticket.original.path, signature, ticket.raw)
        phase = "published"
    else:
        return
    # No fresh read becomes authority: bytes are sealed before entry effects;
    # native facts are the verified result of the exclusive move just performed.
    owner._stages._ledger.cache[ticket.original.path] = expected
    progress["expected"], progress["phase"] = expected, phase


def publish_provenance(owner, acknowledged_plan_identity):
    from .catalog_entry_publication import _BUSY, _FAILED, _WRITERS, _digest

    record = owner._live()
    if owner not in _WRITERS:
        _fail("provenance writer ended")
    if owner in _BUSY:
        _FAILED.add(owner)
        _fail("reentrant provenance effects refused")
    if acknowledged_plan_identity != owner._stages.plan.identity:
        _fail("exact original catalog plan acknowledgement required")
    ticket, progress = record[8:10]
    if progress["phase"] != "prepared":
        _fail("provenance is single-use")
    if progress["published"] != set(owner._items):
        _fail("publish every actual selected item before provenance")
    _BUSY.add(owner)
    try:
        owner.require_current()
        for _kind, _name, files in ticket.files:
            for item in files:
                if owner._project.files.get(item.path) != item.identity:
                    _fail("published item differs from actual staged file receipts")
        state = owner._private
        owner._journal(
            "catalog-provenance-intent",
            {
                "original": None
                if ticket.original.content is None
                else _digest(ticket.original.content),
                "original_signature": ticket.original.signature,
                "prospective": _digest(ticket.raw),
                "bytes": len(ticket.raw),
                "stage": ticket.stage,
                "retired": ticket.retired,
            },
        )
        owner.require_current()
        with _pinned_directory(state.root) as (parent, guard):
            owner._live(writing=True)
            flags = (
                os.O_WRONLY
                | os.O_CREAT
                | os.O_EXCL
                | getattr(os, "O_NOFOLLOW", 0)
                | getattr(os, "O_CLOEXEC", 0)
            )
            fd = os.open(ticket.stage, flags, 0o666, dir_fd=parent)
            try:
                view = memoryview(ticket.raw)
                while view:
                    written = os.write(fd, view)
                    if written <= 0:
                        raise OSError("provenance write made no progress")
                    view = view[written:]
                if ticket.original_mode is not None:
                    os.fchmod(fd, ticket.original_mode)
                os.fsync(fd)
                node = _from_stat(os.fstat(fd))
                if node != _from_stat((state.root / ticket.stage).lstat()):
                    _fail("prospective native file changed")
                if (
                    _file(
                        state.root / ticket.stage, maximum_bytes=len(ticket.raw)
                    ).content
                    != ticket.raw
                ):
                    _fail("prospective file bytes changed")
                state.nodes[ticket.stage], state.files[ticket.stage] = (
                    node,
                    _digest(ticket.raw),
                )
                owner._advance_parent(state, "")
                os.fsync(parent)
                guard()
            finally:
                os.close(fd)
        progress["phase"] = "staged"
        owner.require_current()
        owner._journal(
            "catalog-provenance-staged",
            {"node": asdict(node), "identity": _digest(ticket.raw)},
        )
        if ticket.original.content is not None:
            owner._move(
                owner._project,
                ticket.target,
                state,
                ticket.retired,
                kind="retire-provenance",
            )
        owner._move(
            state,
            ticket.stage,
            owner._project,
            ticket.target,
            kind="publish-provenance",
        )
        owner._journal(
            "catalog-provenance-observed",
            {"identity": _digest(ticket.raw), "path": ticket.target},
        )
        owner.require_current()
        return {
            "state": "provenance-published-controls-pending",
            "path": str(ticket.original.path),
            "identity": _digest(ticket.raw),
            "retired": None
            if ticket.original.content is None
            else str(state.root / ticket.retired),
            "grants_imported_roles": False,
        }
    except BaseException:
        _FAILED.add(owner)
        raise
    finally:
        _BUSY.discard(owner)
