"""Shared real v2 receiving setup with cleanup owned by the calling test."""

import tempfile
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters import retained_cargo_materialization_v2 as receiver
from literate_ai.adapters.retained_cargo_files_v2 import read_retained_cargo_files_v2
from literate_ai.adapters.retained_cargo_import_v2 import RetainedCargoCurrentInputsV2
from literate_ai.adapters.retained_cargo_scratch_v2 import (
    reserve_retained_cargo_scratch_v2,
)
from literate_ai.adapters.retained_cargo_wrapper_v2 import (
    retained_cargo_wrapper_context_v2,
)
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture


def initialize_retained_cargo_receiving_v2_fixture(case):
    case.base = Path(
        case.enterContext(tempfile.TemporaryDirectory(prefix="rv2-"))
    ).resolve()
    case.reviewed, case.provider = case.enterContext(
        scratch_review_fixture(case.base, with_provider=True)
    )
    common = case.reviewed.plan.common
    workspace = case.reviewed.project.root / common.workspace_root
    # Exact fixture after-manifests are authored before the live source owner.
    (workspace / "Cargo.toml").write_bytes(b"workspace")
    (workspace / "Cargo.lock").write_bytes(b"lock")
    case.current = RetainedCargoCurrentInputsV2(
        case.reviewed,
        replace(
            case.provider.inputs,
            importer_project_id=case.reviewed.project.definition.project_id,
            reviewed_binding_identity=case.reviewed.binding.identity,
            configured_store_id=case.reviewed.binding.common.source_store_id,
        ),
    )
    case.context = case.enterContext(retained_cargo_wrapper_context_v2(case.reviewed))
    case.scratch_manager = reserve_retained_cargo_scratch_v2(case.context)
    case.scratch = case.enterContext(case.scratch_manager)
    case.files = read_retained_cargo_files_v2(
        case.reviewed, manifest_state="after", package_state="absent"
    )


def receive_retained_cargo_fixture(case, **changes):
    args = {**case.provider.calls, "read_current": lambda: case.current}
    args.update(changes)
    return receiver.materialize_retained_cargo_archive_v2(
        case.files, scratch=case.scratch, **args
    )
