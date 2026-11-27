"""Operation-local graph metadata preserves fresh authority and exact inputs."""

import json
import os
import pickle
import shutil
import unittest
from contextvars import copy_context
from pathlib import Path
from unittest.mock import Mock, patch

import literate_ai.adapters.legacy_generation_catalog as catalog
import literate_ai.adapters.project_verification as verification
import literate_ai.project_authority_graph as graph
from tests.critical import test_current_component_locks as fixtures
from tests.support.fixtures_test_cli_component_locks import _run


class LineageFlavorObservationTests(unittest.TestCase):
    def setUp(self):
        fixture = fixtures.CurrentComponentLockTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.root = fixture.root
        self.component = fixture.component
        self.roots = (self.root / "flavors",)

    def capture(self):
        return catalog.LegacyFlavorGraphObservation.capture(self.roots)

    def test_bound_scope_keeps_one_exact_root_key_and_foreign_reads_fresh(self):
        other = fixtures.CurrentComponentLockTests()
        other.setUp()
        self.addCleanup(other.doCleanups)
        with patch.object(
            catalog,
            "_load_legacy_flavor_entries",
            wraps=catalog._load_legacy_flavor_entries,
        ) as load:
            with catalog.read_only_flavor_graph_observations(allowed_roots=self.roots):
                frame = catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
                first = graph.project_authority_graph(
                    self.root, include_component_locks=False
                )
                second = graph.project_authority_graph(
                    self.root, include_component_locks=False
                )
                self.assertEqual(first, second)
                self.assertIsNot(first, second)
                self.assertIsNone(
                    catalog.scoped_flavor_graph_observation(
                        (Path(str(self.roots[0]).upper()),)
                    )
                )
                for _ in range(2):
                    graph.project_authority_graph(
                        other.root, include_component_locks=False
                    )
                self.assertEqual(
                    tuple(frame.observations), (tuple(str(p) for p in self.roots),)
                )
                self.assertEqual(load.call_count, 3)
            self.assertFalse(frame.active)
            self.assertEqual(frame.observations, {})

    def test_bound_nested_scopes_and_copied_retired_contexts_do_not_revive_cache(self):
        with catalog.read_only_flavor_graph_observations(allowed_roots=self.roots):
            outer = catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
            original = catalog.scoped_flavor_graph_observation(self.roots)
            copied = copy_context()
            with catalog.read_only_flavor_graph_observations(allowed_roots=self.roots):
                inner = catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
                self.assertIsNot(inner, outer)
                self.assertIsNot(
                    catalog.scoped_flavor_graph_observation(self.roots), original
                )
            self.assertFalse(inner.active)
            self.assertIs(catalog.scoped_flavor_graph_observation(self.roots), original)
        self.assertIsNone(
            copied.run(catalog.scoped_flavor_graph_observation, self.roots)
        )
        with patch.object(
            catalog,
            "_load_legacy_flavor_entries",
            wraps=catalog._load_legacy_flavor_entries,
        ) as load:
            for _ in range(2):
                copied.run(
                    graph.project_authority_graph,
                    self.root,
                    include_component_locks=False,
                )
            self.assertEqual(load.call_count, 2)
        self.assertFalse(outer.active)
        self.assertEqual(outer.observations, {})

    def test_premature_retirement_refuses_owner_close_but_copied_reads_fresh(self):
        with self.assertRaises(catalog.CliFailure):
            with catalog.read_only_flavor_graph_observations(allowed_roots=self.roots):
                catalog.scoped_flavor_graph_observation(self.roots)
                frame = catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
                copied = copy_context()
                frame._retire()
                self.assertIsNone(catalog.scoped_flavor_graph_observation(self.roots))
        self.assertFalse(frame.active)
        self.assertIsNone(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())
        with patch.object(
            catalog,
            "_load_legacy_flavor_entries",
            wraps=catalog._load_legacy_flavor_entries,
        ) as load:
            for _ in range(2):
                copied.run(
                    graph.project_authority_graph,
                    self.root,
                    include_component_locks=False,
                )
            self.assertEqual(load.call_count, 2)

    def test_bound_scope_preserves_body_exception_and_always_retires(self):
        failure = RuntimeError("original consumer failure")
        path = self.roots[0] / "os-macos/flavor.md"
        original = path.read_bytes()
        try:
            with self.assertRaises(RuntimeError) as caught:
                with catalog.read_only_flavor_graph_observations(
                    allowed_roots=self.roots
                ):
                    catalog.scoped_flavor_graph_observation(self.roots)
                    frame = catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
                    path.write_bytes(original + b"\n")
                    raise failure
            self.assertIs(caught.exception, failure)
            self.assertFalse(frame.active)
            self.assertEqual(frame.observations, {})
            self.assertIsNone(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())
        finally:
            path.write_bytes(original)

    def test_original_primitive_metadata_and_reference_fences_refuse_tampering(self):
        for kind in (
            "item",
            "metadata-copy",
            "roots-copy",
            "closures-copy",
            "coordinated-baseline",
        ):
            for direct in (False, True):
                with (
                    self.subTest(kind=kind, direct=direct),
                    self.assertRaises(catalog.CliFailure),
                ):
                    with catalog.read_only_flavor_graph_observations(
                        allowed_roots=self.roots
                    ):
                        observed = catalog.scoped_flavor_graph_observation(self.roots)
                        if kind == "item":
                            object.__setattr__(
                                observed._metadata[0], "flavor_id", "changed"
                            )
                        elif kind == "metadata-copy":
                            object.__setattr__(
                                observed, "_metadata", tuple(list(observed._metadata))
                            )
                        elif kind == "roots-copy":
                            object.__setattr__(
                                observed, "roots", tuple(list(observed.roots))
                            )
                        elif kind == "closures-copy":
                            object.__setattr__(
                                observed, "_closures", tuple(list(observed._closures))
                            )
                        else:
                            original = observed._metadata
                            object.__setattr__(
                                observed, "_metadata", tuple(list(original))
                            )
                            object.__setattr__(
                                observed, "_integrity", lambda value=original: value
                            )
                        if direct:
                            observed.require_current(self.roots)
                        # Otherwise only the final scope close observes drift.

    def test_immutable_unframed_anchor_rejects_both_replacement_paths(self):
        for field in ("_metadata", "_integrity", "roots", "_closures"):
            for raw in (False, True):
                with self.subTest(field=field, raw=raw):
                    observed = self.capture()
                    metadata = observed._metadata
                    value = (
                        (lambda value=metadata: value) if field == "_integrity" else ()
                    )
                    with self.assertRaises(catalog.CliFailure):
                        if raw:
                            object.__setattr__(observed, field, value)
                        else:
                            setattr(observed, field, value)
                    self.assertIs(observed.require_current(self.roots), metadata)

    def test_index_tampering_refuses_at_direct_check_and_final_close(self):
        for kind in ("clear", "replace-entry", "replace-index", "replace-key"):
            for direct in (False, True):
                with self.subTest(kind=kind, direct=direct):
                    with self.assertRaises(catalog.CliFailure):
                        with catalog.read_only_flavor_graph_observations(
                            allowed_roots=self.roots
                        ):
                            observed = catalog.scoped_flavor_graph_observation(
                                self.roots
                            )
                            frame = catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
                            key = tuple(str(p) for p in self.roots)
                            if kind == "clear":
                                frame.observations.clear()
                            elif kind == "replace-entry":
                                frame.observations[key] = (observed, lambda: ())
                            elif kind == "replace-index":
                                object.__setattr__(frame, "observations", {})
                            else:
                                entry = frame.observations.pop(key)
                                frame.observations[("other",)] = entry
                            if direct:
                                observed.require_current(self.roots)
                    self.assertFalse(frame.active)
                    self.assertEqual(frame.observations, {})
                    self.assertIsNone(catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())

    def test_allowed_root_and_scope_anchor_replacement_refuses(self):
        for field in ("allowed_roots", "_lookup", "_integrity", "_close", "_retire"):
            for raw in (False, True):
                with self.subTest(field=field, raw=raw):
                    with self.assertRaises(catalog.CliFailure):
                        with catalog.read_only_flavor_graph_observations(
                            allowed_roots=self.roots
                        ):
                            catalog.scoped_flavor_graph_observation(self.roots)
                            frame = catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
                            value = () if field == "allowed_roots" else lambda: None
                            if raw:
                                object.__setattr__(frame, field, value)
                            else:
                                setattr(frame, field, value)
                    self.assertFalse(frame.active)

    def test_original_closure_values_refuse_coordinated_baseline_edits(self):
        for kind in ("content", "labels", "membership", "limits"):
            for scoped in (False, True):
                with self.subTest(kind=kind, scoped=scoped):
                    path = self.roots[0] / "os-macos/flavor.md"
                    original_bytes = path.read_bytes()
                    try:

                        def mutate(
                            observed,
                            path=path,
                            kind=kind,
                            original_bytes=original_bytes,
                        ):
                            closure = next(
                                c
                                for c in observed._closures
                                if any(e.path == path for e in c._entries.values())
                            )
                            entry = next(
                                e for e in closure._entries.values() if e.path == path
                            )
                            if kind == "content":
                                changed = original_bytes + b"\n"
                                path.write_bytes(changed)
                                object.__setattr__(entry, "content", changed)
                            elif kind == "labels":
                                object.__setattr__(entry, "labels", ("changed",))
                            elif kind == "membership":
                                closure._entries.clear()
                            else:
                                closure.maximum_total_bytes += 1

                        if scoped:
                            with self.assertRaises((ValueError, catalog.CliFailure)):
                                with catalog.read_only_flavor_graph_observations(
                                    allowed_roots=self.roots
                                ):
                                    mutate(
                                        catalog.scoped_flavor_graph_observation(
                                            self.roots
                                        )
                                    )
                        else:
                            observed = self.capture()
                            mutate(observed)
                            with self.assertRaises((ValueError, catalog.CliFailure)):
                                observed.require_current(self.roots)
                    finally:
                        path.write_bytes(original_bytes)

    def test_direct_manual_observation_checks_primitive_metadata_on_every_call(self):
        observed = self.capture()
        object.__setattr__(observed._metadata[0], "revision_digest", 7)
        with self.assertRaises(catalog.CliFailure):
            observed.require_current(self.roots)

    def test_graph_direct_close_uses_independently_retained_metadata_fence(self):
        original_component = graph._component_authoring
        original_current = catalog.LegacyFlavorGraphObservation.require_current
        swapped = False
        closing_checks = []
        with self.assertRaises(catalog.CliFailure) as caught:
            with catalog.read_only_flavor_graph_observations(allowed_roots=self.roots):
                observed = catalog.scoped_flavor_graph_observation(self.roots)

                def component(*args, **kwargs):
                    nonlocal swapped
                    result = original_component(*args, **kwargs)
                    if not swapped:
                        object.__setattr__(
                            observed._metadata[0], "flavor_id", "changed"
                        )
                        swapped = True
                    return result

                def current(observation, roots):
                    if swapped:
                        closing_checks.append(True)
                    return original_current(observation, roots)

                with (
                    patch.object(graph, "_component_authoring", side_effect=component),
                    patch.object(
                        catalog.LegacyFlavorGraphObservation,
                        "require_current",
                        autospec=True,
                        side_effect=current,
                    ),
                ):
                    graph.project_authority_graph(
                        self.root, include_component_locks=False
                    )
        self.assertTrue(swapped)
        self.assertTrue(closing_checks)
        self.assertEqual(caught.exception.code, "generate.input_capture_drift")

    def test_bound_final_close_rejects_changed_bytes_references_and_membership(self):
        for kind in ("bytes", "reference", "member"):
            changed = None
            added = self.roots[0] / "added-during-consumption"
            try:
                expected = catalog.CliFailure if kind == "member" else ValueError
                with self.subTest(kind=kind), self.assertRaises(expected):
                    with catalog.read_only_flavor_graph_observations(
                        allowed_roots=self.roots
                    ):
                        observed = catalog.scoped_flavor_graph_observation(self.roots)
                        if kind == "member":
                            shutil.copytree(self.roots[0] / "os-macos", added)
                        else:
                            path = self.roots[0] / "os-macos/flavor.md"
                            if kind == "reference":
                                path = next(
                                    entry.path
                                    for closure in observed._closures
                                    for entry in closure._entries.values()
                                    if entry.path.name
                                    not in {"flavor.md", "literate.project.json"}
                                )
                            changed = (path, path.read_bytes())
                            path.write_bytes(changed[1] + b"\n")
            finally:
                if changed is not None:
                    changed[0].write_bytes(changed[1])
                if added.exists():
                    shutil.rmtree(added)

    def test_final_validation_cannot_capture_a_new_key(self):
        original = catalog.LegacyFlavorGraphObservation.require_current
        closing = []

        def check(observed, roots):
            frame = catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
            if frame.closing:
                closing.append(True)
                self.assertIsNone(
                    catalog.scoped_flavor_graph_observation((self.root / "never-read",))
                )
            return original(observed, roots)

        with patch.object(
            catalog.LegacyFlavorGraphObservation,
            "require_current",
            autospec=True,
            side_effect=check,
        ):
            with catalog.read_only_flavor_graph_observations():
                catalog.scoped_flavor_graph_observation(self.roots)
        self.assertEqual(closing, [True])

    def test_read_only_scopes_share_parsing_but_keep_graphs_and_calls_independent(self):
        with (
            patch.object(
                catalog,
                "_load_legacy_flavor_entries",
                wraps=catalog._load_legacy_flavor_entries,
            ) as load,
            patch.object(
                graph, "project_skill_catalog", wraps=graph.project_skill_catalog
            ) as skills,
        ):
            for _ in range(2):
                with catalog.read_only_flavor_graph_observations():
                    first = graph.project_authority_graph(
                        self.root, include_component_locks=False
                    )
                    second = graph.project_authority_graph(
                        self.root, include_component_locks=False
                    )
                    self.assertEqual(first, second)
                    self.assertIsNot(first, second)
            self.assertEqual(load.call_count, 2)
            self.assertEqual(skills.call_count, 4)
            for _ in range(2):
                graph.project_authority_graph(self.root, include_component_locks=False)
            self.assertEqual(load.call_count, 4)

    def test_nested_read_only_scopes_do_not_inherit_parent_observations(self):
        with patch.object(
            catalog,
            "_load_legacy_flavor_entries",
            wraps=catalog._load_legacy_flavor_entries,
        ) as load:
            with catalog.read_only_flavor_graph_observations():
                graph.project_authority_graph(self.root, include_component_locks=False)
                with catalog.read_only_flavor_graph_observations():
                    graph.project_authority_graph(
                        self.root, include_component_locks=False
                    )
                graph.project_authority_graph(self.root, include_component_locks=False)
            self.assertEqual(load.call_count, 2)

    def test_scope_exit_refuses_byte_drift_after_the_last_graph(self):
        path = self.roots[0] / "os-macos/flavor.md"
        original = path.read_bytes()
        info = path.stat()
        with self.assertRaises(ValueError):
            with catalog.read_only_flavor_graph_observations():
                graph.project_authority_graph(self.root, include_component_locks=False)
                path.write_bytes(original.replace(b"macOS", b"macOs", 1))
                os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        path.write_bytes(original)
        # A rejected observation must not poison the next independent operation.
        with catalog.read_only_flavor_graph_observations():
            graph.project_authority_graph(self.root, include_component_locks=False)

    def test_public_verify_refuses_drift_after_its_last_gate_without_writes(self):
        manifest = self.root / "literate.project.json"
        definition = json.loads(manifest.read_text())
        definition["default_flavor_selectors"] = ["+python", "+macos"]
        manifest.write_text(json.dumps(definition))
        status, report, error = _run(
            ["lock", str(self.component), "--target", "host", "--json"]
        )
        self.assertEqual(status, 0, (report, error))
        baseline, status = verification.observe_project_verification(
            self.root, gates=("locks",)
        )
        self.assertEqual(status, 0, baseline)
        path = self.roots[0] / "os-macos/flavor.md"
        original = path.read_bytes()
        before = {p: p.read_bytes() for p in self.component.glob("component*.json")}
        observe = verification._GATES["source-intelligence"]

        def changed(root):
            result = observe(root)
            path.write_bytes(original + b"\n")
            return result

        with patch.dict(verification._GATES, {"source-intelligence": changed}):
            with self.assertRaises(verification.ProjectVerificationError) as refusal:
                verification.observe_project_verification(
                    self.root, gates=("locks", "source-intelligence")
                )
        self.assertEqual(refusal.exception.code, "inputs.closure_changed")
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        path.write_bytes(original)
        result, status = verification.observe_project_verification(
            self.root, gates=("locks",)
        )
        self.assertEqual(status, 0, result)

    def test_raw_and_transported_success_claims_are_not_observations(self):
        with self.assertRaises(TypeError):
            catalog.LegacyFlavorGraphObservation()
        with self.assertRaises(TypeError):
            pickle.dumps(self.capture())
        claimed = Mock()
        with self.assertRaises(TypeError):
            graph.project_authority_graph(self.root, flavor_observation=claimed)
        claimed.require_current.assert_not_called()

    def test_metadata_reuse_keeps_full_fresh_graphs_and_skill_validation(self):
        expected = graph.project_authority_graph(
            self.root, include_component_locks=False
        )
        with patch.object(
            catalog,
            "_load_legacy_flavor_entries",
            wraps=catalog._load_legacy_flavor_entries,
        ) as load:
            observed = self.capture()
            with patch.object(
                graph, "project_skill_catalog", wraps=graph.project_skill_catalog
            ) as skills:
                for _ in range(2):
                    actual = graph.project_authority_graph(
                        self.root,
                        include_component_locks=False,
                        flavor_observation=observed,
                    )
                    self.assertEqual(actual, expected)
                self.assertEqual(skills.call_count, 2)
            self.assertEqual(load.call_count, 1)
        self.assertTrue(
            all(
                isinstance(item, catalog.FlavorGraphMetadata)
                for item in observed.require_current(self.roots)
            )
        )

    def test_same_size_same_mtime_manifest_change_refuses(self):
        observed = self.capture()
        path = self.roots[0] / "os-macos/flavor.md"
        original = path.read_bytes()
        token = b"macOS"
        self.assertIn(token, original)
        info = path.stat()
        path.write_bytes(original.replace(token, b"macOs", 1))
        os.utime(path, ns=(info.st_atime_ns, info.st_mtime_ns))
        with self.assertRaises(ValueError):
            observed.require_current(self.roots)

    def test_new_and_missing_members_refuse(self):
        for change in ("add", "missing"):
            with self.subTest(change=change):
                observed = self.capture()
                path = self.roots[0] / "os-macos/flavor.md"
                original = path.read_bytes()
                extra = self.roots[0] / "additional"
                try:
                    if change == "add":
                        shutil.copytree(path.parent, extra)
                    else:
                        path.unlink()
                    with self.assertRaises((ValueError, RuntimeError)):
                        observed.require_current(self.roots)
                finally:
                    path.write_bytes(original)
                    if extra.exists():
                        shutil.rmtree(extra)

    @unittest.skipIf(
        os.name == "nt", "POSIX symlink; native Windows reparse checks are separate"
    )
    def test_redirected_member_refuses(self):
        observed = self.capture()
        path = self.roots[0] / "os-macos/flavor.md"
        backup = path.with_suffix(".saved")
        path.rename(backup)
        try:
            path.symlink_to(backup)
            with self.assertRaises(ValueError):
                observed.require_current(self.roots)
        finally:
            path.unlink(missing_ok=True)
            backup.rename(path)

    def test_nearer_project_creation_and_changed_project_bytes_refuse(self):
        observed = self.capture()
        nearer = self.roots[0] / "os-macos/literate.project.json"
        nearer.write_bytes((self.root / "literate.project.json").read_bytes())
        with self.assertRaises(RuntimeError):
            observed.require_current(self.roots)
        nearer.unlink()
        project = self.root / "literate.project.json"
        project.write_bytes(project.read_bytes() + b"\n")
        with self.assertRaises(RuntimeError):
            observed.require_current(self.roots)

    def test_wrong_catalog_roots_refuse(self):
        with self.assertRaises(RuntimeError):
            self.capture().require_current(())

    def test_changed_specification_and_contribution_bytes_refuse(self):
        for relative in ("lang-python/openspec/spec.md", "lang-python/toolchain.json"):
            with self.subTest(relative=relative):
                observed = self.capture()
                path = self.roots[0] / relative
                original = path.read_bytes()
                try:
                    path.write_bytes(original + b"\n")
                    with self.assertRaises(ValueError):
                        observed.require_current(self.roots)
                finally:
                    path.write_bytes(original)

    def test_public_check_refuses_drift_without_replacing_lock_or_audit(self):
        common = [
            "lock",
            str(self.component),
            "--target",
            "host",
            "--flavor",
            "+python",
            "--flavor",
            "+macos",
            "--flavor-root",
            str(self.roots[0]),
            "--json",
            "--check",
        ]
        before = {p: p.read_bytes() for p in self.component.glob("component*.json")}
        capture = catalog.LegacyFlavorGraphObservation.capture

        def changed(roots):
            observed = capture(roots)
            path = self.roots[0] / "os-macos/flavor.md"
            path.write_bytes(path.read_bytes() + b"\n")
            return observed

        with patch.object(
            catalog.LegacyFlavorGraphObservation, "capture", side_effect=changed
        ):
            status, report, error = _run(common)
            self.assertEqual(status, 2, (report, error))
            self.assertEqual(report["error"]["code"], "inputs.closure_changed")
        self.assertEqual({p: p.read_bytes() for p in before}, before)

    def test_unrelated_skill_invalidity_still_fails_fresh_graph_validation(self):
        observed = self.capture()
        (self.root / "SKILL.md").write_bytes(b"---\nname: [invalid\n---\n")
        with self.assertRaises(ValueError):
            graph.project_authority_graph(
                self.root, include_component_locks=False, flavor_observation=observed
            )

    def test_new_component_self_cycle_still_fails_fresh_graph_validation(self):
        observed = self.capture()
        path = self.component / "component.md"
        content = path.read_text()
        self.assertIn("uri: skills/implement.json", content)
        path.write_text(
            content.replace("uri: skills/implement.json", "uri: greeting/component.md")
        )
        with self.assertRaises(graph.AuthorityGraphError) as refusal:
            graph.project_authority_graph(
                self.root, include_component_locks=False, flavor_observation=observed
            )
        self.assertEqual(refusal.exception.code, "graph.cycle")

    def test_drift_during_graph_construction_refuses_after_graph_validation(self):
        observed = self.capture()
        original = graph._component_authoring
        path = self.roots[0] / "os-macos/flavor.md"

        def changed(*args, **kwargs):
            result = original(*args, **kwargs)
            path.write_bytes(path.read_bytes() + b"\n")
            return result

        with patch.object(graph, "_component_authoring", side_effect=changed):
            with self.assertRaises(ValueError):
                graph.project_authority_graph(
                    self.root,
                    include_component_locks=False,
                    flavor_observation=observed,
                )

    def test_check_owns_one_observation_and_writers_remain_fresh(self):
        common = [
            "lock",
            str(self.component),
            "--target",
            "host",
            "--flavor",
            "+python",
            "--flavor",
            "+macos",
            "--flavor-root",
            str(self.roots[0]),
            "--json",
        ]
        artifacts = tuple(self.component.glob("component*.json"))
        before = {p: p.read_bytes() for p in artifacts}
        with (
            patch.object(
                catalog.LegacyFlavorGraphObservation,
                "capture",
                wraps=catalog.LegacyFlavorGraphObservation.capture,
            ) as capture,
            patch.object(
                graph, "project_authority_graph", wraps=graph.project_authority_graph
            ) as build,
        ):
            for _ in range(2):
                status, report, error = _run([*common, "--check"])
                self.assertEqual(status, 0, (report, error))
            self.assertEqual(capture.call_count, 2)
            self.assertEqual(build.call_count, 8)
        self.assertEqual({p: p.read_bytes() for p in artifacts}, before)
        with patch.object(
            catalog.LegacyFlavorGraphObservation,
            "capture",
            side_effect=AssertionError("writer reused graph metadata"),
        ):
            status, report, error = _run(common)
            self.assertEqual(status, 0, (report, error))
