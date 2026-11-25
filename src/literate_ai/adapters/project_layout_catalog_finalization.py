"""Fresh actual Root/normal producers close original catalog source namespaces.

Original catalog intent and source/producer history stay immutable. Physical
source control descriptors and original records supply bounded custody; they
never restore a retired source transition or retarget a normal source store.
"""

from __future__ import annotations

import os
import uuid
from contextlib import ExitStack, contextmanager
from pathlib import Path

from literate_ai._cache_lock import _acquire, _identity_matches, _release
from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import component_namespace_closing as physical
from literate_ai.adapters import project_layout_catalog_renewal as renewal
from literate_ai.adapters import project_layout_catalog_successor as successor_owner
from literate_ai.adapters import project_layout_continuation as native
from literate_ai.adapters import project_layout_migration as filesystem
from literate_ai.adapters.component_lock_planning import FilesystemComponentLockPlanner
from literate_ai.adapters.exclusive_directory import (
    directory_node,
    move_file_between_owned_parents_exclusive,
    publish_directory_between_owned_parents_exclusive,
)
from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
)
from literate_ai.adapters.project_layout_lease import (
    current_layout_lease,
    require_layout_lease,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity, canonical_json_bytes
from literate_ai.projects import ProjectConfigurationStore


def _fail(message):
    raise ProjectLayoutPlanError("catalog_finalization_conflict", message)


def _views(root, journal, intent, lease, namespace, successor):
    _bindings()
    renewal._guard(root, journal, intent, lease, namespace, successor=successor)
    if "retired-source" not in intent["journal_directories"]:
        _fail("original v1 catalog journal supports rollback, not source closure")
    if not os.path.lexists(journal / "completed") or os.path.lexists(
        journal / "rolled-back"
    ):
        _fail("source closure requires completed original catalog placement")
    selected = {}
    for component, target in renewal._pairs(intent):
        path = renewal._path(root, intent, component, target)
        if os.path.lexists(path):
            _path, record = renewal._decode(root, intent, component, target)
            selected[(component["source_root"], target)] = record["selection"]
    _bindings()
    return selected


def _normal_current(root, journal, intent, lease, namespace, successor):
    selected = _views(root, journal, intent, lease, namespace, successor)
    snapshot = ProjectConfigurationStore(root).read()
    reports = []
    for component in intent["components"]:
        destination = root / component["destination_root"]
        if (
            filesystem._identity(filesystem._file(destination / "component.md")[1])
            != component["manifest_identity"]
        ):
            _fail("actual destination Component differs from original authoring")
        catalog = FilesystemLockedGenerationAuthorityReader().load_catalog(destination)
        _views(root, journal, intent, lease, namespace, successor)
        if (
            catalog.project is None
            or catalog.project.root != root
            or catalog.project.definition != snapshot.definition
        ):
            _fail("current destination catalog belongs to another project")
        catalog.require_unchanged()
        for target in component["target_names"]:
            selection = selected.get((component["source_root"], target))
            flavors = tuple(selection["flavors"]) if selection else ()
            roots = tuple(
                root / path
                for path in (
                    selection["flavor_roots"]
                    if selection
                    else snapshot.definition.flavor_roots
                )
            )
            prepared = operations.prepare_component_lock(
                destination,
                target=target,
                flavors=flavors,
                flavor_roots=roots,
                planner=FilesystemComponentLockPlanner(),
            )
            _views(root, journal, intent, lease, namespace, successor)
            planner, actual_target, actual_flavors, actual_roots = (
                operations.require_original_prepared_component_lock(prepared)
            )
            if selection and (
                prepared.plan.identity.uri != selection["prepared_plan_identity"]
                or prepared.result.lock.identity.uri
                != selection["component_lock_identity"]
                or prepared.result.catalog_audit.identity.uri
                != selection["catalog_audit_identity"]
            ):
                _fail("fresh normal producer differs from original selected renewal")
            report, status = operations.operate_component_lock(
                prepared,
                target=actual_target,
                flavors=actual_flavors,
                flavor_roots=actual_roots,
                planner=planner,
                check=True,
                difference=False,
            )
            _views(root, journal, intent, lease, namespace, successor)
            operations.require_original_prepared_component_lock(prepared)
            if (
                type(status) is not int
                or status != 0
                or report.get("current") is not True
            ):
                _fail("original destination requires ordinary producer renewal")
            reports.append(report)
    return reports


def _record(root, journal, intent, component):
    source = component["source_root"]
    payloads, directories, coordination = physical._expected_preimages(intent, source)
    record = {
        "schema": "literate-ai/component-source-namespace-closure@1",
        "project": str(root),
        "plan_identity": intent["plan"]["plan_identity"],
        "source_root": source,
        "source_node": intent["original_directories"][source],
        "coordination": coordination,
        "empty_directories": directories,
        "payloads": payloads,
        "source_parent_node": intent["original_directories"][
            Path(source).parent.as_posix()
        ],
        "archive_parent_node": intent["journal_directories"]["retired-source"],
    }
    physical._validate_record(record, root, intent["plan"])
    return record


def _location(root, journal, intent, record):
    return physical.source_closure_location(
        root, journal, intent, record["source_root"]
    )


@contextmanager
def _held(root, journal, intent, lease, namespace, successor, record):
    _normal_current(root, journal, intent, lease, namespace, successor)
    source, archive, _path = physical._fixed_paths(root, record)
    actual = archive if os.path.lexists(archive) else source
    identity = canonical_identity(record).uri
    with ExitStack() as stack:
        directory = os.open(actual, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        stack.callback(os.close, directory)
        descriptors = {}
        for name, expected in record["coordination"].items():
            fd = os.open(
                name, os.O_RDWR | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory
            )
            stack.callback(os.close, fd)
            if physical._file_record(fd) != expected:
                _fail("original source control changed before independent hold")
            _acquire(fd, actual / name, timeout_seconds=0)
            stack.callback(_release, fd)
            descriptors[name] = fd

        def current():
            _bindings()
            if canonical_identity(record).uri != identity:
                _fail("original source closing record changed")
            _normal_current(root, journal, intent, lease, namespace, successor)
            if canonical_identity(record).uri != identity:
                _fail("original source record changed during normal closing check")
            actual = _location(root, journal, intent, record)
            observed = os.fstat(directory)
            if (
                [observed.st_dev, observed.st_ino, observed.st_mode]
                != record["source_node"]
                or list(directory_node(actual)) != record["source_node"]
                or list(directory_node(source.parent)) != record["source_parent_node"]
                or list(directory_node(archive.parent)) != record["archive_parent_node"]
            ):
                _fail("original held source or native parent changed")
            physical._residual(actual, record)
            for name, fd in descriptors.items():
                path = actual / name
                if (
                    not _identity_matches(path, path.lstat(), fd, os.fstat(fd))
                    or physical._file_record(fd) != record["coordination"][name]
                ):
                    _fail("held source coordination inode changed")
            if canonical_identity(record).uri != identity:
                _fail("original source record changed during native closing check")
            _bindings()

        current()
        yield current
        current()


def _move(root, record, namespace):
    source, archive, _path = physical._fixed_paths(root, record)
    with (
        native._parent_scope(namespace, source.parent),
        native._parent_scope(namespace, archive.parent),
    ):
        publish_directory_between_owned_parents_exclusive(
            source,
            archive,
            expected_source=tuple(record["source_node"]),
            expected_source_parent=tuple(record["source_parent_node"]),
            expected_destination_parent=tuple(record["archive_parent_node"]),
        )
        filesystem._flush(source.parent)
        filesystem._flush(archive.parent)


def _close(root, journal, intent, component, lease, namespace, successor, move):
    record = _record(root, journal, intent, component)
    source, archive, path = physical._fixed_paths(root, record)
    if os.path.lexists(path):
        physical.source_closure_records(root, journal, intent)
        if os.path.lexists(archive):
            return
    else:
        if os.path.lexists(archive):
            _fail("original source archive has no closure record")
        physical._residual(source, record)
    with _held(root, journal, intent, lease, namespace, successor, record) as current:
        if not os.path.lexists(path):
            data = (
                canonical_json_bytes(
                    {**record, "identity": canonical_identity(record).uri}
                )
                + b"\n"
            )
            pending = path.with_name(
                "." + archive.name + ".pending-" + uuid.uuid4().hex
            )
            current()
            with native._parent_scope(namespace, pending.parent):
                fd = os.open(
                    pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600
                )
                try:
                    with os.fdopen(fd, "wb", closefd=False) as stream:
                        stream.write(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                finally:
                    os.close(fd)
            filesystem._flush(pending.parent)
            node = filesystem._file(pending)[0]
            current()
            with native._parent_scope(namespace, path.parent):
                move_file_between_owned_parents_exclusive(
                    pending,
                    path,
                    expected_source=tuple(node),
                    expected_source_parent=tuple(record["archive_parent_node"]),
                    expected_destination_parent=tuple(record["archive_parent_node"]),
                )
            filesystem._flush(path.parent)
        current()
        move(root, record, namespace)
        current()


def finalize_catalog_components(root, expected, *, successor_plan_identity=None):
    check, move = _bindings, _move
    check()
    if os.name != "posix":
        _fail("source closing needs qualified native rename-compatible control handles")
    root = Path(root).absolute()
    lease = current_layout_lease(root)
    require_layout_lease(lease, root)
    journal, intent = native._decode_intent(root, expected)
    successor = (
        successor_owner.observe_catalog_successor(
            root, journal, intent, lease, None, successor_plan_identity
        )
        if successor_plan_identity is not None
        else None
    )
    with native._operation(root) as namespace, native._reserve(root, namespace):
        _normal_current(root, journal, intent, lease, namespace, successor)
        for component in intent["components"]:
            _close(root, journal, intent, component, lease, namespace, successor, move)
        reports = _normal_current(root, journal, intent, lease, namespace, successor)
        records = physical.source_closure_records(root, journal, intent)
        names = {record["source_root"] for record in records}
        if names != {component["source_root"] for component in intent["components"]}:
            _fail("original catalog source closing inventory is incomplete")
        for record in records:
            source, archive, _path = physical._fixed_paths(root, record)
            if os.path.lexists(source) or not os.path.lexists(archive):
                _fail("original catalog source namespace remains live")
        return {
            "components_finalized": True,
            "closed_components": sorted(names),
            "normal_producers": reports,
            "full_containment": False,
            "qualification": False,
        }


def _bind():
    namespace = globals()
    aliases = tuple(
        (name, namespace[name])
        for name in (
            "_fail",
            "_views",
            "_normal_current",
            "_record",
            "_location",
            "_held",
            "_close",
            "finalize_catalog_components",
            "operations",
            "physical",
            "renewal",
            "successor_owner",
            "native",
            "filesystem",
            "os",
            "uuid",
            "Path",
            "ExitStack",
            "contextmanager",
            "FilesystemComponentLockPlanner",
            "FilesystemLockedGenerationAuthorityReader",
            "ProjectConfigurationStore",
            "current_layout_lease",
            "require_layout_lease",
            "canonical_identity",
            "canonical_json_bytes",
            "directory_node",
            "move_file_between_owned_parents_exclusive",
            "publish_directory_between_owned_parents_exclusive",
            "_acquire",
            "_identity_matches",
            "_release",
        )
    )
    delegates = tuple(
        (module, name, vars(module)[name])
        for module, names in (
            (
                operations,
                (
                    "prepare_component_lock",
                    "require_original_prepared_component_lock",
                    "operate_component_lock",
                ),
            ),
            (
                renewal,
                ("_guard", "_decode", "_path", "_pairs", "_state", "_journal_current"),
            ),
            (
                successor_owner,
                ("observe_catalog_successor", "require_catalog_successor"),
            ),
            (
                native,
                (
                    "_decode_intent",
                    "_current",
                    "_operation",
                    "_reserve",
                    "_parent_scope",
                ),
            ),
            (
                physical,
                (
                    "_expected_preimages",
                    "_validate_record",
                    "_fixed_paths",
                    "_file_record",
                    "_residual",
                    "_census_residual",
                    "_capture",
                    "source_closure_records",
                    "source_closure_location",
                ),
            ),
            (filesystem, ("_file", "_identity", "_flush")),
            (ProjectConfigurationStore, ("read",)),
            (FilesystemLockedGenerationAuthorityReader, ("load_catalog",)),
        )
        for name in names
    )
    error_type = ProjectLayoutPlanError

    def check():
        if (
            namespace.get("_bindings") is not check
            or any(namespace.get(name) is not original for name, original in aliases)
            or any(
                vars(module).get(name) is not original
                for module, name, original in delegates
            )
        ):
            raise error_type(
                "catalog_finalization_conflict",
                "original fresh source-closing delegate changed",
            )

    return check


_bindings = _bind()
