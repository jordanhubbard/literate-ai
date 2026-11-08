"""Read-only physical and operator selection inputs for qualified-child plans."""

from __future__ import annotations

import hashlib
import os
import stat
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from literate_ai._filesystem import require_safe_directory, stat_is_link_or_reparse
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.paths import canonical_relative_posix_path


class QualifiedNativeChildError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        self.code = "native_child." + code
        self.message = message
        super().__init__(message)


def refuse(code: str, message: str) -> None:
    raise QualifiedNativeChildError(code, message)


def physical_node(node: os.stat_result) -> tuple[int, ...]:
    return (
        node.st_dev,
        node.st_ino,
        node.st_mode,
        node.st_nlink,
        node.st_size,
        node.st_mtime_ns,
        node.st_ctime_ns,
        node.st_uid,
        node.st_gid,
    )


def directory_node(path: Path) -> tuple[int, int, int]:
    require_safe_directory(path)
    node = path.lstat()
    return node.st_dev, node.st_ino, node.st_mode


def portable_key(value: str) -> str:
    return unicodedata.normalize("NFC", value.casefold())


@dataclass(frozen=True, slots=True)
class ChildCaptureLimits:
    maximum_children: int = 128
    maximum_components: int = 256
    maximum_tree_entries: int = 131072
    maximum_file_bytes: int = 1024 * 1024 * 1024
    maximum_tree_bytes: int = 16 * 1024 * 1024 * 1024
    maximum_metadata_bytes: int = 64 * 1024 * 1024
    maximum_plan_bytes: int = 16 * 1024 * 1024

    def __post_init__(self) -> None:
        upper = {
            "maximum_children": 4096,
            "maximum_components": 65536,
            "maximum_tree_entries": 1048576,
            "maximum_file_bytes": 2**50,
            "maximum_tree_bytes": 2**50,
            "maximum_metadata_bytes": 2**30,
            "maximum_plan_bytes": 64 * 1024 * 1024,
        }
        for name, maximum in upper.items():
            if (
                type(getattr(self, name)) is not int
                or not 1 <= getattr(self, name) <= maximum
            ):
                refuse(
                    "capture_limits_invalid",
                    "capture limits must be finite positive bounded integers",
                )
        if self.maximum_file_bytes > self.maximum_tree_bytes:
            refuse(
                "capture_limits_invalid",
                "a file budget cannot exceed the complete tree budget",
            )

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class ChildQualificationSelection:
    project: str
    component: str
    target: str
    provider: str
    profile: str
    model: str | None = None
    flavors: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if (
            not isinstance(self.flavors, (tuple, list))
            or any(
                not isinstance(value, str) or not value or len(value) > 256
                for value in self.flavors
            )
            or len(self.flavors) > 64
        ):
            refuse(
                "selection_invalid", "Flavor selectors must be bounded explicit strings"
            )
        object.__setattr__(self, "flavors", tuple(self.flavors))
        if self.project != ".":
            child_relative_path(self.project)
        for name in ("component", "profile"):
            if name == "component" and getattr(self, name) == ".":
                continue
            canonical_relative_posix_path(getattr(self, name), label="child " + name)
        for name in ("target", "provider"):
            value = getattr(self, name)
            if (
                not isinstance(value, str)
                or not value.strip()
                or len(value) > 256
                or any(ord(c) < 32 for c in value)
            ):
                refuse(
                    "selection_invalid",
                    "qualification names must be bounded nonempty strings",
                )
        if self.model is not None and (
            not isinstance(self.model, str)
            or not self.model.strip()
            or len(self.model) > 512
            or any(ord(c) < 32 for c in self.model)
        ):
            refuse(
                "selection_invalid",
                "model selection must be one bounded logical model name",
            )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def child_relative_path(value: str) -> PurePosixPath:
    path = canonical_relative_posix_path(value, label="native child")
    if path.parent != PurePosixPath(".literate/native-projects"):
        refuse(
            "path_invalid",
            "a native child must be a direct .literate/native-projects child",
        )
    return path


def read_qualification_selection(
    value: object,
) -> tuple[tuple[ChildQualificationSelection, ...], ChildCaptureLimits]:
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "components", "limits"}
        or value["schema"] != "literate-ai/native-child-qualification-selection@1"
        or not isinstance(value["components"], list)
        or not isinstance(value["limits"], dict)
        or set(value["limits"]) - set(ChildCaptureLimits.__dataclass_fields__)
    ):
        refuse(
            "selection_invalid",
            "qualification selection must use the closed versioned contract",
        )
    limits = ChildCaptureLimits(**value["limits"])
    if not 1 <= len(value["components"]) <= limits.maximum_components:
        refuse(
            "selection_invalid", "qualification selection exceeds its Component budget"
        )
    result = []
    for item in value["components"]:
        if not isinstance(item, dict) or set(item) != set(
            ChildQualificationSelection.__dataclass_fields__
        ):
            refuse(
                "selection_invalid",
                "each qualification selection must name all current inputs",
            )
        result.append(ChildQualificationSelection(**item))
    keys = [(portable_key(x.project), portable_key(x.component)) for x in result]
    if len(set(keys)) != len(keys):
        refuse(
            "selection_invalid",
            "qualification selections duplicate or alias a Component",
        )
    return tuple(sorted(result, key=lambda x: (x.project, x.component))), limits


def capture_child_tree(root: Path, limits: ChildCaptureLimits) -> dict[str, object]:
    """Stream every direct physical node into a bounded commitment, without pruning.

    A link or special node refuses rather than silently omitting an alternate tree.
    No blob bytes are retained in memory. Capture limits are reviewed plan inputs.
    """
    root = Path(root).absolute()
    root_key = directory_node(root)
    digest = hashlib.sha256()
    count = total = metadata = 0

    def charge(relative: str):
        nonlocal count, metadata
        count += 1
        # Reserve conservative Python/path/list overhead before retaining a name.
        metadata += 1024 + 8 * len(relative.encode("utf-8"))
        if (
            count > limits.maximum_tree_entries
            or metadata > limits.maximum_metadata_bytes
        ):
            refuse(
                "tree_limit",
                "physical child metadata exceeds the reviewed capture budget",
            )

    def visit(directory: Path, relative: PurePosixPath, depth: int):
        nonlocal total
        if depth > 128:
            refuse("tree_limit", "physical child tree exceeds the supported depth")
        expected = directory_node(directory)
        names = []
        with os.scandir(directory) as entries:
            for entry in entries:
                name = (relative / entry.name).as_posix()
                charge(name)
                canonical_relative_posix_path(name, label="physical child node")
                names.append(entry.name)
        if len({portable_key(name) for name in names}) != len(names):
            refuse(
                "tree_alias", "physical child names collide under portable comparison"
            )
        for name in sorted(names):
            path = directory / name
            location = (relative / name).as_posix()
            before = path.lstat()
            if stat_is_link_or_reparse(before):
                refuse(
                    "tree_unsafe",
                    "physical child capture refuses links and reparse nodes",
                )
            record = {"path": location, "node": physical_node(before)}
            if stat.S_ISDIR(before.st_mode):
                record["kind"] = "directory"
                digest.update(canonical_json_bytes(record) + b"\n")
                visit(path, relative / name, depth + 1)
                if physical_node(path.lstat()) != physical_node(before):
                    refuse(
                        "tree_changed",
                        "physical child directory changed while capturing",
                    )
            elif stat.S_ISREG(before.st_mode):
                total += before.st_size
                if (
                    before.st_size > limits.maximum_file_bytes
                    or total > limits.maximum_tree_bytes
                ):
                    refuse(
                        "tree_limit",
                        "physical child bytes exceed the reviewed capture budget",
                    )
                fd = os.open(
                    path,
                    os.O_RDONLY
                    | getattr(os, "O_NOFOLLOW", 0)
                    | getattr(os, "O_NONBLOCK", 0)
                    | getattr(os, "O_BINARY", 0),
                )
                try:
                    opened = os.fstat(fd)
                    if physical_node(opened) != physical_node(
                        before
                    ) or not stat.S_ISREG(opened.st_mode):
                        refuse(
                            "tree_changed", "physical child file changed before capture"
                        )
                    content = hashlib.sha256()
                    size = 0
                    while size <= before.st_size:
                        chunk = os.read(fd, min(65536, before.st_size + 1 - size))
                        if not chunk:
                            break
                        size += len(chunk)
                        content.update(chunk)
                    if (
                        size != before.st_size
                        or physical_node(os.fstat(fd)) != physical_node(before)
                        or physical_node(path.lstat()) != physical_node(before)
                    ):
                        refuse(
                            "tree_changed",
                            "physical child file changed while capturing",
                        )
                    record.update(kind="file", identity="sha256:" + content.hexdigest())
                    digest.update(canonical_json_bytes(record) + b"\n")
                finally:
                    os.close(fd)
            else:
                refuse(
                    "tree_unsafe",
                    "physical child capture requires direct files and directories",
                )
        if directory_node(directory) != expected:
            refuse(
                "tree_changed", "physical child directory was replaced while capturing"
            )
        # A bounded second namespace pass detects concurrent additions/removals.
        observed = []
        with os.scandir(directory) as entries:
            for index, entry in enumerate(entries):
                if index >= len(names):
                    refuse(
                        "tree_changed",
                        "physical child membership changed while capturing",
                    )
                observed.append(entry.name)
        if sorted(observed) != sorted(names):
            refuse("tree_changed", "physical child membership changed while capturing")

    visit(root, PurePosixPath(), 0)
    if directory_node(root) != root_key:
        refuse("tree_changed", "physical child root changed while capturing")
    return {
        "root_node": root_key,
        "entries": count,
        "bytes": total,
        "identity": canonical_identity(
            {
                "domain": "literate-ai/native-child-physical-tree/1",
                "root_node": root_key,
                "entries": count,
                "bytes": total,
                "nodes_sha256": digest.hexdigest(),
            }
        ).uri,
    }
