@echo off
setlocal
cd /d "%~dp0"
title Industrial RCA System - Stop All Services
color 0E

echo ======================================================================
echo    Stopping Industrial RCA Services (Ports 8000, 5173, 1883, 8883)...
echo ======================================================================
echo.

python -c "
import subprocess, re

ports = [8000, 5173, 1883, 8883]
killed = set()
for port in ports:
    try:
        out = subprocess.check_output(f'netstat -ano | findstr :{port}', shell=True, text=True, errors='ignore')
        for line in out.strip().splitlines():
            parts = re.split(r'\s+', line.strip())
            if len(parts) >= 5 and ('LISTENING' in line or 'ESTABLISHED' in line):
                pid = parts[-1]
                if pid and pid != '0' and pid not in killed:
                    killed.add(pid)
                    print(f'Terminating process PID {pid} (Port {port})...')
                    subprocess.run(f'taskkill /F /T /PID {pid}', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception:
        pass
if not killed:
    print('No active services found running on ports 8000, 5173, 1883.')
else:
    print(f'Successfully stopped {len(killed)} process(es).')
"

echo.
echo [DONE] All services have been stopped.
timeout /t 2 >nul
