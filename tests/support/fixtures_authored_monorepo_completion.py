"""Actual installed retained monorepo plus explicit authored-provider fixture.

The installed source runs the maintained real per-component Python harnesses.
No generated native consumer, model/provider or admission is qualified here.
"""

import os
import shutil
from contextlib import ExitStack, contextmanager

from literate_ai.adapters.authored_retained_cargo_execution_inputs import (
    read_authored_retained_cargo_execution_inputs,
)
from literate_ai.adapters.authored_retained_cargo_files import (
    read_authored_retained_cargo_files,
)
from literate_ai.adapters.authored_retained_cargo_inputs import (
    open_authored_retained_cargo_inputs,
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
from literate_ai.adapters.monorepo_components import install_monorepo_components
from tests.critical import test_authored_retained_cargo_inputs as joins
from tests.e2e.test_monorepo_components import MonorepoComponentTests
from tests.support.fixtures_test_project_cli import refresh_authority_review


class _AuthoredMonorepoHarnessFixture(MonorepoComponentTests):
    """Use maintained harness mechanics without mutating another suite's template."""


def initialize_monorepo_completion_template():
    _AuthoredMonorepoHarnessFixture.setUpClass()


def cleanup_monorepo_completion_template():
    _AuthoredMonorepoHarnessFixture.doClassCleanups()


@contextmanager
def authored_monorepo_completion_fixture(case, *, installed=True):
    helper = joins.AuthoredRetainedCargoInputsTests("runTest")
    with helper.fixture() as (root, _binding, arguments, provider_state, _provider):
        monorepo = None
        if installed:
            harness = _AuthoredMonorepoHarnessFixture("runTest")
            harness.setUp()
            try:
                harness.retained_bundle()
                source = root / "monorepo-source"
                shutil.copytree(harness.source, source)
                monorepo = install_monorepo_components(
                    source,
                    harness.bundle,
                    root,
                    harness.receipts,
                    expected_bundle_identity=harness.manifest["bundle_identity"],
                )
                refresh_authority_review(root)
            finally:
                harness.doCleanups()
        with ExitStack() as receiving:
            current = receiving.enter_context(
                open_authored_retained_cargo_inputs(root, **arguments)
            )
            workspace = root / current.reviewed.plan.common.workspace_root
            (workspace / "Cargo.toml").write_bytes(b"workspace")
            (workspace / "Cargo.lock").write_bytes(b"lock")
            wrapper = receiving.enter_context(
                authored_retained_cargo_wrapper_context(current.reviewed)
            )
            scratch = receiving.enter_context(
                reserve_authored_retained_cargo_scratch(wrapper)
            )
            files = read_authored_retained_cargo_files(
                current.reviewed, manifest_state="after", package_state="absent"
            )
            materialized = materialize_authored_retained_cargo_packages(
                files, scratch=scratch, current=current
            )
            home = root.parent / "monorepo-cargo-home"
            home.mkdir()
            environment = {"CARGO_HOME": str(home), "PATH": os.environ["PATH"]}
            inputs = read_authored_retained_cargo_execution_inputs(
                materialized, environment=environment
            )
            yield inputs, environment, receiving.close, monorepo, provider_state
