# Production-Grade Industrial Root Cause Analysis (RCA) System

An autonomous, production-grade Industrial Root Cause Analysis prototype engineered with **Python 3.11+** and **LangGraph**. Grounded in **ISA-95** asset hierarchies, **ISO 14224 / FMEA** failure taxonomy, **ISO 10816 Class III Zone D** vibration standards, **Global 8D (Eight Disciplines)** incident reporting, and **SAP S/4HANA PM01** corrective maintenance work orders.

---

## 🏗️ Architectural Blueprint

The system bridges deterministic industrial physics with stateful agentic graph orchestration:

```
                                  [START]
                                     │
                        ┌────────────▼────────────┐
                        │ Ingest Telemetry Event  │
                        └────────────┬────────────┘
                                     │
                        ┌────────────▼────────────┐
                        │    Detect Anomalies     │
                        └────────────┬────────────┘
                                     │
                     ┌───────────────┴───────────────┐
                     ▼ (No active trip)              ▼ (Trip confirmed)
                ┌─────────┐             ┌────────────────────────┐
                │   END   │             │  Generate Hypotheses   │
                │ (Normal)│             └───────────┬────────────┘
                └─────────┘                         │
                                    ┌───────────────┴───────────────┐
                                    │ Dynamic Fan-Out (Send)        │
                                    ▼                               ▼
                      ┌───────────────────────────┐   ┌───────────────────────────┐
                      │ Parallel Worker Node (H1) │...│ Parallel Worker Node (H3) │
                      │  Lubrication Starvation   │   │ Motor Electrical Overload │
                      └─────────────┬─────────────┘   └─────────────┬─────────────┘
                                    │                               │
                                    └───────────────┬───────────────┘
                                                    │ (Join)
                                      ┌─────────────▼─────────────┐
                                      │   Aggregate Hypotheses    │
                                      │   (Falsification Matrix)  │
                                      └─────────────┬─────────────┘
                                                    │
                                      ┌─────────────▼─────────────┐
                                      │ Upstream Causal 5-Whys    │
                                      │  (ISA-95 Graph Traversal) │
                                      └─────────────┬─────────────┘
                                                    │
                                      ┌─────────────▼─────────────┐
                                      │  HITL Review Interrupt    │
                                      │  (langgraph interrupt)    │
                                      └─────────────┬─────────────┘
                                                    │
                                    ┌───────────────┴───────────────┐
                     [Approve / Override]                           [Reject]
                                    │                                   │
                      ┌─────────────▼─────────────┐       ┌─────────────▼─────────────┐
                      │ Generate Deliverables     │       │  Handle Human Rejection   │
                      │ • Standard 8D Report      │       │  (Audit Log & Clean Close)│
                      │ • SAP PM01 Work Order     │       └─────────────┬─────────────┘
                      └─────────────┬─────────────┘                     │
                                    │                                   │
                                    └───────────────┬───────────────────┘
                                                    ▼
                                                  [END]
```

### Key Architectural Tenets
1. **Deterministic Preprocessing Over Raw TSDB Floats:**
   - Raw time-series arrays are NEVER passed directly into reasoning models.
   - Deterministic feature extractors calculate statistical profiles, two-window sliding change-points, and discrete FFT spectrums (extracting 1X/2X fundamental shaft harmonics vs. 2–8 kHz broadband cavitation floor energy).
2. **In-Memory `TelemetryCache`:**
   - Thread-safe caching keyed by `(dataset_id, tag, start_idx, end_idx, analysis_type)` guarantees that parallel hypothesis workers testing overlapping tags (e.g., `VI-301-R` and `IT-30101`) execute with zero redundant computation.
3. **State Persistence & Clean HITL Resumption:**
   - Built on `langgraph.checkpoint.memory.MemorySaver`. Graph state is checkpointed at every step.
   - The dedicated `human_review` node halts using `langgraph.types.interrupt`, surfacing an engineering review card. Resumes cleanly with `Command(resume=...)`.

---

## 🏭 Embedded Case Study: Boiler Feed Pump (`P-301A`) Trip

A 60-minute, 1 Hz synthetic telemetry dataset representing a multi-stage centrifugal pump in a petrochemical feedwater utility:

### Asset & OEM Operational Limits
- **Asset ID:** `P-301A` (Sulzer GSG 150-360 6-Stage Centrifugal Pump)
- **Rated Running Speed:** 2980 RPM ($1\times \approx 49.67$ Hz, $2\times \approx 99.33$ Hz)
- **Net Positive Suction Head Required ($NPSH_r$):** 1.20 bar
- **Normal Suction Pressure:** $2.30 - 2.50$ bar
- **Bearing Temp Trip Limit:** $\ge 90.0^\circ$C (Alarm at $80.0^\circ$C)
- **Vibration Trip Limit:** $\ge 7.10$ mm/s RMS (ISO 10816 Class III Zone D)
- **Strainer Basket Delta-P ($\Delta P$):** Normal $\le 0.25$ bar; High Alarm $\ge 1.00$ bar

### ISA-95 Asset Topology
```
[TK-300 Deaerator] ──▶ [STR-301A Suction Strainer] ──▶ [LINE-30101 Suction Pipe] ──▶ [P-301A Boiler Feed Pump] ──▶ [CV-30101 Check Valve] ──▶ [HDR-300]
                             (DPS-30101)                         (PT-30101)              (VI-301-R, TI-301-DE)
                                                                                          [M-301A Motor Drive]
                                                                                               (IT-30101)
```

### Telemetry Scenarios
1. **Normal Operating Baseline:** 60 minutes of stable operation within healthy envelopes ($PT \approx 2.4$ bar, $\Delta P \approx 0.12$ bar, $VI \approx 1.8$ mm/s, $TI \approx 48.5^\circ$C, $IT \approx 84.2$ A). Verified to trigger **0 false alarms**.
2. **Fault Scenario (Strainer Clogging Induced Cavitation):**
   - $T_0 - T_{30\text{m}}$: Normal baseline.
   - $T_{30\text{m}} - T_{50\text{m}}$: Marine fouling clogs `STR-301A`. $\Delta P$ ramps $0.12 \to 1.85$ bar.
   - $T_{45\text{m}}$ ($T=2700$s): Suction pressure `PT-30101` drops below $NPSH_r$ ($1.20$ bar), plunging to $0.58$ bar.
   - $T_{48\text{m}}$ ($T=2880$s): Impeller cavitates. `VI-301-R` broadband noise floor explodes ($2.0 - 8.0$ kHz ratio reaches $48.9\%$, overall RMS spikes to $11.4$ mm/s), and motor current fluctuates $\pm 22\%$.
   - $T_{55\text{m}}$ ($T=3300$s): High-friction load elevates drive-end bearing temperature `TI-301-DE` past trip limit ($92.3^\circ$C), tripping the DCS at 03:14 AM.

---

## 📁 Project Structure

```
industrial_rca/
├── README.md                          # Comprehensive architectural and operational guide
├── requirements.txt                   # Dependency specifications
├── config.py                          # Engineering setpoints, sample rates, constants
├── data/
│   ├── asset_topology.json            # ISA-95 plant topology definition
│   ├── oem_manuals.py                 # OEM specifications, ISO 14224 taxonomy, FMEA matrix
│   └── telemetry_generator.py         # 1 Hz TSDB synthesizer & 20 kHz vibration FFT bursts
├── tools/
│   ├── telemetry_analytics.py         # Profiler, change-point detector, FFT analyzer, TelemetryCache
│   ├── cmms_connector.py              # Mock CMMS (SAP PM / IBM Maximo), SAP PM01 work order generator
│   └── topology_tracer.py             # ISA-95 upstream/downstream directed graph tracer
├── graph/
│   ├── state.py                       # RCAState schema, TypedDicts, reducers
│   ├── nodes.py                       # Ingestion, anomaly detection, parallel workers, HITL interrupt
│   └── workflow.py                    # Compiled LangGraph pipeline with MemorySaver
├── main.py                            # Interactive Rich CLI runner
└── tests/
    └── test_rca_system.py             # Pytest test suite (10 unit & integration tests)
```

---

## 🚀 Execution & Usage Guide

### 1. Installation
Ensure Python 3.11+ is installed. Install required packages:
```bash
python3 -m pip install -r industrial_rca/requirements.txt
```

### 2. Interactive Run (Default)
Run the complete workflow interactively with full Rich terminal formatting:
```bash
python3 industrial_rca/main.py
```
*At the HITL verification card, prompt will pause and prompt:*
`Engineer Action: [A]pprove Root Cause / [O]verride / [R]eject [A]: `

### 3. Automated / Headless Modes
```bash
# Automated approval:
python3 industrial_rca/main.py --auto-approve

# Automated override:
python3 industrial_rca/main.py --override

# Automated rejection:
python3 industrial_rca/main.py --reject
```

### 4. Running the Test Suite
Execute the 10-test automated test suite:
```bash
python3 -m pytest industrial_rca/tests/test_rca_system.py -v
```

---

## 📋 Sample Deliverables Emitted by the System

### 1. Standard 8D Incident Report
- **D1 (Team):** Incident Lead, Operations Lead, Hydraulic Specialist, CMMS Coordinator.
- **D2 (Problem Description):** 5W2H framing of the 03:14 AM bearing overheat trip on `P-301A`.
- **D3 (Interim Containment):** Verify standby pump `P-301B`, LOTO electrical breaker `33-SWG-P301A`, isolate suction/discharge valves.
- **D4 (Root Cause Analysis):** Upstream `STR-301A` strainer blinding -> suction depression below $NPSH_r$ -> destructive impeller cavitation -> bearing thermal trip. Includes 5-Whys causal trace and ISO 14224 code (`ISO-14224-PU-HYD-CAV`).
- **D5 (Permanent Corrective Actions):** Replace strainer basket with 316SS 20-mesh screen, re-calibrate DPS alarm at 0.80 bar, boroscope inspection of impeller eye, flush bearing lube oil.
- **D6 (Validation Protocol):** 2-hour full-load validation under vibration surveillance ($RMS < 2.0$ mm/s, broadband ratio $< 5\%$).
- **D7 (Systemic Prevention):** Reclassify strainer cleaning as reliability-critical in SAP PM; eliminate unsupervised operational deferrals.
- **D8 (Sign-off):** Formal engineering sign-off.

### 2. SAP PM01 Corrective Work Order
- **Order Number:** `400924813` | **Type:** `PM01` (Corrective Maintenance)
- **Functional Location:** `FLOC: PLNT-B03-FW300-P301A`
- **Equipment:** `10049201 - P-301A High-Pressure Boiler Feed Pump A`
- **Priority:** `1 - Emergency / Immediate Outage` | **Breakdown:** `X (True)`
- **Operations (0010 - 0050):** LOTO, Strainer Basket Replacement, Impeller Boroscopy, Bearing Inspection/Lube Flush, Commissioning & Vibration Sign-off.
- **Bill of Materials (BOM):** Fluorocarbon Cover Gaskets, 316SS Replacement Basket, Shell Turbo T 46 Lubricating Oil (40 L), Sleeve Bearing Insert.
