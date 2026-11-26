"""Pinned independent actual Cargo runner over an owned exact source copy.

The literal program is carried IN the qualification profile argv, never loaded
from a mutable helper filename at execution. No native output is manufactured.
The original generated tree/manifest/lock are never written. Existing locks are
preserved; only an absent lock is derived in the new owned namespace.
"""

import json
import sys

OWNED_CARGO_PARITY_RUNNER = r"""
import json, os, stat, subprocess, sys, tempfile
from pathlib import Path
source, build = Path(sys.argv[1]), Path(sys.argv[2])
cargo = json.loads(sys.argv[3])
argument = sys.argv[4]
assert source.is_absolute() and build.is_absolute()
assert '..' not in source.parts and '..' not in build.parts
assert isinstance(cargo,list) and cargo and all(isinstance(v,str) and v for v in cargo)
for path in (source, build):
 current=Path(path.anchor)
 for part in path.parts[1:]:
  current=current/part
  node=current.lstat()
  assert stat.S_ISDIR(node.st_mode) and not stat.S_ISLNK(node.st_mode)
with tempfile.TemporaryDirectory(prefix='qualified-owned-parity-',dir=build) as owned:
 owned=Path(owned)
 copied=owned/'source'
 copied.mkdir()
 pending=[(source,copied)]
 count=total=0
 while pending:
  original,destination=pending.pop()
  with os.scandir(original) as entries:
   for entry in entries:
    path=original/entry.name
    target=destination/entry.name
    node=path.lstat()
    assert not stat.S_ISLNK(node.st_mode)
    if stat.S_ISDIR(node.st_mode):
     target.mkdir()
     pending.append((path,target))
    else:
     assert stat.S_ISREG(node.st_mode) and node.st_nlink==1
     descriptor=os.open(path,os.O_RDONLY|getattr(os,'O_NOFOLLOW',0))
     with os.fdopen(descriptor,'rb') as stream:
      actual=os.fstat(stream.fileno())
      assert (actual.st_dev,actual.st_ino)==(node.st_dev,node.st_ino)
      assert actual.st_size<=2*1024*1024
      content=stream.read(2*1024*1024+1)
      assert len(content)==actual.st_size
     count+=1
     total+=len(content)
     assert count<=10000 and total<=64*1024*1024
     with target.open('xb') as stream:
      stream.write(content)
     target.chmod(stat.S_IMODE(node.st_mode))
 manifest=copied/'Cargo.toml'
 assert manifest.is_file() and not manifest.is_symlink()
 def execute(arguments):
  return subprocess.run(arguments,cwd=copied,stdin=subprocess.DEVNULL,
                        stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=False)
 if not (copied/'Cargo.lock').exists():
  result=execute(cargo+['generate-lockfile','--offline','--manifest-path',str(manifest)])
  sys.stderr.buffer.write(result.stderr)
  if result.returncode:
   sys.stdout.buffer.write(result.stdout)
   raise SystemExit(result.returncode)
  assert not result.stdout
 result=execute(cargo+['run','--quiet','--locked','--offline','--manifest-path',str(manifest),
                      '--bin','litai_artifact','--target-dir',str(owned/'target'),'--',argument])
 sys.stdout.buffer.write(result.stdout)
 sys.stderr.buffer.write(result.stderr)
 raise SystemExit(result.returncode)
""".strip()


def owned_cargo_parity_command(cargo):
    """Inert profile data; outer qualification retains its ORIGINAL bounds."""
    return (
        sys.executable,
        "-c",
        OWNED_CARGO_PARITY_RUNNER,
        "{workspace}/source",
        "{build_root}",
        json.dumps(list(cargo.command), separators=(",", ":")),
    )
