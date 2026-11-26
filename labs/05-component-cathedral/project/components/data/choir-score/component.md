---
namespace: unprompted
version: 1.0.0
display_name: Cathedral Choir Score
profiles:
  - application
  - portable
sample: false
inheritable: false
provides:
  - name: unprompted.cathedral-choir-score
    version: 1.0.0
    interface: null
  - name: sample.portable-app
    version: 1.0.0
    interface: null
requires: []
authoring_inputs:
  - kind: specification-to-source-skill
    uri: skills/specification-to-source/portable-specification-planning/SKILL.md
workflow_definition:
  uri: workflows/sample-host.md
routing_policy:
  uri: routing/sample-host.json
flavor_slots:
  - slot_id: language
    axis: implementation.language-ecosystem
    cardinality: exactly-one
    capability_contract: unprompted.cathedral-choir-score
  - slot_id: os
    axis: platform.os
    cardinality: exactly-one
    capability_contract: sample.portable-app
  - slot_id: build-system
    axis: build.system
    cardinality: exactly-one
    capability_contract: sample.portable-app
entrypoints:
  - name: export-score
    kind: portable-application
    path: export-score
acceptance_contracts: []
source_dependencies: []
---
# Cathedral Choir Score

Own the score consumed by the Cathedral browser application. Produce one
UTF-8 JSON score with frequencies 110, 146.8, 164.8, 220 and 293.7 Hz in that
order and a scheduling interval of 360 milliseconds. Export the ordered notes
as build data so the application can embed them into its offline artifact.

The score provider works independently of the DOM, audio device and playback
timer. It accepts no network access and produces identical bytes for repeated
calls. The application owns Web Audio playback, timer cancellation and capture.
