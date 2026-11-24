"""Purpose-specific original source retirement; normal stores never retarget.

POSIX whole-directory closing only. Mixed application directories and Windows
rename-compatible byte-lock ownership remain separate, explicit refusals.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
import weakref
from contextlib import ExitStack, contextmanager
from pathlib import Path

from literate_ai._cache_lock import _acquire, _identity_matches, _release
from literate_ai._filesystem import stat_is_link_or_reparse
from literate_ai.adapters.component_namespace import original_component_physical_binding
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    move_file_between_owned_parents_exclusive,
    publish_directory_between_owned_parents_exclusive,
)
from literate_ai.adapters.project_layout_component_transition import (
    require_original_component_transition as _admit,
)
from literate_ai.adapters.project_layout_component_transition import (
    verify_component_transition_destination_current as _destination_current,
)
from literate_ai.adapters.project_layout_continuation_result import (
    decode_catalog_continuation_result,
)
from literate_ai.adapters.project_layout_filesystem import (
    flush_migration_directory,
    write_migration_file,
)
from literate_ai.adapters.project_layout_lease import (
    current_layout_lease,
    require_layout_lease,
)
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutPlanError,
    _capture,
)
from literate_ai.adapters.qualification_workspace_namespace import (
    hold_qualification_workspace_namespace,
)
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.projects import ProjectConfigurationSnapshot, ProjectConfigurationStore

_SCHEMA = "literate-ai/component-source-namespace-closure@1"
_KEY = object()
_LIVE = {}


def _fail(message):
    raise ProjectLayoutPlanError("source_namespace_closure", message)


def _posix():
    if os.name != "posix":
        _fail("source retirement requires qualified rename-compatible native handles")


def _coordinate(value):
    canonical_relative_posix_path(value, label="source namespace closure coordinate")
    if ".git" in Path(value).parts:
        _fail("source namespace crosses Git administration")
    return value


def _file_record(descriptor):
    before = os.fstat(descriptor)
    if (
        not stat.S_ISREG(before.st_mode)
        or before.st_nlink != 1
        or before.st_size > 1024 * 1024
    ):
        _fail("source coordination is not bounded direct data")
    digest, remaining = hashlib.sha256(), before.st_size
    os.lseek(descriptor, 0, os.SEEK_SET)
    while remaining:
        block = os.read(descriptor, min(remaining, 65536))
        if not block:
            _fail("source coordination changed")
        digest.update(block)
        remaining -= len(block)
    if os.read(descriptor, 1):
        _fail("source coordination grew")
    after = os.fstat(descriptor)
    if (
        before.st_dev,
        before.st_ino,
        before.st_mode,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    ) != (
        after.st_dev,
        after.st_ino,
        after.st_mode,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    ):
        _fail("source coordination changed during capture")
    return {
        "node": [after.st_dev, after.st_ino, after.st_mode],
        "native_kind": "posix",
        "native_node": [after.st_dev, after.st_ino],
        "identity": "sha256:" + digest.hexdigest(),
        "size": after.st_size,
        "mode": stat.S_IMODE(after.st_mode),
    }


def _validate_record(record, root, plan=None):
    if not root.is_absolute() or ".." in root.parts:
        _fail("source closure requires its original absolute project root")
    if type(record) is not dict or set(record) != {
        "schema",
        "project",
        "plan_identity",
        "source_root",
        "source_node",
        "coordination",
        "empty_directories",
        "payloads",
        "source_parent_node",
        "archive_parent_node",
    }:
        _fail("unknown or missing source closure field")
    if record["schema"] != _SCHEMA or record["project"] != str(root):
        _fail("source closure root/schema differs")
    source = _coordinate(record["source_root"])
    from literate_ai.contracts import ContentIdentity

    ContentIdentity.parse_uri(record["plan_identity"])
    if source == "." or (root / "litai").is_relative_to(root / source):
        _fail("source closure overlaps live project/framework authority")

    def node(value, directory):
        if (
            type(value) is not list
            or len(value) != 3
            or any(type(x) is not int or x < 0 for x in value)
            or not (stat.S_ISDIR(value[2]) if directory else stat.S_ISREG(value[2]))
        ):
            _fail("invalid original source native node")

    node(record["source_node"], True)
    node(record["source_parent_node"], True)
    node(record["archive_parent_node"], True)
    for mapping in (
        record["coordination"],
        record["payloads"],
        record["empty_directories"],
    ):
        if type(mapping) is not dict or len(mapping) > 8192:
            _fail("source closure inventory exceeds original bound")
        for name in mapping:
            _coordinate(name)
    if not record["coordination"] or set(record["coordination"]) & set(
        record["payloads"]
    ):
        _fail("source coordination/payload inventory overlaps or is absent")
    for row in record["payloads"].values():
        if type(row) is not dict or set(row) != {"node", "mode", "identity"}:
            _fail("invalid original source payload preimage")
        node(row["node"], False)
        if type(row["mode"]) is not int or stat.S_IMODE(row["node"][2]) != row["mode"]:
            _fail("original source payload mode differs")
        ContentIdentity.parse_uri(row["identity"])
    for name, row in record["coordination"].items():
        if (
            len(Path(name).parts) != 1
            or type(row) is not dict
            or set(row)
            != {"node", "native_kind", "native_node", "identity", "size", "mode"}
            or row["native_kind"] != "posix"
            or row["native_node"] != row["node"][:2]
            or type(row["size"]) is not int
            or not 0 <= row["size"] <= 1024 * 1024
        ):
            _fail("invalid source coordination preimage")
        node(row["node"], False)
        if type(row["mode"]) is not int or stat.S_IMODE(row["node"][2]) != row["mode"]:
            _fail("original source coordination mode differs")
        ContentIdentity.parse_uri(row["identity"])
    parents = {
        parent.as_posix()
        for name in record["payloads"]
        for parent in Path(name).parents
        if parent != Path(".")
    }
    if set(record["empty_directories"]) != parents:
        _fail("source directory scope is not the exact selected payload ancestry")
    for value in record["empty_directories"].values():
        node(value, True)
    if plan is not None:
        if (
            plan["project"] != str(root)
            or plan["plan_identity"] != record["plan_identity"]
        ):
            _fail("source closure differs from original reviewed plan")
        selected = {
            name.removeprefix(source + "/"): row
            for name, row in plan["placements"].items()
            if name.startswith(source + "/")
        }
        if set(selected) != set(record["payloads"]):
            _fail("source payload preimages differ from selected placements")
        for name, row in selected.items():
            if (
                row["from"] != record["payloads"][name]["identity"]
                or row["mode"] != record["payloads"][name]["mode"]
            ):
                _fail("source payload binding differs from reviewed source")
    return record


def read_source_namespace_record(root, plan, path):
    """Strict data reopen; caller still acquires a fresh original recovery gate."""
    from literate_ai.adapters.project_layout_migration import _file

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                _fail("duplicate source closure record key")
            result[key] = value
        return result

    try:
        value = json.loads(_file(path)[1], object_pairs_hook=unique)
        identity = value.pop("identity")
        _validate_record(value, root, plan)
        if (
            canonical_identity(value).uri != identity
            or _fixed_paths(root, value)[2] != path
        ):
            _fail("source closure record identity/coordinate differs")
        return value
    except (OSError, KeyError, TypeError, ValueError) as error:
        if isinstance(error, ProjectLayoutPlanError):
            raise
        raise ProjectLayoutPlanError(
            "source_namespace_closure", "invalid original source closure record"
        ) from error


@contextmanager
def _owned_stack():
    stack = ExitStack()
    try:
        yield stack
    except BaseException as primary:
        try:
            stack.close()
        except BaseException as cleanup:
            try:
                BaseException.add_note(
                    primary,
                    "source namespace cleanup refused: " + type(cleanup).__name__,
                )
            except BaseException:
                pass
        raise
    else:
        stack.close()


def _residual(path, record, *, restored=False):
    if os.path.lexists(path / ".git"):
        _fail("independent Git blocks source retirement")
    nodes, _ = _capture(path)
    expected_files = record["coordination"]
    expected_dirs = record["empty_directories"]
    if restored:
        expected_files = {**expected_files, **record["payloads"]}
    allowed = set(expected_files) | set(expected_dirs)
    for name in nodes:
        if name not in allowed:
            _fail("source residual contains application, foreign or unselected data")
    for name, expected in expected_dirs.items():
        if (
            name not in nodes
            or nodes[name]["kind"] != "directory"
            or list(nodes[name]["stamp"][:3]) != expected
        ):
            _fail("original source subdirectory changed")
    for name, expected in expected_files.items():
        observed = nodes.get(name)
        if restored and observed is None and name in record["payloads"]:
            continue  # original rollback owner restores its exact entries below
        if (
            observed is None
            or observed["kind"] != "file"
            or list(observed["stamp"][:3]) != expected["node"]
            or observed["mode"] != expected["mode"]
            or observed["identity"] != expected["identity"]
        ):
            _fail("source residual file changed")


def _fixed_paths(root, record):
    source = root / _coordinate(record["source_root"])
    journal = (
        root
        / "litai/.literate"
        / (
            "catalog-placement-"
            + canonical_identity({"layout_plan": record["plan_identity"]}).digest
        )
    )
    slot = canonical_identity(
        {"source_root": record["source_root"], "plan_identity": record["plan_identity"]}
    ).digest
    archive = journal / "retired-source" / slot
    return source, archive, archive.with_suffix(".json")


def _move(source, target, node):
    publish_directory_between_owned_parents_exclusive(
        source,
        target,
        expected_source=tuple(node),
        expected_source_parent=directory_node(source.parent),
        expected_destination_parent=directory_node(target.parent),
    )
    flush_migration_directory(source.parent)
    flush_migration_directory(target.parent)


class _Owner:
    __slots__ = ("__weakref__",)

    def __new__(cls, key=None):
        if key is not _KEY:
            raise TypeError("original source closing owner required")
        return super().__new__(cls)

    def __reduce__(self):
        raise TypeError("source closing owner cannot be serialized")


def _state(owner):
    pair = _LIVE.get(id(owner))
    if (
        type(owner) is not _Owner
        or pair is None
        or pair[0]() is not owner
        or not pair[1]["active"]
    ):
        _fail("original source closing owner expired or differs")
    return pair[1]


def require_source_closing_current(owner):
    state = _state(owner)
    record, source, archive = state["record"], state["source"], state["archive"]
    require_layout_lease(state["lease"], state["root"])
    current, absent = (
        (source, archive) if state["phase"] == "live" else (archive, source)
    )
    if (
        os.path.lexists(absent)
        or list(directory_node(current)) != record["source_node"]
    ):
        _fail("retired/live source names have changed or ambiguous custody")
    node = os.fstat(state["directory"])
    if [node.st_dev, node.st_ino, node.st_mode] != record["source_node"]:
        _fail("original held source directory changed")
    if (
        list(directory_node(source.parent)) != record["source_parent_node"]
        or list(directory_node(archive.parent)) != record["archive_parent_node"]
    ):
        _fail("original source/archive parent changed")
    _residual(current, record)
    for name, descriptor in state["descriptors"].items():
        path = current / name
        observed = path.lstat()
        if (
            not _identity_matches(path, observed, descriptor, os.fstat(descriptor))
            or _file_record(descriptor) != record["coordination"][name]
        ):
            _fail("original held source coordination changed")


def retire_source_namespace(owner):
    """The sole live->retired action; no ordinary store points at the archive."""
    state = _state(owner)
    require_source_closing_current(owner)
    if state["phase"] != "live":
        _fail("source namespace already retired")
    _move(state["source"], state["archive"], state["record"]["source_node"])
    state["phase"] = "retired"
    require_source_closing_current(owner)


def source_namespace_record(owner):
    require_source_closing_current(owner)
    return json.loads(canonical_json_bytes(_state(owner)["record"]))


def _project_current(snapshot):
    current = ProjectConfigurationStore(snapshot.root).read()
    if (
        current.manifest_path != snapshot.manifest_path
        or current.content != snapshot.content
        or current.directory_binding != snapshot.directory_binding
    ):
        _fail("original current destination project changed")


@contextmanager
def source_namespace_closing(
    transition, *, result, snapshot, expected_coordination, empty_directories, payloads
):
    """Original live source/data closing under the SAME project layout lease.

    Caller stages the original journal's retired-source container BEFORE this
    factory. Payload preimages are data used solely by exact rollback, never a
    new catalog/producer grant. All source coordination leaves must preexist.
    """
    _posix()
    _admit(transition)  # factory proof BEFORE any original member dereference
    if (
        type(snapshot) is not ProjectConfigurationSnapshot
        or type(snapshot.root) is not type(Path())
        or type(snapshot.content) is not bytes
    ):
        _fail("actual original current destination snapshot required")
    result = decode_catalog_continuation_result(result)
    plan, root = result["plan"], snapshot.root
    source = root / _coordinate(transition.source_root)
    original, identity = original_component_physical_binding(
        transition.original_lock_store
    )
    if (
        original != source
        or plan["project"] != str(root)
        or result["operation"] != "apply"
    ):
        _fail("closing original source/result correlation differs")
    if source == root or (root / "litai").is_relative_to(source):
        _fail("mixed retained application source needs its distinct metadata role")
    manifest = plan["placements"].get(transition.source_root + "/component.md")
    if manifest is None or manifest["from"] != transition.manifest_identity:
        _fail("source authoring is not the exact admitted placement")
    node = list(directory_node(source))
    if (tuple(node[:2]), node[2]) != identity:
        _fail("original source physical identity differs")
    coordination = {}
    expected_paths = tuple(transition.coordination_paths)
    if set(expected_coordination) != set(expected_paths):
        _fail("source coordination differs from the original endpoint owner")
    for path in expected_paths:
        name = Path(path).relative_to(transition.source_root).as_posix()
        if len(Path(name).parts) != 1:
            _fail("source coordination is not an original leaf")
        coordination[name] = dict(expected_coordination[path])
    record = {
        "schema": _SCHEMA,
        "project": str(root),
        "plan_identity": plan["plan_identity"],
        "source_root": transition.source_root,
        "source_node": node,
        "coordination": coordination,
        "empty_directories": dict(empty_directories),
        "payloads": dict(payloads),
    }
    for mapping in (record["empty_directories"], record["payloads"]):
        for name in mapping:
            _coordinate(name)
    source, archive, intent = _fixed_paths(root, record)
    record["source_parent_node"] = list(directory_node(source.parent))
    record["archive_parent_node"] = list(directory_node(archive.parent))
    _validate_record(record, root, plan)
    with ProjectConfigurationStore.layout_lock(root), _owned_stack() as stack:
        lease = current_layout_lease(root)
        require_layout_lease(lease, root)
        _project_current(snapshot)
        _admit(transition)
        original_component_physical_binding(transition.original_lock_store)
        _destination_current(transition, snapshot)
        _project_current(snapshot)
        intent_data = _original_intent(root, plan["plan_identity"])
        eligible = next(
            (
                row
                for row in intent_data["components"]
                if row["source_root"] == transition.source_root
            ),
            None,
        )
        if (
            eligible is None
            or eligible["manifest_identity"] != transition.manifest_identity
        ):
            _fail("original journal has no admitted source endpoint")
        expected_payloads, expected_directories, expected_coord = _expected_preimages(
            intent_data, transition.source_root
        )
        if (
            record["source_node"]
            != intent_data["original_directories"].get(transition.source_root)
            or record["payloads"] != expected_payloads
            or record["empty_directories"] != expected_directories
            or record["coordination"] != expected_coord
            or record["archive_parent_node"]
            != intent_data["journal_directories"]["retired-source"]
        ):
            _fail("source closing inputs differ from original journal preimages")
        if (
            os.path.lexists(source / "component.md")
            or os.path.lexists(archive)
            or os.path.lexists(intent)
        ):
            _fail("source retirement is not at its exact pre-archive boundary")
        for parent in (source.parent, archive.parent):
            stack.enter_context(hold_qualification_workspace_namespace(parent))
        directory = os.open(source, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, directory)
        if list(directory_node(source)) != record["source_node"]:
            _fail("source replaced before directory hold")
        descriptors = {}
        for name, expected in coordination.items():
            descriptor = os.open(
                name, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            stack.callback(os.close, descriptor)
            if _file_record(descriptor) != expected:
                _fail("original source coordination preimage changed")
            _acquire(descriptor, source / name, timeout_seconds=0)
            stack.callback(_release, descriptor)
            descriptors[name] = descriptor
        owner = _Owner(_KEY)
        state = {
            "active": True,
            "root": root,
            "lease": lease,
            "record": record,
            "source": source,
            "archive": archive,
            "directory": directory,
            "descriptors": descriptors,
            "phase": "live",
        }
        _LIVE[id(owner)] = (weakref.ref(owner), state)
        try:
            require_source_closing_current(owner)
            envelope = {**record, "identity": canonical_identity(record).uri}
            pending = intent.parent / (
                "." + intent.stem + ".pending-" + uuid.uuid4().hex
            )
            write_migration_file(pending, canonical_json_bytes(envelope) + b"\n")
            move_file_between_owned_parents_exclusive(
                pending,
                intent,
                expected_source=tuple(
                    (lambda node: (node.st_dev, node.st_ino, node.st_mode))(
                        pending.lstat()
                    )
                ),
                expected_source_parent=directory_node(intent.parent),
                expected_destination_parent=directory_node(intent.parent),
            )
            flush_migration_directory(intent.parent)
            yield owner
            require_source_closing_current(owner)
            _admit(transition)
            _destination_current(transition, snapshot)
            _project_current(snapshot)
            require_source_closing_current(owner)
        finally:
            state["active"] = False
            _LIVE.pop(id(owner), None)


@contextmanager
def restored_source_namespace(root, record):
    """Restore original directory BEFORE caller opens any normal source fence."""
    _posix()
    root = Path(root)
    # Original public recovery verifies the durable record identity and exact
    # acknowledged plan before this private data-restoration owner is entered.
    _validate_record(record, root)
    source, archive, _ = _fixed_paths(root, record)
    with ProjectConfigurationStore.layout_lock(root), _owned_stack() as stack:
        lease = current_layout_lease(root)
        require_layout_lease(lease, root)
        for parent in (source.parent, archive.parent):
            stack.enter_context(hold_qualification_workspace_namespace(parent))
        live, retired = os.path.lexists(source), os.path.lexists(archive)
        if live == retired:
            _fail("source recovery has ambiguous or missing original namespace")
        if (
            list(directory_node(source.parent)) != record["source_parent_node"]
            or list(directory_node(archive.parent)) != record["archive_parent_node"]
        ):
            _fail("original recovery source/archive parent changed")
        current = source if live else archive
        if list(directory_node(current)) != record["source_node"]:
            _fail("original source recovery directory changed")
        _residual(current, record, restored=live)
        if retired:
            _move(archive, source, record["source_node"])
        require_layout_lease(lease, root)
        # No store construction, cache lock, mkdir or metadata write preceded restore.
        yield source
        require_layout_lease(lease, root)
        if (
            os.path.lexists(archive)
            or list(directory_node(source)) != record["source_node"]
        ):
            _fail("restored original source namespace changed")
        _residual(source, record, restored=True)


def _original_intent(root, expected):
    from literate_ai.adapters.project_layout_continuation import (
        _entry_state,
        _guard,
        _load,
    )

    journal, intent = _load(root, expected)
    _guard(root, intent["plan"])
    for source, entry in intent["entries"].items():
        if _entry_state(root, journal, source, entry) != "published":
            _fail("source retirement requires every exact placement/edit published")
    return intent


def _expected_preimages(intent, source_root):
    prefix = source_root + "/"
    payloads = {
        name.removeprefix(prefix): {
            "node": row["node"],
            "mode": row["mode"],
            "identity": row["from"],
        }
        for name, row in intent["entries"].items()
        if name.startswith(prefix)
    }
    directories = {
        name.removeprefix(prefix): node
        for name, node in intent["original_directories"].items()
        if name.startswith(prefix)
    }
    coordination = {
        name.removeprefix(prefix): row
        for name, row in intent["source_coordination"].items()
        if name.startswith(prefix)
    }
    return payloads, directories, coordination


def source_closure_records(root, journal, intent):
    """Strict original-journal extension; returns data mappings, never a lease."""
    container = journal / "retired-source"
    if (
        list(directory_node(container))
        != intent["journal_directories"]["retired-source"]
    ):
        _fail("original source retirement container changed")
    expected = {}
    for component in intent["components"]:
        source = component["source_root"]
        partial = {
            "source_root": source,
            "plan_identity": intent["plan"]["plan_identity"],
        }
        _, archive, path = _fixed_paths(root, partial)
        expected[path.name] = source
        expected[archive.name] = source
    records, found = [], set()
    with os.scandir(container) as entries:
        for ordinal, entry in enumerate(entries):
            if ordinal >= 16384:
                _fail("source closure extension exceeds record bound")
            if re.fullmatch(r"\.[0-9a-f]{64}\.pending-[0-9a-f]{32}", entry.name):
                if entry.name[1:65] not in expected:
                    _fail("unselected source closure staging coordinate")
                node = entry.stat(follow_symlinks=False)
                if (
                    stat_is_link_or_reparse(node)
                    or not stat.S_ISREG(node.st_mode)
                    or node.st_nlink != 1
                    or node.st_size > 16 * 1024 * 1024
                ):
                    _fail("unsafe retained source closure staging data")
                continue  # preserve interrupted private bytes; no cleanup grant
            if entry.name not in expected:
                _fail("unknown source closure extension member")
            if entry.name.endswith(".json"):
                record = read_source_namespace_record(
                    root, intent["plan"], Path(entry.path)
                )
                source = record["source_root"]
                if record["source_node"] != intent["original_directories"].get(source):
                    _fail("source closure directory differs from original journal")
                parent = Path(source).parent.as_posix()
                if record["source_parent_node"] != intent["original_directories"].get(
                    parent
                ):
                    _fail("source closure parent differs from original journal")
                payloads, directories, coordination = _expected_preimages(
                    intent, source
                )
                if (
                    record["payloads"] != payloads
                    or record["empty_directories"] != directories
                    or record["coordination"] != coordination
                    or record["archive_parent_node"]
                    != intent["journal_directories"]["retired-source"]
                ):
                    _fail("source closure preimages differ from original journal")
                records.append(record)
                found.add(source)
    roots = [record["source_root"] for record in records]
    if any(
        first != second and Path(first).is_relative_to(Path(second))
        for first in roots
        for second in roots
    ):
        _fail("overlapping original source namespace records")
    for name, source in expected.items():
        if (
            not name.endswith(".json")
            and os.path.lexists(container / name)
            and source not in found
        ):
            _fail("source archive has no complete original closure record")
    return records


def source_closure_location(root, journal, intent, coordinate):
    """Map only exact ORIGINAL physical data while normal logical stores expire."""
    for record in source_closure_records(root, journal, intent):
        source, archive, _ = _fixed_paths(root, record)
        live, retired = os.path.lexists(source), os.path.lexists(archive)
        if live == retired:
            _fail("source closure has ambiguous or missing physical custody")
        actual = source if live else archive
        if list(directory_node(actual)) != record["source_node"]:
            _fail("original source namespace changed")
        _residual(actual, record, restored=live)
        prefix = record["source_root"]
        if coordinate == prefix or coordinate.startswith(prefix + "/"):
            return actual / Path(coordinate).relative_to(prefix)
    return root / coordinate


@contextmanager
def restore_retired_source_namespaces(root, journal, intent):
    """Original recovery enters this BEFORE its ordinary live journal guards."""
    with _owned_stack() as stack:
        for record in source_closure_records(root, journal, intent):
            stack.enter_context(restored_source_namespace(root, record))
        yield
