"""Source-v2 scratch entry; only fresh roots under its exact current wrapper."""

from contextlib import contextmanager
from dataclasses import dataclass

from literate_ai.adapters.retained_cargo_scratch_core import (
    _CargoConsumerScratchView,
    _CurrentCargoConsumerScratch,
    _reserve_consumer_scratch,
)
from literate_ai.adapters.retained_cargo_wrapper_v2 import RetainedCargoWrapperContextV2

_CREATION_KEY = object()


@dataclass(init=False, frozen=True, eq=False)
class RetainedCargoScratchScopeV2(_CargoConsumerScratchView):
    """Distinct source-v2 view; no authored/decoded scope can substitute."""

    def __init__(self, *, key, core):
        if (
            key is not _CREATION_KEY
            or type(core) is not _CurrentCargoConsumerScratch
            or type(core.context) is not RetainedCargoWrapperContextV2
        ):
            raise TypeError("retained.cargo.v2-live-scratch-required")
        object.__setattr__(self, "_core", core)


@contextmanager
def reserve_retained_cargo_scratch_v2(
    context: RetainedCargoWrapperContextV2,
    *,
    maximum_metadata_bytes: int = 1024 * 1024 * 1024,
):
    """Keep the exact original source-v2 type gate and absent-only transaction."""
    if type(context) is not RetainedCargoWrapperContextV2:
        raise TypeError("retained.cargo.v2-live-wrapper-required")
    with _reserve_consumer_scratch(
        context, maximum_metadata_bytes=maximum_metadata_bytes
    ) as core:
        yield RetainedCargoScratchScopeV2(key=_CREATION_KEY, core=core)
