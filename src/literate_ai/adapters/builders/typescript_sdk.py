"""Explicit TypeScript package capture through the existing SDK custody owner."""

from __future__ import annotations

import os
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path

from literate_ai.adapters.builders.javascript import NodeToolchain
from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.native_sdk_tree_custody import capture_native_sdk_tree
from literate_ai.adapters.node_sdk_tools import node_sdk_tool_environment
from literate_ai.adapters.node_sdk_typescript import (
    NodeSDKTypeScriptCompiler,
    TypeScriptSDK,
)
from literate_ai.bootstrap.host_install_requirements import version_satisfies
from literate_ai.contracts import ContentIdentity, canonical_identity
from literate_ai.contracts.retained_project import RetainedProjectLimits
from literate_ai.storage.cas import FileSystemCAS

_LIMITS = RetainedProjectLimits(1024, 16 * 1024 * 1024, 32 * 1024 * 1024)


def _selection(snapshot, constraint, version_range):
    return canonical_identity(
        {
            "schema": "literate-ai/typescript-sdk-tool-selection@1",
            "snapshot": snapshot.to_dict(),
            "constraint": constraint.to_dict(),
            "version_range": version_range,
        }
    )


@dataclass(frozen=True, slots=True)
class TypeScriptSDKToolchain:
    """A frozen tool image; construction grants no execution or vendor trust."""

    compiler: NodeSDKTypeScriptCompiler
    snapshot_identity: ContentIdentity
    constraint_identity: ContentIdentity
    version_constraint: str

    def __post_init__(self):
        if (
            not isinstance(self.compiler, NodeSDKTypeScriptCompiler)
            or not isinstance(self.snapshot_identity, ContentIdentity)
            or not isinstance(self.constraint_identity, ContentIdentity)
            or not isinstance(self.version_constraint, str)
            or not 1 <= len(self.version_constraint) <= 1024
        ):
            raise TypeError(
                "TypeScript tool selection requires bounded typed authority"
            )
        if self.compiler.selection_identity != _selection(
            self.snapshot_identity, self.constraint_identity, self.version_constraint
        ) or not version_satisfies(self.compiler.sdk.version, self.version_constraint):
            raise ValueError(
                "TypeScript compiler differs from selected snapshot/constraint"
            )

    @property
    def command(self) -> tuple[str, ...]:
        return self.compiler.command

    @property
    def identity(self) -> str:
        return self.compiler.identity.uri

    @property
    def node(self) -> NodeToolchain:
        return self.compiler.node

    @property
    def version(self) -> str:
        return self.compiler.sdk.version

    def require_unchanged(self, environment: Mapping[str, str] | None = None) -> None:
        # Compiler/helper/SDK packets are captured immutable bytes, not promises
        # about a continuing global installation. Node is reopened on execution.
        self.node.require_unchanged(
            node_sdk_tool_environment(
                os.environ if environment is None else environment
            )
        )


def capture_typescript_sdk_toolchain(
    root: Path,
    *,
    node: NodeToolchain,
    store: FileSystemCAS,
    constraint_identity: ContentIdentity,
    version_constraint: str,
    environment: Mapping[str, str],
    require_current: Callable[[], None],
) -> TypeScriptSDKToolchain:
    """Capture one selected package; never install, resolve npm or run its CLI.

    The calling host owns tool selection and execution authorization. The existing
    native-tree owner supplies bounded no-follow capture and closing file/directory
    checks. This profile accepts regular files only, preserving one filesystem
    custody implementation across SDK products and compiler packages.
    """
    if (
        not isinstance(node, NodeToolchain)
        or not isinstance(store, FileSystemCAS)
        or not isinstance(constraint_identity, ContentIdentity)
        or not isinstance(version_constraint, str)
        or not 1 <= len(version_constraint) <= 1024
        or not callable(require_current)
    ):
        raise TypeError(
            "TypeScript capture requires selected Node/store/policy and owner"
        )
    require_current()
    controlled = node_sdk_tool_environment(environment)
    node.require_unchanged(controlled)
    require_current()
    tree = capture_native_sdk_tree(
        root, store=store, limits=_LIMITS, case_sensitive=False
    )
    if tree.aliases:
        raise ValueError(
            "initial TypeScript SDK tool requires regular files without aliases"
        )
    files = []
    for item in tree.files:
        require_current()
        files.append(
            DirectoryExportFile(
                item.path,
                store.get_bytes(item.blob),
                0o755 if item.executable else 0o644,
            )
        )
    sdk = TypeScriptSDK(tuple(files))
    if not version_satisfies(sdk.version, version_constraint):
        raise ValueError("TypeScript SDK version differs from selected constraint")
    require_current()
    closing = capture_native_sdk_tree(
        root, store=store, limits=_LIMITS, case_sensitive=False
    )
    if closing.identity != tree.identity:
        raise ValueError("TypeScript SDK package changed during selection")
    node.require_unchanged(controlled)
    compiler = NodeSDKTypeScriptCompiler(
        sdk,
        node,
        selection_identity=_selection(
            tree.identity, constraint_identity, version_constraint
        ),
    )
    require_current()
    return TypeScriptSDKToolchain(
        compiler, tree.identity, constraint_identity, version_constraint
    )
