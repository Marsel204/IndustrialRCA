import React, { useState } from 'react';
import {
  FileCheck2,
  Printer,
  Copy,
  Check,
  ShieldCheck,
  Wrench,
  Package,
} from 'lucide-react';
import { RCAState } from '../../types';

interface DeliverablesTabProps {
  rcaState: RCAState | null;
}

const DEFAULT_OPERATIONS = [
  {
    operation_number: '0010',
    work_center: 'ELEC-01',
    duration_hours: 1.0,
    description: 'Lock-Out/Tag-Out (LOTO) & DC Bus Safe Discharge Verification',
    details: 'Open main circuit breaker CB_01. Measure DC link voltage on terminals + and - with calibrated DMM; verify V_dc < 24.0V before servicing.',
  },
  {
    operation_number: '0020',
    work_center: 'ELEC-01',
    duration_hours: 2.0,
    description: 'Dynamic Braking Resistor Inspection & Installation (P+/PB)',
    details: 'Inspect braking transistor chopper. Install 70-Ohm 150W ceramic dynamic braking resistor across terminals P+ and PB to dissipate regenerative decel energy.',
  },
  {
    operation_number: '0030',
    work_center: 'AUTO-01',
    duration_hours: 1.5,
    description: 'Inverter & PLC Parameter Reprogramming',
    details: 'Program deceleration ramp parameter F0.18 to controlled 5.0s (prevent rapid stop current spike). Set max frequency clamp F0.10 <= 40.00 Hz and enable DC overvoltage stall prevention F3.08.',
  },
  {
    operation_number: '0040',
    work_center: 'ELEC-01',
    duration_hours: 1.5,
    description: 'Induction Motor Megger & Phase Balance Testing',
    details: 'Perform 500V DC megger test on motor phases U, V, W to PE (>50 M-Ohm required). Measure phase-to-phase resistance balance (<1% unbalance).',
  },
  {
    operation_number: '0050',
    work_center: 'OPS-01',
    duration_hours: 1.5,
    description: 'Step-Speed Commissioning & Decel Load Sign-Off',
    details: 'Energize drive, step speed across 10 Hz, 25 Hz, 40 Hz. Verify DC bus voltage remains within 170.0V - 190.0V envelope during controlled stop without trip.',
  },
];

const DEFAULT_MATERIALS = [
  { material_id: 'MAT-VFD-BRK70', description: '70-Ohm 150W Wirewound Dynamic Braking Resistor Unit', quantity: 1, unit: 'EA' },
  { material_id: 'MAT-CBL-4C25', description: '4-Core 2.5mm2 Shielded VFD Inverter Motor Cable', quantity: 5, unit: 'M' },
  { material_id: 'MAT-BRK-MCCB16', description: '16A 2-Pole Molded Case Circuit Breaker (MCCB)', quantity: 1, unit: 'EA' },
  { material_id: 'MAT-COMM-RS485', description: 'Shielded Twisted Pair RS-485 Modbus RTU Comm Cable', quantity: 2, unit: 'M' },
];

export const DeliverablesTab: React.FC<DeliverablesTabProps> = ({ rcaState }) => {
  const [subView, setSubView] = useState<'8d' | 'sap' | 'sop'>('8d');
  const [copied, setCopied] = useState<boolean>(false);
  const [sopChecked, setSopChecked] = useState<Record<string, boolean>>({
    'sop-1': true,
    'sop-2': true,
    'sop-3': false,
    'sop-4': false,
    'sop-5': false,
  });

  const report8D = rcaState?.incident_report_8d;
  const sapOrder = rcaState?.sap_work_order;
  const operations = sapOrder?.operations && sapOrder.operations.length > 0 ? sapOrder.operations : DEFAULT_OPERATIONS;
  const materials = sapOrder?.materials_required && sapOrder.materials_required.length > 0 ? sapOrder.materials_required : DEFAULT_MATERIALS;

  const toggleSop = (id: string) => {
    setSopChecked((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const handleCopyJSON = () => {
    const exportData = {
      incident_report_8d: report8D,
      sap_work_order: sapOrder,
    };
    navigator.clipboard.writeText(JSON.stringify(exportData, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handlePrint = () => {
    window.print();
  };

  const hasActiveIncident = Boolean(
    rcaState?.has_active_trip ||
    (rcaState?.fault_code && rcaState.fault_code > 0) ||
    rcaState?.winning_hypothesis ||
    rcaState?.incident_report_8d ||
    rcaState?.sap_work_order
  );

  const isErr02 =
    rcaState?.fault_code === 2 ||
    rcaState?.winning_hypothesis?.hypothesis_id === 'H_VFD_ERR02' ||
    rcaState?.winning_hypothesis?.name?.includes('Err02') ||
    rcaState?.root_cause_description?.includes('Err02') ||
    false;

  return (
    <div className="space-y-4">
      {/* Top Banner & Sub-View Switcher */}
      <div className="bg-white border border-slate-200 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-3 shadow-xs">
        <div className="flex items-center space-x-3">
          <div className="p-2 rounded-lg bg-teal-50 text-teal-600 border border-teal-100">
            <FileCheck2 className="w-4 h-4" />
          </div>
          <div>
            <div className="text-xs font-bold font-mono text-slate-800 uppercase">
              Formal Maintenance Deliverables & Investigation Artifacts
            </div>
            <div className="text-[11px] text-slate-500">
              Global 8D Standard Incident Report · SAP S/4HANA PM01 Work Order · Corrective SOP
            </div>
          </div>
        </div>

        {/* Action Buttons */}
        {hasActiveIncident && (
          <div className="flex items-center space-x-2">
            {/* View Selector Pills */}
            <div className="flex items-center bg-slate-100 border border-slate-200 rounded-lg p-0.5 text-xs font-mono">
              <button
                onClick={() => setSubView('8d')}
                className={`px-3 py-1 rounded-md transition-colors cursor-pointer ${
                  subView === '8d'
                    ? 'bg-white text-slate-900 font-bold shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                8D Report
              </button>
              <button
                onClick={() => setSubView('sap')}
                className={`px-3 py-1 rounded-md transition-colors cursor-pointer ${
                  subView === 'sap'
                    ? 'bg-white text-slate-900 font-bold shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                SAP PM01 Order
              </button>
              <button
                onClick={() => setSubView('sop')}
                className={`px-3 py-1 rounded-md transition-colors cursor-pointer ${
                  subView === 'sop'
                    ? 'bg-white text-slate-900 font-bold shadow-xs'
                    : 'text-slate-600 hover:text-slate-900'
                }`}
              >
                SOP Checklist
              </button>
            </div>

            <button
              onClick={handleCopyJSON}
              className="flex items-center space-x-1 px-3 py-1 bg-white hover:bg-slate-50 border border-slate-200 text-xs font-mono text-slate-700 rounded-lg shadow-xs transition-colors cursor-pointer"
              title="Copy all artifact JSON to clipboard"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-teal-600" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied!' : 'Copy JSON'}</span>
            </button>

            <button
              onClick={handlePrint}
              className="flex items-center space-x-1 px-3 py-1 bg-white hover:bg-slate-50 border border-slate-200 text-xs font-mono text-slate-700 rounded-lg shadow-xs transition-colors cursor-pointer"
            >
              <Printer className="w-3.5 h-3.5" />
              <span>Print</span>
            </button>
          </div>
        )}
      </div>

      {/* Nominal State View */}
      {!hasActiveIncident ? (
        <div className="bg-white border border-slate-200 rounded-xl p-10 text-center space-y-3 shadow-xs">
          <div className="w-12 h-12 rounded-full bg-emerald-50 border border-emerald-200 flex items-center justify-center text-emerald-600 mx-auto">
            <ShieldCheck className="w-6 h-6" />
          </div>
          <h3 className="text-sm font-bold text-slate-900 font-mono">
            System Operating Nominally — Zero Active Incidents
          </h3>
          <p className="text-xs text-slate-500 max-w-lg mx-auto leading-relaxed">
            The Wecon VM VFD (VFD_VM_01) telemetry is healthy and operating within calibrated ISA-95 envelopes.
            Global 8D Investigation Reports and SAP S/4HANA PM01 Maintenance Work Orders are generated automatically when a hardware trip occurs.
          </p>
          <div className="inline-flex items-center space-x-2 px-3 py-1 bg-emerald-50 text-emerald-700 border border-emerald-200 rounded-full text-xs font-mono">
            <span className="w-2 h-2 rounded-full bg-emerald-500" />
            <span>Autonomous Ingestion Active · Modbus 1 Hz Stream Nominal</span>
          </div>
        </div>
      ) : (
        <>
          {/* Artifact View 1: 8D Incident Report */}
          {subView === '8d' && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-5">
          {/* 8D Document Header */}
          <div className="border-b border-slate-100 pb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[11px] font-mono text-teal-700 font-bold tracking-wider uppercase">
                Global 8D Standard Root Cause Corrective Action (RCCA)
              </div>
              <h2 className="text-base font-bold text-slate-900">
                Incident Investigation Report: {report8D?.incident_id || 'INC-2026-0915-VFD'}
              </h2>
              <div className="text-xs font-mono text-slate-500 mt-0.5">
                Asset: {report8D?.asset_id || 'VFD_VM_01'} ({report8D?.asset_name || 'Wecon VM Series Variable Frequency Drive'}) · Classification: Level 1 Critical Test Rig Inverter Trip
              </div>
            </div>

            <div className="text-right font-mono text-xs text-slate-500">
              <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold block mb-1">
                STATUS: CLOSED & APPROVED
              </span>
              <span>Date: 2026-09-15 · Automation Test Facility</span>
            </div>
          </div>

          {/* 8 Disciplines Cards */}
          <div className="space-y-3">
            {/* D1 */}
            <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
              <div className="font-mono text-xs font-bold text-teal-800 uppercase tracking-wider">
                D1: Cross-Functional Team Establishment
              </div>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs font-mono pt-1 text-slate-700">
                <div>
                  <span className="text-slate-500 block text-[10px]">Incident Lead</span>
                  <span className="font-semibold">{report8D?.d1_team?.lead || 'M. Al-Hassan (Lead Automation Specialist)'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Operations Lead</span>
                  <span className="font-semibold">{report8D?.d1_team?.operations || 'A. Chen (PLC Controls Engineer)'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Electrical Specialist</span>
                  <span className="font-semibold">{report8D?.d1_team?.process_eng || 'E. Zhao (Power Electronics Engineer)'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">CMMS Planner</span>
                  <span className="font-semibold">{report8D?.d1_team?.cmms_planner || 'K. Vance (Lab Maintenance Coordinator)'}</span>
                </div>
              </div>
            </div>

            {/* D2 */}
            <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
              <div className="font-mono text-xs font-bold text-teal-800 uppercase tracking-wider">
                D2: Problem Description (5W2H)
              </div>
              <div className="text-xs text-slate-700 space-y-1 leading-relaxed font-sans">
                <p>
                  <strong>What:</strong> {report8D?.d2_problem_description?.what || (isErr02 ? 'Unplanned trip of Wecon VM Series VFD (VFD_VM_01) with fault code Err02 (Forced Deceleration Overcurrent).' : 'Unplanned trip of Wecon VM Series VFD (VFD_VM_01) with fault code Err06 (Overfrequency Deceleration Overvoltage).')}
                </p>
                <p>
                  <strong>When & Where:</strong> {report8D?.d2_problem_description?.when || '2026-09-15 14:10:00'} · {report8D?.d2_problem_description?.where || 'Industrial Automation Test Facility - Bench 01 (PLC LX3V + Wecon VM VFD)'}
                </p>
                <p>
                  <strong>Impact:</strong> {report8D?.d2_problem_description?.how_much || (isErr02 ? 'Instantaneous motor current surged to 3.85 A, breaching 2.50 A trip threshold.' : 'Frequency setpoint exceeded 40.00 Hz ceiling toward 50.00 Hz, driving DC bus voltage to 202.5 V (> 195.0 V trip limit).')}{' '}
                  {report8D?.d2_problem_description?.operational_impact || 'Inverter IGBT gate drive inhibited to protect power module and induction motor from thermal damage.'}
                </p>
              </div>
            </div>

            {/* D3 */}
            <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
              <div className="font-mono text-xs font-bold text-teal-800 uppercase tracking-wider">
                D3: Interim Containment Actions (ICA)
              </div>
              <ul className="list-disc pl-5 text-xs text-slate-700 space-y-0.5 font-sans">
                <li>Verify VFD display indicates trip code {isErr02 ? 'Err02' : 'Err06'} and output current/voltage have dropped to 0.</li>
                <li>Confirm DC bus voltage has safely discharged below 24 V before opening enclosure.</li>
                <li>Toggle PLC reset trigger (D-variable / MQTT error topic) to clear fault latch after root cause diagnosis.</li>
              </ul>
            </div>

            {/* D4 */}
            <div className="p-3.5 rounded-lg bg-rose-50/40 border border-rose-200 space-y-1.5">
              <div className="font-mono text-xs font-bold text-rose-700 uppercase tracking-wider">
                D4: Root Cause Analysis & FMEA Verification
              </div>
              <div className="text-xs text-slate-800 font-sans space-y-1">
                <p>
                  <strong>Root Cause Origin:</strong>{' '}
                  <span className="font-mono text-rose-800 font-bold">
                    {report8D?.d4_root_cause_analysis?.root_cause_asset || 'PLC_LX_01 (PLC Controller) / VFD_VM_01 Parameter F0.10'}
                  </span>
                </p>
                <p>
                  <strong>Failure Mechanism:</strong>{' '}
                  <span className="font-mono text-blue-800">
                    {report8D?.d4_root_cause_analysis?.failure_mechanism || 'Overfrequency excursion / Regenerative kinetic energy without braking resistor'}
                  </span>{' '}
                  (ISO 14224: <code>{report8D?.d4_root_cause_analysis?.iso_14224_code || 'ISO-14224-DR-ELC-OVV'}</code>)
                </p>
                <p className="pt-0.5 text-slate-700 leading-relaxed">
                  {report8D?.d4_root_cause_analysis?.root_cause_statement ||
                    'Output frequency setpoint was ramped past the 40.00 Hz operational ceiling toward 50.00 Hz, causing DC bus voltage to escalate to 202.5 V (breaching the calibrated 195.0 V trip limit) because Wecon VM parameter F0.10 was unclamped and dynamic braking resistor terminals P+/PB were unpopulated.'}
                </p>
              </div>
            </div>

            {/* D5 & D6 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                <div className="font-mono text-xs font-bold text-teal-800 uppercase tracking-wider">
                  D5: Permanent Corrective Actions (PCA)
                </div>
                <ul className="list-disc pl-5 text-xs text-slate-700 space-y-0.5 font-sans">
                  <li>Lock parameter F0.10 (Upper Frequency Limit) to 40.00 Hz in Wecon VM VFD.</li>
                  <li>Install dynamic braking resistor (nominal 70-100 Ohm, 100-150W) across terminals P+ and PB.</li>
                  <li>Configure high DC bus pre-alarm in HMI at 190.0 V (trip limit: 195.0 V).</li>
                  <li>Adjust parameter F0.18 deceleration ramp time to &gt;= 5.0 seconds.</li>
                </ul>
              </div>

              <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                <div className="font-mono text-xs font-bold text-teal-800 uppercase tracking-wider">
                  D6: Implement & Validate PCA
                </div>
                <div className="text-xs text-slate-700 space-y-0.5 font-sans">
                  <p>
                    <strong>Validation Protocol:</strong> Baseline 15-minute steady-state run at 40.00 Hz followed by controlled start/stop cycles.
                  </p>
                  <p>
                    <strong>Acceptance Criteria:</strong> DC bus voltage stable at ~182 V (never exceeding 190 V alarm / 195 V trip limit), current &lt; 1.50 A, zero trip codes.
                  </p>
                </div>
              </div>
            </div>

            {/* D7 & D8 */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                <div className="font-mono text-xs font-bold text-teal-800 uppercase tracking-wider">
                  D7: Systemic Prevention
                </div>
                <ul className="list-disc pl-5 text-xs text-slate-700 space-y-0.5 font-sans">
                  <li>Standardize PLC program template with ramped stop routines across all test benches.</li>
                  <li>Require dynamic braking resistor installation for any bench configured for variable deceleration.</li>
                  <li>Store parameter backups in CMMS (WO-VFD-2026-0042) to prevent unauthorized frequency setpoint adjustments.</li>
                </ul>
              </div>

              <div className="p-3.5 rounded-lg bg-emerald-50/40 border border-emerald-200 space-y-1">
                <div className="font-mono text-xs font-bold text-emerald-800 uppercase tracking-wider flex items-center space-x-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span>D8: Engineer Authorization</span>
                </div>
                <div className="text-xs font-mono text-slate-700 space-y-0.5">
                  <p>Reviewed by: <strong className="text-slate-900">{report8D?.d8_sign_off?.reviewed_by || 'M. Al-Hassan (Lead Automation Specialist)'}</strong></p>
                  <p>Status: <span className="text-emerald-700 font-bold">APPROVED & RELEASED</span></p>
                  <p className="text-slate-500 text-[11px]">Notes: {report8D?.d8_sign_off?.review_notes || 'Root cause verified by multi-sensor Modbus telemetry and PLC state correlation.'}</p>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Artifact View 2: SAP PM01 Work Order */}
      {subView === 'sap' && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-5">
          {/* SAP Header */}
          <div className="border-b border-slate-100 pb-4 flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="text-[11px] font-mono text-blue-700 font-bold tracking-wider uppercase">
                SAP S/4HANA Plant Maintenance (PM) Order PM01
              </div>
              <h2 className="text-base font-bold text-slate-900">
                Work Order #{sapOrder?.order_number || '40092841'} · Notification #{sapOrder?.notification_number || '10082914'}
              </h2>
              <div className="text-xs font-mono text-slate-500 mt-0.5">
                Equipment: {sapOrder?.equipment_id || '10049201'} - {sapOrder?.equipment_name || 'VFD_VM_01 Wecon VM Series Inverter & Motor Bench'}
              </div>
            </div>

            <div className="text-right font-mono text-xs">
              <span className="px-2 py-0.5 rounded bg-amber-50 text-amber-700 border border-amber-200 font-bold block mb-1">
                {sapOrder?.priority || '1 - Emergency / Immediate Outage'}
              </span>
              <span className="text-slate-500">System Status: {sapOrder?.system_status || 'CRTD REL PMCO'}</span>
            </div>
          </div>

          {/* SAP Metadata Grid */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2 text-xs font-mono">
            <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
              <span className="text-slate-500 block text-[10px]">Order Type</span>
              <span className="font-bold text-slate-800">{sapOrder?.order_type || 'PM01'} (Corrective)</span>
            </div>
            <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
              <span className="text-slate-500 block text-[10px]">Functional Location</span>
              <span className="font-bold text-slate-800">{sapOrder?.functional_location || 'FLOC: PLNT-B01-VFD-BENCH01'}</span>
            </div>
            <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
              <span className="text-slate-500 block text-[10px]">Cost Center</span>
              <span className="font-bold text-slate-800">{sapOrder?.cost_center || 'CC-ELEC-01'}</span>
            </div>
            <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
              <span className="text-slate-500 block text-[10px]">Total Est. Hours</span>
              <span className="font-bold text-teal-700">{sapOrder?.total_estimated_hours || 7.5} Hours</span>
            </div>
          </div>

          {/* Short Text / Scope */}
          <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1 text-xs">
            <div className="font-mono text-slate-500 font-bold">Scope of Work:</div>
            <div className="font-semibold text-slate-900">{sapOrder?.short_text || 'RCA Remediation: VFD_VM_01 Drive Trip Recovery & Dynamic Braking Resistor Retrofit'}</div>
            <div className="text-slate-600 font-sans text-xs pt-0.5 leading-relaxed">
              {sapOrder?.long_text || 'Root Cause: DC bus voltage surged past 195.0 V during overfrequency excursion (>40 Hz) with missing dynamic braking resistor. Action Required: Install dynamic braking resistor on terminals P+/PB, adjust parameter F0.18 to controlled ramp, clamp max frequency F0.10 <= 40.0 Hz, and verify under step-speed commissioning.'}
            </div>
          </div>

          {/* Maintenance Task List Operations */}
          <div className="space-y-2">
            <div className="font-mono text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-1.5">
              <Wrench className="w-3.5 h-3.5 text-blue-600" />
              <span>Operations / Maintenance Task List:</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono border-collapse border border-slate-200 rounded-lg">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-600">
                    <th className="p-2">Op</th>
                    <th className="p-2">Work Center</th>
                    <th className="p-2">Duration</th>
                    <th className="p-2">Task Description</th>
                    <th className="p-2">Execution Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {operations.map((op) => (
                    <tr key={op.operation_number} className="hover:bg-slate-50/50">
                      <td className="p-2 font-bold text-blue-700">{op.operation_number}</td>
                      <td className="p-2 text-amber-700">{op.work_center}</td>
                      <td className="p-2 text-teal-700 font-bold">{op.duration_hours} h</td>
                      <td className="p-2 font-bold text-slate-800">{op.description}</td>
                      <td className="p-2 text-slate-600 font-sans text-xs">{op.details}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Bill of Materials (BOM) Table */}
          <div className="space-y-2">
            <div className="font-mono text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center space-x-1.5">
              <Package className="w-3.5 h-3.5 text-teal-600" />
              <span>Required Bill of Materials (BOM):</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs font-mono border-collapse border border-slate-200 rounded-lg">
                <thead>
                  <tr className="bg-slate-50 border-b border-slate-200 text-slate-600">
                    <th className="p-2">Material ID</th>
                    <th className="p-2">Description</th>
                    <th className="p-2">Quantity</th>
                    <th className="p-2">Unit</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {materials.map((mat) => (
                    <tr key={mat.material_id} className="hover:bg-slate-50/50">
                      <td className="p-2 font-bold text-blue-700">{mat.material_id}</td>
                      <td className="p-2 text-slate-800">{mat.description}</td>
                      <td className="p-2 text-teal-700 font-bold">{mat.quantity}</td>
                      <td className="p-2 text-slate-500">{mat.unit}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Artifact View 3: SOP Action Checklist */}
      {subView === 'sop' && (
        <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-5">
          <div className="border-b border-slate-100 pb-3">
            <div className="text-[11px] font-mono text-teal-700 font-bold tracking-wider uppercase">
              Standard Operating Procedure (SOP-VFD-001)
            </div>
            <h2 className="text-base font-bold text-slate-900">
              Wecon VM Series VFD Overvoltage Trip Recovery & Dynamic Braking Resistor Retrofit
            </h2>
            <div className="text-xs font-mono text-slate-500 mt-0.5">
              Safety Class: Critical Power Electronics · LOTO & DC Bus Capacitor Discharge Verification Required
            </div>
          </div>

          <div className="space-y-2.5 font-mono text-xs">
            {[
              {
                id: 'sop-1',
                title: 'Phase 1: Lockout/Tagout (LOTO) & DC Bus Discharge Verification',
                desc: 'Open main breaker CB_01. Measure DC link voltage on terminals + and - with calibrated DMM; verify V_dc < 24.0V before servicing.',
              },
              {
                id: 'sop-2',
                title: 'Phase 2: Dynamic Braking Resistor Installation (Terminals P+/PB)',
                desc: 'Mount 70-Ohm 150W wirewound dynamic braking resistor on DIN rail with ceramic standoffs. Wire to terminals P+ and PB using 2.5mm2 shielded silicone cable.',
              },
              {
                id: 'sop-3',
                title: 'Phase 3: Parameter Reprogramming & Frequency Clamping',
                desc: 'Connect Wecon HMI/keypad. Set max frequency clamp F0.10 <= 40.00 Hz. Configure F0.18 deceleration ramp time to 5.0s. Enable stall prevention F3.08.',
              },
              {
                id: 'sop-4',
                title: 'Phase 4: Induction Motor Stator Megger & Phase Balance Testing',
                desc: 'Perform 500V DC megger test on motor phases U, V, W to PE (> 50 M-Ohm required). Measure phase resistance balance (< 1% unbalance).',
              },
              {
                id: 'sop-5',
                title: 'Phase 5: Step-Speed Commissioning & Decel Load Sign-Off',
                desc: 'Energize drive, step speed across 10 Hz, 25 Hz, 40 Hz. Verify DC bus voltage remains within 170.0V - 190.0V envelope during controlled stop without trip.',
              },
            ].map((step) => {
              const isChecked = sopChecked[step.id];
              return (
                <div
                  key={step.id}
                  onClick={() => toggleSop(step.id)}
                  className={`p-3.5 rounded-lg border transition-all cursor-pointer flex items-start space-x-3 ${
                    isChecked
                      ? 'bg-emerald-50/40 border-emerald-300 text-slate-900'
                      : 'bg-slate-50/50 border-slate-200 text-slate-700 hover:border-slate-300'
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={isChecked}
                    onChange={() => {}}
                    className="mt-0.5 w-4 h-4 rounded accent-teal-600 cursor-pointer"
                  />
                  <div className="space-y-0.5">
                    <div className={`font-bold ${isChecked ? 'text-emerald-800' : 'text-slate-900'}`}>
                      {step.title}
                    </div>
                    <p className="text-xs text-slate-600 font-sans leading-relaxed">
                      {step.desc}
                    </p>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}
        </>
      )}
    </div>
  );
};
