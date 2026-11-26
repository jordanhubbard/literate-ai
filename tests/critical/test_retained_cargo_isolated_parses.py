"""Real authority reads reuse parsing, never a guard or ended owner."""

import json
import os
import shutil
import time
import unittest
from contextlib import ExitStack, nullcontext
from pathlib import Path
from unittest.mock import patch

from literate_ai import projects
from literate_ai.adapters import component_lock_planning as planning
from literate_ai.adapters import legacy_generation_catalog as flavor_catalog
from literate_ai.adapters import locked_generation_authority as catalogs
from literate_ai.adapters import project_validation
from literate_ai.adapters import retained_cargo_execution_inputs_v2 as execution_inputs
from literate_ai.adapters.component_lock_application import (
    ProjectComponentLockSetError,
    current_project_component_locks,
)
from literate_ai.adapters.project_validation import ProjectValidationError
from literate_ai.adapters.retained_cargo_wrapper_v2 import RetainedCargoWrapperContextV2
from tests.support.fixtures_current_component_locks import (
    initialize_current_component_lock_fixture,
)
from tests.support.fixtures_retained_cargo_receiving_v2 import (
    initialize_retained_cargo_receiving_v2_fixture,
    receive_retained_cargo_fixture,
)


def _frames():
    return (
        projects._PROJECT_CONFIGURATION_PARSES.get(),
        catalogs._catalog_observations.get(),
    )


class IsolatedAuthorityParseFrameTests(unittest.TestCase):
    def setUp(self):
        initialize_current_component_lock_fixture(self)

    def test_nested_real_reads_restore_ambient_frames_on_success_and_exception(self):
        with (
            projects.read_only_project_configuration_parses(),
            catalogs.read_only_component_catalog_observations(),
        ):
            expected = current_project_component_locks(self.project)
            ambient = _frames()
            keys = (tuple(ambient[0].templates), tuple(ambient[1]))
            with (
                projects.read_only_project_configuration_parses(),
                catalogs.read_only_component_catalog_observations(),
            ):
                self.assertEqual(_frames(), ambient)
            for fail in (False, True):
                with self.subTest(fail=fail):
                    try:
                        with (
                            projects.read_only_project_configuration_parses(
                                isolated=True
                            ),
                            catalogs.read_only_component_catalog_observations(
                                isolated=True
                            ),
                        ):
                            inner = _frames()
                            self.assertIsNot(inner[0], ambient[0])
                            self.assertIsNot(inner[1], ambient[1])
                            self.assertEqual(inner[0].templates, {})
                            self.assertEqual(inner[1], {})
                            self.assertEqual(
                                current_project_component_locks(self.project), expected
                            )
                            if fail:
                                raise LookupError("owned nested-frame failure")
                    except LookupError as error:
                        self.assertTrue(fail)
                        self.assertEqual(str(error), "owned nested-frame failure")
                    self.assertIs(_frames()[0], ambient[0])
                    self.assertIs(_frames()[1], ambient[1])
                    self.assertEqual(
                        (tuple(ambient[0].templates), tuple(ambient[1])), keys
                    )
        self.assertEqual(_frames(), (None, None))

    def test_isolated_warm_catalog_checks_selected_and_flavor_dependencies(self):
        reader = catalogs.FilesystemLockedGenerationAuthorityReader()
        with (
            projects.read_only_project_configuration_parses(isolated=True),
            catalogs.read_only_component_catalog_observations(isolated=True),
        ):
            expected = current_project_component_locks(self.project)
            catalog = reader.load_catalog(self.component)
            paths = {
                self.component / "component.md",
                self.component / "specs/spec.md",
                self.component / "acceptance/execution.json",
                self.root / "skills/implement.json",
                self.root / "workflows/host.json",
                self.root / "routing/default.json",
            }
            for flavor in catalog._flavors:
                paths.add(flavor.path)
                paths.update(
                    flavor.path.parent / reference.uri
                    for reference in (
                        *flavor.definition.specification_fragments,
                        *flavor.definition.authoring_inputs,
                        *(item.content for item in flavor.definition.contributions),
                    )
                )
            for path in sorted(paths):
                with self.subTest(path=path.relative_to(self.root).as_posix()):
                    original = path.read_bytes()
                    try:
                        path.write_bytes(original + b"\nChanged exact input.\n")
                        with self.assertRaises(ProjectComponentLockSetError):
                            current_project_component_locks(self.project)
                        self.assertEqual(
                            path.read_bytes(), original + b"\nChanged exact input.\n"
                        )
                    finally:
                        path.write_bytes(original)
                    self.assertEqual(
                        current_project_component_locks(self.project), expected
                    )

    def test_isolated_catalog_observes_membership_nearest_project_and_redirects(self):
        with (
            projects.read_only_project_configuration_parses(isolated=True),
            catalogs.read_only_component_catalog_observations(isolated=True),
        ):
            expected = current_project_component_locks(self.project)
            added = self.component / "added/component.md"
            added.parent.mkdir()
            try:
                added.write_bytes((self.component / "component.md").read_bytes())
                with self.assertRaises(ProjectComponentLockSetError):
                    current_project_component_locks(self.project)
            finally:
                added.unlink()
                added.parent.rmdir()
            nearer = self.component / "literate.project.json"
            try:
                nearer.write_bytes(b"{}\n")
                with self.assertRaises(
                    (projects.ProjectError, ProjectComponentLockSetError)
                ):
                    current_project_component_locks(self.project)
            finally:
                nearer.unlink()
            if os.name != "nt":
                path = self.root / "flavors/lang-python/flavor.md"
                saved = path.with_name("saved-flavor.md")
                path.rename(saved)
                try:
                    path.symlink_to(saved.name)
                    with self.assertRaises(ProjectComponentLockSetError):
                        current_project_component_locks(self.project)
                finally:
                    path.unlink()
                    saved.rename(path)
            self.assertEqual(current_project_component_locks(self.project), expected)


@unittest.skipUnless(
    os.name != "nt" and shutil.which("git") and shutil.which("make"),
    "requires actual adopted POSIX source and native Git/Make",
)
class RetainedCargoIsolatedObservationTests(unittest.TestCase):
    def setUp(self):
        fixture = unittest.TestCase()
        self.addCleanup(fixture.doCleanups)
        initialize_retained_cargo_receiving_v2_fixture(fixture)
        self.fixture = fixture
        self.reviewed_binding = (
            fixture.reviewed.project.root / (fixture.reviewed.document_paths[1])
        )
        self.on_provider_read = None
        self.provider_reads = 0

        def read_current():
            self.provider_reads += 1
            if self.on_provider_read is not None:
                self.on_provider_read(self.provider_reads)
            return fixture.current

        materialized = receive_retained_cargo_fixture(
            fixture, read_current=read_current
        )
        home = fixture.base / "execution-cargo-home"
        home.mkdir()
        self.environment = {"CARGO_HOME": str(home), "PATH": os.environ["PATH"]}
        self.inputs = execution_inputs.read_retained_cargo_execution_inputs_v2(
            materialized, environment=self.environment
        )

    def observe(self, *, reuse, mutate=None):
        events = []
        original = RetainedCargoWrapperContextV2.require_unchanged
        calls = 0

        def guarded(context):
            nonlocal calls
            calls += 1
            ordinal = calls
            events.append(("enter", ordinal))
            result = original(context)
            events.append(("exit", ordinal))
            if ordinal == 1 and mutate is not None:
                mutate()
            return result

        with ExitStack() as stack:
            if not reuse:
                # Exact original body without the newly added parse-only scopes;
                # every actual owner/guard/read still runs.
                for name in (
                    "read_only_project_configuration_parses",
                    "read_only_component_catalog_observations",
                    "read_only_flavor_graph_observations",
                ):
                    stack.enter_context(
                        patch.object(execution_inputs, name, return_value=nullcontext())
                    )
            stack.enter_context(
                patch.object(
                    RetainedCargoWrapperContextV2, "require_unchanged", guarded
                )
            )
            parser = stack.enter_context(
                patch.object(
                    planning,
                    "_load_authoring_entry",
                    wraps=planning._load_authoring_entry,
                )
            )
            error = None
            value = None
            try:
                value = self.inputs.current_identity(environment=self.environment)
            except (ValueError, RuntimeError) as observed:
                error = observed
            return value, error, events, parser.call_count

    def observe_flavors(self, *, reuse):
        validations = []
        validate = project_validation.FilesystemProjectValidationAdapter.validate

        def checked(adapter, *args, **kwargs):
            validations.append(True)
            return validate(adapter, *args, **kwargs)

        reads = self.provider_reads
        started = time.monotonic()
        with ExitStack() as stack:
            if not reuse:
                stack.enter_context(
                    patch.object(
                        execution_inputs,
                        "read_only_flavor_graph_observations",
                        return_value=nullcontext(),
                        create=True,
                    )
                )
            stack.enter_context(
                patch.object(
                    project_validation.FilesystemProjectValidationAdapter,
                    "validate",
                    checked,
                )
            )
            parser = stack.enter_context(
                patch.object(
                    flavor_catalog,
                    "_load_legacy_flavor_entries",
                    wraps=flavor_catalog._load_legacy_flavor_entries,
                )
            )
            capture = stack.enter_context(
                patch.object(
                    flavor_catalog.LegacyFlavorGraphObservation,
                    "capture",
                    wraps=flavor_catalog.LegacyFlavorGraphObservation.capture,
                )
            )
            value, error, fences, _ = self.observe(reuse=True)
            return {
                "value": value,
                "error": error,
                "fences": fences,
                "parses": parser.call_count,
                "captures": capture.call_count,
                "validations": len(validations),
                "provider_reads": self.provider_reads - reads,
                "seconds": time.monotonic() - started,
            }

    def test_actual_flavor_guard_reuses_parsing_and_independent_calls_recapture(self):
        baseline = self.observe_flavors(reuse=False)
        candidate = self.observe_flavors(reuse=True)
        for field in ("value", "error", "fences", "validations", "provider_reads"):
            self.assertEqual(candidate[field], baseline[field], field)
        self.assertIsNone(candidate["error"])
        self.assertEqual(
            len([row for row in candidate["fences"] if row[0] == "enter"]), 16
        )
        self.assertGreater(candidate["validations"], 0)
        self.assertLess(candidate["parses"], baseline["parses"])
        self.assertEqual(candidate["captures"], 1)
        self.assertEqual(baseline["captures"], 0)
        again = self.observe_flavors(reuse=True)
        for field in (
            "value",
            "error",
            "fences",
            "parses",
            "captures",
            "validations",
            "provider_reads",
        ):
            self.assertEqual(again[field], candidate[field], field)
        self.assertIsNone(flavor_catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())
        print(
            "actual retained input guard comparison "
            + json.dumps(
                {
                    "scope": "real guarded source inputs, not native admission timing",
                    "baseline": {
                        k: baseline[k]
                        for k in (
                            "parses",
                            "captures",
                            "validations",
                            "provider_reads",
                            "seconds",
                        )
                    },
                    "candidate": {
                        k: candidate[k]
                        for k in (
                            "parses",
                            "captures",
                            "validations",
                            "provider_reads",
                            "seconds",
                        )
                    },
                }
            )
        )

    def after_last_materialization(self, mutate):
        owner = type(self.inputs.materialized)
        original = owner.require_unchanged
        calls = []

        def checked(materialized):
            result = original(materialized)
            if materialized is self.inputs.materialized:
                calls.append(True)
                if len(calls) == 2:
                    mutate()
            return result

        with patch.object(owner, "require_unchanged", checked):
            with self.assertRaises(
                (ValueError, RuntimeError, flavor_catalog.CliFailure)
            ):
                self.inputs.current_identity(environment=self.environment)
        self.assertEqual(len(calls), 2)
        self.assertIsNone(flavor_catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())

    def test_final_flavor_byte_drift_with_restored_mtime_cannot_escape_return(self):
        path = next(iter(self.fixture.context.bindings[0][1]._flavors)).path
        original = path.read_bytes()
        metadata = path.stat()
        baseline = self.inputs.current_identity(environment=self.environment)

        def mutate():
            path.write_bytes(bytes([original[0] ^ 1]) + original[1:])
            os.utime(path, ns=(metadata.st_atime_ns, metadata.st_mtime_ns))

        try:
            self.after_last_materialization(mutate)
        finally:
            path.write_bytes(original)
        self.assertEqual(
            self.inputs.current_identity(environment=self.environment), baseline
        )

    def test_final_flavor_membership_and_nearer_project_changes_refuse(self):
        path = next(iter(self.fixture.context.bindings[0][1]._flavors)).path
        alternate = path.with_name(
            "flavor.json" if path.name == "flavor.md" else "flavor.md"
        )
        nearer = path.parent / "literate.project.json"
        for added in (alternate, nearer):
            with self.subTest(path=added.name):
                self.assertFalse(added.exists())
                try:
                    self.after_last_materialization(
                        lambda added=added: added.write_bytes(b"{}\n")
                    )
                finally:
                    added.unlink(missing_ok=True)
                self.inputs.current_identity(environment=self.environment)

    def test_actual_guard_flavor_scope_is_independent_and_restored_on_failure(self):
        with flavor_catalog.read_only_flavor_graph_observations():
            ambient = flavor_catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
            self.inputs.current_identity(environment=self.environment)
            self.assertIs(flavor_catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get(), ambient)
            self.assertEqual(ambient, {})
            error = RuntimeError("owned source callback failure")

            def fail(_ordinal):
                raise error

            self.on_provider_read = fail
            try:
                with self.assertRaises(RuntimeError) as observed:
                    self.inputs.current_identity(environment=self.environment)
                self.assertIs(observed.exception, error)
            finally:
                self.on_provider_read = None
            self.assertIs(flavor_catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get(), ambient)
            self.assertEqual(ambient, {})
        self.inputs.current_identity(environment=self.environment)
        self.assertIsNone(flavor_catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get())

    def test_identity_keeps_sixteen_explicit_fences_and_parse_isolation(self):
        before = _frames()
        baseline = self.observe(reuse=False)
        candidate = self.observe(reuse=True)
        self.assertIsNone(baseline[1])
        self.assertIsNone(candidate[1])
        self.assertEqual(candidate[0], baseline[0])
        self.assertEqual(candidate[2], baseline[2])
        self.assertEqual(len([x for x in candidate[2] if x[0] == "enter"]), 16)
        self.assertGreater(candidate[3], 0)  # Each isolated observation starts cold.
        self.assertLess(candidate[3], baseline[3])
        self.assertEqual(_frames(), before)
        again = self.observe(reuse=True)
        self.assertEqual(again[0], baseline[0])
        self.assertEqual(again[3], candidate[3])
        self.assertEqual(_frames(), before)

    def test_warm_observation_preserves_refusal_stage_for_real_authority_mutations(
        self,
    ):
        context = self.fixture.context
        paths = [
            context.bindings[0][1].root / "component.md",
            next(iter(context.bindings[0][1]._flavors)).path,
        ]
        # Selected payloads are independently closed after catalog checks.
        closure = context._closures[0]
        paths.append(
            next(
                entry.path
                for entry in closure._entries.values()
                if entry.path.suffix == ".md" and entry.path.name != "component.md"
            )
        )
        flavor_labels = {
            paths[1]: "flavor:flavor://literate-ai/build-make:manifest",
            paths[2]: (
                "flavor:flavor://legacy-adoption/build-legacy-shim:"
                "authoring-input:0:specification-to-source-skill"
            ),
        }
        for path in paths:
            self.assertFalse(path.is_relative_to(context.workspace))
            original = path.read_bytes()
            results = []
            for reuse in (False, True):
                with self.subTest(path=path.name, reuse=reuse):
                    try:
                        result = self.observe(
                            reuse=reuse,
                            mutate=lambda path=path, original=original: (
                                path.write_bytes(original + b"\nChanged.\n")
                            ),
                        )
                        self.assertIsNone(result[0])
                        self.assertIsNotNone(result[1])
                        results.append(
                            (
                                type(result[1]),
                                getattr(result[1], "code", None),
                                str(result[1]),
                                result[2],
                            )
                        )
                    finally:
                        path.write_bytes(original)
                    self.assertEqual(_frames(), (None, None))
                    self.assertIsNone(
                        flavor_catalog._READ_ONLY_FLAVOR_OBSERVATIONS.get()
                    )
            if path in flavor_labels:
                # The Flavor pins its manifest and authoring skill. Both detect
                # drift before documentation review, at the same second fence.
                self.assertIs(results[0][0], ProjectValidationError)
                self.assertEqual(
                    results[0][1], "project.documentation_authority_review_stale"
                )
                self.assertIs(results[1][0], projects.PinnedInputClosureError)
                self.assertEqual(results[1][1], "inputs.closure_changed")
                self.assertEqual(
                    results[1][2],
                    "generation authority changed during the operation: "
                    + flavor_labels[path],
                )
                self.assertEqual(results[0][3], results[1][3])
                self.assertEqual(
                    results[1][3], [("enter", 1), ("exit", 1), ("enter", 2)]
                )
            else:
                self.assertEqual(results[0], results[1])

    def test_callback_failures_restore_nested_ambient_frames(self):
        with (
            projects.read_only_project_configuration_parses(),
            catalogs.read_only_component_catalog_observations(),
        ):
            ambient = _frames()
            error = RuntimeError("original provider read failed")
            for fail_at in (1, 2):
                with self.subTest(fail_at=fail_at):

                    def fail(ordinal, target=fail_at):
                        if ordinal == target:
                            raise error

                    self.on_provider_read = fail
                    self.provider_reads = 0
                    try:
                        with self.assertRaises(RuntimeError) as observed:
                            self.inputs.current_identity(environment=self.environment)
                        self.assertIs(observed.exception, error)
                        self.assertEqual(self.provider_reads, fail_at)
                    finally:
                        self.on_provider_read = None
                    self.assertIs(_frames()[0], ambient[0])
                    self.assertIs(_frames()[1], ambient[1])
            self.inputs.current_identity(environment=self.environment)
        self.assertEqual(_frames(), (None, None))

    def test_closing_provider_callback_cannot_change_wrapper_component(self):
        context = self.fixture.context
        component = context.bindings[0][1].root / "component.md"
        self.assertFalse(component.is_relative_to(context.workspace))
        content = component.read_bytes()
        changed = content + b"\nProvider changed the selected wrapper Component.\n"

        def mutate(ordinal):
            if ordinal == 2:
                component.write_bytes(changed)

        self.provider_reads = 0
        self.on_provider_read = mutate
        try:
            with self.assertRaises(ProjectValidationError) as refusal:
                self.inputs.current_identity(environment=self.environment)
            self.assertEqual(
                refusal.exception.code, "project.documentation_authority_review_stale"
            )
            self.assertEqual(self.provider_reads, 2)
            self.assertEqual(component.read_bytes(), changed)
        finally:
            self.on_provider_read = None
            component.write_bytes(content)
        self.assertEqual(_frames(), (None, None))

    def test_ended_actual_scratch_still_refuses_and_clears_isolated_frames(self):
        self.fixture.scratch_manager.__exit__(None, None, None)
        with self.assertRaisesRegex(ValueError, "scratch-operation-ended"):
            self.inputs.current_identity(environment=self.environment)
        self.assertEqual(_frames(), (None, None))

    def test_captured_projection_is_closed_against_cargo_home_mutation(self):
        scope = self.inputs.scope
        original = type(scope)._captured_identity
        changed = Path(self.environment["CARGO_HOME"]) / "late-input"

        def project(scope):
            identity = original(scope)
            changed.write_bytes(b"new member during projection\n")
            return identity

        try:
            with (
                patch.object(type(scope), "_captured_identity", project),
                self.assertRaisesRegex(ValueError, "input-custody-changed"),
            ):
                self.inputs.current_identity(environment=self.environment)
        finally:
            changed.unlink(missing_ok=True)

    def test_public_scope_identity_validates_wrapper_and_lifetime(self):
        scope = self.inputs.scope
        self.assertEqual(scope.identity, scope._captured_identity())
        content = self.reviewed_binding.read_bytes()
        owners_type = type(scope.owners)
        owners_identity = owners_type.identity.fget

        def mutate(owners):
            identity = owners_identity(owners)
            self.reviewed_binding.write_bytes(content + b"\n")
            return identity

        try:
            with (
                patch.object(owners_type, "identity", property(mutate)),
                self.assertRaisesRegex(ValueError, "generation authority changed"),
            ):
                _ = scope.identity
        finally:
            self.reviewed_binding.write_bytes(content)
        self.fixture.doCleanups()
        with self.assertRaisesRegex(ValueError, "wrapper-operation-ended"):
            _ = scope.identity
