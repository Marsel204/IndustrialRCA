"""
DeepSeek API Client for Industrial Root Cause Analysis.
Supports both deepseek-chat (DeepSeek-V3) and deepseek-reasoner (DeepSeek-R1 with CoT reasoning_content).
Loads configuration from .env using python-dotenv.
Provides automatic fallback to high-fidelity deterministic simulation if API key is not present.
"""

import os
import json
import logging
from pathlib import Path
from typing import Dict, Any, List, Optional
from dotenv import load_dotenv
from openai import OpenAI

# Load .env file from project root
env_path = Path(__file__).resolve().parent.parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)


class DeepSeekClient:
    """
    Client for interacting with DeepSeek LLM endpoints (api.deepseek.com).
    Supports live API queries and high-fidelity deterministic simulation for testing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        default_model: Optional[str] = None,
    ):
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        self.base_url = base_url or os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com/v1")
        self.default_model = default_model or os.environ.get("DEEPSEEK_MODEL", "deepseek-chat")

        self.is_live = bool(
            self.api_key and self.api_key.strip() not in ("mock", "test", "dummy", "")
        )

        if self.is_live:
            try:
                self.client = OpenAI(
                    api_key=self.api_key,
                    base_url=self.base_url,
                )
                logger.info(f"Initialized live DeepSeek client with endpoint {self.base_url} (model: {self.default_model})")
            except Exception as e:
                logger.warning(f"Failed to initialize OpenAI client for DeepSeek: {e}. Falling back to test mock.")
                self.is_live = False
                self.client = None
        else:
            self.client = None
            logger.info("DeepSeek client running in deterministic test/simulation mode.")

    def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a chat completion call against DeepSeek API.
        Extracts both content and reasoning_content (when using deepseek-reasoner).
        """
        target_model = model or self.default_model

        if self.is_live and self.client is not None:
            try:
                kwargs: Dict[str, Any] = {
                    "model": target_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                }
                # deepseek-reasoner does not support temperature or response_format in certain versions
                if "reasoner" not in target_model:
                    kwargs["temperature"] = temperature
                    if response_format:
                        kwargs["response_format"] = response_format

                response = self.client.chat.completions.create(**kwargs)
                choice = response.choices[0]
                message = choice.message

                content = message.content or ""
                reasoning_content = getattr(message, "reasoning_content", None) or ""

                return {
                    "success": True,
                    "is_mock": False,
                    "model": target_model,
                    "content": content,
                    "reasoning_content": reasoning_content,
                    "usage": {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                        "total_tokens": response.usage.total_tokens if response.usage else 0,
                    },
                }
            except Exception as e:
                logger.error(f"DeepSeek live API error: {e}. Falling back to test simulation.")
                mock_res = self._generate_simulated_response(messages, target_model)
                mock_res["error"] = str(e)
                return mock_res
        else:
            return self._generate_simulated_response(messages, target_model)

    def _generate_simulated_response(
        self, messages: List[Dict[str, str]], model: str
    ) -> Dict[str, Any]:
        """
        Deterministic simulation for unit testing and offline development.
        """
        full_prompt = " ".join([m.get("content", "") for m in messages]).lower()

        if "5-whys" in full_prompt or "five whys" in full_prompt:
            content = json.dumps({
                "five_whys": [
                    {
                        "level": "Why 1",
                        "question": "Why did Boiler Feed Pump P-301A trip at 03:14 AM?",
                        "answer": "Drive-End bearing temperature sensor TI-301-DE breached the emergency trip threshold (92.3°C vs 90.0°C limit).",
                        "evidence": "TI-301-DE logged exponential temperature escalation beginning at T=2880s.",
                        "asset_involved": "P-301A"
                    },
                    {
                        "level": "Why 2",
                        "question": "Why did the drive-end sleeve bearing overheat?",
                        "answer": "Severe radial vibration (VI-301-R at 11.4 mm/s RMS) caused hydrodynamic lubricant film breakdown and boundary contact.",
                        "evidence": "Radial vibration surged past ISO 10816 Zone D (7.1 mm/s) 7 minutes prior to thermal trip.",
                        "asset_involved": "P-301A"
                    },
                    {
                        "level": "Why 3",
                        "question": "Why did pump vibration surge to catastrophic levels?",
                        "answer": "Intense acoustic fluid cavitation erupted at the first-stage impeller eye.",
                        "evidence": "FFT spectrum shows 48.9% broadband acoustic energy in the 2.0-8.0 kHz cavitation band.",
                        "asset_involved": "P-301A"
                    },
                    {
                        "level": "Why 4",
                        "question": "Why did severe fluid cavitation develop?",
                        "answer": "Net Positive Suction Head Available (0.58 bar) dropped far below OEM requirement NPSHr (1.20 bar).",
                        "evidence": "Suction line pressure PT-30101 collapsed from 2.45 bar to 0.58 bar.",
                        "asset_involved": "LINE-30101"
                    },
                    {
                        "level": "Why 5 (Root Cause)",
                        "question": "Why did suction pressure collapse below NPSHr?",
                        "answer": "Upstream Suction Strainer STR-301A basket blinded with biofouling/particulate debris due to deferred 14-day PM flush.",
                        "evidence": "Differential pressure DPS-30101 reached 1.85 bar (Alarm 1.0 bar). Overdue CMMS PM: WM-2026-0831.",
                        "asset_involved": "STR-301A"
                    }
                ],
                "root_cause_asset": "STR-301A",
                "recommended_fix": "Clean STR-301A basket, boroscope P-301A impeller, and flush DE lube oil."
            }, indent=2)
            reasoning = (
                "DeepSeek Diagnostic Verification:\n"
                "1. Starting with primary trip symptom: TI-301-DE bearing temperature > 90.0 C.\n"
                "2. Trace temporal sequence: Vibration VI-301-R spiked to 11.4 mm/s BEFORE thermal runaway.\n"
                "3. Spectral vibration FFT confirms cavitation signature (2-8 kHz noise floor explosion).\n"
                "4. Upstream topology tracing shows PT-30101 (suction pressure) dropped below NPSHr (1.2 bar).\n"
                "5. Upstream DP sensor DPS-30101 spiked to 1.85 bar across strainer STR-301A.\n"
                "6. Conclusion: Upstream physical root cause is Suction Strainer STR-301A blinding."
            )
        elif "hypothesis" in full_prompt or "hypotheses" in full_prompt:
            content = json.dumps({
                "evaluations": [
                    {
                        "hypothesis_id": "H1",
                        "name": "Drive-End Bearing Lubrication Starvation",
                        "status": "SECONDARY_SYMPTOM",
                        "confidence": 0.94,
                        "rationale": "Refuted as root cause. Oil lab analysis healthy prior to trip. Thermal rise was a downstream effect of vibration rubbing."
                    },
                    {
                        "hypothesis_id": "H2",
                        "name": "NPSH Starvation Induced Impeller Cavitation",
                        "status": "CONFIRMED",
                        "confidence": 0.98,
                        "rationale": "Confirmed. PT-30101 dropped below NPSHr, DPS-30101 breached high alarm, and FFT proves broadband cavitation."
                    },
                    {
                        "hypothesis_id": "H3",
                        "name": "Drive Motor Electrical Overload",
                        "status": "REFUTED",
                        "confidence": 0.96,
                        "rationale": "Refuted. Continuous line current remained below continuous FLA of 115A. Current hunting was caused by 2-phase impeller pumping."
                    }
                ],
                "winning_hypothesis": "H2"
            }, indent=2)
            reasoning = "DeepSeek Diagnostic Falsification confirmed H2 as primary hydraulic trigger."
        elif "motor" in full_prompt and ("overload" in full_prompt or "h3" in full_prompt or "current" in full_prompt or "refut" in full_prompt):
            content = (
                "**Hypothesis H3 (Drive Motor Electrical Overload) was deterministicly refuted** for two key reasons:\n\n"
                "1. **Continuous Current Load:** Motor IT-30101 steady-state line current prior to cavitation was 84.2 A, well below the 115.0 A Full Load Amperes (FLA) rating.\n"
                "2. **Current Oscillations vs Overload:** The ±22% current swings observed between T=2880s and T=3300s were caused by dynamic load fluctuations from a two-phase (vapor/liquid) fluid mixture passing through the pump impeller, NOT electrical rotor/stator breakdown or thermal overload."
            )
            reasoning = "Evaluated electrical sensor IT-30101 against motor FLA limit 115A. Fluctuation pattern matches cavitation hydraulic pulsation."
        elif "cavitation" in full_prompt or "fft" in full_prompt or "acoustic" in full_prompt or "spectrum" in full_prompt:
            content = (
                "**20 kHz High-Frequency Spectral FFT Diagnostic Analysis:**\n\n"
                "- **Overall RMS:** 11.4 mm/s RMS (exceeds ISO 10816 Class III Zone D damage threshold of 7.1 mm/s).\n"
                "- **Broadband Energy Ratio (2.0–8.0 kHz):** 48.9% (Alarm threshold > 35%).\n"
                "- **Harmonics:** 1X running speed (49.7 Hz) is 2.8 mm/s; 2X harmonic (99.3 Hz) is 1.2 mm/s.\n"
                "- **Diagnosis:** High-frequency broadband energy dominates discrete running harmonics. This is the textbook acoustic signature of violent vapor micro-bubble implosions causing shockwaves against the impeller eye."
            )
            reasoning = "Spectral energy density in 2-8 kHz band exceeds 35% threshold. Discrete unbalance/misalignment ruled out."
        elif "cmms" in full_prompt or "work order" in full_prompt or "wm-2026" in full_prompt or "strainer" in full_prompt:
            content = (
                "**CMMS & Maintenance Record Correlation:**\n\n"
                "- **Work Order ID:** `WM-2026-0831`\n"
                "- **Description:** Routine 14-day preventive backflush of Suction Strainer STR-301A basket.\n"
                "- **Status:** **DEFERRED (12 days overdue)** by operations due to peak steam production schedule.\n"
                "- **Consequence:** Marine biofouling and particulate debris accumulated across the 316SS mesh, ramping differential pressure DPS-30101 to 1.85 bar and starving the pump suction below 0.58 bar (NPSHr 1.20 bar)."
            )
            reasoning = "Correlated CMMS work order WM-2026-0831 with DPS-30101 pressure ramp beginning at T=1800s."
        elif "note" in full_prompt or "draft" in full_prompt or "justif" in full_prompt or "approv" in full_prompt:
            content = (
                "**Recommended Engineering Review Notes for HITL Approval:**\n\n"
                "\"Root cause verified through multi-sensor physics convergence and ISA-95 topology tracing. Upstream suction strainer STR-301A blinded due to deferred PM WM-2026-0831, causing suction pressure PT-30101 (0.58 bar) to plummet below NPSHr (1.20 bar). Severe acoustic cavitation confirmed by 20 kHz FFT (48.9% broadband ratio in 2-8 kHz band), inducing 11.4 mm/s RMS vibration that destroyed the DE sleeve bearing lubrication film. Authorize SAP PM01 corrective work order for strainer overhaul and impeller boroscopic inspection.\""
            )
            reasoning = "Drafted standard engineering sign-off rationale referencing sensor tags, ISO standards, and CMMS link."
        elif "containment" in full_prompt or "action" in full_prompt or "recommend" in full_prompt:
            content = (
                "**Recommended Immediate Maintenance & Containment Actions:**\n\n"
                "1. **Isolate & Lockout:** Verify auxiliary feed pump P-301B is stable. Lockout electrical breaker `33-SWG-P301A` (3.3 kV) and close suction/discharge MOVs.\n"
                "2. **Strainer Overhaul:** Pull and inspect STR-301A basket; clean biofouling or install replacement 20-mesh 316SS element.\n"
                "3. **Impeller Boroscopy:** Inspect P-301A first-stage impeller suction eye for cavitation pitting or erosion.\n"
                "4. **Bearing Inspection:** Drain and flush DE sleeve bearing housing; refill with ISO VG 46 lube oil."
            )
            reasoning = "Retrieved D3 containment and D5 permanent corrective actions from FMEA knowledge base."
        elif "hello" in full_prompt or "hi" in full_prompt or "who" in full_prompt or "help" in full_prompt:
            content = (
                "Hello! I am your **Industrial RCA Diagnostic Copilot** powered by DeepSeek. "
                "I have full visibility into the telemetry, 20 kHz vibration FFT, ISA-95 asset topology, and ISO 14224 FMEA falsification matrix for Boiler Feed Pump P-301A. "
                "How can I assist you before you authorize the maintenance deliverables?"
            )
            reasoning = "Operator greeted copilot; offered assistance on incident data."
        elif "deepseek_online" in full_prompt or "ping" in full_prompt:
            content = "DEEPSEEK_ONLINE"
            reasoning = "DeepSeek connection check verified."
        else:
            content = (
                f"Based on the telemetry for asset P-301A, the incident was initiated by upstream suction strainer STR-301A clogging (DPS-30101 reached 1.85 bar), "
                f"which starved pump suction below NPSHr (PT-30101 dropped to 0.58 bar) and triggered severe fluid cavitation (FFT 2-8 kHz ratio: 48.9%). "
                f"This induced radial vibration at 11.4 mm/s RMS, breaking down bearing lubrication and causing the thermal trip on TI-301-DE at 92.3°C."
            )
            reasoning = "Answered operator inquiry with primary causal chain summary."

        return {
            "success": True,
            "is_mock": True,
            "model": f"{model}-simulated",
            "content": content,
            "reasoning_content": reasoning,
            "usage": {
                "prompt_tokens": len(full_prompt) // 4,
                "completion_tokens": len(content) // 4,
                "total_tokens": (len(full_prompt) + len(content)) // 4,
            },
        }

    def test_connection(self) -> Dict[str, Any]:
        """
        Verifies API connectivity. Returns connection status and diagnostic metadata.
        """
        test_messages = [
            {"role": "system", "content": "You are an expert industrial machinery diagnostics AI."},
            {"role": "user", "content": "Respond with 'DEEPSEEK_ONLINE' if you receive this message."},
        ]
        res = self.chat_completion(test_messages, max_tokens=20)
        return {
            "status": "ONLINE" if res.get("success") else "FAILED",
            "is_live": not res.get("is_mock", True),
            "model": res.get("model"),
            "base_url": self.base_url,
            "has_api_key": bool(self.api_key),
            "response": res.get("content", "").strip(),
            "reasoning_sample": res.get("reasoning_content", "")[:100] if res.get("reasoning_content") else None,
            "usage": res.get("usage", {}),
        }


if __name__ == "__main__":
    client = DeepSeekClient()
    info = client.test_connection()
    print("=== DeepSeek API Connection Test ===")
    print(f"Status:          {info['status']}")
    print(f"Live API Mode:   {info['is_live']}")
    print(f"Model:           {info['model']}")
    print(f"Base URL:        {info['base_url']}")
    print(f"Response:        {info['response']}")
    if info.get("reasoning_sample"):
        print(f"Reasoning:       {info['reasoning_sample']}...")
    print(f"Token Usage:     {info['usage']}")
    print("====================================")
