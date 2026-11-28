"""Authored-provider receiving still requires actual retained-consumer authority.

This consumer context grants no provider trust, scratch, execution or admission.
Its original-source conversion and parity concern the consumer, never fabricated
source history for an authored provider.
"""

from contextlib import contextmanager
from dataclasses import dataclass

from literate_ai.adapters.authored_retained_cargo_review import (
    AuthoredRetainedCargoReviewedFiles,
)
from literate_ai.adapters.retained_cargo_wrapper_core import (
    _CargoConsumerWrapperView,
    _CurrentCargoConsumerWrapper,
    _open_consumer_wrapper_context,
    _original_wrapper_view,
    _ReadOnlyCargoConsumerWrapper,
)

_CREATION_KEY = object()


@dataclass(init=False, eq=False, frozen=True)
class AuthoredRetainedCargoWrapperContext(_CargoConsumerWrapperView):
    """Distinct authored receiving view over real current consumer source custody."""

    _IDENTITY_SCHEMA = "literate-ai/authored-retained-cargo-wrapper-context@1"

    def __init__(self, *, _key, core):
        if (
            _key is not _CREATION_KEY
            or type(core) is not _CurrentCargoConsumerWrapper
            or type(core.reviewed) is not AuthoredRetainedCargoReviewedFiles
        ):
            raise TypeError("retained.cargo.authored-live-wrapper-context-required")
        object.__setattr__(self, "_core", core)


@dataclass(init=False, eq=False, frozen=True)
class AuthoredRetainedCargoWrapperObservation(_CargoConsumerWrapperView):
    """Read-only current consumer facts; no scratch or execution authority."""

    _IDENTITY_SCHEMA = "literate-ai/authored-retained-cargo-wrapper-observation@1"

    def __init__(self, *, _key, core):
        if (
            _key is not _CREATION_KEY
            or type(core) is not _ReadOnlyCargoConsumerWrapper
            or type(core.reviewed) is not AuthoredRetainedCargoReviewedFiles
        ):
            raise TypeError("retained.cargo.authored-live-wrapper-observation-required")
        object.__setattr__(self, "_core", core)


@contextmanager
def authored_retained_cargo_wrapper_context(
    reviewed: AuthoredRetainedCargoReviewedFiles,
    *,
    read_only: bool = False,
):
    """Keep actual consumer authority independently of authored provider origin."""
    if type(reviewed) is not AuthoredRetainedCargoReviewedFiles:
        raise TypeError("retained.cargo.authored-reviewed-files-required")
    with _open_consumer_wrapper_context(reviewed, read_only=read_only) as core:
        factory = (
            AuthoredRetainedCargoWrapperObservation
            if read_only
            else AuthoredRetainedCargoWrapperContext
        )
        context = factory(_key=_CREATION_KEY, core=core)
        with _original_wrapper_view(context):
            context.require_unchanged()
            yield context
            context.require_unchanged()
