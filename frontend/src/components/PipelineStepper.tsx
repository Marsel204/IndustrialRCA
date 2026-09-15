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
}

const STEPS = [
  { step: 1, label: 'Ingest', icon: Database, desc: '1 Hz Ingestion' },
  { step: 2, label: 'Anomaly', icon: Search, desc: 'Change-Point' },
  { step: 3, label: 'Hypotheses', icon: Lightbulb, desc: 'ISO 14224 FMEA' },
  { step: 4, label: 'Falsification', icon: Cpu, desc: 'Evidence Filter' },
  { step: 5, label: '5-Whys Trace', icon: GitMerge, desc: 'Topology Trace' },
  { step: 6, label: 'HITL Gate', icon: ShieldCheck, desc: 'Authorization' },
  { step: 7, label: 'Deliverables', icon: FileCheck2, desc: '8D & SAP PM01' },
];

export const PipelineStepper: React.FC<PipelineStepperProps> = ({
  currentStep,
  isPausedAtHitl,
  pipelineStatus,
}) => {
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
