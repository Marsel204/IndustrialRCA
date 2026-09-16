import React from 'react';
import {
  Database,
  Search,
  Lightbulb,
  Cpu,
  GitMerge,
  ShieldCheck,
  FileCheck2,
} from 'lucide-react';

interface PipelineStepperProps {
  currentStep: number;
  isPausedAtHitl: boolean;
  pipelineStatus: string;
  compact?: boolean;
  onSelectStepTab?: (tabId: string) => void;
}

const STEPS = [
  { step: 1, label: 'Ingest', icon: Database, desc: '1 Hz Ingestion', tab: 'telemetry' },
  { step: 2, label: 'Anomaly', icon: Search, desc: 'Change-Point', tab: 'telemetry' },
  { step: 3, label: 'Hypotheses', icon: Lightbulb, desc: 'ISO 14224 FMEA', tab: 'hypotheses' },
  { step: 4, label: 'Falsify', icon: Cpu, desc: 'Evidence Filter', tab: 'hypotheses' },
  { step: 5, label: '5-Whys', icon: GitMerge, desc: 'Topology Trace', tab: 'topology' },
  { step: 6, label: 'HITL Gate', icon: ShieldCheck, desc: 'Authorization', tab: 'hitl' },
  { step: 7, label: 'Deliverables', icon: FileCheck2, desc: '8D & SAP PM01', tab: 'deliverables' },
];

export const PipelineStepper: React.FC<PipelineStepperProps> = ({
  currentStep,
  isPausedAtHitl,
  pipelineStatus,
  compact = false,
  onSelectStepTab,
}) => {
  if (compact) {
    return (
      <div className="border border-slate-200 bg-white rounded-lg p-2.5 shadow-2xs space-y-2">
        {/* Top Header Row */}
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <GitMerge className="w-3.5 h-3.5 text-blue-600" />
            <span className="font-mono text-[11px] font-bold text-slate-800 uppercase tracking-wider">
              LangGraph 7-Step Diagnostic Plan
            </span>
            <span className="text-[10px] font-mono px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 border border-slate-200">
              Step {currentStep}/7
            </span>
          </div>
          <span
            className={`px-2 py-0.2 rounded text-[10px] font-mono font-bold tracking-wider uppercase ${
              pipelineStatus === 'COMPLETED' || pipelineStatus === 'ANALYSIS_COMPLETE'
                ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                : pipelineStatus === 'AWAITING_REVIEW' || isPausedAtHitl
                ? 'bg-amber-50 text-amber-700 border border-amber-200 animate-pulse'
                : 'bg-slate-100 text-slate-600 border border-slate-200'
            }`}
          >
            {pipelineStatus}
          </span>
        </div>

        {/* Stepper Track */}
        <div className="flex items-center justify-between pt-0.5 overflow-x-auto scrollbar-none">
          {STEPS.map((s, idx) => {
            const Icon = s.icon;
            const isCompleted = currentStep > s.step || (currentStep === 7 && s.step === 7);
            const isActive = currentStep === s.step;

            return (
              <React.Fragment key={s.step}>
                <button
                  type="button"
                  onClick={() => s.tab && onSelectStepTab && onSelectStepTab(s.tab)}
                  title={`${s.step}. ${s.label}: ${s.desc} (Click to view)`}
                  className="flex flex-col items-center flex-shrink-0 group cursor-pointer focus:outline-none"
                >
                  <div
                    className={`w-5 h-5 rounded-full flex items-center justify-center font-mono text-[10px] font-bold transition-all duration-200 ${
                      isCompleted
                        ? 'bg-teal-600 text-white shadow-2xs'
                        : isActive
                        ? isPausedAtHitl && s.step === 6
                          ? 'bg-amber-500 text-white ring-2 ring-amber-300 animate-pulse'
                          : 'bg-blue-600 text-white ring-2 ring-blue-300 animate-pulse'
                        : 'bg-slate-100 text-slate-400 border border-slate-200 group-hover:border-slate-300'
                    }`}
                  >
                    {isCompleted ? '✓' : <Icon className="w-2.5 h-2.5" />}
                  </div>
                  <span
                    className={`text-[10px] font-mono mt-1 font-semibold transition-colors ${
                      isCompleted
                        ? 'text-teal-800'
                        : isActive
                        ? isPausedAtHitl && s.step === 6
                          ? 'text-amber-800 font-bold'
                          : 'text-blue-800 font-bold'
                        : 'text-slate-400 group-hover:text-slate-600'
                    }`}
                  >
                    {s.label}
                  </span>
                </button>

                {idx < STEPS.length - 1 && (
                  <div
                    className={`flex-1 h-[2px] mx-1 min-w-[6px] transition-colors duration-200 self-center mb-3.5 ${
                      currentStep > s.step ? 'bg-teal-500' : 'bg-slate-200'
                    }`}
                  />
                )}
              </React.Fragment>
            );
          })}
        </div>
      </div>
    );
  }
  return (
    <div className="bg-white border-b border-slate-200 py-2.5 px-4 shadow-2xs">
      <div className="max-w-[1720px] mx-auto">
        <div className="flex items-center justify-between overflow-x-auto pb-0.5 scrollbar-none">
          {STEPS.map((s, idx) => {
            const Icon = s.icon;
            const isCompleted = currentStep > s.step || (currentStep === 7 && s.step === 7);
            const isActive = currentStep === s.step;

            return (
              <React.Fragment key={s.step}>
                <div className="flex items-center space-x-2 flex-shrink-0">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center font-mono text-[11px] font-bold transition-all duration-200 ${
                      isCompleted
                        ? 'bg-teal-600 text-white'
                        : isActive
                        ? isPausedAtHitl && s.step === 6
                          ? 'bg-amber-500 text-white ring-2 ring-amber-300 animate-pulse'
                          : 'bg-blue-600 text-white ring-2 ring-blue-300 animate-pulse'
                        : 'bg-slate-100 text-slate-400 border border-slate-200'
                    }`}
                  >
                    {isCompleted ? '✓' : <Icon className="w-3 h-3" />}
                  </div>

                  <div className="flex flex-col">
                    <span
                      className={`text-xs font-mono font-semibold ${
                        isCompleted
                          ? 'text-teal-800'
                          : isActive
                          ? isPausedAtHitl && s.step === 6
                            ? 'text-amber-800 font-bold'
                            : 'text-blue-800 font-bold'
                          : 'text-slate-400'
                      }`}
                    >
                      {s.step}. {s.label}
                    </span>
                    <span className="text-[10px] font-mono text-slate-500 hidden sm:inline">
                      {s.desc}
                    </span>
                  </div>
                </div>

                {idx < STEPS.length - 1 && (
                  <div
                    className={`flex-1 h-[2px] mx-2 min-w-[8px] transition-colors duration-200 ${
                      currentStep > s.step
                        ? 'bg-teal-500'
                        : 'bg-slate-200'
                    }`}
                  />
                )}
              </React.Fragment>
            );
          })}

          {/* Pipeline Status Pill */}
          <div className="hidden lg:flex items-center ml-3 pl-3 border-l border-slate-200">
            <span
              className={`px-2 py-0.5 rounded text-[10px] font-mono font-bold tracking-wider uppercase whitespace-nowrap ${
                pipelineStatus === 'COMPLETED'
                  ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                  : pipelineStatus === 'AWAITING_REVIEW' || isPausedAtHitl
                  ? 'bg-amber-50 text-amber-700 border border-amber-200 animate-pulse'
                  : 'bg-slate-100 text-slate-600 border border-slate-200'
              }`}
            >
              {pipelineStatus}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};
