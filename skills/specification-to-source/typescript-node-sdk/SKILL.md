---
name: "typescript-node-sdk"
description: "Generate a pure TypeScript library for the explicit Node SDK Flavors. Use only with lang-typescript-library and package-node-sdk."
metadata:
  author: "Literate AI maintainers <literate-ai-maintainers@users.noreply.github.com>"
schema: "urn:literate-ai:schema:v1:specification-to-source-skill"
skill_id: "typescript-node-sdk"
version: "1.0.0"
title: "Pure TypeScript Node SDK"
stages:
  - "generate"
dependencies: []
limitations:
  - "Use only with an explicit library Component, lang-typescript-library, package-node-sdk and declared dual-format public exports."
  - "Do not install, discover, probe or run Node.js, npm, tsc, npx, package managers or compiler tools during generation. Only the authorized lifecycle selects and executes them."
  - "Do not read provider checkouts, private specifications, oracle inputs or transitive internals. Use only exact supplied direct public declarations and sealed-provider mappings."
  - "Do not generate package manifests, lockfiles, node_modules, provider implementations, declaration files, compiled CJS/ESM output or package archives."
  - "Do not use production Node APIs, ambient types, external packages, network access, filesystem access, a shell, dynamic loading, eval, timers or locale-sensitive behavior."
  - "Do not invent license terms, weaken validation, replay mutations or claim tests passed when the authorized build has not run."
trust: "repository-reviewed"
---
# Pure TypeScript Node SDK

Implement the Component's public library behavior as pure TypeScript under `src/`.
Honor each exact public root/subpath and output stem in the resolved dual-export
surface. Use `src/index.ts` as the default root and supply the other declared stems
without adding undeclared public APIs. Keep source deterministic and portable;
the compiler supplies ES2022 library types without ambient Node or package types.
Use explicit `.js` relative specifiers for sibling TypeScript implementations so
the selected compiler resolves the source and emits relocatable runtime imports.

For direct sealed CommonJS providers, retain the exact lifecycle-supplied relative
bridge path and declarations, using `import provider = require("<supplied path>")`
when a CommonJS import is required. Never replace an unavailable bridge with a stub,
copy, registry dependency or invented type. Preserve provider-owned class/function
identity when forwarding its API. Source generation cannot authorize provider reads
or decide that a returned provider fact remains current.

Write native generated tests in `source/tests/litai_test.cjs`. The authorized TEST
driver supplies the built SDK directory as `process.argv[2]`; load the exact declared
CJS public export beneath that directory, using Node's path API in this test driver
only. Exercise specification examples, boundaries, invariants and error behavior
against that built SDK. Emit one JSON `literate-ai/generated-test-results@1` result
with every selected case ID exactly once and its actual outcome. Keep the executable
tests independent of `source/tests/manifest.json`; do not read that manifest to
manufacture success or embed private independent-oracle answers.

Place the selected legal files at the source root, copying their exact authorized
text from Component inputs. If that text or another required public contract is
absent, report the missing input rather than choosing a license or fabricating it.

The shared lifecycle owns compiler images, strict dual compilation, declaration
emission, provider materialization, package boundaries/exports and offline packing.
Do not create `package.json`, `cjs/`, `esm/`, `_providers/` or an archive yourself.
Direct source self-checks may be unavailable until sealed inputs are admitted;
report that limit honestly and leave BUILD, TEST, EXEC and independent runtime/type
acceptance to their separately authorized owners. A generation result is source,
not acceptance, publication, background permission or downstream adoption.
