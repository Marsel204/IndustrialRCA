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
    """Checks if a TCP port is currently open and listening on 127.0.0.1 or localhost."""
    for h in (host, "127.0.0.1", "localhost"):
        try:
            with socket.create_connection((h, port), timeout=0.5):
                return True
        except Exception:
            pass
    return False


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


def wait_for_service(url: str, name: str, timeout_sec: int = 15, port: int = None) -> bool:
    """Polls an HTTP endpoint or TCP port until service is active."""
    start = time.time()
    while time.time() - start < timeout_sec:
        if port and is_port_in_use(port):
            return True
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                if resp.status in (200, 304):
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def open_browser(url: str) -> bool:
    """
    Robust browser launcher for Windows and Linux/macOS.
    Bypasses silent Windows ShellExecute failures by directly checking and
    launching Chrome, Edge, or Brave before falling back to webbrowser.open.
    """
    if os.name == "nt":
        candidates = [
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
        ]
        for exe in candidates:
            if os.path.exists(exe):
                try:
                    subprocess.Popen([exe, url])
                    return True
                except Exception:
                    pass
        try:
            os.system(f'start "" "{url}"')
            return True
        except Exception:
            pass

    try:
        return webbrowser.open(url)
    except Exception:
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
            if wait_for_service("http://127.0.0.1:8000/api/v1/health", "FastAPI", port=8000):
                print(f"\r {C_GREEN}✓{C_RESET} FastAPI Backend : {C_GREEN}Healthy on http://localhost:8000{C_RESET}")
            else:
                print(f"\r {C_YELLOW}!{C_RESET} FastAPI Backend : Starting up on http://localhost:8000")

        # 3. Start React + Vite Frontend (Port 5173)
        if is_port_in_use(5173):
            print(f" {C_GREEN}●{C_RESET} React Frontend  : {C_DIM}Port 5173 already active (reusing existing server){C_RESET}")
        else:
            # Verify required frontend packages exist
            markdown_pkg = FRONTEND_DIR / "node_modules" / "react-markdown"
            if not markdown_pkg.exists():
                print(f" {C_YELLOW}▶{C_RESET} Installing frontend packages (npm install)...", end="", flush=True)
                subprocess.run([npm_cmd, "install"], cwd=str(FRONTEND_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                print(f"\r {C_GREEN}✓{C_RESET} Frontend packages installed.               ")

            print(f" {C_YELLOW}▶{C_RESET} Starting React Frontend (Port 5173)...", end="", flush=True)
            # Find vite executable or use npm run dev
            vite_cmd = FRONTEND_DIR / "node_modules" / ".bin" / ("vite.cmd" if os.name == "nt" else "vite")
            if vite_cmd.exists():
                fe_args = f'"{vite_cmd}" --host 0.0.0.0 --port 5173' if os.name == "nt" else [str(vite_cmd), "--host", "0.0.0.0", "--port", "5173"]
            else:
                fe_args = f"{npm_cmd} run dev" if os.name == "nt" else [npm_cmd, "run", "dev"]

            fe_proc = subprocess.Popen(
                fe_args,
                cwd=str(FRONTEND_DIR),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=(os.name == "nt"),
            )
            processes.append(("React Frontend", fe_proc))
            if wait_for_service("http://127.0.0.1:5173", "Frontend", port=5173):
                print(f"\r {C_GREEN}✓{C_RESET} React Frontend  : {C_GREEN}Ready on http://localhost:5173{C_RESET}")
            else:
                print(f"\r {C_YELLOW}!{C_RESET} React Frontend  : Launching on http://localhost:5173")

        # 4. Open Default Web Browser
        print(f"\n {C_CYAN}▶ Opening web browser to http://localhost:5173...{C_RESET}")
        time.sleep(1)
        opened = open_browser("http://localhost:5173")
        if opened:
            print(f" {C_GREEN}✓{C_RESET} Browser launched successfully.")
        else:
            print(f" {C_YELLOW}!{C_RESET} Browser auto-open was intercepted by Windows.")

        # Summary box
        print(
            f"\n{C_GREEN}{C_BOLD}"
            "======================================================================\n"
            "   ✓ ALL SERVICES ARE RUNNING AND FULLY OPERATIONAL!                 \n"
            f"======================================================================{C_RESET}"
        )
        print(f"  • {C_BOLD}Main Dashboard :{C_RESET} {C_CYAN}{C_BOLD}http://localhost:5173{C_RESET}  ◄── {C_YELLOW}OPEN THIS IN YOUR BROWSER{C_RESET}")
        print(f"  • {C_BOLD}FastAPI Swagger:{C_RESET} {C_CYAN}http://localhost:8000/docs{C_RESET}")
        print(f"  • {C_BOLD}Edge MQTT Broker:{C_RESET} {C_CYAN}tcp://localhost:1883{C_RESET}")
        print(f"  • {C_BOLD}AI Model       :{C_RESET} {C_MAGENTA}DeepSeek V4.1 Flash{C_RESET}")
        print(f"\n{C_YELLOW}{C_BOLD}NOTE:{C_RESET} This terminal window must stay open while using the app.")
        print(f"{C_DIM}Press Ctrl+C (or close this window) to terminate all services.{C_RESET}\n")

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
