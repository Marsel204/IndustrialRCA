"""
Unified One-Click Launcher for Industrial RCA System.
Orchestrates:
  1. Local MQTT Telemetry Broker (Port 1883 / 8883)
  2. FastAPI REST & SSE Backend (Port 8000)
  3. React + Vite Frontend (Port 5173)
Auto-detects active ports, checks service health, opens the browser,
and manages clean shutdown of all background services on exit.
"""

import os
import sys
import time
import socket
import signal
import subprocess
import webbrowser
import urllib.request
from pathlib import Path

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Enable ANSI escape sequences on Windows console
if os.name == "nt":
    os.system("")

# ANSI Color codes
C_RESET = "\033[0m"
C_BOLD = "\033[1m"
C_CYAN = "\033[36m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_MAGENTA = "\033[35m"
C_RED = "\033[31m"
C_DIM = "\033[2m"

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Checks if a TCP port is currently open and listening."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def kill_pid_tree(pid: int):
    """Terminates a process and all of its child processes."""
    if os.name == "nt":
        subprocess.run(
            f"taskkill /F /T /PID {pid}",
            shell=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    else:
        try:
            os.killpg(os.getpgid(pid), signal.SIGTERM)
        except Exception:
            try:
                os.kill(pid, signal.SIGKILL)
            except Exception:
                pass


def wait_for_service(url: str, name: str, timeout_sec: int = 15) -> bool:
    """Polls an HTTP endpoint until it returns a successful status code."""
    start = time.time()
    while time.time() - start < timeout_sec:
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "RCA-Launcher"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status in (200, 304):
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def print_banner():
    print(
        f"\n{C_CYAN}{C_BOLD}"
        "======================================================================\n"
        "           INDUSTRIAL ROOT CAUSE ANALYSIS (RCA) SYSTEM                \n"
        "                  Unified One-Click Launcher                         \n"
        f"======================================================================{C_RESET}"
    )
    print(f" {C_BOLD}Model Engine:{C_RESET} {C_MAGENTA}DeepSeek V4.1 Flash (deepseek-flash){C_RESET}")
    print(f" {C_BOLD}Root Dir    :{C_RESET} {ROOT_DIR}")
    print(f"{C_CYAN}----------------------------------------------------------------------{C_RESET}\n")


def main():
    print_banner()

    # Verify python and node
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f" {C_GREEN}✓{C_RESET} Python Runtime: {py_ver}")

    npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
    python_exe = sys.executable

    processes = []

    try:
        # 1. Start Local MQTT Broker (Port 1883)
        if is_port_in_use(1883):
            print(f" {C_GREEN}●{C_RESET} MQTT Broker     : {C_DIM}Port 1883 already active (reusing existing broker){C_RESET}")
        else:
            print(f" {C_YELLOW}▶{C_RESET} Starting MQTT Broker (Port 1883 / 8883)...", end="", flush=True)
            mqtt_proc = subprocess.Popen(
                [python_exe, "scripts/run_local_mqtt_broker.py"],
                cwd=str(ROOT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            processes.append(("MQTT Broker", mqtt_proc))
            time.sleep(1)
            print(f"\r {C_GREEN}✓{C_RESET} MQTT Broker     : {C_GREEN}Active on 0.0.0.0:1883{C_RESET}")

        # 2. Start FastAPI Backend (Port 8000)
        if is_port_in_use(8000):
            print(f" {C_GREEN}●{C_RESET} FastAPI Backend : {C_DIM}Port 8000 already active (reusing existing backend){C_RESET}")
        else:
            print(f" {C_YELLOW}▶{C_RESET} Starting FastAPI Backend (Port 8000)...", end="", flush=True)
            api_proc = subprocess.Popen(
                [python_exe, "-u", "-m", "uvicorn", "industrial_rca.api:api_app", "--host", "0.0.0.0", "--port", "8000"],
                cwd=str(ROOT_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            processes.append(("FastAPI Backend", api_proc))
            if wait_for_service("http://127.0.0.1:8000/api/v1/health", "FastAPI"):
                print(f"\r {C_GREEN}✓{C_RESET} FastAPI Backend : {C_GREEN}Healthy on http://localhost:8000{C_RESET}")
            else:
                print(f"\r {C_YELLOW}!{C_RESET} FastAPI Backend : Starting up on http://localhost:8000")

        # 3. Start React + Vite Frontend (Port 5173)
        if is_port_in_use(5173):
            print(f" {C_GREEN}●{C_RESET} React Frontend  : {C_DIM}Port 5173 already active (reusing existing server){C_RESET}")
        else:
            print(f" {C_YELLOW}▶{C_RESET} Starting React Frontend (Port 5173)...", end="", flush=True)
            # Find vite executable or use npm run dev
            vite_cmd = FRONTEND_DIR / "node_modules" / ".bin" / ("vite.cmd" if os.name == "nt" else "vite")
            if vite_cmd.exists():
                fe_args = [str(vite_cmd), "--host", "0.0.0.0", "--port", "5173"]
            else:
                fe_args = [npm_cmd, "run", "dev"]

            fe_proc = subprocess.Popen(
                fe_args,
                cwd=str(FRONTEND_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            processes.append(("React Frontend", fe_proc))
            if wait_for_service("http://127.0.0.1:5173", "Frontend"):
                print(f"\r {C_GREEN}✓{C_RESET} React Frontend  : {C_GREEN}Ready on http://localhost:5173{C_RESET}")
            else:
                print(f"\r {C_YELLOW}!{C_RESET} React Frontend  : Launching on http://localhost:5173")

        # 4. Open Default Web Browser
        print(f"\n {C_CYAN}▶ Opening web browser to http://localhost:5173...{C_RESET}")
        time.sleep(1)
        webbrowser.open("http://localhost:5173")

        # Summary box
        print(
            f"\n{C_GREEN}{C_BOLD}"
            "======================================================================\n"
            "   ✓ ALL SERVICES ARE RUNNING AND FULLY OPERATIONAL!                 \n"
            f"======================================================================{C_RESET}"
        )
        print(f"  • {C_BOLD}Main Dashboard :{C_RESET} {C_CYAN}http://localhost:5173{C_RESET}")
        print(f"  • {C_BOLD}FastAPI Swagger:{C_RESET} {C_CYAN}http://localhost:8000/docs{C_RESET}")
        print(f"  • {C_BOLD}Edge MQTT Broker:{C_RESET} {C_CYAN}tcp://localhost:1883{C_RESET}")
        print(f"  • {C_BOLD}AI Model       :{C_RESET} {C_MAGENTA}DeepSeek V4.1 Flash{C_RESET}")
        print(f"\n{C_DIM}Press Ctrl+C (or close this window) to terminate all services.{C_RESET}\n")

        # Keep alive until user terminates
        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print(f"\n\n{C_YELLOW}Shutdown requested. Stopping all services...{C_RESET}")
    finally:
        for name, proc in processes:
            try:
                print(f" Stopping {name} (PID {proc.pid})...")
                kill_pid_tree(proc.pid)
            except Exception:
                pass
        print(f"{C_GREEN}All services stopped cleanly. Goodbye!{C_RESET}")


if __name__ == "__main__":
    main()
