"""Exact review records for switching an existing qualified child revision."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import ClassVar

from .identity import ComponentCoordinate, ContentIdentity, canonical_identity


def _identities(values: tuple[ContentIdentity, ...]) -> None:
    if (
        not isinstance(values, tuple)
        or not values
        or not all(isinstance(value, ContentIdentity) for value in values)
        or values != tuple(sorted(set(values), key=lambda value: value.uri))
    ):
        raise ValueError("revision evidence must be nonempty and canonical")


@dataclass(frozen=True)
class QualifiedNativeChildSnapshot:
    child: str
    project_id: str
    definition: ContentIdentity
    receipt: ContentIdentity
    tree: ContentIdentity
    coordinates: tuple[str, ...]
    authorities: tuple[ContentIdentity, ...]
    evidence: tuple[ContentIdentity, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.child, str)
            or not isinstance(self.project_id, str)
            or not self.project_id
            or any(ord(character) < 32 for character in self.project_id)
        ):
            raise ValueError("revision requires exact child and project identifiers")
        path = PurePosixPath(self.child)
        if (
            path.parts[:2] != (".literate", "native-projects")
            or len(path.parts) != 3
            or path.as_posix() != self.child
            or ".." in path.parts
            or "\\" in self.child
            or any(ord(character) < 32 for character in self.child)
        ):
            raise ValueError("revision requires a direct native child path")
        if not all(
            isinstance(value, ContentIdentity)
            for value in (self.definition, self.receipt, self.tree)
        ):
            raise ValueError("revision requires content identities")
        if (
            not isinstance(self.coordinates, tuple)
            or not self.coordinates
            or any(
                not isinstance(value, str)
                or not value.startswith("component://")
                or any(ord(character) < 33 for character in value)
                for value in self.coordinates
            )
            or self.coordinates != tuple(sorted(set(self.coordinates)))
        ):
            raise ValueError("revision component coordinates must be canonical")
        for coordinate in self.coordinates:
            if ComponentCoordinate.parse(coordinate).uri != coordinate:
                raise ValueError("revision requires exact component coordinates")
        _identities(self.authorities)
        _identities(self.evidence)
        if not len(self.coordinates) == len(self.authorities) == len(self.evidence):
            raise ValueError("revision must bind every qualified component")

    def to_dict(self) -> dict[str, object]:
        return {
            "child": self.child,
            "project_id": self.project_id,
            "definition_identity": self.definition.uri,
            "receipt_identity": self.receipt.uri,
            "tree_identity": self.tree.uri,
            "coordinates": list(self.coordinates),
            "authority_identities": [value.uri for value in self.authorities],
            "evidence": [value.uri for value in self.evidence],
        }

    @classmethod
    def from_dict(cls, value: object) -> QualifiedNativeChildSnapshot:
        if not isinstance(value, dict):
            raise ValueError("revision snapshot must be an object")
        try:
            identity = ContentIdentity.parse_uri
            snapshot = cls(
                child=value["child"],
                project_id=value["project_id"],
                definition=identity(value["definition_identity"]),
                receipt=identity(value["receipt_identity"]),
                tree=identity(value["tree_identity"]),
                coordinates=tuple(value["coordinates"]),
                authorities=tuple(identity(v) for v in value["authority_identities"]),
                evidence=tuple(identity(v) for v in value["evidence"]),
            )
            if value != snapshot.to_dict():
                raise ValueError("revision snapshot is changed or noncanonical")
            return snapshot
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError("revision snapshot is invalid") from exc


@dataclass(frozen=True)
class QualifiedNativeChildRevisionPlan:
    SCHEMA: ClassVar[str] = "literate-ai/qualified-native-child-revision-plan@1"

    parent_definition: ContentIdentity
    parent_authority: ContentIdentity
    parent_receipt: ContentIdentity
    registry: ContentIdentity
    previous: QualifiedNativeChildSnapshot
    replacement: QualifiedNativeChildSnapshot
    expected_evidence: tuple[ContentIdentity, ...]

    def __post_init__(self) -> None:
        if not all(
            isinstance(value, ContentIdentity)
            for value in (
                self.parent_definition,
                self.parent_authority,
                self.parent_receipt,
                self.registry,
            )
        ) or not all(
            isinstance(value, QualifiedNativeChildSnapshot)
            for value in (self.previous, self.replacement)
        ):
            raise ValueError("revision plan requires typed exact identities")
        if (
            self.previous.child == self.replacement.child
            or self.previous.project_id != self.replacement.project_id
            or self.previous.coordinates != self.replacement.coordinates
            or self.previous.evidence == self.replacement.evidence
        ):
            raise ValueError(
                "revision must preserve logical identity and change evidence"
            )
        _identities(self.expected_evidence)
        if not set(self.replacement.evidence).issubset(self.expected_evidence):
            raise ValueError("revision must retain replacement qualification")

    def _payload(self) -> dict[str, object]:
        return {
            "schema": self.SCHEMA,
            "writes": False,
            "parent_definition_identity": self.parent_definition.uri,
            "parent_authority_identity": self.parent_authority.uri,
            "parent_receipt_identity": self.parent_receipt.uri,
            "registry_identity": self.registry.uri,
            "previous": self.previous.to_dict(),
            "replacement": self.replacement.to_dict(),
            "expected_evidence": [value.uri for value in self.expected_evidence],
        }

    @property
    def identity(self) -> ContentIdentity:
        return canonical_identity(self._payload())

    def to_dict(self) -> dict[str, object]:
        return {**self._payload(), "plan_identity": self.identity.uri}

    @classmethod
    def from_dict(cls, value: object) -> QualifiedNativeChildRevisionPlan:
        if not isinstance(value, dict):
            raise ValueError("revision plan must be an object")
        try:
            identity = ContentIdentity.parse_uri
            plan = cls(
                parent_definition=identity(value["parent_definition_identity"]),
                parent_authority=identity(value["parent_authority_identity"]),
                parent_receipt=identity(value["parent_receipt_identity"]),
                registry=identity(value["registry_identity"]),
                previous=QualifiedNativeChildSnapshot.from_dict(value["previous"]),
                replacement=QualifiedNativeChildSnapshot.from_dict(
                    value["replacement"]
                ),
                expected_evidence=tuple(
                    identity(v) for v in value["expected_evidence"]
                ),
            )
            if value != plan.to_dict() or value.get("writes") is not False:
                raise ValueError("revision plan is changed or noncanonical")
            return plan
        except (KeyError, TypeError, AttributeError) as exc:
            raise ValueError("revision plan is invalid") from exc
