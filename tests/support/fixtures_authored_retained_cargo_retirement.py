"""Actual original consumer retirement with explicit fixture provider admission."""

from contextlib import ExitStack, contextmanager

from literate_ai.adapters import authored_retained_cargo_inputs as inputs
from literate_ai.adapters.authored_retained_cargo_files import (
    read_authored_retained_cargo_files,
)
from literate_ai.adapters.authored_retained_cargo_materialization import (
    materialize_authored_retained_cargo_packages,
)
from literate_ai.adapters.authored_retained_cargo_scratch import (
    reserve_authored_retained_cargo_scratch,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    authored_retained_cargo_wrapper_context,
)
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.contracts.retained_cargo_admission import RetainedCargoSourceRetirement
from tests.critical import test_authored_retained_cargo_inputs as joins
from tests.support.fixtures_test_retained_cargo_import import blob


@contextmanager
def authored_retirement_fixture(case, *, retire=True, roots=None, receiving_state=None):
    helper = joins.AuthoredRetainedCargoInputsTests("runTest")
    with helper.fixture() as (root, _binding, args, _state, _provider):
        with ExitStack() as receiving:
            current = receiving.enter_context(
                inputs.open_authored_retained_cargo_inputs(root, **args)
            )
            workspace = root / current.reviewed.plan.common.workspace_root
            original = workspace / "app.py"
            before = original.read_bytes()
            case.assertEqual(before, b"print('retained')\n")
            if retire:
                original.unlink()
            (workspace / "Cargo.toml").write_bytes(b"workspace")
            (workspace / "Cargo.lock").write_bytes(b"lock")
            declaration = RetainedCargoSourceRetirement(
                current.reviewed.project.definition.project_id,
                current.reviewed.binding.identity,
                (original.relative_to(root).as_posix(),)
                if roots is None
                else roots(current.reviewed),
            )
            relative = "review/retirement.json"
            payload = canonical_json_bytes(declaration.to_dict())
            (root / relative).write_bytes(payload)
            context = receiving.enter_context(
                authored_retained_cargo_wrapper_context(current.reviewed)
            )
            scratch = receiving.enter_context(
                reserve_authored_retained_cargo_scratch(context)
            )
            files = read_authored_retained_cargo_files(
                current.reviewed, manifest_state="after", package_state="absent"
            )
            materialized = materialize_authored_retained_cargo_packages(
                files, scratch=scratch, current=current
            )
            if receiving_state is not None:
                receiving_state["close"] = receiving.close
                receiving_state["provider"] = _state
            yield materialized, relative, blob(payload), original, before
