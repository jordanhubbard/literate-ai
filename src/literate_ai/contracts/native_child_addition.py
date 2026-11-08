"""Exact reviewed authority for adding an already-qualified native child."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import ClassVar

from .identity import ContentIdentity, canonical_identity


@dataclass(frozen=True)
class QualifiedNativeChildAdditionPlan:
    SCHEMA: ClassVar[str] = "literate-ai/qualified-native-child-addition-plan@1"

    parent_definition: ContentIdentity
    parent_authority: ContentIdentity
    parent_receipt: ContentIdentity
    registry: ContentIdentity
    child: str
    child_project_id: str
    child_definition: ContentIdentity
    child_authorities: tuple[ContentIdentity, ...]
    child_evidence: tuple[ContentIdentity, ...]
    expected_evidence: tuple[ContentIdentity, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.child, str) or not isinstance(
            self.child_project_id, str
        ):
            raise ValueError("native child identifiers must be strings")
        if any(ord(character) < 32 for character in self.child_project_id):
            raise ValueError(
                "native child project identifier contains control characters"
            )
        if not all(
            isinstance(value, ContentIdentity)
            for value in (
                self.parent_definition,
                self.parent_authority,
                self.parent_receipt,
                self.registry,
                self.child_definition,
            )
        ):
            raise ValueError("native child addition requires content identities")
        path = PurePosixPath(self.child)
        if (
            path.is_absolute()
            or path.parts[:2] != (".literate", "native-projects")
            or len(path.parts) != 3
            or path.as_posix() != self.child
            or ".." in path.parts
            or "\\" in self.child
            or not self.child_project_id
        ):
            raise ValueError("native child addition requires one exact direct child")
        for identities in (
            self.child_authorities,
            self.child_evidence,
            self.expected_evidence,
        ):
            if not identities or identities != tuple(
                sorted(set(identities), key=lambda value: value.uri)
            ):
                raise ValueError("native child evidence must be nonempty and canonical")
        if not set(self.child_evidence).issubset(self.expected_evidence):
            raise ValueError("the expected evidence must retain all child evidence")

    def _payload(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "writes": False,
            "parent_definition_identity": self.parent_definition.uri,
            "parent_authority_identity": self.parent_authority.uri,
            "parent_receipt_identity": self.parent_receipt.uri,
            "registry_identity": self.registry.uri,
            "child": self.child,
            "child_project_id": self.child_project_id,
            "child_definition_identity": self.child_definition.uri,
            "child_authority_identities": [v.uri for v in self.child_authorities],
            "child_evidence": [v.uri for v in self.child_evidence],
            "expected_evidence": [v.uri for v in self.expected_evidence],
        }

    @property
    def identity(self) -> ContentIdentity:
        return canonical_identity(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "plan_identity": self.identity.uri}

    @classmethod
    def from_dict(cls, value: object) -> QualifiedNativeChildAdditionPlan:
        if not isinstance(value, dict):
            raise ValueError("native child addition plan must be an object")
        try:
            identity = ContentIdentity.parse_uri
            plan = cls(
                parent_definition=identity(value["parent_definition_identity"]),
                parent_authority=identity(value["parent_authority_identity"]),
                parent_receipt=identity(value["parent_receipt_identity"]),
                registry=identity(value["registry_identity"]),
                child=value["child"],
                child_project_id=value["child_project_id"],
                child_definition=identity(value["child_definition_identity"]),
                child_authorities=tuple(
                    identity(v) for v in value["child_authority_identities"]
                ),
                child_evidence=tuple(identity(v) for v in value["child_evidence"]),
                expected_evidence=tuple(
                    identity(v) for v in value["expected_evidence"]
                ),
            )
            if value != plan.to_dict() or value.get("writes") is not False:
                raise ValueError(
                    "native child addition plan is noncanonical or changed"
                )
            return plan
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError("native child addition plan is invalid") from exc
