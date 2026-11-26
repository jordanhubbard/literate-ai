"""Additive live-captured promotion assertions; readers never restore owners."""

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath

from literate_ai.adapters.retained_project_receipt import AdmittedRetainedProject
from literate_ai.adapters.retained_unit_planning_evidence import (
    retain_retained_unit_planning_evidence,
)
from literate_ai.adapters.retained_unit_run_evidence import (
    retain_retained_unit_run_evidence,
)
from literate_ai.contracts import BlobRef, canonical_identity, canonical_json_bytes

SCHEMA = "literate-ai/retained-project-promotion-evidence@1"
ADMISSION_SCHEMA = "literate-ai/retained-project-historical-admission@1"
MAX_METADATA = 128 * 1024**2
MAX_MEMORY = 2 * 1024**3
MAX_DOCUMENT = 64 * 1024**2
MAX_CONTEXT = 32 * 1024**2


@dataclass(frozen=True)
class HistoricalReadPolicy:
    """Finite historical reads, without a package provider or execution grant."""

    max_provider_metadata_bytes: int = MAX_METADATA
    max_provider_memory_bytes: int = MAX_MEMORY
    max_closure_steps: int = 1_000_000

    def __post_init__(self):
        if (
            type(self.max_provider_metadata_bytes) is not int
            or not 1 <= self.max_provider_metadata_bytes <= MAX_METADATA
            or type(self.max_provider_memory_bytes) is not int
            or not 1 <= self.max_provider_memory_bytes <= MAX_MEMORY
            or type(self.max_closure_steps) is not int
            or not 1 <= self.max_closure_steps <= 1_000_000
        ):
            raise ValueError("retained.promotion.finite-read-policy-required")


def _require(condition):
    if not condition:
        raise ValueError("retained.promotion.historical-context-differs")


def _admission_document(admission, planning_ref, run_ref, contexts_identity):
    receipt, run = admission.receipt, admission.run
    return {
        "schema": ADMISSION_SCHEMA,
        "retained_receipt_identity": receipt.identity.uri,
        "plan_identity": run.source_bom.plan.identity.uri,
        "completed_run_identity": run.identity.uri,
        "source_manifest_identity": run.source_bom.manifest.identity.uri,
        "output_manifest_identity": run.output_manifest.identity.uri,
        "payload_manifest_identity": receipt.root("payload-manifest").identity,
        "project_test_policy_identity": run.configured_test_policy.identity.uri,
        "planning_evidence": planning_ref.to_dict(),
        "accepted_run_evidence": run_ref.to_dict(),
        "command_contexts_identity": contexts_identity.uri,
        "capture_owner": "original-live-retained-workspace",
        "required_sdk_scopes_checked": True,
        "admission_issued": False,
        "release_authorized": False,
    }


def retain_retained_promotion_evidence(admission, workspace, *, admission_guard=None):
    """Capture only inside the original runtime, while genuine scopes are live.

    This function accepts live Python owners, never receipt JSON or an admission
    boolean. The resulting assertion cannot authorize an SDK, workspace or LINK.
    """
    from literate_ai.adapters.retained_project_execution import (
        RetainedProjectExecutionWorkspace,
    )

    if not isinstance(admission, AdmittedRetainedProject) or not isinstance(
        workspace, RetainedProjectExecutionWorkspace
    ):
        raise TypeError("retained.promotion.original-live-owners-required")
    if (
        workspace.source != admission.source
        or workspace.plan != admission.run.source_bom.plan
        or workspace.current_plan is not admission.current_plan
        or workspace._promotion_contexts is None
    ):
        raise ValueError("retained.promotion.original-workspace-capture-required")
    guard = admission.require_current if admission_guard is None else admission_guard
    if not callable(guard):
        raise TypeError("retained.promotion.live-currentness-guard-required")

    def current():
        guard()
        admission.require_current()
        admission.require_native_package_scope()
        workspace._require_private_current()

    current()
    rows = workspace._promotion_contexts
    expected = len(admission.run.observations) + len(
        admission.run.acceptance_observations
    )
    if len(rows) != expected or 512 * expected > MAX_MEMORY:
        raise ValueError("retained.promotion.complete-live-contexts-required")
    contexts = canonical_json_bytes(rows)
    if len(contexts) > MAX_CONTEXT or 16 * len(contexts) > MAX_MEMORY:
        raise ValueError("retained.promotion.context-budget")
    planning = retain_retained_unit_planning_evidence(admission)
    run = retain_retained_unit_run_evidence(
        admission,
        maximum_bytes=MAX_METADATA - len(contexts),
        maximum_memory_bytes=MAX_MEMORY - 16 * len(contexts),
        admission_guard=admission.require_current,
        metadata_poll_guard=workspace._require_current_plan,
    )
    assertion = _admission_document(admission, planning, run, canonical_identity(rows))
    document = {
        "schema": SCHEMA,
        "retained_receipt_identity": admission.receipt.identity.uri,
        "planning_evidence": planning.to_dict(),
        "accepted_run_evidence": run.to_dict(),
        "historical_admission": assertion,
        "command_contexts": rows,
        "admission_issued": False,
        "release_authorized": False,
    }
    raw = canonical_json_bytes(document)
    if len(raw) > MAX_DOCUMENT or 16 * len(raw) > MAX_MEMORY:
        raise ValueError("retained.promotion.evidence-budget")
    current()
    reference = admission.store.put_bytes(raw, media_type="application/json")
    current()
    if canonical_json_bytes(workspace._promotion_contexts) != contexts:
        raise ValueError("retained.promotion.live-contexts-changed")
    return reference


def verify_promotion_evidence_context(document, inputs, run, *, store, guard, policy):
    """Verify exact historical context/dependencies; never call a live owner."""
    from literate_ai.adapters.retained_sdk_command_context import (
        verify_retained_sdk_command_context,
    )

    fields = {
        "schema",
        "retained_receipt_identity",
        "planning_evidence",
        "accepted_run_evidence",
        "historical_admission",
        "command_contexts",
        "admission_issued",
        "release_authorized",
    }
    _require(type(document) is dict and set(document) == fields)
    _require(document["schema"] == SCHEMA)
    _require(document["retained_receipt_identity"] == inputs.receipt.identity.uri)
    _require(
        document["admission_issued"] is False
        and document["release_authorized"] is False
    )
    contexts = document["command_contexts"]
    chronological = []
    for observation in run.observations:
        chronological.append(observation)
        if observation.action.stage == "accept":
            chronological.extend(
                o
                for o in run.acceptance_observations
                if next(
                    c
                    for c in run.acceptance_policy.cases
                    if c.identity == o.case_identity
                ).action_id
                == observation.action.action_id
            )
    _require(type(contexts) is list and len(contexts) == len(chronological))
    _require(512 * len(contexts) <= policy.max_provider_memory_bytes)
    assertion = document["historical_admission"]
    # Construct expected pure facts without creating or copying a live capability.
    expected = {
        "schema": ADMISSION_SCHEMA,
        "retained_receipt_identity": inputs.receipt.identity.uri,
        "plan_identity": inputs.plan.identity.uri,
        "completed_run_identity": run.identity.uri,
        "source_manifest_identity": inputs.source_manifest.identity.uri,
        "output_manifest_identity": inputs.output_manifest.identity.uri,
        "payload_manifest_identity": inputs.payload_manifest.identity.uri,
        "project_test_policy_identity": run.configured_test_policy.identity.uri,
        "planning_evidence": document["planning_evidence"],
        "accepted_run_evidence": document["accepted_run_evidence"],
        "command_contexts_identity": canonical_identity(contexts).uri,
        "capture_owner": "original-live-retained-workspace",
        "required_sdk_scopes_checked": True,
        "admission_issued": False,
        "release_authorized": False,
    }
    _require(assertion == expected)
    tools = {name: identity for name, _path, identity in inputs.plan.profile.tools}
    base_anchor = None
    for captured, observed in zip(contexts, chronological, strict=True):
        guard()
        _require(
            type(captured) is dict
            and set(captured)
            == {
                "observation_identity",
                "command_identity",
                "context",
                "dependency_document",
                "filesystem_dependency_document",
            }
        )
        _require(captured["observation_identity"] == observed.identity.uri)
        ordinary = hasattr(observed, "action")
        command_id = (
            canonical_identity(observed.action.to_dict())
            if ordinary
            else observed.case_identity
        )
        _require(captured["command_identity"] == command_id.uri)
        context = captured["context"]
        manifest = (
            observed.output_manifest
            if ordinary
            else next(
                o.output_manifest
                for o in run.observations
                if o.action.action_id
                == next(
                    c.action_id
                    for c in run.acceptance_policy.cases
                    if c.identity == observed.case_identity
                )
            )
        )
        verify_retained_sdk_command_context(
            context,
            plan=inputs.plan,
            manifest=inputs.source_manifest,
            output_manifest=manifest,
            acceptance_policy=run.acceptance_policy,
            command_identity=command_id,
            phase=observed.action.stage if ordinary else "accept",
        )
        anchor = (
            context["platform"],
            context["workspace_root"],
            context["substitutions"],
        )
        if base_anchor is None:
            base_anchor = anchor
        _require(anchor == base_anchor)
        if ordinary:
            _require(observed.tool_identity == tools[observed.action.tool])
            _require(
                observed.environment_identity
                == canonical_identity(context["environment"])
            )
            _require(captured["filesystem_dependency_document"] is None)
            import json

            _require(
                captured["dependency_document"]["observation"]
                == json.loads(run.resolved_bom.tool_observation)
            )
        else:
            _require(observed.command_identity == canonical_identity(context["argv"]))
        dependency = captured["dependency_document"]
        _require(canonical_identity(dependency) == observed.dependency_identity)
        if ordinary:
            _require(
                type(dependency) is dict
                and set(dependency)
                == {
                    "schema",
                    "plan_identity",
                    "manifest_identity",
                    "environment_identity",
                    "observation",
                }
            )
            _require(
                dependency["schema"]
                == "literate-ai/retained-native-dependency-observation@1"
            )
            _require(
                dependency["manifest_identity"] == inputs.source_manifest.identity.uri
            )
            _require(
                dependency["environment_identity"] == observed.environment_identity.uri
            )
        else:
            _verify_export_document(
                dependency, inputs.plan, manifest, context, environment_identity=None
            )
            file_dependency = captured["filesystem_dependency_document"]
            if observed.filesystem_observation is None:
                _require(file_dependency is None)
            else:
                _require(
                    canonical_identity(file_dependency)
                    == observed.filesystem_dependency_identity
                )
                _require(
                    canonical_identity(context["environment"])
                    == observed.filesystem_environment_identity
                )
                _verify_export_document(
                    file_dependency,
                    inputs.plan,
                    manifest,
                    context,
                    environment_identity=observed.filesystem_environment_identity,
                )
        _require(dependency["plan_identity"] == inputs.plan.identity.uri)
    guard()
    return canonical_identity(assertion)


def _verify_export_document(document, plan, manifest, context, *, environment_identity):
    _require(
        type(document) is dict
        and set(document)
        == {
            "schema",
            "plan_identity",
            "output_manifest_identity",
            "environment_identity",
            "observation",
        }
    )
    _require(
        document["schema"] == "literate-ai/retained-export-dependency-observation@1"
    )
    _require(document["plan_identity"] == plan.identity.uri)
    _require(document["output_manifest_identity"] == manifest.identity.uri)
    environment = dict(context["environment"])
    if environment_identity is None:
        # Filesystem cases change only HOME/TMP, while the ordinary dependency
        # guard was captured from the same original workspace environment.
        path = PureWindowsPath if context["platform"] == "windows" else PurePosixPath
        root = path(context["workspace_root"])
        environment.update(HOME=str(root / "home"))
        environment.update(
            {key: str(root / "tmp") for key in ("TMPDIR", "TMP", "TEMP")}
        )
    _require(document["environment_identity"] == canonical_identity(environment).uri)
    _require(
        environment_identity is None
        or canonical_identity(environment) == environment_identity
    )
    graph = document["observation"]
    from literate_ai.adapters.dependencies.types import HostDependencyObservation
    from literate_ai.adapters.retained_project_dependencies import _freeze
    from literate_ai.contracts.sbom import retained_project_bom_ref

    _require(type(graph) is dict and set(graph) == {"components", "edges"})
    observed = HostDependencyObservation(
        tuple(graph["components"]), tuple(tuple(v) for v in graph["edges"])
    )
    _require(
        _freeze(observed, retained_project_bom_ref(plan.identity))
        == canonical_json_bytes(graph)
    )


def verify_native_export_members(
    store, inputs, evidence, guard, *, charge=lambda data: None
):
    """Join actual retained native image bytes to captured export graph records.

    External system-library hashes remain original producer observations. This
    checks physical retained export membership, not current OS/SDK admission.
    """

    class Prefix:
        def __init__(self):
            self.data = bytearray()

        def write(self, data):
            guard()
            charge(data)
            if len(self.data) < 4096:
                self.data.extend(data[: 4096 - len(self.data)])
            return len(data)

    cases = [
        r
        for r in evidence["command_contexts"]
        if r["dependency_document"]["schema"]
        == "literate-ai/retained-export-dependency-observation@1"
    ]
    for member in inputs.output_manifest.members:
        if member.symlink_target is not None:
            continue
        guard()
        prefix = Prefix()
        store.stream_to(BlobRef(member.sha256, member.size), prefix)
        head = bytes(prefix.data)
        native = head[:4] in {
            b"\x7fELF",
            b"\xfe\xed\xfa\xce",
            b"\xce\xfa\xed\xfe",
            b"\xfe\xed\xfa\xcf",
            b"\xcf\xfa\xed\xfe",
            b"\xca\xfe\xba\xbe",
            b"\xbe\xba\xfe\xca",
            b"\xca\xfe\xba\xbf",
            b"\xbf\xba\xfe\xca",
        }
        if head[:2] == b"MZ":
            _require(len(head) >= 64)
            pe = int.from_bytes(head[60:64], "little")
            _require(64 <= pe <= 4092)
            native = head[pe : pe + 4] == b"PE\0\0"
        if not native:
            continue
        found = False
        for row in cases:
            context = row["context"]
            path = (
                PureWindowsPath if context["platform"] == "windows" else PurePosixPath
            )
            expected = path(context["workspace_root"]) / "outputs" / member.path
            properties = {
                "literate-ai:elf-path",
                "literate-ai:pe-path",
                "literate-ai:macho-path",
            }
            for component in row["dependency_document"]["observation"]["components"]:
                paths = [
                    p["value"]
                    for p in component.get("properties", [])
                    if p.get("name") in properties
                ]
                if str(expected) in paths:
                    _require(
                        {"alg": "SHA-256", "content": member.sha256}
                        in component.get("hashes", [])
                    )
                    found = True
        _require(found)
        guard()
