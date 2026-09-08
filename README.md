# Industrial Root Cause Analysis (RCA) System Prototype

Production-grade industrial RCA system built with **Python 3.11+** and **LangGraph**.

- Please refer to [`industrial_rca/README.md`](file:///home/marsel/.gemini/antigravity/worktrees/RCA/build_industrial_rca_system/industrial_rca/README.md) for full architectural documentation, ISA-95 topology details, ISO 14224 failure modes, and case study specifications.

## Quickstart

### 1. Launch Interactive Web GUI Dashboard
```bash
streamlit run app.py
```
> Open your browser at **`http://localhost:8501`** to interact with live telemetry trends, 20 kHz acoustic FFT charts, parallel hypothesis matrices, 5-Whys causal traces, DeepSeek-R1 reasoning, and the one-click Human-in-the-Loop review gate.

### 2. Run Interactive Terminal CLI (Rich TUI)
```bash
python3 main.py
```
Or with DeepSeek AI enabled:
```bash
# Using DeepSeek-V3
python3 main.py --auto-approve --use-deepseek --deepseek-model deepseek-chat

# Using DeepSeek-R1 (with Chain-of-Thought reasoning display)
python3 main.py --auto-approve --use-deepseek --deepseek-model deepseek-reasoner
```

### 3. Verify DeepSeek API Integration
```bash
python3 test_deepseek.py
```

### 4. Run Pytest Suite (13/13 Passing)
```bash
python3 -m pytest industrial_rca/tests -v
```

