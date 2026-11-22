"""Inert bounded Python workspace descriptions, never import or writer rights."""

from dataclasses import dataclass
from typing import ClassVar

from ._validation import fail, fields, int_value
from .blobs import BlobRef
from .identity import ContentIdentity
from .paths import canonical_relative_posix_path


@dataclass(frozen=True, slots=True)
class RetainedPythonWorkspaceBudget:
    maximum_packages: int
    maximum_files: int
    maximum_entries: int
    maximum_file_bytes: int
    maximum_total_bytes: int
    maximum_metadata_bytes: int

    LIMITS: ClassVar[dict[str, int]] = {
        "maximum_packages": 1024,
        "maximum_files": 200000,
        "maximum_entries": 4000000,
        "maximum_file_bytes": 256 * 1024**2,
        "maximum_total_bytes": 4 * 1024**3,
        "maximum_metadata_bytes": 1024**3,
    }

    def __post_init__(self):
        for name, ceiling in self.LIMITS.items():
            int_value(
                getattr(self, name),
                type(self).__name__ + "." + name,
                minimum=1,
                maximum=ceiling,
            )
        if (
            self.maximum_files > self.maximum_entries
            or self.maximum_file_bytes > self.maximum_total_bytes
            or self.maximum_total_bytes > self.maximum_files * self.maximum_file_bytes
        ):
            fail(type(self).__name__, "requires consistent finite allowances")

    def to_dict(self):
        return {name: getattr(self, name) for name in self.LIMITS}

    @classmethod
    def from_dict(cls, value):
        data = fields(value, path=cls.__name__, required=frozenset(cls.LIMITS))
        return cls(*(data[name] for name in cls.LIMITS))


@dataclass(frozen=True, slots=True)
class RetainedPythonExportMount:
    """Exact library export and whole original artifact, before any installation.

    import_root is relative to this export's declared private destination. Wheel
    runtime metadata refers to the original qualified dependency manifest, not a
    new artifact-local authority. The current provider join must prove all bytes.
    """

    export_identity: ContentIdentity
    artifact_tree_identity: ContentIdentity
    profile: str
    import_root: str
    runtime_manifest: BlobRef | None

    FIELDS: ClassVar[frozenset[str]] = frozenset(
        {
            "export_identity",
            "artifact_tree_identity",
            "profile",
            "import_root",
            "runtime_manifest",
        }
    )

    def __post_init__(self):
        for value in (self.export_identity, self.artifact_tree_identity):
            if type(value) is not ContentIdentity:
                fail(
                    type(self).__name__, "requires exact export and artifact identities"
                )
        if type(self.profile) is not str or self.profile not in ("source", "wheel"):
            fail(type(self).__name__, "requires an explicit source or wheel profile")
        if type(self.import_root) is not str or not 1 <= len(self.import_root) <= 128:
            fail(type(self).__name__, "requires a short explicit relative import root")
        if self.import_root != ".":
            canonical_relative_posix_path(self.import_root, label="Python import root")
        if self.runtime_manifest is not None and (
            type(self.runtime_manifest) is not BlobRef
            or self.runtime_manifest.media_type != "application/json"
            or not 0 < self.runtime_manifest.size <= 16 * 1024**2
        ):
            fail(type(self).__name__, "requires exact bounded runtime metadata")
        if self.profile == "wheel" and self.runtime_manifest is None:
            fail(
                type(self).__name__, "wheel profile requires original runtime metadata"
            )

    def to_dict(self):
        return {
            "export_identity": self.export_identity.to_dict(),
            "artifact_tree_identity": self.artifact_tree_identity.to_dict(),
            "profile": self.profile,
            "import_root": self.import_root,
            "runtime_manifest": self.runtime_manifest.to_dict()
            if self.runtime_manifest
            else None,
        }

    @classmethod
    def from_dict(cls, value):
        data = fields(value, path=cls.__name__, required=cls.FIELDS)
        return cls(
            ContentIdentity.from_dict(data["export_identity"]),
            ContentIdentity.from_dict(data["artifact_tree_identity"]),
            data["profile"],
            data["import_root"],
            BlobRef.from_dict(data["runtime_manifest"])
            if data["runtime_manifest"] is not None
            else None,
        )


@dataclass(frozen=True, slots=True)
class RetainedPythonSourceChange:
    """Implementation-relative prospective source/metadata delta; None is absence."""

    path: str
    before: BlobRef | None
    after: BlobRef | None

    def __post_init__(self):
        canonical_relative_posix_path(self.path, label="Python source change")
        if len(self.path) > 128 or self.before is self.after is None:
            fail(type(self).__name__, "requires a short existing or prospective file")
        for value in (self.before, self.after):
            if value is not None and type(value) is not BlobRef:
                fail(type(self).__name__, "requires exact file byte references")

    def to_dict(self):
        return {
            "path": self.path,
            "before": self.before.to_dict() if self.before is not None else None,
            "after": self.after.to_dict() if self.after is not None else None,
        }

    @classmethod
    def from_dict(cls, value):
        data = fields(
            value, path=cls.__name__, required=frozenset({"path", "before", "after"})
        )
        return cls(
            data["path"],
            *(
                BlobRef.from_dict(data[key]) if data[key] is not None else None
                for key in ("before", "after")
            ),
        )
