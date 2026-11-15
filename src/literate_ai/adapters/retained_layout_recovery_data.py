"""Actual nonroot data recovery under a separately live canonical role owner.

Restore exact still-owned pre-commit nodes, or verify committed outputs. Controls
remain held/retained for the subsequent disposition owner. No receipt is renewed.
"""

from __future__ import annotations

import hashlib
import json
import os
import stat
from contextlib import ExitStack
from dataclasses import dataclass, replace
from pathlib import Path

from literate_ai.contracts import (
    ProjectInitializationBaseline,
    ProjectInitializationOrigin,
)
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.projects import PROJECT_FILENAME

from .component_markdown import parse_component_markdown
from .conversion_authority import CONVERSION_AUTHORITY_FILE
from .exclusive_entry import _from_stat, layout_entry_node, move_layout_entry_exclusive
from .repository_refresh import RefreshFileObservation, _file
from .repository_refresh_reservations import _custody_wire
from .retained_cargo_tree_v2 import capture_retained_cargo_tree_v2
from .retained_layout import (
    LEGACY_WRAPPER_COMPONENT,
    RETAINED_LAYOUT_PATH,
    ResolvedRetainedLayout,
    RetainedLayoutDeclaration,
    RetainedLayoutSelection,
)
from .retained_layout_control_publication import _pinned_directory
from .retained_layout_control_roles import layout_pending_control_path
from .retained_layout_partition import _lineage
from .retained_layout_recovery_controls import (
    _close_dependencies,
    _close_dependency_facts,
    _close_retirement_facts,
    _node,
)
from .retained_layout_recovery_roles import _RecoveryRoleLease
from .retained_layout_transaction import (
    _BASELINE,
    _LIFT,
    _ORIGIN,
    HARNESS_WRAPPER_FILENAME,
    _close_tree,
    _native_tree,
    _prospective_metadata,
    _SourceMovePlan,
    _validate_plan_roles,
)

_TARGETS = (HARNESS_WRAPPER_FILENAME, _LIFT, RETAINED_LAYOUT_PATH)


def _fail(message):
    raise ValueError("layout.data-recovery: " + message)


def _decode(value):
    if isinstance(value, dict):
        if set(value) == {"integer_decimal"}:
            raw = value["integer_decimal"]
            if type(raw) is not str or not 1 <= len(raw) <= 128 or str(int(raw)) != raw:
                _fail("invalid recorded native integer")
            return int(raw)
        return {key: _decode(item) for key, item in value.items()}
    if isinstance(value, list):
        return tuple(_decode(item) for item in value)
    return value


def _optional_node(path):
    try:
        return layout_entry_node(path)
    except FileNotFoundError:
        return None


def _signature(node):
    return (
        node.device,
        node.inode,
        node.mode,
        node.size,
        node.modified_ns,
        node.changed_ns,
    )


def _digest(content):
    return (
        None
        if content is None
        else {"content_identity": "sha256:" + hashlib.sha256(content).hexdigest()}
    )


@dataclass(frozen=True, slots=True)
class _File:
    path: Path
    node: object
    content: bytes | None


@dataclass(frozen=True, slots=True)
class _Area:
    root: Path
    lineage: tuple
    entries: tuple


@dataclass(frozen=True, slots=True)
class _Move:
    entry: str
    name: str
    source: Path
    destination: Path
    node: object
    content: bytes | None


@dataclass(frozen=True, slots=True)
class _DataRecoveryPlan:
    root: Path
    phase_identity: str
    role_identity: object
    private_root: Path
    history: tuple
    source_tree: object
    source_native: tuple
    endpoints: tuple
    files: tuple
    areas: tuple
    parents: tuple
    actions: tuple
    committed: bool
    issues: tuple

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/layout-data-recovery@1",
                "plan": _custody_wire(self),
            }
        )


def _area(root):
    lineage = _lineage(root)
    node = root.lstat()
    if node.st_uid != os.geteuid() or stat.S_IMODE(node.st_mode) != 0o700:
        _fail("existing owned private metadata state required")
    entries = []
    with os.scandir(root) as scan:
        for entry in scan:
            if len(entries) >= 32:
                _fail("private metadata namespace exceeds its bound")
            entries.append((entry.name, layout_entry_node(root / entry.name)))
    if _lineage(root) != lineage:
        _fail("private metadata ancestry changed during capture")
    return _Area(root, lineage, tuple(sorted(entries)))


def _read_known(path, node, content):
    if (
        not stat.S_ISREG(node.mode)
        or node.links != 1
        or node.uid != os.geteuid()
        or _file(path).content != content
        or layout_entry_node(path) != node
    ):
        _fail("exact owned metadata bytes/native node required")
    return _File(path, node, content)


def _remember(observations, item):
    previous = observations.get(item.path)
    if previous is not None and (
        previous.node != item.node
        or (
            previous.content is not None
            and item.content is not None
            and previous.content != item.content
        )
    ):
        _fail("metadata endpoint changed during classification")
    if previous is None or item.content is not None:
        observations[item.path] = item


def _entry_at(origin, content, original, moves, observations):
    paths = {origin}
    for move, _ in moves:
        paths.update((Path(move["source"]), Path(move["destination"])))
    matches = []
    for path in sorted(paths, key=str):
        node = _optional_node(path)
        _remember(observations, _File(path, node, None))
        if node is not None and (node.device, node.inode) == (
            original.device,
            original.inode,
        ):
            if node.after_rename() != original.after_rename():
                _fail("original metadata node attributes changed")
            matches.append(_read_known(path, node, content))
    if len(matches) != 1:
        _fail("original metadata node is missing or ambiguous")
    current = matches[0]
    if moves:
        last, observed = moves[-1]
        if current.path == Path(last["destination"]):
            if observed is not None and current.node != observed:
                _fail("observed metadata native node changed")
        elif (
            current.path != Path(last["source"])
            or observed is not None
            or current.node != _node(last["source_node"])
        ):
            _fail("metadata endpoint disagrees with latest actual native intent")
    elif current.path != origin or current.node != original:
        _fail("original metadata changed without a matching native intent")
    _remember(observations, current)
    return current


def _metadata_moves(events, phase, entry, name, base, content, public, areas):
    result = []
    original_kind = "metadata-quarantine" if entry == "old" else "metadata-publication"
    for event in events:
        kind, data = event["kind"], event["data"]
        if data.get("source_phase_identity") != phase:
            continue
        if kind == original_kind + "-intent":
            if (
                Path(data["source"]) if entry == "old" else Path(data["destination"])
            ) != public:
                continue
            if (
                _node(data["source_node"]) != base
                or data["payload_digest"] != hashlib.sha256(content).hexdigest()
            ):
                _fail("original metadata intent disagrees with prepared bytes/node")
            private = Path(data["destination"] if entry == "old" else data["source"])
            parent = _node(
                data["destination_parent"] if entry == "old" else data["source_parent"]
            )
        elif (
            kind == "data-recovery-entry-intent"
            and data.get("entry") == entry
            and data.get("name") == name
        ):
            if data["payload_digest"] != hashlib.sha256(content).hexdigest():
                _fail("recovery metadata payload disagrees with original bytes")
            if _node(data["source_node"]).after_rename() != base.after_rename():
                _fail("recovery metadata intent substitutes the original inode")
            if (
                Path(data["destination"]) if entry == "old" else Path(data["source"])
            ) != public:
                _fail(
                    "recovery metadata effect is outside the canonical authored target"
                )
            private = Path(data["source"] if entry == "old" else data["destination"])
            parent = _node(
                data["source_parent"] if entry == "old" else data["destination_parent"]
            )
        else:
            continue
        if not private.is_absolute() or ".." in private.parts:
            _fail("invalid private metadata coordinate")
        area = _area(private.parent)
        if layout_entry_node(area.root).directory_identity != parent.directory_identity:
            _fail("original private metadata directory was replaced")
        areas[area.root] = area
        observed_kind = (
            original_kind + "-observed"
            if kind != "data-recovery-entry-intent"
            else "data-recovery-entry-observed"
        )
        observations = [
            e["data"]
            for e in events
            if e["sequence"] > event["sequence"]
            and e["kind"] == observed_kind
            and e["data"].get("source") == data["source"]
            and e["data"].get("destination") == data["destination"]
            and e["data"].get("source_phase_identity") == phase
        ]
        observed = _node(observations[0]["observed_node"]) if observations else None
        result.append((data, observed))
    return result


def _original_data(pool, roles, *, budget=None, maximum_metadata_bytes=None):
    journal = pool._journal
    saved = None
    if budget is not None or maximum_metadata_bytes is not None:
        from .retained_layout_source_state import _read_original_state

        if budget is None or maximum_metadata_bytes is None:
            _fail("fresh complete original-state read policy required")
        saved = _read_original_state(
            journal, budget=budget, maximum_metadata_bytes=maximum_metadata_bytes
        )
        document = saved.plan_document
        phase = saved.document["source_phase_identity"]
    else:
        header = json.loads(journal._known["header.json"][1])
        binding = header["binding"]
        if binding.get("schema") != "literate-ai/layout-transaction-binding@1":
            _fail("original source transaction binding required")
        if binding.get("original_state_required") is True:
            _fail("fresh complete original-state read policy required")
        phase = binding["source_phase_identity"]
        raw = journal.read_payload(phase.removeprefix("sha256:"))
        document = json.loads(raw)
        if (
            canonical_json_bytes(document) != raw
            or canonical_identity(document).uri != phase
        ):
            _fail("original source payload is not the acknowledged canonical plan")
    original = document["plan"]
    if "project_namespace" in original and saved is None:
        # Saved policies/descriptions do not grant a new reader its allowance.
        _fail("fresh complete original-state read policy required")
    root = roles._seed.root
    if (
        document["schema"] != "literate-ai/layout-source-phase@1"
        or original["root"] != str(root)
        or document["pending_control"] != str(layout_pending_control_path(root))
    ):
        _fail("original source plan belongs to another actual project")
    events = journal.events if saved is None else saved.events
    intents = [
        e["data"]
        for e in events
        if e["kind"] == "source-move-intent"
        and e["data"].get("source_phase_identity") == phase
    ]
    if len(intents) > 1:
        _fail("ambiguous original source effect history")
    payloads = (
        {item["path"]: item for item in intents[0]["metadata"]} if intents else {}
    )
    if payloads and set(payloads) != set(_TARGETS):
        _fail("original raw metadata payload set disagrees with actual targets")
    old, prospective = {}, {}
    before = {item["path"]: item for item in original["inputs"]}
    for name in _TARGETS:
        item = before[str(root / name)]
        if saved is not None:
            digest = item["content"]
            content = (
                None
                if digest is None
                else saved.body(digest["content_identity"].removeprefix("sha256:"))
            )
            proposed = saved.body(
                dict(original["prospective"])[name]["content_identity"].removeprefix(
                    "sha256:"
                )
            )
            if payloads and (
                payloads[name]["before"]
                != (None if content is None else hashlib.sha256(content).hexdigest())
                or payloads[name]["prospective"] != hashlib.sha256(proposed).hexdigest()
            ):
                _fail("source intent disagrees with durable original metadata")
        elif payloads:
            digest = payloads[name]["before"]
            content = None if digest is None else journal.read_payload(digest)
            proposed = journal.read_payload(payloads[name]["prospective"])
        else:
            content = _file(root / name, optional=item["signature"] is None).content
            proposed = None
        if _digest(content) != item["content"]:
            _fail("raw original metadata bytes are unavailable or inconsistent")
        old[name] = RefreshFileObservation(
            root / name, _decode(item["signature"]), content
        )
        if proposed is not None:
            if _digest(proposed) != dict(original["prospective"])[name]:
                _fail("prospective payload differs from acknowledged plan")
            prospective[name] = proposed
    return phase, original, events, old, prospective


def plan_layout_data_recovery(
    pool, roles, private_root, *, budget=None, maximum_metadata_bytes=None
):
    """Fresh read-only data frontier under actual current canonical descriptors."""
    if type(roles) is not _RecoveryRoleLease or roles._pool is not pool:
        _fail("actual same-producer canonical recovery owner required")
    roles.require_initial_inputs()
    root, private = roles._seed.root, Path(private_root)
    if not private.is_absolute() or ".." in private.parts:
        _fail("direct existing private recovery root required")
    initial_area = _area(private)
    if initial_area.entries:
        _fail("new recovery quarantine root must be empty")
    journal = pool._journal
    files, areas, parents, actions, endpoints = {}, {private: initial_area}, {}, [], {}
    tree, native, phase, committed, issues = None, (), "", False, ()
    try:
        phase, original, events, old, proposed = _original_data(
            pool,
            roles,
            budget=budget,
            maximum_metadata_bytes=maximum_metadata_bytes,
        )
        coordinates = original["layout"]
        selected = RetainedLayoutSelection.from_values(
            coordinates["wrapper_component"], coordinates["implementation_directory"]
        )
        if selected.implementation_directory == ".":
            _fail("root recovery requires the complete mixed-partition owner")
        source, destination = (
            root / selected.implementation_directory,
            Path(original["destination"]),
        )
        if (
            coordinates["implementation_root"] != str(source)
            or original["tree"]["root"] != str(source)
            or coordinates["wrapper_root"] != str(root / selected.wrapper_component)
            or not destination.is_relative_to(root)
            or destination == root
        ):
            _fail("original source coordinates disagree with actual retained roles")
        for path, expected in original["input_lineages"]:
            if _custody_wire(_lineage(Path(path))) != expected:
                _fail("original authored ancestry changed")
        for path, expected in (
            (source.parent, original["source_lineage"][:-1]),
            (destination.parent, original["destination_lineage"]),
        ):
            if _custody_wire(_lineage(path)) != expected:
                _fail("original source effect ancestry changed")
        original_node = _node(original["source_node"])
        found = []
        for path in (source, destination):
            endpoints[path] = _optional_node(path)
            if endpoints[path] is not None:
                if endpoints[path].after_rename() != original_node.after_rename():
                    _fail(f"source endpoint is foreign or changed: {path}")
                found.append(path)
        if len(found) != 1:
            _fail("source endpoints are missing or ambiguous")
        current_source = found[0]
        source_moves = []
        for event in events:
            data = event["data"]
            if data.get("source_phase_identity") != phase:
                continue
            if event["kind"] == "source-move-intent":
                if (
                    data["source"] != str(source)
                    or data["destination"] != str(destination)
                    or _node(data["source_node"]) != original_node
                ):
                    _fail("original source intent contradicts prepared custody")
                source_moves.append((source, destination, original_node, None))
            elif (
                event["kind"] == "data-recovery-entry-intent"
                and data.get("entry") == "source"
            ):
                if data["source"] != str(destination) or data["destination"] != str(
                    source
                ):
                    _fail("recovery source intent contradicts original endpoints")
                before_node = _node(data["source_node"])
                if before_node.after_rename() != original_node.after_rename():
                    _fail("recovery source intent substitutes original node")
                observed = [
                    e["data"]
                    for e in events
                    if e["sequence"] > event["sequence"]
                    and e["kind"] == "data-recovery-entry-observed"
                    and e["data"].get("entry") == "source"
                    and e["data"].get("source_phase_identity") == phase
                ]
                source_moves.append(
                    (
                        destination,
                        source,
                        before_node,
                        None if not observed else _node(observed[0]["observed_node"]),
                    )
                )
        if source_moves:
            before_path, after_path, before_node, observed = source_moves[-1]
            if current_source == after_path:
                if observed is not None and endpoints[current_source] != observed:
                    _fail("observed source root was changed")
            elif (
                current_source != before_path
                or observed is not None
                or endpoints[current_source] != before_node
            ):
                _fail(
                    "source endpoint disagrees with actual recorded native transition"
                )
        elif current_source != source or endpoints[current_source] != original_node:
            _fail("source differs without a matching native intent")
        budget = RetainedCargoInputBudget.from_dict(original["tree"]["budget"])
        if original["tree"]["exclusions"]:
            _fail("complete original source without exclusions required")
        tree = capture_retained_cargo_tree_v2(
            current_source,
            budget=budget,
            maximum_metadata_bytes=original["tree"]["maximum_metadata_bytes"],
        )
        if _custody_wire(replace(tree, root=source)) != original["tree"]:
            _fail("complete original source bytes/topology/physical custody changed")
        native = _native_tree(tree)
        expected_native = tuple(
            (name, _node(node)) for name, node in original["native"]
        )
        if (
            native[0][1].after_rename() != expected_native[0][1].after_rename()
            or native[1:] != expected_native[1:]
        ):
            _fail("original source native namespace changed")
        committed = any(
            e["kind"] in {"layout-commit-observed", "layout-finalization-observed"}
            and e["data"].get("state") == "committed-unqualified"
            and e["data"].get("source_phase_identity") == phase
            for e in events
        )
        if committed and current_source != destination:
            _fail("committed source is not at the acknowledged proposed location")
        if not committed and _custody_wire(roles.git) != original["git"]:
            _fail("pre-commit Git inputs changed; preserve concurrent state")
        inputs = []
        expected_paths = {
            str(root / name)
            for name in (
                _ORIGIN,
                _BASELINE,
                _LIFT,
                RETAINED_LAYOUT_PATH,
                HARNESS_WRAPPER_FILENAME,
                PROJECT_FILENAME,
                CONVERSION_AUTHORITY_FILE,
            )
        }
        expected_paths.update(
            str(root / selected.wrapper_component / name)
            for name in ("component.md", "component.lock.json")
        )
        if {item["path"] for item in original["inputs"]} != expected_paths:
            _fail("original authored set disagrees with actual framework roles")
        for item in original["inputs"]:
            path = Path(item["path"])
            if path in {root / name for name in _TARGETS}:
                inputs.append(old[path.relative_to(root).as_posix()])
            else:
                observed = _file(path, optional=item["signature"] is None)
                if _custody_wire(observed) != item:
                    _fail(f"original authored input changed: {path}")
                files[path] = _File(path, _optional_node(path), observed.content)
                inputs.append(observed)
        by_path = {item.path: item for item in inputs}
        origin = ProjectInitializationOrigin.from_dict(
            json.loads(by_path[root / _ORIGIN].content)
        )
        baseline = ProjectInitializationBaseline.from_dict(
            json.loads(by_path[root / _BASELINE].content)
        )
        if baseline.origin_identity != origin.identity:
            _fail("actual initialization origin/baseline disagree")
        wrapper = root / selected.wrapper_component
        component = by_path[wrapper / "component.md"]
        authoring = parse_component_markdown(
            component.path, component.content.decode(), project_root=root
        )
        if "adoption-shim" not in authoring.profiles or not any(
            item.name == "legacy.pipeline" for item in authoring.provides
        ):
            _fail("actual selected wrapper lacks retained-harness role")
        lift = json.loads(old[_LIFT].content)
        declaration = old[RETAINED_LAYOUT_PATH].content
        previous = (
            None
            if declaration is None
            else RetainedLayoutDeclaration.from_dict(json.loads(declaration))
        )
        if (
            lift["implementation_directory"] != selected.implementation_directory
            or (
                previous is None
                and selected.wrapper_component != LEGACY_WRAPPER_COMPONENT
            )
            or (
                previous is not None
                and (
                    previous.wrapper_component != selected.wrapper_component
                    or previous.implementation_directory
                    != selected.implementation_directory
                )
            )
        ):
            _fail("old source role disagrees with original layout metadata")
        layout = ResolvedRetainedLayout(
            selected.wrapper_component,
            wrapper,
            selected.implementation_directory,
            source,
        )
        prospective = _prospective_metadata(
            root, layout, tuple(inputs), destination.relative_to(root).as_posix()
        )
        if {name: _digest(content) for name, content in prospective} != dict(
            original["prospective"]
        ):
            _fail("prospective metadata does not derive from actual original authority")
        if not proposed:
            proposed = dict(prospective)
        validation = _SourceMovePlan(
            root,
            layout,
            tuple(inputs),
            _decode(original["input_lineages"]),
            roles.git,
            replace(tree, root=source),
            _decode(original["source_lineage"]),
            expected_native,
            destination,
            _decode(original["destination_lineage"]),
            _node(original["destination_parent"]),
            original_node,
            _node(original["source_parent"]),
            tuple(prospective),
        )
        _validate_plan_roles(validation)
        for index, name in enumerate(_TARGETS):
            public, before = root / name, old[name]
            old_events = [
                e["data"]
                for e in events
                if e["kind"] == "metadata-quarantine-intent"
                and e["data"].get("source_phase_identity") == phase
                and e["data"].get("source") == str(public)
            ]
            old_entry = None
            if before.signature is not None:
                base = (
                    _node(old_events[0]["source_node"])
                    if old_events
                    else _optional_node(public)
                )
                if base is None or _signature(base) != before.signature:
                    _fail("original metadata native before-image is unavailable")
                moves = _metadata_moves(
                    events, phase, "old", name, base, before.content, public, areas
                )
                old_entry = _entry_at(public, before.content, base, moves, files)
            new_events = [
                e["data"]
                for e in events
                if e["kind"] == "metadata-publication-intent"
                and e["data"].get("source_phase_identity") == phase
                and e["data"].get("destination") == str(public)
            ]
            new_entry = None
            if new_events:
                base = _node(new_events[0]["source_node"])
                moves = _metadata_moves(
                    events, phase, "new", name, base, proposed[name], public, areas
                )
                new_entry = _entry_at(
                    Path(new_events[0]["source"]), proposed[name], base, moves, files
                )
            actual = _optional_node(public)
            if actual is not None and not any(
                entry is not None and entry.path == public and entry.node == actual
                for entry in (old_entry, new_entry)
            ):
                _fail(f"public metadata has foreign native ownership: {public}")
            files.setdefault(public, _File(public, actual, None))
            if committed:
                if new_entry is None or new_entry.path != public:
                    _fail("committed metadata is not actually published")
            else:
                if new_entry is not None and new_entry.path == public:
                    actions.append(
                        _Move(
                            "new",
                            name,
                            public,
                            private / f"new-{index}",
                            new_entry.node,
                            new_entry.content,
                        )
                    )
                if old_entry is not None and old_entry.path != public:
                    actions.append(
                        _Move(
                            "old",
                            name,
                            old_entry.path,
                            public,
                            old_entry.node,
                            old_entry.content,
                        )
                    )
        if not committed and current_source != source:
            actions.append(
                _Move("source", "", current_source, source, native[0][1], None)
            )
        forbidden = {
            (node.device, node.inode) for _, node in native if stat.S_ISDIR(node.mode)
        }
        forbidden.update(
            (os.fstat(fd).st_dev, os.fstat(fd).st_ino)
            for fd in (pool._descriptor, journal._descriptor)
        )
        for protected in roles.protected_admin_entries:
            if protected.is_dir():
                value = protected.stat()
                forbidden.add((value.st_dev, value.st_ino))
        for area in areas.values():
            if forbidden.intersection(item[1:3] for item in area.lineage):
                _fail("private metadata overlaps source or another actual producer")
        paths = {
            source.parent,
            destination.parent,
            *(path.parent for path in files),
            *areas,
        }
        for path in paths:
            parents[path] = _lineage(path)
        devices = {node.device for _, node in native}
        devices.update(layout_entry_node(path).device for path in parents)
        if devices != {os.fstat(pool._descriptor).st_dev}:
            _fail("data recovery requires one actual filesystem")
    except (ValueError, OSError, KeyError, TypeError) as error:
        issues = (str(error),)
        actions = []
    roles.require_current()
    plan = _DataRecoveryPlan(
        root,
        phase,
        roles.identity,
        private,
        tuple(journal._known[name][1] for name in journal._events),
        tree,
        native,
        tuple(endpoints.items()),
        tuple(files.values()),
        tuple(areas.values()),
        tuple(parents.items()),
        tuple(actions),
        committed,
        issues,
    )
    if not issues:
        _verify(pool, roles, plan)
    return plan


def _observe_data(state):
    """Observe data only; this helper grants no control or mutation authority."""
    for path, ancestry in state.parents:
        if _lineage(path) != ancestry:
            _fail("current recovery parent ancestry changed")
    if state.source_tree is not None:
        state.source_tree.require_unchanged()
    for item in state.files:
        if _optional_node(item.path) != item.node or (
            item.content is not None and _file(item.path).content != item.content
        ):
            _fail("current recovery metadata changed")
    for area in state.areas:
        if _area(area.root) != area:
            _fail("current private metadata namespace changed")


def _close_data(state):
    """Close already captured native data facts without adopting new inputs."""
    private = []
    for area in state.areas:
        before = layout_entry_node(area.root)
        if _area(area.root) != area or layout_entry_node(area.root) != before:
            _fail("private state changed during closing observations")
        private.append((area, before))
    for path, node in state.endpoints:
        if _optional_node(path) != node:
            _fail("current source endpoint changed")
    if state.source_tree is not None:
        _close_tree(state.source_tree, state.source_native)
    for item in state.files:
        if _optional_node(item.path) != item.node:
            _fail("metadata native facts changed during closing observations")
    for path, ancestry in state.parents:
        if _lineage(path) != ancestry:
            _fail("recovery ancestry changed during closing observations")
    _close_data_native(state, tuple(private))
    return tuple(private)


def _close_data_native(state, private):
    """Known facts only, after every source/control/producer namespace read."""
    # All namespace observations precede this final pass over known native
    # facts. Directory stamps also close late membership changes without another
    # scan that could reopen an already closed source/file observation.
    if state.source_tree is not None:
        for name, node in state.source_native:
            if _from_stat((state.source_tree.root / name).lstat()) != node:
                _fail("source native facts changed after namespace observations")
    for item in state.files:
        if _optional_node(item.path) != item.node:
            _fail("metadata changed after namespace observations")
    for area, before in private:
        if layout_entry_node(area.root) != before:
            _fail("private namespace changed after data observations")
        for name, node in area.entries:
            if layout_entry_node(area.root / name) != node:
                _fail("private node changed after data observations")
    for path, node in state.endpoints:
        if _optional_node(path) != node:
            _fail("source endpoint changed after data observations")
    for path, ancestry in state.parents:
        if _lineage(path) != ancestry:
            _fail("data ancestry changed after namespace observations")


def _verify(pool, roles, state):
    roles.require_current()
    _observe_data(state)
    pool.require_current()
    roles.require_current()
    roles.reservations._close_currentness()
    _close_dependencies(pool)
    # Data namespace observations can themselves block. Close actual canonical
    # inputs and producer/descriptor facts after their last read, before effects;
    # none of these closing checks may resample or adopt payload bytes.
    retirements = roles.reservations._close_currentness()
    private = _close_data(state)
    producers = _close_dependencies(pool)
    roles.git.close_native_inputs(roles.reservations.native_inputs)
    roles._seed.close_native_inputs()
    _close_data_native(state, private)
    roles.reservations._close_marker_inputs()
    _close_retirement_facts(retirements)
    _close_dependency_facts(pool, producers)
    pool._guard()
    if not roles._active or roles._receiver != os.getpid():
        _fail("actual data recovery role context ended")


def _advance(state, action, actual, observed_tree, observed_native):
    files = {item.path: item for item in state.files}
    areas = []
    for area in state.areas:
        entries = dict(area.entries)
        if action.source.parent == area.root:
            entries.pop(action.source.name)
        if action.destination.parent == area.root:
            if action.destination.name in entries:
                _fail("recovery private destination was already occupied")
            entries[action.destination.name] = actual
        areas.append(replace(area, entries=tuple(sorted(entries.items()))))
    if action.entry != "source":
        files[action.source] = _File(action.source, None, None)
        files[action.destination] = _File(action.destination, actual, action.content)
        return replace(state, files=tuple(files.values()), areas=tuple(areas))
    endpoints = dict(state.endpoints)
    endpoints[action.source], endpoints[action.destination] = None, actual
    return replace(
        state,
        source_tree=observed_tree,
        source_native=observed_native,
        endpoints=tuple(endpoints.items()),
        areas=tuple(areas),
    )


def apply_layout_data_recovery(
    pool, roles, plan, *, acknowledged_recovery_identity, allow_host_execution
):
    """Restore exact pre-commit data or verify committed data; keep controls."""
    if type(plan) is not _DataRecoveryPlan or allow_host_execution is not True:
        _fail("explicit current data recovery execution authority required")
    fresh = plan_layout_data_recovery(pool, roles, plan.private_root)
    if fresh != plan or acknowledged_recovery_identity != fresh.identity:
        _fail("exact fresh data recovery acknowledgement required")
    if plan.issues:
        return {
            "state": "unresolved",
            "complete": False,
            "qualified": False,
            "issues": list(plan.issues),
        }
    journal = pool._journal
    records = 2 * len(plan.actions) + 2
    if (
        len(journal._events) + records > journal._budget.maximum_events
        or sum(len(raw) for _, raw in journal._known.values()) + records * 128 * 1024
        > journal._budget.maximum_storage_bytes
    ):
        _fail("complete data recovery exceeds remaining journal budget")
    state = plan
    with ExitStack() as stack:
        pinned = {
            path: stack.enter_context(_pinned_directory(path))
            for path, _ in plan.parents
        }
        _verify(pool, roles, state)
        journal.append(
            "data-recovery-intent",
            canonical_json_bytes(
                {
                    "source_phase_identity": plan.phase_identity,
                    "recovery_identity": plan.identity.uri,
                    "committed": plan.committed,
                    "qualified": False,
                }
            ),
        )
        _verify(pool, roles, state)
        for action in plan.actions:
            _verify(pool, roles, state)
            source_parent, destination_parent = (
                layout_entry_node(action.source.parent),
                layout_entry_node(action.destination.parent),
            )
            data = {
                "source_phase_identity": plan.phase_identity,
                "entry": action.entry,
                "name": action.name,
                "source": str(action.source),
                "destination": str(action.destination),
                "source_node": _custody_wire(action.node),
                "source_parent": _custody_wire(source_parent),
                "destination_parent": _custody_wire(destination_parent),
                "payload_digest": None
                if action.content is None
                else hashlib.sha256(action.content).hexdigest(),
            }
            journal.append("data-recovery-entry-intent", canonical_json_bytes(data))
            _verify(pool, roles, state)
            for _, guard in pinned.values():
                guard()
            move_layout_entry_exclusive(
                action.source,
                action.destination,
                expected_source=action.node,
                expected_source_parent=source_parent,
                expected_destination_parent=destination_parent,
            )
            for path in (action.source.parent, action.destination.parent):
                fd, guard = pinned[path]
                os.fsync(fd)
                guard()
            actual = layout_entry_node(action.destination)
            if actual.after_rename() != action.node.after_rename() or os.path.lexists(
                action.source
            ):
                _fail("recovery native endpoint changed after movement")
            moved_tree, moved_native = None, ()
            if action.entry == "source":
                moved_tree = capture_retained_cargo_tree_v2(
                    action.destination,
                    budget=state.source_tree.budget,
                    maximum_metadata_bytes=state.source_tree.maximum_metadata_bytes,
                )
                moved_native = _native_tree(moved_tree)
                if (
                    moved_tree != replace(state.source_tree, root=action.destination)
                    or moved_tree._physical != state.source_tree._physical
                    or moved_native[1:] != state.source_native[1:]
                ):
                    _fail("restored source bytes/topology/native custody changed")
            else:
                observed = _file(action.destination)
                if (
                    observed.content != action.content
                    or observed.signature != _signature(actual)
                ):
                    _fail(
                        "restored metadata observation does not belong to moved inode"
                    )
            if layout_entry_node(action.destination) != actual:
                _fail("recovery destination replaced during final read")
            state = _advance(state, action, actual, moved_tree, moved_native)
            _verify(pool, roles, state)
            journal.append(
                "data-recovery-entry-observed",
                canonical_json_bytes({**data, "observed_node": _custody_wire(actual)}),
            )
            _verify(pool, roles, state)
        result = {
            "state": "committed-unqualified-controls-pending"
            if plan.committed
            else "original-data-restored-controls-pending",
            "complete": False,
            "qualified": False,
            "data_verified": True,
            "controls_released": False,
        }
        journal.append(
            "data-recovery-observed",
            canonical_json_bytes(
                {"source_phase_identity": plan.phase_identity, **result}
            ),
        )
        _verify(pool, roles, state)
        return result
