"""Durable original state must precede the first canonical public mutation.

The acknowledged plan is the first persistence prerequisite. Complete original
namespace/partition payloads and fresh recovery admission remain required too.
"""

from __future__ import annotations

import copy
import hashlib
import os
import unittest
from dataclasses import replace
from pathlib import Path
from unittest import mock

import tests.critical.test_retained_layout_source_admission as fixtures
from literate_ai.adapters import retained_layout_control_publication as publications
from literate_ai.adapters import retained_layout_source_state as state
from literate_ai.adapters.exclusive_entry import _from_stat
from literate_ai.adapters.retained_layout_journal import (
    LayoutJournalBudget,
    retained_layout_journal,
)
from literate_ai.contracts.identity import canonical_json_bytes


@unittest.skipUnless(os.name == "posix", "actual canonical publication boundary")
class SourceStatePersistenceTests(unittest.TestCase):
    git = fixtures.SourceAdmissionTests.git
    init_git = fixtures.SourceAdmissionTests.init_git
    prepare = fixtures.SourceAdmissionTests.prepare
    pool = fixtures.SourceAdmissionTests.pool

    @classmethod
    def setUpClass(cls):
        fixtures.SourceAdmissionTests.setUpClass.__func__(cls)

    def setUp(self):
        fixtures.SourceAdmissionTests.setUp(self)
        self.input_budget = replace(self.input_budget, maximum_entries=131072)

    def test_acknowledged_plan_is_durable_before_first_canonical_publication(self):
        class PublicationObserved(Exception):
            pass

        before = sorted(self.project.rglob("*"))
        observed = []
        with self.assertRaises(PublicationObserved):
            with self.prepare() as owner:
                plan = owner.plan
                expected = canonical_json_bytes(plan.document)
                digest = plan.identity.digest
                with self.pool(plan) as (pool, journal):

                    def before_publication(_source, destination, **_kwargs):
                        self.assertTrue(Path(destination).is_relative_to(self.project))
                        self.assertEqual(publications._publication_history(pool), ())
                        observed.append(Path(destination))
                        try:
                            raw = journal.read_payload(digest)
                        except ValueError as error:
                            self.fail(
                                "acknowledged source plan unavailable before "
                                f"first canonical publication: {error}"
                            )
                        self.assertEqual(raw, expected)
                        # Stop at the real native publication boundary without
                        # inventing a control lease or publishing any node.
                        raise PublicationObserved()

                    with mock.patch.object(
                        publications,
                        "move_layout_entry_exclusive",
                        side_effect=before_publication,
                    ):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=plan.identity,
                            allow_host_execution=True,
                        ):
                            self.fail("publication boundary was not observed")
        self.assertEqual(len(observed), 1)
        self.assertEqual(sorted(self.project.rglob("*")), before)
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def read_state(self, journal, phase):
        return state._read_original_state(
            journal,
            phase,
            budget=self.input_budget,
            maximum_metadata_bytes=self.metadata_limit,
        )

    def test_repeated_raw_metadata_chunks_survive_actual_journal_reopening(self):
        from literate_ai.adapters.component_locks import ComponentLockStore

        metadata = ComponentLockStore(self.source.parent).path
        original = metadata.read_bytes() + b" " * (3 * 1024**2)
        metadata.write_bytes(original)
        digest = hashlib.sha256(original).hexdigest()
        observed = []

        def check(_owner, plan, journal):
            snapshot = self.read_state(journal, plan.identity.uri)
            roster = snapshot.document["byte_witnesses"]["chunks"]
            repeated = {value for value in roster if roster.count(value) > 1}
            self.assertTrue(repeated, "fixture must produce repeated full chunks")
            for value in repeated:
                self.assertEqual(list(journal._known).count(f"p-{value}.bin"), 1)
            self.assertEqual(snapshot.body(digest), original)
            observed.append(tuple(roster))

        self.stop_at_first_publication(check)
        with self.reopen() as journal:
            snapshot = self.read_state(journal, self.saved_phase)
            self.assertEqual(
                tuple(snapshot.document["byte_witnesses"]["chunks"]), observed[0]
            )
            self.assertEqual(snapshot.body(digest), original)
        self.assertEqual(metadata.read_bytes(), original)

    def test_repeated_chunks_cannot_claim_expansion_beyond_original_storage(self):
        originals, descriptions = [], []

        def collect(_owner, plan, journal):
            descriptions.append(
                copy.deepcopy(self.read_state(journal, plan.identity.uri).document)
            )
            originals.extend(
                body
                for name, (_node, body) in journal._known.items()
                if name.startswith("p-")
            )

        self.stop_at_first_publication(collect)
        document = descriptions[0]
        witnesses = document["byte_witnesses"]
        digest = witnesses["chunks"][0]
        ceiling = self.saved_budget.maximum_payload_bytes
        witnesses["size"] = self.saved_budget.maximum_storage_bytes + 1
        witnesses["chunks"] = [digest] * ((witnesses["size"] + ceiling - 1) // ceiling)
        path = self.state / "oversized-expansion-journal"
        with retained_layout_journal(
            path, canonical_binding=self.saved_binding, budget=self.saved_budget
        ) as journal:
            for body in originals:
                journal.store_payload(body)
            state_digest = journal.store_payload(canonical_json_bytes(document))
            journal.append(
                "source-original-state-durable",
                canonical_json_bytes(
                    {
                        "source_phase_identity": self.saved_phase,
                        "state_payload_digest": state_digest,
                        "grants_move_authority": False,
                    }
                ),
            )
        with retained_layout_journal(
            path,
            canonical_binding=self.saved_binding,
            budget=self.saved_budget,
            recover=True,
        ) as journal:
            with self.assertRaisesRegex(
                ValueError,
                "^layout.original-state: original byte chunk roster "
                "exceeds its finite packing policy$",
            ):
                self.read_state(journal, self.saved_phase)

    def stop_at_first_publication(self, check):
        class Observed(Exception):
            pass

        before = sorted(self.project.rglob("*"))
        with self.assertRaises(Observed):
            with self.prepare() as owner:
                plan = owner.plan
                self.saved_binding = canonical_json_bytes(plan.binding)
                self.saved_phase = plan.identity.uri
                with self.pool(plan) as (pool, journal):
                    self.saved_budget = journal._budget

                    def stop(_source, destination, **_kwargs):
                        self.assertTrue(Path(destination).is_relative_to(self.project))
                        self.assertEqual(publications._publication_history(pool), ())
                        check(owner, plan, journal)
                        raise Observed()

                    with mock.patch.object(
                        publications, "move_layout_entry_exclusive", side_effect=stop
                    ):
                        with owner.source_phase(
                            pool,
                            acknowledged_plan_identity=plan.identity,
                            allow_host_execution=True,
                        ):
                            self.fail("first publication was not intercepted")
        self.assertEqual(sorted(self.project.rglob("*")), before)
        self.assertTrue((self.source / "app.py").is_file())
        self.assertFalse(self.destination.exists())
        self.assertFalse((self.project / "litai/layout.pending").exists())

    def reopen(self):
        return retained_layout_journal(
            self.state / "journal",
            canonical_binding=self.saved_binding,
            budget=self.saved_budget,
            recover=True,
        )

    def test_complete_namespace_roles_aliases_and_raw_metadata_survive_reopening(self):
        (self.project / "unknown-empty").mkdir()
        (self.project / "unclaimed.txt").write_bytes(b"retained unknown\n")
        os.link(self.source / "app.py", self.source / "app-hard.py")
        (self.source / "app-link.py").symlink_to("app.py")
        expected_native = {
            str(p.relative_to(self.project)): _from_stat(p.lstat())
            for p in self.project.rglob("*")
        }
        expected_native[""] = _from_stat(self.project.lstat())
        expected_bytes = {}

        def check(_owner, plan, journal):
            for item in plan.inputs:
                if item.content is not None:
                    expected_bytes[hashlib.sha256(item.content).hexdigest()] = (
                        item.content
                    )
            for _, body in plan.prospective:
                expected_bytes[hashlib.sha256(body).hexdigest()] = body
            snapshot = self.read_state(journal, plan.identity.uri)
            self.assertEqual(
                snapshot.document["namespace"]["identity"], plan.project_namespace
            )
            self.assertEqual(
                snapshot.document["partition"]["identity"], plan.project_roles
            )

        self.stop_at_first_publication(check)
        # The creating preparation/read owner and writer are now gone. Reopen
        # the actual immutable chain with its identical binding and policy.
        with self.reopen() as journal:
            snapshot = self.read_state(journal, self.saved_phase)
            from literate_ai.adapters.repository_refresh_reservations import (
                _custody_wire,
            )

            self.assertEqual(
                snapshot.document["namespace"]["native"],
                _custody_wire(
                    tuple(
                        sorted(
                            expected_native.items(), key=lambda x: (x[0] != "", x[0])
                        )
                    )
                ),
            )
            census = snapshot.document["namespace"]["census"]["tree"]
            self.assertIn("unknown-empty", census["directories"])
            self.assertIn(
                "unclaimed.txt",
                dict(snapshot.document["partition"]["document"]["roles"]),
            )
            self.assertEqual(
                {a["kind"] for a in census["aliases"]}, {"hardlink", "symlink"}
            )
            for digest, body in expected_bytes.items():
                self.assertEqual(snapshot.body(digest), body)
            # This object describes observations and cannot be passed off as a
            # preparation owner or a phase with effect permission.
            self.assertFalse(hasattr(snapshot, "source_phase"))

    def test_missing_original_byte_chunk_refuses_reopened_state(self):
        chunks = []
        self.stop_at_first_publication(
            lambda _o, p, j: chunks.extend(
                self.read_state(j, p.identity.uri).document["byte_witnesses"]["chunks"]
            )
        )
        self.assertTrue(chunks)
        (self.state / "journal" / f"p-{chunks[0]}.bin").unlink()
        with self.reopen() as journal:
            with self.assertRaisesRegex(ValueError, "payload-not-recorded"):
                self.read_state(journal, self.saved_phase)

    def test_original_journal_policy_refuses_before_any_payload_or_publication(self):
        before = sorted(self.project.rglob("*"))
        budget = LayoutJournalBudget(128, 64, 8 * 1024**2, 32)
        with (
            self.prepare() as owner,
            self.pool(owner.plan, budget=budget) as (pool, journal),
        ):
            with mock.patch.object(
                publications,
                "move_layout_entry_exclusive",
                side_effect=AssertionError("public effect reached"),
            ):
                with self.assertRaisesRegex(
                    ValueError, "complete original state exceeds"
                ):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ):
                        self.fail("undersized original journal admitted")
            self.assertEqual(journal._payloads, set())
            self.assertEqual(journal.events, ())
        self.assertEqual(sorted(self.project.rglob("*")), before)

    def test_private_persistence_failure_precedes_all_publication(self):
        before = sorted(self.project.rglob("*"))

        class Interrupted(Exception):
            pass

        with self.assertRaises(Interrupted):
            with self.prepare() as owner, self.pool(owner.plan) as (pool, journal):
                self.saved_binding = canonical_json_bytes(owner.plan.binding)
                self.saved_phase = owner.plan.identity.uri
                self.saved_budget = journal._budget
                store = journal.store_payload
                count = 0

                def interrupt(body):
                    nonlocal count
                    count += 1
                    if count == 2:
                        raise Interrupted()
                    return store(body)

                with (
                    mock.patch.object(journal, "store_payload", side_effect=interrupt),
                    mock.patch.object(
                        publications,
                        "move_layout_entry_exclusive",
                        side_effect=AssertionError("public effect reached"),
                    ),
                ):
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ):
                        self.fail("interrupted persistence admitted")
        self.assertEqual(sorted(self.project.rglob("*")), before)
        with self.reopen() as journal:
            with self.assertRaisesRegex(ValueError, "one bound durable original state"):
                self.read_state(journal, self.saved_phase)

    def test_last_private_append_mutation_refuses_binding_and_publication(self):
        from literate_ai.adapters import retained_layout_source_roles as roles

        target = self.source / "app.py"
        before = target.read_bytes()
        inode = target.stat().st_ino
        membership = sorted(self.project.rglob("*"))
        changed = []
        with (
            mock.patch.object(
                roles, "_bind_admission", wraps=roles._bind_admission
            ) as bind,
            mock.patch.object(
                publications,
                "move_layout_entry_exclusive",
                side_effect=AssertionError("publication after private-write mutation"),
            ) as publish,
        ):
            with self.assertRaises(ValueError):
                with self.prepare() as owner:
                    self.saved_binding = canonical_json_bytes(owner.plan.binding)
                    self.saved_phase = owner.plan.identity.uri
                    with self.pool(owner.plan) as (pool, journal):
                        self.saved_budget = journal._budget
                        append = journal.append

                        def mutate(kind, content):
                            result = append(kind, content)
                            if kind == "source-original-state-durable":
                                self.assertFalse(changed)
                                target.write_bytes(
                                    before + b"late-private-write-change\n"
                                )
                                changed.append(True)
                            return result

                        with mock.patch.object(journal, "append", side_effect=mutate):
                            with owner.source_phase(
                                pool,
                                acknowledged_plan_identity=owner.plan.identity,
                                allow_host_execution=True,
                            ):
                                self.fail("changed original source admitted")
            bind.assert_not_called()
            publish.assert_not_called()
        self.assertEqual(changed, [True])
        self.assertEqual(target.stat().st_ino, inode)
        self.assertEqual(target.read_bytes(), before + b"late-private-write-change\n")
        self.assertEqual(sorted(self.project.rglob("*")), membership)
        self.assertFalse(self.destination.exists())
        self.assertFalse((self.project / "litai/layout.pending").exists())
        # Durable original facts survive refusal; decoding these descriptions
        # does not authenticate the now-changed live source or grant effects.
        with self.reopen() as journal:
            snapshot = self.read_state(journal, self.saved_phase)
            original = {
                name: blob
                for name, blob, _executable in snapshot.document["namespace"]["census"][
                    "tree"
                ]["files"]
            }
            name = target.relative_to(self.project).as_posix()
            self.assertEqual(
                original[name]["digest"], hashlib.sha256(before).hexdigest()
            )

    def test_reopening_requires_the_original_acknowledged_phase(self):
        self.stop_at_first_publication(lambda _o, _p, _j: None)
        with self.reopen() as journal:
            with self.assertRaisesRegex(ValueError, "actual journal binding"):
                self.read_state(journal, "sha256:" + "0" * 64)

    def test_fresh_read_policy_is_funded_before_native_journal_reads(self):
        self.stop_at_first_publication(lambda _o, _p, _j: None)
        policies = (
            replace(
                self.input_budget, maximum_file_bytes=64, maximum_total_bytes=65536
            ),
            replace(
                self.input_budget,
                maximum_files=1,
                maximum_total_bytes=self.input_budget.maximum_file_bytes,
            ),
            replace(
                self.input_budget,
                maximum_total_bytes=self.input_budget.maximum_file_bytes,
            ),
        )
        with self.reopen() as journal:
            for policy in policies:
                with (
                    self.subTest(policy=policy),
                    mock.patch.object(
                        journal,
                        "_read",
                        side_effect=AssertionError("unfunded native read"),
                    ),
                ):
                    with self.assertRaisesRegex(
                        ValueError, "fresh per-file|shared catalog input allowance"
                    ):
                        state._read_original_state(
                            journal,
                            self.saved_phase,
                            budget=policy,
                            maximum_metadata_bytes=self.metadata_limit,
                        )

    def test_valid_private_chain_cannot_substitute_original_census(self):
        originals = []

        def collect(_owner, plan, journal):
            snapshot = self.read_state(journal, plan.identity.uri)
            originals.extend(
                body
                for name, (_node, body) in journal._known.items()
                if name.startswith("p-")
            )
            self.changed = copy.deepcopy(snapshot.document)

        self.stop_at_first_publication(collect)
        self.changed["namespace"]["census"]["tree"]["directories"].append(
            "invented-original"
        )
        raw = canonical_json_bytes(self.changed)
        with retained_layout_journal(
            self.state / "substituted-journal",
            canonical_binding=self.saved_binding,
            budget=self.saved_budget,
        ) as journal:
            for body in originals:
                journal.store_payload(body)
            digest = journal.store_payload(raw)
            journal.append(
                "source-original-state-durable",
                canonical_json_bytes(
                    {
                        "source_phase_identity": self.saved_phase,
                        "state_payload_digest": digest,
                        "grants_move_authority": False,
                    }
                ),
            )
            with self.assertRaisesRegex(ValueError, "complete original namespace"):
                self.read_state(journal, self.saved_phase)

    def test_actual_recovery_uses_early_original_bytes_before_source_intent(self):
        from literate_ai.adapters import retained_layout_recovery_data as recovery
        from literate_ai.adapters.retained_layout_control_publication import (
            staged_layout_controls,
        )
        from literate_ai.adapters.retained_layout_recovery_controls import (
            acquire_layout_recovery_controls,
            plan_layout_control_recovery,
        )
        from literate_ai.adapters.retained_layout_recovery_roles import (
            acquire_recovered_layout_roles,
            plan_recovered_layout_roles,
        )

        class Interrupted(Exception):
            pass

        with self.assertRaises(Interrupted):
            with self.prepare() as owner:
                self.saved_binding = canonical_json_bytes(owner.plan.binding)
                self.saved_phase = owner.plan.identity.uri
                with self.pool(owner.plan) as (pool, journal):
                    self.saved_budget = journal._budget
                    with owner.source_phase(
                        pool,
                        acknowledged_plan_identity=owner.plan.identity,
                        allow_host_execution=True,
                    ) as phase:
                        self.targets = tuple(
                            m.target for m in phase.controls.reservations._markers
                        )
                        self.assertNotIn(
                            "source-move-intent", [e["kind"] for e in journal.events]
                        )
                        raise Interrupted()
        stages, quarantine = (
            self.state / "recovery-stages",
            self.state / "recovery-data",
        )
        stages.mkdir(mode=0o700)
        quarantine.mkdir(mode=0o700)
        with self.reopen() as journal, staged_layout_controls(stages, journal) as pool:
            proposal = plan_layout_control_recovery(pool, self.targets)
            with acquire_layout_recovery_controls(
                pool,
                proposal,
                acknowledged_recovery_identity=proposal.identity,
                allow_host_execution=True,
            ) as raw:
                role_plan = plan_recovered_layout_roles(self.project, pool, (raw,))
                with acquire_recovered_layout_roles(
                    pool,
                    (raw,),
                    role_plan,
                    acknowledged_recovery_identity=role_plan.identity,
                    allow_host_execution=True,
                ) as roles:
                    with mock.patch.object(
                        journal,
                        "_read",
                        side_effect=AssertionError("unfunded legacy read"),
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "fresh complete original-state read policy"
                        ):
                            recovery._original_data(pool, roles)
                    # The fresh actual role owner is mandatory; durable source
                    # descriptions alone cannot plan or perform data recovery.
                    with mock.patch.object(
                        recovery,
                        "_file",
                        side_effect=AssertionError("old metadata fallback read"),
                    ):
                        phase, _original, events, old, proposed = (
                            recovery._original_data(
                                pool,
                                roles,
                                budget=self.input_budget,
                                maximum_metadata_bytes=self.metadata_limit,
                            )
                        )
                    self.assertEqual(phase, self.saved_phase)
                    self.assertNotIn("source-move-intent", [e["kind"] for e in events])
                    self.assertEqual(set(old), set(recovery._TARGETS))
                    self.assertEqual(set(proposed), set(recovery._TARGETS))
                    planned = recovery.plan_layout_data_recovery(
                        pool,
                        roles,
                        quarantine,
                        budget=self.input_budget,
                        maximum_metadata_bytes=self.metadata_limit,
                    )
                    self.assertEqual(planned.issues, ())
                    self.assertEqual(planned.actions, ())
        self.assertTrue((self.source / "app.py").exists())
        self.assertFalse(self.destination.exists())


if __name__ == "__main__":
    unittest.main()
