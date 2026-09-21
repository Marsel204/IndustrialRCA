"""
Utility script to stop all active Industrial RCA background services.
Cleans up processes listening on ports 8000, 5173, 1883, and 8883.
"""

import os
import re
import subprocess

PORTS = [8000, 5173, 1883, 8883]


def main():
    killed = set()
    current_pid = str(os.getpid())

    for port in PORTS:
        try:
            out = subprocess.check_output(
                f"netstat -ano | findstr :{port}",
                shell=True,
                text=True,
                errors="ignore",
            )
            for line in out.strip().splitlines():
                parts = re.split(r"\s+", line.strip())
                if len(parts) >= 5 and ("LISTENING" in line or "ESTABLISHED" in line):
                    pid = parts[-1]
                    if pid and pid not in ("0", current_pid) and pid not in killed:
                        killed.add(pid)
                        print(f" Terminating process PID {pid} (Port {port})...")
                        subprocess.run(
                            f"taskkill /F /T /PID {pid}",
                            shell=True,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
        except Exception:
            pass

    # Terminate any active Cloudflare Tunnel processes
    if os.name == "nt":
        try:
            subprocess.run(
                "taskkill /F /IM cloudflared.exe",
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass

    if not killed:
        print(" No active services found running on ports 8000, 5173, 1883.")
    else:
        print(f" Successfully stopped {len(killed)} background process(es).")


if __name__ == "__main__":
    main()
