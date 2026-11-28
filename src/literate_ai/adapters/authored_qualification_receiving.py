"""Current authored inputs for model-free reading, never producer execution.

The factory performs its own original importer-file acquisition. A decoded or
replaced passive review cannot issue this lifetime-bound owner. Historical coding
intent is DATA; current SDK, graph, oracle, project review and driver owners remain
mandatory. No coding CLI is selected, probed or supplied as a pretend participant.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field, fields
from pathlib import Path

from literate_ai.adapters.authored_qualification_authority import (
    read_current_authored_qualification_authority,
)
from literate_ai.adapters.authored_qualification_oracles import (
    CurrentAuthoredQualificationOracles,
    read_current_authored_qualification_oracles,
)
from literate_ai.adapters.authored_qualification_planning import (
    _require_output_directory,
    _reviews,
)
from literate_ai.adapters.authored_retained_cargo_review import (
    AuthoredRetainedCargoReviewedFiles,
    read_authored_retained_cargo_review,
)
from literate_ai.adapters.authored_sdk_product_completion import (
    _capture_authored_sdk_products,
    _OriginalAuthoredSdkProducts,
)
from literate_ai.adapters.generation_preparation import (
    LockedComponentModelSelectionAdapter,
)
from literate_ai.adapters.legacy_generation_catalog import (
    read_only_flavor_graph_observations,
)
from literate_ai.adapters.locked_generation_authority import (
    read_only_component_catalog_observations,
)
from literate_ai.adapters.project_validation import validated_project_authority_identity
from literate_ai.adapters.standard_lifecycle_binding import (
    ResolvedStandardProjectLifecycleDriver,
    resolve_standard_project_lifecycle_driver,
)
from literate_ai.adapters.standard_project import (
    FilesystemStandardProjectPlanningAdapter,
)
from literate_ai.contracts import StandardProjectLifecycleDriver
from literate_ai.contracts.authored_qualification_plans import AuthoredQualificationPlan
from literate_ai.contracts.authored_retained_cargo_review import (
    AuthoredRetainedCargoProducerReview,
)
from literate_ai.projects import read_only_project_configuration_parses

_KEY = object()
_ISSUED_CHECKS = {}


def _function_seal(function):
    return (
        function.__code__,
        function.__defaults__,
        function.__kwdefaults__,
        tuple((function.__kwdefaults__ or {}).items()),
    )


def _require_function_seal(function, seal):
    code, defaults, keywords, items = seal
    actual = function.__kwdefaults__
    if (
        function.__code__ is not code
        or function.__defaults__ is not defaults
        or actual is not keywords
        or (actual is not None and type(actual) is not dict)
        or len(actual or {}) != len(items)
        or any(type(key) is not str for key in (actual or {}))
        or any((actual or {}).get(key) is not value for key, value in items)
    ):
        raise ValueError("qualification.authored.original-receiving-inputs-changed")


@dataclass(init=False, frozen=True, slots=True, eq=False)
class ReviewedAuthoredQualificationInputs:
    """Original current read inputs; no constructor from a saved plan or archive."""

    reviewed: AuthoredRetainedCargoReviewedFiles
    producer_review: AuthoredRetainedCargoProducerReview
    plan: AuthoredQualificationPlan
    oracles: CurrentAuthoredQualificationOracles
    binding: ResolvedStandardProjectLifecycleDriver
    _reviewer: object = field(repr=False)
    _native_sdk_inputs: object = field(repr=False)
    _planned_sdk_inputs: object = field(repr=False)
    _original_sdk_products: _OriginalAuthoredSdkProducts | None = field(repr=False)
    _check: object = field(repr=False)

    def __init__(
        self,
        reviewed,
        oracles,
        binding,
        reviewer,
        native_sdk_inputs,
        original_sdk_products,
        check,
        key,
    ):
        if key is not _KEY:
            raise TypeError("qualification.authored.original-receiving-inputs-required")
        for name, value in (
            ("reviewed", reviewed),
            ("producer_review", reviewed.producer_review),
            ("plan", reviewed.producer_review.provider_plan),
            ("oracles", oracles),
            ("binding", binding),
            ("_reviewer", reviewer),
            ("_native_sdk_inputs", native_sdk_inputs),
            ("_planned_sdk_inputs", native_sdk_inputs),
            ("_original_sdk_products", original_sdk_products),
            ("_check", check),
        ):
            object.__setattr__(self, name, value)

    def __copy__(self):
        raise TypeError("qualification.authored.receiving-inputs-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("qualification.authored.receiving-inputs-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("qualification.authored.receiving-inputs-not-serializable")

    def require_unchanged(self):
        record = _ISSUED_CHECKS.get(id(self))
        if record is None or record[0] is not self:
            raise ValueError("qualification.authored.receiving-inputs-expired")
        if (
            type(self) is not ReviewedAuthoredQualificationInputs
            or vars(ReviewedAuthoredQualificationInputs).get("require_unchanged")
            is not _ORIGINAL_REQUIRE
            or self._check is not record[1]
        ):
            raise ValueError("qualification.authored.original-receiving-inputs-changed")
        _require_function_seal(record[1], record[2])
        record[1](self)


_ORIGINAL_REQUIRE = vars(ReviewedAuthoredQualificationInputs).get("require_unchanged")
_ORIGINAL_REQUIRE_SEAL = _function_seal(_ORIGINAL_REQUIRE)


def require_reviewed_authored_qualification_inputs(current):
    """Authenticate original issuance and dispatch, even after method substitution.

    Closed receiving eligibility gates must call this trusted entry rather than
    delegate eligibility to a possibly substituted public method or DATA callback.
    """
    if type(current) is not ReviewedAuthoredQualificationInputs:
        raise TypeError("qualification.authored.original-receiving-inputs-required")
    _require_function_seal(_ORIGINAL_REQUIRE, _ORIGINAL_REQUIRE_SEAL)
    _ORIGINAL_REQUIRE(current)


def require_original_authored_receiving_fields(current):
    """Close original read fields and seals only; this is NOT a currentness grant.

    Full current/native refresh remains mandatory at its existing transaction
    boundary. This fence performs no native read, planning, SDK refresh or clock.
    """
    if type(current) is not ReviewedAuthoredQualificationInputs:
        raise TypeError("qualification.authored.original-receiving-inputs-required")
    _require_function_seal(_ORIGINAL_REQUIRE, _ORIGINAL_REQUIRE_SEAL)
    record = _ISSUED_CHECKS.get(id(current))
    if record is None or record[0] is not current:
        raise ValueError("qualification.authored.receiving-inputs-expired")
    if current._check is not record[1]:
        raise ValueError("qualification.authored.original-receiving-inputs-changed")
    _require_function_seal(record[1], record[2])
    _require_function_seal(record[3], record[4])
    record[3]()


def require_authored_qualification_read_inputs(current):
    """Dispatch after the caller's existing closed owner-type gate.

    Preserve the original producer path. New receiving owners always use the
    authenticated entry, never a public method selected from mutable DATA.
    """
    if type(current) is ReviewedAuthoredQualificationInputs:
        require_reviewed_authored_qualification_inputs(current)
    else:
        current.require_unchanged()


def authored_qualification_read_intent(current):
    if type(current) is ReviewedAuthoredQualificationInputs:
        require_original_authored_receiving_fields(current)
        return (
            current.producer_review.coding_provider,
            current.producer_review.pipeline_model,
        )
    return current.standard.coding_cli.name, current._pipeline_model


def authored_qualification_read_field_names(current):
    if type(current) is ReviewedAuthoredQualificationInputs:
        require_original_authored_receiving_fields(current)
        return (
            "plan",
            "oracles",
            "binding",
            "reviewed",
            "producer_review",
            "_reviewer",
            "_native_sdk_inputs",
            "_planned_sdk_inputs",
            "_original_sdk_products",
            "_check",
        )
    return (
        "plan",
        "oracles",
        "standard",
        "binding",
        "_reviewer",
        "_coding_selector",
        "_pipeline_model",
        "_native_sdk_inputs",
        "_planned_sdk_inputs",
    )


@contextmanager
def open_reviewed_authored_qualification_inputs(
    importer_root: Path,
    *,
    binding_path,
    reviewed_binding,
    plan_path,
    gate_policy_path,
    test_inventory_path,
    producer_review_path,
    reviewed_producer,
    provider_root: Path,
    selection,
    configured_store_id,
    profile_path="litai/qualification.json",
    output_root="litai/qualification",
    native_sdk_inputs=None,
    max_review_file_bytes=256 * 1024**2,
    max_review_total_bytes=1024**3,
    reviewer=validated_project_authority_identity,
    binding_resolver=resolve_standard_project_lifecycle_driver,
):
    """Read original independently approved intent, then rejoin actual authority.

    Independent paths, BlobRefs, provider selection and logical store are operator
    inputs. Never accept a caller-created ReviewedFiles as issuance. SDK inputs
    must already come from their actual native owner; this read scope acquires no
    source, builds no SDK, executes no coding CLI and grants no publication rights.
    Receiving transactions retain their original absolute operation deadlines.
    """
    reviewed = read_authored_retained_cargo_review(
        importer_root,
        binding_path=binding_path,
        reviewed_binding=reviewed_binding,
        plan_path=plan_path,
        gate_policy_path=gate_policy_path,
        test_inventory_path=test_inventory_path,
        producer_review_path=producer_review_path,
        reviewed_producer=reviewed_producer,
        maximum_file_bytes=max_review_file_bytes,
        maximum_total_bytes=max_review_total_bytes,
    )
    review = reviewed.producer_review
    if type(review) is not AuthoredRetainedCargoProducerReview:
        raise TypeError("qualification.authored.independent-producer-review-required")
    review.require_binding(reviewed.binding)
    if (
        configured_store_id != reviewed.binding.evidence_store_id
        or profile_path != review.profile_path
        or output_root != review.provider_plan.output_root
    ):
        raise ValueError("qualification.authored.receiving-selection-mismatch")
    reviewed_identity = reviewed.identity
    review_identity = review.identity
    plan = review.provider_plan
    plan_identity = plan.identity
    provider_root = Path(provider_root).absolute()
    authority = read_current_authored_qualification_authority(provider_root, selection)
    if authority.project.root != provider_root:
        raise ValueError("qualification.authored.current-provider-project-required")
    oracles = read_current_authored_qualification_oracles(authority, profile_path)
    driver = authority.project.definition.lifecycle_driver
    if not isinstance(driver, StandardProjectLifecycleDriver):
        raise ValueError("qualification.authored.standard_driver_required")
    binding = binding_resolver(driver)
    if (
        type(binding) is not ResolvedStandardProjectLifecycleDriver
        or binding.driver != driver
    ):
        raise TypeError("original resolved Standard binding required")
    sdk_products = (
        _capture_authored_sdk_products(native_sdk_inputs)
        if native_sdk_inputs is not None
        else None
    )
    active = True
    owner = None
    original_fields = ()
    check_seal = None
    close_seal = None

    def close_fields():
        # Pure closing comparisons after all callbacks and native parse-frame
        # closing. Never manufacture fresh expectations from an archive or copy.
        record = _ISSUED_CHECKS.get(id(owner))
        if not active or record is None or record[0] is not owner:
            raise ValueError("qualification.authored.receiving-inputs-expired")
        if (
            record[1] is not check
            or record[2] is not check_seal
            or record[3] is not close_fields
            or record[4] is not close_seal
        ):
            raise ValueError("qualification.authored.original-receiving-inputs-changed")
        if (
            vars(ReviewedAuthoredQualificationInputs).get("require_unchanged")
            is not _ORIGINAL_REQUIRE
        ):
            raise ValueError("qualification.authored.original-receiving-inputs-changed")
        _require_function_seal(_ORIGINAL_REQUIRE, _ORIGINAL_REQUIRE_SEAL)
        _require_function_seal(check, check_seal)
        _require_function_seal(close_fields, close_seal)
        if any(
            getattr(value, name) is not original
            for value, name, original in original_fields
        ) or (
            reviewed._captured_identity() != reviewed_identity
            or review.identity != review_identity
            or plan.identity != plan_identity
        ):
            raise ValueError("qualification.authored.original-receiving-inputs-changed")

    def check(candidate):
        if not active or candidate is not owner:
            raise ValueError("qualification.authored.receiving-inputs-expired")
        if type(candidate) is not ReviewedAuthoredQualificationInputs:
            raise TypeError("qualification.authored.original-receiving-inputs-required")
        _require_function_seal(close_fields, close_seal)
        close_fields()
        with (
            read_only_project_configuration_parses(isolated=True),
            read_only_component_catalog_observations(isolated=True),
            read_only_flavor_graph_observations(),
        ):
            reviewed.require_unchanged()
            review.require_binding(reviewed.binding)
            oracles.require_unchanged()
            binding.require_unchanged()
            execution = FilesystemStandardProjectPlanningAdapter(
                native_sdk_inputs=native_sdk_inputs,
                model_selector=LockedComponentModelSelectionAdapter(
                    pipeline_model=review.pipeline_model
                ),
            ).plan_for_coding_cli(
                authority.locked,
                coding_cli=review.coding_provider,
            )
            if (
                authority.origin != plan.origin
                or oracles.identity != plan.oracle_set_identity
                or oracles.profile.identity != plan.profile_identity
                or oracles.profile.minimum_clean_runs != plan.minimum_clean_runs
                or execution != plan.execution_plan
                or binding.driver.identity != plan.driver_identity
                or binding.policy.identity != plan.lifecycle_policy_identity
                or binding.distribution.identity != plan.framework_distribution_identity
                or _reviews(oracles, reviewer) != plan.project_reviews
            ):
                raise ValueError("qualification.authored.receiving-plan-changed")
            _require_output_directory(provider_root, plan.output_root)
            oracles.require_unchanged()
            if sdk_products is not None:
                sdk_products.require_original_files()
            reviewed.require_unchanged()
        # Reviewer and parse-frame callbacks have all returned. Reopen the
        # original framework binding before the final pure field fence.
        binding.require_unchanged()
        _require_function_seal(close_fields, close_seal)
        close_fields()

    check_seal = _function_seal(check)
    close_seal = _function_seal(close_fields)
    owner = ReviewedAuthoredQualificationInputs(
        reviewed,
        oracles,
        binding,
        reviewer,
        native_sdk_inputs,
        sdk_products,
        check,
        _KEY,
    )
    try:
        _ISSUED_CHECKS[id(owner)] = (owner, check, check_seal, close_fields, close_seal)
        original_fields = tuple(
            (value, item.name, getattr(value, item.name))
            for value in (owner, reviewed, review, plan, oracles, authority, binding)
            for item in fields(value)
        )
        _require_function_seal(check, check_seal)
        check(owner)
        yield owner
        # Dispatch the captured sealed check, never the mutable public method.
        _require_function_seal(check, check_seal)
        check(owner)
    finally:
        active = False
        _ISSUED_CHECKS.pop(id(owner), None)


def _publish_authored_read_port_binder():
    """Publish bounded consumer dispatch from original helper implementations.

    Consumer-private dispatchers and the existing private module/native roots are
    trusted framework code. Public helper publications are authenticated DATA
    here; callers never store or accept their own guard callbacks on an owner.
    """
    namespace = globals()
    ports = (
        (
            "current",
            "require_authored_qualification_read_inputs",
            require_authored_qualification_read_inputs,
        ),
        (
            "full",
            "require_reviewed_authored_qualification_inputs",
            require_reviewed_authored_qualification_inputs,
        ),
        (
            "pure",
            "require_original_authored_receiving_fields",
            require_original_authored_receiving_fields,
        ),
        (
            "intent",
            "authored_qualification_read_intent",
            authored_qualification_read_intent,
        ),
        (
            "fields",
            "authored_qualification_read_field_names",
            authored_qualification_read_field_names,
        ),
        (
            "open",
            "open_reviewed_authored_qualification_inputs",
            open_reviewed_authored_qualification_inputs,
        ),
    )
    original_type = ReviewedAuthoredQualificationInputs
    functions = tuple((function, _function_seal(function)) for _, _, function in ports)
    factory = open_reviewed_authored_qualification_inputs
    wrapped = factory.__wrapped__
    wrapped_seal = _function_seal(wrapped)
    selected = {operation: function for operation, _, function in ports}

    def guard():
        if (
            namespace.get("ReviewedAuthoredQualificationInputs") is not original_type
            or any(namespace.get(name) is not function for _, name, function in ports)
            or factory.__wrapped__ is not wrapped
        ):
            raise ValueError("qualification.authored.original-read-ports-changed")
        for function, seal in (*functions, (wrapped, wrapped_seal)):
            _require_function_seal(function, seal)
        if vars(original_type).get("require_unchanged") is not _ORIGINAL_REQUIRE:
            raise ValueError("qualification.authored.original-read-ports-changed")
        _require_function_seal(_ORIGINAL_REQUIRE, _ORIGINAL_REQUIRE_SEAL)

    @contextmanager
    def opened(*args, **kwargs):
        guard()
        with selected["open"](*args, **kwargs) as current:
            guard()
            yield current
            guard()
        guard()

    def bind():
        guard()

        def dispatch(operation, *args, **kwargs):
            guard()
            if operation == "open":
                return opened(*args, **kwargs)
            if operation not in selected:
                raise TypeError("qualification.authored.read-operation-required")
            result = selected[operation](*args, **kwargs)
            guard()
            return result

        return dispatch

    return bind


_bind_authored_qualification_read_ports = _publish_authored_read_port_binder()
del _publish_authored_read_port_binder
