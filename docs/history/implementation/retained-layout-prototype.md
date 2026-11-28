# Retained layout prototype reconciliation

The recovered `layout14` snapshot is an alternative, unfinished implementation.
Its public helper was not registered in the CLI. Its service, compiler and tests
depend on older partition, transaction and journal issuance APIs that the current
native source work replaced. Restoring those APIs beside the current owners would
introduce another effect path with different ownership and recovery rules.

The exact original work is preserved in the
[full source patch](retained-layout-prototype.patch) and its
[blob and replay manifest](retained-layout-prototype.json). Applying that patch
to its recorded original base in an alternate Git index reproduces the complete
original snapshot tree. All 28 changed paths, including the 13 prototype files,
tests and roadmap observations, are retained. The original revision also remains
reachable through the integrated history and recovery reference.

This is an archival integration decision, **not functional equivalence or feature
completion**. Current source preparation explicitly leaves phase/effect admission
unfinished. The original canonical role-input refusal, source publication,
metadata transition, public composition, independent review and installed/native
acceptance remain active requirements. A historical patch or saved plan cannot
restore a live source, namespace, journal or execution owner.

| Original area | Current authority and remaining work |
| --- | --- |
| Layout declaration and geometry | `adapters/retained_layout.py` owns current selection and structural layout. Preserve the original root/nested geometry intent; do not substitute the prototype's constructible source-policy value for a live owner. |
| Partition observation and planning | `capture_retained_layout_partition`, `prepared_retained_layout_source_move` and the source namespace/authored/role owners provide current bounded observations. Higher-level compiler/inspection/workspace behavior remains unfinished; its original code is retained in the patch. |
| Publication, journal and recovery | Current source phases, native forest operations, journal and recovery owners remain authoritative. Do not restore the older independent publication path to bypass current refusals. Complete the original ownership join and metadata/public composition through these owners. |
| Wrapper lifetime | The recovered original-instance, process/thread and retirement controls were ported to the shared current wrapper. The actual source wrapper controls and authored/Python regressions are recorded in the handoff observation. |
| Initializer, harness, lineage and SDK observations | Retain the current contained metadata, immutable input, source/index, alias and lifecycle guards. Original proposal code and tests remain available for comparison without renewing their historical acceptance. |

Continue the [active layout work](../../roadmap/active-work.md) from its actual
current native frontier. The takeover and checkout consolidation do not close
the layout or release requirements.
