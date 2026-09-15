"""
Real-Time MQTT Telemetry Monitor.
Subscribes to MQTT telemetry topics published by Node-RED, InfluxDB bridge, or Wecon HMI.
Prints decoded telemetry packets and alerts in real-time.
"""

import sys
import json
import time
import asyncio
from amqtt.client import MQTTClient, ClientError, ConnectError
from amqtt.mqtt.constants import QOS_1

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BROKER_URI = "mqtt://127.0.0.1:1883/"
TOPIC_FILTER = "factory/#"


async def monitor():
    print("=" * 75)
    print("Industrial RCA Real-Time MQTT Telemetry Monitor")
    print("=" * 75)
    print(f"  Broker URI:    {BROKER_URI}")
    print(f"  Topic Filter:  {TOPIC_FILTER}")
    print("=" * 75)
    print("Connecting to broker... (Ensure broker is running on port 1883)")

    client = MQTTClient()
    try:
        await client.connect(BROKER_URI)
        print("  ✓ Connected successfully!")
        await client.subscribe([(TOPIC_FILTER, QOS_1)])
        print(f"  ✓ Subscribed to '{TOPIC_FILTER}'")
        print("-" * 75)
        print(f"{'TIMESTAMP':<12} | {'TOPIC':<30} | {'PAYLOAD SUMMARY'}")
        print("-" * 75)

        packet_count = 0
        while True:
            message = await client.deliver_message()
            packet = message.publish_packet
            topic = packet.variable_header.topic_name
            raw_data = packet.payload.data

            packet_count += 1
            now_str = time.strftime("%H:%M:%S")

            try:
                text = raw_data.decode("utf-8")
                parsed = json.loads(text)
                # Formatted summary for VFD packets
                f_out = parsed.get("f_out", parsed.get("frequency"))
                v_dc = parsed.get("v_dc", parsed.get("bus_voltage"))
                current = parsed.get("current")
                fault = parsed.get("fault_code", parsed.get("fault"))

                summary = ""
                if f_out is not None or v_dc is not None:
                    summary = f"f_out: {f_out}Hz | v_dc: {v_dc}V | I: {current}A | Trip: {fault}"
                    if fault and int(fault) > 0:
                        summary += f" 🚨 [TRIP Err0{fault}]"
                else:
                    summary = text[:50] + ("..." if len(text) > 50 else "")

                print(f"[{now_str}] (#{packet_count:04d}) | {topic:<30} | {summary}")
            except Exception:
                print(f"[{now_str}] (#{packet_count:04d}) | {topic:<30} | Raw bytes ({len(raw_data)} B)")

    except (ClientError, ConnectError) as ce:
        print(f"\n❌ MQTT Client Error: {ce}")
        print("Tip: Run 'python scripts/run_local_mqtt_broker.py' to start the local broker.")
    except (asyncio.CancelledError, KeyboardInterrupt):
        print("\nStopping monitor...")
    finally:
        try:
            await client.disconnect()
        except Exception:
            pass
        print("Monitor disconnected.")


def main():
    try:
        asyncio.run(monitor())
    except KeyboardInterrupt:
        print("\nExiting.")
        sys.exit(0)


if __name__ == "__main__":
    main()
