"""Shared bounded CommonJS boundary checks for standalone lifecycle drivers."""

import inspect
import os
import stat
from pathlib import Path

from literate_ai._filesystem import stat_is_link_or_reparse
from literate_ai.adapters.action_build_limits import (
    MAX_BUILD_ARCHIVE_BYTES,
    MAX_BUILD_ARCHIVE_FILES,
)
from literate_ai.application.library_artifacts import (
    COMMONJS_PACKAGE_METADATA_MAX_BYTES,
    require_commonjs_module_files,
    require_commonjs_package_boundary,
)


def require_commonjs_library_tree(export: Path) -> set[str]:
    """Check the closed provider namespace before Node can evaluate any module."""
    pending = [export]
    files = set()
    count = total = 0
    while pending:
        directory = pending.pop()
        metadata = directory.lstat()
        resolved = directory.resolve(strict=True)
        if (
            stat_is_link_or_reparse(metadata)
            or not stat.S_ISDIR(metadata.st_mode)
            or (resolved != export and export not in resolved.parents)
        ):
            raise ValueError(
                "CommonJS library directory escaped its original namespace"
            )
        with os.scandir(directory) as entries:
            for entry in entries:
                path = Path(entry.path)
                metadata = path.lstat()
                count += 1
                if count > MAX_BUILD_ARCHIVE_FILES or stat_is_link_or_reparse(metadata):
                    raise ValueError(
                        "CommonJS library namespace exceeds bounds or has a link"
                    )
                if stat.S_ISDIR(metadata.st_mode):
                    pending.append(path)
                elif stat.S_ISREG(metadata.st_mode):
                    files.add(path.relative_to(export).as_posix())
                    total += metadata.st_size
                    if total > MAX_BUILD_ARCHIVE_BYTES:
                        raise ValueError(
                            "CommonJS library namespace exceeds its byte bound"
                        )
                    if path.name == "package.json":
                        descriptor = os.open(
                            path,
                            os.O_RDONLY
                            | getattr(os, "O_BINARY", 0)
                            | getattr(os, "O_NOFOLLOW", 0)
                            | getattr(os, "O_NONBLOCK", 0),
                        )
                        with os.fdopen(descriptor, "rb") as stream:
                            opened = os.fstat(stream.fileno())
                            if not stat.S_ISREG(opened.st_mode) or (
                                opened.st_dev,
                                opened.st_ino,
                            ) != (metadata.st_dev, metadata.st_ino):
                                raise ValueError("CommonJS package boundary changed")
                            if opened.st_size > COMMONJS_PACKAGE_METADATA_MAX_BYTES:
                                raise ValueError("CommonJS metadata exceeds its bound")
                            require_commonjs_package_boundary(
                                stream.read(COMMONJS_PACKAGE_METADATA_MAX_BYTES + 1)
                            )
                else:
                    raise ValueError("CommonJS library namespace has a foreign node")
    return files


_JAVASCRIPT_IMPORT_PROGRAM = """
if surface.get("schema") == "urn:literate-ai:schema:v2:library-import-surface@2":
    declared_files = require_commonjs_library_tree(export)
    require_commonjs_module_files(
        ((row["runtime"], row["declaration"]) for row in surface["declarations"]),
        declared_files,
    )
script = '''const fs=require('fs'),path=require('path');
const root=fs.realpathSync(process.argv[1]), surface=JSON.parse(process.argv[2]);
const packageRoot=fs.realpathSync(path.join(root,'source',surface.package));
if (!packageRoot.startsWith(root+path.sep))
  throw Error('library package escaped exact artifact');
const declared=surface.schema==='urn:literate-ai:schema:v2:library-import-surface@2';
if (surface.schema!==undefined && !declared)
  throw Error('unsupported library import surface version');
const modules=new Map();
if (declared) {
  if (!Array.isArray(surface.declarations) || !surface.declarations.length)
    throw Error('declared library lacks complete runtime authority');
  for (const row of surface.declarations) {
    if (modules.has(row.module) || row.format!=='commonjs' ||
        typeof row.runtime!=='string' ||
        !row.runtime.startsWith('source/'+surface.package+'/'))
      throw Error('declared library runtime authority differs');
    modules.set(row.module,row);
  }
  const expected=[...new Set(surface.capabilities.map(row=>row.module))].sort();
  if (JSON.stringify([...modules.keys()].sort())!==JSON.stringify(expected))
    throw Error('declared library runtime inventory differs');
} else if (surface.declarations!==undefined) {
  throw Error('legacy library cannot acquire declared runtime authority');
}
const manifestPath=path.join(packageRoot,'package.json');
const manifest=JSON.parse(fs.readFileSync(manifestPath,'utf8'));
if (manifest.name!==surface.package || !manifest.exports ||
    !['commonjs',undefined].includes(manifest.type))
  throw Error('library manifest differs from locked import authority');
const dependencyFields=['dependencies','devDependencies',
                        'optionalDependencies','peerDependencies'];
for (const field of dependencyFields)
  if (manifest[field] && Object.keys(manifest[field]).length)
    throw Error('dependency-free library manifest declares '+field);
const seen=[];
const expectedExports={};
for (const capability of surface.capabilities) {
  const prefix=surface.package+'/';
  if (!capability.module.startsWith(prefix) &&
      !(declared && capability.module===surface.package))
    throw Error('library module escaped package authority');
  const subpath=capability.module===surface.package
    ? '.' : './'+capability.module.slice(prefix.length);
  const targetSpec=declared
    ? './'+modules.get(capability.module).runtime.slice(
        ('source/'+surface.package+'/').length)
    : './'+capability.module.slice(prefix.length)+'.js';
  expectedExports[subpath]=targetSpec;
  if (manifest.exports[subpath]!==targetSpec)
    throw Error('library exports map differs for '+subpath);
  const target=path.join(packageRoot,targetSpec);
  const resolved=fs.realpathSync(require.resolve(target));
  if (!(resolved===packageRoot || resolved.startsWith(packageRoot+path.sep)))
    throw Error('library import escaped exact artifact');
  const value=require(resolved);
  for (const symbol of capability.symbols)
    if (!(symbol in value)) throw Error('missing library symbol '+symbol);
  seen.push(capability.capability);
}
const actualExportKeys=Object.keys(manifest.exports).sort();
const expectedExportKeys=Object.keys(expectedExports).sort();
if (JSON.stringify(actualExportKeys)!==JSON.stringify(expectedExportKeys))
  throw Error('library exports map has undeclared entries');
process.stdout.write(JSON.stringify({schema:'literate-ai/library-import-observation@1',capabilities:seen}));
'''
completed = subprocess.run([*tool, "-e", script, str(export), surface_json],
                           capture_output=True)
sys.stdout.buffer.write(completed.stdout)
sys.stderr.buffer.write(completed.stderr)
raise SystemExit(completed.returncode)
"""


def commonjs_import_driver_source() -> str:
    """Embed the same trusted helpers; the child imports no framework package."""
    return (
        "import json, os, stat\nfrom pathlib import Path\n"
        "_WINDOWS_REPARSE_POINT = "
        "getattr(stat, 'FILE_ATTRIBUTE_REPARSE_POINT', 0x400)\n"
        f"MAX_BUILD_ARCHIVE_FILES = {MAX_BUILD_ARCHIVE_FILES}\n"
        f"MAX_BUILD_ARCHIVE_BYTES = {MAX_BUILD_ARCHIVE_BYTES}\n"
        f"COMMONJS_PACKAGE_METADATA_MAX_BYTES = {COMMONJS_PACKAGE_METADATA_MAX_BYTES}\n"
        + inspect.getsource(stat_is_link_or_reparse)
        + "\n"
        + inspect.getsource(require_commonjs_package_boundary)
        + "\n"
        + inspect.getsource(require_commonjs_module_files)
        + "\n"
        + inspect.getsource(require_commonjs_library_tree)
        + "\n"
        + _JAVASCRIPT_IMPORT_PROGRAM
    )
