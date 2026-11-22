"""Exact source-backed asset declarations at the inverse review boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from literate_ai.contracts import ComponentCoordinate, ContentIdentity
from literate_ai.contracts.component_locking.authoring import ComponentAssetSelector
from literate_ai.contracts.paths import (
    canonical_relative_posix_path,
    canonical_relative_posix_paths,
)

from .errors import SourceToSpecificationError

if TYPE_CHECKING:
    from .contracts import ComponentGraphDraft
    from .inventory import SourceInventory


def validate_asset_selectors(
    assets: tuple[ComponentAssetSelector, ...],
) -> None:
    """Keep declarations typed, pinned, portable and canonically ordered."""

    if not isinstance(assets, tuple) or any(
        not isinstance(item, ComponentAssetSelector) for item in assets
    ):
        raise SourceToSpecificationError(
            "component_graph.assets_invalid", "reviewed assets must be typed selectors"
        )
    identifiers = tuple(item.asset_id for item in assets)
    if identifiers != tuple(sorted(set(identifiers))):
        raise SourceToSpecificationError(
            "component_graph.assets_invalid",
            "reviewed asset ids must be unique and canonically ordered",
        )
    for item in assets:
        if item.pin is None:
            raise SourceToSpecificationError(
                "component_graph.asset_pin_required",
                "source-backed assets require an exact SHA-256 pin",
            )
        try:
            canonical_relative_posix_path(item.source, label="reviewed asset source")
        except (TypeError, ValueError) as exc:
            raise SourceToSpecificationError(
                "component_graph.asset_source_invalid",
                "reviewed asset sources must be canonical baseline-relative paths",
            ) from exc
        if any(
            part.casefold() in {".git", ".literate", ".codegraph"}
            for part in canonical_relative_posix_path(
                item.path, label="reviewed asset runtime path"
            ).parts
        ):
            raise SourceToSpecificationError(
                "component_graph.asset_path_invalid",
                "reviewed assets cannot enter private control directories",
            )
    try:
        canonical_relative_posix_paths(
            (item.path for item in assets), label="reviewed asset runtime path"
        )
        canonical_relative_posix_paths(
            sorted({item.source for item in assets}), label="reviewed asset source"
        )
    except (TypeError, ValueError) as exc:
        raise SourceToSpecificationError(
            "component_graph.asset_path_collision",
            "reviewed assets contain colliding or ambiguous paths",
        ) from exc


def validate_reviewed_asset_inventory(
    graph: ComponentGraphDraft,
    inventory: SourceInventory | None,
) -> None:
    """Bind metadata-only declarations to the exact admitted source snapshot."""

    from .inventory import SourceFileClassification

    assets = tuple(asset for node in graph.nodes for asset in node.assets)
    if not assets:
        return
    if inventory is None or inventory.identity != graph.source_snapshot_id:
        raise SourceToSpecificationError(
            "component_graph.asset_inventory_required",
            "reviewed assets require the exact source inventory for this snapshot",
        )
    entries = {entry.path: entry for entry in inventory.entries}
    for asset in assets:
        entry = entries.get(asset.source)
        if entry is None:
            raise SourceToSpecificationError(
                "component_graph.asset_source_unknown",
                "reviewed asset source is absent from the accepted inventory",
            )
        if entry.classification is SourceFileClassification.SENSITIVE:
            raise SourceToSpecificationError(
                "component_graph.asset_source_sensitive",
                "asset declarations cannot bypass sensitive source admission",
            )
        if asset.pin is None or asset.pin.uri != entry.content_digest:
            raise SourceToSpecificationError(
                "component_graph.asset_pin_mismatch",
                "reviewed asset pin differs from its exact source inventory entry",
            )


@dataclass(frozen=True, slots=True)
class ReviewedSourceAssetBinding:
    """A promotion-bound relation between original data and its immutable copy."""

    component_coordinate: str
    asset_id: str
    source_path: str
    project_path: str
    runtime_path: str
    role: str
    media_type: str
    content_identity: str
    byte_count: int

    def __post_init__(self) -> None:
        try:
            if not all(
                isinstance(value, str) and value
                for value in (
                    self.component_coordinate,
                    self.asset_id,
                    self.source_path,
                    self.project_path,
                    self.runtime_path,
                    self.role,
                    self.media_type,
                    self.content_identity,
                )
            ):
                raise ValueError("asset binding strings must be nonempty")
            prefix = "component://"
            if not self.component_coordinate.startswith(prefix):
                raise ValueError("asset binding requires a Component URI")
            namespace, name = self.component_coordinate.removeprefix(prefix).split("/")
            coordinate = ComponentCoordinate(namespace, name)
            if coordinate.uri != self.component_coordinate:
                raise ValueError("asset binding Component URI is not canonical")
            selector = ComponentAssetSelector(
                asset_id=self.asset_id,
                source=self.source_path,
                path=self.runtime_path,
                role=self.role,
                media_type=self.media_type,
                pin=ContentIdentity.parse_uri(self.content_identity),
            )
            validate_asset_selectors((selector,))
            expected = f"components/{name}/assets/{self.asset_id}"
            if self.project_path != expected:
                raise ValueError("asset binding must name its owning Component copy")
            canonical_relative_posix_path(self.project_path, label="asset binding copy")
            if type(self.byte_count) is not int or self.byte_count < 0:
                raise ValueError("asset binding byte count must be nonnegative")
        except (TypeError, ValueError) as exc:
            raise SourceToSpecificationError(
                "promotion.asset_binding_invalid", "reviewed asset binding is invalid"
            ) from exc

    def to_dict(self) -> dict[str, object]:
        return {
            "component_coordinate": self.component_coordinate,
            "asset_id": self.asset_id,
            "source_path": self.source_path,
            "project_path": self.project_path,
            "runtime_path": self.runtime_path,
            "role": self.role,
            "media_type": self.media_type,
            "content_identity": self.content_identity,
            "byte_count": self.byte_count,
        }

    @classmethod
    def from_dict(cls, value: Any) -> ReviewedSourceAssetBinding:
        expected = {
            "component_coordinate",
            "asset_id",
            "source_path",
            "project_path",
            "runtime_path",
            "role",
            "media_type",
            "content_identity",
            "byte_count",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise SourceToSpecificationError(
                "promotion.asset_binding_invalid",
                "reviewed asset binding fields are invalid",
            )
        return cls(**value)


def validate_asset_bindings(bindings: tuple[ReviewedSourceAssetBinding, ...]) -> None:
    if not isinstance(bindings, tuple) or any(
        not isinstance(item, ReviewedSourceAssetBinding) for item in bindings
    ):
        raise SourceToSpecificationError(
            "promotion.asset_binding_invalid", "asset bindings must be typed"
        )
    paths = tuple(item.project_path for item in bindings)
    if paths != tuple(sorted(set(paths))):
        raise SourceToSpecificationError(
            "promotion.asset_binding_invalid",
            "asset bindings must be canonical and unique",
        )


def validate_bound_component_assets(
    bindings: tuple[ReviewedSourceAssetBinding, ...],
    coordinate: str,
    assets: tuple[ComponentAssetSelector, ...],
) -> None:
    selected = {
        item.asset_id: item
        for item in bindings
        if item.component_coordinate == coordinate
    }
    declarations = {item.asset_id: item for item in assets}
    if set(selected) != set(declarations):
        raise SourceToSpecificationError(
            "promotion.asset_declaration_mismatch",
            "reviewed asset bindings differ from the owning Component declaration",
        )
    for asset_id, binding in selected.items():
        declaration = declarations[asset_id]
        if (
            declaration.source != f"assets/{asset_id}"
            or declaration.path != binding.runtime_path
            or declaration.role != binding.role
            or declaration.media_type != binding.media_type
            or declaration.pin is None
            or declaration.pin.uri != binding.content_identity
        ):
            raise SourceToSpecificationError(
                "promotion.asset_declaration_mismatch",
                "an authored asset differs from its provenance-bound declaration",
            )
