"""Private original SDK product bytes retained before consumer execution.

The original live SDK owner must still refresh before the final local comparisons.
These facts reuse its existing CAS products, never revive producer workspaces,
copy an SDK tree or authorize source acquisition, admission or execution.
"""

import math
import time
from dataclasses import asdict, dataclass, field

from literate_ai.adapters.exclusive_directory import directory_node
from literate_ai.adapters.native_sdk_consumer import NativeSdkConsumerInputs
from literate_ai.adapters.native_sdk_source_build import NativeSdkSourceBuildService
from literate_ai.contracts.identity import canonical_identity
from literate_ai.storage.cas import FileSystemCAS

_KEY = object()


def _product_values(binding):
    product = binding.build.product
    return canonical_identity(
        {
            "binding": binding.to_dict(),
            "snapshot": product.snapshot.to_dict(),
            "verification": asdict(product.verification),
        }
    )


@dataclass(init=False, frozen=True, slots=True, eq=False)
class _OriginalAuthoredSdkProducts:
    _owner: object = field(repr=False)
    _refs: tuple = field(repr=False)
    _values: tuple = field(repr=False)
    _stores: tuple = field(repr=False)
    _nodes: tuple = field(repr=False)
    _sources: tuple = field(repr=False)

    def __init__(self, owner, refs, values, stores, nodes, sources, key):
        if key is not _KEY:
            raise TypeError("qualification.authored.original-sdk-products-required")
        for name, value in (
            ("_owner", owner),
            ("_refs", refs),
            ("_values", values),
            ("_stores", stores),
            ("_nodes", nodes),
            ("_sources", sources),
        ):
            object.__setattr__(self, name, value)

    def __copy__(self):
        raise TypeError("qualification.authored.sdk-products-not-copyable")

    def __deepcopy__(self, memo):
        raise TypeError("qualification.authored.sdk-products-not-copyable")

    def __reduce_ex__(self, protocol):
        raise TypeError("qualification.authored.sdk-products-not-serializable")

    def _require_fields(self):
        if any(getattr(owner, name) is not value for owner, name, value in self._refs):
            raise ValueError("qualification.authored.original-sdk-products-changed")
        if any(_product_values(binding) != value for binding, value in self._values):
            raise ValueError("qualification.authored.original-sdk-products-changed")
        if any(
            store.root != root or store.blob_root != blobs
            for store, root, blobs, _references in self._stores
        ):
            raise ValueError("qualification.authored.original-sdk-store-changed")
        if len(self._owner._blob_sources) != len(self._sources) or any(
            self._owner._blob_sources.get(key) is not store
            for key, store in self._sources
        ):
            raise ValueError("qualification.authored.original-sdk-sources-changed")
        for path, node in self._nodes:
            if directory_node(path) != node:
                raise ValueError("qualification.authored.original-sdk-store-changed")

    def require_original_files(self):
        self._require_fields()
        for store, _root, _blob_root, references in self._stores:
            for reference in references:
                # Existing streaming same-descriptor verification; never put,
                # reacquire source, inspect native images or run a producer.
                FileSystemCAS.verify(store, reference)
        self._require_fields()

    def refresh_current(self, *, deadline):
        if (
            type(deadline) not in (int, float)
            or not math.isfinite(deadline)
            or deadline <= 0
        ):
            raise ValueError("qualification.authored.sdk-refresh-deadline-invalid")

        def within_deadline():
            if time.monotonic() >= deadline:
                raise ValueError("qualification.authored.sdk-refresh-deadline-expired")

        within_deadline()
        self._require_fields()
        self._owner.require_unchanged()
        within_deadline()
        self.require_original_files()
        within_deadline()


def _capture_authored_sdk_products(owner):
    if type(owner) is not NativeSdkConsumerInputs:
        raise TypeError("qualification.authored.original-sdk-owner-required")
    owner.require_unchanged()
    refs = [
        (owner, name, getattr(owner, name))
        for name in ("snapshot", "_services", "_inputs", "_blob_sources")
    ]
    values, stores, nodes = [], [], {}
    for service, binding in owner._inputs:
        if type(service) is not NativeSdkSourceBuildService:
            raise TypeError("qualification.authored.original-sdk-service-required")
        build = binding.build
        product = build.product
        store = service.store
        if type(store) is not FileSystemCAS or service._result is not build:
            raise TypeError("qualification.authored.original-sdk-product-required")
        refs.extend(
            (value, name, getattr(value, name))
            for value, names in (
                (service, ("snapshot", "selection", "store", "builder", "_result")),
                (binding, ("build",)),
                (build, ("selection", "resolution", "product")),
                (
                    product,
                    (
                        "verification",
                        "snapshot",
                        "snapshot_blob",
                        "runtime_observation",
                        "result_blob",
                    ),
                ),
            )
            for name in names
        )
        values.append((binding, _product_values(binding)))
        # The exact list already verified by the actual completed_result owner.
        references = (
            product.snapshot_blob,
            product.runtime_observation,
            product.result_blob,
            *(item.blob for item in product.snapshot.files),
        )
        stores.append((store, store.root, store.blob_root, references))
        for path in (store.root, store.blob_root.parent, store.blob_root):
            nodes[path] = directory_node(path)
    result = _OriginalAuthoredSdkProducts(
        owner,
        tuple(refs),
        tuple(values),
        tuple(stores),
        tuple(nodes.items()),
        tuple(owner._blob_sources.items()),
        _KEY,
    )
    owner.require_unchanged()
    result.require_original_files()
    return result
