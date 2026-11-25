"""Read-only normal-producer classification for an actual catalog transition.

This does not renew records, finalize placement, restore owners, or retire source
names. Reports are data. A later call must hold its own original lease and repeat
all checks; even a current result is not future write authority.
"""

from __future__ import annotations

from literate_ai import _cache_lock as cache_lock
from literate_ai import _filesystem as filesystem
from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import exclusive_directory as exclusive
from literate_ai.adapters import project_layout_continuation as writer
from literate_ai.adapters import project_layout_filesystem as leaf
from literate_ai.adapters import (
    project_layout_framework_transaction as framework_writer,
)
from literate_ai.adapters import project_layout_lease as lease_module
from literate_ai.adapters import project_layout_migration as migration
from literate_ai.adapters import project_layout_planning as planning
from literate_ai.adapters import qualification_workspace_namespace as namespace
from literate_ai.adapters.project_layout_component_transition import (
    require_original_component_transition as _ADMIT_TRANSITION,
)
from literate_ai.adapters.project_layout_lease import require_layout_lease as _LEASE
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_json_bytes
from literate_ai.projects import ProjectConfigurationSnapshot, ProjectConfigurationStore

_ADMIT_PREPARED = operations.require_original_prepared_component_lock
_OPERATE = operations.operate_component_lock
_PROJECT_READ = ProjectConfigurationStore.read


def _fail(message):
    raise ProjectLayoutPlanError("component_destination_unavailable", message)


def _build_classifier(*, framework=False):
    """Origin-bound closure; no module checker lookup after foreign callbacks.

    Rebuilding under explicit test seams produces a modeled classifier only.
    Production dispatch uses only the three values issued at module origin below.
    """
    error_type = ProjectLayoutPlanError
    dispatch = (
        (
            "_framework_callbacks_current",
            "_framework_call",
            "classify_framework_component_destination",
        )
        if framework
        else ("_callbacks_current", "_call", "classify_component_destination")
    )

    def fail(message):
        raise error_type("component_destination_unavailable", message)

    admit_transition, admit_prepared = _ADMIT_TRANSITION, _ADMIT_PREPARED
    lease_current, operate = _LEASE, _OPERATE
    read_project, project_store = _PROJECT_READ, ProjectConfigurationStore
    original_owner = vars(writer)["_owner"]
    aliases = tuple(
        (name, globals()[name])
        for name in (
            "_ADMIT_TRANSITION",
            "_ADMIT_PREPARED",
            "_LEASE",
            "_OPERATE",
            "_PROJECT_READ",
            "ProjectConfigurationStore",
            "ProjectConfigurationSnapshot",
            "canonical_json_bytes",
            "operations",
            "writer",
            "framework_writer",
            "migration",
            "leaf",
            "filesystem",
            "exclusive",
            "planning",
            "namespace",
            "cache_lock",
            "_fail",
            "ProjectLayoutPlanError",
            "lease_module",
        )
    )
    # Raw module slots, not attributes adopted from writer._owner() after a callback.
    modules = tuple(
        (module, tuple((name, vars(module)[name]) for name in names))
        for module, names in (
            (
                writer,
                (
                    "_decode_intent",
                    "_guard_journal",
                    "_guard",
                    "_entry_state",
                    "_owner",
                    "_view",
                    "_guard_directories",
                    "_source_location",
                    "_names",
                    "directory_node",
                    "_matches",
                ),
            ),
            (
                framework_writer,
                (
                    "_decode",
                    "_guard",
                    "_guard_intent",
                    "_state",
                    "_entries",
                    "journal_path",
                ),
            ),
            (
                migration,
                (
                    "_file",
                    "_identity",
                    "read_migration_file",
                    "_stamp",
                    "_fail",
                    "_MAX_FILE_BYTES",
                    "_require_worktree_members",
                    "_git_state",
                ),
            ),
            (
                leaf,
                (
                    "read_migration_file",
                    "_read",
                    "_windows",
                    "require_safe_directory",
                    "stat_is_link_or_reparse",
                    "os",
                    "stat",
                    "Path",
                ),
            ),
            (filesystem, ("require_safe_directory", "stat_is_link_or_reparse")),
            (
                exclusive,
                ("directory_node", "require_safe_directory", "stat_is_link_or_reparse"),
            ),
            (planning, ("_stamp", "_git_state", "_fail")),
            (namespace, ("hold_qualification_workspace_namespace",)),
            (cache_lock, ("_Kernel32Windows",)),
            (
                lease_module,
                ("_git_marker", "native_directory_identity", "_identity_matches"),
            ),
            (
                operations,
                ("require_original_prepared_component_lock", "operate_component_lock"),
            ),
            (leaf.os, ("open", "fdopen", "fstat", "lstat", "stat", "scandir", "name")),
        )
    )
    native_classes = tuple(
        (
            cls,
            tuple(type.__getattribute__(cls, "__dict__").items()),
            type.__getattribute__(cls, "__bases__"),
            type.__getattribute__(cls, "__mro__"),
        )
        for cls in dict.fromkeys(
            (
                cache_lock._Kernel32Windows,
                *leaf.Path.__mro__,
                *type(leaf.Path()).__mro__,
            )
        )
    )

    def _callbacks_current():
        if (
            any(globals().get(name) is not original for name, original in aliases)
            or globals().get(dispatch[0]) is not _callbacks_current
            or globals().get(dispatch[1]) is not _call
            or globals().get(dispatch[2]) is not classify_component_destination
            or any(
                vars(module).get(name) is not original
                for module, members in modules
                for name, original in members
            )
        ):
            fail("original destination delegate/checker changed")
        if original_owner() is not migration:
            fail("original migration module owner changed")
        for cls, members, bases, mro in native_classes:
            current = type.__getattribute__(cls, "__dict__")
            if (
                type.__getattribute__(cls, "__bases__") is not bases
                or type.__getattribute__(cls, "__mro__") is not mro
                or set(current) != {name for name, _ in members}
                or any(current[name] is not original for name, original in members)
            ):
                fail("original destination native class changed")

    def _call(function, *args, **kwargs):
        _callbacks_current()
        result = function(*args, **kwargs)
        _callbacks_current()
        return result

    def classify_component_destination(
        transition,
        expected_snapshot,
        *,
        prepared,
        layout_lease,
        plan_identity,
    ):
        """Classify a genuine normal preparation against exact placed/history facts.

        The actual prepared target/flavor selection is reused, never reconstructed
        from archive names or a synthetic import. Any original input/currentness or
        storage exception propagates; only normal check return 1 means renewal.
        Root layout coordination is held, but no generic component operation/write
        file fences are acquired here. Ordinary renewal belongs outside those fences.
        """
        _callbacks_current()
        admit_transition(transition)  # pure origin; source guard expired after move
        if type(expected_snapshot) is not ProjectConfigurationSnapshot:
            fail("exact independently expected destination snapshot required")
        root = expected_snapshot.root
        lease_current(layout_lease, root)
        planner, target, flavors, flavor_roots = admit_prepared(prepared)
        target_root = root / transition.destination_root
        if (
            transition.source_kind
            not in ("inherited", "initialized", "recorded-wrapper")
            or prepared.component_root != target_root
            or prepared.catalog_snapshot is None
            or prepared.catalog_snapshot.project is None
            or transition.target_names != (target,)
            or prepared.plan.target_name != target
            or prepared.result.lock.target_name != target
            or prepared.result.catalog_audit.component_lock_identity
            != prepared.result.lock.identity
            or prepared.result.catalog_audit.resolver_identity
            != prepared.result.lock.resolver_identity
            or prepared.plan.root_authoring_identity
            != prepared.catalog_snapshot.root_authoring.identity
        ):
            fail("original prepared destination/target/catalog join differs")
        expected_fields = tuple(
            object.__getattribute__(expected_snapshot, name)
            for name in (
                "root",
                "manifest_path",
                "definition",
                "content",
                "directory_binding",
            )
        )
        original_prepared = prepared
        journal = intent = None

        def require_original():
            _callbacks_current()
            admit_transition(transition)
            admit_prepared(original_prepared)
            if any(
                object.__getattribute__(expected_snapshot, name) is not value
                for name, value in zip(
                    (
                        "root",
                        "manifest_path",
                        "definition",
                        "content",
                        "directory_binding",
                    ),
                    expected_fields,
                    strict=True,
                )
            ):
                fail("original expected destination snapshot changed")
            lease_current(layout_lease, root)
            actual = _call(read_project, project_store(root))
            admit_transition(transition)
            admit_prepared(original_prepared)
            if (
                actual.content != expected_snapshot.content
                or actual.definition != expected_snapshot.definition
                or actual.directory_binding != expected_snapshot.directory_binding
                or actual.manifest_path != expected_snapshot.manifest_path
                or prepared.catalog_snapshot.project.definition != actual.definition
            ):
                fail("expected original destination project changed")
            if intent is not None:
                if framework:
                    _call(
                        framework_writer._guard,
                        root,
                        intent["plan"],
                        layout_lease,
                        None,
                    )
                else:
                    _call(writer._guard, root, intent["plan"])
            lease_current(layout_lease, root)
            admit_transition(transition)
            admit_prepared(original_prepared)
            _callbacks_current()
            if any(
                object.__getattribute__(expected_snapshot, name) is not value
                for name, value in zip(
                    (
                        "root",
                        "manifest_path",
                        "definition",
                        "content",
                        "directory_binding",
                    ),
                    expected_fields,
                    strict=True,
                )
            ):
                fail("original expected snapshot changed during closing guard")

        require_original()
        journal, intent = _call(
            framework_writer._decode if framework else writer._decode_intent,
            root,
            plan_identity,
        )
        matching = [
            row
            for row in intent["components"]
            if row["source_root"] == transition.source_root
            and row["destination_root"] == transition.destination_root
            and row["manifest_identity"] == transition.manifest_identity
            and tuple(row["target_names"]) == transition.target_names
        ]
        if (
            len(matching) != 1
            or len(intent["components"]) != 1
            or intent["plan"]["project_id"] != expected_snapshot.definition.project_id
        ):
            fail("classifier requires exactly this one original selected Component")

        # Coordinates are determined by the actual normal prepared producer stores.
        lock_store = operations.ComponentLockStore(prepared.component_root)
        audit_store = operations.ComponentResolutionAuditStore(
            prepared.component_root, target
        )
        lock_path, audit_path = lock_store.path, audit_store.path
        if (
            lock_store.storage_root != target_root
            or audit_store.storage_root != target_root
        ):
            fail("producer storage mapping requires its original mapped owner")
        require_original()
        producer_postimages = {
            lock_path.relative_to(root).as_posix(): canonical_json_bytes(
                prepared.result.lock.to_dict()
            )
            + b"\n",
            audit_path.relative_to(root).as_posix(): canonical_json_bytes(
                prepared.result.catalog_audit.to_dict()
            )
            + b"\n",
        }
        old_producer_destinations = {
            intent["entries"][coordinate]["destination"]
            for coordinate in transition.records
        }
        if old_producer_destinations != set(producer_postimages):
            fail("original selected producer coordinate inventory differs")

        def require_data():
            require_original()
            _call(
                framework_writer._guard_intent if framework else writer._guard_journal,
                root,
                journal,
                intent,
            )
            for coordinate, record in transition.records.items():
                if framework:
                    try:
                        _call(leaf.os.lstat, root / coordinate)
                    except FileNotFoundError:
                        pass
                    else:
                        fail("original framework producer coordinate became occupied")
                    archived = intent["entries"].get(coordinate)
                    if (
                        archived is None
                        or archived["from"] != record["identity"]
                        or archived["mode"] != record["mode"]
                        or archived["owner"] != "original-component-producer"
                        or archived["destination"]
                        != transition.destination_root
                        + coordinate[len(transition.source_root) :]
                    ):
                        fail("original framework producer history binding differs")
                    saved = journal / "before" / archived["slot"]
                    if not writer._matches(
                        writer._view(saved), archived, original=True
                    ):
                        fail("original framework producer backup custody changed")
                    archived_bytes = writer._owner()._file(saved)[1]
                else:
                    archived = intent["history"].get(coordinate)
                    if (
                        archived is None
                        or archived["identity"] != record["identity"]
                        or archived["mode"] != record["mode"]
                        or archived["kind"] != record["kind"]
                        or archived["typed_identity"] != record.get("typed_identity")
                    ):
                        fail("original producer history binding differs")
                    archived_bytes = writer._owner()._file(
                        journal / "history" / archived["slot"]
                    )[1]
                if archived_bytes != transition.original_contents[coordinate]:
                    fail("original producer beforebytes changed")
            for source, entry in intent["entries"].items():
                if entry["destination"] not in producer_postimages:
                    if (
                        _call(
                            framework_writer._state
                            if framework
                            else writer._entry_state,
                            root,
                            journal,
                            source,
                            entry,
                        )
                        != "published"
                    ):
                        fail("nonproducer original postimage is not exactly published")
            require_original()

        require_data()
        # The existing normal checker independently reproduces the prepared plan,
        # takes two stable typed artifact observations and performs closing rechecks.
        report, status = _call(
            operate,
            prepared,
            target=target,
            flavors=flavors,
            flavor_roots=flavor_roots,
            planner=planner,
            check=True,
            difference=False,
        )
        require_data()
        if type(status) is not int or status not in (0, 1):
            fail("normal producer returned an unknown check result")
        if (
            type(report) is not dict
            or report.get("schema") != "literate-ai/component-lock-command@1"
            or report.get("mode") != "check"
            or report.get("component") != str(prepared.component_root)
            or report.get("target") != target
            or report.get("resolution_plan_identity") != prepared.plan.identity.uri
            or report.get("component_lock_identity")
            != prepared.result.lock.identity.uri
            or report.get("catalog_audit_identity")
            != prepared.result.catalog_audit.identity.uri
            or report.get("current") is not (status == 0)
        ):
            fail("normal producer result contradicts its exact prepared check")
        # Only producer files may have new inodes from normal atomic renewal,
        # never payloads. A typed different pair is renewal-required, but changed
        # file kind/mode or missing placed bytes remain original storage refusals.
        for coordinate, payload in producer_postimages.items():
            _node, actual, mode = writer._owner()._file(root / coordinate)
            source = next(
                source
                for source, entry in intent["entries"].items()
                if entry["destination"] == coordinate
            )
            if mode != intent["entries"][source]["mode"]:
                fail("producer mode changed outside the original placement")
            if status == 0 and actual != payload:
                fail("current producer pair differs from exact prepared postimage")
        require_data()
        return {
            "schema": "literate-ai/project-layout-component-destination-state@1",
            "state": "current" if status == 0 else "renewal-required",
            "source_kind": transition.source_kind,
            "plan_identity": plan_identity,
            "destination_root": transition.destination_root,
            "prepared_plan_identity": prepared.plan.identity.uri,
            "component_lock_identity": prepared.result.lock.identity.uri,
            "catalog_audit_identity": prepared.result.catalog_audit.identity.uri,
            "writes": False,
            "finalized": False,
            "full_containment": False,
            "qualification": False,
        }

    return _callbacks_current, _call, classify_component_destination


_callbacks_current, _call, classify_component_destination = _build_classifier()


# Separate original exports select the exact journal protocol at module origin.
# A serialized plan or caller boolean is never used as transition admission.
(
    _framework_callbacks_current,
    _framework_call,
    classify_framework_component_destination,
) = _build_classifier(framework=True)
