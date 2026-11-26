"""Explicit controlled-source/distribution scope for the actual A→B journey."""

import hashlib
import io
import json
import os
import shlex
from contextlib import ExitStack, contextmanager
from pathlib import Path
from unittest import mock

from literate_ai.adapters import project_initialization as initialization
from literate_ai.adapters import retained_provider_authority as provider_authority
from literate_ai.adapters import standard_lifecycle_binding as binding
from literate_ai.cli import main
from literate_ai.cli import rebuild as rebuild_cli
from literate_ai.contracts import (
    ProjectInitializationOrigin,
    ProjectTestReceiptPolicy,
    StandardProjectLifecycleDriver,
    load_current_standard_lifecycle_policy,
)

# This program extension is authored BEFORE the first A source request. The SAME
# executable bytes/path serve A and B. This does not replace any native result.
GENERIC_SOURCE_EXTENSION = r"""
if sys.argv[1:] != ["--version"]:
 import ast
 marker="## Required importable library artifact"
 section=request.split(marker,1)[1].split("```json",1)[1].split("```",1)[0]
 own=json.loads(section)
 if own["package"] == "qualified_consumer":
  body=body.replace("qualified_fixture","qualified_consumer")
  body=body.replace("qualified-fixture","qualified-consumer")
  value=('#[cfg(feature="checked")]\n'
         'pub fn answer(input: &str) -> String { '
         'qualified_fixture::answer(input) }\n')
  parsed=ast.parse(body)
  assignments=(row for row in parsed.body if isinstance(row,ast.Assign))
  node=next(row for row in assignments if any(
   isinstance(name,ast.Name) and name.id=="LIBRARY" for name in row.targets))
  lines=body.splitlines(keepends=True)
  lines[node.lineno-1:node.end_lineno]=["LIBRARY = "+repr(value)+"\n"]
  body="".join(lines)
 else:
  assert own["package"] == "qualified_fixture"
"""


@contextmanager
def actual_public_native_source_scope(base, cargo, rustc, host_environment):
    """Use only existing explicitly synthetic SOURCE observation seams."""
    base = Path(base)
    home, cargo_home = base / "home", base / "cargo-home"
    home.mkdir()
    cargo_home.mkdir()
    environment = {
        key: value
        for key, value in host_environment.items()
        if not key.startswith(("LITAI_", "GIT_"))
    }
    environment.update(
        CODING_CLI="claude",
        HOME=str(home),
        CARGO_HOME=str(cargo_home),
        CARGO_NET_OFFLINE="true",
        CARGO_BUILD_JOBS="2",
        CARGO_INCREMENTAL="0",
        CARGO=shlex.quote(cargo.command[0]),
        RUSTC=shlex.quote(rustc.command[0]),
        BUILD_DIR=str(base / "build"),
        OBJ_DIR=str(base / "obj"),
    )
    distribution = binding.InstalledFrameworkDistribution(
        "literate-ai",
        "1.1.0",
        (
            binding.InstalledFrameworkDistributionMember(
                "literate_ai/__init__.py", 1, "sha256:" + "a" * 64
            ),
        ),
    )
    policy = load_current_standard_lifecycle_policy()
    driver = StandardProjectLifecycleDriver(distribution.identity, policy.identity)
    receipt = ProjectTestReceiptPolicy(
        policy.policy_id,
        policy.policy_version,
        driver.identity,
        policy.required_evidence_kinds,
        policy.minimum_test_count,
    )
    origin = ProjectInitializationOrigin(
        repository_url="https://example.invalid/disposable-source-fixture.git",
        git_revision="a" * 40,
        distribution_name="literate-ai",
        distribution_version="1.1.0",
    )
    original_resolve = binding.resolve_standard_project_lifecycle_driver

    def resolve(value, **options):
        options.setdefault("distribution_observer", lambda: distribution)
        return original_resolve(value, **options)

    calls, agent_hash = [], []

    def invoke(arguments):
        if arguments[:2] == ["spec", "qualify"] and not agent_hash:
            agent = base / "producer/tools/claude"
            assert agent.is_file() and not agent.is_symlink()
            assert not (base / "producer/source-requests.jsonl").exists()
            text = agent.read_text()
            marker = 'exec(compile(body,__file__,"exec"),'
            assert text.count(marker) == 1
            text = text.replace(marker, GENERIC_SOURCE_EXTENSION + "\n" + marker, 1)
            agent.write_text(text)
            agent_hash.append(hashlib.sha256(agent.read_bytes()).hexdigest())
        out, err = io.StringIO(), io.StringIO()
        # The helper may deliberately advance PATH to its one original source
        # executable before the first qualification. Keep direct current-authority
        # reads between CLI calls under exactly that same private environment.
        os.environ.clear()
        os.environ.update(environment)
        code = main(["--json", *arguments], stdout=out, stderr=err)
        envelope = json.loads(out.getvalue() if code == 0 else err.getvalue())
        calls.append((arguments[:2], code))
        (base / f"call-{len(calls)}.stdout").write_text(out.getvalue())
        (base / f"call-{len(calls)}.stderr").write_text(err.getvalue())
        return code, envelope

    with ExitStack() as stack:
        stack.enter_context(mock.patch.dict(os.environ, environment, clear=True))
        stack.enter_context(
            mock.patch.object(
                binding, "resolve_standard_project_lifecycle_driver", resolve
            )
        )
        stack.enter_context(
            mock.patch.object(
                rebuild_cli, "resolve_standard_project_lifecycle_driver", resolve
            )
        )
        stack.enter_context(
            mock.patch.object(
                provider_authority, "resolve_standard_project_lifecycle_driver", resolve
            )
        )
        stack.enter_context(
            mock.patch.object(
                initialization,
                "observe_installed_framework_distribution",
                lambda: distribution,
            )
        )
        stack.enter_context(
            mock.patch.object(
                initialization, "_installed_distribution_origin", lambda: origin
            )
        )
        yield environment, invoke, driver, receipt, calls, agent_hash
