import React, { useState } from 'react';
import {
  ShieldAlert,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  GitCommit,
  Wrench,
} from 'lucide-react';
import { RCAState } from '../../types';

const DEFAULT_HYPOTHESES = [
  {
    hypothesis_id: 'H2',
    name: 'NPSH Starvation Induced Impeller Cavitation via Upstream Restriction',
    status: 'CONFIRMED',
    confidence: 0.98,
    falsification_rationale:
      'DPS-30101 spiked to 1.85 bar, PT-30101 dropped to 0.58 bar (< 1.20 bar NPSHr), 20 kHz FFT showed 48.9% broadband floor elevation.',
    evidence: [
      { check: 'NPSH Margin', observation: 'PT-30101 (0.58 bar) < NPSHr (1.20 bar). Margin negative by 0.62 bar.', status: 'CONFIRMED' },
      { check: 'Strainer Differential Pressure', observation: 'DPS-30101 = 1.85 bar (> 1.00 bar trip limit). Severe upstream restriction.', status: 'CONFIRMED' },
      { check: 'High-Frequency Acoustic Floor', observation: 'Broadband ratio = 48.9% in 2-8 kHz band. Characteristic acoustic signature of cavitation.', status: 'CONFIRMED' },
    ],
    proposed_actions: [
      'Overhaul and flush Suction Strainer STR-301A 20-mesh dual basket element',
      'Boroscopic inspection of first-stage impeller suction eye for cavitation pitting',
      'Inspect DE sleeve bearing shell clearances and replenish ISO VG 46 lube oil',
    ],
  },
  {
    hypothesis_id: 'H1',
    name: 'Drive-End Bearing Lubrication Starvation / Degradation',
    status: 'SECONDARY_SYMPTOM',
    confidence: 0.45,
    falsification_rationale:
      'TI-301-DE reached 92.3°C, but temperature rose 120s AFTER high vibration and pressure drop occurred. Thermal spike was a secondary symptom of severe vibration.',
    evidence: [
      { check: 'Vibration vs Temperature Onset', observation: 'High vibration preceded bearing temperature rise by 120s. Thermal spike was secondary.', status: 'SUPPORTED' },
    ],
    proposed_actions: ['Replace bearing sleeve shells during scheduled overhaul'],
  },
  {
    hypothesis_id: 'H3',
    name: 'Electric Drive Motor Rotor/Stator Electrical Overload',
    status: 'REFUTED',
    confidence: 0.08,
    falsification_rationale:
      'Motor line current IT-30101 remained at 98.2 A, well below continuous rated FLA of 115.0 A. Zero phase imbalance detected.',
    evidence: [
      { check: 'Motor Current FLA', observation: 'IT-30101 average 98.2 A vs 115.0 A FLA limit.', status: 'PASSED' },
    ],
    proposed_actions: [],
  },
  {
    hypothesis_id: 'H_VFD_ERR06',
    name: 'Deceleration Overvoltage (WECON VM Err06)',
    status: 'REFUTED',
    confidence: 0.02,
    falsification_rationale:
      'DC bus voltage v_dc remained nominal at 312.0 V (< 740.0 V trip limit). Inverter brake chopper not triggered.',
    evidence: [
      { check: 'DC Bus Voltage', observation: 'v_dc = 312.0 V (healthy baseline range 310 - 325 V).', status: 'PASSED' },
    ],
    proposed_actions: [],
  },
  {
    hypothesis_id: 'H_VFD_ERR11',
    name: 'Motor Thermal Overload (WECON VM Err11)',
    status: 'REFUTED',
    confidence: 0.05,
    falsification_rationale:
      'Motor load current remained below rated thermal overload curve. Inverter thermal model at 42% capacity.',
    evidence: [
      { check: 'Inverter Thermal Model', observation: 'Thermal accumulator at 42% (< 100% trip threshold).', status: 'PASSED' },
    ],
    proposed_actions: [],
  },
  {
    hypothesis_id: 'H_VFD_ERR02',
    name: 'Acceleration Overcurrent (WECON VM Err02)',
    status: 'REFUTED',
    confidence: 0.03,
    falsification_rationale:
      'Output current did not spike beyond inverter peak limit. Ramp acceleration profile followed nominal curve.',
    evidence: [
      { check: 'Peak Current Trip', observation: 'Instantaneous peak did not exceed 150% drive rating.', status: 'PASSED' },
    ],
    proposed_actions: [],
  },
];

const DEFAULT_5_WHYS = [
  {
    level: 'Why 1',
    question: 'Why did Boiler Feed Pump P-301A experience an emergency trip?',
    answer: 'Drive-End bearing temperature sensor TI-301-DE surged past the 90.0°C shutdown threshold, reaching 92.3°C at T=2880s.',
    evidence: 'TI-301-DE reached 92.3°C at T=2880s',
    asset_involved: 'P-301A',
  },
  {
    level: 'Why 2',
    question: 'Why did the DE sleeve bearing overheat so rapidly?',
    answer: 'Severe high-frequency radial vibration (11.4 mm/s RMS) wiped the hydrodynamic lube oil wedge, causing metal-to-metal boundary friction.',
    evidence: 'VI-301-R exceeded ISO Zone D trip threshold (7.1 mm/s)',
    asset_involved: 'P-301A',
  },
  {
    level: 'Why 3',
    question: 'Why did the pump experience violent radial vibration?',
    answer: 'Catastrophic acoustic cavitation inception inside the first-stage impeller caused violent vapor bubble collapse against the suction vanes.',
    evidence: '48.9% broadband noise floor elevation in 2.0 - 8.0 kHz band',
    asset_involved: 'P-301A',
  },
  {
    level: 'Why 4',
    question: 'Why did the pump undergo acoustic cavitation?',
    answer: 'Pump suction pressure PT-30101 plummeted to 0.58 bar, breaching the minimum required NPSHr limit of 1.20 bar by 0.62 bar.',
    evidence: 'PT-30101 fell from 2.45 bar to 0.58 bar at T=2880s',
    asset_involved: 'LINE-30101',
  },
  {
    level: 'Why 5',
    question: 'Why did suction pressure drop below NPSHr?',
    answer: 'Upstream Suction Strainer STR-301A basket blinded with marine biofouling and particulate debris (DPS-30101 reached 1.85 bar) due to deferred preventative maintenance PM WM-2026-0831.',
    evidence: 'DPS-30101 spiked to 1.85 bar (> 1.00 bar trip limit); CMMS work order WM-2026-0831 was deferred',
    asset_involved: 'STR-301A',
  },
];

interface FMEAMatrixTabProps {
  rcaState: RCAState | null;
}

export const FMEAMatrixTab: React.FC<FMEAMatrixTabProps> = ({ rcaState }) => {
  const [expandedHypId, setExpandedHypId] = useState<string>('H2');

  const rawHypotheses = rcaState?.hypothesis_results;
  const hypotheses = rawHypotheses && rawHypotheses.length > 0 ? rawHypotheses : DEFAULT_HYPOTHESES;
  const winningHyp = rcaState?.winning_hypothesis || hypotheses.find((h) => h.status === 'CONFIRMED');
  const rawWhys = rcaState?.causal_chain_5_whys;
  const fiveWhys = rawWhys && rawWhys.length > 0 ? rawWhys : DEFAULT_5_WHYS;

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'CONFIRMED':
        return (
          <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-xs">
            <CheckCircle2 className="w-3.5 h-3.5 text-emerald-600" />
            <span>CONFIRMED</span>
          </span>
        );
      case 'SECONDARY_SYMPTOM':
        return (
          <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-amber-50 text-amber-700 border border-amber-200">
            <AlertTriangle className="w-3.5 h-3.5 text-amber-600" />
            <span>SECONDARY SYMPTOM</span>
          </span>
        );
      case 'REFUTED':
        return (
          <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-slate-100 text-slate-600 border border-slate-200">
            <XCircle className="w-3.5 h-3.5 text-slate-500" />
            <span>REFUTED</span>
          </span>
        );
      default:
        return (
          <span className="flex items-center space-x-1 px-2.5 py-0.5 rounded text-xs font-mono text-slate-500 bg-slate-50 border border-slate-200">
            <HelpCircle className="w-3.5 h-3.5" />
            <span>INCONCLUSIVE</span>
          </span>
        );
    }
  };

  return (
    <div className="space-y-4">
      {/* Header Banner */}
      <div className="bg-white border border-slate-200 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-teal-50 text-teal-600 border border-teal-100">
            <ShieldAlert className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold font-mono text-slate-800 uppercase">
              ISO 14224 FMEA Hypothesis Falsification Matrix
            </div>
            <div className="text-[11px] text-slate-500">
              Parallel Multi-Branch Evidence Elimination · 6 Hypotheses Tested Against Physical Telemetry
            </div>
          </div>
        </div>

        {winningHyp && (
          <div className="flex items-center space-x-2 text-[11px] font-mono">
            <span className="px-2.5 py-1 rounded bg-teal-50 text-teal-700 border border-teal-200">
              Winning Branch: <strong>{winningHyp.hypothesis_id} ({winningHyp.name.slice(0, 24)}...)</strong>
            </span>
          </div>
        )}
      </div>

      {/* 6 Hypotheses Cards Grid */}
      <div className="space-y-2.5">
        {hypotheses.length > 0 ? (
          hypotheses.map((h) => {
            const isExpanded = expandedHypId === h.hypothesis_id;
            const isWinner = winningHyp?.hypothesis_id === h.hypothesis_id;

            return (
              <div
                key={h.hypothesis_id}
                className={`bg-white border rounded-xl transition-all overflow-hidden ${
                  isWinner
                    ? 'border-teal-400 ring-1 ring-teal-400/20 shadow-xs'
                    : 'border-slate-200 hover:border-slate-300'
                }`}
              >
                {/* Header Row */}
                <div
                  onClick={() => setExpandedHypId(isExpanded ? '' : h.hypothesis_id)}
                  className={`p-3.5 flex flex-wrap items-center justify-between gap-3 cursor-pointer select-none ${
                    isWinner ? 'bg-teal-50/25' : 'hover:bg-slate-50/50'
                  }`}
                >
                  <div className="flex items-center space-x-3">
                    <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 border border-slate-200">
                      {h.hypothesis_id}
                    </span>
                    <span className="font-mono text-xs font-semibold text-slate-900">
                      {h.name}
                    </span>
                  </div>

                  <div className="flex items-center space-x-3">
                    {/* Confidence Meter */}
                    <div className="hidden sm:flex items-center space-x-2 font-mono text-xs text-slate-500">
                      <span>Confidence:</span>
                      <div className="w-16 bg-slate-100 h-2 rounded-full overflow-hidden border border-slate-200">
                        <div
                          className={`h-full ${
                            h.status === 'CONFIRMED'
                              ? 'bg-teal-500'
                              : h.status === 'SECONDARY_SYMPTOM'
                              ? 'bg-amber-400'
                              : 'bg-slate-400'
                          }`}
                          style={{ width: `${h.confidence * 100}%` }}
                        />
                      </div>
                      <span className="font-bold text-slate-700">{(h.confidence * 100).toFixed(0)}%</span>
                    </div>

                    {getStatusBadge(h.status)}

                    <button className="text-slate-400 hover:text-slate-600">
                      {isExpanded ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                    </button>
                  </div>
                </div>

                {/* Expanded Details Body */}
                {isExpanded && (
                  <div className="p-4 border-t border-slate-100 bg-slate-50/50 space-y-3 text-xs font-mono">
                    {/* Falsification Rationale */}
                    <div className="p-3 rounded-lg bg-white border border-slate-200 shadow-xs">
                      <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider mb-1">
                        Physical Telemetry Falsification Rationale:
                      </div>
                      <p className="text-slate-700 leading-relaxed font-sans text-xs">
                        {h.falsification_rationale}
                      </p>
                    </div>

                    {/* Evidence Checks */}
                    {h.evidence && h.evidence.length > 0 && (
                      <div className="space-y-1.5">
                        <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                          Engineering Check Findings:
                        </div>
                        <div className="space-y-1">
                          {h.evidence.map((ev, idx) => (
                            <div
                              key={idx}
                              className="p-2 rounded-lg bg-white border border-slate-200 flex flex-wrap items-start justify-between gap-2"
                            >
                              <div className="space-y-0.5 max-w-xl">
                                <span className="font-semibold text-blue-700">{ev.check}:</span>
                                <p className="text-slate-600 font-sans text-xs">{ev.observation}</p>
                              </div>
                              <span className="px-2 py-0.5 rounded text-[10px] font-mono font-semibold bg-slate-100 text-slate-700 border border-slate-200">
                                {ev.status}
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}

                    {/* Proposed Corrective Actions */}
                    {h.proposed_actions && h.proposed_actions.length > 0 && (
                      <div className="space-y-1">
                        <div className="text-[10px] font-bold text-slate-500 uppercase tracking-wider flex items-center space-x-1">
                          <Wrench className="w-3 h-3 text-teal-600" />
                          <span>Recommended Corrective Actions:</span>
                        </div>
                        <ul className="space-y-0.5 pl-4 list-disc text-slate-600 font-sans text-xs">
                          {h.proposed_actions.map((act, idx) => (
                            <li key={idx}>{act}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })
        ) : (
          <div className="p-8 text-center text-slate-500 font-mono text-xs bg-white border border-slate-200 rounded-xl">
            No hypothesis evaluations available. Trigger the LangGraph pipeline to evaluate the FMEA matrix.
          </div>
        )}
      </div>

      {/* 5-Whys Causal Chain Section */}
      {fiveWhys.length > 0 && (
        <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-xs space-y-4">
          <div className="flex items-center justify-between border-b border-slate-100 pb-2.5">
            <div className="flex items-center space-x-2">
              <GitCommit className="w-4 h-4 text-amber-600" />
              <h3 className="font-mono text-xs font-bold text-slate-900 uppercase">
                Upstream ISA-95 Causal Trace (5-Whys Root Cause Chain)
              </h3>
            </div>
            <span className="text-[11px] font-mono text-slate-500">
              Trip Symptom (TI-301-DE) → Physical Origin (STR-301A)
            </span>
          </div>

          <div className="space-y-3 relative before:absolute before:left-3.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200 pl-7">
            {fiveWhys.map((w, idx) => (
              <div key={idx} className="relative p-3 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                <div
                  className="absolute -left-[23px] top-3 w-4 h-4 rounded-full bg-white border-2 flex items-center justify-center font-mono text-[9px] font-bold"
                  style={{
                    borderColor: idx === 4 ? '#EF4444' : idx === 0 ? '#0D9488' : '#F59E0B',
                    color: idx === 4 ? '#EF4444' : idx === 0 ? '#0D9488' : '#F59E0B',
                  }}
                >
                  {idx + 1}
                </div>

                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-amber-800">{w.level}</span>
                  <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-blue-50 text-blue-700 border border-blue-200">
                    Asset: {w.asset_involved}
                  </span>
                </div>
                <div className="text-xs font-bold text-slate-900 font-sans">{w.question}</div>
                <div className="text-xs text-slate-600 font-sans leading-relaxed">{w.answer}</div>
                <div className="text-[10px] font-mono text-slate-500 border-t border-slate-200 pt-1 mt-1">
                  Evidence: {w.evidence}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
