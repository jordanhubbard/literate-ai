"""Actual input join and publication files around explicit provider admission.

The maintained provider contract fixture is injected. The test adapter adds
actual read-only publication file custody; no all-run semantic replay, model,
native execution or completed consumer admission is qualified here.
"""

import copy
import pickle
import unittest
from contextlib import contextmanager
from unittest.mock import patch

from literate_ai.adapters import authored_retained_cargo_inputs as inputs
from literate_ai.adapters import authored_retained_cargo_products as products
from literate_ai.adapters.authored_publication_files import AuthoredPublicationFiles
from literate_ai.adapters.authored_qualification_planning import (
    CurrentAuthoredQualificationPlan,
)
from literate_ai.adapters.builders.cargo import CargoToolchain
from literate_ai.projects import PinnedInputClosureError
from tests.critical import test_authored_retained_cargo_inputs as joins


class AuthoredInputSessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        joins.AuthoredRetainedCargoInputsTests.setUpClass()

    @contextmanager
    def fixture(self):
        helper = joins.AuthoredRetainedCargoInputsTests("runTest")
        with helper.fixture() as (root, binding, args, provider_state, _provider_file):
            current = args["provider_current"]
            provider_root = current.oracles.authority.project.root
            relative = current.plan.output_root + "/fixture-publication.json"
            path = provider_root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b'{"explicit_provider_contract_fixture":true}')
            retired = path.with_name("fixture-retired")
            public_products = inputs.open_authored_retained_cargo_products
            state = {"yielded": False, "mutated": False, "path": path}

            @contextmanager
            def private_products(actual, selected, **kwargs):
                with public_products(actual, selected, **kwargs) as owner:
                    with AuthoredPublicationFiles(actual, writable=False) as files:
                        metadata = products._PinnedPublicationMetadata(files)
                        metadata.read(relative, max_bytes=products.METADATA_BYTES)
                        publication = products._capture_original_authored_publication(
                            metadata, (retired,)
                        )
                        original = products._AuthoredRetainedCargoProductsSession(
                            owner, publication, products._PUBLICATION_COMPLETION_KEY
                        )
                        state["original"] = original
                        state["yielded"] = True
                        yield original
                        publication.require_original_files()

            with patch.object(
                inputs,
                "_open_authored_retained_cargo_products_session",
                side_effect=private_products,
            ):
                yield root, binding, args, provider_state, state

    def test_actual_original_product_session_is_forwarded_and_public_owners_expire(
        self,
    ):
        with self.fixture() as (root, binding, args, provider_state, state):
            with inputs._open_authored_retained_cargo_inputs_session(
                root, **args
            ) as session:
                self.assertIs(session.products_session, state["original"])
                self.assertIs(session.inputs.products, state["original"].products)
                self.assertEqual(session.inputs.reviewed.binding, binding)
                session.inputs.require_unchanged()
            self.assertTrue(provider_state["closed"])
            with self.assertRaisesRegex(ValueError, "input-owner-expired"):
                session.inputs.require_unchanged()
            with self.assertRaises(ValueError):
                session.products_session.products.require_unchanged()
            trap = AssertionError(
                "original publication comparison invoked expired authority"
            )
            with (
                patch.object(AuthoredPublicationFiles, "read", side_effect=trap),
                patch.object(
                    AuthoredPublicationFiles, "require_current", side_effect=trap
                ),
                patch.object(
                    CurrentAuthoredQualificationPlan,
                    "require_unchanged",
                    side_effect=trap,
                ),
                patch("subprocess.run", side_effect=trap),
                patch("subprocess.Popen", side_effect=trap),
            ):
                session.products_session.publication.require_original_files()
            for operation in (copy.copy, copy.deepcopy, pickle.dumps):
                with self.subTest(operation=operation.__name__):
                    with self.assertRaises(TypeError):
                        operation(session)

    def test_actual_consumer_tool_callback_mutation_cannot_yield_input_session(self):
        with self.fixture() as (root, _binding, args, provider_state, state):
            path = state["path"]
            changed = path.read_bytes() + b" "
            actual = CargoToolchain.require_unchanged

            def late(tool):
                result = actual(tool)
                if (
                    tool is args["consumer_cargo"]
                    and state["yielded"]
                    and not state["mutated"]
                ):
                    path.write_bytes(changed)
                    state["mutated"] = True
                return result

            with patch.object(CargoToolchain, "require_unchanged", new=late):
                with self.assertRaises(PinnedInputClosureError):
                    with inputs._open_authored_retained_cargo_inputs_session(
                        root, **args
                    ):
                        self.fail(
                            "changed original publication yielded usable input session"
                        )
            self.assertTrue(state["mutated"])
            self.assertTrue(provider_state["closed"])
            self.assertEqual(path.read_bytes(), changed)
