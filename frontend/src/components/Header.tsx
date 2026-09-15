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
      {/* Live HIL Alert Banner if active */}
      {latestIncident?.has_incident && (
        <div className="bg-rose-50 border-b border-rose-200 px-4 py-2 flex items-center justify-between animate-pulse">
          <div className="flex items-center space-x-3">
            <AlertOctagon className="w-4 h-4 text-rose-600 animate-bounce" />
            <div>
              <span className="font-mono text-xs font-bold text-rose-700 tracking-wider">
                🚨 LIVE HIL INCIDENT DETECTED FROM EDGE BENCH
              </span>
              <span className="ml-2 font-mono text-xs text-rose-900">
                Asset: {latestIncident.incident_data?.asset_id} | Code: Err0{latestIncident.incident_data?.fault_code} ({latestIncident.incident_data?.fault_description})
              </span>
            </div>
          </div>
          <button
            onClick={onLoadIncident}
            className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white font-mono text-xs font-semibold rounded shadow-xs transition-all flex items-center space-x-1 cursor-pointer"
          >
            <span>1-Click Load Incident</span>
          </button>
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
              {activeScenario?.asset_id || 'P-301A'}
            </span>
            <span className="text-slate-500 text-[11px]">
              {activeScenario?.asset_id === 'VFD_VM_01' || activeScenario?.id === 'live_stream'
                ? 'WECON VM VFD Test Bench'
                : 'HP Boiler Feed Pump'}
            </span>
            <span className="text-[10px] font-mono text-slate-500 bg-white border border-slate-200 px-1 rounded">
              ISA-95 L2
            </span>
          </div>
        </div>

        {/* Center: Scenario Selector */}
        <div className="flex items-center space-x-2.5">
          <div className="flex items-center space-x-1.5 bg-slate-50 border border-slate-200 rounded-lg px-2 py-1">
            <span className="text-xs text-slate-500 font-mono flex items-center space-x-1">
              <span className="hidden md:inline">Scenario:</span>
            </span>
            <select
              value={activeScenarioId}
              onChange={(e) => onSelectScenario(e.target.value)}
              className="bg-white text-slate-800 text-xs font-mono rounded px-2 py-0.5 border border-slate-200 focus:outline-none focus:ring-1 focus:ring-teal-500 cursor-pointer"
            >
              {scenarios.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.id === 'live_stream'
                    ? '⚡ LIVE: Wecon VFD Telemetry'
                    : s.id === 'fault'
                    ? '⚠ ' + s.name
                    : s.id === 'normal'
                    ? '✓ ' + s.name
                    : '🚨 ' + s.name}
                </option>
              ))}
            </select>
          </div>

          {activeScenario && activeScenario.id === 'live_stream' ? (
            <span className="px-2 py-0.5 rounded text-[11px] font-mono font-semibold uppercase bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center space-x-1.5 shadow-xs">
              <span className="relative flex h-2 w-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-2 w-2 bg-emerald-500"></span>
              </span>
              <span>⚡ LIVE STREAM</span>
            </span>
          ) : activeScenario ? (
            <span
              className={`px-2 py-0.5 rounded text-[11px] font-mono font-semibold uppercase ${
                activeScenario.badge === 'CRITICAL'
                  ? 'bg-rose-50 text-rose-700 border border-rose-200'
                  : activeScenario.badge === 'LIVE_EDGE'
                  ? 'bg-purple-50 text-purple-700 border border-purple-200'
                  : 'bg-emerald-50 text-emerald-700 border border-emerald-200'
              }`}
            >
              {activeScenario.badge}
            </span>
          ) : null}
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
