"""Strict local receiving coordinates, separate from portable root authority."""

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

from literate_ai.adapters.models import CODING_CLIS
from literate_ai.contracts._validation import (
    contract_fields,
    fail,
    fields,
    list_value,
    string_value,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.executable_components._common import portable_name
from literate_ai.contracts.paths import canonical_relative_posix_path


def local_absolute_path(value, label):
    string_value(value, label, max_length=4096)
    path = Path(value)
    if not path.is_absolute() or ".." in path.parts or "\x00" in value:
        fail(label, "requires an explicit absolute local coordinate")
    return path


def _overlap(left, right):
    left, right = Path(str(left).casefold()), Path(str(right).casefold())
    return left.is_relative_to(right) or right.is_relative_to(left)


@dataclass(frozen=True, slots=True)
class QualifiedReceiverLocator:
    """Locations are operator coordinates; archive records never select them."""

    selection_ids: tuple[str, ...]
    importer_project: str
    reviewed_binding: BlobRef
    binding_path: str
    workspace_plan_path: str
    gate_policy_path: str
    test_inventory_path: str
    provider_project: str
    provider_component: str
    provider_profile: str
    provider_id: str
    pipeline_model: str | None
    provider_target: str
    provider_flavors: tuple[str, ...]
    archive_path: str
    provider_receivers: str | None = None

    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "selection_ids",
            "importer_project",
            "reviewed_binding",
            "binding_path",
            "workspace_plan_path",
            "gate_policy_path",
            "test_inventory_path",
            "provider_project",
            "provider_component",
            "provider_profile",
            "provider_id",
            "pipeline_model",
            "provider_target",
            "provider_flavors",
            "archive_path",
        }
    )

    def __post_init__(self):
        if (
            type(self.selection_ids) is not tuple
            or not 1 <= len(self.selection_ids) <= 64
            or any(type(value) is not str for value in self.selection_ids)
            or self.selection_ids != tuple(sorted(set(self.selection_ids)))
        ):
            fail("selection_ids", "requires bounded unique ordered names")
        for value in self.selection_ids:
            portable_name(value, "selection_ids")
        for name in ("importer_project", "provider_project", "archive_path"):
            local_absolute_path(getattr(self, name), name)
        if self.provider_receivers is not None:
            local_absolute_path(self.provider_receivers, "provider_receivers")
        for name in (
            "binding_path",
            "workspace_plan_path",
            "gate_policy_path",
            "test_inventory_path",
            "provider_profile",
        ):
            canonical_relative_posix_path(getattr(self, name), label=name)
        if self.provider_component != ".":
            canonical_relative_posix_path(
                self.provider_component, label="provider_component"
            )
        if (
            type(self.reviewed_binding) is not BlobRef
            or self.reviewed_binding.media_type != "application/json"
            or not 0 < self.reviewed_binding.size <= 16 * 1024**2
        ):
            fail(
                "reviewed_binding",
                "requires an independently configured bounded JSON reference",
            )
        if type(self.provider_id) is not str or self.provider_id not in CODING_CLIS:
            fail("provider_id", "requires an explicit supported logical provider")
        if self.pipeline_model is not None:
            string_value(self.pipeline_model, "pipeline_model", max_length=512)
            if not self.pipeline_model.strip():
                fail("pipeline_model", "requires a nonblank explicit selector or null")
        portable_name(self.provider_target, "provider_target")
        if (
            type(self.provider_flavors) is not tuple
            or len(self.provider_flavors) > 64
            or any(
                type(value) is not str or not value or len(value) > 1024
                for value in self.provider_flavors
            )
        ):
            fail("provider_flavors", "requires bounded explicit ordered selectors")

    @classmethod
    def from_dict(cls, value):
        data = fields(
            value,
            path=cls.__name__,
            required=cls._FIELDS,
            optional=frozenset({"provider_receivers"}),
        )
        names = list_value(data["selection_ids"], "selection_ids")
        flavors = list_value(data["provider_flavors"], "provider_flavors")
        if len(names) > 64 or len(flavors) > 64:
            fail(cls.__name__, "selection allowance exceeded")
        return cls(
            **{
                name: (
                    tuple(names)
                    if name == "selection_ids"
                    else tuple(flavors)
                    if name == "provider_flavors"
                    else BlobRef.from_dict(data[name])
                    if name == "reviewed_binding"
                    else data[name]
                )
                for name in cls._FIELDS
            },
            provider_receivers=data.get("provider_receivers"),
        )


@dataclass(frozen=True, slots=True)
class QualifiedReceiverConfiguration:
    receivers: tuple[QualifiedReceiverLocator, ...]
    max_plan_bytes: int
    max_archive_bytes: int
    max_records: int
    max_package_bytes: int

    SCHEMA: ClassVar[str] = "literate-ai/native-root-qualified-library-receivers@1"
    _LIMITS: ClassVar[dict[str, int]] = {
        "max_plan_bytes": 16 * 1024**2,
        "max_archive_bytes": 256 * 1024**2,
        "max_records": 16384,
        "max_package_bytes": 256 * 1024**2,
    }

    def __post_init__(self):
        if (
            type(self.receivers) is not tuple
            or not 1 <= len(self.receivers) <= 64
            or any(
                type(value) is not QualifiedReceiverLocator for value in self.receivers
            )
        ):
            fail("receivers", "requires 1 to 64 exact local receiver declarations")
        names = tuple(
            value for receiver in self.receivers for value in receiver.selection_ids
        )
        if len(names) > 64 or len(set(names)) != len(names):
            fail("receivers", "each root selection must have one receiving owner")
        for name, maximum in self._LIMITS.items():
            value = getattr(self, name)
            if type(value) is not int or not 0 < value <= maximum:
                fail(name, "requires a positive bounded integer")

    def require_distinct_projects(self, consumer_root):
        """Reject self/nested/duplicate writers before entering wrapper locks."""
        roots = [Path(consumer_root)]
        roots.extend(
            local_absolute_path(row.importer_project, "importer_project")
            for row in self.receivers
        )
        for index, root in enumerate(roots):
            for previous in roots[:index]:
                if (
                    str(root).casefold() == str(previous).casefold()
                    or Path(str(root).casefold()).is_relative_to(
                        Path(str(previous).casefold())
                    )
                    or Path(str(previous).casefold()).is_relative_to(
                        Path(str(root).casefold())
                    )
                ):
                    fail(
                        "importer_project",
                        "consumer and receiving writers require "
                        "distinct disjoint projects",
                    )
        nested_roots = tuple(
            Path(row.provider_project)
            for row in self.receivers
            if row.provider_receivers is not None
        )
        for index, root in enumerate(nested_roots):
            for previous in nested_roots[:index]:
                if _overlap(root, previous):
                    fail(
                        "provider_receivers",
                        "group shared provider selections under one receiver",
                    )
        for row in self.receivers:
            provider = local_absolute_path(row.provider_project, "provider_project")
            if any(
                Path(str(provider).casefold()).is_relative_to(
                    Path(str(root).casefold())
                )
                or Path(str(root).casefold()).is_relative_to(
                    Path(str(provider).casefold())
                )
                for root in roots
            ):
                fail(
                    "provider_project",
                    "provider source must be separate from consumer/importer mutation",
                )

    @classmethod
    def from_dict(cls, value):
        data = contract_fields(
            value,
            path=cls.__name__,
            schema_uri=cls.SCHEMA,
            required=frozenset({"receivers", "limits"}),
        )
        rows = list_value(data["receivers"], "receivers")
        if not 1 <= len(rows) <= 64:
            fail("receivers", "receiver allowance exceeded")
        limits = fields(data["limits"], path="limits", required=frozenset(cls._LIMITS))
        return cls(
            tuple(QualifiedReceiverLocator.from_dict(row) for row in rows), **limits
        )
