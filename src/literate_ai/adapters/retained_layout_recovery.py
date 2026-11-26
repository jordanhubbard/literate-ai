"""Bounded read-only observations for a future fresh layout recovery owner.

Historical records locate evidence and describe attempted operations. They do
not restore a lock, live journal, process, execution grant or successful commit.
The recovery service must re-observe all original/moved source bytes and metadata,
construct a new full plan and obtain its acknowledgement before any mutation.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import re
import stat
from pathlib import Path

from literate_ai.adapters.retained_layout import (
    PENDING_LAYOUT_FILE,
    _fail,
    _nonfinite,
    _unique_object,
    read_layout_document,
)
from literate_ai.adapters.retained_layout_journal import (
    _MAX_JOURNAL_BYTES,
    _directory_node,
    _file_stamp,
    _require_private,
)
from literate_ai.adapters.retained_project_inputs import _directory_access, _stream
from literate_ai.contracts.identity import (
    ContentIdentity,
    canonical_identity,
    canonical_json_bytes,
)
from literate_ai.contracts.paths import canonical_relative_posix_path


def _observe_recovery_journal(root, *, state_root, maximum_metadata_bytes=1024**3):
    """Return joined historical diagnostics; never return an applicable action.

    The state root comes from actual operator paths, not a public path selector.
    Every pathname obtained from the pending document remains untrusted and is
    admitted only within the expected original target namespace and private state.
    """
    root, state = Path(root), Path(state_root)
    if (
        not root.is_absolute()
        or not state.is_absolute()
        or root.resolve(strict=True) != root
        or state.resolve(strict=True) != state
        or root.is_relative_to(state)
        or state.is_relative_to(root)
    ):
        _fail("state_overlaps_project", "recovery requires disjoint actual roots")
    if type(maximum_metadata_bytes) is not int or maximum_metadata_bytes < 65536:
        raise ValueError("retained.layout.finite-recovery-memory-bound-required")
    reserved = 65536

    def reserve(size):
        nonlocal reserved
        # Covers raw streams, decoded records and diagnostic projections before
        # any of those representations are allocated concurrently.
        reserved += 256 * size
        if reserved > maximum_metadata_bytes:
            _fail("metadata_limit", "recovery observation exceeds metadata memory")

    pending, pending_bytes = read_layout_document(
        root, PENDING_LAYOUT_FILE, _reserve_metadata=reserve, _maximum_bytes=65536
    )
    if (
        set(pending)
        != {"schema", "plan_identity", "journal", "header_sha256", "target_identity"}
        or pending["schema"] != "literate-ai/retained-layout-pending@1"
    ):
        _fail("recovery_invalid", "complete pending relocation metadata required")
    plan_identity = ContentIdentity.parse_uri(pending["plan_identity"])
    claimed_target = ContentIdentity.parse_uri(pending["target_identity"])
    if (
        type(pending["header_sha256"]) is not str
        or re.fullmatch(r"[0-9a-f]{64}", pending["header_sha256"]) is None
        or type(pending["journal"]) is not str
    ):
        _fail("recovery_invalid", "canonical journal coordinates and hash required")
    state_node = _require_private(state)
    with (
        _directory_access(root) as project_access,
        _directory_access(state) as state_access,
    ):
        if project_access is None or state_access is None:
            _fail(
                "native_owner_unavailable", "recovery needs original directory handles"
            )
        project_node = _directory_node(os.fstat(project_access.directory(())[0]))
        target = canonical_identity(
            {
                "schema": "literate-ai/retained-layout-state-target@1",
                "root": str(root),
                "project_node": [str(value) for value in project_node],
            }
        )
        journal = Path(pending["journal"])
        if (
            target != claimed_target
            or not journal.is_absolute()
            or journal.parent.parent != state
            or journal.name != "journal.jsonl"
            or re.fullmatch(
                "retained-layout-" + target.digest + "-[0-9a-f]{32}",
                journal.parent.name,
            )
            is None
        ):
            _fail(
                "recovery_target_changed", "pending journal belongs to another target"
            )
        stage_node = _require_private(journal.parent)
        relative = journal.relative_to(state).as_posix()
        node = state_access.metadata(journal)
        if (
            not stat.S_ISREG(node.st_mode)
            or node.st_nlink != 1
            or node.st_uid != os.geteuid()
            or stat.S_IMODE(node.st_mode) != 0o600
            or not 0 < node.st_size <= _MAX_JOURNAL_BYTES
        ):
            _fail("journal_unsafe", "recovery journal must be one bounded private file")
        reserve(node.st_size)
        output = io.BytesIO()
        _stream(state, relative, node.st_size, output, access=state_access)
        if _file_stamp(state_access.metadata(journal)) != _file_stamp(node):
            _fail("journal_changed", "recovery journal changed during its read")
        raw = output.getvalue()
        # Incomplete trailing writes are evidence of interruption, never JSON
        # that can be silently discarded to manufacture a successful history.
        if not raw.endswith(b"\n"):
            _fail("journal_incomplete", "journal has an incomplete trailing record")
        records = []
        try:
            for line in raw.splitlines(keepends=True):
                value = json.loads(
                    line, object_pairs_hook=_unique_object, parse_constant=_nonfinite
                )
                if (
                    type(value) is not dict
                    or canonical_json_bytes(value) + b"\n" != line
                ):
                    raise ValueError("journal record is not an object")
                records.append(value)
        except (ValueError, UnicodeError, RecursionError) as exc:
            _fail(
                "journal_invalid", "journal must contain complete bounded JSON records"
            )
            raise AssertionError from exc
        header = records[0]
        if (
            set(header) != {"schema", "plan_identity", "intent"}
            or header["schema"] != "literate-ai/retained-layout-journal@1"
            or header["plan_identity"] != plan_identity.uri
            or hashlib.sha256(raw.split(b"\n", 1)[0] + b"\n").hexdigest()
            != pending["header_sha256"]
        ):
            _fail(
                "journal_invalid",
                "actual journal header differs from pending authority",
            )
        observed_names = set()
        for value in records[1:]:
            if type(value.get("event")) is not str:
                _fail("journal_invalid", "journal event tag required")
            for field in ("source", "destination"):
                if field in value:
                    observed_names.add(
                        canonical_relative_posix_path(
                            value[field], label="historical layout coordinate"
                        ).as_posix()
                    )
        observed = []
        for name in sorted(observed_names):
            try:
                actual = project_access.metadata(root / name)
            except FileNotFoundError:
                stamp = None
            else:
                stamp = [str(value) for value in _file_stamp(actual)]
            observed.append({"path": name, "actual_node": stamp})
        # Close all original file/root/parent and pending-document joins after
        # parsing and pathname observation, rather than trusting a saved hash.
        repeated, repeated_bytes = read_layout_document(
            root, PENDING_LAYOUT_FILE, _maximum_bytes=65536
        )
        if (
            repeated != pending
            or repeated_bytes != pending_bytes
            or _file_stamp(state_access.metadata(journal)) != _file_stamp(node)
            or _require_private(state) != state_node
            or _require_private(journal.parent) != stage_node
            or _directory_node(os.fstat(project_access.directory(())[0]))
            != project_node
        ):
            _fail("recovery_changed", "recovery evidence changed during observation")
        project_access.require_current()
        state_access.require_current()
    return {
        "schema": "literate-ai/retained-layout-recovery-observation@1",
        "root": str(root),
        "target_identity": target.uri,
        "historical_plan_identity": plan_identity.uri,
        "pending_bytes_identity": "sha256:" + hashlib.sha256(pending_bytes).hexdigest(),
        "journal_bytes_identity": "sha256:" + hashlib.sha256(raw).hexdigest(),
        "journal_node": [str(value) for value in _file_stamp(node)],
        "historical_records": records,
        "actual_names": observed,
        "requires_complete_source_and_metadata_replay": True,
        "applicable_actions": [],
        "live_ownership_restored": False,
    }
