"""Canonical authored roles from the actual original source discovery witnesses."""

from __future__ import annotations

import os
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from literate_ai.contracts.component_locking import ComponentAuthoring
from literate_ai.contracts.identity import canonical_identity
from literate_ai.projects import PROJECT_FILENAME

from .component_locks import LOCK_FILENAME, ComponentLockStore
from .conversion_authority import CONVERSION_AUTHORITY_FILE
from .harness_inventory import HARNESS_WRAPPER_FILENAME
from .repository_refresh import _file
from .retained_layout import RETAINED_LAYOUT_PATH

_KEY = object()
_OWNERS = {}


def _fail(message):
    raise ValueError("layout.source-authored: " + message)


def _endpoint_names(root, project, layout, lock_path):
    from .retained_layout_transaction import _LIFT

    paths = (
        project.manifest.path,
        project.conversion.path,
        root / _LIFT,
        root / RETAINED_LAYOUT_PATH,
        root / HARNESS_WRAPPER_FILENAME,
        layout.wrapper_root / "component.md",
        lock_path,
    )
    if (
        project.root != root
        or project.manifest.path != root / PROJECT_FILENAME
        or project.conversion.path != root / CONVERSION_AUTHORITY_FILE
        or layout.wrapper_root != root / layout.wrapper_component
        or len(set(paths)) != len(paths)
        or any(not path.is_relative_to(root) for path in paths)
    ):
        _fail("actual canonical project and selected wrapper endpoints required")
    return tuple(sorted(path.relative_to(root).as_posix() for path in paths))


@dataclass(frozen=True, slots=True)
class _Witness:
    preparation: object
    reader: object
    ledger: object
    plan: object
    project: object
    layout: object
    inputs: tuple
    lineages: tuple
    component: object
    lock_path: Path
    names: tuple
    selector_paths: tuple


class _Capture:
    def __init__(self, preparation):
        from .bounded_role_observation import current_role_observation
        from .retained_layout_source_preparation import _state

        original = _state(preparation, ready=False)
        if (
            original.plan is not None
            or current_role_observation() is not original.reader
        ):
            _fail("actual creating source discovery required")
        self.preparation, self.original = preparation, original
        self.observed = None
        self.finished = False
        self.lock_path = None
        self.selector_paths = ()
        original.ledger.charge_records(
            64, 65536 + 128 * len(str(original.root).encode())
        )

    def canonical_lock(self, layout):
        from .bounded_role_observation import current_role_observation
        from .retained_layout_source_preparation import _state

        if (
            self.finished
            or self.lock_path is not None
            or _state(self.preparation, ready=False) is not self.original
            or current_role_observation() is not self.original.reader
        ):
            _fail("one actual funded canonical store selection required")
        selected = os.environ.get("LITAI_MATRIX_CELL_ROOT")
        matrix_root = None
        if selected:
            self.original.ledger.charge_records(8, 4096 + 4 * len(selected))
            matrix_root = self._canonical_cell(selected)
        lock = ComponentLockStore._storage_root(layout.wrapper_root, matrix_root)
        lock = lock / LOCK_FILENAME
        if not lock.is_relative_to(self.original.root):
            _fail("canonical lock endpoint must remain inside the actual project")
        self.lock_path = lock
        return lock

    def _canonical_cell(self, selected):
        from .bounded_role_observation import current_role_observation
        from .retained_layout_git_controls import _presence
        from .retained_layout_partition import _lineage
        from .retained_layout_source_preparation import _state

        if (
            self.finished
            or self.lock_path is not None
            or _state(self.preparation, ready=False) is not self.original
            or current_role_observation() is not self.original.reader
            or type(selected) is not str
        ):
            _fail("actual creating canonical selector observation required")
        supplied = Path(selected)
        if not supplied.is_absolute():
            # CWD is sampled once under the original allowance. Later store
            # checks use the frozen endpoint, never ambient process state.
            self.original.ledger.charge_records(8, 65536)
            supplied = Path.cwd() / supplied
        resolved = Path(os.path.normpath(str(supplied)))
        if not resolved.is_relative_to(self.original.root):
            _fail("external canonical storage requires its actual shared owner")
        # Every cumulative prefix is at most the supplied absolute path's size.
        # Reserve this conservative bound before constructing the retained list;
        # a long selector must refuse before quadratic path allocation.
        count = len(supplied.parts)
        self.original.ledger.charge_records(
            8 + 4 * count,
            4096 + 128 * count * len(str(supplied).encode()),
        )
        paths = [Path(supplied.anchor)]
        for part in supplied.parts[1:]:
            paths.append(paths[-1].parent if part == ".." else paths[-1] / part)
        facts = {}
        for path in paths:
            node = _presence(path)
            if node is not None:
                if not stat.S_ISDIR(node[2]):
                    _fail("canonical cell resolution requires direct directories")
                _lineage(path)
            facts[path] = node
        self.selector_paths = tuple(facts.items())
        return resolved

    def observe(self, project, layout, inputs, lineages, component):
        from .bounded_role_observation import current_role_observation
        from .retained_layout_control_roles import _ProjectRoles
        from .retained_layout_source_preparation import _state

        if (
            self.finished
            or self.observed is not None
            or _state(self.preparation, ready=False) is not self.original
            or current_role_observation() is not self.original.reader
            or type(project) is not _ProjectRoles
            or type(component) is not ComponentAuthoring
        ):
            _fail("one actual parsed source-input observation required")
        names = _endpoint_names(self.original.root, project, layout, self.lock_path)
        values = {
            item.path.relative_to(self.original.root).as_posix(): item
            for item in inputs
        }
        if (
            not set(names) <= values.keys()
            or project.manifest != values[PROJECT_FILENAME]
            or project.conversion != values[CONVERSION_AUTHORITY_FILE]
            or "adoption-shim" not in component.profiles
            or not any(
                capability.name == "legacy.pipeline"
                for capability in component.provides
            )
        ):
            _fail("parsed canonical source witnesses disagree")
        self.observed = project, layout, inputs, lineages, component, names

    def finish(self, plan):
        from .bounded_role_observation import current_role_observation
        from .retained_layout_source_preparation import _state
        from .retained_layout_transaction import _PreparedSourceMovePlan

        if (
            self.finished
            or self.observed is None
            or type(plan) is not _PreparedSourceMovePlan
            or _state(self.preparation, ready=False) is not self.original
            or current_role_observation() is not self.original.reader
        ):
            _fail("actual creating source plan required to bind witnesses")
        project, layout, inputs, lineages, component, names = self.observed
        if (
            plan.layout is not layout
            or plan.inputs is not inputs
            or plan.input_lineages is not lineages
            or plan.authored_lock != self.lock_path
        ):
            _fail("original parsed source discovery was replaced")

        def folded(path):
            return tuple(
                unicodedata.normalize("NFC", part.casefold()) for part in path.parts
            )

        # An absent leaf still belongs to its original nearest-existing anchor.
        # Use captured native identities: alternate directory spellings cannot
        # hide canonical storage inside the source that this operation will move.
        _, ancestry = self.original.ledger.ancestry[self.lock_path]
        source_overlap = any(
            node[1:3] == plan.tree._physical[0][:2]
            or any(
                stat.S_ISDIR(physical[2]) and node[1:3] == physical[:2]
                for _, physical in plan.tree._physical[1]
            )
            for node in ancestry
        )
        source_overlap |= any(
            node is not None
            and (
                node[:2] == plan.tree._physical[0][:2]
                or any(
                    stat.S_ISDIR(physical[2]) and node[:2] == physical[:2]
                    for _, physical in plan.tree._physical[1]
                )
            )
            for _, node in self.selector_paths
        )
        if source_overlap or any(
            folded(path)[: len(folded(endpoint))] == folded(endpoint)
            for path in (self.lock_path, *(path for path, _ in self.selector_paths))
            for endpoint in (plan.tree.root, plan.destination)
        ):
            _fail("canonical lock storage overlaps source movement")
        self.finished = True
        return _Witness(
            self.preparation,
            self.original.reader,
            self.original.ledger,
            plan,
            project,
            layout,
            inputs,
            lineages,
            component,
            self.lock_path,
            names,
            self.selector_paths,
        )


def _require_witness(preparation, state):
    value = state.authored
    if (
        type(value) is not _Witness
        or value.preparation is not preparation
        or value.reader is not state.reader
        or value.ledger is not state.ledger
        or value.plan is not state.plan
        or value.layout is not state.plan.layout
        or value.inputs is not state.plan.inputs
        or value.lineages is not state.plan.input_lineages
        or value.lock_path != state.plan.authored_lock
        or value.names
        != _endpoint_names(state.root, value.project, value.layout, value.lock_path)
        or any(
            path not in state.reader._presences or state.reader._presences[path] != node
            for path, node in value.selector_paths
        )
    ):
        _fail("original parsed source-input witnesses changed or ended")
    return value


@dataclass(frozen=True, slots=True)
class _Record:
    admission: object
    witness: object
    controls: object
    control_binding: object
    seed: object
    inputs: tuple
    identity: object
    owner: object
    pid: int


class _AuthoredRoles:
    __slots__ = ()

    def __init__(self, key):
        if key is not _KEY:
            raise TypeError("actual source authored-role owner required")

    @property
    def identity(self):
        return _record(self).identity

    @property
    def paths(self):
        value = _record(self)
        return tuple(
            item.path.relative_to(value.witness.plan.root).as_posix()
            for item in _current_inputs(value)
            if item.content is not None
        )

    @property
    def endpoints(self):
        return _record(self).witness.names

    def require_current(self):
        from .retained_layout_source_admission import _control_reads
        from .retained_layout_transaction import _close_authored

        value = _record(self)
        with _control_reads(value.admission.preparation, value.admission.pool):
            for item in _current_inputs(value):
                if (
                    _file(
                        item.path,
                        optional=item.content is None,
                        maximum_bytes=max(1, len(item.content or b"")),
                    )
                    != item
                ):
                    _fail("actual canonical authored input changed")
        _close_authored(value.witness.plan)
        if _record(self) is not value:
            _fail("original authored-role lifetime changed")


def _check(value, admission):
    from .retained_layout_source_preparation import _state

    witness = _require_witness(admission.preparation, _state(admission.preparation))
    if (
        type(value) is not _Record
        or value.admission is not admission
        or value.witness is not witness
        or value.controls is not admission.controls
        or value.control_binding is not admission.control_binding
        or value.seed is not admission.controls._seed
        or value.seed is not admission.control_binding[0]
        or value.pid != os.getpid()
        or admission.authored is not value.owner
    ):
        _fail("original canonical authored participant changed or ended")
    project, seed = witness.project, value.seed
    if (
        seed.root != project.root
        or seed.project_id != project.project_id
        or seed.manifest != project.manifest
        or seed.conversion != project.conversion
        or seed.conversion_identity != project.conversion_identity
        or seed.lineage != project.lineage
    ):
        _fail("actual canonical control and authored roles disagree")
    return value


def _require_registration(admission):
    value = _OWNERS.get(admission.authored)
    if value is None:
        _fail("actual original canonical authored owner required")
    return _check(value, admission)


def _record(owner):
    from .retained_layout_source_admission import _phase_record

    if type(owner) is not _AuthoredRoles:
        raise TypeError("actual source authored-role owner required")
    value = _OWNERS.get(owner)
    if value is None or _phase_record(value.admission.phase) is not value.admission:
        _fail("canonical authored-role owner ended or is foreign")
    return _require_registration(value.admission)


def _bind_authored(admission):
    witness = _require_witness(admission.preparation, admission.original)
    if admission.authored is not None:
        _fail("source authored-role participant is single-use")
    names = set(witness.names)
    inputs = tuple(
        item
        for item in witness.inputs
        if item.path.relative_to(witness.plan.root).as_posix() in names
    )
    targets = {m.target.path for m in admission.controls.reservations._markers}
    for item in inputs:
        if item.path in targets or any(
            item.path.is_relative_to(root)
            for root in witness.plan.git.protected_admin_entries
        ):
            _fail("canonical authored endpoint overlaps actual control ownership")
    admission.original.ledger.charge_records(
        16 + 4 * len(inputs),
        4096 + 32 * sum(len(str(item.path).encode()) for item in inputs),
    )
    identity = canonical_identity(
        {
            "schema": "literate-ai/layout-source-authored@1",
            "source_plan": witness.plan.identity.uri,
            "component": witness.component.coordinate.uri,
            "endpoints": list(witness.names),
        }
    )
    owner = _AuthoredRoles(_KEY)
    value = _Record(
        admission,
        witness,
        admission.controls,
        admission.control_binding,
        admission.controls._seed,
        inputs,
        identity,
        owner,
        os.getpid(),
    )
    _OWNERS[owner] = value
    admission.authored = owner
    _require_registration(admission)


def _current_inputs(value):
    from .retained_layout_source_metadata import _record as metadata_record

    metadata = metadata_record(value.admission.phase)
    current = value.witness.inputs if metadata is None else metadata.inputs
    values = {item.path: item for item in current}
    return tuple(values[item.path] for item in value.inputs)


def _initializer_framework(admission, framework, observed):
    value = _require_registration(admission)
    by_path = {item.path: item for item in value.inputs}
    for item in observed.values():
        if item.path in by_path and item != by_path[item.path]:
            _fail("initializer and canonical authored observations disagree")
    return framework - set(value.witness.names)


def _join_partition(admission, framework, inputs, children, imported, imported_dirs):
    from .catalog_copy_roles import _record as catalog_record
    from .catalog_entry_publication import _digest

    value = _require_registration(admission)
    by_path = {item.path: item for item in inputs}
    names = set(value.witness.names)
    for item in value.inputs:
        name = item.path.relative_to(value.witness.plan.root).as_posix()
        if any(item.path.is_relative_to(child) for child in children):
            _fail("canonical authored endpoint overlaps an independent project")
        if name in imported_dirs:
            _fail("canonical authored file overlaps a catalog directory")
        previous = by_path.get(item.path)
        if previous is not None and previous != item:
            _fail("canonical and initializer ownership observations disagree")
        update = admission.original.framework
        if update is not None:
            previous = update._cache.get(item.path)
            if previous is not None and previous != item:
                _fail("canonical and framework-update observations disagree")
            if name in update.paths and previous is None:
                _fail("actual shared framework-update witness required")
        if name in imported:
            seal = catalog_record(admission.original.catalog, ready=True)["seal"]
            node = seal.project.nodes.get(name)
            signature = (
                None
                if node is None
                else (
                    node.device,
                    node.inode,
                    node.mode,
                    node.size,
                    node.modified_ns,
                    node.changed_ns,
                )
            )
            if (
                signature != item.signature
                or item.content is None
                or seal.project.files.get(name) != _digest(item.content)
            ):
                _fail("canonical and copied ownership receipts disagree")
        by_path[item.path] = item
    return (
        framework - names,
        tuple(by_path[path] for path in sorted(by_path)),
        set(value.admission.authored.paths),
    )


def _closing_authored(admission):
    return _require_registration(admission)


def _close_terminal_authored(admission, original, value):
    from .retained_layout_source_admission import _ADMISSIONS

    if value.witness is not original.authored or value.admission is not admission:
        _fail("original terminal authored witness changed")
    _check(value, admission)
    if (
        _ADMISSIONS.get(admission.preparation) is admission
        and _require_registration(admission) is not value
    ):
        _fail("original closing authored participant ended")


def _end_authored(admission):
    _OWNERS.pop(admission.authored, None)
