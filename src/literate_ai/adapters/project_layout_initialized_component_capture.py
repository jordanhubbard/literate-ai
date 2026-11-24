"""Original initialized Component source capture, before intentional effects only.

No import synthesis, renewal, writer admission, source retirement or platform
qualification. A held/unopened child blocks the original broad Component reader.
"""

from __future__ import annotations

import os
import re
from types import MappingProxyType

from literate_ai.adapters import project_layout_component_transition as core
from literate_ai.adapters import project_layout_filesystem as leaf
from literate_ai.adapters import project_layout_framework_resources as resource_module
from literate_ai.adapters import project_layout_framework_source_proofs as proof_module
from literate_ai.adapters import project_layout_initialized_items as item_module
from literate_ai.adapters import project_layout_planning as planning
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts.paths import canonical_relative_posix_path


def _build_capture():
    error_type = planning.ProjectLayoutPlanError
    admit_proof = proof_module.require_original_initialized_framework_file_proof
    admit_resources = resource_module.require_original_framework_resources
    resources_current = resource_module.require_current_framework_resources
    inventory = item_module.original_initialized_item_inventory
    namespace = core._require_original_source_namespace
    classes_current, data_current = core._classes_current, proof_module._data_current
    observe = core.observe_initialized_component_layout_transition
    reader_type = core.FilesystemLockedGenerationAuthorityReader
    store_type, audit_type = core.ComponentLockStore, core.ComponentResolutionAuditStore
    load, lock_snapshot, lock_read = (
        core._LOAD_CATALOG,
        core._LOCK_SNAPSHOT,
        core._LOCK_READ,
    )
    file_read, stamp = leaf.read_migration_file, planning._stamp
    serialize = UpdateBases.serialized
    maximum = planning._MAX_FILE_BYTES
    entry_limit, total_limit = planning._MAX_ENTRIES, planning._MAX_TOTAL_BYTES
    coordinate = canonical_relative_posix_path
    aliases = tuple(
        (name, globals()[name])
        for name in (
            "os",
            "re",
            "MappingProxyType",
            "UpdateBases",
            "canonical_relative_posix_path",
            "core",
            "resource_module",
            "proof_module",
            "item_module",
            "leaf",
            "planning",
        )
    )
    original_scandir = os.scandir
    modules = tuple(
        (module, tuple((name, vars(module)[name]) for name in names))
        for module, names in (
            (
                core,
                (
                    "_classes_current",
                    "_require_original_source_namespace",
                    "_LOAD_CATALOG",
                    "_LOCK_SNAPSHOT",
                    "_LOCK_READ",
                    "_AUDIT_READ",
                    "_AUDIT_SNAPSHOT",
                    "_CATALOG_CURRENT",
                    "_CATALOG_CONTENT",
                    "_CATALOG_ROOT",
                    "_capture",
                    "_initialized_resources_current",
                    "_admit_initialized_source",
                    "observe_initialized_component_layout_transition",
                    "_observe_component_layout_transition",
                    "FilesystemLockedGenerationAuthorityReader",
                    "ComponentLockStore",
                    "ComponentResolutionAuditStore",
                ),
            ),
            (
                proof_module,
                ("require_original_initialized_framework_file_proof", "_data_current"),
            ),
            (
                resource_module,
                (
                    "require_original_framework_resources",
                    "require_current_framework_resources",
                    "original_framework_initialization",
                ),
            ),
            (
                item_module,
                (
                    "original_initialized_item_inventory",
                    "original_framework_initialization",
                    "prove_initialized_framework_file",
                ),
            ),
            (leaf, ("read_migration_file", "_read", "_windows")),
            (
                planning,
                ("_MAX_FILE_BYTES", "_MAX_ENTRIES", "_MAX_TOTAL_BYTES", "_stamp"),
            ),
        )
    )
    audit_name = re.compile(
        r"(?:\.)?component\.resolution-audit\.[A-Za-z0-9][A-Za-z0-9._-]*\.json(?:\.write\.lock)?\Z"
    )

    def fail(message):
        raise error_type("initialized_component_capture_unavailable", message)

    def seals():
        if (
            any(globals().get(name) is not value for name, value in aliases)
            or os.scandir is not original_scandir
            or globals().get("capture_initialized_framework_component_transitions")
            is not capture
        ):
            fail("original initialized Component capture dispatch changed")
        if any(
            vars(module).get(name) is not original
            for module, members in modules
            for name, original in members
        ):
            fail("original initialized Component reader delegate changed")
        classes_current()
        data_current()

    def checked(callback, *args, **kwargs):
        seals()
        value = callback(*args, **kwargs)
        seals()
        return value

    def capture(
        snapshot,
        context,
        *,
        resources,
        source_proofs,
        update_bases,
        contents,
        observations,
        source_held,
        protected_paths=frozenset(),
        imported_paths=frozenset(),
    ):
        seals()
        admit_resources(resources)
        if (
            resources.snapshot is not snapshot
            or resources.context is not context
            or type(update_bases) is not UpdateBases
            or update_bases.root != snapshot.root
            or type(source_proofs) is not tuple
            or len(source_proofs) > len(resources.files)
            or type(source_held) is not tuple
            or type(protected_paths) is not frozenset
            or type(imported_paths) is not frozenset
            or type(contents) not in (dict, MappingProxyType)
            or type(observations) not in (dict, MappingProxyType)
            or len(contents) > entry_limit
            or len(observations) > entry_limit
            or len(source_held) > entry_limit
        ):
            fail("same original resource/project/base/source census required")
        proof_by_logical = {}
        for proof in source_proofs:
            admit_proof(proof)
            if (
                proof.snapshot is not snapshot
                or proof.context is not context
                or proof.resources is not resources
                or proof.logical in proof_by_logical
            ):
                fail("original proof/resource pairing or unique membership differs")
            proof_by_logical[proof.logical] = proof
        # Only actual issued old-coordinate Component manifest proofs select work.
        candidates = tuple(
            proof
            for proof in source_proofs
            if proof.logical.endswith("/component.md")
            and proof.role == "immutable-catalog"
            and proof.source_path == proof.logical
        )
        if not candidates:
            return ()  # Already-contained proofs never reopen a Component reader.
        frozen_contents = MappingProxyType(dict(contents))
        if any(
            type(path) is not str or type(payload) is not bytes
            for path, payload in frozen_contents.items()
        ):
            fail("exact original public source bytes required")
        if sum(map(len, frozen_contents.values())) > total_limit or any(
            len(value) > maximum for value in frozen_contents.values()
        ):
            fail("source bytes exceed original capture bounds")
        frozen_nodes = {}
        for path, row in observations.items():
            if type(path) is not str or type(row) not in (dict, MappingProxyType):
                fail("exact original source node records required")
            frozen_nodes[path] = MappingProxyType(dict(row))
        frozen_nodes = MappingProxyType(frozen_nodes)
        held = []
        for row in source_held:
            if (
                type(row) not in (dict, MappingProxyType)
                or type(row.get("path")) is not str
            ):
                fail("original held/unopened scope census required")
            coordinate(row["path"], label="held original source coordinate")
            held.append(row["path"])
        for path in (*protected_paths, *imported_paths):
            coordinate(path, label="protected original source coordinate")
        locator = tuple(
            (owner, name, object.__getattribute__(owner, name))
            for owner, names in (
                (snapshot, ("root", "definition", "content", "directory_binding")),
                (context, ("root", "framework_root", "directory_binding")),
                (update_bases, ("root", "scopes", "sources", "blobs")),
            )
            for name in names
        )
        base_bytes = serialize(update_bases)
        base_path = "litai/.literate/update-bases.json"
        if frozen_contents.get(base_path) != base_bytes:
            fail("original current update-base preimage is unavailable")

        def overlap(left, right):
            return (
                left == right
                or left.startswith(right + "/")
                or right.startswith(left + "/")
            )

        roots = tuple(
            proof.source_path.removesuffix("/component.md") for proof in candidates
        )
        for root in roots:
            coordinate(root, label="original initialized Component root")
            if root.startswith("litai/") or not any(
                root.startswith(prefix + "/")
                for prefix in snapshot.definition.component_roots
            ):
                fail("old source must belong to original declared Component catalog")
            if any(
                overlap(root, path)
                for path in (*held, *protected_paths, *imported_paths)
            ):
                # No target metadata or file callback occurs for these scopes.
                fail(
                    "held/unopened or application/import scope blocks Component capture"
                )

        for proof in source_proofs:
            if any(proof.source_path.startswith(root + "/") for root in roots):
                if frozen_contents.get(proof.source_path) != proof.source_bytes or dict(
                    frozen_nodes.get(proof.source_path, {})
                ) != dict(proof.native_observation):
                    fail("original selected proof bytes/native data differ")

        # Close the known read shape BEFORE any source target metadata access.
        # Unknown children are detected by names only; no stat/open follows them.
        selected_nodes = {}
        for root in roots:
            rows = {
                path: row
                for path, row in frozen_nodes.items()
                if path == root or path.startswith(root + "/")
            }
            if any(
                row.get("kind") not in {"file", "directory"} for row in rows.values()
            ):
                fail("independent or unopened Component member blocks capture")
            files = {path for path, row in rows.items() if row["kind"] == "file"}
            for path in files:
                relative = path[len(root) + 1 :]
                finite = "/" not in relative and (
                    relative
                    in {
                        "component.lock.json",
                        ".component.operation.write.lock",
                        ".component.lock.write.lock",
                    }
                    or audit_name.fullmatch(relative)
                )
                if not finite and not any(
                    proof.source_path == path for proof in source_proofs
                ):
                    fail("unknown authored source blocks original Component read scope")
            needed = {root}
            for path in files:
                parent = path.rpartition("/")[0]
                while parent.startswith(root + "/"):
                    needed.add(parent)
                    parent = parent.rpartition("/")[0]
            if {
                path for path, row in rows.items() if row["kind"] == "directory"
            } != needed:
                fail("unowned directory blocks original Component read scope")
            selected_nodes.update(rows)
        expected_children = {
            path: {
                child[len(path) + 1 :].split("/", 1)[0]
                for child in selected_nodes
                if child.startswith(path + "/")
            }
            for path, row in selected_nodes.items()
            if row["kind"] == "directory"
        }

        def original_current():
            seals()
            admit_resources(resources)
            for proof in source_proofs:
                admit_proof(proof)
            if (
                any(
                    object.__getattribute__(owner, name) is not value
                    for owner, name, value in locator
                )
                or serialize(update_bases) != base_bytes
            ):
                fail("original source/project/base pointer or preimage changed")
            for root in roots:
                namespace(snapshot, context, root, frozen_nodes)
                for path, row in frozen_nodes.items():
                    if path == root or path.startswith(root + "/"):
                        if (
                            row["kind"] == "directory"
                            and stamp((snapshot.root / path).lstat()) != row["stamp"]
                        ):
                            fail("original Component directory census changed")
                        if row["kind"] == "directory":
                            with os.scandir(snapshot.root / path) as children:
                                names = set()
                                for child in children:
                                    if len(names) >= entry_limit:
                                        fail("Component census exceeds bound")
                                    names.add(child.name)
                            if names != expected_children[path]:
                                fail("original Component gained or lost a source child")
                            if stamp((snapshot.root / path).lstat()) != row["stamp"]:
                                fail("Component census changed while closing")
            # Exact known leaves only, never directory recursion or held children.
            for path in (
                base_path,
                *(
                    proof.source_path
                    for proof in source_proofs
                    if any(proof.source_path.startswith(root + "/") for root in roots)
                ),
            ):
                row = frozen_nodes.get(path)
                if row is None or row["kind"] != "file":
                    fail("original public source leaf witness unavailable")
                native, payload, mode = file_read(
                    snapshot.root / path,
                    maximum_bytes=maximum,
                    fail=lambda reason, message: fail(message),
                    stamp=stamp,
                )
                if (
                    payload != frozen_contents[path]
                    or mode != row["mode"]
                    or tuple(native) != row["stamp"][:3]
                    or stamp((snapshot.root / path).lstat()) != row["stamp"]
                ):
                    fail("original initialized source leaf changed")
            seals()

        original_current()
        checked(resources_current, resources)
        original_current()
        boundaries, item_owner, expected = checked(
            inventory,
            snapshot,
            context,
            resources=resources,
            update_bases=update_bases,
            proofs=proof_by_logical,
            contents=frozen_contents,
            observations=frozen_nodes,
            protected_paths=protected_paths,
            imported_paths=imported_paths,
        )
        original_current()
        output = []
        for proof, root in zip(candidates, roots, strict=True):
            if (
                root not in boundaries
                or boundaries[root][0] != "component"
                or boundaries[root][1] != proof.logical
            ):
                fail("original complete initialized Component item is unavailable")
            known = {
                logical for logical in proof_by_logical if item_owner(logical) == root
            }
            if known != expected.get(root, frozenset()):
                fail("complete original per-item issued source proofs required")
            for logical in known:
                member = proof_by_logical[logical]
                if (
                    member.role != "immutable-catalog"
                    or member.source_path != logical
                    or member.source_bytes != frozen_contents.get(logical)
                    or dict(member.native_observation)
                    != dict(frozen_nodes.get(logical, {}))
                ):
                    fail("original whole-item source proof closure differs")
            actual = {
                path
                for path, row in frozen_nodes.items()
                if path.startswith(root + "/") and row["kind"] == "file"
            }
            # These names authorize only finite store validation reads. Exact
            # target membership is narrowed after actual typed lock reading.
            finite_candidates = {
                path
                for path in actual
                if "/" not in path[len(root) + 1 :]
                and (
                    path[len(root) + 1 :]
                    in {
                        "component.lock.json",
                        ".component.operation.write.lock",
                        ".component.lock.write.lock",
                    }
                    or audit_name.fullmatch(path[len(root) + 1 :])
                )
            }
            if actual - finite_candidates != known:
                fail(
                    "unproved or incomplete authored item blocks broad Component reader"
                )
            original_current()
            reader = checked(reader_type)
            original_current()
            catalog = checked(load, reader, snapshot.root / root)
            original_current()
            store = checked(store_type, snapshot.root / root)
            original_current()
            audit = None
            allowed = {
                store.path.relative_to(snapshot.root).as_posix(),
                store.operation_lock_path.relative_to(snapshot.root).as_posix(),
                store.write_lock_path.relative_to(snapshot.root).as_posix(),
            }
            if checked(lock_snapshot, store).content is not None:
                original_current()
                lock = checked(lock_read, store, authorings=catalog.authorings)
                original_current()
                audit = checked(audit_type, snapshot.root / root, lock.target_name)
                original_current()
                allowed.update(
                    (
                        audit.path.relative_to(snapshot.root).as_posix(),
                        audit.write_lock_path.relative_to(snapshot.root).as_posix(),
                    )
                )
            if not finite_candidates <= allowed:
                fail("producer file inventory lacks original typed target binding")
            selected_dirs = {
                path
                for path, row in frozen_nodes.items()
                if (path == root or path.startswith(root + "/"))
                and row["kind"] == "directory"
            }
            needed_dirs = {root}
            for path in actual:
                parent = path.rpartition("/")[0]
                while parent.startswith(root + "/"):
                    needed_dirs.add(parent)
                    parent = parent.rpartition("/")[0]
            if selected_dirs != needed_dirs:
                fail("unowned empty or independent directory blocks Component capture")
            original_current()
            result = checked(
                observe,
                snapshot,
                context,
                proof,
                source_root=root,
                contents=frozen_contents,
                observations=frozen_nodes,
                original_catalog=catalog,
                original_lock_store=store,
                original_audit_store=audit,
            )
            original_current()
            checked(resources_current, resources)
            original_current()
            output.append(result)
        return tuple(output)

    return capture


capture_initialized_framework_component_transitions = _build_capture()
