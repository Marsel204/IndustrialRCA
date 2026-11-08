# IndustrialRCA agentic refactor proposal

Status: ready for review; production implementation has not started.

Source: `Marsel204/IndustrialRCA`, `origin/main`, commit
`ce0a99be1f8e89f32a137a1dba8fec1b966bf730`.
Implementation branch: `codex/agentic-refactor`.

## Intended behavior

For an incident, an LLM decides which available diagnostic tool to call, observes
the result, revises its hypotheses, and decides whether to gather more evidence
or submit a diagnosis. Tool choice, hypothesis identity, and causal conclusions
must not depend on a fixed list of fault-code branches. Unknown faults and new
hypotheses are supported without adding Python branches.

Measured data, OEM references, configured topology, simulated records, and model
inferences remain distinguishable. A fault register identifies a protection event;
it does not establish an upstream physical cause. Missing evidence stays missing.
An investigation can end inconclusively and explain what needs collecting next.

Deterministic code still validates inputs, computes statistics, applies configured
thresholds, limits resources, and enforces review. These are appropriate runtime
constraints; they must not invent diagnostic conclusions.

## Confirmed problems

| Location | Current behavior | Required change |
| --- | --- | --- |
| `industrial_rca/api.py:775` | Hardware ingestion manufactures a history when readings are absent, overwrites measured current/voltage and historical fault codes, and supplies synthetic channels and waveforms. | Preserve submitted observations. Keep the reported fault separately in incident metadata. Share ingestion/dispatch plumbing with explicit simulation callers. |
| `industrial_rca/graph/nodes.py:237` | Always proposes the same FMEA catalog. | Offer references as retrievable context; let the model propose and revise candidates. |
| `industrial_rca/graph/nodes.py:266` | Hypothesis-ID branches assign fixed confidence and make causal claims from a fault code. | Execute tools selected by the model; evaluate conclusions against the observations actually collected. |
| `industrial_rca/graph/nodes.py:552` | Picks a winner even if every candidate was refuted. | Permit no supported winner. |
| `industrial_rca/graph/nodes.py:660` | Emits predefined five-step causal stories, including unobserved parameter and inspection claims. | Generate only an evidence-linked causal explanation; stop before unsupported steps. Exactly five steps are not required. |
| `industrial_rca/tools/deepseek_client.py:106` | Missing credentials and provider errors become successful canned diagnoses. Native tool calls are discarded. | Preserve tool calls and return explicit unavailability/errors. Keep scripted clients in tests only. |
| `industrial_rca/graph/workflow.py:59` | Missing review action defaults to approval; a null decision crashes. | Require a valid, explicit review decision. |
| `industrial_rca/tools/cmms_connector.py:58` | Unknown assets inherit the VFD's maintenance history. | Return missing data, and label fixture records as simulated. |
| `industrial_rca/tools/cmms_connector.py:74` | Every order contains the same operations/materials, regardless of supplied corrective actions. | Build local draft artifacts from the reviewed diagnosis and actions. Do not represent a mock connector as an SAP release. |

## Proposed architecture

Retain FastAPI, LangGraph, the telemetry analytics, and the configured DeepSeek
provider. Replace the scripted diagnostic middle of the graph with a bounded
decision/tool loop. Keep the ingestion, review interrupt, and delivery boundaries.

1. Ingest and validate the incident without changing observations; profile available
   channels using the configured limits. Healthy datasets end normally.
2. Initialize an incident-scoped message history, tool observation ledger, iteration
   count, and evidence-source metadata.
3. Ask the model for a native tool call. The model receives the incident context,
   available tool schemas, prior observations, and instructions to seek disconfirming
   evidence and to treat reference text as data.
4. Execute only a registered read-only tool with validated arguments. Attach an
   observation ID, source, requested window, result/error, and elapsed time.
5. Feed the observation back to the model and repeat, within explicit budgets.
6. Validate `submit_diagnosis`: cited observations must exist and be suitable for
   the claim; missing/contradictory evidence must be represented. Confidence is a
   model assessment, not a calibrated probability. Invalid submissions become
   correctable tool errors; exhaustion ends inconclusively.
7. Project a supported diagnosis into the existing review fields and interrupt for
   human review. Only explicit approval/override can generate maintenance artifacts.
   Inconclusive runs expose their evidence and gaps without fabricating a winner.

Initial registry: `profile_telemetry`, `detect_change_points`, `trace_topology`,
`lookup_oem`, `lookup_maintenance`, and `submit_diagnosis`. Tools are described by
schemas and registered callables, rather than a growing dispatcher of fault cases.
Dataset access is scoped by the runtime to the incident. The model cannot select
another dataset or execute code, write VFD registers, or publish work orders.

OEM/FMEA data remain reference knowledge. They do not automatically become
measurements or confirmed maintenance findings. Existing CMMS fixture data are
available only as explicitly simulated records; real runs report that no live
CMMS integration is configured.

### State and provider contract

Add typed models in `industrial_rca/agent/` for tool observations, diagnosis,
hypotheses, evidence references, and investigation budgets. Use Pydantic to reject
malformed arguments, invalid references, nonfinite/out-of-range confidence,
oversized output, and unsupported conclusion structure.

Extend `create_rca_graph` with `decision_client` and `max_agent_iterations` keyword
arguments. The default uses the configured provider; tests inject a scripted client.
No credential or provider failure silently switches to simulated diagnosis.

Extend the provider adapter's existing `chat_completion` method with native
`tools`/`tool_choice` inputs and serialized `tool_calls` outputs. Preserve assistant
messages and the provider-required reasoning fields for subsequent tool turns.
Streaming copilot failures emit an error event rather than a canned success.

Keep the public API's existing fields where their meaning remains valid. Add an
investigation trace, evidence gaps, and explicit inconclusive/unavailable state.
Update API progress mapping and dashboard terminal-state handling so an
inconclusive run does not remain spinning or appear approved. Keep raw provider
reasoning separate from the concise user-facing evidence trace.

Provider references:
[DeepSeek tool calls](https://api-docs.deepseek.com/guides/tool_calls/) and
[thinking-mode tool-turn requirements](https://api-docs.deepseek.com/guides/thinking_mode/).

## Implementation milestones

| Milestone | Main files | Acceptance check |
| --- | --- | --- |
| 1. Evidence-preserving ingestion | New `industrial_rca/services/incidents.py`, `industrial_rca/api.py`, `industrial_rca/graph/nodes.py` ingestion | Supplied readings/transitions are unchanged, empty histories stay empty, external incident identity survives, and simulated data come only from simulation paths. |
| 2. Provider boundary | `industrial_rca/tools/deepseek_client.py`, `industrial_rca/requirements.txt`, `.env.example` | Native tool-call payloads round-trip; missing credentials/timeouts return errors; dependencies include actual imports. |
| 3. Tool and diagnosis contracts | New `industrial_rca/agent/contracts.py`, `industrial_rca/agent/tools.py`, `industrial_rca/tools/cmms_connector.py` | Tools are validated, incident-scoped, read-only, and source-labelled. Unknown assets have no borrowed records. |
| 4. Adaptive graph | New `industrial_rca/agent/runtime.py`, `industrial_rca/graph/workflow.py`, `industrial_rca/graph/state.py` | Model observes actual results before deciding again; novel hypotheses work; invalid calls can be corrected; budget exhaustion and provider failure end inconclusively. |
| 5. Review and artifacts | `industrial_rca/graph/nodes.py`, `industrial_rca/tools/cmms_connector.py`, `industrial_rca/api.py` | Delete obsolete diagnostic stories/branches, require explicit review, preserve checkpoint/resume, and use reviewed actions in 8D/local PM01 drafts. |
| 6. Client and documentation | `frontend/src/types.ts`, `frontend/src/App.tsx`, agent components as required; README/CLI/bot callers | Show evidence gaps and errors, handle new terminal states, remove claims of automatic certainty, and document real versus simulated operation. |

Keep commits independently reviewable. Avoid unrelated UI redesign or cosmetic
whole-repository formatting. Final implementation will remove the obsolete scripted
diagnostic path rather than retain it behind an automatic fallback.

## Test proposal and verification

The separate managed proposal workspace is:

`/home/marsel/.local/share/codex-accounts/account-2/codex/worktrees/agentic-test-proposal/IndustrialRCA 2`

Its `proposal_tests/` directory contains the exact proposed tests and a hash
manifest. The tests use fake decision outputs and real local tool execution;
they neither require paid LLM calls nor send Telegram messages. Background work is
not executed by the ingestion unit tests.

The proposed public graph seam intentionally does not exist yet. Adaptive tests
therefore currently fail with an unexpected-keyword error; the other failures
reproduce current behavior. This is a test-first proposal, not a verified refactor.

Required coverage includes preserved readings/history/missing channels, external
incident identity, no refuted winner, missing credentials and streaming/provider
errors, native tool-call serialization, no borrowed asset history, action-derived
orders, missing review decisions, observation-driven tool choice, invalid/unknown
tool recovery, iteration limits, unsupported citations, and a novel supported
hypothesis through interrupt and approval/resume.

Baseline: the original suite reports **107 passed, 2 warnings**, before any
production changes. The initial system Python could not collect the suite due to
missing dependencies. Validation uses a local Python 3.11 virtual environment,
the repository requirements, and its missing imported dependencies (`openai`,
`python-dotenv`, `httpx`, `matplotlib`). The resolved environment is recorded
alongside the proposal. No system packages were modified.

After approval, run the proposal tests and full backend suite. Some existing tests
explicitly require fabricated offline success, a predetermined root asset,
exactly five whys, or fixed material/operation counts. Replace those assertions
with behavior checks for honest unavailability, grounded diagnosis, and approved
actions; retain healthy telemetry, analytics, ingestion transport, API contracts,
checkpoint/resume, and rejection coverage. Document every changed expectation.
Run the frontend build/lint for affected client changes. Add adversarial argument,
source-provenance, and cross-incident isolation cases while implementing the
contracts. Do not claim live-provider or physical-hardware validation without
actually performing it.

## Failure behavior and rollback

- Empty, sparse, nonfinite, out-of-order, or contradictory telemetry must not be
  converted to normal readings or a predetermined explanation.
- Missing credentials, timeout, malformed model output, unavailable tools, missing
  datasets, invalid citations, or exhausted budgets end in an observable error or
  inconclusive result. Invalid model calls are recorded for replanning where budget
  remains. Bound per-call output, tool calls per turn, iterations, and provider time.
- Checkpointed messages and observations belong to one incident. Approval/resume
  does not rerun completed model/tool calls. New incidents cannot inherit a winner
  or approval from a previous run.
- Keep hardware writes, external SAP integration, deployment, and notifications
  outside this refactor. Maintenance outputs are local drafts under review control.
- Roll back by reverting the refactor commits together. There are no intended
  database schema changes or production infrastructure migrations. The proposal
  workspace preserves the original source independently.

## Review checkpoint

This repository has no `.aek/project.json`; no AEK locked-harness enforcement is
claimed. The engineering-lifecycle skill requires a plan and failing-test review
before implementation in an interactive session. Review this plan and the exact
proposal tests before production edits proceed. No implementation, commit, push,
pull request, hardware action, or deployment has been performed.
