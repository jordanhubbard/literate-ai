"""Explicit fixture-local SYSTEM tool facts, selected BEFORE conversion/review.

No search or Path.resolve. Every lstat/readlink path is in this fixture's exact
admitted local system namespace, checked before access. This is test provisioning,
not a production locality classifier or provider admission. Unsupported host
layouts refuse instead of following a new link target or external volume.
"""

import os
import stat
from pathlib import Path

from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.retained_native_file_custody import (
    NativeFileClosure,
    NativeFileDigest,
    native_file_digest,
)
from literate_ai.adapters.retained_package_tree import _signature
from literate_ai.adapters.retained_python_gate_tools import (
    OriginalPythonGateToolSelection,
)


def selected_system_gate_tool(role):
    alias = Path("/bin/sh" if role == "shell" else "/usr/bin/" + role)
    # Exact known native system roots/files for the actual POSIX source fixture.
    # A changed link leaving this set is rejected BEFORE querying its target.
    admitted = {
        Path(value)
        for value in (
            "/",
            "/usr",
            "/usr/bin",
            "/bin",
            "/usr/bin/make",
            "/bin/make",
            "/usr/bin/git",
            "/bin/git",
            "/bin/sh",
            "/usr/bin/sh",
            "/bin/bash",
            "/usr/bin/bash",
            "/bin/dash",
            "/usr/bin/dash",
        )
    }
    nodes, links = {}, {}
    pending, current, hops = list(alias.parts[1:]), Path(alias.anchor), 0
    while True:
        assert current in admitted
        node = current.lstat()
        if stat.S_ISDIR(node.st_mode):
            nodes[current] = directory_node(current)
        elif stat.S_ISLNK(node.st_mode):
            assert hops < 16 and current not in links
            text = os.readlink(current)
            nodes[current], links[current] = _signature(node), text
            target = Path(text)
            absolute = target if target.is_absolute() else current.parent / target
            target = Path(os.path.normpath(str(absolute.joinpath(*pending))))
            # Pure path check precedes every read of a rewritten target/prefix.
            assert target in admitted and all(
                parent in admitted for parent in target.parents
            )
            current, pending = Path(target.anchor), list(target.parts[1:])
            hops += 1
            continue
        else:
            assert stat.S_ISREG(node.st_mode) and not pending
            nodes[current] = _signature(node)
            canonical = current
            break
        assert pending
        current = current / pending.pop(0)
    digest, size = native_file_digest(canonical, 64 * 1024**2)
    assert _signature(canonical.lstat()) == nodes[canonical]
    return OriginalPythonGateToolSelection(
        role,
        alias,
        canonical,
        NativeFileClosure(
            (NativeFileDigest(canonical, ("original-" + role,), digest, size),)
        ),
        tuple(nodes.items()),
        tuple(links.items()),
    )
