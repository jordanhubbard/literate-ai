"""Artifact-local Python imports from exact accepted library export snapshots."""

from __future__ import annotations

import base64
import hashlib
import json
import keyword
import os
import re
import zlib
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from literate_ai._filesystem import path_is_link_or_reparse, require_safe_directory
from literate_ai.adapters.action_build_limits import (
    MAX_BUILD_ARCHIVE_BYTES,
    MAX_BUILD_ARCHIVE_FILES,
)
from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    encode_directory_export,
    read_directory_export,
    require_materialized_files,
    snapshot_directory_file,
)
from literate_ai.contracts import (
    ArtifactExport,
    BlobRef,
    ComponentCommandContract,
    ContentIdentity,
    LibraryConsumerBinding,
    LibraryImportSurface,
    canonical_identity,
    canonical_json_bytes,
    canonical_relative_posix_path,
    canonical_relative_posix_paths,
)

SCHEMA = "literate-ai/python-library-imports@1"
DIRECTORY = ".litai-python"
MANIFEST = "imports.json"
_MODULE = re.compile(r"[A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)*")


def is_python_import_contract(contract):
    """Select the original typed Python library or locked Python runtime owner."""

    if type(contract) is not ComponentCommandContract:
        return False
    surface = contract.library_import_surface
    return (
        surface is not None and surface.language == "python"
    ) or requires_python_build_inputs(contract)


def requires_python_build_inputs(contract):
    """Recognize modern locked import drivers; old empty library DATA stays legacy."""
    from literate_ai.adapters.lifecycle.standard_runtime import (
        STANDARD_PYTHON_RUNTIME_DRIVER,
        STANDARD_PYTHON_SDK_LIBRARY_IMPORT_DRIVER,
        STANDARD_PYTHON_SDK_RUNTIME_DRIVER,
        STANDARD_PYTHON_WHEEL_LIBRARY_IMPORT_DRIVER,
        STANDARD_PYTHON_WHEEL_RUNTIME_DRIVER,
    )
    from literate_ai.contracts import ComponentCommandPhase

    if type(contract) is not ComponentCommandContract:
        return False
    units = (
        contract.entrypoint_command_contracts()
        if contract.is_multi_entrypoint
        else (contract,)
    )
    drivers = (
        STANDARD_PYTHON_RUNTIME_DRIVER,
        STANDARD_PYTHON_SDK_RUNTIME_DRIVER,
        STANDARD_PYTHON_SDK_LIBRARY_IMPORT_DRIVER,
        STANDARD_PYTHON_WHEEL_RUNTIME_DRIVER,
        STANDARD_PYTHON_WHEEL_LIBRARY_IMPORT_DRIVER,
        compact_python_driver(PYTHON_LIBRARY_BOOTSTRAP),
    )
    return any(
        driver in unit.command(ComponentCommandPhase.EXECUTE).argv
        for unit in units
        for driver in drivers
    )


def compact_python_driver(source: str) -> str:
    """Keep one locked argv token within the original 4096-character limit."""

    encoded = base64.urlsafe_b64encode(zlib.compress(source.encode("utf-8"), 9)).decode(
        "ascii"
    )
    result = (
        "exec(__import__('zlib').decompress(__import__('base64').urlsafe_b64decode('"
        + encoded
        + "')))"
    )
    if len(result) > 4096:
        raise ValueError("locked Python driver exceeds original command argument bound")
    return result


# Locked driver source, never code loaded from an artifact. Enclosing artifact
# custody authenticates these declarations; this bootstrap checks their exact
# materialization and supplies no admission or host-execution authority.
# Braces are reserved for command placeholders, so use constructors below.
PYTHON_LIBRARY_BOOTSTRAP = """
def _litai_python_imports(export, extra=()):
    import hashlib,importlib.machinery,json,os,pathlib,stat,sys
    export=pathlib.Path(export)
    private=export/'.litai-python'
    if not private.exists() and not private.is_symlink(): return
    def require(ok):
        if not ok: raise ValueError('sealed Python library imports differ')
    def child(root,name):
        value=pathlib.PurePosixPath(name)
        require(isinstance(name,str) and value.parts and not value.is_absolute()
                and '..' not in value.parts and str(value)==name and '\\\\' not in name)
        path=root
        for part in value.parts:
            path=path/part
            info=path.lstat()
            require(not stat.S_ISLNK(info.st_mode)
                    and not bool(getattr(info,'st_file_attributes',0)&1024))
        return path
    budget=[0,0,0]; seen_files=set()
    def files(root,rows):
        require(isinstance(rows,list))
        names=[]
        for row in rows:
            require(set(row)==set(('path','size','digest','mode')))
            path=child(root,row['path'])
            info=path.stat()
            if path not in seen_files:
                seen_files.add(path)
                budget[0]+=1; budget[1]+=info.st_size
            require(budget[0]<=65534 and budget[1]<=268435456)
            require(stat.S_ISREG(info.st_mode) and info.st_size==row['size'])
            with path.open('rb') as stream:
                require(hashlib.file_digest(stream,'sha256').hexdigest()==row['digest'])
            require(os.name=='nt' or bool(info.st_mode&0o111)==bool(row['mode']&0o111))
            names.append(row['path'])
        require(names==sorted(set(names)))
        expected=set(names)
        for name in names:
            expected.update(p.as_posix() for p in pathlib.PurePosixPath(name).parents
                            if p.as_posix()!='.')
        actual=set()
        for path in root.rglob('*'):
            info=path.lstat()
            require(not stat.S_ISLNK(info.st_mode)
                    and not bool(getattr(info,'st_file_attributes',0)&1024))
            name=path.relative_to(root).as_posix()
            require(name in expected and name not in actual)
            actual.add(name)
        require(actual==expected)
    def modules(root):
        result=set()
        for index,path in enumerate(root.iterdir()):
            require(index<65534 and not path.is_symlink())
            name=path.name
            if path.is_file():
                name=next((name[:-len(s)] for s in importlib.machinery.all_suffixes()
                           if name.endswith(s)), '')
            if name.isidentifier() and name!='__pycache__': result.add(name)
        return result
    sources=dict(); selected=[]; checked=set()
    stdlib=set(sys.stdlib_module_names)|set(sys.builtin_module_names)|set(('literate_ai_native_sdk',))
    def add(root,owner):
        require(root.is_dir())
        for name in modules(root):
            require(name not in stdlib)
            sources.setdefault(name,dict()).setdefault(owner,[]).append(str(root))
    def visit(root,owner,depth,top=False):
        require(depth<=64)
        support=root/'.litai-python'
        if not support.exists(): return
        child(root,'.litai-python')
        manifest=child(support,'imports.json')
        with manifest.open('rb') as stream: raw=stream.read(16777217)
        budget[2]+=len(raw)
        require(budget[2]<=16777216)
        document=json.loads(raw)
        require(set(document)==set(('schema','consumer','packages','runtime'))
                and document['schema']=='literate-ai/python-library-imports@1')
        expected=set(('imports.json',))
        runtime=document['runtime']
        if runtime is not None:
            require(set(runtime)==set(('identity','files')))
            retained=child(support,'runtime')
            files(retained,runtime['files'])
            expected.add('runtime')
            if not top: add(child(retained,'site'),owner)
        for package in document['packages']:
            require(set(package)==set(('artifact_identity','provider','surface','bindings','public_roots','files')))
            identity=package['artifact_identity']
            folder=identity.removeprefix('sha256:')
            require(len(folder)==64 and all(c in '0123456789abcdef' for c in folder))
            destination=child(support,folder)
            files(destination,package['files'])
            expected.add(folder)
            selected.extend((name,identity) for name in package['public_roots'])
            if identity not in checked:
                checked.add(identity)
                add(child(destination,'source'),identity)
                visit(destination,identity,depth+1)
        actual=set()
        for path in support.iterdir():
            require(path.name in expected and path.name not in actual)
            actual.add(path.name)
        require(actual==expected)
    visit(export,'consumer',0,True)
    own=modules(child(export,'source'))
    other=(set().union(*(modules(pathlib.Path(path)) for path in extra))
           if extra else set())
    for name,owner in selected:
        require(name not in own and name not in other and name not in stdlib)
        require(set(sources.get(name,dict()))==set((owner,)))
        require(len(set(sources[name][owner]))==1)
    class NativeFinder:
        @staticmethod
        def find_spec(fullname,path=None,target=None):
            if path is not None or '.' in fullname or fullname not in sources:
                return None
            candidates=sources[fullname]
            if fullname in own or fullname in other or len(candidates)!=1:
                raise ImportError('ambiguous sealed Python library module: '+fullname)
            roots=tuple(set(next(iter(candidates.values()))))
            if len(roots)!=1:
                raise ImportError('ambiguous sealed Python payload module: '+fullname)
            return importlib.machinery.PathFinder.find_spec(fullname,roots)
    sys.meta_path.insert(0,NativeFinder)
"""


@dataclass(frozen=True, slots=True)
class PythonLibraryPackage:
    provider: ArtifactExport
    surface: LibraryImportSurface
    bindings: tuple[LibraryConsumerBinding, ...]
    files: tuple[DirectoryExportFile, ...]
    public_roots: tuple[str, ...]

    def to_dict(self):
        return {
            "artifact_identity": self.provider.identity.uri,
            "provider": self.provider.to_dict(),
            "surface": self.surface.to_dict(),
            "bindings": [binding.to_dict() for binding in self.bindings],
            "public_roots": list(self.public_roots),
            "files": _inventory(self.files),
        }


@dataclass(frozen=True, slots=True)
class PythonLibraryImports:
    consumer: ContentIdentity
    packages: tuple[PythonLibraryPackage, ...]

    @property
    def identity(self):
        return canonical_identity(self.to_dict())

    def to_dict(self):
        return {
            "schema": SCHEMA,
            "consumer": self.consumer.uri,
            "packages": [package.to_dict() for package in self.packages],
            "runtime": None,
        }


def _inventory(files):
    return [
        {
            "path": item.path,
            "size": len(item.content),
            "digest": hashlib.sha256(item.content).hexdigest(),
            "mode": item.mode,
        }
        for item in files
    ]


def prepare_python_library_imports(
    consumer: ComponentCommandContract,
    providers: tuple[ArtifactExport, ...],
    bindings: tuple[LibraryConsumerBinding, ...],
    contracts: Mapping[str, ComponentCommandContract],
    read_blob: Callable[[BlobRef], bytes],
    *,
    dependency_exports: Mapping[ContentIdentity, ArtifactExport] | None = None,
    runtime_identities: Mapping[ContentIdentity, ContentIdentity] | None = None,
) -> PythonLibraryImports:
    """Reopen bounded provider bytes; the caller retains current BUILD authority."""

    if (
        not isinstance(consumer, ComponentCommandContract)
        or not isinstance(providers, tuple)
        or any(not isinstance(item, ArtifactExport) for item in providers)
        or not isinstance(bindings, tuple)
        or any(not isinstance(item, LibraryConsumerBinding) for item in bindings)
    ):
        raise ValueError("Python library imports require exact typed build inputs")
    exports = {item.identity: item for item in providers}
    if len(exports) != len(providers):
        raise ValueError("duplicate Python provider artifact")
    known = dict(dependency_exports or {})
    known.update(exports)
    runtime_identities = dict(runtime_identities or {})
    grouped = {}
    for binding in bindings:
        if binding.consumer_component_revision != consumer.component_revision:
            raise ValueError("foreign Python library consumer binding")
        grouped.setdefault(binding.artifact_identity, []).append(binding)
    packages = []
    total_bytes = total_entries = 0
    roots = {}
    for artifact_identity, selected in sorted(
        grouped.items(), key=lambda row: row[0].uri
    ):
        artifact = exports.get(artifact_identity)
        contract = contracts.get(selected[0].provider_component_revision.uri)
        if artifact is None or not isinstance(contract, ComponentCommandContract):
            raise ValueError("Python provider or contract unavailable")
        surface = contract.library_import_surface
        if (
            not contract.is_library
            or surface is None
            or surface.language != "python"
            or artifact.role != "library"
            or artifact.component_revision != contract.component_revision
            or artifact.target_identity != consumer.artifact_export.target_identity
            or artifact.target_identity != contract.artifact_export.target_identity
        ):
            raise ValueError("Python provider differs from its exact library contract")
        modules, capabilities = set(), set()
        for binding in selected:
            capability = surface.capability(binding.capability)
            if (
                binding.provider_component_revision != artifact.component_revision
                or binding.import_surface_identity != surface.identity
                or binding.interface_identity != capability.interface_identity
                or binding.target_identity != artifact.target_identity
                or binding.dependency_artifact_identities
                != artifact.dependency_artifact_identities
                or binding.capability in capabilities
            ):
                raise ValueError("Python binding differs from its accepted provider")
            if not _MODULE.fullmatch(capability.module) or any(
                keyword.iskeyword(part) for part in capability.module.split(".")
            ):
                raise ValueError("Python capability is not an exact module name")
            capabilities.add(binding.capability)
            modules.add(capability.module)
        if artifact.blob.size > MAX_BUILD_ARCHIVE_BYTES - total_bytes:
            raise ValueError("Python provider closure exceeds byte bound")
        content = read_blob(artifact.blob)
        files = read_directory_export(
            content,
            artifact.blob,
            max_bytes=MAX_BUILD_ARCHIVE_BYTES - total_bytes,
            max_entries=MAX_BUILD_ARCHIVE_FILES - total_entries,
        )
        total_bytes += len(content)
        total_entries += len(files)
        _require_embedded_closure(
            artifact,
            files,
            known,
            contracts,
            read_blob,
            runtime_identities,
            stack=(),
        )
        paths = {item.path for item in files}
        for module in modules:
            path = "source/" + module.replace(".", "/")
            if path + ".py" not in paths and path + "/__init__.py" not in paths:
                raise ValueError("Python public module is absent from held export")
        aliases = tuple(sorted({module.split(".")[0] for module in modules}))
        for alias in aliases:
            previous = roots.setdefault(alias.casefold(), artifact.identity)
            if previous != artifact.identity:
                raise ValueError("Python providers have ambiguous public module roots")
        packages.append(
            PythonLibraryPackage(
                artifact,
                surface,
                tuple(sorted(selected, key=lambda b: b.identity.uri)),
                files,
                aliases,
            )
        )
    expected = {
        artifact.identity
        for artifact in providers
        if (contract := contracts.get(artifact.component_revision.uri)) is not None
        and contract.is_library
    }
    if set(grouped) != expected:
        raise ValueError("Python direct library binding coverage differs")
    return PythonLibraryImports(consumer.component_revision, tuple(packages))


def _require_embedded_closure(
    artifact, files, known, contracts, read_blob, runtime_identities, *, stack
):
    """Join nested DATA to original accepted exports, never a self-issued graph."""

    if artifact.identity in stack or len(stack) >= 64:
        raise ValueError("Python provider closure is cyclic or too deep")
    table = {item.path: item for item in files}
    if any(
        name.split("/", 1)[0].casefold() == DIRECTORY
        and not name.startswith(DIRECTORY + "/")
        for name in table
    ):
        raise ValueError("Python provider has an aliased reserved import path")
    selected = {}
    for identity in artifact.dependency_artifact_identities:
        child = known.get(identity)
        if child is None or child.identity != identity:
            raise ValueError("Python provider dependency lacks original export custody")
        contract = contracts.get(child.component_revision.uri)
        if not isinstance(contract, ComponentCommandContract):
            raise ValueError("Python provider dependency lacks its current contract")
        surface = contract.library_import_surface
        if surface is not None and surface.language == "python":
            selected[identity.uri] = child
    manifest = table.get(f"{DIRECTORY}/{MANIFEST}")
    expected_runtime = runtime_identities.get(artifact.identity)
    if manifest is None:
        if (
            selected
            or expected_runtime is not None
            or any(name.startswith(DIRECTORY + "/") for name in table)
        ):
            raise ValueError("Python provider lost its bound import/runtime closure")
        return
    if len(manifest.content) > 16 * 1024**2:
        raise ValueError("Python provider import manifest exceeds its bound")
    document = json.loads(manifest.content)
    if (
        not isinstance(document, dict)
        or set(document) != {"schema", "consumer", "packages", "runtime"}
        or document["schema"] != SCHEMA
        or document["consumer"] != artifact.component_revision.uri
        or canonical_json_bytes(document) != manifest.content
        or not isinstance(document["packages"], list)
    ):
        raise ValueError("Python provider has foreign import closure metadata")
    expected_paths = {f"{DIRECTORY}/{MANIFEST}"}
    identities = []
    for package in document["packages"]:
        if not isinstance(package, dict) or set(package) != {
            "artifact_identity",
            "provider",
            "surface",
            "bindings",
            "public_roots",
            "files",
        }:
            raise ValueError("Python provider has malformed nested import metadata")
        identity = package["artifact_identity"]
        child = selected.get(identity)
        if child is None or package["provider"] != child.to_dict():
            raise ValueError("Python nested imports differ from original dependencies")
        contract = contracts[child.component_revision.uri]
        surface = contract.library_import_surface
        if package["surface"] != surface.to_dict():
            raise ValueError("Python nested import surface changed")
        bindings = tuple(
            LibraryConsumerBinding.from_dict(b) for b in package["bindings"]
        )
        if not bindings or bindings != tuple(
            sorted(set(bindings), key=lambda b: b.identity.uri)
        ):
            raise ValueError("Python nested bindings are not canonical")
        aliases = set()
        for binding in bindings:
            capability = surface.capability(binding.capability)
            if (
                binding.consumer_component_revision != artifact.component_revision
                or binding.provider_component_revision != child.component_revision
                or binding.artifact_identity != child.identity
                or binding.import_surface_identity != surface.identity
                or binding.interface_identity != capability.interface_identity
                or binding.target_identity != child.target_identity
                or child.target_identity != artifact.target_identity
                or binding.dependency_artifact_identities
                != child.dependency_artifact_identities
            ):
                raise ValueError("Python nested binding differs from original provider")
            aliases.add(capability.module.split(".")[0])
        if package["public_roots"] != sorted(aliases):
            raise ValueError("Python nested public module roots changed")
        prefix = f"{DIRECTORY}/{child.identity.digest}/"
        child_files = tuple(
            DirectoryExportFile(item.path.removeprefix(prefix), item.content, item.mode)
            for item in files
            if item.path.startswith(prefix)
        )
        expected_paths.update(
            item.path for item in files if item.path.startswith(prefix)
        )
        if package["files"] != _inventory(child_files):
            raise ValueError("Python nested file inventory changed")
        content = encode_directory_export(
            child_files,
            max_bytes=MAX_BUILD_ARCHIVE_BYTES,
            max_entries=MAX_BUILD_ARCHIVE_FILES,
        )
        if (
            len(content) != child.blob.size
            or hashlib.sha256(content).hexdigest() != child.blob.digest
            or read_blob(child.blob) != content
        ):
            raise ValueError("Python nested bytes differ from original held export")
        _require_embedded_closure(
            child,
            child_files,
            known,
            contracts,
            read_blob,
            runtime_identities,
            stack=(*stack, artifact.identity),
        )
        identities.append(identity)
    if identities != sorted(selected):
        raise ValueError("Python nested library dependency coverage differs")
    runtime = document["runtime"]
    if (runtime is None) != (expected_runtime is None):
        raise ValueError("Python provider runtime association differs")
    if runtime is not None:
        if (
            not isinstance(runtime, dict)
            or set(runtime) != {"identity", "files"}
            or runtime["identity"] != expected_runtime.uri
        ):
            raise ValueError("Python provider runtime evidence identity changed")
        prefix = f"{DIRECTORY}/runtime/"
        runtime_files = tuple(
            DirectoryExportFile(item.path.removeprefix(prefix), item.content, item.mode)
            for item in files
            if item.path.startswith(prefix)
        )
        if runtime["files"] != _inventory(runtime_files):
            raise ValueError("Python provider runtime file inventory changed")
        expected_paths.update(
            item.path for item in files if item.path.startswith(prefix)
        )
    if {name for name in table if name.startswith(DIRECTORY + "/")} != expected_paths:
        raise ValueError("Python provider import closure has foreign files")


def _write_files(root: Path, files: tuple[DirectoryExportFile, ...]):
    for item in files:
        path = root.joinpath(
            *canonical_relative_posix_path(
                item.path, label="Python provider file"
            ).parts
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        require_safe_directory(path.parent)
        with path.open("xb") as stream:
            stream.write(item.content)
        path.chmod(item.mode)
    require_materialized_files(root, files)


def capture_python_library_runtime(root: Path) -> tuple[DirectoryExportFile, ...]:
    """Snapshot an already verified payload; its original owner fences this call."""

    require_safe_directory(root)
    pending, result, total, count = [root], [], 0, 0
    while pending:
        directory = pending.pop()
        require_safe_directory(directory)
        with os.scandir(directory) as entries:
            for entry in entries:
                count += 1
                if count > MAX_BUILD_ARCHIVE_FILES:
                    raise ValueError("Python runtime closure exceeds namespace bound")
                path = Path(entry.path)
                if path_is_link_or_reparse(path):
                    raise ValueError("Python runtime closure contains a link")
                if entry.is_dir(follow_symlinks=False):
                    pending.append(path)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    raise ValueError("Python runtime closure contains a non-file")
                if len(result) >= MAX_BUILD_ARCHIVE_FILES:
                    raise ValueError("Python runtime closure exceeds file bound")
                with path.open("rb") as stream:
                    content = stream.read(MAX_BUILD_ARCHIVE_BYTES - total + 1)
                total += len(content)
                if total > MAX_BUILD_ARCHIVE_BYTES:
                    raise ValueError("Python runtime closure exceeds byte bound")
                result.append(
                    DirectoryExportFile(
                        path.relative_to(root).as_posix(),
                        content,
                        path.stat().st_mode & 0o777,
                    )
                )
    return tuple(sorted(result, key=lambda item: item.path))


def python_library_materialization_files(
    imports: PythonLibraryImports,
    *,
    runtime: tuple[DirectoryExportFile, ...] = (),
    runtime_identity: ContentIdentity | None = None,
    windows: bool = False,
) -> tuple[DirectoryExportFile, ...]:
    """Project exact private bytes from independently prepared original inputs.

    This function performs no filesystem access and grants no qualification.
    Callers must reconstruct imports and runtime authority independently of the
    candidate artifact before using this projection as a replay expectation.
    """

    if not isinstance(imports, PythonLibraryImports):
        raise TypeError("Python imports require their prepared typed plan")
    if type(windows) is not bool:
        raise TypeError("Python materialization requires an exact target OS choice")
    if bool(runtime) != (runtime_identity is not None):
        raise ValueError(
            "Python runtime files require their original evidence identity"
        )
    if runtime_identity is not None and not isinstance(
        runtime_identity, ContentIdentity
    ):
        raise TypeError("Python runtime requires its original typed evidence identity")
    if not imports.packages and not runtime:
        return ()
    runtime = tuple(snapshot_directory_file(item) for item in runtime)
    if (
        sum(len(package.files) for package in imports.packages) + len(runtime)
        > MAX_BUILD_ARCHIVE_FILES
        or sum(
            len(item.content) for package in imports.packages for item in package.files
        )
        + sum(len(item.content) for item in runtime)
        > MAX_BUILD_ARCHIVE_BYTES
    ):
        raise ValueError("Python materialization exceeds its original archive bounds")
    canonical_relative_posix_paths(
        tuple(item.path for item in runtime), label="Python runtime file"
    )
    document = imports.to_dict()
    if runtime:
        document["runtime"] = {
            "identity": runtime_identity.uri,
            "files": _inventory(runtime),
        }
    raw = canonical_json_bytes(document)
    if len(raw) > 16 * 1024**2:
        raise ValueError("Python import manifest exceeds its byte bound")
    result = [
        DirectoryExportFile(f"{DIRECTORY}/{MANIFEST}", raw, 0o666 if windows else 0o644)
    ]
    for package in imports.packages:
        prefix = f"{DIRECTORY}/{package.provider.identity.digest}/"
        result.extend(
            DirectoryExportFile(prefix + item.path, item.content, item.mode)
            for item in map(snapshot_directory_file, package.files)
        )
    result.extend(
        DirectoryExportFile(
            f"{DIRECTORY}/runtime/" + item.path, item.content, item.mode
        )
        for item in runtime
    )
    result = tuple(sorted(result, key=lambda item: item.path))
    canonical_relative_posix_paths(
        tuple(item.path for item in result), label="Python materialization file"
    )
    if (
        len(result) > MAX_BUILD_ARCHIVE_FILES
        or sum(len(item.content) for item in result) > MAX_BUILD_ARCHIVE_BYTES
    ):
        raise ValueError("Python materialization exceeds its original archive bounds")
    return result


def verify_python_library_materialization(
    imports: PythonLibraryImports,
    files: tuple[DirectoryExportFile, ...],
    *,
    runtime: tuple[DirectoryExportFile, ...] = (),
    runtime_identity: ContentIdentity | None = None,
    windows: bool = False,
):
    """Compare the complete reserved namespace, including expected absence."""

    expected = python_library_materialization_files(
        imports, runtime=runtime, runtime_identity=runtime_identity, windows=windows
    )
    actual = tuple(snapshot_directory_file(item) for item in files)
    canonical_relative_posix_paths(
        tuple(item.path for item in actual), label="Python candidate artifact file"
    )
    actual = tuple(
        sorted(
            (
                item
                for item in actual
                if item.path.split("/", 1)[0].casefold() == DIRECTORY
            ),
            key=lambda item: item.path,
        )
    )
    if actual != expected:
        raise ValueError("Python materialization differs from original build inputs")


def materialize_python_library_imports(
    imports: PythonLibraryImports,
    export: Path,
    *,
    runtime: tuple[DirectoryExportFile, ...] = (),
    runtime_identity: ContentIdentity | None = None,
):
    """Copy into a fresh owned export; no provider workspace remains a dependency."""

    files = python_library_materialization_files(
        imports,
        runtime=runtime,
        runtime_identity=runtime_identity,
        windows=os.name == "nt",
    )
    require_safe_directory(export.parent)
    if not path_is_link_or_reparse(export) and export.is_file():
        if files:
            raise ValueError("Python dependency closures require a directory export")
        return
    require_safe_directory(export)
    root = export / DIRECTORY
    if root.exists() or path_is_link_or_reparse(root):
        raise ValueError("reserved Python library import destination is occupied")
    for index, path in enumerate(export.iterdir()):
        if index >= MAX_BUILD_ARCHIVE_FILES:
            raise ValueError("Python export exceeds namespace bound")
        if path.name.casefold() == DIRECTORY:
            raise ValueError("reserved Python library import destination is occupied")
    if files:
        root.mkdir()
        _write_files(
            root,
            tuple(
                DirectoryExportFile(
                    item.path.removeprefix(DIRECTORY + "/"), item.content, item.mode
                )
                for item in files
            ),
        )
