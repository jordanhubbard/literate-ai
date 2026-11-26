"""Actual producer-first SOURCE milestone, not installed/release qualification.

Each clean qualification run has a genuine late native mismatch and one fresh
replacement. All qualification/promotion/stage/native streams/current/archive
observations are real. Only the external source CLI and editable SOURCE
distribution observation are controlled. The configured-consumer vertical slice
remains separate required work; this milestone does not claim its completion.
"""

import io
import json
import os
import shlex
import shutil
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from unittest import mock

from literate_ai.adapters import project_initialization as initialization
from literate_ai.adapters import retained_provider_authority as provider_authority
from literate_ai.adapters import standard_lifecycle_binding as binding
from literate_ai.adapters.evidence_storage import FileSystemEvidenceStore
from literate_ai.adapters.native_root_retained_ingress import (
    read_native_root_retained_ingress,
)
from literate_ai.adapters.qualification_archive import reopen_qualification_archive
from literate_ai.adapters.qualification_capture import reopen_qualification_products
from literate_ai.adapters.retained_provider_authority import (
    read_retained_provider_authority,
)
from literate_ai.adapters.retained_provider_native import read_retained_provider_native
from literate_ai.application.generation_preparation import GenerationPreparationRequest
from literate_ai.cli import main
from literate_ai.cli import rebuild as rebuild_cli
from literate_ai.contracts import ProjectInitializationOrigin
from literate_ai.contracts.blobs import BlobRef
from literate_ai.contracts.identity import ContentIdentity
from literate_ai.contracts.native_root_continuation import (
    NativeRootAcceptanceClosure,
    NativeRootAcceptanceRejection,
    NativeRootContinuationLedger,
    NativeRootRunBinding,
)
from literate_ai.security.evidence.storage import EvidenceReadLimits
from tests.support.fixtures_public_qualified_native_provider import (
    prepare_public_qualified_native_provider,
)
from tests.support.fixtures_rust_library_harness import prepare_native_verifier_class


@unittest.skipUnless(
    os.name == "posix" and shutil.which("make") and shutil.which("git"),
    "SOURCE public producer requires the existing POSIX native fixture",
)
class ActualPublicQualifiedNativeLateFirstTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepare_native_verifier_class(cls)

    def test_actual_two_clean_late_first_runs_have_strict_complete_replay(
        self,
    ):
        base = Path(
            tempfile.mkdtemp(prefix="actual public qualified native late first ")
        ).resolve()
        base.chmod(0o700)
        succeeded = False

        def cleanup():
            if (
                succeeded
                and os.environ.get("LITAI_TEST_RETAIN_NATIVE_LATE_FIXTURE") != "1"
            ):
                shutil.rmtree(base)
            else:
                # A retained failed fixture can contain a disposable test signing
                # key; keep the entire root private. Never print key contents.
                print(f"Retained private public-native fixture: {base}")

        self.addCleanup(cleanup)
        environment = {
            key: value
            for key, value in self.environment.items()
            if not key.startswith(("LITAI_", "GIT_"))
        }
        home, cargo_home = base / "home", base / "cargo-home"
        home.mkdir()
        cargo_home.mkdir()
        environment.update(
            HOME=str(home),
            CARGO_HOME=str(cargo_home),
            CARGO_NET_OFFLINE="true",
            CARGO_BUILD_JOBS="2",
            CARGO_INCREMENTAL="0",
            CARGO=shlex.quote(self.cargo.command[0]),
            RUSTC=shlex.quote(self.rustc.command[0]),
            BUILD_DIR=str(base / "build"),
            OBJ_DIR=str(base / "obj"),
        )
        distribution = binding.InstalledFrameworkDistribution(
            "literate-ai",
            "1.1.0",
            (
                binding.InstalledFrameworkDistributionMember(
                    "literate_ai/__init__.py", 1, "sha256:" + "a" * 64
                ),
            ),
        )
        origin = ProjectInitializationOrigin(
            repository_url="https://example.invalid/disposable-source-fixture.git",
            git_revision="a" * 40,
            distribution_name="literate-ai",
            distribution_version="1.1.0",
        )
        original_resolve = binding.resolve_standard_project_lifecycle_driver

        def resolve(driver, **options):
            options.setdefault("distribution_observer", lambda: distribution)
            return original_resolve(driver, **options)

        calls = []

        def invoke(arguments):
            out, err = io.StringIO(), io.StringIO()
            with mock.patch.dict(os.environ, environment, clear=True):
                code = main(["--json", *arguments], stdout=out, stderr=err)
            payload = out.getvalue() if code == 0 else err.getvalue()
            envelope = json.loads(payload)
            calls.append((arguments[:2], code))
            (base / f"call-{len(calls)}.stdout").write_text(out.getvalue())
            (base / f"call-{len(calls)}.stderr").write_text(err.getvalue())
            return code, envelope

        with ExitStack() as stack:
            # Explicit existing SOURCE-only observation seam, not installed
            # provenance. Every original binding/currentness guard remains real.
            stack.enter_context(
                mock.patch.object(
                    binding, "resolve_standard_project_lifecycle_driver", resolve
                )
            )
            stack.enter_context(
                mock.patch.object(
                    rebuild_cli, "resolve_standard_project_lifecycle_driver", resolve
                )
            )
            stack.enter_context(
                mock.patch.object(
                    provider_authority,
                    "resolve_standard_project_lifecycle_driver",
                    resolve,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    initialization,
                    "observe_installed_framework_distribution",
                    lambda: distribution,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    initialization, "_installed_distribution_origin", lambda: origin
                )
            )
            fixture = prepare_public_qualified_native_provider(
                base / "producer",
                self.seed,
                self.cargo,
                self.rustc,
                invoke=invoke,
                environment=environment,
                late_first_per_clean=True,
            )
            oracle_bytes = fixture.oracle.oracle_path.read_bytes()
            histories = []
            with mock.patch.dict(os.environ, environment, clear=True):
                current = read_retained_provider_authority(
                    fixture.project,
                    GenerationPreparationRequest(
                        component_root=fixture.component,
                        target_name="host",
                        flavor_roots=(),
                    ),
                    provider_id="claude",
                    profile_path=fixture.profile.relative_to(
                        fixture.project
                    ).as_posix(),
                )
                native = read_retained_provider_native(current)
                ingress = read_native_root_retained_ingress(native)
                self.assertIsNotNone(ingress)
                result = current.promotion.evidence.qualification_lifecycle_result
                self.assertIsNotNone(result)
                self.assertEqual(len(result.runs), 2)
                reference = BlobRef.from_dict(fixture.retained_evidence["archive"])
                limits = EvidenceReadLimits(
                    maximum_blob_bytes=256 * 1024**2, maximum_total_bytes=256 * 1024**2
                )
                store = FileSystemEvidenceStore(
                    fixture.evidence_store, writable=False, limits=limits
                )
                payload = store.get_bytes(reference)
                reader = reopen_qualification_archive(
                    payload, reference, max_bytes=256 * 1024**2, max_records=100_000
                )
                captures = []
                for member in fixture.retained_evidence["runs"]:
                    native.require_unchanged()
                    capture = reopen_qualification_products(
                        reader,
                        qualification_identity=ContentIdentity.parse_uri(
                            fixture.retained_evidence["qualification_identity"]
                        ),
                        run_identity=ContentIdentity.parse_uri(member["run_identity"]),
                        exports_identity=ContentIdentity.parse_uri(
                            member["export_set_identity"]
                        ),
                        max_package_bytes=256 * 1024**2,
                        component_lock=current.generation.prepared.locked_authority_snapshot.authority.lock,
                        oracle=native.oracle,
                        current_recipes=current.generation.recipes,
                        current_commands=native.commands,
                        current_profile=current.qualification.profile,
                        current_driver=current.lifecycle.driver,
                        native_root_ingress=ingress,
                    )
                    self.assertIsNotNone(capture.verified_lifecycle)
                    lifecycle = capture.verified_lifecycle
                    root = lifecycle.root_integration
                    self.assertIsNotNone(root)

                    def typed(kind, identity):
                        record = kind.from_dict(reader.read_json(identity))
                        self.assertEqual(record.identity, identity)
                        return record

                    closure = typed(
                        NativeRootAcceptanceClosure,
                        root.independent_acceptance_identity,
                    )
                    run = typed(NativeRootRunBinding, closure.run_binding_identity)
                    ledger = typed(
                        NativeRootContinuationLedger, closure.ledger_identity
                    )
                    closure.require_records(run, ledger)
                    self.assertEqual(ledger.disposition, "accepted")
                    self.assertEqual(len(ledger.attempts), 2)
                    first, final = ledger.attempts
                    self.assertEqual((first.ordinal, final.ordinal), (0, 1))
                    self.assertEqual(
                        (first.outcome, final.outcome),
                        ("package-rejected", "root-accepted"),
                    )
                    self.assertEqual(first.retryability, "retryable")
                    self.assertEqual(final.retryability, "none")
                    self.assertEqual(final.incoming_request_kind, "native-root-repair")
                    self.assertEqual(
                        final.predecessor_root_attempt_identities, (first.identity,)
                    )
                    self.assertNotEqual(
                        first.bounded_generation_request_identity,
                        final.bounded_generation_request_identity,
                    )
                    self.assertNotEqual(
                        first.workspace_allocation_identity,
                        final.workspace_allocation_identity,
                    )
                    self.assertNotEqual(
                        first.source_output_identity, final.source_output_identity
                    )
                    rejection = typed(
                        NativeRootAcceptanceRejection, first.failure_evidence_identity
                    )
                    rejection.require_binding(run)
                    self.assertEqual(rejection.acceptance_scope, "packaged-root")
                    self.assertEqual(rejection.decision, "result-values-differ")
                    self.assertEqual(rejection.candidate_ordinal, 0)
                    self.assertEqual(
                        rejection.packaged_binding, first.final_packaged_binding
                    )
                    self.assertEqual(
                        rejection.bounded_generation_request_identity,
                        first.bounded_generation_request_identity,
                    )
                    self.assertEqual(
                        rejection.workspace_allocation_identity,
                        first.workspace_allocation_identity,
                    )
                    self.assertEqual(
                        rejection.source_output_identity, first.source_output_identity
                    )
                    self.assertIsNone(final.failure_evidence_identity)
                    self.assertEqual(
                        closure.actual_independent_acceptance_identity,
                        final.actual_packaged_acceptance_identity,
                    )
                    # The strict public reopen above already verified BOTH
                    # actual source/package/native histories under current
                    # trusted ingress. These assertions inspect exact retained
                    # records; they do not replace that verification.
                    histories.append(
                        {
                            "run_binding_identity": run.identity.uri,
                            "run_nonce": run.run_nonce,
                            "original_deadline_identity": (
                                run.original_deadline_identity.uri
                            ),
                            "ledger_identity": ledger.identity.uri,
                            "attempts": [row.identity.uri for row in ledger.attempts],
                            "rejection_identity": rejection.identity.uri,
                            "actual_acceptance_identity": (
                                closure.actual_independent_acceptance_identity.uri
                            ),
                        }
                    )
                    captures.append(capture)
                    native.require_unchanged()
                self.assertEqual(len(captures), 2)
                self.assertEqual(len({row.run.run_identity for row in captures}), 2)
                self.assertEqual(
                    len({row.verified_lifecycle.identity for row in captures}), 2
                )
                self.assertEqual(len({row["run_nonce"] for row in histories}), 2)
                self.assertEqual(
                    len({row["original_deadline_identity"] for row in histories}), 2
                )
                self.assertEqual(
                    len({row["run_binding_identity"] for row in histories}), 2
                )
                self.assertEqual(
                    len({attempt for row in histories for attempt in row["attempts"]}),
                    4,
                )
                requests = [
                    json.loads(line)
                    for line in fixture.request_log.read_text().splitlines()
                ]
                self.assertEqual(len(requests), 4)
                self.assertEqual(len({row["workspace"] for row in requests}), 4)
                self.assertEqual(
                    len({(row["workspace"], row["request"]) for row in requests}), 4
                )
                suffix = "\n\n## Bounded root candidate-repair evidence\n"
                self.assertEqual(
                    tuple(suffix in row["request"] for row in requests),
                    (False, True, False, True),
                )
                self.assertEqual(fixture.oracle.oracle_path.read_bytes(), oracle_bytes)
        (base / "producer-late-first-receipt.json").write_text(
            json.dumps(
                {
                    "schema": (
                        "actual-public-native-producer-late-first-source-checkpoint@1"
                    ),
                    "actual_clean_runs": 2,
                    "actual_closed_history_reopens": 2,
                    "actual_requests_and_workspaces": 4,
                    "histories": histories,
                    "verifier_timeout_seconds_selected_before_admission": 300,
                    "whole_run_seconds": 1800,
                    "source_distribution_observation": "explicitly synthetic",
                    "external_source_provider": "controlled local process",
                    "qualified_consumer_vertical_slice": "pending",
                    "installed_qualification": "pending",
                    "calls": calls,
                },
                indent=2,
            )
        )
        succeeded = True
