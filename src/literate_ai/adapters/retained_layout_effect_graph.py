"""Pure source projections over a complete role partition; no effect permission.

Carriers describe exclusive native entries. Shared directories stay fixed and
only contribute a logical directory at the destination. Multi-carrier execution
must park all carriers before creating targets or publishing any of them; empty
source containers are retained privately, never deleted as an incidental clean.
"""

from __future__ import annotations

import unicodedata
from dataclasses import dataclass, fields, replace
from pathlib import PurePosixPath

from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_sdk_trees import NativeSdkTree, _ResolutionBudget
from literate_ai.contracts.paths import canonical_relative_posix_path


def _fail(message):
    raise ValueError("layout.effect-graph: " + message)


def _beneath(name, parent):
    return parent == "." or name == parent or name.startswith(parent + "/")


def _parents(name):
    return (p.as_posix() for p in PurePosixPath(name).parents)


@dataclass(frozen=True, slots=True)
class _SourceEffectGraph:
    source: str
    destination: str
    carriers: tuple[tuple[str, str], ...]
    retain_directories: tuple[str, ...]
    create_directories: tuple[str, ...]
    fixed_directories: tuple[str, ...]
    protected_directories: tuple[str, ...]
    projection: tuple[tuple[str, str], ...]

    @property
    def document(self):
        return {
            "schema": "literate-ai/layout-source-effect-graph@1",
            "source": self.source,
            "destination": self.destination,
            "carriers": self.carriers,
            "retain_directories": self.retain_directories,
            "create_directories": self.create_directories,
            "fixed_directories": self.fixed_directories,
            "protected_directories": self.protected_directories,
            "projection": self.projection,
        }

    @property
    def identity(self):
        return canonical_identity(self.document)

    def require_single_rename(self):
        if (
            self.source == "."
            or self.destination == "."
            or self.carriers != ((self.source, self.destination),)
            or self.retain_directories
            or self.create_directories
        ):
            _fail("this executor requires the exact single-rename profile")
        return self.carriers[0]


def _graph_fields(graph):
    if type(graph) is not _SourceEffectGraph:
        _fail("actual typed source effect graph required")
    return tuple(getattr(graph, item.name) for item in fields(_SourceEffectGraph))


def _graph_allowance(roles, directories, destination):
    count = len(roles) + len(directories)
    path_bytes = sum(len(n.encode()) for n, _ in (*roles, *directories))
    path_bytes += count * len(destination.encode())
    return 8 * count, 4096 + 512 * count + 128 * path_bytes


def _source_effect_graph(
    tree, roles, directories, source, destination, *, protected_directories=()
):
    """Derive a finite native carrier forest and validate the final namespace.

    This reads only already observed names and topology. Actual callers fund its
    retained records before construction, bind it to the live partition, and
    seal its immutable field references before effects. A decoded graph never
    grants ownership.
    """
    for coordinate in (source, destination):
        if coordinate != ".":
            canonical_relative_posix_path(coordinate, label="layout coordinate")
    if source == destination:
        _fail("source and destination are identical")
    roles, directories = dict(roles), dict(directories)
    leaves = {n for n, _, _ in tree.files} | {a.path for a in tree.aliases}
    if set(roles) != leaves or set(directories) != {".", *tree.directories}:
        _fail("complete observed leaf and directory roles required")
    if source not in directories:
        _fail("source is not an observed directory")
    boundaries = set(protected_directories)
    boundaries.update(
        role.removeprefix("independent:")
        for values in directories.values()
        for role in values
        if role.startswith("independent:")
    )
    for name in boundaries:
        canonical_relative_posix_path(name, label="protected layout directory")
        if name not in directories:
            _fail("protected directory lacks its actual namespace observation")
    source_leaves = {n for n, role in roles.items() if role == "source"}
    source_dirs = {n for n, values in directories.items() if "source" in values}
    if any(not _beneath(n, source) for n in source_leaves):
        _fail("source ownership escapes the selected source")
    # The selected implementation has a logical root even when a mixed project
    # contains only fixed framework/control entries. Its destination directory
    # still has to exist; the physical repository root remains fixed.
    moving_dirs = {source} | {n for n in source_dirs if _beneath(n, source)}
    fixed_dirs = {
        n
        for n, values in directories.items()
        if n == "." or not _beneath(n, source) or values != ("source",)
    }
    fixed_leaves = leaves - source_leaves

    def after(name):
        tail = (
            ""
            if name == source
            else name
            if source == "."
            else name[len(source) :].lstrip("/")
        )
        if destination == ".":
            return tail or "."
        return destination + ("/" + tail if tail else "")

    projection = {n: after(n) for n in source_leaves | moving_dirs}
    if any(
        _beneath(target, boundary)
        for target in projection.values()
        for boundary in boundaries
    ):
        _fail("projected source enters Git or independent project administration")
    final_roles = {n: roles[n] for n in fixed_leaves}
    for name in sorted(source_leaves):
        target = after(name)
        if target in final_roles or target in fixed_dirs:
            _fail("source leaf collides with a fixed namespace entry")
        final_roles[target] = "source"
    final_dirs = fixed_dirs | {after(n) for n in moving_dirs}
    for name in tuple(final_roles) + tuple(final_dirs - {"."}):
        final_dirs.update(_parents(name))
    if final_dirs & final_roles.keys():
        _fail("projected file blocks a required directory")
    portable = {}
    for name in sorted(final_roles.keys() | final_dirs - {"."}):
        key = unicodedata.normalize("NFC", name.casefold())
        if key in portable and portable[key] != name:
            _fail("projected namespace has a portable name collision")
        portable[key] = name

    # Resolve unchanged symbolic text in both logical namespaces. Equal roles
    # alone are insufficient: a link must keep its actual original referent.
    final_dir_roles = {n: set() for n in final_dirs}
    final_dir_roles[after(source)].add("source")
    for name, role in final_roles.items():
        for parent in _parents(name):
            final_dir_roles[parent].add(role)
    for name, values in directories.items():
        for role in values:
            target = after(name) if role == "source" and name in moving_dirs else name
            if target not in final_dirs:
                continue
            final_dir_roles[target].add(role)
            for parent in _parents(target):
                final_dir_roles[parent].add(role)
    original_aliases = {a.path: a for a in tree.aliases}
    aliases = {
        projection.get(a.path, a.path): replace(
            a,
            path=projection.get(a.path, a.path),
            target=projection.get(a.target, a.target)
            if a.kind == "hardlink"
            else a.target,
        )
        for a in tree.aliases
    }
    files = {n for n, _, _ in tree.files}
    final_files = {projection.get(n, n) for n in files}
    resolution = _ResolutionBudget(
        remaining=max(1048576, tree.budget.maximum_entries * 256)
    )
    for name in original_aliases:
        old_target = NativeSdkTree._resolve(
            name, set(tree.directories), files, original_aliases, resolution
        )
        expected = roles[name]
        target_name = projection.get(name, name)

        def observe(candidate, expected=expected):
            if candidate in aliases and final_roles[candidate] != expected:
                _fail("projected alias traverses another ownership role")

        target = NativeSdkTree._resolve(
            target_name,
            final_dirs - {"."},
            final_files,
            aliases,
            resolution,
            observe=observe,
        )
        target_roles = (
            final_dir_roles[target] if target in final_dirs else {final_roles[target]}
        )
        if target != projection.get(old_target, old_target) or target_roles != {
            expected
        }:
            _fail("projected alias changes referent or crosses ownership roles")

    # A carrier cannot absorb an existing fixed/shared destination directory.
    # Splitting that directory keeps its original inode at the old coordinate;
    # an exclusive source directory that merges is retained empty in private.
    candidates = {
        n
        for n in moving_dirs - {"."}
        if directories[n] == ("source",)
        and after(n) != "."
        and not any(_beneath(fixed, after(n)) for fixed in fixed_dirs)
    }
    carriers = []
    covered = set()
    for name in sorted(candidates, key=lambda n: (n.count("/"), n)):
        if not any(p in covered for p in _parents(name)):
            carriers.append((name, after(name)))
            covered.add(name)
    for name in sorted(source_leaves):
        if not any(p in covered for p in _parents(name)):
            carriers.append((name, after(name)))
    retained = {
        n
        for n in moving_dirs - {"."}
        if directories[n] == ("source",)
        and n not in covered
        and not any(p in covered for p in _parents(n))
    }
    carried_dirs = {
        after(n)
        for n in moving_dirs - {"."}
        if n in covered or any(p in covered for p in _parents(n))
    }
    created = final_dirs - fixed_dirs - carried_dirs
    return _SourceEffectGraph(
        source,
        destination,
        tuple(sorted(carriers)),
        tuple(sorted(retained, key=lambda n: (-n.count("/"), n))),
        tuple(sorted(created, key=lambda n: (n.count("/"), n))),
        tuple(sorted(fixed_dirs)),
        tuple(sorted(boundaries)),
        tuple(sorted(projection.items())),
    )
