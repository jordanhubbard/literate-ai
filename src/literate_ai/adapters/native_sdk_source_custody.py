"""Scoped SDK source links composed with the regular-only project input owner."""

from __future__ import annotations

from pathlib import Path

from literate_ai.contracts import SourceEntry, SourceEntryType
from literate_ai.projects import PinnedInputClosure
from literate_ai.sources.internal_links import read_source_entry, validate_source_links

_MAX_FILES = 1_000_000
_MAX_FILE_BYTES = 1024 * 1024 * 1024
_MAX_TOTAL_BYTES = 16 * 1024 * 1024 * 1024


class NativeSdkSourceInputClosure:
    """Exact link custody, never a relaxation of general project input pinning."""

    def __init__(self, root: Path, entries: tuple[SourceEntry, ...]) -> None:
        self.root = root.absolute()
        if self.root != self.root.resolve(strict=True):
            raise ValueError("SDK source root is redirected")
        self.entries = entries
        if len(entries) > _MAX_FILES or sum(e.size for e in entries) > _MAX_TOTAL_BYTES:
            raise ValueError("SDK source inputs exceed the finite source budget")
        if any(e.size > _MAX_FILE_BYTES for e in entries):
            raise ValueError("SDK source input exceeds the per-file source budget")
        if any(
            e.entry_type not in (SourceEntryType.FILE, SourceEntryType.SYMLINK)
            for e in entries
        ):
            raise ValueError("SDK source closure contains an unsupported entry kind")
        self._by_path = {entry.path: entry for entry in entries}
        self._links = tuple(
            e for e in entries if e.entry_type is SourceEntryType.SYMLINK
        )
        targets = {e.path: self.target_bytes(e).decode("utf-8") for e in self._links}
        self._resolved = validate_source_links(entries, targets)
        self.file_aliases = tuple(
            sorted(
                (name, target)
                for name, target in self._resolved.items()
                if target in self._by_path
                and self._by_path[target].entry_type is SourceEntryType.FILE
            )
        )
        # File aliases can change scanner language selection. Charge the bytes
        # inspected under every observable alias, rather than silently omitting
        # code or allowing a small link inventory to expand without bound.
        expanded = sum(e.size for e in entries if e.entry_type is SourceEntryType.FILE)
        expanded += sum(self._by_path[target].size for _, target in self.file_aliases)
        if expanded > _MAX_TOTAL_BYTES:
            raise ValueError("SDK file-alias scan expansion exceeds the source budget")
        link_bytes = sum(e.size for e in self._links)
        self._regular = PinnedInputClosure(
            maximum_files=_MAX_FILES - len(self._links),
            maximum_file_bytes=_MAX_FILE_BYTES,
            maximum_total_bytes=_MAX_TOTAL_BYTES - link_bytes,
        )

    def pin(self, *args, **kwargs) -> bytes:
        return self._regular.pin(*args, **kwargs)

    def target_bytes(self, entry: SourceEntry) -> bytes:
        if (
            self._by_path.get(entry.path) != entry
            or entry.entry_type is not SourceEntryType.SYMLINK
        ):
            raise ValueError("SDK link is outside the actual captured source")
        digest, size, data = read_source_entry(self.root, entry.path, symlink=True)
        if entry.mode != 0o777 or size != entry.size or digest != entry.identity.digest:
            raise ValueError("SDK source link differs from its exact capture")
        return data

    def require_unchanged(self) -> None:
        self._regular.require_unchanged()
        targets = {e.path: self.target_bytes(e).decode("utf-8") for e in self._links}
        if validate_source_links(self.entries, targets) != self._resolved:
            raise ValueError("SDK source link closure changed")
