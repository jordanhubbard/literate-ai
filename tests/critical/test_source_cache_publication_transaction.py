"""Draft transaction source controls; no native qualification is represented.

POSIX controls use actual local advisory locks and cooperating Python processes.
The Windows CRT control models its protocol only, without claiming native proof.
"""

import errno
import multiprocessing
import os
import stat
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from literate_ai.adapters.cache import _publication as publication
from literate_ai.adapters.cache import filesystem as cache_module
from literate_ai.adapters.cache.standard import (
    FilesystemStandardAcceptedSourcePublisher,
    FilesystemStandardSourceAdmissionPublisher,
)
from literate_ai.application import native_root_run as lifetime
from literate_ai.application import standard_node_sdk_admission as sdk_lifetime
from literate_ai.contracts.native_root_continuation import NativeRootRunPolicy
from literate_ai.storage import FileSystemCAS
from tests.support import fixtures_test_source_cache as fixture
from tests.support import (
    fixtures_test_standard_source_cache_roundtrip as admission_fixture,
)


def _competing_writer(marker, destination, attempted, completed):
    path = Path(destination)
    temporary = path.with_name("peer-temporary")
    temporary.write_bytes(b"same immutable bytes")
    attempted.set()
    with publication.cache_publication_transaction(Path(marker)) as transaction:
        transaction.link(temporary, path)
        path.with_name("peer-membership").write_bytes(b"accepted")
    temporary.unlink()
    completed.set()


def _competing_cache_writer(root, caller, entry, attempted, completed):
    store = cache_module.FileSystemSourceCache("peer", Path(root))
    source = FileSystemCAS(Path(caller), create=False)
    attempted.set()
    store.publish(entry, caller_cas=source)
    completed.set()


@unittest.skipUnless(os.name == "posix", "actual local POSIX locking controls")
class SourceCachePublicationTransactionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.marker = self.root / "format.json"
        self.marker.write_bytes(b'{"format":"immutable-test-coordinate"}')
        self.temporary = self.root / "temporary"
        self.temporary.write_bytes(b"same immutable bytes")
        self.destination = self.root / "manifest"
        self.current = True

    def guard(self):
        if not self.current:
            raise RuntimeError("original lifetime closed")

    def transaction(self, **kwargs):
        return publication.cache_publication_transaction(
            self.marker,
            require_current=self.guard,
            remaining=lambda: 5.0,
            **kwargs,
        )

    def test_read_only_coordinate_has_no_content_or_metadata_writes(self):
        self.marker.chmod(0o400)
        before = self.marker.stat()
        content = self.marker.read_bytes()
        with publication.cache_publication_transaction(self.marker):
            self.assertEqual(self.marker.read_bytes(), content)
        after = self.marker.stat()
        self.assertEqual(
            (before.st_dev, before.st_ino, before.st_mode, before.st_mtime_ns),
            (after.st_dev, after.st_ino, after.st_mode, after.st_mtime_ns),
        )
        self.assertEqual(
            sorted(p.name for p in self.root.iterdir()), ["format.json", "temporary"]
        )

    def test_missing_coordinate_is_never_created(self):
        absent = self.root / "missing-format"
        with self.assertRaises(FileNotFoundError):
            with publication.cache_publication_transaction(absent):
                self.fail("missing marker acquired")
        self.assertFalse(absent.exists())

    def test_contended_lock_reports_original_owner_refusal(self):
        original = RuntimeError("original owner expired while waiting")
        attempts = []

        def busy(_descriptor):
            attempts.append(True)
            raise BlockingIOError(errno.EAGAIN, "owned contention")

        def guard():
            if attempts:
                raise original

        with (
            mock.patch.object(publication, "_try_lock", side_effect=busy),
            mock.patch.object(publication.time, "sleep"),
        ):
            with self.assertRaises(RuntimeError) as caught:
                with publication.cache_publication_transaction(
                    self.marker, require_current=guard, remaining=lambda: 1.0
                ):
                    self.fail("expired owner acquired target")
        self.assertIs(caught.exception, original)

    def test_replaced_parent_does_not_authorize_cleaning_replacement(self):
        directory = self.root / "entries"
        directory.mkdir()
        destination = directory / "entry"
        original = RuntimeError("original publication failure")
        with self.assertRaises(RuntimeError) as caught:
            with self.transaction() as transaction:
                transaction.link(self.temporary, destination)
                directory.rename(self.root / "original-entries")
                directory.mkdir()
                os.link(self.temporary, destination)
                raise original
        self.assertIs(caught.exception, original)
        self.assertTrue(destination.exists())
        self.assertTrue(self.root.joinpath("original-entries", "entry").exists())
        self.assertTrue(any("parent changed" in note for note in original.__notes__))

    def test_guarded_expiry_undoes_only_owned_link(self):
        with self.assertRaisesRegex(RuntimeError, "original lifetime closed"):
            with self.transaction() as transaction:
                self.assertTrue(transaction.link(self.temporary, self.destination))
                self.current = False
        self.assertFalse(self.destination.exists())
        self.assertTrue(self.temporary.exists())

    def test_borrowed_exact_link_survives_refused_attempt(self):
        os.link(self.temporary, self.destination)
        before = self.destination.stat()
        with self.assertRaisesRegex(RuntimeError, "original lifetime closed"):
            with self.transaction() as transaction:
                self.assertFalse(transaction.link(self.temporary, self.destination))
                self.current = False
        after = self.destination.stat()
        self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))

    def test_foreign_replacement_is_retained_and_noted_on_original_error(self):
        original = RuntimeError("original publication failure")
        with self.assertRaises(RuntimeError) as caught:
            with self.transaction() as transaction:
                transaction.link(self.temporary, self.destination)
                self.destination.unlink()
                self.destination.write_bytes(b"foreign replacement")
                raise original
        self.assertIs(caught.exception, original)
        self.assertEqual(self.destination.read_bytes(), b"foreign replacement")
        self.assertTrue(
            any("replacement retained" in note for note in original.__notes__)
        )

    def test_no_owner_preserves_legacy_partial_publication(self):
        original = RuntimeError("legacy partial failure")
        with self.assertRaises(RuntimeError) as caught:
            with publication.cache_publication_transaction(self.marker) as transaction:
                transaction.link(self.temporary, self.destination)
                raise original
        self.assertIs(caught.exception, original)
        self.assertEqual(self.destination.read_bytes(), b"same immutable bytes")

    def test_cleanup_annotation_does_not_dispatch_original_exception_override(self):
        class Original(RuntimeError):
            def add_note(self, note):
                raise AssertionError("overridden note must not run")

        original = Original("original publication failure")
        with self.assertRaises(Original) as caught:
            with self.transaction() as transaction:
                transaction.link(self.temporary, self.destination)
                self.destination.unlink()
                self.destination.write_bytes(b"foreign replacement")
                raise original
        self.assertIs(caught.exception, original)
        self.assertTrue(original.__notes__)

    def test_descriptor_cleanup_attempts_every_retained_handle(self):
        original_close = publication._HeldPath.close
        calls = []
        failure = RuntimeError("first descriptor cleanup failed")

        def close(held):
            original_close(held)
            calls.append(held)
            if len(calls) == 1:
                raise failure

        with self.assertRaises(RuntimeError) as caught:
            with mock.patch.object(publication._HeldPath, "close", close):
                with self.transaction() as transaction:
                    transaction.link(self.temporary, self.destination)
                    transaction.link(self.temporary, self.root / "second-manifest")
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(calls), 4)
        # Cleanup begins after the final live-owner check committed these links.
        self.assertEqual(self.destination.read_bytes(), b"same immutable bytes")
        self.assertEqual(
            (self.root / "second-manifest").read_bytes(), b"same immutable bytes"
        )

    def test_post_commit_unlock_failure_does_not_delete_committed_links(self):
        unlock = publication._unlock
        failure = RuntimeError("post-commit unlock cleanup failed")

        def release(descriptor):
            unlock(descriptor)
            raise failure

        with self.assertRaises(RuntimeError) as caught:
            with mock.patch.object(publication, "_unlock", side_effect=release):
                with self.transaction() as transaction:
                    transaction.link(self.temporary, self.destination)
        self.assertIs(caught.exception, failure)
        self.assertEqual(self.destination.read_bytes(), b"same immutable bytes")

    def test_borrowed_link_cleanup_attempts_both_unretained_handles(self):
        os.link(self.temporary, self.destination)
        original_close = publication._HeldPath.close
        failure = RuntimeError("first unretained close failed")
        calls = []

        def close(held):
            original_close(held)
            calls.append(held)
            if len(calls) == 1:
                raise failure

        with self.assertRaises(RuntimeError) as caught:
            with self.transaction() as transaction:
                with mock.patch.object(publication._HeldPath, "close", close):
                    transaction.link(self.temporary, self.destination)
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(calls), 2)
        self.assertEqual(self.destination.read_bytes(), b"same immutable bytes")

    def test_link_guard_refusal_survives_both_unretained_handle_closes(self):
        original_close = publication._HeldPath.close
        original = RuntimeError("original guard refusal")
        calls, guards = [], []

        def close(held):
            original_close(held)
            calls.append(held)
            if len(calls) == 1:
                raise RuntimeError("unretained close failed")

        def guard():
            guards.append(True)
            if len(guards) == 2:
                raise original

        with self.assertRaises(RuntimeError) as caught:
            with self.transaction() as transaction:
                transaction._require_current = guard
                with mock.patch.object(publication._HeldPath, "close", close):
                    transaction.link(self.temporary, self.destination)
        self.assertIs(caught.exception, original)
        self.assertEqual(len(calls), 2)
        self.assertTrue(
            any("unretained custody" in note for note in original.__notes__)
        )
        self.assertFalse(self.destination.exists())

    def test_retirement_refusal_survives_all_pre_retention_handle_closes(self):
        os.link(self.temporary, self.destination)
        original_close = publication._HeldPath.close
        original = RuntimeError("original undo allocation refusal")
        calls = []

        def close(held):
            original_close(held)
            calls.append(held)
            if len(calls) == 1:
                raise RuntimeError("unretained close failed")

        with self.assertRaises(RuntimeError) as caught:
            with self.transaction() as transaction:
                with (
                    mock.patch.object(publication._HeldPath, "close", close),
                    mock.patch.object(
                        publication.tempfile, "mkdtemp", side_effect=original
                    ),
                ):
                    transaction.remove(self.destination, staging=self.root)
        self.assertIs(caught.exception, original)
        self.assertEqual(len(calls), 2)
        self.assertTrue(
            any("unretained custody" in note for note in original.__notes__)
        )
        self.assertEqual(self.destination.read_bytes(), b"same immutable bytes")

    def test_recursive_public_entry_via_another_path_refuses_without_waiting(self):
        alias = self.root / "format-hardlink"
        os.link(self.marker, alias)
        with self.transaction():
            with self.assertRaisesRegex(
                publication.CachePublicationLockError, "recursive public"
            ):
                with publication.cache_publication_transaction(alias):
                    self.fail("recursive entry acquired")

    def test_closed_owner_refuses_before_visibility_link(self):
        with self.assertRaisesRegex(RuntimeError, "original lifetime closed"):
            with self.transaction() as transaction:
                self.current = False
                transaction.link(self.temporary, self.destination)
        self.assertFalse(self.destination.exists())

    def test_competing_writer_cannot_borrow_uncommitted_manifest(self):
        context = multiprocessing.get_context("spawn")
        attempted, completed = context.Event(), context.Event()
        peer = context.Process(
            target=_competing_writer,
            args=(str(self.marker), str(self.destination), attempted, completed),
        )
        # Releasing the parent lock on every path lets the bounded peer finish.
        try:
            with self.assertRaisesRegex(RuntimeError, "original lifetime closed"):
                with self.transaction() as transaction:
                    transaction.link(self.temporary, self.destination)
                    peer.start()
                    self.assertTrue(attempted.wait(5))
                    self.assertFalse(completed.wait(0.05))
                    self.current = False
            peer.join(5)
            self.assertFalse(peer.is_alive())
            self.assertEqual(peer.exitcode, 0)
            self.assertTrue(completed.is_set())
            self.assertEqual(self.destination.read_bytes(), b"same immutable bytes")
            self.assertEqual(
                self.root.joinpath("peer-membership").read_bytes(), b"accepted"
            )
        finally:
            if peer.pid is not None:
                peer.join(5)
                if peer.is_alive():
                    peer.terminate()
                    peer.join(5)


class SourceCacheWindowsLockProtocolTests(unittest.TestCase):
    def test_crt_readonly_marker_lock_uses_same_beyond_eof_byte_for_unlock(self):
        crt = SimpleNamespace(LK_NBLCK=2, LK_UNLCK=0, locking=mock.Mock())
        with (
            mock.patch.object(
                publication._cache_lock, "_is_windows", return_value=True
            ),
            mock.patch.object(publication.os, "lseek") as seek,
            mock.patch.dict("sys.modules", {"msvcrt": crt}),
        ):
            publication._try_lock(37)
            publication._unlock(37)
        self.assertEqual(
            seek.call_args_list,
            [mock.call(37, 4096, os.SEEK_SET), mock.call(37, 4096, os.SEEK_SET)],
        )
        self.assertEqual(
            crt.locking.call_args_list, [mock.call(37, 2, 1), mock.call(37, 0, 1)]
        )


@unittest.skipUnless(os.name == "posix", "actual local POSIX cache controls")
class SourceCacheCommitConstraintTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.caller = FileSystemCAS(self.root / "caller")
        self.entry, self.attachment = fixture._accepted_entry_with_attachment(
            self.caller
        )
        self.store = cache_module.FileSystemSourceCache("local", self.root / "cache")
        self.current = True
        self.refusal = RuntimeError("original run expired")

    def guard(self):
        if not self.current:
            raise self.refusal

    def owner(self, require_current=lambda: None):
        return lifetime.open_native_root_run(
            NativeRootRunPolicy(120, 3),
            project_identity=fixture._identity("project"),
            framework_distribution_identity=fixture._identity("framework"),
            lifecycle_policy_identity=fixture._identity("lifecycle"),
            require_current=require_current,
        )

    def test_entry_serialization_cannot_clear_and_close_original_run(self):
        entry = admission_fixture._source_admission_entry(self.caller)
        serialize = type(entry).to_dict
        tokens = []
        with self.owner() as owner, lifetime.activate_native_root_run(owner):

            def to_dict(value):
                document = serialize(value)
                if value is entry and not tokens:
                    tokens.append(lifetime._ACTIVE_NATIVE_ROOT_RUN.set(None))
                    owner.close()
                return document

            try:
                with mock.patch.object(type(entry), "to_dict", to_dict):
                    with self.assertRaises(lifetime.NativeRootRunError) as caught:
                        self.store.publish(entry, caller_cas=self.caller)
                self.assertEqual(caught.exception.code, "native_root_run.closed")
            finally:
                if tokens:
                    lifetime._ACTIVE_NATIVE_ROOT_RUN.reset(tokens[0])
        self.assertTrue(tokens)
        self.assertEqual(self.store.published_entries(), ())
        self.assertEqual(self.store.candidates(entry.cache_key), ())

    def test_explicit_constraints_cannot_replace_original_active_run(self):
        for cut in ("guard", "remaining"):
            with self.subTest(cut=cut):
                self._explicit_constraint_case(cut)

    def _explicit_constraint_case(self, cut):
        tokens = []
        with self.owner() as owner, lifetime.activate_native_root_run(owner):

            def close_original():
                if not tokens:
                    tokens.append(lifetime._ACTIVE_NATIVE_ROOT_RUN.set(None))
                    owner.close()

            def current():
                if cut == "guard":
                    close_original()

            def remaining():
                if cut == "remaining":
                    close_original()
                return 30

            try:
                with self.assertRaises(lifetime.NativeRootRunError) as caught:
                    self.store.publish(
                        self.entry,
                        caller_cas=self.caller,
                        require_current=current,
                        remaining=remaining,
                    )
                self.assertEqual(caught.exception.code, "native_root_run.closed")
            finally:
                if tokens:
                    lifetime._ACTIVE_NATIVE_ROOT_RUN.reset(tokens[0])
        self.assertTrue(tokens)
        self.assertEqual(self.store.published_entries(), ())
        self.assertEqual(self.store.candidates(self.entry.derivation.cache_key), ())

    def test_original_native_and_sdk_owners_close_after_each_others_callbacks(self):
        for cut in ("native", "sdk", "final-native"):
            with self.subTest(cut=cut):
                self._original_owner_callback_case(cut)

    def _original_owner_callback_case(self, cut):
        armed, entered, sdk_checks = [], [], []
        invocation = SimpleNamespace(
            identity="invocation",
            prepared=SimpleNamespace(
                recipe=SimpleNamespace(identity="recipe"),
                request=SimpleNamespace(
                    request=SimpleNamespace(context_manifest_identity="manifest")
                ),
            ),
        )

        def native_callback():
            if armed and (
                cut == "native"
                or (cut == "final-native" and entered and len(sdk_checks) > entered[0])
            ):
                scope.active = False
                sdk_lifetime._CURRENT.set(None)

        def sdk_callback():
            sdk_checks.append(True)
            if armed and cut == "sdk":
                owner.close()
                lifetime._ACTIVE_NATIVE_ROOT_RUN.set(None)

        scope = sdk_lifetime._Scope(
            SimpleNamespace(identity="execution"),
            invocation,
            sdk_callback,
            lambda: None,
        )
        with (
            self.owner(native_callback) as owner,
            lifetime.activate_native_root_run(owner),
        ):
            token = sdk_lifetime._CURRENT.set(scope)
            armed.append(True)
            try:
                with self.assertRaises((ValueError, lifetime.NativeRootRunError)):
                    with self.store._operation(
                        require_current=lambda: None,
                        remaining=lambda: 30,
                    ):
                        entered.append(len(sdk_checks))
            finally:
                sdk_lifetime._CURRENT.reset(token)
        self.assertEqual(bool(entered), cut == "final-native")

    def test_attachment_iterator_cannot_drop_original_commit_constraint(self):
        tokens = []
        with self.owner() as owner, lifetime.activate_native_root_run(owner):

            def attachments():
                tokens.append(lifetime._ACTIVE_NATIVE_ROOT_RUN.set(None))
                owner.close()
                yield self.attachment

            try:
                with self.assertRaises(lifetime.NativeRootRunError):
                    self.store.publish(
                        self.entry,
                        caller_cas=self.caller,
                        intelligence_attachments=attachments(),
                    )
            finally:
                if tokens:
                    lifetime._ACTIVE_NATIVE_ROOT_RUN.reset(tokens[0])
        self.assertTrue(tokens)
        self.assert_unpublished()

    def test_retirement_validation_cannot_drop_original_commit_constraint(self):
        self.publish()
        replacement = fixture._accepted_entry(self.caller, suffix="replacement")
        self.store.publish(replacement, caller_cas=self.caller)
        actual_key = self.entry.derivation.cache_key
        tokens = []
        with self.owner() as owner, lifetime.activate_native_root_run(owner):

            class ChangingKey:
                @property
                def __class__(self):
                    if not tokens:
                        tokens.append(lifetime._ACTIVE_NATIVE_ROOT_RUN.set(None))
                        owner.close()
                    return type(actual_key)

                @property
                def accepted_source_lookup_identity(self):
                    return actual_key.accepted_source_lookup_identity

            try:
                with self.assertRaises(lifetime.NativeRootRunError):
                    self.store.retire_other_memberships(
                        ChangingKey(), keep=replacement.identity
                    )
            finally:
                if tokens:
                    lifetime._ACTIVE_NATIVE_ROOT_RUN.reset(tokens[0])
        self.assertTrue(tokens)
        self.assertEqual(
            {entry.identity for entry in self.store.verified_published_entries()},
            {self.entry.identity, replacement.identity},
        )

    def accepted_publisher(self):
        return FilesystemStandardAcceptedSourcePublisher(
            cache=self.store,
            caller_cas=self.caller,
            source_root=lambda identity: None,
            source_custody=lambda identity: None,
            resolved_sbom_content=lambda publication: b"",
            cache_key=lambda publication: self.entry.derivation.cache_key,
        )

    def test_failed_closing_guard_restores_only_own_prior_mapping(self):
        identity = fixture._identity("membership")
        absent = object()
        for prior in (absent, fixture._identity("prior-publication")):
            for foreign in (
                None,
                fixture._identity("foreign-publication"),
                fixture._content_identity(self.entry.identity.uri),
            ):
                with self.subTest(prior=prior, foreign=foreign):
                    publisher = self.accepted_publisher()
                    mapping = publisher._published_entry_by_membership
                    if prior is not absent:
                        mapping[identity] = prior
                    holders = []

                    def guard(mapping=mapping, foreign=foreign, holders=holders):
                        if mapping.get(identity) == self.entry.identity:
                            if foreign is not None:
                                mapping[identity] = foreign
                            holders[0].close()

                    with (
                        self.owner(guard) as owner,
                        lifetime.activate_native_root_run(owner),
                        mock.patch.object(
                            publisher,
                            "_build_entry",
                            return_value=(self.entry.derivation.cache_key, self.entry),
                        ),
                        mock.patch.object(self.store, "publish"),
                    ):
                        holders.append(owner)
                        with self.assertRaises(lifetime.NativeRootRunError):
                            publisher.publish_accepted(
                                SimpleNamespace(
                                    membership=SimpleNamespace(identity=identity)
                                )
                            )
                    expected = foreign if foreign is not None else prior
                    self.assertIs(mapping.get(identity, absent), expected)

    def test_publisher_reports_post_commit_cleanup_error_without_positive_mapping(self):
        publisher = self.accepted_publisher()
        membership = fixture._identity("membership")
        unlock = publication._unlock
        failure = RuntimeError("post-commit target unlock failure")

        def release(descriptor):
            unlock(descriptor)
            raise failure

        with (
            self.owner() as owner,
            lifetime.activate_native_root_run(owner),
            mock.patch.object(
                publisher,
                "_build_entry",
                return_value=(self.entry.derivation.cache_key, self.entry),
            ),
            mock.patch.object(publication, "_unlock", side_effect=release),
        ):
            with self.assertRaises(RuntimeError) as caught:
                publisher.publish_accepted(
                    SimpleNamespace(membership=SimpleNamespace(identity=membership))
                )
        self.assertIs(caught.exception, failure)
        self.assertIsNone(publisher.published_entry_identity(membership))
        self.assertEqual(self.store.verified_published_entries(), (self.entry,))

    def test_source_admission_build_callback_cannot_replace_original_owner(self):
        entry = admission_fixture._source_admission_entry(self.caller)
        source_root = self.root / "admission-source"
        for source in entry.source_files:
            path = source_root / source.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(self.caller.path_for(source.blob).read_bytes())
        tokens = []
        with self.owner() as owner, lifetime.activate_native_root_run(owner):

            def key(membership):
                tokens.append(lifetime._ACTIVE_NATIVE_ROOT_RUN.set(None))
                owner.close()
                return entry.cache_key

            publisher = FilesystemStandardSourceAdmissionPublisher(
                cache=self.store,
                caller_cas=self.caller,
                source_root=lambda identity: source_root,
                source_custody=lambda identity: SimpleNamespace(
                    source_bom_content=self.caller.path_for(
                        entry.source_bom
                    ).read_bytes(),
                    generated_test_suite_content=self.caller.path_for(
                        entry.generated_test_suite
                    ).read_bytes(),
                ),
                cache_key=key,
            )
            try:
                with mock.patch.object(self.store, "publish") as publish:
                    with self.assertRaises(lifetime.NativeRootRunError):
                        publisher.publish(entry.membership)
                    publish.assert_not_called()
            finally:
                if tokens:
                    lifetime._ACTIVE_NATIVE_ROOT_RUN.reset(tokens[0])
        self.assertTrue(tokens)
        self.assertEqual(self.store.published_entries(), ())

    def publish(self):
        return self.store.publish(
            self.entry,
            caller_cas=self.caller,
            intelligence_attachments=(self.attachment,),
            require_current=self.guard,
            remaining=lambda: 10.0,
        )

    def assert_unpublished(self):
        self.assertEqual(self.store.published_entries(), ())
        self.assertEqual(self.store.candidates(self.entry.derivation.cache_key), ())
        self.assertEqual(
            self.store.intelligence_attachments(self.attachment.source_tree_identity),
            (),
        )

    def test_expiry_during_actual_temporary_fsync_prevents_manifest_link(self):
        fsync = os.fsync
        reached = []

        def flush(descriptor):
            fsync(descriptor)
            metadata = os.fstat(descriptor)
            if stat.S_ISREG(metadata.st_mode) and any(
                path.stat().st_ino == metadata.st_ino
                for path in self.store.staging.glob(".publish-*")
            ):
                reached.append(True)
                self.current = False

        with mock.patch.object(cache_module.os, "fsync", side_effect=flush):
            with self.assertRaises(RuntimeError) as caught:
                self.publish()
        self.assertIs(caught.exception, self.refusal)
        self.assertTrue(reached)
        self.assert_unpublished()

    def test_expiry_after_actual_manifest_link_rolls_back_enumerable_manifest(self):
        link = os.link

        def create(source, destination, **kwargs):
            result = link(source, destination, **kwargs)
            if Path(destination).parent == self.store.entries:
                self.current = False
            return result

        with mock.patch.object(cache_module.os, "link", side_effect=create):
            with self.assertRaises(RuntimeError) as caught:
                self.publish()
        self.assertIs(caught.exception, self.refusal)
        self.assert_unpublished()

    def test_expiry_after_attachment_links_removes_every_owned_visibility_link(self):
        original = self.store._publish_membership

        def membership(entry):
            self.current = False
            return original(entry)

        with mock.patch.object(
            self.store, "_publish_membership", side_effect=membership
        ):
            with self.assertRaises(RuntimeError) as caught:
                self.publish()
        self.assertIs(caught.exception, self.refusal)
        self.assert_unpublished()

    def test_same_and_different_entry_writers_cannot_borrow_partial_publication(self):
        context = multiprocessing.get_context("spawn")
        for label in ("same", "different"):
            with self.subTest(entry=label):
                self.current = True
                self.store = cache_module.FileSystemSourceCache(
                    "local", self.root / f"cache-{label}"
                )
                entry = (
                    self.entry
                    if label == "same"
                    else fixture._accepted_entry(self.caller, suffix="different")
                )
                attempted, completed = context.Event(), context.Event()
                peer = context.Process(
                    target=_competing_cache_writer,
                    args=(
                        str(self.store.root),
                        str(self.caller.root),
                        entry,
                        attempted,
                        completed,
                    ),
                )
                original = self.store._publish_membership

                def membership(
                    candidate,
                    peer=peer,
                    attempted=attempted,
                    completed=completed,
                    original=original,
                ):
                    peer.start()
                    self.assertTrue(attempted.wait(5))
                    self.assertFalse(completed.wait(0.05))
                    self.current = False
                    return original(candidate)

                try:
                    with mock.patch.object(
                        self.store, "_publish_membership", side_effect=membership
                    ):
                        with self.assertRaises(RuntimeError) as caught:
                            self.publish()
                    self.assertIs(caught.exception, self.refusal)
                    peer.join(5)
                    self.assertFalse(peer.is_alive())
                    self.assertEqual(peer.exitcode, 0)
                    self.assertTrue(completed.is_set())
                    self.assertEqual(self.store.verified_published_entries(), (entry,))
                finally:
                    if peer.pid is not None:
                        peer.join(5)
                        if peer.is_alive():
                            peer.terminate()
                            peer.join(5)

    def test_ordinary_failure_preserves_legacy_manifest_without_membership(self):
        with mock.patch.object(
            self.store, "_publish_membership", side_effect=self.refusal
        ):
            with self.assertRaises(RuntimeError) as caught:
                self.store.publish(self.entry, caller_cas=self.caller)
        self.assertIs(caught.exception, self.refusal)
        self.assertEqual(self.store.published_entries(), (self.entry,))
        self.assertEqual(self.store.candidates(self.entry.derivation.cache_key), ())

    def test_existing_accepted_entry_is_not_owned_by_failed_republication(self):
        self.publish()
        manifest = self.store.entries / f"{self.entry.identity.digest}.json"
        before = manifest.stat()
        with mock.patch.object(
            self.store, "_publish_membership", side_effect=self.refusal
        ):
            with self.assertRaises(RuntimeError):
                self.publish()
        after = manifest.stat()
        self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
        self.assertEqual(self.store.verified_published_entries(), (self.entry,))

    def test_public_reader_reentry_from_commit_callback_refuses(self):
        peer = cache_module.FileSystemSourceCache(
            "peer", self.store.root, writable=False
        )
        reads = (
            peer.published_entries,
            peer.verified_published_entries,
            lambda: peer.candidates(self.entry.derivation.cache_key),
            lambda: peer.intelligence_attachments(self.attachment.source_tree_identity),
        )
        for read in reads:
            with self.subTest(read=read):

                def callback(read=read):
                    if self.store._current_transaction() is not None:
                        read()

                with self.assertRaisesRegex(
                    publication.CachePublicationLockError, "recursive public"
                ):
                    self.store.publish(
                        self.entry,
                        caller_cas=self.caller,
                        require_current=callback,
                        remaining=lambda: 10.0,
                    )
                self.assert_unpublished()

    def test_readonly_queries_do_not_mutate_marker_or_target_paths(self):
        self.publish()
        marker = self.store.root / "format.json"
        marker.chmod(0o400)
        before = marker.stat()
        paths = sorted(str(path) for path in self.store.root.rglob("*"))
        readonly = cache_module.FileSystemSourceCache(
            "readonly", self.store.root, writable=False
        )
        self.assertEqual(readonly.verified_published_entries(), (self.entry,))
        self.assertEqual(
            readonly.candidates(self.entry.derivation.cache_key), (self.entry,)
        )
        self.assertEqual(
            readonly.intelligence_attachments(self.attachment.source_tree_identity),
            (self.attachment,),
        )
        after = marker.stat()
        self.assertEqual(
            (before.st_ino, before.st_mode, before.st_mtime_ns),
            (after.st_ino, after.st_mode, after.st_mtime_ns),
        )
        self.assertEqual(
            paths, sorted(str(path) for path in self.store.root.rglob("*"))
        )

    def test_retirement_expiry_restores_pointer_before_removing_tombstone(self):
        self.publish()
        replacement = fixture._accepted_entry(self.caller, suffix="replacement")
        self.store.publish(replacement, caller_cas=self.caller)
        directory = (
            self.store.keys
            / self.entry.derivation.cache_key.accepted_source_lookup_identity.digest
        )
        membership = directory / f"{self.entry.identity.digest}.json"
        before = membership.stat()
        fsync = cache_module._fsync_directory

        def flush(path):
            fsync(path)
            if path == directory and not membership.exists():
                self.current = False

        with mock.patch.object(cache_module, "_fsync_directory", side_effect=flush):
            with self.assertRaises(RuntimeError) as caught:
                self.store.retire_other_memberships(
                    self.entry.derivation.cache_key,
                    keep=replacement.identity,
                    require_current=self.guard,
                    remaining=lambda: 10.0,
                )
        self.assertIs(caught.exception, self.refusal)
        after = membership.stat()
        self.assertEqual((before.st_dev, before.st_ino), (after.st_dev, after.st_ino))
        self.assertFalse((directory / ".retired" / membership.name).exists())
        self.assertEqual(
            {entry.identity for entry in self.store.verified_published_entries()},
            {self.entry.identity, replacement.identity},
        )
        self.assertEqual(tuple(self.store.staging.glob(".retire-*")), ())

    def test_retirement_foreign_pointer_retains_recovery_custody_and_tombstone(self):
        self.publish()
        replacement = fixture._accepted_entry(self.caller, suffix="replacement")
        self.store.publish(replacement, caller_cas=self.caller)
        directory = (
            self.store.keys
            / self.entry.derivation.cache_key.accepted_source_lookup_identity.digest
        )
        membership = directory / f"{self.entry.identity.digest}.json"
        original = membership.read_bytes()
        fsync = cache_module._fsync_directory

        def flush(path):
            fsync(path)
            if path == directory and not membership.exists():
                membership.write_bytes(b"foreign membership")
                self.current = False

        with mock.patch.object(cache_module, "_fsync_directory", side_effect=flush):
            with self.assertRaises(RuntimeError) as caught:
                self.store.retire_other_memberships(
                    self.entry.derivation.cache_key,
                    keep=replacement.identity,
                    require_current=self.guard,
                    remaining=lambda: 10.0,
                )
        self.assertIs(caught.exception, self.refusal)
        self.assertEqual(membership.read_bytes(), b"foreign membership")
        self.assertTrue((directory / ".retired" / membership.name).is_file())
        backups = tuple(self.store.staging.glob(".retire-*/membership"))
        self.assertEqual(len(backups), 1)
        self.assertEqual(backups[0].read_bytes(), original)
        self.assertTrue(
            any("rollback incomplete" in note for note in self.refusal.__notes__)
        )
