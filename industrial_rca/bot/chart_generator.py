"""
In-Memory Industrial Telemetry & Waveform Dashboard Generator for Telegram Bot.
Renders high-contrast, modern, light-theme SCADA dashboard charts directly to PNG byte streams
matching the React ECharts web application UI.
"""

import io
import time
from typing import Dict, Any, List, Optional, Union, Tuple
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
COLOR_FREQ_SET = "#D97706"  # Amber 600 (Setpoint dashed)
COLOR_VOLT = "#2563EB"      # Blue 600 (DC Bus Voltage)
COLOR_VOUT = "#6366F1"      # Indigo 600 (AC Output Voltage)
COLOR_CURR = "#0D9488"      # Teal 600 (Motor Phase Current)
COLOR_RPM = "#7C3AED"       # Purple 600 (Induction Motor RPM)
COLOR_TORQUE = "#EC4899"    # Pink 500 (Motor Torque %)
COLOR_POWER = "#D97706"     # Amber 600 (Active Power kW)


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
            "f_target": [40.0] * 60,
            "v_dc": [182.0] * 60,
            "v_out": [184.0] * 60,
            "current": [1.15] * 60,
            "rpm": [1160.0] * 60,
            "torque": [5.0] * 60,
            "power": [0.05] * 60,
            "fault_code": [0] * 60,
        })
    else:
        # Fill standard columns if missing
        if "f_target" not in df.columns:
            df["f_target"] = df["f_out"]
        if "v_dc" not in df.columns:
            df["v_dc"] = 182.0
        if "v_out" not in df.columns:
            df["v_out"] = np.where(df["f_out"] > 0, 184.0, 0.0)
        if "current" not in df.columns:
            df["current"] = 1.15
        if "rpm" not in df.columns:
            df["rpm"] = df["f_out"] * 29.0
        if "torque" not in df.columns:
            df["torque"] = 5.0
        if "power" not in df.columns:
            df["power"] = np.round(np.clip(df["current"] * df["v_out"] * np.sqrt(3) * 0.85 / 1000.0, 0.0, 1.5), 2)
        if "fault_code" not in df.columns:
            df["fault_code"] = 0

    return df


def get_dc_bus_chart_envelope(max_v: float) -> Tuple[float, float, List[int], List[str]]:
    """
    Returns (v_trip, v_max_disp, y_ticks, y_labels) based on physical vs simulation voltage.
    - Physical 220V AC input rig: DC bus nominal is ~270-290V DC, trip threshold is 380V DC.
    - Simulation datasets: DC bus baseline is 182-206V DC, trip threshold is 220V DC.
    """
    is_physical = (max_v > 240.0)
    v_trip = 380.0 if is_physical else 220.0
    v_max_disp = max((420.0 if is_physical else 230.0), max_v * 1.08)
    if is_physical:
        ticks = [0, 100, 200, 300, 380]
        labels = ["0 V", "100 V", "200 V", "300 V", "380 V"]
    else:
        ticks = [0, 50, 100, 150, 200, 220]
        labels = ["0 V", "50 V", "100 V", "150 V", "200 V", "220 V"]
    return v_trip, v_max_disp, ticks, labels


def generate_trip_waveform(
    telemetry_data: Union[pd.DataFrame, Dict[str, Any], Any],
    fault_code: Optional[int] = None,
    asset_id: str = EQUIPMENT_ID,
    title_suffix: str = "Hardware Trip Waveform",
) -> bytes:
    """
    Renders a 3x2 modern industrial dashboard image matching the React web UI.
    Includes all 6 SCADA telemetry channels:
    - [0, 0] f_out · VFD Output Frequency vs Setpoint (Hz) with 40.00 Hz trip line
    - [0, 1] v_dc · DC Bus Voltage (V DC) with dynamic trip line (380V physical / 220V sim)
    - [1, 0] v_out · Inverter AC Output Voltage (V AC) with 184V nominal & 220V rated lines
    - [1, 1] I_out · Motor Phase Current (Amperes) with 2.50 A trip line & 1.15 A FLA
    - [2, 0] RPM · Induction Motor Speed (RPM) with dynamic sync speed line (Ns = 30 * f)
    - [2, 1] τ & P · Motor Mechanical Torque (%) & Active Power (kW) dual-axis
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

    fig = plt.figure(figsize=(13.6, 11.4), facecolor=CANVAS_BG, dpi=160)
    gs = fig.add_gridspec(3, 2, top=0.91, bottom=0.06, left=0.07, right=0.96, wspace=0.18, hspace=0.36)

    # ── Header Banner ──
    is_tripped = (fault_code or 0) > 0 or (df["fault_code"] > 0).any()
    status_label = f"TRIPPED: Err0{fault_code}" if is_tripped else "SYSTEM STATUS: NOMINAL"
    status_color = "#DC2626" if is_tripped else "#16A34A"
    status_bg = "#FEE2E2" if is_tripped else "#DCFCE7"

    # Main Title and Subtitle
    fig.text(0.07, 0.955, f"{asset_id} · Industrial Telemetry Dashboard (6 Channels)", fontsize=15, fontweight="bold", color=TEXT_MAIN)
    fig.text(0.07, 0.932, f"Wecon VM Series Inverter & Motor Test Bench • {time.strftime('%Y-%m-%d %H:%M:%S UTC')}", fontsize=10, color=TEXT_MUTED)

    # Status Pill on Top Right
    bbox_props = dict(boxstyle="round,pad=0.5", facecolor=status_bg, edgecolor=status_color, linewidth=1.2)
    fig.text(0.96, 0.945, f"● {status_label}", fontsize=9.5, fontweight="bold", color=status_color, ha="right", va="center", bbox=bbox_props)

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
    style_card(ax_f, "f_out · Output Frequency vs Setpoint (Hz)")
    y_f = df["f_out"].values
    ax_f.plot(t, y_f, color=COLOR_FREQ, linewidth=2.4, label="f_out")
    ax_f.fill_between(t, 0, y_f, color=COLOR_FREQ, alpha=0.12)
    if "f_target" in df.columns:
        y_f_set = df["f_target"].values
        ax_f.plot(t, y_f_set, color=COLOR_FREQ_SET, linestyle="--", linewidth=1.4, alpha=0.9, label="Setpoint")
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
    # Dynamic DC bus trip threshold & scaling (380V physical / 220V sim)
    max_v = float(np.max(y_v)) if len(y_v) > 0 else 0.0
    v_trip, v_max_disp, v_ticks, v_labels = get_dc_bus_chart_envelope(max_v)
    ax_v.axhline(v_trip, color=COLOR_RED, linestyle="--", linewidth=1.6)
    offset_y = 6.0 if max_v > 240.0 else 2.5
    ax_v.text(x_max, v_trip + offset_y, f"{v_trip:.1f} V", color=COLOR_RED, fontweight="bold", fontsize=9, ha="right", va="bottom", bbox=label_box)
    nom_v = 276.0 if max_v > 240.0 else 208.0
    ax_v.axhline(nom_v, color="#059669", linestyle=":", linewidth=1.3, alpha=0.85)
    ax_v.text(x_min, nom_v + (3.0 if max_v > 240.0 else 2.0), f"Nom ~{int(nom_v)}V", color="#059669", fontsize=8.5, ha="left", va="bottom", bbox=label_box)
    ax_v.set_ylim(0, v_max_disp)
    ax_v.set_yticks(v_ticks)
    ax_v.set_yticklabels(v_labels)

    # 3. Inverter AC Output Voltage Card
    ax_vout = fig.add_subplot(gs[1, 0])
    style_card(ax_vout, "v_out · Inverter AC Output Voltage (V AC)")
    y_vout = df["v_out"].values if "v_out" in df.columns else np.zeros(n)
    ax_vout.plot(t, y_vout, color=COLOR_VOUT, linewidth=2.4, label="v_out")
    ax_vout.fill_between(t, 0, y_vout, color=COLOR_VOUT, alpha=0.12)
    ax_vout.axhline(220.0, color="#64748B", linestyle="--", linewidth=1.4)
    ax_vout.text(x_max, 222.0, "Rated 220V", color="#64748B", fontweight="bold", fontsize=8.5, ha="right", va="bottom", bbox=label_box)
    ax_vout.axhline(184.0, color="#059669", linestyle=":", linewidth=1.4)
    ax_vout.text(x_min, 186.0, "Nom 184V", color="#059669", fontsize=8.5, ha="left", va="bottom", bbox=label_box)
    vout_max_disp = max(250.0, float(np.max(y_vout)) * 1.1)
    ax_vout.set_ylim(0, vout_max_disp)
    ax_vout.set_yticks([0, 50, 100, 150, 184, 220])
    ax_vout.set_yticklabels(["0 V", "50 V", "100 V", "150 V", "184 V", "220 V"])

    # 4. Motor Current Card
    ax_i = fig.add_subplot(gs[1, 1])
    style_card(ax_i, "I_out · Motor Phase Current (Amperes)")
    y_i = df["current"].values
    ax_i.plot(t, y_i, color=COLOR_CURR, linewidth=2.4, label="current")
    ax_i.fill_between(t, 0, y_i, color=COLOR_CURR, alpha=0.12)
    # Threshold 2.50 A
    ax_i.axhline(2.50, color=COLOR_RED, linestyle="--", linewidth=1.6)
    ax_i.text(x_max, 2.56, "2.50 A Trip", color=COLOR_RED, fontweight="bold", fontsize=9, ha="right", va="bottom", bbox=label_box)
    ax_i.axhline(1.15, color="#0D9488", linestyle=":", linewidth=1.3, alpha=0.85)
    ax_i.text(x_min, 1.20, "FLA 1.15A", color="#0D9488", fontsize=8.5, ha="left", va="bottom", bbox=label_box)
    max_curr = float(np.max(y_i)) if len(y_i) > 0 else 0.0
    i_max_disp = max(3.2, max_curr * 1.2)
    ax_i.set_ylim(0, i_max_disp)
    ax_i.set_yticks([0, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0])
    ax_i.set_yticklabels(["0 A", "0.5 A", "1 A", "1.5 A", "2 A", "2.5 A", "3 A"])

    # 5. Motor Speed RPM Card
    ax_rpm = fig.add_subplot(gs[2, 0])
    style_card(ax_rpm, "RPM · Induction Motor Speed (RPM)")
    y_rpm = df["rpm"].values if "rpm" in df.columns else df["f_out"].values * 29.0
    ax_rpm.plot(t, y_rpm, color=COLOR_RPM, linewidth=2.4, label="rpm")
    ax_rpm.fill_between(t, 0, y_rpm, color=COLOR_RPM, alpha=0.12)
    # Dynamic 4-Pole Synchronous Speed Ns = 120 * f / 4 = 30 * f
    avg_f = float(np.mean(y_f)) if len(y_f) > 0 and np.mean(y_f) > 1.0 else 50.0
    sync_rpm = avg_f * 30.0
    ax_rpm.axhline(sync_rpm, color="#D97706", linestyle="--", linewidth=1.6)
    ax_rpm.text(x_max, sync_rpm + (sync_rpm * 0.02), f"Sync {int(round(sync_rpm)):,} RPM", color="#D97706", fontweight="bold", fontsize=9, ha="right", va="bottom", bbox=label_box)
    rpm_max_disp = max(sync_rpm * 1.25, float(np.max(y_rpm)) * 1.15, 600.0)
    ax_rpm.set_ylim(0, rpm_max_disp)
    if rpm_max_disp <= 900:
        ax_rpm.set_yticks([0, 200, 400, 600, 800])
        ax_rpm.set_yticklabels(["0", "200", "400", "600", "800"])
    elif rpm_max_disp <= 1500:
        ax_rpm.set_yticks([0, 300, 600, 900, 1200, 1500])
        ax_rpm.set_yticklabels(["0", "300", "600", "900", "1,200", "1,500"])
    else:
        ax_rpm.set_yticks([0, 300, 600, 900, 1200, 1500, 1800])
        ax_rpm.set_yticklabels(["0", "300", "600", "900", "1,200", "1,500", "1,800"])

    # 6. Torque & Active Power Card (Dual Axis)
    ax_tp = fig.add_subplot(gs[2, 1])
    style_card(ax_tp, "τ & P · Mechanical Torque (%) & Active Power (kW)")
    y_tau = df["torque"].values if "torque" in df.columns else np.zeros(n)
    y_pow = df["power"].values if "power" in df.columns else np.zeros(n)
    ax_tp.plot(t, y_tau, color=COLOR_TORQUE, linewidth=2.4, label="Torque (%)")
    ax_tp.fill_between(t, 0, y_tau, color=COLOR_TORQUE, alpha=0.10)
    max_tau = max(15.0, float(np.max(y_tau)) * 1.25)
    ax_tp.set_ylim(0, max_tau)
    ax_tp.tick_params(axis="y", labelcolor=COLOR_TORQUE)

    # Secondary Y-Axis for Active Power (kW)
    ax_p = ax_tp.twinx()
    ax_p.plot(t, y_pow, color=COLOR_POWER, linewidth=2.0, linestyle="-", label="Power (kW)")
    ax_p.spines["top"].set_visible(False)
    ax_p.spines["left"].set_visible(False)
    ax_p.spines["bottom"].set_visible(False)
    ax_p.spines["right"].set_color("#CBD5E1")
    ax_p.yaxis.grid(False)
    max_pow = max(0.5, float(np.max(y_pow)) * 1.25)
    ax_p.set_ylim(0, max_pow)
    ax_p.tick_params(axis="y", which="both", length=0, colors=COLOR_POWER, labelsize=8.5)
    cur_tau = y_tau[-1] if len(y_tau) > 0 else 0.0
    cur_pow = y_pow[-1] if len(y_pow) > 0 else 0.0
    ax_tp.text(x_max, max_tau * 0.88, f"τ: {cur_tau:.1f}% · P: {cur_pow:.2f}kW", color=TEXT_MAIN, fontweight="bold", fontsize=8.5, ha="right", va="center", bbox=label_box)

    # Trip Event Point Marker (if tripped)
    if is_tripped:
        for ax, y_data in [(ax_f, y_f), (ax_v, y_v), (ax_vout, y_vout), (ax_i, y_i), (ax_rpm, y_rpm), (ax_tp, y_tau)]:
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
