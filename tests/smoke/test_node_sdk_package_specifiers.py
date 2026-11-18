"""Actual bare root/subpath imports, separate from lifecycle admission proof."""

import os
import shutil
import unittest
from dataclasses import replace
from unittest import mock

from literate_ai.adapters.directory_artifacts import (
    DirectoryExportFile,
    require_materialized_files,
)
from literate_ai.adapters.node_library_projection import project_node_sdk_declarations
from literate_ai.contracts import canonical_identity
from tests.smoke import test_node_library_execution as runtime_fixture

_CJS = (
    runtime_fixture._INPUT
    + """
const path=require('node:path');
const manifest=path.join(input.artifact_root,'package.json');
const req=require('node:module').createRequire(manifest);
const rows=input.cases.map(c=>{
 const cap=input.surface.capabilities.find(x=>x.capability===c.capability);
 const symbol=cap.symbols.find(s=>s!=='CounterError');
 const values=input.surface.node_sdk_exports.map(entry=>{
  const resolved=fs.realpathSync(req.resolve(entry.module));
  if(!resolved.startsWith(fs.realpathSync(input.artifact_root)+path.sep))
   throw Error('CJS package resolved outside original artifact');
  return req(entry.module)[symbol](...c.arguments);
 });
 if(values.some(value=>JSON.stringify(value)!==JSON.stringify(values[0])))
  throw Error('CJS root/subpath values differ');
 return {case_id:c.case_id,capability:c.capability,result:values[0]};
});
process.stdout.write(JSON.stringify({schema:'literate-ai/library-acceptance-results@1',cases:rows}));
"""
)
_ESM = """
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
if(input.schema!=='literate-ai/node-library-harness-input@1')throw Error('input');
const workspace=fs.realpathSync(path.dirname(fileURLToPath(import.meta.url)));
const rows=[];
for(const c of input.cases){
 const cap=input.surface.capabilities.find(x=>x.capability===c.capability);
 const symbol=cap.symbols.find(s=>s!=='CounterError');
 const values=[];
 for(const entry of input.surface.node_sdk_exports){
  const resolved=fs.realpathSync(fileURLToPath(import.meta.resolve(entry.module)));
  if(!resolved.startsWith(workspace+path.sep))
   throw Error('ESM package resolved outside owned verifier namespace');
  const lib=await import(entry.module);
  values.push(lib[symbol](...c.arguments));
 }
 if(values.some(value=>JSON.stringify(value)!==JSON.stringify(values[0])))
  throw Error('ESM root/subpath values differ');
 rows.push({case_id:c.case_id,capability:c.capability,result:values[0]});
}
process.stdout.write(JSON.stringify({schema:'literate-ai/library-acceptance-results@1',cases:rows}));
"""


@unittest.skipUnless(shutil.which("node"), "requires available Node")
class NodeSDKPackageSpecifierTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture = runtime_fixture.NodeLibraryExecutionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        self.namespace = project_node_sdk_declarations(
            subject=canonical_identity("runtime namespace fixture"),
            artifact=canonical_identity("separately admitted synthetic artifact"),
            surface=fixture.surface,
            files=fixture.plan.files,
        ).files
        self.oracle = fixture.load(cjs=_CJS, esm=_ESM)

    @unittest.skipUnless(os.name == "posix", "requires live namespace custody")
    def test_bare_cjs_esm_root_and_subpath_imports_use_original_sdk(self):
        fixture = self.fixture
        self.assertEqual(
            {entry.module for entry in fixture.surface.node_sdk_exports},
            {"counter-sdk", "counter-sdk/counter"},
        )
        result = fixture.check(self.oracle, namespace_files=self.namespace)
        self.assertEqual(
            tuple(mode for mode, _ in result.results), ("commonjs", "module")
        )
        self.assertEqual(len(fixture.observations), 2)
        self.assertIsNotNone(result.namespace)
        self.assertEqual(
            fixture.observations[0].input_identity,
            fixture.observations[1].input_identity,
        )
        require_materialized_files(fixture.artifact_root, fixture.plan.files)

    def test_legacy_direct_runtime_identity_remains_unchanged(self):
        fixture = self.fixture
        oracle = fixture.load()
        result = fixture.check(oracle)
        self.assertIsNone(result.namespace)
        self.assertEqual(
            result.identity,
            canonical_identity(
                {
                    "schema": "literate-ai/node-library-runtime-checks@1",
                    "oracle": result.oracle.uri,
                    "artifact": result.artifact.uri,
                    "surface": result.surface.uri,
                    "node": result.node.uri,
                    "results": [
                        [mode, identity.uri] for mode, identity in result.results
                    ],
                }
            ),
        )

    @unittest.skipUnless(os.name == "posix", "requires live namespace custody")
    def test_actual_sdk_checker_denies_ambient_producer_environment(self):
        fixture = self.fixture
        oracle = fixture.load(
            cjs=(
                "if(Object.keys(process.env).some(k=>k.toUpperCase().startsWith("
                "'LITAI_PROVIDER_')))"
                "throw Error('ambient producer path reached SDK');\n" + _CJS
            ),
            esm=_ESM,
        )
        with mock.patch.dict(
            os.environ, {"LiTai_PrOvIdEr_fixture": str(fixture.root / "producer")}
        ):
            fixture.check(oracle, namespace_files=self.namespace)
        self.assertEqual(len(fixture.observations), 2)
        self.assertTrue(all(row.returncode == 0 for row in fixture.observations))

    def test_bare_esm_without_supplied_namespace_refuses(self):
        fixture = self.fixture
        with self.assertRaisesRegex(ValueError, "runtime harness failed"):
            fixture.check(self.oracle)
        self.assertEqual(len(fixture.observations), 2)
        self.assertIn(b"ERR_MODULE_NOT_FOUND", fixture.observations[-1].stderr)

    def test_unsupported_namespace_custody_refuses_before_stage_or_child(self):
        fixture = self.fixture
        with mock.patch("literate_ai.adapters.node_library_execution.os.name", "nt"):
            with self.assertRaisesRegex(ValueError, "POSIX"):
                fixture.check(self.oracle, namespace_files=self.namespace)
        self.assertFalse((fixture.root / "verify").exists())
        self.assertEqual(fixture.observations, [])

    @unittest.skipUnless(os.name == "posix", "requires live namespace custody")
    def test_namespace_inventory_and_harness_collisions_refuse_before_stage(self):
        fixture = self.fixture
        data = b"x" * (12 * 1024 * 1024)
        for namespace in (
            (DirectoryExportFile("harness.cjs", b"x", 0o644),),
            (DirectoryExportFile("harness.mjs/child", b"x", 0o644),),
            (DirectoryExportFile("../outside", b"x", 0o644),),
            (DirectoryExportFile("node_modules/a", b"x", "644"),),
            tuple(
                DirectoryExportFile("node_modules/a/f" + str(i), b"x", 0o644)
                for i in range(4095)
            ),
            tuple(
                DirectoryExportFile("node_modules/a/f" + str(i), data, 0o644)
                for i in range(3)
            ),
        ):
            with self.assertRaises((TypeError, ValueError)):
                fixture.check(self.oracle, namespace_files=namespace)
            self.assertFalse((fixture.root / "verify").exists())
            self.assertEqual(fixture.observations, [])

    @unittest.skipUnless(os.name == "posix", "requires live namespace custody")
    def test_native_esm_export_map_refuses_broken_public_subpath(self):
        import json

        fixture = self.fixture
        namespace = []
        for item in self.namespace:
            if item.path == "node_modules/counter-sdk/package.json":
                manifest = json.loads(item.content)
                del manifest["exports"]["./counter"]
                item = replace(item, content=json.dumps(manifest).encode())
            namespace.append(item)
        with self.assertRaisesRegex(ValueError, "runtime harness failed"):
            fixture.check(self.oracle, namespace_files=tuple(namespace))
        self.assertEqual(len(fixture.observations), 2)
        self.assertEqual(fixture.observations[0].returncode, 0)
        self.assertIn(b"ERR_PACKAGE_PATH_NOT_EXPORTED", fixture.observations[1].stderr)
        require_materialized_files(fixture.artifact_root, fixture.plan.files)

    @unittest.skipUnless(os.name == "posix", "requires live namespace custody")
    def test_observer_same_byte_namespace_rewrite_cannot_reach_second_child(self):
        fixture = self.fixture
        changed = []

        def observer(process):
            fixture.observations.append(process)
            path = fixture.root / "verify/node_modules/counter-sdk/esm/index.js"
            before = path.stat()
            path.write_bytes(path.read_bytes())
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            changed.append(True)

        with self.assertRaisesRegex(ValueError, "changed before inventory close"):
            fixture.check(
                self.oracle, namespace_files=self.namespace, observe_process=observer
            )
        self.assertEqual(changed, [True])
        self.assertEqual(len(fixture.observations), 1)

    @unittest.skipUnless(os.name == "posix", "requires live namespace custody")
    def test_owner_cannot_replace_first_staged_file_before_baseline(self):
        fixture = self.fixture
        changed = []

        def owner():
            fixture.require_current()
            path = fixture.root / "verify/harness.cjs"
            if path.exists() and not changed:
                before = path.stat()
                path.write_bytes(path.read_bytes())
                os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
                changed.append(True)

        with self.assertRaisesRegex(ValueError, "changed before inventory close"):
            fixture.check(
                self.oracle, namespace_files=self.namespace, require_current=owner
            )
        self.assertEqual(changed, [True])
        self.assertEqual(fixture.observations, [])

    @unittest.skipUnless(os.name == "posix", "requires live namespace custody")
    def test_original_namespace_survives_outer_oracle_exit_cut(self):
        from contextlib import contextmanager

        from literate_ai.adapters import node_library_execution as owner

        fixture = self.fixture
        original_capture = owner.capture_loaded_node_library_verifier_inputs
        changed = []

        @contextmanager
        def capture(oracle):
            with original_capture(oracle) as scope:
                yield scope
            path = fixture.root / "verify/node_modules/counter-sdk/esm/index.js"
            before = path.stat()
            path.write_bytes(path.read_bytes())
            os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns))
            changed.append(True)

        with mock.patch.object(
            owner, "capture_loaded_node_library_verifier_inputs", capture
        ):
            with self.assertRaisesRegex(ValueError, "changed before inventory close"):
                fixture.check(self.oracle, namespace_files=self.namespace)
        self.assertEqual(changed, [True])
        self.assertEqual(len(fixture.observations), 2)

    @unittest.skipUnless(os.name == "posix", "requires live namespace custody")
    def test_namespace_primitives_snapshot_before_owner_callback(self):
        fixture = self.fixture
        baseline = fixture.check(self.oracle, namespace_files=self.namespace)
        target = next(
            row for row in self.namespace if row.path.endswith("/esm/index.js")
        )
        original_content = target.content
        changed = []

        def owner():
            fixture.require_current()
            if not changed:
                object.__setattr__(target, "content", b"export const add=()=>999;\n")
                changed.append(True)

        result = fixture.check(
            self.oracle,
            workspace=fixture.root / "second-verify",
            namespace_files=self.namespace,
            require_current=owner,
        )
        self.assertEqual(changed, [True])
        self.assertEqual(result.namespace, baseline.namespace)
        self.assertEqual(
            (fixture.root / "second-verify" / target.path).read_bytes(),
            original_content,
        )
