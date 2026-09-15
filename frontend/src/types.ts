// Type definitions for Industrial RCA React Application

export interface Scenario {
  id: string;
  dataset_id: string;
  name: string;
  asset_id: string;
  condition: string;
  description: string;
  duration_sec: number;
  has_trip: boolean;
  badge: 'CRITICAL' | 'HEALTHY' | 'LIVE_EDGE';
}

export interface TelemetryMetadata {
  asset_id: string;
  condition: string;
  anomaly_expected: boolean;
  duration_sec: number;
  trip_timestamp_sec?: number;
  trip_time_str?: string;
  primary_trip_sensor?: string;
  trip_value?: number;
  trip_setpoint?: number;
  fault_code?: number;
  fault_description?: string;
}

export interface OperationalLimits {
  [tag: string]: {
    name?: string;
    unit?: string;
    normal_min?: number;
    normal_max?: number;
    alarm_high?: number;
    trip_high?: number;
    zone_d_trip?: number;
    npsh_r?: number;
  };
}

export interface TelemetryData {
  dataset_id: string;
  scenario_name: string;
  metadata: TelemetryMetadata;
  sample_count: number;
  timestamps: number[];
  series: Record<string, number[]>;
  operational_limits: OperationalLimits;
}

export interface SpectrumAnalysis {
  overall_rms: number;
  fundamental_1x_hz: number;
  peak_1x_amplitude_mms: number;
  harmonic_2x_hz: number;
  peak_2x_amplitude_mms: number;
  cavitation_band_hz: string;
  broadband_cavitation_ratio: number;
  broadband_cavitation_ratio_pct: number;
  cavitation_detected: boolean;
  diagnosis: string;
}

export interface SpectrumData {
  dataset_id: string;
  analysis: SpectrumAnalysis;
  frequencies: number[];
  magnitudes: number[];
  shaft_1x_hz: number;
  shaft_2x_hz: number;
  cavitation_band: [number, number];
}

export interface TopologyNode {
  id: string;
  name: string;
  type: string;
  isa95_level: number;
  sensors: Array<{
    tag: string;
    description: string;
    unit?: string;
    sampling_rate_hz?: number;
    trip_limit?: number;
    normal_range?: [number, number];
    warning_limit?: number;
  }>;
  operating_specs: Record<string, any>;
  status: 'HEALTHY' | 'TRIPPED' | 'ROOT_CAUSE';
  position: { x: number; y: number };
}

export interface TopologyEdge {
  source: string;
  target: string;
  relation: string;
  medium?: string;
}

export interface TopologyData {
  target_asset: any;
  isa95_hierarchy: any;
  upstream_chain: any[];
  downstream_chain: any[];
  graph: {
    nodes: TopologyNode[];
    edges: TopologyEdge[];
  };
}

export interface HypothesisResult {
  hypothesis_id: string;
  name: string;
  status: 'CONFIRMED' | 'REFUTED' | 'SECONDARY_SYMPTOM' | 'INCONCLUSIVE';
  confidence: number;
  evidence: Array<{
    check: string;
    observation: string;
    status: string;
  }>;
  falsification_rationale: string;
  metrics: Record<string, any>;
  proposed_actions: string[];
}

export interface FiveWhysItem {
  level: string;
  question: string;
  answer: string;
  evidence: string;
  asset_involved: string;
}

export interface HumanReviewPayload {
  incident_id: string;
  asset_id: string;
  asset_name: string;
  winning_hypothesis: string;
  confidence_pct: number;
  iso14224_failure_mechanism: string;
  root_cause_asset: string;
  root_cause_summary: string;
  falsification_summary: Array<{
    hypothesis_id: string;
    name: string;
    status: string;
    confidence_pct: number;
    rationale: string;
  }>;
  causal_chain_5_whys: FiveWhysItem[];
  proposed_actions: string[];
  cmms_overdue_work_order: string;
}

export interface Report8D {
  report_type: string;
  incident_id: string;
  asset_id: string;
  asset_name: string;
  classification: string;
  d1_team: Record<string, string>;
  d2_problem_description: {
    what: string;
    when: string;
    where: string;
    how_much: string;
    operational_impact: string;
  };
  d3_interim_containment_actions: string[];
  d4_root_cause_analysis: {
    iso_14224_code?: string;
    failure_mechanism?: string;
    root_cause_asset?: string;
    root_cause_statement?: string;
    falsification_matrix?: any[];
    five_whys_trace?: FiveWhysItem[];
    deepseek_ai_evaluation?: any;
  };
  ai_diagnostic_engine?: string;
  d5_permanent_corrective_actions: string[];
  d6_implementation_and_validation: {
    validation_method: string;
    acceptance_criteria: string;
  };
  d7_systemic_prevention: string[];
  d8_sign_off: {
    reliability_manager_approval: string;
    reviewed_by: string;
    review_notes: string;
    date: string;
  };
}

export interface SAPWorkOrder {
  order_number: string;
  order_type: string;
  order_category: string;
  notification_number: string;
  equipment_id: string;
  equipment_name: string;
  functional_location: string;
  planner_group: string;
  cost_center: string;
  priority: string;
  breakdown_indicator: boolean;
  short_text: string;
  long_text: string;
  system_status: string;
  created_on: string;
  failure_mode_iso14224: string;
  operations: Array<{
    operation_number: string;
    work_center: string;
    duration_hours: number;
    description: string;
    details: string;
  }>;
  materials_required: Array<{
    material_id: string;
    description: string;
    quantity: number;
    unit: string;
  }>;
  total_estimated_hours: number;
}

export interface RCAState {
  thread_id: string;
  pipeline_status: string;
  current_step: number;
  is_paused_at_hitl: boolean;
  has_active_trip: boolean;
  detected_anomalies: Array<{
    tag: string;
    timestamp_sec: number;
    score: number;
    magnitude_shift: number;
    description: string;
  }>;
  tag_profiles: Record<string, any>;
  hypothesis_results: HypothesisResult[];
  winning_hypothesis?: HypothesisResult | null;
  falsification_summary: Array<{
    hypothesis_id: string;
    name: string;
    status: string;
    confidence_pct: number;
    rationale: string;
  }>;
  fmea_classification: Record<string, any>;
  causal_chain_5_whys: FiveWhysItem[];
  root_cause_asset: string;
  root_cause_description: string;
  human_review_required: boolean;
  human_review_payload?: HumanReviewPayload | null;
  human_review_decision?: {
    action: string;
    reviewer: string;
    notes: string;
    override_text?: string;
  } | null;
  incident_report_8d?: Report8D | null;
  sap_work_order?: SAPWorkOrder | null;
  execution_logs: string[];
  deepseek_evaluation?: {
    model: string;
    is_mock: boolean;
    content: string;
    reasoning_content: string;
    usage: Record<string, number>;
  } | null;
}

export interface ChatMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  reasoning_content?: string;
  timestamp: string;
}

export interface LatestIncident {
  has_incident: boolean;
  incident_data?: {
    incident_id: string;
    asset_id: string;
    fault_code: number;
    fault_description: string;
    dataset_id: string;
    point_count: number;
    received_at: string;
  } | null;
  received_at?: string | null;
  pipeline_status: string;
}

export interface LiveMetric {
  f_out: number;
  v_dc: number;
  current: number;
  rpm: number;
  fault_code: number;
  status: 'RUNNING' | 'TRIPPED' | 'WARNING' | string;
  timestamp: number;
  asset_id?: string;
  event?: string;
  incident_id?: string;
  fault_description?: string;
}
