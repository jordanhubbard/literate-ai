"""Fresh reviewed relocation admission and original transaction orchestration.

No saved plan is loaded as ownership. The public caller selects intent, supplies
its full fresh acknowledgement and explicit host authorization, and uses the
canonical operator state root. Public registration waits for complete consumer
and recovery integration; this module itself runs no build/test/acceptance code.
"""

from __future__ import annotations

import base64
import os
import stat
from pathlib import Path, PurePosixPath

from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock
from literate_ai.adapters.retained_layout import RetainedLayoutError, _fail
from literate_ai.adapters.retained_layout_compiler import (
    compile_retained_layout_transition,
)
from literate_ai.adapters.retained_layout_journal import (
    _begin_layout_journal,
    _file_stamp,
)
from literate_ai.adapters.retained_layout_partition import (
    _layout_modes,
    _layout_source_identity,
    _require_original,
    capture_retained_layout_source,
    observe_retained_layout_partition,
)
from literate_ai.adapters.retained_project_inputs import _directory_access
from literate_ai.adapters.standard_lifecycle_binding import (
    InstalledFrameworkDistribution,
    observe_installed_framework_distribution,
    observe_installed_framework_origin,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.project_initialization import ProjectInitializationOrigin
from literate_ai.contracts.retained_layout import RetainedLayoutDeclaration
from literate_ai.contracts.retained_project import RetainedProjectLimits
from literate_ai.projects import load_project


def _framework(distribution_observer, origin_observer):
    distribution = distribution_observer()
    if type(distribution) is not InstalledFrameworkDistribution:
        _fail("framework_invalid", "actual noneditable framework observation required")
    origin = origin_observer(distribution.distribution_version)
    if type(origin) is not ProjectInitializationOrigin or (
        origin.distribution_name != distribution.distribution_name
        or origin.distribution_version != distribution.distribution_version
    ):
        _fail(
            "framework_invalid", "framework origin differs from measured distribution"
        )
    return distribution, origin


def _framework_current(expected, distribution_observer, origin_observer):
    if _framework(distribution_observer, origin_observer) != expected:
        _fail("framework_changed", "actual framework bytes or origin changed")


def _extra_directory_intent(context, compiled):
    record = _require_original(context)
    body = compiled["plan"]
    publication = body["metadata_operations"]["publication"]
    directories = set(publication["framework_owned_directories"])
    for row in body["metadata_operations"]["replacements"]:
        parent = PurePosixPath(row["path"]).parent
        while parent.parts:
            directories.add(parent.as_posix())
            parent = parent.parent
    transient_parents = set()
    for name in record["transient_roles"]:
        parent = PurePosixPath(name).parent
        while parent.parts:
            transient_parents.add(parent.as_posix())
            parent = parent.parent
    context.require_framework_current(reserved_memory_bytes=8192 * len(directories))
    rows = []
    with _directory_access(record["root"]) as access:
        for name in sorted(directories, key=lambda x: (len(PurePosixPath(x).parts), x)):
            path = record["root"] / name
            try:
                node = access.metadata(path)
            except FileNotFoundError:
                node = None
            if node is not None and (
                not stat.S_ISDIR(node.st_mode)
                or node.st_dev != record["root_node"][0]
                or node.st_uid != os.geteuid()
                or node.st_mode & 0o022
            ):
                _fail("destination_unsafe", "framework destination directory is unsafe")
            # Only actual canonical lifecycle plumbing is normalized. Its native
            # owner is acquired after the first acknowledgement, before replan.
            rows.append(
                {
                    "path": name,
                    "mode": 0o755,
                    "transient": name in transient_parents,
                    "original_node": None
                    if node is None or name in transient_parents
                    else [str(v) for v in _file_stamp(node)],
                }
            )
        old_wrapper = context.layout.declaration.wrapper_component
        wrapper_node = access.metadata(record["root"] / old_wrapper)
    return rows, {
        "path": old_wrapper,
        "node": [str(v) for v in _file_stamp(wrapper_node)],
    }


def _compile(context, declaration, *, limits, case_sensitive, framework):
    compiled = compile_retained_layout_transition(
        context, declaration, limits=limits, case_sensitive=case_sensitive
    )
    directories, wrapper = _extra_directory_intent(context, compiled)
    body = {
        **compiled["plan"],
        "framework_distribution_identity": framework[0].identity.uri,
        "framework_origin_identity": framework[1].identity.uri,
        "framework_directories": directories,
        "original_wrapper_directory": wrapper,
    }
    context.require_framework_current()
    return {"plan": body, "plan_identity": canonical_identity(body).uri}


def plan_retained_layout_relocation(
    project,
    declaration,
    *,
    limits,
    case_sensitive,
    maximum_metadata_bytes=1024**3,
    distribution_observer=observe_installed_framework_distribution,
    origin_observer=observe_installed_framework_origin,
):
    """Read the actual complete source/authority without state/cache creation."""
    if (
        type(declaration) is not RetainedLayoutDeclaration
        or type(limits) is not RetainedProjectLimits
    ):
        raise TypeError("retained.layout.typed-transition-intent-required")
    framework = _framework(distribution_observer, origin_observer)
    loaded = load_project(Path(project))
    with observe_retained_layout_partition(
        loaded, maximum_metadata_bytes=maximum_metadata_bytes
    ) as context:
        result = _compile(
            context,
            declaration,
            limits=limits,
            case_sensitive=case_sensitive,
            framework=framework,
        )
        _framework_current(framework, distribution_observer, origin_observer)
    return result


def _require_descriptor_capacity(body):
    """Admit original held-file/directory custody before any transaction write."""
    if os.name != "posix":
        _fail(
            "native_owner_unavailable",
            "native layout transaction requires POSIX custody",
        )
    import resource

    soft, _ = resource.getrlimit(resource.RLIMIT_NOFILE)
    if soft == resource.RLIM_INFINITY:
        return
    # These are native kernel descriptor protocols, not operator-selected user
    # config/cache/temp roots. Match the native /proc readers' direct OS API use.
    descriptor_root = "/dev/fd"
    if not os.path.isdir(descriptor_root):
        descriptor_root = "/proc/self/fd"
    try:
        active = len(os.listdir(descriptor_root))
    except OSError as exc:
        _fail("descriptor_limit", "actual native descriptor capacity is unavailable")
        raise AssertionError from exc
    operations = body["source_operations"]
    metadata = body["metadata_operations"]
    # Native tree walks retain a bounded parent cache; journal custody additionally
    # keeps every created/removed directory and staged/original metadata file.
    # Reserve their simultaneous lifetimes plus traversal/plumbing headroom.
    required = (
        active
        + 128
        + 3
        * (
            len(operations["create_directories"])
            + len(operations["remove_empty_source_directories"])
            + sum(
                row["original_node"] is None and not row["transient"]
                for row in body["framework_directories"]
            )
        )
        + 4 * len(metadata["replacements"])
        + 2 * len(metadata["retirements"])
    )
    if required > soft:
        _fail(
            "descriptor_limit",
            "transaction needs "
            + str(required)
            + " native descriptors; current soft limit is "
            + str(soft),
        )


def _fresh_match(result, acknowledged):
    if result["plan_identity"] != acknowledged.uri:
        _fail("plan_changed", "full fresh relocation acknowledgement differs")


def _decode(value):
    return base64.b64decode(value, validate=True)


def _execute_source(owner, body):
    program = body["source_operations"]
    for row in program["create_directories"]:
        owner.create_directory(row["path"], mode=row["mode"])
    for row in program["move_leaves"]:
        owner.move(
            row["source"],
            row["destination"],
            expected_source=tuple(int(v) for v in row["source_node"]),
        )
    for row in program["remove_empty_source_directories"]:
        owner.remove_empty_source_directory(
            row["path"], expected_source=tuple(int(v) for v in row["source_node"])
        )


def _create_framework_directories(owner, root, rows):
    with _directory_access(root) as access:
        for row in rows:
            try:
                node = access.metadata(root / row["path"])
            except FileNotFoundError:
                node = None
            if row["original_node"] is not None:
                # Own source operations can alter parent directory timestamps;
                # compare its identity/mode/owner, not a fabricated new original.
                expected = tuple(int(v) for v in row["original_node"])
                if node is None or _file_stamp(node)[:5] != expected[:5]:
                    _fail("destination_changed", "original framework parent changed")
            if node is None:
                owner.create_directory(row["path"], mode=row["mode"])
            elif row["original_node"] is None and not row["transient"]:
                owner.require_created_directory(row["path"])
            elif not stat.S_ISDIR(node.st_mode):
                _fail("destination_changed", "framework parent became a foreign node")


def apply_retained_layout_relocation(
    project,
    declaration,
    *,
    limits,
    case_sensitive,
    acknowledged_plan_identity,
    authorize_relocation,
    state_root,
    maximum_metadata_bytes=1024**3,
    distribution_observer=observe_installed_framework_distribution,
    origin_observer=observe_installed_framework_origin,
):
    """Apply fresh intent under the canonical lock, retaining interrupted custody.

    This is not a plan-restoration API. No filesystem creation precedes explicit
    authorization, source/state disjointness and the first full fresh ACK match.
    """
    if authorize_relocation is not True:
        _fail(
            "host_authorization_required", "explicit relocation host authority required"
        )
    if type(acknowledged_plan_identity) is not ContentIdentity:
        raise TypeError("retained.layout.typed-full-plan-identity-required")
    root = Path(project).absolute()
    state = Path(state_root).absolute()
    if (
        root.resolve(strict=True) != root
        or state.resolve(strict=False) != state
        or root.is_relative_to(state)
        or state.is_relative_to(root)
    ):
        _fail(
            "state_overlaps_project",
            "actual project and canonical state must be disjoint",
        )
    options = dict(
        limits=limits,
        case_sensitive=case_sensitive,
        maximum_metadata_bytes=maximum_metadata_bytes,
        distribution_observer=distribution_observer,
        origin_observer=origin_observer,
    )
    fresh = plan_retained_layout_relocation(root, declaration, **options)
    _fresh_match(fresh, acknowledged_plan_identity)
    _require_descriptor_capacity(fresh["plan"])
    framework = _framework(distribution_observer, origin_observer)
    with project_lifecycle_lock(root, operation="retained-layout-relocation"):
        fresh = plan_retained_layout_relocation(root, declaration, **options)
        _fresh_match(fresh, acknowledged_plan_identity)
        with _begin_layout_journal(
            root,
            state_root=state,
            plan_identity=acknowledged_plan_identity,
            intent=fresh["plan"],
        ) as owner:
            try:
                # Issuance joins the actual pending owner, never a mutable flag added
                # to the preceding read-only context. Source remains unchanged here.
                with observe_retained_layout_partition(
                    load_project(root),
                    maximum_metadata_bytes=maximum_metadata_bytes,
                    _pending_owner=owner,
                ) as context:
                    current = _compile(
                        context,
                        declaration,
                        limits=limits,
                        case_sensitive=case_sensitive,
                        framework=framework,
                    )
                    _fresh_match(current, acknowledged_plan_identity)
                    body = current["plan"]
                    metadata = body["metadata_operations"]
                    for row in metadata["replacements"]:
                        owner.stage_metadata(row["path"], _decode(row["new_bytes"]))
                    _execute_source(owner, body)
                    context.require_framework_current()
                    _framework_current(
                        framework, distribution_observer, origin_observer
                    )
                # Old authority context closes before intentional metadata changes.
                # Every replacement is original-byte joined by the journal itself.
                _create_framework_directories(
                    owner, root, body["framework_directories"]
                )
                for row in metadata["retirements"]:
                    owner.retire_original_metadata(
                        row["path"], expected_bytes=_decode(row["old_bytes"])
                    )
                for row in metadata["replacements"]:
                    owner.publish_metadata(
                        row["path"],
                        expected_previous=(
                            None
                            if row["old_bytes"] is None
                            else _decode(row["old_bytes"])
                        ),
                    )
                old = body["original_wrapper_directory"]
                if (
                    old["path"] != declaration.wrapper_component
                    and not declaration.wrapper_component.startswith(old["path"] + "/")
                    and not declaration.implementation_directory.startswith(
                        old["path"] + "/"
                    )
                ):
                    owner.remove_empty_source_directory(
                        old["path"], expected_source=tuple(int(v) for v in old["node"])
                    )
                with observe_retained_layout_partition(
                    load_project(root),
                    maximum_metadata_bytes=maximum_metadata_bytes,
                    _pending_owner=owner,
                ) as context:
                    tree = capture_retained_layout_source(
                        context, limits=limits, case_sensitive=case_sensitive
                    )
                    modes, memory = _layout_modes(
                        context, tree, reserved_memory_bytes=0
                    )
                    actual = _layout_source_identity(tree.identity, modes)
                    if actual.uri != body["source_plan"]["source_identity"]:
                        _fail(
                            "source_changed",
                            "relocated complete source differs from "
                            "acknowledged source",
                        )
                    context.require_framework_current(
                        reserved_memory_bytes=tree.index.metadata_memory_bound + memory
                    )
                    del modes, tree
                    _framework_current(
                        framework, distribution_observer, origin_observer
                    )
                owner.retire_metadata_stage()
                owner.retire_pending(
                    publication_identity=canonical_identity(metadata["publication"]),
                    source_identity=actual,
                )
                owner.require_current()
            except BaseException as failure:
                try:
                    # Restore original parents before the old metadata names,
                    # then source leaves. Every move remains NOREPLACE and
                    # original-FD joined; a foreign winner stops recovery.
                    owner.rollback_metadata()
                    owner.rollback_removed_directories()
                    owner.rollback_retired_metadata()
                    owner.rollback_moves()
                    owner.rollback_created_directories()
                    owner.retire_metadata_stage()
                    owner.retire_pending(
                        publication_identity=ContentIdentity.parse_uri(
                            fresh["plan"]["source_plan"]["current_layout_identity"]
                        ),
                        source_identity=ContentIdentity.parse_uri(
                            fresh["plan"]["source_plan"]["source_identity"]
                        ),
                        outcome="rolled-back",
                    )
                except BaseException as recovery:
                    retained = BaseExceptionGroup(
                        "original and recovery failures retained", [failure, recovery]
                    )
                    if not isinstance(failure, Exception):
                        raise retained from None
                    raise RetainedLayoutError(
                        "retained.layout.recovery_incomplete",
                        "relocation stopped with unresolved owned/private state; "
                        "preserve the pending marker and private recovery journal",
                    ) from retained
                if isinstance(failure, OSError):
                    raise RetainedLayoutError(
                        "retained.layout.transaction_failed",
                        "relocation failed; original owned source "
                        "and metadata restored",
                    ) from failure
                raise

    return {
        "schema": "literate-ai/retained-layout-relocation-result@1",
        "status": "relocated",
        "plan_identity": acknowledged_plan_identity.uri,
        "source_identity": actual.uri,
        "layout_identity": canonical_identity(metadata["publication"]).uri,
        "requalification_required": True,
        "old_receipt_rewritten": False,
    }
