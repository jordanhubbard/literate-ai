"""Join fresh importer review and measured tools to original authored products.

A saved review or package observation cannot recreate this live scope. This
preflight validates immutable native package manifests; it grants no output
exclusions, publication, consumer execution or admission permission.
"""

from collections.abc import Callable
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

from literate_ai.adapters.authored_qualification_planning import (
    CurrentAuthoredQualificationPlan,
)
from literate_ai.adapters.authored_qualification_receiving import (
    ReviewedAuthoredQualificationInputs,
    _bind_authored_qualification_read_ports,
)
from literate_ai.adapters.authored_retained_cargo_products import (
    CurrentAuthoredRetainedCargoProducts,
    _AuthoredRetainedCargoProductsSession,
    _open_authored_retained_cargo_products_session,
    open_authored_retained_cargo_products,
)
from literate_ai.adapters.authored_retained_cargo_review import (
    AuthoredRetainedCargoReviewedFiles,
    read_authored_retained_cargo_review,
)
from literate_ai.adapters.builders.cargo import CargoToolchain
from literate_ai.adapters.builders.rust import RustToolchain
from literate_ai.adapters.retained_cargo_plan import (
    _bound_cargo_package_exports,
    _verify_bound_cargo_package_exports,
)
from literate_ai.adapters.retained_cargo_test_execution import (
    _require_native_completion_deadline,
)
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import ContentIdentity, canonical_identity

_read_ports = _bind_authored_qualification_read_ports()
del _bind_authored_qualification_read_ports


@dataclass(frozen=True, slots=True)
class CurrentAuthoredRetainedCargoInputs:
    """Original live review/tool/provider join, never a decoded grant."""

    reviewed: AuthoredRetainedCargoReviewedFiles
    products: CurrentAuthoredRetainedCargoProducts
    cargo: CargoToolchain
    rustc: RustToolchain
    _check: Callable[[object], None] = field(repr=False, compare=False)

    def require_unchanged(self):
        self._check(self)

    @property
    def identity(self):
        self.require_unchanged()
        return canonical_identity(
            {
                "schema": "literate-ai/authored-retained-cargo-current-inputs@1",
                "reviewed": self.reviewed.identity.uri,
                "provider_reference": self.products.reference.identity.uri,
                "selected_run": self.products.selected_run_identity.uri,
                "exports": self.products.exports.identity.uri,
                "cargo": self.cargo.identity,
                "rustc": self.rustc.identity,
            }
        )


_INPUT_SESSION_KEY = object()


@dataclass(init=False, frozen=True, slots=True, eq=False)
class _AuthoredRetainedCargoInputsSession:
    inputs: CurrentAuthoredRetainedCargoInputs = field(repr=False)
    products_session: _AuthoredRetainedCargoProductsSession = field(repr=False)

    def __init__(self, inputs, products_session, key):
        if key is not _INPUT_SESSION_KEY:
            raise TypeError("retained.cargo.authored-original-input-session-required")
        object.__setattr__(self, "inputs", inputs)
        object.__setattr__(self, "products_session", products_session)

    def __copy__(self):
        raise TypeError("retained.cargo.authored-input-session-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("retained.cargo.authored-input-session-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("retained.cargo.authored-input-session-not-serializable")


@contextmanager
def open_authored_retained_cargo_inputs(
    project_root: Path,
    *,
    binding_path: str,
    reviewed_binding: BlobRef,
    plan_path: str,
    gate_policy_path: str,
    test_inventory_path: str,
    provider_current: CurrentAuthoredQualificationPlan,
    configured_store_id: str,
    consumer_cargo: CargoToolchain,
    consumer_rustc: RustToolchain,
    archive_payload: bytes,
    native_sdk_inputs=None,
    producer_review_path=None,
    reviewed_producer=None,
    max_review_file_bytes: int = 256 * 1024**2,
    max_review_total_bytes: int = 1024**3,
    max_archive_bytes: int = 256 * 1024**2,
    max_package_bytes: int = 256 * 1024**2,
    max_entries: int = 100_000,
):
    """Reopen operator-reviewed bytes before joining actual current provider data.

    Root, reviewed binding reference, paths, provider plan, logical store and
    native tool pair are independent operator inputs. The transport must bound
    allocation before supplying archive_payload. No candidate file selects its
    own review identity, trust root, endpoint, tools or execution permission.
    Review limits bound all five files and their aggregate before pin/decode,
    including the selected plan and the current project manifest.
    """
    with _open_authored_retained_cargo_inputs_session(
        project_root,
        binding_path=binding_path,
        reviewed_binding=reviewed_binding,
        plan_path=plan_path,
        gate_policy_path=gate_policy_path,
        test_inventory_path=test_inventory_path,
        provider_current=provider_current,
        configured_store_id=configured_store_id,
        consumer_cargo=consumer_cargo,
        consumer_rustc=consumer_rustc,
        archive_payload=archive_payload,
        native_sdk_inputs=native_sdk_inputs,
        **(
            {
                "producer_review_path": producer_review_path,
                "reviewed_producer": reviewed_producer,
            }
            if producer_review_path is not None or reviewed_producer is not None
            else {}
        ),
        max_review_file_bytes=max_review_file_bytes,
        max_review_total_bytes=max_review_total_bytes,
        max_archive_bytes=max_archive_bytes,
        max_package_bytes=max_package_bytes,
        max_entries=max_entries,
        _retain_products=False,
    ) as owner:
        yield owner


@contextmanager
def _open_authored_retained_cargo_inputs_session(
    project_root: Path,
    *,
    binding_path: str,
    reviewed_binding: BlobRef,
    plan_path: str,
    gate_policy_path: str,
    test_inventory_path: str,
    provider_current: CurrentAuthoredQualificationPlan,
    configured_store_id: str,
    consumer_cargo: CargoToolchain,
    consumer_rustc: RustToolchain,
    archive_payload: bytes,
    native_sdk_inputs=None,
    producer_review_path=None,
    reviewed_producer=None,
    max_review_file_bytes: int = 256 * 1024**2,
    max_review_total_bytes: int = 1024**3,
    max_archive_bytes: int = 256 * 1024**2,
    max_package_bytes: int = 256 * 1024**2,
    max_entries: int = 100_000,
    _retain_products=True,
    _operation_deadline=None,
):
    """Reopen operator-reviewed bytes before joining actual current provider data.

    Root, reviewed binding reference, paths, provider plan, logical store and
    native tool pair are independent operator inputs. The transport must bound
    allocation before supplying archive_payload. No candidate file selects its
    own review identity, trust root, endpoint, tools or execution permission.
    Review limits bound all five files and their aggregate before pin/decode,
    including the selected plan and the current project manifest.
    """
    if type(_retain_products) is not bool:
        raise TypeError("retained.cargo.authored-product-retention-mode-invalid")
    if (
        (
            type(provider_current) is not CurrentAuthoredQualificationPlan
            and type(provider_current) is not ReviewedAuthoredQualificationInputs
        )
        or type(consumer_cargo) is not CargoToolchain
        or type(consumer_rustc) is not RustToolchain
    ):
        raise TypeError("retained.cargo.authored-current-provider-and-tools-required")
    if (
        any(
            type(n) is not int or n <= 0
            for n in (
                max_review_file_bytes,
                max_review_total_bytes,
                max_archive_bytes,
                max_package_bytes,
                max_entries,
            )
        )
        or max_review_file_bytes > 256 * 1024**2
        or not max_review_file_bytes <= max_review_total_bytes <= 1024**3
        or max_archive_bytes > 256 * 1024**2
        or max_package_bytes > max_archive_bytes
        or max_entries > 100_000
    ):
        raise ValueError("retained.cargo.authored-input-limits-invalid")

    def require_deadline():
        if _operation_deadline is not None:
            _require_native_completion_deadline(_operation_deadline)

    require_deadline()
    if type(provider_current) is ReviewedAuthoredQualificationInputs:
        if producer_review_path is None or reviewed_producer is None:
            raise ValueError("retained.cargo.authored-producer-review-required")
        _read_ports("current", provider_current)
    reviewed = read_authored_retained_cargo_review(
        project_root,
        binding_path=binding_path,
        reviewed_binding=reviewed_binding,
        plan_path=plan_path,
        gate_policy_path=gate_policy_path,
        test_inventory_path=test_inventory_path,
        **(
            {
                "producer_review_path": producer_review_path,
                "reviewed_producer": reviewed_producer,
            }
            if producer_review_path is not None or reviewed_producer is not None
            else {}
        ),
        maximum_file_bytes=max_review_file_bytes,
        maximum_total_bytes=max_review_total_bytes,
    )
    binding, plan = reviewed.binding, reviewed.plan.common
    cargo_identity = ContentIdentity.parse_uri(consumer_cargo.identity)
    rustc_identity = ContentIdentity.parse_uri(consumer_rustc.identity)
    if (
        plan.cargo_identity != cargo_identity
        or plan.rustc_identity != rustc_identity
        or not {cargo_identity, rustc_identity} <= set(reviewed.policy.toolchains)
    ):
        raise ValueError("retained.cargo.authored-consumer-tool-mismatch")
    reviewed_identity = reviewed.identity
    active = True

    def consumer_current():
        require_deadline()
        reviewed.require_unchanged()
        require_deadline()
        consumer_cargo.require_unchanged()
        require_deadline()
        consumer_rustc.require_unchanged()
        require_deadline()
        if reviewed.identity != reviewed_identity:
            raise ValueError("retained.cargo.authored-reviewed-inputs-changed")
        require_deadline()
        if type(provider_current) is ReviewedAuthoredQualificationInputs:
            _read_ports("pure", provider_current)
            original = provider_current.reviewed
            original.require_unchanged()
            if (
                reviewed.project.root != original.project.root
                or reviewed._context != original._context
                or reviewed._captured_identity() != original._captured_identity()
            ):
                raise ValueError(
                    "retained.cargo.authored-original-reviewed-inputs-mismatch"
                )
            _read_ports("pure", provider_current)
            require_deadline()

    consumer_current()
    try:
        with (
            _open_authored_retained_cargo_products_session
            if _retain_products
            else open_authored_retained_cargo_products
        )(
            provider_current,
            binding,
            configured_store_id=configured_store_id,
            archive_payload=archive_payload,
            native_sdk_inputs=native_sdk_inputs,
            max_bytes=max_archive_bytes,
        ) as products:
            if _retain_products:
                if type(products) is not _AuthoredRetainedCargoProductsSession:
                    raise TypeError(
                        "retained.cargo.authored-original-product-session-required"
                    )
                products_session = products
                products = products_session.products
            if type(products) is not CurrentAuthoredRetainedCargoProducts:
                raise TypeError("retained.cargo.authored-original-products-required")
            consumer_current()
            products.require_unchanged()
            require_deadline()
            if (
                sum(reference.size for reference, _ in products.blobs)
                > max_package_bytes
            ):
                raise ValueError("retained.cargo.authored-package-byte-limit")
            packages = _bound_cargo_package_exports(
                plan, products.exports, binding.destinations
            )
            _verify_bound_cargo_package_exports(
                plan,
                products.exports,
                packages,
                dict(binding.destinations),
                {item.path: item for item in plan.manifests},
                dict(products.blobs),
                max_package_bytes=max_package_bytes,
                max_entries=max_entries,
            )

            def check(candidate):
                if not active:
                    raise ValueError("retained.cargo.authored-input-owner-expired")
                if candidate is not owner:
                    raise ValueError("retained.cargo.authored-original-inputs-required")
                consumer_current()
                products.require_unchanged()
                require_deadline()
                consumer_current()

            owner = CurrentAuthoredRetainedCargoInputs(
                reviewed, products, consumer_cargo, consumer_rustc, check
            )
            owner.require_unchanged()
            if _retain_products:
                products_session.publication.require_original_files()
                yield _AuthoredRetainedCargoInputsSession(
                    owner, products_session, _INPUT_SESSION_KEY
                )
            else:
                yield owner
            owner.require_unchanged()
        # Provider scope closes last: its pinned retirement namespace fence must
        # succeed before this operation can return a usable completion outcome.
    finally:
        active = False
