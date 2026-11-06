"""Process-local original runtime issuer; historical sidecar schema stays canonical.

This module does not encode a second meaning of promotion-evidence@1. The
complete writer/verifier remains retained_promotion_evidence, including its
per-action context and dependency facts. No serialized value restores this scope.
"""

import os
import weakref
from contextlib import contextmanager

from literate_ai.adapters.retained_project_execution import (
    RetainedProjectExecutionWorkspace,
)
from literate_ai.adapters.retained_project_receipt import AdmittedRetainedProject

_ISSUER = object()
_ACTIVE = weakref.WeakKeyDictionary()


class _LiveCapture:
    __slots__ = ("__weakref__",)

    def __init__(self, seal):
        if seal is not _ISSUER:
            raise TypeError("retained.promotion.original-live-capture-required")

    def __copy__(self):
        raise TypeError("retained.promotion.capture-cannot-be-copied")

    def __deepcopy__(self, _memo):
        raise TypeError("retained.promotion.capture-cannot-be-copied")

    def __reduce_ex__(self, _protocol):
        raise TypeError("retained.promotion.capture-cannot-be-serialized")


def _bindings(admission, workspace):
    return (
        admission.receipt,
        admission.run,
        admission.store,
        admission.source,
        admission.current_plan,
        workspace.plan,
        workspace.manifest,
        workspace.source,
        workspace.current_plan,
        workspace.inputs,
        workspace.outputs,
        workspace._native_sdks,
        workspace._dependencies,
        workspace._tools,
        workspace._secondary_views,
        workspace._promotion_contexts,
        *tuple(workspace._tools[name] for name in sorted(workspace._tools)),
    )


@contextmanager
def _issued_capture(admission, workspace):
    if type(admission) is not AdmittedRetainedProject or type(workspace) is not (
        RetainedProjectExecutionWorkspace
    ):
        raise TypeError("retained.promotion.original-live-admission-required")
    if (
        workspace.plan is not admission.run.source_bom.plan
        or workspace.source != admission.source
        or workspace.current_plan is not admission.current_plan
        or workspace._promotion_contexts is None
    ):
        raise ValueError("retained.promotion.live-workspace-context-differs")
    scope = _LiveCapture(_ISSUER)
    _ACTIVE[scope] = (
        os.getpid(),
        admission,
        workspace,
        _bindings(admission, workspace),
    )
    try:
        yield scope
    finally:
        _ACTIVE.pop(scope, None)


def _original(scope):
    value = _ACTIVE.get(scope) if type(scope) is _LiveCapture else None
    if value is None or value[0] != os.getpid():
        raise ValueError("retained.promotion.original-live-capture-required")
    _, admission, workspace, bound = value
    current = _bindings(admission, workspace)
    if len(current) != len(bound) or any(
        a is not b for a, b in zip(current, bound, strict=True)
    ):
        raise ValueError("retained.promotion.live-capture-retargeted")
    return admission, workspace
