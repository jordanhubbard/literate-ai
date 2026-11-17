"""Real declaration checking over synthetic data, never lifecycle qualification."""

import os
import shutil
import unittest
from dataclasses import replace
from unittest.mock import patch

from literate_ai.adapters.directory_artifacts import DirectoryExportFile
from literate_ai.adapters.node_sdk_declarations import (
    NodeDeclarationCase,
    NodeDeclarationProjection,
    check_node_declarations,
)
from literate_ai.adapters.node_sdk_tools import NodeSDKToolProcess
from literate_ai.adapters.node_sdk_typescript import (
    NodeSDKTypeScriptCompiler,
    TypeScriptResult,
)
from literate_ai.contracts import canonical_identity
from tests.smoke import test_node_sdk_composition as composition_fixtures
from tests.smoke import test_node_sdk_typescript as compiler_fixtures


@unittest.skipUnless(
    os.environ.get("LITERATE_TYPESCRIPT_SDK") and shutil.which("node"),
    "requires explicitly selected compiler fixture",
)
class NodeDeclarationChecksTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        compiler_fixtures.TypeScriptCompilerTests.setUpClass.__func__(cls)

    def setUp(self):
        self.fixture = composition_fixtures.NodeSDKCompositionTests(
            "test_relocated_cjs_esm_root_subpath_and_error_identity"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        plan = self.fixture.prepare()
        surface = self.fixture.fixture.consumer.library_import_surface
        capability = surface.capabilities[0]
        prefix = "node_modules/counter-sdk/"
        declarations = sorted(
            {
                prefix + path
                for entry in surface.node_sdk_exports
                for path in (entry.paths[1], entry.paths[3])
            }
        )
        self.projection = NodeDeclarationProjection(
            self.fixture.fixture.consumer.identity,
            canonical_identity({"synthetic_artifact_plan": plan.identity.uri}),
            surface.identity,
            tuple(
                DirectoryExportFile(prefix + item.path, item.content, item.mode)
                for item in plan.files
            ),
            (
                (
                    capability.capability,
                    prefix + "cjs/index.d.ts",
                    prefix + "esm/index.d.ts",
                ),
            ),
            tuple((path, capability.symbols) for path in declarations),
        )
        symbol = self.fixture.symbol
        self.positive = (
            "import {CounterError," + symbol + "} from 'counter-sdk';"
            "import {" + symbol + " as other} from 'counter-sdk/counter';"
            "const n:number=" + symbol + "(2,3);const m:number=other(3,4);"
            "const error:Error=new CounterError('bad');"
        ).encode()
        self.negative = (
            "import {" + symbol + "} from 'counter-sdk';" + symbol + "('bad',3);"
        ).encode()
        self.case = NodeDeclarationCase(
            "numeric-api",
            capability.capability,
            self.positive,
            self.negative,
            self.positive,
            self.negative,
            (2345,),
        )

    def check(self, projection=None, cases=None, **kwargs):
        return check_node_declarations(
            self.projection if projection is None else projection,
            (self.case,) if cases is None else cases,
            compiler=self.compiler,
            environment=self.environment,
            require_current=kwargs.pop("require_current", lambda: None),
            **kwargs,
        )

    def test_real_each_format_and_mode_and_any_quality_controls(self):
        observations = []
        result = self.check(observe_process=observations.append)
        self.assertEqual(len(result.processes), 6)
        self.assertEqual(tuple(observations), result.processes)
        self.assertTrue(all(item.returncode == 0 for item in observations))
        self.assertTrue(all(item.input_identity is not None for item in observations))
        self.assertEqual(result.projection, self.projection.identity)
        self.assertEqual(result.compiler, self.compiler.identity)
        self.assertEqual(result.case_identities, (self.case.identity,))

    def test_already_any_typed_public_api_is_rejected(self):
        public = dict(self.projection.public_declarations)
        body = (
            "export declare const CounterError:any;export declare const "
            + self.fixture.symbol
            + ":any;"
        ).encode()
        weakened = replace(
            self.projection,
            files=tuple(
                DirectoryExportFile(item.path, body, item.mode)
                if item.path in public
                else item
                for item in self.projection.files
            ),
        )
        with self.assertRaisesRegex(ValueError, "expected type errors"):
            self.check(projection=weakened)

    def test_unrelated_negative_error_cannot_stand_in_for_api_types(self):
        unrelated = self.positive + b"const alwaysBad:number='unrelated';"
        case = replace(
            self.case,
            cjs_negative=unrelated,
            esm_negative=unrelated,
            diagnostic_codes=(2322,),
        )
        with self.assertRaisesRegex(ValueError, "does not distinguish"):
            self.check(cases=(case,))

    def test_one_format_cannot_supply_anothers_positive_coverage(self):
        case = replace(self.case, esm_positive=b"const value=42;")
        with self.assertRaisesRegex(ValueError, "positive.*exact public types"):
            self.check(cases=(case,))

    def test_one_resolution_mode_failure_is_insufficient(self):
        expected = self.projection.capabilities[0][1]
        modes = (("node16", (expected,)), ("nodenext", (expected,)))
        positive = TypeScriptResult(True, (), (expected,), (), modes)
        negative = TypeScriptResult(
            False,
            (
                {
                    "mode": "node16",
                    "code": 2345,
                    "category": 1,
                    "message": "synthetic incomplete mode",
                },
            ),
            (expected,),
            (),
            modes,
        )
        values = iter((positive, negative))

        def controlled(*_args, **kwargs):
            kwargs["observe_process"](
                NodeSDKToolProcess(
                    ("synthetic-unit-compiler",),
                    0,
                    b"controlled test data",
                    b"",
                    canonical_identity("synthetic input"),
                )
            )
            return next(values)

        with patch.object(
            NodeSDKTypeScriptCompiler, "run", side_effect=controlled
        ) as run:
            with self.assertRaisesRegex(ValueError, "both modes"):
                self.check()
            self.assertEqual(run.call_count, 2)

    def test_missing_capability_and_known_async_observer_precede_execution(self):
        async def observe(_value):
            raise AssertionError("must not run")

        with patch.object(NodeSDKTypeScriptCompiler, "run") as run:
            with self.assertRaisesRegex(ValueError, "every current capability"):
                self.check(cases=(replace(self.case, capability="another.api"),))
            with self.assertRaisesRegex(TypeError, "synchronous"):
                self.check(observe_process=observe)
            run.assert_not_called()

    def test_owner_cut_after_actual_observation_prevents_check_publication(self):
        active, observations = True, []

        def current():
            if not active:
                raise RuntimeError("declaration owner ended")

        def observe(value):
            nonlocal active
            observations.append(value)
            active = False

        with self.assertRaisesRegex(RuntimeError, "owner ended"):
            self.check(require_current=current, observe_process=observe)
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].returncode, 0)

    def test_positive_must_load_public_declaration_in_each_resolution_mode(self):
        expected = self.projection.capabilities[0][1]
        incomplete = TypeScriptResult(
            True,
            (),
            (expected,),
            (),
            (("node16", (expected,)), ("nodenext", ())),
        )

        def controlled(*_args, **kwargs):
            kwargs["observe_process"](
                NodeSDKToolProcess(
                    ("synthetic-unit-compiler",),
                    0,
                    b"controlled mode data",
                    b"",
                    canonical_identity("synthetic input"),
                )
            )
            return incomplete

        with patch.object(NodeSDKTypeScriptCompiler, "run", side_effect=controlled):
            with self.assertRaisesRegex(ValueError, "positive.*exact public types"):
                self.check()

    def test_independent_case_sources_cannot_suppress_diagnostics(self):
        for field in ("cjs_positive", "cjs_negative", "esm_positive", "esm_negative"):
            for directive in (b"@ts-nocheck", b"@ts-ignore", b"@ts-expect-error"):
                with (
                    self.subTest(field=field, directive=directive),
                    self.assertRaisesRegex(ValueError, "suppress"),
                ):
                    replace(
                        self.case,
                        **{
                            field: b"// "
                            + directive
                            + b"\n"
                            + getattr(self.case, field)
                        },
                    )

    def test_cumulative_evidence_bound_precedes_retention_or_forwarding(self):
        observations = []
        with patch("literate_ai.adapters.node_sdk_declarations._MAX_PROCESS_BYTES", 1):
            with self.assertRaisesRegex(ValueError, "observation byte bound"):
                self.check(observe_process=observations.append)
        self.assertFalse(observations)
