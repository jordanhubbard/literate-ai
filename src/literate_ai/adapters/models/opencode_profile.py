"""Passively project a selected V1 API profile without importing integrations.

This module never starts OpenCode, refreshes authentication, or writes user state.
The invocation owner supplies private state and the existing bounded process runner.
"""

from __future__ import annotations

import json
import os
import stat
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_MAX_FILE_BYTES = 1024 * 1024
_MAX_TOTAL_BYTES = 8 * 1024 * 1024
_MAX_API_KEY_BYTES = 16384
# API SDKs bundled by the reviewed V1 implementation. Native catalog defaults
# remain owned by the selected executable; no runtime catalog is imported here.
_API_SDK_PACKAGES = (
    None,
    "@ai-sdk/anthropic",
    "@ai-sdk/azure",
    "@ai-sdk/cerebras",
    "@ai-sdk/cohere",
    "@ai-sdk/google",
    "@ai-sdk/groq",
    "@ai-sdk/mistral",
    "@ai-sdk/openai",
    "@ai-sdk/openai-compatible",
    "@ai-sdk/perplexity",
    "@ai-sdk/xai",
    "@openrouter/ai-sdk-provider",
)
_NON_API_PROVIDERS = frozenset(
    {
        "amazon-bedrock",
        "google-vertex",
        "google-vertex-anthropic",
        "gitlab",
        "sap-ai-core",
        "sap-aicore",
        "snowflake",
    }
)
_API_ENV = {
    "anthropic": ("ANTHROPIC_API_KEY",),
    "azure": ("AZURE_API_KEY",),
    "cerebras": ("CEREBRAS_API_KEY",),
    "cohere": ("COHERE_API_KEY",),
    "deepseek": ("DEEPSEEK_API_KEY",),
    "fireworks-ai": ("FIREWORKS_API_KEY",),
    "google": ("GEMINI_API_KEY", "GOOGLE_GENERATIVE_AI_API_KEY"),
    "groq": ("GROQ_API_KEY",),
    "mistral": ("MISTRAL_API_KEY",),
    "opencode": ("OPENCODE_API_KEY",),
    "openai": ("OPENAI_API_KEY",),
    "openrouter": ("OPENROUTER_API_KEY",),
    "perplexity": ("PERPLEXITY_API_KEY",),
    "xai": ("XAI_API_KEY",),
}


class OpenCodeProfileError(ValueError):
    """A safe, value-free reason an operator profile cannot be projected."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True, slots=True)
class OpenCodeV1Profile:
    model: str
    configuration: dict[str, Any]
    authentication: dict[str, Any]
    redactions: dict[str, str]


def _read(path: Path, maximum_bytes: int) -> bytes:
    try:
        # Preserve ordinary operator-managed symlinks while refusing a final
        # substitution and avoiding a blocking open on a FIFO/device.
        target = path.resolve(strict=True)
        flags = (
            os.O_RDONLY | getattr(os, "O_NONBLOCK", 0) | getattr(os, "O_NOFOLLOW", 0)
        )
        descriptor = os.open(target, flags)
        with os.fdopen(descriptor, "rb") as stream:
            if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
                raise OpenCodeProfileError("configuration_invalid")
            content = stream.read(maximum_bytes + 1)
        if len(content) > maximum_bytes:
            raise OpenCodeProfileError("configuration_limit")
        return content
    except OSError:
        raise OpenCodeProfileError("configuration_unavailable") from None


def _jsonc(text: str) -> dict[str, Any]:
    # One linear lexical pass preserves quoted URLs/comment markers, replaces
    # comments with whitespace and removes only an actual trailing comma.
    parts: list[str] = []
    pending_comma = None
    index = 0
    while index < len(text):
        char = text[index]
        if char == '"':
            start = index
            index += 1
            while index < len(text):
                if text[index] == "\\":
                    index += 2
                elif text[index] == '"':
                    index += 1
                    break
                else:
                    index += 1
            else:
                raise OpenCodeProfileError("configuration_invalid")
            parts.append(text[start:index])
            pending_comma = None
            continue
        if text.startswith("//", index):
            index += 2
            while index < len(text) and text[index] not in "\r\n":
                index += 1
            parts.append(" ")
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            if end == -1:
                raise OpenCodeProfileError("configuration_invalid")
            index = end + 2
            parts.append(" ")
            continue
        if char in ("}", "]") and pending_comma is not None:
            parts[pending_comma] = ""
        if not char.isspace():
            pending_comma = len(parts) if char == "," else None
        parts.append(char)
        index += 1

    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise OpenCodeProfileError("configuration_ambiguous")
            result[key] = value
        return result

    def invalid_constant(_value):
        raise OpenCodeProfileError("configuration_invalid")

    try:
        value = json.loads(
            "".join(parts), object_pairs_hook=pairs, parse_constant=invalid_constant
        )
    except OpenCodeProfileError:
        raise
    except (ValueError, RecursionError):
        raise OpenCodeProfileError("configuration_invalid") from None
    if not isinstance(value, dict):
        raise OpenCodeProfileError("configuration_invalid")
    pending = [(value, 0)]
    count = 0
    while pending:
        node, depth = pending.pop()
        count += 1
        if depth > 32 or count > 16384:
            raise OpenCodeProfileError("configuration_limit")
        if isinstance(node, dict):
            pending.extend((v, depth + 1) for v in node.values())
        elif isinstance(node, list):
            pending.extend((v, depth + 1) for v in node)
    return value


def _merge(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    result = dict(left)
    for key, value in right.items():
        before = result.get(key)
        result[key] = (
            _merge(before, value)
            if isinstance(before, dict) and isinstance(value, dict)
            else value
        )
    return result


def _key(value: Any) -> str:
    try:
        size = len(value.encode("utf-8")) if isinstance(value, str) else 0
    except UnicodeError:
        raise OpenCodeProfileError("authentication_unsupported") from None
    if (
        not isinstance(value, str)
        or not value
        or size > _MAX_API_KEY_BYTES
        or any(ord(c) < 32 or ord(c) == 127 for c in value)
    ):
        raise OpenCodeProfileError("authentication_unsupported")
    return value


def selected_v1_profile(
    operator_environment: Mapping[str, str],
    invocation_environment: Mapping[str, str],
    model: str | None,
) -> OpenCodeV1Profile:
    """Select finite local data; never initialize an ambient CLI/account store.

    Quoted native env/file placeholders are supported. Arbitrary config code,
    remote account configuration and refreshing credentials are not projected.
    Explicitly supplied partial environments do not gain the process's real home.
    """
    remaining = _MAX_TOTAL_BYTES
    reads = 0

    def read(path: Path) -> str:
        nonlocal remaining, reads
        reads += 1
        if reads > 64:
            raise OpenCodeProfileError("configuration_limit")
        content = _read(path, min(_MAX_FILE_BYTES, remaining))
        remaining -= len(content)
        try:
            return content.decode("utf-8-sig")
        except UnicodeError:
            raise OpenCodeProfileError("configuration_invalid") from None

    values = (
        {k.upper(): v for k, v in operator_environment.items()}
        if os.name == "nt"
        else operator_environment
    )
    invocation = (
        {k.upper(): v for k, v in invocation_environment.items()}
        if os.name == "nt"
        else invocation_environment
    )
    home_value = (
        values.get("USERPROFILE") or values.get("HOME")
        if os.name == "nt"
        else values.get("HOME")
    )
    home = Path(home_value) if home_value else None
    config_home = values.get("XDG_CONFIG_HOME")
    data_home = values.get("XDG_DATA_HOME")
    configuration_root = (
        Path(config_home) / "opencode"
        if config_home
        else home / ".config/opencode"
        if home is not None
        else None
    )
    authentication_root = (
        Path(data_home) / "opencode"
        if data_home
        else home / ".local/share/opencode"
        if home is not None
        else None
    )
    sources: list[tuple[Path, dict[str, Any]]] = []
    if configuration_root is not None:
        for name in ("config.json", "opencode.json", "opencode.jsonc"):
            path = configuration_root / name
            if path.exists() or path.is_symlink():
                sources.append((path, _jsonc(read(path))))
    if home is not None:
        for name in ("opencode.json", "opencode.jsonc"):
            path = home / ".opencode" / name
            if path.exists() or path.is_symlink():
                sources.append((path, _jsonc(read(path))))
    chosen = model
    if chosen is None:
        for _path, source in sources:
            if "model" in source:
                chosen = source["model"]
    if (
        not isinstance(chosen, str)
        or len(chosen) > 1024
        or "/" not in chosen
        or not all(chosen.split("/", 1))
        or any(ord(c) < 33 or ord(c) == 127 for c in chosen)
    ):
        raise OpenCodeProfileError("model_required")
    try:
        chosen.encode("utf-8")
    except UnicodeError:
        raise OpenCodeProfileError("model_required") from None
    provider_id = chosen.split("/", 1)[0]
    secrets: set[str] = set()

    def expand(value: Any, directory: Path, *, private: bool = False):
        nonlocal remaining
        if isinstance(value, dict):
            return {
                k: expand(
                    v,
                    directory,
                    private=private
                    or any(
                        word in k.casefold()
                        for word in (
                            "apikey",
                            "api_key",
                            "token",
                            "secret",
                            "password",
                            "headers",
                        )
                    ),
                )
                for k, v in value.items()
            }
        if isinstance(value, list):
            return [expand(v, directory, private=private) for v in value]
        if not isinstance(value, str):
            return value

        def substitute(kind: str, name: str) -> str:
            if kind == "env":
                result = invocation.get(name.upper() if os.name == "nt" else name, "")
            else:
                if name.startswith("~/"):
                    if home is None:
                        raise OpenCodeProfileError("configuration_unavailable")
                    path = home / name[2:]
                else:
                    path = Path(name)
                    if not path.is_absolute():
                        path = directory / path
                result = read(path).strip()
            if result:
                secrets.add(result)
            return result

        # Native substitution expands environment references before file paths,
        # allowing a quoted {file:{env:HOME}/key} without recursive expansion.
        result = value
        for kind in ("env", "file"):
            pieces = []
            index = 0
            prefix = "{" + kind + ":"
            while index < len(result):
                if result.startswith(prefix, index):
                    start = index + len(prefix)
                    end = result.find("}", start)
                    if end == -1:
                        raise OpenCodeProfileError("configuration_invalid")
                    replacement = substitute(kind, result[start:end])
                    try:
                        remaining -= len(replacement.encode("utf-8"))
                    except UnicodeError:
                        raise OpenCodeProfileError("configuration_invalid") from None
                    if remaining < 0:
                        raise OpenCodeProfileError("configuration_limit")
                    pieces.append(replacement)
                    index = end + 1
                else:
                    pieces.append(result[index])
                    index += 1
            result = "".join(pieces)
        if private and result:
            secrets.add(result)
        return result

    provider: dict[str, Any] = {}
    for path, source in sources:
        providers = source.get("provider", {})
        if not isinstance(providers, dict):
            raise OpenCodeProfileError("configuration_invalid")
        selected = providers.get(provider_id, {})
        if not isinstance(selected, dict):
            raise OpenCodeProfileError("configuration_invalid")
        selected = dict(selected)
        if "models" in selected:
            models = selected["models"]
            if not isinstance(models, dict):
                raise OpenCodeProfileError("configuration_invalid")
            model_id = chosen.split("/", 1)[1]
            selected["models"] = (
                {model_id: models[model_id]} if model_id in models else {}
            )
        provider = _merge(provider, expand(selected, path.parent))
    package = provider.get("npm")
    if (
        provider_id in _NON_API_PROVIDERS
        or package not in _API_SDK_PACKAGES
        or (provider_id not in _API_ENV and package is None)
    ):
        raise OpenCodeProfileError("provider_unsupported")
    for model_config in provider.get("models", {}).values():
        if not isinstance(model_config, dict):
            raise OpenCodeProfileError("configuration_invalid")
        model_provider = model_config.get("provider", {})
        if not isinstance(model_provider, dict):
            raise OpenCodeProfileError("configuration_invalid")
        if model_provider.get("npm") not in _API_SDK_PACKAGES:
            raise OpenCodeProfileError("provider_unsupported")
    stored = {}
    supplied_auth = values.get("OPENCODE_AUTH_CONTENT")
    if supplied_auth:
        try:
            size = len(supplied_auth.encode("utf-8"))
        except UnicodeError:
            raise OpenCodeProfileError("configuration_invalid") from None
        if size > min(_MAX_FILE_BYTES, remaining):
            raise OpenCodeProfileError("configuration_limit")
        remaining -= size
        stored = _jsonc(supplied_auth)
    elif authentication_root is not None:
        path = authentication_root / "auth.json"
        if path.exists() or path.is_symlink():
            stored = _jsonc(read(path))
    selected_auth = stored.get(provider_id)
    authentication = {}
    if selected_auth is not None:
        if not isinstance(selected_auth, dict) or selected_auth.get("type") != "api":
            # Never silently replace a selected refreshing/integration login with
            # environment API billing, or copy a rotating token back to user state.
            raise OpenCodeProfileError("authentication_unsupported")
        if set(selected_auth) - {"type", "key", "metadata"}:
            raise OpenCodeProfileError("authentication_unsupported")
        metadata = selected_auth.get("metadata", {})
        if not isinstance(metadata, dict) or not all(
            isinstance(k, str) and isinstance(v, str) for k, v in metadata.items()
        ):
            raise OpenCodeProfileError("authentication_unsupported")
        key = _key(selected_auth.get("key"))
        authentication[provider_id] = {"type": "api", "key": key}
        if metadata:
            authentication[provider_id]["metadata"] = metadata
            secrets.update(v for v in metadata.values() if v)
        secrets.add(key)
    options = provider.get("options", {})
    if not isinstance(options, dict):
        raise OpenCodeProfileError("configuration_invalid")
    configured_key = options.get("apiKey")
    if configured_key is not None:
        secrets.add(_key(configured_key))
    declared_env = provider.get("env", _API_ENV.get(provider_id, ()))
    if not isinstance(declared_env, (list, tuple)) or not all(
        isinstance(k, str) for k in declared_env
    ):
        raise OpenCodeProfileError("configuration_invalid")
    environment_key = False
    for name in declared_env:
        value = invocation.get(name.upper() if os.name == "nt" else name)
        if value:
            secrets.add(_key(value))
            environment_key = True
    if not (authentication or configured_key or environment_key):
        raise OpenCodeProfileError("authentication_required")
    configuration = {
        "model": chosen,
        "small_model": chosen,
        "enabled_providers": [provider_id],
        "provider": {provider_id: provider} if provider else {},
    }
    # Native errors can quote or JSON-escape a value; protect those renderings
    # without forwarding any diagnostic binding to the actual child process.
    redactions = secrets | {
        rendered
        for value in secrets
        for rendered in (json.dumps(value)[1:-1], repr(value)[1:-1])
        if rendered
    }
    return OpenCodeV1Profile(
        chosen,
        configuration,
        authentication,
        {f"LITAI_REDACTION_SECRET_{i}": v for i, v in enumerate(sorted(redactions))},
    )
