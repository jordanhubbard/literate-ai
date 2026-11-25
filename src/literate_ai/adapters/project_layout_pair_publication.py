"""Finite native pair publication shared by original migration owners.

Only genuine normal preparations enter. Call-local native guards and move ports
come from the owning migration, never from serialized plan or result data.
"""

from __future__ import annotations

from literate_ai import _atomic_publication as atomic
from literate_ai.adapters import component_lock_operations as operations
from literate_ai.adapters import project_layout_migration as filesystem
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from literate_ai.contracts import canonical_identity

_ADMIT = operations.require_original_prepared_component_lock
_OPERATE = operations.operate_component_lock
_SCOPE = atomic.atomic_publication_scope
_SCOPED = atomic._scoped_atomic_writer


def _bind_publisher():
    namespace = globals()
    aliases = tuple(
        (name, namespace[name])
        for name in (
            "_ADMIT",
            "_OPERATE",
            "_SCOPE",
            "_SCOPED",
            "canonical_identity",
            "operations",
            "atomic",
            "filesystem",
        )
    )
    delegates = tuple(
        (module, name, vars(module)[name])
        for module, names in (
            (
                operations,
                ("require_original_prepared_component_lock", "operate_component_lock"),
            ),
            (
                atomic,
                (
                    "atomic_publication_scope",
                    "_scoped_atomic_writer",
                    "publish_atomic_file_if_scoped",
                ),
            ),
            (filesystem, ("_identity",)),
        )
        for name in names
    )
    error_type = ProjectLayoutPlanError

    def publish_prepared_pair(
        root,
        journal,
        record,
        prepared,
        *,
        guard,
        state,
        move,
        complete,
        fail,
        namespace_owner,
    ):
        def bindings():
            if (
                namespace.get("publish_prepared_pair") is not publish_prepared_pair
                or any(
                    namespace.get(name) is not original for name, original in aliases
                )
                or any(
                    vars(module).get(name) is not original
                    for module, name, original in delegates
                )
            ):
                raise error_type(
                    "producer_publication_conflict",
                    "original finite pair publisher changed",
                )

        bindings()
        planner, target, flavors, flavor_roots = _ADMIT(prepared)
        identity = canonical_identity(record).uri
        live = True

        def current():
            bindings()
            if not live:
                fail("normal producer publication scope is closed")
            if canonical_identity(record).uri != identity:
                fail("original finite pair publication record changed")
            guard()
            bindings()
            _ADMIT(prepared)
            if canonical_identity(record).uri != identity:
                fail("original finite pair record changed during closing guard")

        class Writer:
            __slots__ = ()

            def publish(self, path, content, *, require_current, preserve_mode):
                current()
                if (
                    _SCOPED() is not writer
                    or type(content) is not bytes
                    or preserve_mode is not False
                ):
                    fail("original normal producer publication scope changed")
                coordinate = path.relative_to(root).as_posix()
                row = record["entries"].get(coordinate)
                if row is None or require_current is None:
                    fail("normal producer wrote outside its original finite pair")
                actual = state(root, journal, coordinate, row)
                digest = filesystem._identity(content)

                def transfer(source, destination, *, after):
                    current()
                    move(
                        root,
                        journal,
                        record,
                        source,
                        destination,
                        row,
                        after=after,
                        namespace=namespace_owner,
                    )
                    current()

                # The existing ordinary command may roll its own write back.
                # Restore owned original inodes, never synthesize old-byte files.
                if digest == row["from"] and actual == "published":
                    require_current()
                    transfer(
                        root / coordinate, journal / "after" / row["slot"], after=True
                    )
                    transfer(
                        journal / "before" / row["slot"], root / coordinate, after=False
                    )
                    return
                if digest != row["to"] or actual != "original":
                    fail("normal replacement differs from original prepared bytes")
                require_current()
                transfer(
                    root / coordinate, journal / "before" / row["slot"], after=False
                )
                transfer(journal / "after" / row["slot"], root / coordinate, after=True)

        writer = Writer()
        try:
            current()
            with _SCOPE(writer):
                report, status = _OPERATE(
                    prepared,
                    target=target,
                    flavors=flavors,
                    flavor_roots=flavor_roots,
                    planner=planner,
                    check=False,
                    difference=False,
                )
                current()
            if status != 0:
                fail("normal producer update did not finish successfully")
            final, status = _OPERATE(
                prepared,
                target=target,
                flavors=flavors,
                flavor_roots=flavor_roots,
                planner=planner,
                check=True,
                difference=False,
            )
            current()
            if status != 0 or final.get("current") is not True:
                fail("normal producer pair is not current after renewal")
            complete()
            current()
            return {
                "current": True,
                "writes": True,
                "journal": str(journal),
                "command": report,
                "finalized": False,
                "full_containment": False,
                "qualification": False,
            }
        finally:
            live = False

    return publish_prepared_pair


publish_prepared_pair = _bind_publisher()
