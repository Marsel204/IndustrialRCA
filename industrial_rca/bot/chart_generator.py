"""
In-Memory Industrial Telemetry & Waveform Dashboard Generator for Telegram Bot.
Renders high-contrast, modern, light-theme SCADA dashboard charts directly to PNG byte streams
matching the React ECharts web application UI.
"""

import io
import time
from typing import Dict, Any, List, Optional, Union
import numpy as np
import pandas as pd

import matplotlib
matplotlib.use("Agg")  # Headless non-GUI backend
import matplotlib.pyplot as plt

from industrial_rca.config import OPERATIONAL_LIMITS, EQUIPMENT_NAME, EQUIPMENT_ID


# Modern Industrial Dashboard Theme Styling (Matching React ECharts UI)
CANVAS_BG = "#F8FAFC"       # Slate 50 (light canvas)
CARD_BG = "#FFFFFF"         # Pure white card
CARD_BORDER = "#E2E8F0"     # Slate 200 border
GRID_COLOR = "#F1F5F9"      # Very faint slate horizontal gridline
TEXT_MAIN = "#0F172A"       # Slate 900 primary text
TEXT_MUTED = "#64748B"      # Slate 500 secondary labels
COLOR_RED = "#DC2626"       # Red 600 trip thresholds

# Distinct vibrant line colors matching React ECharts
COLOR_FREQ = "#0284C7"      # Sky 600 (Output Frequency)
COLOR_VOLT = "#2563EB"      # Blue 600 (DC Bus Voltage)
COLOR_CURR = "#0D9488"      # Teal 600 (Motor Phase Current)
COLOR_RPM = "#7C3AED"       # Purple 600 (Induction Motor RPM)


def _extract_dataframe(telemetry_data: Union[pd.DataFrame, Dict[str, Any], List[Dict[str, Any]], Any]) -> pd.DataFrame:
    """Extracts a standardized Pandas DataFrame from various telemetry container types."""
    if hasattr(telemetry_data, "df_1hz"):
        df = telemetry_data.df_1hz.copy()
    elif isinstance(telemetry_data, pd.DataFrame):
        df = telemetry_data.copy()
    elif isinstance(telemetry_data, dict) and "points" in telemetry_data:
        df = pd.DataFrame(telemetry_data["points"])
    elif isinstance(telemetry_data, list):
        df = pd.DataFrame(telemetry_data)
    else:
        try:
            df = pd.DataFrame(telemetry_data)
        except Exception:
            df = pd.DataFrame()

    if df.empty or "f_out" not in df.columns:
        df = pd.DataFrame({
            "f_out": [40.0] * 60,
            "v_dc": [182.0] * 60,
            "current": [1.15] * 60,
            "rpm": [1160.0] * 60,
            "fault_code": [0] * 60,
        })
    else:
        # Fill standard columns if missing
        if "v_dc" not in df.columns:
            df["v_dc"] = 182.0
        if "current" not in df.columns:
            df["current"] = 1.15
        if "rpm" not in df.columns:
            df["rpm"] = df["f_out"] * 29.0
        if "fault_code" not in df.columns:
            df["fault_code"] = 0

    return df


def generate_trip_waveform(
    telemetry_data: Union[pd.DataFrame, Dict[str, Any], Any],
    fault_code: Optional[int] = None,
    asset_id: str = EQUIPMENT_ID,
    title_suffix: str = "Hardware Trip Waveform",
) -> bytes:
    """
    Renders a 2x2 modern industrial dashboard image matching the React web UI.
    Includes:
    - [0, 0] f_out · VFD Inverter Output Frequency (Hz) with 40.00 Hz trip line
    - [0, 1] v_dc · DC Bus Voltage (V DC) with 195.0 V trip line
    - [1, 0] I_out · Motor Phase Current (Amperes) with 2.50 A trip line
    - [1, 1] RPM · Induction Motor Speed (RPM) with 1450 RPM trip line
    """
    # Extract metadata fault code if available
    if not fault_code and hasattr(telemetry_data, "metadata"):
        fault_code = telemetry_data.metadata.get("fault_code", 0)

    df = _extract_dataframe(telemetry_data)
    if not fault_code and "fault_code" in df.columns:
        fc_max = int(df["fault_code"].max())
        if fc_max > 0:
            fault_code = fc_max

    n = len(df)
    t = np.arange(n) - (n - 1)  # Relative seconds timeline (-59s ... 0s)
    x_min, x_max = t[0], t[-1]

    fig = plt.figure(figsize=(13.2, 8.2), facecolor=CANVAS_BG, dpi=160)
    gs = fig.add_gridspec(2, 2, top=0.84, bottom=0.08, left=0.07, right=0.96, wspace=0.18, hspace=0.34)

    # ── Header Banner ──
    is_tripped = (fault_code or 0) > 0 or (df["fault_code"] > 0).any()
    status_label = f"TRIPPED: Err0{fault_code}" if is_tripped else "SYSTEM STATUS: NOMINAL"
    status_color = "#DC2626" if is_tripped else "#16A34A"
    status_bg = "#FEE2E2" if is_tripped else "#DCFCE7"

    # Main Title and Subtitle
    fig.text(0.07, 0.940, f"{asset_id} · Industrial Telemetry Dashboard", fontsize=15, fontweight="bold", color=TEXT_MAIN)
    fig.text(0.07, 0.905, f"Wecon VM Series Inverter & Motor Test Bench • {time.strftime('%Y-%m-%d %H:%M:%S UTC')}", fontsize=10, color=TEXT_MUTED)

    # Status Pill on Top Right
    bbox_props = dict(boxstyle="round,pad=0.5", facecolor=status_bg, edgecolor=status_color, linewidth=1.2)
    fig.text(0.96, 0.925, f"● {status_label}", fontsize=9.5, fontweight="bold", color=status_color, ha="right", va="center", bbox=bbox_props)

    # Helper function to style each card exactly like the React dashboard
    def style_card(ax, title: str):
        ax.set_facecolor(CARD_BG)
        ax.set_title(title, loc="left", fontsize=11, fontweight="bold", color=TEXT_MAIN, pad=12)

        # Only horizontal grid lines, clean and faint
        ax.yaxis.grid(True, which="major", color=GRID_COLOR, linestyle="-", linewidth=1.2)
        ax.xaxis.grid(False)

        # Spines: hide top, right, left; keep subtle bottom axis
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_visible(False)
        ax.spines["bottom"].set_color("#CBD5E1")
        ax.spines["bottom"].set_linewidth(1.0)

        # No protruding y-axis tick marks
        ax.tick_params(axis="y", which="both", length=0, colors=TEXT_MUTED, labelsize=9)
        ax.tick_params(axis="x", which="both", length=3, color="#CBD5E1", colors=TEXT_MUTED, labelsize=8.5)

        ax.set_xlim(x_min, x_max)
        step = max(10, n // 5)
        ticks = np.arange(x_min, x_max + 1, step)
        if ticks[-1] != x_max:
            ticks = np.append(ticks, x_max)
        ax.set_xticks(ticks)
        ax.set_xticklabels([f"{int(x)}s" if x < 0 else "Now" for x in ticks], fontsize=8.5, color=TEXT_MUTED)

    label_box = dict(boxstyle="square,pad=0.15", facecolor=CARD_BG, edgecolor="none", alpha=0.90)

    # 1. Output Frequency Card
    ax_f = fig.add_subplot(gs[0, 0])
    style_card(ax_f, "f_out · VFD Inverter Output Frequency (Hz)")
    y_f = df["f_out"].values
    ax_f.plot(t, y_f, color=COLOR_FREQ, linewidth=2.4, label="f_out")
    ax_f.fill_between(t, 0, y_f, color=COLOR_FREQ, alpha=0.12)
    # Threshold 40.00 Hz
    ax_f.axhline(40.0, color=COLOR_RED, linestyle="--", linewidth=1.6)
    ax_f.text(x_max, 41.5, "40.00 Hz", color=COLOR_RED, fontweight="bold", fontsize=9, ha="right", va="bottom", bbox=label_box)
    f_max_disp = max(62.0, float(np.max(y_f)) * 1.1)
    ax_f.set_ylim(0, f_max_disp)
    ax_f.set_yticks([0, 10, 20, 30, 40, 50, 60])
    ax_f.set_yticklabels(["0 Hz", "10 Hz", "20 Hz", "30 Hz", "40 Hz", "50 Hz", "60 Hz"])

    # 2. DC Bus Voltage Card
    ax_v = fig.add_subplot(gs[0, 1])
    style_card(ax_v, "v_dc · DC Bus Voltage (V DC)")
    y_v = df["v_dc"].values
    ax_v.plot(t, y_v, color=COLOR_VOLT, linewidth=2.4, label="v_dc")
    ax_v.fill_between(t, 0, y_v, color=COLOR_VOLT, alpha=0.12)
    # Threshold 195.0 V
    ax_v.axhline(195.0, color=COLOR_RED, linestyle="--", linewidth=1.6)
    ax_v.text(x_max, 197.5, "195.0 V", color=COLOR_RED, fontweight="bold", fontsize=9, ha="right", va="bottom", bbox=label_box)
    v_max_disp = max(230.0, float(np.max(y_v)) * 1.08)
    ax_v.set_ylim(0, v_max_disp)
    ax_v.set_yticks([0, 50, 100, 150, 200, 225])
    ax_v.set_yticklabels(["0 V", "50 V", "100 V", "150 V", "200 V", "225 V"])

    # 3. Motor Current Card
    ax_i = fig.add_subplot(gs[1, 0])
    style_card(ax_i, "I_out · Motor Phase Current (Amperes)")
    y_i = df["current"].values
    ax_i.plot(t, y_i, color=COLOR_CURR, linewidth=2.4, label="current")
    ax_i.fill_between(t, 0, y_i, color=COLOR_CURR, alpha=0.12)
    # Threshold 2.50 A
    ax_i.axhline(2.50, color=COLOR_RED, linestyle="--", linewidth=1.6)
    ax_i.text(x_max, 2.56, "2.50 A", color=COLOR_RED, fontweight="bold", fontsize=9, ha="right", va="bottom", bbox=label_box)
    i_max_disp = max(4.1, float(np.max(y_i)) * 1.15)
    ax_i.set_ylim(0, i_max_disp)
    ax_i.set_yticks([0, 1, 2, 3, 4])
    ax_i.set_yticklabels(["0 A", "1 A", "2 A", "3 A", "4 A"])

    # 4. Motor Speed RPM Card
    ax_rpm = fig.add_subplot(gs[1, 1])
    style_card(ax_rpm, "RPM · Induction Motor Speed (RPM)")
    y_rpm = df["rpm"].values if "rpm" in df.columns else df["f_out"].values * 29.0
    ax_rpm.plot(t, y_rpm, color=COLOR_RPM, linewidth=2.4, label="rpm")
    ax_rpm.fill_between(t, 0, y_rpm, color=COLOR_RPM, alpha=0.12)
    # Threshold 1450 RPM
    ax_rpm.axhline(1450.0, color=COLOR_RED, linestyle="--", linewidth=1.6)
    ax_rpm.text(x_max, 1475.0, "1450 RPM", color=COLOR_RED, fontweight="bold", fontsize=9, ha="right", va="bottom", bbox=label_box)
    rpm_max_disp = max(1850.0, float(np.max(y_rpm)) * 1.1)
    ax_rpm.set_ylim(0, rpm_max_disp)
    ax_rpm.set_yticks([0, 300, 600, 900, 1200, 1500, 1800])
    ax_rpm.set_yticklabels(["0", "300", "600", "900", "1,200", "1,500", "1,800"])

    # Trip Event Point Marker (if tripped)
    if is_tripped:
        for ax, y_data in [(ax_f, y_f), (ax_v, y_v), (ax_i, y_i), (ax_rpm, y_rpm)]:
            ax.scatter([x_max], [y_data[-1]], color=COLOR_RED, s=50, zorder=5, edgecolors="#FFFFFF", linewidth=1.5)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor=CANVAS_BG, dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def generate_live_trend_plot(
    metrics_history: List[Dict[str, Any]],
    asset_id: str = EQUIPMENT_ID,
) -> bytes:
    """Renders a real-time historical trend in the clean 2x2 dashboard layout."""
    df = _extract_dataframe(metrics_history)
    return generate_trip_waveform(df, fault_code=0, asset_id=asset_id, title_suffix="Live Telemetry Dashboard")


def generate_spectrum_plot(
    normal_waveform: Optional[Dict[str, Any]] = None,
    fault_waveform: Optional[Dict[str, Any]] = None,
    sampling_rate: float = 20000.0,
    asset_id: str = EQUIPMENT_ID,
) -> bytes:
    """Renders 20 kHz High-Frequency Vibration FFT Spectrum comparison in clean industrial style."""
    fig, ax = plt.subplots(figsize=(10, 5.0), facecolor=CANVAS_BG, dpi=160)
    ax.set_facecolor(CARD_BG)
    ax.set_title("20 kHz Vibration Velocity FFT Spectrum (0 - 10,000 Hz)", loc="left", fontsize=11, fontweight="bold", color=TEXT_MAIN, pad=12)

    ax.yaxis.grid(True, which="major", color=GRID_COLOR, linestyle="-", linewidth=1.2)
    ax.xaxis.grid(True, which="major", color=GRID_COLOR, linestyle="-", linewidth=1.0)
    for spine in ax.spines.values():
        spine.set_color(CARD_BORDER)
        spine.set_linewidth(1.0)

    ax.tick_params(colors=TEXT_MUTED, labelsize=9)

    def _fft(signal: np.ndarray):
        n = len(signal)
        fft_vals = np.fft.rfft(signal)
        fft_mag = (2.0 / n) * np.abs(fft_vals)
        freqs = np.fft.rfftfreq(n, d=1.0 / sampling_rate)
        return freqs, fft_mag

    if normal_waveform and "signal" in normal_waveform:
        sig_norm = np.array(normal_waveform["signal"])
        f_norm, mag_norm = _fft(sig_norm)
        ax.plot(f_norm, mag_norm, color="#0D9488", label="Baseline Normal FFT", alpha=0.75, linewidth=1.5)

    if fault_waveform and "signal" in fault_waveform:
        sig_fault = np.array(fault_waveform["signal"])
        f_fault, mag_fault = _fft(sig_fault)
        ax.plot(f_fault, mag_fault, color=COLOR_RED, label="Trip / Fault FFT Spectrum", linewidth=1.8)

    # Highlight Cavitation Band (2 kHz - 8 kHz)
    ax.axvspan(2000, 8000, color="#FEF3C7", alpha=0.45, label="Cavitation Band (2-8 kHz)")

    ax.set_xlabel("Frequency (Hz)", color=TEXT_MAIN, fontsize=9.5)
    ax.set_ylabel("Amplitude (mm/s)", color=TEXT_MAIN, fontsize=9.5)
    ax.set_xlim(0, 10000)
    ax.legend(loc="upper right", facecolor=CARD_BG, edgecolor=CARD_BORDER, fontsize=8.5, labelcolor=TEXT_MAIN)

    buf = io.BytesIO()
    plt.savefig(buf, format="png", bbox_inches="tight", facecolor=CANVAS_BG, dpi=160)
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()
