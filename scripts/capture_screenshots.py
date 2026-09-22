"""
Automated UI Screenshot Generation Script
Uses Playwright to capture high-resolution images of the Industrial RCA dashboard for docs and README.
"""
import os
import sys
import time
import json
import urllib.request
from playwright.sync_api import sync_playwright

CHROME_PATH = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
OUTPUT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "docs", "assets", "images"))
os.makedirs(OUTPUT_DIR, exist_ok=True)

def capture_all():
    print(f"[*] Starting screenshot capture to {OUTPUT_DIR}...")
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=CHROME_PATH, headless=True)
        context = browser.new_context(viewport={"width": 1600, "height": 950}, device_scale_factor=1.5)
        page = context.new_page()

        # 1. Main Dashboard Overview (Nominal)
        print("[1/5] Capturing 01_dashboard_overview.png...")
        page.goto("http://localhost:5173", wait_until="networkidle")
        page.wait_for_timeout(3000)
        page.screenshot(path=os.path.join(OUTPUT_DIR, "01_dashboard_overview.png"))

        # 2. Trigger simulated trip incident (Err06)
        print("[2/5] Triggering simulated trip incident (Err06)...")
        req = urllib.request.Request(
            'http://127.0.0.1:8000/api/v1/telemetry/incident',
            data=json.dumps({'fault_code': 6, 'description': 'Deceleration Overvoltage Err06'}).encode('utf-8'),
            headers={'Content-Type': 'application/json'}
        )
        try:
            with urllib.request.urlopen(req) as resp:
                print("    Incident response:", resp.read().decode('utf-8'))
        except Exception as e:
            print("    Error triggering incident:", e)

        print("[*] Waiting for LangGraph RCA to reach Step 6 HITL Gate...")
        try:
            page.wait_for_selector("button:has-text('Review & Authorize')", timeout=35000)
        except Exception as e:
            print("    Timeout waiting for selector:", e)

        page.wait_for_timeout(2000)

        # 3. Capture Active Incident State with HITL Gate
        print("[3/5] Capturing 02_hitl_active_incident.png...")
        page.screenshot(path=os.path.join(OUTPUT_DIR, "02_hitl_active_incident.png"))

        # 4. Capture Review & Authorize Modal
        print("[4/5] Opening Review & Authorize modal...")
        review_btn = page.locator("button:has-text('Review & Authorize'), button:has-text('Authorize')")
        if review_btn.count() > 0 and review_btn.first.is_visible():
            review_btn.first.click()
            page.wait_for_timeout(1500)
            print("    Capturing 03_review_signoff_modal.png...")
            page.screenshot(path=os.path.join(OUTPUT_DIR, "03_review_signoff_modal.png"))
            close_btn = page.locator("button:has-text('✕'), button:has-text('Cancel')")
            if close_btn.count() > 0:
                close_btn.first.click()
                page.wait_for_timeout(1000)

        # 5. Telegram Settings Modal
        print("[5/5] Opening Telegram Bot modal...")
        tg_btn = page.locator("button:has-text('Telegram')")
        if tg_btn.count() > 0:
            tg_btn.first.click()
            page.wait_for_timeout(1500)
            print("    Capturing 05_telegram_settings_modal.png...")
            page.screenshot(path=os.path.join(OUTPUT_DIR, "05_telegram_settings_modal.png"))

        browser.close()
        print("[OK] All browser screenshots captured successfully!")

if __name__ == "__main__":
    capture_all()
