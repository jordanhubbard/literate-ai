"""Actual child revocation and original scoped liveness, without execution grants."""

import io
import os
import sys
import tempfile
import threading
import unittest
from contextvars import copy_context
from pathlib import Path
from unittest import mock

import literate_ai.adapters.builders._process as shared_process
from literate_ai.adapters._processes import (
    ProcessTreeOwnership,
    create_process_tree_ownership,
)
from literate_ai.adapters.builders._process import run_bounded_process
from literate_ai.adapters.models.coding_cli import CodingCliError, _run_bounded
from literate_ai.adapters.process_liveness import (
    ProcessLivenessError,
    process_liveness,
    require_process_liveness,
)
from tests.support.process_state import stopped_process_state


class ProcessLivenessTests(unittest.TestCase):
    def run_child(self, adapter, root, code):
        command = (sys.executable, "-c", code)
        if adapter == "tool":
            return run_bounded_process(
                command,
                cwd=root,
                environment={},
                timeout_seconds=10,
                stdout_limit_bytes=1024,
                stderr_limit_bytes=1024,
                error_prefix="fixture",
                poll_interval_seconds=0.02,
                terminate_descendants=True,
                trace=False,
            )
        return _run_bounded(
            command,
            cwd=root,
            environment={},
            timeout_seconds=10,
            maximum_stdout_bytes=1024,
            maximum_stderr_bytes=1024,
        )

    def test_nested_owners_are_additive_and_restored(self):
        observations = []
        require_process_liveness()

        with process_liveness(lambda: observations.append("outer")):
            with process_liveness(lambda: observations.append("inner")):
                before = len(observations)
                require_process_liveness()
                self.assertEqual(observations[before:], ["outer", "inner"])
            before = len(observations)
            require_process_liveness()
            self.assertEqual(observations[before:], ["outer"])
        require_process_liveness()

    def test_scope_capacity_does_not_replace_an_existing_owner(self):
        with process_liveness(lambda: None):
            with mock.patch("literate_ai.adapters.process_liveness._MAX_SCOPES", 1):
                with self.assertRaisesRegex(ProcessLivenessError, "capacity"):
                    with process_liveness(lambda: None):
                        self.fail("capacity limit bypassed")
            require_process_liveness()

    def test_caught_owner_failure_cannot_revive_the_scope_or_return_success(self):
        alive = True

        def owner():
            if not alive:
                raise ValueError("owner revoked")

        with self.assertRaises(ProcessLivenessError):
            with process_liveness(owner):
                alive = False
                with self.assertRaisesRegex(ValueError, "owner revoked"):
                    require_process_liveness()
                alive = True
                with self.assertRaises(ProcessLivenessError):
                    require_process_liveness()

    def test_async_generator_or_disguised_coroutine_owner_cannot_enter(self):
        async def asynchronous():
            self.fail("async owner executed")

        def generator():
            yield None

        for callback in (asynchronous, generator):
            with self.subTest(callback=callback.__name__), self.assertRaises(TypeError):
                with process_liveness(callback):
                    self.fail("unsupported owner entered")
        returned = []

        def disguised():
            coroutine = asynchronous()
            returned.append(coroutine)
            return coroutine

        with self.assertRaises(TypeError):
            with process_liveness(disguised):
                self.fail("deferred owner entered")
        self.assertIsNone(returned[0].cr_frame)

    def test_copied_context_cannot_extend_lifetime_or_launch_a_child(self):
        for adapter in ("tool", "coding-cli"):
            with (
                self.subTest(adapter=adapter),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                marker = root / "launched"
                with process_liveness(lambda: None):
                    context = copy_context()
                with self.assertRaises(ProcessLivenessError):
                    context.run(
                        self.run_child,
                        adapter,
                        root,
                        "from pathlib import Path;"
                        f"Path({str(marker)!r}).write_text('launched')",
                    )
                self.assertFalse(marker.exists())

    def test_liveness_callback_cannot_launch_a_child_or_swallow_that_refusal(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            marker = root / "child"

            def owner():
                try:
                    self.run_child(
                        "tool",
                        root,
                        "from pathlib import Path;" + f"Path({str(marker)!r}).touch()",
                    )
                except ProcessLivenessError:
                    pass

            with self.assertRaises(ProcessLivenessError):
                with process_liveness(owner):
                    self.fail("recursive owner became current")
            self.assertFalse(marker.exists())

    def test_concurrent_scope_exit_invalidates_an_inflight_original_guard(self):
        entered, release = threading.Event(), threading.Event()
        failures = []

        def owner():
            if threading.current_thread().name == "liveness-fixture":
                entered.set()
                if not release.wait(5):
                    raise TimeoutError("fixture release timed out")

        def check(context):
            try:
                context.run(require_process_liveness)
            except BaseException as exc:
                failures.append(exc)

        try:
            with process_liveness(owner):
                thread = threading.Thread(
                    target=check, args=(copy_context(),), name="liveness-fixture"
                )
                thread.start()
                self.assertTrue(entered.wait(5))
            release.set()
            thread.join(5)
            self.assertFalse(thread.is_alive())
            self.assertEqual(len(failures), 1)
            self.assertIsInstance(failures[0], ProcessLivenessError)
        finally:
            release.set()
            if "thread" in locals():
                thread.join(5)

    def test_outer_retirement_during_inner_prelaunch_check_never_launches(self):
        entered, release = threading.Event(), threading.Event()
        failures = []
        armed = False
        post_trace_checks = 0
        factory = mock.Mock(side_effect=AssertionError("child launched"))

        def arm(*_args, **_kwargs):
            nonlocal armed
            armed = True

        def inner_owner():
            nonlocal post_trace_checks
            if armed:
                post_trace_checks += 1
                if post_trace_checks == 2:
                    entered.set()
                    if not release.wait(5):
                        raise TimeoutError("fixture release timed out")

        def work(context):
            def launch():
                with process_liveness(inner_owner):
                    run_bounded_process(
                        (sys.executable, "-c", "pass"),
                        cwd=None,
                        environment={},
                        timeout_seconds=5,
                        stdout_limit_bytes=1024,
                        stderr_limit_bytes=1024,
                        error_prefix="fixture",
                        process_factory=factory,
                    )

            try:
                context.run(launch)
            except BaseException as exc:
                failures.append(exc)

        with mock.patch.object(shared_process, "trace_subprocess", side_effect=arm):
            try:
                with process_liveness(lambda: None):
                    thread = threading.Thread(
                        target=work,
                        args=(copy_context(),),
                        name="nested-liveness-fixture",
                    )
                    thread.start()
                    self.assertTrue(entered.wait(5))
                release.set()
                thread.join(5)
                self.assertFalse(thread.is_alive())
                factory.assert_not_called()
                self.assertEqual(len(failures), 1)
                self.assertIsInstance(failures[0], ProcessLivenessError)
            finally:
                release.set()
                if "thread" in locals():
                    thread.join(5)

    @unittest.skipUnless(os.name == "posix", "actual POSIX process group")
    def test_revocation_stops_actual_parent_and_descendant_for_both_adapters(self):
        for adapter in ("tool", "coding-cli"):
            with (
                self.subTest(adapter=adapter),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                parent_pid, child_pid = root / "parent.pid", root / "child.pid"
                child = (
                    "import os,time;from pathlib import Path;"
                    f"Path({str(child_pid)!r}).write_text(str(os.getpid()));"
                    "time.sleep(60)"
                )
                parent = (
                    "import os,subprocess,sys,time;from pathlib import Path;"
                    f"Path({str(parent_pid)!r}).write_text(str(os.getpid()));"
                    f"subprocess.Popen([sys.executable,'-c',{child!r}]);"
                    "time.sleep(60)"
                )

                def owner(ready=child_pid):
                    if ready.exists():
                        raise ValueError("owner revoked during child")

                with self.assertRaisesRegex(ValueError, "owner revoked during child"):
                    with process_liveness(owner):
                        self.run_child(adapter, root, parent)
                for path in (parent_pid, child_pid):
                    self.assertTrue(path.exists(), "fixture process did not start")
                    state = stopped_process_state(int(path.read_text()))
                    self.assertTrue(not state or state.startswith("Z"), state)

    def test_expiry_during_final_process_cleanup_withholds_result(self):
        original_release = ProcessTreeOwnership.release
        for adapter in ("tool", "coding-cli"):
            with (
                self.subTest(adapter=adapter),
                tempfile.TemporaryDirectory() as temporary,
            ):

                def exercise(selected_adapter):
                    alive = True

                    def owner():
                        if not alive:
                            raise ValueError("owner ended during cleanup")

                    def released(ownership):
                        nonlocal alive
                        original_release(ownership)
                        alive = False

                    with mock.patch.object(ProcessTreeOwnership, "release", released):
                        with self.assertRaisesRegex(
                            ValueError, "owner ended during cleanup"
                        ):
                            with process_liveness(owner):
                                self.run_child(
                                    selected_adapter,
                                    Path(temporary),
                                    "print('finished')",
                                )

                exercise(adapter)

    def test_scope_exit_in_setup_cannot_discard_entering_child_ownership(self):
        scope = process_liveness(lambda: None)
        scope.__enter__()
        factory = mock.Mock(side_effect=AssertionError("child launched"))
        try:
            with mock.patch.object(
                shared_process,
                "trace_subprocess",
                side_effect=lambda *_args, **_kwargs: scope.__exit__(None, None, None),
            ):
                with self.assertRaises(ProcessLivenessError):
                    run_bounded_process(
                        (sys.executable, "-c", "pass"),
                        cwd=None,
                        environment={},
                        timeout_seconds=5,
                        stdout_limit_bytes=1024,
                        stderr_limit_bytes=1024,
                        error_prefix="fixture",
                        process_factory=factory,
                    )
            factory.assert_not_called()
        finally:
            scope.__exit__(None, None, None)

    def test_revocation_in_prelaunch_callbacks_never_calls_the_process_factory(self):
        for cut in ("trace", "sink", "arguments"):
            with self.subTest(cut=cut):

                def exercise(selected_cut):
                    alive = True
                    ownership = create_process_tree_ownership()
                    self.addCleanup(ownership.release)

                    def owner():
                        if not alive:
                            raise ValueError("owner revoked before launch")

                    def revoke(*_args, **_kwargs):
                        nonlocal alive
                        alive = False
                        return True

                    class Sink(io.BytesIO):
                        def writable(self):
                            return revoke()

                    class Arguments:
                        def __iter__(self):
                            revoke()
                            return iter((sys.executable, "-c", "pass"))

                    factory = mock.Mock(side_effect=AssertionError("child launched"))
                    with (
                        mock.patch.object(
                            shared_process,
                            "create_process_tree_ownership",
                            return_value=ownership,
                        ),
                        mock.patch.object(
                            shared_process,
                            "trace_subprocess",
                            side_effect=revoke if selected_cut == "trace" else None,
                        ),
                        mock.patch.object(
                            ownership, "release", wraps=ownership.release
                        ) as released,
                    ):
                        with self.assertRaisesRegex(
                            ValueError, "owner revoked before launch"
                        ):
                            with process_liveness(owner):
                                run_bounded_process(
                                    Arguments()
                                    if selected_cut == "arguments"
                                    else (sys.executable, "-c", "pass"),
                                    cwd=None,
                                    environment={},
                                    timeout_seconds=5,
                                    stdout_limit_bytes=1024,
                                    stderr_limit_bytes=1024,
                                    error_prefix="fixture",
                                    process_factory=factory,
                                    stdout_sink=Sink()
                                    if selected_cut == "sink"
                                    else None,
                                )
                        factory.assert_not_called()
                        released.assert_called_once()

                exercise(cut)

    def test_coding_cli_output_limits_and_streams_keep_their_error_surface(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = self.run_child(
                "coding-cli",
                root,
                "import sys;sys.stdout.buffer.write(b'out');"
                "sys.stderr.buffer.write(b'err')",
            )
            self.assertEqual(
                (result.returncode, result.stdout, result.stderr), (0, b"out", b"err")
            )
            with self.assertRaises(CodingCliError) as error:
                self.run_child("coding-cli", root, "print('x'*2048)")
            self.assertEqual(error.exception.code, "coding_cli.output_limit")
