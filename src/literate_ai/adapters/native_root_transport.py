"""Exact native source transport preimages, never execution/qualification grants.

Only the existing portable binding payload is retained: provider name, executable
digest and fixed isolation policy. It excludes executable paths, credentials,
environment values, session state, toolchain contents and request/oracle bodies.
Replay requires an independently trusted expected binding, not one selected by
the archive being checked. No live coding CLI is required for replay.

Portable history also requires the shared bounded scope recorder: generic source
capture does not traverse a stage's transport C. A preimage left only in candidate
CAS is not a portable archive; the strict replay route refuses its missing row.
"""

from contextlib import contextmanager
from dataclasses import dataclass

from literate_ai._filesystem import require_safe_directory
from literate_ai.adapters.models import CODING_CLIS
from literate_ai.adapters.models.coding_cli import (
    CodingCliIsolation,
    CodingCliSelection,
)
from literate_ai.adapters.qualification_capture import QualificationEvidenceReader
from literate_ai.application.native_root_continuation import (
    NativeRootController,
    current_native_root_controller,
)
from literate_ai.contracts.identity import ContentIdentity, canonical_identity


class NativeRootTransportError(ValueError):
    """Original transport custody or a trusted binding preimage was refused."""


def _require(condition, name):
    if not condition:
        raise NativeRootTransportError("native_root_transport." + name)


def _document(selection):
    return {
        "schema": "literate-ai/coding-cli-tool-binding@1",
        "coding_cli": selection.name,
        "executable_identity": selection.executable_identity,
        "isolation": selection.isolation.to_dict(),
    }


def _directory_identity(path):
    require_safe_directory(path)
    metadata = path.lstat()
    return metadata.st_dev, metadata.st_ino, metadata.st_mode


@dataclass(frozen=True, slots=True)
class NativeRootTransportPreimage:
    """Comparison data only; construction does not authenticate its provenance."""

    name: str
    raw_executable_identity: ContentIdentity
    isolation: CodingCliIsolation

    @property
    def executable_identity(self):
        return self.raw_executable_identity.uri

    @property
    def tool_binding_identity(self):
        return canonical_identity(_document(self)).uri


def reopen_native_root_transport_preimage(
    reader: QualificationEvidenceReader,
    *,
    expected_provider_id: str,
    expected_tool_binding_identity: ContentIdentity,
) -> NativeRootTransportPreimage:
    """Reopen a preimage of an independently anchored provider/binding pair.

    The expected identity must come from the caller's already joined current
    promotion/qualification closure or independently held selection. Supplying
    the candidate stage's own binding as its expectation would be circular.
    This helper verifies no history/stage/qualification outcome and opens no CLI.
    """
    if (
        not isinstance(reader, QualificationEvidenceReader)
        or type(expected_provider_id) is not str
        or expected_provider_id not in CODING_CLIS
        or type(expected_tool_binding_identity) is not ContentIdentity
    ):
        raise TypeError("independently expected coding provider and binding required")
    expected_tool_binding_identity.__post_init__()
    document = reader.read_json(expected_tool_binding_identity)
    _require(
        type(document) is dict
        and set(document)
        == {"schema", "coding_cli", "executable_identity", "isolation"}
        and document["schema"] == "literate-ai/coding-cli-tool-binding@1"
        and document["coding_cli"] == expected_provider_id
        and canonical_identity(document) == expected_tool_binding_identity,
        "preimage_changed",
    )
    isolation = document["isolation"]
    _require(
        type(isolation) is dict
        and set(isolation)
        == {
            "profile",
            "clean_configuration",
            "filesystem_boundary",
            "hermetic",
            "limitations",
        }
        and type(isolation["profile"]) is str
        and bool(isolation["profile"])
        and type(isolation["filesystem_boundary"]) is str
        and bool(isolation["filesystem_boundary"])
        and type(isolation["clean_configuration"]) is bool
        and type(isolation["hermetic"]) is bool
        and type(isolation["limitations"]) is list
        and all(type(item) is str and item for item in isolation["limitations"]),
        "isolation_invalid",
    )
    _require(
        type(document["executable_identity"]) is str, "executable_identity_invalid"
    )
    transport = NativeRootTransportPreimage(
        expected_provider_id,
        ContentIdentity.parse_uri(document["executable_identity"]),
        CodingCliIsolation(
            isolation["profile"],
            isolation["clean_configuration"],
            isolation["filesystem_boundary"],
            isolation["hermetic"],
            tuple(isolation["limitations"]),
        ),
    )
    _require(
        transport.tool_binding_identity == expected_tool_binding_identity.uri,
        "preimage_changed",
    )
    return transport


@dataclass(frozen=True, slots=True)
class _NativeRootTransportCapture:
    controller: object
    scope: object
    original_run: object
    runner: object
    generator: object
    selection: CodingCliSelection
    selection_guard: object
    selection_guard_function: object
    prepared: object
    cas: object
    namespace_witness: tuple
    cas_root: object
    cas_root_identity: tuple
    cas_blob_root: object
    cas_blob_root_identity: tuple
    expected_binding: ContentIdentity
    document_identity: ContentIdentity

    def _require_custody(self):
        # Inspect the class dictionary before instance descriptor binding, so a
        # substituted descriptor cannot run foreign code merely during this check.
        _require(
            type(self.selection).__dict__.get("require_unchanged")
            is self.selection_guard_function,
            "original_custody_changed",
        )
        current_guard = self.selection.require_unchanged
        _require(
            current_native_root_controller() is self.controller
            and self.controller.scope is self.scope
            and self.scope.original_run is self.original_run
            and self.controller.prepared_candidate is self.prepared
            and self.prepared.plan.component_revision
            == self.scope.run_binding.root_revision
            and self.prepared.plan.identity
            == self.scope.run_binding.original_generation_plan_identity
            and self.runner.generator is self.generator
            and self.runner._original_source_generator is self.generator
            and self.generator.selection is self.selection
            and self.runner._original_coding_cli_selection is self.selection
            and self.runner._original_coding_cli_binding == self.expected_binding
            and self.runner._original_coding_cli_guard is self.selection_guard
            and getattr(self.selection_guard, "__self__", None) is self.selection
            and getattr(self.selection_guard, "__func__", None)
            is self.selection_guard_function
            and getattr(current_guard, "__self__", None) is self.selection
            and getattr(current_guard, "__func__", None)
            is self.selection_guard_function
            and type(self.selection).require_unchanged is self.selection_guard_function
            and self.runner.cas is self.cas
            and self.runner._original_candidate_cas is self.cas
            and self.runner._original_candidate_cas_root is self.cas_root
            and self.runner._original_candidate_blob_root is self.cas_blob_root
            and self.runner._original_candidate_namespace_witness
            is self.namespace_witness
            and self.cas.root is self.cas_root
            and self.cas.blob_root is self.cas_blob_root
            and _directory_identity(self.cas_root) == self.cas_root_identity
            and _directory_identity(self.cas_blob_root) == self.cas_blob_root_identity
            and self.runner.retained_source is None,
            "original_custody_changed",
        )
        _require(
            ContentIdentity.parse_uri(self.selection.tool_binding_identity)
            == self.expected_binding
            and canonical_identity(_document(self.selection)) == self.document_identity
            and self.document_identity == self.expected_binding,
            "original_binding_changed",
        )

    def require_current(self):
        self.controller.require_current()
        self._require_custody()
        self.selection_guard_function(self.selection)
        self.controller.require_current()
        # The original guards are callbacks too: they cannot redirect the final
        # CAS/selection/candidate custody check after its observation.
        self._require_custody()

    @contextmanager
    def guarded(self):
        self.require_current()
        primary = None
        try:
            yield
        except BaseException as error:
            primary = error
            raise
        finally:
            try:
                self.require_current()
            except BaseException:
                if primary is None:
                    raise
                try:
                    BaseException.add_note(
                        primary,
                        "original native source transport closing guard refused",
                    )
                except BaseException:
                    pass

    def retain(self, generation):
        with self.guarded():
            _require(
                generation.coding_cli == self.selection.name
                and generation.executable_identity == self.selection.executable_identity
                and generation.coding_cli_tool_binding_identity
                == self.expected_binding.uri
                and generation.isolation_profile == self.selection.isolation.profile
                and generation.hermetic == self.selection.isolation.hermetic,
                "stage_transport_changed",
            )
            document = _document(self.selection)
            _require(
                self.cas.put_manifest(document).identity == self.expected_binding.uri,
                "preimage_retention_changed",
            )
            _require(
                self.scope.retain_record(document) == self.expected_binding,
                "preimage_retention_changed",
            )


def begin_native_root_transport_capture(controller, runner, prepared):
    """Bind only an explicit live original controller and admitted CLI selection."""
    if type(controller) is not NativeRootController:
        raise TypeError("original current native root controller required")
    # Seal original references before invoking either owner's foreign guards.
    selection = runner._original_coding_cli_selection
    if type(selection) is not CodingCliSelection:
        raise TypeError("original admitted coding CLI selection required")
    cas = runner._original_candidate_cas
    scope = controller._original_scope
    witness = runner._original_candidate_namespace_witness
    (root, root_identity), (blob_root, blob_root_identity) = witness
    expected = runner._original_coding_cli_binding
    if type(expected) is not ContentIdentity:
        raise TypeError("original admitted coding CLI binding required")
    guard = runner._original_coding_cli_guard
    guard_function = getattr(guard, "__func__", None)
    if getattr(guard, "__self__", None) is not selection or guard_function is None:
        raise TypeError("original admitted bound coding CLI guard required")
    capture = _NativeRootTransportCapture(
        controller,
        scope,
        scope.original_run,
        runner,
        runner._original_source_generator,
        selection,
        guard,
        guard_function,
        prepared,
        cas,
        witness,
        root,
        root_identity,
        blob_root,
        blob_root_identity,
        expected,
        canonical_identity(_document(selection)),
    )
    capture.require_current()
    return capture
