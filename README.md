# IndustrialRCA

An industrial root cause investigation prototype using FastAPI, LangGraph,
DeepSeek tool calling, and a React dashboard.

The diagnostic agent chooses what to inspect, executes read-only tools, observes
results, and revises hypotheses. It can propose a new failure hypothesis without
adding a fault-code branch. Investigations stop for human review when a supported
assessment is available, or end inconclusively with the evidence still needed.

## Run locally

Python 3.11+ and Node.js compatible with the frontend's Vite version are required.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r industrial_rca/requirements.txt
cp .env.example .env
```

Set `DEEPSEEK_API_KEY` and `DEEPSEEK_MODEL` in `.env`, then start the backend:

```bash
python -m uvicorn industrial_rca.api:api_app --host 127.0.0.1 --port 8000
```

Start the frontend in another terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open [the dashboard](http://localhost:5173) or [API documentation](http://localhost:8000/docs).
The Windows launch scripts remain available.

Without valid provider credentials, telemetry and analytics remain available;
AI investigation ends `INCONCLUSIVE`. Provider errors are reported explicitly.
There is no canned successful diagnosis or automatic mock fallback.

## Investigation flow

Ingestion preserves supplied readings, historical fault transitions and incident
identity. Missing samples/channels/waveforms remain missing. Nominal telemetry
can complete screening without involving the model.

For an incident, LangGraph checkpoints a repeating decision/tool loop. The model
receives native tool schemas and selects its next action from previous observations:

| Tool | Observation |
| --- | --- |
| `profile_telemetry` | Statistics over a measured channel and sample-index window |
| `detect_change_points` | Changes in a measured channel |
| `trace_topology` | Configured upstream/downstream relationships |
| `lookup_oem` | OEM and FMEA reference knowledge |
| `lookup_maintenance` | Explicitly simulated fixtures, or unavailable live history |
| `submit_diagnosis` | A structured conclusion referencing collected observation IDs |

Tools cannot access arbitrary datasets, run code, write equipment registers, or
publish maintenance work. Arguments, evidence references, confidence bounds and
response sizes are validated. The default investigation budget is eight model
turns, four calls per turn, and 120 seconds checked between calls; each provider
request has a 30-second timeout. `create_rca_graph(decision_client=...,
max_agent_iterations=...)` supports injected decision clients and a different turn
budget. Higher turn budgets require a corresponding LangGraph `recursion_limit`.

Observations distinguish measured, simulated, configured, reference and inferred
information. Configured topology does not verify component condition; an OEM
fault description does not establish an upstream cause. Causal explanations may
contain fewer than five steps. Confidence is a model assessment, not a calibrated
probability. Citation validation checks provenance and structure; engineers must
still assess whether the evidence supports the claims.

## Review and maintenance drafts

Supported diagnoses pause at the LangGraph human-review interrupt. Explicit
approval and an identified reviewer are required before creating local 8D and PM01
drafts. Rejection creates no maintenance artifacts. Override requires a replacement
statement. Resume continues from the checkpoint without rerunning completed calls.

Draft operations come from the reviewed actions. Parts, estimated labor, ERP
identifiers and inspection findings are not fabricated. The CMMS connector is a
prototype with simulation fixtures; it does not submit or release orders in SAP.

The dashboard displays actual backend observations and evidence gaps. The
conversational copilot explains current context; it does not invent tool executions.
Telegram uses the same investigation results and reports missing diagnoses explicitly.

## Telemetry sources

Hardware incidents are accepted at `POST /api/v1/telemetry/incident` with
`asset_id`, `fault_code`, optional `incident_id`, and `pre_fault_telemetry` rows.
An absent history stays empty. Unknown fault codes remain unknown rather than
being converted to a known diagnosis. Samples preserve acquisition order; tool
windows and derived slopes use sample indices, not an assumed sampling interval.

Synthetic presets and user-enabled simulation are labelled as simulated. The live
loader returns an empty history when no readings are available. Operational limits
are installation configuration in `industrial_rca/config.py`; calibrate them for
the equipment. Limits are never inferred from the magnitude of a reading.

## Verification

```bash
python -m pytest industrial_rca/tests -q
cd frontend
npm run build
npm run lint
```

Tests inject offline decision clients and fake provider responses; they do not
require paid LLM calls or Telegram delivery. The approved 25-test proposal is
preserved unchanged under `industrial_rca/tests/agentic/`, with its hash manifest.
See [the implementation report](docs/agentic-refactor-report.md) for validation,
changed legacy expectations, and limitations.

CLI examples:

```bash
python main.py --use-deepseek
python main.py --no-deepseek --reject
python main.py --test-deepseek
```

CLI telemetry examples are simulated. `--auto-approve` explicitly approves local
simulation drafts; it does not operate equipment or submit orders externally.

MIT licensed. See [LICENSE](LICENSE).
