"""Authored retained Cargo intent; decoded records grant no importer permission.

Provider origin is carried by its actual published authored reference. Consumer
workspace, gate and target inventory declarations keep their existing meanings;
none of these records invents provider promotion or source-retirement history.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, ClassVar

from ._validation import contract_fields, fail, fields, list_value
from .authored_qualification_reference import AuthoredQualificationReference
from .blobs import BlobRef
from .identity import ContentIdentity, canonical_identity
from .paths import canonical_relative_posix_paths
from .retained_cargo_policy import RetainedLibraryGatePolicyV2
from .retained_cargo_tests_v2 import RetainedCargoTestInventoryV2
from .retained_cargo_workspace_v2 import RetainedCargoWorkspacePlanV2
from .retained_libraries import RetainedLibraryExportSet


@dataclass(frozen=True, slots=True)
class AuthoredRetainedCargoBinding:
    """Reviewed declarations for one selected run of a complete authored result.

    A receiver must independently reopen the current published reference, plan,
    private oracles and every clean run before selecting these exact exports.
    The selected run is not permission to omit validation of the other runs.
    """

    importer_project_id: str
    evidence_store_id: str
    provider_reference: AuthoredQualificationReference
    selected_run_identity: ContentIdentity
    exports: RetainedLibraryExportSet
    workspace_plan: BlobRef
    gate_policy: BlobRef
    test_inventory: BlobRef
    destinations: tuple[tuple[ContentIdentity, str], ...]

    SCHEMA: ClassVar[str] = "literate-ai/authored-retained-cargo-binding@1"
    MAX_DESTINATIONS: ClassVar[int] = 4096
    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "importer_project_id",
            "evidence_store_id",
            "provider_reference",
            "selected_run_identity",
            "exports",
            "workspace_plan",
            "gate_policy",
            "test_inventory",
            "destinations",
        }
    )

    def __post_init__(self):
        if (
            not isinstance(self.importer_project_id, str)
            or not 1 <= len(self.importer_project_id) <= 256
            or any(ord(c) < 32 or ord(c) == 127 for c in self.importer_project_id)
        ):
            fail(self.__class__.__name__, "requires a printable importer identifier")
        if (
            not isinstance(self.evidence_store_id, str)
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", self.evidence_store_id)
            is None
        ):
            fail(
                self.__class__.__name__, "requires a configured logical evidence store"
            )
        if type(self.provider_reference) is not AuthoredQualificationReference:
            fail(self.__class__.__name__, "requires the exact authored reference codec")
        if not isinstance(self.selected_run_identity, ContentIdentity):
            fail(self.__class__.__name__, "requires an explicit selected run identity")
        if type(self.exports) is not RetainedLibraryExportSet:
            fail(self.__class__.__name__, "requires an exact closed export set")
        for reference in (self.workspace_plan, self.gate_policy, self.test_inventory):
            if (
                type(reference) is not BlobRef
                or reference.media_type != "application/json"
                or not 0 < reference.size <= 256 * 1024 * 1024
            ):
                fail(self.__class__.__name__, "requires finite nonempty reviewed JSON")
        if (
            not isinstance(self.destinations, tuple)
            or not 1 <= len(self.destinations) <= self.MAX_DESTINATIONS
            or any(
                not isinstance(row, tuple)
                or len(row) != 2
                or not isinstance(row[0], ContentIdentity)
                or not isinstance(row[1], str)
                or len(row[1]) > 128
                for row in self.destinations
            )
        ):
            fail(self.__class__.__name__, "requires bounded typed export/path pairs")
        expected = {
            export.identity.uri
            for manifest in self.exports.graph.manifests
            for export in manifest.exports
        }
        if tuple(identity.uri for identity, _ in self.destinations) != tuple(
            sorted(expected)
        ):
            fail(
                self.__class__.__name__,
                "must place every export once in identity order",
            )
        canonical_relative_posix_paths(
            (path for _, path in self.destinations), label="authored Cargo destinations"
        )

    @property
    def identity(self):
        return canonical_identity(self.to_dict())

    def require_declarations(self, plan, policy, inventory):
        """Check exact consumer declarations without claiming provider admission."""
        if (
            type(plan) is not RetainedCargoWorkspacePlanV2
            or type(policy) is not RetainedLibraryGatePolicyV2
            or type(inventory) is not RetainedCargoTestInventoryV2
        ):
            fail(
                self.__class__.__name__, "requires matching typed consumer declarations"
            )
        plan.require_gate_policy(policy)
        inventory.require_graph(plan.graph)
        if (
            policy.importer_project_id != self.importer_project_id
            or inventory.importer_project_id != self.importer_project_id
            or inventory.workspace_plan_identity != plan.identity
            or inventory.gate_policy_identity != policy.identity
        ):
            fail(self.__class__.__name__, "consumer declaration identities differ")

    def to_dict(self):
        return {
            "schema": self.SCHEMA,
            "importer_project_id": self.importer_project_id,
            "evidence_store_id": self.evidence_store_id,
            "provider_reference": self.provider_reference.to_dict(),
            "selected_run_identity": self.selected_run_identity.to_dict(),
            "exports": self.exports.to_dict(),
            "workspace_plan": self.workspace_plan.to_dict(),
            "gate_policy": self.gate_policy.to_dict(),
            "test_inventory": self.test_inventory.to_dict(),
            "destinations": [
                {"export_identity": identity.to_dict(), "path": path}
                for identity, path in self.destinations
            ],
        }

    @classmethod
    def from_dict(cls, value: Any):
        data = contract_fields(
            value, path=cls.__name__, schema_uri=cls.SCHEMA, required=cls._FIELDS
        )
        destinations = list_value(data["destinations"], cls.__name__)
        if not 1 <= len(destinations) <= cls.MAX_DESTINATIONS:
            fail(cls.__name__, "destination allowance exceeded")
        rows = []
        for value in destinations:
            row = fields(
                value,
                path=cls.__name__ + ".destinations",
                required=frozenset({"export_identity", "path"}),
            )
            rows.append(
                (ContentIdentity.from_dict(row["export_identity"]), row["path"])
            )
        return cls(
            data["importer_project_id"],
            data["evidence_store_id"],
            AuthoredQualificationReference.from_dict(data["provider_reference"]),
            ContentIdentity.from_dict(data["selected_run_identity"]),
            RetainedLibraryExportSet.from_dict(data["exports"]),
            BlobRef.from_dict(data["workspace_plan"]),
            BlobRef.from_dict(data["gate_policy"]),
            BlobRef.from_dict(data["test_inventory"]),
            tuple(rows),
        )
