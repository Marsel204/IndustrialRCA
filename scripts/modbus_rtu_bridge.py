"""
Wecon VM Series VFD Direct Modbus RTU RS-485 Serial Bridge.
Polls physical Wecon VM VFD registers over RS-485 and streams 1 Hz telemetry
directly to the Industrial RCA FastAPI backend (http://127.0.0.1:8000/api/v1/telemetry/live/feed).

Standard Wecon VM VFD Settings:
- Baud Rate: 9600 bps (Parameter F9.01 = 3)
- Data Format: 8-N-1 (Parameter F9.02 = 0)
- Slave Station ID: 1 (Parameter F9.00 = 1)
"""

import sys
import time
import json
import argparse
import urllib.request

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    serial = None

FEED_URL = "http://127.0.0.1:8000/api/v1/telemetry/live/feed"


def calculate_crc(data: bytes) -> bytes:
    crc = 0xFFFF
    for pos in data:
        crc ^= pos
        for _ in range(8):
            if (crc & 1) != 0:
                crc >>= 1
                crc ^= 0xA001
            else:
                crc >>= 1
    return crc.to_bytes(2, byteorder="little")


def read_holding_registers(ser: serial.Serial, slave_id: int, start_reg: int, count: int, timeout: float = 0.5):
    req = bytes([slave_id, 0x03, (start_reg >> 8) & 0xFF, start_reg & 0xFF, (count >> 8) & 0xFF, count & 0xFF])
    req += calculate_crc(req)
    
    ser.reset_input_buffer()
    ser.write(req)
    
    expected_len = 3 + 2 * count + 2
    response = bytearray()
    start_t = time.time()
    while len(response) < expected_len and (time.time() - start_t) < timeout:
        chunk = ser.read(expected_len - len(response))
        if chunk:
            response.extend(chunk)
            
    if len(response) < expected_len:
        return None
        
    if response[0] != slave_id or response[1] != 0x03:
        return None
        
    calc_crc = calculate_crc(response[:-2])
    if response[-2:] != calc_crc:
        return None
        
    byte_count = response[2]
    registers = []
    for i in range(0, byte_count, 2):
        val = int.from_bytes(response[3 + i: 5 + i], byteorder="big")
        registers.append(val)
    return registers


def poll_vfd(port: str, baudrate: int = 9600, slave_id: int = 1):
    print("=" * 70)
    print("Wecon VM Series VFD Direct Modbus RTU RS-485 Bridge")
    print("=" * 70)
    print(f"  Serial Port:  {port}")
    print(f"  Baud Rate:    {baudrate} (8-N-1)")
    print(f"  Slave ID:     {slave_id}")
    print(f"  Target Feed:  {FEED_URL}")
    print("=" * 70)
    
    try:
        ser = serial.Serial(port=port, baudrate=baudrate, bytesize=8, parity='N', stopbits=1, timeout=0.2)
        print(f"✓ Opened serial port {port} successfully.")
    except Exception as e:
        print(f"❌ Failed to open serial port {port}: {e}")
        return

    try:
        while True:
            t_start = time.time()
            regs_3000 = read_holding_registers(ser, slave_id, 0x3000, 5)
            regs_fault = read_holding_registers(ser, slave_id, 0x700B, 1)
            regs_rpm = read_holding_registers(ser, slave_id, 0x100F, 1)
            
            if regs_3000:
                f_out = round(regs_3000[0] / 100.0, 2)
                f_target = round(regs_3000[1] / 100.0, 2)
                current = round(regs_3000[2] / 100.0, 2)
                v_out = float(regs_3000[3])
                v_dc = round(regs_3000[4] / 10.0, 1)
                fault_code = int(regs_fault[0]) if regs_fault else 0
                rpm = round(regs_rpm[0] / 10.0, 1) if regs_rpm else f_out * 29.0
                
                payload = {
                    "timestamp": time.time(),
                    "asset_id": "VFD_VM_01",
                    "f_out": f_out,
                    "f_target": f_target,
                    "current": current,
                    "v_out": v_out,
                    "v_dc": v_dc,
                    "rpm": rpm,
                    "fault_code": fault_code,
                    "status": "TRIPPED" if fault_code > 0 else "RUNNING",
                    "source": "modbus_rtu_serial"
                }
                
                print(f"[{time.strftime('%H:%M:%S')}] f_out: {f_out:5.2f}Hz | v_dc: {v_dc:5.1f}V | I: {current:4.2f}A | RPM: {rpm:6.1f} | Fault: {fault_code}")
                
                # Send to FastAPI
                try:
                    req = urllib.request.Request(
                        FEED_URL,
                        data=json.dumps(payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST"
                    )
                    with urllib.request.urlopen(req, timeout=0.5):
                        pass
                except Exception as e:
                    print(f"  Warning: feed forwarding failed: {e}")
            else:
                print(f"[{time.strftime('%H:%M:%S')}] No response from Slave ID {slave_id} on {port} (Check wiring A+/B-)")
                
            elapsed = time.time() - t_start
            time.sleep(max(0.1, 1.0 - elapsed))
            
    except KeyboardInterrupt:
        print("\nStopping Modbus RTU bridge...")
    finally:
        ser.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Wecon VM VFD Modbus RTU RS-485 Bridge")
    parser.add_argument("--port", default="COM2", help="Serial port (e.g. COM2, COM3, /dev/ttyUSB0)")
    parser.add_argument("--baud", type=int, default=9600, help="Baud rate (default: 9600)")
    parser.add_argument("--slave", type=int, default=1, help="Modbus Slave Station ID (default: 1)")
    args = parser.parse_args()
    poll_vfd(port=args.port, baudrate=args.baud, slave_id=args.slave)
