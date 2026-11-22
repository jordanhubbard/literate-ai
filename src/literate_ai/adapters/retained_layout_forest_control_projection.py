"""Current control data derived from genuine fresh canonical descriptors.

Raw acquisition already validates original generation and exact durable control
normalization/retirement history. This join matches that inventory to original
source native identities. Incoming entries additionally need actual publication
receipts. No returned description grants a former public name or effect rights.
"""

from __future__ import annotations

import hashlib
import stat
from dataclasses import replace
from pathlib import Path

from literate_ai.contracts.blobs import BlobRef

from .retained_layout_control_publication import _publication_history
from .retained_layout_forest_control_inventory import (
    close_control_inventory,
    control_inventory,
)
from .retained_layout_forest_metadata_replay import _apart
from .retained_layout_forest_program_read import _initial_node
from .retained_layout_forest_span import _SpanRoot
from .retained_layout_journal import _LIVE_ROOTS


def _fail(message):
    raise ValueError("layout.forest-controls: " + message)


def _parent(name):
    value = Path(name).parent.as_posix()
    return "" if value == "." else value


def project_current_controls(value, roles, span, metadata, access):
    """Caller retains all native handles and closes actual roles after payloads."""
    binding = control_inventory(value, roles)
    raw, incoming, inventory = binding.recovered, binding.incoming, binding.inventory
    ledger = value.ledger
    # Unchanged controls need no successor view. Scan the already sealed tuples
    # without allocating whole source maps or duplicating their funding. Still
    # match exact original/current coordinates, native facts and blob commitments;
    # labels alone cannot classify an unchanged marker.
    ledger.charge_records(4 * len(inventory), 1024 * len(inventory))
    unchanged = incoming is None and all(
        owner._plan.retirement_root is None and not owner._plan.recovery_areas
        for owner in raw
    )
    for named, _marker, _fd, node, target, content in inventory:
        if not unchanged:
            break
        if named != target.path:
            unchanged = False
        elif target.path.is_relative_to(value.root):
            name = target.path.relative_to(value.root).as_posix()
            original = next(
                (n for key, n in value.program.span.roots[0].native if key == name),
                None,
            )
            current = next((n for key, n in span.roots[0].native if key == name), None)
            blob = next(
                (b for key, b, _x in span.roots[0].payloads if key == name), None
            )
            unchanged = (
                original == node == current
                and blob is not None
                and blob.size == len(content)
                and blob.digest == hashlib.sha256(content).hexdigest()
            )
    if unchanged:
        return span, ()
    tail = value.frontier.recovery
    generations = () if tail is None else tail.generations
    count = sum(len(root.native) for root in span.roots)
    count += sum(
        1 + len(g.leases) + len(g.publications) + len(g.handoffs) for g in generations
    )
    count += (
        len(value.program.span.roots[0].native)
        + len(inventory)
        + sum(
            len(owner._plan.lineages) + len(owner._plan.recovery_areas) for owner in raw
        )
    )
    paths = sum(
        len(str(row[0]).encode()) + len(str(row[4].path).encode()) for row in inventory
    )
    bodies = sum(len(row[5]) for row in inventory)
    ledger.charge_records(
        128 + 32 * count, 65536 + 8192 * count + 32 * paths + 8 * bodies
    )
    ledger.require_capacity()

    def close_inventory():
        close_control_inventory(value, roles, binding)

    close_inventory()
    generation_index = {g.group: g for g in generations}
    current_targets = {
        t.path: t for t in (*binding.seed.targets(), *binding.git.targets())
    }
    original = dict(value.program.span.roots[0].native)
    nodes = dict(span.roots[0].native)
    payloads = {
        name: (blob, executable) for name, blob, executable in span.roots[0].payloads
    }
    dirty = set()
    retirement_roots = {}
    for owner in raw:
        plan = owner._plan
        lineages = dict(plan.lineages)
        if plan.retirement_root is not None:
            retirement_roots[plan.retirement_root] = lineages[plan.retirement_root]
        for area in plan.recovery_areas:
            previous = retirement_roots.setdefault(area.root, area.lineage)
            if previous != area.lineage:
                _fail("actual retirement root ancestry is ambiguous")

    if retirement_roots and (metadata is None or not metadata.complete):
        _fail("control retirement requires complete bound metadata projection")
    protected = [
        (value.pool.root, value.reader._lineages[value.pool.root]),
        (
            _LIVE_ROOTS[value.journal],
            value.reader._lineages[_LIVE_ROOTS[value.journal]],
        ),
    ]
    storage = value.selection.path.parent
    # A selected store may be inside the project. Its nearest existing anchor
    # remains a physical participant even if storage itself is absent.
    storage_anchor, storage_lineage = ledger.ancestry[value.selection.path]
    private = {}
    for root, lineage in retirement_roots.items():
        for current in span.roots:
            _apart(root, lineage, current.root, current.lineage)
        for other, other_lineage in protected:
            _apart(root, lineage, other, other_lineage)
        if (
            root.is_relative_to(storage)
            or storage.is_relative_to(root)
            or lineage[-1][1:3] in {row[1:3] for row in storage_lineage}
            or (
                storage_anchor == storage
                and storage_lineage[-1][1:3] in {row[1:3] for row in lineage}
            )
        ):
            _fail("retirement root overlaps actual canonical storage")
        for other, (other_lineage, _node) in private.items():
            _apart(root, lineage, other, other_lineage)
        close_inventory()
        access.add(root, lineage)
        close_inventory()
        node = access.read(root)
        close_inventory()
        if (
            node is None
            or node.directory_identity[:-1] != lineage[-1][1:]
            or stat.S_IMODE(node.mode) != 0o700
        ):
            _fail("actual retirement root changed its pinned identity")
        if root == metadata.retirement_root and (
            lineage != metadata.retirement_lineage
            or node.directory_identity != metadata.retirement_node.directory_identity
        ):
            _fail("retirement root differs from original bound future-effects pin")
        # The first generation must use the actual original bound root. Later
        # recovery areas are admitted only by actual raw plan provenance.
        if (
            any(o._plan.retirement_root == root for o in raw)
            and root != metadata.retirement_root
        ):
            _fail("original retirement root differs from its bound coordinate")
        private[root] = lineage, node

    retired = {root: {} for root in private}
    retired_payloads = {root: {} for root in private}
    seen_original = set()
    supplemental = {}
    records_by_group = {
        owner._plan.group: {
            record.target.path: record for record in owner._plan.markers
        }
        for owner in raw
    }
    if len(records_by_group) != len(raw):
        _fail("actual raw generation repeated")
    original_groups = set()

    def payload(content):
        # These bytes are actual authenticated descriptor inventory, never a
        # hash of unknown source bytes or an inferred marker basename.
        return BlobRef(hashlib.sha256(content).hexdigest(), len(content)), False

    for owner in raw:
        for record in owner._plan.markers:
            target, named, current, content = (
                record.target.path,
                record.named,
                record.node,
                record.content,
            )
            if named != target:
                if named.parent not in retired or named.name in retired[named.parent]:
                    _fail("retired descriptor lacks its complete actual private root")
                retired[named.parent][named.name] = current
                retired_payloads[named.parent][named.name] = payload(content)
            if owner._plan.group in generation_index:
                supplemental.setdefault(owner._plan.group, []).append(record)
                continue
            original_groups.add(owner._plan.group)
            if not target.is_relative_to(value.root):
                continue
            name = target.relative_to(value.root).as_posix()
            if name not in value.saved.document["partition"]["document"]["controls"]:
                _fail("original raw descriptor is not a declared source control")
            before = original.get(name)
            if (
                before is None
                or name in seen_original
                or (before.device, before.inode) != (current.device, current.inode)
                or nodes.get(name) != before
                or name not in payloads
            ):
                _fail("raw descriptor differs from its original complete source node")
            seen_original.add(name)
            if named == target:
                # Raw creation validates normalization intent/observed bytes.
                # The original inode and immutable native properties stay fixed.
                immutable = ("device", "inode", "mode", "links", "uid", "gid")
                if any(getattr(before, k) != getattr(current, k) for k in immutable):
                    _fail("current original marker changed immutable native facts")
                if current != before and (metadata is None or not metadata.complete):
                    _fail("normalization requires complete original metadata")
                nodes[name], payloads[name] = current, payload(content)
            else:
                if (
                    record.target.advisory
                    or current.after_rename() != before.after_rename()
                ):
                    _fail("retirement changed original native custody")
                del nodes[name]
                del payloads[name]
                dirty.add((0, _parent(name)))

    proven = set(original_groups)
    for generation in generations:
        records = supplemental.get(generation.group)
        if records is None:
            continue
        if metadata is None or not metadata.complete:
            _fail("supplemental controls require complete bound original metadata")
        leases = {Path(row["path"]): row for row in generation.leases}
        publications = {
            Path(row["destination"]): row for row in generation.publications
        }
        if {r.target.path for r in records} != set(leases):
            _fail("actual supplemental descriptors do not cover their complete group")
        for record in records:
            target, named, current, content = (
                record.target.path,
                record.named,
                record.node,
                record.content,
            )
            selected = current_targets.get(target)
            lease, publication = leases.get(target), publications.get(target)
            if (
                selected is None
                or selected.advisory is not False
                or record.target.advisory is not False
                or lease is None
                or lease["advisory"] is not False
                or publication is None
                or publication["directory"] is not False
                or publication["payload_digest"] != lease["payload_digest"]
                or hashlib.sha256(content).hexdigest() != lease["payload_digest"]
            ):
                _fail(
                    "supplemental marker lacks actual canonical/publication provenance"
                )
            before = _initial_node(lease["node"])
            published_node = _initial_node(publication["published_node"])
            if (
                published_node != before
                or current.after_rename() != before.after_rename()
            ):
                _fail(
                    "supplemental native custody differs from its original publication"
                )
            parents = []
            for handoff in generation.handoffs:
                if any(
                    Path(path) == target and _initial_node(node) == before
                    for path, node in handoff["incoming_nodes"]
                ):
                    previous_group = handoff["old_group"]
                    previous = records_by_group.get(previous_group, {}).get(target)
                    if (
                        previous_group not in proven
                        or previous is None
                        or previous.named == target
                        or previous.target.advisory
                    ):
                        _fail(
                            "supplemental handoff lacks actual old private descriptors"
                        )
                    parents.append(previous)
            if not parents:
                _fail("supplemental marker lacks original private descriptor lineage")
            if named == target:
                if current != before:
                    _fail(
                        "public supplemental marker changed its recorded native facts"
                    )
                if target.is_relative_to(value.root):
                    name = target.relative_to(value.root).as_posix()
                    if name in nodes or _parent(name) not in nodes:
                        _fail(
                            "supplemental public marker collides with retained source"
                        )
                    nodes[name], payloads[name] = current, payload(content)
                    dirty.add((0, _parent(name)))
            elif named.parent not in retired:
                _fail("supplemental private marker lost its complete retirement root")
        proven.add(generation.group)
    if set(supplemental) - proven:
        _fail("supplemental descriptors lack a closed original generation chain")

    if incoming is not None:
        history = _publication_history(value.pool)
        ledger.charge_records(16 * len(history), 4096 * len(history))
        published = {item.path: item for item in history}
        if len(published) != len(history):
            _fail("actual incoming publications are ambiguous")
        for path, basic, target in sorted(
            incoming._directories, key=lambda row: len(row[0].parts)
        ):
            receipt = published.get(path)
            if (
                receipt is None
                or receipt.content is not None
                or receipt.node.directory_identity[:3] != basic
                or target not in binding.missing
            ):
                _fail("actual incoming parent publication required")
            if path.is_relative_to(value.root):
                name = path.relative_to(value.root).as_posix()
                if name in nodes or _parent(name) not in nodes:
                    _fail("incoming directory collides with original source")
                nodes[name] = receipt.node
                dirty.add((0, _parent(name)))
                dirty.add((0, name))
        for marker in incoming._markers:
            target = marker.target.path
            receipt = published.get(target)
            current = incoming._expected.get(target)
            if (
                receipt is None
                or receipt.node != current
                or receipt.content != marker.content
                or marker.target not in binding.missing
                or not marker.created
            ):
                _fail("actual incoming marker publication required")
            if not target.is_relative_to(value.root):
                continue
            name = target.relative_to(value.root).as_posix()
            if name in nodes or _parent(name) not in nodes:
                _fail("incoming public marker collides with retained source")
            nodes[name], payloads[name] = current, payload(marker.content)
            dirty.add((0, _parent(name)))

    roots = list(span.roots)
    roots[0] = replace(
        roots[0],
        native=tuple(sorted(nodes.items())),
        payloads=tuple((name, *row) for name, row in sorted(payloads.items())),
    )
    for root, (lineage, node) in private.items():
        roots.append(
            _SpanRoot(
                root,
                lineage,
                (("", node), *sorted(retired[root].items())),
                tuple(
                    (name, *row) for name, row in sorted(retired_payloads[root].items())
                ),
            )
        )
    close_inventory()
    return replace(span, roots=tuple(roots)), tuple(sorted(dirty))
