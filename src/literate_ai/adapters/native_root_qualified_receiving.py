"""Explicit local genuine V2 receiving composition for one consumer operation.

The consumer lifecycle lock is owned by the caller. Existing V2 wrapper locks
are acquired in sorted distinct importer order and remain fail-fast; this is not
globally sorted all-project locking and never bypasses or reenters a wrapper.
"""

import json
from contextlib import ExitStack, contextmanager
from contextvars import ContextVar
from dataclasses import asdict
from pathlib import Path
from types import MappingProxyType, MethodType

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.component_lock_planning import _asset_local_path
from literate_ai.adapters.lifecycle_lock import project_lifecycle_lock
from literate_ai.adapters.locked_generation_authority import (
    FilesystemLockedGenerationAuthorityReader,
)
from literate_ai.adapters.native_root_external_libraries import (
    ExternalQualifiedLibraryError,
)
from literate_ai.adapters.native_root_external_runtime import (
    _selected_asset,
    borrow_root_qualified_library_inputs,
    require_qualified_library_inputs,
)
from literate_ai.adapters.native_root_qualified_provider import (
    hold_native_root_qualified_provider,
)
from literate_ai.adapters.native_root_qualified_receiving_config import (
    QualifiedReceiverConfiguration,
    _overlap,
    local_absolute_path,
)
from literate_ai.adapters.retained_cargo_current import _unique_object
from literate_ai.adapters.retained_cargo_current_v2 import (
    compose_retained_cargo_current_inputs_v2,
)
from literate_ai.adapters.retained_cargo_files_v2 import read_retained_cargo_files_v2
from literate_ai.adapters.retained_cargo_materialization_v2 import (
    materialize_retained_cargo_archive_v2,
)
from literate_ai.adapters.retained_cargo_review_v2 import read_retained_cargo_review_v2
from literate_ai.adapters.retained_cargo_scratch_v2 import (
    reserve_retained_cargo_scratch_v2,
)
from literate_ai.adapters.retained_cargo_wrapper_v2 import (
    retained_cargo_wrapper_context_v2,
)
from literate_ai.adapters.retained_provider_authority import (
    read_retained_provider_authority,
)
from literate_ai.adapters.retained_provider_native import read_retained_provider_native
from literate_ai.application.generation_preparation import GenerationPreparationRequest
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import canonical_identity, canonical_json_bytes
from literate_ai.contracts.native_root_external_libraries import (
    NativeRootExternalLibrarySelections,
)
from literate_ai.projects import (
    PinnedInputClosure,
    ProjectConfigurationStore,
    discover_project,
)


def _require(condition, reason):
    if not condition:
        raise ExternalQualifiedLibraryError(reason)


def _note_cleanup(primary, cleanup):
    try:
        BaseException.add_note(
            primary, f"qualified receiving cleanup also refused: {cleanup}"
        )
    except BaseException:
        # An annotation must never replace the operation's original refusal.
        pass


class ConfiguredQualifiedLibraryReceivers:
    """One caller-owned operation stack, never a native run or execution grant."""

    def __init__(self):
        raise TypeError("use configured_qualified_library_receivers")

    def __copy__(self):
        raise TypeError("receiving operations cannot be copied")

    def __deepcopy__(self, memo):
        raise TypeError("receiving operations cannot be copied")

    def __reduce_ex__(self, protocol):
        raise TypeError("receiving operations cannot be serialized")

    def _pin_custody(self, *, check_entries=True):
        pins = self._original_pins
        guard, pin = self._original_pins_guard, self._original_pin
        current_guard, current_pin = pins.require_unchanged, pins.pin
        _require(
            self._pins is pins
            and type(pins) is PinnedInputClosure
            and type(guard) is MethodType
            and type(pin) is MethodType
            and type(current_guard) is MethodType
            and type(current_pin) is MethodType
            and guard.__self__ is pins
            and pin.__self__ is pins
            and current_guard.__self__ is pins
            and current_pin.__self__ is pins
            and guard.__func__ is self._original_pins_guard_function
            and pin.__func__ is self._original_pin_function
            and current_guard.__func__ is guard.__func__
            and current_pin.__func__ is pin.__func__
            and type(pins._entries) is dict
            and frozenset(vars(pins)) == self._original_pins_attributes
            and (pins.maximum_files, pins.maximum_file_bytes, pins.maximum_total_bytes)
            == self._original_pins_limits,
            "receiving_pin_custody_changed",
        )
        if check_entries:
            _require(
                tuple(pins._entries.items()) == self._original_pin_entries
                and PinnedInputClosure.identity.fget(pins)
                == self._original_pins_identity
                and pins._total_bytes
                == sum(len(row.content) for row in pins._entries.values()),
                "receiving_pin_closure_changed",
            )

    def _pin_selection(self, source, asset):
        self._configuration_guard()
        pins, pin = self._original_pins, self._original_pin
        before = self._original_pin_entries
        content = pin(
            source,
            boundary=self._original_project_root,
            label="qualified library root selection",
            expected_identity=asset.blob.identity,
        )
        self._pin_custody(check_entries=False)
        _require(
            self._original_pins is pins and self._original_pin is pin,
            "receiving_pin_custody_changed",
        )
        entries = tuple(pins._entries.items())
        original_keys = {key for key, _ in before}
        added = tuple(row for key, row in entries if key not in original_keys)
        _require(
            len(entries) == len(before) + 1
            and len(added) == 1
            and all(pins._entries.get(key) == row for key, row in before)
            and added[0].path == source
            and added[0].boundary == self._original_project_root
            and added[0].content == content
            and added[0].labels == ("qualified library root selection",)
            and len(content) == asset.blob.size,
            "receiving_selection_pin_changed",
        )
        # Sole trusted extension point, before any mutable wrapper/holder opens.
        # Updating these original observations conveys no currentness success.
        self._original_pin_entries = entries
        self._original_pins_identity = PinnedInputClosure.identity.fget(pins)
        self._configuration_guard()
        return content

    def _configuration_guard(self):
        self._pin_custody()
        pins, guard, pin = (
            self._original_pins,
            self._original_pins_guard,
            self._original_pin,
        )
        entries, identity = self._original_pin_entries, self._original_pins_identity
        _require(
            self._active
            and self.project is self._original_project
            and self.project.root == self._original_project_root
            and self.project.definition is self._original_project_definition
            and self.project.definition.identity == self._project_definition_identity
            and self.configuration is self._original_configuration
            and canonical_identity(asdict(self.configuration))
            == self._configuration_identity,
            "receiving_configuration_changed",
        )
        guard()
        _require(
            self._original_pins is pins
            and self._original_pins_guard is guard
            and self._original_pin is pin
            and self._original_pin_entries is entries
            and self._original_pins_identity == identity,
            "receiving_pin_custody_changed",
        )
        self._pin_custody()
        _require(
            self._active
            and self.project is self._original_project
            and self.project.root == self._original_project_root
            and self.project.definition is self._original_project_definition
            and self.project.definition.identity == self._project_definition_identity
            and self.configuration is self._original_configuration
            and canonical_identity(asdict(self.configuration))
            == self._configuration_identity,
            "receiving_configuration_changed",
        )

    def require_current(self):
        self._configuration_guard()
        _require(
            self._inputs is self._original_inputs
            and self._snapshot is self._original_snapshot
            and self._archive_readers is self._original_archive_readers,
            "receiving_owner_changed",
        )
        original = self._original_inputs
        if original is not None:
            require_qualified_library_inputs(original, self._snapshot)
        self._configuration_guard()
        _require(
            self._inputs is original
            and self._snapshot is self._original_snapshot
            and self._archive_readers is self._original_archive_readers,
            "receiving_owner_changed",
        )

    @property
    def inputs(self):
        self.require_current()
        _require(self._original_inputs is not None, "receiving_not_prepared")
        return self._original_inputs

    def read_archive(self, store, reference, maximum):
        """Dispatch ONLY a reader created for this exact reviewed store/ref."""
        self.require_current()
        readers = self._original_archive_readers
        reader = readers.get((store, reference))
        _require(reader is not None, "provider_archive_not_configured")
        content = reader(store, reference, maximum)
        self.require_current()
        return content

    def prepare(self, snapshot):
        _require(not self._preparing, "receiving_recursive_prepare")
        self._preparing = True
        try:
            return self._prepare(snapshot)
        except BaseException as primary:
            try:
                self._stack.__exit__(type(primary), primary, primary.__traceback__)
            except BaseException as cleanup:
                _note_cleanup(primary, cleanup)
            self._active = False
            raise
        finally:
            self._preparing = False

    def _prepare(self, snapshot):
        self.require_current()
        if self._original_inputs is not None:
            _require(snapshot is self._snapshot, "receiving_snapshot_changed")
            return self._original_inputs
        snapshot.require_unchanged()
        asset = _selected_asset(snapshot)
        _require(asset is not None, "configured_asset_required")
        _require(
            asset.blob.media_type == "application/json"
            and 0 < asset.blob.size <= 1024**2,
            "asset_mismatch",
        )
        lock = snapshot.authority.lock
        node = lock.nodes[0]
        component = snapshot.component_root(node.revision.authoring_identity)
        _require(
            component.is_relative_to(self.project.root),
            "consumer_component_outside_project",
        )
        (resolved,) = tuple(
            value
            for value in node.revision.assets
            if value.selector.asset_id == asset.asset_id
        )
        source = _asset_local_path(
            component, resolved.selector.source, boundary=self.project.root
        )
        _require(source is not None, "local_selection_asset_required")
        content = self._pin_selection(source, asset)
        _require(len(content) == asset.blob.size, "asset_bytes_mismatch")
        descriptor = NativeRootExternalLibrarySelections.from_dict(
            json.loads(content, object_pairs_hook=_unique_object)
        )
        _require(
            canonical_json_bytes(descriptor.to_dict()) == content, "asset_not_canonical"
        )
        selected = {
            selection.selection_id: selection for selection in descriptor.selections
        }
        configured = {
            name for row in self.configuration.receivers for name in row.selection_ids
        }
        _require(configured == set(selected), "receiving_selection_membership")
        self.configuration.require_distinct_projects(self.project.root)
        # Read and validate EVERY reviewed V2 declaration before opening any
        # mutable wrapper/scratch scope. No V1 or authored parser is called.
        reviewed_rows = []
        for locator in self.configuration.receivers:
            expected = tuple(selected[name] for name in locator.selection_ids)
            _require(
                len(
                    {
                        (
                            row.provider_component_revision,
                            row.reviewed_binding_identity,
                            row.importer_project_id,
                            row.evidence_store_id,
                            row.qualification_identity,
                            row.run_identity,
                            row.product_identity,
                            row.target_profile_identity,
                            row.import_surface_identity,
                            row.export_identities,
                        )
                        for row in expected
                    }
                )
                == 1,
                "receiving_group_mismatch",
            )
            reviewed = read_retained_cargo_review_v2(
                local_absolute_path(locator.importer_project, "importer_project"),
                binding_path=locator.binding_path,
                reviewed_binding=locator.reviewed_binding,
                plan_path=locator.workspace_plan_path,
                gate_policy_path=locator.gate_policy_path,
                test_inventory_path=locator.test_inventory_path,
                maximum_file_bytes=self.configuration.max_plan_bytes,
                maximum_total_bytes=5 * self.configuration.max_plan_bytes,
            )
            _require(
                reviewed.binding.identity == expected[0].reviewed_binding_identity
                and reviewed.project.definition.project_id
                == expected[0].importer_project_id
                and reviewed.binding.common.source_store_id
                == expected[0].evidence_store_id,
                "receiving_review_mismatch",
            )
            require_safe_directory(reviewed.project.root)
            common = reviewed.binding.common
            product = tuple(
                value
                for value in common.exports.libraries
                if value.identity == expected[0].product_identity
            )
            _require(
                common.qualification_identity == expected[0].qualification_identity
                and common.run_identity == expected[0].run_identity
                and len(product) == 1
                and product[0].artifact_export.component_revision
                == expected[0].provider_component_revision
                and product[0].artifact_export.target_identity
                == expected[0].target_profile_identity
                and all(
                    product[0].import_surface.identity == row.import_surface_identity
                    and product[0]
                    .import_surface.capability(row.capability)
                    .interface_identity
                    == row.interface_identity
                    for row in expected
                ),
                "receiving_provider_selection_mismatch",
            )
            _require(
                reviewed.project.root == Path(locator.importer_project),
                "receiving_project_alias",
            )
            files = read_retained_cargo_files_v2(
                reviewed,
                manifest_state="after",
                package_state="absent",
                maximum_file_bytes=self.configuration.max_plan_bytes,
                maximum_total_bytes=4 * self.configuration.max_plan_bytes,
            )
            reviewed_rows.append((locator, reviewed, files))
        roots = [
            self.project.root,
            *(reviewed.project.root for _locator, reviewed, _files in reviewed_rows),
        ]
        _require(
            len({str(root.resolve(strict=True)).casefold() for root in roots})
            == len(roots),
            "receiving_project_alias",
        )
        provider_inputs = {}
        for locator, _reviewed, _files in sorted(
            reviewed_rows, key=lambda row: row[0].provider_project.casefold()
        ):
            if locator.provider_receivers is not None:
                provider_inputs[id(locator)] = self._open_provider_inputs(locator)
        readers, origins, holders = {}, {}, {}
        # Wrapper lock acquisition is timeout-zero. ExitStack closes every
        # successfully opened earlier scope if a later importer is contended.
        for locator, reviewed, files in sorted(
            reviewed_rows, key=lambda row: str(row[1].project.root).casefold()
        ):
            self._configuration_guard()
            context = self._stack.enter_context(
                retained_cargo_wrapper_context_v2(reviewed)
            )
            scratch = self._stack.enter_context(
                reserve_retained_cargo_scratch_v2(context)
            )
            provider_root = local_absolute_path(
                locator.provider_project, "provider_project"
            )
            require_safe_directory(provider_root)
            provider_project = discover_project(provider_root)
            _require(
                provider_project is not None and provider_project.root == provider_root,
                "provider_project_required",
            )
            native = read_retained_provider_native(
                read_retained_provider_authority(
                    provider_root,
                    GenerationPreparationRequest(
                        component_root=provider_root / locator.provider_component,
                        target_name=locator.provider_target,
                        flavor_selectors=locator.provider_flavors,
                        flavor_roots=provider_project.roots("flavor"),
                    ),
                    provider_id=locator.provider_id,
                    profile_path=locator.provider_profile,
                    pipeline_model=locator.pipeline_model,
                    **(
                        {"qualified_library_inputs": provider_inputs[id(locator)]}
                        if id(locator) in provider_inputs
                        else {}
                    ),
                )
            )
            expected = selected[locator.selection_ids[0]]
            native.require_unchanged()
            result = native.provider.promotion.evidence.qualification_lifecycle_result
            prepared_provider = native.provider.generation.prepared
            provider_lock = prepared_provider.locked_authority_snapshot.authority.lock
            _require(
                result is not None
                and result.identity == expected.qualification_identity
                and sum(
                    value.run_identity == expected.run_identity for value in result.runs
                )
                == 1
                and provider_lock.root_revision == expected.provider_component_revision
                and provider_lock.target_profile_identity
                == expected.target_profile_identity,
                "current_provider_selection_mismatch",
            )
            native.require_unchanged()
            archive = reviewed.binding.common.qualification_archive
            _require(
                type(archive) is BlobRef
                and 0 < archive.size <= self.configuration.max_archive_bytes,
                "provider_archive_limit",
            )
            archive_path = local_absolute_path(locator.archive_path, "archive_path")
            require_safe_directory(archive_path.parent)
            archive_pins = PinnedInputClosure(
                maximum_files=1,
                maximum_file_bytes=archive.size,
                maximum_total_bytes=archive.size,
            )
            read_archive, current = self._readers(
                reviewed, native, expected, archive, archive_path, archive_pins
            )
            materialized = materialize_retained_cargo_archive_v2(
                files,
                scratch=scratch,
                read_current=current,
                read_archive=read_archive,
                max_plan_bytes=self.configuration.max_plan_bytes,
                max_archive_bytes=self.configuration.max_archive_bytes,
                max_records=self.configuration.max_records,
                max_package_bytes=self.configuration.max_package_bytes,
            )
            holder = self._stack.enter_context(
                hold_native_root_qualified_provider(materialized)
            )
            for name in locator.selection_ids:
                holders[name] = holder
            key = expected.evidence_store_id, archive
            _require(
                key not in origins or origins[key] == archive_path,
                "archive_origin_ambiguous",
            )
            origins[key], readers[key] = archive_path, read_archive
        owner = self._stack.enter_context(
            borrow_root_qualified_library_inputs(
                snapshot, content=content, holders=tuple(sorted(holders.items()))
            )
        )
        self._snapshot = self._original_snapshot = snapshot
        self._inputs = self._original_inputs = owner
        self._archive_readers = self._original_archive_readers = MappingProxyType(
            readers
        )
        self.require_current()
        return owner

    def _open_provider_inputs(self, locator):
        self._configuration_guard()
        root = local_absolute_path(locator.provider_project, "provider_project")
        active = _ACTIVE_RECEIVING_SCOPES.get()
        _require(
            len(active) < 64
            and not any(_overlap(root, other) for frame in active for other in frame),
            "receiving_cycle_or_scope_limit",
        )
        require_safe_directory(root)
        project = discover_project(root)
        _require(
            project is not None and project.root == root, "provider_project_required"
        )
        # The parent consumer lock is already held. This independently owned
        # provider lock and all child importer locks are fail-fast, never reentry
        # or a claim of globally sorted all-project acquisition.
        self._stack.enter_context(
            project_lifecycle_lock(root, operation="qualified-provider-inputs")
        )
        nested = self._stack.enter_context(
            configured_qualified_library_receivers(
                project, Path(locator.provider_receivers)
            )
        )
        snapshot = FilesystemLockedGenerationAuthorityReader().read(
            root / locator.provider_component,
            target_name=locator.provider_target,
            flavor_selectors=locator.provider_flavors,
            flavor_roots=project.roots("flavor"),
        )
        original = nested.prepare(snapshot)
        self._configuration_guard()
        _require(nested.inputs is original, "provider_receiving_owner_changed")
        return original

    def _readers(self, reviewed, native, selected, archive, path, archive_pins):
        store = selected.evidence_store_id
        binding = selected.reviewed_binding_identity

        def archive_reader(current_store, reference, maximum):
            self._configuration_guard()
            reviewed.require_unchanged()
            archive_pins.require_unchanged()
            _require(
                current_store == store
                and reference == archive
                and type(maximum) is int
                and 0 < reference.size <= maximum
                and reference.size <= self.configuration.max_archive_bytes,
                "provider_archive_not_configured",
            )
            content = archive_pins.pin(
                path,
                boundary=path.parent,
                label="original qualified provider archive",
                expected_identity=archive.identity,
            )
            _require(len(content) == archive.size, "provider_archive_changed")
            self._configuration_guard()
            reviewed.require_unchanged()
            archive_pins.require_unchanged()
            return content

        def current():
            self._configuration_guard()
            archive_pins.require_unchanged()
            value = compose_retained_cargo_current_inputs_v2(
                reviewed,
                native,
                reviewed_binding_identity=binding,
                configured_store_id=store,
            )
            self._configuration_guard()
            archive_pins.require_unchanged()
            return value

        return archive_reader, current


_ACTIVE_RECEIVING_SCOPES = ContextVar(
    "literate_ai_qualified_receiving_scopes", default=()
)


@contextmanager
def configured_qualified_library_receivers(project, configuration_path):
    """Own explicit recursive receiving scopes, never discover missing owners."""
    root = local_absolute_path(str(project.root), "consumer_project")
    active = _ACTIVE_RECEIVING_SCOPES.get()
    _require(
        len(active) < 64
        and not any(_overlap(root, other) for frame in active for other in frame),
        "receiving_cycle_or_scope_limit",
    )
    token = _ACTIVE_RECEIVING_SCOPES.set((*active, (root,)))
    declared_token = None
    try:
        with _configured_qualified_library_receivers(
            project, configuration_path
        ) as operation:
            declared = (
                root,
                *(
                    Path(row.importer_project)
                    for row in operation.configuration.receivers
                ),
            )
            _require(
                not any(
                    _overlap(candidate, previous)
                    for candidate in declared
                    for frame in active
                    for previous in frame
                ),
                "receiving_active_project_overlap",
            )
            _require(
                not any(
                    _overlap(Path(row.provider_project), previous)
                    for row in operation.configuration.receivers
                    for frame in active
                    for previous in frame
                ),
                "receiving_active_provider_overlap",
            )
            declared_token = _ACTIVE_RECEIVING_SCOPES.set((*active, declared))
            yield operation
        # Body and nested cleanup finish BEFORE resetting these original frames.
    finally:
        if declared_token is not None:
            _ACTIVE_RECEIVING_SCOPES.reset(declared_token)
        _ACTIVE_RECEIVING_SCOPES.reset(token)


@contextmanager
def _configured_qualified_library_receivers(project, configuration_path):
    """Pin explicit operator coordinates; caller already owns consumer lock."""
    path = local_absolute_path(str(configuration_path), "qualified_library_receivers")
    require_safe_directory(path.parent)
    require_safe_directory(project.root)
    pins = PinnedInputClosure(
        maximum_files=3, maximum_file_bytes=1024**2, maximum_total_bytes=3 * 1024**2
    )
    current = ProjectConfigurationStore(project.root).read()
    _require(
        current.definition == project.definition and current.root == project.root,
        "consumer_project_changed",
    )
    pins.pin(
        current.manifest_path,
        boundary=project.root,
        label="consumer project",
        expected_content=current.content,
    )
    content = pins.pin(
        path, boundary=path.parent, label="explicit qualified receiver configuration"
    )
    configuration = QualifiedReceiverConfiguration.from_dict(
        json.loads(content, object_pairs_hook=_unique_object)
    )
    configuration.require_distinct_projects(project.root)
    operation = object.__new__(ConfiguredQualifiedLibraryReceivers)
    operation._active, operation.project = True, project
    operation._original_project = project
    operation._original_project_root = project.root
    operation._original_project_definition = project.definition
    operation._project_definition_identity = project.definition.identity
    operation._preparing = False
    operation.configuration = operation._original_configuration = configuration
    operation._configuration_identity = canonical_identity(asdict(configuration))
    operation._pins = operation._original_pins = pins
    operation._original_pins_guard = pins.require_unchanged
    operation._original_pin = pins.pin
    operation._original_pins_guard_function = pins.require_unchanged.__func__
    operation._original_pin_function = pins.pin.__func__
    operation._original_pins_attributes = frozenset(vars(pins))
    operation._original_pins_limits = (
        pins.maximum_files,
        pins.maximum_file_bytes,
        pins.maximum_total_bytes,
    )
    operation._original_pin_entries = tuple(pins._entries.items())
    operation._original_pins_identity = PinnedInputClosure.identity.fget(pins)
    operation._inputs = operation._original_inputs = None
    operation._snapshot = operation._original_snapshot = None
    operation._archive_readers = operation._original_archive_readers = MappingProxyType(
        {}
    )
    stack = ExitStack()
    operation._stack = stack
    primary = None
    try:
        operation.require_current()
        yield operation
        operation.require_current()
    except BaseException as error:
        primary = error
        raise
    finally:
        # Existing scopes see the actual primary error, not a fabricated normal
        # exit. Keep configuration guards live through their own cleanup.
        try:
            if primary is None:
                stack.close()
            else:
                try:
                    stack.__exit__(type(primary), primary, primary.__traceback__)
                except BaseException as cleanup:
                    _note_cleanup(primary, cleanup)
        finally:
            operation._active = False
