"""Original issued initialized proofs + actual normal Component producers.

Installed-origin lookup alone is explicitly modeled, as in resource-owner tests.
No ComponentImport, remote acquisition, process execution or move qualification.
"""

from __future__ import annotations

import copy
import os
import shutil
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from literate_ai.adapters import project_layout_component_transition as transition
from literate_ai.adapters import project_layout_framework_resources as resources
from literate_ai.adapters import project_layout_initialized_component_capture as capture
from literate_ai.adapters.component_lock_application import update_component_lock
from literate_ai.adapters.project_layout_planning import (
    ProjectLayoutObservation,
    ProjectLayoutPlanError,
)
from literate_ai.adapters.update_merge import UpdateBases
from literate_ai.contracts import (
    CatalogImportsFile,
    ContentIdentity,
    ProjectInitializationBaselineFile,
    canonical_json_bytes,
)
from literate_ai.projects import serialize_project_configuration
from tests.critical import test_project_layout_framework_source_proofs as support


class InitializedComponentCaptureTests(unittest.TestCase):
    def fixture(self, *, with_lock=False, contained=False, missing_historical=False):
        helper = support.InitializedFrameworkProofTests("runTest")
        self.addCleanup(helper.doCleanups)
        project, previous = helper.fixture()
        logical = "samples/hello-component/component.md"
        source = ("litai/" if contained else "") + logical
        # Exact current original sample has a one-file authored item. Its actual
        # declared external skills/Flavors/workflows/routing come from resources.
        for path, payload in previous.files.items():
            if path.startswith(("skills/", "flavors/", "workflows/", "routing/")):
                project.write(path, payload)
        # Remove the unrelated deliberately minimal inherited-Skill fixture;
        # this is an initialized Component with a genuine empty import catalog.
        (project.root / "skills/demo/SKILL.md").unlink()
        (project.root / "skills/demo").rmdir()
        project.imports = CatalogImportsFile(())
        project.write(
            "litai/.literate/imports.json",
            canonical_json_bytes(project.imports.to_dict()) + b"\n",
        )
        authored = resources.initialization._template_text(logical).encode()
        project.write(source, authored)
        for path, resource in resources.initialization._TEMPLATE_FILES.items():
            if path.startswith(
                ("flavors/os-macos/", "flavors/lang-python/", "flavors/os-base/")
            ):
                project.write(
                    path, resources.initialization._template_text(resource).encode()
                )
        project.definition = replace(
            project.definition,
            agent_skill="SKILL.md",
            component_roots=("samples", "litai/samples"),
            default_flavor_selectors=(
                "+flavor://literate-ai/os-macos",
                "+flavor://literate-ai/lang-python",
            ),
            flavor_roots=("flavors",),
            skill_roots=("skills",),
            workflow_roots=("workflows",),
            routing_roots=("routing",),
        )
        project.write(
            project.manifest, serialize_project_configuration(project.definition)
        )
        project.baseline = replace(
            project.baseline,
            files=tuple(
                sorted(
                    (
                        *project.baseline.files,
                        ProjectInitializationBaselineFile(
                            source,
                            len(authored),
                            ContentIdentity.parse_uri(support.identity(authored)),
                        ),
                    ),
                    key=lambda row: row.path,
                )
            ),
        )
        project.write(
            "litai/.literate/initialization-baseline.json",
            canonical_json_bytes(project.baseline.to_dict()) + b"\n",
        )
        bases = UpdateBases(project.root)
        bases.advance("framework", source, authored)
        if missing_historical:
            bases.advance(
                "framework",
                logical.removesuffix("/component.md") + "/deleted-history.md",
                b"original historical bytes",
            )
        project.write("litai/.literate/update-bases.json", bases.serialized())
        # The normal planner validates every declared catalog directory.
        (project.root / "litai/samples").mkdir(parents=True, exist_ok=True)
        if with_lock:
            update_component_lock(
                project.root / source.removesuffix("/component.md"),
                target_name="macos-host",
                # Ordinary planning consumes the project's declared defaults.
                flavor_selectors=(),
                flavor_roots=(project.root / "flavors",),
            )
        project.refresh()
        project.inventory["retained_implementation"] = None
        project.rehash()
        observed = ProjectLayoutObservation(
            project.snapshot,
            project.context,
            project.inventory,
            project.observations,
            project.contents,
            project.bases,
        )
        self.enterContext(
            patch.object(
                resources, "_read_current_origin", return_value=previous.origin
            )
        )
        owner = resources.observe_original_framework_resources(observed)
        proof = helper.prove(project, owner, logical=logical, source_path=source)
        return project, owner, proof

    def select(self, project, owner, proof, **changes):
        arguments = dict(
            resources=owner,
            source_proofs=(proof,),
            update_bases=project.bases,
            contents=project.contents,
            observations=project.observations,
            source_held=(),
        )
        arguments.update(changes)
        return capture.capture_initialized_framework_component_transitions(
            project.snapshot, project.context, **arguments
        )

    def test_empty_actual_producer_inventory_is_not_an_invented_target(self):
        project, resources_owner, proof = self.fixture()
        (selected,) = self.select(project, resources_owner, proof)
        transition.require_original_component_transition(selected)
        transition.require_current_component_transition(selected)
        self.assertEqual(selected.source_kind, "initialized")
        self.assertIs(selected.initialized_source, proof)
        self.assertIsNone(selected.imported_source)
        self.assertEqual(selected.target_names, ())
        self.assertEqual(dict(selected.records), {})

    def test_actual_typed_lock_and_audit_use_original_shared_core(self):
        project, owner, proof = self.fixture(with_lock=True)
        (selected,) = self.select(project, owner, proof)
        self.assertEqual(selected.target_names, ("macos-host",))
        self.assertEqual(
            {row["kind"] for row in selected.records.values()},
            {"ComponentLock", "ComponentResolutionAudit"},
        )
        for path in selected.records:
            self.assertEqual(selected.original_contents[path], project.contents[path])
        transition.require_current_component_transition(selected)

    def test_copied_proof_and_copied_resource_owner_refuse(self):
        project, owner, proof = self.fixture()
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(project, owner, copy.copy(proof))
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(project, copy.copy(owner), proof)

    def test_same_type_proof_from_other_original_resource_owner_refuses(self):
        first, owner, proof = self.fixture()
        _other, other_owner, _proof = self.fixture()
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(first, other_owner, proof)

    def test_original_source_file_and_native_directory_replacement_refuse(self):
        project, owner, proof = self.fixture()
        source = project.root / proof.source_path
        original = source.read_bytes()
        source.write_bytes(original + b"\nforeign\n")
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(project, owner, proof)
        source.write_bytes(original)
        directory = source.parent
        retired = directory.with_name("retained-original")
        directory.rename(retired)
        shutil.copytree(retired, directory)
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(project, owner, proof)

    def test_held_private_output_or_independent_child_is_never_opened(self):
        project, owner, proof = self.fixture()
        component = proof.source_path.removesuffix("/component.md")
        calls = []
        original_open = os.open
        for suffix, kind in (
            (".env", "private"),
            ("target", "output"),
            ("nested", "independent"),
        ):
            path = component + "/" + suffix
            row = {
                "path": path,
                "kind": kind,
                "reason": "unopened original scope",
                "source": False,
            }

            def observed(path_arg, *args, forbidden=path, **kwargs):
                if isinstance(path_arg, (str, os.PathLike)):
                    value = str(path_arg)
                    if value == str(project.root / forbidden) or value.startswith(
                        str(project.root / forbidden) + os.sep
                    ):
                        calls.append(value)
                        raise AssertionError("held target opened")
                return original_open(path_arg, *args, **kwargs)

            with patch.object(os, "open", observed):
                with self.assertRaisesRegex(ProjectLayoutPlanError, "held/unopened"):
                    self.select(project, owner, proof, source_held=(row,))
        self.assertEqual(calls, [])

    def test_unknown_private_child_after_observation_refuses_without_read(self):
        project, owner, proof = self.fixture()
        secret = project.root / proof.source_path.removesuffix("/component.md") / ".env"
        secret.write_bytes(b"modeled unopened private state")
        original_open = os.open
        reads = []

        def observed(path, *args, **kwargs):
            if isinstance(path, (str, os.PathLike)) and str(path) == str(secret):
                reads.append(path)
                raise AssertionError("unknown child read")
            return original_open(path, *args, **kwargs)

        with patch.object(os, "open", observed):
            with self.assertRaises(ProjectLayoutPlanError):
                self.select(project, owner, proof)
        self.assertEqual(reads, [])

    def test_missing_original_authored_member_or_extra_payload_refuses(self):
        project, owner, proof = self.fixture(missing_historical=True)
        with self.assertRaisesRegex(ProjectLayoutPlanError, "complete original"):
            self.select(project, owner, proof)
        project, owner, proof = self.fixture()
        extra = (
            project.root
            / proof.source_path.removesuffix("/component.md")
            / "unowned.md"
        )
        extra.write_bytes(b"not original initialized membership")
        with self.assertRaises(ProjectLayoutPlanError):
            self.select(project, owner, proof)

    def test_already_contained_component_returns_no_old_source_transition(self):
        project, owner, proof = self.fixture(contained=True)
        self.assertEqual(self.select(project, owner, proof), ())

    def test_original_native_oserror_preserved_as_same_primary_object(self):
        project, owner, proof = self.fixture()
        target = project.root / proof.source_path.removesuffix("/component.md")
        original = Path.lstat
        failure = OSError("original native source failure")

        def broken(path, *args, **kwargs):
            if path == target:
                raise failure
            return original(path, *args, **kwargs)

        with patch.object(Path, "lstat", broken):
            with self.assertRaises(OSError) as caught:
                self.select(project, owner, proof)
        self.assertIs(caught.exception, failure)
