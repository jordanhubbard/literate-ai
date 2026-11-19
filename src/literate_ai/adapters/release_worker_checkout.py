"""Commands for a repository-owned static release checkout on a worker."""

from __future__ import annotations

import base64
import gzip
import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from literate_ai.adapters.live_test_selection import posix_export_prefix
from literate_ai.adapters.ssh_transport import (
    powershell_command,
    powershell_home_path,
    powershell_literal,
)

UNSAFE_CHECKOUT = 73
BUSY_CHECKOUT = 75
DIRTY_CHECKOUT = 77
_NAMESPACE = ".litai-release-v2"
_NAMESPACE_OWNER = "literate-ai-static-release-v2"

_POSIX = """
set -e
umask 077
unset GIT_DIR GIT_WORK_TREE GIT_COMMON_DIR GIT_INDEX_FILE GIT_OBJECT_DIRECTORY \
    GIT_ALTERNATE_OBJECT_DIRECTORIES
owner=.git/litai-release-owner
reservation=.git/litai-release-reservation
git() {
    command git --no-optional-locks -c core.fsmonitor=false \
        -c core.hooksPath=/dev/null -c maintenance.auto=false -c gc.auto=0 "$@"
}
direct_dir() {
    [ -d "$1" ] && [ ! -L "$1" ] && [ "$(cd -- "$1" && pwd -P)" = "$1" ]
}
direct_file() {
    [ -f "$1" ] && [ ! -L "$1" ] && [ "$(wc -c < "$1")" -eq "$2" ]
}
namespace_owned() {
    direct_dir "$workspace" && direct_dir "$namespace" &&
    direct_file "$namespace/.owner" "${#namespace_owner}" &&
    [ "$(cat "$namespace/.owner")" = "$namespace_owner" ]
}
no_git_links() {
    links=$(find .git -type l -print -quit) && [ -z "$links" ]
}
owned() {
    namespace_owned && direct_dir "$d" && cd -- "$d" &&
    direct_dir "$d/.git" &&
    direct_file "$owner" 64 && [ "$(cat "$owner")" = "$identity" ] &&
    [ "$(git rev-parse --show-toplevel)" = "$d" ] &&
    [ "$(git rev-parse --absolute-git-dir)" = "$d/.git" ] &&
    [ "$(git rev-parse --git-common-dir)" = .git ] &&
    [ ! -e .git/objects/info/alternates ] &&
    no_git_links
}
reserved() {
    owned && direct_dir "$d/$reservation" &&
    direct_file "$reservation/token" 32 &&
    [ "$(cat "$reservation/token")" = "$token" ]
}
release_reservation() {
    reserved &&
    [ "$(find "$reservation" -mindepth 1 -maxdepth 1 | wc -l)" -eq 1 ] &&
    rm -- "$reservation/token" && rmdir -- "$reservation"
}
reusable() {
    indexed=$(git ls-files -v) || return 1
    if printf '%s
' "$indexed" | grep -q '^[a-zS]'; then return 1; fi
    changes=$(git status --porcelain --untracked-files=all) || return 1
    [ -z "$changes" ] || return 1
    head=$(git rev-parse -q --verify 'HEAD^{commit}' || :)
    known=$(git rev-parse -q --verify 'refs/litai/release^{commit}' || :)
    if [ -n "$head" ] || [ -n "$known" ]; then
        [ -n "$head" ] && [ "$head" = "$known" ] || return 1
        if git symbolic-ref -q HEAD >/dev/null; then return 1; else [ "$?" -eq 1 ]; fi
    else
        refs=$(git for-each-ref) && [ -z "$refs" ]
    fi
}
"""

_PS = r"""
$ErrorActionPreference = 'Stop'
foreach ($key in @('GIT_DIR','GIT_WORK_TREE','GIT_COMMON_DIR','GIT_INDEX_FILE',
                   'GIT_OBJECT_DIRECTORY','GIT_ALTERNATE_OBJECT_DIRECTORIES')) {
    [Environment]::SetEnvironmentVariable($key, $null, 'Process')
}
$owner = '.git/litai-release-owner'
$reservation = '.git/litai-release-reservation'
function git {
    & git.exe --no-optional-locks -c core.fsmonitor=false -c core.hooksPath=NUL `
        -c maintenance.auto=false -c gc.auto=0 @args
    $global:LASTEXITCODE = $LASTEXITCODE
}
function Direct-Item($path, [bool]$directory, [long]$length = -1) {
    $item = Get-Item -LiteralPath $path -Force -ErrorAction SilentlyContinue
    return ($null -ne $item -and $item.PSIsContainer -eq $directory -and
        -not ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -and
        ($length -lt 0 -or $item.Length -eq $length))
}
function Direct-Directory($path) {
    $path = [IO.Path]::GetFullPath($path)
    while ($path) {
        if (-not (Direct-Item $path $true)) { return $false }
        $parent = [IO.Directory]::GetParent($path)
        if ($null -eq $parent) { break }
        $path = $parent.FullName
    }
    return $true
}
function Namespace-Owned {
    $marker = Join-Path $namespace '.owner'
    return ((Direct-Directory $workspace) -and (Direct-Directory $namespace) -and
        (Direct-Item $marker $false $namespaceOwner.Length) -and
        [IO.File]::ReadAllText($marker) -ceq $namespaceOwner)
}
function Owned {
    if (-not (Namespace-Owned) -or -not (Direct-Directory $d)) { return $false }
    Set-Location -LiteralPath $d
    if (-not (Direct-Directory (Join-Path $d '.git')) -or
        -not (Direct-Item $owner $false 64) -or
        [IO.File]::ReadAllText((Join-Path $d $owner)) -cne $identity) { return $false }
    $top = git rev-parse --show-toplevel
    if ($LASTEXITCODE -ne 0 -or [IO.Path]::GetFullPath($top) -ne $d) { return $false }
    $gitdir = git rev-parse --absolute-git-dir
    if ($LASTEXITCODE -ne 0 -or
        [IO.Path]::GetFullPath($gitdir) -ne (Join-Path $d '.git')) { return $false }
    $common = git rev-parse --git-common-dir
    if ($LASTEXITCODE -ne 0 -or $common -ne '.git' -or
        (Test-Path -LiteralPath '.git/objects/info/alternates')) { return $false }
    $pending = [Collections.Generic.Stack[string]]::new()
    $pending.Push((Join-Path $d '.git'))
    while ($pending.Count) {
        foreach ($item in (Get-ChildItem -LiteralPath ($pending.Pop()) -Force)) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
                return $false
            }
            if ($item.PSIsContainer) { $pending.Push($item.FullName) }
        }
    }
    return $true
}
function Reserved {
    if (-not (Owned) -or
        -not (Direct-Directory (Join-Path $d $reservation)) -or
        -not (Direct-Item "$reservation/token" $false 32)) { return $false }
    return [IO.File]::ReadAllText((Join-Path $d "$reservation/token")) -ceq $token
}
function Release-Reservation {
    if (-not (Reserved) -or
        @(Get-ChildItem -LiteralPath $reservation -Force).Count -ne 1) { exit 74 }
    Remove-Item -LiteralPath "$reservation/token" -Force
    [IO.Directory]::Delete((Join-Path $d $reservation))
}
function Reusable {
    $indexed = git ls-files -v
    if ($LASTEXITCODE -ne 0 -or ($indexed -cmatch '^[a-zS]')) { return $false }
    $changes = git status --porcelain --untracked-files=all
    if ($LASTEXITCODE -ne 0 -or $changes) { return $false }
    $head = git rev-parse -q --verify 'HEAD^{commit}'
    $known = git rev-parse -q --verify 'refs/litai/release^{commit}'
    if ($head -or $known) {
        git symbolic-ref -q HEAD | Out-Null
        return ($head -and $head -ceq $known -and $LASTEXITCODE -eq 1)
    }
    $refs = git for-each-ref
    return ($LASTEXITCODE -eq 0 -and -not $refs)
}
function Write-Admission($path, $value) {
    $file = [IO.File]::Open($path, [IO.FileMode]::CreateNew)
    try {
        $bytes = [Text.Encoding]::ASCII.GetBytes($value)
        $file.Write($bytes, 0, $bytes.Length)
    } finally { $file.Dispose() }
}
"""


def release_worker_origin(
    root: Path, remote: str, *, include_ssh_user: bool = False
) -> str:
    """Normalize provenance; retain SSH account addressing for opaque identities."""
    if not remote:
        return ""
    if any(ord(character) < 32 or ord(character) == 127 for character in remote):
        raise ValueError("invalid Git remote")
    if Path(remote).is_absolute():
        return str(Path(remote).resolve())
    if "://" not in remote:
        scp = re.fullmatch(
            r"(?:([^@/:]+)@)?(\[[A-Fa-f0-9:]+\]|[A-Za-z0-9.-]+):([^:?#][^?#]*)",
            remote,
        )
        if scp:
            user, host, path = scp.groups()
            account = f"{user}@" if include_ssh_user and user else ""
            return f"{account}{host.casefold()}:{path}"
        if ":" in remote:
            raise ValueError("unsupported Git remote")
        return str((root / remote).resolve())
    location = urlsplit(remote)
    if location.scheme == "file":
        if location.netloc not in {"", "localhost"}:
            raise ValueError("unsupported file remote")
        return urlunsplit(("file", "", location.path, "", ""))
    if location.scheme not in {"http", "https", "ssh", "git"} or not location.hostname:
        raise ValueError("unsupported Git remote")
    host = location.hostname.casefold()
    if ":" in host:
        host = f"[{host}]"
    if location.port is not None:
        host = f"{host}:{location.port}"
    if include_ssh_user and location.scheme == "ssh":
        if location.password is not None:
            raise ValueError("password-bearing SSH remotes are unsupported")
        if location.username is not None:
            host = f"{location.username}@{host}"
    return urlunsplit((location.scheme, host, location.path, "", ""))


def _windows_command(script: str) -> str:
    # Windows OpenSSH can start cmd.exe before PowerShell. Compress the guard
    # to keep an ordinary invocation inside that shell's command-line budget.
    payload = base64.b64encode(gzip.compress(script.encode("utf-8"), mtime=0)).decode(
        "ascii"
    )
    return powershell_command(
        f"$source = [IO.MemoryStream]::new([Convert]::FromBase64String('{payload}')); "
        "$archive = [IO.Compression.GZipStream]::new("
        "$source, [IO.Compression.CompressionMode]::Decompress); "
        "$reader = [IO.StreamReader]::new($archive); "
        "$script = $reader.ReadToEnd(); $reader.Dispose(); "
        "& ([ScriptBlock]::Create($script))"
    )


def _posix_path(value: str) -> str:
    if value.startswith("~/"):
        return '"$HOME"/' + shlex.quote(value[2:])
    return shlex.quote(value)


@dataclass(frozen=True)
class ReleaseWorkerCheckout:
    """A finite workspace reservation held through the native gate."""

    workspace: str
    identity: str
    token: str
    windows: bool

    @classmethod
    def create(cls, workspace: str, identity: str, *, windows: bool):
        return cls(workspace.rstrip("/\\"), identity, uuid4().hex, windows)

    @property
    def relative(self) -> str:
        return f"{_NAMESPACE}/{self.identity[:32]}"

    @property
    def directory(self) -> str:
        return f"{self.workspace}/{self.relative}"

    @property
    def bundle(self) -> str:
        return f".git/litai-sync-{self.token}.bundle"

    @property
    def terminal_receipt(self) -> bytes:
        return f"\nlitai-release-reservation-released {self.token}\n".encode("ascii")

    def _command(self, *, posix: str, windows: str) -> str:
        if self.windows:
            workspace = powershell_home_path(self.workspace)
            return _windows_command(
                f"$workspace = [IO.Path]::GetFullPath({workspace}); "
                f"$namespace = Join-Path $workspace '{_NAMESPACE}'; "
                f"$namespaceOwner = '{_NAMESPACE_OWNER}'; "
                f"$d = [IO.Path]::GetFullPath({powershell_home_path(self.directory)}); "
                f"$identity = '{self.identity}'; $token = '{self.token}'; "
                + _PS
                + windows
            )
        return (
            f"workspace={_posix_path(self.workspace)}; "
            f'namespace="$workspace/{_NAMESPACE}"; '
            f"namespace_owner={_NAMESPACE_OWNER}; "
            f"d={_posix_path(self.directory)}; "
            f"identity={self.identity}; token={self.token}; " + _POSIX + posix
        )

    def prepare(self) -> str:
        return self._command(
            posix="""
direct_dir "$workspace" || exit 73
if mkdir -- "$namespace" 2>/dev/null; then
    direct_dir "$namespace" || exit 73
    (set -C; printf %s "$namespace_owner" > "$namespace/.owner")
fi
namespace_owned || exit 73
if mkdir -- "$d" 2>/dev/null; then
    direct_dir "$d" && cd -- "$d" || exit 73
    git init -q --template=
    git config core.autocrlf false
    (set -C; printf %s "$identity" > "$owner")
fi
owned || exit 73
mkdir -- "$reservation" 2>/dev/null || exit 75
(set -C; printf %s "$token" > "$reservation/token")
reserved || exit 74
if ! reusable; then
    release_reservation || exit 74
    exit 77
fi
git rev-parse -q --verify 'refs/litai/release^{commit}' || true
""",
            windows=r"""
if (-not (Direct-Directory $workspace)) { exit 73 }
$createdNamespace = $false
try {
    New-Item -ItemType Directory -Path $namespace | Out-Null
    $createdNamespace = $true
} catch {}
if ($createdNamespace) {
    if (-not (Direct-Directory $namespace)) { exit 73 }
    Write-Admission (Join-Path $namespace '.owner') $namespaceOwner
}
if (-not (Namespace-Owned)) { exit 73 }
$created = $false
try {
    New-Item -ItemType Directory -Path $d | Out-Null
    $created = $true
} catch {}
if ($created) {
    if (-not (Direct-Directory $d)) { exit 73 }
    Set-Location -LiteralPath $d
    git init -q --template=
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    git config core.autocrlf false
    if ($LASTEXITCODE) { exit $LASTEXITCODE }
    Write-Admission (Join-Path $d $owner) $identity
}
if (-not (Owned)) { exit 73 }
try { New-Item -ItemType Directory -Path $reservation | Out-Null }
catch { exit 75 }
Write-Admission (Join-Path $d "$reservation/token") $token
if (-not (Reserved)) { exit 74 }
if (-not (Reusable)) { Release-Reservation; exit 77 }
git rev-parse -q --verify 'refs/litai/release^{commit}'
exit 0
""",
        )

    def apply(self, revision: str, origin: str, *, uploaded: bool) -> str:
        bundle = shlex.quote(self.bundle)
        config = (
            f"git config remote.origin.url {shlex.quote(origin)}\n" if origin else ""
        )
        config_ps = (
            f"git config remote.origin.url {powershell_literal(origin)}\n"
            "if ($LASTEXITCODE) { exit $LASTEXITCODE }\n"
            if origin
            else ""
        )
        # The uploaded name is private to one reservation. Keep it on an
        # uncertain apply so the operator can inspect exact attempt custody.
        fetch = (
            f"[ -f {bundle} ] && [ ! -L {bundle} ] || exit 73\n"
            f"git fetch -q --no-tags --no-auto-maintenance {bundle} HEAD\n"
            if uploaded
            else ""
        )
        fetch_ps = (
            f"if (-not (Direct-Item '{self.bundle}' $false)) {{ exit 73 }}\n"
            f"git fetch -q --no-tags --no-auto-maintenance '{self.bundle}' HEAD\n"
            "if ($LASTEXITCODE) { exit $LASTEXITCODE }\n"
            if uploaded
            else ""
        )
        return self._command(
            posix=f"""
reserved || exit 73
reusable || exit 77
{fetch}
git -c advice.detachedHead=false checkout -q --detach --no-overwrite-ignore {revision}
{config}git update-ref refs/litai/release {revision}
{f"rm -- {bundle}" if uploaded else ""}
git rev-parse HEAD
""",
            windows=f"""
if (-not (Reserved)) {{ exit 73 }}
if (-not (Reusable)) {{ exit 77 }}
{fetch_ps}
git -c advice.detachedHead=false checkout -q --detach --no-overwrite-ignore {revision}
if ($LASTEXITCODE) {{ exit $LASTEXITCODE }}
{config_ps}git update-ref refs/litai/release {revision}
if ($LASTEXITCODE) {{ exit $LASTEXITCODE }}
{f"Remove-Item -LiteralPath '{self.bundle}' -Force" if uploaded else ""}
git rev-parse HEAD
""",
        )

    def gate(
        self, revision: str, argv: tuple[str, ...], overlay: dict[str, str]
    ) -> str:
        ps_environment = "\n".join(
            f"$env:{name} = {powershell_literal(value)}"
            for name, value in overlay.items()
        )
        ps_argv = " ".join(powershell_literal(item) for item in argv)
        return self._command(
            posix=f"""
reserved && [ "$(git rev-parse HEAD)" = '{revision}' ] || exit 73
{posix_export_prefix(overlay) if overlay else ":"}
set +e
( {shlex.join(argv)} )
gate_status=$?
set -e
reserved && [ "$(git rev-parse HEAD)" = '{revision}' ] || exit 73
release_reservation || exit 74
printf '\n%s %s\n' litai-release-reservation-released "$token" >&2
exit "$gate_status"
""",
            windows=f"""
if (-not (Reserved) -or (git rev-parse HEAD) -ne '{revision}') {{ exit 73 }}
{ps_environment}
$ErrorActionPreference = 'Continue'
$LASTEXITCODE = 127
& {ps_argv}
$gateStatus = $LASTEXITCODE
$ErrorActionPreference = 'Stop'
if (-not (Reserved) -or (git rev-parse HEAD) -ne '{revision}') {{ exit 73 }}
Release-Reservation
[Console]::Error.Write("`nlitai-release-reservation-released $token`n")
exit $gateStatus
""",
        )
