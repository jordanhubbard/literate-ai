"""Explicit original native tool ancestry, never lookup/probe/admission.

The caller independently supplies already admitted LOCAL native file/directory/
link facts before Python review/execution. No decoder or locality inference from
an archive/path spelling exists. Construction is inert; rechecking reads ONLY the
exact admitted parent-first namespace. Missing/changed ancestry refuses before
following a new alias target. Existing native byte/directory owners do the reads.
"""

import os
import stat
from dataclasses import dataclass
from pathlib import Path

from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.retained_native_file_custody import (
    NativeFileClosure,
    NativeFileDigest,
)
from literate_ai.adapters.retained_package_tree import _signature
from literate_ai.contracts.identity import ContentIdentity, canonical_identity

_NATIVE_FILE_GUARD = NativeFileClosure.__dict__["require_unchanged"]


@dataclass(frozen=True, slots=True)
class OriginalPythonGateToolSelection:
    """Caller-held comparison facts, NOT a live execution or locality grant.

    `nodes` is the COMPLETE independently admitted local ancestry of alias and
    canonical image, after applying EXACT `links`. Directories use directory_node
    witnesses; files/links use the original native seven-field stat signature.
    The original current native selection owner remains the caller's trust input.
    """

    role: str
    alias: Path
    canonical: Path
    files: NativeFileClosure
    nodes: tuple
    links: tuple

    def __post_init__(self):
        _projection(self)


def _require(condition, reason):
    if not condition:
        raise ValueError("retained.python.original-tools." + reason)


def _path(value):
    _require(
        type(value) is type(Path())
        and len(str(value)) <= 4096
        and len(value.parts) <= 128
        and not any(c in str(value) for c in ("\0", "\n", "\r"))
        and value.is_absolute()
        and ".." not in value.parts
        and os.path.normpath(str(value)) == str(value),
        "explicit_native_path_required",
    )
    return value


def _projection(selection):
    _require(
        type(selection) is OriginalPythonGateToolSelection
        and type(selection.role) is str
        and selection.role in {"git", "make", "shell"}
        and type(selection.files) is NativeFileClosure
        and type(selection.nodes) is tuple
        and 1 <= len(selection.nodes) <= 128
        and type(selection.links) is tuple
        and len(selection.links) <= 16,
        "original_selection_required",
    )
    alias, canonical = _path(selection.alias), _path(selection.canonical)
    _require(
        alias.anchor == canonical.anchor
        and alias.name == selection.role.replace("shell", "sh"),
        "native_alias_changed",
    )
    nodes, links = {}, {}
    for path, witness in selection.nodes:
        _path(path)
        _require(
            path not in nodes
            and type(witness) is tuple
            and len(witness) in {3, 7}
            and all(type(value) is int for value in witness),
            "native_ancestry_invalid",
        )
        kind = stat.S_IFMT(witness[2])
        _require(
            kind in {stat.S_IFDIR, stat.S_IFREG, stat.S_IFLNK}
            and len(witness) == (3 if kind == stat.S_IFDIR else 7),
            "native_ancestry_invalid",
        )
        nodes[path] = witness
    for path, target in selection.links:
        _path(path)
        _require(
            path in nodes
            and stat.S_ISLNK(nodes[path][2])
            and path not in links
            and type(target) is str
            and target
            and len(target) <= 4096
            and not any(value in target for value in ("\0", "\n", "\r")),
            "native_link_invalid",
        )
        links[path] = target
    _require(
        type(selection.files.entries) is tuple
        and len(selection.files.entries) == 1
        and type(selection.files.entries[0]) is NativeFileDigest,
        "exact_native_file_required",
    )
    image = selection.files.entries[0]
    _path(image.path)
    _require(
        type(image.digest) is str
        and len(image.digest) == 64
        and all(value in "0123456789abcdef" for value in image.digest)
        and type(image.labels) is tuple
        and len(image.labels) <= 128
        and all(type(value) is str and len(value) <= 1024 for value in image.labels),
        "exact_native_file_required",
    )
    _require(
        image.path == canonical
        and type(image.size) is int
        and 0 < image.size <= 64 * 1024**2,
        "exact_native_file_required",
    )
    pending, current = list(alias.parts[1:]), Path(alias.anchor)
    visits, used, hops = [current], set(), 0
    _require(
        current in nodes and stat.S_ISDIR(nodes[current][2]), "native_ancestry_missing"
    )
    while pending:
        current = current / pending.pop(0)
        # Membership is checked BEFORE any syscall in require_original_tool.
        _require(current in nodes, "native_ancestry_missing")
        visits.append(current)
        witness = nodes[current]
        if stat.S_ISLNK(witness[2]):
            _require(
                current in links and hops < 16 and current not in used,
                "native_link_closure_invalid",
            )
            used.add(current)
            hops += 1
            target = Path(links[current])
            absolute = target if target.is_absolute() else current.parent / target
            rewritten = Path(os.path.normpath(str(absolute.joinpath(*pending))))
            _require(
                rewritten.is_absolute() and rewritten.anchor == alias.anchor,
                "native_link_closure_invalid",
            )
            current, pending = Path(rewritten.anchor), list(rewritten.parts[1:])
        else:
            _require(
                stat.S_ISDIR(witness[2]) if pending else stat.S_ISREG(witness[2]),
                "native_ancestry_kind_changed",
            )
    _require(
        current == canonical and used == set(links) and set(visits) == set(nodes),
        "exact_native_ancestry_required",
    )
    tool_identity = canonical_identity(
        {
            "schema": "literate-ai/retained-python-native-gate-tool@1",
            "role": selection.role,
            "sha256": image.digest,
            "size": image.size,
        }
    )
    return tuple(dict.fromkeys(visits)), nodes, links, tool_identity


def original_python_gate_tool_selection_identity(selection):
    """Commit only the independently supplied original comparison facts."""
    _projection(selection)
    image = selection.files.entries[0]
    return canonical_identity(
        {
            "schema": "literate-ai/retained-python-original-tool-selection@1",
            "role": selection.role,
            "alias": str(selection.alias),
            "canonical": str(selection.canonical),
            "file": {
                "path": str(image.path),
                "digest": image.digest,
                "size": image.size,
                "labels": image.labels,
            },
            "nodes": [(str(path), witness) for path, witness in selection.nodes],
            "links": [(str(path), text) for path, text in selection.links],
        }
    )


def require_original_python_gate_tool(selection, expected_identity):
    """Recheck only exact admitted namespace and original bounded native image.

    No Path.resolve, shutil.which, directory search, native version probe or new
    alias target is consulted. The caller must already own LOCAL selection; these
    data rows alone cannot establish that independent authority.
    """
    _require(
        type(expected_identity) is ContentIdentity, "expected_tool_identity_required"
    )
    visits, nodes, links, identity = _projection(selection)
    _require(identity == expected_identity, "native_tool_identity_changed")
    original_identity = original_python_gate_tool_selection_identity(selection)
    original = (
        selection.alias,
        selection.canonical,
        selection.files,
        selection.nodes,
        selection.links,
    )
    file_guard = _NATIVE_FILE_GUARD
    files = selection.files
    entries = files.entries

    def namespace():
        _require(
            NativeFileClosure.__dict__.get("require_unchanged") is file_guard,
            "native_file_guard_changed",
        )
        _require(
            all(
                current is held
                for current, held in zip(
                    (
                        selection.alias,
                        selection.canonical,
                        selection.files,
                        selection.nodes,
                        selection.links,
                    ),
                    original,
                    strict=True,
                )
            ),
            "original_selection_changed",
        )
        for path in visits:
            witness = nodes[path]
            if stat.S_ISDIR(witness[2]):
                _require(directory_node(path) == witness, "native_ancestry_changed")
            else:
                _require(_signature(path.lstat()) == witness, "native_ancestry_changed")
                if path in links:
                    _require(os.readlink(path) == links[path], "native_alias_changed")
        _require(
            selection.files is files
            and files.entries is entries
            and original_python_gate_tool_selection_identity(selection)
            == original_identity,
            "original_selection_changed",
        )
        _require(
            NativeFileClosure.__dict__.get("require_unchanged") is file_guard,
            "native_file_guard_changed",
        )

    namespace()
    file_guard(files)
    namespace()
    _require(
        _projection(selection)[-1] == expected_identity
        and original_python_gate_tool_selection_identity(selection)
        == original_identity,
        "original_selection_changed",
    )
