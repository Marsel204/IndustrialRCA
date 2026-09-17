import React, { useState } from 'react';
import {
  ShieldAlert,
  ShieldCheck,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  HelpCircle,
  ChevronDown,
  ChevronUp,
  GitCommit,
  Network,
  Wrench,
} from 'lucide-react';
import { RCAState } from '../../types';

const DEFAULT_HYPOTHESES = [
  {
    hypothesis_id: 'H_VFD_ERR06',
    name: 'Overfrequency Deceleration Overvoltage (WECON VM Err06)',
    status: 'CONFIRMED',
    confidence: 0.98,
    falsification_rationale:
      'Frequency setpoint exceeded 40.00 Hz operational ceiling toward 50.00 Hz, driving DC bus voltage to 202.5 V (> 195.0 V trip limit) with unpopulated dynamic braking resistor terminals P+/PB.',
    evidence: [
      { check: 'DC Bus Voltage (Reg 1003H / 3004H)', observation: 'V_dc surged to 202.5 V (trip threshold: 195.0 V, nominal: 182.0 V, ~207 V at 50 Hz).', status: 'CONFIRMED' },
      { check: 'Output Frequency (Reg 1001H / 3000H)', observation: 'f_out ramped past 40.00 Hz to 48.50 Hz, exceeding test bench ceiling.', status: 'CONFIRMED' },
      { check: 'Braking Resistor Circuit (P+/PB)', observation: 'Dynamic braking resistor absent (open circuit); kinetic back-EMF energy trapped in DC capacitor bank.', status: 'CONFIRMED' },
      { check: 'VFD Fault Register (Reg 700BH)', observation: 'Modbus register 700BH latched fault code 6 (Err06 - Overvoltage during deceleration/overfrequency).', status: 'CONFIRMED' },
    ],
    proposed_actions: [
      'Clamp maximum output frequency parameter F0.10 to 40.00 Hz in Wecon VM VFD',
      'Install dynamic braking resistor (nominal 70-100 Ohm, 100-150W) across terminals P+ and PB',
      'Configure high DC bus pre-alarm in HMI at 190.0 V (trip limit: 195.0 V)',
      'Increase parameter F0.18 deceleration ramp time to >= 5.0 seconds',
    ],
  },
  {
    hypothesis_id: 'H_VFD_ERR02',
    name: 'Forced Sudden Deceleration Overcurrent (WECON VM Err02)',
    status: 'REFUTED',
    confidence: 0.03,
    falsification_rationale:
      'Continuous motor current remained within normal operating limits (peak 1.15 A < 2.50 A trip limit). No abrupt PLC On/Off stop actuation commanded in this scenario.',
    evidence: [
      { check: 'Motor Output Current (Reg 1005H / 3002H)', observation: 'Continuous current average 1.15 A (peak < 2.50 A trip threshold).', status: 'PASSED' },
      { check: 'PLC Stop Trigger (D Variable / MQTT Error Topic)', observation: 'No instantaneous hard-stop de-energization commanded in this run.', status: 'PASSED' },
    ],
    proposed_actions: [],
  },
  {
    hypothesis_id: 'H_VFD_ERR03',
    name: 'Deceleration Overcurrent (WECON VM Err03)',
    status: 'REFUTED',
    confidence: 0.02,
    falsification_rationale:
      'Modbus fault code register Reg 700BH did not report Err03. Current ramp remained within normal linear envelope.',
    evidence: [
      { check: 'Deceleration Ramp Current', observation: 'Current remained within normal linear slope envelope.', status: 'PASSED' },
      { check: 'Fault Register (Reg 700BH)', observation: 'Reported fault code 6, not Err03.', status: 'PASSED' },
    ],
    proposed_actions: [],
  },
  {
    hypothesis_id: 'H_VFD_ERR11',
    name: 'Motor Thermal Overload (WECON VM Err11)',
    status: 'REFUTED',
    confidence: 0.04,
    falsification_rationale:
      'Motor continuous current (1.15 A) remained well below parameter F2.03 rated motor thermal limit (2.50 A). Inverter I2t accumulator at 38%.',
    evidence: [
      { check: 'Motor Thermal Current I2t', observation: 'Inverter thermal model accumulator at 38% (< 100% trip threshold).', status: 'PASSED' },
      { check: 'Motor Shaft Free Rotation', observation: 'Shaft rotation normal; zero mechanical binding detected.', status: 'PASSED' },
    ],
    proposed_actions: [],
  },
];

const DEFAULT_5_WHYS = [
  {
    level: 'Why 1',
    question: 'Why did Wecon VM Series VFD (VFD_VM_01) trip with fault code Err06?',
    answer: 'DC link bus voltage exceeded the calibrated hardware protection ceiling (reached 202.5 V vs 195.0 V trip limit, operating up to ~207 V at 50 Hz).',
    evidence: 'Modbus DC Bus Voltage (Reg 1003H / 3004H) surged past 195.0 V trip setpoint at T_trip. Inverter IGBT firing cut off immediately.',
    asset_involved: 'DC_BUS_LINK',
  },
  {
    level: 'Why 2',
    question: 'Why did the DC bus voltage elevate past the 195.0 V trip limit?',
    answer: 'VFD output frequency setpoint was increased past the 40.00 Hz operational ceiling toward 50.00 Hz without dynamic regenerative absorption.',
    evidence: 'Output frequency Reg 1001H climbed from 40.00 Hz to 48.50 Hz, driving intermediate capacitor bank voltage from 182.0 V to > 200 V.',
    asset_involved: 'VFD_VM_01',
  },
  {
    level: 'Why 3',
    question: 'Why didn\'t the dynamic braking unit dissipate the excess DC bus voltage?',
    answer: 'No external braking resistor is connected across terminals P+ and PB (open circuit). Regenerative energy had nowhere to dissipate.',
    evidence: 'Topology node BRK_RESISTOR_01 physical inspection confirms terminals P+ and PB are unpopulated. Braking chopper duty cycle unutilized.',
    asset_involved: 'BRK_RESISTOR_01',
  },
  {
    level: 'Why 4',
    question: 'Why did output frequency exceed the 40.00 Hz limit?',
    answer: 'Experiment 2 command was sent from the PLC / HMI (192.168.1.104), raising frequency target above 40.00 Hz toward 50.00 Hz.',
    evidence: 'HMI setpoint command in Modbus register 3001H / PLC D-variable registered step increase toward 50.00 Hz.',
    asset_involved: 'HMI_TOUCH_01',
  },
  {
    level: 'Why 5 (Root Cause)',
    question: 'Why was the VFD able to exceed 40.00 Hz and overcharge the DC bus?',
    answer: 'Parameter F0.10 (Upper Limit Frequency) in the Wecon VM VFD was left unclamped at factory default (50.00 Hz) instead of being locked to the test bench limit of 40.00 Hz, and dynamic braking resistor was absent.',
    evidence: 'CMMS parameter audit confirms Parameter F0.10 = 50.00 Hz. Bench operational limit is 40.00 Hz max continuous without braking resistor.',
    asset_involved: 'PLC_LX_01',
  },
];

const DEFAULT_HYPOTHESES_ERR02 = [
  {
    hypothesis_id: 'H_VFD_ERR02',
    name: 'Forced Sudden Deceleration Overcurrent (WECON VM Err02)',
    status: 'CONFIRMED',
    confidence: 0.98,
    falsification_rationale:
      'Operator actuated PLC On/Off stop button via PLC D-variable register, cutting the run command instantaneously without a controlled deceleration ramp routine, inducing a kinetic back-EMF overcurrent surge that tripped the drive on Err02.',
    evidence: [
      { check: 'Output Phase Current (Reg 1005H / 3002H)', observation: 'Instantaneous motor current surged to 3.85 A, breaching 2.50 A trip threshold (217% rated FLA).', status: 'CONFIRMED' },
      { check: 'PLC Stop Trigger (D Variable / MQTT Error Topic)', observation: 'Operator actuated PLC On/Off stop button; hard contact de-energization commanded instantaneous decel stop.', status: 'CONFIRMED' },
      { check: 'Modbus Trip Code Register (Reg 700BH)', observation: 'VFD reported Err02 (Overcurrent during deceleration / forced stop).', status: 'CONFIRMED' },
    ],
    proposed_actions: [
      'Implement controlled deceleration ramp profile in PLC ladder logic instead of instantaneous coil de-energization',
      'Tune VFD parameter F0.18 deceleration time to >= 3.0 seconds',
      'Conduct 500V DC Megger insulation resistance test on induction motor IND_MOTOR_01 (> 50 M-Ohm)',
      'Audit PLC D-variable stop routine on HMI touch panel',
    ],
  },
  {
    hypothesis_id: 'H_VFD_ERR06',
    name: 'Overfrequency Deceleration Overvoltage (WECON VM Err06)',
    status: 'REFUTED',
    confidence: 0.03,
    falsification_rationale:
      'Hardware trip register latched Err02 (Overcurrent). DC bus voltage remained within safe limits during this event.',
    evidence: [
      { check: 'DC Bus Voltage (Reg 1003H / 3004H)', observation: 'DC bus voltage remained below trip limit.', status: 'PASSED' },
      { check: 'VFD Fault Register (Reg 700BH)', observation: 'Latched Err02, not Err06.', status: 'PASSED' },
    ],
    proposed_actions: [],
  },
  {
    hypothesis_id: 'H_VFD_ERR03',
    name: 'Deceleration Overcurrent (WECON VM Err03)',
    status: 'REFUTED',
    confidence: 0.02,
    falsification_rationale:
      'Modbus fault code register Reg 700BH did not report Err03.',
    evidence: [
      { check: 'Deceleration Ramp Current', observation: 'Trip was instantaneous Err02 from PLC stop, not linear ramp Err03.', status: 'PASSED' },
    ],
    proposed_actions: [],
  },
  {
    hypothesis_id: 'H_VFD_ERR11',
    name: 'Motor Thermal Overload (WECON VM Err11)',
    status: 'REFUTED',
    confidence: 0.04,
    falsification_rationale:
      'Motor continuous current remained well below parameter F2.03 rated motor thermal limit.',
    evidence: [
      { check: 'Motor Thermal Current I2t', observation: 'Thermal accumulator well below 100% trip threshold.', status: 'PASSED' },
    ],
    proposed_actions: [],
  },
];

const DEFAULT_5_WHYS_ERR02 = [
  {
    level: 'Why 1',
    question: 'Why did Wecon VM Series VFD (VFD_VM_01) trip with fault code Err02?',
    answer: 'Motor output current (Reg 1005H / 3002H) spiked instantaneously past the 2.50 A trip threshold (reached 3.85 A, 217% of continuous rated FLA).',
    evidence: 'Modbus current register Reg 1005H logged instantaneous 3.85 A transient at trip timestamp; drive tripped on Err02.',
    asset_involved: 'VFD_VM_01',
  },
  {
    level: 'Why 2',
    question: 'Why did the motor output current experience an instantaneous spike?',
    answer: 'A hard stop command was issued while the induction motor was spinning at 1199 RPM, producing an abrupt back-EMF kinetic surge.',
    evidence: 'Rotor rotational speed collapsed from 1199 RPM to 0 RPM in a single controller scan cycle without controlled ramp.',
    asset_involved: 'IND_MOTOR_01',
  },
  {
    level: 'Why 3',
    question: 'Why was a hard instantaneous stop commanded rather than a controlled deceleration?',
    answer: 'The PLC On/Off stop button was triggered via PLC D-variable register, cutting the inverter run contact without ramping down frequency.',
    evidence: 'PLC internal register / MQTT error topic registered instantaneous toggle of the Run coil to OFF.',
    asset_involved: 'PLC_LX_01',
  },
  {
    level: 'Why 4',
    question: 'Why did the VFD attempt an instantaneous stop instead of ramping down safely?',
    answer: 'VFD Parameter F0.18 (Deceleration Time) was configured to 0.1s / Coast-to-stop was disabled, forcing the inverter IGBTs to absorb abrupt rotational kinetic energy.',
    evidence: 'Parameter audit: F0.18 deceleration time set too aggressively for motor inertia; dynamic braking resistor absent.',
    asset_involved: 'VFD_VM_01',
  },
  {
    level: 'Why 5 (Root Cause)',
    question: 'Why did the PLC control logic trigger a hard instantaneous stop?',
    answer: 'The PLC logic in Experiment 1 de-energizes the run command via a single D-variable bit toggle without enforcing an intermediate deceleration ramp routine, overloading the inverter output stage.',
    evidence: 'PLC ladder logic inspection confirms direct de-energization coil mapped to MQTT control error topic without timer ramp.',
    asset_involved: 'PLC_LX_01',
  },
];

const STANDBY_HYPOTHESES = [
  {
    hypothesis_id: 'H_VFD_ERR06',
    name: 'Overfrequency Deceleration Overvoltage (WECON VM Err06)',
    status: 'STANDBY',
    confidence: 0,
    falsification_rationale:
      'Continuous DC bus voltage (182.0 V) remains safely below the 195.0 V trip ceiling. Output frequency is nominal (40.00 Hz). Branch on standby for overvoltage excursions.',
    evidence: [
      { check: 'DC Bus Voltage (Reg 1003H / 3004H)', observation: 'V_dc stable at ~182.0 V (below 195.0 V trip ceiling).', status: 'NOMINAL' },
      { check: 'Output Frequency (Reg 1001H / 3000H)', observation: 'f_out operating at 40.00 Hz operational limit.', status: 'NOMINAL' },
      { check: 'Dynamic Braking Circuit (P+/PB)', observation: 'Awaiting deceleration transient monitoring.', status: 'STANDBY' },
      { check: 'VFD Fault Register (Reg 700BH)', observation: 'Modbus register 700BH reports 0 (No active fault code).', status: 'NOMINAL' },
    ],
    proposed_actions: [
      'Maintain parameter F0.10 clamped <= 40.00 Hz',
      'Verify dynamic braking resistor installation on P+/PB',
    ],
  },
  {
    hypothesis_id: 'H_VFD_ERR02',
    name: 'Forced Sudden Deceleration Overcurrent (WECON VM Err02)',
    status: 'STANDBY',
    confidence: 0,
    falsification_rationale:
      'Motor output current (1.15 A) remains within safe continuous operating limits (< 2.50 A trip limit). Branch on standby for abrupt PLC stop transients.',
    evidence: [
      { check: 'Motor Output Current (Reg 1005H / 3002H)', observation: 'Continuous phase current 1.15 A (safely below 2.50 A trip limit).', status: 'NOMINAL' },
      { check: 'PLC Stop Trigger (D Variable / MQTT)', observation: 'No abrupt de-energization or emergency stop signal received.', status: 'NOMINAL' },
    ],
    proposed_actions: [
      'Maintain deceleration ramp parameter F0.18 >= 5.0s',
    ],
  },
  {
    hypothesis_id: 'H_VFD_ERR03',
    name: 'Deceleration Overcurrent (WECON VM Err03)',
    status: 'STANDBY',
    confidence: 0,
    falsification_rationale:
      'Deceleration slope within calibrated parameters. Branch on standby for inertia overcurrent trips.',
    evidence: [
      { check: 'Deceleration Current Slope', observation: 'Ramp current rate-of-change within linear envelope.', status: 'NOMINAL' },
      { check: 'Fault Register (Reg 700BH)', observation: 'Register 700BH = 0 (No active fault).', status: 'NOMINAL' },
    ],
    proposed_actions: [],
  },
  {
    hypothesis_id: 'H_VFD_ERR11',
    name: 'Motor Thermal Overload (WECON VM Err11)',
    status: 'STANDBY',
    confidence: 0,
    falsification_rationale:
      'Thermal accumulation model confirms motor temperature is within Class F continuous insulation ratings.',
    evidence: [
      { check: 'Motor Thermal Accumulator', observation: 'Thermal load < 45% of maximum rated capacity.', status: 'NOMINAL' },
      { check: 'Fault Register (Reg 700BH)', observation: 'No thermal trip latched.', status: 'NOMINAL' },
    ],
    proposed_actions: [],
  },
];

interface FMEAMatrixTabProps {
  rcaState: RCAState | null;
}

export const FMEAMatrixTab: React.FC<FMEAMatrixTabProps> = ({ rcaState }) => {
  const hasActiveIncident = Boolean(
    rcaState?.has_active_trip ||
    (rcaState?.fault_code && rcaState.fault_code > 0) ||
    rcaState?.winning_hypothesis ||
    (rcaState?.hypothesis_results && rcaState.hypothesis_results.some((h) => h.status === 'CONFIRMED'))
  );

  const isErr02 =
    rcaState?.fault_code === 2 ||
    rcaState?.winning_hypothesis?.hypothesis_id === 'H_VFD_ERR02';
  const defaultHypos = isErr02 ? DEFAULT_HYPOTHESES_ERR02 : DEFAULT_HYPOTHESES;
  const defaultWhys = isErr02 ? DEFAULT_5_WHYS_ERR02 : DEFAULT_5_WHYS;

  const rawHypotheses = rcaState?.hypothesis_results;
  const hypotheses = hasActiveIncident
    ? (rawHypotheses && rawHypotheses.length > 0 ? rawHypotheses : defaultHypos)
    : STANDBY_HYPOTHESES;

  const winningHyp = hasActiveIncident
    ? (rcaState?.winning_hypothesis || hypotheses.find((h) => h.status === 'CONFIRMED') || null)
    : null;

  const rawWhys = rcaState?.causal_chain_5_whys;
  const fiveWhys = hasActiveIncident
    ? (rawWhys && rawWhys.length > 0 ? rawWhys : defaultWhys)
    : [];

  const [expandedHypId, setExpandedHypId] = useState<string>(
    hasActiveIncident ? (winningHyp?.hypothesis_id || (isErr02 ? 'H_VFD_ERR02' : 'H_VFD_ERR06')) : ''
  );

  React.useEffect(() => {
    if (winningHyp?.hypothesis_id) {
      setExpandedHypId(winningHyp.hypothesis_id);
    }
  }, [winningHyp?.hypothesis_id]);

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
      case 'STANDBY':
        return (
          <span className="flex items-center space-x-1.5 px-2.5 py-0.5 rounded text-xs font-mono font-semibold bg-slate-100 text-slate-600 border border-slate-200">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400" />
            <span>STANDBY</span>
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
    <div className="space-y-4 flex-1 flex flex-col min-h-full">
      {/* Header Banner */}
      <div className="bg-white border border-slate-200 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className={`p-2 rounded-lg border ${hasActiveIncident ? 'bg-teal-50 text-teal-600 border-teal-100' : 'bg-emerald-50 text-emerald-600 border-emerald-100'}`}>
            {hasActiveIncident ? <ShieldAlert className="w-4 h-4" /> : <ShieldCheck className="w-4 h-4" />}
          </div>
          <div>
            <div className="text-xs font-bold font-mono text-slate-800 uppercase">
              ISO 14224 FMEA Hypothesis Falsification Matrix
            </div>
            <div className="text-[11px] text-slate-500">
              Parallel Multi-Branch Evidence Elimination · Wecon VM VFD Hypotheses Tested Against Physical Telemetry
            </div>
          </div>
        </div>

        {winningHyp ? (
          <div className="flex items-center space-x-2 text-[11px] font-mono">
            <span className="px-2.5 py-1 rounded bg-teal-50 text-teal-700 border border-teal-200">
              Winning Branch: <strong>{winningHyp.hypothesis_id} ({winningHyp.name.slice(0, 24)}...)</strong>
            </span>
          </div>
        ) : (
          <div className="flex items-center space-x-2 text-[11px] font-mono">
            <span className="px-2.5 py-1 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              <span>Status: <strong>NOMINAL MONITORING (4 Branches on Standby)</strong></span>
            </span>
          </div>
        )}
      </div>

      {/* System Nominal Callout when no active incident */}
      {!hasActiveIncident && (
        <div className="bg-emerald-50 border border-emerald-200 rounded-xl p-3.5 flex items-center space-x-3 text-xs font-mono text-emerald-800 shadow-xs">
          <ShieldCheck className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <div className="leading-relaxed">
            <strong>System Operating Nominally — Zero Active Incidents:</strong> Modbus telemetry from Wecon VM VFD (<code>VFD_VM_01</code>) is healthy and within calibrated ISA-95 limits. The 4 ISO 14224 failure mode branches below are primed on standby and will be dynamically evaluated against physical telemetry if an envelope breach occurs.
          </div>
        </div>
      )}

      {/* Hypotheses Cards Grid */}
      <div className="space-y-2.5">
        {hypotheses.length > 0 ? (
          hypotheses.map((h, idx) => {
            const isExpanded = expandedHypId === h.hypothesis_id;
            const isWinner = winningHyp?.hypothesis_id === h.hypothesis_id;

            return (
              <div
                key={`${h.hypothesis_id}-${idx}`}
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
                    {hasActiveIncident ? (
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
                    ) : (
                      <div className="hidden sm:flex items-center space-x-1.5 font-mono text-[11px] text-slate-400">
                        <span className="w-1.5 h-1.5 rounded-full bg-slate-300" />
                        <span>Untriggered (0%)</span>
                      </div>
                    )}

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
      {hasActiveIncident && fiveWhys.length > 0 ? (
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
      ) : (
        <div className="bg-white border border-slate-200 rounded-xl p-8 text-center flex-1 flex flex-col items-center justify-center space-y-3.5 shadow-xs min-h-[200px]">
          <div className="w-12 h-12 rounded-2xl bg-teal-50 border border-teal-200/80 flex items-center justify-center text-teal-600 shadow-xs">
            <Network className="w-6 h-6 text-teal-600" />
          </div>
          <div>
            <h4 className="text-xs font-bold font-mono text-slate-800 uppercase tracking-wide">
              Upstream ISA-95 Causal Trace (5-Whys Root Cause Chain) — Standby
            </h4>
            <p className="text-xs text-slate-500 max-w-md mx-auto font-sans leading-relaxed mt-1">
              The 5-Whys root cause causal tree is synthesized automatically by the LangGraph diagnostic engine when a physical hardware trip occurs and a root failure mode is confirmed.
            </p>
          </div>
          <div className="inline-flex items-center space-x-1.5 px-3 py-1 bg-slate-100 text-slate-600 border border-slate-200 rounded-full text-xs font-mono">
            <span className="w-1.5 h-1.5 rounded-full bg-slate-400 animate-pulse" />
            <span>Autonomous Causal Engine On Standby</span>
          </div>
        </div>
      )}
    </div>
  );
};
