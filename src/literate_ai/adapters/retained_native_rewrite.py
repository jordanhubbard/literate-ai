"""Reconcile native rewrite locations only after genuine declared readmission."""

from __future__ import annotations

import os
import re
from pathlib import Path

from literate_ai.contracts import canonical_identity
from literate_ai.contracts.paths import canonical_relative_posix_path
from literate_ai.projects import load_project

from .component_lock_application import current_component_lock_binding
from .component_locks import ComponentLockStore
from .lifecycle_lock import project_lifecycle_lock
from .repository_refresh import _file, _signature
from .retained_harness_receipts import (
    RetainedHarnessReceiptError,
    _current_wrapper_lock_identity,
    _load_retained_documents,
    _qualified_layout,
)
from .retained_layout_partition import _lineage
from .retained_layout_renewal import observe_retained_layout_renewal

_ADR = "docs/decisions/0002-native-literate-ai-rewrite.md"
_ROADMAP = "docs/roadmap/native-rewrite-program.md"
_QUEUE = "docs/roadmap/active-work.md"
_INPUTS = (
    ".literate/harness-inventory.json",
    ".literate/legacy-harness-baseline.json",
    ".literate/legacy-wrapper-parity.json",
    ".literate/legacy-lift-shift.json",
    "litai.harness.mk",
    "literate.project.json",
    ".literate/conversion-authority.json",
)


def _fail(message):
    raise ValueError("native_rewrite.layout: " + message)


def _reconcile(texts, implementation, lift_identity):
    """Change recognized generated references, retaining custom work verbatim."""
    adr = texts[_ADR]
    matches = tuple(re.finditer(r"The original project now lives at `([^`\n]+)`", adr))
    if len(matches) != 1:
        _fail("native decision location requires explicit reconciliation")
    old = matches[0][1]
    canonical_relative_posix_path(old, label="prior native rewrite source")
    replacements = {
        _ADR: (
            (
                f"The original project now lives at `{old}`",
                f"The original project now lives at `{implementation}`",
            ),
            (f"and `{old}` contains no", f"and `{implementation}` contains no"),
        ),
        _ROADMAP: (
            (
                f"The retained implementation at `{old}` remains source-authority",
                f"The retained implementation at `{implementation}` "
                "remains source-authority",
            ),
        ),
    }
    result = dict(texts)
    for name, pairs in replacements.items():
        for before, after in pairs:
            if result[name].count(before) != 1:
                _fail("generated location reference is ambiguous or customized")
            result[name] = result[name].replace(before, after, 1)
    # The lift record remains historical. Record its actual current identity,
    # rather than presenting a rewritten report as new execution evidence.
    evidence = re.compile(r"(?m)^- Phase 1\.2 evidence: `sha256:[0-9a-f]{64}`$")
    if len(evidence.findall(result[_ADR])) != 1:
        _fail("native decision evidence reference is ambiguous")
    result[_ADR] = evidence.sub(
        f"- Phase 1.2 evidence: `{lift_identity}`", result[_ADR]
    )
    queue = texts[_QUEUE]
    headings = tuple(re.finditer(r"(?m)^### \[[ xX]\] ADOPT-002(?:\s|$)[^\n]*", queue))
    if len(headings) != 1:
        _fail("native rewrite needs one existing ADOPT-002 work item")
    start = headings[0].start()
    end_match = re.search(r"(?m)^### ", queue[headings[0].end() :])
    end = len(queue) if end_match is None else headings[0].end() + end_match.start()
    block = queue[start:end]
    action = "- **Next action:** Produce the evidence-linked boundary inventory for\n  "
    before = action + f"`{old}`."
    after = action + f"`{implementation}`."
    if before in block:
        block = block.replace(before, after, 1)
    elif old != implementation and f"`{old}`" in block:
        _fail("custom native work item location needs explicit reconciliation")
    evidence = re.compile(
        r"(?m)^- \*\*Evidence:\*\* Phase 1\.2 lift-and-shift identity "
        r"`sha256:[0-9a-f]{64}`\.$"
    )
    if len(evidence.findall(block)) != 1:
        _fail("native work item evidence reference is ambiguous")
    block = evidence.sub(
        f"- **Evidence:** Phase 1.2 lift-and-shift identity `{lift_identity}`.", block
    )
    result[_QUEUE] = queue[:start] + block + queue[end:]
    return result


def _prepare_declared_native_rewrite(lift_shift: dict, *, project_root: Path) -> dict:
    """Renew generated location prose without replacing custom program progress."""
    from .conversion_authority import FilesystemConversionAuthorityStore
    from .project_initialization import _atomic_replace
    from .retained_scope_refresh import (
        _close_source_native_inputs,
        _source_native_inputs,
    )
    from .roadmap_dependencies import require_project_roadmap_acyclic

    project = load_project(project_root)
    root = project.root
    with project_lifecycle_lock(root, operation="native-rewrite.layout"):
        observed = observe_retained_layout_renewal(root)
        inputs = tuple(
            _file(root / name, maximum_bytes=16 * 1024**2) for name in _INPUTS
        )
        conversion = FilesystemConversionAuthorityStore(root).load_optional()
        if conversion is None or conversion.project_id != project.definition.project_id:
            _fail("declared retained source lacks current conversion authority")
        documents = _load_retained_documents(project)
        if documents["lift_shift"]["value"] != lift_shift:
            _fail("supplied lift record differs from actual current evidence")
        layout = _qualified_layout(project, documents)
        lock = _current_wrapper_lock_identity(project, documents)
        selected_lock, catalog = current_component_lock_binding(layout.wrapper_root)
        if selected_lock.identity != lock:
            _fail("selected wrapper changed while capturing its input context")
        lock_store = ComponentLockStore(layout.wrapper_root)
        selected_inputs = catalog.locked_input_closure(
            selected_lock,
            lock_path=lock_store.path,
            lock_boundary=lock_store.storage_root,
        )
        pinned_native = tuple(
            (path, _signature(path)) for path in selected_inputs.pinned_paths
        )
        pinned_ancestry = tuple(
            (parent, _lineage(parent))
            for parent in dict.fromkeys(
                path.parent for path in selected_inputs.pinned_paths
            )
        )
        source_native = _source_native_inputs(
            layout.implementation_root,
            [
                {"path": name}
                for name in documents["inventory"]["value"]["source_scope"]["paths"]
            ],
        )
        originals = {
            name: _file(root / name, maximum_bytes=16 * 1024**2)
            for name in (_ADR, _ROADMAP, _QUEUE)
        }
        texts = {
            name: value.content.decode("utf-8") for name, value in originals.items()
        }
        lift_identity = canonical_identity(lift_shift).uri
        proposed = {
            name: text.encode("utf-8")
            for name, text in _reconcile(
                texts, layout.implementation_directory, lift_identity
            ).items()
        }
        require_project_roadmap_acyclic(root, proposed)
        expected = dict(originals)
        written = {}

        def require_current():
            selected_inputs.require_unchanged()
            if _load_retained_documents(project) != documents:
                _fail("qualification evidence changed during reconciliation")
            if _current_wrapper_lock_identity(project, documents) != lock:
                _fail("selected wrapper authority changed during reconciliation")
            observed.require_current()
            for item in (*inputs, *expected.values()):
                if _signature(item.path) != item.signature:
                    _fail("original inputs changed during reconciliation")
            if any(_signature(path) != node for path, node in pinned_native):
                _fail("selected locked inputs changed during final observations")
            if any(_lineage(path) != nodes for path, nodes in pinned_ancestry):
                _fail("selected locked input ancestry changed")
            _close_source_native_inputs(source_native)
            if os.path.lexists(root / "litai/layout.pending"):
                _fail("pending relocation requires explicit recovery")

        try:
            for name, content in proposed.items():
                if content == originals[name].content:
                    continue
                _atomic_replace(root / name, content, require_current=require_current)
                written[name] = content
                published = _file(root / name, maximum_bytes=16 * 1024**2)
                if published.content != content:
                    _fail("native rewrite output changed after publication")
                expected[name] = published
            require_current()
        except BaseException:
            for name, content in reversed(tuple(written.items())):
                if (root / name).read_bytes() == content:
                    _atomic_replace(root / name, originals[name].content)
            raise
        return {
            "schema": "literate-ai/native-rewrite-program@1",
            "state": "planned",
            "retained_authority": layout.implementation_directory,
            "lift_shift_identity": lift_identity,
            "layout_identity": documents["layout"]["identity"],
            "adr": _ADR,
            "roadmap": _ROADMAP,
            "next_action": "boundary-inventory",
            "source_to_specification_started": False,
        }


def prepare_declared_native_rewrite(lift_shift: dict, *, project_root: Path) -> dict:
    """Keep native planning refusals at its existing ValueError boundary."""
    try:
        return _prepare_declared_native_rewrite(lift_shift, project_root=project_root)
    except RetainedHarnessReceiptError as exc:
        raise ValueError("native_rewrite.layout: " + str(exc)) from exc
