import React from 'react';
import { Waves, GitFork, ShieldAlert, FileCheck2 } from 'lucide-react';
import { TelemetryAnalyticsTab } from '../tabs/TelemetryAnalyticsTab';
import { TopologyTab } from '../tabs/TopologyTab';
import { FMEAMatrixTab } from '../tabs/FMEAMatrixTab';
import { DeliverablesTab } from '../tabs/DeliverablesTab';
import { TelemetryData, SpectrumData, TopologyData, RCAState } from '../../types';

interface ArtifactInspectorProps {
  activeTab: string;
  onSelectTab: (tabId: string) => void;
  telemetry: TelemetryData | null;
  spectrum: SpectrumData | null;
  topology: TopologyData | null;
  rcaState: RCAState | null;
  activeScenarioId: string;
}

export const ArtifactInspector: React.FC<ArtifactInspectorProps> = ({
  activeTab,
  onSelectTab,
  telemetry,
  spectrum,
  topology,
  rcaState,
  activeScenarioId,
}) => {
  const TABS = [
    { id: 'telemetry', label: 'Telemetry & FFT Spectrum', icon: Waves },
    { id: 'topology', label: 'ISA-95 Topology', icon: GitFork },
    { id: 'hypotheses', label: 'FMEA Hypotheses Matrix', icon: ShieldAlert },
    { id: 'deliverables', label: '8D Report & SAP Work Order', icon: FileCheck2 },
  ];

  // Gracefully alias 'fmea' to 'hypotheses' and fallback unknown tabs to 'telemetry'
  const normalizedTab = activeTab === 'fmea' ? 'hypotheses' : activeTab;
  const currentTab = ['telemetry', 'topology', 'hypotheses', 'deliverables'].includes(normalizedTab)
    ? normalizedTab
    : 'telemetry';

  // Trigger a resize event when telemetry tab becomes active to ensure ECharts instances align perfectly
  React.useEffect(() => {
    if (currentTab === 'telemetry') {
      const timer = setTimeout(() => {
        window.dispatchEvent(new Event('resize'));
      }, 50);
      return () => clearTimeout(timer);
    }
  }, [currentTab]);

  return (
    <div className="flex flex-col h-full bg-slate-50/50 border border-slate-200 rounded-2xl shadow-xs overflow-hidden">
      {/* Tab Navigation Header Bar */}
      <div className="bg-white border-b border-slate-200 px-3 pt-2 flex space-x-1 overflow-x-auto scrollbar-none">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const isActive = currentTab === tab.id;
          return (
            <button
              key={tab.id}
              onClick={() => onSelectTab(tab.id)}
              className={`flex items-center space-x-2 px-3.5 py-2.5 font-mono text-xs font-semibold tracking-wide border-b-2 transition-all cursor-pointer whitespace-nowrap rounded-t-lg ${
                isActive
                  ? 'border-teal-600 text-teal-700 bg-teal-50/40'
                  : 'border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-50'
              }`}
            >
              <Icon className={`w-3.5 h-3.5 ${isActive ? 'text-teal-600' : 'text-slate-400'}`} />
              <span>{tab.label}</span>
              {tab.id === 'deliverables' && rcaState?.pipeline_status === 'COMPLETED' && (
                <span className="w-2 h-2 rounded-full bg-emerald-500 ml-1" />
              )}
            </button>
          );
        })}
      </div>

      {/* Tab Content Canvas (Preserved in DOM to prevent canvas tearing / unmount flicker) */}
      <div className="flex-1 overflow-y-auto p-4">
        <div className={currentTab === 'telemetry' ? 'block' : 'hidden'}>
          <TelemetryAnalyticsTab
            telemetry={telemetry}
            spectrum={spectrum}
            activeScenarioId={activeScenarioId}
          />
        </div>

        <div className={currentTab === 'topology' ? 'block' : 'hidden'}>
          <TopologyTab topology={topology} />
        </div>

        <div className={currentTab === 'hypotheses' ? 'block' : 'hidden'}>
          <FMEAMatrixTab rcaState={rcaState} />
        </div>

        <div className={currentTab === 'deliverables' ? 'block' : 'hidden'}>
          <DeliverablesTab rcaState={rcaState} />
        </div>
      </div>
    </div>
  );
};
