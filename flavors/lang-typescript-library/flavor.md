---
schema: "literate-ai/flavor-markdown@1"
namespace: "literate-ai"
name: "lang-typescript-library"
version: "1.0.0"
display_name: "Pure TypeScript Node SDK library"
primary_axis: "implementation.language-ecosystem"
target: "typescript"
secondary_constraints:
  - axis: "packaging"
    value: "node-sdk"
    optional: false
applicable_capabilities: []
provides:
  - name: "implementation.language.typescript"
    version: "1.0.0"
    contract: null
requires: []
specification_roots:
  - "openspec/spec.md"
authoring_inputs:
  - kind: "specification-to-source-skill"
    uri: "../../skills/specification-to-source/typescript-node-sdk/SKILL.md"
contributions:
  - contribution_id: "node-toolchain-constraint"
    kind: "toolchain"
    merge_operator: "exact-singleton"
    slot: "node"
    content:
      kind: "toolchain-constraint"
      uri: "toolchain.json"
  - contribution_id: "typescript-standard-command-profile"
    kind: "builder"
    merge_operator: "exact-singleton"
    slot: "standard-language-command"
    content:
      kind: "standard-command-profile"
      uri: "standard-command-profile.json"
conflicts:
  - "flavor://literate-ai/lang-cpp"
  - "flavor://literate-ai/lang-go"
  - "flavor://literate-ai/lang-javascript"
  - "flavor://literate-ai/lang-python"
  - "flavor://literate-ai/lang-rust"
  - "flavor://literate-ai/lang-swift"
  - "flavor://literate-ai/lang-typescript"
  - "flavor://literate-ai/lang-zig"
co_requisites: []
order_before: []
order_after: []
---
# Pure TypeScript Node SDK library

Select together with `package-node-sdk` for an explicitly declared library.
This Flavor selects SDK source and test layout; it grants no execution or acceptance.
