"""
Local Lightweight MQTT Broker for Industrial RCA Hardware-in-the-Loop (HIL).
Provides zero-configuration local MQTT broker running on 0.0.0.0:1883 using amqtt.
Enables instant local connectivity for Node-RED edge gateway, Wecon HMI, and simulators.
"""

import sys
import time
import json
import asyncio
import logging
import urllib.request
from amqtt.broker import Broker

# Configure clean logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("mqtt_broker")

BROKER_CONFIG = {
    "listeners": {
        "default": {
            "type": "tcp",
            "bind": "0.0.0.0:1883",
            "max_connections": 50,
        },
        "port_8883": {
            "type": "tcp",
            "bind": "0.0.0.0:8883",
            "max_connections": 50,
        },
    },
    "sys_interval": 10,
    "auth": {
        "allow-anonymous": True,
        "plugins": ["auth_anonymous"],
    },
    "topic-check": {
        "enabled": False,
    },
}


# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# Patch Broker._broadcast_message to intercept and log all incoming packets
_orig_broadcast = Broker._broadcast_message


async def _custom_broadcast(self, session, topic, data, force_qos=None):
    cid = getattr(session, "client_id", "local") if session else "broker"
    now_str = time.strftime("%H:%M:%S")
    raw_text = ""
    try:
        raw_text = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else str(data)
    except Exception:
        raw_text = repr(data)

    print(f"\n[MQTT-LIVE] [{now_str}] Client: {cid} | Topic: {topic}", flush=True)
    print(f"   Payload: {raw_text}", flush=True)

    # Forward to FastAPI live feed
    try:
        payload_dict = None
        trimmed = raw_text.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            parsed = json.loads(trimmed)
            if isinstance(parsed, dict):
                payload_dict = parsed
        else:
            low = trimmed.lower()
            if low in ("0", "reset", "clear", "ack", "normal"):
                payload_dict = {"reset": True, "fault_code": 0, "topic": topic}
            elif low in ("2", "02", "err02", "error02"):
                payload_dict = {"fault_code": 2, "fault_description": "Overcurrent during deceleration (Err02)", "topic": topic}
            elif low in ("6", "06", "err06", "error06"):
                payload_dict = {"fault_code": 6, "fault_description": "Overvoltage during operation / Overfrequency (Err06)", "topic": topic}
            elif low in ("3", "03", "err03"):
                payload_dict = {"fault_code": 3, "fault_description": "Overcurrent during constant speed (Err03)", "topic": topic}
            elif low in ("11", "err11"):
                payload_dict = {"fault_code": 11, "fault_description": "Motor Overload (Err11)", "topic": topic}
            elif "reset" in topic.lower() or "clear" in topic.lower():
                payload_dict = {"reset": True, "fault_code": 0, "topic": topic}
            elif "error" in topic.lower() or "fault" in topic.lower():
                try:
                    code_val = int(float(trimmed))
                    if code_val == 0:
                        payload_dict = {"reset": True, "fault_code": 0, "topic": topic}
                    else:
                        payload_dict = {"fault_code": code_val, "topic": topic}
                except ValueError:
                    payload_dict = {"fault_description": trimmed, "fault_code": 2 if "02" in trimmed else 6, "topic": topic}
            elif "trigger" in topic.lower() or "d_var" in topic.lower():
                try:
                    code_val = int(float(trimmed))
                    payload_dict = {"d_trigger": code_val, "fault_code": code_val, "topic": topic}
                except ValueError:
                    payload_dict = {"d_trigger": trimmed, "topic": topic}
            else:
                try:
                    val = float(trimmed)
                    payload_dict = {"value": val, "topic": topic}
                except ValueError:
                    payload_dict = {"raw": trimmed, "topic": topic}

        if payload_dict is not None:
            payload_dict["_mqtt_topic"] = topic
            import urllib.request
            req = urllib.request.Request(
                "http://127.0.0.1:8000/api/v1/telemetry/live/feed",
                data=json.dumps(payload_dict).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=0.5):
                pass
    except Exception:
        pass

    return await _orig_broadcast(self, session, topic, data, force_qos=force_qos)


Broker._broadcast_message = _custom_broadcast


async def start_broker():
    broker = Broker(BROKER_CONFIG)
    print("=" * 70, flush=True)
    print("Industrial RCA Local MQTT Broker (amqtt)", flush=True)
    print("=" * 70, flush=True)
    print("  Host / Interface: 0.0.0.0 (All interfaces)", flush=True)
    print("  Ports:            1883 (Standard) & 8883 (HMI / PIStudio)", flush=True)
    print("  Anonymous Auth:   Enabled", flush=True)
    print("  Target Topics:    factory/bench01/vfd/#", flush=True)
    print("  Node-RED Target:  mqtt://localhost:1883 or mqtt://localhost:8883", flush=True)
    print("=" * 70, flush=True)
    print("Broker starting... Press Ctrl+C to stop.", flush=True)

    await broker.start()
    try:
        while True:
            await asyncio.sleep(1)
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        print("\nShutting down MQTT broker...", flush=True)
        await broker.shutdown()
        print("MQTT broker stopped.", flush=True)


def main():
    try:
        asyncio.run(start_broker())
    except KeyboardInterrupt:
        print("\nBroker terminated by user.")
        sys.exit(0)


if __name__ == "__main__":
    main()
