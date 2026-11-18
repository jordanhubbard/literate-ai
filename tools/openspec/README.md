# OpenSpec validation tooling

This locked package owns the pinned OpenSpec CLI. It is separate from
[documentation rendering](../documentation/README.md), which does not use it.
Neither package is part of the Python framework's runtime dependencies.

`make openspec-check` and `npm --prefix tools/openspec run openspec:check`
audit this complete development dependency graph before validation. High or
critical findings and unavailable audits fail. The shared audit owner is
`tools/npm-audit/check-npm-audit.mjs`; this package owns its own
`audit-exceptions.json`. No development dependencies are omitted.

`make tools-install` installs both contributor toolchains. A documentation-only
`make documentation-check` installs only its browser-bearing toolchain and the
shared audit helper. Full CI, Windows qualification and release qualification
retain both checks. Separating these packages does not remediate an OpenSpec
advisory or permit release while its audit fails.
