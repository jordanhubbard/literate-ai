# ADR 0033: Compose a Universal `os-base` Toolchain with OS-Specific Realizations

- Status: Accepted
- Date: 2026-09-03
- Decision owners: literate-ai maintainers
- Roadmap: [RELEASE-0.9-DEFECTS-010](../roadmap/active-work.md#x-release-09-defects-010-make-coding-agents-part-of-the-universal-os-toolchain)
- Supersedes the ownership split in: [ADR 0032](0032-tuple-specific-native-install-sboms.md)

## Context

The 0.9 host installer and sample-worker bootstrap describe overlapping toolchains in
two places. Tuple-specific host-install SBOMs cover Python, Git, and Git LFS. A separate
Python script hardcodes those capabilities again alongside Node, build tools, and one
of four coding-agent commands. The installer therefore cannot inspect or provision the
coding-agent capability, while a worker can report bootstrap success even when the
controller's explicitly selected provider is absent.

Package spelling is not capability identity. Git is the same universal capability
whether APT calls its package `git`, WinGet calls it `Git.Git`, or Homebrew calls it
`git`. Conversely, a Windows-only launcher or an archive URL is not universal policy
merely because a Python conditional can hide it.

## Decision

1. `flavors/os-base/` owns one logical CycloneDX SBOM for capabilities required on
   every supported Literate AI host: Python 3.11+ with `venv`/`ensurepip`, Git, Git
   LFS, and the supported coding-agent group (`codex`, `claude`, `cursor-agent`,
   `opencode`). The coding-agent realizations are self-contained native binaries;
   Node/npm are not universal prerequisites. The group requires one usable
   realization, not every provider simultaneously.
2. An explicit `CODING_CLI` or equivalent CLI selection narrows that group to exactly
   the named provider. Without an explicit selection, an already usable supported
   provider satisfies the group in declared order; only an empty group selects the
   declared default for installation. Installation never changes provider credentials
   or claims authentication.
3. Every selected language, package, build-system, accelerator, or concrete OS Flavor
   may own a `host-toolchain.cdx.json` logical mix-in. Node belongs to
   `lang-javascript`/`lang-typescript`, npm to `package-npm`, a C++ compiler to
   `lang-cpp`, and Make/CMake/Bazel to their corresponding `build-*` Flavors.
   `os-windows` contributes only Windows-specific Bash compatibility and VC runtime
   requirements. A Component/skill selection contributes exactly the union of its
   Flavor mix-ins.
4. `flavors/os-linux/`, `flavors/os-macos/`, and `flavors/os-windows/` own exact
   OS/distribution, architecture, and accelerator realization SBOMs. Those documents
   map all known logical capability IDs to native package names and package-manager
   commands.
   A provider artifact absent from the native manager is an integrity-pinned managed
   artifact in the same tuple leaf, not a downloaded installer script.
5. The stage-zero parser composes exactly one `os-base` document, the detected OS
   mix-in, and the selected Component/skill Flavor mix-ins before selecting one tuple
   leaf. Identical duplicate capability contracts are de-duplicated deterministically
   and generate a warning naming every contributing Flavor; differing contracts for
   the same capability fail composition. It also rejects missing or unknown
   capability realizations,
   target mismatches, symlinks, malformed graphs, unsafe command templates, archive
   traversal, and digest mismatch. Unsupported tuples enumerate the Flavor-owned SBOM
   directory so a porter can copy the nearest leaf.
6. `make install` and `detect-before-install` call the same Python capability parser,
   observer, consent boundary, installer, and re-probe. The worker profile may append
   language/build/accelerator requirements selected for its sample set, but may not
   restate the universal base or silently replace an explicitly selected provider.
7. User-specific managed tools are rooted only through `HostPaths.managed_tool_root`.
   Native package ownership remains with the host package manager. `make uninstall`
   continues to remove only Literate AI's launcher and private Python environment; it
   does not remove shared prerequisites or independently authenticated provider state.

### Native Python source-build prerequisites

A tuple can require native SDKs when the Python distribution closure has no
compatible binary wheel. These are physical build prerequisites of selected
logical capabilities, rather than new universal capabilities or changes to a
Component's selected Flavors. The first use is the native Windows ARM64 build of
the pinned `cryptography` distribution.

A tuple component with realization kind `native-build-prerequisite` names its
`for-capabilities` logical owners and `requires-capabilities` build tools. Each
reference resolves to its existing Flavor-owned contract. The stage-zero parser
keeps the selected base unchanged and computes a separate finite build closure.
`build-minimum-versions` can strengthen a tool's minimum for this operation while
preserving its original logical contract and upper bounds. Unknown owners, probe
identifiers colliding with logical capabilities, and escaping SDK member paths
refuse. These requirements remain subject to the existing package-manager query,
consent, installation and re-probe boundary.

The SDK declaration records its executable's relative position, required runtime
and development files, and build environment templates. A version string cannot
replace complete files or the existing native ARM64 image checks. SDK variables
resolve from the actual observed executable's root, are rechecked before use,
and refuse a conflicting operator environment, including native target-prefixed
OpenSSL settings that would otherwise take priority. The initial supported variable
set is the OpenSSL build configuration; additional SDK environment support needs
its own implementation and controls. SDK directory templates require exactly one
observed root and a contained relative suffix; foreign literal roots and parent
traversal refuse before installation. No provider credentials are changed.

Metadata controls are development evidence. Native installation, source-built
dependency import, native compiler execution and the ordinary installed-host
acceptance remain required before platform qualification.

### Classification

- **Invariant:** one logical owner per capability; deterministic harmless duplicate
  removal with warnings; conflicting duplicate rejection; exact explicit provider
  selection; detect-before-install; integrity before extraction; no credential
  mutation.
- **Policy:** the current base capability set, provider order/default, package-manager
  mappings, and supported tuple inventory.
- **Platform realization:** native package IDs, executable candidates, archive format,
  post-install PATH entries, and artifact URL/digest belong only to the owning concrete
  OS Flavor.

## Consequences

Adding a coding agent updates the base group once and adds only the realizations that
differ by OS tuple. Adding RPM Linux or FreeBSD copies an OS realization leaf without
changing the capability model or orchestration code. Language compilers, build systems,
GPU toolkits, browsers, and service authentication stay conditional rather than making
the base host needlessly large.

This refines ADR 0032: tuple-specific SBOMs remain the native installation authority,
but they are now realizations of an explicit universal base rather than independent
copies of universal semantics.

## Validation

- Validate the base and every tuple leaf against CycloneDX 1.7 and the composed
  capability-closure contract.
- Exercise all provider selections, default discovery, consent/decline, native and
  managed installation, post-install re-probe, artifact digest/traversal rejection,
  unsupported tuple diagnostics, and credential non-mutation.
- Run install/uninstall/install and selected-provider worker qualification on macOS,
  Debian-family Linux, and native Windows CPU/GPU workers.
