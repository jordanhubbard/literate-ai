"""Closed verifier-request preimages are DATA, never inspection or permission."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from literate_ai.contracts.identity import ContentIdentity, canonical_json_bytes
from literate_ai.security import BuildRequest

MAX_INPUT_BYTES = 16 * 1024
MAX_REQUEST_BYTES = 4096
_OUTPUTS = ("verifier-workspace", "stdout", "stderr")
_PRIVILEGES = ("execute-library-verifier",)
_SANDBOX = "local-explicit-host-process"
_ROLES = {
    "literate-ai/local-node-provider-verifier-inputs@1": (
        "local-node-provider-verifier@1",
        frozenset({"acceptance", "artifact", "contract", "oracle", "surface"}),
    ),
    "literate-ai/local-node-sdk-project-verifier-inputs@1": (
        "local-node-sdk-project-verifier@1",
        frozenset(
            {
                "policy",
                "project_plan",
                "package_plan",
                "package_result",
                "build_plan",
                "artifact",
                "root_test",
                "packaged_execution",
                "oracle",
            }
        ),
    ),
}


def _refuse():
    raise ValueError("Node verifier description differs from its closed request")


def _pairs(items):
    value = {}
    for key, item in items:
        if key in value:
            _refuse()
        value[key] = item
    return value


def _document(content, maximum):
    if type(content) is not bytes or not 1 <= len(content) <= maximum:
        _refuse()
    try:
        value = json.loads(
            content, object_pairs_hook=_pairs, parse_constant=lambda _: _refuse()
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError):
        _refuse()
    if type(value) is not dict:
        _refuse()
    return value


def _inputs(value):
    if type(value) is not dict or not 1 <= len(value) <= 12:
        _refuse()
    for key, item in value.items():
        if (
            type(key) is not str
            or len(key) > 64
            or type(item) is not str
            or not 1 <= len(item) <= 4096
        ):
            _refuse()
    selected = _ROLES.get(value.get("schema"))
    if selected is None:
        _refuse()
    builder, identities = selected
    if set(value) != identities | {"schema", "compiler", "node"}:
        _refuse()
    for name in identities | {"compiler"}:
        ContentIdentity.parse_uri(value[name])
    node = value["node"]
    if len(node.encode("utf-8")) > 4096 or any(
        ord(character) < 32 or ord(character) == 127 for character in node
    ):
        _refuse()
    return builder


def _request_content(request):
    if type(request) is not BuildRequest:
        raise TypeError("Node verifier description requires an exact BuildRequest")
    for name in (
        "effective_revision_digest",
        "source_bundle_digest",
        "builder_id",
        "toolchain_digest",
        "sandbox_profile",
    ):
        value = getattr(request, name)
        if type(value) is not str or not 1 <= len(value) <= 4096:
            _refuse()
    if (
        type(request.requested_privileges) is not tuple
        or len(request.requested_privileges) != 1
        or any(type(value) is not str for value in request.requested_privileges)
        or request.requested_privileges != _PRIVILEGES
        or type(request.allowed_outputs) is not tuple
        or len(request.allowed_outputs) != 3
        or any(type(value) is not str for value in request.allowed_outputs)
        or request.allowed_outputs != _OUTPUTS
        or request.sandbox_profile != _SANDBOX
    ):
        _refuse()
    content = canonical_json_bytes(request.to_dict())
    if len(content) > MAX_REQUEST_BYTES:
        _refuse()
    return content


@dataclass(frozen=True, slots=True)
class NodeLibraryVerifierRequestDescription:
    """Detached preimages, without source custody, inspection or a grant.

    The owner revision is separate: neither existing hashed input schema contains
    it. An actual resource owner must still supply its original revision and live
    witnesses; matching these descriptive values does not establish that owner.
    """

    inputs_content: bytes = field(repr=False)
    request_content: bytes = field(repr=False)
    owner_revision_uri: str

    def __post_init__(self):
        if type(self) is not NodeLibraryVerifierRequestDescription:
            raise TypeError("Node verifier descriptions cannot be subclasses")
        self._validated()

    def _validated(self):
        if type(self) is not NodeLibraryVerifierRequestDescription:
            raise TypeError("Node verifier descriptions cannot be subclasses")
        if (
            type(self.owner_revision_uri) is not str
            or len(self.owner_revision_uri) != 71
        ):
            _refuse()
        ContentIdentity.parse_uri(self.owner_revision_uri)
        inputs = _document(self.inputs_content, MAX_INPUT_BYTES)
        builder = _inputs(inputs)
        if canonical_json_bytes(inputs) != self.inputs_content:
            _refuse()
        document = _document(self.request_content, MAX_REQUEST_BYTES)
        if set(document) != {
            "schema",
            "effective_revision_digest",
            "source_bundle_digest",
            "builder_id",
            "toolchain_digest",
            "sandbox_profile",
            "requested_privileges",
            "allowed_outputs",
        }:
            _refuse()
        for key, value in document.items():
            if key in {"requested_privileges", "allowed_outputs"}:
                if (
                    type(value) is not list
                    or len(value) > 3
                    or any(type(item) is not str for item in value)
                ):
                    _refuse()
            elif type(value) is not str or not 1 <= len(value) <= 4096:
                _refuse()
        if document["schema"] != BuildRequest.SCHEMA:
            _refuse()
        request = BuildRequest.from_dict(document)
        if _request_content(request) != self.request_content:
            _refuse()
        digest = "sha256:" + hashlib.sha256(self.inputs_content).hexdigest()
        if (
            request.builder_id != builder
            or request.effective_revision_digest != self.owner_revision_uri
            or request.toolchain_digest != inputs["compiler"]
            or request.source_bundle_digest != digest
        ):
            _refuse()
        return inputs, request

    @classmethod
    def capture(cls, request, *, owner_revision, inputs):
        if cls is not NodeLibraryVerifierRequestDescription:
            raise TypeError("Node verifier descriptions cannot be subclasses")
        if type(owner_revision) is not ContentIdentity:
            raise TypeError("Node verifier description requires an owner revision")
        _inputs(inputs)
        return cls(
            canonical_json_bytes(inputs),
            _request_content(request),
            owner_revision.uri,
        )

    @property
    def inputs(self):
        """Return a fresh dictionary; retained primitive bytes never alias it."""
        return self._validated()[0]

    @property
    def request(self):
        """Return a fresh request, not the caller's mutable Python object."""
        return self._validated()[1]

    @property
    def inputs_identity(self):
        return ContentIdentity.parse_uri(self.request.source_bundle_digest)

    def require_matches(self, request, *, owner_revision):
        self._validated()
        if (
            type(owner_revision) is not ContentIdentity
            or owner_revision.uri != self.owner_revision_uri
            or _request_content(request) != self.request_content
        ):
            _refuse()
