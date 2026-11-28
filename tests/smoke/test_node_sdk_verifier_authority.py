"""Acknowledgement membership controls only; no runtime or grant qualification."""

import copy
import gc
import os
import pickle
import sys
import threading
import unittest
import weakref
from pathlib import Path
from unittest import mock

from literate_ai.adapters import node_sdk_verifier_authority as owner
from literate_ai.adapters.builders._process import run_bounded_process


class Original:
    pass


class VerifierAcknowledgementTests(unittest.TestCase):
    def setUp(self):
        self.originals = Original(), Original()
        self.facts = ("fixed metadata fixture", "actor", 600, True)
        self.config, self.runtime = Original(), Original()

    def acknowledgement(self, *, facts=None, originals=None):
        handle = owner._new_acknowledgement(
            self.facts if facts is None else facts,
            self.originals if originals is None else originals,
        )
        self.addCleanup(owner._retire_acknowledgement, handle)
        return handle

    def bind(self, handle, **changes):
        args = dict(facts=self.facts, originals=self.originals)
        args.update(changes)
        owner._bind_acknowledgement(handle, self.config, self.runtime, **args)

    def require(self, handle, **changes):
        args = dict(facts=self.facts, originals=self.originals)
        args.update(changes)
        return owner._require_acknowledgement(handle, self.config, self.runtime, **args)

    def test_public_constructor_foreign_and_copied_handle_cannot_bind(self):
        with self.assertRaises(TypeError):
            owner.NodeSDKVerifierExecutionAcknowledgement()
        handle = self.acknowledgement()
        for operation in (copy.copy, copy.deepcopy, pickle.dumps):
            with self.assertRaises(TypeError):
                operation(handle)
        copied = object.__new__(owner.NodeSDKVerifierExecutionAcknowledgement)
        object.__setattr__(copied, "_registration", handle._registration)
        for foreign in (
            object(),
            object.__new__(owner.NodeSDKVerifierExecutionAcknowledgement),
            copied,
        ):
            with self.subTest(kind=type(foreign).__name__):
                with self.assertRaises((TypeError, ValueError)):
                    self.bind(foreign)
        self.bind(handle)
        self.assertTrue(self.require(handle).startswith("sha256:"))

    def test_prebinding_identity_does_not_read_configuration_or_runtime(self):
        calls = []

        class Unreadable:
            def __getattribute__(self, name):
                calls.append(name)
                raise AssertionError("membership must not inspect arbitrary attributes")

        handle = self.acknowledgement()
        identity = owner._values(owner._state(handle))[1]
        config, runtime = Unreadable(), Unreadable()
        owner._bind_acknowledgement(
            handle, config, runtime, facts=self.facts, originals=self.originals
        )
        self.assertEqual(
            owner._require_acknowledgement(
                handle, config, runtime, facts=self.facts, originals=self.originals
            ),
            identity,
        )
        self.assertEqual(calls, [])

    def test_rebinding_poison_is_sticky_even_for_same_runtime(self):
        handle = self.acknowledgement()
        self.bind(handle)
        with self.assertRaisesRegex(ValueError, "already consumed"):
            self.bind(handle)
        with self.assertRaisesRegex(ValueError, "poisoned"):
            self.require(handle)

    def test_policy_owner_is_opaque_and_original_membership_survives_binding(self):
        calls = []

        class Unreadable:
            def __getattribute__(self, name):
                calls.append(name)
                raise AssertionError("membership cannot inspect the policy owner")

        handle, policy = self.acknowledgement(), Unreadable()
        owner._attach_policy_owner(handle, policy)
        self.assertIs(owner._registered_policy_owner(handle), policy)
        self.bind(handle)
        self.assertIs(owner._registered_policy_owner(handle), policy)
        self.require(handle)
        self.assertEqual(calls, [])

    def test_missing_repeated_or_late_policy_attachment_is_sticky(self):
        for action in ("missing", "repeated", "late", "none"):
            with self.subTest(action=action):
                handle, policy = self.acknowledgement(), Original()
                with self.assertRaises(ValueError):
                    if action == "missing":
                        owner._registered_policy_owner(handle)
                    elif action == "repeated":
                        owner._attach_policy_owner(handle, policy)
                        owner._attach_policy_owner(handle, policy)
                    elif action == "late":
                        self.bind(handle)
                        owner._attach_policy_owner(handle, policy)
                    else:
                        owner._attach_policy_owner(handle, None)
                with self.assertRaisesRegex(ValueError, "poisoned"):
                    self.bind(handle)

    def test_policy_attachment_lock_exit_cancellation_remains_poisoned(self):
        handle = self.acknowledgement()
        original_lock = owner._LOCK
        primary = KeyboardInterrupt("original policy attachment cancellation")

        class InterruptedLock:
            depth = 0
            failed = False

            def __enter__(self):
                original_lock.acquire()
                self.depth += 1

            def __exit__(self, *_args):
                self.depth -= 1
                original_lock.release()
                if not self.depth and not self.failed:
                    self.failed = True
                    raise primary

        with mock.patch.object(owner, "_LOCK", InterruptedLock()):
            with self.assertRaises(KeyboardInterrupt) as failure:
                owner._attach_policy_owner(handle, Original())
        self.assertIs(failure.exception, primary)
        with self.assertRaisesRegex(ValueError, "poisoned"):
            owner._registered_policy_owner(handle)

    def test_weak_issuer_backreference_does_not_retain_handle_or_owner(self):
        handle = owner._new_acknowledgement(self.facts, self.originals)
        policy = Original()
        policy.acknowledgement = weakref.ref(handle)
        policy_ref, handle_ref, key = (
            weakref.ref(policy),
            weakref.ref(handle),
            id(handle),
        )
        owner._attach_policy_owner(handle, policy)
        del policy
        self.assertIsNotNone(policy_ref())
        del handle
        gc.collect()
        self.assertIsNone(handle_ref())
        self.assertIsNone(policy_ref())
        self.assertNotIn(key, owner._ACKNOWLEDGEMENTS)

    def test_fixed_retirement_action_runs_once_outside_registry_mutex(self):
        handle = self.acknowledgement()
        availability = []

        def retire():
            def probe():
                acquired = owner._LOCK.acquire(timeout=1)
                availability.append(acquired)
                if acquired:
                    owner._LOCK.release()

            thread = threading.Thread(target=probe)
            thread.start()
            thread.join(timeout=2)
            self.assertFalse(thread.is_alive())

        owner._attach_policy_owner(handle, Original(), retire=retire)
        owner._retire_acknowledgement(handle)
        owner._retire_acknowledgement(handle)
        self.assertEqual(availability, [True])

    def test_weak_retirement_invokes_fixed_release_without_retaining_handle(self):
        handle = owner._new_acknowledgement(self.facts, self.originals)
        released = []
        owner._attach_policy_owner(
            handle, Original(), retire=lambda: released.append(True)
        )
        key, reference = id(handle), weakref.ref(handle)
        del handle
        gc.collect()
        self.assertIsNone(reference())
        self.assertNotIn(key, owner._ACKNOWLEDGEMENTS)
        self.assertEqual(released, [True])

    def test_foreign_facts_or_original_owners_poison_before_binding(self):
        for change in (
            {"facts": self.facts + ("changed",)},
            {"originals": (self.originals[0], Original())},
        ):
            handle = self.acknowledgement()
            with self.assertRaisesRegex(ValueError, "authority changed"):
                self.bind(handle, **change)
            with self.assertRaisesRegex(ValueError, "poisoned"):
                self.bind(handle)

    def test_equal_boolean_and_integer_values_are_distinct_facts(self):
        for original, changed in ((1, True), (True, 1)):
            handle = self.acknowledgement(facts=(original,))
            with self.assertRaisesRegex(ValueError, "authority changed"):
                self.bind(handle, facts=(changed,))
            with self.assertRaisesRegex(ValueError, "poisoned"):
                self.bind(handle, facts=(original,))

    def test_lock_exit_cancellation_poison_prevents_binding_acknowledgement(self):
        handle = self.acknowledgement()
        original_lock = owner._LOCK
        primary = KeyboardInterrupt("original binding lock-exit cancellation")

        class InterruptedLock:
            depth = 0
            failed = False

            def __enter__(self):
                original_lock.acquire()
                self.depth += 1
                return self

            def __exit__(self, *_args):
                self.depth -= 1
                original_lock.release()
                if not self.depth and not self.failed:
                    self.failed = True
                    raise primary

        with mock.patch.object(owner, "_LOCK", InterruptedLock()):
            with self.assertRaises(KeyboardInterrupt) as failure:
                self.bind(handle)
        self.assertIs(failure.exception, primary)
        with self.assertRaisesRegex(ValueError, "poisoned"):
            self.require(handle)

    def test_collected_weak_memberships_cannot_authorize_none(self):
        handle = self.acknowledgement()
        config, runtime = Original(), Original()
        owner._bind_acknowledgement(
            handle, config, runtime, facts=self.facts, originals=self.originals
        )
        del config, runtime
        gc.collect()
        with self.assertRaisesRegex(ValueError, "runtime changed"):
            owner._require_acknowledgement(
                handle, None, None, facts=self.facts, originals=self.originals
            )

    def test_failure_poison_serializes_against_concurrent_binding(self):
        handle = self.acknowledgement()
        paused, release, attempting, completed = (threading.Event() for _ in range(4))
        context = threading.local()
        values, poison = owner._values, owner._poison
        failures, concurrent = [], []

        def observed_poison(state):
            context.poisoning = True
            try:
                return poison(state)
            finally:
                context.poisoning = False

        def observed_values(state):
            result = values(state)
            if getattr(context, "poisoning", False) and not paused.is_set():
                paused.set()
                if not release.wait(2):
                    raise AssertionError("fixture did not release original poison")
            return result

        def failing_bind():
            try:
                owner._bind_acknowledgement(
                    handle,
                    1,
                    self.runtime,
                    facts=self.facts,
                    originals=self.originals,
                )
            except BaseException as error:
                failures.append(error)

        def concurrent_bind():
            attempting.set()
            try:
                self.bind(handle)
                concurrent.append("bound")
            except BaseException as error:
                concurrent.append(error)
            finally:
                completed.set()

        first = threading.Thread(target=failing_bind, name="Original verifier failure")
        second = threading.Thread(
            target=concurrent_bind, name="Concurrent verifier bind"
        )
        with (
            mock.patch.object(owner, "_poison", new=observed_poison),
            mock.patch.object(owner, "_values", new=observed_values),
        ):
            first.start()
            try:
                self.assertTrue(paused.wait(2))
                second.start()
                self.assertTrue(attempting.wait(1))
                self.assertFalse(completed.wait(0.1))
            finally:
                release.set()
                first.join(timeout=3)
                if second.ident is not None:
                    second.join(timeout=3)
        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(len(failures), 1)
        self.assertIsInstance(failures[0], TypeError)
        self.assertEqual(len(concurrent), 1)
        self.assertIsInstance(concurrent[0], ValueError)
        with self.assertRaisesRegex(ValueError, "poisoned"):
            self.require(handle)

    def test_uncertain_poison_denies_process_and_preserves_original_failure(self):
        # The denial has no reset API. Prove it in an isolated interpreter.
        code = """
import types
from unittest.mock import patch
from literate_ai.adapters import node_sdk_verifier_authority as owner
class Original: pass
facts = ('fixture',)
originals = (Original(), Original())
handle = owner._new_acknowledgement(facts, originals)
primary = KeyboardInterrupt('original binding cancellation')
def stopped_ref(*args): raise primary
def failed_write(*args): raise SystemExit('secondary poison failure')
with (
    patch.object(owner, 'weakref', types.SimpleNamespace(ref=stopped_ref)),
    patch.object(owner, '_write', failed_write),
):
    try:
        owner._bind_acknowledgement(
            handle, Original(), Original(), facts=facts, originals=originals
        )
    except KeyboardInterrupt as error:
        assert error is primary
    else:
        raise AssertionError('original cancellation lost')
assert owner._DENIED
try:
    owner._new_acknowledgement(facts, originals)
except ValueError:
    pass
else:
    raise AssertionError('uncertain registry was usable')
owner._retire_acknowledgement(handle)
assert not owner._ACKNOWLEDGEMENTS
print('denied and drained')
"""
        result = run_bounded_process(
            [sys.executable, "-c", code],
            cwd=Path.cwd(),
            environment=dict(os.environ),
            timeout_seconds=10,
            stdout_limit_bytes=4096,
            stderr_limit_bytes=4096,
            error_prefix="verifier_acknowledgement_denial_fixture",
            terminate_descendants=True,
            trace=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr.decode())
        self.assertEqual(result.stdout, b"denied and drained\n")

    def test_runtime_change_and_dead_runtime_refuse_original_registration(self):
        handle = self.acknowledgement()
        self.bind(handle)
        with self.assertRaisesRegex(ValueError, "runtime changed"):
            owner._require_acknowledgement(
                handle,
                self.config,
                Original(),
                facts=self.facts,
                originals=self.originals,
            )
        with self.assertRaisesRegex(ValueError, "poisoned"):
            self.require(handle)
        another = self.acknowledgement()
        self.bind(another)
        self.runtime = Original()
        gc.collect()
        with self.assertRaisesRegex(ValueError, "runtime changed"):
            self.require(another)

    def test_storage_substitution_is_sticky_but_retirement_can_drain_it(self):
        handle = self.acknowledgement()
        token = object.__getattribute__(handle, "_registration")
        object.__setattr__(handle, "_registration", object())
        with self.assertRaisesRegex(ValueError, "poisoned"):
            self.bind(handle)
        object.__setattr__(handle, "_registration", token)
        with self.assertRaisesRegex(ValueError, "poisoned"):
            self.bind(handle)
        owner._retire_acknowledgement(handle)
        owner._retire_acknowledgement(handle)
        with self.assertRaisesRegex(ValueError, "retired"):
            self.bind(handle)

    def test_deleted_slot_failure_remains_poisoned_after_storage_restoration(self):
        handle = self.acknowledgement()
        token = handle._registration
        del handle._registration
        with self.assertRaises(AttributeError):
            self.bind(handle)
        handle._registration = token
        with self.assertRaisesRegex(ValueError, "poisoned"):
            self.bind(handle)

    def test_dropped_handle_releases_originals_through_captured_cleanup(self):
        payload = Original()
        reference = weakref.ref(payload)
        handle = owner._new_acknowledgement(self.facts, (payload, Original()))
        key, handle_reference = id(handle), weakref.ref(handle)
        del payload
        self.assertIsNotNone(reference())
        with mock.patch.object(
            owner, "_drop_registration", side_effect=AssertionError("late callback")
        ):
            del handle
            gc.collect()
        self.assertIsNone(handle_reference())
        self.assertIsNone(reference())
        self.assertNotIn(key, owner._ACKNOWLEDGEMENTS)

    def test_substituted_getter_is_never_invoked_and_retirement_still_drains(self):
        handle = self.acknowledgement()
        calls = []

        def getter(_self):
            calls.append(True)
            raise AssertionError("substituted getter")

        with mock.patch.object(
            owner.NodeSDKVerifierExecutionAcknowledgement,
            "_registration",
            property(getter),
        ):
            with self.assertRaisesRegex(ValueError, "class changed"):
                self.bind(handle)
        self.assertFalse(calls)
        with self.assertRaisesRegex(ValueError, "poisoned"):
            self.bind(handle)
        owner._retire_acknowledgement(handle)

    def test_fact_bounds_reject_callbacks_subclasses_large_text_and_nonportable_values(
        self,
    ):
        class Text(str):
            pass

        for facts in (
            [],
            (),
            (object(),),
            (Text("text"),),
            ("x" * 4097,),
            ("é" * 4096,),
            (float("nan"),),
            (-1,),
            (2**53,),
            tuple(range(17)),
        ):
            with self.subTest(kind=type(facts).__name__):
                with self.assertRaises(ValueError):
                    self.acknowledgement(facts=facts)

    def test_capacity_is_bounded_and_normal_retirement_recovers_it(self):
        handles = []
        try:
            for _ in range(owner._MAX_ACKNOWLEDGEMENTS):
                handles.append(self.acknowledgement())
            with self.assertRaisesRegex(ValueError, "capacity exhausted"):
                self.acknowledgement()
            owner._retire_acknowledgement(handles.pop())
            handles.append(self.acknowledgement())
        finally:
            for handle in handles:
                owner._retire_acknowledgement(handle)

    def test_retirement_releases_original_authority_outside_registry_lock(self):
        availability = []

        class Payload:
            def __del__(self):
                def probe():
                    acquired = owner._LOCK.acquire(timeout=1)
                    availability.append(acquired)
                    if acquired:
                        owner._LOCK.release()

                thread = threading.Thread(target=probe)
                thread.start()
                thread.join(timeout=2)

        payload = Payload()
        reference = weakref.ref(payload)
        handle = self.acknowledgement(originals=(payload, Original()))
        del payload
        self.assertIsNotNone(reference())
        owner._retire_acknowledgement(handle)
        gc.collect()
        self.assertIsNone(reference())
        self.assertEqual(availability, [True])
