"""
Unit tests for Copilot System Prompt structure and context caching optimization.
Verifies:
1. Static prefix invariance (for DeepSeek/LLM KV-cache reuse).
2. Proper section ordering (Static domain rules placed before dynamic telemetry).
3. Preservation of all dynamic telemetry and active incident fields in suffix.
"""

import time
import pytest
from industrial_rca.api import build_copilot_system_prompt
from industrial_rca.data.embedded_tsdb import GLOBAL_TSDB


@pytest.fixture(autouse=True)
def clean_tsdb():
    """Ensure TSDB is completely cleared before and after each prompt test to prevent state leaks."""
    GLOBAL_TSDB.clear()
    yield
    GLOBAL_TSDB.clear()


def test_copilot_prompt_section_ordering():
    """
    Assert that static domain rules, specifications, and response directives appear
    BEFORE any dynamic telemetry or investigation status.
    """
    prompt = build_copilot_system_prompt()

    domain_rules_idx = prompt.find("=== DOMAIN KNOWLEDGE & EXPERT RULES ===")
    assert domain_rules_idx != -1, "Domain knowledge section missing from copilot prompt."

    dynamic_telemetry_header = "=== REAL-TIME TELEMETRY & INVESTIGATION STATE (DYNAMIC) ==="
    dynamic_idx = prompt.find(dynamic_telemetry_header)

    assert dynamic_idx != -1, f"Expected dynamic section header '{dynamic_telemetry_header}' not found."
    assert domain_rules_idx < dynamic_idx, (
        f"Cache violation: Static domain rules (index {domain_rules_idx}) must precede "
        f"dynamic telemetry (index {dynamic_idx}) for server-side prompt caching."
    )


def test_copilot_prompt_static_prefix_invariance():
    """
    Assert that the static prefix up to the dynamic telemetry boundary is byte-for-byte
    identical across calls even when live sensor readings fluctuate wildly.
    """
    dynamic_boundary = "=== REAL-TIME TELEMETRY & INVESTIGATION STATE (DYNAMIC) ==="

    # State A: Ingest packet A into TSDB
    now = time.time()
    packet_a = {
        "timestamp": now,
        "f_out": 40.0,
        "f_target": 40.0,
        "v_bus": 278.5,
        "v_out": 220.0,
        "current": 1.05,
        "rpm": 1198.0,
        "torque": 85.0,
        "power": 0.35,
        "fault_code": 0,
        "status": "RUNNING",
    }
    GLOBAL_TSDB.insert(packet_a)
    prompt_a = build_copilot_system_prompt()

    assert dynamic_boundary in prompt_a, f"Missing dynamic boundary '{dynamic_boundary}' in prompt_a"
    prefix_a = prompt_a.split(dynamic_boundary)[0]

    # State B: Ingest packet B with completely different telemetry values
    packet_b = {
        "timestamp": now + 5.0,
        "f_out": 12.5,
        "f_target": 50.0,
        "v_bus": 345.2,
        "v_out": 110.0,
        "current": 2.45,
        "rpm": 350.0,
        "torque": 140.0,
        "power": 0.72,
        "fault_code": 6,
        "status": "TRIPPED",
    }
    GLOBAL_TSDB.insert(packet_b)
    prompt_b = build_copilot_system_prompt()

    assert dynamic_boundary in prompt_b, f"Missing dynamic boundary '{dynamic_boundary}' in prompt_b"
    prefix_b = prompt_b.split(dynamic_boundary)[0]

    assert prefix_a == prefix_b, (
        "Cache violation: Static prefix differs across sensor fluctuations. "
        "Dynamic sensor values must not leak into the static prefix."
    )
    # Ensure static prefix contains the domain rules
    assert "=== DOMAIN KNOWLEDGE & EXPERT RULES ===" in prefix_a
    assert len(prefix_a) > 1000, f"Static prefix unexpectedly short: {len(prefix_a)} chars"


def test_copilot_prompt_preserves_dynamic_telemetry_in_suffix():
    """
    Verify that dynamic sensor readings and trip codes are accurately present in the dynamic suffix.
    """
    now = time.time()
    packet = {
        "timestamp": now,
        "f_out": 38.75,
        "f_target": 40.0,
        "v_bus": 281.2,
        "v_out": 215.0,
        "current": 1.18,
        "rpm": 1160.0,
        "torque": 92.0,
        "power": 0.41,
        "fault_code": 0,
        "status": "RUNNING",
    }
    GLOBAL_TSDB.insert(packet)
    prompt = build_copilot_system_prompt()

    dynamic_boundary = "=== REAL-TIME TELEMETRY & INVESTIGATION STATE (DYNAMIC) ==="
    assert dynamic_boundary in prompt
    suffix = prompt.split(dynamic_boundary)[1]

    assert "38.75 Hz" in suffix
    assert "281.2 V" in suffix
    assert "1.18 A" in suffix
    assert "1160" in suffix
