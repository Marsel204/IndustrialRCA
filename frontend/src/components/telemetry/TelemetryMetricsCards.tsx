import React from 'react';
import { Radio, Zap, Activity, Cpu, Layers, Gauge } from 'lucide-react';

interface TelemetryMetricsCardsProps {
  isVfdAsset: boolean;
  frequencyHz: number;
  freqStatus: string;
  voltageVdc: number;
  currentAmp: number;
  currentRpm: number;
  currentStatus: string;
  targetFrequencyHz?: number;
  voltageVout?: number;
  torqueFeedback?: number;
  powerKw?: number;
  latestTi: number;
  latestVi: number;
  latestDps: number;
  latestPt: number;
}

export const TelemetryMetricsCards: React.FC<TelemetryMetricsCardsProps> = ({
  isVfdAsset,
  frequencyHz,
  freqStatus,
  voltageVdc,
  currentAmp,
  currentRpm,
  currentStatus,
  targetFrequencyHz,
  voltageVout = 184.0,
  torqueFeedback = 0.0,
  powerKw = 0.0,
  latestTi,
  latestVi,
  latestDps,
  latestPt,
}) => {
  return (
    <div className={`grid gap-3 ${isVfdAsset ? 'grid-cols-2 md:grid-cols-3 xl:grid-cols-6' : 'grid-cols-2 lg:grid-cols-4'}`}>
      {isVfdAsset ? (
        <>
          {/* Card 1: Output Frequency */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs hover:border-blue-300 transition-colors">
            <div className="flex items-center justify-between text-slate-500 mb-1">
              <span className="text-[10px] font-mono uppercase tracking-wider flex items-center gap-1 font-bold text-slate-700">
                <Radio className="w-3.5 h-3.5 text-blue-600" />
                Frequency
              </span>
              <span
                className={`px-1.5 py-0.5 text-[9px] font-mono rounded font-semibold ${
                  freqStatus === 'OVERFREQ TRIP'
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : freqStatus === 'WARNING'
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}
              >
                {freqStatus}
              </span>
            </div>
            <div className="text-xl font-mono font-bold text-slate-900">
              {frequencyHz.toFixed(2)}{' '}
              <span className="text-xs font-normal text-slate-500">Hz</span>
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-1 flex justify-between">
              <span>f_out</span>
              <span className="text-blue-600 font-semibold">
                Set: {targetFrequencyHz ? targetFrequencyHz.toFixed(1) : frequencyHz.toFixed(1)} Hz
              </span>
            </div>
          </div>

          {/* Card 2: DC Bus Voltage */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs hover:border-amber-300 transition-colors">
            <div className="flex items-center justify-between text-slate-500 mb-1">
              <span className="text-[10px] font-mono uppercase tracking-wider flex items-center gap-1 font-bold text-slate-700">
                <Zap className="w-3.5 h-3.5 text-amber-600" />
                DC Bus
              </span>
              <span
                className={`px-1.5 py-0.5 text-[9px] font-mono rounded font-semibold ${
                  voltageVdc >= 380.0
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : voltageVdc >= 320.0
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : voltageVdc >= 220.0
                    ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                    : 'bg-slate-100 text-slate-600 border border-slate-200'
                }`}
              >
                {voltageVdc >= 380.0 ? 'OVERVOLT' : voltageVdc >= 320.0 ? 'WARNING' : 'NOMINAL'}
              </span>
            </div>
            <div className="text-xl font-mono font-bold text-slate-900">
              {voltageVdc.toFixed(1)}{' '}
              <span className="text-xs font-normal text-slate-500">V DC</span>
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-1 flex justify-between">
              <span>v_dc</span>
              <span>Nom: ~276V</span>
            </div>
          </div>

          {/* Card 3: Inverter AC Output Voltage */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs hover:border-indigo-300 transition-colors">
            <div className="flex items-center justify-between text-slate-500 mb-1">
              <span className="text-[10px] font-mono uppercase tracking-wider flex items-center gap-1 font-bold text-slate-700">
                <Layers className="w-3.5 h-3.5 text-indigo-600" />
                Output Voltage
              </span>
              <span className="px-1.5 py-0.5 text-[9px] font-mono rounded font-semibold bg-indigo-50 text-indigo-700 border border-indigo-200">
                V_OUT
              </span>
            </div>
            <div className="text-xl font-mono font-bold text-slate-900">
              {voltageVout.toFixed(1)}{' '}
              <span className="text-xs font-normal text-slate-500">V AC</span>
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-1 flex justify-between">
              <span>v_out</span>
              <span>Rated: 220V</span>
            </div>
          </div>

          {/* Card 4: Motor Phase Current */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs hover:border-teal-300 transition-colors">
            <div className="flex items-center justify-between text-slate-500 mb-1">
              <span className="text-[10px] font-mono uppercase tracking-wider flex items-center gap-1 font-bold text-slate-700">
                <Activity className="w-3.5 h-3.5 text-teal-600" />
                Phase Current
              </span>
              <span
                className={`px-1.5 py-0.5 text-[9px] font-mono rounded font-semibold ${
                  currentAmp >= 2.5
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : currentAmp > 1.8
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}
              >
                {currentAmp >= 2.5 ? 'OVERLOAD' : 'NOMINAL'}
              </span>
            </div>
            <div className="text-xl font-mono font-bold text-slate-900">
              {currentAmp.toFixed(2)}{' '}
              <span className="text-xs font-normal text-slate-500">A</span>
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-1 flex justify-between">
              <span>I_out (FLA 1.15A)</span>
              <span className="text-teal-700 font-semibold">Trip: 2.50A</span>
            </div>
          </div>

          {/* Card 5: Motor Speed RPM */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs hover:border-purple-300 transition-colors">
            <div className="flex items-center justify-between text-slate-500 mb-1">
              <span className="text-[10px] font-mono uppercase tracking-wider flex items-center gap-1 font-bold text-slate-700">
                <Cpu className="w-3.5 h-3.5 text-purple-600" />
                Motor Speed
              </span>
              <span
                className={`px-1.5 py-0.5 text-[9px] font-mono rounded font-semibold ${
                  currentStatus === 'TRIPPED'
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : currentStatus === 'OFFLINE'
                    ? 'bg-slate-100 text-slate-700 border border-slate-300'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}
              >
                {currentStatus}
              </span>
            </div>
            <div className="text-xl font-mono font-bold text-slate-900">
              {Math.round(currentRpm).toLocaleString()}{' '}
              <span className="text-xs font-normal text-slate-500">RPM</span>
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-1 flex justify-between">
              <span>rpm</span>
              <span>Sync: 1,450 RPM</span>
            </div>
          </div>

          {/* Card 6: Motor Mechanical Torque & Power */}
          <div className="bg-white border border-slate-200 rounded-xl p-3 shadow-xs hover:border-pink-300 transition-colors">
            <div className="flex items-center justify-between text-slate-500 mb-1">
              <span className="text-[10px] font-mono uppercase tracking-wider flex items-center gap-1 font-bold text-slate-700">
                <Gauge className="w-3.5 h-3.5 text-pink-600" />
                Torque & Power
              </span>
              <span className="px-1.5 py-0.5 text-[9px] font-mono rounded font-semibold bg-pink-50 text-pink-700 border border-pink-200">
                LOAD
              </span>
            </div>
            <div className="text-xl font-mono font-bold text-slate-900 flex items-baseline gap-1">
              {Number(torqueFeedback).toFixed(1)} <span className="text-xs font-normal text-slate-500">%</span>
              <span className="text-xs text-slate-400 mx-0.5">·</span>
              <span className="text-sm font-semibold text-amber-700">{Number(powerKw).toFixed(2)} kW</span>
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-1 flex justify-between">
              <span>τ / P</span>
              <span>Rated: 100% / 0.75kW</span>
            </div>
          </div>
        </>
      ) : (
        <>
          {/* Card 1: Bearing Temp */}
          <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-1.5">
              <span className="text-[11px] font-mono uppercase tracking-wider flex items-center gap-1.5 font-bold text-slate-700">
                <Zap className="w-3.5 h-3.5 text-rose-600" />
                Bearing Temp (TI-301-DE)
              </span>
              <span
                className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                  latestTi >= 90
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : latestTi > 80
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}
              >
                {latestTi >= 90 ? 'TRIP' : latestTi > 80 ? 'ALARM' : 'NORMAL'}
              </span>
            </div>
            <div className="text-2xl font-mono font-bold text-slate-900">
              {latestTi.toFixed(1)}{' '}
              <span className="text-xs font-normal text-slate-500">°C</span>
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-1">
              Alarm: 80.0°C · Trip: 90.0°C
            </div>
          </div>

          {/* Card 2: Vibration RMS */}
          <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-1.5">
              <span className="text-[11px] font-mono uppercase tracking-wider flex items-center gap-1.5 font-bold text-slate-700">
                <Activity className="w-3.5 h-3.5 text-purple-600" />
                Vibration RMS (VI-301-R)
              </span>
              <span
                className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                  latestVi >= 7.1
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : latestVi > 4.5
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}
              >
                {latestVi >= 7.1 ? 'ZONE D TRIP' : latestVi > 4.5 ? 'ZONE C ALARM' : 'ZONE A/B'}
              </span>
            </div>
            <div className="text-2xl font-mono font-bold text-slate-900">
              {latestVi.toFixed(2)}{' '}
              <span className="text-xs font-normal text-slate-500">mm/s</span>
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-1">
              Zone C: 4.50 mm/s · Zone D: 7.10 mm/s
            </div>
          </div>

          {/* Card 3: Strainer Delta-P */}
          <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-1.5">
              <span className="text-[11px] font-mono uppercase tracking-wider flex items-center gap-1.5 font-bold text-slate-700">
                <Radio className="w-3.5 h-3.5 text-amber-600" />
                Strainer Delta-P (DPS-30101)
              </span>
              <span
                className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                  latestDps >= 1.0
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : latestDps > 0.5
                    ? 'bg-amber-50 text-amber-700 border border-amber-200'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}
              >
                {latestDps >= 1.0 ? 'CLOGGED' : latestDps > 0.5 ? 'DIRTY' : 'CLEAN'}
              </span>
            </div>
            <div className="text-2xl font-mono font-bold text-slate-900">
              {latestDps.toFixed(2)}{' '}
              <span className="text-xs font-normal text-slate-500">bar</span>
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-1">
              Normal: 0.12 bar · Alarm: 1.00 bar
            </div>
          </div>

          {/* Card 4: Suction Pressure */}
          <div className="bg-white border border-slate-200 rounded-xl p-3.5 shadow-xs">
            <div className="flex items-center justify-between text-slate-500 mb-1.5">
              <span className="text-[11px] font-mono uppercase tracking-wider flex items-center gap-1.5 font-bold text-slate-700">
                <Cpu className="w-3.5 h-3.5 text-blue-600" />
                Suction Pressure (PT-30101)
              </span>
              <span
                className={`px-1.5 py-0.5 text-[10px] font-mono rounded font-semibold ${
                  latestPt <= 1.2
                    ? 'bg-rose-50 text-rose-700 border border-rose-200'
                    : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                }`}
              >
                {latestPt <= 1.2 ? 'NPSH CAVITATION' : 'HEALTHY'}
              </span>
            </div>
            <div className="text-2xl font-mono font-bold text-slate-900">
              {latestPt.toFixed(2)}{' '}
              <span className="text-xs font-normal text-slate-500">bar</span>
            </div>
            <div className="text-[10px] font-mono text-slate-500 mt-1">
              Normal: 2.40 bar · NPSHr limit: 1.20 bar
            </div>
          </div>
        </>
      )}
    </div>
  );
};
