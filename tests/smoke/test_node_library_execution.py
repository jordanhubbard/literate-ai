"""Actual two-format harness children, not public lifecycle qualification."""

import os
import shutil
import unittest
from dataclasses import replace
from unittest import mock

from literate_ai.adapters.builders.javascript import discover_node_toolchain
from literate_ai.adapters.builders.python import BuildError
from literate_ai.adapters.directory_artifacts import require_materialized_files
from literate_ai.adapters.node_library_acceptance import load_node_library_acceptance
from literate_ai.adapters.node_library_execution import check_node_library_runtime
from literate_ai.contracts import canonical_identity
from tests.smoke import test_node_library_acceptance as oracle_fixture
from tests.smoke import test_node_sdk_composition as composition_fixture

_INPUT = """
const fs = require('node:fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
if(input.schema !== 'literate-ai/node-library-harness-input@1') throw Error('input');
if(input.cases.some(c => Object.hasOwn(c, 'expected_result'))) throw Error('answers');
"""
_CJS = (
    _INPUT
    + """
const manifest = require('node:path').join(input.artifact_root, 'package.json');
const req = require('node:module').createRequire(manifest);
const rows = input.cases.map(c => {
 const cap=input.surface.capabilities.find(x=>x.capability===c.capability);
 const lib=req(cap.module);
 const result=lib[cap.symbols.find(s=>s!=='CounterError')](...c.arguments);
 return {case_id:c.case_id,capability:c.capability,result};
});
process.stdout.write(JSON.stringify({schema:'literate-ai/library-acceptance-results@1',cases:rows}));
"""
)
_ESM = """
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
if(input.schema !== 'literate-ai/node-library-harness-input@1') throw Error('input');
const rows=[];
for(const c of input.cases) {
 const cap=input.surface.capabilities.find(x=>x.capability===c.capability);
 const entry=input.surface.node_sdk_exports.find(x=>x.module===cap.module);
 const url=pathToFileURL(path.join(input.artifact_root,entry.import.runtime)).href;
 const lib=await import(url);
 const result=lib[cap.symbols.find(s=>s!=='CounterError')](...c.arguments);
 rows.push({case_id:c.case_id,capability:c.capability,result});
}
process.stdout.write(JSON.stringify({schema:'literate-ai/library-acceptance-results@1',cases:rows}));
"""


@unittest.skipUnless(shutil.which("node"), "requires explicitly available Node")
class NodeLibraryExecutionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = composition_fixture.NodeSDKCompositionTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.input = oracle_fixture.NodeLibraryOracleTests()
        self.input.setUp()
        self.addCleanup(self.input.doCleanups)
        self.root = self.input.root
        self.plan = self.fixture.prepare()
        self.surface = self.fixture.fixture.consumer.library_import_surface
        self.artifact_root = self.root / "sdk"
        # Authored synthetic runtime input, independent of the SDK projection
        # owner's stronger platform-specific publication boundary.
        self.artifact_root.mkdir()
        for row in self.plan.files:
            path = self.artifact_root / row.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(row.content)
            path.chmod(row.mode)
        self.node = discover_node_toolchain(environment=dict(os.environ))
        capability = self.surface.capabilities[0].capability
        self.input.document["import_surface_identity"] = self.surface.identity.uri
        self.input.document["cases"][0]["capability"] = capability
        self.input.document["declaration_cases"][0]["capability"] = capability
        self.observations = []
        self.current = True

    def load(self, *, cjs=_CJS, esm=_ESM):
        for name, content, field in (
            ("runtime.cjs", cjs, "harness_identity"),
            ("runtime.mjs", esm, "esm_harness_identity"),
        ):
            encoded = content.encode()
            (self.root / name).write_bytes(encoded)
            self.input.document[field] = oracle_fixture._sha(encoded)
        self.input.write_document()
        return load_node_library_acceptance(self.input.path, "counter")

    def require_current(self):
        if not self.current:
            raise ValueError("live execution owner ended")

    def check(self, oracle, **changes):
        arguments = dict(
            node=self.node,
            artifact=canonical_identity("separately admitted synthetic artifact"),
            surface=self.surface,
            files=self.plan.files,
            artifact_root=self.artifact_root,
            workspace=self.root / "verify",
            environment=dict(os.environ),
            require_current=self.require_current,
            observe_process=self.observations.append,
        )
        return check_node_library_runtime(oracle, **dict(arguments, **changes))

    def test_actual_cjs_and_esm_children_share_exact_original_inputs(self):
        oracle = self.load()
        result = self.check(oracle)
        self.assertEqual(
            tuple(mode for mode, _ in result.results), ("commonjs", "module")
        )
        self.assertEqual(len(self.observations), 2)
        self.assertEqual(
            self.observations[0].input_identity, self.observations[1].input_identity
        )
        self.assertEqual(result.oracle, oracle.identity)
        self.assertEqual(result.surface, self.surface.identity)
        self.assertEqual(result.node.uri, self.node.identity)
        self.assertTrue(result.identity.uri.startswith("sha256:"))
        require_materialized_files(self.artifact_root, self.plan.files)

    def test_both_formats_must_return_exact_results(self):
        wrong = _ESM.replace(
            "const result=lib[cap.symbols.find(s=>s!=='CounterError')]"
            "(...c.arguments);",
            "const result=999;",
        )
        oracle = self.load(esm=wrong)
        with self.assertRaisesRegex(ValueError, "result differs"):
            self.check(oracle)
        self.assertEqual(len(self.observations), 2)
        self.assertTrue((self.root / "verify/harness.mjs").is_file())

    def test_original_instance_required_before_stage_or_child(self):
        oracle = self.load()
        with self.assertRaises(ValueError):
            self.check(replace(oracle))
        self.assertFalse((self.root / "verify").exists())
        self.assertEqual(self.observations, [])

    def test_owner_cut_after_first_child_prevents_second_child(self):
        def observe(process):
            self.observations.append(process)
            self.current = False

        with self.assertRaisesRegex(ValueError, "owner ended"):
            self.check(self.load(), observe_process=observe)
        self.assertEqual(len(self.observations), 1)

    def test_owner_cut_before_execution_leaves_no_stage_or_child(self):
        oracle = self.load()
        self.current = False
        with self.assertRaisesRegex(ValueError, "owner ended"):
            self.check(oracle)
        self.assertFalse((self.root / "verify").exists())
        self.assertEqual(self.observations, [])

    def test_transient_original_harness_substitution_cannot_reach_staged_child(self):
        oracle = self.load()
        original = oracle.harness_content
        marker = self.root / "substituted-harness-executed"
        injected = (
            "require('node:fs').writeFileSync(" + repr(str(marker)) + ",'executed');\n"
        ).encode() + original
        calls = 0

        def require_current():
            nonlocal calls
            calls += 1
            if calls == 2:
                # Exactly the pre-stage callback: the old runner copied this
                # transient replacement, then validated it against itself.
                object.__setattr__(oracle, "harness_content", injected)
            elif calls == 3:
                object.__setattr__(oracle, "harness_content", original)

        result = self.check(oracle, require_current=require_current)
        self.assertEqual(len(result.results), 2)
        self.assertGreaterEqual(calls, 3)
        self.assertFalse(marker.exists())
        self.assertEqual((self.root / "verify/harness.cjs").read_bytes(), original)

    def test_observer_cannot_mutate_oracle_files(self):
        oracle = self.load()

        def observe(process):
            self.observations.append(process)
            (self.root / "runtime.mjs").write_bytes(b"substitute")

        with self.assertRaisesRegex(ValueError, "inputs changed"):
            self.check(oracle, observe_process=observe)
        self.assertEqual(len(self.observations), 1)

    def test_observer_cannot_add_untracked_stage_files(self):
        def observe(process):
            self.observations.append(process)
            (self.root / "verify/extra").write_bytes(b"unexpected")

        with self.assertRaisesRegex(ValueError, "foreign file"):
            self.check(self.load(), observe_process=observe)
        self.assertEqual(len(self.observations), 1)

    def test_ambient_node_controls_cannot_preload_another_module(self):
        environment = dict(os.environ, NODE_OPTIONS="--require=/missing/preloader.cjs")
        environment["NODE_PATH"] = str(self.root / "unadmitted")
        result = self.check(self.load(), environment=environment)
        self.assertEqual(len(result.results), 2)

    def test_actual_child_cannot_mutate_complete_artifact(self):
        cjs = (
            _INPUT + "const license=require('node:path')"
            ".join(input.artifact_root,'LICENSE');\n"
            + "fs.appendFileSync(license,'changed');\n"
            + _CJS[len(_INPUT) :]
        )
        with self.assertRaisesRegex(ValueError, "bytes differ"):
            self.check(self.load(cjs=cjs))
        self.assertTrue((self.root / "verify/harness.cjs").is_file())
        self.assertEqual(self.observations, [])

    def test_actual_child_output_is_bounded(self):
        cjs = _INPUT + "process.stdout.write('x'.repeat(2*1024*1024+1));"
        with self.assertRaisesRegex(BuildError, "stdout|output"):
            self.check(self.load(cjs=cjs))
        self.assertEqual(self.observations, [])

    def test_async_observer_and_reused_or_nested_stage_refused(self):
        oracle = self.load()

        async def asynchronous(_process):
            self.fail("invalid observer executed")

        with mock.patch(
            "literate_ai.adapters.node_library_execution.run_bounded_process"
        ) as process:
            with self.assertRaises(TypeError):
                self.check(oracle, observe_process=asynchronous)
            process.assert_not_called()
        self.assertFalse((self.root / "verify").exists())
        with self.assertRaisesRegex(ValueError, "outside"):
            self.check(oracle, workspace=self.artifact_root / "verify")
        (self.root / "verify").mkdir()
        with self.assertRaises(FileExistsError):
            self.check(oracle)
        self.assertEqual(self.observations, [])
