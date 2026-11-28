"""Independent importer review of historical authored producer intent.

This passive document grants no current provider, execution or importer authority.
Its exact bytes require an independent operator BlobRef and original file custody.
"""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import ClassVar

from ._validation import contract_fields, fail
from .authored_qualification_plans import AuthoredQualificationPlan
from .generation_cache import source_cache_model_selector
from .identity import ContentIdentity, canonical_identity
from .model_scopes import _GENERATION_PROVIDERS
from .paths import canonical_relative_posix_path
from .retained_cargo_authored import AuthoredRetainedCargoBinding


@dataclass(frozen=True, slots=True)
class AuthoredRetainedCargoProducerReview:
    importer_project_id: str
    binding_identity: ContentIdentity
    evidence_store_id: str
    provider_reference_identity: ContentIdentity
    provider_plan: AuthoredQualificationPlan
    coding_provider: str
    pipeline_model: str | None
    profile_path: str

    SCHEMA: ClassVar[str] = "literate-ai/authored-retained-cargo-producer-review@1"
    _FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "importer_project_id",
            "binding_identity",
            "evidence_store_id",
            "provider_reference_identity",
            "provider_plan",
            "coding_provider",
            "pipeline_model",
            "profile_path",
        }
    )

    def __post_init__(self):
        if (
            type(self.importer_project_id) is not str
            or not 1 <= len(self.importer_project_id) <= 256
            or any(ord(c) < 32 or ord(c) == 127 for c in self.importer_project_id)
            or type(self.evidence_store_id) is not str
            or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,127}", self.evidence_store_id)
            is None
        ):
            fail(self.__class__.__name__, "requires bounded importer and store names")
        # Matching this passive record never selects a store or grants transport.
        if (
            type(self.binding_identity) is not ContentIdentity
            or type(self.provider_reference_identity) is not ContentIdentity
            or type(self.provider_plan) is not AuthoredQualificationPlan
        ):
            fail(self.__class__.__name__, "requires exact typed producer identities")
        if type(self.coding_provider) is not str or self.coding_provider not in (
            _GENERATION_PROVIDERS
        ):
            fail(self.__class__.__name__, "requires a logical generation provider")
        if self.pipeline_model is not None and (
            type(self.pipeline_model) is not str
            or any(ord(c) < 32 or ord(c) == 127 for c in self.pipeline_model)
        ):
            fail(
                self.__class__.__name__,
                "requires an explicit printable model or omission",
            )
        source_cache_model_selector(self.pipeline_model)
        canonical_relative_posix_path(self.profile_path, label="producer profile")
        if (
            len(self.profile_path) > 128
            or PurePosixPath(self.profile_path).parts[0] != "litai"
        ):
            fail(
                self.__class__.__name__,
                "requires a bounded original litai profile path",
            )

    @property
    def identity(self):
        return canonical_identity(self.to_dict())

    def require_binding(self, binding):
        if (
            type(binding) is not AuthoredRetainedCargoBinding
            or binding.importer_project_id != self.importer_project_id
            or binding.identity != self.binding_identity
            or binding.evidence_store_id != self.evidence_store_id
            or binding.provider_reference.identity != self.provider_reference_identity
            or binding.provider_reference.plan_identity != self.provider_plan.identity
            or binding.provider_reference.origin != self.provider_plan.origin
        ):
            fail(self.__class__.__name__, "producer review belongs to another binding")

    def to_dict(self):
        return {
            "schema": self.SCHEMA,
            "importer_project_id": self.importer_project_id,
            "binding_identity": self.binding_identity.to_dict(),
            "evidence_store_id": self.evidence_store_id,
            "provider_reference_identity": self.provider_reference_identity.to_dict(),
            "provider_plan": self.provider_plan.to_dict(),
            "coding_provider": self.coding_provider,
            "pipeline_model": self.pipeline_model,
            "profile_path": self.profile_path,
        }

    @classmethod
    def from_dict(cls, value):
        data = contract_fields(
            value,
            path=cls.__name__,
            schema_uri=cls.SCHEMA,
            required=cls._FIELDS,
        )
        return cls(
            data["importer_project_id"],
            ContentIdentity.from_dict(data["binding_identity"]),
            data["evidence_store_id"],
            ContentIdentity.from_dict(data["provider_reference_identity"]),
            AuthoredQualificationPlan.from_dict(data["provider_plan"]),
            data["coding_provider"],
            data["pipeline_model"],
            data["profile_path"],
        )
