"""Request preimages retain old wire identities without supplying authority."""

import json
import unittest
from dataclasses import replace
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.lifecycle.standard_local import _node_provider_verifier_inputs
from literate_ai.adapters.node_library_verifier_request import (
    MAX_INPUT_BYTES,
    MAX_REQUEST_BYTES,
)
from literate_ai.adapters.node_library_verifier_request import (
    NodeLibraryVerifierRequestDescription as Description,
)
from literate_ai.contracts import canonical_identity
from literate_ai.contracts.identity import canonical_json_bytes
from literate_ai.security import BuildRequest


def identity(name):
    return canonical_identity({"fixture": name})


def fixture(role):
    names = (
        ("acceptance", "artifact", "contract", "oracle", "surface")
        if role == "provider"
        else (
            "policy",
            "project_plan",
            "package_plan",
            "package_result",
            "build_plan",
            "artifact",
            "root_test",
            "packaged_execution",
            "oracle",
        )
    )
    stem = "provider" if role == "provider" else "sdk-project"
    inputs = {name: identity(name).uri for name in names}
    inputs.update(
        schema=f"literate-ai/local-node-{stem}-verifier-inputs@1",
        compiler=identity("compiler").uri,
        node="node:fixture-runtime",
    )
    revision = identity("revision")
    request = BuildRequest(
        revision.uri,
        canonical_identity(inputs).uri,
        f"local-node-{stem}-verifier@1",
        identity("compiler").uri,
        "local-explicit-host-process",
        ("execute-library-verifier",),
        ("verifier-workspace", "stdout", "stderr"),
    )
    return request, revision, inputs


class VerifierRequestDescriptionTests(unittest.TestCase):
    def test_both_original_manifest_and_complete_request_bytes_are_preserved(self):
        for role in ("provider", "root"):
            with self.subTest(role=role):
                request, revision, inputs = fixture(role)
                description = Description.capture(
                    request, owner_revision=revision, inputs=inputs
                )
                self.assertEqual(
                    description.inputs_content, canonical_json_bytes(inputs)
                )
                self.assertEqual(
                    description.request_content, canonical_json_bytes(request.to_dict())
                )
                self.assertEqual(
                    description.inputs_identity.uri, request.source_bundle_digest
                )
                self.assertEqual(description.request, request)
                self.assertIsNot(description.request, request)
                self.assertIsNot(description.request, description.request)
                self.assertNotIn("revision", description.inputs)
                description.require_matches(request, owner_revision=revision)

    def test_provider_description_matches_existing_owner_hash(self):
        request, revision, inputs = fixture("provider")
        surface = SimpleNamespace(identity=identity("surface"))
        scope = SimpleNamespace(
            acceptance=SimpleNamespace(identity=identity("acceptance")),
            export=SimpleNamespace(identity=identity("artifact")),
            contract=SimpleNamespace(
                identity=identity("contract"), library_import_surface=surface
            ),
        )
        compiler = SimpleNamespace(
            identity=identity("compiler"), node=SimpleNamespace(identity=inputs["node"])
        )
        oracle = SimpleNamespace(identity=identity("oracle"))
        description = Description.capture(
            request, owner_revision=revision, inputs=inputs
        )
        self.assertEqual(
            description.inputs_identity,
            _node_provider_verifier_inputs(scope, oracle, compiler),
        )

    def test_caller_objects_and_returned_values_cannot_change_retained_bytes(self):
        request, revision, inputs = fixture("root")
        description = Description.capture(
            request, owner_revision=revision, inputs=inputs
        )
        original = description.request
        inputs["artifact"] = identity("foreign").uri
        object.__setattr__(request, "builder_id", "foreign-builder")
        returned = description.inputs
        returned["node"] = "foreign-runtime"
        returned_request = description.request
        object.__setattr__(returned_request, "allowed_outputs", ("foreign",))
        self.assertEqual(description.request, original)
        self.assertEqual(description.inputs["artifact"], identity("artifact").uri)
        description.require_matches(original, owner_revision=revision)

    def test_crossed_role_compiler_revision_and_source_are_refused(self):
        for role in ("provider", "root"):
            request, revision, inputs = fixture(role)
            for changed in (
                replace(
                    request,
                    builder_id="local-node-sdk-project-verifier@1"
                    if role == "provider"
                    else "local-node-provider-verifier@1",
                ),
                replace(request, toolchain_digest=identity("foreign compiler").uri),
                replace(
                    request, effective_revision_digest=identity("foreign revision").uri
                ),
                replace(request, source_bundle_digest=identity("foreign preimage").uri),
                replace(request, sandbox_profile="unrestricted"),
                replace(
                    request,
                    requested_privileges=("execute-library-verifier", "network"),
                ),
                replace(
                    request,
                    allowed_outputs=(
                        "verifier-workspace",
                        "stdout",
                        "stderr",
                        "foreign",
                    ),
                ),
            ):
                with (
                    self.subTest(role=role, request=changed.builder_id),
                    self.assertRaises(ValueError),
                ):
                    Description.capture(changed, owner_revision=revision, inputs=inputs)
            description = Description.capture(
                request, owner_revision=revision, inputs=inputs
            )
            with self.assertRaises(ValueError):
                description.require_matches(
                    request, owner_revision=identity("other owner")
                )

    def test_closed_fields_and_identities_cannot_be_rescoped_by_rehashing(self):
        request, revision, inputs = fixture("provider")
        for change in (
            {**inputs, "extra": identity("extra").uri},
            {key: value for key, value in inputs.items() if key != "oracle"},
            {**inputs, "oracle": "not-a-content-identity"},
            {
                **inputs,
                "schema": "literate-ai/local-node-sdk-project-verifier-inputs@1",
            },
            {**inputs, "node": "x" * 4097},
        ):
            with self.subTest(keys=sorted(change)), self.assertRaises(ValueError):
                Description.capture(
                    replace(
                        request, source_bundle_digest=canonical_identity(change).uri
                    ),
                    owner_revision=revision,
                    inputs=change,
                )

    def test_subclasses_and_coercion_are_not_description_inputs(self):
        class Text(str):
            pass

        class Mapping(dict):
            pass

        class Derived(Description):
            pass

        class DerivedRequest(BuildRequest):
            pass

        request, revision, inputs = fixture("provider")
        for value in (Mapping(inputs), {**inputs, "oracle": Text(inputs["oracle"])}):
            with self.assertRaises(ValueError):
                Description.capture(request, owner_revision=revision, inputs=value)
        with self.assertRaises(TypeError):
            Derived.capture(request, owner_revision=revision, inputs=inputs)
        with self.assertRaises(TypeError):
            Description.capture(request, owner_revision=revision.uri, inputs=inputs)
        with self.assertRaises(TypeError):
            Description.capture(
                DerivedRequest.from_dict(request.to_dict()),
                owner_revision=revision,
                inputs=inputs,
            )

    def test_byte_caps_precede_parsing_and_noncanonical_or_nested_json_refuses(self):
        request, revision, inputs = fixture("provider")
        content = canonical_json_bytes(request.to_dict())
        with mock.patch("json.loads", side_effect=AssertionError("oversize parsed")):
            with self.assertRaises(ValueError):
                Description(b"x" * (MAX_INPUT_BYTES + 1), content, revision.uri)
        nested = b'{"node":' + b"[" * 1100 + b"0" + b"]" * 1100 + b"}"
        for bad in (
            json.dumps(inputs).encode(),
            b'{"x":NaN}',
            b"\xff",
            nested,
            canonical_json_bytes(inputs)[:-1] + b',"schema":"duplicate"}',
        ):
            with self.subTest(bytes=len(bad)), self.assertRaises(ValueError):
                Description(bad, content, revision.uri)
        with self.assertRaises(ValueError):
            Description(
                canonical_json_bytes(inputs),
                b"x" * (MAX_REQUEST_BYTES + 1),
                revision.uri,
            )

    def test_mutated_description_is_revalidated_before_request_or_data_escape(self):
        request, revision, inputs = fixture("provider")
        description = Description.capture(
            request, owner_revision=revision, inputs=inputs
        )
        object.__setattr__(
            description,
            "inputs_content",
            canonical_json_bytes({**inputs, "oracle": identity("changed").uri}),
        )
        for consume in (
            lambda: description.request,
            lambda: description.inputs,
            lambda: description.inputs_identity,
            lambda: description.require_matches(request, owner_revision=revision),
        ):
            with self.assertRaises(ValueError):
                consume()
