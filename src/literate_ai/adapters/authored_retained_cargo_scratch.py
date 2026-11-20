"""Authored receiving scratch preserves the actual retained-consumer namespace.

Only absent roots can be provisioned. This grants no provider trust, package
publication, consumer execution, source retirement or admission permission.
"""

from contextlib import contextmanager
from dataclasses import dataclass

from literate_ai.adapters.authored_retained_cargo_wrapper import (
    AuthoredRetainedCargoWrapperContext,
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

    def __init__(self, *, key, core):
        if (
            key is not _CREATION_KEY
            or type(core) is not _CurrentCargoConsumerScratch
            or type(core.context) is not AuthoredRetainedCargoWrapperContext
        ):
            raise TypeError("retained.cargo.authored-live-scratch-required")
        object.__setattr__(self, "_core", core)


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
