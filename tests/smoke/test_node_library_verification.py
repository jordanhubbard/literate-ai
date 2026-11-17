"""Actual shared runtime/type checks on synthetic packages, not qualification."""

import os
import shutil
import unittest
from dataclasses import replace

from literate_ai.adapters.node_library_verification import check_node_library
from literate_ai.contracts import canonical_identity
from tests.smoke import test_node_library_acceptance as oracle_fixture
from tests.smoke import test_node_library_execution as runtime_fixture
from tests.smoke import test_node_library_projection as projection_fixture
from tests.smoke import test_node_sdk_typescript as compiler_fixture

_CJS_PROVIDER = (
    runtime_fixture._INPUT
    + """
const path=require('node:path');
const rows=input.cases.map(c=>{
 const cap=input.surface.capabilities.find(x=>x.capability===c.capability);
 const entry=input.surface.declarations.find(x=>x.module===cap.module);
 const library=require(path.join(input.artifact_root,entry.runtime));
 const result=library[cap.symbols.find(s=>s!=='CounterError')](...c.arguments);
 return {case_id:c.case_id,capability:c.capability,result};
});
process.stdout.write(JSON.stringify({schema:'literate-ai/library-acceptance-results@1',cases:rows}));
"""
)
_ESM_PROVIDER = """
import fs from 'node:fs';
import path from 'node:path';
import {pathToFileURL} from 'node:url';
const input=JSON.parse(fs.readFileSync(0,'utf8'));
const rows=[];
for(const c of input.cases){
 const cap=input.surface.capabilities.find(x=>x.capability===c.capability);
 const entry=input.surface.declarations.find(x=>x.module===cap.module);
 const url=pathToFileURL(path.join(input.artifact_root,entry.runtime)).href;
 const library=(await import(url)).default;
 const result=library[cap.symbols.find(s=>s!=='CounterError')](...c.arguments);
 rows.push({case_id:c.case_id,capability:c.capability,result});
}
process.stdout.write(JSON.stringify({schema:'literate-ai/library-acceptance-results@1',cases:rows}));
"""


@unittest.skipUnless(
    os.environ.get("LITERATE_TYPESCRIPT_SDK") and shutil.which("node"),
    "requires explicitly selected compiler fixture",
)
class NodeLibraryVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler_fixture.TypeScriptCompilerTests.setUpClass.__func__(cls)

    def setUp(self):
        self.runtime = runtime_fixture.NodeLibraryExecutionTests()
        self.runtime.setUp()
        self.addCleanup(self.runtime.doCleanups)
        self.runtime.node = self.node
        self.surface = self.runtime.surface
        symbol = self.runtime.fixture.symbol
        package = self.surface.package
        positive = (
            f"import {{CounterError,{symbol}}} from '{package}';"
            f"const value:number={symbol}(1,2);"
            "const error:Error=new CounterError('bad');"
        ).encode()
        negative = (f"import {{{symbol}}} from '{package}';{symbol}('bad',2);").encode()
        sources = (positive, negative, positive, negative)
        row = self.runtime.input.document["declaration_cases"][0]
        for field, source in zip(
            oracle_fixture.owner._SOURCE_FIELDS, sources, strict=True
        ):
            ref = row[field]
            (self.runtime.root / ref["path"]).write_bytes(source)
            ref["identity"] = oracle_fixture._sha(source)
        self.oracle = self.runtime.load()

    def check(self, **changes):
        arguments = dict(
            subject=self.runtime.fixture.fixture.consumer.component_revision,
            artifact=canonical_identity("synthetic SDK artifact"),
            surface=self.surface,
            files=self.runtime.plan.files,
            artifact_root=self.runtime.artifact_root,
            workspace=self.runtime.root / "verify",
            node=self.node,
            compiler=self.compiler,
            environment=self.environment,
            require_current=self.runtime.require_current,
            observe_process=self.runtime.observations.append,
        )
        oracle = changes.pop("oracle", self.oracle)
        return check_node_library(oracle, **dict(arguments, **changes))

    def test_original_oracle_joins_six_actual_type_children_and_both_runtimes(self):
        result = self.check()
        self.assertEqual(len(result.declarations.processes), 6)
        self.assertEqual(len(result.runtime.results), 2)
        self.assertEqual(len(self.runtime.observations), 8)
        self.assertEqual(result.oracle, self.oracle.identity)
        self.assertEqual(result.surface, self.surface.identity)
        self.assertEqual(result.runtime.oracle, result.oracle)
        self.assertTrue(result.identity.uri.startswith("sha256:"))

    def test_weakened_types_refuse_before_any_runtime_harness(self):
        symbols = self.surface.capabilities[0].symbols
        weak = "\n".join(
            f"export declare const {symbol}:any;" for symbol in symbols
        ).encode()
        files = tuple(
            replace(file, content=weak)
            if file.path in {"cjs/index.d.ts", "esm/index.d.ts"}
            else file
            for file in self.runtime.plan.files
        )
        for file in files:
            if file.content == weak:
                (self.runtime.artifact_root / file.path).write_bytes(file.content)
        with self.assertRaisesRegex(ValueError, "type errors"):
            self.check(files=files)
        self.assertFalse((self.runtime.root / "verify").exists())
        self.assertTrue(self.runtime.observations)

    def test_copied_oracle_or_unjoined_provider_cannot_start_any_child(self):
        for changes in (
            {"oracle": replace(self.oracle)},
            {"provider": self.runtime.fixture.artifact},
        ):
            with self.subTest(changes=tuple(changes)), self.assertRaises(ValueError):
                self.check(**changes)
        self.assertEqual(self.runtime.observations, [])
        self.assertFalse((self.runtime.root / "verify").exists())

    def test_ended_owner_after_type_child_cannot_reach_runtime(self):
        def observe(process):
            self.runtime.observations.append(process)
            self.runtime.current = False

        with self.assertRaisesRegex(ValueError, "owner ended"):
            self.check(observe_process=observe)
        self.assertEqual(len(self.runtime.observations), 1)
        self.assertFalse((self.runtime.root / "verify").exists())

    def test_commonjs_provider_joins_types_and_original_runtime_formats(self):
        fixture = projection_fixture.NodeLibraryProjectionTests()
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        provider = fixture.fixture.artifact
        surface = fixture.fixture.provider_contract.library_import_surface
        files = fixture.provider_files()
        symbol = fixture.fixture.symbol
        module = surface.capabilities[0].module
        positive = (
            f"import library = require('{module}');"
            f"const value:number=library.{symbol}(1,2);"
            "const error:Error=new library.CounterError('bad');"
        ).encode()
        negative = (
            f"import library = require('{module}');library.{symbol}('bad',2);"
        ).encode()
        document = self.runtime.input.document
        document["language"] = "javascript"
        document["import_surface_identity"] = surface.identity.uri
        document["cases"][0]["capability"] = surface.capabilities[0].capability
        row = document["declaration_cases"][0]
        row["capability"] = surface.capabilities[0].capability
        for field, source in zip(
            oracle_fixture.owner._SOURCE_FIELDS,
            (positive, negative, positive, negative),
            strict=True,
        ):
            ref = row[field]
            (self.runtime.root / ref["path"]).write_bytes(source)
            ref["identity"] = oracle_fixture._sha(source)
        oracle = self.runtime.load(cjs=_CJS_PROVIDER, esm=_ESM_PROVIDER)
        root = self.runtime.root / "original-provider"
        root.mkdir()
        for file in files:
            path = root / file.path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(file.content)
            path.chmod(file.mode)
        checked = self.check(
            oracle=oracle,
            subject=provider.component_revision,
            artifact=provider.identity,
            provider=provider,
            surface=surface,
            files=files,
            artifact_root=root,
            workspace=self.runtime.root / "verify-provider",
        )
        self.assertEqual(len(checked.declarations.processes), 6)
        self.assertEqual(len(checked.runtime.results), 2)
        self.assertEqual(len(self.runtime.observations), 8)
        self.assertEqual(checked.subject, provider.component_revision)
        self.assertEqual(checked.artifact, provider.identity)
