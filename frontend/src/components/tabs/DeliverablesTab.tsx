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
    work_center: 'MECH',
    duration_hours: 4.0,
    description: 'Strainer STR-301A Overhaul & Chemical Flush',
    details: 'Depressurize, unbolt cover, pull 20-mesh basket, inspect for marine biofouling and particulate cake. Chemically flush with citric acid.',
  },
  {
    operation_number: '0020',
    work_center: 'MECH',
    duration_hours: 3.5,
    description: 'First-Stage Impeller Suction Eye Boroscopy',
    details: 'Insert flexible boroscope through suction casing port. Inspect suction vanes for cavitation erosion pitting depth (<0.5mm allowable).',
  },
  {
    operation_number: '0030',
    work_center: 'MECH',
    duration_hours: 4.5,
    description: 'Drive-End Sleeve Bearing Clearance & Shell Inspection',
    details: 'Disassemble DE bearing housing. Measure radial clearance using Plastigage (Target: 0.12 - 0.18 mm). Inspect Babbitt surface.',
  },
  {
    operation_number: '0040',
    work_center: 'LUBE',
    duration_hours: 1.5,
    description: 'Lube Oil Reservoir Drain, Solvent Flush & Charge',
    details: 'Drain degraded oil reservoir. Solvent-flush housing. Charge 40 L fresh ISO VG 46 synthetic turbine lube oil.',
  },
  {
    operation_number: '0050',
    work_center: 'ELEC',
    duration_hours: 1.5,
    description: 'Motor Stator Insulation Megger & Laser Alignment',
    details: 'Megger 3.3 kV motor stator windings (>100 MΩ). Perform laser shaft alignment (angular < 0.05 mm, parallel offset < 0.05 mm).',
  },
];

const DEFAULT_MATERIALS = [
  { material_id: 'MAT-STR-20M', description: '20-Mesh Dual Basket Element (316L SS)', quantity: 1, unit: 'EA' },
  { material_id: 'MAT-BRG-SLV-DE', description: 'Babbitt Sleeve Bearing Shell Pair DE', quantity: 1, unit: 'SET' },
  { material_id: 'MAT-OIL-VG46', description: 'Mobil DTE 846 ISO VG 46 Turbine Lube Oil', quantity: 40, unit: 'L' },
  { material_id: 'MAT-GSK-300', description: 'Spiral Wound Casing Gasket 12" Class 600', quantity: 2, unit: 'EA' },
  { material_id: 'MAT-PLAST-GRN', description: 'Plastigage Green (0.025 - 0.075 mm)', quantity: 1, unit: 'PK' },
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
      </div>

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
                Incident Investigation Report: {report8D?.incident_id || 'INC-2026-0904'}
              </h2>
              <div className="text-xs font-mono text-slate-500 mt-0.5">
                Asset: {report8D?.asset_id || 'P-301A'} ({report8D?.asset_name || 'HP Boiler Feed Pump'}) · Classification: Level 1 Critical Plant Machinery Trip
              </div>
            </div>

            <div className="text-right font-mono text-xs text-slate-500">
              <span className="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200 font-bold block mb-1">
                STATUS: CLOSED & APPROVED
              </span>
              <span>Date: 2026-09-04 · Area 03</span>
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
                  <span className="font-semibold">{report8D?.d1_team?.lead || 'J. Reynolds (Reliability Lead)'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Operations Lead</span>
                  <span className="font-semibold">{report8D?.d1_team?.operations || 'K. Patel (Feedwater Unit Lead)'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">Hydraulic Specialist</span>
                  <span className="font-semibold">{report8D?.d1_team?.process_eng || 'Dr. S. Thorne (Senior Hydraulic Eng)'}</span>
                </div>
                <div>
                  <span className="text-slate-500 block text-[10px]">CMMS Planner</span>
                  <span className="font-semibold">{report8D?.d1_team?.cmms_planner || 'M. Alvarez (Maintenance Coord)'}</span>
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
                  <strong>What:</strong> {report8D?.d2_problem_description?.what || 'Unplanned trip of Boiler Feed Pump P-301A on high drive-end bearing temperature.'}
                </p>
                <p>
                  <strong>When & Where:</strong> {report8D?.d2_problem_description?.when || '2026-09-04 03:14:00 AM'} · {report8D?.d2_problem_description?.where || 'Site Alpha, Area 03, Unit 300'}
                </p>
                <p>
                  <strong>Impact:</strong> {report8D?.d2_problem_description?.how_much || 'Total loss of primary boiler feedwater injection (185 m3/h). Header pressure dipped 4.2 bar.'}{' '}
                  {report8D?.d2_problem_description?.operational_impact || 'Automatic cut-in of auxiliary standby pump P-301B prevented total boiler flame-out.'}
                </p>
              </div>
            </div>

            {/* D3 */}
            <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
              <div className="font-mono text-xs font-bold text-teal-800 uppercase tracking-wider">
                D3: Interim Containment Actions (ICA)
              </div>
              <ul className="list-disc pl-5 text-xs text-slate-700 space-y-0.5 font-sans">
                <li>Verify auto-start and stable discharge pressure on standby boiler feed pump P-301B.</li>
                <li>Electrical isolation & LOTO: Lock out 3.3 kV breaker <code>33-SWG-P301A</code> at substation switchgear.</li>
                <li>Close suction isolation valve MOV-30101 and discharge non-return check valve MOV-30102.</li>
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
                    {report8D?.d4_root_cause_analysis?.root_cause_asset || 'STR-301A (Suction Strainer)'}
                  </span>
                </p>
                <p>
                  <strong>Failure Mechanism:</strong>{' '}
                  <span className="font-mono text-blue-800">
                    {report8D?.d4_root_cause_analysis?.failure_mechanism || 'Cavitation erosion / Hydraulic flow starvation'}
                  </span>{' '}
                  (ISO 14224: <code>{report8D?.d4_root_cause_analysis?.iso_14224_code || 'ISO-14224-PU-HYD-CAV'}</code>)
                </p>
                <p className="pt-0.5 text-slate-700 leading-relaxed">
                  {report8D?.d4_root_cause_analysis?.root_cause_statement ||
                    'Upstream Suction Strainer STR-301A 20-mesh basket fouled with marine biofouling/particulates due to deferred preventative maintenance flush, causing excessive Delta-P (1.85 bar), starving pump suction below NPSHr (0.58 bar < 1.20 bar), and inducing catastrophic cavitation and bearing thermal trip.'}
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
                  <li>Pull, inspect, and chemically clean STR-301A 20-mesh dual basket element.</li>
                  <li>Perform boroscopic inspection of P-301A first-stage impeller suction eye.</li>
                  <li>Inspect sleeve bearing clearances; flush and refill lube oil (ISO VG 46).</li>
                </ul>
              </div>

              <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1">
                <div className="font-mono text-xs font-bold text-teal-800 uppercase tracking-wider">
                  D6: Implement & Validate PCA
                </div>
                <div className="text-xs text-slate-700 space-y-0.5 font-sans">
                  <p>
                    <strong>Validation Protocol:</strong> Baseline 4-hour re-commissioning test under full load.
                  </p>
                  <p>
                    <strong>Acceptance Criteria:</strong> PT-30101 &gt; 2.30 bar, DPS-30101 &lt; 0.15 bar, VI-301-R &lt; 2.1 mm/s RMS, TI-301-DE &lt; 55.0°C.
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
                  <li>Reclassify Suction Strainer PM flush schedule to 'Safety/Reliability Critical' in SAP PM.</li>
                  <li>Enforce mandatory DCS interlock preventing deferred PM without authorization.</li>
                </ul>
              </div>

              <div className="p-3.5 rounded-lg bg-emerald-50/40 border border-emerald-200 space-y-1">
                <div className="font-mono text-xs font-bold text-emerald-800 uppercase tracking-wider flex items-center space-x-1.5">
                  <ShieldCheck className="w-4 h-4 text-emerald-600" />
                  <span>D8: Engineer Authorization</span>
                </div>
                <div className="text-xs font-mono text-slate-700 space-y-0.5">
                  <p>Reviewed by: <strong className="text-slate-900">{report8D?.d8_sign_off?.reviewed_by || 'J. Reynolds (Machinery Reliability Specialist)'}</strong></p>
                  <p>Status: <span className="text-emerald-700 font-bold">APPROVED & RELEASED</span></p>
                  <p className="text-slate-500 text-[11px]">Notes: {report8D?.d8_sign_off?.review_notes || 'Verified by multi-sensor FFT acoustic convergence.'}</p>
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
                Work Order #{sapOrder?.order_number || '40019284'} · Notification #{sapOrder?.notification_number || '10082914'}
              </h2>
              <div className="text-xs font-mono text-slate-500 mt-0.5">
                Equipment: {sapOrder?.equipment_id || '10049201'} - {sapOrder?.equipment_name || 'Sulzer Boiler Feed Pump P-301A'}
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
              <span className="font-bold text-slate-800">{sapOrder?.functional_location || 'PLNT-B03-FW300-P301A'}</span>
            </div>
            <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
              <span className="text-slate-500 block text-[10px]">Cost Center</span>
              <span className="font-bold text-slate-800">{sapOrder?.cost_center || 'CC-UTIL-300'}</span>
            </div>
            <div className="p-2.5 bg-slate-50 border border-slate-200 rounded-lg">
              <span className="text-slate-500 block text-[10px]">Total Est. Hours</span>
              <span className="font-bold text-teal-700">{sapOrder?.total_estimated_hours || 15.0} Hours</span>
            </div>
          </div>

          {/* Short Text / Scope */}
          <div className="p-3.5 rounded-lg bg-slate-50 border border-slate-200 space-y-1 text-xs">
            <div className="font-mono text-slate-500 font-bold">Scope of Work:</div>
            <div className="font-semibold text-slate-900">{sapOrder?.short_text || 'Emergency Overhaul: STR-301A Strainer Clean, Impeller Boroscopy & Bearing Flush'}</div>
            <div className="text-slate-600 font-sans text-xs pt-0.5 leading-relaxed">
              {sapOrder?.long_text || 'Disassemble and inspect Suction Strainer STR-301A following cavitation-induced trip. Inspect first-stage impeller for cavitation erosion pitting. Measure DE bearing clearances with Plastigage. Refill oil reservoir with fresh ISO VG 46.'}
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
              Standard Operating Procedure (SOP-FW-301)
            </div>
            <h2 className="text-base font-bold text-slate-900">
              Feedwater Pump P-301A Cavitation Incident Recovery & Re-commissioning
            </h2>
            <div className="text-xs font-mono text-slate-500 mt-0.5">
              Safety Class: Critical Pressure System · LOTO Verification Required
            </div>
          </div>

          <div className="space-y-2.5 font-mono text-xs">
            {[
              {
                id: 'sop-1',
                title: 'Phase 1: Lockout/Tagout (LOTO) & Energy Isolation',
                desc: 'Rack out 3.3 kV breaker 33-SWG-P301A. Verify zero voltage on motor leads. Close and chain MOV-30101 and MOV-30102.',
              },
              {
                id: 'sop-2',
                title: 'Phase 2: Suction Strainer STR-301A Inspection',
                desc: 'Open drain valve to depressurize strainer body. Unbolt top cover, pull 20-mesh dual basket. Wash out biofouling debris and inspect mesh integrity.',
              },
              {
                id: 'sop-3',
                title: 'Phase 3: Impeller Boroscopy Inspection',
                desc: 'Insert flexible boroscope through suction inspection port. Photograph first-stage impeller eye. Verify pitting depth is < 0.5 mm per OEM limits.',
              },
              {
                id: 'sop-4',
                title: 'Phase 4: Sleeve Bearing Clearance & Lube Oil Renewal',
                desc: 'Remove upper bearing cap. Measure diametral clearance using Plastigage (Target: 0.12 - 0.18 mm). Drain reservoir, flush with clean oil, refill with 40L ISO VG 46.',
              },
              {
                id: 'sop-5',
                title: 'Phase 5: Re-commissioning & Online Baseline Validation',
                desc: 'Prime pump suction. Start pump with discharge valve throttled. Confirm PT-30101 > 2.35 bar, VI-301-R < 2.0 mm/s RMS, and FFT broadband ratio < 10%.',
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
    </div>
  );
};
