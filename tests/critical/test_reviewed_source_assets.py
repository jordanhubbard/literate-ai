from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from literate_ai.adapters.authority import FileAuthorityProjectionStore
from literate_ai.adapters.component_markdown import parse_component_markdown
from literate_ai.cli import main
from literate_ai.cli._wire import component_graph_from_wire, component_graph_to_wire
from literate_ai.contracts import ContentIdentity
from literate_ai.contracts.component_locking import ComponentLock
from literate_ai.contracts.component_locking.authoring import ComponentAssetSelector
from literate_ai.source_to_specification import canonical_digest
from literate_ai.source_to_specification.errors import SourceToSpecificationError
from literate_ai.source_to_specification.inventory import (
    SourceFileClassification,
    inventory_source,
)
from literate_ai.source_to_specification.promotion_materialization import (
    PromotionInputKind,
    SourcePromotionError,
    assess_source_exclusion,
    verify_source_promotion_evidence,
)
from literate_ai.source_to_specification.reviewed_assets import (
    validate_reviewed_asset_inventory,
)
from tests.support.fixtures_test_schema_catalog import SchemaCatalog

DATA = b'["alpha","beta"]\n'
CODE = (
    "import words from './words.json' with {type:'json'};\n"
    "export function containsWord(word) { return words.includes(word); }\n"
)


def asset(**changes):
    selector = ComponentAssetSelector(
        asset_id="words",
        source="words.json",
        path="source/word_fixture/words.json",
        role="runtime-data",
        media_type="application/json",
        pin=ContentIdentity.parse_uri("sha256:" + hashlib.sha256(DATA).hexdigest()),
    )
    return replace(selector, **changes)


def graph_value():
    return {
        "source_snapshot_id": "sha256:" + "a" * 64,
        "root_coordinate": "fixture/data",
        "nodes": [
            {
                "coordinate": "fixture/data",
                "title": "Data",
                "kind": "library",
                "profiles": ["default"],
                "provided_capabilities": ["fixture.lookup"],
                "capability_contracts": [
                    {
                        "name": "fixture.lookup",
                        "contract": "Read the pinned word list.",
                        "evidence_ids": ["source:lookup"],
                    }
                ],
                "entrypoints": [],
                "build_needs": ["implementation.language-ecosystem"],
                "source_paths": ["lookup.mjs", "words.json"],
                "observation_ids": ["observation:lookup"],
                "evidence_ids": ["source:lookup"],
            }
        ],
        "edges": [],
    }


def invoke(*args):
    out, err = io.StringIO(), io.StringIO()
    code = main(args, stdout=out, stderr=err)
    return code, out.getvalue(), err.getvalue()


class ReviewedSourceAssetTests(unittest.TestCase):
    def test_asset_free_identity_and_wire_are_unchanged(self):
        value = graph_value()
        graph = component_graph_from_wire(value)
        self.assertEqual(graph.identity, canonical_digest(value))
        self.assertEqual(component_graph_to_wire(graph), value)
        value["nodes"][0]["assets"] = []
        self.assertEqual(component_graph_from_wire(value).identity, graph.identity)

    def test_asset_roundtrip_and_every_selector_field_bind_identity(self):
        value = graph_value()
        value["nodes"][0]["assets"] = [asset().to_dict()]
        graph = component_graph_from_wire(value)
        self.assertEqual(component_graph_to_wire(graph), value)
        self.assertNotEqual(
            graph.identity, component_graph_from_wire(graph_value()).identity
        )
        for changes in [
            {"asset_id": "other"},
            {"source": "other.json"},
            {"path": "source/word_fixture/other.json"},
            {"role": "test-fixture"},
            {"media_type": "application/octet-stream"},
            {"pin": ContentIdentity.parse_uri("sha256:" + "0" * 64)},
        ]:
            with self.subTest(changes=changes):
                changed = copy.deepcopy(value)
                changed["nodes"][0]["assets"] = [asset(**changes).to_dict()]
                self.assertNotEqual(
                    component_graph_from_wire(changed).identity, graph.identity
                )

    def test_unknown_fields_missing_pins_unsafe_sources_and_collisions_fail(self):
        value = graph_value()
        value["nodes"][0]["unexpected_asset_field"] = []
        with self.assertRaises(ValueError):
            component_graph_from_wire(value)
        for selectors in [
            [asset(pin=None)],
            [asset(source="https://example.invalid/words.json")],
            [asset(path="source/.git/data.json")],
            [asset(), asset(asset_id="z")],
            [asset(), asset(asset_id="z", path="source/word_fixture/words.json/child")],
        ]:
            with self.subTest(selectors=selectors):
                value = graph_value()
                value["nodes"][0]["assets"] = [item.to_dict() for item in selectors]
                with self.assertRaises(SourceToSpecificationError):
                    component_graph_from_wire(value)

    def test_inventory_binding_rejects_unknown_changed_and_sensitive_assets(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "lookup.mjs").write_text(CODE)
            (root / "words.json").write_bytes(DATA)
            inventory = inventory_source(root)
            value = graph_value()
            value["source_snapshot_id"] = inventory.identity
            value["nodes"][0]["assets"] = [asset().to_dict()]
            graph = component_graph_from_wire(value)
            validate_reviewed_asset_inventory(graph, inventory)
            for selector, expected in [
                (asset(source="missing.json"), "component_graph.asset_source_unknown"),
                (
                    asset(pin=ContentIdentity.parse_uri("sha256:" + "0" * 64)),
                    "component_graph.asset_pin_mismatch",
                ),
            ]:
                changed = copy.deepcopy(value)
                changed["nodes"][0]["assets"] = [selector.to_dict()]
                with self.assertRaises(SourceToSpecificationError) as raised:
                    validate_reviewed_asset_inventory(
                        component_graph_from_wire(changed), inventory
                    )
                self.assertEqual(raised.exception.code, expected)
            sensitive = replace(
                inventory,
                entries=tuple(
                    replace(entry, classification=SourceFileClassification.SENSITIVE)
                    if entry.path == "words.json"
                    else entry
                    for entry in inventory.entries
                ),
            )
            with self.assertRaises(SourceToSpecificationError) as raised:
                validate_reviewed_asset_inventory(
                    replace(graph, source_snapshot_id=sensitive.identity), sensitive
                )
            self.assertEqual(
                raised.exception.code, "component_graph.asset_source_sensitive"
            )

    def test_public_review_promotion_and_provenance_keep_exact_asset(self):
        self.promote_fixture(DATA)

    def test_large_json_asset_remains_exact(self):
        self.promote_fixture(
            json.dumps([f"word-{index:06d}" for index in range(16000)]).encode()
        )

    def test_binary_asset_remains_exact(self):
        self.promote_fixture(bytes(range(256)) * 4)

    def test_policy_review_and_separate_opt_in_keep_exact_asset(self):
        self.promote_fixture(DATA, policy=True)

    def promote_fixture(self, data, *, policy=False):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            (source / "lookup.mjs").write_text(CODE)
            (source / "words.json").write_bytes(data)
            key = root / "trust.key"
            key.write_bytes(b"fixture-only-reviewed-asset-key-32-bytes")
            paths = {
                name: root / (name + ".json")
                for name in ["attestation", "bundle", "review", "graph"]
            }
            status, text, errors = invoke(
                "spec",
                "attest",
                str(source),
                "--signer",
                "fixture-reviewer",
                "--machine",
                "fixture",
                "--key",
                str(key),
            )
            self.assertEqual((status, errors), (0, ""))
            paths["attestation"].write_text(text)
            status, text, errors = invoke(
                "spec",
                "derive",
                str(source),
                "--skills",
                str(
                    Path(__file__).resolve().parents[2]
                    / "skills/source-to-specification"
                ),
                "--attestation",
                str(paths["attestation"]),
                "--trust-key",
                str(key),
                "--translator",
                "static",
            )
            self.assertEqual((status, errors), (0, ""))
            paths["bundle"].write_text(text)
            result = json.loads(text)["result"]["result"]
            definition = result["component_definition_draft"]
            references = sorted(
                {
                    ref["evidence_id"]
                    for obs in result["observations"]
                    for ref in obs["evidence"]
                }
            )
            value = graph_value()
            value["source_snapshot_id"] = result["request"]["source_snapshot_id"]
            value["root_coordinate"] = definition["coordinate"]
            node = value["nodes"][0]
            node.update(
                coordinate=definition["coordinate"],
                title=definition["title"],
                source_paths=sorted(
                    {
                        ref["path"]
                        for obs in result["observations"]
                        for ref in obs["evidence"]
                        if ref["path"]
                    }
                ),
                observation_ids=sorted(
                    obs["observation_id"] for obs in result["observations"]
                ),
                evidence_ids=references,
            )
            node["capability_contracts"][0]["evidence_ids"] = references
            node["assets"] = [
                asset(
                    pin=ContentIdentity.parse_uri(
                        "sha256:" + hashlib.sha256(data).hexdigest()
                    )
                ).to_dict()
            ]
            paths["graph"].write_text(json.dumps(value))
            review_args = [
                "spec",
                "review",
                str(paths["bundle"]),
                "--actor",
                "fixture-reviewer",
                "--reason",
                "Accept the fixture word-list contract.",
                "--key",
                str(key),
                "--component-graph",
                str(paths["graph"]),
            ]
            if policy:
                review_args.extend(["--authority", "authorized-policy"])
            for item in result["uncertainty"]["items"]:
                review_args.extend(["--resolve", item["uncertainty_id"]])
            status, text, errors = invoke(*review_args)
            self.assertEqual((status, errors), (0, ""))
            paths["review"].write_text(text)
            self.assertEqual(
                json.loads(text)["result"]["review"]["component_graph_draft"]["nodes"][
                    0
                ]["assets"],
                node["assets"],
            )
            bad = copy.deepcopy(value)
            bad["nodes"][0]["assets"] = [
                asset(pin=ContentIdentity.parse_uri("sha256:" + "0" * 64)).to_dict()
            ]
            paths["graph"].write_text(json.dumps(bad))
            status, _, errors = invoke(*review_args)
            self.assertNotEqual(status, 0)
            self.assertIn("component_graph.asset_pin_mismatch", errors)
            project, accepted = root / "project", root / "accepted"
            accept_args = [
                "spec",
                "accept",
                str(source),
                str(paths["bundle"]),
                "--review",
                str(paths["review"]),
                "--target",
                str(accepted),
                "--trust-key",
                str(key),
                "--project-target",
                str(project),
                "--qualification-target",
                "asset-host",
                "--flavor=-flavor://literate-ai/build-bazel",
                "--flavor=+flavor://literate-ai/lang-javascript",
                "--flavor=+flavor://literate-ai/os-macos",
            ]
            if policy:
                status, _, errors = invoke(*accept_args)
                self.assertNotEqual(status, 0)
                self.assertIn("promotion.authority_denied", errors)
                self.assertFalse(project.exists())
                self.assertFalse(accepted.exists())
                accept_args.append("--allow-authorized-policy-review")
            for mutation in ["changed", "missing", "symlink"]:
                with self.subTest(mutation=mutation):
                    original = source / "words.json"
                    original.unlink()
                    if mutation == "changed":
                        original.write_bytes(data + b"changed")
                    elif mutation == "symlink":
                        outside = root / "outside.json"
                        outside.write_bytes(data)
                        original.symlink_to(outside)
                    status, _, errors = invoke(*accept_args)
                    self.assertNotEqual(status, 0, errors)
                    self.assertFalse(project.exists())
                    self.assertFalse(accepted.exists())
                    if original.exists() or original.is_symlink():
                        original.unlink()
                    original.write_bytes(data)
            status, _, errors = invoke(*accept_args)
            self.assertEqual((status, errors), (0, ""))
            component = next((project / "components").glob("*/component.md"))
            self.assertEqual((component.parent / "assets/words").read_bytes(), data)
            self.assertIn("source/word_fixture/words.json", component.read_text())
            status, text, errors = invoke(
                "lock", str(component.parent), "--target", "asset-host", "--check"
            )
            self.assertEqual((status, errors), (0, ""))
            lock = ComponentLock.from_dict(
                json.loads((component.parent / "component.lock.json").read_text()),
                authorings=(
                    parse_component_markdown(
                        component, component.read_text(), project_root=project
                    ),
                ),
            )
            root_node = next(
                item
                for item in lock.nodes
                if item.revision.identity == lock.root_revision
            )
            self.assertEqual(len(root_node.revision.assets), 1)
            resolved = root_node.revision.assets[0]
            self.assertEqual(resolved.selector.path, "source/word_fixture/words.json")
            self.assertEqual(resolved.blob.size, len(data))
            self.assertEqual(resolved.blob.digest, hashlib.sha256(data).hexdigest())
            self.assertEqual(resolved.blob.media_type, "application/json")
            status, text, errors = invoke(
                "plan", str(component.parent), "--target", "asset-host"
            )
            self.assertEqual((status, errors), (0, ""))
            self.assertNotIn(base64.b64encode(data).decode(), text)
            projection = FileAuthorityProjectionStore(project).current(
                "component://" + definition["coordinate"]
            )
            verified = verify_source_promotion_evidence(project, projection)
            self.assertEqual(len(verified.authored_asset_bindings), 1)
            records = [
                value
                for path in (project / "provenance/source-promotion").rglob("*.json")
                for value in (json.loads(path.read_text()),)
                if value.get("schema")
                == "urn:literate-ai:schema:v4:source-promotion-provenance"
            ]
            self.assertEqual(len(records), 1)
            SchemaCatalog(Path(__file__).resolve().parents[2] / "schemas/v2").validate(
                records[0]["schema"], records[0]
            )
            audit = next(
                item
                for item in verified.promotion_input_audits
                if any(
                    entry.kind is PromotionInputKind.AUTHORED_ASSET
                    for entry in item.entries
                )
            )
            with self.assertRaises(SourcePromotionError):
                assess_source_exclusion(audit, inventory_source(source))
            assessment = assess_source_exclusion(
                audit,
                inventory_source(source),
                authored_asset_bindings=verified.authored_asset_bindings,
            )
            self.assertTrue(assessment.source_excluded)
            self.assertEqual(
                assessment.reviewed_asset_paths,
                (verified.authored_asset_bindings[0].project_path,),
            )
            for changes in [
                {"byte_count": len(data) + 1},
                {"source_path": "missing.json"},
                {"content_identity": "sha256:" + "0" * 64},
            ]:
                with self.subTest(binding_tamper=changes):
                    with self.assertRaises(SourcePromotionError):
                        assess_source_exclusion(
                            audit,
                            inventory_source(source),
                            authored_asset_bindings=(
                                replace(verified.authored_asset_bindings[0], **changes),
                            ),
                        )
            self.assertEqual((source / "lookup.mjs").read_text(), CODE)
            self.assertEqual((source / "words.json").read_bytes(), data)
