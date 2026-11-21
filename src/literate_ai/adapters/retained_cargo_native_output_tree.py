"""Private readonly census of old generated payloads, with native byte budgets.

This grants no exclusions, output ownership or execution. A future source owner
must prove the full BEFORE partition, exact packages, fresh child absence and
exclusive creation. Old payloads stay read-only; no receipt restores custody.
"""

from dataclasses import dataclass, field

from literate_ai.adapters.retained_cargo_tree_v2 import RetainedCargoInputTreeV2
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.retained_cargo_native_custody import (
    RetainedCargoOutputBudget,
)


class _NativeOutputCensusLedger:
    """One readonly pass's aggregate accounting; grants no filesystem rights."""

    def __init__(
        self,
        budget,
        *,
        maximum_files=10000,
        maximum_entries=10000,
        maximum_metadata_bytes=1024**3,
    ):
        if (
            type(maximum_metadata_bytes) is not int
            or not 16 * 1024**2 <= maximum_metadata_bytes <= 16 * 1024**3
        ):
            raise ValueError("retained.output-census.aggregate-metadata-limit-invalid")
        self._budget = _NativeOutputTreeBudget(budget, maximum_files, maximum_entries)
        self._limits = (*self._budget._limits[:4], maximum_metadata_bytes)
        self._used = (0, 0, 0, 0)

    def require_budget(self, budget):
        self._budget._require_current()
        if budget._limits[:4] != self._limits[:4]:
            raise ValueError("retained.output-census.aggregate-budget-changed")

    @property
    def remaining_metadata(self):
        self._budget._require_current()
        return self._limits[4] - self._used[3]

    @property
    def usage(self):
        return self._used

    def charge(self, *, files, entries, payload_bytes, metadata_bytes):
        self._budget._require_current()
        values = (files, entries, payload_bytes, metadata_bytes)
        if any(type(value) is not int or value < 0 for value in values):
            raise ValueError("retained.output-census.aggregate-charge-invalid")
        totals = tuple(a + b for a, b in zip(self._used, values, strict=True))
        limits = (self._limits[0], self._limits[1], self._limits[3], self._limits[4])
        for name, total, limit in zip(
            ("files", "entries", "bytes", "metadata"), totals, limits, strict=True
        ):
            if total > limit:
                raise ValueError("retained.output-census.aggregate-" + name + "-limit")
        self._used = totals


@dataclass(frozen=True, slots=True)
class _NativeOutputTreeBudget:
    native: RetainedCargoOutputBudget
    maximum_files: int
    maximum_entries: int
    _ledger: object = field(default=None, repr=False, compare=False)
    _metadata_limit: int = field(default=1024**3, repr=False, compare=False)
    _original_ledger: object = field(init=False, repr=False, compare=False)
    _limits: tuple = field(init=False, repr=False)

    def __post_init__(self):
        if type(self.native) is not RetainedCargoOutputBudget:
            raise TypeError("retained.output-census.native-budget-required")
        if (
            type(self.maximum_files) is not int
            or type(self.maximum_entries) is not int
            or not 1 <= self.maximum_files <= 100000
            or not self.maximum_files <= self.maximum_entries <= 400000
        ):
            raise ValueError("retained.output-census.namespace-limits-invalid")
        if (
            type(self._metadata_limit) is not int
            or not 16 * 1024**2 <= self._metadata_limit <= 16 * 1024**3
        ):
            raise ValueError("retained.output-census.metadata-limit-invalid")
        # Revalidate exact typed declarations, then retain their original values.
        # This creates only a resource value, never a new source/output owner.
        RetainedCargoOutputBudget(
            self.native.maximum_file_bytes, self.native.maximum_total_bytes
        )
        object.__setattr__(
            self,
            "_limits",
            (
                self.maximum_files,
                self.maximum_entries,
                self.native.maximum_file_bytes,
                self.native.maximum_total_bytes,
                self._metadata_limit,
            ),
        )
        object.__setattr__(self, "_original_ledger", self._ledger)
        if self._ledger is not None:
            if type(self._ledger) is not _NativeOutputCensusLedger:
                raise TypeError("retained.output-census.aggregate-ledger-required")
            self._ledger.require_budget(self)

    def _require_current(self):
        current = (
            self.maximum_files,
            self.maximum_entries,
            self.native.maximum_file_bytes,
            self.native.maximum_total_bytes,
            self._metadata_limit,
        )
        if any(type(value) is not int for value in current) or current != self._limits:
            raise ValueError("retained.output-census.original-budget-changed")
        if self._ledger is not self._original_ledger:
            raise ValueError("retained.output-census.original-ledger-changed")
        if self._ledger is not None:
            self._ledger.require_budget(self)

    @property
    def maximum_file_bytes(self):
        return self._limits[2]

    @property
    def maximum_total_bytes(self):
        return self._limits[3]

    def to_dict(self):
        return {
            "native": {
                "maximum_file_bytes": self._limits[2],
                "maximum_total_bytes": self._limits[3],
            },
            "maximum_files": self.maximum_files,
            "maximum_entries": self.maximum_entries,
        }


@dataclass(frozen=True, slots=True, eq=False)
class _OriginalNativeOutputTree(RetainedCargoInputTreeV2):
    _metadata_charge: int = field(default=0, repr=False, compare=False)

    @property
    def identity(self):
        return canonical_identity(
            {
                "schema": "literate-ai/original-native-output-tree@1",
                "budget": self.budget.to_dict(),
                "maximum_metadata_bytes": self.maximum_metadata_bytes,
                "exclusions": list(self.exclusions),
                "directories": list(self.directories),
                "files": [
                    {"path": name, "blob": blob.to_dict(), "executable": executable}
                    for name, blob, executable in self.files
                ],
                "aliases": [alias.to_dict() for alias in self.aliases],
            }
        )

    def require_unchanged(self, *, _ledger=None):
        self.budget._require_current()
        current = _capture_original_native_output_tree(
            self.root,
            budget=self.budget.native,
            maximum_files=self.budget.maximum_files,
            maximum_entries=self.budget.maximum_entries,
            exclusions=self.exclusions,
            maximum_metadata_bytes=self.maximum_metadata_bytes,
            _ledger=_ledger,
        )
        self.budget._require_current()
        if self._physical != current._physical or self != current:
            raise ValueError("retained.output-census.original-tree-changed")

    def __copy__(self):
        raise TypeError("retained.output-census.not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.output-census.not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.output-census.not-serializable")


def _capture_original_native_output_tree(
    root,
    *,
    budget,
    maximum_files=10000,
    maximum_entries=10000,
    exclusions=(),
    maximum_metadata_bytes=1024**3,
    _ledger=None,
):
    """Read only, no CAS copy, source quota transfer or exclusion permission.

    Exclusions are raw observation selectors only. An owning source operation
    must independently prove absence and exclusive fresh-child ownership before
    any selected name can become a writable/executable output. This snapshot
    alone supplies none of that authority.
    """
    from literate_ai.adapters.retained_cargo_tree_v2 import (
        _capture_retained_cargo_tree,
    )

    if (
        type(maximum_metadata_bytes) is not int
        or not 16 * 1024**2 <= maximum_metadata_bytes <= 16 * 1024**3
    ):
        raise ValueError("retained.output-census.metadata-limit-invalid")
    native = _NativeOutputTreeBudget(
        budget, maximum_files, maximum_entries, _ledger, maximum_metadata_bytes
    )
    if _ledger is not None:
        maximum_metadata_bytes = min(maximum_metadata_bytes, _ledger.remaining_metadata)
    return _capture_retained_cargo_tree(
        root,
        budget=native,
        exclusions=exclusions,
        maximum_metadata_bytes=maximum_metadata_bytes,
        _native_output=True,
    )
