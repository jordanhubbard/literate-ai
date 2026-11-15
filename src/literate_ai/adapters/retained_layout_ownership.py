"""Live initializer/source/control ownership joined to a complete namespace.

An initializer record is checked against actual provider roles, never accepted as
an arbitrary exclusion list. Unknown entries remain explicit. This dependency
supplies no root movement, qualified execution, or recoverable saved permission.
"""

from __future__ import annotations

import hashlib
import json
import os
from contextlib import ExitStack, contextmanager
from pathlib import Path

from literate_ai.contracts import (
    ProjectDefinition,
    ProjectInitializationBaseline,
    ProjectInitializationOrigin,
)
from literate_ai.contracts.identity import canonical_identity
from literate_ai.contracts.native_sdk_trees import NativeSdkTree, _ResolutionBudget
from literate_ai.contracts.retained_cargo_custody import RetainedCargoInputBudget
from literate_ai.projects import PROJECT_FILENAME, load_project

from .component_locks import ComponentLockStore
from .component_resolution_audits import ComponentResolutionAuditStore
from .conversion_authority import (
    CONVERSION_AUTHORITY_FILE,
    NATIVE_PROJECTS_FILE,
    _native_project_roots,
)
from .harness_inventory import legacy_shim_authority
from .project_initialization import (
    _FLAVOR_DIRECTORY_BY_CANONICAL,
    _STARTER_DOCS,
    _TEMPLATE_FILES,
    FLAVOR_SELECTOR_CANONICAL_NAMES,
    _include_template_file,
    discover_installed_initialization_origin,
)
from .repository_refresh import _file, _signature
from .retained_layout import RETAINED_LAYOUT_PATH
from .retained_layout_partition import (
    _project_manifest_candidates,
    capture_retained_layout_partition,
)
from .retained_layout_provider import original_initializer_roster
from .update_merge import CHECKPOINT, UpdateBases

_KEY = object()
_ORIGIN = ".literate/initialization-origin.json"
_BASELINE = ".literate/initialization-baseline.json"
_INVENTORY = ".literate/harness-inventory.json"
_REPORT = ".literate/legacy-harness-baseline.json"


def _fail(message):
    raise ValueError("layout.ownership: " + message)


def _beneath(name, root):
    return name == root or name.startswith(root + "/")


def _initializer_roles(
    phase,
    budget,
    metadata_limit,
    *,
    providers,
    provider_checkout,
    retired=(),
    current_origin=None,
    _source_admission=None,
):
    root = phase.plan.root
    maximum_entries = budget.maximum_entries
    cache = {}
    charged = 0
    payload_bytes = 0
    provider_files = provider_entries = 0

    def parse(content, label):
        from .bounded_role_observation import current_role_observation

        reader = current_role_observation()
        return (
            json.loads(content)
            if reader is None
            else reader.json_value(content, str(root / label))
        )

    def snapshot(path, *, optional=False):
        nonlocal charged, payload_bytes
        if path in cache:
            return cache[path]
        cost = 4096 + 64 * len(str(path).encode("utf-8"))
        remaining = min(
            budget.maximum_file_bytes,
            budget.maximum_total_bytes - payload_bytes,
            (metadata_limit - charged - cost) // 64,
        )
        if (
            len(cache) + provider_files >= budget.maximum_files
            or len(cache) + provider_entries >= maximum_entries
            or remaining < 1
        ):
            _fail("ownership input metadata exceeds its explicit budget")
        item = _file(path, optional=optional, maximum_bytes=remaining)
        size = len(item.content or b"")
        charged += cost + 64 * size
        payload_bytes += size
        cache[path] = item
        return item

    inputs = tuple(
        snapshot(
            root / name, optional=name in {NATIVE_PROJECTS_FILE, RETAINED_LAYOUT_PATH}
        )
        for name in (
            _ORIGIN,
            _BASELINE,
            _INVENTORY,
            _REPORT,
            NATIVE_PROJECTS_FILE,
            RETAINED_LAYOUT_PATH,
        )
    )
    values = {item.path.relative_to(root).as_posix(): item for item in inputs}
    origin = ProjectInitializationOrigin.from_dict(
        parse(values[_ORIGIN].content, _ORIGIN)
    )
    baseline = ProjectInitializationBaseline.from_dict(
        parse(values[_BASELINE].content, _BASELINE)
    )
    if (
        baseline.origin_identity != origin.identity
        or len(baseline.files) > maximum_entries
    ):
        _fail("initialization origin, file inventory or bound disagrees")
    baseline_paths = {item.path for item in baseline.files}
    # Bind selection to the original initialized manifest, not today's mutable
    # selectors or every possible endpoint in the installed template catalog.
    manifest = next(
        (item for item in baseline.files if item.path == PROJECT_FILENAME), None
    )
    if manifest is None:
        _fail("original initializer manifest is missing")
    checkpoint = snapshot(root / CHECKPOINT)
    if _source_admission is not None:
        parse(checkpoint.content, CHECKPOINT)
    limit = min(maximum_entries - len(cache), (metadata_limit - charged) // 4096)
    if limit < 0:
        _fail("canonical checkpoint exceeds ownership metadata budget")
    try:
        bases = UpdateBases.from_observed(
            root, checkpoint.content, maximum_entries=limit
        )
    except ValueError as error:
        _fail(
            "original initializer manifest bytes disagree with canonical checkpoint: "
            + str(error)
        )
    charged += 4096 * bases.entry_count
    provider_entries += bases.entry_count
    original = bases.get(manifest.identity)
    if original is None:
        _fail("original initializer manifest bytes are missing")
    if (
        len(original) != manifest.size
        or "sha256:" + hashlib.sha256(original).hexdigest() != manifest.identity.uri
    ):
        _fail("original initializer manifest bytes disagree with their identity")
    definition = ProjectDefinition.from_dict(parse(original, "initializer-project"))
    provider = None
    if provider_checkout is not None or origin != (
        discover_installed_initialization_origin()
        if current_origin is None
        else current_origin
    ):
        remaining_files = budget.maximum_files - len(cache)
        remaining_entries = budget.maximum_entries - len(cache) - provider_entries
        remaining_bytes = budget.maximum_total_bytes - payload_bytes
        if min(remaining_files, remaining_entries, remaining_bytes) < 1:
            _fail("ownership inputs leave no original provider budget")
        remaining_files = min(remaining_files, remaining_entries)
        file_limit = min(budget.maximum_file_bytes, remaining_bytes)
        provider_budget = RetainedCargoInputBudget(
            remaining_files,
            remaining_entries,
            file_limit,
            min(remaining_bytes, remaining_files * file_limit),
        )
        if _source_admission is None:
            provider = providers.enter_context(
                original_initializer_roster(
                    origin,
                    definition,
                    checkout=provider_checkout,
                    budget=provider_budget,
                    metadata_limit=metadata_limit - charged,
                )
            )
        else:
            from .retained_layout_source_provider import _join

            provider = _join(
                _source_admission,
                origin,
                definition,
                checkout=provider_checkout,
                budget=provider_budget,
                metadata_limit=metadata_limit - charged,
            )
        charged += provider.objects.charged
        payload_bytes += provider.objects.total
        provider_files = provider.objects.file_count
        provider_entries += provider.objects.entries
    active_flavors = set()
    for selector in () if provider is not None else definition.default_flavor_selectors:
        selector = selector.removeprefix("+")
        canonical = FLAVOR_SELECTOR_CANONICAL_NAMES.get(selector, selector)
        directory = _FLAVOR_DIRECTORY_BY_CANONICAL.get(canonical)
        if directory is None:
            _fail("original initializer Flavor lacks its actual provider")
        active_flavors.add(directory)
    allowed = {
        name
        for name in _TEMPLATE_FILES
        if _include_template_file(name, frozenset(active_flavors))
    } | set(_STARTER_DOCS)
    if provider is not None:
        allowed = set(provider.templates) | set(_STARTER_DOCS)
    # This owner requires real conversion inventory/baseline inputs. Conversion
    # never emits the hello starter, even when its caller requested one.
    allowed.update(
        legacy_shim_authority(
            parse(values[_INVENTORY].content, _INVENTORY),
            parse(values[_REPORT].content, _REPORT),
            wrapper_component=phase.plan.layout.wrapper_component,
        )
    )
    allowed.update(
        {
            PROJECT_FILENAME,
            _ORIGIN,
            _BASELINE,
            _INVENTORY,
            _REPORT,
            ".literate/legacy-wrapper-parity.json",
            ".literate/legacy-lift-shift.json",
            ".literate/repository-parent.json",
            ".literate/repository-lineage.json",
            "docs/decisions/0001-legacy-project-lift-and-shift.md",
            "docs/decisions/0002-native-literate-ai-rewrite.md",
            "docs/roadmap/native-rewrite-program.md",
            "litai.harness.mk",
        }
    )
    # Canonical store endpoints are metadata roles even while their evidence is
    # stale. This does not qualify that lock or invent a selected Component.
    component_paths = {
        name for name in baseline_paths & allowed if name.endswith("/component.md")
    } | {phase.plan.layout.wrapper_component + "/component.md"}
    for name in component_paths:
        component = root / Path(name).parent
        if _source_admission is None:
            lock_path = ComponentLockStore(component).path
            audit_path = ComponentResolutionAuditStore(component, "host").path
        else:
            from .component_locks import LOCK_FILENAME

            # Original initialization wrote native host endpoints. Ambient cell
            # selection cannot change what that historical producer owned.
            lock_path = ComponentLockStore._storage_root(component) / LOCK_FILENAME
            audit_path = ComponentResolutionAuditStore._path_for_storage(
                component, "host"
            )
        if lock_path.is_relative_to(root):
            allowed.add(lock_path.relative_to(root).as_posix())
        # Initial conversion produces host locks/audits only. A baseline-named
        # arbitrary target cannot turn the store's naming API into a producer.
        if audit_path.is_relative_to(root):
            allowed.add(audit_path.relative_to(root).as_posix())
    if not baseline_paths <= allowed:
        _fail("initialization record claims files outside actual initializer roles")
    framework = (baseline_paths - set(retired)) | {_BASELINE, CONVERSION_AUTHORITY_FILE}
    # These endpoints have distinct actual owners; their contents cannot label
    # any additional files as framework-owned.
    for name in (CHECKPOINT, NATIVE_PROJECTS_FILE, RETAINED_LAYOUT_PATH):
        if os.path.lexists(root / name):
            framework.add(name)
    if _source_admission is not None:
        from .retained_layout_source_authored import _initializer_framework

        framework = _initializer_framework(_source_admission, framework, cache)
    project = load_project(root)
    children = _native_project_roots(project)
    child_inputs = tuple(snapshot(child / PROJECT_FILENAME) for child in children)
    framework_inputs = tuple(snapshot(root / name) for name in sorted(framework))
    return (
        framework,
        children,
        (*inputs, *child_inputs, *framework_inputs),
        origin,
        provider,
    )


def _partition_roles(
    phase, census, framework, children, imported=(), imported_dirs=(), *, authored=()
):
    root = phase.plan.root
    source = phase.plan.tree.root.relative_to(root).as_posix()
    root_source = source == "."
    controls = {
        marker.target.path.relative_to(root).as_posix()
        for marker in phase.controls.reservations._markers
        if marker.target.path.is_relative_to(root)
    }
    git_roots = tuple(
        path.relative_to(root).as_posix()
        for path in phase.controls.protected_admin_entries
        if path.is_relative_to(root)
    )
    child_roots = tuple(child.relative_to(root).as_posix() for child in children)
    files = {name for name, _, _ in census.tree.files}
    aliases = {item.path: item for item in census.tree.aliases}
    leaves = files | aliases.keys()
    imported, imported_dirs = set(imported), set(imported_dirs)
    authored = set(authored)
    if not imported <= files or not imported_dirs <= set(census.tree.directories):
        _fail("actual catalog roles require their complete copied nodes")
    if not framework <= files | {
        name for name, alias in aliases.items() if alias.kind == "hardlink"
    }:
        _fail("framework roles require exact observed regular files")
    if not authored <= files | {
        name for name, alias in aliases.items() if alias.kind == "hardlink"
    }:
        _fail("authored roles require actual observed canonical files")

    def role(name):
        if name in authored:
            return "authored"
        if name in controls or any(_beneath(name, path) for path in git_roots):
            return "control"
        child = next((path for path in child_roots if _beneath(name, path)), None)
        if child is not None:
            return "independent:" + child
        if name in imported or name in imported_dirs:
            if not root_source and _beneath(name, source):
                _fail("actual catalog ownership overlaps retained source")
            return "imported"
        if name in framework:
            if not root_source and _beneath(name, source):
                _fail("framework ownership overlaps the actual retained source")
            return "framework"
        return "source" if root_source or _beneath(name, source) else "unclaimed"

    for name in _project_manifest_candidates(census.tree):
        if Path(name).parent != Path(".") and not any(
            _beneath(name, child) for child in child_roots
        ):
            _fail("independent project candidate lacks its registered actual owner")
    roles = {name: role(name) for name in leaves}
    directories = {name: set() for name in (".", *census.tree.directories)}

    def ancestors(name):
        path = Path(name).parent
        while path.as_posix() != ".":
            yield path.as_posix()
            path = path.parent
        yield "."

    for name, value in roles.items():
        for parent in ancestors(name):
            directories[parent].add(value)
    for name in sorted(
        census.tree.directories, key=lambda item: item.count("/"), reverse=True
    ):
        if not directories[name]:
            directories[name].add(role(name))
        for parent in ancestors(name):
            directories[parent].update(directories[name])
    resolution = _ResolutionBudget(
        remaining=max(1048576, census.tree.budget.maximum_entries * 128)
    )
    for name in aliases:
        expected = roles[name]

        def observe(candidate, expected=expected):
            if candidate in aliases and roles[candidate] != expected:
                _fail("alias traverses another actual ownership role")

        target = NativeSdkTree._resolve(
            name,
            set(census.tree.directories),
            files,
            aliases,
            resolution,
            observe=observe,
        )
        actual = directories[target] if target in directories else {roles[target]}
        if actual != {expected}:
            _fail("alias or hardlink crosses actual ownership roles")
    return tuple(sorted(roles.items())), tuple(
        sorted((name, tuple(sorted(values))) for name, values in directories.items())
    )


class _OwnedPartition:
    __slots__ = (
        "_phase",
        "_census",
        "_native",
        "_inputs",
        "_provider_origin",
        "_provider",
        "_roles",
        "_directories",
        "_active",
        "_spent",
        "_pid",
        "_identity",
        "_framework_update",
        "_catalog_copy",
        "_authored",
        "_effect_graph",
        "_effect_graph_fields",
    )

    def __init__(
        self,
        key,
        phase,
        census,
        native,
        inputs,
        roles,
        directories,
        origin,
        provider,
        framework_update=None,
        catalog_copy=None,
        *,
        authored=None,
    ):
        if key is not _KEY:
            raise TypeError("layout.ownership.live-source-phase-required")
        self._phase, self._census, self._native, self._inputs = (
            phase,
            census,
            native,
            inputs,
        )
        self._roles, self._directories = roles, directories
        from .retained_layout_effect_graph import _graph_fields, _source_effect_graph

        self._effect_graph = _source_effect_graph(
            census.tree,
            roles,
            directories,
            phase.plan.tree.root.relative_to(phase.plan.root).as_posix(),
            phase.plan.destination.relative_to(phase.plan.root).as_posix(),
            protected_directories=tuple(
                sorted(
                    path.relative_to(phase.plan.root).as_posix()
                    for path in phase.controls.protected_admin_entries
                    if path.is_relative_to(phase.plan.root)
                    and path.relative_to(phase.plan.root).as_posix()
                    in census.tree.directories
                )
            ),
        )
        self._effect_graph_fields = _graph_fields(self._effect_graph)
        self._provider_origin = origin
        self._provider = provider
        self._framework_update = framework_update
        self._catalog_copy = catalog_copy
        self._authored = authored
        self._active, self._spent, self._pid = True, False, os.getpid()
        self._identity = canonical_identity(
            {
                "schema": "literate-ai/layout-owned-partition@1",
                "phase": phase.plan.identity.uri,
                "namespace": census.identity.uri,
                "controls": phase.controls.identity.uri,
                "initializer_provider": None
                if provider is None
                else provider.identity.uri,
                "roles": roles,
                "directories": directories,
                "source_effect_graph": self._effect_graph.identity.uri,
                "inputs": [
                    {
                        "path": str(item.path),
                        "sha256": None
                        if item.content is None
                        else hashlib.sha256(item.content).hexdigest(),
                    }
                    for item in inputs
                ],
                **({} if authored is None else {"authored": authored.identity.uri}),
            }
        )

    @property
    def census(self):
        return self._census

    @property
    def roles(self):
        return self._roles

    @property
    def directories(self):
        return self._directories

    def require_current(self):
        from .retained_layout_source_admission import _partition_current, _phase_record

        if _phase_record(self._phase) is not None:
            _partition_current(self)
        else:
            self._require_current_inputs()

    def _require_current_inputs(self):
        from .retained_layout_source_admission import _origin_for_phase
        from .retained_layout_transaction import _close_tree, _require_prepared

        if not self._active or self._spent or self._pid != os.getpid():
            _fail("partition owner ended or was spent")
        self._phase._live()
        if self._authored is not None:
            self._authored.require_current()
        self._phase.controls.require_initial_inputs()
        _require_prepared(self._phase.plan, self._phase.controls.reservations)
        if self._framework_update is not None:
            self._framework_update.require_plan(self._phase.plan)
            self._framework_update.require_current()
        if self._catalog_copy is not None:
            self._catalog_copy.require_plan(self._phase.plan)
            self._catalog_copy.require_current()
        if self._provider is not None:
            self._provider.require_current()
        elif self._provider_origin != (
            _origin_for_phase(self._phase)
            if self._framework_update is None
            else self._framework_update._provider_origin
        ):
            _fail("original initializer provider changed")
        self.census.require_unchanged()
        self._phase.controls.git.close_native_inputs(self._phase.controls.reservations)
        self._phase.controls.reservations._close_currentness()
        self._phase.controls._seed.close_native_inputs()
        for item in self._inputs:
            try:
                current = _signature(item.path)
            except FileNotFoundError:
                current = None
            if current != item.signature:
                _fail("original ownership inputs changed")
        _close_tree(self.census.tree, self._native, controls=self._phase.controls)
        if self._provider is not None:
            self._provider.close_native()
        if self._framework_update is not None:
            self._framework_update.close_native()
        if self._catalog_copy is not None:
            self._catalog_copy.close_native()
        self._require_eligible()

    def _require_eligible(self):
        self._phase._live()
        controls = self._phase.controls
        if (
            not self._active
            or self._spent
            or self._pid != os.getpid()
            or not self._phase._active
            or not controls._active
            or controls._receiver != os.getpid()
            or controls._finalizing
            or not controls.reservations._active
            or not controls.reservations._complete
        ):
            _fail("partition or original control context ended")
        from .retained_layout_effect_graph import _graph_fields

        if any(
            a is not b
            for a, b in zip(
                _graph_fields(self._effect_graph),
                self._effect_graph_fields,
                strict=True,
            )
        ):
            _fail("original source effect graph changed")

    @property
    def document(self):
        self.require_current()
        result = {
            "schema": "literate-ai/layout-owned-partition-observation@1",
            "identity": self._identity.uri,
            "source_phase_identity": self._phase.plan.identity.uri,
            "namespace_identity": self.census.identity.uri,
            "roles": self.roles,
            "directories": self.directories,
            "source_effect_graph": self._effect_graph.document,
        }
        if self._framework_update is not None:
            result["framework_update"] = self._framework_update.document
        if self._catalog_copy is not None:
            result["catalog_copy"] = self._catalog_copy.document
        return result

    @property
    def identity(self):
        self.require_current()
        return self._identity

    def _consume(self):
        from .retained_layout_source_movement import _consume_admitted_partition

        if _consume_admitted_partition(self):
            return
        from .retained_layout_source_admission import _refuse_unfunded_effects

        _refuse_unfunded_effects(self._phase)
        self.require_current()
        if self._framework_update is not None:
            self._framework_update.spend()
        if self._catalog_copy is not None:
            self._catalog_copy.spend()
        self._require_eligible()
        self._spent = True


@contextmanager
def _owned_partition(
    phase,
    *,
    budget,
    maximum_metadata_bytes,
    provider_checkout=None,
    framework_update=None,
    catalog_copy=None,
):
    from .retained_layout_source_admission import (
        _admitted_partition,
        _phase_record,
    )

    if _phase_record(phase) is not None:
        with _admitted_partition(
            phase,
            budget=budget,
            maximum_metadata_bytes=maximum_metadata_bytes,
            provider_checkout=provider_checkout,
            framework_update=framework_update,
            catalog_copy=catalog_copy,
        ) as owner:
            yield owner
        return
    with ExitStack() as providers:
        with _partition_context(
            phase,
            budget=budget,
            maximum_metadata_bytes=maximum_metadata_bytes,
            providers=providers,
            provider_checkout=provider_checkout,
            framework_update=framework_update,
            catalog_copy=catalog_copy,
        ) as owner:
            yield owner


@contextmanager
def _partition_context(
    phase,
    *,
    budget,
    maximum_metadata_bytes,
    providers,
    provider_checkout,
    framework_update,
    catalog_copy,
):
    from .retained_layout_transaction import (
        _native_tree,
        _require_prepared,
        _SourcePhase,
    )

    if type(phase) is not _SourcePhase:
        raise TypeError("layout.ownership.live-source-phase-required")

    if type(budget) is not RetainedCargoInputBudget:
        _fail("explicit complete-namespace budget required")
    phase._live()
    if phase._attempted or phase._partition_owner is not None:
        _fail("partition observation requires one original live source phase")
    if phase.pool.root.is_relative_to(phase.plan.root):
        _fail("complete namespace requires private journal/stages outside the project")
    _require_prepared(phase.plan, phase.controls.reservations)
    if (
        type(maximum_metadata_bytes) is not int
        or not 64 * 1024**2 <= maximum_metadata_bytes <= 16 * 1024**3
    ):
        _fail("complete ownership metadata budget must be explicit and bounded")
    quarter = maximum_metadata_bytes // 4
    if framework_update is not None:
        from .framework_update_roles import _require_handoff

        _require_handoff(framework_update).require_plan(phase.plan)
        framework_update.require_current()
        if catalog_copy is None:
            budget, maximum_metadata_bytes = framework_update.remaining(
                budget, maximum_metadata_bytes
            )
        else:
            from .catalog_copy_roles import _require_handoff as require_catalog

            require_catalog(catalog_copy).require_framework(framework_update)
        quarter = maximum_metadata_bytes // 4
        moving = {phase.plan.tree._physical[0][:2]} | {
            node[:2] for _name, node in phase.plan.tree._physical[1]
        }
        for _anchor, lineage in framework_update._lineages.values():
            if moving & {entry[1:3] for entry in lineage}:
                _fail("actual update provider or inputs overlap moving source")
        if moving & {node[:2] for node in framework_update._git.directories.values()}:
            _fail(
                "actual update Git administration or object store "
                "overlaps moving source"
            )
    elif phase.plan.framework_update is not None:
        _fail("fresh source plan requires its actual live framework update")
    if catalog_copy is not None:
        from .catalog_copy_roles import _require_handoff as require_catalog

        require_catalog(catalog_copy).require_plan(phase.plan)
        catalog_copy.require_current()
        budget, maximum_metadata_bytes = catalog_copy.remaining(
            budget, maximum_metadata_bytes
        )
        quarter = maximum_metadata_bytes // 4
    elif phase.plan.catalog_copy is not None:
        _fail("fresh source plan requires its actual live catalog copy")
    before = capture_retained_layout_partition(
        phase.plan.root,
        framework_files=(),
        budget=budget,
        maximum_metadata_bytes=quarter,
    )
    private_nodes = {
        (item.st_dev, item.st_ino)
        for item in (
            os.fstat(phase.pool._descriptor),
            os.fstat(phase.pool._journal._descriptor),
        )
    }
    if (
        any(node[:2] in private_nodes for _name, node in before.tree._physical[1])
        or before.tree._physical[0][:2] in private_nodes
    ):
        _fail(
            "private journal/stages physically overlap the complete project namespace"
        )
    framework, children, inputs, origin, provider = _initializer_roles(
        phase,
        budget,
        quarter,
        providers=providers,
        provider_checkout=provider_checkout,
        retired=() if framework_update is None else framework_update.removed_paths,
        current_origin=None
        if framework_update is None
        else framework_update._provider_origin,
    )
    if framework_update is not None:
        framework.update(framework_update.paths)
    imported, imported_dirs = (), ()
    if catalog_copy is not None:
        from literate_ai.contracts.catalog_imports import CatalogImportsFile

        imported, imported_dirs = catalog_copy.paths, catalog_copy.directories
        framework.difference_update(imported)
        framework.add(CatalogImportsFile.PATH)
        inputs = (*inputs, catalog_copy.provenance)
    if provider is not None:
        protected = {node[:2] for node in provider.objects.directories.values()}
        moving = {phase.plan.tree._physical[0][:2]} | {
            node[:2] for _name, node in phase.plan.tree._physical[1]
        }
        if protected & moving:
            _fail(
                "original provider checkout or administration is part of moving source"
            )
    census = capture_retained_layout_partition(
        phase.plan.root,
        framework_files=tuple(sorted(framework)),
        budget=budget,
        maximum_metadata_bytes=quarter,
    )
    if census.tree != before.tree or census.tree._physical != before.tree._physical:
        _fail("complete namespace changed while actual roles were joined")
    native = _native_tree(census.tree)
    roles, directories = _partition_roles(
        phase, census, framework, children, imported, imported_dirs
    )
    # Charge the actual serialized role inventory, not only its digest.
    from literate_ai.contracts.identity import canonical_json_bytes

    wire_size = len(canonical_json_bytes({"roles": roles, "directories": directories}))
    from .retained_layout_effect_graph import _graph_allowance

    _, graph_bytes = _graph_allowance(
        roles,
        directories,
        phase.plan.destination.relative_to(phase.plan.root).as_posix(),
    )
    if wire_size * 64 + graph_bytes > quarter:
        _fail("actual role inventory exceeds ownership metadata budget")
    owner = _OwnedPartition(
        _KEY,
        phase,
        census,
        native,
        inputs,
        roles,
        directories,
        origin,
        provider,
        framework_update,
        catalog_copy,
    )
    phase._partition_owner = owner
    try:
        owner.require_current()
        yield owner
        if not owner._spent:
            owner.require_current()
    finally:
        owner._active = False
        phase._partition_owner = None
