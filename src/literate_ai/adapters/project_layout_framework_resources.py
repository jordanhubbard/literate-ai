"""Original initializer resource observation for existing framework placement.

This original read owner selects finite initializer/update resources. It grants
no move, execution or publication authority. Historical source ownership still
requires current provenance/base and application-boundary joins in the selector.
"""

from __future__ import annotations

import hashlib
import json
import weakref
from dataclasses import dataclass, fields
from pathlib import Path
from types import MappingProxyType

from literate_ai._filesystem import require_safe_directory, stat_is_link_or_reparse
from literate_ai.adapters import harness_inventory as harness
from literate_ai.adapters import project_initialization as initialization
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutPlanError,
    _capture,
    _git_state,
    _json,
)
from literate_ai.contracts import (
    ProjectDefinition,
    ProjectInitializationBaseline,
    ProjectInitializationOrigin,
    canonical_identity,
)
from literate_ai.projects import (
    CATALOG_SOURCE_ROOTS,
    ProjectConfigurationSnapshot,
    ProjectConfigurationStore,
    ProjectContext,
)

_DELEGATES = frozenset(
    {"AGENTS.md", "CLAUDE.md", ".cursor/rules/literate-ai.mdc", "agents/openai.yaml"}
)
_INITIALIZER_FILE = initialization.__file__
_TEMPLATE_MAP = tuple(sorted(initialization._TEMPLATE_FILES.items()))
_STARTER_MAP = tuple(sorted(initialization._STARTER_TEMPLATE_FILES.items()))
_STARTER_DOCS = tuple(sorted(initialization._STARTER_DOCS.items()))
_FLAVORS = tuple(sorted(initialization._FLAVOR_DIRECTORY_BY_CANONICAL.items()))
_ALIASES = tuple(sorted(initialization.FLAVOR_SELECTOR_CANONICAL_NAMES.items()))
_FUNCTIONS = tuple(
    (name, vars(initialization)[name])
    for name in (
        "_include_template_file",
        "render_starter_document",
        "discover_installed_initialization_origin",
    )
)
_INCLUDE = initialization._include_template_file
_RENDER = initialization.render_starter_document
_ORIGIN = initialization.discover_installed_initialization_origin
_NATIVE_PROGRAM = harness.render_native_rewrite_roadmap
_NATIVE_PROGRAM_CODE = _NATIVE_PROGRAM.__code__
_MAX_BYTES = 64 * 1024**2


def _fail(message):
    raise ProjectLayoutPlanError("framework_resource_unavailable", message)


def _identity(content):
    return "sha256:" + hashlib.sha256(content).hexdigest()


def _initializer_current():
    if (
        vars(harness).get("render_native_rewrite_roadmap") is not _NATIVE_PROGRAM
        or _NATIVE_PROGRAM.__code__ is not _NATIVE_PROGRAM_CODE
    ):
        _fail("original native rewrite program producer changed")
    if vars(initialization).get("__file__") != _INITIALIZER_FILE or any(
        vars(initialization).get(name) is not value for name, value in _FUNCTIONS
    ):
        _fail("original initializer resource owner changed")
    for name, expected in (
        ("_TEMPLATE_FILES", _TEMPLATE_MAP),
        ("_STARTER_TEMPLATE_FILES", _STARTER_MAP),
        ("_STARTER_DOCS", _STARTER_DOCS),
        ("_FLAVOR_DIRECTORY_BY_CANONICAL", _FLAVORS),
        ("FLAVOR_SELECTOR_CANONICAL_NAMES", _ALIASES),
    ):
        actual = vars(initialization).get(name)
        if (
            type(actual) is not dict
            or any(
                type(key) is not str or type(value) is not str
                for key, value in actual.items()
            )
            or tuple(sorted(actual.items())) != expected
        ):
            _fail("original initializer finite inventory changed")


def _read_current_origin():
    """Original fixed origin owner; tests may explicitly model this boundary."""
    return _ORIGIN()


def _original_resource_root():
    """Actual initializer package tree; no CWD/project-path lookup."""
    return Path(_INITIALIZER_FILE).parent.parent / "project_template"


def _native_root(root, original=None):
    require_safe_directory(root)
    node = root.lstat()
    if stat_is_link_or_reparse(node):
        _fail("initializer resource namespace is redirected")
    value = (node.st_dev, node.st_ino, node.st_mode)
    if original is not None and value != original:
        _fail("original initializer resource namespace replaced")
    return value


def _project_current(snapshot, context, git_pair):
    if context.directory_binding is None:
        _fail("original project namespace witness unavailable")
    _native_root(snapshot.root, context.directory_binding[0][:3])
    _native_root(context.framework_root, context.directory_binding[1][:3])
    current = ProjectConfigurationStore(snapshot.root).read()
    if (
        current.content != snapshot.content
        or current.definition != snapshot.definition
        or current.directory_binding != snapshot.directory_binding
        or ProjectConfigurationStore.context(snapshot.root) != context
        or (_git_state(snapshot.root), _git_state(context.framework_root)) != git_pair
    ):
        _fail("original current project/context/Git authority changed")


@dataclass(frozen=True, slots=True, weakref_slot=True)
class OriginalScaffoldResourceSelection:
    snapshot: object
    context: object
    origin: ProjectInitializationOrigin
    profile: str
    flavor_selectors: tuple[str, ...]
    converted: bool
    files: object
    roles: object
    resource_identities: object
    identity: str
    _guard: object

    def require_current(self):
        return require_current_framework_resources(self)


_FIELDS = tuple(field.name for field in fields(OriginalScaffoldResourceSelection))
_NAMESPACES = tuple(
    (cls, tuple(vars(cls).items()), cls.__bases__, cls.__mro__)
    for cls in (
        OriginalScaffoldResourceSelection,
        ProjectInitializationOrigin,
        ProjectInitializationBaseline,
        ProjectConfigurationStore,
        ProjectConfigurationSnapshot,
        ProjectContext,
        ProjectDefinition,
    )
)


def _classes_current():
    for cls, namespace, bases, mro in _NAMESPACES:
        current = vars(cls)
        if (
            cls.__bases__ is not bases
            or cls.__mro__ is not mro
            or set(current) != {key for key, _ in namespace}
            or any(current[key] is not value for key, value in namespace)
        ):
            _fail("original framework resource descriptor changed")


def _admissions():
    registry = {}

    def require(owner):
        record = registry.get(id(owner))
        if record is None or record[0]() is not owner:
            _fail("resource selection lacks original factory admission")
        _classes_current()
        for name, value in zip(_FIELDS, record[1], strict=True):
            if object.__getattribute__(owner, name) is not value:
                _fail("original framework resource selection changed")
        for member, values in record[2]:
            if any(
                object.__getattribute__(member, name) is not value
                for name, value in values
            ):
                _fail("original framework resource member changed")
        return record[1]

    def register(owner, values, members, initialization_records):
        key = id(owner)
        if key in registry:
            _fail("resource selection cannot be renewed")

        def release(dead):
            old = registry.get(key)
            if old is not None and old[0] is dead:
                registry.pop(key, None)

        registry[key] = (
            weakref.ref(owner, release),
            values,
            members,
            initialization_records,
        )
        require(owner)

    def retire(owner):
        old = registry.get(id(owner))
        if old is not None and old[0]() is owner:
            registry.pop(id(owner), None)

    def initialization_records(owner):
        require(owner)
        return registry[id(owner)][3]

    return register, require, retire, initialization_records


_register, _require, _retire, _initialization_records = _admissions()
_GUARD = _FIELDS.index("_guard")


def require_original_framework_resources(owner):
    """In-memory original-origin proof; never invokes an owner callback."""
    _require(owner)


def _producer_namespace(nodes):
    """Selected members stay exact; unrelated sibling creation is not a rebase.

    Capture still compares full stamps DURING each read. Across live boundaries,
    an ancestor directory only retains its original physical identity and mode;
    selected file stamps/bytes and exact selected membership remain unchanged.
    """
    return {
        path: {
            **row,
            **({"stamp": row["stamp"][:3]} if row["kind"] == "directory" else {}),
        }
        for path, row in nodes.items()
    }


def original_framework_initialization(owner):
    """Reopen ACTUAL admitted original producer bytes, data only and no I/O.

    Returns (origin, baseline, origin_bytes, baseline_bytes). These correlation
    records are not a live source/move grant and do not reopen an owner.
    """
    origin_bytes, baseline_bytes = _initialization_records(owner)
    origin = ProjectInitializationOrigin.from_dict(json.loads(origin_bytes))
    baseline = ProjectInitializationBaseline.from_dict(json.loads(baseline_bytes))
    if baseline.origin_identity != origin.identity:
        _fail("admitted initialization record join changed")
    return origin, baseline, origin_bytes, baseline_bytes


def require_current_framework_resources(owner):
    values = _require(owner)
    try:
        result = values[_GUARD]()
    except BaseException as primary:
        try:
            _require(owner)
        except BaseException:
            try:
                BaseException.add_note(
                    primary, "Framework resource admission changed during refusal"
                )
            except BaseException:
                pass
        raise
    _require(owner)
    return result


def observe_original_framework_resources(observation):
    """Read finite original initializer resources with stable native custody.

    No remote historical lookup, default Flavor detection, worker configuration,
    new project initialization, runtime execution, or driver/receipt renewal.
    """
    _classes_current()
    _initializer_current()
    snapshot, context = observation.snapshot, observation.context
    if (
        type(snapshot) is not ProjectConfigurationSnapshot
        or type(context) is not ProjectContext
    ):
        _fail("actual original project observation required")
    definition = snapshot.definition
    original_snapshot_fields = (
        snapshot.root,
        snapshot.content,
        definition,
        snapshot.directory_binding,
        context.root,
        context.framework_root,
        context.directory_binding,
    )

    def locator_current():
        _classes_current()
        current_fields = (
            snapshot.root,
            snapshot.content,
            snapshot.definition,
            snapshot.directory_binding,
            context.root,
            context.framework_root,
            context.directory_binding,
        )
        if any(
            a is not b
            for a, b in zip(current_fields, original_snapshot_fields, strict=True)
        ):
            _fail("original framework project locator changed")

    if (
        definition.framework_directory != "litai"
        or context.framework_root != snapshot.root / "litai"
    ):
        _fail("existing contained project authority required")
    selectors = definition.default_flavor_selectors
    if type(selectors) is not tuple:
        _fail("exact original current Flavor selections required")
    aliases, directories = dict(_ALIASES), dict(_FLAVORS)
    active = []
    for selector in selectors:
        if type(selector) is not str or not selector.startswith("+"):
            _fail("unknown/noncanonical original Flavor selector")
        name = selector.removeprefix("+")
        directory = directories.get(aliases.get(name, name))
        if directory is None:
            _fail("original Flavor selection has no initializer resource")
        active.append(directory)
    active = frozenset(active)
    git_pair = (
        None
        if observation.inventory["git_state"] is None
        else dict(observation.inventory["git_state"]),
        None
        if observation.inventory["framework_git_state"] is None
        else dict(observation.inventory["framework_git_state"]),
    )
    metadata_paths = (
        "litai/.literate/initialization-baseline.json",
        "litai/.literate/initialization-origin.json",
    )
    metadata_bytes = {path: observation.contents.get(path) for path in metadata_paths}
    metadata_nodes = {
        path: dict(row)
        for path, row in observation.observations.items()
        if any(
            path == selected or selected.startswith(path + "/")
            for selected in metadata_paths
        )
    }

    def producer_current():
        locator_current()
        _project_current(snapshot, context, git_pair)
        nodes, content = _capture(snapshot.root, selected_scopes=metadata_paths)
        if (
            _producer_namespace(nodes) != _producer_namespace(metadata_nodes)
            or content != metadata_bytes
        ):
            _fail("original initialization producer bytes/native custody changed")

    producer_current()
    baseline = ProjectInitializationBaseline.from_dict(
        _json(observation.contents, "litai/.literate/initialization-baseline.json")
    )
    previous_origin = ProjectInitializationOrigin.from_dict(
        _json(observation.contents, "litai/.literate/initialization-origin.json")
    )
    if baseline.origin_identity != previous_origin.identity:
        _fail("original initialization origin/baseline differ")
    profile = baseline.profile
    if profile != "generated":
        _fail("native project requires its original native-template owner")
    layout_path = "litai/.literate/legacy-lift-shift.json"
    converted = layout_path in observation.contents
    if converted:
        from literate_ai.adapters.retained_layout import resolve_structural_layout

        layout = resolve_structural_layout(
            snapshot.root, _json(observation.contents, layout_path)
        )
        if (
            observation.inventory.get("retained_implementation")
            != layout.implementation_directory
        ):
            _fail("original retained layout and resource selection differ")
    elif observation.inventory.get("retained_implementation") is not None:
        _fail("retained implementation hint lacks its original declaration")
    locator_current()
    origin = _read_current_origin()
    locator_current()
    if type(origin) is not ProjectInitializationOrigin:
        _fail("original initializer did not return an exact origin record")
    from literate_ai.repository_urls import repository_origin_continues

    if (
        not repository_origin_continues(
            previous_origin.repository_url, origin.repository_url
        )
        or previous_origin.distribution_name != origin.distribution_name
    ):
        _fail("current original resource distribution differs from initializing owner")
    origin_document = origin.to_dict()
    resource_root = _original_resource_root()
    native_root = _native_root(resource_root)
    baseline_paths = {row.path.removeprefix("litai/") for row in baseline.files}
    template_map = {
        logical: resource
        for logical, resource in _TEMPLATE_MAP
        if _INCLUDE(logical, active) or logical in baseline_paths
    }

    template_map.update(
        (logical, resource)
        for logical, resource in _STARTER_MAP
        if logical in baseline_paths
    )
    paths = tuple(sorted(set(template_map.values())))
    nodes, captured = _capture(resource_root, selected_scopes=paths)
    _native_root(resource_root, native_root)
    files = {logical: captured[resource] for logical, resource in template_map.items()}
    files.update(
        (logical, _RENDER(logical, converted=converted).encode())
        for logical, _ in _STARTER_DOCS
    )
    if converted:
        files["docs/roadmap/native-rewrite-program.md"] = _NATIVE_PROGRAM(
            implementation_directory=layout.implementation_directory
        ).encode()
    if sum(map(len, files.values())) > _MAX_BYTES:
        _fail("selected original resources exceed bound")
    roles = {
        logical: (
            "root-delegate"
            if logical in _DELEGATES
            else "framework-ignore"
            if logical == ".gitignore"
            else "application-seed"
            if logical == "CHANGELOG.md"
            else "immutable-catalog"
            if logical.split("/", 1)[0] in {*CATALOG_SOURCE_ROOTS, "mcps"}
            else "framework"
        )
        for logical in files
    }
    identities = {logical: _identity(content) for logical, content in files.items()}
    identity = canonical_identity(
        {
            "domain": "existing-framework-resource-selection-v1",
            "origin": origin_document,
            "profile": profile,
            "selectors": list(selectors),
            "converted": converted,
            "files": {
                logical: {"identity": identities[logical], "role": roles[logical]}
                for logical in sorted(files)
            },
        }
    ).uri

    def current():
        _classes_current()
        _initializer_current()
        _native_root(resource_root, native_root)
        producer_current()
        current_nodes, current_bytes = _capture(resource_root, selected_scopes=paths)
        if current_nodes != nodes or current_bytes != captured:
            _fail("original initializer resource bytes/namespace changed")
        _native_root(resource_root, native_root)
        current_origin = _read_current_origin()
        if (
            type(current_origin) is not ProjectInitializationOrigin
            or current_origin.to_dict() != origin_document
        ):
            _fail("original initializer origin changed")
        _initializer_current()
        producer_current()

    values = (
        snapshot,
        context,
        origin,
        profile,
        selectors,
        converted,
        MappingProxyType(files),
        MappingProxyType(roles),
        MappingProxyType(identities),
        identity,
        current,
    )
    owner = OriginalScaffoldResourceSelection(*values)
    try:
        members = tuple(
            (
                member,
                tuple(
                    (field.name, object.__getattribute__(member, field.name))
                    for field in fields(member)
                ),
            )
            for member in (snapshot, context, definition, origin)
        )
        _register(
            owner,
            values,
            members,
            (
                metadata_bytes["litai/.literate/initialization-origin.json"],
                metadata_bytes["litai/.literate/initialization-baseline.json"],
            ),
        )
        require_current_framework_resources(owner)
    except BaseException:
        _retire(owner)
        raise
    return owner
