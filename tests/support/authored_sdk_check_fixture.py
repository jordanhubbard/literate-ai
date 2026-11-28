"""Build consumer review inputs for SDK and archive refusals at the public CLI."""

from dataclasses import replace
from pathlib import Path

from literate_ai.contracts.authored_retained_cargo_review import (
    AuthoredRetainedCargoProducerReview,
)
from literate_ai.contracts.identity import canonical_json_bytes
from tests.critical import test_authored_retained_cargo_review as review_cases
from tests.support.fixtures_retained_cargo_scratch import scratch_review_fixture


def check_arguments(
    scope, base, *, provider_root, provider_component, sdk_args, provider_plan
):
    base.mkdir()
    old = scope.enter_context(scratch_review_fixture(base.resolve(strict=True)))
    helper = review_cases.AuthoredRetainedCargoReviewTests("runTest")
    consumer = old.project.root
    binding = helper.fixture(old)
    # Receiving requires an independent producer review of the actual plan.
    provider = replace(
        binding.provider_reference,
        origin=provider_plan.origin,
        plan_identity=provider_plan.identity,
    )
    binding = replace(binding, provider_reference=provider)
    reference = helper.write_binding(consumer, binding)
    review = AuthoredRetainedCargoProducerReview(
        binding.importer_project_id,
        binding.identity,
        binding.evidence_store_id,
        provider.identity,
        provider_plan,
        "inherited-session",
        None,
        "litai/qualification.json",
    )
    review_bytes = canonical_json_bytes(review.to_dict())
    (consumer / "review/producer.json").write_bytes(review_bytes)
    review_reference = review_cases._json_blob(review_bytes)
    archive = base / "incorrect.archive"
    archive.write_bytes(b"unreviewed transport bytes")
    return [
        "--json",
        "project",
        "retained-cargo",
        "check",
        "--project",
        str(consumer),
        "--binding",
        "review/binding.json",
        "--reviewed-binding",
        reference.identity,
        "--binding-size",
        str(reference.size),
        "--plan",
        "review/plan.json",
        "--gate-policy",
        "review/policy.json",
        "--tests",
        "review/tests.json",
        "--producer-review",
        "review/producer.json",
        "--reviewed-producer-review",
        review_reference.identity,
        "--producer-review-size",
        str(review_reference.size),
        "--store-id",
        binding.evidence_store_id,
        "--provider-project",
        str(provider_root),
        "--provider-component",
        provider_component,
        "--provider-profile",
        "litai/qualification.json",
        "--old-output-file-bytes",
        "1048576",
        "--old-output-total-bytes",
        "4194304",
        "--archive",
        str(archive),
        "--provider-flavor",
        "+python",
        "--provider-flavor",
        sdk_args.flavor[1],
        "--sdk-cache",
        str(Path(sdk_args.sdk_cache)),
        "--sdk-revocations",
        str(sdk_args.sdk_revocations),
        "--sdk-completion",
        sdk_args.sdk_completion,
        "--sdk-completion-size",
        str(sdk_args.sdk_completion_size),
    ]
