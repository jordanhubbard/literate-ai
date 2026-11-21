"""Private complete consumer input capture under closed original scratch owners.

Returned tree values are passive observations; only exact live scratch owners
supply exclusions. Execution must freshly capture its own original scope.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from literate_ai.adapters.authored_retained_cargo_scratch import (
    AuthoredRetainedCargoScratchScope,
)
from literate_ai.adapters.retained_cargo_input_owners_v2 import (
    RetainedCargoInputRootV2,
    capture_retained_cargo_input_owners_v2,
)
from literate_ai.adapters.retained_cargo_scratch_v2 import RetainedCargoScratchScopeV2
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_cargo_policy import RetainedLibraryGatePolicyV2


class _CargoConsumerInputScopeMethods:
    __slots__ = ()
    _IDENTITY_SCHEMA = "literate-ai/retained-cargo-input-scope@2"

    @property
    def identity(self):
        value = self._identity_document()
        if self._scratch is not None:
            value["scratch_context"] = self._scratch.context.identity.uri
        return canonical_identity(value)

    def _captured_identity(self):
        value = self._identity_document()
        if self._scratch is not None:
            value["scratch_context"] = self._scratch.context._captured_identity().uri
        return canonical_identity(value)

    def _identity_document(self):
        return {
            "schema": self._IDENTITY_SCHEMA,
            "policy": self.policy.identity.uri,
            "environment": self.environment_identity.uri,
            "owners": self.owners.identity.uri,
            "roots": [
                {"scope": scope, "path": str(root)} for scope, root in self.roots
            ],
        }

    def require_unchanged(self, *, environment: Mapping[str, str]):
        if self._scratch is not None:
            self._scratch.require_unchanged()
        if _environment_identity(environment) != self.environment_identity:
            raise ValueError("retained.cargo.v2-input-environment-changed")
        self.owners.require_unchanged()
        if _environment_identity(environment) != self.environment_identity:
            raise ValueError("retained.cargo.v2-input-environment-changed")
        if self._scratch is not None:
            self._scratch.require_unchanged()


def _environment_identity(environment):
    if not isinstance(environment, Mapping) or any(
        not isinstance(name, str)
        or not isinstance(value, str)
        or not name
        or "=" in name
        or "\x00" in name + value
        for name, value in environment.items()
    ):
        raise ValueError("retained.cargo.v2-input-environment-invalid")
    return canonical_identity(dict(environment))


def _prepare_consumer_input_scope(workspace, policy, environment):
    if type(policy) is not RetainedLibraryGatePolicyV2:
        raise ValueError("retained.cargo.v2-input-gate-policy-required")
    environment = dict(environment) if isinstance(environment, Mapping) else environment
    environment_identity = _environment_identity(environment)
    if not isinstance(workspace, Path) or not workspace.is_absolute():
        raise ValueError("retained.cargo.v2-input-workspace-invalid")
    return environment_identity, environment


def _capture_consumer_input_scope(
    workspace, *, policy, environment, maximum_metadata_bytes, scratch
):
    exclusions = ()
    if scratch is not None:
        if type(scratch) not in (
            RetainedCargoScratchScopeV2,
            AuthoredRetainedCargoScratchScope,
        ):
            raise TypeError("retained.cargo.v2-live-scratch-required")
        scratch.require_unchanged()
        if (
            scratch.context.workspace != workspace
            or scratch.context.reviewed.policy != policy
        ):
            raise ValueError("retained.cargo.v2-input-scratch-authority-mismatch")
        exclusions = scratch.workspace_exclusions
    roots = {"workspace": workspace}
    for scope, variable in (
        ("cargo-home", "CARGO_HOME"),
        *(("external:" + name, name) for name in policy.external_input_variables),
    ):
        value = environment.get(variable)
        if not value or not Path(value).is_absolute() or ".." in Path(value).parts:
            raise ValueError("retained.cargo.v2-input-explicit-root-required")
        roots[scope] = Path(value)
        if scratch is not None and any(
            roots[scope].is_relative_to(workspace / excluded)
            or (workspace / excluded).is_relative_to(roots[scope])
            for excluded in exclusions
        ):
            raise ValueError("retained.cargo.v2-input-scratch-overlap")
    owners = capture_retained_cargo_input_owners_v2(
        tuple(
            RetainedCargoInputRootV2(
                owner.scope,
                roots[owner.scope],
                exclusions if owner.scope == "workspace" else (),
            )
            for owner in policy.input_custody.owners
        ),
        policy=policy.input_custody,
        maximum_metadata_bytes=maximum_metadata_bytes,
    )
    return owners, tuple((scope, tree.root) for scope, tree in owners.trees)
