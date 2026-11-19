"""Parsed DATA reuse only; original discovery and catalog validation stay live."""

import sys
import tempfile
import unittest
from contextvars import copy_context
from pathlib import Path, PurePosixPath
from threading import Barrier, Event, Lock, Thread
from types import MemberDescriptorType
from unittest import mock

from literate_ai.application import agent_skill_catalog as catalog


def manifest(name="alpha", dependencies=(), body="# Owned DATA.\n"):
    header = f"---\nname: {name}\n"
    if dependencies:
        header += "dependencies:\n" + "".join(f"  - {item}\n" for item in dependencies)
    return (header + "---\n" + body).encode()


class SkillManifestMetadataScopeTests(unittest.TestCase):
    def setUp(self):
        self.source = PurePosixPath("skills/alpha/SKILL.md")
        self.original = catalog._parse_manifest_metadata

    def parse(self, content, source=None):
        return catalog._manifest_metadata(content, source or self.source)

    def test_default_is_uncached_and_scoped_results_have_no_mutable_aliases(self):
        content = manifest(dependencies=("base",))
        with mock.patch.object(
            catalog, "_parse_manifest_metadata", wraps=self.original
        ) as parse:
            self.parse(content)
            self.parse(content)
            self.assertEqual(parse.call_count, 2)
            with catalog.read_only_skill_manifest_metadata():
                first = self.parse(content)
                object.__setattr__(first[2][0], "skill_id", "tampered")
                second = self.parse(content)
                self.assertEqual(second[2][0].skill_id, "base")
                object.__setattr__(second[2][0], "skill_id", "tampered-again")
                self.assertEqual(self.parse(content)[2][0].skill_id, "base")
                self.assertEqual(parse.call_count, 3)
            self.assertIsNone(catalog._SCOPED_SKILL_METADATA.get())
            self.parse(content)
            self.assertEqual(parse.call_count, 4)

    def test_exact_bytes_and_detached_logical_path_are_both_required(self):
        content = manifest()
        with mock.patch.object(
            catalog, "_parse_manifest_metadata", wraps=self.original
        ) as parse:
            with catalog.read_only_skill_manifest_metadata():
                self.parse(content)
                self.parse(content + b"\n")
                self.parse(content, PurePosixPath("other/SKILL.md"))
                self.assertEqual(parse.call_count, 3)
                self.assertEqual(
                    self.parse(b'{"name":"legacy"}', PurePosixPath("skill.json"))[0],
                    "legacy",
                )
                with self.assertRaises(catalog.AgentSkillCatalogError):
                    self.parse(b'{"name":"legacy"}', PurePosixPath("SKILL.md"))

    def test_nonstandard_inputs_keep_the_original_parser(self):
        class ByteSubclass(bytes):
            pass

        class PathSubclass(PurePosixPath):
            pass

        content = manifest()
        with mock.patch.object(
            catalog, "_parse_manifest_metadata", wraps=self.original
        ) as parse:
            with catalog.read_only_skill_manifest_metadata():
                for raw, path in (
                    (ByteSubclass(content), self.source),
                    (content, PathSubclass(str(self.source))),
                ):
                    self.parse(raw, path)
                    self.parse(raw, path)
            self.assertEqual(parse.call_count, 4)

    def test_eligible_parser_owns_a_detached_path_before_caller_mutation(self):
        source = PurePosixPath("skills/alpha/SKILL.md")
        content = b'{"name":"legacy"}'

        def replace_path(value):
            replacement = PurePosixPath(value)
            for owner in type(source).__mro__:
                for slot in getattr(owner, "__slots__", ()):
                    if not isinstance(
                        getattr(type(source), slot, None), MemberDescriptorType
                    ):
                        continue
                    if hasattr(replacement, slot):
                        object.__setattr__(source, slot, getattr(replacement, slot))
                    elif hasattr(source, slot):
                        object.__delattr__(source, slot)

        def mutate_caller(raw, path):
            replace_path("skills/alpha/skill.json")
            try:
                self.assertEqual(source.name, "skill.json")
                return self.original(raw, path)
            finally:
                replace_path("skills/alpha/SKILL.md")

        with mock.patch.object(catalog, "_parse_manifest_metadata", mutate_caller):
            with catalog.read_only_skill_manifest_metadata():
                for _ in range(2):
                    with self.assertRaises(catalog.AgentSkillCatalogError):
                        self.parse(content, source)

    def test_malformed_manifests_preserve_errors_and_are_never_cached(self):
        cases = [
            (b"not frontmatter", self.source),
            (b"\xff", self.source),
            (b"{", PurePosixPath("skill.json")),
            (b"---\nname: alpha\nversion: 123\n---\n", self.source),
            (b"---\nname: alpha\ndependencies: invalid\n---\n", self.source),
        ]
        for content, path in cases:
            with self.subTest(path=path):
                with self.assertRaises(catalog.AgentSkillCatalogError) as baseline:
                    self.original(content, path)
                with mock.patch.object(
                    catalog, "_parse_manifest_metadata", wraps=self.original
                ) as parse:
                    with catalog.read_only_skill_manifest_metadata():
                        for _ in range(2):
                            with self.assertRaises(
                                catalog.AgentSkillCatalogError
                            ) as caught:
                                self.parse(content, path)
                            self.assertEqual(
                                (
                                    type(caught.exception),
                                    caught.exception.code,
                                    caught.exception.message,
                                    caught.exception.catalog_paths,
                                ),
                                (
                                    type(baseline.exception),
                                    baseline.exception.code,
                                    baseline.exception.message,
                                    baseline.exception.catalog_paths,
                                ),
                            )
                    self.assertEqual(parse.call_count, 2)

    def test_entry_limits_are_owned_at_entry_and_overflow_reparses(self):
        with (
            mock.patch.object(catalog, "_SKILL_METADATA_ENTRY_LIMIT", 1),
            mock.patch.object(
                catalog, "_parse_manifest_metadata", wraps=self.original
            ) as parse,
        ):
            with catalog.read_only_skill_manifest_metadata():
                self.parse(manifest("first"))
                with mock.patch.object(catalog, "_SKILL_METADATA_ENTRY_LIMIT", 100):
                    self.parse(manifest("second"))
                    self.parse(manifest("second"))
                self.parse(manifest("first"))
            self.assertEqual(parse.call_count, 3)

    def test_aggregate_byte_and_dependency_caps_skip_retention_without_refusal(self):
        for limits, first, second in (
            (
                {"_SKILL_METADATA_BYTE_LIMIT": 300},
                manifest("first", body="x" * 128),
                manifest("second", body="y" * 128),
            ),
            (
                {"_SKILL_METADATA_DEPENDENCY_LIMIT": 2},
                manifest("first", ("a", "b")),
                manifest("second", ("c",)),
            ),
        ):
            with (
                self.subTest(limits=limits),
                mock.patch.multiple(catalog, **limits),
                mock.patch.object(
                    catalog, "_parse_manifest_metadata", wraps=self.original
                ) as parse,
            ):
                with catalog.read_only_skill_manifest_metadata():
                    self.parse(first)
                    self.parse(second)
                    self.parse(second)
                    self.parse(first)
                self.assertEqual(parse.call_count, 3)

    def test_per_entry_and_unencodable_payloads_use_original_results(self):
        cases = [
            (
                manifest(dependencies=("a", "b")),
                {"_SKILL_METADATA_PER_ENTRY_DEPENDENCIES": 1},
            ),
            (b'{"name":"\\ud800"}', {}),
        ]
        for content, limits in cases:
            path = (
                PurePosixPath("skill.json") if content.startswith(b"{") else self.source
            )
            with (
                self.subTest(limits=limits),
                mock.patch.multiple(
                    catalog, **(limits or {"_SKILL_METADATA_ENTRY_LIMIT": 128})
                ),
                mock.patch.object(
                    catalog, "_parse_manifest_metadata", wraps=self.original
                ) as parse,
            ):
                expected = self.original(content, path)
                with catalog.read_only_skill_manifest_metadata():
                    self.assertEqual(self.parse(content, path), expected)
                    self.assertEqual(self.parse(content, path), expected)
                self.assertEqual(parse.call_count, 2)

    def test_nested_and_copied_contexts_retire_without_losing_outer_cache(self):
        content = manifest()
        with mock.patch.object(
            catalog, "_parse_manifest_metadata", wraps=self.original
        ) as parse:
            with catalog.read_only_skill_manifest_metadata():
                self.parse(content)
                outer = copy_context()
                with catalog.read_only_skill_manifest_metadata():
                    self.parse(content)
                    inner = copy_context()
                inner.run(self.parse, content)
                self.parse(content)
                self.assertEqual(parse.call_count, 3)
            outer.run(self.parse, content)
            outer.run(self.parse, content)
            self.assertEqual(parse.call_count, 5)

    def test_cancellation_identity_and_original_context_are_preserved(self):
        original_context = catalog._SCOPED_SKILL_METADATA.get()
        error = KeyboardInterrupt()
        with self.assertRaises(KeyboardInterrupt) as caught:
            with catalog.read_only_skill_manifest_metadata():
                self.parse(manifest())
                raise error
        self.assertIs(caught.exception, error)
        self.assertIs(catalog._SCOPED_SKILL_METADATA.get(), original_context)

    @unittest.skipUnless(hasattr(sys, "getrefcount"), "CPython retained-byte ownership")
    def test_inflight_copied_context_cannot_retain_bytes_after_retirement(self):
        content = manifest("threaded")
        entered, release = Event(), Event()
        results, errors = [], []
        calls = 0

        def delayed(raw, path):
            nonlocal calls
            calls += 1
            result = self.original(raw, path)
            entered.set()
            if not release.wait(2):
                raise RuntimeError("owned parser fixture release expired")
            return result

        def worker():
            try:
                results.append(context.run(self.parse, content))
            except BaseException as error:
                errors.append(error)

        references = sys.getrefcount(content)
        thread = Thread(target=worker)
        with mock.patch.object(catalog, "_parse_manifest_metadata", delayed):
            try:
                with catalog.read_only_skill_manifest_metadata():
                    context = copy_context()
                    thread.start()
                    self.assertTrue(entered.wait(2))
                still_parsing = thread.is_alive()
            finally:
                release.set()
                if thread.ident is not None:
                    thread.join(3)
            self.assertTrue(still_parsing)
            self.assertFalse(thread.is_alive())
            self.assertEqual(errors, [])
            self.assertEqual(len(results), 1)
            context.run(self.parse, content)
            self.assertEqual(calls, 2)
            self.assertEqual(sys.getrefcount(content), references)

    def test_concurrent_admissions_respect_the_same_entry_cap(self):
        barrier, counter_lock = Barrier(4), Lock()
        calls, errors = 0, []
        documents = [manifest(f"skill-{number}") for number in range(4)]

        def counted(raw, path):
            nonlocal calls
            with counter_lock:
                calls += 1
                ordinal = calls
            result = self.original(raw, path)
            if ordinal <= 4:
                barrier.wait(2)
            return result

        def worker(context, content):
            try:
                context.run(self.parse, content)
            except BaseException as error:
                errors.append(error)

        with (
            mock.patch.object(catalog, "_SKILL_METADATA_ENTRY_LIMIT", 1),
            mock.patch.object(catalog, "_parse_manifest_metadata", counted),
        ):
            with catalog.read_only_skill_manifest_metadata():
                threads = [
                    Thread(target=worker, args=(copy_context(), content))
                    for content in documents
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(3)
                    self.assertFalse(thread.is_alive())
                self.assertEqual(errors, [])
                for content in documents:
                    self.parse(content)
                self.assertEqual(calls, 7)

    def test_catalog_revalidates_dependencies_and_references_after_metadata_hits(self):
        dependent = manifest("dependent", ("base",), "Follow `skills/base/SKILL.md`.\n")
        documents = {
            "skills/base/SKILL.md": manifest("base"),
            "skills/dependent/SKILL.md": dependent,
        }
        with catalog.read_only_skill_manifest_metadata():
            catalog.AgentSkillCatalog.from_documents(
                documents, validate_references=True
            )
            for validate_dependencies in (True, False):
                with self.assertRaises(catalog.AgentSkillCatalogError):
                    catalog.AgentSkillCatalog.from_documents(
                        {"skills/dependent/SKILL.md": dependent},
                        validate_dependencies=validate_dependencies,
                        validate_references=True,
                    )

    def test_fresh_filesystem_discovery_membership_and_symlinks_cannot_use_old_data(
        self,
    ):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            directory = root / "skills" / "alpha"
            directory.mkdir(parents=True)
            path = directory / "SKILL.md"
            path.write_bytes(manifest())

            def discover():
                return catalog.AgentSkillCatalog.discover(
                    root, catalog_roots=(root / "skills",)
                )

            with catalog.read_only_skill_manifest_metadata():
                first = discover()
                path.write_bytes(manifest("changed"))
                second = discover()
                self.assertNotEqual(first.skills[0].identity, second.skills[0].identity)
                self.assertEqual(second.skills[0].name, "changed")
                duplicate = root / "skills" / "duplicate"
                duplicate.mkdir()
                (duplicate / "SKILL.md").write_bytes(manifest("changed"))
                with self.assertRaises(catalog.AgentSkillCatalogError):
                    discover()
                (duplicate / "SKILL.md").unlink()
                path.unlink()
                target = root / "owned-source.md"
                target.write_bytes(manifest("changed"))
                path.symlink_to(target)
                with self.assertRaises(catalog.AgentSkillCatalogError):
                    discover()


if __name__ == "__main__":
    unittest.main()
