"""Bounded raw Python artifact retention under the original build observer.

These records supply bytes for later portable reopening. They grant no provider,
importer, installation or execution authority, and do not change export shapes.
"""

from __future__ import annotations

import io
import json
from pathlib import Path

from literate_ai.adapters.dependencies.python_installed import _snapshot
from literate_ai.adapters.dependencies.types import DependencyObservationError
from literate_ai.adapters.retained_project_inputs import _directory_access, _stream
from literate_ai.contracts.identity import ContentIdentity, canonical_identity

from .standard_python import StandardPythonDependencyObserver


def _fail(message):
    raise DependencyObservationError("dependencies.python-artifact-invalid", message)


def capture_standard_python_artifact_records(
    artifact_root: Path,
    *,
    expected_tree: ContentIdentity,
    observer: StandardPythonDependencyObserver,
    recorder,
) -> tuple[ContentIdentity, ...]:
    """Retain exact whole-artifact bytes before their actual build owner expires.

    The expected full tree comes from the lifecycle's build/custody records, not a
    new sidecar supplied by the artifact. The original observer independently
    rechecks its selected interpreter, lock, build binding and runtime projection.
    Existing recorder limits apply across all components and remain atomic there.
    """
    from literate_ai.adapters.qualification_capture import QualificationEvidenceRecorder

    if (
        type(observer) is not StandardPythonDependencyObserver
        or type(recorder) is not QualificationEvidenceRecorder
        or not isinstance(expected_tree, ContentIdentity)
        or artifact_root != observer.artifact_root
    ):
        _fail("Original Python artifact observer and bounded recorder required")
    existing = dict(recorder.entries)
    if expected_tree not in existing:
        _fail("Expected Python artifact tree must already belong to build custody")
    document = json.loads(existing[expected_tree])
    observer()
    files = _snapshot(artifact_root)

    def require_tree(actual):
        tree = {
            "schema": "literate-ai/local-source-tree@1",
            "files": [
                {"path": item.path, "sha256": item.sha256}
                for item in sorted(actual, key=lambda item: Path(item.path).parts)
            ],
        }
        if tree != document or canonical_identity(tree) != expected_tree:
            _fail("Python artifact differs from its original complete tree")

    require_tree(files)
    missing = {}
    for item in files:
        identity = ContentIdentity.parse_uri("sha256:" + item.sha256)
        if identity in existing:
            if len(existing[identity]) != item.size:
                _fail("Existing Python artifact payload has another size")
        elif identity in missing:
            if missing[identity].size != item.size:
                _fail("Python artifact payload identity has conflicting sizes")
        else:
            missing[identity] = item
    if len(existing) + len(missing) > recorder.max_records:
        _fail("Python artifact exceeds remaining qualification record allowance")
    if sum(item.size for item in missing.values()) > (
        recorder.max_bytes - recorder.retained_bytes
    ):
        _fail("Python artifact exceeds remaining qualification byte allowance")
    captured = []
    with _directory_access(artifact_root) as access:
        for identity, item in missing.items():
            output = io.BytesIO()
            size, _mode, digest = _stream(
                artifact_root, item.path, item.size, output, access=access
            )
            if size != item.size or digest != item.sha256:
                _fail("Python artifact payload changed during capture")
            captured.append((identity, output.getvalue()))
        observer()
        require_tree(_snapshot(artifact_root))
        if access is not None:
            access.require_current()
    # No native callbacks follow closure. A partial failed recorder insertion
    # cannot become qualification: the existing recorder refuses atomically and
    # the original lifecycle must still finish its unchanged admission guards.
    for identity, content in captured:
        if recorder.remember_bytes(content) != identity:
            _fail("Python artifact bytes differ from their original tree")
    return tuple(
        sorted(
            {
                expected_tree,
                *(ContentIdentity.parse_uri("sha256:" + f.sha256) for f in files),
            },
            key=lambda item: item.uri,
        )
    )
