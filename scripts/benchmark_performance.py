"""
Comprehensive Performance Benchmarking & Evaluation Suite for IndustrialRCA.
Measures:
1. Analytics Engine (Vectorized Change-Point Detection, 20 kHz FFT Spectral Analysis, Statistical Profiler)
2. Embedded TSDB (Ingestion throughput, In-memory ring buffer vs SQLite query latency)
3. FastAPI Endpoints (Throughput, P50/P90/P95/P99 latency across core REST endpoints)
4. LangGraph 7-Step RCA Pipeline (Execution latency across multiple fault scenarios)
5. Cache & Concurrency (Multi-threaded cache hits, lock contention, LRU eviction)
"""

import os
import sys
import time
import json
import statistics
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, Any, List

import numpy as np
from starlette.testclient import TestClient

# Ensure repository root is on sys.path
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

from industrial_rca.tools.telemetry_analytics import (
    StatisticalProfiler,
    ChangePointDetector,
    SpectralAnalyzer,
    TelemetryCache,
)
from industrial_rca.data.embedded_tsdb import EmbeddedTSDB
from industrial_rca.api import api_app
from industrial_rca.data.telemetry_generator import TelemetryStore


def compute_metrics(latencies_ms: List[float]) -> Dict[str, float]:
    """Calculates statistical percentiles from latency list."""
    if not latencies_ms:
        return {}
    s = sorted(latencies_ms)
    n = len(s)
    return {
        "count": n,
        "mean_ms": round(statistics.mean(s), 3),
        "std_ms": round(statistics.stdev(s), 3) if n > 1 else 0.0,
        "min_ms": round(s[0], 3),
        "p50_ms": round(statistics.median(s), 3),
        "p90_ms": round(s[int(0.90 * n)], 3),
        "p95_ms": round(s[int(0.95 * n)], 3),
        "p99_ms": round(s[min(int(0.99 * n), n - 1)], 3),
        "max_ms": round(s[-1], 3),
    }


# =========================================================================
# 1. ANALYTICS ENGINE BENCHMARK
# =========================================================================
def benchmark_analytics_engine() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print(" 1. BENCHMARKING DETERMINISTIC ANALYTICS ENGINE")
    print("=" * 70)
    results = {}

    # 1.1 Vectorized Change-Point Detector Scalability
    print("--> 1.1 ChangePointDetector (Vectorized Prefix Sums)...")
    cp_bench = {}
    sample_sizes = [300, 1000, 5000, 10000, 50000]
    for n in sample_sizes:
        # Synthesize time series with an abrupt step at N // 2
        rng = np.random.default_rng(42)
        signal = np.concatenate([
            rng.normal(loc=45.0, scale=0.5, size=n // 2),
            rng.normal(loc=15.0, scale=0.8, size=n - (n // 2)),
        ])

        # Warm-up
        _ = ChangePointDetector.detect_change_points(signal)

        latencies = []
        iterations = 50 if n <= 10000 else 10
        for _ in range(iterations):
            t0 = time.perf_counter()
            pts = ChangePointDetector.detect_change_points(signal)
            latencies.append((time.perf_counter() - t0) * 1000.0)

        m = compute_metrics(latencies)
        pts_per_sec = int(n / (m["mean_ms"] / 1000.0))
        m["throughput_points_per_sec"] = pts_per_sec
        m["detected_points"] = len(pts)
        cp_bench[f"N={n}"] = m
        print(f"    N={n:5d}: Mean={m['mean_ms']:6.3f} ms | P95={m['p95_ms']:6.3f} ms | Throughput={pts_per_sec:,} pts/sec")

    results["change_point_detector"] = cp_bench

    # 1.2 Spectral FFT & Cavitation Analysis
    print("\n--> 1.2 SpectralAnalyzer (20 kHz FFT & Harmonic Filtering)...")
    fft_bench = {}
    fft_sizes = [1024, 2048, 8192, 16384, 65536]
    for n in fft_sizes:
        t = np.linspace(0, n / 20000.0, n, endpoint=False)
        # 1X shaft harmonic at ~49.67 Hz + 2X harmonic at ~99.33 Hz + broadband noise
        sig = 2.5 * np.sin(2 * np.pi * 49.67 * t) + 1.2 * np.sin(2 * np.pi * 99.33 * t) + np.random.normal(0, 0.4, n)

        # Warm-up
        _ = SpectralAnalyzer.analyze_spectrum(sig, sampling_rate_hz=20000.0)

        latencies = []
        iterations = 50 if n <= 16384 else 20
        for _ in range(iterations):
            t0 = time.perf_counter()
            spec = SpectralAnalyzer.analyze_spectrum(sig, sampling_rate_hz=20000.0)
            latencies.append((time.perf_counter() - t0) * 1000.0)

        m = compute_metrics(latencies)
        samples_per_sec = int(n / (m["mean_ms"] / 1000.0))
        m["samples_per_sec"] = samples_per_sec
        m["peak_1x"] = spec["peak_1x_amplitude_mms"]
        fft_bench[f"N={n}"] = m
        print(f"    N={n:5d}: Mean={m['mean_ms']:6.3f} ms | P95={m['p95_ms']:6.3f} ms | Samples/sec={samples_per_sec:,}")

    results["fft_spectral_analyzer"] = fft_bench

    # 1.3 Statistical Profiler
    print("\n--> 1.3 StatisticalProfiler (Mean, Std, Variance, P95, Slope, CV)...")
    prof_bench = {}
    for n in [300, 1000, 10000, 50000]:
        sig = np.linspace(10.0, 50.0, n) + np.random.normal(0, 1.0, n)
        latencies = []
        for _ in range(50):
            t0 = time.perf_counter()
            _ = StatisticalProfiler.profile(sig)
            latencies.append((time.perf_counter() - t0) * 1000.0)
        m = compute_metrics(latencies)
        prof_bench[f"N={n}"] = m
        print(f"    N={n:5d}: Mean={m['mean_ms']:6.3f} ms | P95={m['p95_ms']:6.3f} ms")

    results["statistical_profiler"] = prof_bench
    return results


# =========================================================================
# 2. EMBEDDED TSDB BENCHMARK
# =========================================================================
def benchmark_embedded_tsdb() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print(" 2. BENCHMARKING EMBEDDED TSDB (RING BUFFER & SQLITE WAL)")
    print("=" * 70)
    results = {}

    temp_db = "temp_benchmark_tsdb.db"
    if os.path.exists(temp_db):
        os.remove(temp_db)

    tsdb = EmbeddedTSDB(db_path=temp_db, memory_capacity=5000)

    # 2.1 Ingestion Throughput
    print("--> 2.1 Ingestion Throughput (Insert 1,000 sequential records)...")
    latencies = []
    now = time.time()
    for i in range(1000):
        rec = {
            "timestamp": now + i,
            "asset_id": "VFD_VM_01",
            "f_out": 45.0 + (i % 5) * 0.1,
            "f_target": 45.0,
            "v_dc": 312.0 + (i % 10),
            "v_out": 220.0,
            "current": 1.45,
            "fault_code": 0,
        }
        t0 = time.perf_counter()
        tsdb.insert(rec)
        latencies.append((time.perf_counter() - t0) * 1000.0)

    m_ingest = compute_metrics(latencies)
    total_time_s = sum(latencies) / 1000.0
    throughput = int(1000 / total_time_s)
    m_ingest["inserts_per_second"] = throughput
    print(f"    Mean insert latency: {m_ingest['mean_ms']:6.3f} ms | P95: {m_ingest['p95_ms']:6.3f} ms")
    print(f"    Throughput: {throughput:,} inserts/sec (Total: {total_time_s:.2f}s for 1,000 inserts)")
    results["ingestion"] = m_ingest

    # 2.2 Historical Query Window Slicing (< 1 ms requirement)
    print("\n--> 2.2 In-Memory Pre-Fault Window Extraction...")
    window_bench = {}
    for window_sec in [30, 60, 300, 600, 1800]:
        query_latencies = []
        for _ in range(100):
            t0 = time.perf_counter()
            df = tsdb.get_window(seconds=window_sec)
            query_latencies.append((time.perf_counter() - t0) * 1000.0)
        m = compute_metrics(query_latencies)
        m["returned_rows"] = len(df)
        window_bench[f"{window_sec}s_window"] = m
        print(f"    Window {window_sec:4d}s ({len(df):4d} pts): Mean={m['mean_ms']:6.3f} ms | P95={m['p95_ms']:6.3f} ms | P99={m['p99_ms']:6.3f} ms")

    results["window_query"] = window_bench

    # 2.3 Latest Metrics Lookup
    print("\n--> 2.3 Single-Record Snapshot Lookup (get_latest)...")
    snap_latencies = []
    for _ in range(500):
        t0 = time.perf_counter()
        _ = tsdb.get_latest()
        snap_latencies.append((time.perf_counter() - t0) * 1000.0)
    m_snap = compute_metrics(snap_latencies)
    print(f"    Mean lookup latency: {m_snap['mean_ms'] * 1000:6.1f} µs | P95: {m_snap['p95_ms'] * 1000:6.1f} µs")
    results["latest_lookup"] = m_snap

    # Clean up temp db
    if os.path.exists(temp_db):
        try:
            os.remove(temp_db)
            if os.path.exists(temp_db + "-wal"):
                os.remove(temp_db + "-wal")
            if os.path.exists(temp_db + "-shm"):
                os.remove(temp_db + "-shm")
        except Exception:
            pass

    return results


# =========================================================================
# 3. FASTAPI ENDPOINTS BENCHMARK
# =========================================================================
def benchmark_fastapi_endpoints() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print(" 3. BENCHMARKING FASTAPI BACKEND REST ENDPOINTS")
    print("=" * 70)
    results = {}
    client = TestClient(api_app)

    # Seed embedded TSDB with a fresh reading so live metric endpoint measures fast-path
    from industrial_rca.data.embedded_tsdb import GLOBAL_TSDB
    GLOBAL_TSDB.insert({
        "asset_id": "VFD_VM_01",
        "timestamp": time.time(),
        "f_out": 40.0,
        "f_target": 40.0,
        "v_dc": 312.0,
        "v_out": 220.0,
        "current": 1.25,
        "fault_code": 0,
    })

    endpoints = [
        ("GET", "/api/v1/health", None, 10),
        ("GET", "/api/v1/telemetry/health", None, 100),
        ("GET", "/api/v1/scenarios", None, 100),
        ("GET", "/api/v1/telemetry/exp_err06", None, 50),
        ("GET", "/api/v1/telemetry/exp_err06/spectrum", None, 50),
        ("GET", "/api/v1/topology/VFD_VM_01", None, 50),
        ("GET", "/api/v1/telemetry/live/metrics", None, 50),
        ("GET", "/api/v1/telemetry/latest_incident", None, 100),
        ("POST", "/api/v1/telemetry/incident", {
            "asset_id": "VFD_VM_01",
            "fault_code": 6,
            "fault_description": "Deceleration Overvoltage Benchmark",
            "incident_id": "BENCHMARK-INC-001",
            "pre_fault_telemetry": [
                {"timestamp": time.time() - i, "f_out": 45.0, "v_dc": 312.0, "current": 1.4, "fault_code": 0}
                for i in range(30, 0, -1)
            ]
        }, 50),
    ]

    for method, path, payload, iters in endpoints:
        # Warmup
        if method == "GET":
            client.get(path)
        else:
            client.post(path, json=payload)

        latencies = []
        for _ in range(iters):
            t0 = time.perf_counter()
            if method == "GET":
                resp = client.get(path)
            else:
                resp = client.post(path, json=payload)
            latencies.append((time.perf_counter() - t0) * 1000.0)
            assert resp.status_code == 200, f"Failed: {path} returned {resp.status_code}"

        m = compute_metrics(latencies)
        rps = int(1000.0 / m["mean_ms"]) if m["mean_ms"] > 0 else 0
        m["requests_per_second"] = rps
        results[f"{method} {path}"] = m
        print(f"    {method:4s} {path:36s} | P50={m['p50_ms']:5.2f} ms | P95={m['p95_ms']:5.2f} ms | Mean={m['mean_ms']:5.2f} ms | RPS={rps:5d}")

    return results


# =========================================================================
# 4. LANGGRAPH END-TO-END RCA PIPELINE BENCHMARK
# =========================================================================
def benchmark_langgraph_pipeline() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print(" 4. BENCHMARKING LANGGRAPH 7-STEP RCA PIPELINE")
    print("=" * 70)
    results = {}

    client = TestClient(api_app)
    scenarios = [
        ("exp_err06", "VFD_VM_01", "H_VFD_ERR06", True),
        ("exp_err02", "VFD_VM_01", "H_VFD_ERR02", True),
        ("exp_nominal", "VFD_VM_01", None, False),
    ]

    for dataset_id, asset_id, expected_winner, is_fault in scenarios:
        print(f"\n--> Scenario: {dataset_id} (Asset: {asset_id}, IsFault: {is_fault})...")

        # Measure Step 1-6: Autonomous Ingest through HITL Pause
        thread_id = f"bench-{dataset_id}-{int(time.time())}"
        t0 = time.perf_counter()
        resp_run = client.post("/api/v1/rca/run", json={
            "dataset_id": dataset_id,
            "asset_id": asset_id,
            "thread_id": thread_id,
            "use_deepseek": False,  # Deterministic mode for pure engine benchmarking
        })
        t_phase1 = (time.perf_counter() - t0) * 1000.0
        assert resp_run.status_code == 200, f"RCA Run failed: {resp_run.text}"
        initial_state = resp_run.json()

        win_obj = initial_state.get("winning_hypothesis") or {}
        winner = win_obj.get("hypothesis_id")
        confidence = win_obj.get("confidence_score", 0.0)
        is_paused = initial_state.get("is_paused_at_hitl", False)

        if is_fault:
            # Measure Step 7: HITL Approval & 8D / SAP PM01 Synthesis
            t0_review = time.perf_counter()
            resp_review = client.post("/api/v1/rca/human-review", json={
                "thread_id": thread_id,
                "action": "approve",
                "reviewer": "Benchmark System",
                "notes": "Automated performance verification validation",
            })
            t_phase2 = (time.perf_counter() - t0_review) * 1000.0
            assert resp_review.status_code == 200, f"RCA Review failed: {resp_review.text}"
            final_state = resp_review.json()
            total_time = t_phase1 + t_phase2

            has_8d = "incident_report_8d" in final_state and final_state["incident_report_8d"] is not None
            has_sap = "sap_work_order" in final_state and final_state["sap_work_order"] is not None
        else:
            t_phase2 = 0.0
            total_time = t_phase1
            has_8d = False
            has_sap = False

        bench_data = {
            "dataset_id": dataset_id,
            "asset_id": asset_id,
            "is_fault": is_fault,
            "winning_hypothesis": winner,
            "confidence_score": confidence,
            "expected_winner": expected_winner,
            "matches_expected": winner == expected_winner,
            "phase1_autonomous_ms": round(t_phase1, 2),
            "phase2_review_deliverables_ms": round(t_phase2, 2),
            "total_pipeline_ms": round(total_time, 2),
            "has_8d_report": has_8d,
            "has_sap_order": has_sap,
        }
        results[dataset_id] = bench_data

        print(f"    Target Hypothesis:   {winner} (Confidence: {confidence:.1%}) [Match: {winner == expected_winner}]")
        print(f"    Phase 1 (Steps 1-6): {t_phase1:6.2f} ms")
        if is_fault:
            print(f"    Phase 2 (Step 7):    {t_phase2:6.2f} ms")
        print(f"    Total RCA Pipeline:  {total_time:6.2f} ms")

    return results


# =========================================================================
# 5. CONCURRENCY & CACHE STRESS BENCHMARK
# =========================================================================
def benchmark_concurrency_and_cache() -> Dict[str, Any]:
    print("\n" + "=" * 70)
    print(" 5. BENCHMARKING CONCURRENCY & LRU CACHE UNDER THREAD CONTENTION")
    print("=" * 70)
    results = {}

    cache = TelemetryCache(max_entries=100)

    # 5.1 Multi-threaded cache access
    num_threads = 8
    ops_per_thread = 500
    total_ops = num_threads * ops_per_thread

    def worker_task(worker_id: int):
        latencies = []
        for i in range(ops_per_thread):
            key_id = f"key_{i % 50}"  # 50 unique keys -> creates high hit rate
            t0 = time.perf_counter()
            val = cache.get("ds1", key_id, 0, 100, "stats")
            if val is None:
                cache.set("ds1", key_id, 0, 100, "stats", {"data": i})
            latencies.append((time.perf_counter() - t0) * 1000.0)
        return latencies

    print(f"--> Spawning {num_threads} concurrent threads executing {total_ops:,} operations...")
    t_start = time.perf_counter()
    with ThreadPoolExecutor(max_workers=num_threads) as executor:
        all_thread_latencies = list(executor.map(worker_task, range(num_threads)))
    total_wall_s = time.perf_counter() - t_start

    flat_latencies = [lat for thread_lats in all_thread_latencies for lat in thread_lats]
    m_cache = compute_metrics(flat_latencies)
    throughput_ops = int(total_ops / total_wall_s)
    m_cache["ops_per_second"] = throughput_ops
    m_cache["stats"] = cache.get_stats()

    print(f"    Mean operation latency: {m_cache['mean_ms'] * 1000:6.1f} µs | P95: {m_cache['p95_ms'] * 1000:6.1f} µs")
    print(f"    Throughput: {throughput_ops:,} ops/sec across {num_threads} threads")
    print(f"    Cache Hit Rate: {cache.get_stats()['hit_rate_pct']}% ({cache.get_stats()['hits']} hits, {cache.get_stats()['misses']} misses)")
    results["concurrent_cache"] = m_cache

    return results


# =========================================================================
# MAIN EXECUTION & REPORT GENERATION
# =========================================================================
def run_all_benchmarks():
    print("=" * 70)
    print(" IndustrialRCA High-Performance Comprehensive Benchmark Suite")
    print(" Date/Time:", time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 70)

    start_total = time.perf_counter()
    report = {
        "timestamp": time.time(),
        "date": time.strftime("%Y-%m-%d %H:%M:%S"),
        "analytics": benchmark_analytics_engine(),
        "embedded_tsdb": benchmark_embedded_tsdb(),
        "fastapi": benchmark_fastapi_endpoints(),
        "langgraph_pipeline": benchmark_langgraph_pipeline(),
        "concurrency_and_cache": benchmark_concurrency_and_cache(),
    }
    elapsed_total = time.perf_counter() - start_total
    report["total_benchmark_duration_s"] = round(elapsed_total, 2)

    # Save to JSON
    out_path = "benchmark_results.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("\n" + "=" * 70)
    print(f" Benchmark Complete in {elapsed_total:.2f} seconds!")
    print(f" Full metrics saved to '{out_path}'.")
    print("=" * 70)
    return report


if __name__ == "__main__":
    run_all_benchmarks()
