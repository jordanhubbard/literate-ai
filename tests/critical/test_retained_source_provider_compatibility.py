"""Cargo compatibility dispatch and unchanged source-provider rejection semantics."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from literate_ai.adapters import retained_cargo_plan as cargo
from literate_ai.adapters import retained_source_provider as neutral
from literate_ai.contracts.identity import canonical_identity


class RetainedSourceProviderCompatibilityTests(unittest.TestCase):
    def test_old_cargo_signature_forwards_exact_objects_and_default_shapes(self):
        objects = [object() for _ in range(6)]
        binding, authority, promotion, closure, verifier, policy = objects
        with patch.object(cargo, "verify_current_retained_source_provider") as shared:
            cargo._verify_retained_cargo_provider(
                binding,
                authority,
                promotion,
                current_generation_closure=closure,
                current_verifier_identity=verifier,
                current_policy_identity=policy,
            )
        self.assertEqual(shared.call_args.args, (binding, authority, promotion))
        self.assertEqual(
            shared.call_args.kwargs,
            {
                "current_generation_closure": closure,
                "current_verifier_identity": verifier,
                "current_policy_identity": policy,
            },
        )

    def test_original_provider_run_and_revision_checks_follow_full_promotion(self):
        i = canonical_identity
        run = i("run")
        q, v, p = i("qualification"), i("verifier"), i("policy")
        binding = SimpleNamespace(
            qualification_identity=q,
            verifier_identity=v,
            policy_identity=p,
            run_identity=run,
            exports=SimpleNamespace(
                link_plan=SimpleNamespace(resolved_root_artifact_identities=()),
                libraries=(),
            ),
        )
        promotion = SimpleNamespace(
            qualification_lifecycle_result=SimpleNamespace(
                runs=(SimpleNamespace(run_identity=run),)
            )
        )
        closure = SimpleNamespace(qualification_evidence_identity=q)
        with patch.object(neutral, "verify_qualified_locked_source_promotion") as old:
            options = dict(
                current_generation_closure=closure,
                current_verifier_identity=v,
                current_policy_identity=p,
            )
            neutral.verify_current_retained_source_provider(
                binding, object(), promotion, **options
            )
            self.assertEqual(old.call_count, 1)
            binding.run_identity = i("foreign")
            with self.assertRaisesRegex(ValueError, "provider-run-mismatch"):
                neutral.verify_current_retained_source_provider(
                    binding, object(), promotion, **options
                )
            self.assertEqual(old.call_count, 2)
