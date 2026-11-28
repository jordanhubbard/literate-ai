"""Bound original materialization metadata before filesystem capture.

The caller reserves MAXIMUM_FILE_METADATA_BYTES before this factory. File content
remains separately charged by the live capture owner. This returns detached DATA,
not a filesystem observation, admission, phase membership or execution authority.
"""

from pathlib import Path

from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.node_sdk_verifier_compiler_witness import _read_slots
from literate_ai.contracts.paths import canonical_relative_posix_paths

MAXIMUM_FILE_METADATA_BYTES = 32 * 1024 * 1024
_MAXIMUM_FILES = 16384
_MAXIMUM_DEPTH = 64
_MAXIMUM_DERIVED_ROWS = 65536


def _row_charge(characters, depth):
    # Covers path/string/part storage, original stamp integers/tuples, and entries
    # in construction and retained dictionaries/sets (including move top_names).
    # Repeated ancestor paths are charged repeatedly rather than deduplicated.
    return 4096 + 32 * characters + 64 * depth


def measure_node_file_metadata(root_text, files):
    """Return (detached root, detached rows, conservative metadata charge).

    Cheap primitive length/depth bounds precede path parsing and derived-parent
    allocation. No filesystem operation or caller getter/iteration runs here.
    Original file C slots use the compiler observer's existing namespace fence.
    """
    snapshots = []
    names = []
    item = fields = path = content = mode = root = result = None
    try:
        if type(root_text) is not str:
            raise TypeError("file metadata requires exact root text")
        if (
            not 1 <= len(root_text) <= 4096
            or not root_text.startswith("/")
            or root_text.startswith("//")
            or root_text.count("/") > _MAXIMUM_DEPTH
        ):
            raise ValueError("file metadata root exceeds its bounded POSIX profile")
        root = Path(root_text)
        if ".." in root.parts or root.as_posix() != root_text:
            raise ValueError("file metadata root is not canonical")
        if type(files) is not tuple or not 1 <= len(files) <= _MAXIMUM_FILES:
            raise ValueError("file metadata inventory exceeds its bound")
        root_depth = len(root.parts)
        # Fixed cells and one unexpected filesystem entry before refusal. Include
        # every possible root ancestry row and its temporary construction storage.
        charge = 1024 * 1024 + root_depth * _row_charge(len(root_text), root_depth)
        derived_rows = root_depth
        source_bytes = 0
        for item in files:
            fields = _read_slots(item, DirectoryExportFile)
            path, content, mode = fields
            if (
                type(path) is not str
                or not 1 <= len(path) <= 1024
                or path.count("/") >= _MAXIMUM_DEPTH
                or type(content) is not bytes
                or type(mode) is not int
                or not 0 <= mode <= 0o777
            ):
                raise ValueError("file metadata row exceeds its primitive profile")
            source_bytes += len(content)
            if source_bytes > 128 * 1024 * 1024:
                raise ValueError("file metadata inventory exceeds live source bound")
            depth = path.count("/") + 1
            derived_rows += depth
            if derived_rows > _MAXIMUM_DERIVED_ROWS:
                raise ValueError("file metadata derived inventory exceeds its bound")
            # Bound every parent prefix, including repeated prefixes, using the
            # full path length. This overcounts the quadratic prefix-string cost.
            charge += depth * _row_charge(
                len(root_text) + 1 + len(path), root_depth + depth
            )
            if charge > MAXIMUM_FILE_METADATA_BYTES:
                raise ValueError("file metadata storage exceeds its reservation")
            names.append(path)
            snapshots.append(DirectoryExportFile(path, content, mode))
            item = fields = path = content = mode = None
        # The complete bounded set still uses canonical cross-host alias and
        # file/ancestor collision validation. No filesystem baseline is adopted.
        canonical_relative_posix_paths(tuple(names), label="verifier materialization")
        result = (root, tuple(snapshots), charge)
        return result
    finally:
        root_text = files = item = fields = path = content = mode = root = result = None
        snapshots.clear()
        names.clear()
