"""Offline model decisions for regression tests; production never imports these."""

import json

from industrial_rca.tests.agentic.test_adaptive_investigation import tool_call


class MeasuredDecisionClient:
    is_live = True
    default_model = "offline-test-decisions"

    def __init__(
        self,
        tag="v_dc",
        hypothesis_id="H_FIELD_TRANSIENT",
        name="Observed channel transient",
        actions=None,
    ):
        self.tag, self.hypothesis_id, self.name = tag, hypothesis_id, name
        self.actions = actions or [
            "Collect a higher resolution waveform before attributing an upstream cause"
        ]
        self.calls = 0

    def chat_completion(self, messages, **kwargs):
        self.calls += 1
        if self.calls == 1:
            return tool_call("profile_telemetry", {"tag": self.tag}, "measurement")
        observation = json.loads(
            next(
                message["content"]
                for message in messages
                if message.get("role") == "tool"
            )
        )
        maximum = observation["result"]["max"]
        summary = f"{self.name}: measured {self.tag} maximum {maximum}; upstream cause unverified"
        return tool_call(
            "submit_diagnosis",
            {
                "status": "SUPPORTED",
                "summary": summary,
                "root_cause_asset": observation["asset_id"],
                "root_cause_description": summary,
                "hypotheses": [
                    {
                        "hypothesis_id": self.hypothesis_id,
                        "name": self.name,
                        "status": "SUPPORTED",
                        "confidence": 0.6,
                        "evidence_ids": ["measurement"],
                        "falsification_rationale": "Channel excursion is measured; mechanism requires further evidence",
                        "proposed_actions": self.actions,
                    }
                ],
                "causal_chain_5_whys": [],
                "missing_evidence": ["Upstream mechanism is not yet verified"],
            },
            "finish",
        )
