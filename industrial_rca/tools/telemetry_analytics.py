"""
Deterministic Telemetry Analytics & Feature Extraction Module.
Ensures LLMs NEVER ingest raw time-series arrays.
Provides:
1. In-memory thread-safe TelemetryCache
2. Statistical Profiling (mean, min, max, slope, variance, CV)
3. Two-window sliding change-point detection
4. FFT spectral analysis (1X/2X shaft speed peaks vs broadband cavitation floor)
"""

import threading
from typing import Dict, Any, List, Optional, Tuple, Union
import numpy as np

from industrial_rca.config import (
    RUNNING_FREQUENCY_1X_HZ,
    RUNNING_FREQUENCY_2X_HZ,
    CAVITATION_BROADBAND_BAND_HZ,
    CAVITATION_ENERGY_RATIO_ALARM,
    HIGH_FREQ_SAMPLING_RATE_HZ,
    CACHE_MAX_ENTRIES,
)
from industrial_rca.data.telemetry_generator import TelemetryDataset, TelemetryStore


class TelemetryCache:
    """Thread-safe in-memory cache to prevent redundant computations across parallel graph branches."""

    def __init__(self, max_entries: int = CACHE_MAX_ENTRIES):
        self._cache: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self.hits = 0
        self.misses = 0

    def _build_key(self, dataset_id: str, tag: str, start_idx: int, end_idx: int, analysis_type: str, extra: str = "") -> str:
        return f"{dataset_id}:{tag}:{start_idx}:{end_idx}:{analysis_type}:{extra}"

    def get(self, dataset_id: str, tag: str, start_idx: int, end_idx: int, analysis_type: str, extra: str = "") -> Optional[Any]:
        key = self._build_key(dataset_id, tag, start_idx, end_idx, analysis_type, extra)
        with self._lock:
            if key in self._cache:
                self.hits += 1
                return self._cache[key]
            self.misses += 1
            return None

    def set(self, dataset_id: str, tag: str, start_idx: int, end_idx: int, analysis_type: str, value: Any, extra: str = "") -> None:
        key = self._build_key(dataset_id, tag, start_idx, end_idx, analysis_type, extra)
        with self._lock:
            if len(self._cache) >= self._max_entries:
                # Evict oldest entry
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            self._cache[key] = value

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total = self.hits + self.misses
            hit_rate = (self.hits / total * 100.0) if total > 0 else 0.0
            return {
                "hits": self.hits,
                "misses": self.misses,
                "total_queries": total,
                "hit_rate_pct": round(hit_rate, 2),
                "cached_items": len(self._cache),
            }

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()
            self.hits = 0
            self.misses = 0


# Global singleton cache
GLOBAL_TELEMETRY_CACHE = TelemetryCache()


class StatisticalProfiler:
    """Pure Python statistical profiler for deterministic time-series feature extraction."""

    @staticmethod
    def profile(values: np.ndarray) -> Dict[str, float]:
        if len(values) == 0:
            return {
                "mean": 0.0, "std": 0.0, "variance": 0.0,
                "min": 0.0, "max": 0.0, "p95": 0.0,
                "slope": 0.0, "delta": 0.0, "cv": 0.0,
            }

        n = len(values)
        mean_val = float(np.mean(values))
        std_val = float(np.std(values))
        var_val = float(np.var(values))
        min_val = float(np.min(values))
        max_val = float(np.max(values))
        p95_val = float(np.percentile(values, 95))
        delta_val = float(values[-1] - values[0])

        # Slope computation via linear regression: y = m*x + c
        if n > 1:
            x = np.arange(n, dtype=float)
            x_mean = float(np.mean(x))
            denom = float(np.sum((x - x_mean) ** 2))
            if denom > 1e-12:
                slope_val = float(np.sum((x - x_mean) * (values - mean_val)) / denom)
            else:
                slope_val = 0.0
        else:
            slope_val = 0.0

        cv_val = float(std_val / (abs(mean_val) + 1e-9))

        return {
            "mean": round(mean_val, 4),
            "std": round(std_val, 4),
            "variance": round(var_val, 6),
            "min": round(min_val, 4),
            "max": round(max_val, 4),
            "p95": round(p95_val, 4),
            "slope": round(slope_val, 6),
            "delta": round(delta_val, 4),
            "cv": round(cv_val, 4),
        }


class ChangePointDetector:
    """Two-window sliding variance/mean divergence change-point detector."""

    @staticmethod
    def detect_change_points(
        values: np.ndarray,
        window_sec: int = 120,
        step_sec: int = 10,
        threshold_score: float = 3.5,
        min_relative_shift: float = 0.12,
    ) -> List[Dict[str, Any]]:
        """
        Sliding two-window test:
        Compares window W1: [t - W, t] against window W2: [t, t + W].
        Calculates normalized mean divergence and variance ratio.
        Filters out sub-threshold sensor noise by enforcing min_relative_shift.
        """
        n = len(values)
        change_points = []
        if n < 2 * window_sec:
            return change_points

        scores = []
        timestamps = []

        for t in range(window_sec, n - window_sec, step_sec):
            w_left = values[t - window_sec : t]
            w_right = values[t : t + window_sec]

            m_left, m_right = np.mean(w_left), np.mean(w_right)
            s_left, s_right = np.std(w_left), np.std(w_right)

            # Pooled standard error
            pooled_se = np.sqrt((s_left**2 / window_sec) + (s_right**2 / window_sec) + 1e-6)
            t_stat = abs(m_right - m_left) / pooled_se

            # Variance ratio
            var_ratio = max(s_right**2, s_left**2) / (min(s_right**2, s_left**2) + 1e-6)
            var_score = np.log1p(var_ratio)

            combined_score = float(t_stat + 1.5 * var_score)
            scores.append(combined_score)
            timestamps.append(t)

        if not scores:
            return change_points

        # Peak detection above threshold
        scores = np.array(scores)
        peaks = []
        for i in range(1, len(scores) - 1):
            if scores[i] >= threshold_score and scores[i] > scores[i - 1] and scores[i] > scores[i + 1]:
                peaks.append(i)

        for p_idx in peaks:
            t_sec = timestamps[p_idx]
            pre_w = values[max(0, t_sec - window_sec) : t_sec]
            post_w = values[t_sec : min(n, t_sec + window_sec)]
            pre_m = float(np.mean(pre_w))
            post_m = float(np.mean(post_w))
            shift = float(post_m - pre_m)
            rel_shift = abs(shift) / (abs(pre_m) + 1e-6)

            # Ignore noise shifts below engineering significance threshold (e.g. <12%)
            if rel_shift < min_relative_shift:
                continue

            change_points.append({
                "timestamp_sec": int(t_sec),
                "detector_score": round(float(scores[p_idx]), 2),
                "pre_change_mean": round(pre_m, 4),
                "post_change_mean": round(post_m, 4),
                "magnitude_shift": round(shift, 4),
                "relative_shift_pct": round(rel_shift * 100.0, 1),
                "confidence_pct": min(100.0, round(float(scores[p_idx]) * 12.0, 1)),
            })

        return change_points


class SpectralAnalyzer:
    """
    FFT Spectral Analysis tool for vibration telemetry.
    Differentiates discrete shaft harmonics (1X, 2X) from high-frequency broadband cavitation floor.
    """

    @staticmethod
    def analyze_spectrum(
        signal: np.ndarray,
        sampling_rate_hz: float = HIGH_FREQ_SAMPLING_RATE_HZ,
        running_freq_hz: float = RUNNING_FREQUENCY_1X_HZ,
    ) -> Dict[str, Any]:
        """
        Performs discrete FFT and energy partition analysis on vibration velocity waveform.
        """
        n_samples = len(signal)
        if n_samples == 0:
            return {
                "overall_rms": 0.0,
                "peak_1x_amp": 0.0,
                "peak_2x_amp": 0.0,
                "broadband_cavitation_ratio": 0.0,
                "cavitation_detected": False,
                "diagnosis": "No signal provided",
            }

        # Overall RMS
        overall_rms = float(np.sqrt(np.mean(signal**2)))

        # FFT
        fft_vals = np.fft.rfft(signal)
        freqs = np.fft.rfftfreq(n_samples, d=1.0 / sampling_rate_hz)
        # Power Spectral Density magnitude
        mag = (np.abs(fft_vals) * 2.0 / n_samples)
        total_energy = float(np.sum(mag**2) + 1e-9)

        # 1X peak extraction (tolerance +/- 2.5 Hz around 49.67 Hz)
        f1 = running_freq_hz
        f2 = RUNNING_FREQUENCY_2X_HZ
        mask_1x = (freqs >= (f1 - 2.5)) & (freqs <= (f1 + 2.5))
        amp_1x = float(np.max(mag[mask_1x])) if np.any(mask_1x) else 0.0

        # 2X peak extraction
        mask_2x = (freqs >= (f2 - 3.0)) & (freqs <= (f2 + 3.0))
        amp_2x = float(np.max(mag[mask_2x])) if np.any(mask_2x) else 0.0

        # High-frequency broadband cavitation band (2 kHz to 8 kHz)
        cav_low, cav_high = CAVITATION_BROADBAND_BAND_HZ
        mask_cav = (freqs >= cav_low) & (freqs <= cav_high)
        cav_energy = float(np.sum(mag[mask_cav] ** 2)) if np.any(mask_cav) else 0.0

        broadband_ratio = float(cav_energy / total_energy)
        cavitation_detected = bool(
            broadband_ratio >= CAVITATION_ENERGY_RATIO_ALARM and overall_rms >= 4.5
        )

        if cavitation_detected:
            diagnosis = (
                f"Severe cavitation confirmed: broadband energy ratio is {broadband_ratio*100:.1f}% "
                f"(alarm > {CAVITATION_ENERGY_RATIO_ALARM*100:.0f}%) in 2.0-8.0 kHz band. "
                f"High-frequency vapor micro-implosions dominate running speed harmonics (1X: {amp_1x:.2f} mm/s)."
            )
        elif amp_1x > 3.0 and amp_1x / (amp_2x + 1e-3) > 3.0:
            diagnosis = (
                f"Shaft unbalance dominant: discrete 1X running peak is {amp_1x:.2f} mm/s at {f1:.1f} Hz. "
                f"Broadband noise floor is low ({broadband_ratio*100:.1f}%)."
            )
        elif amp_2x > 2.0:
            diagnosis = (
                f"Shaft misalignment dominant: discrete 2X harmonic is {amp_2x:.2f} mm/s at {f2:.1f} Hz."
            )
        else:
            diagnosis = (
                f"Healthy baseline spectrum: overall RMS is {overall_rms:.2f} mm/s. Discrete 1X peak {amp_1x:.2f} mm/s, "
                f"broadband floor minimal ({broadband_ratio*100:.1f}%)."
            )

        return {
            "overall_rms": round(overall_rms, 3),
            "fundamental_1x_hz": round(f1, 2),
            "peak_1x_amplitude_mms": round(amp_1x, 3),
            "harmonic_2x_hz": round(f2, 2),
            "peak_2x_amplitude_mms": round(amp_2x, 3),
            "cavitation_band_hz": f"{int(cav_low)}-{int(cav_high)} Hz",
            "broadband_cavitation_ratio": round(broadband_ratio, 4),
            "broadband_cavitation_ratio_pct": round(broadband_ratio * 100.0, 1),
            "cavitation_detected": cavitation_detected,
            "diagnosis": diagnosis,
        }


class TelemetryAnalyticsTool:
    """
    High-level facade used by LangGraph nodes.
    Interacts with dataset, leverages TelemetryCache, and delivers pure structured feature dictionaries.
    """

    def __init__(self, cache: Optional[TelemetryCache] = None):
        self.cache = cache or GLOBAL_TELEMETRY_CACHE
        self.profiler = StatisticalProfiler()
        self.change_detector = ChangePointDetector()
        self.spectral_analyzer = SpectralAnalyzer()

    def _resolve_dataset_and_id(self, dataset: Union[TelemetryDataset, str]) -> Tuple[TelemetryDataset, str]:
        if isinstance(dataset, str):
            return TelemetryStore.get(dataset), dataset
        ds_id = getattr(dataset, "_registered_id", None) or f"ds_{id(dataset)}"
        return dataset, ds_id

    def profile_tag(
        self,
        dataset: Union[TelemetryDataset, str],
        tag: str,
        start_sec: int = 0,
        end_sec: int = 3600,
    ) -> Dict[str, Any]:
        """Compute or retrieve cached statistical summary for a sensor tag."""
        ds, ds_id = self._resolve_dataset_and_id(dataset)
        cached = self.cache.get(ds_id, tag, start_sec, end_sec, "profile")
        if cached is not None:
            return cached

        series = ds.get_tag_series(tag)[start_sec:end_sec]
        result = self.profiler.profile(series)
        result["tag"] = tag
        result["start_sec"] = start_sec
        result["end_sec"] = end_sec
        result["sample_count"] = len(series)

        self.cache.set(ds_id, tag, start_sec, end_sec, "profile", result)
        return result

    def detect_tag_changepoints(
        self,
        dataset: Union[TelemetryDataset, str],
        tag: str,
        start_sec: int = 0,
        end_sec: int = 3600,
        window_sec: int = 120,
        threshold_score: float = 3.5,
    ) -> List[Dict[str, Any]]:
        """Detect change points for a tag across the given interval."""
        ds, ds_id = self._resolve_dataset_and_id(dataset)
        cached = self.cache.get(ds_id, tag, start_sec, end_sec, "changepoints", f"{window_sec}:{threshold_score}")
        if cached is not None:
            return cached

        series = ds.get_tag_series(tag)[start_sec:end_sec]
        cps = self.change_detector.detect_change_points(
            series, window_sec=window_sec, threshold_score=threshold_score
        )
        # Adjust timestamps relative to start_sec
        for cp in cps:
            cp["absolute_sec"] = start_sec + cp["timestamp_sec"]
            cp["tag"] = tag

        self.cache.set(ds_id, tag, start_sec, end_sec, "changepoints", cps, f"{window_sec}:{threshold_score}")
        return cps

    def analyze_vibration_waveform(
        self,
        dataset: Union[TelemetryDataset, str],
        is_cavitation_state: bool,
    ) -> Dict[str, Any]:
        """Run FFT spectral decomposition on vibration sample waveform."""
        ds, ds_id = self._resolve_dataset_and_id(dataset)
        wf_data = ds.fault_waveform if is_cavitation_state else ds.normal_waveform
        sig = wf_data["signal"]
        tag = "VI-301-R_FFT"
        cached = self.cache.get(ds_id, tag, 0, len(sig), "fft", str(is_cavitation_state))
        if cached is not None:
            return cached

        result = self.spectral_analyzer.analyze_spectrum(sig)
        result["is_cavitation_sample"] = is_cavitation_state
        self.cache.set(ds_id, tag, 0, len(sig), "fft", result, str(is_cavitation_state))
        return result

    def get_cache_stats(self) -> Dict[str, Any]:
        return self.cache.get_stats()
