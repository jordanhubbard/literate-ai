import assert from "node:assert/strict";
import test from "node:test";

import { auditViolations } from "../check-npm-audit.mjs";

const BRACES = "GHSA-vfj7-8cjw-p6xm";

function report(vias) {
  return {
    metadata: { vulnerabilities: { high: 1 } },
    vulnerabilities: {
      braces: { via: vias },
      micromatch: { via: ["braces"] },
    },
  };
}

function advisory(severity, id = BRACES) {
  return {
    source: 1,
    name: "braces",
    severity,
    title: "stack exhaustion",
    url: `https://github.com/advisories/${id}`,
  };
}

const exception = {
  advisory: BRACES,
  package: "braces",
  reason: "no patched release",
  issue: "https://github.com/jordanhubbard/literate-ai/issues/24",
  expires: "2026-11-15",
};

test("an unexcepted high advisory fails", () => {
  assert.deepEqual(auditViolations(report([advisory("high")]), [], "2026-10-03"), [
    `high ${BRACES} in braces: stack exhaustion`,
  ]);
});

test("a matching unexpired exception passes, including derived packages", () => {
  assert.deepEqual(auditViolations(report([advisory("high")]), [exception], "2026-10-03"), []);
});

test("an exception does not cover a different advisory or a critical finding elsewhere", () => {
  const other = "GHSA-aaaa-bbbb-cccc";
  assert.deepEqual(
    auditViolations(report([advisory("high"), advisory("critical", other)]), [exception], "2026-10-03"),
    [`critical ${other} in braces: stack exhaustion`],
  );
});

test("an expired exception fails", () => {
  assert.deepEqual(auditViolations(report([advisory("high")]), [exception], "2026-11-16"), [
    `exception for ${BRACES} (braces) expired on 2026-11-15`,
    `high ${BRACES} in braces: stack exhaustion`,
  ]);
});

test("an exception that no longer matches a finding fails", () => {
  assert.deepEqual(auditViolations(report([]), [exception], "2026-10-03"), [
    `exception for ${BRACES} (braces) no longer matches a finding; remove it`,
  ]);
});

test("low and moderate advisories do not gate", () => {
  assert.deepEqual(
    auditViolations(report([advisory("low"), advisory("moderate")]), [], "2026-10-03"),
    [],
  );
});

test("an incomplete exception is rejected", () => {
  assert.deepEqual(auditViolations(report([]), [{ advisory: BRACES }], "2026-10-03"), [
    "exception 0 is invalid (package, reason, issue, expires)",
  ]);
});

test("an unavailable audit is an error, not a pass", () => {
  assert.throws(
    () => auditViolations({ error: { code: "ENOTFOUND" } }, [], "2026-10-03"),
    /npm audit unavailable/,
  );
  assert.throws(() => auditViolations({}, [], "2026-10-03"), /lacks vulnerability evidence/);
});

// Exercise the shared CLI with two real package roots. Only registry transport is
// replaced; argument selection, exception loading and process status remain real.
test("the shared audit CLI audits its explicit package, independently of cwd", async () => {
  const { mkdtempSync, mkdirSync, writeFileSync, rmSync } = await import("node:fs");
  const { tmpdir } = await import("node:os");
  const { join, resolve } = await import("node:path");
  const { fileURLToPath, pathToFileURL } = await import("node:url");
  const { spawnSync } = await import("node:child_process");
  const fixture = mkdtempSync(join(tmpdir(), "litai-audit-"));
  try {
    const clean = join(fixture, "clean");
    const vulnerable = join(fixture, "vulnerable");
    for (const directory of [clean, vulnerable]) {
      mkdirSync(directory);
      writeFileSync(join(directory, "audit-exceptions.json"), '{"exceptions":[]}');
    }
    writeFileSync(join(clean, "registry.json"), JSON.stringify(report([])));
    writeFileSync(join(vulnerable, "registry.json"), JSON.stringify(report([advisory("high")])));
    const hook = join(fixture, "registry.mjs");
    writeFileSync(hook, `
      import childProcess from 'node:child_process';
      import { syncBuiltinESMExports } from 'node:module';
      import { readFileSync } from 'node:fs';
      import { join } from 'node:path';
      childProcess.spawnSync = (command, args, options) => {
        if (!['npm', 'npm.cmd'].includes(command) || JSON.stringify(args) !== '["audit","--json"]') {
          throw new Error('Unexpected registry transport');
        }
        return { status: 0, stdout: readFileSync(join(options.cwd, 'registry.json'), 'utf8'), stderr: '' };
      };
      syncBuiltinESMExports();
    `);
    const cli = fileURLToPath(new URL("../check-npm-audit.mjs", import.meta.url));
    const invoke = (cwd, project) => spawnSync(process.execPath,
      ["--import", pathToFileURL(hook).href, cli, resolve(project)],
      { cwd, encoding: "utf8", timeout: 10000 });
    const rejected = invoke(clean, vulnerable);
    assert.equal(rejected.status, 1, rejected.stderr);
    assert.match(rejected.stderr, /GHSA-vfj7-8cjw-p6xm/);
    const accepted = invoke(vulnerable, clean);
    assert.equal(accepted.status, 0, accepted.stderr);
    assert.match(accepted.stdout, /no unexcepted high or critical advisories/);
  } finally {
    rmSync(fixture, { recursive: true, force: true });
  }
});
