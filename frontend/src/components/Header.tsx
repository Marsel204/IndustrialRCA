import React, { useState, useRef, useEffect } from 'react';
import {
  Activity,
  RotateCcw,
  Server,
  Bot,
  ChevronDown,
  Zap,
} from 'lucide-react';
import { Scenario, LatestIncident } from '../types';

interface HeaderProps {
  scenarios: Scenario[];
  activeScenarioId: string;
  apiOnline: boolean;
  latestIncident: LatestIncident | null;
  onResetPipeline: () => void;
  deepseekModel?: string;
  onToggleModel?: (model: string) => void;
  isPipelineRunning: boolean;
  mqttConnected?: boolean;
  telemetryConnected?: boolean;
  isSimulated?: boolean;
  simulationScenario?: string;
  simulationPhase?: string;
  simulationCountdown?: number;
  onToggleSimulation?: (enabled: boolean, scenario?: string, duration?: number) => void;
}

export const Header: React.FC<HeaderProps> = ({
  scenarios,
  activeScenarioId,
  apiOnline,
  latestIncident,
  onResetPipeline,
  deepseekModel,
  onToggleModel,
  isPipelineRunning,
  mqttConnected = false,
  telemetryConnected = false,
  isSimulated = false,
  simulationScenario = 'nominal',
  simulationPhase = 'IDLE',
  simulationCountdown = 0,
  onToggleSimulation,
}) => {
  const activeScenario = scenarios.find((s) => s.id === activeScenarioId);
  const incFaultNum = latestIncident?.incident_data?.fault_code || 6;
  const incFaultStr = incFaultNum >= 10 ? `Err${incFaultNum}` : `Err0${incFaultNum}`;

  const [isSimMenuOpen, setIsSimMenuOpen] = useState(false);
  const simMenuRef = useRef<HTMLDivElement>(null);

  const SIMULATION_SCENARIOS = [
    { id: 'H_VFD_ERR06', name: 'Err06 · Decel Overvoltage (195V)', icon: '⚡', color: 'text-amber-700' },
    { id: 'H_VFD_ERR02', name: 'Err02 · Sudden Stop Overcurrent (2.5A)', icon: '💥', color: 'text-rose-700' },
    { id: 'H_VFD_ERR03', name: 'Err03 · Decel Ramp Overcurrent (2.5A)', icon: '📉', color: 'text-orange-700' },
    { id: 'H_VFD_ERR11', name: 'Err11 · Motor Thermal Overload (2.0A)', icon: '🔥', color: 'text-red-700' },
    { id: 'nominal', name: 'Nominal 40Hz Baseline (Zero Faults)', icon: '🟢', color: 'text-emerald-700' },
  ];

  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (simMenuRef.current && !simMenuRef.current.contains(e.target as Node)) {
        setIsSimMenuOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-xs">
      {/* Live Hardware Incident Banner (100% Autonomous) */}
      {latestIncident?.has_incident && (
        <div className="bg-rose-50 border-b border-rose-200 px-4 py-2 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="relative flex h-3 w-3">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-rose-400 opacity-75"></span>
              <span className="relative inline-flex rounded-full h-3 w-3 bg-rose-600"></span>
            </div>
            <div>
              <span className="font-mono text-xs font-bold text-rose-700 tracking-wider">
                🚨 HARDWARE FAULT AUTOMATICALLY CAPTURED FROM EDGE BENCH
              </span>
              <span className="ml-2 font-mono text-xs text-rose-900">
                Asset: {latestIncident.incident_data?.asset_id || 'VFD_VM_01'} | Code: {incFaultStr} ({latestIncident.incident_data?.fault_description || 'Deceleration Overvoltage'})
              </span>
            </div>
          </div>
          <div className="flex items-center space-x-2">
            <span className="px-2.5 py-1 bg-rose-100 border border-rose-300 text-rose-800 font-mono text-xs font-semibold rounded shadow-xs flex items-center space-x-1.5">
              <span className="w-2 h-2 rounded-full bg-rose-600 animate-pulse" />
              <span>
                {latestIncident.pipeline_status === 'ANALYSIS_COMPLETE'
                  ? '✓ AUTO-ANALYZED · DIAGNOSIS ACTIVE'
                  : '⏳ AUTONOMOUS RCA IN PROGRESS...'}
              </span>
            </span>
          </div>
        </div>
      )}

      {/* Main Navigation Bar */}
      <div className="max-w-[1720px] mx-auto px-4 py-2 flex items-center justify-between gap-3">
        {/* Left: Branding & Asset Chip */}
        <div className="flex items-center space-x-3 min-w-0">
          <div className="flex items-center space-x-2.5 flex-shrink-0">
            <div className="w-7 h-7 rounded-lg bg-teal-50 border border-teal-200 flex items-center justify-center shadow-xs">
              <Activity className="w-3.5 h-3.5 text-teal-600" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5 leading-none">
                <span className="font-bold text-xs tracking-wide text-slate-900 uppercase">
                  Industrial RCA
                </span>
                <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-slate-100 text-slate-500 border border-slate-200">
                  v2.1
                </span>
              </div>
              <div className="font-mono text-[9px] text-slate-400 tracking-wider mt-0.5">
                Reliability Workspace
              </div>
            </div>
          </div>

          <div className="h-4 w-[1px] bg-slate-200 hidden sm:block flex-shrink-0" />

          {/* Active Asset Pill */}
          <div className="hidden sm:flex items-center space-x-1.5 bg-slate-50 border border-slate-200 px-2 py-1 rounded-md text-xs flex-shrink-0">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500" />
            <span className="font-mono font-bold text-slate-800 text-[11px]">
              {activeScenario?.asset_id || 'VFD_VM_01'}
            </span>
            <span className="text-slate-400 text-[10px] hidden md:inline">
              (Wecon VM)
            </span>
          </div>
        </div>

        {/* Right: Streamlined Status & Controls */}
        <div className="flex items-center space-x-2 flex-shrink-0">
          {/* Telemetry Stream & Simulation Control Indicator */}
          <div className="relative" ref={simMenuRef}>
            {isSimulated ? (
              <div className="flex items-center space-x-1.5 bg-amber-50/90 border border-amber-300/80 px-2 py-1 rounded-md text-[11px] font-mono shadow-2xs">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-amber-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-amber-500" />
                </span>
                <span className="text-amber-900 font-semibold">
                  {simulationPhase === 'NORMAL' && simulationCountdown > 0 ? (
                    <span className="flex items-center space-x-1">
                      <span>🧪 {simulationScenario}</span>
                      <span className="bg-amber-200/90 text-amber-950 px-1 py-0.2 rounded font-bold animate-pulse">
                        Tripping in {simulationCountdown.toFixed(0)}s
                      </span>
                    </span>
                  ) : simulationPhase === 'TRIPPED' ? (
                    <span className="text-rose-800 font-bold">⚡ Injected {simulationScenario}</span>
                  ) : (
                    <span>🧪 Sim: {simulationScenario}</span>
                  )}
                </span>
                <button
                  onClick={() => setIsSimMenuOpen(!isSimMenuOpen)}
                  className="p-0.5 hover:bg-amber-200/70 text-amber-900 rounded transition-colors cursor-pointer"
                  title="Select different simulation scenario"
                >
                  <ChevronDown className="w-3 h-3" />
                </button>
                {onToggleSimulation && (
                  <button
                    onClick={() => onToggleSimulation(false)}
                    className="ml-1 px-1.5 py-0.5 text-[10px] bg-slate-200 hover:bg-slate-300 text-slate-700 rounded transition-colors cursor-pointer"
                    title="Disable simulation and listen for live MQTT hardware"
                  >
                    Stop Sim
                  </button>
                )}
              </div>
            ) : telemetryConnected ? (
              <div className="flex items-center space-x-1.5 bg-slate-50 border border-slate-200 px-2 py-1 rounded-md text-[11px] font-mono shadow-2xs">
                <span className="relative flex h-2 w-2">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500" />
                </span>
                <span className="text-emerald-800 font-medium">● Live Rig · MQTT</span>
                {onToggleSimulation && (
                  <button
                    onClick={() => setIsSimMenuOpen(!isSimMenuOpen)}
                    className="ml-1 px-1.5 py-0.5 text-[10px] bg-slate-100 hover:bg-slate-200 text-slate-700 rounded transition-colors flex items-center space-x-0.5 cursor-pointer"
                    title="Switch to simulated telemetry"
                  >
                    <span>🧪 Sim</span>
                    <ChevronDown className="w-2.5 h-2.5" />
                  </button>
                )}
              </div>
            ) : (
              <div className="flex items-center space-x-1.5 bg-slate-50 border border-slate-200 px-2 py-1 rounded-md text-[11px] font-mono shadow-2xs">
                <span className="relative flex h-2 w-2">
                  <span className="relative inline-flex rounded-full h-2 w-2 bg-rose-400" />
                </span>
                <span className="text-rose-700 font-medium">○ Telemetry Offline</span>
                {onToggleSimulation && (
                  <button
                    onClick={() => setIsSimMenuOpen(!isSimMenuOpen)}
                    className="ml-1 px-1.5 py-0.5 text-[10px] bg-amber-100 hover:bg-amber-200 text-amber-900 border border-amber-300 rounded transition-colors font-semibold flex items-center space-x-1 cursor-pointer"
                    title="Choose a scenario to simulate"
                  >
                    <span>🧪 Simulate Scenario</span>
                    <ChevronDown className="w-2.5 h-2.5" />
                  </button>
                )}
              </div>
            )}

            {/* Scenario Selection Dropdown */}
            {isSimMenuOpen && (
              <div className="absolute right-0 mt-1 w-72 bg-white border border-slate-200 rounded-lg shadow-xl z-50 py-1 text-xs font-mono">
                <div className="px-3 py-1.5 text-[10px] font-bold text-slate-400 uppercase tracking-wider border-b border-slate-100">
                  Select Scenario (5s Normal → Fault)
                </div>
                {SIMULATION_SCENARIOS.map((sc) => (
                  <button
                    key={sc.id}
                    onClick={() => {
                      onToggleSimulation?.(true, sc.id, 5);
                      setIsSimMenuOpen(false);
                    }}
                    className={`w-full text-left px-3 py-2 hover:bg-slate-50 flex items-center space-x-2 transition-colors cursor-pointer ${
                      simulationScenario.toLowerCase() === sc.id.toLowerCase() ? 'bg-amber-50 font-bold' : ''
                    }`}
                  >
                    <span className="text-sm">{sc.icon}</span>
                    <span className={sc.color}>{sc.name}</span>
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Fault Alert Badge (shows only on active trip) */}
          {latestIncident?.has_incident && (
            <span className="px-2 py-1 rounded text-[11px] font-mono font-bold bg-rose-50 text-rose-700 border border-rose-200 flex items-center space-x-1.5 animate-pulse shadow-2xs">
              <span className="w-1.5 h-1.5 rounded-full bg-rose-600" />
              <span>FAULT: {incFaultStr}</span>
            </span>
          )}

          {/* DeepSeek Unified Model Badge */}
          <div className="flex items-center space-x-1.5 bg-purple-50/70 border border-purple-200/80 px-2 py-1 rounded-md text-[11px] font-mono shadow-2xs">
            <Bot className="w-3 h-3 text-purple-600" />
            <span className="text-purple-800 font-bold">
              V4.1 Flash
            </span>
          </div>

          {/* API Health Pill */}
          <div
            className="flex items-center space-x-1 px-2 py-1 bg-slate-50 border border-slate-200 rounded-md text-[11px] font-mono text-slate-600"
            title={apiOnline ? 'Backend API Online' : 'Backend API Offline'}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${apiOnline ? 'bg-emerald-500' : 'bg-rose-500'}`} />
            <span className="text-[10px] uppercase font-semibold">{apiOnline ? 'API' : 'OFFLINE'}</span>
          </div>

          {/* Reset / Return to Normal Button */}
          <button
            onClick={onResetPipeline}
            disabled={isPipelineRunning}
            className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-md font-mono text-xs font-semibold transition-colors cursor-pointer shadow-xs disabled:opacity-50 ${
              latestIncident?.has_incident
                ? 'bg-emerald-600 hover:bg-emerald-700 text-white border border-emerald-700'
                : 'bg-white hover:bg-slate-50 active:bg-slate-100 border border-slate-200 text-slate-700'
            }`}
            title={
              latestIncident?.has_incident
                ? 'Fault resolved: Click to clear incident and return to normal real-time monitoring'
                : 'Reset active session'
            }
          >
            <RotateCcw className={`w-3 h-3 ${latestIncident?.has_incident ? 'text-white' : 'text-slate-500'} ${isPipelineRunning ? 'animate-spin' : ''}`} />
            <span>{latestIncident?.has_incident ? 'Reset' : 'Reset'}</span>
          </button>
        </div>
      </div>
    </header>
  );
};
