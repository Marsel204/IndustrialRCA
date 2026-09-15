import React from 'react';
import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock,
  Gauge,
  HardDrive,
  Info,
  Layers,
  Thermometer,
  Zap,
} from 'lucide-react';
import { TelemetryData, RCAState, Scenario } from '../../types';

interface ExecutiveSummaryTabProps {
  telemetry: TelemetryData | null;
  rcaState: RCAState | null;
  activeScenario: Scenario | undefined;
  onNavigateToTab: (tabId: string) => void;
}

export const ExecutiveSummaryTab: React.FC<ExecutiveSummaryTabProps> = ({
  telemetry,
  rcaState,
  activeScenario,
  onNavigateToTab,
}) => {
  const isFault = activeScenario?.id !== 'normal';
  const hasTrip = rcaState?.has_active_trip || isFault;

  const bearingTempMax = telemetry?.series?.['TI-301-DE']
    ? Math.max(...telemetry.series['TI-301-DE'])
    : isFault ? 92.3 : 48.5;

  const vibRmsMax = telemetry?.series?.['VI-301-R']
    ? Math.max(...telemetry.series['VI-301-R'])
    : isFault ? 11.4 : 1.8;

  const suctionMin = telemetry?.series?.['PT-30101']
    ? Math.min(...telemetry.series['PT-30101'])
    : isFault ? 0.58 : 2.4;

  const strainerDpMax = telemetry?.series?.['DPS-30101']
    ? Math.max(...telemetry.series['DPS-30101'])
    : isFault ? 1.85 : 0.12;

  return (
    <div className="space-y-6">
      {/* Top Section: KPI Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
        {/* Card 1: Asset Identification */}
        <div className="bg-[#0F172A] border border-blue-500/20 rounded-xl p-4 shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">Critical Asset</span>
            <span className="p-1.5 rounded-lg bg-blue-500/10 text-blue-400">
              <Layers className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-2xl font-mono font-bold text-slate-100">P-301A</span>
            <span className="text-xs font-mono text-blue-400">HP Feedwater</span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400">
            Sulzer GSG 150-360 · 2980 RPM
          </p>
          <div className="absolute top-0 right-0 w-24 h-24 bg-blue-500/5 rounded-full blur-2xl pointer-events-none" />
        </div>

        {/* Card 2: Operating Status */}
        <div
          className={`bg-[#0F172A] border rounded-xl p-4 shadow-lg relative overflow-hidden ${
            hasTrip ? 'border-red-500/30' : 'border-emerald-500/30'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">Operating Status</span>
            <span
              className={`p-1.5 rounded-lg ${
                hasTrip ? 'bg-red-500/10 text-red-400' : 'bg-emerald-500/10 text-emerald-400'
              }`}
            >
              {hasTrip ? <AlertTriangle className="w-4 h-4" /> : <CheckCircle2 className="w-4 h-4" />}
            </span>
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span
              className={`text-2xl font-mono font-bold ${
                hasTrip ? 'text-red-400 animate-pulse' : 'text-emerald-400'
              }`}
            >
              {hasTrip ? 'TRIPPED' : 'RUNNING'}
            </span>
          </div>
          <p className="mt-1 text-[11px] text-slate-400 font-mono">
            {hasTrip ? 'Emergency Trip @ 03:14 AM' : 'Nominal Steady-State'}
          </p>
          <div
            className={`absolute top-0 right-0 w-24 h-24 rounded-full blur-2xl pointer-events-none ${
              hasTrip ? 'bg-red-500/10' : 'bg-emerald-500/10'
            }`}
          />
        </div>

        {/* Card 3: Bearing Temperature */}
        <div
          className={`bg-[#0F172A] border rounded-xl p-4 shadow-lg relative overflow-hidden ${
            bearingTempMax >= 90 ? 'border-red-500/40' : 'border-slate-800'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">DE Bearing Temp</span>
            <span
              className={`p-1.5 rounded-lg ${
                bearingTempMax >= 90 ? 'bg-red-500/10 text-red-400' : 'bg-slate-800 text-slate-300'
              }`}
            >
              <Thermometer className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span
              className={`text-2xl font-mono font-bold ${
                bearingTempMax >= 90 ? 'text-red-400' : 'text-emerald-400'
              }`}
            >
              {bearingTempMax.toFixed(1)}°C
            </span>
            <span className="text-[11px] font-mono text-slate-400">TI-301-DE</span>
          </div>
          <p className="mt-1 text-[11px] font-mono text-amber-400/90">
            Trip Setpoint: 90.0°C ({bearingTempMax >= 90 ? '+2.3°C Breached' : 'Safe'})
          </p>
        </div>

        {/* Card 4: Radial Vibration RMS */}
        <div
          className={`bg-[#0F172A] border rounded-xl p-4 shadow-lg relative overflow-hidden ${
            vibRmsMax >= 7.1 ? 'border-red-500/40' : 'border-slate-800'
          }`}
        >
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">Vibration RMS</span>
            <span
              className={`p-1.5 rounded-lg ${
                vibRmsMax >= 7.1 ? 'bg-red-500/10 text-red-400' : 'bg-slate-800 text-slate-300'
              }`}
            >
              <Activity className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span
              className={`text-2xl font-mono font-bold ${
                vibRmsMax >= 7.1 ? 'text-red-400' : 'text-emerald-400'
              }`}
            >
              {vibRmsMax.toFixed(1)} mm/s
            </span>
            <span className="text-[11px] font-mono text-slate-400">VI-301-R</span>
          </div>
          <p className="mt-1 text-[11px] font-mono text-amber-400/90">
            ISO 10816: {vibRmsMax >= 7.1 ? 'Zone D (Danger/Trip)' : 'Zone A (Good)'}
          </p>
        </div>

        {/* Card 5: Pipeline & Cache State */}
        <div className="bg-[#0F172A] border border-slate-800 rounded-xl p-4 shadow-lg relative overflow-hidden">
          <div className="flex items-center justify-between">
            <span className="text-xs font-mono text-slate-400">RCA Gate Status</span>
            <span className="p-1.5 rounded-lg bg-purple-500/10 text-purple-400">
              <Zap className="w-4 h-4" />
            </span>
          </div>
          <div className="mt-2 flex items-baseline space-x-2">
            <span className="text-lg font-mono font-bold text-purple-300">
              {rcaState?.is_paused_at_hitl
                ? 'HITL GATE'
                : rcaState?.pipeline_status === 'COMPLETED'
                ? 'COMPLETED'
                : rcaState?.pipeline_status === 'NORMAL_STABLE'
                ? 'BASELINE'
                : rcaState?.pipeline_status || 'READY'}
            </span>
          </div>
          <p className="mt-1 text-[11px] font-mono text-slate-400">
            {rcaState?.is_paused_at_hitl
              ? '⏸️ Awaiting Authorization'
              : rcaState?.pipeline_status === 'COMPLETED'
              ? '✓ Work Order Emitted'
              : 'Zero False Alarms'}
          </p>
        </div>
      </div>

      {/* Main Section: Investigation Status & Primary Findings */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left Column (2/3): Primary Diagnostic Findings */}
        <div className="lg:col-span-2 bg-[#0F172A] border border-[#1E293B] rounded-xl p-5 shadow-xl space-y-4">
          <div className="flex items-center justify-between border-b border-slate-800 pb-3">
            <div className="flex items-center space-x-2">
              <Info className="w-5 h-5 text-[#00D4AA]" />
              <h3 className="font-mono text-sm font-bold text-slate-100 tracking-wide uppercase">
                Diagnostic Convergence & Incident Summary
              </h3>
            </div>
            {rcaState?.winning_hypothesis && (
              <span className="px-2.5 py-0.5 rounded text-xs font-mono font-bold bg-[#00D4AA]/10 text-[#00D4AA] border border-[#00D4AA]/30">
                Confidence: {rcaState.winning_hypothesis.confidence * 100}%
              </span>
            )}
          </div>

          {hasTrip ? (
            <div className="space-y-4">
              {/* Primary Root Cause Banner */}
              <div className="p-4 rounded-lg bg-gradient-to-r from-red-950/40 to-slate-900 border border-red-500/30">
                <div className="text-xs font-mono uppercase tracking-wider text-red-400 font-bold mb-1">
                  Confirmed Physical Root Cause Asset
                </div>
                <div className="text-base font-bold text-slate-100">
                  Upstream Suction Strainer STR-301A Blinding & NPSH Starvation
                </div>
                <p className="mt-1 text-xs text-slate-300 leading-relaxed">
                  Marine biofouling and particulate debris blinded the 20-mesh strainer basket following a deferred
                  14-day preventive maintenance flush (CMMS Order WM-2026-0831). Strainer differential pressure
                  (DPS-30101) escalated from 0.12 bar to 1.85 bar, starving pump suction pressure (PT-30101) down to
                  0.58 bar (well below OEM NPSHr of 1.20 bar).
                </p>
              </div>

              {/* Physical Causal Cascade Grid */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3 text-xs font-mono">
                <div className="p-3 bg-[#0B1120] border border-slate-800 rounded-lg">
                  <div className="text-slate-400 mb-1 font-semibold flex items-center justify-between">
                    <span>1. Hydraulic Restriction</span>
                    <span className="text-red-400">DPS-30101: 1.85 bar</span>
                  </div>
                  <p className="text-slate-300">
                    Upstream strainer dP breached high alarm threshold (1.00 bar) by 85%, creating severe suction line choking.
                  </p>
                </div>

                <div className="p-3 bg-[#0B1120] border border-slate-800 rounded-lg">
                  <div className="text-slate-400 mb-1 font-semibold flex items-center justify-between">
                    <span>2. Suction Cavitation Inception</span>
                    <span className="text-red-400">PT-30101: 0.58 bar</span>
                  </div>
                  <p className="text-slate-300">
                    Suction pressure plunged below NPSHr (1.20 bar), triggering explosive vapor micro-bubble collapse in the first-stage impeller eye.
                  </p>
                </div>

                <div className="p-3 bg-[#0B1120] border border-slate-800 rounded-lg">
                  <div className="text-slate-400 mb-1 font-semibold flex items-center justify-between">
                    <span>3. High-Freq Acoustic Shockwaves</span>
                    <span className="text-red-400">FFT 2-8 kHz: 48.9%</span>
                  </div>
                  <p className="text-slate-300">
                    20 kHz FFT spectral analysis proves 48.9% broadband acoustic energy floor (alarm &gt; 35%), ruling out discrete shaft unbalance.
                  </p>
                </div>

                <div className="p-3 bg-[#0B1120] border border-slate-800 rounded-lg">
                  <div className="text-slate-400 mb-1 font-semibold flex items-center justify-between">
                    <span>4. Bearing Hydrodynamic Wipe</span>
                    <span className="text-red-400">TI-301-DE: 92.3°C</span>
                  </div>
                  <p className="text-slate-300">
                    11.4 mm/s radial vibration destroyed the hydrodynamic oil wedge, causing sleeve boundary friction and thermal trip at 03:14 AM.
                  </p>
                </div>
              </div>

              {/* Quick Jump Action Bar */}
              <div className="flex flex-wrap gap-2 pt-2 border-t border-slate-800">
                <button
                  onClick={() => onNavigateToTab('telemetry')}
                  className="px-3 py-1.5 bg-[#1E293B] hover:bg-[#334155] text-xs font-mono text-[#00D4AA] rounded-md transition-colors cursor-pointer"
                >
                  📈 Inspect 60fps Telemetry & FFT Spectrum →
                </button>
                <button
                  onClick={() => onNavigateToTab('hypotheses')}
                  className="px-3 py-1.5 bg-[#1E293B] hover:bg-[#334155] text-xs font-mono text-blue-400 rounded-md transition-colors cursor-pointer"
                >
                  🧪 View 6 FMEA Hypotheses Matrix →
                </button>
                <button
                  onClick={() => onNavigateToTab('hitl')}
                  className="px-3 py-1.5 bg-[#1E293B] hover:bg-[#334155] text-xs font-mono text-amber-400 rounded-md transition-colors cursor-pointer"
                >
                  🛑 Engineer HITL Gate & AI Copilot →
                </button>
              </div>
            </div>
          ) : (
            <div className="p-6 text-center space-y-3 bg-[#0B1120] border border-emerald-500/20 rounded-lg">
              <CheckCircle2 className="w-12 h-12 text-emerald-400 mx-auto" />
              <div className="text-base font-bold text-emerald-400">
                Baseline Normal Operation Verified
              </div>
              <p className="text-xs text-slate-300 max-w-lg mx-auto">
                Asset P-301A operated strictly within all OEM operational envelopes over the 60-minute evaluation
                window. Statistical variance, change-point detector, and FFT spectral analyzer detected zero
                anomalies. Zero false alarms raised.
              </p>
            </div>
          )}
        </div>

        {/* Right Column (1/3): Equipment Technical Specification */}
        <div className="bg-[#0F172A] border border-[#1E293B] rounded-xl p-5 shadow-xl space-y-4">
          <div className="flex items-center space-x-2 border-b border-slate-800 pb-3">
            <Gauge className="w-5 h-5 text-blue-400" />
            <h3 className="font-mono text-sm font-bold text-slate-100 tracking-wide uppercase">
              OEM Equipment Specification
            </h3>
          </div>

          <div className="space-y-2.5 text-xs font-mono">
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Asset Tag</span>
              <span className="text-slate-200 font-bold">P-301A</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Equipment Type</span>
              <span className="text-slate-200">Centrifugal (PU-CE)</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Manufacturer</span>
              <span className="text-slate-200">Sulzer Pumps Ltd</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Model</span>
              <span className="text-slate-200">GSG 150-360 6-Stage</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Rated Speed / F1</span>
              <span className="text-slate-200">2980 RPM / 49.67 Hz</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Harmonic 2X</span>
              <span className="text-slate-200">99.33 Hz</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">NPSH Required</span>
              <span className="text-amber-400 font-semibold">1.20 bar</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Bearing Trip Limit</span>
              <span className="text-red-400 font-semibold">90.0°C (TI-301-DE)</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">ISO 10816 Zone D Trip</span>
              <span className="text-red-400 font-semibold">7.10 mm/s RMS</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-800/60">
              <span className="text-slate-400">Strainer Clean / Trip dP</span>
              <span className="text-slate-200">0.12 / 1.80 bar</span>
            </div>
            <div className="flex justify-between py-1">
              <span className="text-slate-400">Drive Motor FLA</span>
              <span className="text-slate-200">115.0 A (450 kW)</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
