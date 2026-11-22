"""Record a local build witness for an independently selected authored SDK."""

from literate_ai.adapters.authored_qualification_authority import (
    CurrentAuthoredQualificationAuthority,
)
from literate_ai.adapters.native_sdk_completion_cache import cache_record_ref
from literate_ai.adapters.native_sdk_completion_resolution import (
    require_resolution_relationships,
    resolution_document,
)
from literate_ai.adapters.native_sdk_completion_security import security_refs
from literate_ai.adapters.native_sdk_consumer import NativeSdkConsumerInputs
from literate_ai.adapters.native_sdk_source_build import NativeSdkSourceBuildService
from literate_ai.adapters.standard_lifecycle_binding import (
    resolve_standard_project_lifecycle_driver,
)
from literate_ai.contracts import canonical_identity
from literate_ai.security import SecurityPolicy


def sdk_completion_policy(standard):
    return SecurityPolicy(
        canonical_identity(
            {
                "policy": "standard-native-sdk-build@1",
                "standard_policy": standard.policy.identity.uri,
            }
        ).uri
    )


def completion_header(authority, standard, policy):
    snapshot = authority.locked
    intelligence = authority.project.definition.source_intelligence
    return {
        "schema": "literate-ai/authored-sdk-local-completion@1",
        "origin": authority.origin.to_dict(),
        "locked_authority": snapshot.authority.identity.to_dict(),
        "catalog_audit": snapshot.catalog_audit_identity.to_dict(),
        "input_closure": snapshot.input_closure_identity,
        "standard": standard.trust_binding.to_dict(),
        "security_policy": policy.policy_digest,
        "source_intelligence_policy": intelligence.identity.to_dict(),
    }


def record_authored_sdk_completion(authority, owner):
    if (
        type(authority) is not CurrentAuthoredQualificationAuthority
        or type(owner) is not NativeSdkConsumerInputs
    ):
        raise TypeError(
            "SDK completion requires authored authority and completed producer inputs"
        )
    if owner.snapshot is not authority.locked or not owner._inputs:
        raise ValueError(
            "SDK completion requires the selected project's completed builds"
        )
    definition = authority.project.definition
    standard = resolve_standard_project_lifecycle_driver(definition.lifecycle_driver)
    policy = sdk_completion_policy(standard)
    store = owner._inputs[0][0].store

    def collect():
        authority.require_unchanged()
        standard.require_unchanged()
        owner.require_unchanged()
        rows = []
        baseline = owner._inputs[0][0].revocations()
        for service, binding in owner._inputs:
            if (
                type(service) is not NativeSdkSourceBuildService
                or service.snapshot is not owner.snapshot
                or service.store is not store
                or service.revocations() != baseline
                or service.policy != policy
                or service.source_intelligence_policy != definition.source_intelligence
            ):
                raise ValueError(
                    "SDK producer differs from current authored build policy"
                )
            build = service.completed_result()
            selection = service.selection
            if build != binding.build or selection != build.selection:
                raise ValueError("SDK producer differs from completed consumer binding")
            tools = service.planner.tools
            if tuple(tools) != selection.recipe.tools:
                raise ValueError("SDK producer tool selection changed")
            for tool in tools.values():
                tool.require_unchanged()
            require_resolution_relationships(
                build.resolution,
                selection=selection,
                toolchains=tuple(tool.toolchain_identity for tool in tools.values()),
            )
            rows.append(
                {
                    "selection": selection.identity.to_dict(),
                    "binding": binding.to_dict(),
                    "security": security_refs(store, build.resolution),
                    "resolution": resolution_document(build.resolution),
                    "cache_record": cache_record_ref(store, build.resolution).to_dict(),
                }
            )
        return {
            **completion_header(authority, standard, policy),
            "builds": rows,
            "revocations": baseline.to_dict(),
        }

    document = collect()
    reference = store.put_manifest(document)
    if collect() != document or store.get_manifest(reference) != document:
        raise ValueError("SDK completion changed while recording the local witness")
    return reference
