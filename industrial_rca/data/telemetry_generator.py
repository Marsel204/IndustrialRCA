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
    """Baseline normal steady-state operation on Wecon VFD test bench."""
    return generate_vfd_dataset(scenario="nominal", duration_sec=duration_sec, seed=seed)


def generate_fault_scenario(duration_sec: int = SIMULATION_DURATION_SEC, seed: int = 202) -> TelemetryDataset:
    """Overfrequency excursion trip scenario on Wecon VFD test bench."""
    return generate_vfd_dataset(scenario="exp_err06", duration_sec=duration_sec, seed=seed)


def generate_vfd_dataset(
    scenario: str = "nominal",
    df_live: Optional[pd.DataFrame] = None,
    duration_sec: int = 300,
    seed: int = 42,
) -> TelemetryDataset:
    """
    Generates standardized VFD telemetry datasets for:
    - 'live_stream': Real-time HMI telemetry buffer from embedded TSDB / MQTT broker.
    - 'nominal' / 'exp_nominal': Healthy operation at 40 Hz, 182.0V DC, 1.15A, 1199 RPM.
    - 'exp_err02': Forced sudden deceleration via PLC On/Off button (D variable trigger) -> Err02 current spike.
    - 'exp_err06': Overfrequency excursion past 40 Hz toward 50 Hz -> DC bus breaches 195.0V ceiling -> Err06 trip.
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
            ("current", 0.0),
            ("v_dc", 182.0),
            ("v_out", 220.0),
            ("rpm", 1199.0),
            ("fault_code", 0),
        ]:
            if col not in df.columns:
                df[col] = default

        if "timestamp_sec" not in df.columns:
            df["timestamp_sec"] = np.arange(len(df))

        # Maintain legacy tag aliases for backward compatibility with existing tests/inspectors
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
            scenario_name="Wecon VFD Live Telemetry (Physical HMI / MQTT)",
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

    elif scenario in ("nominal", "exp_nominal"):
        t = np.arange(duration_sec)
        f_out = 40.0 + rng.normal(0, 0.05, duration_sec)
        v_dc = 182.0 + rng.normal(0, 0.4, duration_sec)
        current = 1.15 + rng.normal(0, 0.02, duration_sec)
        rpm = np.full(duration_sec, 1199.0) + rng.normal(0, 0.8, duration_sec)
        v_out = np.full(duration_sec, 220.0) + rng.normal(0, 0.2, duration_sec)
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
            "PT-30101": np.full(duration_sec, 2.40),
            "DPS-30101": np.full(duration_sec, 0.12),
            "VI-301-R": np.full(duration_sec, 1.80),
            "TI-301-DE": np.full(duration_sec, 48.5),
            "IT-30101": np.round(current * 60.0, 1),
        })

        t_wf_norm, sig_norm = generate_high_frequency_vibration(is_cavitating=False, seed=seed)
        t_wf_cav, sig_cav = generate_high_frequency_vibration(is_cavitating=False, seed=seed)

        return TelemetryDataset(
            scenario_name="Wecon VM VFD 40 Hz Nominal Baseline",
            df_1hz=df,
            metadata={
                "asset_id": VFD_EQUIPMENT_ID,
                "duration_sec": duration_sec,
                "condition": "HEALTHY",
                "anomaly_expected": False,
                "scenario": "exp_nominal",
                "fault_code": 0,
            },
            normal_waveform={"t": t_wf_norm, "signal": sig_norm},
            fault_waveform={"t": t_wf_cav, "signal": sig_cav},
        )

    elif scenario in ("exp_err02", "accel_overcurrent"):
        # Experiment 1: Forced sudden deceleration via PLC On/Off button (D variable trigger)
        t = np.arange(duration_sec)
        idx_trip = duration_sec - 15

        f_out = np.full(duration_sec, 40.0)
        v_dc = np.full(duration_sec, 182.0) + rng.normal(0, 0.3, duration_sec)
        current = np.full(duration_sec, 1.15) + rng.normal(0, 0.02, duration_sec)
        v_out = np.full(duration_sec, 220.0)
        rpm = np.full(duration_sec, 1199.0) + rng.normal(0, 0.5, duration_sec)
        fault_code = np.zeros(duration_sec, dtype=int)

        # Abrupt stop commanded at idx_trip: back-EMF kinetic surge
        current[idx_trip] = 3.85  # Spikes above 2.50A trip limit
        fault_code[idx_trip:] = 2   # Err02
        f_out[idx_trip:] = 0.0
        v_out[idx_trip:] = 0.0
        rpm[idx_trip:] = 0.0
        current[idx_trip + 1:] = 0.0

        df = pd.DataFrame({
            "timestamp_sec": t,
            "f_out": np.round(f_out, 2),
            "f_target": np.where(t >= idx_trip, 0.0, 40.0),
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
            scenario_name="Experiment 1: Forced Sudden Decel Trip (Err02)",
            df_1hz=df,
            metadata={
                "asset_id": VFD_EQUIPMENT_ID,
                "duration_sec": duration_sec,
                "condition": "HARDWARE_FAULT_TRIP",
                "anomaly_expected": True,
                "scenario": "exp_err02",
                "trip_timestamp_sec": idx_trip,
                "trip_time_str": "03:14:00 AM",
                "primary_trip_sensor": "current",
                "trip_value": 3.85,
                "trip_setpoint": 2.50,
                "fault_code": 2,
                "fault_description": "Forced Decel Overcurrent (Err02) - PLC On/Off stop button trigger without controlled ramp",
            },
            normal_waveform={"t": t_wf_norm, "signal": sig_norm},
            fault_waveform={"t": t_wf_cav, "signal": sig_cav},
        )

    elif scenario in ("exp_err06", "decel_overvoltage", "overfrequency"):
        # Experiment 2: Overfrequency excursion past 40 Hz toward 50 Hz breaching 195.0 V DC limit
        t = np.arange(duration_sec)
        idx_trip = duration_sec - 15
        idx_ramp = idx_trip - 20

        f_out = np.full(duration_sec, 40.0)
        v_dc = np.full(duration_sec, 182.0)
        current = np.full(duration_sec, 1.15)
        v_out = np.full(duration_sec, 220.0)
        rpm = np.full(duration_sec, 1199.0)
        fault_code = np.zeros(duration_sec, dtype=int)

        # Ramp frequency up past 40 Hz towards 50 Hz, DC bus climbs from 182V to 202.5V (breaching 195V)
        ramp_len = idx_trip - idx_ramp
        f_out[idx_ramp:idx_trip] = np.linspace(40.0, 48.5, ramp_len)
        v_dc[idx_ramp:idx_trip] = np.linspace(182.0, 202.5, ramp_len)
        current[idx_ramp:idx_trip] = np.linspace(1.15, 1.85, ramp_len)
        rpm[idx_ramp:idx_trip] = np.linspace(1199.0, 1420.0, ramp_len)

        # Trip state at idx_trip
        fault_code[idx_trip:] = 6  # Err06
        v_dc[idx_trip:] = np.linspace(202.5, 185.0, duration_sec - idx_trip)
        f_out[idx_trip:] = 0.0
        v_out[idx_trip:] = 0.0
        current[idx_trip:] = 0.0
        rpm[idx_trip:] = 0.0

        df = pd.DataFrame({
            "timestamp_sec": t,
            "f_out": np.round(f_out, 2),
            "f_target": np.where(t >= idx_trip, 0.0, np.where(t >= idx_ramp, 50.0, 40.0)),
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
            scenario_name="Experiment 2: Overfrequency Excursion Trip (Err06)",
            df_1hz=df,
            metadata={
                "asset_id": VFD_EQUIPMENT_ID,
                "duration_sec": duration_sec,
                "condition": "HARDWARE_FAULT_TRIP",
                "anomaly_expected": True,
                "scenario": "exp_err06",
                "trip_timestamp_sec": idx_trip,
                "trip_time_str": "03:14:00 AM",
                "primary_trip_sensor": "v_dc",
                "trip_value": 202.5,
                "trip_setpoint": 195.0,
                "fault_code": 6,
                "fault_description": "Overfrequency Overvoltage (Err06) - Frequency exceeded 40 Hz ceiling, DC bus breached 195.0 V",
            },
            normal_waveform={"t": t_wf_norm, "signal": sig_norm},
            fault_waveform={"t": t_wf_cav, "signal": sig_cav},
        )

    else:
        raise ValueError(f"Unknown VFD scenario: {scenario}. Expected live_stream, exp_err02, exp_err06, or nominal.")

