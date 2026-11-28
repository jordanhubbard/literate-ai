"""Receipt-backed metadata successor of an actual funded source movement.

Original plans and producer witnesses remain immutable. Quarantined originals
and current public nodes are separate observations, never fresh baselines.
"""

from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass, replace
from pathlib import Path

from .exclusive_entry import _from_stat, layout_entry_node
from .repository_refresh import RefreshFileObservation, _file, _raw_file, _signature
from .retained_layout_source_admission import _control_reads, _fail, _phase_record
from .retained_layout_transaction import _bind_original_source_metadata_ports
from .retained_scaffold_coordinates import retained_scaffold_path

_METADATA = {}
_AREAS = {}
_UNSET = object()


@dataclass(frozen=True, slots=True)
class _Step:
    source: Path
    destination: Path
    content: bytes
    public: Path
    quarantine: bool


@dataclass(frozen=True, slots=True)
class _Metadata:
    admission: object
    root: Path
    lineage: tuple
    original_root: object
    inputs: tuple
    steps: tuple
    active: bool = True
    area: object = None
    descriptor: object = None
    guard: object = None
    root_node: object = None
    known: tuple = ()
    stages: tuple = ()
    cursor: int = 0
    receipts: tuple = ()
    history: tuple = ()
    observed: bool = False
    published: bool = False


def _record(phase, *, pending_inputs=False):
    value = _METADATA.get(phase)
    if value is None:
        return None
    if _phase_record(phase) is not value.admission:
        _fail("actual original metadata admission required")
    if not pending_inputs and phase._current_inputs is not value.inputs:
        _fail("original metadata input inventory changed")
    if value.area is not None and (
        _AREAS.get(value.area) is not phase
        or phase._metadata_area is not value.area
        or value.area.root != value.root
        or value.area.descriptor != value.descriptor
        or value.area.guard is not value.guard
        or value.area.journal is not phase.pool._journal
        or value.area.maximum_entries != 6
        or value.area.pid != os.getpid()
    ):
        _fail("actual original metadata area changed or ended")
    return value


def _advance(phase, before, **changes):
    if _METADATA.get(phase) is not before:
        _fail("original metadata transition predecessor changed")
    after = replace(before, **changes)
    _METADATA[phase] = after
    return after


def _require_metadata_authority(phase):
    admission = _phase_record(phase)
    if admission is None:
        return None
    value = _record(phase)
    if value is None or not value.active or value.observed:
        _fail("actual original metadata publication call required")
    return value


def _run_metadata_publication(phase, private_root):
    from .retained_layout_partition import _lineage
    from .retained_layout_source_movement import _require_movement_current

    phase._live()
    admission = _phase_record(phase)
    if admission is None:
        return phase._publish_metadata(private_root)
    if phase in _METADATA or phase._metadata_attempted or phase._moved is None:
        _fail("actual moved source and one unattempted metadata publication required")
    _require_movement_current(admission)
    root = Path(private_root)
    if not root.is_absolute() or ".." in root.parts:
        _fail("direct absolute private metadata root required")
    ledger, reader = admission.original.ledger, admission.original.reader
    from .retained_layout_transaction import _metadata_names

    names = _metadata_names(phase.plan.root)
    prospective = dict(phase.plan.prospective)
    original = {item.path: item for item in phase.plan.inputs}
    steps = []
    for index, name in enumerate(names):
        path = phase.plan.root / name
        if len(prospective[name]) > ledger.budget.maximum_file_bytes:
            _fail("prospective metadata exceeds original per-file allowance")
        if original[path].content is not None:
            steps.append(
                _Step(path, root / f"old-{index}", original[path].content, path, True)
            )
        steps.append(_Step(root / f"new-{index}", path, prospective[name], path, False))
    from .retained_layout_forest_effects import _metadata_allowance

    records, payload, size, step_count = _metadata_allowance(
        phase.plan.root,
        root,
        prospective,
        phase.plan.inputs,
        len(admission.movement.expected[1]),
    )
    if step_count != len(steps):
        _fail("metadata allowance differs from exact publication schedule")
    from .retained_layout_source_forest_movement import _prepaid

    prepaid = _prepaid(admission, "metadata", root, (records, payload, size))
    if not prepaid:
        remaining = (
            ledger.budget.maximum_entries - ledger.records,
            ledger.budget.maximum_total_bytes - ledger.bytes - ledger.reserve,
            ledger.metadata - ledger.charged,
        )
        required = records, payload, 4096 * records + 64 * size
        if any(
            need > available
            for need, available in zip(required, remaining, strict=True)
        ):
            _fail(
                "metadata preflight exceeds original allowance: "
                f"required={required}, remaining={remaining}"
            )
        ledger.bytes += payload
        ledger.charge_records(records, size)
    with _control_reads(admission.preparation, admission.pool):
        lineage = _lineage(root)
        node = layout_entry_node(root)
        if prepaid and (node != prepaid.node or lineage != prepaid.lineage):
            _fail("metadata area differs from its original pre-movement pin")
        if node.uid != os.geteuid() or stat.S_IMODE(node.mode) != 0o700:
            _fail("owned mode0700 metadata area required")
        identity = node.device, node.inode
        for other in (phase.plan.root, phase.pool.root, admission.journal_root):
            other_lineage = _lineage(other)
            if identity in {row[1:3] for row in other_lineage} or other_lineage[-1][
                1:3
            ] in {row[1:3] for row in lineage}:
                _fail(
                    "private metadata physically overlaps project or original producer"
                )
        _separate_predecessor_state(admission, lineage)
        for index, name in enumerate(names):
            for prefix in ("new", "old"):
                if (
                    reader.file(
                        root / f"{prefix}-{index}",
                        optional=True,
                        maximum_bytes=ledger.budget.maximum_file_bytes,
                    ).content
                    is not None
                ):
                    _fail("private metadata endpoint is occupied")
            if name in names[1:]:
                reader.json_value(prospective[name], str(phase.plan.root / name))
        value = _Metadata(
            admission, root, lineage, node, phase._current_inputs, tuple(steps)
        )
        _METADATA[phase] = value
        try:
            result = phase._publish_metadata(root)
        except BaseException:
            admission.failed = True
            raise
        finally:
            current = _METADATA[phase]
            _advance(phase, current, active=False)
    try:
        _require_movement_current(admission)
        value = _record(phase)
        if not value.observed or value.cursor != len(value.steps):
            _fail("actual complete metadata publication required")
        _advance(phase, value, published=True)
        phase._metadata_published = True
        _record(phase)
        return result
    except BaseException:
        admission.failed = True
        raise


def _separate_predecessor_state(
    admission, candidate_lineage, *, _before_movement=False
):
    """Keep original producer state and catalog source inputs read-only."""
    from .component_lock_observation import _separate_effects as separate_storage
    from .retained_layout_partition import _lineage
    from .retained_layout_source_movement import _consumed_predecessor

    if type(_before_movement) is not bool:
        _fail("exact predecessor phase required")
    if _before_movement:
        if (
            _phase_record(admission.phase) is not admission
            or admission.movement is not None
            or admission.phase._attempted
            or admission.partition is None
        ):
            _fail("actual unspent original partition required for future effect areas")
        admission.partition._require_eligible()
    separate_storage(admission.preparation, candidate_lineage)

    roots = []
    catalog = admission.original.catalog
    if catalog is not None:
        if not _before_movement and _consumed_predecessor(catalog) is not admission:
            _fail("actual consumed catalog predecessor required")
        record = admission.catalog_lifetime[0]
        node = record["root_node"]
        roots.append((record["root"], (node.device, node.inode)))
        seal = record["seal"]
        source_root = record["stages"].plan.source_root
        original_source = {
            row[1:3]
            for census in seal.source_censuses
            for row in census._lineage
            if Path(row[0]) == source_root
        }
        if len(original_source) != 1:
            _fail("original complete catalog source-root ancestry required")
        roots.append((source_root, next(iter(original_source))))
        if record["source_lifetime"] is not None:
            source_record, _binding = record["source_lifetime"]
            for path, _descriptor, _guard, original_node in source_record["pinned"]:
                roots.append((path, (original_node.device, original_node.inode)))
        for namespace in seal.private:
            node = namespace.nodes[""]
            roots.append((namespace.root, (node.device, node.inode)))
        for census, native in zip(
            seal.source_censuses, seal.source_native, strict=True
        ):
            if not native or native[0][0] != "":
                _fail("original catalog source root receipt required")
            node = native[0][1]
            roots.append((census.tree.root, (node.device, node.inode)))
    framework = admission.original.framework
    if framework is not None:
        if not _before_movement and _consumed_predecessor(framework) is not admission:
            _fail("actual consumed framework predecessor required")
        if framework._retirement_directory is not None:
            roots.append(
                (framework._retirement_directory, framework._retirement_facts[:2])
            )
        provider = getattr(framework, "_git", None)
        if provider is not None:
            roots.extend(
                (path, provider.directories[path][:2])
                for path in provider.git_paths[:2]
            )
            roots.extend(
                (path, signature[:2]) for path, signature in provider.object_stores
            )
    from .retained_layout_source_provider import _separate_effects as separate_provider

    separate_provider(admission, candidate_lineage)
    candidate_identity = candidate_lineage[-1][1:3]
    ancestors = {row[1:3] for row in candidate_lineage}
    for path, expected in roots:
        actual = _lineage(path)
        if actual[-1][1:3] != expected:
            _fail("original predecessor root identity changed")
        if expected in ancestors or candidate_identity in {row[1:3] for row in actual}:
            _fail(
                "private metadata physically overlaps original "
                "predecessor state or source"
            )
    # These actual consumed observers close original held descriptors, guards,
    # namespace roots, source facts and registry bindings after the ancestry I/O.
    # No ready rights are reacquired and no fresh root baseline is accepted.
    for producer in (framework, catalog):
        if producer is not None:
            producer.close_native(_consumed=not _before_movement)
    if (
        catalog is not None
        and admission.catalog_lifetime[0]["source_lease"] is not None
    ):
        admission.catalog_lifetime[0]["source_lease"].close_native()


def _bind_metadata_area(phase, area):
    from .retained_layout_partition import _lineage
    from .retained_layout_transaction import _MetadataArea

    value = _require_metadata_authority(phase)
    if value is None:
        return
    if (
        type(area) is not _MetadataArea
        or value.area is not None
        or phase._metadata_area is not area
        or area.root != value.root
        or area.journal is not phase.pool._journal
    ):
        _fail("one actual creating metadata area required")
    area.guard()
    node = _from_stat(os.fstat(area.descriptor))
    if (
        node != value.original_root
        or layout_entry_node(area.root) != node
        or _lineage(area.root) != value.lineage
        or area.names()
    ):
        _fail("original empty private metadata area changed")
    _AREAS[area] = phase
    _advance(
        phase,
        value,
        area=area,
        descriptor=area.descriptor,
        guard=area.guard,
        root_node=node,
    )


def _stage_preflight(area, name, content, *, old_node=_UNSET):
    phase = _AREAS.get(area)
    if phase is None:
        from .bounded_role_observation import current_role_observation

        current = current_role_observation()
        if any(current is v.admission.original.reader for v in _METADATA.values()):
            _fail("actual creating metadata area required for staging")
        return None
    value = _require_metadata_authority(phase)

    from .retained_layout_transaction import _metadata_names

    names = _metadata_names(phase.plan.root)
    if (
        len(value.stages) >= 3
        or name != f"new-{len(value.stages)}"
        or content != dict(phase.plan.prospective)[names[len(value.stages)]]
    ):
        _fail("exact next acknowledged metadata stage required")
    public_name = names[len(value.stages)]
    template = dict(value.admission.movement.expected[1]).get(public_name)
    original = next(
        item for item in phase.plan.inputs if item.path == phase.plan.root / public_name
    )
    signature = (
        None
        if template is None
        else (
            template.device,
            template.inode,
            template.mode,
            template.size,
            template.modified_ns,
            template.changed_ns,
        )
    )
    if signature != original.signature or (
        old_node is not _UNSET and old_node != template
    ):
        _fail("exact original metadata permission template required")
    return value


def _read_staged_metadata(area, name, content, node, descriptor, created):
    value = _stage_preflight(area, name, content)
    if value is None:
        return _file(area.root / name)
    phase = _AREAS[area]

    from .retained_layout_transaction import _metadata_names

    public_name = _metadata_names(phase.plan.root)[len(value.stages)]
    template = dict(value.admission.movement.expected[1]).get(public_name)
    mode, gid = (
        (created.mode, created.gid)
        if template is None
        else (template.mode, template.gid)
    )
    if (
        not stat.S_ISREG(node.mode)
        or node.uid != os.geteuid()
        or node.links != 1
        or node.mode != mode
        or node.gid != gid
        or (template is None and stat.S_IMODE(created.mode) & ~0o600)
    ):
        _fail("staged metadata permissions differ from original template")
    if (
        _from_stat(os.fstat(descriptor)) != node
        or layout_entry_node(area.root / name) != node
    ):
        _fail("actual original staged metadata FD required")
    observed = _receipt_read(area.root / name, node, content)
    known = dict(value.known)
    known[name] = node, content
    _advance_cache(value, observed.path, observed)
    _advance(
        phase,
        value,
        known=tuple(sorted(known.items())),
        stages=(*value.stages, observed),
        root_node=_area_node(value, known),
    )
    return observed


def _receipt_read(path, node, content):
    if node.size != len(content):
        _fail("metadata receipt byte bound changed")
    observed = _raw_file(path, maximum_bytes=max(1, len(content)))
    if (
        observed.content != content
        or observed.signature
        != (
            node.device,
            node.inode,
            node.mode,
            node.size,
            node.modified_ns,
            node.changed_ns,
        )
        or layout_entry_node(path) != node
    ):
        _fail("actual metadata receipt node or bytes changed")
    return observed


def _require_metadata_step(
    phase, source, destination, source_node, content, *, quarantine
):
    value = _require_metadata_authority(phase)
    if value is None:
        return None
    if len(value.stages) != 3 or value.cursor >= len(value.steps):
        _fail("actual complete stages and next metadata step required")
    step = value.steps[value.cursor]
    expected = (
        dict(value.admission.movement.expected[1]).get(
            source.relative_to(phase.plan.root).as_posix()
        )
        if quarantine
        else dict(value.known).get(source.name, (None,))[0]
    )
    if (source, destination, content, quarantine) != (
        step.source,
        step.destination,
        step.content,
        step.quarantine,
    ) or source_node != expected:
        _fail("exact original next metadata move required")
    return value


def _read_metadata_destination(
    phase, source, destination, source_node, actual, content, *, quarantine
):
    value = _require_metadata_step(
        phase, source, destination, source_node, content, quarantine=quarantine
    )
    if value is None:
        return _file(destination)
    if actual.after_rename() != source_node.after_rename() or os.path.lexists(source):
        _fail("metadata receipt lacks exact original native rename")
    return _receipt_read(destination, actual, content)


def _preflight_metadata_receipt(phase, data):
    from literate_ai.contracts.identity import canonical_json_bytes

    from .retained_layout_journal import _DOCUMENT_LIMIT

    value = _require_metadata_authority(phase)
    if value is None:
        return
    # The closed observed event has four fixed native records. Even decimal
    # wrappers for every integer and a three-part native ID fit 256 JSON nodes.
    # Its bytes are already reserved by the original journal admission; keep
    # room for the actual decoded-node charge after the native rename as well.
    ledger = value.admission.original.ledger
    projected = canonical_json_bytes({**data, "observed_node": data["source_node"]})
    if (
        len(projected) + 128 > _DOCUMENT_LIMIT
        or ledger.budget.maximum_entries - ledger.records < 256
        or ledger.metadata - ledger.charged < 4096 * 256
    ):
        _fail("metadata observed record has no original allowance before rename")


def _advance_cache(value, path, observed):
    ledger, reader = value.admission.original.ledger, value.admission.original.reader
    if path not in ledger.cache or observed.path != path:
        _fail("metadata observation was not funded before effects")
    ledger.cache[path] = observed
    if path in reader._presences:
        node = None if observed.signature is None else layout_entry_node(path)
        reader._presences[path] = (
            None
            if node is None
            else (
                node.device,
                node.inode,
                node.mode,
                node.uid,
                node.gid,
                node.size,
                node.modified_ns,
                node.changed_ns,
                node.links,
            )
        )


def _area_node(value, known):
    area = value.area
    area.guard()
    if area.names() != set(known):
        _fail("private metadata namespace differs from verified effects")
    node = _from_stat(os.fstat(area.descriptor))
    if (
        node.directory_identity != value.original_root.directory_identity
        or layout_entry_node(area.root) != node
    ):
        _fail("original private metadata area changed")
    return node


def _commit_metadata_move(
    phase, source, destination, source_node, actual, observed, *, quarantine
):
    from literate_ai.contracts.blobs import BlobRef

    from .retained_layout_source_movement import _advance_movement, _movement_record

    value = _record(phase, pending_inputs=True)
    if value is None:
        return
    step = value.steps[value.cursor]
    if (source, destination, quarantine, observed.content) != (
        step.source,
        step.destination,
        step.quarantine,
        step.content,
    ):
        _fail("actual next metadata receipt required")
    public = step.public
    original = next(item for item in phase.plan.inputs if item.path == public)
    empty = RefreshFileObservation(source, None, None)
    public_observation = empty if quarantine else observed
    expected_inputs = tuple(
        public_observation if item.path == public else item for item in value.inputs
    )
    if phase._current_inputs != expected_inputs:
        _fail("metadata current input transition disagrees with actual receipt")
    known = dict(value.known)
    if quarantine:
        known[destination.name] = actual, observed.content
    else:
        del known[source.name]
    if phase._metadata_area.known != known:
        _fail("private metadata effect inventory changed")
    movement = _movement_record(value.admission)
    tree, native = movement.expected
    nodes, files, physical = (
        dict(native),
        {name: (blob, mode) for name, blob, mode in tree.files},
        dict(tree._physical[1]),
    )
    name = public.relative_to(phase.plan.root).as_posix()
    if quarantine:
        del nodes[name], files[name], physical[name]
    else:
        nodes[name] = actual
        files[name] = (
            BlobRef(
                hashlib.sha256(observed.content).hexdigest(), len(observed.content)
            ),
            bool(actual.mode & 0o111),
        )
        physical[name] = (*observed.signature, actual.links, actual.uid, actual.gid)
    parent = public.parent
    parent_name = (
        ""
        if parent == phase.plan.root
        else parent.relative_to(phase.plan.root).as_posix()
    )
    parent_after = layout_entry_node(parent)
    if parent_after.directory_identity != nodes[parent_name].directory_identity:
        _fail("metadata parent lost original native identity")
    nodes[parent_name] = parent_after
    expected_tree = replace(
        tree,
        files=tuple(sorted((name, *item) for name, item in files.items())),
        _physical=(tree._physical[0], tuple(sorted(physical.items()))),
    )
    receipts = {
        path: (old, backup, current) for path, old, backup, current in value.receipts
    }
    backup = observed if quarantine else receipts.get(public, (None, None, None))[1]
    receipts[public] = original, backup, public_observation
    before = tuple(
        (path, value.admission.original.ledger.cache[path])
        for path in (source, destination)
    )
    _advance_cache(value, source, empty)
    _advance_cache(value, destination, observed)
    root_node = _area_node(value, known)
    _advance(
        phase,
        value,
        inputs=phase._current_inputs,
        known=tuple(sorted(known.items())),
        root_node=root_node,
        cursor=value.cursor + 1,
        receipts=tuple((path, *items) for path, items in sorted(receipts.items())),
        history=(*value.history, (step, before, source_node, actual)),
    )
    _advance_movement(
        value.admission,
        movement,
        expected=(
            expected_tree,
            tuple(sorted(nodes.items(), key=lambda row: (row[0] != "", row[0]))),
        ),
        history=(*movement.history, ("metadata", movement.expected)),
    )


def _require_metadata_moved(phase):
    value = _record(phase)
    if value is None:
        return False
    from .retained_layout_source_movement import _require_movement_current

    _require_movement_current(value.admission)
    return True


def _observe_metadata_area(admission):
    value = _record(admission.phase)
    if value is None or value.area is None:
        return
    value.area.require_current()
    if (
        value.area.known != dict(value.known)
        or _area_node(value, dict(value.known)) != value.root_node
    ):
        _fail("original metadata private graph changed")


def _close_metadata_native(admission):
    value = _record(admission.phase)
    if value is None or value.area is None:
        return
    if value.area.poisoned or value.area.known != dict(value.known):
        _fail("original metadata area native facts changed")
    for name, (node, _content) in value.known:
        if (
            _from_stat(os.stat(name, dir_fd=value.descriptor, follow_symlinks=False))
            != node
        ):
            _fail("retained metadata native node changed")
    value.guard()
    if (
        _from_stat(os.fstat(value.descriptor)) != value.root_node
        or layout_entry_node(value.root) != value.root_node
        or _from_stat(os.fstat(value.descriptor)) != value.root_node
    ):
        _fail("original metadata area native membership changed")
    _record(admission.phase)


def _close_current_authored(plan):
    from .retained_layout_partition import _lineage
    from .retained_layout_transaction import _close_inputs

    for phase, value in tuple(_METADATA.items()):
        if phase.plan is plan:
            _record(phase)
            if (
                plan.catalog_provenance is not None
                and _signature(plan.catalog_provenance.path)
                != plan.catalog_provenance.signature
            ):
                _fail("original catalog provenance changed")
            _close_inputs(value.inputs)
            if any(_lineage(path) != lineage for path, lineage in plan.input_lineages):
                _fail("original authored metadata ancestry changed")
            return True
    return False


def _close_consumed_input(owner, item):
    from .retained_layout_source_movement import _consumed_predecessor

    admission = _consumed_predecessor(owner)
    from .retained_layout_source_finalization import _terminal_metadata

    value = _terminal_metadata(owner)
    if value is None:
        value = _record(admission.phase)
    if value is None:
        return False
    for path, original, backup, current in value.receipts:
        if path != item.path:
            continue
        if item.signature != original.signature or item.content != original.content:
            _fail("metadata successor differs from original producer witness")
        if backup is not None and _signature(backup.path) != backup.signature:
            _fail("retained original producer metadata changed")
        if (_signature(path) if os.path.lexists(path) else None) != current.signature:
            _fail("current producer metadata successor changed")
        return True
    return False


def _published_layout(phase, *, _metadata_constructor):
    from .retained_layout import resolve_structural_layout
    from .retained_layout_transaction import _LIFT

    value = _record(phase)
    if value is None:
        import json

        return resolve_structural_layout(
            phase.plan.root,
            json.loads(_file(retained_scaffold_path(phase.plan.root, _LIFT)).content),
        )
    reader = value.admission.original.reader
    project = value.admission.original.authored.project
    manifests = tuple(
        item for item in value.inputs if item.path == project.manifest.path
    )
    if len(manifests) != 1 or manifests[0] != project.manifest:
        _fail("same original current manifest observation required")
    observation = _metadata_constructor(
        phase.plan.root,
        reader,
        manifest=manifests[0],
        root_node=project.lineage[-1][1:4],
        snapshot=project._snapshot,
        context=project._context,
    )
    lift_path = retained_scaffold_path(phase.plan.root, _LIFT, _observation=observation)
    lift = reader.json_value(
        _file(lift_path).content,
        str(lift_path),
    )
    if phase.plan.source_forest is not None:
        from .retained_layout import _layout_coordinates
        from .retained_layout_source_forest_movement import _record as forest_record
        from .retained_layout_source_forest_movement import _validate as validate_forest
        from .retained_layout_source_movement import _require_movement_current

        forest = forest_record(value.admission)
        proposed = dict(phase.plan.prospective)
        receipts = {path: current for path, _old, _backup, current in value.receipts}
        if value.cursor != len(value.steps) or any(
            receipts.get(phase.plan.root / name) is None
            or receipts[phase.plan.root / name].content != body
            for name, body in proposed.items()
        ):
            _fail("complete exact acknowledged forest metadata receipts required")
        _require_movement_current(value.admission)
        layout, _declaration = _layout_coordinates(
            phase.plan.root,
            lift,
            _observation=observation,
        )
        _require_movement_current(value.admission)
        if (
            validate_forest(value.admission) is not forest
            or _record(phase) is not value
        ):
            _fail("original forest metadata changed during coordinate validation")
        observation.require_current()
        return layout
    layout = resolve_structural_layout(
        phase.plan.root,
        lift,
        _observation=observation,
    )
    observation.require_current()
    return layout


def _bind_original_published_layout(implementation):
    construct, validate = _bind_original_source_metadata_ports()
    code, defaults, keywords = (
        implementation.__code__,
        implementation.__defaults__,
        implementation.__kwdefaults__,
    )
    failure = ValueError

    def published_layout(phase):
        if (
            implementation.__code__ is not code
            or implementation.__defaults__ is not defaults
            or implementation.__kwdefaults__ is not keywords
        ):
            raise failure("original published layout constructor boundary changed")
        validate()
        return implementation(phase, _metadata_constructor=construct)

    return published_layout


_published_layout = _bind_original_published_layout(_published_layout)
del _bind_original_published_layout


def _mark_metadata_observed(phase):
    value = _record(phase)
    if value is None:
        phase._metadata_published = True
        return
    if value.cursor != len(value.steps):
        _fail("actual complete metadata receipts required")
    _advance(phase, value, observed=True)


def _end_metadata(admission):
    value = _METADATA.pop(admission.phase, None)
    if value is not None and value.area is not None:
        _AREAS.pop(value.area, None)
