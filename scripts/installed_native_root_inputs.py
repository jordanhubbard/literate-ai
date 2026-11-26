"""Explicit immutable TEST/native inputs for the two installed native release cells.

This does not install, execute native tools, grant execution, or infer qualification.
Both wheel owner and isolated installed fixture use the same closed input codec.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import stat
from contextlib import contextmanager
from pathlib import Path, PurePosixPath

SCHEMA = "literate-ai/installed-native-root-fixture-inputs@1"
MODES = ("consumer", "late-first")
# Separate NEW mode transports: qualify12600 + setup/reopen4800, + B2400.
MODE_TRANSPORT_SECONDS = {"consumer": 19800, "late-first": 17400}


def identity(value):
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def _native_census_supported():
    if (
        os.name != "posix"
        or not getattr(os, "O_NOFOLLOW", 0)
        or not getattr(os, "O_DIRECTORY", 0)
        or os.open not in os.supports_dir_fd
        or os.scandir not in os.supports_fd
    ):
        raise ValueError("native no-follow census is unsupported on this platform")


def _directory_path(value):
    path = Path(value)
    if (
        not path.is_absolute()
        or ".." in path.parts
        or len(path.parts) > 65
        or len(str(path).encode("utf-8")) > 4096
    ):
        raise ValueError("bounded explicit absolute native fixture directory required")
    if os.name == "nt" and path.drive.startswith("\\"):
        raise ValueError("selected fixture census requires an explicit local drive")
    return path


def _close_owned(descriptors, primary):
    first = None
    for descriptor in reversed(descriptors):
        try:
            os.close(descriptor)
        except BaseException as error:
            if primary is not None:
                BaseException.add_note(
                    primary,
                    "closing native census descriptor failed: " + type(error).__name__,
                )
            elif first is None:
                first = error
            else:
                BaseException.add_note(
                    first,
                    "closing another native descriptor failed: " + type(error).__name__,
                )
    if primary is None and first is not None:
        raise first


@contextmanager
def _directory_descriptor(value):
    _native_census_supported()
    path = _directory_path(value)
    descriptors, primary = [], None
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
    try:
        try:
            descriptors.append(os.open(path.anchor, flags))
            for part in path.parts[1:]:
                descriptors.append(os.open(part, flags, dir_fd=descriptors[-1]))
                if not stat.S_ISDIR(os.fstat(descriptors[-1]).st_mode):
                    raise ValueError("fixture directory component is not native")
        except OSError as error:
            raise ValueError(
                "native fixture directory is unavailable or aliased"
            ) from error
        yield descriptors[-1]
    except BaseException as error:
        primary = error
        raise
    finally:
        _close_owned(descriptors, primary)


def real_directory(value):
    path = _directory_path(value)
    if os.name == "nt":
        from literate_ai.adapters.qualification_workspace_namespace import (
            hold_qualification_workspace_namespace,
        )

        with hold_qualification_workspace_namespace(path, read_only=True):
            pass
    else:
        with _directory_descriptor(path):
            pass
    return path


def _directory_identity(metadata):
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_mtime_ns,
        metadata.st_ctime_ns,
    )


def bounded_census(
    root,
    *,
    suffix,
    maximum_entries,
    maximum_namespace_bytes,
    maximum_depth=64,
    maximum_path_bytes=768,
):
    """Stream native fd-relative entries; count EVERY name before metadata/descent.

    Sorting happens only AFTER the complete namespace fits its finite budgets.
    No path-based scandir/rglob, link following, or Windows atomicity is implied.
    """
    for value in (
        maximum_entries,
        maximum_namespace_bytes,
        maximum_depth,
        maximum_path_bytes,
    ):
        if type(value) is not int or value <= 0:
            raise ValueError("positive finite native census budgets required")
    root = _directory_path(root)
    if os.name == "nt":
        return _windows_bounded_census(
            root,
            suffix=suffix,
            maximum_entries=maximum_entries,
            maximum_namespace_bytes=maximum_namespace_bytes,
            maximum_depth=maximum_depth,
            maximum_path_bytes=maximum_path_bytes,
        )
    selected, namespace = [], []
    used_entries = used_bytes = 0
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    flags |= getattr(os, "O_CLOEXEC", 0)

    def walk(descriptor, parts, depth):
        nonlocal used_entries, used_bytes
        before_directory = os.fstat(descriptor)
        with os.scandir(descriptor) as entries:
            for entry in entries:
                used_entries += 1
                if used_entries > maximum_entries:
                    raise ValueError("native fixture entry budget exceeded")
                if (
                    type(entry.name) is not str
                    or entry.name in {"", ".", ".."}
                    or "/" in entry.name
                ):
                    raise ValueError("native fixture entry name invalid")
                relative = "/".join((*parts, entry.name))
                size = len(relative.encode("utf-8"))
                used_bytes += size
                if size > maximum_path_bytes or used_bytes > maximum_namespace_bytes:
                    raise ValueError("native fixture namespace byte budget exceeded")
                observed = os.stat(entry.name, dir_fd=descriptor, follow_symlinks=False)
                if stat.S_ISDIR(observed.st_mode):
                    if depth >= maximum_depth:
                        raise ValueError("native fixture directory depth exceeded")
                    namespace.append((relative, "directory"))
                    child = os.open(entry.name, flags, dir_fd=descriptor)
                    primary = None
                    try:
                        if _directory_identity(os.fstat(child)) != _directory_identity(
                            observed
                        ):
                            raise ValueError(
                                "native fixture directory changed before descent"
                            )
                        walk(child, (*parts, entry.name), depth + 1)
                        current = os.stat(
                            entry.name, dir_fd=descriptor, follow_symlinks=False
                        )
                        if _directory_identity(current) != _directory_identity(
                            observed
                        ):
                            raise ValueError(
                                "native fixture directory changed during descent"
                            )
                    except BaseException as error:
                        primary = error
                        raise
                    finally:
                        _close_owned((child,), primary)
                elif stat.S_ISREG(observed.st_mode):
                    namespace.append((relative, "file"))
                    if suffix is None or entry.name.endswith(suffix):
                        selected.append(root / relative)
                else:
                    raise ValueError(
                        "native fixture census refuses aliases/special files"
                    )
        if _directory_identity(os.fstat(descriptor)) != _directory_identity(
            before_directory
        ):
            raise ValueError("native fixture namespace changed during enumeration")

    with _directory_descriptor(root) as descriptor:
        walk(descriptor, (), 0)
    return tuple(sorted(selected)), tuple(sorted(namespace))


TEST_CENSUS_LIMITS = {"maximum_entries": 8000, "maximum_namespace_bytes": 2 * 1024**2}
ASSET_CENSUS_LIMITS = {"maximum_entries": 2048, "maximum_namespace_bytes": 1024**2}


def _subject_census(repository):
    # Both roots/ancestors are opened natively BEFORE either namespace enumerates.
    tests_root = real_directory(repository / "tests")
    assets_root = real_directory(repository / "skills/source-to-specification")
    tests, test_namespace = bounded_census(
        tests_root, suffix=".py", **TEST_CENSUS_LIMITS
    )
    assets, asset_namespace = bounded_census(
        assets_root, suffix=None, **ASSET_CENSUS_LIMITS
    )
    return tests, assets, test_namespace, asset_namespace


class NativeRootFixturePins:
    """Original file closure AND selected authoring/test directory membership."""

    __slots__ = ("_pins", "_repository", "_test_namespace", "_asset_namespace")

    def __init__(self, pins, repository, test_namespace, asset_namespace):
        self._pins, self._repository = pins, repository
        self._test_namespace, self._asset_namespace = test_namespace, asset_namespace

    def require_unchanged(self):
        # Validate/census namespace natively FIRST; never ask another reader to
        # examine a now-aliased selected root before this refusal.
        _tests, _assets, tests, assets = _subject_census(self._repository)
        if tests != self._test_namespace or assets != self._asset_namespace:
            raise ValueError("original native fixture subject membership changed")
        self._pins.require_unchanged()

    def pin(self, *arguments, **options):
        return self._pins.pin(*arguments, **options)


def capture_inputs(repository, archive_directory):
    """Return closed data and the ORIGINAL byte-custody closure; never cache success."""
    from literate_ai.projects import PinnedInputClosure

    repository = real_directory(repository)
    archive_directory = real_directory(archive_directory)
    pins = PinnedInputClosure(
        maximum_files=8192,
        maximum_file_bytes=8 * 1024**2,
        maximum_total_bytes=256 * 1024**2,
    )
    test_paths, asset_paths, test_namespace, asset_namespace = _subject_census(
        repository
    )
    tests = {}
    for path in test_paths:
        relative = path.relative_to(repository).as_posix()
        payload = pins.pin(
            path, boundary=repository, label="native-fixture:" + relative
        )
        tests[relative] = hashlib.sha256(payload).hexdigest()
    assets = {}
    for path in asset_paths:
        relative = path.relative_to(repository).as_posix()
        payload = pins.pin(
            path, boundary=repository, label="authoring-asset:" + relative
        )
        assets[relative] = hashlib.sha256(payload).hexdigest()
    if not assets:
        raise ValueError("actual public source-to-specification assets required")
    helpers = {}
    for name in (
        "scripts/installed_native_root_inputs.py",
        "tests/support/installed_public_qualified_native_journey.py",
    ):
        payload = pins.pin(repository / name, boundary=repository, label=name)
        helpers[name] = hashlib.sha256(payload).hexdigest()
    declaration = repository / "tests/support/fixtures_rust_harness_vendor.py"
    raw = pins.pin(declaration, boundary=repository, label="canonical-upstream-crates")
    constants = [
        node.value
        for node in ast.parse(raw).body
        if isinstance(node, ast.Assign)
        and any(
            isinstance(target, ast.Name) and target.id == "CRATES"
            for target in node.targets
        )
    ]
    if len(constants) != 1:
        raise ValueError("one canonical upstream crate inventory required")
    crates = ast.literal_eval(constants[0])
    if type(crates) is not dict or len(crates) != 11:
        raise ValueError("exact eleven upstream fixture archives required")
    archives = {}
    for name, expectation in sorted(crates.items()):
        if (
            type(name) is not str
            or not name
            or any(
                character not in "abcdefghijklmnopqrstuvwxyz0123456789_-."
                for character in name
            )
            or type(expectation) is not tuple
            or len(expectation) != 2
        ):
            raise ValueError("closed upstream archive declaration required")
        size, digest = expectation
        if (
            type(size) is not int
            or not 0 < size <= 8 * 1024**2
            or (
                type(digest) is not str
                or len(digest) != 64
                or any(character not in "0123456789abcdef" for character in digest)
            )
        ):
            raise ValueError("bounded upstream size/hash required")
        payload = pins.pin(
            archive_directory / (name + ".crate"),
            boundary=archive_directory,
            label="upstream:" + name,
        )
        if len(payload) != size or hashlib.sha256(payload).hexdigest() != digest:
            raise ValueError("canonical upstream fixture archive differs")
        archives[name + ".crate"] = {"size": size, "sha256": digest}
    record = {
        "schema": SCHEMA,
        "modes": list(MODES),
        "test_python": tests,
        "test_python_identity": identity(tests),
        "test_python_members": len(tests),
        "helpers": helpers,
        "authoring_assets": assets,
        "authoring_assets_identity": identity(assets),
        "archives": archives,
    }
    record["identity"] = identity(record)
    guarded = NativeRootFixturePins(pins, repository, test_namespace, asset_namespace)
    guarded.require_unchanged()
    return record, guarded


def stage_inputs(repository, archive_directory, destination, *, inputs, pins):
    """Copy ONLY exact original-pinned TEST/data bytes to a fresh private owner."""
    repository, archive_directory = (
        real_directory(repository),
        real_directory(archive_directory),
    )
    destination = Path(destination)
    real_directory(destination.parent)
    if not destination.is_absolute() or os.path.lexists(destination):
        raise ValueError("fresh owned fixture snapshot required")
    if (
        identity({name: value for name, value in inputs.items() if name != "identity"})
        != inputs["identity"]
    ):
        raise ValueError("original fixture input declaration changed")
    pins.require_unchanged()
    payloads = {}
    for relative, digest in {
        **inputs["test_python"],
        **inputs["authoring_assets"],
        **inputs["helpers"],
    }.items():
        path = PurePosixPath(relative)
        if (
            path.is_absolute()
            or not path.parts
            or ".." in path.parts
            or path.parts[0] not in {"tests", "skills", "scripts"}
            or path.as_posix() != relative
        ):
            raise ValueError("only closed relative test/asset/script inputs may stage")
        payloads[relative] = pins.pin(
            repository / relative,
            boundary=repository,
            label="staged-original:" + relative,
            expected_identity="sha256:" + digest,
        )
    for name, record in inputs["archives"].items():
        payloads["archives/" + name] = pins.pin(
            archive_directory / name,
            boundary=archive_directory,
            label="staged-upstream:" + name,
            expected_identity="sha256:" + record["sha256"],
        )
    pins.require_unchanged()
    destination.mkdir(mode=0o700)
    for relative, content in sorted(payloads.items()):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        descriptor = os.open(target, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
    pins.require_unchanged()
    observed, snapshot_pins = capture_inputs(destination, destination / "archives")
    if observed != inputs:
        raise ValueError("owned fixture snapshot differs from original input subject")
    snapshot_pins.require_unchanged()
    return destination, snapshot_pins


def _windows_bounded_census(
    root,
    *,
    suffix,
    maximum_entries,
    maximum_namespace_bytes,
    maximum_depth,
    maximum_path_bytes,
):
    """Enumerate only while ORIGINAL read-only native name custody is held."""
    from literate_ai.adapters.qualification_workspace_namespace import (
        hold_qualification_workspace_namespace,
    )

    selected, namespace = [], []
    used_entries = used_bytes = 0

    def walk(path, parts, depth):
        nonlocal used_entries, used_bytes
        with hold_qualification_workspace_namespace(path, read_only=True) as current:
            current()
            before = path.lstat()
            with os.scandir(path) as entries:
                for entry in entries:
                    used_entries += 1
                    if used_entries > maximum_entries:
                        raise ValueError("native fixture entry budget exceeded")
                    if (
                        type(entry.name) is not str
                        or entry.name in {"", ".", ".."}
                        or "/" in entry.name
                        or "\\" in entry.name
                    ):
                        raise ValueError("native fixture entry name invalid")
                    relative = "/".join((*parts, entry.name))
                    size = len(relative.encode("utf-8"))
                    used_bytes += size
                    if (
                        size > maximum_path_bytes
                        or used_bytes > maximum_namespace_bytes
                    ):
                        raise ValueError(
                            "native fixture namespace byte budget exceeded"
                        )
                    child = path / entry.name
                    observed = child.lstat()
                    if (
                        getattr(observed, "st_file_attributes", 0)
                        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
                    ) or stat.S_ISLNK(observed.st_mode):
                        raise ValueError(
                            "native fixture census refuses reparse/alias entries"
                        )
                    if stat.S_ISDIR(observed.st_mode):
                        if depth >= maximum_depth:
                            raise ValueError("native fixture directory depth exceeded")
                        namespace.append((relative, "directory"))
                        walk(child, (*parts, entry.name), depth + 1)
                        current()
                    elif stat.S_ISREG(observed.st_mode):
                        namespace.append((relative, "file"))
                        if suffix is None or entry.name.endswith(suffix):
                            selected.append(child)
                    else:
                        raise ValueError(
                            "native fixture census refuses special entries"
                        )
            current()
            after = path.lstat()
            # Native IDs come from the ORIGINAL owner. These are mutation
            # stamps only, never substitute Python st_ino for Windows file IDs.
            if (before.st_mode, before.st_mtime_ns, before.st_ctime_ns) != (
                after.st_mode,
                after.st_mtime_ns,
                after.st_ctime_ns,
            ):
                raise ValueError("native fixture namespace changed during enumeration")
            current()

    walk(root, (), 0)
    return tuple(sorted(selected)), tuple(sorted(namespace))
