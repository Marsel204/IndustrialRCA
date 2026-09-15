"""
Synthetic Telemetry Generator for Industrial RCA System.
Generates 60 minutes of 1 Hz telemetry and high-frequency vibration waveforms
for Normal Baseline and Fault Scenarios (Boiler Feed Pump P-301A).
"""

from dataclasses import dataclass
from typing import Dict, Any, Tuple, Optional
import numpy as np
import pandas as pd

from industrial_rca.config import (
    EQUIPMENT_ID,
    VFD_EQUIPMENT_ID,
    SAMPLING_RATE_HZ,
    HIGH_FREQ_SAMPLING_RATE_HZ,
    SIMULATION_DURATION_SEC,
    SCENARIO_START_TIME,
    RUNNING_FREQUENCY_1X_HZ,
    RUNNING_FREQUENCY_2X_HZ,
)


import threading
from collections import OrderedDict

@dataclass
class TelemetryDataset:
    scenario_name: str
    df_1hz: pd.DataFrame
    metadata: Dict[str, Any]
    normal_waveform: Dict[str, np.ndarray]  # {"t": ..., "signal": ...}
    fault_waveform: Dict[str, np.ndarray]    # {"t": ..., "signal": ...}

    def get_tag_series(self, tag: str) -> np.ndarray:
        """Retrieve numpy array of 1 Hz floats for tag."""
        if tag in self.df_1hz.columns:
            return self.df_1hz[tag].to_numpy()
        raise KeyError(f"Sensor tag '{tag}' not found in dataset. Available: {list(self.df_1hz.columns)}")

    def get_timestamps(self) -> np.ndarray:
        """Retrieve seconds since start (0 to 3599)."""
        return self.df_1hz["timestamp_sec"].to_numpy()


class TelemetryStore:
    """In-memory registry decoupling raw TSDB datasets from serializable LangGraph state.
    Uses bounded LRU cache (OrderedDict, max 50 items) to prevent memory leaks."""
    _store: "OrderedDict[str, TelemetryDataset]" = OrderedDict()
    _lock = threading.RLock()
    MAX_ITEMS: int = 50

    @classmethod
    def register(cls, dataset: TelemetryDataset, custom_id: Optional[str] = None) -> str:
        ds_id = custom_id or f"ds_{dataset.scenario_name.lower().replace(' ', '_')}_{id(dataset)}"
        with cls._lock:
            if ds_id in cls._store:
                cls._store.move_to_end(ds_id)
            cls._store[ds_id] = dataset
            if len(cls._store) > cls.MAX_ITEMS:
                cls._store.popitem(last=False)
        return ds_id

    @classmethod
    def get(cls, dataset_id: str) -> TelemetryDataset:
        with cls._lock:
            if dataset_id not in cls._store:
                raise KeyError(f"Dataset '{dataset_id}' not found in TelemetryStore. Available: {list(cls._store.keys())}")
            cls._store.move_to_end(dataset_id)
            return cls._store[dataset_id]

    @classmethod
    def clear(cls) -> None:
        with cls._lock:
            cls._store.clear()


_VIBRATION_WAVEFORM_CACHE: "OrderedDict[Tuple[bool, float, float, int], Tuple[np.ndarray, np.ndarray]]" = OrderedDict()
_WAVEFORM_CACHE_LOCK = threading.Lock()
MAX_WAVEFORM_CACHE_ITEMS: int = 50


def generate_high_frequency_vibration(
    is_cavitating: bool = False,
    duration_sec: float = 1.0,
    sampling_rate_hz: float = HIGH_FREQ_SAMPLING_RATE_HZ,
    seed: int = 42,
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Synthesize high-frequency piezoelectric accelerometer vibration signal (in mm/s velocity).
    Results are cached in memory using a bounded LRU cache (max 50 items) to accelerate repeated queries.

    - Normal state: Prominent 1X (49.67 Hz) and small 2X (99.33 Hz) shaft speed peaks.
                    Broadband noise floor (2 kHz - 8 kHz) is minimal.
    - Cavitation state: Explosive broadband noise floor (2 kHz - 8 kHz) caused by
                        imploding vapor micro-bubbles, plus harmonic distortion.
    """
    cache_key = (is_cavitating, duration_sec, sampling_rate_hz, seed)
    with _WAVEFORM_CACHE_LOCK:
        if cache_key in _VIBRATION_WAVEFORM_CACHE:
            _VIBRATION_WAVEFORM_CACHE.move_to_end(cache_key)
            t_cached, sig_cached = _VIBRATION_WAVEFORM_CACHE[cache_key]
            return t_cached.copy(), sig_cached.copy()

    rng = np.random.default_rng(seed)
    n_samples = int(duration_sec * sampling_rate_hz)
    t = np.linspace(0.0, duration_sec, n_samples, endpoint=False)

    f1 = RUNNING_FREQUENCY_1X_HZ  # 49.67 Hz
    f2 = RUNNING_FREQUENCY_2X_HZ  # 99.33 Hz

    if not is_cavitating:
        # Healthy baseline: 1.8 mm/s overall RMS
        # 1X peak ~ 1.6 mm/s, 2X harmonic ~ 0.3 mm/s, broadband white noise ~ 0.15 mm/s
        signal = (
            1.6 * np.sqrt(2.0) * np.sin(2.0 * np.pi * f1 * t)
            + 0.3 * np.sqrt(2.0) * np.sin(2.0 * np.pi * f2 * t + 0.5)
            + rng.normal(0.0, 0.15, n_samples)
        )
    else:
        # Cavitating fault state: 11.4 mm/s overall RMS
        # Shaft 1X/2X modulation + intense broadband noise in 2-8 kHz band
        shaft_base = (
            2.8 * np.sqrt(2.0) * np.sin(2.0 * np.pi * f1 * t)
            + 1.2 * np.sqrt(2.0) * np.sin(2.0 * np.pi * f2 * t + 1.1)
        )
        # Broadband cavitation noise synthesized using multiple high-frequency acoustic modes (2kHz - 8kHz)
        # and filtered white noise
        raw_noise = rng.normal(0.0, 1.0, n_samples)
        # Bandpass frequency-domain weighting in 2000 - 8000 Hz band
        fft_noise = np.fft.rfft(raw_noise)
        freqs = np.fft.rfftfreq(n_samples, d=1.0 / sampling_rate_hz)
        cav_mask = (freqs >= 2000.0) & (freqs <= 8000.0)
        fft_noise[~cav_mask] *= 0.12  # Suppress outside cavitation band
        fft_noise[cav_mask] *= 3.8    # Amplify cavitation acoustic floor
        cavitation_broadband = np.fft.irfft(fft_noise, n=n_samples)

        # Scale broadband noise so total RMS matches ~11.4 mm/s
        signal = shaft_base + cavitation_broadband
        # Normalize to target RMS
        current_rms = np.sqrt(np.mean(signal**2))
        signal = signal * (11.4 / (current_rms + 1e-6))

    with _WAVEFORM_CACHE_LOCK:
        if cache_key in _VIBRATION_WAVEFORM_CACHE:
            _VIBRATION_WAVEFORM_CACHE.move_to_end(cache_key)
        _VIBRATION_WAVEFORM_CACHE[cache_key] = (t, signal)
        if len(_VIBRATION_WAVEFORM_CACHE) > MAX_WAVEFORM_CACHE_ITEMS:
            _VIBRATION_WAVEFORM_CACHE.popitem(last=False)

    return t.copy(), signal.copy()


def generate_normal_scenario(duration_sec: int = SIMULATION_DURATION_SEC, seed: int = 101) -> TelemetryDataset:
    """
    Synthesizes 60 minutes of 1 Hz normal operating baseline telemetry for Boiler Feed Pump P-301A.
    All parameters remain strictly within healthy OEM operational envelopes.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(0, duration_sec, 1)

    # PT-30101: Suction pressure steady at 2.40 bar +/- 0.05 bar
    pt_30101 = 2.40 + rng.normal(0.0, 0.015, duration_sec)
    pt_30101 = np.clip(pt_30101, 2.30, 2.50)

    # DPS-30101: Clean strainer Delta-P steady at 0.12 bar
    dps_30101 = 0.12 + rng.normal(0.0, 0.005, duration_sec)
    dps_30101 = np.clip(dps_30101, 0.10, 0.15)

    # VI-301-R: Radial vibration RMS steady at healthy 1.80 mm/s
    vi_301_r = 1.80 + rng.normal(0.0, 0.08, duration_sec)
    vi_301_r = np.clip(vi_301_r, 1.60, 2.10)

    # TI-301-DE: Drive-end bearing temperature steady at 48.5 deg C
    ti_301_de = 48.5 + rng.normal(0.0, 0.2, duration_sec)

    # IT-30101: Motor current steady at 84.2 A
    it_30101 = 84.2 + rng.normal(0.0, 0.4, duration_sec)

    df = pd.DataFrame({
        "timestamp_sec": t,
        "PT-30101": pt_30101,
        "DPS-30101": dps_30101,
        "VI-301-R": vi_301_r,
        "TI-301-DE": ti_301_de,
        "IT-30101": it_30101,
    })

    t_wf_norm, sig_norm = generate_high_frequency_vibration(is_cavitating=False, seed=seed)
    t_wf_cav, sig_cav = generate_high_frequency_vibration(is_cavitating=True, seed=seed)

    return TelemetryDataset(
        scenario_name="Baseline Normal Operation",
        df_1hz=df,
        metadata={
            "asset_id": EQUIPMENT_ID,
            "duration_sec": duration_sec,
            "condition": "HEALTHY",
            "anomaly_expected": False,
        },
        normal_waveform={"t": t_wf_norm, "signal": sig_norm},
        fault_waveform={"t": t_wf_cav, "signal": sig_cav},
    )


def generate_fault_scenario(duration_sec: int = SIMULATION_DURATION_SEC, seed: int = 202) -> TelemetryDataset:
    """
    Synthesizes 60 minutes of 1 Hz fault scenario telemetry:
    - T0 to T30m (0 - 1800s): Normal baseline
    - T30m to T50m (1800 - 3000s): Marine fouling in STR-301A. Delta-P ramps 0.12 -> 1.85 bar.
    - T45m (2700s): Suction pressure plunges below NPSHr (1.2 bar) to 0.58 bar.
    - T48m (2880s): Impeller cavitates. Vibration spikes to 11.4 mm/s RMS, broadband 2-8 kHz noise explosion,
                    motor current oscillates +/- 22%.
    - T55m (3300s): Drive-end bearing temp TI-301-DE elevates past trip limit (92.3 C), tripping DCS at 03:14 AM.
    - T55m to T60m (3300 - 3600s): Post-trip shutdown / coastdown.
    """
    rng = np.random.default_rng(seed)
    t = np.arange(0, duration_sec, 1)

    # Initialize with normal baseline arrays
    pt_30101 = np.full(duration_sec, 2.40) + rng.normal(0.0, 0.015, duration_sec)
    dps_30101 = np.full(duration_sec, 0.12) + rng.normal(0.0, 0.005, duration_sec)
    vi_301_r = np.full(duration_sec, 1.80) + rng.normal(0.0, 0.08, duration_sec)
    ti_301_de = np.full(duration_sec, 48.5) + rng.normal(0.0, 0.15, duration_sec)
    it_30101 = np.full(duration_sec, 84.2) + rng.normal(0.0, 0.4, duration_sec)

    # 1. T30m to T50m (1800s to 3000s): Strainer Fouling Delta-P Ramp
    # Ramps smoothly from 0.12 bar to 1.85 bar
    idx_30 = 1800
    idx_50 = 3000
    ramp_steps = idx_50 - idx_30
    dp_ramp = np.linspace(0.12, 1.85, ramp_steps) + rng.normal(0.0, 0.02, ramp_steps)
    dps_30101[idx_30:idx_50] = dp_ramp
    # After T50m, Delta-P remains severely choked around 1.85 bar until trip
    idx_55 = 3300
    dps_30101[idx_50:idx_55] = 1.85 + rng.normal(0.0, 0.03, idx_55 - idx_50)
    # Post trip (pump off, flow stops, dP collapses)
    dps_30101[idx_55:] = 0.02 + rng.normal(0.0, 0.005, duration_sec - idx_55)

    # 2. T45m (2700s): Suction Pressure Plunges below NPSHr (1.2 bar)
    # Gradual suction depression from T35m (2100s), sharp drop below NPSHr at 2700s down to 0.58 bar
    idx_35 = 2100
    idx_45 = 2700
    # Between 2100s and 2700s, suction drops from 2.38 bar to 1.20 bar
    pt_30101[idx_35:idx_45] = np.linspace(2.38, 1.20, idx_45 - idx_35) + rng.normal(0.0, 0.02, idx_45 - idx_35)
    # From 2700s to 2880s (T48m), drops further to 0.58 bar (deep starvation)
    idx_48 = 2880
    pt_30101[idx_45:idx_48] = np.linspace(1.20, 0.58, idx_48 - idx_45) + rng.normal(0.0, 0.03, idx_48 - idx_45)
    # Stays severely depressed (0.58 bar) until trip at 3300s
    pt_30101[idx_48:idx_55] = 0.58 + rng.normal(0.0, 0.02, idx_55 - idx_48)
    # Post trip, suction equalizes back toward static deaerator head (~2.4 bar)
    post_trip_len = duration_sec - idx_55
    pt_30101[idx_55:] = np.linspace(0.60, 2.35, post_trip_len) + rng.normal(0.0, 0.02, post_trip_len)

    # 3. T48m (2880s): Impeller Cavitates -> Vibration spikes to 11.4 mm/s RMS
    # Prior to cavitation, slight elevation due to suction turbulence (1.8 -> 3.2 mm/s between 2700 and 2880)
    vi_301_r[idx_45:idx_48] = np.linspace(1.8, 3.2, idx_48 - idx_45) + rng.normal(0.0, 0.15, idx_48 - idx_45)
    # Cavitation erupts at 2880s: sudden spike to 11.4 mm/s RMS with erratic pulsations
    cav_len = idx_55 - idx_48
    vi_301_r[idx_48:idx_55] = 11.4 + rng.normal(0.0, 0.9, cav_len)
    # Post trip: vibration coasts down immediately to near 0 (0.1 mm/s)
    vi_301_r[idx_55:] = 0.15 * np.exp(-np.linspace(0, 5, post_trip_len)) + rng.normal(0.0, 0.02, post_trip_len)

    # 4. Motor Current: T48m (2880s) to T55m (3300s) fluctuates by +/- 22% due to unstable two-phase fluid load
    fluctuation_profile = np.sin(np.linspace(0, 40 * np.pi, cav_len)) * 18.5 + rng.normal(0.0, 3.0, cav_len)
    it_30101[idx_48:idx_55] = 84.2 + fluctuation_profile
    # Post trip: circuit breaker trips, current drops to 0.0 A
    it_30101[idx_55:] = 0.0

    # 5. Bearing Temp TI-301-DE: Heat generation accelerates from T48m (high friction/vibration)
    # Ramps from 48.5 C up past trip limit (90.0 C) reaching 92.3 C at T55m (3300s)
    ti_301_de[idx_48:idx_55] = np.linspace(48.5, 92.3, cav_len) + rng.normal(0.0, 0.2, cav_len)
    # Post trip: slow thermal cooling
    ti_301_de[idx_55:] = 92.3 - np.linspace(0, 14.0, post_trip_len) + rng.normal(0.0, 0.2, post_trip_len)

    df = pd.DataFrame({
        "timestamp_sec": t,
        "PT-30101": pt_30101,
        "DPS-30101": dps_30101,
        "VI-301-R": vi_301_r,
        "TI-301-DE": ti_301_de,
        "IT-30101": it_30101,
    })

    t_wf_norm, sig_norm = generate_high_frequency_vibration(is_cavitating=False, seed=seed)
    t_wf_cav, sig_cav = generate_high_frequency_vibration(is_cavitating=True, seed=seed)

    return TelemetryDataset(
        scenario_name="Strainer Clogging Induced Cavitation Trip",
        df_1hz=df,
        metadata={
            "asset_id": EQUIPMENT_ID,
            "duration_sec": duration_sec,
            "condition": "FAULT_TRIP",
            "anomaly_expected": True,
            "trip_timestamp_sec": idx_55,
            "trip_time_str": "03:14:00 AM",
            "primary_trip_sensor": "TI-301-DE",
            "trip_value": 92.3,
            "trip_setpoint": 90.0,
        },
        normal_waveform={"t": t_wf_norm, "signal": sig_norm},
        fault_waveform={"t": t_wf_cav, "signal": sig_cav},
    )


def generate_vfd_dataset(
    scenario: str = "nominal",
    df_live: Optional[pd.DataFrame] = None,
    duration_sec: int = 300,
    seed: int = 42,
) -> TelemetryDataset:
    """
    Generates standardized VFD telemetry datasets for:
    - 'nominal': Healthy operation at 40 Hz, 312V DC, 1.35A, 1160 RPM.
    - 'overfrequency': Pushed past 40 Hz limit up to 50 Hz with current elevation.
    - 'decel_overvoltage': Rapid deceleration down to 0 without braking resistor -> Err06 (>700V DC surge).
    - 'live_stream': Ingests live InfluxDB / buffer DataFrame (or generates live stream fallback).
    Maps all measurements to standard RCA columns:
    v_dc, current, f_out, rpm, fault_code, PT-30101, DPS-30101, VI-301-R, TI-301-DE, IT-30101.
    """
    rng = np.random.default_rng(seed)

    if scenario == "live_stream":
        if df_live is not None:
            df = df_live.copy()
        else:
            from industrial_rca.tools.influx_tool import InfluxDBTelemetryTool
            df = InfluxDBTelemetryTool().get_live_telemetry(limit=duration_sec)

        # Standardize required columns
        for col, default in [
            ("f_out", 40.0),
            ("f_target", 40.0),
            ("current", 1.35),
            ("v_dc", 312.0),
            ("v_out", 220.0),
            ("rpm", 1160.0),
            ("fault_code", 0),
        ]:
            if col not in df.columns:
                df[col] = default

        if "timestamp_sec" not in df.columns:
            df["timestamp_sec"] = np.arange(len(df))

        # Standard pump & motor baseline tags remain healthy/nominal for VFD operations
        if "PT-30101" not in df.columns:
            df["PT-30101"] = 2.40
        if "DPS-30101" not in df.columns:
            df["DPS-30101"] = 0.12
        if "VI-301-R" not in df.columns:
            df["VI-301-R"] = 1.80
        if "TI-301-DE" not in df.columns:
            df["TI-301-DE"] = 48.50
        if "IT-30101" not in df.columns:
            df["IT-30101"] = df["current"] * 60.0

        t_wf_norm, sig_norm = generate_high_frequency_vibration(is_cavitating=False, seed=seed)
        t_wf_cav, sig_cav = generate_high_frequency_vibration(is_cavitating=False, seed=seed)

        has_trip = bool((df["fault_code"].max() or 0) > 0)

        return TelemetryDataset(
            scenario_name="Wecon VFD Live Telemetry (Node-RED / InfluxDB)",
            df_1hz=df,
            metadata={
                "asset_id": VFD_EQUIPMENT_ID,
                "duration_sec": len(df),
                "condition": "HARDWARE_FAULT_TRIP" if has_trip else "LIVE_STREAM",
                "anomaly_expected": bool(has_trip),
                "scenario": "live_stream",
                "fault_code": int(df["fault_code"].max()),
            },
            normal_waveform={"t": t_wf_norm, "signal": sig_norm},
            fault_waveform={"t": t_wf_cav, "signal": sig_cav},
        )

    elif scenario == "nominal":
        t = np.arange(duration_sec)
        f_out = 40.0 + rng.normal(0, 0.05, duration_sec)
        v_dc = 312.0 + rng.normal(0, 0.5, duration_sec)
        current = 1.35 + rng.normal(0, 0.02, duration_sec)
        rpm = f_out * 29.0 + rng.normal(0, 1.0, duration_sec)
        v_out = np.full(duration_sec, 220.0) + rng.normal(0, 0.3, duration_sec)
        fault_code = np.zeros(duration_sec, dtype=int)

        df = pd.DataFrame({
            "timestamp_sec": t,
            "f_out": np.round(f_out, 2),
            "f_target": np.full(duration_sec, 40.0),
            "v_dc": np.round(v_dc, 1),
            "v_out": np.round(v_out, 1),
            "current": np.round(current, 2),
            "rpm": np.round(rpm, 1),
            "fault_code": fault_code,
            "PT-30101": np.round(2.40 + rng.normal(0, 0.01, duration_sec), 2),
            "DPS-30101": np.round(0.12 + rng.normal(0, 0.005, duration_sec), 2),
            "VI-301-R": np.round(1.80 + rng.normal(0, 0.05, duration_sec), 2),
            "TI-301-DE": np.round(48.5 + rng.normal(0, 0.1, duration_sec), 1),
            "IT-30101": np.round(current * 60.0, 1),
        })

        t_wf_norm, sig_norm = generate_high_frequency_vibration(is_cavitating=False, seed=seed)
        t_wf_cav, sig_cav = generate_high_frequency_vibration(is_cavitating=False, seed=seed)

        return TelemetryDataset(
            scenario_name="WECON VM VFD Nominal Baseline",
            df_1hz=df,
            metadata={
                "asset_id": VFD_EQUIPMENT_ID,
                "duration_sec": duration_sec,
                "condition": "HEALTHY",
                "anomaly_expected": False,
                "scenario": "nominal",
                "fault_code": 0,
            },
            normal_waveform={"t": t_wf_norm, "signal": sig_norm},
            fault_waveform={"t": t_wf_cav, "signal": sig_cav},
        )

    elif scenario == "overfrequency":
        t = np.arange(duration_sec)
        idx_ramp = int(duration_sec * 0.5)
        f_out = np.full(duration_sec, 40.0)
        f_out[idx_ramp:] = np.linspace(40.0, 48.5, duration_sec - idx_ramp)
        f_out += rng.normal(0, 0.05, duration_sec)

        current = np.full(duration_sec, 1.35)
        current[idx_ramp:] = np.linspace(1.35, 2.15, duration_sec - idx_ramp)
        current += rng.normal(0, 0.03, duration_sec)

        v_dc = 312.0 + rng.normal(0, 0.8, duration_sec)
        rpm = f_out * 29.0 + rng.normal(0, 1.0, duration_sec)
        v_out = np.full(duration_sec, 220.0)
        fault_code = np.zeros(duration_sec, dtype=int)

        df = pd.DataFrame({
            "timestamp_sec": t,
            "f_out": np.round(f_out, 2),
            "f_target": np.full(duration_sec, 48.5),
            "v_dc": np.round(v_dc, 1),
            "v_out": np.round(v_out, 1),
            "current": np.round(current, 2),
            "rpm": np.round(rpm, 1),
            "fault_code": fault_code,
            "PT-30101": np.full(duration_sec, 2.40),
            "DPS-30101": np.full(duration_sec, 0.12),
            "VI-301-R": np.where(f_out > 42.0, 3.80, 1.80),
            "TI-301-DE": np.where(current > 2.0, 68.5, 48.5),
            "IT-30101": np.round(current * 60.0, 1),
        })

        t_wf_norm, sig_norm = generate_high_frequency_vibration(is_cavitating=False, seed=seed)
        t_wf_cav, sig_cav = generate_high_frequency_vibration(is_cavitating=False, seed=seed)

        return TelemetryDataset(
            scenario_name="WECON VM VFD Overfrequency Warning",
            df_1hz=df,
            metadata={
                "asset_id": VFD_EQUIPMENT_ID,
                "duration_sec": duration_sec,
                "condition": "WARNING_OVERFREQUENCY",
                "anomaly_expected": True,
                "scenario": "overfrequency",
                "primary_trip_sensor": "f_out",
                "trip_value": 48.5,
                "trip_setpoint": 40.0,
                "fault_code": 0,
            },
            normal_waveform={"t": t_wf_norm, "signal": sig_norm},
            fault_waveform={"t": t_wf_cav, "signal": sig_cav},
        )

    elif scenario == "decel_overvoltage":
        t = np.arange(duration_sec)
        idx_trip = duration_sec - 15
        idx_decel = idx_trip - 5

        f_out = np.full(duration_sec, 40.0)
        v_dc = np.full(duration_sec, 312.0)
        current = np.full(duration_sec, 1.35)
        v_out = np.full(duration_sec, 220.0)
        fault_code = np.zeros(duration_sec, dtype=int)

        # Decel ramp 5s
        decel_steps = idx_trip - idx_decel
        f_out[idx_decel:idx_trip] = np.linspace(40.0, 0.0, decel_steps)
        v_dc[idx_decel:idx_trip] = np.linspace(312.0, 748.5, decel_steps)
        current[idx_decel:idx_trip] = np.linspace(1.35, 3.80, decel_steps)
        v_out[idx_decel:idx_trip] = np.linspace(220.0, 140.0, decel_steps)

        # Trip state
        f_out[idx_trip:] = 0.0
        v_dc[idx_trip:] = 748.5 - np.linspace(0, 45.0, duration_sec - idx_trip)
        current[idx_trip:] = 0.0
        v_out[idx_trip:] = 0.0
        fault_code[idx_trip:] = 6

        rpm = f_out * 29.0

        df = pd.DataFrame({
            "timestamp_sec": t,
            "f_out": np.round(f_out, 2),
            "f_target": np.where(t >= idx_decel, 0.0, 40.0),
            "v_dc": np.round(v_dc, 1),
            "v_out": np.round(v_out, 1),
            "current": np.round(current, 2),
            "rpm": np.round(rpm, 1),
            "fault_code": fault_code,
            "PT-30101": np.full(duration_sec, 2.40),
            "DPS-30101": np.full(duration_sec, 0.12),
            "VI-301-R": np.full(duration_sec, 1.80),
            "TI-301-DE": np.full(duration_sec, 48.5),
            "IT-30101": np.round(current * 60.0, 1),
        })

        t_wf_norm, sig_norm = generate_high_frequency_vibration(is_cavitating=False, seed=seed)
        t_wf_cav, sig_cav = generate_high_frequency_vibration(is_cavitating=False, seed=seed)

        return TelemetryDataset(
            scenario_name="WECON VM VFD Decel Overvoltage Trip (Err06)",
            df_1hz=df,
            metadata={
                "asset_id": VFD_EQUIPMENT_ID,
                "duration_sec": duration_sec,
                "condition": "HARDWARE_FAULT_TRIP",
                "anomaly_expected": True,
                "scenario": "decel_overvoltage",
                "trip_timestamp_sec": idx_trip,
                "trip_time_str": "03:14:00 AM",
                "primary_trip_sensor": "v_dc",
                "trip_value": 748.5,
                "trip_setpoint": 700.0,
                "fault_code": 6,
                "fault_description": "Deceleration Overvoltage (Err06) - DC link regeneration surge without brake resistor",
            },
            normal_waveform={"t": t_wf_norm, "signal": sig_norm},
            fault_waveform={"t": t_wf_cav, "signal": sig_cav},
        )

    else:
        raise ValueError(f"Unknown VFD scenario: {scenario}. Expected nominal, overfrequency, decel_overvoltage, or live_stream.")
