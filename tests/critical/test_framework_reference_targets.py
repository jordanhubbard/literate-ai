"""Finite native reference facts remain read-only and never become move inputs."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from literate_ai.adapters import project_layout_framework_ingress as ingress
from literate_ai.adapters import project_layout_framework_observation as native
from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters.project_layout_migration import (
    apply_legacy_layout_migration,
    plan_legacy_layout_migration,
)
from literate_ai.adapters.project_layout_planning import ProjectLayoutPlanError
from tests.critical import test_project_layout_mixed_component_channels as support


def foreign_code(function):
    names = function.__code__.co_freevars
    source = "def outer():\n"
    source += "".join(f"    {name} = None\n" for name in names)
    source += "    def foreign(*args, **kwargs):\n"
    source += "        _ = (" + ",".join(names) + (",)\n" if names else ")\n")
    source += "        raise AssertionError('foreign reference helper invoked')\n"
    source += "    return foreign\n"
    namespace = {}
    exec(source, namespace)
    return namespace["outer"]().__code__


class ReferenceTargetTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve(strict=True)
        self.relative = "litai/samples/peer/component.md"
        self.target = self.root / self.relative
        self.target.parent.mkdir(parents=True)
        self.target.write_bytes(b"\xff\xfeprivate body need not be decoded or read")
        value = self.root.stat()
        self.expected = (*native._identity(value), value.st_uid, value.st_gid)

    def test_existing_target_captures_metadata_without_payload_reader(self):
        inode = self.target.stat().st_ino
        with mock.patch.object(
            native, "_read", side_effect=AssertionError("payload read")
        ) as reader:
            nodes = native.capture_framework_reference_targets(
                self.root, self.expected, (self.relative,)
            )
            reader.assert_not_called()
        self.assertEqual(nodes[self.relative]["kind"], "file")
        self.assertEqual(set(nodes[self.relative]), {"kind", "mode", "stamp"})
        self.assertEqual(self.target.stat().st_ino, inode)
        self.assertEqual(
            self.target.read_bytes(),
            b"\xff\xfeprivate body need not be decoded or read",
        )

    def test_private_output_and_unsupported_targets_never_enter_root(self):
        self.assertEqual(
            native.capture_framework_reference_targets(
                None,
                None,
                (
                    "litai/samples/peer/.env",
                    "litai/samples/peer/credentials.json",
                    "litai/samples/peer/node_modules/token",
                    "litai/.literate/provider.json",
                    "litai/samples/peer/private.sqlite",
                    "application/credentials.json",
                    "litai/samples/peer/.git/config",
                ),
            ),
            {},
        )

    def test_missing_target_is_not_a_semantic_presence_fact(self):
        self.target.unlink()
        nodes = native.capture_framework_reference_targets(
            self.root, self.expected, (self.relative,)
        )
        self.assertNotIn(self.relative, nodes)

    def test_hardlinked_target_and_portable_alias_refuse(self):
        linked = self.target.parent / "shared.md"
        os.link(self.target, linked)
        try:
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "direct regular member"
            ):
                native.capture_framework_reference_targets(
                    self.root, self.expected, (self.relative,)
                )
        finally:
            linked.unlink()
        self.target.unlink()
        upper = self.target.parent / "Peer.md"
        upper.write_bytes(b"one")
        (self.target.parent / "peer.md").write_bytes(b"two")
        with self.assertRaisesRegex(ProjectLayoutPlanError, "portable alias"):
            native.capture_framework_reference_targets(
                self.root, self.expected, ("litai/samples/peer/peer.md",)
            )

    def test_reference_count_bound_refuses_before_native_root_use(self):
        coordinates = tuple(
            f"litai/samples/p{index}/component.md" for index in range(8193)
        )
        with self.assertRaisesRegex(
            ProjectLayoutPlanError, "bounded original reference"
        ):
            native.capture_framework_reference_targets(None, None, coordinates)

    def test_same_object_helper_and_parser_code_changes_refuse_before_call(self):
        for function in (
            ingress._reference_coordinates,
            ingress._reference_facts,
            ingress._reference_subjects,
            ingress._reference_subjects.__globals__["extract_markdown_links"],
        ):
            with self.subTest(function=function.__name__):
                original = function.__code__
                try:
                    function.__code__ = foreign_code(function)
                    with self.assertRaisesRegex(
                        ProjectLayoutPlanError, "reference target producer changed"
                    ):
                        ingress._invoke(function, None)
                finally:
                    function.__code__ = original

    def test_url_and_percent_decoder_helpers_refuse_same_object_code_changes(self):
        parser = ingress._reference_subjects.__globals__["unquote"].__globals__
        exercised = 0
        for name in (
            "_coerce_args",
            "_urlsplit",
            "_noop",
            "_generate_unquoted_parts",
            "_unquote_impl",
        ):
            value = parser.get(name)
            if value is None:
                continue  # The stdlib uses different helpers across Python versions.
            function = getattr(value, "__wrapped__", value)
            exercised += 1
            with self.subTest(helper=name):
                original = function.__code__
                try:
                    function.__code__ = foreign_code(function)
                    with self.assertRaisesRegex(
                        ProjectLayoutPlanError, "reference target producer changed"
                    ):
                        ingress._invoke(
                            ingress._reference_subjects,
                            "SKILL.md",
                            b"[peer](litai/samples/peer/%63omponent.md)",
                        )
                finally:
                    function.__code__ = original

        self.assertGreater(exercised, 0)

    def test_selector_parser_export_replacement_refuses_before_foreign_call(self):
        namespace = ingress._reference_subjects.__globals__
        original = namespace["_local_subjects"]
        calls = []

        def foreign(*args, **kwargs):
            calls.append((args, kwargs))
            return ()

        try:
            namespace["_local_subjects"] = foreign
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "reference target producer changed"
            ):
                ingress._invoke(
                    ingress._reference_subjects,
                    "SKILL.md",
                    b"[peer](litai/samples/peer/%63omponent.md)",
                )
            self.assertEqual(calls, [])
        finally:
            namespace["_local_subjects"] = original

    def test_reparse_mask_and_portable_path_grammar_changes_refuse_before_io(self):
        for namespace, name, replacement in (
            (native.stat_is_link_or_reparse.__globals__, "_WINDOWS_REPARSE_POINT", 0),
            (
                native.canonical_relative_posix_path.__globals__,
                "_WINDOWS_DRIVE_PREFIX",
                object(),
            ),
        ):
            with self.subTest(name=name):
                original = namespace[name]
                try:
                    namespace[name] = replacement
                    with self.assertRaisesRegex(
                        ProjectLayoutPlanError, "reference observation delegate changed"
                    ):
                        native.capture_framework_reference_targets(
                            None, None, (self.relative,)
                        )
                finally:
                    namespace[name] = original

    def test_imported_reference_is_not_owned_and_equal_byte_replacement_is_stale(self):
        template = resources.initialization._template_text("SKILL.md").encode()
        helper = support.MixedComponentChannelTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, _, _ = helper.fixture(
            shared_parent=True,
            original_skill_content=template
            + b"\n[peer](litai/samples/peer/%63omponent.md)\n",
        )
        plan = plan_legacy_layout_migration(
            project.root, (), place_forward_skills=False, place_imported_catalogs=True
        )
        self.assertTrue(plan["applicable"], plan["blocked_references"])
        apply_legacy_layout_migration(
            project.root,
            plan["plan_identity"],
            acknowledge=True,
            references=(),
            place_forward_skills=False,
            place_imported_catalogs=True,
        )
        public, selection = ingress.read_existing_framework_authority(project.root)
        self.addCleanup(ingress.close_observed_framework_selection, selection)
        self.assertTrue(public["applicable"], public["required_owners"])
        relative = "litai/samples/peer/component.md"
        self.assertNotIn(relative, selection.original_contents)
        self.assertNotIn(relative, selection.observations)
        self.assertNotIn(
            relative, {proof.source_path for proof in selection.source_proofs}
        )
        for action in (
            selection.placements,
            selection.owned_placements,
            selection.resident_edits,
            selection.reference_edits,
            selection.delegate_edits,
            selection.owned_creations,
        ):
            self.assertNotIn(relative, action)
            self.assertFalse(
                any(row.get("destination") == relative for row in action.values())
            )
        target = project.root / relative
        saved = self.root / "original-imported-peer"
        payload = target.read_bytes()
        mode = target.stat().st_mode & 0o7777
        target.rename(saved)
        target.write_bytes(payload)
        target.chmod(mode)
        foreign_inode = target.stat().st_ino
        try:
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "reference target native facts changed"
            ):
                ingress.require_current_observed_framework_selection(selection)
            self.assertEqual(target.read_bytes(), payload)
            self.assertEqual(target.stat().st_ino, foreign_inode)
        finally:
            target.unlink()
            saved.rename(target)

    def test_inherited_url_result_constructor_and_getter_refuse_before_use(self):
        parser = ingress._reference_subjects.__globals__["unquote"].__globals__
        result = parser["SplitResult"]
        owner = next(base for base in result.__mro__ if "path" in vars(base))
        original = vars(owner)["path"]

        def foreign_getter(self):
            raise AssertionError("foreign URL result getter invoked")

        try:
            owner.path = property(foreign_getter)
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "reference target producer changed"
            ):
                ingress._invoke(
                    ingress._reference_subjects,
                    "SKILL.md",
                    b"[peer](litai/samples/peer/component.md)",
                )
        finally:
            owner.path = original
        owner = next(base for base in result.__mro__ if "__new__" in vars(base))
        descriptor = vars(owner)["__new__"]
        constructor = getattr(descriptor, "__func__", descriptor)
        original = constructor.__code__
        try:
            constructor.__code__ = foreign_code(constructor)
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "reference target producer changed"
            ):
                ingress._invoke(
                    ingress._reference_subjects,
                    "SKILL.md",
                    b"[peer](litai/samples/peer/component.md)",
                )
        finally:
            constructor.__code__ = original

    def test_in_place_url_grammar_change_refuses_before_parser(self):
        parser = ingress._reference_subjects.__globals__["unquote"].__globals__
        sequence = parser["_UNSAFE_URL_BYTES_TO_REMOVE"]
        original = tuple(sequence)
        try:
            sequence.append("x")
            with self.assertRaisesRegex(
                ProjectLayoutPlanError, "URL grammar list changed"
            ):
                ingress._invoke(
                    ingress._reference_subjects,
                    "SKILL.md",
                    b"[peer](litai/samples/peer/component.md)",
                )
        finally:
            sequence[:] = original
