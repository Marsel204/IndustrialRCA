"""
Simulation Test Script for Hardware-in-the-Loop (HIL) Ingestion.
Enables instant zero-hardware testing of the IndustrialRCA API endpoint,
simulating a real WECON VM VFD Deceleration Overvoltage (Err06) incident.
"""

import time
import json
import urllib.request
import urllib.error

API_URL = "http://localhost:8000/api/v1/telemetry/incident"
HEALTH_URL = "http://localhost:8000/api/v1/telemetry/health"

def run_simulation_test():
    print("=" * 70)
    print("🚀 IndustrialRCA HIL Middleware Ingestion Simulation Test")
    print("=" * 70)

    # 1. Health check
    print("\n[1/3] Checking FastAPI middleware health...")
    try:
        with urllib.request.urlopen(HEALTH_URL, timeout=3) as resp:
            data = json.loads(resp.read().decode())
            print(f"  ✓ Health Status: {data.get('status')} ({data.get('service')})")
    except Exception as e:
        print(f"  ❌ Health check failed: {e}")
        print("  💡 Tip: Ensure app.py is running via 'streamlit run app.py' or 'uvicorn app:api_app --port 8000'.")
        return False

    # 2. Build 60-second simulated telemetry buffer
    print("\n[2/3] Generating 60-second simulated WECON VM VFD Decel Overvoltage (Err06) buffer...")
    now = int(time.time())
    telemetry = []

    # 0s - 50s: Normal operating state (45 Hz, nominal 312V DC)
    for t in range(50, 5, -1):
        telemetry.append({
            "timestamp": now - t,
            "f_out": 45.0,
            "f_target": 45.0,
            "current": 1.42,
            "v_out": 220.0,
            "v_dc": 312.4,
            "fault_code": 0
        })

    # 50s - 54s: Operator commands rapid deceleration to 0 Hz (F0.18 = 0.2s, no brake resistor)
    # DC bus surges from 312V up to 748V
    decel_vdc = [360.0, 480.0, 620.0, 695.0, 748.5]
    decel_fout = [36.0, 24.0, 12.0, 4.0, 0.0]
    for i, (v, f) in enumerate(zip(decel_vdc, decel_fout)):
        t_offset = 5 - i
        telemetry.append({
            "timestamp": now - t_offset,
            "f_out": f,
            "f_target": 0.0,
            "current": 3.85,
            "v_out": 160.0,
            "v_dc": v,
            "fault_code": 0
        })

    # 55s: VFD trips Err06 (DC bus > 700V)
    telemetry.append({
        "timestamp": now,
        "f_out": 0.0,
        "f_target": 0.0,
        "current": 0.0,
        "v_out": 0.0,
        "v_dc": 748.5,
        "fault_code": 6
    })

    incident_payload = {
        "asset_id": "VFD_VM_01",
        "fault_code": 6,
        "fault_description": "Deceleration Overvoltage (Err06) - DC link regeneration surge without brake resistor",
        "incident_id": f"SIM-HIL-{now}",
        "pre_fault_telemetry": telemetry
    }
    print(f"  ✓ Buffer created with {len(telemetry)} points. Trip: Err06 (DC bus: {telemetry[-1]['v_dc']}V).")

    # 3. Post incident to FastAPI endpoint
    print(f"\n[3/3] POSTing incident payload to {API_URL}...")
    req = urllib.request.Request(
        API_URL,
        data=json.dumps(incident_payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            resp_data = json.loads(resp.read().decode())
            print("  ✓ HTTP Response Code: 200 OK")
            print(f"  ✓ Ingestion Status:   {resp_data.get('status')}")
            print(f"  ✓ Incident ID:        {resp_data.get('incident_id')}")
            print(f"  ✓ Asset ID:           {resp_data.get('asset_id')}")
            print(f"  ✓ Fault Code:         {resp_data.get('fault_code')} ({resp_data.get('fault_description')})")
            print(f"  ✓ Points Buffered:    {resp_data.get('telemetry_points_buffered')}")
            print(f"  ✓ RCA Pipeline:       {resp_data.get('rca_pipeline')}")
    except urllib.error.HTTPError as e:
        print(f"  ❌ HTTP Error {e.code}: {e.read().decode()}")
        return False
    except Exception as e:
        print(f"  ❌ Connection Error: {e}")
        return False

    print("\n" + "=" * 70)
    print("✅ TEST PASSED: Ingestion pipeline received and dispatched the incident!")
    print("👉 Check the Streamlit dashboard at http://localhost:8501 to inspect the live incident.")
    print("=" * 70)
    return True

if __name__ == "__main__":
    run_simulation_test()
