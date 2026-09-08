"""
Industrial Root Cause Analysis (RCA) System — Interactive Web Dashboard.
Built with Streamlit, LangGraph, Plotly, and DeepSeek AI.
Complies with ISA-95, ISO 14224 / FMEA, ISO 10816 Class III, Global 8D, and SAP PM01.

UI: Dark industrial control-room theme with glassmorphism panels.
"""

import sys
import json
import time
from pathlib import Path
from typing import Dict, Any, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from langgraph.types import Command

from industrial_rca.config import (
    EQUIPMENT_ID,
    EQUIPMENT_NAME,
    OPERATIONAL_LIMITS,
    DEFAULT_THREAD_ID,
    RUNNING_FREQUENCY_1X_HZ,
    RUNNING_FREQUENCY_2X_HZ,
)
from industrial_rca.data.telemetry_generator import (
    generate_normal_scenario,
    generate_fault_scenario,
    TelemetryStore,
)
from industrial_rca.tools.telemetry_analytics import (
    TelemetryAnalyticsTool,
    GLOBAL_TELEMETRY_CACHE,
)
from industrial_rca.graph.workflow import create_rca_graph
from industrial_rca.tools.deepseek_client import DeepSeekClient


# ── Page Config ───────────────────────────────────────────────────────
st.set_page_config(
    page_title="Industrial RCA System | Plant Diagnostics",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ── CSS Theme ─────────────────────────────────────────────────────────
st.markdown("""
<style>
/* ── Base ────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap');

:root {
    --bg-primary: #0B0F19;
    --bg-card: #111827;
    --bg-card-hover: #1A2332;
    --border-subtle: rgba(99,179,237,0.12);
    --border-glow: rgba(0,212,170,0.25);
    --accent: #00D4AA;
    --accent-dim: rgba(0,212,170,0.15);
    --warning: #FFB020;
    --danger: #FF4B4B;
    --danger-dim: rgba(255,75,75,0.15);
    --text-primary: #E2E8F0;
    --text-secondary: #8892B0;
    --text-muted: #64748B;
    --font-mono: 'JetBrains Mono', monospace;
    --font-sans: 'Inter', sans-serif;
}

.stApp { background-color: var(--bg-primary) !important; }
section[data-testid="stSidebar"] { background-color: #0D1321 !important; border-right: 1px solid var(--border-subtle); }

/* ── Glass Card ─────────────────────────────────── */
.glass-card {
    background: linear-gradient(135deg, rgba(17,24,39,0.92), rgba(15,23,42,0.88));
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    padding: 20px 24px;
    margin-bottom: 16px;
    backdrop-filter: blur(12px);
    transition: border-color 0.2s, box-shadow 0.2s;
}
.glass-card:hover {
    border-color: var(--border-glow);
    box-shadow: 0 0 20px rgba(0,212,170,0.08);
}

/* ── Header Banner ──────────────────────────────── */
.header-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    background: linear-gradient(90deg, #0D1321 0%, #111827 50%, #0D1321 100%);
    border: 1px solid var(--border-subtle);
    border-radius: 12px;
    margin-bottom: 20px;
}
.header-title {
    font-family: var(--font-sans);
    font-size: 1.6rem;
    font-weight: 700;
    color: var(--text-primary);
    letter-spacing: -0.02em;
}
.header-subtitle {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    color: var(--text-muted);
    margin-top: 2px;
    letter-spacing: 0.04em;
}
.status-pill {
    display: inline-block;
    padding: 6px 16px;
    border-radius: 20px;
    font-family: var(--font-mono);
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.06em;
}
.pill-fault {
    background: var(--danger-dim);
    color: var(--danger);
    border: 1px solid rgba(255,75,75,0.3);
    animation: pulse-red 2s ease-in-out infinite;
}
.pill-nominal {
    background: var(--accent-dim);
    color: var(--accent);
    border: 1px solid rgba(0,212,170,0.3);
}
@keyframes pulse-red {
    0%, 100% { box-shadow: 0 0 4px rgba(255,75,75,0.2); }
    50% { box-shadow: 0 0 16px rgba(255,75,75,0.45); }
}

/* ── KPI Metric Card ────────────────────────────── */
.kpi-card {
    background: linear-gradient(135deg, rgba(17,24,39,0.95), rgba(15,23,42,0.9));
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 16px 18px;
    text-align: center;
    min-height: 120px;
    transition: transform 0.15s, border-color 0.2s;
}
.kpi-card:hover { transform: translateY(-2px); border-color: var(--border-glow); }
.kpi-icon { font-size: 1.5rem; margin-bottom: 6px; }
.kpi-label {
    font-family: var(--font-mono);
    font-size: 0.65rem;
    color: var(--text-muted);
    text-transform: uppercase;
    letter-spacing: 0.08em;
    margin-bottom: 6px;
}
.kpi-value {
    font-family: var(--font-mono);
    font-size: 1.35rem;
    font-weight: 700;
    color: var(--text-primary);
}
.kpi-delta {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    margin-top: 4px;
}
.kpi-delta-danger { color: var(--danger); }
.kpi-delta-ok { color: var(--accent); }
.kpi-delta-warn { color: var(--warning); }
.kpi-border-danger { border-left: 3px solid var(--danger); }
.kpi-border-ok { border-left: 3px solid var(--accent); }
.kpi-border-warn { border-left: 3px solid var(--warning); }
.kpi-border-info { border-left: 3px solid #60A5FA; }

/* ── Pipeline Stepper ───────────────────────────── */
.stepper-bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 20px;
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    margin-bottom: 20px;
    overflow-x: auto;
}
.step-node {
    display: flex;
    flex-direction: column;
    align-items: center;
    min-width: 80px;
    position: relative;
}
.step-circle {
    width: 28px; height: 28px;
    border-radius: 50%;
    display: flex; align-items: center; justify-content: center;
    font-family: var(--font-mono);
    font-size: 0.7rem; font-weight: 700;
    margin-bottom: 6px;
    transition: all 0.3s;
}
.step-done { background: var(--accent); color: #0B0F19; }
.step-active { background: transparent; border: 2px solid var(--accent); color: var(--accent); animation: pulse-glow 1.5s infinite; }
.step-pending { background: #1E293B; border: 1px solid #334155; color: #64748B; }
@keyframes pulse-glow {
    0%, 100% { box-shadow: 0 0 4px rgba(0,212,170,0.3); }
    50% { box-shadow: 0 0 14px rgba(0,212,170,0.6); }
}
.step-label {
    font-family: var(--font-mono);
    font-size: 0.55rem;
    color: var(--text-muted);
    text-align: center;
    max-width: 80px;
    line-height: 1.25;
}
.step-connector {
    flex: 1;
    height: 2px;
    margin: 0 4px 20px 4px;
    min-width: 16px;
}
.connector-done { background: var(--accent); }
.connector-pending { background: #334155; }

/* ── Hypothesis Cards ───────────────────────────── */
.hyp-card {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 12px;
    border-left: 4px solid;
    transition: border-color 0.2s;
}
.hyp-confirmed { border-left-color: var(--accent); }
.hyp-secondary { border-left-color: var(--warning); }
.hyp-refuted { border-left-color: var(--danger); }
.hyp-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 8px;
}
.hyp-name {
    font-family: var(--font-sans);
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text-primary);
}
.hyp-badge {
    padding: 3px 10px;
    border-radius: 12px;
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 600;
    letter-spacing: 0.04em;
}
.badge-confirmed { background: rgba(0,212,170,0.15); color: var(--accent); border: 1px solid rgba(0,212,170,0.3); }
.badge-secondary { background: rgba(255,176,32,0.15); color: var(--warning); border: 1px solid rgba(255,176,32,0.3); }
.badge-refuted { background: rgba(255,75,75,0.15); color: var(--danger); border: 1px solid rgba(255,75,75,0.3); }
.conf-bar-bg {
    background: #1E293B;
    border-radius: 6px;
    height: 6px;
    margin: 8px 0 6px 0;
    overflow: hidden;
}
.conf-bar-fill {
    height: 100%;
    border-radius: 6px;
    transition: width 0.5s;
}
.hyp-rationale {
    font-family: var(--font-sans);
    font-size: 0.82rem;
    color: var(--text-secondary);
    line-height: 1.5;
    margin-top: 8px;
}

/* ── 5-Whys Timeline ────────────────────────────── */
.timeline-container { padding: 10px 0 10px 24px; position: relative; }
.timeline-container::before {
    content: '';
    position: absolute;
    left: 37px;
    top: 0; bottom: 0;
    width: 2px;
    background: linear-gradient(180deg, var(--accent), var(--border-subtle));
}
.timeline-item {
    position: relative;
    padding: 12px 0 12px 40px;
    margin-bottom: 4px;
}
.timeline-dot {
    position: absolute;
    left: -12px; top: 14px;
    width: 24px; height: 24px;
    border-radius: 50%;
    background: var(--accent);
    color: #0B0F19;
    display: flex; align-items: center; justify-content: center;
    font-family: var(--font-mono);
    font-size: 0.65rem; font-weight: 700;
    z-index: 2;
}
.timeline-question {
    font-family: var(--font-sans);
    font-weight: 600;
    font-size: 0.95rem;
    color: var(--text-primary);
    margin-bottom: 4px;
}
.timeline-answer {
    font-family: var(--font-sans);
    font-size: 0.85rem;
    color: var(--text-secondary);
    line-height: 1.55;
    margin-bottom: 4px;
}
.timeline-asset-badge {
    display: inline-block;
    padding: 2px 8px;
    background: rgba(96,165,250,0.15);
    color: #60A5FA;
    border: 1px solid rgba(96,165,250,0.3);
    border-radius: 4px;
    font-family: var(--font-mono);
    font-size: 0.65rem;
    font-weight: 500;
}
.timeline-evidence {
    font-family: var(--font-mono);
    font-size: 0.7rem;
    color: var(--text-muted);
    margin-top: 4px;
}

/* ── HITL Decision Panel ────────────────────────── */
.hitl-panel {
    background: linear-gradient(135deg, rgba(17,24,39,0.95), rgba(15,23,42,0.9));
    border: 1px solid var(--border-subtle);
    border-radius: 14px;
    padding: 28px 32px;
    max-width: 700px;
    margin: 0 auto;
}
.hitl-status {
    text-align: center;
    margin-bottom: 20px;
}
.hitl-badge-waiting {
    display: inline-block;
    padding: 8px 24px;
    background: rgba(255,176,32,0.12);
    color: var(--warning);
    border: 1px solid rgba(255,176,32,0.3);
    border-radius: 24px;
    font-family: var(--font-mono);
    font-size: 0.8rem;
    font-weight: 600;
    letter-spacing: 0.05em;
    animation: pulse-amber 2s ease-in-out infinite;
}
@keyframes pulse-amber {
    0%, 100% { box-shadow: 0 0 4px rgba(255,176,32,0.2); }
    50% { box-shadow: 0 0 16px rgba(255,176,32,0.4); }
}

/* ── 8D Section Cards ───────────────────────────── */
.section-8d {
    background: var(--bg-card);
    border: 1px solid var(--border-subtle);
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 10px;
}
.section-8d-header {
    font-family: var(--font-mono);
    font-size: 0.72rem;
    font-weight: 600;
    color: var(--accent);
    text-transform: uppercase;
    letter-spacing: 0.06em;
    margin-bottom: 8px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-subtle);
}
.section-8d-body {
    font-family: var(--font-sans);
    font-size: 0.85rem;
    color: var(--text-secondary);
    line-height: 1.6;
}

/* ── ISA-95 Tree ────────────────────────────────── */
.isa-tree { padding: 10px 0; }
.isa-node {
    font-family: var(--font-mono);
    font-size: 0.8rem;
    color: var(--text-secondary);
    padding: 3px 0;
    line-height: 1.6;
}
.isa-node-root {
    color: var(--danger);
    font-weight: 600;
    background: rgba(255,75,75,0.08);
    padding: 2px 8px;
    border-radius: 4px;
    display: inline;
}
.isa-node-primary {
    color: var(--warning);
    font-weight: 600;
}

/* ── DeepSeek AI Card ───────────────────────────── */
.ds-card {
    background: linear-gradient(135deg, rgba(88,28,135,0.15), rgba(17,24,39,0.9));
    border: 1px solid rgba(139,92,246,0.25);
    border-radius: 12px;
    padding: 20px 24px;
    margin-top: 16px;
}
.ds-header {
    font-family: var(--font-sans);
    font-weight: 600;
    font-size: 1rem;
    color: #A78BFA;
    margin-bottom: 10px;
}

/* ── Misc ───────────────────────────────────────── */
.divider {
    height: 1px;
    background: var(--border-subtle);
    margin: 20px 0;
}
.section-title {
    font-family: var(--font-sans);
    font-size: 1.15rem;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 14px;
    letter-spacing: -0.01em;
}
.mono { font-family: var(--font-mono); }
.text-muted { color: var(--text-muted); }
.text-accent { color: var(--accent); }
.text-danger { color: var(--danger); }
.text-warning { color: var(--warning); }

/* Hide default Streamlit branding / footer */
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

/* Plotly chart container padding */
div[data-testid="stPlotlyChart"] { margin-top: -10px; }
</style>
""", unsafe_allow_html=True)


# ── Session State ─────────────────────────────────────────────────────
if "graph" not in st.session_state:
    st.session_state.graph = create_rca_graph()
if "thread_id" not in st.session_state:
    st.session_state.thread_id = f"rca-gui-{int(time.time())}"
if "pipeline_run" not in st.session_state:
    st.session_state.pipeline_run = False
if "paused_state" not in st.session_state:
    st.session_state.paused_state = None
if "final_state" not in st.session_state:
    st.session_state.final_state = None
if "ds_normal" not in st.session_state:
    st.session_state.ds_normal = generate_normal_scenario()
if "ds_fault" not in st.session_state:
    st.session_state.ds_fault = generate_fault_scenario()
if "hitl_chat_history" not in st.session_state:
    st.session_state.hitl_chat_history = [
        {
            "role": "assistant",
            "content": (
                "👋 **Hello Operator.** I am your **Industrial RCA Diagnostic Copilot**.\n\n"
                "I have evaluated the emergency trip telemetry on **Boiler Feed Pump P-301A**, "
                "the 20 kHz vibration spectrum, and the upstream ISA-95 topology.\n\n"
                "Ask me anything before authorizing the maintenance deliverables:\n"
                "- *Why was motor overload (H3) ruled out?*\n"
                "- *What is the acoustic evidence for impeller cavitation?*\n"
                "- *What does CMMS work order WM-2026-0831 indicate?*\n"
                "- *Can you draft engineering justification notes for my sign-off?*"
            ),
            "reasoning": None,
        }
    ]
if "hitl_review_notes" not in st.session_state:
    st.session_state.hitl_review_notes = (
        "Root cause verified through multi-sensor physics convergence and ISA-95 topology tracing. "
        "Upstream suction strainer STR-301A blinded due to deferred PM WM-2026-0831, causing suction "
        "pressure PT-30101 (0.58 bar) to plummet below NPSHr (1.20 bar). Severe acoustic cavitation confirmed by "
        "20 kHz FFT (48.9% broadband ratio), inducing 11.4 mm/s RMS vibration that wiped the DE sleeve bearing lubrication film. "
        "Authorize SAP PM01 corrective work order for strainer overhaul and impeller boroscopic inspection."
    )


# ── Sidebar ───────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style="text-align:center; padding: 12px 0 8px 0;">
        <span style="font-size:2rem;">🏭</span><br>
        <span style="font-family:var(--font-sans); font-size:1.05rem; font-weight:700; color:#E2E8F0;">RCA Control Panel</span><br>
        <span style="font-family:var(--font-mono); font-size:0.6rem; color:#64748B; letter-spacing:0.06em;">INDUSTRIAL DIAGNOSTICS v2.0</span>
    </div>
    """, unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    st.markdown('<p style="font-family:var(--font-mono); font-size:0.65rem; color:#64748B; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:8px;">⚙ Asset Configuration</p>', unsafe_allow_html=True)
    st.markdown("""
    <div class="glass-card" style="padding:12px 16px;">
        <span class="mono" style="font-size:0.75rem; color:#60A5FA;">P-301A</span>
        <span style="font-size:0.75rem; color:#8892B0;"> — HP Boiler Feed Pump</span><br>
        <span class="mono" style="font-size:0.62rem; color:#64748B;">ISA-95 · ISO 14224 · ISO 10816</span>
    </div>
    """, unsafe_allow_html=True)

    scenario_choice = st.selectbox(
        "Telemetry Stream",
        [
            "⚠ Fault: Strainer Clogging & Cavitation Trip",
            "✅ Baseline: Normal Stable Operation",
        ],
        index=0,
        label_visibility="collapsed",
    )

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<p style="font-family:var(--font-mono); font-size:0.65rem; color:#64748B; letter-spacing:0.08em; text-transform:uppercase; margin-bottom:8px;">🤖 AI Engine</p>', unsafe_allow_html=True)

    use_deepseek = st.toggle("DeepSeek AI Reasoning", value=True)
    deepseek_model = st.selectbox(
        "Model",
        ["deepseek-chat", "deepseek-reasoner"],
        index=0,
        help="deepseek-chat (V3) for fast synthesis, deepseek-reasoner (R1) for CoT causal validation.",
        label_visibility="collapsed",
    )

    if st.button("⚡ Test Connection", use_container_width=True):
        ds_client = DeepSeekClient(default_model=deepseek_model)
        conn = ds_client.test_connection()
        if conn["status"] == "ONLINE":
            st.success(f"Online · {'Live API' if conn['is_live'] else 'Simulation'}", icon="✅")
        else:
            st.error("Connection failed", icon="❌")

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    if st.button("🔄 Reset Pipeline", type="primary", use_container_width=True):
        st.session_state.thread_id = f"rca-gui-{int(time.time())}"
        st.session_state.pipeline_run = False
        st.session_state.paused_state = None
        st.session_state.final_state = None
        st.session_state.hitl_chat_history = [
            {
                "role": "assistant",
                "content": (
                    "👋 **Hello Operator.** I am your **Industrial RCA Diagnostic Copilot**.\n\n"
                    "I have evaluated the emergency trip telemetry on **Boiler Feed Pump P-301A**, "
                    "the 20 kHz vibration spectrum, and the upstream ISA-95 topology.\n\n"
                    "Ask me anything before authorizing the maintenance deliverables:\n"
                    "- *Why was motor overload (H3) ruled out?*\n"
                    "- *What is the acoustic evidence for impeller cavitation?*\n"
                    "- *What does CMMS work order WM-2026-0831 indicate?*\n"
                    "- *Can you draft engineering justification notes for my sign-off?*"
                ),
                "reasoning": None,
            }
        ]
        st.rerun()


# ── Data Selection ────────────────────────────────────────────────────
is_fault_scenario = "Fault" in scenario_choice
active_ds = st.session_state.ds_fault if is_fault_scenario else st.session_state.ds_normal


# ── Pipeline Execution ────────────────────────────────────────────────
if not st.session_state.pipeline_run:
    with st.spinner("Executing LangGraph pipeline with physics feature extractors..."):
        ds_id = TelemetryStore.register(active_ds, "gui_active_dataset")
        config = {"configurable": {"thread_id": st.session_state.thread_id}}
        init_state = {
            "dataset_id": ds_id,
            "asset_id": EQUIPMENT_ID,
            "use_deepseek": use_deepseek,
            "deepseek_model": deepseek_model,
        }
        for event in st.session_state.graph.stream(init_state, config=config):
            pass
        state_snapshot = st.session_state.graph.get_state(config)
        st.session_state.paused_state = state_snapshot
        st.session_state.pipeline_run = True


state_vals = st.session_state.paused_state.values if st.session_state.paused_state else {}
is_at_interrupt = bool(
    st.session_state.paused_state
    and st.session_state.paused_state.tasks
    and st.session_state.paused_state.tasks[0].interrupts
)
review_payload = (
    st.session_state.paused_state.tasks[0].interrupts[0].value
    if is_at_interrupt
    else {}
)


# ══════════════════════════════════════════════════════════════════════
# HELPER: Plotly dark template
# ══════════════════════════════════════════════════════════════════════
PLOTLY_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(11,15,25,0.6)",
    font=dict(family="JetBrains Mono, monospace", size=11, color="#8892B0"),
    margin=dict(l=50, r=20, t=36, b=40),
    xaxis=dict(gridcolor="rgba(99,179,237,0.08)", zerolinecolor="rgba(99,179,237,0.08)"),
    yaxis=dict(gridcolor="rgba(99,179,237,0.08)", zerolinecolor="rgba(99,179,237,0.08)"),
    legend=dict(bgcolor="rgba(0,0,0,0)", font=dict(size=10)),
    hoverlabel=dict(bgcolor="#1E293B", bordercolor="#334155", font=dict(family="JetBrains Mono", size=11)),
)


def _plotly_base(title: str = "", height: int = 300) -> go.Figure:
    """Create a base Plotly figure with the dark industrial template."""
    fig = go.Figure()
    fig.update_layout(**PLOTLY_LAYOUT, title=dict(text=title, font=dict(size=13, color="#E2E8F0"), x=0.01), height=height)
    return fig


# ══════════════════════════════════════════════════════════════════════
# HELPER: Pipeline step index
# ══════════════════════════════════════════════════════════════════════
def _get_pipeline_step() -> int:
    """Determine the current pipeline step index (0-6)."""
    if st.session_state.final_state:
        return 7  # all done
    if is_at_interrupt:
        return 5  # at HITL
    if not st.session_state.pipeline_run:
        return 0
    if not is_fault_scenario:
        return 2  # stopped at anomaly detection (no anomalies)
    return 5  # default: at HITL


PIPELINE_STEPS = [
    ("1", "Ingest"),
    ("2", "Anomaly\nDetection"),
    ("3", "Hypothesis\nGeneration"),
    ("4", "Parallel\nFalsification"),
    ("5", "5-Whys\nTrace"),
    ("6", "HITL\nGate"),
    ("7", "Deliverables"),
]


def build_hitl_copilot_messages(
    user_question: str,
    history: List[Dict[str, Any]],
    review_payload: Dict[str, Any],
    state_vals: Dict[str, Any],
    spec_data: Dict[str, Any],
) -> List[Dict[str, str]]:
    """Build grounded contextual prompt for the HITL AI Diagnostic Copilot."""
    overall_rms = spec_data.get("overall_rms", 11.4)
    cav_ratio = spec_data.get("broadband_cavitation_ratio_pct", 48.9)
    f1 = spec_data.get("fundamental_1x_hz", 49.7)
    amp_1x = spec_data.get("peak_1x_amplitude_mms", 2.8)
    amp_2x = spec_data.get("peak_2x_amplitude_mms", 1.2)
    winning_h = review_payload.get("winning_hypothesis", "NPSH Starvation Induced Impeller Cavitation")
    conf = review_payload.get("confidence_pct", 98.0)
    root_asset = review_payload.get("root_cause_asset", "STR-301A")
    cmms_order = review_payload.get("cmms_overdue_work_order", "WM-2026-0831 (Bi-weekly strainer flush deferred)")

    system_prompt = f"""You are the Lead Machinery Reliability AI Copilot for Global PetroChem Refining Corp.
You are advising plant operators and reliability engineers inside the Human-in-the-Loop (HITL) authorization gate for Boiler Feed Pump P-301A.

LIVE INCIDENT TELEMETRY & PHYSICS EVIDENCE:
- Critical Asset: P-301A (HP Centrifugal Boiler Feed Pump, Unit 300, Area 03, Site Alpha)
- Emergency Trip Event: 03:14:00 AM (T=3300s) on high Drive-End bearing temp TI-301-DE = 92.3°C (Trip threshold: 90.0°C).
- Prior Vibration Surge: Spiked at T=2880s to VI-301-R = 11.4 mm/s RMS (ISO 10816 Class III Zone D damage threshold: 7.1 mm/s RMS).
- Suction Pressure Depression: PT-30101 plummeted from 2.40 bar down to 0.58 bar (OEM NPSHr requirement: 1.20 bar, severe fluid starvation).
- Upstream Suction Strainer: STR-301A differential pressure DPS-30101 surged from 0.12 bar to 1.85 bar (Alarm: 1.00 bar, Trip: 1.80 bar).
- High-Frequency 20 kHz FFT Decomposition: Overall RMS = {overall_rms:.2f} mm/s. Discrete 1X ({f1:.1f} Hz) = {amp_1x:.2f} mm/s, 2X = {amp_2x:.2f} mm/s. Broadband cavitation ratio (2.0-8.0 kHz) is {cav_ratio:.1f}% (Alarm threshold > 35%). Confirms acoustic micro-implosions from vapor bubble collapse.
- FMEA Hypothesis Falsification Matrix:
  * H1 (Bearing Lube Starvation): REFUTED as root cause (Secondary symptom). Lube oil analysis clean; thermal runaway occurred 7 minutes AFTER violent 11.4 mm/s vibration destroyed the hydrodynamic oil wedge.
  * H2 (NPSH Starvation Cavitation): CONFIRMED ({conf:.1f}% confidence). Direct correlation between strainer dP surge, suction pressure dropping below NPSHr, and acoustic cavitation explosion.
  * H3 (Drive Motor Electrical Overload): REFUTED. Steady-state motor current (84.2 A) remained below continuous 115.0 A FLA. Current hunting (±22%) was caused by two-phase fluid load fluctuations, not electrical fault.
- 5-Whys Causal Chain:
  * Why 1: Pump tripped on bearing temperature TI-301-DE (92.3°C > 90°C).
  * Why 2: DE bearing overheated because 11.4 mm/s RMS radial vibration broke down hydrodynamic lubrication.
  * Why 3: Vibration surged due to acoustic fluid cavitation at first-stage impeller eye (FFT 2-8 kHz broadband energy ratio {cav_ratio:.1f}%).
  * Why 4: Cavitation occurred because suction pressure PT-30101 (0.58 bar) plummeted below NPSHr (1.20 bar).
  * Why 5 (Root Cause): Suction pressure collapsed because upstream Suction Strainer STR-301A basket blinded with biofouling/debris due to deferred 14-day PM flush.
- CMMS Maintenance History: {cmms_order}. Deferred 12 days past scheduled execution due to peak steam production.
- Winning Diagnosis: {winning_h} on upstream root cause asset {root_asset}.

GUIDELINES FOR YOUR RESPONSES:
1. Provide concise, engineering-grade answers citing sensor tags, ISO standards (ISO 10816, ISO 14224), and OEM thresholds.
2. Explain the physical causality clearly (fluid mechanics, cavitation acoustics, rotordynamics, tribology).
3. If the operator asks to draft review notes, provide an audit-ready justification statement suitable for formal sign-off in the SAP PM01 review form.
4. Maintain a professional, authoritative, helpful tone."""

    messages = [{"role": "system", "content": system_prompt}]
    for msg in history[-6:]:
        if msg.get("role") in ("user", "assistant"):
            messages.append({"role": msg["role"], "content": msg["content"]})
    messages.append({"role": "user", "content": user_question})
    return messages


# ── Header Banner ─────────────────────────────────────────────────────
if is_fault_scenario:
    status_html = '<span class="status-pill pill-fault">● ACTIVE FAULT — EMERGENCY TRIP</span>'
else:
    status_html = '<span class="status-pill pill-nominal">● NOMINAL OPERATION</span>'

st.markdown(f"""
<div class="header-banner">
    <div>
        <div class="header-title">🏭 Industrial Root Cause Analysis System</div>
        <div class="header-subtitle">LANGGRAPH ORCHESTRATION · PHYSICS EXTRACTORS · DEEPSEEK AI DIAGNOSTICS</div>
    </div>
    <div style="text-align:right;">
        {status_html}
        <div class="header-subtitle" style="margin-top:6px;">Asset P-301A · {time.strftime('%Y-%m-%d %H:%M')}</div>
    </div>
</div>
""", unsafe_allow_html=True)


# ── Pipeline Stepper ──────────────────────────────────────────────────
current_step = _get_pipeline_step()
stepper_html = '<div class="stepper-bar">'
for i, (num, label) in enumerate(PIPELINE_STEPS):
    if i < current_step:
        circle_cls = "step-done"
        icon = "✓"
    elif i == current_step:
        circle_cls = "step-active"
        icon = num
    else:
        circle_cls = "step-pending"
        icon = num

    stepper_html += f'''
    <div class="step-node">
        <div class="step-circle {circle_cls}">{icon}</div>
        <div class="step-label">{label}</div>
    </div>'''
    if i < len(PIPELINE_STEPS) - 1:
        conn_cls = "connector-done" if i < current_step else "connector-pending"
        stepper_html += f'<div class="step-connector {conn_cls}"></div>'
stepper_html += '</div>'
st.markdown(stepper_html, unsafe_allow_html=True)


# ── Tabs ──────────────────────────────────────────────────────────────
tab_overview, tab_telemetry, tab_falsification, tab_5whys, tab_hitl, tab_deliverables = st.tabs([
    "📊 Executive Summary",
    "📈 Telemetry & FFT",
    "🧪 Hypothesis Falsification",
    "🔍 5-Whys Causal Trace",
    "🛑 HITL Gate",
    "📑 Deliverables",
])


# ══════════════════════════════════════════════════════════════════════
# TAB 1: EXECUTIVE SUMMARY
# ══════════════════════════════════════════════════════════════════════
with tab_overview:
    # KPI Metric Cards
    kpi_cols = st.columns(5)

    kpi_cols[0].markdown(f"""
    <div class="kpi-card kpi-border-info">
        <div class="kpi-icon">⚙</div>
        <div class="kpi-label">Critical Asset</div>
        <div class="kpi-value">{EQUIPMENT_ID}</div>
        <div class="kpi-delta" style="color:#60A5FA;">HP Feedwater Pump</div>
    </div>""", unsafe_allow_html=True)

    if is_fault_scenario:
        kpi_cols[1].markdown("""
        <div class="kpi-card kpi-border-danger">
            <div class="kpi-icon">🔴</div>
            <div class="kpi-label">Operating Status</div>
            <div class="kpi-value text-danger">TRIPPED</div>
            <div class="kpi-delta kpi-delta-danger">Emergency Trip @ 03:14 AM</div>
        </div>""", unsafe_allow_html=True)
    else:
        kpi_cols[1].markdown("""
        <div class="kpi-card kpi-border-ok">
            <div class="kpi-icon">🟢</div>
            <div class="kpi-label">Operating Status</div>
            <div class="kpi-value text-accent">RUNNING</div>
            <div class="kpi-delta kpi-delta-ok">Baseline Stable</div>
        </div>""", unsafe_allow_html=True)

    trip_val = "92.3°C" if is_fault_scenario else "48.5°C"
    trip_cls = "danger" if is_fault_scenario else "ok"
    kpi_cols[2].markdown(f"""
    <div class="kpi-card kpi-border-{'danger' if is_fault_scenario else 'ok'}">
        <div class="kpi-icon">🌡️</div>
        <div class="kpi-label">Bearing Temp TI-301-DE</div>
        <div class="kpi-value text-{trip_cls}">{trip_val}</div>
        <div class="kpi-delta kpi-delta-{'danger' if is_fault_scenario else 'ok'}">Trip Limit: 90.0°C</div>
    </div>""", unsafe_allow_html=True)

    vib_val = "11.4 mm/s" if is_fault_scenario else "1.8 mm/s"
    vib_zone = "Zone D" if is_fault_scenario else "Zone A"
    vib_cls = "danger" if is_fault_scenario else "ok"
    kpi_cols[3].markdown(f"""
    <div class="kpi-card kpi-border-{'danger' if is_fault_scenario else 'ok'}">
        <div class="kpi-icon">📳</div>
        <div class="kpi-label">Vibration RMS VI-301-R</div>
        <div class="kpi-value text-{vib_cls}">{vib_val}</div>
        <div class="kpi-delta kpi-delta-{vib_cls}">ISO 10816 {vib_zone}</div>
    </div>""", unsafe_allow_html=True)

    cache_stats = GLOBAL_TELEMETRY_CACHE.get_stats()
    kpi_cols[4].markdown(f"""
    <div class="kpi-card kpi-border-info">
        <div class="kpi-icon">💾</div>
        <div class="kpi-label">TSDB Cache Hit Rate</div>
        <div class="kpi-value">{cache_stats['hit_rate_pct']}%</div>
        <div class="kpi-delta" style="color:#60A5FA;">{cache_stats['hits']} queries saved</div>
    </div>""", unsafe_allow_html=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

    col_sum1, col_sum2 = st.columns([3, 2])
    with col_sum1:
        st.markdown('<div class="section-title">📋 Investigation Status</div>', unsafe_allow_html=True)

        if not is_fault_scenario:
            st.markdown("""
            <div class="glass-card" style="border-left: 3px solid var(--accent);">
                <span style="font-size:1rem;">✅</span>
                <span style="font-family:var(--font-sans); font-weight:600; color:var(--accent);"> Baseline Stable</span><br>
                <span style="font-family:var(--font-sans); font-size:0.85rem; color:var(--text-secondary);">
                    Asset operating within all OEM envelopes. Zero anomalies detected. Zero false alarms raised.
                </span>
            </div>""", unsafe_allow_html=True)

        elif is_at_interrupt:
            st.markdown("""
            <div class="glass-card" style="border-left: 3px solid var(--warning);">
                <span style="font-size:1rem;">⏸️</span>
                <span style="font-family:var(--font-sans); font-weight:600; color:var(--warning);"> HITL Interrupt Active</span><br>
                <span style="font-family:var(--font-sans); font-size:0.85rem; color:var(--text-secondary);">
                    Parallel hypothesis testing and 5-Whys causal trace complete. Graph execution paused —
                    awaiting Reliability Engineer authorization to emit maintenance artifacts.
                </span>
            </div>""", unsafe_allow_html=True)

        elif st.session_state.final_state:
            final_status = st.session_state.final_state.get("pipeline_status")
            if final_status == "COMPLETED":
                st.markdown("""
                <div class="glass-card" style="border-left: 3px solid var(--accent);">
                    <span style="font-size:1rem;">✅</span>
                    <span style="font-family:var(--font-sans); font-weight:600; color:var(--accent);"> Investigation Approved & Finalized</span><br>
                    <span style="font-family:var(--font-sans); font-size:0.85rem; color:var(--text-secondary);">
                        8D Incident Report and SAP PM01 Corrective Work Order emitted successfully.
                    </span>
                </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""
                <div class="glass-card" style="border-left: 3px solid var(--danger);">
                    <span style="font-size:1rem;">❌</span>
                    <span style="font-family:var(--font-sans); font-weight:600; color:var(--danger);"> Investigation Rejected</span><br>
                    <span style="font-family:var(--font-sans); font-size:0.85rem; color:var(--text-secondary);">
                        Incident closed without work order emission per engineer decision.
                    </span>
                </div>""", unsafe_allow_html=True)

        if is_fault_scenario and review_payload:
            winning = review_payload.get("winning_hypothesis", "N/A")
            confidence = review_payload.get("confidence_pct", 0)
            mechanism = review_payload.get("iso14224_failure_mechanism", "Impeller Cavitation")
            root_asset = review_payload.get("root_cause_asset", "STR-301A")
            cmms = review_payload.get("cmms_overdue_work_order", "N/A")

            st.markdown(f"""
            <div class="glass-card" style="margin-top:12px;">
                <div style="font-family:var(--font-sans); font-weight:600; color:var(--text-primary); margin-bottom:12px;">
                    🔬 Primary Findings
                </div>
                <table style="width:100%; font-family:var(--font-sans); font-size:0.85rem;">
                    <tr><td style="color:var(--text-muted); padding:4px 12px 4px 0; width:180px;">Failure Mechanism</td>
                        <td style="color:var(--text-primary); font-weight:500;">{mechanism}</td></tr>
                    <tr><td style="color:var(--text-muted); padding:4px 12px 4px 0;">Winning Hypothesis</td>
                        <td style="color:var(--accent); font-weight:500;">{winning} ({confidence:.1f}%)</td></tr>
                    <tr><td style="color:var(--text-muted); padding:4px 12px 4px 0;">Root Cause Asset</td>
                        <td><code style="background:#1E293B; padding:2px 8px; border-radius:4px; color:#FF4B4B; font-family:var(--font-mono); font-size:0.8rem;">{root_asset}</code> Suction Strainer</td></tr>
                    <tr><td style="color:var(--text-muted); padding:4px 12px 4px 0;">CMMS Finding</td>
                        <td style="color:var(--warning);">{cmms}</td></tr>
                </table>
            </div>""", unsafe_allow_html=True)

    with col_sum2:
        st.markdown('<div class="section-title">🗺️ ISA-95 Asset Topology</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="glass-card isa-tree">
            <div class="isa-node">🏢 Global PetroChem Refining Corp</div>
            <div class="isa-node" style="padding-left:16px;">📍 Site Alpha — Baytown Complex</div>
            <div class="isa-node" style="padding-left:32px;">🔧 Area 03: Steam & Power Generation</div>
            <div class="isa-node" style="padding-left:48px;">⚡ Unit 300: HP Boiler Feedwater Train</div>
            <div class="isa-node" style="padding-left:64px;">
                <span style="color:var(--text-muted);">TK-300</span> Deaerator Storage Tank
            </div>
            <div class="isa-node" style="padding-left:64px;">
                <span class="isa-node-root">⚠ STR-301A</span>
                <span style="color:var(--danger);"> Suction Strainer (ROOT CAUSE)</span>
            </div>
            <div class="isa-node" style="padding-left:64px;">
                <span style="color:var(--text-muted);">LINE-30101</span> Suction Piping <code style="color:#64748B; font-size:0.7rem;">PT-30101</code>
            </div>
            <div class="isa-node" style="padding-left:64px;">
                <span class="isa-node-primary">P-301A</span>
                <span style="color:var(--warning);"> Boiler Feed Pump</span>
                <code style="color:#64748B; font-size:0.7rem;">VI-301-R · TI-301-DE</code>
            </div>
            <div class="isa-node" style="padding-left:64px;">
                <span style="color:var(--text-muted);">M-301A</span> 3.3 kV Induction Motor <code style="color:#64748B; font-size:0.7rem;">IT-30101</code>
            </div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# TAB 2: TELEMETRY & FFT ANALYTICS
# ══════════════════════════════════════════════════════════════════════
with tab_telemetry:
    st.markdown('<div class="section-title">📈 Plant SCADA Telemetry Trends (1 Hz · 60 Minutes)</div>', unsafe_allow_html=True)

    df_chart = active_ds.df_1hz.copy()
    df_chart["Time_min"] = df_chart["timestamp_sec"] / 60.0

    sensor_configs = [
        {
            "tag": "TI-301-DE", "title": "Bearing Temperature — TI-301-DE",
            "unit": "°C", "color": "#FF4B4B",
            "thresholds": [
                {"val": 90.0, "label": "TRIP (90°C)", "color": "#FF4B4B"},
                {"val": 80.0, "label": "ALARM (80°C)", "color": "#FFB020"},
            ],
        },
        {
            "tag": "VI-301-R", "title": "Radial Vibration RMS — VI-301-R",
            "unit": "mm/s", "color": "#E040FB",
            "thresholds": [
                {"val": 7.1, "label": "Zone D TRIP (7.1)", "color": "#FF4B4B"},
                {"val": 4.5, "label": "Zone C ALARM (4.5)", "color": "#FFB020"},
            ],
        },
        {
            "tag": "DPS-30101", "title": "Strainer ΔP — DPS-30101",
            "unit": "bar", "color": "#FFA500",
            "thresholds": [
                {"val": 1.80, "label": "TRIP (1.80 bar)", "color": "#FF4B4B"},
                {"val": 1.00, "label": "ALARM (1.00 bar)", "color": "#FFB020"},
            ],
        },
        {
            "tag": "PT-30101", "title": "Suction Pressure — PT-30101",
            "unit": "bar", "color": "#00D4AA",
            "thresholds": [
                {"val": 1.20, "label": "NPSHr LIMIT (1.20)", "color": "#FF4B4B"},
            ],
        },
    ]

    col_t1, col_t2 = st.columns(2)
    for i, sc in enumerate(sensor_configs):
        target_col = col_t1 if i % 2 == 0 else col_t2
        with target_col:
            fig = _plotly_base(sc["title"], height=260)
            fig.add_trace(go.Scatter(
                x=df_chart["Time_min"], y=df_chart[sc["tag"]],
                mode="lines", name=sc["tag"],
                line=dict(color=sc["color"], width=1.5),
                hovertemplate=f"<b>{sc['tag']}</b><br>Time: %{{x:.1f}} min<br>Value: %{{y:.2f}} {sc['unit']}<extra></extra>",
            ))
            for th in sc["thresholds"]:
                fig.add_hline(
                    y=th["val"], line_dash="dot", line_color=th["color"], line_width=1,
                    annotation_text=th["label"],
                    annotation_position="top left",
                    annotation_font=dict(size=9, color=th["color"], family="JetBrains Mono"),
                )
            fig.update_xaxes(title_text="Time (min)", title_font=dict(size=10))
            fig.update_yaxes(title_text=sc["unit"], title_font=dict(size=10))
            st.plotly_chart(fig, use_container_width=True)

    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    fig_motor = _plotly_base("Motor Line Current — IT-30101", height=220)
    fig_motor.add_trace(go.Scatter(
        x=df_chart["Time_min"], y=df_chart["IT-30101"],
        mode="lines", name="IT-30101",
        line=dict(color="#60A5FA", width=1.5),
        hovertemplate="<b>IT-30101</b><br>Time: %{x:.1f} min<br>Current: %{y:.1f} A<extra></extra>",
    ))
    fig_motor.add_hline(y=115.0, line_dash="dot", line_color="#FF4B4B", line_width=1,
                        annotation_text="FLA (115A)", annotation_position="top left",
                        annotation_font=dict(size=9, color="#FF4B4B", family="JetBrains Mono"))
    fig_motor.update_xaxes(title_text="Time (min)", title_font=dict(size=10))
    fig_motor.update_yaxes(title_text="Amperes (A)", title_font=dict(size=10))
    st.plotly_chart(fig_motor, use_container_width=True)

    # FFT Spectrum
    st.markdown('<div class="divider"></div>', unsafe_allow_html=True)
    st.markdown('<div class="section-title">🔬 20 kHz Spectral FFT — Acoustic Cavitation Analysis</div>', unsafe_allow_html=True)

    analytics = TelemetryAnalyticsTool(GLOBAL_TELEMETRY_CACHE)
    spec_data = analytics.analyze_vibration_waveform("gui_active_dataset", is_cavitation_state=is_fault_scenario)

    col_spec1, col_spec2 = st.columns([1, 3])
    with col_spec1:
        overall_rms = spec_data.get("overall_rms", 0.0)
        rms_cls = "danger" if overall_rms > 7.1 else ("warn" if overall_rms > 4.5 else "ok")
        rms_zone = "Zone D" if overall_rms > 7.1 else ("Zone C" if overall_rms > 4.5 else "Zone A")

        st.markdown(f"""
        <div class="kpi-card kpi-border-{'danger' if rms_cls == 'danger' else ('warn' if rms_cls == 'warn' else 'ok')}" style="margin-bottom:10px;">
            <div class="kpi-label">Overall RMS</div>
            <div class="kpi-value text-{rms_cls}">{overall_rms:.2f} mm/s</div>
            <div class="kpi-delta kpi-delta-{rms_cls}">ISO 10816 {rms_zone}</div>
        </div>
        <div class="kpi-card kpi-border-info" style="margin-bottom:10px;">
            <div class="kpi-label">1X Peak (49.7 Hz)</div>
            <div class="kpi-value">{spec_data.get('peak_1x_amplitude_mms', 0.0):.2f}</div>
            <div class="kpi-delta" style="color:#60A5FA;">mm/s</div>
        </div>
        <div class="kpi-card kpi-border-info" style="margin-bottom:10px;">
            <div class="kpi-label">2X Peak (99.3 Hz)</div>
            <div class="kpi-value">{spec_data.get('peak_2x_amplitude_mms', 0.0):.2f}</div>
            <div class="kpi-delta" style="color:#60A5FA;">mm/s</div>
        </div>""", unsafe_allow_html=True)

        cav_ratio = spec_data.get("broadband_cavitation_ratio_pct", 0.0)
        cav_cls = "danger" if cav_ratio > 35 else "ok"
        st.markdown(f"""
        <div class="kpi-card kpi-border-{'danger' if cav_ratio > 35 else 'ok'}">
            <div class="kpi-label">Cavitation Energy (2-8 kHz)</div>
            <div class="kpi-value text-{cav_cls}">{cav_ratio:.1f}%</div>
            <div class="kpi-delta kpi-delta-{cav_cls}">{'⚠ ALARM > 35%' if cav_ratio > 35 else '✓ Normal'}</div>
        </div>""", unsafe_allow_html=True)

    with col_spec2:
        wf_data = active_ds.fault_waveform if is_fault_scenario else active_ds.normal_waveform
        sig = wf_data["signal"]
        n_samples = len(sig)
        fft_vals = np.fft.rfft(sig)
        freqs = np.fft.rfftfreq(n_samples, d=1.0 / 20000.0)
        mag = np.abs(fft_vals) * 2.0 / n_samples

        step = max(1, len(freqs) // 800)
        f_ds = freqs[::step]
        m_ds = mag[::step]

        fig_fft = _plotly_base("", height=380)
        fig_fft.add_trace(go.Scatter(
            x=f_ds, y=m_ds, mode="lines", name="Spectral Amplitude",
            line=dict(color="#00D4AA", width=1),
            fill="tozeroy", fillcolor="rgba(0,212,170,0.08)",
            hovertemplate="<b>%{x:.0f} Hz</b><br>Amplitude: %{y:.4f} mm/s<extra></extra>",
        ))
        fig_fft.add_vrect(
            x0=2000, x1=8000,
            fillcolor="rgba(255,75,75,0.06)", line_width=0,
            annotation_text="CAVITATION BAND (2-8 kHz)",
            annotation_position="top",
            annotation_font=dict(size=9, color="#FF4B4B", family="JetBrains Mono"),
        )
        fig_fft.add_vline(x=RUNNING_FREQUENCY_1X_HZ, line_dash="dot", line_color="#60A5FA", line_width=1,
                          annotation_text="1X", annotation_position="top",
                          annotation_font=dict(size=9, color="#60A5FA", family="JetBrains Mono"))
        fig_fft.add_vline(x=RUNNING_FREQUENCY_2X_HZ, line_dash="dot", line_color="#A78BFA", line_width=1,
                          annotation_text="2X", annotation_position="top",
                          annotation_font=dict(size=9, color="#A78BFA", family="JetBrains Mono"))
        fig_fft.update_xaxes(title_text="Frequency (Hz)", title_font=dict(size=10), type="linear")
        fig_fft.update_yaxes(title_text="Amplitude (mm/s)", title_font=dict(size=10))
        st.plotly_chart(fig_fft, use_container_width=True)

        st.markdown(f"""
        <div style="font-family:var(--font-mono); font-size:0.7rem; color:var(--text-muted); text-align:center; margin-top:-10px;">
            Diagnosis: {spec_data.get('diagnosis', 'N/A')}
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# TAB 3: HYPOTHESIS FALSIFICATION
# ══════════════════════════════════════════════════════════════════════
with tab_falsification:
    st.markdown('<div class="section-title">🧪 Parallel Hypothesis Falsification Matrix</div>', unsafe_allow_html=True)
    st.markdown('<p style="font-family:var(--font-mono); font-size:0.7rem; color:var(--text-muted); margin-top:-10px; margin-bottom:16px;">ISO 14224 FMEA · Deterministic Physics Extractors · LangGraph Send Fan-Out</p>', unsafe_allow_html=True)

    fals_list = review_payload.get("falsification_summary", state_vals.get("falsification_summary", []))

    if fals_list:
        for h in fals_list:
            status = h["status"].upper()
            if status == "CONFIRMED":
                card_cls = "hyp-confirmed"
                badge_cls = "badge-confirmed"
                bar_color = "#00D4AA"
            elif status in ("SECONDARY", "CONTRIBUTING"):
                card_cls = "hyp-secondary"
                badge_cls = "badge-secondary"
                bar_color = "#FFB020"
            else:
                card_cls = "hyp-refuted"
                badge_cls = "badge-refuted"
                bar_color = "#FF4B4B"

            confidence = h.get("confidence_pct", 0)
            st.markdown(f"""
            <div class="hyp-card {card_cls}">
                <div class="hyp-header">
                    <div>
                        <span class="hyp-name">{h['name']}</span>
                        <span class="mono" style="color:var(--text-muted); font-size:0.72rem; margin-left:8px;">{h['hypothesis_id']}</span>
                    </div>
                    <div>
                        <span class="hyp-badge {badge_cls}">{status}</span>
                        <span class="mono" style="color:var(--text-primary); font-size:0.85rem; font-weight:600; margin-left:10px;">{confidence}%</span>
                    </div>
                </div>
                <div class="conf-bar-bg">
                    <div class="conf-bar-fill" style="width:{confidence}%; background:{bar_color};"></div>
                </div>
                <div class="hyp-rationale">{h['rationale']}</div>
            </div>""", unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="glass-card" style="text-align:center; padding:40px;">
            <span style="font-size:2rem;">✅</span><br>
            <span style="font-family:var(--font-sans); color:var(--accent); font-weight:500;">No Active Anomalies</span><br>
            <span style="font-family:var(--font-sans); font-size:0.82rem; color:var(--text-muted);">
                All sensor tags within OEM envelopes. No fault hypotheses generated for baseline scenario.
            </span>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# TAB 4: 5-WHYS CAUSAL TRACE
# ══════════════════════════════════════════════════════════════════════
with tab_5whys:
    st.markdown('<div class="section-title">🔍 Upstream ISA-95 Causal Trace — 5-Whys Drill-Down</div>', unsafe_allow_html=True)

    whys = review_payload.get("causal_chain_5_whys", state_vals.get("causal_chain_5_whys", []))

    if whys:
        timeline_html = '<div class="timeline-container">'
        for i, why in enumerate(whys):
            level_num = i + 1
            timeline_html += f"""
            <div class="timeline-item">
                <div class="timeline-dot">{level_num}</div>
                <div class="timeline-question">{why.get('question', f'Why #{level_num}?')}</div>
                <div><span class="timeline-asset-badge">{why.get('asset_involved', 'N/A')}</span></div>
                <div class="timeline-answer">{why.get('answer', 'N/A')}</div>
                <div class="timeline-evidence">📎 {why.get('evidence', 'N/A')}</div>
            </div>"""
        timeline_html += '</div>'
        st.markdown(timeline_html, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="glass-card" style="text-align:center; padding:40px;">
            <span style="font-size:2rem;">🔍</span><br>
            <span style="font-family:var(--font-sans); color:var(--text-muted);">
                No causal trace generated for baseline normal operation.
            </span>
        </div>""", unsafe_allow_html=True)

    # DeepSeek AI Evaluation Card
    ds_eval = state_vals.get("deepseek_evaluation")
    if ds_eval:
        st.markdown(f"""
        <div class="ds-card">
            <div class="ds-header">🤖 DeepSeek AI Industrial Diagnosis</div>
            <div style="font-family:var(--font-mono); font-size:0.72rem; color:#8892B0; margin-bottom:12px;">
                Model: <span style="color:#A78BFA;">{ds_eval.get('model', 'N/A')}</span> ·
                Mode: <span style="color:#A78BFA;">{'Live API' if not ds_eval.get('is_mock') else 'Simulation'}</span>
            </div>
        </div>""", unsafe_allow_html=True)

        if ds_eval.get("reasoning_content"):
            with st.expander("🧠 DeepSeek-R1 Chain-of-Thought (Reasoning Tokens)", expanded=False):
                st.code(ds_eval["reasoning_content"], language="markdown")

        if ds_eval.get("content"):
            st.markdown(f"""
            <div class="glass-card" style="margin-top:12px;">
                <div style="font-family:var(--font-sans); font-size:0.88rem; color:var(--text-secondary); line-height:1.7;">
                    {ds_eval['content']}
                </div>
            </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# TAB 5: HUMAN-IN-THE-LOOP (HITL) GATE
# ══════════════════════════════════════════════════════════════════════
with tab_hitl:
    if not is_fault_scenario:
        st.markdown("""
        <div class="glass-card" style="text-align:center; padding:48px; max-width:600px; margin:40px auto;">
            <span style="font-size:2.5rem;">✅</span><br><br>
            <span style="font-family:var(--font-sans); font-weight:600; font-size:1.1rem; color:var(--accent);">No Review Required</span><br>
            <span style="font-family:var(--font-sans); font-size:0.85rem; color:var(--text-muted);">
                Normal baseline operation. No fault anomalies detected. All parameters within OEM operational envelopes.
            </span>
        </div>""", unsafe_allow_html=True)

    elif is_at_interrupt:
        # Top Header Banner
        winning_name = review_payload.get("winning_hypothesis", "Impeller Cavitation")
        confidence_val = review_payload.get("confidence_pct", 98.0)
        root_asset_id = review_payload.get("root_cause_asset", "STR-301A")
        failure_mech = review_payload.get("iso14224_failure_mechanism", "Impeller Cavitation")
        cmms_finding = review_payload.get("cmms_overdue_work_order", "WM-2026-0831 (Deferred strainer flush)")

        st.markdown(f"""
        <div class="glass-card" style="padding:16px 20px; margin-bottom:18px; border-left:4px solid var(--warning);">
            <div style="display:flex; justify-content:space-between; align-items:center; flex-wrap:wrap; gap:10px;">
                <div>
                    <span class="hitl-badge-waiting">⏸ AWAITING RELIABILITY ENGINEER AUTHORIZATION</span>
                    <div style="font-family:var(--font-sans); font-size:0.85rem; color:var(--text-secondary); margin-top:8px;">
                        LangGraph execution is suspended at <code>langgraph.types.interrupt()</code>. Interrogate the <b>AI Diagnostic Copilot</b> on the left before authorizing maintenance actions on the right.
                    </div>
                </div>
                <div style="display:flex; gap:12px; align-items:center;">
                    <span style="font-family:var(--font-mono); font-size:0.75rem; color:var(--text-muted);">Root Cause:</span>
                    <code style="color:var(--danger); font-size:0.85rem; font-weight:600;">{root_asset_id}</code>
                    <span class="hyp-badge badge-confirmed">{confidence_val:.1f}% CONFIRMED</span>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # Dual-Column HITL Interface
        col_chat, col_decision = st.columns([11, 9], gap="large")

        # ── LEFT COLUMN: AI Diagnostic Copilot Chatbot ───────────────
        with col_chat:
            st.markdown(f"""
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
                <span style="font-family:var(--font-sans); font-weight:700; font-size:1.15rem; color:var(--text-primary);">
                    💬 AI Diagnostic Copilot
                </span>
                <span class="mono" style="font-size:0.7rem; color:#A78BFA; background:rgba(167,139,250,0.12); padding:2px 8px; border-radius:12px; border:1px solid rgba(167,139,250,0.25);">
                    🤖 {deepseek_model} · {'Live' if not (state_vals.get('deepseek_evaluation', {}).get('is_mock')) else 'Simulation'}
                </span>
            </div>
            <p style="font-family:var(--font-mono); font-size:0.72rem; color:var(--text-muted); margin-bottom:10px;">
                Ask the copilot to interrogate SCADA telemetry, probe FMEA falsifications, verify ISO 10816 limits, or draft review justification notes.
            </p>
            """, unsafe_allow_html=True)

            # Quick Prompt Chips
            st.markdown('<p style="font-family:var(--font-mono); font-size:0.65rem; color:#64748B; letter-spacing:0.06em; text-transform:uppercase; margin-bottom:4px;">⚡ Quick Inquiries</p>', unsafe_allow_html=True)
            chip_col1, chip_col2, chip_col3 = st.columns(3)
            chip_prompt = None
            if chip_col1.button("❓ Rule out motor?", key="chip_motor", use_container_width=True, help="Why was motor electrical overload (H3) refuted?"):
                chip_prompt = "Why was hypothesis H3 (Drive Motor Electrical Overload) ruled out?"
            if chip_col2.button("🔬 Cavitation FFT proof?", key="chip_fft", use_container_width=True, help="Explain how the 20 kHz vibration FFT proves cavitation."):
                chip_prompt = "Explain how the 20 kHz vibration FFT proves cavitation over normal bearing unbalance."
            if chip_col3.button("📋 CMMS work order?", key="chip_cmms", use_container_width=True, help="What does CMMS work order WM-2026-0831 indicate?"):
                chip_prompt = "What does CMMS work order WM-2026-0831 indicate about the suction strainer?"

            chip_col4, chip_col5 = st.columns(2)
            if chip_col4.button("💡 Draft justification notes for approval", key="chip_notes", use_container_width=True, help="Draft audit-ready notes for the review form."):
                chip_prompt = "Please draft a concise, audit-ready engineering justification note for me to approve this RCA."
            if chip_col5.button("🛠 Containment & corrective actions", key="chip_actions", use_container_width=True, help="List immediate D3 containment and D5 permanent corrective actions."):
                chip_prompt = "What are the recommended immediate containment and permanent corrective actions?"

            # Scrollable Message Container
            chat_container = st.container(height=360)
            with chat_container:
                for msg in st.session_state.hitl_chat_history:
                    if msg["role"] == "user":
                        with st.chat_message("user", avatar="👤"):
                            st.markdown(msg["content"])
                    else:
                        with st.chat_message("assistant", avatar="🤖"):
                            st.markdown(msg["content"])
                            if msg.get("reasoning"):
                                with st.expander("🧠 DeepSeek-R1 Chain-of-Thought (Reasoning Tokens)", expanded=False):
                                    st.code(msg["reasoning"], language="markdown")

            # Chat Input Field
            chat_in = st.chat_input("Ask about telemetry, FMEA falsifications, OEM limits, or draft notes...", key="hitl_chat_input")

            prompt_to_send = chip_prompt or chat_in
            if prompt_to_send:
                # 1. Append user prompt
                st.session_state.hitl_chat_history.append({"role": "user", "content": prompt_to_send, "reasoning": None})

                # 2. Build grounded contextual messages
                spec_analytics = TelemetryAnalyticsTool(GLOBAL_TELEMETRY_CACHE)
                active_spec = spec_analytics.analyze_vibration_waveform("gui_active_dataset", is_cavitation_state=is_fault_scenario)
                messages = build_hitl_copilot_messages(
                    user_question=prompt_to_send,
                    history=st.session_state.hitl_chat_history,
                    review_payload=review_payload,
                    state_vals=state_vals,
                    spec_data=active_spec,
                )

                # 3. Query DeepSeek client
                with st.spinner("AI Copilot analyzing evidence..."):
                    ds_client = DeepSeekClient(default_model=deepseek_model)
                    res = ds_client.chat_completion(messages, model=deepseek_model)
                    resp_content = res.get("content", "Diagnostic analysis temporarily unavailable.")
                    resp_reasoning = res.get("reasoning_content")

                    st.session_state.hitl_chat_history.append({
                        "role": "assistant",
                        "content": resp_content,
                        "reasoning": resp_reasoning,
                    })

                    # If this was a request to draft notes, auto-extract into review notes
                    if any(k in prompt_to_send.lower() for k in ("draft", "note", "justif")):
                        clean_notes = resp_content.replace('**Recommended Engineering Review Notes for HITL Approval:**', '').replace('"', '').strip()
                        if len(clean_notes) > 40:
                            st.session_state.hitl_review_notes = clean_notes

                st.rerun()

            # Chat utilities row
            util_c1, util_c2 = st.columns([1, 1])
            with util_c1:
                if st.button("🗑️ Clear Chat History", key="clear_chat_btn", use_container_width=True):
                    st.session_state.hitl_chat_history = [
                        {
                            "role": "assistant",
                            "content": (
                                "👋 Chat history cleared. What questions can I answer about **Boiler Feed Pump P-301A** or the upstream topology?"
                            ),
                            "reasoning": None,
                        }
                    ]
                    st.rerun()
            with util_c2:
                if st.button("📥 Use Latest Response as Review Notes", key="use_latest_notes_btn", use_container_width=True):
                    latest_asst = [m for m in st.session_state.hitl_chat_history if m["role"] == "assistant"]
                    if latest_asst:
                        text = latest_asst[-1]["content"].replace('**Recommended Engineering Review Notes for HITL Approval:**', '').replace('"', '').strip()
                        st.session_state.hitl_review_notes = text
                        st.toast("Copied AI notes to review form!", icon="✅")
                        st.rerun()

        # ── RIGHT COLUMN: Engineer Decision & Authorization Form ───────
        with col_decision:
            st.markdown("""
            <div style="margin-bottom:6px;">
                <span style="font-family:var(--font-sans); font-weight:700; font-size:1.15rem; color:var(--text-primary);">
                    🔐 Engineer Decision & Authorization
                </span>
            </div>
            <p style="font-family:var(--font-mono); font-size:0.72rem; color:var(--text-muted); margin-bottom:10px;">
                Formal reliability engineering sign-off required to emit SAP PM01 work order and Global 8D report.
            </p>
            """, unsafe_allow_html=True)

            # Diagnostic Summary Card
            st.markdown(f"""
            <div class="glass-card" style="padding:14px 18px; margin-bottom:14px; border-left:3px solid var(--accent);">
                <div style="font-family:var(--font-sans); font-weight:600; font-size:0.85rem; color:var(--text-primary); margin-bottom:6px;">
                    Incident Diagnostic Summary
                </div>
                <table style="width:100%; font-family:var(--font-mono); font-size:0.72rem; color:var(--text-secondary); line-height:1.7;">
                    <tr><td style="color:var(--text-muted); width:130px;">Winning Hypothesis:</td>
                        <td style="color:var(--accent); font-weight:600;">{winning_name} ({confidence_val:.1f}%)</td></tr>
                    <tr><td style="color:var(--text-muted);">Root Cause Asset:</td>
                        <td><code style="color:var(--danger); font-size:0.78rem;">{root_asset_id}</code> Suction Strainer</td></tr>
                    <tr><td style="color:var(--text-muted);">Failure Mechanism:</td>
                        <td style="color:var(--text-primary);">{failure_mech}</td></tr>
                    <tr><td style="color:var(--text-muted);">CMMS Finding:</td>
                        <td style="color:var(--warning);">{cmms_finding}</td></tr>
                </table>
            </div>
            """, unsafe_allow_html=True)

            with st.form("hitl_decision_form"):
                decision_action = st.radio(
                    "Select Engineer Action:",
                    [
                        "✅ Approve — Authorize SAP PM01 Work Order & 8D Report",
                        "🔄 Override — Approve with custom root cause statement",
                        "❌ Reject — Close investigation without work order",
                    ],
                    index=0,
                )

                reviewer_name = st.text_input(
                    "Reviewer Name & Title",
                    "Lead Machinery Reliability Specialist",
                )

                engineer_notes = st.text_area(
                    "Review Notes / Audit Justification",
                    value=st.session_state.hitl_review_notes,
                    height=135,
                    help="You can ask the Copilot on the left to draft or refine these justification notes.",
                )

                custom_override = ""
                if "Override" in decision_action:
                    custom_override = st.text_input(
                        "Custom Root Cause Statement",
                        "Upstream suction strainer biofouling with particulate debris",
                    )

                submitted = st.form_submit_button("✅ Authorize & Resume LangGraph Pipeline", type="primary", use_container_width=True)

                if submitted:
                    action_str = "approve" if "Approve" in decision_action else ("override" if "Override" in decision_action else "reject")
                    decision_payload = {
                        "action": action_str,
                        "reviewer": reviewer_name,
                        "notes": engineer_notes,
                        "override_root_cause": custom_override if action_str == "override" else None,
                    }

                    config = {"configurable": {"thread_id": st.session_state.thread_id}}
                    for event in st.session_state.graph.stream(Command(resume=decision_payload), config=config):
                        pass

                    final_state = st.session_state.graph.get_state(config)
                    st.session_state.final_state = final_state.values
                    st.session_state.paused_state = None
                    st.success(f"Decision '{action_str.upper()}' recorded! Pipeline resumed.")
                    st.rerun()

    elif st.session_state.final_state:
        final_status = st.session_state.final_state.get("pipeline_status", "COMPLETED")
        final_dec = st.session_state.final_state.get("human_review_decision", {})

        st.markdown(f"""
        <div class="glass-card" style="padding:28px; max-width:800px; margin:20px auto; border-left: 4px solid {'var(--accent)' if final_status == 'APPROVED' or final_status == 'COMPLETED' else 'var(--danger)'};">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:16px;">
                <div>
                    <span style="font-size:1.8rem;">{'✅' if final_status in ('APPROVED', 'COMPLETED') else '❌'}</span>
                    <span style="font-family:var(--font-sans); font-weight:700; font-size:1.2rem; color:var(--text-primary); margin-left:8px;">
                        HITL Authorization Completed — Status: {final_status}
                    </span>
                </div>
                <span class="mono" style="font-size:0.75rem; color:var(--text-muted);">
                    Reviewer: {final_dec.get('reviewer', 'Lead Reliability Specialist')}
                </span>
            </div>
            <div style="font-family:var(--font-sans); font-size:0.88rem; color:var(--text-secondary); line-height:1.6; margin-bottom:16px;">
                <b>Recorded Review Notes:</b><br>
                <div style="background:#0D1321; border:1px solid var(--border-subtle); border-radius:8px; padding:12px 16px; margin-top:6px; font-family:var(--font-mono); font-size:0.8rem; color:#E2E8F0;">
                    {final_dec.get('notes', 'No notes provided.')}
                </div>
            </div>
            <div style="text-align:center;">
                <span style="font-family:var(--font-sans); font-size:0.85rem; color:var(--accent);">
                    👉 Navigate to the <b>Deliverables</b> tab to inspect and download the generated Global 8D Report and SAP S/4HANA PM01 Work Order.
                </span>
            </div>
        </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════
# TAB 6: MAINTENANCE DELIVERABLES
# ══════════════════════════════════════════════════════════════════════
with tab_deliverables:
    st.markdown('<div class="section-title">📑 Standardized Industrial Deliverables</div>', unsafe_allow_html=True)

    final_data = st.session_state.final_state or state_vals
    rep_8d = final_data.get("incident_report_8d")
    sap_wo = final_data.get("sap_work_order")

    if rep_8d and sap_wo:
        deliv_tab1, deliv_tab2 = st.tabs(["📋 Global 8D Incident Report", "🛠️ SAP PM01 Work Order"])

        with deliv_tab1:
            incident_id = rep_8d.get("incident_id", "N/A")
            st.markdown(f"""
            <div class="glass-card" style="margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-family:var(--font-sans); font-weight:700; font-size:1.1rem; color:var(--text-primary);">
                            Global 8D Incident Report
                        </span><br>
                        <span class="mono" style="font-size:0.75rem; color:var(--accent);">{incident_id}</span>
                    </div>
                    <span class="mono" style="font-size:0.7rem; color:var(--text-muted);">
                        {rep_8d.get('classification', 'N/A')}
                    </span>
                </div>
            </div>""", unsafe_allow_html=True)

            d1 = rep_8d.get("d1_team", {})
            if d1:
                members_html = "".join(
                    f'<div style="padding:2px 0;"><span style="color:var(--text-muted); display:inline-block; width:120px;">{role.replace("_"," ").title()}</span>'
                    f'<span style="color:var(--text-primary);">{name}</span></div>'
                    for role, name in d1.items()
                )
                st.markdown(f"""
                <div class="section-8d">
                    <div class="section-8d-header">D1 — Investigation Team</div>
                    <div class="section-8d-body">{members_html}</div>
                </div>""", unsafe_allow_html=True)

            d2 = rep_8d.get("d2_problem_description", {})
            if d2:
                d2_html = "".join(
                    f'<div style="padding:3px 0;"><span style="color:var(--accent); font-weight:500;">{k.upper()}: </span>'
                    f'<span>{v}</span></div>'
                    for k, v in d2.items()
                )
                st.markdown(f"""
                <div class="section-8d">
                    <div class="section-8d-header">D2 — Problem Description</div>
                    <div class="section-8d-body">{d2_html}</div>
                </div>""", unsafe_allow_html=True)

            d3 = rep_8d.get("d3_interim_containment_actions", [])
            if d3:
                d3_html = "".join(f'<div style="padding:3px 0;">• {item}</div>' for item in d3)
                st.markdown(f"""
                <div class="section-8d">
                    <div class="section-8d-header">D3 — Interim Containment Actions</div>
                    <div class="section-8d-body">{d3_html}</div>
                </div>""", unsafe_allow_html=True)

            d4 = rep_8d.get("d4_root_cause_analysis", {})
            if d4:
                st.markdown(f"""
                <div class="section-8d">
                    <div class="section-8d-header">D4 — Root Cause Analysis</div>
                    <div class="section-8d-body">
                        <div style="padding:3px 0;"><span style="color:var(--accent);">ISO 14224 Code:</span> {d4.get('iso_14224_code', 'N/A')}</div>
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Failure Mechanism:</span> {d4.get('failure_mechanism', 'N/A')}</div>
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Root Cause Asset:</span> <code style="color:var(--danger);">{d4.get('root_cause_asset', 'N/A')}</code></div>
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Statement:</span> {d4.get('root_cause_statement', 'N/A')}</div>
                    </div>
                </div>""", unsafe_allow_html=True)

            d5 = rep_8d.get("d5_permanent_corrective_actions", [])
            if d5:
                d5_html = "".join(f'<div style="padding:3px 0;">• {item}</div>' for item in d5)
                st.markdown(f"""
                <div class="section-8d">
                    <div class="section-8d-header">D5 — Permanent Corrective Actions</div>
                    <div class="section-8d-body">{d5_html}</div>
                </div>""", unsafe_allow_html=True)

            d6 = rep_8d.get("d6_implementation_and_validation", {})
            if d6:
                st.markdown(f"""
                <div class="section-8d">
                    <div class="section-8d-header">D6 — Implementation & Validation</div>
                    <div class="section-8d-body">
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Method:</span> {d6.get('validation_method', 'N/A')}</div>
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Acceptance:</span> {d6.get('acceptance_criteria', 'N/A')}</div>
                    </div>
                </div>""", unsafe_allow_html=True)

            d7 = rep_8d.get("d7_systemic_prevention", [])
            if d7:
                d7_html = "".join(f'<div style="padding:3px 0;">• {item}</div>' for item in d7)
                st.markdown(f"""
                <div class="section-8d">
                    <div class="section-8d-header">D7 — Systemic Prevention</div>
                    <div class="section-8d-body">{d7_html}</div>
                </div>""", unsafe_allow_html=True)

            d8 = rep_8d.get("d8_sign_off", {})
            if d8:
                st.markdown(f"""
                <div class="section-8d">
                    <div class="section-8d-header">D8 — Sign-Off</div>
                    <div class="section-8d-body">
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Approval:</span> {d8.get('reliability_manager_approval', 'N/A')}</div>
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Reviewed By:</span> {d8.get('reviewed_by', 'N/A')}</div>
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Notes:</span> {d8.get('review_notes', 'N/A')}</div>
                    </div>
                </div>""", unsafe_allow_html=True)

            st.markdown("")
            st.download_button(
                "📥 Download 8D Report (JSON)",
                data=json.dumps(rep_8d, indent=2),
                file_name=f"8D_Report_{incident_id}.json",
                mime="application/json",
                use_container_width=True,
            )

        with deliv_tab2:
            order_num = sap_wo.get("order_number", "N/A")
            st.markdown(f"""
            <div class="glass-card" style="margin-bottom:16px;">
                <div style="display:flex; justify-content:space-between; align-items:center;">
                    <div>
                        <span style="font-family:var(--font-sans); font-weight:700; font-size:1.1rem; color:var(--text-primary);">
                            SAP S/4HANA PM01 Corrective Work Order
                        </span><br>
                        <span class="mono" style="font-size:0.75rem; color:var(--accent);">#{order_num}</span>
                    </div>
                    <span class="mono" style="font-size:0.7rem; color:var(--danger); font-weight:600;">
                        Priority: {sap_wo.get('priority', 'N/A')}
                    </span>
                </div>
            </div>""", unsafe_allow_html=True)

            col_wo1, col_wo2 = st.columns(2)
            with col_wo1:
                st.markdown(f"""
                <div class="section-8d">
                    <div class="section-8d-header">Order Details</div>
                    <div class="section-8d-body">
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Functional Location:</span> <code>{sap_wo.get('functional_location', 'N/A')}</code></div>
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Planning Plant:</span> {sap_wo.get('planning_plant', 'N/A')}</div>
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Failure Mode:</span> {sap_wo.get('failure_mode', 'N/A')}</div>
                    </div>
                </div>""", unsafe_allow_html=True)
            with col_wo2:
                st.markdown(f"""
                <div class="section-8d">
                    <div class="section-8d-header">Resource Estimate</div>
                    <div class="section-8d-body">
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Estimated Hours:</span> <span style="font-weight:600; color:var(--text-primary);">{sap_wo.get('total_estimated_hours', 'N/A')} hours</span></div>
                        <div style="padding:3px 0;"><span style="color:var(--accent);">Order Type:</span> PM01 Corrective</div>
                    </div>
                </div>""", unsafe_allow_html=True)

            ops = sap_wo.get("operations", [])
            if ops:
                st.markdown("""
                <div class="section-8d" style="margin-top:12px;">
                    <div class="section-8d-header">Operations Task List</div>
                </div>""", unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(ops), use_container_width=True, hide_index=True)

            mats = sap_wo.get("materials_required", [])
            if mats:
                st.markdown("""
                <div class="section-8d" style="margin-top:12px;">
                    <div class="section-8d-header">Bill of Materials (BOM)</div>
                </div>""", unsafe_allow_html=True)
                st.dataframe(pd.DataFrame(mats), use_container_width=True, hide_index=True)

            st.markdown("")
            st.download_button(
                "📥 Download SAP PM01 Order (JSON)",
                data=json.dumps(sap_wo, indent=2),
                file_name=f"SAP_PM01_{order_num}.json",
                mime="application/json",
                use_container_width=True,
            )
    else:
        st.markdown("""
        <div class="glass-card" style="text-align:center; padding:48px;">
            <span style="font-size:2.5rem;">📑</span><br><br>
            <span style="font-family:var(--font-sans); font-weight:600; font-size:1rem; color:var(--text-primary);">Deliverables Pending</span><br>
            <span style="font-family:var(--font-sans); font-size:0.85rem; color:var(--text-muted);">
                8D Report and SAP PM01 Work Order will appear here after the fault investigation is reviewed and approved via the HITL Gate.
            </span>
        </div>""", unsafe_allow_html=True)
