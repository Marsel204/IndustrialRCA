"""Validated boundaries for model decisions, tool arguments and conclusions."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Text = Annotated[str, Field(min_length=1, max_length=4000)]
Identifier = Annotated[str, Field(min_length=1, max_length=128)]
References = Annotated[list[Identifier], Field(max_length=32)]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class InvestigationBudget(Contract):
    max_iterations: int = Field(default=8, ge=1, le=24)
    max_calls_per_turn: int = Field(default=4, ge=1, le=8)
    max_observation_chars: int = Field(default=16000, ge=512, le=32000)
    max_history_chars: int = Field(default=160000, ge=4096)
    max_elapsed_seconds: float = Field(default=120, gt=0, le=600)


class TelemetryQuery(Contract):
    tag: Identifier
    start_index: int = Field(default=0, ge=0)
    end_index: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def ordered_window(self):
        if self.end_index is not None and self.end_index <= self.start_index:
            raise ValueError("end_index must be greater than start_index")
        return self


class TopologyQuery(Contract):
    asset_id: Identifier
    direction: Literal["upstream", "downstream"] = "upstream"
    max_depth: int = Field(default=3, ge=1, le=5)


class ReferenceQuery(Contract):
    asset_id: Identifier
    fault_code: int | None = Field(default=None, ge=0, le=65535)


class MaintenanceQuery(Contract):
    asset_id: Identifier


class Hypothesis(Contract):
    hypothesis_id: Identifier
    name: Text
    status: Literal[
        "CONFIRMED", "SUPPORTED", "REFUTED", "SECONDARY_SYMPTOM", "INCONCLUSIVE"
    ]
    confidence: float = Field(ge=0, le=1)
    evidence_ids: References = Field(default_factory=list)
    falsification_rationale: Text
    proposed_actions: list[Text] = Field(default_factory=list, max_length=20)


class CausalStep(Contract):
    level: Text
    question: Text
    answer: Text
    evidence: Text
    evidence_ids: References
    asset_involved: Identifier


class Diagnosis(Contract):
    status: Literal["SUPPORTED", "INCONCLUSIVE"]
    summary: Text
    hypotheses: list[Hypothesis] = Field(default_factory=list, max_length=20)
    causal_chain_5_whys: list[CausalStep] = Field(default_factory=list, max_length=10)
    root_cause_asset: Identifier | None = None
    root_cause_description: Text
    missing_evidence: list[Text] = Field(default_factory=list, max_length=20)
    # Classification must be a retrieved reference, not an invented ISO code.
    fmea_classification: dict[str, str] = Field(default_factory=dict, max_length=10)


class Observation(Contract):
    observation_id: Identifier
    tool: Identifier
    arguments: dict[str, Any]
    source_type: Literal[
        "measured", "simulated", "reference", "configured", "inferred", "unavailable"
    ]
    asset_id: Identifier
    dataset_id: Annotated[str, Field(min_length=1, max_length=1024)]
    result: Any = None
    error: str | None = None
    elapsed_ms: float = Field(ge=0)
