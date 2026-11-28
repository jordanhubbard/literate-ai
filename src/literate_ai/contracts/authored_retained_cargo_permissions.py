"""Independent operator-reviewed exclusions, scoped to one authored binding.

Decoding this inert document grants nothing. The CLI must reopen exact bytes
against an independent operator BlobRef and keep that file owner current during
execution and final permission refresh. Candidate inventory is never authority.
"""

from dataclasses import dataclass
from typing import ClassVar

from literate_ai.contracts._validation import contract_fields, fail, list_value
from literate_ai.contracts.identity import ContentIdentity, canonical_identity
from literate_ai.contracts.retained_cargo_authored import AuthoredRetainedCargoBinding


@dataclass(frozen=True, slots=True)
class AuthoredRetainedCargoExclusionAuthority:
    importer_project_id: str
    binding_identity: ContentIdentity
    permissions: tuple[ContentIdentity, ...]

    SCHEMA: ClassVar[str] = "literate-ai/authored-retained-cargo-exclusion-authority@1"

    def __post_init__(self):
        if (
            not isinstance(self.importer_project_id, str)
            or not 1 <= len(self.importer_project_id) <= 256
            or any(
                ord(char) < 32 or ord(char) == 127 for char in self.importer_project_id
            )
            or type(self.binding_identity) is not ContentIdentity
        ):
            fail(
                self.__class__.__name__,
                "requires exact importer and binding identities",
            )
        if (
            type(self.permissions) is not tuple
            or len(self.permissions) > 4096
            or any(type(item) is not ContentIdentity for item in self.permissions)
            or self.permissions
            != tuple(sorted(set(self.permissions), key=lambda item: item.uri))
        ):
            fail(
                self.__class__.__name__,
                "requires bounded sorted distinct permission identities",
            )

    @property
    def identity(self):
        return canonical_identity(self.to_dict())

    def require_binding(self, binding):
        if (
            type(binding) is not AuthoredRetainedCargoBinding
            or binding.importer_project_id != self.importer_project_id
            or binding.identity != self.binding_identity
        ):
            fail(
                self.__class__.__name__,
                "exclusion authority belongs to another binding",
            )

    def to_dict(self):
        return dict(
            schema=self.SCHEMA,
            importer_project_id=self.importer_project_id,
            binding_identity=self.binding_identity.to_dict(),
            permissions=[item.to_dict() for item in self.permissions],
        )

    @classmethod
    def from_dict(cls, value):
        data = contract_fields(
            value,
            path=cls.__name__,
            schema_uri=cls.SCHEMA,
            required={"importer_project_id", "binding_identity", "permissions"},
        )
        items = list_value(data["permissions"], cls.__name__)
        if len(items) > 4096:
            fail(cls.__name__, "permission record allowance exceeded")
        return cls(
            data["importer_project_id"],
            ContentIdentity.from_dict(data["binding_identity"]),
            tuple(ContentIdentity.from_dict(item) for item in items),
        )
