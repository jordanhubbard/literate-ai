"""Reviewed external selections; decoded declarations grant no live authority."""

from dataclasses import dataclass
from typing import ClassVar

from ._validation import contract_fields, fail, fields, list_value, string_value
from .executable_components._common import portable_name
from .identity import ContentIdentity, canonical_identity

QUALIFIED_LIBRARY_ASSET_ROLE = "qualified-library-inputs"


@dataclass(frozen=True, slots=True)
class ExternalQualifiedLibrarySelection:
    selection_id: str
    provider_component_revision: ContentIdentity
    reviewed_binding_identity: ContentIdentity
    qualification_identity: ContentIdentity
    run_identity: ContentIdentity
    product_identity: ContentIdentity
    export_identities: tuple[ContentIdentity, ...]
    import_surface_identity: ContentIdentity
    capability: str
    interface_identity: ContentIdentity
    importer_project_id: str
    evidence_store_id: str
    target_profile_identity: ContentIdentity

    _IDENTITIES: ClassVar[tuple[str, ...]] = (
        "provider_component_revision",
        "reviewed_binding_identity",
        "qualification_identity",
        "run_identity",
        "product_identity",
        "import_surface_identity",
        "interface_identity",
        "target_profile_identity",
    )
    _STRINGS: ClassVar[tuple[str, ...]] = (
        "selection_id",
        "capability",
        "importer_project_id",
        "evidence_store_id",
    )

    def __post_init__(self):
        for name in self._IDENTITIES:
            if type(getattr(self, name)) is not ContentIdentity:
                fail(name, "requires an exact content identity")
        for name in ("selection_id", "capability", "evidence_store_id"):
            portable_name(getattr(self, name), name)
        string_value(self.importer_project_id, "importer_project_id", max_length=256)
        if any(ord(char) < 32 or ord(char) == 127 for char in self.importer_project_id):
            fail("importer_project_id", "requires a printable identifier")
        exports = self.export_identities
        if (
            type(exports) is not tuple
            or not 1 <= len(exports) <= 4096
            or any(type(value) is not ContentIdentity for value in exports)
            or tuple(value.uri for value in exports)
            != tuple(sorted({value.uri for value in exports}))
        ):
            fail(
                "export_identities", "requires a bounded canonical complete export set"
            )

    @property
    def identity(self):
        return canonical_identity(self.to_dict())

    def to_dict(self):
        return {
            **{name: getattr(self, name).to_dict() for name in self._IDENTITIES},
            **{name: getattr(self, name) for name in self._STRINGS},
            "export_identities": [value.to_dict() for value in self.export_identities],
        }

    @classmethod
    def from_dict(cls, value):
        data = fields(
            value,
            path=cls.__name__,
            required=frozenset((*cls._IDENTITIES, *cls._STRINGS, "export_identities")),
        )
        exports = list_value(data["export_identities"], "export_identities")
        if not 1 <= len(exports) <= 4096:
            fail("export_identities", "export allowance exceeded")
        return cls(
            **{name: ContentIdentity.from_dict(data[name]) for name in cls._IDENTITIES},
            **{name: data[name] for name in cls._STRINGS},
            export_identities=tuple(
                ContentIdentity.from_dict(value) for value in exports
            ),
        )


@dataclass(frozen=True, slots=True)
class NativeRootExternalLibrarySelections:
    """Root asset content; consumer revision is bound by the enclosing asset.

    Embedding that revision here would introduce a root/asset identity cycle.
    No filesystem path, transport credential or execution permission is carried.
    """

    selections: tuple[ExternalQualifiedLibrarySelection, ...]
    SCHEMA: ClassVar[str] = "literate-ai/native-root-external-library-selection@1"

    def __post_init__(self):
        if (
            type(self.selections) is not tuple
            or not 1 <= len(self.selections) <= 64
            or any(
                type(row) is not ExternalQualifiedLibrarySelection
                for row in self.selections
            )
        ):
            fail("selections", "requires 1 to 64 exact typed selections")
        keys = tuple(row.selection_id for row in self.selections)
        edges = tuple(
            (row.provider_component_revision.uri, row.capability)
            for row in self.selections
        )
        if keys != tuple(sorted(set(keys))) or len(edges) != len(set(edges)):
            fail(
                "selections",
                "requires unique ordered names and provider/capability pairs",
            )

    @property
    def identity(self):
        return canonical_identity(self.to_dict())

    def to_dict(self):
        return {
            "schema": self.SCHEMA,
            "selections": [row.to_dict() for row in self.selections],
        }

    @classmethod
    def from_dict(cls, value):
        data = contract_fields(
            value,
            path=cls.__name__,
            schema_uri=cls.SCHEMA,
            required=frozenset({"selections"}),
        )
        rows = list_value(data["selections"], "selections")
        if not 1 <= len(rows) <= 64:
            fail("selections", "selection allowance exceeded")
        return cls(
            tuple(ExternalQualifiedLibrarySelection.from_dict(row) for row in rows)
        )
