"""Pure exact original-resource transitions, never update/cutover authority."""

from __future__ import annotations

import ast
import hashlib
import posixpath
import re

from .project_scaffold_references import validate_reference_coordinates

_MAXIMUM_BYTES = 16 * 1024**2
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def reviewed_bootstrap_transition(
    before,
    *,
    original_before_bytes,
    original_after_bytes,
    before_sha256,
    after_sha256,
    coordinate_map,
    original_helper_bytes,
    helper_sha256,
):
    """Return independently reviewed upstream bytes after exact original checks.

    All original resources/digests must come from the original update owner and
    its retained baseline/origin, not hashes synthesized from current user files.
    This inert operation reads no filesystem and cannot establish that provenance.
    The effect owner retains currentness/namespace/journal and publication authority.
    """
    for content in (
        before,
        original_before_bytes,
        original_after_bytes,
        original_helper_bytes,
    ):
        if type(content) is not bytes or not content or len(content) > _MAXIMUM_BYTES:
            raise ValueError(
                "bootstrap transition requires bounded original resource bytes"
            )
    for content, digest in (
        (original_before_bytes, before_sha256),
        (original_after_bytes, after_sha256),
        (original_helper_bytes, helper_sha256),
    ):
        if (
            type(digest) is not str
            or _DIGEST.fullmatch(digest) is None
            or hashlib.sha256(content).hexdigest() != digest
        ):
            raise ValueError("bootstrap original resource digest differs")
    if before != original_before_bytes:
        raise ValueError("historical bootstrap differs from original reviewed resource")
    logical = "scripts/bootstrap_litai.py"
    coordinates = validate_reference_coordinates(coordinate_map, document=logical)
    helper = "scripts/_bootstrap_processes.py"
    if helper not in coordinates or posixpath.dirname(
        coordinates[helper]
    ) != posixpath.dirname(coordinates[logical]):
        raise ValueError(
            "bootstrap and original process helper require one actual sibling closure"
        )
    tree = ast.parse(original_after_bytes.decode("utf-8"))
    stores = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Name)
        and isinstance(node.ctx, ast.Store)
        and node.id == "_OWNER_DIGEST"
    ]
    values = [
        node.value.value
        for node in tree.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "_OWNER_DIGEST"
        and isinstance(node.value, ast.Constant)
        and type(node.value.value) is str
    ]
    if len(stores) != 1 or values != [helper_sha256]:
        raise ValueError(
            "reviewed bootstrap does not pin the exact original process helper"
        )
    return original_after_bytes
