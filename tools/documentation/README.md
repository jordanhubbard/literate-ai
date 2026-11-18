# Repository documentation tooling

This directory owns the pinned Mermaid CLI, Puppeteer, yauzl and their npm
dependency graph. It renders every Mermaid fence through one sandboxed browser
session. OpenSpec validation has its own package under `tools/openspec`; rendering
does not install or execute it. Neither toolchain is part of the Python framework
package or required to install, import or run the kernel.

Contributor tooling requires Node.js 22.12 or newer (CI uses Node 24). Puppeteer
25 removes the vulnerable `extract-zip` and js-yaml dependency chains from the
lock. Puppeteer then extracts its browser with a host `unzip`, so the lock pins the
optional `yauzl` extractor instead; hosts without `unzip` would otherwise leave an empty
browser folder that fails every later render. These are documentation-tool requirements,
not changes to generated applications' selected runtimes. Keep browser sandbox defaults
enabled.

`make documentation-check` first audits the staged locked dependency graph. High or
critical findings, or an unavailable audit service, fail the gate; do not substitute
`--omit=dev`, because these development dependencies are the tooling being qualified.
The only allowance is `audit-exceptions.json`: each entry names one advisory and
package, with a reason, tracking issue and expiry date. Expired entries and entries that
no longer match a finding also fail the gate.
The gate needs access to the configured npm registry's audit endpoint. Parser and
rendering checks still run after a passing audit.

Install and run it from the repository root:

```bash
make documentation-check
```

The shared audit implementation lives under `tools/npm-audit`; each toolchain owns
its own exception file. Both audited checks remain required in full CI, Windows
qualification and release qualification. A successful documentation check does not
qualify the OpenSpec dependency graph.
