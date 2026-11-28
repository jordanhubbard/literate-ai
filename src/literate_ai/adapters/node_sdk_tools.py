"""One environment policy for SDK compiler and packer tool processes."""

import hashlib
import inspect
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from subprocess import CompletedProcess

from literate_ai.adapters.builders.javascript import controlled_node_environment
from literate_ai.contracts import ContentIdentity

SDK_TOOL_ENVIRONMENT_POLICY = "literate-ai/node-sdk-tool-environment@2"


def node_sdk_tool_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Keep launch necessities while denying ambient Node/npm tool controls.

    NODE_V8_COVERAGE, warning redirection and future NODE_* switches must not
    write outside object custody. These are compiler/packer tools, not application
    execution; no application NODE_ENV behavior is inferred or changed here.
    """
    controlled = controlled_node_environment(dict(environment))
    result = {
        name: value
        for name, value in controlled.items()
        if not name.upper().startswith(("NODE_", "NPM_", "LITAI_PROVIDER_"))
    }
    result["NODE_DISABLE_COMPILE_CACHE"] = "1"
    return result


@dataclass(frozen=True, slots=True)
class NodeSDKToolProcess:
    """Immutable facts from an actual closed child, never execution authority.

    Command paths and raw streams remain private caller-owned evidence. A
    lifecycle recorder chooses its bounded, path-free public observation shape.
    The observer receives no mutable reference to the runner's result object.
    """

    command: tuple[str, ...] = field(repr=False)
    returncode: int
    stdout: bytes = field(repr=False)
    stderr: bytes = field(repr=False)
    input_identity: ContentIdentity | None

    def __post_init__(self):
        if (
            not isinstance(self.command, tuple)
            or not self.command
            or any(
                not isinstance(token, str) or not token or "\0" in token
                for token in self.command
            )
            or type(self.returncode) is not int
            or not isinstance(self.stdout, bytes)
            or not isinstance(self.stderr, bytes)
            or (
                self.input_identity is not None
                and not isinstance(self.input_identity, ContentIdentity)
            )
        ):
            raise TypeError(
                "SDK process facts require immutable actual command/streams"
            )


def require_node_sdk_process_observer(observer) -> None:
    """An observer must finish synchronously before publication can proceed."""
    if observer is None:
        return
    if not callable(observer):
        raise TypeError("SDK process observer must be synchronous and return None")
    targets = (observer, type(observer).__call__)
    if any(
        inspect.iscoroutinefunction(target)
        or inspect.isasyncgenfunction(target)
        or inspect.isgeneratorfunction(target)
        for target in targets
    ):
        raise TypeError("SDK process observer must be synchronous and return None")


def notify_node_sdk_process(
    observer: Callable[[NodeSDKToolProcess], None] | None,
    *,
    command: tuple[str, ...],
    result: CompletedProcess[bytes],
    input_bytes: bytes | None = None,
) -> None:
    """Project actual process facts without exposing a mutable runner result."""
    require_node_sdk_process_observer(observer)
    if observer is not None:
        returned = observer(
            NodeSDKToolProcess(
                command,
                result.returncode,
                result.stdout,
                result.stderr,
                None
                if input_bytes is None
                else ContentIdentity.parse_uri(
                    "sha256:" + hashlib.sha256(input_bytes).hexdigest()
                ),
            )
        )
        if returned is not None:
            # A disguised coroutine must not leave an unawaited coroutine behind;
            # never drive it or adopt it as a deferred observation/permission.
            if inspect.iscoroutine(returned):
                returned.close()
            raise TypeError("SDK process observer must return None synchronously")
