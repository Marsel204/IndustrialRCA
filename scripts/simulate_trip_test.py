"""
Simulation test:
1. Feeds 40 Hz nominal telemetry for 6 seconds.
2. Ramps frequency from 40 Hz to 50 Hz with corresponding RPM and DC bus voltage surge.
3. Triggers Err06 trip (overfrequency deceleration overvoltage).
4. Monitors backend events, LLM execution status, and SSE stream.
"""

import sys
import os
import time
import json
import urllib.request

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FEED_URL = "http://127.0.0.1:8000/api/v1/telemetry/live/feed"
HEALTH_URL = "http://127.0.0.1:8000/api/v1/telemetry/health"
LATEST_INC_URL = "http://127.0.0.1:8000/api/v1/telemetry/latest_incident"

def send_metric(metric: dict):
    req = urllib.request.Request(
        FEED_URL,
        data=json.dumps(metric).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    with urllib.request.urlopen(req, timeout=2.0) as resp:
        return json.loads(resp.read().decode())

def run_test():
    print("=" * 70)
    print(" 1. Initializing Simulation Test: 40 Hz -> 50 Hz -> Err06")
    print("=" * 70)

    # 1. First reset any prior incident
    print("\n[Step 0] Resetting incident state...")
    try:
        reset_req = urllib.request.Request("http://127.0.0.1:8000/api/v1/telemetry/incident/clear", method="POST")
        with urllib.request.urlopen(reset_req, timeout=2.0) as r:
            print("  Reset response:", r.read().decode())
    except Exception as e:
        print("  Reset failed (ignoring):", e)

    # 2. Feed 40 Hz nominal for 6 seconds
    print("\n[Step 1] Simulating 40 Hz nominal operation for 6 seconds...")
    now = time.time()
    for sec in range(1, 7):
        t = now + sec
        metric = {
            "timestamp": t,
            "asset_id": "VFD_VM_01",
            "f_out": 40.0,
            "f_target": 40.0,
            "v_dc": 182.0,
            "v_out": 220.0,
            "current": 1.15,
            "rpm": 1199.0,
            "fault_code": 0,
            "status": "RUNNING"
        }
        res = send_metric(metric)
        print(f"  Sec {sec}/6: f_out=40.0 Hz | v_dc=182.0 V | rpm=1199.0 | Status: RUNNING (TSDB buffered: {res.get('tsdb_buffered')})")
        time.sleep(1.0)

    # 3. Ramp to 50 Hz (50K) over 3 seconds
    print("\n[Step 2] Ramping frequency to 50 Hz (exceeding 40 Hz ceiling toward 50 Hz)...")
    ramp_steps = [
        {"f_out": 44.0, "rpm": 1315.0, "v_dc": 188.0, "current": 1.35},
        {"f_out": 48.0, "rpm": 1435.0, "v_dc": 194.5, "current": 1.65},
    ]
    for i, step in enumerate(ramp_steps, start=1):
        t = time.time()
        metric = {
            "timestamp": t,
            "asset_id": "VFD_VM_01",
            "f_out": step["f_out"],
            "f_target": 50.0,
            "v_dc": step["v_dc"],
            "v_out": 220.0,
            "current": step["current"],
            "rpm": step["rpm"],
            "fault_code": 0,
            "status": "RUNNING"
        }
        res = send_metric(metric)
        print(f"  Ramp {i}: f_out={step['f_out']} Hz | v_dc={step['v_dc']} V | rpm={step['rpm']} | Status: RUNNING")
        time.sleep(1.0)

    # 4. Breaching ceiling at 50 Hz -> DC bus voltage surges to 202.5 V (> 195V trip limit) -> Err06 Trip!
    print("\n[Step 3] Output reaches 50.0 Hz! DC Bus escalates to 202.5 V (> 195.0 V limit) -> TRIGGERING Err06...")
    t = time.time()
    trip_metric = {
        "timestamp": t,
        "asset_id": "VFD_VM_01",
        "f_out": 50.0,
        "f_target": 50.0,
        "v_dc": 202.5,
        "v_out": 220.0,
        "current": 1.95,
        "rpm": 1495.0,
        "fault_code": 6,
        "fault_description": "Overfrequency Deceleration Overvoltage (Err06)",
        "status": "TRIPPED"
    }
    res_trip = send_metric(trip_metric)
    print("  --> Ingest response:", res_trip)

    # 5. Monitor LLM and pipeline status
    print("\n[Step 4] Monitoring LLM & LangGraph pipeline status on backend...")
    for i in range(10):
        time.sleep(1.0)
        try:
            with urllib.request.urlopen(LATEST_INC_URL, timeout=2.0) as r:
                inc_info = json.loads(r.read().decode())
                status = inc_info.get("pipeline_status")
                has_inc = inc_info.get("has_incident")
                print(f"  T+{i+1}s: Pipeline Status: '{status}' (has_incident: {has_inc})")
                if status == "ANALYSIS_COMPLETE":
                    print("\n  [SUCCESS] LLM & RCA Pipeline completed successfully!")
                    res_val = inc_info.get("graph_result", {})
                    winner = res_val.get("winning_hypothesis", {}).get("hypothesis_id")
                    print(f"  Winning Hypothesis: {winner}")
                    print(f"  Root Cause Asset:   {res_val.get('root_cause_asset')}")
                    print(f"  5-Whys Causal Tree: {len(res_val.get('causal_chain_5_whys', []))} steps generated")
                    break
        except Exception as e:
            print(f"  Error polling status: {e}")

if __name__ == "__main__":
    run_test()
