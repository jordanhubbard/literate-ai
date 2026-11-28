"""Failure notes preserve actual read custody, limits and the original error."""

import os
import unittest
from dataclasses import replace
from unittest import mock

from literate_ai.adapters import retained_layout_source_provider as production
from literate_ai.adapters.builders.python import BuildError


def _closed(function, name):
    return dict(
        zip(
            function.__code__.co_freevars,
            (cell.cell_contents for cell in function.__closure__),
            strict=True,
        )
    )[name]


class SourceProviderFailureNoteTests(unittest.TestCase):
    def values(self):
        return (100, 80, 80, 4096, 1200, 1024, 64000, 8 * 1024**3, 4096, 16384, 0)

    def test_numeric_note_uses_original_unbound_add_note(self):
        class OriginalError(ValueError):
            def add_note(self, note):
                raise AssertionError("instance override executed")

        error = OriginalError("original")
        _closed(production._Provider.run, "descriptor")[0](error, self.values())
        self.assertEqual(str(error), "original")
        self.assertEqual(len(error.__notes__), 1)
        self.assertIn(
            "requested_stdout=100, remaining_stdout=80, chosen_stdout=80",
            error.__notes__[0],
        )
        self.assertLessEqual(len(error.__notes__[0]), 1024)

    def test_nonprimitive_or_oversized_fields_skip_note_without_formatting(self):
        class Foreign:
            def __str__(self):
                raise AssertionError("foreign formatting executed")

        note = _closed(production._Provider.run, "descriptor")[0]
        for invalid in (Foreign(), True, 1 << 129):
            with self.subTest(field_type=type(invalid).__name__):
                error = ValueError("original")
                note(error, (invalid, *self.values()[1:]))
                self.assertFalse(hasattr(error, "__notes__"))

    def test_changed_private_note_code_skips_dispatch(self):
        checked = _closed(production._Provider.run, "descriptor")[0]
        note = _closed(checked, "note")
        original = note.__code__
        try:
            note.__code__ = original.replace(co_name="changed")
            error = ValueError("original")
            checked(error, self.values())
            self.assertFalse(hasattr(error, "__notes__"))
        finally:
            note.__code__ = original

    def test_late_formatting_builtin_shadows_never_execute(self):
        checked = _closed(production._Provider.run, "descriptor")[0]
        for name in ("type", "str", "len", "any"):
            with self.subTest(shadow=name):
                with mock.patch.object(
                    production, name, create=True, side_effect=AssertionError("foreign")
                ) as foreign:
                    error = ValueError("original")
                    checked(error, self.values())
                    self.assertEqual(len(error.__notes__), 1)
                    foreign.assert_not_called()

    def actual_read(
        self,
        *,
        fail,
        drift=False,
        smaller=False,
        mismatch=False,
        tamper=False,
        pressure=False,
        foreign_stream=None,
    ):
        import tests.critical.test_retained_layout_source_provider as fixtures

        fixtures.SourceProviderTests.setUpClass()
        self.addCleanup(fixtures.SourceProviderTests.doClassCleanups)
        fixture = fixtures.SourceProviderTests("runTest")
        fixture.setUp()
        self.addCleanup(fixture.doCleanups)
        original_error = BuildError(
            "layout.source-provider_output_limit", "original native limit"
        )
        remaining_calls, caught, native_calls, accounting = [], [], [], []
        remaining_values, foreign_calls = [], []
        original_remaining = production._Provider.remaining
        original_native = production.run_bounded_process
        checker = _closed(production._Provider.run, "descriptor")[0]
        checker_code = checker.__code__

        def foreign_note(error, values):
            error.foreign_called = True

        def remaining(owner):
            remaining_calls.append(True)
            value = original_remaining(owner)
            remaining_values.append(value)
            return value

        class ForeignBytes(bytes):
            def __len__(self):
                foreign_calls.append("len")
                return super().__len__()

            def __ne__(self, other):
                foreign_calls.append("compare")
                return super().__ne__(other)

        def native(command, **kwargs):
            native_calls.append((command, kwargs))
            if drift:
                checker.__code__ = foreign_note.__code__.replace(
                    co_freevars=checker_code.co_freevars
                )
            if fail:
                raise original_error
            observed = original_native(command, **kwargs)
            if tamper:
                objects.cache[kind, oid] = bytes(bytearray(content))
            if mismatch:
                observed = replace(
                    observed,
                    stdout=bytes([observed.stdout[0] ^ 1]) + observed.stdout[1:],
                )
            if foreign_stream is not None:
                observed = replace(
                    observed,
                    **{foreign_stream: ForeignBytes(getattr(observed, foreign_stream))},
                )
            return observed

        result = objects = content = kind = oid = requested = None

        def exercise():
            nonlocal result, objects, content, kind, oid, requested
            with fixture.inspecting() as (owner, phase, _pool, _journal):
                with fixture.observe(phase) as partition:
                    actual = partition._provider
                    objects = actual.objects
                    (kind, oid), content = next(iter(objects.cache.items()))
                    requested = max(1, len(content))
                    if smaller:
                        requested -= 1
                    with owner._reads():
                        ledger = fixtures.preparation._state(owner).ledger
                        temporary_charge = 0
                        if pressure:
                            self.assertGreater(requested, 65)
                            margin = 64 * (4096 + max(65, requested // 2))
                            temporary_charge = (
                                (ledger.metadata - ledger.charged - margin) // 64
                            ) * 64
                            self.assertGreater(temporary_charge, 0)
                            # Test-owned live metadata pressure; the policy and
                            # reserve stay original. Release only after success.
                            ledger.charge_records(0, temporary_charge // 64)
                        before = ledger.bytes, ledger.charged, ledger.records
                        with (
                            mock.patch.object(
                                production._Provider, "remaining", remaining
                            ),
                            mock.patch.object(
                                production, "run_bounded_process", native
                            ),
                        ):
                            try:
                                result = actual.run(
                                    objects, ("cat-file", kind, oid), requested
                                )
                                accounting.append(
                                    tuple(
                                        after - prior
                                        for after, prior in zip(
                                            (
                                                ledger.bytes,
                                                ledger.charged,
                                                ledger.records,
                                            ),
                                            before,
                                            strict=True,
                                        )
                                    )
                                )
                                ledger.charged -= temporary_charge
                            except BaseException as error:
                                caught.append(error)
                                raise

        try:
            if fail or smaller or mismatch or tamper or foreign_stream is not None:
                with self.assertRaises((ValueError, BuildError)):
                    exercise()
            else:
                exercise()
        finally:
            checker.__code__ = checker_code
        if fail:
            self.assertEqual(caught, [original_error])
        elif smaller:
            self.assertEqual(len(caught), 1)
            self.assertIsInstance(caught[0], BuildError)
            self.assertEqual(caught[0].code, "layout.source-provider_output_limit")
            self.assertIn("scratch_stdout=0", caught[0].__notes__[0])
        elif mismatch or tamper or foreign_stream is not None:
            self.assertEqual(len(caught), 1)
            self.assertIn(
                "exact byte streams"
                if foreign_stream is not None
                else (
                    "witness or lifetime changed" if tamper else "object bytes changed"
                ),
                str(caught[0]),
            )
            self.assertIsNone(result)
            if tamper:
                self.assertIsNot(objects.cache[kind, oid], content)
            else:
                self.assertIs(objects.cache[kind, oid], content)
        else:
            self.assertEqual(caught, [])
        self.assertEqual(remaining_calls, [True])
        self.assertEqual(foreign_calls, [])
        if pressure:
            self.assertGreater(remaining_values[0], 0)
            self.assertLess(remaining_values[0], requested)
        self.assertEqual(len(native_calls), 1)
        command, kwargs = native_calls[0]
        self.assertEqual(command[-3:], ("cat-file", kind, oid))
        self.assertEqual(kwargs["stdout_limit_bytes"], requested)
        self.assertEqual(kwargs["stderr_limit_bytes"], 4096)
        self.assertIs(kwargs["environment"], objects.environment)
        if fail and not drift:
            self.assertEqual(len(original_error.__notes__), 1)
            self.assertIn("requested_stdout=", original_error.__notes__[0])
        if drift:
            self.assertFalse(getattr(original_error, "foreign_called", False))
            self.assertFalse(hasattr(original_error, "__notes__"))
        if not (fail or smaller or mismatch or tamper or foreign_stream is not None):
            self.assertIs(result, content)
            self.assertEqual(accounting, [(0, 4096, 1)])
        self.assertTrue(fixture.source.is_dir())
        self.assertFalse(fixture.destination.exists())

    @unittest.skipUnless(os.name == "posix", "actual original provider fixture")
    def test_real_owner_failure_keeps_one_native_call_and_original_error(self):
        self.actual_read(fail=True)

    @unittest.skipUnless(os.name == "posix", "actual original provider fixture")
    def test_checker_change_during_native_call_never_executes(self):
        self.actual_read(fail=True, drift=True)

    @unittest.skipUnless(os.name == "posix", "actual original provider fixture")
    def test_real_owner_success_keeps_original_bytes_and_native_call(self):
        self.actual_read(fail=False)

    @unittest.skipUnless(os.name == "posix", "actual original provider fixture")
    def test_smaller_caller_ceiling_remains_original_native_refusal(self):
        self.actual_read(fail=False, smaller=True)

    @unittest.skipUnless(os.name == "posix", "actual original provider fixture")
    def test_fresh_byte_mismatch_never_returns_cached_success(self):
        self.actual_read(fail=False, mismatch=True)

    @unittest.skipUnless(os.name == "posix", "actual original provider fixture")
    def test_binding_replacement_during_native_read_refuses(self):
        self.actual_read(fail=False, tamper=True)

    @unittest.skipUnless(os.name == "posix", "actual original provider fixture")
    def test_original_scratch_succeeds_below_new_payload_headroom(self):
        self.actual_read(fail=False, pressure=True)

    @unittest.skipUnless(os.name == "posix", "actual original provider fixture")
    def test_foreign_stdout_comparison_never_executes(self):
        self.actual_read(fail=False, foreign_stream="stdout")

    @unittest.skipUnless(os.name == "posix", "actual original provider fixture")
    def test_foreign_stderr_length_never_executes(self):
        self.actual_read(fail=False, foreign_stream="stderr")
