"""Reference Standard action receiver composed from one private operator config.

Receiver mode (the worker command an operator registers)::

    python -I -m literate_ai.standard_receiver --config /private/receiver.json

composes configured phase workers for portable Standard projects and serves one
lifecycle action exactly like `literate_ai.action_worker`; receiver mode flags
the controller appends (for example `--describe`) pass through unchanged. Each
phase runs in a supervised child that re-enters this module with `--child`, the
same config and its byte identity; a changed config refuses to run. The
operator still owns provisioning, placement and grants (ADR 0044).
"""

import argparse
import sys

from literate_ai.contracts import ComponentCommandPhase, canonical_identity

_CHILD_PHASES = ("BUILD", "TEST", "EXECUTE", "ACCEPT", "FINALIZE")


def _launcher(config, phase, code_identity):
    from literate_ai.adapters.builders.python import discover_python_toolchain
    from literate_ai.adapters.lifecycle.standard_local import (
        LocalComponentToolBinding,
    )

    runtime = discover_python_toolchain(pinned_command=(sys.executable,))

    def guard():
        runtime.require_unchanged()
        config.require_unchanged()

    return LocalComponentToolBinding(
        sys.executable,
        (
            "-I",
            "-B",
            "-m",
            "literate_ai.standard_receiver",
            "--child",
            phase,
            "--config",
            str(config.path),
            "--config-identity",
            config.identity.uri,
        ),
        authority_identity=canonical_identity(
            {
                "schema": "literate-ai/standard-receiver-child@1",
                "runtime": runtime.identity,
                "code": code_identity.uri,
                "config": config.identity.uri,
                "phase": phase,
            }
        ),
        _authority_guard=guard,
    )


def _workers(config):
    from literate_ai.adapters.action_accept_worker import ConfiguredAcceptWorker
    from literate_ai.adapters.action_build_worker import ConfiguredBuildWorker
    from literate_ai.adapters.action_capabilities import receiver_code_identity
    from literate_ai.adapters.action_execute_worker import ConfiguredExecuteWorker
    from literate_ai.adapters.action_package_worker import ConfiguredPackageWorker
    from literate_ai.adapters.action_test_worker import ConfiguredTestWorker
    from literate_ai.adapters.packaging import DirectoryPackageAdapter
    from literate_ai.adapters.standard_receiver_runtime import ReceiverTools

    workers = {}
    environment = dict(config.child_environment)
    command_phases = {"BUILD", "TEST", "EXECUTE", "ACCEPT", "FINALIZE"} & config.phases
    if command_phases:
        code = receiver_code_identity()
        tools = ReceiverTools(config)
        for phase, keyword, worker_type in (
            ("BUILD", "build_worker", ConfiguredBuildWorker),
            ("TEST", "test_worker", ConfiguredTestWorker),
            ("EXECUTE", "execute_worker", ConfiguredExecuteWorker),
        ):
            if phase in command_phases:
                workers[keyword] = worker_type(
                    _launcher(config, phase, code),
                    tools.bindings,
                    environment=environment,
                )
        if "ACCEPT" in command_phases:
            workers["accept_worker"] = ConfiguredAcceptWorker(
                _launcher(config, "ACCEPT", code), environment=environment
            )
        if "FINALIZE" in command_phases:
            from literate_ai.adapters.standard_receiver_finalize import (
                configured_finalize_worker,
            )

            workers["finalize_worker"] = configured_finalize_worker(
                config, _launcher(config, "FINALIZE", code), code, tools
            )
    if "PACKAGE" in config.phases:
        workers["package_worker"] = ConfiguredPackageWorker(
            canonical_identity({"packager": "local-directory-package@1"}),
            DirectoryPackageAdapter,
            config.require_unchanged,
        )
    return workers


def _receive(config, passthrough):
    from literate_ai.action_worker import main as receive

    argv = ["--cas", str(config.cas), "--workspace", str(config.workspace)]
    if config.source_cas_url is not None:
        argv += ["--source-cas-url", config.source_cas_url]
        if config.source_token_env is not None:
            argv += ["--source-token-env", config.source_token_env]
        if config.allow_http:
            argv.append("--allow-http")
    return receive([*argv, *passthrough], **_workers(config))


def _child(config, phase):
    from literate_ai import accept_worker, build_worker, execute_worker, test_worker
    from literate_ai.adapters.standard_receiver_runtime import (
        ReceiverTools,
        accept_runtime_factory,
        portable_runtime_factory,
    )

    if phase not in config.phases or phase not in _CHILD_PHASES:
        print("phase is not enabled in this receiver", file=sys.stderr)
        return 2
    tools = ReceiverTools(config)
    if phase == "FINALIZE":
        from literate_ai.adapters.standard_receiver_finalize import (
            run_finalize_child,
        )

        return run_finalize_child(config, tools)
    if phase == "ACCEPT":
        return accept_worker.main([], runtime_factory=accept_runtime_factory(tools))
    entry = {
        "BUILD": build_worker,
        "TEST": test_worker,
        "EXECUTE": execute_worker,
    }[phase]
    return entry.main(
        [],
        runtime_factory=portable_runtime_factory(tools, ComponentCommandPhase[phase]),
    )


def main(argv=None):
    from literate_ai.adapters.standard_receiver_config import (
        StandardReceiverConfigError,
        load_standard_receiver_config,
    )

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--child", choices=_CHILD_PHASES)
    parser.add_argument("--config-identity")
    parser.add_argument(
        "--print-profiles",
        action="store_true",
        help="print the private profiles to pin in controller configuration",
    )
    parser.add_argument(
        "--issue-finalize-grant",
        metavar="REQUEST",
        help="authorize exactly one described FINALIZE grant request",
    )
    parser.add_argument("--actor")
    parser.add_argument("--reason")
    parser.add_argument("--expires-in", type=int, default=3600)
    args, passthrough = parser.parse_known_args(argv)
    try:
        config = load_standard_receiver_config(args.config)
        if args.child is not None and args.config_identity != config.identity.uri:
            raise StandardReceiverConfigError("receiver configuration changed")
    except StandardReceiverConfigError as exc:
        print(f"standard receiver refused: {exc}", file=sys.stderr)
        return 2
    if args.print_profiles:
        import json

        workers = _workers(config)
        finalize = workers.get("finalize_worker")
        print(
            json.dumps(
                {
                    "finalize_profile": None
                    if finalize is None
                    else finalize.identity.uri
                },
                sort_keys=True,
            )
        )
        return 0
    if args.issue_finalize_grant is not None:
        from literate_ai.adapters.action_finalize_issue import (
            FinalizeGrantIssueError,
            issue_finalize_grant,
        )

        if config.finalize is None:
            print("FINALIZE is not enabled in this receiver", file=sys.stderr)
            return 2
        try:
            grant = issue_finalize_grant(
                args.issue_finalize_grant,
                config.finalize.grant_path,
                actor=args.actor,
                reason=args.reason,
                expires_in_seconds=args.expires_in,
            )
        except (FinalizeGrantIssueError, OSError) as exc:
            print(f"FINALIZE grant refused: {exc}", file=sys.stderr)
            return 2
        print(grant.authorization_id)
        return 0
    if args.child is not None:
        if passthrough:
            print("child mode accepts no extra arguments", file=sys.stderr)
            return 2
        return _child(config, args.child)
    return _receive(config, passthrough)


if __name__ == "__main__":
    raise SystemExit(main())
