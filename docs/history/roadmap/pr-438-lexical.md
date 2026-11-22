# Historical lexical-custody branch record

This is the original PR #438 branch record, retained during release recovery.
Its lexical implementation is part of current `CARGO-CUSTODY-PERF-001`; its
proposed separate goal below is historical branch context, not an additional
selected release goal or a claim of current receiving/release qualification.
The current release manifest remains unchanged.

### [ ] CARGO-LEXICAL-PERF-001 — Bound repeated lexical path validation during retained input capture

- **GitHub issue:** [#432](https://github.com/jordanhubbard/literate-ai/issues/432); separate lexical follow-up to the pending [PR #435](https://github.com/jordanhubbard/literate-ai/pull/435).
- **Release target:** 1.4.0
- **Priority:** P1
- **Owner:** Retained input filesystem adapter; PROJECT Goals 1 and 4
- **Direction:** Resolve the remaining pure lexical traversal amplification reported under upstream issue #432 without reducing fresh byte, filesystem or currentness checks.
- **Conclusion:** Use one bounded per-access memo of successful immutable relative-path parsing only. Charge it within the existing metadata allowance, evict before retention exceeds that allowance, preserve every stat/read/lineage/guard operation and fall back to uncached parsing when no allowance remains. Prior descriptor and parsing-scope work in PR #435 stays separate; neither this patch nor its timing closes #432 or downstream receiving acceptance.
- **Depends on:** none
- **Completion prerequisites:** none
- **Implementation:**
  - [x] Implement an opt-in access-local lexical cache and tree metadata accounting; keep default/Windows/low-descriptor readers and public identities unchanged.
  - [x] Add causal filesystem content/mode/ancestor/namespace mutation controls, exact fresh-operation counters, finite cache/eviction/low-budget/cleanup coverage and a fresh same-input before/after comparison.
- **Evidence:**
  - [x] Pass applicable maintained Python tests and source gates, independent review of accounting and custody invariants, and an actual bounded native baseline/candidate comparison before publishing any speed claim. Full receiving, installed SDK and upstream integration remain separately pending.

- **Development evidence:** The maintained focused Python gate selects 57 POSIX input cases: 55 pass, with the existing Windows-executable and optional external source-corpus cases explicitly skipped. The 12 new cases preserve identical native stat/open/close and payload-stream counts against uncached parsing, and cover cache caps, metadata-budget fallback, exception cleanup, namespace/content/mode/write-and-restore and same-byte object replacement refusals. Full formatting (1,893 files) and lint pass. The first new alias fixture used an absolute target that failed the existing target-spelling contract; its failure is retained and the fixture now exercises a valid relative escaping target. The independent native comparison and complete source suite are now recorded below; upstream integration and complete receiving acceptance remain pending.

- **Qualification prerequisite (2026-11-13):** The complete default source run at `56fb5310fe2b67fb1a00d6533d951a5197001888` retains one known [#424](https://github.com/jordanhubbard/literate-ai/issues/424) mixed-interpreter oracle failure: 1,627 passed, one failed and 86 skipped out of 2,795 selected; all 12 lexical controls passed and independent process/source/tool closure passed. Its Python 3.14 test interpreter correctly differed from the admitted Python 3.12 compiler. Reuse only the exact existing test correction from `5895a62ad6b97a8d3288324cf68348f728e441b5` / PR #425 (also reused by PR #435), preserving the real mixed environment, accepted compiler identity, independent expected source and full byte equality. No interpreter switch, test exclusion, duplicate implementation or production change is introduced. The focused causal case and complete fresh source qualification pass on the composed source as recorded below.

- **Native qualification (2026-11-13):** [Portable source and comparison record](../../../verification/retained-cargo-lexical-linux.json) binds the unchanged `56fb5310` production modules and composed source `29437a85`. All 12 native mutation/accounting controls pass. The fixed baseline/candidate/candidate/baseline comparison on 47,616 CargoHome files (1,688,282,712 bytes) averages 30.753 versus 22.390 seconds, a 27.2% reduction for this capture only; Python filesystem API/payload-reader counts and semantic/physical snapshots remain equal. The complete fresh default `make python-check` selects 2,795 unique cases: 2,677 pass, 118 retain declared skips, zero fail or remain known-failed. Actual test Python 3.14.4 and admitted compiler 3.12.10 remain distinct; the formerly failing E2E passes both directly and in the full suite. All five bounded phases and the outer owner exit zero, source/tool bytes remain unchanged, and independent unit/group retirement passes. The previous failed aggregate remains failed. This is source qualification, not an installed wheel, complete receiving budget, upstream landing or release claim.
