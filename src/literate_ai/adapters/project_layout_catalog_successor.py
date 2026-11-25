"""Current Root/native custody joins an explicitly selected successor journal.

Stored identities describe history. Every use revalidates both actual journals,
native preimages and the current Root lease; no retired source actor is restored.
"""

from __future__ import annotations

import os

from literate_ai.adapters import project_layout_continuation as native
from literate_ai.adapters import project_layout_framework_renewal as renewal
from literate_ai.adapters import project_layout_framework_transaction as framework
from literate_ai.adapters import project_layout_migration as filesystem
from literate_ai.adapters.project_layout_lease import require_layout_lease
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import ContentIdentity, canonical_identity


def _fail(message):
    raise ProjectLayoutPlanError("catalog_successor_conflict", message)


def validate_successor_binding(binding):
    if type(binding) is not dict or set(binding) != {
        "plan_identity",
        "intent_identity",
    }:
        _fail("exact original successor identities required")
    for value in binding.values():
        ContentIdentity.parse_uri(value)


def _load(root, expected):
    path = framework.journal_path(root, expected)
    filesystem._require_worktree_members(
        root, ((path / "intent.json").relative_to(root).as_posix(),)
    )
    try:
        return framework._decode(root, expected)
    except OSError as error:
        raise ProjectLayoutPlanError(
            "catalog_successor_conflict", "original successor journal unavailable"
        ) from error


def _published_framework(root, journal, intent, lease, namespace):
    outputs = {}
    for component, target in renewal._expected_pairs(intent):
        path = renewal._path(
            root, intent["plan"]["plan_identity"], component["source_root"], target
        )
        filesystem._require_worktree_members(
            root, ((path / "intent.json").relative_to(root).as_posix(),)
        )
        if not os.path.lexists(path):
            continue
        path, record = renewal._decode(
            root, intent["plan"]["plan_identity"], component, target, intent
        )
        renewal._guard_journal(root, path, record, journal, intent, lease, namespace)
        if not os.path.lexists(path / "renewed") or os.path.lexists(
            path / "rolled-back"
        ):
            _fail("successor normal producer must finish or recover first")
        for coordinate, row in record["entries"].items():
            expected = "original" if row["from"] == row["to"] else "published"
            if (
                coordinate in outputs
                or renewal._state(root, path, coordinate, row) != expected
            ):
                _fail("successor normal producer has foreign or overlapping custody")
            outputs[coordinate] = row
    for source, row in intent["entries"].items():
        if row["destination"] in outputs:
            if (
                not native._matches(
                    native._view(journal / "before" / row["slot"]),
                    row,
                    original=True,
                )
                or native._view(journal / "after" / row["slot"]) is not None
                or os.path.lexists(root / source)
            ):
                _fail("successor original producer history changed")
        elif framework._state(root, journal, source, row) != "published":
            _fail("successor original postimage is not published")


def require_catalog_successor(
    root, parent, intent, lease, namespace, binding, *, recovering=False
):
    """Return only catalog rows whose exact postimage a current successor holds."""
    _bindings()
    require_layout_lease(lease, root)
    validate_successor_binding(binding)
    journal, successor = _load(root, binding["plan_identity"])
    if canonical_identity(successor).uri != binding["intent_identity"] or any(
        successor["plan"][name] != intent["plan"][name]
        for name in ("project", "project_id", "root_node", "framework_node")
    ):
        _fail("successor differs from the original catalog Root/history")
    framework._current(root, journal, successor, lease, namespace)
    rolled_back = os.path.lexists(journal / "rolled-back")
    if recovering:
        if not rolled_back:
            _fail("recover the original framework successor before catalog recovery")
        for source, row in successor["entries"].items():
            if framework._state(root, journal, source, row) != "original":
                _fail("successor has not restored its exact original epoch")
    else:
        if rolled_back or not os.path.lexists(journal / "placed"):
            _fail("normal producer requires completed original successor placement")
        _published_framework(root, journal, successor, lease, namespace)
    joined = set()
    for source, row in intent["entries"].items():
        later = successor["entries"].get(row["destination"])
        if later is None:
            continue
        expected = row["after_node"], row["to"], row["mode"]
        if (later["node"], later["from"], later["mode"]) != expected:
            _fail("successor beforeimage is not the exact original catalog postimage")
        location = (
            root / row["destination"]
            if rolled_back
            else journal / "before" / later["slot"]
        )
        if (
            native._view(location) != expected
            or not native._matches(
                native._view(parent / "before" / row["slot"]), row, original=True
            )
            or native._view(parent / "after" / row["slot"]) is not None
            or (source != row["destination"] and os.path.lexists(root / source))
        ):
            _fail("original catalog/successor native handoff custody changed")
        joined.add(source)
    if not joined:
        _fail("selected successor holds no original catalog metadata postimage")
    framework._current(root, journal, successor, lease, namespace)
    require_layout_lease(lease, root)
    _bindings()
    return set() if rolled_back else joined


def observe_catalog_successor(root, parent, intent, lease, namespace, expected):
    _bindings()
    journal, successor = _load(root, expected)
    binding = {
        "plan_identity": expected,
        "intent_identity": canonical_identity(successor).uri,
    }
    require_catalog_successor(root, parent, intent, lease, namespace, binding)
    return binding


def _bind():
    namespace = globals()
    aliases = tuple(
        (name, namespace[name])
        for name in (
            "_fail",
            "_load",
            "_published_framework",
            "validate_successor_binding",
            "require_catalog_successor",
            "observe_catalog_successor",
            "native",
            "renewal",
            "framework",
            "filesystem",
            "os",
            "ContentIdentity",
            "canonical_identity",
            "require_layout_lease",
        )
    )
    delegates = tuple(
        (module, name, vars(module)[name])
        for module, names in (
            (
                framework,
                (
                    "journal_path",
                    "_decode",
                    "_current",
                    "_state",
                    "_guard_intent",
                    "_guard",
                ),
            ),
            (
                renewal,
                (
                    "_expected_pairs",
                    "_path",
                    "_decode",
                    "_guard_journal",
                    "_state",
                    "_bindings",
                ),
            ),
            (native, ("_view", "_matches")),
            (filesystem, ("_require_worktree_members",)),
        )
        for name in names
    )
    error_type = ProjectLayoutPlanError
    require_original_framework = renewal._bindings

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
                "catalog_successor_conflict",
                "original successor owner delegate changed",
            )

        require_original_framework()

    return check


_bindings = _bind()
