import React from 'react';
import {
  Activity,
  RotateCcw,
  Server,
  Bot,
  AlertOctagon,
} from 'lucide-react';
import { Scenario, LatestIncident } from '../types';

interface HeaderProps {
  scenarios: Scenario[];
  activeScenarioId: string;
  onSelectScenario: (scenarioId: string) => void;
  apiOnline: boolean;
  latestIncident: LatestIncident | null;
  onLoadIncident: () => void;
  onResetPipeline: () => void;
  deepseekModel: string;
  onToggleModel: (model: string) => void;
  isPipelineRunning: boolean;
}

export const Header: React.FC<HeaderProps> = ({
  scenarios,
  activeScenarioId,
  onSelectScenario,
  apiOnline,
  latestIncident,
  onLoadIncident,
  onResetPipeline,
  deepseekModel,
  onToggleModel,
  isPipelineRunning,
}) => {
  const activeScenario = scenarios.find((s) => s.id === activeScenarioId);

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
                Asset: {latestIncident.incident_data?.asset_id || 'VFD_VM_01'} | Code: Err0{latestIncident.incident_data?.fault_code} ({latestIncident.incident_data?.fault_description})
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
      <div className="max-w-[1720px] mx-auto px-4 py-2.5 flex flex-wrap items-center justify-between gap-3">
        {/* Left: Branding & Asset Pill */}
        <div className="flex items-center space-x-3">
          <div className="flex items-center space-x-2.5">
            <div className="w-8 h-8 rounded-lg bg-teal-50 border border-teal-200 flex items-center justify-center shadow-xs">
              <Activity className="w-4 h-4 text-teal-600" />
            </div>
            <div>
              <div className="flex items-center space-x-1.5">
                <span className="font-bold text-xs tracking-wide text-slate-900 uppercase">
                  Industrial RCA System
                </span>
                <span className="px-1.5 py-0.2 rounded text-[10px] font-mono bg-slate-100 text-slate-600 border border-slate-200">
                  v2.1
                </span>
              </div>
              <div className="font-mono text-[10px] text-slate-500 tracking-wider">
                Agent-First Reliability Workspace
              </div>
            </div>
          </div>

          <div className="h-5 w-[1px] bg-slate-200 hidden md:block" />

          {/* Active Asset Pill */}
          <div className="hidden sm:flex items-center space-x-2 bg-slate-50 border border-slate-200 px-2.5 py-1 rounded-md text-xs">
            <span className={`w-2 h-2 rounded-full ${activeScenario?.id === 'live_stream' ? 'bg-emerald-500 animate-pulse' : 'bg-emerald-500'}`} />
            <span className="font-mono font-bold text-slate-800">
              {activeScenario?.asset_id || 'VFD_VM_01'}
            </span>
            <span className="text-slate-500 text-[11px]">
              Wecon VM Series VFD & Motor Rig
            </span>
            <span className="text-[10px] font-mono text-slate-500 bg-white border border-slate-200 px-1 rounded">
              ISA-95 L2
            </span>
          </div>
        </div>

        {/* Center: Live Real-Time Hardware Connection Indicator */}
        <div className="flex items-center space-x-2.5">
          <div className="flex items-center space-x-2 bg-slate-50 border border-slate-200 rounded-lg px-3 py-1.5 shadow-xs">
            <span className="relative flex h-2.5 w-2.5">
              <span className={`animate-ping absolute inline-flex h-full w-full rounded-full opacity-75 ${
                latestIncident?.has_incident ? 'bg-rose-400' : 'bg-emerald-400'
              }`} />
              <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${
                latestIncident?.has_incident ? 'bg-rose-500' : 'bg-emerald-500'
              }`} />
            </span>
            <span className="text-xs font-mono font-bold text-slate-800 tracking-wide">
              LIVE HARDWARE TELEMETRY
            </span>
            <span className="text-slate-400 text-xs">·</span>
            <span className="text-[11px] font-mono text-slate-600">
              Wecon VM VFD (192.168.1.104)
            </span>
          </div>

          {/* MQTT Protocol Pill */}
          <span className="hidden sm:flex items-center space-x-1 px-2 py-1 rounded text-[11px] font-mono font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200 shadow-xs">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
            <span>MQTT 1883/8883 CONNECTED</span>
          </span>

          {/* Fault Status Pill */}
          {latestIncident?.has_incident ? (
            <span className="px-2.5 py-1 rounded text-[11px] font-mono font-bold bg-rose-50 text-rose-700 border border-rose-200 flex items-center space-x-1.5 animate-pulse shadow-xs">
              <span>🚨 FAULT ACTIVE: Err0{latestIncident.incident_data?.fault_code}</span>
            </span>
          ) : (
            <span className="px-2.5 py-1 rounded text-[11px] font-mono font-medium bg-slate-100 text-slate-700 border border-slate-200 flex items-center space-x-1.5 shadow-xs">
              <span className="w-2 h-2 rounded-full bg-emerald-500" />
              <span>MONITORING (NOMINAL)</span>
            </span>
          )}
        </div>

        {/* Right: AI Engine Toggle, Status & Actions */}
        <div className="flex items-center space-x-2.5">
          {/* DeepSeek Model Selector */}
          <div className="hidden lg:flex items-center space-x-1.5 bg-slate-50 border border-slate-200 px-2 py-1 rounded-md">
            <Bot className="w-3.5 h-3.5 text-purple-600" />
            <span className="text-[11px] font-mono text-slate-500">AI:</span>
            <button
              onClick={() =>
                onToggleModel(deepseekModel === 'deepseek-chat' ? 'deepseek-reasoner' : 'deepseek-chat')
              }
              className="text-[11px] font-mono font-medium text-purple-700 hover:text-purple-900 underline decoration-dotted cursor-pointer"
              title="Click to toggle between DeepSeek-V3 and DeepSeek-R1 Reasoner"
            >
              {deepseekModel === 'deepseek-reasoner' ? 'R1 (Reasoner CoT)' : 'V3 (Chat Fast)'}
            </button>
          </div>

          {/* API Health Pill */}
          <div className="flex items-center space-x-1.5 px-2.5 py-1 bg-emerald-50 border border-emerald-200 rounded-md text-xs font-mono font-medium text-emerald-700">
            <Server className="w-3.5 h-3.5 text-emerald-600" />
            <span
              className={`w-2 h-2 rounded-full ${
                apiOnline ? 'bg-emerald-500' : 'bg-red-500'
              }`}
            />
            <span className="text-[11px]">
              {apiOnline ? 'ONLINE' : 'OFFLINE'}
            </span>
          </div>

          {/* Reset Pipeline Button */}
          <button
            onClick={onResetPipeline}
            disabled={isPipelineRunning}
            className="flex items-center space-x-1.5 px-3 py-1 bg-white hover:bg-slate-50 active:bg-slate-100 border border-slate-200 text-slate-700 rounded-md font-mono text-xs font-medium transition-colors cursor-pointer shadow-xs disabled:opacity-50"
            title="Reset active LangGraph thread and re-run analysis"
          >
            <RotateCcw className={`w-3.5 h-3.5 text-slate-500 ${isPipelineRunning ? 'animate-spin' : ''}`} />
            <span>Reset</span>
          </button>
        </div>
      </div>
    </header>
  );
};
