"""Actual producer-first SOURCE milestone, not installed/release qualification.

All qualification/promotion/stage/native streams/current/archive observations are
real. Only the external source CLI and editable SOURCE distribution observation
are controlled. The subsequent configured-consumer vertical slice is separate
required work; this milestone does not claim its completion.
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
from literate_ai.security.evidence.storage import EvidenceReadLimits
from tests.support.fixtures_public_qualified_native_provider import (
    prepare_public_qualified_native_provider,
)
from tests.support.fixtures_rust_library_harness import prepare_native_verifier_class


@unittest.skipUnless(
    os.name == "posix" and shutil.which("make") and shutil.which("git"),
    "SOURCE public producer requires the existing POSIX native fixture",
)
class ActualPublicQualifiedNativeProducerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        prepare_native_verifier_class(cls)

    def test_actual_two_clean_public_runs_then_original_current_full_history_reopen(
        self,
    ):
        base = Path(
            tempfile.mkdtemp(prefix="actual public qualified native ")
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
            )
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
                    captures.append(capture)
                    native.require_unchanged()
                self.assertEqual(len(captures), 2)
                self.assertEqual(len({row.run.run_identity for row in captures}), 2)
                self.assertEqual(
                    len({row.verified_lifecycle.identity for row in captures}), 2
                )
        (base / "producer-receipt.json").write_text(
            json.dumps(
                {
                    "schema": "actual-public-native-producer-source-checkpoint@1",
                    "actual_clean_runs": 2,
                    "actual_closed_history_reopens": 2,
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
