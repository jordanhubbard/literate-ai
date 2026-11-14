"""Actual catalog application handed once to a fresh retained-source owner."""

from __future__ import annotations

import os
import stat
import threading
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass
from pathlib import Path

from literate_ai.contracts.catalog_imports import CatalogImportsFile
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget

from .catalog_copy_plan import _anchor, _Observation, _root, plan_catalog_copy
from .catalog_copy_staging import staged_catalog_copies
from .exclusive_entry import _from_stat
from .repository_refresh import _raw_file, _signature
from .retained_cargo_tree_v2 import capture_retained_cargo_tree_v2
from .retained_layout_control_publication import (
    _pinned_directory,
    staged_layout_controls,
)
from .retained_layout_control_roles import acquire_retained_layout_control_roles
from .retained_layout_journal import (
    _RECORD_LIMIT,
    LayoutJournalBudget,
    retained_layout_journal,
)
from .retained_layout_partition import _lineage
from .retained_layout_transaction import _native_tree

_LIVE = {}
_TRANSFERS = {}


def _fail(message):
    raise ValueError("catalog.copy-roles: " + message)


@dataclass(frozen=True, slots=True)
class _Seal:
    identity: object
    project: object
    private: tuple
    inputs: tuple
    ancestry: tuple
    source_censuses: tuple
    source_native: tuple
    targets: tuple
    lineages: tuple
    provenance: object
    original_provenance: object
    ledger: object
    view_budget: object
    view_metadata: int


def _binding(record):
    return (
        record["state"],
        record["seal"],
        record["stages"],
        record["controls"],
        record["guard"],
        record["nonce"],
        record["descriptor"],
        record["root_node"],
    )


def _close_record(owner, record, original):
    """Final original lifetime check, without guard or native callbacks."""
    if (
        _LIVE.get(owner) is not record
        or record["pid"] != os.getpid()
        or record["thread"] != threading.get_ident()
        or record["failed"]
        or record["spent"]
        or record["state"] != original[0]
        or any(
            a is not b
            for a, b in zip(
                (record["seal"], record["stages"], record["controls"], record["guard"]),
                original[1:5],
                strict=True,
            )
        )
        or (record["nonce"], record["descriptor"], record["root_node"]) != original[5:]
    ):
        _fail("original copy producer lifetime or phase ended")


def _record(owner, *, ready=False):
    if type(owner) is not _CatalogCopyRoles:
        raise TypeError("actual live catalog-copy producer required")
    record = _LIVE.get(owner)
    if record is None:
        raise TypeError("actual live catalog-copy producer required")
    if (
        record["pid"] != os.getpid()
        or record["thread"] != threading.get_ident()
        or record["failed"]
        or record["spent"]
    ):
        _fail("copy producer ended, interrupted or spent")
    if ready and record["state"] != "ready":
        _fail("actual successful catalog application and teardown required")
    original = _binding(record)
    record["guard"]()
    if (
        _from_stat(os.fstat(record["descriptor"])) != record["root_node"]
        or _from_stat(record["root"].lstat()) != record["root_node"]
    ):
        _fail("actual producer private root node changed")
    _close_record(owner, record, original)
    return record


def _accept_receiver(receiver, producer):
    from .catalog_entry_publication import _OWNERS, _WRITERS

    record = _record(producer)
    actual = receiver._live()
    stages = record["stages"]
    if (
        record["state"] != "applying"
        or receiver not in _WRITERS
        or receiver._stages is not stages
        or receiver._controls is not record["controls"]
        or _OWNERS.get(stages) is not actual
        or not actual[11]["complete"]
        or actual[9]["phase"] != "published"
    ):
        _fail("actual completed creating catalog receiver required")
    receiver.require_current()
    control_paths = {m.target.path for m in actual[10].markers}
    ledger = stages._ledger
    # These exact endpoints belong to the old control acquisition. Fresh source
    # roles must acquire their own actual descriptors; no old control is a copy
    # role. Preserve all original cache/history, taking a filtered read inventory.
    inputs = tuple(
        item for path, item in ledger.cache.items() if path not in control_paths
    )
    targets = tuple(target for _source, target in receiver._items.values())
    provenance = ledger.cache[stages.plan.root / CatalogImportsFile.PATH]
    identity = canonical_identity(
        {
            "schema": "literate-ai/catalog-copy-handoff@1",
            "nonce": record["nonce"],
            "plan": stages.plan.identity.uri,
            "provenance": receiver._project.files[CatalogImportsFile.PATH],
        }
    )
    seal = _Seal(
        identity,
        receiver._project,
        (receiver._private, *receiver._control_views),
        inputs,
        tuple((i.path, ledger.ancestry[i.path]) for i in inputs),
        stages.plan._censuses[1:],
        stages.plan._native[1:],
        targets,
        tuple(
            (stages.plan.root / target, _lineage(stages.plan.root / target))
            for target in targets
        ),
        provenance,
        actual[8].original,
        ledger,
        receiver._view_budget,
        receiver._view_metadata,
    )
    receiver.require_current()
    record["seal"] = seal
    _TRANSFERS[stages] = receiver, producer


def _transferred(receiver):
    value = _TRANSFERS.get(receiver._stages)
    if value is None or value[0] is not receiver:
        return False
    record = _record(value[1])
    if (
        record["state"] != "applying"
        or record["seal"] is None
        or record["stages"] is not receiver._stages
        or record["controls"] is not receiver._controls
    ):
        _fail("creating producer transfer changed")
    receiver.require_current()
    return True


def _revoked(stages):
    _TRANSFERS.pop(stages, None)


class _CatalogCopyRoles:
    @property
    def plan(self):
        return _record(self)["stages"].plan

    @property
    def identity(self):
        return _record(self, ready=True)["seal"].identity

    @property
    def provenance(self):
        return _record(self, ready=True)["seal"].provenance

    @property
    def paths(self):
        seal = _record(self, ready=True)["seal"]
        return tuple(
            sorted(
                name
                for name in seal.project.files
                if any(name == p or name.startswith(p + "/") for p in seal.targets)
            )
        )

    @property
    def directories(self):
        seal = _record(self, ready=True)["seal"]
        return tuple(
            sorted(
                name
                for name, node in seal.project.nodes.items()
                if stat.S_ISDIR(node.mode)
                and any(name == p or name.startswith(p + "/") for p in seal.targets)
            )
        )

    @property
    def document(self):
        record = _record(self, ready=True)
        return {
            "schema": "literate-ai/catalog-copy-role-observation@1",
            "identity": self.identity.uri,
            "plan": record["stages"].plan.identity.uri,
            "paths": list(self.paths),
            "directories": list(self.directories),
            "qualified": False,
        }

    def apply(self, *, acknowledged_plan_identity):
        from .catalog_entry_publication import _registered, catalog_entry_publication

        record = _record(self)
        if record["state"] != "prepared":
            _fail("one actual unspent copy application required")
        if acknowledged_plan_identity != self.plan.identity:
            _fail("exact prepared catalog plan acknowledgement required")
        record["state"] = "applying"
        try:
            stages, controls = record["stages"], record["controls"]
            # Fund small immutable handoff records before the first entry effect;
            # namespace maps transfer by identity rather than being copied.
            stages._ledger.charge_records(16 + 2 * len(stages.plan.items), 8192)
            tokens = tuple(stages.stage_item(i) for i in range(len(stages.plan.items)))
            with catalog_entry_publication(
                stages, controls, control_journal_root=record["root"] / "journal"
            ) as receiver:
                for token in tokens:
                    receiver.publish(
                        token, acknowledged_plan_identity=stages.plan.identity
                    )
                receiver.publish_provenance(
                    acknowledged_plan_identity=stages.plan.identity
                )
                receiver.finalize_controls(
                    acknowledged_plan_identity=stages.plan.identity
                )
                _accept_receiver(receiver, self)
            # The original factories perform all normal closing checks and
            # revoke observation before descriptor teardown. No readiness on an
            # exception, even when catalog effects have already committed.
            record["resources"].close()
            if stages._active or controls._active or _registered(stages):
                _fail("original catalog resource stack has not ended")
            record["state"] = "ready"
            self.require_current()
            if record["framework_update"] is not None:
                record["framework_update"].accept_catalog_successor(self)
            return self.document
        except BaseException:
            record["failed"] = True
            raise

    def require_current(self):
        from .catalog_entry_publication import _digest, _payloads

        record = _record(self, ready=True)
        original = _binding(record)
        seal = record["seal"]
        try:
            seal.ledger.require_capacity()
            for item in seal.inputs:
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
                    _fail("original producer input changed")
            for census in seal.source_censuses:
                census.require_unchanged()
            for state in seal.private:
                tree = capture_retained_cargo_tree_v2(
                    state.root,
                    budget=seal.view_budget,
                    maximum_metadata_bytes=seal.view_metadata,
                )
                if dict(_native_tree(tree)) != state.nodes or _payloads(tree) != (
                    state.files,
                    state.links,
                ):
                    _fail("retained actual private catalog state changed")
            for target in seal.targets:
                tree = capture_retained_cargo_tree_v2(
                    seal.project.root / target,
                    budget=seal.view_budget,
                    maximum_metadata_bytes=seal.view_metadata,
                )
                native = {
                    target + ("/" + name if name else ""): node
                    for name, node in _native_tree(tree)
                }
                files, links = _payloads(tree)
                if (
                    native != seal.project.subset(target)
                    or {target + "/" + name: value for name, value in files.items()}
                    != {
                        name: value
                        for name, value in seal.project.files.items()
                        if name.startswith(target + "/")
                    }
                    or links
                ):
                    _fail("actual copied subtree changed")
            with os.scandir(record["descriptor"]) as entries:
                names = set()
                for entry in entries:
                    if len(names) >= 3:
                        _fail("producer private root acquired foreign entries")
                    names.add(entry.name)
            if names != {"controls", "copies", "journal"}:
                _fail("actual producer private root namespace changed")
            if (
                _digest(seal.provenance.content)
                != seal.project.files[CatalogImportsFile.PATH]
            ):
                _fail("sealed provenance observation changed")
            self.close_native()
            _close_record(self, record, original)
        except BaseException:
            record["failed"] = True
            raise

    def close_native(self):
        record = _record(self, ready=True)
        original = _binding(record)
        seal = record["seal"]
        for path, expected in seal.ancestry:
            if _anchor(path) != expected:
                _fail("original producer input ancestry changed")
        for item in seal.inputs:
            if (
                _signature(item.path) if os.path.lexists(item.path) else None
            ) != item.signature:
                _fail("original producer input node changed")
        for path, lineage in seal.lineages:
            if _lineage(path) != lineage:
                _fail("actual copied ancestry changed")
        for census, native in zip(
            seal.source_censuses, seal.source_native, strict=True
        ):
            if _lineage(census.tree.root) != census._lineage:
                _fail("original source-provider ancestry changed")
            for name, expected in native:
                if _from_stat((census.tree.root / name).lstat()) != expected:
                    _fail("original source-provider node changed")
        for state in seal.private:
            for name, expected in state.nodes.items():
                if _from_stat((state.root / name).lstat()) != expected:
                    _fail("actual private catalog node changed")
        for target in seal.targets:
            for name, expected in seal.project.subset(target).items():
                if _from_stat((seal.project.root / name).lstat()) != expected:
                    _fail("actual copied node changed")
        record["guard"]()
        if (
            _from_stat(os.fstat(record["descriptor"])) != record["root_node"]
            or _from_stat(record["root"].lstat()) != record["root_node"]
        ):
            _fail("actual producer private root node changed")

        _close_record(self, record, original)

    def bind(self, root):
        self.require_current()
        if root != _record(self, ready=True)["seal"].project.root:
            _fail("handoff belongs to another project")
        return self.identity.uri

    def require_plan(self, plan):
        seal = _record(self, ready=True)["seal"]
        if (
            plan.root != seal.project.root
            or plan.catalog_copy != self.identity.uri
            or plan.catalog_provenance != seal.provenance
        ):
            _fail("fresh source plan does not bind actual copy/provenance")
        moving = {
            plan.tree._physical[0][:2],
            *(node[:2] for _name, node in plan.tree._physical[1]),
        }
        if any(
            item.signature is not None and item.signature[:2] in moving
            for item in seal.inputs
        ) or any(
            (node.device, node.inode) in moving
            for native in seal.source_native
            for _name, node in native
        ):
            _fail("actual copy provider/input physically overlaps moving source")
        for _path, (_anchor_path, lineage) in seal.ancestry:
            if moving & {entry[1:3] for entry in lineage}:
                _fail("original copy provider/input overlaps moving source")
        for state in seal.private:
            if moving & {(n.device, n.inode) for n in state.nodes.values()}:
                _fail("actual copy private state overlaps moving source")

    def remaining(self, budget, metadata):
        seal = _record(self, ready=True)["seal"]
        ledger = seal.ledger
        if metadata > ledger.metadata or any(
            getattr(budget, name) > getattr(ledger.budget, name)
            for name in (
                "maximum_files",
                "maximum_entries",
                "maximum_file_bytes",
                "maximum_total_bytes",
            )
        ):
            _fail("ownership cannot enlarge original shared copy policy")
        files, entries = (
            budget.maximum_files - ledger.files,
            budget.maximum_entries - ledger.records,
        )
        total = budget.maximum_total_bytes - ledger.bytes - ledger.reserve
        metadata -= ledger.charged
        if min(files, entries, total, metadata) < 1:
            _fail("copy leaves no complete ownership allowance")
        files = min(files, entries)
        per_file = min(budget.maximum_file_bytes, total)
        return RetainedCargoInputBudget(
            files, entries, per_file, min(total, files * per_file)
        ), metadata

    def require_framework(self, update):
        record = _record(self, ready=True)
        if (
            record["framework_update"] is not update
            or not record["framework_included"]
            or update._catalog_successor is not self
        ):
            _fail("actual included framework predecessor required")

    def spend(self):
        self.require_current()
        record = _record(self, ready=True)
        _close_record(self, record, _binding(record))
        record["spent"] = True


def _require_handoff(value):
    _record(value, ready=True)
    return value


def _framework_successor(value, update):
    """Return only the actual expected predecessor's owned metadata transition."""
    record = _record(value, ready=True)
    if (
        record["framework_update"] is not update
        or record["framework_identity"] != update.identity
    ):
        _fail("catalog successor belongs to another actual framework producer")
    value.require_current()
    seal = record["seal"]
    return seal.original_provenance, seal.provenance, seal.identity


def _reserve_framework_successor(value, update, *, total, metadata, entries, files):
    record = _record(value, ready=True)
    if record["framework_update"] is not update or not record["framework_included"]:
        _fail("actual included framework predecessor required for successor budget")
    ledger = record["seal"].ledger
    ledger.bytes += total
    ledger.files += files
    ledger.records += entries
    ledger.charged += metadata
    ledger.require_capacity()


@contextmanager
def prepared_catalog_copy_roles(
    root,
    source_root,
    item_specs,
    *,
    private_root,
    budget,
    maximum_metadata_bytes,
    control_journal_budget,
    copy_journal_budget,
    overwrite=False,
    framework_update=None,
):
    """Internal producer: apply exact plan, then borrow live roles after teardown.

    Unapplied/interrupted contexts retain their actual controls for recovery;
    they issue no ownership. This is not the complete public catalog command.
    """
    root, source_root, private_root = (
        _root(root),
        _root(source_root),
        Path(private_root),
    )
    if type(budget) is not RetainedCargoInputBudget or any(
        type(policy) is not LayoutJournalBudget
        for policy in (control_journal_budget, copy_journal_budget)
    ):
        _fail("original typed copy and journal policies required")
    control_journal_budget.validate()
    copy_journal_budget.validate()
    if (
        max(
            _RECORD_LIMIT,
            control_journal_budget.maximum_payload_bytes,
            copy_journal_budget.maximum_payload_bytes,
        )
        > budget.maximum_file_bytes
    ):
        _fail("journal read ceiling exceeds original shared file policy")
    if (
        not private_root.is_absolute()
        or ".." in private_root.parts
        or any(
            private_root.is_relative_to(p) or p.is_relative_to(private_root)
            for p in (root, source_root)
        )
    ):
        _fail("direct private root outside project/source required")
    with _pinned_directory(private_root) as (descriptor, guard):
        node = os.fstat(descriptor)
        if (
            node.st_uid != os.geteuid()
            or stat.S_IMODE(node.st_mode) != 0o700
            or node.st_dev != root.stat().st_dev
        ):
            _fail("owned mode0700 private root on project filesystem required")
        private_identity = node.st_dev, node.st_ino
        private_lineage = {entry[1:3] for entry in _lineage(private_root)}
        for path in (root, source_root):
            observed = path.stat()
            if (
                observed.st_dev,
                observed.st_ino,
            ) in private_lineage or private_identity in {
                entry[1:3] for entry in _lineage(path)
            }:
                _fail("producer private root physically overlaps project/source")
        with os.scandir(descriptor) as entries:
            if next(entries, None) is not None:
                _fail("empty private producer root required")
        owner, stages, resources = _CatalogCopyRoles(), None, ExitStack()
        try:
            framework_identity = None
            if framework_update is not None:
                from .framework_update_roles import _require_handoff as require_update

                require_update(framework_update).bind(root)
                framework_identity = framework_update.identity
            ledger = _Observation(budget, maximum_metadata_bytes, (root, source_root))
            if framework_update is not None:
                # The predecessor remains live. Debit its actual retained work
                # before copy planning; the one sequential peak buffer is shared.
                ledger.bytes += framework_update._used_bytes
                ledger.files += framework_update._used_files
                ledger.records += framework_update._used_entries
                ledger.charged += max(
                    0, framework_update._used_metadata - 64 * framework_update._reserve
                )
                ledger.require_capacity()
            # Hold setup's actual journal capacity before resource entry; retain
            # the real usage and refund only unused storage after verified setup.
            journal_files = (
                8
                + 2 * control_journal_budget.maximum_events
                + control_journal_budget.maximum_stages
            )
            ledger.bytes += control_journal_budget.maximum_storage_bytes
            ledger.files += journal_files
            ledger.charge_records(
                journal_files, control_journal_budget.maximum_storage_bytes
            )
            os.mkdir("controls", 0o700, dir_fd=descriptor)
            journal = resources.enter_context(
                retained_layout_journal(
                    private_root / "journal",
                    canonical_binding=b"{}",
                    budget=control_journal_budget,
                )
            )
            pool = resources.enter_context(
                staged_layout_controls(private_root / "controls", journal)
            )
            controls = resources.enter_context(
                acquire_retained_layout_control_roles(
                    root, pool, _catalog_ledger=ledger
                )
            )
            journal.require_current()
            unused = control_journal_budget.maximum_storage_bytes - sum(
                len(raw) for _node, raw in journal._known.values()
            )
            ledger.bytes -= unused
            ledger.charged -= 64 * unused
            ledger.require_capacity()
            plan = plan_catalog_copy(
                root,
                source_root,
                item_specs,
                budget=budget,
                maximum_metadata_bytes=maximum_metadata_bytes,
                overwrite=overwrite,
                _control_ledger=ledger,
            )
            os.mkdir("copies", 0o700, dir_fd=descriptor)
            stages = resources.enter_context(
                staged_catalog_copies(
                    private_root / "copies",
                    plan,
                    journal_budget=copy_journal_budget,
                    _control_ledger=ledger,
                )
            )
            _LIVE[owner] = {
                "nonce": os.urandom(16).hex(),
                "pid": os.getpid(),
                "thread": threading.get_ident(),
                "root": private_root,
                "descriptor": descriptor,
                "root_node": _from_stat(os.fstat(descriptor)),
                "guard": guard,
                "stages": stages,
                "controls": controls,
                "resources": resources,
                "state": "prepared",
                "seal": None,
                "spent": False,
                "failed": False,
                "framework_update": framework_update,
                "framework_identity": framework_identity,
                "framework_included": framework_update is not None,
            }
            yield owner
            if not _LIVE[owner]["spent"]:
                owner.require_current()
        except BaseException as error:
            resources.__exit__(type(error), error, error.__traceback__)
            raise
        finally:
            try:
                resources.close()
            finally:
                if stages is not None:
                    _TRANSFERS.pop(stages, None)
                _LIVE.pop(owner, None)
