"""Source-derived v2 nominal entrypoint for current retained-consumer custody."""

from contextlib import contextmanager
from dataclasses import dataclass

from literate_ai.adapters.retained_cargo_review_v2 import RetainedCargoReviewedFilesV2
from literate_ai.adapters.retained_cargo_wrapper_core import (
    _CargoConsumerWrapperView,
    _CurrentCargoConsumerWrapper,
    _open_consumer_wrapper_context,
    _original_wrapper_view,
)

_CREATION_KEY = object()


@dataclass(init=False, eq=False, frozen=True)
class RetainedCargoWrapperContextV2(_CargoConsumerWrapperView):
    """Original source-v2 view; decoded or authored values cannot mint it."""

    def __init__(self, *, _key, core):
        if (
            _key is not _CREATION_KEY
            or type(core) is not _CurrentCargoConsumerWrapper
            or type(core.reviewed) is not RetainedCargoReviewedFilesV2
        ):
            raise TypeError("retained.cargo.v2-live-wrapper-context-required")
        object.__setattr__(self, "_core", core)


@contextmanager
def retained_cargo_wrapper_context_v2(reviewed: RetainedCargoReviewedFilesV2):
    """Keep the exact source-derived entry gate and original consumer authority."""
    if type(reviewed) is not RetainedCargoReviewedFilesV2:
        raise TypeError("retained.cargo.v2-reviewed-files-required")
    with _open_consumer_wrapper_context(reviewed) as core:
        context = RetainedCargoWrapperContextV2(_key=_CREATION_KEY, core=core)
        with _original_wrapper_view(context):
            context.require_unchanged()
            yield context
            context.require_unchanged()
