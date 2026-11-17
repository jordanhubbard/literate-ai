---
schema: "literate-ai/flavor-markdown@1"
namespace: "literate-ai"
name: "package-node-sdk"
version: "1.0.0"
display_name: "Offline dual Node SDK package"
primary_axis: "packaging"
target: "node-sdk"
secondary_constraints:
  - axis: "implementation.language-ecosystem"
    value: "typescript"
    optional: false
applicable_capabilities: []
provides:
  - name: "package.format.node-sdk"
    version: "1.0.0"
    contract: null
requires: []
specification_roots:
  - "openspec/spec.md"
authoring_inputs:
  - kind: "specification-to-source-skill"
    uri: "../../skills/specification-to-source/typescript-node-sdk/SKILL.md"
contributions:
  - contribution_id: "npm-toolchain-constraint"
    kind: "toolchain"
    merge_operator: "exact-singleton"
    slot: "npm"
    content:
      kind: "toolchain-constraint"
      uri: "toolchain.json"
  - contribution_id: "typescript-image-constraint"
    kind: "toolchain"
    merge_operator: "exact-singleton"
    slot: "typescript"
    content:
      kind: "toolchain-constraint"
      uri: "typescript.json"
  - contribution_id: "node-sdk-standard-command-profile"
    kind: "builder"
    merge_operator: "exact-singleton"
    slot: "standard-package-command"
    content:
      kind: "standard-command-profile"
      uri: "standard-command-profile.json"
conflicts: []
co_requisites:
  - "flavor://literate-ai/lang-typescript-library"
order_before: []
order_after: []
---
# Offline dual Node SDK package

Select with `lang-typescript-library` for an explicit dual library. The shared
compiler/packer owns the package; supplied legal text and current execution grants
remain required. This is distinct from lockfile-based `package-npm` applications.
