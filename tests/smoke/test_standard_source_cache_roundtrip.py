"""Accepted-cache round trip for complete Standard source-generation evidence."""

from __future__ import annotations

import os
import shutil
import tarfile
import tempfile
import unittest
from contextlib import ExitStack
from copy import copy
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters.cache import (
    FileSystemSourceCache,
    FilesystemStandardAcceptedSourcePublisher,
    FilesystemStandardSourceRestorer,
    SourceCacheMaterializer,
    SourceCacheResolver,
    restore_standard_source_cache_membership,
)
from literate_ai.adapters.cache.filesystem import _native_filesystem_path
from literate_ai.adapters.source_materialization import (
    capture_accepted_source_cache_archive,
)
from literate_ai.application import (
    StandardAcceptedSourcePublication,
    StandardProjectLifecycleError,
)
from literate_ai.contracts import (
    AcceptedSourceCacheEntry,
    GeneratedSourceCandidate,
    SourceCacheMode,
    SourceGenerationProvenance,
    SourceGenerationResumeCandidate,
    SourceGenerationRunOutput,
    StandardAcceptedSourceCacheEntry,
    StandardBuildEvidence,
    StandardComponentAcceptanceEvidence,
    StandardExecutionEvidence,
    StandardGeneratedTestCaseEvidence,
    StandardGeneratedTestExecutionEvidence,
)
from literate_ai.contracts.standard_lifecycle import (
    StandardSourceCacheMembershipDocument,
)
from literate_ai.remote_source_guard import extract_accepted_source_cache_archive
from literate_ai.storage import FileSystemCAS
from tests.support.fixtures_test_source_cache import (
    _accepted_entry,
    _cache_key,
    _configuration,
    _identity,
    _target,
)
from tests.support.fixtures_test_standard_post_source_evidence import _export


def _standard_entry(
    cas: FileSystemCAS, *, suffix: str = "standard"
) -> StandardAcceptedSourceCacheEntry:
    legacy = _accepted_entry(cas, suffix=suffix)
    derivation = legacy.derivation
    key = derivation.cache_key
    candidate = GeneratedSourceCandidate(
        component_revision=_identity(f"{suffix}-component-revision"),
        # This is the bounded framework request, not the coding-agent prompt
        # identity stored in SourceDerivationCacheKey.request_identity.
        source_generation_request_identity=_identity(f"{suffix}-source-request"),
        planned_coding_cli_request_identity=key.request_identity,
        component_generation_plan_identity=_identity(f"{suffix}-generation-plan"),
        generation_key_identity=_identity(f"{suffix}-generation-key"),
        context_manifest_identity=_identity(f"{suffix}-context"),
        prompt_identity=_identity(f"{suffix}-prompt"),
        recipe_identity=key.recipe_identity,
        workspace_allocation_identity=_identity(f"{suffix}-workspace"),
        tree_identity=derivation.source_tree_identity,
        source_bundle_identity=_identity(f"{suffix}-source-bundle"),
        source_manifest_identity=_identity(f"{suffix}-source-manifest"),
        source_bom_identity=derivation.source_sbom_identity,
        generated_test_suite_identity=derivation.generated_test_suite_identity,
    )
    provenance = SourceGenerationProvenance(
        candidate.source_generation_request_identity,
        candidate.planned_coding_cli_request_identity,
        derivation.component_lock_identity,
        _identity(f"{suffix}-application-root"),
        candidate.component_revision,
        candidate.component_generation_plan_identity,
        candidate.generation_key_identity,
        candidate.context_manifest_identity,
        candidate.prompt_identity,
        candidate.recipe_identity,
        candidate.workspace_allocation_identity,
        _identity(f"{suffix}-readiness"),
        (_identity(f"{suffix}-route"),),
        (_identity(f"{suffix}-model-output"),),
        candidate.identity,
    )
    provenance_evidence = cas.put_manifest(provenance.to_dict())
    assert provenance_evidence.identity == provenance.identity.uri
    output = SourceGenerationRunOutput(
        candidate,
        candidate.identity,
        provenance,
        provenance.identity,
    )
    resume = SourceGenerationResumeCandidate(
        output,
        output.identity,
        _identity(f"{suffix}-complexity-budget"),
        _identity(f"{suffix}-complexity-decision"),
    )
    membership = StandardSourceCacheMembershipDocument(
        candidate.component_revision,
        candidate.generation_key_identity,
        resume,
        derivation.acceptance_identity,
    )
    updated_derivation = replace(derivation, provenance_identity=provenance.identity)
    values = {
        item.name: getattr(legacy, item.name)
        for item in fields(AcceptedSourceCacheEntry)
    }
    values.update(
        derivation=updated_derivation,
        provenance_evidence=provenance_evidence,
        standard_source_membership=membership,
    )
    return StandardAcceptedSourceCacheEntry(**values)


class StandardSourceCacheRoundTripTests(unittest.TestCase):
    def test_twelve_published_keys_round_trip_through_portable_archive(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            try:
                project = root / ("project with spaces " + ("long-" * 20))
                staging = root / "staging"
                project.mkdir()
                staging.mkdir()
                caller_cas = FileSystemCAS(root / "caller-cas")
                cache_root = project / "generated" / "accepted-source-cache"
                coordinator = FileSystemSourceCache("runtime", cache_root)
                entries = tuple(
                    _accepted_entry(
                        caller_cas,
                        suffix=f"node-{index}",
                        key=_cache_key(selector=f"model-node-{index}"),
                    )
                    for index in range(12)
                )
                for entry in entries:
                    coordinator.publish(entry, caller_cas=caller_cas)

                with patch.dict(os.environ, {"BUILD_DIR": str(project / "generated")}):
                    reference = capture_accepted_source_cache_archive(
                        project, directory=staging
                    )
                self.assertIsNotNone(reference)
                archive = staging / "accepted-source-cache.tar.gz"
                with tarfile.open(archive, "r:gz") as stream:
                    names = tuple(item.name for item in stream.getmembers())
                self.assertTrue(names)
                self.assertFalse(any("\\" in name for name in names))

                restored_root = root / "short build root" / "accepted-source-cache"
                restored_root.parent.mkdir()
                extract_accepted_source_cache_archive(archive, restored_root)
                restored = FileSystemSourceCache("runtime", restored_root)
                long_lookup = (
                    cache_root
                    / "keys"
                    / "sha256"
                    / entries[0].derivation.cache_key.identity.digest
                    / f"{entries[0].identity.digest}.json"
                )
                self.assertGreater(len(str(long_lookup)), 260)
                original_read_bytes = Path.read_bytes

                def reject_checkout_cache_lookup(path: Path) -> bytes:
                    if (
                        Path(_native_filesystem_path(path.absolute()))
                        .resolve()
                        .is_relative_to(
                            Path(_native_filesystem_path(cache_root)).resolve()
                        )
                    ):
                        raise AssertionError(
                            "restored lookup touched the long request-checkout cache"
                        )
                    return original_read_bytes(path)

                with patch.object(Path, "read_bytes", reject_checkout_cache_lookup):
                    candidates = tuple(
                        candidate
                        for entry in entries
                        for candidate in restored.candidates(entry.derivation.cache_key)
                    )
                self.assertEqual(
                    len(candidates),
                    12,
                )
                self.assertEqual(
                    len(tuple((restored_root / "keys" / "sha256").glob("*/*.json"))),
                    12,
                )
                self.assertEqual(
                    {candidate.identity for candidate in candidates},
                    {entry.identity for entry in entries},
                )
            finally:
                shutil.rmtree(Path(_native_filesystem_path(root)))

    def test_complete_publication_binds_every_durable_cache_input(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            cas = FileSystemCAS(root / "cas")
            entry = _standard_entry(cas)
            membership = restore_standard_source_cache_membership(entry)
            assert membership is not None
            output = membership.generation.output
            component = membership.component_revision
            export = _export(component, output.candidate.tree_identity)
            build = StandardBuildEvidence(
                component,
                _identity("publication-build-plan"),
                output.candidate.tree_identity,
                _identity("publication-source-custody"),
                entry.derivation.source_sbom_binding,
                entry.derivation.resolved_sbom_binding,
                (export,),
                (export.identity,),
                _identity("publication-build-observation"),
                _identity("publication-artifact-custody"),
            )
            case = StandardGeneratedTestCaseEvidence(
                "publication-case",
                _identity("publication-case-identity"),
                _identity("publication-case-observation"),
            )
            generated_tests = StandardGeneratedTestExecutionEvidence(
                component,
                output.candidate.generated_test_suite_identity,
                build.identity,
                build.export_identities,
                _identity("publication-test-runner"),
                _identity("publication-test-custody"),
                (case.case_identity,),
                (case,),
                1,
                1,
                1,
            )
            execution = StandardExecutionEvidence(
                component,
                build.identity,
                build.export_identities,
                export.identity,
                _identity("publication-execution-contract"),
                _identity("publication-runtime"),
                build.artifact_custody_identity,
                _identity("publication-execution-observation"),
                _identity("publication-stdout"),
                _identity("publication-stderr"),
                0,
            )
            acceptance = StandardComponentAcceptanceEvidence(
                component,
                output.identity,
                generated_tests.generated_test_suite_identity,
                build,
                generated_tests,
                execution,
                _identity("publication-acceptance-policy"),
            )
            membership = replace(membership, acceptance_identity=acceptance.identity)

            publication = StandardAcceptedSourcePublication(
                component,
                build.build_plan_identity,
                output,
                (export,),
                _identity("publication-index"),
                export.authorization_identity,
                membership,
                build,
                generated_tests,
                execution,
                acceptance,
            )

            self.assertEqual(publication.membership, membership)
            self.assertEqual(publication.acceptance_evidence, acceptance)
            with self.assertRaisesRegex(
                StandardProjectLifecycleError, "complete accepted node"
            ):
                replace(
                    publication,
                    index_identity=_identity("changed-index"),
                    exports=(),
                )
            with self.assertRaisesRegex(
                StandardProjectLifecycleError, "complete accepted node"
            ):
                replace(
                    publication,
                    build_plan_identity=_identity("substituted-build-plan"),
                )

            source_root = root / "accepted-source"
            for source_file in entry.source_files:
                destination = source_root.joinpath(*Path(source_file.path).parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(cas.path_for(source_file.blob).read_bytes())
            cache = FileSystemSourceCache("standard", root / "cache")
            publisher = FilesystemStandardAcceptedSourcePublisher(
                cache=cache,
                caller_cas=cas,
                source_root=lambda _identity: source_root,
                source_custody=lambda _identity: SimpleNamespace(
                    managed_graph=entry.managed_sbom_graph,
                    source_bom_content=cas.path_for(entry.source_sbom).read_bytes(),
                    generated_test_suite_content=cas.path_for(
                        entry.generated_test_suite
                    ).read_bytes(),
                ),
                resolved_sbom_content=lambda _publication: cas.path_for(
                    entry.resolved_sbom
                ).read_bytes(),
                cache_key=lambda _publication: entry.derivation.cache_key,
            )

            # Exercise real entry construction, CAS copying and filesystem
            # membership links under an additive captured owner. This does not
            # qualify provider/SDK execution; only the publication cut is tested.
            from literate_ai.adapters.cache import filesystem as cache_filesystem

            for boundary in ("entry", "copy", "prelink", "postlink"):
                with self.subTest(owner_loss=boundary):
                    guarded_cache = FileSystemSourceCache(boundary, root / boundary)
                    guarded_publisher = copy(publisher)
                    guarded_publisher.cache = guarded_cache
                    guarded_publisher._published_entry_by_membership = {}
                    state = {"alive": True, "membership": False}

                    def owner(state=state):
                        if not state["alive"]:
                            raise ValueError("publication owner ended")

                    original_write = guarded_cache._publish_immutable_bytes

                    def write(
                        destination,
                        content,
                        *,
                        state=state,
                        guarded_cache=guarded_cache,
                        original_write=original_write,
                        **kwargs,
                    ):
                        state["membership"] = (
                            destination.parent.parent == guarded_cache.keys
                        )
                        try:
                            return original_write(destination, content, **kwargs)
                        finally:
                            state["membership"] = False

                    with ExitStack() as stack:
                        stack.enter_context(
                            patch(
                                "literate_ai.application.standard_node_sdk_admission.capture_node_sdk_lifecycle",
                                return_value=owner,
                            )
                        )
                        if boundary == "entry":

                            def key(_publication, state=state):
                                state["alive"] = False
                                return entry.derivation.cache_key

                            guarded_publisher.cache_key = key
                        elif boundary == "copy":
                            original_copy = guarded_cache.cas.put_file

                            def copied(
                                *args,
                                state=state,
                                original_copy=original_copy,
                                **kwargs,
                            ):
                                result = original_copy(*args, **kwargs)
                                state["alive"] = False
                                return result

                            stack.enter_context(
                                patch.object(
                                    guarded_cache.cas, "put_file", side_effect=copied
                                )
                            )
                        else:
                            stack.enter_context(
                                patch.object(
                                    guarded_cache,
                                    "_publish_immutable_bytes",
                                    side_effect=write,
                                )
                            )
                            if boundary == "prelink":
                                original_fsync = cache_filesystem.os.fsync

                                def fsync(
                                    descriptor,
                                    state=state,
                                    original_fsync=original_fsync,
                                ):
                                    original_fsync(descriptor)
                                    if state["membership"]:
                                        state["alive"] = False

                                stack.enter_context(
                                    patch.object(
                                        cache_filesystem.os, "fsync", side_effect=fsync
                                    )
                                )
                            else:
                                original_link = cache_filesystem.os.link

                                def link(
                                    *args,
                                    state=state,
                                    original_link=original_link,
                                    **kwargs,
                                ):
                                    original_link(*args, **kwargs)
                                    if state["membership"]:
                                        state["alive"] = False

                                stack.enter_context(
                                    patch.object(
                                        cache_filesystem.os, "link", side_effect=link
                                    )
                                )
                        with self.assertRaisesRegex(ValueError, "owner ended"):
                            guarded_publisher.publish_accepted(publication)
                    candidates = guarded_cache.candidates(entry.derivation.cache_key)
                    # Guarded SDK publication joins the existing cooperative
                    # transaction: loss before commit rolls back its own pointer,
                    # including a link already created by this invocation.
                    self.assertEqual(len(candidates), 0)
                    self.assertIsNone(
                        guarded_publisher.published_entry_identity(membership.identity)
                    )

            published = publisher.publish_accepted(publication)
            candidates = cache.candidates(entry.derivation.cache_key)

            self.assertEqual(published, membership.identity)
            self.assertEqual(len(candidates), 1)
            self.assertEqual(
                tuple(item.path for item in candidates[0].source_files),
                tuple(sorted(item.path for item in candidates[0].source_files)),
            )
            self.assertEqual(
                restore_standard_source_cache_membership(candidates[0]), membership
            )

            # Re-open the durable store to prove the read does not depend on the
            # publishing process or any of its in-memory evidence objects.
            reader_store = FileSystemSourceCache(
                "standard", root / "cache", writable=False
            )
            resolver = SourceCacheResolver(
                _configuration(
                    SourceCacheMode.READ_ONLY,
                    _target("standard"),
                ),
                {"standard": reader_store},
            )
            restorer = FilesystemStandardSourceRestorer(
                resolver=resolver,
                materializer=SourceCacheMaterializer(),
            )
            (root / "restored-source").mkdir()
            restored = restorer.restore(
                entry.derivation.cache_key,
                root / "restored-source",
                component_lock_identity=entry.derivation.component_lock_identity,
            )

            self.assertIsNotNone(restored)
            assert restored is not None
            self.assertEqual(restored.membership, membership)
            self.assertEqual(restored.entry_identity, candidates[0].identity)
            self.assertFalse(restored.current_acceptance_trusted)
            self.assertEqual(
                {
                    item.relative_to(restored.source_root).as_posix(): item.read_bytes()
                    for item in restored.source_root.rglob("*")
                    if item.is_file()
                },
                {
                    item.relative_to(source_root).as_posix(): item.read_bytes()
                    for item in source_root.rglob("*")
                    if item.is_file()
                },
            )
            bypass = restorer.restore(
                entry.derivation.cache_key,
                root / "forced-source",
                component_lock_identity=entry.derivation.component_lock_identity,
                force_regeneration=True,
            )
            self.assertIsNone(bypass)
            self.assertFalse((root / "forced-source").exists())


if __name__ == "__main__":
    unittest.main()
