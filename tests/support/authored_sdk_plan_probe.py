"""Run public SDK planning with fixture review, distribution and model ports."""

import json
import sys
from contextlib import ExitStack
from unittest.mock import patch

from literate_ai.adapters.authored_qualification_planning import (
    FilesystemAuthoredQualificationPlanner,
)
from literate_ai.adapters.models import InheritedSessionSelection
from literate_ai.adapters.project_validation import FilesystemProjectValidationAdapter
from literate_ai.adapters.standard_lifecycle_binding import (
    InstalledFrameworkDistribution,
    InstalledFrameworkDistributionMember,
    ResolvedStandardProjectLifecycleDriver,
)
from literate_ai.cli import (
    authored_qualification,
    authored_sdk,
    dispatch,
    retained_cargo_authored,
)
from literate_ai.contracts import (
    StandardProjectLifecycleDriver,
    load_current_standard_lifecycle_policy,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.storage import FileSystemCAS


def fixture_binding():
    distribution = InstalledFrameworkDistribution(
        "literate-ai",
        "1.4.0",
        (
            InstalledFrameworkDistributionMember(
                "literate_ai/__init__.py", 1, "sha256:" + "a" * 64
            ),
        ),
    )
    policy = load_current_standard_lifecycle_policy()
    driver = StandardProjectLifecycleDriver(distribution.identity, policy.identity)
    return ResolvedStandardProjectLifecycleDriver(
        driver, distribution, policy, lambda: distribution, lambda: policy
    )


def main():
    arguments = json.load(sys.stdin)
    binding = fixture_binding()

    def review(_root, *, synchronize_source_intelligence):
        if synchronize_source_intelligence:
            raise AssertionError("plan attempted to synchronize source intelligence")
        return canonical_identity({"fixture": "project-review"})

    planner = FilesystemAuthoredQualificationPlanner(
        reviewer=review,
        binding_resolver=lambda _driver: binding,
        coding_selector=lambda: InheritedSessionSelection(
            canonical_identity({"fixture": "provider"})
        ),
    )
    with ExitStack() as guards:
        for module in ("cli.authored_sdk", "adapters.native_sdk_completion_packet"):
            guards.enter_context(
                patch(
                    "literate_ai."
                    + module
                    + ".resolve_standard_project_lifecycle_driver",
                    return_value=binding,
                )
            )
        # Sealed receiving read ports call the actual project validator, which
        # dispatches here; it receives the same fixture review as planning.
        guards.enter_context(
            patch.object(
                FilesystemProjectValidationAdapter,
                "authority_identity",
                lambda _self, root, *, synchronize_source_intelligence=True: review(
                    root,
                    synchronize_source_intelligence=synchronize_source_intelligence,
                ),
            )
        )
        for entrypoint in (authored_qualification, retained_cargo_authored):
            # Sealed read-port consumers no longer import the planner.
            if not hasattr(entrypoint, "FilesystemAuthoredQualificationPlanner"):
                continue
            guards.enter_context(
                patch.object(
                    entrypoint,
                    "FilesystemAuthoredQualificationPlanner",
                    return_value=planner,
                )
            )
        for owner, names in (
            (authored_sdk, ("NativeSdkProjectAcquisition",)),
            (FileSystemCAS, ("put_manifest", "put_bytes", "put_file")),
            (
                dispatch,
                (
                    "maybe_host_self_update",
                    "ensure_user_mcp_catalog",
                    "journal_mutagenic_event",
                ),
            ),
        ):
            for name in names:
                guards.enter_context(
                    patch.object(owner, name, side_effect=AssertionError(name))
                )
        guards.enter_context(
            patch("socket.socket.connect", side_effect=AssertionError("network"))
        )
        guards.enter_context(
            patch(
                "literate_ai.adapters.source.repository_git.run_bounded_process",
                side_effect=AssertionError("read-only SDK plan ran source Git"),
            )
        )
        if len(sys.argv) == 1:
            return dispatch.main(arguments)
        expected = sys.argv[1]
        observed = []
        reopen = retained_cargo_authored.reopen_authored_sdk_inputs
        archive = retained_cargo_authored._archive

        def read_sdk(*args, **kwargs):
            try:
                owner = reopen(*args, **kwargs)
            except ValueError as error:
                if "source build authorization is revoked" in str(error):
                    observed.append("revoked")
                raise
            if owner is None:
                raise AssertionError("retained check skipped the prepared SDK")
            observed.append("reopened")
            return owner

        def read_archive(*args, **kwargs):
            try:
                return archive(*args, **kwargs)
            except ValueError as error:
                if getattr(error, "code", "") == "inputs.closure_identity_changed":
                    observed.append("archive digest mismatch")
                raise

        guards.enter_context(
            patch.object(
                retained_cargo_authored, "reopen_authored_sdk_inputs", new=read_sdk
            )
        )
        guards.enter_context(
            patch.object(retained_cargo_authored, "_archive", new=read_archive)
        )
        status = dispatch.main(arguments)
        required = {
            # Sealed receiving read ports resolve the actual installed, pinned
            # framework before transport; this fixture pins a synthetic
            # distribution, so the refusal follows the reopened SDK. Archive
            # digest refusal is covered in-process by the critical input tests.
            "changed-archive": ["reopened"],
            "revoked-sdk": ["revoked"],
        }[expected]
        if status != 2 or observed != required:
            raise AssertionError((status, observed, required))
        return status


if __name__ == "__main__":
    raise SystemExit(main())
