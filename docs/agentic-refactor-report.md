# Agentic refactor implementation report

Implemented on `codex/agentic-refactor` from `origin/main` commit
`ce0a99be1f8e89f32a137a1dba8fec1b966bf730`.

## Result

The fixed hypothesis fan-out, fault-specific confidence assignments, predefined
causal stories, and canned provider fallback have been replaced with a native
LLM tool loop. The model selects tools, receives incident-scoped observations,
revises hypotheses and submits an evidence-linked assessment. New hypotheses do
not require adding fault-code cases. Numeric screening and validation remain
deterministic runtime constraints.

The implementation separates:

- `industrial_rca/agent/contracts.py`: validated tool arguments, budgets,
  hypotheses, causal steps, diagnoses and observations.
- `industrial_rca/agent/tools.py`: schema/callable registry of read-only tools.
- `industrial_rca/agent/runtime.py`: checkpointed decision, execution,
  evidence validation and conclusion projection.
- `industrial_rca/graph/workflow.py`: bounded graph routing and human review.
- `industrial_rca/graph/nodes.py`: evidence ingestion, screening, explicit review,
  and local artifact generation.
- `industrial_rca/services/incidents.py`: shared hardware/simulation conversion
  that preserves submitted readings.
- `industrial_rca/tools/deepseek_client.py`: provider transport with native tool
  calls, reasoning-field replay, streaming errors and explicit unavailability.

Hardware ingestion and the live loader no longer fabricate missing channels,
waveforms, voltage/current excursions, or historical fault codes. Unknown datasets
and assets do not borrow known scenarios or maintenance history. Synthetic presets
remain available, explicitly labelled as simulated. Missing live history is empty.
The dashboard's fake tool cards, diagnoses and maintenance artifacts were removed;
its tool log now comes from actual backend observations. Offline frames do not
accumulate fabricated chart history. Inconclusive/error states stop progress and
show missing evidence. The responsive header was fixed after a browser check found
mobile overflow.

Explicit review with an identified reviewer is required for local maintenance
drafts. Review of one thread cannot replace another active incident. Draft
operations come from reviewed actions, without invented parts, labor estimates,
ERP identities or external release. The CLI handles graph audit-log resets and
reports missing model access. Telegram no longer supplies a default diagnosis or
approval buttons for an inconclusive investigation.

## Verification

Final local verification:

| Check | Result |
| --- | --- |
| Full backend suite | **153 passed**, 2 warnings, 28.93 seconds |
| Original baseline before implementation | 107 passed, 2 warnings |
| Approved proposal tests | All 25 pass; source hashes unchanged |
| Frontend TypeScript/Vite production build | Passed |
| Frontend oxlint | Exit 0; 21 warnings in existing imports/hooks/render patterns |
| Ruff correctness/import checks on the new agent, services and rewritten core | Passed |
| `git diff --check` | Passed |
| CLI `main.py --no-deepseek --reject` | Exits normally with `INCONCLUSIVE`, no maintenance drafts |
| Local API incident preview | Unknown fault 99 preserves its two supplied readings and ends inconclusively without credentials |
| Browser desktop and 390 × 844 viewport | Inconclusive evidence gaps and absence of maintenance drafts verified; no browser errors captured; mobile document width matches viewport after header fix |

The approved proposal snapshot SHA-256 is
`b6bee5e9c8ccd6213cde7cf32ec5a2e56ba598fe2255b977b8831102c7f4644f`.
Its manifest is retained in `industrial_rca/tests/agentic/approved-proposal.json`.
The three approved Python files were copied byte-for-byte from the separate
proposal workspace and were not modified. The project is not enrolled in AEK;
this is local verification, not an AEK-locked harness or independent CI approval.

Twenty-one additional tests cover adversarial boundaries and integration beyond
the approved 25: confidence bounds, duplicate call IDs, oversized tool names,
nonstandard JSON constants, cross-dataset access, no sensor channels, incident
reset/isolation, maintenance provenance, sparse live data, offline histories,
long incident IDs, exact classification fields, API review requirements and
isolation, and CLI log reset handling.

## Changed legacy expectations

The existing tests were retained, with changes where the approved behavior
intentionally replaces the scripted demo:

- Provider/connection tests inject responses or assert `UNAVAILABLE`; a missing
  API key is no longer an online simulated success. Configuration status is
  `CONFIGURED`, while `ONLINE` requires an actual successful connection test.
- Graph and API approval/rejection tests inject model decisions, exercise real
  local tools and check the interrupt/resume. They no longer require a fixed
  catalog winner, a predetermined PLC origin or exactly five causal steps.
- The Err13 integration test keeps OEM/scenario checks and tests an independently
  named model hypothesis with an explicit evidence gap before review.
- Work orders use reviewed actions; tests expect local draft status, no fabricated
  ERP equipment identity, no default materials and unspecified labor estimates.
- Live/offline tests require an empty unavailable history instead of generated
  normal/zero readings and synthetic sensor aliases.
- Telegram/plot tests preserve supplied readings and configured thresholds rather
  than guessing physical versus simulated equipment from voltage magnitude.

Previously unrelated analytics, telemetry generation, cache, storage, transport,
status recovery, formatting and bot tests continue to pass. Test-only decision
clients are under `industrial_rca/tests/`; production modules never import them.

## Review and limits

This is a self-review, not independent review. The diff was inspected against the
approved plan for evidence preservation, no scripted diagnostic fallback,
incident/tool scoping, bounded iteration/context/output, provider errors,
unsupported citations/classifications, approval defaults, cross-incident updates,
checkpoint resume and draft-only artifacts. Reproduced issues discovered during
implementation were covered by additional tests before their fixes.

Live-provider diagnostic quality, actual hardware behavior and external Telegram
or SAP delivery were not validated. Citation validation checks existing successful
observations and exact reference fields; it cannot prove that a model's physical
interpretation is correct. Confidence remains an uncalibrated model assessment
and the human review boundary remains necessary. The default checkpointer is
process-memory storage, so checkpoints are not durable across restarts.

No deployment, equipment operation or external work-order release was performed.
Changes are local; no GitHub push or pull request was created.
