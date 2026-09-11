# Industrial Root Cause Analysis (RCA) System Prototype

Production-grade industrial RCA system built with **Python 3.11+**, **LangGraph**, and **DeepSeek AI**. Grounded in **ISA-95** asset hierarchies, **ISO 14224 / FMEA** failure taxonomies, and **ISO 10816 Class III** vibration standards.

---

## ⚡ Quickstart

### 1. Launch Interactive Web GUI & REST API Daemon
```bash
streamlit run app.py
```
> - **Web GUI Dashboard:** Open [http://localhost:8501](http://localhost:8501)
> - **HIL Ingestion API (FastAPI):** Open [http://localhost:8000/docs](http://localhost:8000/docs)
*(The FastAPI server automatically runs in a background thread on port 8000 when starting Streamlit).*

### 2. Standalone Ingestion API Execution (Optional)
```bash
uvicorn app:api_app --host 0.0.0.0 --port 8000
```

### 3. Run Interactive Terminal CLI (Rich TUI)
```bash
# Using DeepSeek-V3
python main.py --auto-approve --use-deepseek --deepseek-model deepseek-chat

# Using DeepSeek-R1 (with Chain-of-Thought reasoning display)
python main.py --auto-approve --use-deepseek --deepseek-model deepseek-reasoner
```

### 4. Run Automated Test Suite
```bash
python -m pytest industrial_rca/tests -v
```

---

## 🏭 Hardware-in-the-Loop (HIL) Test Bench Integration Guide

This platform supports real physical industrial hardware (HMI touch screen, WECON VM Series VFD, 3-phase induction motor, and V-Box IoT Gateway) streaming live telemetry into the LangGraph root cause engine.

### 1. End-to-End System Architecture

```
[HMI Touch Screen / V-Box] 
      │ (Touch Slider / Start-Stop Commands over RS-485 Modbus RTU)
      ▼
[WECON VM Series VFD] ──────(3-Phase PWM)─────> [Induction Motor]
      │
      │ (RS-485 Port S+, S- / Modbus Slave ID 1, 9600 8-N-1)
      ▼
[V-Box Edge Gateway]
      │ (MQTT JSON stream: factory/bench01/vfd/telemetry)
      ▼
[Mosquitto MQTT Broker] (Port 1883)
      │
      ▼
[Node-RED Orchestrator] (Port 1880)
      ├── (Continuous 1 Hz stream) ──> [InfluxDB 2.7] (Port 8086, Bucket: telemetry)
      └── (Trip condition: Reg 700BH > 0)
                  │
                  ▼ (Fetches 60s pre-fault window from InfluxDB)
      [HTTP POST to http://host.docker.internal:8000/api/v1/telemetry/incident]
                  │
                  ▼
      [IndustrialRCA FastAPI Endpoint: app.py]
                  │
                  ▼
      [LangGraph Graph Engine: workflow.py]
        ├── telemetry_analytics.py (Voltage spikes, decel trends)
        ├── topology_tracer.py (Asset linking via asset_topology.json)
        ├── oem_manuals.py (WECON VM Err codes: Err02, Err03, Err06, Err11)
        └── deepseek_client.py (Root cause deduction & remediation)
```

---

### 2. Edge Transport Middleware Deployment (`docker-compose.infra.yml`)

The infrastructure stack runs Eclipse Mosquitto, InfluxDB 2.7, and Node-RED in Docker:

```bash
# Start edge transport middleware
docker compose -f docker-compose.infra.yml up -d

# Check container status
docker compose -f docker-compose.infra.yml ps
```

- **Mosquitto MQTT Broker:** `mqtt://<HOST_IP>:1883` (Anonymous access enabled)
- **InfluxDB 2.7:** `http://<HOST_IP>:8086` (Org: `factory`, Bucket: `telemetry`, Token: `rca_super_secret_token_123`)
- **Node-RED Web Flow Editor:** `http://<HOST_IP>:1880`

To import the pre-configured ingestion pipeline into Node-RED:
1. Open `http://localhost:1880`.
2. Click the hamburger menu $\to$ **Import** $\to$ select [`infra/nodered/flows.json`](file:///c:/HMI/RCA/infra/nodered/flows.json).
3. Click **Deploy**.

---

### 3. WECON VM Series VFD Keypad Parameter Configuration

Configure these parameters on the VFD front keypad:

| Parameter | Function Name | Required Setting | Description |
| :--- | :--- | :--- | :--- |
| **`F9.00`** | Communication Station / Slave ID | **`1`** | Modbus Slave ID = 1 |
| **`F9.01`** | Modbus Baud Rate | **`3`** | `9600 bps` |
| **`F9.02`** | Modbus Data Format | **`0`** | `8-N-1` (8 data bits, no parity, 1 stop bit) |
| **`F0.02`** | Run Command Source | **`2`** | RS-485 Communication control |
| **`F0.03`** | Frequency Reference Source | **`2`** | RS-485 Communication setting |
| **`F0.17`** | Acceleration Time | **`5.0s`** | Normal acceleration ramp |
| **`F0.18`** | Deceleration Time | **`5.0s`** (Normal) | Baseline ramp. *(Set to `0.2s` for `Err06` trip test)* |
| **`F2.03`** | Motor Rated Current | Motor FLA | True motor nameplate current. *(Set to `0.3A` for `Err11` trip test)* |

---

### 4. WECON VM Modbus Register Mapping Table

| Register (Hex) | Register (Dec) | Modbus Function | Data Type | Engineering Unit | Scale Factor | Access | Description |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **`2000H`** | `8192` (`4x8192`) | `0x06` / `0x10` | 16-bit Int | Enum | `1` | Write | Control Command (`1`=FWD Run, `2`=REV, `5`=Decel Stop, `6`=Coast Stop, `7`=Fault Reset) |
| **`2001H`** | `8193` (`4x8193`) | `0x06` / `0x10` | 16-bit Int | Hz | `Value / 100` | Write | Target Frequency Command ($0 - 10000 = 0.00 - 100.00\text{ Hz}$) |
| **`3000H`** | `12288` (`4x12288`) | `0x03` | 16-bit Int | Hz | `Value / 100` | Read | Output Operating Frequency (`f_out`) |
| **`3001H`** | `12289` (`4x12289`) | `0x03` | 16-bit Int | Hz | `Value / 100` | Read | Commanded Target Frequency (`f_target`) |
| **`3002H`** | `12290` (`4x12290`) | `0x03` | 16-bit Int | A | `Value / 100` | Read | Output Motor Line Current (`current`) |
| **`3003H`** | `12291` (`4x12291`) | `0x03` | 16-bit Int | V | `Value * 1` | Read | Output Voltage (`v_out`) |
| **`3004H`** | `12292` (`4x12292`) | `0x03` | 16-bit Int | V | `Value / 10` | Read | DC Bus Voltage (`v_dc`) |
| **`700BH`** | `28683` (`4x28683`) | `0x03` | 16-bit Int | Code | `1` | Read | Active Trip Code (`0`=Normal, `2`=Err02, `3`=Err03, `6`=Err06, `11`=Err11) |

---

### 5. HMI Screen Widget Addressing (PIStudio / Weinview / Modbus HMI)

Configure your HMI screen controls using the following mappings:

| HMI Widget Type | Display Label | Modbus Register Address (Hex) | Modbus Address (Dec) | Data Format | Multiplier | Read / Write |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Numeric Input / Slider** | **Target Frequency Setpoint** | **`2001H`** | **`4x8193`** (`8193`) | 16-bit Unsigned | `0.01` ($5000 = 50.00\text{ Hz}$) | **Read / Write** |
| **Momentary / Toggle Button** | **START (Forward Run)** | **`2000H`** | **`4x8192`** (`8192`) | 16-bit Int | Constant value **`1`** | **Write Only** |
| **Momentary / Toggle Button** | **STOP (Decel to Stop)** | **`2000H`** | **`4x8192`** (`8192`) | 16-bit Int | Constant value **`5`** | **Write Only** |
| **Momentary Button** | **EMERGENCY COAST STOP** | **`2000H`** | **`4x8192`** (`8192`) | 16-bit Int | Constant value **`6`** | **Write Only** |
| **Momentary Button** | **FAULT RESET** | **`2000H`** | **`4x8192`** (`8192`) | 16-bit Int | Constant value **`7`** | **Write Only** |
| **Meter / Numeric Display** | **Operating Frequency** | **`3000H`** | **`4x12288`** (`12288`) | 16-bit Unsigned | `0.01` ($0 - 50.00\text{ Hz}$) | **Read Only** |
| **Numeric Display** | **Commanded Frequency** | **`3001H`** | **`4x12289`** (`12289`) | 16-bit Unsigned | `0.01` ($0 - 50.00\text{ Hz}$) | **Read Only** |
| **Meter / Numeric Display** | **Motor Line Current** | **`3002H`** | **`4x12290`** (`12290`) | 16-bit Unsigned | `0.01` ($142 = 1.42\text{ A}$) | **Read Only** |
| **Numeric Display** | **Output Voltage** | **`3003H`** | **`4x12291`** (`12291`) | 16-bit Unsigned | `1` ($0 - 380\text{ V}$) | **Read Only** |
| **Meter / Numeric Display** | **DC Bus Voltage** | **`3004H`** | **`4x12292`** (`12292`) | 16-bit Unsigned | `0.1` ($3124 = 312.4\text{ V}$) | **Read Only** |
| **Alarm / Text Display** | **Active Fault Code** | **`700BH`** | **`4x28683`** (`28683`) | 16-bit Unsigned | `1` (`0`=Normal, `6`=Err06, `11`=Err11) | **Read Only** |

---

### 6. V-Box Edge Gateway MQTT Publisher Settings

In the V-Box / HMI cloud configurator:
- **Serial Connection:** RS-485 to VFD `S+`, `S-`, Baud `9600`, `8-N-1`, Slave ID `1`.
- **Polling Interval:** `1000 ms` (1 Hz).
- **MQTT Server:** `<HOST_IP>` (Port `1883`, anonymous).
- **Publish Topic:** `factory/bench01/vfd/telemetry`.
- **Payload Schema:**
  ```json
  {
    "f_out": 45.00,
    "f_target": 45.00,
    "current": 1.42,
    "v_out": 220,
    "v_dc": 311.5,
    "fault_code": 0
  }
  ```

---

### 7. Incident Reporting Destination (Node-RED ➔ IndustrialRCA)

When a trip is detected (`fault_code > 0`), Node-RED pulls the 60-second pre-fault buffer from InfluxDB and sends an HTTP POST:

- **Target URL (from Docker):** `http://host.docker.internal:8000/api/v1/telemetry/incident`
- **Target URL (from external LAN):** `http://<HOST_IP>:8000/api/v1/telemetry/incident`
- **HTTP Method:** `POST`
- **Headers:** `Content-Type: application/json`
- **Payload Schema:**
  ```json
  {
    "asset_id": "VFD_VM_01",
    "fault_code": 6,
    "fault_description": "Deceleration Overvoltage (Err06) - DC link regeneration surge",
    "incident_id": "INC-HIL-1726041200",
    "pre_fault_telemetry": [
      {
        "timestamp": 1726041140,
        "f_out": 45.00,
        "f_target": 45.00,
        "current": 1.42,
        "v_out": 220,
        "v_dc": 311.5,
        "fault_code": 0
      },
      {
        "timestamp": 1726041200,
        "f_out": 12.50,
        "f_target": 0.00,
        "current": 3.85,
        "v_out": 180,
        "v_dc": 745.2,
        "fault_code": 6
      }
    ]
  }
  ```

---

### 8. Safe Software Fault Injection Recipes

#### 1. Deceleration Overvoltage (`Err06`)
1. On the VFD keypad, set parameter **`F0.18 = 0.2`** (0.2s deceleration ramp). Verify that no dynamic braking resistor is connected to terminals `P+` and `PB`.
2. On the HMI screen, set target frequency to **`45.00 Hz`** and tap **START**.
3. Once running at steady speed, drag the frequency slider to **`0.00 Hz`** or tap **STOP**.
4. The motor regenerates kinetic energy into the DC bus; DC voltage (`3004H`) surges past $700\text{ V DC}$ and trips **`Err06`** (`fault_code = 6`).
5. V-Box publishes `fault_code: 6` $\to$ Node-RED catches the trip $\to$ queries 60s buffer $\to$ POSTs incident to IndustrialRCA.

#### 2. Motor Thermal Overload (`Err11`)
1. On the VFD keypad, set parameter **`F2.03 = 0.3`** (lowered below idle motor current, e.g. 0.3A).
2. On the HMI screen, set target frequency to **`50.00 Hz`** and tap **START**.
3. With the motor drawing ~1.0A–1.5A, the VFD's internal thermal accumulator ($I^2t$) charges rapidly.
4. After ~20–60 seconds, the VFD trips on **`Err11`** (`fault_code = 11`).
