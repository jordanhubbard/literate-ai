"""Authored receiving scratch preserves the actual retained-consumer namespace.

Only absent roots can be provisioned. This grants no provider trust, package
publication, consumer execution, source retirement or admission permission.
"""

from contextlib import contextmanager
from dataclasses import dataclass

from literate_ai.adapters.authored_retained_cargo_reopen_owner import (
    _CurrentAuthoredReopenedNamespace,
)
from literate_ai.adapters.authored_retained_cargo_wrapper import (
    AuthoredRetainedCargoWrapperContext,
)
from literate_ai.adapters.retained_cargo_native_output_tree import (
    _NativeOutputTreeBudget,
)
from literate_ai.adapters.retained_cargo_scratch_core import (
    _CargoConsumerScratchView,
    _CurrentCargoConsumerScratch,
    _reserve_consumer_scratch,
)

_CREATION_KEY = object()


@dataclass(init=False, frozen=True, eq=False)
class AuthoredRetainedCargoScratchScope(_CargoConsumerScratchView):
    """Distinct authored receiving view over original consumer scratch custody."""

    def __init__(self, *, key, core, output_policy=None):
        if (
            key is not _CREATION_KEY
            or type(core)
            not in (_CurrentCargoConsumerScratch, _CurrentAuthoredReopenedNamespace)
            or (
                type(core) is _CurrentAuthoredReopenedNamespace
                and type(output_policy) is not _NativeOutputTreeBudget
            )
            or (
                type(core) is _CurrentCargoConsumerScratch and output_policy is not None
            )
            or type(core.context) is not AuthoredRetainedCargoWrapperContext
        ):
            raise TypeError("retained.cargo.authored-live-scratch-required")
        object.__setattr__(self, "_core", core)
        object.__setattr__(self, "_output_policy", output_policy)
        object.__setattr__(self, "_original_output_policy", output_policy)

    def require_unchanged(self):
        self._core.require_unchanged()
        if self._output_policy is not self._original_output_policy:
            raise ValueError("retained.reopen.original-output-policy-changed")
        if self._output_policy is not None:
            self._output_policy._require_current()


def _authored_reopened_scratch(namespace, *, output_policy):
    if type(namespace) is not _CurrentAuthoredReopenedNamespace:
        raise TypeError("retained.cargo.authored-live-reopened-namespace-required")
    result = AuthoredRetainedCargoScratchScope(
        key=_CREATION_KEY, core=namespace, output_policy=output_policy
    )
    result.require_unchanged()
    return result


@contextmanager
def reserve_authored_retained_cargo_scratch(
    context: AuthoredRetainedCargoWrapperContext,
    *,
    maximum_metadata_bytes: int = 1024 * 1024 * 1024,
):
    """Reserve fresh consumer roots under the exact authored receiving wrapper."""
    if type(context) is not AuthoredRetainedCargoWrapperContext:
        raise TypeError("retained.cargo.authored-live-wrapper-required")
    with _reserve_consumer_scratch(
        context, maximum_metadata_bytes=maximum_metadata_bytes
    ) as core:
        yield AuthoredRetainedCargoScratchScope(key=_CREATION_KEY, core=core)
