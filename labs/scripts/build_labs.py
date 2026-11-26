#!/usr/bin/env python3
"""Bundle authored lab sources, with exact offline source inspection."""

from __future__ import annotations

import hashlib
import html
import json
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><link rel="icon" href="data:,">
<title>{title}</title><style>{css}</style></head><body>
<div class="shell"><aside class="lesson"><div class="eyebrow" data-level></div>
<h1 data-title></h1><p data-subtitle></p><p class="learning" data-learning></p>
<h2 class="flow-title">Lesson flow (illustrative)</h2><p class="inventory" data-inventory></p>
<div data-graph></div><div class="authority" data-authority>Select a role to inspect its responsibility.</div>
<details data-spec-details><summary>Readable lab specification — component.md</summary><pre class="spec" data-spec></pre></details>
<p class="footer">Authored JavaScript and CSS bundled into one offline file. This diagram is not a resolved Component DAG; this artifact has no lifecycle acceptance receipt.</p>
</aside><main class="stage"><header class="stage-head"><h2>{stage}</h2><span class="badge">offline artifact</span></header>
<section class="viewport"><canvas aria-label="Lab visual output"></canvas><div class="flash"></div></section>
<div class="controls" data-controls></div><div class="readout" data-readout>ready</div>
<section class="harness-panel" aria-label="Surrounding inputs and harness"><h2>Surrounding inputs &amp; harness</h2>
<p>The lesson flow above describes lab responsibilities. These are the external authoring inputs and the harness boundaries for this actual bundle.</p>
<div class="harness-grid" data-harness></div></section></main></div>
<section class="source-inspector"><h2>Exact bundled source</h2>
<p>Complete authored inputs, including shared support, the HTML builder and project/catalog context. The specification is not the entire implementation. SHA-256 identifies bytes; it does not certify generation or acceptance.</p>
<div data-sources></div></section>
<script>{runtime}</script><script>{main}</script>
<script id="lab-config" type="application/json">{config}</script>
<script>LitLab.mount(JSON.parse(document.getElementById('lab-config').textContent),window.startLab);</script>
</body></html>
"""


class CanonicalLab(NamedTuple):
    project: Path
    component: Path
    manifest_bytes: bytes
    lock_bytes: bytes
    manifest: dict
    lock: dict


def _project_file(root: Path, uri: str) -> Path:
    relative = Path(uri)
    path = root / relative
    if (
        relative.is_absolute()
        or ".." in relative.parts
        or "\\" in uri
        or path.is_symlink()
        or not path.resolve(strict=True).is_relative_to(root.resolve(strict=True))
        or not path.is_file()
    ):
        raise ValueError(
            f"project input must be a regular file inside its owner: {uri}"
        )
    return path


def _canonical_lab(lab: Path) -> CanonicalLab:
    manifest_path = _project_file(lab, "project/literate.project.json")
    project = manifest_path.parent
    manifest_bytes = manifest_path.read_bytes()
    manifest = json.loads(manifest_bytes)
    declared = manifest["repository_policy"]["default_component"]
    lock_path = _project_file(project, f"{declared}/component.lock.json")
    lock_bytes = lock_path.read_bytes()
    return CanonicalLab(
        project,
        lock_path.parent,
        manifest_bytes,
        lock_bytes,
        manifest,
        json.loads(lock_bytes),
    )


def _authoring_references(revision: dict) -> list[dict]:
    return revision["authoring_inputs"] + [
        revision["workflow_definition"],
        revision["routing_policy"],
    ]


def source_records(lab: Path, authority: CanonicalLab | None = None) -> list[dict]:
    if authority is None and (lab / "project/literate.project.json").exists():
        authority = _canonical_lab(lab)
    common = [
        lab / "lab.json",
        lab / "main.js",
        ROOT / "shared/lab.css",
        ROOT / "shared/lab-runtime.js",
        ROOT / "scripts/build_labs.py",
    ]
    if authority is None:
        paths = [
            lab / "component.md",
            *common,
            ROOT.parent / "literate.project.json",
            ROOT.parent / "flavors/lang-javascript/flavor.md",
        ]
        bound = {}
        observed = {}
    else:
        project, component = authority.project, authority.component
        manifest_path = project / "literate.project.json"
        lock_path = component / "component.lock.json"
        paths = [
            _project_file(component, "component.md"),
            *common,
            manifest_path,
            lock_path,
        ]
        observed = {
            manifest_path: authority.manifest_bytes,
            lock_path: authority.lock_bytes,
        }
        bound = {}
        for node in authority.lock["nodes"]:
            revision = node["revision"]
            references = [(project, ref) for ref in _authoring_references(revision)]
            if (
                node["target_flavor_selection"]["component_revision"]
                == authority.lock["root_revision"]
            ):
                references.extend(
                    (component, ref)
                    for ref in revision["specifications"]
                    if ref["uri"] == "component.md"
                )
            for base, ref in references:
                path = _project_file(base, ref["uri"])
                identity = ref["identity"]
                digest = identity["digest"]
                if (
                    identity["algorithm"] != "sha256"
                    or bound.get(path, digest) != digest
                ):
                    raise ValueError(f"invalid locked content reference: {ref['uri']}")
                bound[path] = digest
                paths.append(path)
        # Flavor revisions identify resolved definitions, not raw Markdown bytes.
        # Display the selected Flavor documents as source context.
        for selector in authority.manifest["default_flavor_selectors"]:
            paths.append(
                _project_file(
                    project, f"flavors/{selector.rsplit('/', 1)[-1]}/flavor.md"
                )
            )

    records = []
    for path in dict.fromkeys(paths):
        relative = path.relative_to(ROOT.parent).as_posix()
        raw = observed[path] if path in observed else path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if path in bound and bound[path] != digest:
            raise ValueError(f"locked content drift: {relative}")
        records.append(
            {"path": relative, "sha256": digest, "content": raw.decode("utf-8")}
        )
    return records


def build_page(lab: Path) -> str:
    config = json.loads((lab / "lab.json").read_text())
    canonical = (lab / "project/literate.project.json").exists()
    if canonical:
        return build_canonical_page(lab, config)
    config["spec"] = (lab / "component.md").read_bytes().decode("utf-8")
    project = json.loads((ROOT.parent / "literate.project.json").read_text())
    lab_path = lab.relative_to(ROOT.parent).as_posix()

    def registered(roots: list[str]) -> bool:
        return any(
            lab_path == root or lab_path.startswith(root.rstrip("/") + "/")
            for root in roots
        )

    config["harness"] = {
        "project": project["project_id"],
        "version": project["version"],
        "documentation_root": registered(project["documentation_roots"]),
        "component_root": registered(project["component_roots"]),
        "selected_flavors": [],
        "language_selection": "Authored JavaScript; chosen manually, not resolved from a Flavor.",
        "available_flavor": "flavors/lang-javascript/flavor.md",
    }
    config["sources"] = source_records(lab)
    # JSON is data, never executable code; escape script end tags in source text.
    serialized = json.dumps(config, separators=(",", ":")).replace("<", "\\u003c")
    return TEMPLATE.format(
        title=html.escape(config["title"]),
        stage=html.escape(config["stage"]),
        css=(ROOT / "shared/lab.css").read_text(),
        runtime=(ROOT / "shared/lab-runtime.js").read_text(),
        main=(lab / "main.js").read_text(),
        config=serialized,
    )


def build_canonical_page(lab: Path, config: dict) -> str:
    authority = _canonical_lab(lab)
    manifest, lock = authority.manifest, authority.lock
    sources = source_records(lab, authority)
    config["sources"] = sources
    config["spec"] = sources[0]["content"]
    config["canonical"] = True
    nodes, edges, known = [], [], set()

    def add(identity: str, label: str, detail: str) -> None:
        if identity not in known:
            nodes.append({"id": identity, "label": label, "detail": detail})
            known.add(identity)

    def key(identity: dict) -> str:
        return identity["digest"]

    for node in lock["nodes"]:
        revision = node["revision"]
        # Canonical JSON hashing is not needed: root/edge identity fields in the
        # lock already bind the Component revision.
        identity = key(node["target_flavor_selection"]["component_revision"])
        coordinate = revision["coordinate"]
        add(
            identity,
            coordinate["name"],
            "Component "
            + coordinate["namespace"]
            + "/"
            + coordinate["name"]
            + "; specification set "
            + revision["specification_set_identity"]["digest"],
        )
        for slot in node["target_flavor_selection"]["slots"]:
            for selection in slot["selected"]:
                selected = key(selection["flavor_revision"])
                add(
                    selected,
                    "Flavor: " + selection["value"],
                    "Selected Flavor for "
                    + slot["slot"]["axis"]
                    + "; revision "
                    + selected,
                )
                edges.append([selected, identity])
        for ref in _authoring_references(revision):
            ref_id = key(ref["identity"])
            label = (
                ref["uri"].split("/")[-2]
                if ref["uri"].endswith("SKILL.md")
                else Path(ref["uri"]).stem
            )
            add(
                ref_id,
                label,
                ref["kind"] + ": " + ref["uri"] + "; content SHA-256 " + ref_id,
            )
            edges.append([ref_id, identity])
    for edge in lock["edges"]:
        edges.append([key(edge["source_revision"]), key(edge["target_revision"])])
    config["nodes"], config["edges"] = nodes, edges
    selected = sorted(
        {
            selection["value"]
            for node in lock["nodes"]
            for slot in node["target_flavor_selection"]["slots"]
            for selection in slot["selected"]
        }
    )
    config["harness"] = {
        "project": manifest["project_id"],
        "version": manifest["version"],
        "component_count": len(lock["nodes"]),
        "selected_flavors": selected,
        "component_root": True,
        "documentation_root": True,
        "framework_version": "1.3.1",
        "lock_sha256": hashlib.sha256(authority.lock_bytes).hexdigest(),
    }
    serialized = json.dumps(config, separators=(",", ":")).replace("<", "\\u003c")
    template = (
        TEMPLATE.replace("Lesson flow (illustrative)", "Resolved authority graph")
        .replace(
            "Select a role to inspect its responsibility.",
            "Select a resolved input to inspect its authority.",
        )
        .replace(
            "Authored JavaScript and CSS bundled into one offline file. This diagram is not a resolved Component DAG; this artifact has no lifecycle acceptance receipt.",
            "Canonical Literate AI 1.3.1 project. This preview is authored retained input; inspect the separate project receipt for actual lifecycle qualification.",
        )
        .replace(
            "The lesson flow above describes lab responsibilities. These are the external authoring inputs and the harness boundaries for this actual bundle.",
            "The graph comes from the Component lock. Components, selected Flavors and pinned authoring inputs have distinct responsibilities.",
        )
    )
    return template.format(
        title=html.escape(config["title"]),
        stage=html.escape(config["stage"]),
        css=(ROOT / "shared/lab.css").read_text(),
        runtime=(ROOT / "shared/lab-runtime.js").read_text(),
        main=(lab / "main.js").read_text(),
        config=serialized,
    )


def main() -> None:
    labs = sorted(ROOT.glob("[0-9][0-9]-*/lab.json"))
    pages = [
        (manifest.parent / "index.html", build_page(manifest.parent))
        for manifest in labs
    ]
    for destination, page in pages:
        destination.write_text(page, encoding="utf-8")
    print(f"built {len(labs)} standalone labs with exact source inspection")


if __name__ == "__main__":
    main()
