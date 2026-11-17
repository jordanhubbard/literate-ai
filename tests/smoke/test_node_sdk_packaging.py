"""Exact package readback and actual offline npm pack of isolated SDK fixtures."""

import gzip
import io
import json
import os
import shutil
import tarfile
import unittest
from unittest.mock import patch

from literate_ai.adapters.builders.javascript import (
    discover_node_toolchain,
    discover_npm_toolchain,
)
from literate_ai.adapters.node_sdk_packaging import (
    pack_node_sdk,
    require_node_sdk_tarball,
)
from literate_ai.contracts import ContentIdentity, canonical_identity
from tests.smoke import test_node_sdk_composition as composition_fixtures


class NodeSDKTarballTests(unittest.TestCase):
    def setUp(self):
        self.fixture = composition_fixtures.NodeSDKCompositionTests(
            "test_relocated_cjs_esm_root_subpath_and_error_identity"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.plan = self.fixture.prepare()

    def archive(
        self,
        *,
        omit=None,
        changed=None,
        duplicate=False,
        link=False,
        trailing=False,
        mode=None,
        kind=tarfile.REGTYPE,
    ):
        raw = io.BytesIO()
        with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as archive:
            for item in self.plan.files:
                if item.path == omit:
                    continue
                content = b"changed" if item.path == changed else item.content
                info = tarfile.TarInfo("package/" + item.path)
                info.type = kind
                info.size = len(content)
                info.mode = (
                    mode
                    if mode is not None
                    else (0o755 if item.mode & 0o111 else 0o644)
                )
                archive.addfile(info, io.BytesIO(content))
            if duplicate or link:
                info = tarfile.TarInfo("package/" + self.plan.files[0].path)
                info.mode = 0o644
                if link:
                    info.type = tarfile.SYMTYPE
                    info.linkname = "/etc/private"
                archive.addfile(info, io.BytesIO())
        return gzip.compress(raw.getvalue() + (b"outside" if trailing else b""))

    def test_complete_tarball_is_reopened(self):
        require_node_sdk_tarball(self.plan, self.archive())

    def test_missing_changed_duplicate_link_mode_and_trailing_bytes_rejected(self):
        first = self.plan.files[0].path
        for changes in [
            dict(omit=first),
            dict(changed=first),
            dict(duplicate=True),
            dict(link=True),
            dict(trailing=True),
            dict(mode=0o600),
            dict(kind=tarfile.CONTTYPE),
            dict(kind=tarfile.GNUTYPE_SPARSE),
        ]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                require_node_sdk_tarball(self.plan, self.archive(**changes))

    def test_malformed_and_bounded_compression_rejected(self):
        for content in [b"", b"not gzip", gzip.compress(b"not tar")]:
            with self.subTest(size=len(content)), self.assertRaises(ValueError):
                require_node_sdk_tarball(self.plan, content)
        with patch("literate_ai.adapters.node_sdk_packaging._MAX_ARCHIVE", 1024):
            with self.assertRaisesRegex(ValueError, "decompressed byte bound"):
                require_node_sdk_tarball(self.plan, gzip.compress(b"\x00" * 2048))


@unittest.skipUnless(
    shutil.which("node") and shutil.which("npm"),
    "requires selected local Node/npm tools",
)
class NodeSDKOfflinePackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.environment = dict(os.environ)
        for key in ("NODE_OPTIONS", "NODE_PATH"):
            cls.environment.pop(key, None)
        cls.node = discover_node_toolchain(cls.environment)
        cls.npm = discover_npm_toolchain(
            cls.node,
            cls.environment,
            version_constraint=">=10.0.0",
            constraint_identity=canonical_identity(
                "SDK packaging test tool constraint"
            ).uri,
        )

    def setUp(self):
        self.fixture = composition_fixtures.NodeSDKCompositionTests(
            "test_relocated_cjs_esm_root_subpath_and_error_identity"
        )
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.plan = self.fixture.prepare(
            node=ContentIdentity.parse_uri(self.node.identity),
            packer=ContentIdentity.parse_uri(self.npm.identity),
        )

    def test_actual_offline_pack_exact_payload_and_relocation(self):
        observations = []
        result = pack_node_sdk(
            self.plan,
            self.fixture.fixture.root / "pack-attempt",
            npm=self.npm,
            environment={
                **self.environment,
                "NPM_CONFIG_REGISTRY": "https://must-not-be-contacted.invalid",
                "NODE_OPTIONS": "--require=/must-not-load.cjs",
                "NODE_V8_COVERAGE": str(
                    self.fixture.fixture.root / "outside-pack-coverage"
                ),
            },
            require_current=lambda: None,
            observe_process=observations.append,
        )
        self.assertEqual(len(observations), 1)
        observed = observations[0]
        self.assertEqual(observed.command[: len(self.npm.command)], self.npm.command)
        self.assertIn("--offline", observed.command)
        self.assertIn("--ignore-scripts", observed.command)
        self.assertIsNone(observed.input_identity)
        self.assertEqual(observed.returncode, 0)
        self.assertEqual(json.loads(observed.stdout)[0]["name"], "counter-sdk")
        self.assertFalse((self.fixture.fixture.root / "outside-pack-coverage").exists())
        self.assertEqual(result.plan, self.plan.identity)
        require_node_sdk_tarball(self.plan, result.content)
        # Safe test relocation: use only already verified regular members.
        root = self.fixture.fixture.root / "relocated/node_modules/counter-sdk"
        root.mkdir(parents=True)
        with tarfile.open(fileobj=io.BytesIO(result.content), mode="r:gz") as archive:
            for member in archive:
                destination = root / member.name.removeprefix("package/")
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(archive.extractfile(member).read())
        import subprocess

        for source in [
            "const a=require('counter-sdk'),b=require('counter-sdk/counter');"
            "if(a.CounterError!==b.CounterError||a."
            + self.fixture.symbol
            + "(2,3)!==5)process.exit(1);",
            "import * as a from 'counter-sdk';"
            "import * as b from 'counter-sdk/counter';"
            "if(a.CounterError!==b.CounterError||a."
            + self.fixture.symbol
            + "(2,3)!==5)process.exit(1);",
        ]:
            command = (
                *self.node.command,
                *(["--input-type=module"] if source.startswith("import") else []),
                "--eval",
                source,
            )
            result = subprocess.run(
                command,
                cwd=root.parent.parent,
                env=self.environment,
                capture_output=True,
                timeout=15,
            )
            self.assertEqual(result.returncode, 0, result.stderr.decode())

    def test_owner_cut_never_starts_or_creates_workspace(self):
        workspace = self.fixture.fixture.root / "cut-pack"

        def stopped():
            raise RuntimeError("call owner ended")

        with patch(
            "literate_ai.adapters.node_sdk_packaging.run_bounded_process"
        ) as run:
            with self.assertRaisesRegex(RuntimeError, "call owner ended"):
                pack_node_sdk(
                    self.plan,
                    workspace,
                    npm=self.npm,
                    environment=self.environment,
                    require_current=stopped,
                )
            run.assert_not_called()
        self.assertFalse(workspace.exists())

    def test_observer_projection_mutation_denies_package_publication(self):
        workspace = self.fixture.fixture.root / "observed-pack"
        observations = []

        def observe(value):
            observations.append(value)
            (workspace / "sdk/package.json").write_bytes(b"{}\n")

        with self.assertRaises(ValueError):
            pack_node_sdk(
                self.plan,
                workspace,
                npm=self.npm,
                environment=self.environment,
                require_current=lambda: None,
                observe_process=observe,
            )
        self.assertEqual(len(observations), 1)
        self.assertEqual(observations[0].returncode, 0)
        self.assertTrue(list((workspace / "packed").glob("*.tgz")))

    def test_invalid_observer_cannot_create_packer_workspace(self):
        workspace = self.fixture.fixture.root / "invalid-observed-pack"
        with patch(
            "literate_ai.adapters.node_sdk_packaging.run_bounded_process"
        ) as run:
            with self.assertRaises(TypeError):
                pack_node_sdk(
                    self.plan,
                    workspace,
                    npm=self.npm,
                    environment=self.environment,
                    require_current=lambda: None,
                    observe_process=object(),
                )
            run.assert_not_called()
        self.assertFalse(workspace.exists())

    def test_known_async_observer_cannot_start_or_create_workspace(self):
        async def observe(_value):
            raise AssertionError("must not run")

        workspace = self.fixture.fixture.root / "async-observed-pack"
        with patch(
            "literate_ai.adapters.node_sdk_packaging.run_bounded_process"
        ) as run:
            with self.assertRaisesRegex(TypeError, "synchronous"):
                pack_node_sdk(
                    self.plan,
                    workspace,
                    npm=self.npm,
                    environment=self.environment,
                    require_current=lambda: None,
                    observe_process=observe,
                )
            run.assert_not_called()
        self.assertFalse(workspace.exists())

    def test_observer_return_value_prevents_packed_output_publication(self):
        bodies, observed = [], []

        async def deferred():
            bodies.append("must not run")

        for index, factory in enumerate((deferred, lambda: False)):

            def observe(value, factory=factory):
                observed.append(value)
                return factory()

            workspace = self.fixture.fixture.root / (
                "deferred-observed-pack-" + str(index)
            )
            with (
                self.subTest(index=index),
                self.assertRaisesRegex(TypeError, "return None"),
            ):
                pack_node_sdk(
                    self.plan,
                    workspace,
                    npm=self.npm,
                    environment=self.environment,
                    require_current=lambda: None,
                    observe_process=observe,
                )
            self.assertTrue(list((workspace / "packed").glob("*.tgz")))
        self.assertEqual(len(observed), 2)
        self.assertTrue(all(value.returncode == 0 for value in observed))
        self.assertFalse(bodies)
