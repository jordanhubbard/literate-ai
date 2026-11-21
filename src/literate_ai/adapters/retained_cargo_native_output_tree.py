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


@dataclass(frozen=True, slots=True)
class _NativeOutputTreeBudget:
    native: RetainedCargoOutputBudget
    maximum_files: int
    maximum_entries: int
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
            ),
        )

    def _require_current(self):
        current = (
            self.maximum_files,
            self.maximum_entries,
            self.native.maximum_file_bytes,
            self.native.maximum_total_bytes,
        )
        if any(type(value) is not int for value in current) or current != self._limits:
            raise ValueError("retained.output-census.original-budget-changed")

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

    def require_unchanged(self):
        self.budget._require_current()
        current = _capture_original_native_output_tree(
            self.root,
            budget=self.budget.native,
            maximum_files=self.budget.maximum_files,
            maximum_entries=self.budget.maximum_entries,
            exclusions=self.exclusions,
            maximum_metadata_bytes=self.maximum_metadata_bytes,
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

    native = _NativeOutputTreeBudget(budget, maximum_files, maximum_entries)
    return _capture_retained_cargo_tree(
        root,
        budget=native,
        exclusions=exclusions,
        maximum_metadata_bytes=maximum_metadata_bytes,
        _native_output=True,
    )
